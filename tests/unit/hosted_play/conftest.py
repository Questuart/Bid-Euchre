"""Shared test fixtures and factory helpers for hosted-play tests.

Provides reusable factories for creating test database objects (Player,
Match, Hand, Decision) with sensible defaults.  Override any column via
keyword arguments.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pytest
from sklearn.dummy import DummyRegressor
from sqlalchemy.orm import Session

from bid_euchre.hosted_play.engine import MatchEngine
from bid_euchre.strategy.bidding import ACTION_FEATURE_NAMES, STATE_FEATURE_NAMES
from web.config import HostedPlayConfig
from web.db import (
    Decision,
    Hand,
    InviteCode,
    Match,
    Player,
    create_tables,
    generate_invite_code,
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


def create_browser_ai_test_artifacts(base_dir: Path) -> tuple[str, str]:
    """Write minimal browser AI artifacts for hosted-play tests.

    The browser roster now requires both OLSa and Bud Bot at startup.
    CI does not have the production artifact bundle, so tests build
    deterministic local fixtures instead of weakening startup checks.
    """
    artifact_dir = base_dir / "browser_ai_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    state_names = list(STATE_FEATURE_NAMES)
    action_names = list(ACTION_FEATURE_NAMES)
    bid_feature_names = state_names + action_names

    def _ols_model(intercept: float, feature_names: list[str]) -> dict[str, Any]:
        return {
            "coefficients": [0.0] * len(feature_names),
            "intercept": intercept,
            "feature_names": feature_names,
            "r_squared": 0.25,
        }

    olsa_artifact = {
        "schema_version": "action_value_olsa_v1",
        "models": {
            "suit": _ols_model(1.0, bid_feature_names),
            "high": _ols_model(0.9, bid_feature_names),
            "low": _ols_model(0.8, bid_feature_names),
            "pass": _ols_model(0.0, state_names),
        },
        "metadata": {
            "context_features": [
                "partner_level_same_suit",
                "partner_level_same_color",
                "partner_level_off_color",
                "partner_level_high",
                "partner_level_low",
                "partner_passed",
            ],
            "arm": "full",
        },
    }
    olsa_path = artifact_dir / "olsa_test_artifact.json"
    olsa_path.write_text(json.dumps(olsa_artifact, indent=2))

    bid_width = len(bid_feature_names)
    pass_width = len(state_names)
    X_bid = np.zeros((2, bid_width))
    y_bid = np.array([1.0, 1.0])
    X_pass = np.zeros((2, pass_width))
    y_pass = np.array([0.0, 0.0])

    gbt_files = {
        "suit": ("gbt_suit.joblib", 1.0),
        "high": ("gbt_high.joblib", 0.9),
        "low": ("gbt_low.joblib", 0.8),
        "pass": ("gbt_pass.joblib", 0.0),
    }
    for family, (filename, constant) in gbt_files.items():
        model = DummyRegressor(strategy="constant", constant=constant)
        if family == "pass":
            model.fit(X_pass, y_pass)
        else:
            model.fit(X_bid, y_bid)
        joblib.dump(model, artifact_dir / filename)

    gbt_artifact = {
        "schema_version": "action_value_gbt_v1",
        "models": {
            "suit": {
                "model_file": "gbt_suit.joblib",
                "feature_names": bid_feature_names,
                "r_squared": 0.25,
                "feature_importances": {},
            },
            "high": {
                "model_file": "gbt_high.joblib",
                "feature_names": bid_feature_names,
                "r_squared": 0.25,
                "feature_importances": {},
            },
            "low": {
                "model_file": "gbt_low.joblib",
                "feature_names": bid_feature_names,
                "r_squared": 0.25,
                "feature_importances": {},
            },
            "pass": {
                "model_file": "gbt_pass.joblib",
                "feature_names": state_names,
                "r_squared": 0.25,
                "feature_importances": {},
            },
        },
    }
    gbt_path = artifact_dir / "bud_bot_test_artifact.json"
    gbt_path.write_text(json.dumps(gbt_artifact, indent=2))

    return str(olsa_path), str(gbt_path)


def make_hosted_play_test_config(tmp_path: Path, **overrides: Any) -> HostedPlayConfig:
    """Build HostedPlayConfig with deterministic browser AI artifacts."""
    db_path = tmp_path / "test.db"
    olsa_artifact, gbt_artifact = create_browser_ai_test_artifacts(tmp_path)
    defaults: dict[str, Any] = {
        "database_url": f"sqlite:///{db_path}",
        "default_model_id": "olsa",
        "olsa_artifact": olsa_artifact,
        "gbt_artifact": gbt_artifact,
    }
    defaults.update(overrides)
    return HostedPlayConfig(**defaults)


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


def create_test_invite_code(
    session: Session,
    **overrides: Any,
) -> InviteCode:
    """Insert an InviteCode with sensible defaults.

    Override any column by passing keyword arguments.
    """
    defaults: dict[str, Any] = {
        "code": generate_invite_code(),
        "status": "active",
    }
    defaults.update(overrides)
    invite = InviteCode(**defaults)
    session.add(invite)
    session.flush()
    return invite


# ---------------------------------------------------------------------------
# Route-test helpers (shared across unit and integration suites)
# ---------------------------------------------------------------------------


def get_match_state(app, link_uuid: str):
    """Load the current match state from the DB for assertions.

    Returns ``(state, match_row, session)`` or *None* if no match is found.
    Caller **must** close the returned session.
    """
    session_factory = app.state.session_factory
    session = session_factory()
    try:
        player = session.query(Player).filter_by(link_uuid=link_uuid).first()
        if player is None:
            session.close()
            return None

        match_row = (
            session.query(Match)
            .filter_by(player_id=player.id, status="active")
            .order_by(Match.created_at.desc())
            .first()
        )
        if match_row is None:
            # Fall back to any match (e.g. completed)
            match_row = (
                session.query(Match)
                .filter_by(player_id=player.id)
                .order_by(Match.created_at.desc())
                .first()
            )
        if match_row is None:
            session.close()
            return None

        ai_manager = app.state.ai_manager
        info = ai_manager.get_model_info(match_row.ai_model)
        engine = MatchEngine(
            bidding_policy=info.bidding_policy,
            play_strategy=info.play_strategy,
        )
        state = engine.deserialize(json.loads(match_row.match_state_json))
        return state, match_row, session
    except Exception:
        session.close()
        raise


def advance_pending_reveals(
    client,
    app,
    link_uuid: str,
    *,
    max_steps: int = 12,
):
    """Advance hidden auction/trick reveals until the state is actionable."""
    for _ in range(max_steps):
        result = get_match_state(app, link_uuid)
        assert result is not None, "Match disappeared unexpectedly"
        state, _, session = result
        session.close()

        hand = state.current_hand
        if hand is None:
            return state

        has_hidden_auction = hand.revealed_auction_count < len(hand.auction)
        if not has_hidden_auction and not hand.paused_after_trick:
            return state

        resp = client.post(f"/play/{link_uuid}/next")
        assert resp.status_code == 200

    pytest.fail("Reveal state did not settle within safety limit")
