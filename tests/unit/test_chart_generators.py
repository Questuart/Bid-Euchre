"""Unit tests for production chart generators."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from bid_euchre.reporting.charts import (
    generate_contract_faceted_charts,
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

    def test_self_play_by_contract_with_scenarios(self, matchup_results):
        """Generates per-contract self-play chart when scenarios present."""
        # Add scenarios to self-play entries
        for key in list(matchup_results.keys()):
            team0, team1 = key
            if team0 == team1:
                matchup_results[key]["scenarios"] = {
                    "suit_C": {"avg_team0": 5.1, "deals": 50},
                    "suit_D": {"avg_team0": 4.9, "deals": 50},
                    "suit_H": {"avg_team0": 5.0, "deals": 50},
                    "suit_S": {"avg_team0": 5.2, "deals": 50},
                    "high": {"avg_team0": 4.8, "deals": 50},
                    "low": {"avg_team0": 5.3, "deals": 50},
                }
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_strategy_matchup_charts(matchup_results, tmpdir)
            names = [Path(p).stem for p in paths]
            assert "self_play_by_contract" in names

    def test_self_play_by_contract_skips_without_scenarios(self, matchup_results):
        """No error when matchup results lack scenarios key."""
        # matchup_results fixture doesn't have scenarios by default
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_strategy_matchup_charts(matchup_results, tmpdir)
            names = [Path(p).stem for p in paths]
            assert "self_play_by_contract" not in names


@pytest.fixture
def feature_outcome_with_trump_df(feature_outcome_df):
    """DataFrame with features, outcomes, and trump_suit column."""
    df = feature_outcome_df.copy()
    rng = np.random.RandomState(42)
    suits = ["C", "D", "H", "S", None]  # None for no-trump contracts
    df["trump_suit"] = rng.choice(suits, len(df))
    return df


class TestContractFacetedCharts:
    """Test contract-faceted chart generation."""

    def test_generates_pngs_with_full_data(self, feature_outcome_with_trump_df):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_contract_faceted_charts(
                feature_outcome_with_trump_df, tmpdir
            )
            assert len(paths) >= 2
            for p in paths:
                assert Path(p).exists()
                assert p.endswith(".png")

    def test_skips_when_no_trump_data(self):
        """Handles DataFrames with no trump suit info."""
        df = pd.DataFrame(
            {
                "hand_value": [5.0, 6.0, 7.0],
                "contract_type": ["high", "high", "low"],
                "tricks_won": [5, 6, 4],
            }
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not crash; trump-dependent charts may be skipped or show placeholder
            paths = generate_contract_faceted_charts(df, tmpdir)
            # Some charts may still be generated (outcome_by_trump shows placeholder)
            # Key assertion: no crash
            assert isinstance(paths, list)

    def test_file_sizes_reasonable(self, feature_outcome_with_trump_df):
        """Generated PNGs should not be tiny placeholders."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_contract_faceted_charts(
                feature_outcome_with_trump_df, tmpdir
            )
            for p in paths:
                size = Path(p).stat().st_size
                assert size > 1024, f"{p} is suspiciously small ({size} bytes)"

    def test_contract_faceted_in_available_suites(self):
        from bid_euchre.reporting.chart_runner import AVAILABLE_SUITES

        assert "contract_faceted" in AVAILABLE_SUITES


