"""Tests for ops monitoring cycle (SP-3-08)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from bid_euchre.ops.monitor import (
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_WARN,
    MonitorFinding,
    check_lane_health,
    check_open_prs,
    check_stale_dispatches,
    format_findings_json,
    format_findings_text,
    run_monitoring_cycle,
)

# ---------------------------------------------------------------------------
# check_lane_health tests
# ---------------------------------------------------------------------------


class TestCheckLaneHealth:
    """Tests for lane health checking."""

    def test_returns_capacity_summary(self, tmp_path: Path) -> None:
        """Always includes a capacity info summary."""
        pool_mock = MagicMock()
        pool_mock.workers = []
        pool_mock.active_count = 0
        pool_mock.idle_count = 2
        pool_mock.parked_count = 1
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 5

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_lane_health(tmp_path)

        info_findings = [f for f in findings if f.severity == SEVERITY_INFO]
        assert len(info_findings) == 1
        assert "capacity=5" in info_findings[0].summary

    def test_flags_active_lane_with_dead_tmux(self, tmp_path: Path) -> None:
        """Active lane with dead tmux pane is flagged HIGH."""
        worker = MagicMock()
        worker.lane_id = "author-a"
        worker.pool_status = "active"
        worker.tmux_alive = False
        worker.current_task_id = "pkt123"
        worker.health = "healthy"

        pool_mock = MagicMock()
        pool_mock.workers = [worker]
        pool_mock.active_count = 1
        pool_mock.idle_count = 0
        pool_mock.parked_count = 0
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 4

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_lane_health(tmp_path)

        high_findings = [f for f in findings if f.severity == SEVERITY_HIGH]
        assert len(high_findings) == 1
        assert "author-a" in high_findings[0].summary
        assert "dead" in high_findings[0].summary

    def test_flags_critical_health(self, tmp_path: Path) -> None:
        """Critical supervisor health is flagged HIGH."""
        worker = MagicMock()
        worker.lane_id = "author-b"
        worker.pool_status = "idle"
        worker.tmux_alive = True
        worker.current_task_id = None
        worker.health = "critical"

        pool_mock = MagicMock()
        pool_mock.workers = [worker]
        pool_mock.active_count = 0
        pool_mock.idle_count = 1
        pool_mock.parked_count = 0
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 5

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_lane_health(tmp_path)

        high_findings = [f for f in findings if f.severity == SEVERITY_HIGH]
        assert len(high_findings) == 1
        assert "critical" in high_findings[0].summary

    def test_handles_snapshot_failure(self, tmp_path: Path) -> None:
        """Gracefully handles pool snapshot failure."""
        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            side_effect=RuntimeError("no registry"),
        ):
            findings = check_lane_health(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "snapshot" in findings[0].summary


# ---------------------------------------------------------------------------
# check_open_prs tests
# ---------------------------------------------------------------------------


class TestCheckOpenPRs:
    """Tests for PR status checking."""

    def test_no_open_prs(self) -> None:
        """Reports info when no PRs are open."""
        result = MagicMock()
        result.returncode = 0
        result.stdout = "[]"

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO
        assert "No open PRs" in findings[0].summary

    def test_flags_conflicting_pr(self) -> None:
        """Conflicting PR is flagged HIGH."""
        prs = [
            {
                "number": 42,
                "title": "Fix something",
                "headRefName": "fix/something",
                "mergeable": "CONFLICTING",
                "statusCheckRollup": [],
            }
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        high = [f for f in findings if f.severity == SEVERITY_HIGH]
        assert len(high) == 1
        assert "merge conflicts" in high[0].summary
        assert "#42" in high[0].summary

    def test_flags_failing_checks(self) -> None:
        """Failing CI checks are flagged WARN."""
        prs = [
            {
                "number": 99,
                "title": "Big feature",
                "headRefName": "feat/big",
                "mergeable": "MERGEABLE",
                "statusCheckRollup": [
                    {"name": "tests", "conclusion": "FAILURE"},
                    {"name": "lint", "conclusion": "SUCCESS"},
                ],
            }
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        warn = [f for f in findings if f.severity == SEVERITY_WARN]
        assert len(warn) == 1
        assert "tests" in warn[0].summary

    def test_handles_gh_failure(self) -> None:
        """Gracefully handles gh command failure."""
        result = MagicMock()
        result.returncode = 1
        result.stderr = "not authenticated"

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN

    def test_handles_gh_not_found(self) -> None:
        """Gracefully handles gh not being installed."""
        with patch("subprocess.run", side_effect=FileNotFoundError("gh")):
            findings = check_open_prs()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN


# ---------------------------------------------------------------------------
# check_stale_dispatches tests
# ---------------------------------------------------------------------------


class TestCheckStaleDispatches:
    """Tests for stale dispatch detection."""

    def test_no_dispatched_packets(self, tmp_path: Path) -> None:
        """No dispatched packets produces no findings."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            return_value=[],
        ):
            findings = check_stale_dispatches(runtime_dir)

        assert len(findings) == 0

    def test_fresh_unacked_packet_not_flagged(self, tmp_path: Path) -> None:
        """A recently-dispatched unacked packet is not flagged."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = MagicMock()
        pkt.packet_id = "pkt001"
        pkt.owner = "author-a"
        pkt.title = "Fresh task"
        pkt.created_at = "2026-03-23T11:45:00Z"  # 15 min ago

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=None),
        ):
            findings = check_stale_dispatches(runtime_dir, now=now)

        assert len(findings) == 0

    def test_stale_unacked_packet_flagged(self, tmp_path: Path) -> None:
        """A dispatched packet unacked for >30min is flagged HIGH."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = MagicMock()
        pkt.packet_id = "pkt002"
        pkt.owner = "author-b"
        pkt.title = "Stale task"
        pkt.created_at = "2026-03-23T11:00:00Z"  # 60 min ago

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=None),
        ):
            findings = check_stale_dispatches(runtime_dir, now=now)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_HIGH
        assert "pkt002" in findings[0].summary
        assert "60" in findings[0].summary

    def test_acked_packet_not_flagged(self, tmp_path: Path) -> None:
        """A dispatched packet that has been acked is not flagged."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = MagicMock()
        pkt.packet_id = "pkt003"
        pkt.owner = "author-a"
        pkt.title = "Acked task"
        pkt.created_at = "2026-03-23T10:00:00Z"  # 120 min ago

        ack_mock = MagicMock()

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=ack_mock),
        ):
            findings = check_stale_dispatches(runtime_dir, now=now)

        assert len(findings) == 0

    def test_custom_stale_threshold(self, tmp_path: Path) -> None:
        """Custom stale_minutes threshold is respected."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = MagicMock()
        pkt.packet_id = "pkt004"
        pkt.owner = "author-c"
        pkt.title = "Threshold test"
        pkt.created_at = "2026-03-23T11:50:00Z"  # 10 min ago

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=None),
        ):
            # With 5-min threshold, should be flagged
            findings = check_stale_dispatches(runtime_dir, now=now, stale_minutes=5)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_HIGH


