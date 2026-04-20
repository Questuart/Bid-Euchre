<!-- review-tier: medium -->
# Messaging Revamp Execution Plan
**Date:** 2026-04-20
**Status:** DRAFT
**Goal:** Reduce message-to-attention latency for orchestrator and lane coordination without changing the durable message bus contract. Ship the immediate wins first, then add a broker-style wake-up path only if the lightweight fixes leave unacceptable gaps.

## Summary

The current problem is not bus durability. The problem is attention latency:
messages land in the durable inbox immediately, but the recipient may not look
for several minutes. The orchestrator's `/loop 8m /fleet-check` cadence makes
`completion`, `blocker`, and `escalation` messages feel slow even though the
bus write itself is immediate.

This plan keeps the existing architecture intact:
- `src/bid_euchre/ops/message_bus.py` remains durable truth and stays free of
  tmux delivery side effects.
- `src/bid_euchre/ops/worker_pool.py` remains the home of best-effort pane
  nudges such as `/start-task` and `/inbox-poll`.
- hook-based surfacing remains advisory and prompt-boundary only.

Recommended implementation chain:
1. **PR-MSG-1** — completion path nudge after post-merge notify
2. **PR-MSG-3 (adjusted)** — broaden prompt-boundary surfacing, but only
   auto-ack completions
3. **PR-MSG-2 (adjusted)** — add a delivery-policy helper outside
   `send_message()` for high-value message types
4. **PR-MSG-4 (recommended addition)** — optional attention-broker foundation
   if the first three PRs still leave visible latency or stacking gaps

Adjustment from the original proposal:
- Do **not** add `nudge_recipient` to `send_message()`. That mixes durable bus
  state with tmux-specific side effects and increases circular-import pressure.
  Instead, add a small helper layer that sends the message first, then applies
  delivery policy.

## Scope

In scope:
- Orchestrator wake-up on post-merge completion
- Prompt-boundary surfacing of pending high-priority inbox items
- Message-type-aware best-effort tmux nudges for selected high-value messages
- Tests and hook wiring needed to make the above durable

Out of scope for this chain:
- Inbox TTL hygiene / stale test message cleanup
- Replacing tmux nudges with a Claude-native interrupt API
- Full control-plane rewrite
- Extraction/platform-10 work beyond preserving existing boundaries

## Architecture Constraints

Existing boundaries to preserve:
- `src/bid_euchre/ops/message_bus.py` explicitly "does not actively push or
  poll" and should continue to only write/read durable message state.
- `src/bid_euchre/ops/worker_pool.py` already owns `nudge_inbox()` and is the
  correct place for tmux wake-up mechanics.
- `.claude/hooks/inbox-completion-inject.py` currently auto-acks injected
  completion messages; that behavior must not be widened to blockers or urgent
  alerts.

## PR Chain

### PR-MSG-1 — Completion Wake-Up via Post-Merge Hook

**Intent:** Cut the most common idle gap: author lane merges a PR, completion
message is written, orchestrator remains idle until the next fleet-check cron.

**Change:**
- After `.claude/hooks/post-merge-notify.sh` sends the `completion` message,
  call `nudge_inbox("orchestrator")` as a best-effort follow-up.
- Leave the cron path intact as fallback.

**Files:**
- `.claude/hooks/post-merge-notify.sh` — after successful completion send,
  invoke repo-owned nudge helper
- `src/bid_euchre/ops/worker_pool.py` — no behavioral change expected unless a
  tiny helper wrapper is needed for shell-safe invocation
- `tests/unit/test_post_merge_notify_hook.py` — cover nudge-on-success,
  no-nudge-on-send-failure, auto-merge watcher path

**Requires:** Existing `nudge_inbox()` in `worker_pool.py`

**Produces:** 3-10 second completion-to-orchestrator attention in the normal
case, with cron fallback retained

**Risk:** Low. Nudge is best-effort and advisory only.

### PR-MSG-3 — Prompt-Boundary Surfacing for Pending High-Priority Inbox Items

**Intent:** Make the orchestrator see urgent state on every prompt boundary, not
just on cron boundaries.

**Change:**
- Extend `.claude/hooks/inbox-completion-inject.py` to read:
  - pending/delivered `completion`
  - pending/delivered `blocker`
  - pending/delivered `escalation`
  - pending/delivered high-priority `supervisor_alert`
