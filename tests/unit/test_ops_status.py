"""Tests for status aggregation (ops/status.py)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.status import (
    STALE_MINUTES,
    LaneStatus,
    StatusReport,
    _branch_short,
    _derive_current_step,
    _find_last_event_for_lane,
    _format_relative_time,
    _probe_fallback_liveness,
    aggregate_status,
    emit_scope_snapshot,
    format_status_json,
    format_status_text,
    get_task_scope,
    load_lane_registry,
    load_sessions,
    load_tasks,
    record_touched_files,
    set_declared_scope,
    synthesize_lane_activity,
    update_task_scope,
)


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temp runtime directory with standard subdirs."""
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "session_metadata").mkdir(parents=True)
    (rd / "task_state").mkdir(parents=True)
    (rd / "events").mkdir(parents=True)
    return rd


def _write_json(directory: Path, filename: str, data: dict) -> None:
    (directory / filename).write_text(json.dumps(data, indent=2))


class TestLoadLaneRegistry:
    """Tests for load_lane_registry()."""

    def test_empty(self, runtime_dir: Path) -> None:
        entries = load_lane_registry(runtime_dir)
        assert entries == []

    def test_reads_entries(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "created_at": "2026-03-18T10:00:00Z",
                "last_active": "2026-03-18T10:00:00Z",
                "session_id": None,
                "ttl_hours": None,
            },
        )
        entries = load_lane_registry(runtime_dir)
        assert len(entries) == 1
        assert entries[0]["lane_id"] == "author-a"


class TestLoadSessions:
    """Tests for load_sessions()."""

    def test_empty(self, runtime_dir: Path) -> None:
        sessions = load_sessions(runtime_dir)
        assert sessions == []

    def test_reads_v2_session(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "session_metadata",
            "test-session.json",
            {
                "schema_version": 2,
                "session_id": "test-uuid",
                "lane_id": "author-a",
                "started_at": "2026-03-18T10:00:00Z",
                "task": "Implement ops CLI",
                "worktree_path": "/tmp/wt-a",
            },
        )
        sessions = load_sessions(runtime_dir)
        assert len(sessions) == 1
        assert sessions[0]["lane_id"] == "author-a"

    def test_infers_v1_lane_id(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "session_metadata",
            "old-session.json",
            {
                "schema_version": 1,
                "session_id": "old-uuid",
                "role": "author",
                "started_at": "2026-03-16T10:00:00Z",
                "worktree_path": "/tmp/wt-author",
            },
        )
        sessions = load_sessions(runtime_dir)
        assert len(sessions) == 1
        assert sessions[0]["lane_id"] == "author-a"

    def test_v1_unmapped_role_uses_role_name(self, runtime_dir: Path) -> None:
        """v1 session with unrecognized role preserves role as lane_id (#907)."""
        _write_json(
            runtime_dir / "session_metadata",
            "bogus-session.json",
            {
                "schema_version": 1,
                "session_id": "bogus-uuid",
                "role": "experiment",
                "started_at": "2026-03-16T10:00:00Z",
                "worktree_path": "/tmp/wt-experiment",
            },
        )
        sessions = load_sessions(runtime_dir)
        assert len(sessions) == 1
        assert sessions[0]["lane_id"] == "experiment"


class TestLoadTasks:
    """Tests for load_tasks()."""

    def test_empty(self, runtime_dir: Path) -> None:
        tasks = load_tasks(runtime_dir)
        assert tasks == []

    def test_reads_v2_task(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "task_state",
            "task-1.json",
            {
                "schema_version": 2,
                "task_id": "task-uuid-1",
                "owner_lane": "author-a",
                "subject": "Write events module",
                "goal": "Implement durable event log",
                "status": "in_progress",
                "in_scope": ["events.py"],
                "out_of_scope": ["reviews.py"],
                "items": [
                    {"id": 1, "description": "Write code", "status": "completed"},
                    {"id": 2, "description": "Write tests", "status": "in_progress"},
                ],
                "blocked_by": [],
                "escalation_triggers": [],
                "progress": None,
                "completion_note": None,
            },
        )
        tasks = load_tasks(runtime_dir)
        assert len(tasks) == 1
        assert tasks[0]["owner_lane"] == "author-a"

    def test_infers_v1_fields(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "task_state",
            "task-old.json",
            {
                "schema_version": 1,
                "task_id": "old-task",
                "subject": "Legacy task",
                "status": "completed",
                "items": [],
            },
        )
        tasks = load_tasks(runtime_dir)
        assert len(tasks) == 1
        assert tasks[0]["owner_lane"] == "unknown"
        assert tasks[0]["goal"] == "Legacy task"
        assert tasks[0]["in_scope"] == []

    def test_v1_owner_inferred_from_session(self, runtime_dir: Path) -> None:
        """v1 task with matching session metadata → owner_lane inferred."""
        _write_json(
            runtime_dir / "session_metadata",
            "session-1.json",
            {
                "schema_version": 2,
                "session_id": "uuid-1",
                "lane_id": "author-a",
                "started_at": "2026-03-18T10:00:00Z",
                "worktree_path": "/tmp/wt-a",
            },
        )
        _write_json(
            runtime_dir / "task_state",
            "task-v1.json",
            {
                "schema_version": 1,
                "task_id": "v1-task",
                "subject": "Legacy task with worktree",
                "status": "in_progress",
                "items": [],
                "worktree_path": "/tmp/wt-a",
            },
        )
        sessions = load_sessions(runtime_dir)
        tasks = load_tasks(runtime_dir, sessions=sessions)
        assert len(tasks) == 1
        assert tasks[0]["owner_lane"] == "author-a"

    def test_v1_owner_unknown_without_session(self, runtime_dir: Path) -> None:
        """v1 task with no matching session → owner_lane stays unknown."""
        _write_json(
            runtime_dir / "task_state",
            "task-v1.json",
            {
                "schema_version": 1,
                "task_id": "v1-task",
                "subject": "Orphan legacy task",
                "status": "completed",
                "items": [],
                "worktree_path": "/tmp/wt-gone",
            },
        )
        tasks = load_tasks(runtime_dir, sessions=[])
        assert len(tasks) == 1
        assert tasks[0]["owner_lane"] == "unknown"


class TestAggregateStatus:
    """Tests for aggregate_status()."""

    def test_empty_runtime(self, runtime_dir: Path) -> None:
        report = aggregate_status(runtime_dir)
        assert len(report.lanes) == 0
        assert len(report.active_tasks) == 0
        assert len(report.blocked_tasks) == 0

    def test_lane_with_active_session(self, runtime_dir: Path) -> None:
        """Lane with session_id set in registry → has_active_session=True."""
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "created_at": "2026-03-18T10:00:00Z",
                "last_active": "2026-03-18T12:00:00Z",
                "session_id": "uuid-1",
                "ttl_hours": None,
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-1.json",
            {
                "schema_version": 2,
                "session_id": "uuid-1",
                "lane_id": "author-a",
                "started_at": "2026-03-18T12:00:00Z",
                "task": "Implement PR-3",
                "worktree_path": "/tmp/wt-a",
                "last_checkpoint": "Phase 3A step 2",
            },
        )

        report = aggregate_status(runtime_dir)
        assert len(report.lanes) == 1
        lane = report.lanes[0]
        assert lane.has_active_session is True
        assert lane.session_task == "Implement PR-3"
        assert lane.last_checkpoint == "Phase 3A step 2"
        # Lane activity fields: active session with no task → active
        assert lane.state == "active"

    def test_preserved_session_not_active(self, runtime_dir: Path) -> None:
        """Preserved session metadata with session_id=None → not active.

        Session metadata files persist after session end for resume/audit.
        They must NOT be treated as proof of a live session. However, old
        session/registry timestamps are stale evidence — the lane shows
        as ``stale`` (not ``active`` and not ``idle``), honestly surfacing
        that *some* past activity existed but may have ended.
        """
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "created_at": "2026-03-18T10:00:00Z",
                "last_active": "2026-03-18T12:00:00Z",
                "session_id": None,
                "ttl_hours": None,
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-old.json",
            {
                "schema_version": 2,
                "session_id": "old-uuid",
                "lane_id": "author-a",
                "started_at": "2026-03-18T10:00:00Z",
                "task": "Previous task",
                "worktree_path": "/tmp/wt-a",
                "last_checkpoint": "Done",
            },
        )

        report = aggregate_status(runtime_dir)
        assert len(report.lanes) == 1
        lane = report.lanes[0]
        assert lane.has_active_session is False
        # Old evidence → stale (not active, not idle)
        assert lane.state == "stale"
        assert lane.liveness_source == "session_metadata"
        # Session task available for context
        assert lane.session_task == "Previous task"

        # Text output shows stale state, not active task display
        text = format_status_text(report)
        assert "stale" in text.lower()
        assert "Previous task" in text

    def test_blocked_task_generates_warning(self, runtime_dir: Path) -> None:
        _write_json(
            runtime_dir / "task_state",
            "task-blocked.json",
            {
                "schema_version": 2,
                "task_id": "blocked-uuid",
                "owner_lane": "author-a",
                "subject": "Blocked task",
                "goal": "Do something",
                "status": "blocked",
                "in_scope": [],
                "out_of_scope": [],
                "items": [],
                "blocked_by": ["Missing dependency"],
                "escalation_triggers": [],
                "progress": None,
                "completion_note": None,
            },
        )

        report = aggregate_status(runtime_dir)
        assert len(report.blocked_tasks) == 1
        assert any("blocked" in w.lower() for w in report.warnings)

    def test_stale_persistent_lane_generates_warning(self, runtime_dir: Path) -> None:
        """Persistent lane with old last_active and no session → stale with warning.

        The old last_active provides stale evidence, so the lane is 'stale'
        (not 'idle') but still generates an attention warning.
        """
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {
                "schema_version": 2,
                "lane_id": "ops",
                "lane_class": "ops",
                "worktree_path": "/tmp/wt-ops",
                "branch": "codex/steward-ops",
                "class": "persistent",
                "created_at": "2026-03-18T10:00:00Z",
                "last_active": "2026-03-18T10:00:00Z",
                "session_id": None,
                "ttl_hours": None,
            },
        )

        report = aggregate_status(runtime_dir)
        assert len(report.lanes) == 1
        assert not report.lanes[0].has_active_session
        assert report.lanes[0].state == "stale"
        assert report.lanes[0].liveness_source == "last_active"
        assert report.lanes[0].attention_needed is True
        assert any("stale" in w.lower() for w in report.warnings)

    def test_idle_persistent_lane_generates_warning(self, runtime_dir: Path) -> None:
        """Persistent lane with no evidence at all → genuinely idle with warning."""
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {
                "schema_version": 2,
                "lane_id": "ops",
                "lane_class": "ops",
                "worktree_path": "/tmp/wt-ops",
                "branch": "codex/steward-ops",
                "class": "persistent",
                "created_at": "2026-03-18T10:00:00Z",
                "last_active": None,
                "session_id": None,
                "ttl_hours": None,
            },
        )

        report = aggregate_status(runtime_dir)
        assert len(report.lanes) == 1
        assert not report.lanes[0].has_active_session
        assert report.lanes[0].state == "idle"
        assert report.lanes[0].liveness_source is None
        assert report.lanes[0].attention_needed is True
        assert any("idle" in w.lower() for w in report.warnings)

    def test_task_categorization(self, runtime_dir: Path) -> None:
        for status, tid in [
            ("pending", "t1"),
            ("in_progress", "t2"),
            ("blocked", "t3"),
            ("completed", "t4"),
        ]:
            _write_json(
                runtime_dir / "task_state",
                f"{tid}.json",
                {
                    "schema_version": 2,
                    "task_id": tid,
                    "owner_lane": "author-a",
                    "subject": f"Task {tid}",
                    "goal": "test",
                    "status": status,
                    "in_scope": [],
                    "out_of_scope": [],
                    "items": [],
                    "blocked_by": ["x"] if status == "blocked" else [],
                    "escalation_triggers": [],
                    "progress": None,
                    "completion_note": None,
                },
            )

        report = aggregate_status(runtime_dir)
        assert len(report.active_tasks) == 2  # pending + in_progress
        assert len(report.blocked_tasks) == 1
        assert len(report.completed_tasks) == 1


