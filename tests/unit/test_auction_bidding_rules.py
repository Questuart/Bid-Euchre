"""
Unit tests for auction bidding rules correctness (v1 + v2 moon/loner).

These tests lock the v1 auction bidding behavior:
- One round, starting left of dealer (sequential bidding in LOD order)
- Strict-increasing bids (<= current high => pass/ignored)
- Winner is highest accepted bid (unique)
- All pass => redeal
- Contract choices include suit + HIGH + LOW

And v2 moon/loner extensions:
- Moon and loner BidActions
- Overcall hierarchy: regular < moon < loner
- Dealer takeover for moon/loner
- enumerate_legal_actions with moon/loner support
"""

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
    enumerate_legal_actions,
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
            _,
            _,
            _,
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
            _,
            _,
            _,
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
            _,
            _,
            _,
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
            _,
            _,
            _,
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
                _,
                _,
                _,
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
            _,
            _,
            _,
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


class TestBidActionMoonLoner:
    """Test BidAction construction and validation for moon/loner bid types."""

    def test_moon_bid_creation(self):
        """Moon bids can be created via classmethod."""
        action = BidAction.moon("S")
        assert action.n == 10
        assert action.contract == "S"
        assert action.bid_type == "moon"
        assert not action.is_pass()

    def test_loner_bid_creation(self):
        """Loner bids can be created via classmethod."""
        action = BidAction.loner("HIGH")
        assert action.n == 10
        assert action.contract == "HIGH"
        assert action.bid_type == "loner"
        assert not action.is_pass()

    def test_moon_all_contracts(self):
        """Moon bids work for all contract types (suit + HIGH + LOW)."""
        for contract in ["C", "D", "H", "S", "HIGH", "LOW"]:
            action = BidAction.moon(contract)
            assert action.n == 10
            assert action.contract == contract
            assert action.bid_type == "moon"

    def test_loner_all_contracts(self):
        """Loner bids work for all contract types."""
        for contract in ["C", "D", "H", "S", "HIGH", "LOW"]:
            action = BidAction.loner(contract)
            assert action.n == 10
            assert action.contract == contract
            assert action.bid_type == "loner"

    def test_moon_must_be_level_10(self):
        """Moon bids must be level 10."""
        with pytest.raises(ValueError, match="moon bids must be level 10"):
            BidAction(n=5, contract="S", bid_type="moon")

    def test_loner_must_be_level_10(self):
        """Loner bids must be level 10."""
        with pytest.raises(ValueError, match="loner bids must be level 10"):
            BidAction(n=8, contract="H", bid_type="loner")

    def test_pass_must_be_regular(self):
        """Pass bids cannot have moon/loner type."""
        with pytest.raises(ValueError, match="Pass.*must have bid_type='regular'"):
            BidAction(n=0, contract=None, bid_type="moon")

    def test_invalid_bid_type(self):
        """Invalid bid_type raises ValueError."""
        with pytest.raises(ValueError, match="bid_type must be"):
            BidAction(n=10, contract="S", bid_type="invalid")

    def test_regular_bid_backward_compat(self):
        """Regular bids default to bid_type='regular' for backward compatibility."""
        action = BidAction.bid(5, "S")
        assert action.bid_type == "regular"
        action2 = BidAction.pass_bid()
        assert action2.bid_type == "regular"

    def test_moon_to_contract_tuple(self):
        """Moon bids convert to contract tuples correctly."""
        assert BidAction.moon("S").to_contract_tuple() == ("suit", "S")
        assert BidAction.moon("HIGH").to_contract_tuple() == ("high", None)
        assert BidAction.moon("LOW").to_contract_tuple() == ("low", None)

    def test_loner_to_contract_tuple(self):
        """Loner bids convert to contract tuples correctly."""
        assert BidAction.loner("H").to_contract_tuple() == ("suit", "H")
        assert BidAction.loner("HIGH").to_contract_tuple() == ("high", None)

    def test_moon_loner_frozen(self):
        """Moon and loner BidActions are frozen dataclasses."""
        moon = BidAction.moon("S")
        with pytest.raises(AttributeError):
            moon.n = 5  # type: ignore[misc]
        loner = BidAction.loner("S")
        with pytest.raises(AttributeError):
            loner.bid_type = "regular"  # type: ignore[misc]


