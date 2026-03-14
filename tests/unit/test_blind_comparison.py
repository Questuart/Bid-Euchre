"""Unit tests for blind strategy comparison tool.

Tests import the script functions via importlib.util (same pattern as
test_h2h_battery.py) since scripts/internal/ has no __init__.py.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import script module via importlib.util
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).parent.parent.parent
    / "scripts"
    / "internal"
    / "blind_strategy_comparison.py"
)
_spec = importlib.util.spec_from_file_location(
    "blind_strategy_comparison", _SCRIPT_PATH
)
_mod = importlib.util.module_from_spec(_spec)
# Register in sys.modules so dataclass decorator can resolve the module
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

compare_blind = _mod.compare_blind
load_profile = _mod.load_profile
anonymize_profile = _mod.anonymize_profile
result_to_dict = _mod.result_to_dict
result_to_markdown = _mod.result_to_markdown
BlindComparisonResult = _mod.BlindComparisonResult
RubricScore = _mod.RubricScore
_extract_strategy_name = _mod._extract_strategy_name
_get_per_contract_eppd = _mod._get_per_contract_eppd
_get_seed_deltas = _mod._get_seed_deltas

# ---------------------------------------------------------------------------
# Realistic test profiles based on R1.5.3 GBT vs Hybrid R0 results
# (pooled +0.570, suit +0.827, high +0.333, low -0.041)
# ---------------------------------------------------------------------------

GBT_PROFILE = {
    "strategy_id": "gbt_av_bidder_r1_5_3",
    "strategy_name": "GBT Action-Value Bidder",
    "model_type": "gradient_boosted_trees",
    "artifact_path": "data/artifacts/arc_d/r1_5_3/gbt_av.json",
    "feature_count": 42,
    "net_expected_points_per_deal": 0.570,
    "net_eppd": 0.570,
    "expected_points_per_deal": 4.85,
    "bid_rate": 0.45,
    "make_rate": 0.72,
    "pass_rate": 0.55,
    "cvar_5": -3.2,
    "net_cvar_5": -5.1,
    "downside_variance": 12.5,
    "net_downside_variance": 18.3,
    "deals_total": 50000,
    "ci_low": 0.50,
    "ci_high": 0.64,
    "suit": {"net_eppd": 0.827, "bid_rate": 0.35, "make_rate": 0.75},
    "high": {"net_eppd": 0.333, "bid_rate": 0.30, "make_rate": 0.68},
    "low": {"net_eppd": -0.041, "bid_rate": 0.15, "make_rate": 0.62},
    "seed_deltas": [0.595, 0.557, 0.558],
}

HYBRID_R0_PROFILE = {
    "strategy_id": "hybrid_olsa_r0",
    "strategy_name": "Hybrid OLSa R0",
    "model_type": "hybrid_olsa_v1",
    "artifact_path": "data/artifacts/arc_d/r0/hybrid_r0.json",
    "feature_count": 39,
    "net_expected_points_per_deal": 0.0,
    "net_eppd": 0.0,
    "expected_points_per_deal": 4.28,
    "bid_rate": 0.42,
    "make_rate": 0.65,
    "pass_rate": 0.58,
    "cvar_5": -3.8,
    "net_cvar_5": -5.9,
    "downside_variance": 14.1,
    "net_downside_variance": 20.7,
    "deals_total": 50000,
    "ci_low": -0.07,
    "ci_high": 0.07,
    "suit": {"net_eppd": 0.0, "bid_rate": 0.32, "make_rate": 0.68},
    "high": {"net_eppd": 0.0, "bid_rate": 0.28, "make_rate": 0.60},
    "low": {"net_eppd": 0.0, "bid_rate": 0.14, "make_rate": 0.58},
    "seed_deltas": [0.0, 0.0, 0.0],
}

# Profiles that are nearly identical (for tie detection)
CLOSE_PROFILE_A = {
    "strategy_id": "strategy_a",
    "net_eppd": 1.005,
    "suit": {"net_eppd": 1.2},
    "high": {"net_eppd": 0.8},
    "low": {"net_eppd": 0.5},
}

CLOSE_PROFILE_B = {
    "strategy_id": "strategy_b",
    "net_eppd": 1.000,
    "suit": {"net_eppd": 1.2},
    "high": {"net_eppd": 0.8},
    "low": {"net_eppd": 0.5},
}


# ---------------------------------------------------------------------------
# Tests: Label randomization
# ---------------------------------------------------------------------------


class TestLabelRandomization:
    def test_deterministic_with_same_seed(self):
        """Same seed produces same label assignment."""
        r1 = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        r2 = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        assert r1.label_assignment == r2.label_assignment
        assert r1.winner == r2.winner
        assert r1.alpha_total == r2.alpha_total
        assert r1.beta_total == r2.beta_total

    def test_different_seeds_can_differ(self):
        """Different seeds can produce different label assignments.

        We check a range of seeds to find at least one that swaps.
        """
        base = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        found_different = False
        for s in range(100):
            other = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=s)
            if other.label_assignment != base.label_assignment:
                found_different = True
                break
        assert (
            found_different
        ), "Expected at least one seed to produce a different assignment"

    def test_label_keys(self):
        """Label assignment has exactly Alpha and Beta keys."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        assert set(result.label_assignment.keys()) == {"Alpha", "Beta"}

    def test_label_values_are_real_names(self):
        """Label assignment values are the original strategy names."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        names = set(result.label_assignment.values())
        assert names == {"gbt_av_bidder_r1_5_3", "hybrid_olsa_r0"}


# ---------------------------------------------------------------------------
# Tests: Anonymization
# ---------------------------------------------------------------------------


class TestAnonymization:
    def test_no_strategy_names_leak(self):
        """Anonymized profile must not contain identifying keys."""
        anon = anonymize_profile(GBT_PROFILE)
        for key in (
            "strategy_id",
            "strategy_name",
            "model_type",
            "artifact_path",
            "feature_count",
        ):
            assert (
                key not in anon
            ), f"Identifying key '{key}' leaked into anonymized profile"

    def test_performance_metrics_preserved(self):
        """Anonymized profile preserves performance metrics."""
        anon = anonymize_profile(GBT_PROFILE)
        assert anon["net_eppd"] == 0.570
        assert anon["bid_rate"] == 0.45
        assert anon["make_rate"] == 0.72

    def test_nested_contract_data_preserved(self):
        """Anonymized profile preserves per-contract data."""
        anon = anonymize_profile(GBT_PROFILE)
        assert "suit" in anon
        assert anon["suit"]["net_eppd"] == 0.827
        assert anon["high"]["net_eppd"] == 0.333
        assert anon["low"]["net_eppd"] == -0.041

    def test_seed_deltas_preserved(self):
        """Anonymized profile preserves multi-seed data."""
        anon = anonymize_profile(GBT_PROFILE)
        assert anon["seed_deltas"] == [0.595, 0.557, 0.558]

    def test_empty_profile(self):
        """Anonymizing empty profile returns empty dict."""
        assert anonymize_profile({}) == {}


# ---------------------------------------------------------------------------
# Tests: Rubric scoring
# ---------------------------------------------------------------------------


class TestRubricScoring:
    def test_scores_in_range(self):
        """All rubric scores must be between 1 and 5."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        for r in result.rubric:
            assert (
                1 <= r.score_alpha <= 5
            ), f"{r.criterion}: Alpha score {r.score_alpha} out of range"
            assert (
                1 <= r.score_beta <= 5
            ), f"{r.criterion}: Beta score {r.score_beta} out of range"

    def test_five_criteria(self):
        """Rubric has exactly 5 criteria."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        assert len(result.rubric) == 5

    def test_criteria_names(self):
        """Rubric criteria match expected names."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        names = {r.criterion for r in result.rubric}
        expected = {
            "pooled_net_eppd",
            "worst_contract_risk",
            "cross_contract_consistency",
            "statistical_significance",
            "seed_stability",
        }
        assert names == expected

    def test_weights_include_pooled_2x(self):
        """Pooled net_eppd criterion has 2x weight."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        pooled = [r for r in result.rubric if r.criterion == "pooled_net_eppd"][0]
        assert pooled.weight == 2.0
        for r in result.rubric:
            if r.criterion != "pooled_net_eppd":
                assert r.weight == 1.0

    def test_reasoning_not_empty(self):
        """Each rubric criterion has non-empty reasoning."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        for r in result.rubric:
            assert r.reasoning, f"{r.criterion}: reasoning is empty"


