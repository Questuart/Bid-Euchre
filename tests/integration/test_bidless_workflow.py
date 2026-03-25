"""Integration tests for bidless dataset workflow.

Tests the end-to-end flow from run_experiment.py --emit-bidless-dataset
to loading the dataset with diagnostics.load_bidless_dataset().
"""

import os
import shutil
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.integration


class TestBidlessDatasetWorkflow:
    """Test bidless dataset emission via run_experiment.py."""

    @pytest.fixture
    def temp_run_dir(self):
        """Create a temporary directory for test outputs."""
        tmpdir = tempfile.mkdtemp(prefix="bidless_test_")
        yield tmpdir
        # Cleanup after test
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_emit_bidless_dataset_creates_expected_files(self, temp_run_dir):
        """--emit-bidless-dataset creates parquet, jsonl, and meta files."""
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
            ],
            env={**os.environ, "PYTHONPATH": "src"},
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )

        assert result.returncode == 0, f"run_experiment.py failed:\n{result.stderr}"

        # Find the run directory (includes timestamp)
        run_dirs = [
            d for d in os.listdir(temp_run_dir) if d.startswith("quick_test_42_")
        ]
        assert len(run_dirs) == 1, f"Expected one run dir, found: {run_dirs}"
        run_dir = os.path.join(temp_run_dir, run_dirs[0])

        # Check dataset directory exists
        datasets_dir = os.path.join(run_dir, "datasets")
        assert os.path.isdir(
            datasets_dir
        ), f"datasets/ directory not found in {run_dir}"

        # Check expected files exist
        expected_files = ["bidless.parquet", "bidless.jsonl", "bidless_meta.json"]
        for fname in expected_files:
            fpath = os.path.join(datasets_dir, fname)
            assert os.path.isfile(fpath), f"{fname} not found in datasets/"

    def test_emit_bidless_dataset_loadable_by_diagnostics(self, temp_run_dir):
        """Emitted dataset can be loaded by diagnostics.load_bidless_dataset()."""
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
                "--emit-bidless-dataset",
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
        run_dir = os.path.join(temp_run_dir, run_dirs[0])
        datasets_dir = os.path.join(run_dir, "datasets")

        # Load using diagnostics module
        from bid_euchre.diagnostics import load_bidless_dataset, load_meta

        meta = load_meta(datasets_dir)
        assert "run_id" in meta
        assert "bidless_dataset_schema_version" in meta

        df = load_bidless_dataset(datasets_dir)
        # 10 hands × 2 scenarios × 2 strategies × 4 seats = 160 rows
        # But we only emit one collector per scenario, so:
        # quick_test.yaml has 2 scenarios (suit-H, high), 2 strategies
        # Each strategy runs 10 hands per scenario = 20 hands per strategy
        # 20 hands × 4 seats × 2 strategies = 160 rows
        assert len(df) > 0, "DataFrame is empty"
        assert "seat" in df.columns
        assert "contract_type" in df.columns
        assert "hand_cards" in df.columns

    def test_emit_bidless_dataset_only_declared_contracts(self, temp_run_dir):
        """Bidless dataset only includes declared contracts, not auction mode."""
        # Use quick_test.yaml which has declared contracts (not auction)
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

        from bid_euchre.diagnostics import load_bidless_dataset

        df = load_bidless_dataset(datasets_dir)

        # All rows should have a contract_type (not None)
        assert df["contract_type"].notna().all(), "Found rows with None contract_type"

        # Should only have contract types from quick_test.yaml scenarios
        contract_types = set(df["contract_type"].unique())
        assert "suit" in contract_types or "high" in contract_types

    def test_emit_bidless_dataset_jsonl_format(self, temp_run_dir):
        """--bidless-dataset-format=jsonl works correctly."""
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
                "--bidless-dataset-format",
                "jsonl",
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

        # Check JSONL file exists and is not empty
        jsonl_path = os.path.join(datasets_dir, "bidless.jsonl")
        assert os.path.isfile(jsonl_path)
        assert os.path.getsize(jsonl_path) > 0

        # Load using diagnostics (should auto-detect format)
        from bid_euchre.diagnostics import load_bidless_dataset

        df = load_bidless_dataset(datasets_dir, format="jsonl")
        assert len(df) > 0

    def test_no_emit_flag_produces_no_dataset(self, temp_run_dir):
        """Without --emit-bidless-dataset, no dataset files are created."""
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
                # Note: no --emit-bidless-dataset flag
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

        # Dataset directory might exist but should not have bidless files
        if os.path.isdir(datasets_dir):
            files = os.listdir(datasets_dir)
            bidless_files = [f for f in files if f.startswith("bidless")]
            assert (
                len(bidless_files) == 0
            ), f"Found bidless files without flag: {bidless_files}"

    def test_hand_id_uniqueness_across_strategies_and_scenarios(self, temp_run_dir):
        """hand_id is globally unique across all strategies and scenarios.

        This tests the fix for the hand_id collision bug where deal_id was used
        as hand_id, causing collisions when multiple strategies or scenarios
        share the same deal_id values (0..n_per-1).

        The fix computes: hand_id = ((plan_id * num_scenarios + scenario_id) * n_per) + deal_id
        """
        # Use strategy_comparison.yaml which has 5 strategies
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
                "--emit-bidless-dataset",
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

        from bid_euchre.diagnostics import load_bidless_dataset

        df = load_bidless_dataset(datasets_dir)

        # Verify (hand_id, seat) uniqueness
        # strategy_comparison.yaml: 5 strategies × 6 scenarios × 10 hands × 4 seats = 1200 rows
        # Each unique hand_id should appear exactly 4 times (once per seat)
        hand_id_counts = df.groupby("hand_id").size()
        assert (
            hand_id_counts == 4
        ).all(), "Some hand_ids don't have exactly 4 rows (one per seat)"

        # Verify total unique hand_ids matches expected
        num_strategies = (
            5  # greedy, glutton, random_legal, always_lowest, always_highest
        )
        num_scenarios = 6  # suit-C, suit-D, suit-H, suit-S, high, low
        n_per = 10
        expected_unique_hands = num_strategies * num_scenarios * n_per
        assert df["hand_id"].nunique() == expected_unique_hands, (
            f"Expected {expected_unique_hands} unique hand_ids, "
            f"got {df['hand_id'].nunique()}"
        )

        # Verify (hand_id, seat) is truly unique (no duplicates)
        duplicates = df.groupby(["hand_id", "seat"]).size()
        assert (duplicates == 1).all(), "Found duplicate (hand_id, seat) pairs"
