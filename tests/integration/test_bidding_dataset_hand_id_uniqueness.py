"""Test that hand_id values are globally unique across multi-policy auction runs."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration


class TestBiddingDatasetHandIdUniqueness:
    """Verify hand_id uniqueness when running multiple bidding policies."""

    def test_multi_policy_hand_id_uniqueness(self):
        """Run bid_eval_tiny with multiple policies and verify hand_id uniqueness."""
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"

        with tempfile.TemporaryDirectory() as temp_base:
            n_per = 5  # Small for fast test
            cmd = [
                sys.executable,
                "-m",
                "experiments.run_experiment",
                "--config",
                "experiments/configs/bid_eval_tiny.yaml",
                "--run-dir",
                temp_base,
                "--seed",
                "42",
                "--n_per",
                str(n_per),
                "--emit-bidding-dataset",
            ]
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=os.getcwd(),
                env=env,
            )
            assert result.returncode == 0, f"Runner failed: {result.stderr}"

            # Find run directory
            run_dirs = sorted(Path(temp_base).glob("bid_eval_tiny_*"))
            assert run_dirs, f"No run directories found in {temp_base}"
            run_dir = run_dirs[-1]

            # Load effective config to get policy count
            config_path = run_dir / "config_effective.yaml"
            with open(config_path) as f:
                config = yaml.safe_load(f)

            num_policies = len(config["bidding_policies"])
            num_scenarios = len(config["scenarios"])
            expected_hands = num_policies * num_scenarios * n_per

            # This test only makes sense with multiple policies
            assert (
                num_policies > 1
            ), f"Need >1 policies for collision test, got {num_policies}"

            # Load parquet and check uniqueness
            try:
                import pyarrow.parquet as pq

                parquet_path = run_dir / "datasets" / "bidding.parquet"
                table = pq.read_table(parquet_path)
                df_hand_ids = table.column("hand_id").to_pylist()
            except ImportError:
                # Fallback to JSONL
                jsonl_path = run_dir / "datasets" / "bidding.jsonl"
                df_hand_ids = []
                with open(jsonl_path) as f:
                    for line in f:
                        row = json.loads(line)
                        df_hand_ids.append(row["hand_id"])

            unique_hand_ids = sorted(set(df_hand_ids))

            # Verify uniqueness and contiguous range: should be exactly [0, 1, 2, ..., expected_hands-1]
            expected_range = list(range(expected_hands))
            assert unique_hand_ids == expected_range, (
                f"hand_id mismatch!\n"
                f"Expected: {expected_range[:10]}...{expected_range[-3:]} ({len(expected_range)} values)\n"
                f"Got: {unique_hand_ids[:10]}...{unique_hand_ids[-3:]} ({len(unique_hand_ids)} unique values)\n"
                f"Missing: {set(expected_range) - set(unique_hand_ids)}\n"
                f"Extra: {set(unique_hand_ids) - set(expected_range)}"
            )
