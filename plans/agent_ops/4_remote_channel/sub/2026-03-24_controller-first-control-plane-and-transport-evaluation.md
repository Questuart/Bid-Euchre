# Controller-First Control Plane And Transport Evaluation

**ID:** SP-4-07
**Date:** 2026-03-24
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 4, Pre-Platform-9 / transport-consolidation follow-up
**Status:** proposed
**Owner:** orchestrator

---

## Problem Statement

The steward platform now has multiple transport surfaces:

- repo-owned task packets, events, review verdicts, and the custom message bus
- Claude native inboxes populated by `SendMessage`
- Claude Channels for remote/plugin delivery
- hooks that can inject or block at local execution boundaries
- tmux pane nudges as the current live-session fallback

The platform's current failure mode is not lack of storage. It is lack of one
authoritative controller that decides:

- what changed
- what is urgent
- what can wait
- what action is next
- when an alert has been acknowledged or cleared

Without that controller, transport debates (`SendMessage` vs custom bus vs
Channels vs hooks) collapse into current-system bias. The platform keeps adding
delivery mechanisms without settling what the canonical actionable state is.

This sub-plan fixes that by introducing a controller-first control plane and a
comparative proving path for the available delivery adapters.

## Goals

1. Make repo-owned reconciled state the only control-plane truth.
2. Keep the custom bus as durable coordination/audit transport, not the primary
   alert brain.
3. Use hooks for local surfacing and guardrails.
4. Use Claude Channels as the preferred remote/live-session push adapter if the
   proving data supports it.
5. Keep native `SendMessage` / native inboxes as optional conversational signal
   sources until `#1289` is resolved with evidence.

## Inputs

- `plans/agent_ops/governing_plan.md`
- `plans/agent_ops/4_remote_channel/plan.md`
- `plans/agent_ops/4_remote_channel/checkpoints.md`
- `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`
- `plans/agent_ops/4_remote_channel/sub/2026-03-24_platform-8b-audit-trail.md`
- `plans/sessions/2026-03-23_operator-hardening.md`
- Issue `#1289` -- transport consolidation reassessment
- Issue `#1571` -- messaging re-evaluation
- Issue `#1573` -- Platform-8b runtime wiring gap
- Issue `#1597` -- missing orchestration lifecycle integration test
- Issue `#1581` -- pass/fail criteria requirement
- `src/bid_euchre/ops/monitor.py`
- `src/bid_euchre/ops/message_bus.py`
- `src/bid_euchre/ops/scheduler.py`
- `src/bid_euchre/ops/dashboard.py`
- `scripts/internal/ops.py`

## Scope

This sub-plan covers:

- a repo-owned controller/reconciler that derives actionable state
- a stable machine-readable control-plane projection
- hook-based local surfacing and guardrails fed from that projection
- Platform-8b runtime wiring against the controller, not only raw transport
- comparative evaluation of custom bus, native inbox bridge, and Channels
- outcome-based smoke/full/proving gates for transport decisions

This sub-plan does **not** cover:

- replacing task packets, review verdicts, or the current review gate
- moving authoritative workflow state into Claude-native inboxes or Channels
- enabling author lanes for direct remote ingress
- making tmux nudges the primary control-plane mechanism
- final Discord rollout

## Locked Architectural Decisions

- **Repo-owned state is canonical.**
  - Task packets, review verdicts, lifecycle events, lane state, and the
    controller projection remain the only workflow truth.
- **The custom bus stays.**
  - It remains the durable lane-to-lane transport and audit record.
  - It is not the sole urgent-alert consumption path.
- **Native `SendMessage` stays optional.**
  - Native inboxes may be imported into the repo-owned surface.
  - Native inboxes are not promoted to canonical workflow truth in this slice.
- **Claude Channels are the preferred remote push adapter.**
  - If remote proving succeeds, Channels become the preferred way to push into
    the running orchestrator session.
  - Channels remain adapters on top of repo-owned state.
- **Hooks enforce local boundaries.**
  - Hooks may surface unresolved urgent state or block unsafe actions.
  - Hooks do not become the authoritative state store.
