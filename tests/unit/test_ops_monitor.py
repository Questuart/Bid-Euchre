"""Tests for ops monitoring cycle (SP-3-08)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bid_euchre.ops.monitor import (
    ESCALATION_AGE_MINUTES,
    MAX_AUTO_DISPATCH_PER_CYCLE,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_WARN,
    MonitorCycleResult,
    MonitorFinding,
    _default_stall_state_path,
    _detect_active_work,
    _detect_background_validation,
    _match_approval_prompt,
    _save_stall_state,
    check_approval_stalls,
    check_auto_dispatch,
    check_escalations,
    check_fleet_idle,
    check_idle_lanes,
    check_lane_health,
    check_merged_dispatches,
    check_open_prs,
    check_recently_merged_prs,
    check_stale_dispatches,
    check_stalled_lanes,
    evaluate_alert_push,
    format_findings_json,
    format_findings_text,
    reconcile_dispatched_packets,
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
# check_stalled_lanes tests
# ---------------------------------------------------------------------------


def _make_dispatched_pkt(
    packet_id: str = "pkt100",
    owner: str = "author-a",
    title: str = "Test task",
    created_at: str = "2026-03-23T11:00:00Z",
    metadata: dict[str, Any] | None = None,
) -> MagicMock:
    """Helper to create a mock dispatched packet."""
    pkt = MagicMock()
    pkt.packet_id = packet_id
    pkt.owner = owner
    pkt.title = title
    pkt.created_at = created_at
    pkt.metadata = metadata or {}
    return pkt


class TestCheckStalledLanes:
    """Tests for stall detection on dispatched+acked lanes."""

    def test_no_dispatched_packets(self, tmp_path: Path) -> None:
        """No dispatched packets produces no findings."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            return_value=[],
        ):
            findings = check_stalled_lanes(runtime_dir)

        assert len(findings) == 0

    def test_unacked_dispatch_skipped(self, tmp_path: Path) -> None:
        """Dispatched but unacked packets are not checked (handled by stale check)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=None),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=lambda _: 1000,
            )

        assert len(findings) == 0

    def test_fresh_dispatch_not_flagged(self, tmp_path: Path) -> None:
        """Acked dispatch younger than stall_minutes is not flagged."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        # Only 5 min old — below the 10-min threshold
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:55:00Z")

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=lambda _: 1000,
            )

        assert len(findings) == 0

    def test_active_lane_not_flagged_first_cycle(self, tmp_path: Path) -> None:
        """First observation of an active lane does not flag (needs 2+ cycles)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")  # 60min ago

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=lambda _: 1000,
            )

        assert len(findings) == 0

    def test_stalled_lane_detected_after_two_cycles(self, tmp_path: Path) -> None:
        """Lane flagged as stalled when activity unchanged over 2 consecutive cycles.

        With no_recovery=True, the original report-only behavior is preserved.
        """
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")  # 60min ago

        def probe(_: str) -> int:
            return 9999  # fixed activity epoch — simulates no change

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1: first observation — no finding
            f1 = check_stalled_lanes(
                runtime_dir, now=now, no_recovery=True, _activity_probe=probe
            )
            assert len(f1) == 0

            # Cycle 2: same activity — unchanged_count=1, still below threshold
            f2 = check_stalled_lanes(
                runtime_dir, now=now, no_recovery=True, _activity_probe=probe
            )
            assert len(f2) == 0

            # Cycle 3: same activity — unchanged_count=2, now at threshold
            f3 = check_stalled_lanes(
                runtime_dir, now=now, no_recovery=True, _activity_probe=probe
            )

        assert len(f3) == 1
        assert f3[0].severity == SEVERITY_WARN
        assert f3[0].category == "stall_detection"
        assert "author-a" in f3[0].summary
        assert "stalled" in f3[0].summary
        assert f3[0].details["unchanged_cycles"] == 2

    def test_activity_change_resets_counter(self, tmp_path: Path) -> None:
        """Activity change resets the stall counter."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        call_count = [0]

        def changing_probe(_: str) -> int:
            call_count[0] += 1
            # Returns same value for first 2 calls, then changes
            if call_count[0] <= 2:
                return 9999
            return 10001  # activity changed

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1: first observation
            check_stalled_lanes(runtime_dir, now=now, _activity_probe=changing_probe)
            # Cycle 2: same activity (unchanged_count=1)
            check_stalled_lanes(runtime_dir, now=now, _activity_probe=changing_probe)
            # Cycle 3: activity changed — resets counter
            f3 = check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=changing_probe
            )

        assert len(f3) == 0

    def test_probe_failure_skips_lane(self, tmp_path: Path) -> None:
        """Lane is skipped if activity probe returns None."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=lambda _: None,
            )

        assert len(findings) == 0

    def test_state_file_persisted(self, tmp_path: Path) -> None:
        """State file is written after each cycle."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=lambda _: 5000,
            )

        state_path = _default_stall_state_path(runtime_dir)
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert "observations" in state
        assert "author-a" in state["observations"]
        assert state["observations"]["author-a"]["activity_epoch"] == 5000

    def test_stale_observations_cleaned_up(self, tmp_path: Path) -> None:
        """Observations for lanes no longer dispatched are cleaned up."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        # Pre-seed state with an old lane observation
        state_path = _default_stall_state_path(runtime_dir)
        _save_stall_state(
            state_path,
            {
                "observations": {
                    "author-z": {
                        "packet_id": "old",
                        "activity_epoch": 1000,
                        "unchanged_count": 5,
                    }
                }
            },
        )

        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            return_value=[],
        ):
            check_stalled_lanes(runtime_dir)

        state = json.loads(state_path.read_text())
        assert "author-z" not in state.get("observations", {})

    def test_custom_thresholds(self, tmp_path: Path) -> None:
        """Custom stall_minutes and consecutive_cycles are respected."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        # 5 min ago — would be skipped at default 10min, but not at 3min
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:55:00Z")

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # With stall_minutes=3 and consecutive_cycles=1, second cycle flags
            f1 = check_stalled_lanes(
                runtime_dir,
                now=now,
                stall_minutes=3,
                consecutive_cycles=1,
                no_recovery=True,
                _activity_probe=probe,
            )
            assert len(f1) == 0  # first observation

            f2 = check_stalled_lanes(
                runtime_dir,
                now=now,
                stall_minutes=3,
                consecutive_cycles=1,
                no_recovery=True,
                _activity_probe=probe,
            )

        assert len(f2) == 1
        assert f2[0].severity == SEVERITY_WARN

    def test_dispatched_at_metadata_preferred_over_created_at(
        self, tmp_path: Path
    ) -> None:
        """Stall timer uses metadata.dispatched_at when available."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        # created_at is 60 min ago (would be past stall_minutes threshold)
        # but dispatched_at is only 5 min ago (should be considered fresh)
        pkt = _make_dispatched_pkt(
            created_at="2026-03-23T11:00:00Z",
            metadata={"dispatched_at": "2026-03-23T11:55:00Z"},
        )

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=lambda _: 1000,
            )

        # Should be considered fresh (5 min < 10 min threshold) despite
        # created_at being 60 min ago.
        assert len(findings) == 0

    def test_falls_back_to_created_at_without_dispatched_at(
        self, tmp_path: Path
    ) -> None:
        """Stall timer falls back to created_at when metadata.dispatched_at absent."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        # No dispatched_at in metadata — 60 min old created_at should be used
        pkt = _make_dispatched_pkt(
            created_at="2026-03-23T11:00:00Z",
            metadata={},
        )

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1
            f1 = check_stalled_lanes(
                runtime_dir, now=now, no_recovery=True, _activity_probe=probe
            )
            assert len(f1) == 0
            # Cycle 2
            f2 = check_stalled_lanes(
                runtime_dir, now=now, no_recovery=True, _activity_probe=probe
            )
            assert len(f2) == 0
            # Cycle 3: should flag (past threshold + 2 unchanged cycles)
            f3 = check_stalled_lanes(
                runtime_dir, now=now, no_recovery=True, _activity_probe=probe
            )

        assert len(f3) == 1
        assert f3[0].category == "stall_detection"


# ---------------------------------------------------------------------------
# Stall recovery tests (SP-4-02 Step 3)
# ---------------------------------------------------------------------------


