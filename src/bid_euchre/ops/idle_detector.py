"""Fleet idle detection for auto-shutoff (#1572).

Determines whether the entire steward fleet has been idle for a configurable
threshold.  "Idle" means no meaningful operational change has occurred across
any lane — no PRs merged/opened, no tasks dispatched/completed, and no lane
has transitioned to active state.

The detector reads the durable event log to find the most recent meaningful
event and compares its timestamp against the threshold.  It also checks for
any currently-active lanes (via the status module) to avoid false positives
when a lane is actively working but hasn't emitted an event recently.

Usage::

    from bid_euchre.ops.idle_detector import is_fleet_idle

    result = is_fleet_idle(threshold_minutes=90)
    if result.idle:
        print(f"Fleet idle for {result.idle_minutes:.0f}m — consider shutoff")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bid_euchre.ops.events import append_event, read_events

logger = logging.getLogger("ops.idle_detector")

# Default idle threshold in minutes.
DEFAULT_THRESHOLD_MINUTES = 90

# Control-plane lanes that are always running (crons, monitoring, review
# polling) and should NOT count when determining fleet idleness.  Only
# implementation lanes (author, browser-author, flex, analyst) matter.
CONTROL_PLANE_LANES = frozenset({"orchestrator", "ops", "review"})

# Event types that reset the idle timer.  These represent genuine fleet-level
# progress, not infrastructure bookkeeping.  Every type here MUST be in
# VALID_EVENT_TYPES (events.py) AND emitted by at least one production path.
# The subset-containment test (test_ops_idle_detector.py) enforces the first
# invariant; see #1588 for the emission audit that verified the second.
MEANINGFUL_EVENT_TYPES = frozenset(
    {
        # Task lifecycle
        "task_started",
        "task_completed",
        "task_failed",
        "task_rerouted",
        # CI outcomes
        "ci_success",
        "ci_failure",
        # Review & PR signals
        "review_outcome",
        "review_verdict",
        # Skill events that represent deliberate work
        "skill_promoted",
    }
)


@dataclass(frozen=True)
class IdleStatus:
    """Result of a fleet idle check.

    Attributes:
        idle: True if the fleet is considered idle (no meaningful activity
            within the threshold and no lanes currently active).
        idle_minutes: Minutes since the last meaningful event.  ``0.0`` when
            the fleet is active or no events exist.
        last_meaningful_event: Timestamp of the most recent meaningful event,
            or None if no events were found.
        active_lanes: List of lane IDs that are currently in an active state.
            Non-empty means the fleet is NOT idle regardless of event age.
        reason: Human-readable explanation of the determination.
    """

    idle: bool
    idle_minutes: float
    last_meaningful_event: datetime | None
    active_lanes: list[str]
    reason: str


def _find_last_meaningful_event(
    events_dir: Path | None = None,
) -> datetime | None:
    """Scan the event log for the most recent meaningful event timestamp.

    Returns None if no meaningful events are found.
    """
    # Read a generous number of recent events (meaningful ones may be
    # interspersed with infrastructure noise).
    events = read_events(events_dir, limit=500)

    for event in events:  # Already sorted most-recent-first
        etype = event.get("event_type", "")
        lane = event.get("lane_id", "")
        # Skip events emitted by control-plane lanes — they run crons that
        # generate infrastructure events and should not reset the idle timer.
        if lane in CONTROL_PLANE_LANES:
            continue
        if etype in MEANINGFUL_EVENT_TYPES:
            try:
                return datetime.fromisoformat(event["timestamp"])
            except (KeyError, ValueError):
                continue
    return None


def _get_active_lane_ids(
    runtime_dir: Path | None = None,
) -> list[str]:
    """Return lane IDs that are currently active.

    Uses a lightweight check: reads the worktree registry for lanes with
    an active session_id.  This avoids importing the full status module's
    heavy aggregation machinery.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    registry_dir = runtime_dir / "worktree_registry"
    if not registry_dir.exists():
        return []

    active: list[str] = []
    import json as _json

    for entry_file in sorted(registry_dir.glob("*.json")):
        try:
            data = _json.loads(entry_file.read_text())
        except (OSError, ValueError):
            continue
        lane_id = data.get("lane_id", "")
        session_id = data.get("session_id")
        if session_id and lane_id and lane_id not in CONTROL_PLANE_LANES:
            active.append(lane_id)

    return active


