"""Tests for remote ack parser and controller mutation (Platform-9a, PR 2).

Covers:
- Parse valid commands with various prefix lengths
- Parse case-insensitive variants
- Reject non-command messages (return None)
- Execute ack on matching item -> state changes to 'acked'
- Execute suppress (dismiss/mute) on matching item -> state changes to 'suppressed'
- Execute clear on matching item -> state changes to 'cleared'
- Ambiguous prefix -> error result with candidate list
- No matching item -> error result
- Item already acked -> error result (idempotency note)
- Confirmation formatting for success, error, and ambiguous results
"""

from __future__ import annotations

from bid_euchre.ops.control_plane import (
    STATE_ACKED,
    STATE_CLEARED,
    STATE_OPEN,
    STATE_SUPPRESSED,
    ActionableItem,
    FleetStatus,
)
from bid_euchre.ops.remote_ack import (
    AckAction,
    AckCommand,
    AckResult,
    execute_remote_ack,
    format_ack_confirmation,
    parse_ack_command,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    item_id: str = "abc123def456",
    severity: str = "high",
    state: str = STATE_OPEN,
    summary: str = "Test alert on author-b",
) -> ActionableItem:
    return ActionableItem(
        item_id=item_id,
        severity=severity,
        category="lane_health",
        source="monitor",
        summary=summary,
        first_seen_at="2026-03-25T00:00:00Z",
        last_seen_at="2026-03-25T00:00:00Z",
        state=state,
    )


def _make_status(*items: ActionableItem) -> FleetStatus:
    return FleetStatus(
        items=list(items),
        generated_at="2026-03-25T00:00:00Z",
        cycle_count=1,
    )


# ===================================================================
# Parsing tests
# ===================================================================


class TestParseAckCommand:
    """Tests for parse_ack_command()."""

    def test_parse_ack(self) -> None:
        cmd = parse_ack_command("ack abc123")
        assert cmd is not None
        assert cmd.action == AckAction.ACK
        assert cmd.prefix == "abc123"

    def test_parse_dismiss(self) -> None:
        cmd = parse_ack_command("dismiss abc123")
        assert cmd is not None
        assert cmd.action == AckAction.DISMISS
        assert cmd.prefix == "abc123"

    def test_parse_mute(self) -> None:
        cmd = parse_ack_command("mute abc123")
        assert cmd is not None
        assert cmd.action == AckAction.MUTE
        assert cmd.prefix == "abc123"

    def test_parse_clear(self) -> None:
        cmd = parse_ack_command("clear abc123")
        assert cmd is not None
        assert cmd.action == AckAction.CLEAR
        assert cmd.prefix == "abc123"

    def test_parse_short_prefix(self) -> None:
        """Short prefix (4 chars) is valid."""
        cmd = parse_ack_command("ack abc1")
        assert cmd is not None
        assert cmd.prefix == "abc1"

    def test_parse_full_12_char_id(self) -> None:
        """Full 12-char item_id is valid."""
        cmd = parse_ack_command("ack abc123def456")
        assert cmd is not None
        assert cmd.prefix == "abc123def456"

    def test_parse_case_insensitive_action(self) -> None:
        """Action keyword is case-insensitive."""
        for text in ["ACK abc1", "Ack abc1", "aCk abc1"]:
            cmd = parse_ack_command(text)
            assert cmd is not None, f"Failed to parse: {text!r}"
            assert cmd.action == AckAction.ACK

    def test_parse_case_insensitive_prefix(self) -> None:
        """Hex prefix is normalized to lowercase."""
        cmd = parse_ack_command("ack ABC123DEF")
        assert cmd is not None
        assert cmd.prefix == "abc123def"

    def test_parse_leading_whitespace(self) -> None:
        cmd = parse_ack_command("  ack abc1")
        assert cmd is not None
        assert cmd.action == AckAction.ACK

    def test_parse_trailing_whitespace(self) -> None:
        cmd = parse_ack_command("ack abc1   ")
        assert cmd is not None
        assert cmd.prefix == "abc1"

    def test_parse_extra_inner_whitespace(self) -> None:
        """Multiple spaces between action and prefix."""
        cmd = parse_ack_command("ack   abc1")
        assert cmd is not None
        assert cmd.prefix == "abc1"

    def test_reject_non_command_messages(self) -> None:
        """Non-command messages return None (passthrough)."""
        non_commands = [
            "hello",
            "how's the fleet doing?",
            "acknowledged",
            "ack",  # no prefix
            "ack ",  # no prefix (trailing space)
            "ack abc xyz",  # extra words
            "please ack abc1",  # prefix before action
            "123 ack",  # reversed order
            "",
            " ",
        ]
        for text in non_commands:
            result = parse_ack_command(text)
            assert result is None, f"Should have rejected: {text!r}"

    def test_reject_non_hex_prefix(self) -> None:
        """Prefix must be hex characters only."""
        non_hex = [
            "ack xyz123",  # non-hex letters
            "ack hello",
            "ack 12-34",  # dash
            "ack 12_34",  # underscore
        ]
        for text in non_hex:
            result = parse_ack_command(text)
            assert result is None, f"Should have rejected non-hex: {text!r}"


