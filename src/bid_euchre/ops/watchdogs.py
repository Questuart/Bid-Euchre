"""Watchdog rules for health and progress monitoring.

Detects stale heartbeats, stuck tasks, worktree issues, CI stuck states,
repeated sub-agent failures, scope drift, and other conditions that
indicate autonomous work needs attention.
"""

from __future__ import annotations

import fnmatch
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.watchdogs")


@dataclass
class WatchdogFinding:
    """A single watchdog detection result."""

    watchdog_name: str
    severity: str  # "critical", "warning", "info"
    target: str  # what was checked (lane, process, worktree path)
    message: str
    threshold: str  # what threshold fired (e.g., "5 min staleness")
    recommended_action: str


def check_heartbeats(
    plans_dir: Path | None = None,
    *,
    staleness_minutes: int = 5,
    now: datetime | None = None,
) -> list[WatchdogFinding]:
    """Check for stale or missing heartbeat files.

    Scans ``plans/**/heartbeat`` files for timestamps older than
    the staleness threshold.

    Args:
        plans_dir: Root plans directory to scan. Defaults to ``plans/``.
        staleness_minutes: Minutes after which a heartbeat is considered stale.
        now: Override current time for testing.

    Returns:
        List of findings for stale heartbeats.
    """
    if plans_dir is None:
        plans_dir = Path("plans")

    if now is None:
        now = datetime.now(timezone.utc)

    findings: list[WatchdogFinding] = []

    for hb_file in plans_dir.rglob("heartbeat"):
        try:
            content = hb_file.read_text().strip()
            if not content:
                findings.append(
                    WatchdogFinding(
                        watchdog_name="heartbeat_check",
                        severity="warning",
                        target=str(hb_file),
                        message="Empty heartbeat file",
                        threshold=f"{staleness_minutes}min",
                        recommended_action="Check if the process is still running",
                    )
                )
                continue

            # Try ISO 8601 first, then epoch
            try:
                hb_time = datetime.fromisoformat(content)
            except ValueError:
                try:
                    hb_time = datetime.fromtimestamp(float(content), tz=timezone.utc)
                except (ValueError, OSError):
                    findings.append(
                        WatchdogFinding(
                            watchdog_name="heartbeat_check",
                            severity="warning",
                            target=str(hb_file),
                            message=f"Unparseable heartbeat: {content[:50]}",
                            threshold=f"{staleness_minutes}min",
                            recommended_action="Inspect heartbeat file format",
                        )
                    )
                    continue

            if hb_time.tzinfo is None:
                hb_time = hb_time.replace(tzinfo=timezone.utc)

            age_minutes = (now - hb_time).total_seconds() / 60

            if age_minutes > staleness_minutes:
                findings.append(
                    WatchdogFinding(
                        watchdog_name="heartbeat_check",
                        severity="critical",
                        target=str(hb_file),
                        message=(
                            f"Stale heartbeat: {age_minutes:.0f}min old "
                            f"(threshold: {staleness_minutes}min)"
                        ),
                        threshold=f"{staleness_minutes}min",
                        recommended_action=(
                            "Check if the owning process is alive. "
                            "Respawn if stale >5min per agent reliability rules."
                        ),
                    )
                )

        except OSError as e:
            findings.append(
                WatchdogFinding(
                    watchdog_name="heartbeat_check",
                    severity="warning",
                    target=str(hb_file),
                    message=f"Cannot read heartbeat: {e}",
                    threshold=f"{staleness_minutes}min",
                    recommended_action="Check file permissions",
                )
            )

    return findings