class TestFormatters:
    """Tests for format_status_text() and format_status_json()."""

    def test_text_format(self) -> None:
        report = StatusReport()
        text = format_status_text(report)
        assert "Steward Status" in text
        assert "Lane Activity: 0" in text
        assert "Warnings: none" in text

    def test_json_format(self) -> None:
        report = StatusReport()
        data = format_status_json(report)
        assert "lanes" in data
        assert "active_tasks" in data
        assert "blocked_tasks" in data
        assert "warnings" in data
        assert isinstance(data["lanes"], list)

    def test_json_includes_lane_activity_fields(self) -> None:
        """JSON output includes all lane-activity fields."""
        lane = LaneStatus(
            lane_id="author-a",
            lane_class="author",
            worktree_path="/tmp/wt-a",
            branch="codex/steward-author",
            lifecycle_class="persistent",
            has_active_session=True,
            state="active",
            current_task_id="t1",
            current_task_title="Do something",
            current_step="step 2/5",
            linked_pr=985,
            last_progress="2026-03-19T14:00:00Z",
            attention_needed=False,
        )
        report = StatusReport(lanes=[lane])
        data = format_status_json(report)
        lane_json = data["lanes"][0]
        assert lane_json["state"] == "active"
        assert lane_json["current_task_id"] == "t1"
        assert lane_json["current_task_title"] == "Do something"
        assert lane_json["current_step"] == "step 2/5"
        assert lane_json["linked_pr"] == 985
        assert lane_json["last_progress"] == "2026-03-19T14:00:00Z"
        assert lane_json["attention_needed"] is False
        assert lane_json["attention_reason"] is None

    def test_text_shows_warnings(self) -> None:
        report = StatusReport(warnings=["Something is wrong"])
        text = format_status_text(report)
        assert "Warnings: 1" in text
        assert "Something is wrong" in text

    def test_text_shows_attention_section(self) -> None:
        """Text output includes Attention section for flagged lanes."""
        lane = LaneStatus(
            lane_id="author-b",
            lane_class="author",
            worktree_path="/tmp/wt-b",
            branch="codex/steward-author-b",
            lifecycle_class="persistent",
            has_active_session=False,
            state="idle",
            attention_needed=True,
            attention_reason="persistent lane idle with no active session",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "Attention: 1" in text
        assert "author-b" in text
        assert "persistent lane idle" in text


# ---- Lane Activity Synthesis Tests ----


def _make_lane(
    lane_id: str,
    lane_class: str = "author",
    session_id: str | None = None,
    last_active: str | None = None,
    lifecycle_class: str = "persistent",
) -> dict:
    return {
        "schema_version": 2,
        "lane_id": lane_id,
        "lane_class": lane_class,
        "worktree_path": f"/tmp/wt-{lane_id}",
        "branch": f"codex/steward-{lane_id}",
        "class": lifecycle_class,
        "session_id": session_id,
        "last_active": last_active,
    }


def _make_task(
    task_id: str,
    owner_lane: str,
    status: str = "in_progress",
    subject: str = "Test task",
    blocked_by: list[str] | None = None,
    pr_number: int | None = None,
    items: list[dict] | None = None,
    progress: dict | None = None,
) -> dict:
    d: dict = {
        "schema_version": 2,
        "task_id": task_id,
        "owner_lane": owner_lane,
        "subject": subject,
        "status": status,
        "blocked_by": blocked_by or [],
        "items": items or [],
        "progress": progress,
    }
    if pr_number is not None:
        d["pr_number"] = pr_number
    return d


class TestSynthesizeLaneActivity:
    """Tests for synthesize_lane_activity()."""

    def test_active_lane_with_task(self) -> None:
        """Lane with active session + in_progress task → active."""
        now = datetime(2026, 3, 19, 10, 5, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {
            "author-a": {"task": "Fix bug", "started_at": "2026-03-19T10:00:00Z"}
        }
        tasks = {"author-a": [_make_task("t1", "author-a", subject="Fix bug")]}

        result = synthesize_lane_activity(lanes, sessions, tasks, [], now=now)
        assert len(result) == 1
        lane = result[0]
        assert lane.state == "active"
        assert lane.current_task_id == "t1"
        assert lane.current_task_title == "Fix bug"
        assert lane.attention_needed is False

    def test_active_lane_without_task(self) -> None:
        """Lane with active session but no task → still active."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {
            "author-a": {"task": "General work", "started_at": "2026-03-19T10:00:00Z"}
        }

        result = synthesize_lane_activity(lanes, sessions, {}, [])
        assert result[0].state == "active"
        assert result[0].current_task_id is None

    def test_blocked_lane(self) -> None:
        """Lane with blocked task → blocked with attention."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {
            "author-a": {"task": "Fix CI", "started_at": "2026-03-19T10:00:00Z"}
        }
        tasks = {
            "author-a": [
                _make_task(
                    "t1",
                    "author-a",
                    status="blocked",
                    subject="Fix CI",
                    blocked_by=["CI infra down"],
                ),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        lane = result[0]
        assert lane.state == "blocked"
        assert lane.attention_needed is True
        assert "CI infra down" in (lane.attention_reason or "")

    def test_idle_lane_no_session(self) -> None:
        """Lane with no session_id → idle."""
        lanes = [_make_lane("author-b")]
        result = synthesize_lane_activity(lanes, {}, {}, [])
        assert result[0].state == "idle"

    def test_idle_persistent_lane_attention(self) -> None:
        """Idle persistent lane → attention_needed."""
        lanes = [_make_lane("author-b", lifecycle_class="persistent")]
        result = synthesize_lane_activity(lanes, {}, {}, [])
        lane = result[0]
        assert lane.state == "idle"
        assert lane.attention_needed is True
        assert "idle" in (lane.attention_reason or "").lower()

    def test_idle_ephemeral_lane_no_attention(self) -> None:
        """Idle ephemeral lane → no attention flag."""
        lanes = [_make_lane("work-123", lifecycle_class="ephemeral")]
        result = synthesize_lane_activity(lanes, {}, {}, [])
        lane = result[0]
        assert lane.state == "idle"
        assert lane.attention_needed is False

    def test_session_with_pending_task_is_active(self) -> None:
        """Lane with session + pending task → active.

        A pending task with an active session means the lane is running
        and has queued work. The session itself makes it active.
        """
        now = datetime(2026, 3, 19, 10, 5, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "TBD", "started_at": "2026-03-19T10:00:00Z"}}
        tasks = {
            "author-a": [
                _make_task("t1", "author-a", status="pending", subject="Pending")
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [], now=now)
        lane = result[0]
        assert lane.state == "active"
        assert lane.current_task_id == "t1"

    def test_pr_linkage_from_task(self) -> None:
        """PR number derived from task metadata."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {
            "author-a": {"task": "PR work", "started_at": "2026-03-19T10:00:00Z"}
        }
        tasks = {
            "author-a": [
                _make_task("t1", "author-a", subject="PR work", pr_number=985),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        assert result[0].linked_pr == 985

    def test_pr_linkage_from_events(self) -> None:
        """PR number derived from events when not in task."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        events = [
            {
                "event_type": "ci_success",
                "lane_id": "author-a",
                "payload": {"pr_number": 982},
            },
            {
                "event_type": "ci_failure",
                "lane_id": "author-b",
                "payload": {"pr_number": 100},
            },
        ]

        result = synthesize_lane_activity(lanes, sessions, {}, events)
        assert result[0].linked_pr == 982

    def test_pr_linkage_task_takes_precedence(self) -> None:
        """Task pr_number takes precedence over events."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        tasks = {
            "author-a": [_make_task("t1", "author-a", pr_number=985)],
        }
        events = [
            {
                "event_type": "ci_success",
                "lane_id": "author-a",
                "payload": {"pr_number": 982},
            },
        ]

        result = synthesize_lane_activity(lanes, sessions, tasks, events)
        assert result[0].linked_pr == 985

    def test_stale_active_lane(self) -> None:
        """Active lane with old last_progress → stale attention."""
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        old_ts = "2026-03-19T14:00:00+00:00"  # 60 min ago
        lanes = [_make_lane("author-a", session_id="s1", last_active=old_ts)]
        sessions = {"author-a": {"task": "Work", "started_at": old_ts}}
        tasks = {
            "author-a": [
                _make_task(
                    "t1",
                    "author-a",
                    progress={"last_forward_progress_at": old_ts},
                ),
            ],
        }

        result = synthesize_lane_activity(
            lanes, sessions, tasks, [], now=now, stale_minutes=STALE_MINUTES
        )
        lane = result[0]
        assert lane.state == "active"
        assert lane.attention_needed is True
        assert "stale" in (lane.attention_reason or "").lower()
        assert "60min" in (lane.attention_reason or "")

    def test_recent_active_lane_not_stale(self) -> None:
        """Active lane with recent progress → not flagged stale."""
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        recent_ts = "2026-03-19T14:50:00+00:00"  # 10 min ago
        lanes = [_make_lane("author-a", session_id="s1", last_active=recent_ts)]
        sessions = {"author-a": {"task": "Work", "started_at": recent_ts}}

        result = synthesize_lane_activity(
            lanes, sessions, {}, [], now=now, stale_minutes=STALE_MINUTES
        )
        lane = result[0]
        assert lane.state == "active"
        assert lane.attention_needed is False

    def test_current_step_from_items(self) -> None:
        """Current step derived from checklist items."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        tasks = {
            "author-a": [
                _make_task(
                    "t1",
                    "author-a",
                    items=[
                        {"id": 1, "description": "Write code", "status": "completed"},
                        {
                            "id": 2,
                            "description": "Write tests",
                            "status": "in_progress",
                        },
                        {"id": 3, "description": "Run CI", "status": "pending"},
                    ],
                ),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        assert result[0].current_step == "step 2/3: Write tests"

    def test_current_step_from_progress_field(self) -> None:
        """Current step from explicit progress dict."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        tasks = {
            "author-a": [
                _make_task(
                    "t1",
                    "author-a",
                    progress={"last_completed_item": "Finished data migration"},
                ),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        assert result[0].current_step == "Finished data migration"

    def test_multiple_lanes(self) -> None:
        """Multiple lanes synthesized correctly."""
        lanes = [
            _make_lane("author-a", session_id="s1"),
            _make_lane("author-b"),
            _make_lane("ops", lane_class="ops", session_id="s2"),
        ]
        sessions = {
            "author-a": {"task": "Task A", "started_at": "2026-03-19T10:00:00Z"},
            "ops": {"task": "Monitoring", "started_at": "2026-03-19T10:00:00Z"},
        }
        tasks = {
            "author-a": [_make_task("t1", "author-a", subject="Task A")],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        assert len(result) == 3
        states = {r.lane_id: r.state for r in result}
        assert states["author-a"] == "active"
        assert states["author-b"] == "idle"
        assert states["ops"] == "active"

    def test_graceful_degradation_missing_fields(self) -> None:
        """Missing fields degrade gracefully to None/unknown."""
        # Minimal lane data with almost no fields
        lanes = [{"lane_id": "x"}]
        result = synthesize_lane_activity(lanes, {}, {}, [])
        lane = result[0]
        assert lane.lane_id == "x"
        assert lane.state == "idle"  # no session_id → idle
        assert lane.current_task_id is None
        assert lane.linked_pr is None
        assert lane.last_progress is None

    def test_blocked_task_preferred_over_pending(self) -> None:
        """Blocked task is selected as primary over pending task."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        tasks = {
            "author-a": [
                _make_task("t1", "author-a", status="pending", subject="Pending"),
                _make_task(
                    "t2",
                    "author-a",
                    status="blocked",
                    subject="Blocked",
                    blocked_by=["dep"],
                ),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        lane = result[0]
        assert lane.state == "blocked"
        assert lane.current_task_id == "t2"
        assert lane.current_task_title == "Blocked"

    def test_last_progress_mixed_iso_formats(self) -> None:
        """last_progress correctly compares Z, +00:00, and naive timestamps.

        Regression test for P1 finding: lexicographic max() on mixed ISO
        formats gives wrong results (e.g., "Z" < "+00:00" lexicographically).
        """
        now = datetime(2026, 3, 19, 16, 0, 0, tzinfo=timezone.utc)
        # The +00:00 timestamp is actually later, but sorts before Z lexicographically
        lanes = [
            _make_lane(
                "author-a",
                session_id="s1",
                last_active="2026-03-19T14:00:00Z",  # 14:00 UTC
            )
        ]
        sessions = {
            "author-a": {
                "task": "Work",
                "started_at": "2026-03-19T15:00:00+00:00",  # 15:00 UTC — later
            }
        }
        tasks = {
            "author-a": [
                _make_task(
                    "t1",
                    "author-a",
                    progress={
                        "last_forward_progress_at": "2026-03-19T15:30:00",  # naive, 15:30 UTC
                    },
                ),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [], now=now)
        lane = result[0]
        # 15:30 naive (treated as UTC) is the latest — should be selected
        assert lane.last_progress == "2026-03-19T15:30:00"
        # 30 min old — not stale (threshold is 30 min)
        assert lane.attention_needed is False

    def test_last_progress_z_vs_offset(self) -> None:
        """Z suffix and +00:00 represent the same instant — later one wins."""
        now = datetime(2026, 3, 19, 16, 0, 0, tzinfo=timezone.utc)
        lanes = [
            _make_lane(
                "author-a",
                session_id="s1",
                last_active="2026-03-19T15:00:00+00:00",
            )
        ]
        sessions = {
            "author-a": {
                "task": "Work",
                "started_at": "2026-03-19T15:30:00Z",  # Same as +00:00, but later
            }
        }

        result = synthesize_lane_activity(lanes, sessions, {}, [], now=now)
        lane = result[0]
        # 15:30Z is later than 15:00+00:00
        assert lane.last_progress == "2026-03-19T15:30:00Z"


class TestSessionSelectionTimezone:
    """Tests for session selection with mixed ISO formats."""

    def test_session_selection_mixed_formats(self, runtime_dir: Path) -> None:
        """Most recent session selected despite mixed ISO formats.

        Regression test: lexicographic comparison of "Z" vs "+00:00"
        can pick the wrong session.
        """
        # Older session with Z suffix
        _write_json(
            runtime_dir / "session_metadata",
            "session-old.json",
            {
                "schema_version": 2,
                "session_id": "old",
                "lane_id": "author-a",
                "started_at": "2026-03-19T14:00:00Z",
                "task": "Old task",
            },
        )
        # Newer session with +00:00 suffix
        _write_json(
            runtime_dir / "session_metadata",
            "session-new.json",
            {
                "schema_version": 2,
                "session_id": "new",
                "lane_id": "author-a",
                "started_at": "2026-03-19T15:00:00+00:00",
                "task": "New task",
            },
        )
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "session_id": "new",
                "last_active": "2026-03-19T15:00:00+00:00",
            },
        )

        report = aggregate_status(runtime_dir)
        lane = report.lanes[0]
        # Must pick "New task" (15:00) not "Old task" (14:00)
        assert lane.session_task == "New task"

    def test_session_selection_malformed_vs_valid(self, runtime_dir: Path) -> None:
        """Valid session wins over malformed session timestamp.

        Regression test for Codex P2 finding on PR #998:
        _is_newer_session() fell through to lexicographic comparison
        when one timestamp was malformed, causing a bogus timestamp
        to win over a valid one.
        """
        # Session with malformed timestamp
        _write_json(
            runtime_dir / "session_metadata",
            "session-bad.json",
            {
                "schema_version": 2,
                "session_id": "bad",
                "lane_id": "author-a",
                "started_at": "bogus-not-a-timestamp",
                "task": "Bad session",
            },
        )
        # Session with valid timestamp
        _write_json(
            runtime_dir / "session_metadata",
            "session-good.json",
            {
                "schema_version": 2,
                "session_id": "good",
                "lane_id": "author-a",
                "started_at": "2026-03-19T15:00:00+00:00",
                "task": "Good session",
            },
        )
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "session_id": "good",
                "last_active": "2026-03-19T15:00:00+00:00",
            },
        )

        report = aggregate_status(runtime_dir)
        lane = report.lanes[0]
        # Valid timestamp must always win over malformed
        assert lane.session_task == "Good session"

    def test_session_selection_valid_vs_malformed(self, runtime_dir: Path) -> None:
        """Valid session wins regardless of file sort order.

        Files are sorted alphabetically, so this test ensures the valid
        session wins even when the malformed session file sorts later.
        """
        # Valid session (sorts first alphabetically)
        _write_json(
            runtime_dir / "session_metadata",
            "a-session-valid.json",
            {
                "schema_version": 2,
                "session_id": "valid",
                "lane_id": "ops",
                "started_at": "2026-03-19T10:00:00Z",
                "task": "Valid session",
            },
        )
        # Malformed session (sorts second alphabetically)
        _write_json(
            runtime_dir / "session_metadata",
            "z-session-malformed.json",
            {
                "schema_version": 2,
                "session_id": "malformed",
                "lane_id": "ops",
                "started_at": "zzz-definitely-not-a-date",
                "task": "Malformed session",
            },
        )
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {
                "schema_version": 2,
                "lane_id": "ops",
                "lane_class": "ops",
                "worktree_path": "/tmp/wt-ops",
                "branch": "codex/steward-ops",
                "class": "persistent",
                "session_id": "valid",
                "last_active": "2026-03-19T10:00:00Z",
            },
        )

        report = aggregate_status(runtime_dir)
        lane = report.lanes[0]
        # Valid timestamp must always beat malformed
        assert lane.session_task == "Valid session"


