"""Repo-specific adapters implementing the core ops ABCs.

This package contains concrete implementations of the four core ops ABCs
(:class:`~bid_euchre.ops.core.interfaces.AbstractController`,
:class:`~bid_euchre.ops.core.interfaces.AbstractMonitor`,
:class:`~bid_euchre.ops.core.interfaces.AbstractTaskQueue`,
:class:`~bid_euchre.ops.core.interfaces.AbstractWorkerPool`)
that delegate to the existing module-level functions in
``bid_euchre.ops.{control_plane,monitor,task_queue,worker_pool}``.

Platform-10 PR3 completes the core-vs-adapter split by providing the
final two adapters (TaskQueueService, WorkerPoolService) alongside the
existing two (ControlPlaneController, MonitorService).

The ``bid_euchre`` adapter module is the project-specific wiring layer.
A second project reusing the core ABCs would provide its own adapter
module with different backing implementations.

Usage::

    from bid_euchre.ops.adapters import (
        ControlPlaneController,
        MonitorService,
        TaskQueueService,
        WorkerPoolService,
    )
"""

from bid_euchre.ops.adapters.bid_euchre import TaskQueueService, WorkerPoolService
from bid_euchre.ops.core.controller import ControlPlaneController
from bid_euchre.ops.core.monitor import MonitorService

__all__ = [
    "ControlPlaneController",
    "MonitorService",
    "TaskQueueService",
    "WorkerPoolService",
]
