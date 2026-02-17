#!/usr/bin/env python3
"""Generate all NEW charts for the Phase 0 report r4/r5.

Produces 8–9 chart PNGs for sections 3, 4, 5a, 5b, 5c, 9c of the report.
Assumes PYTHONPATH=src is set externally.

Usage:
    PYTHONPATH=src uv run python scripts/internal/generate_r4_charts.py \
      --zoom-dir data/runs/canonical_bidless_outcomes_zoom_42_20260204_222712 \
      --greedy-dir data/runs/canonical_bidless_dataset_greedy_42_20260204_221121 \
      --glutton-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
      --mixed-play-dir data/runs/canonical_bidless_dataset_mixed_play_42_20260204_221115 \
      --gate-json data/runs/play_policy_gate_aggregate_20260204_221656.json \
      --output-dir docs/04_reports/assets/phase0_20260207_r5 \
      --dpi 150
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bid_euchre.datasets.join import join_features_outcomes
from bid_euchre.reporting.style import (
    apply_report_style,
    get_contract_color,
    get_contract_label,
    get_strategy_color,
    get_strategy_name,
)

# ---------------------------------------------------------------------------
# Colors for contract groups in grouped boxplots
# ---------------------------------------------------------------------------
CONTRACT_GROUP_COLORS = {
    "aggregate": "#95a5a6",  # gray
    "suit": "#3498db",  # blue
    "high": "#27ae60",  # green
    "low": "#e74c3c",  # red
}

# Colors for seats in the seat balance chart
SEAT_COLORS = {
    0: "#3498db",  # blue
    1: "#e67e22",  # orange
    2: "#27ae60",  # green
    3: "#9b59b6",  # purple
}

# Strategies expected in self-play zoom runs
SELF_PLAY_STRATEGIES = [
    "always_highest",
    "always_lowest",
    "glutton",
    "greedy",
    "random_legal",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _save_figure(fig: plt.Figure, output_dir: Path, name: str, dpi: int = 150) -> str:
    """Save a figure to PNG and close it. Returns the output path."""
    path = output_dir / f"{name}.png"
    fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def _expand_distribution(dist: Dict[str, int]) -> np.ndarray:
    """Expand a {trick_count_str: count} histogram to a flat array of values."""
    values: List[int] = []
    for tricks_str, count in dist.items():
        values.extend([int(tricks_str)] * count)
    return np.array(values)


def _load_self_play_scenarios(zoom_dir: Path) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Load self-play scenario results from zoom run.

    Returns:
        Dict mapping strategy_name -> scenario_name -> scenario data dict.
        Only self-play matchups (team0 == team1) are included.
    """
    results_dir = zoom_dir / "results"
    if not results_dir.exists():
        raise FileNotFoundError(f"Results directory not found: {results_dir}")

    self_play: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for matchup_dir in sorted(results_dir.iterdir()):
        if not matchup_dir.is_dir():
            continue
        name = matchup_dir.name
        if "_vs_" not in name:
            continue

        team0, team1 = name.split("_vs_", maxsplit=1)
        if team0 != team1:
            continue  # Only self-play

        scenarios: Dict[str, Dict[str, Any]] = {}
        for scenario_file in sorted(matchup_dir.glob("*.json")):
            with open(scenario_file) as f:
                data = json.load(f)
            scenarios[scenario_file.stem] = data

        if scenarios:
            self_play[team0] = scenarios

    return self_play


def _classify_scenario(scenario_name: str) -> str:
    """Classify a scenario name into a contract group.

    Returns one of: 'suit', 'high', 'low'.
    """
    if scenario_name.startswith("suit_"):
        return "suit"
    return scenario_name  # 'high' or 'low'


