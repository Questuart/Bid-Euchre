"""Tests for status aggregation (ops/status.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.status import (
    StatusReport,
    aggregate_status,
    format_status_json,
    format_status_text,
    load_lane_registry,
    load_sessions,
    load_tasks,
)


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temp runtime directory with standard subdirs."""
    rd = tmp_path / "runtime"
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "session_metadata").mkdir(parents=True)
    (rd / "task_state").mkdir(parents=True)
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

    def test_v1_unknown_role_maps_to_unknown(self, runtime_dir: Path) -> None:
        """v1 session with unrecognized role should get lane_id='unknown'."""
        _write_json(
            runtime_dir / "session_metadata",
            "bogus-session.json",
            {
                "schema_version": 1,
                "session_id": "bogus-uuid",
                "role": "bogus_role",
                "started_at": "2026-03-16T10:00:00Z",
                "worktree_path": "/tmp/wt-bogus",
            },
        )
        sessions = load_sessions(runtime_dir)
        assert len(sessions) == 1
        assert sessions[0]["lane_id"] == "unknown"


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
        assert report.lanes[0].has_active_session is True
        assert report.lanes[0].session_task == "Implement PR-3"
        assert report.lanes[0].last_checkpoint == "Phase 3A step 2"

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
        assert report.lanes[0].has_active_session is False
        # Session task available for context but NOT displayed as active work
        assert report.lanes[0].session_task == "Previous task"

        # Text output must show "(idle, last: ...)" not "→ Previous task"
        text = format_status_text(report)
        assert "idle, last: Previous task" in text
        assert "→ Previous task" not in text

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
        assert any("no active session" in w.lower() for w in report.warnings)

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
        assert "Lanes: 0" in text
        assert "Warnings: none" in text

    def test_json_format(self) -> None:
        report = StatusReport()
        data = format_status_json(report)
        assert "lanes" in data
        assert "active_tasks" in data
        assert "blocked_tasks" in data
        assert "warnings" in data
        assert isinstance(data["lanes"], list)

    def test_text_shows_warnings(self) -> None:
        report = StatusReport(warnings=["Something is wrong"])
        text = format_status_text(report)
        assert "Warnings: 1" in text
        assert "Something is wrong" in text
