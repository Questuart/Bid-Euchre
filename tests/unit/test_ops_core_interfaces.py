"""Tests for ops core ABCs — verify they cannot be instantiated directly.

Platform-10 PR1: the ABCs define the contract that repo-specific adapters
must implement.  These tests verify that:

1. ABCs cannot be instantiated directly (TypeError).
2. A concrete subclass that implements all abstract methods CAN be
   instantiated.
3. A concrete subclass that omits an abstract method CANNOT be instantiated.
4. The ``__init__.py`` re-exports all four ABCs.
"""

from __future__ import annotations

from typing import Any

import pytest

from bid_euchre.ops.core import (
    AbstractController,
    AbstractLaneConfig,
    AbstractMonitor,
    AbstractTaskQueue,
    AbstractWorkerPool,
)
from bid_euchre.ops.core.interfaces import (
    AbstractController as DirectController,
)
from bid_euchre.ops.core.interfaces import (
    AbstractLaneConfig as DirectLaneConfig,
)
from bid_euchre.ops.core.interfaces import (
    AbstractMonitor as DirectMonitor,
)
from bid_euchre.ops.core.interfaces import (
    AbstractTaskQueue as DirectTaskQueue,
)
from bid_euchre.ops.core.interfaces import (
    AbstractWorkerPool as DirectWorkerPool,
)

# ---------------------------------------------------------------------------
# Test: ABCs cannot be instantiated directly
# ---------------------------------------------------------------------------


class TestAbstractControllerNotInstantiable:
    """AbstractController raises TypeError on direct instantiation."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            AbstractController()  # type: ignore[abstract]

    def test_re_export_matches_direct(self) -> None:
        assert AbstractController is DirectController


class TestAbstractMonitorNotInstantiable:
    """AbstractMonitor raises TypeError on direct instantiation."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            AbstractMonitor()  # type: ignore[abstract]

    def test_re_export_matches_direct(self) -> None:
        assert AbstractMonitor is DirectMonitor


class TestAbstractTaskQueueNotInstantiable:
    """AbstractTaskQueue raises TypeError on direct instantiation."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            AbstractTaskQueue()  # type: ignore[abstract]

    def test_re_export_matches_direct(self) -> None:
        assert AbstractTaskQueue is DirectTaskQueue


class TestAbstractLaneConfigNotInstantiable:
    """AbstractLaneConfig raises TypeError on direct instantiation."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            AbstractLaneConfig()  # type: ignore[abstract]

    def test_re_export_matches_direct(self) -> None:
        assert AbstractLaneConfig is DirectLaneConfig


