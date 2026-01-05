import pytest

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import trick_winner, _highest_trump, _highest_in_suit, get_legal_indices


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


class TestGetLegalIndices:
    """Test get_legal_indices - single source of truth for legal plays."""

    def test_leading_any_card_legal(self):
        """When leading (no plays so far), any card is legal."""
        hand = [Card("H", "A"), Card("S", "K"), Card("D", "Q")]
        legal = get_legal_indices(hand, [], "suit", "H")
        assert legal == [0, 1, 2]

    def test_must_follow_led_suit(self):
        """Must follow suit if you have cards in led suit."""
        hand = [Card("H", "A"), Card("S", "K"), Card("H", "Q")]
        plays_so_far = [(0, Card("H", "T"))]  # Hearts led
        legal = get_legal_indices(hand, plays_so_far, "suit", "S")
        # Only hearts are legal (indices 0 and 2)
        assert legal == [0, 2]

    def test_cannot_follow_suit_any_legal(self):
        """If you can't follow suit, any card is legal."""
        hand = [Card("S", "A"), Card("D", "K"), Card("C", "Q")]
        plays_so_far = [(0, Card("H", "T"))]  # Hearts led
        legal = get_legal_indices(hand, plays_so_far, "suit", "S")
        # No hearts in hand, so any card is legal
        assert legal == [0, 1, 2]

    def test_left_bower_is_trump_suit(self):
        """Left bower should be treated as trump suit for follow-suit."""
        hand = [Card("D", "J"), Card("S", "K"), Card("C", "Q")]  # D-J is left bower when H is trump
        plays_so_far = [(0, Card("H", "T"))]  # Hearts led
        legal = get_legal_indices(hand, plays_so_far, "suit", "H")
        # D-J has effective suit of Hearts (left bower), so it's the only legal play
        assert legal == [0]

    def test_high_contract_no_trump(self):
        """High contract - follow suit normally."""
        hand = [Card("H", "A"), Card("S", "K"), Card("H", "Q")]
        plays_so_far = [(0, Card("H", "T"))]
        legal = get_legal_indices(hand, plays_so_far, "high", None)
        assert legal == [0, 2]

    def test_low_contract_no_trump(self):
        """Low contract - follow suit normally."""
        hand = [Card("H", "A"), Card("S", "K"), Card("H", "Q")]
        plays_so_far = [(0, Card("H", "T"))]
        legal = get_legal_indices(hand, plays_so_far, "low", None)
        assert legal == [0, 2]

    def test_trump_led_must_follow_trump(self):
        """When trump is led, must follow with trump if possible."""
        hand = [Card("H", "A"), Card("S", "K"), Card("D", "Q")]  # S-K is only trump (spades trump)
        plays_so_far = [(0, Card("S", "T"))]  # Spades (trump) led
        legal = get_legal_indices(hand, plays_so_far, "suit", "S")
        # Only S-K follows spades
        assert legal == [1]

    def test_single_card_hand(self):
        """Single card in hand is always legal."""
        hand = [Card("H", "A")]
        plays_so_far = [(0, Card("S", "T"))]
        legal = get_legal_indices(hand, plays_so_far, "suit", "S")
        assert legal == [0]

    def test_all_cards_follow_suit(self):
        """When all cards follow suit, all are legal."""
        hand = [Card("H", "A"), Card("H", "K"), Card("H", "Q")]
        plays_so_far = [(0, Card("H", "T"))]
        legal = get_legal_indices(hand, plays_so_far, "suit", "S")
        assert legal == [0, 1, 2]
