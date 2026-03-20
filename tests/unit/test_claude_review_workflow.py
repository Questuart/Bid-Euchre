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

    def test_prompt_is_read_only(self):
        """Prompt must explicitly forbid modifying files."""
        step = self._review_step()
        prompt = step["with"]["prompt"].lower()
        assert "read-only" in prompt, "prompt must state 'read-only'"
        assert "do not" in prompt, "prompt must include prohibitions"

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

    # -- allowed_tools constraints --

    def test_has_allowed_tools(self):
        """Review step must declare an explicit allowed_tools allowlist."""
        step = self._review_step()
        assert "allowed_tools" in step["with"], "allowed_tools must be present"

    def test_allowed_tools_includes_read_tools(self):
        """Allowlist must include core read-only inspection tools."""
        tools = self._allowed_tools_set()
        for required in ("Read", "Glob", "Grep"):
            assert required in tools, f"missing read tool: {required}"

    def test_allowed_tools_excludes_write_tools(self):
        """Allowlist must NOT include tools that modify the repository."""
        tools_text = self._review_step()["with"]["allowed_tools"]
        for forbidden in ("Edit", "Write", "NotebookEdit"):
            assert forbidden not in tools_text, f"write tool present: {forbidden}"
        # No git push, git commit, or destructive gh commands
        for forbidden_bash in ("git push", "git commit", "git checkout", "gh pr merge"):
            assert (
                forbidden_bash not in tools_text
            ), f"destructive bash pattern present: {forbidden_bash}"

    def test_allowed_tools_includes_pr_comment(self):
        """Reviewer must be able to post PR comments (its primary output)."""
        tools = self._allowed_tools_set()
        assert any(
            "gh pr comment" in t for t in tools
        ), "must include Bash(gh pr comment *)"

    # -- infra-failure classifier constraints --

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

    def test_classifier_handles_missing_execution_file(self):
        """Classifier must explicitly handle blank/missing EXECUTION_FILE."""
        flag_step = self._flag_step()
        script = flag_step["run"]
        # Must check for blank EXECUTION_FILE (not just file-not-found)
        assert (
            '-z "$EXECUTION_FILE"' in script
        ), "classifier must check for blank EXECUTION_FILE"
        assert (
            "missing_execution_file" in script
        ), "must classify blank EXECUTION_FILE as 'missing_execution_file'"

    def test_classifier_handles_file_not_found(self):
        """Classifier must handle EXECUTION_FILE path set but file absent."""
        flag_step = self._flag_step()
        script = flag_step["run"]
        assert (
            '! -f "$EXECUTION_FILE"' in script
        ), "classifier must check for file-not-found"
        assert (
            "execution_file_not_found" in script
        ), "must classify missing file as 'execution_file_not_found'"

    def test_classifier_guards_empty_jq_output(self):
        """Classifier must guard against jq returning empty strings."""
        flag_step = self._flag_step()
        script = flag_step["run"]
        assert (
            "unparseable_execution_file" in script
        ), "must classify empty jq output as 'unparseable_execution_file'"

    # -- helpers --

    def _review_step(self):
        """Return the 'Run Claude Code Review' step."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        for s in steps:
            if s.get("id") == "claude-review":
                return s
        raise AssertionError("claude-review step not found")

    def _flag_step(self):
        """Return the 'Flag reviewer infra failure' step."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        for s in steps:
            if s.get("name") == "Flag reviewer infra failure":
                return s
        raise AssertionError("Flag reviewer infra failure step not found")

    def _allowed_tools_set(self) -> set[str]:
        """Parse allowed_tools into a set of tool entries."""
        raw = self._review_step()["with"]["allowed_tools"]
        return {line.strip() for line in raw.strip().splitlines() if line.strip()}
