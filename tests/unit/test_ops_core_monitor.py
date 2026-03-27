"""Tests for MonitorService — the concrete AbstractMonitor implementation.

Platform-10 PR2: verifies that MonitorService correctly implements
the AbstractMonitor interface and delegates to monitor module functions.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bid_euchre.ops.core import AbstractMonitor
from bid_euchre.ops.core.monitor import MonitorService
from bid_euchre.ops.monitor import MonitorFinding


class TestMonitorServiceIsAbstractMonitor:
    """Verify MonitorService properly implements the ABC."""

    def test_is_subclass(self) -> None:
        assert issubclass(MonitorService, AbstractMonitor)

    def test_can_instantiate(self) -> None:
        mon = MonitorService()
        assert isinstance(mon, AbstractMonitor)

    def test_custom_runtime_dir(self, tmp_path: Path) -> None:
        mon = MonitorService(runtime_dir=tmp_path)
        assert mon._runtime_dir == tmp_path


class TestRunCycle:
    """Verify run_cycle() delegates and converts output to dicts."""

    @patch("bid_euchre.ops.monitor.run_monitoring_cycle")
    def test_run_cycle_delegates(self, mock_cycle: MagicMock) -> None:
        mock_cycle.return_value = [
            MonitorFinding(
                category="lane_health",
                severity="warn",
                summary="Test finding",
                details={"lane_id": "author-a"},
            ),
        ]
        mon = MonitorService()
        result = mon.run_cycle(skip_pr_check=True, notify_orchestrator=False)

        mock_cycle.assert_called_once_with(
            runtime_dir=None,
            skip_pr_check=True,
            notify_orchestrator=False,
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["category"] == "lane_health"
        assert result[0]["severity"] == "warn"
        assert result[0]["details"]["lane_id"] == "author-a"

    @patch("bid_euchre.ops.monitor.run_monitoring_cycle")
    def test_run_cycle_empty(self, mock_cycle: MagicMock) -> None:
        mock_cycle.return_value = []
        mon = MonitorService()
        result = mon.run_cycle()
        assert result == []

    @patch("bid_euchre.ops.monitor.run_monitoring_cycle")
    def test_run_cycle_passes_runtime_dir(self, mock_cycle: MagicMock) -> None:
        mock_cycle.return_value = []
        rt = Path("/tmp/test-runtime")
        mon = MonitorService(runtime_dir=rt)
        mon.run_cycle(skip_pr_check=True)
        mock_cycle.assert_called_once_with(
            runtime_dir=rt,
            skip_pr_check=True,
        )


class TestCheckLaneHealth:
    """Verify check_lane_health() delegates and converts."""

    @patch("bid_euchre.ops.monitor.check_lane_health")
    def test_delegates(self, mock_check: MagicMock) -> None:
        mock_check.return_value = [
            MonitorFinding(
                category="lane_health",
                severity="high",
                summary="Lane degraded",
                details={"lane_id": "author-b", "reason": "no tmux pane"},
            ),
        ]
        mon = MonitorService()
        result = mon.check_lane_health()

        mock_check.assert_called_once_with(None)
        assert len(result) == 1
        assert result[0]["severity"] == "high"
        assert result[0]["details"]["lane_id"] == "author-b"

    @patch("bid_euchre.ops.monitor.check_lane_health")
    def test_passes_runtime_dir(self, mock_check: MagicMock) -> None:
        mock_check.return_value = []
        rt = Path("/tmp/rt")
        mon = MonitorService(runtime_dir=rt)
        mon.check_lane_health()
        mock_check.assert_called_once_with(rt)


class TestCheckStaleDispatches:
    """Verify check_stale_dispatches() delegates and converts."""

    @patch("bid_euchre.ops.monitor.check_stale_dispatches")
    def test_delegates(self, mock_check: MagicMock) -> None:
        mock_check.return_value = [
            MonitorFinding(
                category="stale_dispatch",
                severity="high",
                summary="Stale packet",
                details={"packet_id": "pkt-1"},
            ),
        ]
        mon = MonitorService()
        result = mon.check_stale_dispatches()

        mock_check.assert_called_once_with(None)
        assert len(result) == 1
        assert result[0]["category"] == "stale_dispatch"

    @patch("bid_euchre.ops.monitor.check_stale_dispatches")
    def test_passes_runtime_dir(self, mock_check: MagicMock) -> None:
        mock_check.return_value = []
        rt = Path("/tmp/rt")
        mon = MonitorService(runtime_dir=rt)
        mon.check_stale_dispatches()
        mock_check.assert_called_once_with(rt)


class TestCheckIdleLanes:
    """Verify check_idle_lanes() delegates and converts."""

    @patch("bid_euchre.ops.monitor.check_idle_lanes")
    def test_delegates(self, mock_check: MagicMock) -> None:
        mock_check.return_value = [
            MonitorFinding(
                category="idle_lane",
                severity="info",
                summary="Lane idle",
                details={"lane_id": "author-c"},
            ),
        ]
        mon = MonitorService()
        result = mon.check_idle_lanes()

        mock_check.assert_called_once_with(None)
        assert len(result) == 1
        assert result[0]["category"] == "idle_lane"

    @patch("bid_euchre.ops.monitor.check_idle_lanes")
    def test_passes_runtime_dir(self, mock_check: MagicMock) -> None:
        mock_check.return_value = []
        rt = Path("/tmp/rt")
        mon = MonitorService(runtime_dir=rt)
        mon.check_idle_lanes()
        mock_check.assert_called_once_with(rt)


class TestFindingsToDicts:
    """Verify the static converter helper."""

    def test_converts_findings(self) -> None:
        findings = [
            MonitorFinding(
                category="test",
                severity="info",
                summary="hello",
                details={"key": "value"},
            ),
            MonitorFinding(
                category="test2",
                severity="warn",
                summary="world",
            ),
        ]
        result = MonitorService._findings_to_dicts(findings)
        assert len(result) == 2
        assert all(isinstance(d, dict) for d in result)
        assert result[0]["summary"] == "hello"
        assert result[1]["details"] == {}

    def test_empty_list(self) -> None:
        assert MonitorService._findings_to_dicts([]) == []


class TestRunCycleMultipleFindings:
    """Verify run_cycle() correctly converts multiple findings."""

    @patch("bid_euchre.ops.monitor.run_monitoring_cycle")
    def test_multiple_categories(self, mock_cycle: MagicMock) -> None:
        """Multiple findings from different categories all convert correctly."""
        mock_cycle.return_value = [
            MonitorFinding(
                category="lane_health",
                severity="high",
                summary="Lane degraded",
                details={"lane_id": "author-a"},
            ),
            MonitorFinding(
                category="stale_dispatch",
                severity="warn",
                summary="Stale 30m",
                details={"packet_id": "pkt-1", "elapsed": 30},
            ),
            MonitorFinding(
                category="idle_lane",
                severity="info",
                summary="Lane idle",
                details={"lane_id": "author-c"},
            ),
        ]
        mon = MonitorService()
        result = mon.run_cycle()

        assert len(result) == 3
        categories = [d["category"] for d in result]
        assert categories == ["lane_health", "stale_dispatch", "idle_lane"]

    @patch("bid_euchre.ops.monitor.run_monitoring_cycle")
    def test_findings_are_independent_dicts(self, mock_cycle: MagicMock) -> None:
        """Each finding converts to an independent dict (no shared references)."""
        mock_cycle.return_value = [
            MonitorFinding(
                category="test",
                severity="info",
                summary="A",
                details={"key": "val1"},
            ),
            MonitorFinding(
                category="test",
                severity="info",
                summary="B",
                details={"key": "val2"},
            ),
        ]
        mon = MonitorService()
        result = mon.run_cycle()

        # Mutating one dict shouldn't affect the other
        result[0]["details"]["key"] = "mutated"
        assert result[1]["details"]["key"] == "val2"


class TestFindingsFieldPreservation:
    """Verify that all MonitorFinding fields survive dict conversion."""

    def test_all_fields_present_in_dict(self) -> None:
        """Every MonitorFinding field appears in the converted dict."""
        finding = MonitorFinding(
            category="stale_dispatch",
            severity="high",
            summary="Stale packet pkt-abc",
            details={"packet_id": "pkt-abc", "owner": "author-d"},
        )
        result = MonitorService._findings_to_dicts([finding])
        d = result[0]

        assert d["category"] == "stale_dispatch"
        assert d["severity"] == "high"
        assert d["summary"] == "Stale packet pkt-abc"
        assert d["details"]["packet_id"] == "pkt-abc"
        assert d["details"]["owner"] == "author-d"

    def test_empty_details_produces_empty_dict(self) -> None:
        """A finding with default (empty) details converts to empty dict."""
        finding = MonitorFinding(
            category="test",
            severity="info",
            summary="No details",
        )
        result = MonitorService._findings_to_dicts([finding])
        assert result[0]["details"] == {}

    def test_nested_details_preserved(self) -> None:
        """Nested structures in details survive conversion."""
        nested = {
            "lane_id": "author-a",
            "checks": [
                {"name": "health", "passed": True},
                {"name": "stale", "passed": False},
            ],
            "metadata": {"inner": {"deep": 42}},
        }
        finding = MonitorFinding(
            category="complex",
            severity="warn",
            summary="Nested details",
            details=nested,
        )
        result = MonitorService._findings_to_dicts([finding])
        d = result[0]["details"]

        assert d["checks"][1]["passed"] is False
        assert d["metadata"]["inner"]["deep"] == 42


class TestModuleExports:
    """Verify core __init__.py exports include the new classes."""

    def test_controller_exported(self) -> None:
        import bid_euchre.ops.core as core_mod

        assert hasattr(core_mod, "ControlPlaneController")

    def test_monitor_exported(self) -> None:
        import bid_euchre.ops.core as core_mod

        assert hasattr(core_mod, "MonitorService")

    def test_all_includes_new_classes(self) -> None:
        import bid_euchre.ops.core as core_mod

        assert "ControlPlaneController" in core_mod.__all__
        assert "MonitorService" in core_mod.__all__