def _build_self_play_boxplot_data(
    self_play: Dict[str, Dict[str, Dict[str, Any]]],
) -> pd.DataFrame:
    """Build a DataFrame for grouped boxplots from self-play scenario data.

    Returns DataFrame with columns: strategy, contract_group, tricks_won
    """
    rows: List[Dict[str, Any]] = []

    for strategy, scenarios in self_play.items():
        for scenario_name, data in scenarios.items():
            dist = data.get("distribution_team0", {})
            if not dist:
                continue

            values = _expand_distribution(dist)
            group = _classify_scenario(scenario_name)

            for v in values:
                rows.append(
                    {
                        "strategy": strategy,
                        "contract_group": group,
                        "tricks_won": v,
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["strategy", "contract_group", "tricks_won"])

    df = pd.DataFrame(rows)

    # Also add an "aggregate" group for each strategy (all scenarios combined)
    agg = df.copy()
    agg["contract_group"] = "aggregate"
    df = pd.concat([df, agg], ignore_index=True)

    return df


def _load_joined_data(run_dir: Path) -> pd.DataFrame:
    """Load features joined with outcomes from a run directory."""
    bidless_path = str(run_dir / "datasets" / "bidless.parquet")
    outcomes_path = str(run_dir / "datasets" / "bidless_outcomes.parquet")

    if not Path(bidless_path).exists():
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not Path(outcomes_path).exists():
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    return join_features_outcomes(bidless_path, outcomes_path)


def _derive_contract_group(df: pd.DataFrame) -> pd.DataFrame:
    """Add a 'contract_group' column: 'suit', 'high', or 'low'."""
    df = df.copy()
    df["contract_group"] = df["contract_type"].apply(
        lambda ct: "suit" if ct.startswith("suit") else ct
    )
    return df


# ---------------------------------------------------------------------------
# Chart 1: Self-Play Grouped Boxplot (section 3)
# ---------------------------------------------------------------------------


def generate_self_play_grouped_boxplot(
    zoom_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate self-play grouped boxplot chart.

    X-axis: strategy name (5 strategies)
    Within each strategy: 4 grouped boxplots (aggregate, suit, high, low)
    Y-axis: tricks_won (from distribution_team0)
    """
    apply_report_style()

    self_play = _load_self_play_scenarios(zoom_dir)
    df = _build_self_play_boxplot_data(self_play)

    if df.empty:
        raise ValueError("No self-play scenario data found in zoom run")

    # Order strategies and contract groups
    strategy_order = [s for s in SELF_PLAY_STRATEGIES if s in df["strategy"].unique()]
    group_order = ["aggregate", "suit", "high", "low"]

    fig, ax = plt.subplots(figsize=(14, 7))

    # Build grouped boxplot manually for precise control
    n_groups = len(group_order)
    box_width = 0.18
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, strategy in enumerate(strategy_order):
        center = i * (n_groups + 1) * box_width + i * 0.3
        tick_positions.append(center + (n_groups - 1) * box_width / 2)
        tick_labels.append(get_strategy_name(strategy))

        for j, group in enumerate(group_order):
            mask = (df["strategy"] == strategy) & (df["contract_group"] == group)
            subset = df.loc[mask, "tricks_won"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(CONTRACT_GROUP_COLORS[group])

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # Reference line and green band
    ax.axhline(5.0, color="green", linestyle="-", linewidth=2, alpha=0.8, zorder=1)
    ax.axhspan(4.75, 5.25, color="green", alpha=0.08, zorder=0)

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Tricks Won (Team 0)")
    ax.set_title("Self-Play Tricks Distribution by Strategy and Contract Group")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=CONTRACT_GROUP_COLORS[g], alpha=0.75)
        for g in group_order
    ]
    legend_labels = [g.capitalize() for g in group_order]
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Contract Group")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "self_play_grouped_boxplot", dpi)


# ---------------------------------------------------------------------------
# Chart 2: Seat Balance Grouped Boxplot (section 4)
# ---------------------------------------------------------------------------


def generate_seat_balance_grouped_boxplot(
    greedy_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate seat balance grouped boxplot chart.

    X-axis: contract group (aggregate, suit, high, low)
    Within each contract group: 4 grouped boxplots (seats 0–3)
    Y-axis: hand_value
    """
    apply_report_style()

    df = _load_joined_data(greedy_dir)
    df = _derive_contract_group(df)

    # Add aggregate group
    agg = df.copy()
    agg["contract_group"] = "aggregate"
    plot_df = pd.concat([df, agg], ignore_index=True)

    seat_order = [0, 1, 2, 3]
    group_order = ["aggregate", "suit", "high", "low"]

    fig, ax = plt.subplots(figsize=(12, 7))

    n_seats = len(seat_order)
    box_width = 0.18
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, group in enumerate(group_order):
        center = i * (n_seats + 1) * box_width + i * 0.3
        tick_positions.append(center + (n_seats - 1) * box_width / 2)
        tick_labels.append(group.capitalize())

        for j, seat in enumerate(seat_order):
            mask = (plot_df["seat"] == seat) & (plot_df["contract_group"] == group)
            subset = plot_df.loc[mask, "hand_value"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(SEAT_COLORS[seat])

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Hand Value")
    ax.set_title("Seat Balance: Hand Value by Contract Group and Seat")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=SEAT_COLORS[s], alpha=0.75)
        for s in seat_order
    ]
    legend_labels = [f"Seat {s}" for s in seat_order]
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Seat")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "seat_balance_grouped_boxplot", dpi)


# ---------------------------------------------------------------------------
# Chart 3: Hand Value by Contract Comparison (section 5a)
# ---------------------------------------------------------------------------


def generate_hand_value_by_contract_comparison(
    greedy_dir: Path,
    glutton_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate hand-value-by-contract comparison boxplot.

    X-axis: contract type (suit, high, low)
    Within each contract: 2 boxplots (greedy, glutton)
    Y-axis: hand_value
    """
    apply_report_style()

    greedy_df = _load_joined_data(greedy_dir)
    greedy_df["strategy"] = "greedy"
    greedy_df = _derive_contract_group(greedy_df)

    glutton_df = _load_joined_data(glutton_dir)
    glutton_df["strategy"] = "glutton"
    glutton_df = _derive_contract_group(glutton_df)

    df = pd.concat([greedy_df, glutton_df], ignore_index=True)

    contract_order = ["suit", "high", "low"]
    strategy_order = ["greedy", "glutton"]

    fig, ax = plt.subplots(figsize=(10, 7))

    n_strategies = len(strategy_order)
    box_width = 0.3
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, contract in enumerate(contract_order):
        center = i * (n_strategies + 0.5) * box_width + i * 0.2
        tick_positions.append(center + (n_strategies - 1) * box_width / 2)
        tick_labels.append(contract.capitalize())

        for j, strategy in enumerate(strategy_order):
            mask = (df["strategy"] == strategy) & (df["contract_group"] == contract)
            subset = df.loc[mask, "hand_value"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(get_strategy_color(strategy))

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Hand Value")
    ax.set_title("Hand Value Distribution by Contract Type: Greedy vs Glutton")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=get_strategy_color(s), alpha=0.75)
        for s in strategy_order
    ]
    legend_labels = [get_strategy_name(s) for s in strategy_order]
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Strategy")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "hand_value_by_contract_comparison", dpi)


# ---------------------------------------------------------------------------
# Chart 4: Tricks by Contract Comparison (section 5b)
# ---------------------------------------------------------------------------


def generate_tricks_by_contract_comparison(
    greedy_dir: Path,
    glutton_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate tricks-by-contract comparison boxplot.

    X-axis: contract type (suit, high, low)
    Within each contract: 2 boxplots (greedy, glutton)
    Y-axis: tricks_won
    """
    apply_report_style()

    greedy_df = _load_joined_data(greedy_dir)
    greedy_df["strategy"] = "greedy"
    greedy_df = _derive_contract_group(greedy_df)

    glutton_df = _load_joined_data(glutton_dir)
    glutton_df["strategy"] = "glutton"
    glutton_df = _derive_contract_group(glutton_df)

    df = pd.concat([greedy_df, glutton_df], ignore_index=True)

    contract_order = ["suit", "high", "low"]
    strategy_order = ["greedy", "glutton"]

    fig, ax = plt.subplots(figsize=(10, 7))

    n_strategies = len(strategy_order)
    box_width = 0.3
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, contract in enumerate(contract_order):
        center = i * (n_strategies + 0.5) * box_width + i * 0.2
        tick_positions.append(center + (n_strategies - 1) * box_width / 2)
        tick_labels.append(contract.capitalize())

        for j, strategy in enumerate(strategy_order):
            mask = (df["strategy"] == strategy) & (df["contract_group"] == contract)
            subset = df.loc[mask, "tricks_won"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(get_strategy_color(strategy))

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # Reference line at 5.0
    ax.axhline(5.0, color="gray", linestyle="--", alpha=0.6, label="Expected (5.0)")

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Tricks Won")
    ax.set_title("Tricks Won Distribution by Contract Type: Greedy vs Glutton")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=get_strategy_color(s), alpha=0.75)
        for s in strategy_order
    ]
    legend_labels = [get_strategy_name(s) for s in strategy_order]
    legend_handles.append(plt.Line2D([0], [0], color="gray", linestyle="--", alpha=0.6))
    legend_labels.append("Expected (5.0)")
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Strategy")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "tricks_by_contract_comparison", dpi)


# ---------------------------------------------------------------------------
# Chart 5: CDF Comparison (section 5b)
# ---------------------------------------------------------------------------


def generate_cdf_comparison(
    greedy_dir: Path,
    glutton_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate side-by-side CDF comparison.

    Left panel: Greedy CDF with 3 curves (suit, high, low)
    Right panel: Glutton CDF with 3 curves (suit, high, low)
    Discrete steps (0-10 tricks), no smoothing.
    """
    apply_report_style()

    greedy_df = _load_joined_data(greedy_dir)
    greedy_df = _derive_contract_group(greedy_df)

    glutton_df = _load_joined_data(glutton_dir)
    glutton_df = _derive_contract_group(glutton_df)

    contract_groups = ["suit", "high", "low"]
    contract_colors = {
        "suit": CONTRACT_GROUP_COLORS["suit"],
        "high": CONTRACT_GROUP_COLORS["high"],
        "low": CONTRACT_GROUP_COLORS["low"],
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

    trick_values = np.arange(0, 11)  # 0 through 10

    for ax, (label, df) in zip(axes, [("Greedy", greedy_df), ("Glutton", glutton_df)]):
        for group in contract_groups:
            mask = df["contract_group"] == group
            subset = df.loc[mask, "tricks_won"].values

            if len(subset) == 0:
                continue

            # Compute empirical CDF at discrete trick values
            cdf_values = np.array([(subset <= t).mean() for t in trick_values])

            ax.step(
                trick_values,
                cdf_values,
                where="post",
                color=contract_colors[group],
                linewidth=2,
                label=group.capitalize(),
            )

        ax.set_xlabel("Tricks Won")
        ax.set_title(f"{label} CDF by Contract Type")
        ax.set_xticks(trick_values)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right")

    axes[0].set_ylabel("Cumulative Probability")

    fig.suptitle(
        "CDF of Tricks Won: Greedy vs Glutton by Contract Type",
        fontsize=13,
        y=1.02,
    )
    plt.tight_layout()
    return _save_figure(fig, output_dir, "cdf_comparison", dpi)


# ---------------------------------------------------------------------------
# Chart 6: Hand Value by Trump Comparison (section 5c)
# ---------------------------------------------------------------------------


def generate_hand_value_by_trump_comparison(
    greedy_dir: Path,
    glutton_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate hand-value-by-trump comparison boxplot (suit contracts only).

    X-axis: trump suit (C, D, H, S)
    Within each suit: 2 boxplots (greedy, glutton)
    Y-axis: hand_value
    """
    apply_report_style()

    greedy_df = _load_joined_data(greedy_dir)
    greedy_df["strategy"] = "greedy"
    greedy_df = _derive_contract_group(greedy_df)

    glutton_df = _load_joined_data(glutton_dir)
    glutton_df["strategy"] = "glutton"
    glutton_df = _derive_contract_group(glutton_df)

    df = pd.concat([greedy_df, glutton_df], ignore_index=True)

    # Filter to suit contracts only
    df = df[df["contract_group"] == "suit"].copy()

    trump_order = ["C", "D", "H", "S"]
    strategy_order = ["greedy", "glutton"]

    fig, ax = plt.subplots(figsize=(10, 7))

    n_strategies = len(strategy_order)
    box_width = 0.3
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, trump in enumerate(trump_order):
        center = i * (n_strategies + 0.5) * box_width + i * 0.2
        tick_positions.append(center + (n_strategies - 1) * box_width / 2)
        tick_labels.append(get_contract_label("suit", trump))

        for j, strategy in enumerate(strategy_order):
            mask = (df["strategy"] == strategy) & (df["trump_suit"] == trump)
            subset = df.loc[mask, "hand_value"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(get_strategy_color(strategy))

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Hand Value")
    ax.set_title("Hand Value by Trump Suit (Suit Contracts): Greedy vs Glutton")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=get_strategy_color(s), alpha=0.75)
        for s in strategy_order
    ]
    legend_labels = [get_strategy_name(s) for s in strategy_order]
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Strategy")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "hand_value_by_trump_comparison", dpi)


# ---------------------------------------------------------------------------
# Chart 7: Outcome by Trump Comparison (section 5c)
# ---------------------------------------------------------------------------


def generate_outcome_by_trump_comparison(
    greedy_dir: Path,
    glutton_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate outcome-by-trump comparison boxplot (suit contracts only).

    X-axis: trump suit (C, D, H, S)
    Within each suit: 2 boxplots (greedy, glutton)
    Y-axis: tricks_won
    """
    apply_report_style()

    greedy_df = _load_joined_data(greedy_dir)
    greedy_df["strategy"] = "greedy"
    greedy_df = _derive_contract_group(greedy_df)

    glutton_df = _load_joined_data(glutton_dir)
    glutton_df["strategy"] = "glutton"
    glutton_df = _derive_contract_group(glutton_df)

    df = pd.concat([greedy_df, glutton_df], ignore_index=True)

    # Filter to suit contracts only
    df = df[df["contract_group"] == "suit"].copy()

    trump_order = ["C", "D", "H", "S"]
    strategy_order = ["greedy", "glutton"]

    fig, ax = plt.subplots(figsize=(10, 7))

    n_strategies = len(strategy_order)
    box_width = 0.3
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, trump in enumerate(trump_order):
        center = i * (n_strategies + 0.5) * box_width + i * 0.2
        tick_positions.append(center + (n_strategies - 1) * box_width / 2)
        tick_labels.append(get_contract_label("suit", trump))

        for j, strategy in enumerate(strategy_order):
            mask = (df["strategy"] == strategy) & (df["trump_suit"] == trump)
            subset = df.loc[mask, "tricks_won"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(get_strategy_color(strategy))

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    # Reference line at 5.0
    ax.axhline(5.0, color="gray", linestyle="--", alpha=0.6, label="Expected (5.0)")

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Tricks Won")
    ax.set_title("Tricks Won by Trump Suit (Suit Contracts): Greedy vs Glutton")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=get_strategy_color(s), alpha=0.75)
        for s in strategy_order
    ]
    legend_labels = [get_strategy_name(s) for s in strategy_order]
    legend_handles.append(plt.Line2D([0], [0], color="gray", linestyle="--", alpha=0.6))
    legend_labels.append("Expected (5.0)")
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Strategy")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "outcome_by_trump_comparison", dpi)


# ---------------------------------------------------------------------------
# Chart 8: Advantage by Contract (section 9c)
# ---------------------------------------------------------------------------


def generate_advantage_by_contract(
    gate_json_path: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate horizontal bar chart of glutton advantage by contract type.

    Reads the policy gate JSON to extract per-scenario advantage data from
    seed 42, glutton_vs_greedy direction.

    One bar per contract type: suit_S, suit_C, suit_D, suit_H, high, low.
    Error bars = 95% CI. Reference line at 0.0.
    """
    apply_report_style()

    with open(gate_json_path) as f:
        gate_data = json.load(f)

    # Extract scenarios from seed 42 (first seed typically), glutton_vs_greedy direction
    scenarios: List[Dict[str, Any]] = []
    for seed_result in gate_data.get("seeds", []):
        if seed_result.get("seed") != 42:
            continue
        for scenario in seed_result.get("scenarios", []):
            scenario_name = scenario.get("scenario", "")
            # Only glutton_vs_greedy direction
            if scenario_name.startswith("glutton_vs_greedy/"):
                contract = scenario_name.split("/", 1)[1]
                scenarios.append(
                    {
                        "contract": contract,
                        "adv_mean": scenario["adv_mean"],
                        "adv_ci": scenario["adv_ci"],
                    }
                )

    if not scenarios:
        # Fallback: try all scenarios regardless of seed/direction filtering
        for seed_result in gate_data.get("seeds", []):
            for scenario in seed_result.get("scenarios", []):
                scenario_name = scenario.get("scenario", "")
                if scenario_name.startswith("glutton_vs_greedy/"):
                    contract = scenario_name.split("/", 1)[1]
                    scenarios.append(
                        {
                            "contract": contract,
                            "adv_mean": scenario["adv_mean"],
                            "adv_ci": scenario["adv_ci"],
                        }
                    )
            if scenarios:
                break  # Use first seed that has data

    if not scenarios:
        raise ValueError("No glutton_vs_greedy scenario data found in gate JSON")

    # Order contracts consistently
    contract_order = ["suit_S", "suit_C", "suit_D", "suit_H", "high", "low"]
    scenario_map = {s["contract"]: s for s in scenarios}

    # Filter to those present
    ordered = [scenario_map[c] for c in contract_order if c in scenario_map]
    # Add any not in the predefined order
    seen = set(contract_order)
    for s in scenarios:
        if s["contract"] not in seen:
            ordered.append(s)
            seen.add(s["contract"])

    contracts = [s["contract"] for s in ordered]
    means = [s["adv_mean"] for s in ordered]
    ci_lowers = [s["adv_ci"][0] for s in ordered]
    ci_uppers = [s["adv_ci"][1] for s in ordered]

    # Compute error bar sizes (asymmetric)
    xerr_lower = [m - lo for m, lo in zip(means, ci_lowers)]
    xerr_upper = [hi - m for m, hi in zip(means, ci_uppers)]

    # Colors by contract type
    colors = []
    for c in contracts:
        if c.startswith("suit_") and len(c) == 6:
            colors.append(get_contract_color("suit", c[-1]))
        else:
            colors.append(get_contract_color(c))

    # Labels
    labels = []
    for c in contracts:
        if c.startswith("suit_") and len(c) == 6:
            labels.append(get_contract_label("suit", c[-1]))
        else:
            labels.append(get_contract_label(c))

    fig, ax = plt.subplots(figsize=(10, 6))

    y_pos = np.arange(len(contracts))
    bars = ax.barh(
        y_pos,
        means,
        xerr=[xerr_lower, xerr_upper],
        color=colors,
        alpha=0.8,
        capsize=4,
        edgecolor="black",
        linewidth=0.5,
    )

    # Reference line at 0.0
    ax.axvline(0, color="black", linestyle="-", linewidth=1.2)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Glutton Advantage (tricks, positive = glutton better)")
    ax.set_title("Glutton Advantage by Contract Type (seed 42, 95% CI)")
    ax.grid(True, axis="x", alpha=0.3)

    # Annotate bars with mean values
    for i, (bar, mean) in enumerate(zip(bars, means)):
        x_offset = 0.05 if mean >= 0 else -0.05
        ha = "left" if mean >= 0 else "right"
        ax.text(
            mean + x_offset,
            i,
            f"{mean:+.3f}",
            va="center",
            ha=ha,
            fontsize=9,
            fontweight="bold",
        )

    plt.tight_layout()
    return _save_figure(fig, output_dir, "advantage_by_contract", dpi)


# ---------------------------------------------------------------------------
# Chart 9: Hand Value All Strategies (section 5a, r5)
# ---------------------------------------------------------------------------


def _load_joined_data_with_strategy(run_dir: Path) -> pd.DataFrame:
    """Load features joined with outcomes, preserving strategy columns.

    The mixed_play dataset has team0_strategy and team1_strategy columns in
    the outcomes parquet. This helper merges the strategy onto each seat row
    (seats 0,2 -> team0_strategy, seats 1,3 -> team1_strategy).
    """
    bidless_path = str(run_dir / "datasets" / "bidless.parquet")
    outcomes_path = str(run_dir / "datasets" / "bidless_outcomes.parquet")

    if not Path(bidless_path).exists():
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not Path(outcomes_path).exists():
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    # Get the joined features + outcomes
    joined = join_features_outcomes(bidless_path, outcomes_path)

    # Read outcomes again to get strategy columns
    outcomes_df = pd.read_parquet(outcomes_path)
    if "team0_strategy" not in outcomes_df.columns:
        raise ValueError(f"No team0_strategy column in {outcomes_path}")

    strategy_cols = outcomes_df[
        ["hand_id", "contract_type", "trump_suit", "team0_strategy", "team1_strategy"]
    ].drop_duplicates(subset=["hand_id", "contract_type", "trump_suit"], keep="first")

    # Merge strategy onto joined data
    merged = joined.merge(
        strategy_cols,
        on=["hand_id", "contract_type", "trump_suit"],
        how="left",
    )

    # Assign per-seat strategy
    merged["strategy"] = np.where(
        merged["seat"].isin([0, 2]),
        merged["team0_strategy"],
        merged["team1_strategy"],
    )
    merged = merged.drop(columns=["team0_strategy", "team1_strategy"])

    return merged


def generate_hand_value_all_strategies(
    mixed_play_dir: Path,
    output_dir: Path,
    dpi: int = 150,
) -> str:
    """Generate hand value calibration chart for all 3 strategies.

    X-axis: contract type (suit, high, low)
    Within each contract: 3 grouped boxplots (greedy, glutton, random_legal)
    Y-axis: hand_value
    Colors: from get_strategy_color()
    """
    apply_report_style()

    df = _load_joined_data_with_strategy(mixed_play_dir)
    df = _derive_contract_group(df)

    # Only self-play rows (strategy same for both teams on this hand)
    contract_order = ["suit", "high", "low"]
    strategy_order = ["greedy", "glutton", "random_legal"]

    fig, ax = plt.subplots(figsize=(10, 7))

    n_strategies = len(strategy_order)
    box_width = 0.25
    positions = []
    box_data = []
    box_colors = []
    tick_positions = []
    tick_labels = []

    for i, contract in enumerate(contract_order):
        center = i * (n_strategies + 0.5) * box_width + i * 0.3
        tick_positions.append(center + (n_strategies - 1) * box_width / 2)
        tick_labels.append(contract.capitalize())

        for j, strategy in enumerate(strategy_order):
            mask = (df["strategy"] == strategy) & (df["contract_group"] == contract)
            subset = df.loc[mask, "hand_value"].values
            pos = center + j * box_width
            positions.append(pos)
            box_data.append(subset if len(subset) > 0 else [np.nan])
            box_colors.append(get_strategy_color(strategy))

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=box_width * 0.85,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "black", "linewidth": 1.5},
    )

    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)

    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels)
    ax.set_ylabel("Hand Value")
    ax.set_title("Hand Value Calibration: All Strategies by Contract Type")
    ax.grid(True, axis="y", alpha=0.3)

    # Legend
    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=get_strategy_color(s), alpha=0.75)
        for s in strategy_order
    ]
    legend_labels = [get_strategy_name(s) for s in strategy_order]
    ax.legend(legend_handles, legend_labels, loc="upper right", title="Strategy")

    plt.tight_layout()
    return _save_figure(fig, output_dir, "hand_value_all_strategies", dpi)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate Phase 0 report r4 charts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--zoom-dir",
        type=Path,
        required=True,
        help="Path to zoom run directory (self-play matchups)",
    )
    parser.add_argument(
        "--greedy-dir",
        type=Path,
        required=True,
        help="Path to greedy dataset run directory",
    )
    parser.add_argument(
        "--glutton-dir",
        type=Path,
        required=True,
        help="Path to glutton dataset run directory",
    )
    parser.add_argument(
        "--gate-json",
        type=Path,
        required=True,
        help="Path to play policy gate aggregate JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output directory for PNG charts",
    )
    parser.add_argument(
        "--mixed-play-dir",
        type=Path,
        default=None,
        help="Path to mixed-play dataset run directory (for all-strategy chart)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=150,
        help="Output resolution in DPI (default: 150)",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Validate input paths
    for name, path in [
        ("zoom-dir", args.zoom_dir),
        ("greedy-dir", args.greedy_dir),
        ("glutton-dir", args.glutton_dir),
        ("gate-json", args.gate_json),
    ]:
        if not path.exists():
            print(f"ERROR: --{name} path not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    charts_generated: List[str] = []

    # Chart 1: Self-play grouped boxplot (section 3)
    print("Generating self_play_grouped_boxplot.png (section 3)...")
    path = generate_self_play_grouped_boxplot(args.zoom_dir, args.output_dir, args.dpi)
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 2: Seat balance grouped boxplot (section 4)
    print("Generating seat_balance_grouped_boxplot.png (section 4)...")
    path = generate_seat_balance_grouped_boxplot(
        args.greedy_dir, args.output_dir, args.dpi
    )
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 3: Hand value by contract comparison (section 5a)
    print("Generating hand_value_by_contract_comparison.png (section 5a)...")
    path = generate_hand_value_by_contract_comparison(
        args.greedy_dir, args.glutton_dir, args.output_dir, args.dpi
    )
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 4: Tricks by contract comparison (section 5b)
    print("Generating tricks_by_contract_comparison.png (section 5b)...")
    path = generate_tricks_by_contract_comparison(
        args.greedy_dir, args.glutton_dir, args.output_dir, args.dpi
    )
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 5: CDF comparison (section 5b)
    print("Generating cdf_comparison.png (section 5b)...")
    path = generate_cdf_comparison(
        args.greedy_dir, args.glutton_dir, args.output_dir, args.dpi
    )
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 6: Hand value by trump comparison (section 5c)
    print("Generating hand_value_by_trump_comparison.png (section 5c)...")
    path = generate_hand_value_by_trump_comparison(
        args.greedy_dir, args.glutton_dir, args.output_dir, args.dpi
    )
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 7: Outcome by trump comparison (section 5c)
    print("Generating outcome_by_trump_comparison.png (section 5c)...")
    path = generate_outcome_by_trump_comparison(
        args.greedy_dir, args.glutton_dir, args.output_dir, args.dpi
    )
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 8: Advantage by contract (section 9c)
    print("Generating advantage_by_contract.png (section 9c)...")
    path = generate_advantage_by_contract(args.gate_json, args.output_dir, args.dpi)
    charts_generated.append(path)
    print(f"  -> {path}")

    # Chart 9: Hand value all strategies (section 5a, r5)
    if args.mixed_play_dir is not None:
        if not args.mixed_play_dir.exists():
            print(
                f"WARNING: --mixed-play-dir not found: {args.mixed_play_dir}",
                file=sys.stderr,
            )
        else:
            print("Generating hand_value_all_strategies.png (section 5a)...")
            path = generate_hand_value_all_strategies(
                args.mixed_play_dir, args.output_dir, args.dpi
            )
            charts_generated.append(path)
            print(f"  -> {path}")

    # Summary
    print(f"\nGenerated {len(charts_generated)} chart(s) in {args.output_dir}")

    # Write manifest
    manifest_path = args.output_dir / "chart_manifest.json"
    manifest_data = {
        "charts": charts_generated,
        "zoom_dir": str(args.zoom_dir),
        "greedy_dir": str(args.greedy_dir),
        "glutton_dir": str(args.glutton_dir),
        "gate_json": str(args.gate_json),
        "dpi": args.dpi,
    }
    if args.mixed_play_dir is not None:
        manifest_data["mixed_play_dir"] = str(args.mixed_play_dir)
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
