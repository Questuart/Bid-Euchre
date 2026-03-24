"""Tests for scripts/internal/export_hosted_decisions.py CLI.

Tests the CLI main() entry point using an in-memory SQLite database.
The underlying export_decisions() and decision_to_jsonl() logic are tested
in tests/unit/hosted_play/test_export.py.
"""

from __future__ import annotations

import json
import uuid

import pytest

from scripts.internal.export_hosted_decisions import main
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

    def test_creates_nested_parent_directories(self, tmp_path):
        """CLI creates parent directories for the output path."""
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)
        factory = make_session_factory(engine)
        sess = factory()

        player = _make_player(sess)
        match = _make_match(sess, player)
        hand = _make_hand(sess, match)
        _make_decision(sess, match, hand)
        sess.commit()
        sess.close()

        output = tmp_path / "nested" / "deep" / "out.jsonl"
        code = main(["--db", str(db_path), "--output", str(output)])
        assert code == 0
        assert output.exists()

    def test_help_flag(self):
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
