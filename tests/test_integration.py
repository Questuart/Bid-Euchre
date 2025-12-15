import pytest
import sys
import os
import json
import tempfile

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.sim import simulation
from bid_euchre.core.cards import create_deck, deal_hands
from bid_euchre.core.rules import trick_winner
from bid_euchre.strategy.strategy import choose_card_basic


class TestEndToEndSimulation:
    """Test complete simulation workflows."""

    def test_full_hand_simulation_basic_strategy(self):
        """Test simulating a complete hand with basic strategy."""
        # Play one complete hand
        result = simulation.play_single_hand("suit", "H")

        team0_tricks, team1_tricks, player0_score, player0_features = result

        # Basic validation
        assert isinstance(team0_tricks, int)
        assert isinstance(team1_tricks, int)
        assert 0 <= team0_tricks <= 10
        assert 0 <= team1_tricks <= 10
        assert team0_tricks + team1_tricks == 10

        assert isinstance(player0_score, int)
        assert player0_score >= 0

        assert isinstance(player0_features, dict)
        expected_features = {"bowers", "trump_count", "offsuit_aces", "high_offsuit", "rank_sum"}
        assert set(player0_features.keys()) == expected_features

    def test_experiment_script_workflow(self):
        """Test the complete experiment script workflow."""
        import subprocess

        # Create temporary directory for test output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Run the experiment script with command line arguments
            cmd = [
                sys.executable,
                os.path.join(os.path.dirname(__file__), '..', 'experiments', 'run_baseline_greedy.py'),
                '--n_per', '50',
                '--seed', '42',
                '--output_dir', temp_dir
            ]

            # Set PYTHONPATH for the subprocess
            env = os.environ.copy()
            env['PYTHONPATH'] = os.path.join(os.path.dirname(__file__), '..', 'src')

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            # Check that the command succeeded
            assert result.returncode == 0, f"Command failed: {result.stderr}"

            # Check that output files were created
            expected_files = [
                "baseline_greedy_high.json",
                "baseline_greedy_low.json",
                "baseline_greedy_suit_C.json",
                "baseline_greedy_suit_D.json",
                "baseline_greedy_suit_H.json",
                "baseline_greedy_suit_S.json"
            ]

            for filename in expected_files:
                expected_file = os.path.join(temp_dir, filename)
                assert os.path.exists(expected_file), f"Missing output file: {filename}"

                # Check that file contains valid JSON
                with open(expected_file, 'r') as f:
                    data = json.load(f)
                    assert data["hands"] == 50
                    assert "contract_type" in data
                    assert "trump_suit" in data or data["contract_type"] in ["high", "low"]

    def test_strategy_comparison(self):
        """Test that different strategies produce different results."""
        # This would require modifying USE_GREEDY, so we'll test the concept
        # by running simulations and checking they're reasonably different

        # Run with greedy (default)
        result_greedy = simulation.simulate_many_hands(200, "suit", "H")

        # For a full test, we'd need to temporarily change USE_GREEDY
        # For now, just verify the simulation works
        assert result_greedy["hands"] == 200
        assert 4.0 <= result_greedy["avg_team0"] <= 6.0


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

    def test_experiment_data_directory_structure(self):
        """Test that experiment script creates expected directory structure."""
        # This would test the actual experiment script output
        # For now, just verify directories exist
        assert os.path.exists("data")
        assert os.path.exists("data/raw")
        assert os.path.exists("data/processed")
        assert os.path.exists("data/reports")

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

    def test_trump_provided_for_no_trump_contract(self):
        """Test error when trump suit provided for no-trump contracts."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "high", "H")

        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "low", "H")
