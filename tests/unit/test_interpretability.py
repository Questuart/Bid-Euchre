"""Tests for generate_interpretability.py — SHAP shape normalization and chart generation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "internal"
    / "generate_interpretability.py"
)

spec = importlib.util.spec_from_file_location("generate_interpretability", _SCRIPT_PATH)
_mod = importlib.util.module_from_spec(spec)
sys.modules["generate_interpretability"] = _mod
spec.loader.exec_module(_mod)

normalize_shap_values = _mod.normalize_shap_values
generate_shap_interactions_chart = _mod.generate_shap_interactions_chart
_read_csv_safe = _mod._read_csv_safe


# ──────────────────────────────────────────────
#  SHAP shape normalization tests
# ──────────────────────────────────────────────


class TestNormalizeShapValues:
    """Test normalize_shap_values handles all shape variants."""

    def test_2d_passthrough(self):
        """Standard 2D (n_samples, n_features) passes through unchanged."""
        vals = np.random.randn(50, 10)
        result = normalize_shap_values(vals)
        assert result.shape == (50, 10)
        np.testing.assert_array_equal(result, vals)

    def test_1d_reshaped(self):
        """1D array (single feature) is reshaped to (n_samples, 1)."""
        vals = np.random.randn(50)
        result = normalize_shap_values(vals)
        assert result.ndim == 2
        assert result.shape == (50, 1)
        np.testing.assert_array_equal(result[:, 0], vals)

    def test_3d_takes_first_output(self):
        """3D array (multi-output) takes first output slice."""
        vals = np.random.randn(50, 10, 3)
        result = normalize_shap_values(vals)
        assert result.shape == (50, 10)
        np.testing.assert_array_equal(result, vals[:, :, 0])

    def test_list_takes_last_class(self):
        """List of arrays (multi-class) takes last element (positive class)."""
        class_0 = np.random.randn(50, 10)
        class_1 = np.random.randn(50, 10)
        vals = [class_0, class_1]
        result = normalize_shap_values(vals)
        assert result.shape == (50, 10)
        np.testing.assert_array_equal(result, class_1)

    def test_list_single_element(self):
        """List with single element still works."""
        single = np.random.randn(50, 10)
        result = normalize_shap_values([single])
        assert result.shape == (50, 10)
        np.testing.assert_array_equal(result, single)

    def test_list_of_1d(self):
        """List containing 1D arrays — take last, reshape to (n, 1)."""
        vals = [np.random.randn(50), np.random.randn(50)]
        result = normalize_shap_values(vals)
        assert result.ndim == 2
        assert result.shape == (50, 1)
        np.testing.assert_array_equal(result[:, 0], vals[-1])

    def test_list_of_3d(self):
        """List containing 3D arrays — take last element, then first output."""
        vals = [np.random.randn(50, 10, 2), np.random.randn(50, 10, 2)]
        result = normalize_shap_values(vals)
        assert result.shape == (50, 10)
        np.testing.assert_array_equal(result, vals[-1][:, :, 0])

    def test_preserves_values(self):
        """Verify no data corruption during normalization."""
        original = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        result = normalize_shap_values(original)
        np.testing.assert_array_equal(result, original)

    def test_empty_2d(self):
        """Empty 2D array passes through."""
        vals = np.zeros((0, 5))
        result = normalize_shap_values(vals)
        assert result.shape == (0, 5)


# ──────────────────────────────────────────────
#  SHAP interactions chart test
# ──────────────────────────────────────────────


class TestShapInteractionsChart:
    """Test shap_interactions.png generation from CSV."""

    def test_generates_chart_from_csv(self, tmp_path):
        """Verify chart is created when interaction CSV exists."""
        chart_data_dir = tmp_path / "chart_data"
        charts_dir = tmp_path / "charts"
        chart_data_dir.mkdir()
        charts_dir.mkdir()

        # Create test interaction data
        interactions = pd.DataFrame(
            {
                "contract_type": ["suit", "suit", "high", "high"],
                "feature_1": ["trump_count", "trump_count", "ace_count", "ace_count"],
                "feature_2": ["void_count", "ace_count", "king_count", "void_count"],
                "interaction_strength": [0.45, 0.30, 0.55, 0.20],
                "correlation": [0.45, -0.30, 0.55, -0.20],
            }
        )
        interactions.to_csv(chart_data_dir / "shap_interactions.csv", index=False)

        result = generate_shap_interactions_chart(chart_data_dir, charts_dir, dpi=72)
        assert result == "shap_interactions.png"
        assert (charts_dir / "shap_interactions.png").exists()

    def test_returns_none_when_no_csv(self, tmp_path):
        """Returns None when CSV is missing."""
        result = generate_shap_interactions_chart(tmp_path, tmp_path, dpi=72)
        assert result is None

    def test_returns_none_for_empty_csv(self, tmp_path):
        """Returns None when CSV is empty."""
        chart_data_dir = tmp_path / "chart_data"
        chart_data_dir.mkdir()
        # Write empty CSV with just headers
        pd.DataFrame(
            columns=[
                "contract_type",
                "feature_1",
                "feature_2",
                "interaction_strength",
                "correlation",
            ]
        ).to_csv(chart_data_dir / "shap_interactions.csv", index=False)

        result = generate_shap_interactions_chart(chart_data_dir, tmp_path, dpi=72)
        assert result is None
