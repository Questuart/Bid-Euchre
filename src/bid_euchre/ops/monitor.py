"""Ops monitoring cycle (SP-3-08).

Runs a single monitoring sweep across lane health, open PRs, CI status,
and stale dispatched packets.  Produces structured findings that are
optionally sent to the orchestrator inbox via the message bus.

Usage::

    from bid_euchre.ops.monitor import run_monitoring_cycle

    findings = run_monitoring_cycle()
    # findings is a list of MonitorFinding dataclasses

The CLI wrapper (``ops.py monitor``) calls this and formats the output.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.monitor")

# A dispatched packet with no progress after this many minutes is flagged.
STALE_DISPATCH_MINUTES: int = 30

# Severity levels for findings.
SEVERITY_INFO = "info"
SEVERITY_WARN = "warn"
SEVERITY_HIGH = "high"


@dataclass(frozen=True)
class MonitorFinding:
    """A single finding from one monitoring sweep."""

    category: str  # "lane_health", "pr_status", "ci_status", "stale_dispatch"
    severity: str  # "info", "warn", "high"
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def check_lane_health(
    runtime_dir: Path | None = None,
) -> list[MonitorFinding]:
    """Check lane pool health via a pool snapshot.

    Flags:
    - Lanes with ``pool_status == "active"`` but no tmux pane (degraded).
    - Lanes marked critical by the supervisor.
    - Summary of pool capacity.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        List of findings.
    """
    findings: list[MonitorFinding] = []
    try:
        from bid_euchre.ops.worker_pool import take_pool_snapshot

        pool = take_pool_snapshot(runtime_dir)
    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="lane_health",
                severity=SEVERITY_WARN,
                summary=f"Could not take pool snapshot: {exc}",
            )
        )
        return findings

    for worker in pool.workers:
        # Active lane with dead tmux pane
        if worker.pool_status == "active" and not worker.tmux_alive:
            findings.append(
                MonitorFinding(
                    category="lane_health",
                    severity=SEVERITY_HIGH,
                    summary=(
                        f"Lane {worker.lane_id!r} is active but tmux pane is dead"
                    ),
                    details={
                        "lane_id": worker.lane_id,
                        "task_id": worker.current_task_id,
                    },
                )
            )

        # Critical health from supervisor
        if worker.health == "critical":
            findings.append(
                MonitorFinding(
                    category="lane_health",
                    severity=SEVERITY_HIGH,
                    summary=f"Lane {worker.lane_id!r} health is critical",
                    details={"lane_id": worker.lane_id},
                )
            )

    # Capacity summary (info)
    findings.append(
        MonitorFinding(
            category="lane_health",
            severity=SEVERITY_INFO,
            summary=(
                f"Pool: {pool.active_count} active, {pool.idle_count} idle, "
                f"{pool.parked_count} parked, {pool.retired_count} retired, "
                f"capacity={pool.available_capacity}"
            ),
            details={
                "active": pool.active_count,
                "idle": pool.idle_count,
                "parked": pool.parked_count,
                "retired": pool.retired_count,
                "capacity": pool.available_capacity,
            },
        )
    )

    return findings


def check_open_prs() -> list[MonitorFinding]:
    """Check open PRs via ``gh pr list``.

    Flags:
    - PRs with failing checks.
    - PRs with merge conflicts.
    - Total count of open PRs.

    Returns:
        List of findings.
    """
    findings: list[MonitorFinding] = []

    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "open",
                "--json",
                "number,title,headRefName,statusCheckRollup,mergeable",
                "--limit",
                "20",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            findings.append(
                MonitorFinding(
                    category="pr_status",
                    severity=SEVERITY_WARN,
                    summary=f"gh pr list failed: {result.stderr[:200]}",
                )
            )
            return findings

        prs = json.loads(result.stdout) if result.stdout.strip() else []
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
        OSError,
        json.JSONDecodeError,
    ) as exc:
        findings.append(
            MonitorFinding(
                category="pr_status",
                severity=SEVERITY_WARN,
                summary=f"Could not check PRs: {exc}",
            )
        )
        return findings

    if not prs:
        findings.append(
            MonitorFinding(
                category="pr_status",
                severity=SEVERITY_INFO,
                summary="No open PRs.",
            )
        )
        return findings

    for pr in prs:
        pr_num = pr.get("number", "?")
        title = pr.get("title", "?")

        # Check for merge conflicts
        mergeable = pr.get("mergeable", "UNKNOWN")
        if mergeable == "CONFLICTING":
            findings.append(
                MonitorFinding(
                    category="pr_status",
                    severity=SEVERITY_HIGH,
                    summary=f"PR #{pr_num} has merge conflicts: {title}",
                    details={
                        "pr": pr_num,
                        "title": title,
                        "branch": pr.get("headRefName"),
                    },
                )
            )

        # Check for failing CI
        checks = pr.get("statusCheckRollup") or []
        failing = [
            c
            for c in checks
            if c.get("conclusion") in ("FAILURE", "ERROR", "CANCELLED")
        ]
        if failing:
            check_names = [c.get("name", "?") for c in failing[:3]]
            findings.append(
                MonitorFinding(
                    category="ci_status",
                    severity=SEVERITY_WARN,
                    summary=(
                        f"PR #{pr_num} has {len(failing)} failing check(s): "
                        f"{', '.join(check_names)}"
                    ),
                    details={"pr": pr_num, "failing_checks": check_names},
                )
            )

    # Summary
    findings.append(
        MonitorFinding(
            category="pr_status",
            severity=SEVERITY_INFO,
            summary=f"{len(prs)} open PR(s).",
            details={"count": len(prs)},
        )
    )

    return findings


def check_stale_dispatches(
    runtime_dir: Path | None = None,
    *,
    stale_minutes: int = STALE_DISPATCH_MINUTES,
    now: datetime | None = None,
) -> list[MonitorFinding]:
    """Check for dispatched task packets that have been idle too long.

    A dispatched packet with no progress (ack or result) after
    ``stale_minutes`` is flagged as potentially stuck.

    Args:
        runtime_dir: Override for the runtime directory root.
        stale_minutes: Minutes after which a dispatched packet is flagged.
        now: Override current time for testing.

    Returns:
        List of findings.
    """
    findings: list[MonitorFinding] = []

    if now is None:
        now = datetime.now(timezone.utc)

    try:
        from bid_euchre.ops.task_queue import list_packets, load_ack

        if runtime_dir is None:
            runtime_dir = Path(".claude/runtime")

        task_queue_root = runtime_dir / "task_queue"
        dispatched = list_packets(task_queue_root, status_filter="dispatched")
    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="stale_dispatch",
                severity=SEVERITY_WARN,
                summary=f"Could not check dispatched packets: {exc}",
            )
        )
        return findings

    for pkt in dispatched:
        # Check if there's an ack (indicates the lane received the task)
        ack = load_ack(pkt.packet_id, task_queue_root)
        if ack is not None:
            # Has been acknowledged — not stale
            continue

        # Check dispatch time
        try:
            ts_str = pkt.created_at.replace("Z", "+00:00")
            dispatch_time = datetime.fromisoformat(ts_str)
            if dispatch_time.tzinfo is None:
                dispatch_time = dispatch_time.replace(tzinfo=timezone.utc)
            age_minutes = (now - dispatch_time).total_seconds() / 60.0
        except (ValueError, TypeError):
            age_minutes = 0.0

        if age_minutes > stale_minutes:
            findings.append(
                MonitorFinding(
                    category="stale_dispatch",
                    severity=SEVERITY_HIGH,
                    summary=(
                        f"Packet {pkt.packet_id!r} dispatched to "
                        f"{pkt.owner!r} has been unacked for "
                        f"{age_minutes:.0f}min (threshold: {stale_minutes}min)"
                    ),
                    details={
                        "packet_id": pkt.packet_id,
                        "owner": pkt.owner,
                        "title": pkt.title,
                        "age_minutes": round(age_minutes),
                    },
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Orchestrator notification
# ---------------------------------------------------------------------------


def _send_findings_to_orchestrator(
    findings: list[MonitorFinding],
    *,
    bus_root: Path | None = None,
) -> str | None:
    """Send a monitoring summary to the orchestrator inbox.

    If there are high-severity findings, the message priority is set to
    ``high``. Otherwise it is ``normal``.

    Args:
        findings: The findings from the monitoring cycle.
        bus_root: Override for the message bus root.

    Returns:
        The message_id if sent, or None on failure.
    """
    if not findings:
        return None

    from bid_euchre.ops.message_bus import create_message, send_message

    has_high = any(f.severity == SEVERITY_HIGH for f in findings)
    high_count = sum(1 for f in findings if f.severity == SEVERITY_HIGH)
    warn_count = sum(1 for f in findings if f.severity == SEVERITY_WARN)
    info_count = sum(1 for f in findings if f.severity == SEVERITY_INFO)

    # Build summary line
    if has_high:
        summary = (
            f"Monitor: {high_count} HIGH, {warn_count} warn, {info_count} info findings"
        )
    elif warn_count > 0:
        summary = f"Monitor: {warn_count} warn, {info_count} info findings"
    else:
        summary = f"Monitor: {info_count} info findings (all nominal)"

    # Build payload with structured findings
    payload = {
        "findings": [asdict(f) for f in findings],
        "high_count": high_count,
        "warn_count": warn_count,
        "info_count": info_count,
    }

    priority = "high" if has_high else "normal"

    msg = create_message(
        from_lane="ops",
        to_lane="orchestrator",
        message_type="supervisor_alert",
        summary=summary,
        priority=priority,
        payload=payload,
    )

    try:
        return send_message(msg, bus_root)
    except (ValueError, OSError) as exc:
        logger.warning("Failed to send monitor summary: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_monitoring_cycle(
    runtime_dir: Path | None = None,
    *,
    now: datetime | None = None,
    stale_minutes: int = STALE_DISPATCH_MINUTES,
    notify_orchestrator: bool = True,
    skip_pr_check: bool = False,
) -> list[MonitorFinding]:
    """Run a single monitoring sweep.

    Collects findings from:
    1. Lane pool health snapshot
    2. Open PR status (via ``gh``)
    3. Stale dispatched packet detection

    Optionally sends a summary to the orchestrator inbox.

    Args:
        runtime_dir: Override for the runtime directory root.
        now: Override current time for testing.
        stale_minutes: Minutes after which a dispatched packet is flagged.
        notify_orchestrator: If True, send findings to orchestrator inbox.
        skip_pr_check: If True, skip the gh pr check (for testing).

    Returns:
        List of all findings from the sweep.
    """
    findings: list[MonitorFinding] = []

    # 1. Lane health
    findings.extend(check_lane_health(runtime_dir))

    # 2. Open PRs and CI
    if not skip_pr_check:
        findings.extend(check_open_prs())

    # 3. Stale dispatched packets
    findings.extend(
        check_stale_dispatches(runtime_dir, stale_minutes=stale_minutes, now=now)
    )

    # 4. Notify orchestrator
    if notify_orchestrator:
        _send_findings_to_orchestrator(findings)

    return findings


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_SEVERITY_MARKERS = {
    SEVERITY_HIGH: "!!",
    SEVERITY_WARN: "! ",
    SEVERITY_INFO: "  ",
}


def format_findings_text(findings: list[MonitorFinding]) -> str:
    """Format findings as human-readable text."""
    if not findings:
        return "Monitor: no findings."

    high = [f for f in findings if f.severity == SEVERITY_HIGH]
    warn = [f for f in findings if f.severity == SEVERITY_WARN]
    info = [f for f in findings if f.severity == SEVERITY_INFO]

    lines: list[str] = []
    lines.append(
        f"=== Monitor Cycle: {len(high)} HIGH, {len(warn)} warn, {len(info)} info ==="
    )

    for f in findings:
        marker = _SEVERITY_MARKERS.get(f.severity, "  ")
        lines.append(f"  [{marker}] [{f.category}] {f.summary}")

    return "\n".join(lines)


def format_findings_json(findings: list[MonitorFinding]) -> dict[str, Any]:
    """Format findings as a JSON-serializable dict."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(findings),
        "high": sum(1 for f in findings if f.severity == SEVERITY_HIGH),
        "warn": sum(1 for f in findings if f.severity == SEVERITY_WARN),
        "info": sum(1 for f in findings if f.severity == SEVERITY_INFO),
        "findings": [asdict(f) for f in findings],
    }
