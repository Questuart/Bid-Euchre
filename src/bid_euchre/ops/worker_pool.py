"""Worker pool lifecycle management (Platform-7).

Enables the orchestrator to reuse idle author lanes, open/resume author
panes on demand when delegating work, and park or retire lanes when idle.
All state flows through repo-owned artifacts (worktree registry, task queue);
tmux is used for pane lifecycle only.

Uses subprocess ``tmux`` commands (not libtmux) for the first version,
matching the pattern in ``steward-session.sh``.  libtmux migration is
deferred to Platform-10 (portability layer).

Usage::

    from bid_euchre.ops.worker_pool import (
        take_pool_snapshot,
        select_worker,
        wake_worker,
        park_worker,
        retire_worker,
        dispatch_to_worker,
        nudge_pane,
        run_pool_maintenance,
    )

    pool = take_pool_snapshot()
    lane = select_worker(pool)
    if lane:
        action = dispatch_to_worker(packet_id, lane)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.worker_pool")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum number of simultaneously active (non-idle) author lanes.
#: Matches the dual-domain layout in steward-session.sh:
#: 4 platform + 4 browser-game + 1 scratch + 3 flex = 12 worker lanes.
MAX_ACTIVE_AUTHORS: int = 12

#: Idle threshold (minutes) before a lane is eligible for parking.
IDLE_PARK_MINUTES: int = 15

#: Parked threshold (minutes) before a parked lane is eligible for retirement.
PARKED_RETIRE_MINUTES: int = 60

#: Default tmux session name (matches steward-session.sh default).
DEFAULT_TMUX_SESSION: str = "steward"

#: Pool status values.
POOL_STATUSES: frozenset[str] = frozenset({"active", "idle", "parked", "retired"})

#: Default domain assignment for each managed lane.
#: Lanes with ``None`` are "flex" — available to any domain when same-domain
#: lanes are exhausted.
LANE_DOMAINS: dict[str, str | None] = {
    # Platform pool (original)
    "author-a": "platform",
    "author-b": "platform",
    "author-c": "platform",
    "author-d": "platform",
    "author-scratch": None,  # flex
    # Browser-game pool
    "brws-author-a": "browser-game",
    "brws-author-b": "browser-game",
    "brws-author-c": "browser-game",
    "brws-author-d": "browser-game",
    # Flex pool (domain-agnostic overflow)
    "flex-a": None,
    "flex-b": None,
    "flex-c": None,
}


def _managed_lanes() -> frozenset[str]:
    """Return the set of lane IDs managed by the worker pool.

    Imports KNOWN_AUTHOR_LANES from task_queue to avoid duplication.
    """
    from bid_euchre.ops.task_queue import KNOWN_AUTHOR_LANES

    return KNOWN_AUTHOR_LANES


def get_lane_domain(lane_id: str) -> str | None:
    """Return the configured domain for a lane, or None if flex/unknown."""
    return LANE_DOMAINS.get(lane_id)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class WorkerState:
    """Snapshot of one author lane's pool state."""

    lane_id: str
    pool_status: str  # "active", "idle", "parked", "retired"
    health: str  # from supervisor: "healthy", "idle", "degraded", "critical"
    current_task_id: str | None
    last_activity: str | None  # ISO 8601
    visibility: str  # "foreground", "background", "hidden"
    tmux_alive: bool  # whether the tmux pane/window exists and has a process
    session_handle: str | None
    domain: str | None = None  # configured lane domain, None = flex


@dataclass
class PoolSnapshot:
    """Point-in-time summary of the worker pool."""

    timestamp: str
    workers: list[WorkerState] = field(default_factory=list)
    active_count: int = 0
    idle_count: int = 0
    parked_count: int = 0
    retired_count: int = 0
    available_capacity: int = MAX_ACTIVE_AUTHORS


