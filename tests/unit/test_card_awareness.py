"""
Card Awareness Tests: Hooks and card tracking for GluttonStrategy.

These tests verify that:
1. cards_that_beat() correctly identifies cards that beat a candidate
2. The hooks (on_hand_start, observe_play) properly track game state
3. Double-deck semantics are correctly handled (2 copies per card)

NOTE: The simplified GluttonStrategy doesn't use sure-winner logic for
decision-making, but the card tracking infrastructure is still tested here.
"""

from bid_euchre.core.cards import Card, cards_that_beat
from bid_euchre.strategy import GluttonStrategy


class TestCardsThatBeat:
    """Unit tests for the cards_that_beat() utility."""

    def test_right_bower_unbeatable(self):
        """Right bower in suit contract cannot be beaten by any card."""
        right_bower = Card("H", "J")  # Hearts trump, J of hearts = right bower
        beating = cards_that_beat(right_bower, led_suit="H", trump_suit="H", contract_type="suit")
        assert beating == set(), "Right bower should have no cards that beat it"

    def test_left_bower_only_beaten_by_right(self):
        """Left bower beaten only by right bower."""
        left_bower = Card("D", "J")  # Diamonds J is left bower when Hearts trump
        beating = cards_that_beat(left_bower, led_suit="H", trump_suit="H", contract_type="suit")
        # Only right bower (H-J) beats left bower
        assert beating == {Card("H", "J")}, "Left bower beaten only by right bower"

    def test_trump_ace_beaten_by_bowers(self):
        """Trump ace beaten by both bowers."""
        trump_ace = Card("H", "A")
        beating = cards_that_beat(trump_ace, led_suit="H", trump_suit="H", contract_type="suit")
        assert Card("H", "J") in beating, "Right bower should beat trump ace"
        assert Card("D", "J") in beating, "Left bower should beat trump ace"
        # No other cards should beat it
        non_bower_threats = beating - {Card("H", "J"), Card("D", "J")}
        assert non_bower_threats == set(), "Only bowers beat trump ace"

    def test_trump_king_beaten_by_ace_and_bowers(self):
        """Trump king beaten by ace and bowers."""
        trump_king = Card("H", "K")
        beating = cards_that_beat(trump_king, led_suit="H", trump_suit="H", contract_type="suit")
        assert Card("H", "J") in beating  # Right bower
        assert Card("D", "J") in beating  # Left bower
        assert Card("H", "A") in beating  # Trump ace
        # Verify no non-trump cards beat it
        for suit in ["C", "S"]:
            for rank in ["T", "J", "Q", "K", "A"]:
                assert Card(suit, rank) not in beating

    def test_offsuit_beaten_by_trump_and_higher_led(self):
        """Non-trump card beaten by all trump and higher led-suit cards."""
        offsuit_queen = Card("S", "Q")  # Spades queen, hearts trump
        beating = cards_that_beat(offsuit_queen, led_suit="S", trump_suit="H", contract_type="suit")

        # All hearts (trump) beat it
        assert Card("H", "T") in beating
        assert Card("H", "A") in beating
        assert Card("H", "J") in beating  # Right bower
        assert Card("D", "J") in beating  # Left bower (counts as hearts)

        # Higher spades beat it
        assert Card("S", "K") in beating
        assert Card("S", "A") in beating

        # Lower spades don't beat it
        assert Card("S", "T") not in beating
        assert Card("S", "J") not in beating

        # Clubs (offsuit, not led) don't beat it
        assert Card("C", "A") not in beating

    def test_high_contract_no_trump(self):
        """In high contract, only higher ranks of same suit beat."""
        queen = Card("C", "Q")
        beating = cards_that_beat(queen, led_suit="C", trump_suit=None, contract_type="high")
        assert beating == {Card("C", "K"), Card("C", "A")}

    def test_high_contract_ace_unbeatable(self):
        """In high contract, ace of led suit is unbeatable."""
        ace = Card("C", "A")
        beating = cards_that_beat(ace, led_suit="C", trump_suit=None, contract_type="high")
        assert beating == set(), "Ace of led suit should be unbeatable in high contract"

    def test_low_contract_reversed_ranks(self):
        """In low contract, lower ranks beat higher (A is weakest, T is strongest)."""
        queen = Card("C", "Q")
        beating = cards_that_beat(queen, led_suit="C", trump_suit=None, contract_type="low")
        # In low: A < K < Q < J < T, so Q is beaten by J and T
        assert Card("C", "J") in beating
        assert Card("C", "T") in beating
        # K and A are weaker in low, so they don't beat Q
        assert Card("C", "K") not in beating
        assert Card("C", "A") not in beating

    def test_low_contract_ten_unbeatable(self):
        """In low contract, T of led suit is strongest (unbeatable)."""
        ten = Card("C", "T")
        beating = cards_that_beat(ten, led_suit="C", trump_suit=None, contract_type="low")
        assert beating == set(), "Ten of led suit should be unbeatable in low contract"


