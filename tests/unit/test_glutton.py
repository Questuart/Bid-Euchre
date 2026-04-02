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
        assert (
            choice == 2
        ), f"Expected to dump C-T (cheapest), got {choice} ({hand[choice]})"
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

        NOTE: Using a low trump (not sure winner) so Glutton sees threats
        and chooses to dump rather than overkill partner.
        """
        greedy = GreedyStrategy()
        glutton = GluttonStrategy()

        hand = [
            Card("H", "T"),  # idx 0 - Low trump (can win, but bowers/A/K beat it)
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

        # Greedy would play the trump (overkill) - it wins the trick
        assert greedy_choice == 0, f"Greedy should play trump, chose {greedy_choice}"

        # Glutton should dump (partner is winning, trump has high threats)
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


class TestPositionAwareness:
    """Tests for position-aware aggression (Step 4) and partner covering (Step 5)."""

    def test_3rd_seat_aggression_low_threats(self):
        """In 3rd seat with low threat count, should take the trick when opponent winning."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (can win, likely no threats)
            Card("D", "T"),  # idx 1 - Diamonds T (cheapest discard)
        ]

        # Initialize state - pretend we've seen the other Clubs A already
        glutton.on_hand_start(hand, "high", None, player_index=2)
        glutton._seen_counts[Card("C", "A")] = 1  # One Ace already played

        # 3rd seat scenario: opponent (player 1) is winning
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner leads Clubs Q
            (1, Card("C", "K")),  # Opponent plays Clubs K - WINNING
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 2)

        # Should take with Ace since threats are low (other Ace seen) and opponent winning
        assert choice == 0, f"Should take trick with Ace, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "3rd_seat_aggression"

    def test_3rd_seat_no_aggression_high_threats(self):
        """In 3rd seat with high threat count, should defer to partner awareness."""
        glutton = GluttonStrategy(debug=True)

        # Hand that can't follow clubs - gives us a choice between trump in or dump
        hand = [
            Card("H", "K"),  # idx 0 - Hearts King (trump - can win but Ace unseen)
            Card("D", "T"),  # idx 1 - Diamonds T (cheapest discard)
        ]

        # Initialize state - NO trump cards seen (both Aces, both bowers still out)
        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # 3rd seat scenario - partner is winning with clubs Ace
        # We can't follow clubs, so can trump in or dump
        plays_so_far = [
            (0, Card("C", "A")),  # Partner leads Clubs Ace - winning
            (1, Card("C", "Q")),  # Opponent plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Partner is winning, our trump King has high threats (Ace, bowers out)
        # Should dump D-T instead of overkilling with trump
        assert (
            choice == 1
        ), f"Should dump when partner winning with high threats, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_partner_cover_with_sure_winner(self):
        """In 3rd seat, cover vulnerable partner with sure winner."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (sure winner if other Ace seen)
            Card("D", "T"),  # idx 1 - Diamonds T
        ]

        # Initialize state - both copies of all higher cards seen/in-hand
        glutton.on_hand_start(hand, "high", None, player_index=2)
        glutton._seen_counts[Card("C", "A")] = 1  # Other Ace seen

        # Partner (player 0) leads weak card, opponent plays lower
        # Partner is currently winning but 4th seat could beat them
        plays_so_far = [
            (0, Card("C", "K")),  # Partner leads King - currently winning
            (1, Card("C", "Q")),  # Opponent plays Queen
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 2)

        # Partner winning, so 3rd-seat aggression is skipped (partner_winning condition)
        # Falls through to partner_vulnerable_cover since we have a sure winner
        assert choice == 0, f"Should cover with Ace, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "partner_vulnerable_cover"

    def test_3rd_seat_skips_aggression_when_partner_winning(self):
        """3rd seat aggression should NOT trigger when partner is already winning."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (would win with low threats)
            Card("D", "T"),  # idx 1 - Diamonds T (cheapest discard)
        ]

        glutton.on_hand_start(hand, "high", None, player_index=2)
        glutton._seen_counts[Card("C", "A")] = 1  # Other Ace seen (low threat)

        # Partner (player 0) is winning with King
        plays_so_far = [
            (0, Card("C", "K")),  # Partner leads King - WINNING
            (1, Card("C", "Q")),  # Opponent plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 2)

        # Even though we have low threats, we should NOT trigger 3rd_seat_aggression
        # because partner is winning. Should use partner_vulnerable_cover or partner_winning
        assert choice == 0, f"Should cover partner with Ace, got {choice}"
        scenario = glutton.decision_log[-1]["scenario"]
        assert (
            scenario != "3rd_seat_aggression"
        ), f"Should NOT use 3rd_seat_aggression when partner winning, got {scenario}"
        assert (
            scenario == "partner_vulnerable_cover"
        ), f"Expected partner_vulnerable_cover, got {scenario}"

    def test_3rd_seat_aggression_when_opponent_winning(self):
        """3rd seat aggression SHOULD trigger when opponent is winning."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (wins with low threats)
            Card("D", "T"),  # idx 1 - Diamonds T
        ]

        glutton.on_hand_start(hand, "high", None, player_index=2)
        glutton._seen_counts[Card("C", "A")] = 1  # Low threat count

        # Opponent (player 1) is winning
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner leads Queen
            (1, Card("C", "K")),  # Opponent plays King - WINNING
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 2)

        # Opponent winning, low threats, should trigger 3rd_seat_aggression
        assert (
            choice == 0
        ), f"Should take with Ace via 3rd_seat_aggression, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "3rd_seat_aggression"

    def test_4th_seat_no_aggression_logic(self):
        """4th seat should not trigger 3rd seat aggression logic."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace
            Card("D", "T"),  # idx 1 - Diamonds T
        ]

        glutton.on_hand_start(hand, "high", None, player_index=3)

        # 4th seat scenario - 3 plays made
        # For player 3: partner is (3+2)%4 = 1
        plays_so_far = [
            (0, Card("C", "K")),  # Opponent leads
            (1, Card("C", "Q")),  # Partner plays lower (not winning)
            (2, Card("C", "T")),  # Opponent plays lowest - K is still winning
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 3)

        # Opponent (0) is winning, we should win with Ace
        assert choice == 0, f"Should win with Ace in 4th seat, got {choice}"
        # Should be regular can_win, not 3rd_seat_aggression
        assert glutton.decision_log[-1]["scenario"] == "can_win"


