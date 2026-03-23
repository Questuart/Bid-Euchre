"""Tests for ops monitoring cycle (SP-3-08)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from bid_euchre.ops.monitor import (
    MAX_AUTO_DISPATCH_PER_CYCLE,
    SEVERITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_WARN,
    MonitorFinding,
    _default_stall_state_path,
    _save_stall_state,
    check_auto_dispatch,
    check_lane_health,
    check_merged_dispatches,
    check_open_prs,
    check_stale_dispatches,
    check_stalled_lanes,
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
