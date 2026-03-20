"""Regression tests for the promoted CI workflow structure.

The CI workflow splits work across several jobs (checks, tests-shard,
notebooks, promotion-gate) and uses a non-matrix ``tests`` aggregation
job to preserve the required check context.  These tests verify the
structural invariants that branch protection depends on.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestCIWorkflowStructure:
    """Validate the promoted CI workflow shape."""

    def setup_method(self) -> None:
        self.workflow = yaml.safe_load(CI_WORKFLOW.read_text())
        self.jobs = self.workflow["jobs"]

    def test_expected_jobs_exist(self) -> None:
        expected = {
            "changes",
            "checks",
            "tests-shard",
            "notebooks",
            "promotion-gate",
            "tests",
        }
        assert expected == set(self.jobs.keys())

    def test_tests_is_aggregation_gate(self) -> None:
        """The ``tests`` job must be a non-matrix aggregation gate."""
        tests_job = self.jobs["tests"]
        # Non-matrix: no strategy key
        assert "strategy" not in tests_job
        # Depends on all upstream jobs
        expected_needs = {
            "changes",
            "checks",
            "tests-shard",
            "notebooks",
            "promotion-gate",
        }
        assert set(tests_job["needs"]) == expected_needs
        # Always runs (to post a status even on docs-only PRs)
        assert "always()" in str(tests_job.get("if", ""))

    def test_tests_shard_is_2way_pytest_split(self) -> None:
        """The shard job uses a 2-group matrix with pytest-split."""
        shard_job = self.jobs["tests-shard"]
        matrix = shard_job["strategy"]["matrix"]
        assert matrix["group"] == [1, 2]
        # Check that pytest-split flags are present in the test step
        test_steps = [
            s for s in shard_job["steps"] if "pytest" in str(s.get("run", ""))
        ]
        assert len(test_steps) == 1
        assert "--splits 2" in test_steps[0]["run"]
        assert "--group" in test_steps[0]["run"]

    def test_shard_is_not_advisory(self) -> None:
        """Promoted shard job must NOT have continue-on-error."""
        shard_job = self.jobs["tests-shard"]
        assert shard_job.get("continue-on-error") is not True

    def test_docs_only_pr_path_supported(self) -> None:
        """On docs/plans-only PRs, heavy jobs are skipped by changes gating.

        The ``changes`` job runs only on PRs and exports path-filter
        outputs.  Downstream heavy jobs (checks, tests-shard, notebooks)
        depend on ``changes`` outputs so they are truly absent when no
        relevant files changed.
        """
        # The changes job runs on PRs only
        assert "pull_request" in str(self.jobs["changes"].get("if", ""))
        # Heavy jobs depend on changes outputs
        for job_name in ("checks", "tests-shard", "notebooks"):
            job = self.jobs[job_name]
            assert "changes" in job.get("needs", [])
            job_if = str(job.get("if", ""))
            # Must reference changes outputs for conditional gating
            assert "needs.changes.outputs" in job_if

    def test_changes_exports_both_filters(self) -> None:
        """The changes job must export both code and notebook detection."""
        outputs = self.jobs["changes"]["outputs"]
        assert "code_changed" in outputs
        assert "notebooks_changed" in outputs

    def test_shard_fail_fast_disabled(self) -> None:
        """Shards must not use fail-fast so both always report results."""
        shard_job = self.jobs["tests-shard"]
        assert shard_job["strategy"]["fail-fast"] is False

    def test_aggregator_does_not_install(self) -> None:
        """The tests aggregation gate must be lightweight — no setup steps."""
        tests_job = self.jobs["tests"]
        step_names = [s.get("name", "") for s in tests_job.get("steps", [])]
        for name in step_names:
            assert "install" not in name.lower()
            assert "checkout" not in name.lower()
            assert "setup" not in name.lower()

    def test_aggregator_evaluates_all_upstream_jobs(self) -> None:
        """The gate must check every upstream job including ``changes``.

        If ``changes`` fails but is omitted from the evaluation, all
        downstream jobs would be skipped and the gate would pass green,
        silently masking the failure.
        """
        tests_job = self.jobs["tests"]
        # Find the evaluation step that runs the bash gate logic
        eval_steps = [
            s
            for s in tests_job.get("steps", [])
            if "results=(" in str(s.get("run", ""))
        ]
        assert len(eval_steps) == 1, "Expected exactly one evaluation step"
        run_script = eval_steps[0]["run"]
        # Every job listed in needs must appear in the results array
        for job_name in tests_job["needs"]:
            assert (
                f"needs.{job_name}.result" in run_script
            ), f"Aggregator does not evaluate {job_name!r} result"
