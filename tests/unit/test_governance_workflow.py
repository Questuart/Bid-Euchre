"""Regression tests for the governance workflow structure."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "governance.yml"


class TestGovernanceWorkflowStructure:
    """Validate governance short-circuiting for dashboard chores."""

    def setup_method(self) -> None:
        self.workflow = yaml.safe_load(GOVERNANCE_WORKFLOW.read_text())

    def test_dashboard_chore_prs_are_skipped(self) -> None:
        job = self.workflow["jobs"]["governance"]
        job_if = str(job.get("if", ""))
        assert "chore: update PR analytics dashboard" in job_if
        assert "startsWith(github.head_ref, 'chore/auto-dashboard')" in job_if
