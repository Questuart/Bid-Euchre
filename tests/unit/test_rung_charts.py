"""Tests for diagnostic chart generators in generate_rung_charts.py.

Covers:
- predictions scatter plot generation
- residuals histogram generation
- calibration curve generation
- feature importance bar chart generation
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

        generated = charts_mod.generate_all_charts(
            tables_dir=tables_dir,
            output_dir=charts_dir,
            chart_data_dir=chart_data_dir,
        )

        # All 4 new diagnostic charts should be in the generated list
        expected_new = [
            "pred_vs_actual.png",
            "residual_distribution.png",
            "calibration_curve.png",
            "feature_importance.png",
        ]
        for chart in expected_new:
            assert (
                chart in generated
            ), f"Expected {chart} in generated list, got: {generated}"
            assert (charts_dir / chart).exists(), f"{chart} file not found"
            assert (charts_dir / chart).stat().st_size > 0, f"{chart} is empty"
