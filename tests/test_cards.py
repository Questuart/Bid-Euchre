import pytest
import os
from collections import Counter

from bid_euchre.core.cards import (
    Card, create_deck, shuffle_deck, deal_hands,
    is_right_bower, is_left_bower, effective_suit, rank_strength,
    SUITS, RANKS, SAME_COLOR_SUIT
)


class TestCardClass:
    """Test the Card dataclass functionality."""

    def test_card_creation(self):
        """Test basic card creation and properties."""
        card = Card("H", "A")
        assert card.suit == "H"
        assert card.rank == "A"
        assert str(card) == "AH"
        assert repr(card) == "AH"

    def test_card_immutability(self):
        """Test that Card objects are immutable (frozen dataclass)."""
        card = Card("H", "A")
        with pytest.raises(AttributeError):
            card.suit = "S"

    def test_card_equality(self):
        """Test card equality comparison."""
        card1 = Card("H", "A")
        card2 = Card("H", "A")
        card3 = Card("S", "A")
        assert card1 == card2
        assert card1 != card3


class TestDeckOperations:
    """Test deck creation, shuffling, and dealing."""

    def test_deck_creation(self):
        """Test that create_deck produces correct deck."""
        deck = create_deck()

        # Should have 40 cards (4 suits × 5 ranks × 2 copies)
        assert len(deck) == 40

        # Check that we have exactly 2 of each card
        card_counts = Counter(str(card) for card in deck)
        for suit in SUITS:
            for rank in RANKS:
                card_str = f"{rank}{suit}"
                assert card_counts[card_str] == 2, f"Card {card_str} should appear exactly 2 times"

    def test_deck_contains_valid_cards_only(self):
        """Test that deck only contains valid cards."""
        deck = create_deck()
        for card in deck:
            assert card.suit in SUITS
            assert card.rank in RANKS

    def test_shuffle_deck(self):
        """Test that shuffle_deck modifies the deck in place."""
        deck1 = create_deck()
        deck2 = create_deck()

        # Decks should be identical before shuffling
        assert deck1 == deck2

        # Shuffle one deck
        shuffle_deck(deck1)

        # After shuffling, order should be different (with very high probability)
        # Note: This could theoretically fail, but probability is negligible
        assert deck1 != deck2

    def test_deal_hands(self):
        """Test hand dealing functionality."""
        deck = create_deck()
        hands = deal_hands(deck, num_players=4, hand_size=10)

        # Should have 4 hands
        assert len(hands) == 4

        # Each hand should have 10 cards
        for hand in hands:
            assert len(hand) == 10

        # In double deck Bid Euchre, each card should appear exactly twice
        all_cards = [card for hand in hands for card in hand]
        card_counts = {}
        for card in all_cards:
            card_str = str(card)
            card_counts[card_str] = card_counts.get(card_str, 0) + 1

        # Each of the 20 unique card types should appear exactly twice
        assert len(card_counts) == 20  # 4 suits * 5 ranks
        assert all(count == 2 for count in card_counts.values())

    def test_deal_hands_insufficient_cards(self):
        """Test that dealing fails when not enough cards."""
        small_deck = create_deck()[:30]  # Only 30 cards
        with pytest.raises(ValueError, match="Not enough cards"):
            deal_hands(small_deck, num_players=4, hand_size=10)


class TestBowerLogic:
    """Test bower (jack) mechanics."""

    def test_right_bower_detection(self):
        """Test right bower (jack of trump suit) detection."""
        # Right bower for hearts
        assert is_right_bower(Card("H", "J"), "H") == True
        assert is_right_bower(Card("H", "J"), "S") == False
        assert is_right_bower(Card("S", "J"), "H") == False
        assert is_right_bower(Card("H", "Q"), "H") == False

    def test_left_bower_detection(self):
        """Test left bower (jack of same-color suit) detection."""
        # Left bower for hearts is diamonds (same color)
        assert is_left_bower(Card("D", "J"), "H") == True
        assert is_left_bower(Card("H", "J"), "H") == False  # Right, not left
        assert is_left_bower(Card("D", "J"), "S") == False  # Wrong trump
        assert is_left_bower(Card("D", "Q"), "H") == False  # Wrong rank

    def test_same_color_suit_mapping(self):
        """Test the same-color suit mapping for bowers."""
        assert SAME_COLOR_SUIT["H"] == "D"
        assert SAME_COLOR_SUIT["D"] == "H"
        assert SAME_COLOR_SUIT["S"] == "C"
        assert SAME_COLOR_SUIT["C"] == "S"


class TestEffectiveSuit:
    """Test effective suit determination."""

    def test_effective_suit_no_trump(self):
        """Test effective suit when no trump suit."""
        card = Card("H", "A")
        assert effective_suit(card, None, "high") == "H"
        assert effective_suit(card, None, "low") == "H"

    def test_effective_suit_with_trump_regular_card(self):
        """Test effective suit for regular cards in trump contracts."""
        card = Card("H", "A")
        assert effective_suit(card, "S", "suit") == "H"  # Not a bower

    def test_effective_suit_right_bower(self):
        """Test that right bower takes trump suit."""
        right_bower = Card("H", "J")
        assert effective_suit(right_bower, "H", "suit") == "H"

    def test_effective_suit_left_bower(self):
        """Test that left bower takes trump suit."""
        left_bower = Card("D", "J")  # Left bower when hearts are trump
        assert effective_suit(left_bower, "H", "suit") == "H"


class TestRankStrength:
    """Test rank strength calculations."""

    def test_rank_strength_high_contract(self):
        """Test rank ordering for 'high' contracts."""
        # In high contracts: T < J < Q < K < A
        assert rank_strength(Card("H", "T"), "high") == 0
        assert rank_strength(Card("H", "J"), "high") == 1
        assert rank_strength(Card("H", "Q"), "high") == 2
        assert rank_strength(Card("H", "K"), "high") == 3
        assert rank_strength(Card("H", "A"), "high") == 4

    def test_rank_strength_low_contract(self):
        """Test rank ordering for 'low' contracts."""
        # In low contracts: A < K < Q < J < T
        assert rank_strength(Card("H", "A"), "low") == 0
        assert rank_strength(Card("H", "K"), "low") == 1
        assert rank_strength(Card("H", "Q"), "low") == 2
        assert rank_strength(Card("H", "J"), "low") == 3
        assert rank_strength(Card("H", "T"), "low") == 4

    def test_rank_strength_invalid_contract(self):
        """Test that invalid contract types raise errors."""
        with pytest.raises(ValueError, match="Unknown contract_type"):
            rank_strength(Card("H", "A"), "invalid")
