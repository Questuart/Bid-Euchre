"""Integration tests for the full remote ack loop (Platform-9a, PR 4).

Proves the end-to-end path from an inbound Telegram message through the ack
parser, controller mutation, confirmation formatting, and audit trail — the
complete inbound half of the remote alert lifecycle.

Test paths:

1. **Inbound ack mutates controller** — a simulated inbound ``ack <prefix>``
   message is parsed, the matching item's state changes to ``acked`` in the
   persisted fleet status, a confirmation message is formatted, and both
   the inbound command and outbound confirmation are recorded in the audit
   trail.

2. **Non-command passthrough** — a free-form Telegram message is parsed,
   returns ``None`` from the ack parser, and does NOT mutate the controller
   projection.

3. **Error paths** — ambiguous prefix, no match, already-acked item all
   produce error confirmations and leave the projection unchanged.

4. **Suppress/clear variants** — ``mute`` and ``clear`` commands go through
   the same loop and produce the correct controller mutations.

5. **Round-trip persistence** — mutations survive a save/reload cycle via
   ``save_fleet_status()`` / ``load_fleet_status()``.

Exit criteria (from sub-plan):
- Inbound ack commands correctly mutate controller state
- Non-command messages pass through unchanged
- Confirmation reply sent after successful ack
- Both directions audited
- Full loop proven in integration test
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bid_euchre.ops.audit_trail import (
    audit_channel_tag,
    audit_reply,
    read_records,
)
from bid_euchre.ops.control_plane import (
    SEVERITY_HIGH,
    SEVERITY_URGENT,
    STATE_ACKED,
    STATE_CLEARED,
    STATE_OPEN,
    STATE_SUPPRESSED,
    ActionableItem,
    FleetStatus,
    load_fleet_status,
    save_fleet_status,
)
from bid_euchre.ops.remote_ack import (
    execute_remote_ack,
    format_ack_confirmation,
    parse_ack_command,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CHAT_ID = "test-chat-999"
FIXED_TS = "2026-03-25T12:00:00+00:00"


def _make_item(
    item_id: str = "abc123def456",
    severity: str = SEVERITY_HIGH,
    state: str = STATE_OPEN,
    summary: str = "Approval stall on author-b",
) -> ActionableItem:
    """Create a test ActionableItem."""
    return ActionableItem(
        item_id=item_id,
        severity=severity,
        category="approval_stall",
        source="monitor",
        summary=summary,
        first_seen_at="2026-03-25T11:00:00+00:00",
        last_seen_at="2026-03-25T11:55:00+00:00",
        state=state,
    )


def _make_fleet_status(*items: ActionableItem) -> FleetStatus:
    """Create a FleetStatus with the given items."""
    return FleetStatus(
        items=list(items),
        generated_at="2026-03-25T11:55:00+00:00",
        cycle_count=5,
    )


def _simulate_inbound_ack(
    text: str,
    fleet_status: FleetStatus,
    audit_dir: Path,
) -> dict:
    """Simulate the full inbound ack pipeline.

    Mirrors the orchestrator's handling of an inbound Telegram message:
    1. Audit the inbound message.
    2. Parse the ack command.
    3. If it's a command: execute, format confirmation, audit confirmation.
    4. If not a command: return passthrough indicator.

    Returns a dict with:
      - parsed: the AckCommand or None
      - result: the AckResult or None
      - confirmation_text: the formatted reply text or None
      - is_passthrough: True if the message was not a command
    """
    # Step 1: Audit the inbound message (as the inbound hook would).
    tag_text = (
        f'<channel source="telegram" chat_id="{CHAT_ID}" '
        f'message_id="42" user="operator" ts="{FIXED_TS}">'
    )
    audit_channel_tag(tag_text, text, audit_dir=audit_dir)

    # Step 2: Parse the ack command.
    cmd = parse_ack_command(text)
    if cmd is None:
        return {
            "parsed": None,
            "result": None,
            "confirmation_text": None,
            "is_passthrough": True,
        }

    # Step 3: Execute the remote ack against the fleet status.
    ack_result = execute_remote_ack(cmd, fleet_status)

    # Step 4: Format the confirmation.
    confirmation_text = format_ack_confirmation(ack_result)

    # Step 5: Audit the outbound confirmation reply.
    audit_reply(
        chat_id=CHAT_ID,
        body=confirmation_text,
        audit_dir=audit_dir,
        timestamp=FIXED_TS,
    )

    return {
        "parsed": cmd,
        "result": ack_result,
        "confirmation_text": confirmation_text,
        "is_passthrough": False,
    }


# ===========================================================================
# 1. Full ack loop — inbound ack mutates controller, confirmation, audit
# ===========================================================================


class TestInboundAckLoop:
    """Prove the complete inbound ack → mutate → confirm → audit path."""

    def test_ack_mutates_controller_and_persists(self, tmp_path: Path) -> None:
        """Inbound 'ack <prefix>' mutates the item state and survives persistence."""
        audit_dir = tmp_path / "audit_trail"
        runtime_dir = tmp_path / "runtime"

        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        # Save initial state.
        save_fleet_status(status, runtime_dir=runtime_dir)

        # Simulate inbound ack.
        outcome = _simulate_inbound_ack("ack abc1", status, audit_dir)

        assert outcome["is_passthrough"] is False
        assert outcome["result"].success is True
        assert outcome["result"].item_id == "abc123def456"
        assert item.state == STATE_ACKED

        # Persist the mutated status and reload.
        save_fleet_status(status, runtime_dir=runtime_dir)
        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None

        acked_items = [i for i in reloaded.items if i.state == STATE_ACKED]
        assert len(acked_items) == 1
        assert acked_items[0].item_id == "abc123def456"

    def test_confirmation_message_content(self, tmp_path: Path) -> None:
        """Confirmation includes checkmark and item summary."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(
            item_id="abc123def456",
            summary="Approval stall on author-b",
        )
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("ack abc1", status, audit_dir)

        assert "\u2705" in outcome["confirmation_text"]  # checkmark
        assert "Approval stall" in outcome["confirmation_text"]

    def test_audit_records_both_directions(self, tmp_path: Path) -> None:
        """Both inbound command and outbound confirmation are audited."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        _simulate_inbound_ack("ack abc1", status, audit_dir)

        records = read_records(audit_dir=audit_dir)
        assert len(records) == 2

        inbound = [r for r in records if r.direction == "inbound"]
        outbound = [r for r in records if r.direction == "outbound"]

        assert len(inbound) == 1
        assert len(outbound) == 1

        # Inbound record captures the command text.
        assert "ack abc1" in inbound[0].content_preview
        assert inbound[0].chat_id == CHAT_ID
        assert inbound[0].sender_identity == "operator"
        assert inbound[0].exchange_type == "message"

        # Outbound record captures the confirmation.
        assert "\u2705" in outbound[0].content_preview
        assert outbound[0].chat_id == CHAT_ID
        assert outbound[0].exchange_type == "reply"

    def test_ack_urgent_item(self, tmp_path: Path) -> None:
        """Acking an URGENT item works the same as HIGH."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(
            item_id="def999aaa000",
            severity=SEVERITY_URGENT,
            summary="CI broken on main",
        )
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("ack def9", status, audit_dir)

        assert outcome["result"].success is True
        assert item.state == STATE_ACKED


