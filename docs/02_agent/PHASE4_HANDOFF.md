# Phase 4 Handoff — Remote Channel Implementation

> **Phase:** 4 (`4_remote_channel`)
> **Governing plan:** `plans/agent_ops/governing_plan.md`
> **Status:** IN_PROGRESS (Platform-8a/8b complete, Platform-9a in progress)
> **Last updated:** 2026-03-25

---

## Summary

Phase 4 adds a **remote operator channel** to the steward platform, enabling
the human operator to monitor fleet status and interact with the orchestrator
from a phone (Telegram) when away from the desk.

The implementation follows a layered architecture:

1. **Transport layer** (Platform-8a) — Telegram plugin configuration and
   bidirectional message delivery
2. **Audit layer** (Platform-8b) — Durable repo-owned recording of all
   remote exchanges
3. **Control plane** (SP-4-07) — Controller projection as single source of
   truth for fleet state, with hook-based alert injection and guardrails
4. **Alert push** (Platform-9a) — Proactive push of unresolved alerts to
   Telegram with dedup, backoff, and remote acknowledgement

---

## What Was Built

### Platform-8a: Telegram Transport (COMPLETE)

**Sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-23_platform-8a-telegram-transport.md`

Configured the official Claude Code Channels plugin for Telegram as the
remote transport. Key deliverables:

| Component | Description |
|-----------|-------------|
| Plugin config | Telegram plugin enabled in `.claude/settings.json` |
| tmux launcher | `STEWARD_TELEGRAM_ENABLED` env var + auto-detect in `.claude/tmux/steward-session.sh` |
| Kill switch | `STEWARD_TELEGRAM_ENABLED=0` disables without code changes |
| Orchestrator-only | Only the orchestrator pane receives `--channels`; author lanes stay tmux-only |
| Pairing | Proven with user `8122530898` via `/telegram:access` |

**Key PRs:** #1436, #1451, #1452

### Platform-8b: Audit Trail (COMPLETE)

**Sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-24_platform-8b-audit-trail.md`

Durable recording of all inbound and outbound remote exchanges in a
repo-owned JSONL file.

| Component | Location | Description |
|-----------|----------|-------------|
| Core library | `src/bid_euchre/ops/audit_trail.py` | `append_record()`, `create_record()`, `audit_channel_tag()`, `audit_mcp_outbound()` |
| Outbound hook | `.claude/hooks/post-telegram-audit.sh` | PostToolUse hook for MCP reply/react/edit tools |
| Inbound hook | `.claude/hooks/inbound-channel-audit.sh` + `.py` | UserPromptSubmit hook for `<channel>` tag extraction |
| Storage | **.claude/runtime/audit_trail/remote_exchanges.jsonl** | Append-only JSONL with flock safety |

**Key PRs:** #1532, #1536, #1541, #1715, #1760

### SP-4-07: Controller-First Control Plane (COMPLETE)

**Sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-24_controller-first-control-plane-and-transport-evaluation.md`

The largest single sub-plan in Phase 4 (25+ PRs). Established the controller
projection as the canonical actionable-state surface.

| Component | Location | Description |
|-----------|----------|-------------|
| Controller module | `src/bid_euchre/ops/control_plane.py` | `reconcile()`, `load_fleet_status()`, item mutations (`ack_item`, `clear_item`, `suppress_item`) |
| Alert injection | `.claude/hooks/alert-inject.py` | UserPromptSubmit hook: injects HIGH/URGENT items into orchestrator context |
| Urgent-state guard | `.claude/hooks/urgent-state-guard.py` | PreToolUse hook: blocks merge/dispatch when unresolved urgent state |
| Monitor integration | `src/bid_euchre/ops/monitor.py` | `reconcile()` called during each monitor cycle |
| Fleet CLI | `scripts/internal/ops.py` | Human-friendly projection reader and mutation commands |

**Key exit criteria proven:**
1. Unread-alert replay through controller projection (10 tests)
2. Noise discrimination in controller projection (proving run 2)
3. Persistence, dedup, and clear lifecycle (7 tests)
4. False-stall prevention via stall guard (6 tests)
5. Outbound audit wired into PostToolUse hook
6. Telegram e2e remote loop (messages 83-86)

**Key PRs:** #1618, #1633, #1699, #1701, #1703, #1704, #1712, #1714, #1715,
#1718, #1719, #1730, #1755, #1760, #1764

### Platform-9a: Alert Push (IN PROGRESS)

**Sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-25_platform-9a-idle-attention-alerts.md`

Proactive push of unresolved alerts to the operator's Telegram when the
fleet is idle.

| Component | Location | Description |
|-----------|----------|-------------|
| Alert push evaluator | `src/bid_euchre/ops/alert_push.py` | Pure-function evaluator: filters items, applies dedup/backoff |
| Push state | **.claude/runtime/alert_push_state.json** | Tracks per-item push timestamps and counts |
| Remote ack parser | `src/bid_euchre/ops/remote_ack.py` | Parses `ack`/`dismiss`/`mute`/`clear` from inbound text |
| Telegram push adapter | `src/bid_euchre/ops/telegram_push.py` | Formats messages, gates on kill switch, orchestrates push cycle |
| Idle detector | `src/bid_euchre/ops/idle_detector.py` | Determines fleet idle state from event log |

**Key PRs (merged so far):** #1777 (remote ack parser), #1781 (alert push evaluator)

---

## Architecture Decisions

### Transport Choice: Telegram via Claude Channels

**Decision:** Use the official Claude Code Channels plugin for Telegram
rather than building a custom transport.

