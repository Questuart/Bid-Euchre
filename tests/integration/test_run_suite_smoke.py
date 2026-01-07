"""
Integration test: suite runner smoke test.

Runs the suite runner on baseline_tiny.yaml with minimal settings
and verifies the suite rollup structure.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

SUITE_PATH = "experiments/suites/baseline_tiny.yaml"
SEED = 42
N_PER = 5


def test_run_suite_smoke(tmp_path: Path) -> None:
    """
    Run suite runner on baseline_tiny and verify rollup structure.
    
    This test:
    - Runs scripts/run_suite.py with ultra-small settings (n_per=5)
    - Verifies 4 directories created (3 experiment runs + 1 rollup)
    - Checks rollup contains required files and structure
    - Verifies each member run has required files
    """
    # Snapshot existing directories
    dirs_before = set(d.name for d in tmp_path.iterdir() if d.is_dir())
    
    cmd = [
        "python",
        "scripts/run_suite.py",
        "--suite", SUITE_PATH,
        "--seed", str(SEED),
        "--n-per", str(N_PER),
        "--run-dir", str(tmp_path),
        "--no-reports"  # Speed up test
    ]
    
    env = {**os.environ, "PYTHONPATH": "src"}
    
    try:
        subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"Suite runner failed:\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Stdout:\n{e.stdout}\n"
            f"Stderr:\n{e.stderr}"
        )
    
    # Discover new directories
    dirs_after = set(d.name for d in tmp_path.iterdir() if d.is_dir())
    new_dirs = dirs_after - dirs_before
    
    # Should have exactly 4 new directories (3 experiment runs + 1 rollup)
    assert len(new_dirs) == 4, (
        f"Expected 4 new directories (3 runs + 1 rollup), found {len(new_dirs)}: "
        f"{sorted(new_dirs)}"
    )
    
    # Identify rollup directory (starts with "suite_" or contains rollup.json)
    rollup_dir = None
    member_run_dirs = []
    
    for dir_name in new_dirs:
        dir_path = tmp_path / dir_name
        if (dir_path / "rollup.json").exists():
            rollup_dir = dir_path
        else:
            member_run_dirs.append(dir_path)
    
    assert rollup_dir is not None, (
        f"Could not find rollup directory (no rollup.json found). "
        f"Directories: {sorted(new_dirs)}"
    )
    
    assert len(member_run_dirs) == 3, (
        f"Expected 3 member run directories, found {len(member_run_dirs)}"
    )
    
    # Verify rollup directory structure
    assert (rollup_dir / "meta.json").exists(), "Missing rollup meta.json"
    assert (rollup_dir / "suite_effective.yaml").exists(), "Missing suite_effective.yaml"
    assert (rollup_dir / "rollup.json").exists(), "Missing rollup.json"
    assert (rollup_dir / "reports" / "ROLLUP.md").exists(), "Missing reports/ROLLUP.md"
    
    # Verify required subdirectories exist (even if empty)
    assert (rollup_dir / "results").is_dir(), "Missing results/ directory"
    assert (rollup_dir / "logs").is_dir(), "Missing logs/ directory"
    assert (rollup_dir / "reports").is_dir(), "Missing reports/ directory"
    assert (rollup_dir / "splits").is_dir(), "Missing splits/ directory"
    assert (rollup_dir / "artifacts").is_dir(), "Missing artifacts/ directory"
    
    # Load and verify rollup.json
    with (rollup_dir / "rollup.json").open("r") as f:
        rollup = json.load(f)
    
    assert rollup["schema_version"] == 1, "rollup.json schema_version should be 1"
    assert rollup["suite_name"] == "baseline_tiny", "suite_name mismatch"
    assert rollup["suite_seed"] == SEED, f"suite_seed should be {SEED}"
    assert rollup["suite_n_per"] == N_PER, f"suite_n_per should be {N_PER}"
    assert "configs" in rollup, "rollup.json missing 'configs' field"
    assert len(rollup["configs"]) == 3, (
        f"Expected 3 configs in rollup.json, found {len(rollup['configs'])}"
    )
    
    # Verify each config entry in rollup
    for config in rollup["configs"]:
        assert "config_path" in config, "config missing 'config_path'"
        assert "run_id" in config, "config missing 'run_id'"
        assert "run_dir" in config, "config missing 'run_dir'"
        assert "status" in config, "config missing 'status'"
        assert config["status"] in ["ok", "failed"], f"Invalid status: {config['status']}"
    
    # Load and verify meta.json (schema v2)
    with (rollup_dir / "meta.json").open("r") as f:
        meta = json.load(f)
    
    assert meta["schema_version"] == 2, "meta.json schema_version should be 2"
    assert "run_id" in meta, "meta.json missing 'run_id'"
    assert meta["run_id"].startswith("suite_"), "rollup run_id should start with 'suite_'"
    assert "created_at_utc" in meta, "meta.json missing 'created_at_utc'"
    assert meta["created_at_utc"].endswith("Z"), "created_at_utc should be UTC (end with Z)"
    assert "git_sha" in meta, "meta.json missing 'git_sha'"
    assert meta["config_path"] == SUITE_PATH, "config_path should point to suite file"
    assert "config_sha256" in meta, "meta.json missing 'config_sha256'"
    assert meta["experiment_name"] == "baseline_tiny", "experiment_name should match suite_name"
    
    # Verify suite-specific fields in meta.json
    assert "suite" in meta, "meta.json missing 'suite' object"
    suite_meta = meta["suite"]
    assert suite_meta["is_suite_run"] is True, "is_suite_run should be True"
    assert suite_meta["suite_name"] == "baseline_tiny", "suite_name mismatch in meta"
    assert suite_meta["seed"] == SEED, f"seed should be {SEED} in suite metadata"
    assert suite_meta["n_per"] == N_PER, f"n_per should be {N_PER} in suite metadata"
    assert "member_run_ids" in suite_meta, "suite metadata missing 'member_run_ids'"
    assert len(suite_meta["member_run_ids"]) == 3, (
        f"Expected 3 member_run_ids, found {len(suite_meta['member_run_ids'])}"
    )
    
    # Load and verify suite_effective.yaml
    with (rollup_dir / "suite_effective.yaml").open("r") as f:
        suite_effective = yaml.safe_load(f)
    
    assert suite_effective["suite_name"] == "baseline_tiny", "suite_name mismatch"
    assert "parameters" in suite_effective, "suite_effective missing 'parameters'"
    params = suite_effective["parameters"]
    assert params["seed"] == SEED, f"Effective seed should be {SEED}"
    assert params["n_per"] == N_PER, f"Effective n_per should be {N_PER}"
    
    # Verify ROLLUP.md exists and is non-empty
    rollup_md = (rollup_dir / "reports" / "ROLLUP.md").read_text()
    assert len(rollup_md) > 0, "ROLLUP.md should not be empty"
    assert "baseline_tiny" in rollup_md, "ROLLUP.md should mention suite name"
    
    # Verify each member run directory has required files
    for run_dir in member_run_dirs:
        assert (run_dir / "meta.json").exists(), (
            f"Missing meta.json in {run_dir.name}"
        )
        assert (run_dir / "config_effective.yaml").exists(), (
            f"Missing config_effective.yaml in {run_dir.name}"
        )
        assert (run_dir / "results").is_dir(), (
            f"Missing results/ directory in {run_dir.name}"
        )
        
        # Verify meta.json is valid JSON (basic smoke test)
        with (run_dir / "meta.json").open("r") as f:
            run_meta = json.load(f)
        
        assert "run_id" in run_meta, f"run_id missing in {run_dir.name}/meta.json"
        assert "schema_version" in run_meta, (
            f"schema_version missing in {run_dir.name}/meta.json"
        )
