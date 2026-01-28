"""
Integration tests: RNG health diagnostics.

These tests verify that the RNG produces uniform distributions within bounded
tolerance limits. We avoid chi-square p-values to ensure CI stability.

Key invariants tested:
- Initial leader frequency should be roughly uniform (20-30% per seat)
- Different seeds must produce different deals
- Consecutive deals must differ (no stuck state)
- Same seed reproduces identical results
"""

from collections import Counter
from typing import List

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.sim.deals import generate_deal, generate_initial_leader
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.baselines import AlwaysHighestLegalStrategy


def _card_signature(hands: List[List[Card]]) -> tuple:
    """Create a hashable signature for a deal."""
    return tuple(
        tuple((c.suit, c.rank) for c in hand)
        for hand in hands
    )


class TestLeaderDistribution:
    """Tests for initial leader uniformity."""

    def test_initial_leader_bounded_frequency(self) -> None:
        """Leader positions should be roughly uniform (20-30% per seat).

        Uses bounded tolerance instead of chi-square p-values for CI stability.
        """
        n = 10_000
        seed = 12345

        leader_counts = Counter(
            generate_initial_leader(seed, deal_id) for deal_id in range(n)
        )

        # Check each seat is within 20-30% (±5% from expected 25%)
        for seat in range(4):
            freq = leader_counts[seat] / n
            assert 0.20 <= freq <= 0.30, (
                f"Seat {seat} has frequency {freq:.3f}, expected 0.20-0.30. "
                f"Counts: {dict(leader_counts)}"
            )

    def test_leader_distribution_different_seeds(self) -> None:
        """Different master seeds should produce different leader sequences."""
        n = 100

        leaders_seed1 = [generate_initial_leader(seed=1, deal_id=i) for i in range(n)]
        leaders_seed2 = [generate_initial_leader(seed=2, deal_id=i) for i in range(n)]

        # At least some leaders should differ
        matches = sum(1 for a, b in zip(leaders_seed1, leaders_seed2) if a == b)
        assert matches < n * 0.5, (
            f"Leaders from different seeds match {matches}/{n} times - "
            f"expected less than 50%"
        )


class TestDealDistinctness:
    """Tests ensuring different deals are actually different."""

    def test_different_seeds_produce_different_deals(self) -> None:
        """Different master seeds must produce different deals."""
        deal_id = 0

        hands1 = generate_deal(seed=100, deal_id=deal_id)
        hands2 = generate_deal(seed=200, deal_id=deal_id)

        sig1 = _card_signature(hands1)
        sig2 = _card_signature(hands2)

        assert sig1 != sig2, "Different seeds produced identical deals"

    def test_different_deal_ids_produce_different_deals(self) -> None:
        """Different deal_ids with same seed must produce different deals."""
        seed = 42

        hands1 = generate_deal(seed=seed, deal_id=0)
        hands2 = generate_deal(seed=seed, deal_id=1)

        sig1 = _card_signature(hands1)
        sig2 = _card_signature(hands2)

        assert sig1 != sig2, "Different deal_ids produced identical deals"

    def test_consecutive_deals_not_identical(self) -> None:
        """No stuck state: consecutive deals must differ."""
        seed = 42
        n = 100

        signatures = [
            _card_signature(generate_deal(seed=seed, deal_id=i))
            for i in range(n)
        ]

        # Check no consecutive duplicates
        for i in range(n - 1):
            assert signatures[i] != signatures[i + 1], (
                f"Consecutive deals {i} and {i+1} are identical (stuck state)"
            )

    def test_all_deals_distinct_in_batch(self) -> None:
        """All deals in a batch should be unique."""
        seed = 42
        n = 1000

        signatures = [
            _card_signature(generate_deal(seed=seed, deal_id=i))
            for i in range(n)
        ]

        unique_count = len(set(signatures))
        assert unique_count == n, (
            f"Expected {n} unique deals, got {unique_count}"
        )


