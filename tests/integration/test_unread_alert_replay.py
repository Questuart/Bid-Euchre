"""Integration test: SP-4-07 proving run 1 — unread-alert replay.

Recreates the failure shape from the 2026-03-24c session where ops detected
25+ HIGH alerts that the orchestrator never saw.  Proves:

1. HIGH alerts persisted via the message bus survive across session boundaries.
2. The controller projection (``reconcile()``) surfaces unread alerts as
   actionable items with appropriate severity.
3. After acking in the message bus, a subsequent reconcile cycle auto-clears
   the items.

No tmux, no live Claude sessions — pure data-contract validation against a
temporary bus root and runtime directory.

Closes #1681.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.control_plane import (
    SEVERITY_HIGH,
    SEVERITY_URGENT,
    STATE_CLEARED,
    STATE_OPEN,
    load_fleet_status,
    reconcile,
)
from bid_euchre.ops.message_bus import (
    ack_message,
    create_message,
    read_inbox,
    send_message,
    shared_bus_root,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def bus_root(tmp_path: Path) -> Path:
    """Create a temporary bus root with inbox directory."""
    return shared_bus_root(tmp_path / "message_bus")


@pytest.fixture()
def events_dir(tmp_path: Path) -> Path:
    """Create a temporary events directory."""
    d = tmp_path / "events"
    d.mkdir()
    return d


@pytest.fixture()
def runtime_dir(tmp_path: Path) -> Path:
    """Create a temporary runtime directory for fleet_status.json."""
    d = tmp_path / "runtime"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _send_high_alert(
    bus_root: Path,
    events_dir: Path,
    *,
    summary: str = "CI failure on PR #100",
    from_lane: str = "ops",
    to_lane: str = "orchestrator",
    priority: str = "high",
    message_type: str = "supervisor_alert",
) -> str:
    """Create and send a high-priority alert message. Returns message_id."""
    msg = create_message(
        from_lane=from_lane,
        to_lane=to_lane,
        message_type=message_type,
        summary=summary,
        priority=priority,
    )
    return send_message(msg, bus_root=bus_root, events_dir=events_dir)


def _backdate_message(
    bus_root: Path, lane_id: str, message_id: str, minutes: int
) -> None:
    """Backdate a message's created_at by *minutes* so age-based filters trigger.

    This writes a status-update record with an older created_at into the
    inbox JSONL.  ``read_inbox`` deduplicates by message_id (latest record
    wins), so we append a record that keeps all fields but rewrites the
    timestamp.
    """
    import json

    inbox_path = bus_root / "inbox" / f"{lane_id}.jsonl"
    # Read all records, find the target message
    records = []
    with open(inbox_path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    target = None
    for rec in records:
        if rec.get("message_id") == message_id:
            target = rec
            break

    if target is None:
        raise ValueError(f"Message {message_id} not found in {lane_id} inbox")

    # Create a backdated copy
    backdated = dict(target)
    old_ts = datetime.now(timezone.utc).timestamp() - (minutes * 60)
    backdated["created_at"] = datetime.fromtimestamp(old_ts, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    # Append the backdated record (latest wins in dedup)
    with open(inbox_path, "a") as f:
        f.write(json.dumps(backdated) + "\n")


# ---------------------------------------------------------------------------
# Test: Unread alerts surface through controller projection
# ---------------------------------------------------------------------------


class TestUnreadAlertReplay:
    """Prove that unread HIGH/URGENT alerts are surfaced by the controller."""

    def test_unread_high_alert_surfaces_in_projection(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """A HIGH alert in the orchestrator inbox appears as an actionable item
        after reconcile, without any manual inbox scan."""

        # Step 1: Seed a HIGH alert from ops to orchestrator
        alert_id = _send_high_alert(
            bus_root, events_dir, summary="Merge conflict on PR #200"
        )

        # Verify message landed in orchestrator inbox
        inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == alert_id for m in inbox)

        # Step 2: Backdate the message so it exceeds the unacked-message age
        # threshold (default 10 minutes in items_from_unacked_messages)
        _backdate_message(bus_root, "orchestrator", alert_id, minutes=15)

        # Step 3: Read unacked messages from the bus and feed to reconcile
        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(unacked) >= 1

        # Step 4: Run controller reconcile with the unacked messages
        status = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=unacked,
        )

        # Step 5: Verify the alert appears as a HIGH actionable item
        high_items = status.high_items
        assert len(high_items) >= 1, (
            f"Expected at least 1 HIGH item, got {len(high_items)}. "
            f"All items: {[i.summary for i in status.items]}"
        )

        # Find the specific alert item
        alert_items = [
            i for i in high_items if "Merge conflict on PR #200" in i.summary
        ]
        assert len(alert_items) == 1, (
            f"Expected exactly 1 alert item for 'Merge conflict on PR #200', "
            f"got {len(alert_items)}. HIGH items: {[i.summary for i in high_items]}"
        )

        item = alert_items[0]
        assert item.severity == SEVERITY_HIGH
        assert item.state == STATE_OPEN
        assert item.category == "unacked_message"
        assert item.source == "message_bus"

        # Step 6: Verify fleet_status.json was persisted
        persisted = load_fleet_status(runtime_dir)
        assert persisted is not None
        assert persisted.cycle_count == 1
        assert len(persisted.high_items) >= 1

    def test_multiple_unread_alerts_all_surface(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """Multiple unread alerts all appear in the projection."""

        alerts = []
        for i in range(5):
            mid = _send_high_alert(
                bus_root,
                events_dir,
                summary=f"Lane stalled: author-{i}",
            )
            alerts.append(mid)

        # Backdate all messages
        for mid in alerts:
            _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )

        status = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=unacked,
        )

        # All 5 should surface
        high_items = status.high_items
        assert len(high_items) >= 5, (
            f"Expected ≥5 HIGH items, got {len(high_items)}. "
            f"Items: {[i.summary for i in status.items]}"
        )

    def test_urgent_escalation_surfaces_at_urgent_severity(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """An URGENT escalation message surfaces with URGENT severity."""

        mid = _send_high_alert(
            bus_root,
            events_dir,
            summary="ESCALATED: lane dead for 30min",
            priority="urgent",
            message_type="escalation",
        )

        _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )

        status = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=unacked,
        )

        urgent_items = status.urgent_items
        assert len(urgent_items) >= 1, (
            f"Expected ≥1 URGENT item, got {len(urgent_items)}. "
            f"All items: {[i.summary for i in status.items]}"
        )

        item = urgent_items[0]
        assert item.severity == SEVERITY_URGENT
        assert item.state == STATE_OPEN


# ---------------------------------------------------------------------------
# Test: Session restart simulation
# ---------------------------------------------------------------------------


class TestSessionRestartReplay:
    """Simulate session restart: alerts from a previous cycle survive and
    reappear in the next reconcile cycle."""

    def test_alerts_survive_across_reconcile_cycles(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """Unread alerts from cycle 1 reappear in cycle 2 (session restart)."""

        # --- Cycle 1: seed alerts and reconcile ---
        mid = _send_high_alert(
            bus_root, events_dir, summary="PR #300 has merge conflict"
        )
        _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        status1 = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=unacked,
        )

        assert status1.cycle_count == 1
        assert len(status1.high_items) >= 1

        # Record the item_id for tracking
        item_id_cycle1 = status1.high_items[0].item_id

        # --- Simulate session restart ---
        # In a real restart, the orchestrator reloads fleet_status.json from
        # disk and re-reads unacked messages from the bus. We do the same.

        # Step A: Re-read from bus (messages are still pending — not acked)
        unacked_restart = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        assert len(unacked_restart) >= 1, "Alert should still be pending after restart"

        # Step B: Reconcile again (loads previous fleet_status.json)
        status2 = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=unacked_restart,
        )

        assert status2.cycle_count == 2
        assert len(status2.high_items) >= 1

        # The item_id should be stable across cycles
        item_ids_cycle2 = {i.item_id for i in status2.high_items}
        assert item_id_cycle1 in item_ids_cycle2, (
            f"Alert item {item_id_cycle1} from cycle 1 not found in cycle 2. "
            f"Cycle 2 IDs: {item_ids_cycle2}"
        )

        # first_seen_at should be preserved from cycle 1
        matching = [i for i in status2.items if i.item_id == item_id_cycle1]
        assert len(matching) == 1
        assert matching[0].first_seen_at == status1.high_items[0].first_seen_at

    def test_fleet_status_persists_to_disk_between_cycles(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """fleet_status.json is durable — a new reconcile can load the previous state."""

        mid = _send_high_alert(bus_root, events_dir, summary="Stale dispatch: author-c")
        _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )

        # Cycle 1
        reconcile(runtime_dir=runtime_dir, unacked_messages=unacked)

        # Verify file exists on disk
        status_path = runtime_dir / "fleet_status.json"
        assert status_path.exists(), "fleet_status.json should be persisted"

        # Load from disk (simulating a fresh process)
        loaded = load_fleet_status(runtime_dir)
        assert loaded is not None
        assert loaded.cycle_count == 1
        assert len(loaded.high_items) >= 1


# ---------------------------------------------------------------------------
# Test: Ack clears alerts on subsequent cycles
# ---------------------------------------------------------------------------


class TestAckClearsAlerts:
    """After acking in the message bus, the next reconcile cycle should
    auto-clear the corresponding actionable item."""

    def test_acked_message_cleared_on_next_cycle(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """Acking a message in the bus removes it from the next projection."""

        # Cycle 1: seed unacked alert
        mid = _send_high_alert(bus_root, events_dir, summary="CI red on author-a PR")
        _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        status1 = reconcile(runtime_dir=runtime_dir, unacked_messages=unacked)
        assert len(status1.high_items) >= 1

        # Ack the message in the bus
        ack_message(mid, "orchestrator", bus_root=bus_root, events_dir=events_dir)

        # Verify message is now acked
        acked_inbox = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="acked",
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == mid for m in acked_inbox)

        # Cycle 2: reconcile with only acked messages (no pending)
        pending = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )

        status2 = reconcile(runtime_dir=runtime_dir, unacked_messages=pending)

        # The alert should now be CLEARED (was in previous, not in new)
        cleared_items = [i for i in status2.items if i.state == STATE_CLEARED]
        assert len(cleared_items) >= 1, (
            f"Expected ≥1 cleared item after acking, got {len(cleared_items)}. "
            f"All items: {[(i.state, i.summary) for i in status2.items]}"
        )

        # No high items should remain open
        assert (
            len(status2.high_items) == 0
        ), f"Expected 0 open HIGH items after ack, got {len(status2.high_items)}"

    def test_partial_ack_preserves_remaining_alerts(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """Acking one of many alerts only clears that one."""

        # Seed 3 alerts
        mids = []
        for i in range(3):
            mid = _send_high_alert(
                bus_root,
                events_dir,
                summary=f"Alert {i}: lane issue",
            )
            mids.append(mid)

        for mid in mids:
            _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        # Cycle 1
        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        status1 = reconcile(runtime_dir=runtime_dir, unacked_messages=unacked)
        assert len(status1.high_items) >= 3

        # Ack only the first alert
        ack_message(mids[0], "orchestrator", bus_root=bus_root, events_dir=events_dir)

        # Cycle 2
        pending = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        status2 = reconcile(runtime_dir=runtime_dir, unacked_messages=pending)

        # 2 alerts should still be open, 1 should be cleared
        assert (
            len(status2.high_items) >= 2
        ), f"Expected ≥2 open HIGH items, got {len(status2.high_items)}"
        cleared = [i for i in status2.items if i.state == STATE_CLEARED]
        assert len(cleared) >= 1


# ---------------------------------------------------------------------------
# Test: Combined monitor findings + unacked messages
# ---------------------------------------------------------------------------


class TestCombinedSources:
    """Controller reconcile combines monitor findings with unacked messages."""

    def test_monitor_findings_and_unacked_messages_coexist(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """Items from both monitor findings and unacked messages appear."""

        # Seed a monitor finding (e.g., merge conflict on PR)
        monitor_findings = [
            {
                "category": "pr_status",
                "severity": "high",
                "summary": "PR #400 has merge conflict",
                "details": {"pr_number": 400, "mergeable": "CONFLICTING"},
            },
        ]

        # Seed an unacked bus message
        mid = _send_high_alert(bus_root, events_dir, summary="Lane author-b stalled")
        _backdate_message(bus_root, "orchestrator", mid, minutes=15)

        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )

        # Reconcile with both sources
        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=monitor_findings,
            unacked_messages=unacked,
        )

        # Should have items from both sources
        sources = {i.source for i in status.items if i.state == STATE_OPEN}
        assert "monitor" in sources, "Should have monitor-derived items"
        assert "message_bus" in sources, "Should have message_bus-derived items"

        # Total open HIGH items should be at least 2
        assert len(status.high_items) >= 2

    def test_reconcile_with_no_alerts_produces_empty_projection(
        self,
        runtime_dir: Path,
    ) -> None:
        """Reconcile with no inputs produces an empty projection."""

        status = reconcile(runtime_dir=runtime_dir)

        assert len(status.items) == 0
        assert len(status.high_items) == 0
        assert len(status.urgent_items) == 0
        assert status.cycle_count == 1

    def test_end_to_end_seed_reconcile_ack_clear(
        self,
        bus_root: Path,
        events_dir: Path,
        runtime_dir: Path,
    ) -> None:
        """Full lifecycle: seed → reconcile → verify → ack → reconcile → verify cleared.

        This is the exact proving-run scenario from #1681:
        1. Ops seeds a P0 finding via the message bus
        2. Controller reconcile writes fleet_status.json
        3. Orchestrator sees the alert in the projection
        4. Orchestrator acks the message
        5. Next reconcile cycle clears the item
        """

        # 1. Ops detects a blocker and sends a HIGH alert
        alert_id = _send_high_alert(
            bus_root,
            events_dir,
            summary="BLOCKER: merge conflict on PR #500",
            priority="high",
        )

        # Backdate to simulate age > threshold
        _backdate_message(bus_root, "orchestrator", alert_id, minutes=20)

        # 2. Controller reconcile (simulates what happens on prompt submission)
        unacked = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        status1 = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=unacked,
        )

        # 3. Orchestrator sees the alert
        assert len(status1.high_items) >= 1
        alert_item = [
            i for i in status1.high_items if "BLOCKER: merge conflict" in i.summary
        ]
        assert len(alert_item) == 1
        assert alert_item[0].state == STATE_OPEN
        assert alert_item[0].recommended_action is not None

        # 4. Orchestrator acks the alert in the bus
        ack_message(alert_id, "orchestrator", bus_root=bus_root, events_dir=events_dir)

        # 5. Next reconcile cycle
        pending = read_inbox(
            "orchestrator",
            bus_root=bus_root,
            status="pending",
            auto_expire=False,
            auto_compact=False,
        )
        status2 = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=pending,
        )

        # 6. Alert should be cleared, no open HIGH items
        assert len(status2.high_items) == 0, (
            f"Expected 0 open HIGH items after ack cycle, "
            f"got {len(status2.high_items)}: "
            f"{[i.summary for i in status2.high_items]}"
        )
        assert status2.cycle_count == 2
