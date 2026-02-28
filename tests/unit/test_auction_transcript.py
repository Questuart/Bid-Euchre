"""
Tests for auction_transcript field on BiddingObservation.

Verifies that the auction_transcript accumulates correctly across all three
auction paths in play_single_hand, and that backward compatibility is preserved.
"""

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy import GreedyStrategy
from bid_euchre.strategy.bidding import (
    BidAction,
    BiddingObservation,
    BiddingPolicy,
)


class TranscriptCapturingPolicy(BiddingPolicy):
    """BiddingPolicy that captures observations for inspection."""

    def __init__(self, name: str = "transcript_capturer"):
        super().__init__(name)
        self.observations: list[BiddingObservation] = []

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        self.observations.append(obs)
        return BidAction.pass_bid()


class TranscriptCapturingBidder(BiddingPolicy):
    """BiddingPolicy that captures observations and bids once (seat 0 only)."""

    def __init__(self, seat_to_bid: int, name: str = "capturing_bidder"):
        super().__init__(name)
        self.seat_to_bid = seat_to_bid
        self.observations: list[BiddingObservation] = []

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        self.observations.append(obs)
        if obs.seat == self.seat_to_bid:
            return BidAction.bid(3, "S")
        return BidAction.pass_bid()


class TestAuctionTranscriptBackwardCompat:
    """Backward compatibility for auction_transcript."""

    def test_default_empty_tuple(self):
        """Default auction_transcript is empty tuple."""
        obs = BiddingObservation(hand=[], seat=0, dealer_seat=3, current_high_bid=0)
        assert obs.auction_transcript == ()

    def test_explicit_transcript(self):
        """Can supply explicit auction_transcript."""
        entry = {"seat": 1, "action": "BID", "tricks_bid": 3}
        obs = BiddingObservation(
            hand=[],
            seat=2,
            dealer_seat=0,
            current_high_bid=3,
            auction_transcript=(entry,),
        )
        assert obs.auction_transcript == (entry,)
        assert len(obs.auction_transcript) == 1

    def test_frozen(self):
        """auction_transcript field is immutable (frozen dataclass)."""
        obs = BiddingObservation(hand=[], seat=0, dealer_seat=3, current_high_bid=0)
        try:
            obs.auction_transcript = ({"seat": 0, "action": "PASS"},)  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass  # Expected: frozen dataclass


class TestTranscriptAccumulatesSeatBiddingPolicies:
    """Verify transcript grows across seats in seat_bidding_policies path."""

    def test_transcript_grows_each_seat(self):
        """Each successive bidder should see a longer transcript."""
        cap0 = TranscriptCapturingPolicy("cap0")
        cap1 = TranscriptCapturingPolicy("cap1")
        cap2 = TranscriptCapturingPolicy("cap2")
        cap3 = TranscriptCapturingPolicy("cap3")

        # dealer_seat is determined by initial_leader: dealer = (initial_leader - 1) % 4
        # initial_leader=0 => dealer=3, bid order: seat 0, 1, 2, 3
        play_single_hand(
            contract_type=None,
            bidding_policies=[cap0, cap1, cap2, cap3],
            initial_leader=0,
        )

        # Seat 0 bids first (after dealer=3), sees 0 prior entries
        assert len(cap0.observations) == 1
        assert len(cap0.observations[0].auction_transcript) == 0

        # Seat 1 bids second, sees 1 prior entry (seat 0's action)
        assert len(cap1.observations) == 1
        assert len(cap1.observations[0].auction_transcript) == 1
        assert cap1.observations[0].auction_transcript[0]["seat"] == 0

        # Seat 2 bids third, sees 2 prior entries
        assert len(cap2.observations) == 1
        assert len(cap2.observations[0].auction_transcript) == 2

        # Seat 3 (dealer) bids last, sees 3 prior entries
        assert len(cap3.observations) == 1
        assert len(cap3.observations[0].auction_transcript) == 3

    def test_transcript_contains_pass_actions(self):
        """Transcript entries for passes should have action=PASS."""
        cap0 = TranscriptCapturingPolicy("cap0")
        cap1 = TranscriptCapturingPolicy("cap1")
        cap2 = TranscriptCapturingPolicy("cap2")
        cap3 = TranscriptCapturingPolicy("cap3")

        play_single_hand(
            contract_type=None,
            bidding_policies=[cap0, cap1, cap2, cap3],
            initial_leader=0,
        )

        # All pass, so seat 3 should see 3 PASS entries
        for entry in cap3.observations[0].auction_transcript:
            assert entry["action"] == "PASS"
            assert entry["tricks_bid"] == 0

    def test_transcript_contains_bid_actions(self):
        """Transcript entries for bids should have action=BID."""
        # Seat 0 bids 3 of Spades; others capture and pass
        bidder = TranscriptCapturingBidder(seat_to_bid=0, name="bidder_s0")
        cap1 = TranscriptCapturingPolicy("cap1")
        cap2 = TranscriptCapturingPolicy("cap2")
        cap3 = TranscriptCapturingPolicy("cap3")

        play_single_hand(
            contract_type=None,
            bidding_policies=[bidder, cap1, cap2, cap3],
            initial_leader=0,
        )

        # Seat 1 sees seat 0's bid
        assert len(cap1.observations[0].auction_transcript) == 1
        entry = cap1.observations[0].auction_transcript[0]
        assert entry["seat"] == 0
        assert entry["action"] == "BID"
        assert entry["tricks_bid"] == 3
        assert entry["contract_type"] == "suit"
        assert entry["trump"] == "S"


