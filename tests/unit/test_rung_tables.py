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
    _EMPTY_SHA256,
    TIER_ANCHOR,
    TIER_HEURISTIC,
    TIER_SMART,
    _classify_tier,
    _extract_bid_levels,
    _extract_bid_levels_from_parquet,
    _extract_decision_comparison,
    _extract_disagreement_outcomes,
    _extract_feature_importance,
    _extract_feature_importances_flat,
    _extract_h2h_by_contract,
    _extract_outcome_distributions,
    _extract_outcome_distributions_from_parquet,
    _make_repo_relative,
    _merge_comparator_cis,
    _merge_h2h_batteries,
    _per_seed_sanity_comparator,
    _per_seed_sanity_h2h,
    generate_all_tables,
    generate_artifact_inventory,
    generate_behavior_by_bid_type,
    generate_behavior_by_contract,
    generate_behavior_summary,
    generate_chart_data,
    generate_comparator_rankings,
    generate_cross_rung_deltas,
    generate_cross_rung_progression,
    generate_data_sanity,
    generate_dataset_provenance,
    generate_h2h_delta_matrix,
    generate_h2h_tier_summary,
    generate_hypothesis_outcomes,
    generate_model_eval_csvs,
    generate_model_performance,
    generate_rung_model_spec,
    generate_sanity_bounds_check,
    generate_seat_balance_csv,
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
        "pass_rate",
        "make_rate",
        "cvar_5",
        "net_cvar_5",
        "mix_suit",
        "mix_high",
        "mix_low",
        "source",
    ],
    "behavior_by_contract": [
        "model",
        "contract",
        "net_eppd",
        "bid_rate",
        "pass_rate",
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
    "h2h_tier_summary": [
        "model",
        "tier",
        "mean_delta",
        "mean_win_rate",
        "n_opponents",
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

    def test_row_count_with_facets(self, comparator_cis):
        """Pooled rows always present; per-contract rows when bidders_by_contract exists."""
        df = generate_comparator_rankings(comparator_cis)
        n_bidders = len(comparator_cis["bidders"])
        pooled = df[df["facet"] == "pooled"]
        assert len(pooled) == n_bidders
        # With bidders_by_contract in fixture, also expect per-contract rows
        n_contracts = len(comparator_cis.get("bidders_by_contract", {}))
        assert len(df) == n_bidders * (1 + n_contracts)

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
    def test_schema_empty(self):
        df = generate_hypothesis_outcomes()
        assert list(df.columns) == EXPECTED_SCHEMAS["hypothesis_outcomes"]
        assert len(df) == 0

    def test_schema_with_advance_check(self):
        advance_check = {
            "hypothesis_checks": [
                {
                    "id": "H1",
                    "description": "Test hypothesis",
                    "pass": True,
                    "observed": 1.5,
                    "expected_bound": "> 0.5",
                    "surprise_hit": False,
                    "error": None,
                },
                {
                    "id": "H2",
                    "description": "Failed hypothesis",
                    "pass": False,
                    "observed": -0.3,
                    "expected_bound": ">= 0.0",
                    "surprise_hit": True,
                    "error": None,
                },
            ],
        }
        df = generate_hypothesis_outcomes(advance_check)
        assert list(df.columns) == EXPECTED_SCHEMAS["hypothesis_outcomes"]
        assert len(df) == 2
        assert df.iloc[0]["hypothesis_id"] == "H1"
        assert df.iloc[0]["status"] == "PASS"
        assert "1.5" in df.iloc[0]["evidence"]
        assert df.iloc[1]["status"] == "FAIL"
        assert "SURPRISE" in df.iloc[1]["notes"]

    def test_skipped_hypothesis_status(self):
        """Skipped hypotheses (excluded models) get status SKIP, not FAIL."""
        advance_check = {
            "hypothesis_checks": [
                {
                    "id": "H1",
                    "description": "Passing hypothesis",
                    "pass": True,
                    "observed": 1.5,
                    "expected_bound": "> 0.5",
                    "surprise_hit": False,
                    "error": None,
                },
                {
                    "id": "H5",
                    "description": "Skipped hypothesis",
                    "pass": False,
                    "observed": None,
                    "expected_bound": None,
                    "surprise_hit": False,
                    "error": None,
                    "skipped": True,
                    "note": "SKIP: model(s) selected_ols_av not in active roster",
                },
            ],
        }
        df = generate_hypothesis_outcomes(advance_check)
        assert len(df) == 2
        assert df.iloc[0]["status"] == "PASS"
        assert df.iloc[1]["status"] == "SKIP"
        assert "selected_ols_av" in df.iloc[1]["notes"]

    def test_no_overwrite_populated_csv(self, tmp_path):
        """generate_all_tables does not overwrite populated hypothesis_outcomes."""
        output_dir = tmp_path / "tables"
        output_dir.mkdir()

        # Pre-populate hypothesis_outcomes.csv with real data
        populated = output_dir / "hypothesis_outcomes.csv"
        populated.write_text(
            "hypothesis_id,description,status,evidence,notes\n"
            "H1,Test,PASS,observed=1.0,\n"
        )
        original_size = populated.stat().st_size

        # Run generate_all_tables with no advance_check available
        generate_all_tables(FIXTURES_DIR, output_dir)

        # Should NOT have been overwritten with empty stub
        assert populated.stat().st_size >= original_size
        assert "H1" in populated.read_text()


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


class TestH2HTierSummary:
    """Tests for h2h_tier_summary.csv generation."""

    def test_tier_classification(self):
        """Verify tier assignment for known models."""
        assert _classify_tier("full_ols_av") == "smart"
        assert _classify_tier("constrained_ols_av") == "smart"
        assert _classify_tier("selected_ols_av") == "smart"
        assert _classify_tier("selected_two_stage_av") == "smart"
        assert _classify_tier("anchor_hybrid_r0_full") == "anchor"
        assert _classify_tier("modeloespecifico") == "heuristic"
        assert _classify_tier("stricthellraiser") == "heuristic"
        assert _classify_tier("rankthetank") == "heuristic"
        assert _classify_tier("some_new_model") == "unknown"

    def test_tier_sets_non_overlapping(self):
        """Tier sets must not overlap."""
        assert TIER_SMART & TIER_ANCHOR == frozenset()
        assert TIER_SMART & TIER_HEURISTIC == frozenset()
        assert TIER_ANCHOR & TIER_HEURISTIC == frozenset()

    def test_smart_tier_mean_across_4_opponents(self):
        """Smart tier computes mean across 4 opponent models."""
        # Create a minimal h2h_delta_matrix with gbt_av vs 4 smart models
        rows = []
        smart_models = [
            "full_ols_av",
            "constrained_ols_av",
            "selected_ols_av",
            "selected_two_stage_av",
        ]
        deltas = [1.0, 2.0, 3.0, 4.0]
        win_rates = [0.6, 0.7, 0.8, 0.5]
        for model, delta, wr in zip(smart_models, deltas, win_rates):
            rows.append(
                {
                    "model_a": "gbt_av",
                    "model_b": model,
                    "facet": "pooled",
                    "net_eppd_delta": delta,
                    "ci_low": delta - 0.5,
                    "ci_high": delta + 0.5,
                    "win_rate_a": wr,
                    "deals_total": 2500,
                }
            )
        df_matrix = pd.DataFrame(rows)
        df = generate_h2h_tier_summary(df_matrix)

        gbt_smart = df[(df["model"] == "gbt_av") & (df["tier"] == "smart")]
        assert len(gbt_smart) == 1
        assert gbt_smart.iloc[0]["n_opponents"] == 4
        assert gbt_smart.iloc[0]["mean_delta"] == pytest.approx(2.5, abs=1e-3)
        assert gbt_smart.iloc[0]["mean_win_rate"] == pytest.approx(0.65, abs=1e-3)

    def test_schema(self):
        """Output has expected columns."""
        rows = [
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "pooled",
                "net_eppd_delta": 1.5,
                "ci_low": 1.0,
                "ci_high": 2.0,
                "win_rate_a": 0.6,
                "deals_total": 2500,
            },
        ]
        df = generate_h2h_tier_summary(pd.DataFrame(rows))
        assert list(df.columns) == EXPECTED_SCHEMAS["h2h_tier_summary"]

    def test_excludes_self_play(self):
        """Self-play rows (model_a == model_b) are excluded."""
        rows = [
            {
                "model_a": "gbt_av",
                "model_b": "gbt_av",
                "facet": "pooled",
                "net_eppd_delta": 0.0,
                "ci_low": -0.5,
                "ci_high": 0.5,
                "win_rate_a": 0.5,
                "deals_total": 2500,
            },
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "pooled",
                "net_eppd_delta": 1.5,
                "ci_low": 1.0,
                "ci_high": 2.0,
                "win_rate_a": 0.6,
                "deals_total": 2500,
            },
        ]
        df = generate_h2h_tier_summary(pd.DataFrame(rows))
        # Only the cross-matchup row should produce output
        assert len(df) == 1
        assert df.iloc[0]["model"] == "gbt_av"
        assert df.iloc[0]["tier"] == "smart"

    def test_excludes_non_pooled_facets(self):
        """Only pooled-facet rows are used for tier summary."""
        rows = [
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "pooled",
                "net_eppd_delta": 1.5,
                "ci_low": 1.0,
                "ci_high": 2.0,
                "win_rate_a": 0.6,
                "deals_total": 2500,
            },
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "suit",
                "net_eppd_delta": 2.0,
                "ci_low": 1.5,
                "ci_high": 2.5,
                "win_rate_a": 0.7,
                "deals_total": 2000,
            },
        ]
        df = generate_h2h_tier_summary(pd.DataFrame(rows))
        # Only pooled row should be used
        assert len(df) == 1
        assert df.iloc[0]["mean_delta"] == pytest.approx(1.5, abs=1e-3)

    def test_all_models_shown(self, h2h_battery):
        """All models from the battery appear in the tier summary."""
        h2h_matrix = generate_h2h_delta_matrix(h2h_battery)
        df = generate_h2h_tier_summary(h2h_matrix)
        # Every model that has cross-matchup rows should appear
        pooled_cross = h2h_matrix[
            (h2h_matrix["facet"] == "pooled")
            & (h2h_matrix["model_a"] != h2h_matrix["model_b"])
        ]
        expected_models = set(pooled_cross["model_a"].unique())
        actual_models = set(df["model"].unique())
        assert actual_models == expected_models

    def test_works_with_r0_r2_data(self):
        """R0-R2 data (no moon/loner) works correctly."""
        # Minimal R0-style battery with no bid_type facets
        rows = [
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "pooled",
                "net_eppd_delta": 1.3,
                "ci_low": 1.0,
                "ci_high": 1.6,
                "win_rate_a": 0.6,
                "deals_total": 2500,
            },
            {
                "model_a": "gbt_av",
                "model_b": "anchor_hybrid_r0_full",
                "facet": "pooled",
                "net_eppd_delta": 1.06,
                "ci_low": 0.8,
                "ci_high": 1.3,
                "win_rate_a": 0.53,
                "deals_total": 2500,
            },
            {
                "model_a": "gbt_av",
                "model_b": "modeloespecifico",
                "facet": "pooled",
                "net_eppd_delta": 0.63,
                "ci_low": 0.4,
                "ci_high": 0.85,
                "win_rate_a": 0.55,
                "deals_total": 2500,
            },
        ]
        df = generate_h2h_tier_summary(pd.DataFrame(rows))
        assert len(df) == 3
        tiers = set(df["tier"].unique())
        assert tiers == {"smart", "anchor", "heuristic"}

    def test_works_with_r3_bid_type_facets(self):
        """R3 data with bid_type:* facets are ignored (only pooled used)."""
        rows = [
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "pooled",
                "net_eppd_delta": 1.5,
                "ci_low": 1.0,
                "ci_high": 2.0,
                "win_rate_a": 0.6,
                "deals_total": 2500,
            },
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "bid_type:regular",
                "net_eppd_delta": 1.4,
                "ci_low": 0.9,
                "ci_high": 1.9,
                "win_rate_a": 0.59,
                "deals_total": 2400,
            },
            {
                "model_a": "gbt_av",
                "model_b": "full_ols_av",
                "facet": "bid_type:moon",
                "net_eppd_delta": 5.0,
                "ci_low": -5.0,
                "ci_high": 15.0,
                "win_rate_a": 0.7,
                "deals_total": 10,
            },
        ]
        df = generate_h2h_tier_summary(pd.DataFrame(rows))
        # Only the pooled row should count
        assert len(df) == 1
        assert df.iloc[0]["mean_delta"] == pytest.approx(1.5, abs=1e-3)


