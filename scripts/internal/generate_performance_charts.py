#!/usr/bin/env python
"""Generate performance-over-time charts for Que and Meeks.

Reads CSV exports from the production database and generates
publication-quality charts comparing two human players' performance
trends against the bud_bot AI.

Usage::

    # Export data first (requires render CLI):
    #   See export commands in the script header comments
    # Then generate charts:
    uv run python scripts/internal/generate_performance_charts.py \
        --matches /tmp/que_meeks_matches.csv \
        --hands /tmp/que_meeks_hands.csv \
        --bids /tmp/que_meeks_bids.csv \
        --outdir plans/sessions/gameplay_screenshots

Data provenance: Render production DB (bideuchre-db), queried 2026-04-07.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# --- Style constants ---
COLORS = {"Que": "#1f77b4", "Meeks": "#ff7f0e"}  # blue / orange
FIGSIZE = (12, 6)
FIGSIZE_WIDE = (14, 7)
DPI = 150
sns.set_theme(style="whitegrid", font_scale=1.1)


def load_data(
    matches_path: str, hands_path: str, bids_path: str
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and prepare the three CSV datasets."""
    matches = pd.read_csv(matches_path, parse_dates=["created_at", "completed_at"])
    hands = pd.read_csv(hands_path, parse_dates=["completed_at"])
    bids = pd.read_csv(bids_path)

    # Parse bid JSON
    bids["bid_data"] = bids["chosen_action_json"].apply(json.loads)
    bids["bid_n"] = bids["bid_data"].apply(lambda x: x.get("n", 0))
    bids["bid_contract"] = bids["bid_data"].apply(lambda x: x.get("contract") or "PASS")
    bids["bid_type"] = bids["bid_data"].apply(lambda x: x.get("bid_type", "regular"))

    # Add match sequence number per player
    for player in ["Que", "Meeks"]:
        mask = matches["player"] == player
        matches.loc[mask, "match_seq"] = range(1, mask.sum() + 1)
    matches["match_seq"] = matches["match_seq"].astype(int)

    return matches, hands, bids


# ---------------------------------------------------------------------------
# Chart 1: Win rate over time (cumulative + rolling)
# ---------------------------------------------------------------------------


