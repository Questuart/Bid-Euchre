"""Unit tests for diagnostics chart functions."""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")  # Non-interactive backend for testing

from bid_euchre.diagnostics import plot_ccdf, plot_cdf


class TestPlotCdf:
    """Tests for plot_cdf function."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for testing."""
        np.random.seed(42)
        return pd.DataFrame({
            "feat_hand_value": np.random.randn(100) * 10 + 50,
            "contract_type": np.random.choice(["suit", "high", "low"], 100),
        })

    def test_cdf_returns_figure(self, sample_df):
        """plot_cdf returns a matplotlib Figure."""
        fig = plot_cdf(sample_df, column="feat_hand_value")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_cdf_handles_missing_column(self, sample_df):
        """plot_cdf handles missing column gracefully."""
        fig = plot_cdf(sample_df, column="nonexistent_column")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_cdf_with_group_by(self, sample_df):
        """plot_cdf works with group_by parameter."""
        fig = plot_cdf(sample_df, column="feat_hand_value", group_by="contract_type")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_cdf_with_custom_title(self, sample_df):
        """plot_cdf respects custom title."""
        custom_title = "Custom CDF Title"
        fig = plot_cdf(sample_df, column="feat_hand_value", title=custom_title)
        assert isinstance(fig, plt.Figure)
        # Check that title was set
        ax = fig.axes[0]
        assert ax.get_title() == custom_title
        plt.close(fig)

    def test_cdf_empty_data(self):
        """plot_cdf handles empty DataFrame."""
        empty_df = pd.DataFrame({"feat_hand_value": []})
        fig = plot_cdf(empty_df, column="feat_hand_value")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestPlotCcdf:
    """Tests for plot_ccdf function."""

    @pytest.fixture
    def sample_df(self):
        """Create a sample DataFrame for testing."""
        np.random.seed(42)
        return pd.DataFrame({
            "feat_hand_value": np.random.randn(100) * 10 + 50,
            "contract_type": np.random.choice(["suit", "high", "low"], 100),
        })

    def test_ccdf_returns_figure(self, sample_df):
        """plot_ccdf returns a matplotlib Figure."""
        fig = plot_ccdf(sample_df, column="feat_hand_value")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_ccdf_handles_missing_column(self, sample_df):
        """plot_ccdf handles missing column gracefully."""
        fig = plot_ccdf(sample_df, column="nonexistent_column")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_ccdf_with_group_by(self, sample_df):
        """plot_ccdf works with group_by parameter."""
        fig = plot_ccdf(sample_df, column="feat_hand_value", group_by="contract_type")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_ccdf_log_scale_default(self, sample_df):
        """plot_ccdf uses log scale by default."""
        fig = plot_ccdf(sample_df, column="feat_hand_value")
        ax = fig.axes[0]
        assert ax.get_yscale() == "log"
        plt.close(fig)

    def test_ccdf_linear_scale(self, sample_df):
        """plot_ccdf respects log_scale=False."""
        fig = plot_ccdf(sample_df, column="feat_hand_value", log_scale=False)
        ax = fig.axes[0]
        assert ax.get_yscale() == "linear"
        plt.close(fig)

    def test_ccdf_with_custom_title(self, sample_df):
        """plot_ccdf respects custom title."""
        custom_title = "Custom CCDF Title"
        fig = plot_ccdf(sample_df, column="feat_hand_value", title=custom_title)
        ax = fig.axes[0]
        assert ax.get_title() == custom_title
        plt.close(fig)

    def test_ccdf_empty_data(self):
        """plot_ccdf handles empty DataFrame."""
        empty_df = pd.DataFrame({"feat_hand_value": []})
        fig = plot_ccdf(empty_df, column="feat_hand_value")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)
