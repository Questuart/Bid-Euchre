"""Telegram push adapter for alert delivery (Platform-9a, PR 3).

Bridges the transport-agnostic alert push evaluator (``alert_push.py``)
to the Telegram channel.  Responsibilities:

1. **Format** controller items as Telegram-friendly messages with visible
   ``item_id`` prefixes so the operator can reply ``ack <prefix>``.
2. **Gate** on the ``STEWARD_TELEGRAM_ENABLED`` env var kill switch.
3. **Orchestrate** a single push cycle: evaluate → format → record state →
   audit trail.  The *actual* MCP ``reply`` call is the caller's job —
   this module returns a :class:`PushResult` containing the ready-to-send
   text and chat_id.

.. note::

   The MCP ``reply`` tool is only callable from an active Claude Code
   conversation with the Telegram plugin enabled.  This adapter therefore
   **prepares** the push payload but does not send it.  The orchestrator
   skill (``/check-in`` or monitor cycle) is responsible for calling the
   MCP tool with the returned payload.

Usage::

    from bid_euchre.ops.telegram_push import prepare_alert_push, is_push_enabled

    if is_push_enabled():
        result = prepare_alert_push(
            fleet_status=status,
            idle_status=idle,
            push_state=ps,
            chat_id=chat_id,
        )
        if result is not None:
            # Caller sends result.message to result.chat_id via MCP reply
            ...
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from bid_euchre.ops.alert_push import (
    PushState,
    evaluate_push_needed,
    load_push_state,
    record_push,
    save_push_state,
)
from bid_euchre.ops.audit_trail import append_record, create_record
from bid_euchre.ops.control_plane import (
    ActionableItem,
    FleetStatus,
    load_fleet_status,
)
from bid_euchre.ops.idle_detector import IdleStatus, is_fleet_idle
from bid_euchre.ops.time_util import fmt_operator

logger = logging.getLogger("ops.telegram_push")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Env var checked by the push adapter.  The tmux launcher sets this based on
# whether the Telegram plugin is installed (see .claude/tmux/steward-session.sh).
TELEGRAM_ENABLED_ENV = "STEWARD_TELEGRAM_ENABLED"

# Env var for the target Telegram chat ID.  Set in the tmux session or .env.
ALERT_PUSH_CHAT_ID_ENV = "STEWARD_ALERT_PUSH_CHAT_ID"

# Severity emoji mapping for Telegram messages.
_SEVERITY_EMOJI: dict[str, str] = {
    "urgent": "\U0001f6a8",  # 🚨
    "high": "\u26a0\ufe0f",  # ⚠️
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PushResult:
    """Ready-to-send Telegram push payload.

    Attributes:
        chat_id: Telegram chat ID to send to.
        message: Formatted Telegram message text.
        items_pushed: The items included in this push (for state tracking).
    """

    chat_id: str
    message: str
    items_pushed: list[ActionableItem] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_alert_push(
    items: list[ActionableItem],
    *,
    now: datetime | None = None,
) -> str:
    """Format actionable items as a Telegram-friendly alert message.

    Each item shows its severity, truncated item_id (for ``ack <prefix>``
    replies), summary, and recommended action. The message is operator-
    facing, so the issued-at timestamp renders in Pacific Time.

    Args:
        items: The items to include in the message.
        now: Override current time (for testing). Defaults to ``utcnow()``.

    Returns:
        A multi-line string suitable for Telegram delivery.
    """
    if not items:
        return ""

    if now is None:
        now = datetime.now(timezone.utc)

    lines: list[str] = []
    lines.append(f"\U0001f4e2 Fleet Alert — {len(items)} item(s) need attention")
    lines.append(f"Issued: {fmt_operator(now)}")
    lines.append("")

    for item in items:
        emoji = _SEVERITY_EMOJI.get(item.severity, "\u2139\ufe0f")
        prefix = item.item_id[:8]
        lines.append(f"{emoji} [{item.severity.upper()}] {item.summary}")
        lines.append(f"   ID: {prefix}")
        if item.recommended_action:
            lines.append(f"   → {item.recommended_action}")
        if item.lane_id:
            lines.append(f"   Lane: {item.lane_id}")
        lines.append("")

    lines.append("Reply: ack <id>, mute <id>, or clear <id>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gate check
# ---------------------------------------------------------------------------


def is_push_enabled() -> bool:
    """Check if Telegram push is enabled via env var.

    Returns ``True`` when ``STEWARD_TELEGRAM_ENABLED`` is set to ``"1"``.
    Any other value (including unset) returns ``False``.
    """
    return os.environ.get(TELEGRAM_ENABLED_ENV, "0") == "1"


def get_push_chat_id() -> str | None:
    """Read the alert push chat ID from the environment.

    Returns ``None`` if not configured.
    """
    val = os.environ.get(ALERT_PUSH_CHAT_ID_ENV, "").strip()
    return val if val else None


# ---------------------------------------------------------------------------
# Push orchestration
# ---------------------------------------------------------------------------


def prepare_alert_push(
    fleet_status: FleetStatus,
    idle_status: IdleStatus,
    push_state: PushState,
    chat_id: str,
    *,
    cooldown_minutes: float | None = None,
    now: datetime | None = None,
    runtime_dir: Path | None = None,
    audit_dir: Path | None = None,
) -> PushResult | None:
    """Evaluate, format, record, and return a push payload if needed.

    This is the main entry point for the monitor cycle integration.
    It performs the full push preparation pipeline:

    1. Call ``evaluate_push_needed()`` to identify items that should be pushed.
    2. Format the items as a Telegram message via ``format_alert_push()``.
    3. Record each pushed item in the push state.
    4. Save the push state to disk.
    5. Audit the outbound push.

    Returns ``None`` if no push is needed (fleet active, no eligible items,
    or all items within cooldown).

    The caller is responsible for sending ``result.message`` to
    ``result.chat_id`` via the MCP ``reply`` tool.

    Args:
        fleet_status: Current controller projection.
        idle_status: Current fleet idle determination.
        push_state: Previously tracked push history (mutated in place).
        chat_id: Telegram chat ID for the push.
        cooldown_minutes: Override for push cooldown (default from alert_push).
        now: Override current time (for testing).
        runtime_dir: Override runtime directory for push state persistence.
        audit_dir: Override audit trail directory.

    Returns:
        A :class:`PushResult` ready for sending, or ``None`` if no push needed.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Evaluate which items need pushing.
    kwargs: dict = {"now": now}
    if cooldown_minutes is not None:
        kwargs["cooldown_minutes"] = cooldown_minutes

    items_to_push = evaluate_push_needed(
        fleet_status, idle_status, push_state, **kwargs
    )

    if not items_to_push:
        logger.debug("No items need pushing — skipping alert push cycle")
        return None

    # Format the alert message.
    message = format_alert_push(items_to_push, now=now)

    # Record each item as pushed in the push state.
    for item in items_to_push:
        record_push(push_state, item.item_id, item.severity, now=now)

    # Persist push state.
    save_push_state(push_state, runtime_dir=runtime_dir)

    # Audit the outbound push.
    try:
        audit_rec = create_record(
            direction="outbound",
            channel_source="telegram",
            sender_identity="steward-ops",
            exchange_type="reply",
            content=message,
            chat_id=chat_id,
            metadata={
                "purpose": "alert_push",
                "item_count": len(items_to_push),
                "item_ids": [i.item_id for i in items_to_push],
            },
        )
        append_record(audit_rec, audit_dir=audit_dir)
    except Exception:
        logger.warning("Failed to audit alert push — continuing", exc_info=True)

    logger.info(
        "Prepared alert push: %d item(s) for chat %s",
        len(items_to_push),
        chat_id,
    )

    return PushResult(
        chat_id=chat_id,
        message=message,
        items_pushed=list(items_to_push),
    )


