"""Tests for the Bid Euchre repo-specific ops adapters.

Platform-10 PR3: verifies that TaskQueueService and WorkerPoolService
correctly implement the core ABCs and delegate to the existing module-level
functions in ``bid_euchre.ops.task_queue`` and ``bid_euchre.ops.worker_pool``.

Test categories:
1. **ABC compliance** — adapters are subclasses and can be instantiated.
2. **Delegation** — adapter methods correctly call through to module functions.
3. **Package exports** — ``adapters/__init__.py`` re-exports all four adapters.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bid_euchre.ops.core.interfaces import (
    AbstractTaskQueue,
    AbstractWorkerPool,
)

# =========================================================================
# TaskQueueService
# =========================================================================


class TestTaskQueueServiceABCCompliance:
    """TaskQueueService properly implements AbstractTaskQueue."""

    def test_is_subclass(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        assert issubclass(TaskQueueService, AbstractTaskQueue)

    def test_can_instantiate(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService()
        assert isinstance(tq, AbstractTaskQueue)

    def test_custom_queue_root(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        assert tq._queue_root == tmp_path


class TestTaskQueueServiceDelegation:
    """TaskQueueService methods delegate to task_queue module functions."""

    def test_create_packet_delegates(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService()
        pkt = tq.create_packet("Test Task", "Test description")
        # Should return a TaskPacket from the module
        assert hasattr(pkt, "packet_id")
        assert pkt.title == "Test Task"
        assert pkt.description == "Test description"
        assert pkt.status == "pending"

    def test_create_packet_with_kwargs(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService()
        pkt = tq.create_packet(
            "Test Task",
            "Description",
            owner="author-a",
            scope_declared=["src/foo.py"],
            validation=["make check"],
            priority="high",
            domain="platform",
            metadata={"key": "value"},
        )
        assert pkt.owner == "author-a"
        assert pkt.scope_declared == ["src/foo.py"]
        assert pkt.validation == ["make check"]
        assert pkt.priority == "high"
        assert pkt.domain == "platform"
        assert pkt.metadata == {"key": "value"}

    def test_save_and_load_packet(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        pkt = tq.create_packet("Save Test", "Test saving")
        tq.save_packet(pkt)

        loaded = tq.load_packet(pkt.packet_id)
        assert loaded is not None
        assert loaded.title == "Save Test"
        assert loaded.packet_id == pkt.packet_id

    def test_load_packet_not_found(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        assert tq.load_packet("nonexistent") is None

    def test_list_packets_empty(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        assert tq.list_packets() == []

    def test_list_packets_with_filter(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)

        pkt1 = tq.create_packet("Task 1", "Desc 1", owner="author-a")
        pkt2 = tq.create_packet("Task 2", "Desc 2", owner="author-b")
        tq.save_packet(pkt1)
        tq.save_packet(pkt2)

        all_packets = tq.list_packets()
        assert len(all_packets) == 2

        filtered = tq.list_packets(owner="author-a")
        assert len(filtered) == 1
        assert filtered[0].owner == "author-a"

        status_filtered = tq.list_packets(status="pending")
        assert len(status_filtered) == 2

    def test_transition_status(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        pkt = tq.create_packet("Trans Test", "Description")
        tq.save_packet(pkt)

        updated = tq.transition_status(pkt.packet_id, "approved")
        assert updated is not None
        assert updated.status == "approved"

    def test_transition_status_invalid(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        pkt = tq.create_packet("Trans Test", "Description")
        tq.save_packet(pkt)

        # pending -> dispatched is not a valid transition
        with pytest.raises(ValueError, match="Invalid transition"):
            tq.transition_status(pkt.packet_id, "dispatched")

    def test_transition_status_with_owner(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        pkt = tq.create_packet("Owner Test", "Description")
        tq.save_packet(pkt)

        updated = tq.transition_status(pkt.packet_id, "approved", owner="author-a")
        assert updated is not None
        # owner metadata should be set
        assert updated.metadata.get("dispatched_owner") == "author-a"

    def test_archive_packet(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        pkt = tq.create_packet("Archive Test", "Description")
        tq.save_packet(pkt)

        result = tq.archive_packet(pkt.packet_id)
        assert result is True

        # Should no longer be in active queue
        assert tq.load_packet(pkt.packet_id) is None

    def test_archive_packet_not_found(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        assert tq.archive_packet("nonexistent") is False

    def test_complete_packet(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)
        pkt = tq.create_packet("Complete Test", "Description")
        tq.save_packet(pkt)
        # Must transition through valid states first
        tq.transition_status(pkt.packet_id, "approved")
        tq.transition_status(pkt.packet_id, "dispatched")

        tq.complete_packet(
            pkt.packet_id,
            summary="Done",
            pr_number=42,
            completed_by="author-a",
        )
        # complete_packet archives by default, so load returns None
        assert tq.load_packet(pkt.packet_id) is None

    def test_queue_summary(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import TaskQueueService

        tq = TaskQueueService(queue_root=tmp_path)

        summary = tq.queue_summary()
        assert summary["total"] == 0

        pkt = tq.create_packet("Summary Test", "Description")
        tq.save_packet(pkt)

        summary = tq.queue_summary()
        assert summary["total"] == 1
        assert summary["by_status"]["pending"] == 1


# =========================================================================
# WorkerPoolService
# =========================================================================


class TestWorkerPoolServiceABCCompliance:
    """WorkerPoolService properly implements AbstractWorkerPool."""

    def test_is_subclass(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        assert issubclass(WorkerPoolService, AbstractWorkerPool)

    def test_can_instantiate(self) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()
        assert isinstance(wp, AbstractWorkerPool)

    def test_custom_params(self, tmp_path: Path) -> None:
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService(runtime_dir=tmp_path, tmux_session="test")
        assert wp._runtime_dir == tmp_path
        assert wp._tmux_session == "test"


class TestWorkerPoolServiceDelegation:
    """WorkerPoolService methods delegate to worker_pool module functions."""

    def test_take_snapshot_delegates(self) -> None:
        """Verify take_snapshot calls through to take_pool_snapshot."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService(tmux_session="test-session")

        with patch("bid_euchre.ops.worker_pool.take_pool_snapshot") as mock_snap:
            mock_snap.return_value = MagicMock(workers=[], active_count=0, idle_count=0)
            result = wp.take_snapshot()
            mock_snap.assert_called_once_with(
                runtime_dir=None,
                tmux_session="test-session",
            )
            assert result is mock_snap.return_value

    def test_select_worker_delegates(self) -> None:
        """Verify select_worker calls through to module function."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()
        mock_snapshot = MagicMock()

        with patch("bid_euchre.ops.worker_pool.select_worker") as mock_select:
            mock_select.return_value = "author-a"
            result = wp.select_worker(
                mock_snapshot, preferred_lane="author-a", domain="platform"
            )
            mock_select.assert_called_once_with(
                mock_snapshot,
                preferred_lane="author-a",
                domain="platform",
            )
            assert result == "author-a"

    def test_select_worker_returns_none(self) -> None:
        """Verify select_worker returns None when no capacity."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()
        mock_snapshot = MagicMock()

        with patch("bid_euchre.ops.worker_pool.select_worker") as mock_select:
            mock_select.return_value = None
            result = wp.select_worker(mock_snapshot)
            assert result is None

    def test_dispatch_to_worker_delegates(self) -> None:
        """Verify dispatch_to_worker calls through to module function."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService(tmux_session="test-session")

        with patch("bid_euchre.ops.worker_pool.dispatch_to_worker") as mock_dispatch:
            mock_dispatch.return_value = MagicMock(action="dispatch", executed=True)
            result = wp.dispatch_to_worker("pkt123", "author-a")
            mock_dispatch.assert_called_once_with(
                "pkt123",
                "author-a",
                tmux_session="test-session",
                runtime_dir=None,
            )
            assert result is mock_dispatch.return_value

    def test_wake_worker_delegates(self) -> None:
        """Verify wake_worker calls through to module function."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService(tmux_session="test-session")

        with patch("bid_euchre.ops.worker_pool.wake_worker") as mock_wake:
            mock_wake.return_value = MagicMock(action="wake", executed=True)
            result = wp.wake_worker("author-b")
            mock_wake.assert_called_once_with(
                "author-b",
                tmux_session="test-session",
                runtime_dir=None,
            )
            assert result is mock_wake.return_value

    def test_park_worker_delegates(self) -> None:
        """Verify park_worker calls through to module function."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService(tmux_session="test-session")

        with patch("bid_euchre.ops.worker_pool.park_worker") as mock_park:
            mock_park.return_value = MagicMock(action="park", executed=True)
            result = wp.park_worker("author-c")
            mock_park.assert_called_once_with(
                "author-c",
                tmux_session="test-session",
                runtime_dir=None,
            )
            assert result is mock_park.return_value

    def test_nudge_pane_delegates(self) -> None:
        """Verify nudge_pane calls through to module function."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService(tmux_session="test-session")

        with patch("bid_euchre.ops.worker_pool.nudge_pane") as mock_nudge:
            mock_nudge.return_value = MagicMock(executed=True)
            result = wp.nudge_pane("author-a", "/start-task abc123")
            mock_nudge.assert_called_once_with(
                "author-a",
                "abc123",
                tmux_session="test-session",
                runtime_dir=None,
            )
            assert result is True

    def test_nudge_pane_returns_false_on_failure(self) -> None:
        """Verify nudge_pane returns False when execution fails."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()

        with patch("bid_euchre.ops.worker_pool.nudge_pane") as mock_nudge:
            mock_nudge.return_value = MagicMock(executed=False)
            result = wp.nudge_pane("author-a", "/start-task xyz")
            assert result is False

    def test_nudge_pane_raw_text(self) -> None:
        """Verify nudge_pane handles non-start-task text."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService

        wp = WorkerPoolService()

        with patch("bid_euchre.ops.worker_pool.nudge_pane") as mock_nudge:
            mock_nudge.return_value = MagicMock(executed=True)
            wp.nudge_pane("author-a", "some-raw-text")
            mock_nudge.assert_called_once_with(
                "author-a",
                "some-raw-text",
                tmux_session="steward",
                runtime_dir=None,
            )

    def test_action_to_dict_helper(self) -> None:
        """Verify the static _action_to_dict helper works."""
        from bid_euchre.ops.adapters.bid_euchre import WorkerPoolService
        from bid_euchre.ops.worker_pool import PoolAction

        action = PoolAction(
            action="test",
            lane_id="author-a",
            reason="testing",
            executed=True,
        )
        result = WorkerPoolService._action_to_dict(action)
        assert isinstance(result, dict)
        assert result["action"] == "test"
        assert result["lane_id"] == "author-a"
        assert result["executed"] is True