- **tmux nudges remain fallback-only.**
  - They may wake or re-nudge a live pane, but they do not define control-plane
    truth.

## Deliverables

### 1. Controller / reconciler module

Add a repo-owned module, likely one of:

- `src/bid_euchre/ops/control_plane.py`
- `src/bid_euchre/ops/attention_state.py`

It should read:

- monitor findings
- task packets / task lifecycle state
- review verdict state
- lane/session registry and lane activity state
- message bus records
- native inbox imports when enabled
- remote audit records when relevant

It should write:

- `.claude/runtime/fleet_status.json`
- optional `.claude/runtime/next_actions.json`

Minimum fields per item:

- stable `item_id`
- `severity`
- `category`
- `source`
- `first_seen_at`
- `last_seen_at`
- `state` (`open`, `acked`, `cleared`, `suppressed`)
- related lane / task / PR identifiers
- recommended action
- escalation metadata if applicable

### 2. Hook-fed local enforcement

Add hook behavior driven by the controller projection:

- `UserPromptSubmit` -- inject unresolved P0/P1 state into orchestrator context
- `PreToolUse` -- warn or block risky actions (dispatch, merge, similar) when
  unresolved P0 exists
- `Stop` / `TaskCompleted` -- prevent false completion when required checks or
  unresolved critical state remain

### 3. Platform-8b runtime wiring

Finish remote audit and runtime integration by ensuring:

- inbound remote messages update the controller and audit surfaces
- outbound replies/reacts/edits update the controller and audit surfaces
- controller state, not raw transport, decides alert visibility

### 4. Transport comparison matrix

Produce a short architecture decision record covering:

- custom bus
- native `SendMessage` / native inbox bridge
- Claude Channels
- hooks
- tmux nudges

Criteria:

- latency to surface urgent state
- durability / replayability
- structured metadata support
- ack / clear compatibility
- auditability
- operator usability
- implementation and maintenance cost

## PR Roadmap

### PR 1 -- Stabilization gate and lifecycle test baseline

**Goal:** Remove obvious substrate bugs and add the missing end-to-end
orchestration lifecycle test.

**Scope:**

- fix open correctness debt that would poison the controller layer
- add `tests/integration/test_orchestration_lifecycle.py`
- align Phase 4 docs with actual runtime wiring state

**Likely files:**

- `src/bid_euchre/ops/message_bus.py`
- `src/bid_euchre/ops/monitor.py`
- `.claude/skills/park/SKILL.md`
- `tests/integration/test_orchestration_lifecycle.py`
- `tests/unit/test_ops_message_bus.py`
- `tests/unit/test_ops_monitor.py`

**Primary issues:**

- `#1596`
- `#1610`
- `#1612`
- `#1580`
- `#1597`
- `#1573`

### PR 2 -- Controller projection

**Goal:** Publish one canonical actionable-state projection.

**Scope:**

- add controller/reconciler module
- derive controller state from monitor/task/review/lane surfaces
- write `fleet_status.json` / `next_actions.json`
- expose read-only CLI/debug surface if useful

**Likely files:**

- `src/bid_euchre/ops/control_plane.py` or `attention_state.py`
- `src/bid_euchre/ops/monitor.py`
- `src/bid_euchre/ops/status.py`
- `src/bid_euchre/ops/dashboard.py`
- `scripts/internal/ops.py`
- `tests/unit/test_ops_control_plane.py` (new)

**Primary issues:**

- `#1571`
- `#1569`

### PR 3 -- Hook surfacing and local guardrails

**Goal:** Make unresolved urgent state mechanically visible and block unsafe
local actions where appropriate.

**Scope:**

- `UserPromptSubmit` surfacing for unresolved P0/P1
- `PreToolUse` guardrails for risky actions
- `Stop` / `TaskCompleted` completion checks where they reduce false "done"

**Likely files:**

- `.claude/settings.json`
- `.claude/settings.local.json` or repo-shared equivalent if promoted
- new hook scripts under `.claude/hooks/`
- `tests/unit/test_hook_dispatchers.py`
- `tests/unit/test_daemon_notify.py`

**Primary issues:**

- `#1608`
- `#1581`

### PR 4 -- Platform-8b runtime wiring and controller-backed remote path