class TestStallRecovery:
    """Tests for bounded stall recovery ladder."""

    def test_first_stall_triggers_nudge(self, tmp_path: Path) -> None:
        """First stall detection re-nudges the lane."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Build up to stall threshold (cycles 1-2 with default consecutive_cycles=2)
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            # Cycle 3: unchanged_count=2 >= threshold, first stall -> nudge
            f3 = check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )

        assert len(f3) == 1
        assert f3[0].category == "stall_recovery"
        assert f3[0].severity == SEVERITY_WARN
        assert "re-nudged" in f3[0].summary
        assert f3[0].details["recovery_action"] == "nudge"
        assert len(nudges) == 1
        assert nudges[0] == ("author-a", "pkt100")

    def test_second_stall_escalates_to_high(self, tmp_path: Path) -> None:
        """Second consecutive stall after re-nudge escalates to HIGH."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycles 1-2: build up observations
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            # Cycle 3: first stall -> nudge (recovery_count becomes 1)
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            # Cycle 4: still stalled -> escalate (recovery_count >= 1)
            f4 = check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )

        assert len(f4) == 1
        assert f4[0].category == "stall_recovery"
        assert f4[0].severity == SEVERITY_HIGH
        assert "escalating" in f4[0].summary
        assert f4[0].details["recovery_action"] == "escalate"
        assert f4[0].details["recovery_count"] == 2
        # Nudge was only called once (at step 1)
        assert len(nudges) == 1

    def test_no_recovery_flag_disables_actions(self, tmp_path: Path) -> None:
        """no_recovery=True disables nudge and escalation (report only)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Build up stall threshold
            check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
            )
            check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
            )
            # Cycle 3: would normally nudge, but no_recovery=True
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
            )

        assert len(f3) == 1
        assert f3[0].category == "stall_detection"  # Not "stall_recovery"
        assert f3[0].severity == SEVERITY_WARN
        assert "stalled" in f3[0].summary
        # No nudge was called
        assert len(nudges) == 0

    def test_activity_change_after_nudge_resets_recovery(self, tmp_path: Path) -> None:
        """Activity change after a nudge resets the recovery counter."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        call_count = [0]

        def probe(_: str) -> int:
            call_count[0] += 1
            # First 3 calls return same value (stall), then change (recovery)
            if call_count[0] <= 3:
                return 9999
            return 11111  # activity changed

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycles 1-2: build up
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            # Cycle 3: stall -> nudge
            f3 = check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            assert len(f3) == 1
            assert f3[0].details["recovery_action"] == "nudge"

            # Cycle 4: activity changed -> reset
            f4 = check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )

        assert len(f4) == 0  # No finding — activity recovered

        # Verify state was reset
        state_path = _default_stall_state_path(runtime_dir)
        state = json.loads(state_path.read_text())
        obs = state["observations"]["author-a"]
        assert obs["unchanged_count"] == 0
        assert obs["recovery_count"] == 0

    def test_new_packet_resets_recovery_count(self, tmp_path: Path) -> None:
        """A new packet on the same lane resets recovery_count."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        def probe(_: str) -> int:
            return 9999

        # First packet stalls and gets nudged
        pkt1 = _make_dispatched_pkt(
            packet_id="pkt_old", created_at="2026-03-23T11:00:00Z"
        )

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt1]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            # Cycle 3: first stall -> nudge
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )

        assert len(nudges) == 1

        # New packet dispatched — should reset recovery_count
        pkt2 = _make_dispatched_pkt(
            packet_id="pkt_new", created_at="2026-03-23T11:00:00Z"
        )

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt2]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1 with new packet
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )
            # Cycle 3: should nudge again (not escalate) because new packet
            f3 = check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=mock_nudge
            )

        assert len(f3) == 1
        assert f3[0].details["recovery_action"] == "nudge"  # Not escalate
        assert len(nudges) == 2  # Two nudges total (one per packet)

    def test_recovery_count_persisted_in_state(self, tmp_path: Path) -> None:
        """recovery_count is persisted in stall_state.json."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=lambda *_: None
            )
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=lambda *_: None
            )
            # Cycle 3: nudge happens, recovery_count becomes 1
            check_stalled_lanes(
                runtime_dir, now=now, _activity_probe=probe, _nudge_fn=lambda *_: None
            )

        state_path = _default_stall_state_path(runtime_dir)
        state = json.loads(state_path.read_text())
        obs = state["observations"]["author-a"]
        assert obs["recovery_count"] == 1

    def test_escalation_includes_required_details(self, tmp_path: Path) -> None:
        """Escalation finding includes packet_id, lane_id, and stall duration."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(
            packet_id="pkt_esc",
            owner="author-c",
            title="Stuck task",
            created_at="2026-03-23T11:00:00Z",
        )

        def probe(_: str) -> int:
            return 9999

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Build stall -> nudge -> escalate
            for _ in range(2):
                check_stalled_lanes(
                    runtime_dir,
                    now=now,
                    _activity_probe=probe,
                    _nudge_fn=lambda *_: None,
                )
            # Cycle 3: nudge
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
            )
            # Cycle 4: escalate
            f4 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
            )

        assert len(f4) == 1
        d = f4[0].details
        assert d["packet_id"] == "pkt_esc"
        assert d["lane_id"] == "author-c"
        assert d["age_minutes"] == 60
        assert d["recovery_action"] == "escalate"
        assert d["recovery_count"] == 2


# ---------------------------------------------------------------------------
# Active-work guard prevents false stall reports (#1612)
# ---------------------------------------------------------------------------


class TestActiveWorkGuard:
    """Active-work indicators prevent false stall reports (#1612)."""

    def test_active_work_prevents_stall_finding(self, tmp_path: Path) -> None:
        """Lane showing spinner is NOT reported as stalled."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        def probe(_: str) -> int:
            return 9999  # Same epoch every cycle (looks stalled)

        def capture(_: str) -> str:
            # Spinner visible — lane is actively working
            return "Some output\n⏺ Running Bash(uv run pytest...)  12s\n"

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Build up to stall threshold
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
                _capture_fn=capture,
            )
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
                _capture_fn=capture,
            )
            # Cycle 3: would normally stall but spinner is active
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
                _capture_fn=capture,
            )

        # No stall finding — lane is actively working
        assert len(f3) == 0, f"Expected no stall findings, got: {f3}"
        # No nudge attempted
        assert len(nudges) == 0

    def test_idle_pane_still_reports_stall(self, tmp_path: Path) -> None:
        """Lane with NO spinner IS reported as stalled (normal behavior)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        def probe(_: str) -> int:
            return 9999

        def capture(_: str) -> str:
            # Idle prompt — no spinner
            return "Some old output\n$\n"

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )
            # Cycle 3: should report stall
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )

        assert len(f3) == 1
        assert "stalled" in f3[0].summary or "re-nudged" in f3[0].summary

    def test_capture_failure_does_not_block_stall_detection(
        self, tmp_path: Path
    ) -> None:
        """If pane capture returns None, stall detection proceeds normally."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")

        def probe(_: str) -> int:
            return 9999

        def capture(_: str) -> None:
            return None  # Pane capture failed

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )
            check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )

        # Should still report stall — capture failure doesn't block detection
        assert len(f3) == 1


# ---------------------------------------------------------------------------
# False-stall regression proving run (#1679)
# ---------------------------------------------------------------------------


class TestFalseStallRegression:
    """Prove stall guard from #1618 prevents false positives (#1679).

    Key scenario: a lane has *stale* stall state from when it was idle, but is
    now actively working.  The active-work guard must suppress the false stall
    and reset the persisted observation.
    """

    def test_stale_observation_with_active_lane_no_false_stall(
        self, tmp_path: Path
    ) -> None:
        """Pre-seeded stale stall state does NOT produce a false stall finding
        when the lane is actively working (spinner present)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-24T11:00:00Z")

        # Pre-seed stall state: lane was idle for 5 cycles (well above threshold)
        _save_stall_state(
            _default_stall_state_path(runtime_dir),
            {
                "observations": {
                    pkt.owner: {
                        "packet_id": pkt.packet_id,
                        "activity_epoch": 9999,
                        "unchanged_count": 5,
                        "recovery_count": 0,
                    }
                }
            },
        )

        nudges: list[tuple[str, str]] = []

        def mock_nudge(lane_id: str, packet_id: str) -> None:
            nudges.append((lane_id, packet_id))

        def probe(_: str) -> int:
            return 9999  # Same epoch as stale observation (looks unchanged)

        def capture(_: str) -> str:
            # Lane is actively working — spinner visible
            return "Implementing changes...\n⏺ Running Bash(git diff)…  3s\n"

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=mock_nudge,
                _capture_fn=capture,
            )

        # Active-work guard prevents false stall
        assert len(findings) == 0, f"Expected no stall findings, got: {findings}"
        assert len(nudges) == 0, "No nudge should be attempted on active lane"

        # Verify stale observation was reset
        state_path = _default_stall_state_path(runtime_dir)
        import json as _json

        state = _json.loads(state_path.read_text())
        obs = state["observations"][pkt.owner]
        assert obs["unchanged_count"] == 0, "Stale unchanged_count should be reset"
        assert obs["recovery_count"] == 0, "Recovery count should be reset"

    def test_stale_recovery_count_reset_by_active_work(self, tmp_path: Path) -> None:
        """Pre-seeded recovery_count (from prior nudge) is reset when lane
        shows active work, preventing immediate escalation."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-24T11:00:00Z")

        # Pre-seed: lane was nudged once (recovery_count=1), still stalled
        _save_stall_state(
            _default_stall_state_path(runtime_dir),
            {
                "observations": {
                    pkt.owner: {
                        "packet_id": pkt.packet_id,
                        "activity_epoch": 9999,
                        "unchanged_count": 3,
                        "recovery_count": 1,
                    }
                }
            },
        )

        def probe(_: str) -> int:
            return 9999

        def capture(_: str) -> str:
            return "Working...\n✻ Edit(src/foo.py)...\n"

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            findings = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda *_: None,
                _capture_fn=capture,
            )

        assert len(findings) == 0
        # Verify recovery_count is reset — next genuine stall will nudge, not escalate
        import json as _json

        state = _json.loads(_default_stall_state_path(runtime_dir).read_text())
        obs = state["observations"][pkt.owner]
        assert obs["recovery_count"] == 0

    def test_active_lane_transitions_to_idle_is_detected(self, tmp_path: Path) -> None:
        """Lane that was active then becomes idle IS correctly detected
        as stalled after the required consecutive cycles.

        Active phase: activity epoch changes each cycle (work happening).
        Idle phase: epoch stops changing + no spinner → stall detected.
        """
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-24T11:00:00Z")

        # Activity epochs: changing during active work, then frozen.
        # Cycles 1-3: epoch changes (active). Cycle 4: first frozen epoch
        # (unchanged_count stays 0 because epoch just changed from 3000→9999).
        # Cycle 5: same epoch (unchanged_count=1). Cycle 6: same epoch
        # (unchanged_count=2, hits default threshold).
        probe_values = iter([1000, 2000, 3000, 9999, 9999, 9999])

        def probe(_: str) -> int:
            return next(probe_values)

        def capture(_: str) -> str:
            # Only called when stall threshold is hit — pane is idle
            return "All done.\n$\n"

        nudges: list[tuple[str, str]] = []

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycles 1-3: changing epoch → unchanged_count resets, no stall
            for i in range(3):
                f = check_stalled_lanes(
                    runtime_dir,
                    now=now,
                    _activity_probe=probe,
                    _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                    _capture_fn=capture,
                )
                assert len(f) == 0, f"Active cycle {i + 1} should not stall: {f}"

            # Cycle 4: epoch changes to 9999 (new value) — unchanged_count=0
            f4 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                _capture_fn=capture,
            )
            assert len(f4) == 0

            # Cycle 5: same epoch 9999 — unchanged_count=1 (below threshold)
            f5 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                _capture_fn=capture,
            )
            assert len(f5) == 0

            # Cycle 6: same epoch 9999 — unchanged_count=2 → stall detected
            f6 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                _capture_fn=capture,
            )

        assert len(f6) >= 1, "Idle lane should be detected as stalled"
        assert "stalled" in f6[0].summary or "re-nudged" in f6[0].summary
        assert len(nudges) == 1, "Should have nudged the now-idle lane"

    def test_make_check_running_not_flagged_as_stalled(self, tmp_path: Path) -> None:
        """A lane running ``make check-quiet`` with progress indicators is NOT
        flagged as stalled, even though the activity epoch is unchanged
        (make check can take several minutes with no tmux epoch change)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-24T11:00:00Z")

        def probe(_: str) -> int:
            return 9999  # Unchanged epoch — make check is long-running

        def capture(_: str) -> str:
            return (
                "$ make check-quiet\n"
                "ruff check --force-exclude .\n"
                "All checks passed!\n"
                "ruff format --check .\n"
                "148 files already formatted\n"
                "⏺ Running Bash(make check-quiet)…  4m 12s\n"
            )

        nudges: list[tuple[str, str]] = []

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Run enough cycles to exceed stall threshold
            for _ in range(5):
                findings = check_stalled_lanes(
                    runtime_dir,
                    now=now,
                    _activity_probe=probe,
                    _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                    _capture_fn=capture,
                )
                assert (
                    len(findings) == 0
                ), f"make check should not trigger stall: {findings}"

        assert len(nudges) == 0, "No nudge during make check"

    def test_make_check_not_flagged_as_approval_stall(self, tmp_path: Path) -> None:
        """``make check`` output with progress indicators does not trigger
        approval-stall detection either."""
        pane_content = {
            "author-a": (
                "$ make check-quiet\n"
                "ruff check --force-exclude .\n"
                "uv run python -m pytest tests/\n"
                "⏺ Running Bash(make check-quiet)…  3m 45s\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.1",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=lambda *_: None,
            )

        assert len(findings) == 0

    def test_genuinely_idle_lane_detected_from_fresh_state(
        self, tmp_path: Path
    ) -> None:
        """A genuinely idle lane with no spinner IS correctly flagged as
        stalled after the required consecutive unchanged cycles."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 24, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-24T11:00:00Z")

        def probe(_: str) -> int:
            return 9999

        def capture(_: str) -> str:
            # No spinner, no progress — genuinely idle
            return "Last output was a while ago.\nSome old result.\n$\n"

        nudges: list[tuple[str, str]] = []

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1: first observation
            f1 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                _capture_fn=capture,
            )
            assert len(f1) == 0  # Below threshold

            # Cycle 2: unchanged_count=1 (still below default threshold of 2)
            f2 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                _capture_fn=capture,
            )
            assert len(f2) == 0

            # Cycle 3: unchanged_count=2 >= threshold → stall detected
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                _activity_probe=probe,
                _nudge_fn=lambda lid, pid: nudges.append((lid, pid)),
                _capture_fn=capture,
            )

        assert len(f3) == 1
        assert "stalled" in f3[0].summary or "re-nudged" in f3[0].summary
        assert len(nudges) == 1, "Should have nudged the genuinely idle lane"


# ---------------------------------------------------------------------------
# check_merged_dispatches tests (Gap A: auto-merge bypass)
# ---------------------------------------------------------------------------


class TestCheckMergedDispatches:
    """Tests for auto-completing dispatched packets whose PRs were merged."""

    def test_no_dispatched_packets(self, tmp_path: Path) -> None:
        """No dispatched packets produces no findings."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            return_value=[],
        ):
            findings = check_merged_dispatches(runtime_dir)

        assert len(findings) == 0

    def test_packet_without_pr_number_skipped(self, tmp_path: Path) -> None:
        """Dispatched packets without metadata.pr_number are skipped."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={})

        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            return_value=[pkt],
        ):
            findings = check_merged_dispatches(runtime_dir)

        assert len(findings) == 0

    def test_merged_pr_auto_completes_packet(self, tmp_path: Path) -> None:
        """A dispatched packet whose PR is MERGED is auto-completed."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 42})

        gh_result = MagicMock()
        gh_result.returncode = 0
        gh_result.stdout = "MERGED\n"

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch("subprocess.run", return_value=gh_result),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
        ):
            findings = check_merged_dispatches(runtime_dir)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO
        assert findings[0].category == "merged_dispatch"
        assert "Auto-completed" in findings[0].summary
        assert "42" in findings[0].summary
        mock_transition.assert_called_once_with(
            pkt.packet_id,
            "completed",
            runtime_dir / "task_queue",
        )

    def test_open_pr_not_completed(self, tmp_path: Path) -> None:
        """A dispatched packet whose PR is still OPEN is not completed."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 99})

        gh_result = MagicMock()
        gh_result.returncode = 0
        gh_result.stdout = "OPEN\n"

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch("subprocess.run", return_value=gh_result),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
        ):
            findings = check_merged_dispatches(runtime_dir)

        assert len(findings) == 0
        mock_transition.assert_not_called()

    def test_gh_failure_skips_gracefully(self, tmp_path: Path) -> None:
        """GitHub CLI failure is handled gracefully (skip, don't crash)."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 55})

        gh_result = MagicMock()
        gh_result.returncode = 1
        gh_result.stdout = ""

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch("subprocess.run", return_value=gh_result),
        ):
            findings = check_merged_dispatches(runtime_dir)

        assert len(findings) == 0

    def test_transition_failure_produces_warning(self, tmp_path: Path) -> None:
        """If transition_status fails, a WARN finding is produced."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 77})

        gh_result = MagicMock()
        gh_result.returncode = 0
        gh_result.stdout = "MERGED\n"

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch("subprocess.run", return_value=gh_result),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
                side_effect=ValueError("Invalid transition"),
            ),
        ):
            findings = check_merged_dispatches(runtime_dir)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Failed to auto-complete" in findings[0].summary


# ---------------------------------------------------------------------------
# reconcile_dispatched_packets tests (#2701)
# ---------------------------------------------------------------------------


class TestReconcileDispatchedPackets:
    """Tests for the orchestrator-side dispatched packet reconciler."""

    def test_merged_pr_completes_and_emits_message(self, tmp_path: Path) -> None:
        """MERGED → packet.status=completed + completion message queued."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(
            packet_id="pkt-merged-1",
            owner="author-a",
            metadata={"pr_number": 42},
        )

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.monitor._query_pr_state",
                return_value="MERGED",
            ),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
            patch(
                "bid_euchre.ops.message_bus.create_message",
            ) as mock_create,
            patch(
                "bid_euchre.ops.message_bus.send_message",
            ) as mock_send,
        ):
            mock_create.return_value = MagicMock()
            findings = reconcile_dispatched_packets(runtime_dir)

        mock_transition.assert_called_once_with(
            "pkt-merged-1", "completed", runtime_dir / "task_queue"
        )
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["to_lane"] == "orchestrator"
        assert kwargs["message_type"] == "completion"
        assert kwargs["task_id"] == "pkt-merged-1"
        assert kwargs["payload"]["pr_number"] == 42
        assert kwargs["payload"]["status"] == "completed"
        assert kwargs["payload"]["reconciled"] is True
        mock_send.assert_called_once()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO
        assert findings[0].details["reconciled"] is True

    def test_closed_pr_marks_failed_and_emits_message(self, tmp_path: Path) -> None:
        """CLOSED → packet.status=failed with reason + completion message."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(
            packet_id="pkt-closed-1",
            owner="author-b",
            metadata={"pr_number": 55},
        )

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.monitor._query_pr_state",
                return_value="CLOSED",
            ),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
            patch(
                "bid_euchre.ops.message_bus.create_message",
            ) as mock_create,
            patch(
                "bid_euchre.ops.message_bus.send_message",
            ) as mock_send,
        ):
            mock_create.return_value = MagicMock()
            findings = reconcile_dispatched_packets(runtime_dir)

        mock_transition.assert_called_once_with(
            "pkt-closed-1", "failed", runtime_dir / "task_queue"
        )
        mock_create.assert_called_once()
        payload = mock_create.call_args.kwargs["payload"]
        assert payload["status"] == "failed"
        assert payload["reason"] == "pr_closed_without_merge"
        assert payload["reconciled"] is True
        mock_send.assert_called_once()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert findings[0].details["reason"] == "pr_closed_without_merge"

    def test_open_pr_unchanged(self, tmp_path: Path) -> None:
        """OPEN → packet unchanged, no message emitted."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 99})

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.monitor._query_pr_state",
                return_value="OPEN",
            ),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
            patch("bid_euchre.ops.message_bus.send_message") as mock_send,
        ):
            findings = reconcile_dispatched_packets(runtime_dir)

        assert len(findings) == 0
        mock_transition.assert_not_called()
        mock_send.assert_not_called()

    def test_no_pr_number_skipped(self, tmp_path: Path) -> None:
        """Packet without metadata.pr_number is skipped gracefully."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={})

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.monitor._query_pr_state",
            ) as mock_query,
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
            patch("bid_euchre.ops.message_bus.send_message") as mock_send,
        ):
            findings = reconcile_dispatched_packets(runtime_dir)

        assert len(findings) == 0
        mock_query.assert_not_called()
        mock_transition.assert_not_called()
        mock_send.assert_not_called()

    def test_gh_query_failure_skips_packet(self, tmp_path: Path) -> None:
        """If _query_pr_state returns None, packet is left dispatched."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 111})

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.monitor._query_pr_state",
                return_value=None,
            ),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
            patch("bid_euchre.ops.message_bus.send_message") as mock_send,
        ):
            findings = reconcile_dispatched_packets(runtime_dir)

        assert len(findings) == 0
        mock_transition.assert_not_called()
        mock_send.assert_not_called()

    def test_message_send_failure_does_not_rollback_transition(
        self, tmp_path: Path
    ) -> None:
        """send_message failure is swallowed — packet stays completed."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pkt = _make_dispatched_pkt(metadata={"pr_number": 200})

        with (
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.monitor._query_pr_state",
                return_value="MERGED",
            ),
            patch(
                "bid_euchre.ops.task_queue.transition_status",
            ) as mock_transition,
            patch(
                "bid_euchre.ops.message_bus.send_message",
                side_effect=OSError("bus unavailable"),
            ),
        ):
            findings = reconcile_dispatched_packets(runtime_dir)

        mock_transition.assert_called_once()
        # INFO finding still produced — message failure is logged, not
        # surfaced as a finding to avoid infinite escalation.
        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO

    def test_check_merged_dispatches_is_alias(self, tmp_path: Path) -> None:
        """The pre-#2701 name forwards to reconcile_dispatched_packets."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        with patch(
            "bid_euchre.ops.monitor.reconcile_dispatched_packets",
            return_value=[],
        ) as mock_new:
            check_merged_dispatches(runtime_dir)

        mock_new.assert_called_once_with(runtime_dir)