class TestTrumpGating:
    """Tests for trump gating in 3rd-seat aggression (suit contracts only)."""

    def test_trump_gating_small_hand_allows_trump(self):
        """With small hand (<=6 cards), trump-in is allowed in 3rd seat."""
        glutton = GluttonStrategy(debug=True)

        # Small hand - 4 cards (late game), void in clubs
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace (can trump in)
            Card("D", "T"),  # idx 1 - Offsuit
            Card("D", "K"),  # idx 2 - Offsuit
            Card("S", "Q"),  # idx 3 - Offsuit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)
        # Mark both bowers as seen to make H-A a sure winner (low threats)
        glutton._seen_counts[Card("H", "J")] = 2  # Both right bowers seen
        glutton._seen_counts[Card("D", "J")] = 2  # Both left bowers seen
        glutton._seen_counts[Card("H", "A")] = 1  # Other Ace seen

        # Opponent winning with clubs, we're void in clubs
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner plays lower
            (1, Card("C", "K")),  # Opponent winning
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Small hand (4 cards <= 6), should allow trump-in via 3rd_seat_aggression
        assert choice == 0, f"Should trump in with small hand, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "3rd_seat_aggression"

    def test_trump_gating_trump_heavy_allows_trump(self):
        """With trump-heavy hand (>=3 trump), trump-in is allowed."""
        glutton = GluttonStrategy(debug=True)

        # Large hand but trump-heavy (3+ trump), void in clubs
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("H", "K"),  # idx 1 - Trump King
            Card("H", "Q"),  # idx 2 - Trump Queen (cheapest winner)
            Card("D", "T"),  # idx 3 - Offsuit
            Card("D", "K"),  # idx 4 - Offsuit
            Card("S", "Q"),  # idx 5 - Offsuit
            Card("S", "T"),  # idx 6 - Offsuit
            Card("S", "K"),  # idx 7 - Offsuit (8 cards total, > 6)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)
        # Mark both bowers as seen to make H-A a sure winner (low threats)
        glutton._seen_counts[Card("H", "J")] = 2  # Both right bowers seen
        glutton._seen_counts[Card("D", "J")] = 2  # Both left bowers seen
        glutton._seen_counts[Card("H", "A")] = 1  # Other Ace seen

        # Opponent winning with clubs, we're void in clubs
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner plays
            (1, Card("C", "A")),  # Opponent winning
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # 8 cards > 6, but 3 trump >= 3, so gating allows trump-in
        # Should play cheapest winning trump (H-Q at idx 2, threats=1 which is <=1)
        assert choice == 2, f"Should trump in with cheapest trump (H-Q), got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "3rd_seat_aggression"

    def test_trump_gating_large_hand_low_trump_skips_aggression(self):
        """With large hand and few trump, trump-in should NOT use 3rd seat aggression."""
        glutton = GluttonStrategy(debug=True)

        # Large hand with only 1 trump, void in clubs
        hand = [
            Card("H", "A"),  # idx 0 - Only trump
            Card("D", "T"),  # idx 1 - Offsuit
            Card("D", "K"),  # idx 2 - Offsuit
            Card("S", "Q"),  # idx 3 - Offsuit
            Card("S", "T"),  # idx 4 - Offsuit
            Card("S", "K"),  # idx 5 - Offsuit
            Card("S", "A"),  # idx 6 - Offsuit (7 cards > 6, only 1 trump < 3)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)
        # Mark both bowers as seen to make H-A a sure winner (low threats)
        glutton._seen_counts[Card("H", "J")] = 2  # Both right bowers seen
        glutton._seen_counts[Card("D", "J")] = 2  # Both left bowers seen
        glutton._seen_counts[Card("H", "A")] = 1  # Other Ace seen

        # Opponent winning with clubs, we're void
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner plays
            (1, Card("C", "K")),  # Opponent winning
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # 7 cards > 6, only 1 trump < 3, gating should BLOCK trump-in
        # Falls through to can_win path instead
        assert choice == 0, f"Should still trump in via can_win path, got {choice}"
        assert (
            glutton.decision_log[-1]["scenario"] == "can_win"
        ), f"Should skip 3rd_seat_aggression due to trump gating, got {glutton.decision_log[-1]['scenario']}"

    def test_non_trump_winner_no_gating(self):
        """Non-trump winners are not affected by trump gating (use high contract)."""
        glutton = GluttonStrategy(debug=True)

        # Large hand in high contract (no trump gating applies)
        hand = [
            Card("C", "A"),  # idx 0 - Clubs Ace (following suit)
            Card("C", "T"),  # idx 1 - Following suit
            Card("D", "K"),  # idx 2 - Offsuit
            Card("D", "Q"),  # idx 3 - Offsuit
            Card("D", "T"),  # idx 4 - Offsuit
            Card("S", "K"),  # idx 5 - Offsuit
            Card("S", "Q"),  # idx 6 - Offsuit (7 cards > 6)
        ]

        glutton.on_hand_start(hand, "high", None, player_index=2)
        # Make Clubs Ace low-threat (other Ace seen)
        glutton._seen_counts[Card("C", "A")] = 1

        # Opponent winning with clubs, we follow suit
        plays_so_far = [
            (0, Card("C", "Q")),  # Partner plays
            (1, Card("C", "K")),  # Opponent winning
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 2)

        # In high contract, no trump gating applies - just threat count
        # C-A has 0 threats (2 copies, 1 seen, 1 in hand)
        assert choice == 0, f"Should take with Clubs Ace, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "3rd_seat_aggression"


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


class TestProbabilisticTrumpIn:
    """Tests for void-aware probabilistic trump-in decisions."""

    def test_trump_in_when_fourth_seat_void(self):
        """Should trump in when 4th seat is void in led suit and might have trump."""
        glutton = GluttonStrategy(debug=True)

        # Void in clubs, have trump
        hand = [
            Card("H", "T"),  # idx 0 - Low trump
            Card("D", "K"),  # idx 1 - Offsuit (can't follow clubs)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Mark 4th seat (player 3) as void in clubs (from earlier play)
        glutton._void_suits_by_seat[3].add("C")

        # Partner is winning with clubs Ace
        plays_so_far = [
            (0, Card("C", "A")),  # Partner leads Ace - winning
            (1, Card("C", "Q")),  # Opponent plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should trump to protect partner from 4th seat trump
        assert choice == 0, f"Should trump in, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "probabilistic_trump_cover"

    def test_no_trump_in_when_fourth_seat_can_follow(self):
        """Should not trump if 4th seat can follow suit."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - Trump
            Card("D", "K"),  # idx 1 - Offsuit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # 4th seat is NOT void in clubs
        # (no entry in _void_suits_by_seat[3] for "C")

        plays_so_far = [
            (0, Card("C", "A")),  # Partner leads Ace - winning
            (1, Card("C", "Q")),  # Opponent plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should NOT trump (partner safe, 4th seat can follow suit)
        assert choice == 1, f"Should discard, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_no_trump_in_high_contract(self):
        """Should not trigger trump-in logic in high contract."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "A"),  # idx 0 - Hearts Ace
            Card("D", "K"),  # idx 1 - Offsuit
        ]

        glutton.on_hand_start(hand, "high", None, player_index=2)
        glutton._void_suits_by_seat[3].add("C")  # Would trigger in suit contract

        plays_so_far = [
            (0, Card("C", "A")),  # Partner winning
            (1, Card("C", "Q")),
        ]

        choice = glutton.choose_card(hand, plays_so_far, "high", None, 2)

        # High contract - no trump-in logic applies
        assert choice == 1  # Discard offsuit
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_no_trump_in_when_fourth_seat_void_in_trump(self):
        """Should not trump if 4th seat is void in trump (can't overtrump)."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - Trump
            Card("D", "K"),  # idx 1 - Offsuit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # 4th seat is void in clubs AND void in hearts (trump)
        glutton._void_suits_by_seat[3].add("C")
        glutton._void_suits_by_seat[3].add("H")  # No trump!

        plays_so_far = [
            (0, Card("C", "A")),  # Partner leads Ace - winning
            (1, Card("C", "Q")),  # Opponent plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # 4th seat is void in trump, can't overtrump partner's lead
        assert choice == 1, f"Should discard, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_no_trump_in_when_can_follow_suit(self):
        """Should not consider trump-in if we can follow suit."""
        glutton = GluttonStrategy(debug=True)

        # Can follow clubs
        hand = [
            Card("H", "T"),  # idx 0 - Trump
            Card("C", "K"),  # idx 1 - Can follow suit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=2)
        glutton._void_suits_by_seat[3].add("C")  # 4th seat void in clubs

        plays_so_far = [
            (0, Card("C", "A")),  # Partner leads Ace - winning
            (1, Card("C", "Q")),  # Opponent plays lower
        ]

        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)

        # We must follow suit with C-K
        assert choice == 1, f"Should follow suit with C-K, got {choice}"
        assert glutton.decision_log[-1]["scenario"] == "partner_winning"

    def test_no_trump_in_not_third_seat(self):
        """Probabilistic trump-in should only apply in 3rd seat."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - Trump
            Card("D", "K"),  # idx 1 - Offsuit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=1)
        glutton._void_suits_by_seat[2].add("C")  # Next player void

        # 2nd seat position (only 1 play so far)
        plays_so_far = [
            (0, Card("C", "A")),  # Player 0 leads - partner is (1+2)%4=3, not 0
        ]

        glutton.choose_card(hand, plays_so_far, "suit", "H", 1)

        # In 2nd seat, 4th seat protection doesn't apply
        # Player 0 is opponent for player 1 - so we try to win
        assert glutton.decision_log[-1]["scenario"] != "probabilistic_trump_cover"


class TestLowContractBehavior:
    """Tests for correct card ranking on low contracts (#2098).

    In low contracts (10 high, A low), the Glutton should:
    - Lead with WEAK cards (aces) to conserve strong cards (tens)
    - Discard weak cards when following and can't win
    - Use the cheapest winner when following and can win
    """

    def test_low_lead_plays_weakest_card(self):
        """On low contracts, lead with weakest card (A) not strongest (T)."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("S", "T"),  # idx 0 - strongest in low (value 4)
            Card("S", "K"),  # idx 1 - (value 1 in low)
            Card("S", "Q"),  # idx 2 - (value 2 in low)
            Card("S", "J"),  # idx 3 - (value 3 in low)
            Card("S", "A"),  # idx 4 - weakest in low (value 0)
            Card("H", "T"),  # idx 5
            Card("H", "K"),  # idx 6
            Card("H", "Q"),  # idx 7
            Card("H", "J"),  # idx 8
            Card("H", "A"),  # idx 9
        ]

        glutton.on_hand_start(hand, "low", None, player_index=0)
        choice = glutton.choose_card(hand, [], "low", None, 0)

        # Should lead with weakest card from longest suit (both suits equal,
        # picks first = spades; weakest in spades = A at idx 4)
        assert (
            hand[choice].rank == "A"
        ), f"Low lead should play A (weakest), got {hand[choice]}"

    def test_low_lead_order_weak_to_strong(self):
        """On low contracts, successive leads go weak-to-strong (A, K, Q, J, T)."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("S", "T"),
            Card("S", "J"),
            Card("S", "Q"),
            Card("S", "K"),
            Card("S", "A"),
            Card("H", "T"),
            Card("H", "J"),
            Card("H", "Q"),
            Card("H", "K"),
            Card("H", "A"),
        ]

        glutton.on_hand_start(hand[:], "low", None, player_index=0)

        # Simulate 5 leads, tracking which cards are chosen
        remaining = list(range(len(hand)))
        lead_ranks = []
        for _ in range(5):
            sub_hand = [hand[i] for i in remaining]
            choice = glutton.choose_card(sub_hand, [], "low", None, 0)
            lead_ranks.append(sub_hand[choice].rank)
            remaining.pop(choice)

        # Should lead weak-to-strong: A, A, K, K, Q (not T, T, J, J, Q)
        assert lead_ranks == [
            "A",
            "A",
            "K",
            "K",
            "Q",
        ], f"Low leads should go weak-to-strong, got {lead_ranks}"

    def test_high_lead_order_strong_to_weak(self):
        """On high contracts, successive leads go strong-to-weak (unchanged)."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("S", "T"),
            Card("S", "J"),
            Card("S", "Q"),
            Card("S", "K"),
            Card("S", "A"),
            Card("H", "T"),
            Card("H", "J"),
            Card("H", "Q"),
            Card("H", "K"),
            Card("H", "A"),
        ]

        glutton.on_hand_start(hand[:], "high", None, player_index=0)

        remaining = list(range(len(hand)))
        lead_ranks = []
        for _ in range(5):
            sub_hand = [hand[i] for i in remaining]
            choice = glutton.choose_card(sub_hand, [], "high", None, 0)
            lead_ranks.append(sub_hand[choice].rank)
            remaining.pop(choice)

        # Should lead strong-to-weak: A, A, K, K, Q
        assert lead_ranks == [
            "A",
            "A",
            "K",
            "K",
            "Q",
        ], f"High leads should go strong-to-weak, got {lead_ranks}"

    def test_low_discard_dumps_weakest(self):
        """On low, discard should dump weakest card (A), saving strong (T)."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - strongest in low
            Card("H", "K"),  # idx 1
            Card("H", "A"),  # idx 2 - weakest in low
        ]

        glutton.on_hand_start(hand, "low", None, player_index=2)

        # Opponent leads T (strongest in low), can't beat it
        plays = [
            (0, Card("H", "T")),
            (1, Card("H", "Q")),
        ]

        choice = glutton.choose_card(hand, plays, "low", None, 2)

        assert (
            hand[choice].rank == "A"
        ), f"Low discard should dump A (weakest), got {hand[choice]}"

    def test_low_cheapest_winner(self):
        """On low, use cheapest winner when following (save expensive cards)."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "T"),  # idx 0 - strongest (value 4 in low)
            Card("H", "J"),  # idx 1 - second strongest (value 3 in low)
            Card("H", "A"),  # idx 2 - can't win
        ]

        glutton.on_hand_start(hand, "low", None, player_index=3)

        # Opponent (player 2) is winning with Q (value 2 in low)
        # Both T (4) and J (3) can beat Q. Should use J (cheaper).
        plays = [
            (1, Card("H", "K")),  # Partner leads K (value 1)
            (2, Card("H", "Q")),  # Opponent plays Q (value 2) - winning
            (0, Card("H", "A")),  # Other opponent plays A (value 0)
        ]

        choice = glutton.choose_card(hand, plays, "low", None, 3)

        assert (
            hand[choice].rank == "J"
        ), f"Low should use cheapest winner (J), got {hand[choice]}"
