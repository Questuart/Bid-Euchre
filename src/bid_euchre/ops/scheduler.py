"""Periodic scheduler for ops tick loop and due-check logic.

The scheduler runs health checks on a configurable interval, emits
events for findings, and persists state so it can resume after session
restart without relying on session-only cron.

Storage: ``.claude/runtime/scheduler/state.json`` (gitignored)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.events import append_event
from bid_euchre.ops.watchdogs import (
    WatchdogFinding,
    run_all_watchdogs,
)

logger = logging.getLogger("ops.scheduler")

DEFAULT_SCHEDULER_DIR = Path(".claude/runtime/scheduler")

# Default checks to run each tick
DEFAULT_CHECKS = [
    "heartbeats",
    "task_progress",
    "worktree_health",
]


@dataclass
class SchedulerState:
    """Persisted scheduler state."""

    last_tick: str | None = None  # ISO 8601
    last_health_pass: str | None = None  # ISO 8601
    tick_count: int = 0
    due_checks: list[str] = field(default_factory=lambda: list(DEFAULT_CHECKS))
    last_error: str | None = None


@dataclass
class TickResult:
    """Result of one scheduler tick cycle."""

    checks_run: list[str]
    findings: list[WatchdogFinding]
    events_emitted: int
    errors: list[str]
    tick_number: int


def load_scheduler_state(
    scheduler_dir: Path | None = None,
) -> SchedulerState:
    """Load persisted scheduler state from disk.

    Args:
        scheduler_dir: Override for scheduler directory.

    Returns:
        SchedulerState. Returns default state if no file exists.
    """
    if scheduler_dir is None:
        scheduler_dir = DEFAULT_SCHEDULER_DIR

    state_file = scheduler_dir / "state.json"
    if not state_file.exists():
        return SchedulerState()

    try:
        data = json.loads(state_file.read_text())
        return SchedulerState(
            last_tick=data.get("last_tick"),
            last_health_pass=data.get("last_health_pass"),
            tick_count=data.get("tick_count", 0),
            due_checks=data.get("due_checks", list(DEFAULT_CHECKS)),
            last_error=data.get("last_error"),
        )
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Cannot load scheduler state: %s", e)
        return SchedulerState()


def save_scheduler_state(
    state: SchedulerState,
    scheduler_dir: Path | None = None,
) -> Path:
    """Save scheduler state to disk.

    Args:
        state: State to persist.
        scheduler_dir: Override for scheduler directory.

    Returns:
        Path to the state file.
    """
    if scheduler_dir is None:
        scheduler_dir = DEFAULT_SCHEDULER_DIR

    scheduler_dir.mkdir(parents=True, exist_ok=True)
    state_file = scheduler_dir / "state.json"
    state_file.write_text(json.dumps(asdict(state), indent=2))
    return state_file


def tick(
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    scheduler_dir: Path | None = None,
    events_dir: Path | None = None,
    *,
    now: datetime | None = None,
) -> TickResult:
    """Run one scheduler cycle.

    Steps:
    1. Load scheduler state
    2. Run all due health checks (watchdogs)
    3. Emit events for findings
    4. Update and save scheduler state
    5. Return summary

    Args:
        runtime_dir: Runtime directory root.
        plans_dir: Plans directory for heartbeat scanning.
        scheduler_dir: Scheduler state directory.
        events_dir: Events directory for emitting findings.
        now: Override current time for testing.

    Returns:
        TickResult with check results and findings.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    now_iso = now.isoformat()

    # 1. Load state
    state = load_scheduler_state(scheduler_dir)
    state.tick_count += 1

    result = TickResult(
        checks_run=[],
        findings=[],
        events_emitted=0,
        errors=[],
        tick_number=state.tick_count,
    )

    # 2. Run watchdogs (only those listed in due_checks)
    try:
        due = set(state.due_checks) if state.due_checks else set(DEFAULT_CHECKS)
        findings = run_all_watchdogs(runtime_dir, plans_dir, now=now, checks=due)
        result.findings = findings
        result.checks_run = sorted(due)
    except Exception as e:
        error_msg = f"Watchdog checks failed: {e}"
        logger.error(error_msg)
        result.errors.append(error_msg)
        state.last_error = error_msg
        state.last_tick = now_iso
        save_scheduler_state(state, scheduler_dir)
        return result

    # 3. Emit events for findings
    for finding in findings:
        try:
            append_event(
                event_type="watchdog_finding",
                source="ops.scheduler.tick",
                lane_id="ops",
                payload={
                    "watchdog_name": finding.watchdog_name,
                    "severity": finding.severity,
                    "target": finding.target,
                    "message": finding.message,
                    "recommended_action": finding.recommended_action,
                },
                events_dir=events_dir,
            )
            result.events_emitted += 1
        except Exception as e:
            logger.warning("Failed to emit event for finding: %s", e)

    # Also emit a tick event
    try:
        append_event(
            event_type="scheduler_tick",
            source="ops.scheduler.tick",
            lane_id="ops",
            payload={
                "tick_number": state.tick_count,
                "checks_run": result.checks_run,
                "findings_count": len(findings),
                "critical_count": sum(1 for f in findings if f.severity == "critical"),
            },
            events_dir=events_dir,
        )
        result.events_emitted += 1
    except Exception as e:
        logger.warning("Failed to emit tick event: %s", e)

    # 4. Update state
    state.last_tick = now_iso
    state.last_error = None

    if not any(f.severity == "critical" for f in findings):
        state.last_health_pass = now_iso

    save_scheduler_state(state, scheduler_dir)

    return result


def format_tick_text(result: TickResult) -> str:
    """Format a TickResult as human-readable text."""
    lines = [f"Tick #{result.tick_number}"]
    lines.append(f"  Checks: {', '.join(result.checks_run) or 'none'}")
    lines.append(f"  Findings: {len(result.findings)}")
    lines.append(f"  Events emitted: {result.events_emitted}")

    if result.errors:
        lines.append(f"  Errors: {len(result.errors)}")
        for e in result.errors:
            lines.append(f"    ✗ {e}")

    for f in result.findings:
        icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(f.severity, "⚪")
        lines.append(f"  {icon} {f.message}")

    return "\n".join(lines)


def format_tick_json(result: TickResult) -> dict[str, Any]:
    """Format a TickResult as JSON-serializable dict."""
    return {
        "tick_number": result.tick_number,
        "checks_run": result.checks_run,
        "findings_count": len(result.findings),
        "events_emitted": result.events_emitted,
        "errors": result.errors,
        "findings": [
            {
                "watchdog_name": f.watchdog_name,
                "severity": f.severity,
                "target": f.target,
                "message": f.message,
                "recommended_action": f.recommended_action,
            }
            for f in result.findings
        ],
    }
