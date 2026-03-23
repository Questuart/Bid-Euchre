"""Dashboard-first steward supervision surface (Platform-4).

Provides a structured dashboard view that answers "who owns what and what
needs attention" without requiring author panes to stay foregrounded.

The dashboard reads from existing data sources:
- ``ops.status.aggregate_status()`` — lane registry + task/session state
- ``ops.task_queue.queue_summary()`` — task packet counts
- ``ops.message_bus.inbox_stats()`` — per-lane inbox counts

It groups lanes into foreground (dashboard, orchestrator, ops, review, issues)
and background (author-*), surfaces attention items, and highlights unread
inbox messages.

Usage::

    from bid_euchre.ops.dashboard import build_dashboard_view, format_dashboard_text

    view = build_dashboard_view()
    print(format_dashboard_text(view))
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bid_euchre.ops.status import (
    LaneStatus,
    StatusReport,
    aggregate_status,
    branch_short,
    format_relative_time,
)

logger = logging.getLogger("ops.dashboard")

# ---------------------------------------------------------------------------
# Default visibility policy
# ---------------------------------------------------------------------------

#: Lane patterns that default to foreground visibility.
#: Lanes not matching any pattern default to ``"background"``.
FOREGROUND_LANE_IDS: frozenset[str] = frozenset(
    {"dashboard", "orchestrator", "ops", "review", "issues"}
)


def default_visibility(lane_id: str) -> str:
    """Return the default visibility for a lane based on its ID.

    Args:
        lane_id: Lane identifier.

    Returns:
        ``"foreground"`` for known supervisory lanes,
        ``"background"`` for author-* and others.
    """
    if lane_id in FOREGROUND_LANE_IDS:
        return "foreground"
    return "background"


def effective_visibility(lane: LaneStatus) -> str:
    """Return the effective visibility for a lane.

    Uses the explicit ``visibility`` field from the lane registry if set,
    otherwise falls back to :func:`default_visibility`.

    Args:
        lane: Lane status object (with optional ``visibility`` field).

    Returns:
        One of ``"foreground"``, ``"background"``, ``"hidden"``.
    """
    if lane.visibility and lane.visibility in ("foreground", "background", "hidden"):
        return lane.visibility
    return default_visibility(lane.lane_id)


# ---------------------------------------------------------------------------
# Visibility management
# ---------------------------------------------------------------------------

_VALID_VISIBILITY = frozenset({"foreground", "background", "hidden"})


def set_lane_visibility(
    lane_id: str,
    visibility: str,
    runtime_dir: Path | None = None,
) -> bool:
    """Set the visibility field on a lane's worktree registry entry.

    Reads the registry JSON, updates the ``visibility`` field, and writes
    it back atomically.

    Args:
        lane_id: Lane to update.
        visibility: One of ``"foreground"``, ``"background"``, ``"hidden"``.
        runtime_dir: Override for the runtime directory root.

    Returns:
        True if the lane was found and updated, False otherwise.

    Raises:
        ValueError: If *visibility* is not a valid value.
    """
    if visibility not in _VALID_VISIBILITY:
        raise ValueError(
            f"Invalid visibility {visibility!r}; "
            f"expected one of {sorted(_VALID_VISIBILITY)}"
        )

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    registry_dir = runtime_dir / "worktree_registry"
    if not registry_dir.exists():
        return False

    for entry_file in registry_dir.glob("*.json"):
        try:
            data = json.loads(entry_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        if data.get("lane_id") == lane_id:
            data["visibility"] = visibility
            # Atomic write via temp + rename
            tmp_fd, tmp_path = tempfile.mkstemp(dir=str(registry_dir), suffix=".tmp")
            try:
                os.write(tmp_fd, json.dumps(data, indent=2).encode())
                os.close(tmp_fd)
                Path(tmp_path).rename(entry_file)
            except Exception:
                # Clean up temp file on failure
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    pass
                raise
            logger.info("Set visibility for lane %r to %r", lane_id, visibility)
            return True

    return False


# ---------------------------------------------------------------------------
# Dashboard data structures
# ---------------------------------------------------------------------------


@dataclass
class DashboardSection:
    """One section of the dashboard (foreground or background lanes)."""

    title: str
    lanes: list[LaneStatus] = field(default_factory=list)


@dataclass
class AttentionItem:
    """A single item requiring operator attention."""

    lane_id: str
    severity: str  # "high", "medium", "low"
    reason: str
    suggested_action: str | None = None


@dataclass
class InboxHighlight:
    """Summary of unread/unacked messages for a lane."""

    lane_id: str
    unacked_count: int
    oldest_unacked_age: str | None = None  # relative time


@dataclass
class DashboardView:
    """Complete dashboard state for rendering.

    Built by :func:`build_dashboard_view` from existing repo-local state.
    Consumers should treat this as a read-only snapshot.
    """

    generated_at: str
    foreground: DashboardSection
    background: DashboardSection
    attention_items: list[AttentionItem] = field(default_factory=list)
    inbox_highlights: list[InboxHighlight] = field(default_factory=list)
    task_queue_summary: dict[str, Any] = field(default_factory=dict)
    active_task_count: int = 0
    blocked_task_count: int = 0
    warning_count: int = 0


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _derive_attention_items(
    report: StatusReport,
) -> list[AttentionItem]:
    """Derive attention items from lane status and task state.

    Priority order:
    - blocked lanes/tasks -> high
    - stale lanes -> medium
    - idle persistent lanes -> low

    Args:
        report: Aggregated status report.

    Returns:
        List of attention items, highest severity first.
    """
    items: list[AttentionItem] = []

    for lane in report.lanes:
        if not lane.attention_needed:
            continue

        reason = lane.attention_reason or "needs attention"

        if lane.state == "blocked":
            items.append(
                AttentionItem(
                    lane_id=lane.lane_id,
                    severity="high",
                    reason=reason,
                    suggested_action="unblock or reroute task",
                )
            )
        elif lane.state == "stale" or ("stale" in reason.lower() if reason else False):
            items.append(
                AttentionItem(
                    lane_id=lane.lane_id,
                    severity="medium",
                    reason=reason,
                    suggested_action="check if agent died",
                )
            )
        else:
            items.append(
                AttentionItem(
                    lane_id=lane.lane_id,
                    severity="low",
                    reason=reason,
                )
            )

    # Sort: high first, then medium, then low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: severity_order.get(x.severity, 3))

    return items


def _derive_inbox_highlights(
    bus_root: Path | None = None,
    *,
    now: datetime | None = None,
) -> list[InboxHighlight]:
    """Derive inbox highlights from message bus stats.

    Uses ``inbox_stats()`` to get per-lane message counts and computes
    unacked count as ``total - acked - resolved``.

    Args:
        bus_root: Override for message bus root directory.
        now: Current time for relative age computation.

    Returns:
        List of inbox highlights for lanes with unacked messages.
    """
    try:
        from bid_euchre.ops.message_bus import inbox_stats, read_inbox
    except ImportError:
        logger.debug("message_bus not available; skipping inbox highlights")
        return []

    if now is None:
        now = datetime.now(timezone.utc)

    try:
        stats = inbox_stats(bus_root)
    except Exception as exc:
        logger.debug("inbox_stats() failed: %s", exc)
        return []

    highlights: list[InboxHighlight] = []

    for lane_info in stats.get("lanes", []):
        lane_id = lane_info.get("lane_id", "")
        total = lane_info.get("total", 0)
        by_status = lane_info.get("by_status", {})

        # Derive unacked: total minus terminal statuses
        terminal_count = (
            by_status.get("acked", 0)
            + by_status.get("resolved", 0)
            + by_status.get("expired", 0)
            + by_status.get("dead_lettered", 0)
        )
        unacked = max(0, total - terminal_count)

        if unacked > 0:
            # Try to find oldest unacked message age
            oldest_age: str | None = None
            try:
                # Read pending/delivered messages to find oldest
                pending = read_inbox(lane_id, bus_root, status="pending")
                delivered = read_inbox(lane_id, bus_root, status="delivered")
                unacked_msgs = pending + delivered
                if unacked_msgs:
                    oldest_ts = min(
                        (m.get("created_at", "") for m in unacked_msgs),
                        default="",
                    )
                    if oldest_ts:
                        oldest_age = format_relative_time(oldest_ts, now=now)
            except Exception:
                pass

            highlights.append(
                InboxHighlight(
                    lane_id=lane_id,
                    unacked_count=unacked,
                    oldest_unacked_age=oldest_age,
                )
            )

    # Sort by count descending
    highlights.sort(key=lambda x: x.unacked_count, reverse=True)

    return highlights


def build_dashboard_view(
    runtime_dir: Path | None = None,
    *,
    bus_root: Path | None = None,
    check_worktree: bool = False,
    now: datetime | None = None,
) -> DashboardView:
    """Build a complete dashboard view from existing repo-local state.

    Synthesizes from:
    - ``aggregate_status()`` for lane/task/session data
    - ``inbox_stats()`` for message bus inbox highlights
    - Task queue summary (embedded in StatusReport)

    Args:
        runtime_dir: Override for the runtime directory root.
        bus_root: Override for message bus root directory.
        check_worktree: If True, run dirty-worktree subprocess checks.
            Default False for fast dashboard rendering.
        now: Current time for relative timestamps.

    Returns:
        Complete ``DashboardView`` snapshot.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Gather status data
    report = aggregate_status(runtime_dir, check_worktree=check_worktree)

    # Group lanes by effective visibility
    fg_lanes: list[LaneStatus] = []
    bg_lanes: list[LaneStatus] = []

    for lane in report.lanes:
        vis = effective_visibility(lane)
        if vis == "foreground":
            fg_lanes.append(lane)
        elif vis != "hidden":
            bg_lanes.append(lane)
        # hidden lanes are excluded from the dashboard view

    # Derive attention items and inbox highlights
    attention_items = _derive_attention_items(report)
    inbox_highlights = _derive_inbox_highlights(bus_root, now=now)

    return DashboardView(
        generated_at=now.isoformat(),
        foreground=DashboardSection(
            title="Foreground Lanes",
            lanes=fg_lanes,
        ),
        background=DashboardSection(
            title="Background Lanes",
            lanes=bg_lanes,
        ),
        attention_items=attention_items,
        inbox_highlights=inbox_highlights,
        task_queue_summary=report.task_queue_summary,
        active_task_count=len(report.active_tasks),
        blocked_task_count=len(report.blocked_tasks),
        warning_count=len(report.warnings),
    )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _format_lane_line(
    lane: LaneStatus,
    *,
    now: datetime | None = None,
) -> str:
    """Format a single lane as one dashboard line.

    Args:
        lane: Lane status object.
        now: Current time for relative timestamps.

    Returns:
        Formatted line string.
    """
    # State badge
    if lane.attention_needed:
        state_badge = f"[{lane.state}!]"
    else:
        state_badge = f"[{lane.state}]"

    # Task info
    if lane.current_task_title:
        task_info = lane.current_task_title
        if lane.current_step:
            task_info += f" ({lane.current_step})"
    elif lane.has_active_session and lane.session_task:
        task_info = lane.session_task
    elif lane.state == "likely_active" and lane.liveness_source:
        task_info = f"likely active (via {lane.liveness_source})"
    elif lane.state == "stale" and lane.liveness_source:
        task_info = f"stale (via {lane.liveness_source})"
    elif lane.session_task:
        task_info = f"idle, last: {lane.session_task}"
    else:
        # em dash
        task_info = "\u2014"

    # PR info
    pr_info = f"  PR #{lane.linked_pr}" if lane.linked_pr else ""

    # Branch info
    short_branch = branch_short(lane.branch) if lane.branch else ""
    branch_info = f"  @{short_branch}" if short_branch else ""

    # Time
    time_info = f"  {format_relative_time(lane.last_progress, now=now)}"

    return (
        f"  {lane.lane_id:15s} {state_badge:16s} "
        f"{task_info}{pr_info}{branch_info}{time_info}"
    )