class TestParseIsoTimestamp:
    """Tests for _parse_iso_timestamp() edge cases."""

    def test_z_suffix_parsed_correctly(self) -> None:
        """Z-suffix timestamps must parse on Python 3.10+ (not just 3.11+)."""
        from bid_euchre.ops.status import _parse_iso_timestamp

        result = _parse_iso_timestamp("2026-03-19T15:00:00Z")
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 19
        assert result.hour == 15
        assert result.tzinfo is not None

    def test_z_suffix_equals_plus_zero(self) -> None:
        """Z and +00:00 must produce the same datetime."""
        from bid_euchre.ops.status import _parse_iso_timestamp

        z_result = _parse_iso_timestamp("2026-03-19T15:00:00Z")
        offset_result = _parse_iso_timestamp("2026-03-19T15:00:00+00:00")
        assert z_result is not None
        assert offset_result is not None
        assert z_result == offset_result

    def test_none_returns_none(self) -> None:
        from bid_euchre.ops.status import _parse_iso_timestamp

        assert _parse_iso_timestamp(None) is None

    def test_empty_returns_none(self) -> None:
        from bid_euchre.ops.status import _parse_iso_timestamp

        assert _parse_iso_timestamp("") is None

    def test_garbage_returns_none(self) -> None:
        from bid_euchre.ops.status import _parse_iso_timestamp

        assert _parse_iso_timestamp("not-a-timestamp") is None


