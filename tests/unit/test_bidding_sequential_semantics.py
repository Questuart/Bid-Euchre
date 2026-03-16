"""
Unit tests for bidding sequential semantics.

These tests verify that bidding follows sequential auction in LOD order
with strict-raise legality, matching the current simulator behavior.
"""

from bid_euchre.core.cards import Card
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.bidding import (
    BidAction,
    BiddingObservation,
    BiddingPolicy,
)


class TestBiddingSequentialSemantics:
    """Test suite for sequential bidding semantics (LOD order, strict-raise legality)."""

    def test_bidding_order_lod_to_dealer(self):
        """Bidding proceeds sequentially: LOD → partner → ROD → dealer."""

        class OrderTracker(BiddingPolicy):
            """Records the order in which seats are called to bid."""

            call_order = []

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                OrderTracker.call_order.append(obs.seat)
                return BidAction.pass_bid()

        # Reset tracker
        OrderTracker.call_order = []

        policy = OrderTracker()
        fixed_hand = [
            Card("S", "A"),
            Card("H", "K"),
            Card("D", "Q"),
            Card("C", "J"),
            Card("S", "T"),
            Card("H", "A"),
            Card("D", "K"),
            Card("C", "Q"),
            Card("S", "J"),
            Card("H", "T"),
        ]
        hands = [fixed_hand.copy() for _ in range(4)]

        # Dealer is seat 2 (initial_leader=3 means dealer = (3-1)%4 = 2)
        # Expected order: LOD(3) → partner(0) → ROD(1) → dealer(2)
        play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        expected_order = [3, 0, 1, 2]  # LOD → partner → ROD → dealer
        assert (
            OrderTracker.call_order == expected_order
        ), f"Expected LOD order {expected_order}, got {OrderTracker.call_order}"

    def test_strict_raise_legality_enforced(self):
        """Bids <= current_high_bid are treated as pass (illegal bids coerced to pass)."""

        class ScriptedBidder(BiddingPolicy):
            """Bids according to a predefined script per seat."""

            def __init__(self, seat_bids):
                self.seat_bids = seat_bids  # seat -> BidAction

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                return self.seat_bids.get(obs.seat, BidAction.pass_bid())

        # Seat 0: bid 5 first (legal)
        # Seat 1: bid 3 (illegal, <= 5, should be treated as pass)
        # Seat 2: bid 7 (legal, > 5)
        # Seat 3: pass
        policy = ScriptedBidder(
            {
                0: BidAction.bid(5, "S"),  # LOD bids 5
                1: BidAction.bid(3, "H"),  # Partner tries 3 (<= 5, illegal)
                2: BidAction.bid(7, "D"),  # ROD bids 7 (> 5, legal)
                3: BidAction.pass_bid(),  # Dealer passes
            }
        )

        fixed_hand = [
            Card("S", "A"),
            Card("H", "K"),
            Card("D", "Q"),
            Card("C", "J"),
            Card("S", "T"),
            Card("H", "A"),
            Card("D", "K"),
            Card("C", "Q"),
            Card("S", "J"),
            Card("H", "T"),
        ]
        hands = [fixed_hand.copy() for _ in range(4)]

        # Dealer is seat 2 (initial_leader=3)
        (
            t0,
            t1,
            scores,
            features,
            leader,
            hands,
            bid,
            dealer_pos,
            bidder_pos,
            final_contract,
            final_trump,
            _,
            _,
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        # Seat 2 (ROD) should win with bid 7 (seat 1's bid 3 was ignored as illegal)
        assert (
            leader == 2
        ), f"Expected leader to be 2 (ROD with highest valid bid), got {leader}"
        assert bid == 7, f"Expected bid to be 7, got {bid}"
        assert (
            final_contract == "suit"
        ), f"Expected contract 'suit', got {final_contract}"
        assert final_trump == "D", f"Expected trump 'D', got {final_trump}"
