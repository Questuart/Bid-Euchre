"""Auction-related diagnostic charts for Arc D evaluation.

Provides charts for analyzing auction behavior and bidder performance
from eval JSONL datasets. All functions return Figure objects.
"""

from typing import List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..reporting.style import (
    BASE_COLORS,
    FIGSIZE_COMPARISON,
    apply_report_style,
    apply_seaborn_style,
    get_contract_color,
    get_contract_label,
)

try:
    import seaborn as sns  # noqa: F401

    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False


def _cycle_base_colors(n: int) -> List[str]:
    """Cycle through BASE_COLORS to get n colors."""
    return [BASE_COLORS[i % len(BASE_COLORS)] for i in range(n)]


def _apply_style() -> None:
    if HAS_SEABORN:
        apply_seaborn_style()
    else:
        apply_report_style()


def _missing_columns_message(
    ax: plt.Axes, required: List[str], available: pd.Index
) -> bool:
    """Display a text message for missing columns. Returns True if any missing."""
    missing = [c for c in required if c not in available]
    if missing:
        ax.text(
            0.5,
            0.5,
            f"Required columns missing:\n{', '.join(missing)}",
            ha="center",
            va="center",
            transform=ax.transAxes,
            fontsize=10,
        )
        return True
    return False


def plot_auction_health(
    df: pd.DataFrame,
    figsize: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot auction health diagnostics: contract selection, bid distribution, auction length.

    Creates a 1x3 figure summarizing auction behavior from an eval dataset.

    Parameters
    ----------
    df:
        DataFrame from ``build_eval_dataset()`` with per-seat rows.
        Expected columns: ``deal_id``, ``contract_type``, ``winning_bid``,
        ``auction_rounds``.
    figsize:
        Figure size tuple. Defaults to ``FIGSIZE_COMPARISON``.
    title:
        Optional suptitle override.

    Returns
    -------
    plt.Figure
        A 1x3 figure with contract selection, bid distribution, and
        auction length panels.
    """
    _apply_style()
    figsize = figsize or FIGSIZE_COMPARISON

    fig, axes = plt.subplots(1, 3, figsize=figsize)

    required = ["deal_id", "contract_type", "winning_bid", "auction_rounds"]
    if _missing_columns_message(axes[0], required, df.columns):
        for ax in axes[1:]:
            ax.set_visible(False)
        plt.tight_layout()
        return fig

    # Deduplicate to deal-level (1 row per deal_id)
    deal_df = df.drop_duplicates(subset="deal_id")

    if len(deal_df) == 0:
        axes[0].text(
            0.5,
            0.5,
            "No deals found",
            ha="center",
            va="center",
            transform=axes[0].transAxes,
        )
        for ax in axes[1:]:
            ax.set_visible(False)
        plt.tight_layout()
        return fig

    # ---- Panel 1: Contract selection bar chart ----
    ax = axes[0]
    contract_order = ["suit", "high", "low"]
    present = [ct for ct in contract_order if ct in deal_df["contract_type"].values]
    if not present:
        present = sorted(deal_df["contract_type"].unique())

    counts = deal_df["contract_type"].value_counts()
    bar_counts = [counts.get(ct, 0) for ct in present]
    colors = [get_contract_color(ct) for ct in present]
    labels = [get_contract_label(ct) for ct in present]

    ax.bar(range(len(present)), bar_counts, color=colors, alpha=0.8)
    ax.set_xticks(range(len(present)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Count")
    ax.set_title("Contract Selection")
    ax.grid(True, alpha=0.3, axis="y")

    # Annotate with counts
    for i, count in enumerate(bar_counts):
        ax.text(i, count + 0.5, str(count), ha="center", va="bottom", fontsize=9)

    # ---- Panel 2: Bid distribution histogram ----
    ax = axes[1]
    valid_bids = deal_df.dropna(subset=["winning_bid"])
    if len(valid_bids) > 0:
        bid_values = valid_bids["winning_bid"].values
        bid_min = int(np.nanmin(bid_values))
        bid_max = int(np.nanmax(bid_values))
        bins = np.arange(bid_min - 0.5, bid_max + 1.5, 1)

        # Color by contract type
        for ct in present:
            ct_bids = valid_bids[valid_bids["contract_type"] == ct][
                "winning_bid"
            ].values
            if len(ct_bids) > 0:
                ax.hist(
                    ct_bids,
                    bins=bins,
                    alpha=0.6,
                    color=get_contract_color(ct),
                    label=get_contract_label(ct),
                    edgecolor="black",
                    linewidth=0.5,
                )
        ax.legend(fontsize=8)
    else:
        ax.text(
            0.5, 0.5, "No valid bids", ha="center", va="center", transform=ax.transAxes
        )

    ax.set_xlabel("Winning Bid")
    ax.set_ylabel("Count")
    ax.set_title("Bid Distribution")
    ax.grid(True, alpha=0.3, axis="y")

    # ---- Panel 3: Auction length histogram ----
    ax = axes[2]
    rounds = deal_df["auction_rounds"].dropna().values
    if len(rounds) > 0:
        round_min = int(np.nanmin(rounds))
        round_max = int(np.nanmax(rounds))
        bins = np.arange(round_min - 0.5, round_max + 1.5, 1)
        ax.hist(
            rounds,
            bins=bins,
            color=BASE_COLORS[0],
            alpha=0.7,
            edgecolor="black",
            linewidth=0.5,
        )
        ax.axvline(
            np.mean(rounds),
            color="red",
            linestyle="--",
            label=f"Mean: {np.mean(rounds):.1f}",
        )
        ax.legend(fontsize=8)
    else:
        ax.text(
            0.5,
            0.5,
            "No auction data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_xlabel("Auction Rounds")
    ax.set_ylabel("Count")
    ax.set_title("Auction Length")
    ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle(title or "Auction Health Diagnostics", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig


def plot_bidder_performance(
    df: pd.DataFrame,
    figsize: Optional[Tuple[int, int]] = None,
    title: Optional[str] = None,
) -> plt.Figure:
    """Plot bidder performance: make rate by contract, make rate curve, overbid histogram.

    Creates a 1x3 figure analyzing bidder accuracy and calibration.

    Parameters
    ----------
    df:
        DataFrame from ``build_eval_dataset()`` with per-seat rows.
        Expected columns: ``is_bidder``, ``contract_type``, ``made_bid``,
        ``winning_bid``, ``is_declaring_team``, ``tricks_won``.
    figsize:
        Figure size tuple. Defaults to ``FIGSIZE_COMPARISON``.
    title:
        Optional suptitle override.

    Returns
    -------
    plt.Figure
        A 1x3 figure with make rate by contract, make rate curve by bid value,
        and overbid/underbid histogram.
    """
    _apply_style()
    figsize = figsize or FIGSIZE_COMPARISON

    fig, axes = plt.subplots(1, 3, figsize=figsize)

    required = [
        "is_bidder",
        "contract_type",
        "made_bid",
        "winning_bid",
        "is_declaring_team",
        "tricks_won",
    ]
    if _missing_columns_message(axes[0], required, df.columns):
        for ax in axes[1:]:
            ax.set_visible(False)
        plt.tight_layout()
        return fig

    # Filter to bidder rows only
    bidder_df = df[df["is_bidder"] == True].copy()  # noqa: E712

    if len(bidder_df) == 0:
        axes[0].text(
            0.5,
            0.5,
            "No bidder rows found\n(is_bidder == True)",
            ha="center",
            va="center",
            transform=axes[0].transAxes,
        )
        for ax in axes[1:]:
            ax.set_visible(False)
        plt.tight_layout()
        return fig

    # ---- Panel 1: Make rate bar chart by contract_type ----
    ax = axes[0]
    contract_order = ["suit", "high", "low"]
    present = [ct for ct in contract_order if ct in bidder_df["contract_type"].values]
    if not present:
        present = sorted(bidder_df["contract_type"].unique())

    make_rates = []
    for ct in present:
        ct_df = bidder_df[bidder_df["contract_type"] == ct]
        valid = ct_df["made_bid"].dropna()
        rate = valid.mean() if len(valid) > 0 else 0.0
        make_rates.append(rate)

    colors = [get_contract_color(ct) for ct in present]
    labels = [get_contract_label(ct) for ct in present]
    bars = ax.bar(range(len(present)), make_rates, color=colors, alpha=0.8)
    ax.set_xticks(range(len(present)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Make Rate")
    ax.set_title("Make Rate by Contract")
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3, axis="y")

    # Annotate bars
    for bar, rate in zip(bars, make_rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{rate:.1%}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # ---- Panel 2: Make rate curve by bid value ----
    ax = axes[1]
    valid_bids = bidder_df.dropna(subset=["winning_bid", "made_bid"])
    if len(valid_bids) > 0:
        grouped = valid_bids.groupby("winning_bid")["made_bid"]
        bid_vals = sorted(valid_bids["winning_bid"].unique())
        means = [grouped.get_group(bv).mean() for bv in bid_vals]
        counts = [len(grouped.get_group(bv)) for bv in bid_vals]

        # Binomial CI: mean +/- 1.96 * sqrt(p*(1-p)/n)
        ci_lower = []
        ci_upper = []
        for m, n in zip(means, counts):
            if n > 0:
                se = np.sqrt(m * (1 - m) / n) if n > 1 else 0.0
                ci_lower.append(max(0, m - 1.96 * se))
                ci_upper.append(min(1, m + 1.96 * se))
            else:
                ci_lower.append(0)
                ci_upper.append(0)

        ax.plot(bid_vals, means, "o-", color=BASE_COLORS[0], linewidth=2, markersize=6)
        ax.fill_between(
            bid_vals,
            ci_lower,
            ci_upper,
            alpha=0.2,
            color=BASE_COLORS[0],
            label="95% CI",
        )
        ax.legend(fontsize=8)

        # Annotate sample sizes
        for bv, n in zip(bid_vals, counts):
            ax.annotate(
                f"n={n}",
                xy=(bv, 0.02),
                ha="center",
                fontsize=7,
                alpha=0.6,
            )
    else:
        ax.text(
            0.5,
            0.5,
            "No valid bid data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_xlabel("Winning Bid")
    ax.set_ylabel("Make Rate")
    ax.set_title("Make Rate by Bid Value")
    ax.set_ylim(-0.05, 1.05)
    ax.grid(True, alpha=0.3)

    # ---- Panel 3: Overbid/underbid histogram ----
    ax = axes[2]
    # Get declaring team tricks for each deal — use bidder rows which have
    # is_declaring_team == True (the bidder IS on the declaring team)
    # The bidder_df already has tricks_won for the bidder's team
    overbid_df = bidder_df.dropna(subset=["winning_bid", "tricks_won"]).copy()
    if len(overbid_df) > 0:
        residuals = overbid_df["winning_bid"].values - overbid_df["tricks_won"].values
        # Reasonable bin range
        r_min = int(np.floor(residuals.min())) - 1
        r_max = int(np.ceil(residuals.max())) + 1
        bins = np.arange(r_min - 0.5, r_max + 1.5, 1)

        n_vals, bin_edges, patches = ax.hist(
            residuals,
            bins=bins,
            color=BASE_COLORS[2],
            alpha=0.7,
            edgecolor="black",
            linewidth=0.5,
        )

        # Color overbids red, underbids green, exact blue
        for patch, left_edge in zip(patches, bin_edges[:-1]):
            center = left_edge + 0.5
            if center > 0.5:
                patch.set_facecolor("#e74c3c")  # Red = overbid
                patch.set_alpha(0.7)
            elif center < -0.5:
                patch.set_facecolor("#27ae60")  # Green = underbid
                patch.set_alpha(0.7)
            else:
                patch.set_facecolor("#3498db")  # Blue = exact
                patch.set_alpha(0.7)

        ax.axvline(0, color="black", linestyle="-", linewidth=1.5)
        mean_residual = np.mean(residuals)
        ax.axvline(
            mean_residual,
            color="red",
            linestyle="--",
            label=f"Mean: {mean_residual:+.2f}",
        )
        ax.legend(fontsize=8)
    else:
        ax.text(
            0.5,
            0.5,
            "No bid/tricks data",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    ax.set_xlabel("Bid - Tricks Won (positive = overbid)")
    ax.set_ylabel("Count")
    ax.set_title("Overbid / Underbid")
    ax.grid(True, alpha=0.3, axis="y")

    fig.suptitle(title or "Bidder Performance Diagnostics", fontsize=14, y=1.02)
    plt.tight_layout()
    return fig
