"""Tests for hosted-play state serialization round-trips and edge cases."""

import json

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.hosted_play import HandState, MatchState, TrickResult, TrickState
from bid_euchre.hosted_play.state import (
    _card_from_data,
    _card_to_data,
    _plays_from_data,
    _plays_to_data,
)

# ---------------------------------------------------------------------------
# Helper-level tests
# ---------------------------------------------------------------------------


class TestCardSerialization:
    """Tests for _card_to_data / _card_from_data helpers."""

    def test_card_round_trip(self) -> None:
        card = Card("H", "A")
        assert _card_from_data(_card_to_data(card)) == card

    def test_card_to_data_format(self) -> None:
        assert _card_to_data(Card("S", "K")) == ["S", "K"]

    def test_card_from_data_accepts_tuple(self) -> None:
        assert _card_from_data(("D", "Q")) == Card("D", "Q")

    def test_card_from_data_rejects_wrong_length(self) -> None:
        with pytest.raises(ValueError, match="length 2"):
            _card_from_data(["H"])

        with pytest.raises(ValueError, match="length 2"):
            _card_from_data(["H", "A", "extra"])


class TestPlaysSerialization:
    """Tests for _plays_to_data / _plays_from_data helpers."""

    def test_plays_round_trip(self) -> None:
        plays = [(0, Card("S", "A")), (2, Card("H", "K"))]
        assert _plays_from_data(_plays_to_data(plays)) == plays

    def test_plays_to_data_format(self) -> None:
        plays = [(1, Card("C", "T"))]
        assert _plays_to_data(plays) == [[1, ["C", "T"]]]

    def test_empty_plays_round_trip(self) -> None:
        assert _plays_from_data(_plays_to_data([])) == []

    def test_plays_from_data_rejects_wrong_item_length(self) -> None:
        with pytest.raises(ValueError, match="length 2"):
            _plays_from_data([[1]])  # missing card


# ---------------------------------------------------------------------------
# TrickState tests
# ---------------------------------------------------------------------------


class TestTrickState:
    """Tests for TrickState serialization."""

    def test_round_trip_with_plays(self) -> None:
        state = TrickState(
            leader=2,
            plays=[(2, Card("H", "A")), (3, Card("H", "Q"))],
        )
        assert TrickState.from_dict(state.to_dict()) == state

    def test_round_trip_empty_plays(self) -> None:
        state = TrickState(leader=0, plays=[])
        assert TrickState.from_dict(state.to_dict()) == state

    def test_to_dict_format(self) -> None:
        state = TrickState(
            leader=1,
            plays=[(1, Card("D", "K"))],
        )
        d = state.to_dict()
        assert d == {
            "leader": 1,
            "plays": [[1, ["D", "K"]]],
        }

    def test_from_dict_missing_plays_defaults_empty(self) -> None:
        """from_dict tolerates a missing 'plays' key."""
        state = TrickState.from_dict({"leader": 3})
        assert state.leader == 3
        assert state.plays == []

    def test_json_serializable(self) -> None:
        """to_dict output must survive json.dumps/loads."""
        state = TrickState(leader=0, plays=[(0, Card("S", "J"))])
        raw = json.dumps(state.to_dict())
        assert TrickState.from_dict(json.loads(raw)) == state


# ---------------------------------------------------------------------------
# TrickResult tests
# ---------------------------------------------------------------------------


class TestTrickResult:
    """Tests for TrickResult serialization."""

    def test_round_trip(self) -> None:
        result = TrickResult(
            leader=1,
            plays=[
                (1, Card("C", "A")),
                (2, Card("C", "K")),
                (3, Card("C", "Q")),
                (0, Card("C", "J")),
            ],
            winner=1,
        )
        assert TrickResult.from_dict(result.to_dict()) == result

    def test_round_trip_empty_plays(self) -> None:
        result = TrickResult(leader=0, plays=[], winner=0)
        assert TrickResult.from_dict(result.to_dict()) == result

    def test_to_dict_format(self) -> None:
        result = TrickResult(
            leader=3,
            plays=[(3, Card("H", "T")), (0, Card("H", "A"))],
            winner=0,
        )
        d = result.to_dict()
        assert d == {
            "leader": 3,
            "plays": [[3, ["H", "T"]], [0, ["H", "A"]]],
            "winner": 0,
        }

    def test_json_serializable(self) -> None:
        result = TrickResult(
            leader=2,
            plays=[(2, Card("D", "A"))],
            winner=2,
        )
        raw = json.dumps(result.to_dict())
        assert TrickResult.from_dict(json.loads(raw)) == result


