"""Tests for operator away-mode detection and escalation thresholds.

Covers:
- State transitions: present → idle → away → extended_away
- Boundary conditions at each threshold
- EscalationThresholds validation
- is_operator_away() convenience function
- minutes_until_escalation() scheduling helper
- Edge cases: None interaction, clock skew, custom thresholds
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from bid_euchre.ops.away_mode import (
    DEFAULT_AWAY_MINUTES,
    DEFAULT_EXTENDED_AWAY_MINUTES,
    DEFAULT_IDLE_MINUTES,
    DEFAULT_THRESHOLDS,
    EscalationThresholds,
    OperatorPresence,
    detect_operator_state,
    is_operator_away,
    minutes_until_escalation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 25, 12, 0, 0, tzinfo=timezone.utc)


def _interaction_at(minutes_ago: float) -> datetime:
    """Return a datetime ``minutes_ago`` minutes before NOW."""
    return NOW - timedelta(minutes=minutes_ago)


# ---------------------------------------------------------------------------
# EscalationThresholds validation
# ---------------------------------------------------------------------------


class TestEscalationThresholds:
    """Test threshold construction and validation."""

    def test_default_thresholds(self) -> None:
        t = EscalationThresholds()
        assert t.idle_minutes == DEFAULT_IDLE_MINUTES
        assert t.away_minutes == DEFAULT_AWAY_MINUTES
        assert t.extended_away_minutes == DEFAULT_EXTENDED_AWAY_MINUTES

    def test_custom_thresholds(self) -> None:
        t = EscalationThresholds(
            idle_minutes=5, away_minutes=30, extended_away_minutes=60
        )
        assert t.idle_minutes == 5
        assert t.away_minutes == 30
        assert t.extended_away_minutes == 60

    def test_idle_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="idle_minutes must be positive"):
            EscalationThresholds(
                idle_minutes=0, away_minutes=10, extended_away_minutes=20
            )

    def test_idle_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="idle_minutes must be positive"):
            EscalationThresholds(
                idle_minutes=-5, away_minutes=10, extended_away_minutes=20
            )

    def test_away_must_exceed_idle(self) -> None:
        with pytest.raises(ValueError, match="away_minutes.*must be greater than"):
            EscalationThresholds(
                idle_minutes=10, away_minutes=10, extended_away_minutes=20
            )

    def test_extended_away_must_exceed_away(self) -> None:
        with pytest.raises(
            ValueError, match="extended_away_minutes.*must be greater than"
        ):
            EscalationThresholds(
                idle_minutes=5, away_minutes=15, extended_away_minutes=15
            )

    def test_thresholds_are_frozen(self) -> None:
        t = EscalationThresholds()
        with pytest.raises(AttributeError):
            t.idle_minutes = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# State detection — default thresholds
# ---------------------------------------------------------------------------


class TestDetectOperatorState:
    """Test detect_operator_state with default thresholds."""

    def test_present_just_interacted(self) -> None:
        result = detect_operator_state(_interaction_at(0), now=NOW)
        assert result.state == OperatorPresence.PRESENT
        assert result.escalation_tier == 0
        assert result.minutes_inactive == pytest.approx(0.0, abs=0.1)

    def test_present_within_idle_threshold(self) -> None:
        result = detect_operator_state(
            _interaction_at(DEFAULT_IDLE_MINUTES - 1), now=NOW
        )
        assert result.state == OperatorPresence.PRESENT
        assert result.escalation_tier == 0

    def test_idle_at_threshold(self) -> None:
        result = detect_operator_state(_interaction_at(DEFAULT_IDLE_MINUTES), now=NOW)
        assert result.state == OperatorPresence.IDLE
        assert result.escalation_tier == 1

    def test_idle_between_thresholds(self) -> None:
        mid = (DEFAULT_IDLE_MINUTES + DEFAULT_AWAY_MINUTES) / 2
        result = detect_operator_state(_interaction_at(mid), now=NOW)
        assert result.state == OperatorPresence.IDLE
        assert result.escalation_tier == 1

    def test_away_at_threshold(self) -> None:
        result = detect_operator_state(_interaction_at(DEFAULT_AWAY_MINUTES), now=NOW)
        assert result.state == OperatorPresence.AWAY
        assert result.escalation_tier == 2

    def test_away_between_thresholds(self) -> None:
        mid = (DEFAULT_AWAY_MINUTES + DEFAULT_EXTENDED_AWAY_MINUTES) / 2
        result = detect_operator_state(_interaction_at(mid), now=NOW)
        assert result.state == OperatorPresence.AWAY
        assert result.escalation_tier == 2

    def test_extended_away_at_threshold(self) -> None:
        result = detect_operator_state(
            _interaction_at(DEFAULT_EXTENDED_AWAY_MINUTES), now=NOW
        )
        assert result.state == OperatorPresence.EXTENDED_AWAY
        assert result.escalation_tier == 3

    def test_extended_away_past_threshold(self) -> None:
        result = detect_operator_state(
            _interaction_at(DEFAULT_EXTENDED_AWAY_MINUTES + 60), now=NOW
        )
        assert result.state == OperatorPresence.EXTENDED_AWAY
        assert result.escalation_tier == 3
        assert result.minutes_inactive == pytest.approx(
            DEFAULT_EXTENDED_AWAY_MINUTES + 60, abs=0.1
        )

    def test_minutes_inactive_tracks_elapsed(self) -> None:
        minutes_ago = 42.5
        result = detect_operator_state(_interaction_at(minutes_ago), now=NOW)
        assert result.minutes_inactive == pytest.approx(minutes_ago, abs=0.1)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_interaction_assumes_extended_away(self) -> None:
        result = detect_operator_state(None, now=NOW)
        assert result.state == OperatorPresence.EXTENDED_AWAY
        assert result.escalation_tier == 3
        assert result.last_interaction is None
        assert "No known operator interaction" in result.reason

    def test_clock_skew_future_interaction_treated_as_present(self) -> None:
        """last_interaction in the future → treat as present (safe default)."""
        future = NOW + timedelta(minutes=5)
        result = detect_operator_state(future, now=NOW)
        assert result.state == OperatorPresence.PRESENT
        assert result.escalation_tier == 0
        assert result.minutes_inactive == 0.0
        assert "clock skew" in result.reason.lower()

    def test_result_is_frozen(self) -> None:
        result = detect_operator_state(_interaction_at(10), now=NOW)
        with pytest.raises(AttributeError):
            result.state = OperatorPresence.AWAY  # type: ignore[misc]

    def test_result_includes_thresholds(self) -> None:
        result = detect_operator_state(_interaction_at(10), now=NOW)
        assert result.thresholds is DEFAULT_THRESHOLDS

    def test_now_defaults_to_utc(self) -> None:
        """Smoke test: calling without now= should not crash."""
        result = detect_operator_state(datetime.now(timezone.utc))
        assert result.state in OperatorPresence


# ---------------------------------------------------------------------------
# Custom thresholds
# ---------------------------------------------------------------------------


class TestCustomThresholds:
    """Test with non-default escalation thresholds."""

    TIGHT = EscalationThresholds(
        idle_minutes=5, away_minutes=10, extended_away_minutes=20
    )

    def test_present_with_tight_thresholds(self) -> None:
        result = detect_operator_state(
            _interaction_at(4), thresholds=self.TIGHT, now=NOW
        )
        assert result.state == OperatorPresence.PRESENT

    def test_idle_with_tight_thresholds(self) -> None:
        result = detect_operator_state(
            _interaction_at(5), thresholds=self.TIGHT, now=NOW
        )
        assert result.state == OperatorPresence.IDLE

    def test_away_with_tight_thresholds(self) -> None:
        result = detect_operator_state(
            _interaction_at(10), thresholds=self.TIGHT, now=NOW
        )
        assert result.state == OperatorPresence.AWAY

    def test_extended_away_with_tight_thresholds(self) -> None:
        result = detect_operator_state(
            _interaction_at(20), thresholds=self.TIGHT, now=NOW
        )
        assert result.state == OperatorPresence.EXTENDED_AWAY


# ---------------------------------------------------------------------------
# is_operator_away convenience function
# ---------------------------------------------------------------------------


class TestIsOperatorAway:
    """Test the boolean convenience wrapper."""

    def test_present_returns_false(self) -> None:
        assert not is_operator_away(_interaction_at(0), now=NOW)

    def test_idle_returns_false(self) -> None:
        assert not is_operator_away(_interaction_at(DEFAULT_IDLE_MINUTES), now=NOW)

    def test_away_returns_true(self) -> None:
        assert is_operator_away(_interaction_at(DEFAULT_AWAY_MINUTES), now=NOW)

    def test_extended_away_returns_true(self) -> None:
        assert is_operator_away(_interaction_at(DEFAULT_EXTENDED_AWAY_MINUTES), now=NOW)

    def test_none_interaction_returns_true(self) -> None:
        assert is_operator_away(None, now=NOW)

    def test_custom_thresholds_respected(self) -> None:
        tight = EscalationThresholds(
            idle_minutes=2, away_minutes=5, extended_away_minutes=10
        )
        # 4 minutes ago with away threshold of 5 → IDLE, not away
        assert not is_operator_away(_interaction_at(4), thresholds=tight, now=NOW)
        # 6 minutes ago with away threshold of 5 → AWAY
        assert is_operator_away(_interaction_at(6), thresholds=tight, now=NOW)


# ---------------------------------------------------------------------------
# minutes_until_escalation scheduling helper
# ---------------------------------------------------------------------------


class TestMinutesUntilEscalation:
    """Test the escalation scheduling helper."""

    def test_present_to_idle(self) -> None:
        """5 minutes ago → 10 minutes until idle (default 15m threshold)."""
        remaining = minutes_until_escalation(_interaction_at(5), now=NOW)
        assert remaining is not None
        assert remaining == pytest.approx(DEFAULT_IDLE_MINUTES - 5, abs=0.1)

    def test_idle_to_away(self) -> None:
        """20 minutes ago → 25 minutes until away (default 45m threshold)."""
        remaining = minutes_until_escalation(_interaction_at(20), now=NOW)
        assert remaining is not None
        assert remaining == pytest.approx(DEFAULT_AWAY_MINUTES - 20, abs=0.1)

    def test_away_to_extended_away(self) -> None:
        """60 minutes ago → 60 minutes until extended_away (default 120m threshold)."""
        remaining = minutes_until_escalation(_interaction_at(60), now=NOW)
        assert remaining is not None
        assert remaining == pytest.approx(DEFAULT_EXTENDED_AWAY_MINUTES - 60, abs=0.1)

    def test_extended_away_returns_none(self) -> None:
        """Already at max tier — no further escalation."""
        remaining = minutes_until_escalation(
            _interaction_at(DEFAULT_EXTENDED_AWAY_MINUTES + 30), now=NOW
        )
        assert remaining is None

    def test_none_interaction_returns_none(self) -> None:
        """No known interaction → already at max tier."""
        remaining = minutes_until_escalation(None, now=NOW)
        assert remaining is None

    def test_at_threshold_boundary(self) -> None:
        """Exactly at idle threshold → 0 minutes until next escalation, state is IDLE."""
        remaining = minutes_until_escalation(
            _interaction_at(DEFAULT_IDLE_MINUTES), now=NOW
        )
        assert remaining is not None
        # IDLE → next is away_minutes (45), currently at 15 → 30 remaining
        assert remaining == pytest.approx(
            DEFAULT_AWAY_MINUTES - DEFAULT_IDLE_MINUTES, abs=0.1
        )

    def test_just_before_threshold(self) -> None:
        """Just under idle threshold → nearly 0 remaining until idle."""
        remaining = minutes_until_escalation(
            _interaction_at(DEFAULT_IDLE_MINUTES - 0.1), now=NOW
        )
        assert remaining is not None
        assert remaining == pytest.approx(0.1, abs=0.05)


# ---------------------------------------------------------------------------
# State progression — full lifecycle
# ---------------------------------------------------------------------------


class TestStateProgression:
    """Verify the full state machine progresses correctly over time."""

    THRESHOLDS = EscalationThresholds(
        idle_minutes=10, away_minutes=30, extended_away_minutes=60
    )
    INTERACTION = NOW - timedelta(minutes=0)

    def test_full_progression(self) -> None:
        """Walk through all four states as time progresses."""
        checks = [
            (0, OperatorPresence.PRESENT, 0),
            (5, OperatorPresence.PRESENT, 0),
            (10, OperatorPresence.IDLE, 1),
            (20, OperatorPresence.IDLE, 1),
            (30, OperatorPresence.AWAY, 2),
            (45, OperatorPresence.AWAY, 2),
            (60, OperatorPresence.EXTENDED_AWAY, 3),
            (120, OperatorPresence.EXTENDED_AWAY, 3),
        ]
        for minutes_later, expected_state, expected_tier in checks:
            check_time = NOW + timedelta(minutes=minutes_later)
            result = detect_operator_state(
                self.INTERACTION, thresholds=self.THRESHOLDS, now=check_time
            )
            assert (
                result.state == expected_state
            ), f"At +{minutes_later}m: expected {expected_state}, got {result.state}"
            assert result.escalation_tier == expected_tier

    def test_tier_monotonically_increases(self) -> None:
        """Escalation tier never decreases as time progresses."""
        prev_tier = -1
        for minutes_later in range(0, 120, 1):
            check_time = NOW + timedelta(minutes=minutes_later)
            result = detect_operator_state(
                self.INTERACTION, thresholds=self.THRESHOLDS, now=check_time
            )
            assert result.escalation_tier >= prev_tier, (
                f"Tier decreased at +{minutes_later}m: "
                f"{prev_tier} → {result.escalation_tier}"
            )
            prev_tier = result.escalation_tier


# ---------------------------------------------------------------------------
# Reason strings
# ---------------------------------------------------------------------------


class TestReasonStrings:
    """Verify that reason strings are informative."""

    def test_present_reason_mentions_threshold(self) -> None:
        result = detect_operator_state(_interaction_at(5), now=NOW)
        assert "idle threshold" in result.reason.lower()

    def test_idle_reason_mentions_minutes(self) -> None:
        result = detect_operator_state(
            _interaction_at(DEFAULT_IDLE_MINUTES + 1), now=NOW
        )
        assert "idle threshold" in result.reason.lower()

    def test_away_reason_mentions_minutes(self) -> None:
        result = detect_operator_state(
            _interaction_at(DEFAULT_AWAY_MINUTES + 1), now=NOW
        )
        assert "away threshold" in result.reason.lower()

    def test_extended_away_reason_mentions_minutes(self) -> None:
        result = detect_operator_state(
            _interaction_at(DEFAULT_EXTENDED_AWAY_MINUTES + 1), now=NOW
        )
        assert "extended-away threshold" in result.reason.lower()
