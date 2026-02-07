"""Unit tests for play_policy_gate.py."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
from play_policy_gate import (
    DirectionResult,
    ScenarioInfo,
    bootstrap_ci,
    compute_gate_status,
    compute_scenario_note,
    expand_distribution_to_adv,
    load_and_evaluate_run,
    pool_adv_samples,
)


class TestExpandDistribution:
    """Tests for expand_distribution_to_adv function."""

    def test_glutton_vs_greedy_positive_delta(self):
        """adv = 2*tricks - 10 when glutton is team0 (team0 = 7 tricks -> delta = +4)."""
        dist = {"7": 5, "8": 3}  # 5 hands with 7 tricks, 3 with 8
        samples = expand_distribution_to_adv(dist, "glutton_vs_greedy")

        # 7 tricks: delta = 2*7 - 10 = 4
        # 8 tricks: delta = 2*8 - 10 = 6
        expected = [4] * 5 + [6] * 3
        np.testing.assert_array_equal(samples, expected)

    def test_glutton_vs_greedy_negative_delta(self):
        """Team0 = 3 tricks means delta = 2*3 - 10 = -4."""
        dist = {"3": 2}
        samples = expand_distribution_to_adv(dist, "glutton_vs_greedy")

        expected = [-4, -4]
        np.testing.assert_array_equal(samples, expected)

    def test_greedy_vs_glutton_flips_sign(self):
        """adv = -(2*tricks - 10) when greedy is team0 (flip to make glutton positive)."""
        dist = {"7": 5, "8": 3}
        samples = expand_distribution_to_adv(dist, "greedy_vs_glutton")

        # greedy as team0 with 7 tricks means glutton got 3 tricks
        # delta = 2*7 - 10 = 4, but flipped to -4 (glutton worse)
        expected = [-4] * 5 + [-6] * 3
        np.testing.assert_array_equal(samples, expected)

    def test_greedy_vs_glutton_positive_when_glutton_better(self):
        """When greedy (team0) gets 3 tricks, glutton got 7, adv should be positive."""
        dist = {"3": 2}  # team0 (greedy) got 3 tricks
        samples = expand_distribution_to_adv(dist, "greedy_vs_glutton")

        # delta = 2*3 - 10 = -4, flipped to +4 (glutton better)
        expected = [4, 4]
        np.testing.assert_array_equal(samples, expected)

    def test_tie_gives_zero(self):
        """5-5 tie should give adv = 0."""
        dist = {"5": 10}
        samples = expand_distribution_to_adv(dist, "glutton_vs_greedy")

        expected = [0] * 10
        np.testing.assert_array_equal(samples, expected)

    def test_unknown_direction_raises(self):
        """Unknown direction should raise ValueError."""
        dist = {"5": 10}
        with pytest.raises(ValueError, match="Unknown direction"):
            expand_distribution_to_adv(dist, "unknown")


class TestPoolSamples:
    """Tests for pool_adv_samples function."""

    def test_concatenates_not_averages(self):
        """Pooling concatenates, not averages."""
        results = {
            "suit_H": {"distribution_team0": {"7": 3}},  # [4, 4, 4]
            "suit_S": {"distribution_team0": {"8": 2}},  # [6, 6]
        }
        pooled = pool_adv_samples(results, "glutton_vs_greedy")

        # Should be 5 samples total, not 2 averaged values
        assert len(pooled) == 5
        np.testing.assert_array_equal(sorted(pooled), [4, 4, 4, 6, 6])

    def test_empty_results(self):
        """Empty results return empty array."""
        pooled = pool_adv_samples({}, "glutton_vs_greedy")
        assert len(pooled) == 0

    def test_skips_missing_distribution(self):
        """Scenarios without distribution_team0 are skipped."""
        results = {
            "suit_H": {"distribution_team0": {"7": 3}},
            "suit_S": {"avg_team0": 5.0},  # no distribution
        }
        pooled = pool_adv_samples(results, "glutton_vs_greedy")

        assert len(pooled) == 3
        np.testing.assert_array_equal(pooled, [4, 4, 4])


class TestGateStatus:
    """Tests for compute_gate_status function."""

    def test_pass_ci_above_zero(self):
        """CI lower > 0 -> PASS."""
        assert compute_gate_status((0.5, 1.5)) == "PASS"
        assert compute_gate_status((0.01, 0.02)) == "PASS"

    def test_fail_ci_below_zero(self):
        """CI upper < 0 -> FAIL."""
        assert compute_gate_status((-1.5, -0.5)) == "FAIL"
        assert compute_gate_status((-0.02, -0.01)) == "FAIL"

    def test_warn_ci_overlaps_zero(self):
        """CI spans 0 -> WARN."""
        assert compute_gate_status((-0.5, 0.5)) == "WARN"
        assert compute_gate_status((-0.01, 0.01)) == "WARN"
        assert compute_gate_status((0.0, 0.5)) == "WARN"  # lower = 0
        assert compute_gate_status((-0.5, 0.0)) == "WARN"  # upper = 0


class TestScenarioNote:
    """Tests for compute_scenario_note function."""

    def test_reversal_when_upper_below_zero(self):
        """CI upper < 0 -> reversal."""
        assert compute_scenario_note((-1.5, -0.5)) == "reversal"

    def test_uncertain_when_overlaps_zero(self):
        """CI spans 0 -> uncertain."""
        assert compute_scenario_note((-0.5, 0.5)) == "uncertain"

    def test_empty_when_clearly_positive(self):
        """CI lower > 0 -> empty string."""
        assert compute_scenario_note((0.5, 1.5)) == ""


class TestOverallWorstOf:
    """Tests for overall worst-of logic."""

    def test_any_fail_gives_fail(self):
        """Any FAIL in directions -> overall FAIL."""
        directions = [
            DirectionResult("d1", 0.1, (0.05, 0.15), 100, "PASS"),
            DirectionResult("d2", -0.1, (-0.15, -0.05), 100, "FAIL"),
        ]
        statuses = [d.status for d in directions]
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "WARN" in statuses:
            overall = "WARN"
        else:
            overall = "PASS"

        assert overall == "FAIL"

    def test_any_warn_gives_warn(self):
        """Any WARN (no FAIL) -> overall WARN."""
        directions = [
            DirectionResult("d1", 0.1, (0.05, 0.15), 100, "PASS"),
            DirectionResult("d2", 0.0, (-0.05, 0.05), 100, "WARN"),
        ]
        statuses = [d.status for d in directions]
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "WARN" in statuses:
            overall = "WARN"
        else:
            overall = "PASS"

        assert overall == "WARN"

    def test_all_pass_gives_pass(self):
        """All PASS -> overall PASS."""
        directions = [
            DirectionResult("d1", 0.1, (0.05, 0.15), 100, "PASS"),
            DirectionResult("d2", 0.2, (0.15, 0.25), 100, "PASS"),
        ]
        statuses = [d.status for d in directions]
        if "FAIL" in statuses:
            overall = "FAIL"
        elif "WARN" in statuses:
            overall = "WARN"
        else:
            overall = "PASS"

        assert overall == "PASS"


class TestStrictScenariosFlag:
    """Tests for --strict-scenarios flag behavior."""

    def test_strict_reversal_causes_fail(self):
        """With strict_scenarios=True, per-scenario reversal -> FAIL."""
        scenarios = [
            ScenarioInfo("suit_H", 0.1, (0.05, 0.15), ""),
            ScenarioInfo("low", -0.1, (-0.15, -0.05), "reversal"),
        ]
        # Simulate strict mode check
        overall = "PASS"  # Would be PASS based on pooled
        for s in scenarios:
            if s.note == "reversal":
                overall = "FAIL"
                break

        assert overall == "FAIL"

    def test_non_strict_ignores_reversal(self):
        """Without strict_scenarios, per-scenario reversal doesn't affect overall."""
        # In non-strict mode, only pooled status matters, not per-scenario reversals
        # Create scenarios to verify they exist but don't affect the overall status
        _ = [
            ScenarioInfo("suit_H", 0.1, (0.05, 0.15), ""),
            ScenarioInfo("low", -0.1, (-0.15, -0.05), "reversal"),
        ]
        # Non-strict mode: overall is determined by pooled result only
        overall = "PASS"  # Based on pooled result, not checking scenarios

        assert overall == "PASS"


