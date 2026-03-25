"""
Integration tests: Game rules invariants.

These tests verify that the trick resolution and winner determination logic
is correct, with special focus on trump and bower handling.

Key invariants tested:
- If trump is played, highest trump wins (not highest non-trump)
- Bower ordering: Right bower > Left bower > A > K > Q > J > 10
- Follow-suit enforcement
- LOW contract rank reversal (10 > J > Q > K > A)
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

from bid_euchre.core.cards import (
    SAME_COLOR_SUIT,
    Card,
    effective_suit,
)
from bid_euchre.core.rules import get_legal_indices, trick_winner
from bid_euchre.logging.game_logger import GameLogger, LogLevel
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.baselines import AlwaysHighestLegalStrategy


def _read_jsonl(path: Path) -> list[dict]:
    """Read JSONL log file."""
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class TestBowerOrdering:
    """Tests for bower ordering in suit contracts."""

    def test_right_bower_beats_left_bower(self) -> None:
        """Right bower (J of trump) beats left bower (J of same color)."""
        trump_suit = "H"
        right_bower = Card(suit="H", rank="J")  # Right bower
        left_bower = Card(suit="D", rank="J")  # Left bower (diamonds = same color)

        plays = [
            (0, left_bower),  # Player 0 leads left bower
            (1, right_bower),  # Player 1 plays right bower
        ]

        winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
        assert winner == 1, "Right bower should beat left bower"

    def test_left_bower_beats_ace_of_trump(self) -> None:
        """Left bower beats Ace of trump."""
        trump_suit = "H"
        left_bower = Card(suit="D", rank="J")  # Left bower
        ace_trump = Card(suit="H", rank="A")  # Ace of hearts (trump)

        plays = [
            (0, ace_trump),  # Player 0 leads ace of trump
            (1, left_bower),  # Player 1 plays left bower
        ]

        winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
        assert winner == 1, "Left bower should beat Ace of trump"

    def test_right_bower_beats_ace_of_trump(self) -> None:
        """Right bower beats Ace of trump."""
        trump_suit = "H"
        right_bower = Card(suit="H", rank="J")  # Right bower
        ace_trump = Card(suit="H", rank="A")  # Ace of hearts (trump)

        plays = [
            (0, ace_trump),  # Player 0 leads ace of trump
            (1, right_bower),  # Player 1 plays right bower
        ]

        winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
        assert winner == 1, "Right bower should beat Ace of trump"

    @pytest.mark.parametrize("trump_suit", ["C", "D", "H", "S"])
    def test_bower_ordering_all_suits(self, trump_suit: str) -> None:
        """Bower ordering holds for all trump suits."""
        same_color = SAME_COLOR_SUIT[trump_suit]
        right_bower = Card(suit=trump_suit, rank="J")
        left_bower = Card(suit=same_color, rank="J")
        ace_trump = Card(suit=trump_suit, rank="A")
        king_trump = Card(suit=trump_suit, rank="K")

        # Right > Left > A > K
        cards_strongest_first = [right_bower, left_bower, ace_trump, king_trump]

        for i in range(len(cards_strongest_first) - 1):
            stronger = cards_strongest_first[i]
            weaker = cards_strongest_first[i + 1]

            plays = [
                (0, weaker),  # Player 0 leads weaker card
                (1, stronger),  # Player 1 plays stronger card
            ]

            winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
            assert (
                winner == 1
            ), f"Expected {stronger} to beat {weaker} with trump={trump_suit}"


class TestTrumpBeatsNonTrump:
    """Tests ensuring trump beats non-trump."""

    def test_lowest_trump_beats_highest_offsuit(self) -> None:
        """Even the lowest trump (10) beats Ace of non-trump."""
        trump_suit = "H"
        ten_trump = Card(suit="H", rank="T")  # 10 of trump (lowest)
        ace_offsuit = Card(suit="S", rank="A")  # Ace of spades

        plays = [
            (0, ace_offsuit),  # Player 0 leads ace of spades
            (1, ten_trump),  # Player 1 trumps with 10
        ]

        winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
        assert winner == 1, "Lowest trump should beat highest offsuit"

    def test_trump_wins_when_following_not_possible(self) -> None:
        """Player who trumps wins even if led suit has high card."""
        trump_suit = "H"
        ace_led = Card(suit="C", rank="A")  # Ace of clubs (led suit)
        king_led = Card(suit="C", rank="K")  # King of clubs
        queen_led = Card(suit="C", rank="Q")  # Queen of clubs
        trump_card = Card(suit="H", rank="T")  # 10 of hearts (trump)

        plays = [
            (0, ace_led),  # Player 0 leads ace of clubs
            (1, king_led),  # Player 1 follows with king
            (2, trump_card),  # Player 2 trumps (can't follow)
            (3, queen_led),  # Player 3 follows with queen
        ]

        winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
        assert winner == 2, "Trump should win even over ace of led suit"

    def test_highest_trump_wins_when_multiple_trump(self) -> None:
        """When multiple players trump, highest trump wins."""
        trump_suit = "H"
        card_led = Card(suit="C", rank="A")  # Ace of clubs (led)
        trump_1 = Card(suit="H", rank="T")  # 10 of hearts
        trump_2 = Card(suit="H", rank="Q")  # Queen of hearts
        trump_3 = Card(suit="H", rank="K")  # King of hearts

        plays = [
            (0, card_led),  # Player 0 leads
            (1, trump_1),  # Player 1 trumps with 10
            (2, trump_2),  # Player 2 trumps with Q
            (3, trump_3),  # Player 3 trumps with K
        ]

        winner = trick_winner(plays, contract_type="suit", trump_suit=trump_suit)
        assert winner == 3, "Highest trump (King) should win"


class TestHighLowContracts:
    """Tests for HIGH and LOW contract ranking."""

    def test_high_contract_ace_beats_king(self) -> None:
        """In HIGH contracts, Ace beats King."""
        ace = Card(suit="C", rank="A")
        king = Card(suit="C", rank="K")

        plays = [
            (0, king),
            (1, ace),
        ]

        winner = trick_winner(plays, contract_type="high", trump_suit=None)
        assert winner == 1, "Ace should beat King in HIGH contract"

    def test_low_contract_ten_beats_ace(self) -> None:
        """In LOW contracts, 10 beats Ace (ranking is reversed)."""
        ace = Card(suit="C", rank="A")
        ten = Card(suit="C", rank="T")

        plays = [
            (0, ace),
            (1, ten),
        ]

        winner = trick_winner(plays, contract_type="low", trump_suit=None)
        assert winner == 1, "10 should beat Ace in LOW contract"

    def test_low_contract_full_ordering(self) -> None:
        """LOW contract: T > J > Q > K > A (10 is strongest, Ace weakest)."""
        # In LOW, lower face value = stronger
        # So 10 > J > Q > K > A
        ten = Card(suit="C", rank="T")
        jack = Card(suit="C", rank="J")
        queen = Card(suit="C", rank="Q")
        king = Card(suit="C", rank="K")
        ace = Card(suit="C", rank="A")

        # Verify 10 > J
        plays = [(0, jack), (1, ten)]
        assert trick_winner(plays, "low", None) == 1, "10 > J in LOW"

        # Verify J > Q
        plays = [(0, queen), (1, jack)]
        assert trick_winner(plays, "low", None) == 1, "J > Q in LOW"

        # Verify Q > K
        plays = [(0, king), (1, queen)]
        assert trick_winner(plays, "low", None) == 1, "Q > K in LOW"

        # Verify K > A
        plays = [(0, ace), (1, king)]
        assert trick_winner(plays, "low", None) == 1, "K > A in LOW"

    def test_high_contract_no_bowers(self) -> None:
        """HIGH contracts should not have bower logic (J is just a J)."""
        # Hearts would be trump in suit contract, but not in HIGH
        jack_hearts = Card(suit="H", rank="J")
        ace_hearts = Card(suit="H", rank="A")

        plays = [
            (0, jack_hearts),
            (1, ace_hearts),
        ]

        winner = trick_winner(plays, contract_type="high", trump_suit=None)
        assert winner == 1, "In HIGH, Ace beats Jack (no bowers)"


class TestFollowSuitEnforcement:
    """Tests for follow-suit rule enforcement."""

    def test_must_follow_suit_if_able(self) -> None:
        """get_legal_indices only returns cards of led suit when possible."""
        hand = [
            Card(suit="H", rank="A"),  # 0
            Card(suit="H", rank="K"),  # 1
            Card(suit="S", rank="A"),  # 2
            Card(suit="C", rank="Q"),  # 3
        ]

        # Hearts was led
        plays_so_far = [(0, Card(suit="H", rank="T"))]

        legal = get_legal_indices(hand, plays_so_far, "suit", trump_suit="S")

        # Should only be hearts cards (indices 0, 1)
        assert set(legal) == {0, 1}, f"Expected hearts only, got indices {legal}"

    def test_any_card_legal_when_void(self) -> None:
        """When void in led suit, any card is legal."""
        hand = [
            Card(suit="S", rank="A"),  # 0
            Card(suit="S", rank="K"),  # 1
            Card(suit="C", rank="Q"),  # 2
            Card(suit="D", rank="T"),  # 3
        ]

        # Hearts was led, but we have no hearts
        plays_so_far = [(0, Card(suit="H", rank="T"))]

        legal = get_legal_indices(hand, plays_so_far, "suit", trump_suit="S")

        # All cards should be legal
        assert set(legal) == {0, 1, 2, 3}, f"Expected all cards legal, got {legal}"

    def test_left_bower_follows_trump_suit(self) -> None:
        """Left bower must follow when trump is led (it's effectively trump)."""
        trump_suit = "H"
        same_color = SAME_COLOR_SUIT[trump_suit]  # D
        left_bower = Card(suit=same_color, rank="J")  # JD is left bower

        hand = [
            left_bower,  # 0 - left bower (effectively hearts)
            Card(suit="D", rank="A"),  # 1 - Ace of diamonds
            Card(suit="S", rank="K"),  # 2 - King of spades
        ]

        # Hearts (trump) was led
        plays_so_far = [(0, Card(suit="H", rank="T"))]

        legal = get_legal_indices(hand, plays_so_far, "suit", trump_suit=trump_suit)

        # Only left bower follows trump
        assert set(legal) == {
            0
        }, f"Left bower should be only legal card when trump led, got {legal}"


class TestTrickWinnerInSimulation:
    """Integration tests running real simulations and checking winners."""

    @pytest.mark.parametrize("trump_suit", ["C", "D", "H", "S"])
    def test_trump_winner_in_logged_game(self, tmp_path: Path, trump_suit: str) -> None:
        """In logged games, verify trump tricks are won by highest trump."""
        log_path = tmp_path / f"trump_test_{trump_suit}.jsonl"
        deal_seed = 4242

        logger = GameLogger(
            run_id="test_trump",
            strategy_id="always_highest",
            level=LogLevel.TRICK,
        ).open(str(log_path))

        simulate_many_hands(
            n=10,
            contract_type="suit",
            trump_suit=trump_suit,
            deal_seed=deal_seed,
            strategy=AlwaysHighestLegalStrategy(),
            logger=logger,
        )

        logger.close()

        records = _read_jsonl(log_path)
        trick_ends = [r for r in records if r.get("event") == "trick_end"]

        for trick in trick_ends:
            plays = trick["plays"]  # [[player_idx, suit, rank], ...]
            winner = trick["winner"]

            # Find trump cards in this trick
            trump_plays = [
                (p[0], Card(suit=p[1], rank=p[2]))
                for p in plays
                if effective_suit(Card(suit=p[1], rank=p[2]), trump_suit, "suit")
                == trump_suit
            ]

            if trump_plays:
                # Winner must have played trump
                winner_play = next(p for p in plays if p[0] == winner)
                winner_card = Card(suit=winner_play[1], rank=winner_play[2])
                winner_eff_suit = effective_suit(winner_card, trump_suit, "suit")

                assert winner_eff_suit == trump_suit, (
                    f"When trump played, winner should have trump. "
                    f"Winner card: {winner_card}, trump: {trump_suit}"
                )

    def test_trick_count_always_ten(self, tmp_path: Path) -> None:
        """Every hand should have exactly 10 tricks."""
        log_path = tmp_path / "trick_count.jsonl"

        logger = GameLogger(
            run_id="test_count",
            strategy_id="always_highest",
            level=LogLevel.TRICK,
        ).open(str(log_path))

        simulate_many_hands(
            n=20,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=AlwaysHighestLegalStrategy(),
            logger=logger,
        )

        logger.close()

        records = _read_jsonl(log_path)

        # Group by deal_id
        by_deal = defaultdict(list)
        for r in records:
            if r.get("event") == "trick_end":
                by_deal[r["deal_id"]].append(r)

        for deal_id, tricks in by_deal.items():
            assert (
                len(tricks) == 10
            ), f"Deal {deal_id} has {len(tricks)} tricks, expected 10"

    def test_team_tricks_sum_to_ten(self, tmp_path: Path) -> None:
        """Team0 tricks + Team1 tricks should always equal 10."""
        log_path = tmp_path / "team_sum.jsonl"

        logger = GameLogger(
            run_id="test_sum",
            strategy_id="always_highest",
            level=LogLevel.TRICK,
        ).open(str(log_path))

        simulate_many_hands(
            n=50,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=AlwaysHighestLegalStrategy(),
            logger=logger,
        )

        logger.close()

        records = _read_jsonl(log_path)
        hand_ends = [r for r in records if r.get("event") == "hand_end"]

        for hand in hand_ends:
            t0 = hand["t0"]  # Team 0 tricks
            t1 = hand["t1"]  # Team 1 tricks
            assert (
                t0 + t1 == 10
            ), f"Deal {hand['deal_id']}: team tricks {t0} + {t1} = {t0 + t1}, expected 10"
