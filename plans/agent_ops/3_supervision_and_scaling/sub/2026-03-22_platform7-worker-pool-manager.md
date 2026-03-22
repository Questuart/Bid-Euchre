<!-- review-tier: medium -->
# Platform-7 -- Worker Pool Manager

**ID:** SP-3-02
**Date:** 2026-03-22
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 3 (`3_supervision_and_scaling`), `Platform-7`
**Status:** proposed
**Owner:** (unassigned)

---

## Goal

Deliver repo-owned worker-pool lifecycle management so that the orchestrator
can reuse idle author lanes, open/resume author panes on demand when
delegating work, and park or retire lanes when idle -- all without requiring
author panes to be pre-opened or manually managed.

Done when (from governing plan):
1. Orchestrator can reuse idle authors before creating new workers.
2. A delegated task can cause the needed author lane to open or resume on
   demand without requiring all author panes to be pre-opened.
3. Dynamic worker creation and retirement obey repo-owned concurrency and
   cleanup limits.

## Inputs

- `plans/agent_ops/governing_plan.md` -- Platform-7 definition (lines 1159-1175)
- `plans/agent_ops/amendments.md` -- A3 (frontmatter hardening), A4 (agent teams boundary)
- `src/bid_euchre/ops/status.py` -- `LaneStatus`, `aggregate_status()`, `LaneStatus.state`, `LaneStatus.visibility`, `LaneStatus.session_handle`
- `src/bid_euchre/ops/supervisor.py` -- `LaneHealthAssessment`, `RecoveryRecommendation`, `take_snapshot()`, `run_supervisor_cycle()`
- `src/bid_euchre/ops/dashboard.py` -- `effective_visibility()`, `set_lane_visibility()`, `build_dashboard_view()`
- `src/bid_euchre/ops/task_queue.py` -- `TaskPacket`, `KNOWN_AUTHOR_LANES`, `list_packets()`, `transition_status()`
- `src/bid_euchre/ops/worktrees.py` -- `list_worktrees_registry()`
- `.claude/tmux/steward-session.sh` -- current tmux bootstrap with `write_lane_metadata()`, `ensure_worktree()`
- `scripts/internal/ops.py` -- CLI entrypoint (new `workers` subcommand)

## Assumptions