class TestAbstractWorkerPoolNotInstantiable:
    """AbstractWorkerPool raises TypeError on direct instantiation."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            AbstractWorkerPool()  # type: ignore[abstract]

    def test_re_export_matches_direct(self) -> None:
        assert AbstractWorkerPool is DirectWorkerPool


# ---------------------------------------------------------------------------
# Test: Concrete subclass with all methods implemented CAN be instantiated
# ---------------------------------------------------------------------------


class _StubController(AbstractController):
    """Minimal concrete implementation for testing."""

    def reconcile(self, **kwargs: Any) -> Any:
        return {"items": [], "cycle_count": 1}

    def load_status(self) -> Any | None:
        return None

    def save_status(self, status: Any) -> None:
        pass

    def ack_item(self, item_id: str) -> bool:
        return True

    def clear_item(self, item_id: str) -> bool:
        return True

    def suppress_item(self, item_id: str) -> bool:
        return True


class _StubMonitor(AbstractMonitor):
    """Minimal concrete implementation for testing."""

    def run_cycle(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def check_lane_health(self) -> list[dict[str, Any]]:
        return []

    def check_stale_dispatches(self) -> list[dict[str, Any]]:
        return []

    def check_idle_lanes(self) -> list[dict[str, Any]]:
        return []


class _StubTaskQueue(AbstractTaskQueue):
    """Minimal concrete implementation for testing."""

    def create_packet(self, title: str, description: str, **kwargs: Any) -> Any:
        return {"packet_id": "test", "title": title}

    def save_packet(self, packet: Any) -> Any:
        return "/tmp/test"

    def load_packet(self, packet_id: str) -> Any | None:
        return None

    def list_packets(self, **kwargs: Any) -> list[Any]:
        return []

    def transition_status(self, packet_id: str, new_status: str, **kwargs: Any) -> Any:
        return {"packet_id": packet_id, "status": new_status}

    def archive_packet(self, packet_id: str) -> bool:
        return True

    def complete_packet(self, packet_id: str, **kwargs: Any) -> Any:
        return {"packet_id": packet_id, "status": "completed"}

    def queue_summary(self) -> dict[str, Any]:
        return {"total": 0}


class _StubLaneConfig(AbstractLaneConfig):
    """Minimal concrete implementation for testing."""

    def known_lanes(self) -> frozenset[str]:
        return frozenset({"test-lane-a", "test-lane-b"})

    def lane_domains(self) -> dict[str, str | None]:
        return {"test-lane-a": "domain-x", "test-lane-b": None}

    def pane_name_for_lane(self, lane_id: str) -> str | None:
        if lane_id in ("test-lane-a", "test-lane-b"):
            return lane_id
        return None

    def legacy_lanes(self) -> frozenset[str]:
        return frozenset({"old-lane"})


class _StubWorkerPool(AbstractWorkerPool):
    """Minimal concrete implementation for testing."""

    def take_snapshot(self) -> Any:
        return {"workers": [], "timestamp": "2026-01-01T00:00:00Z"}

    def select_worker(self, snapshot: Any, **kwargs: Any) -> str | None:
        return None

    def dispatch_to_worker(self, packet_id: str, lane_id: str) -> Any:
        return {"action": "dispatched", "lane_id": lane_id}

    def wake_worker(self, lane_id: str) -> Any:
        return {"action": "woken", "lane_id": lane_id}

    def park_worker(self, lane_id: str) -> Any:
        return {"action": "parked", "lane_id": lane_id}

    def nudge_pane(self, lane_id: str, text: str) -> bool:
        return True


class TestConcreteSubclasses:
    """Concrete subclasses with all methods implemented can be instantiated."""

    def test_stub_controller(self) -> None:
        ctrl = _StubController()
        assert isinstance(ctrl, AbstractController)
        result = ctrl.reconcile()
        assert isinstance(result, dict)
        assert ctrl.load_status() is None
        ctrl.save_status({"items": []})
        assert ctrl.ack_item("test") is True
        assert ctrl.clear_item("test") is True
        assert ctrl.suppress_item("test") is True

    def test_stub_monitor(self) -> None:
        mon = _StubMonitor()
        assert isinstance(mon, AbstractMonitor)
        findings = mon.run_cycle()
        assert isinstance(findings, list)
        assert mon.check_lane_health() == []
        assert mon.check_stale_dispatches() == []
        assert mon.check_idle_lanes() == []

    def test_stub_task_queue(self) -> None:
        tq = _StubTaskQueue()
        assert isinstance(tq, AbstractTaskQueue)
        pkt = tq.create_packet("Test", "Description")
        assert pkt["title"] == "Test"
        assert tq.load_packet("missing") is None
        assert tq.list_packets() == []
        assert tq.archive_packet("test") is True
        assert tq.queue_summary()["total"] == 0

    def test_stub_lane_config(self) -> None:
        lc = _StubLaneConfig()
        assert isinstance(lc, AbstractLaneConfig)
        lanes = lc.known_lanes()
        assert isinstance(lanes, frozenset)
        assert "test-lane-a" in lanes
        assert "test-lane-b" in lanes
        domains = lc.lane_domains()
        assert domains["test-lane-a"] == "domain-x"
        assert domains["test-lane-b"] is None
        assert lc.pane_name_for_lane("test-lane-a") == "test-lane-a"
        assert lc.pane_name_for_lane("unknown") is None
        assert "old-lane" in lc.legacy_lanes()

    def test_stub_worker_pool(self) -> None:
        wp = _StubWorkerPool()
        assert isinstance(wp, AbstractWorkerPool)
        snap = wp.take_snapshot()
        assert isinstance(snap, dict)
        assert wp.select_worker(snap) is None
        result = wp.dispatch_to_worker("pkt1", "author-a")
        assert result["lane_id"] == "author-a"
        assert wp.nudge_pane("author-a", "/start-task abc") is True


# ---------------------------------------------------------------------------
# Test: Partial subclass (missing methods) CANNOT be instantiated
# ---------------------------------------------------------------------------


class _PartialController(AbstractController):
    """Missing suppress_item — should fail to instantiate."""

    def reconcile(self, **kwargs: Any) -> Any:
        return {}

    def load_status(self) -> Any | None:
        return None

    def save_status(self, status: Any) -> None:
        pass

    def ack_item(self, item_id: str) -> bool:
        return True

    def clear_item(self, item_id: str) -> bool:
        return True

    # suppress_item intentionally omitted


class _PartialMonitor(AbstractMonitor):
    """Missing check_idle_lanes — should fail to instantiate."""

    def run_cycle(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def check_lane_health(self) -> list[dict[str, Any]]:
        return []

    def check_stale_dispatches(self) -> list[dict[str, Any]]:
        return []

    # check_idle_lanes intentionally omitted


class _PartialTaskQueue(AbstractTaskQueue):
    """Missing queue_summary — should fail to instantiate."""

    def create_packet(self, title: str, description: str, **kwargs: Any) -> Any:
        return {}

    def save_packet(self, packet: Any) -> Any:
        return ""

    def load_packet(self, packet_id: str) -> Any | None:
        return None

    def list_packets(self, **kwargs: Any) -> list[Any]:
        return []

    def transition_status(self, packet_id: str, new_status: str, **kwargs: Any) -> Any:
        return {}

    def archive_packet(self, packet_id: str) -> bool:
        return True

    def complete_packet(self, packet_id: str, **kwargs: Any) -> Any:
        return {}

    # queue_summary intentionally omitted


class _PartialLaneConfig(AbstractLaneConfig):
    """Missing legacy_lanes — should fail to instantiate."""

    def known_lanes(self) -> frozenset[str]:
        return frozenset()

    def lane_domains(self) -> dict[str, str | None]:
        return {}

    def pane_name_for_lane(self, lane_id: str) -> str | None:
        return None

    # legacy_lanes intentionally omitted


class _PartialWorkerPool(AbstractWorkerPool):
    """Missing nudge_pane — should fail to instantiate."""

    def take_snapshot(self) -> Any:
        return {}

    def select_worker(self, snapshot: Any, **kwargs: Any) -> str | None:
        return None

    def dispatch_to_worker(self, packet_id: str, lane_id: str) -> Any:
        return {}

    def wake_worker(self, lane_id: str) -> Any:
        return {}

    def park_worker(self, lane_id: str) -> Any:
        return {}

    # nudge_pane intentionally omitted


class TestPartialSubclasses:
    """Partial subclasses missing abstract methods cannot be instantiated."""

    def test_partial_controller(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            _PartialController()  # type: ignore[abstract]

    def test_partial_monitor(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            _PartialMonitor()  # type: ignore[abstract]

    def test_partial_task_queue(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            _PartialTaskQueue()  # type: ignore[abstract]

    def test_partial_lane_config(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            _PartialLaneConfig()  # type: ignore[abstract]

    def test_partial_worker_pool(self) -> None:
        with pytest.raises(TypeError, match="abstract method"):
            _PartialWorkerPool()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Test: __all__ exports
# ---------------------------------------------------------------------------


class TestModuleExports:
    """Verify __init__.py __all__ contains all expected names."""

    def test_all_exports_include_abcs(self) -> None:
        import bid_euchre.ops.core as core_mod

        expected_abcs = {
            "AbstractController",
            "AbstractLaneConfig",
            "AbstractMonitor",
            "AbstractTaskQueue",
            "AbstractWorkerPool",
        }
        assert expected_abcs.issubset(set(core_mod.__all__))

    def test_abcs_are_not_instantiable(self) -> None:
        """ABC exports cannot be instantiated directly."""
        import bid_euchre.ops.core as core_mod

        abc_names = [
            "AbstractController",
            "AbstractLaneConfig",
            "AbstractMonitor",
            "AbstractTaskQueue",
            "AbstractWorkerPool",
        ]
        for name in abc_names:
            cls = getattr(core_mod, name)
            with pytest.raises(TypeError):
                cls()  # type: ignore[abstract]
