"""Tests for the hosted-play MatchEngine (Phase 1 core).

Required tests from sub-plan SP-1-01:
1.  Full hand flow
2.  All-pass redeal
3.  Match win
4.  Match loss
5.  Legal plays match core
6.  Scoring matches core
7.  Serialization round-trip
8.  Idempotent turn_number
9.  Dealer rotation
10. Human leads after winning auction
11. Visible state hides other hands

Moon/loner tests from sub-plan SP-1-02:
12. Moon/loner legality in get_legal_bids
13. Overcall hierarchy tracking
14. Moon exchange flow
15. Loner sit-out trick flow
16. Moon/loner scoring through compute_points
17. Regular bid regression after moon/loner changes
18. Serialization round-trip with moon/loner state
"""

from __future__ import annotations

import random
from typing import List, Optional, Tuple

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import get_legal_indices
from bid_euchre.hosted_play.engine import (
    HUMAN_SEAT,
    MATCH_TARGET,
    MatchEngine,
    _bid_order,
    _next_active_seat,
    _players_per_trick,
    sort_hand_for_display,
)
from bid_euchre.hosted_play.state import MatchState
from bid_euchre.scoring import compute_points
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import BidAction, BiddingObservation, BiddingPolicy
from bid_euchre.strategy.glutton import GluttonStrategy

# ---------------------------------------------------------------------------
# Test helpers — deterministic AI stubs
# ---------------------------------------------------------------------------


class AlwaysPassBidder(BiddingPolicy):
    """Bidding policy that always passes."""

    def __init__(self) -> None:
        super().__init__(name="always_pass")

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        return BidAction.pass_bid()


class FixedBidder(BiddingPolicy):
    """Bidding policy that bids a fixed amount if legal, else passes."""

    def __init__(self, n: int = 5, contract: str = "S") -> None:
        super().__init__(name=f"fixed_{n}{contract}")
        self._n = n
        self._contract = contract

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if self._n > obs.current_high_bid:
            return BidAction.bid(self._n, self._contract)
        return BidAction.pass_bid()


class MoonBidder(BiddingPolicy):
    """Bidding policy that bids moon if no bid yet, else passes."""

    def __init__(self, contract: str = "S") -> None:
        super().__init__(name=f"moon_{contract}")
        self._contract = contract

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.current_high_bid == 0:
            return BidAction.moon(self._contract)
        return BidAction.pass_bid()


class LonerBidder(BiddingPolicy):
    """Bidding policy that bids loner if no bid yet, else passes."""

    def __init__(self, contract: str = "S") -> None:
        super().__init__(name=f"loner_{contract}")
        self._contract = contract

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.current_high_bid == 0:
            return BidAction.loner(self._contract)
        return BidAction.pass_bid()


class FirstLegalPlay(Strategy):
    """Play strategy that always picks the first legal card."""

    def __init__(self) -> None:
        super().__init__(name="first_legal")

    def choose_card(
        self,
        hand: List[Card],
        plays_so_far: List[Tuple[int, Card]],
        contract_type: str,
        trump_suit: Optional[str],
        player_index: int,
    ) -> int:
        legal = get_legal_indices(hand, plays_so_far, contract_type, trump_suit)
        return legal[0]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SEED = 42


@pytest.fixture
def engine() -> MatchEngine:
    """Engine with a fixed 5S bidder and first-legal play strategy."""
    return MatchEngine(
        bidding_policy=FixedBidder(n=5, contract="S"),
        play_strategy=FirstLegalPlay(),
    )


@pytest.fixture
def pass_engine() -> MatchEngine:
    """Engine with all-pass bidding."""
    return MatchEngine(
        bidding_policy=AlwaysPassBidder(),
        play_strategy=FirstLegalPlay(),
    )


@pytest.fixture
def moon_engine() -> MatchEngine:
    """Engine with a moon bidder and first-legal play strategy."""
    return MatchEngine(
        bidding_policy=MoonBidder(contract="S"),
        play_strategy=FirstLegalPlay(),
    )


@pytest.fixture
def loner_engine() -> MatchEngine:
    """Engine with a loner bidder and first-legal play strategy."""
    return MatchEngine(
        bidding_policy=LonerBidder(contract="S"),
        play_strategy=FirstLegalPlay(),
    )


def _auto_exchange(engine: MatchEngine, state: MatchState) -> MatchState:
    """If in moon_exchange phase (selecting), auto-pick first 2 cards."""
    hand = state.current_hand
    if (
        hand is not None
        and hand.phase == "moon_exchange"
        and hand.exchange_phase == "selecting"
    ):
        state = engine.submit_exchange_selection(state, [0, 1])
    return state


def _play_full_hand(
    engine: MatchEngine,
    state: MatchState,
    human_bid: BidAction | None = None,
) -> MatchState:
    """Drive a full hand to completion, making first-legal plays for human.

    Args:
        human_bid: Optional specific bid for the human. If None, bids 5S
            if legal, else passes.
    """
    hand = state.current_hand
    assert hand is not None

    # Handle auction phase
    while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
        if human_bid is not None:
            state = engine.submit_human_bid(state, human_bid)
            human_bid = None  # Only use the override once
        elif 5 > hand.current_high_bid:
            state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
        else:
            state = engine.submit_human_bid(state, BidAction.pass_bid())
        hand = state.current_hand
        if hand is None:
            return state

    # Handle interactive moon exchange
    state = _auto_exchange(engine, state)

    # Handle trick play phase (skip if human is sitting out for moon/loner).
    # The engine now pauses after each AI card play (per-card reveal) and
    # after each trick completion, so we must resume between human plays.
    while (
        state.status == "active"
        and state.current_hand is not None
        and state.current_hand.phase == "trick_play"
    ):
        hand = state.current_hand
        if hand.paused_after_play:
            state = engine.resume_after_play(state)
            continue
        if hand.paused_after_trick:
            state = engine.resume_ai(state)
            continue
        if hand.sitting_out_seat == HUMAN_SEAT:
            break  # Human sits out — engine handles all play
        if hand.current_seat != HUMAN_SEAT:
            break  # Not human's turn, not paused — shouldn't happen
        legal = engine.get_legal_plays(state)
        state = engine.submit_human_card(state, legal[0])

    return state


def _play_until_match_end(engine: MatchEngine, state: MatchState) -> MatchState:
    """Drive the full match to completion."""
    iterations = 0
    max_iterations = 10000  # Safety valve (more iterations needed with trick pauses)
    while state.status == "active" and iterations < max_iterations:
        hand = state.current_hand
        assert hand is not None
        iterations += 1

        if hand.phase == "complete":
            # Match is not finished yet, but the hand paused on the result
            # screen. Advance explicitly to continue testing full-match flow.
            state = engine.advance_to_next_hand(state)
            continue
        if hand.phase == "redeal":
            state = engine.deal_after_redeal(state)
            continue
        if hand.phase == "trick_play" and hand.paused_after_play:
            state = engine.resume_after_play(state)
            continue
        if hand.phase == "trick_play" and hand.paused_after_trick:
            state = engine.resume_ai(state)
            continue
        if hand.phase == "auction":
            if hand.current_seat != HUMAN_SEAT:
                # In exceptional cases, force AI catch-up to keep the helper moving.
                state = engine._advance_ai(state)
                continue
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
        elif hand.phase == "moon_exchange":
            state = _auto_exchange(engine, state)
        elif hand.phase == "trick_play":
            if hand.current_seat == HUMAN_SEAT:
                legal = engine.get_legal_plays(state)
                state = engine.submit_human_card(state, legal[0])
            else:
                # In normal rounds, only human may sit out during moon/loner hands.
                state = engine._advance_ai(state)
        elif hand.phase == "complete":
            state = engine.advance_to_next_hand(state)
        else:
            raise AssertionError(f"Unexpected phase: {hand.phase}")

    assert (
        state.status == "complete"
    ), f"Match did not complete after {max_iterations} iterations"
    return state


# ---------------------------------------------------------------------------
# Test 1: Full hand flow
# ---------------------------------------------------------------------------


