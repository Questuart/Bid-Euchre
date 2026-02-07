"""Tests for batch eligibility engine.

All tests are fixture-based — no real experiment runs required.
"""

import json

from bid_euchre.models.freeze import freeze_artifact
from bid_euchre.reporting.eligibility import (
    check_artifacts_frozen,
    check_canonical_summaries,
    check_config_membership,
    check_git_sha_consistency,
    check_notebook_gate,
    check_split_manifests,
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
    """Create canonical summary with production nested schema."""
    return {
        "sanity": {
            "fail_count": fail_count,
            "pass_count": 5,
            "warn_count": 0,
            "skip_count": 0,
            "failing_tests": [],
            "all_passed": fail_count == 0,
        }
    }


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
            {
                "name": f"nb_{i}.ipynb",
                "status": "PASS" if i < passed else "FAIL",
                "duration_seconds": 1.0,
                "message": "OK" if i < passed else "Error",
            }
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
            run_dir = tmp_path / config["run_dir"] / "artifacts"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "PASS"

    def test_fail_count_nonzero(self, tmp_path):
        rollup = _make_rollup()
        for i, config in enumerate(rollup["configs"]):
            run_dir = tmp_path / config["run_dir"] / "artifacts"
            run_dir.mkdir(parents=True)
            fc = 1 if i == 0 else 0
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=fc), f)

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "FAIL"
        assert "fail_count=1" in result.detail

    def test_missing_canonical_summary(self, tmp_path):
        rollup = _make_rollup()
        # Don't create any summary files (neither artifacts/ nor reports/)
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"]
            run_dir.mkdir(parents=True)

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "FAIL"
        assert "missing" in result.detail

    def test_legacy_flat_schema(self, tmp_path):
        """Test backward compatibility with old flat fail_count schema."""
        rollup = _make_rollup()
        # Use only first config for simplicity
        rollup["configs"] = rollup["configs"][:1]

        run_dir = tmp_path / rollup["configs"][0]["run_dir"] / "artifacts"
        run_dir.mkdir(parents=True)
        summary_path = run_dir / "canonical_summary.json"
        # Legacy flat schema (no nested sanity object)
        summary_path.write_text(json.dumps({"fail_count": 0, "pass_count": 5}))

        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "PASS"

    def test_legacy_path_fallback(self, tmp_path):
        """Test backward compatibility with old reports/ path."""
        rollup = _make_rollup()
        rollup["configs"] = rollup["configs"][:1]

        # Create file in old reports/ location (not artifacts/)
        run_dir = tmp_path / rollup["configs"][0]["run_dir"] / "reports"
        run_dir.mkdir(parents=True)
        summary_path = run_dir / "canonical_summary.json"
        summary_path.write_text(
            json.dumps(
                {
                    "sanity": {
                        "fail_count": 0,
                        "pass_count": 5,
                        "warn_count": 0,
                        "skip_count": 0,
                        "failing_tests": [],
                        "all_passed": True,
                    }
                }
            )
        )

        # Should find file in legacy reports/ location
        result = check_canonical_summaries(rollup, str(tmp_path))
        assert result.status == "PASS"


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


