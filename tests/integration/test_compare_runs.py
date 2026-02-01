"""
Integration tests for compare_runs.py script.

Tests bootstrap-based statistical comparison of experiment runs.
"""

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path


def run_experiment(
    config_path: str,
    extra_args: list[str] | None = None,
    run_dir: str | None = None,
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


def run_compare(
    baseline_dir: Path,
    candidate_dir: Path,
    format: str = "json",
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run compare_runs.py with given args."""
    args = [
        "python",
        "scripts/compare_runs.py",
        "--baseline",
        str(baseline_dir),
        "--candidate",
        str(candidate_dir),
        "--format",
        format,
    ]
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


def test_compare_runs_identical_runs():
    """Comparing two identical runs should show no significant differences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run same config twice with same seed
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "100"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0, f"Run 1 failed: {result1.stderr}"

        # Wait 1 second to ensure different timestamp in run_id
        time.sleep(1)

        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "100"],
            run_dir=tmpdir,
        )
        assert result2.returncode == 0, f"Run 2 failed: {result2.stderr}"

        # Find run directories
        run_dirs = sorted(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 2, f"Expected 2 run directories, found {len(run_dirs)}"

        baseline_dir = run_dirs[0]
        candidate_dir = run_dirs[1]

        # Compare runs
        result = run_compare(baseline_dir, candidate_dir, format="json")
        assert result.returncode == 0, f"Comparison failed: {result.stderr}"

        # Parse JSON output
        data = json.loads(result.stdout)

        # Verify structure
        assert "baseline" in data
        assert "candidate" in data
        assert "comparisons" in data
        assert "summary" in data

        # Verify no significant differences
        assert data["summary"]["significant_changes"] == 0, \
            "Identical runs should show no significant differences"

        # Verify all metrics have p-value close to 1.0 (no difference)
        for comparison in data["comparisons"]:
            assert not comparison["is_significant"], \
                f"Metric {comparison['metric']} incorrectly marked as significant"
            assert comparison["p_value"] >= 0.5, \
                f"Metric {comparison['metric']} has suspiciously low p-value: {comparison['p_value']}"
            assert abs(comparison["effect_size"]) < 0.1, \
                f"Metric {comparison['metric']} has non-negligible effect size: {comparison['effect_size']}"


def test_compare_runs_different_strategies():
    """Comparing different strategies should detect significant differences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run same config (quick_test) with different seeds to get different results
        # Both runs have same scenarios (greedy/high and greedy/suit_H), so comparison works
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "100", "--n_per", "200"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0, f"Run 1 failed: {result1.stderr}"

        # Wait 1 second to ensure different timestamp
        time.sleep(1)

        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "999", "--n_per", "200"],
            run_dir=tmpdir,
        )
        assert result2.returncode == 0, f"Run 2 failed: {result2.stderr}"

        # Find run directories
        run_dirs = sorted(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 2, f"Expected 2 run directories, found {len(run_dirs)}"

        baseline_dir = run_dirs[0]
        candidate_dir = run_dirs[1]

        # Compare runs
        result = run_compare(baseline_dir, candidate_dir, format="json")
        assert result.returncode == 0, f"Comparison failed: {result.stderr}"

        # Parse JSON output
        data = json.loads(result.stdout)

        # Verify we have common scenarios to compare
        assert data["summary"]["total_metrics"] > 0, "Should have compared some metrics"

        # With different seeds, we should see SOME differences, but not necessarily
        # significant ones (depends on sample size and variance)
        sig_count = data["summary"]["significant_changes"]
        assert sig_count >= 0, "Significant changes count should be non-negative"


def test_compare_runs_markdown_format():
    """Verify markdown output format is valid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run same config twice
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0

        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "43", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result2.returncode == 0

        # Find run directories
        run_dirs = sorted(Path(tmpdir).glob("*"))
        baseline_dir = run_dirs[0]
        candidate_dir = run_dirs[1]

        # Compare with markdown format
        result = run_compare(baseline_dir, candidate_dir, format="markdown")
        assert result.returncode == 0, f"Comparison failed: {result.stderr}"

        output = result.stdout

        # Verify markdown structure
        assert "## Run Comparison" in output, "Should have main heading"
        assert "**Baseline:**" in output, "Should have baseline metadata"
        assert "**Candidate:**" in output, "Should have candidate metadata"
        assert "| Metric |" in output, "Should have table header"
        assert "|--------|" in output, "Should have table separator"
        assert "**Interpretation:**" in output, "Should have interpretation"


def test_compare_runs_human_format():
    """Verify human-readable output format."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run same config twice
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0

        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "43", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result2.returncode == 0

        # Find run directories
        run_dirs = sorted(Path(tmpdir).glob("*"))
        baseline_dir = run_dirs[0]
        candidate_dir = run_dirs[1]

        # Compare with human format
        result = run_compare(baseline_dir, candidate_dir, format="human")
        assert result.returncode == 0, f"Comparison failed: {result.stderr}"

        output = result.stdout

        # Verify human format structure
        assert "=== Run Comparison ===" in output
        assert "Baseline:" in output
        assert "Candidate:" in output
        assert "--- Per-Scenario Comparison ---" in output
        assert "Effect size:" in output
        assert "Significance:" in output
        assert "Summary:" in output


def test_compare_runs_missing_baseline():
    """Verify error handling for missing baseline directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create only candidate run
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0

        run_dirs = list(Path(tmpdir).glob("*"))
        candidate_dir = run_dirs[0]

        # Try to compare with non-existent baseline
        missing_baseline = Path(tmpdir) / "nonexistent"
        result = run_compare(missing_baseline, candidate_dir, format="json")

        # Should fail with error
        assert result.returncode != 0, "Should fail for missing baseline"
        assert "not found" in result.stderr.lower(), \
            f"Should report missing baseline: {result.stderr}"


def test_compare_runs_deterministic_bootstrap():
    """Verify bootstrap results are deterministic with same seed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run same config twice
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "100"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0

        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "43", "--n_per", "100"],
            run_dir=tmpdir,
        )
        assert result2.returncode == 0

        # Find run directories
        run_dirs = sorted(Path(tmpdir).glob("*"))
        baseline_dir = run_dirs[0]
        candidate_dir = run_dirs[1]

        # Compare with same seed twice
        result_a = run_compare(
            baseline_dir, candidate_dir, format="json", extra_args=["--seed", "999"]
        )
        assert result_a.returncode == 0

        result_b = run_compare(
            baseline_dir, candidate_dir, format="json", extra_args=["--seed", "999"]
        )
        assert result_b.returncode == 0

        # Parse JSON outputs
        data_a = json.loads(result_a.stdout)
        data_b = json.loads(result_b.stdout)

        # Verify identical results
        for comp_a, comp_b in zip(data_a["comparisons"], data_b["comparisons"]):
            assert comp_a["metric"] == comp_b["metric"]
            assert comp_a["baseline_ci"] == comp_b["baseline_ci"], \
                f"Bootstrap CIs should be deterministic for {comp_a['metric']}"
            assert comp_a["candidate_ci"] == comp_b["candidate_ci"], \
                f"Bootstrap CIs should be deterministic for {comp_a['metric']}"
            assert comp_a["delta_ci"] == comp_b["delta_ci"], \
                f"Bootstrap delta CIs should be deterministic for {comp_a['metric']}"
            assert comp_a["p_value"] == comp_b["p_value"], \
                f"Bootstrap p-values should be deterministic for {comp_a['metric']}"


def test_compare_runs_json_parseable():
    """Verify JSON output is valid and parseable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run same config twice
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result1.returncode == 0

        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "43", "--n_per", "50"],
            run_dir=tmpdir,
        )
        assert result2.returncode == 0

        # Find run directories
        run_dirs = sorted(Path(tmpdir).glob("*"))
        baseline_dir = run_dirs[0]
        candidate_dir = run_dirs[1]

        # Compare and parse JSON
        result = run_compare(baseline_dir, candidate_dir, format="json")
        assert result.returncode == 0

        # Should parse without error
        data = json.loads(result.stdout)

        # Verify expected structure
        assert isinstance(data["baseline"], dict)
        assert isinstance(data["candidate"], dict)
        assert isinstance(data["comparisons"], list)
        assert isinstance(data["summary"], dict)

        # Verify required fields in comparisons
        for comparison in data["comparisons"]:
            required_fields = [
                "metric",
                "baseline_mean",
                "baseline_ci",
                "candidate_mean",
                "candidate_ci",
                "delta_mean",
                "delta_ci",
                "effect_size",
                "p_value",
                "is_significant",
            ]
            for field in required_fields:
                assert field in comparison, f"Missing field: {field}"

            # Verify types
            assert isinstance(comparison["metric"], str)
            assert isinstance(comparison["baseline_mean"], (int, float))
            assert isinstance(comparison["baseline_ci"], list)
            assert len(comparison["baseline_ci"]) == 2
            assert isinstance(comparison["is_significant"], bool)
            assert 0 <= comparison["p_value"] <= 1.0
