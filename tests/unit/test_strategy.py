import pytest
import os

from bid_euchre.core.cards import Card
from bid_euchre.strategy import (
    choose_card_basic,
    choose_card_greedy,
    card_value_for_dump,
)


class TestChooseCardBasic:
    """Test the basic strategy implementation."""

    def test_choose_card_basic_follow_suit(self):
        """Test that basic strategy follows suit when possible."""
        hand = [
            Card("H", "T"),  # 10 of hearts (lowest)
            Card("H", "K"),  # King of hearts (highest)
            Card("S", "A"),  # Ace of spades (offsuit)
        ]

        # Hearts led, should play lowest heart
        plays_so_far = [(0, Card("H", "Q"))]  # Opponent led hearts
        choice = choose_card_basic(hand, plays_so_far, "high", None, 1)
        assert choice == 0  # Index of 10 of hearts (lowest)

    def test_choose_card_basic_cannot_follow_suit(self):
        """Test that basic strategy plays lowest card when can't follow suit."""
        hand = [
            Card("S", "A"),  # Ace of spades (highest)
            Card("S", "T"),  # 10 of spades (lowest)
            Card("D", "K"),  # King of diamonds (offsuit)
        ]

        # Hearts led, cannot follow
        plays_so_far = [(0, Card("H", "Q"))]  # Opponent led hearts
        choice = choose_card_basic(hand, plays_so_far, "high", None, 1)
        assert choice == 1  # Index of 10 of spades (lowest)

    def test_choose_card_basic_on_lead(self):
        """Test that basic strategy plays lowest card on lead."""
        hand = [
            Card("S", "A"),  # Ace of spades
            Card("H", "T"),  # 10 of hearts (lowest)
            Card("D", "K"),  # King of diamonds
        ]

        # On lead (no plays so far)
        choice = choose_card_basic(hand, [], "high", None, 1)
        assert choice == 1  # Index of 10 of hearts (lowest)


class TestChooseCardGreedy:
    """Test the greedy strategy implementation."""

    def test_choose_card_greedy_winning_play(self):
        """Test that greedy strategy chooses winning plays when available."""
        hand = [
            Card("H", "T"),  # 10 of hearts
            Card("H", "A"),  # Ace of hearts (winning card)
            Card("S", "K"),  # King of spades (offsuit)
        ]

        # Opponent led low heart
        plays_so_far = [(0, Card("H", "Q"))]  # Queen of hearts led
        choice = choose_card_greedy(hand, plays_so_far, "high", None, 1)

        # Should choose Ace of hearts (winning card)
        assert choice == 1

    def test_choose_card_greedy_must_follow_suit(self):
        """Test that greedy strategy follows suit even when losing."""
        hand = [
            Card("H", "T"),  # 10 of hearts (must follow suit)
            Card("S", "A"),  # Ace of spades (expensive offsuit)
            Card("D", "J"),  # Jack of diamonds (cheapest)
        ]

        # Opponent led high heart - must follow suit
        plays_so_far = [(0, Card("H", "A"))]  # Ace of hearts led
        choice = choose_card_greedy(hand, plays_so_far, "high", None, 1)

        # Must follow suit with heart, even though it loses
        assert choice == 0  # HT (only heart in hand)

    def test_choose_card_greedy_cheapest_winner(self):
        """Test that greedy chooses cheapest winning card when multiple options."""
        hand = [
            Card("H", "K"),  # King of hearts (expensive winner)
            Card("H", "Q"),  # Queen of hearts (cheaper winner)
            Card("S", "A"),  # Ace of spades (offsuit)
        ]

        # Opponent led low heart
        plays_so_far = [(0, Card("H", "T"))]  # 10 of hearts led
        choice = choose_card_greedy(hand, plays_so_far, "high", None, 1)

        # Both King and Queen win, but Queen is cheaper
        assert choice == 1  # Queen of hearts

    def test_choose_card_greedy_must_follow_suit_trump(self):
        """Test that greedy strategy follows suit in trump contract."""
        hand = [
            Card("H", "A"),  # Ace of hearts (trump)
            Card("H", "T"),  # 10 of hearts (trump)
            Card("S", "T"),  # 10 of spades (follows suit)
        ]

        # Opponent led spades - must follow suit since we have spades
        plays_so_far = [(0, Card("S", "A"))]  # Spades ace led
        choice = choose_card_greedy(hand, plays_so_far, "suit", "H", 1)

        # Must follow suit with the only spade available
        assert choice == 2  # TS (only spade in hand)

    def test_choose_card_greedy_bower_valuation(self):
        """Test that greedy highly values bowers."""
        hand = [
            Card("H", "J"),  # Right bower (very valuable)
            Card("D", "J"),  # Left bower (valuable)
            Card("S", "T"),  # 10 of spades (cheapest)
        ]

        # Cannot follow suit
        plays_so_far = [(0, Card("C", "Q"))]  # Clubs led
        choice = choose_card_greedy(hand, plays_so_far, "suit", "H", 1)

        # Should play cheapest winning card (left bower beats right bower in value)
        assert choice == 1  # JD (left bower, cheaper than JH)


class TestCardValueForDump:
    """Test the card valuation function used by greedy strategy."""

    def test_card_value_regular_cards(self):
        """Test valuation of regular cards."""
        # Higher rank = higher value
        assert card_value_for_dump(Card("H", "T"), "high", None) == 0
        assert card_value_for_dump(Card("H", "J"), "high", None) == 1
        assert card_value_for_dump(Card("H", "A"), "high", None) == 4

    def test_card_value_trump_cards(self):
        """Test that trump cards have higher value."""
        # Trump cards get +10 bonus
        offsuit_ace = card_value_for_dump(Card("H", "A"), "suit", "S")
        trump_ace = card_value_for_dump(Card("S", "A"), "suit", "S")
        assert trump_ace == offsuit_ace + 10

    def test_card_value_bowers(self):
        """Test that bowers have very high value."""
        regular_trump = card_value_for_dump(Card("S", "A"), "suit", "S")
        left_bower = card_value_for_dump(Card("D", "J"), "suit", "H")  # Left bower (Diamonds when Hearts trump)
        right_bower = card_value_for_dump(Card("H", "J"), "suit", "H")  # Right bower

        # Right bower should be most valuable
        assert right_bower > left_bower > regular_trump

    def test_card_value_low_contract(self):
        """Test card valuation in low contracts."""
        # In low contracts, ranking is reversed but valuation still applies
        ace_value = card_value_for_dump(Card("H", "A"), "low", None)
        ten_value = card_value_for_dump(Card("H", "T"), "low", None)
        assert ten_value > ace_value  # 10 is more valuable in low


class TestGreedyPolicyOracle:
    """Validate GreedyStrategy policy matches its intended definition."""

    def test_greedy_on_lead_plays_highest_value(self):
        hand = [
            Card("H", "T"),
            Card("S", "A"),
            Card("H", "A"),
        ]
        # On lead: should play a highest-valued card under contract rules (ties break by first max).
        idx = choose_card_greedy(hand, [], "high", None, 0)
        assert idx == 1
