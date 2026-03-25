"""
Integration test: deterministic repeatability.

Runs the canonical runner twice with the same config+seed+n_per and asserts
that stable output artifacts match exactly.

This is a regression guard to catch changes to RNG propagation, deal seeding,
config resolution, or runner determinism.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration
import yaml

CONFIG_PATH = "experiments/configs/quick_test.yaml"
SEED = 42
N_PER = 5


def _run_experiment_once(tmp_path: Path, label: str) -> Path:
    """
    Run the canonical experiment runner once and return the created run directory.
    Writes only under tmp_path.
    """
    run_base = tmp_path / f"run_base_{label}"
    run_base.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python",
        "experiments/run_experiment.py",
        "--config",
        CONFIG_PATH,
        "--seed",
        str(SEED),
        "--n_per",
        str(N_PER),
        "--log-level",
        "none",
        "--run-dir",
        str(run_base),
    ]

    env = {**os.environ, "PYTHONPATH": "src"}

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    except subprocess.CalledProcessError as e:
        pytest.fail(
            "Runner failed:\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Stdout:\n{e.stdout}\n"
            f"Stderr:\n{e.stderr}"
        )

    run_dirs = [d for d in run_base.iterdir() if d.is_dir()]
    assert (
        len(run_dirs) == 1
    ), f"Expected 1 run dir under {run_base}, got {len(run_dirs)}: {run_dirs}"
    return run_dirs[0]


def _load_config_effective(run_dir: Path) -> dict:
    """Load and parse config_effective.yaml."""
    cfg_path = run_dir / "config_effective.yaml"
    assert cfg_path.exists(), f"Missing {cfg_path}"
    with cfg_path.open("r") as f:
        return yaml.safe_load(f)


def _load_all_results(results_dir: Path) -> dict[str, object]:
    """
    Load all JSON result files under results_dir, keyed by relative path.
    """
    assert results_dir.exists(), f"Missing results dir: {results_dir}"
    out: dict[str, object] = {}
    for jf in sorted(results_dir.rglob("*.json")):
        rel = jf.relative_to(results_dir)
        with jf.open("r") as f:
            out[str(rel)] = json.load(f)
    return out


def test_determinism_repeatability(tmp_path: Path) -> None:
    """
    Run the canonical runner twice with same seed and assert stable outputs match.

    This test:
    - Runs experiments/run_experiment.py twice with identical parameters
    - Compares stable artifacts (config_effective.yaml, results/**/*.json)
    - Asserts contract files exist (meta.json, perf.json) but does not compare them
    - Uses exact equality (no tolerance) - any differences indicate a determinism bug
    """
    run1 = _run_experiment_once(tmp_path, "one")
    run2 = _run_experiment_once(tmp_path, "two")

    # Contract assertions (existence only; do not compare)
    assert (run1 / "meta.json").exists(), f"Missing meta.json in {run1}"
    assert (run2 / "meta.json").exists(), f"Missing meta.json in {run2}"
    assert (run1 / "perf.json").exists(), f"Missing perf.json in {run1}"
    assert (run2 / "perf.json").exists(), f"Missing perf.json in {run2}"

    # Stable comparisons: config_effective.yaml
    cfg1 = _load_config_effective(run1)
    cfg2 = _load_config_effective(run2)
    assert cfg1 == cfg2, "config_effective.yaml differs between runs"

    # Stable comparisons: results/**/*.json
    res1 = _load_all_results(run1 / "results")
    res2 = _load_all_results(run2 / "results")

    assert res1.keys() == res2.keys(), (
        f"Result file set differs between runs:\n"
        f"Run 1: {sorted(res1.keys())}\n"
        f"Run 2: {sorted(res2.keys())}"
    )

    for k in res1:
        assert res1[k] == res2[k], f"Results differ for {k}"