class TestTranscriptAccumulatesSinglePolicy:
    """Verify transcript grows in single bidding_policy path."""

    def test_transcript_grows_single_policy(self):
        """Single policy sees growing transcript across its 4 invocations."""
        capturer = TranscriptCapturingPolicy("single")

        play_single_hand(
            contract_type=None,
            bidding_policy=capturer,
            initial_leader=0,
        )

        # Should be called 4 times (once per seat)
        assert len(capturer.observations) == 4

        # Transcript lengths should be 0, 1, 2, 3
        for i, obs in enumerate(capturer.observations):
            assert len(obs.auction_transcript) == i, (
                f"Observation {i} should have {i} transcript entries, "
                f"got {len(obs.auction_transcript)}"
            )


class TestTranscriptAccumulatesLegacyStrategy:
    """Verify transcript grows in legacy Strategy.decide_bid path."""

    def test_transcript_in_returned_tuple(self):
        """Legacy path should populate auction_transcript in return tuple."""
        strategy = GreedyStrategy()

        result = play_single_hand(
            contract_type=None,
            strategy=strategy,
            initial_leader=0,
        )

        # Index 11 is the auction_transcript in the return tuple
        transcript = result[11]
        assert transcript is not None
        assert isinstance(transcript, list)
        # Should have exactly 4 entries (one per seat in bidding order)
        assert len(transcript) == 4

    def test_legacy_transcript_entries_have_required_keys(self):
        """Each transcript entry should have seat, action, tricks_bid, contract_type, trump."""
        strategy = GreedyStrategy()

        result = play_single_hand(
            contract_type=None,
            strategy=strategy,
            initial_leader=0,
        )

        transcript = result[11]
        required_keys = {"seat", "action", "tricks_bid", "contract_type", "trump"}
        for entry in transcript:
            assert required_keys.issubset(
                entry.keys()
            ), f"Missing keys in transcript entry: {required_keys - entry.keys()}"


