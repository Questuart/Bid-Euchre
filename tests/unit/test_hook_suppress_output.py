"""Tests for PreToolUse hook silent exit on happy paths.

PreToolUse hooks must produce NO stdout on their exit-0 code paths to
avoid noisy "Async hook PreToolUse completed" messages.  Unlike PostToolUse
hooks, PreToolUse hooks have no suppressOutput field — any stdout triggers
Claude Code's default completion notification.

Blocking paths (exit 2) may emit free-form text to explain the block.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _run_hook(
    script: str, payload: dict, env_override: dict | None = None
) -> tuple[int, str, dict | None]:
    """Run a hook script with JSON payload on stdin.

    Returns (exit_code, raw_stdout, parsed_json_or_None).
    """
    import os

    env = os.environ.copy()
    if env_override:
        env.update(env_override)

    result = subprocess.run(
        ["bash", str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )

    parsed = None
    stdout = result.stdout.strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pass  # Blocking paths emit free-form text, not JSON

    return result.returncode, stdout, parsed


class TestRuleLoaderSilentExit:
    """rule-loader.sh must emit NO stdout on all exit-0 non-matching paths."""

    SCRIPT = "rule-loader.sh"

    def test_unmatched_tool_produces_no_stdout(self) -> None:
        """Glob tool doesn't match any case arm — should be silent."""
        rc, raw, _out = _run_hook(self.SCRIPT, {"tool_name": "Glob", "tool_input": {}})
        assert rc == 0
        assert raw == ""

    def test_empty_file_path_produces_no_stdout(self) -> None:
        """Read with empty file_path triggers early exit — should be silent."""
        rc, raw, _out = _run_hook(
            self.SCRIPT, {"tool_name": "Read", "tool_input": {"file_path": ""}}
        )
        assert rc == 0
        assert raw == ""

    def test_no_rules_matched_produces_no_stdout(self) -> None:
        """Read on a path that doesn't trigger any rule pattern — should be silent."""
        rc, raw, _out = _run_hook(
            self.SCRIPT,
            {"tool_name": "Read", "tool_input": {"file_path": "/tmp/unrelated.txt"}},
        )
        assert rc == 0
        assert raw == ""


class TestPreWorktreeCleanupSilentExit:
    """pre-worktree-cleanup.sh must produce no stdout on non-matching paths."""

    SCRIPT = "pre-worktree-cleanup.sh"

    def test_empty_command_produces_no_stdout(self) -> None:
        """Non-Bash tool input (no command field) — should be silent."""
        rc, raw, _out = _run_hook(self.SCRIPT, {"tool_name": "Read", "tool_input": {}})
        assert rc == 0
        assert raw == ""

    def test_safe_command_produces_no_stdout(self) -> None:
        """Safe bash command that doesn't match any dangerous pattern — silent."""
        rc, raw, _out = _run_hook(
            self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        )
        assert rc == 0
        assert raw == ""

    def test_dangerous_command_blocks_without_suppress(self) -> None:
        """Dangerous worktree command should block (exit 2) with text."""
        rc, raw, _out = _run_hook(
            self.SCRIPT,
            {"tool_name": "Bash", "tool_input": {"command": "git worktree prune"}},
        )
        assert rc == 2
        assert "BLOCKED" in raw


class TestPreMergeReviewGuardSilentExit:
    """pre-merge-review-guard.sh must produce no stdout on non-merge commands."""

    SCRIPT = "pre-merge-review-guard.sh"

    def test_empty_command_produces_no_stdout(self) -> None:
        """Non-Bash tool input (no command field) — should be silent."""
        rc, raw, _out = _run_hook(self.SCRIPT, {"tool_name": "Read", "tool_input": {}})
        assert rc == 0
        assert raw == ""

    def test_non_merge_command_produces_no_stdout(self) -> None:
        """Regular bash command that isn't gh pr merge — should be silent."""
        rc, raw, _out = _run_hook(
            self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        )
        assert rc == 0
        assert raw == ""