class TestDeterminism:
    """Tests for RNG determinism (same inputs = same outputs)."""

    def test_same_seed_same_deal(self) -> None:
        """Same (seed, deal_id) must produce identical deals."""
        seed = 42
        deal_id = 7

        hands1 = generate_deal(seed=seed, deal_id=deal_id)
        hands2 = generate_deal(seed=seed, deal_id=deal_id)

        sig1 = _card_signature(hands1)
        sig2 = _card_signature(hands2)

        assert sig1 == sig2, "Same seed+deal_id produced different deals"

    def test_same_seed_same_leader(self) -> None:
        """Same (seed, deal_id) must produce identical leader."""
        seed = 42
        deal_id = 7

        leader1 = generate_initial_leader(seed=seed, deal_id=deal_id)
        leader2 = generate_initial_leader(seed=seed, deal_id=deal_id)

        assert leader1 == leader2, "Same seed+deal_id produced different leaders"

    def test_simulation_determinism(self) -> None:
        """Same seed must produce identical simulation results."""
        seed = 42
        n = 50

        result1 = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=seed,
            strategy=AlwaysHighestLegalStrategy(),
        )

        result2 = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=seed,
            strategy=AlwaysHighestLegalStrategy(),
        )

        assert result1 == result2, "Same seed produced different simulation results"


class TestDealIntegrity:
    """Tests for deal structure integrity."""

    def test_deal_has_40_cards(self) -> None:
        """Each deal should have exactly 40 cards (4 seats x 10 cards)."""
        seed = 42

        for deal_id in range(100):
            hands = generate_deal(seed=seed, deal_id=deal_id)

            assert len(hands) == 4, f"Expected 4 hands, got {len(hands)}"
            for seat, hand in enumerate(hands):
                assert len(hand) == 10, (
                    f"Deal {deal_id} seat {seat}: expected 10 cards, got {len(hand)}"
                )

    def test_deal_card_counts_valid(self) -> None:
        """Each (suit, rank) should appear at most twice (double deck)."""
        seed = 42

        for deal_id in range(100):
            hands = generate_deal(seed=seed, deal_id=deal_id)
            all_cards = [c for hand in hands for c in hand]

            counts = Counter((c.suit, c.rank) for c in all_cards)
            for card_key, count in counts.items():
                assert count <= 2, (
                    f"Deal {deal_id}: {card_key} appears {count} times (max 2)"
                )


class TestSeedSpaceDistribution:
    """Tests for distribution across the seed space."""

    def test_hands_vary_across_seats(self) -> None:
        """Different seats should receive different hands."""
        seed = 42

        for deal_id in range(100):
            hands = generate_deal(seed=seed, deal_id=deal_id)
            signatures = [tuple((c.suit, c.rank) for c in h) for h in hands]

            # At least 3 of 4 hands should be different
            unique_hands = len(set(signatures))
            assert unique_hands >= 3, (
                f"Deal {deal_id}: only {unique_hands} unique hands out of 4"
            )

    @pytest.mark.parametrize("contract_type,trump_suit", [
        ("suit", "H"),
        ("suit", "S"),
        ("high", None),
        ("low", None),
    ])
    def test_trick_distribution_bounded(self, contract_type: str, trump_suit: str | None) -> None:
        """Trick counts should be reasonably distributed (not degenerate)."""
        seed = 42
        n = 200

        result = simulate_many_hands(
            n=n,
            contract_type=contract_type,
            trump_suit=trump_suit,
            deal_seed=seed,
            strategy=AlwaysHighestLegalStrategy(),
        )

        # Extract team trick averages and convert to totals
        avg_t0 = result["avg_team0"]
        avg_t1 = result["avg_team1"]

        # Verify averages sum to 10 (10 tricks per hand)
        assert abs((avg_t0 + avg_t1) - 10.0) < 0.01, (
            f"Expected avg_team0 + avg_team1 = 10, got {avg_t0 + avg_t1}"
        )

        # Distribution should not be degenerate (one team winning all)
        t0_ratio = avg_t0 / 10.0
        assert 0.1 < t0_ratio < 0.9, (
            f"Trick distribution too skewed: Team0={t0_ratio:.2%}"
        )
