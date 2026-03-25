"""
Integration test for the bid_eval_tiny suite.

Ensures the evaluator output (bidder risk metrics) is produced deterministically.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SUITE_PATH = "experiments/suites/bid_eval_tiny.yaml"
SEED = 42
N_PER = 5


def test_bid_eval_tiny_emits_evaluator(tmp_path: Path) -> None:
    run_base = tmp_path / "runs"
    run_base.mkdir(parents=True, exist_ok=True)
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
        "--run-dir",
        str(run_base),
    ]

    env = {**os.environ, "PYTHONPATH": "src"}

    subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)

    dirs_after = set(run_base.iterdir())
    new_dirs = dirs_after - dirs_before
    assert (
        len(new_dirs) == 2
    ), f"Expected 2 directories (1 run + 1 rollup), found {len(new_dirs)}"

    rollup_dir = next(d for d in new_dirs if (d / "rollup.json").exists())
    assert (rollup_dir / "rollup.json").exists()

    with (rollup_dir / "rollup.json").open() as f:
        rollup = json.load(f)

    assert rollup["suite_name"] == "bid_eval_tiny"
    assert rollup["configs"], "Expected at least one config"

    run_dir_names = {entry["run_dir"] for entry in rollup["configs"]}

    for run_dir_name in run_dir_names:
        member_run = rollup_dir.parent / run_dir_name
        eval_path = member_run / "reports" / "bidding_strategy" / "evaluation.json"
        assert eval_path.exists(), f"Missing evaluator output: {eval_path}"

        with eval_path.open() as ef:
            data = json.load(ef)

        assert data["primary_series"] == "net_bidder_team_points"
        assert isinstance(data["strategies"], list)
        for strategy in data["strategies"]:
            assert "strategy_id" in strategy
            assert isinstance(strategy["bidder_team_points"], list)
            assert isinstance(strategy["net_bidder_team_points"], list)
            # Original metrics (backward compat)
            assert "expected_points" in strategy
            assert "make_rate" in strategy
            assert "cvar_5" in strategy
            assert "downside_variance" in strategy
            # Net-differential metrics
            assert "net_expected_points" in strategy
            assert "net_expected_points_per_deal" in strategy
            assert "net_cvar_5" in strategy
            assert "net_downside_variance" in strategy

        # Check that baseline matrix report exists
        matrix_path = (
            member_run / "reports" / "bidding_strategy" / "baseline_matrix.json"
        )
        assert matrix_path.exists(), f"Missing baseline matrix report: {matrix_path}"

        with matrix_path.open() as mf:
            matrix_data = json.load(mf)

        assert "strategies" in matrix_data
        assert isinstance(matrix_data["strategies"], list)
        assert len(matrix_data["strategies"]) == len(data["strategies"])

        # Verify deterministic ordering (sorted by strategy_id)
        matrix_ids = [s["strategy_id"] for s in matrix_data["strategies"]]
        sorted_ids = sorted(matrix_ids)
        assert (
            matrix_ids == sorted_ids
        ), f"Matrix not deterministically ordered: {matrix_ids} != {sorted_ids}"

        # Verify required fields are present in each strategy
        for strategy in matrix_data["strategies"]:
            assert "strategy_id" in strategy
            assert "expected_points" in strategy
            assert "make_rate" in strategy
            assert "cvar_5" in strategy
            assert "downside_variance" in strategy
            assert "net_expected_points" in strategy
            assert "net_expected_points_per_deal" in strategy
            assert "net_cvar_5" in strategy
            assert "net_downside_variance" in strategy
            assert "n_hands" in strategy
