"""Tests for watchdog rules (ops/watchdogs.py)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.watchdogs import (
    check_heartbeats,
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
