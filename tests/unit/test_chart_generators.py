"""Unit tests for production chart generators."""

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from bid_euchre.reporting.charts import (
    generate_distribution_charts,
    generate_feature_health_charts,
    generate_feature_outcome_charts,
)


@pytest.fixture
def feature_df():
    """Minimal DataFrame with hand features."""
    rng = np.random.RandomState(42)
    n = 200
    return pd.DataFrame({
        "hand_value": rng.uniform(0, 10, n),
        "seat": np.tile([0, 1, 2, 3], n // 4),
        "contract_type": np.tile(["suit", "high"], n // 2),
        "trump_count": rng.randint(0, 6, n),
        "bowers": rng.randint(0, 3, n),
        "offsuit_aces": rng.randint(0, 5, n),
        "offsuit_tens_count": rng.randint(0, 5, n),
    })


@pytest.fixture
def feature_outcome_df(feature_df):
    """DataFrame with features and tricks_won outcome."""
    rng = np.random.RandomState(42)
    df = feature_df.copy()
    df["tricks_won"] = rng.randint(0, 11, len(df))
    return df


class TestFeatureHealthCharts:
    """Test feature health chart generation."""

    def test_generates_pngs(self, feature_df):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_health_charts(feature_df, tmpdir)
            assert len(paths) >= 2  # At minimum seat + contract charts
            for p in paths:
                assert Path(p).exists()
                assert p.endswith(".png")

    def test_creates_output_dir(self, feature_df):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = str(Path(tmpdir) / "sub" / "charts")
            paths = generate_feature_health_charts(feature_df, nested)
            assert len(paths) >= 2
            assert Path(nested).exists()


class TestFeatureOutcomeCharts:
    """Test feature-outcome chart generation."""

    def test_generates_pngs(self, feature_outcome_df):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_outcome_charts(feature_outcome_df, tmpdir)
            assert len(paths) >= 1
            for p in paths:
                assert Path(p).exists()

    def test_empty_features(self):
        """Handles DataFrames with no feature columns gracefully."""
        df = pd.DataFrame({"tricks_won": [5, 6, 7], "contract_type": ["suit"] * 3})
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_outcome_charts(df, tmpdir)
            # Should still generate outcome_distributions at minimum
            assert len(paths) >= 1


class TestDistributionCharts:
    """Test CDF/CCDF chart generation."""

    def test_generates_cdf_ccdf(self, feature_outcome_df):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_distribution_charts(feature_outcome_df, tmpdir)
            assert len(paths) == 2
            names = [Path(p).stem for p in paths]
            assert "cdf" in names
            assert "ccdf" in names

    def test_missing_column_returns_empty(self):
        df = pd.DataFrame({"other": [1, 2, 3]})
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_distribution_charts(df, tmpdir)
            assert len(paths) == 0


class TestChartRunnerCLI:
    """Smoke tests for the chart_runner CLI."""

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "bid_euchre.reporting.chart_runner", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "--run-dir" in result.stdout
        assert "--suite" in result.stdout

    def test_missing_run_dir(self):
        result = subprocess.run(
            [
                sys.executable, "-m", "bid_euchre.reporting.chart_runner",
                "--run-dir", "/nonexistent/path",
                "--output-dir", "/tmp/test_charts",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 1
