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

    def test_max_turns_in_claude_args(self):
        """Max turns must be explicitly set to a bounded value."""
        step = self._review_step()
        claude_args = step["with"]["claude_args"]
        assert (
            "--max-turns 15" in claude_args
        ), f"expected '--max-turns 15' in claude_args, got {claude_args!r}"

    def test_no_continue_on_error(self):
        """Review step must NOT use continue-on-error — failures must be visible."""
        step = self._review_step()
        assert step.get("continue-on-error") is not True

    def test_no_allowed_tools_input(self):
        """allowed_tools is not a valid action input — must not be present.

        The anthropics/claude-code-action@v1 action silently ignores this input.
        Tool restrictions must be passed via --disallowedTools in claude_args.
        """
        step = self._review_step()
        assert "allowed_tools" not in step.get("with", {}), (
            "allowed_tools is not a valid input for claude-code-action@v1 — "
            "use --disallowedTools in claude_args instead"
        )

    def test_disallowed_tools_in_claude_args(self):
        """claude_args must include --disallowedTools to block write tools.

        Without this, the reviewer wastes turns on permission-denied attempts
        to use Edit/Write/NotebookEdit, burning 2+ turns of the max-turns budget.
        """
        step = self._review_step()
        claude_args = step["with"]["claude_args"]
        assert (
            "--disallowedTools" in claude_args
        ), "claude_args must include --disallowedTools to prevent write tool denials"

    def test_disallowed_tools_blocks_write_tools(self):
        """The --disallowedTools list must include Edit, Write, and NotebookEdit."""
        step = self._review_step()
        claude_args = step["with"]["claude_args"]
        for tool in ("Edit", "Write", "NotebookEdit"):
            assert (
                tool in claude_args
            ), f"write tool '{tool}' must be in --disallowedTools list"

    def test_disallowed_tools_blocks_network_and_agent_tools(self):
        """Agent, WebFetch, WebSearch, and LSP must be disallowed.

        These tools are denied by the CI sandbox and waste turns when
        attempted. Blocking them upfront saves ~36% of the turn budget.
        """
        step = self._review_step()
        claude_args = step["with"]["claude_args"]
        for tool in ("Agent", "WebFetch", "WebSearch", "LSP"):
            assert (
                tool in claude_args
            ), f"'{tool}' must be in --disallowedTools to prevent wasted turns"

    def test_full_git_history_for_diff(self):
        """Checkout must use fetch-depth 0 so git diff origin/main works."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        checkout = next(s for s in steps if "checkout" in s.get("uses", ""))
        assert checkout["with"]["fetch-depth"] == 0, (
            "fetch-depth must be 0 for full git history — "
            "the reviewer needs git diff origin/main...HEAD"
        )

    # -- infra-failure classifier constraints --

    def test_has_infra_failure_flag_step(self):
        """A follow-up step must handle reviewer failures (conditional issue creation)."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        flag_steps = [
            s for s in steps if s.get("name") == "Flag reviewer infra failure"
        ]
        assert len(flag_steps) == 1
        flag_step = flag_steps[0]
        # Must scope to the review step specifically, not blanket failure()
        assert "steps.claude-review.outcome" in flag_step["if"]
        # Must have GH_TOKEN for gh issue create (used on genuine failures)
        assert "GH_TOKEN" in str(flag_step.get("env", {}))

    def test_classifier_suppresses_blank_execution_file(self):
        """Blank EXECUTION_FILE must warn and exit 0, not create an issue.

        The action does not set execution_file on error_max_turns exits.
        Creating an issue for every blank file would spam the repo.
        """
        flag_step = self._flag_step()
        script = flag_step["run"]
        # Must check for blank EXECUTION_FILE
        assert (
            '-z "$EXECUTION_FILE"' in script
        ), "classifier must check for blank EXECUTION_FILE"
        # Must exit 0 (no issue creation) on blank path
        # Find the blank-file branch and verify it has exit 0 before gh issue create
        blank_idx = script.index('-z "$EXECUTION_FILE"')
        exit_idx = script.index("exit 0", blank_idx)
        issue_idx = script.index("gh issue create")
        assert (
            exit_idx < issue_idx
        ), "blank EXECUTION_FILE path must exit 0 before reaching gh issue create"

    def test_classifier_suppresses_max_turns(self):
        """error_max_turns must warn and exit 0, not create an issue.

        Max-turns exhaustion is a normal operational boundary, not an infra
        failure. Issue creation is reserved for genuine infra failures.
        """
        flag_step = self._flag_step()
        script = flag_step["run"]
        assert (
            "error_max_turns" in script
        ), "classifier must check for error_max_turns subtype"
        # The error_max_turns guard must exit 0 before gh issue create
        max_turns_idx = script.index("error_max_turns")
        exit_idx = script.index("exit 0", max_turns_idx)
        issue_idx = script.index("gh issue create")
        assert (
            exit_idx < issue_idx
        ), "error_max_turns path must exit 0 before reaching gh issue create"

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
