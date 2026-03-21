"""Tests for the repo-bounded filesystem access policy.

Covers path classification, boundary enforcement, symlink traversal
prevention, and audit event emission.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bid_euchre.ops.fs_boundary import (
    BoundaryViolationError,
    PathClass,
    check_path,
    classify_path,
    get_repo_boundaries,
    require_in_boundary,
    require_path,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_layout(tmp_path: Path) -> dict[str, str]:
    """Build a fake repo layout with worktrees and runtime dirs.

    Returns resolved string paths for each component.
    """
    repo_root = tmp_path / "Bid-Euchre"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()

    wt_author = tmp_path / "Bid-Euchre-steward-author"
    wt_author.mkdir()

    wt_review = tmp_path / "Bid-Euchre-steward-review"
    wt_review.mkdir()

    runtime = repo_root / ".claude" / "runtime"
    runtime.mkdir(parents=True)
    events = runtime / "events"
    events.mkdir()

    # Runtime dir under a worktree too
    wt_runtime = wt_author / ".claude" / "runtime"
    wt_runtime.mkdir(parents=True)

    external = tmp_path / "unrelated-project"
    external.mkdir()

    return {
        "repo_root": str(repo_root.resolve()),
        "worktree_paths": [
            str(repo_root.resolve()),
            str(wt_author.resolve()),
            str(wt_review.resolve()),
        ],
        "runtime_dirs": [
            str(runtime.resolve()),
            str(wt_runtime.resolve()),
        ],
        "external": str(external.resolve()),
        "events_dir": str(events.resolve()),
    }


# ---------------------------------------------------------------------------
# classify_path tests
# ---------------------------------------------------------------------------


class TestClassifyPath:
    """Tests for classify_path()."""

    def test_repo_root_exact(self, repo_layout: dict[str, str]) -> None:
        result = classify_path(
            repo_layout["repo_root"],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.REPO_ROOT

    def test_repo_root_subpath(self, repo_layout: dict[str, str]) -> None:
        subpath = Path(repo_layout["repo_root"]) / "src" / "file.py"
        result = classify_path(
            str(subpath),
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.REPO_ROOT

    def test_registered_worktree_exact(self, repo_layout: dict[str, str]) -> None:
        # The second worktree (not repo root)
        wt = repo_layout["worktree_paths"][1]
        result = classify_path(
            wt,
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.REGISTERED_WORKTREE

    def test_registered_worktree_subpath(self, repo_layout: dict[str, str]) -> None:
        wt = repo_layout["worktree_paths"][2]
        subpath = Path(wt) / "tests" / "test_something.py"
        result = classify_path(
            str(subpath),
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.REGISTERED_WORKTREE

    def test_managed_runtime(self, repo_layout: dict[str, str]) -> None:
        runtime = repo_layout["runtime_dirs"][0]
        result = classify_path(
            runtime,
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.MANAGED_RUNTIME

    def test_managed_runtime_subpath(self, repo_layout: dict[str, str]) -> None:
        subpath = Path(repo_layout["runtime_dirs"][0]) / "events" / "events.jsonl"
        result = classify_path(
            str(subpath),
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.MANAGED_RUNTIME

    def test_managed_runtime_in_worktree(self, repo_layout: dict[str, str]) -> None:
        """Runtime dir under a worktree is MANAGED_RUNTIME, not REGISTERED_WORKTREE."""
        result = classify_path(
            repo_layout["runtime_dirs"][1],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.MANAGED_RUNTIME

    def test_external_path(self, repo_layout: dict[str, str]) -> None:
        result = classify_path(
            repo_layout["external"],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.EXTERNAL

    def test_explicit_exception(self, repo_layout: dict[str, str]) -> None:
        result = classify_path(
            repo_layout["external"],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
            exceptions=[repo_layout["external"]],
        )
        assert result == PathClass.EXPLICIT_EXCEPTION

    def test_explicit_exception_subpath(self, repo_layout: dict[str, str]) -> None:
        """A subpath of an exception dir is also EXPLICIT_EXCEPTION."""
        subpath = Path(repo_layout["external"]) / "data" / "file.txt"
        result = classify_path(
            str(subpath),
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
            exceptions=[repo_layout["external"]],
        )
        assert result == PathClass.EXPLICIT_EXCEPTION

    def test_root_path_is_external(self, repo_layout: dict[str, str]) -> None:
        """The root filesystem '/' should be classified as external."""
        result = classify_path(
            "/",
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.EXTERNAL

    def test_home_dir_is_external(self, repo_layout: dict[str, str]) -> None:
        result = classify_path(
            "/Users/someone/Documents",
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.EXTERNAL


# ---------------------------------------------------------------------------
# Symlink traversal tests
# ---------------------------------------------------------------------------


class TestSymlinkTraversal:
    """Verify that symlinks cannot be used to escape the boundary."""

    def test_symlink_to_external_is_external(
        self, repo_layout: dict[str, str], tmp_path: Path
    ) -> None:
        """A symlink inside the repo pointing outside is classified by its real target."""
        external_target = Path(repo_layout["external"]) / "secret.txt"
        external_target.write_text("secret data")

        repo_link = Path(repo_layout["repo_root"]) / "sneaky_link"
        repo_link.symlink_to(external_target)

        result = classify_path(
            str(repo_link),
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.EXTERNAL

    def test_symlink_within_repo_is_allowed(self, repo_layout: dict[str, str]) -> None:
        """A symlink from one repo location to another is fine."""
        src = Path(repo_layout["repo_root"]) / "src"
        src.mkdir(exist_ok=True)
        target = Path(repo_layout["repo_root"]) / "src" / "real_file.py"
        target.write_text("# code")

        link = Path(repo_layout["repo_root"]) / "link_to_src"
        link.symlink_to(target)

        result = classify_path(
            str(link),
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
        )
        assert result == PathClass.REPO_ROOT


# ---------------------------------------------------------------------------
# require_in_boundary tests
# ---------------------------------------------------------------------------


class TestRequireInBoundary:
    """Tests for require_in_boundary()."""

    def test_allows_repo_root(self, repo_layout: dict[str, str]) -> None:
        result = require_in_boundary(
            repo_layout["repo_root"],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
            emit_event=False,
        )
        assert result == PathClass.REPO_ROOT

    def test_allows_worktree(self, repo_layout: dict[str, str]) -> None:
        result = require_in_boundary(
            repo_layout["worktree_paths"][1],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
            emit_event=False,
        )
        assert result == PathClass.REGISTERED_WORKTREE

    def test_allows_runtime(self, repo_layout: dict[str, str]) -> None:
        result = require_in_boundary(
            repo_layout["runtime_dirs"][0],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
            emit_event=False,
        )
        assert result == PathClass.MANAGED_RUNTIME

    def test_rejects_external(self, repo_layout: dict[str, str]) -> None:
        with pytest.raises(BoundaryViolationError) as exc_info:
            require_in_boundary(
                repo_layout["external"],
                repo_root=repo_layout["repo_root"],
                worktree_paths=repo_layout["worktree_paths"],
                runtime_dirs=repo_layout["runtime_dirs"],
                emit_event=False,
            )
        assert exc_info.value.classification == PathClass.EXTERNAL
        assert repo_layout["external"] in str(exc_info.value)

    def test_allows_explicit_exception(self, repo_layout: dict[str, str]) -> None:
        result = require_in_boundary(
            repo_layout["external"],
            repo_root=repo_layout["repo_root"],
            worktree_paths=repo_layout["worktree_paths"],
            runtime_dirs=repo_layout["runtime_dirs"],
            exceptions=[repo_layout["external"]],
            emit_event=False,
        )
        assert result == PathClass.EXPLICIT_EXCEPTION

    def test_emits_audit_event_on_violation(self, repo_layout: dict[str, str]) -> None:
        """Boundary violation should emit an audit event to the event log."""
        events_dir = Path(repo_layout["events_dir"])

        with pytest.raises(BoundaryViolationError):
            require_in_boundary(
                repo_layout["external"],
                repo_root=repo_layout["repo_root"],
                worktree_paths=repo_layout["worktree_paths"],
                runtime_dirs=repo_layout["runtime_dirs"],
                emit_event=True,
                events_dir=events_dir,
            )

        # Verify event was written
        events_file = events_dir / "events.jsonl"
        assert events_file.exists(), "Expected events.jsonl to be created"

        lines = events_file.read_text().strip().splitlines()
        assert len(lines) >= 1

        event = json.loads(lines[-1])
        assert event["event_type"] == "fs_boundary_violation"
        assert event["payload"]["classification"] == "external"
        assert event["payload"]["action"] == "denied"
        assert repo_layout["external"] in event["payload"]["path"]


# ---------------------------------------------------------------------------
# PathClass enum tests
# ---------------------------------------------------------------------------


class TestPathClassEnum:
    """Basic tests for PathClass values."""

    def test_all_values(self) -> None:
        expected = {
            "repo_root",
            "registered_worktree",
            "managed_runtime",
            "explicit_exception",
            "external",
        }
        actual = {pc.value for pc in PathClass}
        assert actual == expected

    def test_boundary_violation_error_attributes(self) -> None:
        err = BoundaryViolationError("/tmp/evil", PathClass.EXTERNAL)
        assert err.path == "/tmp/evil"
        assert err.classification == PathClass.EXTERNAL
        assert "outside the repo boundary" in str(err)


# ---------------------------------------------------------------------------
# get_repo_boundaries tests
# ---------------------------------------------------------------------------


class TestGetRepoBoundaries:
    """Tests for get_repo_boundaries()."""

    def test_raises_when_no_git_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running from a directory with no .git anywhere above should raise RuntimeError."""
        no_git = tmp_path / "empty"
        no_git.mkdir()
        monkeypatch.chdir(no_git)

        with pytest.raises(RuntimeError, match="Cannot discover repo root"):
            get_repo_boundaries()

    def test_explicit_repo_root_skips_discovery(self, tmp_path: Path) -> None:
        """Passing repo_root explicitly should bypass .git discovery."""
        fake_root = tmp_path / "fake-repo"
        fake_root.mkdir()

        boundaries = get_repo_boundaries(repo_root=fake_root)
        assert boundaries["repo_root"] == str(fake_root.resolve())


