"""
Integration tests for the experiment runner's fail-fast validation paths.
"""

import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def run_experiment(
    config_path: str, extra_args: list[str] | None = None
) -> subprocess.CompletedProcess:
    """Invoke the canonical runner using the provided config."""
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


def _assert_validation_error(result: subprocess.CompletedProcess, substring: str):
    """Assert that the runner exited with a validation error."""
    assert result.returncode != 0, "Runner should exit non-zero for validation errors"
    assert (
        "Traceback" not in result.stderr
    ), "Validation errors must not print a traceback"
    assert (
        substring in result.stderr
    ), f"Expected substring '{substring}' in stderr: {result.stderr}"
    assert "Error:" in result.stderr, f"Expected 'Error:' prefix: {result.stderr}"


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "runner_validation.yaml"
    config_path.write_text(content.strip() + "\n")
    return config_path


def test_runner_fails_with_empty_scenarios(tmp_path: Path):
    config = """
experiment_name: empty_scenarios
strategies:
  - name: greedy
    class_name: GreedyStrategy

scenarios: []

parameters:
  seed: 42
  n_per: 10
"""

    config_path = _write_config(tmp_path, config)
    result = run_experiment(str(config_path))

    _assert_validation_error(result, "No scenarios configured in")


def test_runner_fails_with_empty_strategies(tmp_path: Path):
    config = """
experiment_name: empty_strategies

strategies: []

scenarios:
  - contract_type: high

parameters:
  seed: 42
  n_per: 10
"""

    config_path = _write_config(tmp_path, config)
    result = run_experiment(str(config_path))

    _assert_validation_error(result, "No strategies or bidding_policies configured in")


def test_runner_fails_with_invalid_n_per(tmp_path: Path):
    config = """
experiment_name: invalid_n_per

strategies:
  - name: greedy
    class_name: GreedyStrategy

scenarios:
  - contract_type: high

parameters:
  seed: 42
  n_per: 0
"""

    config_path = _write_config(tmp_path, config)
    result = run_experiment(str(config_path))

    _assert_validation_error(result, "`n_per` must be greater than 0")


def test_runner_fails_when_config_file_missing(tmp_path: Path):
    missing_path = tmp_path / "does_not_exist.yaml"
    result = run_experiment(str(missing_path))

    expected = f"Configuration file not found: {missing_path}"
    _assert_validation_error(result, expected)
