"""Smoke tests for scripts/generate_dashboard.py."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Add scripts to path so we can import
scripts_dir = str(Path(__file__).resolve().parents[2] / "scripts")
sys.path.insert(0, scripts_dir)
from generate_dashboard import _bollinger, _draw_bollinger_panel  # noqa: E402


class TestBollinger:
    """Tests for the _bollinger computation."""

    def test_empty_data_below_window(self):
        """When data has fewer points than window, all SMA values are NaN."""
        data = np.array([1.0, 2.0, 3.0])
        sma, upper, lower, pct_b = _bollinger(data, window=10, num_std=2)
        assert np.all(np.isnan(sma))
        assert np.all(np.isnan(upper))
        assert np.all(np.isnan(lower))

    def test_basic_computation(self):
        """SMA is correct for a simple known input."""
        data = np.array([2.0, 4.0, 6.0, 8.0, 10.0], dtype=float)
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        # First 2 values should be NaN (window-1)
        assert np.isnan(sma[0])
        assert np.isnan(sma[1])
        # SMA at index 2 = mean([2, 4, 6]) = 4.0
        assert sma[2] == pytest.approx(4.0)
        # SMA at index 3 = mean([4, 6, 8]) = 6.0
        assert sma[3] == pytest.approx(6.0)
        # SMA at index 4 = mean([6, 8, 10]) = 8.0
        assert sma[4] == pytest.approx(8.0)

    def test_constant_data_zero_bandwidth(self):
        """When all values are equal, bands collapse and %B is 0.5."""
        data = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        # band_width is 0 when std=0, so pct_b should be 0.5
        assert pct_b[2] == pytest.approx(0.5)


class TestDrawBollingerPanel:
    """Tests for the panel rendering, especially the n_valid==0 edge case."""

    def test_zero_valid_no_crash(self):
        """Panel renders without error when n_valid is 0 (all NaN SMA)."""
        fig, ax = plt.subplots()
        n = 5
        x = np.arange(n)
        data = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        # All NaN — simulates window > data length
        sma = np.full(n, np.nan)
        upper = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        pct_b = np.full(n, np.nan)
        valid = ~np.isnan(sma)  # All False

        # Should NOT raise ZeroDivisionError
        _draw_bollinger_panel(
            ax,
            x,
            data,
            sma,
            upper,
            lower,
            pct_b,
            valid,
            latest_idx=n - 1,
            band_color="#3498db",
            sma_color="#2980b9",
            dot_color="#2c3e50",
        )
        plt.close(fig)

    def test_normal_rendering(self):
        """Panel renders correctly with valid Bollinger data."""
        fig, ax = plt.subplots()
        data = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        sma, upper, lower, pct_b = _bollinger(data, window=3, num_std=2)
        valid = ~np.isnan(sma)

        _draw_bollinger_panel(
            ax,
            np.arange(5),
            data,
            sma,
            upper,
            lower,
            pct_b,
            valid,
            latest_idx=4,
            band_color="#3498db",
            sma_color="#2980b9",
            dot_color="#2c3e50",
        )
        plt.close(fig)
