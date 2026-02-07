"""Tests for batch eligibility engine.

All tests are fixture-based — no real experiment runs required.
"""

import json

from bid_euchre.reporting.eligibility import (
    check_canonical_summaries,
    check_config_membership,
    check_git_sha_consistency,
    check_notebook_gate,
    compute_eligibility,
)


def _make_rollup(**overrides):
    """Create a minimal rollup fixture."""
    base = {
        "schema_version": 1,
        "suite_name": "test_suite",
        "suite_seed": 42,
        "suite_n_per": 20,
        "created_at_utc": "2026-02-10T12:00:00Z",
        "configs": [
            {
                "config_path": "experiments/configs/quick_test.yaml",
                "run_id": "quick_test_42_20260210",
                "run_dir": "quick_test_42_20260210",
                "status": "ok",
                "git_sha": "abc1234",
            },
            {
                "config_path": "experiments/configs/baseline_greedy.yaml",
                "run_id": "baseline_greedy_42_20260210",
                "run_dir": "baseline_greedy_42_20260210",
                "status": "ok",
                "git_sha": "abc1234",
            },
        ],
        "summary": [],
        "batch": {
            "batch_id": "test_batch_001",
            "batch_purpose": "promotion",
        },
    }
    base.update(overrides)
    return base


def _make_canonical_summary(fail_count=0):
    return {"fail_count": fail_count, "pass_count": 5}


def _make_notebook_gate(gate_status="PASS", total=3, passed=3, failed=0):
    return {
        "schema_version": 1,
        "gate_status": gate_status,
        "created_at_utc": "2026-02-10T12:00:00Z",
        "mode": "smoke",
        "total": total,
        "passed": passed,
        "failed": failed,
        "notebooks": [
            {"name": f"nb_{i}.ipynb", "status": "PASS" if i < passed else "FAIL",
             "duration_seconds": 1.0, "message": "OK" if i < passed else "Error"}
            for i in range(total)
        ],
    }


class TestCheckConfigMembership:

    def test_all_configs_ok(self):
        rollup = _make_rollup()
        result = check_config_membership(rollup)
        assert result.status == "PASS"

    def test_config_failed_status(self):
        rollup = _make_rollup()
        rollup["configs"][1]["status"] = "failed"
        result = check_config_membership(rollup)
        assert result.status == "FAIL"
        assert "baseline_greedy.yaml" in result.detail

    def test_expected_config_missing(self):
        rollup = _make_rollup()
        result = check_config_membership(
            rollup, expected_configs={"quick_test.yaml", "missing_config.yaml"}
        )
        assert result.status == "FAIL"
        assert "missing_config.yaml" in result.detail

    def test_expected_configs_all_present(self):
        rollup = _make_rollup()
        result = check_config_membership(
            rollup, expected_configs={"quick_test.yaml", "baseline_greedy.yaml"}
        )
        assert result.status == "PASS"


class TestCheckCanonicalSummaries:

    def test_all_clean(self, tmp_path):
        rollup = _make_rollup()
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "reports"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "PASS"

    def test_fail_count_nonzero(self, tmp_path):
        rollup = _make_rollup()
        for i, config in enumerate(rollup["configs"]):
            run_dir = tmp_path / config["run_dir"] / "reports"
            run_dir.mkdir(parents=True)
            fc = 1 if i == 0 else 0
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=fc), f)

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "FAIL"
        assert "fail_count=1" in result.detail

    def test_missing_canonical_summary(self, tmp_path):
        rollup = _make_rollup()
        # Don't create any summary files
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "reports"
            run_dir.mkdir(parents=True)

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "FAIL"
        assert "missing" in result.detail


class TestCheckNotebookGate:

    def test_promotion_gate_required_missing(self):
        result = check_notebook_gate(None, "promotion")
        assert result.status == "FAIL"
        assert "required for promotion" in result.detail

    def test_promotion_gate_pass(self, tmp_path):
        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="PASS"), f)
        result = check_notebook_gate(str(gate_path), "promotion")
        assert result.status == "PASS"

    def test_promotion_gate_fail(self, tmp_path):
        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="FAIL", passed=2, failed=1), f)
        result = check_notebook_gate(str(gate_path), "promotion")
        assert result.status == "FAIL"

    def test_exploration_gate_optional_missing(self):
        result = check_notebook_gate(None, "exploration")
        assert result.status == "PASS"
        assert "optional" in result.detail

    def test_exploration_gate_fail(self, tmp_path):
        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="FAIL", passed=2, failed=1), f)
        result = check_notebook_gate(str(gate_path), "exploration")
        assert result.status == "FAIL"

    def test_nonexistent_path(self):
        result = check_notebook_gate("/nonexistent/path.json", "promotion")
        assert result.status == "FAIL"


class TestCheckGitShaConsistency:

    def test_all_same_sha(self):
        rollup = _make_rollup()
        result = check_git_sha_consistency(rollup)
        assert result.status == "PASS"
        assert "abc1234" in result.detail

    def test_different_shas(self):
        rollup = _make_rollup()
        rollup["configs"][1]["git_sha"] = "def5678"
        result = check_git_sha_consistency(rollup)
        assert result.status == "FAIL"
        assert "Inconsistent" in result.detail

    def test_no_shas(self):
        rollup = _make_rollup(configs=[])
        result = check_git_sha_consistency(rollup)
        assert result.status == "PASS"


class TestComputeEligibility:

    def test_eligible_all_pass(self, tmp_path):
        rollup = _make_rollup()
        # Create canonical summaries
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "reports"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        # Create gate
        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="PASS"), f)

        gate = compute_eligibility(
            rollup, str(tmp_path), "promotion",
            notebook_gate_path=str(gate_path),
        )
        assert gate.eligible is True
        assert all(r.status == "PASS" for r in gate.reasons)

    def test_any_fail_ineligible(self, tmp_path):
        rollup = _make_rollup()
        # Missing canonical summaries will cause FAIL
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "reports"
            run_dir.mkdir(parents=True)

        gate = compute_eligibility(
            rollup, str(tmp_path), "promotion",
        )
        assert gate.eligible is False

    def test_gate_to_dict(self, tmp_path):
        rollup = _make_rollup()
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "reports"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="PASS"), f)

        gate = compute_eligibility(
            rollup, str(tmp_path), "promotion",
            notebook_gate_path=str(gate_path),
        )
        d = gate.to_dict()
        assert d["schema_version"] == 1
        assert "eligible" in d
        assert "reasons" in d
        assert isinstance(d["reasons"], list)
        assert all("rule" in r and "status" in r and "detail" in r for r in d["reasons"])
