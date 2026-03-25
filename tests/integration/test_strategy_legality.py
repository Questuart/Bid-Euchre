"""
Integration tests: Strategy legality validation.

These tests verify that all strategy implementations always return legal moves.
The engine has guardrails that throw on illegal plays, so this test suite
ensures strategies don't trigger those guardrails.

Key invariants tested:
- Every strategy returns a legal card index 100% of the time
- Strategies handle all contract types correctly
- Strategies work with all trump suits
"""

from typing import Type

import pytest

pytestmark = pytest.mark.integration

from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.baselines import (
    AlwaysHighestLegalStrategy,
    AlwaysLowestLegalStrategy,
    BasicStrategy,
    RandomLegalStrategy,
)
from bid_euchre.strategy.greedy import GluttonStrategy, GreedyStrategy

# All strategy classes to test
STRATEGY_CLASSES: list[Type[Strategy]] = [
    BasicStrategy,
    RandomLegalStrategy,
    AlwaysLowestLegalStrategy,
    AlwaysHighestLegalStrategy,
    GreedyStrategy,
    GluttonStrategy,
]


class TestStrategyLegalityBasic:
    """Basic legality tests for all strategies."""

    @pytest.mark.parametrize("strategy_class", STRATEGY_CLASSES)
    def test_strategy_legal_suit_contract(self, strategy_class: Type[Strategy]) -> None:
        """Every strategy must return legal moves in suit contracts."""
        strategy = strategy_class()
        n = 100  # Run enough hands to exercise various game states

        # If this raises, the strategy returned an illegal move
        result = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=strategy,
        )

        # Basic sanity: avg tricks should sum to 10
        assert abs((result["avg_team0"] + result["avg_team1"]) - 10.0) < 0.01

    @pytest.mark.parametrize("strategy_class", STRATEGY_CLASSES)
    def test_strategy_legal_high_contract(self, strategy_class: Type[Strategy]) -> None:
        """Every strategy must return legal moves in HIGH contracts."""
        strategy = strategy_class()
        n = 100

        result = simulate_many_hands(
            n=n,
            contract_type="high",
            trump_suit=None,
            deal_seed=43,
            strategy=strategy,
        )

        assert abs((result["avg_team0"] + result["avg_team1"]) - 10.0) < 0.01

    @pytest.mark.parametrize("strategy_class", STRATEGY_CLASSES)
    def test_strategy_legal_low_contract(self, strategy_class: Type[Strategy]) -> None:
        """Every strategy must return legal moves in LOW contracts."""
        strategy = strategy_class()
        n = 100

        result = simulate_many_hands(
            n=n,
            contract_type="low",
            trump_suit=None,
            deal_seed=44,
            strategy=strategy,
        )

        assert abs((result["avg_team0"] + result["avg_team1"]) - 10.0) < 0.01


class TestStrategyLegalityAllTrumpSuits:
    """Test strategies across all trump suits."""

    @pytest.mark.parametrize("strategy_class", STRATEGY_CLASSES)
    @pytest.mark.parametrize("trump_suit", ["C", "D", "H", "S"])
    def test_strategy_legal_all_trump_suits(
        self, strategy_class: Type[Strategy], trump_suit: str
    ) -> None:
        """Strategies must handle all trump suits correctly."""
        strategy = strategy_class()
        n = 50  # Fewer hands per combination since we're testing many

        result = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit=trump_suit,
            deal_seed=100 + ord(trump_suit),  # Different seed per suit
            strategy=strategy,
        )

        assert abs((result["avg_team0"] + result["avg_team1"]) - 10.0) < 0.01


class TestStrategyLegalityStress:
    """Stress tests with many hands."""

    @pytest.mark.parametrize("strategy_class", STRATEGY_CLASSES)
    def test_strategy_500_hands(self, strategy_class: Type[Strategy]) -> None:
        """Run 500 hands to catch rare edge cases."""
        strategy = strategy_class()
        n = 500

        # Test across multiple contract types
        for contract_type, trump_suit in [
            ("suit", "H"),
            ("high", None),
            ("low", None),
        ]:
            result = simulate_many_hands(
                n=n,
                contract_type=contract_type,
                trump_suit=trump_suit,
                deal_seed=999,
                strategy=strategy,
            )

            assert abs((result["avg_team0"] + result["avg_team1"]) - 10.0) < 0.01


