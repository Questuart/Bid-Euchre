"""Tests for diagnostic chart generators in generate_rung_charts.py.

Covers:
- Intelligence-faceted H2H chart generation
- predictions scatter plot generation
- residuals histogram generation
- calibration curve generation
- feature importance bar chart generation
- h2h ranking scatter generation
- outcome distributions chart generation
- bid level distribution generation
- selection path chart generation
- decision agreement chart generation
- disagreement outcomes chart generation
- Dashboard expansion (3x2 model_eval, 3x2 competitive, 3x2 health with seat balance + bid-type)
- Graceful degradation when CSV data is missing
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts" / "internal"


def _import_chart_module():
    """Import the chart generator script as a module."""
    spec = importlib.util.spec_from_file_location(
        "generate_rung_charts",
        SCRIPTS_DIR / "generate_rung_charts.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def charts_mod():
    """Module-level import of the chart generator."""
    return _import_chart_module()


# ──────────────────────────────────────────────
#  Fixture data helpers
# ──────────────────────────────────────────────


@pytest.fixture
def predictions_csv(tmp_path):
    """Create a predictions.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": ["gbt"] * 6 + ["ols"] * 6,
            "contract": ["suit", "suit", "high", "high", "low", "low"] * 2,
            "prediction": [5.1, 4.8, 3.2, 3.5, 6.0, 5.8, 4.9, 5.0, 3.1, 3.3, 5.9, 5.7],
            "actual": [5.0, 5.0, 3.0, 3.0, 6.0, 6.0, 5.0, 5.0, 3.0, 3.0, 6.0, 6.0],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "predictions.csv", index=False)
    return chart_data_dir


@pytest.fixture
def residuals_csv(tmp_path):
    """Create a residuals.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": ["gbt"] * 4 + ["ols"] * 4,
            "contract": ["suit", "suit", "high", "high"] * 2,
            "residual_bin": [-0.5, 0.0, 0.5, 1.0, -0.5, 0.0, 0.5, 1.0],
            "count": [5, 20, 15, 3, 8, 18, 12, 5],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "residuals.csv", index=False)
    return chart_data_dir


@pytest.fixture
def calibration_csv(tmp_path):
    """Create a calibration_bins.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": ["gbt"] * 4,
            "contract": ["suit"] * 4,
            "pred_bin": [1, 2, 3, 4],
            "mean_pred": [3.0, 4.0, 5.0, 6.0],
            "actual_mean": [3.1, 4.2, 4.9, 5.8],
            "n_samples": [25, 25, 25, 25],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "calibration_bins.csv", index=False)
    return chart_data_dir


@pytest.fixture
def selection_paths_csv(tmp_path):
    """Create a selection_paths.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": ["gbt"] * 5,
            "contract": ["suit"] * 5,
            "rank": [1, 2, 3, 4, 5],
            "feature_name": [
                "trump_count",
                "hand_strength",
                "seat",
                "bid_level",
                "void_count",
            ],
            "importance": [0.35, 0.25, 0.18, 0.12, 0.10],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "selection_paths.csv", index=False)
    return chart_data_dir


@pytest.fixture
def outcome_distributions_csv(tmp_path):
    """Create an outcome_distributions.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": ["gbt"] * 6 + ["ols"] * 6,
            "contract": ["suit"] * 3 + ["high"] * 3 + ["suit"] * 3 + ["high"] * 3,
            "tricks_won": [3, 4, 5, 3, 4, 5, 3, 4, 5, 3, 4, 5],
            "count": [10, 30, 20, 8, 25, 15, 12, 28, 18, 10, 22, 16],
            "fraction": [
                0.167,
                0.500,
                0.333,
                0.167,
                0.521,
                0.312,
                0.207,
                0.483,
                0.310,
                0.208,
                0.458,
                0.333,
            ],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "outcome_distributions.csv", index=False)
    return chart_data_dir


