"""Tests for web.db — SQLAlchemy models and session management.

Uses an in-memory SQLite database for isolation and speed.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import inspect

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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    """In-memory SQLite engine with tables created."""
    eng = init_engine("sqlite:///:memory:")
    create_tables(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Scoped session that rolls back after each test."""
    factory = make_session_factory(engine)
    sess = factory()
    yield sess
    sess.rollback()
    sess.close()


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------


class TestSchemaCreation:
    """Verify that create_tables produces the expected tables and columns."""

    def test_all_tables_created(self, engine):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"players", "matches", "hands", "decisions"} <= tables

    def test_players_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("players")}
        assert {"id", "link_uuid", "nickname", "created_at", "updated_at"} <= cols

    def test_matches_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("matches")}
        expected = {
            "id",
            "match_uuid",
            "player_id",
            "ai_model",
            "status",
            "seed",
            "score_human",
            "score_ai",
            "hands_played",
            "current_hand_number",
            "match_state_json",
            "created_at",
            "completed_at",
        }
        assert expected <= cols

    def test_hands_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("hands")}
        expected = {
            "id",
            "match_id",
            "hand_number",
            "deal_id",
            "dealer_seat",
            "status",
            "winning_bid_n",
            "winning_contract",
            "bidder_seat",
            "contract_type",
            "trump_suit",
            "tricks_team0",
            "tricks_team1",
            "points_team0",
            "points_team1",
            "hand_state_json",
            "started_at",
            "completed_at",
        }
        assert expected <= cols

    def test_decisions_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("decisions")}
        expected = {
            "id",
            "match_id",
            "hand_id",
            "turn_number",
            "seat",
            "phase",
            "actor_type",
            "decision_source",
            "legal_actions_json",
            "chosen_action_json",
            "game_state_json",
            "decision_time_ms",
            "created_at",
        }
        assert expected <= cols


# ---------------------------------------------------------------------------
# CRUD — Player
# ---------------------------------------------------------------------------


class TestPlayerCRUD:
    """Basic CRUD operations on the Player model."""

    def test_create_player(self, session):
        player = Player(link_uuid=str(uuid.uuid4()), nickname="Alice")
        session.add(player)
        session.flush()

        assert player.id is not None
        assert player.nickname == "Alice"
        assert player.created_at is not None

    def test_player_link_uuid_unique(self, session):
        uid = str(uuid.uuid4())
        session.add(Player(link_uuid=uid, nickname="A"))
        session.flush()

        session.add(Player(link_uuid=uid, nickname="B"))
        with pytest.raises(Exception):  # IntegrityError wrapped
            session.flush()

    def test_player_nickname_nullable(self, session):
        player = Player(link_uuid=str(uuid.uuid4()))
        session.add(player)
        session.flush()
        assert player.nickname is None


# ---------------------------------------------------------------------------
# CRUD — Match
# ---------------------------------------------------------------------------


class TestMatchCRUD:
    """Basic CRUD operations on the Match model."""

    def _make_player(self, session) -> Player:
        player = Player(link_uuid=str(uuid.uuid4()), nickname="Tester")
        session.add(player)
        session.flush()
        return player

    def test_create_match(self, session):
        player = self._make_player(session)
        match = Match(
            match_uuid=str(uuid.uuid4()),
            player_id=player.id,
            ai_model="heuristic",
            status="active",
            seed=42,
            match_state_json="{}",
        )
        session.add(match)
        session.flush()

        assert match.id is not None
        assert match.score_human == 0
        assert match.score_ai == 0
        assert match.hands_played == 0
        assert match.completed_at is None

    def test_match_status_constraint(self, session):
        """Only 'active', 'complete', 'abandoned' are valid."""
        player = self._make_player(session)
        match = Match(
            match_uuid=str(uuid.uuid4()),
            player_id=player.id,
            ai_model="heuristic",
            status="invalid_status",
            seed=42,
            match_state_json="{}",
        )
        session.add(match)
        with pytest.raises(Exception):
            session.flush()

    def test_match_uuid_unique(self, session):
        player = self._make_player(session)
        uid = str(uuid.uuid4())
        session.add(
            Match(
                match_uuid=uid,
                player_id=player.id,
                ai_model="heuristic",
                status="active",
                seed=42,
                match_state_json="{}",
            )
        )
        session.flush()

        session.add(
            Match(
                match_uuid=uid,
                player_id=player.id,
                ai_model="heuristic",
                status="active",
                seed=99,
                match_state_json="{}",
            )
        )
        with pytest.raises(Exception):
            session.flush()

    def test_match_foreign_key(self, session):
        """Foreign key to players must be enforced."""
        match = Match(
            match_uuid=str(uuid.uuid4()),
            player_id=99999,  # non-existent
            ai_model="heuristic",
            status="active",
            seed=42,
            match_state_json="{}",
        )
        session.add(match)
        with pytest.raises(Exception):
            session.flush()


# ---------------------------------------------------------------------------
# CRUD — Hand
# ---------------------------------------------------------------------------


