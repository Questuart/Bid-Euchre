"""Unit tests for model diagnostic chart functions."""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pytest

matplotlib.use("Agg")  # Non-interactive backend for testing

from bid_euchre.diagnostics.model_charts import (
    plot_calibration_curve,
    plot_dual_arm_comparison,
    plot_model_diagnostics,
)

# ---------------------------------------------------------------------------
# Fixtures: synthetic model data
# ---------------------------------------------------------------------------


def _make_model_data(
    n: int = 200, seed: int = 42
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create synthetic y_true, y_pred, contract_types arrays."""
    rng = np.random.RandomState(seed)
    contract_types = rng.choice(["suit", "high", "low"], size=n)
    y_true = rng.uniform(3, 8, size=n)
    # Predictions = true + noise (correlated)
    y_pred = y_true + rng.normal(0, 0.5, size=n)
    return y_true, y_pred, contract_types


# ---------------------------------------------------------------------------
# Tests: plot_model_diagnostics
# ---------------------------------------------------------------------------


class TestPlotModelDiagnostics:
    """Tests for plot_model_diagnostics function."""

    def test_returns_figure(self) -> None:
        """plot_model_diagnostics returns a matplotlib Figure."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_model_diagnostics(y_true, y_pred, ct)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_has_three_panels(self) -> None:
        """Figure contains 3 visible axes."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_model_diagnostics(y_true, y_pred, ct)
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 3
        plt.close(fig)

    def test_custom_title(self) -> None:
        """Custom title is applied."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_model_diagnostics(y_true, y_pred, ct, title="Custom Diag")
        assert fig._suptitle.get_text() == "Custom Diag"
        plt.close(fig)

    def test_custom_figsize(self) -> None:
        """Custom figsize is respected."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_model_diagnostics(y_true, y_pred, ct, figsize=(15, 5))
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_empty_arrays(self) -> None:
        """Empty arrays handled gracefully."""
        fig = plot_model_diagnostics(
            np.array([]),
            np.array([]),
            np.array([]),
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_contract_type(self) -> None:
        """Works with only one contract type."""
        rng = np.random.RandomState(42)
        n = 50
        y_true = rng.uniform(3, 8, size=n)
        y_pred = y_true + rng.normal(0, 0.5, size=n)
        ct = np.array(["suit"] * n)
        fig = plot_model_diagnostics(y_true, y_pred, ct)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_small_arrays(self) -> None:
        """Works with very small arrays."""
        y_true = np.array([5.0, 6.0, 7.0])
        y_pred = np.array([5.1, 5.8, 7.2])
        ct = np.array(["suit", "high", "low"])
        fig = plot_model_diagnostics(y_true, y_pred, ct)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Tests: plot_dual_arm_comparison
# ---------------------------------------------------------------------------


class TestPlotDualArmComparison:
    """Tests for plot_dual_arm_comparison function."""

    def test_returns_figure_simple(self) -> None:
        """Simple metrics dict produces a Figure."""
        metrics = {
            "OLSa": {"net_eppd": 1.6, "make_rate": 0.70},
            "OLSa_Full": {"net_eppd": 1.5, "make_rate": 0.72},
        }
        fig = plot_dual_arm_comparison(metrics)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_returns_figure_with_r2(self) -> None:
        """Metrics with r2_by_contract shows both panels."""
        metrics = {
            "OLSa": {
                "net_eppd": 1.6,
                "make_rate": 0.70,
                "r2_by_contract": {"suit": 0.35, "high": 0.28, "low": 0.22},
            },
            "OLSa_Full": {
                "net_eppd": 1.5,
                "make_rate": 0.72,
                "r2_by_contract": {"suit": 0.40, "high": 0.30, "low": 0.25},
            },
        }
        fig = plot_dual_arm_comparison(metrics)
        assert isinstance(fig, plt.Figure)
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 2
        plt.close(fig)

    def test_custom_title(self) -> None:
        """Custom title is applied."""
        metrics = {"A": {"x": 1.0}, "B": {"x": 2.0}}
        fig = plot_dual_arm_comparison(metrics, title="Arms Test")
        assert fig._suptitle.get_text() == "Arms Test"
        plt.close(fig)

    def test_empty_metrics(self) -> None:
        """Empty metrics dict handled gracefully."""
        fig = plot_dual_arm_comparison({})
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_arm(self) -> None:
        """Single arm works."""
        metrics = {"OLSa": {"net_eppd": 1.6, "make_rate": 0.7}}
        fig = plot_dual_arm_comparison(metrics)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_panel2_hidden_without_r2(self) -> None:
        """Panel 2 is hidden when no r2_by_contract present."""
        metrics = {
            "OLSa": {"net_eppd": 1.6},
            "OLSa_Full": {"net_eppd": 1.5},
        }
        fig = plot_dual_arm_comparison(metrics)
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 1  # Only panel 1
        plt.close(fig)


# ---------------------------------------------------------------------------
# Tests: plot_calibration_curve
# ---------------------------------------------------------------------------


class TestPlotCalibrationCurve:
    """Tests for plot_calibration_curve function."""

    def test_returns_figure(self) -> None:
        """plot_calibration_curve returns a Figure."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_calibration_curve(y_true, y_pred, ct)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_has_two_panels(self) -> None:
        """Figure contains 2 visible axes."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_calibration_curve(y_true, y_pred, ct)
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 2
        plt.close(fig)

    def test_custom_title(self) -> None:
        """Custom title is applied."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_calibration_curve(y_true, y_pred, ct, title="Cal Test")
        assert fig._suptitle.get_text() == "Cal Test"
        plt.close(fig)

    def test_custom_n_bins(self) -> None:
        """Custom n_bins is accepted."""
        y_true, y_pred, ct = _make_model_data()
        fig = plot_calibration_curve(y_true, y_pred, ct, n_bins=5)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_empty_arrays(self) -> None:
        """Empty arrays handled gracefully."""
        fig = plot_calibration_curve(
            np.array([]),
            np.array([]),
            np.array([]),
        )
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_single_contract_type(self) -> None:
        """Works with only one contract type."""
        rng = np.random.RandomState(42)
        n = 100
        y_true = rng.uniform(3, 8, size=n)
        y_pred = y_true + rng.normal(0, 0.5, size=n)
        ct = np.array(["suit"] * n)
        fig = plot_calibration_curve(y_true, y_pred, ct)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_small_arrays(self) -> None:
        """Works with very small arrays (fewer than n_bins)."""
        y_true = np.array([5.0, 6.0, 7.0])
        y_pred = np.array([5.1, 5.8, 7.2])
        ct = np.array(["suit", "suit", "suit"])
        fig = plot_calibration_curve(y_true, y_pred, ct, n_bins=10)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


# ---------------------------------------------------------------------------
# Teardown: close all figures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _close_all_figures():
    """Close all matplotlib figures after each test to prevent leaks."""
    yield
    plt.close("all")