def format_dashboard_text(
    view: DashboardView,
    *,
    now: datetime | None = None,
) -> str:
    """Format a DashboardView as human-readable text.

    Args:
        view: Dashboard view to format.
        now: Current time for relative timestamps.

    Returns:
        Multi-line text summary.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    lines: list[str] = []
    lines.append("=== Steward Dashboard ===")
    lines.append("")

    # Foreground lanes
    fg = view.foreground
    lines.append(f"{fg.title} ({len(fg.lanes)})")
    if fg.lanes:
        for lane in fg.lanes:
            lines.append(_format_lane_line(lane, now=now))
    else:
        lines.append("  (none)")
    lines.append("")

    # Background lanes — summary line with counts
    bg = view.background
    bg_active = sum(1 for lane in bg.lanes if lane.state in ("active", "likely_active"))
    bg_attention = sum(1 for lane in bg.lanes if lane.attention_needed)
    lines.append(
        f"{bg.title} ({len(bg.lanes)} total"
        f", {bg_active} active"
        f", {bg_attention} attention)"
    )
    if bg.lanes:
        for lane in bg.lanes:
            lines.append(_format_lane_line(lane, now=now))
    else:
        lines.append("  (none)")
    lines.append("")

    # Attention items
    if view.attention_items:
        lines.append(f"Attention ({len(view.attention_items)})")
        for item in view.attention_items:
            action_str = f" -> {item.suggested_action}" if item.suggested_action else ""
            lines.append(
                f"  [{item.severity}] {item.lane_id}: {item.reason}{action_str}"
            )
        lines.append("")

    # Inbox highlights
    if view.inbox_highlights:
        total_unacked = sum(h.unacked_count for h in view.inbox_highlights)
        lines.append(f"Inbox ({total_unacked} unacked)")
        for h in view.inbox_highlights:
            age_str = (
                f" (oldest: {h.oldest_unacked_age})" if h.oldest_unacked_age else ""
            )
            lines.append(
                f"  {h.lane_id}: {h.unacked_count} unacked message"
                f"{'s' if h.unacked_count != 1 else ''}{age_str}"
            )
        lines.append("")

    # Tasks summary
    lines.append(
        f"Tasks: {view.active_task_count} active, {view.blocked_task_count} blocked"
    )

    # Task queue
    tq = view.task_queue_summary
    if tq and tq.get("total", 0) > 0:
        lines.append(f"Task Queue: {tq['total']} packets")
        for pkt_info in tq.get("packets", []):
            owner_str = pkt_info.get("owner") or "(unassigned)"
            domain_str = f" [{pkt_info['domain']}]" if pkt_info.get("domain") else ""
            lines.append(
                f"  [{pkt_info.get('status', '?')}] "
                f"{pkt_info.get('title', '?')} -> {owner_str}{domain_str}"
            )

    if view.warning_count > 0:
        lines.append(f"Warnings: {view.warning_count}")

    return "\n".join(lines)


def format_dashboard_json(view: DashboardView) -> dict[str, Any]:
    """Format a DashboardView as a JSON-serializable dict.

    Args:
        view: Dashboard view to format.

    Returns:
        Dict suitable for JSON serialization.
    """
    return {
        "generated_at": view.generated_at,
        "summary": {
            "foreground_lanes": len(view.foreground.lanes),
            "background_lanes": len(view.background.lanes),
            "attention_items": len(view.attention_items),
            "inbox_unacked": sum(h.unacked_count for h in view.inbox_highlights),
            "active_tasks": view.active_task_count,
            "blocked_tasks": view.blocked_task_count,
            "warnings": view.warning_count,
        },
        "foreground": {
            "title": view.foreground.title,
            "lanes": [asdict(lane) for lane in view.foreground.lanes],
        },
        "background": {
            "title": view.background.title,
            "lanes": [asdict(lane) for lane in view.background.lanes],
        },
        "attention_items": [asdict(item) for item in view.attention_items],
        "inbox_highlights": [asdict(h) for h in view.inbox_highlights],
        "task_queue": view.task_queue_summary,
    }