class TestOvercallHierarchy:
    """Test the overcall hierarchy: regular < moon < loner."""

    def test_regular_overcalls_lower_regular(self):
        """A regular bid overcalls a lower regular bid."""
        bid5 = BidAction.bid(5, "S")
        bid6 = BidAction.bid(6, "H")
        assert bid6.overcalls(bid5)
        assert not bid5.overcalls(bid6)

    def test_regular_does_not_overcall_equal(self):
        """A regular bid does not overcall an equal regular bid."""
        bid5a = BidAction.bid(5, "S")
        bid5b = BidAction.bid(5, "H")
        assert not bid5a.overcalls(bid5b)
        assert not bid5b.overcalls(bid5a)

    def test_moon_overcalls_any_regular(self):
        """Moon overcalls any regular bid, including regular 10."""
        regular10 = BidAction.bid(10, "S")
        moon = BidAction.moon("S")
        assert moon.overcalls(regular10)
        assert not regular10.overcalls(moon)

    def test_moon_overcalls_lower_regular(self):
        """Moon overcalls lower regular bids."""
        regular5 = BidAction.bid(5, "S")
        moon = BidAction.moon("H")
        assert moon.overcalls(regular5)

    def test_loner_overcalls_moon(self):
        """Loner overcalls moon."""
        moon = BidAction.moon("S")
        loner = BidAction.loner("H")
        assert loner.overcalls(moon)
        assert not moon.overcalls(loner)

    def test_loner_overcalls_any_regular(self):
        """Loner overcalls any regular bid."""
        regular10 = BidAction.bid(10, "S")
        loner = BidAction.loner("S")
        assert loner.overcalls(regular10)

    def test_moon_does_not_overcall_moon(self):
        """Moon does not overcall another moon (same rank)."""
        moon_s = BidAction.moon("S")
        moon_h = BidAction.moon("H")
        assert not moon_s.overcalls(moon_h)
        assert not moon_h.overcalls(moon_s)

    def test_loner_does_not_overcall_loner(self):
        """Loner does not overcall another loner (same rank)."""
        loner_s = BidAction.loner("S")
        loner_h = BidAction.loner("H")
        assert not loner_s.overcalls(loner_h)

    def test_pass_never_overcalls(self):
        """Pass never overcalls anything."""
        pass_bid = BidAction.pass_bid()
        assert not pass_bid.overcalls(BidAction.bid(1, "S"))
        assert not pass_bid.overcalls(BidAction.moon("S"))
        assert not pass_bid.overcalls(BidAction.loner("S"))
        assert not pass_bid.overcalls(BidAction.pass_bid())

    def test_any_bid_overcalls_pass(self):
        """Any bid overcalls a pass."""
        pass_bid = BidAction.pass_bid()
        assert BidAction.bid(1, "S").overcalls(pass_bid)
        assert BidAction.moon("S").overcalls(pass_bid)
        assert BidAction.loner("S").overcalls(pass_bid)

    def test_bid_rank_ordering(self):
        """bid_rank() returns correct ordering for the full hierarchy."""
        pass_bid = BidAction.pass_bid()
        regular1 = BidAction.bid(1, "S")
        regular5 = BidAction.bid(5, "S")
        regular10 = BidAction.bid(10, "S")
        moon = BidAction.moon("S")
        loner = BidAction.loner("S")

        assert pass_bid.bid_rank() < regular1.bid_rank()
        assert regular1.bid_rank() < regular5.bid_rank()
        assert regular5.bid_rank() < regular10.bid_rank()
        assert regular10.bid_rank() < moon.bid_rank()
        assert moon.bid_rank() < loner.bid_rank()

    def test_regular_cannot_overcall_moon(self):
        """A regular bid (even level 10) cannot overcall moon."""
        regular10 = BidAction.bid(10, "S")
        moon = BidAction.moon("S")
        assert not regular10.overcalls(moon)


