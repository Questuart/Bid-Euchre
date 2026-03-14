"""Tests for canonical rung table generation (generate_rung_tables.py).

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

# Import table generators — these are scripts, not library code, so we
# import them via their module path.
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "generate_rung_tables",
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "generate_rung_tables.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

generate_all_tables = _mod.generate_all_tables
generate_comparator_rankings = _mod.generate_comparator_rankings
generate_h2h_delta_matrix = _mod.generate_h2h_delta_matrix
generate_model_performance = _mod.generate_model_performance
generate_behavior_summary = _mod.generate_behavior_summary
generate_behavior_by_contract = _mod.generate_behavior_by_contract
generate_sanity_bounds_check = _mod.generate_sanity_bounds_check
generate_hypothesis_outcomes = _mod.generate_hypothesis_outcomes
generate_rung_model_spec = _mod.generate_rung_model_spec
generate_cross_rung_deltas = _mod.generate_cross_rung_deltas
generate_dataset_provenance = _mod.generate_dataset_provenance
generate_artifact_inventory = _mod.generate_artifact_inventory
generate_data_sanity = _mod.generate_data_sanity


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

    def test_row_count(self, comparator_cis):
        df = generate_comparator_rankings(comparator_cis)
        # One pooled row per bidder
        n_bidders = len(comparator_cis["bidders"])
        assert len(df) == n_bidders

    def test_ranking_order(self, comparator_cis):
        df = generate_comparator_rankings(comparator_cis)
        assert df["rank"].tolist() == list(range(1, len(df) + 1))


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
        # r_squared should be numeric
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
        # All fixture data should pass sanity checks
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

        # Should generate all 12 tables
        assert (
            len(generated) >= 11
        ), f"Generated only {len(generated)} tables: {generated}"

        # Verify each generated CSV exists and is non-empty
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
                continue  # Some tables may be optional
            df = pd.read_csv(csv_path)
            assert list(df.columns) == expected_cols, (
                f"{table_name}.csv columns mismatch: "
                f"got {list(df.columns)}, expected {expected_cols}"
            )
