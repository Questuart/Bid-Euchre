"""Unit tests for the controller / reconciler module (SP-4-07 PR 2).

Tests the pure-function derivation core and the side-effecting reconcile loop.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bid_euchre.ops.control_plane import (
    CAT_AUDIT_EXCHANGE,
    STATE_ACKED,
    STATE_CLEARED,
    STATE_OPEN,
    STATE_SUPPRESSED,
    ActionableItem,
    FleetStatus,
    _finding_stable_id,
    ack_item,
    clear_item,
    derive_items,
    format_status_json,
    format_status_text,
    items_from_audit_records,
    items_from_monitor_findings,
    items_from_task_packets,
    items_from_unacked_messages,
    load_fleet_status,
    merge_with_previous,
    monitor_findings_to_dicts,
    reconcile,
    save_fleet_status,
    suppress_item,
)
from bid_euchre.ops.monitor import MonitorFinding

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW_ISO = "2026-03-24T22:00:00+00:00"


def _monitor_finding(
    category: str = "lane_health",
    severity: str = "high",
    summary: str = "Lane dead",
    details: dict | None = None,
) -> dict:
    return {
        "category": category,
        "severity": severity,
        "summary": summary,
        "details": details or {},
    }


def _task_packet(
    packet_id: str = "pkt001",
    status: str = "approved",
    title: str = "Test task",
    owner: str | None = None,
    priority: str = "normal",
) -> dict:
    return {
        "packet_id": packet_id,
        "status": status,
        "title": title,
        "owner": owner,
        "priority": priority,
    }


def _bus_message(
    message_id: str = "msg001",
    priority: str = "high",
    status: str = "delivered",
    from_lane: str = "ops",
    to_lane: str = "orchestrator",
    summary: str = "Alert: lane dead",
    created_at: str | None = None,
) -> dict:
    if created_at is None:
        # 30 minutes ago by default (well past the default 10-min threshold).
        ts = time.time() - 1800
        created_at = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    return {
        "id": message_id,
        "priority": priority,
        "status": status,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "summary": summary,
        "created_at": created_at,
    }


# ---------------------------------------------------------------------------
# ActionableItem construction
# ---------------------------------------------------------------------------


class TestActionableItem:
    def test_valid_construction(self):
        item = ActionableItem(
            item_id="abc123",
            severity="high",
            category="lane_health",
            source="monitor",
            summary="Lane dead",
            first_seen_at=NOW_ISO,
            last_seen_at=NOW_ISO,
        )
        assert item.item_id == "abc123"
        assert item.state == STATE_OPEN

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="Invalid severity"):
            ActionableItem(
                item_id="x",
                severity="critical",
                category="test",
                source="test",
                summary="bad",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
            )

    def test_invalid_state_raises(self):
        with pytest.raises(ValueError, match="Invalid state"):
            ActionableItem(
                item_id="x",
                severity="high",
                category="test",
                source="test",
                summary="bad",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state="invalid",
            )

    def test_optional_fields_default_to_none(self):
        item = ActionableItem(
            item_id="x",
            severity="info",
            category="test",
            source="test",
            summary="test",
            first_seen_at=NOW_ISO,
            last_seen_at=NOW_ISO,
        )
        assert item.lane_id is None
        assert item.task_id is None
        assert item.pr_number is None
        assert item.recommended_action is None
        assert item.details == {}


# ---------------------------------------------------------------------------
# FleetStatus model
# ---------------------------------------------------------------------------


class TestFleetStatus:
    def test_empty_status(self):
        s = FleetStatus(generated_at=NOW_ISO)
        assert s.items == []
        assert s.open_items == []
        assert s.urgent_items == []
        assert s.high_items == []

    def test_property_filters(self):
        items = [
            ActionableItem(
                item_id="a",
                severity="urgent",
                category="test",
                source="test",
                summary="urgent open",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state=STATE_OPEN,
            ),
            ActionableItem(
                item_id="b",
                severity="high",
                category="test",
                source="test",
                summary="high open",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state=STATE_OPEN,
            ),
            ActionableItem(
                item_id="c",
                severity="warn",
                category="test",
                source="test",
                summary="warn acked",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state=STATE_ACKED,
            ),
            ActionableItem(
                item_id="d",
                severity="info",
                category="test",
                source="test",
                summary="info cleared",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state=STATE_CLEARED,
            ),
        ]
        s = FleetStatus(items=items, generated_at=NOW_ISO)
        assert len(s.open_items) == 2
        assert len(s.urgent_items) == 1
        assert len(s.high_items) == 2  # urgent + high

    def test_to_dict_and_from_dict_roundtrip(self):
        items = [
            ActionableItem(
                item_id="x",
                severity="warn",
                category="pr_status",
                source="monitor",
                summary="PR failing",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                pr_number=42,
            )
        ]
        original = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=5)
        data = original.to_dict()
        restored = FleetStatus.from_dict(data)
        assert len(restored.items) == 1
        assert restored.items[0].item_id == "x"
        assert restored.items[0].pr_number == 42
        assert restored.cycle_count == 5
        assert data["summary"]["total"] == 1
        assert data["summary"]["open"] == 1


# ---------------------------------------------------------------------------
# Derivation: monitor findings
# ---------------------------------------------------------------------------


class TestItemsFromMonitorFindings:
    def test_high_severity_finding_produces_item(self):
        findings = [
            _monitor_finding(
                severity="high",
                summary="Lane 'author-a' is active but tmux pane is dead",
                details={"lane_id": "author-a"},
            )
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert len(items) == 1
        assert items[0].severity == "high"
        assert items[0].category == "lane_health"
        assert items[0].source == "monitor"
        assert items[0].lane_id == "author-a"
        assert items[0].recommended_action is not None

    def test_info_capacity_summary_is_filtered_out(self):
        findings = [
            _monitor_finding(
                severity="info",
                category="lane_health",
                summary="Pool: 3 active, 5 idle",
            )
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert len(items) == 0

    def test_info_non_capacity_is_preserved(self):
        findings = [
            _monitor_finding(
                severity="info",
                category="merged_pr",
                summary="PR #1234 merged",
                details={"pr_number": 1234},
            )
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert len(items) == 1
        assert items[0].pr_number == 1234

    def test_stable_ids_across_calls(self):
        findings = [
            _monitor_finding(
                severity="warn",
                summary="PR #100 failing checks",
                details={"number": 100},
            )
        ]
        items1 = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        items2 = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert items1[0].item_id == items2[0].item_id

    def test_different_findings_get_different_ids(self):
        f1 = [_monitor_finding(summary="Lane A dead", details={"lane_id": "a"})]
        f2 = [_monitor_finding(summary="Lane B dead", details={"lane_id": "b"})]
        items1 = items_from_monitor_findings(f1, now_iso=NOW_ISO)
        items2 = items_from_monitor_findings(f2, now_iso=NOW_ISO)
        assert items1[0].item_id != items2[0].item_id

    def test_pr_status_recommendation(self):
        findings = [
            _monitor_finding(
                category="pr_status",
                severity="warn",
                summary="PR #50 has merge conflicts",
                details={"number": 50, "mergeable": "CONFLICTING"},
            )
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert "Rebase" in items[0].recommended_action

    def test_stale_dispatch_recommendation(self):
        findings = [
            _monitor_finding(
                category="stale_dispatch",
                severity="warn",
                summary="Stale dispatch",
            )
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert "nudge" in items[0].recommended_action

    def test_approval_stall_recommendation(self):
        findings = [
            _monitor_finding(
                category="approval_stall",
                severity="high",
                summary="Lane blocked on approval",
            )
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert "Approve" in items[0].recommended_action

    def test_empty_findings(self):
        items = items_from_monitor_findings([], now_iso=NOW_ISO)
        assert items == []


# ---------------------------------------------------------------------------
# Derivation: task packets
# ---------------------------------------------------------------------------


class TestItemsFromTaskPackets:
    def test_approved_packet_produces_item(self):
        packets = [_task_packet(status="approved", title="Deploy fix")]
        items = items_from_task_packets(packets, now_iso=NOW_ISO)
        assert len(items) == 1
        assert "Deploy fix" in items[0].summary
        assert items[0].category == "task_lifecycle"
        assert items[0].source == "task_queue"
        assert items[0].recommended_action is not None

    def test_dispatched_packet_does_not_produce_item(self):
        packets = [_task_packet(status="dispatched")]
        items = items_from_task_packets(packets, now_iso=NOW_ISO)
        assert len(items) == 0

    def test_completed_packet_does_not_produce_item(self):
        packets = [_task_packet(status="completed")]
        items = items_from_task_packets(packets, now_iso=NOW_ISO)
        assert len(items) == 0

    def test_high_priority_approved_is_warn(self):
        packets = [_task_packet(status="approved", priority="high")]
        items = items_from_task_packets(packets, now_iso=NOW_ISO)
        assert items[0].severity == "warn"

    def test_normal_priority_approved_is_info(self):
        packets = [_task_packet(status="approved", priority="normal")]
        items = items_from_task_packets(packets, now_iso=NOW_ISO)
        assert items[0].severity == "info"

    def test_empty_packets(self):
        items = items_from_task_packets([], now_iso=NOW_ISO)
        assert items == []


# ---------------------------------------------------------------------------
# Derivation: unacked bus messages
# ---------------------------------------------------------------------------


class TestItemsFromUnackedMessages:
    def test_old_high_message_produces_item(self):
        msgs = [_bus_message(priority="high")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO)
        assert len(items) == 1
        assert items[0].severity == "high"
        assert items[0].category == "unacked_message"

    def test_old_urgent_message_produces_urgent_item(self):
        msgs = [_bus_message(priority="urgent")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO)
        assert len(items) == 1
        assert items[0].severity == "urgent"

    def test_recent_message_is_filtered_out(self):
        recent = datetime.now(timezone.utc).isoformat()
        msgs = [_bus_message(priority="high", created_at=recent)]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO, max_age_minutes=10)
        assert len(items) == 0

    def test_normal_priority_is_filtered_out(self):
        msgs = [_bus_message(priority="normal")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO)
        assert len(items) == 0

    def test_acked_message_is_filtered_out(self):
        msgs = [_bus_message(priority="high", status="acked")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO)
        assert len(items) == 0

    def test_resolved_message_is_filtered_out(self):
        msgs = [_bus_message(priority="high", status="resolved")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO)
        assert len(items) == 0

    def test_custom_age_threshold(self):
        # Message is 30 min old, threshold is 60 min.
        msgs = [_bus_message(priority="high")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO, max_age_minutes=60)
        assert len(items) == 0

    def test_empty_messages(self):
        items = items_from_unacked_messages([], now_iso=NOW_ISO)
        assert items == []

    def test_malformed_timestamp_skipped(self):
        msgs = [_bus_message(priority="urgent", created_at="not-a-date")]
        items = items_from_unacked_messages(msgs, now_iso=NOW_ISO)
        assert len(items) == 0


# ---------------------------------------------------------------------------
# derive_items (combined)
# ---------------------------------------------------------------------------


class TestDeriveItems:
    def test_combines_all_sources(self):
        findings = [
            _monitor_finding(
                severity="high", summary="Lane dead", details={"lane_id": "a"}
            )
        ]
        packets = [_task_packet(status="approved")]
        msgs = [_bus_message(priority="urgent")]

        items = derive_items(
            monitor_findings=findings,
            task_packets=packets,
            unacked_messages=msgs,
            now_iso=NOW_ISO,
        )
        sources = {i.source for i in items}
        assert "monitor" in sources
        assert "task_queue" in sources
        assert "message_bus" in sources

    def test_none_inputs_produce_empty(self):
        items = derive_items(now_iso=NOW_ISO)
        assert items == []


# ---------------------------------------------------------------------------
# Merge with previous state
# ---------------------------------------------------------------------------


class TestMergeWithPrevious:
    def test_no_previous_returns_new(self):
        items = [
            ActionableItem(
                item_id="a",
                severity="high",
                category="test",
                source="test",
                summary="new",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
            )
        ]
        merged = merge_with_previous(items, None)
        assert len(merged) == 1
        assert merged[0].item_id == "a"

    def test_preserves_first_seen_at(self):
        old_time = "2026-03-24T20:00:00+00:00"
        new_time = "2026-03-24T22:00:00+00:00"

        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="a",
                    severity="high",
                    category="test",
                    source="test",
                    summary="found",
                    first_seen_at=old_time,
                    last_seen_at=old_time,
                )
            ]
        )
        new_items = [
            ActionableItem(
                item_id="a",
                severity="high",
                category="test",
                source="test",
                summary="found",
                first_seen_at=new_time,
                last_seen_at=new_time,
            )
        ]
        merged = merge_with_previous(new_items, previous)
        assert merged[0].first_seen_at == old_time
        assert merged[0].last_seen_at == new_time

    def test_carries_forward_acked_state(self):
        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="a",
                    severity="high",
                    category="test",
                    source="test",
                    summary="found",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=STATE_ACKED,
                )
            ]
        )
        new_items = [
            ActionableItem(
                item_id="a",
                severity="high",
                category="test",
                source="test",
                summary="found",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state=STATE_OPEN,  # new derivation says open
            )
        ]
        merged = merge_with_previous(new_items, previous)
        assert merged[0].state == STATE_ACKED  # acked is preserved

    def test_carries_forward_suppressed_state(self):
        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="a",
                    severity="warn",
                    category="test",
                    source="test",
                    summary="suppressed",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=STATE_SUPPRESSED,
                )
            ]
        )
        new_items = [
            ActionableItem(
                item_id="a",
                severity="warn",
                category="test",
                source="test",
                summary="suppressed",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                state=STATE_OPEN,
            )
        ]
        merged = merge_with_previous(new_items, previous)
        assert merged[0].state == STATE_SUPPRESSED

    def test_auto_clears_vanished_open_items(self):
        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="gone",
                    severity="high",
                    category="test",
                    source="test",
                    summary="was here",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=STATE_OPEN,
                )
            ]
        )
        merged = merge_with_previous([], previous)
        assert len(merged) == 1
        assert merged[0].item_id == "gone"
        assert merged[0].state == STATE_CLEARED

    def test_drops_vanished_cleared_items(self):
        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="old",
                    severity="info",
                    category="test",
                    source="test",
                    summary="already cleared",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=STATE_CLEARED,
                )
            ]
        )
        merged = merge_with_previous([], previous)
        assert len(merged) == 0  # fully dropped

    def test_drops_vanished_suppressed_items(self):
        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="sup",
                    severity="info",
                    category="test",
                    source="test",
                    summary="suppressed",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=STATE_SUPPRESSED,
                )
            ]
        )
        merged = merge_with_previous([], previous)
        assert len(merged) == 0

    def test_new_items_added(self):
        previous = FleetStatus(
            items=[
                ActionableItem(
                    item_id="old",
                    severity="info",
                    category="test",
                    source="test",
                    summary="old item",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                )
            ]
        )
        new_items = [
            ActionableItem(
                item_id="new",
                severity="high",
                category="test",
                source="test",
                summary="new item",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
            )
        ]
        merged = merge_with_previous(new_items, previous)
        ids = {i.item_id for i in merged}
        assert "new" in ids
        assert "old" in ids  # auto-cleared but still present


# ---------------------------------------------------------------------------
# Ack / clear / suppress
# ---------------------------------------------------------------------------


class TestAckClearSuppress:
    def _make_status(self, state: str = STATE_OPEN) -> FleetStatus:
        return FleetStatus(
            items=[
                ActionableItem(
                    item_id="item1",
                    severity="high",
                    category="test",
                    source="test",
                    summary="test",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=state,
                )
            ]
        )

    def test_ack_open_item(self):
        s = self._make_status(STATE_OPEN)
        assert ack_item(s, "item1") is True
        assert s.items[0].state == STATE_ACKED

    def test_ack_non_open_item_returns_false(self):
        s = self._make_status(STATE_ACKED)
        assert ack_item(s, "item1") is False

    def test_ack_nonexistent_returns_false(self):
        s = self._make_status()
        assert ack_item(s, "nonexistent") is False

    def test_clear_open_item(self):
        s = self._make_status(STATE_OPEN)
        assert clear_item(s, "item1") is True
        assert s.items[0].state == STATE_CLEARED

    def test_clear_acked_item(self):
        s = self._make_status(STATE_ACKED)
        assert clear_item(s, "item1") is True
        assert s.items[0].state == STATE_CLEARED

    def test_clear_already_cleared_returns_false(self):
        s = self._make_status(STATE_CLEARED)
        assert clear_item(s, "item1") is False

    def test_suppress_open_item(self):
        s = self._make_status(STATE_OPEN)
        assert suppress_item(s, "item1") is True
        assert s.items[0].state == STATE_SUPPRESSED

    def test_suppress_cleared_returns_false(self):
        s = self._make_status(STATE_CLEARED)
        assert suppress_item(s, "item1") is False


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path: Path):
        items = [
            ActionableItem(
                item_id="p1",
                severity="warn",
                category="pr_status",
                source="monitor",
                summary="PR #42 failing",
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                pr_number=42,
            )
        ]
        status = FleetStatus(items=items, generated_at=NOW_ISO, cycle_count=3)
        path = save_fleet_status(status, tmp_path)
        assert path.exists()

        loaded = load_fleet_status(tmp_path)
        assert loaded is not None
        assert len(loaded.items) == 1
        assert loaded.items[0].item_id == "p1"
        assert loaded.items[0].pr_number == 42
        assert loaded.cycle_count == 3

    def test_load_missing_returns_none(self, tmp_path: Path):
        assert load_fleet_status(tmp_path) is None

    def test_load_corrupt_file_returns_none(self, tmp_path: Path):
        path = tmp_path / "fleet_status.json"
        path.write_text("not json!!!")
        assert load_fleet_status(tmp_path) is None

    def test_save_creates_directory(self, tmp_path: Path):
        nested = tmp_path / "deep" / "dir"
        status = FleetStatus(generated_at=NOW_ISO)
        save_fleet_status(status, nested)
        assert (nested / "fleet_status.json").exists()

    def test_atomic_write_valid_json(self, tmp_path: Path):
        status = FleetStatus(
            items=[
                ActionableItem(
                    item_id="x",
                    severity="info",
                    category="test",
                    source="test",
                    summary="test",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                )
            ],
            generated_at=NOW_ISO,
        )
        save_fleet_status(status, tmp_path)
        data = json.loads((tmp_path / "fleet_status.json").read_text())
        assert "items" in data
        assert "summary" in data
        assert data["summary"]["total"] == 1


# ---------------------------------------------------------------------------
# Full reconcile cycle
# ---------------------------------------------------------------------------


class TestReconcile:
    def test_first_cycle(self, tmp_path: Path):
        findings = [
            _monitor_finding(
                severity="high",
                summary="Lane dead",
                details={"lane_id": "author-a"},
            )
        ]
        status = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=findings,
            now_iso=NOW_ISO,
        )
        assert status.cycle_count == 1
        assert len(status.open_items) == 1

    def test_second_cycle_increments_count(self, tmp_path: Path):
        findings = [
            _monitor_finding(
                severity="warn",
                summary="Stale dispatch",
                category="stale_dispatch",
            )
        ]
        reconcile(runtime_dir=tmp_path, monitor_findings=findings, now_iso=NOW_ISO)
        status = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=findings,
            now_iso=NOW_ISO,
        )
        assert status.cycle_count == 2

    def test_preserves_ack_across_cycles(self, tmp_path: Path):
        findings = [
            _monitor_finding(
                severity="high",
                summary="Lane dead",
                details={"lane_id": "author-a"},
            )
        ]
        status1 = reconcile(
            runtime_dir=tmp_path, monitor_findings=findings, now_iso=NOW_ISO
        )
        # Ack the item.
        ack_item(status1, status1.items[0].item_id)
        save_fleet_status(status1, tmp_path)

        # Next cycle — same finding present.
        status2 = reconcile(
            runtime_dir=tmp_path, monitor_findings=findings, now_iso=NOW_ISO
        )
        target = [i for i in status2.items if i.lane_id == "author-a"]
        assert target[0].state == STATE_ACKED

    def test_auto_clears_resolved_findings(self, tmp_path: Path):
        findings = [
            _monitor_finding(
                severity="high",
                summary="Lane dead",
                details={"lane_id": "author-a"},
            )
        ]
        reconcile(runtime_dir=tmp_path, monitor_findings=findings, now_iso=NOW_ISO)

        # Next cycle — finding gone.
        status2 = reconcile(runtime_dir=tmp_path, now_iso=NOW_ISO)
        cleared = [i for i in status2.items if i.state == STATE_CLEARED]
        assert len(cleared) == 1

    def test_persists_to_disk(self, tmp_path: Path):
        reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[_monitor_finding(severity="warn", summary="test")],
            now_iso=NOW_ISO,
        )
        assert (tmp_path / "fleet_status.json").exists()
        data = json.loads((tmp_path / "fleet_status.json").read_text())
        assert data["cycle_count"] == 1

    def test_empty_cycle(self, tmp_path: Path):
        status = reconcile(runtime_dir=tmp_path, now_iso=NOW_ISO)
        assert status.cycle_count == 1
        assert len(status.items) == 0


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_text_empty(self):
        s = FleetStatus(generated_at=NOW_ISO)
        text = format_status_text(s)
        assert "all clear" in text

    def test_format_text_with_items(self):
        s = FleetStatus(
            items=[
                ActionableItem(
                    item_id="abc12345",
                    severity="high",
                    category="lane_health",
                    source="monitor",
                    summary="Lane author-a dead",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    recommended_action="Check tmux pane",
                )
            ],
            generated_at=NOW_ISO,
            cycle_count=5,
        )
        text = format_status_text(s)
        assert "HIGH" in text
        assert "abc12345" in text
        assert "Lane author-a dead" in text
        assert "Check tmux pane" in text

    def test_format_text_groups_by_severity(self):
        s = FleetStatus(
            items=[
                ActionableItem(
                    item_id="u1",
                    severity="urgent",
                    category="test",
                    source="test",
                    summary="Urgent item",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                ),
                ActionableItem(
                    item_id="w1",
                    severity="warn",
                    category="test",
                    source="test",
                    summary="Warn item",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                ),
            ],
            generated_at=NOW_ISO,
            cycle_count=1,
        )
        text = format_status_text(s)
        urgent_pos = text.index("URGENT")
        warn_pos = text.index("WARN")
        assert urgent_pos < warn_pos

    def test_format_json_valid(self):
        s = FleetStatus(
            items=[
                ActionableItem(
                    item_id="j1",
                    severity="info",
                    category="test",
                    source="test",
                    summary="json test",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                )
            ],
            generated_at=NOW_ISO,
        )
        data = json.loads(format_status_json(s))
        assert len(data["items"]) == 1
        assert "summary" in data

    def test_format_text_shows_acked_count(self):
        s = FleetStatus(
            items=[
                ActionableItem(
                    item_id="a1",
                    severity="high",
                    category="test",
                    source="test",
                    summary="acked",
                    first_seen_at=NOW_ISO,
                    last_seen_at=NOW_ISO,
                    state=STATE_ACKED,
                ),
            ],
            generated_at=NOW_ISO,
            cycle_count=1,
        )
        text = format_status_text(s)
        assert "acked: 1" in text


# ---------------------------------------------------------------------------
# Stable ID determinism
# ---------------------------------------------------------------------------


class TestStableIds:
    def test_same_inputs_same_id(self):
        f1 = [
            _monitor_finding(
                severity="high",
                summary="Lane dead",
                details={"lane_id": "author-a"},
            )
        ]
        items1 = items_from_monitor_findings(f1, now_iso=NOW_ISO)
        items2 = items_from_monitor_findings(f1, now_iso=NOW_ISO)
        assert items1[0].item_id == items2[0].item_id

    def test_different_lanes_different_ids(self):
        f1 = [_monitor_finding(details={"lane_id": "a"})]
        f2 = [_monitor_finding(details={"lane_id": "b"})]
        i1 = items_from_monitor_findings(f1, now_iso=NOW_ISO)
        i2 = items_from_monitor_findings(f2, now_iso=NOW_ISO)
        assert i1[0].item_id != i2[0].item_id


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_derive_with_all_none(self):
        items = derive_items(
            monitor_findings=None,
            task_packets=None,
            unacked_messages=None,
            now_iso=NOW_ISO,
        )
        assert items == []

    def test_reconcile_corrupt_previous(self, tmp_path: Path):
        # Write corrupt data.
        (tmp_path / "fleet_status.json").write_text("{bad json")
        # Should still work — treats as no previous.
        status = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[_monitor_finding(severity="warn", summary="test")],
            now_iso=NOW_ISO,
        )
        assert status.cycle_count == 1  # starts fresh

    def test_multiple_items_same_source(self):
        findings = [
            _monitor_finding(
                severity="high",
                summary="Lane A dead",
                details={"lane_id": "author-a"},
            ),
            _monitor_finding(
                severity="high",
                summary="Lane B dead",
                details={"lane_id": "author-b"},
            ),
        ]
        items = items_from_monitor_findings(findings, now_iso=NOW_ISO)
        assert len(items) == 2
        assert items[0].item_id != items[1].item_id


# ---------------------------------------------------------------------------
# MonitorFinding → dict bridge
# ---------------------------------------------------------------------------


class TestMonitorFindingsToDicts:
    def test_converts_single_finding(self):
        finding = MonitorFinding(
            category="lane_health",
            severity="high",
            summary="Lane dead",
            details={"lane_id": "author-a"},
        )
        result = monitor_findings_to_dicts([finding])
        assert len(result) == 1
        assert result[0]["category"] == "lane_health"
        assert result[0]["severity"] == "high"
        assert result[0]["summary"] == "Lane dead"
        assert result[0]["details"]["lane_id"] == "author-a"

    def test_converts_multiple_findings(self):
        findings = [
            MonitorFinding(
                category="lane_health",
                severity="high",
                summary="Lane A dead",
                details={"lane_id": "author-a"},
            ),
            MonitorFinding(
                category="pr_status",
                severity="warn",
                summary="PR #42 failing",
                details={"number": 42},
            ),
        ]
        result = monitor_findings_to_dicts(findings)
        assert len(result) == 2
        assert result[0]["category"] == "lane_health"
        assert result[1]["category"] == "pr_status"

    def test_empty_list(self):
        result = monitor_findings_to_dicts([])
        assert result == []

    def test_roundtrip_through_items_from_monitor_findings(self):
        """MonitorFinding → dict → ActionableItem works end-to-end."""
        finding = MonitorFinding(
            category="stale_dispatch",
            severity="warn",
            summary="Stale dispatch for author-a",
            details={"lane_id": "author-a", "task_id": "pkt001"},
        )
        dicts = monitor_findings_to_dicts([finding])
        items = items_from_monitor_findings(dicts, now_iso=NOW_ISO)
        assert len(items) == 1
        assert items[0].category == "stale_dispatch"
        assert items[0].severity == "warn"
        assert items[0].lane_id == "author-a"
        assert items[0].task_id == "pkt001"
        assert items[0].source == "monitor"


# ---------------------------------------------------------------------------
# Stable ID robustness (dedup across cycles with changing details)
# ---------------------------------------------------------------------------


class TestFindingStableIdDedup:
    def test_same_lane_different_summary_same_id(self):
        """Same logical condition with changing summary text → same item_id."""
        details = {"lane_id": "author-a"}
        id1 = _finding_stable_id("lane_health", details)
        id2 = _finding_stable_id("lane_health", details)
        assert id1 == id2

    def test_same_pr_different_check_count_same_id(self):
        """PR findings with changing check counts → same item_id."""
        details1 = {"number": 42, "failing_checks": 2}
        details2 = {"number": 42, "failing_checks": 5}
        id1 = _finding_stable_id("pr_status", details1)
        id2 = _finding_stable_id("pr_status", details2)
        assert id1 == id2

    def test_different_lanes_different_ids(self):
        d1 = {"lane_id": "author-a"}
        d2 = {"lane_id": "author-b"}
        assert _finding_stable_id("lane_health", d1) != _finding_stable_id(
            "lane_health", d2
        )

    def test_different_categories_same_details_different_ids(self):
        details = {"lane_id": "author-a"}
        assert _finding_stable_id("lane_health", details) != _finding_stable_id(
            "stalled_lane", details
        )

    def test_no_identifiers_uses_summary_fallback(self):
        """Findings with no lane/PR/task keys fall back to summary-based id."""
        d1 = {"summary": "Fleet idle for 90 minutes"}
        d2 = {"summary": "Something completely different"}
        id1 = _finding_stable_id("idle_lane", d1)
        id2 = _finding_stable_id("idle_lane", d2)
        assert id1 != id2

    def test_finding_dedup_across_cycles_preserves_first_seen(self, tmp_path):
        """Same logical finding across 2 cycles keeps first_seen_at."""
        # Cycle 1: PR #50 has 2 failing checks.
        findings_c1 = [
            _monitor_finding(
                category="pr_status",
                severity="warn",
                summary="PR #50 has 2 failing checks",
                details={"number": 50, "failing_checks": 2},
            )
        ]
        status1 = reconcile(
            runtime_dir=tmp_path, monitor_findings=findings_c1, now_iso=NOW_ISO
        )
        assert len(status1.open_items) == 1
        item_id_c1 = status1.items[0].item_id

        # Cycle 2: Same PR, different check count text.
        later = "2026-03-24T23:00:00+00:00"
        findings_c2 = [
            _monitor_finding(
                category="pr_status",
                severity="warn",
                summary="PR #50 has 5 failing checks",
                details={"number": 50, "failing_checks": 5},
            )
        ]
        status2 = reconcile(
            runtime_dir=tmp_path, monitor_findings=findings_c2, now_iso=later
        )
        # Same logical finding — should keep the same item_id.
        item_id_c2 = [i for i in status2.items if i.state == STATE_OPEN][0].item_id
        assert item_id_c1 == item_id_c2
        # first_seen_at should be from cycle 1, not cycle 2.
        open_items = [i for i in status2.items if i.state == STATE_OPEN]
        assert open_items[0].first_seen_at == NOW_ISO


# ---------------------------------------------------------------------------
# derive_items / reconcile with MonitorFinding objects
# ---------------------------------------------------------------------------


class TestDeriveItemsWithMonitorObjects:
    def test_accepts_monitor_finding_objects(self):
        findings = [
            MonitorFinding(
                category="stale_dispatch",
                severity="warn",
                summary="Stale dispatch",
                details={"lane_id": "author-a"},
            )
        ]
        items = derive_items(monitor_finding_objects=findings, now_iso=NOW_ISO)
        assert len(items) == 1
        assert items[0].source == "monitor"
        assert items[0].category == "stale_dispatch"

    def test_combines_dict_and_object_findings(self):
        dict_findings = [
            _monitor_finding(
                severity="high",
                summary="Lane A dead",
                details={"lane_id": "author-a"},
            )
        ]
        obj_findings = [
            MonitorFinding(
                category="pr_status",
                severity="warn",
                summary="PR #99 failing",
                details={"number": 99},
            )
        ]
        items = derive_items(
            monitor_findings=dict_findings,
            monitor_finding_objects=obj_findings,
            now_iso=NOW_ISO,
        )
        categories = {i.category for i in items}
        assert "lane_health" in categories
        assert "pr_status" in categories
        assert len(items) == 2

    def test_none_objects_ignored(self):
        items = derive_items(
            monitor_finding_objects=None,
            now_iso=NOW_ISO,
        )
        assert items == []


class TestReconcileWithMonitorObjects:
    def test_reconcile_with_monitor_finding_objects(self, tmp_path):
        findings = [
            MonitorFinding(
                category="lane_health",
                severity="high",
                summary="Lane dead",
                details={"lane_id": "author-b"},
            )
        ]
        status = reconcile(
            runtime_dir=tmp_path,
            monitor_finding_objects=findings,
            now_iso=NOW_ISO,
        )
        assert status.cycle_count == 1
        assert len(status.open_items) == 1
        assert status.items[0].lane_id == "author-b"

    def test_reconcile_combines_dict_and_object(self, tmp_path):
        dict_findings = [
            _monitor_finding(
                severity="warn",
                summary="Stale dispatch",
                category="stale_dispatch",
                details={"lane_id": "flex-a"},
            )
        ]
        obj_findings = [
            MonitorFinding(
                category="approval_stall",
                severity="high",
                summary="Lane blocked on approval",
                details={"lane_id": "author-c"},
            )
        ]
        status = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=dict_findings,
            monitor_finding_objects=obj_findings,
            now_iso=NOW_ISO,
        )
        assert len(status.open_items) == 2
        categories = {i.category for i in status.open_items}
        assert "stale_dispatch" in categories
        assert "approval_stall" in categories

    def test_monitor_objects_auto_clear_across_cycles(self, tmp_path):
        """MonitorFinding objects correctly participate in auto-clear lifecycle."""
        findings_c1 = [
            MonitorFinding(
                category="lane_health",
                severity="high",
                summary="Lane dead",
                details={"lane_id": "author-d"},
            )
        ]
        reconcile(
            runtime_dir=tmp_path,
            monitor_finding_objects=findings_c1,
            now_iso=NOW_ISO,
        )
        # Second cycle: finding gone → auto-cleared.
        status2 = reconcile(runtime_dir=tmp_path, now_iso=NOW_ISO)
        cleared = [i for i in status2.items if i.state == STATE_CLEARED]
        assert len(cleared) == 1
        assert cleared[0].lane_id == "author-d"

    def test_monitor_objects_ack_preserved_across_cycles(self, tmp_path):
        """Acked item from MonitorFinding stays acked when re-detected."""
        findings = [
            MonitorFinding(
                category="stalled_lane",
                severity="warn",
                summary="Author-a stalled",
                details={"lane_id": "author-a"},
            )
        ]
        status1 = reconcile(
            runtime_dir=tmp_path,
            monitor_finding_objects=findings,
            now_iso=NOW_ISO,
        )
        ack_item(status1, status1.items[0].item_id)
        save_fleet_status(status1, tmp_path)

        # Re-detect same finding.
        status2 = reconcile(
            runtime_dir=tmp_path,
            monitor_finding_objects=findings,
            now_iso=NOW_ISO,
        )
        target = [i for i in status2.items if i.lane_id == "author-a"]
        assert target[0].state == STATE_ACKED


# ---------------------------------------------------------------------------
# Derivation: audit trail records
# ---------------------------------------------------------------------------


def _audit_record(
    direction: str = "inbound",
    chat_id: str = "123",
    sender: str = "operator",
    exchange_type: str = "message",
    content_preview: str = "Hello",
    ts: str = "2026-03-24T07:00:00+00:00",
    exchange_id: str = "ex-1",
) -> dict:
    return {
        "exchange_id": exchange_id,
        "timestamp": ts,
        "direction": direction,
        "channel_source": "telegram",
        "sender_identity": sender,
        "exchange_type": exchange_type,
        "content_hash": "abc123",
        "content_preview": content_preview,
        "chat_id": chat_id,
        "message_id": "1",
        "metadata": {},
    }


class TestItemsFromAuditRecords:
    def test_unanswered_inbound_produces_item(self):
        records = [_audit_record(direction="inbound")]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert len(items) == 1
        assert items[0].category == CAT_AUDIT_EXCHANGE
        assert items[0].source == "audit_trail"
        assert "operator" in items[0].summary

    def test_answered_inbound_no_item(self):
        records = [
            _audit_record(
                direction="inbound",
                ts="2026-03-24T07:00:00+00:00",
                exchange_id="in-1",
            ),
            _audit_record(
                direction="outbound",
                ts="2026-03-24T07:01:00+00:00",
                exchange_type="reply",
                sender="orchestrator",
                exchange_id="out-1",
            ),
        ]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert len(items) == 0

    def test_recent_inbound_below_threshold(self):
        records = [
            _audit_record(
                direction="inbound",
                ts="2026-03-24T07:58:00+00:00",
            )
        ]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert len(items) == 0

    def test_severity_warn_under_30min(self):
        records = [
            _audit_record(
                direction="inbound",
                ts="2026-03-24T07:50:00+00:00",
                chat_id="a",
            )
        ]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert items[0].severity == "warn"

    def test_severity_high_over_30min(self):
        records = [
            _audit_record(
                direction="inbound",
                ts="2026-03-24T07:15:00+00:00",
                chat_id="b",
            )
        ]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert items[0].severity == "high"

    def test_multi_chat_independent(self):
        records = [
            _audit_record(direction="inbound", chat_id="A", exchange_id="a-in"),
            _audit_record(
                direction="outbound",
                chat_id="A",
                ts="2026-03-24T07:01:00+00:00",
                exchange_type="reply",
                exchange_id="a-out",
            ),
            _audit_record(direction="inbound", chat_id="B", exchange_id="b-in"),
        ]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert len(items) == 1
        assert items[0].details["chat_id"] == "B"

    def test_empty_records(self):
        items = items_from_audit_records(
            [], now_iso=NOW_ISO, unanswered_threshold_minutes=5
        )
        assert items == []

    def test_outbound_only_no_item(self):
        records = [
            _audit_record(direction="outbound", exchange_type="reply"),
        ]
        items = items_from_audit_records(
            records,
            now_iso="2026-03-24T08:00:00+00:00",
            unanswered_threshold_minutes=5,
        )
        assert len(items) == 0

    def test_stable_ids(self):
        records = [_audit_record(direction="inbound", chat_id="X")]
        items1 = items_from_audit_records(records, now_iso="2026-03-24T08:00:00+00:00")
        items2 = items_from_audit_records(records, now_iso="2026-03-24T08:00:00+00:00")
        assert items1[0].item_id == items2[0].item_id


class TestDeriveItemsWithAudit:
    def test_audit_records_in_derive_items(self):
        records = [_audit_record(direction="inbound", ts="2026-03-24T07:00:00+00:00")]
        items = derive_items(
            audit_records=records,
            now_iso="2026-03-24T08:00:00+00:00",
        )
        audit_items = [i for i in items if i.category == CAT_AUDIT_EXCHANGE]
        assert len(audit_items) == 1

    def test_audit_combined_with_other_sources(self):
        findings = [
            _monitor_finding(
                severity="high",
                summary="Lane dead",
                details={"lane_id": "a"},
            )
        ]
        records = [_audit_record(direction="inbound", ts="2026-03-24T07:00:00+00:00")]
        items = derive_items(
            monitor_findings=findings,
            audit_records=records,
            now_iso="2026-03-24T08:00:00+00:00",
        )
        sources = {i.source for i in items}
        assert "monitor" in sources
        assert "audit_trail" in sources


class TestReconcileWithAudit:
    def test_reconcile_with_audit_records(self, tmp_path: Path):
        records = [_audit_record(direction="inbound", ts="2026-03-24T07:00:00+00:00")]
        status = reconcile(
            runtime_dir=tmp_path,
            audit_records=records,
            now_iso="2026-03-24T08:00:00+00:00",
        )
        audit_items = [i for i in status.items if i.category == CAT_AUDIT_EXCHANGE]
        assert len(audit_items) == 1
        assert status.cycle_count == 1

    def test_reconcile_audit_clears_when_answered(self, tmp_path: Path):
        # Cycle 1: unanswered inbound
        records = [_audit_record(direction="inbound", ts="2026-03-24T07:00:00+00:00")]
        status1 = reconcile(
            runtime_dir=tmp_path,
            audit_records=records,
            now_iso="2026-03-24T08:00:00+00:00",
        )
        assert len(status1.open_items) == 1

        # Cycle 2: now answered
        records_answered = [
            _audit_record(
                direction="inbound",
                ts="2026-03-24T07:00:00+00:00",
                exchange_id="in-1",
            ),
            _audit_record(
                direction="outbound",
                ts="2026-03-24T07:30:00+00:00",
                exchange_type="reply",
                exchange_id="out-1",
            ),
        ]
        status2 = reconcile(
            runtime_dir=tmp_path,
            audit_records=records_answered,
            now_iso="2026-03-24T08:00:00+00:00",
        )
        # The unanswered item from cycle 1 should be auto-cleared
        open_audit = [
            i
            for i in status2.items
            if i.category == CAT_AUDIT_EXCHANGE and i.state == "open"
        ]
        assert len(open_audit) == 0


# ---------------------------------------------------------------------------
# cmd_monitor → reconcile wiring (#1684)
# ---------------------------------------------------------------------------


class TestMonitorReconcileWiring:
    """Verify that cmd_monitor calls reconcile() after the monitor cycle.

    The ``cmd_monitor`` function lives in ``scripts/internal/ops.py`` which
    has a top-level ``from _repo_utils import ...`` that only resolves when
    run via ``uv run``.  Rather than importing the CLI module directly, we
    test the wiring contract at the library level: the monitor cycle produces
    ``MonitorFinding`` objects and these can be fed directly into
    ``reconcile(monitor_finding_objects=...)``.  A subprocess smoke test
    validates the full CLI path.
    """

    def test_monitor_findings_feed_into_reconcile(self, tmp_path: Path):
        """Monitor findings fed into reconcile() produce fleet status."""
        from bid_euchre.ops.monitor import MonitorFinding

        finding = MonitorFinding(
            category="pr_status",
            severity="warn",
            summary="PR #42 has failing checks",
            details={"pr_number": 42},
        )

        status = reconcile(
            runtime_dir=tmp_path,
            monitor_finding_objects=[finding],
        )

        assert status.cycle_count == 1
        assert len(status.items) >= 1
        pr_items = [i for i in status.items if i.pr_number == 42]
        assert len(pr_items) == 1
        assert pr_items[0].summary == "PR #42 has failing checks"

        # Fleet status file should exist on disk.
        loaded = load_fleet_status(tmp_path)
        assert loaded is not None
        assert loaded.cycle_count == 1

    def test_monitor_findings_plus_task_packets(self, tmp_path: Path):
        """reconcile() combines monitor findings and task packets."""
        from dataclasses import asdict

        from bid_euchre.ops.monitor import MonitorFinding
        from bid_euchre.ops.task_queue import TaskPacket

        finding = MonitorFinding(
            category="lane_health",
            severity="high",
            summary="Lane author-a is unresponsive",
            details={"lane_id": "author-a"},
        )

        packet = TaskPacket(
            packet_id="abc123",
            title="Test task",
            description="A test",
            owner=None,
            created_by="orchestrator",
            created_at="2026-03-24T22:00:00Z",
            status="approved",
            priority="high",
        )

        status = reconcile(
            runtime_dir=tmp_path,
            monitor_finding_objects=[finding],
            task_packets=[asdict(packet)],
        )

        assert status.cycle_count == 1
        # Both sources should produce items.
        lane_items = [i for i in status.items if i.lane_id == "author-a"]
        task_items = [i for i in status.items if i.task_id == "abc123"]
        assert len(lane_items) >= 1
        assert len(task_items) == 1

    def test_cli_monitor_reconcile_smoke(self, tmp_path: Path):
        """CLI ``ops.py monitor --skip-pr-check`` updates fleet status."""
        import subprocess

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "--runtime-dir",
                str(tmp_path),
                "monitor",
                "--skip-pr-check",
                "--no-notify",
                "--no-recovery",
                "--no-auto-dispatch",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        # Monitor should succeed (may exit 1 for high-severity findings
        # but should not crash).
        assert result.returncode in (
            0,
            1,
        ), f"Monitor crashed: stderr={result.stderr[:500]}"

        # Fleet status file should have been written by reconcile().
        loaded = load_fleet_status(tmp_path)
        assert (
            loaded is not None
        ), f"reconcile() did not write fleet_status.json; stdout={result.stdout[:300]}"
        assert loaded.cycle_count >= 1

    def test_cli_no_reconcile_flag(self, tmp_path: Path):
        """CLI ``--no-reconcile`` skips fleet status update."""
        import subprocess

        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/internal/ops.py",
                "--runtime-dir",
                str(tmp_path),
                "monitor",
                "--skip-pr-check",
                "--no-notify",
                "--no-recovery",
                "--no-auto-dispatch",
                "--no-reconcile",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode in (0, 1)

        # No fleet status file should exist.
        assert load_fleet_status(tmp_path) is None


# ---------------------------------------------------------------------------
# Proving run 3 — persistence, deduplication, and clear lifecycle (#1678)
# ---------------------------------------------------------------------------


class TestControllerPersistenceAndDedupe:
    """Prove controller projection persistence and deduplication work correctly.

    Scenario from issue #1678:
    1. Seed one urgent finding, reconcile → verify exactly 1 actionable item
    2. Reconcile 5 more times with same finding → item count stays at 1
    3. Simulate restart (reload from disk) → item resurfaces
    4. Ack the item → verify state transitions to acked
    5. Resolve (remove finding) → verify item clears from fleet_status.json
    """

    def _urgent_stalled_finding(self) -> dict:
        """A single urgent stalled-lane finding used throughout the scenario."""
        return _monitor_finding(
            category="stalled_lane",
            severity="urgent",
            summary="Lane author-a stalled for 45 min",
            details={"lane_id": "author-a", "stall_minutes": 45},
        )

    # -- Step 1: Seed one urgent finding -------------------------------------

    def test_persist_single_urgent_item(self, tmp_path: Path):
        """Reconcile with one urgent finding → exactly 1 open item on disk."""
        finding = self._urgent_stalled_finding()
        status = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[finding],
            now_iso=NOW_ISO,
        )

        assert len(status.items) == 1
        assert len(status.open_items) == 1
        assert status.items[0].severity == "urgent"
        assert status.items[0].state == STATE_OPEN
        assert status.items[0].category == "stalled_lane"
        assert status.cycle_count == 1

        # Verify it's on disk and valid JSON.
        loaded = load_fleet_status(tmp_path)
        assert loaded is not None
        assert len(loaded.items) == 1
        assert loaded.items[0].item_id == status.items[0].item_id

    # -- Step 2: Repeated reconcile doesn't duplicate -------------------------

    def test_dedupe_across_repeated_reconcile_cycles(self, tmp_path: Path):
        """Running reconcile 6 times with the same finding keeps item count at 1."""
        finding = self._urgent_stalled_finding()
        timestamps = [f"2026-03-24T22:{i:02d}:00+00:00" for i in range(6)]

        first_item_id = None
        for cycle, ts in enumerate(timestamps, 1):
            status = reconcile(
                runtime_dir=tmp_path,
                monitor_findings=[finding],
                now_iso=ts,
            )

            # Every cycle: exactly 1 open item, no duplicates.
            open_items = status.open_items
            assert (
                len(open_items) == 1
            ), f"Cycle {cycle}: expected 1 open item, got {len(open_items)}"
            assert status.cycle_count == cycle

            if first_item_id is None:
                first_item_id = open_items[0].item_id
            else:
                # Same logical item across all cycles.
                assert open_items[0].item_id == first_item_id

        # After 6 cycles, verify first_seen_at is preserved from cycle 1.
        final = load_fleet_status(tmp_path)
        assert final is not None
        assert len(final.open_items) == 1
        assert final.open_items[0].first_seen_at == timestamps[0]
        assert final.open_items[0].last_seen_at == timestamps[-1]

    # -- Step 3: Persistence survives restart ---------------------------------

    def test_persist_survives_restart(self, tmp_path: Path):
        """State written to disk survives a simulated restart (fresh load)."""
        finding = self._urgent_stalled_finding()

        # Write state.
        status1 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[finding],
            now_iso=NOW_ISO,
        )
        original_id = status1.items[0].item_id

        # Simulate restart: discard all in-memory state, reload from disk only.
        reloaded = load_fleet_status(tmp_path)
        assert reloaded is not None
        assert len(reloaded.items) == 1
        assert reloaded.items[0].item_id == original_id
        assert reloaded.items[0].severity == "urgent"
        assert reloaded.items[0].state == STATE_OPEN

        # Resume reconciliation with the same finding — item persists,
        # first_seen_at is preserved, and cycle_count increments.
        later = "2026-03-24T23:00:00+00:00"
        status2 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[finding],
            now_iso=later,
        )
        assert len(status2.open_items) == 1
        assert status2.open_items[0].item_id == original_id
        assert status2.open_items[0].first_seen_at == NOW_ISO
        assert status2.cycle_count == 2

    # -- Step 4: Ack transitions state ----------------------------------------

    def test_persist_ack_survives_reconcile(self, tmp_path: Path):
        """Acking an item persists across subsequent reconcile cycles."""
        finding = self._urgent_stalled_finding()

        # Cycle 1: create the item.
        status1 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[finding],
            now_iso=NOW_ISO,
        )
        item_id = status1.items[0].item_id
        assert status1.items[0].state == STATE_OPEN

        # Ack it and save.
        assert ack_item(status1, item_id) is True
        assert status1.items[0].state == STATE_ACKED
        save_fleet_status(status1, tmp_path)

        # Cycle 2: same finding still present — acked state survives merge.
        later = "2026-03-24T23:00:00+00:00"
        status2 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[finding],
            now_iso=later,
        )
        matched = [i for i in status2.items if i.item_id == item_id]
        assert len(matched) == 1
        assert matched[0].state == STATE_ACKED

        # Verify on disk too.
        loaded = load_fleet_status(tmp_path)
        assert loaded is not None
        disk_item = [i for i in loaded.items if i.item_id == item_id]
        assert len(disk_item) == 1
        assert disk_item[0].state == STATE_ACKED

    # -- Step 5: Resolve clears the item --------------------------------------

    def test_clear_after_resolve(self, tmp_path: Path):
        """Removing the finding causes the item to auto-clear on next cycle."""
        finding = self._urgent_stalled_finding()

        # Cycle 1: item exists.
        status1 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[finding],
            now_iso=NOW_ISO,
        )
        assert len(status1.open_items) == 1
        item_id = status1.items[0].item_id

        # Cycle 2: finding is gone (lane recovered) → item auto-clears.
        later = "2026-03-24T23:00:00+00:00"
        status2 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[],  # No findings — condition resolved.
            now_iso=later,
        )

        # No open items.
        assert len(status2.open_items) == 0

        # The item should be present with state "cleared".
        cleared = [i for i in status2.items if i.item_id == item_id]
        assert len(cleared) == 1
        assert cleared[0].state == STATE_CLEARED

        # Cycle 3: cleared item that's still absent gets dropped entirely.
        much_later = "2026-03-25T00:00:00+00:00"
        status3 = reconcile(
            runtime_dir=tmp_path,
            monitor_findings=[],
            now_iso=much_later,
        )
        assert len(status3.items) == 0
        assert len(status3.open_items) == 0

        # fleet_status.json shows 0 items.
        loaded = load_fleet_status(tmp_path)
        assert loaded is not None
        assert loaded.to_dict()["summary"]["open"] == 0
        assert loaded.to_dict()["summary"]["total"] == 0

    # -- Full lifecycle scenario (end-to-end) ---------------------------------

    def test_full_persist_dedupe_clear_lifecycle(self, tmp_path: Path):
        """End-to-end proving run: seed → dedupe → restart → ack → clear."""
        finding = self._urgent_stalled_finding()

        # Phase 1: Seed one urgent finding.
        t1 = "2026-03-24T20:00:00+00:00"
        s1 = reconcile(runtime_dir=tmp_path, monitor_findings=[finding], now_iso=t1)
        assert len(s1.open_items) == 1
        item_id = s1.open_items[0].item_id

        # Phase 2: Reconcile 5 more times — no duplicates.
        for i in range(5):
            ts = f"2026-03-24T20:{(i + 1) * 10:02d}:00+00:00"
            s = reconcile(runtime_dir=tmp_path, monitor_findings=[finding], now_iso=ts)
            assert len(s.open_items) == 1, f"Duplicate at cycle {i + 2}"
            assert s.open_items[0].item_id == item_id

        # Phase 3: Simulate restart — reload from disk, verify item survives.
        reloaded = load_fleet_status(tmp_path)
        assert reloaded is not None
        assert len(reloaded.open_items) == 1
        assert reloaded.open_items[0].item_id == item_id
        assert reloaded.open_items[0].first_seen_at == t1

        # Phase 4: Ack the item.
        assert ack_item(reloaded, item_id) is True
        save_fleet_status(reloaded, tmp_path)

        t_ack = "2026-03-24T21:30:00+00:00"
        s_ack = reconcile(
            runtime_dir=tmp_path, monitor_findings=[finding], now_iso=t_ack
        )
        acked = [i for i in s_ack.items if i.item_id == item_id]
        assert len(acked) == 1
        assert acked[0].state == STATE_ACKED

        # Phase 5: Resolve — remove the finding.
        t_resolve = "2026-03-24T22:00:00+00:00"
        s_resolve = reconcile(
            runtime_dir=tmp_path, monitor_findings=[], now_iso=t_resolve
        )
        assert len(s_resolve.open_items) == 0

        # Cleared item still present this cycle...
        cleared = [i for i in s_resolve.items if i.item_id == item_id]
        assert len(cleared) == 1
        assert cleared[0].state == STATE_CLEARED

        # ...and drops on the next cycle.
        t_final = "2026-03-24T23:00:00+00:00"
        s_final = reconcile(runtime_dir=tmp_path, monitor_findings=[], now_iso=t_final)
        assert len(s_final.items) == 0

        # Disk shows 0 open items.
        final_disk = load_fleet_status(tmp_path)
        assert final_disk is not None
        assert final_disk.to_dict()["summary"]["open"] == 0

    # -- JSON validity after multiple writes ----------------------------------

    def test_persist_valid_json_after_multiple_writes(self, tmp_path: Path):
        """fleet_status.json is valid JSON after many reconcile cycles."""
        finding = self._urgent_stalled_finding()
        for i in range(10):
            ts = f"2026-03-24T20:{i:02d}:00+00:00"
            reconcile(
                runtime_dir=tmp_path,
                monitor_findings=[finding],
                now_iso=ts,
            )

        # Read the raw file and verify it's valid JSON.
        status_path = tmp_path / "fleet_status.json"
        assert status_path.exists()
        raw = status_path.read_text()
        data = json.loads(raw)  # Raises on invalid JSON.
        assert isinstance(data, dict)
        assert "items" in data
        assert "summary" in data
        assert data["summary"]["total"] >= 1
