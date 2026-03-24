# Session Handoff — SP-4-07 Controller-First Control Plane

**Date:** 2026-03-24
**Status:** READY TO DISPATCH
**Primary owner:** orchestrator
**Parent sub-plan:** `plans/agent_ops/4_remote_channel/sub/2026-03-24_controller-first-control-plane-and-transport-evaluation.md`

---

## Executive Summary

The next platform step is not another inbox tweak or another transport layer.
It is a controller-first refactor.

The current Platform OS can store events and alerts, but it does not yet have
one repo-owned component that decides:

- what changed
- what is urgent
- what can wait
- what action is next
- when an item is acknowledged or cleared

That gap is why transport debates keep recurring:

- custom message bus
- native `SendMessage` / team inboxes
- Claude Channels
- hooks
- tmux nudges

This handoff makes `SP-4-07` the governing slice that settles control-plane
truth first, then evaluates delivery adapters against that truth.

## Key Decisions

### 1. Canonical truth stays repo-owned

Do not move workflow truth into Channels, native inboxes, or hook state.

Canonical state remains:

- task packets / task lifecycle state
- review verdict state
- monitor findings
- lane/session state
- repo-owned controller projection

### 2. The custom bus stays, but its role narrows

Keep the custom bus as:

- durable lane-to-lane transport
- audit trail
- sender attribution surface

Do not keep expanding it as the main urgent-alert brain.

### 3. Native `SendMessage` is not the answer by itself

Native inboxes are real and should remain available as an imported signal
source, but they are currently too thin to replace repo-owned workflow state.

### 4. Claude Channels are the preferred remote push adapter

Channels are the best candidate for remote and live-session delivery if they
prove reliable in this repo.

They should sit on top of repo-owned state, not replace it.

### 5. Hooks are enforcement surfaces, not the controller

Use hooks to surface or block at local boundaries.

Do not treat hooks as the only control loop or the primary source of state.

## Problem Frame

The main platform problem is reaction, not storage.

Evidence already in repo history and planning:

- monitor findings can be persisted without being acted on in time
- inbox volume obscures high-signal action items
- remote audit/runtime wiring is incomplete
- some lifecycle claims are still tested only indirectly or not at all

This means the platform currently over-invests in transports and under-invests
in a shared actionable-state controller.

## Primary Issues / Inputs

- `#1289` -- reassess custom vs native messaging transport
- `#1569` -- orchestrator unread inbox / alert surfacing gap
- `#1571` -- messaging and control-plane re-evaluation
- `#1573` -- Platform-8b runtime audit wiring gap
- `#1580` -- `/clear` / shutdown hygiene gap
- `#1581` -- pass/fail criteria requirement
- `#1596` -- inbox/bus correctness edge case
- `#1597` -- missing orchestration lifecycle integration test
- `#1608` -- hook-based attention surfacing
- `#1610` -- escalation flood risk
- `#1612` -- stale / false lane-status reporting

## Required Reading Before Implementation

- `plans/agent_ops/governing_plan.md`
- `plans/agent_ops/4_remote_channel/plan.md`
- `plans/agent_ops/4_remote_channel/checkpoints.md`
- `plans/agent_ops/4_remote_channel/sub/2026-03-24_controller-first-control-plane-and-transport-evaluation.md`
- `plans/agent_ops/4_remote_channel/sub/2026-03-24_reactive-control-loop-hardening.md`
- `plans/sessions/2026-03-23_operator-hardening.md`
- `src/bid_euchre/ops/message_bus.py`
- `src/bid_euchre/ops/monitor.py`
- `src/bid_euchre/ops/dashboard.py`
- `src/bid_euchre/ops/scheduler.py`
- `scripts/internal/ops.py`

## Implementation Sequence

### PR 1 — Stabilization gate and lifecycle baseline

**Goal:** remove correctness noise that would invalidate the controller slice.

**Scope:**

- fix known message-bus / monitor / stall-reporting correctness debt
- fix cleanup/shutdown hygiene that leaves background behavior behind
- add the missing orchestration lifecycle integration test
- keep planning docs honest about Platform-8b runtime state

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

### PR 2 — Controller projection

**Goal:** publish one canonical actionable-state surface.

**Scope:**

- add `src/bid_euchre/ops/control_plane.py` or equivalent
- reconcile monitor findings, task state, review state, lane state, and bus data
- write `.claude/runtime/fleet_status.json`
- optionally write `.claude/runtime/next_actions.json`
- add a read-only CLI view if it materially helps operations

**Minimum output fields:**

- `item_id`
- `severity`
- `category`
- `source`
- `first_seen_at`
- `last_seen_at`
- `state`
- related lane / task / PR identifiers
- recommended action

**Likely files:**

- `src/bid_euchre/ops/control_plane.py`
- `src/bid_euchre/ops/monitor.py`
- `src/bid_euchre/ops/status.py`
- `src/bid_euchre/ops/dashboard.py`
- `scripts/internal/ops.py`
- `tests/unit/test_ops_control_plane.py`

**Primary issues:**

- `#1571`
- `#1569`

### PR 3 — Hook surfacing and local guardrails

**Goal:** make unresolved urgent state mechanically visible.

**Scope:**

