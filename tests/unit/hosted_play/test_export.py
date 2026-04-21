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

from tests.unit.hosted_play.conftest import (
    create_test_decision,
    create_test_hand,
    create_test_match,
    create_test_player,
)
from web.export import (
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    SCHEMA_VERSION,
    decision_to_jsonl,
    export_decisions,
    validate_replay,
)

# ---------------------------------------------------------------------------
# Schema compliance tests
# ---------------------------------------------------------------------------


class TestSchemaCompliance:
    """Verify exported dict matches the SP-4-01 JSONL schema."""

    def test_all_required_fields_present(self, db_session):
        """Every field in REQUIRED_FIELDS must appear in the output."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        missing = REQUIRED_FIELDS - set(result.keys())
        assert not missing, f"Missing required fields: {missing}"

    def test_no_extra_fields(self, db_session):
        """Output should contain exactly required + known optional fields."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        extra = set(result.keys()) - REQUIRED_FIELDS - OPTIONAL_FIELDS
        assert not extra, f"Unexpected extra fields: {extra}"

    def test_schema_version_is_integer(self, db_session):
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert isinstance(result["schema_version"], int)
        assert result["schema_version"] == SCHEMA_VERSION

    def test_event_is_string(self, db_session):
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert isinstance(result["event"], str)
        assert result["event"] == "hosted_decision"

    def test_integer_fields_are_integers(self, db_session):
        """Numeric fields must be ints (not strings or floats)."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

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

    def test_parsed_json_fields_are_not_strings(self, db_session):
        """legal_actions, chosen_action, game_state must be parsed objects."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert isinstance(result["legal_actions"], list)
        assert isinstance(result["chosen_action"], dict)
        assert isinstance(result["game_state"], dict)

    def test_output_is_json_serializable(self, db_session):
        """The output dict must be JSON-serializable (no date objects, etc.)."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

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

    def test_match_fields(self, db_session):
        """match_uuid, match_seed, ai_model come from the Match row."""
        player = create_test_player(db_session)
        match_uuid = str(uuid.uuid4())
        match = create_test_match(
            db_session,
            player_id=player.id,
            match_uuid=match_uuid,
            seed=123,
            ai_model="neural_v2",
        )
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert result["match_uuid"] == match_uuid
        assert result["match_seed"] == 123
        assert result["ai_model"] == "neural_v2"

    def test_hand_fields(self, db_session):
        """hand_number, deal_id, dealer_seat come from the Hand row."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(
            db_session,
            match,
            hand_number=3,
            deal_id=42,
            dealer_seat=1,
        )
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        assert result["hand_number"] == 3
        assert result["deal_id"] == 42
        assert result["dealer_seat"] == 1

    def test_decision_fields(self, db_session):
        """Core decision fields come from the Decision row."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(
            db_session,
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

    def test_legal_actions_parsed(self, db_session):
        """legal_actions_json is parsed into a Python list."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        actions = [{"n": 0}, {"n": 3, "contract": "H"}]
        decision = create_test_decision(
            db_session,
            match,
            hand,
            legal_actions_json=json.dumps(actions),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["legal_actions"] == actions

    def test_chosen_action_parsed(self, db_session):
        """chosen_action_json is parsed into a Python dict."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        action = {"n": 5, "contract": "S"}
        decision = create_test_decision(
            db_session,
            match,
            hand,
            chosen_action_json=json.dumps(action),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["chosen_action"] == action

    def test_game_state_parsed(self, db_session):
        """game_state_json is parsed into a Python dict."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        state = {
            "phase": "auction",
            "hand": [["S", "A"], ["H", "K"]],
            "current_high_bid": 3,
        }
        decision = create_test_decision(
            db_session,
            match,
            hand,
            game_state_json=json.dumps(state),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["game_state"] == state

    def test_timestamp_iso_format(self, db_session):
        """created_at is exported as an ISO 8601 UTC string."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(db_session, match, hand)

        result = decision_to_jsonl(decision, match, hand)
        ts = result["timestamp"]
        assert isinstance(ts, str)
        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None, "Timestamp must include timezone"

    def test_decision_time_ms_nullable(self, db_session):
        """decision_time_ms can be None (nullable in DB)."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(
            db_session,
            match,
            hand,
            decision_time_ms=None,
        )

        result = decision_to_jsonl(decision, match, hand)
        assert result["decision_time_ms"] is None

    def test_full_round_trip_json_serialization(self, db_session):
        """Full round-trip: DB -> export -> JSON string -> parse -> verify."""
        player = create_test_player(db_session)
        match_uuid = str(uuid.uuid4())
        match = create_test_match(
            db_session,
            player_id=player.id,
            match_uuid=match_uuid,
            seed=99,
            ai_model="heuristic",
        )
        hand = create_test_hand(
            db_session,
            match,
            hand_number=2,
            deal_id=14,
            dealer_seat=3,
        )
        legal = [{"n": 0}, {"n": 2, "contract": "D"}]
        chosen = {"n": 2, "contract": "D"}
        state = {"phase": "auction", "bids": []}
        decision = create_test_decision(
            db_session,
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

    def test_human_only_filter(self, db_session, tmp_path):
        """export with human_only=True excludes AI decisions."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)

        # Create one human and one AI decision
        create_test_decision(
            db_session,
            match,
            hand,
            turn_number=0,
            actor_type="human",
            decision_source="human",
        )
        create_test_decision(
            db_session,
            match,
            hand,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        db_session.commit()

        output = tmp_path / "human_only.jsonl"
        count = export_decisions(db_session, output, human_only=True)

        assert count == 1
        lines = output.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["actor_type"] == "human"

    def test_match_uuid_filter(self, db_session, tmp_path):
        """export with match_uuid filters to that match only."""
        player = create_test_player(db_session)
        target_uuid = str(uuid.uuid4())
        other_uuid = str(uuid.uuid4())
        match_target = create_test_match(
            db_session, player_id=player.id, match_uuid=target_uuid, seed=10
        )
        match_other = create_test_match(
            db_session, player_id=player.id, match_uuid=other_uuid, seed=20
        )
        hand_target = create_test_hand(db_session, match_target, hand_number=1)
        hand_other = create_test_hand(db_session, match_other, hand_number=1)

        create_test_decision(db_session, match_target, hand_target, turn_number=0)
        create_test_decision(db_session, match_other, hand_other, turn_number=0)
        db_session.commit()

        output = tmp_path / "single_match.jsonl"
        count = export_decisions(db_session, output, match_uuid=target_uuid)

        assert count == 1
        lines = output.read_text().strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["match_uuid"] == target_uuid

    def test_empty_db_produces_empty_file(self, db_session, tmp_path):
        """Export from empty DB produces empty file and returns 0."""
        output = tmp_path / "empty.jsonl"
        count = export_decisions(db_session, output)

        assert count == 0
        content = output.read_text()
        assert content == ""

    def test_multi_match_export_all(self, db_session, tmp_path):
        """Export without filters includes all decisions across matches."""
        player = create_test_player(db_session)
        match1 = create_test_match(db_session, player_id=player.id, seed=10)
        match2 = create_test_match(db_session, player_id=player.id, seed=20)
        hand1 = create_test_hand(db_session, match1, hand_number=1)
        hand2 = create_test_hand(db_session, match2, hand_number=1)

        # 2 decisions in match1, 1 in match2
        create_test_decision(db_session, match1, hand1, turn_number=0)
        create_test_decision(
            db_session,
            match1,
            hand1,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        create_test_decision(db_session, match2, hand2, turn_number=0)
        db_session.commit()

        output = tmp_path / "all.jsonl"
        count = export_decisions(db_session, output)

        assert count == 3
        lines = output.read_text().strip().splitlines()
        assert len(lines) == 3

        # Verify both match UUIDs appear
        match_uuids = {json.loads(line)["match_uuid"] for line in lines}
        assert match1.match_uuid in match_uuids
        assert match2.match_uuid in match_uuids

    def test_combined_filters(self, db_session, tmp_path):
        """match_uuid + human_only filters combine correctly."""
        player = create_test_player(db_session)
        target_uuid = str(uuid.uuid4())
        other_uuid = str(uuid.uuid4())
        match_target = create_test_match(
            db_session, player_id=player.id, match_uuid=target_uuid, seed=10
        )
        match_other = create_test_match(
            db_session, player_id=player.id, match_uuid=other_uuid, seed=20
        )
        hand_target = create_test_hand(db_session, match_target, hand_number=1)
        hand_other = create_test_hand(db_session, match_other, hand_number=1)

        # Target match: human + AI
        create_test_decision(
            db_session,
            match_target,
            hand_target,
            turn_number=0,
            actor_type="human",
            decision_source="human",
        )
        create_test_decision(
            db_session,
            match_target,
            hand_target,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        # Other match: human
        create_test_decision(
            db_session,
            match_other,
            hand_other,
            turn_number=0,
            actor_type="human",
            decision_source="human",
        )
        db_session.commit()

        output = tmp_path / "combined.jsonl"
        count = export_decisions(
            db_session, output, match_uuid=target_uuid, human_only=True
        )

        assert count == 1
        lines = output.read_text().strip().splitlines()
        record = json.loads(lines[0])
        assert record["match_uuid"] == target_uuid
        assert record["actor_type"] == "human"

    def test_export_orders_by_hand_number(self, db_session, tmp_path):
        """Records are ordered by hand_number regardless of DB insertion order.

        Regression test for #1575 / #1577: export_decisions must ORDER BY
        Hand.hand_number (logical order), not Hand.id (insertion order).
        We insert hand_number=2 before hand_number=1 so the DB auto-increment
        ids are reversed relative to logical hand order.
        """
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)

        # Insert hand_number=2 first (gets lower hand.id)
        hand_2 = create_test_hand(db_session, match, hand_number=2)
        # Insert hand_number=1 second (gets higher hand.id)
        hand_1 = create_test_hand(db_session, match, hand_number=1)

        # One decision per hand
        create_test_decision(db_session, match, hand_2, turn_number=0)
        create_test_decision(db_session, match, hand_1, turn_number=0)
        db_session.commit()

        output = tmp_path / "ordered.jsonl"
        count = export_decisions(db_session, output)

        assert count == 2
        lines = output.read_text().strip().splitlines()
        records = [json.loads(line) for line in lines]

        # hand_number=1 must come before hand_number=2
        assert records[0]["hand_number"] == 1
        assert records[1]["hand_number"] == 2

    def test_export_orders_by_turn_within_hand(self, db_session, tmp_path):
        """Within the same hand, records are ordered by turn_number.

        Companion to test_export_orders_by_hand_number — verifies the
        secondary sort key (turn_number) within a hand.
        """
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match, hand_number=1)

        # Insert turn_number=2 before turn_number=0
        create_test_decision(db_session, match, hand, turn_number=2, seat=2)
        create_test_decision(db_session, match, hand, turn_number=0, seat=0)
        create_test_decision(db_session, match, hand, turn_number=1, seat=1)
        db_session.commit()

        output = tmp_path / "turn_ordered.jsonl"
        count = export_decisions(db_session, output)

        assert count == 3
        lines = output.read_text().strip().splitlines()
        records = [json.loads(line) for line in lines]

        assert [r["turn_number"] for r in records] == [0, 1, 2]

    def test_output_lines_are_valid_json(self, db_session, tmp_path):
        """Every line in the output file is valid JSON with schema fields."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand, turn_number=0)
        create_test_decision(
            db_session,
            match,
            hand,
            turn_number=1,
            actor_type="ai",
            decision_source="heuristic",
        )
        db_session.commit()

        output = tmp_path / "valid.jsonl"
        count = export_decisions(db_session, output)
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

    def test_double_deck_duplicate_cards_accepted(self, tmp_path):
        """Hands with duplicate cards (double deck) must not false-negative.

        Regression test for #1550: set() comparison collapsed duplicates,
        causing valid hands with two copies of the same card to fail
        deal-regeneration checks.

        Uses seed=1, deal_id=1 where seat 0 is dealt two Club Jacks.
        """
        # seed=1, deal_id=1 → seat 0 has two C-J (Club Jack)
        dup_seed = 1
        dup_deal_id = 1
        dup_match_uuid = "dupdup00-bbbb-cccc-dddd-eeeeeeeeeeee"

        # Full 10-card hand including duplicates (from generate_deal(1, 1))
        dup_human_hand = [
            ["D", "A"],
            ["H", "T"],
            ["C", "J"],
            ["S", "Q"],
            ["C", "K"],
            ["D", "T"],
            ["H", "Q"],
            ["S", "A"],
            ["C", "J"],  # second copy of Club Jack
            ["C", "Q"],
        ]

        dup_game_state = {
            "status": "active",
            "winner": None,
            "phase": "auction",
            "dealer_seat": 0,
            "current_seat": 1,
            "turn_number": 0,
            "human_hand": dup_human_hand,
            "auction": [],
            "contract_type": None,
            "trump": None,
            "current_trick": None,
            "completed_tricks": [],
            "tricks_team0": 0,
            "tricks_team1": 0,
        }

        records = [
            {
                "schema_version": 1,
                "event": "hosted_decision",
                "match_uuid": dup_match_uuid,
                "match_seed": dup_seed,
                "hand_number": 1,
                "deal_id": dup_deal_id,
                "dealer_seat": 0,
                "turn_number": 0,
                "seat": 1,
                "phase": "bid",
                "actor_type": "ai",
                "decision_source": "heuristic",
                "ai_model": "heuristic",
                "legal_actions": [{"n": 0}],
                "chosen_action": {"n": 0},
                "game_state": dup_game_state,
                "decision_time_ms": 100,
                "timestamp": "2026-03-24T06:00:00+00:00",
            },
        ]

        path = tmp_path / "double_deck.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert (
            errors == []
        ), f"Valid hand with duplicate cards should pass, got: {errors}"

    def test_double_deck_extra_duplicate_detected(self, tmp_path):
        """Three copies of a card (impossible in double deck) must be caught.

        The multiset comparison must detect that the logged hand claims more
        copies of a card than the dealt hand contains.
        """
        dup_seed = 1
        dup_deal_id = 1
        dup_match_uuid = "triples0-bbbb-cccc-dddd-eeeeeeeeeeee"

        # Tampered hand: THREE Club Jacks (dealt hand only has two)
        bad_human_hand = [
            ["D", "A"],
            ["H", "T"],
            ["C", "J"],
            ["S", "Q"],
            ["C", "K"],
            ["D", "T"],
            ["H", "Q"],
            ["C", "J"],  # second copy (valid)
            ["C", "J"],  # third copy (invalid!)
            ["C", "Q"],
        ]

        bad_game_state = {
            "status": "active",
            "winner": None,
            "phase": "auction",
            "dealer_seat": 0,
            "current_seat": 1,
            "turn_number": 0,
            "human_hand": bad_human_hand,
            "auction": [],
            "contract_type": None,
            "trump": None,
            "current_trick": None,
            "completed_tricks": [],
            "tricks_team0": 0,
            "tricks_team1": 0,
        }

        records = [
            {
                "schema_version": 1,
                "event": "hosted_decision",
                "match_uuid": dup_match_uuid,
                "match_seed": dup_seed,
                "hand_number": 1,
                "deal_id": dup_deal_id,
                "dealer_seat": 0,
                "turn_number": 0,
                "seat": 1,
                "phase": "bid",
                "actor_type": "ai",
                "decision_source": "heuristic",
                "ai_model": "heuristic",
                "legal_actions": [{"n": 0}],
                "chosen_action": {"n": 0},
                "game_state": bad_game_state,
                "decision_time_ms": 100,
                "timestamp": "2026-03-24T06:00:00+00:00",
            },
        ]

        path = tmp_path / "triple_deck.jsonl"
        _write_jsonl(path, records)

        errors = validate_replay(path)
        assert any(
            "not in dealt hand" in e for e in errors
        ), f"Three copies should be caught, got: {errors}"


