"""Tests for web.export — JSONL export of hosted-play decisions.

Uses an in-memory SQLite database for isolation and speed.

Tests cover:
1. Schema compliance — all required fields present and typed correctly
2. Round-trip — create DB fixtures -> export -> parse -> verify field values
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import pytest

from web.db import (
    Decision,
    Hand,
    Match,
    Player,
    create_tables,
    init_engine,
    make_session_factory,
)
from web.export import REQUIRED_FIELDS, SCHEMA_VERSION, decision_to_jsonl

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


def _make_player(session) -> Player:
    player = Player(link_uuid=str(uuid.uuid4()), nickname="TestPlayer")
    session.add(player)
    session.flush()
    return player


def _make_match(session, player: Player, **overrides) -> Match:
    defaults = {
        "match_uuid": str(uuid.uuid4()),
        "player_id": player.id,
        "ai_model": "heuristic",
        "status": "active",
        "seed": 42,
        "match_state_json": "{}",
    }
    defaults.update(overrides)
    match = Match(**defaults)
    session.add(match)
    session.flush()
    return match


def _make_hand(session, match: Match, **overrides) -> Hand:
    defaults = {
        "match_id": match.id,
        "hand_number": 1,
        "deal_id": 7,
        "dealer_seat": 2,
        "status": "in_progress",
        "hand_state_json": "{}",
    }
    defaults.update(overrides)
    hand = Hand(**defaults)
    session.add(hand)
    session.flush()
    return hand


SAMPLE_LEGAL_ACTIONS = [
    {"n": 0},
    {"n": 1, "contract": "S"},
    {"n": 1, "contract": "H"},
]

SAMPLE_CHOSEN_ACTION = {"n": 1, "contract": "S"}

SAMPLE_GAME_STATE = {
    "phase": "auction",
    "hand": [["S", "A"], ["S", "K"], ["H", "J"]],
    "auction_transcript": [{"seat": 3, "action": "pass", "n": 0}],
    "current_high_bid": 0,
}


def _make_decision(session, match: Match, hand: Hand, **overrides) -> Decision:
    defaults = {
        "match_id": match.id,
        "hand_id": hand.id,
        "turn_number": 0,
        "seat": 0,
        "phase": "bid",
        "actor_type": "human",
        "decision_source": "human",
        "legal_actions_json": json.dumps(SAMPLE_LEGAL_ACTIONS),
        "chosen_action_json": json.dumps(SAMPLE_CHOSEN_ACTION),
        "game_state_json": json.dumps(SAMPLE_GAME_STATE),
        "decision_time_ms": 4200,
    }
    defaults.update(overrides)
    decision = Decision(**defaults)
    session.add(decision)
    session.flush()
    return decision


# ---------------------------------------------------------------------------
# Schema compliance tests
# ---------------------------------------------------------------------------


class TestSchemaCompliance:
    """Verify exported dict matches the SP-4-01 JSONL schema."""

    def test_all_required_fields_present(self, session):
        """Every field in REQUIRED_FIELDS must appear in the output."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        missing = REQUIRED_FIELDS - set(result.keys())
        assert not missing, f"Missing required fields: {missing}"

    def test_no_extra_fields(self, session):
        """Output should contain exactly the required fields (no extras)."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        extra = set(result.keys()) - REQUIRED_FIELDS
        assert not extra, f"Unexpected extra fields: {extra}"

    def test_schema_version_is_integer(self, session):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert isinstance(result["schema_version"], int)
        assert result["schema_version"] == SCHEMA_VERSION

    def test_event_is_string(self, session):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert isinstance(result["event"], str)
        assert result["event"] == "hosted_decision"

    def test_integer_fields_are_integers(self, session):
        """Numeric fields must be ints (not strings or floats)."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        int_fields = [
            "match_seed",
            "hand_number",
            "deal_id",
            "dealer_seat",
            "turn_number",
            "seat",
        ]
        for field in int_fields:
            assert isinstance(
                result[field], int
            ), f"{field} should be int, got {type(result[field])}"

    def test_parsed_json_fields_are_not_strings(self, session):
        """legal_actions, chosen_action, game_state must be parsed objects."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert isinstance(result["legal_actions"], list)
        assert isinstance(result["chosen_action"], dict)
        assert isinstance(result["game_state"], dict)

    def test_output_is_json_serializable(self, session):
        """The output dict must be JSON-serializable (no date objects, etc.)."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        # Should not raise
        serialized = json.dumps(result)
        # Round-trip: parse back and verify keys preserved
        parsed = json.loads(serialized)
        assert set(parsed.keys()) == set(result.keys())


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """Create DB fixtures -> export -> verify field values match."""

    def test_match_fields(self, session):
        """match_uuid, match_seed, ai_model come from the Match row."""
        player = _make_player(session)
        match_uuid = str(uuid.uuid4())
        match = _make_match(
            session,
            player,
            match_uuid=match_uuid,
            seed=123,
            ai_model="neural_v2",
        )
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert result["match_uuid"] == match_uuid
        assert result["match_seed"] == 123
        assert result["ai_model"] == "neural_v2"

    def test_hand_fields(self, session):
        """hand_number, deal_id, dealer_seat come from the Hand row."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(
            session,
            match,
            hand_number=3,
            deal_id=42,
            dealer_seat=1,
        )
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert result["hand_number"] == 3
        assert result["deal_id"] == 42
        assert result["dealer_seat"] == 1

    def test_decision_fields(self, session):
        """Core decision fields come from the Decision row."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(
            session,
            match,
            hand,
            turn_number=5,
            seat=2,
            phase="play",
            actor_type="ai",
            decision_source="heuristic",
            decision_time_ms=1500,
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["turn_number"] == 5
        assert result["seat"] == 2
        assert result["phase"] == "play"
        assert result["actor_type"] == "ai"
        assert result["decision_source"] == "heuristic"
        assert result["decision_time_ms"] == 1500

    def test_legal_actions_parsed(self, session):
        """legal_actions_json is parsed into a Python list."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        actions = [{"n": 0}, {"n": 3, "contract": "H"}]
        decision = _make_decision(
            session,
            match,
            hand,
            legal_actions_json=json.dumps(actions),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["legal_actions"] == actions

    def test_chosen_action_parsed(self, session):
        """chosen_action_json is parsed into a Python dict."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        action = {"n": 5, "contract": "S"}
        decision = _make_decision(
            session,
            match,
            hand,
            chosen_action_json=json.dumps(action),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["chosen_action"] == action

    def test_game_state_parsed(self, session):
        """game_state_json is parsed into a Python dict."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        state = {
            "phase": "auction",
            "hand": [["S", "A"], ["H", "K"]],
            "current_high_bid": 3,
        }
        decision = _make_decision(
            session,
            match,
            hand,
            game_state_json=json.dumps(state),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["game_state"] == state

    def test_timestamp_iso_format(self, session):
        """created_at is exported as an ISO 8601 UTC string."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        ts = result["timestamp"]
        assert isinstance(ts, str)
        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None, "Timestamp must include timezone"

    def test_decision_time_ms_nullable(self, session):
        """decision_time_ms can be None (nullable in DB)."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        decision = _make_decision(
            session,
            match,
            hand,
            decision_time_ms=None,
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["decision_time_ms"] is None

    def test_full_round_trip_json_serialization(self, session):
        """Full round-trip: DB -> export -> JSON string -> parse -> verify."""
        player = _make_player(session)
        match_uuid = str(uuid.uuid4())
        match = _make_match(
            session,
            player,
            match_uuid=match_uuid,
            seed=99,
            ai_model="heuristic",
        )
        hand = _make_hand(
            session,
            match,
            hand_number=2,
            deal_id=14,
            dealer_seat=3,
        )
        legal = [{"n": 0}, {"n": 2, "contract": "D"}]
        chosen = {"n": 2, "contract": "D"}
        state = {"phase": "auction", "bids": []}
        decision = _make_decision(
            session,
            match,
            hand,
            turn_number=1,
            seat=1,
            phase="bid",
            actor_type="human",
            decision_source="human",
            legal_actions_json=json.dumps(legal),
            chosen_action_json=json.dumps(chosen),
            game_state_json=json.dumps(state),
            decision_time_ms=3100,
        )

        result = decision_to_jsonl(decision, match, hand)

        # Serialize to JSONL string and parse back
        jsonl_line = json.dumps(result)
        parsed = json.loads(jsonl_line)

        # Verify all values survive the round-trip
        assert parsed["schema_version"] == 1
        assert parsed["event"] == "hosted_decision"
        assert parsed["match_uuid"] == match_uuid
        assert parsed["match_seed"] == 99
        assert parsed["hand_number"] == 2
        assert parsed["deal_id"] == 14
        assert parsed["dealer_seat"] == 3
        assert parsed["turn_number"] == 1
        assert parsed["seat"] == 1
        assert parsed["phase"] == "bid"
        assert parsed["actor_type"] == "human"
        assert parsed["decision_source"] == "human"
        assert parsed["ai_model"] == "heuristic"
        assert parsed["legal_actions"] == legal
        assert parsed["chosen_action"] == chosen
        assert parsed["game_state"] == state
        assert parsed["decision_time_ms"] == 3100
        assert isinstance(parsed["timestamp"], str)
