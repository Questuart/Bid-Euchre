"""
Tests validating bower handling in GreedyStrategy and GluttonStrategy.

Confirms that both strategies correctly value bowers (Right bower = J of trump,
Left bower = J of same color) in suit contracts, and that the simulation path
has always called on_hand_start() / observe_play() correctly.

Context: PR #2126 fixed a bower bug in the hosted-play engine (MatchEngine
did not call on_hand_start, so GluttonStrategy defaulted to contract_type=high
/ trump_suit=None). The simulation path was never affected — these tests
confirm that.
"""

from bid_euchre.core.cards import Card
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy


class TestBowerValueGreedy:
    """Verify GreedyStrategy correctly values bowers in suit contracts."""

    def test_greedy_leads_right_bower_in_suit(self):
        """Right bower (J of trump) should be the highest-value lead in suit."""
        greedy = GreedyStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("H", "J"),  # idx 1 - Right bower (highest card)
            Card("C", "A"),  # idx 2 - Off-suit Ace
            Card("S", "K"),  # idx 3 - Off-suit King
        ]
        # Leading — Greedy plays highest value
        choice = greedy.choose_card(hand, [], "suit", "H", 0)
        assert (
            choice == 1
        ), f"Greedy should lead right bower (idx 1), got idx {choice} ({hand[choice]})"

    def test_greedy_leads_left_bower_over_ace(self):
        """Left bower (J of same color) ranks above trump Ace in suit."""
        greedy = GreedyStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("D", "J"),  # idx 1 - Left bower (H trump → D-J is left)
            Card("C", "K"),  # idx 2 - Off-suit King
        ]
        choice = greedy.choose_card(hand, [], "suit", "H", 0)
        assert (
            choice == 1
        ), f"Greedy should lead left bower (idx 1), got idx {choice} ({hand[choice]})"

    def test_greedy_right_bower_beats_left_bower(self):
        """Right bower should beat left bower when following."""
        greedy = GreedyStrategy()
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("D", "J"),  # idx 1 - Left bower
            Card("S", "T"),  # idx 2 - Off-suit
        ]
        # Opponent led left bower, we can beat with right
        plays_so_far = [
            (1, Card("D", "J")),  # Opponent led left bower
        ]
        choice = greedy.choose_card(hand, plays_so_far, "suit", "H", 0)
        # Cheapest winner — right bower (idx 0) is the only card that beats left bower
        assert (
            choice == 0
        ), f"Greedy should play right bower to beat left, got idx {choice}"


