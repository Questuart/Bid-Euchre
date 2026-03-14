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
    generate_all_tables,
    generate_artifact_inventory,
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