class TestCheckArtifactsFrozen:
    def test_promotion_no_dir_fails(self):
        result = check_artifacts_frozen(None, "promotion")
        assert result.status == "FAIL"

    def test_exploration_no_dir_passes(self):
        result = check_artifacts_frozen(None, "exploration")
        assert result.status == "PASS"

    def test_promotion_unfrozen_fails(self, tmp_path):
        artifact = tmp_path / "olsa_v1.json"
        artifact.write_text(json.dumps({"frozen_at": None, "artifact_type": "olsa_v1"}))
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "FAIL"
        assert "olsa_v1.json" in result.detail

    def test_promotion_frozen_passes(self, tmp_path):
        artifact = tmp_path / "olsa_v1.json"
        artifact.write_text(json.dumps({"frozen_at": None, "artifact_type": "olsa_v1"}))
        freeze_artifact(artifact)
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "PASS"

    def test_exploration_unfrozen_passes_with_warning(self, tmp_path):
        artifact = tmp_path / "olsa_v1.json"
        artifact.write_text(json.dumps({"frozen_at": None, "artifact_type": "olsa_v1"}))
        result = check_artifacts_frozen(str(tmp_path), "exploration")
        assert result.status == "PASS"
        assert "warning" in result.detail.lower()

    def test_exempt_files_ignored(self, tmp_path):
        """meta.json and rollup.json are exempt from freeze check."""
        (tmp_path / "meta.json").write_text(json.dumps({"frozen_at": None}))
        (tmp_path / "rollup.json").write_text(json.dumps({"frozen_at": None}))
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "PASS"

    def test_empty_dir_passes(self, tmp_path):
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "PASS"

    def test_split_manifest_excluded(self, tmp_path):
        """Split manifest JSON files must not be treated as model artifacts."""
        (tmp_path / "split_manifest_suit.json").write_text(
            json.dumps({"schema_version": 1, "split_type": "three_way"})
        )
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "PASS"
        assert "No model artifacts" in result.detail

    def test_split_manifest_with_model_artifact(self, tmp_path):
        """Split manifest alongside a frozen model artifact should pass."""
        (tmp_path / "split_manifest_suit.json").write_text(
            json.dumps({"schema_version": 1, "split_type": "three_way"})
        )
        artifact = tmp_path / "olsa_v1.json"
        artifact.write_text(json.dumps({"frozen_at": None}))
        freeze_artifact(artifact)
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "PASS"
        assert "1 model artifacts frozen" in result.detail

    def test_missing_artifact_sha256_fails_promotion(self, tmp_path):
        """Artifact with frozen_at but missing artifact_sha256 must fail via verify_frozen."""
        (tmp_path / "olsa_v1.json").write_text(
            json.dumps(
                {"frozen_at": "2026-02-07T12:00:00Z", "artifact_type": "olsa_v1"}
            )
        )
        result = check_artifacts_frozen(str(tmp_path), "promotion")
        assert result.status == "FAIL"
        assert "olsa_v1.json" in result.detail


class TestCheckSplitManifests:
    def test_promotion_no_dir_fails(self):
        result = check_split_manifests(None, "promotion")
        assert result.status == "FAIL"

    def test_exploration_no_dir_passes(self):
        result = check_split_manifests(None, "exploration")
        assert result.status == "PASS"

    def test_promotion_two_way_fails(self, tmp_path):
        manifest = tmp_path / "split_manifest_suit.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "split_type": "two_way",
                    "split_seed": 42,
                }
            )
        )
        result = check_split_manifests(str(tmp_path), "promotion")
        assert result.status == "FAIL"
        assert "two_way" in result.detail

    def test_promotion_three_way_passes(self, tmp_path):
        manifest = tmp_path / "split_manifest_suit.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "split_type": "three_way",
                    "split_seed": 42,
                }
            )
        )
        result = check_split_manifests(str(tmp_path), "promotion")
        assert result.status == "PASS"

    def test_exploration_two_way_passes(self, tmp_path):
        manifest = tmp_path / "split_manifest_suit.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "split_type": "two_way",
                    "split_seed": 42,
                }
            )
        )
        result = check_split_manifests(str(tmp_path), "exploration")
        assert result.status == "PASS"

    def test_no_manifests_promotion_fails(self, tmp_path):
        result = check_split_manifests(str(tmp_path), "promotion")
        assert result.status == "FAIL"

    def test_no_manifests_exploration_passes(self, tmp_path):
        result = check_split_manifests(str(tmp_path), "exploration")
        assert result.status == "PASS"


