"""
Tests for GluttonStrategy (Greedy + partner awareness).

GluttonStrategy is essentially GreedyStrategy with one key difference:
when partner is winning the trick, Glutton dumps cheapest card instead of
trying to overkill. This saves cards for future tricks.

NOTE: GluttonStrategy also has hooks (on_hand_start, observe_play) for state
tracking, though the simplified version doesn't use them for decision-making.
"""

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy


class TestPartnerAwareness:
    """Tests for partner awareness feature - the key difference from Greedy."""

    def test_dont_overkill_partner_winning_card(self):
        """Should not play high card when partner is winning."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (strongest trump)
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("C", "T"),  # idx 2 - Clubs T (cheapest)
            Card("S", "K"),  # idx 3 - Spades K
        ]

        # Initialize state
        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Partner (player 0) is winning with Clubs A, we can't follow suit
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "A")),  # Player 0 (PARTNER) led Clubs A - WINNING
            (1, Card("C", "Q")),  # Player 1 played Clubs Q
        ]

        # Player 2's turn - partner (player 0) is winning, can't follow suit
        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should dump cheapest card - C-T has lowest value
        assert choice == 2, f"Expected to dump C-T (cheapest), got {choice} ({hand[choice]})"
        # Scenario should indicate partner-related behavior
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_overkill_when_partner_not_winning(self):
        """Should try to win when partner is NOT winning."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (can trump in)
            Card("S", "T"),  # idx 1 - Offsuit T (no clubs!)
            Card("D", "K"),  # idx 2 - Offsuit K (no clubs!)
        ]

        # Initialize state
        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Opponent is winning with Clubs A
        # We can't follow suit (no clubs in hand), so we can trump in
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "K")),  # Partner (player 0) led Clubs K (losing)
            (1, Card("C", "A")),  # Opponent (player 1) played Clubs A - WINNING
        ]

        # Player 2's turn - opponent is winning, partner is not
        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should play right bower (cheapest winner that beats opponent)
        assert choice == 0, f"Should play right bower to beat opponent, got {choice}"

    def test_greedy_would_overkill(self):
        """GreedyStrategy would overkill partner - Glutton should not.

        Setup: We can't follow clubs (no clubs in hand), so we can choose
        to trump in (overkill) or dump.
        """
        greedy = GreedyStrategy()
        glutton = GluttonStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (can trump in to win)
            Card("S", "T"),  # idx 1 - Spades T (cheapest, NOT clubs)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Partner (player 0) is winning
        # We CAN'T follow clubs (no clubs in hand), so we can trump or dump
        plays_so_far = [
            (0, Card("C", "A")),  # Partner led and is winning
            (1, Card("C", "Q")),  # Opponent played lower
        ]

        greedy_choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 2)
        glutton_choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Greedy would play the bower (overkill) - it wins the trick
        assert greedy_choice == 0, f"Greedy should play bower, chose {greedy_choice}"

        # Glutton should dump (partner is winning)
        assert glutton_choice == 1, f"Glutton should dump, chose {glutton_choice}"


