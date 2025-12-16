"""
Tests for null baseline strategies (RandomLegal, AlwaysLowest, AlwaysHighest).
"""

import pytest
from bid_euchre.core.cards import Card
from bid_euchre.strategy import (
    RandomLegalStrategy,
    AlwaysLowestLegalStrategy,
    AlwaysHighestLegalStrategy,
)


class TestRandomLegalStrategy:
    """Tests for RandomLegalStrategy."""

    def test_chooses_legal_card(self):
        """RandomLegal should always choose a legal card."""
        strategy = RandomLegalStrategy(seed=42)
        hand = [
            Card("C", "A"),
            Card("D", "K"),
            Card("H", "T"),
            Card("S", "Q"),
        ]
        
        # Leading - all cards legal
        plays_so_far = []
        for _ in range(10):
            choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
            assert 0 <= choice < len(hand)
    
    def test_deterministic_with_seed(self):
        """Same seed should produce same results."""
        hand = [Card("C", "A"), Card("D", "K"), Card("H", "T"), Card("S", "Q")]
        plays_so_far = []
        
        strategy1 = RandomLegalStrategy(seed=42)
        strategy2 = RandomLegalStrategy(seed=42)
        
        choice1 = strategy1.choose_card(hand, plays_so_far, "suit", "H", 0)
        choice2 = strategy2.choose_card(hand, plays_so_far, "suit", "H", 0)
        
        assert choice1 == choice2
    
    def test_different_seeds_different_results(self):
        """Different seeds should produce different distributions."""
        hand = [Card("C", "A"), Card("D", "K"), Card("H", "T"), Card("S", "Q")]
        plays_so_far = []
        
        strategy1 = RandomLegalStrategy(seed=42)
        strategy2 = RandomLegalStrategy(seed=99)
        
        choices1 = [strategy1.choose_card(hand, plays_so_far, "suit", "H", 0) for _ in range(100)]
        choices2 = [strategy2.choose_card(hand, plays_so_far, "suit", "H", 0) for _ in range(100)]
        
        # Should be different distributions (with high probability)
        assert choices1 != choices2


class TestAlwaysLowestLegalStrategy:
    """Tests for AlwaysLowestLegalStrategy."""

    def test_chooses_lowest_offsuit(self):
        """Should choose lowest offsuit card when leading."""
        strategy = AlwaysLowestLegalStrategy()
        hand = [
            Card("C", "A"),  # idx 0
            Card("D", "T"),  # idx 1 - LOWEST
            Card("H", "K"),  # idx 2
            Card("S", "Q"),  # idx 3
        ]
        
        # Leading - all legal, should choose lowest (D-T)
        plays_so_far = []
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice == 1  # D-T
    
    def test_avoids_trump_when_possible(self):
        """Should avoid playing trump if offsuit available."""
        strategy = AlwaysLowestLegalStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace (high)
            Card("D", "T"),  # idx 1 - offsuit T (lowest)
            Card("D", "K"),  # idx 2 - offsuit K
            Card("D", "Q"),  # idx 3 - offsuit Q
        ]
        
        # Leading - should choose lowest offsuit (D-T), not trump
        plays_so_far = []
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice == 1  # D-T (lowest offsuit)
    
    def test_avoids_bowers(self):
        """Should avoid playing bowers if possible."""
        strategy = AlwaysLowestLegalStrategy()
        hand = [
            Card("H", "J"),  # idx 0 - Right bower (strongest)
            Card("D", "J"),  # idx 1 - Left bower (2nd strongest)
            Card("C", "T"),  # idx 2 - offsuit T (LOWEST)
            Card("S", "A"),  # idx 3 - offsuit A
        ]
        
        # Leading - should choose lowest offsuit (C-T)
        plays_so_far = []
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice == 2  # C-T


class TestAlwaysHighestLegalStrategy:
    """Tests for AlwaysHighestLegalStrategy."""

    def test_chooses_highest_card(self):
        """Should choose highest card when leading."""
        strategy = AlwaysHighestLegalStrategy()
        hand = [
            Card("C", "A"),  # idx 0 - HIGHEST (A)
            Card("D", "T"),  # idx 1
            Card("H", "K"),  # idx 2
            Card("S", "Q"),  # idx 3
        ]
        
        # Leading - should choose highest (C-A)
        plays_so_far = []
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice == 0  # C-A
    
    def test_prefers_bowers(self):
        """Should prefer playing bowers over other cards."""
        strategy = AlwaysHighestLegalStrategy()
        hand = [
            Card("H", "J"),  # idx 0 - Right bower (STRONGEST)
            Card("D", "J"),  # idx 1 - Left bower
            Card("H", "A"),  # idx 2 - Trump Ace
            Card("S", "A"),  # idx 3 - Offsuit Ace
        ]
        
        # Leading - should choose right bower
        plays_so_far = []
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice == 0  # Right bower
    
    def test_prefers_trump_over_offsuit(self):
        """Should prefer trump over offsuit when leading."""
        strategy = AlwaysHighestLegalStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace (STRONGEST non-bower)
            Card("D", "A"),  # idx 1 - Offsuit Ace
            Card("C", "A"),  # idx 2 - Offsuit Ace
            Card("S", "A"),  # idx 3 - Offsuit Ace
        ]
        
        # Leading - should choose trump ace over offsuit aces
        plays_so_far = []
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice == 0  # H-A (trump)


class TestNullStrategyIntegration:
    """Integration tests for null strategies."""

    def test_all_strategies_respect_suit_following(self):
        """All strategies must follow suit when required."""
        strategies = [
            RandomLegalStrategy(seed=42),
            AlwaysLowestLegalStrategy(),
            AlwaysHighestLegalStrategy(),
        ]
        
        hand = [
            Card("H", "A"),  # idx 0 - Hearts (trump)
            Card("C", "K"),  # idx 1 - Clubs
            Card("C", "T"),  # idx 2 - Clubs
            Card("S", "Q"),  # idx 3 - Spades
        ]
        
        # Clubs led - must follow suit
        plays_so_far = [(0, Card("C", "A"))]  # Clubs led
        
        for strategy in strategies:
            choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
            # Must choose one of the two clubs (idx 1 or 2)
            assert choice in [1, 2], f"{strategy.name} failed to follow suit"
    
    def test_strategies_differ_in_behavior(self):
        """Different strategies should make different choices."""
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("C", "T"),  # idx 2 - Offsuit T
            Card("S", "K"),  # idx 3 - Offsuit K
        ]
        
        plays_so_far = []  # Leading
        
        # AlwaysLowest should choose C-T
        lowest = AlwaysLowestLegalStrategy()
        assert lowest.choose_card(hand, plays_so_far, "suit", "H", 0) == 2
        
        # AlwaysHighest should choose H-J
        highest = AlwaysHighestLegalStrategy()
        assert highest.choose_card(hand, plays_so_far, "suit", "H", 0) == 0

