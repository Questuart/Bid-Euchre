"""Failure classification and recovery templates.

Provides structured guidance for common operational failures:
CI failures, stuck tasks, stale heartbeats, quarantined worktrees, and
escalations. Each failure type maps to a recovery template with
human-readable steps.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.recovery")


@dataclass
class RecoveryTemplate:
    """A named recovery procedure for a failure category."""

    name: str
    description: str
    steps: list[str]
    auto_remediable: bool


@dataclass
class FailureClassification:
    """Classification of a single failure event."""

    failure_type: str  # matches event_type or category
    severity: str  # "critical" | "warning" | "info"
    target: str  # what failed (lane_id, PR number, worktree path)
    details: str  # human-readable description
    template: RecoveryTemplate | None = None


# ---------------------------------------------------------------------------
# Recovery template catalog
# ---------------------------------------------------------------------------

RECOVERY_TEMPLATES: dict[str, RecoveryTemplate] = {
    "ci_failure": RecoveryTemplate(
        name="CI Failure",
        description="CI check failed on a PR",
        steps=[
            "Run `ruff check --fix` on changed files",
            "Run `ruff format` on changed files",
            "Run `uv run python -m pytest tests/unit/ -x` to check tests",
            "Commit fixes and push",
        ],
        auto_remediable=True,
    ),
    "task_failed": RecoveryTemplate(
        name="Task Failure",
        description="A task failed during execution",
        steps=[
            "Check task state file for error details",
            "Review event log for related failures",
            "Retry the task or reroute to a different lane",
            "If repeated failures, escalate to human operator",
        ],
        auto_remediable=False,
    ),
    "task_blocked": RecoveryTemplate(
        name="Task Blocked",
        description="A task is blocked by an unresolved dependency",
        steps=[
            "Check blocked_by field in task state",
            "Resolve the blocking dependency",
            "If blocker is external, skip to next non-dependent task",
            "Update task state to in_progress once unblocked",
        ],
        auto_remediable=False,
    ),
    "heartbeat_stale": RecoveryTemplate(
        name="Stale Heartbeat",
        description="An agent's heartbeat file is older than the threshold",
        steps=[
            "Check if the agent process is still running",
            "If dead, respawn the agent with the same task scope",
            "If alive but unresponsive, check for context exhaustion",
            "Update heartbeat file after recovery",
        ],
        auto_remediable=False,
    ),
    "worktree_quarantined": RecoveryTemplate(
        name="Quarantined Worktree",
        description="A stale worktree has uncommitted changes",
        steps=[
            "Review the saved diff in .claude/runtime/worktree_quarantine/",
            "Commit valuable changes or discard them",
            "Archive the worktree via `ops.py worktrees archive <path>`",
        ],
        auto_remediable=False,
    ),
    "escalation": RecoveryTemplate(
        name="Escalation",
        description="An issue requires human operator attention",
        steps=[
            "Read the escalation event payload for context",
            "Human decision required — no automated recovery available",
        ],
        auto_remediable=False,
    ),
}

# Map event types to failure severity defaults
_SEVERITY_MAP: dict[str, str] = {
    "ci_failure": "warning",
    "task_failed": "warning",
    "task_blocked": "warning",
    "heartbeat_stale": "critical",
    "worktree_quarantined": "warning",
    "escalation": "critical",
}

# Event types that represent active failures needing attention
_FAILURE_EVENT_TYPES = frozenset(
    {
        "ci_failure",
        "task_failed",
        "task_blocked",
        "heartbeat_stale",
        "worktree_quarantined",
        "escalation",
    }
)

# Maps resolution event types to the failure types they resolve.
# Used by get_active_failures() to exclude resolved failures.
_RESOLUTION_MAP: dict[str, frozenset[str]] = {
    "ci_success": frozenset({"ci_failure"}),
    "task_completed": frozenset({"task_failed", "task_blocked"}),
    "heartbeat_ok": frozenset({"heartbeat_stale"}),
    "worktree_archived": frozenset({"worktree_quarantined"}),
    "recovery_action": frozenset({"escalation"}),
}


def classify_failure(event: dict[str, Any]) -> FailureClassification:
    """Classify a single event into a failure with recovery guidance.

    Args:
        event: An event dict from the event log.

    Returns:
        FailureClassification with severity and recovery template.
    """
    event_type = event.get("event_type", "unknown")
    lane_id = event.get("lane_id", "unknown")
    payload = event.get("payload", {})

    # Determine target from payload or lane
    target = payload.get("target", lane_id)

    # Build details string
    details = payload.get("details", payload.get("message", f"{event_type} event"))

    # Look up template and severity
    template = RECOVERY_TEMPLATES.get(event_type)
    severity = _SEVERITY_MAP.get(event_type, "info")

    return FailureClassification(
        failure_type=event_type,
        severity=severity,
        target=str(target),
        details=str(details),
        template=template,
    )


def _resolution_target(event: dict[str, Any]) -> str:
    """Extract the resolution-matching target from an event.

    Uses ``payload.target`` if present, falling back to ``lane_id``.
    This key is used to correlate failure events with their resolutions.
    """
    payload = event.get("payload", {})
    return str(payload.get("target", event.get("lane_id", "unknown")))


def get_active_failures(
    events_dir: Path,
    *,
    limit: int = 50,
) -> list[FailureClassification]:
    """Read recent events and return only unresolved failures.

    Scans recent events (newest-first) and correlates failure events with
    resolution events by target. A failure is considered resolved when a
    matching resolution event (e.g., ``ci_success`` for ``ci_failure``)
    exists with a later timestamp for the same target.

    Resolution pairs (defined in ``_RESOLUTION_MAP``):
    - ``ci_failure`` ← ``ci_success``
    - ``task_failed`` / ``task_blocked`` ← ``task_completed``
    - ``heartbeat_stale`` ← ``heartbeat_ok``
    - ``worktree_quarantined`` ← ``worktree_archived``
    - ``escalation`` ← ``recovery_action``

    Args:
        events_dir: Path to the events directory.
        limit: Maximum number of events to scan.

    Returns:
        List of FailureClassification objects for unresolved failures,
        most recent first.
    """
    from bid_euchre.ops.events import read_events

    events = read_events(events_dir, limit=limit)

    # Walk events newest-first. Resolution events mark (failure_type, target)
    # as resolved. Only failure events whose key is NOT resolved are returned.
    resolved_keys: set[tuple[str, str]] = set()
    failures: list[FailureClassification] = []

    for event in events:
        event_type = event.get("event_type", "")
        target = _resolution_target(event)

        # If this is a resolution event, mark the corresponding failure
        # types as resolved for this target.
        resolved_failure_types = _RESOLUTION_MAP.get(event_type, frozenset())
        for ft in resolved_failure_types:
            resolved_keys.add((ft, target))

        # If this is a failure event, only include if not yet resolved.
        if event_type in _FAILURE_EVENT_TYPES:
            if (event_type, target) not in resolved_keys:
                failures.append(classify_failure(event))

    return failures


def format_recovery_text(failures: list[FailureClassification]) -> str:
    """Format failures as human-readable text.

    Args:
        failures: List of classified failures.

    Returns:
        Multi-line text summary with recovery steps.
    """
    if not failures:
        return "=== Recovery Guidance ===\n\nNo active failures. All clear."

    lines: list[str] = []
    lines.append("=== Recovery Guidance ===")
    lines.append("")
    lines.append(f"Active failures: {len(failures)}")
    lines.append("")

    for i, failure in enumerate(failures, 1):
        severity_icon = {"critical": "!!!", "warning": "!!", "info": "i"}.get(
            failure.severity, "?"
        )
        lines.append(f"  [{severity_icon}] {failure.failure_type}: {failure.details}")
        lines.append(f"      Target: {failure.target}")
        if failure.template:
            lines.append(f"      Recovery ({failure.template.name}):")
            for step_num, step in enumerate(failure.template.steps, 1):
                lines.append(f"        {step_num}. {step}")
        if i < len(failures):
            lines.append("")

    return "\n".join(lines)


def format_recovery_json(
    failures: list[FailureClassification],
) -> list[dict[str, Any]]:
    """Format failures as JSON-serializable list.

    Args:
        failures: List of classified failures.

    Returns:
        List of dicts suitable for JSON serialization.
    """
    return [
        {
            "failure_type": f.failure_type,
            "severity": f.severity,
            "target": f.target,
            "details": f.details,
            "template": {
                "name": f.template.name,
                "description": f.template.description,
                "steps": f.template.steps,
                "auto_remediable": f.template.auto_remediable,
            }
            if f.template
            else None,
        }
        for f in failures
    ]
