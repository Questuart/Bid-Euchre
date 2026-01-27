"""
Card Awareness Tests: Sure-win logic for GluttonStrategy.

These tests verify that:
1. cards_that_beat() correctly identifies cards that beat a candidate
2. GluttonStrategy only commits to winning when it's guaranteed
3. State tracking persists across tricks and resets on new hands
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


class TestSureWinLogic:
    """Test the sure-win decision logic in GluttonStrategy."""

    def test_right_bower_always_sure_winner(self):
        """Right bower is always a sure winner - no card can beat it."""
        strategy = GluttonStrategy()
        # Can't follow suit (no spades), so both cards are legal
        hand = [Card("H", "J"), Card("C", "T")]  # Right bower + offsuit
        plays_so_far = [(0, Card("S", "K"))]  # Spades led (non-trump)

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
        # Right bower can trump in and is guaranteed to win
        assert choice == 0, "Should play right bower (sure winner)"

    def test_left_bower_sure_winner_after_right_played(self):
        """Left bower is sure winner once right bower has been played."""
        strategy = GluttonStrategy()
        # Simulate right bower already played in a previous trick
        strategy._played_cards = {Card("H", "J")}

        # Can't follow suit (no spades), so both cards are legal
        hand = [Card("D", "J"), Card("C", "T")]  # Left bower + offsuit
        plays_so_far = [(0, Card("S", "K"))]  # Spades led (non-trump)

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
        assert choice == 0, "Left bower is sure winner when right bower played"

    def test_trump_not_sure_winner_when_higher_trump_unplayed(self):
        """Trump that can be beaten is NOT a sure winner - should slough."""
        strategy = GluttonStrategy()
        # Right bower not in played_cards, not in hand -> could beat our trump

        # Can't follow suit (no spades), so both cards are legal
        hand = [Card("H", "A"), Card("C", "T")]  # Trump ace + offsuit
        plays_so_far = [(0, Card("S", "K"))]  # Spades led, 2nd to act

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
        # Trump ace would win, but bowers could beat it - not a sure winner
        # Should slough offsuit instead of committing trump
        assert choice == 1, "Should slough when trump ace isn't a sure win"

    def test_trump_ace_sure_winner_after_both_bowers_played(self):
        """Trump ace IS a sure winner after both bowers have been played."""
        strategy = GluttonStrategy()
        # Both bowers already played
        strategy._played_cards = {Card("H", "J"), Card("D", "J")}

        # Can't follow suit (no spades), so both cards are legal
        hand = [Card("H", "A"), Card("C", "T")]  # Trump ace + offsuit
        plays_so_far = [(0, Card("S", "K"))]  # Spades led

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
        assert choice == 0, "Trump ace is sure winner when both bowers played"

    def test_4th_position_any_winner_is_safe(self):
        """Last to act - any winning card is safe (no one plays after)."""
        strategy = GluttonStrategy()
        # Can't follow suit (no spades), so both cards are legal
        hand = [Card("H", "A"), Card("C", "T")]  # Trump ace + offsuit
        # Setup so opponent (player 2) is winning, not partner (player 1)
        # For player 3: partner is (3+2)%4 = 1, opponents are 0 and 2
        plays_so_far = [
            (0, Card("S", "Q")),  # Opponent leads
            (1, Card("S", "T")),  # Partner plays lower
            (2, Card("S", "K")),  # Opponent is winning
        ]  # 4th to act, spades led, opponent winning

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 3)
        assert choice == 0, "4th position can safely play any winner to beat opponent"

    def test_high_contract_ace_sure_winner(self):
        """In high contract, ace of led suit is always a sure winner."""
        strategy = GluttonStrategy()
        hand = [Card("C", "A"), Card("C", "T")]  # Ace of clubs + ten of clubs
        plays_so_far = [(0, Card("C", "Q"))]  # Clubs queen led

        choice = strategy.choose_card(hand, plays_so_far, "high", None, 1)
        assert choice == 0, "Ace of led suit is sure winner in high contract"

    def test_high_contract_king_not_sure_winner_2nd_position(self):
        """In high contract at 2nd position, king is NOT sure (ace could follow)."""
        strategy = GluttonStrategy()
        hand = [Card("C", "K"), Card("C", "T")]  # King + Ten of clubs
        plays_so_far = [(0, Card("C", "Q"))]  # Clubs queen led, 2nd to act

        choice = strategy.choose_card(hand, plays_so_far, "high", None, 1)
        # King currently wins but ace could beat it (2 more players to act)
        # Should slough C-T instead of committing king
        assert choice == 1, "Should slough when king isn't a sure win (2nd position)"

    def test_high_contract_king_safe_when_ace_played(self):
        """In high contract, king is safe when ace already played."""
        strategy = GluttonStrategy()
        strategy._played_cards = {Card("C", "A")}  # Ace already played

        hand = [Card("C", "K"), Card("C", "T")]  # King + Ten of clubs
        plays_so_far = [(0, Card("C", "Q"))]  # Clubs queen led

        choice = strategy.choose_card(hand, plays_so_far, "high", None, 1)
        # King is now sure winner (ace is gone)
        assert choice == 0, "King is sure winner when ace played"


class TestStateTracking:
    """Test that card tracking persists across tricks and resets on new hand."""

    def test_resets_on_new_hand(self):
        """Card tracking resets when full hand (10 cards) and leading."""
        strategy = GluttonStrategy()

        # Simulate end of previous hand - some cards tracked
        strategy._played_cards = {Card("H", "A"), Card("S", "K"), Card("C", "Q")}

        # New hand: 10 cards, leading (no plays_so_far)
        new_hand = [
            Card("H", "T"), Card("H", "J"), Card("H", "Q"), Card("H", "K"), Card("H", "A"),
            Card("S", "T"), Card("S", "J"), Card("S", "Q"), Card("S", "K"), Card("S", "A"),
        ]
        strategy.choose_card(new_hand, [], "suit", "H", 0)

        # After reset, only our played card should be in _played_cards
        assert len(strategy._played_cards) == 1, "Should reset and only have our played card"

    def test_cards_accumulate_from_plays_so_far(self):
        """Cards from plays_so_far are added to tracking."""
        strategy = GluttonStrategy()

        hand = [Card("H", "A"), Card("S", "T"), Card("C", "Q")]
        plays_so_far = [
            (0, Card("H", "K")),
            (1, Card("D", "J")),
        ]

        strategy.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should have accumulated the plays_so_far cards
        assert Card("H", "K") in strategy._played_cards
        assert Card("D", "J") in strategy._played_cards

    def test_our_play_recorded_for_future(self):
        """Our own played card is recorded for future trick tracking."""
        strategy = GluttonStrategy()

        hand = [Card("H", "J"), Card("S", "T")]  # Right bower + weak
        plays_so_far = [(0, Card("H", "K"))]

        # This should play right bower and record it
        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 1)
        played_card = hand[choice]

        assert played_card in strategy._played_cards, "Our played card should be recorded"


class TestPartnerAwarenessPreserved:
    """Verify that partner awareness still works with the new logic."""

    def test_does_not_overkill_partner_even_with_sure_winner(self):
        """Don't overkill partner even if we have a sure winner."""
        strategy = GluttonStrategy()

        hand = [
            Card("H", "J"),  # Right bower (sure winner!)
            Card("C", "T"),  # Cheap offsuit
        ]

        # Partner (player 0) is winning with C-A
        # Teams: 0+2, 1+3. Player 2's partner is 0
        plays_so_far = [
            (0, Card("C", "A")),  # Partner led Clubs A - WINNING
            (1, Card("C", "Q")),  # Opponent played Clubs Q
        ]

        choice = strategy.choose_card(hand, plays_so_far, "suit", "H", 2)

        # Should dump cheap offsuit, not overkill partner even with sure winner
        assert choice == 1, "Should dump when partner winning, not overkill"
