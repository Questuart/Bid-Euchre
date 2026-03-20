"""Retry follow-through helpers for task lifecycle management.

Proactively scans the event log for tasks that have failed but haven't
been retried, rerouted, or completed — ensuring failed work does not
silently disappear.

This module complements ``recovery.py`` (which is reactive: you ask it
to evaluate a specific task) by providing aggregate scanning across all
tasks in the event history.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("ops.retries")


@dataclass
class PendingRetry:
    """A task with an unresolved failure that needs follow-up."""

    task_id: str
    failure_count: int
    last_failure_details: str
    last_failure_lane: str
    last_failure_timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "failure_count": self.failure_count,
            "last_failure_details": self.last_failure_details,
            "last_failure_lane": self.last_failure_lane,
            "last_failure_timestamp": self.last_failure_timestamp,
        }


@dataclass
class RetrySummary:
    """Aggregate retry/reroute state across all tasks."""

    total_tasks_with_failures: int
    pending_retries: list[PendingRetry]
    resolved_tasks: int
    retried_tasks: int
    rerouted_tasks: int
    escalated_tasks: int

    @property
    def dropped_count(self) -> int:
        """Number of tasks with failures but no follow-up action."""
        return len(self.pending_retries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tasks_with_failures": self.total_tasks_with_failures,
            "pending_retries": [p.to_dict() for p in self.pending_retries],
            "resolved_tasks": self.resolved_tasks,
            "retried_tasks": self.retried_tasks,
            "rerouted_tasks": self.rerouted_tasks,
            "escalated_tasks": self.escalated_tasks,
            "dropped_count": self.dropped_count,
        }


# Event types that resolve a task failure (no retry needed)
_RESOLUTION_EVENTS = frozenset(
    {
        "retry_attempted",
        "task_rerouted",
        "task_completed",
        "escalation",
    }
)

# Event types that count as follow-up actions (for summary stats)
_FOLLOWUP_EVENT_MAP: dict[str, str] = {
    "retry_attempted": "retried",
    "task_rerouted": "rerouted",
    "escalation": "escalated",
    "task_completed": "resolved",
}


def _extract_task_id(event: dict[str, Any]) -> str | None:
    """Extract a task identifier from an event's payload.

    Checks ``payload.task_id`` first, then ``payload.target``.
    Returns None if neither is present.
    """
    payload = event.get("payload", {})
    task_id = payload.get("task_id")
    if task_id is not None:
        return str(task_id)
    target = payload.get("target")
    if target is not None:
        return str(target)
    return None


def get_pending_retries(
    events: list[dict[str, Any]],
    *,
    max_age_hours: float | None = None,
) -> list[PendingRetry]:
    """Find tasks with ``task_failed`` events that lack follow-up.

    Scans the event list for tasks that have failed but have NOT had
    any of the following follow-up events for the same task_id:

    - ``retry_attempted`` — the task was retried
    - ``task_rerouted`` — the task was rerouted to another lane
    - ``task_completed`` — the task eventually succeeded
    - ``escalation`` — the failure was escalated

    Args:
        events: List of event dicts (from ``read_events``).
            Expected to be most-recent-first.
        max_age_hours: If set, only consider failures within this
            many hours. Older failures are ignored.

    Returns:
        List of PendingRetry objects, most recent first.
    """
    # Build a set of task_ids that have follow-up events
    resolved_task_ids: set[str] = set()
    for event in events:
        event_type = event.get("event_type", "")
        if event_type in _RESOLUTION_EVENTS:
            task_id = _extract_task_id(event)
            if task_id:
                resolved_task_ids.add(task_id)

    # Find unresolved task_failed events
    # Track per-task: accumulate failure count, keep most recent details
    task_failures: dict[str, dict[str, Any]] = {}
    cutoff: datetime | None = None

    if max_age_hours is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

    for event in events:
        if event.get("event_type") != "task_failed":
            continue

        task_id = _extract_task_id(event)
        if not task_id:
            continue

        # Skip resolved tasks
        if task_id in resolved_task_ids:
            continue

        # Apply age filter
        if cutoff is not None:
            try:
                event_time = datetime.fromisoformat(event["timestamp"])
                if event_time < cutoff:
                    continue
            except (KeyError, ValueError):
                continue

        if task_id not in task_failures:
            payload = event.get("payload", {})
            task_failures[task_id] = {
                "failure_count": 0,
                "last_failure_details": payload.get(
                    "details", payload.get("message", "unknown")
                ),
                "last_failure_lane": event.get("lane_id", "unknown"),
                "last_failure_timestamp": event.get("timestamp", ""),
            }

        task_failures[task_id]["failure_count"] += 1

    # Build PendingRetry list, ordered by most recent first
    pending = [
        PendingRetry(
            task_id=task_id,
            failure_count=info["failure_count"],
            last_failure_details=info["last_failure_details"],
            last_failure_lane=info["last_failure_lane"],
            last_failure_timestamp=info["last_failure_timestamp"],
        )
        for task_id, info in task_failures.items()
    ]

    # Sort by timestamp descending (most recent first)
    pending.sort(key=lambda p: p.last_failure_timestamp, reverse=True)
    return pending


def get_retry_summary(events: list[dict[str, Any]]) -> RetrySummary:
    """Aggregate retry/reroute/escalation state across all tasks.

    Provides a high-level view of retry follow-through: how many
    tasks have failures, how many were retried/rerouted/escalated,
    and how many are pending (dropped without follow-up).

    Args:
        events: List of event dicts (from ``read_events``).

    Returns:
        RetrySummary with aggregate counts.
    """
    # Collect all task_ids with failures
    failed_task_ids: set[str] = set()
    for event in events:
        if event.get("event_type") == "task_failed":
            task_id = _extract_task_id(event)
            if task_id:
                failed_task_ids.add(task_id)

    # Collect follow-up actions per task
    task_followups: dict[str, set[str]] = {tid: set() for tid in failed_task_ids}
    for event in events:
        event_type = event.get("event_type", "")
        action = _FOLLOWUP_EVENT_MAP.get(event_type)
        if not action:
            continue
        task_id = _extract_task_id(event)
        if task_id and task_id in task_followups:
            task_followups[task_id].add(action)

    # Count categories
    resolved = 0
    retried = 0
    rerouted = 0
    escalated = 0

    for actions in task_followups.values():
        if "resolved" in actions:
            resolved += 1
        if "retried" in actions:
            retried += 1
        if "rerouted" in actions:
            rerouted += 1
        if "escalated" in actions:
            escalated += 1

    # Pending retries: tasks with failures and NO follow-up at all
    pending = get_pending_retries(events)

    return RetrySummary(
        total_tasks_with_failures=len(failed_task_ids),
        pending_retries=pending,
        resolved_tasks=resolved,
        retried_tasks=retried,
        rerouted_tasks=rerouted,
        escalated_tasks=escalated,
    )


# --- Formatting ---


def format_pending_retries_text(pending: list[PendingRetry]) -> str:
    """Format pending retries as human-readable text."""
    if not pending:
        return (
            "=== Pending Retries ===\n\nNo pending retries. All failures followed up."
        )

    lines = ["=== Pending Retries ===", ""]
    lines.append(f"Tasks needing attention: {len(pending)}")
    lines.append("")

    for p in pending:
        lines.append(f"  Task: {p.task_id}")
        lines.append(f"    Failures: {p.failure_count}")
        lines.append(f"    Last failure: {p.last_failure_details}")
        lines.append(f"    Lane: {p.last_failure_lane}")
        lines.append(f"    Timestamp: {p.last_failure_timestamp}")
        lines.append("")

    return "\n".join(lines)


def format_retry_summary_text(summary: RetrySummary) -> str:
    """Format retry summary as human-readable text."""
    lines = ["=== Retry Follow-Through Summary ===", ""]
    lines.append(f"Tasks with failures: {summary.total_tasks_with_failures}")
    lines.append(f"  Resolved (completed): {summary.resolved_tasks}")
    lines.append(f"  Retried: {summary.retried_tasks}")
    lines.append(f"  Rerouted: {summary.rerouted_tasks}")
    lines.append(f"  Escalated: {summary.escalated_tasks}")
    lines.append(f"  Dropped (no follow-up): {summary.dropped_count}")

    if summary.pending_retries:
        lines.append("")
        lines.append("Dropped tasks:")
        for p in summary.pending_retries:
            lines.append(
                f"  ! {p.task_id} — {p.failure_count} failure(s), "
                f"last: {p.last_failure_details}"
            )

    return "\n".join(lines)


def format_retry_summary_json(summary: RetrySummary) -> dict[str, Any]:
    """Format retry summary as JSON-serializable dict."""
    return summary.to_dict()