class TestChartContentValidity:
    """Assert production charts render actual data, not placeholder text."""

    def test_feature_health_all_charts_have_content(
        self, feature_outcome_with_trump_df
    ):
        """All feature_health charts should be non-trivial after normalization fix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_health_charts(
                feature_outcome_with_trump_df, tmpdir
            )
            assert len(paths) >= 4  # seat, contract, distributions, correlation
            for p in paths:
                assert (
                    Path(p).stat().st_size > 2048
                ), f"{Path(p).name} suspiciously small"

    def test_feature_outcome_all_charts_have_content(
        self, feature_outcome_with_trump_df
    ):
        """All feature_outcome charts should render with normalized data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_outcome_charts(
                feature_outcome_with_trump_df, tmpdir
            )
            assert len(paths) >= 3  # correlation, scatter, outcome_distributions
            for p in paths:
                assert (
                    Path(p).stat().st_size > 2048
                ), f"{Path(p).name} suspiciously small"

    def test_normalized_features_found(self):
        """After normalization, diagnostic functions should find feat_ columns."""
        from bid_euchre.reporting.charts import _normalize_for_diagnostics

        df = pd.DataFrame(
            {
                "hand_value": [100, 200],
                "trump_count": [3, 4],
                "trump_suit": ["H", "S"],
                "tricks_won": [5, 6],
            }
        )
        norm = _normalize_for_diagnostics(df)
        feat_cols = [c for c in norm.columns if c.startswith("feat_")]
        assert len(feat_cols) >= 2
        assert "feat_hand_value" in norm.columns
        assert "trump" in norm.columns

    def test_feature_health_includes_seat_and_contract_chart(self, feature_df):
        """Feature health suite includes hand_value_by_seat_and_contract chart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_health_charts(feature_df, tmpdir)
            names = [Path(p).stem for p in paths]
            assert "hand_value_by_seat_and_contract" in names

    def test_hand_value_by_seat_and_contract_returns_figure(self, feature_df):
        """Diagnostic function returns Figure with correct subplot count."""
        from bid_euchre.diagnostics.charts import plot_hand_value_by_seat_and_contract
        from bid_euchre.reporting.charts import _normalize_for_diagnostics

        df = _normalize_for_diagnostics(feature_df)
        fig = plot_hand_value_by_seat_and_contract(df)
        assert isinstance(fig, plt.Figure)
        axes = fig.get_axes()
        assert len(axes) == 2  # suit + high (no "low" in fixture)
        plt.close(fig)

    def test_coefficient_heatmap_returns_figure(self):
        """Coefficient heatmap renders with sample data."""
        from bid_euchre.diagnostics.charts import plot_coefficient_heatmap

        coefs = {
            "suit": pd.Series({"bowers": 0.5, "trump_count": 0.3, "rank_sum": -0.2}),
            "high": pd.Series({"bowers": 0.1, "trump_count": 0.0, "rank_sum": 0.4}),
            "low": pd.Series({"bowers": -0.1, "trump_count": 0.2, "rank_sum": 0.5}),
        }
        fig = plot_coefficient_heatmap(coefs, top_n=3)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestLoadMatchupResults:
    """Tests for _load_matchup_results loader with scenario extension."""

    def test_legacy_aggregate_keys(self, tmp_path):
        """Legacy aggregate keys (win_rate, mean_tricks_*, deals) are populated."""
        from bid_euchre.reporting.chart_runner import _load_matchup_results

        matchup_dir = tmp_path / "results" / "greedy_vs_random"
        matchup_dir.mkdir(parents=True)
        scenario = {
            "win_rate_team0": 0.65,
            "avg_team0": 5.5,
            "avg_team1": 4.5,
            "deals": 100,
            "distribution_team0": {"3": 10, "5": 60, "7": 30},
        }
        (matchup_dir / "suit_C.json").write_text(json.dumps(scenario))

        results = _load_matchup_results(tmp_path)
        assert ("greedy", "random") in results
        r = results[("greedy", "random")]
        assert r["win_rate"] == pytest.approx(0.65)
        assert r["mean_tricks_team0"] == pytest.approx(5.5)
        assert r["mean_tricks_team1"] == pytest.approx(4.5)
        assert r["mean_tricks"] == pytest.approx(5.5)
        assert r["deals"] == 100
        assert len(r["tricks_team0"]) == 100  # 10+60+30

    def test_multi_scenario_aggregation(self, tmp_path):
        """Multiple scenario files are weighted-averaged correctly."""
        from bid_euchre.reporting.chart_runner import _load_matchup_results

        matchup_dir = tmp_path / "results" / "glutton_vs_greedy"
        matchup_dir.mkdir(parents=True)

        s1 = {
            "win_rate_team0": 0.80,
            "avg_team0": 6.0,
            "avg_team1": 4.0,
            "deals": 200,
        }
        s2 = {
            "win_rate_team0": 0.60,
            "avg_team0": 5.0,
            "avg_team1": 5.0,
            "deals": 100,
        }
        (matchup_dir / "suit_H.json").write_text(json.dumps(s1))
        (matchup_dir / "high.json").write_text(json.dumps(s2))

        results = _load_matchup_results(tmp_path)
        r = results[("glutton", "greedy")]
        assert r["deals"] == 300
        # Weighted average: (0.80*200 + 0.60*100) / 300 = 220/300
        assert r["win_rate"] == pytest.approx(220.0 / 300)
        assert r["mean_tricks_team0"] == pytest.approx((6.0 * 200 + 5.0 * 100) / 300)
        assert r["mean_tricks_team1"] == pytest.approx((4.0 * 200 + 5.0 * 100) / 300)

    def test_scenarios_key_populated(self, tmp_path):
        """Per-scenario breakdown is available under result['scenarios']."""
        from bid_euchre.reporting.chart_runner import _load_matchup_results

        matchup_dir = tmp_path / "results" / "greedy_vs_random"
        matchup_dir.mkdir(parents=True)

        for name in ["suit_C", "suit_D", "high", "low"]:
            data = {
                "win_rate_team0": 0.5,
                "avg_team0": 5.0,
                "avg_team1": 5.0,
                "deals": 50,
            }
            (matchup_dir / f"{name}.json").write_text(json.dumps(data))

        results = _load_matchup_results(tmp_path)
        r = results[("greedy", "random")]
        assert "scenarios" in r
        assert set(r["scenarios"].keys()) == {"suit_C", "suit_D", "high", "low"}
        # Each scenario preserves raw data
        assert r["scenarios"]["suit_C"]["deals"] == 50
        assert r["scenarios"]["high"]["avg_team0"] == 5.0

    def test_empty_results_dir(self, tmp_path):
        """Returns empty dict when results/ has no matchup subdirectories."""
        from bid_euchre.reporting.chart_runner import _load_matchup_results

        (tmp_path / "results").mkdir()
        assert _load_matchup_results(tmp_path) == {}

    def test_no_results_dir(self, tmp_path):
        """Returns empty dict when results/ does not exist."""
        from bid_euchre.reporting.chart_runner import _load_matchup_results

        assert _load_matchup_results(tmp_path) == {}

    def test_tricks_team0_absent_without_distribution(self, tmp_path):
        """tricks_team0 key absent when scenario lacks distribution_team0."""
        from bid_euchre.reporting.chart_runner import _load_matchup_results

        matchup_dir = tmp_path / "results" / "a_vs_b"
        matchup_dir.mkdir(parents=True)
        data = {
            "win_rate_team0": 0.5,
            "avg_team0": 5.0,
            "avg_team1": 5.0,
            "deals": 10,
        }
        (matchup_dir / "high.json").write_text(json.dumps(data))

        results = _load_matchup_results(tmp_path)
        assert "tricks_team0" not in results[("a", "b")]


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
