# Platform-9a — Idle-Attention Alerts and Remote Acknowledgement Loop

**ID:** SP-4-08
**Date:** 2026-03-25
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Step 4 (Platform-9a)
**Status:** in_progress
**Owner:** multi-lane (overnight fleet + author-c)

---

## Problem Statement

The steward platform can detect fleet idle state and project actionable items
through the controller, but it cannot proactively push those items to an
away-from-desk operator. When the operator is not watching the terminal, work
sits idle until they return — defeating the purpose of the remote channel
infrastructure built in Platform-8.

The pieces exist in isolation:

| Component | Location | What it does |
|-----------|----------|--------------|
| Idle detector | `src/bid_euchre/ops/idle_detector.py` | Detects when no meaningful event has occurred within a threshold |
| Controller projection | `src/bid_euchre/ops/control_plane.py` | Derives actionable items, supports `ack`/`clear`/`suppress` |
| Alert injection hook | `.claude/hooks/alert-inject.py` | Injects HIGH/URGENT items into orchestrator context (local only) |
| Telegram channel | Claude Channels plugin (proven SP-4-04) | Bidirectional message delivery to operator's phone |
| Audit trail | `src/bid_euchre/ops/audit_trail.py` | Records inbound/outbound remote exchanges |
| Fleet CLI | `scripts/internal/ops.py fleet` | Reads/mutates controller projection (ack/clear/suppress) |

What is **missing** is the glue:

1. **Proactive push:** No code path reads the controller projection and pushes
   unresolved items to Telegram when the operator is away. The alert injection
   hook only works when the orchestrator is actively prompting — it is reactive,
   not proactive.

2. **Remote acknowledgement:** The operator can ack items via the CLI
   (`ops.py fleet --ack <id>`), but there is no path from a Telegram reply
   back to `ack_item()` / `clear_item()` in the controller. The operator must
   be at the terminal to acknowledge alerts.

3. **Backoff and dedup:** Without these, pushing alerts to Telegram would spam
   the operator with repeated notifications for the same unresolved item across
   monitor cycles.

## Goals

1. Enable the orchestrator to proactively push unresolved HIGH/URGENT controller
   items to the operator via Telegram when the fleet is idle or unattended.
2. Enable the operator to acknowledge or dismiss alerts from Telegram without
   being at the terminal.
3. Implement dedup and backoff so repeated monitor cycles do not spam the
   operator's phone.
4. Keep controller projection as the single source of truth — Telegram is an
   adapter, not a state store.

## Non-Goals

- Building a full remote command language (deferred to Platform-9b)
- Replacing the local alert injection hook (it stays for terminal-active use)
- Supporting multiple remote operators (v1 is single-operator)
- Discord support (Telegram only in v1)
- Automatic remediation from remote ack (ack changes alert state, not fleet state)
- Push notifications for INFO/WARN items (only HIGH/URGENT)

## Scope

### In Scope

1. **Alert push adapter** — a function that reads `fleet_status.json`, filters
   for open HIGH/URGENT items not yet pushed, and sends a formatted summary to
   the configured Telegram chat via the `reply` MCP tool.

2. **Push dedup and backoff** — track which `item_id` values have been pushed
   and when. Re-push only if: (a) a new item appears, (b) an existing item
   escalates in severity, or (c) a cooldown period (e.g., 15 minutes) has
   elapsed since the last push for that item.

3. **Remote ack parsing** — when the operator replies to an alert in Telegram
   with a recognized pattern (e.g., `ack <prefix>`, `dismiss <prefix>`,
   `mute <prefix>`), the orchestrator maps that to `ack_item()` /
   `suppress_item()` on the controller projection.

