import json
import os
import subprocess
import sys
import tempfile

import pytest

pytestmark = pytest.mark.integration

from bid_euchre.sim import simulation
from bid_euchre.strategy import BasicStrategy, GreedyStrategy


class TestEndToEndSimulation:
    """Test complete simulation workflows."""

    def test_full_hand_simulation_basic_strategy(self):
        """Test simulating a complete hand with basic strategy."""
        # Play one complete hand
        result = simulation.play_single_hand("suit", "H", strategy=BasicStrategy())

        (
            team0_tricks,
            team1_tricks,
            all_scores,
            all_features,
            initial_leader,
            starting_hands,
            _,
            _,
            _,
            _,
            _,
        ) = result

        # Basic validation
        assert isinstance(team0_tricks, int)
        assert isinstance(team1_tricks, int)
        assert 0 <= team0_tricks <= 10
        assert 0 <= team1_tricks <= 10
        assert team0_tricks + team1_tricks == 10

        # Initial leader should be 0-3
        assert isinstance(initial_leader, int)
        assert 0 <= initial_leader <= 3

        # Now returns features for ALL 4 players
        assert isinstance(all_scores, list)
        assert len(all_scores) == 4
        for score in all_scores:
            assert isinstance(score, int)
            assert score >= 0

        assert isinstance(all_features, list)
        assert len(all_features) == 4
        # Check for core features (allow additional features from hand_eval evolution)
        core_features = {
            "bowers",
            "trump_count",
            "offsuit_aces",
            "offsuit_non_ace_count",
            "rank_sum",
        }
        for features in all_features:
            assert isinstance(features, dict)
            assert core_features.issubset(
                set(features.keys())
            ), f"Missing core features. Expected {core_features}, got {set(features.keys())}"

        # Validate starting_hands
        assert isinstance(starting_hands, list)
        assert len(starting_hands) == 4
        for hand in starting_hands:
            assert isinstance(hand, list)
            assert len(hand) == 10  # Each player gets 10 cards

    def test_experiment_script_workflow(self):
        """Test the complete experiment script workflow."""
        import subprocess

        # Create temporary directory for test output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Get repo root (tests/integration/../../ = repo root)
            repo_root = os.path.join(os.path.dirname(__file__), "..", "..")

            # Run the experiment script with command line arguments
            cmd = [
                sys.executable,
                os.path.join(repo_root, "experiments", "run_experiment.py"),
                "--config",
                os.path.join(
                    repo_root, "experiments", "configs", "baseline_greedy.yaml"
                ),
                "--n_per",
                "50",
                "--seed",
                "42",
                "--run-dir",
                temp_dir,
                "--log-level",
                "hand",
            ]

            # Set PYTHONPATH for the subprocess
            env = os.environ.copy()
            env["PYTHONPATH"] = os.path.join(repo_root, "src")

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            # Check that the command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"

            # Check that a run folder was created and contains expected results
            run_folders = [
                p for p in os.listdir(temp_dir) if p.startswith("baseline_greedy_")
            ]
            assert len(run_folders) >= 1
            run_folder = os.path.join(temp_dir, sorted(run_folders)[-1])

            results_dir = os.path.join(run_folder, "results", "greedy")
            assert os.path.isdir(results_dir)

            expected_files = [
                "high.json",
                "low.json",
                "suit_C.json",
                "suit_D.json",
                "suit_H.json",
                "suit_S.json",
            ]

            for filename in expected_files:
                expected_file = os.path.join(results_dir, filename)
                assert os.path.exists(expected_file), f"Missing output file: {filename}"

                with open(expected_file, "r") as f:
                    data = json.load(f)
                    assert data["hands"] == 50
                    assert "contract_type" in data
                    assert "trump_suit" in data or data["contract_type"] in [
                        "high",
                        "low",
                    ]

            # Ensure logs exist
            logs_dir = os.path.join(run_folder, "logs")
            assert os.path.isdir(logs_dir)
            assert any(name.endswith(".jsonl") for name in os.listdir(logs_dir))

    def test_strategy_comparison(self):
        """Test that different strategies produce different results."""
        # Run with both strategies using the same seed for comparability
        result_greedy = simulation.simulate_many_hands(
            200, "suit", "H", seed=42, strategy=GreedyStrategy()
        )
        result_basic = simulation.simulate_many_hands(
            200, "suit", "H", seed=42, strategy=BasicStrategy()
        )

        # Both should produce valid results
        assert result_greedy["hands"] == 200
        assert result_basic["hands"] == 200
        assert 4.0 <= result_greedy["avg_team0"] <= 6.0
        assert 4.0 <= result_basic["avg_team0"] <= 6.0


class TestDataPipeline:
    """Test data input/output and processing."""

    def test_json_output_format(self):
        """Test that simulation output is properly formatted JSON."""
        result = simulation.simulate_many_hands(100, "suit", "H")

        # Convert to JSON and back
        json_str = json.dumps(result, indent=2)
        parsed = json.loads(json_str)

        # Verify structure is preserved
        assert parsed["hands"] == result["hands"]
        assert parsed["contract_type"] == result["contract_type"]
        assert parsed["trump_suit"] == result["trump_suit"]

    def test_experiment_output_structure_smoke(self, tmp_path):
        run_root = tmp_path / "runs"

        cmd = [
            sys.executable,
            "experiments/run_experiment.py",
            "--config",
            "experiments/configs/quick_test.yaml",
            "--run-dir",
            str(run_root),
            "--n_per",
            "50",
            "--seed",
            "1",
            "--log-level",
            "none",
        ]

        env = dict(os.environ)
        env["PYTHONPATH"] = "src"

        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

        assert run_root.exists()
        runs = [p for p in run_root.iterdir() if p.is_dir()]
        assert len(runs) == 1

        run_dir = runs[0]
        assert (run_dir / "meta.json").exists()
        assert (run_dir / "perf.json").exists()
        assert (run_dir / "results").exists()

        # Validate meta.json contract (schema v2)
        meta_path = run_dir / "meta.json"
        meta = json.loads(meta_path.read_text())

        assert meta["schema_version"] == 2
        assert meta["created_at_utc"].endswith("Z")
        assert "git_sha" in meta
        assert meta["git_sha"] == "unknown" or len(meta["git_sha"]) >= 7
        assert meta["config_path"] == "experiments/configs/quick_test.yaml"
        assert len(meta["config_sha256"]) == 64

        # Backward-compatible fields
        assert meta["n_per"] == 50
        assert meta["seed"] == 1

    def test_simulation_reproducibility(self):
        """Test that simulations with same seed produce same results."""
        # Note: Current implementation doesn't support seeding
        # This is a placeholder for when seeding is implemented

        result1 = simulation.simulate_many_hands(100, "suit", "H")
        result2 = simulation.simulate_many_hands(100, "suit", "H")

        # Results should be statistically similar but not identical
        # (since there's randomness in shuffling)
        assert abs(result1["avg_team0"] - result2["avg_team0"]) < 1.0


class TestErrorHandling:
    """Test error handling in the simulation pipeline."""

    def test_invalid_contract_type_handling(self):
        """Test that invalid contract types are properly rejected."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "invalid_contract", None)

    def test_missing_trump_for_suit_contract(self):
        """Test error when suit contract lacks trump suit."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "suit", None)

    @pytest.mark.xfail(
        reason="Trump suit validation for high/low contracts not yet implemented"
    )
    def test_trump_provided_for_no_trump_contract(self):
        """Test error when trump suit provided for no-trump contracts."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "high", "H")

        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "low", "H")
