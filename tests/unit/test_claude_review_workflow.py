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

    def test_prompt_contains_review_semantics(self):
        """Prompt must instruct Claude to perform a code review."""
        step = self._review_step()
        prompt = step["with"]["prompt"]
        assert "review" in prompt.lower(), "prompt must mention 'review'"

    def test_max_turns_value(self):
        """Max turns must be explicitly set to a small bound."""
        step = self._review_step()
        claude_args = step["with"]["claude_args"]
        assert (
            claude_args == "--max-turns 5"
        ), f"expected '--max-turns 5', got {claude_args!r}"

    def test_no_continue_on_error(self):
        """Review step must NOT use continue-on-error — failures must be visible."""
        step = self._review_step()
        assert step.get("continue-on-error") is not True

    def test_has_infra_failure_flag_step(self):
        """A follow-up step must create an issue on reviewer infra failure."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        flag_steps = [
            s for s in steps if s.get("name") == "Flag reviewer infra failure"
        ]
        assert len(flag_steps) == 1
        flag_step = flag_steps[0]
        # Must scope to the review step specifically, not blanket failure()
        assert "steps.claude-review.outcome" in flag_step["if"]
        # Must have GH_TOKEN for gh issue create
        assert "GH_TOKEN" in str(flag_step.get("env", {}))

    def _review_step(self):
        """Return the 'Run Claude Code Review' step."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        for s in steps:
            if s.get("id") == "claude-review":
                return s
        raise AssertionError("claude-review step not found")
