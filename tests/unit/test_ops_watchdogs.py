"""Tests for watchdog rules (ops/watchdogs.py)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.watchdogs import (
    check_ci_stuck,
    check_heartbeats,
    check_scope_drift,
    check_subagent_failures,
    check_task_progress,
    format_watchdog_json,
    format_watchdog_text,
    run_all_watchdogs,
)


@pytest.fixture()
def plans_dir(tmp_path: Path) -> Path:
    """Create a temp plans directory."""
    d = tmp_path / "plans"
    d.mkdir()
    return d


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temp runtime directory."""
    rd = tmp_path / "runtime"
    (rd / "task_state").mkdir(parents=True)
    (rd / "worktree_registry").mkdir(parents=True)
    (rd / "events").mkdir(parents=True)
    return rd


class TestCheckHeartbeats:
    """Tests for check_heartbeats()."""

    def test_no_heartbeat_files(self, plans_dir: Path) -> None:
        findings = check_heartbeats(plans_dir)
        assert findings == []

    def test_fresh_heartbeat(self, plans_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        hb = plans_dir / "arc_d_v2" / "r3"
        hb.mkdir(parents=True)
        (hb / "heartbeat").write_text((now - timedelta(minutes=2)).isoformat())

        findings = check_heartbeats(plans_dir, staleness_minutes=5, now=now)
        assert findings == []

    def test_stale_heartbeat(self, plans_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        hb = plans_dir / "arc_d_v2" / "r3"
        hb.mkdir(parents=True)
        (hb / "heartbeat").write_text((now - timedelta(minutes=10)).isoformat())

        findings = check_heartbeats(plans_dir, staleness_minutes=5, now=now)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "stale" in findings[0].message.lower()

    def test_empty_heartbeat(self, plans_dir: Path) -> None:
        hb = plans_dir / "sub"
        hb.mkdir()
        (hb / "heartbeat").write_text("")

        findings = check_heartbeats(plans_dir)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert "empty" in findings[0].message.lower()

    def test_unparseable_heartbeat(self, plans_dir: Path) -> None:
        hb = plans_dir / "sub"
        hb.mkdir()
        (hb / "heartbeat").write_text("not a timestamp")

        findings = check_heartbeats(plans_dir)
        assert len(findings) == 1
        assert "unparseable" in findings[0].message.lower()

    def test_epoch_timestamp(self, plans_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        hb = plans_dir / "sub"
        hb.mkdir()
        epoch = (now - timedelta(minutes=2)).timestamp()
        (hb / "heartbeat").write_text(str(epoch))

        findings = check_heartbeats(plans_dir, staleness_minutes=5, now=now)
        assert findings == []

    def test_multiple_heartbeats(self, plans_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)

        for name, age_min in [("fresh", 2), ("stale", 20)]:
            d = plans_dir / name
            d.mkdir()
            (d / "heartbeat").write_text((now - timedelta(minutes=age_min)).isoformat())

        findings = check_heartbeats(plans_dir, staleness_minutes=5, now=now)
        assert len(findings) == 1
        assert "stale" in findings[0].target


class TestCheckTaskProgress:
    """Tests for check_task_progress()."""

    def test_no_tasks(self, runtime_dir: Path) -> None:
        findings = check_task_progress(runtime_dir)
        assert findings == []

    def test_completed_task_ignored(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps({"status": "completed", "progress": None})
        )
        findings = check_task_progress(runtime_dir)
        assert findings == []

    def test_in_progress_no_progress_field(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "subject": "Test task",
                    "status": "in_progress",
                    "progress": None,
                }
            )
        )
        findings = check_task_progress(runtime_dir)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert "no progress tracking" in findings[0].message.lower()

    def test_fresh_progress(self, runtime_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "subject": "Active task",
                    "status": "in_progress",
                    "progress": {
                        "last_forward_progress_at": (
                            now - timedelta(minutes=5)
                        ).isoformat(),
                    },
                }
            )
        )
        findings = check_task_progress(runtime_dir, staleness_minutes=30, now=now)
        assert findings == []

    def test_stalled_task_no_blocker(self, runtime_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "subject": "Stalled task",
                    "status": "in_progress",
                    "progress": {
                        "last_forward_progress_at": (
                            now - timedelta(minutes=60)
                        ).isoformat(),
                        "current_blocker": None,
                    },
                }
            )
        )
        findings = check_task_progress(runtime_dir, staleness_minutes=30, now=now)
        assert len(findings) == 1
        assert findings[0].severity == "critical"
        assert "no reported blocker" in findings[0].message.lower()

    def test_stalled_task_with_blocker(self, runtime_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "subject": "Blocked task",
                    "status": "in_progress",
                    "progress": {
                        "last_forward_progress_at": (
                            now - timedelta(minutes=60)
                        ).isoformat(),
                        "current_blocker": "Waiting for CI",
                    },
                }
            )
        )
        findings = check_task_progress(runtime_dir, staleness_minutes=30, now=now)
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert "waiting for ci" in findings[0].message.lower()


