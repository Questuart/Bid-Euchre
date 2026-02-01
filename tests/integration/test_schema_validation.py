"""
Integration tests for schema validation.

Tests that experiment runs produce outputs conforming to documented schemas:
- meta.json (schema v2)
- results JSON files
- rollup.json (schema v1 from suite runs)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from bid_euchre.validation.schemas import (
    ValidationError,
    validate_meta_v2,
    validate_results_json,
    validate_rollup_v1,
)


def run_experiment(
    config_path: str,
    extra_args: list[str] | None = None,
    run_dir: str | None = None
) -> subprocess.CompletedProcess:
    """Run the experiment runner with given args."""
    args = ["python", "experiments/run_experiment.py", "--config", config_path]
    if extra_args:
        args.extend(extra_args)
    if run_dir:
        args.extend(["--run-dir", run_dir])

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=env,
    )


def run_suite(
    suite_path: str,
    extra_args: list[str] | None = None,
    run_dir: str | None = None
) -> subprocess.CompletedProcess:
    """Run the suite runner with given args."""
    args = ["python", "scripts/run_suite.py", "--suite", suite_path]
    if extra_args:
        args.extend(extra_args)
    if run_dir:
        args.extend(["--run-dir", run_dir])

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=env,
    )


def test_quick_test_produces_valid_meta_v2():
    """Run quick_test and validate meta.json schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Run should succeed. Error: {result.stderr}"

        # Find run directory
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, f"Expected 1 run directory, found {len(run_dirs)}"
        run_dir = run_dirs[0]

        # Load and validate meta.json
        meta_path = run_dir / "meta.json"
        assert meta_path.exists(), "meta.json should exist"

        with open(meta_path) as f:
            meta = json.load(f)

        errors = validate_meta_v2(meta)
        assert not errors, f"meta.json validation errors: {errors}"


def test_quick_test_produces_valid_results():
    """Validate all results JSON files match contract."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Run should succeed. Error: {result.stderr}"

        # Find run directory
        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # Validate all result files
        results_dir = run_dir / "results"
        assert results_dir.exists(), "results/ directory should exist"

        result_files = list(results_dir.rglob("*.json"))
        assert len(result_files) > 0, "Should have at least one result file"

        for results_file in result_files:
            with open(results_file) as f:
                results = json.load(f)

            errors = validate_results_json(results)
            assert not errors, \
                f"{results_file.name} validation errors: {errors}"


def test_suite_produces_valid_rollup():
    """Validate rollup.json from suite run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run baseline_tiny suite (small and fast)
        result = run_suite(
            "experiments/suites/baseline_tiny.yaml",
            ["--seed", "42", "--n-per", "5"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Suite run should succeed. Error: {result.stderr}"

        # Find suite rollup directory (starts with "suite_")
        suite_dirs = list(Path(tmpdir).glob("suite_*"))
        assert len(suite_dirs) >= 1, f"Expected at least 1 suite directory, found {len(suite_dirs)}"

        # Use the most recent suite dir (in case multiple runs)
        suite_dir = sorted(suite_dirs, key=lambda p: p.name)[-1]

        # Load and validate rollup.json
        rollup_path = suite_dir / "rollup.json"
        assert rollup_path.exists(), "rollup.json should exist"

        with open(rollup_path) as f:
            rollup = json.load(f)

        errors = validate_rollup_v1(rollup)
        assert not errors, f"rollup.json validation errors: {errors}"


def test_meta_validator_catches_missing_field():
    """Verify validator catches missing required fields."""
    invalid_meta = {
        "schema_version": 2,
        "run_id": "test_run",
        # Missing created_at_utc and other required fields
    }

    errors = validate_meta_v2(invalid_meta)
    assert len(errors) > 0, "Should catch missing fields"
    assert any("created_at_utc" in err for err in errors), \
        f"Should catch missing created_at_utc: {errors}"


def test_meta_validator_catches_wrong_schema_version():
    """Verify validator catches wrong schema version."""
    invalid_meta = {
        "schema_version": 1,  # Wrong version
        "run_id": "test_run",
        "created_at_utc": "2026-01-31T00:00:00Z",
        "git_sha": "abc123",
        "config_path": "test.yaml",
        "config_sha256": "0" * 64,
        "is_deterministic": True,
        "seed": 42,
        "n_per": 100,
    }

    errors = validate_meta_v2(invalid_meta)
    assert len(errors) > 0, "Should catch wrong schema version"
    assert any("schema_version must be 2" in err for err in errors), \
        f"Should catch schema version mismatch: {errors}"


def test_meta_validator_catches_invalid_timestamp():
    """Verify validator catches invalid UTC timestamp format."""
    invalid_meta = {
        "schema_version": 2,
        "run_id": "test_run",
        "created_at_utc": "2026-01-31T00:00:00",  # Missing Z suffix
        "git_sha": "abc123",
        "config_path": "test.yaml",
        "config_sha256": "0" * 64,
        "is_deterministic": True,
        "seed": 42,
        "n_per": 100,
    }

    errors = validate_meta_v2(invalid_meta)
    assert len(errors) > 0, "Should catch invalid timestamp"
    assert any("ISO-8601 with Z suffix" in err for err in errors), \
        f"Should catch timestamp format error: {errors}"


def test_results_validator_catches_missing_distribution():
    """Verify results validator catches missing distribution_team0 field."""
    invalid_results = {
        "hands": 100,
        "avg_team0": 5.2,
        "avg_team1": 4.8,
        # Missing distribution_team0 (required field)
    }

    errors = validate_results_json(invalid_results)
    assert len(errors) > 0, "Should catch missing distribution_team0"
    assert any("distribution_team0" in err for err in errors), \
        f"Should catch missing distribution: {errors}"


def test_results_validator_catches_invalid_avg_range():
    """Verify results validator catches out-of-range averages."""
    invalid_results = {
        "hands": 100,
        "avg_team0": 15.0,  # Out of range [0, 10]
        "avg_team1": 4.8,
        "distribution_team0": {},
    }

    errors = validate_results_json(invalid_results)
    assert len(errors) > 0, "Should catch out-of-range average"
    assert any("avg_team0" in err and "range" in err.lower() for err in errors), \
        f"Should catch range error: {errors}"


def test_rollup_validator_catches_missing_summary():
    """Verify rollup validator catches missing summary field."""
    invalid_rollup = {
        "schema_version": 1,
        "suite_name": "test_suite",
        "suite_seed": 42,
        "suite_n_per": 100,
        "created_at_utc": "2026-01-31T00:00:00Z",
        "configs": [],
        # Missing summary
    }

    errors = validate_rollup_v1(invalid_rollup)
    assert len(errors) > 0, "Should catch missing summary"
    assert any("summary" in err for err in errors), \
        f"Should catch missing summary: {errors}"


def test_validation_error_exception():
    """Verify ValidationError can be raised with raise_on_error flag."""
    invalid_meta = {"schema_version": 1}  # Wrong version, missing fields

    try:
        validate_meta_v2(invalid_meta, raise_on_error=True)
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert len(e.errors) > 0, "ValidationError should contain error list"
        assert "schema_version must be 2" in str(e), \
            f"ValidationError message should mention schema version: {e}"
