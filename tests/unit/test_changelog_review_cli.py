"""CLI-level tests for ``scripts/internal/changelog_review.py``.

Mirrors the Primitive D shape §4.5.6 CLI row, same shape as
``test_archivist_cli.py`` (§4.1.6): ``--help``, ``--dry-run``, fixture flag.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "scripts" / "internal" / "changelog_review.py"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "changelog_review"


@pytest.fixture(scope="module")
def changelog_review_cli():
    """Import the changelog_review CLI module via spec-loader.

    The CLI script lives under ``scripts/internal/`` which is not a
    normal importable package; we load it by file path for testing.
    """
    spec = importlib.util.spec_from_file_location("_changelog_review_cli", CLI_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestChangelogReviewCLI:
    """Cover the CLI wrapper per shape §4.5.3 + §4.5.6."""

    def test_help_exits_zero(
        self, changelog_review_cli, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--help`` exits with code 0 and prints usage text."""
        with pytest.raises(SystemExit) as exc_info:
            changelog_review_cli.main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--since" in captured.out
        assert "--fixture-dir" in captured.out
        assert "--dry-run" in captured.out

    def test_dry_run_with_fixture_dir(
        self,
        changelog_review_cli,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--dry-run --fixture-dir ...`` prints target path and does not write."""
        candidates_dir = tmp_path / "_candidates"

        rc = changelog_review_cli.main(
            [
                "--dry-run",
                "--fixture-dir",
                str(FIXTURE_DIR),
                "--candidates-dir",
                str(candidates_dir),
                # Skip real harness_assumptions.md reads to keep tests hermetic.
                "--assumptions-path",
                str(tmp_path / "no-such.md"),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "dry-run" in captured.out
        assert "candidates=" in captured.out
        # No output file, no watermark.
        assert not candidates_dir.exists() or not any(candidates_dir.iterdir())

    def test_fixture_dir_writes_candidate_file(
        self,
        changelog_review_cli,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """``--fixture-dir`` writes a dated candidate file with feature entries."""
        candidates_dir = tmp_path / "_candidates"

        rc = changelog_review_cli.main(
            [
                "--fixture-dir",
                str(FIXTURE_DIR),
                "--candidates-dir",
                str(candidates_dir),
                "--assumptions-path",
                str(tmp_path / "no-such.md"),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "wrote" in captured.out

        matches = list(candidates_dir.glob("*_changelog.md"))
        assert len(matches) == 1
        body = matches[0].read_text(encoding="utf-8")
        assert "# Changelog Review Candidate" in body
        assert "## Candidate" in body

        # Watermark advanced.
        watermark = candidates_dir / ".last_run_changelog"
        assert watermark.exists()

    def test_no_fixture_dir_returns_exit_2(
        self, changelog_review_cli, tmp_path: Path
    ) -> None:
        """Production mode without WebFetch wiring → all-unreachable → exit 2.

        Phase 0 scope (§4.5) ships the null fetcher as production default.
        The intent is operator visibility of "WebFetch not wired" rather
        than a silent empty scan. Phase 1+ swaps in the WebFetch fetcher.
        """
        candidates_dir = tmp_path / "_candidates"
        rc = changelog_review_cli.main(
            [
                "--candidates-dir",
                str(candidates_dir),
                "--assumptions-path",
                str(tmp_path / "no-such.md"),
                # Provide a tiny explicit source list so we do not walk the
                # full DEFAULT_SOURCES and print many lines.
                "--sources-file",
                str(
                    _write_sources_file(
                        tmp_path, ["https://example.com/one", "https://example.com/two"]
                    )
                ),
            ]
        )
        assert rc == 2

    def test_malformed_since_exits_2(
        self, changelog_review_cli, tmp_path: Path
    ) -> None:
        """``--since`` not ISO-8601 → exit 2 (source-unreachable class)."""
        rc = changelog_review_cli.main(
            [
                "--fixture-dir",
                str(FIXTURE_DIR),
                "--since",
                "not-a-date",
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--assumptions-path",
                str(tmp_path / "no-such.md"),
            ]
        )
        assert rc == 2

    def test_missing_fixture_dir_exits_2(
        self, changelog_review_cli, tmp_path: Path
    ) -> None:
        """Non-existent ``--fixture-dir`` → exit 2."""
        rc = changelog_review_cli.main(
            [
                "--fixture-dir",
                str(tmp_path / "does-not-exist"),
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--assumptions-path",
                str(tmp_path / "no-such.md"),
            ]
        )
        assert rc == 2

    def test_empty_sources_file_exits_2(
        self, changelog_review_cli, tmp_path: Path
    ) -> None:
        """Empty ``--sources-file`` rejected → exit 2."""
        empty = tmp_path / "empty_sources.txt"
        empty.write_text("# just a comment\n\n", encoding="utf-8")
        rc = changelog_review_cli.main(
            [
                "--sources-file",
                str(empty),
                "--fixture-dir",
                str(FIXTURE_DIR),
                "--candidates-dir",
                str(tmp_path / "_candidates"),
                "--assumptions-path",
                str(tmp_path / "no-such.md"),
            ]
        )
        assert rc == 2


def _write_sources_file(tmp_path: Path, urls: list[str]) -> Path:
    path = tmp_path / "sources.txt"
    path.write_text("\n".join(urls) + "\n", encoding="utf-8")
    return path
