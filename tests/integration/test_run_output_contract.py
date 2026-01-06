"""
Tests for run output structure contract.

Validates that every run creates the required directory skeleton and config snapshot.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import yaml


def run_experiment(config_path: str, extra_args: list[str] | None = None, run_dir: str | None = None) -> subprocess.CompletedProcess:
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


def test_run_output_structure_contract():
    """Verify every run creates the required output structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run with minimal config
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Run should succeed. Error: {result.stderr}"

        # Find the run directory (should be only one)
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, f"Expected 1 run directory, found {len(run_dirs)}"

        run_dir = run_dirs[0]

        # Verify required files exist
        assert (run_dir / "meta.json").exists(), "meta.json should exist"
        assert (run_dir / "config_effective.yaml").exists(), "config_effective.yaml should exist"
        assert (run_dir / "perf.json").exists(), "perf.json should exist"

        # Verify required directories exist
        assert (run_dir / "results").is_dir(), "results/ directory should exist"
        assert (run_dir / "logs").is_dir(), "logs/ directory should exist"
        assert (run_dir / "reports").is_dir(), "reports/ directory should exist"
        assert (run_dir / "splits").is_dir(), "splits/ directory should exist"
        assert (run_dir / "artifacts").is_dir(), "artifacts/ directory should exist"


def test_config_effective_is_valid_and_useful():
    """Verify config_effective.yaml is valid YAML and contains effective values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run with overrides
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "10"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Run should succeed. Error: {result.stderr}"

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        config_path = run_dir / "config_effective.yaml"
        assert config_path.exists(), "config_effective.yaml should exist"

        # Parse as YAML
        with open(config_path) as f:
            effective_config = yaml.safe_load(f)

        assert effective_config is not None, "Config should be valid YAML"
        assert isinstance(effective_config, dict), "Config should be a dict"

        # Verify it contains the overridden values
        assert "parameters" in effective_config, "Config should have parameters section"
        params = effective_config["parameters"]

        assert params["seed"] == 42, f"Seed should be 42 (overridden), got {params.get('seed')}"
        assert params["n_per"] == 10, f"n_per should be 10 (overridden), got {params.get('n_per')}"
        assert params["log_level"] == "none", "log_level should be set"

        # Verify it has strategies and scenarios
        assert "strategies" in effective_config, "Config should have strategies"
        assert len(effective_config["strategies"]) > 0, "Should have at least one strategy"

        assert "scenarios" in effective_config, "Config should have scenarios"
        assert len(effective_config["scenarios"]) > 0, "Should have at least one scenario"


def test_run_output_is_self_contained():
    """Verify all outputs are written only under the run directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Run should succeed. Error: {result.stderr}"

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # Count all files written (recursively)
        all_files = list(run_dir.rglob("*"))
        files_only = [f for f in all_files if f.is_file()]

        # Should have at least: meta.json, config_effective.yaml, perf.json, and some result files
        assert len(files_only) >= 3, f"Should have multiple output files, found {len(files_only)}"

        # All files should be under the run directory
        for file_path in files_only:
            assert file_path.is_relative_to(run_dir), \
                f"File {file_path} should be under run directory {run_dir}"


def test_empty_directories_are_created():
    """Verify empty directories (splits, artifacts, reports) are created even if unused."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/quick_test.yaml",
            ["--seed", "42", "--n_per", "5", "--log-level", "none"],
            run_dir=tmpdir
        )

        assert result.returncode == 0, f"Run should succeed. Error: {result.stderr}"

        run_dirs = list(Path(tmpdir).glob("*"))
        run_dir = run_dirs[0]

        # These directories might be empty but should still exist
        for dir_name in ["splits", "artifacts", "reports"]:
            dir_path = run_dir / dir_name
            assert dir_path.exists(), f"{dir_name}/ should exist"
            assert dir_path.is_dir(), f"{dir_name}/ should be a directory"
