"""Watchdog rules for health and progress monitoring.

Detects stale heartbeats, stuck tasks, worktree issues, and other
conditions that indicate autonomous work needs attention.
"""

from __future__ import annotations

import json
import logging
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


def run_all_watchdogs(
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    *,
    heartbeat_staleness_minutes: int = 5,
    task_staleness_minutes: int = 30,
    now: datetime | None = None,
    checks: set[str] | None = None,
) -> list[WatchdogFinding]:
    """Run watchdog checks and return combined findings.

    Args:
        runtime_dir: Runtime directory root.
        plans_dir: Plans directory for heartbeat scanning.
        heartbeat_staleness_minutes: Threshold for heartbeat checks.
        task_staleness_minutes: Threshold for task progress checks.
        now: Override current time for testing.
        checks: Set of check names to run. If None, runs all.
            Valid names: ``"heartbeats"``, ``"task_progress"``,
            ``"worktree_health"``.

    Returns:
        Combined list of all watchdog findings, sorted by severity.
    """
    all_checks = {"heartbeats", "task_progress", "worktree_health"}
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