- Preserve current auto-ack behavior **only** for `completion`.
- Do **not** auto-ack blockers, escalations, or urgent/high alerts just because
  they were surfaced.

**Files:**
- `.claude/hooks/inbox-completion-inject.py` — broaden selection and conditional
  ack logic
- `.claude/hooks/inbox-completion-inject.sh` — no-op wrapper update only if
  comments/help text drift
- `tests/unit/test_inbox_completion_inject.py` — add coverage for:
  - injected urgent/high items are surfaced
  - completions are auto-acked
  - blockers/escalations are not auto-acked

**Requires:** None

**Produces:** Prompt-boundary visibility for urgent inbox state even if cron has
not yet fired

**Risk:** Low-Medium. Main risk is accidental auto-ack of items that still need
human/agent action.

### PR-MSG-2 — Delivery Policy Helper Outside `send_message()`

**Intent:** Give selected message types a standard best-effort wake-up path
without moving tmux logic into the bus layer.

**Change:**
- Add a small helper module or function that:
  1. sends the durable message via `send_message()`
  2. decides whether the recipient should be nudged
  3. calls `nudge_inbox(recipient)` when policy allows
- Apply this helper only to high-value message types:
  - `blocker`
  - `escalation`
  - `supervisor_alert` with `priority in {"high", "urgent"}`
- Keep `completion` on the post-merge fast path from PR-MSG-1.

**Recommended file shape:**
- New file: `src/bid_euchre/ops/attention.py`
  - `send_with_attention(...)`
  - `should_nudge_for_message(...)`
- Or, if the new file feels too heavy for this slice:
  - add a narrowly scoped helper in `src/bid_euchre/ops/monitor.py` or
    `src/bid_euchre/ops/adapters/bid_euchre.py`

**Files:**
- `src/bid_euchre/ops/attention.py` (new) — delivery-policy helper
- `src/bid_euchre/ops/monitor.py` — switch selected send paths to helper
- `src/bid_euchre/ops/message_bus.py` — no signature change
- `tests/unit/test_ops_message_bus.py` — only if shared fixtures are reused
- New test file if needed: `tests/unit/test_ops_attention.py`

**Requires:** PR-MSG-1 not strictly required, but the design should not fight it

**Produces:** Consistent wake-up policy for urgent/high-value messages without
violating the bus boundary

**Risk:** Medium. Main risks are helper placement, accidental policy spread to
low-priority messages, and import cycles if the helper lives in the wrong layer.

### PR-MSG-4 — Attention Broker Foundation (Recommended Addition, Optional)

**Intent:** Add a repo-owned daemon that watches `message_sent` events and
nudges recipients only when they appear safe to poke.

**Why this is recommended in addition:**
- PR-MSG-1/2/3 improve attention latency immediately.
- They do **not** solve the deeper problem that blind `tmux send-keys` can
  collide with active work.
- A small daemon closes that gap without requiring a new Claude lane.

**Change:**
- Add `src/bid_euchre/ops/attention.py` daemon mode:
  - tail `.claude/runtime/events/events.jsonl`
  - inspect recipient pane state
  - nudge immediately if idle/prompt-safe
  - defer and retry if actively working
- Add `ops.py attention once|run|status`
- Add runtime state under `.claude/runtime/attention_broker/`
- Add a session-start or fleet-bootstrap launcher with PID/sentinel dedupe

**Files:**
- `src/bid_euchre/ops/attention.py` — daemon + state model
- `scripts/internal/ops.py` — new `attention` subcommand
- `.claude/hooks/attention-broker-autostart.sh` (new)
- `.claude/settings.json` — register startup hook if enabled
- `.claude/hooks/post-tool-daemon-notify.sh` — optionally include broker
  `FAILED` sentinel discovery
- `tests/unit/test_ops_attention.py`
- `tests/integration/test_attention_broker.py`

**Requires:** PR-MSG-2 helper shape is a good foundation, but not mandatory

**Produces:** Durable attention tickets, deferred-safe nudges, lower collision
risk than blind send-on-write

**Risk:** Medium-High. The hard part is "safe to poke" detection, not event
tailing.

## Dependency Graph