4. **Ack confirmation** — after processing a remote ack, reply in Telegram
   confirming the action (e.g., "Acked item abc123de — approval stall on
   author-b").

5. **Integration with monitor cycle** — the push check runs after each
   `reconcile()` call (piggybacks on the existing ops monitoring loop), not on
   a separate timer.

6. **Audit trail integration** — all outbound alert pushes and inbound ack
   commands are recorded via `audit_trail.py`.

### Out of Scope

- Remote task dispatch or rerouting (Platform-9b)
- Remote status queries ("what's the fleet doing?") (Platform-9b)
- Multi-channel fanout (push to both Telegram and desktop notification)
- Custom alert severity thresholds per operator preference
- Historical alert browsing via Telegram

## Existing Infrastructure to Reuse

### Idle Detector (`idle_detector.py`)

- `is_fleet_idle(threshold_minutes)` → `IdleStatus` — used to decide whether
  the operator is likely away and should receive push alerts.
- `MEANINGFUL_EVENT_TYPES` — defines what counts as "activity."
- Already tested (`tests/unit/test_ops_idle_detector.py`).

### Controller Projection (`control_plane.py`)

- `load_fleet_status()` → `FleetStatus` — reads the current projection.
- `FleetStatus.open_items`, `.urgent_items`, `.high_items` — filtered views.
- `ack_item()`, `clear_item()`, `suppress_item()` — mutation API.
- `save_fleet_status()` — atomic persistence after mutation.
- `ActionableItem.item_id` — stable 12-char hex ID for dedup/tracking.
- Already tested (`tests/unit/test_ops_control_plane.py`,
  `tests/integration/test_ops_control_plane.py`).

### Alert Injection Hook (`alert-inject.py`)

- Reads `fleet_status.json` and formats HIGH/URGENT items as context.
- `format_alert_context()` — reusable formatting function.
- Pattern to follow: read projection, filter, format, output.

### Telegram Channel

- Proven bidirectional (SP-4-04, PR #1616 inbound fix).
- Outbound: `mcp__plugin_telegram_telegram__reply(chat_id, text)`.
- Inbound: arrives as `<channel source="telegram" chat_id="..." ...>` tags.
- `STEWARD_TELEGRAM_ENABLED` env var controls kill switch.

### Audit Trail (`audit_trail.py`)

- `append_record()` — write to JSONL audit log.
- `AuditRecord` dataclass with direction, exchange_type, content_preview, etc.
- Outbound hook already wired via `audit_mcp_outbound` (PR #1715).

### Fleet CLI (`ops.py fleet`)

- `--ack`, `--clear`, `--suppress` with prefix matching.
- Pattern to follow for remote ack: parse prefix from Telegram message, call
  the same `ack_item()` / `suppress_item()` functions.

## Architecture

```
                    ┌───────────────────────────┐
                    │     Monitor Cycle          │
                    │  run_monitoring_cycle()    │
                    │        ↓                   │
                    │  reconcile()               │
                    │        ↓                   │
                    │  fleet_status.json         │
                    └───────────┬───────────────┘
                                │
                    ┌───────────▼───────────────┐
                    │  Idle-Attention Evaluator  │
                    │                           │
                    │  1. Is fleet idle/         │
                    │     unattended?            │
                    │  2. Any open HIGH/URGENT   │
                    │     items not yet pushed?  │
                    │  3. Backoff not active?    │
                    │        ↓                   │
                    │  Push alert to Telegram    │
                    │  Record in push_state.json │
                    │  Audit via audit_trail     │
                    └───────────┬───────────────┘
                                │
                    ┌───────────▼───────────────┐
                    │       Telegram             │
                    │   (operator's phone)       │
                    └───────────┬───────────────┘
                                │
                    ┌───────────▼───────────────┐
                    │  Inbound Ack Parser       │
                    │                           │
                    │  "ack abc123" →            │
                    │    ack_item(status, id)    │
                    │    save_fleet_status()     │
                    │    reply confirmation      │
                    │    audit via audit_trail   │
                    └───────────────────────────┘
```

## Key Decisions for Review

### KD-1: Push trigger — idle-based vs timer-based

**Recommendation: Idle-based (Option A).**

- **Option A (idle-based):** Only push alerts when `is_fleet_idle()` returns
  True or no orchestrator prompt has been submitted in N minutes. This avoids
  spamming the operator's phone while they're actively working at the terminal.

- **Option B (timer-based):** Push on every monitor cycle regardless of
  operator presence. Simpler but noisy — the operator gets Telegram pings
  while actively working on the alerts locally.

- **Option C (hybrid):** Push immediately for URGENT, idle-gate for HIGH.
  More nuanced but adds complexity to v1.

Evidence: The check-in skill already polls at 3-minute intervals during active
fleet runs. Adding Telegram pushes on every cycle would create ~20 messages/hour
for a single unresolved alert (before backoff). Idle-gating avoids this.

### KD-2: Ack command format

**Recommendation: Prefix-based free-form (Option A).**

- **Option A (prefix-based):** Operator replies `ack abc1`, `dismiss abc1`, or
  `mute abc1` where `abc1` is the item_id prefix. Matches the CLI pattern
  (`ops.py fleet --ack abc1`). Simple, consistent, no new grammar.

- **Option B (button-based):** Use Telegram inline keyboard buttons attached to
  each alert message. More polished UX but requires tracking callback_query
  state, which the current Claude Channels plugin may not support.

- **Option C (reply-quote):** Operator quotes the alert message and types
  "ack". Telegram-native but harder to parse reliably.

Evidence: The `ops.py fleet --ack` CLI already supports prefix matching with
ambiguity detection. Reusing the same prefix model keeps the mental model
consistent and avoids Telegram API features that may not be exposed through the
Claude plugin.

### KD-3: Push state storage

**Recommendation: Dedicated `push_state.json` (Option A).**

- **Option A (dedicated file):** Store push tracking in
  `.claude/runtime/alert_push_state.json` with per-item-id last-pushed
  timestamps. Separate from `fleet_status.json` to keep the controller
  projection transport-agnostic.

- **Option B (embed in fleet_status.json):** Add `last_pushed_at` fields to
  `ActionableItem`. Simpler but couples the controller projection to the
  Telegram adapter.

Evidence: The controller projection is designed to be consumed by multiple
adapters (hooks, CLI, remote channels). Embedding push state in it would make
it Telegram-specific, violating the adapter separation established in SP-4-07.

### KD-4: Backoff strategy

**Recommendation: Simple cooldown per item (Option A).**

- **Option A (fixed cooldown):** Don't re-push the same `item_id` within N
  minutes (configurable, default 15). Reset cooldown if severity escalates.

- **Option B (exponential backoff):** First push at 0, then 5min, 15min, 30min,
  60min. More sophisticated but complex for v1.

Evidence: The monitor cycle already runs every ~3 minutes. With 15-minute fixed
cooldown, an unresolved URGENT item generates at most 4 pushes/hour — tolerable
for the single-operator v1 use case. If insufficient, upgrade to exponential in
Platform-9c hardening.

## PR Decomposition

### PR 1 — Alert push evaluator and push state tracking

**Goal:** Add the core logic that decides when to push alerts and tracks what
has been pushed.

**Scope:**
- New module: `src/bid_euchre/ops/alert_push.py`
  - `evaluate_push_needed(fleet_status, idle_status, push_state) → list[ActionableItem]`
  - `PushState` dataclass (per-item-id: last_pushed_at, push_count, severity_at_push)
  - `load_push_state()` / `save_push_state()` (atomic file I/O)
  - `record_push(push_state, item_id)` — update tracking after successful push
  - Backoff logic: skip if same item pushed within cooldown window
  - Dedup logic: skip if item severity unchanged since last push
- New tests: `tests/unit/test_ops_alert_push.py`
  - Push needed when idle + open HIGH/URGENT items exist
  - Push skipped when fleet is active (not idle)
  - Push skipped when item already pushed within cooldown
  - Push triggered when severity escalates (WARN→HIGH or HIGH→URGENT)
  - Push state persistence round-trip
  - Empty fleet status produces no pushes
  - Cooldown reset on severity change

**Files:**
- `src/bid_euchre/ops/alert_push.py` (new)
- `tests/unit/test_ops_alert_push.py` (new)

**Exit criteria:**
- All unit tests pass
- `evaluate_push_needed()` is a pure function (no I/O, no Telegram calls)
- Push state is transport-agnostic (no Telegram references in the data model)

### PR 2 — Remote ack parser and controller mutation

**Goal:** Parse ack/dismiss/mute commands from inbound Telegram messages and
apply them to the controller projection.

**Scope:**
- New module or extension: `src/bid_euchre/ops/remote_ack.py`
  - `parse_ack_command(text) → AckCommand | None`
    - Recognized patterns: `ack <prefix>`, `dismiss <prefix>`, `mute <prefix>`,
      `clear <prefix>`
    - Case-insensitive, leading/trailing whitespace tolerant
    - Returns None for non-command messages (free-form conversation)
  - `execute_remote_ack(command, fleet_status) → AckResult`
    - Maps `ack` → `ack_item()`, `dismiss`/`mute` → `suppress_item()`,
      `clear` → `clear_item()`
    - Includes prefix-match ambiguity detection (same as CLI)
    - Returns success/failure with human-readable message
  - `format_ack_confirmation(result) → str` — Telegram-friendly confirmation text
- New tests: `tests/unit/test_ops_remote_ack.py`
  - Parse valid commands with various prefix lengths
  - Parse case-insensitive variants
  - Reject non-command messages (return None)
  - Execute ack on matching item → state changes to `acked`
  - Execute suppress on matching item → state changes to `suppressed`
  - Ambiguous prefix → error result with candidate list
  - No matching item → error result
  - Item already acked → error result (idempotency note)

**Files:**
- `src/bid_euchre/ops/remote_ack.py` (new)
- `tests/unit/test_ops_remote_ack.py` (new)

**Exit criteria:**
- All unit tests pass
- Parser handles all documented patterns
- Mutation calls use the existing `control_plane.py` API (no bypass)
- No Telegram-specific code in this module (pure logic)

### PR 3 — Telegram push adapter and monitor cycle integration

**Goal:** Wire the push evaluator into the ops monitor cycle and send actual
Telegram messages via the MCP plugin.

**Scope:**
- New module: `src/bid_euchre/ops/telegram_push.py`
  - `format_alert_push(items: list[ActionableItem]) → str`
    — Format items as a Telegram-friendly message with item_id prefixes
    visible for ack replies
  - `push_alerts_to_telegram(chat_id, items)` — calls MCP `reply` tool
  - `ALERT_PUSH_CHAT_ID` env var or config for target chat
- Wire into `cmd_monitor()` in `scripts/internal/ops.py`:
  - After `reconcile()`, call `evaluate_push_needed()`
  - If items need pushing and Telegram is enabled, call `push_alerts_to_telegram()`
  - Record push in push state and audit trail
- Add `--no-push` flag to `ops.py monitor` to disable push (for tests)
- Integration test: `tests/integration/test_alert_push_integration.py`
  - Full cycle: seed finding → monitor → reconcile → evaluate → push decision
  - Verify push state updated after push
  - Verify audit record created for outbound alert push

**Files:**
- `src/bid_euchre/ops/telegram_push.py` (new)
- `scripts/internal/ops.py` (extend `cmd_monitor`)
- `tests/integration/test_alert_push_integration.py` (new)

**Exit criteria:**
- Alert push fires after reconcile when idle + unresolved items exist
- Push state prevents re-push within cooldown window
- Audit trail records every outbound push
- `--no-push` flag prevents any Telegram calls (for CI)
- `STEWARD_TELEGRAM_ENABLED=0` also prevents push (kill switch honored)

### PR 4 — Inbound ack wiring and end-to-end proving

**Goal:** Wire inbound Telegram messages through the ack parser and prove the
full alert → push → ack → confirm loop.

**Scope:**
- Wire inbound ack parsing into the orchestrator's Telegram message handling:
  - When a `<channel source="telegram">` message arrives, check if it matches
    an ack command pattern
  - If yes: execute the remote ack, send confirmation reply, audit both
    the inbound command and outbound confirmation
  - If no: pass through to normal orchestrator handling (free-form message)
- Orchestrator skill/instruction update to document ack command handling
- End-to-end integration test: `tests/integration/test_remote_ack_loop.py`
  - Seed an unresolved HIGH item
  - Simulate inbound "ack <prefix>" message
  - Verify item state changes to `acked`
  - Verify confirmation reply would be sent
  - Verify audit records for both directions
- Update `.claude/skills/check-in/SKILL.md` with remote ack documentation

**Files:**
- `.claude/skills/check-in/SKILL.md` or new skill docs (extend)
- `tests/integration/test_remote_ack_loop.py` (new)
- Orchestrator-facing instruction/wiring (skill or hook)

**Exit criteria:**
- Inbound ack commands correctly mutate controller state
- Non-command messages pass through unchanged
- Confirmation reply sent after successful ack
- Both directions audited
- Full loop proven in integration test

## Exit Criteria (Sub-Plan Level)

This sub-plan is complete only when all of the following are met:

| # | Criterion | Pass/Fail Test |
|---|-----------|----------------|
| E1 | Unresolved HIGH/URGENT items are proactively pushed to Telegram when the fleet is idle | Seed a HIGH finding, confirm fleet is idle, run monitor cycle → Telegram message received |
| E2 | Push dedup prevents repeated alerts for the same item within the cooldown window | Push an alert, run 3 more monitor cycles within cooldown → only 1 Telegram message sent |
| E3 | Severity escalation triggers a re-push even within the cooldown window | Push a HIGH alert, escalate to URGENT → new Telegram message sent |
| E4 | Operator can ack an alert from Telegram with `ack <prefix>` | Send "ack abc1" via Telegram → item state changes to `acked` in `fleet_status.json` |
| E5 | Operator can suppress an alert from Telegram with `mute <prefix>` | Send "mute abc1" via Telegram → item state changes to `suppressed` |
| E6 | Ack confirmation is sent back to Telegram after successful ack | Execute remote ack → confirmation reply appears in Telegram chat |
| E7 | All pushes and acks are recorded in the audit trail | Check `remote_exchanges.jsonl` after push+ack → both records present |
| E8 | Push is suppressed when `STEWARD_TELEGRAM_ENABLED=0` | Set env var to 0, run monitor cycle with unresolved items → no Telegram call made |
| E9 | At least one real remote round-trip is proven | Human operator receives alert on phone, sends ack, sees confirmation — all without terminal |

## Validation Commands

```bash
# Unit tests (Tier 1 — during implementation)
uv run python -m pytest tests/unit/test_ops_alert_push.py -v
uv run python -m pytest tests/unit/test_ops_remote_ack.py -v

# Integration tests (Tier 1 — after wiring)
uv run python -m pytest tests/integration/test_alert_push_integration.py -v
uv run python -m pytest tests/integration/test_remote_ack_loop.py -v

# Full validation (Tier 2 — before PR)
make check-quiet

# Manual proving (E9 — requires operator + phone)
# 1. Ensure STEWARD_TELEGRAM_ENABLED=1 and fleet is idle
# 2. Seed a HIGH finding: uv run python scripts/internal/ops.py monitor
# 3. Verify Telegram message received on phone
# 4. Reply "ack <prefix>" from phone
# 5. Verify item state changed: uv run python scripts/internal/ops.py fleet
# 6. Verify audit: cat .claude/runtime/audit_trail/remote_exchanges.jsonl | tail -5
```

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Telegram rate limits on rapid push | Low | Alert delivery delayed | Backoff already in design; batch multiple items per message |
| Claude Channels plugin drops inbound ack messages | Medium | Operator thinks they acked but state unchanged | Confirmation reply makes success/failure visible; operator retries |
| Push state file corruption | Low | Re-pushes or lost push history | Atomic write pattern (same as fleet_status.json); push state is reconstructible |
| Ambiguous item_id prefix from phone keyboard | Medium | Ack fails, operator frustrated | Return candidate list in error reply; suggest longer prefix |
| MCP tool calls from orchestrator context may not be available in all hook contexts | Medium | Cannot push from hooks, only from active orchestrator conversation | Design as orchestrator-invoked function, not hook — hooks remain read-only |

## Implementation Hazards

1. **MCP tool availability:** The `reply` MCP tool is only callable from an
   active Claude Code conversation with the Telegram plugin enabled. The push
   adapter must run within the orchestrator's conversation context (e.g.,
   during `/check-in` or the monitor cycle), not from a standalone script or
   background agent. This is a platform constraint, not a design choice.

2. **Inbound message ordering:** If the operator sends multiple ack commands
   rapidly, they arrive as separate `<channel>` tags. Each must be processed
   independently. No batching or ordering guarantees.

3. **Controller state race:** Between reading `fleet_status.json` and saving
   after ack, another monitor cycle could overwrite the file. The existing
   `merge_with_previous()` pattern in `reconcile()` preserves ack state
   across cycles, so this is safe as long as ack mutations use
   `load_fleet_status()` → mutate → `save_fleet_status()` atomically.

## File Ownership and Safe Parallelism

| File | Owner | Notes |
|------|-------|-------|
| `src/bid_euchre/ops/alert_push.py` | PR 1 | New file, no conflicts |
| `src/bid_euchre/ops/remote_ack.py` | PR 2 | New file, no conflicts |
| `src/bid_euchre/ops/telegram_push.py` | PR 3 | New file, no conflicts |
| `scripts/internal/ops.py` | PR 3 | Extends `cmd_monitor()` only |
| `tests/unit/test_ops_alert_push.py` | PR 1 | New file |
| `tests/unit/test_ops_remote_ack.py` | PR 2 | New file |
| `tests/integration/test_alert_push_integration.py` | PR 3 | New file |
| `tests/integration/test_remote_ack_loop.py` | PR 4 | New file |

**Safe parallelism:** PRs 1 and 2 are fully independent (disjoint new files).
PR 3 depends on PR 1. PR 4 depends on PRs 2 and 3.

```
PR 1 (push evaluator) ──────┐
                             ├──→ PR 3 (Telegram wiring) ──→ PR 4 (end-to-end)
PR 2 (ack parser) ──────────┘                                       ↑
                             └──────────────────────────────────────┘
```

## Dependencies

- **SP-4-07 COMPLETE** — controller projection must be live and proven.
- **Telegram channel proven** — bidirectional delivery confirmed (SP-4-04).
- **Audit trail library** — available (SP-4-06).
- **Idle detector** — available and tested.

## Session Log

| Date | Summary |
|------|---------|
| 2026-03-25 | SP-4-08 drafted as proposed by analyst lane. 4-PR decomposition covering push evaluator, ack parser, Telegram wiring, and end-to-end proving. 4 key decisions flagged for review (push trigger, ack format, push state storage, backoff strategy). |