# ===========================================================================
# 2. Non-command passthrough
# ===========================================================================


class TestNonCommandPassthrough:
    """Non-command messages pass through without mutating controller."""

    def test_freeform_message_passthrough(self, tmp_path: Path) -> None:
        """Free-form message returns passthrough, item state unchanged."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("How's the fleet doing?", status, audit_dir)

        assert outcome["is_passthrough"] is True
        assert outcome["parsed"] is None
        assert outcome["result"] is None
        assert item.state == STATE_OPEN

    def test_passthrough_still_audits_inbound(self, tmp_path: Path) -> None:
        """Passthrough messages are still audited as inbound."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item()
        status = _make_fleet_status(item)

        _simulate_inbound_ack("What's happening?", status, audit_dir)

        records = read_records(audit_dir=audit_dir)
        # Only inbound, no outbound confirmation.
        assert len(records) == 1
        assert records[0].direction == "inbound"
        assert "What's happening?" in records[0].content_preview


# ===========================================================================
# 3. Error paths
# ===========================================================================


class TestErrorPaths:
    """Error paths produce error confirmations, do not mutate controller."""

    def test_no_matching_item(self, tmp_path: Path) -> None:
        """Ack with non-matching prefix produces error, state unchanged."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("ack fff000", status, audit_dir)

        assert outcome["result"].success is False
        assert "No item matching prefix" in outcome["result"].message
        assert "\u274c" in outcome["confirmation_text"]
        assert item.state == STATE_OPEN

    def test_ambiguous_prefix(self, tmp_path: Path) -> None:
        """Ambiguous prefix produces error with candidate list."""
        audit_dir = tmp_path / "audit_trail"
        item1 = _make_item(item_id="abc123000000", summary="Item 1")
        item2 = _make_item(item_id="abc123ffffff", summary="Item 2")
        status = _make_fleet_status(item1, item2)

        outcome = _simulate_inbound_ack("ack abc123", status, audit_dir)

        assert outcome["result"].success is False
        assert "Ambiguous" in outcome["result"].message
        assert outcome["result"].candidates is not None
        assert len(outcome["result"].candidates) == 2
        assert "Candidates:" in outcome["confirmation_text"]

        # Neither item mutated.
        assert item1.state == STATE_OPEN
        assert item2.state == STATE_OPEN

    def test_already_acked_item(self, tmp_path: Path) -> None:
        """Acking an already-acked item produces error confirmation."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456", state=STATE_ACKED)
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("ack abc1", status, audit_dir)

        assert outcome["result"].success is False
        assert "\u274c" in outcome["confirmation_text"]
        assert "cannot be" in outcome["result"].message

    def test_error_path_still_audits_both_directions(self, tmp_path: Path) -> None:
        """Error acks are still fully audited (inbound + outbound)."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        _simulate_inbound_ack("ack fff000", status, audit_dir)

        records = read_records(audit_dir=audit_dir)
        assert len(records) == 2
        directions = {r.direction for r in records}
        assert directions == {"inbound", "outbound"}


# ===========================================================================
# 4. Suppress and clear variants
# ===========================================================================


class TestSuppressAndClearVariants:
    """Mute and clear commands go through the same loop correctly."""

    def test_mute_via_full_loop(self, tmp_path: Path) -> None:
        """Inbound 'mute <prefix>' suppresses the item."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("mute abc1", status, audit_dir)

        assert outcome["result"].success is True
        assert item.state == STATE_SUPPRESSED
        assert "\u2705" in outcome["confirmation_text"]

    def test_dismiss_via_full_loop(self, tmp_path: Path) -> None:
        """Inbound 'dismiss <prefix>' suppresses the item."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("dismiss abc1", status, audit_dir)

        assert outcome["result"].success is True
        assert item.state == STATE_SUPPRESSED

    def test_clear_via_full_loop(self, tmp_path: Path) -> None:
        """Inbound 'clear <prefix>' clears the item."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("clear abc1", status, audit_dir)

        assert outcome["result"].success is True
        assert item.state == STATE_CLEARED
        assert "\u2705" in outcome["confirmation_text"]

    def test_case_insensitive_command(self, tmp_path: Path) -> None:
        """Commands are case-insensitive through the full loop."""
        audit_dir = tmp_path / "audit_trail"
        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)

        outcome = _simulate_inbound_ack("ACK ABC1", status, audit_dir)

        assert outcome["result"].success is True
        assert item.state == STATE_ACKED


