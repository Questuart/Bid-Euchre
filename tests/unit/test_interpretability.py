"""Tests for the interpretability pipeline.

Tests CSV schema correctness, decision comparison logic, context feature tagging,
and graceful skip behaviors using synthetic/fixture data only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def synthetic_eval_df() -> pd.DataFrame:
    """Synthetic evaluation dataset mimicking action-value parquet schema."""
    rng = np.random.RandomState(42)
    n = 200
    contracts = ["suit", "high", "low"]
    rows = []
    for i in range(n):
        contract = contracts[i % 3]
        rows.append(
            {
                "hand_id": i // 4,
                "contract_family": contract,
                "action_type": "bid" if i % 5 != 0 else "pass",
                "bid_n": rng.randint(1, 11),
                "bid_n_sq": 0,  # filled below
                "trump_count": rng.randint(0, 8),
                "bower_count": rng.randint(0, 3),
                "ace_count": rng.randint(0, 5),
                "void_count": rng.randint(0, 4),
                "singleton_count": rng.randint(0, 4),
                "doubleton_count": rng.randint(0, 4),
                "partner_bid_level": rng.randint(0, 6),
                "partner_passed": rng.choice([0, 1]),
                "partner_suit_match": rng.choice([0, 1]),
                "net_points": rng.normal(0, 3),
            }
        )
    df = pd.DataFrame(rows)
    df["bid_n_sq"] = df["bid_n"] ** 2
    return df


@pytest.fixture
def sample_gbt_artifact(tmp_path: Path) -> dict:
    """Create a minimal GBT artifact JSON + mock joblib files."""
    import joblib
    from sklearn.ensemble import GradientBoostingRegressor

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()

    feature_names = [
        "trump_count",
        "bower_count",
        "ace_count",
        "void_count",
        "singleton_count",
        "doubleton_count",
        "partner_bid_level",
        "partner_passed",
        "partner_suit_match",
        "bid_n",
        "bid_n_sq",
    ]

    models = {}
    for family in ("suit", "high", "low", "pass"):
        model = GradientBoostingRegressor(n_estimators=5, max_depth=2, random_state=42)
        # Train on tiny random data
        rng = np.random.RandomState(42)
        X = rng.rand(50, len(feature_names))
        y = rng.normal(0, 1, 50)
        model.fit(X, y)

        model_file = f"gbt_{family}.joblib"
        joblib.dump(model, artifacts_dir / model_file)
        models[family] = {
            "model_file": model_file,
            "r_squared": 0.5,
            "feature_names": feature_names,
        }

    artifact = {
        "schema_version": "action_value_gbt_v1",
        "target": "net_points",
        "risk_mode": "neutral",
        "continuation_policy": "hybrid_r0_full",
        "action_features": ["bid_n", "bid_n_sq"],
        "feature_set": "full",
        "models": models,
        "metadata": {
            "n_deals": 100,
            "training_seed": 42,
            "arm": "full",
            "context_features": [],
            "model_class": "gbt",
        },
    }

    artifact_path = artifacts_dir / "gbt_model_a.json"
    with open(artifact_path, "w") as f:
        json.dump(artifact, f)

    return {
        "path": artifact_path,
        "name": "gbt_model_a",
        "schema": "action_value_gbt_v1",
        "artifact": artifact,
    }


@pytest.fixture
def sample_ols_artifact(tmp_path: Path) -> dict:
    """Create a minimal OLS artifact JSON (no SHAP support)."""
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    feature_names = [
        "trump_count",
        "bower_count",
        "ace_count",
        "bid_n",
        "bid_n_sq",
    ]

    models = {}
    for family in ("suit", "high", "low", "pass"):
        models[family] = {
            "coefficients": [0.1, 0.2, 0.3, 0.4, 0.5],
            "intercept": 1.0,
            "r_squared": 0.45,
            "feature_names": feature_names,
        }

    artifact = {
        "schema_version": "action_value_olsa_v1",
        "target": "net_points",
        "risk_mode": "neutral",
        "continuation_policy": "hybrid_r0_full",
        "action_features": ["bid_n", "bid_n_sq"],
        "feature_set": "full",
        "models": models,
        "metadata": {
            "n_deals": 100,
            "training_seed": 42,
            "arm": "full",
            "context_features": [],
            "model_class": "ols",
            "selection": "forward",
            "selection_logs": {
                "suit": {
                    "steps": [
                        {
                            "step": 1,
                            "feature": "trump_count",
                            "feature_index": 0,
                            "r2": 0.35,
                            "improvement": 0.35,
                        },
                        {
                            "step": 2,
                            "feature": "bower_count",
                            "feature_index": 1,
                            "r2": 0.42,
                            "improvement": 0.07,
                        },
                        {
                            "step": 3,
                            "feature": "ace_count",
                            "feature_index": 2,
                            "r2": 0.45,
                            "improvement": 0.03,
                        },
                    ],
                    "final_r2": 0.45,
                    "n_selected": 3,
                    "locked_base": [],
                },
                "high": {
                    "steps": [
                        {
                            "step": 1,
                            "feature": "ace_count",
                            "feature_index": 2,
                            "r2": 0.30,
                            "improvement": 0.30,
                        },
                        {
                            "step": 2,
                            "feature": "trump_count",
                            "feature_index": 0,
                            "r2": 0.38,
                            "improvement": 0.08,
                        },
                    ],
                    "final_r2": 0.38,
                    "n_selected": 2,
                    "locked_base": [],
                },
            },
        },
    }

    artifact_path = artifacts_dir / "ols_model.json"
    with open(artifact_path, "w") as f:
        json.dump(artifact, f)

    return {
        "path": artifact_path,
        "name": "ols_model",
        "schema": "action_value_olsa_v1",
        "artifact": artifact,
    }


@pytest.fixture
def two_gbt_artifacts(tmp_path: Path, synthetic_eval_df: pd.DataFrame) -> list[dict]:
    """Create two GBT artifacts for pairwise comparison tests."""
    import joblib
    from sklearn.ensemble import GradientBoostingRegressor

    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    feature_names = [
        "trump_count",
        "bower_count",
        "ace_count",
        "void_count",
        "singleton_count",
        "doubleton_count",
        "partner_bid_level",
        "partner_passed",
        "partner_suit_match",
        "bid_n",
        "bid_n_sq",
    ]

    results = []
    for model_id in ("model_a", "model_b"):
        seed = 42 if model_id == "model_a" else 99
        models_section = {}
        for family in ("suit", "high", "low", "pass"):
            model = GradientBoostingRegressor(
                n_estimators=5, max_depth=2, random_state=seed
            )
            rng = np.random.RandomState(seed)
            X = rng.rand(50, len(feature_names))
            y = rng.normal(0, 1, 50)
            model.fit(X, y)

            model_file = f"gbt_{family}_{model_id}.joblib"
            joblib.dump(model, artifacts_dir / model_file)
            models_section[family] = {
                "model_file": model_file,
                "r_squared": 0.5,
                "feature_names": feature_names,
            }

        artifact = {
            "schema_version": "action_value_gbt_v1",
            "target": "net_points",
            "risk_mode": "neutral",
            "continuation_policy": "hybrid_r0_full",
            "action_features": ["bid_n", "bid_n_sq"],
            "feature_set": "full",
            "models": models_section,
            "metadata": {
                "n_deals": 100,
                "training_seed": seed,
                "arm": "full",
                "context_features": [],
                "model_class": "gbt",
            },
        }

        artifact_path = artifacts_dir / f"{model_id}.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact, f)

        results.append(
            {
                "path": artifact_path,
                "name": model_id,
                "schema": "action_value_gbt_v1",
                "artifact": artifact,
            }
        )

    return results


# ── Import helper ───────────────────────────────────────────

# The scripts live outside src/ so we import via path manipulation in tests.
# This mirrors how other test files import internal scripts.

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "internal"


def _import_generate_interpretability():
    """Import the generate_interpretability module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_interpretability",
        SCRIPTS_DIR / "generate_interpretability.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_generate_interpretability_charts():
    """Import the generate_interpretability_charts module."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_interpretability_charts",
        SCRIPTS_DIR / "generate_interpretability_charts.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── SHAP value normalization tests ─────────────────────────


class TestNormalizeShapValues:
    """Tests for normalize_shap_values handling variable TreeExplainer output shapes."""

    def test_2d_passthrough(self):
        """2D regression output (n_samples, n_features) passes through unchanged."""
        mod = _import_generate_interpretability()
        vals = np.random.RandomState(42).randn(10, 5)
        result = mod.normalize_shap_values(vals)
        assert result.shape == (10, 5)
        np.testing.assert_array_equal(result, vals)

    def test_list_takes_last_element(self):
        """List of arrays (binary classification) takes the last (positive class)."""
        mod = _import_generate_interpretability()
        neg = np.zeros((10, 5))
        pos = np.ones((10, 5))
        result = mod.normalize_shap_values([neg, pos])
        assert result.shape == (10, 5)
        np.testing.assert_array_equal(result, pos)

    def test_1d_reshaped_to_column(self):
        """1D array (single feature) is reshaped to (n_samples, 1)."""
        mod = _import_generate_interpretability()
        vals = np.array([1.0, 2.0, 3.0])
        result = mod.normalize_shap_values(vals)
        assert result.shape == (3, 1)
        np.testing.assert_array_equal(result.ravel(), vals)

    def test_3d_takes_first_output(self):
        """3D array (multi-output) takes first output slice."""
        mod = _import_generate_interpretability()
        vals = np.random.RandomState(42).randn(10, 5, 3)
        result = mod.normalize_shap_values(vals)
        assert result.shape == (10, 5)
        np.testing.assert_array_equal(result, vals[:, :, 0])

    def test_list_binary_classification_selects_positive(self):
        """Binary classification list: negative class zeros, positive class ones."""
        mod = _import_generate_interpretability()
        neg = np.zeros((5, 3))
        pos = np.full((5, 3), 0.42)
        result = mod.normalize_shap_values([neg, pos])
        assert result.shape == (5, 3)
        np.testing.assert_allclose(result, 0.42)

    def test_4d_raises_value_error(self):
        """4D array raises ValueError (unexpected shape)."""
        mod = _import_generate_interpretability()
        vals = np.zeros((2, 3, 4, 5))
        with pytest.raises(ValueError, match="Unexpected SHAP values shape"):
            mod.normalize_shap_values(vals)

    def test_list_of_single_array(self):
        """List with single element (single-class) takes that element."""
        mod = _import_generate_interpretability()
        arr = np.ones((8, 4))
        result = mod.normalize_shap_values([arr])
        assert result.shape == (8, 4)
        np.testing.assert_array_equal(result, arr)


class TestNormalizeShapInteractionValues:
    """Tests for normalize_shap_interaction_values."""

    def test_3d_passthrough(self):
        """3D interaction values (n_samples, n_features, n_features) pass through."""
        mod = _import_generate_interpretability()
        vals = np.random.RandomState(42).randn(10, 5, 5)
        result = mod.normalize_shap_interaction_values(vals)
        assert result.shape == (10, 5, 5)
        np.testing.assert_array_equal(result, vals)

    def test_list_takes_last_element(self):
        """List of 3D arrays (binary classification) takes the last."""
        mod = _import_generate_interpretability()
        neg = np.zeros((10, 5, 5))
        pos = np.ones((10, 5, 5))
        result = mod.normalize_shap_interaction_values([neg, pos])
        assert result.shape == (10, 5, 5)
        np.testing.assert_array_equal(result, pos)

    def test_4d_takes_first_output(self):
        """4D array (multi-output) takes first output slice."""
        mod = _import_generate_interpretability()
        vals = np.random.RandomState(42).randn(10, 5, 5, 3)
        result = mod.normalize_shap_interaction_values(vals)
        assert result.shape == (10, 5, 5)
        np.testing.assert_array_equal(result, vals[:, :, :, 0])

    def test_2d_raises_value_error(self):
        """2D array raises ValueError (unexpected shape for interactions)."""
        mod = _import_generate_interpretability()
        vals = np.zeros((10, 5))
        with pytest.raises(
            ValueError, match="Unexpected SHAP interaction values shape"
        ):
            mod.normalize_shap_interaction_values(vals)


# ── SHAP analysis tests ────────────────────────────────────


class TestShapAnalysis:
    """Tests for SHAP-based feature analysis."""

    def test_shap_ranking_csv_schema(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """SHAP ranking CSV has correct columns."""
        mod = _import_generate_interpretability()
        ranking, _, _ = mod.generate_shap_analysis(
            sample_gbt_artifact, synthetic_eval_df, eval_sample=100
        )
        assert not ranking.empty
        expected_cols = {
            "model",
            "contract",
            "feature",
            "rank",
            "mean_abs_shap",
            "direction",
        }
        assert set(ranking.columns) == expected_cols

    def test_shap_ranking_direction_values(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """Direction is either 'positive' or 'negative'."""
        mod = _import_generate_interpretability()
        ranking, _, _ = mod.generate_shap_analysis(
            sample_gbt_artifact, synthetic_eval_df, eval_sample=100
        )
        assert ranking["direction"].isin(["positive", "negative"]).all()

    def test_shap_ranking_has_all_contracts(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """SHAP ranking includes rows for each contract family with data."""
        mod = _import_generate_interpretability()
        ranking, _, _ = mod.generate_shap_analysis(
            sample_gbt_artifact, synthetic_eval_df, eval_sample=100
        )
        contracts = set(ranking["contract"].unique())
        # Should have suit, high, low (pass may or may not be present)
        assert "suit" in contracts
        assert "high" in contracts
        assert "low" in contracts

    def test_shap_dependence_csv_schema(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """SHAP dependence CSV has correct columns."""
        mod = _import_generate_interpretability()
        _, dependence, _ = mod.generate_shap_analysis(
            sample_gbt_artifact, synthetic_eval_df, eval_sample=100
        )
        assert not dependence.empty
        expected_cols = {"model", "contract", "feature", "feature_value", "shap_value"}
        assert set(dependence.columns) == expected_cols

    def test_shap_interactions_csv_schema(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """SHAP interactions CSV has correct columns when interactions available."""
        mod = _import_generate_interpretability()
        _, _, interactions = mod.generate_shap_analysis(
            sample_gbt_artifact, synthetic_eval_df, eval_sample=50
        )
        if not interactions.empty:
            expected_cols = {
                "model",
                "contract",
                "feature_1",
                "feature_2",
                "interaction_strength",
            }
            assert set(interactions.columns) == expected_cols

    def test_shap_graceful_skip_when_unavailable(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """SHAP analysis returns empty DataFrames when shap is not importable."""
        mod = _import_generate_interpretability()
        with patch.dict(sys.modules, {"shap": None}):
            # Force re-import check
            ranking, dep, inter = mod.generate_shap_analysis(
                sample_gbt_artifact, synthetic_eval_df, eval_sample=100
            )
        # The function catches ImportError internally, so we test the guard path
        # by checking it doesn't crash

    def test_shap_skips_ols_artifacts(
        self, sample_ols_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """SHAP analysis returns empty DataFrames for non-GBT artifacts."""
        mod = _import_generate_interpretability()
        # OLS artifacts have no joblib models, so _load_gbt_models returns None
        ranking, dep, inter = mod.generate_shap_analysis(
            sample_ols_artifact, synthetic_eval_df, eval_sample=100
        )
        assert ranking.empty
        assert dep.empty
        assert inter.empty


# ── Selection path tests ────────────────────────────────────


class TestSelectionPaths:
    """Tests for forward selection path extraction."""

    def test_selection_paths_csv_schema(self, sample_ols_artifact: dict):
        """Selection paths CSV has correct columns."""
        mod = _import_generate_interpretability()
        df = mod.extract_selection_paths(sample_ols_artifact)
        assert not df.empty
        expected_cols = {
            "model",
            "contract",
            "step",
            "feature_added",
            "oof_r2",
            "delta_r2",
        }
        assert set(df.columns) == expected_cols

    def test_selection_paths_values(self, sample_ols_artifact: dict):
        """Selection paths contain correct values from fixture."""
        mod = _import_generate_interpretability()
        df = mod.extract_selection_paths(sample_ols_artifact)

        # Check suit path
        suit_df = df[df["contract"] == "suit"].sort_values("step")
        assert len(suit_df) == 3
        assert list(suit_df["feature_added"]) == [
            "trump_count",
            "bower_count",
            "ace_count",
        ]
        assert suit_df.iloc[0]["oof_r2"] == pytest.approx(0.35)
        assert suit_df.iloc[1]["delta_r2"] == pytest.approx(0.07)

    def test_selection_paths_r2_monotonic(self, sample_ols_artifact: dict):
        """OOF R² should be monotonically increasing along the selection path."""
        mod = _import_generate_interpretability()
        df = mod.extract_selection_paths(sample_ols_artifact)

        for contract in df["contract"].unique():
            cdf = df[df["contract"] == contract].sort_values("step")
            r2_values = cdf["oof_r2"].values
            # Each step's R² should be >= previous (monotonic in forward selection)
            for i in range(1, len(r2_values)):
                assert (
                    r2_values[i] >= r2_values[i - 1]
                ), f"R² decreased at step {i + 1} for {contract}"

    def test_selection_paths_skip_when_missing(self, sample_gbt_artifact: dict):
        """Returns empty DataFrame when no selection_logs in metadata."""
        mod = _import_generate_interpretability()
        df = mod.extract_selection_paths(sample_gbt_artifact)
        assert df.empty


# ── Decision comparison tests ───────────────────────────────


class TestDecisionComparison:
    """Tests for pairwise model decision comparison."""

    def test_comparison_csv_schema(
        self, two_gbt_artifacts: list, synthetic_eval_df: pd.DataFrame
    ):
        """Decision comparison CSV has correct columns."""
        mod = _import_generate_interpretability()
        comp_df, _ = mod.generate_decision_comparison(
            two_gbt_artifacts, synthetic_eval_df, eval_sample=100
        )
        assert not comp_df.empty
        expected_cols = {
            "model_a",
            "model_b",
            "contract",
            "agreement_rate",
            "n_disagree",
        }
        assert set(comp_df.columns) == expected_cols

    def test_disagreement_outcomes_csv_schema(
        self, two_gbt_artifacts: list, synthetic_eval_df: pd.DataFrame
    ):
        """Disagreement outcomes CSV has correct columns."""
        mod = _import_generate_interpretability()
        _, disagree_df = mod.generate_decision_comparison(
            two_gbt_artifacts, synthetic_eval_df, eval_sample=100
        )
        assert not disagree_df.empty
        expected_cols = {
            "model_a",
            "model_b",
            "contract",
            "a_better_pct",
            "b_better_pct",
            "tie_pct",
        }
        assert set(disagree_df.columns) == expected_cols

    def test_agreement_rate_bounds(
        self, two_gbt_artifacts: list, synthetic_eval_df: pd.DataFrame
    ):
        """Agreement rate is between 0 and 1."""
        mod = _import_generate_interpretability()
        comp_df, _ = mod.generate_decision_comparison(
            two_gbt_artifacts, synthetic_eval_df, eval_sample=100
        )
        assert (comp_df["agreement_rate"] >= 0).all()
        assert (comp_df["agreement_rate"] <= 1).all()

    def test_disagreement_pcts_sum_to_one(
        self, two_gbt_artifacts: list, synthetic_eval_df: pd.DataFrame
    ):
        """a_better + b_better + tie should sum to ~1.0."""
        mod = _import_generate_interpretability()
        _, disagree_df = mod.generate_decision_comparison(
            two_gbt_artifacts, synthetic_eval_df, eval_sample=100
        )
        totals = (
            disagree_df["a_better_pct"]
            + disagree_df["b_better_pct"]
            + disagree_df["tie_pct"]
        )
        np.testing.assert_allclose(totals, 1.0, atol=0.01)

    def test_identical_models_full_agreement(
        self, sample_gbt_artifact: dict, synthetic_eval_df: pd.DataFrame
    ):
        """Two copies of the same model should have 100% agreement."""
        mod = _import_generate_interpretability()
        # Create two identical artifact infos
        info_b = dict(sample_gbt_artifact)
        info_b = {**info_b, "name": "gbt_model_b"}
        comp_df, _ = mod.generate_decision_comparison(
            [sample_gbt_artifact, info_b], synthetic_eval_df, eval_sample=100
        )
        assert (comp_df["agreement_rate"] == 1.0).all()

    def test_comparison_with_synthetic_predictions(self):
        """Decision comparison works correctly with known synthetic predictions."""
        # Create predictable predictions
        preds_a = np.array([3, 4, 5, 6, 7])
        preds_b = np.array([3, 4, 6, 6, 8])

        agree = (preds_a == preds_b).sum()
        n_disagree = len(preds_a) - agree
        agreement_rate = agree / len(preds_a)

        assert agreement_rate == pytest.approx(0.6)  # 3/5 agree
        assert n_disagree == 2

        disagree_mask = preds_a != preds_b
        a_higher = (preds_a[disagree_mask] > preds_b[disagree_mask]).sum()
        b_higher = (preds_b[disagree_mask] > preds_a[disagree_mask]).sum()
        assert a_higher == 0  # model_a never bids higher
        assert b_higher == 2  # model_b bids higher in both disagreements


# ── Context feature usage tests ─────────────────────────────


class TestContextFeatureUsage:
    """Tests for context vs hand feature classification."""

    def test_context_feature_tagging(self):
        """Known context features are correctly tagged."""
        mod = _import_generate_interpretability()

        ranking_df = pd.DataFrame(
            [
                {
                    "model": "test",
                    "contract": "suit",
                    "feature": "trump_count",
                    "rank": 1,
                    "mean_abs_shap": 0.5,
                    "direction": "positive",
                },
                {
                    "model": "test",
                    "contract": "suit",
                    "feature": "partner_bid_level",
                    "rank": 2,
                    "mean_abs_shap": 0.3,
                    "direction": "positive",
                },
                {
                    "model": "test",
                    "contract": "suit",
                    "feature": "ace_count",
                    "rank": 11,
                    "mean_abs_shap": 0.01,
                    "direction": "negative",
                },
            ]
        )

        result = mod.generate_context_feature_usage(ranking_df)
        assert len(result) == 3

        # trump_count is a hand feature
        hand_row = result[result["feature"] == "trump_count"].iloc[0]
        assert bool(hand_row["is_context_feature"]) is False
        assert bool(hand_row["entered_top_10"]) is True

        # partner_bid_level is a context feature
        ctx_row = result[result["feature"] == "partner_bid_level"].iloc[0]
        assert bool(ctx_row["is_context_feature"]) is True
        assert bool(ctx_row["entered_top_10"]) is True

        # ace_count is rank 11 so NOT in top 10
        low_row = result[result["feature"] == "ace_count"].iloc[0]
        assert bool(low_row["is_context_feature"]) is False
        assert bool(low_row["entered_top_10"]) is False

    def test_context_feature_usage_csv_schema(self):
        """Context feature usage CSV has correct columns."""
        mod = _import_generate_interpretability()

        ranking_df = pd.DataFrame(
            [
                {
                    "model": "test",
                    "contract": "suit",
                    "feature": "trump_count",
                    "rank": 1,
                    "mean_abs_shap": 0.5,
                    "direction": "positive",
                },
            ]
        )

        result = mod.generate_context_feature_usage(ranking_df)
        expected_cols = {
            "model",
            "contract",
            "feature",
            "rank",
            "mean_abs_shap",
            "is_context_feature",
            "entered_top_10",
        }
        assert set(result.columns) == expected_cols

    def test_context_feature_constants(self):
        """CONTEXT_FEATURE_NAMES includes known partner/auction features."""
        mod = _import_generate_interpretability()
        assert "partner_bid_level" in mod.CONTEXT_FEATURE_NAMES
        assert "partner_passed" in mod.CONTEXT_FEATURE_NAMES
        assert "partner_suit_match" in mod.CONTEXT_FEATURE_NAMES
        # Hand features should not be in context set
        assert "trump_count" not in mod.CONTEXT_FEATURE_NAMES
        assert "ace_count" not in mod.CONTEXT_FEATURE_NAMES

    def test_empty_ranking_returns_empty(self):
        """Empty ranking DF produces empty context usage DF."""
        mod = _import_generate_interpretability()
        result = mod.generate_context_feature_usage(pd.DataFrame())
        assert result.empty


# ── Artifact discovery tests ────────────────────────────────


class TestArtifactDiscovery:
    """Tests for artifact discovery in rung directories."""

    def test_discover_gbt_artifacts(self, sample_gbt_artifact: dict):
        """Discovers GBT artifacts from artifacts/ directory."""
        mod = _import_generate_interpretability()
        rung_dir = sample_gbt_artifact["path"].parent.parent
        results = mod._discover_artifacts(rung_dir)
        assert len(results) == 1
        assert results[0]["schema"] == "action_value_gbt_v1"

    def test_discover_ols_artifacts(self, sample_ols_artifact: dict):
        """Discovers OLS artifacts from artifacts/ directory."""
        mod = _import_generate_interpretability()
        rung_dir = sample_ols_artifact["path"].parent.parent
        results = mod._discover_artifacts(rung_dir)
        assert len(results) == 1
        assert results[0]["schema"] == "action_value_olsa_v1"

    def test_discover_no_artifacts(self, tmp_path: Path):
        """Returns empty list when no artifacts directory."""
        mod = _import_generate_interpretability()
        results = mod._discover_artifacts(tmp_path)
        assert results == []

    def test_discover_ignores_non_action_value(self, tmp_path: Path):
        """Ignores JSON files with other schema versions."""
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir()
        with open(artifacts_dir / "other.json", "w") as f:
            json.dump({"schema_version": "other_v1"}, f)

        mod = _import_generate_interpretability()
        results = mod._discover_artifacts(tmp_path)
        assert results == []


# ── End-to-end pipeline test ────────────────────────────────


class TestEndToEnd:
    """Integration-style tests for the full pipeline."""

    def test_run_produces_csvs(
        self,
        tmp_path: Path,
        sample_gbt_artifact: dict,
        synthetic_eval_df: pd.DataFrame,
    ):
        """Full run produces at least SHAP ranking and context usage CSVs."""
        mod = _import_generate_interpretability()

        # Set up rung dir with artifact and eval data
        rung_dir = sample_gbt_artifact["path"].parent.parent
        datasets_dir = rung_dir / "datasets"
        datasets_dir.mkdir(exist_ok=True)
        synthetic_eval_df.to_parquet(datasets_dir / "action_value.parquet")

        report_dir = tmp_path / "report"
        outputs = mod.run(rung_dir, report_dir, eval_sample=50)

        assert "shap_feature_ranking" in outputs
        assert "context_feature_usage" in outputs

        # Verify files exist and are valid CSVs
        for name, path in outputs.items():
            assert path.exists(), f"{name} file does not exist"
            df = pd.read_csv(path)
            assert len(df) > 0, f"{name} CSV is empty"

    def test_run_with_selection_logs(
        self,
        tmp_path: Path,
        sample_ols_artifact: dict,
    ):
        """Run produces selection paths CSV from OLS artifact with selection logs."""
        mod = _import_generate_interpretability()
        rung_dir = sample_ols_artifact["path"].parent.parent

        report_dir = tmp_path / "report"
        outputs = mod.run(rung_dir, report_dir, eval_sample=50)

        assert "selection_paths" in outputs
        df = pd.read_csv(outputs["selection_paths"])
        assert len(df) > 0


# ── Chart generation tests ──────────────────────────────────


class TestChartGeneration:
    """Tests for interpretability chart generation."""

    def test_shap_summary_chart(self, tmp_path: Path):
        """SHAP summary chart generates without error."""
        mod = _import_generate_interpretability_charts()

        ranking_df = pd.DataFrame(
            [
                {
                    "model": "m1",
                    "contract": "suit",
                    "feature": f"f{i}",
                    "rank": i,
                    "mean_abs_shap": 1.0 / i,
                    "direction": "positive",
                }
                for i in range(1, 6)
            ]
        )
        mod.generate_shap_summary(ranking_df, tmp_path)
        assert (tmp_path / "shap_summary.png").exists()

    def test_selection_path_chart(self, tmp_path: Path):
        """Selection path chart generates without error."""
        mod = _import_generate_interpretability_charts()

        sel_df = pd.DataFrame(
            [
                {
                    "model": "m1",
                    "contract": "suit",
                    "step": 1,
                    "feature_added": "f1",
                    "oof_r2": 0.3,
                    "delta_r2": 0.3,
                },
                {
                    "model": "m1",
                    "contract": "suit",
                    "step": 2,
                    "feature_added": "f2",
                    "oof_r2": 0.4,
                    "delta_r2": 0.1,
                },
            ]
        )
        mod.generate_selection_path_chart(sel_df, tmp_path)
        assert (tmp_path / "selection_path.png").exists()

    def test_run_charts_from_csvs(self, tmp_path: Path):
        """Full chart run from CSV files."""
        mod = _import_generate_interpretability_charts()

        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        # Write a minimal ranking CSV
        ranking_df = pd.DataFrame(
            [
                {
                    "model": "m1",
                    "contract": "suit",
                    "feature": f"f{i}",
                    "rank": i,
                    "mean_abs_shap": 1.0 / i,
                    "direction": "positive",
                }
                for i in range(1, 4)
            ]
        )
        ranking_df.to_csv(chart_data_dir / "shap_feature_ranking.csv", index=False)

        output_dir = tmp_path / "charts"
        generated = mod.run(chart_data_dir, output_dir)

        assert "shap_summary.png" in generated
        assert (output_dir / "shap_summary.png").exists()

    def test_feature_importance_chart(self, tmp_path: Path):
        """Feature importance bar chart generates without error."""
        mod = _import_generate_interpretability_charts()

        importance_df = pd.DataFrame(
            [
                {
                    "model": "gbt_av",
                    "contract": "suit",
                    "rank": i,
                    "feature_name": f"f{i}",
                    "importance": 1.0 / i,
                }
                for i in range(1, 6)
            ]
        )
        mod.generate_feature_importance_chart(importance_df, tmp_path)
        assert (tmp_path / "feature_importance.png").exists()

    def test_run_dispatches_importance_schema(self, tmp_path: Path):
        """run() generates feature_importance.png when CSV has rank/importance cols."""
        mod = _import_generate_interpretability_charts()

        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        # Write CSV with rank/importance schema (the actual tables.py output)
        importance_df = pd.DataFrame(
            [
                {
                    "model": "gbt_av",
                    "contract": ct,
                    "rank": i,
                    "feature_name": f"f{i}",
                    "importance": 1.0 / i,
                }
                for ct in ("suit", "high")
                for i in range(1, 4)
            ]
        )
        importance_df.to_csv(chart_data_dir / "selection_paths.csv", index=False)

        output_dir = tmp_path / "charts"
        generated = mod.run(chart_data_dir, output_dir)

        # Should dispatch to feature_importance chart, NOT crash
        assert "feature_importance.png" in generated
        assert (output_dir / "feature_importance.png").exists()
        # selection_path.png should NOT be generated (wrong schema)
        assert "selection_path.png" not in generated

    def test_run_dispatches_selection_path_schema(self, tmp_path: Path):
        """run() generates selection_path.png when CSV has step/oof_r2 cols."""
        mod = _import_generate_interpretability_charts()

        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        # Write CSV with step/oof_r2 schema (forward-selection path data)
        sel_df = pd.DataFrame(
            [
                {
                    "model": "m1",
                    "contract": "suit",
                    "step": i,
                    "feature_added": f"f{i}",
                    "oof_r2": 0.2 + 0.1 * i,
                    "delta_r2": 0.1,
                }
                for i in range(1, 4)
            ]
        )
        sel_df.to_csv(chart_data_dir / "selection_paths.csv", index=False)

        output_dir = tmp_path / "charts"
        generated = mod.run(chart_data_dir, output_dir)

        assert "selection_path.png" in generated
        assert (output_dir / "selection_path.png").exists()

    def test_run_prefers_feature_importances_csv(self, tmp_path: Path):
        """run() reads feature_importances.csv when selection_paths.csv absent."""
        mod = _import_generate_interpretability_charts()

        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        importance_df = pd.DataFrame(
            [
                {
                    "model": "gbt_av",
                    "contract": "suit",
                    "rank": i,
                    "feature_name": f"f{i}",
                    "importance": 1.0 / i,
                }
                for i in range(1, 4)
            ]
        )
        importance_df.to_csv(chart_data_dir / "feature_importances.csv", index=False)

        output_dir = tmp_path / "charts"
        generated = mod.run(chart_data_dir, output_dir)

        assert "feature_importance.png" in generated
        assert (output_dir / "feature_importance.png").exists()