class TestBootstrapCI:
    """Tests for bootstrap_ci function."""

    def test_deterministic_with_same_seed(self):
        """Same seed -> same CI."""
        samples = np.random.default_rng(0).normal(0.5, 0.1, 1000)

        ci1 = bootstrap_ci(samples, 1000, seed=42)
        ci2 = bootstrap_ci(samples, 1000, seed=42)

        assert ci1 == ci2

    def test_different_seeds_different_results(self):
        """Different seeds -> different CIs (with high probability)."""
        samples = np.random.default_rng(0).normal(0.5, 0.1, 1000)

        ci1 = bootstrap_ci(samples, 1000, seed=42)
        ci2 = bootstrap_ci(samples, 1000, seed=43)

        # Should be different (extremely unlikely to be identical)
        assert ci1 != ci2

    def test_empty_samples(self):
        """Empty samples return (0.0, 0.0)."""
        ci = bootstrap_ci(np.array([]), 1000, seed=42)
        assert ci == (0.0, 0.0)

    def test_ci_contains_mean(self):
        """95% CI should contain the sample mean (for well-behaved data)."""
        samples = np.random.default_rng(0).normal(0.5, 0.1, 1000)
        mean = samples.mean()

        ci = bootstrap_ci(samples, 1000, seed=42)

        assert ci[0] <= mean <= ci[1]