@dataclass
class PoolAction:
    """A single lifecycle action proposed or executed by the pool manager."""

    action: str  # "wake", "park", "retire", "reuse", "dispatch"
    lane_id: str
    reason: str
    executed: bool = False
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_tmux_target(
    lane_id: str,
    tmux_session: str,
    runtime_dir: Path | None = None,
) -> str:
    """Resolve a lane's tmux pane target from registry metadata.

    Reads ``tmux_window`` and ``tmux_pane`` from the lane's worktree registry
    entry to construct a ``{session}:{window}.{pane}`` target string.

    Falls back to ``{session}:{lane_id}`` if the registry entry is missing or
    does not contain pane metadata (backwards compatibility with the legacy
    one-window-per-lane layout).

    Args:
        lane_id: Lane identifier.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        A tmux target string suitable for ``send-keys -t`` or
        ``display-message -t``.
    """
    import json

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    registry_file = runtime_dir / "worktree_registry" / f"{lane_id}.json"
    try:
        data = json.loads(registry_file.read_text())
        window = data.get("tmux_window")
        pane = data.get("tmux_pane")
        if window and pane is not None:
            return f"{tmux_session}:{window}.{pane}"
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    # Fallback: legacy one-window-per-lane naming
    return f"{tmux_session}:{lane_id}"


