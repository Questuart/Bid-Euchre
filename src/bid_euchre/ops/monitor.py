"""Ops monitoring cycle (SP-3-08).

Runs a single monitoring sweep across lane health, open PRs, CI status,
and stale dispatched packets.  Produces structured findings that are
optionally sent to the orchestrator inbox via the message bus.

After the monitoring sweep, callers may run :func:`evaluate_alert_push`
to prepare a Telegram alert push for unresolved HIGH/URGENT items.
The push evaluator reads the latest fleet status from disk (written by
:func:`~bid_euchre.ops.control_plane.reconcile`) and returns a
:class:`MonitorCycleResult` that bundles findings and push payload.

Usage::

    from bid_euchre.ops.monitor import run_monitoring_cycle, evaluate_alert_push

    findings = run_monitoring_cycle()
    # findings is a list of MonitorFinding dataclasses

    # After reconcile(), evaluate alert push:
    result = evaluate_alert_push(findings=findings)
    if result.push_result is not None:
        # Caller sends result.push_result.message via Telegram MCP reply
        ...

The CLI wrapper (``ops.py monitor``) calls this and formats the output.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.monitor")

# A dispatched packet with no progress after this many minutes is flagged.
STALE_DISPATCH_MINUTES: int = 30

# Maximum auto-dispatches per monitor cycle (rate limit / kill switch).
MAX_AUTO_DISPATCH_PER_CYCLE: int = 2

# Stall detection: dispatched+acked lane with no tmux activity growth.
STALL_THRESHOLD_MINUTES: int = 10
STALL_CONSECUTIVE_CYCLES: int = 2

# Escalation: unacked alerts older than this are escalated to urgent priority.
# Default is 2 monitor cycles at 3 min each.
ESCALATION_AGE_MINUTES: int = 6

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


@dataclass
class MonitorCycleResult:
    """Complete result from a monitoring sweep plus optional alert push.

    Bundles the monitoring findings with the push evaluator result so that
    callers receive a single object with everything needed to act on the
    cycle outcome.

    Attributes:
        findings: All findings from the monitoring sweep.
        push_result: Alert push payload ready for Telegram delivery, or
            ``None`` if no push is needed (Telegram disabled, fleet active,
            no eligible items, etc.).
    """

    findings: list[MonitorFinding]
    push_result: Any = None  # PushResult | None — typed as Any to avoid hard import


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

        # Check for all-green CI (PR ready for merge)
        all_complete = checks and all(
            c.get("conclusion") == "SUCCESS" or c.get("status") == "COMPLETED"
            for c in checks
        )
        # Only flag as ready if there are actual checks AND none failing
        if all_complete and not failing:
            findings.append(
                MonitorFinding(
                    category="pr_ready",
                    severity=SEVERITY_WARN,
                    summary=(f"PR #{pr_num} CI green, ready for merge: {title}"),
                    details={
                        "pr": pr_num,
                        "title": title,
                        "branch": pr.get("headRefName"),
                        "checks_passed": len(checks),
                    },
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
# Idle lane detection
# ---------------------------------------------------------------------------


def check_idle_lanes(
    runtime_dir: Path | None = None,
) -> list[MonitorFinding]:
    """Detect lanes that are idle and available for dispatch.

    A lane is considered idle when it has ``pool_status == "idle"`` or has
    no current task assigned.  These lanes are immediately available for
    new work and the orchestrator should be notified so it can dispatch.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        List of findings for idle lanes.
    """
    findings: list[MonitorFinding] = []

    try:
        from bid_euchre.ops.worker_pool import take_pool_snapshot

        pool = take_pool_snapshot(runtime_dir)
    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="lane_idle",
                severity=SEVERITY_WARN,
                summary=f"Could not check for idle lanes: {exc}",
            )
        )
        return findings

    idle_lanes: list[str] = []
    for worker in pool.workers:
        if worker.pool_status == "idle" and worker.tmux_alive:
            idle_lanes.append(worker.lane_id)

    if idle_lanes:
        for lane_id in idle_lanes:
            findings.append(
                MonitorFinding(
                    category="lane_idle",
                    severity=SEVERITY_INFO,
                    summary=f"Lane {lane_id!r} idle and available for dispatch",
                    details={"lane_id": lane_id},
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Escalation check — unacked alerts from previous cycles
# ---------------------------------------------------------------------------


def check_escalations(
    *,
    bus_root: Path | None = None,
    events_dir: Path | None = None,
    max_age_minutes: int = ESCALATION_AGE_MINUTES,
) -> list[MonitorFinding]:
    """Check for unacked ops→orchestrator alerts and escalate if stale.

    Calls :func:`~bid_euchre.ops.message_bus.escalate_unacked` to find
    outbound ``supervisor_alert`` messages from ``ops`` to ``orchestrator``
    that remain unacknowledged after *max_age_minutes*.  For each such
    message an urgent escalation is created by the message bus.

    Args:
        bus_root: Override for the message bus root directory.
        events_dir: Override for the events directory (for testing).
        max_age_minutes: Age threshold in minutes before escalation fires.

    Returns:
        List of findings — one per escalation sent plus a summary.
    """
    findings: list[MonitorFinding] = []

    try:
        from bid_euchre.ops.message_bus import escalate_unacked

        escalation_ids = escalate_unacked(
            sender_lane="ops",
            recipient_lane="orchestrator",
            max_age_minutes=max_age_minutes,
            bus_root=bus_root,
            events_dir=events_dir,
        )
    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="escalation",
                severity=SEVERITY_WARN,
                summary=f"Could not check for unacked alerts: {exc}",
            )
        )
        return findings

    if escalation_ids:
        logger.warning("Escalated %d unacked alerts to P0", len(escalation_ids))
        findings.append(
            MonitorFinding(
                category="escalation",
                severity=SEVERITY_HIGH,
                summary=(f"Escalated {len(escalation_ids)} unacked alert(s) to urgent"),
                details={"escalation_ids": escalation_ids},
            )
        )
    else:
        findings.append(
            MonitorFinding(
                category="escalation",
                severity=SEVERITY_INFO,
                summary="No unacked alerts to escalate.",
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Recently merged PR detection
# ---------------------------------------------------------------------------


def check_recently_merged_prs(
    runtime_dir: Path | None = None,
) -> list[MonitorFinding]:
    """Detect PRs that have been merged recently.

    Queries ``gh pr list --state merged`` and compares against a persisted
    set of already-reported merged PR numbers.  Only new merges since the
    last cycle produce findings.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        List of findings for newly merged PRs.
    """
    findings: list[MonitorFinding] = []

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    state_path = runtime_dir / "merged_pr_state.json"

    # Load previously seen merged PRs
    try:
        seen: set[int] = set(json.loads(state_path.read_text()).get("seen", []))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        seen = set()

    try:
        result = subprocess.run(
            [
                "gh",
                "pr",
                "list",
                "--state",
                "merged",
                "--json",
                "number,title,headRefName,mergedAt",
                "--limit",
                "10",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            findings.append(
                MonitorFinding(
                    category="pr_merged",
                    severity=SEVERITY_WARN,
                    summary=f"gh pr list --state merged failed: {result.stderr[:200]}",
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
                category="pr_merged",
                severity=SEVERITY_WARN,
                summary=f"Could not check merged PRs: {exc}",
            )
        )
        return findings

    new_merged_numbers: set[int] = set()
    for pr in prs:
        pr_num = pr.get("number")
        if pr_num is None:
            continue
        new_merged_numbers.add(pr_num)

        if pr_num not in seen:
            title = pr.get("title", "?")
            branch = pr.get("headRefName", "?")
            findings.append(
                MonitorFinding(
                    category="pr_merged",
                    severity=SEVERITY_INFO,
                    summary=f"PR #{pr_num} merged: {title} ({branch})",
                    details={
                        "pr": pr_num,
                        "title": title,
                        "branch": branch,
                        "merged_at": pr.get("mergedAt"),
                    },
                )
            )

    # Persist the current set of seen merged PRs (keep up to last 50)
    updated_seen = sorted(seen | new_merged_numbers)[-50:]
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"seen": updated_seen}) + "\n")
    except OSError:
        pass  # Best-effort persistence

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
    _capture_fn: Any | None = None,
    _pane_pid_fn: Any | None = None,
    _pgrep_fn: Any | None = None,
) -> list[MonitorFinding]:
    """Detect dispatched+acked lanes that have stopped making progress.

    A lane is considered stalled when:
    1. It has a dispatched packet that has been acked (lane accepted the work).
    2. The dispatch is older than ``stall_minutes``.
    3. The tmux pane's activity epoch has not changed over
       ``consecutive_cycles`` consecutive monitor invocations.
    4. The pane does NOT show active-work indicators (spinner, progress
       counters) — prevents false stall reports when the lane is actively
       thinking but producing no visible output (#1612).
    5. No validation processes (make/pytest/ruff) are running in the lane's
       process tree — prevents false stalls during ``make check`` (#2123).

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
        _capture_fn: Optional callable(lane_id) -> str|None for testing.
            If provided, used instead of ``_capture_pane_content()`` when
            checking for active-work indicators (#1612).
        _pane_pid_fn: Optional callable(lane_id) -> str|None for testing.
            If provided, used instead of tmux pane PID probe (#2123).
        _pgrep_fn: Optional callable(pane_pid) -> list[str] for testing.
            If provided, used instead of ``pgrep`` subprocess (#2123).

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
            # ---- Active-work guard (#1612) ----
            # Before reporting stalled, verify the pane isn't showing
            # active-work indicators (spinner, progress counters).  A lane
            # that is actively thinking may have an unchanged activity epoch
            # but should not be reported as stalled.
            pane_content = _capture_pane_content(
                lane_id, tmux_session, runtime_dir, _capture_fn=_capture_fn
            )
            if pane_content is not None and _detect_active_work(pane_content):
                # Lane is actively working — reset observation, skip stall
                observations[lane_id]["unchanged_count"] = 0
                observations[lane_id]["recovery_count"] = 0
                continue

            # ---- Process-level validation guard (#2123) ----
            # Even if pane content doesn't show spinners, check if
            # make/pytest/ruff is running in the pane's process tree.
            if _detect_background_validation(
                lane_id,
                tmux_session,
                runtime_dir,
                _pane_pid_fn=_pane_pid_fn,
                _pgrep_fn=_pgrep_fn,
            ):
                observations[lane_id]["unchanged_count"] = 0
                observations[lane_id]["recovery_count"] = 0
                continue

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
# Approval-stall detection: lanes blocked on tool-approval prompts
# ---------------------------------------------------------------------------

#: Characters and patterns that indicate a lane is actively working (spinner,
#: progress indicators).  Presence of these in the last few pane lines means
#: the lane is NOT stalled — any approval-prompt text is historical noise.
_SPINNER_GLYPHS: frozenset[str] = frozenset("✶✻✽✢⏺✳⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

_ACTIVE_WORK_PATTERNS: list[re.Pattern[str]] = [
    # Claude Code spinner status line: "⏺ Running…", "✻ Bash(…"
    re.compile(r"[✶✻✽✢⏺✳⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]"),
    # Duration counters (e.g. "1m 23s", "0:45", "12s" but NOT "3.2s")
    re.compile(r"\d+m\s+\d+s|\d+:\d{2}(?!.*test)|(?<![.\d])\d+s\b"),
    # Running / timeout indicators
    re.compile(r"Running[…\.]|timeout", re.IGNORECASE),
    # Tool execution progress (not prompts — these appear inline during runs)
    re.compile(r"(?:Bash|Edit|Read|Write|Grep|Glob)\(.*\.\.\.", re.IGNORECASE),
    # make check / validation progress indicators
    re.compile(
        r"Running full check|Waiting for.*slot|make\[|All checks passed|"
        r"Checks FAILED|check-gated|check-quiet",
        re.IGNORECASE,
    ),
]

#: Number of trailing pane lines to scan for activity indicators.
#: Increased from 5 to 20 (#2123) — Claude Code TUI renders Bash tool status
#: (e.g. "⏺ Bash(make check-gated)…") above the visible prompt, so a 5-line
#: window misses it when status-bar / blank lines push it up.
_ACTIVITY_TAIL_LINES: int = 20

#: Regex patterns that match Claude Code tool-approval / elicitation prompts.
#: Each is compiled once at import time for efficiency.
_APPROVAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Allow\s+(Bash|Edit|Write|Read|Grep|Glob|NotebookEdit)", re.IGNORECASE),
    re.compile(r"\[A\]llow", re.IGNORECASE),
    re.compile(r"\[Y\]es,?\s*always", re.IGNORECASE),
    re.compile(r"Permission required", re.IGNORECASE),
    re.compile(r"Do you want to proceed", re.IGNORECASE),
    re.compile(r"Do you want to make this edit", re.IGNORECASE),
    re.compile(r"approve.*deny", re.IGNORECASE),
]

#: Lanes to check for approval stalls.  Only author and flex lanes —
#: not orchestrator, ops, or review.
_CHECKABLE_LANES: tuple[str, ...] = (
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


def _capture_pane_content(
    lane_id: str,
    tmux_session: str = "steward",
    runtime_dir: Path | None = None,
    *,
    _capture_fn: Any | None = None,
) -> str | None:
    """Capture the visible content of a lane's tmux pane.

    Args:
        lane_id: The lane identifier.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.
        _capture_fn: Optional test callable(lane_id) -> str|None.

    Returns:
        The pane content as a string, or None if capture fails.
    """
    if _capture_fn is not None:
        return _capture_fn(lane_id)

    from bid_euchre.ops.worker_pool import _resolve_tmux_target

    target = _resolve_tmux_target(lane_id, tmux_session, runtime_dir)
    try:
        result = subprocess.run(
            # -S -50: capture 50 lines of scrollback so we don't miss Bash
            # tool status lines pushed above the visible area (#2123).
            ["tmux", "capture-pane", "-t", target, "-p", "-S", "-50"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _detect_active_work(content: str) -> bool:
    """Check the tail of pane content for spinner / progress indicators.

    Only the last ``_ACTIVITY_TAIL_LINES`` non-empty lines are checked, since
    spinners and progress indicators appear at the bottom of the pane where
    current activity is displayed.

    Args:
        content: The captured pane text.

    Returns:
        True if the lane appears to be actively working (spinner, running
        indicator, or progress counter detected).
    """
    lines = content.splitlines()
    # Grab the last N non-empty lines
    tail: list[str] = []
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            tail.append(stripped)
            if len(tail) >= _ACTIVITY_TAIL_LINES:
                break

    for line in tail:
        for pattern in _ACTIVE_WORK_PATTERNS:
            if pattern.search(line):
                return True
    return False


#: Process names that indicate validation is running in a lane's pane.
_VALIDATION_PROCESS_NAMES: tuple[str, ...] = (
    "make",
    "pytest",
    "ruff",
    "python -m pytest",
)


def _detect_background_validation(
    lane_id: str,
    tmux_session: str = "steward",
    runtime_dir: Path | None = None,
    *,
    _pane_pid_fn: Any | None = None,
    _pgrep_fn: Any | None = None,
) -> bool:
    """Check if validation processes (make/pytest/ruff) are running in a lane's pane.

    Uses the OS process tree rooted at the pane's shell PID to detect
    ``make check``, ``pytest``, or ``ruff`` subprocesses — regardless of
    whether the TUI renders visible progress indicators.

    Args:
        lane_id: The lane identifier.
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.
        _pane_pid_fn: Optional test callable(lane_id) -> str|None.
        _pgrep_fn: Optional test callable(pane_pid) -> list[str].

    Returns:
        True if a validation process is detected in the lane's process tree.
    """
    # Step 1: Get the pane's shell PID
    if _pane_pid_fn is not None:
        pane_pid = _pane_pid_fn(lane_id)
    else:
        from bid_euchre.ops.worker_pool import _resolve_tmux_target

        target = _resolve_tmux_target(lane_id, tmux_session, runtime_dir)
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-t", target, "-p", "#{pane_pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            pane_pid = result.stdout.strip() if result.returncode == 0 else None
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pane_pid = None

    if not pane_pid:
        return False

    # Step 2: Check for validation processes in the pane's process tree
    if _pgrep_fn is not None:
        procs = _pgrep_fn(pane_pid)
    else:
        try:
            result = subprocess.run(
                ["pgrep", "-P", pane_pid, "-a"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            procs = result.stdout.strip().splitlines() if result.returncode == 0 else []
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            procs = []

    for proc_line in procs:
        proc_lower = proc_line.lower()
        for name in _VALIDATION_PROCESS_NAMES:
            if name in proc_lower:
                return True
    return False


def _match_approval_prompt(content: str) -> str | None:
    """Search pane content for approval-prompt patterns.

    Args:
        content: The captured pane text.

    Returns:
        The first matching line, or None if no match found.
    """
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for pattern in _APPROVAL_PATTERNS:
            if pattern.search(stripped):
                return stripped
    return None


def _default_approval_state_path(runtime_dir: Path | None = None) -> Path:
    """Return the path to the approval-stall dedup state file."""
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    return runtime_dir / "approval_stall_state.json"


def _load_approval_state(state_path: Path) -> dict[str, Any]:
    """Load approval-stall dedup state from disk."""
    try:
        return json.loads(state_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_approval_state(state_path: Path, state: dict[str, Any]) -> None:
    """Persist approval-stall dedup state to disk."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n")


def check_approval_stalls(
    tmux_session: str = "steward",
    runtime_dir: Path | None = None,
    *,
    _capture_fn: Any | None = None,
    _notify_fn: Any | None = None,
) -> list[MonitorFinding]:
    """Detect author lanes stuck on tool-approval prompts.

    Iterates through checkable lane panes, captures their content via
    ``tmux capture-pane``, and searches for approval-prompt patterns.

    Deduplication: tracks which lanes have been reported as stuck. Only sends
    a new notification if:
    - The lane wasn't previously reported as stuck, OR
    - The lane was unstuck and is now stuck again on a different prompt.

    Args:
        tmux_session: tmux session name.
        runtime_dir: Override for the runtime directory root.
        _capture_fn: Optional test callable(lane_id) -> str|None.
        _notify_fn: Optional test callable(lane_id, prompt_text, target) for
            notification side-effects.

    Returns:
        List of findings for lanes stuck on approval prompts.
    """
    findings: list[MonitorFinding] = []
    state_path = _default_approval_state_path(runtime_dir)
    state = _load_approval_state(state_path)
    reported: dict[str, str] = state.get("reported", {})

    from bid_euchre.ops.worker_pool import _resolve_tmux_target

    currently_stuck: dict[str, str] = {}

    for lane_id in _CHECKABLE_LANES:
        content = _capture_pane_content(
            lane_id,
            tmux_session,
            runtime_dir,
            _capture_fn=_capture_fn,
        )
        if content is None:
            continue

        # If the lane shows active-work indicators (spinner, progress
        # counters, etc.), it is executing — any approval-prompt text in the
        # pane is historical noise, not a real stall.
        if _detect_active_work(content):
            continue

        prompt_text = _match_approval_prompt(content)
        if prompt_text is None:
            continue

        # Resolve tmux target for the finding details
        try:
            target = _resolve_tmux_target(lane_id, tmux_session, runtime_dir)
        except Exception:
            target = f"{tmux_session}:{lane_id}"

        currently_stuck[lane_id] = prompt_text

        # Dedup: skip if already reported with the same prompt text
        if reported.get(lane_id) == prompt_text:
            continue

        findings.append(
            MonitorFinding(
                category="approval_stall",
                severity=SEVERITY_HIGH,
                summary=(
                    f"Lane {lane_id!r} stuck on approval prompt: {prompt_text[:80]}"
                ),
                details={
                    "lane_id": lane_id,
                    "prompt_text": prompt_text,
                    "tmux_target": target,
                },
            )
        )

        # Notify orchestrator for each new stall
        if _notify_fn is not None:
            _notify_fn(lane_id, prompt_text, target)
        else:
            _notify_approval_stall(lane_id, prompt_text, target)

    # Update dedup state: only keep lanes that are currently stuck
    new_reported: dict[str, str] = {}
    for lane_id, prompt_text in currently_stuck.items():
        new_reported[lane_id] = prompt_text

    _save_approval_state(state_path, {"reported": new_reported})

    return findings


def _notify_approval_stall(
    lane_id: str,
    prompt_text: str,
    tmux_target: str,
) -> str | None:
    """Send an approval-stall escalation to the orchestrator inbox.

    Args:
        lane_id: The blocked lane.
        prompt_text: The approval prompt text.
        tmux_target: The tmux pane target for manual navigation.

    Returns:
        The message_id if sent, or None on failure.
    """
    try:
        from bid_euchre.ops.message_bus import create_message, send_message

        msg = create_message(
            from_lane="ops-monitor",
            to_lane="orchestrator",
            message_type="escalation",
            summary=(f"Lane {lane_id!r} stuck on approval prompt: {prompt_text[:120]}"),
            payload={
                "lane_id": lane_id,
                "prompt_text": prompt_text,
                "tmux_target": tmux_target,
                "action": "User must navigate to tmux pane and approve/deny",
            },
        )
        return send_message(msg)
    except Exception as exc:
        logger.warning(
            "Failed to notify orchestrator about approval stall for %r: %s",
            lane_id,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Fleet-level idle check — auto-shutoff recommendation (#1572 / #1587)
# ---------------------------------------------------------------------------


def check_fleet_idle(
    runtime_dir: Path | None = None,
    *,
    now: datetime | None = None,
    threshold_minutes: float = 90,
) -> list[MonitorFinding]:
    """Check whether the entire fleet has been idle beyond the shutoff threshold.

    Calls :func:`~bid_euchre.ops.idle_detector.recommend_shutoff` and translates
    the result into a HIGH-severity finding when shutoff is recommended.  The
    finding's ``details`` include the structured recommendation so the
    orchestrator can act on it (cancel cron jobs, produce handoff, etc.).

    Args:
        runtime_dir: Override for the runtime directory root.
        now: Override for current time (for testing).
        threshold_minutes: Minutes threshold before idle shutoff is recommended.

    Returns:
        List of findings (0 or 1).
    """
    findings: list[MonitorFinding] = []

    try:
        from bid_euchre.ops.idle_detector import recommend_shutoff

        recommendation = recommend_shutoff(
            threshold_minutes=threshold_minutes,
            runtime_dir=runtime_dir,
            now=now,
        )
    except Exception as exc:
        logger.warning("Fleet idle check failed: %s", exc)
        findings.append(
            MonitorFinding(
                category="fleet_idle",
                severity=SEVERITY_WARN,
                summary=f"Could not check fleet idle status: {exc}",
            )
        )
        return findings

    if recommendation.should_shutoff:
        actions_text = "; ".join(recommendation.recommended_actions)
        findings.append(
            MonitorFinding(
                category="fleet_idle",
                severity=SEVERITY_HIGH,
                summary=(
                    f"Fleet idle for {recommendation.idle_status.idle_minutes:.0f}m — "
                    f"auto-shutoff recommended"
                ),
                details={
                    "should_shutoff": True,
                    "idle_minutes": recommendation.idle_status.idle_minutes,
                    "threshold_minutes": threshold_minutes,
                    "recommended_actions": recommendation.recommended_actions,
                    "reason": recommendation.idle_status.reason,
                },
            )
        )
        logger.warning(
            "Fleet idle shutoff finding emitted: %.0fm idle. Actions: %s",
            recommendation.idle_status.idle_minutes,
            actions_text,
        )
    else:
        # Emit an info-level finding for observability
        status = recommendation.idle_status
        findings.append(
            MonitorFinding(
                category="fleet_idle",
                severity=SEVERITY_INFO,
                summary=(f"Fleet active — {status.reason}"),
                details={
                    "should_shutoff": False,
                    "idle_minutes": status.idle_minutes,
                    "active_lanes": status.active_lanes,
                },
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Auto-dispatch: assign approved packets to idle lanes (SP-4-02 Step 6)
# ---------------------------------------------------------------------------


def _attempt_single_dispatch(
    pkt: Any,
    pool: Any,
    *,
    high_lanes: set[str],
    _dispatch_fn: Any | None,
    tmux_session: str,
    runtime_dir: Path,
) -> tuple[list[MonitorFinding], bool]:
    """Try to dispatch one approved packet to an idle lane.

    Selects a worker, applies safety guards (HIGH-lane skip), executes the
    dispatch, and mutates ``pool`` on success so the caller's next iteration
    won't re-select the same lane.

    Args:
        pkt: The approved task packet to dispatch.
        pool: Live pool snapshot (mutated in-place on success).
        high_lanes: Lane IDs with unresolved HIGH findings (skip these).
        _dispatch_fn: Optional test callable(packet_id, lane_id).
        tmux_session: tmux session name.
        runtime_dir: Runtime directory root.

    Returns:
        ``(findings, success)`` — findings produced by this attempt and
        whether the dispatch succeeded.
    """
    from bid_euchre.ops.worker_pool import select_worker

    findings: list[MonitorFinding] = []

    domain = getattr(pkt, "domain", None)
    lane_id = select_worker(pool, domain=domain)

    if lane_id is None:
        return findings, False

    # Skip lanes with unresolved HIGH findings
    if lane_id in high_lanes:
        return findings, False

    try:
        if _dispatch_fn is not None:
            _dispatch_fn(pkt.packet_id, lane_id)
        else:
            from bid_euchre.ops.worker_pool import dispatch_to_worker

            result = dispatch_to_worker(
                pkt.packet_id,
                lane_id,
                tmux_session=tmux_session,
                runtime_dir=runtime_dir,
                reset=True,
            )
            if result.error:
                findings.append(
                    MonitorFinding(
                        category="auto_dispatch",
                        severity=SEVERITY_WARN,
                        summary=(
                            f"Auto-dispatch failed for packet "
                            f"{pkt.packet_id!r} → {lane_id!r}: "
                            f"{result.error}"
                        ),
                        details={
                            "packet_id": pkt.packet_id,
                            "lane_id": lane_id,
                            "error": result.error,
                        },
                    )
                )
                return findings, False

        findings.append(
            MonitorFinding(
                category="auto_dispatch",
                severity=SEVERITY_INFO,
                summary=(
                    f"Auto-dispatched packet {pkt.packet_id!r} "
                    f"({pkt.title!r}) → {lane_id!r}"
                ),
                details={
                    "packet_id": pkt.packet_id,
                    "title": pkt.title,
                    "lane_id": lane_id,
                    "domain": domain,
                },
            )
        )

        # Mark lane as no longer idle in the snapshot so the next
        # iteration doesn't pick it again.
        for w in pool.workers:
            if w.lane_id == lane_id:
                # WorkerState is a dataclass (not frozen), mutate in place
                w.pool_status = "active"
                w.current_task_id = pkt.packet_id
                break
        pool.active_count += 1
        pool.available_capacity = max(0, pool.available_capacity - 1)

        return findings, True

    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="auto_dispatch",
                severity=SEVERITY_WARN,
                summary=(
                    f"Auto-dispatch error for packet "
                    f"{pkt.packet_id!r} → {lane_id!r}: {exc}"
                ),
                details={
                    "packet_id": pkt.packet_id,
                    "lane_id": lane_id,
                    "error": str(exc),
                },
            )
        )
        return findings, False


def check_auto_dispatch(
    runtime_dir: Path | None = None,
    *,
    max_dispatches: int = MAX_AUTO_DISPATCH_PER_CYCLE,
    current_findings: list[MonitorFinding] | None = None,
    tmux_session: str = "steward",
    _dispatch_fn: Any | None = None,
) -> list[MonitorFinding]:
    """Auto-dispatch approved packets to idle lanes.

    When a lane goes idle after completing a task, the monitor can
    auto-dispatch the next queued approved packet.  Domain affinity is
    used to match packets to lanes: same-domain → flex → skip.

    Safety guards:
    - Rate limit: at most ``max_dispatches`` dispatches per cycle.
    - Skip lanes that have unresolved HIGH findings in the current cycle.
    - Skip lanes that already have a dispatched packet.
    - Skip lanes with ``health == "critical"``.

    Args:
        runtime_dir: Override for the runtime directory root.
        max_dispatches: Maximum dispatches per cycle (kill switch).
        current_findings: Findings from earlier checks in the current cycle.
            Used to skip lanes with unresolved HIGH findings.
        tmux_session: tmux session name.
        _dispatch_fn: Optional callable(packet_id, lane_id) for testing.
            If provided, used instead of ``dispatch_to_worker()``.

    Returns:
        List of findings (INFO for successful dispatches, WARN for errors).
    """
    findings: list[MonitorFinding] = []

    if max_dispatches <= 0:
        return findings

    try:
        from bid_euchre.ops.task_queue import list_packets
        from bid_euchre.ops.worker_pool import take_pool_snapshot

        pool = take_pool_snapshot(runtime_dir, tmux_session=tmux_session)
        if runtime_dir is None:
            runtime_dir = Path(".claude/runtime")
        task_queue_root = runtime_dir / "task_queue"
        approved = list_packets(task_queue_root, status_filter="approved")
    except Exception as exc:
        findings.append(
            MonitorFinding(
                category="auto_dispatch",
                severity=SEVERITY_WARN,
                summary=f"Could not check for auto-dispatch: {exc}",
            )
        )
        return findings

    if not approved:
        return findings

    if pool.available_capacity <= 0:
        return findings

    # Build set of lanes with unresolved HIGH findings from this cycle.
    high_lanes: set[str] = set()
    if current_findings:
        for f in current_findings:
            if f.severity == SEVERITY_HIGH:
                lane_id = f.details.get("lane_id")
                if lane_id:
                    high_lanes.add(lane_id)

    dispatched_count = 0

    for pkt in approved:
        if dispatched_count >= max_dispatches:
            break

        attempt_findings, success = _attempt_single_dispatch(
            pkt,
            pool,
            high_lanes=high_lanes,
            _dispatch_fn=_dispatch_fn,
            tmux_session=tmux_session,
            runtime_dir=runtime_dir,
        )
        findings.extend(attempt_findings)
        if success:
            dispatched_count += 1

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
    no_auto_dispatch: bool = False,
) -> list[MonitorFinding]:
    """Run a single monitoring sweep.

    Collects findings from:
    0. Escalation check — escalate unacked alerts from previous cycles
    1. Lane pool health snapshot
    2. Open PR status and CI-ready detection (via ``gh``)
    3. Stale dispatched packet detection
    4. Idle lane detection (available for dispatch)
    5. Stalled lane detection (acked but idle), with optional recovery
    6. Approval-stall detection (lanes blocked on tool-approval prompts)
    7. Recently merged PR detection (new merges since last cycle)
    8. Auto-complete dispatched packets whose PRs were merged externally
    9. Auto-dispatch approved packets to idle lanes
    10. Fleet-level idle check — auto-shutoff recommendation (#1572)

    Optionally sends a summary to the orchestrator inbox.

    Args:
        runtime_dir: Override for the runtime directory root.
        now: Override current time for testing.
        stale_minutes: Minutes after which a dispatched packet is flagged.
        notify_orchestrator: If True, send findings to orchestrator inbox.
        skip_pr_check: If True, skip the gh pr check (for testing).
        no_recovery: If True, disable stall recovery actions (report only).
        no_auto_dispatch: If True, disable auto-dispatch of approved packets.

    Returns:
        List of all findings from the sweep.
    """
    findings: list[MonitorFinding] = []

    # 0. Escalation check — escalate unacked alerts from previous cycles
    findings.extend(check_escalations())

    # 1. Lane health
    findings.extend(check_lane_health(runtime_dir))

    # 2. Open PRs, CI status, and CI-ready detection
    if not skip_pr_check:
        findings.extend(check_open_prs())

    # 3. Stale dispatched packets
    findings.extend(
        check_stale_dispatches(runtime_dir, stale_minutes=stale_minutes, now=now)
    )

    # 4. Idle lane detection
    findings.extend(check_idle_lanes(runtime_dir))

    # 5. Stalled lane detection (acked dispatches with no progress)
    findings.extend(check_stalled_lanes(runtime_dir, now=now, no_recovery=no_recovery))

    # 6. Approval-stall detection (lanes blocked on approval prompts)
    findings.extend(check_approval_stalls(runtime_dir=runtime_dir))

    # 7. Recently merged PRs (new since last cycle)
    if not skip_pr_check:
        findings.extend(check_recently_merged_prs(runtime_dir))

    # 8. Auto-complete dispatched packets whose PRs were merged externally
    if not skip_pr_check:
        findings.extend(check_merged_dispatches(runtime_dir))

    # 9. Auto-dispatch approved packets to idle lanes
    if not no_auto_dispatch:
        findings.extend(check_auto_dispatch(runtime_dir, current_findings=findings))

    # 10. Fleet-level idle check — auto-shutoff recommendation (#1572)
    findings.extend(check_fleet_idle(runtime_dir, now=now))

    # 11. Notify orchestrator
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


# ---------------------------------------------------------------------------
# Alert push integration (Platform-9a)
# ---------------------------------------------------------------------------


def evaluate_alert_push(
    findings: list[MonitorFinding],
    *,
    runtime_dir: Path | None = None,
    audit_dir: Path | None = None,
    now: datetime | None = None,
) -> MonitorCycleResult:
    """Evaluate alert push after a monitoring sweep and return a combined result.

    This function bridges the monitoring cycle and the push evaluator from
    :mod:`~bid_euchre.ops.telegram_push`.  It is designed to be called
    **after** :func:`run_monitoring_cycle` and
    :func:`~bid_euchre.ops.control_plane.reconcile`, so that the fleet
    status on disk reflects the latest controller projection.

    The push evaluator reads fleet status from disk, evaluates which
    items need pushing (respecting cooldown, severity, and idle-gate),
    formats a Telegram-ready message, and records the push in the audit
    trail.  This function wraps that call with error handling (push is
    best-effort — never blocks the monitor cycle) and returns a
    :class:`MonitorCycleResult` that bundles findings + push payload.

    The **caller** is responsible for actually sending
    ``result.push_result.message`` to ``result.push_result.chat_id``
    via the Telegram MCP ``reply`` tool.

    Args:
        findings: Findings from :func:`run_monitoring_cycle`.
        runtime_dir: Override for the runtime directory root.
        audit_dir: Override audit trail directory.  If ``None`` and
            *runtime_dir* is set, defaults to ``runtime_dir / audit_trail``.
        now: Override current time (for testing).

    Returns:
        A :class:`MonitorCycleResult` with the original findings and an
        optional :class:`~bid_euchre.ops.telegram_push.PushResult`.
    """
    push_result = None
    try:
        from bid_euchre.ops.telegram_push import run_push_cycle

        effective_audit_dir = audit_dir
        if effective_audit_dir is None and runtime_dir is not None:
            effective_audit_dir = runtime_dir / "audit_trail"

        push_result = run_push_cycle(
            runtime_dir=runtime_dir,
            audit_dir=effective_audit_dir,
            now=now,
        )
    except Exception:
        # Push is best-effort — log and continue.
        logger.warning("Alert push evaluation failed", exc_info=True)

    return MonitorCycleResult(findings=findings, push_result=push_result)


# ---------------------------------------------------------------------------
# Inbound ack integration (Platform-9a)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InboundAckResult:
    """Result of processing an inbound message for ack commands.

    Attributes:
        is_ack_command: Whether the inbound text was a recognized ack command.
        success: Whether the ack mutation succeeded (False for non-commands).
        reply_text: Formatted confirmation/error text for replying to the
            operator, or ``None`` if the message was not an ack command.
        item_id: The full item_id that was matched (if any).
        action: The action string (ack/dismiss/mute/clear) or ``None``.
    """

    is_ack_command: bool
    success: bool = False
    reply_text: str | None = None
    item_id: str | None = None
    action: str | None = None


def process_inbound_ack(
    text: str,
    *,
    runtime_dir: Path | None = None,
) -> InboundAckResult:
    """Process an inbound Telegram message for ack/dismiss/mute/clear commands.

    This function bridges the inbound Telegram message path and the remote ack
    parser from :mod:`~bid_euchre.ops.remote_ack`.  It is designed to be called
    when the orchestrator receives an inbound message that may contain an ack
    command (e.g., ``ack abc1``).

    The full pipeline:

    1. Parse the inbound text via :func:`~bid_euchre.ops.remote_ack.parse_ack_command`.
    2. If not a command, return immediately (passthrough for free-form conversation).
    3. Load the fleet status from disk.
    4. Execute the ack mutation via :func:`~bid_euchre.ops.remote_ack.execute_remote_ack`.
    5. If the mutation succeeded, save the updated fleet status to disk.
    6. Format a confirmation message via :func:`~bid_euchre.ops.remote_ack.format_ack_confirmation`.

    The **caller** is responsible for:
    - Auditing the inbound message (via :func:`~bid_euchre.ops.audit_trail.audit_channel_tag`).
    - Sending ``result.reply_text`` back to the operator via Telegram MCP ``reply``.
    - Auditing the outbound confirmation (via :func:`~bid_euchre.ops.audit_trail.audit_reply`).

    Args:
        text: The inbound message text to parse.
        runtime_dir: Override for the runtime directory root (for fleet status I/O).

    Returns:
        An :class:`InboundAckResult` indicating whether the message was an ack
        command, whether the mutation succeeded, and the reply text.
    """
    from bid_euchre.ops.remote_ack import (
        execute_remote_ack,
        format_ack_confirmation,
        parse_ack_command,
    )

    # Step 1: Parse the ack command.
    cmd = parse_ack_command(text)
    if cmd is None:
        return InboundAckResult(is_ack_command=False)

    # Step 2: Load the fleet status from disk.
    from bid_euchre.ops.control_plane import load_fleet_status, save_fleet_status

    fleet_status = load_fleet_status(runtime_dir)
    if fleet_status is None:
        logger.warning("process_inbound_ack: no fleet status available")
        return InboundAckResult(
            is_ack_command=True,
            success=False,
            reply_text="\u274c No fleet status available — cannot process ack command.",
            action=cmd.action.value,
        )

    # Step 3: Execute the ack mutation.
    ack_result = execute_remote_ack(cmd, fleet_status)

    # Step 4: Save if mutation succeeded.
    if ack_result.success:
        try:
            save_fleet_status(fleet_status, runtime_dir=runtime_dir)
        except Exception:
            logger.warning(
                "process_inbound_ack: failed to save fleet status after mutation",
                exc_info=True,
            )
            return InboundAckResult(
                is_ack_command=True,
                success=False,
                reply_text=(
                    f"\u274c Ack {cmd.action.value} processed but failed to persist"
                    " — the change will be lost on next reload."
                ),
                item_id=ack_result.item_id,
                action=cmd.action.value,
            )

    # Step 5: Format confirmation.
    reply_text = format_ack_confirmation(ack_result)

    return InboundAckResult(
        is_ack_command=True,
        success=ack_result.success,
        reply_text=reply_text,
        item_id=ack_result.item_id,
        action=cmd.action.value,
    )