class TestSureWinnerInfrastructure:
    """Test the sure-winner detection infrastructure.

    NOTE: The simplified Glutton doesn't use sure-winner logic for decisions,
    but the _is_sure_winner method still exists for potential future use.
    """

    def test_right_bower_always_sure_winner(self):
        """Right bower has no cards that beat it."""
        strategy = GluttonStrategy()
        hand = [Card("H", "J"), Card("C", "T")]
        plays_so_far = [(0, Card("S", "K"))]

        strategy.on_hand_start(hand, "suit", "H", player_index=1)

        # Right bower is a sure winner (nothing beats it)
        assert strategy._is_sure_winner(hand[0], plays_so_far, hand)

    def test_left_bower_sure_after_both_right_bowers(self):
        """Left bower is sure winner once BOTH right bowers seen (double deck)."""
        strategy = GluttonStrategy()
        hand = [Card("D", "J"), Card("C", "T")]

        strategy.on_hand_start(hand, "suit", "H", player_index=1)
        strategy._seen_counts[Card("H", "J")] = 2  # Both right bowers seen

        plays_so_far = [(0, Card("S", "K"))]
        assert strategy._is_sure_winner(hand[0], plays_so_far, hand)

    def test_left_bower_not_sure_with_one_right(self):
        """Left bower NOT sure with only one right bower seen."""
        strategy = GluttonStrategy()
        hand = [Card("D", "J"), Card("C", "T")]

        strategy.on_hand_start(hand, "suit", "H", player_index=1)
        strategy._seen_counts[Card("H", "J")] = 1  # Only one right bower seen

        plays_so_far = [(0, Card("S", "K"))]
        assert not strategy._is_sure_winner(hand[0], plays_so_far, hand)


