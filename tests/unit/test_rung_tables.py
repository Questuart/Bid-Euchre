"""Tests for canonical rung table generation.

Covers:
- CSV schema validation for all 11 canonical tables
- Table generation from fixture data
- Full pipeline smoke test
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

# Resolve fixture directory
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "arc_d_v2"

from bid_euchre.arc_d_v2.tables import (
    _merge_comparator_cis,
    _merge_h2h_batteries,
    _per_seed_sanity_comparator,
    _per_seed_sanity_h2h,
    generate_all_tables,
    generate_artifact_inventory,
    generate_behavior_by_bid_type,
    generate_behavior_by_contract,
    generate_behavior_summary,
    generate_comparator_rankings,
    generate_cross_rung_deltas,
    generate_data_sanity,
    generate_dataset_provenance,
    generate_h2h_delta_matrix,
    generate_hypothesis_outcomes,
    generate_model_performance,
    generate_rung_model_spec,
    generate_sanity_bounds_check,
    generate_seed_sanity_table,
)

# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────


def _load_fixture_json(name: str) -> dict:
    """Load a fixture JSON file."""
    path = FIXTURES_DIR / name
    assert path.exists(), f"Fixture not found: {path}"
    with open(path) as f:
        return json.load(f)


# ──────────────────────────────────────────────
#  Schema tests (parametrized)
# ──────────────────────────────────────────────

# Expected columns for each canonical CSV
EXPECTED_SCHEMAS = {
    "comparator_rankings": [
        "model",
        "facet",
        "net_eppd",
        "ci_low",
        "ci_high",
        "bid_rate",
        "make_rate",
        "net_cvar_5",
        "rank",
    ],
    "h2h_delta_matrix": [
        "model_a",
        "model_b",
        "facet",
        "net_eppd_delta",
        "ci_low",
        "ci_high",
        "win_rate_a",
        "deals_total",
    ],
    "model_performance": [
        "model",
        "contract",
        "r_squared",
        "mae",
        "n_train",
        "n_val",
    ],
    "behavior_summary": [
        "model",
        "net_eppd",
        "eppd",
        "bid_rate",
        "make_rate",
        "cvar_5",
        "net_cvar_5",
        "source",
    ],
    "behavior_by_contract": [
        "model",
        "contract",
        "net_eppd",
        "bid_rate",
        "make_rate",
        "source",
    ],
    "sanity_bounds_check": [
        "model",
        "check_name",
        "value",
        "lower_bound",
        "upper_bound",
        "status",
    ],
    "hypothesis_outcomes": [
        "hypothesis_id",
        "description",
        "status",
        "evidence",
        "notes",
    ],
    "rung_model_spec": [
        "model",
        "class_name",
        "trainable",
        "model_class",
        "feature_set",
        "category",
        "artifact_path",
    ],
    "cross_rung_deltas": [
        "model",
        "rung",
        "pooled_delta",
        "suit_delta",
        "high_delta",
        "low_delta",
        "ci_low",
        "ci_high",
    ],
    "dataset_provenance": [
        "dataset_name",
        "path",
        "n_rows",
        "seed",
        "sha256",
        "model_class",
    ],
    "artifact_inventory": [
        "artifact_name",
        "path",
        "schema_version",
        "model_class",
        "git_sha",
    ],
    "data_sanity": [
        "check_name",
        "scope",
        "value",
        "threshold",
        "status",
        "detail",
    ],
}


@pytest.fixture
def comparator_cis():
    return _load_fixture_json("comparator_cis.json")


@pytest.fixture
def h2h_battery():
    return _load_fixture_json("h2h_battery.json")


@pytest.fixture
def roster():
    return _load_fixture_json("roster.json")


@pytest.fixture
def training_artifacts():
    return {
        "ols": _load_fixture_json("training_artifact_ols.json"),
        "gbt": _load_fixture_json("training_artifact_gbt.json"),
    }


class TestComparatorRankings:
    def test_schema(self, comparator_cis):
        df = generate_comparator_rankings(comparator_cis)
        assert list(df.columns) == EXPECTED_SCHEMAS["comparator_rankings"]

    def test_row_count_pooled_only(self, comparator_cis):
        df = generate_comparator_rankings(comparator_cis)
        n_bidders = len(comparator_cis["bidders"])
        assert len(df) == n_bidders
        assert (df["facet"] == "pooled").all()

    def test_ranking_order(self, comparator_cis):
        df = generate_comparator_rankings(comparator_cis)
        pooled = df[df["facet"] == "pooled"]
        assert pooled["rank"].tolist() == list(range(1, len(pooled) + 1))

    def test_per_contract_faceting(self, comparator_cis):
        """When bidders_by_contract is present, per-facet rows are emitted."""
        enriched = dict(comparator_cis)
        enriched["bidders_by_contract"] = {
            "suit": {
                "gbt_av": {
                    "net_eppd": 2.5,
                    "net_eppd_ci": [2.5, 2.0, 3.0],
                    "bid_rate": 0.50,
                    "make_rate": 0.70,
                    "net_cvar_5": -2.0,
                },
                "selected_ols_av": {
                    "net_eppd": 1.8,
                    "net_eppd_ci": [1.8, 1.3, 2.3],
                    "bid_rate": 0.40,
                    "make_rate": 0.60,
                    "net_cvar_5": -3.0,
                },
            },
        }
        df = generate_comparator_rankings(enriched)
        n_bidders = len(comparator_cis["bidders"])
        assert len(df) == n_bidders + 2
        assert set(df["facet"].unique()) == {"pooled", "suit"}
        suit_rows = df[df["facet"] == "suit"]
        assert suit_rows.iloc[0]["model"] == "gbt_av"
        assert suit_rows.iloc[0]["rank"] == 1


class TestH2HDeltaMatrix:
    def test_schema(self, h2h_battery):
        df = generate_h2h_delta_matrix(h2h_battery)
        assert list(df.columns) == EXPECTED_SCHEMAS["h2h_delta_matrix"]

    def test_row_count(self, h2h_battery):
        df = generate_h2h_delta_matrix(h2h_battery)
        n_cells = len(h2h_battery["cells"])
        assert len(df) == n_cells


class TestModelPerformance:
    def test_schema(self, training_artifacts):
        df = generate_model_performance(training_artifacts)
        assert list(df.columns) == EXPECTED_SCHEMAS["model_performance"]

    def test_has_all_contracts(self, training_artifacts):
        df = generate_model_performance(training_artifacts)
        for model_name in training_artifacts:
            model_contracts = set(df[df["model"] == model_name]["contract"].tolist())
            expected = set(training_artifacts[model_name]["models"].keys())
            assert model_contracts == expected

    def test_r2_dtype(self, training_artifacts):
        df = generate_model_performance(training_artifacts)
        assert df["r_squared"].dtype in ("float64", "float32")


class TestBehaviorSummary:
    def test_schema(self, comparator_cis, h2h_battery):
        df = generate_behavior_summary(comparator_cis, h2h_battery)
        assert list(df.columns) == EXPECTED_SCHEMAS["behavior_summary"]

    def test_has_comparator_rows(self, comparator_cis):
        df = generate_behavior_summary(comparator_cis, None)
        comp_rows = df[df["source"] == "comparator"]
        assert len(comp_rows) == len(comparator_cis["bidders"])


class TestBehaviorByContract:
    def test_schema(self, comparator_cis):
        df = generate_behavior_by_contract(comparator_cis)
        assert list(df.columns) == EXPECTED_SCHEMAS["behavior_by_contract"]


class TestSanityBoundsCheck:
    def test_schema(self, comparator_cis, training_artifacts):
        df = generate_sanity_bounds_check(comparator_cis, training_artifacts)
        assert list(df.columns) == EXPECTED_SCHEMAS["sanity_bounds_check"]

    def test_all_pass(self, comparator_cis, training_artifacts):
        df = generate_sanity_bounds_check(comparator_cis, training_artifacts)
        assert (df["status"] == "PASS").all()


class TestHypothesisOutcomes:
    def test_schema(self):
        df = generate_hypothesis_outcomes()
        assert list(df.columns) == EXPECTED_SCHEMAS["hypothesis_outcomes"]

    def test_empty(self):
        df = generate_hypothesis_outcomes()
        assert len(df) == 0


class TestRungModelSpec:
    def test_schema(self, roster):
        df = generate_rung_model_spec(roster)
        assert list(df.columns) == EXPECTED_SCHEMAS["rung_model_spec"]

    def test_has_anchor(self, roster):
        df = generate_rung_model_spec(roster)
        assert "anchor" in df["category"].values


class TestCrossRungDeltas:
    def test_schema(self):
        df = generate_cross_rung_deltas()
        assert list(df.columns) == EXPECTED_SCHEMAS["cross_rung_deltas"]


class TestDatasetProvenance:
    def test_schema(self, training_artifacts):
        df = generate_dataset_provenance(training_artifacts)
        assert list(df.columns) == EXPECTED_SCHEMAS["dataset_provenance"]


class TestArtifactInventory:
    def test_schema(self, training_artifacts, roster):
        df = generate_artifact_inventory(training_artifacts, roster, FIXTURES_DIR)
        assert list(df.columns) == EXPECTED_SCHEMAS["artifact_inventory"]


class TestDataSanity:
    def test_schema(self, h2h_battery, comparator_cis, training_artifacts):
        df = generate_data_sanity(h2h_battery, comparator_cis, training_artifacts)
        assert list(df.columns) == EXPECTED_SCHEMAS["data_sanity"]

    def test_has_checks(self, h2h_battery, comparator_cis, training_artifacts):
        df = generate_data_sanity(h2h_battery, comparator_cis, training_artifacts)
        assert len(df) > 0


class TestFullPipeline:
    """Smoke test: run generate_all_tables on fixture data."""

    def test_generates_all_tables(self, tmp_path):
        output_dir = tmp_path / "tables"
        generated = generate_all_tables(FIXTURES_DIR, output_dir)

        assert (
            len(generated) >= 11
        ), f"Generated only {len(generated)} tables: {generated}"

        for csv_name in generated:
            csv_path = output_dir / csv_name
            assert csv_path.exists(), f"Missing: {csv_path}"
            assert csv_path.stat().st_size > 0, f"Empty: {csv_path}"

    def test_csv_schemas_match(self, tmp_path):
        """Verify all generated CSVs match expected schemas."""
        output_dir = tmp_path / "tables"
        generate_all_tables(FIXTURES_DIR, output_dir)

        for table_name, expected_cols in EXPECTED_SCHEMAS.items():
            csv_path = output_dir / f"{table_name}.csv"
            if not csv_path.exists():
                continue
            df = pd.read_csv(csv_path)
            assert list(df.columns) == expected_cols, (
                f"{table_name}.csv columns mismatch: "
                f"got {list(df.columns)}, expected {expected_cols}"
            )


# ──────────────────────────────────────────────
#  Multi-seed merge tests
# ──────────────────────────────────────────────


def _make_h2h_battery(seed, delta_a_vs_b, deals=100):
    """Create a minimal H2H battery fixture with one cross-matchup cell."""
    return {
        "schema": "h2h_battery_v2",
        "mode": "QUICK",
        "seed": seed,
        "n_per": deals,
        "roster": ["model_a", "model_b"],
        "cells": {
            "model_a_vs_model_b": {
                "bidder_a": "model_a",
                "bidder_b": "model_b",
                "net_eppd_delta": delta_a_vs_b,
                "net_eppd_a": delta_a_vs_b,
                "net_eppd_b": -delta_a_vs_b,
                "ci_low": delta_a_vs_b - 0.5,
                "ci_high": delta_a_vs_b + 0.5,
                "win_rate_a": 0.55,
                "abs_net_eppd_team0": 3.0 + delta_a_vs_b / 2,
                "abs_net_eppd_team1": 3.0 - delta_a_vs_b / 2,
                "cvar_5": -2.0,
                "fullgame_eppd": None,
                "deals_total": deals,
                "pair_deals": True,
                "matchup_id": "model_a_vs_model_b",
            }
        },
    }


def _make_comparator_cis(seed, net_eppd_a, net_eppd_b, deals=100):
    """Create a minimal comparator CIs fixture."""
    return {
        "schema": "comparator_cis_v1",
        "seed": seed,
        "n_bootstrap": 1000,
        "ranked_order": ["model_a", "model_b"]
        if net_eppd_a >= net_eppd_b
        else ["model_b", "model_a"],
        "bidders": {
            "model_a": {
                "net_eppd": net_eppd_a,
                "eppd": net_eppd_a + 1.0,
                "bid_rate": 0.40,
                "make_rate": 0.65,
                "cvar_5": -1.5,
                "net_cvar_5": -3.0,
                "deals_total": deals,
                "hands_with_bids": int(deals * 0.4),
                "net_eppd_ci": [net_eppd_a, net_eppd_a - 0.3, net_eppd_a + 0.3],
                "eppd_ci": [
                    net_eppd_a + 1.0,
                    net_eppd_a + 0.7,
                    net_eppd_a + 1.3,
                ],
            },
            "model_b": {
                "net_eppd": net_eppd_b,
                "eppd": net_eppd_b + 1.0,
                "bid_rate": 0.35,
                "make_rate": 0.60,
                "cvar_5": -2.0,
                "net_cvar_5": -4.0,
                "deals_total": deals,
                "hands_with_bids": int(deals * 0.35),
                "net_eppd_ci": [net_eppd_b, net_eppd_b - 0.3, net_eppd_b + 0.3],
                "eppd_ci": [
                    net_eppd_b + 1.0,
                    net_eppd_b + 0.7,
                    net_eppd_b + 1.3,
                ],
            },
        },
    }


class TestMergeH2HBatteries:
    """Tests for _merge_h2h_batteries deal-count-weighted pooling."""

    def test_single_battery_passthrough(self):
        """Single battery returns unchanged."""
        battery = _make_h2h_battery(42, 1.0)
        merged = _merge_h2h_batteries([battery])
        assert merged is battery  # Exact same object

    def test_weighted_pooling_equal_deals(self):
        """With equal deal counts, weighted mean = simple average."""
        b1 = _make_h2h_battery(42, 1.0, deals=100)
        b2 = _make_h2h_battery(123, 2.0, deals=100)
        merged = _merge_h2h_batteries([b1, b2])
        cell = merged["cells"]["model_a_vs_model_b"]
        assert cell["net_eppd_delta"] == pytest.approx(1.5, abs=1e-4)
        assert cell["deals_total"] == 200
        assert cell["ci_method"] == "seed_averaged"

    def test_weighted_pooling_unequal_deals(self):
        """With unequal deal counts, weighted mean differs from simple avg."""
        b1 = _make_h2h_battery(42, 1.0, deals=100)
        b2 = _make_h2h_battery(123, 3.0, deals=300)
        merged = _merge_h2h_batteries([b1, b2])
        cell = merged["cells"]["model_a_vs_model_b"]
        # Weighted: (1.0*100 + 3.0*300) / (100+300) = 1000/400 = 2.5
        assert cell["net_eppd_delta"] == pytest.approx(2.5, abs=1e-4)
        # Simple average would be 2.0 -- verify it's NOT that
        assert cell["net_eppd_delta"] != pytest.approx(2.0, abs=0.01)
        assert cell["deals_total"] == 400

    def test_ci_averaged_not_weighted(self):
        """CIs are averaged across seeds (not deal-count-weighted)."""
        b1 = _make_h2h_battery(42, 1.0, deals=100)
        b2 = _make_h2h_battery(123, 3.0, deals=300)
        merged = _merge_h2h_batteries([b1, b2])
        cell = merged["cells"]["model_a_vs_model_b"]
        # ci_low from b1 = 0.5 (1.0-0.5), from b2 = 2.5 (3.0-0.5)
        # average = 1.5
        assert cell["ci_low"] == pytest.approx(1.5, abs=1e-4)

    def test_seeds_merged_count(self):
        """Merged output records number of seeds."""
        b1 = _make_h2h_battery(42, 1.0)
        b2 = _make_h2h_battery(123, 1.5)
        b3 = _make_h2h_battery(456, 2.0)
        merged = _merge_h2h_batteries([b1, b2, b3])
        assert merged["seeds_merged"] == 3

    def test_per_contract_merge(self):
        """Per-contract data is merged with weighted pooling."""
        b1 = _make_h2h_battery(42, 1.0, deals=100)
        b1["cells"]["model_a_vs_model_b"]["by_contract"] = {
            "suit": {
                "net_eppd_delta": 1.5,
                "ci_low": 0.5,
                "ci_high": 2.5,
                "win_rate_a": 0.60,
                "deals_total": 40,
            }
        }
        b2 = _make_h2h_battery(123, 2.0, deals=100)
        b2["cells"]["model_a_vs_model_b"]["by_contract"] = {
            "suit": {
                "net_eppd_delta": 2.5,
                "ci_low": 1.5,
                "ci_high": 3.5,
                "win_rate_a": 0.70,
                "deals_total": 60,
            }
        }
        merged = _merge_h2h_batteries([b1, b2])
        suit = merged["cells"]["model_a_vs_model_b"]["by_contract"]["suit"]
        # Weighted: (1.5*40 + 2.5*60) / 100 = 210/100 = 2.1
        assert suit["net_eppd_delta"] == pytest.approx(2.1, abs=1e-4)
        assert suit["deals_total"] == 100
        assert suit["ci_method"] == "seed_averaged"


class TestMergeComparatorCIs:
    """Tests for _merge_comparator_cis deal-count-weighted pooling."""

    def test_single_cis_passthrough(self):
        """Single CIs dict returns unchanged."""
        cis = _make_comparator_cis(42, 2.0, 1.0)
        merged = _merge_comparator_cis([cis])
        assert merged is cis

    def test_weighted_pooling_equal_deals(self):
        """With equal deals, weighted = simple average."""
        c1 = _make_comparator_cis(42, 2.0, 1.0, deals=100)
        c2 = _make_comparator_cis(123, 3.0, 1.5, deals=100)
        merged = _merge_comparator_cis([c1, c2])
        assert merged["bidders"]["model_a"]["net_eppd"] == pytest.approx(2.5, abs=1e-4)
        assert merged["bidders"]["model_b"]["net_eppd"] == pytest.approx(1.25, abs=1e-4)

    def test_weighted_pooling_unequal_deals(self):
        """With unequal deals, weighted mean != simple average."""
        c1 = _make_comparator_cis(42, 2.0, 1.0, deals=100)
        c2 = _make_comparator_cis(123, 4.0, 2.0, deals=300)
        merged = _merge_comparator_cis([c1, c2])
        # Weighted: (2.0*100 + 4.0*300) / 400 = 1400/400 = 3.5
        assert merged["bidders"]["model_a"]["net_eppd"] == pytest.approx(3.5, abs=1e-4)
        # Simple avg would be 3.0
        assert merged["bidders"]["model_a"]["net_eppd"] != pytest.approx(3.0, abs=0.01)

    def test_re_ranking(self):
        """Merged output re-ranks by pooled net_eppd."""
        c1 = _make_comparator_cis(42, 2.0, 3.0, deals=100)  # b > a on seed 42
        c2 = _make_comparator_cis(123, 2.0, 3.0, deals=100)
        merged = _merge_comparator_cis([c1, c2])
        # model_b has higher net_eppd
        assert merged["ranked_order"][0] == "model_b"
        assert merged["ranked_order"][1] == "model_a"

    def test_ci_method_marker(self):
        """Merged bidders carry ci_method = 'seed_averaged'."""
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        c2 = _make_comparator_cis(123, 2.5, 1.2)
        merged = _merge_comparator_cis([c1, c2])
        for bidder in merged["bidders"].values():
            assert bidder["ci_method"] == "seed_averaged"

    def test_ci_arrays_averaged(self):
        """CI arrays [point, low, high] are averaged element-wise."""
        c1 = _make_comparator_cis(42, 2.0, 1.0, deals=100)
        c2 = _make_comparator_cis(123, 3.0, 1.5, deals=100)
        merged = _merge_comparator_cis([c1, c2])
        ci = merged["bidders"]["model_a"]["net_eppd_ci"]
        # c1 ci = [2.0, 1.7, 2.3], c2 ci = [3.0, 2.7, 3.3]
        # avg = [2.5, 2.2, 2.8]
        assert ci[0] == pytest.approx(2.5, abs=1e-4)
        assert ci[1] == pytest.approx(2.2, abs=1e-4)
        assert ci[2] == pytest.approx(2.8, abs=1e-4)


class TestPooledVsAverageCIs:
    """Verify that pooled weighted merge produces different results than naive averaging."""

    def test_h2h_weighted_differs_from_naive_avg(self):
        """Weighted pooling with unequal deal counts differs from naive avg."""
        b1 = _make_h2h_battery(42, 1.0, deals=50)
        b2 = _make_h2h_battery(123, 3.0, deals=150)
        merged = _merge_h2h_batteries([b1, b2])
        cell = merged["cells"]["model_a_vs_model_b"]
        # Naive avg would be 2.0, weighted = (50+450)/200 = 2.5
        naive_avg = (1.0 + 3.0) / 2
        assert cell["net_eppd_delta"] != pytest.approx(naive_avg, abs=0.01)
        expected = (1.0 * 50 + 3.0 * 150) / 200
        assert cell["net_eppd_delta"] == pytest.approx(expected, abs=1e-4)

    def test_comparator_weighted_differs_from_naive_avg(self):
        """Weighted pooling with unequal deal counts differs from naive avg."""
        c1 = _make_comparator_cis(42, 1.0, 0.5, deals=50)
        c2 = _make_comparator_cis(123, 3.0, 1.5, deals=150)
        merged = _merge_comparator_cis([c1, c2])
        naive_avg = (1.0 + 3.0) / 2
        expected = (1.0 * 50 + 3.0 * 150) / 200
        assert merged["bidders"]["model_a"]["net_eppd"] != pytest.approx(
            naive_avg, abs=0.01
        )
        assert merged["bidders"]["model_a"]["net_eppd"] == pytest.approx(
            expected, abs=1e-4
        )


# ──────────────────────────────────────────────
#  Per-seed sanity check tests
# ──────────────────────────────────────────────


class TestPerSeedSanityH2H:
    """Tests for H2H per-seed outlier and rank reversal checks."""

    def test_no_warnings_single_seed(self):
        """Single seed produces no warnings."""
        b1 = _make_h2h_battery(42, 1.0)
        assert _per_seed_sanity_h2h([b1]) == []

    def test_no_warnings_consistent_seeds(self):
        """Consistent seeds produce no warnings."""
        b1 = _make_h2h_battery(42, 1.0, deals=100)
        b2 = _make_h2h_battery(123, 1.1, deals=100)
        b3 = _make_h2h_battery(456, 0.9, deals=100)
        warnings = _per_seed_sanity_h2h([b1, b2, b3])
        # Small variation shouldn't trigger outlier or rank reversal
        rank_reversals = [w for w in warnings if w["check"] == "h2h_rank_reversal"]
        assert len(rank_reversals) == 0

    def test_rank_reversal_detected(self):
        """Sign flip across seeds triggers rank_reversal warning."""
        b1 = _make_h2h_battery(42, 1.0)  # model_a > model_b
        b2 = _make_h2h_battery(123, -0.5)  # model_a < model_b
        warnings = _per_seed_sanity_h2h([b1, b2])
        reversals = [w for w in warnings if w["check"] == "h2h_rank_reversal"]
        assert len(reversals) == 1
        assert "model_a_vs_model_b" in reversals[0]["matchup_id"]

    def test_outlier_detected(self):
        """Extreme seed outlier triggers warning (uses MAD for small-n robustness)."""
        b1 = _make_h2h_battery(42, 1.0)
        b2 = _make_h2h_battery(123, 1.1)
        b3 = _make_h2h_battery(456, 10.0)  # Extreme outlier
        warnings = _per_seed_sanity_h2h([b1, b2, b3])
        outliers = [w for w in warnings if w["check"] == "h2h_seed_outlier"]
        assert len(outliers) >= 1
        assert any("456" in w["detail"] for w in outliers)


class TestPerSeedSanityComparator:
    """Tests for comparator per-seed outlier and rank reversal checks."""

    def test_no_warnings_single_seed(self):
        """Single seed produces no warnings."""
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        assert _per_seed_sanity_comparator([c1]) == []

    def test_rank_reversal_detected(self):
        """Ranking flip across seeds triggers warning."""
        c1 = _make_comparator_cis(42, 2.0, 1.0)  # a > b
        c2 = _make_comparator_cis(123, 0.5, 1.5)  # b > a
        warnings = _per_seed_sanity_comparator([c1, c2])
        reversals = [w for w in warnings if w["check"] == "comparator_rank_reversal"]
        assert len(reversals) >= 1

    def test_outlier_detected(self):
        """Extreme seed outlier triggers warning (uses MAD for small-n robustness)."""
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        c2 = _make_comparator_cis(123, 2.1, 1.1)
        c3 = _make_comparator_cis(456, 10.0, 1.0)  # a is extreme outlier
        warnings = _per_seed_sanity_comparator([c1, c2, c3])
        outliers = [w for w in warnings if w["check"] == "comparator_seed_outlier"]
        assert len(outliers) >= 1
        assert any("456" in w["detail"] for w in outliers)


class TestSeedSanityTable:
    """Tests for the combined seed_sanity table generator."""

    def test_schema(self):
        """seed_sanity.csv has expected columns."""
        b1 = _make_h2h_battery(42, 1.0)
        b2 = _make_h2h_battery(123, -0.5)
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        c2 = _make_comparator_cis(123, 0.5, 1.5)
        df = generate_seed_sanity_table([b1, b2], [c1, c2])
        assert list(df.columns) == [
            "check",
            "scope",
            "matchup_or_model",
            "detail",
        ]
        assert len(df) > 0

    def test_empty_for_single_seed(self):
        """Single seed produces empty table."""
        b1 = _make_h2h_battery(42, 1.0)
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        df = generate_seed_sanity_table([b1], [c1])
        assert len(df) == 0

    def test_scopes(self):
        """Warnings are categorized by scope (h2h / comparator)."""
        b1 = _make_h2h_battery(42, 1.0)
        b2 = _make_h2h_battery(123, -0.5)
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        c2 = _make_comparator_cis(123, 0.5, 1.5)
        df = generate_seed_sanity_table([b1, b2], [c1, c2])
        assert "h2h" in df["scope"].values
        assert "comparator" in df["scope"].values


class TestMultiSeedPipeline:
    """Integration tests for multi-seed path through generate_all_tables."""

    def test_multi_seed_generates_seed_sanity(self, tmp_path):
        """When seeds=[42, 123], seed_sanity.csv is generated."""
        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()

        # Create two battery files with different seeds
        b1 = _make_h2h_battery(42, 1.0)
        b2 = _make_h2h_battery(123, -0.5)  # rank reversal
        (rung_dir / "h2h_battery_quick_42.json").write_text(json.dumps(b1))
        (rung_dir / "h2h_battery_quick_123.json").write_text(json.dumps(b2))

        # Create comparator CIs
        c1 = _make_comparator_cis(42, 2.0, 1.0)
        c2 = _make_comparator_cis(123, 0.5, 1.5)
        (rung_dir / "comparator_cis_rung_42.json").write_text(json.dumps(c1))
        (rung_dir / "comparator_cis_rung_123.json").write_text(json.dumps(c2))

        output_dir = tmp_path / "tables"
        generated = generate_all_tables(
            rung_dir, output_dir, mode="quick", seeds=[42, 123]
        )
        assert "seed_sanity.csv" in generated

    def test_single_seed_no_seed_sanity(self, tmp_path):
        """When seeds=[42], seed_sanity.csv is NOT generated."""
        output_dir = tmp_path / "tables"
        generated = generate_all_tables(FIXTURES_DIR, output_dir, seeds=[42])
        assert "seed_sanity.csv" not in generated


# ──────────────────────────────────────────────
#  Bid-type faceting tests
# ──────────────────────────────────────────────


class TestBehaviorByBidType:
    """Tests for the behavior_by_bid_type.csv table generation."""

    def test_r0_style_only_regular_rows(self):
        """R0-R2 data (no bidders_by_bid_type) produces only 'regular' rows."""
        comparator = {
            "bidders": {
                "model_a": {
                    "net_eppd": 1.5,
                    "bid_rate": 0.6,
                    "make_rate": 0.7,
                    "hands_with_bids": 120,
                },
                "model_b": {
                    "net_eppd": 0.8,
                    "bid_rate": 0.5,
                    "make_rate": 0.6,
                    "hands_with_bids": 100,
                },
            },
        }
        df = generate_behavior_by_bid_type(comparator_cis=comparator)
        assert len(df) == 2
        assert set(df["bid_type"].unique()) == {"regular"}
        assert set(df["model"].unique()) == {"model_a", "model_b"}

    def test_r3_style_has_regular_moon_loner(self):
        """R3 data with bidders_by_bid_type produces regular + moon + loner rows."""
        comparator = {
            "bidders": {
                "gbt": {"net_eppd": 2.0, "bid_rate": 0.7, "make_rate": 0.8},
            },
            "bidders_by_bid_type": {
                "regular": {
                    "gbt": {
                        "net_eppd": 1.8,
                        "bid_rate": 0.6,
                        "make_rate": 0.75,
                        "hands_with_bids": 100,
                    },
                },
                "moon": {
                    "gbt": {
                        "net_eppd": 5.0,
                        "bid_rate": 0.08,
                        "make_rate": 0.5,
                        "hands_with_bids": 12,
                    },
                },
                "loner": {
                    "gbt": {
                        "net_eppd": 10.0,
                        "bid_rate": 0.02,
                        "make_rate": 0.3,
                        "hands_with_bids": 3,
                    },
                },
            },
        }
        df = generate_behavior_by_bid_type(comparator_cis=comparator)
        assert len(df) == 3
        assert set(df["bid_type"].unique()) == {"regular", "moon", "loner"}

    def test_schema_columns(self):
        """Output has expected columns."""
        comparator = {
            "bidders": {
                "model_a": {
                    "net_eppd": 1.0,
                    "bid_rate": 0.5,
                    "make_rate": 0.6,
                    "hands_with_bids": 50,
                },
            },
        }
        df = generate_behavior_by_bid_type(comparator_cis=comparator)
        expected_cols = {
            "model",
            "bid_type",
            "count",
            "bid_rate",
            "make_rate",
            "mean_net_points",
            "source",
        }
        assert set(df.columns) == expected_cols

    def test_h2h_self_play_by_bid_type(self):
        """H2H self-play with by_bid_type data emits per-type rows."""
        h2h = {
            "cells": {
                "gbt_vs_gbt": {
                    "bidder_a": "gbt",
                    "bidder_b": "gbt",
                    "deals_total": 200,
                    "by_bid_type": {
                        "regular": {
                            "net_eppd_delta": 0.1,
                            "win_rate_a": 0.5,
                            "deals_total": 180,
                        },
                        "moon": {
                            "net_eppd_delta": 2.0,
                            "win_rate_a": 0.6,
                            "deals_total": 20,
                        },
                    },
                },
            },
        }
        df = generate_behavior_by_bid_type(h2h_battery=h2h)
        assert len(df) == 2
        assert set(df["bid_type"].unique()) == {"regular", "moon"}
        assert all(df["source"] == "h2h_self_play")

    def test_h2h_no_bid_type_data_falls_back(self):
        """H2H self-play without by_bid_type falls back to 'regular' row."""
        h2h = {
            "cells": {
                "ols_vs_ols": {
                    "bidder_a": "ols",
                    "bidder_b": "ols",
                    "deals_total": 100,
                    "bid_rate_a": 0.5,
                    "make_rate_a": 0.6,
                    "fullgame_eppd": 4.5,
                },
            },
        }
        df = generate_behavior_by_bid_type(h2h_battery=h2h)
        assert len(df) == 1
        assert df.iloc[0]["bid_type"] == "regular"


class TestH2HDeltaMatrixBidType:
    """Tests that h2h_delta_matrix includes bid_type facet rows."""

    def test_by_bid_type_rows_present(self):
        """H2H battery with by_bid_type produces bid_type:* facet rows."""
        h2h = {
            "cells": {
                "a_vs_b": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_b",
                    "net_eppd_delta": 0.5,
                    "ci_low": 0.1,
                    "ci_high": 0.9,
                    "win_rate_a": 0.55,
                    "deals_total": 1000,
                    "by_bid_type": {
                        "regular": {
                            "net_eppd_delta": 0.4,
                            "ci_low": 0.05,
                            "ci_high": 0.75,
                            "win_rate_a": 0.54,
                            "deals_total": 900,
                        },
                        "moon": {
                            "net_eppd_delta": 2.0,
                            "ci_low": 0.5,
                            "ci_high": 3.5,
                            "win_rate_a": 0.7,
                            "deals_total": 100,
                        },
                    },
                },
            },
        }
        df = generate_h2h_delta_matrix(h2h)
        # Should have: 1 pooled + 2 bid_type facets
        assert len(df) == 3
        facets = set(df["facet"].unique())
        assert "pooled" in facets
        assert "bid_type:regular" in facets
        assert "bid_type:moon" in facets

    def test_no_bid_type_no_extra_rows(self):
        """H2H battery without by_bid_type produces only pooled row."""
        h2h = {
            "cells": {
                "a_vs_b": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_b",
                    "net_eppd_delta": 0.5,
                    "ci_low": 0.1,
                    "ci_high": 0.9,
                    "win_rate_a": 0.55,
                    "deals_total": 1000,
                },
            },
        }
        df = generate_h2h_delta_matrix(h2h)
        assert len(df) == 1
        assert df.iloc[0]["facet"] == "pooled"