class TestHandCRUD:
    """Basic CRUD operations on the Hand model."""

    def _make_match(self, session) -> Match:
        player = Player(link_uuid=str(uuid.uuid4()), nickname="P")
        session.add(player)
        session.flush()
        match = Match(
            match_uuid=str(uuid.uuid4()),
            player_id=player.id,
            ai_model="heuristic",
            status="active",
            seed=42,
            match_state_json="{}",
        )
        session.add(match)
        session.flush()
        return match

    def test_create_hand(self, session):
        match = self._make_match(session)
        hand = Hand(
            match_id=match.id,
            hand_number=1,
            deal_id=0,
            dealer_seat=0,
            status="in_progress",
            hand_state_json="{}",
        )
        session.add(hand)
        session.flush()

        assert hand.id is not None
        assert hand.tricks_team0 == 0
        assert hand.tricks_team1 == 0

    def test_hand_unique_per_match(self, session):
        """(match_id, hand_number) must be unique."""
        match = self._make_match(session)
        session.add(
            Hand(
                match_id=match.id,
                hand_number=1,
                deal_id=0,
                dealer_seat=0,
                status="in_progress",
                hand_state_json="{}",
            )
        )
        session.flush()

        session.add(
            Hand(
                match_id=match.id,
                hand_number=1,
                deal_id=1,
                dealer_seat=1,
                status="in_progress",
                hand_state_json="{}",
            )
        )
        with pytest.raises(Exception):
            session.flush()

    def test_hand_dealer_seat_constraint(self, session):
        """dealer_seat must be 0-3."""
        match = self._make_match(session)
        hand = Hand(
            match_id=match.id,
            hand_number=1,
            deal_id=0,
            dealer_seat=5,  # out of range
            status="in_progress",
            hand_state_json="{}",
        )
        session.add(hand)
        with pytest.raises(Exception):
            session.flush()

    def test_hand_status_constraint(self, session):
        match = self._make_match(session)
        hand = Hand(
            match_id=match.id,
            hand_number=1,
            deal_id=0,
            dealer_seat=0,
            status="bogus",
            hand_state_json="{}",
        )
        session.add(hand)
        with pytest.raises(Exception):
            session.flush()


# ---------------------------------------------------------------------------
# CRUD — Decision
# ---------------------------------------------------------------------------


class TestDecisionCRUD:
    """Basic CRUD operations on the Decision model."""

    def _make_hand(self, session) -> tuple[Match, Hand]:
        player = Player(link_uuid=str(uuid.uuid4()), nickname="P")
        session.add(player)
        session.flush()
        match = Match(
            match_uuid=str(uuid.uuid4()),
            player_id=player.id,
            ai_model="heuristic",
            status="active",
            seed=42,
            match_state_json="{}",
        )
        session.add(match)
        session.flush()
        hand = Hand(
            match_id=match.id,
            hand_number=1,
            deal_id=0,
            dealer_seat=0,
            status="in_progress",
            hand_state_json="{}",
        )
        session.add(hand)
        session.flush()
        return match, hand

    def test_create_decision(self, session):
        match, hand = self._make_hand(session)
        decision = Decision(
            match_id=match.id,
            hand_id=hand.id,
            turn_number=0,
            seat=0,
            phase="bid",
            actor_type="human",
            decision_source="human",
            legal_actions_json=json.dumps(["pass", "bid_5_H"]),
            chosen_action_json=json.dumps("bid_5_H"),
            game_state_json=json.dumps({"phase": "auction"}),
        )
        session.add(decision)
        session.flush()

        assert decision.id is not None
        assert decision.decision_time_ms is None

    def test_decision_unique_per_hand_turn(self, session):
        """(hand_id, turn_number) must be unique."""
        match, hand = self._make_hand(session)
        session.add(
            Decision(
                match_id=match.id,
                hand_id=hand.id,
                turn_number=0,
                seat=0,
                phase="bid",
                actor_type="human",
                decision_source="human",
                legal_actions_json="[]",
                chosen_action_json="{}",
                game_state_json="{}",
            )
        )
        session.flush()

        session.add(
            Decision(
                match_id=match.id,
                hand_id=hand.id,
                turn_number=0,  # duplicate
                seat=1,
                phase="bid",
                actor_type="ai",
                decision_source="heuristic",
                legal_actions_json="[]",
                chosen_action_json="{}",
                game_state_json="{}",
            )
        )
        with pytest.raises(Exception):
            session.flush()

    def test_decision_phase_constraint(self, session):
        match, hand = self._make_hand(session)
        d = Decision(
            match_id=match.id,
            hand_id=hand.id,
            turn_number=0,
            seat=0,
            phase="invalid",
            actor_type="human",
            decision_source="human",
            legal_actions_json="[]",
            chosen_action_json="{}",
            game_state_json="{}",
        )
        session.add(d)
        with pytest.raises(Exception):
            session.flush()

    def test_decision_seat_constraint(self, session):
        match, hand = self._make_hand(session)
        d = Decision(
            match_id=match.id,
            hand_id=hand.id,
            turn_number=0,
            seat=5,  # out of range
            phase="bid",
            actor_type="human",
            decision_source="human",
            legal_actions_json="[]",
            chosen_action_json="{}",
            game_state_json="{}",
        )
        session.add(d)
        with pytest.raises(Exception):
            session.flush()


# ---------------------------------------------------------------------------
# Engine / session helpers
# ---------------------------------------------------------------------------


class TestEngineHelpers:
    """Test engine creation and session factory."""

    def test_init_engine_sqlite(self):
        engine = init_engine("sqlite:///:memory:")
        assert engine is not None

    def test_create_tables_idempotent(self):
        """Calling create_tables twice should not error."""
        engine = init_engine("sqlite:///:memory:")
        create_tables(engine)
        create_tables(engine)  # second call — idempotent

    def test_session_factory(self, engine):
        factory = make_session_factory(engine)
        session = factory()
        assert session is not None
        session.close()

    def test_sqlite_foreign_keys_enabled(self, engine):
        """SQLite FK enforcement must be on (PRAGMA foreign_keys = ON)."""
        factory = make_session_factory(engine)
        sess = factory()
        result = sess.execute(
            __import__("sqlalchemy").text("PRAGMA foreign_keys")
        ).scalar()
        assert result == 1
        sess.close()
