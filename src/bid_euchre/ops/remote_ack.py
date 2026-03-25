"""Remote ack parser and controller mutation (Platform-9a, PR 2).

Parses ack/dismiss/mute/clear commands from inbound Telegram messages
and applies them to the controller projection via the existing
``control_plane.py`` mutation API.

This module is **pure logic** -- it contains no Telegram-specific code,
no I/O with Telegram, and no MCP tool calls.  It operates on text input
and :class:`FleetStatus` objects, returning structured results.

Usage::

    from bid_euchre.ops.remote_ack import (
        parse_ack_command,
        execute_remote_ack,
        format_ack_confirmation,
    )

    cmd = parse_ack_command("ack abc1")
    if cmd is not None:
        result = execute_remote_ack(cmd, fleet_status)
        reply_text = format_ack_confirmation(result)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from bid_euchre.ops.control_plane import (
    FleetStatus,
    ack_item,
    clear_item,
    suppress_item,
)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class AckAction(Enum):
    """Recognized remote-ack actions."""

    ACK = "ack"
    DISMISS = "dismiss"
    MUTE = "mute"
    CLEAR = "clear"


@dataclass(frozen=True)
class AckCommand:
    """A parsed ack command from inbound text.

    Attributes:
        action: The ack action (ack/dismiss/mute/clear).
        prefix: The item_id prefix provided by the operator.
    """

    action: AckAction
    prefix: str


@dataclass(frozen=True)
class AckResult:
    """Result of executing a remote ack command.

    Attributes:
        success: Whether the mutation succeeded.
        action: The action that was attempted.
        item_id: The full item_id that was matched (or None on failure).
        summary: The matched item's summary (or None on failure).
        message: Human-readable result message.
        candidates: On ambiguous prefix, the list of matching item_ids.
    """

    success: bool
    action: AckAction
    item_id: str | None = None
    summary: str | None = None
    message: str = ""
    candidates: list[str] | None = None


# ---------------------------------------------------------------------------
# Command patterns
# ---------------------------------------------------------------------------

# Matches: "ack <prefix>", "dismiss <prefix>", "mute <prefix>", "clear <prefix>"
# Case-insensitive, whitespace-tolerant.
_COMMAND_RE = re.compile(
    r"^\s*(ack|dismiss|mute|clear)\s+([a-f0-9]+)\s*$",
    re.IGNORECASE,
)

_ACTION_MAP: dict[str, AckAction] = {
    "ack": AckAction.ACK,
    "dismiss": AckAction.DISMISS,
    "mute": AckAction.MUTE,
    "clear": AckAction.CLEAR,
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_ack_command(text: str) -> AckCommand | None:
    """Parse a remote ack command from inbound message text.

    Recognized patterns (case-insensitive, whitespace-tolerant)::

        ack <hex-prefix>
        dismiss <hex-prefix>
        mute <hex-prefix>
        clear <hex-prefix>

    Returns ``None`` for non-command messages (free-form conversation),
    allowing the caller to pass them through to normal handling.
    """
    match = _COMMAND_RE.match(text)
    if match is None:
        return None

    action_str = match.group(1).lower()
    prefix = match.group(2).lower()

    return AckCommand(
        action=_ACTION_MAP[action_str],
        prefix=prefix,
    )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def _find_items_by_prefix(status: FleetStatus, prefix: str) -> list[tuple[str, str]]:
    """Find items whose item_id starts with the given prefix.

    Returns a list of (item_id, summary) tuples.
    """
    return [
        (item.item_id, item.summary)
        for item in status.items
        if item.item_id.startswith(prefix)
    ]


def execute_remote_ack(command: AckCommand, status: FleetStatus) -> AckResult:
    """Execute a remote ack command against the fleet status projection.

    Maps command actions to controller mutations:
    - ``ack`` -> ``ack_item()``
    - ``dismiss`` / ``mute`` -> ``suppress_item()``
    - ``clear`` -> ``clear_item()``

    Includes prefix-match ambiguity detection (same pattern as CLI).
    Does NOT call ``save_fleet_status()`` -- the caller is responsible
    for persistence after a successful mutation.

    Args:
        command: The parsed ack command.
        status: The current fleet status (mutated in place on success).

    Returns:
        An ``AckResult`` with success status and human-readable message.
    """
    matches = _find_items_by_prefix(status, command.prefix)

    if not matches:
        return AckResult(
            success=False,
            action=command.action,
            message=f"No item matching prefix '{command.prefix}'",
        )

    if len(matches) > 1:
        return AckResult(
            success=False,
            action=command.action,
            message=(
                f"Ambiguous prefix '{command.prefix}' -- "
                f"matches {len(matches)} items. "
                f"Use a longer prefix."
            ),
            candidates=[item_id for item_id, _ in matches],
        )

    item_id, item_summary = matches[0]

    # Map action to mutation function.
    mutation_fn = {
        AckAction.ACK: ack_item,
        AckAction.DISMISS: suppress_item,
        AckAction.MUTE: suppress_item,
        AckAction.CLEAR: clear_item,
    }[command.action]

    ok = mutation_fn(status, item_id)

    if not ok:
        # Item exists but is not in a mutable state (e.g., already acked).
        return AckResult(
            success=False,
            action=command.action,
            item_id=item_id,
            summary=item_summary,
            message=(
                f"Item {item_id[:8]} exists but cannot be "
                f"{command.action.value}d (may already be "
                f"acked/cleared/suppressed)"
            ),
        )

    action_past = {
        AckAction.ACK: "Acknowledged",
        AckAction.DISMISS: "Suppressed",
        AckAction.MUTE: "Suppressed",
        AckAction.CLEAR: "Cleared",
    }[command.action]

    return AckResult(
        success=True,
        action=command.action,
        item_id=item_id,
        summary=item_summary,
        message=f"{action_past} item {item_id[:8]} -- {item_summary}",
    )


# ---------------------------------------------------------------------------
# Confirmation formatting
# ---------------------------------------------------------------------------


def format_ack_confirmation(result: AckResult) -> str:
    """Format an ack result as a Telegram-friendly confirmation message.

    Returns a human-readable string suitable for replying to the operator.
    """
    if result.success:
        return f"\u2705 {result.message}"

    if result.candidates:
        lines = [f"\u274c {result.message}"]
        lines.append("")
        lines.append("Candidates:")
        for cid in result.candidates:
            lines.append(f"  {cid}")
        return "\n".join(lines)

    return f"\u274c {result.message}"
