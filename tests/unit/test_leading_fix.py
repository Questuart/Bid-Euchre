"""
Tests to verify the leading bug fix for greedy strategies.
"""

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy


class TestGreedyLeadingFix:
    """Tests that greedy plays strong cards when leading."""

    def test_greedy_leads_with_strong_card(self):
        """Greedy should lead with strong card, not weak card."""
        greedy = GreedyStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (STRONGEST)
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("C", "T"),  # idx 2 - Offsuit Ten (WEAKEST)
            Card("D", "K"),  # idx 3 - Offsuit King
        ]

        # Leading - no plays yet
        plays_so_far = []

        choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 0)

        # Should play bower (idx 0) or trump ace (idx 1), NOT offsuit ten
        assert choice in [0, 1], f"Expected to lead with strong card (0 or 1), got {choice} ({hand[choice]})"

    def test_greedy_leads_with_highest_value(self):
        """Greedy should lead with the highest value card."""
        greedy = GreedyStrategy()

        hand = [
            Card("C", "T"),  # idx 0 - Clubs Ten (lowest value)
            Card("D", "K"),  # idx 1 - Diamonds King
            Card("S", "Q"),  # idx 2 - Spades Queen
            Card("H", "A"),  # idx 3 - Hearts Ace (highest in high contract)
        ]

        # Leading in high contract
        plays_so_far = []

        choice = greedy.choose_card(hand, plays_so_far, "high", None, 0)

        # Should lead with Ace (highest rank in high contract)
        assert choice == 3, f"Expected to lead with Ace (idx 3), got {choice} ({hand[choice]})"

    def test_greedy_leads_with_trump_in_suit_contract(self):
        """Greedy should prefer leading with trump in suit contracts."""
        greedy = GreedyStrategy()

        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace (strongest available)
            Card("C", "A"),  # idx 1 - Offsuit Ace
            Card("D", "K"),  # idx 2 - Offsuit King
        ]

        # Leading in suit contract with Hearts trump
        plays_so_far = []

        choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 0)

        # Should lead with trump ace (most valuable)
        assert choice == 0, f"Expected to lead with trump Ace (idx 0), got {choice} ({hand[choice]})"

    def test_greedy_follows_normally_after_fix(self):
        """After fix, greedy should still follow suit correctly."""
        greedy = GreedyStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("C", "A"),  # idx 1 - Clubs Ace (can win by following)
            Card("C", "T"),  # idx 2 - Clubs Ten
        ]

        # Following - Clubs led
        plays_so_far = [
            (0, Card("C", "K")),  # Clubs King led
        ]

        choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 1)

        # Should win with Clubs Ace (cheapest winner)
        assert choice == 1, f"Expected to win with C-A (idx 1), got {choice} ({hand[choice]})"


class TestGluttonLeadingFix:
    """Tests that glutton plays strong cards when leading."""

    def test_glutton_leads_with_strong_card(self):
        """Glutton should lead with strong card, not weak card."""
        glutton = GluttonStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (STRONGEST)
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("C", "T"),  # idx 2 - Offsuit Ten (WEAKEST)
            Card("D", "K"),  # idx 3 - Offsuit King
        ]

        # Leading - no plays yet
        plays_so_far = []

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 0)

        # Should play bower (idx 0) or trump ace (idx 1), NOT offsuit ten
        assert choice in [0, 1], f"Expected to lead with strong card (0 or 1), got {choice} ({hand[choice]})"

    def test_glutton_leads_with_bower(self):
        """Glutton should lead with bower when available."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (STRONGEST)
            Card("C", "A"),  # idx 1 - Offsuit Ace
            Card("D", "K"),  # idx 2 - Offsuit King
        ]

        # Leading in suit contract
        plays_so_far = []

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 0)

        # Should lead with bower (highest value)
        assert choice == 0, f"Expected to lead with bower (idx 0), got {choice} ({hand[choice]})"
        assert glutton.decision_log[-1]["scenario"] == "leading"

    def test_glutton_still_has_partner_awareness_when_following(self):
        """After fix, glutton should still avoid overkilling partner."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("C", "T"),  # idx 1 - Clubs Ten (cheapest)
            Card("D", "K"),  # idx 2 - Diamonds King
        ]

        # Partner (player 0) is winning, we can't follow suit
        plays_so_far = [
            (0, Card("C", "A")),  # Partner led and is winning
            (1, Card("C", "Q")),  # Opponent played lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should dump cheapest (idx 1), not play trump
        assert choice == 1, f"Expected to dump when partner winning (idx 1), got {choice} ({hand[choice]})"
        assert "partner_winning" in glutton.decision_log[-1]["scenario"]


class TestCompareLeadingBehavior:
    """Compare leading behavior across strategies."""

    def test_all_strategies_lead_with_reasonable_cards(self):
        """All strategies should make reasonable leading decisions."""
        from bid_euchre.strategy import (
            AlwaysHighestLegalStrategy,
            GluttonStrategy,
            GreedyStrategy,
        )

        strategies = [
            GreedyStrategy(),
            GluttonStrategy(),
            AlwaysHighestLegalStrategy(),
        ]

        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("C", "T"),  # idx 1 - Offsuit Ten (weakest)
        ]

        plays_so_far = []  # Leading

        for strategy in strategies:
            choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
            # All should choose bower (idx 0), not ten (idx 1)
            assert choice == 0, f"{strategy.name} should lead with bower, chose {choice}"