class TestEnumerateLegalActionsWithMoonLoner:
    """Test enumerate_legal_actions with include_moon_loner=True."""

    def _make_obs(self, current_high_bid=0, seat=0, dealer_seat=3):
        """Helper to create a minimal BiddingObservation."""
        hand = [Card("S", "A")] * 10  # Dummy hand
        return BiddingObservation(
            hand=hand,
            seat=seat,
            dealer_seat=dealer_seat,
            current_high_bid=current_high_bid,
        )

    def test_without_flag_no_moon_loner(self):
        """Without include_moon_loner, no moon/loner actions are returned."""
        obs = self._make_obs(current_high_bid=0)
        actions = enumerate_legal_actions(obs)
        for a in actions:
            assert a.bid_type == "regular" or a.is_pass()

    def test_with_flag_includes_moon_loner(self):
        """With include_moon_loner=True, moon and loner actions are included."""
        obs = self._make_obs(current_high_bid=0)
        actions = enumerate_legal_actions(obs, include_moon_loner=True)
        moon_actions = [a for a in actions if a.bid_type == "moon"]
        loner_actions = [a for a in actions if a.bid_type == "loner"]
        assert len(moon_actions) == 6  # 4 suits + HIGH + LOW
        assert len(loner_actions) == 6

    def test_moon_blocks_regular_bids(self):
        """When current high bid is a moon, no regular bids are legal."""
        obs = self._make_obs(current_high_bid=10)
        actions = enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type="moon",
        )
        regular_bids = [
            a for a in actions if a.bid_type == "regular" and not a.is_pass()
        ]
        assert len(regular_bids) == 0

    def test_moon_allows_loner(self):
        """When current high bid is a moon, loner overcalls are available."""
        obs = self._make_obs(current_high_bid=10)
        actions = enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type="moon",
        )
        loner_actions = [a for a in actions if a.bid_type == "loner"]
        assert len(loner_actions) == 6

    def test_moon_no_moon_for_non_dealer(self):
        """Non-dealer cannot match a moon (no moon actions when current is moon)."""
        obs = self._make_obs(current_high_bid=10, seat=0, dealer_seat=3)
        actions = enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type="moon",
            is_dealer=False,
        )
        moon_actions = [a for a in actions if a.bid_type == "moon"]
        assert len(moon_actions) == 0

    def test_moon_dealer_can_take_away(self):
        """Dealer can match a moon bid (takeover)."""
        obs = self._make_obs(current_high_bid=10, seat=3, dealer_seat=3)
        actions = enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type="moon",
            is_dealer=True,
        )
        moon_actions = [a for a in actions if a.bid_type == "moon"]
        assert len(moon_actions) == 6

    def test_loner_blocks_all_except_dealer_loner(self):
        """When current is loner, only dealer can match with another loner."""
        obs = self._make_obs(current_high_bid=10, seat=0, dealer_seat=3)
        actions = enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type="loner",
            is_dealer=False,
        )
        # Only pass should be available for non-dealer
        non_pass = [a for a in actions if not a.is_pass()]
        assert len(non_pass) == 0

    def test_loner_dealer_can_take_away(self):
        """Dealer can match a loner bid."""
        obs = self._make_obs(current_high_bid=10, seat=3, dealer_seat=3)
        actions = enumerate_legal_actions(
            obs,
            include_moon_loner=True,
            current_bid_type="loner",
            is_dealer=True,
        )
        loner_actions = [a for a in actions if a.bid_type == "loner"]
        assert len(loner_actions) == 6

    def test_backward_compat_default_args(self):
        """Default arguments produce same results as before (no moon/loner)."""
        obs = self._make_obs(current_high_bid=5)
        actions_default = enumerate_legal_actions(obs)
        actions_explicit = enumerate_legal_actions(obs, include_moon_loner=False)
        assert actions_default == actions_explicit

    def test_pass_always_available(self):
        """Pass is always available regardless of moon/loner state."""
        for bid_type in ["regular", "moon", "loner"]:
            obs = self._make_obs(current_high_bid=10)
            actions = enumerate_legal_actions(
                obs,
                include_moon_loner=True,
                current_bid_type=bid_type,
            )
            assert BidAction.pass_bid() in actions