class TestIsNewerSession:
    """Direct unit tests for _is_newer_session() edge cases."""

    def test_malformed_candidate_loses_to_valid_existing(self) -> None:
        """Malformed candidate must lose to valid existing session.

        Covers the branch at status.py where candidate is malformed but
        existing is valid — existing wins (return False).
        """
        from bid_euchre.ops.status import _is_newer_session

        malformed = {"started_at": "not-a-date"}
        valid = {"started_at": "2026-03-18T12:00:00+00:00"}
        assert not _is_newer_session(malformed, valid)

    def test_valid_candidate_beats_malformed_existing(self) -> None:
        """Valid candidate must beat malformed existing session."""
        from bid_euchre.ops.status import _is_newer_session

        valid = {"started_at": "2026-03-18T12:00:00+00:00"}
        malformed = {"started_at": "garbage"}
        assert _is_newer_session(valid, malformed)

    def test_both_malformed_uses_lexicographic(self) -> None:
        """When both are malformed, lexicographic fallback applies."""
        from bid_euchre.ops.status import _is_newer_session

        a = {"started_at": "zzz"}
        b = {"started_at": "aaa"}
        assert _is_newer_session(a, b)
        assert not _is_newer_session(b, a)


class TestAggregateStatusLaneActivity:
    """Integration tests for lane-activity via aggregate_status()."""

    def test_active_lane_with_task_integration(self, runtime_dir: Path) -> None:
        """Full integration: registry + session + task → active lane.

        Uses timestamps close to UTC now to avoid stale detection.
        The test checks state, task details, PR linkage, and output formats.
        """
        # Use a recent timestamp to avoid stale flagging
        recent = datetime.now(timezone.utc).isoformat()
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "session_id": "uuid-1",
                "last_active": recent,
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-1.json",
            {
                "schema_version": 2,
                "session_id": "uuid-1",
                "lane_id": "author-a",
                "started_at": recent,
                "task": "Lane-activity visibility",
            },
        )
        _write_json(
            runtime_dir / "task_state",
            "t1.json",
            {
                "schema_version": 2,
                "task_id": "t1",
                "owner_lane": "author-a",
                "subject": "Lane-activity visibility",
                "status": "in_progress",
                "pr_number": 985,
                "items": [
                    {"id": 1, "description": "Write code", "status": "completed"},
                    {"id": 2, "description": "Write tests", "status": "in_progress"},
                ],
                "blocked_by": [],
            },
        )

        report = aggregate_status(runtime_dir)
        lane = report.lanes[0]
        assert lane.state == "active"
        assert lane.current_task_id == "t1"
        assert lane.current_task_title == "Lane-activity visibility"
        assert lane.current_step == "step 2/2: Write tests"
        assert lane.linked_pr == 985
        assert lane.attention_needed is False

        # JSON output includes new fields
        data = format_status_json(report)
        lane_json = data["lanes"][0]
        assert lane_json["state"] == "active"
        assert lane_json["linked_pr"] == 985

        # Text output shows lane activity
        text = format_status_text(report)
        assert "[active]" in text
        assert "Lane-activity visibility" in text
        assert "PR #985" in text

    def test_events_provide_pr_linkage(self, runtime_dir: Path) -> None:
        """PR linkage derived from events when not in task metadata."""
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "session_id": "uuid-1",
                "last_active": "2026-03-19T14:00:00Z",
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-1.json",
            {
                "schema_version": 2,
                "session_id": "uuid-1",
                "lane_id": "author-a",
                "started_at": "2026-03-19T14:00:00Z",
                "task": "Work",
            },
        )
        # Write events JSONL
        event_line = json.dumps(
            {
                "event_type": "ci_success",
                "lane_id": "author-a",
                "payload": {"pr_number": 982},
                "timestamp": "2026-03-19T14:00:00Z",
            }
        )
        (runtime_dir / "events" / "events.jsonl").write_text(event_line + "\n")

        report = aggregate_status(runtime_dir)
        assert report.lanes[0].linked_pr == 982


# ---- New helpers and enrichment tests ----


class TestDeriveCurrentStepAllDone:
    """Tests for _derive_current_step when all items completed."""

    def test_all_items_completed(self) -> None:
        """All items completed → 'all N steps done'."""
        task = {
            "items": [
                {"id": 1, "description": "Step A", "status": "completed"},
                {"id": 2, "description": "Step B", "status": "completed"},
                {"id": 3, "description": "Step C", "status": "completed"},
            ],
        }
        assert _derive_current_step(task) == "all 3 steps done"

    def test_single_item_completed(self) -> None:
        task = {"items": [{"id": 1, "description": "Only step", "status": "completed"}]}
        assert _derive_current_step(task) == "all 1 steps done"

    def test_no_items_returns_none(self) -> None:
        task = {"items": []}
        assert _derive_current_step(task) is None

    def test_progress_field_takes_precedence_over_all_done(self) -> None:
        """Explicit progress note wins over checklist summary."""
        task = {
            "progress": {"last_completed_item": "Manual override note"},
            "items": [
                {"id": 1, "description": "Step", "status": "completed"},
            ],
        }
        assert _derive_current_step(task) == "Manual override note"


class TestFindLastEventForLane:
    """Tests for _find_last_event_for_lane()."""

    def test_finds_matching_lane(self) -> None:
        events = [
            {"lane_id": "author-a", "event_type": "ci_success", "timestamp": "T2"},
            {"lane_id": "author-b", "event_type": "ci_failure", "timestamp": "T1"},
        ]
        result = _find_last_event_for_lane(events, "author-a")
        assert result is not None
        assert result["event_type"] == "ci_success"

    def test_returns_first_match_most_recent(self) -> None:
        """Events are most-recent-first, so first match is latest."""
        events = [
            {"lane_id": "ops", "event_type": "task_completed", "timestamp": "T3"},
            {"lane_id": "ops", "event_type": "ci_success", "timestamp": "T2"},
        ]
        result = _find_last_event_for_lane(events, "ops")
        assert result is not None
        assert result["event_type"] == "task_completed"

    def test_no_match_returns_none(self) -> None:
        events = [
            {"lane_id": "author-a", "event_type": "ci_success"},
        ]
        assert _find_last_event_for_lane(events, "ops") is None

    def test_empty_events(self) -> None:
        assert _find_last_event_for_lane([], "author-a") is None


class TestFormatRelativeTime:
    """Tests for _format_relative_time()."""

    def test_minutes(self) -> None:
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert _format_relative_time("2026-03-19T14:55:00+00:00", now=now) == "5m ago"

    def test_hours(self) -> None:
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert _format_relative_time("2026-03-19T13:00:00+00:00", now=now) == "2h ago"

    def test_days(self) -> None:
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert _format_relative_time("2026-03-17T15:00:00+00:00", now=now) == "2d ago"

    def test_days_plus(self) -> None:
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert _format_relative_time("2026-03-10T15:00:00+00:00", now=now) == "9d+"

    def test_now(self) -> None:
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert _format_relative_time("2026-03-19T14:59:50+00:00", now=now) == "now"

    def test_future(self) -> None:
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        assert _format_relative_time("2026-03-19T16:00:00+00:00", now=now) == "now"

    def test_none_returns_dash(self) -> None:
        assert _format_relative_time(None) == "—"

    def test_garbage_returns_dash(self) -> None:
        assert _format_relative_time("not-a-time") == "—"


