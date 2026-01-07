"""
Integration test: baseline_tiny invariants (CI regression guard)

This test runs the baseline_tiny suite deterministically and compares
the stable metrics (trick distributions) against a committed fixture.

Catches regressions in:
- RNG/deal seeding
- Strategy behavior (changes in trick distributions)
- Output structure (missing result files)

Fixture: data/fixtures/baseline_tiny/expected_metrics_seed42_nper3.json
Parameters: seed=42, n_per=3, --no-reports
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

SUITE_PATH = "experiments/suites/baseline_tiny.yaml"
SEED = 42
N_PER = 3
FIXTURE_PATH = "data/fixtures/baseline_tiny/expected_metrics_seed42_nper3.json"


def test_baseline_tiny_invariants(tmp_path: Path) -> None:
    """
    Run baseline_tiny suite and verify stable metrics match fixture exactly.
    
    This is a CI regression guard that ensures:
    - Deterministic deal seeding works correctly
    - Strategy behavior remains unchanged
    - Output structure is stable
    """
    # Load expected metrics from fixture
    fixture_path = Path(FIXTURE_PATH)
    assert fixture_path.exists(), f"Fixture not found: {FIXTURE_PATH}"
    
    with fixture_path.open("r") as f:
        fixture = json.load(f)
    
    # Validate fixture parameters match test parameters
    assert fixture["suite_name"] == "baseline_tiny", "Fixture suite_name mismatch"
    assert fixture["seed"] == SEED, f"Fixture seed mismatch: expected {SEED}, got {fixture['seed']}"
    assert fixture["n_per"] == N_PER, f"Fixture n_per mismatch: expected {N_PER}, got {fixture['n_per']}"
    
    # Run baseline_tiny suite
    run_base = tmp_path / "runs"
    run_base.mkdir(parents=True, exist_ok=True)
    
    # Snapshot dirs before running
    dirs_before = set(run_base.iterdir()) if run_base.exists() else set()
    
    cmd = [
        "python",
        "scripts/run_suite.py",
        "--suite",
        SUITE_PATH,
        "--seed",
        str(SEED),
        "--n-per",
        str(N_PER),
        "--no-reports",
        "--run-dir",
        str(run_base),
    ]
    
    env = {**os.environ, "PYTHONPATH": "src"}
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    except subprocess.CalledProcessError as e:
        pytest.fail(
            f"Suite runner failed:\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Stdout:\n{e.stdout}\n"
            f"Stderr:\n{e.stderr}"
        )
    
    # Discover new directories (4 expected: 3 member runs + 1 rollup)
    dirs_after = set(run_base.iterdir())
    new_dirs = dirs_after - dirs_before
    
    assert len(new_dirs) == 4, (
        f"Expected 4 new directories (3 member runs + 1 rollup), found {len(new_dirs)}: "
        f"{[d.name for d in new_dirs]}"
    )
    
    # Identify rollup directory
    rollup_candidates = [d for d in new_dirs if (d / "rollup.json").exists()]
    assert len(rollup_candidates) == 1, (
        f"Expected exactly 1 rollup directory, found {len(rollup_candidates)}"
    )
    rollup_dir = rollup_candidates[0]
    
    # Verify rollup contract (existence-only checks)
    assert (rollup_dir / "meta.json").exists(), "Missing meta.json in rollup"
    assert (rollup_dir / "suite_effective.yaml").exists(), "Missing suite_effective.yaml"
    assert (rollup_dir / "rollup.json").exists(), "Missing rollup.json"
    assert (rollup_dir / "reports" / "ROLLUP.md").exists(), "Missing ROLLUP.md"
    
    # Load rollup to find member run directories
    with (rollup_dir / "rollup.json").open("r") as f:
        rollup = json.load(f)
    
    assert rollup["suite_name"] == "baseline_tiny", "Rollup suite_name mismatch"
    assert len(rollup["configs"]) == 3, f"Expected 3 configs, found {len(rollup['configs'])}"
    
    # Build actual metrics from member runs
    actual_metrics = {
        "suite_name": "baseline_tiny",
        "seed": SEED,
        "n_per": N_PER,
        "configs": []
    }
    
    for config_entry in rollup["configs"]:
        config_path = config_entry["config_path"]
        run_dir_name = config_entry["run_dir"]
        
        # Resolve member run directory (sibling to rollup)
        member_run_dir = rollup_dir.parent / run_dir_name
        
        assert member_run_dir.exists(), f"Member run dir not found: {member_run_dir}"
        
        # Verify member run contract (existence-only)
        assert (member_run_dir / "meta.json").exists(), (
            f"Missing meta.json in {member_run_dir.name}"
        )
        assert (member_run_dir / "config_effective.yaml").exists(), (
            f"Missing config_effective.yaml in {member_run_dir.name}"
        )
        assert (member_run_dir / "results").is_dir(), (
            f"Missing results/ directory in {member_run_dir.name}"
        )
        
        # Load all result files and extract stable metrics
        config_results = {}
        results_dir = member_run_dir / "results"
        
        for result_file in sorted(results_dir.rglob("*.json")):
            rel_path = str(result_file.relative_to(results_dir))
            
            with result_file.open("r") as f:
                result_data = json.load(f)
            
            # Extract stable metrics only
            metrics = {
                "hands": result_data["hands"],
                "distribution_team0": result_data["distribution_team0"]
            }
            
            # Include distribution_team1 only if present
            if "distribution_team1" in result_data:
                metrics["distribution_team1"] = result_data["distribution_team1"]
            
            # Assert distribution values are integers
            for dist_key in ["distribution_team0", "distribution_team1"]:
                if dist_key in metrics:
                    for trick_count, count in metrics[dist_key].items():
                        assert isinstance(count, int), (
                            f"Non-integer distribution value in {rel_path}: "
                            f"{dist_key}[{trick_count}] = {count} (type: {type(count).__name__})"
                        )
            
            config_results[rel_path] = metrics
        
        actual_metrics["configs"].append({
            "config_path": config_path,
            "results": config_results
        })
    
    # Sort both fixture and actual configs by config_path for comparison
    fixture_configs = sorted(fixture["configs"], key=lambda c: c["config_path"])
    actual_configs = sorted(actual_metrics["configs"], key=lambda c: c["config_path"])
    
    # Compare config count
    assert len(actual_configs) == len(fixture_configs), (
        f"Config count mismatch: expected {len(fixture_configs)}, got {len(actual_configs)}"
    )
    
    # Compare each config
    for fixture_config, actual_config in zip(fixture_configs, actual_configs):
        config_path = fixture_config["config_path"]
        
        assert actual_config["config_path"] == config_path, (
            f"Config path mismatch: expected {config_path}, got {actual_config['config_path']}"
        )
        
        fixture_results = fixture_config["results"]
        actual_results = actual_config["results"]
        
        # Compare result file keys
        assert actual_results.keys() == fixture_results.keys(), (
            f"Result file set differs for {config_path}:\n"
            f"  Expected: {sorted(fixture_results.keys())}\n"
            f"  Actual:   {sorted(actual_results.keys())}\n"
            f"  Missing:  {sorted(set(fixture_results.keys()) - set(actual_results.keys()))}\n"
            f"  Extra:    {sorted(set(actual_results.keys()) - set(fixture_results.keys()))}"
        )
        
        # Compare metrics for each result file
        for result_path in sorted(fixture_results.keys()):
            fixture_metrics = fixture_results[result_path]
            actual_metrics_for_file = actual_results[result_path]
            
            # Compare hands
            assert actual_metrics_for_file["hands"] == fixture_metrics["hands"], (
                f"Hands mismatch for {config_path} / {result_path}:\n"
                f"  Expected: {fixture_metrics['hands']}\n"
                f"  Actual:   {actual_metrics_for_file['hands']}"
            )
            
            # Compare distribution_team0
            assert actual_metrics_for_file["distribution_team0"] == fixture_metrics["distribution_team0"], (
                f"distribution_team0 mismatch for {config_path} / {result_path}:\n"
                f"  Expected: {fixture_metrics['distribution_team0']}\n"
                f"  Actual:   {actual_metrics_for_file['distribution_team0']}"
            )
            
            # Compare distribution_team1 if present in fixture
            if "distribution_team1" in fixture_metrics:
                assert "distribution_team1" in actual_metrics_for_file, (
                    f"distribution_team1 missing in actual results for {config_path} / {result_path}"
                )
                assert actual_metrics_for_file["distribution_team1"] == fixture_metrics["distribution_team1"], (
                    f"distribution_team1 mismatch for {config_path} / {result_path}:\n"
                    f"  Expected: {fixture_metrics['distribution_team1']}\n"
                    f"  Actual:   {actual_metrics_for_file['distribution_team1']}"
                )