class TestRunAllWatchdogs:
    """Tests for run_all_watchdogs()."""

    def test_empty_returns_empty(
        self, plans_dir: Path, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Stub out git worktree list to avoid real worktree detection
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])
        findings = run_all_watchdogs(runtime_dir, plans_dir)
        assert findings == []

    def test_sorts_by_severity(
        self, plans_dir: Path, runtime_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)

        # Stale heartbeat → critical
        d = plans_dir / "sub"
        d.mkdir()
        (d / "heartbeat").write_text((now - timedelta(minutes=20)).isoformat())

        # Task with no progress → warning
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "subject": "No progress",
                    "status": "in_progress",
                    "progress": None,
                }
            )
        )

        findings = run_all_watchdogs(
            runtime_dir,
            plans_dir,
            heartbeat_staleness_minutes=5,
            now=now,
        )
        assert len(findings) >= 2
        # Critical should come before warning
        severities = [f.severity for f in findings]
        assert severities.index("critical") < severities.index("warning")


class TestFormatters:
    """Tests for format functions."""

    def test_text_all_clear(self) -> None:
        text = format_watchdog_text([])
        assert "all clear" in text.lower()

    def test_text_with_findings(self) -> None:
        from bid_euchre.ops.watchdogs import WatchdogFinding

        findings = [
            WatchdogFinding(
                watchdog_name="test",
                severity="critical",
                target="test-target",
                message="Something bad",
                threshold="5min",
                recommended_action="Fix it",
            ),
        ]
        text = format_watchdog_text(findings)
        assert "1 finding" in text
        assert "CRITICAL" in text
        assert "Something bad" in text
        assert "Fix it" in text

    def test_json_format(self) -> None:
        from bid_euchre.ops.watchdogs import WatchdogFinding

        findings = [
            WatchdogFinding(
                watchdog_name="test",
                severity="warning",
                target="t",
                message="msg",
                threshold="10min",
                recommended_action="act",
            ),
        ]
        data = format_watchdog_json(findings)
        assert len(data) == 1
        assert data[0]["watchdog_name"] == "test"
        assert data[0]["severity"] == "warning"


# ---- Phase 3D: New watchdog tests ----


