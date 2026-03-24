"""Tests for session-sync-worktree.sh hook.

Validates that the session-sync hook only emits stderr output for
WARNING conditions, keeping success paths silent to reduce TUI noise.
See: GitHub issue #1421.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / ".claude"
    / "hooks"
    / "session-sync-worktree.sh"
)


class TestSessionSyncSilentSuccess:
    """Success paths must not emit stderr output (issue #1421)."""

    def test_all_echo_stderr_statements_are_warnings(self) -> None:
        """Every 'echo >&2' in the hook must contain 'WARNING:'."""
        content = HOOK_PATH.read_text()
        # Match lines that echo to stderr (echo >&2)
        echo_stderr_lines = [
            line.strip()
            for line in content.splitlines()
            if re.search(r"\becho\s+>&2\b", line) and not line.strip().startswith("#")
        ]
        assert len(echo_stderr_lines) > 0, "Expected at least one WARNING echo"
        for line in echo_stderr_lines:
            assert (
                "WARNING" in line
            ), f"Non-warning stderr output found (issue #1421): {line}"

    def test_git_reset_silences_stdout(self) -> None:
        """The git reset command must redirect both stdout and stderr (issue #1437)."""
        content = HOOK_PATH.read_text()
        # Find the git reset line
        reset_lines = [
            line.strip()
            for line in content.splitlines()
            if "git" in line and "reset" in line and not line.strip().startswith("#")
        ]
        assert (
            len(reset_lines) == 1
        ), f"Expected 1 git reset line, found {len(reset_lines)}"
        reset_line = reset_lines[0]
        # Must redirect both stdout AND stderr (>/dev/null 2>&1),
        # not just stderr alone (2>/dev/null).  The old pattern
        # "2>/dev/null" is a substring of the correct redirect, so we
        # check for the full pattern to avoid a false-positive.
        assert (
            ">/dev/null 2>&1" in reset_line
        ), f"git reset must redirect stdout+stderr (>/dev/null 2>&1): {reset_line}"

    def test_non_steward_dir_exits_silently(self) -> None:
        """Hook exits 0 with no output when PROJECT_DIR is not a steward dir."""
        import os

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = "/tmp/plain-project-dir"

        result = subprocess.run(
            ["bash", str(HOOK_PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""
        assert result.stderr.strip() == ""
