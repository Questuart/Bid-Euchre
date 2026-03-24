"""Tests for web.export — JSONL export of hosted-play decisions.

Uses an in-memory SQLite database for isolation and speed.

Tests cover:
1. Schema compliance — all required fields present and typed correctly
2. Round-trip — create DB fixtures -> export -> parse -> verify field values
3. Batch export — export_decisions with filters (human_only, match_uuid)
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
from web.export import (
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    decision_to_jsonl,
    export_decisions,
    validate_replay,
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


# ---------------------------------------------------------------------------
# Batch export tests (export_decisions)
# ---------------------------------------------------------------------------


class TestExportDecisions:
    """Test export_decisions() with filters and edge cases."""

    def test_human_only_filter(self, session, tmp_path):
        """export with human_only=True excludes AI decisions."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)

        # Create one human and one AI decision
        _make_decision(
            session,
            match,
            hand,
            turn_number=0,
            actor_type="human",
            decision_source="human",
        )
        _make_decision(
            session,
            match,
            hand,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        session.commit()

        output = tmp_path / "human_only.jsonl"
        count = export_decisions(session, output, human_only=True)

        assert count == 1
        lines = output.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["actor_type"] == "human"

    def test_match_uuid_filter(self, session, tmp_path):
        """export with match_uuid filters to that match only."""
        player = _make_player(session)
        target_uuid = str(uuid.uuid4())
        other_uuid = str(uuid.uuid4())
        match_target = _make_match(session, player, match_uuid=target_uuid, seed=10)
        match_other = _make_match(session, player, match_uuid=other_uuid, seed=20)
        hand_target = _make_hand(session, match_target, hand_number=1)
        hand_other = _make_hand(session, match_other, hand_number=1)

        _make_decision(session, match_target, hand_target, turn_number=0)
        _make_decision(session, match_other, hand_other, turn_number=0)
        session.commit()

        output = tmp_path / "single_match.jsonl"
        count = export_decisions(session, output, match_uuid=target_uuid)

        assert count == 1
        lines = output.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["match_uuid"] == target_uuid

    def test_empty_db_produces_empty_file(self, session, tmp_path):
        """Export from empty DB produces empty file and returns 0."""
        output = tmp_path / "empty.jsonl"
        count = export_decisions(session, output)

        assert count == 0
        content = output.read_text()
        assert content == ""

    def test_multi_match_export_all(self, session, tmp_path):
        """Export without filters includes all decisions across matches."""
        player = _make_player(session)
        match1 = _make_match(session, player, seed=10)
        match2 = _make_match(session, player, seed=20)
        hand1 = _make_hand(session, match1, hand_number=1)
        hand2 = _make_hand(session, match2, hand_number=1)

        # 2 decisions in match1, 1 in match2
        _make_decision(session, match1, hand1, turn_number=0)
        _make_decision(
            session,
            match1,
            hand1,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        _make_decision(session, match2, hand2, turn_number=0)
        session.commit()

        output = tmp_path / "all.jsonl"
        count = export_decisions(session, output)

        assert count == 3
        lines = output.read_text().strip().splitlines()
        assert len(lines) == 3

        # Verify both match UUIDs appear
        match_uuids = {json.loads(line)["match_uuid"] for line in lines}
        assert match1.match_uuid in match_uuids
        assert match2.match_uuid in match_uuids

    def test_combined_filters(self, session, tmp_path):
        """match_uuid + human_only filters combine correctly."""
        player = _make_player(session)
        target_uuid = str(uuid.uuid4())
        other_uuid = str(uuid.uuid4())
        match_target = _make_match(session, player, match_uuid=target_uuid, seed=10)
        match_other = _make_match(session, player, match_uuid=other_uuid, seed=20)
        hand_target = _make_hand(session, match_target, hand_number=1)
        hand_other = _make_hand(session, match_other, hand_number=1)

        # Target match: human + AI
        _make_decision(
            session,
            match_target,
            hand_target,
            turn_number=0,
            actor_type="human",
            decision_source="human",
        )
        _make_decision(
            session,
            match_target,
            hand_target,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        # Other match: human
        _make_decision(
            session,
            match_other,
            hand_other,
            turn_number=0,
            actor_type="human",
            decision_source="human",
        )
        session.commit()

        output = tmp_path / "combined.jsonl"
        count = export_decisions(
            session, output, match_uuid=target_uuid, human_only=True
        )

        assert count == 1
        lines = output.read_text().strip().splitlines()
        record = json.loads(lines[0])
        assert record["match_uuid"] == target_uuid
        assert record["actor_type"] == "human"

    def test_output_lines_are_valid_json(self, session, tmp_path):
        """Every line in the output file is valid JSON with schema fields."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand, turn_number=0)
        _make_decision(
            session,
            match,
            hand,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        session.commit()

        output = tmp_path / "valid.jsonl"
        count = export_decisions(session, output)
        assert count == 2

        lines = output.read_text().strip().splitlines()
        for line in lines:
            record = json.loads(line)  # Must not raise
            missing = REQUIRED_FIELDS - set(record.keys())
            assert not missing, f"Missing required fields: {missing}"


# ---------------------------------------------------------------------------
# Replay validation tests (validate_replay)
# ---------------------------------------------------------------------------

# Fixtures use seed=42, deal_id=7 with Hearts trump.  Seat 1 bids 5H.
# Trick 0: seat 0 DK → seat 1 DA → seat 2 DK → seat 3 DQ → winner seat 1.

_MATCH_UUID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_MATCH_SEED = 42
_DEAL_ID = 7

# Visible game state capturing auction result and one completed trick.
_GAME_STATE_AFTER_TRICK_0 = {
    "status": "active",
    "winner": None,
    "score_human": 0,
    "score_ai": 0,
    "hands_played": 0,
    "phase": "trick_play",
    "dealer_seat": 0,
    "current_seat": 1,
    "turn_number": 8,
    "human_hand": [
        ["D", "T"],
        ["S", "Q"],
        ["C", "A"],
        ["H", "Q"],
        ["C", "T"],
        ["C", "Q"],
        ["H", "A"],
        ["D", "A"],
        ["S", "K"],
    ],
    "auction": [
        {"seat": 1, "n": 0, "contract": None},
        {"seat": 2, "n": 0, "contract": None},
        {"seat": 3, "n": 0, "contract": None},
        {"seat": 0, "n": 0, "contract": None},
        {"seat": 1, "n": 5, "contract": "H"},
    ],
    "contract_type": "suit",
    "trump": "H",
    "current_trick": None,
    "completed_tricks": [
        {
            "leader": 0,
            "plays": [
                [0, ["D", "K"]],
                [1, ["D", "A"]],
                [2, ["D", "K"]],
                [3, ["D", "Q"]],
            ],
            "winner": 1,
        },
    ],
    "tricks_team0": 0,
    "tricks_team1": 1,
}

# Minimal game state for first bid decision (full human hand, auction phase).
_GAME_STATE_AUCTION_START = {
    "status": "active",
    "winner": None,
    "score_human": 0,
    "score_ai": 0,
    "hands_played": 0,
    "phase": "auction",
    "dealer_seat": 0,
    "current_seat": 1,
    "turn_number": 0,
    "human_hand": [
        ["D", "K"],
        ["D", "T"],
        ["S", "Q"],
        ["C", "A"],
        ["H", "Q"],
        ["C", "T"],
        ["C", "Q"],
        ["H", "A"],
        ["D", "A"],
        ["S", "K"],
    ],
    "auction": [],
    "contract_type": None,
    "trump": None,
    "current_trick": None,
    "completed_tricks": [],
    "tricks_team0": 0,
    "tricks_team1": 0,
}

# Game state for the play decision at trick 0, seat 0 leading.
_GAME_STATE_PLAY_SEAT0 = {
    "status": "active",
    "winner": None,
    "score_human": 0,
    "score_ai": 0,
    "hands_played": 0,
    "phase": "trick_play",
    "dealer_seat": 0,
    "current_seat": 0,
    "turn_number": 5,
    "human_hand": [
        ["D", "K"],
        ["D", "T"],
        ["S", "Q"],
        ["C", "A"],
        ["H", "Q"],
        ["C", "T"],
        ["C", "Q"],
        ["H", "A"],
        ["D", "A"],
        ["S", "K"],
    ],
    "auction": [
        {"seat": 1, "n": 0, "contract": None},
        {"seat": 2, "n": 0, "contract": None},
        {"seat": 3, "n": 0, "contract": None},
        {"seat": 0, "n": 0, "contract": None},
        {"seat": 1, "n": 5, "contract": "H"},
    ],
    "contract_type": "suit",
    "trump": "H",
    "current_trick": {"leader": 0, "plays": []},
    "completed_tricks": [],
    "tricks_team0": 0,
    "tricks_team1": 0,
}


def _write_jsonl(path, records):
    """Write a list of record dicts as JSONL to *path*."""
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def _make_bid_record(turn, seat, *, chosen, legal=None, game_state=None):
    """Build a minimal bid-phase JSONL record."""
    return {
        "schema_version": 1,
        "event": "hosted_decision",
        "match_uuid": _MATCH_UUID,
        "match_seed": _MATCH_SEED,
        "hand_number": 1,
        "deal_id": _DEAL_ID,
        "dealer_seat": 0,
        "turn_number": turn,
        "seat": seat,
        "phase": "bid",
        "actor_type": "human" if seat == 0 else "ai",
        "decision_source": "human" if seat == 0 else "heuristic",
        "ai_model": "heuristic",
        "legal_actions": legal or [{"n": 0}],
        "chosen_action": chosen,
        "game_state": game_state or _GAME_STATE_AUCTION_START,
        "decision_time_ms": 1000,
        "timestamp": "2026-03-24T06:00:00+00:00",
    }


def _make_play_record(turn, seat, *, chosen, legal, game_state):
    """Build a minimal play-phase JSONL record."""
    return {
        "schema_version": 1,
        "event": "hosted_decision",
        "match_uuid": _MATCH_UUID,
        "match_seed": _MATCH_SEED,
        "hand_number": 1,
        "deal_id": _DEAL_ID,
        "dealer_seat": 0,
        "turn_number": turn,
        "seat": seat,
        "phase": "play",
        "actor_type": "human" if seat == 0 else "ai",
        "decision_source": "human" if seat == 0 else "heuristic",
        "ai_model": "heuristic",
        "legal_actions": legal,
        "chosen_action": chosen,
        "game_state": game_state,
        "decision_time_ms": 500,
        "timestamp": "2026-03-24T06:00:01+00:00",
    }


class TestValidateReplay:
    """Tests for validate_replay — offline JSONL correctness verification."""

    def test_valid_file_returns_no_errors(self, tmp_path):
        """A correctly formed JSONL file produces an empty error list."""
        records = [
            # 5 bid decisions (4 passes + 1 real bid)
            _make_bid_record(0, 1, chosen={"n": 0}),
            _make_bid_record(1, 2, chosen={"n": 0}),
            _make_bid_record(2, 3, chosen={"n": 0}),
            _make_bid_record(3, 0, chosen={"n": 0}),
            _make_bid_record(
                4,
                1,
                chosen={"n": 5, "contract": "H"},
                legal=[{"n": 0}, {"n": 5, "contract": "H"}],
            ),
            # Play: seat 0 leads DK (index 0), all 10 indices legal
            _make_play_record(
                5,
                0,
                chosen=0,
                legal=list(range(10)),
                game_state=_GAME_STATE_PLAY_SEAT0,
            ),
        ]

        path = tmp_path / "valid.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_empty_file_returns_no_errors(self, tmp_path):
        """An empty JSONL file is trivially valid."""
        path = tmp_path / "empty.jsonl"
        path.write_text("")

        errors = validate_replay(path)
        assert errors == []

    def test_invalid_json_line_reported(self, tmp_path):
        """Lines that aren't valid JSON produce parse errors."""
        path = tmp_path / "bad.jsonl"
        path.write_text("not valid json\n")

        errors = validate_replay(path)
        assert len(errors) == 1
        assert "invalid JSON" in errors[0]

    def test_missing_required_field_reported(self, tmp_path):
        """Records missing required routing fields produce errors."""
        path = tmp_path / "missing.jsonl"
        # Missing match_seed
        _write_jsonl(path, [{"match_uuid": "abc", "hand_number": 1, "deal_id": 7}])

        errors = validate_replay(path)
        assert any("missing required field" in e for e in errors)

    def test_deal_regeneration_mismatch(self, tmp_path):
        """Detects when human_hand doesn't match dealt cards."""
        bad_state = dict(_GAME_STATE_AUCTION_START)
        bad_state["human_hand"] = [["Z", "9"]] * 10  # Fake cards

        records = [_make_bid_record(0, 1, chosen={"n": 0}, game_state=bad_state)]

        path = tmp_path / "bad_deal.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert any("not in dealt hand" in e for e in errors)

    def test_chosen_action_not_in_legal(self, tmp_path):
        """Detects when chosen_action is not in legal_actions."""
        records = [
            _make_bid_record(
                0,
                1,
                chosen={"n": 7, "contract": "S"},  # Not in legal
                legal=[{"n": 0}, {"n": 5, "contract": "H"}],
            ),
        ]

        path = tmp_path / "bad_action.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert any("chosen action not in legal_actions" in e for e in errors)

    def test_trick_winner_mismatch(self, tmp_path):
        """Detects when logged trick winner disagrees with trick_winner()."""
        bad_state = json.loads(json.dumps(_GAME_STATE_AFTER_TRICK_0))
        # Trick 0: DA wins (seat 1), but we claim seat 3 won.
        bad_state["completed_tricks"][0]["winner"] = 3

        records = [
            _make_bid_record(0, 1, chosen={"n": 0}),
            _make_play_record(
                5,
                0,
                chosen=0,
                legal=list(range(10)),
                game_state=bad_state,
            ),
        ]

        path = tmp_path / "bad_winner.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert any("winner mismatch" in e for e in errors)

    def test_trick_count_mismatch(self, tmp_path):
        """Detects when logged tricks_team counts don't match completed_tricks."""
        bad_state = json.loads(json.dumps(_GAME_STATE_AFTER_TRICK_0))
        # Completed trick winner is seat 1 (team 1), but claim team0 won it.
        bad_state["tricks_team0"] = 1
        bad_state["tricks_team1"] = 0

        records = [
            _make_bid_record(0, 1, chosen={"n": 0}),
            _make_play_record(
                5,
                0,
                chosen=0,
                legal=list(range(10)),
                game_state=bad_state,
            ),
        ]

        path = tmp_path / "bad_count.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert any("team0 tricks mismatch" in e for e in errors)
        assert any("team1 tricks mismatch" in e for e in errors)

    def test_play_legality_cross_check(self, tmp_path):
        """Verifies get_legal_indices cross-check catches bad legal_actions."""
        # Seat 0 leading — all 10 indices are legal.
        # But we claim only index 0 is legal (wrong).
        records = [
            _make_bid_record(0, 1, chosen={"n": 0}),
            _make_play_record(
                5,
                0,
                chosen=0,
                legal=[0],  # Should be [0..9]
                game_state=_GAME_STATE_PLAY_SEAT0,
            ),
        ]

        path = tmp_path / "bad_legal.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert any("legal_actions mismatch" in e for e in errors)

    def test_valid_trick_winner_passes(self, tmp_path):
        """A correct trick winner passes the check."""
        records = [
            _make_bid_record(0, 1, chosen={"n": 0}),
            _make_play_record(
                5,
                0,
                chosen=0,
                legal=list(range(10)),
                game_state=_GAME_STATE_AFTER_TRICK_0,
            ),
        ]

        path = tmp_path / "good_winner.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        # No trick winner errors
        assert not any("winner mismatch" in e for e in errors)