class TestRandomStrategySeeding:
    """Tests specific to RandomLegalStrategy seeding."""

    def test_random_strategy_seeded_is_deterministic(self) -> None:
        """RandomLegalStrategy with seed should be deterministic."""
        seed = 12345
        n = 50

        result1 = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=RandomLegalStrategy(seed=seed),
        )

        result2 = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=RandomLegalStrategy(seed=seed),
        )

        assert result1 == result2, "Seeded RandomLegalStrategy should be deterministic"

    def test_random_strategy_different_seeds_differ(self) -> None:
        """RandomLegalStrategy with different seeds should produce different results."""
        n = 100

        result1 = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=RandomLegalStrategy(seed=1),
        )

        result2 = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=RandomLegalStrategy(seed=2),
        )

        # Results should differ (different play choices)
        assert result1 != result2, "Different seeds should produce different results"


class TestMixedStrategies:
    """Tests with different strategies per seat."""

    def test_mixed_strategies_legal(self) -> None:
        """Different strategies per seat should all play legally."""
        from bid_euchre.sim.deals import generate_deal
        from bid_euchre.sim.simulation import play_single_hand

        strategies = [
            AlwaysHighestLegalStrategy(),
            AlwaysLowestLegalStrategy(),
            GreedyStrategy(),
            GluttonStrategy(),
        ]

        n = 100
        for deal_id in range(n):
            hands = generate_deal(seed=42, deal_id=deal_id)

            # This should not raise
            result = play_single_hand(
                contract_type="suit",
                trump_suit="H",
                strategies=strategies,
                hands=[list(h) for h in hands],
                deal_seed=42,
                initial_leader=deal_id % 4,
            )

            # Tricks should sum to 10
            t0, t1 = result[0], result[1]
            assert t0 + t1 == 10, f"Deal {deal_id}: tricks {t0}+{t1}!=10"

    def test_alternating_high_low_strategies(self) -> None:
        """Alternating aggressive/passive strategies should work."""
        from bid_euchre.sim.deals import generate_deal
        from bid_euchre.sim.simulation import play_single_hand

        strategies = [
            AlwaysHighestLegalStrategy(),  # Seat 0: aggressive
            AlwaysLowestLegalStrategy(),  # Seat 1: passive
            AlwaysHighestLegalStrategy(),  # Seat 2: aggressive
            AlwaysLowestLegalStrategy(),  # Seat 3: passive
        ]

        n = 100
        for deal_id in range(n):
            hands = generate_deal(seed=123, deal_id=deal_id)

            result = play_single_hand(
                contract_type="suit",
                trump_suit="S",
                strategies=strategies,
                hands=[list(h) for h in hands],
                deal_seed=123,
                initial_leader=0,
            )

            t0, t1 = result[0], result[1]
            assert t0 + t1 == 10


class TestGluttonStrategySpecific:
    """Tests specific to GluttonStrategy's tracking behavior."""

    def test_glutton_card_tracking_resets(self) -> None:
        """GluttonStrategy should reset card tracking on new hands."""
        from bid_euchre.sim.deals import generate_deal
        from bid_euchre.sim.simulation import play_single_hand

        strategy = GluttonStrategy()

        # Play multiple hands with same strategy instance
        for deal_id in range(50):
            hands = generate_deal(seed=42, deal_id=deal_id)

            result = play_single_hand(
                contract_type="suit",
                trump_suit="H",
                strategy=strategy,
                hands=[list(h) for h in hands],
                deal_seed=42,
                initial_leader=0,
            )

            t0, t1 = result[0], result[1]
            assert (
                t0 + t1 == 10
            ), f"Deal {deal_id}: card tracking may have corrupted state"

    def test_glutton_debug_mode_legal(self) -> None:
        """GluttonStrategy in debug mode should still play legally."""
        strategy = GluttonStrategy(debug=True)
        n = 100

        result = simulate_many_hands(
            n=n,
            contract_type="suit",
            trump_suit="H",
            deal_seed=42,
            strategy=strategy,
        )

        assert abs((result["avg_team0"] + result["avg_team1"]) - 10.0) < 0.01

        # Debug mode should have logged decisions
        assert len(strategy.decision_log) > 0, "Debug mode should log decisions"
