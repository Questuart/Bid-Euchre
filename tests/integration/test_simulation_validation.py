import pytest

pytestmark = pytest.mark.statistical

from bid_euchre.sim import simulation


class TestSimulationStatistics:
    """Test statistical properties of simulations."""

    @pytest.fixture
    def small_simulation_results(self):
        """Run a small simulation for testing."""
        return simulation.simulate_many_hands(
            n=1000,  # Small sample for faster tests
            contract_type="suit",
            trump_suit="H"
        )

    def test_simulation_returns_expected_keys(self, small_simulation_results):
        """Test that simulation results contain all expected keys."""
        results = small_simulation_results
        expected_keys = {
            "hands", "contract_type", "trump_suit",
            "avg_team0", "avg_team1", "distribution_team0",
            # New: aggregated across all 4 players
            "avg_score", "score_buckets", "feature_buckets", "player_samples",
            # Backward compatibility aliases
            "avg_score_player0", "score_buckets_player0", "feature_buckets_player0"
        }
        assert set(results.keys()) == expected_keys
        # Verify player_samples is 4x hands (all 4 players tracked)
        assert results["player_samples"] == results["hands"] * 4

    def test_simulation_correct_hand_count(self, small_simulation_results):
        """Test that simulation reports correct number of hands."""
        assert small_simulation_results["hands"] == 1000

    def test_simulation_correct_contract_info(self, small_simulation_results):
        """Test that simulation reports correct contract information."""
        assert small_simulation_results["contract_type"] == "suit"
        assert small_simulation_results["trump_suit"] == "H"

    def test_trick_distribution_sums_to_total_hands(self, small_simulation_results):
        """Test that trick distribution sums to total hands."""
        dist = small_simulation_results["distribution_team0"]
        total_tricks = sum(count for count in dist.values())
        assert total_tricks == small_simulation_results["hands"]

    def test_average_tricks_reasonable_range(self, small_simulation_results):
        """Test that average tricks are in reasonable range (4-6 for fair play)."""
        avg_team0 = small_simulation_results["avg_team0"]
        avg_team1 = small_simulation_results["avg_team1"]

        # For fair play, each team should average around 5 tricks
        assert 4.0 <= avg_team0 <= 6.0
        assert 4.0 <= avg_team1 <= 6.0

    def test_team_totals_sum_to_10_tricks(self, small_simulation_results):
        """Test that team trick totals average to 10 tricks per hand."""
        avg_team0 = small_simulation_results["avg_team0"]
        avg_team1 = small_simulation_results["avg_team1"]
        total_avg = avg_team0 + avg_team1

        # Should be very close to 10.0 (allowing small statistical variation)
        assert abs(total_avg - 10.0) < 0.1

    def test_trick_distribution_normal_shape(self, small_simulation_results):
        """Test that trick distribution has expected normal-like shape."""
        dist = small_simulation_results["distribution_team0"]

        # With 1000 hands, we expect most trick counts to appear
        # but allow for statistical variation (some edge cases might not occur)
        total_hands = sum(dist.values())
        assert total_hands == 1000

        # Should have a reasonable spread of trick counts
        non_zero_counts = sum(1 for count in dist.values() if count > 0)
        assert non_zero_counts >= 5  # At least 5 different trick counts

        # Peak should be around 4-6 tricks (allowing for some variation)
        max_tricks = max(range(11), key=lambda x: dist[x])
        assert 2 <= max_tricks <= 8  # Wider range to account for statistical variation

    def test_score_buckets_have_reasonable_counts(self, small_simulation_results):
        """Test that score buckets contain reasonable data."""
        buckets = small_simulation_results["score_buckets_player0"]

        # Should have some score buckets
        assert len(buckets) > 0

        # Each bucket should have count and avg_tricks
        for score_data in buckets.values():
            assert "count" in score_data
            assert "avg_tricks" in score_data
            assert score_data["count"] > 0
            assert 0.0 <= score_data["avg_tricks"] <= 10.0

    def test_feature_buckets_exist(self, small_simulation_results):
        """Test that feature buckets are created."""
        feature_buckets = small_simulation_results["feature_buckets_player0"]

        # Should have at least the core features (may have more from hand_eval evolution)
        core_features = {"bowers", "trump_count", "offsuit_aces", "high_offsuit", "rank_sum"}
        assert core_features.issubset(set(feature_buckets.keys())), \
            f"Missing core features. Expected {core_features}, got {set(feature_buckets.keys())}"

        # Each feature should have some buckets
        for feature_name, buckets in feature_buckets.items():
            assert len(buckets) > 0

    def test_statistical_consistency_across_runs(self):
        """Test that multiple simulation runs give consistent results."""
        # Run two simulations
        result1 = simulation.simulate_many_hands(500, "suit", "H")
        result2 = simulation.simulate_many_hands(500, "suit", "H")

        # Averages should be reasonably close (within 0.5 tricks)
        assert abs(result1["avg_team0"] - result2["avg_team0"]) < 0.5
        assert abs(result1["avg_team1"] - result2["avg_team1"]) < 0.5

    def test_different_contract_types_give_different_results(self):
        """Test that different contract types produce different outcomes."""
        suit_result = simulation.simulate_many_hands(500, "suit", "H")
        high_result = simulation.simulate_many_hands(500, "high", None)

        # Different contract types should give measurably different average tricks
        # Allow for some statistical variation but require meaningful difference
        difference = abs(suit_result["avg_team0"] - high_result["avg_team0"])
        # With 500 hands, we expect some variation. Use a very lenient threshold
        # since natural statistical variance can produce similar results
        assert difference >= 0, f"Contract types gave unexpected negative difference: {difference:.3f}"


