"""Regression tests for .github/workflows/auto-merge.yml structure.

The auto-merge workflow enables GitHub auto-merge for owner-authored PRs
and the auto-dashboard maintenance PRs. It fires on PR open/reopen/
synchronize and retries after check suites complete. These tests verify
the structural invariants that keep the workflow safe and correctly scoped.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "auto-merge.yml"


class TestAutoMergeWorkflowStructure:
    """Validate the auto-merge workflow shape."""

    def setup_method(self) -> None:
        self.workflow = yaml.safe_load(WORKFLOW.read_text())
        self.jobs = self.workflow["jobs"]

    def test_has_pull_request_trigger(self) -> None:
        """PR trigger must include opened, reopened, and synchronize."""
        # YAML parses bare `on` as boolean True
        pr_trigger = self.workflow[True]["pull_request"]
        assert "main" in pr_trigger["branches"]
        required_types = {"opened", "reopened", "synchronize"}
        assert required_types.issubset(set(pr_trigger["types"]))

    def test_has_check_suite_trigger(self) -> None:
        """check_suite trigger must fire on completed events."""
        cs_trigger = self.workflow[True]["check_suite"]
        assert "completed" in cs_trigger["types"]

    def test_job_condition_gates_owner_and_dashboard_prs(self) -> None:
        """pull_request events must allow the owner and auto-dashboard PRs."""
        job_if = self.jobs["enable-auto-merge"]["if"]
        assert "pull_request" in job_if
        assert "repository_owner" in job_if
        assert "pull_request.head.ref" in job_if
        assert "chore/auto-dashboard" in job_if

    def test_job_condition_gates_success_for_check_suite(self) -> None:
        """check_suite events must be gated to successful conclusions."""
        job_if = self.jobs["enable-auto-merge"]["if"]
        assert "check_suite" in job_if
        assert "success" in job_if

    def test_permissions_are_minimal(self) -> None:
        """Workflow should have write permissions for contents and PRs only."""
        perms = self.workflow["permissions"]
        assert perms["contents"] == "write"
        assert perms["pull-requests"] == "write"
        # No additional permissions
        assert set(perms.keys()) == {"contents", "pull-requests"}

    def test_step_uses_env_vars_not_inline_expressions(self) -> None:
        """Shell script should use env vars for event data (security)."""
        step = self.jobs["enable-auto-merge"]["steps"][0]
        env = step["env"]
        # Key event data passed via env, not inline ${{ }} in run
        assert "EVENT_NAME" in env
        assert "PR_NUMBER" in env
        assert "HEAD_SHA" in env
        assert "REPO_OWNER" in env

    def test_check_suite_path_filters_owner_and_dashboard_prs(self) -> None:
        """The check_suite retry path must filter to eligible PRs only."""
        step = self.jobs["enable-auto-merge"]["steps"][0]
        script = step["run"]
        # Must filter by author login matching repo owner or the dashboard branch
        assert "author.login" in script
        assert "REPO_OWNER" in script
        assert "headRefName" in script
        assert "chore/auto-dashboard" in script
        # Must filter to open PRs targeting main
        assert "--state open" in script
        assert "--base main" in script

    def test_auto_merge_uses_squash(self) -> None:
        """All gh pr merge calls must use --auto --squash."""
        step = self.jobs["enable-auto-merge"]["steps"][0]
        script = step["run"]
        assert "--auto --squash" in script

    def test_failures_are_tolerated(self) -> None:
        """gh pr merge failures should produce notices, not job failures."""
        step = self.jobs["enable-auto-merge"]["steps"][0]
        script = step["run"]
        # Should have || fallback for idempotency
        assert "::notice::" in script