# ---------------------------------------------------------------------------
# run_monitoring_cycle tests
# ---------------------------------------------------------------------------


class TestRunMonitoringCycle:
    """Tests for the full monitoring cycle."""

    def test_combines_all_checks(self, tmp_path: Path) -> None:
        """Cycle combines lane health, PR, and stale dispatch findings."""
        pool_mock = MagicMock()
        pool_mock.workers = []
        pool_mock.active_count = 0
        pool_mock.idle_count = 0
        pool_mock.parked_count = 0
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 5

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool_mock,
            ),
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[]),
            patch(
                "bid_euchre.ops.monitor._send_findings_to_orchestrator",
                return_value="msg123",
            ),
        ):
            findings = run_monitoring_cycle(
                tmp_path,
                skip_pr_check=True,
                notify_orchestrator=True,
            )

        # Should have at least the capacity summary
        categories = {f.category for f in findings}
        assert "lane_health" in categories

    def test_skip_pr_check(self, tmp_path: Path) -> None:
        """skip_pr_check=True skips PR checking."""
        pool_mock = MagicMock()
        pool_mock.workers = []
        pool_mock.active_count = 0
        pool_mock.idle_count = 0
        pool_mock.parked_count = 0
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 5

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool_mock,
            ),
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[]),
            patch("subprocess.run") as mock_run,
        ):
            findings = run_monitoring_cycle(
                tmp_path,
                skip_pr_check=True,
                notify_orchestrator=False,
            )

        # subprocess.run should NOT have been called (no gh pr list)
        mock_run.assert_not_called()
        categories = {f.category for f in findings}
        assert "pr_status" not in categories

    def test_no_notify(self, tmp_path: Path) -> None:
        """notify_orchestrator=False suppresses inbox messages."""
        pool_mock = MagicMock()
        pool_mock.workers = []
        pool_mock.active_count = 0
        pool_mock.idle_count = 0
        pool_mock.parked_count = 0
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 5

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool_mock,
            ),
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[]),
            patch(
                "bid_euchre.ops.monitor._send_findings_to_orchestrator"
            ) as mock_notify,
        ):
            run_monitoring_cycle(
                tmp_path,
                skip_pr_check=True,
                notify_orchestrator=False,
            )

        mock_notify.assert_not_called()


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------


class TestFormatters:
    """Tests for finding formatters."""

    def test_format_text_empty(self) -> None:
        assert "no findings" in format_findings_text([])

    def test_format_text_with_findings(self) -> None:
        findings = [
            MonitorFinding("lane_health", SEVERITY_HIGH, "Lane dead"),
            MonitorFinding("pr_status", SEVERITY_INFO, "2 open PRs"),
        ]
        text = format_findings_text(findings)
        assert "1 HIGH" in text
        assert "Lane dead" in text
        assert "2 open PRs" in text

    def test_format_json_structure(self) -> None:
        findings = [
            MonitorFinding("lane_health", SEVERITY_WARN, "Something"),
        ]
        data = format_findings_json(findings)
        assert data["total"] == 1
        assert data["warn"] == 1
        assert data["high"] == 0
        assert len(data["findings"]) == 1
        assert data["findings"][0]["category"] == "lane_health"