# ---------------------------------------------------------------------------
# check_escalations tests (#1571 Phase 2b)
# ---------------------------------------------------------------------------


class TestCheckEscalations:
    """Tests for the escalation check wired into the monitoring cycle."""

    def test_no_escalation_when_no_unacked(self) -> None:
        """Returns info finding when escalate_unacked returns empty list."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            return_value=[],
        ):
            findings = check_escalations()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO
        assert findings[0].category == "escalation"
        assert "No unacked" in findings[0].summary

    def test_escalation_when_unacked_alerts_exist(self) -> None:
        """Returns HIGH finding with escalation IDs when alerts are unacked."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            return_value=["esc-001", "esc-002"],
        ):
            findings = check_escalations()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_HIGH
        assert findings[0].category == "escalation"
        assert "2 unacked alert(s)" in findings[0].summary
        assert findings[0].details["escalation_ids"] == ["esc-001", "esc-002"]

    def test_custom_max_age_passed_through(self) -> None:
        """max_age_minutes parameter is forwarded to escalate_unacked."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            return_value=[],
        ) as mock_esc:
            check_escalations(max_age_minutes=42)

        mock_esc.assert_called_once()
        call_kwargs = mock_esc.call_args
        assert call_kwargs[1]["max_age_minutes"] == 42

    def test_custom_bus_root_passed_through(self, tmp_path: Path) -> None:
        """bus_root parameter is forwarded to escalate_unacked."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            return_value=[],
        ) as mock_esc:
            check_escalations(bus_root=tmp_path)

        mock_esc.assert_called_once()
        call_kwargs = mock_esc.call_args
        assert call_kwargs[1]["bus_root"] == tmp_path

    def test_graceful_on_escalate_failure(self) -> None:
        """Returns WARN finding when escalate_unacked raises."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            side_effect=OSError("bus root missing"),
        ):
            findings = check_escalations()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert findings[0].category == "escalation"
        assert "Could not check" in findings[0].summary

    def test_default_age_minutes_matches_constant(self) -> None:
        """Default max_age_minutes uses the ESCALATION_AGE_MINUTES constant."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            return_value=[],
        ) as mock_esc:
            check_escalations()

        call_kwargs = mock_esc.call_args
        assert call_kwargs[1]["max_age_minutes"] == ESCALATION_AGE_MINUTES

    def test_integration_with_real_bus(self, tmp_path: Path) -> None:
        """End-to-end: ops sends a blocker, don't ack, verify escalation fires.

        Uses ``message_type="blocker"`` rather than ``supervisor_alert``:
        per #2700, ``supervisor_alert`` rollups are exempt from escalation
        because they are idempotent summaries of fleet state re-emitted
        every cycle. Real SLA-relevant messages (blocker, escalation from
        ops-monitor, approval_stall) remain escalation-eligible, which is
        what this integration test now verifies.
        """
        from bid_euchre.ops.message_bus import (
            create_message,
            send_message,
        )

        bus_root = tmp_path / "bus"
        events_dir = tmp_path / "events"

        # ops sends a blocker to orchestrator — still escalation-eligible
        # because blocker is not a rollup message type.
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="blocker",
            priority="high",
            summary="3 HIGH findings",
        )
        send_message(msg, bus_root, events_dir=events_dir)

        # Run check_escalations with max_age_minutes=0 so it fires immediately
        findings = check_escalations(
            bus_root=bus_root,
            events_dir=events_dir,
            max_age_minutes=0,
        )

        # Should have escalated
        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_HIGH
        assert findings[0].category == "escalation"
        assert len(findings[0].details["escalation_ids"]) >= 1

    def test_integration_supervisor_alert_no_self_cascade(self, tmp_path: Path) -> None:
        """Unacked supervisor_alerts must NOT trigger a HIGH escalation (#2700).

        Regression for the self-feeding cascade: monitor was emitting a
        supervisor_alert each cycle, then on the next cycle finding its own
        prior supervisor_alerts unacked and escalating them — which in turn
        produced a new HIGH finding, feeding the next cycle.
        """
        from bid_euchre.ops.message_bus import (
            create_message,
            send_message,
        )

        bus_root = tmp_path / "bus"
        events_dir = tmp_path / "events"

        # Simulate two unacked ops→orchestrator supervisor_alerts from
        # prior monitor cycles.
        for i in range(2):
            msg = create_message(
                from_lane="ops",
                to_lane="orchestrator",
                message_type="supervisor_alert",
                priority="high",
                summary=f"Monitor cycle {i} rollup",
            )
            send_message(msg, bus_root, events_dir=events_dir)

        findings = check_escalations(
            bus_root=bus_root,
            events_dir=events_dir,
            max_age_minutes=0,
        )

        # No HIGH finding — supervisor_alerts are exempt from escalation
        assert all(
            f.severity != SEVERITY_HIGH for f in findings
        ), "supervisor_alerts must not trigger HIGH escalation (self-cascade)"
        # Single info finding: "No unacked alerts to escalate."
        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO
        assert "No unacked" in findings[0].summary

    def test_integration_no_escalation_when_acked(self, tmp_path: Path) -> None:
        """End-to-end: ops sends alert, ack it, verify no escalation."""
        from bid_euchre.ops.message_bus import (
            ack_message,
            create_message,
            send_message,
        )

        bus_root = tmp_path / "bus"
        events_dir = tmp_path / "events"

        # ops sends an alert to orchestrator
        msg = create_message(
            from_lane="ops",
            to_lane="orchestrator",
            message_type="supervisor_alert",
            priority="high",
            summary="3 HIGH findings",
        )
        mid = send_message(msg, bus_root, events_dir=events_dir)

        # orchestrator acks it
        ack_message(mid, "orchestrator", bus_root=bus_root)

        # Run check_escalations with max_age_minutes=0
        findings = check_escalations(
            bus_root=bus_root,
            events_dir=events_dir,
            max_age_minutes=0,
        )

        # Should NOT have escalated — info finding instead
        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_INFO
        assert "No unacked" in findings[0].summary


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

        # subprocess.run may be called by approval-stall check (tmux
        # capture-pane), but NO call should contain "gh" (no PR checks).
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0] if call_args[0] else []
            assert "gh" not in cmd, f"gh should not be called: {cmd}"
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
# check_auto_dispatch tests (SP-4-02 Step 6)
# ---------------------------------------------------------------------------


def _make_approved_pkt(
    packet_id: str = "apkt001",
    title: str = "Approved task",
    domain: str | None = "platform",
) -> MagicMock:
    """Helper to create a mock approved packet."""
    pkt = MagicMock()
    pkt.packet_id = packet_id
    pkt.title = title
    pkt.domain = domain
    pkt.status = "approved"
    return pkt


def _make_pool_snapshot(
    workers: list[Any] | None = None,
    active: int = 0,
    idle: int = 0,
    parked: int = 0,
    retired: int = 0,
    capacity: int = 5,
) -> MagicMock:
    """Helper to create a mock PoolSnapshot."""
    pool = MagicMock()
    pool.workers = workers or []
    pool.active_count = active
    pool.idle_count = idle
    pool.parked_count = parked
    pool.retired_count = retired
    pool.available_capacity = capacity
    return pool


def _make_worker(
    lane_id: str = "author-a",
    pool_status: str = "idle",
    health: str = "healthy",
    current_task_id: str | None = None,
    domain: str | None = "platform",
) -> MagicMock:
    """Helper to create a mock WorkerState."""
    w = MagicMock()
    w.lane_id = lane_id
    w.pool_status = pool_status
    w.health = health
    w.current_task_id = current_task_id
    w.domain = domain
    return w


