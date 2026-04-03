"""Failure classification, recovery templates, and retry/reroute policy.

Provides structured guidance for common operational failures:
CI failures, stuck tasks, stale heartbeats, quarantined worktrees, and
escalations. Each failure type maps to a recovery template with
human-readable steps.

The retry/reroute policy engine evaluates failure history for a task and
recommends: retry (under cap), reroute (at cap), or escalate (over cap).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
    "auth_failure": RecoveryTemplate(
        name="Auth Failure",
        description="Codex CLI or review tool authentication expired or invalid",
        steps=[
            "Run `codex login status` to check current auth state",
            "If expired, run `codex login` interactively to refresh tokens",
            "Verify with `codex login status` after re-authentication",
            "Re-trigger the review: `python scripts/internal/review_driver.py "
            "--pr <N> --trigger manual`",
        ],
        auto_remediable=False,
    ),
    "review_lane_stall": RecoveryTemplate(
        name="Review Lane Stall",
        description="The review lane agent is stuck (detached HEAD, stale lock, "
        "or permission prompt)",
        steps=[
            "Check review lane worktree state: "
            "`git -C ../Bid-Euchre-steward-review status`",
            "If detached HEAD: "
            "`git -C ../Bid-Euchre-steward-review checkout main && "
            "git -C ../Bid-Euchre-steward-review pull`",
            "Remove stale lock files: "
            "`rm -f ../Bid-Euchre-steward-review/.claude/scheduled_tasks.lock`",
            "Clear the review lane session: "
            "`tmux send-keys -t steward:review '/clear' Enter`",
            "Re-nudge the review lane or restart the runner: "
            "`python scripts/internal/review_lane_runner.py --once`",
        ],
        auto_remediable=True,
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
    "auth_failure": "warning",
    "review_lane_stall": "warning",
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
        "auth_failure",
        "review_lane_stall",
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
    "auth_recovered": frozenset({"auth_failure"}),
    "review_lane_recovered": frozenset({"review_lane_stall"}),
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

    # Determine target: explicit target > worktree_path > lane_id
    target = payload.get("target")
    if target is None:
        target = payload.get("worktree_path", lane_id)

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

    Uses ``payload.target`` if present, then ``payload.worktree_path``
    for worktree-related events, falling back to ``lane_id``.
    This key is used to correlate failure events with their resolutions.

    The ``worktree_path`` fallback ensures that worktree events
    (``worktree_quarantined`` / ``worktree_archived``) are matched by
    the specific worktree rather than the lane, since a single lane can
    own multiple worktrees.
    """
    payload = event.get("payload", {})
    target = payload.get("target")
    if target is not None:
        return str(target)
    # Worktree events: prefer worktree_path as matching key
    wt_path = payload.get("worktree_path")
    if wt_path:
        return str(wt_path)
    return str(event.get("lane_id", "unknown"))


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


# ---------------------------------------------------------------------------
# Retry / Reroute Policy Engine
# ---------------------------------------------------------------------------

# Persistent lanes that can accept rerouted work
PERSISTENT_LANES: tuple[str, ...] = (
    # Platform pool
    "author-a",
    "author-b",
    "author-c",
    "author-d",
    # Browser-game pool
    "brws-author-a",
    "brws-author-b",
    "brws-author-c",
    "brws-author-d",
    # Analyst pool
    "analyst-a",
    "analyst-b",
    "analyst-c",
    "analyst-d",
    # Flex pool
    "flex-a",
    "flex-b",
    "flex-c",
    "flex-d",
)

# Default retry cap per task
DEFAULT_MAX_RETRIES: int = 3


@dataclass
class RetryPolicy:
    """Retry/reroute decision for a task based on failure history."""

    task_id: str
    retry_count: int
    max_retries: int
    last_failure: str  # most recent failure details
    action: str  # "retry", "reroute", "escalate"
    reroute_to: str | None = None  # lane_id for reroute target
    failure_lane: str | None = None  # lane where failures occurred
    reasons: list[str] = field(default_factory=list)


