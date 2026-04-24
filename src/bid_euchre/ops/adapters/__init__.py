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
        create_provider,
    )

    # Convenience factory: constructs a fully-wired ServiceProvider
    provider = create_provider()
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from bid_euchre.ops.adapters.bid_euchre import (
    BidEuchreLaneConfig,
    TaskQueueService,
    WorkerPoolService,
    get_lane_config,
)
from bid_euchre.ops.adapters.token_economy_adapter import (
    NATIVE_USAGE_FLAG,
    infer_lane_from_path,
    native_usage_enabled,
    read_session_records,
)
from bid_euchre.ops.core.controller import ControlPlaneController
from bid_euchre.ops.core.monitor import MonitorService

if TYPE_CHECKING:
    from bid_euchre.ops.core.provider import ServiceProvider


def create_provider(
    *,
    runtime_dir: Path | None = None,
    queue_root: Path | None = None,
    tmux_session: str = "steward",
) -> ServiceProvider:
    """Convenience factory: construct a fully-wired ServiceProvider.

    Equivalent to ``ServiceProvider.default()`` but importable from the
    adapters package for callers that don't need the core ABCs.

    Args:
        runtime_dir: Path to the runtime directory.
        queue_root: Path to the task queue directory.
        tmux_session: tmux session name for the worker pool adapter.

    Returns:
        A :class:`~bid_euchre.ops.core.provider.ServiceProvider` wired
        with Bid-Euchre adapters.
    """
    from bid_euchre.ops.core.provider import ServiceProvider

    return ServiceProvider.default(
        runtime_dir=runtime_dir,
        queue_root=queue_root,
        tmux_session=tmux_session,
    )


__all__ = [
    "NATIVE_USAGE_FLAG",
    "BidEuchreLaneConfig",
    "ControlPlaneController",
    "MonitorService",
    "TaskQueueService",
    "WorkerPoolService",
    "create_provider",
    "get_lane_config",
    "infer_lane_from_path",
    "native_usage_enabled",
    "read_session_records",
]