# ---------------------------------------------------------------------------
# Convenience: full cycle from disk
# ---------------------------------------------------------------------------


def run_push_cycle(
    *,
    runtime_dir: Path | None = None,
    audit_dir: Path | None = None,
    cooldown_minutes: float | None = None,
    now: datetime | None = None,
    idle_threshold_minutes: float | None = None,
) -> PushResult | None:
    """Run a complete alert push cycle reading all state from disk.

    Convenience wrapper that loads fleet status, idle status, and push state
    from the standard runtime locations, then delegates to
    :func:`prepare_alert_push`.

    Returns ``None`` if:
    - Telegram push is disabled (env var)
    - No chat_id configured
    - No fleet status on disk
    - No push needed

    This function is designed to be called from ``cmd_monitor()`` after
    ``reconcile()`` completes.
    """
    if not is_push_enabled():
        logger.debug("Telegram push disabled (env: %s)", TELEGRAM_ENABLED_ENV)
        return None

    chat_id = get_push_chat_id()
    if not chat_id:
        logger.debug(
            "No alert push chat ID configured (env: %s)", ALERT_PUSH_CHAT_ID_ENV
        )
        return None

    fleet_status = load_fleet_status(runtime_dir)
    if fleet_status is None:
        logger.debug("No fleet status available — skipping push cycle")
        return None

    idle_kwargs: dict = {}
    if runtime_dir is not None:
        idle_kwargs["runtime_dir"] = runtime_dir
    if idle_threshold_minutes is not None:
        idle_kwargs["threshold_minutes"] = idle_threshold_minutes

    idle_status = is_fleet_idle(**idle_kwargs)

    push_state = load_push_state(runtime_dir=runtime_dir)

    return prepare_alert_push(
        fleet_status=fleet_status,
        idle_status=idle_status,
        push_state=push_state,
        chat_id=chat_id,
        cooldown_minutes=cooldown_minutes,
        now=now,
        runtime_dir=runtime_dir,
        audit_dir=audit_dir,
    )