class TestBranchShort:
    """Tests for _branch_short()."""

    def test_strips_codex_steward_prefix(self) -> None:
        assert _branch_short("codex/steward-author") == "author"

    def test_strips_codex_prefix(self) -> None:
        assert _branch_short("codex/some-branch") == "some-branch"

    def test_strips_refs_heads_prefix(self) -> None:
        assert _branch_short("refs/heads/main") == "main"

    def test_no_prefix(self) -> None:
        assert _branch_short("feature/my-branch") == "feature/my-branch"

    def test_empty(self) -> None:
        assert _branch_short("") == ""


class TestSynthesizeLaneActivityEventEnrichment:
    """Tests for event-enriched lane activity fields."""

    def test_event_context_populated(self) -> None:
        """Last event type and timestamp are populated per lane."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        events = [
            {
                "lane_id": "author-a",
                "event_type": "ci_success",
                "timestamp": "2026-03-19T10:05:00Z",
                "payload": {},
            },
        ]

        result = synthesize_lane_activity(lanes, sessions, {}, events)
        lane = result[0]
        assert lane.last_event_type == "ci_success"
        assert lane.last_event_at == "2026-03-19T10:05:00Z"

    def test_no_events_for_lane(self) -> None:
        """Lane with no matching events → event fields are None."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-19T10:00:00Z"}}
        events = [
            {"lane_id": "ops", "event_type": "scheduler_tick", "timestamp": "T1"},
        ]

        result = synthesize_lane_activity(lanes, sessions, {}, events)
        lane = result[0]
        assert lane.last_event_type is None
        assert lane.last_event_at is None

    def test_event_timestamp_enriches_last_progress(self) -> None:
        """Event timestamp is used in last_progress when it's the most recent."""
        now = datetime(2026, 3, 19, 16, 0, 0, tzinfo=timezone.utc)
        # Session started at 14:00, event at 15:30 — event is more recent
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {
            "author-a": {"task": "Work", "started_at": "2026-03-19T14:00:00+00:00"}
        }
        events = [
            {
                "lane_id": "author-a",
                "event_type": "ci_success",
                "timestamp": "2026-03-19T15:30:00+00:00",
                "payload": {},
            },
        ]

        result = synthesize_lane_activity(lanes, sessions, {}, events, now=now)
        lane = result[0]
        # Event timestamp (15:30) is later than session started_at (14:00)
        assert lane.last_progress == "2026-03-19T15:30:00+00:00"

    def test_stale_lane_with_old_event_shows_event_context(self) -> None:
        """Lane with no session and old event → stale (not idle), shows event type.

        The event is 60min old (> 30min stale threshold), so the fallback
        liveness probe classifies this as 'stale' rather than 'idle'.
        """
        now = datetime(2026, 3, 19, 16, 0, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-b", lifecycle_class="ephemeral")]
        events = [
            {
                "lane_id": "author-b",
                "event_type": "task_completed",
                "timestamp": "2026-03-19T15:00:00+00:00",
                "payload": {},
            },
        ]

        result = synthesize_lane_activity(lanes, {}, {}, events, now=now)
        lane = result[0]
        # Event is 60min old — beyond staleness threshold → stale, not idle
        assert lane.state == "stale"
        assert lane.liveness_source == "events"
        assert lane.last_event_type == "task_completed"
        # Event timestamp used for last_progress
        assert lane.last_progress == "2026-03-19T15:00:00+00:00"


class TestProbeFallbackLiveness:
    """Tests for _probe_fallback_liveness() — the fallback liveness probe."""

    def test_no_evidence_returns_idle(self) -> None:
        """No events, tasks, session, or last_active → genuinely idle."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is False
        assert probe.is_stale is False
        assert probe.source is None

    def test_recent_event_returns_likely_live(self) -> None:
        """Event within stale threshold → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": "2026-03-20T11:50:00+00:00",
            },
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=events,
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is True
        assert probe.is_stale is False
        assert probe.source == "events"

    def test_stale_event_returns_stale(self) -> None:
        """Event beyond stale threshold, no fresher signals → stale."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": "2026-03-20T11:00:00+00:00",  # 60min ago
            },
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=events,
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is False
        assert probe.is_stale is True
        assert probe.source == "events"

    def test_recent_task_progress_returns_likely_live(self) -> None:
        """In-progress task with recent progress → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        tasks = [
            _make_task(
                "t1",
                "author-b",
                status="in_progress",
                subject="Fix bug",
                progress={"last_forward_progress_at": "2026-03-20T11:45:00+00:00"},
            ),
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=tasks,
            events=[],
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is True
        assert probe.source == "task_state"

    def test_recent_session_metadata_returns_likely_live(self) -> None:
        """Session started recently → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        session = {"started_at": "2026-03-20T11:55:00+00:00", "task": "Work"}
        probe = _probe_fallback_liveness(
            "author-b",
            session=session,
            lane_tasks=[],
            events=[],
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is True
        assert probe.source == "session_metadata"

    def test_recent_last_active_returns_likely_live(self) -> None:
        """Registry last_active recent → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=[],
            last_active_ts="2026-03-20T11:40:00+00:00",
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is True
        assert probe.source == "last_active"

    def test_fresh_signal_takes_priority_over_stale(self) -> None:
        """Stale event + recent task progress → likely_active from task."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_failure",
                "timestamp": "2026-03-20T10:00:00+00:00",  # 2h ago
            },
        ]
        tasks = [
            _make_task(
                "t1",
                "author-b",
                status="in_progress",
                subject="Fix bug",
                progress={"last_forward_progress_at": "2026-03-20T11:50:00+00:00"},
            ),
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=tasks,
            events=events,
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is True
        assert probe.source == "task_state"

    def test_events_for_other_lane_ignored(self) -> None:
        """Events for a different lane don't count as evidence."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "lane_id": "author-a",
                "event_type": "ci_success",
                "timestamp": "2026-03-20T11:55:00+00:00",
            },
        ]
        probe = _probe_fallback_liveness(
            "author-b",
            session=None,
            lane_tasks=[],
            events=events,
            last_active_ts=None,
            now=now,
            stale_minutes=30,
        )
        assert probe.is_likely_live is False
        assert probe.is_stale is False
        assert probe.source is None

    def test_dirty_worktree_returns_likely_live(self, tmp_path: Path) -> None:
        """Dirty worktree with no other evidence → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        # Create a fake worktree dir so is_worktree_dirty can find it
        wt = tmp_path / "wt-author-b"
        wt.mkdir()
        # Mock is_worktree_dirty to return True
        import unittest.mock as mock

        with mock.patch(
            "bid_euchre.ops.worktrees.is_worktree_dirty", return_value=True
        ):
            probe = _probe_fallback_liveness(
                "author-b",
                session=None,
                lane_tasks=[],
                events=[],
                last_active_ts=None,
                now=now,
                stale_minutes=30,
                worktree_path=str(wt),
            )
        assert probe.is_likely_live is True
        assert probe.is_stale is False
        assert probe.source == "worktree_dirty"
        assert "uncommitted changes" in probe.detail

    def test_clean_worktree_returns_idle(self, tmp_path: Path) -> None:
        """Clean worktree with no other evidence → genuinely idle."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        wt = tmp_path / "wt-author-b"
        wt.mkdir()
        import unittest.mock as mock

        with mock.patch(
            "bid_euchre.ops.worktrees.is_worktree_dirty", return_value=False
        ):
            probe = _probe_fallback_liveness(
                "author-b",
                session=None,
                lane_tasks=[],
                events=[],
                last_active_ts=None,
                now=now,
                stale_minutes=30,
                worktree_path=str(wt),
            )
        assert probe.is_likely_live is False
        assert probe.is_stale is False
        assert probe.source is None

    def test_worktree_file_not_found_degrades_gracefully(self) -> None:
        """FileNotFoundError from is_worktree_dirty → skip signal, idle."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        import unittest.mock as mock

        with mock.patch(
            "bid_euchre.ops.worktrees.is_worktree_dirty",
            side_effect=FileNotFoundError("no such dir"),
        ):
            probe = _probe_fallback_liveness(
                "author-b",
                session=None,
                lane_tasks=[],
                events=[],
                last_active_ts=None,
                now=now,
                stale_minutes=30,
                worktree_path="/nonexistent/path",
            )
        assert probe.is_likely_live is False
        assert probe.source is None

    def test_worktree_subprocess_error_degrades_gracefully(self) -> None:
        """Generic exception from is_worktree_dirty → skip signal, idle."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        import unittest.mock as mock

        with mock.patch(
            "bid_euchre.ops.worktrees.is_worktree_dirty",
            side_effect=OSError("subprocess failed"),
        ):
            probe = _probe_fallback_liveness(
                "author-b",
                session=None,
                lane_tasks=[],
                events=[],
                last_active_ts=None,
                now=now,
                stale_minutes=30,
                worktree_path="/some/path",
            )
        assert probe.is_likely_live is False
        assert probe.source is None

    def test_worktree_check_skipped_when_disabled(self) -> None:
        """check_worktree=False → is_worktree_dirty never called."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        import unittest.mock as mock

        with mock.patch("bid_euchre.ops.worktrees.is_worktree_dirty") as mock_dirty:
            probe = _probe_fallback_liveness(
                "author-b",
                session=None,
                lane_tasks=[],
                events=[],
                last_active_ts=None,
                now=now,
                stale_minutes=30,
                worktree_path="/some/path",
                check_worktree=False,
            )
        mock_dirty.assert_not_called()
        assert probe.is_likely_live is False
        assert probe.source is None

    def test_worktree_signal_lowest_priority(self) -> None:
        """Fresh event takes priority over dirty worktree."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": "2026-03-20T11:50:00+00:00",
            },
        ]
        import unittest.mock as mock

        with mock.patch(
            "bid_euchre.ops.worktrees.is_worktree_dirty", return_value=True
        ) as mock_dirty:
            probe = _probe_fallback_liveness(
                "author-b",
                session=None,
                lane_tasks=[],
                events=events,
                last_active_ts=None,
                now=now,
                stale_minutes=30,
                worktree_path="/some/path",
            )
        # Fresh event returns early — worktree check never reached
        mock_dirty.assert_not_called()
        assert probe.is_likely_live is True
        assert probe.source == "events"


