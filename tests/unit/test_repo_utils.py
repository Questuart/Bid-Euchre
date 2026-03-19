"""Tests for scripts/internal/_repo_utils.py shared utilities."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Import the module — it lives in scripts/internal/ so we add it to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"


@pytest.fixture(autouse=True)
def _add_scripts_path() -> None:
    """Ensure scripts/internal is importable."""
    path_str = str(SCRIPTS_DIR)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


class TestFindRepoRoot:
    """Tests for find_repo_root()."""

    def test_returns_path(self) -> None:
        """find_repo_root() returns a Path object."""
        from _repo_utils import find_repo_root

        result = find_repo_root()
        assert isinstance(result, Path)

    def test_finds_git_directory(self) -> None:
        """When run from within the repo, finds the root with .git."""
        from _repo_utils import find_repo_root

        root = find_repo_root()
        assert (root / ".git").exists() or (root / ".git").is_file()

    def test_result_is_absolute(self) -> None:
        """Returned path is always absolute."""
        from _repo_utils import find_repo_root

        root = find_repo_root()
        assert root.is_absolute()

    def test_fallback_outside_repo(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falls back to cwd when not inside a git repo."""
        from _repo_utils import find_repo_root

        # Create a directory with no .git anywhere in ancestors
        isolated = tmp_path / "no_git" / "deep" / "path"
        isolated.mkdir(parents=True)
        monkeypatch.chdir(isolated)

        result = find_repo_root()
        # Should fall back to cwd since there's no .git
        assert result == Path.cwd()