class TestGreedyLikeBehavior:
    """Test that Glutton behaves like Greedy in non-partner-winning scenarios."""

    def test_wins_when_possible_opponent_winning(self):
        """Should try to win when opponent is winning."""
        glutton = GluttonStrategy()

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (can win by following suit)
            Card("C", "T"),  # idx 1 - Clubs T
            Card("D", "K"),  # idx 2 - Diamonds K
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Opponent (player 1) is winning
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner led Clubs Q
            (1, Card("C", "K")),  # Opponent beat partner
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should play cheapest winner (C-T beats C-K? No, C-A does)
        # Wait, C-T doesn't beat C-K. C-A does.
        assert choice == 0, f"Should play C-A to win, chose {choice}"

    def test_leads_with_smart_selection(self):
        """When leading, Glutton uses smart lead selection (differs from Greedy).

        Glutton prioritizes: non-trump Aces → draw trump (>=4) → longest non-trump.
        Greedy just leads with highest value card.
        """
        glutton = GluttonStrategy()
        greedy = GreedyStrategy()

        hand = [
            Card("H", "J"),  # idx 0 - Right bower (highest value)
            Card("C", "T"),  # idx 1 - Only non-trump card (longest non-trump suit)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=0)

        glutton_choice = glutton.choose_card(hand, [], "suit", "H", 0)
        greedy_choice = greedy.choose_card(hand, [], "suit", "H", 0)

        # Greedy leads highest value (bower)
        assert greedy_choice == 0
        # Glutton leads from longest non-trump suit (C-T)
        assert glutton_choice == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_leading_trick(self):
        """Should work when leading a trick - uses smart lead selection."""
        glutton = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("C", "K"),  # idx 1 - Longest non-trump suit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=0)

        # Leading - no plays yet
        choice = glutton.choose_card(hand, [], "suit", "H", 0)

        # Glutton leads from longest non-trump suit (C-K)
        # (No non-trump Aces, not >=4 trump to draw, so longest non-trump)
        assert choice == 1

    def test_last_to_play_opponent_winning(self):
        """In 4th position with opponent winning, should win if possible."""
        glutton = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0 - Trump A (can win by trumping)
            Card("D", "T"),  # idx 1 - Offsuit T
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=3)

        # Player 0 (opponent) is winning
        # For player 3: partner is (3+2)%4 = 1
        plays_so_far = [
            (0, Card("C", "K")),  # Opponent leads
            (1, Card("C", "Q")),  # Partner plays lower
            (2, Card("C", "T")),  # Opponent 2 plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 3)

        # Should trump to win (opponent is winning, we can beat them)
        assert choice == 0, f"Should trump to win, got {choice}"

    def test_last_to_play_partner_winning(self):
        """In 4th position with partner winning, should dump."""
        glutton = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0 - Trump A (could overkill)
            Card("D", "T"),  # idx 1 - Offsuit T (cheapest)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=3)

        # Player 1 (partner) is winning
        # For player 3: partner is (3+2)%4 = 1
        plays_so_far = [
            (0, Card("C", "Q")),  # Opponent leads
            (1, Card("C", "K")),  # Partner beats opponent
            (2, Card("C", "T")),  # Opponent 2 can't beat partner
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 3)

        # Partner is winning - should dump cheapest
        assert choice == 1, f"Should dump when partner winning, got {choice}"

    def test_no_trump_contract(self):
        """Should handle no-trump contracts correctly."""
        glutton = GluttonStrategy()

        hand = [
            Card("H", "A"),  # idx 0 - Ace of led suit
            Card("C", "K"),  # idx 1
        ]

        glutton.on_hand_start(hand, "high", None, player_index=1)

        plays_so_far = [
            (0, Card("H", "K")),  # Hearts King led (opponent)
        ]

        # Opponent is winning, we can beat them with Ace
        choice = glutton.choose_card(hand, plays_so_far, "high", None, 1)
        assert choice == 0, "Should play Ace to win"


class TestHooksIntegration:
    """Test that hooks are properly called during simulation."""

    def test_on_hand_start_initializes_state(self):
        """on_hand_start should reset and initialize tracking state."""
        strategy = GluttonStrategy()

        # Pollute state
        strategy._seen_counts = {Card("H", "A"): 2}
        strategy._void_suits_by_seat[0].add("C")

        hand = [Card("H", "J"), Card("C", "T")]
        strategy.on_hand_start(hand, "suit", "H", player_index=0)

        assert strategy._seen_counts == {}
        assert all(len(v) == 0 for v in strategy._void_suits_by_seat.values())
        assert strategy._contract_type == "suit"
        assert strategy._trump_suit == "H"

    def test_observe_play_tracks_cards(self):
        """observe_play should increment seen counts."""
        strategy = GluttonStrategy()
        strategy.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)

        strategy.observe_play(
            player_index=1,
            card=Card("H", "K"),
            trick_plays=[(1, Card("H", "K"))],
            contract_type="suit",
            trump_suit="H",
        )

        assert strategy._seen_counts.get(Card("H", "K"), 0) == 1

    def test_observe_play_infers_voids(self):
        """observe_play should infer voids when player doesn't follow suit."""
        strategy = GluttonStrategy()
        strategy.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)

        # Spades led
        strategy.observe_play(
            player_index=0,
            card=Card("S", "K"),
            trick_plays=[(0, Card("S", "K"))],
            contract_type="suit",
            trump_suit="H",
        )

        # Player 1 plays trump instead of following spades -> void in spades
        strategy.observe_play(
            player_index=1,
            card=Card("H", "T"),
            trick_plays=[(0, Card("S", "K")), (1, Card("H", "T"))],
            contract_type="suit",
            trump_suit="H",
        )

        assert "S" in strategy._void_suits_by_seat[1]
