"""
Tests for the report generator script.

Validates that reports are generated correctly with strict I/O contract.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def run_experiment(
    config_path: str, extra_args: list[str] | None = None, run_dir: str | None = None
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


def generate_report(
    run_dir: str, extra_args: list[str] | None = None
) -> subprocess.CompletedProcess:
    """Run the report generator on a run directory."""
    args = ["python", "scripts/generate_report.py", "--run-dir", run_dir]
    if extra_args:
        args.extend(extra_args)

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        env=env,
    )


def test_report_generator_creates_summary():
    """Test that report generator creates ANALYSIS_SUMMARY.md."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run experiment
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir,
        )
        assert (
            result.returncode == 0
        ), f"Experiment should succeed. Error: {result.stderr}"

        # Find run directory
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, f"Expected 1 run directory, found {len(run_dirs)}"
        run_dir = run_dirs[0]

        # Generate report
        result = generate_report(str(run_dir))
        assert (
            result.returncode == 0
        ), f"Report generation should succeed. Error: {result.stderr}"

        # Verify reports/ exists
        reports_dir = run_dir / "reports"
        assert reports_dir.exists(), "reports/ should exist"
        assert reports_dir.is_dir(), "reports/ should be a directory"

        # Verify ANALYSIS_SUMMARY.md exists
        summary_path = reports_dir / "ANALYSIS_SUMMARY.md"
        assert summary_path.exists(), "ANALYSIS_SUMMARY.md should exist"

        # Verify content
        content = summary_path.read_text()
        assert len(content) > 50, "ANALYSIS_SUMMARY.md should be non-trivial"
        assert run_dir.name in content, "Summary should contain run directory name"
        assert (
            "Results Files Discovered" in content
        ), "Summary should have results section"
        assert "Charts Generated" in content, "Summary should have charts section"


def test_report_generator_includes_metadata():
    """Test that report includes seed and n_per from metadata."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run experiment with specific parameters
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "123", "--n_per", "7"],
            run_dir=tmpdir,
        )
        assert (
            result.returncode == 0
        ), f"Experiment should succeed. Error: {result.stderr}"

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # Generate report
        result = generate_report(str(run_dir))
        assert (
            result.returncode == 0
        ), f"Report generation should succeed. Error: {result.stderr}"

        # Verify metadata in summary
        summary_path = run_dir / "reports" / "ANALYSIS_SUMMARY.md"
        content = summary_path.read_text()

        assert "123" in content, "Summary should contain seed value"
        assert "7" in content, "Summary should contain n_per value"


def test_report_generator_handles_empty_results():
    """Test that report generator succeeds even with empty results/ directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal run directory structure manually
        run_dir = Path(tmpdir) / "fake_run"
        run_dir.mkdir()
        (run_dir / "results").mkdir()

        # Create minimal meta.json
        import json

        with open(run_dir / "meta.json", "w") as f:
            json.dump({"seed": 42, "n_per": 0}, f)

        # Generate report (should succeed with no results)
        result = generate_report(str(run_dir))
        assert (
            result.returncode == 0
        ), f"Report generation should succeed with empty results. Error: {result.stderr}"

        # Verify summary exists and notes no results
        summary_path = run_dir / "reports" / "ANALYSIS_SUMMARY.md"
        assert (
            summary_path.exists()
        ), "ANALYSIS_SUMMARY.md should exist even with no results"

        content = summary_path.read_text()
        assert (
            "No results found" in content or len(content) > 0
        ), "Summary should handle empty results gracefully"


def test_report_generator_fails_without_results_directory():
    """Test that report generator fails clearly if results/ missing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a directory without results/
        bad_dir = Path(tmpdir) / "not_a_run"
        bad_dir.mkdir()

        # Try to generate report
        result = generate_report(str(bad_dir))
        assert result.returncode != 0, "Should fail for invalid run directory"
        assert (
            "missing results/" in result.stderr.lower()
            or "not a valid run" in result.stderr.lower()
        ), "Error message should mention missing results/"


def test_report_generator_fails_if_reports_exist_without_overwrite():
    """Test that report generator fails if reports/ exists and --overwrite not set."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run experiment
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir,
        )
        assert result.returncode == 0

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # Generate report first time
        result = generate_report(str(run_dir))
        assert result.returncode == 0, "First report generation should succeed"

        # Try to generate again without --overwrite
        result = generate_report(str(run_dir))
        assert (
            result.returncode != 0
        ), "Should fail when reports/ exists without --overwrite"
        assert "overwrite" in result.stderr.lower(), "Error should mention --overwrite"


def test_report_generator_succeeds_with_overwrite():
    """Test that report generator succeeds with --overwrite flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run experiment
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir,
        )
        assert result.returncode == 0

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # Generate report first time
        result = generate_report(str(run_dir))
        assert result.returncode == 0

        summary_path = run_dir / "reports" / "ANALYSIS_SUMMARY.md"

        # Generate again with --overwrite
        result = generate_report(str(run_dir), ["--overwrite"])
        assert (
            result.returncode == 0
        ), f"Should succeed with --overwrite. Error: {result.stderr}"

        # Verify summary was regenerated
        assert summary_path.exists(), "Summary should still exist after regeneration"
        second_content = summary_path.read_text()

        # Content should be logically similar (same run_id, seed, etc.)
        assert (
            run_dir.name in second_content
        ), "Regenerated summary should contain run_id"


def test_report_generator_writes_only_under_reports_and_artifacts():
    """Test strict I/O contract: writes only under run_dir/reports/ and run_dir/artifacts/."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run experiment
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir,
        )
        assert result.returncode == 0

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # Snapshot files before report generation
        files_before = set(run_dir.rglob("*"))

        # Generate report
        result = generate_report(str(run_dir))
        assert result.returncode == 0

        # Snapshot files after report generation
        files_after = set(run_dir.rglob("*"))

        # Find new files
        new_files = files_after - files_before

        # All new files should be under reports/ or artifacts/
        reports_dir = run_dir / "reports"
        artifacts_dir = run_dir / "artifacts"
        for new_file in new_files:
            if new_file.is_file():
                is_under_reports = new_file.is_relative_to(reports_dir)
                is_under_artifacts = new_file.is_relative_to(artifacts_dir)
                assert (
                    is_under_reports or is_under_artifacts
                ), f"New file should be under reports/ or artifacts/: {new_file.relative_to(run_dir)}"