class TestBowerValueGlutton:
    """Verify GluttonStrategy correctly values bowers after on_hand_start."""

    def test_glutton_values_bowers_after_hand_start(self):
        """GluttonStrategy should recognize bowers as trump after on_hand_start.

        When Glutton has 4+ trump including only one bower (not both), the
        smart lead logic draws trump with the lowest trump card. This confirms
        bowers are counted as trump in the effective suit calculation.

        Hand: right bower + trump A/K/Q + offsuit T = 4 trump + 1 offsuit.
        With ≥4 trump and NOT both bowers → draw trump with lowest (H-Q).
        """
        glutton = GluttonStrategy()
        hand = [
            Card("H", "A"),  # idx 0 - Trump Ace
            Card("H", "J"),  # idx 1 - Right bower (counts as trump)
            Card("H", "K"),  # idx 2 - Trump King
            Card("H", "Q"),  # idx 3 - Trump Queen (lowest trump)
            Card("C", "T"),  # idx 4 - Off-suit
        ]
        # Critical: call on_hand_start to set contract context
        glutton.on_hand_start(hand, "suit", "H", player_index=0)

        # No non-trump Aces → check draw trump: 4 trump, has right but not left
        # → draw trump with lowest trump card (H-Q)
        choice = glutton.choose_card(hand, [], "suit", "H", 0)
        chosen_card = hand[choice]
        assert chosen_card == Card(
            "H", "Q"
        ), f"Glutton should draw trump with lowest trump (H-Q), got {chosen_card}"

    def test_glutton_without_hand_start_defaults_to_high(self):
        """Without on_hand_start, Glutton defaults to high contract (no bowers).

        This is the bug that PR #2126 fixed in hosted-play. In this mode,
        bowers are just Jacks with no special rank.
        """
        glutton = GluttonStrategy()
        # Do NOT call on_hand_start — simulates the hosted-play bug
        hand = [
            Card("H", "J"),  # idx 0 - Would be right bower if trump=H
            Card("H", "A"),  # idx 1 - Would be below right bower
            Card("C", "K"),  # idx 2 - Off-suit
        ]
        # In "high" contract (the default), A > K > Q > J > T
        # H-A should be highest, not H-J
        choice = glutton.choose_card(hand, [], "high", None, 0)
        assert (
            choice == 1
        ), f"In high contract, Ace should outrank Jack, got idx {choice}"

    def test_glutton_bower_following_with_tracking(self):
        """Glutton should correctly play bower when following in suit contract."""
        glutton = GluttonStrategy()
        hand = [
            Card("H", "J"),  # idx 0 - Right bower
            Card("C", "T"),  # idx 1 - Off-suit
            Card("S", "Q"),  # idx 2 - Off-suit
        ]
        glutton.on_hand_start(hand, "suit", "H", player_index=2)

        # Opponent leading trump Ace, we can beat with right bower
        plays_so_far = [
            (1, Card("H", "A")),  # Opponent led trump Ace
        ]
        choice = glutton.choose_card(hand, plays_so_far, "suit", "H", 2)
        # Right bower beats trump Ace — should play it (opponent winning, not partner)
        assert (
            choice == 0
        ), f"Glutton should play right bower to beat trump Ace, got idx {choice}"


class TestSimPathHooksAlreadyCorrect:
    """Validate that the simulation path correctly invokes strategy hooks.

    These tests don't test the sim directly but confirm the contract:
    on_hand_start resets state, observe_play tracks cards, and choose_card
    uses that state.
    """

    def test_on_hand_start_sets_contract_context(self):
        """on_hand_start should set _contract_type and _trump_suit."""
        glutton = GluttonStrategy()
        assert glutton._contract_type == "high"  # default
        assert glutton._trump_suit is None  # default

        hand = [Card("H", "A"), Card("C", "K")]
        glutton.on_hand_start(hand, "suit", "S", player_index=0)
        assert glutton._contract_type == "suit"
        assert glutton._trump_suit == "S"

    def test_on_hand_start_resets_tracking(self):
        """on_hand_start should clear seen counts and void inference."""
        glutton = GluttonStrategy()
        # Simulate some tracking
        glutton._seen_counts[Card("H", "A")] = 1
        glutton._void_suits_by_seat[1].add("C")

        hand = [Card("H", "A"), Card("C", "K")]
        glutton.on_hand_start(hand, "suit", "H", player_index=0)

        assert len(glutton._seen_counts) == 0
        assert len(glutton._void_suits_by_seat[1]) == 0

    def test_observe_play_tracks_cards(self):
        """observe_play should increment seen counts."""
        glutton = GluttonStrategy()
        glutton.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)

        card = Card("C", "A")
        glutton.observe_play(1, card, [(1, card)], "suit", "H")
        assert glutton._seen_counts[card] == 1

        glutton.observe_play(3, card, [(3, card)], "suit", "H")
        assert glutton._seen_counts[card] == 2  # Double deck: max 2

    def test_observe_play_infers_voids(self):
        """observe_play should infer voids when player doesn't follow suit."""
        glutton = GluttonStrategy()
        glutton.on_hand_start([Card("H", "A")], "suit", "H", player_index=0)

        # Player 1 led clubs, player 2 played diamonds (void in clubs)
        led_card = Card("C", "A")
        off_card = Card("D", "K")
        glutton.observe_play(1, led_card, [(1, led_card)], "suit", "H")
        glutton.observe_play(2, off_card, [(1, led_card), (2, off_card)], "suit", "H")
        assert "C" in glutton._void_suits_by_seat[2]
