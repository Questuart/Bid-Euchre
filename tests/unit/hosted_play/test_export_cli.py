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
from tests.unit.hosted_play.conftest import (
    create_test_decision,
    create_test_hand,
    create_test_match,
    create_test_player,
)
from web.db import (
    create_tables,
    init_engine,
    make_session_factory,
)

# ---------------------------------------------------------------------------
# _build_query tests
# ---------------------------------------------------------------------------


class TestBuildQuery:
    """Verify query filters work correctly."""

    def test_unfiltered_returns_all(self, db_session):
        match = create_test_match(db_session)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand, turn_number=0, actor_type="human")
        create_test_decision(db_session, match, hand, turn_number=1, actor_type="ai")
        db_session.commit()

        stmt = _build_query()
        rows = db_session.execute(stmt).all()
        assert len(rows) == 2

    def test_match_uuid_filter(self, db_session):
        player = create_test_player(db_session)
        target_uuid = str(uuid.uuid4())
        match1 = create_test_match(
            db_session, player_id=player.id, match_uuid=target_uuid
        )
        match2 = create_test_match(db_session, player_id=player.id)
        hand1 = create_test_hand(db_session, match1, hand_number=1)
        hand2 = create_test_hand(db_session, match2, hand_number=1)
        create_test_decision(db_session, match1, hand1, turn_number=0)
        create_test_decision(db_session, match2, hand2, turn_number=0)
        db_session.commit()

        stmt = _build_query(match_uuid=target_uuid)
        rows = db_session.execute(stmt).all()
        assert len(rows) == 1
        assert rows[0][1].match_uuid == target_uuid

    def test_human_only_filter(self, db_session):
        match = create_test_match(db_session)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand, turn_number=0, actor_type="human")
        create_test_decision(db_session, match, hand, turn_number=1, actor_type="ai")
        db_session.commit()

        stmt = _build_query(human_only=True)
        rows = db_session.execute(stmt).all()
        assert len(rows) == 1
        assert rows[0][0].actor_type == "human"

    def test_combined_filters(self, db_session):
        player = create_test_player(db_session)
        target_uuid = str(uuid.uuid4())
        match1 = create_test_match(
            db_session, player_id=player.id, match_uuid=target_uuid
        )
        match2 = create_test_match(db_session, player_id=player.id)
        hand1 = create_test_hand(db_session, match1, hand_number=1)
        hand2 = create_test_hand(db_session, match2, hand_number=1)
        # Target match: one human, one AI
        create_test_decision(
            db_session, match1, hand1, turn_number=0, actor_type="human"
        )
        create_test_decision(db_session, match1, hand1, turn_number=1, actor_type="ai")
        # Other match: one human
        create_test_decision(
            db_session, match2, hand2, turn_number=0, actor_type="human"
        )
        db_session.commit()

        stmt = _build_query(match_uuid=target_uuid, human_only=True)
        rows = db_session.execute(stmt).all()
        assert len(rows) == 1
        assert rows[0][0].actor_type == "human"
        assert rows[0][1].match_uuid == target_uuid


# ---------------------------------------------------------------------------
# export_decisions tests
# ---------------------------------------------------------------------------


class TestExportDecisions:
    """Verify export_decisions writes correct JSONL files."""

    def test_writes_jsonl_file(self, db_session, tmp_path):
        match = create_test_match(db_session)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand, turn_number=0)
        create_test_decision(db_session, match, hand, turn_number=1, actor_type="ai")
        db_session.commit()

        output = tmp_path / "out.jsonl"
        count = export_decisions(db_session, output)
        assert count == 2
        assert output.exists()

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            record = json.loads(line)
            assert record["schema_version"] == 1

    def test_empty_db_writes_empty_file(self, db_session, tmp_path):
        db_session.commit()

        output = tmp_path / "empty.jsonl"
        count = export_decisions(db_session, output)
        assert count == 0
        assert output.exists()
        assert output.read_text() == ""

    def test_creates_parent_directories(self, db_session, tmp_path):
        match = create_test_match(db_session)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand)
        db_session.commit()

        output = tmp_path / "nested" / "deep" / "out.jsonl"
        count = export_decisions(db_session, output)
        assert count == 1
        assert output.exists()

    def test_match_uuid_filter(self, db_session, tmp_path):
        player = create_test_player(db_session)
        target_uuid = str(uuid.uuid4())
        match1 = create_test_match(
            db_session, player_id=player.id, match_uuid=target_uuid
        )
        match2 = create_test_match(db_session, player_id=player.id)
        hand1 = create_test_hand(db_session, match1, hand_number=1)
        hand2 = create_test_hand(db_session, match2, hand_number=1)
        create_test_decision(db_session, match1, hand1, turn_number=0)
        create_test_decision(db_session, match2, hand2, turn_number=0)
        db_session.commit()

        output = tmp_path / "filtered.jsonl"
        count = export_decisions(db_session, output, match_uuid=target_uuid)
        assert count == 1

        record = json.loads(output.read_text().strip())
        assert record["match_uuid"] == target_uuid

    def test_human_only_filter(self, db_session, tmp_path):
        match = create_test_match(db_session)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand, turn_number=0, actor_type="human")
        create_test_decision(db_session, match, hand, turn_number=1, actor_type="ai")
        db_session.commit()

        output = tmp_path / "human.jsonl"
        count = export_decisions(db_session, output, human_only=True)
        assert count == 1

        record = json.loads(output.read_text().strip())
        assert record["actor_type"] == "human"

    def test_deterministic_ordering(self, db_session, tmp_path):
        """Records are ordered by match_id, hand_id, turn_number."""
        match = create_test_match(db_session)
        hand = create_test_hand(db_session, match)
        create_test_decision(db_session, match, hand, turn_number=2, seat=2)
        create_test_decision(db_session, match, hand, turn_number=0, seat=0)
        create_test_decision(db_session, match, hand, turn_number=1, seat=1)
        db_session.commit()

        output = tmp_path / "ordered.jsonl"
        export_decisions(db_session, output)

        lines = output.read_text().strip().split("\n")
        turns = [json.loads(line)["turn_number"] for line in lines]
        assert turns == [0, 1, 2]


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

        player = create_test_player(sess)
        match = create_test_match(sess, player_id=player.id)
        hand = create_test_hand(sess, match)
        create_test_decision(sess, match, hand, turn_number=0)
        create_test_decision(sess, match, hand, turn_number=1, actor_type="ai")
        sess.commit()
        sess.close()

        output = tmp_path / "export" / "decisions.jsonl"
        code = main(["--db", str(db_path), "--output", str(output)])
        assert code == 0
        assert output.exists()

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_help_flag(self, capsys):
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