class TestSynthesizeLaneActivityLiveness:
    """Tests for fallback liveness in synthesize_lane_activity()."""

    def test_likely_active_from_recent_event(self) -> None:
        """No session_id but recent event → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-b")]
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_success",
                "timestamp": "2026-03-20T11:50:00+00:00",
            },
        ]

        result = synthesize_lane_activity(lanes, {}, {}, events, now=now)
        lane = result[0]
        assert lane.state == "likely_active"
        assert lane.liveness_source == "events"
        assert lane.attention_needed is False

    def test_likely_active_from_recent_task(self) -> None:
        """No session_id but in-progress task with recent progress → likely_active."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-b")]
        tasks = {
            "author-b": [
                _make_task(
                    "t1",
                    "author-b",
                    status="in_progress",
                    subject="Fix bug",
                    progress={"last_forward_progress_at": "2026-03-20T11:45:00+00:00"},
                ),
            ],
        }

        result = synthesize_lane_activity(lanes, {}, tasks, [], now=now)
        lane = result[0]
        assert lane.state == "likely_active"
        assert lane.liveness_source == "task_state"

    def test_stale_with_old_event(self) -> None:
        """No session_id, event beyond threshold → stale with attention flag."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-b")]
        events = [
            {
                "lane_id": "author-b",
                "event_type": "ci_failure",
                "timestamp": "2026-03-20T11:00:00+00:00",  # 60min ago
            },
        ]

        result = synthesize_lane_activity(lanes, {}, {}, events, now=now)
        lane = result[0]
        assert lane.state == "stale"
        assert lane.liveness_source == "events"
        assert lane.attention_needed is True
        assert "stale" in (lane.attention_reason or "").lower()

    def test_idle_genuinely_no_evidence(self) -> None:
        """No session_id, no events, no tasks → genuinely idle."""
        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-b")]

        result = synthesize_lane_activity(lanes, {}, {}, [], now=now)
        lane = result[0]
        assert lane.state == "idle"
        assert lane.liveness_source is None

    def test_active_lane_has_registry_liveness_source(self) -> None:
        """Active lane (has session_id) → liveness_source is 'registry'."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-20T12:00:00Z"}}

        result = synthesize_lane_activity(lanes, sessions, {}, [])
        lane = result[0]
        assert lane.state == "active"
        assert lane.liveness_source == "registry"

    def test_blocked_lane_liveness_source(self) -> None:
        """Blocked lane with session_id → liveness_source is 'registry'."""
        lanes = [_make_lane("author-a", session_id="s1")]
        sessions = {"author-a": {"task": "Work", "started_at": "2026-03-20T12:00:00Z"}}
        tasks = {
            "author-a": [
                _make_task("t1", "author-a", status="blocked", blocked_by=["CI"]),
            ],
        }

        result = synthesize_lane_activity(lanes, sessions, tasks, [])
        lane = result[0]
        assert lane.state == "blocked"
        assert lane.liveness_source == "registry"

    def test_likely_active_from_dirty_worktree(self) -> None:
        """No session, no events, no tasks, but dirty worktree → likely_active."""
        import unittest.mock as mock

        now = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
        lanes = [_make_lane("author-b")]  # worktree_path = /tmp/wt-author-b

        with mock.patch(
            "bid_euchre.ops.worktrees.is_worktree_dirty", return_value=True
        ):
            result = synthesize_lane_activity(lanes, {}, {}, [], now=now)

        lane = result[0]
        assert lane.state == "likely_active"
        assert lane.liveness_source == "worktree_dirty"
        # likely_active lanes are not flagged for attention (they're live)
        assert lane.attention_needed is False