# ===========================================================================
# 5. Round-trip persistence
# ===========================================================================


class TestRoundTripPersistence:
    """Mutations survive a save/reload cycle."""

    def test_ack_then_reload(self, tmp_path: Path) -> None:
        """Acked state persists through save + load."""
        audit_dir = tmp_path / "audit_trail"
        runtime_dir = tmp_path / "runtime"

        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)
        save_fleet_status(status, runtime_dir=runtime_dir)

        _simulate_inbound_ack("ack abc1", status, audit_dir)
        save_fleet_status(status, runtime_dir=runtime_dir)

        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert len(reloaded.items) == 1
        assert reloaded.items[0].state == STATE_ACKED
        assert reloaded.items[0].item_id == "abc123def456"

    def test_suppress_then_reload(self, tmp_path: Path) -> None:
        """Suppressed state persists through save + load."""
        audit_dir = tmp_path / "audit_trail"
        runtime_dir = tmp_path / "runtime"

        item = _make_item(item_id="abc123def456")
        status = _make_fleet_status(item)
        save_fleet_status(status, runtime_dir=runtime_dir)

        _simulate_inbound_ack("mute abc1", status, audit_dir)
        save_fleet_status(status, runtime_dir=runtime_dir)

        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        assert reloaded.items[0].state == STATE_SUPPRESSED

    def test_multiple_items_selective_ack(self, tmp_path: Path) -> None:
        """Acking one item preserves the other items' states."""
        audit_dir = tmp_path / "audit_trail"
        runtime_dir = tmp_path / "runtime"

        item1 = _make_item(item_id="aaa111000000", summary="Item 1")
        item2 = _make_item(item_id="bbb222000000", summary="Item 2")
        item3 = _make_item(item_id="ccc333000000", summary="Item 3")
        status = _make_fleet_status(item1, item2, item3)
        save_fleet_status(status, runtime_dir=runtime_dir)

        # Ack only item2.
        _simulate_inbound_ack("ack bbb2", status, audit_dir)
        save_fleet_status(status, runtime_dir=runtime_dir)

        reloaded = load_fleet_status(runtime_dir)
        assert reloaded is not None
        states = {i.item_id: i.state for i in reloaded.items}
        assert states["aaa111000000"] == STATE_OPEN
        assert states["bbb222000000"] == STATE_ACKED
        assert states["ccc333000000"] == STATE_OPEN