# ---------------------------------------------------------------------------
# Tests: Winner determination
# ---------------------------------------------------------------------------


class TestWinnerDetermination:
    def test_clear_winner_gbt_vs_r0(self):
        """GBT with pooled +0.570 should win over R0 baseline."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        # The winner label is "Alpha" or "Beta", but the real name should be GBT
        assert result.winner_real_name == "gbt_av_bidder_r1_5_3"
        assert result.winner in ("Alpha", "Beta")

    def test_tie_detection_close_profiles(self):
        """Strategies within 0.01 net_eppd delta should produce Tie or weak confidence."""
        result = compare_blind(CLOSE_PROFILE_A, CLOSE_PROFILE_B, seed=42)
        # With only 0.005 net_eppd gap and identical per-contract data,
        # this should be a tie or very weak result
        assert result.confidence == "weak" or result.winner == "Tie"

    def test_confidence_levels(self):
        """Confidence is one of strong, moderate, weak."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        assert result.confidence in ("strong", "moderate", "weak")

    def test_winner_matches_higher_total(self):
        """Winner should be the strategy with the higher weighted total."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        if result.winner == "Alpha":
            assert result.alpha_total >= result.beta_total
        elif result.winner == "Beta":
            assert result.beta_total >= result.alpha_total
        else:
            # Tie
            assert abs(result.alpha_total - result.beta_total) < 0.1


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_missing_contract_types(self):
        """Profiles without per-contract data should not crash."""
        profile_no_contracts = {
            "strategy_id": "minimal",
            "net_eppd": 0.3,
            "bid_rate": 0.4,
        }
        result = compare_blind(profile_no_contracts, HYBRID_R0_PROFILE, seed=42)
        assert result.winner in ("Alpha", "Beta", "Tie")
        assert len(result.rubric) == 5

    def test_single_seed_data(self):
        """Profiles with no multi-seed data should still score seed_stability."""
        profile_no_seeds = {
            "strategy_id": "no_seeds",
            "net_eppd": 0.5,
        }
        result = compare_blind(profile_no_seeds, HYBRID_R0_PROFILE, seed=42)
        seed_criterion = [r for r in result.rubric if r.criterion == "seed_stability"][
            0
        ]
        # Should get neutral score when data is absent on one side
        assert 1 <= seed_criterion.score_alpha <= 5
        assert 1 <= seed_criterion.score_beta <= 5

    def test_minimal_profiles(self):
        """Comparison of two minimal profiles should not crash."""
        minimal_a = {"strategy_id": "a", "net_eppd": 0.1}
        minimal_b = {"strategy_id": "b", "net_eppd": 0.2}
        result = compare_blind(minimal_a, minimal_b, seed=42)
        assert isinstance(result, BlindComparisonResult)
        assert result.summary  # Non-empty summary

    def test_missing_strategy_id(self):
        """Profiles without strategy_id should default to 'unknown'."""
        profile = {"net_eppd": 0.5}
        name = _extract_strategy_name(profile)
        assert name == "unknown"


# ---------------------------------------------------------------------------
# Tests: JSON output
# ---------------------------------------------------------------------------


class TestJsonOutput:
    def test_valid_json(self):
        """Output is valid, parseable JSON."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        d = result_to_dict(result)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert "seed" in parsed
        assert "rubric" in parsed
        assert "winner" in parsed
        assert "label_assignment" in parsed

    def test_schema_version(self):
        """JSON output contains schema version."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        d = result_to_dict(result)
        assert d["schema"] == "blind_comparison_v1"

    def test_generated_at(self):
        """JSON output contains timestamp."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        d = result_to_dict(result)
        assert "generated_at" in d
        assert d["generated_at"].endswith("Z")

    def test_rubric_in_json(self):
        """JSON output contains all rubric entries as dicts."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        d = result_to_dict(result)
        assert len(d["rubric"]) == 5
        for entry in d["rubric"]:
            assert "criterion" in entry
            assert "weight" in entry
            assert "score_alpha" in entry
            assert "score_beta" in entry
            assert "reasoning" in entry


# ---------------------------------------------------------------------------
# Tests: Markdown output
# ---------------------------------------------------------------------------


class TestMarkdownOutput:
    def test_contains_rubric_table(self):
        """Markdown output contains a rubric table."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        md = result_to_markdown(result)
        assert "| Criterion | Weight | Alpha | Beta | Reasoning |" in md

    def test_contains_unblinding(self):
        """Markdown output contains unblinding section."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        md = result_to_markdown(result)
        assert "## Unblinding" in md
        assert "Alpha" in md
        assert "Beta" in md

    def test_contains_summary(self):
        """Markdown output contains summary."""
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        md = result_to_markdown(result)
        assert "## Summary" in md

    def test_no_identifying_info_before_unblinding(self):
        """Before unblinding section, no real strategy names appear.

        The rubric section should use Alpha/Beta labels only.
        """
        result = compare_blind(GBT_PROFILE, HYBRID_R0_PROFILE, seed=42)
        md = result_to_markdown(result)
        # Split at unblinding section
        parts = md.split("## Unblinding")
        rubric_section = parts[0]
        # Real names should not appear in the rubric section
        assert "gbt_av_bidder_r1_5_3" not in rubric_section
        assert "hybrid_olsa_r0" not in rubric_section


# ---------------------------------------------------------------------------
# Tests: Profile loading
# ---------------------------------------------------------------------------


class TestProfileLoading:
    def test_load_flat_format(self):
        """Load flat metrics dict."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"net_eppd": 0.5, "bid_rate": 0.4}, f)
            f.flush()
            profile = load_profile(f.name)
        assert profile["net_eppd"] == 0.5

    def test_load_strategies_format(self):
        """Load evaluator output with strategies list."""
        data = {"strategies": [{"strategy_id": "test", "net_eppd": 0.3}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            profile = load_profile(f.name)
        assert profile["net_eppd"] == 0.3

    def test_load_nested_metrics_format(self):
        """Load nested metrics dict."""
        data = {"metrics": {"net_eppd": 0.7}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            f.flush()
            profile = load_profile(f.name)
        assert profile["net_eppd"] == 0.7

    def test_file_not_found(self):
        """Loading non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_profile("/nonexistent/path/metrics.json")


# ---------------------------------------------------------------------------
# Tests: Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_get_per_contract_eppd_nested(self):
        """Extract per-contract eppd from nested format."""
        result = _get_per_contract_eppd(GBT_PROFILE)
        assert result["suit"] == 0.827
        assert result["high"] == 0.333
        assert result["low"] == -0.041

    def test_get_per_contract_eppd_flat(self):
        """Extract per-contract eppd from flat key format."""
        profile = {
            "net_eppd_suit": 1.0,
            "net_eppd_high": 0.5,
            "net_eppd_low": -0.1,
        }
        result = _get_per_contract_eppd(profile)
        assert result["suit"] == 1.0
        assert result["high"] == 0.5
        assert result["low"] == -0.1

    def test_get_per_contract_eppd_empty(self):
        """Empty profile returns empty dict."""
        result = _get_per_contract_eppd({})
        assert result == {}

    def test_get_seed_deltas_explicit(self):
        """Extract seed deltas from explicit key."""
        result = _get_seed_deltas(GBT_PROFILE)
        assert result == [0.595, 0.557, 0.558]

    def test_get_seed_deltas_from_seeds_list(self):
        """Extract seed deltas from seeds list of dicts."""
        profile = {
            "seeds": [
                {"net_eppd_delta": 0.5},
                {"net_eppd_delta": 0.6},
            ]
        }
        result = _get_seed_deltas(profile)
        assert result == [0.5, 0.6]

    def test_get_seed_deltas_empty(self):
        """Empty profile returns empty list."""
        result = _get_seed_deltas({})
        assert result == []

    def test_extract_strategy_name_id(self):
        """Extract name from strategy_id."""
        assert _extract_strategy_name({"strategy_id": "foo"}) == "foo"

    def test_extract_strategy_name_name(self):
        """Extract name from name key."""
        assert _extract_strategy_name({"name": "bar"}) == "bar"

    def test_extract_strategy_name_priority(self):
        """strategy_id takes priority over name."""
        profile = {"strategy_id": "primary", "name": "secondary"}
        assert _extract_strategy_name(profile) == "primary"
