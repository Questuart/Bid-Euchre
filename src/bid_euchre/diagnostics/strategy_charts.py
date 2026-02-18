"""Strategy comparison chart functions for head-to-head analysis.

Provides matplotlib-based visualizations for comparing strategy performance
across matchups. Designed for head-to-head and self-play evaluation.
"""

from typing import Any, Dict, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

# Try to import seaborn, fall back gracefully
try:
    import seaborn as sns

    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

# Import style constants from reporting module
from ..reporting.style import (
    FIGSIZE_MATRIX,
    FIGSIZE_SINGLE_PLOT,
    apply_report_style,
    apply_seaborn_style,
    get_strategy_color,
    get_strategy_name,
)


def _apply_style() -> None:
    if HAS_SEABORN:
        apply_seaborn_style()
    else:
        apply_report_style()


def plot_win_rate_heatmap(
    matchup_results: Dict[Tuple[str, str], Dict[str, Any]],
    metric: str = "win_rate",
    figsize: Tuple[int, int] = FIGSIZE_MATRIX,
    title: Optional[str] = None,
    fmt: Optional[str] = None,
    center_override: Optional[float] = None,
    vmin_override: Optional[float] = None,
    vmax_override: Optional[float] = None,
    cbar_label_override: Optional[str] = None,
) -> plt.Figure:
    """Plot heatmap of win rates for all strategy matchups.

    Creates a square heatmap where rows are Team 0 strategies and columns
    are Team 1 strategies. Cell values show the win rate for Team 0.

    Args:
        matchup_results: Dict mapping (team0_name, team1_name) to result dict.
            Each result dict should contain the specified metric key.
        metric: Key in result dict to plot (default "win_rate" for Team 0)
        figsize: Figure size tuple
        title: Optional title override
        fmt: Format string for annotations. Default: ".1%" for win_rate, ".1f" otherwise
        center_override: Override colormap center (e.g. 0 for trick advantage)
        vmin_override: Override colormap minimum
        vmax_override: Override colormap maximum
        cbar_label_override: Override colorbar label text

    Returns:
        matplotlib Figure
    """
    _apply_style()

    # Extract unique strategies (preserve order from first appearance)
    strategies = []
    seen = set()
    for team0, team1 in matchup_results.keys():
        if team0 not in seen:
            strategies.append(team0)
            seen.add(team0)
        if team1 not in seen:
            strategies.append(team1)
            seen.add(team1)

    n = len(strategies)
    if n == 0:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No matchup data provided", ha="center", va="center")
        return fig

    # Build matrix
    matrix = np.full((n, n), np.nan)
    strategy_idx = {s: i for i, s in enumerate(strategies)}

    for (team0, team1), result in matchup_results.items():
        i = strategy_idx.get(team0)
        j = strategy_idx.get(team1)
        if i is not None and j is not None:
            val = result.get(metric)
            if val is not None:
                matrix[i, j] = val

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Determine format string
    if fmt is None:
        fmt = ".1%" if metric == "win_rate" else ".1f"

    # Determine colorbar label and value range
    is_win_rate = metric == "win_rate"
    vmin = 0 if is_win_rate else None
    vmax = 1 if is_win_rate else None
    center = 0.5 if is_win_rate else None
    cbar_label = "Win Rate (Team 0)" if is_win_rate else metric

    # Apply overrides when provided
    if center_override is not None:
        center = center_override
    if vmin_override is not None:
        vmin = vmin_override
    if vmax_override is not None:
        vmax = vmax_override
    if cbar_label_override is not None:
        cbar_label = cbar_label_override

    # Plot heatmap
    if HAS_SEABORN:
        labels = [get_strategy_name(s) for s in strategies]
        annot = np.array(
            [[f"{v:{fmt}}" if not np.isnan(v) else "" for v in row] for row in matrix]
        )
        sns.heatmap(
            matrix,
            annot=annot,
            fmt="",
            cmap="RdYlGn",
            center=center,
            vmin=vmin,
            vmax=vmax,
            ax=ax,
            xticklabels=labels,
            yticklabels=labels,
            cbar_kws={"label": cbar_label},
        )
    else:
        im = ax.imshow(matrix, cmap="RdYlGn", vmin=vmin, vmax=vmax, aspect="auto")
        fig.colorbar(im, ax=ax, label=cbar_label)

        # Labels
        labels = [get_strategy_name(s) for s in strategies]
        ax.set_xticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticks(range(n))
        ax.set_yticklabels(labels)

        # Annotate
        for i in range(n):
            for j in range(n):
                val = matrix[i, j]
                if not np.isnan(val):
                    color = (
                        "white"
                        if (vmax and (val < 0.3 * vmax or val > 0.7 * vmax))
                        else "black"
                    )
                    ax.text(j, i, f"{val:{fmt}}", ha="center", va="center", color=color)

    ax.set_xlabel("Team 1 Strategy")
    ax.set_ylabel("Team 0 Strategy")
    ax.set_title(title or "Win Rate Heatmap (Team 0 vs Team 1)")

    plt.tight_layout()
    return fig


