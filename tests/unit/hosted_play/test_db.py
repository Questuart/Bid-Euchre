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
    InviteCode,
    Match,
    Player,
    create_tables,
    generate_invite_code,
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

    def test_decision_accepts_moon_exchange_phase(self, session):
        match, hand = self._make_hand(session)
        decision = Decision(
            match_id=match.id,
            hand_id=hand.id,
            turn_number=0,
            seat=0,
            phase="moon_exchange",
            actor_type="human",
            decision_source="human",
            legal_actions_json="[]",
            chosen_action_json="[0, 1]",
            game_state_json="{}",
        )
        session.add(decision)
        session.flush()

        assert decision.id is not None

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
# CRUD — InviteCode
# ---------------------------------------------------------------------------


class TestInviteCodeCRUD:
    """Basic CRUD operations on the InviteCode model."""

    def test_create_invite_code(self, session):
        code = InviteCode(code="TESTCODE", status="active")
        session.add(code)
        session.flush()

        assert code.id is not None
        assert code.code == "TESTCODE"
        assert code.status == "active"
        assert code.player_id is None
        assert code.created_at is not None
        assert code.redeemed_at is None

    def test_invite_code_unique(self, session):
        session.add(InviteCode(code="UNIQ1234", status="active"))
        session.flush()

        session.add(InviteCode(code="UNIQ1234", status="active"))
        with pytest.raises(Exception):
            session.flush()

    def test_invite_code_status_constraint(self, session):
        """Only 'active', 'redeemed', 'revoked' are valid."""
        code = InviteCode(code="BAD00000", status="invalid")
        session.add(code)
        with pytest.raises(Exception):
            session.flush()

    def test_invite_code_with_label(self, session):
        code = InviteCode(code="LABEL123", status="active", label="Beta tester")
        session.add(code)
        session.flush()
        assert code.label == "Beta tester"

    def test_invite_code_redeem(self, session):
        """Redeeming binds a player_id and updates status."""
        player = Player(link_uuid=str(uuid.uuid4()))
        session.add(player)
        session.flush()

        code = InviteCode(code="REDEEM01", status="active")
        session.add(code)
        session.flush()

        code.status = "redeemed"
        code.player_id = player.id
        session.flush()

        assert code.status == "redeemed"
        assert code.player_id == player.id

    def test_invite_code_revoke(self, session):
        code = InviteCode(code="REVOKE01", status="active")
        session.add(code)
        session.flush()

        code.status = "revoked"
        session.flush()
        assert code.status == "revoked"

    def test_invite_code_player_fk(self, session):
        """player_id FK references players table."""
        code = InviteCode(code="FKTEST01", status="redeemed", player_id=99999)
        session.add(code)
        with pytest.raises(Exception):
            session.flush()


class TestInviteCodeSchema:
    """Verify invite_codes table is created with expected columns."""

    def test_invite_codes_table_created(self, engine):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "invite_codes" in tables

    def test_invite_codes_columns(self, engine):
        inspector = inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("invite_codes")}
        expected = {
            "id",
            "code",
            "status",
            "player_id",
            "label",
            "created_at",
            "redeemed_at",
        }
        assert expected <= cols


class TestGenerateInviteCode:
    """Test the invite code generator."""

    def test_default_length(self):
        code = generate_invite_code()
        assert len(code) == 8

    def test_custom_length(self):
        code = generate_invite_code(length=12)
        assert len(code) == 12

    def test_alphanumeric_uppercase(self):
        code = generate_invite_code()
        assert code.isalnum()
        assert code == code.upper()

    def test_uniqueness(self):
        """Multiple generated codes should be unique (probabilistic)."""
        codes = {generate_invite_code() for _ in range(100)}
        assert len(codes) == 100


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