class TestFullPipeline:
    """Smoke test: run generate_all_tables on fixture data."""

    def test_generates_all_tables(self, tmp_path):
        output_dir = tmp_path / "tables"
        generated = generate_all_tables(FIXTURES_DIR, output_dir)

        assert (
            len(generated) >= 11
        ), f"Generated only {len(generated)} tables: {generated}"

        for csv_name in generated:
            if csv_name.startswith("chart_data/"):
                # chart_data CSVs live at output_dir.parent / chart_data/
                csv_path = output_dir.parent / csv_name
            else:
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
#  Dataset dirs parquet discovery tests
# ──────────────────────────────────────────────


class TestDatasetDirsDiscovery:
    """Tests for the dataset_dirs parameter in generate_all_tables."""

    def test_dataset_dirs_enables_parquet_outcome_distributions(self, tmp_path):
        """With dataset_dirs, outcome_distributions uses parquet (source=parquet)."""
        import shutil

        # Copy fixtures to rung_dir (JSON artifacts)
        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()
        for f in FIXTURES_DIR.glob("*.json"):
            shutil.copy2(f, rung_dir / f.name)

        # Create a dataset dir with action_value.parquet
        ds_dir = tmp_path / "datasets" / "seed_1001"
        ds_dir.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "hand_id": range(100),
                "deal_id": list(range(50)) * 2,
                "focal_seat": [0, 1, 2, 3] * 25,
                "action_type": ["bid"] * 80 + ["pass"] * 20,
                "contract_family": (["suit"] * 50 + ["high"] * 30 + ["low"] * 20),
                "bid_n": [6] * 100,
                "trump_suit": ["H"] * 100,
                "net_points": [2.0] * 100,
                "tricks_won": ([5, 6, 7, 4, 8, 3, 5, 6, 7, 5] * 10),
            }
        )
        parquet_path = ds_dir / "action_value.parquet"
        df.to_parquet(parquet_path)

        output_dir = tmp_path / "tables"
        generated = generate_all_tables(rung_dir, output_dir, dataset_dirs=[ds_dir])

        # Check outcome_distributions was generated
        assert "chart_data/outcome_distributions.csv" in generated

        # Verify it used parquet path (source=parquet, multiple tricks_won values)
        od_path = output_dir.parent / "chart_data" / "outcome_distributions.csv"
        od_df = pd.read_csv(od_path)
        assert "source" in od_df.columns
        assert (
            od_df["source"] == "parquet"
        ).all(), f"Expected source=parquet but got: {od_df['source'].unique()}"
        # Real parquet data should have multiple tricks_won values per contract
        suit_rows = od_df[od_df["contract"] == "suit"]
        assert (
            len(suit_rows) > 1
        ), f"Expected multiple histogram bins for suit, got {len(suit_rows)} rows"

    def test_without_dataset_dirs_no_parquet_outcome_distributions(self, tmp_path):
        """Without dataset_dirs and no matching legacy path, parquet CSVs not generated."""
        output_dir = tmp_path / "tables"
        generated = generate_all_tables(FIXTURES_DIR, output_dir)

        # The fixture parquet is at FIXTURES_DIR root, not under seed_<s>/datasets/,
        # so legacy discovery won't find it. outcome_distributions may or may not
        # be generated via the H2H synthetic fallback depending on fixture data.
        # The key assertion: if it IS generated, it should be synthetic.
        if "chart_data/outcome_distributions.csv" in generated:
            od_path = output_dir.parent / "chart_data" / "outcome_distributions.csv"
            od_df = pd.read_csv(od_path)
            assert (od_df["source"] == "synthetic").all()

    def test_dataset_dirs_nested_datasets_subdir(self, tmp_path):
        """Discovers parquet in datasets/ subdirectory of dataset_dir."""
        import shutil

        rung_dir = tmp_path / "rung"
        rung_dir.mkdir()
        for f in FIXTURES_DIR.glob("*.json"):
            shutil.copy2(f, rung_dir / f.name)

        # Parquet nested under datasets/ subdir
        ds_dir = tmp_path / "datasets" / "seed_1001"
        nested = ds_dir / "datasets"
        nested.mkdir(parents=True)
        df = pd.DataFrame(
            {
                "hand_id": range(50),
                "deal_id": list(range(25)) * 2,
                "focal_seat": [0, 1, 2, 3] * 12 + [0, 0],
                "action_type": ["bid"] * 50,
                "contract_family": ["suit"] * 30 + ["high"] * 20,
                "bid_n": [6] * 50,
                "trump_suit": ["H"] * 50,
                "net_points": [2.0] * 50,
                "tricks_won": ([5, 6, 7, 4, 8] * 10),
            }
        )
        (nested / "action_value.parquet").parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(nested / "action_value.parquet")

        output_dir = tmp_path / "tables"
        generated = generate_all_tables(rung_dir, output_dir, dataset_dirs=[ds_dir])

        assert "chart_data/outcome_distributions.csv" in generated
        od_df = pd.read_csv(
            output_dir.parent / "chart_data" / "outcome_distributions.csv"
        )
        assert (od_df["source"] == "parquet").all()


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


# ──────────────────────────────────────────────
#  Expanded behavior column tests
# ──────────────────────────────────────────────


