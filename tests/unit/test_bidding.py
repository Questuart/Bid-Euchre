"""
Unit tests for bidding policy interface and baseline bidders.
"""

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    BidAction,
    BiddingObservation,
    StrictRaiserBidder,
)


class TestBidAction:
    """Test BidAction dataclass and validation."""

    def test_pass_action(self):
        """Test creating a pass action."""
        action = BidAction.pass_bid()
        assert action.n == 0
        assert action.contract is None
        assert action.trump_suit is None
        assert action.is_pass()

    def test_bid_action_valid(self):
        """Test creating valid bid actions."""
        # Suit contracts
        action = BidAction.bid(3, "S")
        assert action.n == 3
        assert action.contract == "S"
        assert action.trump_suit is None
        assert not action.is_pass()

        action = BidAction.bid(5, "C")
        assert action.n == 5
        assert action.contract == "C"

        # High/Low contracts
        action = BidAction.bid(7, "HIGH")
        assert action.n == 7
        assert action.contract == "HIGH"

        action = BidAction.bid(8, "LOW")
        assert action.n == 8
        assert action.contract == "LOW"

    def test_bid_action_invalid_n(self):
        """Test invalid bid amounts."""
        with pytest.raises(ValueError, match="Bid amount n must be 0-10"):
            BidAction(n=-1, contract="S")

        with pytest.raises(ValueError, match="Bid amount n must be 0-10"):
            BidAction(n=11, contract="S")

    def test_bid_action_invalid_contract(self):
        """Test invalid contract types."""
        with pytest.raises(ValueError, match="Contract must be one of"):
            BidAction.bid(3, "invalid")

        with pytest.raises(ValueError, match="Contract must be one of"):
            BidAction.bid(3, "suit")  # Old format not allowed

    def test_pass_with_contract_invalid(self):
        """Test that pass cannot have contract."""
        with pytest.raises(ValueError, match="Pass.*must have contract=None"):
            BidAction(n=0, contract="S")

    def test_bid_without_contract_invalid(self):
        """Test that bid must have contract."""
        with pytest.raises(ValueError, match="Bid.*must specify contract"):
            BidAction.bid(3, None)

    def test_trump_suit_not_allowed(self):
        """Test that trump_suit is not used in v1."""
        with pytest.raises(ValueError, match="trump_suit must be None"):
            BidAction(n=3, contract="S", trump_suit="S")

    def test_to_contract_tuple(self):
        """Test conversion to legacy contract format."""
        # Pass
        action = BidAction.pass_bid()
        assert action.to_contract_tuple() == (None, None)

        # Suit contracts
        action = BidAction.bid(3, "S")
        assert action.to_contract_tuple() == ("suit", "S")

        action = BidAction.bid(4, "C")
        assert action.to_contract_tuple() == ("suit", "C")

        # High/Low
        action = BidAction.bid(5, "HIGH")
        assert action.to_contract_tuple() == ("high", None)

        action = BidAction.bid(6, "LOW")
        assert action.to_contract_tuple() == ("low", None)


class TestBiddingObservation:
    """Test BiddingObservation dataclass."""

    def test_observation_creation(self):
        """Test creating a bidding observation."""
        hand = [Card("S", "A"), Card("H", "K")]
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=2
        )

        assert obs.hand == hand
        assert obs.seat == 0
        assert obs.dealer_seat == 3
        assert obs.current_high_bid == 2
        assert obs.allowed_contracts == ("C", "D", "H", "S", "HIGH", "LOW")


class TestAlwaysPassBidder:
    """Test AlwaysPassBidder."""

    def test_always_passes(self):
        """Test that AlwaysPassBidder always passes."""
        bidder = AlwaysPassBidder()
        hand = [Card("S", "A"), Card("H", "K")]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()

        # Test with existing high bid
        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=5
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()


class TestStrictRaiserBidder:
    """Test StrictRaiserBidder."""

    def test_initial_bid(self):
        """Test bidding 3 when no high bid exists."""
        bidder = StrictRaiserBidder()
        hand = [Card("S", "A"), Card("H", "K")]

        obs = BiddingObservation(
            hand=hand,
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        assert action.n == 3
        assert action.contract == "S"
        assert not action.is_pass()

    def test_raise_bid(self):
        """Test raising existing bids."""
        bidder = StrictRaiserBidder()

        # Raise from 3 to 4
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=3
        )

        action = bidder.choose_bid(obs)
        assert action.n == 4
        assert action.contract == "S"

        # Raise from 8 to 9
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=8
        )

        action = bidder.choose_bid(obs)
        assert action.n == 9
        assert action.contract == "S"

    def test_max_bid_pass(self):
        """Test passing when at maximum bid."""
        bidder = StrictRaiserBidder()

        # Bid 10 when current is 9
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=9
        )

        action = bidder.choose_bid(obs)
        assert action.n == 10
        assert action.contract == "S"
        assert not action.is_pass()

        # Pass when current is 10 (can't bid higher)
        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=10
        )

        action = bidder.choose_bid(obs)
        assert action.is_pass()

    def test_contract_tuple_conversion(self):
        """Test that bids convert to correct contract tuples."""
        bidder = StrictRaiserBidder()

        obs = BiddingObservation(
            hand=[],
            seat=0,
            dealer_seat=3,
            current_high_bid=0
        )

        action = bidder.choose_bid(obs)
        contract_type, trump_suit = action.to_contract_tuple()
        assert contract_type == "suit"
        assert trump_suit == "S"