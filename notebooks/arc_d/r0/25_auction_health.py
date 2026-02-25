# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags
#     formats: ipynb,py:percent
#     notebook_metadata_filter: jupytext,kernelspec,language_info
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
#   language_info:
#     name: python
# ---

# %% [markdown]
# # Auction Health Analysis
#
# **Goal:** Comprehensive auction health diagnostics for Arc D evaluation data.
# Validates bid distributions, bidder/dealer seat uniformity, make rate calibration,
# and auction length patterns. Extracted from `40_r0_baseline.py` §2/§4 and expanded
# with review-tracked issues C39, C40, C42, C43, C49.
#
# **Data source:** JSONL eval logs (primary) or synthetic demo data (CI fallback).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
# - Parameterize via papermill — do not hardcode paths.

# %% tags=["parameters"]
EVAL_LOG_PATH = "data/runs/arc_d_eval_r0_42_20260221_180253"
MODE = "QUICK"
RUNG_ID = "r0"
CHART_OUTPUT_DIR = ""
SEED = 42

# %% [markdown]
# # S0: Configuration & Data Loading

# %%
import os
import warnings
from pathlib import Path

# Ensure CWD is repo root (Jupyter kernels start in notebook dir)
_cwd = Path.cwd()
if not (_cwd / ".git").exists():
    _root = _cwd
    while _root != _root.parent:
        _root = _root.parent
        if (_root / ".git").exists():
            os.chdir(_root)
            break
    else:
        print(f"WARNING: Could not find repo root from {_cwd}")
print(f"Working directory: {Path.cwd()}")

# %% [markdown]
# ## Available eval runs
# Run this cell to discover local eval data:

# %%
for _p in (
    sorted(Path("data/runs").glob("arc_d_eval*")) if Path("data/runs").exists() else []
):
    print(_p)

# %%
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chisquare, f_oneway

from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.diagnostics.auction_charts import (
    plot_auction_health,
    plot_bidder_performance,
)

matplotlib.use("Agg")

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
_max_deals = MODE_DEAL_COUNTS.get(MODE, 30)
if MODE not in MODE_DEAL_COUNTS:
    warnings.warn(f"Unknown MODE={MODE!r}, defaulting to 30 deals", stacklevel=2)
max_deals = _max_deals

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