class TestBehaviorSummaryExpanded:
    """Tests for expanded behavior_summary columns (pass_rate, mix_*)."""

    def test_pass_rate_computed(self, comparator_cis, h2h_battery):
        """pass_rate = 1 - bid_rate is present and correct."""
        df = generate_behavior_summary(comparator_cis, h2h_battery)
        assert "pass_rate" in df.columns
        comp_rows = df[df["source"] == "comparator"]
        for _, row in comp_rows.iterrows():
            if row["bid_rate"] is not None and not pd.isna(row["bid_rate"]):
                expected = round(1.0 - row["bid_rate"], 4)
                assert row["pass_rate"] == pytest.approx(expected, abs=1e-4)

    def test_mix_columns_present(self, comparator_cis, h2h_battery):
        """mix_suit, mix_high, mix_low columns are present."""
        df = generate_behavior_summary(comparator_cis, h2h_battery)
        for col in ("mix_suit", "mix_high", "mix_low"):
            assert col in df.columns

    def test_mix_from_h2h_self_play(self):
        """Contract mix computed from H2H self-play by_contract deal counts."""
        h2h = {
            "cells": {
                "a_self": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_a",
                    "fullgame_eppd": 3.5,
                    "bid_rate_a": 0.4,
                    "make_rate_a": 0.6,
                    "fullgame_cvar_5": -2.0,
                    "deals_total": 100,
                    "by_contract": {
                        "suit": {"deals_total": 70, "net_eppd_delta": 0.5},
                        "high": {"deals_total": 20, "net_eppd_delta": 0.3},
                        "low": {"deals_total": 10, "net_eppd_delta": 0.1},
                    },
                },
            },
        }
        df = generate_behavior_summary(None, h2h)
        row = df.iloc[0]
        assert row["mix_suit"] == pytest.approx(0.7, abs=1e-3)
        assert row["mix_high"] == pytest.approx(0.2, abs=1e-3)
        assert row["mix_low"] == pytest.approx(0.1, abs=1e-3)

    def test_graceful_without_contract_data(self):
        """mix_* columns are None when no by_contract data is available."""
        # Use a minimal fixture WITHOUT bidders_by_contract
        cis_no_contract = {
            "bidders": {
                "model_a": {
                    "bid_rate": 0.5,
                    "make_rate": 0.7,
                    "net_eppd": 1.0,
                    "cvar_5": -1.0,
                    "net_cvar_5": -2.0,
                },
            },
        }
        df = generate_behavior_summary(cis_no_contract, None)
        for col in ("mix_suit", "mix_high", "mix_low"):
            assert df[col].isna().all()


class TestBehaviorByContractExpanded:
    """Tests for expanded behavior_by_contract columns (pass_rate)."""

    def test_pass_rate_present(self, comparator_cis):
        """pass_rate column is present in behavior_by_contract."""
        df = generate_behavior_by_contract(comparator_cis)
        assert "pass_rate" in df.columns

    def test_pass_rate_computed(self, comparator_cis):
        """pass_rate = 1 - bid_rate for all rows."""
        df = generate_behavior_by_contract(comparator_cis)
        for _, row in df.iterrows():
            if row["bid_rate"] is not None and not pd.isna(row["bid_rate"]):
                expected = round(1.0 - row["bid_rate"], 4)
                assert row["pass_rate"] == pytest.approx(expected, abs=1e-4)

    def test_per_contract_rows_when_data_present(self, comparator_cis):
        """When bidders_by_contract is present, emit suit/high/low rows."""
        assert (
            "bidders_by_contract" in comparator_cis
        ), "Fixture should include bidders_by_contract"
        df = generate_behavior_by_contract(comparator_cis)
        contracts = sorted(df["contract"].unique())
        assert "suit" in contracts, "Should have suit rows"
        assert "high" in contracts, "Should have high rows"
        assert "low" in contracts, "Should have low rows"
        assert "pooled" in contracts, "Should still have pooled rows"

    def test_per_contract_bid_rate_populated(self, comparator_cis):
        """Per-contract rows should have non-null bid_rate/make_rate."""
        df = generate_behavior_by_contract(comparator_cis)
        suit_rows = df[df["contract"] == "suit"]
        assert len(suit_rows) > 0, "Should have suit rows"
        assert suit_rows["bid_rate"].notna().all(), "bid_rate should not be null"
        assert suit_rows["make_rate"].notna().all(), "make_rate should not be null"

    def test_pooled_only_without_contract_data(self):
        """Without bidders_by_contract, only pooled rows are emitted."""
        cis_no_contract = {
            "bidders": {
                "model_a": {"bid_rate": 0.5, "make_rate": 0.7, "net_eppd": 1.0},
            }
        }
        df = generate_behavior_by_contract(cis_no_contract)
        assert df["contract"].unique().tolist() == ["pooled"]


# ──────────────────────────────────────────────
#  Chart data extraction tests
# ──────────────────────────────────────────────


class TestChartData:
    """Tests for chart_data CSV generation."""

    def test_outcome_summary_not_generated(self, h2h_battery, tmp_path):
        """outcome_summary.csv removed per plan §3.10 — no longer generated."""
        generated = generate_chart_data(h2h_battery=h2h_battery, output_dir=tmp_path)
        assert "outcome_summary.csv" not in generated
        assert not (tmp_path / "outcome_summary.csv").exists()

    def test_decision_comparison_not_in_canonical_path(self, tmp_path):
        """decision_comparison.csv not produced by generate_chart_data().

        Canonical producer is generate_interpretability.py. The dormant
        parquet extractor is retained as a library function but must not
        be called from generate_chart_data() to prevent silent shadowing.
        See governing plan §16.5 ownership table.
        """
        parquet_path = FIXTURES_DIR / "action_value.parquet"
        generated = generate_chart_data(
            output_dir=tmp_path, parquet_paths=[parquet_path]
        )
        assert "decision_comparison.csv" not in generated
        assert not (tmp_path / "decision_comparison.csv").exists()

    def test_disagreement_outcomes_not_in_canonical_path(self, tmp_path):
        """disagreement_outcomes.csv not produced by generate_chart_data().

        Canonical producer is generate_interpretability.py. Same ownership
        guard as decision_comparison.csv.
        """
        parquet_path = FIXTURES_DIR / "action_value.parquet"
        generated = generate_chart_data(
            output_dir=tmp_path, parquet_paths=[parquet_path]
        )
        assert "disagreement_outcomes.csv" not in generated
        assert not (tmp_path / "disagreement_outcomes.csv").exists()

    def test_contract_mix_from_h2h(self, tmp_path):
        """contract_mix.csv generated from H2H self-play by_contract."""
        h2h = {
            "cells": {
                "a_self": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_a",
                    "deals_total": 100,
                    "by_contract": {
                        "suit": {"deals_total": 60, "net_eppd_delta": 0.5},
                        "high": {"deals_total": 25, "net_eppd_delta": 0.3},
                        "low": {"deals_total": 15, "net_eppd_delta": 0.1},
                    },
                },
            },
        }
        generated = generate_chart_data(h2h_battery=h2h, output_dir=tmp_path)
        assert "contract_mix.csv" in generated
        df = pd.read_csv(tmp_path / "contract_mix.csv")
        assert set(df.columns) == {"model", "contract", "deals", "fraction"}
        assert len(df) == 3
        suit_row = df[df["contract"] == "suit"].iloc[0]
        assert suit_row["deals"] == 60
        assert suit_row["fraction"] == pytest.approx(0.6, abs=1e-3)

    def test_no_data_no_csvs(self, tmp_path):
        """No chart_data CSVs generated when no source data exists."""
        generated = generate_chart_data(output_dir=tmp_path)
        assert len(generated) == 0

    def test_graceful_without_by_contract(self, tmp_path):
        """No contract_mix.csv when H2H has no by_contract data."""
        h2h = {
            "cells": {
                "a_self": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_a",
                    "deals_total": 100,
                    "fullgame_eppd": 3.5,
                },
            },
        }
        generated = generate_chart_data(h2h_battery=h2h, output_dir=tmp_path)
        assert "contract_mix.csv" not in generated

    def test_chart_data_in_full_pipeline(self, tmp_path):
        """generate_all_tables produces chart_data CSVs."""
        output_dir = tmp_path / "tables"
        generated = generate_all_tables(FIXTURES_DIR, output_dir)
        chart_data_items = [g for g in generated if g.startswith("chart_data/")]
        # Fixture h2h_battery has self-play cells with fullgame_eppd
        assert len(chart_data_items) > 0

    def test_h2h_by_contract_from_h2h(self, h2h_battery, tmp_path):
        """h2h_by_contract.csv generated from H2H battery by_contract."""
        # Add by_contract data to a cross-matchup cell for testing
        h2h = dict(h2h_battery)
        cells = dict(h2h["cells"])
        cell = dict(cells["gbt_av_vs_selected_ols_av"])
        cell["by_contract"] = {
            "suit": {
                "net_eppd_delta": 0.6,
                "deals_total": 30,
                "win_rate_a": 0.58,
            },
            "high": {
                "net_eppd_delta": 0.3,
                "deals_total": 15,
                "win_rate_a": 0.52,
            },
        }
        cells["gbt_av_vs_selected_ols_av"] = cell
        h2h["cells"] = cells

        generated = generate_chart_data(h2h_battery=h2h, output_dir=tmp_path)
        assert "h2h_by_contract.csv" in generated
        df = pd.read_csv(tmp_path / "h2h_by_contract.csv")
        assert "model" in df.columns
        assert "opponent" in df.columns
        assert "contract" in df.columns
        assert "net_eppd_delta" in df.columns
        assert len(df) > 0

    def test_h2h_by_contract_no_by_contract(self, tmp_path):
        """h2h_by_contract still emits pooled rows from cells without by_contract."""
        h2h = {
            "cells": {
                "a_vs_b": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_b",
                    "net_eppd_delta": 0.5,
                    "deals_total": 50,
                    "win_rate_a": 0.55,
                },
            },
        }
        generated = generate_chart_data(h2h_battery=h2h, output_dir=tmp_path)
        assert "h2h_by_contract.csv" in generated
        df = pd.read_csv(tmp_path / "h2h_by_contract.csv")
        assert len(df) == 1
        assert df.iloc[0]["contract"] == "pooled"

    def test_bid_levels_from_comparator(self, comparator_cis, tmp_path):
        """bid_levels.csv generated from comparator CIs."""
        generated = generate_chart_data(
            comparator_cis=comparator_cis, output_dir=tmp_path
        )
        assert "bid_levels.csv" in generated
        df = pd.read_csv(tmp_path / "bid_levels.csv")
        assert "model" in df.columns
        assert "bid_rate" in df.columns
        assert "make_rate" in df.columns
        assert "pass_rate" in df.columns
        assert len(df) == len(comparator_cis["bidders"])

    def test_selection_paths_from_training_artifacts(
        self, training_artifacts, tmp_path
    ):
        """selection_paths.csv generated from feature_importances in training artifacts."""
        generated = generate_chart_data(
            training_artifacts=training_artifacts, output_dir=tmp_path
        )
        assert "selection_paths.csv" in generated
        df = pd.read_csv(tmp_path / "selection_paths.csv")
        assert "model" in df.columns
        assert "contract" in df.columns
        assert "rank" in df.columns
        assert "feature_name" in df.columns
        assert "importance" in df.columns
        # GBT artifact has 4 contracts with feature_importances
        gbt_rows = df[df["model"] == "gbt"]
        assert len(gbt_rows) > 0
        # Check ranking is correct: rank 1 should have highest importance
        suit_rows = gbt_rows[gbt_rows["contract"] == "suit"].sort_values("rank")
        assert suit_rows.iloc[0]["rank"] == 1

    def test_full_pipeline_with_all_chart_data(self, tmp_path):
        """Full pipeline produces the new chart_data CSVs."""
        output_dir = tmp_path / "tables"
        generated = generate_all_tables(FIXTURES_DIR, output_dir)
        chart_data_items = [g for g in generated if g.startswith("chart_data/")]
        csv_names = [item.replace("chart_data/", "") for item in chart_data_items]
        assert "outcome_summary.csv" not in csv_names  # removed per plan §3.10
        # Training artifacts have feature_importances, so selection_paths
        assert "selection_paths.csv" in csv_names


