"""Tests for scripts/internal/export_hosted_decisions.py CLI.

Tests the export_decisions() function and the CLI main() entry point
using an in-memory SQLite database.
"""

from __future__ import annotations

import json
import uuid

import pytest

# Import the CLI module's functions
from scripts.internal.export_hosted_decisions import (
    _build_query,
    export_decisions,
    main,
)
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
# Fixtures (reused pattern from test_export.py)
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


SAMPLE_LEGAL_ACTIONS = [{"n": 0}, {"n": 1, "contract": "S"}]
SAMPLE_CHOSEN_ACTION = {"n": 1, "contract": "S"}
SAMPLE_GAME_STATE = {"phase": "auction", "hand": [["S", "A"]]}


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
# _build_query tests
# ---------------------------------------------------------------------------


class TestBuildQuery:
    """Verify query filters work correctly."""

    def test_unfiltered_returns_all(self, session):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand, turn_number=0, actor_type="human")
        _make_decision(session, match, hand, turn_number=1, actor_type="ai")
        session.commit()

        stmt = _build_query()
        rows = session.execute(stmt).all()
        assert len(rows) == 2

    def test_match_uuid_filter(self, session):
        player = _make_player(session)
        target_uuid = str(uuid.uuid4())
        match1 = _make_match(session, player, match_uuid=target_uuid)
        match2 = _make_match(session, player)
        hand1 = _make_hand(session, match1, hand_number=1)
        hand2 = _make_hand(session, match2, hand_number=1)
        _make_decision(session, match1, hand1, turn_number=0)
        _make_decision(session, match2, hand2, turn_number=0)
        session.commit()

        stmt = _build_query(match_uuid=target_uuid)
        rows = session.execute(stmt).all()
        assert len(rows) == 1
        assert rows[0][1].match_uuid == target_uuid

    def test_human_only_filter(self, session):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand, turn_number=0, actor_type="human")
        _make_decision(session, match, hand, turn_number=1, actor_type="ai")
        session.commit()

        stmt = _build_query(human_only=True)
        rows = session.execute(stmt).all()
        assert len(rows) == 1
        assert rows[0][0].actor_type == "human"

    def test_combined_filters(self, session):
        player = _make_player(session)
        target_uuid = str(uuid.uuid4())
        match1 = _make_match(session, player, match_uuid=target_uuid)
        match2 = _make_match(session, player)
        hand1 = _make_hand(session, match1, hand_number=1)
        hand2 = _make_hand(session, match2, hand_number=1)
        # Target match: one human, one AI
        _make_decision(session, match1, hand1, turn_number=0, actor_type="human")
        _make_decision(session, match1, hand1, turn_number=1, actor_type="ai")
        # Other match: one human
        _make_decision(session, match2, hand2, turn_number=0, actor_type="human")
        session.commit()

        stmt = _build_query(match_uuid=target_uuid, human_only=True)
        rows = session.execute(stmt).all()
        assert len(rows) == 1
        assert rows[0][0].actor_type == "human"
        assert rows[0][1].match_uuid == target_uuid


# ---------------------------------------------------------------------------
# export_decisions tests
# ---------------------------------------------------------------------------


