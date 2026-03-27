"""Tests for ControlPlaneController — the concrete AbstractController impl.

Platform-10 PR2: verifies that ControlPlaneController correctly implements
the AbstractController interface and delegates to control_plane module
functions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.control_plane import (
    ActionableItem,
    FleetStatus,
    save_fleet_status,
)
from bid_euchre.ops.core import AbstractController
from bid_euchre.ops.core.controller import ControlPlaneController


class TestControlPlaneControllerIsAbstractController:
    """Verify ControlPlaneController properly implements the ABC."""

    def test_is_subclass(self) -> None:
        assert issubclass(ControlPlaneController, AbstractController)

    def test_can_instantiate(self) -> None:
        ctrl = ControlPlaneController()
        assert isinstance(ctrl, AbstractController)

    def test_custom_runtime_dir(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        assert ctrl._runtime_dir == tmp_path


class TestReconcile:
    """Verify reconcile() delegates correctly."""

    def test_reconcile_empty(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = ctrl.reconcile()
        assert isinstance(status, FleetStatus)
        assert status.cycle_count == 1
        assert status.items == []

    def test_reconcile_with_monitor_findings(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        findings = [
            {
                "category": "stale_dispatch",
                "severity": "high",
                "summary": "Stale packet test",
                "details": {"packet_id": "pkt1", "owner": "author-a"},
            }
        ]
        status = ctrl.reconcile(monitor_findings=findings)
        assert isinstance(status, FleetStatus)
        assert len(status.items) == 1
        assert status.items[0].category == "stale_dispatch"

    def test_reconcile_persists(self, tmp_path: Path) -> None:
        """Reconcile should persist status to disk."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        ctrl.reconcile()
        # Should be loadable
        loaded = ctrl.load_status()
        assert loaded is not None
        assert isinstance(loaded, FleetStatus)

    def test_reconcile_increments_cycle(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        s1 = ctrl.reconcile()
        s2 = ctrl.reconcile()
        assert s2.cycle_count == s1.cycle_count + 1


class TestLoadSaveStatus:
    """Verify load/save delegation."""

    def test_load_no_file(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        assert ctrl.load_status() is None

    def test_save_and_load(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = FleetStatus(items=[], generated_at="2026-01-01T00:00:00Z")
        ctrl.save_status(status)
        loaded = ctrl.load_status()
        assert loaded is not None
        assert loaded.generated_at == "2026-01-01T00:00:00Z"


class TestAckClearSuppress:
    """Verify ack/clear/suppress item lifecycle."""

    @pytest.fixture()
    def ctrl_with_items(self, tmp_path: Path) -> ControlPlaneController:
        """Create a controller with pre-populated fleet status."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = FleetStatus(
            items=[
                ActionableItem(
                    item_id="item-001",
                    severity="high",
                    category="stale_dispatch",
                    source="monitor",
                    summary="Test item",
                    first_seen_at="2026-01-01T00:00:00Z",
                    last_seen_at="2026-01-01T00:00:00Z",
                    state="open",
                ),
                ActionableItem(
                    item_id="item-002",
                    severity="warn",
                    category="pr_status",
                    source="monitor",
                    summary="Another item",
                    first_seen_at="2026-01-01T00:00:00Z",
                    last_seen_at="2026-01-01T00:00:00Z",
                    state="open",
                ),
            ],
            generated_at="2026-01-01T00:00:00Z",
            cycle_count=1,
        )
        save_fleet_status(status, tmp_path)
        return ctrl

    def test_ack_item_found(self, ctrl_with_items: ControlPlaneController) -> None:
        assert ctrl_with_items.ack_item("item-001") is True
        # Verify persisted
        status = ctrl_with_items.load_status()
        assert status is not None
        item = next(i for i in status.items if i.item_id == "item-001")
        assert item.state == "acked"

    def test_ack_item_not_found(self, ctrl_with_items: ControlPlaneController) -> None:
        assert ctrl_with_items.ack_item("nonexistent") is False

    def test_ack_no_status(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        assert ctrl.ack_item("item-001") is False

    def test_clear_item_found(self, ctrl_with_items: ControlPlaneController) -> None:
        assert ctrl_with_items.clear_item("item-001") is True
        status = ctrl_with_items.load_status()
        assert status is not None
        item = next(i for i in status.items if i.item_id == "item-001")
        assert item.state == "cleared"

    def test_clear_item_not_found(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        assert ctrl_with_items.clear_item("nonexistent") is False

    def test_clear_no_status(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        assert ctrl.clear_item("item-001") is False

    def test_suppress_item_found(self, ctrl_with_items: ControlPlaneController) -> None:
        assert ctrl_with_items.suppress_item("item-002") is True
        status = ctrl_with_items.load_status()
        assert status is not None
        item = next(i for i in status.items if i.item_id == "item-002")
        assert item.state == "suppressed"

    def test_suppress_item_not_found(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        assert ctrl_with_items.suppress_item("nonexistent") is False

    def test_suppress_no_status(self, tmp_path: Path) -> None:
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        assert ctrl.suppress_item("item-001") is False

    def test_ack_then_clear(self, ctrl_with_items: ControlPlaneController) -> None:
        """Acked items can still be cleared."""
        ctrl_with_items.ack_item("item-001")
        assert ctrl_with_items.clear_item("item-001") is True
        status = ctrl_with_items.load_status()
        assert status is not None
        item = next(i for i in status.items if i.item_id == "item-001")
        assert item.state == "cleared"

    def test_ack_then_suppress(self, ctrl_with_items: ControlPlaneController) -> None:
        """Acked items can be suppressed."""
        ctrl_with_items.ack_item("item-001")
        assert ctrl_with_items.suppress_item("item-001") is True
        status = ctrl_with_items.load_status()
        assert status is not None
        item = next(i for i in status.items if i.item_id == "item-001")
        assert item.state == "suppressed"

    def test_double_ack_returns_false(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        """Acking an already-acked item returns False (not in open state)."""
        assert ctrl_with_items.ack_item("item-001") is True
        assert ctrl_with_items.ack_item("item-001") is False

    def test_clear_already_cleared_returns_false(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        """Clearing an already-cleared item returns False."""
        assert ctrl_with_items.clear_item("item-001") is True
        assert ctrl_with_items.clear_item("item-001") is False

    def test_suppress_already_suppressed_returns_false(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        """Suppressing an already-suppressed item returns False."""
        assert ctrl_with_items.suppress_item("item-001") is True
        assert ctrl_with_items.suppress_item("item-001") is False

    def test_clear_after_suppress_returns_false(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        """Cannot clear a suppressed item (only open/acked can be cleared)."""
        ctrl_with_items.suppress_item("item-001")
        assert ctrl_with_items.clear_item("item-001") is False

    def test_suppress_after_clear_returns_false(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        """Cannot suppress a cleared item (only open/acked can be suppressed)."""
        ctrl_with_items.clear_item("item-001")
        assert ctrl_with_items.suppress_item("item-001") is False

    def test_operations_on_different_items(
        self, ctrl_with_items: ControlPlaneController
    ) -> None:
        """Operations on one item don't affect another."""
        ctrl_with_items.ack_item("item-001")
        ctrl_with_items.suppress_item("item-002")

        status = ctrl_with_items.load_status()
        assert status is not None

        item1 = next(i for i in status.items if i.item_id == "item-001")
        item2 = next(i for i in status.items if i.item_id == "item-002")
        assert item1.state == "acked"
        assert item2.state == "suppressed"


class TestReconcileMultipleInputs:
    """Verify reconcile() with multiple input source combinations."""

    def test_reconcile_all_none(self, tmp_path: Path) -> None:
        """Reconcile with all inputs explicitly None produces empty status."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        status = ctrl.reconcile(
            monitor_findings=None,
            task_packets=None,
            unacked_messages=None,
            audit_records=None,
        )
        assert isinstance(status, FleetStatus)
        assert status.items == []

    def test_reconcile_with_task_packets(self, tmp_path: Path) -> None:
        """Reconcile processes task packet input."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        packets = [
            {
                "packet_id": "pkt-001",
                "status": "dispatched",
                "owner": "author-a",
                "title": "Test task",
            }
        ]
        status = ctrl.reconcile(task_packets=packets)
        assert isinstance(status, FleetStatus)

    def test_reconcile_with_unacked_messages(self, tmp_path: Path) -> None:
        """Reconcile processes unacked message input."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        messages = [
            {
                "message_id": "msg-001",
                "from_lane": "author-a",
                "type": "blocker",
                "summary": "Help needed",
            }
        ]
        status = ctrl.reconcile(unacked_messages=messages)
        assert isinstance(status, FleetStatus)

    def test_reconcile_with_audit_records(self, tmp_path: Path) -> None:
        """Reconcile processes audit record input."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        audits = [
            {
                "type": "outbound_exchange",
                "timestamp": "2026-01-01T00:00:00Z",
                "details": {"tool": "Bash"},
            }
        ]
        status = ctrl.reconcile(audit_records=audits)
        assert isinstance(status, FleetStatus)

    def test_reconcile_combined_inputs(self, tmp_path: Path) -> None:
        """Reconcile handles all input sources simultaneously."""
        ctrl = ControlPlaneController(runtime_dir=tmp_path)
        findings = [
            {
                "category": "stale_dispatch",
                "severity": "high",
                "summary": "Stale",
                "details": {},
            }
        ]
        packets = [
            {
                "packet_id": "pkt-002",
                "status": "dispatched",
                "owner": "author-b",
                "title": "Another task",
            }
        ]
        status = ctrl.reconcile(
            monitor_findings=findings,
            task_packets=packets,
            unacked_messages=[],
            audit_records=[],
        )
        assert isinstance(status, FleetStatus)
        assert status.cycle_count >= 1