def chart_win_rate(matches: pd.DataFrame, outdir: Path) -> None:
    """Rolling and cumulative win rate for both players."""
    fig, axes = plt.subplots(1, 2, figsize=FIGSIZE_WIDE, sharey=True)

    for player in ["Que", "Meeks"]:
        df = matches[matches["player"] == player].copy()
        df = df.sort_values("created_at").reset_index(drop=True)
        df["cum_wins"] = df["win"].cumsum()
        df["cum_wr"] = df["cum_wins"] / (df.index + 1) * 100
        df["roll_wr"] = df["win"].rolling(5, min_periods=1).mean() * 100
        x = range(1, len(df) + 1)

        # Cumulative
        axes[0].plot(x, df["cum_wr"], color=COLORS[player], label=player, linewidth=2)
        # Rolling
        axes[1].plot(x, df["roll_wr"], color=COLORS[player], label=player, linewidth=2)

    axes[0].set_title("Cumulative Win Rate", fontweight="bold")
    axes[0].set_xlabel("Match Number (chronological)")
    axes[0].set_ylabel("Win Rate (%)")
    axes[0].axhline(50, color="gray", linestyle="--", alpha=0.5, label="50%")
    axes[0].legend()
    axes[0].set_ylim(0, 100)

    axes[1].set_title("Rolling Win Rate (5-match window)", fontweight="bold")
    axes[1].set_xlabel("Match Number (chronological)")
    axes[1].axhline(50, color="gray", linestyle="--", alpha=0.5)
    axes[1].legend()
    axes[1].set_ylim(0, 100)

    fig.suptitle("Win Rate Over Time: Que vs Meeks", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(outdir / "que_meeks_win_rate_trend.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ que_meeks_win_rate_trend.png")


# ---------------------------------------------------------------------------
# Chart 2: Points per hand over time
# ---------------------------------------------------------------------------


def chart_pph_trend(matches: pd.DataFrame, hands: pd.DataFrame, outdir: Path) -> None:
    """Rolling average net PPH across matches."""
    fig, ax = plt.subplots(figsize=FIGSIZE)

    for player in ["Que", "Meeks"]:
        mdf = matches[matches["player"] == player].sort_values("created_at")
        match_ids = mdf["match_id"].values

        # Compute net PPH per match
        pphs = []
        for mid in match_ids:
            hdf = hands[hands["match_id"] == mid]
            if len(hdf) == 0:
                pphs.append(0)
                continue
            net_pph = (hdf["points_team0"] - hdf["points_team1"]).mean()
            pphs.append(net_pph)

        pphs = pd.Series(pphs)
        rolling_pph = pphs.rolling(5, min_periods=1).mean()
        x = range(1, len(pphs) + 1)

        ax.plot(
            x,
            rolling_pph,
            color=COLORS[player],
            label=f"{player} (rolling 5)",
            linewidth=2,
        )
        ax.scatter(x, pphs, color=COLORS[player], alpha=0.3, s=30, zorder=2)

    ax.axhline(0, color="gray", linestyle="--", alpha=0.5)
    ax.set_title(
        "Net Points Per Hand Over Time (Rolling 5-match avg)",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Match Number (chronological)")
    ax.set_ylabel("Net PPH (team0 − opponents)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "que_meeks_pph_trend.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ que_meeks_pph_trend.png")


# ---------------------------------------------------------------------------
# Chart 3: Set rate trend
# ---------------------------------------------------------------------------


def chart_set_rate_trend(
    matches: pd.DataFrame, hands: pd.DataFrame, outdir: Path
) -> None:
    """Rolling set rate when declaring, by match."""
    fig, ax = plt.subplots(figsize=FIGSIZE)

    for player in ["Que", "Meeks"]:
        mdf = matches[matches["player"] == player].sort_values("created_at")
        match_ids = mdf["match_id"].values

        set_rates = []
        for mid in match_ids:
            hdf = hands[hands["match_id"] == mid]
            # Declaring = bidder_seat is 0 or 2 (team0)
            declaring = hdf[hdf["bidder_seat"].isin([0, 2])]
            if len(declaring) == 0:
                set_rates.append(np.nan)
                continue
            # Set = points_team0 < 0
            sets = (declaring["points_team0"] < 0).sum()
            set_rates.append(sets / len(declaring) * 100)

        sr = pd.Series(set_rates)
        rolling_sr = sr.rolling(5, min_periods=1).mean()
        x = range(1, len(sr) + 1)

        ax.plot(
            x,
            rolling_sr,
            color=COLORS[player],
            label=f"{player} (rolling 5)",
            linewidth=2,
        )
        ax.scatter(x, sr, color=COLORS[player], alpha=0.3, s=30, zorder=2)

    ax.set_title(
        "Set Rate When Declaring (Rolling 5-match avg)", fontsize=13, fontweight="bold"
    )
    ax.set_xlabel("Match Number (chronological)")
    ax.set_ylabel("Set Rate (%)")
    ax.legend()
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(outdir / "que_meeks_set_rate_trend.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ que_meeks_set_rate_trend.png")


# ---------------------------------------------------------------------------
# Chart 4: Score margin over time
# ---------------------------------------------------------------------------


def chart_score_margin(matches: pd.DataFrame, outdir: Path) -> None:
    """Per-match margin with trendline."""
    fig, ax = plt.subplots(figsize=FIGSIZE)

    for player in ["Que", "Meeks"]:
        df = matches[matches["player"] == player].sort_values("created_at")
        x = np.arange(1, len(df) + 1)
        y = df["margin"].values

        ax.scatter(
            x,
            y,
            color=COLORS[player],
            alpha=0.6,
            s=50,
            zorder=3,
            label=f"{player} (per match)",
        )

        # Trendline (linear regression)
        if len(x) > 1:
            z = np.polyfit(x, y, 1)
            p = np.poly1d(z)
            ax.plot(
                x,
                p(x),
                color=COLORS[player],
                linestyle="--",
                linewidth=1.5,
                alpha=0.7,
                label=f"{player} trend ({z[0]:+.1f}/match)",
            )

    ax.axhline(0, color="gray", linestyle="-", alpha=0.3)
    ax.set_title("Score Margin Per Match (Human − AI)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Match Number (chronological)")
    ax.set_ylabel("Score Margin")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "que_meeks_score_margin.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ que_meeks_score_margin.png")


# ---------------------------------------------------------------------------
# Chart 5: Bid level distribution comparison
# ---------------------------------------------------------------------------


def chart_bid_distribution(bids: pd.DataFrame, outdir: Path) -> None:
    """Side-by-side bar chart of bid level frequencies."""
    fig, ax = plt.subplots(figsize=FIGSIZE)

    # Filter to actual bids (exclude passes)
    actual_bids = bids[bids["bid_n"] > 0].copy()

    # Bin levels: 1-2, 3, 4, 5, 6, 7, 8-9, 10
    def level_bin(n: int) -> str:
        if n <= 2:
            return "1-2"
        elif n in (8, 9):
            return "8-9"
        else:
            return str(n)

    actual_bids["level_bin"] = actual_bids["bid_n"].apply(level_bin)
    bin_order = ["1-2", "3", "4", "5", "6", "7", "8-9", "10"]

    # Compute percentages per player
    bar_data = []
    for player in ["Que", "Meeks"]:
        pdf = actual_bids[actual_bids["player"] == player]
        total = len(pdf)
        for b in bin_order:
            count = (pdf["level_bin"] == b).sum()
            pct = count / total * 100 if total > 0 else 0
            bar_data.append(
                {"Player": player, "Bid Level": b, "Pct": pct, "Count": count}
            )

    bdf = pd.DataFrame(bar_data)

    x = np.arange(len(bin_order))
    width = 0.35

    que_data = bdf[bdf["Player"] == "Que"]
    meeks_data = bdf[bdf["Player"] == "Meeks"]

    bars1 = ax.bar(
        x - width / 2,
        que_data["Pct"],
        width,
        label="Que",
        color=COLORS["Que"],
        alpha=0.85,
    )
    bars2 = ax.bar(
        x + width / 2,
        meeks_data["Pct"],
        width,
        label="Meeks",
        color=COLORS["Meeks"],
        alpha=0.85,
    )

    # Add count labels on bars
    for bars, data in [(bars1, que_data), (bars2, meeks_data)]:
        for bar, (_, row) in zip(bars, data.iterrows()):
            if row["Count"] > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.5,
                    f"n={int(row['Count'])}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    alpha=0.7,
                )

    ax.set_xticks(x)
    ax.set_xticklabels(bin_order)
    ax.set_title("Bid Level Distribution: Que vs Meeks", fontsize=13, fontweight="bold")
    ax.set_xlabel("Bid Level")
    ax.set_ylabel("Frequency (%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(outdir / "que_meeks_bid_distribution.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ que_meeks_bid_distribution.png")


# ---------------------------------------------------------------------------
# Chart 6: Contract type performance heatmap
# ---------------------------------------------------------------------------


def chart_contract_heatmap(hands: pd.DataFrame, outdir: Path) -> None:
    """2x3 heatmap of make rate by player × contract type."""
    fig, ax = plt.subplots(figsize=(10, 5))

    contract_types = ["suit", "high", "low"]
    players = ["Que", "Meeks"]

    make_rates = np.zeros((len(players), len(contract_types)))
    annotations = []

    for i, player in enumerate(players):
        row_annot = []
        for j, ct in enumerate(contract_types):
            pdf = hands[(hands["player"] == player) & (hands["contract_type"] == ct)]
            # Only when team0 declares
            declaring = pdf[pdf["bidder_seat"].isin([0, 2])]
            if len(declaring) == 0:
                make_rates[i, j] = np.nan
                row_annot.append("N/A")
                continue
            made = (declaring["points_team0"] >= 0).sum()
            rate = made / len(declaring) * 100
            make_rates[i, j] = rate
            row_annot.append(f"{rate:.0f}%\n({made}/{len(declaring)})")
        annotations.append(row_annot)

    annot_arr = np.array(annotations)

    # Create heatmap
    cmap = sns.diverging_palette(10, 130, s=80, l=55, as_cmap=True)
    sns.heatmap(
        make_rates,
        annot=annot_arr,
        fmt="",
        xticklabels=[ct.upper() for ct in contract_types],
        yticklabels=players,
        cmap=cmap,
        vmin=60,
        vmax=100,
        linewidths=2,
        linecolor="white",
        ax=ax,
        cbar_kws={"label": "Make Rate (%)"},
    )

    ax.set_title(
        "Contract Type Performance: Make Rate When Declaring",
        fontsize=13,
        fontweight="bold",
    )
    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Player")
    fig.tight_layout()
    fig.savefig(outdir / "que_meeks_contract_heatmap.png", dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("  ✓ que_meeks_contract_heatmap.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Que vs Meeks performance charts"
    )
    parser.add_argument("--matches", required=True, help="Path to matches CSV export")
    parser.add_argument("--hands", required=True, help="Path to hands CSV export")
    parser.add_argument("--bids", required=True, help="Path to bids CSV export")
    parser.add_argument(
        "--outdir",
        default="plans/sessions/gameplay_screenshots",
        help="Output directory for PNG charts",
    )
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print("Loading data...")
    matches, hands, bids = load_data(args.matches, args.hands, args.bids)
    print(
        f"  Matches: {len(matches)} "
        f"(Que: {(matches['player'] == 'Que').sum()}, "
        f"Meeks: {(matches['player'] == 'Meeks').sum()})"
    )
    print(
        f"  Hands: {len(hands)} "
        f"(Que: {(hands['player'] == 'Que').sum()}, "
        f"Meeks: {(hands['player'] == 'Meeks').sum()})"
    )
    print(
        f"  Bids: {len(bids)} "
        f"(Que: {(bids['player'] == 'Que').sum()}, "
        f"Meeks: {(bids['player'] == 'Meeks').sum()})"
    )

    print(f"\nGenerating charts → {outdir}/")
    chart_win_rate(matches, outdir)
    chart_pph_trend(matches, hands, outdir)
    chart_set_rate_trend(matches, hands, outdir)
    chart_score_margin(matches, outdir)
    chart_bid_distribution(bids, outdir)
    chart_contract_heatmap(hands, outdir)

    print(f"\n✓ All 6 charts saved to {outdir}/")


if __name__ == "__main__":
    main()