class TestTranscriptEntriesAreIndependentCopies:
    """Verify that mutating a dict in one observation's transcript is isolated."""

    def test_transcript_entries_are_independent_copies(self):
        """Mutating an entry in one observation's transcript must not affect others."""

        class MutatingPolicy(BiddingPolicy):
            """Policy that mutates transcript entry[0] to detect cross-copy leaks."""

            def __init__(self):
                super().__init__(name="mutator")
                self.observations: list[BiddingObservation] = []

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                self.observations.append(obs)
                # Mutate the first entry if it exists
                if obs.auction_transcript:
                    obs.auction_transcript[0]["seat"] = 999
                return BidAction.pass_bid()

        # Only seat 1 mutates; seats 0, 2, 3 just capture.
        cap0 = TranscriptCapturingPolicy("cap0")
        mutator = MutatingPolicy()
        cap2 = TranscriptCapturingPolicy("cap2")
        cap3 = TranscriptCapturingPolicy("cap3")

        # dealer = (initial_leader - 1) % 4 = 3, bid order: 0, 1, 2, 3
        play_single_hand(
            contract_type=None,
            bidding_policies=[cap0, mutator, cap2, cap3],
            initial_leader=0,
        )

        # Seat 1 (mutator) mutated its own copy of entry[0]["seat"] to 999.
        assert mutator.observations[0].auction_transcript[0]["seat"] == 999

        # Seat 2 should still see the original seat value (0) for entry[0],
        # proving the deep copy isolated the mutation.
        assert (
            cap2.observations[0].auction_transcript[0]["seat"] == 0
        ), "Mutation in seat 1's transcript leaked to seat 2's transcript"

        # Seat 3 should also see the original seat value (0) for entry[0].
        assert (
            cap3.observations[0].auction_transcript[0]["seat"] == 0
        ), "Mutation in seat 1's transcript leaked to seat 3's transcript"

    def test_mutation_does_not_affect_single_policy_path(self):
        """Mutating transcript entries in single-policy path is also isolated."""

        class MutateOnceSinglePolicy(BiddingPolicy):
            """Mutates transcript entry[0] only on the second call (first non-empty)."""

            def __init__(self):
                super().__init__(name="single_mutator")
                self.observations: list[BiddingObservation] = []
                self._call_count = 0

            def choose_bid(self, obs: BiddingObservation) -> BidAction:
                self.observations.append(obs)
                self._call_count += 1
                # Mutate only on the second call (first time transcript is non-empty)
                if self._call_count == 2 and obs.auction_transcript:
                    obs.auction_transcript[0]["seat"] = 999
                return BidAction.pass_bid()

        policy = MutateOnceSinglePolicy()

        play_single_hand(
            contract_type=None,
            bidding_policy=policy,
            initial_leader=0,
        )

        # 4 observations total.
        # Call 2 (obs[1]) mutated its copy of entry[0]["seat"] to 999.
        assert policy.observations[1].auction_transcript[0]["seat"] == 999

        # Calls 3 and 4 (obs[2], obs[3]) should see original seat=0,
        # proving the deep copy isolated the mutation.
        assert (
            policy.observations[2].auction_transcript[0]["seat"] == 0
        ), "Mutation leaked in single-policy path"
        assert (
            policy.observations[3].auction_transcript[0]["seat"] == 0
        ), "Mutation leaked in single-policy path"


class TestTranscriptIsSnapshot:
    """Verify transcript is a snapshot (tuple), not a mutable reference."""

    def test_transcript_is_tuple(self):
        """auction_transcript should be a tuple, not a list reference."""
        capturer = TranscriptCapturingPolicy("snapshot_test")

        play_single_hand(
            contract_type=None,
            bidding_policy=capturer,
            initial_leader=0,
        )

        for obs in capturer.observations:
            assert isinstance(
                obs.auction_transcript, tuple
            ), f"Expected tuple, got {type(obs.auction_transcript)}"

    def test_later_mutations_dont_affect_earlier_snapshots(self):
        """Transcript snapshots taken at different times should be independent."""
        capturer = TranscriptCapturingPolicy("mutation_test")

        play_single_hand(
            contract_type=None,
            bidding_policy=capturer,
            initial_leader=0,
        )

        # First observation should always have 0 entries
        # regardless of later appends to _transcript
        assert len(capturer.observations[0].auction_transcript) == 0
        # Last observation should have 3 entries
        assert len(capturer.observations[3].auction_transcript) == 3
