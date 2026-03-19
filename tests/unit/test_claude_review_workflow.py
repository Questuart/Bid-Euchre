"""Regression tests for .github/workflows/claude-code-review.yml structure."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github/workflows/claude-code-review.yml"
)


class TestClaudeReviewWorkflow:
    """Validate claude-code-review.yml has the expected structure."""

    def setup_method(self):
        self.cfg = yaml.safe_load(WORKFLOW.read_text())

    def test_uses_v1_action(self):
        step = self._review_step()
        assert step["uses"] == "anthropics/claude-code-action@v1"

    def test_has_oauth_token(self):
        step = self._review_step()
        with_block = step["with"]
        assert "claude_code_oauth_token" in with_block

    def test_no_plugin_marketplaces(self):
        """plugin_marketplaces causes 'claude not found' errors on runners."""
        step = self._review_step()
        with_block = step["with"]
        assert "plugin_marketplaces" not in with_block
        assert "plugins" not in with_block

    def test_has_prompt(self):
        step = self._review_step()
        assert "prompt" in step["with"]

    def test_has_max_turns(self):
        step = self._review_step()
        assert "claude_args" in step["with"]
        assert "--max-turns" in step["with"]["claude_args"]

    def _review_step(self):
        """Return the 'Run Claude Code Review' step."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        for s in steps:
            if s.get("id") == "claude-review":
                return s
        raise AssertionError("claude-review step not found")