# =========================================================================
# Package exports
# =========================================================================


class TestAdapterPackageExports:
    """Verify adapters/__init__.py re-exports all four adapter classes."""

    def test_all_four_adapters_exported(self) -> None:
        import bid_euchre.ops.adapters as adapters

        expected = {
            "ControlPlaneController",
            "MonitorService",
            "TaskQueueService",
            "WorkerPoolService",
        }
        assert expected == set(adapters.__all__)

    def test_controller_from_adapters(self) -> None:
        from bid_euchre.ops.adapters import ControlPlaneController
        from bid_euchre.ops.core.controller import (
            ControlPlaneController as Direct,
        )

        assert ControlPlaneController is Direct

    def test_monitor_from_adapters(self) -> None:
        from bid_euchre.ops.adapters import MonitorService
        from bid_euchre.ops.core.monitor import MonitorService as Direct

        assert MonitorService is Direct

    def test_task_queue_from_adapters(self) -> None:
        from bid_euchre.ops.adapters import TaskQueueService
        from bid_euchre.ops.adapters.bid_euchre import (
            TaskQueueService as Direct,
        )

        assert TaskQueueService is Direct

    def test_worker_pool_from_adapters(self) -> None:
        from bid_euchre.ops.adapters import WorkerPoolService
        from bid_euchre.ops.adapters.bid_euchre import (
            WorkerPoolService as Direct,
        )

        assert WorkerPoolService is Direct


