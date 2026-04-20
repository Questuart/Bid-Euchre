#!/usr/bin/env python3
"""UserPromptSubmit hook: inject unacked high-priority inbox messages as additionalContext.

When author/analyst lanes signal state that needs orchestrator attention,
they send messages to the orchestrator's inbox via the message bus.  This
hook reads those messages, formats a grouped summary, and injects it as
``additionalContext`` so the orchestrator sees the state on every prompt
boundary — not just on cron boundaries.

Surfaced message types:
- ``completion`` — a lane finished a task (pre-existing behavior)
- ``blocker`` — a lane cannot proceed without action
- ``escalation`` — an unresolved item bubbled up from the monitor
- ``supervisor_alert`` with priority ``high`` or ``urgent``

Auto-ack policy (**critical**):
- ``completion`` messages are auto-acked after surfacing (preserves the
  previous behavior — the orchestrator has now observed the completion
  and a re-injection on the next prompt would be noise).
- ``blocker``, ``escalation``, and high/urgent ``supervisor_alert``
  messages are surfaced ONLY.  They must remain unacked so the action
  item survives across prompts until it is explicitly handled.  Auto-
  acking these would silently drop a real action item.

Design constraints:
- Best-effort: failures never block prompt submission.
- Uses ``uv run`` to access project imports (bid_euchre.ops.message_bus).
- Lazy imports for project modules to keep the fast-exit path lightweight.

Closes #1986.  Extended by PR-MSG-3 (messaging revamp execution plan) to
cover blockers, escalations, and high/urgent supervisor_alert messages.
"""

from __future__ import annotations

import json
import sys

# ---------------------------------------------------------------------------
# Selection / ack policy
# ---------------------------------------------------------------------------

_COMPLETION = "completion"
_BLOCKER = "blocker"
_ESCALATION = "escalation"
_SUPERVISOR_ALERT = "supervisor_alert"

# Message types that always surface regardless of priority.
_ALWAYS_SURFACE_TYPES: frozenset[str] = frozenset({_COMPLETION, _BLOCKER, _ESCALATION})

# ``supervisor_alert`` only surfaces for these priorities.  Low/normal
# supervisor alerts stay in the inbox for the next cron batch.
_ACTIONABLE_ALERT_PRIORITIES: frozenset[str] = frozenset({"high", "urgent"})

# Tuple of every type we even bother fetching from the inbox.
_FETCH_TYPES: tuple[str, ...] = (
    _COMPLETION,
    _BLOCKER,
    _ESCALATION,
    _SUPERVISOR_ALERT,
)

# ONLY these types are auto-acked after surfacing.  Everything else must
# remain unacked so the action item is not silently dropped.
_AUTO_ACK_TYPES: frozenset[str] = frozenset({_COMPLETION})

# Output section ordering — most urgent first.  Each entry is
# ``(message_type, header_label)``.
_SECTION_SPECS: tuple[tuple[str, str], ...] = (
    (_ESCALATION, "ESCALATIONS"),
    (_BLOCKER, "BLOCKERS"),
    (_SUPERVISOR_ALERT, "URGENT ALERTS"),
    (_COMPLETION, "LANE COMPLETIONS"),
)


def _is_actionable(msg: dict) -> bool:
    """Return True if *msg* should surface at the prompt boundary."""
    mt = msg.get("message_type")
    if mt in _ALWAYS_SURFACE_TYPES:
        return True
    if mt == _SUPERVISOR_ALERT:
        return msg.get("priority") in _ACTIONABLE_ALERT_PRIORITIES
    return False


def _format_message_line(msg: dict) -> str:
    """Render a single inbox message as a bullet line."""
    from_lane = msg.get("from_lane", "unknown")
    summary = msg.get("summary", "(no summary)")
    task_id = msg.get("task_id", "")
    task_suffix = f" [task:{task_id[:12]}]" if task_id else ""

    # Surface the priority tag for supervisor_alert so the orchestrator can
    # tell high from urgent at a glance.
    mt = msg.get("message_type")
    priority = msg.get("priority", "")
    pri_tag = f" <{priority}>" if mt == _SUPERVISOR_ALERT and priority else ""

    return f"  [{from_lane}]{pri_tag} {summary}{task_suffix}"


def main() -> int:
    """Entry point.  Returns 0 always (never blocks prompt submission)."""
    # Lazy import — only load project modules when we actually run
    try:
        from bid_euchre.ops.message_bus import ack_message, read_inbox
    except ImportError:
        return 0

    # Read the orchestrator inbox for any actionable message type.
    # Status "delivered" or "pending" are the actionable states.
    fetched: list[dict] = []
    for status in ("delivered", "pending"):
        msgs = read_inbox(
            "orchestrator",
            status=status,
            message_type=_FETCH_TYPES,
            limit=50,
            auto_expire=True,
            auto_compact=False,  # Don't compact on every prompt
        )
        fetched.extend(msgs)

    # Apply the priority filter for supervisor_alert.  Other actionable
    # types pass through unconditionally.
    actionable = [m for m in fetched if _is_actionable(m)]

    if not actionable:
        return 0

    # Group messages by type for readable grouped output.
    groups: dict[str, list[dict]] = {mt: [] for mt, _ in _SECTION_SPECS}
    for msg in actionable:
        mt = msg.get("message_type")
        if mt in groups:
            groups[mt].append(msg)

    # Build the context string — sections in most-urgent-first order.
    lines: list[str] = []
    for mt, label in _SECTION_SPECS:
        msgs_of_type = groups.get(mt, [])
        if not msgs_of_type:
            continue
        lines.append(f"{label} ({len(msgs_of_type)} unacked):")
        for msg in msgs_of_type:
            lines.append(_format_message_line(msg))
        lines.append("")

    # Dispatch / action hint — preserves the "reviewing their PRs" /
    # "dispatch" phrasing assertions from the legacy test suite while
    # covering the broader set of surfaced states.
    lines.append(
        "These items require orchestrator attention. Consider reviewing "
        "their PRs, unblocking lanes, and dispatching new work as appropriate."
    )

    context = "\n".join(lines)

    # Auto-ack ONLY completion messages.  Blockers, escalations, and
    # high/urgent alerts must remain unacked so the action item is not
    # silently dropped.  This is the primary invariant of PR-MSG-3.
    for msg in actionable:
        if msg.get("message_type") not in _AUTO_ACK_TYPES:
            continue
        mid = msg.get("message_id")
        if not mid:
            continue
        try:
            ack_message(mid, "orchestrator")
        except Exception:  # noqa: BLE001 — best-effort
            pass

    # Output the additionalContext payload
    print(json.dumps({"additionalContext": context}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
