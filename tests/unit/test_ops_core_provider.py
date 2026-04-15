"""Tests for the ServiceProvider core adapter wiring.

Platform-10 PR5: verifies that the ServiceProvider correctly constructs,
holds, and exposes all four core ops adapters as a cohesive unit.

Test categories:
1. **Construction** — default factory builds all four adapters.
2. **ABC compliance** — all adapters satisfy their abstract contracts.
3. **Custom injection** — provider accepts pre-built stubs for testing.
4. **Diagnostics** — to_dict and repr expose adapter types.
5. **Package exports** — provider is importable from expected locations.
6. **Convenience factory** — adapters.create_provider() shortcut works.
7. **Hook import resolution** — hook callers can resolve imports through
   the provider/adapter layer (SP-5-01 PR4 regression guard).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bid_euchre.ops.core.interfaces import (
    AbstractController,
    AbstractMonitor,
    AbstractTaskQueue,
    AbstractWorkerPool,
)
from bid_euchre.ops.core.provider import ServiceProvider

# =========================================================================
# Construction via default()
# =========================================================================


class TestServiceProviderDefault:
    """ServiceProvider.default() constructs all four adapters."""

    def test_default_creates_provider(self) -> None:
        provider = ServiceProvider.default()
        assert isinstance(provider, ServiceProvider)

    def test_default_controller_is_abstract_controller(self) -> None:
        provider = ServiceProvider.default()
        assert isinstance(provider.controller, AbstractController)

    def test_default_monitor_is_abstract_monitor(self) -> None:
        provider = ServiceProvider.default()
        assert isinstance(provider.monitor, AbstractMonitor)

    def test_default_task_queue_is_abstract_task_queue(self) -> None:
        provider = ServiceProvider.default()
        assert isinstance(provider.task_queue, AbstractTaskQueue)

    def test_default_worker_pool_is_abstract_worker_pool(self) -> None:
        provider = ServiceProvider.default()
        assert isinstance(provider.worker_pool, AbstractWorkerPool)

    def test_default_uses_concrete_controller(self) -> None:
        from bid_euchre.ops.core.controller import ControlPlaneController

        provider = ServiceProvider.default()
        assert isinstance(provider.controller, ControlPlaneController)

    def test_default_uses_concrete_monitor(self) -> None:
        from bid_euchre.ops.core.monitor import MonitorService

        provider = ServiceProvider.default()
        assert isinstance(provider.monitor, MonitorService)

    def test_default_uses_concrete_task_queue(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        provider = ServiceProvider.default()
        assert isinstance(provider.task_queue, TaskQueueService)

    def test_default_uses_concrete_worker_pool(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        provider = ServiceProvider.default()
        assert isinstance(provider.worker_pool, WorkerPoolService)


# =========================================================================
# Configuration passthrough
# =========================================================================


class TestServiceProviderConfiguration:
    """Configuration parameters are passed to adapters correctly."""

    def test_custom_runtime_dir(self, tmp_path: Path) -> None:
        provider = ServiceProvider.default(runtime_dir=tmp_path)
        # Controller and monitor receive runtime_dir
        assert provider.controller._runtime_dir == tmp_path
        assert provider.monitor._runtime_dir == tmp_path
        # Worker pool receives runtime_dir
        assert provider.worker_pool._runtime_dir == tmp_path

    def test_custom_queue_root(self, tmp_path: Path) -> None:
        provider = ServiceProvider.default(queue_root=tmp_path)
        assert provider.task_queue._queue_root == tmp_path

    def test_custom_tmux_session(self) -> None:
        provider = ServiceProvider.default(tmux_session="test-session")
        assert provider.worker_pool._tmux_session == "test-session"

    def test_default_tmux_session(self) -> None:
        provider = ServiceProvider.default()
        assert provider.worker_pool._tmux_session == "steward"


# =========================================================================
# Custom injection (stub support)
# =========================================================================


class _StubController(AbstractController):
    """Minimal stub for testing injection."""

    def reconcile(self, **kwargs: Any) -> Any:
        return {"stub": True}

    def load_status(self) -> Any:
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
    """Minimal stub for testing injection."""

    def run_cycle(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []

    def check_lane_health(self) -> list[dict[str, Any]]:
        return []

    def check_stale_dispatches(self) -> list[dict[str, Any]]:
        return []

    def check_idle_lanes(self) -> list[dict[str, Any]]:
        return []


class _StubTaskQueue(AbstractTaskQueue):
    """Minimal stub for testing injection."""

    def create_packet(self, title: str, description: str, **kw: Any) -> Any:
        return {"title": title}

    def save_packet(self, packet: Any) -> Any:
        return "/tmp/stub"

    def load_packet(self, packet_id: str) -> Any:
        return None

    def list_packets(self, **kw: Any) -> list[Any]:
        return []

    def transition_status(self, packet_id: str, new_status: str, **kw: Any) -> Any:
        return None

    def archive_packet(self, packet_id: str) -> bool:
        return True

    def complete_packet(self, packet_id: str, **kw: Any) -> Any:
        return None

    def queue_summary(self) -> dict[str, Any]:
        return {"total": 0}


class _StubWorkerPool(AbstractWorkerPool):
    """Minimal stub for testing injection."""

    def take_snapshot(self) -> Any:
        return {}

    def select_worker(self, snapshot: Any, **kw: Any) -> str | None:
        return None

    def dispatch_to_worker(self, packet_id: str, lane_id: str) -> Any:
        return None

    def wake_worker(self, lane_id: str) -> Any:
        return None

    def park_worker(self, lane_id: str) -> Any:
        return None

    def nudge_pane(self, lane_id: str, text: str) -> bool:
        return True


class TestServiceProviderInjection:
    """ServiceProvider accepts injected adapter instances."""

    def _make_provider(self) -> ServiceProvider:
        return ServiceProvider(
            controller=_StubController(),
            monitor=_StubMonitor(),
            task_queue=_StubTaskQueue(),
            worker_pool=_StubWorkerPool(),
        )

    def test_injected_controller(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider.controller, _StubController)

    def test_injected_monitor(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider.monitor, _StubMonitor)

    def test_injected_task_queue(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider.task_queue, _StubTaskQueue)

    def test_injected_worker_pool(self) -> None:
        provider = self._make_provider()
        assert isinstance(provider.worker_pool, _StubWorkerPool)

    def test_injected_stubs_are_callable(self) -> None:
        """Verify injected stubs work through the ABC interface."""
        provider = self._make_provider()
        # Controller
        result = provider.controller.reconcile()
        assert result == {"stub": True}
        # Monitor
        findings = provider.monitor.run_cycle()
        assert findings == []
        # Task queue
        pkt = provider.task_queue.create_packet("T", "D")
        assert pkt == {"title": "T"}
        # Worker pool
        snap = provider.worker_pool.take_snapshot()
        assert snap == {}


# =========================================================================
# Diagnostics
# =========================================================================


class TestServiceProviderDiagnostics:
    """to_dict() and __repr__() expose adapter types."""

    def test_to_dict_default(self) -> None:
        provider = ServiceProvider.default()
        d = provider.to_dict()
        assert d["controller"] == "ControlPlaneController"
        assert d["monitor"] == "MonitorService"
        assert d["task_queue"] == "TaskQueueService"
        assert d["worker_pool"] == "WorkerPoolService"

    def test_to_dict_stubs(self) -> None:
        provider = ServiceProvider(
            controller=_StubController(),
            monitor=_StubMonitor(),
            task_queue=_StubTaskQueue(),
            worker_pool=_StubWorkerPool(),
        )
        d = provider.to_dict()
        assert "_StubController" in d["controller"]
        assert "_StubMonitor" in d["monitor"]
        assert "_StubTaskQueue" in d["task_queue"]
        assert "_StubWorkerPool" in d["worker_pool"]

    def test_repr_includes_class_names(self) -> None:
        provider = ServiceProvider.default()
        r = repr(provider)
        assert "ServiceProvider(" in r
        assert "ControlPlaneController" in r
        assert "MonitorService" in r
        assert "TaskQueueService" in r
        assert "WorkerPoolService" in r

    def test_to_dict_keys(self) -> None:
        provider = ServiceProvider.default()
        d = provider.to_dict()
        assert set(d.keys()) == {"controller", "monitor", "task_queue", "worker_pool"}


# =========================================================================
# Package exports
# =========================================================================


class TestPackageExports:
    """ServiceProvider is importable from expected locations."""

    def test_import_from_core(self) -> None:
        from bid_euchre.ops.core import ServiceProvider as SP

        assert SP is ServiceProvider

    def test_import_from_core_provider(self) -> None:
        from bid_euchre.ops.core.provider import ServiceProvider as SP

        assert SP is ServiceProvider

    def test_core_all_includes_provider(self) -> None:
        import bid_euchre.ops.core as core

        assert "ServiceProvider" in core.__all__

    def test_adapters_exports_create_provider(self) -> None:
        import bid_euchre.ops.adapters as adapters

        assert "create_provider" in adapters.__all__
        assert hasattr(adapters, "create_provider")


# =========================================================================
# Convenience factory
# =========================================================================


class TestCreateProviderFactory:
    """adapters.create_provider() convenience factory."""

    def test_create_provider_returns_service_provider(self) -> None:
        from bid_euchre.ops.adapters import create_provider

        provider = create_provider()
        assert isinstance(provider, ServiceProvider)

    def test_create_provider_passes_runtime_dir(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters import create_provider

        provider = create_provider(runtime_dir=tmp_path)
        assert provider.controller._runtime_dir == tmp_path

    def test_create_provider_passes_queue_root(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters import create_provider

        provider = create_provider(queue_root=tmp_path)
        assert provider.task_queue._queue_root == tmp_path

    def test_create_provider_passes_tmux_session(self) -> None:
        from bid_euchre.ops.adapters import create_provider

        provider = create_provider(tmux_session="custom")
        assert provider.worker_pool._tmux_session == "custom"


# =========================================================================
# Hook import resolution (SP-5-01 PR4 regression guard)
# =========================================================================


class TestHookImportResolution:
    """Verify that all hook-level imports resolve through provider or direct paths.

    Hook files (.claude/hooks/) use inline Python with deferred imports.
    These tests ensure the import paths remain valid after the SP-5-01 PR4
    migration.  They test import resolution only — functional correctness
    of hooks requires a live steward session.
    """

    def test_post_merge_notify_provider_import(self) -> None:
        """post-merge-notify.sh: ServiceProvider is importable and constructs."""
        from bid_euchre.ops.core.provider import ServiceProvider

        provider = ServiceProvider.default()
        # The hook uses provider.task_queue.list_packets and .transition_status
        assert hasattr(provider.task_queue, "list_packets")
        assert hasattr(provider.task_queue, "transition_status")

    def test_post_merge_notify_list_packets_via_provider(self) -> None:
        """post-merge-notify.sh: list_packets through provider returns a list."""
        from bid_euchre.ops.core.provider import ServiceProvider

        provider = ServiceProvider.default()
        # Should not raise; returns a list (may be empty in test env)
        result = provider.task_queue.list_packets(status="dispatched")
        assert isinstance(result, list)

    def test_post_merge_notify_worker_pool_import(self) -> None:
        """post-merge-notify.sh: cleanup_lane_processes is importable directly.

        This function is a module-level utility without an ABC counterpart.
        It remains a direct import until Platform-13.
        """
        from bid_euchre.ops.worker_pool import cleanup_lane_processes

        assert callable(cleanup_lane_processes)

    def test_post_merge_notify_message_bus_import(self) -> None:
        """post-merge-notify.sh: message_bus functions are importable directly.

        message_bus has no ABC — these remain direct imports.
        """
        from bid_euchre.ops.message_bus import create_message, send_message

        assert callable(create_message)
        assert callable(send_message)

    def test_inbound_channel_audit_monitor_import(self) -> None:
        """inbound-channel-audit.py: process_inbound_ack is importable.

        This is a module-level utility without an ABC counterpart on
        AbstractMonitor.  Remains a direct import until Platform-13.
        """
        from bid_euchre.ops.monitor import process_inbound_ack

        assert callable(process_inbound_ack)

    def test_inbound_channel_audit_audit_trail_import(self) -> None:
        """inbound-channel-audit.py: audit_channel_tag is importable.

        audit_trail has no ABC — remains a direct import.
        """
        from bid_euchre.ops.audit_trail import audit_channel_tag

        assert callable(audit_channel_tag)

    def test_park_skill_worker_pool_import(self) -> None:
        """park/SKILL.md: cleanup_lane_processes is importable via worker_pool.

        The SKILL.md code example uses this function directly.
        """
        from bid_euchre.ops.worker_pool import cleanup_lane_processes

        assert callable(cleanup_lane_processes)
