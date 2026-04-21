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

from bid_euchre.ops.lane_heartbeat import read_heartbeat
from bid_euchre.ops.status import (
    LaneStatus,
    StatusReport,
    aggregate_status,
    branch_short,
    format_relative_time,
)

logger = logging.getLogger("ops.dashboard")


def _format_age(seconds: int | None) -> str:
    """Format an age in seconds compactly (``45s``, ``3m12s``, ``1h2m``).

    Mirrors :func:`scripts.internal.ops._format_age` — kept local to avoid
    reaching into the CLI module from the library.  Keep the two in sync.
    """
    if seconds is None:
        return "\u2014"  # em dash
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m{s}s"
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    return f"{h}h{m}m"


def _heartbeat_age_seconds(lane: LaneStatus, now: datetime) -> int | None:
    """Return the age of the lane's heartbeat in seconds, or ``None``.

    Reads the heartbeat file at
    ``<lane.worktree_path>/.claude/runtime/lane_status/<lane.lane_id>.json``.
    A missing file, malformed JSON, or unparseable timestamp yields
    ``None`` so the caller can fall back to the legacy render path
    without raising.
    """
    worktree_path = lane.worktree_path
    if not worktree_path:
        return None
    heartbeat_dir = Path(worktree_path) / ".claude" / "runtime" / "lane_status"
    try:
        hb = read_heartbeat(lane.lane_id, runtime_dir=heartbeat_dir)
    except Exception:  # pragma: no cover — defensive
        return None
    if hb is None:
        return None
    try:
        updated = datetime.fromisoformat(hb.updated_at.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age = (now - updated).total_seconds()
    if age < 0:
        return 0
    return int(age)


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
    token_economy: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


#: Lane classes considered "worker" lanes for fleet-wide idle detection.
#: Control-plane lanes (ops, review) are excluded — their idleness is normal
#: and should not contribute to a fleet-stuck determination.
_WORKER_LANE_CLASSES: frozenset[str] = frozenset({"author", "analyst", "scratch"})


def _derive_attention_items(
    report: StatusReport,
) -> list[AttentionItem]:
    """Derive attention items from lane status and task state.

    Priority order:
    - blocked lanes/tasks -> high
    - all worker lanes idle/stale -> high (fleet stuck)
    - stale lanes -> low (informational)
    - idle persistent lanes -> low

    Individual lane staleness is ``low`` (informational) — it is normal for
    some lanes to sit idle during fleet runs.  A ``high`` fleet-level alert
    fires only when **all** author/analyst/scratch lanes are idle or stale,
    indicating the entire fleet may be stuck (#1775).

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
            # Individual stale lanes are informational — it's normal for some
            # lanes to be unused during fleet runs (#1775).
            items.append(
                AttentionItem(
                    lane_id=lane.lane_id,
                    severity="low",
                    reason=reason,
                    suggested_action="check if agent died (informational)",
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

    # Fleet-wide idle check: if ALL worker lanes are idle or stale, the
    # entire fleet may be stuck — escalate to high (#1775).
    worker_lanes = [
        lane for lane in report.lanes if lane.lane_class in _WORKER_LANE_CLASSES
    ]
    if worker_lanes:
        all_idle_or_stale = all(
            lane.state in ("idle", "stale") for lane in worker_lanes
        )
        if all_idle_or_stale:
            items.append(
                AttentionItem(
                    lane_id="fleet",
                    severity="high",
                    reason=(
                        f"All {len(worker_lanes)} worker lanes are idle or "
                        f"stale — fleet may be stuck"
                    ),
                    suggested_action="check if fleet is stuck; consider dispatch or shutoff",
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

    # Token economy (best-effort — never fail dashboard on missing data)
    token_economy: dict[str, Any] = {}
    try:
        from bid_euchre.ops.token_economy import dashboard_token_economy

        runtime_root = runtime_dir or Path(".claude/runtime")
        te_output_dir = runtime_root / "token_economy"
        token_economy = dashboard_token_economy(
            output_dir=te_output_dir,
            auto_import=runtime_dir is None,
        )
    except Exception:
        pass  # Token economy data is optional

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
        token_economy=token_economy,
    )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def _format_age_seconds_short(seconds: float | int | None) -> str:
    """Compact human age string for dashboard token-economy header."""
    if seconds is None:
        return "unknown"
    s = max(int(seconds), 0)
    if s < 60:
        return f"{s}s"
    m = s // 60
    if m < 60:
        return f"{m}m"
    h = m // 60
    m %= 60
    if h < 24:
        return f"{h}h{m:02d}m"
    d = h // 24
    h %= 24
    return f"{d}d{h:02d}h"


def _format_token_economy_header(status: dict[str, Any] | None) -> str:
    """Render the token economy section header with a staleness marker.

    ``status`` is the ``store_status`` sub-dict attached by
    :func:`bid_euchre.ops.token_economy.dashboard_token_economy`.  When the
    status is missing (older callers) or indicates the store is fresh, the
    header is the plain ``"Token Economy"`` label so the dashboard appearance
    does not regress for healthy stores.

    Empty stores (``store_status.empty`` True) never reach this path because
    ``dashboard_token_economy`` returns ``{}`` for empty stores and the
    dashboard hides the section entirely.
    """
    if not status:
        return "Token Economy"
    if status.get("stale"):
        age = _format_age_seconds_short(status.get("age_seconds"))
        if not status.get("attributions_present", True):
            return f"Token Economy [STALE: {age} old; attributions missing]"
        return f"Token Economy [STALE: {age} old]"
    return "Token Economy"


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
    # Normalize ``now`` so helpers receive a concrete datetime.
    effective_now = now if now is not None else datetime.now(timezone.utc)

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
        if lane.liveness_source == "heartbeat":
            age_s = _heartbeat_age_seconds(lane, effective_now)
            if age_s is not None:
                task_info = f"likely active (via heartbeat, {_format_age(age_s)} ago)"
    elif lane.state == "stale" and lane.liveness_source:
        task_info = f"stale (via {lane.liveness_source})"
        if lane.liveness_source == "heartbeat":
            age_s = _heartbeat_age_seconds(lane, effective_now)
            if age_s is not None:
                task_info = f"stale (via heartbeat, {_format_age(age_s)} ago)"
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


def _format_dashboard_by_model(by_model: dict[str, Any] | None) -> list[str]:
    """Render the token-economy ``By model`` sub-section.

    Slice B (#2169) rules:

    1. Suppress the panel entirely when no non-``unknown`` bucket exists
       — a store that contains only legacy session-meta / pre-Slice-B
       JSONL rows would otherwise render as "unknown 100%" which is
       noise, not signal.
    2. Render at most four non-``unknown`` buckets. Any remaining
       non-``unknown`` buckets are folded into a single ``other`` row so
       the section stays bounded as the model zoo grows (haiku,
       synthetic-classifier-N, …).
    3. The ``unknown`` bucket is always shown when it exists and carries
       tokens — the operator must be able to see how much of the fleet
       cannot yet be attributed.
    """
    if not isinstance(by_model, dict):
        return []
    buckets = by_model.get("buckets") or []
    if not buckets:
        return []
    non_unknown = [b for b in buckets if b.get("model") != "unknown"]
    if not non_unknown:
        return []

    total_tokens = by_model.get("total_tokens") or 0
    # Sort non-unknown by total_tokens descending (model_summary already
    # sorts; we re-sort defensively in case the CLI or JSON consumer
    # reordered the list).
    non_unknown = sorted(
        non_unknown, key=lambda b: b.get("total_tokens") or 0, reverse=True
    )

    visible = non_unknown[:4]
    tail = non_unknown[4:]

    def fmt_row(label: str, tokens: int, commits: int | None) -> str:
        pct = (tokens / total_tokens * 100) if total_tokens > 0 else 0.0
        commits_str = f"{commits:>3d} commits" if commits else "—"
        return (
            f"    {label:<18s} {tokens / 1_000_000:>5.1f}M tok "
            f"({pct:>4.1f}%)  {commits_str}"
        )

    out: list[str] = ["  By model:"]
    for b in visible:
        out.append(
            fmt_row(
                b.get("model", "?"),
                int(b.get("total_tokens") or 0),
                b.get("git_commits"),
            )
        )
    if tail:
        tail_tokens = sum(int(b.get("total_tokens") or 0) for b in tail)
        tail_commits = sum(int(b.get("git_commits") or 0) for b in tail)
        out.append(
            fmt_row("other", tail_tokens, tail_commits if tail_commits > 0 else None)
        )
    # Unknown always last, as a disclosure row.
    unknown_bucket = next((b for b in buckets if b.get("model") == "unknown"), None)
    if unknown_bucket and int(unknown_bucket.get("total_tokens") or 0) > 0:
        out.append(
            fmt_row(
                "unknown",
                int(unknown_bucket.get("total_tokens") or 0),
                unknown_bucket.get("git_commits"),
            )
        )
    return out


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

    # Token economy
    te = view.token_economy
    if te:
        lines.append("")
        # Prepend a staleness/empty marker when the store is not fresh.
        # store_status is attached by dashboard_token_economy() on the
        # with-data path (empty stores still hide the section entirely).
        lines.append(_format_token_economy_header(te.get("store_status")))
        overview = te.get("overview", {})
        if overview:
            lines.append(
                f"  Tokens: {overview.get('total_tokens', 0):,}"
                f" ({overview.get('session_count', 0)} sessions"
                f", {overview.get('total_git_commits', 0)} commits)"
            )
            lines.append(
                f"  Efficiency: {overview.get('tokens_per_hour', 0):,.0f} tok/hr"
                f", {overview.get('output_input_ratio', 0):.1f}x out/in"
                f", {overview.get('net_lines', 0):+,d} net lines"
            )

        top_lanes = te.get("top_lanes", [])
        if top_lanes:
            lines.append("  Top lanes:")
            for tl in top_lanes[:3]:
                tpc = tl.get("tokens_per_commit")
                tpc_str = f"{tpc:,.0f} tok/commit" if tpc is not None else "—"
                lines.append(
                    f"    {tl['lane_id']:<18s} {tl['total_tokens']:>10,d} tok"
                    f"  {tpc_str}"
                )

        # Slice B (v3): by-model sub-section. Suppressed on stores that
        # contain only session-meta / pre-Slice-B JSONL rows (every
        # bucket would be ``unknown`` and mislead the operator).
        by_model = te.get("by_model", {})
        by_model_lines = _format_dashboard_by_model(by_model)
        if by_model_lines:
            lines.extend(by_model_lines)

        anti_patterns = te.get("anti_patterns", [])
        if anti_patterns:
            lines.append(f"  Anti-patterns: {len(anti_patterns)} detected")
            for ap in anti_patterns[:3]:
                sev = ap.get("severity", "?")
                lines.append(f"    [{sev}] {ap.get('name', '?')}")

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
        "token_economy": view.token_economy or None,
    }