# ===================================================================
# Execution tests
# ===================================================================


class TestExecuteRemoteAck:
    """Tests for execute_remote_ack()."""

    def test_ack_matching_item(self) -> None:
        """Ack with matching prefix changes state to acked."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.ACK, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert result.action == AckAction.ACK
        assert result.item_id == "abc123def456"
        assert result.summary == "Test alert on author-b"
        assert item.state == STATE_ACKED

    def test_dismiss_matching_item(self) -> None:
        """Dismiss changes state to suppressed."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.DISMISS, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert result.action == AckAction.DISMISS
        assert item.state == STATE_SUPPRESSED

    def test_mute_matching_item(self) -> None:
        """Mute changes state to suppressed (same as dismiss)."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.MUTE, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert result.action == AckAction.MUTE
        assert item.state == STATE_SUPPRESSED

    def test_clear_matching_item(self) -> None:
        """Clear changes state to cleared."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.CLEAR, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert result.action == AckAction.CLEAR
        assert item.state == STATE_CLEARED

    def test_no_matching_item(self) -> None:
        """No item matching prefix -> error result."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.ACK, prefix="fff")

        result = execute_remote_ack(cmd, status)

        assert result.success is False
        assert "No item matching prefix" in result.message
        assert result.item_id is None
        assert result.candidates is None

    def test_ambiguous_prefix(self) -> None:
        """Ambiguous prefix -> error result with candidate list."""
        item1 = _make_item(item_id="abc123000000", summary="Item 1")
        item2 = _make_item(item_id="abc123ffffff", summary="Item 2")
        status = _make_status(item1, item2)
        cmd = AckCommand(action=AckAction.ACK, prefix="abc123")

        result = execute_remote_ack(cmd, status)

        assert result.success is False
        assert "Ambiguous prefix" in result.message
        assert result.candidates is not None
        assert len(result.candidates) == 2
        assert "abc123000000" in result.candidates
        assert "abc123ffffff" in result.candidates

    def test_already_acked_item(self) -> None:
        """Acking an already-acked item -> error result."""
        item = _make_item(item_id="abc123def456", state=STATE_ACKED)
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.ACK, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is False
        assert result.item_id == "abc123def456"
        assert "cannot be" in result.message
        assert "acked" in result.message.lower() or "already" in result.message.lower()

    def test_already_suppressed_item(self) -> None:
        """Muting an already-suppressed item -> error result."""
        item = _make_item(item_id="abc123def456", state=STATE_SUPPRESSED)
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.MUTE, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is False
        assert result.item_id == "abc123def456"

    def test_already_cleared_item(self) -> None:
        """Clearing an already-cleared item -> error result."""
        item = _make_item(item_id="abc123def456", state=STATE_CLEARED)
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.CLEAR, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is False
        assert result.item_id == "abc123def456"

    def test_exact_match_with_full_id(self) -> None:
        """Full 12-char item_id as prefix matches exactly."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.ACK, prefix="abc123def456")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert result.item_id == "abc123def456"

    def test_multiple_items_unique_prefix(self) -> None:
        """Multiple items but unique prefix -> correct match."""
        item1 = _make_item(item_id="abc123000000", summary="Item A")
        item2 = _make_item(item_id="def456000000", summary="Item B")
        status = _make_status(item1, item2)
        cmd = AckCommand(action=AckAction.ACK, prefix="def4")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert result.item_id == "def456000000"
        assert result.summary == "Item B"
        assert item2.state == STATE_ACKED
        # item1 unchanged
        assert item1.state == STATE_OPEN

    def test_clear_acked_item(self) -> None:
        """Clearing an acked item succeeds (acked -> cleared)."""
        item = _make_item(item_id="abc123def456", state=STATE_ACKED)
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.CLEAR, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert item.state == STATE_CLEARED

    def test_suppress_acked_item(self) -> None:
        """Suppressing an acked item succeeds (acked -> suppressed)."""
        item = _make_item(item_id="abc123def456", state=STATE_ACKED)
        status = _make_status(item)
        cmd = AckCommand(action=AckAction.DISMISS, prefix="abc1")

        result = execute_remote_ack(cmd, status)

        assert result.success is True
        assert item.state == STATE_SUPPRESSED


