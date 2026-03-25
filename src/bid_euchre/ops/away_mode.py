"""Operator away-mode detection and escalation thresholds (Platform-9b).

Detects whether the operator is actively present, idle, away, or extended-away
based on the elapsed time since the last operator interaction.  The module is
**pure logic, no I/O** — callers supply timestamps and the module returns
deterministic state assessments.

State machine::

    present ──(idle_minutes)──→ idle ──(away_minutes)──→ away ──(extended_away_minutes)──→ extended_away

Each transition is governed by a configurable threshold in
:class:`EscalationThresholds`.  The thresholds represent *cumulative* minutes
since the last operator interaction — not minutes *in* the previous state.

Usage::

    from bid_euchre.ops.away_mode import (
        detect_operator_state,
        is_operator_away,
        EscalationThresholds,
    )

    # Simple check
    result = is_operator_away(last_interaction=some_datetime, now=now)
    if result:
        print("Operator is away — consider auto-escalation")

    # Detailed state assessment
    state = detect_operator_state(last_interaction=some_datetime, now=now)
    print(state.state, state.minutes_inactive, state.escalation_tier)
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("ops.away_mode")


# ---------------------------------------------------------------------------
# State enumeration
# ---------------------------------------------------------------------------


class OperatorPresence(enum.Enum):
    """Operator presence states, ordered by increasing absence duration.

    Values:
        PRESENT: Operator has interacted within the idle threshold.
        IDLE: No interaction for ``idle_minutes`` — may be briefly away.
        AWAY: No interaction for ``away_minutes`` — likely not at desk.
        EXTENDED_AWAY: No interaction for ``extended_away_minutes`` — prolonged absence.
    """

    PRESENT = "present"
    IDLE = "idle"
    AWAY = "away"
    EXTENDED_AWAY = "extended_away"


# ---------------------------------------------------------------------------
# Escalation thresholds
# ---------------------------------------------------------------------------

# Defaults (in minutes).
DEFAULT_IDLE_MINUTES = 15
DEFAULT_AWAY_MINUTES = 45
DEFAULT_EXTENDED_AWAY_MINUTES = 120


@dataclass(frozen=True)
class EscalationThresholds:
    """Configurable time windows for operator state transitions.

    All values are *cumulative* minutes since the last operator interaction.
    The invariant ``idle < away < extended_away`` is enforced at construction.

    Attributes:
        idle_minutes: Minutes before transitioning from PRESENT → IDLE.
        away_minutes: Minutes before transitioning from IDLE → AWAY.
        extended_away_minutes: Minutes before transitioning from AWAY → EXTENDED_AWAY.
    """

    idle_minutes: float = DEFAULT_IDLE_MINUTES
    away_minutes: float = DEFAULT_AWAY_MINUTES
    extended_away_minutes: float = DEFAULT_EXTENDED_AWAY_MINUTES

    def __post_init__(self) -> None:
        if self.idle_minutes <= 0:
            raise ValueError(f"idle_minutes must be positive, got {self.idle_minutes}")
        if self.away_minutes <= self.idle_minutes:
            raise ValueError(
                f"away_minutes ({self.away_minutes}) must be greater than "
                f"idle_minutes ({self.idle_minutes})"
            )
        if self.extended_away_minutes <= self.away_minutes:
            raise ValueError(
                f"extended_away_minutes ({self.extended_away_minutes}) must be "
                f"greater than away_minutes ({self.away_minutes})"
            )


# Singleton default thresholds.
DEFAULT_THRESHOLDS = EscalationThresholds()


# ---------------------------------------------------------------------------
# State detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OperatorStateResult:
    """Result of operator presence detection.

    Attributes:
        state: The determined :class:`OperatorPresence` state.
        minutes_inactive: Minutes since the last operator interaction.
            ``0.0`` when ``last_interaction`` is ``None`` and no fallback
            was available.
        last_interaction: The timestamp of the last operator interaction,
            or ``None`` if unknown.
        thresholds: The :class:`EscalationThresholds` used for this assessment.
        escalation_tier: Integer tier (0–3) corresponding to the state.
            0 = PRESENT, 1 = IDLE, 2 = AWAY, 3 = EXTENDED_AWAY.
            Higher tiers justify more aggressive autonomous actions.
        reason: Human-readable explanation of the determination.
    """

    state: OperatorPresence
    minutes_inactive: float
    last_interaction: datetime | None
    thresholds: EscalationThresholds
    escalation_tier: int
    reason: str


_STATE_TO_TIER: dict[OperatorPresence, int] = {
    OperatorPresence.PRESENT: 0,
    OperatorPresence.IDLE: 1,
    OperatorPresence.AWAY: 2,
    OperatorPresence.EXTENDED_AWAY: 3,
}


def detect_operator_state(
    last_interaction: datetime | None,
    *,
    thresholds: EscalationThresholds | None = None,
    now: datetime | None = None,
) -> OperatorStateResult:
    """Determine the operator's current presence state.

    This is a **pure function** — no I/O, no side effects.  All inputs are
    explicit.

    Args:
        last_interaction: Timestamp of the operator's most recent interaction
            (e.g., UserPromptSubmit, Telegram message).  ``None`` means no
            known interaction — treated as extended away.
        thresholds: Escalation thresholds.  Defaults to
            :data:`DEFAULT_THRESHOLDS`.
        now: Current time.  Defaults to ``datetime.now(timezone.utc)``.

    Returns:
        An :class:`OperatorStateResult` describing the assessment.
    """
    if thresholds is None:
        thresholds = DEFAULT_THRESHOLDS
    if now is None:
        now = datetime.now(timezone.utc)

    # No known interaction → assume extended away
    if last_interaction is None:
        state = OperatorPresence.EXTENDED_AWAY
        return OperatorStateResult(
            state=state,
            minutes_inactive=0.0,
            last_interaction=None,
            thresholds=thresholds,
            escalation_tier=_STATE_TO_TIER[state],
            reason="No known operator interaction — assuming extended away",
        )

    elapsed = now - last_interaction
    minutes_inactive = elapsed.total_seconds() / 60.0

    # Negative elapsed means last_interaction is in the future (clock skew).
    # Treat as present to be safe.
    if minutes_inactive < 0:
        state = OperatorPresence.PRESENT
        return OperatorStateResult(
            state=state,
            minutes_inactive=0.0,
            last_interaction=last_interaction,
            thresholds=thresholds,
            escalation_tier=_STATE_TO_TIER[state],
            reason="Last interaction is in the future (clock skew) — treating as present",
        )

    # Determine state from thresholds (check highest tier first)
    if minutes_inactive >= thresholds.extended_away_minutes:
        state = OperatorPresence.EXTENDED_AWAY
        reason = (
            f"No interaction for {minutes_inactive:.0f}m "
            f"(≥ {thresholds.extended_away_minutes:.0f}m extended-away threshold)"
        )
    elif minutes_inactive >= thresholds.away_minutes:
        state = OperatorPresence.AWAY
        reason = (
            f"No interaction for {minutes_inactive:.0f}m "
            f"(≥ {thresholds.away_minutes:.0f}m away threshold)"
        )
    elif minutes_inactive >= thresholds.idle_minutes:
        state = OperatorPresence.IDLE
        reason = (
            f"No interaction for {minutes_inactive:.0f}m "
            f"(≥ {thresholds.idle_minutes:.0f}m idle threshold)"
        )
    else:
        state = OperatorPresence.PRESENT
        reason = (
            f"Last interaction {minutes_inactive:.0f}m ago "
            f"(< {thresholds.idle_minutes:.0f}m idle threshold)"
        )

    return OperatorStateResult(
        state=state,
        minutes_inactive=minutes_inactive,
        last_interaction=last_interaction,
        thresholds=thresholds,
        escalation_tier=_STATE_TO_TIER[state],
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Convenience entry point
# ---------------------------------------------------------------------------


def is_operator_away(
    last_interaction: datetime | None,
    *,
    thresholds: EscalationThresholds | None = None,
    now: datetime | None = None,
) -> bool:
    """Return True if the operator is in AWAY or EXTENDED_AWAY state.

    This is a convenience wrapper around :func:`detect_operator_state` for
    callers that only need a boolean answer.

    Args:
        last_interaction: Timestamp of the operator's most recent interaction.
        thresholds: Escalation thresholds.
        now: Current time.

    Returns:
        True if the operator is AWAY or EXTENDED_AWAY.
    """
    result = detect_operator_state(last_interaction, thresholds=thresholds, now=now)
    return result.state in (OperatorPresence.AWAY, OperatorPresence.EXTENDED_AWAY)


# ---------------------------------------------------------------------------
# Threshold-based escalation helpers
# ---------------------------------------------------------------------------


def minutes_until_escalation(
    last_interaction: datetime | None,
    *,
    thresholds: EscalationThresholds | None = None,
    now: datetime | None = None,
) -> float | None:
    """Return minutes until the next escalation tier, or None if already at max.

    Useful for scheduling the next check — the caller can sleep or set a timer
    for this many minutes rather than polling continuously.

    Args:
        last_interaction: Timestamp of the operator's most recent interaction.
        thresholds: Escalation thresholds.
        now: Current time.

    Returns:
        Minutes until the next escalation tier, or ``None`` if already at
        EXTENDED_AWAY (the maximum tier).
    """
    result = detect_operator_state(last_interaction, thresholds=thresholds, now=now)

    if result.state == OperatorPresence.EXTENDED_AWAY:
        return None

    # Determine the next threshold
    if result.state == OperatorPresence.PRESENT:
        next_threshold = result.thresholds.idle_minutes
    elif result.state == OperatorPresence.IDLE:
        next_threshold = result.thresholds.away_minutes
    else:  # AWAY
        next_threshold = result.thresholds.extended_away_minutes

    remaining = next_threshold - result.minutes_inactive
    return max(0.0, remaining)