class TestCheckCiStuck:
    """Tests for check_ci_stuck()."""

    def test_no_events(self, runtime_dir: Path) -> None:
        findings = check_ci_stuck(runtime_dir)
        assert findings == []

    def test_recent_ci_failure_not_stuck(self, runtime_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        events_file = runtime_dir / "events" / "events.jsonl"
        events_file.write_text(
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=5)).isoformat(),
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"pr_number": 100, "failure_class": "lint_format"},
                }
            )
            + "\n"
        )
        findings = check_ci_stuck(runtime_dir, stuck_minutes=30, now=now)
        assert findings == []

    def test_old_ci_failure_is_stuck(self, runtime_dir: Path) -> None:
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        events_file = runtime_dir / "events" / "events.jsonl"
        events_file.write_text(
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=60)).isoformat(),
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"pr_number": 100, "failure_class": "lint_format"},
                }
            )
            + "\n"
        )
        findings = check_ci_stuck(runtime_dir, stuck_minutes=30, now=now)
        assert len(findings) == 1
        assert findings[0].watchdog_name == "ci_stuck_check"
        assert findings[0].severity == "warning"
        assert "PR #100" in findings[0].message

    def test_ci_success_clears_stuck(self, runtime_dir: Path) -> None:
        """A ci_success after ci_failure means PR is no longer stuck."""
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=60)).isoformat(),
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"pr_number": 100, "failure_class": "lint"},
                }
            ),
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=5)).isoformat(),
                    "event_type": "ci_success",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"pr_number": 100},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_ci_stuck(runtime_dir, stuck_minutes=30, now=now)
        assert findings == []

    def test_multiple_prs(self, runtime_dir: Path) -> None:
        """Only flags the stuck PR, not the healthy one."""
        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=60)).isoformat(),
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"pr_number": 100, "failure_class": "lint"},
                }
            ),
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=5)).isoformat(),
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-b",
                    "payload": {"pr_number": 200, "failure_class": "test"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_ci_stuck(runtime_dir, stuck_minutes=30, now=now)
        assert len(findings) == 1
        assert "PR #100" in findings[0].message


class TestCheckSubagentFailures:
    """Tests for check_subagent_failures()."""

    def test_no_events(self, runtime_dir: Path) -> None:
        findings = check_subagent_failures(runtime_dir)
        assert findings == []

    def test_below_threshold(self, runtime_dir: Path) -> None:
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = [
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:00:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 1"},
                }
            ),
            json.dumps(
                {
                    "timestamp": "2026-03-18T10:05:00Z",
                    "event_type": "task_failed",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"task_id": "t1", "details": "error 2"},
                }
            ),
        ]
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_subagent_failures(runtime_dir, max_failures=3)
        assert findings == []

    def test_at_threshold(self, runtime_dir: Path) -> None:
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = []
        for i in range(3):
            lines.append(
                json.dumps(
                    {
                        "timestamp": f"2026-03-18T10:0{i}:00Z",
                        "event_type": "task_failed",
                        "source": "hook",
                        "lane_id": "author-a",
                        "payload": {"task_id": "t1", "details": f"error {i}"},
                    }
                )
            )
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_subagent_failures(runtime_dir, max_failures=3)
        assert len(findings) == 1
        assert findings[0].watchdog_name == "subagent_failure_check"
        assert "3 times" in findings[0].message
        assert "reroute" in findings[0].recommended_action.lower()

    def test_high_failure_count_is_critical(self, runtime_dir: Path) -> None:
        """Double the threshold → critical severity."""
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = []
        for i in range(6):
            lines.append(
                json.dumps(
                    {
                        "timestamp": f"2026-03-18T10:0{i}:00Z",
                        "event_type": "task_failed",
                        "source": "hook",
                        "lane_id": "author-a",
                        "payload": {"task_id": "t1", "details": f"error {i}"},
                    }
                )
            )
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_subagent_failures(runtime_dir, max_failures=3)
        assert len(findings) == 1
        assert findings[0].severity == "critical"

    def test_different_tasks_counted_separately(self, runtime_dir: Path) -> None:
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = []
        for task_id in ("t1", "t2"):
            for i in range(2):
                lines.append(
                    json.dumps(
                        {
                            "timestamp": f"2026-03-18T10:0{i}:00Z",
                            "event_type": "task_failed",
                            "source": "hook",
                            "lane_id": "author-a",
                            "payload": {"task_id": task_id, "details": "err"},
                        }
                    )
                )
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_subagent_failures(runtime_dir, max_failures=3)
        assert findings == []  # Neither task reached 3 failures

    def test_target_from_payload(self, runtime_dir: Path) -> None:
        """Uses 'target' field if 'task_id' is absent."""
        events_file = runtime_dir / "events" / "events.jsonl"
        lines = []
        for i in range(3):
            lines.append(
                json.dumps(
                    {
                        "timestamp": f"2026-03-18T10:0{i}:00Z",
                        "event_type": "task_failed",
                        "source": "hook",
                        "lane_id": "author-b",
                        "payload": {"target": "task-x", "details": "boom"},
                    }
                )
            )
        events_file.write_text("\n".join(lines) + "\n")
        findings = check_subagent_failures(runtime_dir, max_failures=3)
        assert len(findings) == 1
        assert "task-x" in findings[0].target


