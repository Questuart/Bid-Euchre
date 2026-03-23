<!-- review-tier: medium -->
# Phase 3 Closeout And Transition Entry

**ID:** SP-3-04
**Date:** 2026-03-22
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 3 (`3_supervision_and_scaling`), Step 5
**Status:** completed
**Owner:** author-scratch

---

## Goal

Durably close Phase 3 now that Batch D and BD-004 are resolved, reconcile the
stale planning state, and hand off the next governed action as the
dual-domain steward layout transition package that will run before any
Platform-8 implementation work starts.

## Why This Exists

Phase 3 runtime work is effectively done, but the durable planning state still
lags shipped reality:

- `checkpoints.md` still says Step 5 is blocked on BD-004
- `plan.md` still shows `Platform-7` as pending
- `sub_plan_registry.md` does not yet reflect all Phase 3 sub-plans

This sub-plan closes that gap and makes the next step explicit so the browser-
game and platform tracks can proceed from durable repo state rather than chat.

## Inputs

- `plans/agent_ops/governing_plan.md`
- `plans/agent_ops/amendments.md`
- `plans/agent_ops/sub_plan_registry.md`
- `plans/agent_ops/3_supervision_and_scaling/plan.md`
- `plans/agent_ops/3_supervision_and_scaling/checkpoints.md`
- `plans/agent_ops/3_supervision_and_scaling/qa_log.md`
- `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_platform7-worker-pool-manager.md`
- `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_bd004-v1-pane-delivery.md`
- GitHub issue `#1259` (BD-004) -- CLOSED
- PR `#1260` (Batch D docs update) -- MERGED
- PR `#1261` (BD-001/BD-002/BD-003 fix line) -- MERGED

## Done When

1. Phase 3 checkpoints no longer show BD-004 as an active blocker.
2. Phase 3 plan reflects `Platform-7` and Batch D as complete.
3. The sub-plan registry reflects the Phase 3 sub-plan set accurately enough
   that a new session can resume from files alone.
4. The governing plan and amendments record the post-Phase-3 dual-domain
   layout transition as the next governed action before Platform-8.
5. The next operational step is unambiguous:
   - first the layout transition package
   - then Platform-8 scope lock

## Work Items

### Step 1 -- Reconcile Phase 3 durable state

Update:
- `plans/agent_ops/3_supervision_and_scaling/checkpoints.md`
- `plans/agent_ops/3_supervision_and_scaling/plan.md`
- `plans/agent_ops/sub_plan_registry.md`

Required corrections:
- remove the lingering BD-004 block from Step 5
- mark Step 5 `COMPLETE` once the closeout PR lands
- mark `Platform-7` complete in `plan.md`
- mark the Batch D pass-gate checklist complete
- reconcile `SP-3-02`, `SP-3-03`, and this closeout plan entry

### Step 2 -- Record the transition package as the next governed action

Update:
- `plans/agent_ops/governing_plan.md`
- `plans/agent_ops/amendments.md`

Required note:
- the dual-domain steward layout refactor is a bounded transition package
  between Phase 3 and Platform-8
- it does not renumber the platform roadmap
- it exists to support parallel platform + browser-game work while preserving
  centralized control

### Step 3 -- Hand off the next action cleanly

The Phase 3 closeout PR should point directly at:
- `SP-3-05` (dual-domain steward layout transition)

It should also say explicitly:
- Platform-8 planning has not started yet
- browser-game work may proceed after the transition package is in place
- residual non-blocking debt stays as debt, not as a hidden Phase 3 blocker

## Scope Lock

- `plans/agent_ops/governing_plan.md`
- `plans/agent_ops/amendments.md`
- `plans/agent_ops/sub_plan_registry.md`
- `plans/agent_ops/3_supervision_and_scaling/plan.md`
- `plans/agent_ops/3_supervision_and_scaling/checkpoints.md`
- `plans/agent_ops/3_supervision_and_scaling/qa_log.md` if cross-references need cleanup

## Validation

```bash
rg -n "BD-004|Step 5|Platform-7|SP-3-02|SP-3-03|SP-3-04|SP-3-05" \
  plans/agent_ops/3_supervision_and_scaling/plan.md \
  plans/agent_ops/3_supervision_and_scaling/checkpoints.md \
  plans/agent_ops/sub_plan_registry.md \
  plans/agent_ops/governing_plan.md \
  plans/agent_ops/amendments.md

make check-quiet
```

## Acceptance Criteria

- [ ] `checkpoints.md` no longer says Phase 3 exit is blocked on BD-004
- [ ] `plan.md` no longer shows `Platform-7` as pending
- [ ] `sub_plan_registry.md` includes the relevant Phase 3 sub-plans
- [ ] the governing plan records the layout transition as the next step before
      Platform-8
- [ ] a fresh operator can determine the next action from repo state only

## Out Of Scope

- Implementing the dual-domain layout transition itself
- Starting Platform-8 scope lock
- Starting browser-game feature work
- Reopening Batch D proving

## Risks / Notes

- The main failure mode is leaving the repo in a half-closed state where
  runtime reality says Phase 3 is done but the plan says it is not. This
  sub-plan exists specifically to avoid that drift.
