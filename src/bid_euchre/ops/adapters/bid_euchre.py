"""Bid Euchre repo-specific adapters for AbstractTaskQueue and AbstractWorkerPool.

Completes the Platform-10 core-vs-adapter split by providing concrete
implementations of the remaining two ABCs that delegate to the existing
module-level functions in ``bid_euchre.ops.task_queue`` and
``bid_euchre.ops.worker_pool``.

These adapters follow the same pattern established by
:class:`~bid_euchre.ops.core.controller.ControlPlaneController` and
:class:`~bid_euchre.ops.core.monitor.MonitorService` (Platform-10 PR2):

- Encapsulate a ``runtime_dir`` parameter
- Use deferred imports to avoid circular dependencies
- Delegate to the existing module-level functions
- Convert repo-specific dataclasses to plain dicts at the ABC boundary

Usage::

    from bid_euchre.ops.adapters.bid_euchre import TaskQueueService, WorkerPoolService

    tq = TaskQueueService()
    pkt = tq.create_packet("Fix bug", "Description of fix")
    tq.save_packet(pkt)

    wp = WorkerPoolService()
    snap = wp.take_snapshot()
    lane = wp.select_worker(snap, domain="platform")
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from bid_euchre.ops.core.interfaces import AbstractTaskQueue, AbstractWorkerPool


class TaskQueueService(AbstractTaskQueue):
    """Concrete task queue backed by the task_queue module.

    Encapsulates a ``queue_root`` and delegates to the existing
    module-level functions in ``bid_euchre.ops.task_queue``.

    Args:
        queue_root: Path to the task queue directory (defaults to
            ``.claude/runtime/task_queue``).
    """

    def __init__(self, queue_root: Path | None = None) -> None:
        self._queue_root = queue_root

    # -- AbstractTaskQueue interface -----------------------------------------

    def create_packet(
        self,
        title: str,
        description: str,
        *,
        owner: str | None = None,
        scope_declared: list[str] | None = None,
        validation: list[str] | None = None,
        priority: str = "normal",
        domain: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """Create a new task packet.

        Delegates to :func:`bid_euchre.ops.task_queue.create_packet`.
        """
        from bid_euchre.ops.task_queue import create_packet

        return create_packet(
            title=title,
            description=description,
            owner=owner,
            scope_declared=scope_declared,
            validation=validation,
            priority=priority,
            domain=domain,
            metadata=metadata,
        )

    def save_packet(self, packet: Any) -> Any:
        """Persist a task packet to durable storage.

        Delegates to :func:`bid_euchre.ops.task_queue.save_packet`.
        """
        from bid_euchre.ops.task_queue import save_packet

        return save_packet(packet, self._queue_root)

    def load_packet(self, packet_id: str) -> Any | None:
        """Load a task packet by ID.

        Delegates to :func:`bid_euchre.ops.task_queue.load_packet`.
        """
        from bid_euchre.ops.task_queue import load_packet

        return load_packet(packet_id, self._queue_root)

    def list_packets(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
    ) -> list[Any]:
        """List task packets with optional filtering.

        Delegates to :func:`bid_euchre.ops.task_queue.list_packets`.
        """
        from bid_euchre.ops.task_queue import list_packets

        return list_packets(
            self._queue_root,
            status_filter=status,
            owner_filter=owner,
        )

    def transition_status(
        self,
        packet_id: str,
        new_status: str,
        *,
        owner: str | None = None,
    ) -> Any:
        """Transition a packet to a new status.

        Delegates to :func:`bid_euchre.ops.task_queue.transition_status`.
        If *owner* is provided, updates the packet's metadata with
        the owner assignment after the status transition.
        """
        from bid_euchre.ops.task_queue import transition_status, update_packet_metadata

        pkt = transition_status(packet_id, new_status, self._queue_root)
        if pkt is not None and owner is not None:
            pkt = update_packet_metadata(
                packet_id,
                {"dispatched_owner": owner},
                self._queue_root,
            )
        return pkt

    def archive_packet(self, packet_id: str) -> bool:
        """Archive a completed/rejected packet.

        Delegates to :func:`bid_euchre.ops.task_queue.archive_packet`.
        """
        from bid_euchre.ops.task_queue import archive_packet

        return archive_packet(packet_id, self._queue_root)

    def complete_packet(
        self,
        packet_id: str,
        *,
        summary: str = "",
        pr_number: int | None = None,
        completed_by: str = "",
    ) -> Any:
        """Complete a packet with a result record.

        Delegates to :func:`bid_euchre.ops.task_queue.complete_packet`
        by constructing a :class:`~bid_euchre.ops.task_queue.TaskResult`
        and passing it to the module-level function.
        """
        from bid_euchre.ops.task_queue import complete_packet, create_result

        result = create_result(
            packet_id=packet_id,
            status="completed",
            summary=summary,
            pr_number=pr_number,
            completed_by=completed_by,
        )
        return complete_packet(result, self._queue_root)

    def queue_summary(self) -> dict[str, Any]:
        """Get a summary of queue state.

        Delegates to :func:`bid_euchre.ops.task_queue.queue_summary`.
        """
        from bid_euchre.ops.task_queue import queue_summary

        return queue_summary(self._queue_root)


class WorkerPoolService(AbstractWorkerPool):
    """Concrete worker pool backed by the worker_pool module.

    Encapsulates ``runtime_dir`` and ``tmux_session`` and delegates
    to the existing module-level functions in
    ``bid_euchre.ops.worker_pool``.

    Args:
        runtime_dir: Path to the runtime directory (defaults to
            ``.claude/runtime``).
        tmux_session: tmux session name (defaults to ``"steward"``).
    """

    def __init__(
        self,
        runtime_dir: Path | None = None,
        tmux_session: str = "steward",
    ) -> None:
        self._runtime_dir = runtime_dir
        self._tmux_session = tmux_session

    @staticmethod
    def _action_to_dict(action: Any) -> dict[str, Any]:
        """Convert a PoolAction dataclass to a plain dict.

        The ABC contract returns adapter-defined types; we preserve
        the PoolAction as-is since it is already a concrete type that
        callers can use directly.  This method is available for cases
        where dict serialization is needed.
        """
        return asdict(action)

    # -- AbstractWorkerPool interface ----------------------------------------

    def take_snapshot(self) -> Any:
        """Build a point-in-time worker pool snapshot.

        Delegates to :func:`bid_euchre.ops.worker_pool.take_pool_snapshot`.
        """
        from bid_euchre.ops.worker_pool import take_pool_snapshot

        return take_pool_snapshot(
            runtime_dir=self._runtime_dir,
            tmux_session=self._tmux_session,
        )

    def select_worker(
        self,
        snapshot: Any,
        *,
        preferred_lane: str | None = None,
        domain: str | None = None,
    ) -> str | None:
        """Choose the best lane for new work.

        Delegates to :func:`bid_euchre.ops.worker_pool.select_worker`.
        """
        from bid_euchre.ops.worker_pool import select_worker

        return select_worker(
            snapshot,
            preferred_lane=preferred_lane,
            domain=domain,
        )

    def dispatch_to_worker(
        self,
        packet_id: str,
        lane_id: str,
    ) -> Any:
        """Dispatch a task packet to a worker lane.

        Delegates to :func:`bid_euchre.ops.worker_pool.dispatch_to_worker`.
        """
        from bid_euchre.ops.worker_pool import dispatch_to_worker

        return dispatch_to_worker(
            packet_id,
            lane_id,
            tmux_session=self._tmux_session,
            runtime_dir=self._runtime_dir,
        )

    def wake_worker(self, lane_id: str) -> Any:
        """Wake a parked or retired worker lane.

        Delegates to :func:`bid_euchre.ops.worker_pool.wake_worker`.
        """
        from bid_euchre.ops.worker_pool import wake_worker

        return wake_worker(
            lane_id,
            tmux_session=self._tmux_session,
            runtime_dir=self._runtime_dir,
        )

    def park_worker(self, lane_id: str) -> Any:
        """Park an idle worker lane.

        Delegates to :func:`bid_euchre.ops.worker_pool.park_worker`.
        """
        from bid_euchre.ops.worker_pool import park_worker

        return park_worker(
            lane_id,
            tmux_session=self._tmux_session,
            runtime_dir=self._runtime_dir,
        )

    def nudge_pane(self, lane_id: str, text: str) -> bool:
        """Send a text nudge to a lane's tmux pane.

        Delegates to :func:`bid_euchre.ops.worker_pool.nudge_pane`.
        The module-level function uses a ``packet_id`` parameter rather
        than raw text; this adapter extracts the packet_id from the text
        if it follows the ``/start-task <id>`` pattern, otherwise passes
        the text as-is.

        Note: The underlying module function returns a PoolAction, but
        the ABC contract returns a bool.  We convert accordingly.
        """
        from bid_euchre.ops.worker_pool import nudge_pane as _nudge

        # Extract packet_id from "/start-task <id>" if present
        packet_id = text
        if text.startswith("/start-task "):
            packet_id = text.split(maxsplit=1)[1] if " " in text else text

        action = _nudge(
            lane_id,
            packet_id,
            tmux_session=self._tmux_session,
            runtime_dir=self._runtime_dir,
        )
        return action.executed
