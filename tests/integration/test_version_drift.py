"""
Integration tests: Version drift detection.

These tests detect unintended behavior changes between versions by comparing
simulation results against known baselines. If tests fail after a code change,
either the change was unintentional (bug) or the baselines need updating.

Key principles:
- Store expected values as small literals in tests (not big fixture files)
- Use exact seed + config for reproducibility
- Small tolerance for floating-point comparison
- Document how to update baselines when intentional changes occur

To update baselines after intentional changes:
    PYTHONPATH=src python -c "
    from bid_euchre.sim.simulation import simulate_many_hands
    from bid_euchre.strategy.baselines import AlwaysHighestLegalStrategy
    result = simulate_many_hands(n=100, contract_type='suit', trump_suit='H',
                                  deal_seed=42, strategy=AlwaysHighestLegalStrategy())
    print(f'avg_team0={result[\"avg_team0\"]:.2f}')
    "
"""


from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.baselines import AlwaysHighestLegalStrategy

# ============================================================================
# BASELINE VALUES
# ============================================================================
# These are the expected results for specific (seed, config) combinations.
# If these fail after a code change, either:
#   1. The change was unintentional (fix the bug), or
#   2. The change was intentional (update the baseline)
#
# Last updated: 2025-01-27
# Git SHA at baseline: (update when changing)
# ============================================================================

BASELINE_SUIT_HEARTS_SEED42 = {
    "n": 100,
    "contract_type": "suit",
    "trump_suit": "H",
    "deal_seed": 42,
    "expected_avg_team0": 5.05,
    "expected_avg_team1": 4.95,
}

BASELINE_HIGH_SEED42 = {
    "n": 100,
    "contract_type": "high",
    "trump_suit": None,
    "deal_seed": 42,
    "expected_avg_team0": 4.97,
    "expected_avg_team1": 5.03,
}

BASELINE_LOW_SEED42 = {
    "n": 100,
    "contract_type": "low",
    "trump_suit": None,
    "deal_seed": 42,
    "expected_avg_team0": 4.96,
    "expected_avg_team1": 5.04,
}


class TestVersionDrift:
    """Tests that detect unintended behavior changes."""

    def test_baseline_suit_hearts_seed42(self) -> None:
        """Verify suit/H contract with seed=42 matches baseline."""
        baseline = BASELINE_SUIT_HEARTS_SEED42

        result = simulate_many_hands(
            n=baseline["n"],
            contract_type=baseline["contract_type"],
            trump_suit=baseline["trump_suit"],
            deal_seed=baseline["deal_seed"],
            strategy=AlwaysHighestLegalStrategy(),
        )

        # Exact match for deterministic simulation
        assert result["avg_team0"] == baseline["expected_avg_team0"], (
            f"Drift detected! Expected avg_team0={baseline['expected_avg_team0']}, "
            f"got {result['avg_team0']}. "
            f"If intentional, update BASELINE_SUIT_HEARTS_SEED42."
        )
        assert result["avg_team1"] == baseline["expected_avg_team1"], (
            f"Drift detected! Expected avg_team1={baseline['expected_avg_team1']}, "
            f"got {result['avg_team1']}. "
            f"If intentional, update BASELINE_SUIT_HEARTS_SEED42."
        )

    def test_baseline_high_seed42(self) -> None:
        """Verify HIGH contract with seed=42 matches baseline."""
        baseline = BASELINE_HIGH_SEED42

        result = simulate_many_hands(
            n=baseline["n"],
            contract_type=baseline["contract_type"],
            trump_suit=baseline["trump_suit"],
            deal_seed=baseline["deal_seed"],
            strategy=AlwaysHighestLegalStrategy(),
        )

        assert result["avg_team0"] == baseline["expected_avg_team0"], (
            f"Drift detected! Expected avg_team0={baseline['expected_avg_team0']}, "
            f"got {result['avg_team0']}. "
            f"If intentional, update BASELINE_HIGH_SEED42."
        )
        assert result["avg_team1"] == baseline["expected_avg_team1"], (
            f"Drift detected! Expected avg_team1={baseline['expected_avg_team1']}, "
            f"got {result['avg_team1']}. "
            f"If intentional, update BASELINE_HIGH_SEED42."
        )

    def test_baseline_low_seed42(self) -> None:
        """Verify LOW contract with seed=42 matches baseline."""
        baseline = BASELINE_LOW_SEED42

        result = simulate_many_hands(
            n=baseline["n"],
            contract_type=baseline["contract_type"],
            trump_suit=baseline["trump_suit"],
            deal_seed=baseline["deal_seed"],
            strategy=AlwaysHighestLegalStrategy(),
        )

        assert result["avg_team0"] == baseline["expected_avg_team0"], (
            f"Drift detected! Expected avg_team0={baseline['expected_avg_team0']}, "
            f"got {result['avg_team0']}. "
            f"If intentional, update BASELINE_LOW_SEED42."
        )
        assert result["avg_team1"] == baseline["expected_avg_team1"], (
            f"Drift detected! Expected avg_team1={baseline['expected_avg_team1']}, "
            f"got {result['avg_team1']}. "
            f"If intentional, update BASELINE_LOW_SEED42."
        )

    def test_tricks_sum_to_ten(self) -> None:
        """Sanity check: avg_team0 + avg_team1 should always equal 10."""
        for baseline in [BASELINE_SUIT_HEARTS_SEED42, BASELINE_HIGH_SEED42, BASELINE_LOW_SEED42]:
            total = baseline["expected_avg_team0"] + baseline["expected_avg_team1"]
            assert total == 10.0, (
                f"Baseline {baseline['contract_type']}: "
                f"avg_team0 + avg_team1 = {total}, expected 10.0"
            )

    def test_different_seeds_differ(self) -> None:
        """Different seeds should produce different results (sanity check)."""
        result_42 = simulate_many_hands(
            n=100,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=AlwaysHighestLegalStrategy(),
        )

        result_43 = simulate_many_hands(
            n=100,
            contract_type="suit",
            trump_suit="H",
            deal_seed=43,
            strategy=AlwaysHighestLegalStrategy(),
        )

        # Results should differ for different seeds
        assert result_42["avg_team0"] != result_43["avg_team0"], (
            "Different seeds produced identical results - RNG may be broken"
        )
