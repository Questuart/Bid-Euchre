"""Durable event log for operational signals.

Events are appended to a JSONL file and can be queried or drained.
The event log is the canonical bus for CI failures, heartbeat anomalies,
task completions, and other hook-produced operational signals.

Storage: ``.claude/runtime/events/events.jsonl`` (append-only, gitignored)
Archive: ``.claude/runtime/events/events.archive.jsonl`` (drained events)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.events")

VALID_EVENT_TYPES = frozenset(
    {
        "task_completed",
        "task_failed",
        "task_blocked",
        "ci_failure",
        "ci_success",
        "heartbeat_stale",
        "heartbeat_ok",
        "review_outcome",
        "plan_review_outcome",
        "worktree_created",
        "worktree_removed",
        "worktree_quarantined",
        "worktree_archived",
        "escalation",
        "recovery_action",
        "session_started",
        "session_ended",
        "watchdog_finding",
        "scheduler_tick",
    }
)

DEFAULT_EVENTS_DIR = Path(".claude/runtime/events")
EVENTS_FILE = "events.jsonl"
ARCHIVE_FILE = "events.archive.jsonl"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def append_event(
    event_type: str,
    source: str,
    lane_id: str,
    payload: dict[str, Any],
    events_dir: Path | None = None,
) -> dict[str, Any]:
    """Append one event to the durable event log.

    Args:
        event_type: Must be one of ``VALID_EVENT_TYPES``.
        source: Identifier for the producer (e.g., ``"ops.tick"``, ``"hook.post-task"``).
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        payload: Arbitrary structured payload data.
        events_dir: Override for events directory. Defaults to
            ``.claude/runtime/events``.

    Returns:
        The event dict that was written.

    Raises:
        ValueError: If ``event_type`` is not in ``VALID_EVENT_TYPES``.
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Unknown event_type {event_type!r}. "
            f"Valid types: {sorted(VALID_EVENT_TYPES)}"
        )

    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    event = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "source": source,
        "lane_id": lane_id,
        "payload": payload,
    }

    events_dir.mkdir(parents=True, exist_ok=True)
    events_file = events_dir / EVENTS_FILE

    with open(events_file, "a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")

    logger.debug("Event appended: %s from %s", event_type, source)
    return event


def read_events(
    events_dir: Path | None = None,
    *,
    since: datetime | None = None,
    event_type: str | None = None,
    lane_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read and filter events from the log.

    Args:
        events_dir: Override for events directory.
        since: Only return events after this timestamp.
        event_type: Filter to this event type.
        lane_id: Filter to this lane.
        limit: Maximum number of events to return (most recent first).

    Returns:
        List of event dicts, most recent first, up to ``limit``.
    """
    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    events_file = events_dir / EVENTS_FILE
    if not events_file.exists():
        return []

    events: list[dict[str, Any]] = []
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed event line: %s", line[:100])
                continue

            # Apply filters
            if event_type is not None and event.get("event_type") != event_type:
                continue
            if lane_id is not None and event.get("lane_id") != lane_id:
                continue
            if since is not None:
                try:
                    event_time = datetime.fromisoformat(event["timestamp"])
                    if event_time <= since:
                        continue
                except (KeyError, ValueError):
                    continue

            events.append(event)

    # Most recent first, capped at limit
    events.reverse()
    return events[:limit]


def drain_events(
    events_dir: Path | None = None,
    *,
    up_to: datetime | None = None,
) -> int:
    """Archive processed events from the active log.

    Moves events with timestamps <= ``up_to`` from the active log to
    the archive file. If ``up_to`` is None, drains all events.

    Args:
        events_dir: Override for events directory.
        up_to: Drain events up to this timestamp. None drains all.

    Returns:
        Number of events drained.
    """
    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    events_file = events_dir / EVENTS_FILE
    archive_file = events_dir / ARCHIVE_FILE

    if not events_file.exists():
        return 0

    to_drain: list[str] = []
    to_keep: list[str] = []

    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if up_to is None:
                to_drain.append(line)
                continue

            try:
                event = json.loads(line)
                event_time = datetime.fromisoformat(event["timestamp"])
                if event_time <= up_to:
                    to_drain.append(line)
                else:
                    to_keep.append(line)
            except (json.JSONDecodeError, KeyError, ValueError):
                # Keep malformed lines in active log
                to_keep.append(line)

    if not to_drain:
        return 0

    # Append drained events to archive
    with open(archive_file, "a") as f:
        for line in to_drain:
            f.write(line + "\n")

    # Rewrite active log with remaining events
    with open(events_file, "w") as f:
        for line in to_keep:
            f.write(line + "\n")

    logger.info("Drained %d events to archive", len(to_drain))
    return len(to_drain)


def count_events(
    events_dir: Path | None = None,
    *,
    event_type: str | None = None,
) -> int:
    """Count events in the active log.

    Args:
        events_dir: Override for events directory.
        event_type: Count only events of this type.

    Returns:
        Number of matching events.
    """
    if events_dir is None:
        events_dir = DEFAULT_EVENTS_DIR

    events_file = events_dir / EVENTS_FILE
    if not events_file.exists():
        return 0

    count = 0
    with open(events_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if event_type is None:
                count += 1
            else:
                try:
                    event = json.loads(line)
                    if event.get("event_type") == event_type:
                        count += 1
                except json.JSONDecodeError:
                    continue
    return count