# =========================================================================
# Cross-cutting: isinstance checks across the full adapter set
# =========================================================================


class TestAllAdaptersImplementABCs:
    """All four adapters are instances of their respective ABCs."""

    def test_all_four_are_abc_subclasses(self) -> None:
        from bid_euchre.ops.adapters import (
            ControlPlaneController,
            MonitorService,
            TaskQueueService,
            WorkerPoolService,
        )
        from bid_euchre.ops.core import (
            AbstractController,
            AbstractMonitor,
            AbstractTaskQueue,
            AbstractWorkerPool,
        )

        assert issubclass(ControlPlaneController, AbstractController)
        assert issubclass(MonitorService, AbstractMonitor)
        assert issubclass(TaskQueueService, AbstractTaskQueue)
        assert issubclass(WorkerPoolService, AbstractWorkerPool)

    def test_all_four_can_instantiate(self) -> None:
        from bid_euchre.ops.adapters import (
            ControlPlaneController,
            MonitorService,
            TaskQueueService,
            WorkerPoolService,
        )

        # All should instantiate without error
        ctrl = ControlPlaneController()
        mon = MonitorService()
        tq = TaskQueueService()
        wp = WorkerPoolService()

        assert ctrl is not None
        assert mon is not None
        assert tq is not None
        assert wp is not None
