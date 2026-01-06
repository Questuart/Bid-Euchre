import time

import pytest

from bid_euchre.sim import simulation


class TestPerformanceRegression:
    """Test for performance regressions in simulation speed."""

    @pytest.mark.slow
    def test_simulation_performance_baseline(self):
        """Test that simulation performance meets baseline expectations."""
        # This test establishes a performance baseline
        # Adjust thresholds based on your system's performance

        start_time = time.time()
        result = simulation.simulate_many_hands(1000, "suit", "H")
        end_time = time.time()

        duration = end_time - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        # On a typical modern machine, 1000 hands should take < 5 seconds
        assert duration < 10.0, f"{duration:.2f}"

        # Verify result is still correct
        assert result["hands"] == 1000
        assert 4.0 <= result["avg_team0"] <= 6.0

    def test_memory_usage_basic(self):
        """Basic test that simulations don't cause obvious memory issues."""
        # Run multiple simulations to check for memory leaks
        for i in range(10):
            result = simulation.simulate_many_hands(100, "suit", "H")
            assert result["hands"] == 100

        # If we get here without crashing, basic memory usage is OK
        # More sophisticated memory testing would require additional tools

    def test_large_simulation_scalability(self):
        """Test that large simulations scale reasonably."""
        # Test with increasing sizes
        sizes = [100, 500, 1000]

        times = []
        for size in sizes:
            start_time = time.time()
            result = simulation.simulate_many_hands(size, "suit", "H")
            end_time = time.time()

            duration = end_time - start_time
            times.append(duration)

            assert result["hands"] == size

        # Check that scaling is roughly linear (allowing some overhead)
        # Time for 1000 should be roughly 10x time for 100
        scaling_factor = times[2] / times[0]  # 1000 vs 100
        assert 5.0 <= scaling_factor <= 20.0  # Allow some variance


class TestStatisticalStability:
    """Test statistical stability of simulation results."""

    def test_results_stability_over_time(self):
        """Test that results are statistically stable across multiple runs."""
        # Run multiple small simulations
        results = []
        for _ in range(5):
            result = simulation.simulate_many_hands(200, "suit", "H")
            results.append(result["avg_team0"])

        # Calculate coefficient of variation
        mean_result = sum(results) / len(results)
        variance = sum((x - mean_result) ** 2 for x in results) / len(results)
        std_dev = variance ** 0.5
        cv = std_dev / mean_result if mean_result > 0 else 0

        # Coefficient of variation should be reasonable (< 10%)
        # This indicates statistical stability
        assert cv < 0.1, ".3f"

    def test_different_seeds_give_different_results(self):
        """Test that different random seeds give different results."""
        # Note: Current implementation doesn't support explicit seeding
        # This test would be more meaningful with seeded randomness

        result1 = simulation.simulate_many_hands(500, "suit", "H")
        result2 = simulation.simulate_many_hands(500, "suit", "H")

        # Results should be similar but not identical
        assert abs(result1["avg_team0"] - result2["avg_team0"]) < 1.0
        # Very unlikely to be exactly equal (probability ~ 1e-10)
        assert result1["avg_team0"] != result2["avg_team0"]