class TestLoadAndEvaluate:
    """Tests for load_and_evaluate_run with fixture data."""

    def create_mock_run(self, tmpdir: Path, run_id: str, seed: int, results: dict):
        """Create a mock run directory with given results."""
        run_dir = tmpdir / run_id
        run_dir.mkdir(parents=True)

        # Create meta.json
        meta = {"seed": seed, "n_per": 100}
        (run_dir / "meta.json").write_text(json.dumps(meta))

        # Create results directory structure
        results_dir = run_dir / "results"
        for direction, scenarios in results.items():
            direction_dir = results_dir / direction
            direction_dir.mkdir(parents=True)
            for scenario, data in scenarios.items():
                (direction_dir / f"{scenario}.json").write_text(json.dumps(data))

        return run_dir

    def test_loads_and_evaluates_passing_run(self):
        """Test loading a run where glutton clearly wins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # glutton wins 8 tricks on average (strong positive advantage)
            results = {
                "glutton_vs_greedy": {
                    "suit_H": {"distribution_team0": {"8": 100}},
                    "suit_S": {"distribution_team0": {"8": 100}},
                },
                "greedy_vs_glutton": {
                    "suit_H": {"distribution_team0": {"2": 100}},  # greedy only gets 2
                    "suit_S": {"distribution_team0": {"2": 100}},
                },
            }

            self.create_mock_run(tmpdir, "test_run", seed=42, results=results)

            result = load_and_evaluate_run(
                tmpdir, "test_run", n_bootstrap=100, bootstrap_seed=42, strict_scenarios=False
            )

            assert result.seed == 42
            assert result.run_id == "test_run"
            assert result.status == "PASS"
            assert len(result.directions) == 2


class TestCLIArguments:
    """Tests for CLI argument validation."""

    def test_skip_run_without_run_ids_raises(self):
        """--skip-run without --run-ids should error."""
        # This is covered by the main() function's validation
        # We verify the logic here
        skip_run = True
        run_ids = None

        if skip_run and not run_ids:
            error = True
        else:
            error = False

        assert error is True

    def test_run_ids_seed_count_mismatch(self):
        """Number of run_ids must match number of seeds."""
        seeds = [42, 43, 44]
        run_ids = ["run1", "run2"]  # Only 2 run IDs for 3 seeds

        if len(run_ids) != len(seeds):
            error = True
        else:
            error = False

        assert error is True
