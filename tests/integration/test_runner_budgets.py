"""Integration tests for runner work budget enforcement."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def run_experiment(
    config_path: str,
    extra_args: list[str] | None = None,
    run_dir: str | None = None,
    expect_failure: bool = False,
) -> subprocess.CompletedProcess:
    """Run the experiment runner with given args.

    Args:
        config_path: Path to config file
        extra_args: Additional command-line arguments
        run_dir: Optional run directory override
        expect_failure: If True, don't raise on non-zero exit code

    Returns:
        CompletedProcess with stdout/stderr captured
    """
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
        check=not expect_failure,
    )


def test_runner_enforces_work_budget():
    """Runner should block runs exceeding work budget."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # quick_test budget is 1,000 total hands
        # Config has 2 strategies and 2 scenarios
        # total_hands = plan_count (2) * scenarios (2) * n_per
        # n_per=300 gives 2 * 2 * 300 = 1,200 total hands (exceeds 1,000 budget)
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            extra_args=["--seed", "42", "--n_per", "300"],
            run_dir=tmpdir,
            expect_failure=True,
        )

        assert result.returncode != 0, "Should fail when budget exceeded"
        assert (
            "Total hands budget exceeded" in result.stderr
            or "Total hands budget exceeded" in result.stdout
        ), f"Should mention budget exceeded. stderr: {result.stderr}, stdout: {result.stdout}"


def test_runner_allows_force_override():
    """--force should override work budget."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Same scenario as above (1,200 hands > 1,000 budget), but with --force
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            extra_args=["--seed", "42", "--n_per", "300", "--force"],
            run_dir=tmpdir,
        )

        assert (
            result.returncode == 0
        ), f"Should succeed with --force. stderr: {result.stderr}"

        # Verify run directory was created
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, "Should create exactly one run directory"


def test_runner_allows_runs_within_budget():
    """Runs within budget should proceed without --force."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # quick_test budget is 1,000 total hands
        # Config has 2 strategies and 2 scenarios
        # total_hands = plan_count (2) * scenarios (2) * n_per
        # n_per=200 gives 2 * 2 * 200 = 800 total hands (within budget)
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            extra_args=["--seed", "42", "--n_per", "200"],
            run_dir=tmpdir,
        )

        assert (
            result.returncode == 0
        ), f"Should succeed within budget. stderr: {result.stderr}"

        # Verify run completed
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, "Should create exactly one run directory"


def test_runner_budget_check_uses_config_name():
    """Budget check should use config name, not override value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # quick_test has experiment_name "quick_test" and budget 1,000
        # Verify budget check uses experiment_name from config
        # n_per=300 gives 2 * 2 * 300 = 1,200 (exceeds 1,000)
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            extra_args=["--seed", "42", "--n_per", "300"],
            run_dir=tmpdir,
            expect_failure=True,
        )

        assert result.returncode != 0, "Should fail when budget exceeded"
        assert "quick_test" in (
            result.stderr + result.stdout
        ), "Error message should mention config name"


def test_runner_no_budget_for_unlisted_configs():
    """Configs without budget entries should run without restriction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # baseline_greedy is not in TOTAL_HANDS_BUDGETS, so no budget check
        # This should run regardless of size
        result = run_experiment(
            "experiments/configs/baseline_greedy.yaml",
            extra_args=["--seed", "42", "--n_per", "50"],
            run_dir=tmpdir,
        )

        assert (
            result.returncode == 0
        ), f"Should succeed for unlisted config. stderr: {result.stderr}"