# ===================================================================
# Confirmation formatting tests
# ===================================================================


class TestFormatAckConfirmation:
    """Tests for format_ack_confirmation()."""

    def test_success_message(self) -> None:
        """Successful ack produces a checkmark message."""
        result = AckResult(
            success=True,
            action=AckAction.ACK,
            item_id="abc123def456",
            summary="Approval stall on author-b",
            message="Acknowledged item abc123de -- Approval stall on author-b",
        )
        text = format_ack_confirmation(result)
        assert "\u2705" in text  # checkmark
        assert "abc123de" in text

    def test_error_message_no_match(self) -> None:
        """No-match error produces a cross-mark message."""
        result = AckResult(
            success=False,
            action=AckAction.ACK,
            message="No item matching prefix 'fff'",
        )
        text = format_ack_confirmation(result)
        assert "\u274c" in text  # cross mark
        assert "No item" in text

    def test_ambiguous_message_shows_candidates(self) -> None:
        """Ambiguous prefix shows candidate list."""
        result = AckResult(
            success=False,
            action=AckAction.ACK,
            message="Ambiguous prefix 'abc1' -- matches 2 items.",
            candidates=["abc123000000", "abc123ffffff"],
        )
        text = format_ack_confirmation(result)
        assert "\u274c" in text
        assert "Candidates:" in text
        assert "abc12300" in text
        assert "abc123ff" in text

    def test_already_acked_message(self) -> None:
        """Already-acked error produces a cross-mark message."""
        result = AckResult(
            success=False,
            action=AckAction.ACK,
            item_id="abc123def456",
            summary="Some alert",
            message="Item abc123de exists but cannot be ackd",
        )
        text = format_ack_confirmation(result)
        assert "\u274c" in text
        assert "cannot be" in text


# ===================================================================
# Integration-style: parse + execute round-trip
# ===================================================================


class TestParseAndExecuteRoundTrip:
    """End-to-end parse -> execute -> format round-trips."""

    def test_full_ack_round_trip(self) -> None:
        """Parse 'ack abc1' -> execute -> format confirmation."""
        item = _make_item(item_id="abc123def456", summary="Lane stall")
        status = _make_status(item)

        cmd = parse_ack_command("ack abc1")
        assert cmd is not None

        result = execute_remote_ack(cmd, status)
        assert result.success is True
        assert item.state == STATE_ACKED

        text = format_ack_confirmation(result)
        assert "\u2705" in text
        assert "Lane stall" in text

    def test_full_mute_round_trip(self) -> None:
        """Parse 'mute abc1' -> execute -> format confirmation."""
        item = _make_item(item_id="abc123def456")
        status = _make_status(item)

        cmd = parse_ack_command("MUTE ABC1")
        assert cmd is not None

        result = execute_remote_ack(cmd, status)
        assert result.success is True
        assert item.state == STATE_SUPPRESSED

        text = format_ack_confirmation(result)
        assert "\u2705" in text

    def test_non_command_passthrough(self) -> None:
        """Non-command text returns None from parser (passthrough)."""
        cmd = parse_ack_command("How's the fleet?")
        assert cmd is None
