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

    def test_prompt_contains_review_semantics(self):
        """Prompt must instruct Claude to perform a code review."""
        step = self._review_step()
        prompt = step["with"]["prompt"]
        assert "review" in prompt.lower(), "prompt must mention 'review'"
        assert "pull request" in prompt.lower(), "prompt must reference pull requests"
        # At least one quality dimension must be specified
        quality_terms = {"quality", "correctness", "security"}
        prompt_lower = prompt.lower()
        found = {t for t in quality_terms if t in prompt_lower}
        assert found, f"prompt must mention at least one of {quality_terms}"
        # Must instruct Claude to post findings as review comments
        assert (
            "review comments" in prompt_lower
        ), "prompt must instruct posting findings as review comments"

    def test_max_turns_value(self):
        """Max turns must be explicitly set to a small bound."""
        step = self._review_step()
        claude_args = step["with"]["claude_args"]
        assert (
            claude_args == "--max-turns 5"
        ), f"expected '--max-turns 5', got {claude_args!r}"

    def _review_step(self):
        """Return the 'Run Claude Code Review' step."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        for s in steps:
            if s.get("id") == "claude-review":
                return s
        raise AssertionError("claude-review step not found")
