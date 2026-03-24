"""Shared test fixtures and factory helpers for hosted-play tests.

Provides reusable factories for creating test database objects (Player,
Match, Hand, Decision) with sensible defaults.  Override any column via
keyword arguments.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy.orm import Session

from web.db import (
    Decision,
    Hand,
    Match,
    Player,
    create_tables,
    init_engine,
    make_session_factory,
)

# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_engine():
    """In-memory SQLite engine with all tables created."""
    engine = init_engine("sqlite:///:memory:")
    create_tables(engine)
    return engine


@pytest.fixture()
def db_session_factory(db_engine):
    """Session factory bound to the in-memory engine."""
    return make_session_factory(db_engine)


@pytest.fixture()
def db_session(db_session_factory):
    """Scoped session that rolls back after each test."""
    session = db_session_factory()
    yield session
    session.rollback()
    session.close()


# ---------------------------------------------------------------------------
# Counter for auto-incrementing turn numbers
# ---------------------------------------------------------------------------

_turn_counter: dict[int, int] = {}


def _next_turn(hand_id: int) -> int:
    """Return the next turn_number for *hand_id*, starting at 0."""
    n = _turn_counter.get(hand_id, 0)
    _turn_counter[hand_id] = n + 1
    return n


@pytest.fixture(autouse=True)
def _reset_turn_counter():
    """Reset the per-hand turn counter between tests."""
    _turn_counter.clear()
    yield
    _turn_counter.clear()


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def create_test_db() -> tuple:
    """Create an in-memory SQLite database with all tables.

    Returns:
        (engine, session_factory) — ready to use.
    """
    engine = init_engine("sqlite:///:memory:")
    create_tables(engine)
    factory = make_session_factory(engine)
    return engine, factory


def create_test_player(session: Session, **overrides: Any) -> Player:
    """Insert a Player with sensible defaults.

    Override any column by passing keyword arguments.
    """
    defaults: dict[str, Any] = {
        "link_uuid": str(uuid.uuid4()),
        "nickname": "TestPlayer",
    }
    defaults.update(overrides)
    player = Player(**defaults)
    session.add(player)
    session.flush()
    return player


def create_test_match(session: Session, **overrides: Any) -> Match:
    """Insert a Match (and its parent Player if needed) with sensible defaults.

    If ``player_id`` is not provided, a new Player is created automatically.
    Override any column by passing keyword arguments.
    """
    defaults: dict[str, Any] = {
        "match_uuid": str(uuid.uuid4()),
        "seed": 42,
        "ai_model": "heuristic",
        "status": "active",
        "match_state_json": "{}",
    }
    defaults.update(overrides)

    # Auto-create a player if none supplied
    if "player_id" not in defaults:
        player = create_test_player(session)
        defaults["player_id"] = player.id

    match = Match(**defaults)
    session.add(match)
    session.flush()
    return match


def create_test_hand(session: Session, match: Match, **overrides: Any) -> Hand:
    """Insert a Hand under *match* with sensible defaults.

    Override any column by passing keyword arguments.
    """
    defaults: dict[str, Any] = {
        "match_id": match.id,
        "hand_number": 0,
        "deal_id": 0,
        "dealer_seat": 0,
        "status": "in_progress",
        "hand_state_json": "{}",
    }
    defaults.update(overrides)
    hand = Hand(**defaults)
    session.add(hand)
    session.flush()
    return hand


def create_test_decision(
    session: Session,
    match: Match,
    hand: Hand,
    **overrides: Any,
) -> Decision:
    """Insert a Decision under *match*/*hand* with sensible defaults.

    ``turn_number`` auto-increments per hand_id if not explicitly provided.
    Override any column by passing keyword arguments.
    """
    defaults: dict[str, Any] = {
        "match_id": match.id,
        "hand_id": hand.id,
        "turn_number": _next_turn(hand.id),
        "seat": 0,
        "phase": "bid",
        "actor_type": "human",
        "decision_source": "human",
        "legal_actions_json": json.dumps([{"n": 0}, {"n": 1, "contract": "S"}]),
        "chosen_action_json": json.dumps({"n": 1, "contract": "S"}),
        "game_state_json": json.dumps({"phase": "auction", "hand": [["S", "A"]]}),
        "decision_time_ms": 4200,
    }
    defaults.update(overrides)
    decision = Decision(**defaults)
    session.add(decision)
    session.flush()
    return decision


def populate_complete_hand(
    session: Session,
    match: Match,
    *,
    n_decisions: int = 14,
) -> tuple[Hand, list[Decision]]:
    """Create a hand with a full set of decisions.

    By default creates 14 decisions: 4 bid-phase + 10 play-phase (one per
    trick), which models a typical hand flow.  Adjust *n_decisions* for
    shorter/longer sequences.

    Returns:
        (hand, decisions) — the created Hand and its Decision list.
    """
    hand = create_test_hand(session, match)
    decisions: list[Decision] = []

    for i in range(n_decisions):
        # First 4 decisions are bids, rest are plays
        if i < 4:
            phase = "bid"
            actor_type = "human" if i % 2 == 0 else "ai"
            action = json.dumps("pass" if i < 3 else "bid_5_H")
            legal = json.dumps(["pass", "bid_5_H"])
            state = json.dumps({"phase": "auction", "turn": i})
        else:
            phase = "play"
            actor_type = "human" if i % 2 == 0 else "ai"
            action = json.dumps({"suit": "H", "rank": "A"})
            legal = json.dumps([{"suit": "H", "rank": "A"}, {"suit": "H", "rank": "K"}])
            state = json.dumps({"phase": "play", "trick": i - 4})

        decision = create_test_decision(
            session,
            match,
            hand,
            seat=i % 4,
            phase=phase,
            actor_type=actor_type,
            decision_source=actor_type,
            chosen_action_json=action,
            legal_actions_json=legal,
            game_state_json=state,
        )
        decisions.append(decision)

    return hand, decisions