def evaluate_retry_policy(
    task_id: str,
    events: list[dict[str, Any]],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    current_lane: str | None = None,
) -> RetryPolicy:
    """Evaluate retry/reroute policy for a task based on its failure history.

    Counts ``task_failed`` events for the given task and decides:
    - **retry** if failure count < max_retries
    - **reroute** if failure count == max_retries (move to different persistent lane)
    - **escalate** if failure count > max_retries (human attention needed)

    Args:
        task_id: The task identifier to evaluate.
        events: List of event dicts (from ``read_events``).
        max_retries: Maximum retry attempts before reroute.
        current_lane: Lane where the task is currently running (used to
            pick a different reroute target).

    Returns:
        RetryPolicy with the recommended action.
    """
    # Count failures for this specific task
    failure_count = 0
    last_failure = "unknown"
    failure_lane = current_lane

    for event in events:
        if event.get("event_type") != "task_failed":
            continue
        payload = event.get("payload", {})
        event_task_id = payload.get("task_id", payload.get("target", ""))

        if str(event_task_id) != str(task_id):
            continue

        failure_count += 1
        # Events are most-recent-first; capture first (= most recent) failure
        if failure_count == 1:
            last_failure = payload.get(
                "details", payload.get("message", "unknown error")
            )
            failure_lane = event.get("lane_id", current_lane)

    # Decide action
    reasons: list[str] = []

    if failure_count < max_retries:
        action = "retry"
        reasons.append(
            f"Failure count ({failure_count}) below retry cap ({max_retries})"
        )
        reroute_to = None

    elif failure_count == max_retries:
        action = "reroute"
        reasons.append(
            f"Failure count ({failure_count}) reached retry cap ({max_retries})"
        )
        reasons.append("Rerouting to a different persistent lane")
        reroute_to = _pick_reroute_target(current_lane)

    else:
        action = "escalate"
        reasons.append(
            f"Failure count ({failure_count}) exceeds retry cap ({max_retries})"
        )
        reasons.append("Human operator attention required")
        reroute_to = None

    return RetryPolicy(
        task_id=task_id,
        retry_count=failure_count,
        max_retries=max_retries,
        last_failure=last_failure,
        action=action,
        reroute_to=reroute_to,
        failure_lane=failure_lane,
        reasons=reasons,
    )


def _pick_reroute_target(current_lane: str | None) -> str | None:
    """Pick a persistent lane to reroute work to, avoiding the current lane.

    Args:
        current_lane: The lane to avoid.

    Returns:
        A different persistent lane, or the first available if current is
        not in the persistent list.
    """
    for lane in PERSISTENT_LANES:
        if lane != current_lane:
            return lane
    # Fallback: if all lanes are the same as current (shouldn't happen)
    return PERSISTENT_LANES[0] if PERSISTENT_LANES else None


def format_retry_policy_text(policy: RetryPolicy) -> str:
    """Format a RetryPolicy as human-readable text."""
    lines = ["=== Retry/Reroute Policy ===", ""]
    lines.append(f"Task: {policy.task_id}")
    lines.append(f"Failures: {policy.retry_count} / {policy.max_retries} max")
    lines.append(f"Action: {policy.action.upper()}")
    if policy.failure_lane:
        lines.append(f"Failure lane: {policy.failure_lane}")
    if policy.reroute_to:
        lines.append(f"Reroute to: {policy.reroute_to}")
    lines.append(f"Last failure: {policy.last_failure}")
    if policy.reasons:
        lines.append("")
        lines.append("Reasons:")
        for reason in policy.reasons:
            lines.append(f"  - {reason}")
    return "\n".join(lines)


def format_retry_policy_json(policy: RetryPolicy) -> dict[str, Any]:
    """Format a RetryPolicy as JSON-serializable dict."""
    return {
        "task_id": policy.task_id,
        "retry_count": policy.retry_count,
        "max_retries": policy.max_retries,
        "last_failure": policy.last_failure,
        "action": policy.action,
        "reroute_to": policy.reroute_to,
        "failure_lane": policy.failure_lane,
        "reasons": policy.reasons,
    }


# ---------------------------------------------------------------------------
# Retry/Reroute Event Emission (#930)
# ---------------------------------------------------------------------------

# Module-level constant: maps RetryPolicy action names to event types.
_RETRY_EVENT_MAP: dict[str, str] = {
    "retry": "retry_attempted",
    "reroute": "task_rerouted",
    "escalate": "escalation",
}


def emit_retry_event(
    policy: RetryPolicy,
    lane_id: str,
    events_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Emit a durable event based on a retry policy decision.

    Maps ``RetryPolicy.action`` to event types:

    - ``"retry"`` -> ``retry_attempted``
    - ``"reroute"`` -> ``task_rerouted``
    - ``"escalate"`` -> ``escalation``

    This function is the canonical producer for ``retry_attempted`` and
    ``task_rerouted`` events, which are consumed by watchdogs and the
    recovery guidance surface.

    Args:
        policy: The evaluated retry policy.
        lane_id: Canonical lane identity (e.g., ``"author-a"``).
        events_dir: Override for events directory. Defaults to
            ``.claude/runtime/events``.

    Returns:
        The emitted event dict, or None if the action has no matching
        event type.
    """
    from bid_euchre.ops.events import append_event

    event_type = _RETRY_EVENT_MAP.get(policy.action)
    if not event_type:
        return None

    payload: dict[str, str | int] = {
        "task_id": policy.task_id,
        "retry_count": policy.retry_count,
        "last_failure": policy.last_failure,
    }

    if policy.action == "reroute" and policy.reroute_to:
        payload["source_lane"] = lane_id
        payload["target_lane"] = policy.reroute_to

    if policy.action == "escalate":
        payload["details"] = (
            f"Task {policy.task_id} exceeded retry cap "
            f"({policy.retry_count} failures) — human attention required"
        )

    return append_event(
        event_type=event_type,
        source="ops.retry",
        lane_id=lane_id,
        payload=payload,
        events_dir=events_dir,
    )
