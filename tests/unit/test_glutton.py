"""
Tests for GluttonStrategy (Greedy + partner awareness).

GluttonStrategy is essentially GreedyStrategy with one key difference:
when partner is winning the trick, Glutton dumps cheapest card instead of
trying to overkill. This saves cards for future tricks.

NOTE: GluttonStrategy also has hooks (on_hand_start, observe_play) for state
tracking, though the simplified version doesn't use them for decision-making.
"""

import copy

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonIsolatedStrategy, GluttonStrategy, GreedyStrategy


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

    def test_lead_right_bower_when_both_bowers_and_strong_trump(self):
        """With both bowers + 5+ trump, Glutton should lead the right bower.

        This is the highest-priority lead tier for suit contracts.
        Leading the right bower draws out opponent trump and establishes
        total trump control when holding overwhelming trump strength.
        """
        glutton = GluttonStrategy()

        # 5 trump (including both bowers) + non-trump Ace
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("D", "J"),  # idx 1 - Left bower (hearts trump → diamonds J is left)
            Card("H", "A"),  # idx 2 - Trump Ace
            Card("H", "K"),  # idx 3 - Trump King
            Card("H", "Q"),  # idx 4 - Trump Queen
            Card("C", "A"),  # idx 5 - Non-trump Ace (would be Step 1 lead otherwise)
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=0)
        choice = glutton.choose_card(hand, [], "suit", "H", 0)

        # Should lead right bower (idx 0), NOT the non-trump Ace (idx 5)
        assert (
            choice == 0
        ), f"Expected right bower (idx 0), got idx {choice} ({hand[choice]})"

    def test_no_right_bower_lead_with_only_4_trump(self):
        """With both bowers but only 4 trump, should NOT trigger the new tier.

        Falls through to Step 1 (non-trump Aces) or Step 2 (draw trump).
        """
        glutton = GluttonStrategy()

        # 4 trump (including both bowers) + non-trump Ace
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("D", "J"),  # idx 1 - Left bower
            Card("H", "A"),  # idx 2 - Trump Ace
            Card("H", "K"),  # idx 3 - Trump King
            Card("C", "A"),  # idx 4 - Non-trump Ace
            Card("S", "T"),  # idx 5 - Offsuit
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=0)
        choice = glutton.choose_card(hand, [], "suit", "H", 0)

        # Should NOT lead right bower — should lead non-trump Ace (Step 1)
        assert (
            choice == 4
        ), f"Expected non-trump Ace (idx 4), got idx {choice} ({hand[choice]})"

    def test_no_right_bower_lead_with_only_one_bower(self):
        """With only right bower (no left) + 5 trump, should NOT trigger new tier.

        Falls through to Step 2 (draw trump with lowest).
        """
        glutton = GluttonStrategy()

        # 5 trump (right bower only, no left) + offsuit
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("H", "A"),  # idx 1 - Trump Ace
            Card("H", "K"),  # idx 2 - Trump King
            Card("H", "Q"),  # idx 3 - Trump Queen
            Card("H", "T"),  # idx 4 - Trump Ten
            Card("C", "A"),  # idx 5 - Non-trump Ace
        ]

        glutton.on_hand_start(hand, "suit", "H", player_index=0)
        choice = glutton.choose_card(hand, [], "suit", "H", 0)

        # Should lead non-trump Ace (Step 1), not right bower
        assert (
            choice == 5
        ), f"Expected non-trump Ace (idx 5), got idx {choice} ({hand[choice]})"


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
    """Tests for correct card ranking on low contracts (#2098, #2300).

    In low contracts (10 high, A low), the Glutton should:
    - Lead with STRONGEST cards (tens) to win the current trick (greedy)
    - Discard weak cards when following and can't win
    - Use the cheapest winner when following and can win
    """

    def test_low_lead_plays_strongest_card(self):
        """On low contracts, lead with strongest card (T) to win the trick (#2300)."""
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

        # Greedy: lead strongest card from longest suit to win the trick.
        # card_value_for_dump inverts ranks for low (T=4, J=3, ... A=0),
        # so max() correctly picks T.
        assert (
            hand[choice].rank == "T"
        ), f"Low lead should play T (strongest), got {hand[choice]}"

    def test_low_lead_order_strong_to_weak(self):
        """On low contracts, successive leads go strong-to-weak (T, T, J, J, Q) (#2300)."""
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

        # Greedy: lead strong-to-weak in Low: T, T, J, J, Q
        assert lead_ranks == [
            "T",
            "T",
            "J",
            "J",
            "Q",
        ], f"Low leads should go strong-to-weak, got {lead_ranks}"

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