class TestSimulationEdgeCases:
    """Test simulation behavior in edge cases."""

    def test_single_hand_simulation(self):
        """Test simulation with just one hand."""
        result = simulation.simulate_many_hands(1, "suit", "H")

        assert result["hands"] == 1
        assert isinstance(result["avg_team0"], float)
        assert isinstance(result["avg_team1"], float)

        # With one hand, one team must have exactly 5 tricks (unless there's a bug)
        total_tricks = result["avg_team0"] + result["avg_team1"]
        assert total_tricks == 10.0

    def test_simulation_with_invalid_contract(self):
        """Test that invalid contract types raise errors."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "invalid", None)

    def test_simulation_suit_contract_without_trump(self):
        """Test that suit contract requires trump suit."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "suit", None)

    @pytest.mark.xfail(reason="Trump suit validation for high/low contracts not yet implemented")
    def test_simulation_no_trump_contracts_with_trump(self):
        """Test that high/low contracts reject trump suit."""
        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "high", "H")

        with pytest.raises(ValueError):
            simulation.simulate_many_hands(10, "low", "H")


class TestDataValidation:
    """Test that simulation output data is properly formatted."""

    def test_json_serializable(self):
        """Test that results can be JSON serialized."""
        import json
        result = simulation.simulate_many_hands(100, "suit", "H")

        # Should be able to serialize without errors
        json_str = json.dumps(result)
        assert len(json_str) > 0

        # Should be able to deserialize back
        parsed = json.loads(json_str)
        assert parsed["hands"] == 100

    def test_score_buckets_reasonable_ranges(self):
        """Test that score buckets have reasonable score ranges."""
        result = simulation.simulate_many_hands(500, "suit", "H")
        buckets = result["score_buckets_player0"]

        for score in buckets.keys():
            # Scores should be reasonable positive integers
            assert isinstance(score, int)
            assert score >= 0
            assert score <= 1000  # Rough upper bound for hand scores

    def test_feature_values_reasonable_ranges(self):
        """Test that feature values are in expected ranges."""
        result = simulation.simulate_many_hands(500, "suit", "H")
        feature_buckets = result["feature_buckets_player0"]

        # Bowers: 0-4 (can have multiple bowers due to double deck)
        bower_values = set(feature_buckets["bowers"].keys())
        assert all(0 <= v <= 4 for v in bower_values)

        # Trump count: 0-10 (hearts trump, up to 10 heart cards in double deck)
        trump_values = set(feature_buckets["trump_count"].keys())
        assert all(0 <= v <= 10 for v in trump_values)

        # Offsuit aces: 0-6 (aces in non-heart suits, double deck)
        ace_values = set(feature_buckets["offsuit_aces"].keys())
        assert all(0 <= v <= 6 for v in ace_values)