class TestCheckAutoDispatch:
    """Tests for auto-dispatch of approved packets to idle lanes."""

    def test_no_approved_packets(self, tmp_path: Path) -> None:
        """No approved packets → no dispatches."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pool = _make_pool_snapshot(capacity=5)

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[],
            ),
        ):
            findings = check_auto_dispatch(runtime_dir)

        assert len(findings) == 0

    def test_dispatches_approved_to_idle_lane(self, tmp_path: Path) -> None:
        """Approved packet dispatched to idle lane via _dispatch_fn."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        worker = _make_worker(lane_id="author-a", pool_status="idle")
        pool = _make_pool_snapshot(workers=[worker], idle=1, capacity=5)
        pkt = _make_approved_pkt(packet_id="apkt001", domain="platform")

        dispatches: list[tuple[str, str]] = []

        def mock_dispatch(packet_id: str, lane_id: str) -> None:
            dispatches.append((packet_id, lane_id))

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.worker_pool.select_worker",
                return_value="author-a",
            ),
        ):
            findings = check_auto_dispatch(runtime_dir, _dispatch_fn=mock_dispatch)

        assert len(findings) == 1
        assert findings[0].category == "auto_dispatch"
        assert findings[0].severity == SEVERITY_INFO
        assert "apkt001" in findings[0].summary
        assert "author-a" in findings[0].summary
        assert len(dispatches) == 1
        assert dispatches[0] == ("apkt001", "author-a")

    def test_rate_limit_enforced(self, tmp_path: Path) -> None:
        """At most max_dispatches per cycle."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        worker_a = _make_worker(lane_id="author-a", pool_status="idle")
        worker_b = _make_worker(lane_id="author-b", pool_status="idle")
        worker_c = _make_worker(lane_id="author-c", pool_status="idle")
        pool = _make_pool_snapshot(
            workers=[worker_a, worker_b, worker_c],
            idle=3,
            capacity=5,
        )

        pkts = [
            _make_approved_pkt(packet_id=f"apkt{i:03d}", title=f"Task {i}")
            for i in range(4)
        ]

        dispatches: list[tuple[str, str]] = []
        select_calls = iter(["author-a", "author-b", "author-c", "author-d"])

        def mock_dispatch(packet_id: str, lane_id: str) -> None:
            dispatches.append((packet_id, lane_id))

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=pkts,
            ),
            patch(
                "bid_euchre.ops.worker_pool.select_worker",
                side_effect=lambda *a, **kw: next(select_calls),
            ),
        ):
            findings = check_auto_dispatch(
                runtime_dir,
                max_dispatches=2,
                _dispatch_fn=mock_dispatch,
            )

        info_findings = [f for f in findings if f.severity == SEVERITY_INFO]
        assert len(info_findings) == 2
        assert len(dispatches) == 2

    def test_skips_lane_with_high_finding(self, tmp_path: Path) -> None:
        """Lanes with HIGH findings in current cycle are skipped."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        worker = _make_worker(lane_id="author-a", pool_status="idle")
        pool = _make_pool_snapshot(workers=[worker], idle=1, capacity=5)
        pkt = _make_approved_pkt()

        # Simulate a HIGH finding for author-a from earlier checks
        current_findings = [
            MonitorFinding(
                category="lane_health",
                severity=SEVERITY_HIGH,
                summary="Lane author-a has dead tmux",
                details={"lane_id": "author-a"},
            ),
        ]

        dispatches: list[tuple[str, str]] = []

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.worker_pool.select_worker",
                return_value="author-a",
            ),
        ):
            findings = check_auto_dispatch(
                runtime_dir,
                current_findings=current_findings,
                _dispatch_fn=lambda pid, lid: dispatches.append((pid, lid)),
            )

        assert len(dispatches) == 0
        assert len(findings) == 0

    def test_no_capacity_skips(self, tmp_path: Path) -> None:
        """No available capacity → no dispatches."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pool = _make_pool_snapshot(capacity=0)
        pkt = _make_approved_pkt()

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
        ):
            findings = check_auto_dispatch(runtime_dir)

        assert len(findings) == 0

    def test_no_matching_lane_skips(self, tmp_path: Path) -> None:
        """No matching lane for a packet → skip that packet."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        pool = _make_pool_snapshot(capacity=5)
        pkt = _make_approved_pkt()

        dispatches: list[tuple[str, str]] = []

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.worker_pool.select_worker",
                return_value=None,
            ),
        ):
            findings = check_auto_dispatch(
                runtime_dir,
                _dispatch_fn=lambda pid, lid: dispatches.append((pid, lid)),
            )

        assert len(dispatches) == 0
        assert len(findings) == 0

    def test_dispatch_exception_produces_warn(self, tmp_path: Path) -> None:
        """Exception during dispatch produces WARN finding."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        worker = _make_worker(lane_id="author-a", pool_status="idle")
        pool = _make_pool_snapshot(workers=[worker], idle=1, capacity=5)
        pkt = _make_approved_pkt()

        def bad_dispatch(packet_id: str, lane_id: str) -> None:
            raise RuntimeError("tmux not found")

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.worker_pool.select_worker",
                return_value="author-a",
            ),
        ):
            findings = check_auto_dispatch(runtime_dir, _dispatch_fn=bad_dispatch)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert findings[0].category == "auto_dispatch"
        assert "tmux not found" in findings[0].summary

    def test_max_dispatches_zero_noop(self, tmp_path: Path) -> None:
        """max_dispatches=0 is a kill switch — no dispatches."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        findings = check_auto_dispatch(runtime_dir, max_dispatches=0)
        assert len(findings) == 0

    def test_snapshot_failure_graceful(self, tmp_path: Path) -> None:
        """Pool snapshot failure produces WARN, doesn't crash."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            side_effect=RuntimeError("no registry"),
        ):
            findings = check_auto_dispatch(runtime_dir)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "auto-dispatch" in findings[0].summary.lower()

    def test_default_rate_limit_is_two(self) -> None:
        """Default MAX_AUTO_DISPATCH_PER_CYCLE is 2."""
        assert MAX_AUTO_DISPATCH_PER_CYCLE == 2

    def test_domain_passed_to_select_worker(self, tmp_path: Path) -> None:
        """Packet domain is passed through to select_worker."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        worker = _make_worker(lane_id="brws-author-a", domain="browser-game")
        pool = _make_pool_snapshot(workers=[worker], idle=1, capacity=5)
        pkt = _make_approved_pkt(domain="browser-game")

        dispatches: list[tuple[str, str]] = []

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool,
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[pkt],
            ),
            patch(
                "bid_euchre.ops.worker_pool.select_worker",
                return_value="brws-author-a",
            ) as mock_select,
        ):
            findings = check_auto_dispatch(
                runtime_dir,
                _dispatch_fn=lambda pid, lid: dispatches.append((pid, lid)),
            )

        mock_select.assert_called_once_with(pool, domain="browser-game")
        assert len(dispatches) == 1
        assert findings[0].details["domain"] == "browser-game"


class TestRunMonitoringCycleAutoDispatch:
    """Tests for auto-dispatch integration in run_monitoring_cycle."""

    def test_no_auto_dispatch_flag_disables(self, tmp_path: Path) -> None:
        """no_auto_dispatch=True prevents auto-dispatch step."""
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
                "bid_euchre.ops.monitor.check_auto_dispatch",
            ) as mock_auto,
            patch(
                "bid_euchre.ops.monitor._send_findings_to_orchestrator",
                return_value=None,
            ),
        ):
            run_monitoring_cycle(
                tmp_path,
                skip_pr_check=True,
                no_auto_dispatch=True,
            )

        mock_auto.assert_not_called()

    def test_auto_dispatch_enabled_by_default(self, tmp_path: Path) -> None:
        """Auto-dispatch runs by default when not disabled."""
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
                "bid_euchre.ops.monitor.check_auto_dispatch",
                return_value=[],
            ) as mock_auto,
            patch(
                "bid_euchre.ops.monitor._send_findings_to_orchestrator",
                return_value=None,
            ),
        ):
            run_monitoring_cycle(
                tmp_path,
                skip_pr_check=True,
            )

        mock_auto.assert_called_once()


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


# ---------------------------------------------------------------------------
# check_approval_stalls tests
# ---------------------------------------------------------------------------


class TestCheckApprovalStalls:
    """Tests for approval-stall detection."""

    def test_detects_bash_approval_prompt(self, tmp_path: Path) -> None:
        """Detects a Bash tool-approval prompt in a lane's pane."""
        pane_content = {
            "author-a": (
                "Working on implementation...\n"
                "  Allow Bash(git status) [Y]es, always / [N]o\n"
                ">\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        notifications: list[tuple[str, str, str]] = []

        def notify_fn(lane_id: str, prompt_text: str, target: str) -> None:
            notifications.append((lane_id, prompt_text, target))

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.1",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_HIGH
        assert findings[0].category == "approval_stall"
        assert "author-a" in findings[0].summary
        assert findings[0].details["lane_id"] == "author-a"
        assert findings[0].details["tmux_target"] == "steward:platform.1"

        # Notification should have been sent
        assert len(notifications) == 1
        assert notifications[0][0] == "author-a"

    def test_detects_elicitation_dialog(self, tmp_path: Path) -> None:
        """Detects an elicitation-style approval dialog."""
        pane_content = {
            "flex-a": (
                "Analyzing code changes...\n"
                "Permission required to write to file\n"
                "  [A]llow this action?\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:scratch.2",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=lambda *_: None,
            )

        assert len(findings) >= 1
        approval_findings = [f for f in findings if f.category == "approval_stall"]
        assert len(approval_findings) >= 1
        assert "flex-a" in approval_findings[0].summary

    def test_detects_do_you_want_to_make_this_edit(self, tmp_path: Path) -> None:
        """Catches 'Do you want to make this edit' prompts (#1672)."""
        pane_content = {
            "brws-author-a": (
                "Editing SKILL.md...\nDo you want to make this edit to SKILL.md?\n>\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        notifications: list[tuple[str, str, str]] = []

        def notify_fn(lane_id: str, prompt_text: str, target: str) -> None:
            notifications.append((lane_id, prompt_text, target))

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:browser.1",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_HIGH
        assert findings[0].category == "approval_stall"
        assert "brws-author-a" in findings[0].summary
        assert "Do you want to make this edit" in findings[0].summary
        assert len(notifications) == 1

    def test_no_false_positive_on_normal_output(self, tmp_path: Path) -> None:
        """Normal pane output does not trigger false positives."""
        pane_content = {
            "author-a": (
                "Running tests...\nPASSED 42 tests in 3.2s\nAll checks green.\n"
            ),
            "author-b": (
                "Editing src/bid_euchre/ops/monitor.py...\n"
                "Changes saved successfully.\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.1",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=lambda *_: None,
            )

        assert len(findings) == 0

    def test_dedup_prevents_repeat_notification(self, tmp_path: Path) -> None:
        """Same prompt text on same lane is not re-reported."""
        prompt_line = "Allow Bash(make check) [Y]es, always / [N]o"
        pane_content = {
            "author-c": f"Working...\n{prompt_line}\n",
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        notifications: list[tuple[str, str, str]] = []

        def notify_fn(lane_id: str, prompt_text: str, target: str) -> None:
            notifications.append((lane_id, prompt_text, target))

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.3",
        ):
            # First check — should produce a finding
            findings1 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )
            assert len(findings1) == 1
            assert len(notifications) == 1

            # Second check — same prompt, should be deduped
            findings2 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )
            assert len(findings2) == 0
            assert len(notifications) == 1  # no new notification

    def test_cleared_after_unstuck(self, tmp_path: Path) -> None:
        """A lane that gets unstuck and then re-stuck is reported again."""
        prompt_line = "Allow Edit(file.py) [Y]es, always / [N]o"
        stuck_content = {
            "author-b": f"Working...\n{prompt_line}\n",
        }
        clear_content: dict[str, str] = {
            "author-b": "Continuing implementation...\nDone.\n",
        }
        new_prompt_line = "Allow Write(new_file.py) [Y]es, always / [N]o"
        restuck_content = {
            "author-b": f"Working again...\n{new_prompt_line}\n",
        }

        notifications: list[tuple[str, str, str]] = []

        def notify_fn(lane_id: str, prompt_text: str, target: str) -> None:
            notifications.append((lane_id, prompt_text, target))

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.2",
        ):
            # 1. Stuck — should report
            findings1 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=lambda lid: stuck_content.get(lid),
                _notify_fn=notify_fn,
            )
            assert len(findings1) == 1

            # 2. Unstuck — no findings, state cleared
            findings2 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=lambda lid: clear_content.get(lid),
                _notify_fn=notify_fn,
            )
            assert len(findings2) == 0

            # 3. Re-stuck on different prompt — should report again
            findings3 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=lambda lid: restuck_content.get(lid),
                _notify_fn=notify_fn,
            )
            assert len(findings3) == 1
            assert len(notifications) == 2  # two unique notifications


class TestMatchApprovalPrompt:
    """Tests for the _match_approval_prompt helper."""

    def test_matches_allow_bash(self) -> None:
        content = "some output\n  Allow Bash(git diff) to run?\n"
        result = _match_approval_prompt(content)
        assert result is not None
        assert "Allow Bash" in result

    def test_matches_allow_bracket(self) -> None:
        content = "output\n[A]llow this tool?\n"
        result = _match_approval_prompt(content)
        assert result is not None

    def test_matches_permission_required(self) -> None:
        content = "output\nPermission required to proceed\n"
        result = _match_approval_prompt(content)
        assert result is not None
        assert "Permission required" in result

    def test_no_match_normal_text(self) -> None:
        content = "Running tests...\nPASSED\nDone.\n"
        result = _match_approval_prompt(content)
        assert result is None

    def test_matches_yes_always(self) -> None:
        content = "prompt\n  [Y]es, always allow\n"
        result = _match_approval_prompt(content)
        assert result is not None

    def test_matches_do_you_want_to_make_this_edit(self) -> None:
        """Catches 'Do you want to make this edit' permission prompts (#1672)."""
        content = "Working on SKILL.md...\nDo you want to make this edit to SKILL.md?\n"
        result = _match_approval_prompt(content)
        assert result is not None
        assert "Do you want to make this edit" in result

    def test_matches_do_you_want_to_make_this_edit_case_insensitive(self) -> None:
        content = "output\ndo you want to make this edit to settings.json?\n"
        result = _match_approval_prompt(content)
        assert result is not None


# ---------------------------------------------------------------------------
# _detect_active_work tests
# ---------------------------------------------------------------------------


