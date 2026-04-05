"""Unit tests for the block-runtime-writes PreToolUse hook.

The hook blocks Edit/Write tool calls targeting .claude/runtime/ paths
to prevent permission stalls in autonomous fleet operation. Checked-in
README.md schema docs are exempted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_SH = REPO_ROOT / ".claude" / "hooks" / "block-runtime-writes.sh"


def _run_hook(file_path: str) -> subprocess.CompletedProcess[str]:
    """Run the hook with a simulated tool_input payload."""
    payload = json.dumps({"tool_input": {"file_path": file_path}})
    return subprocess.run(
        ["bash", str(HOOK_SH)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
    )


# ---------------------------------------------------------------------------
# Blocked paths (exit 2)
# ---------------------------------------------------------------------------


class TestBlockedPaths:
    """Runtime state files must be blocked."""

    def test_relative_runtime_file(self) -> None:
        r = _run_hook(".claude/runtime/review_state/last_merged_pr.txt")
        assert r.returncode == 2
        assert "BLOCKED" in r.stdout

    def test_absolute_runtime_file(self) -> None:
        r = _run_hook("/home/user/project/.claude/runtime/task_queue/packet.json")
        assert r.returncode == 2
        assert "BLOCKED" in r.stdout

    def test_runtime_root_file(self) -> None:
        r = _run_hook(".claude/runtime/permission_denials.jsonl")
        assert r.returncode == 2
        assert "BLOCKED" in r.stdout

    def test_deeply_nested_runtime_file(self) -> None:
        r = _run_hook(".claude/runtime/review_loops/pr_42/state.json")
        assert r.returncode == 2
        assert "BLOCKED" in r.stdout

    def test_arbitrary_subdir_readme_blocked(self) -> None:
        """README.md in an untracked subdirectory must be blocked (#2431)."""
        r = _run_hook(".claude/runtime/arbitrary_new_dir/README.md")
        assert r.returncode == 2
        assert "BLOCKED" in r.stdout

    def test_absolute_arbitrary_subdir_readme_blocked(self) -> None:
        """Absolute path to README.md in untracked subdir must be blocked (#2431)."""
        r = _run_hook("/home/user/project/.claude/runtime/unknown_dir/README.md")
        assert r.returncode == 2
        assert "BLOCKED" in r.stdout


# ---------------------------------------------------------------------------
# Exempt paths — checked-in README.md docs (exit 0)
# ---------------------------------------------------------------------------


class TestExemptReadmePaths:
    """Checked-in README.md schema docs should pass through."""

    def test_top_level_readme(self) -> None:
        r = _run_hook(".claude/runtime/README.md")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_subdirectory_readme(self) -> None:
        r = _run_hook(".claude/runtime/events/README.md")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_worktree_registry_readme(self) -> None:
        r = _run_hook(".claude/runtime/worktree_registry/README.md")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_absolute_path_readme(self) -> None:
        r = _run_hook("/home/user/project/.claude/runtime/session_metadata/README.md")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_absolute_top_level_readme(self) -> None:
        r = _run_hook("/home/user/project/.claude/runtime/README.md")
        assert r.returncode == 0
        assert r.stdout == ""


# ---------------------------------------------------------------------------
# Allowed non-runtime paths (exit 0)
# ---------------------------------------------------------------------------


class TestAllowedPaths:
    """Paths outside .claude/runtime/ should always be allowed."""

    def test_source_file(self) -> None:
        r = _run_hook("src/bid_euchre/ops/foo.py")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_claude_settings(self) -> None:
        r = _run_hook(".claude/settings.json")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_claude_rules(self) -> None:
        r = _run_hook(".claude/rules/10_workflow.md")
        assert r.returncode == 0
        assert r.stdout == ""

    def test_empty_path(self) -> None:
        """Empty file_path should exit 0 (not our concern)."""
        payload = json.dumps({"tool_input": {"file_path": ""}})
        r = subprocess.run(
            ["bash", str(HOOK_SH)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode == 0

    def test_missing_file_path(self) -> None:
        """Missing file_path key should exit 0."""
        payload = json.dumps({"tool_input": {}})
        r = subprocess.run(
            ["bash", str(HOOK_SH)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert r.returncode == 0