# ──────────────────────────────────────────────
#  Cross-rung progression tests
# ──────────────────────────────────────────────


class TestCrossRungProgression:
    """Tests for cross_rung_progression.csv generation."""

    def test_basic_progression(self, comparator_cis):
        """Progression across two rungs produces correct rows."""
        rung_cis = {
            "r0": comparator_cis,
            "r1": comparator_cis,  # Same data for testing structure
        }
        df = generate_cross_rung_progression(rung_cis)
        assert "rung" in df.columns
        assert "model" in df.columns
        assert "rank" in df.columns
        assert "net_eppd" in df.columns
        assert "bid_rate" in df.columns
        n_bidders = len(comparator_cis["bidders"])
        assert len(df) == 2 * n_bidders

    def test_rung_ordering(self, comparator_cis):
        """Rungs are sorted alphabetically in output."""
        rung_cis = {
            "r2": comparator_cis,
            "r0": comparator_cis,
            "r1": comparator_cis,
        }
        df = generate_cross_rung_progression(rung_cis)
        rungs = df["rung"].unique().tolist()
        assert rungs == ["r0", "r1", "r2"]

    def test_empty_input(self):
        """Empty input returns empty DataFrame."""
        df = generate_cross_rung_progression({})
        assert len(df) == 0
        assert "rung" in df.columns


# ──────────────────────────────────────────────
#  Seat balance tests
# ──────────────────────────────────────────────