- Platform-6 (supervisor routines) is merged and stable (PR #1242).
- The tmux session is the steward session created by `steward-session.sh`.
- The `tmux` binary is available on the host.
- All author lanes have persistent worktrees that already exist (created by
  `steward-session.sh` or `start-role-worktree.sh`); this module does not
  create new git worktrees.
- `CLAUDE_BIN` is discoverable via `command -v claude` (same as
  `steward-session.sh`).
- Amendment A4 holds: agent teams are a convenience execution layer, not a
  coordination truth model. All durable state lives in repo-owned artifacts
  (registry, task queue, dashboard, bus).

## Dependencies

- `SP-3-01` (Platform-6 supervisor routines) -- COMPLETE. Provides health
  assessments and recovery recommendations consumed by the worker pool.
- Platform-4 dashboard -- COMPLETE (PR #1231). Provides visibility management
  consumed by state transitions.

## Design

### New module: `src/bid_euchre/ops/worker_pool.py`

#### Constants

```python
# Maximum number of simultaneously active (non-idle) author lanes.
# Matches the 5 persistent author worktrees in steward-session.sh.
MAX_ACTIVE_AUTHORS: int = 5

# Lane IDs that the worker pool manages (same as KNOWN_AUTHOR_LANES
# in task_queue.py but imported to avoid duplication).
MANAGED_LANES: frozenset[str]  # = task_queue.KNOWN_AUTHOR_LANES

# Idle threshold (minutes) before a lane is eligible for parking.
IDLE_PARK_MINUTES: int = 15

# Parked threshold (minutes) before a parked lane is eligible for retirement.
PARKED_RETIRE_MINUTES: int = 60

# Default tmux session name (matches steward-session.sh default).
DEFAULT_TMUX_SESSION: str = "steward"
```

#### Dataclasses

```python
@dataclass
class WorkerState:
    """Snapshot of one author lane's pool state."""
    lane_id: str
    pool_status: str   # "active", "idle", "parked", "retired"
    health: str        # from supervisor: "healthy", "idle", "degraded", "critical"
    current_task_id: str | None
    last_activity: str | None  # ISO 8601
    visibility: str    # "foreground", "background", "hidden"
    tmux_alive: bool   # whether the tmux pane/window exists and has a process
    session_handle: str | None

@dataclass
class PoolSnapshot:
    """Point-in-time summary of the worker pool."""
    timestamp: str
    workers: list[WorkerState]
    active_count: int
    idle_count: int
    parked_count: int
    retired_count: int
    available_capacity: int  # MAX_ACTIVE_AUTHORS - active_count

@dataclass
class PoolAction:
    """A single lifecycle action proposed or executed by the pool manager."""
    action: str        # "wake", "park", "retire", "reuse"
    lane_id: str
    reason: str
    executed: bool = False
    error: str | None = None
```

#### Core functions

```python
def take_pool_snapshot(
    runtime_dir: Path | None = None,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    now: datetime | None = None,
) -> PoolSnapshot:
    """Build a point-in-time worker pool snapshot.

    Reads from:
    - worktree registry (via status.aggregate_status)
    - supervisor snapshot (via supervisor.take_snapshot)
    - tmux session state (via _probe_tmux_pane)

    Filters to MANAGED_LANES only.
    """

def select_worker(
    pool: PoolSnapshot,
    *,
    preferred_lane: str | None = None,
) -> str | None:
    """Choose the best lane for new work.

    Priority order:
    1. preferred_lane (if idle or parked and healthy)
    2. idle lanes (already running, no active task)
    3. parked lanes (need waking, but worktree exists)
    4. retired lanes (need full resume)
    5. None if at MAX_ACTIVE_AUTHORS

    Returns lane_id or None if no capacity.
    """

def wake_worker(
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Open or resume an author pane for the given lane.

    Steps:
    1. Check if tmux window/pane already exists for lane_id.
       - If alive: set visibility to "foreground", return.
    2. If window does not exist: create a new tmux window in the
       steward session, pointed at the lane's worktree, running
       claude with the lane's agent profile.
    3. Update registry: visibility -> "foreground", last_active -> now.
    4. Return PoolAction with executed=True.

    Implementation uses subprocess tmux commands (not libtmux) for
    the first version. libtmux adoption is deferred to Platform-10
    portability layer per governing plan tooling recommendations.
    """

def park_worker(
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Move an idle author lane to parked state.

    Steps:
    1. Verify lane is idle (no active task, not dispatched).
    2. Set visibility to "hidden" in worktree registry.
    3. Do NOT kill the tmux pane -- just hide from dashboard.
       The claude process may still be running but idle.
    4. Return PoolAction.
    """

def retire_worker(
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Fully retire a parked lane.

    Steps:
    1. Verify lane is parked and has been parked > PARKED_RETIRE_MINUTES.
    2. Set visibility to "hidden" in worktree registry.
    3. Optionally send SIGTERM to the tmux pane's process (if alive).
    4. Do NOT remove the worktree (persistent worktrees are never removed
       per .claude/rules/75_worktree_protection.md).
    5. Return PoolAction.
    """

def dispatch_to_worker(
    packet_id: str,
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Complete lifecycle: select/wake worker, assign task packet, update state.

    Steps:
    1. Load task packet, verify it is in "approved" status.
    2. Take pool snapshot, verify lane_id has capacity.
    3. If lane is parked/retired: wake_worker() first.
    4. Transition packet to "dispatched" with owner = lane_id.
    5. Set lane visibility to "foreground".
    6. Return PoolAction.

    This is the high-level entry point the orchestrator calls.
    """

def run_pool_maintenance(
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[PoolAction]:
    """Periodic maintenance: park idle workers, retire parked ones.

    Called by the ops scheduler (or manually via CLI).
    Scans all MANAGED_LANES and applies lifecycle transitions:
    - idle > IDLE_PARK_MINUTES -> park
    - parked > PARKED_RETIRE_MINUTES -> retire

    Returns list of proposed (dry_run=True) or executed actions.
    """
```

#### Internal helpers

```python
def _probe_tmux_pane(
    lane_id: str,
    tmux_session: str,
) -> bool:
    """Check if a tmux window/pane for lane_id exists and has a running process.

    Uses: subprocess.run(["tmux", "list-windows", "-t", session, "-F", "#{window_name}"])
    Matches window name to lane_id.
    Returns True if found.
    """

def _create_tmux_window(
    lane_id: str,
    worktree_path: str,
    tmux_session: str,
) -> bool:
    """Create a new tmux window for the lane.

    Uses: subprocess.run(["tmux", "new-window", "-t", session, "-n", lane_id,
                          "-c", worktree_path, claude_bin, "--name", lane_id,
                          "--agent", agent_name])
    Returns True on success.

    The claude_bin path is discovered the same way steward-session.sh does it:
    shutil.which("claude").
    The agent name is derived from lane_id: f"steward-{lane_id}".
    """

def _resolve_agent_name(lane_id: str) -> str:
    """Map lane_id to the canonical agent profile name.

    "author-a" -> "steward-author-a"
    "author-scratch" -> "steward-author-scratch"
    etc.
    """

def _resolve_worktree_path(
    lane_id: str,
    runtime_dir: Path | None = None,
) -> str | None:
    """Look up the worktree path for a lane from the registry."""
```

### CLI addition: `scripts/internal/ops.py` -- `workers` subcommand

```
uv run python scripts/internal/ops.py workers [--json]
uv run python scripts/internal/ops.py workers wake LANE_ID [--json]
uv run python scripts/internal/ops.py workers park LANE_ID [--json]
uv run python scripts/internal/ops.py workers retire LANE_ID [--json]
uv run python scripts/internal/ops.py workers dispatch PACKET_ID LANE_ID [--json]
uv run python scripts/internal/ops.py workers maintain [--dry-run] [--json]
```

- `workers` (no sub-action): show pool snapshot (text or JSON)
- `workers wake`: open/resume an author pane
- `workers park`: park an idle lane
- `workers retire`: retire a parked lane
- `workers dispatch`: assign a task packet to a lane (wake if needed)
- `workers maintain`: run periodic maintenance (park idle, retire parked)

### Integration points

| Consumer | Reads From | Writes To |
|----------|-----------|----------|
| `worker_pool.take_pool_snapshot()` | `status.aggregate_status()`, `supervisor.take_snapshot()` | (read-only) |
| `worker_pool.select_worker()` | `PoolSnapshot` | (read-only) |
| `worker_pool.wake_worker()` | worktree registry | registry `visibility`, `last_active`; tmux session |
| `worker_pool.park_worker()` | worktree registry, task_queue | registry `visibility` |
| `worker_pool.retire_worker()` | worktree registry | registry `visibility`; tmux pane (SIGTERM) |
| `worker_pool.dispatch_to_worker()` | task_queue, pool snapshot | task_queue status transition, registry `visibility` |
| `worker_pool.run_pool_maintenance()` | pool snapshot | park/retire actions |
| dashboard | `effective_visibility()` | (read-only -- already works) |

### How the orchestrator signals "I need author-a to wake up"

The orchestrator does NOT send a tmux command directly. The flow is:

1. Orchestrator creates/approves a task packet with `owner = "author-a"`.
2. Orchestrator calls `dispatch_to_worker(packet_id, "author-a")`.
3. `dispatch_to_worker` calls `wake_worker("author-a")` if the lane is
   parked/retired.
4. `wake_worker` creates the tmux window, updates the registry.
5. The newly opened claude session reads the task packet from the durable
   queue on startup (via its agent profile prompt, which instructs it to
   check for pending dispatched packets).

Alternative: if the orchestrator wants automatic worker selection (not a
specific lane), it calls `select_worker(pool)` first, then
`dispatch_to_worker(packet_id, selected_lane)`.

### How parking/retirement works

**Parking** = the lane is marked `visibility: "hidden"` in the registry but
the tmux pane may still exist. The claude process might be running but has
no active task. Dashboard hides it. The lane can be woken instantly by
creating or selecting the tmux window.

**Retirement** = same as parking but the tmux pane's process is terminated
(SIGTERM). The worktree persists (never removed per worktree protection
rules). Waking a retired lane requires creating a new tmux window and
starting a new claude session.

Thresholds:
- Idle for > `IDLE_PARK_MINUTES` (15 min) with no active task -> park
- Parked for > `PARKED_RETIRE_MINUTES` (60 min) -> retire

### Concurrency limits

- `MAX_ACTIVE_AUTHORS = 5` (matches the 5 persistent author worktrees)
- `select_worker()` returns `None` when active count >= MAX_ACTIVE_AUTHORS
- The limit is repo-owned (a constant in `worker_pool.py`), not derived
  from tmux or Claude Code agent teams

### libtmux vs shell tmux

The governing plan recommends libtmux for "tmux-aware introspection,
session checks, and safer lane/session handling." However, the first
version uses shell `subprocess.run(["tmux", ...])` commands for simplicity
and fewer dependencies. This matches how `steward-session.sh` already
works. Migration to libtmux is deferred to Platform-10 (portability layer)
when the adapter surface is defined.

### Agent teams boundary (Amendment A4)

This module does NOT use `SendMessage` or Claude Code agent teams for
coordination. All state flows through:
- Worktree registry JSON files (visibility, last_active)
- Task queue JSON files (packet status, owner)
- tmux commands for pane lifecycle only

If agent teams are enabled experimentally, they provide display convenience
only. The worker pool module remains functional without them.

## Scope Lock

### Files to create

| File | Purpose |
|------|---------|
| `src/bid_euchre/ops/worker_pool.py` | Worker pool lifecycle module |
| `tests/unit/test_ops_worker_pool.py` | Unit tests |

### Files to modify

| File | Change |
|------|--------|
| `src/bid_euchre/ops/__init__.py` | Add `worker_pool` to module docstring |
| `scripts/internal/ops.py` | Add `workers` subcommand and `cmd_workers()` |
| `plans/agent_ops/sub_plan_registry.md` | Register SP-3-02 |
| `plans/agent_ops/3_supervision_and_scaling/checkpoints.md` | Update Step 2 status |

### Files NOT modified (out of scope)

| File | Why |
|------|-----|
| `src/bid_euchre/ops/status.py` | No schema changes needed; existing `LaneStatus` fields are sufficient |
| `src/bid_euchre/ops/supervisor.py` | Read-only consumer; no changes needed |
| `src/bid_euchre/ops/dashboard.py` | Already supports visibility-based filtering; no changes needed |
| `src/bid_euchre/ops/task_queue.py` | Existing lifecycle transitions are sufficient; KNOWN_AUTHOR_LANES is imported |
| `.claude/tmux/steward-session.sh` | Bootstrap script is unchanged; worker_pool operates within the created session |

## Out of Scope

These items explicitly belong to later platform slices and MUST NOT leak
into Platform-7:

- **Remote operator channel** (Platform-8) -- no Telegram/Discord integration
- **Idle attention flow** (Platform-9) -- no idle-attention alerts or
  acknowledgement handling
- **libtmux migration** (Platform-10) -- use subprocess tmux commands
- **Skill learning loop** (Platform-11) -- no skill suggestion/promotion
- **Cross-model review** (Platform-12) -- no multi-model execution
- **Agent teams as infrastructure** (Amendment A4) -- agent teams are
  convenience only, not coordination truth
- **Dynamic worktree creation** -- new git worktrees are NOT created by
  this module; it operates within existing persistent worktrees
- **Automatic periodic scheduling** -- `run_pool_maintenance()` is a
  callable function exposed via CLI; wiring it into the ops scheduler
  daemon is a follow-up if needed
- **SendMessage-based resume** -- while `SendMessage` can resume stopped
  subagents, the first version uses tmux window creation for simplicity

## Open Design Questions

The implementation author should decide these during implementation:

1. **Graceful retirement signal**: Should `retire_worker` send SIGTERM to
   the tmux pane, or just hide it and let the claude process idle? SIGTERM
   is cleaner but risks interrupting any in-flight cleanup. Recommendation:
   SIGTERM with a grace period check (verify no active task first).

2. **Pool snapshot persistence**: Should `PoolSnapshot` be persisted to
   disk (like `SupervisorSnapshot`)? Or is it always computed on demand?
   Recommendation: compute on demand for v1; persistence is a v2
   optimization if maintenance becomes too slow.

3. **Agent startup task discovery**: When `wake_worker` creates a new tmux
   window, how does the new claude session learn about its dispatched task?
   Options: (a) the agent profile prompt instructs it to check the task
   queue, (b) the tmux window command includes a `--prompt` argument, or
   (c) a message is sent via the bus. Recommendation: (a) agent profile
   approach, since the task queue already exists and the agent profiles
   already instruct task discovery.

4. **Two-PR split**: The governing plan notes that "if scaling and
   retirement logic do not fit cleanly, this slice may land as two PRs
   under the same parent label." The implementation author should assess
   whether the scope fits in one PR or needs splitting (e.g.,
   wake/dispatch in PR 1, park/retire/maintain in PR 2).

## Validation

- [ ] `uv run python -m pytest tests/unit/test_ops_worker_pool.py -v`
- [ ] `uv run python -m pytest tests/unit/test_ops_cli.py -v -k workers`
- [ ] `make check-quiet` (full validation)
- [ ] Manual smoke test: `uv run python scripts/internal/ops.py workers --json`
- [ ] Manual smoke test: verify `take_pool_snapshot()` returns correct
  worker states with a running steward session
- [ ] Verify dashboard still renders correctly after visibility changes
- [ ] Verify no regressions in existing supervisor/status/dashboard tests

### Test coverage expectations

Unit tests should cover:
- `take_pool_snapshot()` with mocked status/supervisor data
- `select_worker()` with various pool configurations (all idle, all active,
  mixed, at capacity)
- `wake_worker()` with tmux probe mocked (pane exists vs. needs creation)
- `park_worker()` and `retire_worker()` with state validation
- `dispatch_to_worker()` end-to-end with mocked tmux
- `run_pool_maintenance()` with various idle/parked age scenarios
- `_probe_tmux_pane()` with mocked subprocess
- Concurrency limit enforcement in `select_worker()`
- Error handling: tmux not available, lane not in registry, packet not found

## Planned Outputs

- `src/bid_euchre/ops/worker_pool.py` -- worker pool lifecycle module
- `tests/unit/test_ops_worker_pool.py` -- unit tests
- Updated `scripts/internal/ops.py` with `workers` subcommand
- Updated `src/bid_euchre/ops/__init__.py` with module docstring entry

## Observed Outputs

_Filled during/after execution._

## Outcome

_Filled after completion._

- Status: (pending)
- PR: (pending)
- Deviations from plan: ...
- Issues discovered: ...

## Handoff

_Filled at session end if work is incomplete._
