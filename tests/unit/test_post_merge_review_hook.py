"""Tests for the post-merge-review hook scope constraints.

Validates three key behaviors:
1. Docs/plans-only PRs are skipped (no review triggered)
2. Code PRs trigger review with explicit file list
3. Dedupe sentinel prevents double-firing
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "post-merge-review.sh"


def _run_hook(
    *,
    command: str,
    exit_code: int = 0,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Run the post-merge-review hook with the given input."""
    hook_input = json.dumps(
        {
            "tool_input": {"command": command},
            "tool_response": {"exit_code": exit_code},
        }
    )
    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=hook_input,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with a merge commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "t@t.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    # Initial commit on main
    (repo / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=repo, capture_output=True, check=True
    )
    return repo


def _add_files_and_commit(repo: Path, files: dict[str, str], message: str) -> None:
    """Add files to repo and commit."""
    for path, content in files.items():
        full_path = repo / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", message], cwd=repo, capture_output=True, check=True
    )


def _make_env(repo: Path, tmp_path: Path) -> dict[str, str]:
    """Build env dict for hook execution."""
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    # Clean up any stale sentinels
    for f in Path("/tmp").glob(".claude-post-merge-review-*"):
        f.unlink(missing_ok=True)
    return env


class TestDocsOnlySkip:
    """Docs/plans-only PRs should produce no output (review skipped)."""

    def test_docs_only_pr_skipped(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        # Simulate a docs-only merge commit
        _add_files_and_commit(
            repo,
            {
                "docs/04_reports/r0/manifest.md": "# Manifest\n",
                "plans/sessions/foo.md": "# Plan\n",
            },
            "docs-only merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 999",
            cwd=repo,
            env=env,
        )
        # No hookSpecificOutput means review was skipped
        assert "hookSpecificOutput" not in result.stdout

    def test_mixed_docs_and_code_triggers_review(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {
                "docs/report.md": "# Report\n",
                "src/bid_euchre/foo.py": "x = 1\n",
            },
            "mixed merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 888",
            cwd=repo,
            env=env,
        )
        assert "hookSpecificOutput" in result.stdout


class TestCodePRTriggersReview:
    """Code PRs should trigger review with explicit file list."""

    def test_src_files_trigger_review(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {"src/bid_euchre/core/rules.py": "# rules\n"},
            "code merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 777",
            cwd=repo,
            env=env,
        )
        output = result.stdout
        assert "hookSpecificOutput" in output
        assert "PR #777" in output

    def test_test_files_trigger_review(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {"tests/unit/test_rules.py": "# tests\n"},
            "test merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 776",
            cwd=repo,
            env=env,
        )
        assert "hookSpecificOutput" in result.stdout

    def test_scripts_files_trigger_review(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {"scripts/internal/run.py": "# script\n"},
            "script merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 775",
            cwd=repo,
            env=env,
        )
        assert "hookSpecificOutput" in result.stdout

    def test_output_contains_scope_constraint_language(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {"src/bid_euchre/foo.py": "x = 1\n"},
            "code merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 774",
            cwd=repo,
            env=env,
        )
        output = result.stdout
        # Verify scope constraint language is present
        assert "ONLY review" in output or "SCOPE" in output
        assert "Changed files" in output
        assert "Do NOT" in output or "do NOT" in output

    def test_output_includes_changed_file_paths(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {
                "src/bid_euchre/core/rules.py": "# rules\n",
                "tests/unit/test_rules.py": "# tests\n",
            },
            "code merge",
        )
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 773",
            cwd=repo,
            env=env,
        )
        output = result.stdout
        assert "src/bid_euchre/core/rules.py" in output
        assert "tests/unit/test_rules.py" in output


class TestNonMergeSkip:
    """Non-merge commands should produce no output."""

    def test_non_merge_command_skipped(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr create --title foo",
            cwd=repo,
            env=env,
        )
        assert "hookSpecificOutput" not in result.stdout

    def test_failed_merge_skipped(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        env = _make_env(repo, tmp_path)
        result = _run_hook(
            command="gh pr merge 999",
            exit_code=1,
            cwd=repo,
            env=env,
        )
        assert "hookSpecificOutput" not in result.stdout


class TestDeduplication:
    """Sentinel file prevents double-firing."""

    def test_dedupe_sentinel_prevents_second_fire(self, tmp_path: Path) -> None:
        repo = _make_git_repo(tmp_path)
        _add_files_and_commit(
            repo,
            {"src/bid_euchre/foo.py": "x = 1\n"},
            "code merge",
        )
        env = _make_env(repo, tmp_path)

        # First call should trigger
        result1 = _run_hook(command="gh pr merge 772", cwd=repo, env=env)
        assert "hookSpecificOutput" in result1.stdout

        # Second call should be deduped
        result2 = _run_hook(command="gh pr merge 772", cwd=repo, env=env)
        assert "hookSpecificOutput" not in result2.stdout

        # Clean up sentinel
        Path("/tmp/.claude-post-merge-review-772").unlink(missing_ok=True)
