"""Delivery-policy helper for high-value bus messages (PR-MSG-2).

The ``message_bus`` layer is intentionally durable-only: it writes audit
trails and per-lane inboxes and emits events, but it does not actively
push to tmux panes or otherwise try to wake recipients.  That boundary
exists to keep the bus free of tmux coupling and to avoid circular
imports between ``message_bus`` and ``worker_pool``.

Most messages should ride the durable path alone — the recipient's
prompt-boundary surfacing (``.claude/hooks/inbox-completion-inject.py``)
and periodic cron polling (``/fleet-check``) are sufficient for
``assignment``, ``progress``, ``ack``, and low/normal ``supervisor_alert``.

A small set of message types, however, are attention-worthy enough that
the extra 3–10 seconds of nudge latency is worth the best-effort tmux
poke.  This module provides:

- :func:`should_nudge_for_message` — policy decision: does this
  ``(message_type, priority)`` combination warrant a nudge?
- :func:`send_with_attention` — convenience wrapper that writes the
  durable message via ``message_bus.send_message`` and then, on success,
  optionally calls ``worker_pool.nudge_inbox`` when the policy allows.

The policy explicitly nudges on:

- ``blocker``
- ``escalation``
- ``supervisor_alert`` with priority ``high`` or ``urgent``

Everything else returns the durable message_id without poking the
recipient pane.

Architectural invariant:
    ``message_bus.send_message`` must NOT grow a ``nudge_recipient``
    parameter or any other tmux side effect.  All delivery-policy
    decisions live here or in higher-level adapters.

See ``plans/sessions/2026-04-20_messaging-revamp-execution-plan.md``
§ PR-MSG-2 for the full design rationale.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from bid_euchre.ops.message_bus import send_message
from bid_euchre.ops.worker_pool import nudge_inbox

if TYPE_CHECKING:
    from bid_euchre.ops.message_bus import BusMessage

logger = logging.getLogger("ops.attention")

# Message types that always warrant a best-effort nudge regardless of priority.
_ALWAYS_NUDGE_TYPES: frozenset[str] = frozenset({"blocker", "escalation"})

# supervisor_alert priorities that warrant a nudge.  Low/normal/info alerts
# ride the durable-only path and surface via prompt-boundary hooks or cron.
_SUPERVISOR_NUDGE_PRIORITIES: frozenset[str] = frozenset({"high", "urgent"})


def should_nudge_for_message(
    message_type: str,
    priority: str,
) -> bool:
    """Return ``True`` when this message warrants a best-effort pane nudge.

    Policy (must match the PR-MSG-2 task packet):

    - ``blocker`` — always nudge.  By definition the sender cannot proceed
      without attention; waiting a full fleet-check cycle would stall the
      fleet.
    - ``escalation`` — always nudge.  Escalations are already second-order
      signals (unacked-message amplification, approval stalls) and must
      reach the recipient promptly.
    - ``supervisor_alert`` — nudge only when priority is ``high`` or
      ``urgent``.  Routine ``normal``/``low``/``info`` alerts are noise
      when nudged.
    - All other message types (``assignment``, ``progress``, ``ack``,
      ``completion``, ``recovery``) — durable-only.  Completion has its
      own fast path in ``post-merge-notify.sh`` (see PR-MSG-1).

    Args:
        message_type: The ``BusMessage.message_type`` value.
        priority: The ``BusMessage.priority`` value.

    Returns:
        ``True`` if the policy mandates a pane nudge, else ``False``.
    """
    if message_type in _ALWAYS_NUDGE_TYPES:
        return True
    if message_type == "supervisor_alert" and priority in _SUPERVISOR_NUDGE_PRIORITIES:
        return True
    return False


def send_with_attention(
    msg: "BusMessage",
    bus_root: Path | None = None,
    *,
    events_dir: Path | None = None,
    deduplicate: bool = False,
    tmux_session: str | None = None,
    runtime_dir: Path | None = None,
) -> str:
    """Send a durable message, then optionally nudge the recipient.

    Writes the message to the bus via :func:`message_bus.send_message` and,
    if :func:`should_nudge_for_message` returns ``True`` for this message's
    ``(message_type, priority)``, calls
    :func:`worker_pool.nudge_inbox` as a best-effort tmux poke.

    The nudge is strictly best-effort: any failure is logged and swallowed.
    It never propagates back to the caller and never affects the returned
    message_id.  If ``send_message`` fails, the nudge is never attempted —
    there is no inbox entry to look at, so poking the pane would just be
    noise.

    Args:
        msg: The :class:`BusMessage` to send.
        bus_root: Override for the message bus root directory.
        events_dir: Override for the events directory (for testing).
        deduplicate: Forwarded to :func:`send_message`.
        tmux_session: Override for the tmux session name used by the nudge.
        runtime_dir: Override for the runtime directory used by the nudge.

    Returns:
        The ``message_id`` returned by :func:`send_message`.

    Raises:
        ValueError: Propagated from :func:`send_message` on duplicate IDs.
        OSError: Propagated from :func:`send_message` on audit-trail IO errors.
    """
    # Durable write first.  Any exception here skips the nudge entirely.
    message_id = send_message(
        msg,
        bus_root,
        events_dir=events_dir,
        deduplicate=deduplicate,
    )

    if not should_nudge_for_message(msg.message_type, msg.priority):
        return message_id

    # nudge_inbox is imported at module top level so test suites can patch
    # the name on this module; the worker_pool -> message_bus dependency
    # is lazy-only, so there is no import cycle.
    try:
        if tmux_session is not None and runtime_dir is not None:
            action = nudge_inbox(
                msg.to_lane,
                tmux_session=tmux_session,
                runtime_dir=runtime_dir,
            )
        elif tmux_session is not None:
            action = nudge_inbox(msg.to_lane, tmux_session=tmux_session)
        elif runtime_dir is not None:
            action = nudge_inbox(msg.to_lane, runtime_dir=runtime_dir)
        else:
            action = nudge_inbox(msg.to_lane)

        if not action.executed:
            logger.debug(
                "Best-effort nudge for %s (%s) did not execute: %s",
                msg.to_lane,
                msg.message_type,
                action.reason,
            )
    except Exception:
        # Best-effort only — the durable send already succeeded.
        logger.warning(
            "Best-effort nudge_inbox raised for %s (%s); durable send is intact",
            msg.to_lane,
            msg.message_type,
            exc_info=True,
        )

    return message_id


__all__ = [
    "send_with_attention",
    "should_nudge_for_message",
]