- `UserPromptSubmit` injection for unresolved P0/P1
- `PreToolUse` warnings or blocks for risky actions under unresolved P0
- `Stop` or `TaskCompleted` checks where they materially reduce false "done"

**Likely files:**

- `.claude/settings.json`
- `.claude/hooks/*`
- `tests/unit/test_hook_dispatchers.py`
- `tests/unit/test_daemon_notify.py`

**Primary issues:**

- `#1608`

### PR 4 — Platform-8b runtime wiring

**Goal:** finish real remote audit/runtime integration against the controller.

**Scope:**

- wire inbound remote messages into audit plus controller state
- wire outbound replies/reacts/edits into audit plus controller state
- ensure alert visibility is driven by the controller, not raw transport

**Likely files:**

- runtime paths that actually invoke `audit_inbound`, `audit_reply`,
  `audit_react`, `audit_edit`
- remote channel integration points
- controller/audit tests

**Primary issues:**

- `#1573`
- remote audit follow-up under Platform-8b

### PR 5 — Transport comparison and `#1289` decision

**Goal:** choose transport roles from proving data, not intuition.

**Compare:**

- custom bus
- native `SendMessage` / native inbox bridge
- Claude Channels
- hooks
- tmux nudges

**Decision output:**

- what remains canonical truth
- what remains durable transport
- what becomes preferred push adapter
- what stays fallback-only

## Test Plan

### Unit tests

1. Controller derivation
- reconcile multiple raw findings into one actionable item
- dedupe repeated alerts
- clear items on ack/resolve
- keep low-priority routine state out of urgent surfacing

2. Hook behavior
- inject urgent context only when unresolved P0/P1 exists
- stay silent for empty or low-priority state
- fail safely on malformed projection files
- block guarded actions only when policy requires it

3. Bus/controller boundary
- bus records still round-trip correctly
- controller projection derives from existing repo-owned state
- ack/resolve transitions clear surfaced urgent items

4. Freshness / stall correctness
- stale observations do not override current lane state
- active work is not surfaced as stalled

### Smoke tests

1. Controller smoke
- synthesize one urgent finding
- run controller once
- verify `fleet_status.json` contains one actionable item

2. Hook smoke
- seed controller output
- submit prompt in orchestrator session
- verify urgent context appears exactly once

3. Guard smoke
- leave unresolved P0 present
- attempt guarded dispatch or merge path
- verify warn/block behavior matches policy

4. Native import smoke
- seed a native inbox entry
- verify bridge import works and dedupes on rerun

5. Channel smoke
- send one real channel message
- verify orchestrator receives it
- verify inbound/outbound audit records are written

### Full integration tests

1. Lifecycle
- dispatch -> accept -> progress -> completion -> ack -> clear

2. Alert loop
- monitor finding -> controller projection -> hook surfacing -> ack -> clear

3. Restart persistence
- unresolved urgent state survives restart/compaction
- next boundary still surfaces it

4. Remote loop
- inbound remote message -> orchestrator handling -> outbound reply -> audit
  trail -> controller update

5. Shutdown hygiene
- `/park` or equivalent cleanup removes background cron/process state before
  clear/restart

## Required Proving Runs

### 1. Unread-alert replay

Recreate the original blind-spot shape.

**Pass if:**

- `ops` detects a real blocker
- orchestrator does not manually inspect raw inboxes
- the blocker is still surfaced mechanically within one normal interaction
  boundary

### 2. Noise discrimination run

Generate many routine findings and one real blocker.

**Pass if:**

- only the blocker becomes interrupt-like
- routine status stays available without prompt spam

### 3. Persistence / dedupe run

Keep one urgent item open across multiple cycles and a restart.

**Pass if:**

- no duplicate flood
- no lost urgent item
- ack/resolve clears it cleanly

### 4. False-stall regression run

Keep one lane actively working while older observations suggest a stall.

**Pass if:**

- current-state verification prevents false stall surfacing

### 5. Real remote loop proving run

Use the actual preferred remote adapter candidate.

**Pass if:**

- inbound arrives
- reply succeeds
- audit records both directions
- controller reflects the interaction correctly

## Acceptance Gates

Do not close `SP-4-07` or claim transport convergence unless all are true:

1. One automated integration test covers `detect -> surface -> ack -> clear`.
2. One controller-backed actionable-state file exists and is stable.
3. Unresolved urgent state cannot be silently ignored at normal orchestrator
   interaction boundaries.
4. Resolved urgent state stops surfacing immediately.
5. Platform-8b runtime audit wiring is real, not library-only.
6. One real Channels-backed remote loop is proven if Channels remain the
   preferred remote adapter.
7. The `#1289` transport decision is written as an explicit comparison, not an
   assumption.

## Non-Goals

Do not broaden this slice into:

- replacing task packets or review verdicts
- making author lanes directly remote-addressable
- replacing the custom bus outright
- moving workflow truth into native Claude inboxes
- final Discord rollout

## Closeout Requirements

When this sequence lands, leave a closeout note with:

- PR numbers
- issues closed or narrowed
- final controller file/location
- whether Channels proved reliable enough to remain preferred
- whether native inbox import stays enabled
- any residual follow-up issue needed after `#1289`
