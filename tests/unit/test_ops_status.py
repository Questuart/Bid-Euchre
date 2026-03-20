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
        They must NOT be treated as proof of a live session.
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
        assert lane.state == "idle"
        # Session task available for context but NOT displayed as active work
        assert lane.session_task == "Previous task"

        # Text output must show "idle, last: ..." not active task display
        text = format_status_text(report)
        assert "idle, last: Previous task" in text

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

    def test_idle_persistent_lane_generates_warning(self, runtime_dir: Path) -> None:
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
        assert report.lanes[0].state == "idle"
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