class TestStateTracking:
    """Test that card tracking works with hooks-based API."""

    def test_on_hand_start_resets_state(self):
        """on_hand_start resets all tracking state."""
        strategy = GluttonStrategy()

        # Simulate end of previous hand - some cards tracked
        strategy._seen_counts = {Card("H", "A"): 2, Card("S", "K"): 1}
        strategy._void_suits_by_seat = {0: {"C"}, 1: set(), 2: set(), 3: set()}

        # New hand: call on_hand_start
        new_hand = [
            Card("H", "T"), Card("H", "J"), Card("H", "Q"), Card("H", "K"), Card("H", "A"),
            Card("S", "T"), Card("S", "J"), Card("S", "Q"), Card("S", "K"), Card("S", "A"),
        ]
        strategy.on_hand_start(new_hand, "suit", "H", 0)

        # After reset, tracking should be empty
        assert strategy._seen_counts == {}, "Should reset _seen_counts"
        assert all(len(v) == 0 for v in strategy._void_suits_by_seat.values()), "Should reset voids"

    def test_observe_play_increments_seen_count(self):
        """observe_play increments the seen count for played cards."""
        strategy = GluttonStrategy()
        hand = [Card("H", "A"), Card("S", "T"), Card("C", "Q")]

        # Initialize
        strategy.on_hand_start(hand, "suit", "H", 2)

        # Simulate observing a card played
        strategy.observe_play(
            player_index=0,
            card=Card("H", "K"),
            trick_plays=[(0, Card("H", "K"))],
            contract_type="suit",
            trump_suit="H",
        )

        assert strategy._seen_counts.get(Card("H", "K"), 0) == 1

        # Play the same card again (second copy)
        strategy.observe_play(
            player_index=1,
            card=Card("H", "K"),
            trick_plays=[(0, Card("H", "K")), (1, Card("H", "K"))],
            contract_type="suit",
            trump_suit="H",
        )

        assert strategy._seen_counts.get(Card("H", "K"), 0) == 2

    def test_observe_play_infers_void(self):
        """observe_play infers voids when a player doesn't follow suit."""
        strategy = GluttonStrategy()
        hand = [Card("H", "A"), Card("S", "T")]

        # Initialize
        strategy.on_hand_start(hand, "suit", "H", 2)

        # Player 1 leads clubs
        strategy.observe_play(
            player_index=1,
            card=Card("C", "K"),
            trick_plays=[(1, Card("C", "K"))],
            contract_type="suit",
            trump_suit="H",
        )

        # Player 2 plays a heart (trump) instead of following clubs -> void in clubs
        strategy.observe_play(
            player_index=2,
            card=Card("H", "T"),
            trick_plays=[(1, Card("C", "K")), (2, Card("H", "T"))],
            contract_type="suit",
            trump_suit="H",
        )

        # Player 2 should be marked as void in clubs
        assert "C" in strategy._void_suits_by_seat[2], "Should infer void when not following suit"


class TestPartnerAwarenessPreserved:
    """Verify that partner awareness still works with the simplified logic."""

    def test_does_not_overkill_partner(self):
        """Don't overkill partner even if we have a sure winner."""
        strategy = GluttonStrategy(debug=True)

        hand = [
            Card("H", "J"),  # Right bower (sure winner!)
            Card("C", "T"),  # Cheap offsuit
        ]

        strategy.on_hand_start(hand, "suit", "H", player_index=2)

        # Partner (player 0) is winning with C-A
        plays_so_far = [
            (0, Card("C", "A")),  # Partner led Clubs A - WINNING
            (1, Card("C", "Q")),  # Opponent played Clubs Q
        ]

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should dump cheap offsuit, not overkill partner
        assert choice == 1, "Should dump when partner winning, not overkill"
        assert strategy.decision_log[-1]["scenario"] == "partner_winning"


class TestDoubleDeckSemantics:
    """Test double-deck specific scenarios for the tracking infrastructure."""

    def test_seen_count_capped_at_two(self):
        """Seen count should be capped at 2 (double deck max)."""
        strategy = GluttonStrategy()
        hand = [Card("H", "A")]

        strategy.on_hand_start(hand, "suit", "H", 0)

        # Observe same card 3 times (which shouldn't happen, but test the cap)
        for _ in range(3):
            strategy.observe_play(
                player_index=1,
                card=Card("H", "K"),
                trick_plays=[(1, Card("H", "K"))],
                contract_type="suit",
                trump_suit="H",
            )

        # Should be capped at 2
        assert strategy._seen_counts.get(Card("H", "K"), 0) == 2

    def test_sure_winner_accounts_for_hand_copies(self):
        """Sure winner logic accounts for copies in our own hand."""
        strategy = GluttonStrategy()
        # We hold BOTH copies of the ace (unlikely but valid) + king
        hand = [Card("C", "A"), Card("C", "A"), Card("C", "K")]

        strategy.on_hand_start(hand, "high", None, player_index=1)

        plays_so_far = [(0, Card("C", "Q"))]

        # King is a sure winner because both Aces are in our hand
        assert strategy._is_sure_winner(hand[2], plays_so_far, hand)