if EVAL_LOG_PATH:
    eval_run = Path(EVAL_LOG_PATH)
    log_files = sorted(eval_run.glob("logs/*.jsonl"))
    if log_files:
        try:
            df = build_eval_dataset(str(log_files[0]), max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {log_files[0].name}")
            print(f"  Deals: {df['deal_id'].nunique()}, Source: {_data_source}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"WARNING: Could not load eval logs: {exc}")

if EVAL_LOG_PATH and df.empty:
    print(
        f"WARNING: EVAL_LOG_PATH={EVAL_LOG_PATH!r} is set but no data was loaded.\n"
        "  Check that the path exists relative to the repo root."
    )

if df.empty:
    # Synthetic demo data for CI / SMOKE fallback
    rng = np.random.default_rng(SEED)
    n_deals = max_deals or 30
    rows = []
    for deal_id in range(n_deals):
        contract = rng.choice(["suit", "high", "low"])
        trump = rng.choice(["C", "D", "H", "S"]) if contract == "suit" else None
        t0 = rng.integers(0, 11)
        t1 = 10 - t0
        winning_bid = int(rng.integers(5, 11))
        made = bool(t0 >= winning_bid)
        bidder_seat = int(rng.integers(0, 4))
        dealer_seat = int(rng.integers(0, 4))
        n_bids = int(rng.integers(1, 5))
        n_passes = int(rng.integers(1, 5))
        auction_rounds = n_bids + n_passes
        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            bidder_team = 0 if bidder_seat in (0, 2) else 1
            tricks = t0 if seat in (0, 2) else t1
            if team == bidder_team:
                pts = tricks if made else -winning_bid
            else:
                pts = tricks
            rows.append(
                {
                    "deal_id": deal_id,
                    "seat": seat,
                    "team": team,
                    "contract_type": contract,
                    "trump": trump,
                    "tricks_won": tricks,
                    "points_won": pts,
                    "winning_bid": winning_bid,
                    "made_bid": made,
                    "is_bidder": seat == bidder_seat,
                    "is_declaring_team": team == bidder_team,
                    "bidder_seat": bidder_seat,
                    "dealer_seat": dealer_seat,
                    "n_bids": n_bids,
                    "n_passes": n_passes,
                    "auction_rounds": auction_rounds,
                }
            )
    df = pd.DataFrame(rows)
    _data_source = "synthetic"
    print(f"Using synthetic demo data ({n_deals} deals, {len(df)} rows)")

# Deal-level aggregate (one row per deal)
deal_df = df[df["seat"] == 0].copy()

print(f"\nMODE={MODE}, data_source={_data_source}")
print()
print("=" * 60)
print("RUN METADATA")
print("=" * 60)
print(f"  Data source:    {_data_source}")
print(f"  Run directory:  {EVAL_LOG_PATH or 'N/A (synthetic)'}")
print(f"  Total deals:    {df['deal_id'].nunique():,}")
print(f"  Total rows:     {len(df):,} (4 per deal)")
print(f"  Mode:           {MODE}")
print(f"  Seed:           {SEED}")
if "contract_type" in df.columns:
    ct_counts = dict(df.drop_duplicates("deal_id")["contract_type"].value_counts())
    print(f"  Contract types: {ct_counts}")

# %% [markdown]
# # S1: Fail-Fast Validation

# %%
# --- Core shape checks ---
assert len(df) > 0, "DataFrame is empty"
assert df["deal_id"].nunique() >= 10, f"Need >= 10 deals, got {df['deal_id'].nunique()}"
assert (
    len(df) == 4 * df["deal_id"].nunique()
), f"Expected 4 rows/deal, got {len(df)} rows for {df['deal_id'].nunique()} deals"

# --- Columns for plot_auction_health ---
for col in ("deal_id", "contract_type", "winning_bid", "auction_rounds"):
    assert col in df.columns, f"Missing column for auction health chart: {col}"

# --- Columns for plot_bidder_performance ---
for col in (
    "is_bidder",
    "contract_type",
    "made_bid",
    "winning_bid",
    "is_declaring_team",
    "tricks_won",
):
    assert col in df.columns, f"Missing column for bidder performance chart: {col}"

# --- Auction-specific columns (required when eval logs present) ---
if _data_source == "eval_logs":
    for col in ("n_bids", "n_passes", "auction_rounds"):
        assert (
            col in df.columns and df[col].notna().all()
        ), f"Auction column {col} missing or has nulls in eval_logs mode"

# --- Seat analysis columns ---
for col in ("bidder_seat", "dealer_seat"):
    assert col in df.columns, f"Missing seat column: {col}"

print("All validation checks passed.")

# %% [markdown]
# # S2: Bid Distribution by Contract (C40)
#
# Baseline auction health from library chart, then suit-contract breakout by trump.

# %%
fig_auction = plot_auction_health(df)
if CHART_OUTPUT_DIR:
    out = Path(CHART_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    fig_auction.savefig(out / "auction_health.png", dpi=150)
plt.show()

# C40: suit breakout — bid distribution faceted by trump suit
suit_deals = deal_df[deal_df["contract_type"] == "suit"]
if not suit_deals.empty and "trump" in suit_deals.columns:
    trumps = sorted(suit_deals["trump"].dropna().unique())
    if trumps:
        n_trumps = len(trumps)
        fig_suit, axes_suit = plt.subplots(
            1, n_trumps, figsize=(4 * n_trumps, 4), sharey=True
        )
        if not hasattr(axes_suit, "__len__"):
            axes_suit = [axes_suit]
        for ax, trump in zip(axes_suit, trumps):
            grp = suit_deals[suit_deals["trump"] == trump]
            if "winning_bid" in grp.columns and not grp.empty:
                grp["winning_bid"].value_counts().sort_index().plot.bar(ax=ax)
                ax.set_title(f"Suit: trump={trump} (n={len(grp)})")
                ax.set_xlabel("Winning Bid")
                ax.set_ylabel("Count")
        plt.suptitle("Bid Distribution by Trump Suit (suit contracts)", fontsize=12)
        plt.tight_layout()
        plt.show()
else:
    print("No suit contracts with trump data — skipping trump breakout.")

# Contract selection frequency table
print("\n=== Contract Selection Frequency ===")
ct_freq = deal_df["contract_type"].value_counts()
ct_pct = deal_df["contract_type"].value_counts(normalize=True) * 100
ct_table = pd.DataFrame({"count": ct_freq, "pct": ct_pct.round(1)})
print(ct_table.to_string())

# %% [markdown]
# # S3: Bidder & Dealer Seat Distributions (C39)
#
# Uniformity tests for bidder and dealer positions. Chi-square tests expect
# 25% per seat; ANOVA checks bid height by dealer seat.

# %%
# --- Bidder seat distribution ---
print("=== Bidder Seat Distribution ===")
bidder_seat_counts = deal_df["bidder_seat"].value_counts().sort_index()
print(bidder_seat_counts.to_string())

fig_bs, ax_bs = plt.subplots(figsize=(6, 4))
bidder_seat_counts.plot.bar(ax=ax_bs, color="#2196F3", edgecolor="black")
ax_bs.set_xlabel("Bidder Seat")
ax_bs.set_ylabel("Count")
ax_bs.set_title("Bidder Seat Distribution")
ax_bs.axhline(
    len(deal_df) / 4, color="red", linestyle="--", alpha=0.5, label="Expected (uniform)"
)
ax_bs.legend()
plt.tight_layout()
plt.show()

# Guarded chi-square: need all 4 seats with n >= 2
seats_present = bidder_seat_counts.index.tolist()
if len(seats_present) == 4 and all(bidder_seat_counts[s] >= 2 for s in seats_present):
    observed = [bidder_seat_counts.get(s, 0) for s in range(4)]
    chi2, p_val = chisquare(observed)
    print(f"Chi-square uniformity test: chi2={chi2:.4f}, p={p_val:.4f}")
    if p_val < 0.05:
        print("WARNING: Non-uniform bidder seat distribution (p < 0.05)")
else:
    print("Insufficient data for chi-square test (need all 4 seats with n>=2)")

# --- Dealer seat distribution ---
print("\n=== Dealer Seat Distribution ===")
dealer_seat_counts = deal_df["dealer_seat"].value_counts().sort_index()
print(dealer_seat_counts.to_string())

fig_ds, ax_ds = plt.subplots(figsize=(6, 4))
dealer_seat_counts.plot.bar(ax=ax_ds, color="#FF9800", edgecolor="black")
ax_ds.set_xlabel("Dealer Seat")
ax_ds.set_ylabel("Count")
ax_ds.set_title("Dealer Seat Distribution")
ax_ds.axhline(
    len(deal_df) / 4, color="red", linestyle="--", alpha=0.5, label="Expected (uniform)"
)
ax_ds.legend()
plt.tight_layout()
plt.show()

dealer_seats_present = dealer_seat_counts.index.tolist()
if len(dealer_seats_present) == 4 and all(
    dealer_seat_counts[s] >= 2 for s in dealer_seats_present
):
    observed_d = [dealer_seat_counts.get(s, 0) for s in range(4)]
    chi2_d, p_val_d = chisquare(observed_d)
    print(f"Chi-square uniformity test: chi2={chi2_d:.4f}, p={p_val_d:.4f}")
    if p_val_d < 0.05:
        print("WARNING: Non-uniform dealer seat distribution (p < 0.05)")
else:
    print("Insufficient data for chi-square test (need all 4 seats with n>=2)")

# --- Bid height by dealer seat ---
print("\n=== Bid Height by Dealer Seat ===")
groups = []
group_labels = []
for seat in sorted(deal_df["dealer_seat"].unique()):
    grp = deal_df[deal_df["dealer_seat"] == seat]["winning_bid"].dropna()
    if len(grp) >= 2:
        groups.append(grp.values)
        group_labels.append(seat)
    print(f"  Seat {seat}: mean_bid={grp.mean():.2f}, n={len(grp)}")

if len(groups) >= 2:
    f_stat, p_val_a = f_oneway(*groups)
    print(f"ANOVA (bid height by dealer seat): F={f_stat:.4f}, p={p_val_a:.4f}")
    if p_val_a < 0.05:
        print("WARNING: Significant bid height difference by dealer seat (p < 0.05)")
else:
    print("Insufficient data for ANOVA (need >= 2 groups with n>=2)")

# --- Cross-tab: bidder_seat x contract_type ---
print("\n=== Bidder Seat x Contract Type ===")
xtab = pd.crosstab(deal_df["bidder_seat"], deal_df["contract_type"])
print(xtab.to_string())

fig_xt, ax_xt = plt.subplots(figsize=(8, 5))
xtab.plot.bar(ax=ax_xt, edgecolor="black")
ax_xt.set_xlabel("Bidder Seat")
ax_xt.set_ylabel("Count")
ax_xt.set_title("Bidder Seat × Contract Type")
ax_xt.legend(title="Contract Type")
plt.tight_layout()
plt.show()

# %% [markdown]
# # S4: Make Rate & Surplus (C42)
#
# Baseline bidder performance from library chart, then per-contract surplus table.

# %%
fig_perf = plot_bidder_performance(df)
if CHART_OUTPUT_DIR:
    out = Path(CHART_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    fig_perf.savefig(out / "bidder_performance.png", dpi=150)
plt.show()

# Per-contract accuracy table
bidder_df = df[df["is_bidder"] == True].copy()  # noqa: E712
if not bidder_df.empty:
    print("\n=== Per-Contract Make Rate & Surplus ===")
    for ctype in sorted(bidder_df["contract_type"].unique()):
        grp = bidder_df[bidder_df["contract_type"] == ctype]
        n = len(grp)
        if n == 0:
            continue
        make_rate = (
            grp["made_bid"].mean() if "made_bid" in grp.columns else float("nan")
        )
        surplus = (grp["tricks_won"] - grp["winning_bid"]).values
        overbid_rate = (surplus < 0).mean()
        underbid_rate = (surplus > 1).mean()
        mean_surplus = surplus.mean()
        print(f"\n{ctype} (n={n}):")
        print(f"  Make rate:    {make_rate:.3f}")
        print(f"  Mean surplus: {mean_surplus:+.2f}")
        print(f"  Overbid rate: {overbid_rate:.3f}")
        print(f"  Underbid (>1 surplus): {underbid_rate:.3f}")

    # Surplus distribution faceted by contract_type
    ctypes = sorted(bidder_df["contract_type"].unique())
    n_ct = len(ctypes)
    fig_surplus, axes_s = plt.subplots(1, n_ct, figsize=(5 * n_ct, 4), sharey=True)
    if not hasattr(axes_s, "__len__"):
        axes_s = [axes_s]
    for ax, ctype in zip(axes_s, ctypes):
        grp = bidder_df[bidder_df["contract_type"] == ctype]
        surplus = grp["tricks_won"] - grp["winning_bid"]
        ax.hist(surplus, bins=range(-11, 12), edgecolor="black", alpha=0.7)
        ax.axvline(0, color="red", linestyle="--", linewidth=1)
        ax.set_title(f"Surplus: {ctype} (n={len(grp)})")
        ax.set_xlabel("Tricks Won - Bid")
        ax.set_ylabel("Count")
    plt.suptitle("Surplus Distribution by Contract Type", fontsize=12)
    plt.tight_layout()
    plt.show()
else:
    print("No bidder rows found — skipping make rate analysis.")

# %% [markdown]
# # S5: Seat-Faceted Bid Accuracy (C43)
#
# Make rate and surplus broken down by bidder seat, per contract type.

# %%
if not bidder_df.empty:
    # Make rate by bidder seat, grouped by contract type
    ctypes = sorted(bidder_df["contract_type"].unique())
    seats = sorted(bidder_df["bidder_seat"].unique())

    # Build matrix: rows = seats, cols = contract types
    make_matrix = {}
    for ctype in ctypes:
        for seat in seats:
            grp = bidder_df[
                (bidder_df["contract_type"] == ctype)
                & (bidder_df["bidder_seat"] == seat)
            ]
            key = (seat, ctype)
            make_matrix[key] = grp["made_bid"].mean() if len(grp) > 0 else float("nan")

    # Grouped bar: make rate by bidder seat
    fig_seat_mr, ax_smr = plt.subplots(figsize=(8, 5))
    x = np.arange(len(seats))
    width = 0.8 / max(len(ctypes), 1)
    for i, ctype in enumerate(ctypes):
        vals = [make_matrix.get((s, ctype), float("nan")) for s in seats]
        ax_smr.bar(x + i * width, vals, width, label=ctype)
    ax_smr.set_xticks(x + width * (len(ctypes) - 1) / 2)
    ax_smr.set_xticklabels([f"Seat {s}" for s in seats])
    ax_smr.set_xlabel("Bidder Seat")
    ax_smr.set_ylabel("Make Rate")
    ax_smr.set_title("Make Rate by Bidder Seat (per contract)")
    ax_smr.set_ylim(0, 1.05)
    ax_smr.legend(title="Contract Type")
    ax_smr.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.show()

    # Mean surplus by bidder seat
    fig_seat_sur, ax_ssur = plt.subplots(figsize=(8, 5))
    for i, ctype in enumerate(ctypes):
        surplus_by_seat = []
        for seat in seats:
            grp = bidder_df[
                (bidder_df["contract_type"] == ctype)
                & (bidder_df["bidder_seat"] == seat)
            ]
            surplus_by_seat.append(
                (grp["tricks_won"] - grp["winning_bid"]).mean()
                if len(grp) > 0
                else float("nan")
            )
        ax_ssur.bar(x + i * width, surplus_by_seat, width, label=ctype)
    ax_ssur.set_xticks(x + width * (len(ctypes) - 1) / 2)
    ax_ssur.set_xticklabels([f"Seat {s}" for s in seats])
    ax_ssur.set_xlabel("Bidder Seat")
    ax_ssur.set_ylabel("Mean Surplus (tricks - bid)")
    ax_ssur.set_title("Mean Surplus by Bidder Seat (per contract)")
    ax_ssur.axhline(0, color="red", linestyle="--", alpha=0.5)
    ax_ssur.legend(title="Contract Type")
    ax_ssur.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.show()

    # Guarded ANOVA: make rate by seat
    print("\n=== ANOVA: Make Rate by Bidder Seat ===")
    anova_groups = []
    for seat in seats:
        grp = bidder_df[bidder_df["bidder_seat"] == seat]["made_bid"].dropna()
        if len(grp) >= 2:
            anova_groups.append(grp.values.astype(float))
    if len(anova_groups) >= 2:
        f_stat, p_val = f_oneway(*anova_groups)
        print(f"F={f_stat:.4f}, p={p_val:.4f}")
        if p_val < 0.05:
            print("WARNING: Significant make rate difference by bidder seat (p < 0.05)")
    else:
        print("Insufficient data for ANOVA (need >= 2 groups with n>=2)")

    # Per-seat, per-contract make rate matrix
    print("\n=== Make Rate Matrix (seat x contract) ===")
    mr_df = pd.DataFrame(
        {
            ctype: {
                f"Seat {s}": make_matrix.get((s, ctype), float("nan")) for s in seats
            }
            for ctype in ctypes
        }
    )
    print(mr_df.round(3).to_string())
else:
    print("No bidder rows — skipping seat-faceted analysis.")

# %% [markdown]
# # S6: Auction Length & Pass Rate
#
# Auction dynamics: rounds distribution, pass rate per deal,
# and auction length vs bid correlation.

# %%
# Auction rounds distribution per contract type
ctypes = sorted(deal_df["contract_type"].unique())
n_ct = len(ctypes)
fig_rounds, axes_r = plt.subplots(1, n_ct, figsize=(5 * n_ct, 4), sharey=True)
if not hasattr(axes_r, "__len__"):
    axes_r = [axes_r]
for ax, ctype in zip(axes_r, ctypes):
    grp = deal_df[deal_df["contract_type"] == ctype]
    rounds = grp["auction_rounds"].dropna()
    if not rounds.empty:
        r_min = int(rounds.min())
        r_max = int(rounds.max())
        bins = range(max(0, r_min - 1), r_max + 2)
        ax.hist(rounds, bins=bins, edgecolor="black", alpha=0.7)
        ax.axvline(
            rounds.mean(),
            color="red",
            linestyle="--",
            label=f"Mean: {rounds.mean():.1f}",
        )
        ax.legend(fontsize=8)
    ax.set_title(f"Auction Rounds: {ctype} (n={len(grp)})")
    ax.set_xlabel("Rounds")
    ax.set_ylabel("Count")
plt.suptitle("Auction Length by Contract Type", fontsize=12)
plt.tight_layout()
plt.show()

# Pass rate per deal (mean of per-deal ratios avoids Jensen's inequality)
if "n_passes" in deal_df.columns and "n_bids" in deal_df.columns:
    total_actions = deal_df["n_bids"] + deal_df["n_passes"]
    deal_pass_rate = deal_df["n_passes"] / total_actions.replace(0, np.nan)
    mean_pass_rate = deal_pass_rate.mean()
    print("\n=== Pass Rate (mean of per-deal ratios) ===")
    print(f"  Mean pass rate: {mean_pass_rate:.3f}")
    print(f"  Std:  {deal_pass_rate.std():.3f}")

    # Per contract type
    for ctype in ctypes:
        grp = deal_df[deal_df["contract_type"] == ctype]
        total = grp["n_bids"] + grp["n_passes"]
        pr = grp["n_passes"] / total.replace(0, np.nan)
        print(
            f"  {ctype}: pass_rate={pr.mean():.3f}, "
            f"mean_bids={grp['n_bids'].mean():.2f}, "
            f"mean_passes={grp['n_passes'].mean():.2f}"
        )

# Scatter: auction length vs winning bid
if "auction_rounds" in deal_df.columns and "winning_bid" in deal_df.columns:
    fig_scatter, ax_sc = plt.subplots(figsize=(7, 5))
    for ctype in ctypes:
        grp = deal_df[deal_df["contract_type"] == ctype]
        ax_sc.scatter(
            grp["auction_rounds"],
            grp["winning_bid"],
            alpha=0.4,
            s=15,
            label=ctype,
        )
    ax_sc.set_xlabel("Auction Rounds")
    ax_sc.set_ylabel("Winning Bid")
    ax_sc.set_title("Auction Length vs Winning Bid")
    ax_sc.legend(title="Contract Type")
    ax_sc.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

# %% [markdown]
# # S7: Summary
#
# Key findings and cross-references to companion notebooks.

# %%
print("=" * 60)
print("AUCTION HEALTH SUMMARY")
print("=" * 60)
print(f"  Deals analysed: {deal_df['deal_id'].nunique():,}")
print(f"  Data source:    {_data_source}")
print(f"  Mode:           {MODE}")
print()
print("Cross-references:")
print("  - Feature health:           10_feature_health.py")
print("  - Outcome health:           20_outcome_health.py")
print("  - Baseline eval (model):    40_r0_baseline.py")
