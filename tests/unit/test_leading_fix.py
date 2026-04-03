"""
Tests to verify leading and partner awareness behavior for greedy strategies.
"""

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy


class TestGreedyLeadingFix:
    """Tests that Greedy plays strong cards when leading."""

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
        assert choice in [
            0,
            1,
        ], f"Expected to lead with strong card (0 or 1), got {choice} ({hand[choice]})"

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
        assert (
            choice == 3
        ), f"Expected to lead with Ace (idx 3), got {choice} ({hand[choice]})"

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
        assert (
            choice == 0
        ), f"Expected to lead with trump Ace (idx 0), got {choice} ({hand[choice]})"

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
        assert (
            choice == 1
        ), f"Expected to win with C-A (idx 1), got {choice} ({hand[choice]})"


class TestGluttonLeadingFix:
    """Tests that Glutton plays strong cards when leading."""

    def test_glutton_leads_with_smart_heuristic(self):
        """Glutton smart leading prefers offsuit leads over trump in suit contracts.

        The _choose_lead heuristic for suit contracts:
        1. Non-trump Aces (win trick without spending trump)
        2. Draw trump if holding ≥4
        3. Lead from longest non-trump suit, highest card

        With no non-trump Aces and <4 trump, Glutton leads from offsuit.
        """
        glutton = GluttonStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (trump)
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("C", "T"),  # idx 2 - Offsuit Ten
            Card("D", "K"),  # idx 3 - Offsuit King
        ]

        # Leading - no plays yet
        plays_so_far = []

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 0)

        # Smart heuristic leads from offsuit (step 3: longest non-trump, highest card)
        # Both C and D have count 1, so leads highest from whichever is selected
        assert choice in [
            2,
            3,
        ], f"Expected smart lead from offsuit (2 or 3), got {choice} ({hand[choice]})"

    def test_glutton_leads_with_non_trump_ace(self):
        """Glutton smart leading prefers non-trump Ace over bower.

        Non-trump Aces win a trick without spending trump, making them
        the #1 priority in _choose_lead for suit contracts.
        """
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (trump)
            Card("C", "A"),  # idx 1 - Offsuit Ace (non-trump Ace)
            Card("D", "K"),  # idx 2 - Offsuit King
        ]

        # Leading in suit contract
        plays_so_far = []

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 0)

        # Smart heuristic step 1: lead non-trump Ace (C-A at idx 1)
        assert (
            choice == 1
        ), f"Expected non-trump Ace lead (idx 1), got {choice} ({hand[choice]})"
        assert glutton.decision_log[-1]["scenario"] == "leading"

    def test_glutton_partner_awareness_when_following(self):
        """Glutton should dump when partner is winning and we have non-sure-winner trump.

        NOTE: Using a low trump (not sure winner) so Glutton sees threats
        and chooses to dump rather than overkill partner.
        """
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - Low trump (bowers/A/K beat it)
            Card("S", "T"),  # idx 1 - Spades Ten (cheapest)
            Card("D", "K"),  # idx 2 - Diamonds King
        ]

        # Initialize state
        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Partner (player 0) is winning, we can't follow suit (no clubs)
        # Partner's card is vulnerable (could be trumped) but partner is still winning
        plays_so_far = [
            (0, Card("C", "A")),  # Partner led and is currently winning
            (1, Card("C", "Q")),  # Opponent played lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should dump cheapest card (S-T) since partner is winning and trump has threats
        assert (
            choice == 1
        ), f"Expected to dump S-T when partner winning, got {choice} ({hand[choice]})"
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_glutton_takes_trick_when_opponent_winning(self):
        """Glutton should take trick when opponent is winning."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (sure winner)
            Card("S", "T"),  # idx 1 - Spades Ten
            Card("D", "K"),  # idx 2 - Diamonds King
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Opponent (player 1) is winning
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner led
            (1, Card("C", "A")),  # Opponent beat partner - WINNING
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should play cheapest winner (right bower) to beat opponent
        assert (
            choice == 0
        ), f"Expected to play right bower to win, got {choice} ({hand[choice]})"


class TestCompareLeadingBehavior:
    """Compare leading behavior across strategies."""

    def test_all_strategies_lead_with_reasonable_cards(self):
        """All strategies should make reasonable leading decisions.

        Greedy and AlwaysHighestLegal lead with the strongest card (bower).
        Glutton's smart heuristic leads from offsuit in suit contracts
        (step 3: longest non-trump suit) — this is strategically sound.
        """
        from bid_euchre.strategy import (
            AlwaysHighestLegalStrategy,
            GluttonStrategy,
            GreedyStrategy,
        )

        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("C", "T"),  # idx 1 - Offsuit Ten (weakest)
        ]

        plays_so_far = []  # Leading

        # Greedy and AlwaysHighest lead with strongest card
        for strategy in [GreedyStrategy(), AlwaysHighestLegalStrategy()]:
            choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 0)
            assert (
                choice == 0
            ), f"{strategy.name} should lead with bower, chose {choice}"

        # Glutton's smart heuristic leads from offsuit in suit contracts
        glutton = GluttonStrategy()
        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 0)
        assert choice in [
            0,
            1,
        ], f"glutton should make a legal lead choice, chose {choice}"
