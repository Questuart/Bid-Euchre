"""Status aggregation across lanes, sessions, and tasks.

Provides a unified summary of the current state of the steward workspace:
which lanes are active, which sessions are running, which tasks are blocked,
and what needs attention.

The lane-activity view synthesizes current work from existing repo-local
state (worktree registry, session metadata, task state, durable events)
to answer: "which lane is working on which problem right now?"
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("ops.status")

DEFAULT_RUNTIME_DIR = Path(".claude/runtime")

# Minutes after which an active lane with no progress is flagged as stale.
STALE_MINUTES = 30

# Valid lane activity states.
LANE_STATES = frozenset({"active", "blocked", "idle", "unknown"})


@dataclass
class LaneStatus:
    """Status summary for one lane.

    ``has_active_session`` is True only when the worktree registry entry
    has a non-null ``session_id``, indicating the lane is currently owned
    by a running session. Preserved session metadata files (which persist
    after session end for resume/audit) do **not** count as live sessions.

    Lane activity fields (``state``, ``current_task_id``, etc.) are
    derived by ``synthesize_lane_activity()`` from existing repo-local
    state. They degrade gracefully to None/``"unknown"`` when data is
    missing.
    """

    lane_id: str
    lane_class: str
    worktree_path: str
    branch: str
    lifecycle_class: str
    has_active_session: bool
    session_task: str | None = None
    last_active: str | None = None
    last_checkpoint: str | None = None

    # --- Lane activity fields (synthesized) ---
    state: str = "unknown"
    current_task_id: str | None = None
    current_task_title: str | None = None
    current_step: str | None = None
    linked_pr: int | None = None
    last_progress: str | None = None
    attention_needed: bool = False
    attention_reason: str | None = None


@dataclass
class StatusReport:
    """Aggregated status across all lanes, sessions, and tasks."""

    lanes: list[LaneStatus] = field(default_factory=list)
    recent_sessions: list[dict[str, Any]] = field(default_factory=list)
    active_tasks: list[dict[str, Any]] = field(default_factory=list)
    blocked_tasks: list[dict[str, Any]] = field(default_factory=list)
    completed_tasks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def load_lane_registry(runtime_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read all worktree registry entries.

    Delegates to ``worktrees.list_worktrees_registry()`` using the standard
    registry subdirectory under ``runtime_dir``.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        List of registry entry dicts (normalized to v2).
    """
    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR

    from bid_euchre.ops.worktrees import list_worktrees_registry

    return list_worktrees_registry(runtime_dir / "worktree_registry")


