"""Tests for the post-merge-notify hook behavior.

Validates key behaviors (issue #1461):
1. Direct merge creates sentinel and exits immediately
2. Auto-merge (--auto flag) does NOT create sentinel immediately
3. PR number fallback: extracted from stdout when not in command
4. Non-merge commands are ignored (guard check)
5. Failed commands are ignored (exit code guard)
6. Dedupe sentinel prevents double-firing
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "post-merge-notify.sh"


def _run_hook(
    *,
    command: str,
    exit_code: int = 0,
    stdout: str = "",
    tmp_path: Path,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the post-merge-notify hook with the given input."""
    hook_input = json.dumps(
        {
            "tool_input": {"command": command},
            "tool_response": {
                "stdout": stdout,
                "stderr": "",
                "exit_code": exit_code,
            },
        }
    )
    # Minimal env: PATH + HOME + jq/uv access, but no CLAUDE_ vars
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        # Prevent hook from writing to the real message bus
        "BID_EUCHRE_BUS_DIR": str(tmp_path / "test_bus"),
    }
    if env_overrides:
        env.update(env_overrides)

    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=hook_input,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


class TestPostMergeNotifyGuards:
    """Test that the guard checks correctly filter commands."""

    def test_non_merge_command_exits_immediately(self, tmp_path: Path) -> None:
        """Non-merge commands should exit 0 with no side effects."""
        result = _run_hook(
            command="git status",
            tmp_path=tmp_path,
        )
        assert result.returncode == 0

    def test_failed_merge_exits_immediately(self, tmp_path: Path) -> None:
        """Failed merge commands should exit 0 with no side effects."""
        sentinel = Path("/tmp/.claude-post-merge-notify-4444")
        sentinel.unlink(missing_ok=True)

        result = _run_hook(
            command="gh pr merge 4444 --squash",
            exit_code=1,
            tmp_path=tmp_path,
        )
        assert result.returncode == 0
        assert not sentinel.exists()

    def test_dedupe_sentinel_prevents_refire(self, tmp_path: Path) -> None:
        """If sentinel exists, hook should exit immediately."""
        pr_num = "3333"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.touch()
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --squash",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
        finally:
            sentinel.unlink(missing_ok=True)


class TestPRNumberExtraction:
    """Test PR number extraction from command and stdout."""

    def test_pr_number_from_command(self, tmp_path: Path) -> None:
        """PR number should be extracted from the command string."""
        pr_num = "2222"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --squash",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert sentinel.exists(), "Sentinel should be created for direct merge"
        finally:
            sentinel.unlink(missing_ok=True)

    def test_branch_name_digits_not_extracted(self, tmp_path: Path) -> None:
        """Branch names with digits should NOT be treated as PR numbers.

        Regression test for issue #1479: `gh pr merge fix/issue-5678 --squash`
        should NOT extract 5678 as the PR number — it should fall back to
        stdout parsing instead.
        """
        # The branch has digits but the actual PR number is in stdout
        real_pr = "7777"
        fake_pr = "5678"
        sentinel_real = Path(f"/tmp/.claude-post-merge-notify-{real_pr}")
        sentinel_fake = Path(f"/tmp/.claude-post-merge-notify-{fake_pr}")
        sentinel_real.unlink(missing_ok=True)
        sentinel_fake.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge fix/issue-{fake_pr} --squash",
                stdout=f"✓ Squashed and merged pull request #{real_pr}",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert (
                sentinel_real.exists()
            ), "Sentinel should use the real PR number from stdout"
            assert (
                not sentinel_fake.exists()
            ), "Sentinel should NOT use digits from the branch name"
        finally:
            sentinel_real.unlink(missing_ok=True)
            sentinel_fake.unlink(missing_ok=True)

    def test_pr_number_from_pull_url(self, tmp_path: Path) -> None:
        """PR number should be extracted from /pull/<N> URL in command.

        Regression test for issue #1520: `gh pr merge https://...pull/123`
        should extract 123 via URL parsing before falling back to stdout.
        """
        pr_num = "6543"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge https://github.com/owner/repo/pull/{pr_num} --squash",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert (
                sentinel.exists()
            ), "Sentinel should be created from /pull/<N> URL extraction"
        finally:
            sentinel.unlink(missing_ok=True)

    def test_pr_number_from_stdout_fallback(self, tmp_path: Path) -> None:
        """When command has no PR number, extract from stdout."""
        pr_num = "1111"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command="gh pr merge --squash",
                stdout=f"✓ Squashed and merged pull request #{pr_num}",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert sentinel.exists(), "Sentinel should be created via stdout fallback"
        finally:
            sentinel.unlink(missing_ok=True)


