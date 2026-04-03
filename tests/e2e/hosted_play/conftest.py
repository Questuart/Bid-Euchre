"""Shared fixtures for hosted-play E2E tests.

Provides engine instances, Jinja2 template rendering, and helper functions
that drive the full pipeline: MatchEngine -> get_visible_state -> template
rendering.  No external services or browsers required.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

import jinja2
import pytest

from bid_euchre.core.cards import Card
from bid_euchre.core.rules import get_legal_indices, trick_winner
from bid_euchre.hosted_play.engine import (
    HUMAN_SEAT,
    MatchEngine,
)
from bid_euchre.hosted_play.state import MatchState
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import BidAction, BiddingObservation, BiddingPolicy
from web.routes import _build_seat_bids
from web.template_filters import display_rank, effective_suit

# ---------------------------------------------------------------------------
# Deterministic AI stubs
# ---------------------------------------------------------------------------


class AlwaysPassBidder(BiddingPolicy):
    """Bidding policy that always passes."""

    def __init__(self) -> None:
        super().__init__(name="always_pass")

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        return BidAction.pass_bid()


class FixedBidder(BiddingPolicy):
    """Bids a fixed amount if legal, else passes."""

    def __init__(self, n: int = 5, contract: str = "S") -> None:
        super().__init__(name=f"fixed_{n}{contract}")
        self._n = n
        self._contract = contract

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if self._n > obs.current_high_bid:
            return BidAction.bid(self._n, self._contract)
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
# Constants
# ---------------------------------------------------------------------------

SEED = 42

TEMPLATES_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "web",
    "templates",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the local test server (placeholder for future use)."""
    return "http://localhost:8000"


@pytest.fixture()
def jinja_env() -> jinja2.Environment:
    """Jinja2 environment loading from web/templates/."""
    environment = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
        autoescape=True,
        undefined=jinja2.StrictUndefined,
    )
    environment.filters["display_rank"] = display_rank
    environment.filters["effective_suit"] = effective_suit
    return environment


@pytest.fixture()
def engine() -> MatchEngine:
    """Engine with a fixed 5S bidder and first-legal play strategy."""
    return MatchEngine(
        bidding_policy=FixedBidder(n=5, contract="S"),
        play_strategy=FirstLegalPlay(),
    )


@pytest.fixture()
def pass_engine() -> MatchEngine:
    """Engine with all-pass bidding."""
    return MatchEngine(
        bidding_policy=AlwaysPassBidder(),
        play_strategy=FirstLegalPlay(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def play_full_hand(
    engine: MatchEngine,
    state: MatchState,
    human_bid: BidAction | None = None,
) -> MatchState:
    """Drive a full hand to completion, making first-legal plays for human."""
    hand = state.current_hand
    assert hand is not None

    while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
        if human_bid is not None:
            state = engine.submit_human_bid(state, human_bid)
            human_bid = None
        elif 5 > hand.current_high_bid:
            state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
        else:
            state = engine.submit_human_bid(state, BidAction.pass_bid())
        hand = state.current_hand
        if hand is None:
            return state

    while (
        state.status == "active"
        and state.current_hand is not None
        and state.current_hand.phase == "trick_play"
        and state.current_hand.current_seat == HUMAN_SEAT
        and state.current_hand.sitting_out_seat != HUMAN_SEAT
    ):
        legal = engine.get_legal_plays(state)
        state = engine.submit_human_card(state, legal[0])

    return state


def advance_to_trick_play(
    engine: MatchEngine,
    state: MatchState,
    human_bid: BidAction | None = None,
) -> MatchState:
    """Drive past the auction into trick play, submitting human bids as needed."""
    hand = state.current_hand
    assert hand is not None

    while hand.phase == "auction" and hand.current_seat == HUMAN_SEAT:
        if human_bid is not None:
            state = engine.submit_human_bid(state, human_bid)
            human_bid = None
        elif 5 > hand.current_high_bid:
            state = engine.submit_human_bid(state, BidAction.bid(5, "S"))
        else:
            state = engine.submit_human_bid(state, BidAction.pass_bid())
        hand = state.current_hand
        if hand is None:
            return state

    return state


def play_one_trick(engine: MatchEngine, state: MatchState) -> MatchState:
    """Drive exactly one trick to completion."""
    hand = state.current_hand
    assert hand is not None
    assert hand.phase == "trick_play"

    initial_completed = len(hand.completed_tricks)
    while (
        state.status == "active"
        and state.current_hand is not None
        and state.current_hand.phase == "trick_play"
        and len(state.current_hand.completed_tricks) == initial_completed
    ):
        if state.current_hand.current_seat == HUMAN_SEAT:
            legal = engine.get_legal_plays(state)
            state = engine.submit_human_card(state, legal[0])
        # If AI needs to play, the engine auto-advances

    return state


def build_visible_context(
    engine: MatchEngine,
    state: MatchState,
    link_uuid: str = "test-uuid",
) -> dict[str, Any]:
    """Build a template context from engine visible state.

    Mirrors _build_game_context from web/routes.py but without web
    dependencies (no Request, no DB).
    """
    visible = engine.get_visible_state(state)
    hand = state.current_hand

    ctx: dict[str, Any] = {
        "link_uuid": link_uuid,
        "match_status": state.status,
        **visible,
    }

    if hand is not None:
        ctx["winning_bid"] = hand.winning_bid
        ctx["bidder_seat"] = hand.bidder_seat
        ctx["current_high_bid"] = hand.current_high_bid
        ctx["points_team0"] = hand.points_team0
        ctx["points_team1"] = hand.points_team1
        ctx["show_next"] = False
        ctx["next_reason"] = None
        ctx["show_bid_panel"] = (
            hand.phase == "auction" and hand.current_seat == HUMAN_SEAT
        )

        if hand.phase == "trick_play" and hand.current_seat == HUMAN_SEAT:
            ctx["legal_plays"] = engine.get_legal_plays(state)
        else:
            ctx["legal_plays"] = None

        # Compute trick_winning_seat (mirrors routes.py logic)
        trick = hand.current_trick if hand.current_trick is not None else None
        if (
            trick is not None
            and len(trick.plays) >= 1
            and hand.contract_type is not None
        ):
            ctx["trick_winning_seat"] = trick_winner(
                trick.plays, hand.contract_type, hand.trump
            )
        else:
            ctx["trick_winning_seat"] = None

        ctx["opp_left_count"] = len(hand.hands[1]) if len(hand.hands) > 1 else 0
        ctx["partner_count"] = len(hand.hands[2]) if len(hand.hands) > 2 else 0
        ctx["opp_right_count"] = len(hand.hands[3]) if len(hand.hands) > 3 else 0
        ctx["action_rail"] = []
        # Build seat → bid text mapping for inline bid display
        # Uses the canonical parser from web/routes.py to avoid drift.
        ctx["seat_bids"] = _build_seat_bids(visible.get("auction", []))
    else:
        ctx["winning_bid"] = None
        ctx["bidder_seat"] = None
        ctx["current_high_bid"] = 0
        ctx["points_team0"] = 0
        ctx["points_team1"] = 0
        ctx["legal_plays"] = None
        ctx["trick_winning_seat"] = None
        ctx["opp_left_count"] = 0
        ctx["partner_count"] = 0
        ctx["opp_right_count"] = 0
        ctx["action_rail"] = []
        ctx["seat_bids"] = {}
        ctx["show_next"] = False
        ctx["next_reason"] = None
        ctx["show_bid_panel"] = False

    return ctx
