"""Tests for core ops adapter contract conformance and cross-adapter integration.

Platform-10 PR4: verifies that all four concrete adapters correctly satisfy
their ABC contracts from the *core* perspective — polymorphism, method
signature conformance, and integration between adapters (controller consuming
monitor output).

This complements the per-class tests in ``test_ops_core_controller.py``,
``test_ops_core_monitor.py``, and ``test_ops_adapter_migration.py`` by
focusing on cross-cutting properties that hold across the full adapter set.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from bid_euchre.ops.core.interfaces import (
    AbstractController,
    AbstractMonitor,
    AbstractTaskQueue,
    AbstractWorkerPool,
)

# ---------------------------------------------------------------------------
# ABC ↔ adapter pairings for parametric tests
# ---------------------------------------------------------------------------

_ADAPTER_PAIRS: list[tuple[type, str, str]] = [
    (
        AbstractController,
        "bid_euchre.ops.core.controller",
        "ControlPlaneController",
    ),
    (
        AbstractMonitor,
        "bid_euchre.ops.core.monitor",
        "MonitorService",
    ),
    (
        AbstractTaskQueue,
        "bid_euchre.ops.adapters.bid_euchre",
        "TaskQueueService",
    ),
    (
        AbstractWorkerPool,
        "bid_euchre.ops.adapters.bid_euchre",
        "WorkerPoolService",
    ),
]


def _import_adapter(module_path: str, class_name: str) -> type:
    """Import an adapter class by module path and class name."""
    import importlib

    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


# ---------------------------------------------------------------------------
# Test: Method signature conformance — adapter signatures match ABCs
# ---------------------------------------------------------------------------


class TestMethodSignatureConformance:
    """Every adapter's public methods match the ABC method signatures.

    This catches signature drift: if an adapter renames a parameter, drops
    a keyword argument, or changes a default value, the test fails.
    """

    @pytest.mark.parametrize(
        "abc_cls,module_path,class_name",
        _ADAPTER_PAIRS,
        ids=["Controller", "Monitor", "TaskQueue", "WorkerPool"],
    )
    def test_all_abstract_methods_present(
        self,
        abc_cls: type,
        module_path: str,
        class_name: str,
    ) -> None:
        """Adapter implements every abstract method declared by the ABC."""
        adapter_cls = _import_adapter(module_path, class_name)

        abstract_methods = {
            name
            for name, _ in inspect.getmembers(abc_cls, predicate=inspect.isfunction)
            if getattr(getattr(abc_cls, name, None), "__isabstractmethod__", False)
        }

        for method_name in abstract_methods:
            assert hasattr(
                adapter_cls, method_name
            ), f"{class_name} missing abstract method {method_name!r}"

    @pytest.mark.parametrize(
        "abc_cls,module_path,class_name",
        _ADAPTER_PAIRS,
        ids=["Controller", "Monitor", "TaskQueue", "WorkerPool"],
    )
    def test_parameter_names_match(
        self,
        abc_cls: type,
        module_path: str,
        class_name: str,
    ) -> None:
        """Adapter method parameter names match the ABC's parameter names."""
        adapter_cls = _import_adapter(module_path, class_name)

        abstract_methods = {
            name
            for name, _ in inspect.getmembers(abc_cls, predicate=inspect.isfunction)
            if getattr(getattr(abc_cls, name, None), "__isabstractmethod__", False)
        }

        for method_name in abstract_methods:
            abc_sig = inspect.signature(getattr(abc_cls, method_name))
            adapter_sig = inspect.signature(getattr(adapter_cls, method_name))

            abc_params = list(abc_sig.parameters.keys())
            adapter_params = list(adapter_sig.parameters.keys())

            assert abc_params == adapter_params, (
                f"{class_name}.{method_name}: parameter names differ — "
                f"ABC has {abc_params}, adapter has {adapter_params}"
            )

    @pytest.mark.parametrize(
        "abc_cls,module_path,class_name",
        _ADAPTER_PAIRS,
        ids=["Controller", "Monitor", "TaskQueue", "WorkerPool"],
    )
    def test_parameter_kinds_match(
        self,
        abc_cls: type,
        module_path: str,
        class_name: str,
    ) -> None:
        """Adapter parameter kinds (POSITIONAL, KEYWORD_ONLY, etc.) match ABC."""
        adapter_cls = _import_adapter(module_path, class_name)

        abstract_methods = {
            name
            for name, _ in inspect.getmembers(abc_cls, predicate=inspect.isfunction)
            if getattr(getattr(abc_cls, name, None), "__isabstractmethod__", False)
        }

        for method_name in abstract_methods:
            abc_sig = inspect.signature(getattr(abc_cls, method_name))
            adapter_sig = inspect.signature(getattr(adapter_cls, method_name))

            for param_name in abc_sig.parameters:
                abc_kind = abc_sig.parameters[param_name].kind
                adapter_kind = adapter_sig.parameters[param_name].kind
                assert abc_kind == adapter_kind, (
                    f"{class_name}.{method_name}({param_name}): "
                    f"kind differs — ABC={abc_kind.name}, adapter={adapter_kind.name}"
                )