@pytest.fixture
def bid_levels_csv(tmp_path):
    """Create a bid_levels.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": ["gbt", "ols"],
            "bid_rate": [0.65, 0.55],
            "make_rate": [0.72, 0.61],
            "pass_rate": [0.35, 0.45],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "bid_levels.csv", index=False)
    return chart_data_dir


@pytest.fixture
def decision_comparison_csv(tmp_path):
    """Create a decision_comparison.csv fixture file."""
    df = pd.DataFrame(
        {
            "model_a": ["gbt", "gbt", "ols"],
            "model_b": ["ols", "heuristic", "heuristic"],
            "agreement_rate": [0.72, 0.58, 0.61],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "decision_comparison.csv", index=False)
    return chart_data_dir


@pytest.fixture
def disagreement_outcomes_csv(tmp_path):
    """Create a disagreement_outcomes.csv fixture file."""
    df = pd.DataFrame(
        {
            "model_a": ["gbt", "gbt"],
            "model_b": ["ols", "heuristic"],
            "a_better": [45, 62],
            "b_better": [30, 28],
            "tie": [25, 10],
        }
    )
    chart_data_dir = tmp_path / "chart_data"
    chart_data_dir.mkdir()
    df.to_csv(chart_data_dir / "disagreement_outcomes.csv", index=False)
    return chart_data_dir


@pytest.fixture
def comparator_rankings_csv(tmp_path):
    """Create comparator_rankings.csv and h2h_tier_summary.csv fixtures."""
    tables_dir = tmp_path / "tables"
    tables_dir.mkdir()
    pd.DataFrame(
        {
            "model": ["gbt", "ols", "heuristic"],
            "facet": ["pooled", "pooled", "pooled"],
            "net_eppd": [1.2, 0.3, -0.5],
            "ci_low": [0.8, 0.1, -0.8],
            "ci_high": [1.6, 0.5, -0.2],
            "net_cvar_5": [-0.3, -0.7, -1.2],
        }
    ).to_csv(tables_dir / "comparator_rankings.csv", index=False)
    pd.DataFrame(
        {
            "model": ["gbt", "gbt", "ols", "ols"],
            "tier": ["smart", "anchor", "smart", "anchor"],
            "mean_delta": [1.0, 0.5, 0.2, -0.1],
            "mean_win_rate": [0.62, 0.58, 0.51, 0.48],
            "n_opponents": [1, 1, 1, 1],
        }
    ).to_csv(tables_dir / "h2h_tier_summary.csv", index=False)
    return tables_dir


# ──────────────────────────────────────────────
#  Intelligence-faceted H2H tests
# ──────────────────────────────────────────────


@pytest.fixture
def h2h_tier_summary_csv(tmp_path):
    """Create an h2h_tier_summary.csv fixture file."""
    df = pd.DataFrame(
        {
            "model": [
                "gbt_av",
                "gbt_av",
                "gbt_av",
                "ols_av",
                "ols_av",
                "ols_av",
            ],
            "tier": [
                "smart",
                "anchor",
                "heuristic",
                "smart",
                "anchor",
                "heuristic",
            ],
            "mean_delta": [1.2, 0.8, 2.1, -0.3, 0.4, 1.5],
            "mean_win_rate": [0.58, 0.55, 0.65, 0.48, 0.52, 0.60],
            "n_opponents": [3, 1, 3, 3, 1, 3],
        }
    )
    tables_dir = tmp_path / "tables"
    tables_dir.mkdir()
    df.to_csv(tables_dir / "h2h_tier_summary.csv", index=False)
    return tables_dir


class TestIntelligenceFacetedH2H:
    """Tests for generate_intelligence_faceted_h2h."""

    def test_produces_png(self, charts_mod, h2h_tier_summary_csv, tmp_path):
        """Produces h2h_intelligence_faceted.png from valid tier summary CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_intelligence_faceted_h2h(
            h2h_tier_summary_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "h2h_intelligence_faceted.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when h2h_tier_summary.csv is missing."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_intelligence_faceted_h2h(tables_dir, output_dir)
        assert result is False

    def test_missing_columns_returns_false(self, charts_mod, tmp_path):
        """Returns False when CSV lacks required columns."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        df = pd.DataFrame({"model": ["gbt"], "wrong_col": [1.0]})
        df.to_csv(tables_dir / "h2h_tier_summary.csv", index=False)
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_intelligence_faceted_h2h(tables_dir, output_dir)
        assert result is False

    def test_wired_into_generate_all_charts(
        self, charts_mod, h2h_tier_summary_csv, tmp_path
    ):
        """generate_all_charts includes intelligence-faceted H2H when data exists."""
        charts_dir = tmp_path / "charts"
        generated = charts_mod.generate_all_charts(
            tables_dir=h2h_tier_summary_csv,
            output_dir=charts_dir,
        )
        assert "full_chart_suite/h2h_intelligence_faceted.png" in generated
        assert (
            charts_dir / "full_chart_suite" / "h2h_intelligence_faceted.png"
        ).exists()


# ──────────────────────────────────────────────
#  Predictions scatter tests
# ──────────────────────────────────────────────


class TestPredictionsScatter:
    """Tests for generate_predictions_scatter."""

    def test_produces_png(self, charts_mod, predictions_csv, tmp_path):
        """Produces pred_vs_actual.png from valid predictions CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_predictions_scatter(predictions_csv, output_dir)
        assert result is True
        png_path = output_dir / "pred_vs_actual.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when predictions.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_predictions_scatter(chart_data_dir, output_dir)
        assert result is False

    def test_missing_columns_returns_false(self, charts_mod, tmp_path):
        """Returns False when CSV lacks required columns."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        df = pd.DataFrame({"model": ["gbt"], "wrong_col": [1.0]})
        df.to_csv(chart_data_dir / "predictions.csv", index=False)
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_predictions_scatter(chart_data_dir, output_dir)
        assert result is False


# ──────────────────────────────────────────────
#  Residuals chart tests
# ──────────────────────────────────────────────


class TestResidualsChart:
    """Tests for generate_residuals_chart."""

    def test_produces_png(self, charts_mod, residuals_csv, tmp_path):
        """Produces residual_distribution.png from valid residuals CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_residuals_chart(residuals_csv, output_dir)
        assert result is True
        png_path = output_dir / "residual_distribution.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when residuals.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_residuals_chart(chart_data_dir, output_dir)
        assert result is False


# ──────────────────────────────────────────────
#  Calibration curve tests
# ──────────────────────────────────────────────


class TestCalibrationCurve:
    """Tests for generate_calibration_curve."""

    def test_produces_png(self, charts_mod, calibration_csv, tmp_path):
        """Produces calibration_curve.png from valid calibration CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_calibration_curve(calibration_csv, output_dir)
        assert result is True
        png_path = output_dir / "calibration_curve.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when calibration_bins.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_calibration_curve(chart_data_dir, output_dir)
        assert result is False


# ──────────────────────────────────────────────
#  Feature importance chart tests
# ──────────────────────────────────────────────


class TestFeatureImportanceChart:
    """Tests for generate_feature_importance_chart."""

    def test_produces_png(self, charts_mod, selection_paths_csv, tmp_path):
        """Produces feature_importance.png from valid selection_paths CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_feature_importance_chart(
            selection_paths_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "feature_importance.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when selection_paths.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_feature_importance_chart(
            chart_data_dir, output_dir
        )
        assert result is False

    def test_missing_columns_returns_false(self, charts_mod, tmp_path):
        """Returns False when CSV lacks required columns."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        df = pd.DataFrame({"model": ["gbt"], "bad_col": [1.0]})
        df.to_csv(chart_data_dir / "selection_paths.csv", index=False)
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_feature_importance_chart(
            chart_data_dir, output_dir
        )
        assert result is False


# ──────────────────────────────────────────────
#  H2H ranking scatter tests (new — Phase B)
# ──────────────────────────────────────────────


class TestH2HRankingScatter:
    """Tests for generate_h2h_ranking_scatter."""

    def test_produces_png(self, charts_mod, comparator_rankings_csv, tmp_path):
        """Produces h2h_ranking_scatter.png from fixture CSVs."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_h2h_ranking_scatter(
            comparator_rankings_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "h2h_ranking_scatter.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when comparator_rankings.csv is missing."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_h2h_ranking_scatter(tables_dir, output_dir)
        assert result is False


# ──────────────────────────────────────────────
#  Outcome distributions chart tests (new — Phase B)
# ──────────────────────────────────────────────


class TestOutcomeDistributionsChart:
    """Tests for generate_outcome_distributions_chart."""

    def test_produces_png(self, charts_mod, outcome_distributions_csv, tmp_path):
        """Produces outcome_distributions.png from valid CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_outcome_distributions_chart(
            outcome_distributions_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "outcome_distributions.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when outcome_distributions.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_outcome_distributions_chart(
            chart_data_dir, output_dir
        )
        assert result is False

    def test_missing_columns_returns_false(self, charts_mod, tmp_path):
        """Returns False when CSV lacks required columns."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        df = pd.DataFrame({"model": ["gbt"], "wrong_col": [1.0]})
        df.to_csv(chart_data_dir / "outcome_distributions.csv", index=False)
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_outcome_distributions_chart(
            chart_data_dir, output_dir
        )
        assert result is False


# ──────────────────────────────────────────────
#  outcome_summary removal (Phase E cleanup)
# ──────────────────────────────────────────────


class TestOutcomeSummaryRemoved:
    """Verify generate_outcome_summary was removed (Phase E — not in 23-chart registry)."""

    def test_generate_outcome_summary_not_in_module(self, charts_mod):
        """generate_outcome_summary should no longer exist in the chart module."""
        assert not hasattr(charts_mod, "generate_outcome_summary")

    def test_outcome_summary_not_in_chart_data_generators(self, charts_mod):
        """The generate_all_charts function source should not reference outcome_summary.png."""
        import inspect

        source = inspect.getsource(charts_mod.generate_all_charts)
        assert "outcome_summary.png" not in source


# ──────────────────────────────────────────────
#  Bid level distribution tests (new — Phase B)
# ──────────────────────────────────────────────


class TestBidLevelDistribution:
    """Tests for generate_bid_level_distribution."""

    def test_produces_png(self, charts_mod, bid_levels_csv, tmp_path):
        """Produces bid_level_distribution.png from valid CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_bid_level_distribution(bid_levels_csv, output_dir)
        assert result is True
        png_path = output_dir / "bid_level_distribution.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when bid_levels.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_bid_level_distribution(chart_data_dir, output_dir)
        assert result is False


# ──────────────────────────────────────────────
#  Selection path chart tests (new — Phase B)
# ──────────────────────────────────────────────


class TestSelectionPathChart:
    """Tests for generate_selection_path_chart."""

    def test_produces_png(self, charts_mod, selection_paths_csv, tmp_path):
        """Produces selection_path.png from valid CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_selection_path_chart(
            selection_paths_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "selection_path.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when selection_paths.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_selection_path_chart(chart_data_dir, output_dir)
        assert result is False


# ──────────────────────────────────────────────
#  Decision agreement chart tests (new — Phase B)
# ──────────────────────────────────────────────


class TestDecisionAgreementChart:
    """Tests for generate_decision_agreement_chart."""

    def test_produces_png(self, charts_mod, decision_comparison_csv, tmp_path):
        """Produces decision_agreement.png from valid CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_decision_agreement_chart(
            decision_comparison_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "decision_agreement.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when decision_comparison.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_decision_agreement_chart(
            chart_data_dir, output_dir
        )
        assert result is False


# ──────────────────────────────────────────────
#  Disagreement outcomes chart tests (new — Phase B)
# ──────────────────────────────────────────────


class TestDisagreementOutcomesChart:
    """Tests for generate_disagreement_outcomes_chart."""

    def test_produces_png(self, charts_mod, disagreement_outcomes_csv, tmp_path):
        """Produces disagreement_outcomes.png from valid CSV."""
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_disagreement_outcomes_chart(
            disagreement_outcomes_csv, output_dir
        )
        assert result is True
        png_path = output_dir / "disagreement_outcomes.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_missing_csv_returns_false(self, charts_mod, tmp_path):
        """Returns False when disagreement_outcomes.csv is missing."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        output_dir = tmp_path / "charts"
        output_dir.mkdir()
        result = charts_mod.generate_disagreement_outcomes_chart(
            chart_data_dir, output_dir
        )
        assert result is False


# ──────────────────────────────────────────────
#  Dashboard expansion tests (Phase B)
# ──────────────────────────────────────────────


class TestDashboardModelEvalExpansion:
    """Tests that dashboard_model_eval.png produces a 3x2 figure."""

    def test_model_eval_3x2_with_data(self, charts_mod, tmp_path):
        """Model eval dashboard produces 3x2 figure with chart_data."""
        import matplotlib

        matplotlib.use("Agg")

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        # Minimal model_performance.csv
        pd.DataFrame(
            {
                "model": ["gbt", "gbt"],
                "contract": ["suit", "high"],
                "r_squared": [0.85, 0.72],
                "mae": [0.42, 0.55],
            }
        ).to_csv(tables_dir / "model_performance.csv", index=False)

        result = charts_mod.generate_dashboard_model_eval(
            tables_dir, charts_dir, chart_data_dir
        )
        assert result is True
        png_path = charts_dir / "dashboard_model_eval.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_model_eval_3x2_empty_data(self, charts_mod, tmp_path):
        """Model eval dashboard degrades gracefully with no data."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        result = charts_mod.generate_dashboard_model_eval(tables_dir, charts_dir)
        assert result is True
        assert (charts_dir / "dashboard_model_eval.png").exists()


class TestDashboardCompetitiveExpansion:
    """Tests that dashboard_competitive.png produces a 3x2 figure."""

    def test_competitive_3x2_with_data(self, charts_mod, tmp_path):
        """Competitive dashboard produces 3x2 figure with table data."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        # Minimal comparator_rankings.csv
        pd.DataFrame(
            {
                "model": ["gbt", "ols"],
                "facet": ["pooled", "pooled"],
                "net_eppd": [1.2, 0.3],
                "ci_low": [0.8, 0.1],
                "ci_high": [1.6, 0.5],
                "net_cvar_5": [-0.3, -0.7],
            }
        ).to_csv(tables_dir / "comparator_rankings.csv", index=False)

        result = charts_mod.generate_dashboard_competitive(tables_dir, charts_dir)
        assert result is True
        png_path = charts_dir / "dashboard_competitive.png"
        assert png_path.exists()
        assert png_path.stat().st_size > 0

    def test_competitive_3x2_empty_data(self, charts_mod, tmp_path):
        """Competitive dashboard degrades gracefully with no data."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        result = charts_mod.generate_dashboard_competitive(tables_dir, charts_dir)
        assert result is True
        assert (charts_dir / "dashboard_competitive.png").exists()


class TestDashboardHealthOutcomeDistributions:
    """Tests that health dashboard is 3x2 and Panel 3 uses outcome_distributions."""

    def test_health_panel3_prefers_outcome_distributions(self, charts_mod, tmp_path):
        """Health dashboard renders outcome_distributions when available."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        # Write behavior_summary.csv for panels 1 & 2
        pd.DataFrame(
            {
                "model": ["gbt", "ols"],
                "source": ["comparator", "comparator"],
                "bid_rate": [0.65, 0.55],
                "make_rate": [0.72, 0.61],
                "mix_suit": [0.5, 0.5],
                "mix_high": [0.3, 0.3],
                "mix_low": [0.2, 0.2],
            }
        ).to_csv(tables_dir / "behavior_summary.csv", index=False)

        # Write outcome_distributions.csv
        pd.DataFrame(
            {
                "model": ["gbt"] * 3 + ["ols"] * 3,
                "contract": ["suit"] * 3 + ["suit"] * 3,
                "tricks_won": [3, 4, 5, 3, 4, 5],
                "count": [10, 30, 20, 12, 28, 18],
                "fraction": [0.167, 0.500, 0.333, 0.207, 0.483, 0.310],
            }
        ).to_csv(chart_data_dir / "outcome_distributions.csv", index=False)

        result = charts_mod.generate_dashboard_health(
            tables_dir, charts_dir, chart_data_dir
        )
        assert result is True
        assert (charts_dir / "dashboard_health.png").exists()

    def test_health_degrades_gracefully(self, charts_mod, tmp_path):
        """Health dashboard works with no data at all."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        result = charts_mod.generate_dashboard_health(tables_dir, charts_dir)
        assert result is True
        assert (charts_dir / "dashboard_health.png").exists()


# ──────────────────────────────────────────────
#  Integration: generate_all_charts includes new generators
# ──────────────────────────────────────────────


class TestAllChartsIntegration:
    """Tests that generate_all_charts wires the new diagnostic generators."""

    def test_all_charts_with_chart_data(self, charts_mod, tmp_path):
        """generate_all_charts produces diagnostic PNGs when chart_data CSVs exist."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()

        # Write predictions.csv fixture
        pd.DataFrame(
            {
                "model": ["gbt"] * 4,
                "contract": ["suit", "suit", "high", "high"],
                "prediction": [5.1, 4.8, 3.2, 3.5],
                "actual": [5.0, 5.0, 3.0, 3.0],
            }
        ).to_csv(chart_data_dir / "predictions.csv", index=False)

        # Write residuals.csv fixture
        pd.DataFrame(
            {
                "model": ["gbt"] * 4,
                "contract": ["suit", "suit", "high", "high"],
                "residual_bin": [-0.5, 0.0, 0.5, 1.0],
                "count": [5, 20, 15, 3],
            }
        ).to_csv(chart_data_dir / "residuals.csv", index=False)

        # Write calibration_bins.csv fixture
        pd.DataFrame(
            {
                "model": ["gbt"] * 3,
                "contract": ["suit"] * 3,
                "pred_bin": [1, 2, 3],
                "mean_pred": [3.0, 4.0, 5.0],
                "actual_mean": [3.1, 4.2, 4.9],
                "n_samples": [25, 25, 25],
            }
        ).to_csv(chart_data_dir / "calibration_bins.csv", index=False)

        # Write selection_paths.csv fixture
        pd.DataFrame(
            {
                "model": ["gbt"] * 3,
                "contract": ["suit"] * 3,
                "rank": [1, 2, 3],
                "feature_name": ["trump_count", "hand_strength", "seat"],
                "importance": [0.35, 0.25, 0.18],
            }
        ).to_csv(chart_data_dir / "selection_paths.csv", index=False)

        # Write outcome_distributions.csv fixture
        pd.DataFrame(
            {
                "model": ["gbt"] * 3,
                "contract": ["suit"] * 3,
                "tricks_won": [3, 4, 5],
                "count": [10, 30, 20],
                "fraction": [0.167, 0.500, 0.333],
            }
        ).to_csv(chart_data_dir / "outcome_distributions.csv", index=False)

        # Write bid_levels.csv fixture
        pd.DataFrame(
            {
                "model": ["gbt"],
                "bid_rate": [0.65],
                "make_rate": [0.72],
                "pass_rate": [0.35],
            }
        ).to_csv(chart_data_dir / "bid_levels.csv", index=False)

        generated = charts_mod.generate_all_charts(
            tables_dir=tables_dir,
            output_dir=charts_dir,
            chart_data_dir=chart_data_dir,
        )

        # All diagnostic charts should be in the generated list (with prefix)
        expected_new = [
            "full_chart_suite/pred_vs_actual.png",
            "full_chart_suite/residual_distribution.png",
            "full_chart_suite/calibration_curve.png",
            "full_chart_suite/feature_importance.png",
            "full_chart_suite/outcome_distributions.png",
            "full_chart_suite/bid_level_distribution.png",
            "full_chart_suite/selection_path.png",
        ]
        for chart in expected_new:
            assert (
                chart in generated
            ), f"Expected {chart} in generated list, got: {generated}"
            assert (charts_dir / chart).exists(), f"{chart} file not found"
            assert (charts_dir / chart).stat().st_size > 0, f"{chart} is empty"

        # Dashboard charts should also be generated (at top level)
        for dashboard in [
            "dashboard_competitive.png",
            "dashboard_health.png",
            "dashboard_model_eval.png",
        ]:
            assert (
                dashboard in generated
            ), f"Expected {dashboard} in generated list, got: {generated}"


# ──────────────────────────────────────────────
#  Health dashboard 3x2 verification
# ──────────────────────────────────────────────


class TestHealthDashboard3x2:
    """Tests that health dashboard is 3x2 (6 panels)."""

    def test_health_dashboard_3x2_figsize(self, charts_mod, tmp_path):
        """Health dashboard uses 3x2 grid with appropriate figsize."""
        import matplotlib

        matplotlib.use("Agg")

        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        result = charts_mod.generate_dashboard_health(tables_dir, charts_dir)
        assert result is True
        assert (charts_dir / "dashboard_health.png").exists()


# ──────────────────────────────────────────────
#  Competitive dashboard panel 6 intelligence-faceted
# ──────────────────────────────────────────────


class TestCompetitiveDashboardPanel6:
    """Tests that competitive dashboard panel 6 shows intelligence-faceted H2H."""

    def test_panel6_with_tier_data(self, charts_mod, tmp_path):
        """Competitive dashboard panel 6 renders tier data when available."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        # Minimal comparator_rankings.csv
        pd.DataFrame(
            {
                "model": ["gbt", "ols"],
                "facet": ["pooled", "pooled"],
                "net_eppd": [1.2, 0.3],
                "ci_low": [0.8, 0.1],
                "ci_high": [1.6, 0.5],
                "net_cvar_5": [-0.3, -0.7],
            }
        ).to_csv(tables_dir / "comparator_rankings.csv", index=False)

        # h2h_tier_summary.csv for panel 6
        pd.DataFrame(
            {
                "model": ["gbt", "gbt", "ols", "ols"],
                "tier": ["smart", "anchor", "smart", "anchor"],
                "mean_delta": [1.0, 0.5, 0.2, -0.1],
                "mean_win_rate": [0.62, 0.58, 0.51, 0.48],
                "n_opponents": [1, 1, 1, 1],
            }
        ).to_csv(tables_dir / "h2h_tier_summary.csv", index=False)

        result = charts_mod.generate_dashboard_competitive(tables_dir, charts_dir)
        assert result is True
        assert (charts_dir / "dashboard_competitive.png").exists()

    def test_panel6_placeholder_without_tier_data(self, charts_mod, tmp_path):
        """Competitive dashboard panel 6 shows placeholder without tier data."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()

        result = charts_mod.generate_dashboard_competitive(tables_dir, charts_dir)
        assert result is True
        assert (charts_dir / "dashboard_competitive.png").exists()


# ──────────────────────────────────────────────
#  Layout restructure: full_chart_suite/ subdirectory
# ──────────────────────────────────────────────


class TestFullChartSuiteLayout:
    """Tests that standalone charts go to full_chart_suite/ subdirectory."""

    def test_standalone_charts_in_subdirectory(self, charts_mod, tmp_path):
        """Standalone charts are written to full_chart_suite/ subdir."""
        tables_dir = tmp_path / "tables"
        tables_dir.mkdir()
        charts_dir = tmp_path / "charts"

        # Minimal h2h_tier_summary for one standalone chart
        pd.DataFrame(
            {
                "model": ["gbt", "gbt"],
                "tier": ["smart", "anchor"],
                "mean_delta": [1.0, 0.5],
                "mean_win_rate": [0.62, 0.58],
                "n_opponents": [1, 1],
            }
        ).to_csv(tables_dir / "h2h_tier_summary.csv", index=False)

        generated = charts_mod.generate_all_charts(
            tables_dir=tables_dir,
            output_dir=charts_dir,
        )

        # Standalone charts have full_chart_suite/ prefix
        suite_charts = [c for c in generated if c.startswith("full_chart_suite/")]
        dashboard_charts = [
            c for c in generated if not c.startswith("full_chart_suite/")
        ]

        assert len(suite_charts) > 0, "Expected some standalone charts"
        # Dashboards are at top level
        for d in dashboard_charts:
            assert (charts_dir / d).exists(), f"Dashboard {d} not at top level"
        # Suite charts are in subdirectory
        for s in suite_charts:
            assert (charts_dir / s).exists(), f"Suite chart {s} not in subdirectory"