def check_task_progress(
    runtime_dir: Path | None = None,
    *,
    staleness_minutes: int = 30,
    now: datetime | None = None,
) -> list[WatchdogFinding]:
    """Check for tasks without recent forward progress.

    Reads ``task_state/*.json`` and checks ``progress.last_forward_progress_at``.

    Args:
        runtime_dir: Runtime directory root.
        staleness_minutes: Minutes after which a task is considered stalled.
        now: Override current time for testing.

    Returns:
        List of findings for stalled tasks.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    if now is None:
        now = datetime.now(timezone.utc)

    findings: list[WatchdogFinding] = []
    task_dir = runtime_dir / "task_state"

    if not task_dir.exists():
        return findings

    for f in task_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status", "")
        if status != "in_progress":
            continue

        progress = data.get("progress")
        if progress is None:
            findings.append(
                WatchdogFinding(
                    watchdog_name="task_progress_check",
                    severity="warning",
                    target=data.get("task_id", f.stem),
                    message=(
                        f"In-progress task {data.get('subject', '?')!r} "
                        f"has no progress tracking"
                    ),
                    threshold=f"{staleness_minutes}min",
                    recommended_action="Update task progress fields",
                )
            )
            continue

        last_progress_str = progress.get("last_forward_progress_at")
        if not last_progress_str:
            findings.append(
                WatchdogFinding(
                    watchdog_name="task_progress_check",
                    severity="warning",
                    target=data.get("task_id", f.stem),
                    message=(
                        f"In-progress task {data.get('subject', '?')!r} "
                        f"has no last_forward_progress_at"
                    ),
                    threshold=f"{staleness_minutes}min",
                    recommended_action="Update progress.last_forward_progress_at",
                )
            )
            continue

        try:
            last_progress = datetime.fromisoformat(last_progress_str)
            if last_progress.tzinfo is None:
                last_progress = last_progress.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        age_minutes = (now - last_progress).total_seconds() / 60

        if age_minutes > staleness_minutes:
            blocker = progress.get("current_blocker")
            if blocker:
                severity = "warning"
                msg = (
                    f"Task {data.get('subject', '?')!r} stalled for "
                    f"{age_minutes:.0f}min (blocked: {blocker})"
                )
                action = "Resolve blocker or escalate"
            else:
                severity = "critical"
                msg = (
                    f"Task {data.get('subject', '?')!r} stalled for "
                    f"{age_minutes:.0f}min with no reported blocker"
                )
                action = (
                    "Check if the owning lane is alive and making progress. "
                    "Consider rerouting to another lane."
                )

            findings.append(
                WatchdogFinding(
                    watchdog_name="task_progress_check",
                    severity=severity,
                    target=data.get("task_id", f.stem),
                    message=msg,
                    threshold=f"{staleness_minutes}min",
                    recommended_action=action,
                )
            )

    return findings


def check_worktree_health(
    runtime_dir: Path | None = None,
) -> list[WatchdogFinding]:
    """Check for worktree health issues.

    Detects unregistered, missing, and orphaned worktrees by reconciling
    the registry with ``git worktree list``.

    Args:
        runtime_dir: Runtime directory root.

    Returns:
        List of findings for worktree issues.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    from bid_euchre.ops.worktrees import (
        list_worktrees_git,
        list_worktrees_registry,
        reconcile,
    )

    findings: list[WatchdogFinding] = []

    git_wts = list_worktrees_git()
    registry = list_worktrees_registry(runtime_dir / "worktree_registry")
    report = reconcile(git_wts, registry)

    for wt in report.unregistered:
        findings.append(
            WatchdogFinding(
                watchdog_name="worktree_health",
                severity="warning",
                target=wt.path,
                message=f"Unregistered worktree: {wt.branch}",
                threshold="n/a",
                recommended_action=(
                    "Register in worktree_registry or remove with "
                    "`ops.py worktrees prune`"
                ),
            )
        )

    for entry in report.missing:
        findings.append(
            WatchdogFinding(
                watchdog_name="worktree_health",
                severity="warning",
                target=entry.get("lane_id", "?"),
                message=(
                    f"Registry entry points to {entry.get('worktree_path', '?')} "
                    f"but no git worktree exists"
                ),
                threshold="n/a",
                recommended_action="Remove stale registry entry or recreate worktree",
            )
        )

    return findings