def is_fleet_idle(
    threshold_minutes: float = DEFAULT_THRESHOLD_MINUTES,
    *,
    events_dir: Path | None = None,
    runtime_dir: Path | None = None,
    now: datetime | None = None,
) -> IdleStatus:
    """Determine whether the steward fleet is idle.

    The fleet is considered idle when **both** conditions are met:
    1. No meaningful event has occurred within ``threshold_minutes``.
    2. No lane is currently in an active state (has a live session_id).

    Args:
        threshold_minutes: Number of minutes with no meaningful activity
            before the fleet is considered idle.  Defaults to 90.
        events_dir: Override for the events directory.
        runtime_dir: Override for the runtime directory (used for lane
            activity checks).
        now: Override for current time (for testing).

    Returns:
        An :class:`IdleStatus` describing the determination.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Find the last meaningful event
    last_event_ts = _find_last_meaningful_event(events_dir)

    # 2. Check for currently active lanes
    active_lanes = _get_active_lane_ids(runtime_dir)

    # If any lane is actively running, the fleet is not idle
    if active_lanes:
        idle_minutes = (
            (now - last_event_ts).total_seconds() / 60.0 if last_event_ts else 0.0
        )
        return IdleStatus(
            idle=False,
            idle_minutes=idle_minutes,
            last_meaningful_event=last_event_ts,
            active_lanes=active_lanes,
            reason=f"Active lanes: {', '.join(sorted(active_lanes))}",
        )

    # No active lanes — check event recency
    if last_event_ts is None:
        # No events at all — if no lanes are active, we're idle
        return IdleStatus(
            idle=True,
            idle_minutes=float(threshold_minutes),  # Conservative: at least threshold
            last_meaningful_event=None,
            active_lanes=[],
            reason="No meaningful events found and no active lanes",
        )

    elapsed = now - last_event_ts
    idle_minutes = elapsed.total_seconds() / 60.0

    if idle_minutes >= threshold_minutes:
        return IdleStatus(
            idle=True,
            idle_minutes=idle_minutes,
            last_meaningful_event=last_event_ts,
            active_lanes=[],
            reason=(
                f"No meaningful activity for {idle_minutes:.0f}m "
                f"(threshold: {threshold_minutes:.0f}m)"
            ),
        )

    return IdleStatus(
        idle=False,
        idle_minutes=idle_minutes,
        last_meaningful_event=last_event_ts,
        active_lanes=[],
        reason=(
            f"Last meaningful event {idle_minutes:.0f}m ago "
            f"(threshold: {threshold_minutes:.0f}m)"
        ),
    )


# ---------------------------------------------------------------------------
# Shutoff recommendation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShutoffRecommendation:
    """Structured recommendation from the fleet idle check.

    When ``should_shutoff`` is True, the caller should act on the
    recommended actions (cancel cron jobs, notify user, produce handoff).

    Attributes:
        should_shutoff: Whether the fleet should shut off autonomous operation.
        idle_status: The underlying :class:`IdleStatus` determination.
        recommended_actions: Human-readable list of actions to take.
    """

    should_shutoff: bool
    idle_status: IdleStatus
    recommended_actions: list[str]


def recommend_shutoff(
    threshold_minutes: float = DEFAULT_THRESHOLD_MINUTES,
    *,
    events_dir: Path | None = None,
    runtime_dir: Path | None = None,
    now: datetime | None = None,
) -> ShutoffRecommendation:
    """Check fleet idle status and produce a shutoff recommendation.

    Wraps :func:`is_fleet_idle` and translates the result into a structured
    recommendation with concrete action items for the caller to execute.

    Args:
        threshold_minutes: Minutes threshold for idle detection.
        events_dir: Override for the events directory.
        runtime_dir: Override for the runtime directory.
        now: Override for current time (for testing).

    Returns:
        A :class:`ShutoffRecommendation` with actions if shutoff is warranted.
    """
    status = is_fleet_idle(
        threshold_minutes=threshold_minutes,
        events_dir=events_dir,
        runtime_dir=runtime_dir,
        now=now,
    )

    if not status.idle:
        return ShutoffRecommendation(
            should_shutoff=False,
            idle_status=status,
            recommended_actions=[],
        )

    actions = [
        "Cancel all active cron jobs to stop burning tokens",
        "Produce a session handoff summary (what shipped, what's stuck, next steps)",
        "Log the shutoff event for operational traceability",
    ]

    # Include the idle duration for context
    logger.warning(
        "Fleet idle shutoff recommended: %s (idle %.0fm)",
        status.reason,
        status.idle_minutes,
    )

    return ShutoffRecommendation(
        should_shutoff=True,
        idle_status=status,
        recommended_actions=actions,
    )


# ---------------------------------------------------------------------------
# Shutoff execution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ShutoffResult:
    """Result of executing the fleet idle shutoff sequence.

    Attributes:
        executed: True if the shutoff was actually executed (event logged).
            False when the fleet is not idle or when running in dry-run mode.
        idle_status: The underlying :class:`IdleStatus` determination that
            informed the decision.
        event_logged: Whether a ``fleet_idle_shutoff`` event was appended
            to the durable event log.
        summary: Human-readable summary of the outcome.
        recommended_actions: Concrete actions for the caller to execute.
            The caller (typically the orchestrator) is responsible for:
            - Cancelling cron jobs (via CronDelete)
            - Producing a session handoff summary
            - Notifying the user (via Telegram or durable log)
    """

    executed: bool
    idle_status: IdleStatus
    event_logged: bool
    summary: str
    recommended_actions: list[str]


def execute_shutoff(
    threshold_minutes: float = DEFAULT_THRESHOLD_MINUTES,
    *,
    events_dir: Path | None = None,
    runtime_dir: Path | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
) -> ShutoffResult:
    """Check fleet idle status and execute shutoff if warranted.

    This is the top-level entry point for the auto-shutoff sequence.  It:

    1. Checks whether the fleet is idle via :func:`is_fleet_idle`.
    2. If idle past the threshold, appends a ``fleet_idle_shutoff`` event
       to the durable event log (unless ``dry_run`` is True).
    3. Returns a :class:`ShutoffResult` with the recommended actions for
       the caller to execute.

    The caller is responsible for executing the recommended actions:

    - **Cancel cron jobs** — stop polling / check-in crons to prevent
      token waste.
    - **Produce a session handoff** — summarize what shipped, what's
      stuck, and recommended next steps.
    - **Notify the user** — via Telegram (if available) or durable log.
    - **Log the shutoff** — the event is logged here, but the caller
      should also record the shutoff in its session notes.

    This function is idempotent — calling it multiple times produces
    multiple events but the same recommendation.  The caller should
    gate on a "shutoff already executed" flag to avoid duplicate actions.

    Args:
        threshold_minutes: Minutes threshold for idle detection.
        events_dir: Override for the events directory.
        runtime_dir: Override for the runtime directory.
        now: Override for current time (for testing).
        dry_run: If True, check idle status but do not log the event.
            Useful for previewing the shutoff recommendation.

    Returns:
        A :class:`ShutoffResult` describing the outcome.
    """
    status = is_fleet_idle(
        threshold_minutes=threshold_minutes,
        events_dir=events_dir,
        runtime_dir=runtime_dir,
        now=now,
    )

    if not status.idle:
        return ShutoffResult(
            executed=False,
            idle_status=status,
            event_logged=False,
            summary=f"Fleet is active — no shutoff needed. {status.reason}",
            recommended_actions=[],
        )

    # Fleet is idle — prepare the shutoff
    actions = [
        "Cancel all active cron jobs (CronList → CronDelete each)",
        "Produce a session handoff summary (what shipped, what's stuck, next steps)",
        "Notify the user via Telegram or durable log",
        "Stop autonomous dispatch and monitoring (do NOT exit the session)",
    ]

    event_logged = False
    if not dry_run:
        try:
            append_event(
                event_type="fleet_idle_shutoff",
                source="ops.idle_detector",
                lane_id="orchestrator",
                payload={
                    "idle_minutes": status.idle_minutes,
                    "threshold_minutes": threshold_minutes,
                    "last_meaningful_event": (
                        status.last_meaningful_event.isoformat()
                        if status.last_meaningful_event
                        else None
                    ),
                    "active_lanes": status.active_lanes,
                    "reason": status.reason,
                },
                events_dir=events_dir,
            )
            event_logged = True
        except Exception as exc:
            logger.error("Failed to log fleet_idle_shutoff event: %s", exc)

    idle_mins = status.idle_minutes
    summary = (
        f"Fleet idle shutoff {'executed' if event_logged else 'recommended'}: "
        f"no meaningful activity for {idle_mins:.0f}m "
        f"(threshold: {threshold_minutes:.0f}m). "
        f"{status.reason}"
    )
    if dry_run:
        summary = f"[DRY RUN] {summary}"

    logger.warning("Fleet idle shutoff: %s", summary)

    return ShutoffResult(
        executed=event_logged,
        idle_status=status,
        event_logged=event_logged,
        summary=summary,
        recommended_actions=actions,
    )
