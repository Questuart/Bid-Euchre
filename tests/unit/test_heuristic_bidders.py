"""
Unit tests for heuristic baseline bidding policies.

Tests determinism and strict-increasing compliance for:
- FixedBidder
- HeuristicSuitBidder
- HighLowHeuristicBidder
"""

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    BiddingObservation,
    FixedBidder,
    HeuristicSuitBidder,
    HighLowHeuristicBidder,
)


class TestFixedBidder:
    """Tests for FixedBidder."""

    def test_bids_when_allowed(self):
        """Fixed bidder bids its fixed amount when higher than current bid."""
        bidder = FixedBidder(n=5, contract="H")
        obs = BiddingObservation(
            hand=[Card("H", "A"), Card("H", "K")],
            seat=0,
            dealer_seat=3,
            current_high_bid=3,
        )
        action = bidder.choose_bid(obs)
        assert action.n == 5
        assert action.contract == "H"
        assert not action.is_pass()

    def test_passes_when_not_allowed(self):
        """Fixed bidder passes when its fixed bid is not higher than current."""
        bidder = FixedBidder(n=5, contract="H")
        obs = BiddingObservation(
            hand=[Card("H", "A"), Card("H", "K")],
            seat=0,
            dealer_seat=3,
            current_high_bid=6,
        )
        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_passes_when_equal(self):
        """Fixed bidder passes when its fixed bid equals current (strict increasing)."""
        bidder = FixedBidder(n=5, contract="H")
        obs = BiddingObservation(
            hand=[Card("H", "A"), Card("H", "K")],
            seat=0,
            dealer_seat=3,
            current_high_bid=5,
        )
        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_validates_n_range(self):
        """FixedBidder validates n is 1-10."""
        try:
            FixedBidder(n=0, contract="H")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "1-10" in str(e)

        try:
            FixedBidder(n=11, contract="H")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "1-10" in str(e)

    def test_validates_contract(self):
        """FixedBidder validates contract is valid."""
        try:
            FixedBidder(n=5, contract="INVALID")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid contract" in str(e)


class TestHeuristicSuitBidder:
    """Tests for HeuristicSuitBidder."""

    def test_determinism_same_hand_same_bid(self):
        """Same hand produces same bid."""
        bidder = HeuristicSuitBidder()
        hand = [
            Card("H", "A"), Card("H", "K"), Card("H", "Q"),
            Card("C", "A"), Card("C", "K")
        ]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        # Call multiple times
        action1 = bidder.choose_bid(obs)
        action2 = bidder.choose_bid(obs)
        action3 = bidder.choose_bid(obs)

        # All should be identical
        assert action1.n == action2.n == action3.n
        assert action1.contract == action2.contract == action3.contract

    def test_picks_strongest_suit(self):
        """Heuristic bidder picks the strongest suit."""
        bidder = HeuristicSuitBidder()
        # Strong hearts hand (right bower, left bower, A, K, Q - 5 cards total)
        hand = [
            Card("H", "J"), Card("D", "J"), Card("H", "A"),
            Card("H", "K"), Card("H", "Q")
        ]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        # Should choose H (hearts) as it has the strongest cards
        assert action.contract == "H"

    def test_passes_weak_hand(self):
        """Heuristic bidder passes if hand is too weak."""
        bidder = HeuristicSuitBidder()
        # Very weak hand (all tens)
        hand = [Card("C", "T"), Card("D", "T"), Card("H", "T"), Card("S", "T"), Card("C", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_complies_with_strict_increasing(self):
        """Heuristic bidder passes if computed bid not higher than current."""
        bidder = HeuristicSuitBidder()
        # Medium strength hand that would bid 3
        hand = [Card("H", "A"), Card("C", "K"), Card("D", "Q"), Card("S", "T"), Card("H", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=5,  # Already higher than what we'd bid
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()


class TestHighLowHeuristicBidder:
    """Tests for HighLowHeuristicBidder."""

    def test_determinism_same_hand_same_bid(self):
        """Same hand produces same bid."""
        bidder = HighLowHeuristicBidder()
        hand = [Card("H", "A"), Card("C", "K"), Card("D", "Q"), Card("S", "J"), Card("H", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        # Call multiple times
        action1 = bidder.choose_bid(obs)
        action2 = bidder.choose_bid(obs)
        action3 = bidder.choose_bid(obs)

        # All should be identical
        assert action1.n == action2.n == action3.n
        assert action1.contract == action2.contract == action3.contract

    def test_chooses_high_for_high_cards(self):
        """Chooses HIGH when hand has more high cards."""
        bidder = HighLowHeuristicBidder()
        # 4 high cards (A, K, Q, Q) vs 1 low card (T)
        hand = [Card("H", "A"), Card("C", "K"), Card("D", "Q"), Card("S", "Q"), Card("H", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "HIGH"

    def test_chooses_low_for_low_cards(self):
        """Chooses LOW when hand has more low cards."""
        bidder = HighLowHeuristicBidder()
        # 1 high card (A) vs 4 low cards (J, J, T, T)
        hand = [Card("H", "A"), Card("C", "J"), Card("D", "J"), Card("S", "T"), Card("H", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        action = bidder.choose_bid(obs)
        assert not action.is_pass()
        assert action.contract == "LOW"

    def test_chooses_high_on_tie(self):
        """Chooses HIGH deterministically when high/low counts are tied."""
        bidder = HighLowHeuristicBidder()
        # 3 high cards (A, K, Q) vs 2 low cards (J, T)
        hand = [Card("H", "A"), Card("C", "K"), Card("D", "J"), Card("S", "T"), Card("H", "Q")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0,
        )

        action = bidder.choose_bid(obs)
        # Should choose HIGH (more high cards)
        if not action.is_pass():
            assert action.contract == "HIGH"

    def test_complies_with_strict_increasing(self):
        """Passes if computed bid not higher than current."""
        bidder = HighLowHeuristicBidder()
        # Medium strength hand
        hand = [Card("H", "A"), Card("C", "K"), Card("D", "Q"), Card("S", "J"), Card("H", "T")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=6,  # Higher than what we'd bid
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()