def load_sessions(runtime_dir: Path | None = None) -> list[dict[str, Any]]:
    """Read all session metadata entries.

    Handles both v1 and v2 entries, inferring missing v2 fields.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        List of session entry dicts.
    """
    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR

    session_dir = runtime_dir / "session_metadata"
    if not session_dir.exists():
        return []

    sessions: list[dict[str, Any]] = []
    for f in sorted(session_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping malformed session file %s: %s", f.name, e)
            continue

        # v1 → v2 inference: use role name as fallback to preserve uniqueness
        if data.get("schema_version", 1) < 2:
            role = data.get("role", "unknown")
            lane_id_map = {"author": "author-a", "review": "review", "ops": "ops"}
            data.setdefault("lane_id", lane_id_map.get(role, role))

        sessions.append(data)

    return sessions


def _infer_owner_lane(
    sessions: list[dict[str, Any]],
    task_worktree: str | None,
) -> str:
    """Infer owner_lane for a v1 task from session metadata.

    Matches by worktree_path if available, otherwise returns ``"unknown"``.

    Args:
        sessions: All loaded session metadata entries.
        task_worktree: The task's worktree_path, if present.

    Returns:
        Inferred lane_id, or ``"unknown"`` if no match found.
    """
    if not task_worktree:
        return "unknown"

    for session in sessions:
        if session.get("worktree_path") == task_worktree:
            lane_id = session.get("lane_id")
            if lane_id:
                return lane_id
    return "unknown"


def load_tasks(
    runtime_dir: Path | None = None,
    *,
    sessions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Read all task state entries.

    Handles both v1 and v2 entries, inferring missing v2 fields.
    For v1 tasks missing ``owner_lane``, attempts to infer from session
    metadata per the v2 schema contract.

    Args:
        runtime_dir: Override for the runtime directory root.
        sessions: Pre-loaded session metadata for v1 owner inference.
            If None and v1 tasks are found, no inference is attempted.

    Returns:
        List of task entry dicts.
    """
    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR

    task_dir = runtime_dir / "task_state"
    if not task_dir.exists():
        return []

    tasks: list[dict[str, Any]] = []
    for f in sorted(task_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Skipping malformed task file %s: %s", f.name, e)
            continue

        # v1 → v2 inference
        if data.get("schema_version", 1) < 2:
            # Infer owner_lane from session metadata when available
            if "owner_lane" not in data:
                inferred = _infer_owner_lane(sessions or [], data.get("worktree_path"))
                data["owner_lane"] = inferred
            data.setdefault("owner_lane", "unknown")
            data.setdefault("goal", data.get("subject", ""))
            data.setdefault("in_scope", [])
            data.setdefault("out_of_scope", [])
            data.setdefault("escalation_triggers", [])
            data.setdefault("progress", None)
            data.setdefault("completion_note", None)

        tasks.append(data)

    return tasks


def _derive_current_step(task: dict[str, Any]) -> str | None:
    """Extract a human-readable progress note from a task.

    Looks at the task's ``progress`` field first, then counts checklist
    items to produce a "step N/M" summary.

    Args:
        task: Task state dict.

    Returns:
        Short progress string, or None if no progress info is available.
    """
    # Prefer explicit progress field
    progress = task.get("progress")
    if progress and isinstance(progress, dict):
        note = progress.get("last_completed_item") or progress.get("note")
        if note:
            return str(note)

    # Fall back to checklist item counts
    items = task.get("items")
    if items and isinstance(items, list):
        total = len(items)
        done = sum(1 for item in items if item.get("status") == "completed")
        in_prog = [item for item in items if item.get("status") == "in_progress"]
        if in_prog:
            return f"step {done + 1}/{total}: {in_prog[0].get('description', '?')}"
        if done > 0:
            return f"step {done}/{total}"

    return None


def _find_pr_from_events(
    events: list[dict[str, Any]],
    lane_id: str,
) -> int | None:
    """Find the most recent PR number from events for a given lane.

    Scans events (assumed most-recent-first) for payload containing
    ``pr_number``.

    Args:
        events: List of event dicts, most recent first.
        lane_id: Lane to filter by.

    Returns:
        PR number if found, else None.
    """
    for event in events:
        if event.get("lane_id") != lane_id:
            continue
        payload = event.get("payload")
        if isinstance(payload, dict):
            pr = payload.get("pr_number")
            if isinstance(pr, int):
                return pr
    return None


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

    Normalizes the ``Z`` suffix to ``+00:00`` for Python 3.10 compatibility
    (``datetime.fromisoformat`` only handles ``Z`` natively in 3.11+).

    Returns None if the string is missing or unparseable.
    """
    if not ts:
        return None
    try:
        # Normalize Z suffix for Python 3.10 compat
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _max_timestamp(candidates: list[str]) -> str | None:
    """Return the latest ISO 8601 timestamp from a list, using parsed comparison.

    Handles mixed formats (``Z``, ``+00:00``, naive) by parsing each
    candidate to a timezone-aware ``datetime`` before comparing. Entries
    that cannot be parsed are silently skipped.

    Args:
        candidates: ISO 8601 timestamp strings.

    Returns:
        The raw string corresponding to the latest instant, or None if
        no candidates could be parsed.
    """
    best_dt: datetime | None = None
    best_raw: str | None = None
    for raw in candidates:
        dt = _parse_iso_timestamp(raw)
        if dt is not None and (best_dt is None or dt > best_dt):
            best_dt = dt
            best_raw = raw
    return best_raw


def _is_newer_session(
    candidate: dict[str, Any],
    existing: dict[str, Any],
) -> bool:
    """Return True if *candidate* session started after *existing*.

    Uses parsed datetime comparison to handle mixed ISO 8601 formats
    (``Z``, ``+00:00``, naive). Handles all four cases:

    - Both parseable → compare datetimes.
    - Candidate parseable, existing malformed → candidate wins.
    - Candidate malformed, existing parseable → existing wins.
    - Both unparseable → lexicographic fallback.
    """
    c_ts = _parse_iso_timestamp(candidate.get("started_at"))
    e_ts = _parse_iso_timestamp(existing.get("started_at"))
    if c_ts is not None and e_ts is not None:
        return c_ts > e_ts
    if c_ts is not None:
        # Candidate is valid, existing is malformed → candidate wins
        return True
    if e_ts is not None:
        # Existing is valid, candidate is malformed → existing wins
        return False
    # Both unparseable → lexicographic fallback
    return candidate.get("started_at", "") > existing.get("started_at", "")


def synthesize_lane_activity(
    lanes_data: list[dict[str, Any]],
    sessions_by_lane: dict[str, dict[str, Any]],
    tasks_by_lane: dict[str, list[dict[str, Any]]],
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_minutes: int = STALE_MINUTES,
) -> list[LaneStatus]:
    """Synthesize lane-activity view from existing repo-local state.

    Combines worktree registry, session metadata, task state, and durable
    events to produce a per-lane activity summary with derived state,
    current task, PR linkage, and attention flags.

    Args:
        lanes_data: Worktree registry entries.
        sessions_by_lane: Most recent session per lane_id.
        tasks_by_lane: Active (pending/in_progress/blocked) tasks grouped
            by ``owner_lane``.
        events: Recent events, most-recent-first.
        now: Current time for staleness checks (default: UTC now).
        stale_minutes: Minutes without progress before flagging stale.

    Returns:
        List of enriched LaneStatus objects.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    results: list[LaneStatus] = []

    for lane in lanes_data:
        lane_id = lane.get("lane_id", "unknown")
        session = sessions_by_lane.get(lane_id)
        has_active_session = lane.get("session_id") is not None

        # Find the primary task for this lane (prefer in_progress over pending)
        lane_tasks = tasks_by_lane.get(lane_id, [])
        primary_task: dict[str, Any] | None = None
        for t in lane_tasks:
            if t.get("status") == "in_progress":
                primary_task = t
                break
        if primary_task is None:
            for t in lane_tasks:
                if t.get("status") == "blocked":
                    primary_task = t
                    break
        if primary_task is None and lane_tasks:
            primary_task = lane_tasks[0]  # pending

        # Derive state — has_active_session is a bool so the branches
        # are exhaustive; no "unknown" fallback is needed (see #994).
        if primary_task and primary_task.get("status") == "blocked":
            state = "blocked"
        elif has_active_session:
            state = "active"
        else:
            state = "idle"

        # Extract task details
        current_task_id = primary_task.get("task_id") if primary_task else None
        current_task_title = (
            primary_task.get("subject") or primary_task.get("goal")
            if primary_task
            else None
        )
        current_step = _derive_current_step(primary_task) if primary_task else None

        # PR linkage: task metadata first, then events
        linked_pr: int | None = None
        if primary_task:
            pr = primary_task.get("pr_number")
            if isinstance(pr, int):
                linked_pr = pr
        if linked_pr is None:
            linked_pr = _find_pr_from_events(events, lane_id)

        # Last progress: best available timestamp
        last_progress_candidates: list[str] = []
        if primary_task:
            prog = primary_task.get("progress")
            if isinstance(prog, dict):
                ts = prog.get("last_forward_progress_at")
                if ts:
                    last_progress_candidates.append(ts)
        if session:
            ts = session.get("started_at")
            if ts:
                last_progress_candidates.append(ts)
        last_active_ts = lane.get("last_active")
        if last_active_ts:
            last_progress_candidates.append(last_active_ts)

        last_progress = _max_timestamp(last_progress_candidates)

        # Attention flags
        attention_needed = False
        attention_reason: str | None = None

        if state == "blocked":
            attention_needed = True
            blockers = primary_task.get("blocked_by", []) if primary_task else []
            attention_reason = f"blocked: {blockers}" if blockers else "blocked"
        elif state == "active" and last_progress:
            lp_dt = _parse_iso_timestamp(last_progress)
            if lp_dt and (now - lp_dt).total_seconds() / 60 > stale_minutes:
                age_min = int((now - lp_dt).total_seconds() / 60)
                attention_needed = True
                attention_reason = f"stale: no progress for {age_min}min"
        elif state == "idle" and lane.get("class", "persistent") == "persistent":
            attention_needed = True
            attention_reason = "persistent lane idle with no active session"

        lane_status = LaneStatus(
            lane_id=lane_id,
            lane_class=lane.get("lane_class", "unknown"),
            worktree_path=lane.get("worktree_path", ""),
            branch=lane.get("branch", ""),
            lifecycle_class=lane.get("class", "persistent"),
            has_active_session=has_active_session,
            session_task=session.get("task") if session else None,
            last_active=last_active_ts,
            last_checkpoint=session.get("last_checkpoint") if session else None,
            state=state,
            current_task_id=current_task_id,
            current_task_title=current_task_title,
            current_step=current_step,
            linked_pr=linked_pr,
            last_progress=last_progress,
            attention_needed=attention_needed,
            attention_reason=attention_reason,
        )
        results.append(lane_status)

    return results


def _load_recent_events(
    runtime_dir: Path,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Load recent events for lane-activity synthesis.

    Reads the JSONL event log and returns the most recent ``limit``
    entries, most-recent-first.

    Args:
        runtime_dir: Runtime directory root.
        limit: Maximum number of events to return.

    Returns:
        List of event dicts, most recent first.
    """
    events_file = runtime_dir / "events" / "events.jsonl"
    if not events_file.exists():
        return []

    # Read all lines and take the tail (most recent)
    try:
        lines = events_file.read_text().strip().splitlines()
    except OSError:
        return []

    recent_lines = lines[-limit:] if len(lines) > limit else lines
    events: list[dict[str, Any]] = []
    for line in reversed(recent_lines):  # most recent first
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return events


def aggregate_status(runtime_dir: Path | None = None) -> StatusReport:
    """Build a unified status report across lanes, sessions, and tasks.

    Args:
        runtime_dir: Override for the runtime directory root.

    Returns:
        StatusReport with categorized entries and warnings.
    """
    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR

    report = StatusReport()

    # Load data — sessions first so load_tasks can use them for v1 owner inference
    lanes_data = load_lane_registry(runtime_dir)
    sessions_data = load_sessions(runtime_dir)
    tasks_data = load_tasks(runtime_dir, sessions=sessions_data)
    events = _load_recent_events(runtime_dir)

    # Build session lookup by lane_id (most recent per lane, for context).
    # Uses parsed datetime comparison to handle mixed ISO formats.
    sessions_by_lane: dict[str, dict[str, Any]] = {}
    for session in sessions_data:
        lane_id = session.get("lane_id", "")
        if lane_id:
            existing = sessions_by_lane.get(lane_id)
            if existing is None or _is_newer_session(session, existing):
                sessions_by_lane[lane_id] = session

    # Build task lookup by owner_lane (non-completed tasks only)
    tasks_by_lane: dict[str, list[dict[str, Any]]] = {}
    for task in tasks_data:
        owner = task.get("owner_lane", "unknown")
        status = task.get("status", "pending")
        if status != "completed":
            tasks_by_lane.setdefault(owner, []).append(task)

    # Synthesize lane activity from all data sources
    report.lanes = synthesize_lane_activity(
        lanes_data,
        sessions_by_lane,
        tasks_by_lane,
        events,
    )

    # Session metadata files are preserved for resume/audit — they are
    # NOT proof of live sessions. Store as recent_sessions for context.
    report.recent_sessions = sessions_data

    # Categorize tasks
    for task in tasks_data:
        status = task.get("status", "pending")
        if status == "blocked":
            report.blocked_tasks.append(task)
        elif status == "completed":
            report.completed_tasks.append(task)
        elif status in ("pending", "in_progress"):
            report.active_tasks.append(task)

    # Generate warnings from lane attention flags
    for lane in report.lanes:
        if lane.attention_needed and lane.attention_reason:
            report.warnings.append(f"Lane {lane.lane_id!r}: {lane.attention_reason}")

    # Generate warnings from blocked tasks
    for task in report.blocked_tasks:
        blockers = task.get("blocked_by", [])
        report.warnings.append(
            f"Task {task.get('task_id', '?')!r} ({task.get('subject', '?')}) "
            f"is blocked: {blockers}"
        )

    return report


def _format_time_short(ts: str | None) -> str:
    """Format a timestamp as a short HH:MM string for display.

    Falls back to ``"—"`` if the timestamp is missing or unparseable.
    """
    if not ts:
        return "—"
    dt = _parse_iso_timestamp(ts)
    if dt is None:
        return "—"
    return dt.strftime("%H:%M")


def format_status_text(report: StatusReport) -> str:
    """Format a StatusReport as human-readable text.

    Args:
        report: The status report to format.

    Returns:
        Multi-line text summary.
    """
    lines: list[str] = []
    lines.append("=== Steward Status ===")
    lines.append("")

    # Lane Activity
    lines.append(f"Lane Activity: {len(report.lanes)}")
    for lane in report.lanes:
        # State badge
        state_badge = f"[{lane.state}]"
        if lane.attention_needed:
            state_badge = f"[{lane.state}!]"

        # Task info
        if lane.current_task_title:
            task_info = lane.current_task_title
            if lane.current_step:
                task_info += f" ({lane.current_step})"
        elif lane.has_active_session and lane.session_task:
            task_info = lane.session_task
        elif lane.session_task:
            task_info = f"idle, last: {lane.session_task}"
        else:
            task_info = "—"

        # PR info
        pr_info = f"  PR #{lane.linked_pr}" if lane.linked_pr else ""

        # Time
        time_info = f"  {_format_time_short(lane.last_progress)}"

        lines.append(
            f"  {lane.lane_id:15s} {state_badge:12s} {task_info}{pr_info}{time_info}"
        )

    lines.append("")

    # Attention items
    attention_lanes = [l for l in report.lanes if l.attention_needed]
    if attention_lanes:
        lines.append(f"Attention: {len(attention_lanes)}")
        for lane in attention_lanes:
            lines.append(f"  {lane.lane_id}: {lane.attention_reason}")
        lines.append("")

    # Tasks
    active_count = len(report.active_tasks)
    blocked_count = len(report.blocked_tasks)
    completed_count = len(report.completed_tasks)
    lines.append(
        f"Tasks: {active_count} active, {blocked_count} blocked, "
        f"{completed_count} completed"
    )

    for task in report.active_tasks:
        lines.append(
            f"  [{task.get('status', '?')}] {task.get('subject', '?')} "
            f"(owner: {task.get('owner_lane', '?')})"
        )

    for task in report.blocked_tasks:
        lines.append(
            f"  [BLOCKED] {task.get('subject', '?')} — {task.get('blocked_by', [])}"
        )

    lines.append("")

    # Warnings
    if report.warnings:
        lines.append(f"Warnings: {len(report.warnings)}")
        for w in report.warnings:
            lines.append(f"  ⚠ {w}")
    else:
        lines.append("Warnings: none")

    return "\n".join(lines)


def format_status_json(report: StatusReport) -> dict[str, Any]:
    """Format a StatusReport as a JSON-serializable dict.

    Args:
        report: The status report to format.

    Returns:
        Dict suitable for JSON serialization.
    """
    return {
        "lanes": [
            {
                "lane_id": lane.lane_id,
                "lane_class": lane.lane_class,
                "state": lane.state,
                "current_task_id": lane.current_task_id,
                "current_task_title": lane.current_task_title,
                "current_step": lane.current_step,
                "linked_pr": lane.linked_pr,
                "last_progress": lane.last_progress,
                "last_active": lane.last_active,
                "attention_needed": lane.attention_needed,
                "attention_reason": lane.attention_reason,
                "worktree_path": lane.worktree_path,
                "branch": lane.branch,
                "lifecycle_class": lane.lifecycle_class,
                "has_active_session": lane.has_active_session,
                "session_task": lane.session_task,
                "last_checkpoint": lane.last_checkpoint,
            }
            for lane in report.lanes
        ],
        "active_tasks": report.active_tasks,
        "blocked_tasks": report.blocked_tasks,
        "completed_tasks": report.completed_tasks,
        "warnings": report.warnings,
    }


# ---------------------------------------------------------------------------
# Task scope management
# ---------------------------------------------------------------------------


def _validate_task_id(task_id: str) -> None:
    """Validate task_id contains no path traversal sequences.

    Mirrors the validation in ``compaction._validate_session_id`` —
    rejects empty strings and strings containing ``..``, ``/``, or ``\\``.

    Raises:
        ValueError: If the task_id is invalid.
    """
    if not task_id or ".." in task_id or "/" in task_id or "\\" in task_id:
        raise ValueError(
            f"Invalid task_id {task_id!r}: must not contain path separators or '..'"
        )


def update_task_scope(
    task_id: str,
    *,
    declared_files: list[str] | None = None,
    touched_files: list[str] | None = None,
    append_touched: bool = False,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Update scope fields on a task state file.

    Reads the task state JSON, updates the ``scope`` object, and writes
    it back atomically. Creates the ``scope`` key if it does not exist.

    Args:
        task_id: Task identifier (filename stem in ``task_state/``).
        declared_files: Glob patterns for declared file scope. Replaces
            existing ``scope.declared_files`` if provided.
        touched_files: File paths to record as touched. Behavior depends
            on ``append_touched``.
        append_touched: If True, appends ``touched_files`` to the existing
            list (deduplicating). If False, replaces the existing list.
        runtime_dir: Override for the runtime directory root.

    Returns:
        The updated task state dict.

    Raises:
        FileNotFoundError: If the task state file does not exist.
        ValueError: If neither ``declared_files`` nor ``touched_files``
            is provided, or if ``task_id`` contains path traversal.
    """
    _validate_task_id(task_id)

    if declared_files is None and touched_files is None:
        raise ValueError(
            "At least one of declared_files or touched_files must be provided"
        )

    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR

    task_file = runtime_dir / "task_state" / f"{task_id}.json"
    if not task_file.exists():
        raise FileNotFoundError(f"Task state file not found: {task_file}")

    data = json.loads(task_file.read_text())

    # Ensure scope object exists
    if "scope" not in data or not isinstance(data.get("scope"), dict):
        data["scope"] = {"declared_files": [], "touched_files": []}

    scope = data["scope"]

    if declared_files is not None:
        scope["declared_files"] = list(declared_files)

    if touched_files is not None:
        if append_touched:
            existing = scope.get("touched_files", [])
            # Deduplicate while preserving order
            seen = set(existing)
            merged = list(existing)
            for f in touched_files:
                if f not in seen:
                    seen.add(f)
                    merged.append(f)
            scope["touched_files"] = merged
        else:
            scope["touched_files"] = list(touched_files)

    data["scope"] = scope

    # Atomic write with fsync — matches memory.py pattern (see #951, #990)
    content = json.dumps(data, indent=2).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(task_file.parent), suffix=".tmp")
    closed = False
    try:
        os.write(fd, content)
        os.fsync(fd)
        os.close(fd)
        closed = True
        os.replace(tmp, str(task_file))
    except BaseException:
        if not closed:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return data


def get_task_scope(
    task_id: str,
    *,
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Read scope fields from a task state file.

    Args:
        task_id: Task identifier (filename stem in ``task_state/``).
        runtime_dir: Override for the runtime directory root.

    Returns:
        The scope dict (``declared_files``, ``touched_files``), or an
        empty dict if no scope is set.

    Raises:
        FileNotFoundError: If the task state file does not exist.
        ValueError: If the task_id contains path traversal sequences.
    """
    _validate_task_id(task_id)

    if runtime_dir is None:
        runtime_dir = DEFAULT_RUNTIME_DIR

    task_file = runtime_dir / "task_state" / f"{task_id}.json"
    if not task_file.exists():
        raise FileNotFoundError(f"Task state file not found: {task_file}")

    data = json.loads(task_file.read_text())
    return data.get("scope", {})


# ---------------------------------------------------------------------------
# Convenience wrappers for scope producers (#929)
# ---------------------------------------------------------------------------


def set_declared_scope(
    task_id: str,
    patterns: list[str],
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Set declared file-scope patterns for a task.

    Convenience wrapper around ``update_task_scope()`` for use by hooks
    and agents when a task is assigned or its scope is defined.

    Args:
        task_id: Task identifier (filename stem in ``task_state/``).
        patterns: Glob patterns for declared file scope
            (e.g., ``["src/bid_euchre/ops/*.py", "tests/unit/test_ops_*.py"]``).
        runtime_dir: Override for the runtime directory root.

    Returns:
        The updated task state dict.

    Raises:
        FileNotFoundError: If the task state file does not exist.
        ValueError: If ``task_id`` contains path traversal or ``patterns``
            is empty.
    """
    if not patterns:
        raise ValueError("patterns must be a non-empty list of glob strings")
    return update_task_scope(task_id, declared_files=patterns, runtime_dir=runtime_dir)


def record_touched_files(
    task_id: str,
    files: list[str],
    runtime_dir: Path | None = None,
) -> dict[str, Any]:
    """Append touched files to a task's scope tracking.

    Convenience wrapper around ``update_task_scope()`` with
    ``append_touched=True``. Designed for hooks that observe which files
    an agent has modified so that ``check_scope_drift()`` can detect
    out-of-scope edits.

    Args:
        task_id: Task identifier (filename stem in ``task_state/``).
        files: File paths to record as touched. Appended to the existing
            list (duplicates are automatically removed).
        runtime_dir: Override for the runtime directory root.

    Returns:
        The updated task state dict.

    Raises:
        FileNotFoundError: If the task state file does not exist.
        ValueError: If ``task_id`` contains path traversal or ``files``
            is empty.
    """
    if not files:
        raise ValueError("files must be a non-empty list of file paths")
    return update_task_scope(
        task_id,
        touched_files=files,
        append_touched=True,
        runtime_dir=runtime_dir,
    )


# ---------------------------------------------------------------------------
# Git-based scope snapshot (#929)
# ---------------------------------------------------------------------------


def emit_scope_snapshot(
    task_id: str,
    repo_root: Path | None = None,
    runtime_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Snapshot current git changes into a task's ``touched_files`` scope.

    Runs ``git diff --name-only HEAD`` and ``git diff --name-only`` (unstaged)
    from *repo_root* to discover which files the current work has modified,
    then appends them to the task's ``scope.touched_files`` via
    ``record_touched_files()``.

    This is the canonical hook-friendly producer for scope tracking: a
    PostToolUse hook or pre-commit hook can call this after file edits
    so that ``check_scope_drift()`` has data to consume.

    Args:
        task_id: Task identifier (filename stem in ``task_state/``).
        repo_root: Working directory for git commands. Defaults to the
            current working directory.
        runtime_dir: Override for the runtime directory root.

    Returns:
        The updated task state dict, or None if no files have changed.

    Raises:
        FileNotFoundError: If the task state file does not exist.
        ValueError: If ``task_id`` contains path traversal sequences.
    """
    import subprocess

    if repo_root is None:
        repo_root = Path.cwd()

    changed: set[str] = set()

    # Staged changes (relative to HEAD)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    changed.add(line.strip())
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git diff --name-only HEAD failed for task %s: %s", task_id, exc)

    # Unstaged changes
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                if line.strip():
                    changed.add(line.strip())
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("git diff --name-only failed for task %s: %s", task_id, exc)

    if not changed:
        return None

    return record_touched_files(task_id, sorted(changed), runtime_dir)