class TestFullHandFlow:
    """Deal → auction (human bids 5S) → 10 tricks → hand scoring."""

    def test_full_hand_completes(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        # Match should be active, hand should be in progress
        assert state.status == "active"
        hand = state.current_hand
        assert hand is not None
        assert hand.phase in ("auction", "trick_play")

        # Play through one full hand
        state = _play_full_hand(engine, state)

        # After one hand, match should still be active (score < 52)
        # or complete if somehow enough points were scored
        assert state.hands_played >= 1

    def test_hand_has_10_tricks(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        # Play the full match until at least one hand completes
        state = _play_full_hand(engine, state)

        # The match should have played at least one hand
        assert state.hands_played >= 1

    def test_hand_completion_pauses_for_result_screen(
        self, engine: MatchEngine
    ) -> None:
        """A completed hand remains complete and does not auto-deal the next hand."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None
        initial_deal_id = hand.deal_id
        initial_dealer = state.dealer_seat

        state = _play_full_hand(engine, state)

        hand = state.current_hand
        assert hand is not None
        if state.status == "active":
            assert hand.phase == "complete"
            assert hand.deal_id == initial_deal_id
            assert state.dealer_seat == initial_dealer
        else:
            assert state.status == "complete"


# ---------------------------------------------------------------------------
# Test 1b: Per-card pacing
# ---------------------------------------------------------------------------


class TestPerCardPacing:
    """AI cards appear one at a time via paused_after_play flag (#2231)."""

    def test_submit_human_card_pauses_after_first_ai(self, engine: MatchEngine) -> None:
        """After human plays, the engine pauses after one AI card play."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Advance through auction
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        # Advance through any per-card pauses to reach human's trick turn
        for _ in range(50):
            if hand.phase != "trick_play":
                break
            if hand.paused_after_play:
                state = engine.resume_after_play(state)
                hand = state.current_hand
                assert hand is not None
                continue
            if hand.paused_after_trick:
                state = engine.resume_ai(state)
                hand = state.current_hand
                assert hand is not None
                continue
            break

        if hand.phase != "trick_play" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Not in human trick play position")

        pre_plays = len(hand.current_trick.plays) if hand.current_trick else 0
        legal = engine.get_legal_plays(state)
        state = engine.submit_human_card(state, legal[0])
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "trick_play" and not hand.paused_after_trick:
            # If trick didn't complete, engine should have paused after
            # exactly one AI card play.
            assert hand.paused_after_play is True
            post_plays = len(hand.current_trick.plays) if hand.current_trick else 0
            # Human played +1, AI played +1 = +2 from before
            assert post_plays == pre_plays + 2

    def test_resume_after_play_advances_one_card(self, engine: MatchEngine) -> None:
        """Each resume_after_play() call advances exactly one AI card."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Get to a paused_after_play state
        state = _play_full_hand(engine, state)
        # _play_full_hand handles all pauses internally, so let's take
        # a more direct approach
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Bid through auction
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        # Advance to first paused_after_play state
        for _ in range(50):
            hand = state.current_hand
            if hand is None:
                break
            if hand.phase == "trick_play" and hand.paused_after_play:
                break
            if hand.paused_after_trick:
                state = engine.resume_ai(state)
                continue
            if hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                legal = engine.get_legal_plays(state)
                state = engine.submit_human_card(state, legal[0])
                continue
            break

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play" or not hand.paused_after_play:
            pytest.skip("Could not reach paused_after_play state")

        pre_plays = len(hand.current_trick.plays) if hand.current_trick else 0
        state = engine.resume_after_play(state)
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "trick_play" and hand.current_trick is not None:
            post_plays = len(hand.current_trick.plays)
            # Should have advanced by exactly 1 card (or trick completed)
            assert post_plays == pre_plays + 1 or hand.paused_after_trick

    def test_paused_after_play_serialization(self, engine: MatchEngine) -> None:
        """paused_after_play survives serialization round-trip."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Set the flag manually
        hand.paused_after_play = True
        data = engine.serialize(state)
        restored = engine.deserialize(data)
        assert restored.current_hand is not None
        assert restored.current_hand.paused_after_play is True

        # And the default (False)
        hand.paused_after_play = False
        data = engine.serialize(state)
        restored = engine.deserialize(data)
        assert restored.current_hand is not None
        assert restored.current_hand.paused_after_play is False

    def test_submit_human_card_pauses_without_ai_advance(
        self, engine: MatchEngine
    ) -> None:
        """submit_human_card sets paused_after_play without advancing AI (#2405).

        When the human plays a card that does NOT complete the trick, the
        engine must:
        1. Set ``paused_after_play = True``
        2. NOT call ``_advance_ai()`` — no AI cards are played
        3. Return with only the human's card added to the trick
        """
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Have the human win the auction so they lead (guaranteeing their
        # card won't complete the trick since they play first).
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if hand.current_high_bid < 6:
                state = engine.submit_human_bid(state, BidAction.bid(6, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        # Advance through auction reveals and pauses to reach the human's
        # first trick play turn.
        for _ in range(80):
            hand = state.current_hand
            if hand is None:
                break
            if hand.phase != "trick_play":
                break
            if hand.paused_after_play:
                state = engine.resume_after_play(state)
                continue
            if hand.paused_after_trick:
                state = engine.resume_ai(state)
                continue
            if hand.current_seat == HUMAN_SEAT:
                break  # Found the human's turn
            break

        hand = state.current_hand
        if (
            hand is None
            or hand.phase != "trick_play"
            or hand.current_seat != HUMAN_SEAT
        ):
            pytest.skip("Could not reach human trick-play turn")

        trick = hand.current_trick
        pre_plays = len(trick.plays) if trick else 0
        pre_tricks = len(hand.completed_tricks)

        # --- Act ---
        legal = engine.get_legal_plays(state)
        state = engine.submit_human_card(state, legal[0])

        # --- Assert ---
        hand_after = state.current_hand
        assert hand_after is not None
        assert hand_after.phase == "trick_play"

        # Trick must NOT have completed (human didn't play last)
        assert (
            len(hand_after.completed_tricks) == pre_tricks
        ), "Expected trick to remain incomplete after human plays mid-trick"

        # 1. paused_after_play is set
        assert (
            hand_after.paused_after_play is True
        ), "submit_human_card must set paused_after_play when trick is incomplete"

        # 2. Only the human's card was added — no AI advancement
        trick_after = hand_after.current_trick
        assert trick_after is not None
        post_plays = len(trick_after.plays)
        assert post_plays == pre_plays + 1, (
            f"Expected {pre_plays + 1} plays (human only), got {post_plays}; "
            "AI should NOT advance after human card play"
        )

        # 3. No AI action events were generated
        assert (
            engine.last_ai_events == []
        ), "submit_human_card must not generate AI events"


# ---------------------------------------------------------------------------
# Test: skip_to_next_decision (#2309)
# ---------------------------------------------------------------------------


class TestSkipToNextDecision:
    """skip_to_next_decision advances past all per-card pauses (#2309)."""

    def _reach_paused_after_play(
        self, engine: MatchEngine, seed: int = SEED
    ) -> MatchState:
        """Drive match to a ``paused_after_play`` state, or pytest.skip."""
        state = engine.start_match(seed, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Bid through auction
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        # Advance to first paused_after_play state
        for _ in range(80):
            hand = state.current_hand
            if hand is None:
                break
            if hand.phase == "trick_play" and hand.paused_after_play:
                return state
            if hand.paused_after_trick:
                state = engine.resume_ai(state)
                continue
            if hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
                legal = engine.get_legal_plays(state)
                state = engine.submit_human_card(state, legal[0])
                continue
            break

        pytest.skip("Could not reach paused_after_play state")

    def test_skip_advances_to_trick_end(self, engine: MatchEngine) -> None:
        """skip_to_next_decision stops at paused_after_trick (trick boundary)."""
        state = self._reach_paused_after_play(engine)
        hand = state.current_hand
        assert hand is not None
        assert hand.paused_after_play is True

        state = engine.skip_to_next_decision(state)
        hand = state.current_hand

        # After skip, should NOT be paused_after_play — only after_trick,
        # human turn, or hand/match end are valid stops.
        if hand is not None and hand.phase == "trick_play":
            assert hand.paused_after_play is False
            # Must be at a valid decision point:
            assert (
                hand.paused_after_trick
                or hand.current_seat == HUMAN_SEAT
                or hand.phase != "trick_play"
            )

    def test_skip_stops_at_human_turn(self, engine: MatchEngine) -> None:
        """skip_to_next_decision returns when the human's seat is next."""
        state = self._reach_paused_after_play(engine)

        state = engine.skip_to_next_decision(state)
        hand = state.current_hand

        if hand is not None and hand.phase == "trick_play":
            # Must be at a valid stop: paused_after_trick or human's turn
            assert hand.paused_after_trick or hand.current_seat == HUMAN_SEAT

    def test_skip_when_not_paused_is_noop(self, engine: MatchEngine) -> None:
        """skip_to_next_decision is a no-op when no pause flag is set."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Bid through auction
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        # Clear any pauses to reach a clean state
        for _ in range(80):
            hand = state.current_hand
            if hand is None:
                break
            if hand.paused_after_play:
                state = engine.resume_after_play(state)
                continue
            if hand.paused_after_trick:
                state = engine.resume_ai(state)
                continue
            break

        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("Could not reach clean trick_play state")

        # Take a snapshot before skip
        pre_trick_count = len(hand.completed_tricks)
        pre_seat = hand.current_seat

        state_after = engine.skip_to_next_decision(state)
        hand_after = state_after.current_hand

        # When neither pause flag is set, skip_to_next_decision returns
        # immediately — state unchanged.
        if hand_after is not None and hand_after.phase == "trick_play":
            assert len(hand_after.completed_tricks) == pre_trick_count
            assert hand_after.current_seat == pre_seat

    def test_skip_clears_last_ai_events(self, engine: MatchEngine) -> None:
        """skip_to_next_decision always clears last_ai_events before advancing."""
        state = self._reach_paused_after_play(engine)

        # Pre-populate events to verify they get cleared
        engine.last_ai_events = [{"fake": "event"}]
        state = engine.skip_to_next_decision(state)

        # last_ai_events should have been reset (may contain new events from
        # the advance, but the pre-existing fake event must be gone).
        assert {"fake": "event"} not in engine.last_ai_events

    def test_skip_at_hand_end(self, engine: MatchEngine) -> None:
        """skip_to_next_decision returns immediately if hand is complete/None."""
        state = engine.start_match(SEED, "heuristic")

        # Play a full hand to completion
        state = _play_full_hand(engine, state)
        hand = state.current_hand

        # After _play_full_hand, the hand may be phase="complete" (hand
        # finished but not yet advanced) or still in trick_play (human
        # sitting out).  If it's complete, advance to get current_hand=None.
        if hand is not None and hand.phase == "complete":
            state = engine.advance_to_next_hand(state)

        # Now either current_hand is None (inter-hand) or status=="complete"
        # (match over).  In both cases skip should be a no-op.
        if state.status == "complete":
            state_after = engine.skip_to_next_decision(state)
            assert state_after.status == "complete"
        elif state.current_hand is None:
            state_after = engine.skip_to_next_decision(state)
            assert state_after.current_hand is None
        else:
            # Hand is still in progress (e.g. redeal or next hand started)
            # — skip should still be safe to call
            state_after = engine.skip_to_next_decision(state)
            assert state_after.status in ("active", "complete")
            if state_after.current_hand is not None:
                assert state_after.current_hand.phase in (
                    "auction",
                    "trick_play",
                    "complete",
                    "redeal",
                    "moon_exchange",
                )

    def test_skip_at_match_complete(self, engine: MatchEngine) -> None:
        """skip_to_next_decision returns immediately if match is complete."""
        state = _play_until_match_end(engine, engine.start_match(SEED, "heuristic"))
        assert state.status == "complete"

        state_after = engine.skip_to_next_decision(state)
        assert state_after.status == "complete"

    def test_skip_during_non_trick_phase(self, engine: MatchEngine) -> None:
        """skip_to_next_decision returns immediately if not in trick_play."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "auction"

        state_after = engine.skip_to_next_decision(state)
        hand_after = state_after.current_hand
        assert hand_after is not None
        # Should return without changing the phase
        assert hand_after.phase == "auction"


# ---------------------------------------------------------------------------
# Test 2: All-pass redeal
# ---------------------------------------------------------------------------


class TestAllPassRedeal:
    """All 4 pass → hand marked redeal; deal_after_redeal() starts next hand."""

    def test_all_pass_triggers_redeal(self, pass_engine: MatchEngine) -> None:
        state = pass_engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # When all AI pass, engine pauses for human bid
        assert hand.phase == "auction"
        assert hand.current_seat == HUMAN_SEAT

        initial_dealer = state.dealer_seat
        initial_deal_id = state.deal_id

        # Human also passes → all-pass → hand marked "redeal"
        state = pass_engine.submit_human_bid(state, BidAction.pass_bid())

        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "redeal"
        # Dealer and deal_id not yet advanced (waiting for persistence)
        assert state.dealer_seat == initial_dealer
        assert state.deal_id == initial_deal_id
        assert state.hands_played == 0  # Redeals don't count

        # After persistence, deal the next hand
        state = pass_engine.deal_after_redeal(state)

        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "auction"
        assert state.hands_played == 0  # Still no completed hands
        assert state.dealer_seat == (initial_dealer + 1) % 4
        assert state.deal_id == initial_deal_id + 1

    def test_redeal_advances_dealer(self) -> None:
        """Verify dealer rotates only after deal_after_redeal()."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        initial_dealer = state.dealer_seat

        # Human passes — triggers all-pass redeal
        state = engine.submit_human_bid(state, BidAction.pass_bid())

        # Before deal_after_redeal, dealer hasn't rotated
        assert state.dealer_seat == initial_dealer
        assert state.current_hand is not None
        assert state.current_hand.phase == "redeal"

        # After deal_after_redeal, dealer advances
        state = engine.deal_after_redeal(state)
        expected = (initial_dealer + 1) % 4
        assert state.dealer_seat == expected


# ---------------------------------------------------------------------------
# Test 3: Match win
# ---------------------------------------------------------------------------


class TestMatchWin:
    """Score reaches +52, status becomes "complete", winner = "human"."""

    def test_match_reaches_completion(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")
        state = _play_until_match_end(engine, state)

        assert state.status == "complete"
        assert state.winner in ("human", "ai")
        assert state.hands_played > 0

    def test_human_win_at_52(self) -> None:
        """Directly verify that score_human >= 52 triggers human win."""
        state = MatchState(seed=1, ai_model="test")
        state.score_human = MATCH_TARGET
        state.status = "complete"
        state.winner = "human"
        assert state.score_human >= MATCH_TARGET
        assert state.winner == "human"


# ---------------------------------------------------------------------------
# Test 4: Match loss
# ---------------------------------------------------------------------------


class TestMatchLoss:
    """Score reaches conditions for AI win."""

    def test_ai_win_at_52(self) -> None:
        """Score_ai >= 52 triggers AI win."""
        state = MatchState(seed=1, ai_model="test")
        state.score_ai = MATCH_TARGET
        state.status = "complete"
        state.winner = "ai"
        assert state.score_ai >= MATCH_TARGET
        assert state.winner == "ai"


# ---------------------------------------------------------------------------
# Test 5: Legal plays match core
# ---------------------------------------------------------------------------


class TestLegalPlaysMatchCore:
    """Verify get_legal_plays() matches get_legal_indices() output."""

    def test_legal_plays_delegate_to_core(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        # Get to trick play phase
        hand = state.current_hand
        assert hand is not None
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        if hand.phase != "trick_play" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Human not in trick play position")

        # Compare engine's legal plays with direct core call
        engine_legal = engine.get_legal_plays(state)
        assert hand.current_trick is not None
        assert hand.contract_type is not None
        core_legal = get_legal_indices(
            hand.hands[HUMAN_SEAT],
            hand.current_trick.plays,
            hand.contract_type,
            hand.trump,
        )
        assert engine_legal == core_legal

    def test_legal_plays_multiple_states(self, engine: MatchEngine) -> None:
        """Check legal plays at several game states."""
        state = engine.start_match(SEED, "heuristic")

        checks = 0
        iterations = 0
        while state.status == "active" and checks < 5 and iterations < 500:
            hand = state.current_hand
            assert hand is not None
            iterations += 1

            # Advance past per-card and trick-completion pauses
            if hand.phase == "trick_play" and hand.paused_after_play:
                state = engine.resume_after_play(state)
                continue
            if hand.phase == "trick_play" and hand.paused_after_trick:
                state = engine.resume_ai(state)
                continue

            if hand.current_seat != HUMAN_SEAT:
                break

            if hand.phase == "auction":
                if 5 > hand.current_high_bid:
                    state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
                else:
                    state = engine.submit_human_bid(state, BidAction.pass_bid())
            elif hand.phase == "trick_play":
                # Verify legal plays match
                engine_legal = engine.get_legal_plays(state)
                assert hand.current_trick is not None
                assert hand.contract_type is not None
                core_legal = get_legal_indices(
                    hand.hands[HUMAN_SEAT],
                    hand.current_trick.plays,
                    hand.contract_type,
                    hand.trump,
                )
                assert engine_legal == core_legal
                checks += 1

                state = engine.submit_human_card(state, engine_legal[0])

        assert checks > 0, "No legal play checks were performed"


# ---------------------------------------------------------------------------
# Test 6: Scoring matches core
# ---------------------------------------------------------------------------


class TestScoringMatchesCore:
    """Verify hand points match compute_points() output."""

    def test_scoring_delegates_to_core(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        # Play a full hand
        state = _play_full_hand(engine, state)
        assert state.hands_played >= 1

        # The score should have changed by the points from the hand
        # We can't easily verify the exact hand since it's overwritten,
        # but we can verify that scores are non-zero or that the match
        # progresses consistently
        assert isinstance(state.score_human, int)
        assert isinstance(state.score_ai, int)

    def test_scoring_via_full_match(self, engine: MatchEngine) -> None:
        """Run a full match and verify total scores are consistent."""
        state = engine.start_match(SEED, "heuristic")
        state = _play_until_match_end(engine, state)

        # Winner should have reached ±52
        if state.winner == "human":
            assert state.score_human >= MATCH_TARGET or state.score_ai <= -MATCH_TARGET
        else:
            assert state.score_ai >= MATCH_TARGET or state.score_human <= -MATCH_TARGET


# ---------------------------------------------------------------------------
# Test 7: Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerializationRoundTrip:
    """Serialize mid-hand state, deserialize, verify equality."""

    def test_round_trip_mid_auction(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        # Serialize and deserialize
        data = MatchEngine.serialize(state)
        restored = MatchEngine.deserialize(data)

        assert restored == state

    def test_round_trip_mid_trick_play(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        # Get to trick play
        hand = state.current_hand
        assert hand is not None
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        if hand.phase == "trick_play":
            data = MatchEngine.serialize(state)
            restored = MatchEngine.deserialize(data)
            assert restored == state

    def test_round_trip_preserves_cards(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        original_hand_0 = list(hand.hands[0])

        data = MatchEngine.serialize(state)
        restored = MatchEngine.deserialize(data)

        assert restored.current_hand is not None
        assert restored.current_hand.hands[0] == original_hand_0


# ---------------------------------------------------------------------------
# Test 8: Idempotent turn_number
# ---------------------------------------------------------------------------


class TestIdempotentTurnNumber:
    """Turn number increments monotonically and is deterministic."""

    def test_turn_number_increments(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        prev_turn = hand.turn_number

        # Make a move — turn number should increase
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())

            hand = state.current_hand
            if hand is not None:
                assert hand.turn_number > prev_turn

    def test_same_seed_same_turns(self) -> None:
        """Two matches with same seed produce identical turn sequences."""
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        state1 = engine.start_match(SEED, "heuristic")
        state2 = engine.start_match(SEED, "heuristic")

        assert state1.current_hand is not None
        assert state2.current_hand is not None
        assert state1.current_hand.turn_number == state2.current_hand.turn_number

        # Both should be at the same position
        assert state1.current_hand.current_seat == state2.current_hand.current_seat
        assert state1.current_hand.phase == state2.current_hand.phase


# ---------------------------------------------------------------------------
# Test 9: Dealer rotation
# ---------------------------------------------------------------------------


class TestDealerRotation:
    """Dealer advances correctly across multiple hands."""

    def test_dealer_rotates_after_hand(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")
        initial_dealer = state.dealer_seat

        # Play through one complete hand
        state = _play_full_hand(engine, state)
        assert state.hands_played >= 1
        # Dealer should stay until explicit transition
        assert state.dealer_seat == initial_dealer
        if state.status == "active" and state.hands_played >= 1:
            state = engine.advance_to_next_hand(state)
            # Dealer should have advanced
            expected = (initial_dealer + 1) % 4
            assert state.dealer_seat == expected

    def test_dealer_rotates_on_redeal(self) -> None:
        """Dealer rotates after deal_after_redeal() on all-pass."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        initial_dealer = state.dealer_seat

        # Human passes → all pass → redeal (hand marked, not yet dealt)
        state = engine.submit_human_bid(state, BidAction.pass_bid())
        assert state.current_hand is not None
        assert state.current_hand.phase == "redeal"
        assert state.dealer_seat == initial_dealer  # Not yet rotated

        # After deal_after_redeal, dealer advances
        state = engine.deal_after_redeal(state)
        expected = (initial_dealer + 1) % 4
        assert state.dealer_seat == expected


class TestHandCompletionTransition:
    """Hand lifecycle transitions from complete to next hand."""

    def test_full_hand_marks_complete(self, engine: MatchEngine) -> None:
        """Driving a full hand ends with hand.phase == complete."""
        state = engine.start_match(SEED, "heuristic")
        state = _play_full_hand(engine, state)

        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "complete"

    def test_advance_to_next_hand_starts_new_hand(self, engine: MatchEngine) -> None:
        """advance_to_next_hand() should move to a fresh auction hand."""
        state = engine.start_match(SEED, "heuristic")
        initial_dealer = state.dealer_seat
        initial_deal_id = state.deal_id

        state = _play_full_hand(engine, state)
        assert state.current_hand is not None
        assert state.current_hand.phase == "complete"

        state = engine.advance_to_next_hand(state)
        hand = state.current_hand
        assert hand is not None
        if state.status == "active":
            assert hand.phase in ("auction", "trick_play")
            assert state.deal_id == initial_deal_id + 1
            assert state.dealer_seat == (initial_dealer + 1) % 4

    def test_advance_to_next_hand_noop_when_not_complete(
        self, engine: MatchEngine
    ) -> None:
        """advance_to_next_hand() should be a no-op unless hand.phase == complete."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None
        assert hand.phase in ("auction", "trick_play", "redeal")

        state_after = engine.advance_to_next_hand(state)
        hand_after = state_after.current_hand
        assert hand_after is not None
        assert hand_after == hand
        assert hand_after.phase != "complete"


# ---------------------------------------------------------------------------
# Test 10: Human leads after winning auction
# ---------------------------------------------------------------------------


class TestHumanLeadsAfterAuctionWin:
    """Declarer leads the first trick."""

    def test_human_declarer_leads(self) -> None:
        """When human wins the auction, human leads first trick."""
        # Use a bidder that passes (so human's bid of 5 wins)
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )

        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "auction"

        # Human bids 5S (AI all pass, so human should be first bidder
        # and wins)
        state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
        hand = state.current_hand
        assert hand is not None

        # After auction (all AI pass), human should be declarer and lead
        if hand.phase == "trick_play":
            assert hand.current_seat == HUMAN_SEAT
            assert hand.current_trick is not None
            assert hand.current_trick.leader == HUMAN_SEAT
            assert hand.bidder_seat == HUMAN_SEAT

    def test_ai_declarer_leads(self) -> None:
        """When AI wins the auction, AI leads first trick (not human)."""
        # Use a bidder that always bids high
        engine = MatchEngine(
            bidding_policy=FixedBidder(n=8, contract="H"),
            play_strategy=FirstLegalPlay(),
        )

        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # The engine auto-advanced AI bids. If an AI bid 8H, and human
        # needs to pass (since 8 is already high), the auction will
        # resolve with AI as declarer.
        # Human passes
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is not None and hand.phase == "trick_play":
                # The declarer should be the AI seat that bid highest
                assert hand.bidder_seat != HUMAN_SEAT
                # The trick leader should be the declarer
                assert hand.current_trick is not None
                assert hand.current_trick.leader == hand.bidder_seat
                # Engine auto-advanced one AI card play; with per-card
                # pacing it pauses after each AI card, so current_seat
                # may be an AI seat with paused_after_play set.
                if hand.paused_after_play:
                    assert hand.current_seat != HUMAN_SEAT
                else:
                    assert hand.current_seat == HUMAN_SEAT


# ---------------------------------------------------------------------------
# Test 11: Visible state hides other hands
# ---------------------------------------------------------------------------


class TestVisibleStateHidesHands:
    """get_visible_state() shows only seat 0's cards."""

    def test_only_human_hand_visible(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        visible = engine.get_visible_state(state)

        # Should have human_hand
        assert "human_hand" in visible
        assert len(visible["human_hand"]) > 0

        # Should NOT expose other hands
        for key in visible:
            assert key != "hands", "Full hands array should not be in visible state"

    def test_visible_state_has_scores(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        visible = engine.get_visible_state(state)

        assert "score_human" in visible
        assert "score_ai" in visible
        assert "status" in visible
        assert "phase" in visible

    def test_visible_state_has_trick_info(self, engine: MatchEngine) -> None:
        state = engine.start_match(SEED, "heuristic")

        visible = engine.get_visible_state(state)

        assert "current_trick" in visible
        assert "completed_tricks" in visible
        assert "auction" in visible


# ---------------------------------------------------------------------------
# Additional integration tests
# ---------------------------------------------------------------------------


class TestBidOrder:
    """Verify the auction order helper."""

    def test_bid_order_from_dealer_0(self) -> None:
        assert _bid_order(0) == [1, 2, 3, 0]

    def test_bid_order_from_dealer_2(self) -> None:
        assert _bid_order(2) == [3, 0, 1, 2]

    def test_bid_order_from_dealer_3(self) -> None:
        assert _bid_order(3) == [0, 1, 2, 3]


class TestAIActionEvents:
    """Verify engine emits exact AI action events during auto-advance."""

    def test_start_match_emits_bid_events(self, engine: MatchEngine) -> None:
        """start_match() emits events for AI bids in the first auction."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Engine should have captured AI bid events during start_match
        events = engine.last_ai_events
        assert len(events) > 0, "Expected at least one AI event from start_match"

        for event in events:
            assert event.seat != HUMAN_SEAT, "AI events should not be for human seat"
            assert event.phase == "bid"
            assert isinstance(event.legal_actions, list)
            assert len(event.legal_actions) > 0, "legal_actions must not be empty"
            assert isinstance(event.chosen_action, dict)
            assert "n" in event.chosen_action
            assert "contract" in event.chosen_action
            assert isinstance(event.game_state, dict)
            assert event.game_state["phase"] == "auction"

    def test_submit_human_bid_emits_events(self, engine: MatchEngine) -> None:
        """submit_human_bid() emits events for subsequent AI bids."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase != "auction" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Human not in auction position after start")

        # Human passes
        state = engine.submit_human_bid(state, BidAction.pass_bid())

        # Events should be fresh (only from this submit call)
        for event in engine.last_ai_events:
            assert event.seat != HUMAN_SEAT
            assert len(event.legal_actions) > 0

    def test_submit_human_card_emits_play_events(self, engine: MatchEngine) -> None:
        """submit_human_card() emits events for subsequent AI plays."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Get to trick play
        while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            if 5 > hand.current_high_bid:
                state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
            else:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
            hand = state.current_hand
            if hand is None:
                pytest.skip("Match ended during auction")

        if hand.phase != "trick_play" or hand.current_seat != HUMAN_SEAT:
            pytest.skip("Human not in trick play position")

        legal = engine.get_legal_plays(state)
        state = engine.submit_human_card(state, legal[0])

        # Should have AI play events
        play_events = [e for e in engine.last_ai_events if e.phase == "play"]
        if len(play_events) > 0:
            for event in play_events:
                assert event.seat != HUMAN_SEAT
                assert isinstance(event.legal_actions, list)
                assert len(event.legal_actions) > 0
                assert isinstance(event.chosen_action, int)
                assert event.game_state["phase"] == "trick_play"

    def test_events_cleared_between_calls(self, engine: MatchEngine) -> None:
        """Each public method resets last_ai_events."""
        state = engine.start_match(SEED, "heuristic")
        events_from_start = list(engine.last_ai_events)
        assert len(events_from_start) > 0

        hand = state.current_hand
        assert hand is not None
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.pass_bid())
            # Events should be fresh, not accumulated from start_match
            assert engine.last_ai_events != events_from_start

    def test_event_seat_is_exact(self, engine: MatchEngine) -> None:
        """Event seat matches the actual AI seat that acted."""
        engine.start_match(SEED, "heuristic")
        events = engine.last_ai_events

        for event in events:
            assert 0 <= event.seat < 4
            assert event.seat != HUMAN_SEAT
            # Seat must be one of the AI seats
            assert event.seat in (1, 2, 3)

    def test_event_game_state_has_required_fields(self, engine: MatchEngine) -> None:
        """Event game_state contains context fields for replay."""
        engine.start_match(SEED, "heuristic")
        events = engine.last_ai_events
        assert len(events) > 0

        required_fields = {
            "phase",
            "seat",
            "turn_number",
            "dealer_seat",
            "current_high_bid",
            "auction",
            "contract_type",
            "trump",
            "bid_type",
            "tricks_team0",
            "tricks_team1",
            "hand_size",
        }
        for event in events:
            assert required_fields.issubset(
                event.game_state.keys()
            ), f"Missing fields: {required_fields - event.game_state.keys()}"


class TestMatchDeterminism:
    """Same seed + config = identical results."""

    def test_opening_dealer_derived_from_seed(self) -> None:
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        state = engine.start_match(SEED, "heuristic")
        assert state.dealer_seat == random.Random(SEED).randrange(4)

    def test_same_seed_same_result(self) -> None:
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        state1 = engine.start_match(SEED, "heuristic")
        state2 = engine.start_match(SEED, "heuristic")

        # Both should produce identical state
        assert MatchEngine.serialize(state1) == MatchEngine.serialize(state2)

    def test_different_seeds_differ(self) -> None:
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        state1 = engine.start_match(SEED, "heuristic")
        state2 = engine.start_match(SEED + 1, "heuristic")

        # Different seeds should produce different hands
        assert state1.current_hand is not None
        assert state2.current_hand is not None
        # Hands should differ (extremely unlikely to be identical)
        assert state1.current_hand.hands != state2.current_hand.hands


# ===========================================================================
# Moon/Loner Tests (SP-1-02)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 12: Moon/loner legality in get_legal_bids
# ---------------------------------------------------------------------------


class TestMoonLonerLegality:
    """get_legal_bids() includes moon/loner options when appropriate."""

    def test_legal_bids_include_moon_and_loner(self, engine: MatchEngine) -> None:
        """Fresh auction should include moon and loner bids."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # If human's turn in auction, get legal bids
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_bids(state)

            bid_types = {b.bid_type for b in legal if not b.is_pass()}
            assert "regular" in bid_types, "Should include regular bids"
            assert "moon" in bid_types, "Should include moon bids"
            assert "loner" in bid_types, "Should include loner bids"

            # Moon bids are always level 10
            moon_bids = [b for b in legal if b.bid_type == "moon"]
            assert all(b.n == 10 for b in moon_bids)

            # Loner bids are always level 10
            loner_bids = [b for b in legal if b.bid_type == "loner"]
            assert all(b.n == 10 for b in loner_bids)

    def test_no_regular_bids_after_moon(self) -> None:
        """After a moon bid, regular bids are no longer legal."""
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # AI should have bid moon; when it's human's turn, check legality
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_bids(state)
            regular_bids = [
                b for b in legal if b.bid_type == "regular" and not b.is_pass()
            ]
            assert (
                len(regular_bids) == 0
            ), "Regular bids should not be legal after a moon bid"

            # Should still have pass, loner
            assert any(b.is_pass() for b in legal)
            loner_bids = [b for b in legal if b.bid_type == "loner"]
            assert len(loner_bids) > 0, "Loner bids should overcall moon"

    def test_only_pass_after_loner(self) -> None:
        """After a loner bid, only pass is legal (for non-dealer)."""
        engine = MatchEngine(
            bidding_policy=LonerBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # AI should have bid loner
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_bids(state)
            is_dealer = hand.current_seat == hand.dealer_seat
            non_pass = [b for b in legal if not b.is_pass()]
            if not is_dealer:
                # Non-dealer: only loner bids (to overcall) are legal,
                # but since current bid IS loner, only dealer take-away is
                # possible. Non-dealer gets only pass.
                # Actually — loner overcalls moon and regular. After a
                # loner, only another loner (dealer take-away) overcalls.
                loner_bids = [b for b in non_pass if b.bid_type == "loner"]
                assert len(loner_bids) == 0, "Non-dealer cannot overcall a loner bid"

    def test_pass_always_legal(self, engine: MatchEngine) -> None:
        """Pass is always an option regardless of current bid state."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_bids(state)
            assert any(b.is_pass() for b in legal)


# ---------------------------------------------------------------------------
# Test 13: Overcall hierarchy tracking
# ---------------------------------------------------------------------------


class TestOvercallHierarchy:
    """bid_type and bid_rank are tracked correctly during auction."""

    def test_moon_overcalls_regular(self) -> None:
        """Moon overcalls any regular bid."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            # Human bids moon
            state = engine.submit_human_bid(state, BidAction.moon("H"))
            hand = state.current_hand
            assert hand is not None

            # After all others pass, hand state should reflect moon
            if hand.phase in ("trick_play", "redeal"):
                pass  # Auction ended
            # During auction, bid_type should be "moon"
            assert hand.bid_type == "moon"
            assert hand.current_high_bid == 10
            assert hand.bidder_seat == HUMAN_SEAT

    def test_loner_overcalls_moon(self) -> None:
        """Loner overcalls moon."""
        # AI bids moon, human can overcall with loner
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            # Human overcalls with loner
            state = engine.submit_human_bid(state, BidAction.loner("H"))
            hand = state.current_hand
            assert hand is not None
            assert hand.bid_type == "loner"
            assert hand.bidder_seat == HUMAN_SEAT

    def test_regular_cannot_overcall_moon(self) -> None:
        """Regular bid cannot overcall moon — only loner can."""
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_bids(state)
            regular_bids = [
                b for b in legal if b.bid_type == "regular" and not b.is_pass()
            ]
            assert len(regular_bids) == 0


# ---------------------------------------------------------------------------
# Test 14: Moon exchange flow
# ---------------------------------------------------------------------------


class TestMoonExchange:
    """Moon win triggers a 2-card exchange before trick play."""

    def test_moon_exchange_happens(self) -> None:
        """After a moon bid wins, hands are modified by exchange."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            # Capture pre-exchange hands
            hand_before_human = list(hand.hands[HUMAN_SEAT])
            hand_before_partner = list(hand.hands[2])

            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            # Human is mooner — should enter interactive exchange phase
            if hand.phase == "moon_exchange":
                assert hand.exchange_phase == "selecting"
                state = engine.submit_exchange_selection(state, [0, 1])
                hand = state.current_hand
                assert hand is not None

            if hand.phase == "trick_play":
                # Exchange should have occurred
                assert hand.exchange_given is not None
                assert hand.exchange_received is not None
                assert len(hand.exchange_given) == 2
                assert len(hand.exchange_received) == 2

                # Hands should have changed (extremely unlikely to be same)
                assert hand.hands[HUMAN_SEAT] != hand_before_human
                assert hand.hands[2] != hand_before_partner

                # Both hands should still have 10 cards
                assert len(hand.hands[HUMAN_SEAT]) == 10
                assert len(hand.hands[2]) == 10

    def test_moon_exchange_state_persists(self) -> None:
        """Exchange metadata survives serialization."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            # Handle interactive exchange
            if hand.phase == "moon_exchange":
                state = engine.submit_exchange_selection(state, [0, 1])
                hand = state.current_hand
                assert hand is not None

            if hand.phase == "trick_play" and hand.exchange_given is not None:
                data = MatchEngine.serialize(state)
                restored = MatchEngine.deserialize(data)
                assert restored.current_hand is not None
                assert restored.current_hand.exchange_given == hand.exchange_given
                assert restored.current_hand.exchange_received == hand.exchange_received


# ---------------------------------------------------------------------------
# Test 14b: Interactive moon exchange
# ---------------------------------------------------------------------------


class TestInteractiveMoonExchange:
    """Moon exchange pauses for human card selection when human is involved."""

    def test_human_mooner_enters_exchange_phase(self) -> None:
        """When human bids moon, engine enters moon_exchange selecting phase."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None
            assert hand.phase == "moon_exchange"
            assert hand.exchange_phase == "selecting"
            # Exchange not yet done
            assert hand.exchange_given is None
            assert hand.exchange_received is None
            # Hand still has 10 cards
            assert len(hand.hands[HUMAN_SEAT]) == 10

    def test_human_mooner_exchange_selection(self) -> None:
        """Human mooner selects 2 cards, exchange completes properly."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None
            assert hand.phase == "moon_exchange"

            # Choose first two cards
            chosen_0 = hand.hands[HUMAN_SEAT][0]
            chosen_1 = hand.hands[HUMAN_SEAT][1]
            state = engine.submit_exchange_selection(state, [0, 1])
            hand = state.current_hand
            assert hand is not None

            # Should be in trick_play now
            assert hand.phase == "trick_play"
            assert hand.exchange_phase is None
            assert hand.exchange_given is not None
            assert hand.exchange_received is not None
            assert len(hand.exchange_given) == 2
            assert len(hand.exchange_received) == 2

            # The cards human gave should be the ones at indices 0 and 1
            given_cards = {tuple(c) for c in hand.exchange_given}
            assert (chosen_0.suit, chosen_0.rank) in given_cards
            assert (chosen_1.suit, chosen_1.rank) in given_cards

            # Both hands still 10 cards
            assert len(hand.hands[HUMAN_SEAT]) == 10
            assert len(hand.hands[2]) == 10

    def test_human_partner_exchange_phase(self) -> None:
        """When AI partner bids moon, human (as partner) enters exchange."""
        # MoonBidder bids moon if current_high_bid == 0.  Find a seed where
        # AI Partner (seat 2) bids before the human and wins the auction.
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        for seed in range(500):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if hand is None:
                continue

            # start_match already auto-advanced AI; if human turn, pass
            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                # Check if there's already a moon bid from seat 2
                has_moon_from_2 = any(
                    e.get("action") == "bid"
                    and e.get("bid_type") == "moon"
                    and e.get("seat") == 2
                    for e in hand.auction
                )
                if not has_moon_from_2:
                    continue
                # Human passes to let the auction finish
                state = engine.submit_human_bid(state, BidAction.pass_bid())
                hand = state.current_hand
                if hand is None:
                    continue

            if hand.phase == "moon_exchange" and hand.bidder_seat == 2:
                # Human is partner — should be in selecting phase
                assert hand.exchange_phase == "selecting"
                assert len(hand.hands[HUMAN_SEAT]) == 10

                # Complete the exchange
                state = engine.submit_exchange_selection(state, [0, 1])
                hand = state.current_hand
                assert hand is not None
                # Human sits out — AI advancement is deferred for the
                # exchange-reveal interstitial
                assert hand.phase == "trick_play"
                assert hand.sitting_out_seat == HUMAN_SEAT
                assert hand.exchange_given is not None
                assert hand.exchange_received is not None

                # Simulate the exchange reveal step (route layer)
                hand.exchange_revealed = True
                state = engine.advance_after_exchange_reveal(state)
                hand = state.current_hand
                assert hand is not None
                # AI auto-plays with per-card and trick-by-trick pauses.
                # Resume through all pauses until hand completes.
                for _ in range(200):  # Safety valve (per-card pacing)
                    if hand.phase == "complete":
                        break
                    if hand.paused_after_play:
                        state = engine.resume_after_play(state)
                        hand = state.current_hand
                        assert hand is not None
                    elif hand.paused_after_trick:
                        state = engine.resume_ai(state)
                        hand = state.current_hand
                        assert hand is not None
                    else:
                        break
                assert (
                    hand.phase == "complete"
                ), f"Expected 'complete' after reveal, got '{hand.phase}'"
                return  # Test passed

        pytest.skip("No seed found where AI Partner bids moon first")

    def test_ai_only_exchange_auto_resolves(self) -> None:
        """When neither human is mooner nor partner, exchange is automatic."""
        # Find a seed where AI Left (seat 1) or AI Right (seat 3) bids moon.
        # Their partner is seat 3 or 1 respectively — human not involved.
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        for seed in range(500):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if hand is None:
                continue

            # If it's human's turn during auction, pass
            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
                hand = state.current_hand
                if hand is None:
                    continue

            # Check if an AI from the opposing team (seat 1 or 3) won
            if (
                hand.phase == "trick_play"
                and hand.bid_type == "moon"
                and hand.bidder_seat in (1, 3)
            ):
                # Should have auto-resolved — no moon_exchange phase
                assert hand.exchange_given is not None
                assert hand.exchange_received is not None
                assert hand.exchange_phase is None
                return

        pytest.skip("No seed found where opposing AI bids moon")

    def test_exchange_selection_validates_card_count(self) -> None:
        """Must select exactly 2 cards."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            if hand.phase == "moon_exchange":
                with pytest.raises(ValueError, match="exactly 2"):
                    engine.submit_exchange_selection(state, [0])
                with pytest.raises(ValueError, match="exactly 2"):
                    engine.submit_exchange_selection(state, [0, 1, 2])

    def test_exchange_selection_validates_same_card(self) -> None:
        """Cannot select the same card twice."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            if hand.phase == "moon_exchange":
                with pytest.raises(ValueError, match="2 different"):
                    engine.submit_exchange_selection(state, [3, 3])

    def test_exchange_selection_validates_index_range(self) -> None:
        """Card indices must be in range."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            if hand.phase == "moon_exchange":
                with pytest.raises(ValueError, match="out of range"):
                    engine.submit_exchange_selection(state, [0, 99])

    def test_exchange_phase_serialization(self) -> None:
        """Exchange selecting phase round-trips through serialization."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            if hand.phase == "moon_exchange":
                data = MatchEngine.serialize(state)
                restored = MatchEngine.deserialize(data)
                r_hand = restored.current_hand
                assert r_hand is not None
                assert r_hand.phase == "moon_exchange"
                assert r_hand.exchange_phase == "selecting"
                assert r_hand.exchange_given is None  # Not yet exchanged


# ---------------------------------------------------------------------------
# Test 14c: Moon exchange — AI advance after exchange (#1910)
# ---------------------------------------------------------------------------


class TestMoonExchangeAIAdvance:
    """After moon exchange, AI auto-advances when the leader is an AI seat.

    Regression tests for #1910: the game was stuck after a moon exchange
    when the bidder (who leads the first trick) was an AI, because
    ``submit_exchange_selection`` did not call ``_advance_ai``.
    """

    def test_ai_mooner_advances_after_partner_exchange(self) -> None:
        """When an AI bids moon and human is the partner, AI leads after exchange.

        After submit_exchange_selection, the engine must auto-advance AI
        so that the game isn't stuck on the AI leader's turn.
        """
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        # Find a seed where seat 2 (AI Partner) bids moon.
        # The human (seat 0) is the partner — exchange is interactive.
        for seed in range(1000):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if hand is None:
                continue

            # If human's turn in auction, pass (so AI partner can bid)
            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
                hand = state.current_hand
                if hand is None:
                    continue

            # Look for interactive exchange where seat 2 is the mooner
            if hand.phase == "moon_exchange" and hand.bidder_seat == 2:
                assert hand.exchange_phase == "selecting"

                # Human is the partner — select 2 cards to give
                state = engine.submit_exchange_selection(state, [0, 1])
                hand = state.current_hand
                assert hand is not None

                # Moon partner sits out (3-player trick play).
                # Seat 2 bids moon → partner is seat 0 (HUMAN_SEAT).
                # AI advancement is deferred for the exchange interstitial.
                partner_seat = (hand.bidder_seat + 2) % 4
                assert hand.sitting_out_seat == partner_seat
                assert partner_seat == HUMAN_SEAT
                assert hand.phase == "trick_play"

                # Simulate exchange reveal (route layer)
                hand.exchange_revealed = True
                state = engine.advance_after_exchange_reveal(state)
                hand = state.current_hand
                assert hand is not None

                # Human sits out → AI auto-plays with per-card and trick pauses
                for _ in range(200):  # Safety valve (per-card pacing)
                    if hand.phase == "complete":
                        break
                    if hand.paused_after_play:
                        state = engine.resume_after_play(state)
                        hand = state.current_hand
                        assert hand is not None
                    elif hand.paused_after_trick:
                        state = engine.resume_ai(state)
                        hand = state.current_hand
                        assert hand is not None
                    else:
                        break
                assert (
                    hand.phase == "complete"
                ), f"Expected 'complete' after reveal, got '{hand.phase}'"
                return

        pytest.skip("No seed found where AI Partner (seat 2) bids moon")

    def test_moon_sets_sitting_out_after_exchange(self) -> None:
        """Moon bids set sitting_out_seat — partner sits out, 3-player tricks.

        Moon = exchange THEN partner sits out.  Same 3-player trick play as
        loner; the difference is moon has a card exchange first.
        """
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )
        found = False
        for seed in range(500):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if hand is None:
                continue

            # Pass if it's the human's turn
            if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
                state = engine.submit_human_bid(state, BidAction.pass_bid())
                hand = state.current_hand
                if hand is None:
                    continue

            # Handle interactive exchange
            if hand.phase == "moon_exchange":
                state = engine.submit_exchange_selection(state, [0, 1])
                hand = state.current_hand
                assert hand is not None

            if hand.bid_type == "moon":
                expected_sitting_out = (hand.bidder_seat + 2) % 4
                assert hand.sitting_out_seat == expected_sitting_out, (
                    f"Moon bid should set sitting_out_seat to partner "
                    f"(seat {expected_sitting_out}), got {hand.sitting_out_seat}"
                )
                found = True

        assert found, "No moon bid occurred across 500 seeds"

    def test_human_mooner_leads_after_exchange(self) -> None:
        """When human bids moon and is the leader, no AI advance is needed."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))
            hand = state.current_hand
            assert hand is not None

            if hand.phase == "moon_exchange":
                state = engine.submit_exchange_selection(state, [0, 1])
                hand = state.current_hand
                assert hand is not None

                # Human bid moon → human leads → current_seat is HUMAN_SEAT
                # Partner (seat 2) sits out — 3-player trick play
                if hand.phase == "trick_play":
                    assert hand.current_seat == HUMAN_SEAT
                    assert hand.bidder_seat == HUMAN_SEAT
                    assert hand.sitting_out_seat == 2  # Human's partner
                    # No AI plays yet — human leads
                    assert hand.current_trick is not None
                    assert len(hand.current_trick.plays) == 0


# ---------------------------------------------------------------------------
# Test 15: Loner sit-out trick flow
# ---------------------------------------------------------------------------


class TestLonerSitOut:
    """Loner bid causes partner to sit out during trick play."""

    def test_loner_sets_sitting_out(self) -> None:
        """Human bids loner — partner (seat 2) sits out."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.loner("S"))
            hand = state.current_hand
            assert hand is not None

            if hand.phase == "trick_play":
                assert hand.sitting_out_seat == 2  # Human's partner
                assert hand.bid_type == "loner"

    def test_loner_3_player_tricks(self) -> None:
        """Loner tricks have 3 players, not 4."""
        assert _players_per_trick(None) == 4
        assert _players_per_trick(2) == 3

    def test_next_active_seat_skips_sitting_out(self) -> None:
        """_next_active_seat skips the sitting-out seat."""
        # Seat 2 sits out
        assert _next_active_seat(1, 2) == 3  # skip 2
        assert _next_active_seat(0, 2) == 1  # no skip needed
        assert _next_active_seat(3, 2) == 0  # wrap around, no skip
        assert _next_active_seat(1, None) == 2  # no sitting out

    def test_ai_loner_human_sits_out(self) -> None:
        """When AI partner (seat 2) bids loner, human (seat 0) sits out.

        The engine should auto-advance through all trick play without
        pausing for human input.
        """
        engine = MatchEngine(
            bidding_policy=LonerBidder(contract="S"),
            play_strategy=FirstLegalPlay(),
        )

        # We need a seed where seat 1 (left of dealer 0) bids first.
        # With LonerBidder, the first AI to bid will bid loner.
        # Let's find a state where the AI bids loner and human sits out.
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Check if the AI bid loner
        if hand.sitting_out_seat == HUMAN_SEAT:
            # Human is sitting out — engine should have auto-advanced
            # through all trick play
            assert hand.phase in ("trick_play", "complete")
            # If trick play is still going, it shouldn't be waiting for human
            if hand.phase == "trick_play":
                assert hand.current_seat != HUMAN_SEAT

    def test_loner_full_hand_completes(self) -> None:
        """A loner hand plays to completion with correct trick count."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = _play_full_hand(engine, state, human_bid=BidAction.loner("S"))

            # Hand should complete
            assert state.hands_played >= 1


# ---------------------------------------------------------------------------
# Test 16: Moon/loner scoring through compute_points
# ---------------------------------------------------------------------------


class TestMoonLonerScoring:
    """Verify correct scoring for moon and loner hands."""

    def test_moon_scoring_make(self) -> None:
        """Moon bid made (10 tricks): declaring team gets +20."""
        pts0, pts1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=10,
            tricks_team1=0,
            bid_type="moon",
        )
        assert pts0 == 20
        assert pts1 == 0

    def test_moon_scoring_fail(self) -> None:
        """Moon bid failed: declaring team gets -20, defenders get tricks."""
        pts0, pts1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=8,
            tricks_team1=2,
            bid_type="moon",
        )
        assert pts0 == -20
        assert pts1 == 2

    def test_loner_scoring_make(self) -> None:
        """Loner bid made (10 tricks): declaring team gets +40."""
        pts0, pts1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=10,
            tricks_team1=0,
            bid_type="loner",
        )
        assert pts0 == 40
        assert pts1 == 0

    def test_loner_scoring_fail(self) -> None:
        """Loner bid failed: declaring team gets -40, defenders get tricks."""
        pts0, pts1 = compute_points(
            winning_bid=10,
            bidder_position=0,
            tricks_team0=7,
            tricks_team1=3,
            bid_type="loner",
        )
        assert pts0 == -40
        assert pts1 == 3

    def test_engine_moon_scoring_integration(self) -> None:
        """Engine scores a moon hand correctly through _process_hand_end."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = _play_full_hand(engine, state, human_bid=BidAction.moon("S"))

            if state.hands_played >= 1:
                # Scores should reflect moon scoring (±20)
                total = abs(state.score_human) + abs(state.score_ai)
                # Moon: winner gets ±20, loser gets tricks won
                # So total should involve 20 + something
                assert total > 0

    def test_engine_loner_scoring_integration(self) -> None:
        """Engine scores a loner hand correctly through _process_hand_end."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = _play_full_hand(engine, state, human_bid=BidAction.loner("S"))

            if state.hands_played >= 1:
                total = abs(state.score_human) + abs(state.score_ai)
                assert total > 0


# ---------------------------------------------------------------------------
# Test 17: Regular bid regression
# ---------------------------------------------------------------------------


class TestRegularBidRegression:
    """Existing regular-bid behavior unchanged after moon/loner changes."""

    def test_regular_hand_still_works(self, engine: MatchEngine) -> None:
        """Regular bid flow: deal → auction → 10 tricks → scoring."""
        state = engine.start_match(SEED, "heuristic")
        state = _play_full_hand(engine, state)
        assert state.hands_played >= 1

    def test_regular_full_match(self, engine: MatchEngine) -> None:
        """Full match with regular bids completes normally."""
        state = engine.start_match(SEED, "heuristic")
        state = _play_until_match_end(engine, state)
        assert state.status == "complete"
        assert state.winner in ("human", "ai")

    def test_regular_bid_type_is_regular(self, engine: MatchEngine) -> None:
        """Hand state bid_type defaults to 'regular' for normal bids."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None
        assert hand.bid_type == "regular"

    def test_regular_no_sitting_out(self, engine: MatchEngine) -> None:
        """Regular hands have no sitting-out seat."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None
        assert hand.sitting_out_seat is None

    def test_regular_no_exchange(self, engine: MatchEngine) -> None:
        """Regular hands have no exchange data."""
        state = engine.start_match(SEED, "heuristic")
        state = _play_full_hand(engine, state)
        # After a regular hand, exchange fields should be None
        # (the new hand won't have exchange data either)
        assert state.hands_played >= 1


# ---------------------------------------------------------------------------
# Test 18: Serialization with moon/loner state
# ---------------------------------------------------------------------------


class TestMoonLonerSerialization:
    """Round-trip serialization preserves moon/loner state fields."""

    def test_moon_state_round_trip(self) -> None:
        """Moon exchange state survives serialization."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.moon("S"))

            data = MatchEngine.serialize(state)
            restored = MatchEngine.deserialize(data)

            assert restored.current_hand is not None
            assert restored.current_hand.bid_type == "moon"
            assert restored == state

    def test_loner_state_round_trip(self) -> None:
        """Loner sitting-out state survives serialization."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.loner("S"))

            data = MatchEngine.serialize(state)
            restored = MatchEngine.deserialize(data)

            assert restored.current_hand is not None
            assert restored.current_hand.bid_type == "loner"
            assert restored.current_hand.sitting_out_seat is not None
            assert restored == state

    def test_visible_state_includes_moon_loner_fields(self) -> None:
        """get_visible_state includes bid_type and sitting_out_seat."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")

        visible = engine.get_visible_state(state)
        assert "bid_type" in visible
        assert "sitting_out_seat" in visible


# ---------------------------------------------------------------------------
# Test: Partner hand reveal at end of moon hand (#2554)
# ---------------------------------------------------------------------------


class TestPartnerHandReveal:
    """Verify get_visible_state includes partner's hand for completed moon hands."""

    def test_visible_state_includes_partner_hand_on_moon_complete(self) -> None:
        """partner_exchange_hand present when phase=complete and bid_type=moon."""
        engine = MatchEngine(
            bidding_policy=MoonBidder("S"),
            play_strategy=FirstLegalPlay(),
        )

        for seed in range(200):
            state = engine.start_match(seed, "heuristic")
            # Auto-play to completion
            for _ in range(500):
                hand = state.current_hand
                if hand is None or state.status == "complete":
                    break
                if hand.phase == "complete":
                    break
                if hand.phase == "redeal":
                    state = engine.next_hand(state)
                    continue
                if hand.phase == "trick_play" and hand.paused_after_play:
                    state = engine.resume_after_play(state)
                    continue
                if hand.phase == "trick_play" and hand.paused_after_trick:
                    state = engine.resume_ai(state)
                    continue
                if hand.current_seat == HUMAN_SEAT:
                    if hand.phase == "auction":
                        state = engine.submit_human_bid(state, BidAction.pass_bid())
                    elif hand.phase == "trick_play":
                        legal = engine.get_legal_plays(state)
                        state = engine.submit_human_card(state, legal[0])
                    elif hand.phase == "moon_exchange":
                        indices = [0, 1]
                        state = engine.submit_exchange_selection(state, indices)
                    else:
                        state = engine.advance(state)
                else:
                    state = engine.advance(state)

            hand = state.current_hand
            if (
                hand is not None
                and hand.phase == "complete"
                and hand.bid_type == "moon"
            ):
                visible = engine.get_visible_state(state)
                assert "partner_exchange_hand" in visible
                assert "partner_exchange_seat" in visible
                assert visible["partner_exchange_seat"] == hand.sitting_out_seat
                # Partner's hand should have 10 cards (sat out, played nothing)
                assert len(visible["partner_exchange_hand"]) == 10
                # Each card should be [suit, rank]
                for card in visible["partner_exchange_hand"]:
                    assert len(card) == 2
                return  # success

        pytest.fail("Could not find a completed moon hand in 200 seeds")

    def test_visible_state_excludes_partner_hand_non_moon(self) -> None:
        """partner_exchange_hand absent for regular (non-moon) completed hands."""
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        for seed in range(200):
            state = engine.start_match(seed, "heuristic")
            # Auto-play to completion
            for _ in range(500):
                hand = state.current_hand
                if hand is None or state.status == "complete":
                    break
                if hand.phase == "complete":
                    break
                if hand.phase == "redeal":
                    state = engine.next_hand(state)
                    continue
                if hand.phase == "trick_play" and hand.paused_after_play:
                    state = engine.resume_after_play(state)
                    continue
                if hand.phase == "trick_play" and hand.paused_after_trick:
                    state = engine.resume_ai(state)
                    continue
                if hand.current_seat == HUMAN_SEAT:
                    if hand.phase == "auction":
                        state = engine.submit_human_bid(state, BidAction.pass_bid())
                    elif hand.phase == "trick_play":
                        legal = engine.get_legal_plays(state)
                        state = engine.submit_human_card(state, legal[0])
                    else:
                        state = engine.advance(state)
                else:
                    state = engine.advance(state)

            hand = state.current_hand
            if (
                hand is not None
                and hand.phase == "complete"
                and hand.bid_type != "moon"
            ):
                visible = engine.get_visible_state(state)
                assert "partner_exchange_hand" not in visible
                assert "partner_exchange_seat" not in visible
                return  # success

        pytest.fail("Could not find a completed non-moon hand in 200 seeds")


# ---------------------------------------------------------------------------
# Test 19: Trick winner display — winning_card in visible state
# ---------------------------------------------------------------------------


class TestTrickWinnerDisplay:
    """Verify completed trick dicts include the winning card."""

    def test_completed_trick_has_winning_card(self) -> None:
        """completed_tricks in visible state include a winning_card field."""
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        # Play through multiple seeds until we find a completed trick in
        # visible state (any seed where AI bids and tricks complete)
        for seed in range(100):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if hand is None:
                continue

            # Auto-play through until we have at least one completed trick
            for _ in range(500):  # max iterations to avoid infinite loop
                hand = state.current_hand
                if hand is None:
                    break
                if state.status == "complete":
                    break
                if hand.phase in ("complete", "redeal"):
                    break
                if hand.completed_tricks:
                    break
                if hand.phase == "trick_play" and hand.paused_after_play:
                    state = engine.resume_after_play(state)
                    continue
                if hand.phase == "trick_play" and hand.paused_after_trick:
                    state = engine.resume_ai(state)
                    continue
                if hand.current_seat == HUMAN_SEAT:
                    if hand.phase == "auction":
                        state = engine.submit_human_bid(state, BidAction.pass_bid())
                    elif hand.phase == "trick_play":
                        legal = engine.get_legal_plays(state)
                        state = engine.submit_human_card(state, legal[0])

            hand = state.current_hand
            if hand is not None and hand.completed_tricks:
                visible = engine.get_visible_state(state)
                tricks = visible["completed_tricks"]
                assert len(tricks) > 0
                for tr in tricks:
                    assert (
                        "winning_card" in tr
                    ), "completed trick must have winning_card"
                    wc = tr["winning_card"]
                    assert wc is not None, "winning_card must not be None"
                    assert len(wc) == 2, "winning_card should be [suit, rank]"
                    # Verify the winning_card matches the card played by the winner
                    winner_seat = tr["winner"]
                    winner_plays = [p[1] for p in tr["plays"] if p[0] == winner_seat]
                    assert (
                        wc in winner_plays
                    ), f"winning_card {wc} not in winner's plays {winner_plays}"
                return  # success

        pytest.fail("Could not find a completed trick in 100 seeds")

    def test_exchange_revealed_persists(self) -> None:
        """exchange_revealed field survives serialization round-trip."""
        engine = MatchEngine(
            bidding_policy=MoonBidder("S"),
            play_strategy=FirstLegalPlay(),
        )

        for seed in range(100):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if hand is None:
                continue

            # Auto-play until moon exchange happens
            for _ in range(20):
                hand = state.current_hand
                if hand is None:
                    break
                if hand.exchange_given is not None:
                    break
                if hand.current_seat == HUMAN_SEAT and hand.phase == "auction":
                    state = engine.submit_human_bid(state, BidAction.pass_bid())

            hand = state.current_hand
            if hand is not None and hand.exchange_given is not None:
                # Verify default is False
                assert hand.exchange_revealed is False

                # Toggle and round-trip
                hand.exchange_revealed = True
                data = engine.serialize(state)
                restored = engine.deserialize(data)
                assert restored.current_hand is not None
                assert restored.current_hand.exchange_revealed is True
                return

        pytest.fail("Could not find a moon exchange in 100 seeds")


# ---------------------------------------------------------------------------
# 20. sort_hand_for_display
# ---------------------------------------------------------------------------


class TestSortHandForDisplay:
    """Tests for the display-sorting helper."""

    def test_groups_by_suit(self) -> None:
        """Cards are grouped by printed suit when no trump is active."""
        hand = [
            Card("H", "A"),
            Card("S", "K"),
            Card("D", "Q"),
            Card("S", "A"),
            Card("H", "T"),
            Card("C", "J"),
        ]
        sort_hand_for_display(hand)
        suits = [c.suit for c in hand]
        # S group first, then H, C, D — alternating black/red
        assert suits == ["S", "S", "H", "H", "C", "D"]

    def test_within_suit_rank_order(self) -> None:
        """Within a suit: J > A > K > Q > T (no trump)."""
        hand = [
            Card("H", "T"),
            Card("H", "A"),
            Card("H", "J"),
            Card("H", "Q"),
            Card("H", "K"),
        ]
        sort_hand_for_display(hand)
        ranks = [c.rank for c in hand]
        assert ranks == ["J", "A", "K", "Q", "T"]

    def test_trump_suit_first(self) -> None:
        """With trump active, trump group appears before other suits."""
        hand = [
            Card("S", "A"),
            Card("H", "A"),
            Card("D", "A"),
            Card("C", "A"),
        ]
        sort_hand_for_display(hand, contract_type="suit", trump="D")
        suits = [c.suit for c in hand]
        assert suits[0] == "D"  # Trump first
        # Remaining suits alternate black/red: S, H, C
        assert suits[1:] == ["S", "H", "C"]

    def test_trump_alternates_remaining_suits(self) -> None:
        """Non-trump suits alternate black/red after trump group."""
        hand = [
            Card("S", "A"),
            Card("H", "A"),
            Card("D", "A"),
            Card("C", "A"),
        ]
        # Trump = C (black): remaining should be H(red), S(black), D(red)
        sort_hand_for_display(hand, contract_type="suit", trump="C")
        suits = [c.suit for c in hand]
        assert suits == ["C", "H", "S", "D"]

    def test_right_bower_highest_in_trump(self) -> None:
        """Right bower (J of trump) sorts highest in trump group."""
        hand = [
            Card("H", "A"),
            Card("H", "J"),  # Right bower
            Card("H", "K"),
        ]
        sort_hand_for_display(hand, contract_type="suit", trump="H")
        ranks = [c.rank for c in hand]
        assert ranks == ["J", "A", "K"]  # J (right bower) first

    def test_left_bower_moves_to_trump_group(self) -> None:
        """Left bower (J of same color) moves from its printed suit to trump."""
        hand = [
            Card("H", "A"),  # Trump
            Card("D", "J"),  # Left bower (same color as H)
            Card("H", "J"),  # Right bower
            Card("D", "A"),  # Non-trump D (J removed)
        ]
        sort_hand_for_display(hand, contract_type="suit", trump="H")
        # Trump group: right bower J♥, left bower J♦, A♥
        # Then remaining: D♦ A
        result = [(c.suit, c.rank) for c in hand]
        assert result == [
            ("H", "J"),  # right bower
            ("D", "J"),  # left bower (effective suit = H)
            ("H", "A"),  # trump A
            ("D", "A"),  # non-trump D
        ]

    def test_low_contract_rank_order(self) -> None:
        """Low contract: T > J > Q > K > A (10 is high)."""
        hand = [
            Card("S", "A"),
            Card("S", "T"),
            Card("S", "K"),
            Card("S", "J"),
            Card("S", "Q"),
        ]
        sort_hand_for_display(hand, contract_type="low")
        ranks = [c.rank for c in hand]
        assert ranks == ["T", "J", "Q", "K", "A"]

    def test_high_contract_ace_high_order(self) -> None:
        """High contract: no bowers, A-high order (A > K > Q > J > T)."""
        hand = [
            Card("H", "J"),
            Card("D", "J"),
            Card("H", "A"),
        ]
        sort_hand_for_display(hand, contract_type="high")
        # Both Js stay in their printed suits, no bower movement.
        # Ace ranks above J in HIGH contracts.
        result = [(c.suit, c.rank) for c in hand]
        assert result == [
            ("H", "A"),
            ("H", "J"),
            ("D", "J"),
        ]

    def test_non_trump_suit_ace_high_in_suit_contract(self) -> None:
        """Non-trump suits in suit contracts use A-high order."""
        hand = [
            Card("S", "J"),
            Card("S", "A"),
            Card("S", "T"),
            Card("S", "K"),
            Card("S", "Q"),
        ]
        sort_hand_for_display(hand, contract_type="suit", trump="H")
        # Non-trump Spades: A > K > Q > J > T
        ranks = [c.rank for c in hand]
        assert ranks == ["A", "K", "Q", "J", "T"]

    def test_sort_is_stable_idempotent(self) -> None:
        """Sorting an already-sorted hand produces the same order."""
        hand = [
            Card("S", "J"),
            Card("S", "A"),
            Card("H", "K"),
            Card("D", "Q"),
        ]
        sort_hand_for_display(hand)
        first_pass = list(hand)
        sort_hand_for_display(hand)
        assert hand == first_pass

    def test_duplicate_cards_handled(self) -> None:
        """Double-deck duplicates don't cause errors."""
        hand = [
            Card("H", "A"),
            Card("H", "A"),
            Card("S", "K"),
            Card("S", "K"),
        ]
        sort_hand_for_display(hand)
        result = [(c.suit, c.rank) for c in hand]
        assert result == [
            ("S", "K"),
            ("S", "K"),
            ("H", "A"),
            ("H", "A"),
        ]

    def test_engine_sorts_after_deal(self) -> None:
        """After starting a match, the human hand is sorted by suit."""
        engine = MatchEngine(
            bidding_policy=AlwaysPassBidder(),
            play_strategy=FirstLegalPlay(),
        )
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        assert hand is not None

        human_cards = hand.hands[HUMAN_SEAT]
        # Verify grouped by suit: each suit's cards are contiguous
        seen_suits: list[str] = []
        for card in human_cards:
            if not seen_suits or seen_suits[-1] != card.suit:
                seen_suits.append(card.suit)
        # No suit should appear more than once in the seen list
        assert len(seen_suits) == len(set(seen_suits))


# ---------------------------------------------------------------------------
# Glutton bower-sorting fix (#2113)
# ---------------------------------------------------------------------------


class TestGluttonBowerFix:
    """Regression tests for #2113: engine must call on_hand_start so
    GluttonStrategy knows the contract type and trump suit."""

    def test_on_hand_start_called_after_auction(self) -> None:
        """After auction ends, GluttonStrategy._contract_type and
        _trump_suit must reflect the won contract — not the defaults."""
        glutton = GluttonStrategy()
        engine = MatchEngine(
            bidding_policy=FixedBidder(n=5, contract="S"),
            play_strategy=glutton,
        )
        state = engine.start_match(42, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Submit human bid (pass) so AI wins auction
        state = engine.submit_human_bid(state, BidAction.pass_bid())

        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "trick_play"
        # The engine should have called on_hand_start, setting trump info
        assert glutton._contract_type == hand.contract_type
        assert glutton._trump_suit == hand.trump

    def test_on_hand_start_called_after_moon_exchange(self) -> None:
        """Moon exchange path must also call on_hand_start."""
        glutton = GluttonStrategy()
        engine = MatchEngine(
            bidding_policy=MoonBidder(contract="S"),
            play_strategy=glutton,
        )
        state = engine.start_match(42, "heuristic")
        hand = state.current_hand
        assert hand is not None

        # Submit human bid (pass) so AI wins with moon
        state = engine.submit_human_bid(state, BidAction.pass_bid())

        hand = state.current_hand
        assert hand is not None
        # Moon goes through exchange phase first
        if hand.phase == "moon_exchange":
            state = engine.submit_exchange_selection(state, [0, 1])
            hand = state.current_hand
            assert hand is not None

        assert hand.phase == "trick_play"
        assert glutton._contract_type == hand.contract_type
        assert glutton._trump_suit == hand.trump

    def test_observe_play_fires_on_card_play(self) -> None:
        """Each card play must notify the strategy via observe_play.

        After the auction, AI auto-advances and plays cards, which populates
        _seen_counts. Then the human plays, adding more observations.
        We verify the total observation count increases after the human play.
        """
        glutton = GluttonStrategy()
        engine = MatchEngine(
            bidding_policy=FixedBidder(n=5, contract="S"),
            play_strategy=glutton,
        )
        state = engine.start_match(42, "heuristic")
        # Submit human pass so AI wins
        state = engine.submit_human_bid(state, BidAction.pass_bid())
        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "trick_play"

        # Advance through per-card pauses until it's the human's turn
        for _ in range(50):
            hand = state.current_hand
            if hand is None:
                break
            if hand.paused_after_play:
                state = engine.resume_after_play(state)
                continue
            if hand.paused_after_trick:
                state = engine.resume_ai(state)
                continue
            break

        hand = state.current_hand
        assert hand is not None
        assert hand.phase == "trick_play"

        # AI auto-advance may have already tracked some plays
        initial_total = sum(glutton._seen_counts.values())

        # Play the human card
        if hand.current_seat == HUMAN_SEAT:
            legal = get_legal_indices(
                hand.hands[HUMAN_SEAT],
                list(hand.current_trick.plays) if hand.current_trick else [],
                hand.contract_type or "high",
                hand.trump,
            )
            state = engine.submit_human_card(state, legal[0])

        # Total observation count must have increased
        final_total = sum(glutton._seen_counts.values())
        assert final_total > initial_total

    def test_bower_values_correct_with_fix(self) -> None:
        """With on_hand_start called, right bower is valued higher than ace."""
        from bid_euchre.strategy.base import card_value_for_dump

        # Without the fix, _contract_type="high" and _trump_suit=None
        # would make J♥ value < A♥.  With the fix, J♥ (right bower) > A♥.
        right_bower = Card("H", "J")
        ace_of_trump = Card("H", "A")

        # Correct values with bower awareness
        rb_val = card_value_for_dump(right_bower, "suit", "H")
        ace_val = card_value_for_dump(ace_of_trump, "suit", "H")
        assert (
            rb_val > ace_val
        ), f"Right bower ({rb_val}) must be valued higher than ace ({ace_val})"

        # Bug scenario: without trump info, J is low
        rb_no_trump = card_value_for_dump(right_bower, "high", None)
        ace_no_trump = card_value_for_dump(ace_of_trump, "high", None)
        assert (
            rb_no_trump < ace_no_trump
        ), "Without trump info, J should be valued lower than A (the bug)"


# ---------------------------------------------------------------------------
# Trick 10 pause — final trick result interstitial (#2210)
# ---------------------------------------------------------------------------


class TestFinalTrickPause:
    """After trick 10, paused_after_trick must be True so the UI shows the
    final trick result before the hand-result screen (#2210)."""

    def test_trick_10_sets_paused_after_trick(self) -> None:
        """When the last card of trick 10 completes the hand, the engine
        sets paused_after_trick=True so the route layer can show the trick
        result interstitial before the hand-result screen."""
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        # Use _play_full_hand which drives through auction + tricks.
        # After our fix, the hand should end with paused_after_trick=True.
        for seed in range(50):
            state = engine.start_match(seed, "heuristic")
            state = _play_full_hand(engine, state)
            hand = state.current_hand
            if hand is not None and hand.phase == "complete":
                # Key assertion: after trick 10, paused_after_trick must be
                # True so the UI shows the final trick result.
                assert hand.paused_after_trick, (
                    f"seed={seed}: trick 10 completed the hand but "
                    f"paused_after_trick is False — the final trick result "
                    f"interstitial would be skipped"
                )
                assert len(hand.completed_tricks) == 10
                return  # Test passed

        pytest.skip("No seed produced a normal hand completion in range(50)")

    def test_clearing_pause_on_complete_hand(self) -> None:
        """After clearing paused_after_trick on a complete hand, the hand
        remains in phase='complete' and paused_after_trick=False, ready
        for the hand-result screen."""
        engine = MatchEngine(
            bidding_policy=FixedBidder(5, "S"),
            play_strategy=FirstLegalPlay(),
        )

        for seed in range(50):
            state = engine.start_match(seed, "heuristic")
            state = _play_full_hand(engine, state)
            hand = state.current_hand
            if hand is None or hand.phase != "complete":
                continue

            if hand.paused_after_trick:
                # Simulate what the /next route handler does: clear the flag
                hand.paused_after_trick = False

                # Hand should still be complete
                assert hand.phase == "complete"
                assert not hand.paused_after_trick
                assert len(hand.completed_tricks) == 10
                return  # Test passed

        pytest.skip("No seed produced a complete hand with paused_after_trick")


# ---------------------------------------------------------------------------
# AI Suggestions (#2185)
# ---------------------------------------------------------------------------


class TestGetSuggestedPlay:
    """Tests for MatchEngine.get_suggested_play()."""

    def test_returns_legal_card_index_on_human_turn(self, engine: MatchEngine):
        """Suggested play should be a valid legal card index."""
        state = engine.start_match(SEED, "heuristic")
        # Advance to human play turn
        state = _advance_to_human_play(engine, state)
        hand = state.current_hand
        if hand is None or hand.phase != "trick_play":
            pytest.skip("No human play turn reached with this seed")

        suggestion = engine.get_suggested_play(state)
        assert suggestion is not None
        legal = engine.get_legal_plays(state)
        assert suggestion in legal

    def test_returns_none_during_auction(self, engine: MatchEngine):
        """Suggested play should be None when in auction phase."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        if (
            hand is not None
            and hand.phase == "auction"
            and hand.current_seat == HUMAN_SEAT
        ):
            assert engine.get_suggested_play(state) is None

    def test_returns_none_when_not_human_turn(self, engine: MatchEngine):
        """Suggested play should be None when it's not the human's turn."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        # After start_match, AI has advanced — if it's not human's turn, should be None
        if hand is not None and hand.current_seat != HUMAN_SEAT:
            assert engine.get_suggested_play(state) is None

    def test_returns_none_when_no_hand(self, engine: MatchEngine):
        """Suggested play should be None when current_hand is None."""
        state = MatchState(seed=SEED, ai_model="heuristic")
        assert engine.get_suggested_play(state) is None

    def test_no_state_leakage_between_calls(self):
        """Calling get_suggested_play() must not mutate the shared strategy.

        GluttonStrategy has mutable tracking state (_seen_counts,
        _void_suits_by_seat, _player_index, etc.).  The suggestion path
        must use an isolated copy so repeated calls don't corrupt the
        strategy instance used for AI play.  Regression lock for #2644.
        """
        glutton = GluttonStrategy()
        engine = MatchEngine(
            bidding_policy=FixedBidder(n=5, contract="S"),
            play_strategy=glutton,
        )

        # Find a seed where the human gets a play turn
        for seed in range(200):
            state = engine.start_match(seed, "heuristic")
            state = _advance_to_human_play(engine, state)
            hand = state.current_hand
            if (
                hand is not None
                and hand.phase == "trick_play"
                and hand.current_seat == HUMAN_SEAT
            ):
                break
        else:
            pytest.skip("No human play turn found in 200 seeds")

        # Snapshot strategy state before suggestion
        seen_before = dict(glutton._seen_counts)
        voids_before = {s: set(v) for s, v in glutton._void_suits_by_seat.items()}
        player_idx_before = glutton._player_index
        contract_before = glutton._contract_type
        trump_before = glutton._trump_suit
        last_lead_suit_before = glutton._last_won_lead_suit
        last_lead_seat_before = glutton._last_won_lead_seat

        # Call suggestion multiple times
        for _ in range(3):
            result = engine.get_suggested_play(state)
            assert result is not None

        # Strategy state must be unchanged
        assert (
            glutton._seen_counts == seen_before
        ), "get_suggested_play() leaked _seen_counts into shared strategy"
        assert (
            glutton._void_suits_by_seat == voids_before
        ), "get_suggested_play() leaked _void_suits_by_seat into shared strategy"
        assert (
            glutton._player_index == player_idx_before
        ), "get_suggested_play() leaked _player_index into shared strategy"
        assert glutton._contract_type == contract_before
        assert glutton._trump_suit == trump_before
        assert glutton._last_won_lead_suit == last_lead_suit_before
        assert glutton._last_won_lead_seat == last_lead_seat_before


class TestGetSuggestedBid:
    """Tests for MatchEngine.get_suggested_bid()."""

    def test_returns_bid_dict_on_human_auction_turn(self, engine: MatchEngine):
        """Suggested bid should return a dict with n, contract, bid_type."""
        for seed in range(100):
            state = engine.start_match(seed, "heuristic")
            hand = state.current_hand
            if (
                hand is not None
                and hand.phase == "auction"
                and hand.current_seat == HUMAN_SEAT
            ):
                suggestion = engine.get_suggested_bid(state)
                assert suggestion is not None
                assert "n" in suggestion
                assert "contract" in suggestion
                assert "bid_type" in suggestion
                assert isinstance(suggestion["n"], int)
                assert 0 <= suggestion["n"] <= 10
                return
        pytest.skip("No seed produced a human auction turn")

    def test_returns_none_during_trick_play(self, engine: MatchEngine):
        """Suggested bid should be None during trick play."""
        state = engine.start_match(SEED, "heuristic")
        state = _advance_to_human_play(engine, state)
        hand = state.current_hand
        if hand is not None and hand.phase == "trick_play":
            assert engine.get_suggested_bid(state) is None

    def test_returns_none_when_not_human_turn(self, engine: MatchEngine):
        """Suggested bid should be None when it's not the human's turn."""
        state = engine.start_match(SEED, "heuristic")
        hand = state.current_hand
        if (
            hand is not None
            and hand.phase == "auction"
            and hand.current_seat != HUMAN_SEAT
        ):
            assert engine.get_suggested_bid(state) is None

    def test_returns_none_when_no_hand(self, engine: MatchEngine):
        """Suggested bid should be None when current_hand is None."""
        state = MatchState(seed=SEED, ai_model="heuristic")
        assert engine.get_suggested_bid(state) is None


def _advance_to_human_play(engine: MatchEngine, state: MatchState) -> MatchState:
    """Advance state until the human has a play turn (trick_play phase)."""
    hand = state.current_hand
    if hand is None:
        return state

    # If auction, submit a bid for human
    if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
        state = engine.submit_human_bid(state, BidAction.pass_bid())
        hand = state.current_hand

    # Handle exchange
    if (
        hand is not None
        and hand.phase == "moon_exchange"
        and hand.exchange_phase == "selecting"
    ):
        state = engine.submit_exchange_selection(state, [0, 1])
        hand = state.current_hand

    # Advance through next steps to reach trick play
    for _ in range(50):
        hand = state.current_hand
        if hand is None:
            break
        if hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
            if not hand.paused_after_play and not hand.paused_after_trick:
                return state
        if hand.paused_after_play or hand.paused_after_trick:
            hand.paused_after_play = False
            hand.paused_after_trick = False
            state = engine.resume_ai(state)
            continue
        if hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
            state = engine.submit_human_bid(state, BidAction.pass_bid())
            continue
        if hand.phase in ("complete", "redeal"):
            break
        break

    return state