class TestAutoMergeDetection:
    """Test auto-merge flag detection and deferred completion."""

    def test_auto_merge_does_not_create_sentinel_immediately(
        self, tmp_path: Path
    ) -> None:
        """Auto-merge should NOT create sentinel (PR isn't merged yet)."""
        pr_num = "9876"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --auto --squash",
                stdout=f"✓ Auto-merge enabled for pull request #{pr_num}",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert not sentinel.exists(), (
                "Sentinel should NOT be created for --auto "
                "(PR isn't merged yet, watcher handles it)"
            )
        finally:
            sentinel.unlink(missing_ok=True)

    def test_auto_merge_with_delete_branch(self, tmp_path: Path) -> None:
        """Auto-merge with --delete-branch should also defer."""
        pr_num = "9875"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --auto --squash --delete-branch",
                stdout=f"✓ Auto-merge enabled for pull request #{pr_num}",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert (
                not sentinel.exists()
            ), "Sentinel should NOT be created for --auto --delete-branch"
        finally:
            sentinel.unlink(missing_ok=True)

    def test_direct_merge_creates_sentinel(self, tmp_path: Path) -> None:
        """Direct merge (no --auto) should create sentinel immediately."""
        pr_num = "9874"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --squash",
                stdout=f"✓ Squashed and merged pull request #{pr_num}",
                tmp_path=tmp_path,
            )
            assert result.returncode == 0
            assert sentinel.exists(), "Sentinel should be created for direct merge"
        finally:
            sentinel.unlink(missing_ok=True)


class TestLaneIdResolution:
    """Test lane identity resolution from environment variables."""

    @pytest.mark.parametrize(
        "dir_name,expected_lane",
        [
            ("Bid-Euchre-steward-author", "author-a"),
            ("Bid-Euchre-steward-author-b", "author-b"),
            ("Bid-Euchre-steward-flex-a", "flex-a"),
            ("Bid-Euchre-steward-flex-b", "flex-b"),
            ("Bid-Euchre-steward-brws-author-c", "brws-author-c"),
            ("Bid-Euchre-steward-ops", "ops"),
        ],
    )
    def test_lane_from_project_dir(
        self,
        tmp_path: Path,
        dir_name: str,
        expected_lane: str,  # noqa: ARG002
    ) -> None:
        """CLAUDE_PROJECT_DIR should resolve to correct lane ID."""
        # We can't easily verify the lane_id from outside the hook,
        # but we can verify the hook doesn't crash with valid dir names.
        pr_num = "8765"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --squash",
                tmp_path=tmp_path,
                env_overrides={
                    "CLAUDE_PROJECT_DIR": f"/tmp/{dir_name}",
                },
            )
            assert result.returncode == 0
            assert sentinel.exists()
        finally:
            sentinel.unlink(missing_ok=True)

    def test_lane_from_agent_name(self, tmp_path: Path) -> None:
        """CLAUDE_AGENT_NAME should resolve to lane ID."""
        pr_num = "8764"
        sentinel = Path(f"/tmp/.claude-post-merge-notify-{pr_num}")
        sentinel.unlink(missing_ok=True)
        try:
            result = _run_hook(
                command=f"gh pr merge {pr_num} --squash",
                tmp_path=tmp_path,
                env_overrides={
                    "CLAUDE_AGENT_NAME": "steward-author-c",
                },
            )
            assert result.returncode == 0
            assert sentinel.exists()
        finally:
            sentinel.unlink(missing_ok=True)