def _probe_tmux_pane(
    lane_id: str,
    tmux_session: str,
    *,
    runtime_dir: Path | None = None,
) -> bool:
    """Check if a tmux pane for lane_id is alive in the session.

    Resolves the lane's tmux target from registry metadata (supporting both
    the tiled 4-window layout and the legacy one-window-per-lane layout) and
    queries ``tmux display-message`` to verify the pane exists.

    Args:
        lane_id: Lane identifier to look for.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        True if the lane's tmux pane exists and is running.
    """
    target = _resolve_tmux_target(lane_id, tmux_session, runtime_dir)
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", target, "-p", "#{pane_pid}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and result.stdout.strip() != ""
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _create_tmux_window(
    lane_id: str,
    worktree_path: str,
    tmux_session: str,
) -> bool:
    """Create a new tmux window for the lane.

    Creates a window in the steward session pointed at the lane's worktree.
    The window runs the claude CLI with the lane's agent profile.

    Args:
        lane_id: Lane identifier (becomes the window name).
        worktree_path: Path to the lane's worktree directory.
        tmux_session: tmux session name.

    Returns:
        True on success, False on failure.
    """
    claude_bin = shutil.which("claude")
    if not claude_bin:
        logger.error("Cannot find 'claude' binary in PATH")
        return False

    agent_name = _resolve_agent_name(lane_id)

    try:
        result = subprocess.run(
            [
                "tmux",
                "new-window",
                "-t",
                tmux_session,
                "-n",
                lane_id,
                "-c",
                worktree_path,
                claude_bin,
                "--name",
                lane_id,
                "--agent",
                agent_name,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.error(
                "tmux new-window failed for %s: %s",
                lane_id,
                result.stderr.strip(),
            )
            return False
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        logger.error("tmux new-window error for %s: %s", lane_id, exc)
        return False


def _resolve_agent_name(lane_id: str) -> str:
    """Map lane_id to the canonical agent profile name.

    Examples:
        "author-a"       -> "steward-author-a"
        "author-scratch" -> "steward-author-scratch"
    """
    return f"steward-{lane_id}"


def _resolve_worktree_path(
    lane_id: str,
    runtime_dir: Path | None = None,
) -> str | None:
    """Look up the worktree path for a lane from the registry.

    Args:
        lane_id: Lane to look up.
        runtime_dir: Override for the runtime directory root.

    Returns:
        Worktree path string, or None if not found.
    """
    from bid_euchre.ops.status import aggregate_status

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    report = aggregate_status(runtime_dir, check_worktree=False)
    for lane in report.lanes:
        if lane.lane_id == lane_id:
            return lane.worktree_path
    return None


def _classify_pool_status(
    lane: Any,
    health: str,
    has_task: bool,
    tmux_alive: bool,
    visibility: str,
) -> str:
    """Derive pool_status from lane state, health, task presence, and visibility.

    Args:
        lane: LaneStatus object.
        health: Health classification from supervisor.
        has_task: Whether the lane has an active/dispatched task.
        tmux_alive: Whether the tmux pane is alive.
        visibility: Effective visibility.

    Returns:
        One of "active", "idle", "parked", "retired".
    """
    # Hidden lanes are parked or retired depending on tmux state
    if visibility == "hidden":
        if tmux_alive:
            return "parked"
        return "retired"

    # Active task -> lane is busy
    if has_task:
        return "active"

    # Lane shows signs of life but has no task -> idle (dispatchable)
    if lane.state in ("active", "likely_active"):
        return "idle"

    # Otherwise idle
    return "idle"


def _get_lane_task_id(
    lane_id: str,
    runtime_dir: Path | None = None,
) -> str | None:
    """Find the active/dispatched task ID for a lane, if any.

    Args:
        lane_id: Lane to check.
        runtime_dir: Override for the task queue root directory.

    Returns:
        Packet ID of the active task, or None.
    """
    from bid_euchre.ops.task_queue import list_packets

    # task_queue functions expect the task_queue subdirectory, not the
    # runtime root.  When runtime_dir is provided (e.g. ".claude/runtime"),
    # derive the correct path; when None, let shared_task_root() default.
    task_queue_root = (runtime_dir / "task_queue") if runtime_dir else None

    # Check dispatched packets owned by this lane
    dispatched = list_packets(
        task_queue_root, status_filter="dispatched", owner_filter=lane_id
    )
    if dispatched:
        return dispatched[0].packet_id
    return None


def _minutes_since(iso_timestamp: str | None, now: datetime) -> float | None:
    """Calculate minutes elapsed since an ISO 8601 timestamp.

    Returns None if the timestamp is None or unparseable.
    """
    if not iso_timestamp:
        return None
    try:
        # Handle various ISO formats
        ts_str = iso_timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = now - dt
        return delta.total_seconds() / 60.0
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


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

    Filters to managed lanes only.

    Args:
        runtime_dir: Override for the runtime directory root.
        tmux_session: tmux session name to probe.
        now: Override current time for testing.

    Returns:
        A new :class:`PoolSnapshot`.
    """
    from bid_euchre.ops.dashboard import effective_visibility
    from bid_euchre.ops.status import aggregate_status
    from bid_euchre.ops.supervisor import take_snapshot as supervisor_snapshot

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    if now is None:
        now = datetime.now(timezone.utc)

    managed = _managed_lanes()

    # Gather lane status
    report = aggregate_status(runtime_dir, check_worktree=False)

    # Gather supervisor health assessments
    try:
        sup_snap = supervisor_snapshot(runtime_dir, now=now)
        health_by_lane = {la.lane_id: la.health for la in sup_snap.lane_assessments}
    except Exception as exc:
        logger.debug("Supervisor snapshot failed: %s", exc)
        health_by_lane = {}

    workers: list[WorkerState] = []
    counts = {"active": 0, "idle": 0, "parked": 0, "retired": 0}

    for lane in report.lanes:
        if lane.lane_id not in managed:
            continue

        visibility = effective_visibility(lane)
        health = health_by_lane.get(lane.lane_id, "idle")
        tmux_alive = _probe_tmux_pane(lane.lane_id, tmux_session)
        task_id = _get_lane_task_id(lane.lane_id, runtime_dir)

        pool_status = _classify_pool_status(
            lane, health, task_id is not None, tmux_alive, visibility
        )

        # Determine last activity time
        last_activity = lane.last_progress or lane.last_active

        workers.append(
            WorkerState(
                lane_id=lane.lane_id,
                pool_status=pool_status,
                health=health,
                current_task_id=task_id,
                last_activity=last_activity,
                visibility=visibility,
                tmux_alive=tmux_alive,
                session_handle=lane.session_handle,
                domain=get_lane_domain(lane.lane_id),
            )
        )
        counts[pool_status] = counts.get(pool_status, 0) + 1

    return PoolSnapshot(
        timestamp=now.isoformat(),
        workers=workers,
        active_count=counts["active"],
        idle_count=counts["idle"],
        parked_count=counts["parked"],
        retired_count=counts["retired"],
        available_capacity=max(0, MAX_ACTIVE_AUTHORS - counts["active"]),
    )


def select_worker(
    pool: PoolSnapshot,
    *,
    preferred_lane: str | None = None,
    domain: str | None = None,
    allow_cross_domain: bool = False,
) -> str | None:
    """Choose the best lane for new work, with optional domain routing.

    Priority order (within each tier, same-domain lanes are tried first,
    then flex lanes, then cross-domain only if *allow_cross_domain* is set):

    1. preferred_lane (if idle or parked and healthy, and domain-compatible)
    2. idle lanes (already running, no active task)
    3. parked lanes (need waking, but worktree exists)
    4. retired lanes (need full resume)
    5. None if at MAX_ACTIVE_AUTHORS

    Domain routing rule:
    - same-domain first (worker.domain == domain)
    - flex second (worker.domain is None)
    - cross-domain only if *allow_cross_domain* is True

    When *domain* is None, all lanes are eligible (no domain filtering).

    Args:
        pool: Current pool snapshot.
        preferred_lane: Preferred lane ID, if any.
        domain: Execution domain to route to (e.g. "platform", "browser-game").
        allow_cross_domain: If True, allow routing to lanes in a different
            domain when same-domain and flex lanes are exhausted.

    Returns:
        Lane ID or None if no capacity.
    """
    if pool.available_capacity <= 0:
        return None

    workers_by_id = {w.lane_id: w for w in pool.workers}

    def _domain_compatible(w: WorkerState) -> bool:
        """Check if a worker is compatible with the requested domain."""
        if domain is None:
            return True  # no domain preference — all lanes eligible
        if w.domain == domain:
            return True  # same domain
        if w.domain is None:
            return True  # flex lane
        return allow_cross_domain  # cross-domain only if explicitly allowed

    def _domain_sort_key(w: WorkerState) -> int:
        """Sort key: same-domain (0) > flex (1) > cross-domain (2)."""
        if domain is None:
            return 0
        if w.domain == domain:
            return 0
        if w.domain is None:
            return 1
        return 2

    # 1. Check preferred lane
    if preferred_lane and preferred_lane in workers_by_id:
        w = workers_by_id[preferred_lane]
        if w.pool_status in ("idle", "parked", "retired") and _domain_compatible(w):
            return preferred_lane

    # Helper: filter, sort by domain preference, return first match
    def _best_from(status: str) -> str | None:
        candidates = [
            w
            for w in pool.workers
            if w.pool_status == status
            and w.health != "critical"
            and _domain_compatible(w)
        ]
        if not candidates:
            return None
        candidates.sort(key=_domain_sort_key)
        return candidates[0].lane_id

    # 2. Idle lanes (already running)
    result = _best_from("idle")
    if result:
        return result

    # 3. Parked lanes
    result = _best_from("parked")
    if result:
        return result

    # 4. Retired lanes
    result = _best_from("retired")
    if result:
        return result

    return None


def wake_worker(
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Open or resume an author pane for the given lane.

    Steps:
    1. Check if tmux window already exists for lane_id.
       - If alive: set visibility to "foreground", return.
    2. If window does not exist: create a new tmux window in the
       steward session, pointed at the lane's worktree.
    3. Update registry: visibility -> "foreground".
    4. Return PoolAction with executed=True.

    Args:
        lane_id: Lane to wake.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        A :class:`PoolAction` describing what happened.
    """
    from bid_euchre.ops.dashboard import set_lane_visibility

    if lane_id not in _managed_lanes():
        return PoolAction(
            action="wake",
            lane_id=lane_id,
            reason=f"Lane {lane_id!r} is not a managed author lane",
            executed=False,
            error="not_managed",
        )

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    # Check if already alive
    if _probe_tmux_pane(lane_id, tmux_session):
        # Already running -- just ensure visibility
        set_lane_visibility(lane_id, "foreground", runtime_dir)
        return PoolAction(
            action="wake",
            lane_id=lane_id,
            reason="Pane already alive; set visibility to foreground",
            executed=True,
        )

    # Need to create a new tmux window
    worktree_path = _resolve_worktree_path(lane_id, runtime_dir)
    if not worktree_path:
        return PoolAction(
            action="wake",
            lane_id=lane_id,
            reason=f"Could not resolve worktree path for {lane_id!r}",
            executed=False,
            error="no_worktree",
        )

    success = _create_tmux_window(lane_id, worktree_path, tmux_session)
    if not success:
        return PoolAction(
            action="wake",
            lane_id=lane_id,
            reason="Failed to create tmux window",
            executed=False,
            error="tmux_failed",
        )

    # Update visibility
    set_lane_visibility(lane_id, "foreground", runtime_dir)

    return PoolAction(
        action="wake",
        lane_id=lane_id,
        reason="Created tmux window and set visibility to foreground",
        executed=True,
    )


def park_worker(
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Move an idle author lane to parked state.

    Sets visibility to "hidden" but does NOT kill the tmux pane.
    The claude process may still be running but idle.

    Args:
        lane_id: Lane to park.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        A :class:`PoolAction` describing what happened.
    """
    from bid_euchre.ops.dashboard import set_lane_visibility

    if lane_id not in _managed_lanes():
        return PoolAction(
            action="park",
            lane_id=lane_id,
            reason=f"Lane {lane_id!r} is not a managed author lane",
            executed=False,
            error="not_managed",
        )

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    # Verify no active task
    task_id = _get_lane_task_id(lane_id, runtime_dir)
    if task_id:
        return PoolAction(
            action="park",
            lane_id=lane_id,
            reason=f"Lane has active task {task_id!r}; cannot park",
            executed=False,
            error="has_active_task",
        )

    # Set visibility to hidden
    set_lane_visibility(lane_id, "hidden", runtime_dir)

    return PoolAction(
        action="park",
        lane_id=lane_id,
        reason="Set visibility to hidden; tmux pane left running",
        executed=True,
    )


def retire_worker(
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Fully retire a parked lane.

    Sets visibility to "hidden" and sends SIGTERM to the tmux pane's
    process (if alive).  The worktree is never removed (per worktree
    protection rules).

    Args:
        lane_id: Lane to retire.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        A :class:`PoolAction` describing what happened.
    """
    from bid_euchre.ops.dashboard import set_lane_visibility

    if lane_id not in _managed_lanes():
        return PoolAction(
            action="retire",
            lane_id=lane_id,
            reason=f"Lane {lane_id!r} is not a managed author lane",
            executed=False,
            error="not_managed",
        )

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    # Verify no active task
    task_id = _get_lane_task_id(lane_id, runtime_dir)
    if task_id:
        return PoolAction(
            action="retire",
            lane_id=lane_id,
            reason=f"Lane has active task {task_id!r}; cannot retire",
            executed=False,
            error="has_active_task",
        )

    # Set visibility to hidden
    set_lane_visibility(lane_id, "hidden", runtime_dir)

    # Terminate the tmux pane if alive
    if _probe_tmux_pane(lane_id, tmux_session):
        try:
            subprocess.run(
                [
                    "tmux",
                    "kill-window",
                    "-t",
                    f"{tmux_session}:{lane_id}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            logger.info("Terminated tmux window for %s", lane_id)
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
            logger.warning(
                "Failed to terminate tmux window for %s: %s",
                lane_id,
                exc,
            )
            return PoolAction(
                action="retire",
                lane_id=lane_id,
                reason=f"Visibility set to hidden but tmux kill failed: {exc}",
                executed=True,
                error="tmux_kill_failed",
            )

    return PoolAction(
        action="retire",
        lane_id=lane_id,
        reason="Set visibility to hidden and terminated tmux pane",
        executed=True,
    )


def nudge_pane(
    lane_id: str,
    packet_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Send a short command to the lane's tmux pane to trigger task consumption.

    Uses ``tmux send-keys`` to inject ``/start-task <packet_id>`` into the
    target pane.  The command is a Claude Code slash-command that loads the
    dispatched task packet from durable state and begins execution.

    The target is resolved from the lane's worktree registry metadata
    (``tmux_window`` + ``tmux_pane``), supporting both the tiled 4-window
    layout and the legacy one-window-per-lane layout.

    Args:
        lane_id: Target lane whose pane should receive the command.
        packet_id: Task packet ID to pass to the ``/start-task`` skill.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        A :class:`PoolAction` with ``action="nudge"`` describing the outcome.
    """
    target = _resolve_tmux_target(lane_id, tmux_session, runtime_dir)
    cmd = f"/start-task {packet_id}"

    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", target, cmd, "Enter"],
            check=True,
            capture_output=True,
            timeout=5,
        )
        return PoolAction(
            action="nudge",
            lane_id=lane_id,
            reason=f"Sent '{cmd}' to pane {target}",
            executed=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return PoolAction(
            action="nudge",
            lane_id=lane_id,
            reason=f"Failed to nudge pane: {exc}",
            executed=False,
            error="nudge_failed",
        )
    except (FileNotFoundError, OSError) as exc:
        return PoolAction(
            action="nudge",
            lane_id=lane_id,
            reason=f"Failed to nudge pane: {exc}",
            executed=False,
            error="nudge_failed",
        )


def dispatch_to_worker(
    packet_id: str,
    lane_id: str,
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
) -> PoolAction:
    """Complete lifecycle: wake worker, assign task packet, nudge pane.

    Steps:
    1. Load task packet, verify it is in "approved" status.
    2. Take pool snapshot, verify lane_id has capacity.
    3. If lane is parked/retired: wake_worker() first.
    4. Transition packet to "dispatched" with owner = lane_id.
    4b. Copy dispatched packet JSON to the target worktree's task_queue
        so the author lane can discover it via ``/start-task``.
    5. Write inbox message via message_bus (audit trail).
    6. Nudge the target pane with ``/start-task <packet_id>``.
    7. Record delivery outcome (update inbox message status).
    8. Set lane visibility to "foreground".
    9. Return PoolAction.

    This is the high-level entry point the orchestrator calls.

    Args:
        packet_id: Task packet ID to dispatch.
        lane_id: Target lane for the work.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.

    Returns:
        A :class:`PoolAction` describing what happened.
    """
    from bid_euchre.ops.task_queue import load_packet, transition_status

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    # task_queue functions expect the task_queue subdirectory, not the
    # runtime root.
    task_queue_root = runtime_dir / "task_queue"

    # 1. Verify packet exists and is approved
    packet = load_packet(packet_id, task_queue_root)
    if packet is None:
        return PoolAction(
            action="dispatch",
            lane_id=lane_id,
            reason=f"Task packet {packet_id!r} not found",
            executed=False,
            error="packet_not_found",
        )

    if packet.status != "approved":
        return PoolAction(
            action="dispatch",
            lane_id=lane_id,
            reason=(
                f"Packet {packet_id!r} is in {packet.status!r} status; "
                f"expected 'approved'"
            ),
            executed=False,
            error="wrong_status",
        )

    # 2. Take snapshot and verify capacity
    pool = take_pool_snapshot(runtime_dir, tmux_session=tmux_session)
    worker = next((w for w in pool.workers if w.lane_id == lane_id), None)

    if worker is None:
        return PoolAction(
            action="dispatch",
            lane_id=lane_id,
            reason=f"Lane {lane_id!r} not found in pool snapshot",
            executed=False,
            error="lane_not_found",
        )

    if worker.pool_status == "active":
        return PoolAction(
            action="dispatch",
            lane_id=lane_id,
            reason=f"Lane {lane_id!r} is already active with a task",
            executed=False,
            error="lane_busy",
        )

    # An idle lane is already counted as non-active, so dispatching it does
    # not consume additional capacity.  Only reject when there is truly no
    # room (capacity exhausted AND the lane would need to be woken/promoted).
    if pool.available_capacity <= 0 and worker.pool_status not in ("idle",):
        return PoolAction(
            action="dispatch",
            lane_id=lane_id,
            reason="No available capacity in the worker pool",
            executed=False,
            error="no_capacity",
        )

    # 3. Wake if parked/retired
    if worker.pool_status in ("parked", "retired"):
        wake_result = wake_worker(
            lane_id,
            tmux_session=tmux_session,
            runtime_dir=runtime_dir,
        )
        if not wake_result.executed:
            return PoolAction(
                action="dispatch",
                lane_id=lane_id,
                reason=f"Failed to wake lane: {wake_result.reason}",
                executed=False,
                error=f"wake_failed:{wake_result.error}",
            )

    # 4. Transition packet to dispatched
    try:
        # Update packet owner to lane_id before transitioning
        # (TaskPacket is frozen, so we re-save with owner set)
        from dataclasses import asdict as _asdict

        from bid_euchre.ops.task_queue import TaskPacket, save_packet

        pkt_data = _asdict(packet)
        pkt_data["owner"] = lane_id
        pkt_data["status"] = "approved"  # keep current status for re-save
        updated_pkt = TaskPacket(**pkt_data)
        save_packet(updated_pkt, task_queue_root)

        transition_status(packet_id, "dispatched", task_queue_root)
    except (ValueError, OSError) as exc:
        return PoolAction(
            action="dispatch",
            lane_id=lane_id,
            reason=f"Failed to transition packet: {exc}",
            executed=False,
            error="transition_failed",
        )

    # 4b. Copy dispatched packet to the target worktree's task_queue
    #     so the author lane can discover it via /start-task.
    worktree_path = _resolve_worktree_path(lane_id, runtime_dir)
    if worktree_path:
        wt_task_queue = Path(worktree_path) / ".claude" / "runtime" / "task_queue"
        try:
            wt_task_queue.mkdir(parents=True, exist_ok=True)
            src_packet = task_queue_root / f"{packet_id}.json"
            if src_packet.exists():
                shutil.copy2(str(src_packet), str(wt_task_queue / f"{packet_id}.json"))
                logger.info(
                    "Copied packet %s to worktree task_queue at %s",
                    packet_id,
                    wt_task_queue,
                )
        except OSError as exc:
            logger.warning(
                "Failed to copy packet %s to worktree %s: %s",
                packet_id,
                worktree_path,
                exc,
            )
    else:
        logger.warning(
            "Could not resolve worktree path for %s; packet not copied to worktree",
            lane_id,
        )

    # 5. Write inbox message via message_bus
    message_id: str | None = None
    try:
        from bid_euchre.ops.message_bus import create_message, send_message

        msg = create_message(
            from_lane="orchestrator",
            to_lane=lane_id,
            message_type="assignment",
            summary=f"Task dispatched: {packet.title}",
            task_id=packet_id,
            payload={"packet_id": packet_id, "title": packet.title},
        )
        message_id = send_message(msg)
    except Exception as exc:
        # Inbox message is best-effort; dispatch still succeeds
        logger.warning(
            "Failed to send inbox message for dispatch %s: %s",
            packet_id,
            exc,
        )

    # 6. Nudge the target pane
    nudge_result = nudge_pane(lane_id, packet_id, tmux_session=tmux_session)

    # 7. Record delivery outcome
    if message_id is not None:
        try:
            from bid_euchre.ops.message_bus import (
                _update_inbox_status,
                shared_bus_root,
            )

            if nudge_result.executed:
                bus_root = shared_bus_root()
                _update_inbox_status(message_id, lane_id, "delivered", bus_root)
        except Exception as exc:
            logger.warning(
                "Failed to update delivery status for message %s: %s",
                message_id,
                exc,
            )

    # 8. Ensure visibility is foreground
    from bid_euchre.ops.dashboard import set_lane_visibility

    set_lane_visibility(lane_id, "foreground", runtime_dir)

    return PoolAction(
        action="dispatch",
        lane_id=lane_id,
        reason=f"Dispatched packet {packet_id!r} to {lane_id!r}",
        executed=True,
    )


def run_pool_maintenance(
    *,
    tmux_session: str = DEFAULT_TMUX_SESSION,
    runtime_dir: Path | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> list[PoolAction]:
    """Periodic maintenance: park idle workers, retire parked ones.

    Scans all managed lanes and applies lifecycle transitions:
    - idle > IDLE_PARK_MINUTES -> park
    - parked > PARKED_RETIRE_MINUTES -> retire

    Args:
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.
        now: Override current time for testing.
        dry_run: If True, only propose actions without executing them.

    Returns:
        List of proposed (dry_run=True) or executed actions.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    if now is None:
        now = datetime.now(timezone.utc)

    pool = take_pool_snapshot(runtime_dir, tmux_session=tmux_session, now=now)
    actions: list[PoolAction] = []

    for worker in pool.workers:
        idle_minutes = _minutes_since(worker.last_activity, now)

        if worker.pool_status == "idle" and idle_minutes is not None:
            if idle_minutes > IDLE_PARK_MINUTES:
                action = PoolAction(
                    action="park",
                    lane_id=worker.lane_id,
                    reason=(
                        f"Idle for {idle_minutes:.0f} min "
                        f"(threshold: {IDLE_PARK_MINUTES} min)"
                    ),
                    executed=False,
                )
                if not dry_run:
                    result = park_worker(
                        worker.lane_id,
                        tmux_session=tmux_session,
                        runtime_dir=runtime_dir,
                    )
                    action.executed = result.executed
                    action.error = result.error
                actions.append(action)

        elif worker.pool_status == "parked" and idle_minutes is not None:
            if idle_minutes > PARKED_RETIRE_MINUTES:
                action = PoolAction(
                    action="retire",
                    lane_id=worker.lane_id,
                    reason=(
                        f"Parked for {idle_minutes:.0f} min "
                        f"(threshold: {PARKED_RETIRE_MINUTES} min)"
                    ),
                    executed=False,
                )
                if not dry_run:
                    result = retire_worker(
                        worker.lane_id,
                        tmux_session=tmux_session,
                        runtime_dir=runtime_dir,
                    )
                    action.executed = result.executed
                    action.error = result.error
                actions.append(action)

    return actions


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_pool_text(pool: PoolSnapshot) -> str:
    """Format a pool snapshot as human-readable text.

    Args:
        pool: Pool snapshot to format.

    Returns:
        Multi-line text summary.
    """
    lines: list[str] = []
    lines.append("=== Worker Pool ===")
    lines.append(f"Timestamp: {pool.timestamp}")
    lines.append(
        f"Active: {pool.active_count}  Idle: {pool.idle_count}  "
        f"Parked: {pool.parked_count}  Retired: {pool.retired_count}  "
        f"Capacity: {pool.available_capacity}"
    )
    lines.append("")

    if pool.workers:
        lines.append("Workers:")
        for w in pool.workers:
            tmux_str = "tmux:up" if w.tmux_alive else "tmux:down"
            task_str = f"  task:{w.current_task_id}" if w.current_task_id else ""
            domain_str = f"  domain:{w.domain}" if w.domain else "  domain:flex"
            lines.append(
                f"  {w.lane_id:15s} [{w.pool_status:8s}] "
                f"health:{w.health:8s} vis:{w.visibility:10s} "
                f"{tmux_str}{domain_str}{task_str}"
            )
    else:
        lines.append("  (no managed workers found)")

    return "\n".join(lines)


def format_pool_json(pool: PoolSnapshot) -> dict[str, Any]:
    """Format a pool snapshot as a JSON-serializable dict.

    Args:
        pool: Pool snapshot to format.

    Returns:
        Dict suitable for JSON serialization.
    """
    return {
        "timestamp": pool.timestamp,
        "summary": {
            "active": pool.active_count,
            "idle": pool.idle_count,
            "parked": pool.parked_count,
            "retired": pool.retired_count,
            "available_capacity": pool.available_capacity,
        },
        "workers": [asdict(w) for w in pool.workers],
    }


def format_action_text(action: PoolAction) -> str:
    """Format a single pool action as human-readable text."""
    status = "OK" if action.executed else "SKIPPED"
    error_str = f" (error: {action.error})" if action.error else ""
    return f"[{status}] {action.action} {action.lane_id}: {action.reason}{error_str}"


def format_actions_json(actions: list[PoolAction]) -> list[dict[str, Any]]:
    """Format pool actions as JSON-serializable list."""
    return [asdict(a) for a in actions]
