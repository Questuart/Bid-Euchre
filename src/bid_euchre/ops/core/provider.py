"""Service provider for the core ops platform.

Constructs and holds all four adapter instances as a cohesive unit, providing
a single entry point for the orchestration loop to access the full adapter
surface.

This is the wiring layer that connects the abstract interfaces
(:mod:`bid_euchre.ops.core.interfaces`) to the concrete implementations.
Callers program against the provider rather than constructing individual
adapters manually.

Design principles:

1. **Single construction point** -- all adapters share compatible
   configuration (runtime_dir, tmux_session) and are constructed together.
2. **Lazy construction** -- adapter instances are created on first access,
   not at import time, to avoid import-time side effects.
3. **Swappable** -- the provider accepts pre-built adapter instances for
   testing, allowing in-memory stubs to replace the filesystem-backed
   adapters.

Usage::

    from bid_euchre.ops.core.provider import ServiceProvider

    # Default: uses Bid-Euchre-specific adapters
    provider = ServiceProvider.default()
    status = provider.controller.reconcile(monitor_findings=findings)
    snap = provider.worker_pool.take_snapshot()

    # Custom: inject test stubs
    provider = ServiceProvider(
        controller=mock_controller,
        monitor=mock_monitor,
        task_queue=mock_task_queue,
        worker_pool=mock_worker_pool,
    )
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


class ServiceProvider:
    """Holds the four core ops adapter instances.

    Provides typed access to each adapter via properties, and a
    ``default()`` class method that constructs the Bid-Euchre-specific
    adapter set.

    Args:
        controller: The controller adapter instance.
        monitor: The monitor adapter instance.
        task_queue: The task queue adapter instance.
        worker_pool: The worker pool adapter instance.
    """

    def __init__(
        self,
        *,
        controller: AbstractController,
        monitor: AbstractMonitor,
        task_queue: AbstractTaskQueue,
        worker_pool: AbstractWorkerPool,
    ) -> None:
        self._controller = controller
        self._monitor = monitor
        self._task_queue = task_queue
        self._worker_pool = worker_pool

    @property
    def controller(self) -> AbstractController:
        """The fleet status controller."""
        return self._controller

    @property
    def monitor(self) -> AbstractMonitor:
        """The monitoring service."""
        return self._monitor

    @property
    def task_queue(self) -> AbstractTaskQueue:
        """The task packet queue."""
        return self._task_queue

    @property
    def worker_pool(self) -> AbstractWorkerPool:
        """The worker pool manager."""
        return self._worker_pool

    @classmethod
    def default(
        cls,
        *,
        runtime_dir: Path | None = None,
        queue_root: Path | None = None,
        tmux_session: str = "steward",
    ) -> ServiceProvider:
        """Construct the default Bid-Euchre adapter set.

        Uses deferred imports to avoid circular dependencies and
        import-time side effects.

        Args:
            runtime_dir: Path to the runtime directory.  Passed to the
                controller, monitor, and worker pool adapters.
            queue_root: Path to the task queue directory.  If ``None``,
                the task queue adapter uses its own default.
            tmux_session: tmux session name for the worker pool adapter.

        Returns:
            A fully-wired ``ServiceProvider`` with Bid-Euchre adapters.
        """
        from bid_euchre.ops.adapters.bid_euchre import (
            TaskQueueService,
            WorkerPoolService,
        )
        from bid_euchre.ops.core.controller import ControlPlaneController
        from bid_euchre.ops.core.monitor import MonitorService

        return cls(
            controller=ControlPlaneController(runtime_dir=runtime_dir),
            monitor=MonitorService(runtime_dir=runtime_dir),
            task_queue=TaskQueueService(queue_root=queue_root),
            worker_pool=WorkerPoolService(
                runtime_dir=runtime_dir,
                tmux_session=tmux_session,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a diagnostic dict of adapter types.

        Useful for status displays and debugging to verify which
        concrete adapters are wired in.

        Returns:
            Dict mapping role names to adapter class names.
        """
        return {
            "controller": type(self._controller).__qualname__,
            "monitor": type(self._monitor).__qualname__,
            "task_queue": type(self._task_queue).__qualname__,
            "worker_pool": type(self._worker_pool).__qualname__,
        }

    def __repr__(self) -> str:
        return (
            f"ServiceProvider("
            f"controller={type(self._controller).__name__}, "
            f"monitor={type(self._monitor).__name__}, "
            f"task_queue={type(self._task_queue).__name__}, "
            f"worker_pool={type(self._worker_pool).__name__})"
        )
