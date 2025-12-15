import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import trick_winner, _highest_trump, _highest_in_suit


class TestTrickWinner:
    """Test trick winner determination."""

    def test_trick_winner_no_cards(self):
        """Test that empty trick raises error."""
        with pytest.raises(ValueError, match="No cards played"):
            trick_winner([], "suit", "H")

    def test_trick_winner_high_contract(self):
        """Test trick winner in high no-trump contract."""
        plays = [
            (0, Card("H", "T")),  # Player 0: 10 of hearts
            (1, Card("H", "K")),  # Player 1: King of hearts (higher)
            (2, Card("H", "Q")),  # Player 2: Queen of hearts
            (3, Card("S", "A")),  # Player 3: Ace of spades (different suit)
        ]

        # Led suit is hearts, so highest heart wins
        winner = trick_winner(plays, "high", None)
        assert winner == 1  # Player 1 has the highest heart

    def test_trick_winner_low_contract(self):
        """Test trick winner in low no-trump contract."""
        plays = [
            (0, Card("H", "A")),  # Player 0: Ace of hearts (lowest in low contract)
            (1, Card("H", "T")),  # Player 1: 10 of hearts (highest in low contract)
            (2, Card("H", "K")),  # Player 2: King of hearts
            (3, Card("S", "J")),  # Player 3: Jack of spades (different suit)
        ]

        # In low contract, 10 is highest, so player 1 wins
        winner = trick_winner(plays, "low", None)
        assert winner == 1

    def test_trick_winner_suit_contract_no_trump_played(self):
        """Test suit contract when no trump is played."""
        plays = [
            (0, Card("H", "T")),  # Player 0: 10 of hearts (led suit)
            (1, Card("H", "K")),  # Player 1: King of hearts (higher)
            (2, Card("D", "A")),  # Player 2: Ace of diamonds (offsuit)
            (3, Card("C", "A")),  # Player 3: Ace of clubs (offsuit)
        ]

        winner = trick_winner(plays, "suit", "S")  # Spades are trump
        assert winner == 1  # Highest heart wins

    def test_trick_winner_suit_contract_with_trump(self):
        """Test suit contract when trump is played."""
        plays = [
            (0, Card("H", "T")),  # Player 0: 10 of hearts (led suit)
            (1, Card("H", "K")),  # Player 1: King of hearts
            (2, Card("S", "Q")),  # Player 2: Queen of spades (trump!)
            (3, Card("C", "A")),  # Player 3: Ace of clubs (offsuit)
        ]

        winner = trick_winner(plays, "suit", "S")  # Spades are trump
        assert winner == 2  # Trump wins regardless of led suit

    def test_trick_winner_right_bower_wins(self):
        """Test that right bower wins the trick."""
        plays = [
            (0, Card("H", "A")),  # Player 0: Ace of hearts (led suit)
            (1, Card("H", "K")),  # Player 1: King of hearts
            (2, Card("H", "J")),  # Player 2: Jack of hearts (RIGHT bower when hearts trump)
            (3, Card("S", "A")),  # Player 3: Ace of spades
        ]

        winner = trick_winner(plays, "suit", "H")
        assert winner == 2  # Right bower wins

    def test_trick_winner_left_bower_wins(self):
        """Test that left bower wins the trick."""
        plays = [
            (0, Card("H", "A")),  # Player 0: Ace of hearts (led suit)
            (1, Card("H", "K")),  # Player 1: King of hearts
            (2, Card("D", "J")),  # Player 2: Jack of diamonds (LEFT bower when hearts trump)
            (3, Card("S", "A")),  # Player 3: Ace of spades
        ]

        winner = trick_winner(plays, "suit", "H")
        assert winner == 2  # Left bower wins

    def test_trick_winner_bower_precedence(self):
        """Test that right bower beats left bower."""
        plays = [
            (0, Card("D", "J")),  # Player 0: Left bower (diamonds when hearts trump)
            (1, Card("H", "J")),  # Player 1: Right bower (hearts)
            (2, Card("H", "A")),  # Player 2: Ace of hearts
            (3, Card("S", "A")),  # Player 3: Ace of spades
        ]

        winner = trick_winner(plays, "suit", "H")
        assert winner == 1  # Right bower beats left bower


class TestHighestTrump:
    """Test _highest_trump helper function."""

    def test_highest_trump_right_bower_wins(self):
        """Test that right bower is highest trump."""
        trump_plays = [
            (0, Card("H", "J")),  # Right bower
            (1, Card("D", "J")),  # Left bower
            (2, Card("H", "A")),  # Ace of trump
        ]
        winner = _highest_trump(trump_plays, "H")
        assert winner == 0

    def test_highest_trump_left_bower_second(self):
        """Test that left bower beats regular trump."""
        trump_plays = [
            (0, Card("D", "J")),  # Left bower
            (1, Card("H", "A")),  # Ace of trump
            (2, Card("H", "K")),  # King of trump
        ]
        winner = _highest_trump(trump_plays, "H")
        assert winner == 0

    def test_highest_trump_regular_trump_ordering(self):
        """Test ordering of regular trump cards."""
        trump_plays = [
            (0, Card("H", "T")),  # 10
            (1, Card("H", "Q")),  # Queen
            (2, Card("H", "K")),  # King
            (3, Card("H", "A")),  # Ace
        ]
        winner = _highest_trump(trump_plays, "H")
        assert winner == 3  # Ace wins


class TestHighestInSuit:
    """Test _highest_in_suit helper function."""

    def test_highest_in_suit_high_contract(self):
        """Test highest card in suit for high contract."""
        suit_plays = [
            (0, Card("H", "T")),
            (1, Card("H", "Q")),
            (2, Card("H", "K")),
            (3, Card("H", "A")),
        ]
        winner = _highest_in_suit(suit_plays, "high")
        assert winner == 3  # Ace wins

    def test_highest_in_suit_low_contract(self):
        """Test highest card in suit for low contract."""
        suit_plays = [
            (0, Card("H", "A")),  # Lowest in low contract
            (1, Card("H", "T")),  # Highest in low contract
            (2, Card("H", "K")),
            (3, Card("H", "Q")),
        ]
        winner = _highest_in_suit(suit_plays, "low")
        assert winner == 1  # 10 wins

    def test_highest_in_suit_empty_plays_error(self):
        """Test that empty suit plays raises error."""
        with pytest.raises(ValueError, match="No cards following led suit"):
            _highest_in_suit([], "high")
