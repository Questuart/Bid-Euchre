"""
Integration test: bidless_dataset_tiny smoke test

Minimal smoke test to verify the collect_bidless_dataset script works
and produces deterministic output.
"""

import json
import os
import subprocess
import tempfile

SUITE_PATH = "experiments/suites/bidless_dataset_tiny.yaml"
SEED = 42


def test_collect_bidless_dataset_smoke():
    """Smoke test that the script runs and produces valid JSONL output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "dataset.jsonl")

        # Run the collection script
        cmd = [
            "python", "scripts/collect_bidless_dataset.py",
            "--suite", SUITE_PATH,
            "--seed", str(SEED),
            "--out", output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Verify output file exists
        assert os.path.exists(output_path), "Output file not created"

        # Verify it's valid JSONL (one JSON object per line)
        with open(output_path, 'r') as f:
            lines = f.readlines()
            assert len(lines) > 0, "Output file is empty"

            for line in lines:
                # Each line should be valid JSON
                data = json.loads(line.strip())
                # Required fields from BidlessDatasetCollector schema
                assert "hand_id" in data
                assert "hand_cards" in data  # List of card strings
                assert "hand_features" in data  # Feature dict
                assert "run_id" in data
                assert "seat" in data  # Player seat (0-3)
                assert "dealer_seat" in data  # Dealer position
                assert "contract_type" in data  # suit/high/low
                assert "hand_feature_schema_version" in data


def test_collect_bidless_dataset_deterministic():
    """Test that same seed produces identical output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output1 = os.path.join(tmpdir, "dataset1.jsonl")
        output2 = os.path.join(tmpdir, "dataset2.jsonl")

        # Run twice with same seed
        cmd = [
            "python", "scripts/collect_bidless_dataset.py",
            "--suite", SUITE_PATH,
            "--seed", str(SEED),
            "--out", output1
        ]
        subprocess.run(cmd, check=True)

        cmd[7] = output2  # Change output path
        subprocess.run(cmd, check=True)

        # Files should be byte-identical
        with open(output1, 'rb') as f1, open(output2, 'rb') as f2:
            assert f1.read() == f2.read(), "Outputs not identical for same seed"
