"""Regression tests for the governance workflow structure."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "governance.yml"


class TestGovernanceWorkflowStructure:
    """Validate governance required-check behavior for dashboard chores."""

    def setup_method(self) -> None:
        self.workflow = yaml.safe_load(GOVERNANCE_WORKFLOW.read_text())

    def test_governance_job_has_no_dashboard_skip(self) -> None:
        job = self.workflow["jobs"]["governance"]
        job_if = str(job.get("if", ""))
        assert "chore: update PR analytics dashboard" not in job_if
        assert "startsWith(github.head_ref, 'chore/auto-dashboard')" not in job_if

    def test_dashboard_chore_prs_emit_skip_notice(self) -> None:
        steps = self.workflow["jobs"]["governance"]["steps"]
        notice = next(
            s for s in steps if s.get("name") == "Skip notice for dashboard chore PRs"
        )
        notice_if = str(notice.get("if", ""))
        assert "chore: update PR analytics dashboard" in notice_if
        assert "startsWith(github.head_ref, 'chore/auto-dashboard')" in notice_if