class TestAuctionMoonLonerIntegration:
    """Integration tests for moon/loner in the auction simulation."""

    def _fixed_hands(self):
        """Return fixed hands for deterministic auction tests."""
        hand = [
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
        return [hand.copy() for _ in range(4)]

    def test_moon_wins_over_regular_bid(self):
        """A moon bid wins over a regular bid 10."""

        class MoonBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.bid(10, "S")  # Regular 10
                elif obs.seat == 1:
                    return BidAction.moon("H")  # Moon overcalls
                return BidAction.pass_bid()

        policy = MoonBidder()
        hands = self._fixed_hands()

        (
            _,
            _,
            _,
            _,
            leader,
            _,
            bid,
            _,
            bidder_pos,
            contract,
            trump,
            transcript,
            _,
            _,
            _,
            _,
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,  # dealer=2, LOD order: [3, 0, 1, 2]
        )

        assert bidder_pos == 1, f"Moon bidder (seat 1) should win, got {bidder_pos}"
        assert bid == 10
        assert contract == "suit"
        assert trump == "H"

    def test_loner_wins_over_moon(self):
        """A loner bid wins over a moon bid."""

        class LonerBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("S")  # Moon
                elif obs.seat == 1:
                    return BidAction.loner("D")  # Loner overcalls moon
                return BidAction.pass_bid()

        policy = LonerBidder()
        hands = self._fixed_hands()

        (
            _,
            _,
            _,
            _,
            leader,
            _,
            bid,
            _,
            bidder_pos,
            contract,
            trump,
            _,
            _,
            _,
            _,
            _,
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        assert bidder_pos == 1, f"Loner bidder (seat 1) should win, got {bidder_pos}"
        assert contract == "suit"
        assert trump == "D"

    def test_regular_cannot_overcall_moon(self):
        """A regular bid after a moon is treated as pass."""

        class RegularAfterMoon(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("S")
                elif obs.seat == 1:
                    return BidAction.bid(10, "H")  # Regular 10 cannot beat moon
                return BidAction.pass_bid()

        policy = RegularAfterMoon()
        hands = self._fixed_hands()

        (
            _,
            _,
            _,
            _,
            _,
            _,
            _,
            _,
            bidder_pos,
            contract,
            trump,
            transcript,
            _,
            _,
            _,
            _,
        ) = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        # Moon bidder (seat 0) should still be the winner
        assert bidder_pos == 0, f"Moon bidder (seat 0) should win, got {bidder_pos}"
        assert trump == "S"

        # Verify transcript shows seat 1 as PASS
        seat_1_entry = [e for e in transcript if e["seat"] == 1][0]
        assert seat_1_entry["action"] == "PASS"

    def test_dealer_takeover_moon(self):
        """Dealer can take away a moon bid by bidding moon."""

        class DealerTakeoverMoon(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("S")  # Non-dealer bids moon
                elif obs.seat == 2:
                    return BidAction.moon("H")  # Dealer takes it away
                return BidAction.pass_bid()

        policy = DealerTakeoverMoon()
        hands = self._fixed_hands()

        # Dealer is seat 2, LOD order: [3, 0, 1, 2]
        *_, bidder_pos, contract, trump, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,  # dealer = (3-1)%4 = 2
        )

        # Dealer (seat 2) should take away the moon
        assert bidder_pos == 2, f"Dealer (seat 2) should take moon, got {bidder_pos}"
        assert trump == "H"

    def test_dealer_takeover_loner(self):
        """Dealer can take away a loner bid by bidding loner."""

        class DealerTakeoverLoner(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.loner("S")  # Non-dealer bids loner
                elif obs.seat == 2:
                    return BidAction.loner("D")  # Dealer takes it away
                return BidAction.pass_bid()

        policy = DealerTakeoverLoner()
        hands = self._fixed_hands()

        *_, bidder_pos, contract, trump, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        assert bidder_pos == 2, f"Dealer (seat 2) should take loner, got {bidder_pos}"
        assert trump == "D"

    def test_non_dealer_cannot_takeover_moon(self):
        """Non-dealer cannot match a moon bid (treated as pass)."""

        class NonDealerMoonMatch(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("S")  # First moon
                elif obs.seat == 1:
                    return BidAction.moon("H")  # Non-dealer tries to match
                return BidAction.pass_bid()

        policy = NonDealerMoonMatch()
        hands = self._fixed_hands()

        *_, bidder_pos, _, trump, transcript, _, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        # Seat 0 should still win (seat 1's moon treated as pass)
        assert bidder_pos == 0, f"Seat 0 should win, got {bidder_pos}"
        assert trump == "S"

        seat_1_entry = [e for e in transcript if e["seat"] == 1][0]
        assert seat_1_entry["action"] == "PASS"

    def test_moon_with_per_seat_policies(self):
        """Moon/loner work with per-seat bidding policies too."""

        class MoonBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                return BidAction.moon("S")

        class PassBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                return BidAction.pass_bid()

        policies = [MoonBidder(), PassBidder(), PassBidder(), PassBidder()]
        hands = self._fixed_hands()

        *_, bid, _, bidder_pos, contract, trump, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policies=policies,
            hands=hands,
            initial_leader=3,
        )

        assert bidder_pos == 0
        assert bid == 10
        assert trump == "S"

    def test_transcript_records_bid_type(self):
        """Auction transcript records bid_type for moon/loner bids."""

        class MoonBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("S")
                return BidAction.pass_bid()

        policy = MoonBidder()
        hands = self._fixed_hands()

        *_, transcript, _bid_type, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        # Find the BID entry in the transcript
        bid_entries = [e for e in transcript if e["action"] == "BID"]
        assert len(bid_entries) == 1
        assert bid_entries[0]["bid_type"] == "moon"

    def test_moon_high_contract(self):
        """Moon with HIGH contract works correctly."""

        class MoonHighBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("HIGH")
                return BidAction.pass_bid()

        policy = MoonHighBidder()
        hands = self._fixed_hands()

        *_, bid, _, bidder_pos, contract, trump, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        assert bidder_pos == 0
        assert contract == "high"
        assert trump is None

    def test_moon_low_contract(self):
        """Moon with LOW contract works correctly."""

        class MoonLowBidder(BiddingPolicy):
            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                if obs.seat == 0:
                    return BidAction.moon("LOW")
                return BidAction.pass_bid()

        policy = MoonLowBidder()
        hands = self._fixed_hands()

        *_, bid, _, bidder_pos, contract, trump, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            hands=hands,
            initial_leader=3,
        )

        assert bidder_pos == 0
        assert contract == "low"
        assert trump is None