class TestComputeEligibility:
    def test_eligible_all_pass(self, tmp_path):
        rollup = _make_rollup()
        # Create canonical summaries
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "artifacts"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        # Create gate
        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="PASS"), f)

        gate = compute_eligibility(
            rollup,
            str(tmp_path),
            "promotion",
            notebook_gate_path=str(gate_path),
        )
        # Will fail because no artifact_dir and split_manifest_dir for promotion
        assert gate.eligible is False

    def test_eligible_all_pass_with_artifacts(self, tmp_path):
        rollup = _make_rollup()
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "artifacts"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="PASS"), f)

        # Create frozen artifact
        artifact_dir = tmp_path / "model_artifacts"
        artifact_dir.mkdir()
        artifact_path = artifact_dir / "olsa_v1.json"
        artifact_path.write_text(json.dumps({"frozen_at": None}))
        freeze_artifact(artifact_path)

        # Create three_way split manifest
        split_dir = tmp_path / "splits"
        split_dir.mkdir()
        (split_dir / "split_manifest_suit.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "split_type": "three_way",
                }
            )
        )

        gate = compute_eligibility(
            rollup,
            str(tmp_path),
            "promotion",
            notebook_gate_path=str(gate_path),
            artifact_dir=str(artifact_dir),
            split_manifest_dir=str(split_dir),
        )
        assert gate.eligible is True
        assert all(r.status == "PASS" for r in gate.reasons)

    def test_any_fail_ineligible(self, tmp_path):
        rollup = _make_rollup()
        # Missing canonical summaries will cause FAIL (neither artifacts/ nor reports/)
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"]
            run_dir.mkdir(parents=True)

        gate = compute_eligibility(
            rollup,
            str(tmp_path),
            "promotion",
        )
        assert gate.eligible is False

    def test_gate_to_dict(self, tmp_path):
        rollup = _make_rollup()
        for config in rollup["configs"]:
            run_dir = tmp_path / config["run_dir"] / "artifacts"
            run_dir.mkdir(parents=True)
            with (run_dir / "canonical_summary.json").open("w") as f:
                json.dump(_make_canonical_summary(fail_count=0), f)

        gate_path = tmp_path / "notebook_gate.json"
        with gate_path.open("w") as f:
            json.dump(_make_notebook_gate(gate_status="PASS"), f)

        gate = compute_eligibility(
            rollup,
            str(tmp_path),
            "promotion",
            notebook_gate_path=str(gate_path),
        )
        d = gate.to_dict()
        assert d["schema_version"] == 1
        assert "eligible" in d
        assert "reasons" in d
        assert isinstance(d["reasons"], list)
        assert all(
            "rule" in r and "status" in r and "detail" in r for r in d["reasons"]
        )


def test_eligibility_with_realistic_artifacts(tmp_path):
    """Integration-like test with realistic run directory structure using new schema."""
    # Setup: Create realistic run directory matching production
    run_id = "test_run_42_20260206_120000"
    run_dir_path = tmp_path / run_id
    artifacts_dir = run_dir_path / "artifacts"
    artifacts_dir.mkdir(parents=True)

    # Create canonical_summary.json with production schema (nested sanity object)
    summary_path = artifacts_dir / "canonical_summary.json"
    summary_data = {
        "run_id": run_id,
        "experiment_name": "test_run",
        "seed": 42,
        "n_per": 100,
        "git_sha": "abc123",
        "total_hands": 600,
        "sanity": {
            "pass_count": 5,
            "warn_count": 0,
            "fail_count": 0,
            "skip_count": 0,
            "failing_tests": [],
            "all_passed": True,
        },
        "discovered": {
            "results_files": ["results_high_2_pairs.jsonl"],
            "datasets_present": False,
            "bidless_parquet": False,
            "bidless_outcomes_parquet": False,
        },
        "generated_at_utc": "2026-02-06T12:00:00Z",
    }
    summary_path.write_text(json.dumps(summary_data, indent=2))

    # Create rollup dict (not meta.json - use rollup directly)
    rollup = {
        "schema_version": 1,
        "suite_name": "test_suite",
        "suite_seed": 42,
        "suite_n_per": 100,
        "created_at_utc": "2026-02-06T12:00:00Z",
        "configs": [
            {
                "config_path": "experiments/configs/test.yaml",
                "run_id": run_id,
                "run_dir": run_id,
                "status": "ok",
                "git_sha": "abc123",
            }
        ],
        "summary": [],
        "batch": {
            "batch_id": "test_batch_001",
            "batch_purpose": "promotion",
        },
    }

    # Test: Compute eligibility (no notebook gate for simplicity)
    gate = compute_eligibility(
        rollup=rollup,
        run_base_dir=str(tmp_path),
        batch_purpose="promotion",
        notebook_gate_path=None,  # Omit gate, should FAIL for promotion
    )

    # Assert: Should fail (promotion requires notebook gate)
    assert gate.eligible is False
    gate_reasons = {r.rule: r for r in gate.reasons}
    assert gate_reasons["notebook_gate"].status == "FAIL"
    # But canonical summary check should PASS with new artifacts/ path
    assert gate_reasons["canonical_summary_clean"].status == "PASS"