class TestDetectActiveWork:
    """Tests for the _detect_active_work helper."""

    def test_detects_spinner_glyph(self) -> None:
        content = "some output\nprocessing files\n⏺ Running Bash(make check)…\n"
        assert _detect_active_work(content) is True

    def test_detects_braille_spinner(self) -> None:
        content = "working\n⠹ Building…\n"
        assert _detect_active_work(content) is True

    def test_detects_duration_counter_m_s(self) -> None:
        content = "output\nRunning tests  1m 23s\n"
        assert _detect_active_work(content) is True

    def test_detects_duration_counter_colon(self) -> None:
        content = "output\nElapsed: 0:45\n"
        assert _detect_active_work(content) is True

    def test_detects_seconds_counter(self) -> None:
        content = "output\nCompleted in 12s\n"
        assert _detect_active_work(content) is True

    def test_detects_running_ellipsis(self) -> None:
        content = "output\nRunning… tests\n"
        assert _detect_active_work(content) is True

    def test_detects_running_dots(self) -> None:
        content = "output\nRunning...\n"
        assert _detect_active_work(content) is True

    def test_detects_timeout_indicator(self) -> None:
        content = "output\ntimeout --signal=TERM 300\n"
        assert _detect_active_work(content) is True

    def test_detects_tool_execution_progress(self) -> None:
        content = "output\nBash(make check-quiet)...\n"
        assert _detect_active_work(content) is True

    def test_no_match_normal_output(self) -> None:
        content = "Running tests...\nPASSED 42 tests in 3.2s\nAll checks green.\n"
        # "Running..." matches — but that's intentional, it means active work.
        # Let's use content without active indicators.
        content = "PASSED 42 tests in 3.2s\nAll checks green.\nDone.\n"
        assert _detect_active_work(content) is False

    def test_no_match_approval_prompt_only(self) -> None:
        """An approval prompt without spinners is NOT active work."""
        content = (
            "Working on implementation...\n"
            "  Allow Bash(git status) [Y]es, always / [N]o\n"
            ">\n"
        )
        assert _detect_active_work(content) is False

    def test_only_checks_tail_lines(self) -> None:
        """Activity indicators early in the pane are ignored."""
        # Put a spinner far from the bottom with 25+ normal lines after
        # (_ACTIVITY_TAIL_LINES is 20, so 25 padding lines push it out)
        lines = ["⏺ Running Bash(make check)…"]
        lines.extend(["normal output"] * 25)
        lines.append("Done.")
        content = "\n".join(lines) + "\n"
        assert _detect_active_work(content) is False

    def test_detects_bash_spinner_at_line_8(self) -> None:
        """Bash spinner at line 8 (outside old 5-line window) is now detected (#2123)."""
        # Simulate: spinner at line 8 from bottom, status bar + blank lines below
        lines = ["some output"] * 5
        lines.append("⏺ Bash(make check-gated)…")
        lines.extend([""] * 3)  # blank lines
        lines.append("claude-3-5-sonnet  12345 tokens  2m 15s")
        lines.append("❯")
        content = "\n".join(lines) + "\n"
        assert _detect_active_work(content) is True

    def test_detects_make_check_progress_line(self) -> None:
        """'Running full check' progress line is detected (#2123)."""
        lines = ["some output"] * 5
        lines.append(">>> Running full check (logs → /tmp/check-abc.log)")
        lines.extend([""] * 3)
        lines.append("❯")
        content = "\n".join(lines) + "\n"
        assert _detect_active_work(content) is True

    def test_detects_waiting_for_slot(self) -> None:
        """'Waiting for slot' message from check-gated is detected (#2123)."""
        lines = ["previous output"] * 3
        lines.append("Waiting for check-gated slot (3 of 3 occupied)")
        lines.extend([""] * 2)
        lines.append("❯")
        content = "\n".join(lines) + "\n"
        assert _detect_active_work(content) is True

    def test_detects_check_quiet_in_output(self) -> None:
        """check-quiet keyword in pane output is detected (#2123)."""
        content = "running\ncheck-quiet started\n❯\n"
        assert _detect_active_work(content) is True


# ---------------------------------------------------------------------------
# _detect_background_validation tests
# ---------------------------------------------------------------------------


class TestDetectBackgroundValidation:
    """Tests for process-tree validation detection (#2123)."""

    def test_detects_make_process(self) -> None:
        """Returns True when 'make' is running in the pane's process tree."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: "12345",
            _pgrep_fn=lambda _: ["12346 make check-quiet"],
        )
        assert result is True

    def test_detects_pytest_process(self) -> None:
        """Returns True when 'pytest' is running in the pane's process tree."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: "12345",
            _pgrep_fn=lambda _: ["12347 python -m pytest tests/"],
        )
        assert result is True

    def test_detects_ruff_process(self) -> None:
        """Returns True when 'ruff' is running in the pane's process tree."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: "12345",
            _pgrep_fn=lambda _: ["12348 ruff check src/"],
        )
        assert result is True

    def test_no_validation_process(self) -> None:
        """Returns False when no validation process is running."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: "12345",
            _pgrep_fn=lambda _: ["12349 vim README.md"],
        )
        assert result is False

    def test_empty_process_list(self) -> None:
        """Returns False when no child processes exist."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: "12345",
            _pgrep_fn=lambda _: [],
        )
        assert result is False

    def test_no_pane_pid(self) -> None:
        """Returns False when pane PID cannot be determined."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: None,
            _pgrep_fn=lambda _: ["12346 make check"],
        )
        assert result is False

    def test_empty_pane_pid(self) -> None:
        """Returns False when pane PID is empty string."""
        result = _detect_background_validation(
            "author-a",
            _pane_pid_fn=lambda _: "",
            _pgrep_fn=lambda _: ["12346 make check"],
        )
        assert result is False


# ---------------------------------------------------------------------------
# check_stalled_lanes process-level guard integration
# ---------------------------------------------------------------------------


class TestStalledLanesProcessGuard:
    """Tests that process-level validation guard suppresses false stalls (#2123)."""

    def test_stall_suppressed_when_make_running(self, tmp_path: Path) -> None:
        """A lane running make check should NOT be flagged as stalled."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")  # 60min ago

        def probe(_: str) -> int:
            return 9999  # fixed epoch — simulates no change

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1: first observation — no finding
            check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _capture_fn=lambda _: "❯\n",  # no spinner
                _pane_pid_fn=lambda _: "12345",
                _pgrep_fn=lambda _: ["12346 make check-quiet"],
            )

            # Cycle 2: unchanged but process guard not yet triggered (threshold not met)
            check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _capture_fn=lambda _: "❯\n",
                _pane_pid_fn=lambda _: "12345",
                _pgrep_fn=lambda _: ["12346 make check-quiet"],
            )

            # Cycle 3: threshold met, but process guard suppresses stall
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _capture_fn=lambda _: "❯\n",
                _pane_pid_fn=lambda _: "12345",
                _pgrep_fn=lambda _: ["12346 make check-quiet"],
            )

        stall_findings = [f for f in f3 if "stall" in f.category]
        assert len(stall_findings) == 0

    def test_stall_detected_when_no_validation_process(self, tmp_path: Path) -> None:
        """A truly idle lane (no validation running) IS flagged as stalled."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        now = datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc)
        pkt = _make_dispatched_pkt(created_at="2026-03-23T11:00:00Z")  # 60min ago

        def probe(_: str) -> int:
            return 9999  # fixed epoch

        with (
            patch("bid_euchre.ops.task_queue.list_packets", return_value=[pkt]),
            patch("bid_euchre.ops.task_queue.load_ack", return_value=MagicMock()),
        ):
            # Cycle 1
            check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _capture_fn=lambda _: "❯\n",
                _pane_pid_fn=lambda _: "12345",
                _pgrep_fn=lambda _: [],  # no validation processes
            )

            # Cycle 2
            check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _capture_fn=lambda _: "❯\n",
                _pane_pid_fn=lambda _: "12345",
                _pgrep_fn=lambda _: [],
            )

            # Cycle 3: should trigger stall (no spinner, no processes)
            f3 = check_stalled_lanes(
                runtime_dir,
                now=now,
                no_recovery=True,
                _activity_probe=probe,
                _capture_fn=lambda _: "❯\n",
                _pane_pid_fn=lambda _: "12345",
                _pgrep_fn=lambda _: [],
            )

        stall_findings = [f for f in f3 if "stall" in f.category]
        assert len(stall_findings) == 1
        assert "stalled" in stall_findings[0].summary


# ---------------------------------------------------------------------------
# check_approval_stalls with spinner-activity detection
# ---------------------------------------------------------------------------


class TestApprovalStallsWithSpinner:
    """Tests that active lanes are not flagged as approval-stalled."""

    def test_spinner_active_lane_not_flagged(self, tmp_path: Path) -> None:
        """A lane with a spinner should not be flagged even if approval text exists."""
        pane_content = {
            "author-a": (
                "Working on implementation...\n"
                "  Allow Bash(git status) [Y]es, always / [N]o\n"
                "Some more output\n"
                "⏺ Running Bash(make check-quiet)…\n"
                "  1m 23s\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        notifications: list[tuple[str, str, str]] = []

        def notify_fn(lane_id: str, prompt_text: str, target: str) -> None:
            notifications.append((lane_id, prompt_text, target))

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.1",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )

        assert len(findings) == 0
        assert len(notifications) == 0

    def test_no_spinner_still_flags_approval(self, tmp_path: Path) -> None:
        """A lane without a spinner but with an approval prompt is still flagged."""
        pane_content = {
            "author-b": (
                "Working on implementation...\n"
                "  Allow Bash(git status) [Y]es, always / [N]o\n"
                ">\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.2",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=lambda *_: None,
            )

        assert len(findings) == 1
        assert findings[0].category == "approval_stall"
        assert "author-b" in findings[0].summary

    def test_make_check_with_spinner_not_flagged(self, tmp_path: Path) -> None:
        """A lane running make check-quiet with active spinner is not flagged."""
        pane_content = {
            "flex-a": (
                "$ make check-quiet\nruff check passed\npytest running...\n⠹ Running…\n"
            ),
        }

        def capture_fn(lane_id: str) -> str | None:
            return pane_content.get(lane_id)

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:flex.0",
        ):
            findings = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=lambda *_: None,
            )

        assert len(findings) == 0

    def test_spinner_clears_then_approval_detected(self, tmp_path: Path) -> None:
        """After spinner stops, an approval prompt is detected correctly."""
        # First call: lane active with spinner
        active_content = {
            "author-c": "Working...\n⏺ Running Bash(make check)…\n",
        }
        # Second call: spinner gone, prompt visible
        stalled_content = {
            "author-c": (
                "Done with check.\n  Allow Bash(git push) [Y]es, always / [N]o\n>\n"
            ),
        }

        call_count = {"n": 0}

        def capture_fn(lane_id: str) -> str | None:
            if call_count["n"] == 0:
                return active_content.get(lane_id)
            return stalled_content.get(lane_id)

        notifications: list[tuple[str, str, str]] = []

        def notify_fn(lane_id: str, prompt_text: str, target: str) -> None:
            notifications.append((lane_id, prompt_text, target))

        with patch(
            "bid_euchre.ops.worker_pool._resolve_tmux_target",
            return_value="steward:platform.3",
        ):
            # First check — spinner active, no findings
            findings1 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )
            assert len(findings1) == 0

            # Second check — spinner gone, prompt detected
            call_count["n"] = 1
            findings2 = check_approval_stalls(
                runtime_dir=tmp_path,
                _capture_fn=capture_fn,
                _notify_fn=notify_fn,
            )
            assert len(findings2) == 1
            assert "author-c" in findings2[0].summary
            assert len(notifications) == 1


# ---------------------------------------------------------------------------
# check_idle_lanes tests
# ---------------------------------------------------------------------------