**Goal:** Move Platform-8b from library-complete to runtime-complete.

**Scope:**

- wire inbound/outbound remote exchanges into the controller path
- ensure repo-owned audit is updated in all real runtime paths
- keep channel/plugin transport as adapter only

**Likely files:**

- `src/bid_euchre/ops/audit_trail.py`
- orchestrator-facing remote wrappers / helpers
- `scripts/internal/ops.py`
- `.claude/tmux/steward-session.sh`
- `tests/integration/test_audit_trail_integration.py`

**Primary issues:**

- `#1573`
- `#1521`

### PR 5 -- Comparative transport proving and `#1289` decision

**Goal:** Decide the long-term role of native inboxes with proving data.

**Scope:**

- run the proving matrix across bus, native bridge, hooks, and Channels
- write the decision note for `#1289`
- update the governing plan only after the matrix is complete

**Likely files:**

- this sub-plan closeout
- `plans/agent_ops/governing_plan.md`
- `plans/agent_ops/amendments.md`
- `plans/sessions/...` proving reports

**Primary issue:**

- `#1289`

## Test Strategy

### Unit tests

Controller:

- derive actionable items from monitor/task/review/lane inputs
- dedupe repeated items
- preserve stable IDs across cycles
- clear items when acked/resolved
- do not promote routine state to urgent incorrectly

Hooks:

- inject context only for unresolved P0/P1
- remain silent for empty/low-priority state
- fail safely on malformed projection state
- block guarded actions only when policy requires it

Transport boundary:

- bus records still round-trip correctly
- native inbox import remains idempotent
- runtime wiring updates audit + controller state consistently

### Smoke tests

Controller smoke:

- seed one urgent finding
- run the controller once
- verify `fleet_status.json` contains one actionable item

Hook smoke:

- seed unresolved urgent state
- submit a prompt in orchestrator
- verify injected context appears once
- clear it and verify surfacing stops

Remote audit smoke:

- send one inbound remote message
- verify inbound audit record and controller update
- send one outbound reply
- verify outbound audit record

### Full integration tests

- dispatch -> accept -> progress -> completion -> ack -> clear
- monitor finding -> controller projection -> hook surfacing -> ack -> clear
- unresolved urgent state survives restart/compaction and resurfaces correctly
- `/park` / shutdown removes cron jobs before clear
- remote inbound -> orchestrator handling -> outbound reply -> audit -> controller update

## Proving Runs

### Proving run 1 -- unread-alert replay

Recreate the original failure shape where `ops` detects a blocker and the
orchestrator does not manually poll raw inbox state.

**Pass when:**

- the urgent state is surfaced through the controller/hook path
- no manual raw-inbox scan is required to notice it

### Proving run 2 -- noise discrimination

Generate many info/warn findings plus one real blocker.

**Pass when:**

- only the blocker becomes interrupt-like
- routine findings remain visible but do not spam operator flow

### Proving run 3 -- persistence and dedupe

Run several monitor/controller cycles with one unresolved urgent item.

**Pass when:**

- the item is not lost across restart/compaction
- repeated cycles do not create alert floods
- ack/resolve clears the item cleanly

### Proving run 4 -- false-stall regression

Keep one lane actively working while earlier observations suggest trouble.

**Pass when:**

- current-state verification prevents false stall reports

### Proving run 5 -- real remote loop

Run one real remote exchange through the chosen channel path.

**Pass when:**

- inbound delivery works
- outbound reply works
- both directions are durably audited
- controller state reflects the exchange correctly

## Exit Criteria

This sub-plan is complete only when:

- one repo-owned controller surface exists and is the documented actionable
  truth for urgent/routine operator state
- one automated integration test proves `detect -> surface -> ack -> clear`
- unresolved urgent state can no longer be silently ignored at normal
  orchestrator interaction boundaries
- Platform-8b is runtime-wired, not library-only
- one real channel-backed remote loop is proven end to end
- `#1289` has a decision note backed by the transport comparison matrix

## Notes

- The intent is not to rewrite the entire platform around Channels or native
  inboxes.
- The intent is to make transport choice subordinate to control-plane truth.