# ---------------------------------------------------------------------------
# Test: Polymorphism — adapters work through ABC references
# ---------------------------------------------------------------------------


def _accept_controller(ctrl: AbstractController) -> Any:
    """Helper: call controller methods through the ABC type."""
    return ctrl.load_status()


def _accept_monitor(mon: AbstractMonitor) -> list[dict[str, Any]]:
    """Helper: call monitor methods through the ABC type."""
    return mon.check_lane_health()


class TestPolymorphism:
    """Concrete adapters can be used polymorphically through ABC references."""

    def test_controller_through_abc_ref(self, tmp_path: Path) -> None:
        from bid_euchre.ops.core.controller import ControlPlaneController

        ctrl: AbstractController = ControlPlaneController(runtime_dir=tmp_path)
        result = _accept_controller(ctrl)
        assert result is None  # no file yet

    def test_monitor_through_abc_ref(self) -> None:
        from bid_euchre.ops.core.monitor import MonitorService

        mon: AbstractMonitor = MonitorService()
        with patch("bid_euchre.ops.monitor.check_lane_health") as mock_check:
            mock_check.return_value = []
            result = _accept_monitor(mon)
        assert result == []

    def test_task_queue_through_abc_ref(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq: AbstractTaskQueue = TaskQueueService()
        pkt = tq.create_packet("Poly test", "Testing polymorphism")
        assert hasattr(pkt, "packet_id")
        assert pkt.title == "Poly test"

    def test_worker_pool_through_abc_ref(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp: AbstractWorkerPool = WorkerPoolService()
        with patch("bid_euchre.ops.worker_pool.take_pool_snapshot") as mock_snap:
            mock_snap.return_value = MagicMock(workers=[], active_count=0)
            snap = wp.take_snapshot()
        assert snap is not None


# ---------------------------------------------------------------------------
# Test: Controller ↔ Monitor integration
# ---------------------------------------------------------------------------


class TestControllerMonitorIntegration:
    """Controller consumes monitor output — the core adapter contract."""

    def test_monitor_findings_feed_controller_reconcile(self, tmp_path: Path) -> None:
        """MonitorService output (list[dict]) is valid input to reconcile()."""
        from bid_euchre.ops.core.controller import ControlPlaneController
        from bid_euchre.ops.core.monitor import MonitorService
        from bid_euchre.ops.monitor import MonitorFinding

        # Monitor produces findings
        mon = MonitorService()
        with patch("bid_euchre.ops.monitor.check_lane_health") as mock_check:
            mock_check.return_value = [
                MonitorFinding(
                    category="lane_health",
                    severity="high",
                    summary="Lane degraded",
                    details={"lane_id": "author-a"},
                ),
                MonitorFinding(
                    category="lane_health",
                    severity="warn",
                    summary="Lane idle 30m",
                    details={"lane_id": "author-b"},
                ),
            ]
            findings = mon.check_lane_health()

        # Controller consumes them
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = ctrl.reconcile(monitor_findings=findings)

        # Verify integration: controller produced items from findings
        assert len(status.items) == 2
        categories = {item.category for item in status.items}
        assert "lane_health" in categories

    def test_empty_monitor_output_produces_empty_reconcile(
        self, tmp_path: Path
    ) -> None:
        """Empty monitor findings produce no controller items."""
        from bid_euchre.ops.core.controller import ControlPlaneController
        from bid_euchre.ops.core.monitor import MonitorService

        mon = MonitorService()
        with patch("bid_euchre.ops.monitor.run_monitoring_cycle") as mock_cycle:
            mock_cycle.return_value = []
            findings = mon.run_cycle()

        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = ctrl.reconcile(monitor_findings=findings)
        assert status.items == []

    def test_monitor_findings_round_trip_preserves_details(
        self, tmp_path: Path
    ) -> None:
        """Details dict survives monitor -> dict -> controller round-trip."""
        from bid_euchre.ops.core.controller import ControlPlaneController
        from bid_euchre.ops.core.monitor import MonitorService
        from bid_euchre.ops.monitor import MonitorFinding

        details = {
            "packet_id": "pkt-abc",
            "owner": "author-c",
            "elapsed_minutes": 45,
        }

        mon = MonitorService()
        with patch("bid_euchre.ops.monitor.check_stale_dispatches") as mock_check:
            mock_check.return_value = [
                MonitorFinding(
                    category="stale_dispatch",
                    severity="high",
                    summary="Stale 45m",
                    details=details,
                ),
            ]
            findings = mon.check_stale_dispatches()

        # Verify the dict layer preserved details
        assert findings[0]["details"] == details

        # Controller also consumes it
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = ctrl.reconcile(monitor_findings=findings)
        assert len(status.items) == 1
        assert status.items[0].details == details


# ---------------------------------------------------------------------------
# Test: Default construction
# ---------------------------------------------------------------------------


class TestAdapterDefaultConstruction:
    """All adapters can be constructed with zero arguments (default config)."""

    def test_controller_default(self) -> None:
        from bid_euchre.ops.core.controller import ControlPlaneController

        ctrl = ControlPlaneController()
        assert ctrl._runtime_dir is None

    def test_monitor_default(self) -> None:
        from bid_euchre.ops.core.monitor import MonitorService

        mon = MonitorService()
        assert mon._runtime_dir is None

    def test_task_queue_default(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService()
        assert tq._queue_root is None

    def test_worker_pool_default(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()
        assert wp._runtime_dir is None
        assert wp._tmux_session == "steward"


# ---------------------------------------------------------------------------
# Test: isinstance checks propagate correctly
# ---------------------------------------------------------------------------


class TestIsinstanceChecks:
    """isinstance() works correctly for all adapter / ABC pairs."""

    def test_controller_isinstance(self) -> None:
        from bid_euchre.ops.core.controller import ControlPlaneController

        ctrl = ControlPlaneController()
        assert isinstance(ctrl, AbstractController)
        assert not isinstance(ctrl, AbstractMonitor)
        assert not isinstance(ctrl, AbstractTaskQueue)
        assert not isinstance(ctrl, AbstractWorkerPool)

    def test_monitor_isinstance(self) -> None:
        from bid_euchre.ops.core.monitor import MonitorService

        mon = MonitorService()
        assert isinstance(mon, AbstractMonitor)
        assert not isinstance(mon, AbstractController)
        assert not isinstance(mon, AbstractTaskQueue)
        assert not isinstance(mon, AbstractWorkerPool)

    def test_task_queue_isinstance(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService()
        assert isinstance(tq, AbstractTaskQueue)
        assert not isinstance(tq, AbstractController)
        assert not isinstance(tq, AbstractMonitor)
        assert not isinstance(tq, AbstractWorkerPool)

    def test_worker_pool_isinstance(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()
        assert isinstance(wp, AbstractWorkerPool)
        assert not isinstance(wp, AbstractController)
        assert not isinstance(wp, AbstractMonitor)
        assert not isinstance(wp, AbstractTaskQueue)