class TestLivenessFormatting:
    """Tests for formatting of new liveness states in text and JSON output."""

    def test_text_likely_active_shows_source(self) -> None:
        """likely_active lane shows 'likely active (via source)' in text."""
        lane = LaneStatus(
            lane_id="author-b",
            lane_class="author",
            worktree_path="/tmp/wt-b",
            branch="codex/steward-author-b",
            lifecycle_class="persistent",
            has_active_session=False,
            state="likely_active",
            liveness_source="events",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "[likely_active]" in text
        assert "likely active (via events)" in text

    def test_text_stale_shows_attention(self) -> None:
        """stale lane shows attention flag in text."""
        lane = LaneStatus(
            lane_id="author-b",
            lane_class="author",
            worktree_path="/tmp/wt-b",
            branch="codex/steward-author-b",
            lifecycle_class="persistent",
            has_active_session=False,
            state="stale",
            liveness_source="events",
            attention_needed=True,
            attention_reason="stale heartbeat/evidence (last event 60m ago)",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "[stale!]" in text
        assert "Attention:" in text
        assert "stale heartbeat" in text

    def test_json_includes_liveness_source(self) -> None:
        """JSON output includes liveness_source field for all lanes."""
        lanes = [
            LaneStatus(
                lane_id="a",
                lane_class="author",
                worktree_path="/tmp/a",
                branch="b1",
                lifecycle_class="persistent",
                has_active_session=True,
                state="active",
                liveness_source="registry",
            ),
            LaneStatus(
                lane_id="b",
                lane_class="author",
                worktree_path="/tmp/b",
                branch="b2",
                lifecycle_class="persistent",
                has_active_session=False,
                state="likely_active",
                liveness_source="events",
            ),
            LaneStatus(
                lane_id="c",
                lane_class="author",
                worktree_path="/tmp/c",
                branch="b3",
                lifecycle_class="persistent",
                has_active_session=False,
                state="idle",
                liveness_source=None,
            ),
        ]
        report = StatusReport(lanes=lanes)
        data = format_status_json(report)

        assert data["lanes"][0]["liveness_source"] == "registry"
        assert data["lanes"][1]["liveness_source"] == "events"
        assert data["lanes"][2]["liveness_source"] is None

    def test_state_counts_include_new_states(self) -> None:
        """Summary state counts include likely_active and stale."""
        lanes = [
            LaneStatus(
                lane_id="a",
                lane_class="author",
                worktree_path="/tmp/a",
                branch="b1",
                lifecycle_class="persistent",
                has_active_session=True,
                state="active",
            ),
            LaneStatus(
                lane_id="b",
                lane_class="author",
                worktree_path="/tmp/b",
                branch="b2",
                lifecycle_class="persistent",
                has_active_session=False,
                state="likely_active",
            ),
            LaneStatus(
                lane_id="c",
                lane_class="author",
                worktree_path="/tmp/c",
                branch="b3",
                lifecycle_class="persistent",
                has_active_session=False,
                state="stale",
            ),
        ]
        report = StatusReport(lanes=lanes)
        text = format_status_text(report)
        assert "1 active" in text
        assert "1 likely_active" in text
        assert "1 stale" in text

    def test_text_likely_active_with_session_task(self) -> None:
        """likely_active lane with preserved session task shows it."""
        lane = LaneStatus(
            lane_id="author-b",
            lane_class="author",
            worktree_path="/tmp/wt-b",
            branch="codex/steward-author-b",
            lifecycle_class="persistent",
            has_active_session=False,
            state="likely_active",
            liveness_source="task_state",
            session_task="Previous work",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "likely active (via task_state)" in text
        assert "last: Previous work" in text


class TestMixedRuntimeStatesIntegration:
    """Integration test: multiple lanes with varied states and partial data."""

    def test_multi_lane_mixed_states(self, runtime_dir: Path) -> None:
        """5 lanes: active+task, active+no-task, blocked, idle+session, idle+no-data."""
        recent = datetime.now(timezone.utc).isoformat()

        # Lane 1: active with task and PR
        _write_json(
            runtime_dir / "worktree_registry",
            "author-a.json",
            {
                "schema_version": 2,
                "lane_id": "author-a",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-a",
                "branch": "codex/steward-author",
                "class": "persistent",
                "session_id": "uuid-a",
                "last_active": recent,
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-a.json",
            {
                "schema_version": 2,
                "session_id": "uuid-a",
                "lane_id": "author-a",
                "started_at": recent,
                "task": "Implement lane activity",
            },
        )
        _write_json(
            runtime_dir / "task_state",
            "t-a.json",
            {
                "schema_version": 2,
                "task_id": "t-a",
                "owner_lane": "author-a",
                "subject": "Implement lane activity",
                "status": "in_progress",
                "pr_number": 1025,
                "items": [
                    {"id": 1, "description": "Code", "status": "completed"},
                    {"id": 2, "description": "Test", "status": "in_progress"},
                ],
                "blocked_by": [],
            },
        )

        # Lane 2: active session, no task (ops monitoring)
        _write_json(
            runtime_dir / "worktree_registry",
            "ops.json",
            {
                "schema_version": 2,
                "lane_id": "ops",
                "lane_class": "ops",
                "worktree_path": "/tmp/wt-ops",
                "branch": "codex/steward-ops",
                "class": "persistent",
                "session_id": "uuid-ops",
                "last_active": recent,
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-ops.json",
            {
                "schema_version": 2,
                "session_id": "uuid-ops",
                "lane_id": "ops",
                "started_at": recent,
                "task": "Daily monitoring",
            },
        )

        # Lane 3: blocked task
        _write_json(
            runtime_dir / "worktree_registry",
            "author-b.json",
            {
                "schema_version": 2,
                "lane_id": "author-b",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-b",
                "branch": "codex/steward-author-b",
                "class": "persistent",
                "session_id": "uuid-b",
                "last_active": recent,
            },
        )
        _write_json(
            runtime_dir / "task_state",
            "t-b.json",
            {
                "schema_version": 2,
                "task_id": "t-b",
                "owner_lane": "author-b",
                "subject": "Blocked on CI",
                "status": "blocked",
                "blocked_by": ["CI red on main"],
                "items": [],
            },
        )

        # Lane 4: idle persistent with old session (no active session_id)
        _write_json(
            runtime_dir / "worktree_registry",
            "review.json",
            {
                "schema_version": 2,
                "lane_id": "review",
                "lane_class": "review",
                "worktree_path": "/tmp/wt-review",
                "branch": "codex/steward-review",
                "class": "persistent",
                "session_id": None,
                "last_active": "2026-03-19T10:00:00Z",
            },
        )
        _write_json(
            runtime_dir / "session_metadata",
            "session-review-old.json",
            {
                "schema_version": 2,
                "session_id": "old-review",
                "lane_id": "review",
                "started_at": "2026-03-19T10:00:00Z",
                "task": "Previous review",
            },
        )

        # Lane 5: idle ephemeral with no data at all
        _write_json(
            runtime_dir / "worktree_registry",
            "work-123.json",
            {
                "schema_version": 2,
                "lane_id": "work-123",
                "lane_class": "author",
                "worktree_path": "/tmp/wt-work-123",
                "branch": "work-20260319-123",
                "class": "ephemeral",
                "session_id": None,
                "last_active": None,
            },
        )

        # Add an event for author-a
        event_line = json.dumps(
            {
                "event_type": "ci_success",
                "lane_id": "author-a",
                "payload": {"pr_number": 1025},
                "timestamp": recent,
            }
        )
        (runtime_dir / "events" / "events.jsonl").write_text(event_line + "\n")

        report = aggregate_status(runtime_dir)

        # Verify all 5 lanes present
        assert len(report.lanes) == 5
        by_id = {lane.lane_id: lane for lane in report.lanes}

        # Lane 1: active with task
        assert by_id["author-a"].state == "active"
        assert by_id["author-a"].current_task_id == "t-a"
        assert by_id["author-a"].current_task_title == "Implement lane activity"
        assert by_id["author-a"].current_step == "step 2/2: Test"
        assert by_id["author-a"].linked_pr == 1025
        assert by_id["author-a"].last_event_type == "ci_success"
        assert by_id["author-a"].attention_needed is False

        # Lane 2: active ops
        assert by_id["ops"].state == "active"
        assert by_id["ops"].current_task_id is None
        assert by_id["ops"].session_task == "Daily monitoring"

        # Lane 3: blocked
        assert by_id["author-b"].state == "blocked"
        assert by_id["author-b"].attention_needed is True
        assert "CI red" in (by_id["author-b"].attention_reason or "")

        # Lane 4: stale persistent → attention needed
        # (has session metadata and last_active but they're old → stale)
        assert by_id["review"].state == "stale"
        assert by_id["review"].liveness_source == "session_metadata"
        assert by_id["review"].attention_needed is True
        assert by_id["review"].session_task == "Previous review"

        # Lane 5: idle ephemeral → no attention
        # (no evidence at all — genuinely idle)
        assert by_id["work-123"].state == "idle"
        assert by_id["work-123"].liveness_source is None
        assert by_id["work-123"].attention_needed is False
        assert by_id["work-123"].last_event_type is None

        # Verify JSON output includes summary
        data = format_status_json(report)
        assert "summary" in data
        assert data["summary"]["total_lanes"] == 5
        assert data["summary"]["lanes_by_state"]["active"] == 2
        assert data["summary"]["lanes_by_state"]["blocked"] == 1
        assert data["summary"]["lanes_by_state"]["stale"] == 1
        assert data["summary"]["lanes_by_state"]["idle"] == 1
        assert data["summary"]["active_tasks"] == len(report.active_tasks)
        assert "generated_at" in data["summary"]

        # Verify JSON includes event fields
        lane_a_json = next(l for l in data["lanes"] if l["lane_id"] == "author-a")
        assert lane_a_json["last_event_type"] == "ci_success"
        assert lane_a_json["last_event_at"] is not None

        # Verify text output includes state summary, branch info, and relative time
        text = format_status_text(report)
        assert "lanes (" in text
        assert "2 active" in text
        assert "1 blocked" in text
        assert "1 idle" in text
        assert "1 stale" in text
        assert "@author" in text  # branch shortening
        assert "Attention:" in text
        assert "Blocked on CI" in text


class TestJsonOutputStability:
    """Tests that JSON output has a stable, useful schema for tooling."""

    def test_empty_report_json_schema(self) -> None:
        """Empty report produces a complete, well-formed JSON structure."""
        report = StatusReport()
        data = format_status_json(report)

        # Top-level keys are always present
        assert set(data.keys()) == {
            "summary",
            "lanes",
            "active_tasks",
            "blocked_tasks",
            "completed_tasks",
            "warnings",
        }

        # Summary always present with stable fields
        summary = data["summary"]
        assert isinstance(summary["total_lanes"], int)
        assert isinstance(summary["lanes_by_state"], dict)
        assert isinstance(summary["active_tasks"], int)
        assert isinstance(summary["blocked_tasks"], int)
        assert isinstance(summary["completed_tasks"], int)
        assert isinstance(summary["warnings"], int)
        assert isinstance(summary["generated_at"], str)

    def test_lane_json_has_all_fields(self) -> None:
        """Every lane entry in JSON has the complete field set."""
        lane = LaneStatus(
            lane_id="author-a",
            lane_class="author",
            worktree_path="/tmp/wt-a",
            branch="codex/steward-author",
            lifecycle_class="persistent",
            has_active_session=True,
            state="active",
            last_event_type="ci_success",
            last_event_at="2026-03-19T15:00:00Z",
        )
        report = StatusReport(lanes=[lane])
        data = format_status_json(report)
        lane_json = data["lanes"][0]

        expected_fields = {
            "lane_id",
            "lane_class",
            "state",
            "liveness_source",
            "current_task_id",
            "current_task_title",
            "current_step",
            "linked_pr",
            "last_progress",
            "last_active",
            "attention_needed",
            "attention_reason",
            "worktree_path",
            "branch",
            "lifecycle_class",
            "has_active_session",
            "session_task",
            "last_checkpoint",
            "last_event_type",
            "last_event_at",
        }
        assert set(lane_json.keys()) == expected_fields
        assert lane_json["last_event_type"] == "ci_success"
        assert lane_json["last_event_at"] == "2026-03-19T15:00:00Z"


class TestTextOutputEnhancements:
    """Tests for the improved text output format."""

    def test_state_summary_in_header(self) -> None:
        """Header line includes lane count and state breakdown."""
        lanes = [
            LaneStatus(
                lane_id="a",
                lane_class="author",
                worktree_path="/tmp/a",
                branch="b",
                lifecycle_class="persistent",
                has_active_session=True,
                state="active",
            ),
            LaneStatus(
                lane_id="b",
                lane_class="author",
                worktree_path="/tmp/b",
                branch="b2",
                lifecycle_class="persistent",
                has_active_session=False,
                state="idle",
                attention_needed=True,
                attention_reason="idle",
            ),
        ]
        report = StatusReport(lanes=lanes)
        text = format_status_text(report)
        assert "2 lanes" in text
        assert "1 active" in text
        assert "1 idle" in text

    def test_branch_info_in_lane_row(self) -> None:
        """Lane row includes shortened branch name."""
        lane = LaneStatus(
            lane_id="author-a",
            lane_class="author",
            worktree_path="/tmp/wt-a",
            branch="codex/steward-author",
            lifecycle_class="persistent",
            has_active_session=True,
            state="active",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "@author" in text

    def test_relative_time_in_lane_row(self) -> None:
        """Lane row shows relative time instead of absolute HH:MM."""
        now = datetime(2026, 3, 19, 15, 0, 0, tzinfo=timezone.utc)
        lane = LaneStatus(
            lane_id="author-a",
            lane_class="author",
            worktree_path="/tmp/wt-a",
            branch="b",
            lifecycle_class="persistent",
            has_active_session=True,
            state="active",
            last_progress="2026-03-19T14:45:00+00:00",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report, now=now)
        assert "15m ago" in text

    def test_idle_lane_with_event_context(self) -> None:
        """Idle lane with no session but event → shows last event type."""
        lane = LaneStatus(
            lane_id="work-123",
            lane_class="author",
            worktree_path="/tmp/wt-w",
            branch="work-branch",
            lifecycle_class="ephemeral",
            has_active_session=False,
            state="idle",
            last_event_type="task_completed",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "idle, last event: task_completed" in text

    def test_idle_lane_with_session_shows_last_task(self) -> None:
        """Idle lane with preserved session → shows 'idle, last: task'."""
        lane = LaneStatus(
            lane_id="review",
            lane_class="review",
            worktree_path="/tmp/wt-r",
            branch="codex/steward-review",
            lifecycle_class="persistent",
            has_active_session=False,
            state="idle",
            session_task="Previous review",
            attention_needed=True,
            attention_reason="idle",
        )
        report = StatusReport(lanes=[lane])
        text = format_status_text(report)
        assert "idle, last: Previous review" in text

    def test_no_lanes_shows_none_summary(self) -> None:
        """Empty report shows 0 lanes with 'none' summary."""
        report = StatusReport()
        text = format_status_text(report)
        assert "0 lanes (none)" in text


# ---- Task Scope Management Tests ----


class TestUpdateTaskScope:
    """Tests for update_task_scope()."""

    def test_set_declared_files(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        result = update_task_scope(
            "t1",
            declared_files=["src/bid_euchre/ops/*.py"],
            runtime_dir=runtime_dir,
        )
        assert result["scope"]["declared_files"] == ["src/bid_euchre/ops/*.py"]
        assert result["scope"]["touched_files"] == []

    def test_set_touched_files_replace(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {
                        "declared_files": [],
                        "touched_files": ["old.py"],
                    },
                }
            )
        )
        result = update_task_scope(
            "t1",
            touched_files=["new.py"],
            runtime_dir=runtime_dir,
        )
        assert result["scope"]["touched_files"] == ["new.py"]

    def test_append_touched_deduplicates(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {
                        "declared_files": [],
                        "touched_files": ["a.py", "b.py"],
                    },
                }
            )
        )
        result = update_task_scope(
            "t1",
            touched_files=["b.py", "c.py"],
            append_touched=True,
            runtime_dir=runtime_dir,
        )
        assert result["scope"]["touched_files"] == ["a.py", "b.py", "c.py"]

    def test_creates_scope_object_if_missing(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        result = update_task_scope(
            "t1",
            declared_files=["*.py"],
            runtime_dir=runtime_dir,
        )
        assert "scope" in result
        assert result["scope"]["declared_files"] == ["*.py"]
        assert result["scope"]["touched_files"] == []

    def test_raises_on_missing_task(self, runtime_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            update_task_scope(
                "nonexistent",
                declared_files=["*.py"],
                runtime_dir=runtime_dir,
            )

    @pytest.mark.parametrize(
        "bad_id",
        ["../../etc/passwd", "../secret", "foo/bar", "a\\b", ""],
    )
    def test_rejects_path_traversal(self, runtime_dir: Path, bad_id: str) -> None:
        """task_id with path separators or '..' is rejected (#989)."""
        with pytest.raises(ValueError, match="must not contain"):
            update_task_scope(
                bad_id,
                declared_files=["*.py"],
                runtime_dir=runtime_dir,
            )

    def test_raises_on_no_arguments(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1"})
        )
        with pytest.raises(ValueError, match="At least one"):
            update_task_scope("t1", runtime_dir=runtime_dir)

    def test_atomic_write(self, runtime_dir: Path) -> None:
        """Verify file is rewritten atomically (no .tmp leftover)."""
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        update_task_scope(
            "t1",
            declared_files=["src/*.py"],
            runtime_dir=runtime_dir,
        )
        assert not (runtime_dir / "task_state" / "t1.tmp").exists()
        # Verify file is valid JSON
        data = json.loads((runtime_dir / "task_state" / "t1.json").read_text())
        assert data["scope"]["declared_files"] == ["src/*.py"]

    def test_preserves_other_fields(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "subject": "Do something",
                    "owner_lane": "author-a",
                }
            )
        )
        result = update_task_scope(
            "t1",
            declared_files=["src/*.py"],
            runtime_dir=runtime_dir,
        )
        assert result["subject"] == "Do something"
        assert result["owner_lane"] == "author-a"


class TestGetTaskScope:
    """Tests for get_task_scope()."""

    def test_returns_scope(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "scope": {
                        "declared_files": ["src/*.py"],
                        "touched_files": ["src/a.py"],
                    },
                }
            )
        )
        scope = get_task_scope("t1", runtime_dir=runtime_dir)
        assert scope["declared_files"] == ["src/*.py"]
        assert scope["touched_files"] == ["src/a.py"]

    def test_returns_empty_dict_if_no_scope(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1"})
        )
        scope = get_task_scope("t1", runtime_dir=runtime_dir)
        assert scope == {}

    def test_raises_on_missing_task(self, runtime_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            get_task_scope("nonexistent", runtime_dir=runtime_dir)

    @pytest.mark.parametrize(
        "bad_id",
        ["../../etc/passwd", "../secret", "foo/bar", "a\\b", ""],
    )
    def test_rejects_path_traversal(self, runtime_dir: Path, bad_id: str) -> None:
        """task_id with path separators or '..' is rejected (#989)."""
        with pytest.raises(ValueError, match="must not contain"):
            get_task_scope(bad_id, runtime_dir=runtime_dir)


# ---- Convenience Scope Wrappers (#929) ----


class TestSetDeclaredScope:
    """Tests for set_declared_scope() convenience wrapper."""

    def test_sets_declared_patterns(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        result = set_declared_scope(
            "t1",
            ["src/bid_euchre/ops/*.py", "tests/unit/test_ops_*.py"],
            runtime_dir,
        )
        assert result["scope"]["declared_files"] == [
            "src/bid_euchre/ops/*.py",
            "tests/unit/test_ops_*.py",
        ]

    def test_rejects_empty_patterns(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        with pytest.raises(ValueError, match="non-empty"):
            set_declared_scope("t1", [], runtime_dir)

    def test_raises_on_missing_task(self, runtime_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            set_declared_scope("nonexistent", ["*.py"], runtime_dir)


class TestRecordTouchedFiles:
    """Tests for record_touched_files() convenience wrapper."""

    def test_appends_files(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {
                        "declared_files": ["src/*.py"],
                        "touched_files": ["src/a.py"],
                    },
                }
            )
        )
        result = record_touched_files("t1", ["src/b.py", "src/c.py"], runtime_dir)
        assert result["scope"]["touched_files"] == [
            "src/a.py",
            "src/b.py",
            "src/c.py",
        ]

    def test_deduplicates_on_append(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {
                        "declared_files": [],
                        "touched_files": ["src/a.py"],
                    },
                }
            )
        )
        result = record_touched_files("t1", ["src/a.py", "src/b.py"], runtime_dir)
        assert result["scope"]["touched_files"] == ["src/a.py", "src/b.py"]

    def test_creates_scope_if_missing(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        result = record_touched_files("t1", ["src/new.py"], runtime_dir)
        assert result["scope"]["touched_files"] == ["src/new.py"]

    def test_rejects_empty_files(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )
        with pytest.raises(ValueError, match="non-empty"):
            record_touched_files("t1", [], runtime_dir)

    def test_raises_on_missing_task(self, runtime_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            record_touched_files("nonexistent", ["a.py"], runtime_dir)


# ---- Git-based scope snapshot (#929) ----


class TestEmitScopeSnapshot:
    """Tests for emit_scope_snapshot() -- git-based scope tracking (#929)."""

    @pytest.fixture()
    def runtime_dir(self, tmp_path: Path) -> Path:
        rd = tmp_path / "runtime"
        (rd / "task_state").mkdir(parents=True)
        return rd

    def test_with_changes(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Captures git-changed files into touched_files."""
        import subprocess

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )

        def mock_run(cmd, **kwargs):
            # Both staged and unstaged return files
            if cmd == ["git", "diff", "--name-only", "HEAD"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="src/a.py\nsrc/b.py\n", stderr=""
                )
            if cmd == ["git", "diff", "--name-only"]:
                return subprocess.CompletedProcess(
                    args=cmd, returncode=0, stdout="src/b.py\nsrc/c.py\n", stderr=""
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=1, stdout="", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = emit_scope_snapshot(
            "t1", repo_root=Path("/fake"), runtime_dir=runtime_dir
        )
        assert result is not None
        touched = result["scope"]["touched_files"]
        # Union of staged and unstaged, sorted
        assert sorted(touched) == ["src/a.py", "src/b.py", "src/c.py"]

    def test_no_changes_returns_none(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns None when no files have changed."""
        import subprocess

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = emit_scope_snapshot(
            "t1", repo_root=Path("/fake"), runtime_dir=runtime_dir
        )
        assert result is None

    def test_nonexistent_task_raises(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raises FileNotFoundError for missing task state."""
        import subprocess

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="src/a.py\n", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        with pytest.raises(FileNotFoundError):
            emit_scope_snapshot(
                "nonexistent", repo_root=Path("/fake"), runtime_dir=runtime_dir
            )

    def test_git_failure_graceful(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Git command failure returns None (no crash)."""
        import subprocess

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"task_id": "t1", "status": "in_progress"})
        )

        def mock_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                args=cmd, returncode=128, stdout="", stderr="not a git repo"
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = emit_scope_snapshot(
            "t1", repo_root=Path("/fake"), runtime_dir=runtime_dir
        )
        assert result is None

    def test_appends_to_existing_touched(
        self, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Appends new files to existing touched_files without duplicates."""
        import subprocess

        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {
                        "declared_files": ["src/*.py"],
                        "touched_files": ["src/existing.py"],
                    },
                }
            )
        )

        def mock_run(cmd, **kwargs):
            if cmd == ["git", "diff", "--name-only", "HEAD"]:
                return subprocess.CompletedProcess(
                    args=cmd,
                    returncode=0,
                    stdout="src/existing.py\nsrc/new.py\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)

        result = emit_scope_snapshot(
            "t1", repo_root=Path("/fake"), runtime_dir=runtime_dir
        )
        assert result is not None
        touched = result["scope"]["touched_files"]
        # existing.py should not be duplicated
        assert touched == ["src/existing.py", "src/new.py"]
