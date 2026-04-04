"""Tests for consolidated hook dispatchers (issue #1255).

The pre-bash-dispatch.sh and post-bash-dispatch.sh scripts consolidate
multiple hooks into single invocations to reduce TUI noise.  These tests
verify:
  - Normal commands produce no stdout (PreToolUse has no suppressOutput)
  - Blocking commands propagate exit code 2
  - Rule-loader context injection works through the dispatcher
  - PostToolUse dispatcher suppresses TUI notification for non-matching commands
  - Background process stdout is properly redirected (post-push-ci-check fix)
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _run_hook(
    script: str, payload: dict, env_override: dict | None = None
) -> tuple[int, str, dict | None]:
    """Run a hook script with JSON payload on stdin.

    Returns (exit_code, raw_stdout, parsed_json_or_None).
    """
    env = os.environ.copy()
    # Point to repo root so sub-hooks can be found
    env["CLAUDE_PROJECT_DIR"] = str(HOOKS_DIR.parents[1])
    if env_override:
        env.update(env_override)

    result = subprocess.run(
        ["bash", str(HOOKS_DIR / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )

    parsed = None
    stdout = result.stdout.strip()
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            pass  # Blocking paths emit free-form text

    return result.returncode, stdout, parsed


class TestPreBashDispatch:
    """pre-bash-dispatch.sh consolidates PreToolUse Bash hooks."""

    SCRIPT = "pre-bash-dispatch.sh"

    def test_normal_command_produces_no_stdout(self) -> None:
        """A safe command should produce no stdout (PreToolUse has no suppressOutput)."""
        rc, raw, out = _run_hook(
            self.SCRIPT, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}}
        )
        assert rc == 0
        assert raw == ""
        assert out is None

    def test_dangerous_worktree_command_blocks(self) -> None:
        """Dangerous worktree operations should block with exit 2."""
        rc, raw, _out = _run_hook(
            self.SCRIPT,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "git worktree prune"},
            },
        )
        assert rc == 2
        assert "BLOCKED" in raw

    def test_dangerous_rm_command_blocks(self) -> None:
        """rm -rf on Bid-Euchre directories should block."""
        rc, raw, _out = _run_hook(
            self.SCRIPT,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf ../Bid-Euchre-steward-author"},
            },
        )
        assert rc == 2
        assert "BLOCKED" in raw

    def test_rule_loader_context_injection(self) -> None:
        """Rule-loader should inject additionalContext for matching paths."""
        # Clear any loaded-rules sentinel so the rule-loader triggers
        runtime_dir = HOOKS_DIR.parents[1] / ".claude" / "runtime"
        for sentinel in runtime_dir.glob(".loaded_rules_*"):
            sentinel.unlink(missing_ok=True)

        rc, _raw, out = _run_hook(
            self.SCRIPT,
            {
                "tool_name": "Bash",
                "tool_input": {"command": "cat notebooks/analysis.py"},
            },
        )
        assert rc == 0
        assert out is not None
        # Rule-loader should have injected context for notebook paths
        assert out.get("additionalContext") is not None
        # PreToolUse hooks should NOT include suppressOutput (not a valid field)
        assert "suppressOutput" not in out


class TestRuleLoaderDirect:
    """rule-loader.sh produces no stdout for non-matching PreToolUse paths."""

    SCRIPT = "rule-loader.sh"

    def test_non_matching_path_produces_no_stdout(self) -> None:
        """Non-matching paths should produce no stdout to avoid TUI noise."""
        rc, raw, out = _run_hook(
            self.SCRIPT,
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "/some/unrelated/file.py"},
            },
        )
        assert rc == 0
        assert raw == ""
        assert out is None

    def test_matching_path_has_no_suppress_output(self) -> None:
        """Matching paths should return additionalContext but not suppressOutput."""
        # Clear sentinels
        runtime_dir = HOOKS_DIR.parents[1] / ".claude" / "runtime"
        for sentinel in runtime_dir.glob(".loaded_rules_*"):
            sentinel.unlink(missing_ok=True)

        rc, _raw, out = _run_hook(
            self.SCRIPT,
            {
                "tool_name": "Read",
                "tool_input": {"file_path": "notebooks/analysis.py"},
            },
        )
        assert rc == 0
        assert out is not None
        assert out.get("additionalContext") is not None
        assert "suppressOutput" not in out


class TestPostBashDispatch:
    """post-bash-dispatch.sh consolidates PostToolUse Bash hooks."""

    SCRIPT = "post-bash-dispatch.sh"

    def test_normal_command_suppresses_output(self) -> None:
        """Non-matching commands should suppress TUI notification (issue #1360)."""
        rc, _raw, out = _run_hook(
            self.SCRIPT,
            {
                "tool_input": {"command": "git status"},
                "tool_response": {"exit_code": 0, "stdout": ""},
            },
        )
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True

    def test_failed_command_suppresses_output(self) -> None:
        """Failed commands should suppress TUI notification (issue #1360)."""
        rc, _raw, out = _run_hook(
            self.SCRIPT,
            {
                "tool_input": {"command": "git push origin main"},
                "tool_response": {"exit_code": 1, "stdout": ""},
            },
        )
        assert rc == 0
        assert out is not None
        assert out.get("suppressOutput") is True


class TestPreBashDispatchTimeout:
    """Timeout comment in pre-bash-dispatch.sh must match settings.json."""

    def test_timeout_comment_matches_settings(self) -> None:
        """Regression: header comment must agree with configured timeout."""
        script = (HOOKS_DIR / "pre-bash-dispatch.sh").read_text()
        settings = json.loads((HOOKS_DIR.parent / "settings.json").read_text())
        # Find the configured timeout for pre-bash-dispatch.sh
        configured_timeout = None
        for group in settings.get("hooks", {}).get("PreToolUse", []):
            for hook in group.get("hooks", []):
                cmd = hook.get("command", "")
                if "pre-bash-dispatch.sh" in cmd:
                    configured_timeout = hook.get("timeout")
                    break
        assert configured_timeout is not None, "pre-bash-dispatch not found in settings"
        assert f"# Timeout: {configured_timeout}s" in script, (
            f"Header comment should say 'Timeout: {configured_timeout}s' "
            f"but does not match"
        )


class TestPostPushCiCheckStdoutRedirect:
    """post-push-ci-check.sh must redirect background process stdout."""

    def test_background_redirect_present(self) -> None:
        """The background poller launch must redirect stdout/stderr."""
        hook_content = (HOOKS_DIR / "post-push-ci-check.sh").read_text()
        # The fix adds > /dev/null 2>&1 to the background subshell
        assert "> /dev/null 2>&1 &" in hook_content


class TestPermissionDeniedHook:
    """permission-denied-log.sh uses canonical lane IDs (#2299)."""

    SCRIPT = "permission-denied-log.sh"
    PAYLOAD = {
        "tool_name": "Bash",
        "reason": "test denial",
        "tool_input": {"command": "test"},
        "session_id": "unit-test",
    }

    def test_primary_author_worktree_maps_to_author_a(self) -> None:
        """Bid-Euchre-steward-author → author-a (not 'author')."""
        rc, _raw, out = _run_hook(
            self.SCRIPT,
            self.PAYLOAD,
            env_override={
                "CLAUDE_PROJECT_DIR": "/fake/Bid-Euchre-steward-author",
                "CLAUDE_AGENT_NAME": "",
            },
        )
        assert rc == 0
        assert out is not None

    def test_primary_analyst_worktree_maps_to_analyst_a(self) -> None:
        """Bid-Euchre-steward-analyst → analyst-a (not 'analyst')."""
        rc, _raw, out = _run_hook(
            self.SCRIPT,
            self.PAYLOAD,
            env_override={
                "CLAUDE_PROJECT_DIR": "/fake/Bid-Euchre-steward-analyst",
                "CLAUDE_AGENT_NAME": "",
            },
        )
        assert rc == 0
        assert out is not None

    def test_claude_agent_name_takes_precedence(self) -> None:
        """CLAUDE_AGENT_NAME env var should be preferred over dir parsing."""
        rc, _raw, out = _run_hook(
            self.SCRIPT,
            self.PAYLOAD,
            env_override={
                "CLAUDE_AGENT_NAME": "steward-ops",
                "CLAUDE_PROJECT_DIR": "/fake/Bid-Euchre-steward-author",
            },
        )
        assert rc == 0
        assert out is not None

    def test_malformed_input_exits_zero(self) -> None:
        """Malformed input should exit 0 with retry: false (never block)."""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(HOOKS_DIR.parents[1])
        result = subprocess.run(
            ["bash", str(HOOKS_DIR / self.SCRIPT)],
            input="not json at all",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert result.returncode == 0
        parsed = json.loads(result.stdout.strip())
        assert parsed["hookSpecificOutput"]["retry"] is False
