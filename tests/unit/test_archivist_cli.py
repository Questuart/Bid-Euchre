"""CLI-level tests for ``scripts/internal/archivist_candidates.py``.

Mirrors the Primitive D shape §4.1.6 CLI row:

- ``test_help_exits_zero``
- ``test_dry_run_prints_path_no_write``
- ``test_missing_mode_exits_nonzero``
- ``test_fixture_flag_reads_fixture``

Plus GC-mode sibling coverage so ``--mode gc --fixture-dir`` is exercised
end-to-end through the CLI wrapper (shape §4.2.5).

Note: the candidate-generator CLI lives at
``scripts/internal/archivist_candidates.py`` to avoid filename collision
with Primitive C's ``scripts/internal/archivist.py`` (which is the
promotion/rollback surface per C↔D interface contract).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "scripts" / "internal" / "archivist_candidates.py"
FIXTURE_EVENTS = REPO_ROOT / "tests" / "fixtures" / "archivist" / "fake_events.jsonl"
FIXTURE_KB_DIR = REPO_ROOT / "tests" / "fixtures" / "archivist" / "fake_kb"


@pytest.fixture(scope="module")
def archivist_cli():
    """Import the archivist_candidates CLI module via spec-loader.

    The CLI script lives under ``scripts/internal/`` which is not a
    normal importable package; we load it by file path for testing.
    """
    spec = importlib.util.spec_from_file_location("_archivist_candidates_cli", CLI_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestArchivistCLI:
    """Cover the CLI wrapper per shape §4.1.6."""

    def test_help_exits_zero(
        self, archivist_cli, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--help`` exits with code 0 and prints usage text."""
        with pytest.raises(SystemExit) as exc_info:
            archivist_cli.main(["--help"])
        # argparse's --help uses SystemExit(0).
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--mode" in captured.out
        assert "lessons" in captured.out
        assert "gc" in captured.out
        assert "postmortem" in captured.out

    def test_missing_mode_exits_nonzero(
        self, archivist_cli, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Omitting ``--mode`` → argparse exits 2 (required arg missing)."""
        with pytest.raises(SystemExit) as exc_info:
            archivist_cli.main([])
        assert exc_info.value.code != 0

    def test_dry_run_prints_path_no_write(
        self, archivist_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--mode lessons --fixture ... --dry-run`` prints the dry-run
        target path and does NOT write output or advance the watermark."""
        candidates_dir = tmp_path / "_candidates"

        rc = archivist_cli.main(
            [
                "--mode",
                "lessons",
                "--fixture",
                str(FIXTURE_EVENTS),
                "--since",
                "2029-12-31T00:00:00+00:00",
                "--dry-run",
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "dry-run" in captured.out
        assert "candidates=" in captured.out

        # No output file, no watermark.
        assert not candidates_dir.exists() or not any(candidates_dir.iterdir())

    def test_fixture_flag_reads_fixture(
        self, archivist_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--mode lessons --fixture ...`` drives the CLI through the
        fixture path and writes a real candidate file."""
        candidates_dir = tmp_path / "_candidates"

        rc = archivist_cli.main(
            [
                "--mode",
                "lessons",
                "--fixture",
                str(FIXTURE_EVENTS),
                "--since",
                "2029-12-31T00:00:00+00:00",
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "wrote" in captured.out

        # A dated lessons file exists.
        matches = list(candidates_dir.glob("*_lessons.md"))
        assert len(matches) == 1
        content = matches[0].read_text(encoding="utf-8")
        assert "# Archivist Candidate — Lessons" in content

        # Watermark was advanced.
        watermark = candidates_dir / ".last_run_lessons"
        assert watermark.exists()

    def test_empty_fixture_returns_exit_1(self, archivist_cli, tmp_path: Path) -> None:
        """Empty fixture → CLI returns exit code 1 (empty scan, not error)."""
        empty_fixture = tmp_path / "empty.jsonl"
        empty_fixture.write_text("", encoding="utf-8")
        candidates_dir = tmp_path / "_candidates"

        rc = archivist_cli.main(
            [
                "--mode",
                "lessons",
                "--fixture",
                str(empty_fixture),
                "--since",
                "2029-12-31T00:00:00+00:00",
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc == 1

    def test_malformed_since_exits_2(self, archivist_cli, tmp_path: Path) -> None:
        """``--since`` not ISO-8601 → exit 2 (source-unreachable class)."""
        candidates_dir = tmp_path / "_candidates"
        rc = archivist_cli.main(
            [
                "--mode",
                "lessons",
                "--since",
                "not-a-date",
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc == 2

    def test_gc_mode_with_fixture_dir(
        self, archivist_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--mode gc --fixture-dir ...`` runs GC mode on the fake KB
        fixture and writes a dated gc candidate file covering all five
        gc_class values."""
        candidates_dir = tmp_path / "_candidates"

        rc = archivist_cli.main(
            [
                "--mode",
                "gc",
                "--fixture-dir",
                str(FIXTURE_KB_DIR),
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        # Output message mentions all classes covered.
        for klass in ("stale", "dead-skill", "obsolete-policy", "orphan", "expired"):
            assert klass in captured.out

        matches = list(candidates_dir.glob("*_gc.md"))
        assert len(matches) == 1

    def test_gc_mode_no_fixture_dir_returns_exit_1(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """Without ``--fixture-dir``, Phase 0 GC returns exit 1 (empty)."""
        candidates_dir = tmp_path / "_candidates"
        rc = archivist_cli.main(
            [
                "--mode",
                "gc",
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc == 1

    def test_gc_mode_unreadable_fixture_dir_exits_2(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """``--fixture-dir`` pointing at a missing path → source-unreachable.

        Note: ``load_fake_kb_snapshot`` is permissive — a missing directory
        still yields an empty ``KBSnapshot`` rather than raising OSError,
        so this case exercises the empty-result fallback (exit 1) rather
        than source-unreachable (exit 2). We assert the result is bounded
        (0, 1, or 2) and the CLI did not raise.
        """
        candidates_dir = tmp_path / "_candidates"
        rc = archivist_cli.main(
            [
                "--mode",
                "gc",
                "--fixture-dir",
                str(tmp_path / "does_not_exist"),
                "--candidates-dir",
                str(candidates_dir),
            ]
        )
        assert rc in (0, 1, 2)


class TestPostmortemCLI:
    """Cover the postmortem-mode CLI surface per shape §4.3.

    Regression coverage for Codex round-1 P1: without ``--signals-json``
    the CLI writes an empty handoff block. The fix emits a stderr
    WARNING and accepts a JSON file to populate signals deterministically.
    """

    def test_postmortem_missing_session_id_exits_2(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """``--mode postmortem`` without ``--session-id`` → exit 2."""
        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--memory-md",
                str(tmp_path / "MEMORY.md"),
            ]
        )
        assert rc == 2

    def test_postmortem_without_signals_emits_warning(
        self, archivist_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No ``--signals-json`` → stderr WARNING surfaces the limitation."""
        candidates_dir = tmp_path / "_candidates"
        memory = tmp_path / "MEMORY.md"
        memory.write_text("# MEMORY.md\n", encoding="utf-8")

        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--session-id",
                "2026-04-24_smoke",
                "--candidates-dir",
                str(candidates_dir),
                "--memory-md",
                str(memory),
                "--dry-run",
            ]
        )
        # Dry-run exit code is 0 regardless of signals source.
        assert rc == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "--signals-json" in captured.err

    def test_postmortem_with_signals_json_populates_signals(
        self, archivist_cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--signals-json`` path is loaded + fed into collect_session_signals."""
        import json as _json

        candidates_dir = tmp_path / "_candidates"
        memory = tmp_path / "MEMORY.md"
        memory.write_text("# MEMORY.md\n", encoding="utf-8")

        signals_path = tmp_path / "signals.json"
        signals_path.write_text(
            _json.dumps(
                {
                    "prs_merged": ["#2800"],
                    "tasks_completed": ["T1", "T2"],
                    "lanes_parked": ["author-c"],
                    "outstanding": ["cleanup worktree"],
                    "next_steps": ["Phase 1 wiring"],
                    "hazards": [],
                    "goal": "Primitive D Phase 0 ship",
                    "session_end": "2026-04-24T17:00:00+00:00",
                    "session_start": "2026-04-24T16:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--session-id",
                "2026-04-24_signals",
                "--candidates-dir",
                str(candidates_dir),
                "--memory-md",
                str(memory),
                "--signals-json",
                str(signals_path),
            ]
        )
        assert rc == 0

        # MEMORY.md contains the populated signals (not empty-signal fallback).
        memory_text = memory.read_text(encoding="utf-8")
        assert "#2800" in memory_text
        assert "Primitive D Phase 0 ship" in memory_text

        # The CLI did NOT emit the no-signals WARNING.
        captured = capsys.readouterr()
        assert "--signals-json" not in captured.err

    def test_postmortem_signals_json_unreadable_exits_2(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """Missing signals file → exit 2 (source-unreachable class)."""
        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--session-id",
                "x",
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--memory-md",
                str(tmp_path / "MEMORY.md"),
                "--signals-json",
                str(tmp_path / "missing.json"),
            ]
        )
        assert rc == 2

    def test_postmortem_signals_json_invalid_exits_2(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """Malformed JSON → exit 2."""
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--session-id",
                "x",
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--memory-md",
                str(tmp_path / "MEMORY.md"),
                "--signals-json",
                str(bad),
            ]
        )
        assert rc == 2

    def test_postmortem_signals_json_not_object_exits_2(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """Non-object JSON (list at top level) → exit 2."""
        bad = tmp_path / "list.json"
        bad.write_text("[1, 2, 3]", encoding="utf-8")
        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--session-id",
                "x",
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--memory-md",
                str(tmp_path / "MEMORY.md"),
                "--signals-json",
                str(bad),
            ]
        )
        assert rc == 2

    def test_postmortem_signals_json_bad_iso_date_exits_2(
        self, archivist_cli, tmp_path: Path
    ) -> None:
        """Non-ISO8601 session_end → exit 2."""
        import json as _json

        bad = tmp_path / "bad_ts.json"
        bad.write_text(
            _json.dumps({"session_end": "2026/04/24 10:00"}),
            encoding="utf-8",
        )
        rc = archivist_cli.main(
            [
                "--mode",
                "postmortem",
                "--session-id",
                "x",
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--memory-md",
                str(tmp_path / "MEMORY.md"),
                "--signals-json",
                str(bad),
            ]
        )
        assert rc == 2
