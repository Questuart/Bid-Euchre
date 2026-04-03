"""Tests for the dev database reset utility (web.reset_dev_db)."""

from __future__ import annotations

import pytest

from web.db import Comment, Decision, Hand, InviteCode, Match, Player
from web.reset_dev_db import ResetResult, get_counts, reset_game_data

from .conftest import (
    create_test_decision,
    create_test_hand,
    create_test_invite_code,
    create_test_match,
    create_test_player,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_decisions(session, match, hand, n: int) -> list:
    """Add *n* decisions to a hand."""
    decs = []
    for _ in range(n):
        decs.append(create_test_decision(session, match, hand))
    return decs


def _seed_full_db(session) -> dict[str, int]:
    """Populate the DB with a realistic mix of game data and accounts.

    Returns expected counts per table.
    """
    # Two players
    p1 = create_test_player(session, nickname="Alice")
    p2 = create_test_player(session, nickname="Bob")

    # Two invite codes (one redeemed, one active)
    create_test_invite_code(session, status="redeemed", player_id=p1.id)
    create_test_invite_code(session, status="active")

    # Player 1: complete match with 2 hands
    m1 = create_test_match(session, player_id=p1.id, status="complete")
    h1 = create_test_hand(session, m1, hand_number=0)
    _add_decisions(session, m1, h1, 14)
    h2 = create_test_hand(session, m1, hand_number=1)
    _add_decisions(session, m1, h2, 10)

    # Player 2: active match with 1 hand
    m2 = create_test_match(session, player_id=p2.id, status="active")
    h3 = create_test_hand(session, m2, hand_number=0)
    _add_decisions(session, m2, h3, 6)

    # A comment
    comment = Comment(player_id=p1.id, match_id=m1.id, content="Great game!")
    session.add(comment)
    session.flush()

    return {
        "players": 2,
        "invite_codes": 2,
        "matches": 2,
        "hands": 3,
        "decisions": 14 + 10 + 6,
        "comments": 1,
    }


# ---------------------------------------------------------------------------
# Tests: get_counts
# ---------------------------------------------------------------------------


class TestGetCounts:
    def test_empty_db(self, db_session):
        counts = get_counts(db_session)
        assert all(v == 0 for v in counts.values())

    def test_populated_db(self, db_session):
        expected = _seed_full_db(db_session)
        counts = get_counts(db_session)
        assert counts == expected


# ---------------------------------------------------------------------------
# Tests: reset_game_data (default — preserve accounts)
# ---------------------------------------------------------------------------


class TestResetGameDataDefault:
    """Default mode: clear matches/hands/decisions/comments, keep players/codes."""

    def test_clears_game_data(self, db_session):
        _seed_full_db(db_session)
        result = reset_game_data(db_session)

        assert result.decisions == 30
        assert result.hands == 3
        assert result.matches == 2
        assert result.comments == 1

        # Game tables are empty
        assert db_session.query(Decision).count() == 0
        assert db_session.query(Hand).count() == 0
        assert db_session.query(Match).count() == 0
        assert db_session.query(Comment).count() == 0

    def test_preserves_players(self, db_session):
        _seed_full_db(db_session)
        result = reset_game_data(db_session)

        assert result.players == 0  # no players deleted
        assert db_session.query(Player).count() == 2

    def test_preserves_invite_codes(self, db_session):
        _seed_full_db(db_session)
        result = reset_game_data(db_session)

        assert result.invite_codes == 0  # no codes deleted
        assert db_session.query(InviteCode).count() == 2

    def test_empty_db_is_noop(self, db_session):
        result = reset_game_data(db_session)
        assert result == ResetResult()

    def test_returns_correct_counts(self, db_session):
        expected = _seed_full_db(db_session)
        result = reset_game_data(db_session)

        assert result.decisions == expected["decisions"]
        assert result.hands == expected["hands"]
        assert result.matches == expected["matches"]
        assert result.comments == expected["comments"]


# ---------------------------------------------------------------------------
# Tests: reset_game_data (full — clear everything)
# ---------------------------------------------------------------------------


class TestResetGameDataFull:
    """Full mode: clear all tables including players and invite codes."""

    def test_clears_everything(self, db_session):
        _seed_full_db(db_session)
        reset_game_data(db_session, full=True)

        # All tables empty
        for model in (Decision, Hand, Match, Comment, InviteCode, Player):
            assert db_session.query(model).count() == 0

    def test_reports_all_deletions(self, db_session):
        expected = _seed_full_db(db_session)
        result = reset_game_data(db_session, full=True)

        assert result.decisions == expected["decisions"]
        assert result.hands == expected["hands"]
        assert result.matches == expected["matches"]
        assert result.comments == expected["comments"]
        assert result.invite_codes == expected["invite_codes"]
        assert result.players == expected["players"]


# ---------------------------------------------------------------------------
# Tests: CLI (main)
# ---------------------------------------------------------------------------


class TestCLI:
    """Test the CLI entry point via main().

    CLI tests use a file-based temp SQLite DB because ``main()`` calls
    ``engine.dispose()`` which destroys in-memory SQLite databases.
    """

    @pytest.fixture()
    def _cli_db(self, tmp_path):
        """Create a file-based temp DB and seed it. Return (db_url, engine)."""
        from web.db import create_tables as _ct
        from web.db import init_engine as _ie
        from web.db import make_session_factory as _mf

        db_path = tmp_path / "test_reset.db"
        db_url = f"sqlite:///{db_path}"
        engine = _ie(db_url)
        _ct(engine)
        factory = _mf(engine)
        session = factory()
        _seed_full_db(session)
        session.commit()
        session.close()
        return db_url, engine

    def _check_counts(self, db_url: str) -> dict[str, int]:
        """Open a fresh session and return current row counts."""
        from web.db import init_engine as _ie
        from web.db import make_session_factory as _mf

        engine = _ie(db_url)
        factory = _mf(engine)
        session = factory()
        counts = get_counts(session)
        session.close()
        engine.dispose()
        return counts

    def test_dry_run_no_changes(self, _cli_db, monkeypatch):
        """--dry-run should report counts but not delete anything."""
        db_url, _ = _cli_db

        from web.config import HostedPlayConfig

        monkeypatch.setattr(
            "web.reset_dev_db.get_config",
            lambda: HostedPlayConfig(database_url=db_url),
        )

        from web.reset_dev_db import main

        exit_code = main(["--dry-run"])
        assert exit_code == 0

        counts = self._check_counts(db_url)
        assert counts["matches"] == 2
        assert counts["players"] == 2

    def test_yes_flag_no_prompt(self, _cli_db, monkeypatch):
        """--yes should skip confirmation and delete game data."""
        db_url, _ = _cli_db

        from web.config import HostedPlayConfig

        monkeypatch.setattr(
            "web.reset_dev_db.get_config",
            lambda: HostedPlayConfig(database_url=db_url),
        )

        from web.reset_dev_db import main

        exit_code = main(["--yes"])
        assert exit_code == 0

        counts = self._check_counts(db_url)
        assert counts["matches"] == 0
        assert counts["players"] == 2
        assert counts["invite_codes"] == 2

    def test_full_yes_clears_all(self, _cli_db, monkeypatch):
        """--full --yes should delete everything."""
        db_url, _ = _cli_db

        from web.config import HostedPlayConfig

        monkeypatch.setattr(
            "web.reset_dev_db.get_config",
            lambda: HostedPlayConfig(database_url=db_url),
        )

        from web.reset_dev_db import main

        exit_code = main(["--full", "--yes"])
        assert exit_code == 0

        counts = self._check_counts(db_url)
        assert counts["matches"] == 0
        assert counts["players"] == 0
        assert counts["invite_codes"] == 0

    def test_empty_db_exits_zero(self, tmp_path, monkeypatch):
        """Empty database should exit 0 with 'nothing to reset' message."""
        from web.config import HostedPlayConfig
        from web.db import create_tables as _ct
        from web.db import init_engine as _ie

        db_path = tmp_path / "empty_reset.db"
        db_url = f"sqlite:///{db_path}"
        engine = _ie(db_url)
        _ct(engine)
        engine.dispose()

        monkeypatch.setattr(
            "web.reset_dev_db.get_config",
            lambda: HostedPlayConfig(database_url=db_url),
        )

        from web.reset_dev_db import main

        exit_code = main(["--yes"])
        assert exit_code == 0
