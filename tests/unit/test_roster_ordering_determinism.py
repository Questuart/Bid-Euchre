"""
Unit tests for roster ordering determinism and baseline ID stability.

This module tests that:
1. Roster baseline IDs are unique
2. Roster loading produces deterministic ordering
3. Expected baseline IDs exist in stable order
"""

from pathlib import Path

from bid_euchre.experiments.teacher_roster import load_teacher_roster


class TestRosterOrderingDeterminism:
    """Test roster ordering determinism and baseline ID stability."""

    def test_roster_baseline_ids_unique(self):
        """Test that all baseline IDs in the roster are unique."""
        roster_path = Path("experiments/baselines/teacher_roster_v1.yaml")
        roster = load_teacher_roster(roster_path)

        baseline_ids = [baseline['id'] for baseline in roster['baselines']]
        assert len(baseline_ids) == len(set(baseline_ids)), f"Duplicate baseline IDs found: {baseline_ids}"

    def test_roster_loading_deterministic(self):
        """Test that loading the roster multiple times produces identical results."""
        roster_path = Path("experiments/baselines/teacher_roster_v1.yaml")

        # Load roster multiple times
        roster1 = load_teacher_roster(roster_path)
        roster2 = load_teacher_roster(roster_path)
        roster3 = load_teacher_roster(roster_path)

        # All loads should produce identical results
        assert roster1 == roster2 == roster3

        # Baseline order should be identical
        ids1 = [b['id'] for b in roster1['baselines']]
        ids2 = [b['id'] for b in roster2['baselines']]
        ids3 = [b['id'] for b in roster3['baselines']]
        assert ids1 == ids2 == ids3

    def test_roster_has_expected_baselines_in_stable_order(self):
        """Test that roster contains expected baseline IDs in documented stable order."""
        roster_path = Path("experiments/baselines/teacher_roster_v1.yaml")
        roster = load_teacher_roster(roster_path)

        baseline_ids = [baseline['id'] for baseline in roster['baselines']]

        # Expected baseline IDs in stable order (matches roster file order)
        expected_ids = [
            "always_pass",
            "strict_raiser",
            "heuristics",
            "fixed_bidder",
            "artifact_bidder"
        ]

        assert baseline_ids == expected_ids, f"Baseline IDs not in expected order. Got: {baseline_ids}, Expected: {expected_ids}"

    def test_roster_derived_config_ordering_deterministic(self):
        """Test that roster-derived config creation produces deterministic ordering."""
        import tempfile
        from pathlib import Path

        import yaml

        from bid_euchre.experiments.config import load_config

        # Create a test config that uses the roster
        test_config = {
            "experiment_name": "test_roster_ordering",
            "strategy_roster_path": "experiments/baselines/teacher_roster_v1.yaml",
            "include_baselines": ["strict_raiser", "heuristics", "artifact_bidder"],
            "scenarios": [{"contract_type": None}],
            "parameters": {"n_per": 10, "seed": 42}
        }

        # Write to temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_config_path = f.name

        try:
            # Load config multiple times
            config1 = load_config(temp_config_path)
            config2 = load_config(temp_config_path)
            config3 = load_config(temp_config_path)

            # Extract bidding policy names
            policies1 = [p.name for p in config1.get_bidding_policies()]
            policies2 = [p.name for p in config2.get_bidding_policies()]
            policies3 = [p.name for p in config3.get_bidding_policies()]

            # All should be identical
            assert policies1 == policies2 == policies3

            # Should match the include_baselines order
            expected_order = ["Strict Raiser", "Heuristics", "Artifact Bidder (Greedy Play)"]
            assert policies1 == expected_order

        finally:
            Path(temp_config_path).unlink()
