"""Regression tests for the dashboard CI workflow.

The dashboard workflow regenerates assets/dashboard/commit_bollinger.png
and opens a PR (instead of pushing directly to main, which branch protection
blocks).  These tests verify the structural invariants.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "dashboard.yml"


class TestDashboardWorkflowStructure:
    """Validate the dashboard workflow uses a PR-based approach."""

    def setup_method(self) -> None:
        self.workflow = yaml.safe_load(DASHBOARD_WORKFLOW.read_text())

    def test_permissions_include_pull_requests(self) -> None:
        """Workflow needs pull-requests: write to open PRs."""
        perms = self.workflow["permissions"]
        assert perms.get("pull-requests") == "write"
        assert perms.get("contents") == "write"

    def test_no_direct_push_to_main(self) -> None:
        """The workflow must not push directly to main.

        Branch protection blocks direct pushes from CI.  The workflow
        should create a PR branch instead.
        """
        job = self.workflow["jobs"]["update-dashboard"]
        for step in job["steps"]:
            run_cmd = step.get("run", "")
            # The only git push should be to a branch, not bare 'git push'
            # that would push to the current (main) branch
            for line in run_cmd.splitlines():
                stripped = line.strip()
                # A bare 'git push' (without branch/force/origin args) pushes to main
                if stripped == "git push":
                    raise AssertionError(
                        f"Step {step.get('name', '?')!r} contains bare 'git push' "
                        "which would push directly to main"
                    )

    def test_pr_creation_step_exists(self) -> None:
        """There must be a step that creates or updates a PR."""
        job = self.workflow["jobs"]["update-dashboard"]
        pr_steps = [s for s in job["steps"] if "gh pr create" in str(s.get("run", ""))]
        assert len(pr_steps) >= 1, "Expected at least one step with 'gh pr create'"

    def test_auto_merge_is_reasserted_for_existing_dashboard_prs(self) -> None:
        """The workflow should queue auto-merge after every branch update."""
        job = self.workflow["jobs"]["update-dashboard"]
        step = next(s for s in job["steps"] if "gh pr create" in str(s.get("run", "")))
        script = step["run"]
        assert 'PR_NUMBER="$EXISTING"' in script
        assert 'gh pr merge "$PR_NUMBER" --auto --squash --delete-branch' in script

    def test_dashboard_branch_is_not_main(self) -> None:
        """The commit target branch must not be 'main'."""
        job = self.workflow["jobs"]["update-dashboard"]
        for step in job["steps"]:
            run_cmd = step.get("run", "")
            if "git checkout -b" in run_cmd:
                # Extract the branch name variable or literal
                assert "chore/auto-dashboard" in run_cmd or "BRANCH" in run_cmd
                return
        raise AssertionError("No 'git checkout -b' found — workflow may push to main")
