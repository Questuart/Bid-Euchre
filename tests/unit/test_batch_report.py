"""Tests for generate_batch_report.py CLI."""

import json
import subprocess
import sys

from bid_euchre.models.freeze import freeze_artifact


def _make_rollup(batch_purpose="promotion"):
    return {
        "schema_version": 1,
        "suite_name": "test_suite",
        "suite_seed": 42,
        "suite_n_per": 20,
        "created_at_utc": "2026-02-10T12:00:00Z",
        "configs": [
            {
                "config_path": "experiments/configs/quick_test.yaml",
                "run_id": "quick_test_42",
                "run_dir": "quick_test_42",
                "status": "ok",
                "git_sha": "abc1234",
            },
        ],
        "summary": [],
        "batch": {
            "batch_id": "test_batch_001",
            "batch_purpose": batch_purpose,
        },
    }


def _setup_run_dir(tmp_path, rollup):
    """Create canonical summaries for all configs in rollup."""
    for config in rollup["configs"]:
        run_dir = tmp_path / config["run_dir"] / "artifacts"
        run_dir.mkdir(parents=True)
        (run_dir / "canonical_summary.json").write_text(
            json.dumps({"sanity": {"fail_count": 0, "pass_count": 5}})
        )


def _run_batch_report(tmp_path, extra_args=None):
    """Run generate_batch_report.py and return (exit_code, stdout, stderr)."""
    rollup_path = tmp_path / "rollup.json"
    output_dir = tmp_path / "output"

    cmd = [
        sys.executable,
        "scripts/internal/generate_batch_report.py",
        "--rollup",
        str(rollup_path),
        "--run-dir",
        str(tmp_path),
        "--output",
        str(output_dir),
    ]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
    )
    return result.returncode, result.stdout, result.stderr


class TestBatchReportCLI:
    def test_promotion_missing_artifact_dir_fails(self, tmp_path):
        """Promotion without --artifact-dir should fail artifacts_frozen check."""
        rollup = _make_rollup(batch_purpose="promotion")
        _setup_run_dir(tmp_path, rollup)
        (tmp_path / "rollup.json").write_text(json.dumps(rollup))

        exit_code, stdout, _ = _run_batch_report(tmp_path)
        assert exit_code == 1
        assert "NOT ELIGIBLE" in stdout
        assert "artifacts_frozen" in stdout

    def test_promotion_missing_split_manifest_dir_fails(self, tmp_path):
        """Promotion without --split-manifest-dir should fail split_manifests check."""
        rollup = _make_rollup(batch_purpose="promotion")
        _setup_run_dir(tmp_path, rollup)
        (tmp_path / "rollup.json").write_text(json.dumps(rollup))

        # Provide artifact-dir but not split-manifest-dir
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        artifact_path = artifact_dir / "olsa_v1.json"
        artifact_path.write_text(json.dumps({"frozen_at": None}))
        freeze_artifact(artifact_path)

        exit_code, stdout, _ = _run_batch_report(
            tmp_path, ["--artifact-dir", str(artifact_dir)]
        )
        assert exit_code == 1
        assert "split_manifests" in stdout

    def test_promotion_with_valid_dirs_passes_those_checks(self, tmp_path):
        """Promotion with valid artifact and split dirs should pass those checks."""
        rollup = _make_rollup(batch_purpose="promotion")
        _setup_run_dir(tmp_path, rollup)
        (tmp_path / "rollup.json").write_text(json.dumps(rollup))

        # Create frozen artifact
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        artifact_path = artifact_dir / "olsa_v1.json"
        artifact_path.write_text(json.dumps({"frozen_at": None}))
        freeze_artifact(artifact_path)

        # Create three_way split manifest
        split_dir = tmp_path / "splits"
        split_dir.mkdir()
        (split_dir / "split_manifest_suit.json").write_text(
            json.dumps({"schema_version": 1, "split_type": "three_way"})
        )

        exit_code, stdout, _ = _run_batch_report(
            tmp_path,
            [
                "--artifact-dir",
                str(artifact_dir),
                "--split-manifest-dir",
                str(split_dir),
            ],
        )
        # Still fails because no notebook gate, but artifact and split checks pass
        assert exit_code == 1  # notebook_gate FAIL
        assert "[PASS] artifacts_frozen" in stdout
        assert "[PASS] split_manifests" in stdout

    def test_exploration_passes_without_artifact_dirs(self, tmp_path):
        """Exploration batch should pass without artifact or split dirs."""
        rollup = _make_rollup(batch_purpose="exploration")
        _setup_run_dir(tmp_path, rollup)
        (tmp_path / "rollup.json").write_text(json.dumps(rollup))

        exit_code, stdout, _ = _run_batch_report(tmp_path)
        assert exit_code == 0
        assert "ELIGIBLE" in stdout
