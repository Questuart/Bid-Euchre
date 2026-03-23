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

# Stall detection: dispatched+acked lane with no tmux activity growth.
STALL_THRESHOLD_MINUTES: int = 10
STALL_CONSECUTIVE_CYCLES: int = 2

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
# Merged-dispatch completion (Gap A: auto-merge bypass)
# ---------------------------------------------------------------------------


def check_merged_dispatches(
    runtime_dir: Path | None = None,
) -> list[MonitorFinding]:
    """Complete dispatched packets whose PRs have already been merged.

    When GitHub auto-merges a PR (server-side), the PostToolUse hook in
    ``post-merge-notify.sh`` never fires because no ``gh pr merge`` runs in
    a Claude session.  This check scans dispatched packets that carry a
    ``metadata.pr_number``, queries GitHub for each PR's merge state, and
    auto-completes any that are merged.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        List of findings (one per auto-completed packet, plus errors).
    """
    findings: list[MonitorFinding] = []

    try:
        from bid_euchre.ops.task_queue import (
            list_packets,
            transition_status,
        )

        if runtime_dir is None:
            runtime_dir = Path(".claude/runtime")

        task_queue_root = runtime_dir / "task_queue"
        dispatched = list_packets(task_queue_root, status_filter="dispatched")
    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="merged_dispatch",
                severity=SEVERITY_WARN,
                summary=f"Could not check dispatched packets: {exc}",
            )
        )
        return findings

    for pkt in dispatched:
        pr_number = (getattr(pkt, "metadata", None) or {}).get("pr_number")
        if pr_number is None:
            continue

        # Query GitHub for the PR's merge state
        try:
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "view",
                    str(pr_number),
                    "--json",
                    "state",
                    "--jq",
                    ".state",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                continue
            state = result.stdout.strip()
        except (
            FileNotFoundError,
            subprocess.TimeoutExpired,
            OSError,
        ):
            continue

        if state != "MERGED":
            continue

        # Auto-complete the packet
        try:
            transition_status(pkt.packet_id, "completed", task_queue_root)
            findings.append(
                MonitorFinding(
                    category="merged_dispatch",
                    severity=SEVERITY_INFO,
                    summary=(
                        f"Auto-completed packet {pkt.packet_id!r} "
                        f"(PR #{pr_number} merged via auto-merge)"
                    ),
                    details={
                        "packet_id": pkt.packet_id,
                        "pr_number": pr_number,
                        "owner": pkt.owner,
                    },
                )
            )
        except Exception as exc:
            findings.append(
                MonitorFinding(
                    category="merged_dispatch",
                    severity=SEVERITY_WARN,
                    summary=(
                        f"Failed to auto-complete packet {pkt.packet_id!r} "
                        f"(PR #{pr_number}): {exc}"
                    ),
                    details={"packet_id": pkt.packet_id, "error": str(exc)},
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Stall detection helpers
# ---------------------------------------------------------------------------


def _default_stall_state_path(runtime_dir: Path | None = None) -> Path:
    """Return the path to the stall detection state file."""
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    return runtime_dir / "stall_state.json"


def _load_stall_state(state_path: Path) -> dict[str, Any]:
    """Load stall detection state from disk.

    Returns an empty dict if the file doesn't exist or is corrupt.
    """
    try:
        return json.loads(state_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_stall_state(state_path: Path, state: dict[str, Any]) -> None:
    """Persist stall detection state to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def _get_pane_activity_epoch(
    lane_id: str,
    tmux_session: str = "steward",
    runtime_dir: Path | None = None,
) -> int | None:
    """Query the tmux pane's last-activity epoch for a lane.

    Uses ``tmux display-message -t <target> -p '#{pane_activity}'``.

    Returns:
        The unix epoch timestamp of last pane activity, or None if the
        probe fails (pane dead, tmux unavailable, etc.).
    """
    from bid_euchre.ops.worker_pool import _resolve_tmux_target

    target = _resolve_tmux_target(lane_id, tmux_session, runtime_dir)
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-t", target, "-p", "#{pane_activity}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _do_nudge(
    lane_id: str,
    packet_id: str,
    tmux_session: str,
    runtime_dir: Path | None,
    nudge_fn: Any | None = None,
) -> bool:
    """Execute a re-nudge for a stalled lane.

    Uses the provided ``nudge_fn`` if given (for testing), otherwise calls
    ``nudge_pane()`` from the worker pool.

    Returns True if the nudge was attempted (regardless of outcome).
    """
    if nudge_fn is not None:
        nudge_fn(lane_id, packet_id)
        return True

    try:
        from bid_euchre.ops.worker_pool import nudge_pane

        nudge_pane(
            lane_id, packet_id, tmux_session=tmux_session, runtime_dir=runtime_dir
        )
    except Exception as exc:
        logger.warning("Re-nudge failed for lane %r: %s", lane_id, exc)
    return True


def check_stalled_lanes(
    runtime_dir: Path | None = None,
    *,
    stall_minutes: int = STALL_THRESHOLD_MINUTES,
    consecutive_cycles: int = STALL_CONSECUTIVE_CYCLES,
    now: datetime | None = None,
    tmux_session: str = "steward",
    no_recovery: bool = False,
    _activity_probe: Any | None = None,
    _nudge_fn: Any | None = None,
) -> list[MonitorFinding]:
    """Detect dispatched+acked lanes that have stopped making progress.

    A lane is considered stalled when:
    1. It has a dispatched packet that has been acked (lane accepted the work).
    2. The dispatch is older than ``stall_minutes``.
    3. The tmux pane's activity epoch has not changed over
       ``consecutive_cycles`` consecutive monitor invocations.

    When recovery is enabled (``no_recovery=False``, the default), stall
    detection includes a 2-step recovery ladder:

    - **First stall detection:** Re-nudge the lane via ``nudge_pane()``.
    - **Second consecutive stall (same lane, same packet):** Escalate to
      the orchestrator inbox as a HIGH finding.

    Recovery is limited to one action per lane per monitor cycle and is
    idempotent (re-nudge is safe to repeat).

    Cross-cycle state is persisted in a JSON state file so that each
    single-shot monitor invocation can compare against previous observations.

    Args:
        runtime_dir: Override for the runtime directory root.
        stall_minutes: Minimum dispatch age before stall detection activates.
        consecutive_cycles: Number of unchanged cycles before flagging.
        now: Override current time for testing.
        tmux_session: tmux session name.
        no_recovery: If True, disable recovery actions (report only).
        _activity_probe: Optional callable(lane_id) -> int|None for testing.
            If provided, used instead of tmux probe.
        _nudge_fn: Optional callable(lane_id, packet_id) for testing.
            If provided, used instead of ``nudge_pane()``.

    Returns:
        List of findings for stalled lanes (WARN for detection, HIGH for
        escalation).
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
                category="stall_detection",
                severity=SEVERITY_WARN,
                summary=f"Could not check for stalled lanes: {exc}",
            )
        )
        return findings

    # Load cross-cycle state
    state_path = _default_stall_state_path(runtime_dir)
    state = _load_stall_state(state_path)
    observations: dict[str, Any] = state.get("observations", {})

    # Track which lanes are still dispatched (for cleanup)
    active_lanes: set[str] = set()

    for pkt in dispatched:
        lane_id = pkt.owner
        if lane_id is None:
            continue

        # Only check acked dispatches (lane has started work)
        ack = load_ack(pkt.packet_id, task_queue_root)
        if ack is None:
            continue

        active_lanes.add(lane_id)

        # Check dispatch age — prefer metadata.dispatched_at (set by
        # dispatch_to_worker) over created_at (packet creation time).
        try:
            raw_ts: str = (getattr(pkt, "metadata", None) or {}).get(
                "dispatched_at", ""
            ) or pkt.created_at
            ts_str = raw_ts.replace("Z", "+00:00")
            dispatch_time = datetime.fromisoformat(ts_str)
            if dispatch_time.tzinfo is None:
                dispatch_time = dispatch_time.replace(tzinfo=timezone.utc)
            age_minutes = (now - dispatch_time).total_seconds() / 60.0
        except (ValueError, TypeError):
            age_minutes = 0.0

        if age_minutes < stall_minutes:
            # Too fresh — reset observation and skip
            observations[lane_id] = {
                "packet_id": pkt.packet_id,
                "activity_epoch": None,
                "unchanged_count": 0,
            }
            continue

        # Probe tmux pane activity
        if _activity_probe is not None:
            activity_epoch = _activity_probe(lane_id)
        else:
            activity_epoch = _get_pane_activity_epoch(
                lane_id, tmux_session, runtime_dir
            )

        if activity_epoch is None:
            # Can't probe — skip (dead panes caught by check_lane_health)
            continue

        # Compare with previous observation
        prev = observations.get(lane_id, {})
        prev_packet = prev.get("packet_id")
        prev_epoch = prev.get("activity_epoch")
        prev_count = prev.get("unchanged_count", 0)

        if prev_packet == pkt.packet_id and prev_epoch == activity_epoch:
            # Same packet, same activity — increment stall counter
            unchanged_count = prev_count + 1
        else:
            # Activity changed or new packet — reset
            unchanged_count = 0

        # Track recovery attempts across cycles for the escalation ladder.
        prev_recovery = prev.get("recovery_count", 0)
        if prev_packet != pkt.packet_id or prev_epoch != activity_epoch:
            # New packet or activity change — reset recovery counter
            recovery_count = 0
        else:
            recovery_count = prev_recovery

        observations[lane_id] = {
            "packet_id": pkt.packet_id,
            "activity_epoch": activity_epoch,
            "unchanged_count": unchanged_count,
            "recovery_count": recovery_count,
        }

        if unchanged_count >= consecutive_cycles:
            # ---- Recovery ladder ----
            if not no_recovery and recovery_count == 0:
                # Step 1: Re-nudge the lane
                _do_nudge(
                    lane_id,
                    pkt.packet_id,
                    tmux_session,
                    runtime_dir,
                    _nudge_fn,
                )
                observations[lane_id]["recovery_count"] = 1
                findings.append(
                    MonitorFinding(
                        category="stall_recovery",
                        severity=SEVERITY_WARN,
                        summary=(
                            f"Lane {lane_id!r} stalled — re-nudged "
                            f"(dispatched {age_minutes:.0f}min ago, "
                            f"{unchanged_count} unchanged cycle(s))"
                        ),
                        details={
                            "lane_id": lane_id,
                            "packet_id": pkt.packet_id,
                            "title": pkt.title,
                            "age_minutes": round(age_minutes),
                            "unchanged_cycles": unchanged_count,
                            "last_activity_epoch": activity_epoch,
                            "recovery_action": "nudge",
                        },
                    )
                )
            elif not no_recovery and recovery_count >= 1:
                # Step 2: Escalate to orchestrator inbox as HIGH
                observations[lane_id]["recovery_count"] = recovery_count + 1
                findings.append(
                    MonitorFinding(
                        category="stall_recovery",
                        severity=SEVERITY_HIGH,
                        summary=(
                            f"Lane {lane_id!r} still stalled after re-nudge "
                            f"— escalating (dispatched {age_minutes:.0f}min "
                            f"ago, {unchanged_count} unchanged cycle(s), "
                            f"recovery_count={recovery_count + 1})"
                        ),
                        details={
                            "lane_id": lane_id,
                            "packet_id": pkt.packet_id,
                            "title": pkt.title,
                            "age_minutes": round(age_minutes),
                            "unchanged_cycles": unchanged_count,
                            "last_activity_epoch": activity_epoch,
                            "recovery_action": "escalate",
                            "recovery_count": recovery_count + 1,
                        },
                    )
                )
            else:
                # no_recovery mode — report only (original behavior)
                findings.append(
                    MonitorFinding(
                        category="stall_detection",
                        severity=SEVERITY_WARN,
                        summary=(
                            f"Lane {lane_id!r} may be stalled: dispatched "
                            f"{age_minutes:.0f}min ago, no activity change "
                            f"over {unchanged_count} monitor cycle(s)"
                        ),
                        details={
                            "lane_id": lane_id,
                            "packet_id": pkt.packet_id,
                            "title": pkt.title,
                            "age_minutes": round(age_minutes),
                            "unchanged_cycles": unchanged_count,
                            "last_activity_epoch": activity_epoch,
                        },
                    )
                )

    # Clean up observations for lanes no longer dispatched
    for old_lane in list(observations.keys()):
        if old_lane not in active_lanes:
            del observations[old_lane]

    # Persist state
    _save_stall_state(state_path, {"observations": observations})

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
    no_recovery: bool = False,
) -> list[MonitorFinding]:
    """Run a single monitoring sweep.

    Collects findings from:
    1. Lane pool health snapshot
    2. Open PR status (via ``gh``)
    3. Stale dispatched packet detection
    4. Stalled lane detection (acked but idle), with optional recovery

    Optionally sends a summary to the orchestrator inbox.

    Args:
        runtime_dir: Override for the runtime directory root.
        now: Override current time for testing.
        stale_minutes: Minutes after which a dispatched packet is flagged.
        notify_orchestrator: If True, send findings to orchestrator inbox.
        skip_pr_check: If True, skip the gh pr check (for testing).
        no_recovery: If True, disable stall recovery actions (report only).

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

    # 4. Stalled lane detection (acked dispatches with no progress)
    findings.extend(check_stalled_lanes(runtime_dir, now=now, no_recovery=no_recovery))

    # 5. Auto-complete dispatched packets whose PRs were merged externally
    if not skip_pr_check:
        findings.extend(check_merged_dispatches(runtime_dir))

    # 6. Notify orchestrator
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