def check_ci_stuck(
    runtime_dir: Path | None = None,
    *,
    stuck_minutes: int = 30,
    now: datetime | None = None,
) -> list[WatchdogFinding]:
    """Check for PRs with CI stuck pending or failing beyond threshold.

    Reads the event log for ``ci_failure`` events. For each PR, checks
    whether the most recent CI event is a failure older than the threshold
    without a subsequent ``ci_success`` event.

    Args:
        runtime_dir: Runtime directory root.
        stuck_minutes: Minutes after which stuck CI is flagged.
        now: Override current time for testing.

    Returns:
        List of findings for stuck CI.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    if now is None:
        now = datetime.now(timezone.utc)

    from bid_euchre.ops.events import read_events

    events_dir = runtime_dir / "events"
    events = read_events(events_dir, limit=200)

    # Build per-PR timeline: track latest CI event
    # Events are most-recent-first from read_events
    pr_latest: dict[int, dict[str, Any]] = {}

    for event in events:
        event_type = event.get("event_type", "")
        if event_type not in ("ci_failure", "ci_success"):
            continue

        payload = event.get("payload", {})
        pr_num = payload.get("pr_number")
        if pr_num is None:
            continue

        pr_num = int(pr_num)
        # Only keep the most recent event per PR (first seen = most recent)
        if pr_num not in pr_latest:
            pr_latest[pr_num] = event

    findings: list[WatchdogFinding] = []

    for pr_num, event in pr_latest.items():
        if event.get("event_type") != "ci_failure":
            continue

        try:
            event_time = datetime.fromisoformat(event["timestamp"])
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue

        age_minutes = (now - event_time).total_seconds() / 60

        if age_minutes > stuck_minutes:
            payload = event.get("payload", {})
            failure_class = payload.get("failure_class", "unknown")
            findings.append(
                WatchdogFinding(
                    watchdog_name="ci_stuck_check",
                    severity="warning",
                    target=f"PR #{pr_num}",
                    message=(
                        f"CI stuck failing on PR #{pr_num} for "
                        f"{age_minutes:.0f}min ({failure_class})"
                    ),
                    threshold=f"{stuck_minutes}min",
                    recommended_action=(
                        "Check CI logs. If auto-remediable (lint/test), "
                        "retry. If infrastructure, escalate."
                    ),
                )
            )

    return findings


def check_subagent_failures(
    runtime_dir: Path | None = None,
    *,
    max_failures: int = 3,
) -> list[WatchdogFinding]:
    """Check for repeated task failures from the same lane/task.

    Reads the event log for ``task_failed`` events and groups them by
    the ``(lane_id, task_id)`` key from the event payload. Flags when
    the failure count meets or exceeds ``max_failures``.

    Args:
        runtime_dir: Runtime directory root.
        max_failures: Failure count threshold for flagging.

    Returns:
        List of findings for repeated failures.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    from bid_euchre.ops.events import read_events

    events_dir = runtime_dir / "events"
    events = read_events(events_dir, event_type="task_failed", limit=200)

    # Group failures by (lane_id, task_id)
    failure_counts: dict[tuple[str, str], int] = defaultdict(int)
    failure_details: dict[tuple[str, str], str] = {}

    for event in events:
        lane_id = event.get("lane_id", "unknown")
        payload = event.get("payload", {})
        task_id = payload.get("task_id", payload.get("target", "unknown"))
        key = (lane_id, str(task_id))
        failure_counts[key] += 1
        # Keep the most recent failure detail (events are most-recent-first)
        if key not in failure_details:
            failure_details[key] = payload.get(
                "details", payload.get("message", "unknown error")
            )

    findings: list[WatchdogFinding] = []

    for (lane_id, task_id), count in failure_counts.items():
        if count >= max_failures:
            details = failure_details.get((lane_id, task_id), "")
            severity = "critical" if count >= max_failures * 2 else "warning"

            findings.append(
                WatchdogFinding(
                    watchdog_name="subagent_failure_check",
                    severity=severity,
                    target=f"{lane_id}:{task_id}",
                    message=(
                        f"Task {task_id!r} on lane {lane_id!r} has failed "
                        f"{count} times (threshold: {max_failures}). "
                        f"Last error: {details}"
                    ),
                    threshold=f"{max_failures} failures",
                    recommended_action=(
                        "Reroute task to a persistent lane. If already on a "
                        "persistent lane, escalate to human operator."
                    ),
                )
            )

    return findings


