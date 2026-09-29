"""
Smoke test for auction/bidding mode runner support.

Tests that the experiment runner can handle contract_type: null configurations
and produces expected output structure with bidding-related metrics.
"""

import json
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


def test_auction_mode_runner_smoke():
    """Smoke test that auction mode runs successfully and produces expected outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/auction_smoke.yaml", ["--run-dir", tmpdir]
        )

        assert (
            result.returncode == 0
        ), f"Auction mode run should succeed. Error: {result.stderr}"

        # Find the run directory (should be exactly one)
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, f"Expected 1 run directory, found {len(run_dirs)}"
        run_dir = run_dirs[0]

        # Verify standard output structure exists
        results_dir = run_dir / "results"
        assert results_dir.exists(), "results/ directory should exist"

        # Should have results for exactly one strategy (greedy from config)
        strategy_dirs = list(results_dir.glob("*"))
        assert (
            len(strategy_dirs) == 1
        ), f"Expected 1 strategy dir, found {len(strategy_dirs)}"
        strategy_dir = strategy_dirs[0]
        assert (
            strategy_dir.name == "greedy"
        ), f"Expected 'greedy' strategy dir, found {strategy_dir.name}"

        # Should have exactly one results JSON file (auction scenario)
        result_files = list(strategy_dir.glob("*.json"))
        assert (
            len(result_files) == 1
        ), f"Expected 1 result file, found {len(result_files)}"
        result_file = result_files[0]

        # Load and verify result structure indicates auction mode ran
        with open(result_file) as f:
            results = json.load(f)

        # Core simulation completed (at least some hands were simulated)
        assert "hands" in results, "Results should have 'hands' field"
        assert isinstance(results["hands"], int), "hands should be an integer"
        assert results["hands"] > 0, "Should have simulated at least 1 hand"

        # Auction mode was executed (contract_type: null)
        assert "contract_type" in results, "Results should have 'contract_type' field"
        assert (
            results["contract_type"] is None
        ), "Contract type should be None for auction mode"

        # Auction mode always produces bidding_points structure
        assert (
            "bidding_points" in results
        ), "bidding_points should exist for auction mode"
        bidding_points = results["bidding_points"]
        assert isinstance(bidding_points, dict), "bidding_points should be a dictionary"

        # Verify bidding_points has required structure (always present in auction mode)
        required_bidding_fields = ["enabled", "hands_with_bids"]
        for field in required_bidding_fields:
            assert (
                field in bidding_points
            ), f"bidding_points should have '{field}' field"
            assert isinstance(
                bidding_points[field], (bool, int)
            ), f"{field} should be boolean or int"

        # hands_with_bids should be a non-negative integer (can be 0 if no bidding occurred)
        assert (
            bidding_points["hands_with_bids"] >= 0
        ), "hands_with_bids should be non-negative"


def test_all_pass_runner_emits_empty_played_sample_without_crashing(tmp_path):
    """Canonical runner handles an all-redeal result with numeric display fields."""
    config_path = tmp_path / "all_pass.yaml"
    config_path.write_text(
        """
experiment_name: all_pass_runner_test
strategies:
  - name: random_legal
    class_name: RandomLegalStrategy
scenarios:
  - contract_type: null
parameters:
  n_per: 3
  seed: 42
  log_level: hand
""".lstrip()
    )
    output_dir = tmp_path / "runs"

    completed = run_experiment(str(config_path), run_dir=str(output_dir))
    assert completed.returncode == 0, completed.stderr
    assert "WinRate: N/A" in completed.stdout
    assert "Reports generated automatically" in completed.stdout
    assert "Report generation encountered issues" not in completed.stdout

    run_dirs = list(output_dir.glob("*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "reports" / "ANALYSIS_SUMMARY.md").exists()
    assert (run_dir / "artifacts" / "canonical_summary.json").exists()

    result_files = list(run_dir.glob("results/random_legal/*.json"))
    assert len(result_files) == 1
    results = json.loads(result_files[0].read_text())
    assert results["hands"] == 3
    assert results["played_hands"] == 0
    assert results["redeals"] == 3
    assert results["avg_team0"] == 0.0
    assert results["avg_team1"] == 0.0
    assert results["win_rate_team0"] is None
    assert results["win_rate_team1"] is None
    assert sum(results["distribution_team0"].values()) == 0
