"""
Tests for experiment runner determinism enforcement and CLI behavior.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def run_experiment(
    config_path: str, extra_args: list[str] | None = None
) -> subprocess.CompletedProcess:
    """Run the experiment runner with given args."""
    args = ["python", "experiments/run_experiment.py", "--config", config_path]
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


def test_runner_fails_without_seed():
    """CLI must fail if no seed and no --allow-nondeterministic."""
    # Create a temporary config without seed
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "no_seed.yaml"
        config_path.write_text("""
experiment_name: no_seed_test
parameters:
  n_per: 1
  log_level: none

strategies:
  - name: random
    class_name: RandomLegalStrategy

scenarios:
  - contract_type: high
""")

        result = run_experiment(str(config_path), ["--n_per", "1"])

        assert result.returncode != 0, "Runner should fail without seed"
        assert (
            "--seed is required" in result.stderr
            or "--seed is required" in result.stdout
        ), f"Error message should mention --seed requirement. Got: {result.stderr}"


def test_runner_succeeds_with_seed():
    """CLI must succeed with explicit seed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "1", "--run-dir", tmpdir],
        )

        assert (
            result.returncode == 0
        ), f"Runner should succeed with seed. Error: {result.stderr}"


def test_runner_succeeds_with_allow_nondeterministic():
    """CLI must succeed with --allow-nondeterministic (no seed)."""
    # Create a config without seed
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "no_seed.yaml"
        config_path.write_text("""
experiment_name: nondeterministic_test
parameters:
  n_per: 1
  log_level: none

strategies:
  - name: random
    class_name: RandomLegalStrategy

scenarios:
  - contract_type: high
""")

        result = run_experiment(
            str(config_path),
            ["--allow-nondeterministic", "--n_per", "1", "--run-dir", tmpdir],
        )

        assert (
            result.returncode == 0
        ), f"Runner should succeed with --allow-nondeterministic. Error: {result.stderr}"


def test_seed_wins_over_allow_nondeterministic():
    """If both --seed and --allow-nondeterministic provided, seed wins (deterministic)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            [
                "--seed",
                "42",
                "--allow-nondeterministic",
                "--n_per",
                "1",
                "--run-dir",
                tmpdir,
            ],
        )

        assert result.returncode == 0, f"Runner should succeed. Error: {result.stderr}"

        # Find the run directory
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, f"Expected 1 run directory, found {len(run_dirs)}"

        meta_path = run_dirs[0] / "meta.json"
        assert meta_path.exists(), "meta.json should exist"

        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["seed"] == 42, "Seed should be 42 (from CLI)"
        assert meta["is_deterministic"] is True, "Run should be deterministic"


def test_determinism_same_seed_produces_same_results():
    """Same seed + same config produces identical aggregate metrics."""
    with (
        tempfile.TemporaryDirectory() as tmpdir1,
        tempfile.TemporaryDirectory() as tmpdir2,
    ):
        # Run 1
        result1 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "10", "--run-dir", tmpdir1],
        )
        assert result1.returncode == 0, f"Run 1 failed: {result1.stderr}"

        # Get run 1 results (pick first strategy's first scenario)
        run_dirs_1 = list(Path(tmpdir1).glob("*"))
        assert (
            len(run_dirs_1) == 1
        ), f"Expected 1 run dir in tmpdir1, got {len(run_dirs_1)}"
        results1_dir = run_dirs_1[0] / "results"
        strategy_dirs = list(results1_dir.glob("*"))
        assert len(strategy_dirs) > 0, "Expected at least one strategy results dir"

        result_files = list(strategy_dirs[0].glob("*.json"))
        assert len(result_files) > 0, "Expected at least one result file"

        with open(result_files[0]) as f:
            results1 = json.load(f)

        # Run 2 (same seed, different tmpdir)
        result2 = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "10", "--run-dir", tmpdir2],
        )
        assert result2.returncode == 0, f"Run 2 failed: {result2.stderr}"

        # Get run 2 results
        run_dirs_2 = list(Path(tmpdir2).glob("*"))
        assert (
            len(run_dirs_2) == 1
        ), f"Expected 1 run dir in tmpdir2, got {len(run_dirs_2)}"
        results2_dir = run_dirs_2[0] / "results"
        strategy_dirs2 = list(results2_dir.glob("*"))
        result_files2 = list(strategy_dirs2[0].glob("*.json"))

        with open(result_files2[0]) as f:
            results2 = json.load(f)

        # Assert determinism: same aggregate metrics (within fixed precision)
        assert results1["hands"] == results2["hands"], "Hand count should match"
        assert (
            abs(results1["avg_team0"] - results2["avg_team0"]) < 0.001
        ), f"avg_team0 should match: {results1['avg_team0']} vs {results2['avg_team0']}"
        assert (
            abs(results1["avg_team1"] - results2["avg_team1"]) < 0.001
        ), f"avg_team1 should match: {results1['avg_team1']} vs {results2['avg_team1']}"

        # Distribution should match exactly
        assert (
            results1["distribution_team0"] == results2["distribution_team0"]
        ), "Team0 distribution should match exactly"


def test_nondeterministic_run_records_metadata():
    """Nondeterministic run should record seed=null and is_deterministic=false."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create config without seed
        config_path = Path(tmpdir) / "noseed.yaml"
        config_path.write_text("""
experiment_name: nondeterministic_test
parameters:
  n_per: 1
  log_level: none

strategies:
  - name: random
    class_name: RandomLegalStrategy

scenarios:
  - contract_type: high
""")

        result = run_experiment(
            str(config_path),
            ["--allow-nondeterministic", "--n_per", "1", "--run-dir", tmpdir],
        )

        assert result.returncode == 0, f"Runner should succeed. Error: {result.stderr}"

        run_dirs = [d for d in Path(tmpdir).glob("*") if d.is_dir()]
        assert len(run_dirs) == 1, f"Expected 1 run dir, found {len(run_dirs)}"

        meta_path = run_dirs[0] / "meta.json"
        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["seed"] is None, "Seed should be null for nondeterministic run"
        assert (
            meta["is_deterministic"] is False
        ), "Run should be marked nondeterministic"


def test_config_seed_works():
    """Seed from config file should work (no CLI seed needed)."""
    # Create a temporary config with seed
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "test_config.yaml"
        config_path.write_text("""
experiment_name: test_determinism
parameters:
  n_per: 1
  seed: 123
  log_level: none

strategies:
  - name: random
    class_name: RandomLegalStrategy

scenarios:
  - contract_type: high
""")

        result = run_experiment(str(config_path), ["--run-dir", tmpdir])

        assert (
            result.returncode == 0
        ), f"Runner should succeed with config seed. Error: {result.stderr}"

        run_dirs = [d for d in Path(tmpdir).glob("*") if d.is_dir()]
        assert len(run_dirs) == 1

        meta_path = run_dirs[0] / "meta.json"
        with open(meta_path) as f:
            meta = json.load(f)

        assert meta["seed"] == 123, "Seed from config should be used"
        assert meta["is_deterministic"] is True, "Run should be deterministic"
