# Phase 3 — Supervision and Scaling

**Governing plan:** `plans/agent_ops/governing_plan.md`
**Phase:** `3_supervision_and_scaling`
**Status:** IN_PROGRESS
**Last updated:** 2026-03-22 by author-b (Phase 3 plan creation)

---

## Scope

Phase 3 covers `Platform-6` and `Platform-7`: supervisor routines with delta
summaries and background worker-pool management with bounded dynamic author
scaling. These two slices form Batch D.

## Prerequisites

Phase 2 (`2_visible_operating_model`) is COMPLETE:
- Platform-4: Dashboard-first steward layout (PR #1231)
- Platform-5: Canonical prompts and skills (PR #1234)
- Batch C pass gate: PASSED (see `batch_c_reassessment.md`)

## Slices

| Slice | Goal | Status | Batch | Depends On |
|-------|------|--------|-------|------------|
| `Platform-6` | `ops` supervisor routines and delta summaries | COMPLETE (PR #1242) | D | Platform-3, Platform-4 |
| `Platform-7` | Background worker-pool management and bounded dynamic author scaling | PENDING | D | Platform-1, Platform-2, Platform-3 |

## Batch D Pass Gate

Before treating Phase 4 as ready, verify Batch D (Platform-6 + Platform-7):

- [ ] `ops` delta summaries are reliable enough to drive intervention decisions
- [ ] Worker reuse/open-on-demand behavior works in a live multi-lane proving run
- [ ] Stale/blocked/degraded lane handling is auditable and does not require pane
  archaeology
- [ ] In the current tmux-first steward layout, a dispatched task can land in the
  target live author session through a repo-owned delivery adapter without
  manual pane inspection

## Platform-6 Summary (Complete)

**PR:** #1242 ("ops: add supervisor routines and delta summaries (Platform-6)")
**Merged:** 2026-03-22
**Sub-plan:** SP-3-01

Shipped:
- `SupervisorSnapshot` point-in-time lane health snapshots
- `DeltaSummary` computation between consecutive snapshots
- Per-lane `LaneHealthAssessment` from status + watchdog findings
- Bounded `RecoveryRecommendation` proposals (retry, reroute, escalate, respawn, unblock)
- Snapshot persistence with atomic writes and bounded retention
- `run_supervisor_cycle()` main entry point for single pass
- Text and JSON formatters for CLI surface
- CLI `supervisor` subcommand with `--save` and `--diff` flags
- Comprehensive unit test suite

## Platform-7 — Worker Pool Manager

From governing plan:
- Idle worker reuse
- Bounded dynamic author creation
- Worker parking/retirement
- Worker-pool dashboard state
- Open/resume author panes on delegation and return them to background/hidden
  state when idle
- BD-004 closure path for this phase:
  - use a thin tmux-backed delivery adapter on top of durable task/message state
  - dispatch should wake the target lane if needed, then invoke a packet-specific
    repo-owned consumer entrypoint in the live pane
  - do not introduce channel-sidecar or `cmux` delivery as the required Phase 3
    fix; those are later adapter upgrades
- Note: if scaling and retirement logic do not fit cleanly, this slice may
  land as two PRs under the same parent label
- Done when:
  - `orchestrator` can reuse idle authors before creating new workers
  - A delegated task can cause the needed author lane to open or resume on
    demand without requiring all author panes to be pre-opened
  - Dynamic worker creation and retirement obey repo-owned concurrency and
    cleanup limits

## Later Delivery Upgrades

After the Phase 3 gate is closed with the tmux-backed v1 delivery adapter:

- `v2` (later, Platform-8-capable): optional Claude channel sidecar that watches
  repo-owned task/inbox state and pushes events into the running session
- `v3` (later, optional): `cmux` transport upgrade if workspace/surface refs are
  populated and stable enough to replace raw tmux targeting cleanly

## Key Constraints

- Core-vs-adapter separation must be preserved
- No heavyweight external orchestrator dependencies
- Repo-local, explicit, schema-driven, easy to audit
- Each slice produces: code/docs changes, automated tests, smoke checks,
  unhappy-path checks, rollback path, known gaps list

## Sub-Plans

Active sub-plans are tracked in `plans/agent_ops/sub_plan_registry.md`.

| ID | Slice | Status |
|----|-------|--------|
| SP-3-01 | Platform-6 | completed |
| SP-3-02 | Platform-7 | pending |

## Step Sequence

See `checkpoints.md` for current step progress. Phase 3 follows the standard
step template from the governing plan (SS4.2): scope lock -> implementation ->
verification -> handoff, repeated per slice.