def check_scope_drift(
    runtime_dir: Path | None = None,
) -> list[WatchdogFinding]:
    """Check for tasks whose file changes exceed their declared scope.

    Reads ``task_state/*.json`` files for in-progress tasks that have both
    ``scope.declared_files`` (list of glob patterns) and
    ``scope.touched_files`` (list of actually modified file paths).
    Flags when touched files don't match any declared pattern.

    Args:
        runtime_dir: Runtime directory root.

    Returns:
        List of findings for scope drift.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    findings: list[WatchdogFinding] = []
    task_dir = runtime_dir / "task_state"

    if not task_dir.exists():
        return findings

    for f in task_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        status = data.get("status", "")
        if status != "in_progress":
            continue

        scope = data.get("scope")
        if not scope or not isinstance(scope, dict):
            continue

        declared = scope.get("declared_files", [])
        touched = scope.get("touched_files", [])

        if not declared or not touched:
            continue

        # Check each touched file against declared patterns
        out_of_scope: list[str] = []
        for touched_file in touched:
            matched = any(
                fnmatch.fnmatch(touched_file, pattern) for pattern in declared
            )
            if not matched:
                out_of_scope.append(touched_file)

        if out_of_scope:
            task_id = data.get("task_id", f.stem)
            subject = data.get("subject", "?")
            lane_id = data.get("lane_id", "unknown")

            # Limit displayed files to avoid flooding
            displayed = out_of_scope[:5]
            suffix = (
                f" (+{len(out_of_scope) - 5} more)" if len(out_of_scope) > 5 else ""
            )
            file_list = ", ".join(displayed) + suffix

            findings.append(
                WatchdogFinding(
                    watchdog_name="scope_drift_check",
                    severity="warning",
                    target=f"{lane_id}:{task_id}",
                    message=(
                        f"Task {subject!r} on {lane_id} touched files "
                        f"outside declared scope: {file_list}"
                    ),
                    threshold="declared_files scope",
                    recommended_action=(
                        "Review whether the scope change is intentional. "
                        "If not, revert out-of-scope changes and log "
                        "follow-up work."
                    ),
                )
            )

    return findings


def run_all_watchdogs(
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    *,
    heartbeat_staleness_minutes: int = 5,
    task_staleness_minutes: int = 30,
    ci_stuck_minutes: int = 30,
    subagent_max_failures: int = 3,
    now: datetime | None = None,
    checks: set[str] | None = None,
) -> list[WatchdogFinding]:
    """Run watchdog checks and return combined findings.

    Args:
        runtime_dir: Runtime directory root.
        plans_dir: Plans directory for heartbeat scanning.
        heartbeat_staleness_minutes: Threshold for heartbeat checks.
        task_staleness_minutes: Threshold for task progress checks.
        ci_stuck_minutes: Threshold for CI stuck detection.
        subagent_max_failures: Failure count threshold for sub-agent checks.
        now: Override current time for testing.
        checks: Set of check names to run. If None, runs all.
            Valid names: ``"heartbeats"``, ``"task_progress"``,
            ``"worktree_health"``, ``"ci_stuck"``,
            ``"subagent_failures"``, ``"scope_drift"``.

    Returns:
        Combined list of all watchdog findings, sorted by severity.
    """
    all_checks = {
        "heartbeats",
        "task_progress",
        "worktree_health",
        "ci_stuck",
        "subagent_failures",
        "scope_drift",
    }
    active = checks if checks is not None else all_checks

    findings: list[WatchdogFinding] = []

    if "heartbeats" in active:
        findings.extend(
            check_heartbeats(
                plans_dir, staleness_minutes=heartbeat_staleness_minutes, now=now
            )
        )
    if "task_progress" in active:
        findings.extend(
            check_task_progress(
                runtime_dir, staleness_minutes=task_staleness_minutes, now=now
            )
        )
    if "worktree_health" in active:
        findings.extend(check_worktree_health(runtime_dir))
    if "ci_stuck" in active:
        findings.extend(
            check_ci_stuck(runtime_dir, stuck_minutes=ci_stuck_minutes, now=now)
        )
    if "subagent_failures" in active:
        findings.extend(
            check_subagent_failures(runtime_dir, max_failures=subagent_max_failures)
        )
    if "scope_drift" in active:
        findings.extend(check_scope_drift(runtime_dir))

    # Sort: critical first, then warning, then info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    findings.sort(key=lambda f: severity_order.get(f.severity, 3))

    return findings


def format_watchdog_text(findings: list[WatchdogFinding]) -> str:
    """Format watchdog findings as human-readable text."""
    if not findings:
        return "Watchdogs: all clear"

    lines = [f"Watchdogs: {len(findings)} finding(s)"]
    for f in findings:
        icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity, "⚪")
        lines.append(f"  {icon} [{f.severity.upper()}] {f.message}")
        lines.append(f"     → {f.recommended_action}")

    return "\n".join(lines)


def format_watchdog_json(findings: list[WatchdogFinding]) -> list[dict[str, Any]]:
    """Format watchdog findings as JSON-serializable dicts."""
    return [
        {
            "watchdog_name": f.watchdog_name,
            "severity": f.severity,
            "target": f.target,
            "message": f.message,
            "threshold": f.threshold,
            "recommended_action": f.recommended_action,
        }
        for f in findings
    ]