class TestCheckScopeDrift:
    """Tests for check_scope_drift()."""

    def test_no_tasks(self, runtime_dir: Path) -> None:
        findings = check_scope_drift(runtime_dir)
        assert findings == []

    def test_no_scope_field_skipped(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "subject": "Do something",
                }
            )
        )
        findings = check_scope_drift(runtime_dir)
        assert findings == []

    def test_within_scope(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "subject": "Fix watchdogs",
                    "lane_id": "author-a",
                    "scope": {
                        "declared_files": ["src/bid_euchre/ops/*.py"],
                        "touched_files": [
                            "src/bid_euchre/ops/watchdogs.py",
                            "src/bid_euchre/ops/recovery.py",
                        ],
                    },
                }
            )
        )
        findings = check_scope_drift(runtime_dir)
        assert findings == []

    def test_out_of_scope(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "subject": "Fix watchdogs",
                    "lane_id": "author-a",
                    "scope": {
                        "declared_files": ["src/bid_euchre/ops/*.py"],
                        "touched_files": [
                            "src/bid_euchre/ops/watchdogs.py",
                            "src/bid_euchre/strategy/heuristic.py",
                        ],
                    },
                }
            )
        )
        findings = check_scope_drift(runtime_dir)
        assert len(findings) == 1
        assert findings[0].watchdog_name == "scope_drift_check"
        assert "heuristic.py" in findings[0].message

    def test_completed_task_ignored(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "completed",
                    "scope": {
                        "declared_files": ["src/a.py"],
                        "touched_files": ["src/b.py"],
                    },
                }
            )
        )
        findings = check_scope_drift(runtime_dir)
        assert findings == []

    def test_many_out_of_scope_truncated(self, runtime_dir: Path) -> None:
        """More than 5 out-of-scope files are truncated in message."""
        touched = [f"src/other/file{i}.py" for i in range(10)]
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "subject": "Fix",
                    "lane_id": "author-a",
                    "scope": {
                        "declared_files": ["src/bid_euchre/ops/*.py"],
                        "touched_files": touched,
                    },
                }
            )
        )
        findings = check_scope_drift(runtime_dir)
        assert len(findings) == 1
        assert "+5 more" in findings[0].message

    def test_empty_declared_files_skipped(self, runtime_dir: Path) -> None:
        (runtime_dir / "task_state" / "t1.json").write_text(
            json.dumps(
                {
                    "task_id": "t1",
                    "status": "in_progress",
                    "scope": {
                        "declared_files": [],
                        "touched_files": ["src/anything.py"],
                    },
                }
            )
        )
        findings = check_scope_drift(runtime_dir)
        assert findings == []


class TestRunAllWatchdogsPhase3D:
    """Tests that run_all_watchdogs integrates new Phase 3D checks."""

    def test_ci_stuck_included(
        self, runtime_dir: Path, plans_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        now = datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)
        events_file = runtime_dir / "events" / "events.jsonl"
        events_file.write_text(
            json.dumps(
                {
                    "timestamp": (now - timedelta(minutes=60)).isoformat(),
                    "event_type": "ci_failure",
                    "source": "hook",
                    "lane_id": "author-a",
                    "payload": {"pr_number": 100, "failure_class": "lint"},
                }
            )
            + "\n"
        )

        findings = run_all_watchdogs(
            runtime_dir, plans_dir, ci_stuck_minutes=30, now=now
        )
        ci_findings = [f for f in findings if f.watchdog_name == "ci_stuck_check"]
        assert len(ci_findings) == 1

    def test_selective_checks(
        self, runtime_dir: Path, plans_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Can run only specific checks via the checks parameter."""
        from bid_euchre.ops import worktrees as wt_mod

        monkeypatch.setattr(wt_mod, "list_worktrees_git", lambda: [])

        findings = run_all_watchdogs(runtime_dir, plans_dir, checks={"scope_drift"})
        # Should only have run scope_drift (no findings expected here)
        assert findings == []
