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

    def test_shallow_clone_sufficient(self):
        """Checkout uses shallow clone — reviewer uses gh pr diff (not git diff)."""
        steps = self.cfg["jobs"]["claude-review"]["steps"]
        checkout = next(s for s in steps if "checkout" in s.get("uses", ""))
        assert checkout["with"]["fetch-depth"] == 1, (
            "fetch-depth must be 1 (shallow) — reviewer uses gh pr diff, "
            "not git diff, so full history is unnecessary"
        )

    def test_prompt_uses_gh_pr_diff(self):
        """Reviewer prompt must use `gh pr diff` not `git diff`.

        The allowed-tools only grant scoped Bash for `gh` commands.
        Unrestricted `git diff` may be denied by the sandbox (#1146).
        """
        step = self._review_step()
        prompt = step["with"]["prompt"]
        assert "gh pr diff" in prompt, "prompt must use gh pr diff (not git diff)"
        assert "git diff" not in prompt, "prompt must not reference git diff"

    def test_threshold_alerting_for_blank_execution(self):
        """Consecutive blank-execution failures must escalate to an issue.

        After BLANK_EXEC_THRESHOLD consecutive failures, the classifier
        creates an infra issue instead of silently warning (#1092).
        """
        flag_step = self._flag_step()
        script = flag_step["run"]
        assert "BLANK_EXEC_THRESHOLD" in script, (
            "classifier must define BLANK_EXEC_THRESHOLD for consecutive "
            "blank-execution alerting"
        )
        assert (
            "CONSECUTIVE_FAILURES" in script
        ), "classifier must count consecutive failures"

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
        """Blank EXECUTION_FILE below threshold must warn and exit 0.

        The action does not set execution_file on error_max_turns exits.
        Below the threshold, blank files exit 0 (suppressed). Above the
        threshold, consecutive failures escalate to an issue (#1092).
        """
        flag_step = self._flag_step()
        script = flag_step["run"]
        # Must check for blank EXECUTION_FILE
        assert (
            '-z "$EXECUTION_FILE"' in script
        ), "classifier must check for blank EXECUTION_FILE"
        # The blank-execution branch must contain both:
        # - exit 0 (below threshold, suppress)
        # - exit 1 (above threshold, escalate)
        blank_idx = script.index('-z "$EXECUTION_FILE"')
        # Find the elif that ends the blank-execution branch
        elif_idx = script.index("elif", blank_idx)
        blank_section = script[blank_idx:elif_idx]
        assert (
            "exit 0" in blank_section
        ), "blank EXECUTION_FILE path must exit 0 below threshold"
        assert (
            "exit 1" in blank_section
        ), "blank EXECUTION_FILE path must exit 1 above threshold"

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
        # The error_max_turns guard must exit 0 before the final gh issue create
        # (the one for genuine infra failures, not the threshold alerting one)
        max_turns_idx = script.index("error_max_turns")
        exit_idx = script.index("exit 0", max_turns_idx)
        # Find the last gh issue create (genuine failure path)
        last_issue_idx = script.rindex("gh issue create")
        assert (
            exit_idx < last_issue_idx
        ), "error_max_turns path must exit 0 before the genuine-failure issue create"

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

    def test_threshold_dedup_guard(self):
        """Threshold-breach issue creation must check for existing open issues.

        Without dedup, the 4th, 5th, etc. consecutive failures each create
        a new issue. The guard searches for an existing open issue and skips
        creation if one exists (#1164).
        """
        flag_step = self._flag_step()
        script = flag_step["run"]
        # Dedup guard must appear before the threshold gh issue create
        assert "gh issue list --search" in script, (
            "threshold-breach path must search for existing open issues "
            "before creating a new one"
        )
        # The search must look for the same title pattern used in creation
        assert (
            "consecutive blank-execution" in script
        ), "dedup search must match the threshold-breach issue title pattern"
        # Dedup guard must come before the threshold issue create
        dedup_idx = script.index("gh issue list --search")
        # Find the threshold issue create (first one, not the genuine-failure one)
        threshold_create_idx = script.index("gh issue create")
        assert (
            dedup_idx < threshold_create_idx
        ), "dedup guard must appear before the threshold gh issue create"

    def test_consecutive_count_uses_reduce(self):
        """Failure count must be truly consecutive — stop at first non-failure.

        The original implementation counted all failures in the window, not
        consecutive ones from the start. The fix uses a jq reduce that stops
        counting at the first non-failure (#1164).
        """
        flag_step = self._flag_step()
        script = flag_step["run"]
        assert "reduce" in script, (
            "consecutive failure count must use jq reduce for true "
            "sequential counting (not filter-then-length)"
        )

    def test_bash_scoping_comment_mentions_blocklist(self):
        """The Bash scoping comment must reference --disallowedTools blocklist.

        The action does NOT use an allowed-tools allowlist — it uses
        --disallowedTools in claude_args (#1167).
        """
        # Check the raw YAML text for the comment; step dict won't include it
        workflow_text = WORKFLOW.read_text()
        assert "scoped via --disallowedTools blocklist" in workflow_text, (
            "Bash scoping comment must mention --disallowedTools blocklist, "
            "not allowed-tools allowlist"
        )
        # The old misleading phrasing must not be present
        assert (
            "allowed-tools in the action config" not in workflow_text
        ), "old misleading comment about allowed-tools must be removed"

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
