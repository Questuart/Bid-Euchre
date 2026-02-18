"""
Unit tests for auction bidding rules correctness (v1).

These tests lock the v1 auction bidding behavior:
- One round, starting left of dealer (sequential bidding in LOD order)
- Strict-increasing bids (<= current high => pass/ignored)
- Winner is highest accepted bid (unique)
- All pass => redeal
- Contract choices include suit + HIGH + LOW
"""

from bid_euchre.core.cards import Card
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
)


class TestAuctionBiddingRules:
    """Test suite for auction bidding rules (v1)."""

    def test_all_pass_results_in_redeal(self):
        """All players passing should result in redeal (leader=-1, bid=0)."""
        # Use AlwaysPassBidder as the bidding policy (applied to all players)
        bidding_policy = AlwaysPassBidder()

        # Play hand with auction mode (contract_type=None)
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
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=bidding_policy,
        )

        # Verify redeal conditions
        assert leader == -1, "Leader should be -1 for redeal"
        assert bid == 0, "Bid should be 0 for redeal"
        assert bidder_pos is None, "Bidder position should be None for redeal"
        assert t0 == 0, "Team 0 tricks should be 0 for redeal"
        assert t1 == 0, "Team 1 tricks should be 0 for redeal"

    def test_strict_increasing_bids_ignored(self):
        """Bids <= current high bid should be treated as pass/ignored."""

        class SeatBasedBidder(BiddingPolicy):
            """Bids differently based on seat."""

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.bid(8, "S")  # High bid first
                elif obs.seat == 1:
                    return BidAction.bid(3, "S")  # Underbid (will be ignored)
                else:
                    return BidAction.pass_bid()  # Others pass

        bidding_policy = SeatBasedBidder()

        # Use a fixed hand and dealer to ensure determinism
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

        hands = [
            fixed_hand.copy() for _ in range(4)
        ]  # Same hand for all for simplicity

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
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=bidding_policy,
            hands=hands,
            initial_leader=3,  # Make seat 3 dealer so bidding order is 0,1,2,3
        )

        # Seat 0 should win with bid 8 (seat 1's bid 3 was ignored as <= 8)
        assert leader == 0, f"Expected leader to be 0 (high bidder), got {leader}"
        assert bid == 8, f"Expected bid to be 8, got {bid}"
        assert (
            final_contract == "suit"
        ), f"Expected contract 'suit', got {final_contract}"
        assert final_trump == "S", f"Expected trump 'S', got {final_trump}"

    def test_highest_valid_bid_wins(self):
        """The player with the highest valid bid should win the auction."""

        class SeatBasedBidder(BiddingPolicy):
            """Bids differently based on seat."""

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.bid(5, "HIGH")
                elif obs.seat == 1:
                    return BidAction.bid(7, "LOW")  # Highest bid
                elif obs.seat == 2:
                    return BidAction.bid(3, "S")
                elif obs.seat == 3:
                    return BidAction.bid(6, "C")
                return BidAction.pass_bid()

        bidding_policy = SeatBasedBidder()

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
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=bidding_policy,
            hands=hands,
            initial_leader=3,  # Make seat 3 dealer so bidding order is 0,1,2,3
        )

        # Seat 1 should win with the highest bid (7 LOW)
        assert (
            leader == 1
        ), f"Expected leader to be 1 (highest bidder with 7), got {leader}"
        assert bid == 7, f"Expected bid to be 7, got {bid}"
        assert final_contract == "low", f"Expected contract 'low', got {final_contract}"
        assert (
            final_trump is None
        ), f"Expected trump None for LOW contract, got {final_trump}"

    def test_sequential_bidding_lod_order(self):
        """Bidding proceeds sequentially in LOD order: left of dealer first, then clockwise, dealer last."""

        class CallOrderTracker(BiddingPolicy):
            """Tracks the order in which seats are called."""

            call_order = []  # Class variable to track order of calls

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                CallOrderTracker.call_order.append(obs.seat)
                return BidAction.pass_bid()  # All pass for this test

        # Reset order tracker
        CallOrderTracker.call_order = []

        bidding_policy = CallOrderTracker()

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

        # Dealer is seat 2 (initial_leader=3 means dealer is (3-1)%4 = 2)
        # Expected LOD order: seat 3 (dealer+1), 0 (dealer+2), 1 (dealer+3), 2 (dealer)
        play_single_hand(
            contract_type=None,
            bidding_policy=bidding_policy,
            hands=hands,
            initial_leader=3,  # Dealer is seat 2
        )

        # Verify sequential LOD order: [3, 0, 1, 2]
        expected_order = [3, 0, 1, 2]
        assert (
            CallOrderTracker.call_order == expected_order
        ), f"Expected LOD order {expected_order}, got {CallOrderTracker.call_order}"

        # Verify each seat called exactly once
        assert (
            len(CallOrderTracker.call_order) == 4
        ), f"Expected 4 calls (one round), got {len(CallOrderTracker.call_order)}"

    def test_current_high_bid_progresses_sequentially(self):
        """Verify that current_high_bid visible to each bidder reflects the sequential progression."""

        class ObservationTracker(BiddingPolicy):
            """Tracks the current_high_bid each seat observes and bids according to seat."""

            observed_high_bids = {}  # seat -> current_high_bid at time of bidding

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                ObservationTracker.observed_high_bids[obs.seat] = obs.current_high_bid
                # LOD (seat 3) bids 5, next (seat 0) tries 4 (will be ignored), next (seat 1) bids 6, dealer (seat 2) passes
                if obs.seat == 3:
                    return BidAction.bid(5, "S")  # LOD bids 5
                elif obs.seat == 0:
                    return BidAction.bid(4, "S")  # Attempts 4 (<= 5, will be ignored)
                elif obs.seat == 1:
                    return BidAction.bid(6, "H")  # Bids 6 (valid)
                elif obs.seat == 2:
                    return BidAction.pass_bid()  # Dealer passes
                return BidAction.pass_bid()

        # Reset tracker
        ObservationTracker.observed_high_bids = {}

        bidding_policy = ObservationTracker()

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

        # Dealer is seat 2, LOD order: [3, 0, 1, 2]
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
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=bidding_policy,
            hands=hands,
            initial_leader=3,  # Dealer is seat 2
        )

        # Verify the winner is seat 1 (who bid 6)
        assert (
            bidder_pos == 1
        ), f"Expected winner to be seat 1 (bid 6), got {bidder_pos}"
        assert bid == 6, f"Expected winning bid to be 6, got {bid}"
        assert (
            final_contract == "suit"
        ), f"Expected contract 'suit', got {final_contract}"
        assert final_trump == "H", f"Expected trump 'H', got {final_trump}"

        # Verify current_high_bid progression:
        # - Seat 3 (LOD) should see current_high_bid = 0 (no bids yet)
        # - Seat 0 should see current_high_bid = 5 (seat 3's bid)
        # - Seat 1 should see current_high_bid = 5 (seat 0's bid was ignored)
        # - Seat 2 should see current_high_bid = 6 (seat 1's bid)
        assert (
            ObservationTracker.observed_high_bids[3] == 0
        ), f"Seat 3 (LOD) should see current_high_bid=0, got {ObservationTracker.observed_high_bids[3]}"
        assert (
            ObservationTracker.observed_high_bids[0] == 5
        ), f"Seat 0 should see current_high_bid=5 (from seat 3), got {ObservationTracker.observed_high_bids[0]}"
        assert (
            ObservationTracker.observed_high_bids[1] == 5
        ), f"Seat 1 should see current_high_bid=5 (seat 0's bid ignored), got {ObservationTracker.observed_high_bids[1]}"
        assert (
            ObservationTracker.observed_high_bids[2] == 6
        ), f"Seat 2 (dealer) should see current_high_bid=6 (from seat 1), got {ObservationTracker.observed_high_bids[2]}"

    def test_contract_types_supported(self):
        """Auction supports suit contracts (S,H,D,C) and HIGH/LOW contracts."""

        # Test each contract type wins
        test_cases = [
            ("S", "suit", "S"),
            ("H", "suit", "H"),
            ("D", "suit", "D"),
            ("C", "suit", "C"),
            ("HIGH", "high", None),
            ("LOW", "low", None),
        ]

        for contract_input, expected_contract, expected_trump in test_cases:

            class ContractBidder(BiddingPolicy):
                """Bids with a specific contract type."""

                def choose_bid(self, obs: BiddingObservation) -> BidAction:
                    if obs.seat == 0:  # Only seat 0 bids
                        return BidAction.bid(5, contract_input)
                    return BidAction.pass_bid()

            bidding_policy = ContractBidder()

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
            ) = play_single_hand(
                contract_type=None,
                bidding_policy=bidding_policy,
                hands=hands,
                initial_leader=3,  # Seat 0 is left of dealer
            )

            assert (
                leader == 0
            ), f"Expected leader 0 for contract {contract_input}, got {leader}"
            assert bid == 5, f"Expected bid 5 for contract {contract_input}, got {bid}"
            assert (
                final_contract == expected_contract
            ), f"Expected contract '{expected_contract}' for {contract_input}, got '{final_contract}'"
            assert (
                final_trump == expected_trump
            ), f"Expected trump '{expected_trump}' for {contract_input}, got '{final_trump}'"

    def test_bidder_wins_and_leads(self):
        """The auction winner must lead the first trick."""

        class SeatBasedBidder(BiddingPolicy):
            """Only seat 1 bids."""

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 1:
                    return BidAction.bid(6, "S")  # Seat 1 bids 6
                return BidAction.pass_bid()  # Others pass

        bidding_policy = SeatBasedBidder()

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
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=bidding_policy,
            hands=hands,
            initial_leader=0,  # Make seat 0 left of dealer (so seat 1 is not dealer)
        )

        # Seat 1 should win and lead
        assert leader == 1, f"Expected leader to be 1 (auction winner), got {leader}"
        assert bid == 6, f"Expected bid to be 6, got {bid}"
        assert bidder_pos == 1, f"Expected bidder position to be 1, got {bidder_pos}"