class TestDiscardValueOnly:
    """Verify discard picks lowest-value non-trump card, ignoring suit counts.

    Regression tests for #2300: the old void-suit sort in _choose_discard
    preferentially discarded from shorter suits.  This caused high-value
    cards (e.g. Aces) to be dumped from non-void suits while low cards in
    longer suits were preserved — a net trick loss.
    """

    def test_discard_picks_lowest_value_not_shortest_suit(self):
        """Ace in a long suit should still be kept over 10 in a short suit."""
        glutton = GluttonStrategy(debug=True)

        # Trump is hearts.  Hand has:
        #   1 spade  (A♠ — high value, short suit)
        #   2 clubs  (10♣, Q♣ — low value, longer suit)
        #   1 trump  (K♥)
        hand = [
            Card("S", "A"),  # idx 0 - lone spade, high value
            Card("C", "T"),  # idx 1 - clubs (low value)
            Card("C", "Q"),  # idx 2 - clubs (medium value)
            Card("H", "K"),  # idx 3 - trump
        ]
        glutton.on_hand_start(hand[:], "suit", "H", player_index=0)

        # Leading — glutton leads, then must discard on later tricks.
        # Call _choose_discard directly to test the discard logic.
        legal = [0, 1, 2]  # non-trump indices
        choice = glutton._choose_discard(hand, legal)

        # 10♣ is the lowest-value non-trump card — should be discarded.
        # Old code would discard A♠ because spades has count=1 (shortest).
        assert (
            choice == 1
        ), f"Should discard 10♣ (lowest value), got idx {choice} ({hand[choice]})"

    def test_discard_ace_kept_over_ten_in_singleton_suit(self):
        """A singleton Ace should NOT be discarded just because its suit is short."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("S", "A"),  # idx 0 - singleton spade Ace
            Card("C", "T"),  # idx 1 - clubs Ten (low)
            Card("C", "J"),  # idx 2 - clubs Jack
            Card("C", "Q"),  # idx 3 - clubs Queen
            Card("H", "A"),  # idx 4 - trump
        ]
        glutton.on_hand_start(hand[:], "suit", "H", player_index=0)

        legal = [0, 1, 2, 3]  # non-trump indices
        choice = glutton._choose_discard(hand, legal)

        # 10♣ (idx 1) is the lowest-value non-trump — discard it.
        assert (
            choice == 1
        ), f"Should discard 10♣ (lowest value), got idx {choice} ({hand[choice]})"

    def test_isolated_discard_same_behaviour(self):
        """GluttonIsolatedStrategy should match GluttonStrategy discard."""
        isolated = GluttonIsolatedStrategy(
            debug=True,
            smart_discards=True,
            partner_awareness=True,
        )

        hand = [
            Card("S", "A"),  # idx 0 - singleton spade Ace
            Card("C", "T"),  # idx 1 - clubs Ten (low)
            Card("C", "Q"),  # idx 2 - clubs Queen
            Card("H", "K"),  # idx 3 - trump
        ]
        isolated.on_hand_start(hand[:], "suit", "H", player_index=0)

        legal = [0, 1, 2]
        choice = isolated._choose_discard_smart(hand, legal)

        assert (
            choice == 1
        ), f"Isolated should discard 10♣ (lowest value), got idx {choice} ({hand[choice]})"


class TestContractSyncDefenseInDepth:
    """Tests for defense-in-depth contract sync (#2133 Bug B).

    These tests verify that choose_card() correctly handles Low/Suit
    contracts even when on_hand_start() was never called. Before the fix,
    the stale default _contract_type="high" would cause incorrect card
    ranking in _choose_discard and _choose_lead.
    """

    def test_low_discard_without_on_hand_start(self):
        """Low discard should dump weakest (A) without on_hand_start.

        Before the fix, _contract_type stayed "high" and the discard
        logic used high-contract ranking, dumping T (strongest in low)
        instead of A (weakest in low).
        """
        glutton = GluttonStrategy(debug=True)
        # Do NOT call on_hand_start — simulating the bug scenario

        hand = [
            Card("H", "T"),  # idx 0 - strongest in low
            Card("H", "K"),  # idx 1
            Card("H", "A"),  # idx 2 - weakest in low
        ]

        # Opponent leads T (strongest in low), partner plays Q
        # We follow suit but can't beat T — must discard
        plays = [
            (0, Card("H", "T")),
            (1, Card("H", "Q")),
        ]

        choice = glutton.choose_card(hand, plays, "low", None, 2)

        assert (
            hand[choice].rank == "A"
        ), f"Low discard without on_hand_start should dump A (weakest), got {hand[choice]}"

    def test_low_lead_without_on_hand_start(self):
        """Low lead should play strongest card (T) without on_hand_start (#2300).

        Greedy strategy always leads strongest to win the current trick.
        In Low contracts, T is strongest (value 4).
        """
        glutton = GluttonStrategy(debug=True)
        # Do NOT call on_hand_start

        hand = [
            Card("S", "T"),  # idx 0 - strongest in low
            Card("S", "K"),  # idx 1
            Card("S", "A"),  # idx 2 - weakest in low
            Card("H", "T"),  # idx 3
            Card("H", "K"),  # idx 4
            Card("H", "A"),  # idx 5
        ]

        # Leading with 6-card hand (not 10, so the old fallback wouldn't fire)
        choice = glutton.choose_card(hand, [], "low", None, 0)

        assert (
            hand[choice].rank == "T"
        ), f"Low lead without on_hand_start should play T (strongest), got {hand[choice]}"

    def test_contract_type_synced_on_every_call(self):
        """_contract_type should reflect the most recent choose_card() call.

        This ensures helpers like _choose_discard and _choose_lead always
        use the current call's contract_type, not stale state from a
        previous hand.
        """
        glutton = GluttonStrategy()

        # First call with "high"
        hand_high = [Card("S", "A"), Card("S", "T")]
        glutton.choose_card(hand_high, [], "high", None, 0)
        assert glutton._contract_type == "high"

        # Second call with "low" — _contract_type must update
        hand_low = [Card("S", "A"), Card("S", "T")]
        glutton.choose_card(hand_low, [], "low", None, 0)
        assert (
            glutton._contract_type == "low"
        ), f"Expected _contract_type='low' after low call, got '{glutton._contract_type}'"

        # Third call with "suit" — _contract_type must update again
        hand_suit = [Card("H", "J"), Card("C", "T")]
        glutton.choose_card(hand_suit, [], "suit", "H", 0)
        assert (
            glutton._contract_type == "suit"
        ), f"Expected _contract_type='suit', got '{glutton._contract_type}'"
        assert (
            glutton._trump_suit == "H"
        ), f"Expected _trump_suit='H', got '{glutton._trump_suit}'"

    def test_following_trick1_no_fallback(self):
        """Following on trick 1 (10-card hand) should sync contract.

        The old fallback only fired on 10-card hand when leading
        (not plays_so_far). Following on trick 1 with 10 cards would
        NOT trigger the fallback, leaving _contract_type stale.
        """
        glutton = GluttonStrategy(debug=True)
        # Do NOT call on_hand_start

        # 10-card hand, following (not leading) on trick 1
        hand = [
            Card("H", "T"),  # idx 0 - strongest in low
            Card("H", "J"),  # idx 1
            Card("H", "Q"),  # idx 2
            Card("H", "K"),  # idx 3
            Card("H", "A"),  # idx 4 - weakest in low
            Card("S", "T"),  # idx 5
            Card("S", "J"),  # idx 6
            Card("S", "Q"),  # idx 7
            Card("S", "K"),  # idx 8
            Card("S", "A"),  # idx 9
        ]

        # Opponent leads — we're following on trick 1 with all 10 cards
        plays = [(0, Card("H", "T"))]

        glutton.choose_card(hand, plays, "low", None, 1)

        # In low contract, T is the trick winner rank (strongest).
        # Opponent led H-T. We must follow hearts. Our H-T ties,
        # but everything else in hearts loses. The correct discard
        # under low ranking: dump the weakest (H-A).
        # Verify contract was synced (the key invariant):
        assert glutton._contract_type == "low", (
            f"Expected _contract_type='low' on 10-card follow, "
            f"got '{glutton._contract_type}'"
        )

    def test_isolated_low_discard_without_on_hand_start(self):
        """GluttonIsolatedStrategy low discard without on_hand_start.

        Same defense-in-depth test for the isolated variant.
        """
        glutton = GluttonIsolatedStrategy(
            debug=True,
            smart_discards=True,
            partner_awareness=True,
        )
        # Do NOT call on_hand_start

        hand = [
            Card("H", "T"),  # idx 0 - strongest in low
            Card("H", "K"),  # idx 1
            Card("H", "A"),  # idx 2 - weakest in low
        ]

        plays = [
            (0, Card("H", "T")),
            (1, Card("H", "Q")),
        ]

        choice = glutton.choose_card(hand, plays, "low", None, 2)

        assert (
            hand[choice].rank == "A"
        ), f"Isolated low discard without on_hand_start should dump A, got {hand[choice]}"

    def test_isolated_contract_type_synced(self):
        """GluttonIsolatedStrategy syncs _contract_type on every call."""
        glutton = GluttonIsolatedStrategy()

        hand = [Card("S", "A"), Card("S", "T")]
        glutton.choose_card(hand, [], "low", None, 0)
        assert glutton._contract_type == "low"
        assert glutton._trump_suit is None

        glutton.choose_card(hand, [], "suit", "H", 0)
        assert glutton._contract_type == "suit"
        assert glutton._trump_suit == "H"


class TestStaleInferenceReset:
    """Tests for stale inference reset when contract changes (#2139).

    When on_hand_start() is never called, the defense-in-depth sync in
    choose_card() should reset _seen_counts and _void_suits_by_seat when
    the contract changes — stale inference from a previous hand could
    cause incorrect decisions.
    """

    def test_glutton_inference_cleared_on_contract_change(self):
        """GluttonStrategy clears inference when contract changes mid-stream.

        Simulate: hand 1 under "high" accumulates inference, then hand 2
        switches to "low" without on_hand_start.  The stale inference from
        hand 1 must not persist into hand 2.
        """
        glutton = GluttonStrategy(debug=True)

        # Simulate hand 1 under "high" with some observed plays
        hand1 = [
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "T"),
            Card("S", "J"),
        ]
        glutton.on_hand_start(hand1, "high", None, 0)
        # Observe some plays to populate inference
        glutton.observe_play(1, Card("C", "A"), [(1, Card("C", "A"))], "high", None)
        glutton.observe_play(
            2, Card("D", "T"), [(1, Card("C", "A")), (2, Card("D", "T"))], "high", None
        )
        assert len(glutton._seen_counts) > 0, "Precondition: inference populated"
        assert any(
            len(v) > 0 for v in glutton._void_suits_by_seat.values()
        ), "Precondition: void inference populated"

        # Hand 2 starts with a different contract but NO on_hand_start
        hand2 = [Card("H", "T"), Card("H", "K"), Card("H", "A")]
        glutton.choose_card(hand2, [], "low", None, 0)

        # Inference should have been cleared by the contract change
        assert (
            glutton._seen_counts == {}
        ), f"Stale _seen_counts not cleared on contract change: {glutton._seen_counts}"
        assert all(
            len(v) == 0 for v in glutton._void_suits_by_seat.values()
        ), f"Stale _void_suits_by_seat not cleared: {glutton._void_suits_by_seat}"

    def test_glutton_inference_preserved_within_hand(self):
        """Inference should NOT be cleared on subsequent calls within the same hand."""
        glutton = GluttonStrategy(debug=True)

        hand = [
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "T"),
            Card("S", "J"),
            Card("S", "Q"),
            Card("D", "A"),
            Card("D", "K"),
            Card("D", "Q"),
            Card("C", "T"),
            Card("C", "J"),
        ]
        glutton.on_hand_start(hand, "high", None, 0)

        # Observe a play to populate inference
        glutton.observe_play(
            1, Card("C", "A"), [(0, Card("H", "A")), (1, Card("C", "A"))], "high", None
        )
        assert len(glutton._seen_counts) > 0

        # Call choose_card with SAME contract — inference must be preserved
        remaining = hand[1:]  # 9 cards
        plays = [(1, Card("S", "A"))]
        glutton.choose_card(remaining, plays, "high", None, 0)

        assert (
            len(glutton._seen_counts) > 0
        ), "Inference should be preserved within the same hand/contract"

    def test_glutton_trump_change_clears_inference(self):
        """Changing trump_suit (same contract_type) also clears inference."""
        glutton = GluttonStrategy(debug=True)

        hand1 = [Card("H", "J"), Card("S", "T")]
        glutton.on_hand_start(hand1, "suit", "H", 0)
        glutton.observe_play(1, Card("D", "A"), [(1, Card("D", "A"))], "suit", "H")
        assert len(glutton._seen_counts) > 0

        # New hand with different trump, no on_hand_start
        hand2 = [Card("S", "J"), Card("D", "T")]
        glutton.choose_card(hand2, [], "suit", "S", 0)

        assert (
            glutton._seen_counts == {}
        ), "Stale inference not cleared on trump_suit change"

    def test_isolated_inference_cleared_on_contract_change(self):
        """GluttonIsolatedStrategy clears inference when contract changes."""
        glutton = GluttonIsolatedStrategy(
            debug=True,
            smart_leads=True,
            partner_awareness=True,
        )

        # Hand 1 under "high" — accumulate inference
        hand1 = [
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "T"),
            Card("S", "J"),
        ]
        glutton.on_hand_start(hand1, "high", None, 0)
        glutton.observe_play(1, Card("C", "A"), [(1, Card("C", "A"))], "high", None)
        glutton.observe_play(
            2, Card("D", "T"), [(1, Card("C", "A")), (2, Card("D", "T"))], "high", None
        )
        assert len(glutton._seen_counts) > 0

        # Hand 2 with different contract, no on_hand_start
        hand2 = [Card("H", "T"), Card("H", "K"), Card("H", "A")]
        glutton.choose_card(hand2, [], "low", None, 0)

        assert (
            glutton._seen_counts == {}
        ), f"Isolated: stale _seen_counts not cleared: {glutton._seen_counts}"
        assert all(
            len(v) == 0 for v in glutton._void_suits_by_seat.values()
        ), f"Isolated: stale _void_suits_by_seat not cleared: {glutton._void_suits_by_seat}"

    def test_isolated_inference_preserved_within_hand(self):
        """Isolated variant preserves inference within the same hand."""
        glutton = GluttonIsolatedStrategy(debug=True, partner_awareness=True)

        hand = [
            Card("H", "A"),
            Card("H", "K"),
            Card("S", "T"),
            Card("S", "J"),
            Card("S", "Q"),
            Card("D", "A"),
            Card("D", "K"),
            Card("D", "Q"),
            Card("C", "T"),
            Card("C", "J"),
        ]
        glutton.on_hand_start(hand, "high", None, 0)
        glutton.observe_play(
            1, Card("C", "A"), [(0, Card("H", "A")), (1, Card("C", "A"))], "high", None
        )
        assert len(glutton._seen_counts) > 0

        remaining = hand[1:]
        plays = [(1, Card("S", "A"))]
        glutton.choose_card(remaining, plays, "high", None, 0)

        assert (
            len(glutton._seen_counts) > 0
        ), "Isolated: inference should be preserved within same hand/contract"


class TestCrossMatchIsolation:
    """Prove that deepcopy-per-match prevents shared-state contamination.

    Regression test for #2168: AIManager stored ONE GluttonStrategy instance
    per model.  All concurrent matches shared that instance, leaking
    seen_counts, void_suits, contract_type, and trump_suit across games.
    The fix deepcopies the strategy at engine-build time.
    """

    def test_deepcopy_isolates_seen_counts(self):
        """Two cloned strategies must not share _seen_counts."""
        shared = GluttonStrategy()
        a = copy.deepcopy(shared)
        b = copy.deepcopy(shared)

        # Match A is a suit/Hearts contract
        a.on_hand_start(
            [Card("H", "A"), Card("H", "K"), Card("S", "T")],
            "suit",
            "H",
            player_index=1,
        )
        a.observe_play(
            0,
            Card("H", "Q"),
            [(0, Card("H", "Q"))],
            "suit",
            "H",
        )

        # Match B is a high (no-trump) contract — sees completely different cards
        b.on_hand_start(
            [Card("D", "A"), Card("D", "K"), Card("C", "T")],
            "high",
            None,
            player_index=2,
        )
        b.observe_play(
            1,
            Card("C", "A"),
            [(1, Card("C", "A"))],
            "high",
            None,
        )

        # Match A should only know about H-Q, not C-A
        assert Card("H", "Q") in a._seen_counts
        assert (
            Card("C", "A") not in a._seen_counts
        ), "Match A leaked seen_counts from Match B"

        # Match B should only know about C-A, not H-Q
        assert Card("C", "A") in b._seen_counts
        assert (
            Card("H", "Q") not in b._seen_counts
        ), "Match B leaked seen_counts from Match A"

        # Original shared instance must be untouched
        assert (
            len(shared._seen_counts) == 0
        ), "Shared prototype was mutated by a cloned match"

    def test_deepcopy_isolates_void_suits(self):
        """Void-suit inference must not leak between cloned strategies."""
        shared = GluttonStrategy()
        a = copy.deepcopy(shared)
        b = copy.deepcopy(shared)

        a.on_hand_start(
            [Card("H", "A"), Card("S", "K")],
            "suit",
            "H",
            player_index=1,
        )
        # Player 2 fails to follow clubs → void in clubs
        a.observe_play(
            2,
            Card("H", "T"),
            [(0, Card("C", "A")), (1, Card("C", "K")), (2, Card("H", "T"))],
            "suit",
            "H",
        )

        b.on_hand_start(
            [Card("D", "A"), Card("C", "T")],
            "high",
            None,
            player_index=3,
        )

        assert "C" in a._void_suits_by_seat[2], "Match A should infer seat 2 void in C"
        assert (
            "C" not in b._void_suits_by_seat[2]
        ), "Match B should not inherit void inference from Match A"

    def test_deepcopy_isolates_contract_context(self):
        """Contract type and trump suit must not leak between clones."""
        shared = GluttonStrategy()
        a = copy.deepcopy(shared)
        b = copy.deepcopy(shared)

        a.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)
        b.on_hand_start([Card("D", "A")], "low", None, player_index=0)

        assert a._contract_type == "suit"
        assert a._trump_suit == "H"
        assert b._contract_type == "low"
        assert b._trump_suit is None
        # Shared prototype retains its default
        assert shared._contract_type == "high"
        assert shared._trump_suit is None


class TestSuitContinuity:
    """Tests for suit continuity feature (#2506).

    After winning a trick as leader in suit X, the AI should prefer
    continuing to lead suit X if it still holds cards in that suit.
    """

    def test_continues_suit_after_winning_lead_suit_contract(self):
        """Suit contract: after winning trick leading clubs, continue clubs."""
        g = GluttonStrategy()
        hand_full = [
            Card("C", "A"),  # 0 - clubs ace
            Card("C", "K"),  # 1 - clubs king
            Card("C", "Q"),  # 2 - clubs queen
            Card("D", "A"),  # 3 - diamonds ace
            Card("D", "K"),  # 4 - diamonds king
            Card("H", "T"),  # 5 - hearts ten
            Card("S", "T"),  # 6 - spades ten
        ]
        g.on_hand_start(list(hand_full), "suit", "H", player_index=0)

        # Simulate a completed trick: seat 0 led C-A and won
        trick_plays = [
            (0, Card("C", "A")),
            (1, Card("C", "T")),
            (2, Card("C", "J")),
            (3, Card("C", "T")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "suit", "H")

        # Now leading again with remaining hand (minus the A♣ that was played)
        remaining = [
            Card("C", "K"),  # 0
            Card("C", "Q"),  # 1
            Card("D", "A"),  # 2 - diamond ace (high value)
            Card("D", "K"),  # 3
            Card("H", "T"),  # 4 - trump
            Card("S", "T"),  # 5
        ]
        choice = g.choose_card(remaining, [], "suit", "H", 0)
        chosen = remaining[choice]
        # Should continue clubs (C-K or C-Q), not switch to diamonds or trump
        assert chosen.suit == "C", f"Expected club continuation, got {chosen}"

    def test_continues_suit_after_winning_lead_high_contract(self):
        """High contract: after winning trick leading spades, continue spades."""
        g = GluttonStrategy()
        hand_full = [
            Card("S", "A"),
            Card("S", "K"),
            Card("S", "Q"),
            Card("D", "A"),
            Card("D", "K"),
            Card("H", "T"),
            Card("C", "T"),
        ]
        g.on_hand_start(list(hand_full), "high", None, player_index=2)

        # Simulate: seat 2 led S-A and won
        trick_plays = [
            (2, Card("S", "A")),
            (3, Card("S", "T")),
            (0, Card("S", "J")),
            (1, Card("S", "T")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "high", None)

        remaining = [
            Card("S", "K"),  # 0
            Card("S", "Q"),  # 1
            Card("D", "A"),  # 2 - diamond ace
            Card("D", "K"),  # 3
            Card("H", "T"),  # 4
            Card("C", "T"),  # 5
        ]
        choice = g.choose_card(remaining, [], "high", None, 2)
        chosen = remaining[choice]
        assert chosen.suit == "S", f"Expected spade continuation, got {chosen}"

    def test_no_continuity_when_leader_lost(self):
        """Continuity should NOT trigger when the leader lost the trick."""
        g = GluttonStrategy()
        hand = [
            Card("C", "A"),  # 0
            Card("C", "K"),  # 1
            Card("D", "A"),  # 2 - diamond ace (highest)
            Card("D", "K"),  # 3
            Card("D", "Q"),  # 4
            Card("H", "T"),  # 5
        ]
        g.on_hand_start(list(hand), "high", None, player_index=0)

        # Seat 1 led clubs but seat 0 won (we're seat 0, we didn't lead)
        # Actually, let's simulate seat 1 leading and losing to seat 3
        trick_plays = [
            (1, Card("C", "K")),  # seat 1 led clubs
            (2, Card("C", "T")),
            (3, Card("C", "A")),  # seat 3 wins
            (0, Card("C", "J")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "high", None)

        # Leader (seat 1) lost → continuity should be cleared
        assert g._last_won_lead_suit is None

    def test_continuity_cleared_on_hand_start(self):
        """Continuity state resets at the start of each hand."""
        g = GluttonStrategy()
        g._last_won_lead_suit = "C"
        g._last_won_lead_seat = 0

        g.on_hand_start([Card("D", "A")] * 10, "high", None, player_index=0)
        assert g._last_won_lead_suit is None
        assert g._last_won_lead_seat is None

    def test_no_continuity_when_suit_exhausted(self):
        """If all cards in the continued suit are gone, fall through to other logic."""
        g = GluttonStrategy()
        hand = [
            Card("D", "A"),  # 0
            Card("D", "K"),  # 1
            Card("H", "T"),  # 2
            Card("S", "T"),  # 3
        ]
        g.on_hand_start([Card("C", "A")] + list(hand), "high", None, player_index=0)

        # Simulate winning with clubs lead
        trick_plays = [
            (0, Card("C", "A")),
            (1, Card("C", "T")),
            (2, Card("C", "J")),
            (3, Card("C", "T")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "high", None)

        # No clubs left in hand — should fall through to other logic
        choice = g.choose_card(hand, [], "high", None, 0)
        chosen = hand[choice]
        # Should pick from remaining cards (not crash)
        assert chosen in hand

    def test_continuity_only_for_winning_seat(self):
        """Continuity should only apply to the seat that won, not others."""
        g = GluttonStrategy()
        # Diamonds is strictly longest suit (3 vs 1 club)
        hand = [
            Card("C", "K"),  # 0
            Card("D", "A"),  # 1 - diamond ace
            Card("D", "K"),  # 2
            Card("D", "Q"),  # 3
            Card("H", "T"),  # 4
        ]
        g.on_hand_start(list(hand), "high", None, player_index=2)

        # Seat 0 led clubs and won — not seat 2
        trick_plays = [
            (0, Card("C", "A")),
            (1, Card("C", "T")),
            (2, Card("C", "J")),
            (3, Card("C", "T")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "high", None)

        assert g._last_won_lead_seat == 0  # seat 0 won, not us (seat 2)

        # Seat 2 now leads — continuity should NOT apply (wrong seat)
        choice = g.choose_card(hand, [], "high", None, 2)
        chosen = hand[choice]
        # Should use normal logic (longest suit = diamonds), not clubs
        assert chosen.suit == "D", f"Expected diamond lead (longest suit), got {chosen}"

    def test_isolated_suit_continuity_flag_off(self):
        """GluttonIsolatedStrategy with suit_continuity=False should NOT continue suit."""
        g = GluttonIsolatedStrategy(smart_leads=True, suit_continuity=False)
        hand = [
            Card("C", "A"),
            Card("C", "K"),
            Card("D", "A"),
            Card("D", "K"),
            Card("D", "Q"),
            Card("H", "T"),
        ]
        g.on_hand_start(list(hand), "high", None, player_index=0)

        # Simulate winning with clubs lead
        trick_plays = [
            (0, Card("C", "A")),
            (1, Card("C", "T")),
            (2, Card("C", "J")),
            (3, Card("C", "T")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "high", None)

        # With suit_continuity=False, should NOT track
        assert g._last_won_lead_suit is None

    def test_isolated_suit_continuity_flag_on(self):
        """GluttonIsolatedStrategy with suit_continuity=True should continue suit."""
        g = GluttonIsolatedStrategy(smart_leads=True, suit_continuity=True)
        hand_full = [
            Card("C", "A"),
            Card("C", "K"),
            Card("C", "Q"),
            Card("D", "A"),
            Card("D", "K"),
            Card("H", "T"),
            Card("S", "T"),
        ]
        g.on_hand_start(list(hand_full), "high", None, player_index=0)

        # Simulate winning with clubs lead
        trick_plays = [
            (0, Card("C", "A")),
            (1, Card("C", "T")),
            (2, Card("C", "J")),
            (3, Card("C", "T")),
        ]
        for i, (seat, card) in enumerate(trick_plays):
            g.observe_play(seat, card, trick_plays[: i + 1], "high", None)

        assert g._last_won_lead_suit == "C"

        remaining = [
            Card("C", "K"),  # 0
            Card("C", "Q"),  # 1
            Card("D", "A"),  # 2
            Card("D", "K"),  # 3
            Card("H", "T"),  # 4
            Card("S", "T"),  # 5
        ]
        choice = g.choose_card(remaining, [], "high", None, 0)
        chosen = remaining[choice]
        assert chosen.suit == "C", f"Expected club continuation, got {chosen}"