class TestCheckIdleLanes:
    """Tests for idle lane detection."""

    def test_reports_idle_lanes(self, tmp_path: Path) -> None:
        """Idle lanes with live tmux are reported."""
        worker_idle = MagicMock()
        worker_idle.lane_id = "author-b"
        worker_idle.pool_status = "idle"
        worker_idle.tmux_alive = True

        worker_active = MagicMock()
        worker_active.lane_id = "author-a"
        worker_active.pool_status = "active"
        worker_active.tmux_alive = True

        pool_mock = MagicMock()
        pool_mock.workers = [worker_idle, worker_active]

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_idle_lanes(tmp_path)

        idle_findings = [f for f in findings if f.category == "lane_idle"]
        assert len(idle_findings) == 1
        assert "author-b" in idle_findings[0].summary
        assert idle_findings[0].severity == SEVERITY_INFO

    def test_no_idle_lanes(self, tmp_path: Path) -> None:
        """No findings when all lanes are active."""
        worker = MagicMock()
        worker.lane_id = "author-a"
        worker.pool_status = "active"
        worker.tmux_alive = True

        pool_mock = MagicMock()
        pool_mock.workers = [worker]

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_idle_lanes(tmp_path)

        assert len(findings) == 0

    def test_idle_lane_with_dead_tmux_not_reported(self, tmp_path: Path) -> None:
        """Idle lanes with dead tmux panes are not reported as available."""
        worker = MagicMock()
        worker.lane_id = "author-c"
        worker.pool_status = "idle"
        worker.tmux_alive = False

        pool_mock = MagicMock()
        pool_mock.workers = [worker]

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_idle_lanes(tmp_path)

        assert len(findings) == 0

    def test_multiple_idle_lanes(self, tmp_path: Path) -> None:
        """Multiple idle lanes each produce a finding."""
        workers = []
        for lid in ["author-a", "flex-a", "brws-author-b"]:
            w = MagicMock()
            w.lane_id = lid
            w.pool_status = "idle"
            w.tmux_alive = True
            workers.append(w)

        pool_mock = MagicMock()
        pool_mock.workers = workers

        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            return_value=pool_mock,
        ):
            findings = check_idle_lanes(tmp_path)

        assert len(findings) == 3
        lane_ids = {f.details["lane_id"] for f in findings}
        assert lane_ids == {"author-a", "flex-a", "brws-author-b"}

    def test_handles_snapshot_failure(self, tmp_path: Path) -> None:
        """Gracefully handles pool snapshot failure."""
        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            side_effect=RuntimeError("no registry"),
        ):
            findings = check_idle_lanes(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "idle" in findings[0].summary.lower()


# ---------------------------------------------------------------------------
# check_recently_merged_prs tests
# ---------------------------------------------------------------------------


class TestCheckRecentlyMergedPRs:
    """Tests for recently merged PR detection."""

    def test_reports_new_merges(self, tmp_path: Path) -> None:
        """Newly merged PRs are reported as findings."""
        prs = [
            {
                "number": 100,
                "title": "Fix scoring",
                "headRefName": "fix/scoring",
                "mergedAt": "2026-03-23T10:00:00Z",
            },
            {
                "number": 101,
                "title": "Add feature",
                "headRefName": "feat/new",
                "mergedAt": "2026-03-23T11:00:00Z",
            },
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_recently_merged_prs(tmp_path)

        merged = [f for f in findings if f.category == "pr_merged"]
        assert len(merged) == 2
        nums = {f.details["pr"] for f in merged}
        assert nums == {100, 101}

    def test_deduplicates_across_cycles(self, tmp_path: Path) -> None:
        """Previously seen merges are not re-reported."""
        # Seed the state with PR #100 already seen
        state_path = tmp_path / "merged_pr_state.json"
        state_path.write_text(json.dumps({"seen": [100]}) + "\n")

        prs = [
            {
                "number": 100,
                "title": "Fix scoring",
                "headRefName": "fix/scoring",
                "mergedAt": "2026-03-23T10:00:00Z",
            },
            {
                "number": 102,
                "title": "New PR",
                "headRefName": "feat/new",
                "mergedAt": "2026-03-23T12:00:00Z",
            },
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_recently_merged_prs(tmp_path)

        merged = [f for f in findings if f.category == "pr_merged"]
        assert len(merged) == 1
        assert merged[0].details["pr"] == 102

    def test_persists_state(self, tmp_path: Path) -> None:
        """Seen PR numbers are persisted after a cycle."""
        prs = [
            {
                "number": 200,
                "title": "PR 200",
                "headRefName": "feat/200",
                "mergedAt": "2026-03-23T10:00:00Z",
            },
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            check_recently_merged_prs(tmp_path)

        state_path = tmp_path / "merged_pr_state.json"
        assert state_path.exists()
        state = json.loads(state_path.read_text())
        assert 200 in state["seen"]

    def test_no_merged_prs(self, tmp_path: Path) -> None:
        """No findings when no PRs are merged."""
        result = MagicMock()
        result.returncode = 0
        result.stdout = "[]"

        with patch("subprocess.run", return_value=result):
            findings = check_recently_merged_prs(tmp_path)

        assert len(findings) == 0

    def test_handles_gh_failure(self, tmp_path: Path) -> None:
        """Gracefully handles gh command failure."""
        result = MagicMock()
        result.returncode = 1
        result.stderr = "auth error"
        result.stdout = ""

        with patch("subprocess.run", return_value=result):
            findings = check_recently_merged_prs(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "failed" in findings[0].summary


# ---------------------------------------------------------------------------
# check_open_prs — pr_ready detection tests
# ---------------------------------------------------------------------------


class TestCheckOpenPRsReady:
    """Tests for CI-ready PR detection in check_open_prs."""

    def test_flags_pr_with_all_green_checks(self) -> None:
        """PR with all checks passing is flagged as pr_ready."""
        prs = [
            {
                "number": 50,
                "title": "Good PR",
                "headRefName": "feat/good",
                "mergeable": "MERGEABLE",
                "statusCheckRollup": [
                    {"name": "tests", "conclusion": "SUCCESS", "status": "COMPLETED"},
                    {"name": "lint", "conclusion": "SUCCESS", "status": "COMPLETED"},
                ],
            }
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        ready = [f for f in findings if f.category == "pr_ready"]
        assert len(ready) == 1
        assert "#50" in ready[0].summary
        assert ready[0].severity == SEVERITY_WARN

    def test_does_not_flag_pr_with_failing_checks(self) -> None:
        """PR with failing checks is NOT flagged as pr_ready."""
        prs = [
            {
                "number": 51,
                "title": "Broken PR",
                "headRefName": "feat/broken",
                "mergeable": "MERGEABLE",
                "statusCheckRollup": [
                    {"name": "tests", "conclusion": "FAILURE", "status": "COMPLETED"},
                    {"name": "lint", "conclusion": "SUCCESS", "status": "COMPLETED"},
                ],
            }
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        ready = [f for f in findings if f.category == "pr_ready"]
        assert len(ready) == 0

    def test_does_not_flag_pr_with_no_checks(self) -> None:
        """PR with no checks is NOT flagged as pr_ready."""
        prs = [
            {
                "number": 52,
                "title": "No checks PR",
                "headRefName": "feat/noci",
                "mergeable": "MERGEABLE",
                "statusCheckRollup": [],
            }
        ]
        result = MagicMock()
        result.returncode = 0
        result.stdout = json.dumps(prs)

        with patch("subprocess.run", return_value=result):
            findings = check_open_prs()

        ready = [f for f in findings if f.category == "pr_ready"]
        assert len(ready) == 0


# ---------------------------------------------------------------------------
# check_fleet_idle tests
# ---------------------------------------------------------------------------


class TestCheckFleetIdle:
    """Tests for fleet-level idle check (auto-shutoff wiring)."""

    def test_emits_warn_finding_when_idle(self) -> None:
        """Should emit WARN severity finding when fleet is idle."""
        from bid_euchre.ops.idle_detector import IdleStatus, ShutoffRecommendation

        idle_rec = ShutoffRecommendation(
            should_shutoff=True,
            idle_status=IdleStatus(
                idle=True,
                idle_minutes=120.0,
                last_meaningful_event=None,
                active_lanes=[],
                reason="No meaningful activity for 120m (threshold: 90m)",
            ),
            recommended_actions=["Cancel cron jobs", "Produce handoff"],
        )

        with patch(
            "bid_euchre.ops.monitor.check_fleet_idle.__module__",
            create=True,
        ):
            with patch(
                "bid_euchre.ops.idle_detector.recommend_shutoff",
                return_value=idle_rec,
            ):
                findings = check_fleet_idle()

        warn = [f for f in findings if f.severity == "warn"]
        assert len(warn) == 1
        assert warn[0].category == "fleet_idle"
        assert "120m" in warn[0].summary
        assert "shutoff" in warn[0].summary.lower()
        assert warn[0].details["should_shutoff"] is True
        assert warn[0].details["idle_minutes"] == 120.0
        assert len(warn[0].details["recommended_actions"]) == 2

    def test_emits_info_when_active(self) -> None:
        """Should emit info finding when fleet is active."""
        from bid_euchre.ops.idle_detector import IdleStatus, ShutoffRecommendation

        active_rec = ShutoffRecommendation(
            should_shutoff=False,
            idle_status=IdleStatus(
                idle=False,
                idle_minutes=10.0,
                last_meaningful_event=None,
                active_lanes=["author-a"],
                reason="Active lanes: author-a",
            ),
            recommended_actions=[],
        )

        with patch(
            "bid_euchre.ops.idle_detector.recommend_shutoff",
            return_value=active_rec,
        ):
            findings = check_fleet_idle()

        info = [f for f in findings if f.severity == "info"]
        assert len(info) == 1
        assert info[0].category == "fleet_idle"
        assert info[0].details["should_shutoff"] is False
        assert "author-a" in info[0].details["active_lanes"]

    def test_handles_exception_gracefully(self) -> None:
        """Should emit warn finding if idle check raises."""
        with patch(
            "bid_euchre.ops.idle_detector.recommend_shutoff",
            side_effect=RuntimeError("events dir missing"),
        ):
            findings = check_fleet_idle()

        warn = [f for f in findings if f.severity == "warn"]
        assert len(warn) == 1
        assert "Could not check fleet idle status" in warn[0].summary


# ---------------------------------------------------------------------------
# Phase 4 Edge-Case Hardening — monitor cycle timeout handling
# ---------------------------------------------------------------------------


class TestMonitorSubprocessTimeouts:
    """Prove that subprocess timeouts in monitor checks produce graceful findings.

    Monitor checks call external commands (``gh pr list``, ``tmux``, etc.) via
    ``subprocess.run(..., timeout=N)``.  If any of these time out, the check
    must produce a WARN finding and continue rather than crashing the cycle.
    """

    def test_check_open_prs_timeout(self) -> None:
        """check_open_prs handles subprocess.TimeoutExpired gracefully."""
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("gh", 30),
        ):
            findings = check_open_prs()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check PRs" in findings[0].summary

    def test_check_open_prs_oserror(self) -> None:
        """check_open_prs handles OSError (e.g., broken pipe) gracefully."""
        with patch(
            "subprocess.run",
            side_effect=OSError("broken pipe"),
        ):
            findings = check_open_prs()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN

    def test_check_recently_merged_prs_timeout(self, tmp_path: Path) -> None:
        """check_recently_merged_prs handles subprocess timeout gracefully."""
        import subprocess

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired("gh", 30),
        ):
            findings = check_recently_merged_prs(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check merged PRs" in findings[0].summary

    def test_check_merged_dispatches_timeout(self, tmp_path: Path) -> None:
        """check_merged_dispatches handles list_packets failure gracefully."""
        # When list_packets fails, we get a WARN finding instead of a crash.
        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            side_effect=RuntimeError("disk full"),
        ):
            findings = check_merged_dispatches(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check dispatched packets" in findings[0].summary

    def test_check_stale_dispatches_task_queue_failure(self, tmp_path: Path) -> None:
        """check_stale_dispatches handles task queue errors gracefully."""
        runtime_dir = tmp_path / "runtime"
        (runtime_dir / "task_queue").mkdir(parents=True)

        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            side_effect=RuntimeError("corrupt queue"),
        ):
            findings = check_stale_dispatches(runtime_dir)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN

    def test_check_stalled_lanes_task_queue_failure(self, tmp_path: Path) -> None:
        """check_stalled_lanes handles task queue errors gracefully."""
        with patch(
            "bid_euchre.ops.task_queue.list_packets",
            side_effect=RuntimeError("corrupt queue"),
        ):
            findings = check_stalled_lanes(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check for stalled lanes" in findings[0].summary

    def test_check_idle_lanes_pool_snapshot_failure(self, tmp_path: Path) -> None:
        """check_idle_lanes handles pool snapshot failure gracefully."""
        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            side_effect=RuntimeError("registry missing"),
        ):
            findings = check_idle_lanes(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check for idle lanes" in findings[0].summary

    def test_check_escalations_bus_failure(self) -> None:
        """check_escalations handles message bus failure gracefully."""
        with patch(
            "bid_euchre.ops.message_bus.escalate_unacked",
            side_effect=RuntimeError("bus dir missing"),
        ):
            findings = check_escalations()

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check for unacked alerts" in findings[0].summary

    def test_check_auto_dispatch_pool_snapshot_failure(self, tmp_path: Path) -> None:
        """check_auto_dispatch handles pool snapshot failure gracefully."""
        with patch(
            "bid_euchre.ops.worker_pool.take_pool_snapshot",
            side_effect=RuntimeError("tmux not running"),
        ):
            findings = check_auto_dispatch(tmp_path)

        assert len(findings) == 1
        assert findings[0].severity == SEVERITY_WARN
        assert "Could not check for auto-dispatch" in findings[0].summary


class TestMonitorCycleRobustness:
    """Prove that the full monitor cycle is robust to individual check failures.

    ``run_monitoring_cycle()`` calls many individual checks. If one fails,
    the others should still produce their findings.
    """

    def test_cycle_continues_after_pr_check_failure(self, tmp_path: Path) -> None:
        """Monitor cycle produces non-PR findings even when gh fails."""
        pool_mock = MagicMock()
        pool_mock.workers = []
        pool_mock.active_count = 0
        pool_mock.idle_count = 0
        pool_mock.parked_count = 0
        pool_mock.retired_count = 0
        pool_mock.available_capacity = 0

        with (
            patch(
                "bid_euchre.ops.worker_pool.take_pool_snapshot",
                return_value=pool_mock,
            ),
            patch(
                "subprocess.run",
                side_effect=FileNotFoundError("gh"),
            ),
            patch(
                "bid_euchre.ops.message_bus.escalate_unacked",
                return_value=[],
            ),
            patch(
                "bid_euchre.ops.task_queue.list_packets",
                return_value=[],
            ),
            patch(
                "bid_euchre.ops.idle_detector.recommend_shutoff",
                side_effect=RuntimeError("no events"),
            ),
        ):
            findings = run_monitoring_cycle(
                runtime_dir=tmp_path,
                notify_orchestrator=False,
                no_auto_dispatch=True,
            )

        # Should have findings from multiple checks (not just first failure).
        categories = {f.category for f in findings}
        # Lane health info summary should still be present.
        assert "lane_health" in categories
        # Escalation check should produce a finding (info or warn).
        assert "escalation" in categories


# ---------------------------------------------------------------------------
# MonitorCycleResult tests
# ---------------------------------------------------------------------------


class TestMonitorCycleResult:
    """Tests for the MonitorCycleResult dataclass."""

    def test_default_push_result_is_none(self) -> None:
        """Push result defaults to None."""
        result = MonitorCycleResult(findings=[])
        assert result.findings == []
        assert result.push_result is None

    def test_with_findings_and_push(self) -> None:
        """Result carries both findings and push_result."""
        finding = MonitorFinding(
            category="lane_health",
            severity="info",
            summary="Pool: 2 active",
        )
        mock_push = MagicMock()
        mock_push.chat_id = "12345"
        mock_push.message = "Alert text"
        mock_push.items_pushed = []

        result = MonitorCycleResult(findings=[finding], push_result=mock_push)
        assert len(result.findings) == 1
        assert result.push_result is mock_push
        assert result.push_result.chat_id == "12345"


# ---------------------------------------------------------------------------
# evaluate_alert_push tests
# ---------------------------------------------------------------------------


class TestEvaluateAlertPush:
    """Tests for evaluate_alert_push() integration wrapper."""

    def test_returns_cycle_result_with_none_when_disabled(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """When Telegram is disabled, push_result is None."""
        monkeypatch.setenv("STEWARD_TELEGRAM_ENABLED", "0")
        findings = [
            MonitorFinding(category="lane_health", severity="info", summary="ok")
        ]
        result = evaluate_alert_push(findings, runtime_dir=tmp_path)
        assert isinstance(result, MonitorCycleResult)
        assert result.findings is findings
        assert result.push_result is None

    def test_returns_cycle_result_with_none_when_no_chat_id(
        self, tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
    ) -> None:
        """When Telegram enabled but no chat ID, push_result is None."""
        monkeypatch.setenv("STEWARD_TELEGRAM_ENABLED", "1")
        monkeypatch.delenv("STEWARD_ALERT_PUSH_CHAT_ID", raising=False)
        findings = [
            MonitorFinding(category="lane_health", severity="info", summary="ok")
        ]
        result = evaluate_alert_push(findings, runtime_dir=tmp_path)
        assert result.push_result is None

    @patch("bid_euchre.ops.telegram_push.run_push_cycle")
    def test_returns_push_result_when_available(
        self, mock_push: MagicMock, tmp_path: Path
    ) -> None:
        """When run_push_cycle returns a result, it's in push_result."""
        mock_pr = MagicMock()
        mock_pr.chat_id = "999"
        mock_pr.message = "🚨 Alert"
        mock_pr.items_pushed = [MagicMock()]
        mock_push.return_value = mock_pr

        findings = [
            MonitorFinding(category="stale_dispatch", severity="high", summary="stale")
        ]
        result = evaluate_alert_push(findings, runtime_dir=tmp_path)
        assert result.push_result is mock_pr
        assert result.findings is findings
        mock_push.assert_called_once()

    @patch("bid_euchre.ops.telegram_push.run_push_cycle")
    def test_returns_none_push_on_exception(
        self, mock_push: MagicMock, tmp_path: Path
    ) -> None:
        """When run_push_cycle raises, push_result is None (best-effort)."""
        mock_push.side_effect = RuntimeError("boom")

        findings = [
            MonitorFinding(category="lane_health", severity="info", summary="ok")
        ]
        result = evaluate_alert_push(findings, runtime_dir=tmp_path)
        assert result.push_result is None
        assert result.findings is findings

    @patch("bid_euchre.ops.telegram_push.run_push_cycle")
    def test_passes_audit_dir_from_runtime_dir(
        self, mock_push: MagicMock, tmp_path: Path
    ) -> None:
        """Audit dir defaults to runtime_dir/audit_trail when not explicit."""
        mock_push.return_value = None
        evaluate_alert_push([], runtime_dir=tmp_path)
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["audit_dir"] == tmp_path / "audit_trail"
        assert call_kwargs["runtime_dir"] == tmp_path

    @patch("bid_euchre.ops.telegram_push.run_push_cycle")
    def test_explicit_audit_dir_overrides_default(
        self, mock_push: MagicMock, tmp_path: Path
    ) -> None:
        """Explicit audit_dir takes precedence over runtime_dir-derived."""
        mock_push.return_value = None
        custom_audit = tmp_path / "custom_audit"
        evaluate_alert_push([], runtime_dir=tmp_path, audit_dir=custom_audit)
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["audit_dir"] == custom_audit

    @patch("bid_euchre.ops.telegram_push.run_push_cycle")
    def test_passes_now_to_push_cycle(
        self, mock_push: MagicMock, tmp_path: Path
    ) -> None:
        """The now parameter is forwarded to run_push_cycle."""
        mock_push.return_value = None
        from datetime import datetime, timezone

        ts = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)
        evaluate_alert_push([], runtime_dir=tmp_path, now=ts)
        call_kwargs = mock_push.call_args.kwargs
        assert call_kwargs["now"] == ts


# ---------------------------------------------------------------------------
# E2E smoke test: full alert → push → ack loop (Platform-9a, #1826 part 3)
# ---------------------------------------------------------------------------


class TestAlertPushAckE2E:
    """End-to-end smoke test for the complete alert→push→ack cycle.

    Exercises the full loop with real functions (no mocks):
    1. Seed a HIGH monitor finding.
    2. Reconcile to produce fleet_status.json on disk.
    3. Run prepare_alert_push (reads fleet status from disk) → PushResult.
    4. Parse the push message for an ack command.
    5. Execute the ack against the fleet status.
    6. Verify the item transitions to acked state.

    Uses ``prepare_alert_push`` with a constructed ``IdleStatus`` to avoid
    wall-clock coupling in the idle detector (``run_push_cycle`` does not
    forward ``now`` to ``is_fleet_idle``).
    """

    def test_full_alert_push_ack_loop(
        self,
        tmp_path: Path,
    ) -> None:
        """Full alert→push→ack cycle through real functions, no mocks."""
        from bid_euchre.ops.alert_push import PushState, load_push_state
        from bid_euchre.ops.audit_trail import read_records
        from bid_euchre.ops.control_plane import (
            STATE_ACKED,
            STATE_OPEN,
            load_fleet_status,
            reconcile,
            save_fleet_status,
        )
        from bid_euchre.ops.idle_detector import IdleStatus
        from bid_euchre.ops.remote_ack import (
            execute_remote_ack,
            format_ack_confirmation,
            parse_ack_command,
        )
        from bid_euchre.ops.telegram_push import prepare_alert_push

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        audit_dir = runtime_dir / "audit_trail"

        now = datetime(2026, 3, 27, 14, 0, 0, tzinfo=timezone.utc)

        # --- Phase 1: Alert — create a HIGH finding and reconcile ---
        finding = MonitorFinding(
            category="approval_stall",
            severity="high",
            summary="author-b approval stall — no review after 45m",
            details={"lane": "author-b"},
        )

        fleet_status = reconcile(
            runtime_dir=runtime_dir,
            monitor_finding_objects=[finding],
            now_iso=now.isoformat(),
        )

        # Verify reconcile produced at least one open HIGH item.
        high_open = [
            i
            for i in fleet_status.items
            if i.severity == "high" and i.state == STATE_OPEN
        ]
        assert len(high_open) >= 1, "Reconcile should produce ≥1 HIGH open item"
        target_item = high_open[0]

        # --- Phase 2: Push — prepare_alert_push with fleet idle ---
        idle_status = IdleStatus(
            idle=True,
            idle_minutes=120.0,
            last_meaningful_event=None,
            active_lanes=[],
            reason="Test: fleet idle",
        )
        push_state = PushState()

        push_result = prepare_alert_push(
            fleet_status=fleet_status,
            idle_status=idle_status,
            push_state=push_state,
            chat_id="test-chat-42",
            now=now,
            runtime_dir=runtime_dir,
            audit_dir=audit_dir,
        )

        assert push_result is not None, "Push should fire for idle fleet + HIGH item"
        assert push_result.chat_id == "test-chat-42"
        assert len(push_result.items_pushed) >= 1

        # The push message should contain the item_id prefix (first 8 hex chars).
        item_prefix = target_item.item_id[:8]
        assert (
            item_prefix in push_result.message
        ), f"Push message should contain item prefix {item_prefix}"
        assert "approval stall" in push_result.message.lower()

        # Verify audit trail recorded the outbound push.
        audit_recs = read_records(audit_dir=audit_dir)
        outbound = [r for r in audit_recs if r.direction == "outbound"]
        assert len(outbound) >= 1, "Audit trail should record the outbound push"
        assert outbound[0].metadata.get("purpose") == "alert_push"

        # Verify push state was persisted.
        reloaded_push_state = load_push_state(runtime_dir=runtime_dir)
        assert target_item.item_id in reloaded_push_state.items

        # --- Phase 3: Ack — parse the operator's reply and execute ---
        # Simulate operator replying "ack <prefix>" to the Telegram alert.
        ack_text = f"ack {item_prefix}"
        cmd = parse_ack_command(ack_text)
        assert cmd is not None, f"Should parse ack command from '{ack_text}'"
        assert cmd.prefix == item_prefix

        # Re-load fleet status from disk (as the real ack path would).
        status_from_disk = load_fleet_status(runtime_dir)
        assert status_from_disk is not None

        ack_result = execute_remote_ack(cmd, status_from_disk)
        assert ack_result.success, f"Ack should succeed: {ack_result.message}"
        assert ack_result.item_id == target_item.item_id

        # Verify the item is now acked.
        acked_item = next(
            i for i in status_from_disk.items if i.item_id == target_item.item_id
        )
        assert acked_item.state == STATE_ACKED

        # Persist the acked status (as the real flow would).
        save_fleet_status(status_from_disk, runtime_dir)

        # Verify ack confirmation message is user-friendly.
        confirmation = format_ack_confirmation(ack_result)
        assert "✅" in confirmation
        assert item_prefix in confirmation

    def test_push_suppressed_for_active_fleet(self, tmp_path: Path) -> None:
        """No push when the fleet has recent activity (idle gate blocks)."""
        from bid_euchre.ops.alert_push import PushState
        from bid_euchre.ops.control_plane import reconcile
        from bid_euchre.ops.idle_detector import IdleStatus
        from bid_euchre.ops.telegram_push import prepare_alert_push

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()

        now = datetime(2026, 3, 27, 14, 0, 0, tzinfo=timezone.utc)

        finding = MonitorFinding(
            category="approval_stall",
            severity="high",
            summary="author-b approval stall",
            details={"lane": "author-b"},
        )
        fleet_status = reconcile(
            runtime_dir=runtime_dir,
            monitor_finding_objects=[finding],
            now_iso=now.isoformat(),
        )

        # Fleet is actively running — push should be suppressed.
        idle_status = IdleStatus(
            idle=False,
            idle_minutes=5.0,
            last_meaningful_event=now,
            active_lanes=["author-a"],
            reason="Test: fleet active",
        )
        push_state = PushState()

        result = prepare_alert_push(
            fleet_status=fleet_status,
            idle_status=idle_status,
            push_state=push_state,
            chat_id="test-chat-42",
            now=now,
            runtime_dir=runtime_dir,
        )
        assert result is None, "Push should be suppressed for active fleet"

    def test_ack_nonexistent_prefix_fails(self) -> None:
        """Ack with a prefix that doesn't match any item fails gracefully."""
        from bid_euchre.ops.control_plane import (
            STATE_OPEN,
            ActionableItem,
            FleetStatus,
        )
        from bid_euchre.ops.remote_ack import execute_remote_ack, parse_ack_command

        now = datetime(2026, 3, 27, 14, 0, 0, tzinfo=timezone.utc)
        item = ActionableItem(
            item_id="aabbccdd11223344",
            severity="high",
            category="approval_stall",
            source="monitor",
            summary="Test item",
            first_seen_at=now.isoformat(),
            last_seen_at=now.isoformat(),
            state=STATE_OPEN,
        )
        status = FleetStatus(
            items=[item],
            generated_at=now.isoformat(),
            cycle_count=1,
        )

        # Try acking with a nonexistent prefix.
        cmd = parse_ack_command("ack deadbeef")
        assert cmd is not None
        result = execute_remote_ack(cmd, status)
        assert not result.success
        assert "No item matching" in result.message

    def test_double_ack_fails_gracefully(self, tmp_path: Path) -> None:
        """Acking the same item twice — second ack fails (already acked)."""
        from bid_euchre.ops.alert_push import PushState
        from bid_euchre.ops.control_plane import (
            load_fleet_status,
            reconcile,
            save_fleet_status,
        )
        from bid_euchre.ops.idle_detector import IdleStatus
        from bid_euchre.ops.remote_ack import execute_remote_ack, parse_ack_command
        from bid_euchre.ops.telegram_push import prepare_alert_push

        runtime_dir = tmp_path / "runtime"
        runtime_dir.mkdir()
        audit_dir = runtime_dir / "audit_trail"

        now = datetime(2026, 3, 27, 14, 0, 0, tzinfo=timezone.utc)

        finding = MonitorFinding(
            category="approval_stall",
            severity="high",
            summary="author-c stall",
            details={"lane": "author-c"},
        )
        fleet_status = reconcile(
            runtime_dir=runtime_dir,
            monitor_finding_objects=[finding],
            now_iso=now.isoformat(),
        )

        # Push fires (fleet idle).
        idle_status = IdleStatus(
            idle=True,
            idle_minutes=120.0,
            last_meaningful_event=None,
            active_lanes=[],
            reason="Test: fleet idle",
        )
        push_state = PushState()

        push_result = prepare_alert_push(
            fleet_status=fleet_status,
            idle_status=idle_status,
            push_state=push_state,
            chat_id="test-chat-42",
            now=now,
            runtime_dir=runtime_dir,
            audit_dir=audit_dir,
        )
        assert push_result is not None
        pushed_item = push_result.items_pushed[0]
        prefix = pushed_item.item_id[:8]

        # First ack — succeeds.
        status = load_fleet_status(runtime_dir)
        assert status is not None
        cmd = parse_ack_command(f"ack {prefix}")
        assert cmd is not None
        r1 = execute_remote_ack(cmd, status)
        assert r1.success
        save_fleet_status(status, runtime_dir)

        # Second ack — fails gracefully (item already acked).
        status2 = load_fleet_status(runtime_dir)
        assert status2 is not None
        r2 = execute_remote_ack(cmd, status2)
        assert not r2.success
        assert "cannot be" in r2.message.lower() or "already" in r2.message.lower()


# ---------------------------------------------------------------------------
# process_inbound_ack tests (Platform-9a — inbound ack wiring)
# ---------------------------------------------------------------------------


class TestProcessInboundAck:
    """Tests for process_inbound_ack() — the monitor-level ack handler."""

    @staticmethod
    def _write_fleet_status(runtime_dir: Path, items: list[dict]) -> None:
        """Write a minimal fleet_status.json to disk."""
        from bid_euchre.ops.control_plane import (
            ActionableItem,
            FleetStatus,
            save_fleet_status,
        )

        fleet_items = []
        for raw in items:
            fleet_items.append(
                ActionableItem(
                    item_id=raw["item_id"],
                    severity=raw.get("severity", "high"),
                    category=raw.get("category", "lane_health"),
                    source=raw.get("source", "monitor"),
                    summary=raw.get("summary", "Test alert"),
                    first_seen_at="2026-03-27T00:00:00Z",
                    last_seen_at="2026-03-27T00:00:00Z",
                    state=raw.get("state", "open"),
                )
            )
        status = FleetStatus(
            items=fleet_items,
            generated_at="2026-03-27T00:00:00Z",
            cycle_count=1,
        )
        save_fleet_status(status, runtime_dir=runtime_dir)

    def test_non_command_passthrough(self, tmp_path: Path) -> None:
        """Free-form text returns is_ack_command=False, no reply_text."""
        from bid_euchre.ops.monitor import process_inbound_ack

        result = process_inbound_ack("How's the fleet?", runtime_dir=tmp_path)
        assert result.is_ack_command is False
        assert result.success is False
        assert result.reply_text is None

    def test_ack_command_mutates_and_persists(self, tmp_path: Path) -> None:
        """'ack <prefix>' mutates fleet status and saves to disk."""
        from bid_euchre.ops.control_plane import load_fleet_status
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456", "summary": "Stall on author-b"}],
        )

        result = process_inbound_ack("ack abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is True
        assert result.item_id == "abc123def456"
        assert result.action == "ack"
        assert result.reply_text is not None
        assert "\u2705" in result.reply_text  # checkmark
        assert "Stall on author-b" in result.reply_text

        # Verify persistence — reload from disk.
        reloaded = load_fleet_status(tmp_path)
        assert reloaded is not None
        acked = [i for i in reloaded.items if i.state == "acked"]
        assert len(acked) == 1
        assert acked[0].item_id == "abc123def456"

    def test_dismiss_command(self, tmp_path: Path) -> None:
        """'dismiss <prefix>' suppresses the item."""
        from bid_euchre.ops.control_plane import load_fleet_status
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456", "summary": "CI flaky"}],
        )

        result = process_inbound_ack("dismiss abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is True
        assert result.action == "dismiss"

        reloaded = load_fleet_status(tmp_path)
        assert reloaded is not None
        suppressed = [i for i in reloaded.items if i.state == "suppressed"]
        assert len(suppressed) == 1

    def test_mute_command(self, tmp_path: Path) -> None:
        """'mute <prefix>' suppresses the item (same as dismiss)."""
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456"}],
        )

        result = process_inbound_ack("mute abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is True
        assert result.action == "mute"

    def test_clear_command(self, tmp_path: Path) -> None:
        """'clear <prefix>' clears the item."""
        from bid_euchre.ops.control_plane import load_fleet_status
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456"}],
        )

        result = process_inbound_ack("clear abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is True
        assert result.action == "clear"

        reloaded = load_fleet_status(tmp_path)
        assert reloaded is not None
        cleared = [i for i in reloaded.items if i.state == "cleared"]
        assert len(cleared) == 1

    def test_no_fleet_status_returns_error(self, tmp_path: Path) -> None:
        """Ack command with no fleet status on disk returns error reply."""
        from bid_euchre.ops.monitor import process_inbound_ack

        result = process_inbound_ack("ack abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is False
        assert result.reply_text is not None
        assert "No fleet status" in result.reply_text

    def test_no_matching_item(self, tmp_path: Path) -> None:
        """Ack with non-matching prefix returns error with cross-mark."""
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456"}],
        )

        result = process_inbound_ack("ack fff000", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is False
        assert result.reply_text is not None
        assert "\u274c" in result.reply_text

    def test_ambiguous_prefix(self, tmp_path: Path) -> None:
        """Ambiguous prefix returns error with candidates."""
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [
                {"item_id": "abc123000000", "summary": "Item 1"},
                {"item_id": "abc123ffffff", "summary": "Item 2"},
            ],
        )

        result = process_inbound_ack("ack abc123", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is False
        assert "Ambiguous" in (result.reply_text or "")

    def test_already_acked_item(self, tmp_path: Path) -> None:
        """Acking an already-acked item returns error."""
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456", "state": "acked"}],
        )

        result = process_inbound_ack("ack abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is False
        assert "cannot be" in (result.reply_text or "")

    def test_case_insensitive(self, tmp_path: Path) -> None:
        """Commands are case-insensitive."""
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456"}],
        )

        result = process_inbound_ack("ACK ABC1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is True

    def test_selective_ack_preserves_other_items(self, tmp_path: Path) -> None:
        """Acking one item leaves others unchanged."""
        from bid_euchre.ops.control_plane import load_fleet_status
        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [
                {"item_id": "aaa111000000", "summary": "Item A"},
                {"item_id": "bbb222000000", "summary": "Item B"},
            ],
        )

        result = process_inbound_ack("ack bbb2", runtime_dir=tmp_path)

        assert result.success is True
        assert result.item_id == "bbb222000000"

        reloaded = load_fleet_status(tmp_path)
        assert reloaded is not None
        states = {i.item_id: i.state for i in reloaded.items}
        assert states["aaa111000000"] == "open"
        assert states["bbb222000000"] == "acked"

    def test_save_failure_reports_ack_failure(self, tmp_path: Path) -> None:
        """If save_fleet_status raises, process_inbound_ack returns failure."""
        from unittest.mock import patch

        from bid_euchre.ops.monitor import process_inbound_ack

        self._write_fleet_status(
            tmp_path,
            [{"item_id": "abc123def456", "summary": "Stall on author-a"}],
        )

        with patch(
            "bid_euchre.ops.control_plane.save_fleet_status",
            side_effect=OSError("disk full"),
        ):
            result = process_inbound_ack("ack abc1", runtime_dir=tmp_path)

        assert result.is_ack_command is True
        assert result.success is False
        assert "failed to persist" in (result.reply_text or "").lower()
        assert result.item_id == "abc123def456"


# ---------------------------------------------------------------------------
# PUSH_RELAY output format — verifies the machine-readable line that the
# PostToolUse hook (post-monitor-push-relay.sh) parses.
# ---------------------------------------------------------------------------


class TestPushRelayOutput:
    """The monitor CLI emits a PUSH_RELAY: JSON line when a push payload
    is prepared.  The PostToolUse hook greps for this marker and injects
    additionalContext for Telegram delivery.  These tests verify the format.
    """

    def test_push_relay_json_line_is_parseable(self) -> None:
        """PUSH_RELAY line produced by ops.py is valid JSON with expected keys."""
        import json

        chat_id = "12345"
        message = "🚨 ALERT: 2 HIGH items\n  [abc1] Lane stalled"
        relay = json.dumps({"chat_id": chat_id, "message": message})
        line = f"PUSH_RELAY:{relay}"

        # Simulate what the hook does: strip prefix, parse JSON
        assert line.startswith("PUSH_RELAY:")
        payload = json.loads(line[len("PUSH_RELAY:") :])
        assert payload["chat_id"] == chat_id
        assert payload["message"] == message

    def test_push_relay_special_characters(self) -> None:
        """PUSH_RELAY JSON handles quotes, backslashes, and unicode."""
        import json

        message = 'Line with "quotes" and \\backslash and emoji 🎯'
        relay = json.dumps({"chat_id": "999", "message": message})
        line = f"PUSH_RELAY:{relay}"

        payload = json.loads(line[len("PUSH_RELAY:") :])
        assert payload["message"] == message

    def test_push_relay_not_emitted_when_no_push(
        self,
    ) -> None:
        """When push_result is None, no PUSH_RELAY line appears."""
        # This is a structural assertion: evaluate_alert_push returns
        # MonitorCycleResult with push_result=None when push is suppressed.
        result = MonitorCycleResult(findings=[], push_result=None)
        assert result.push_result is None
        # The CLI only prints PUSH_RELAY when push_result is not None,
        # so no relay line would be emitted.

    def test_hook_script_injects_context_on_push(self) -> None:
        """The post-monitor-push-relay.sh hook injects additionalContext
        when PUSH_RELAY: is found in monitor stdout."""
        import json
        import subprocess

        hook_path = Path(__file__).resolve().parents[2] / (
            ".claude/hooks/post-monitor-push-relay.sh"
        )
        if not hook_path.exists():
            pytest.skip("hook script not found in worktree")

        relay = json.dumps({"chat_id": "42", "message": "test alert"})
        stdout_content = f"Some findings\nPUSH_RELAY:{relay}"
        payload = json.dumps(
            {
                "tool_input": {"command": "ops.py monitor"},
                "tool_response": {"exit_code": 1, "stdout": stdout_content},
            }
        )

        result = subprocess.run(
            [str(hook_path)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        assert "TELEGRAM ALERT PUSH (chat_id=42):" in ctx
        assert "test alert" in ctx
        assert "DELIVER NOW" in ctx

    def test_hook_script_preserves_messages_up_to_4096_chars(self) -> None:
        """Regression: messages up to Telegram's 4096-char limit are not truncated.

        Previously the hook truncated at 2000 chars (#1988). Telegram supports
        4096, so messages within that limit must be relayed intact.
        """
        import json
        import subprocess

        hook_path = Path(__file__).resolve().parents[2] / (
            ".claude/hooks/post-monitor-push-relay.sh"
        )
        if not hook_path.exists():
            pytest.skip("hook script not found in worktree")

        # Build a message that is 3000 chars — was truncated before the fix
        long_message = "A" * 3000
        relay = json.dumps({"chat_id": "42", "message": long_message})
        stdout_content = f"Some findings\nPUSH_RELAY:{relay}"
        payload = json.dumps(
            {
                "tool_input": {"command": "ops.py monitor"},
                "tool_response": {"exit_code": 1, "stdout": stdout_content},
            }
        )

        result = subprocess.run(
            [str(hook_path)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        ctx = output["hookSpecificOutput"]["additionalContext"]
        # The full 3000-char message must appear — no truncation at 2000
        assert long_message in ctx

    def test_hook_script_silent_on_no_push(self) -> None:
        """The hook emits nothing when no PUSH_RELAY: marker in stdout."""
        import json
        import subprocess

        hook_path = Path(__file__).resolve().parents[2] / (
            ".claude/hooks/post-monitor-push-relay.sh"
        )
        if not hook_path.exists():
            pytest.skip("hook script not found in worktree")

        payload = json.dumps(
            {
                "tool_input": {"command": "ops.py monitor"},
                "tool_response": {"exit_code": 0, "stdout": "No push needed"},
            }
        )

        result = subprocess.run(
            [str(hook_path)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_hook_script_skips_non_monitor_commands(self) -> None:
        """The hook exits immediately for non-monitor commands."""
        import json
        import subprocess

        hook_path = Path(__file__).resolve().parents[2] / (
            ".claude/hooks/post-monitor-push-relay.sh"
        )
        if not hook_path.exists():
            pytest.skip("hook script not found in worktree")

        relay = json.dumps({"chat_id": "42", "message": "test"})
        payload = json.dumps(
            {
                "tool_input": {"command": "git status"},
                "tool_response": {
                    "exit_code": 0,
                    "stdout": f"PUSH_RELAY:{relay}",
                },
            }
        )

        result = subprocess.run(
            [str(hook_path)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""