# ---------------------------------------------------------------------------
# HandState tests
# ---------------------------------------------------------------------------


class TestHandState:
    """Tests for HandState serialization."""

    def test_round_trip_bid_phase_minimal(self) -> None:
        """HandState in bid phase with all optional fields at defaults/None."""
        state = HandState(
            phase="bidding",
            hands=[
                [Card("S", "A"), Card("S", "K")],
                [Card("H", "Q"), Card("H", "J")],
                [Card("D", "T"), Card("D", "A")],
                [Card("C", "K"), Card("C", "Q")],
            ],
            dealer_seat=0,
            deal_id=1,
        )
        assert HandState.from_dict(state.to_dict()) == state

    def test_round_trip_trick_play_phase(self) -> None:
        """HandState mid-trick-play with populated optional fields."""
        state = HandState(
            phase="trick_play",
            hands=[[Card("S", "A")], [], [Card("D", "J")], [Card("C", "T")]],
            dealer_seat=3,
            deal_id=5,
            auction=[
                {"seat": 0, "n": 3, "contract": "H"},
                {"seat": 1, "n": 0, "contract": None},
            ],
            current_high_bid=3,
            bidder_seat=0,
            winning_bid=3,
            contract_type="suit",
            trump="H",
            current_trick=TrickState(leader=2, plays=[]),
            completed_tricks=[
                TrickResult(
                    leader=0,
                    plays=[
                        (0, Card("H", "A")),
                        (1, Card("H", "T")),
                        (2, Card("H", "K")),
                        (3, Card("H", "Q")),
                    ],
                    winner=0,
                ),
            ],
            tricks_team0=1,
            tricks_team1=0,
            points_team0=0,
            points_team1=0,
            current_seat=2,
            turn_number=5,
        )
        assert HandState.from_dict(state.to_dict()) == state

    def test_round_trip_empty_hands(self) -> None:
        """Empty card lists (e.g. all cards played)."""
        state = HandState(
            phase="scoring",
            hands=[[], [], [], []],
            dealer_seat=1,
            deal_id=10,
            tricks_team0=6,
            tricks_team1=4,
            points_team0=6,
            points_team1=-5,
        )
        assert HandState.from_dict(state.to_dict()) == state

    def test_round_trip_no_trump_contracts(self) -> None:
        """High/low contracts have contract_type set but trump is None."""
        for ct in ("high", "low"):
            state = HandState(
                phase="trick_play",
                hands=[[Card("S", "A")], [Card("H", "K")], [], []],
                dealer_seat=2,
                deal_id=7,
                winning_bid=4,
                bidder_seat=1,
                contract_type=ct,
                trump=None,
            )
            restored = HandState.from_dict(state.to_dict())
            assert restored == state
            assert restored.contract_type == ct
            assert restored.trump is None

    def test_to_dict_none_fields_serialize_as_none(self) -> None:
        """Optional None fields round-trip through dict as None, not absent."""
        state = HandState(
            phase="bidding",
            hands=[[Card("S", "A")]],
            dealer_seat=0,
            deal_id=1,
        )
        d = state.to_dict()
        assert d["bidder_seat"] is None
        assert d["winning_bid"] is None
        assert d["contract_type"] is None
        assert d["trump"] is None
        assert d["current_trick"] is None

    def test_from_dict_missing_optional_keys(self) -> None:
        """from_dict handles absent optional keys gracefully."""
        minimal = {
            "phase": "bidding",
            "dealer_seat": 0,
            "deal_id": 1,
        }
        state = HandState.from_dict(minimal)
        assert state.hands == []
        assert state.auction == []
        assert state.current_high_bid == 0
        assert state.bidder_seat is None
        assert state.winning_bid is None
        assert state.contract_type is None
        assert state.trump is None
        assert state.current_trick is None
        assert state.completed_tricks == []

    def test_json_serializable(self) -> None:
        state = HandState(
            phase="bidding",
            hands=[[Card("H", "A"), Card("H", "K")]],
            dealer_seat=0,
            deal_id=1,
            auction=[{"seat": 0, "n": 5, "contract": "H"}],
            current_high_bid=5,
            bidder_seat=0,
        )
        raw = json.dumps(state.to_dict())
        assert HandState.from_dict(json.loads(raw)) == state


# ---------------------------------------------------------------------------
# MatchState tests
# ---------------------------------------------------------------------------


