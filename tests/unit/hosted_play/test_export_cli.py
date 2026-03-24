"""Tests for scripts/internal/export_hosted_decisions.py CLI.

Tests the CLI main() entry point using an in-memory SQLite database.
The underlying export_decisions() and decision_to_jsonl() logic are tested
in tests/unit/hosted_play/test_export.py.
"""

from __future__ import annotations

import pytest

from scripts.internal.export_hosted_decisions import main
from tests.unit.hosted_play.conftest import (
    create_test_decision,
    create_test_hand,
    create_test_match,
    create_test_player,
)
from web.db import create_tables, init_engine, make_session_factory

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

    def test_creates_nested_parent_directories(self, tmp_path):
        """CLI creates parent directories for the output path."""
        db_path = tmp_path / "test.db"
        engine = init_engine(f"sqlite:///{db_path}")
        create_tables(engine)
        factory = make_session_factory(engine)
        sess = factory()

        player = create_test_player(sess)
        match = create_test_match(sess, player_id=player.id)
        hand = create_test_hand(sess, match)
        create_test_decision(sess, match, hand)
        sess.commit()
        sess.close()

        output = tmp_path / "nested" / "deep" / "out.jsonl"
        code = main(["--db", str(db_path), "--output", str(output)])
        assert code == 0
        assert output.exists()

    def test_samefile_guard(self, tmp_path):
        """--output that resolves to --db should return exit code 1."""
        db_path = tmp_path / "test.db"
        db_path.write_bytes(b"")  # create empty file

        # Exact same path
        code = main(["--db", str(db_path), "--output", str(db_path)])
        assert code == 1

    def test_samefile_guard_via_hardlink(self, tmp_path):
        """--output pointing to a hard link of --db should be caught."""
        import os

        db_path = tmp_path / "test.db"
        db_path.write_bytes(b"")
        link_path = tmp_path / "alias.db"
        os.link(db_path, link_path)

        code = main(["--db", str(db_path), "--output", str(link_path)])
        assert code == 1

    def test_help_flag(self):
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


class TestImportGuard:
    """Verify the import guard catches only ModuleNotFoundError (#1566)."""

    def test_guard_uses_module_not_found_error(self):
        """The import guard should be ModuleNotFoundError, not broad ImportError."""
        import ast
        from pathlib import Path

        src = Path("scripts/internal/export_hosted_decisions.py").read_text()
        tree = ast.parse(src)

        # Find the module-level try/except that guards the web imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                # Check if this try block imports from web.*
                has_web_import = any(
                    isinstance(stmt, (ast.Import, ast.ImportFrom))
                    and getattr(stmt, "module", "") is not None
                    and "web" in (getattr(stmt, "module", "") or "")
                    for stmt in node.body
                )
                if has_web_import:
                    for handler in node.handlers:
                        assert handler.type is not None
                        assert isinstance(handler.type, ast.Name)
                        assert handler.type.id == "ModuleNotFoundError", (
                            f"Import guard should catch ModuleNotFoundError, "
                            f"not {handler.type.id}"
                        )
                    return

        pytest.fail("Could not find the web import try/except block")