class TestExportDecisions:
    """Verify export_decisions writes correct JSONL files."""

    def test_writes_jsonl_file(self, session, tmp_path):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand, turn_number=0)
        _make_decision(session, match, hand, turn_number=1, actor_type="ai")
        session.commit()

        output = tmp_path / "out.jsonl"
        count = export_decisions(session, output)
        assert count == 2
        assert output.exists()

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            record = json.loads(line)
            assert record["schema_version"] == 1

    def test_empty_db_writes_empty_file(self, session, tmp_path):
        session.commit()

        output = tmp_path / "empty.jsonl"
        count = export_decisions(session, output)
        assert count == 0
        assert output.exists()
        assert output.read_text() == ""

    def test_creates_parent_directories(self, session, tmp_path):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand)
        session.commit()

        output = tmp_path / "nested" / "deep" / "out.jsonl"
        count = export_decisions(session, output)
        assert count == 1
        assert output.exists()

    def test_match_uuid_filter(self, session, tmp_path):
        player = _make_player(session)
        target_uuid = str(uuid.uuid4())
        match1 = _make_match(session, player, match_uuid=target_uuid)
        match2 = _make_match(session, player)
        hand1 = _make_hand(session, match1, hand_number=1)
        hand2 = _make_hand(session, match2, hand_number=1)
        _make_decision(session, match1, hand1, turn_number=0)
        _make_decision(session, match2, hand2, turn_number=0)
        session.commit()

        output = tmp_path / "filtered.jsonl"
        count = export_decisions(session, output, match_uuid=target_uuid)
        assert count == 1

        record = json.loads(output.read_text().strip())
        assert record["match_uuid"] == target_uuid

    def test_human_only_filter(self, session, tmp_path):
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand, turn_number=0, actor_type="human")
        _make_decision(session, match, hand, turn_number=1, actor_type="ai")
        session.commit()

        output = tmp_path / "human.jsonl"
        count = export_decisions(session, output, human_only=True)
        assert count == 1

        record = json.loads(output.read_text().strip())
        assert record["actor_type"] == "human"

    def test_deterministic_ordering(self, session, tmp_path):
        """Records are ordered by match_id, hand_number, turn_number."""
        player = _make_player(session)
        match = _make_match(session, player)
        hand = _make_hand(session, match)
        _make_decision(session, match, hand, turn_number=2, seat=2)
        _make_decision(session, match, hand, turn_number=0, seat=0)
        _make_decision(session, match, hand, turn_number=1, seat=1)
        session.commit()

        output = tmp_path / "ordered.jsonl"
        export_decisions(session, output)

        lines = output.read_text().strip().split("\n")
        turns = [json.loads(line)["turn_number"] for line in lines]
        assert turns == [0, 1, 2]

    def test_ordering_by_hand_number(self, session, tmp_path):
        """Decisions are ordered by logical hand_number, not hand PK."""
        player = _make_player(session)
        match = _make_match(session, player)
        # Create hands with non-sequential hand_numbers inserted out of order
        hand3 = _make_hand(session, match, hand_number=3)
        hand1 = _make_hand(session, match, hand_number=1)
        hand2 = _make_hand(session, match, hand_number=2)
        _make_decision(session, match, hand3, turn_number=0, seat=0)
        _make_decision(session, match, hand1, turn_number=0, seat=0)
        _make_decision(session, match, hand2, turn_number=0, seat=0)
        session.commit()

        output = tmp_path / "hand_order.jsonl"
        export_decisions(session, output)

        lines = output.read_text().strip().split("\n")
        hand_numbers = [json.loads(line)["hand_number"] for line in lines]
        assert hand_numbers == [1, 2, 3]


# ---------------------------------------------------------------------------
# CLI main() tests
# ---------------------------------------------------------------------------


class TestMainCLI:
    """Test the main() entry point."""

    def test_missing_db_returns_error(self, tmp_path):
        """Non-existent DB file should return exit code 1."""
        fake_db = tmp_path / "nonexistent.db"
        output = tmp_path / "out.jsonl"
        code = main(["--db", str(fake_db), "--output", str(output)])
        assert code == 1

    def test_export_from_real_db(self, tmp_path):
        """End-to-end: create DB, populate, export via main()."""
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)
        factory = make_session_factory(engine)
        sess = factory()

        player = _make_player(sess)
        match = _make_match(sess, player)
        hand = _make_hand(sess, match)
        _make_decision(sess, match, hand, turn_number=0)
        _make_decision(sess, match, hand, turn_number=1, actor_type="ai")
        sess.commit()
        sess.close()

        output = tmp_path / "export" / "decisions.jsonl"
        code = main(["--db", str(db_path), "--output", str(output)])
        assert code == 0
        assert output.exists()

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_overwrite_guard_rejects_same_path(self, tmp_path):
        """--output same as --db should return exit code 1."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        code = main(["--db", str(db_path), "--output", str(db_path)])
        assert code == 1

    def test_overwrite_guard_rejects_symlink(self, tmp_path):
        """--output symlink pointing to --db should return exit code 1."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        link_path = tmp_path / "link.db"
        link_path.symlink_to(db_path)
        code = main(["--db", str(db_path), "--output", str(link_path)])
        assert code == 1

    def test_help_flag(self, capsys):
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