# ---------------------------------------------------------------------------
# Glutton counterfactual export tests
# ---------------------------------------------------------------------------


class TestGluttonCounterfactualExport:
    """Verify glutton_action appears in export when set on Decision rows."""

    def test_glutton_action_included_when_present(self, db_session):
        """glutton_action field appears in export for decisions that have it."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(
            db_session,
            match,
            hand,
            phase="play",
            actor_type="human",
            decision_source="human",
            glutton_action_json=json.dumps(3),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert "glutton_action" in result
        assert result["glutton_action"] == 3

    def test_glutton_action_absent_when_null(self, db_session):
        """glutton_action field is omitted for decisions without it."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        decision = create_test_decision(
            db_session,
            match,
            hand,
            phase="bid",
            actor_type="human",
            decision_source="human",
        )

        result = decision_to_jsonl(decision, match, hand)
        assert "glutton_action" not in result


# ---------------------------------------------------------------------------
# GBT bid counterfactual export tests (#2645)
# ---------------------------------------------------------------------------


class TestBidCounterfactualExport:
    """Verify ``counterfactual`` is optional: present only when non-null.

    Schema unification (#2645): both counterfactual fields share the
    omit-when-null pattern.  ``counterfactual`` lives in OPTIONAL_FIELDS,
    not REQUIRED_FIELDS.
    """

    def test_counterfactual_is_optional_not_required(self):
        """Schema constant: ``counterfactual`` must be an OPTIONAL field."""
        from web.export import OPTIONAL_FIELDS, REQUIRED_FIELDS

        assert "counterfactual" in OPTIONAL_FIELDS
        assert "counterfactual" not in REQUIRED_FIELDS

    def test_counterfactual_included_when_present(self, db_session):
        """counterfactual field appears in export for decisions that have it."""
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        cf_payload = {"n": 3, "contract": "H"}
        decision = create_test_decision(
            db_session,
            match,
            hand,
            phase="bid",
            actor_type="human",
            decision_source="human",
            counterfactual_json=json.dumps(cf_payload),
        )

        result = decision_to_jsonl(decision, match, hand)
        assert "counterfactual" in result
        assert result["counterfactual"] == cf_payload

    def test_counterfactual_absent_when_null(self, db_session):
        """counterfactual field is omitted for decisions without it.

        This is the key behaviour change from #2645: previously the field was
        always emitted as ``null`` on non-human rows, wasting bytes.  Now it
        is omitted entirely, matching the glutton_action precedent (PR #2616).
        """
        player = create_test_player(db_session)
        match = create_test_match(db_session, player_id=player.id)
        hand = create_test_hand(db_session, match)
        # AI bid row — no counterfactual_json set.
        decision = create_test_decision(
            db_session,
            match,
            hand,
            phase="bid",
            actor_type="ai",
            decision_source="heuristic",
        )

        result = decision_to_jsonl(decision, match, hand)
        assert "counterfactual" not in result
