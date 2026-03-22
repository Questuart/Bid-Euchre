# Platform-7 Implementation Handoff -- Worker Pool Manager

**Sub-plan:** `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_platform7-worker-pool-manager.md`
**Registry ID:** SP-3-02
**Date:** 2026-03-22
**Target lane:** author-b (or any available author lane)

---

## Lane Direction

You are implementing Platform-7 (Worker Pool Manager) for the Agentic
Orchestration Platform. This is the second and final slice of Phase 3
(Batch D: Supervision and Scaling).

Platform-6 (supervisor routines, PR #1242) is already merged. It provides
the health assessment and recovery recommendation infrastructure that the
worker pool consumes.

## Goal

Deliver `src/bid_euchre/ops/worker_pool.py` and a `workers` CLI subcommand
so the orchestrator can:
1. Reuse idle author lanes before creating new workers.
2. Open or resume author panes on demand when delegating work.
3. Park idle and retire parked lanes within repo-owned concurrency limits.

## Dependencies

- Platform-6 merged (PR #1242) -- supervisor routines
- Platform-4 merged (PR #1231) -- dashboard visibility management
- Platform-2 merged (PR #1221) -- task packet lifecycle

All dependencies are satisfied. No blockers.

## Context to Read Before Planning

Read these files to ground your implementation plan:

| Priority | File | What to extract |
|----------|------|-----------------|
| 1 | `plans/agent_ops/3_supervision_and_scaling/sub/2026-03-22_platform7-worker-pool-manager.md` | Full sub-plan with design, API signatures, integration points |
| 2 | `src/bid_euchre/ops/supervisor.py` | `LaneHealthAssessment`, `take_snapshot()` -- you consume these |
| 3 | `src/bid_euchre/ops/dashboard.py` | `set_lane_visibility()`, `effective_visibility()` -- you call these |
| 4 | `src/bid_euchre/ops/task_queue.py` | `KNOWN_AUTHOR_LANES`, `transition_status()`, `list_packets()` -- you integrate with these |
| 5 | `src/bid_euchre/ops/status.py` | `LaneStatus`, `aggregate_status()` -- you read lane state from these |
| 6 | `.claude/tmux/steward-session.sh` | Current tmux bootstrap -- understand the session/window/pane model |
| 7 | `scripts/internal/ops.py` | CLI structure -- add `workers` subcommand following the same pattern as `supervisor` |
| 8 | `plans/agent_ops/amendments.md` | A3 (frontmatter) and A4 (agent teams boundary) -- design constraints |

## Scope Lock

### Create

| File | Purpose |
|------|---------|
| `src/bid_euchre/ops/worker_pool.py` | Worker pool lifecycle module |
| `tests/unit/test_ops_worker_pool.py` | Unit tests |

### Modify

| File | Change |
|------|--------|
| `src/bid_euchre/ops/__init__.py` | Add `worker_pool` to module docstring |
| `scripts/internal/ops.py` | Add `workers` subcommand and argument parser |

### Do NOT Touch

| File | Why |
|------|-----|
| `src/bid_euchre/ops/status.py` | No schema changes; read-only consumer |
| `src/bid_euchre/ops/supervisor.py` | Read-only consumer |
| `src/bid_euchre/ops/dashboard.py` | Already supports visibility filtering |
| `src/bid_euchre/ops/task_queue.py` | Existing lifecycle sufficient; import KNOWN_AUTHOR_LANES |
| `.claude/tmux/steward-session.sh` | Bootstrap is unchanged |

## Design Lock

These design decisions are fixed (from the sub-plan):

1. **tmux via subprocess**, not libtmux. Match `steward-session.sh` pattern.
   libtmux deferred to Platform-10.
2. **No new git worktrees**. Operate within existing persistent worktrees.
3. **No agent teams as infrastructure** (Amendment A4). All state in
   repo-owned JSON files.
4. **Constants**: `MAX_ACTIVE_AUTHORS = 5`, `IDLE_PARK_MINUTES = 15`,
   `PARKED_RETIRE_MINUTES = 60`, `DEFAULT_TMUX_SESSION = "steward"`.
5. **Parking** = set visibility to "hidden", leave tmux pane running.
6. **Retirement** = set visibility to "hidden", terminate tmux pane process.
   Never remove worktrees.
7. **Worker selection priority**: preferred lane > idle > parked > retired.
8. **Orchestrator dispatch flow**: create packet -> approve -> `dispatch_to_worker()` -> wake if needed -> transition to "dispatched".

## Open Design Questions (decide during implementation)

1. Should `retire_worker` SIGTERM the pane or just hide it?
2. Should `PoolSnapshot` be persisted to disk or always computed on demand?
3. How does a newly woken claude session discover its dispatched task?
4. Should this ship as one PR or two (wake/dispatch vs. park/retire)?

## Execution Order

### Step 1: Create `worker_pool.py` core dataclasses and constants
- `WorkerState`, `PoolSnapshot`, `PoolAction`
- Constants: `MAX_ACTIVE_AUTHORS`, `IDLE_PARK_MINUTES`, etc.
- Import `KNOWN_AUTHOR_LANES` from `task_queue`

### Step 2: Implement `take_pool_snapshot()`
- Read lane registry via `aggregate_status()`
- Read supervisor health via `take_snapshot()`
- Probe tmux panes via `_probe_tmux_pane()`
- Filter to `MANAGED_LANES` only

### Step 3: Implement `select_worker()` and `_probe_tmux_pane()`
- Worker selection logic with priority ordering
- tmux probing via `subprocess.run(["tmux", "list-windows", ...])`

### Step 4: Implement lifecycle actions
- `wake_worker()` -- create tmux window, update registry
- `park_worker()` -- set visibility hidden
- `retire_worker()` -- terminate pane, set visibility hidden
- `dispatch_to_worker()` -- end-to-end orchestrator entry point

### Step 5: Implement `run_pool_maintenance()`
- Scan for idle/parked lanes exceeding thresholds
- Apply park/retire transitions
- Support `dry_run` mode

### Step 6: Write unit tests
- Mock `aggregate_status`, `take_snapshot`, `subprocess.run`
- Cover: snapshot building, worker selection, lifecycle actions,
  maintenance, error handling, concurrency limits

### Step 7: Add CLI subcommand
- Add `workers` parser to `scripts/internal/ops.py`
- Sub-actions: (default show), wake, park, retire, dispatch, maintain
- Follow existing CLI patterns (e.g., `cmd_supervisor`)

### Step 8: Update `__init__.py` and validate
- Add `worker_pool` to ops module docstring
- Run `uv run python -m pytest tests/unit/test_ops_worker_pool.py -v`
- Run `uv run python -m pytest tests/unit/test_ops_cli.py -v -k workers`
- Run `make check-quiet`

## Validation Commands

```bash
# Tier 1 -- during implementation
uv run python -m pytest tests/unit/test_ops_worker_pool.py -v
uv run python -m pytest tests/unit/test_ops_cli.py -v -k workers

# Tier 2 -- before PR
make check-quiet

# Manual smoke
uv run python scripts/internal/ops.py workers --json
uv run python scripts/internal/ops.py workers maintain --dry-run --json
```

## Out of Scope

- Remote channels (Platform-8)
- Idle attention (Platform-9)
- libtmux (Platform-10)
- Skill learning (Platform-11)
- Agent teams as coordination infrastructure (Amendment A4)
- New git worktree creation
- Automatic scheduler wiring (follow-up if needed)
- SendMessage-based resume

## Exit Criteria

- [ ] `src/bid_euchre/ops/worker_pool.py` exists with all functions from sub-plan
- [ ] `tests/unit/test_ops_worker_pool.py` covers snapshot, selection, lifecycle, maintenance
- [ ] `ops.py workers` subcommand works (text and JSON modes)
- [ ] `make check-quiet` passes
- [ ] PR opened with exact repro command, scope lock table, worktree proof
- [ ] Dashboard still renders correctly after visibility changes
- [ ] No regressions in existing supervisor/status/dashboard tests

## Execution Protocol Reminder

Before writing code:
1. Read the sub-plan and all referenced source files.
2. Draft a concrete execution plan.
3. Spawn a reviewer agent to review the plan.
4. Create a TUI task list for implementation and validation.
5. Assess parallelism (Steps 1-5 are sequential; Step 6 can partially
   overlap with Steps 4-5; Steps 7-8 are sequential after Step 6).
6. Execute end to end: implement, test, commit, open PR with validation
   evidence.
