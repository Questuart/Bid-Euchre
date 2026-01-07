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


def test_auction_mode_runner_smoke():
    """Smoke test that auction mode runs successfully and produces expected outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = run_experiment(
            "experiments/configs/auction_smoke.yaml",
            ["--run-dir", tmpdir]
        )

        assert result.returncode == 0, f"Auction mode run should succeed. Error: {result.stderr}"

        # Find the run directory
        run_dirs = list(Path(tmpdir).glob("*"))
        assert len(run_dirs) == 1, f"Expected 1 run directory, found {len(run_dirs)}"

        run_dir = run_dirs[0]

        # Verify results directory and files exist
        results_dir = run_dir / "results"
        assert results_dir.exists(), "results/ directory should exist"

        # Should have results for the greedy strategy
        strategy_dirs = list(results_dir.glob("*"))
        assert len(strategy_dirs) == 1, f"Expected 1 strategy dir, found {len(strategy_dirs)}"
        assert strategy_dirs[0].name == "greedy", f"Expected 'greedy' strategy dir, found {strategy_dirs[0].name}"

        # Should have auction.json result file
        result_files = list(strategy_dirs[0].glob("*.json"))
        assert len(result_files) == 1, f"Expected 1 result file, found {len(result_files)}"
        assert result_files[0].name == "auction.json", f"Expected 'auction.json', found {result_files[0].name}"

        # Load and verify result structure
        with open(result_files[0]) as f:
            results = json.load(f)

        # Basic structure checks
        assert "hands" in results, "Results should have 'hands' field"
        assert results["hands"] == 20, "Should have run 20 hands"
        assert "contract_type" in results, "Results should have 'contract_type' field"
        assert results["contract_type"] is None, "Contract type should be None for auction mode"

        # Bidding-specific fields should exist (when bidding occurred)
        # Note: these fields are only present when bidding actually happened
        if "bidding_points" in results:
            bidding_points = results["bidding_points"]
            assert "enabled" in bidding_points, "bidding_points should have 'enabled' field"
            assert bidding_points["enabled"] is True, "Bidding should be enabled for auction mode"
            assert "hands_with_bids" in bidding_points, "bidding_points should have 'hands_with_bids' field"
            assert isinstance(bidding_points["hands_with_bids"], int), "hands_with_bids should be an integer"
            assert bidding_points["hands_with_bids"] >= 0, "hands_with_bids should be non-negative"
