"""
Unit tests for experiment configuration loading.

Tests verify:
1. A.2: Roster + explicit strategies merge correctly (not overwrite)
2. A.1: play_strategy parameter loading from YAML works as documented
3. A.3: Evaluator metrics fields exist as expected (integration test for evaluator output)
"""

import pytest

from bid_euchre.experiments.config import load_config


class TestRosterWithExplicitStrategies:
    """Test A.2: roster + explicit strategies merge correctly."""

    def test_roster_with_explicit_strategies_merges(self, tmp_path):
        """Verify explicit strategies from YAML are preserved when using roster."""
        # Create a minimal roster
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: strict_raiser
    display_name: "Strict Raiser"
    kind: "policy"
    import_path: "bid_euchre.strategy.bidding.StrictRaiserBidder"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        # Create config that uses roster AND explicit strategies
        config_content = f"""
experiment_name: test_roster_with_strategies
strategy_roster_path: {roster_file}
include_baselines:
  - strict_raiser
strategies:
  - name: glutton_play
    class_name: GluttonStrategy
    params:
      debug: false
scenarios:
  - contract_type: null
parameters:
  n_per: 100
  seed: 42
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        # Verify both explicit strategies AND roster bidding policies are present
        assert len(config.strategies) == 1, "Explicit strategies should be preserved"
        assert config.strategies[0].name == "glutton_play"
        assert config.strategies[0].class_name == "GluttonStrategy"

        assert len(config.bidding_policies) == 1, "Roster bidding policies should be loaded"
        assert config.bidding_policies[0].name == "Strict Raiser"

    def test_roster_without_explicit_strategies(self, tmp_path):
        """Verify roster works when no explicit strategies are provided."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: rankthetank
    display_name: "RanktheTank"
    kind: "policy"
    import_path: "bid_euchre.strategy.bidding.RanktheTank"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        config_content = f"""
experiment_name: test_roster_only
strategy_roster_path: {roster_file}
include_baselines:
  - rankthetank
scenarios:
  - contract_type: null
parameters:
  n_per: 100
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert len(config.strategies) == 0
        assert len(config.bidding_policies) == 1
        assert config.bidding_policies[0].class_name == "RanktheTank"

    def test_explicit_strategies_without_roster(self, tmp_path):
        """Verify explicit strategies work without roster (legacy path)."""
        config_content = """
experiment_name: test_no_roster
strategies:
  - name: greedy
    class_name: GreedyStrategy
  - name: glutton
    class_name: GluttonStrategy
bidding_policies:
  - name: always_pass
    class_name: AlwaysPassBidder
scenarios:
  - contract_type: suit
    trump_suit: H
parameters:
  n_per: 100
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert len(config.strategies) == 2
        assert {s.name for s in config.strategies} == {"greedy", "glutton"}
        assert len(config.bidding_policies) == 1
        assert config.bidding_policies[0].name == "always_pass"

    def test_roster_with_explicit_bidding_policies_merges(self, tmp_path):
        """Verify explicit bidding_policies from YAML are also preserved when using roster."""
        roster_content = """
roster_version: "1"
created: "2026-01-13"
description: "Test roster"
baselines:
  - id: strict_raiser
    display_name: "Strict Raiser"
    kind: "policy"
    import_path: "bid_euchre.strategy.bidding.StrictRaiserBidder"
    params: {}
"""
        roster_file = tmp_path / "test_roster.yaml"
        roster_file.write_text(roster_content)

        # Config with both roster AND explicit bidding_policies
        config_content = f"""
experiment_name: test_roster_with_bidding_policies
strategy_roster_path: {roster_file}
include_baselines:
  - strict_raiser
bidding_policies:
  - name: always_pass
    class_name: AlwaysPassBidder
scenarios:
  - contract_type: null
parameters:
  n_per: 100
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        # Both explicit AND roster-derived bidding policies should be present
        assert len(config.bidding_policies) == 2
        names = {bp.name for bp in config.bidding_policies}
        assert "always_pass" in names, "Explicit bidding policy should be preserved"
        assert "Strict Raiser" in names, "Roster bidding policy should be added"


class TestPlayStrategyParameter:
    """Test A.1: play_strategy parameter loading from YAML."""

    def test_play_strategy_in_parameters(self, tmp_path):
        """Verify play_strategy is accessible from parameters dict."""
        config_content = """
experiment_name: test_play_strategy
strategies:
  - name: glutton_play
    class_name: GluttonStrategy
scenarios:
  - contract_type: null
parameters:
  n_per: 100
  play_strategy: glutton_play
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        assert config.parameters.get("play_strategy") == "glutton_play"

    def test_play_strategy_not_required(self, tmp_path):
        """Verify play_strategy is optional and defaults to None/missing."""
        config_content = """
experiment_name: test_no_play_strategy
strategies:
  - name: greedy
    class_name: GreedyStrategy
scenarios:
  - contract_type: suit
    trump_suit: H
parameters:
  n_per: 100
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_config(str(config_file))

        # play_strategy should either not exist or be None
        assert config.parameters.get("play_strategy") is None


class TestEvaluatorMetricFields:
    """Test A.3: Verify evaluator outputs expected metric fields.

    These tests verify the contract that evaluator produces specific metrics.
    The actual evaluator logic is tested elsewhere; here we test the public contract.
    """

    def test_evaluator_metric_fields_defined(self):
        """Verify the expected evaluator metrics exist in the module."""
        from bid_euchre.reporting.evaluator import (
            compute_cvar,
            compute_downside_variance,
        )

        # These functions should exist and be importable
        assert callable(compute_cvar)
        assert callable(compute_downside_variance)

    def test_evaluator_metric_computation_basic(self):
        """Verify cvar and downside_variance compute correctly on sample data."""
        from bid_euchre.reporting.evaluator import (
            compute_cvar,
            compute_downside_variance,
        )

        # Test with simple data
        values = [-10, -5, 0, 5, 10, 15, 20]

        cvar = compute_cvar(values, tail_fraction=0.20)
        assert cvar is not None
        # 20% of 7 values = ~1.4, rounded up to 2 values
        # Sorted: [-10, -5, 0, 5, 10, 15, 20], worst 2 = [-10, -5]
        # Mean = -7.5
        assert cvar == pytest.approx(-7.5, rel=0.01)

        downside_var = compute_downside_variance(values)
        assert downside_var is not None
        # Negatives: [-10, -5], mean_neg = -7.5
        # Variance = (((-10 - -7.5)^2) + ((-5 - -7.5)^2)) / 2 = (6.25 + 6.25) / 2 = 6.25
        assert downside_var == pytest.approx(6.25, rel=0.01)

    def test_evaluator_empty_values_handling(self):
        """Verify evaluator handles empty values gracefully."""
        from bid_euchre.reporting.evaluator import (
            compute_cvar,
            compute_downside_variance,
        )

        assert compute_cvar([]) is None
        assert compute_downside_variance([]) is None

        # No negatives should return None for downside_variance
        assert compute_downside_variance([1, 2, 3, 4, 5]) is None