**Rationale:** The Channels plugin provides bidirectional message delivery,
pairing/access control, and MCP tool integration out of the box. Custom
transport would duplicate this and require ongoing maintenance.

**Trade-off:** Dependency on Claude Code plugin ecosystem. Mitigated by
keeping the audit trail and controller projection repo-owned.

### Controller as Single Truth

**Decision:** All actionable state flows through the controller projection.
Hooks, dashboards, and remote adapters consume this projection — they do
not build their own views of urgency.

**Rationale:** Without a single truth, different surfaces (local terminal,
Telegram, dashboard) would disagree on fleet state. The controller's
`reconcile()` function merges all signal sources into one coherent view.

### Orchestrator-Only Ingress

**Decision:** Only the orchestrator pane processes inbound Telegram messages.
Author lanes remain tmux-only.

**Rationale:** The orchestrator is the dispatch authority. Allowing direct
remote control of author lanes would bypass task dispatch, scope lock, and
review gates.

### Audit Before Trust

**Decision:** Every remote exchange is durably recorded before the message
is processed or the response is sent.

**Rationale:** Remote channels introduce an external trust boundary. The
audit trail provides forensic traceability for incident review and enables
post-hoc verification that the remote channel was not misused.

---

## Hook Registration Map

| Hook | Event | File | Purpose |
|------|-------|------|---------|
| Alert injection | UserPromptSubmit | `.claude/hooks/alert-inject.sh` + `.py` | Inject HIGH/URGENT alerts into orchestrator context |
| Inbound audit | UserPromptSubmit | `.claude/hooks/inbound-channel-audit.sh` + `.py` | Record inbound `<channel>` tags to audit trail |
| Outbound audit | PostToolUse (Telegram tools) | `.claude/hooks/post-telegram-audit.sh` | Record outbound MCP tool calls to audit trail |
| Urgent-state guard | PreToolUse (Bash) | `.claude/hooks/urgent-state-guard.py` | Block merge/dispatch when urgent state unresolved |

All hooks are registered in `.claude/settings.json`.

---

## File Inventory

### Source Code (under `src/bid_euchre/ops/`)

| File | Platform | Description |
|------|----------|-------------|
| `control_plane.py` | SP-4-07 | Controller projection: reconcile, load, mutations |
| `alert_push.py` | 9a | Alert push evaluator with dedup/backoff |
| `remote_ack.py` | 9a | Parse and execute remote ack commands |
| `telegram_push.py` | 9a | Telegram-specific push adapter |
| `audit_trail.py` | 8b | Durable audit trail for remote exchanges |
| `idle_detector.py` | 9a | Fleet idle detection from event log |
| `monitor.py` | SP-4-07 | Monitor with controller integration and stall detection |
| `message_bus.py` | Pre-4 | Lane-to-lane messaging (used by controller inputs) |
| `events.py` | Pre-4 | Durable event log (used by idle detector) |

### Hooks (under `.claude/hooks/`)

| File | Phase 4 Role |
|------|-------------|
| `alert-inject.sh` + `.py` | Local alert injection into orchestrator |
| `urgent-state-guard.py` | Merge/dispatch guard on urgent state |
| `inbound-channel-audit.sh` + `.py` | Inbound Telegram audit |
| `post-telegram-audit.sh` | Outbound Telegram audit |
| `pre-bash-dispatch.sh` | Consolidated PreToolUse dispatcher (orchestrates guards) |

### Runtime State (under `.claude/runtime/`)

| File | Owner | Description |
|------|-------|-------------|
| fleet_status.json | Controller | Canonical actionable-state projection |
| alert_push_state.json | Alert push | Per-item push timestamps and counts |
| **audit_trail/remote_exchanges.jsonl** | Audit trail | Append-only remote exchange log |
| stall_state.json | Monitor | Cross-cycle stall detection state |
| approval_stall_state.json | Monitor | Approval prompt detection state |

---

## Remaining Work

### Platform-9a Completion (Step 4)

- [ ] Telegram wiring: integrate `prepare_alert_push()` into orchestrator
  monitor/check-in cycle
- [ ] E2e loop proving: push alert -> operator acks from phone -> item
  state changes in projection

### Platform-9b: Away-from-Desk Queue Moving (Step 5)

- [ ] Operator can review and approve task dispatches from Telegram
- [ ] Operator can trigger `/check-in` and receive status summary remotely
- [ ] Queue-moving proving run: dispatch, monitor, ack cycle without desktop

### Platform-9c: First Hardening Pass (Step 6)

- [ ] Fix real proving-run issues discovered in 9a/9b
- [ ] Update operator documentation with lessons learned
- [ ] Record known gaps and deferred items
- [ ] Phase 4 handoff: mark COMPLETE, update governing plan

---

## Known Gaps and Debt

| Item | Severity | Description |
|------|----------|-------------|
| Two messaging transports | Low | Internal bus and Telegram coexist but are not consolidated (#1289 ADR written) |
| Permission stalls | Medium | Settings self-edit prompt is platform-hardcoded; workaround is Esc+2 (#1759) |
| Token economy telemetry | Low | Pipeline broken after Claude Code v2.1.80+ format change (#1770) |
| Analyst pool dispatch | Low | Analyst lane not in KNOWN_AUTHOR_LANES; dispatch via tmux only (#1769) |
| Multiple operators | Deferred | v1 supports single operator only |
| Discord | Deferred | Telegram only in v1 |

---

## Operator Reference

For day-to-day operation, see:
- **Runbook:** `docs/02_agent/PHASE4_OPERATOR_RUNBOOK.md`
- **Autonomous workflow:** `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
- **Review loop:** `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`