class TestSeatBalance:
    """Tests for seat_balance.csv generation from parquet."""

    def test_basic_seat_balance(self, tmp_path):
        """Generates seat_balance from a parquet with seat column."""
        df = pd.DataFrame(
            {
                "seat": [0, 0, 1, 1, 2, 2, 3, 3],
                "contract_family": [
                    "suit",
                    "high",
                    "suit",
                    "high",
                    "suit",
                    "high",
                    "suit",
                    "high",
                ],
                "tricks_won": [5.0, 4.0, 6.0, 3.0, 5.5, 4.5, 4.5, 5.5],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        output_dir = tmp_path / "chart_data"
        result = generate_seat_balance_csv(parquet_path, output_dir)
        assert result == "seat_balance.csv"
        out_df = pd.read_csv(output_dir / "seat_balance.csv")
        assert "seat" in out_df.columns
        assert "contract" in out_df.columns
        assert "mean_tricks" in out_df.columns
        assert "n_hands" in out_df.columns
        assert len(out_df) == 8  # 4 seats * 2 contracts

    def test_missing_parquet(self, tmp_path):
        """Returns None when parquet file does not exist."""
        result = generate_seat_balance_csv(
            tmp_path / "nonexistent.parquet", tmp_path / "chart_data"
        )
        assert result is None

    def test_missing_seat_column(self, tmp_path):
        """Returns None when parquet lacks both seat and focal_seat columns."""
        df = pd.DataFrame({"other_col": [1, 2, 3], "tricks_won": [5, 6, 7]})
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        result = generate_seat_balance_csv(parquet_path, tmp_path / "chart_data")
        assert result is None

    def test_focal_seat_fallback(self, tmp_path):
        """Uses focal_seat column when seat column is absent."""
        df = pd.DataFrame(
            {
                "focal_seat": [0, 0, 1, 1, 2, 2, 3, 3],
                "contract_family": [
                    "suit",
                    "high",
                    "suit",
                    "high",
                    "suit",
                    "high",
                    "suit",
                    "high",
                ],
                "tricks_won": [5.0, 4.0, 6.0, 3.0, 5.5, 4.5, 4.5, 5.5],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        output_dir = tmp_path / "chart_data"
        result = generate_seat_balance_csv(parquet_path, output_dir)
        assert result == "seat_balance.csv"
        out_df = pd.read_csv(output_dir / "seat_balance.csv")
        assert "seat" in out_df.columns
        assert "contract" in out_df.columns
        assert "mean_tricks" in out_df.columns
        assert "n_hands" in out_df.columns
        assert len(out_df) == 8  # 4 seats * 2 contracts

    def test_seat_balance_no_seat_col_returns_none(self, tmp_path):
        """Returns None when DataFrame has tricks_won and contract_family but no seat column."""
        df = pd.DataFrame(
            {
                "contract_family": ["suit", "high", "suit"],
                "tricks_won": [5.0, 4.0, 6.0],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        result = generate_seat_balance_csv(parquet_path, tmp_path / "chart_data")
        assert result is None

    def test_seat_balance_no_value_col_returns_none(self, tmp_path):
        """Returns None when DataFrame has seat but no tricks_won or actual column."""
        df = pd.DataFrame(
            {
                "seat": [0, 1, 2, 3],
                "contract_family": ["suit", "suit", "suit", "suit"],
                "some_other_metric": [1.0, 2.0, 3.0, 4.0],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        result = generate_seat_balance_csv(parquet_path, tmp_path / "chart_data")
        assert result is None

    def test_seat_balance_pooled_no_contract_col(self, tmp_path):
        """Uses pooled groupby (seat only) when no contract column is present."""
        df = pd.DataFrame(
            {
                "seat": [0, 0, 1, 1, 2, 2, 3, 3],
                "tricks_won": [5.0, 6.0, 4.0, 5.0, 3.0, 7.0, 4.5, 5.5],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        output_dir = tmp_path / "chart_data"
        result = generate_seat_balance_csv(parquet_path, output_dir)
        assert result == "seat_balance.csv"
        out_df = pd.read_csv(output_dir / "seat_balance.csv")
        assert len(out_df) == 4  # 4 seats, no contract faceting
        assert set(out_df["contract"].unique()) == {"pooled"}
        assert set(out_df["seat"].unique()) == {0, 1, 2, 3}

    def test_seat_balance_contract_type_fallback(self, tmp_path):
        """Falls back to contract_type when contract_family is absent."""
        df = pd.DataFrame(
            {
                "seat": [0, 0, 1, 1],
                "contract_type": ["suit", "high", "suit", "high"],
                "tricks_won": [5.0, 4.0, 6.0, 3.0],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        output_dir = tmp_path / "chart_data"
        result = generate_seat_balance_csv(parquet_path, output_dir)
        assert result == "seat_balance.csv"
        out_df = pd.read_csv(output_dir / "seat_balance.csv")
        assert len(out_df) == 4  # 2 seats * 2 contract types
        assert set(out_df["contract"].unique()) == {"suit", "high"}

    def test_seat_balance_actual_fallback(self, tmp_path):
        """Falls back to actual column when tricks_won is absent."""
        df = pd.DataFrame(
            {
                "seat": [0, 0, 1, 1, 2, 2, 3, 3],
                "contract_family": [
                    "suit",
                    "high",
                    "suit",
                    "high",
                    "suit",
                    "high",
                    "suit",
                    "high",
                ],
                "actual": [5.0, 4.0, 6.0, 3.0, 5.5, 4.5, 4.5, 5.5],
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)
        output_dir = tmp_path / "chart_data"
        result = generate_seat_balance_csv(parquet_path, output_dir)
        assert result == "seat_balance.csv"
        out_df = pd.read_csv(output_dir / "seat_balance.csv")
        assert len(out_df) == 8  # 4 seats * 2 contracts
        assert "mean_tricks" in out_df.columns
        # Verify the actual values were used (seat 0, suit should be 5.0)
        seat0_suit = out_df[(out_df["seat"] == 0) & (out_df["contract"] == "suit")]
        assert float(seat0_suit["mean_tricks"].iloc[0]) == 5.0


# ──────────────────────────────────────────────
#  Feature importance extraction tests
# ──────────────────────────────────────────────


class TestFeatureImportanceExtraction:
    """Tests for _extract_feature_importance helper."""

    def test_gbt_feature_importances(self, training_artifacts):
        """GBT artifact with feature_importances produces ranked rows."""
        rows = _extract_feature_importance(training_artifacts)
        assert len(rows) > 0
        # Check structure
        for row in rows:
            assert "model" in row
            assert "contract" in row
            assert "rank" in row
            assert "feature_name" in row
            assert "importance" in row

    def test_ranking_order(self, training_artifacts):
        """Features are ranked by descending importance."""
        rows = _extract_feature_importance(training_artifacts)
        gbt_suit = [r for r in rows if r["model"] == "gbt" and r["contract"] == "suit"]
        assert len(gbt_suit) > 0
        # Rank 1 should have highest importance
        importances = [(r["rank"], r["importance"]) for r in gbt_suit]
        importances.sort(key=lambda x: x[0])
        for i in range(len(importances) - 1):
            assert importances[i][1] >= importances[i + 1][1]

    def test_empty_artifacts(self):
        """Empty artifacts return empty list."""
        assert _extract_feature_importance({}) == []


# ──────────────────────────────────────────────
#  Outcome distributions extraction tests
# ──────────────────────────────────────────────


class TestH2hByContractExtraction:
    """Tests for _extract_h2h_by_contract helper."""

    def test_basic_extraction(self):
        """Extracts pooled rows from cells without by_contract."""
        h2h = {
            "cells": {
                "a_vs_b": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_b",
                    "net_eppd_delta": 0.5,
                    "deals_total": 50,
                    "win_rate_a": 0.55,
                },
            },
        }
        rows = _extract_h2h_by_contract(h2h)
        assert len(rows) == 1
        assert rows[0]["contract"] == "pooled"
        assert rows[0]["model"] == "model_a"

    def test_with_by_contract(self):
        """Extracts per-contract + pooled rows."""
        h2h = {
            "cells": {
                "a_vs_b": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_b",
                    "net_eppd_delta": 0.5,
                    "deals_total": 50,
                    "win_rate_a": 0.55,
                    "by_contract": {
                        "suit": {
                            "net_eppd_delta": 0.6,
                            "deals_total": 30,
                            "win_rate_a": 0.58,
                        },
                    },
                },
            },
        }
        rows = _extract_h2h_by_contract(h2h)
        assert len(rows) == 2  # 1 suit + 1 pooled
        contracts = [r["contract"] for r in rows]
        assert "suit" in contracts
        assert "pooled" in contracts


# ──────────────────────────────────────────────
#  Bid levels extraction tests
# ──────────────────────────────────────────────


class TestBidLevelsExtraction:
    """Tests for _extract_bid_levels helper."""

    def test_basic_extraction(self, comparator_cis):
        """Extracts bid/make/pass rates from comparator CIs."""
        rows = _extract_bid_levels(comparator_cis)
        assert len(rows) == len(comparator_cis["bidders"])
        for row in rows:
            assert "model" in row
            assert "bid_rate" in row
            assert "make_rate" in row
            assert "pass_rate" in row
            # pass_rate should be 1 - bid_rate
            if row["bid_rate"] is not None and row["pass_rate"] is not None:
                assert abs(row["bid_rate"] + row["pass_rate"] - 1.0) < 0.01

    def test_empty_comparator(self):
        """Empty bidders returns empty list."""
        rows = _extract_bid_levels({"bidders": {}})
        assert rows == []


# ──────────────────────────────────────────────
#  Model eval CSVs tests
# ──────────────────────────────────────────────


class TestModelEvalCsvs:
    """Tests for generate_model_eval_csvs."""

    def test_graceful_without_parquet(self, training_artifacts, tmp_path):
        """Returns empty when eval parquet doesn't exist."""
        result = generate_model_eval_csvs(
            training_artifacts,
            tmp_path / "nonexistent.parquet",
            tmp_path / "output",
        )
        assert result == []

    def test_graceful_without_artifacts(self, tmp_path):
        """Returns empty when no training artifacts provided."""
        result = generate_model_eval_csvs(
            {},
            tmp_path / "eval.parquet",
            tmp_path / "output",
        )
        assert result == []

    def test_graceful_with_none_path(self, training_artifacts, tmp_path):
        """Returns empty when eval path is None."""
        result = generate_model_eval_csvs(
            training_artifacts,
            None,
            tmp_path / "output",
        )
        assert result == []

    def test_tricks_won_column_fallback(self, tmp_path):
        """Produces predictions/residuals/calibration using tricks_won when actual absent.

        Uses an OLS artifact (coefficients in JSON, no joblib required) to
        verify that the tricks_won column fallback enables CSV generation
        from action_value parquets that lack an 'actual' column.
        """
        import numpy as np

        # Minimal OLS artifact with one feature per contract
        ols_artifact = {
            "schema_version": "action_value_olsa_v1",
            "target": "tricks_won",
            "models": {
                "suit": {
                    "feature_names": ["hand_value"],
                    "coefficients": [0.5],
                    "intercept": 2.0,
                    "r_squared": 0.6,
                    "mae": 1.0,
                    "n_train": 100,
                    "n_val": 20,
                },
            },
            "metadata": {},
        }
        training_artifacts = {"test_ols": ols_artifact}

        # Parquet with tricks_won but no 'actual' column
        rng = np.random.RandomState(42)
        n = 50
        df = pd.DataFrame(
            {
                "hand_value": rng.uniform(0, 10, n),
                "contract_family": ["suit"] * n,
                "action_type": ["bid"] * n,
                "tricks_won": rng.uniform(2, 8, n),
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)

        output_dir = tmp_path / "chart_data"
        result = generate_model_eval_csvs(training_artifacts, parquet_path, output_dir)

        # Should produce all three CSVs
        assert "predictions.csv" in result
        assert "residuals.csv" in result
        assert "calibration_bins.csv" in result

        # Verify predictions CSV has correct columns
        pred_df = pd.read_csv(output_dir / "predictions.csv")
        assert "model" in pred_df.columns
        assert "contract" in pred_df.columns
        assert "prediction" in pred_df.columns
        assert "actual" in pred_df.columns
        assert len(pred_df) == n

    def test_actual_column_preferred_over_tricks_won(self, tmp_path):
        """When both 'actual' and 'tricks_won' exist, 'actual' is used."""
        import numpy as np

        ols_artifact = {
            "schema_version": "action_value_olsa_v1",
            "target": "tricks_won",
            "models": {
                "suit": {
                    "feature_names": ["hand_value"],
                    "coefficients": [0.5],
                    "intercept": 2.0,
                    "r_squared": 0.6,
                    "mae": 1.0,
                    "n_train": 100,
                    "n_val": 20,
                },
            },
            "metadata": {},
        }
        training_artifacts = {"test_ols": ols_artifact}

        rng = np.random.RandomState(42)
        n = 30
        actual_values = rng.uniform(2, 8, n)
        tricks_won_values = rng.uniform(0, 10, n)  # Different from actual
        df = pd.DataFrame(
            {
                "hand_value": rng.uniform(0, 10, n),
                "contract_family": ["suit"] * n,
                "action_type": ["bid"] * n,
                "actual": actual_values,
                "tricks_won": tricks_won_values,
            }
        )
        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)

        output_dir = tmp_path / "chart_data"
        result = generate_model_eval_csvs(training_artifacts, parquet_path, output_dir)
        assert "predictions.csv" in result

        pred_df = pd.read_csv(output_dir / "predictions.csv")
        # The 'actual' column values should match the 'actual' source, not tricks_won
        for _, row in pred_df.iterrows():
            assert row["actual"] in [round(v, 4) for v in actual_values]

    def test_gbt_joblib_discovered_via_rung_dir(self, tmp_path):
        """GBT joblib files are found when rung_dir points to artifacts directory."""
        import numpy as np

        try:
            import joblib
        except ImportError:
            pytest.skip("joblib not installed")

        from sklearn.ensemble import GradientBoostingRegressor

        # Train a minimal GBT model and save as joblib
        rng = np.random.RandomState(42)
        n_train = 50
        X_train = rng.uniform(0, 10, (n_train, 1))
        y_train = rng.uniform(2, 8, n_train)
        model = GradientBoostingRegressor(n_estimators=5, max_depth=2, random_state=42)
        model.fit(X_train, y_train)

        # Set up rung_dir with joblib model
        rung_dir = tmp_path / "rung_artifacts"
        rung_dir.mkdir()
        joblib.dump(model, rung_dir / "gbt_suit.joblib")

        # GBT training artifact referencing the joblib file
        gbt_artifact = {
            "schema_version": "action_value_gbt_v1",
            "models": {
                "suit": {
                    "feature_names": ["hand_value"],
                    "model_file": "gbt_suit.joblib",
                    "r_squared": 0.5,
                    "mae": 1.5,
                    "n_train": n_train,
                    "n_val": 10,
                },
            },
        }
        training_artifacts = {"gbt_av": gbt_artifact}

        # Eval parquet in a completely separate directory (simulating real layout)
        eval_dir = tmp_path / "datasets" / "action_value"
        eval_dir.mkdir(parents=True)
        n_eval = 30
        df = pd.DataFrame(
            {
                "hand_value": rng.uniform(0, 10, n_eval),
                "contract_family": ["suit"] * n_eval,
                "action_type": ["bid"] * n_eval,
                "tricks_won": rng.uniform(2, 8, n_eval),
            }
        )
        parquet_path = eval_dir / "eval.parquet"
        df.to_parquet(parquet_path)

        output_dir = tmp_path / "chart_data"

        # Without rung_dir: GBT should be skipped (joblib not near parquet)
        result_without = generate_model_eval_csvs(
            training_artifacts, parquet_path, output_dir
        )
        assert result_without == []

        # With rung_dir: GBT should be found and produce predictions
        result_with = generate_model_eval_csvs(
            training_artifacts, parquet_path, output_dir, rung_dir=rung_dir
        )
        assert "predictions.csv" in result_with
        assert "residuals.csv" in result_with
        assert "calibration_bins.csv" in result_with

        # Verify GBT model name appears in predictions
        pred_df = pd.read_csv(output_dir / "predictions.csv")
        assert "gbt_av" in pred_df["model"].values
        assert len(pred_df[pred_df["model"] == "gbt_av"]) == n_eval

    def test_bid_n_sq_derived_enables_contract_facets(self, tmp_path):
        """Parquet with bid_n but NOT bid_n_sq produces suit/high/low rows.

        Regression test: before the fix, models requiring bid_n_sq would
        silently skip non-pass contracts because the derived feature was
        missing from the parquet. The fix computes bid_n_sq on the fly.
        """
        import numpy as np

        # OLS artifact whose suit/high/low models require bid_n + bid_n_sq
        ols_artifact = {
            "schema_version": "action_value_olsa_v1",
            "target": "tricks_won",
            "models": {
                "suit": {
                    "feature_names": ["bowers", "bid_n", "bid_n_sq"],
                    "coefficients": [0.5, 0.3, -0.01],
                    "intercept": 2.0,
                    "r_squared": 0.6,
                    "mae": 1.0,
                    "n_train": 100,
                    "n_val": 20,
                },
                "high": {
                    "feature_names": ["bowers", "bid_n", "bid_n_sq"],
                    "coefficients": [0.4, 0.2, -0.005],
                    "intercept": 1.5,
                    "r_squared": 0.5,
                    "mae": 1.2,
                    "n_train": 100,
                    "n_val": 20,
                },
                "low": {
                    "feature_names": ["bowers", "bid_n", "bid_n_sq"],
                    "coefficients": [0.3, 0.1, -0.002],
                    "intercept": 1.0,
                    "r_squared": 0.4,
                    "mae": 1.5,
                    "n_train": 100,
                    "n_val": 20,
                },
                "pass": {
                    "feature_names": ["bowers"],
                    "coefficients": [0.2],
                    "intercept": 3.0,
                    "r_squared": 0.3,
                    "mae": 2.0,
                    "n_train": 100,
                    "n_val": 20,
                },
            },
            "metadata": {},
        }
        training_artifacts = {"test_ols": ols_artifact}

        rng = np.random.RandomState(42)
        n = 40
        # Parquet has bid_n but NOT bid_n_sq (mirrors real action_value.parquet)
        df = pd.DataFrame(
            {
                "bowers": rng.uniform(0, 2, n),
                "bid_n": rng.randint(1, 11, n),
                "contract_family": ["suit"] * 10
                + ["high"] * 10
                + ["low"] * 10
                + ["none"] * 10,
                "action_type": ["bid"] * 30 + ["pass"] * 10,
                "tricks_won": rng.uniform(0, 10, n),
            }
        )
        assert "bid_n_sq" not in df.columns  # Precondition

        parquet_path = tmp_path / "eval.parquet"
        df.to_parquet(parquet_path)

        output_dir = tmp_path / "chart_data"
        result = generate_model_eval_csvs(training_artifacts, parquet_path, output_dir)

        assert "predictions.csv" in result
        pred_df = pd.read_csv(output_dir / "predictions.csv")
        contracts = sorted(pred_df["contract"].unique())

        # All four contract types should be present
        assert contracts == [
            "high",
            "low",
            "pass",
            "suit",
        ], f"Expected all 4 contracts, got {contracts}"

        # Verify suit/high/low rows exist (the regression target)
        for contract in ["suit", "high", "low"]:
            contract_rows = pred_df[pred_df["contract"] == contract]
            assert len(contract_rows) > 0, f"No rows for contract={contract}"


# ──────────────────────────────────────────────
#  Outcome distributions extraction tests (Phase B)
# ──────────────────────────────────────────────


class TestExtractOutcomeDistributions:
    """Tests for _extract_outcome_distributions helper."""

    def test_self_play_fallback(self):
        """Extracts fallback single-bin rows from self-play cells."""
        h2h = {
            "cells": {
                "gbt_self": {
                    "bidder_a": "gbt",
                    "bidder_b": "gbt",
                    "by_contract": {
                        "suit": {"deals_total": 100, "net_eppd_delta": 0.5},
                        "high": {"deals_total": 50, "net_eppd_delta": 0.3},
                    },
                },
            },
        }
        rows = _extract_outcome_distributions(h2h)
        assert len(rows) == 2
        for row in rows:
            assert row["model"] == "gbt"
            assert "tricks_won" in row
            assert "count" in row
            assert "fraction" in row
            assert row["count"] > 0

    def test_explicit_histogram(self):
        """Extracts explicit histogram bins when available."""
        h2h = {
            "cells": {
                "gbt_self": {
                    "bidder_a": "gbt",
                    "bidder_b": "gbt",
                    "by_contract": {
                        "suit": {
                            "deals_total": 100,
                            "tricks_won_histogram": {
                                "3": 10,
                                "4": 30,
                                "5": 40,
                                "6": 20,
                            },
                        },
                    },
                },
            },
        }
        rows = _extract_outcome_distributions(h2h)
        assert len(rows) == 4
        tricks = [r["tricks_won"] for r in rows]
        assert 3 in tricks
        assert 6 in tricks
        total_count = sum(r["count"] for r in rows)
        assert total_count == 100

    def test_skips_cross_matchup(self):
        """Skips non-self-play cells."""
        h2h = {
            "cells": {
                "cross": {
                    "bidder_a": "gbt",
                    "bidder_b": "ols",
                    "by_contract": {
                        "suit": {"deals_total": 100},
                    },
                },
            },
        }
        rows = _extract_outcome_distributions(h2h)
        assert len(rows) == 0

    def test_empty_battery(self):
        """Returns empty list for empty battery."""
        rows = _extract_outcome_distributions({"cells": {}})
        assert rows == []

    def test_chart_data_includes_outcome_distributions(self, tmp_path):
        """generate_chart_data produces outcome_distributions.csv."""
        h2h = {
            "cells": {
                "gbt_self": {
                    "bidder_a": "gbt",
                    "bidder_b": "gbt",
                    "fullgame_eppd": 3.5,
                    "by_contract": {
                        "suit": {"deals_total": 60, "net_eppd_delta": 0.5},
                        "high": {"deals_total": 25, "net_eppd_delta": 0.3},
                        "low": {"deals_total": 15, "net_eppd_delta": 0.1},
                    },
                },
            },
        }
        generated = generate_chart_data(h2h_battery=h2h, output_dir=tmp_path)
        assert "outcome_distributions.csv" in generated
        df = pd.read_csv(tmp_path / "outcome_distributions.csv")
        assert "model" in df.columns
        assert "contract" in df.columns
        assert "tricks_won" in df.columns
        assert "count" in df.columns
        assert len(df) > 0


# ──────────────────────────────────────────────
#  Feature importances flat extraction tests (Phase B)
# ──────────────────────────────────────────────


class TestExtractFeatureImportancesFlat:
    """Tests for _extract_feature_importances_flat helper."""

    def test_extracts_from_feature_importances(self):
        """Extracts flat feature importance rows from artifact dicts."""
        artifacts = {
            "gbt": {
                "models": {
                    "suit": {
                        "feature_importances": {
                            "trump_count": 0.35,
                            "hand_strength": 0.25,
                        },
                    },
                    "high": {
                        "feature_importances": {
                            "trump_count": 0.10,
                        },
                    },
                },
            },
        }
        rows = _extract_feature_importances_flat(artifacts)
        assert len(rows) == 3
        for row in rows:
            assert "model" in row
            assert "contract" in row
            assert "feature_name" in row
            assert "importance" in row
            assert row["model"] == "gbt"

    def test_empty_artifacts(self):
        """Returns empty list for empty artifacts."""
        assert _extract_feature_importances_flat({}) == []

    def test_no_importances_key(self):
        """Returns empty list when models lack feature_importances."""
        artifacts = {
            "gbt": {
                "models": {
                    "suit": {"r_squared": 0.85},
                },
            },
        }
        rows = _extract_feature_importances_flat(artifacts)
        assert rows == []

    def test_chart_data_includes_feature_importances(self, tmp_path):
        """generate_chart_data produces feature_importances.csv with ranked schema.

        Step 6 (_extract_feature_importance) writes the ranked schema (with rank
        column) from feature_importances dicts. Step 8 is skipped because step 6
        already produced the file (fixes #833 — no more clobbering).
        """
        artifacts = {
            "gbt": {
                "models": {
                    "suit": {
                        "feature_importances": {
                            "trump_count": 0.35,
                            "hand_strength": 0.25,
                        },
                    },
                },
            },
        }
        generated = generate_chart_data(
            training_artifacts=artifacts, output_dir=tmp_path
        )
        assert "feature_importances.csv" in generated
        df = pd.read_csv(tmp_path / "feature_importances.csv")
        # Step 6 produces the ranked schema (includes rank column)
        assert set(df.columns) == {
            "model",
            "contract",
            "rank",
            "feature_name",
            "importance",
        }
        assert len(df) == 2

        # Verify backward-compat dual-write: selection_paths.csv is also produced
        assert "selection_paths.csv" in generated
        assert (tmp_path / "selection_paths.csv").exists()
        df_sel = pd.read_csv(tmp_path / "selection_paths.csv")
        pd.testing.assert_frame_equal(df, df_sel)

    def test_outcome_distributions_from_parquet(self, tmp_path):
        """outcome_distributions.csv uses parquet data when available."""
        parquet_path = FIXTURES_DIR / "action_value.parquet"
        assert parquet_path.exists(), "Fixture parquet required for this test"
        h2h = {
            "cells": {
                "a_self": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_a",
                    "deals_total": 100,
                    "by_contract": {
                        "suit": {"deals_total": 50, "mean_tricks_won": 5},
                    },
                },
            },
        }
        generated = generate_chart_data(
            h2h_battery=h2h,
            output_dir=tmp_path,
            parquet_paths=[parquet_path],
        )
        assert "outcome_distributions.csv" in generated
        df = pd.read_csv(tmp_path / "outcome_distributions.csv")
        assert "source" in df.columns
        # Parquet path should produce source=parquet rows
        assert (df["source"] == "parquet").all()
        # Should have multiple tricks_won bins, not just one
        assert df["tricks_won"].nunique() > 1
        # Without a model column in parquet, model defaults to "pooled"
        assert (df["model"] == "pooled").all()

    def test_outcome_distributions_synthetic_fallback(self, tmp_path):
        """outcome_distributions.csv falls back to synthetic without parquet."""
        h2h = {
            "cells": {
                "a_self": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_a",
                    "deals_total": 100,
                    "by_contract": {
                        "suit": {"deals_total": 50, "mean_tricks_won": 5},
                        "high": {"deals_total": 30, "mean_tricks_won": 6},
                    },
                },
            },
        }
        generated = generate_chart_data(
            h2h_battery=h2h,
            output_dir=tmp_path,
        )
        assert "outcome_distributions.csv" in generated
        df = pd.read_csv(tmp_path / "outcome_distributions.csv")
        assert "source" in df.columns
        assert (df["source"] == "synthetic").all()

    def test_decision_comparison_graceful_skip(self):
        """decision_comparison skips when parquet lacks bid_decision column."""
        parquet_path = FIXTURES_DIR / "action_value.parquet"
        assert parquet_path.exists()
        rows = _extract_decision_comparison([parquet_path])
        assert rows == []

    def test_disagreement_outcomes_graceful_skip(self):
        """disagreement_outcomes skips when parquet lacks bid_decision column."""
        parquet_path = FIXTURES_DIR / "action_value.parquet"
        assert parquet_path.exists()
        rows = _extract_disagreement_outcomes([parquet_path])
        assert rows == []

    def test_decision_comparison_no_parquet(self):
        """decision_comparison returns empty with no parquet files."""
        rows = _extract_decision_comparison([])
        assert rows == []

    def test_disagreement_outcomes_no_parquet(self):
        """disagreement_outcomes returns empty with no parquet files."""
        rows = _extract_disagreement_outcomes([])
        assert rows == []


class TestBidLevelsFromParquet:
    """Tests for parquet-backed bid-level distribution extraction."""

    def test_bid_levels_from_parquet(self, tmp_path):
        """bid_levels.csv extracted from parquet has per-level rows."""
        # Create test parquet with bid_n column
        df = pd.DataFrame(
            {
                "contract_family": ["suit", "suit", "suit", "high", "high"],
                "bid_n": [6, 7, 6, 8, 9],
                "action_type": ["bid", "bid", "bid", "bid", "bid"],
                "tricks_won": [7, 8, 6, 9, 10],
                "focal_seat": [0, 1, 2, 0, 1],
            }
        )
        pq_path = tmp_path / "test.parquet"
        df.to_parquet(pq_path)

        rows = _extract_bid_levels_from_parquet([pq_path])
        assert len(rows) > 0

        result_df = pd.DataFrame(rows)
        assert "bid_level" in result_df.columns
        assert "contract" in result_df.columns
        assert "count" in result_df.columns
        assert "fraction" in result_df.columns

        # suit bid_n=6 appears twice, bid_n=7 once
        suit_6 = result_df[
            (result_df["contract"] == "suit") & (result_df["bid_level"] == 6)
        ]
        assert len(suit_6) == 1
        assert suit_6.iloc[0]["count"] == 2

    def test_bid_levels_fallback_to_aggregate(self):
        """bid_levels.csv falls back to aggregate when no parquet available."""
        comparator_cis = {
            "bidders": {
                "model_a": {"bid_rate": 0.7, "make_rate": 0.8},
                "model_b": {"bid_rate": 0.6, "make_rate": 0.9},
            }
        }
        rows = _extract_bid_levels(comparator_cis)
        assert len(rows) == 2
        assert all("model" in r for r in rows)
        assert all("bid_rate" in r for r in rows)

    def test_bid_levels_parquet_preferred_over_aggregate(self, tmp_path):
        """bid_levels uses parquet when available, ignoring aggregate fallback."""
        # Create parquet with bid_n
        df = pd.DataFrame(
            {
                "contract_family": ["suit", "suit"],
                "bid_n": [6, 7],
                "action_type": ["bid", "bid"],
            }
        )
        pq_path = tmp_path / "test.parquet"
        df.to_parquet(pq_path)

        comparator_cis = {
            "bidders": {
                "model_a": {"bid_rate": 0.7, "make_rate": 0.8},
            }
        }
        generated = generate_chart_data(
            comparator_cis=comparator_cis,
            output_dir=tmp_path,
            parquet_paths=[pq_path],
        )
        assert "bid_levels.csv" in generated
        result_df = pd.read_csv(tmp_path / "bid_levels.csv")
        # Parquet-backed rows have bid_level column, not bid_rate
        assert "bid_level" in result_df.columns

    def test_bid_levels_from_parquet_no_bid_n(self, tmp_path):
        """bid_levels returns empty when parquet lacks bid_n column."""
        df = pd.DataFrame(
            {
                "contract_family": ["suit", "suit"],
                "action_type": ["bid", "bid"],
                "tricks_won": [7, 8],
            }
        )
        pq_path = tmp_path / "test.parquet"
        df.to_parquet(pq_path)

        rows = _extract_bid_levels_from_parquet([pq_path])
        assert rows == []

    def test_outcome_distributions_synthetic_flagged(self, tmp_path):
        """Synthetic outcome distributions write a .status sidecar file."""
        h2h = {
            "cells": {
                "self_a": {
                    "bidder_a": "model_a",
                    "bidder_b": "model_a",
                    "by_contract": {
                        "suit": {"deals_total": 100, "mean_tricks_won": 5.5},
                    },
                }
            }
        }
        rows = _extract_outcome_distributions(h2h, parquet_paths=None)
        assert len(rows) > 0
        assert all(r["source"] == "synthetic" for r in rows)

        # Verify the full pipeline writes a .status sidecar
        generated = generate_chart_data(
            h2h_battery=h2h,
            output_dir=tmp_path,
        )
        assert "outcome_distributions.csv" in generated
        status_path = tmp_path / "outcome_distributions.status"
        assert status_path.exists()
        assert "degraded:synthetic" in status_path.read_text()


# ──────────────────────────────────────────────
#  Post-merge hardening: Parquet extraction edge cases (T3, T5)
# ──────────────────────────────────────────────


class TestExtractOutcomeDistributionsFromParquet:
    """Direct tests for _extract_outcome_distributions_from_parquet."""

    def test_missing_contract_column_returns_empty(self, tmp_path):
        """Returns [] when parquet has tricks_won but no contract column."""
        df = pd.DataFrame(
            {
                "hand_id": range(50),
                "tricks_won": [5, 6, 7, 4, 8] * 10,
                "model": ["gbt"] * 50,
                # No contract_family, contract_type, or contract column
            }
        )
        parquet_path = tmp_path / "action_value.parquet"
        df.to_parquet(parquet_path)

        rows = _extract_outcome_distributions_from_parquet([parquet_path])
        assert rows == []

    def test_missing_tricks_won_returns_empty(self, tmp_path):
        """Returns [] when parquet has contract but no tricks_won column."""
        df = pd.DataFrame(
            {
                "hand_id": range(50),
                "contract_family": ["suit"] * 30 + ["high"] * 20,
                "model": ["gbt"] * 50,
                # No tricks_won column
            }
        )
        parquet_path = tmp_path / "action_value.parquet"
        df.to_parquet(parquet_path)

        rows = _extract_outcome_distributions_from_parquet([parquet_path])
        assert rows == []

    def test_nonexistent_file_returns_empty(self, tmp_path):
        """Returns [] when parquet file does not exist."""
        fake_path = tmp_path / "nonexistent.parquet"
        rows = _extract_outcome_distributions_from_parquet([fake_path])
        assert rows == []

    def test_fraction_sums_to_one(self, tmp_path):
        """Fractions within each (model, contract) group sum to 1.0."""
        df = pd.DataFrame(
            {
                "hand_id": range(100),
                "contract_family": ["suit"] * 50 + ["high"] * 50,
                "tricks_won": [3, 4, 5, 6, 7] * 20,
                "model": ["gbt"] * 100,
            }
        )
        parquet_path = tmp_path / "action_value.parquet"
        df.to_parquet(parquet_path)

        rows = _extract_outcome_distributions_from_parquet([parquet_path])
        assert len(rows) > 0

        # Group by model+contract and verify fractions sum to ~1.0
        result_df = pd.DataFrame(rows)
        for (model, contract), group in result_df.groupby(["model", "contract"]):
            fraction_sum = group["fraction"].sum()
            assert (
                abs(fraction_sum - 1.0) < 1e-6
            ), f"Fractions for ({model}, {contract}) sum to {fraction_sum}, not 1.0"

    def test_uses_bidder_column_for_model(self, tmp_path):
        """Discovers model from 'bidder' column when 'model' is absent."""
        df = pd.DataFrame(
            {
                "hand_id": range(60),
                "contract_family": ["suit"] * 30 + ["high"] * 30,
                "tricks_won": [4, 5, 6] * 20,
                "bidder": ["gbt_av"] * 30 + ["ols_av"] * 30,
            }
        )
        parquet_path = tmp_path / "action_value.parquet"
        df.to_parquet(parquet_path)

        rows = _extract_outcome_distributions_from_parquet([parquet_path])
        assert len(rows) > 0
        models = {r["model"] for r in rows}
        assert models == {"gbt_av", "ols_av"}

    def test_all_rows_have_source_parquet(self, tmp_path):
        """All output rows have source='parquet'."""
        df = pd.DataFrame(
            {
                "hand_id": range(30),
                "contract_family": ["suit"] * 30,
                "tricks_won": [4, 5, 6] * 10,
                "model": ["gbt"] * 30,
            }
        )
        parquet_path = tmp_path / "action_value.parquet"
        df.to_parquet(parquet_path)

        rows = _extract_outcome_distributions_from_parquet([parquet_path])
        assert all(r["source"] == "parquet" for r in rows)


# ──────────────────────────────────────────────
#  _make_repo_relative helper
# ──────────────────────────────────────────────


class TestMakeRepoRelative:
    """Tests for _make_repo_relative path normalization."""

    def test_strips_data_prefix(self):
        """Paths containing /data/ are stripped to repo-relative."""
        p = Path("/Users/someone/Projects/repo/data/artifacts/r0/foo.json")
        assert _make_repo_relative(p) == "data/artifacts/r0/foo.json"

    def test_multiple_data_segments(self):
        """First /data/ occurrence is used when path has multiple."""
        p = Path("/home/user/data/extra/data/artifacts/foo.json")
        assert _make_repo_relative(p) == "data/extra/data/artifacts/foo.json"

    def test_fallback_to_basename(self):
        """Paths without /data/ fall back to basename, not absolute path."""
        p = Path("/Users/someone/Projects/repo/docs/report.md")
        result = _make_repo_relative(p)
        assert result == "report.md"
        assert not result.startswith("/")

    def test_relative_path_passthrough(self):
        """Relative paths without /data/ are resolved repo-relative or basename."""
        p = Path("some/local/path.json")
        result = _make_repo_relative(p)
        # With repo root detection, the relative path resolves against cwd
        # (inside the repo), producing a repo-relative result.  Without
        # detection (outside a git repo), falls back to basename.
        assert not result.startswith("/"), "Must not leak absolute paths"
        assert result.endswith("path.json")


# ──────────────────────────────────────────────
#  Provenance generation bug fixes
# ──────────────────────────────────────────────


class TestArtifactInventoryPaths:
    """Regression tests for artifact_inventory path generation."""

    def test_artifact_inventory_distinct_paths(self, tmp_path):
        """Each model must produce a distinct path containing the full model name."""
        rung_dir = tmp_path / "data" / "artifacts" / "arc_d_v2" / "r0"
        rung_dir.mkdir(parents=True)
        model_names = ["full_ols_av", "gbt_av", "selected_ols_av"]
        artifacts = {}
        for name in model_names:
            artifacts[name] = {
                "metadata": {"model_class": "ols", "git_sha": "abc123"},
                "schema_version": "v1",
            }

        df = generate_artifact_inventory(
            training_artifacts=artifacts, rung_dir=rung_dir
        )

        # All paths must be unique
        paths = df["path"].tolist()
        assert len(set(paths)) == len(paths), f"Duplicate paths: {paths}"

        # Each path must contain the full model name
        for name in model_names:
            expected_file = f"training_artifact_{name}.json"
            matching = [p for p in paths if expected_file in p]
            assert (
                len(matching) == 1
            ), f"Expected exactly one path containing {expected_file}, got {matching}"


class TestDatasetProvenanceBugs:
    """Regression tests for dataset_provenance generation."""

    @staticmethod
    def _make_artifact(
        *,
        n_deals=5000,
        dataset_path="/Users/foo/Projects/Bid-Euchre/data/runs/arc_d_v2/ds",
        dataset_sha256=_EMPTY_SHA256,
        model_class="ols",
    ):
        """Build a minimal training artifact dict with metadata."""
        return {
            "metadata": {
                "n_deals": n_deals,
                "dataset_path": dataset_path,
                "dataset_sha256": dataset_sha256,
                "model_class": model_class,
                "training_seed": 42,
            }
        }

    def test_n_rows_from_n_deals(self):
        """n_rows should be populated from metadata.n_deals."""
        artifacts = {"full_ols_av": self._make_artifact(n_deals=5000)}
        df = generate_dataset_provenance(training_artifacts=artifacts)
        assert df.loc[0, "n_rows"] == 5000

    def test_neutralizes_empty_sha256(self):
        """SHA-256 of empty bytes must be replaced with empty string."""
        artifacts = {"gbt_av": self._make_artifact(dataset_sha256=_EMPTY_SHA256)}
        df = generate_dataset_provenance(training_artifacts=artifacts)
        assert df.loc[0, "sha256"] == ""

    def test_preserves_real_sha256(self):
        """A genuine SHA-256 value must be preserved."""
        real_sha = "abc123def456" * 5  # Not the empty-string sentinel
        artifacts = {"gbt_av": self._make_artifact(dataset_sha256=real_sha)}
        df = generate_dataset_provenance(training_artifacts=artifacts)
        assert df.loc[0, "sha256"] == real_sha

    def test_repo_relative_paths(self):
        """Absolute worktree paths must be converted to repo-relative."""
        abs_path = (
            "/Users/foo/Projects/Bid-Euchre-steward-author"
            "/data/runs/arc_d_v2/base_datasets/pre_r3/full"
        )
        artifacts = {"full_ols_av": self._make_artifact(dataset_path=abs_path)}
        df = generate_dataset_provenance(training_artifacts=artifacts)
        result = df.loc[0, "path"]
        assert result.startswith("data/"), f"Expected repo-relative, got: {result}"
        assert not result.startswith("/"), f"Path still absolute: {result}"

    def test_empty_path_stays_empty(self):
        """If dataset_path is empty, it should remain empty (no crash)."""
        artifacts = {"x": self._make_artifact(dataset_path="")}
        df = generate_dataset_provenance(training_artifacts=artifacts)
        assert df.loc[0, "path"] == ""
