"""Unit tests for production chart generators."""

import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from bid_euchre.reporting.charts import (
    generate_distribution_charts,
    generate_feature_health_charts,
    generate_feature_outcome_charts,
    generate_strategy_matchup_charts,
)


@pytest.fixture
def feature_df():
    """Minimal DataFrame with hand features."""
    rng = np.random.RandomState(42)
    n = 200
    return pd.DataFrame(
        {
            "hand_value": rng.uniform(0, 10, n),
            "seat": np.tile([0, 1, 2, 3], n // 4),
            "contract_type": np.tile(["suit", "high"], n // 2),
            "trump_count": rng.randint(0, 6, n),
            "bowers": rng.randint(0, 3, n),
            "offsuit_aces": rng.randint(0, 5, n),
            "offsuit_tens_count": rng.randint(0, 5, n),
        }
    )


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

    def test_feature_outcome_includes_by_contract_scatter(self, feature_outcome_df):
        """Generates contract-faceted scatter when contract_type present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_outcome_charts(feature_outcome_df, tmpdir)
            names = [Path(p).stem for p in paths]
            assert "feature_vs_outcome_by_contract" in names

    def test_plot_feature_vs_outcome_by_contract_returns_figure(
        self, feature_outcome_df
    ):
        """Diagnostic function returns Figure with correct subplot count."""
        from bid_euchre.diagnostics.charts import plot_feature_vs_outcome_by_contract

        fig = plot_feature_vs_outcome_by_contract(
            feature_outcome_df, "hand_value", "tricks_won"
        )
        assert isinstance(fig, plt.Figure)
        # feature_outcome_df has contract_type with "suit" and "high" only
        axes = fig.get_axes()
        assert len(axes) == 2  # suit + high (no "low" in fixture)
        plt.close(fig)


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


@pytest.fixture
def matchup_results():
    """Minimal matchup results dict for strategy charts."""
    rng = np.random.RandomState(42)
    strategies = ["greedy", "random"]
    results = {}
    for t0 in strategies:
        for t1 in strategies:
            tricks = rng.randint(0, 11, 50).tolist()
            results[(t0, t1)] = {
                "win_rate": rng.uniform(0.3, 0.7),
                "mean_tricks_team0": np.mean(tricks),
                "mean_tricks_team1": 10 - np.mean(tricks),
                "mean_tricks": np.mean(tricks),
                "tricks_team0": tricks,
                "deals": 50,
            }
    return results


class TestStrategyMatchupCharts:
    """Test strategy matchup chart generation."""

    def test_generates_pngs(self, matchup_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_strategy_matchup_charts(matchup_results, tmpdir)
            assert len(paths) >= 3  # heatmap + tricks_distribution + matchup_summary
            for p in paths:
                assert Path(p).exists()
                assert p.endswith(".png")

    def test_includes_delta_bars_and_self_play(self, matchup_results):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_strategy_matchup_charts(
                matchup_results,
                tmpdir,
                baseline_name="random",
            )
            names = [Path(p).stem for p in paths]
            assert "win_rate_heatmap" in names
            assert "matchup_summary" in names
            assert "self_play_control" in names
            assert "strategy_delta_bars" in names

    def test_no_self_play_skips_gracefully(self):
        """Handles matchup results with no self-play entries."""
        results = {
            ("greedy", "random"): {
                "win_rate": 0.6,
                "mean_tricks_team0": 5.5,
                "mean_tricks_team1": 4.5,
                "mean_tricks": 5.5,
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_strategy_matchup_charts(results, tmpdir)
            assert len(paths) >= 2  # heatmap + tricks_distribution at minimum
            names = [Path(p).stem for p in paths]
            assert "self_play_control" not in names


class TestChartRunnerCLI:
    """Smoke tests for the chart_runner CLI."""

    def test_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "bid_euchre.reporting.chart_runner", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--run-dir" in result.stdout
        assert "--suite" in result.stdout

    def test_missing_run_dir(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "bid_euchre.reporting.chart_runner",
                "--run-dir",
                "/nonexistent/path",
                "--output-dir",
                "/tmp/test_charts",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