| PR | Depends on | Notes |
|----|------------|-------|
| PR-MSG-1 | none | highest-value immediate win |
| PR-MSG-3 | none | can ship before or after PR-MSG-1 |
| PR-MSG-2 | none | but should follow the adjusted boundary decision in this plan |
| PR-MSG-4 | PR-MSG-2 preferred | optional follow-on, not required for immediate latency win |

Recommended order:
1. PR-MSG-1
2. PR-MSG-3
3. PR-MSG-2
4. PR-MSG-4 (only if needed after proving run)

## Risks

### Execution Risks
- **tmux collision risk:** Any send-keys nudge can still hit an active pane
- **hook semantics drift:** widening completion injection could accidentally ack
  messages that still need action
- **import-cycle risk:** delivery helper placement could create a loop between
  bus, monitor, worker-pool, and adapter layers
- **timeline drift:** PR-MSG-4 is materially larger than the original 3-PR
  estimate and should not be treated as a 30-60 minute add-on

### Rollback Plan
- PR-MSG-1: remove the extra nudge call; completion messaging remains intact
- PR-MSG-3: revert to completion-only injection
- PR-MSG-2: switch call sites back to raw `send_message()`
- PR-MSG-4: disable the autostart hook and leave the module unused

## Test Strategy

### PR-MSG-1
- Add/update unit tests for `.claude/hooks/post-merge-notify.sh`
- Verify:
  - direct merge sends completion and attempts nudge
  - failed merge does nothing
  - auto-merge watcher path nudges only after actual merge

### PR-MSG-3
- Extend `.claude/hooks/inbox-completion-inject.py` tests
- Verify:
  - completions still inject and auto-ack
  - blockers/escalations/high alerts inject but remain unacked
  - empty inbox remains silent

### PR-MSG-2
- Unit test helper policy selection
- Verify:
  - low/normal progress does not nudge
  - blocker/escalation/high supervisor alert nudges
  - message send failure prevents any nudge attempt

### PR-MSG-4
- Unit test event cursor resume, deferred-ticket transitions, and safe/unsafe
  poke decisions
- Integration test: message event arrives while lane is busy, broker defers,
  lane becomes idle, broker nudges once

## Files

- `.claude/hooks/post-merge-notify.sh` — completion fast path
- `.claude/hooks/inbox-completion-inject.py` — prompt-boundary surfacing
- `.claude/hooks/inbox-completion-inject.sh` — wrapper/help text if needed
- `.claude/hooks/attention-broker-autostart.sh` — optional daemon launcher
- `.claude/hooks/post-tool-daemon-notify.sh` — optional broker failure surfacing
- `.claude/settings.json` — optional hook registration
- `src/bid_euchre/ops/message_bus.py` — preserved boundary, no delivery-policy
  signature change
- `src/bid_euchre/ops/worker_pool.py` — existing `nudge_inbox()` consumer
- `src/bid_euchre/ops/monitor.py` — selected call-site policy wiring
- `src/bid_euchre/ops/attention.py` — new helper / optional daemon
- `scripts/internal/ops.py` — optional `attention` CLI surface
- `tests/unit/test_post_merge_notify_hook.py` — PR-MSG-1
- `tests/unit/test_inbox_completion_inject.py` — PR-MSG-3
- `tests/unit/test_ops_attention.py` — PR-MSG-2 / PR-MSG-4
- `tests/integration/test_attention_broker.py` — PR-MSG-4

## Test Criteria
<!-- Define before implementation starts. What proves this work is done? -->
- **Pass condition:** PR-MSG-1/2/3 land with targeted tests and no regression to
  the message bus durability contract; PR-MSG-4 is only taken if follow-up
  proving shows the lightweight fixes are still leaving unacceptable latency or
  nudge collisions.
- **Verification command:** `uv run pytest -q tests/unit/test_post_merge_notify_hook.py tests/unit/test_inbox_completion_inject.py tests/unit/test_ops_message_bus.py tests/integration/test_unread_alert_replay.py`
- **Expected result:** Existing targeted tests remain green; new tests prove
  completion nudges, conditional surfacing/ack behavior, and selected
  high-value nudge policy. If PR-MSG-4 is implemented, broker unit/integration
  tests also pass.

## Outcome
<!-- Filled after implementation -->
- PR: TBD
- Notes: TBD
