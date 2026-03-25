"""Integration tests for SP-4-07 controller projection surfaces.

Tests three cross-module integration paths:

1. **Lifecycle** — reconcile() writes a projection that load_fleet_status()
   can read back with identical item data, cycle count, and timestamps.
2. **Alert pipeline** — an urgent bus message is sent, detected by the
   controller via items_from_unacked_messages(), surfaced in the projection,
   and then auto-cleared after ack.
3. **Remote exchange** — an inbound audit record surfaces an unanswered-
   message actionable item; a subsequent outbound reply clears it on the
   next reconcile cycle.

Closes #1683.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.audit_trail import (
    audit_channel_tag,
    audit_mcp_outbound,
    read_records,
)
from bid_euchre.ops.control_plane import (
    CAT_AUDIT_EXCHANGE,
    CAT_UNACKED_MESSAGE,
    SEVERITY_HIGH,
    SEVERITY_URGENT,
    STATE_CLEARED,
    STATE_OPEN,
    derive_items,
    items_from_unacked_messages,
    load_fleet_status,
    reconcile,
)
from bid_euchre.ops.message_bus import (
    create_message,
    read_inbox,
    send_message,
    shared_bus_root,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _old_urgent_message_dict(
    *,
    msg_id: str = "test-msg-001",
    from_lane: str = "author-b",
    to_lane: str = "orchestrator",
    summary: str = "CI broken on main — all PRs blocked",
    priority: str = "urgent",
    created_at: str = "2026-03-24T07:00:00+00:00",
) -> dict:
    """Construct an inbox message dict with an old created_at for age tests.

    ``items_from_unacked_messages`` uses wall-clock ``time.time()`` for age
    calculation, so freshly created messages won't exceed the default
    10-minute threshold. We fabricate a dict with a past timestamp to
    exercise the detection logic without sleeping.
    """
    return {
        "message_id": msg_id,
        "from_lane": from_lane,
        "to_lane": to_lane,
        "message_type": "blocker",
        "priority": priority,
        "status": "pending",
        "created_at": created_at,
        "summary": summary,
    }


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# 1. Lifecycle: reconcile → persist → reload
# ---------------------------------------------------------------------------


class TestReconcileLifecycle:
    """Prove the reconcile → projection write → projection read path."""

    def test_reconcile_persists_and_reloads(self, tmp_path: Path) -> None:
        """reconcile() writes fleet_status.json that load_fleet_status() reads back."""
        runtime_dir = tmp_path / "runtime"

        # Inject a monitor finding that will produce an actionable item.
        findings = [
            {
                "category": "pr_status",
                "severity": "warn",
                "summary": "PR #42 has merge conflicts",
                "details": {"pr_number": 42, "mergeable": "CONFLICTING"},
            },
        ]

        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            now_iso="2026-03-24T10:00:00+00:00",
        )

        # Verify in-memory result.
        assert status.cycle_count == 1
        assert len(status.items) == 1
        assert status.items[0].pr_number == 42
        assert status.items[0].state == STATE_OPEN

        # Reload from disk.
        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert reloaded.cycle_count == status.cycle_count
        assert reloaded.generated_at == status.generated_at
        assert len(reloaded.items) == len(status.items)

        # Compare item fields.
        original = status.items[0]
        restored = reloaded.items[0]
        assert restored.item_id == original.item_id
        assert restored.severity == original.severity
        assert restored.category == original.category
        assert restored.summary == original.summary
        assert restored.pr_number == original.pr_number
        assert restored.recommended_action == original.recommended_action

    def test_multi_cycle_increments_count(self, tmp_path: Path) -> None:
        """Consecutive reconcile cycles increment cycle_count."""
        runtime_dir = tmp_path / "runtime"

        for cycle in range(1, 4):
            status = reconcile(
                runtime_dir=runtime_dir,
                now_iso=f"2026-03-24T10:0{cycle}:00+00:00",
            )
            assert status.cycle_count == cycle

    def test_merge_preserves_first_seen_at(self, tmp_path: Path) -> None:
        """An item present across cycles retains its original first_seen_at."""
        runtime_dir = tmp_path / "runtime"
        findings = [
            {
                "category": "stalled_lane",
                "severity": "high",
                "summary": "Lane author-a stalled",
                "details": {"lane_id": "author-a"},
            },
        ]

        # Cycle 1 — item first appears.
        s1 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            now_iso="2026-03-24T10:00:00+00:00",
        )
        first_seen = s1.items[0].first_seen_at

        # Cycle 2 — same item still present.
        s2 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            now_iso="2026-03-24T10:05:00+00:00",
        )

        assert len(s2.items) >= 1
        # Find the same item by id.
        matching = [i for i in s2.items if i.item_id == s1.items[0].item_id]
        assert len(matching) == 1
        assert matching[0].first_seen_at == first_seen
        assert matching[0].last_seen_at == "2026-03-24T10:05:00+00:00"

    def test_resolved_item_auto_clears(self, tmp_path: Path) -> None:
        """An item that disappears from findings is auto-cleared on next cycle."""
        runtime_dir = tmp_path / "runtime"
        findings = [
            {
                "category": "pr_status",
                "severity": "warn",
                "summary": "PR #99 failing CI",
                "details": {"pr_number": 99},
            },
        ]

        # Cycle 1 — item appears.
        reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=findings,
            now_iso="2026-03-24T10:00:00+00:00",
        )

        # Cycle 2 — no findings (issue resolved).
        s2 = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=[],
            now_iso="2026-03-24T10:05:00+00:00",
        )

        cleared = [i for i in s2.items if i.state == STATE_CLEARED]
        assert len(cleared) == 1
        assert cleared[0].pr_number == 99


# ---------------------------------------------------------------------------
# 2. Alert pipeline: urgent bus message → controller detection → projection
# ---------------------------------------------------------------------------


class TestAlertPipeline:
    """Prove urgent bus messages are detected and surfaced in the projection.

    Note: ``items_from_unacked_messages`` uses wall-clock ``time.time()`` for
    age calculation, so freshly-created bus messages won't exceed the default
    10-minute threshold. These tests use fabricated message dicts with old
    ``created_at`` timestamps to exercise the full detection pipeline without
    sleeping or monkey-patching the clock.
    """

    def test_urgent_message_surfaces_in_projection(self, tmp_path: Path) -> None:
        """An unacked urgent message is surfaced as an actionable item."""
        runtime_dir = tmp_path / "runtime"

        # 1. Fabricate an urgent message dict with a timestamp old enough
        #    to exceed the default 10-minute age threshold.
        msg_dict = _old_urgent_message_dict(
            msg_id="urgent-001",
            summary="CI broken on main — all PRs blocked",
            priority="urgent",
            created_at="2026-03-24T07:00:00+00:00",
        )

        # 2. Controller detects the unacked urgent message.
        items = items_from_unacked_messages(
            [msg_dict],
            now_iso="2026-03-24T08:00:00+00:00",
        )
        urgent_items = [i for i in items if i.severity == SEVERITY_URGENT]
        assert len(urgent_items) >= 1
        assert any("CI broken" in i.summary for i in urgent_items)
        assert urgent_items[0].category == CAT_UNACKED_MESSAGE

        # 3. Feed to reconcile via derive_items to verify persistence.
        #    Use derive_items directly since reconcile calls it internally.
        all_items = derive_items(
            unacked_messages=[msg_dict],
            now_iso="2026-03-24T08:00:00+00:00",
            unacked_message_age_minutes=0,  # bypass wall-clock check
        )
        assert any(i.severity == SEVERITY_URGENT for i in all_items)

        # 4. Verify reconcile persists the item (using age_minutes=0 workaround:
        #    pass the item as a monitor finding instead).
        status = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=[msg_dict],
            now_iso="2026-03-24T08:00:00+00:00",
        )
        # The message has an old created_at so it should be detected.
        open_urgent = [
            i
            for i in status.items
            if i.severity == SEVERITY_URGENT and i.state == STATE_OPEN
        ]
        assert len(open_urgent) >= 1

        # 5. Verify the projection can be reloaded.
        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert len(reloaded.urgent_items) >= 1

    def test_high_priority_message_detected(self) -> None:
        """A high-priority unacked message surfaces as a high-severity item."""
        msg_dict = _old_urgent_message_dict(
            msg_id="high-001",
            from_lane="author-c",
            summary="Review stalled — needs manual approval",
            priority="high",
            created_at="2026-03-24T07:00:00+00:00",
        )

        items = items_from_unacked_messages(
            [msg_dict],
            now_iso="2026-03-24T08:00:00+00:00",
        )
        high_items = [i for i in items if i.severity == SEVERITY_HIGH]
        assert len(high_items) >= 1
        assert any("Review stalled" in i.summary for i in high_items)

    def test_acked_message_clears_from_projection(self, tmp_path: Path) -> None:
        """An item from an urgent message is auto-cleared when the message disappears."""
        runtime_dir = tmp_path / "runtime"

        # Fabricate an old urgent message.
        msg_dict = _old_urgent_message_dict(
            msg_id="ack-test-001",
            summary="Worktree corrupted",
            priority="urgent",
            created_at="2026-03-24T07:00:00+00:00",
        )

        # Cycle 1: message detected in projection.
        s1 = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=[msg_dict],
            now_iso="2026-03-24T08:00:00+00:00",
        )
        assert len(s1.urgent_items) >= 1

        # Cycle 2: message has been acked (no longer in unacked list).
        s2 = reconcile(
            runtime_dir=runtime_dir,
            unacked_messages=[],
            now_iso="2026-03-24T08:05:00+00:00",
        )

        # The urgent item should be auto-cleared.
        still_urgent = [
            i
            for i in s2.items
            if i.category == CAT_UNACKED_MESSAGE and i.state == STATE_OPEN
        ]
        assert len(still_urgent) == 0

        # Verify the cleared item is retained for audit.
        cleared = [
            i
            for i in s2.items
            if i.category == CAT_UNACKED_MESSAGE and i.state == STATE_CLEARED
        ]
        assert len(cleared) == 1

    def test_bus_send_then_detect_end_to_end(self, tmp_path: Path) -> None:
        """Full E2E: send via bus → read inbox → detect with age_minutes=0."""
        bus_root_dir = tmp_path / "bus"
        events_dir = tmp_path / "events"
        events_dir.mkdir()

        root = shared_bus_root(bus_root_dir)

        # Send an urgent message via the real bus.
        msg = create_message(
            from_lane="author-d",
            to_lane="orchestrator",
            message_type="blocker",
            summary="Disk full on build machine",
            priority="urgent",
            task_id="packet-888",
        )
        msg_id = send_message(msg, bus_root=root, events_dir=events_dir)

        # Read the inbox — message arrives.
        inbox = read_inbox(
            "orchestrator",
            bus_root=root,
            auto_expire=False,
            auto_compact=False,
        )
        assert any(m["message_id"] == msg_id for m in inbox)

        # Detect with max_age_minutes=0 (fresh message is still detected).
        items = items_from_unacked_messages(
            inbox,
            now_iso="2026-03-24T08:00:00+00:00",
            max_age_minutes=0,
        )
        urgent = [i for i in items if i.severity == SEVERITY_URGENT]
        assert len(urgent) >= 1
        assert "Disk full" in urgent[0].summary


# ---------------------------------------------------------------------------
# 3. Remote exchange: audit inbound → projection → outbound clears it
# ---------------------------------------------------------------------------


class TestRemoteExchangeProjection:
    """Prove inbound/outbound audit records flow through the projection correctly."""

    def test_unanswered_inbound_surfaces_and_reply_clears(self, tmp_path: Path) -> None:
        """Full E2E: inbound audit → projection item → outbound reply → cleared."""
        audit_dir = tmp_path / "audit"
        runtime_dir = tmp_path / "runtime"

        # 1. Inbound message arrives via channel tag.
        tag = (
            '<channel source="telegram" chat_id="999" '
            'message_id="200" user="operator" ts="2026-03-24T07:00:00Z">'
        )
        audit_channel_tag(tag_text=tag, content="Fleet status?", audit_dir=audit_dir)

        # 2. Read audit records and feed to reconcile.
        records = read_records(audit_dir=audit_dir)
        assert len(records) == 1
        record_dicts = [r.to_dict() for r in records]

        s1 = reconcile(
            runtime_dir=runtime_dir,
            audit_records=record_dicts,
            now_iso="2026-03-24T08:00:00+00:00",  # 60 min later
        )

        # Verify the unanswered inbound is surfaced.
        audit_items = [i for i in s1.items if i.category == CAT_AUDIT_EXCHANGE]
        assert len(audit_items) == 1
        assert audit_items[0].state == STATE_OPEN
        assert "operator" in audit_items[0].summary

        # 3. Outbound reply is sent.
        audit_mcp_outbound(
            tool_name="mcp__plugin_telegram_telegram__reply",
            tool_args={
                "chat_id": "999",
                "body": "All 12 lanes nominal.",
                "reply_to": "200",
            },
            audit_dir=audit_dir,
        )

        # 4. Second reconcile cycle with updated audit records.
        records_2 = read_records(audit_dir=audit_dir)
        assert len(records_2) == 2
        record_dicts_2 = [r.to_dict() for r in records_2]

        s2 = reconcile(
            runtime_dir=runtime_dir,
            audit_records=record_dicts_2,
            now_iso="2026-03-24T08:05:00+00:00",
        )

        # The audit item should be cleared — the reply answered the inbound.
        open_audit = [
            i
            for i in s2.items
            if i.category == CAT_AUDIT_EXCHANGE and i.state == STATE_OPEN
        ]
        assert len(open_audit) == 0

    def test_multi_chat_isolation(self, tmp_path: Path) -> None:
        """Unanswered detection is per-chat — answering chat A leaves chat B open."""
        audit_dir = tmp_path / "audit"
        runtime_dir = tmp_path / "runtime"

        # Chat A: inbound
        tag_a = (
            '<channel source="telegram" chat_id="AAA" '
            'message_id="1" user="alice" ts="2026-03-24T07:00:00Z">'
        )
        audit_channel_tag(tag_text=tag_a, content="Hello from A", audit_dir=audit_dir)

        # Chat B: inbound
        tag_b = (
            '<channel source="telegram" chat_id="BBB" '
            'message_id="2" user="bob" ts="2026-03-24T07:00:00Z">'
        )
        audit_channel_tag(tag_text=tag_b, content="Hello from B", audit_dir=audit_dir)

        # Reply to Chat A only.
        audit_mcp_outbound(
            tool_name="mcp__plugin_telegram_telegram__reply",
            tool_args={"chat_id": "AAA", "body": "Hi Alice!", "reply_to": "1"},
            audit_dir=audit_dir,
        )

        # Reconcile — chat B should still be unanswered.
        records = read_records(audit_dir=audit_dir)
        record_dicts = [r.to_dict() for r in records]

        status = reconcile(
            runtime_dir=runtime_dir,
            audit_records=record_dicts,
            now_iso="2026-03-24T08:00:00+00:00",
        )

        open_audit = [
            i
            for i in status.items
            if i.category == CAT_AUDIT_EXCHANGE and i.state == STATE_OPEN
        ]
        assert len(open_audit) == 1
        assert open_audit[0].details["chat_id"] == "BBB"

    def test_combined_sources_in_single_reconcile(self, tmp_path: Path) -> None:
        """reconcile() merges items from monitor findings, bus messages, and audit."""
        audit_dir = tmp_path / "audit"
        runtime_dir = tmp_path / "runtime"

        # Source 1: monitor finding.
        monitor = [
            {
                "category": "pr_status",
                "severity": "warn",
                "summary": "PR #10 failing CI",
                "details": {"pr_number": 10},
            },
        ]

        # Source 2: fabricated old urgent bus message (bypasses wall-clock age).
        old_msg = _old_urgent_message_dict(
            msg_id="combined-001",
            from_lane="author-d",
            summary="Disk full",
            priority="urgent",
            created_at="2026-03-24T07:00:00+00:00",
        )

        # Source 3: audit inbound.
        tag = (
            '<channel source="telegram" chat_id="777" '
            'message_id="50" user="ops" ts="2026-03-24T07:00:00Z">'
        )
        audit_channel_tag(tag_text=tag, content="Check deploy", audit_dir=audit_dir)
        records = read_records(audit_dir=audit_dir)
        record_dicts = [r.to_dict() for r in records]

        # Reconcile with all three sources.
        now_iso = "2026-03-24T08:00:00+00:00"
        status = reconcile(
            runtime_dir=runtime_dir,
            monitor_findings=monitor,
            unacked_messages=[old_msg],
            audit_records=record_dicts,
            now_iso=now_iso,
        )

        # Verify items from each source are present.
        categories = {i.category for i in status.items if i.state == STATE_OPEN}
        assert "pr_status" in categories
        assert CAT_UNACKED_MESSAGE in categories
        assert CAT_AUDIT_EXCHANGE in categories

        # Verify total count — at least 3 items.
        assert len(status.open_items) >= 3

        # Verify the projection round-trips via persistence.
        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert len(reloaded.items) == len(status.items)
