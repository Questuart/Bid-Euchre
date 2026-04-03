"""Simulation vs browser-game MatchEngine parity tests.

Verifies that the sim path (``sim/simulation.py::play_single_hand``) and the
hosted-play path (``hosted_play/engine.py::MatchEngine``) produce **identical
AI card-play decisions** given the same hands, contract, and strategy.

Phase 1 — forced-contract parity (no auction divergence):
  Feed identical pre-dealt hands + fixed contract into both paths via a
  ``FixedBidder`` auction, then compare every card play.

Addresses: #2229
Analyst plan: plans/sessions/2026-04-03_sim_browser_parity_plan.md
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import trick_winner
from bid_euchre.hosted_play.engine import HUMAN_SEAT, MatchEngine
from bid_euchre.hosted_play.state import HandState, MatchState
from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import BidAction, FixedBidder
from bid_euchre.strategy.greedy import GluttonStrategy

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PlayRecord:
    """One card play within a trick."""

    trick_num: int
    play_order: int  # 0-based within the trick
    seat: int
    card_suit: str
    card_rank: str

    def __repr__(self) -> str:
        return f"T{self.trick_num}P{self.play_order}:seat{self.seat}={self.card_rank}{self.card_suit}"


@dataclass
class HandResult:
    """Aggregated outcome from one hand."""

    plays: list[PlayRecord] = field(default_factory=list)
    trick_winners: list[int] = field(default_factory=list)
    tricks_team0: int = 0
    tricks_team1: int = 0


# ---------------------------------------------------------------------------
# Decision-capturing strategy wrapper
# ---------------------------------------------------------------------------


class DecisionCapture(Strategy):
    """Transparent wrapper that records every ``choose_card`` decision.

    Delegates ``choose_card``, ``on_hand_start``, and ``observe_play`` to the
    wrapped *inner* strategy so that card-tracking state is maintained
    identically.
    """

    def __init__(self, inner: Strategy) -> None:
        super().__init__(inner.name + "_capture")
        self.inner = inner
        self.records: list[PlayRecord] = []
        self._trick_num = 0

    def choose_card(
        self,
        hand: list[Card],
        plays_so_far: list[tuple[int, Card]],
        contract_type: str,
        trump_suit: str | None,
        player_index: int,
    ) -> int:
        idx = self.inner.choose_card(
            hand, plays_so_far, contract_type, trump_suit, player_index
        )
        card = hand[idx]
        play_order = len(plays_so_far)
        # Detect new trick: play_order == 0 after at least one play recorded
        if play_order == 0 and self.records:
            self._trick_num += 1
        self.records.append(
            PlayRecord(
                trick_num=self._trick_num,
                play_order=play_order,
                seat=player_index,
                card_suit=card.suit,
                card_rank=card.rank,
            )
        )
        return idx

    def on_hand_start(
        self,
        starting_hand: list[Card],
        contract_type: str,
        trump_suit: str | None,
        player_index: int,
    ) -> None:
        self.inner.on_hand_start(starting_hand, contract_type, trump_suit, player_index)

    def observe_play(
        self,
        player_index: int,
        card: Card,
        trick_plays: list[tuple[int, Card]],
        contract_type: str,
        trump_suit: str | None,
    ) -> None:
        self.inner.observe_play(
            player_index, card, trick_plays, contract_type, trump_suit
        )


# ---------------------------------------------------------------------------
# Sim-path runner
# ---------------------------------------------------------------------------


def _run_sim_hand(
    hands: list[list[Card]],
    contract_type: str,
    trump: str | None,
    bidder_seat: int,
) -> HandResult:
    """Play one hand through the sim path and capture every play.

    Uses a fresh ``GluttonStrategy`` wrapped in ``DecisionCapture``.
    The *bidder_seat* becomes the initial leader (who leads the first trick).
    """
    glutton = GluttonStrategy()
    capture = DecisionCapture(glutton)

    result = play_single_hand(
        contract_type=contract_type,
        trump_suit=trump,
        strategies=[capture, capture, capture, capture],
        hands=[list(h) for h in hands],
        initial_leader=bidder_seat,
    )
    t0, t1 = result[0], result[1]

    # Extract trick winners from the completed plays
    trick_winners = _extract_trick_winners(capture.records, contract_type, trump)

    return HandResult(
        plays=capture.records,
        trick_winners=trick_winners,
        tricks_team0=t0,
        tricks_team1=t1,
    )


def _extract_trick_winners(
    records: list[PlayRecord],
    contract_type: str,
    trump: str | None,
) -> list[int]:
    """Reconstruct trick winners from a play sequence."""
    winners: list[int] = []
    trick_plays: list[tuple[int, Card]] = []
    current_trick = 0

    for rec in records:
        if rec.trick_num != current_trick:
            # Previous trick complete — resolve winner
            if trick_plays:
                w = trick_winner(trick_plays, contract_type, trump)
                winners.append(w)
            trick_plays = []
            current_trick = rec.trick_num
        trick_plays.append((rec.seat, Card(suit=rec.card_suit, rank=rec.card_rank)))

    # Last trick
    if trick_plays:
        w = trick_winner(trick_plays, contract_type, trump)
        winners.append(w)

    return winners


# ---------------------------------------------------------------------------
# Engine-path runner (AllAIMatchHarness)
# ---------------------------------------------------------------------------


def _run_engine_hand(
    hands: list[list[Card]],
    contract_type: str,
    trump: str | None,
    bidder_seat: int,
) -> HandResult:
    """Play one hand through the MatchEngine path and capture every play.

    Uses a ``FixedBidder`` to ensure *bidder_seat* wins the auction with the
    target contract.  The human seat (0) is driven programmatically with
    the **same** ``GluttonStrategy`` instance used by the engine so that
    card-tracking state (``observe_play``) is shared — matching the sim's
    shared-instance model.

    The harness captures AI plays from ``engine.last_ai_events`` and human
    plays from the direct ``choose_card`` calls.
    """
    # Build the bidding contract string
    if contract_type == "suit":
        assert trump is not None
        bid_contract = trump  # "S", "H", "D", "C"
    elif contract_type == "high":
        bid_contract = "HIGH"
    else:
        bid_contract = "LOW"

    bidder = FixedBidder(10, bid_contract)
    glutton = GluttonStrategy()
    engine = MatchEngine(bidding_policy=bidder, play_strategy=glutton)

    # We need to control the dealer so that the desired bidder_seat wins.
    # bid_order(dealer) = [(dealer+1)%4, (dealer+2)%4, (dealer+3)%4, dealer].
    # FixedBidder(10, ...) will win at the first seat that bids (first in order).
    # We want first bidder = bidder_seat, so dealer = (bidder_seat - 1) % 4.
    dealer_seat = (bidder_seat - 1) % 4

    # Manually build the initial match state with our specific hands and dealer.
    state = MatchState(seed=0, ai_model="parity_test")
    state.dealer_seat = dealer_seat

    # Keep the original unsorted human hand.  MatchEngine sorts for display
    # (``sort_hand_for_display``), which changes index-order tie-breaking in
    # ``_choose_lead``.  Restoring the unsorted hand after auction ensures
    # the harness matches the sim path where hands are never sorted.
    unsorted_human_hand = list(hands[HUMAN_SEAT])

    # Build HandState with our injected hands
    first_bidder_seat = bidder_seat  # = (dealer_seat + 1) % 4
    hand_state = HandState(
        phase="auction",
        hands=[list(h) for h in hands],
        dealer_seat=dealer_seat,
        deal_id=0,
        current_seat=first_bidder_seat,
        turn_number=0,
    )
    state.current_hand = hand_state

    # Sort human hand for display (MatchEngine does this in _deal_new_hand).
    # This is required for the auction to work correctly, but we'll restore
    # the unsorted hand after the auction ends.
    from bid_euchre.hosted_play.engine import sort_hand_for_display

    sort_hand_for_display(hand_state.hands[HUMAN_SEAT])

    # Advance AI through the auction (AI seats bid before human gets a turn,
    # or human bids first if human is the first bidder).
    engine.last_ai_events = []
    state = engine._advance_ai(state)
    _restore_unsorted = True  # Flag: restore human hand once trick_play begins

    # Collect all plays
    plays: list[PlayRecord] = []
    trick_num = 0
    last_completed_count = 0

    # Drive the hand to completion
    max_iterations = 200  # Safety valve
    for _ in range(max_iterations):
        hand = state.current_hand
        if hand is None:
            break
        if hand.phase in ("complete", "redeal"):
            break
        if state.status == "complete":
            break

        # Restore unsorted human hand once trick play begins.
        # MatchEngine sorts the hand during _process_auction_end, which
        # alters tie-breaking order in _choose_lead.  The sim never sorts,
        # so we restore the original deal order to match.  The card SET is
        # identical — only the element order differs.
        if _restore_unsorted and hand.phase == "trick_play":
            # Rebuild the human hand in original deal order.
            # The card SET is identical to the sorted version — only order differs.
            # Handle double-deck duplicates by consuming from remaining_list.
            restored_checked: list[Card] = []
            remaining_list = list(hand.hands[HUMAN_SEAT])
            for c in unsorted_human_hand:
                for i, rc in enumerate(remaining_list):
                    if rc.suit == c.suit and rc.rank == c.rank:
                        restored_checked.append(c)
                        remaining_list.pop(i)
                        break
            hand.hands[HUMAN_SEAT] = restored_checked
            _restore_unsorted = False

        if hand.current_seat == HUMAN_SEAT:
            if hand.phase == "auction":
                if bidder_seat == HUMAN_SEAT:
                    # Human IS the intended bidder — bid high to win the auction
                    state = engine.submit_human_bid(
                        state, BidAction.bid(10, bid_contract)
                    )
                else:
                    # Human is NOT the bidder — pass
                    state = engine.submit_human_bid(state, BidAction.pass_bid())
            elif hand.phase == "trick_play":
                assert hand.current_trick is not None
                assert hand.contract_type is not None
                # Drive human with the engine's own glutton (shared instance)
                card_idx = glutton.choose_card(
                    hand.hands[HUMAN_SEAT],
                    hand.current_trick.plays,
                    hand.contract_type,
                    hand.trump,
                    HUMAN_SEAT,
                )
                card = hand.hands[HUMAN_SEAT][card_idx]
                play_order = len(hand.current_trick.plays)
                plays.append(
                    PlayRecord(
                        trick_num=trick_num,
                        play_order=play_order,
                        seat=HUMAN_SEAT,
                        card_suit=card.suit,
                        card_rank=card.rank,
                    )
                )
                state = engine.submit_human_card(state, card_idx)
            elif hand.phase == "moon_exchange":
                # Phase 1 does not cover moon — skip
                raise AssertionError("Unexpected moon_exchange in forced-contract test")
            else:
                break  # Unexpected phase
        elif hand.paused_after_trick:
            state = engine.resume_ai(state)
        else:
            # Shouldn't reach here in normal flow
            break

        engine.last_ai_events = []

        # Track trick completions for numbering
        hand_after = state.current_hand
        if hand_after is not None:
            new_completed = len(hand_after.completed_tricks)
            if new_completed > last_completed_count:
                trick_num = new_completed
                last_completed_count = new_completed

    # Extract all plays from completed tricks
    hand_final = state.current_hand
    if hand_final is None:
        return HandResult()

    engine_plays: list[PlayRecord] = []
    for t_idx, tr in enumerate(hand_final.completed_tricks):
        for p_idx, (seat, card) in enumerate(tr.plays):
            engine_plays.append(
                PlayRecord(
                    trick_num=t_idx,
                    play_order=p_idx,
                    seat=seat,
                    card_suit=card.suit,
                    card_rank=card.rank,
                )
            )

    trick_winners = [tr.winner for tr in hand_final.completed_tricks]

    return HandResult(
        plays=engine_plays,
        trick_winners=trick_winners,
        tricks_team0=hand_final.tricks_team0,
        tricks_team1=hand_final.tricks_team1,
    )


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------


def _first_divergence(
    sim_plays: list[PlayRecord], engine_plays: list[PlayRecord]
) -> str | None:
    """Return a human-readable description of the first divergence, or None."""
    min_len = min(len(sim_plays), len(engine_plays))
    for i in range(min_len):
        sp, ep = sim_plays[i], engine_plays[i]
        if (sp.trick_num, sp.play_order, sp.seat) != (
            ep.trick_num,
            ep.play_order,
            ep.seat,
        ):
            return (
                f"Play {i}: structure mismatch — "
                f"sim=({sp.trick_num},{sp.play_order},seat{sp.seat}) "
                f"vs engine=({ep.trick_num},{ep.play_order},seat{ep.seat})"
            )
        if (sp.card_suit, sp.card_rank) != (ep.card_suit, ep.card_rank):
            return (
                f"Play {i} (trick {sp.trick_num}, order {sp.play_order}, seat {sp.seat}): "
                f"card mismatch — sim={sp.card_rank}{sp.card_suit} "
                f"vs engine={ep.card_rank}{ep.card_suit}"
            )
    if len(sim_plays) != len(engine_plays):
        return f"Length mismatch: sim={len(sim_plays)} vs engine={len(engine_plays)}"
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# Seeds chosen for variety; 3 seeds × 6 contracts × N deals each
_SEEDS = [42, 137, 2718]
_DEALS_PER_COMBO = 10  # 10 deals per (seed, contract) — 180 total forced-contract hands


@pytest.mark.integration
class TestSimBrowserParity:
    """Verify simulation and MatchEngine produce identical AI decisions."""

    @pytest.mark.parametrize(
        "contract_type,trump",
        [
            ("suit", "S"),
            ("suit", "H"),
            ("suit", "D"),
            ("suit", "C"),
            ("high", None),
            ("low", None),
        ],
    )
    @pytest.mark.parametrize("seed", _SEEDS)
    def test_forced_contract_parity(
        self,
        seed: int,
        contract_type: str,
        trump: str | None,
    ) -> None:
        """Same hands + same contract → identical card plays across both paths.

        For each deal:
        1. Generate hands deterministically from (seed, deal_id).
        2. Run through sim with forced contract and GluttonStrategy at all 4 seats.
        3. Run through MatchEngine with FixedBidder auction and GluttonStrategy.
        4. Compare every card play by (trick, position, seat, card).
        """
        # Use seat 1 as the bidder/leader for all deals.  This means:
        # - Sim: initial_leader=1
        # - Engine: dealer=0, first bidder=seat 1, FixedBidder wins at seat 1
        bidder_seat = 1

        for deal_id in range(_DEALS_PER_COMBO):
            hands = generate_deal(seed, deal_id)

            sim_result = _run_sim_hand(hands, contract_type, trump, bidder_seat)
            engine_result = _run_engine_hand(hands, contract_type, trump, bidder_seat)

            # Compare trick counts
            assert sim_result.tricks_team0 == engine_result.tricks_team0, (
                f"Team 0 tricks mismatch: seed={seed} deal={deal_id} "
                f"contract={contract_type} trump={trump} — "
                f"sim={sim_result.tricks_team0} vs engine={engine_result.tricks_team0}"
            )
            assert sim_result.tricks_team1 == engine_result.tricks_team1, (
                f"Team 1 tricks mismatch: seed={seed} deal={deal_id} "
                f"contract={contract_type} trump={trump} — "
                f"sim={sim_result.tricks_team1} vs engine={engine_result.tricks_team1}"
            )

            # Compare trick winners
            assert sim_result.trick_winners == engine_result.trick_winners, (
                f"Trick winners mismatch: seed={seed} deal={deal_id} "
                f"contract={contract_type} trump={trump} — "
                f"sim={sim_result.trick_winners} vs engine={engine_result.trick_winners}"
            )

            # Compare card-by-card play sequence
            divergence = _first_divergence(sim_result.plays, engine_result.plays)
            assert divergence is None, (
                f"Card play divergence: seed={seed} deal={deal_id} "
                f"contract={contract_type} trump={trump} — {divergence}"
            )

    @pytest.mark.parametrize("seed", _SEEDS)
    def test_trick_count_consistency(self, seed: int) -> None:
        """Verify trick counts always sum to 10 in both paths."""
        bidder_seat = 2
        for deal_id in range(5):
            hands = generate_deal(seed, deal_id)
            for ct, ts in [("suit", "H"), ("high", None), ("low", None)]:
                sim = _run_sim_hand(hands, ct, ts, bidder_seat)
                eng = _run_engine_hand(hands, ct, ts, bidder_seat)
                assert (
                    sim.tricks_team0 + sim.tricks_team1 == 10
                ), f"Sim tricks don't sum to 10: {sim.tricks_team0}+{sim.tricks_team1}"
                assert (
                    eng.tricks_team0 + eng.tricks_team1 == 10
                ), f"Engine tricks don't sum to 10: {eng.tricks_team0}+{eng.tricks_team1}"

    @pytest.mark.parametrize("seed", _SEEDS)
    def test_multiple_bidder_seats(self, seed: int) -> None:
        """Verify parity holds regardless of which seat is the bidder/leader."""
        deal_id = 0
        hands = generate_deal(seed, deal_id)
        for bidder_seat in range(4):
            sim_result = _run_sim_hand(hands, "suit", "S", bidder_seat)
            engine_result = _run_engine_hand(hands, "suit", "S", bidder_seat)

            divergence = _first_divergence(sim_result.plays, engine_result.plays)
            assert (
                divergence is None
            ), f"Divergence with bidder_seat={bidder_seat} seed={seed}: {divergence}"

    @pytest.mark.parametrize("seed", _SEEDS)
    def test_play_count_is_40(self, seed: int) -> None:
        """Each hand should produce exactly 40 plays (4 players × 10 tricks)."""
        hands = generate_deal(seed, 0)
        sim = _run_sim_hand(hands, "suit", "S", 1)
        eng = _run_engine_hand(hands, "suit", "S", 1)
        assert len(sim.plays) == 40, f"Sim produced {len(sim.plays)} plays, expected 40"
        assert (
            len(eng.plays) == 40
        ), f"Engine produced {len(eng.plays)} plays, expected 40"
