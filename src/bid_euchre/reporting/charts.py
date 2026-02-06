"""Production chart generators for reporting.

Wraps diagnostic chart functions to save PNGs and return manifests.
Each generator takes a run directory, saves charts to output_dir,
and returns a list of generated file paths.

Boundary:
- diagnostics/ = exploratory, returns Figure objects, notebook-facing
- reporting/ = production, saves PNGs, returns manifests, CLI-runnable
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd

from ..diagnostics.charts import (
    plot_ccdf,
    plot_cdf,
    plot_feature_correlation,
    plot_feature_distributions,
    plot_feature_outcome_correlation,
    plot_feature_vs_outcome,
    plot_hand_value_by_contract,
    plot_hand_value_by_seat,
    plot_outcome_distributions,
)
from ..diagnostics.strategy_charts import (
    plot_matchup_summary,
    plot_self_play_control,
    plot_strategy_delta_bars,
    plot_tricks_distribution_comparison,
    plot_win_rate_heatmap,
)


def _save_figure(fig: plt.Figure, output_dir: Path, name: str, dpi: int = 150) -> str:
    """Save a figure and close it. Returns the output path."""
    path = output_dir / f"{name}.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def generate_feature_health_charts(
    df: pd.DataFrame,
    output_dir: str,
    top_features: int = 9,
    dpi: int = 150,
) -> List[str]:
    """Generate feature health check charts.

    Produces:
    - hand_value_by_seat.png
    - hand_value_by_contract.png
    - feature_distributions.png
    - feature_correlation.png

    Args:
        df: DataFrame with hand features (from bidless.parquet).
        output_dir: Directory to save PNGs.
        top_features: Number of features for distribution grid.
        dpi: Output resolution.

    Returns:
        List of generated file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    fig = plot_hand_value_by_seat(df)
    paths.append(_save_figure(fig, out, "hand_value_by_seat", dpi))

    fig = plot_hand_value_by_contract(df)
    paths.append(_save_figure(fig, out, "hand_value_by_contract", dpi))

    # Select top features by variance for distributions
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    feature_cols = [c for c in numeric_cols if c not in ("seat", "deal_id", "hand_id")]
    if feature_cols:
        variances = df[feature_cols].var().sort_values(ascending=False)
        top = variances.head(top_features).index.tolist()
        fig = plot_feature_distributions(df, features=top)
        paths.append(_save_figure(fig, out, "feature_distributions", dpi))

        fig = plot_feature_correlation(df, features=top)
        paths.append(_save_figure(fig, out, "feature_correlation", dpi))

    return paths


def generate_strategy_matchup_charts(
    matchup_results: Dict[Tuple[str, str], Dict[str, Any]],
    output_dir: str,
    dpi: int = 150,
) -> List[str]:
    """Generate strategy comparison charts.

    Produces:
    - win_rate_heatmap.png
    - tricks_distribution.png
    - matchup_summary.png
    - strategy_delta_bars.png
    - self_play_control.png

    Args:
        matchup_results: Dict mapping (team0, team1) to result dicts.
            Each result dict should have 'win_rate', 'mean_tricks_team0', etc.
        output_dir: Directory to save PNGs.
        dpi: Output resolution.

    Returns:
        List of generated file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    fig = plot_win_rate_heatmap(matchup_results)
    paths.append(_save_figure(fig, out, "win_rate_heatmap", dpi))

    fig = plot_tricks_distribution_comparison(matchup_results)
    paths.append(_save_figure(fig, out, "tricks_distribution", dpi))

    fig = plot_matchup_summary(matchup_results)
    paths.append(_save_figure(fig, out, "matchup_summary", dpi))

    fig = plot_strategy_delta_bars(matchup_results)
    paths.append(_save_figure(fig, out, "strategy_delta_bars", dpi))

    fig = plot_self_play_control(matchup_results)
    paths.append(_save_figure(fig, out, "self_play_control", dpi))

    return paths


def generate_feature_outcome_charts(
    df: pd.DataFrame,
    output_dir: str,
    outcome_col: str = "tricks_won",
    top_n: int = 10,
    dpi: int = 150,
) -> List[str]:
    """Generate feature-outcome relationship charts.

    Produces:
    - feature_vs_outcome.png (top feature scatter)
    - feature_outcome_correlation.png
    - outcome_distributions.png

    Args:
        df: DataFrame with features and outcome column.
        output_dir: Directory to save PNGs.
        outcome_col: Name of the outcome column.
        top_n: Number of top features for correlation chart.
        dpi: Output resolution.

    Returns:
        List of generated file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    # Identify feature columns
    feature_cols = [c for c in df.columns if c.startswith("feat_") or c == "hand_value"]
    if not feature_cols:
        # Try numeric columns excluding metadata
        skip = {"seat", "deal_id", "hand_id", outcome_col, "contract_type", "trump", "trump_suit"}
        feature_cols = [c for c in df.select_dtypes(include="number").columns if c not in skip]

    if feature_cols and outcome_col in df.columns:
        # Correlation bar chart
        fig = plot_feature_outcome_correlation(
            df, outcome=outcome_col, features=feature_cols, top_n=top_n,
        )
        paths.append(_save_figure(fig, out, "feature_outcome_correlation", dpi))

        # Top feature scatter
        correlations = df[feature_cols].corrwith(df[outcome_col]).abs().sort_values(ascending=False)
        top_feature = correlations.index[0] if len(correlations) > 0 else feature_cols[0]
        fig = plot_feature_vs_outcome(df, feature=top_feature, outcome=outcome_col)
        paths.append(_save_figure(fig, out, "feature_vs_outcome", dpi))

    if outcome_col in df.columns and "contract_type" in df.columns:
        fig = plot_outcome_distributions(df, outcome=outcome_col, group_by="contract_type")
        paths.append(_save_figure(fig, out, "outcome_distributions", dpi))

    return paths


def generate_distribution_charts(
    df: pd.DataFrame,
    output_dir: str,
    value_col: str = "tricks_won",
    group_col: Optional[str] = "contract_type",
    dpi: int = 150,
) -> List[str]:
    """Generate distribution analysis charts (CDF/CCDF).

    Produces:
    - cdf.png
    - ccdf.png

    Args:
        df: DataFrame with value column.
        output_dir: Directory to save PNGs.
        value_col: Column to plot distributions for.
        group_col: Optional grouping column.
        dpi: Output resolution.

    Returns:
        List of generated file paths.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []

    if value_col not in df.columns:
        return paths

    fig = plot_cdf(df, column=value_col, group_by=group_col)
    paths.append(_save_figure(fig, out, "cdf", dpi))

    fig = plot_ccdf(df, column=value_col, group_by=group_col)
    paths.append(_save_figure(fig, out, "ccdf", dpi))

    return paths
