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

    def test_uses_code_review_plugin(self):
        """Workflow uses the code-review plugin via marketplace."""
        step = self._review_step()
        with_block = step["with"]
        assert "plugin_marketplaces" in with_block
        assert "plugins" in with_block
        assert "code-review" in with_block["plugins"]

    def test_prompt_invokes_code_review_skill(self):
        """Prompt invokes the /code-review skill with the PR reference."""
        step = self._review_step()
        prompt = step["with"]["prompt"]
        assert "/code-review" in prompt, "prompt must invoke the code-review skill"
        assert "pull" in prompt.lower(), "prompt must reference the pull request"

    def test_no_continue_on_error(self):
        """Review step must NOT use continue-on-error — failures must be visible."""
        step = self._review_step()
        assert step.get("continue-on-error") is not True

    def test_permissions_are_read_only(self):
        """Permissions must be read-only (no write access to contents)."""
        permissions = self.cfg["jobs"]["claude-review"]["permissions"]
        assert permissions.get("contents") == "read"
        assert permissions.get("pull-requests") == "read"

    def _review_step(self):
        """Return the 'Run Claude Code Review' step."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        for s in steps:
            if s.get("id") == "claude-review":
                return s
        raise AssertionError("claude-review step not found")
