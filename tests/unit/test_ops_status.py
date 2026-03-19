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
    format_status_json,
    format_status_text,
    get_task_scope,
    load_lane_registry,
    load_sessions,
    load_tasks,
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