# ---------------------------------------------------------------------------
# check_path tests
# ---------------------------------------------------------------------------


class TestCheckPath:
    """Tests for the check_path() convenience wrapper."""

    def test_check_path_in_repo(self, repo_layout: dict[str, str]) -> None:
        """A path inside repo_root should return REPO_ROOT."""
        subpath = Path(repo_layout["repo_root"]) / "src" / "foo.py"
        result = check_path(str(subpath), boundaries=repo_layout)
        assert result == PathClass.REPO_ROOT

    def test_check_path_external(self, repo_layout: dict[str, str]) -> None:
        """A path outside all boundaries should return EXTERNAL."""
        result = check_path(repo_layout["external"], boundaries=repo_layout)
        assert result == PathClass.EXTERNAL

    def test_check_path_with_boundaries(self, repo_layout: dict[str, str]) -> None:
        """Pre-computed boundaries should be used without calling get_repo_boundaries()."""
        wt = repo_layout["worktree_paths"][1]
        subpath = Path(wt) / "some_file.py"
        result = check_path(str(subpath), boundaries=repo_layout)
        assert result == PathClass.REGISTERED_WORKTREE


# ---------------------------------------------------------------------------
# require_path tests
# ---------------------------------------------------------------------------


class TestRequirePath:
    """Tests for the require_path() convenience wrapper."""

    def test_require_path_allows_repo(self, repo_layout: dict[str, str]) -> None:
        """A path inside repo_root should be allowed and return REPO_ROOT."""
        subpath = Path(repo_layout["repo_root"]) / "src" / "bar.py"
        result = require_path(str(subpath), boundaries=repo_layout, emit_event=False)
        assert result == PathClass.REPO_ROOT

    def test_require_path_rejects_external(self, repo_layout: dict[str, str]) -> None:
        """An external path should raise BoundaryViolationError."""
        with pytest.raises(BoundaryViolationError) as exc_info:
            require_path(
                repo_layout["external"], boundaries=repo_layout, emit_event=False
            )
        assert exc_info.value.classification == PathClass.EXTERNAL

    def test_require_path_with_boundaries(self, repo_layout: dict[str, str]) -> None:
        """Pre-computed boundaries should be used; runtime dir should return MANAGED_RUNTIME."""
        runtime = repo_layout["runtime_dirs"][0]
        result = require_path(runtime, boundaries=repo_layout, emit_event=False)
        assert result == PathClass.MANAGED_RUNTIME
