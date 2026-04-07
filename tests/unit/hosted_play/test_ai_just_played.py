"""Unit tests for _last_played_seat and ai_just_played gate in web/routes.py.

Covers the trick-boundary fallback in _last_played_seat and the broadened
ai_just_played gate that now fires on paused_after_trick as well as
paused_after_play.  Refs #2538.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bid_euchre.core.cards import Card
from bid_euchre.hosted_play import TrickResult, TrickState
from web.routes import _last_played_seat

# ---------------------------------------------------------------------------
# Minimal hand stub — only the fields _last_played_seat needs
# ---------------------------------------------------------------------------


@dataclass
class _HandStub:
    """Minimal stand-in for HandState; only has the fields under test."""

    phase: str = "trick_play"
    current_trick: TrickState | None = None
    completed_tricks: list[TrickResult] = field(default_factory=list)
    paused_after_play: bool = False
    paused_after_trick: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HUMAN_SEAT = 0  # Matches engine constant
AI_SEAT_1 = 1
AI_SEAT_2 = 3


def _card(rank: str, suit: str) -> Card:
    return Card(rank=rank, suit=suit)


def _make_completed_trick(plays: list[tuple[int, Card]], winner: int) -> TrickResult:
    return TrickResult(leader=plays[0][0], plays=plays, winner=winner)


# ---------------------------------------------------------------------------
# _last_played_seat tests
# ---------------------------------------------------------------------------


class TestLastPlayedSeatActiveTrick:
    """When the active trick has plays, return the last player."""

    def test_single_play(self):
        hand = _HandStub(
            current_trick=TrickState(
                leader=1,
                plays=[(1, _card("A", "S"))],
            ),
        )
        assert _last_played_seat(hand) == 1

    def test_multiple_plays(self):
        hand = _HandStub(
            current_trick=TrickState(
                leader=0,
                plays=[
                    (0, _card("A", "S")),
                    (1, _card("K", "S")),
                    (2, _card("Q", "S")),
                ],
            ),
        )
        assert _last_played_seat(hand) == 2

    def test_full_trick(self):
        hand = _HandStub(
            current_trick=TrickState(
                leader=1,
                plays=[
                    (1, _card("A", "H")),
                    (2, _card("K", "H")),
                    (3, _card("Q", "H")),
                    (0, _card("10", "H")),
                ],
            ),
        )
        assert _last_played_seat(hand) == 0


class TestLastPlayedSeatFallback:
    """When the active trick is empty/None, fall back to completed tricks."""

    def test_empty_active_trick_with_completed(self):
        """paused_after_trick: active trick cleared, completed has the trick."""
        completed = _make_completed_trick(
            plays=[
                (1, _card("A", "S")),
                (2, _card("K", "S")),
                (3, _card("Q", "S")),
                (0, _card("10", "S")),
            ],
            winner=1,
        )
        hand = _HandStub(
            current_trick=TrickState(leader=1, plays=[]),
            completed_tricks=[completed],
            paused_after_trick=True,
        )
        assert _last_played_seat(hand) == 0

    def test_none_active_trick_with_completed(self):
        """current_trick is None but completed tricks exist."""
        completed = _make_completed_trick(
            plays=[
                (2, _card("A", "H")),
                (3, _card("K", "H")),
                (0, _card("Q", "H")),
                (1, _card("10", "H")),
            ],
            winner=2,
        )
        hand = _HandStub(
            current_trick=None,
            completed_tricks=[completed],
            paused_after_trick=True,
        )
        assert _last_played_seat(hand) == 1

    def test_multiple_completed_uses_last(self):
        """With multiple completed tricks, use the most recent one."""
        older = _make_completed_trick(
            plays=[
                (0, _card("A", "S")),
                (1, _card("K", "S")),
                (2, _card("Q", "S")),
                (3, _card("10", "S")),
            ],
            winner=0,
        )
        newer = _make_completed_trick(
            plays=[
                (0, _card("A", "H")),
                (1, _card("K", "H")),
                (2, _card("Q", "H")),
                (3, _card("10", "H")),
            ],
            winner=0,
        )
        hand = _HandStub(
            current_trick=TrickState(leader=0, plays=[]),
            completed_tricks=[older, newer],
            paused_after_trick=True,
        )
        # Should return seat 3 (last play in newest completed trick)
        assert _last_played_seat(hand) == 3

    def test_no_tricks_at_all(self):
        """No active trick plays AND no completed tricks → None."""
        hand = _HandStub(
            current_trick=TrickState(leader=0, plays=[]),
            completed_tricks=[],
        )
        assert _last_played_seat(hand) is None

    def test_none_trick_no_completed(self):
        """current_trick is None and no completed tricks → None."""
        hand = _HandStub(current_trick=None, completed_tricks=[])
        assert _last_played_seat(hand) is None


# ---------------------------------------------------------------------------
# ai_just_played gate tests (via _build_game_context internals)
# ---------------------------------------------------------------------------

# We test the gate logic inline rather than calling _build_game_context
# (which requires a full engine/state). The gate is:
#
#   ai_just_played = (
#       hand.phase == "trick_play"
#       and (hand.paused_after_play or hand.paused_after_trick)
#       and last_seat is not None
#       and last_seat != HUMAN_SEAT
#   )


def _ai_just_played(hand) -> bool:
    """Replicate the ai_just_played gate logic from _build_game_context."""
    last_seat = _last_played_seat(hand)
    return (
        hand.phase == "trick_play"
        and (hand.paused_after_play or hand.paused_after_trick)
        and last_seat is not None
        and last_seat != HUMAN_SEAT
    )


class TestAiJustPlayedPausedAfterPlay:
    """Regression: paused_after_play still works (original behavior)."""

    def test_ai_mid_trick(self):
        hand = _HandStub(
            phase="trick_play",
            current_trick=TrickState(
                leader=1,
                plays=[(1, _card("A", "S"))],
            ),
            paused_after_play=True,
        )
        assert _ai_just_played(hand) is True

    def test_human_mid_trick(self):
        hand = _HandStub(
            phase="trick_play",
            current_trick=TrickState(
                leader=0,
                plays=[(HUMAN_SEAT, _card("A", "S"))],
            ),
            paused_after_play=True,
        )
        assert _ai_just_played(hand) is False

    def test_not_paused(self):
        hand = _HandStub(
            phase="trick_play",
            current_trick=TrickState(
                leader=1,
                plays=[(1, _card("A", "S"))],
            ),
            paused_after_play=False,
            paused_after_trick=False,
        )
        assert _ai_just_played(hand) is False


class TestAiJustPlayedPausedAfterTrick:
    """New behavior: ai_just_played fires at trick boundary too."""

    def test_ai_completes_trick_active_empty(self):
        """AI played the 4th card, trick moved to completed list."""
        completed = _make_completed_trick(
            plays=[
                (HUMAN_SEAT, _card("A", "S")),
                (AI_SEAT_1, _card("K", "S")),
                (2, _card("Q", "S")),
                (AI_SEAT_2, _card("10", "S")),
            ],
            winner=HUMAN_SEAT,
        )
        hand = _HandStub(
            phase="trick_play",
            current_trick=TrickState(leader=HUMAN_SEAT, plays=[]),
            completed_tricks=[completed],
            paused_after_trick=True,
        )
        # Last play was seat 3 (AI) → ai_just_played should be True
        assert _last_played_seat(hand) == AI_SEAT_2
        assert _ai_just_played(hand) is True

    def test_human_completes_trick(self):
        """Human played the 4th card — ai_just_played should be False."""
        completed = _make_completed_trick(
            plays=[
                (AI_SEAT_1, _card("A", "S")),
                (2, _card("K", "S")),
                (AI_SEAT_2, _card("Q", "S")),
                (HUMAN_SEAT, _card("10", "S")),
            ],
            winner=AI_SEAT_1,
        )
        hand = _HandStub(
            phase="trick_play",
            current_trick=TrickState(leader=AI_SEAT_1, plays=[]),
            completed_tricks=[completed],
            paused_after_trick=True,
        )
        assert _last_played_seat(hand) == HUMAN_SEAT
        assert _ai_just_played(hand) is False

    def test_wrong_phase(self):
        """paused_after_trick in complete phase → not ai_just_played."""
        completed = _make_completed_trick(
            plays=[
                (HUMAN_SEAT, _card("A", "S")),
                (AI_SEAT_1, _card("K", "S")),
                (2, _card("Q", "S")),
                (AI_SEAT_2, _card("10", "S")),
            ],
            winner=HUMAN_SEAT,
        )
        hand = _HandStub(
            phase="complete",
            current_trick=None,
            completed_tricks=[completed],
            paused_after_trick=True,
        )
        assert _ai_just_played(hand) is False
