"""Integration tests for bidless outcomes dataset workflow.

Tests the end-to-end flow from run_experiment.py --emit-bidless-outcomes-dataset
to loading the dataset and verifying its structure.
"""

import json
import os
import shutil
import subprocess
import tempfile

import pandas as pd
import pytest

pytestmark = pytest.mark.integration


class TestBidlessOutcomesDatasetWorkflow:
    """Test bidless outcomes dataset emission via run_experiment.py."""

    @pytest.fixture
    def temp_run_dir(self):
        """Create a temporary directory for test outputs."""
        tmpdir = tempfile.mkdtemp(prefix="bidless_outcomes_test_")
        yield tmpdir
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_emit_bidless_outcomes_dataset_creates_expected_files(self, temp_run_dir):
        """--emit-bidless-outcomes-dataset creates parquet, jsonl, and meta files."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "5",
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0, f"run_experiment.py failed:\n{result.stderr}"

        # Find the run directory
        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        assert len(run_dirs) == 1
        run_dir = os.path.join(temp_run_dir, run_dirs[0])

        # Check dataset directory and files
        datasets_dir = os.path.join(run_dir, "datasets")
        assert os.path.isdir(datasets_dir)

        expected_files = [
            "bidless_outcomes.parquet",
            "bidless_outcomes.jsonl",
            "bidless_outcomes_meta.json",
        ]
        for fname in expected_files:
            fpath = os.path.join(datasets_dir, fname)
            assert os.path.isfile(fpath), f"{fname} not found in datasets/"

    def test_outcomes_dataset_has_correct_schema(self, temp_run_dir):
        """Outcomes dataset has per-hand granularity with correct columns."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "10",
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0, f"run_experiment.py failed:\n{result.stderr}"

        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        df = pd.read_parquet(os.path.join(datasets_dir, "bidless_outcomes.parquet"))

        # Check all expected columns are present
        expected_columns = {
            "hand_id",
            "deal_id",
            "dealer_seat",
            "contract_type",
            "trump_suit",
            "strategy_id",
            "matchup_id",
            "team0_strategy",
            "team1_strategy",
            "tricks_team0",
            "tricks_team1",
            "team0_win",
        }
        assert (
            set(df.columns) == expected_columns
        ), f"Unexpected columns: {set(df.columns)}"

        # Check row count: per-hand granularity
        # quick_test.yaml: 2 strategies × 2 scenarios × 10 hands = 40 rows
        assert len(df) == 40, f"Expected 40 rows, got {len(df)}"

        # Check hand_id uniqueness
        assert df["hand_id"].nunique() == 40, "hand_id should be unique per hand"

    def test_outcomes_dataset_strategy_context_self_play(self, temp_run_dir):
        """In self_play mode, strategy_id and matchup_id are set correctly."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "5",
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0

        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        df = pd.read_parquet(os.path.join(datasets_dir, "bidless_outcomes.parquet"))

        # All rows should have strategy_id set
        assert df["strategy_id"].notna().all()

        # In self_play, team0_strategy == team1_strategy
        assert (df["team0_strategy"] == df["team1_strategy"]).all()

        # matchup_id should be "strategy_vs_strategy"
        for _, row in df.iterrows():
            expected_matchup = f"{row['strategy_id']}_vs_{row['strategy_id']}"
            assert row["matchup_id"] == expected_matchup

    def test_outcomes_dataset_team0_win_values(self, temp_run_dir):
        """team0_win is correctly computed: 1.0=win, 0.5=tie, 0.0=loss."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "50",  # More samples to get all three outcomes
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0

        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        df = pd.read_parquet(os.path.join(datasets_dir, "bidless_outcomes.parquet"))

        # Check team0_win values are valid
        assert df["team0_win"].isin([0.0, 0.5, 1.0]).all()

        # Verify team0_win is consistent with tricks_team0
        for _, row in df.iterrows():
            if row["tricks_team0"] > 5:
                assert row["team0_win"] == 1.0, "Win (>5 tricks) should be 1.0"
            elif row["tricks_team0"] == 5:
                assert row["team0_win"] == 0.5, "Tie (5 tricks) should be 0.5"
            else:
                assert row["team0_win"] == 0.0, "Loss (<5 tricks) should be 0.0"

        # Verify tricks sum to 10
        assert ((df["tricks_team0"] + df["tricks_team1"]) == 10).all()

    def test_outcomes_dataset_hand_id_uniqueness_across_strategies_scenarios(
        self, temp_run_dir
    ):
        """hand_id is globally unique across all strategies and scenarios."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/strategy_comparison.yaml",
                "--seed",
                "42",
                "--n_per",
                "10",
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0, f"run_experiment.py failed:\n{result.stderr}"

        run_dirs = [
            d
            for d in os.listdir(temp_run_dir)
            if d.startswith("strategy_comparison_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        df = pd.read_parquet(os.path.join(datasets_dir, "bidless_outcomes.parquet"))

        # strategy_comparison.yaml: 5 strategies × 6 scenarios × 10 hands = 300 rows
        num_strategies = 5
        num_scenarios = 6
        n_per = 10
        expected_rows = num_strategies * num_scenarios * n_per

        assert len(df) == expected_rows, f"Expected {expected_rows} rows, got {len(df)}"
        assert df["hand_id"].nunique() == expected_rows, "Each hand_id should be unique"

    def test_outcomes_meta_json_is_valid(self, temp_run_dir):
        """bidless_outcomes_meta.json contains correct metadata."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "10",
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0

        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        with open(os.path.join(datasets_dir, "bidless_outcomes_meta.json")) as f:
            meta = json.load(f)

        assert "run_id" in meta
        assert meta["bidless_outcomes_schema_version"] == 1
        assert meta["row_count"] == 40  # 2 strategies × 2 scenarios × 10 hands
        assert meta["parquet_path"] == "bidless_outcomes.parquet"
        assert meta["jsonl_path"] == "bidless_outcomes.jsonl"

    def test_no_outcomes_flag_produces_no_outcomes_dataset(self, temp_run_dir):
        """Without --emit-bidless-outcomes-dataset, no outcomes files are created."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "5",
                "--run-dir",
                temp_run_dir,
                # Note: no --emit-bidless-outcomes-dataset flag
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0

        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        # Dataset directory might exist but should not have outcomes files
        if os.path.isdir(datasets_dir):
            files = os.listdir(datasets_dir)
            outcomes_files = [f for f in files if f.startswith("bidless_outcomes")]
            assert (
                len(outcomes_files) == 0
            ), f"Found outcomes files without flag: {outcomes_files}"

    def test_both_bidless_flags_emit_both_datasets(self, temp_run_dir):
        """--emit-bidless-dataset and --emit-bidless-outcomes-dataset can be used together."""
        result = subprocess.run(
            [
                "python",
                "experiments/run_experiment.py",
                "--config",
                "experiments/configs/quick_test.yaml",
                "--seed",
                "42",
                "--n_per",
                "5",
                "--run-dir",
                temp_run_dir,
                "--emit-bidless-dataset",
                "--emit-bidless-outcomes-dataset",
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0, f"run_experiment.py failed:\n{result.stderr}"

        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        # Should have both feature dataset files and outcomes dataset files
        assert os.path.isfile(os.path.join(datasets_dir, "bidless.parquet"))
        assert os.path.isfile(os.path.join(datasets_dir, "bidless_outcomes.parquet"))

        # Feature dataset is per-seat (4× more rows than outcomes)
        df_features = pd.read_parquet(os.path.join(datasets_dir, "bidless.parquet"))
        df_outcomes = pd.read_parquet(
            os.path.join(datasets_dir, "bidless_outcomes.parquet")
        )

        # quick_test: 2 strategies × 2 scenarios × 5 hands = 20 hands
        # Features: 20 hands × 4 seats = 80 rows
        # Outcomes: 20 hands = 20 rows
        assert (
            len(df_features) == 80
        ), f"Features should have 80 rows, got {len(df_features)}"
        assert (
            len(df_outcomes) == 20
        ), f"Outcomes should have 20 rows, got {len(df_outcomes)}"