def plot_tricks_distribution_comparison(
    matchup_results: Dict[Tuple[str, str], Dict[str, Any]],
    team: int = 0,
    figsize: Tuple[int, int] = (14, 6),
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot violin/box plots comparing trick distributions across matchups.

    Args:
        matchup_results: Dict mapping (team0_name, team1_name) to result dict.
            Each result dict should contain "tricks_team0" or "tricks_team1" key
            with a list of trick counts.
        team: Which team's tricks to plot (0 or 1)
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    _apply_style()

    tricks_key = f"tricks_team{team}"

    # Collect data
    matchup_labels = []
    trick_data = []

    for (team0, team1), result in matchup_results.items():
        tricks = result.get(tricks_key, [])
        if tricks:
            label = f"{get_strategy_name(team0)}\nvs\n{get_strategy_name(team1)}"
            matchup_labels.append(label)
            trick_data.append(tricks)

    if not trick_data:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(
            0.5,
            0.5,
            f"No trick data found (key: {tricks_key})",
            ha="center",
            va="center",
        )
        return fig

    fig, ax = plt.subplots(figsize=figsize)

    if HAS_SEABORN:
        # Flatten for seaborn
        import pandas as pd

        plot_df = []
        for label, tricks in zip(matchup_labels, trick_data):
            for t in tricks:
                plot_df.append({"Matchup": label, "Tricks": t})
        plot_df = pd.DataFrame(plot_df)
        sns.violinplot(data=plot_df, x="Matchup", y="Tricks", ax=ax, inner="box")
    else:
        bp = ax.boxplot(trick_data, labels=matchup_labels, patch_artist=True)
        colors = plt.cm.tab10(np.linspace(0, 1, len(trick_data)))
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

    ax.axhline(5.0, color="red", linestyle="--", alpha=0.7, label="Expected (5.0)")
    ax.set_xlabel("Matchup")
    ax.set_ylabel(f"Tricks (Team {team})")
    ax.set_title(title or f"Trick Distribution by Matchup (Team {team})")
    ax.legend(loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    ax.tick_params(axis="x", rotation=0)

    plt.tight_layout()
    return fig


def plot_strategy_delta_bars(
    baseline_results: Dict[str, Any],
    comparison_results: Dict[str, Dict[str, Any]],
    baseline_name: str = "random",
    metric: str = "mean_tricks",
    figsize: Tuple[int, int] = FIGSIZE_SINGLE_PLOT,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot bar chart showing delta (strategy - baseline) for each strategy.

    Args:
        baseline_results: Result dict for baseline strategy (self-play)
        comparison_results: Dict mapping strategy name to result dict.
            Each result should be from (strategy vs baseline) matchup.
        baseline_name: Name of baseline strategy for labeling
        metric: Metric key to compare (default "mean_tricks")
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    _apply_style()

    baseline_val = baseline_results.get(metric, 5.0)

    # Compute deltas
    strategies = []
    deltas = []
    ci_lowers = []
    ci_uppers = []
    colors = []

    for strategy_name, result in sorted(comparison_results.items()):
        val = result.get(metric)
        if val is None:
            continue

        delta = val - baseline_val
        strategies.append(get_strategy_name(strategy_name))
        deltas.append(delta)
        colors.append(get_strategy_color(strategy_name))

        # Try to get CI if available
        ci_lower = result.get("ci_lower")
        ci_upper = result.get("ci_upper")
        if ci_lower is not None and ci_upper is not None:
            ci_lowers.append(ci_lower - baseline_val)
            ci_uppers.append(ci_upper - baseline_val)
        else:
            ci_lowers.append(None)
            ci_uppers.append(None)

    if not strategies:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No comparison data provided", ha="center", va="center")
        return fig

    fig, ax = plt.subplots(figsize=figsize)

    y_pos = np.arange(len(strategies))
    bars = ax.barh(y_pos, deltas, color=colors, alpha=0.8)

    # Add error bars if available
    has_ci = all(l is not None for l in ci_lowers)
    if has_ci:
        xerr_lower = [d - l for d, l in zip(deltas, ci_lowers)]
        xerr_upper = [u - d for d, u in zip(deltas, ci_uppers)]
        ax.errorbar(
            deltas,
            y_pos,
            xerr=[xerr_lower, xerr_upper],
            fmt="none",
            color="black",
            capsize=3,
        )

    ax.axvline(0, color="black", linestyle="-", linewidth=1)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(strategies)
    ax.set_xlabel(f"Delta ({metric} - baseline)")
    ax.set_ylabel("Strategy")
    ax.set_title(
        title or f"Strategy Performance vs {get_strategy_name(baseline_name)} Baseline"
    )
    ax.grid(True, axis="x", alpha=0.3)

    # Annotate bars with values
    for i, (bar, delta) in enumerate(zip(bars, deltas)):
        x_pos = delta + 0.05 if delta >= 0 else delta - 0.05
        ha = "left" if delta >= 0 else "right"
        ax.text(x_pos, i, f"{delta:+.2f}", va="center", ha=ha, fontsize=9)

    plt.tight_layout()
    return fig


def plot_self_play_control(
    self_play_results: Dict[str, Dict[str, Any]],
    expected_mean: float = 5.0,
    figsize: Tuple[int, int] = FIGSIZE_SINGLE_PLOT,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot control chart for self-play sanity check.

    In self-play (strategy vs itself), each team should average ~5.0 tricks.
    This chart flags strategies where the mean deviates significantly.

    Args:
        self_play_results: Dict mapping strategy name to result dict.
            Each result should contain "mean_tricks" and optionally "ci_lower"/"ci_upper".
        expected_mean: Expected mean tricks for fair self-play (default 5.0)
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure
    """
    _apply_style()

    strategies = []
    means = []
    ci_lowers = []
    ci_uppers = []
    colors = []
    warnings = []

    for strategy_name, result in sorted(self_play_results.items()):
        mean = result.get("mean_tricks")
        if mean is None:
            continue

        strategies.append(get_strategy_name(strategy_name))
        means.append(mean)
        colors.append(get_strategy_color(strategy_name))

        ci_lower = result.get("ci_lower", mean - 0.1)
        ci_upper = result.get("ci_upper", mean + 0.1)
        ci_lowers.append(ci_lower)
        ci_uppers.append(ci_upper)

        # Flag if expected mean is outside CI
        is_warning = ci_lower > expected_mean or ci_upper < expected_mean
        warnings.append(is_warning)

    if not strategies:
        fig, ax = plt.subplots(figsize=figsize)
        ax.text(0.5, 0.5, "No self-play data provided", ha="center", va="center")
        return fig

    fig, ax = plt.subplots(figsize=figsize)

    x_pos = np.arange(len(strategies))

    # Plot points with error bars
    for i, (x, m, lo, hi, c, warn) in enumerate(
        zip(x_pos, means, ci_lowers, ci_uppers, colors, warnings)
    ):
        marker = "o" if not warn else "s"
        edge_color = "red" if warn else c
        ax.errorbar(
            x,
            m,
            yerr=[[m - lo], [hi - m]],
            fmt=marker,
            color=c,
            markeredgecolor=edge_color,
            markeredgewidth=2 if warn else 1,
            markersize=10,
            capsize=5,
            label=strategies[i] if warn else None,
        )

    # Reference line and acceptable region
    ax.axhline(expected_mean, color="green", linestyle="-", linewidth=2, alpha=0.8)
    ax.axhspan(expected_mean - 0.2, expected_mean + 0.2, color="green", alpha=0.1)

    ax.set_xticks(x_pos)
    ax.set_xticklabels(strategies, rotation=45, ha="right")
    ax.set_xlabel("Strategy (Self-Play)")
    ax.set_ylabel("Mean Tricks (Team 0)")
    ax.set_title(title or "Self-Play Control Chart (Expected: 5.0 tricks)")
    ax.grid(True, axis="y", alpha=0.3)

    # Add warning annotation if any
    if any(warnings):
        warning_strats = [s for s, w in zip(strategies, warnings) if w]
        ax.annotate(
            f"Warning: {', '.join(warning_strats)}",
            xy=(0.02, 0.98),
            xycoords="axes fraction",
            ha="left",
            va="top",
            fontsize=9,
            color="red",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

    plt.tight_layout()
    return fig


def plot_matchup_summary(
    matchup_results: Dict[Tuple[str, str], Dict[str, Any]],
    figsize: Tuple[int, int] = (16, 5),
    metric_key: str = "mean_tricks_team0",
) -> plt.Figure:
    """Create a 3-panel summary of matchup results.

    Left: Win rate heatmap
    Center: Mean tricks (Team 0) by matchup
    Right: Self-play control chart

    Args:
        matchup_results: Dict mapping (team0_name, team1_name) to result dict.
            Expected keys per result: "win_rate", "mean_tricks_team0", "mean_tricks_team1".
        figsize: Figure size tuple
        metric_key: Key for mean tricks metric (default "mean_tricks_team0")

    Returns:
        matplotlib Figure with 3 subplots
    """
    _apply_style()

    fig, axes = plt.subplots(1, 3, figsize=figsize)

    # Panel 1: Win rate heatmap
    ax = axes[0]
    # Use sorted() for deterministic ordering instead of set()
    strategies = sorted(set(s for pair in matchup_results.keys() for s in pair))
    n = len(strategies)

    if n > 0:
        matrix = np.full((n, n), np.nan)
        strategy_idx = {s: i for i, s in enumerate(strategies)}

        for (team0, team1), result in matchup_results.items():
            i = strategy_idx.get(team0)
            j = strategy_idx.get(team1)
            if i is not None and j is not None:
                val = result.get("win_rate")
                if val is not None:
                    matrix[i, j] = val

        im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
        fig.colorbar(im, ax=ax, label="Win Rate", shrink=0.8)
        labels = [get_strategy_name(s) for s in strategies]
        ax.set_xticks(range(n))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticks(range(n))
        ax.set_yticklabels(labels)
        ax.set_title("Win Rate Heatmap")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")

    # Panel 2: Mean tricks comparison
    # Fix: Use metric_key parameter and get_strategy_name() for labels
    ax = axes[1]
    matchup_labels = []
    mean_tricks = []

    for (team0, team1), result in sorted(matchup_results.items()):
        label = f"{get_strategy_name(team0)} v {get_strategy_name(team1)}"
        mean = result.get(metric_key)
        if mean is not None:
            matchup_labels.append(label)
            mean_tricks.append(mean)

    if mean_tricks:
        ax.bar(range(len(mean_tricks)), mean_tricks)
        ax.axhline(5.0, color="red", linestyle="--", label="Expected")
        ax.set_xticks(range(len(mean_tricks)))
        ax.set_xticklabels(matchup_labels, rotation=45, ha="right")
        ax.set_ylabel("Mean Tricks (Team 0)")
        ax.set_title("Mean Tricks by Matchup")
        ax.legend()
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")

    # Panel 3: Self-play subset
    ax = axes[2]
    self_play_data = {
        team0: result
        for (team0, team1), result in matchup_results.items()
        if team0 == team1
    }

    if self_play_data:
        # Sort for deterministic ordering
        sorted_strategies = sorted(self_play_data.keys())
        strat_names = [get_strategy_name(s) for s in sorted_strategies]
        means = [self_play_data[s].get(metric_key, 5.0) for s in sorted_strategies]
        colors = [get_strategy_color(s) for s in sorted_strategies]

        ax.bar(range(len(means)), means, color=colors)
        ax.axhline(5.0, color="green", linestyle="-", linewidth=2)
        ax.axhspan(4.8, 5.2, color="green", alpha=0.1)
        ax.set_xticks(range(len(means)))
        ax.set_xticklabels(strat_names, rotation=45, ha="right")
        ax.set_ylabel("Mean Tricks")
        ax.set_title("Self-Play Control")
    else:
        ax.text(
            0.5,
            0.5,
            "No self-play data\n(add self-play matchups\nto configuration)",
            ha="center",
            va="center",
            fontsize=10,
        )

    fig.suptitle("Strategy Matchup Summary", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig


def plot_self_play_by_contract(
    matchup_results: Dict[Tuple[str, str], Dict[str, Any]],
    expected_mean: float = 5.0,
    figsize: Tuple[int, int] = (14, 8),
    title: Optional[str] = None,
) -> Optional[plt.Figure]:
    """Plot self-play mean tricks broken down by contract/scenario.

    Creates a grouped bar chart showing mean tricks per scenario for each
    self-play strategy, with a control band around expected_mean.

    Args:
        matchup_results: Dict mapping (team0, team1) to result dicts.
            Self-play entries (team0 == team1) with 'scenarios' key are used.
        expected_mean: Expected mean tricks for fair self-play (default 5.0)
        figsize: Figure size tuple
        title: Optional title override

    Returns:
        matplotlib Figure, or None if no self-play entries have scenario data
    """
    _apply_style()

    # Extract self-play entries with scenarios
    self_play = {}
    for (team0, team1), result in matchup_results.items():
        if team0 == team1 and "scenarios" in result:
            self_play[team0] = result["scenarios"]

    if not self_play:
        return None

    # Collect all scenario names across all strategies
    all_scenarios = sorted(
        set(s for scenarios in self_play.values() for s in scenarios.keys())
    )

    if not all_scenarios:
        return None

    fig, ax = plt.subplots(figsize=figsize)

    # Grouped bar chart
    strategies = sorted(self_play.keys())
    n_strategies = len(strategies)
    n_scenarios = len(all_scenarios)

    bar_width = 0.8 / n_strategies
    x = np.arange(n_scenarios)

    for i, strategy in enumerate(strategies):
        scenarios = self_play[strategy]
        means = []
        for scenario in all_scenarios:
            data = scenarios.get(scenario, {})
            # Use avg_team0 or mean_tricks_team0
            mean = data.get("avg_team0", data.get("mean_tricks_team0", np.nan))
            means.append(mean)

        offset = (i - n_strategies / 2 + 0.5) * bar_width
        color = get_strategy_color(strategy)
        label = get_strategy_name(strategy)
        ax.bar(x + offset, means, bar_width, color=color, alpha=0.8, label=label)

    # Control band
    ax.axhline(expected_mean, color="green", linestyle="-", linewidth=2)
    ax.axhspan(expected_mean - 0.25, expected_mean + 0.25, color="green", alpha=0.1)

    # Labels
    from ..reporting.style import get_contract_label

    scenario_labels = []
    for s in all_scenarios:
        # Parse scenario name: "suit_C" -> get_contract_label("suit", "C")
        if s.startswith("suit_") and len(s) == 6:
            scenario_labels.append(get_contract_label("suit", s[-1]))
        else:
            scenario_labels.append(get_contract_label(s))

    ax.set_xticks(x)
    ax.set_xticklabels(scenario_labels, rotation=45, ha="right")
    ax.set_xlabel("Contract / Scenario")
    ax.set_ylabel("Mean Tricks (Team 0)")
    ax.set_title(title or "Self-Play Mean Tricks by Contract")
    ax.legend(loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout()
    return fig
