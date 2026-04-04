"""Tests for fleet-check-autostart.sh SessionStart hook.

Validates the two guards added in #2375:
1. Only fires when CLAUDE_AGENT_NAME=orchestrator (no directory fallback).
2. Skips when the inhibit marker file exists (respects intentional park).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
SCRIPT = HOOKS_DIR / "fleet-check-autostart.sh"


def _run_autostart(
    agent_name: str | None = None,
    project_dir: str | None = None,
) -> tuple[int, str]:
    """Run the fleet-check-autostart hook and return (exit_code, stdout)."""
    env = os.environ.copy()
    if agent_name is not None:
        env["CLAUDE_AGENT_NAME"] = agent_name
    else:
        env.pop("CLAUDE_AGENT_NAME", None)

    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    else:
        # Use a temp-like path that won't match "Bid-Euchre"
        env["CLAUDE_PROJECT_DIR"] = "/tmp/test-project"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )
    return result.returncode, result.stdout.strip()


class TestOrchestratorGuard:
    """Only the orchestrator lane should receive the directive."""

    def test_orchestrator_gets_directive(self):
        rc, stdout = _run_autostart(agent_name="orchestrator")
        assert rc == 0
        assert "FLEET-CHECK AUTO-START" in stdout

    def test_non_orchestrator_skips(self):
        rc, stdout = _run_autostart(agent_name="author-a")
        assert rc == 0
        assert stdout == ""

    def test_empty_agent_name_skips(self):
        """No CLAUDE_AGENT_NAME set — should NOT fallback to directory."""
        rc, stdout = _run_autostart(agent_name="")
        assert rc == 0
        assert stdout == ""

    def test_unset_agent_name_skips(self):
        """CLAUDE_AGENT_NAME not in env at all — should NOT fallback."""
        rc, stdout = _run_autostart(agent_name=None)
        assert rc == 0
        assert stdout == ""

    def test_main_checkout_without_agent_name_skips(self):
        """Session in Bid-Euchre directory but no agent name — not orchestrator."""
        rc, stdout = _run_autostart(
            agent_name=None, project_dir="/some/path/Bid-Euchre"
        )
        assert rc == 0
        assert stdout == ""


class TestInhibitMarker:
    """The inhibit marker suppresses autostart after intentional park."""

    def test_inhibit_marker_suppresses_directive(self, tmp_path: Path):
        # Set up a fake project dir with the inhibit marker
        runtime_dir = tmp_path / ".claude" / "runtime"
        runtime_dir.mkdir(parents=True)
        (runtime_dir / "fleet-check-inhibit").touch()

        rc, stdout = _run_autostart(
            agent_name="orchestrator", project_dir=str(tmp_path)
        )
        assert rc == 0
        assert stdout == ""

    def test_no_inhibit_marker_allows_directive(self, tmp_path: Path):
        # Set up a fake project dir without the inhibit marker
        runtime_dir = tmp_path / ".claude" / "runtime"
        runtime_dir.mkdir(parents=True)

        rc, stdout = _run_autostart(
            agent_name="orchestrator", project_dir=str(tmp_path)
        )
        assert rc == 0
        assert "FLEET-CHECK AUTO-START" in stdout