class TestMatchState:
    """Tests for MatchState serialization."""

    def test_round_trip_with_nested_hand_state(self) -> None:
        state = MatchState(
            seed=42,
            ai_model="olsa",
            score_human=12,
            score_ai=-3,
            hands_played=4,
            status="active",
            dealer_seat=2,
            deal_id=9,
            current_hand=HandState(
                phase="trick_play",
                hands=[
                    [Card("S", "A"), Card("H", "K")],
                    [Card("C", "Q")],
                    [Card("D", "J")],
                    [Card("S", "T")],
                ],
                dealer_seat=2,
                deal_id=9,
                auction=[
                    {"seat": 3, "n": 0, "contract": None},
                    {"seat": 0, "n": 5, "contract": "S"},
                ],
                current_high_bid=5,
                bidder_seat=0,
                winning_bid=5,
                contract_type="suit",
                trump="S",
                current_trick=TrickState(
                    leader=0,
                    plays=[(0, Card("S", "A")), (1, Card("C", "Q"))],
                ),
                completed_tricks=[
                    TrickResult(
                        leader=3,
                        plays=[
                            (3, Card("H", "A")),
                            (0, Card("H", "K")),
                            (1, Card("H", "Q")),
                            (2, Card("H", "J")),
                        ],
                        winner=3,
                    )
                ],
                tricks_team0=1,
                tricks_team1=0,
                points_team0=0,
                points_team1=0,
                current_seat=2,
                turn_number=6,
            ),
        )

        restored = MatchState.from_dict(state.to_dict())

        assert restored == state

    def test_round_trip_without_current_hand(self) -> None:
        state = MatchState(
            seed=7,
            ai_model="heuristic",
            score_human=52,
            score_ai=18,
            hands_played=11,
            current_hand=None,
            status="complete",
            winner="human",
            dealer_seat=1,
            deal_id=11,
        )

        restored = MatchState.from_dict(state.to_dict())

        assert restored == state

    def test_round_trip_defaults_only(self) -> None:
        """MatchState with only required fields; everything else is default."""
        state = MatchState(seed=1, ai_model="heuristic")
        restored = MatchState.from_dict(state.to_dict())
        assert restored == state
        assert restored.score_human == 0
        assert restored.score_ai == 0
        assert restored.hands_played == 0
        assert restored.current_hand is None
        assert restored.status == "active"
        assert restored.winner is None

    def test_round_trip_negative_scores(self) -> None:
        """Negative scores (from being set) serialize correctly."""
        state = MatchState(
            seed=99,
            ai_model="heuristic",
            score_human=-8,
            score_ai=-3,
            hands_played=2,
        )
        restored = MatchState.from_dict(state.to_dict())
        assert restored == state
        assert restored.score_human == -8
        assert restored.score_ai == -3

    def test_to_dict_format(self) -> None:
        state = MatchState(seed=10, ai_model="heuristic", status="abandoned")
        d = state.to_dict()
        assert d["seed"] == 10
        assert d["ai_model"] == "heuristic"
        assert d["status"] == "abandoned"
        assert d["current_hand"] is None
        assert d["winner"] is None

    def test_from_dict_missing_optional_keys(self) -> None:
        """from_dict handles absent optional keys with sensible defaults."""
        minimal = {"seed": 5, "ai_model": "heuristic"}
        state = MatchState.from_dict(minimal)
        assert state.score_human == 0
        assert state.score_ai == 0
        assert state.hands_played == 0
        assert state.current_hand is None
        assert state.status == "active"
        assert state.winner is None
        assert state.dealer_seat == 0
        assert state.deal_id == 0

    def test_json_serializable(self) -> None:
        """Full MatchState with nested hand survives json.dumps/loads."""
        state = MatchState(
            seed=42,
            ai_model="olsa",
            score_human=5,
            score_ai=3,
            hands_played=2,
            current_hand=HandState(
                phase="bidding",
                hands=[[Card("S", "A")]],
                dealer_seat=0,
                deal_id=3,
            ),
        )
        raw = json.dumps(state.to_dict())
        assert MatchState.from_dict(json.loads(raw)) == state

    def test_round_trip_all_match_statuses(self) -> None:
        """All valid match status values round-trip correctly."""
        for status in ("active", "complete", "abandoned"):
            state = MatchState(seed=1, ai_model="heuristic", status=status)
            assert MatchState.from_dict(state.to_dict()).status == status
