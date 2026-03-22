"""Tests for PreToolUse hook suppressOutput on happy paths.

Each PreToolUse hook must output {"suppressOutput": true} on its exit-0
code paths to avoid noisy "Async hook PreToolUse completed" messages.
Blocking paths (exit 2) must NOT emit suppressOutput.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _run_hook(
    script: str, payload: dict, env_override: dict | None = None
) -> tuple[int, dict | None]:
    """Run a hook script with JSON payload on stdin.

    Returns (exit_code, parsed_json_or_None).
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

    return result.returncode, parsed


class TestRuleLoaderSuppressOutput:
    """rule-loader.sh must emit suppressOutput on all exit-0 paths."""

    SCRIPT = "rule-loader.sh"

    def test_unmatched_tool_emits_suppress(self) -> None:
        """Glob tool doesn't match any case arm."""
        rc, out = _run_hook(self.SCRIPT, {"tool_name": "Glob", "tool_input": {}})
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True

    def test_empty_file_path_emits_suppress(self) -> None:
        """Read with empty file_path triggers early exit."""
        rc, out = _run_hook(
            self.SCRIPT, {"tool_name": "Read", "tool_input": {"file_path": ""}}
        )
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True

    def test_no_rules_matched_emits_suppress(self) -> None:
        """Read on a path that doesn't trigger any rule pattern."""
        rc, out = _run_hook(
            self.SCRIPT,
            {"tool_name": "Read", "tool_input": {"file_path": "/tmp/unrelated.txt"}},
        )
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True


class TestPreWorktreeCleanupSuppressOutput:
    """pre-worktree-cleanup.sh must emit suppressOutput on non-matching paths."""

    SCRIPT = "pre-worktree-cleanup.sh"

    def test_empty_command_emits_suppress(self) -> None:
        """Non-Bash tool input (no command field)."""
        rc, out = _run_hook(self.SCRIPT, {"tool_name": "Read", "tool_input": {}})
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True

    def test_safe_command_emits_suppress(self) -> None:
        """Safe bash command that doesn't match any dangerous pattern."""
        rc, out = _run_hook(
            self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        )
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True

    def test_dangerous_command_blocks_without_suppress(self) -> None:
        """Dangerous worktree command should block (exit 2) without suppressOutput."""
        rc, out = _run_hook(
            self.SCRIPT,
            {"tool_name": "Bash", "tool_input": {"command": "git worktree prune"}},
        )
        assert rc == 2
        # Blocking path emits human-readable text, not JSON with suppressOutput
        assert out is None or out.get("suppressOutput") is not True


class TestPreMergeReviewGuardSuppressOutput:
    """pre-merge-review-guard.sh must emit suppressOutput on non-merge commands."""

    SCRIPT = "pre-merge-review-guard.sh"

    def test_empty_command_emits_suppress(self) -> None:
        """Non-Bash tool input (no command field)."""
        rc, out = _run_hook(self.SCRIPT, {"tool_name": "Read", "tool_input": {}})
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True

    def test_non_merge_command_emits_suppress(self) -> None:
        """Regular bash command that isn't gh pr merge."""
        rc, out = _run_hook(
            self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        )
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True
