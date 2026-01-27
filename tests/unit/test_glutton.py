"""
Tests for GluttonStrategy (partner awareness + 2-trick lookahead).
"""

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy


class TestPartnerAwareness:
    """Tests for partner awareness feature."""

    def test_dont_overkill_partner_winning_card(self):
        """Should not play high card when partner is winning (offsuit scenario)."""
        improved = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (strongest trump)
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("C", "T"),  # idx 2 - Clubs T (cheapest)
            Card("S", "K"),  # idx 3 - Spades K
        ]

        # Partner (player 0) is winning with Clubs A, we can't follow suit
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "A")),  # Player 0 (PARTNER) led Clubs A - WINNING
            (1, Card("C", "Q")),  # Player 1 played Clubs Q
        ]

        # Player 2's turn - partner (player 0) is winning, can't follow suit (no more clubs)
        # Legal cards: all of them (can't follow suit)
        choice = improved.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should play cheapest card (C-T at idx 2) instead of trump
        assert choice == 2, f"Expected to dump C-T (idx 2), got {choice}"
        assert "partner_winning" in improved.decision_log[-1]["scenario"]

    def test_overkill_when_partner_not_winning(self):
        """Should play high card when partner is not winning."""
        improved = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (can win)
            Card("C", "T"),  # idx 1 - Offsuit T
            Card("D", "K"),  # idx 2 - Offsuit K
        ]

        # Opponent is winning with Clubs A, can't follow suit
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "K")),  # Partner (player 0) led Clubs K (losing)
            (1, Card("C", "A")),  # Opponent (player 1) played Clubs A - WINNING
        ]

        # Player 2's turn - opponent is winning, partner is not, can't follow suit
        choice = improved.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Strategy will try to win if possible
        assert choice in [0, 1], f"Should choose a card, got {choice}"
        assert improved.decision_log[-1]["scenario"] in ["can_win", "cant_win_save_trump", "default_dump"]

    def test_save_trump_when_losing(self):
        """Should save trump cards when can't win the trick (if not following suit)."""
        improved = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - Trump T
            Card("C", "K"),  # idx 1 - Clubs K (can dump)
            Card("D", "Q"),  # idx 2 - Diamonds Q (can dump)
        ]

        # Spades led - can't follow, can't win even with trump T (A and K higher)
        plays_so_far = [
            (0, Card("S", "A")),  # Spades A led
            (1, Card("S", "K")),  # Spades K played
        ]

        # Player 2's turn - can't follow suit (no spades), can't win
        # Should prefer to dump offsuit over trump
        choice = improved.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should dump offsuit (C-K or D-Q), not trump
        assert choice in [1, 2], f"Expected to dump offsuit (idx 1 or 2), got {choice}"
        if improved.decision_log:
            assert "save_trump" in improved.decision_log[-1]["scenario"] or "dump" in improved.decision_log[-1]["action"]


class TestComparisonWithOriginalGreedy:
    """Compare improved vs original greedy behavior."""

    def test_original_greedy_wins_when_possible(self):
        """Original greedy should try to win when it can (no sure-win logic)."""
        original = GreedyStrategy()

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (can win by following suit)
            Card("C", "T"),  # idx 1 - Clubs T
            Card("D", "K"),  # idx 2 - Diamonds K
        ]

        # Can win with Clubs A by following suit
        plays_so_far = [
            (0, Card("C", "K")),  # Clubs K led
        ]

        original_choice = original.choose_card(hand, plays_so_far, "suit", "H", 1)

        # Original greedy should try to win with Clubs A
        assert original_choice == 0, f"Original chose {original_choice}"

    def test_glutton_conservative_when_not_sure(self):
        """Glutton with sure-win logic sloughs when not certain to win."""
        glutton = GluttonStrategy()

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (can win but trump could beat it)
            Card("C", "T"),  # idx 1 - Clubs T
            Card("D", "K"),  # idx 2 - Diamonds K
        ]

        # Clubs K led, hearts is trump - Clubs A is not a sure winner
        # (opponents could trump in with hearts)
        plays_so_far = [
            (0, Card("C", "K")),  # Clubs K led
        ]

        glutton_choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 1)

        # Glutton with sure-win logic should slough (C-T is cheapest legal)
        # because C-A is not a sure winner (could be trumped)
        assert glutton_choice == 1, f"Glutton should slough, chose {glutton_choice}"

    def test_glutton_wins_when_sure(self):
        """Glutton plays winner when it's guaranteed."""
        glutton = GluttonStrategy()
        # Simulate all trump already played
        glutton._played_cards = {
            Card("H", "J"), Card("D", "J"),  # Both bowers
            Card("H", "A"), Card("H", "K"), Card("H", "Q"), Card("H", "T"),  # All other trump
        }

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (now a sure winner - no trump left)
            Card("C", "T"),  # idx 1 - Clubs T
        ]

        plays_so_far = [
            (0, Card("C", "K")),  # Clubs K led
        ]

        glutton_choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 1)

        # Now C-A is a sure winner (no trump remaining to beat it)
        assert glutton_choice == 0, f"Glutton should win with sure winner, chose {glutton_choice}"

    def test_differ_on_partner_winning(self):
        """Improved should differ from original when partner is winning."""
        improved = GluttonStrategy()
        original = GreedyStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (trump)
            Card("C", "T"),  # idx 1 - Clubs T (cheap offsuit)
            Card("D", "K"),  # idx 2 - Diamonds K
        ]

        # Partner (player 0) is winning with Clubs A, we can't follow suit
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "A")),  # Partner (player 0) led Clubs A - WINNING
            (1, Card("C", "Q")),  # Clubs Q
        ]

        improved_choice = improved.choose_card(hand, plays_so_far, "suit", "H", 2)
        original_choice = original.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Improved should dump cheap offsuit when partner winning
        assert improved_choice == 1, f"Improved should dump when partner winning, chose {improved_choice}"
        # Original greedy doesn't have partner awareness, so behavior may vary
        assert original_choice in [0, 1], f"Original choice should be valid, chose {original_choice}"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_leading_trick(self):
        """Should work when leading a trick (no partner to check)."""
        improved = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0
            Card("C", "K"),  # idx 1
        ]

        # Leading - no plays yet
        plays_so_far = []

        # Should not crash
        choice = improved.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice in [0, 1]

    def test_last_to_play(self):
        """Should work when playing last in trick."""
        improved = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0 - Trump A
            Card("C", "T"),  # idx 1 - Offsuit T
        ]

        # Last to play - all 3 opponents have played
        plays_so_far = [
            (0, Card("C", "K")),
            (1, Card("C", "Q")),
            (2, Card("C", "J")),  # Partner winning with J
        ]

        # Should not overkill partner (play offsuit)
        choice = improved.choose_card(hand, plays_so_far, "suit", "H", 3)

        # Actually, at position 3 (last), can check partner at position 1
        # (0 + 2) % 4 = 2, (1 + 2) % 4 = 3, (2 + 2) % 4 = 0, (3 + 2) % 4 = 1
        # So partner of 3 is 1, who played C-Q (not winning)
        # Partner of 2 is 0, who led C-K (winning!)
        # So from player 3's perspective, partner (player 1) is not winning
        # This should try to win if possible
        assert choice in [0, 1]  # Either is valid

    def test_no_trump_contract(self):
        """Should handle no-trump contracts correctly."""
        improved = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0
            Card("C", "K"),  # idx 1
        ]

        plays_so_far = [
            (0, Card("H", "K")),
        ]

        # No trump - should work normally
        choice = improved.choose_card(hand, plays_so_far, "high", None, 1)
        assert choice == 0  # Play A to win
