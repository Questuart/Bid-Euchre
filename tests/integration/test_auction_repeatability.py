"""
Test for auction mode repeatability under deal_seed.

Verifies that auction mode produces byte-identical results when run with the same
inputs (seed, deal_seed behavior).
"""

import filecmp
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


def test_auction_repeatability():
    """Verify auction mode produces identical results across repeated runs with same seed."""
    config_path = "experiments/configs/auction_smoke.yaml"

    with tempfile.TemporaryDirectory() as tmpdir:
        # First run
        result1 = run_experiment(
            config_path, ["--seed", "42", "--n_per", "5"], run_dir=f"{tmpdir}/run1"
        )
        assert result1.returncode == 0, f"First run failed: {result1.stderr}"

        # Second run (same inputs)
        result2 = run_experiment(
            config_path, ["--seed", "42", "--n_per", "5"], run_dir=f"{tmpdir}/run2"
        )
        assert result2.returncode == 0, f"Second run failed: {result2.stderr}"

        # Find result directories
        run1_dir = Path(tmpdir) / "run1"
        run2_dir = Path(tmpdir) / "run2"

        run1_subdirs = list(run1_dir.glob("*"))
        run2_subdirs = list(run2_dir.glob("*"))

        assert (
            len(run1_subdirs) == 1
        ), f"Expected 1 run dir in run1, got {len(run1_subdirs)}"
        assert (
            len(run2_subdirs) == 1
        ), f"Expected 1 run dir in run2, got {len(run2_subdirs)}"

        run1_results = run1_subdirs[0] / "results"
        run2_results = run2_subdirs[0] / "results"

        # Compare all result files (should be byte-identical)
        run1_files = list(run1_results.rglob("*.json"))
        run2_files = list(run2_results.rglob("*.json"))

        assert len(run1_files) > 0, "No result files found in first run"
        assert len(run1_files) == len(
            run2_files
        ), f"Different number of result files: {len(run1_files)} vs {len(run2_files)}"

        # Sort files by relative path for comparison
        run1_files.sort(key=lambda p: p.relative_to(run1_results))
        run2_files.sort(key=lambda p: p.relative_to(run2_results))

        for f1, f2 in zip(run1_files, run2_files):
            assert f1.relative_to(run1_results) == f2.relative_to(
                run2_results
            ), f"File paths don't match: {f1} vs {f2}"
            assert filecmp.cmp(f1, f2, shallow=False), f"Files differ: {f1} vs {f2}"
