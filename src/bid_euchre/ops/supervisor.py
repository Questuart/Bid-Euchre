"""Ops supervisor routines and delta summaries (Platform-6).

Provides point-in-time lane health snapshots, delta computation between
consecutive snapshots, per-lane health assessment, and bounded recovery
recommendations.  This module **consumes** existing infrastructure
(dashboard, watchdogs, recovery, status, events) and does not modify or
replace any of it.

The main entry point is :func:`run_supervisor_cycle`, which performs a
single take-snapshot/assess/recommend/emit pass.  The CLI exposes this
via ``ops.py supervisor``.

Usage::

    from bid_euchre.ops.supervisor import (
        run_supervisor_cycle,
        take_snapshot,
        compute_delta,
        format_supervisor_text,
    )

    result = run_supervisor_cycle()
    print(format_supervisor_text(result))
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

logger = logging.getLogger("ops.supervisor")

# ---------------------------------------------------------------------------
# Health classification constants
# ---------------------------------------------------------------------------

#: Lane health levels, ordered from worst to best.
HEALTH_LEVELS: tuple[str, ...] = ("critical", "degraded", "healthy", "idle")

#: Lane states (from status.py) that map to each health level.
_STATE_TO_HEALTH: dict[str, str] = {
    "blocked": "critical",
    "stale": "degraded",
    "active": "healthy",
    "likely_active": "healthy",
    "idle": "idle",
    "unknown": "idle",
}

#: Default snapshot storage directory (under runtime_dir).
SNAPSHOT_DIR_NAME = "supervisor_snapshots"

#: Maximum number of persisted snapshots to keep.
MAX_PERSISTED_SNAPSHOTS = 20


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class LaneHealthAssessment:
    """Per-lane health classification derived from lane status + watchdogs.

    Attributes:
        lane_id: Lane identifier.
        health: One of ``HEALTH_LEVELS``.
        state: Raw lane state from status.py.
        findings: Watchdog findings targeting this lane, if any.
        attention_needed: Whether the lane needs operator attention.
        attention_reason: Human-readable reason if attention is needed.
        current_task: Title of the current task, if any.
        linked_pr: PR number if the lane has one open.
    """

    lane_id: str
    health: str
    state: str
    findings: list[dict[str, str]] = field(default_factory=list)
    attention_needed: bool = False
    attention_reason: str | None = None
    current_task: str | None = None
    linked_pr: int | None = None


@dataclass
class RecoveryRecommendation:
    """Bounded recovery action proposal for a lane.

    The supervisor does not execute recovery actions.  It produces
    recommendations that the orchestrator or human operator can accept,
    defer, or reject.

    Attributes:
        lane_id: Lane to apply recovery to.
        action: Short action label (``"retry"``, ``"reroute"``,
            ``"escalate"``, ``"respawn"``, ``"unblock"``).
        reason: Why this action is recommended.
        priority: Relative urgency (``"high"``, ``"medium"``, ``"low"``).
        auto_remediable: Whether the action can be automated.
        recovery_steps: Ordered human-readable steps if manual.
    """

    lane_id: str
    action: str
    reason: str
    priority: str = "medium"
    auto_remediable: bool = False
    recovery_steps: list[str] = field(default_factory=list)


@dataclass
class SupervisorSnapshot:
    """Point-in-time lane health snapshot.

    Captures the full state of all lanes and watchdog findings at a
    single moment.  Two consecutive snapshots can be diffed via
    :func:`compute_delta`.

    Attributes:
        timestamp: ISO 8601 timestamp when the snapshot was taken.
        lane_assessments: Per-lane health assessments.
        watchdog_finding_count: Total number of watchdog findings.
        active_failure_count: Number of unresolved failures from recovery.
        recommendations: Recovery recommendations derived from this snapshot.
        summary: Aggregate counts for quick inspection.
    """

    timestamp: str
    lane_assessments: list[LaneHealthAssessment] = field(default_factory=list)
    watchdog_finding_count: int = 0
    active_failure_count: int = 0
    recommendations: list[RecoveryRecommendation] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


@dataclass
class DeltaSummary:
    """Diff between two consecutive supervisor snapshots.

    Contains only what changed, so the orchestrator or ops surface can
    present delta-only summaries instead of repeating the full state.

    Attributes:
        from_timestamp: Timestamp of the earlier snapshot.
        to_timestamp: Timestamp of the later snapshot.
        health_changes: Lanes whose health level changed.
        new_findings: Watchdog findings present in *to* but not *from*.
        resolved_findings: Findings present in *from* but not *to*.
        new_recommendations: Recommendations in *to* but not *from*.
        resolved_recommendations: Recommendations in *from* but not *to*.
        summary_deltas: Changes in aggregate counts (key -> delta int).
    """

    from_timestamp: str
    to_timestamp: str
    health_changes: list[dict[str, str]] = field(default_factory=list)
    new_findings: list[dict[str, str]] = field(default_factory=list)
    resolved_findings: list[dict[str, str]] = field(default_factory=list)
    new_recommendations: list[dict[str, str]] = field(default_factory=list)
    resolved_recommendations: list[dict[str, str]] = field(default_factory=list)
    summary_deltas: dict[str, int] = field(default_factory=dict)


@dataclass
class SupervisorCycleResult:
    """Complete result from one supervisor cycle.

    Groups the snapshot, delta (if a previous snapshot exists), and any
    recommendations for convenient consumption.

    Attributes:
        snapshot: The current snapshot.
        delta: Delta from previous snapshot, or None if first run.
        has_changes: True if the delta contains any changes.
    """

    snapshot: SupervisorSnapshot
    delta: DeltaSummary | None = None
    has_changes: bool = False


# ---------------------------------------------------------------------------
# Core routines
# ---------------------------------------------------------------------------


def take_snapshot(
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    *,
    now: datetime | None = None,
) -> SupervisorSnapshot:
    """Take a point-in-time supervisor snapshot.

    Gathers lane status, watchdog findings, and active failures into a
    single coherent snapshot.

    Args:
        runtime_dir: Override for the runtime directory root.
        plans_dir: Override for the plans directory.
        now: Override current time for testing.

    Returns:
        A new :class:`SupervisorSnapshot`.
    """
    from bid_euchre.ops.recovery import get_active_failures
    from bid_euchre.ops.status import aggregate_status
    from bid_euchre.ops.watchdogs import run_all_watchdogs

    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")
    if plans_dir is None:
        plans_dir = Path("plans")
    if now is None:
        now = datetime.now(timezone.utc)

    # 1. Gather lane status
    report = aggregate_status(runtime_dir, check_worktree=False)

    # 2. Run watchdog checks
    findings = run_all_watchdogs(
        runtime_dir=runtime_dir,
        plans_dir=plans_dir,
        now=now,
    )

    # 3. Get active (unresolved) failures
    events_dir = runtime_dir / "events"
    active_failures: list = []
    if events_dir.exists():
        try:
            active_failures = get_active_failures(events_dir)
        except Exception as exc:
            logger.debug("get_active_failures() failed: %s", exc)

    # 4. Build per-lane assessments
    # Index watchdog findings by target lane (best-effort extraction)
    findings_by_lane: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        # Extract lane_id from target — may be a path or lane name
        lane_key = _extract_lane_from_target(f.target, report)
        findings_by_lane.setdefault(lane_key, []).append(
            {
                "watchdog": f.watchdog_name,
                "severity": f.severity,
                "message": f.message,
                "target": f.target,
            }
        )

    lane_assessments = []
    for lane in report.lanes:
        lane_findings = findings_by_lane.get(lane.lane_id, [])
        health = _classify_lane_health(lane, lane_findings)
        lane_assessments.append(
            LaneHealthAssessment(
                lane_id=lane.lane_id,
                health=health,
                state=lane.state,
                findings=lane_findings,
                attention_needed=lane.attention_needed,
                attention_reason=lane.attention_reason,
                current_task=lane.current_task_title,
                linked_pr=lane.linked_pr,
            )
        )

    # 5. Build summary counts
    health_counts: dict[str, int] = {h: 0 for h in HEALTH_LEVELS}
    for la in lane_assessments:
        health_counts[la.health] = health_counts.get(la.health, 0) + 1

    summary = {
        "total_lanes": len(lane_assessments),
        "critical": health_counts.get("critical", 0),
        "degraded": health_counts.get("degraded", 0),
        "healthy": health_counts.get("healthy", 0),
        "idle": health_counts.get("idle", 0),
        "watchdog_findings": len(findings),
        "active_failures": len(active_failures),
        "attention_needed": sum(1 for la in lane_assessments if la.attention_needed),
    }

    # 6. Generate recovery recommendations
    recommendations = _build_recommendations(lane_assessments, active_failures)

    return SupervisorSnapshot(
        timestamp=now.isoformat(),
        lane_assessments=lane_assessments,
        watchdog_finding_count=len(findings),
        active_failure_count=len(active_failures),
        recommendations=recommendations,
        summary=summary,
    )


def assess_lane_health(
    lane_id: str,
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    *,
    now: datetime | None = None,
) -> LaneHealthAssessment | None:
    """Assess health of a single lane.

    Convenience wrapper that takes a full snapshot then extracts the
    assessment for the requested lane.

    Args:
        lane_id: Lane to assess.
        runtime_dir: Override for the runtime directory root.
        plans_dir: Override for the plans directory.
        now: Override current time for testing.

    Returns:
        The lane's health assessment, or None if the lane was not found.
    """
    snapshot = take_snapshot(runtime_dir, plans_dir, now=now)
    for la in snapshot.lane_assessments:
        if la.lane_id == lane_id:
            return la
    return None


def recommend_recovery(
    snapshot: SupervisorSnapshot,
) -> list[RecoveryRecommendation]:
    """Extract or recompute recovery recommendations from a snapshot.

    This is a convenience accessor; recommendations are already embedded
    in the snapshot by :func:`take_snapshot`.

    Args:
        snapshot: A supervisor snapshot.

    Returns:
        List of recovery recommendations.
    """
    return list(snapshot.recommendations)


def compute_delta(
    prev: SupervisorSnapshot,
    curr: SupervisorSnapshot,
) -> DeltaSummary:
    """Compute the delta between two consecutive snapshots.

    Identifies health-level changes, new/resolved findings, and
    new/resolved recommendations.

    Args:
        prev: The earlier snapshot.
        curr: The later snapshot.

    Returns:
        A :class:`DeltaSummary` capturing only what changed.
    """
    # 1. Health changes
    prev_health = {la.lane_id: la.health for la in prev.lane_assessments}
    curr_health = {la.lane_id: la.health for la in curr.lane_assessments}

    health_changes: list[dict[str, str]] = []

    # Check lanes in both snapshots for changes, plus new lanes
    all_lane_ids = set(prev_health) | set(curr_health)
    for lid in sorted(all_lane_ids):
        old_h = prev_health.get(lid)
        new_h = curr_health.get(lid)
        if old_h != new_h:
            health_changes.append(
                {
                    "lane_id": lid,
                    "from": old_h or "(absent)",
                    "to": new_h or "(absent)",
                }
            )

    # 2. Findings delta (by watchdog+target composite key)
    def _finding_key(f: dict[str, str]) -> str:
        return f"{f.get('watchdog', '')}:{f.get('target', '')}"

    prev_findings: dict[str, dict[str, str]] = {}
    for la in prev.lane_assessments:
        for f in la.findings:
            prev_findings[_finding_key(f)] = f

    curr_findings: dict[str, dict[str, str]] = {}
    for la in curr.lane_assessments:
        for f in la.findings:
            curr_findings[_finding_key(f)] = f

    new_finding_keys = set(curr_findings) - set(prev_findings)
    resolved_finding_keys = set(prev_findings) - set(curr_findings)

    new_findings = [curr_findings[k] for k in sorted(new_finding_keys)]
    resolved_findings = [prev_findings[k] for k in sorted(resolved_finding_keys)]

    # 3. Recommendation delta (by lane_id+action key)
    def _rec_key(r: RecoveryRecommendation | dict[str, Any]) -> str:
        if isinstance(r, RecoveryRecommendation):
            return f"{r.lane_id}:{r.action}"
        return f"{r.get('lane_id', '')}:{r.get('action', '')}"

    prev_recs = {_rec_key(r): _rec_to_dict(r) for r in prev.recommendations}
    curr_recs = {_rec_key(r): _rec_to_dict(r) for r in curr.recommendations}

    new_rec_keys = set(curr_recs) - set(prev_recs)
    resolved_rec_keys = set(prev_recs) - set(curr_recs)

    new_recommendations = [curr_recs[k] for k in sorted(new_rec_keys)]
    resolved_recommendations = [prev_recs[k] for k in sorted(resolved_rec_keys)]

    # 4. Summary deltas
    summary_deltas: dict[str, int] = {}
    all_keys = set(prev.summary) | set(curr.summary)
    for key in sorted(all_keys):
        old_val = prev.summary.get(key, 0)
        new_val = curr.summary.get(key, 0)
        delta = new_val - old_val
        if delta != 0:
            summary_deltas[key] = delta

    return DeltaSummary(
        from_timestamp=prev.timestamp,
        to_timestamp=curr.timestamp,
        health_changes=health_changes,
        new_findings=new_findings,
        resolved_findings=resolved_findings,
        new_recommendations=new_recommendations,
        resolved_recommendations=resolved_recommendations,
        summary_deltas=summary_deltas,
    )


def run_supervisor_cycle(
    runtime_dir: Path | None = None,
    plans_dir: Path | None = None,
    *,
    now: datetime | None = None,
    prev_snapshot: SupervisorSnapshot | None = None,
    save: bool = False,
) -> SupervisorCycleResult:
    """Run a single supervisor cycle: snapshot, delta, recommend.

    This is the main entry point for supervisor operations.  It:

    1. Takes a new snapshot via :func:`take_snapshot`.
    2. If a previous snapshot is available (either passed in or loaded
       from disk), computes a delta via :func:`compute_delta`.
    3. Returns the combined result.

    Args:
        runtime_dir: Override for the runtime directory root.
        plans_dir: Override for the plans directory.
        now: Override current time for testing.
        prev_snapshot: Previous snapshot to diff against.  If None and
            ``save`` is True, attempts to load the most recent saved
            snapshot.
        save: If True, persist the snapshot to disk for future delta
            computation.

    Returns:
        A :class:`SupervisorCycleResult` with snapshot, delta, and
        change flag.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    snapshot = take_snapshot(runtime_dir, plans_dir, now=now)

    # Try to load previous snapshot if none provided and save mode is on
    if prev_snapshot is None and save:
        prev_snapshot = load_latest_snapshot(runtime_dir)

    # Compute delta
    delta: DeltaSummary | None = None
    has_changes = False

    if prev_snapshot is not None:
        delta = compute_delta(prev_snapshot, snapshot)
        has_changes = bool(
            delta.health_changes
            or delta.new_findings
            or delta.resolved_findings
            or delta.new_recommendations
            or delta.resolved_recommendations
            or delta.summary_deltas
        )

    # Persist snapshot if requested
    if save:
        save_snapshot(snapshot, runtime_dir)

    return SupervisorCycleResult(
        snapshot=snapshot,
        delta=delta,
        has_changes=has_changes,
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def save_snapshot(
    snapshot: SupervisorSnapshot,
    runtime_dir: Path | None = None,
) -> Path:
    """Persist a snapshot to disk for future delta computation.

    Snapshots are stored as timestamped JSON files in
    ``{runtime_dir}/supervisor_snapshots/``.

    Args:
        snapshot: The snapshot to save.
        runtime_dir: Override for the runtime directory root.

    Returns:
        Path to the saved snapshot file.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    snap_dir = runtime_dir / SNAPSHOT_DIR_NAME
    snap_dir.mkdir(parents=True, exist_ok=True)

    # Use timestamp-based filename (replace colons for filesystem compat)
    safe_ts = snapshot.timestamp.replace(":", "-").replace("+", "p")
    filename = f"snapshot_{safe_ts}.json"
    target = snap_dir / filename

    data = _snapshot_to_dict(snapshot)

    # Atomic write
    fd, tmp_path = tempfile.mkstemp(dir=str(snap_dir), suffix=".tmp")
    try:
        os.write(fd, json.dumps(data, indent=2, default=str).encode())
        os.close(fd)
        Path(tmp_path).rename(target)
    except Exception:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise

    # Prune old snapshots
    _prune_snapshots(snap_dir)

    logger.debug("Saved supervisor snapshot: %s", target)
    return target


def load_latest_snapshot(
    runtime_dir: Path | None = None,
) -> SupervisorSnapshot | None:
    """Load the most recent saved snapshot from disk.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        The most recent snapshot, or None if no snapshots exist.
    """
    if runtime_dir is None:
        runtime_dir = Path(".claude/runtime")

    snap_dir = runtime_dir / SNAPSHOT_DIR_NAME
    if not snap_dir.exists():
        return None

    files = sorted(snap_dir.glob("snapshot_*.json"))
    if not files:
        return None

    try:
        data = json.loads(files[-1].read_text())
        return _dict_to_snapshot(data)
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        logger.debug("Failed to load snapshot %s: %s", files[-1], exc)
        return None


def _prune_snapshots(snap_dir: Path) -> None:
    """Remove old snapshots beyond the retention limit."""
    files = sorted(snap_dir.glob("snapshot_*.json"))
    while len(files) > MAX_PERSISTED_SNAPSHOTS:
        oldest = files.pop(0)
        try:
            oldest.unlink()
            logger.debug("Pruned old snapshot: %s", oldest)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_lane_from_target(
    target: str,
    report: Any,
) -> str:
    """Best-effort extraction of lane_id from a watchdog finding target.

    Watchdog targets may be file paths, lane IDs, task IDs, or other
    strings.  We try to match against known lane IDs from the status
    report.

    Args:
        target: The watchdog finding's target string.
        report: A StatusReport with ``.lanes`` attribute.

    Returns:
        The matched lane_id, or ``"_unknown"`` if no match.
    """
    known_lanes = {lane.lane_id for lane in report.lanes}

    # Direct match
    if target in known_lanes:
        return target

    # Check if any lane_id is a substring of the target (e.g., path
    # contains lane name)
    for lid in known_lanes:
        if lid in target:
            return lid

    return "_unknown"


def _classify_lane_health(
    lane: Any,
    findings: list[dict[str, str]],
) -> str:
    """Classify a lane's health from its state and watchdog findings.

    Args:
        lane: A LaneStatus object.
        findings: Watchdog findings for this lane.

    Returns:
        One of ``HEALTH_LEVELS``.
    """
    # Critical findings override everything
    if any(f.get("severity") == "critical" for f in findings):
        return "critical"

    # Attention-needed lanes with warnings are degraded
    if lane.attention_needed and findings:
        return "degraded"

    # Map from lane state
    base_health = _STATE_TO_HEALTH.get(lane.state, "idle")

    # Warning findings on an otherwise healthy lane -> degraded
    if base_health == "healthy" and any(
        f.get("severity") == "warning" for f in findings
    ):
        return "degraded"

    return base_health


def _build_recommendations(
    lane_assessments: list[LaneHealthAssessment],
    active_failures: list,
) -> list[RecoveryRecommendation]:
    """Build recovery recommendations from assessments and failures.

    Consumes recovery.py templates but does not modify them.

    Args:
        lane_assessments: Per-lane health assessments.
        active_failures: Unresolved failures from recovery.py.

    Returns:
        List of recovery recommendations.
    """
    from bid_euchre.ops.recovery import RECOVERY_TEMPLATES

    recommendations: list[RecoveryRecommendation] = []

    # Recommendations from lane health
    for la in lane_assessments:
        if la.health == "critical":
            # Check if there are stale heartbeat findings
            has_stale_hb = any(
                "heartbeat" in f.get("watchdog", "") for f in la.findings
            )
            if has_stale_hb:
                template = RECOVERY_TEMPLATES.get("heartbeat_stale")
                recommendations.append(
                    RecoveryRecommendation(
                        lane_id=la.lane_id,
                        action="respawn",
                        reason="Stale heartbeat detected — agent may have died",
                        priority="high",
                        auto_remediable=False,
                        recovery_steps=(
                            template.steps if template else ["Check agent process"]
                        ),
                    )
                )
            elif la.state == "blocked":
                template = RECOVERY_TEMPLATES.get("task_blocked")
                recommendations.append(
                    RecoveryRecommendation(
                        lane_id=la.lane_id,
                        action="unblock",
                        reason=la.attention_reason or "Lane is blocked",
                        priority="high",
                        auto_remediable=False,
                        recovery_steps=(
                            template.steps if template else ["Investigate blocker"]
                        ),
                    )
                )
            else:
                recommendations.append(
                    RecoveryRecommendation(
                        lane_id=la.lane_id,
                        action="escalate",
                        reason=la.attention_reason or "Critical health with findings",
                        priority="high",
                        auto_remediable=False,
                        recovery_steps=["Investigate critical findings manually"],
                    )
                )

        elif la.health == "degraded" and la.attention_needed:
            # Degraded with attention — suggest investigation
            recommendations.append(
                RecoveryRecommendation(
                    lane_id=la.lane_id,
                    action="investigate",
                    reason=la.attention_reason or "Degraded lane health",
                    priority="medium",
                    auto_remediable=False,
                    recovery_steps=[
                        "Check watchdog findings for this lane",
                        "Verify task progress",
                        "Check for CI or review blockers",
                    ],
                )
            )

    # Recommendations from active failures not already covered by lane
    # assessments
    covered_lanes = {r.lane_id for r in recommendations}
    for failure in active_failures:
        target = failure.target
        if target in covered_lanes:
            continue

        if failure.template and failure.template.auto_remediable:
            recommendations.append(
                RecoveryRecommendation(
                    lane_id=target,
                    action="retry",
                    reason=failure.details,
                    priority="medium",
                    auto_remediable=True,
                    recovery_steps=failure.template.steps,
                )
            )
        elif failure.severity == "critical":
            recommendations.append(
                RecoveryRecommendation(
                    lane_id=target,
                    action="escalate",
                    reason=failure.details,
                    priority="high",
                    auto_remediable=False,
                    recovery_steps=(
                        failure.template.steps
                        if failure.template
                        else ["Manual investigation required"]
                    ),
                )
            )

    return recommendations


def _rec_to_dict(
    rec: RecoveryRecommendation | dict[str, Any],
) -> dict[str, Any]:
    """Convert a RecoveryRecommendation to a plain dict."""
    if isinstance(rec, dict):
        return rec
    return asdict(rec)


def _snapshot_to_dict(snapshot: SupervisorSnapshot) -> dict[str, Any]:
    """Serialize a SupervisorSnapshot to a JSON-compatible dict."""
    return {
        "timestamp": snapshot.timestamp,
        "lane_assessments": [asdict(la) for la in snapshot.lane_assessments],
        "watchdog_finding_count": snapshot.watchdog_finding_count,
        "active_failure_count": snapshot.active_failure_count,
        "recommendations": [asdict(r) for r in snapshot.recommendations],
        "summary": snapshot.summary,
    }


def _dict_to_snapshot(data: dict[str, Any]) -> SupervisorSnapshot:
    """Deserialize a dict back into a SupervisorSnapshot."""
    lane_assessments = [
        LaneHealthAssessment(**la) for la in data.get("lane_assessments", [])
    ]
    recommendations = [
        RecoveryRecommendation(**r) for r in data.get("recommendations", [])
    ]
    return SupervisorSnapshot(
        timestamp=data["timestamp"],
        lane_assessments=lane_assessments,
        watchdog_finding_count=data.get("watchdog_finding_count", 0),
        active_failure_count=data.get("active_failure_count", 0),
        recommendations=recommendations,
        summary=data.get("summary", {}),
    )


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_supervisor_text(result: SupervisorCycleResult) -> str:
    """Format a supervisor cycle result as human-readable text.

    Args:
        result: The supervisor cycle result.

    Returns:
        Multi-line text summary.
    """
    lines: list[str] = []
    snap = result.snapshot

    lines.append("=== Supervisor Report ===")
    lines.append(f"Timestamp: {snap.timestamp}")
    lines.append("")

    # Summary
    s = snap.summary
    lines.append(
        f"Lanes: {s.get('total_lanes', 0)} total"
        f" ({s.get('healthy', 0)} healthy"
        f", {s.get('degraded', 0)} degraded"
        f", {s.get('critical', 0)} critical"
        f", {s.get('idle', 0)} idle)"
    )
    lines.append(
        f"Findings: {snap.watchdog_finding_count}"
        f"  Failures: {snap.active_failure_count}"
        f"  Attention: {s.get('attention_needed', 0)}"
    )
    lines.append("")

    # Lane health table
    if snap.lane_assessments:
        lines.append("Lane Health:")
        for la in snap.lane_assessments:
            badge = _health_badge(la.health)
            task_str = f"  {la.current_task}" if la.current_task else ""
            pr_str = f"  PR #{la.linked_pr}" if la.linked_pr else ""
            finding_str = (
                f"  ({len(la.findings)} finding{'s' if len(la.findings) != 1 else ''})"
                if la.findings
                else ""
            )
            lines.append(
                f"  {la.lane_id:15s} {badge:12s} [{la.state}]"
                f"{task_str}{pr_str}{finding_str}"
            )
        lines.append("")

    # Recommendations
    if snap.recommendations:
        lines.append(f"Recommendations ({len(snap.recommendations)}):")
        for rec in snap.recommendations:
            pri_badge = f"[{rec.priority}]"
            auto_str = " (auto)" if rec.auto_remediable else ""
            lines.append(
                f"  {pri_badge:8s} {rec.lane_id}: "
                f"{rec.action}{auto_str} -- {rec.reason}"
            )
            for step in rec.recovery_steps:
                lines.append(f"           {step}")
        lines.append("")

    # Delta section
    if result.delta is not None:
        delta = result.delta
        if result.has_changes:
            lines.append("--- Delta ---")
            lines.append(f"From: {delta.from_timestamp}  To: {delta.to_timestamp}")

            if delta.health_changes:
                lines.append("  Health changes:")
                for hc in delta.health_changes:
                    lines.append(f"    {hc['lane_id']}: {hc['from']} -> {hc['to']}")

            if delta.new_findings:
                lines.append(f"  New findings: {len(delta.new_findings)}")
                for f in delta.new_findings:
                    lines.append(
                        f"    [{f.get('severity', '?')}] "
                        f"{f.get('watchdog', '?')}: {f.get('message', '?')}"
                    )

            if delta.resolved_findings:
                lines.append(f"  Resolved findings: {len(delta.resolved_findings)}")

            if delta.new_recommendations:
                lines.append(f"  New recommendations: {len(delta.new_recommendations)}")

            if delta.resolved_recommendations:
                lines.append(
                    f"  Resolved recommendations: {len(delta.resolved_recommendations)}"
                )

            if delta.summary_deltas:
                lines.append("  Summary deltas:")
                for key, val in sorted(delta.summary_deltas.items()):
                    sign = "+" if val > 0 else ""
                    lines.append(f"    {key}: {sign}{val}")
        else:
            lines.append("--- Delta: no changes ---")

    return "\n".join(lines)


def format_supervisor_json(result: SupervisorCycleResult) -> dict[str, Any]:
    """Format a supervisor cycle result as a JSON-serializable dict.

    Args:
        result: The supervisor cycle result.

    Returns:
        Dict suitable for JSON serialization.
    """
    snap = result.snapshot

    output: dict[str, Any] = {
        "timestamp": snap.timestamp,
        "summary": snap.summary,
        "lane_assessments": [asdict(la) for la in snap.lane_assessments],
        "recommendations": [asdict(r) for r in snap.recommendations],
        "watchdog_finding_count": snap.watchdog_finding_count,
        "active_failure_count": snap.active_failure_count,
        "has_changes": result.has_changes,
    }

    if result.delta is not None:
        output["delta"] = asdict(result.delta)

    return output


def _health_badge(health: str) -> str:
    """Return a text badge for a health level."""
    badges = {
        "critical": "[CRITICAL]",
        "degraded": "[DEGRADED]",
        "healthy": "[healthy]",
        "idle": "[idle]",
    }
    return badges.get(health, f"[{health}]")
