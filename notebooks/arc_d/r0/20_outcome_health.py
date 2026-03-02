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
# # Outcome Health — Arc D Evaluation
#
# **Goal:** Validate outcome distributions, team balance, and bidder
# performance from an Arc D eval JSONL log.
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
# # S0 Configuration & Data Loading
#
# Load eval JSONL logs (primary) or generate synthetic demo data (CI fallback).
# Constructs a row-level DataFrame (`df`, 4 rows per deal) and a deal-level
# DataFrame (`deal_df`, 1 row per deal via seat-0 filter).

# %%
import os
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
import glob as _g

for _p in sorted(_g.glob("data/runs/arc_d_eval*")):
    print(_p)

# %%
# C1: removed duplicate `import glob as glob_mod`; using Path.glob() below

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.diagnostics.auction_charts import (
    plot_auction_health,
    plot_bidder_performance,
)
from bid_euchre.diagnostics.charts import (
    plot_ccdf,
    plot_cdf,
    plot_outcome_distributions,
)

matplotlib.use("Agg")

try:
    from scipy.stats import binom  # noqa: F401

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
max_deals = MODE_DEAL_COUNTS.get(MODE, 30)

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

if EVAL_LOG_PATH:
    log_path = Path(EVAL_LOG_PATH)
    if log_path.is_dir():
        # C1: use Path.glob() instead of glob_mod.glob()
        log_files = sorted((log_path / "logs").glob("*.jsonl"))
        if log_files:
            log_path = log_files[0]
    if log_path.is_file():
        try:
            df = build_eval_dataset(log_path, max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {log_path.name}")
            print(f"  Deals: {df['deal_id'].nunique()}, Source: {_data_source}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"WARNING: Could not load eval logs: {exc}")

if EVAL_LOG_PATH and df.empty:
    print(f"WARNING: EVAL_LOG_PATH={EVAL_LOG_PATH!r} did not resolve to data.")
    print(f"  CWD: {Path.cwd()}")
    print("  Falling back to synthetic data.")

if df.empty:
    # Synthetic demo data for CI / SMOKE fallback
    rng = np.random.default_rng(SEED)
    n_deals = max_deals or 30
    rows = []
    for deal_id in range(n_deals):
        contract = rng.choice(["suit", "high", "low"])
        trump = rng.choice(["C", "D", "H", "S"]) if contract == "suit" else None
        winning_bid = int(rng.integers(5, 11))
        bidder_seat = int(rng.integers(0, 4))
        bidder_team = 0 if bidder_seat in (0, 2) else 1
        t0 = int(rng.integers(0, 11))
        t1 = 10 - t0
        made = (t0 >= winning_bid) if bidder_team == 0 else (t1 >= winning_bid)
        # C30: compute points_won for synthetic data (C32 semantics)
        pts_t0 = t0 if (bidder_team != 0 or made) else -winning_bid
        pts_t1 = t1 if (bidder_team != 1 or made) else -winning_bid
        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            rows.append(
                {
                    "deal_id": deal_id,
                    "hand_id": deal_id,
                    "seat": seat,
                    "team": team,
                    "contract_type": contract,
                    "trump": trump,
                    "tricks_won": t0 if seat in (0, 2) else t1,
                    "winning_bid": winning_bid,
                    "is_bidder": seat == bidder_seat,
                    "is_declaring_team": team == bidder_team,
                    "made_bid": made,
                    "n_bids": int(rng.integers(1, 4)),
                    "n_passes": int(rng.integers(1, 4)),
                    "auction_rounds": 4,
                    "bidder_seat": bidder_seat,
                    "bidder_team": bidder_team,
                    "points_won": pts_t0 if seat in (0, 2) else pts_t1,
                }
            )
    df = pd.DataFrame(rows)
    _data_source = "synthetic"
    print(f"Using synthetic demo data ({n_deals} deals, {len(df)} rows)")

print(f"MODE={MODE}, data_source={_data_source}")

# Deal-level frame (one row per deal, using seat 0)
deal_df = df[df["seat"] == 0].copy()
print(f"deal_df: {len(deal_df)} deals")

# C22: Run metadata summary
print("\n" + "=" * 60)
print("RUN METADATA")
print("=" * 60)
print(f"  Data source:    {_data_source}")
print(f"  Run directory:  {EVAL_LOG_PATH or 'N/A (synthetic)'}")
print(f"  Total deals:    {df['deal_id'].nunique():,}")
print(f"  Total rows:     {len(df):,} (4 per deal)")
print(f"  Mode:           {MODE}")
print(f"  Seed:           {SEED}")
if "contract_type" in df.columns:
    print(
        f"  Contract types: "
        f"{dict(df.drop_duplicates('deal_id')['contract_type'].value_counts())}"
    )

# %% [markdown]
# # S1 Fail-Fast Validation
#
# Assert-style gates that halt execution on data integrity violations.
# All checks must pass before proceeding to analysis sections.

# %%
_validation_results = []

# Check 1: tricks_won in [0, 10]
tricks_range_ok = df["tricks_won"].between(0, 10).all()
assert tricks_range_ok, (
    f"tricks_won out of range: "
    f"min={df['tricks_won'].min()}, max={df['tricks_won'].max()}"
)
_validation_results.append(
    {
        "check": "tricks_won in [0, 10]",
        "expected": "all True",
        "actual": "all True",
        "status": "PASS",
    }
)

# Check 2: team0 + team1 tricks == 10 per deal
_deal_trick_totals = df.groupby("deal_id").apply(
    lambda g: g[g["team"] == 0]["tricks_won"].iloc[0]
    + g[g["team"] == 1]["tricks_won"].iloc[0]
)
tricks_sum_ok = (_deal_trick_totals == 10).all()
assert tricks_sum_ok, (
    f"Team tricks do not sum to 10 for some deals: "
    f"{_deal_trick_totals[_deal_trick_totals != 10].to_dict()}"
)
_validation_results.append(
    {
        "check": "team0 + team1 tricks == 10",
        "expected": "all 10",
        "actual": "all 10",
        "status": "PASS",
    }
)

# Check 3: no missing contract_type
missing_contract = df["contract_type"].isna().sum()
assert missing_contract == 0, f"Missing contract_type: {missing_contract} rows"
_validation_results.append(
    {
        "check": "no missing contract_type",
        "expected": "0 missing",
        "actual": f"{missing_contract} missing",
        "status": "PASS",
    }
)

# Check 4: no missing tricks_won
missing_tricks = df["tricks_won"].isna().sum()
assert missing_tricks == 0, f"Missing tricks_won: {missing_tricks} rows"
_validation_results.append(
    {
        "check": "no missing tricks_won",
        "expected": "0 missing",
        "actual": f"{missing_tricks} missing",
        "status": "PASS",
    }
)

print("=== Validation Results ===")
print(pd.DataFrame(_validation_results).to_string(index=False))
print("\nAll fail-fast checks passed.")

# %% [markdown]
# # S2 Outcome Distributions by Contract Type
#
# Histograms, violin plots, and summary statistics for `tricks_won`
# faceted by contract type. Includes declaring vs defending split.

# %%
if not df.empty and "tricks_won" in df.columns and "contract_type" in df.columns:
    ctypes = sorted(df["contract_type"].unique())

    # C20: min-N guard
    MIN_DEALS_PER_STRATUM = 30
    deal_counts = df.drop_duplicates(subset=["deal_id"]).groupby("contract_type").size()
    thin_strata = deal_counts[deal_counts < MIN_DEALS_PER_STRATUM]
    if len(thin_strata) > 0:
        import warnings

        warnings.warn(
            f"Thin strata detected (< {MIN_DEALS_PER_STRATUM} deals): "
            f"{thin_strata.to_dict()}. Sub-group charts may be noisy.",
            stacklevel=2,
        )

    # Histogram grid of tricks_won by contract_type
    fig_hist, axes = plt.subplots(
        1, len(ctypes), figsize=(5 * len(ctypes), 4), sharey=True
    )
    if not hasattr(axes, "__len__"):
        axes = [axes]
    for ax, ctype in zip(axes, ctypes):
        grp = df[df["contract_type"] == ctype]
        ax.hist(
            grp["tricks_won"],
            bins=11,
            range=(-0.5, 10.5),
            edgecolor="black",
            alpha=0.7,
        )
        ax.set_title(f"Tricks Won: {ctype} (n={len(grp)})")
        ax.set_xlabel("Tricks Won")
        ax.set_ylabel("Count")
    plt.tight_layout()
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_hist.savefig(out / "tricks_won_histogram.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Violin/box plot using library function
    fig_violin = plot_outcome_distributions(
        df, outcome="tricks_won", group_by="contract_type"
    )
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_violin.savefig(out / "tricks_won_violin.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Per-contract summary table
    print("\n=== Tricks Won Summary by Contract Type ===")
    summary_rows = []
    for ctype in ctypes:
        grp = df[df["contract_type"] == ctype]["tricks_won"]
        summary_rows.append(
            {
                "contract": ctype,
                "N": len(grp),
                "mean": f"{grp.mean():.2f}",
                "std": f"{grp.std():.2f}",
                "P5": f"{grp.quantile(0.05):.1f}",
                "P25": f"{grp.quantile(0.25):.1f}",
                "P50": f"{grp.quantile(0.50):.1f}",
                "P75": f"{grp.quantile(0.75):.1f}",
                "P95": f"{grp.quantile(0.95):.1f}",
            }
        )
    print(pd.DataFrame(summary_rows).to_string(index=False))

    # C23-T2: Declaring vs defending outcome split
    if "is_declaring_team" in df.columns:
        print("\n=== Outcome Split: Declaring vs Defending ===")
        for ct in ctypes:
            subset = df[df["contract_type"] == ct]
            decl_tricks = subset[subset["is_declaring_team"] == True]["tricks_won"]  # noqa: E712
            def_tricks = subset[subset["is_declaring_team"] == False]["tricks_won"]  # noqa: E712
            if len(decl_tricks) > 0 and len(def_tricks) > 0:
                print(
                    f"  {ct}: declaring mean={decl_tricks.mean():.3f}, "
                    f"defending mean={def_tricks.mean():.3f}, "
                    f"delta={decl_tricks.mean() - def_tricks.mean():+.3f}"
                )
else:
    print("No data available for outcome distributions.")

# %% [markdown]
# # S3 Team & Seat Balance
#
# Tests whether teams and seats receive balanced outcomes. Team balance
# uses Mann-Whitney U; seat balance compares per-seat trick means.
# Declaring vs defending split disambiguates structural asymmetry from bias.

# %%
_team_balance_gates = []

if not df.empty and "tricks_won" in df.columns and "team" in df.columns:
    ctypes = sorted(df["contract_type"].unique())

    # Boxplot of tricks_won by team x contract_type
    fig_team, axes = plt.subplots(
        1, len(ctypes), figsize=(5 * len(ctypes), 4), sharey=True
    )
    if not hasattr(axes, "__len__"):
        axes = [axes]
    for ax, ctype in zip(axes, ctypes):
        grp = df[df["contract_type"] == ctype]
        team_data = [grp.loc[grp["team"] == t, "tricks_won"].dropna() for t in [0, 1]]
        ax.boxplot(team_data, labels=["Team 0", "Team 1"])
        means = [d.mean() for d in team_data]
        ax.scatter([1, 2], means, color="red", marker="D", s=50, zorder=5, label="Mean")
        ax.set_title(f"{ctype} (n={len(grp)})")
        ax.set_xlabel("Team")
        ax.set_ylabel("Tricks Won")
        ax.legend(fontsize=8)
    plt.tight_layout()
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_team.savefig(out / "team_balance_boxplot.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Per-contract team delta and significance
    print("\n=== Team Balance by Contract Type ===")
    balance_rows = []
    for ctype in ctypes:
        grp = df[df["contract_type"] == ctype]
        t0 = grp.loc[grp["team"] == 0, "tricks_won"]
        t1 = grp.loc[grp["team"] == 1, "tricks_won"]
        delta = t0.mean() - t1.mean()

        # Mann-Whitney U test (nonparametric — robust for small N)
        p_value = np.nan
        try:
            from scipy.stats import mannwhitneyu

            if len(t0) > 0 and len(t1) > 0:
                _, p_value = mannwhitneyu(t0, t1, alternative="two-sided")
        except ImportError:
            pass

        passed = abs(delta) < 0.25
        _team_balance_gates.append({"contract": ctype, "delta": delta, "pass": passed})
        balance_rows.append(
            {
                "contract": ctype,
                "team0_mean": f"{t0.mean():.3f}",
                "team1_mean": f"{t1.mean():.3f}",
                "delta": f"{delta:+.3f}",
                "p_value": f"{p_value:.4f}" if not np.isnan(p_value) else "N/A",
                "pass (|d|<0.25)": "PASS" if passed else "FAIL",
            }
        )
    print(pd.DataFrame(balance_rows).to_string(index=False))

    # C23-T1: Declaring vs defending means
    if "is_declaring_team" in df.columns:
        print("\n=== Declaring vs Defending Means (per contract type) ===")
        for ct in ctypes:
            subset = df[df["contract_type"] == ct]
            decl = subset[subset["is_declaring_team"] == True]["tricks_won"]  # noqa: E712
            defd = subset[subset["is_declaring_team"] == False]["tricks_won"]  # noqa: E712
            print(
                f"  {ct}: declaring={decl.mean():.3f} (n={len(decl)}), "
                f"defending={defd.mean():.3f} (n={len(defd)})"
            )

        # Bidder team distribution per contract type
        if "bidder_team" in deal_df.columns:
            print("\n=== Bidder Team Distribution (per contract type) ===")
            for ct in ctypes:
                subset = deal_df[deal_df["contract_type"] == ct]
                if "bidder_team" in subset.columns:
                    dist = subset["bidder_team"].value_counts().sort_index()
                    total = len(subset)
                    parts = ", ".join(
                        f"team{t}={n} ({n / total:.1%})" for t, n in dist.items()
                    )
                    print(f"  {ct}: {parts}")

    # C24: Seat balance analysis
    print("\n=== Seat Balance ===")
    seat_means = df.groupby(["contract_type", "seat"])["tricks_won"].mean().unstack()
    print(seat_means.round(3))
else:
    print("No data available for team balance analysis.")

# %% [markdown]
# # S4 Auction Health (Arc D-specific)
#
# Validates auction behavior: contract selection distribution, bid levels,
# and auction length. Includes per-suit bid breakdown for suit contracts.

# %%
if not df.empty:
    # Use the library composite figure (1x3: contract selection, bid dist, auction length)
    fig_auction = plot_auction_health(df)
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_auction.savefig(out / "auction_health.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Auction summary table
    if "contract_type" in deal_df.columns:
        print("\n=== Auction Summary by Contract Type ===")
        auction_rows = []
        for ctype in sorted(deal_df["contract_type"].unique()):
            grp = deal_df[deal_df["contract_type"] == ctype]
            row = {"contract": ctype, "n_deals": len(grp)}
            if "winning_bid" in grp.columns:
                bids = grp["winning_bid"].dropna()
                row["mean_bid"] = f"{bids.mean():.2f}" if len(bids) > 0 else "N/A"
                row["median_bid"] = f"{bids.median():.1f}" if len(bids) > 0 else "N/A"
            if "n_passes" in grp.columns and "auction_rounds" in grp.columns:
                mean_rounds = grp["auction_rounds"].mean()
                mean_passes = grp["n_passes"].mean()
                pass_rate = mean_passes / mean_rounds if mean_rounds > 0 else 0.0
                row["pass_rate"] = f"{pass_rate:.3f}"
                row["mean_rounds"] = f"{mean_rounds:.2f}"
            auction_rows.append(row)
        print(pd.DataFrame(auction_rows).to_string(index=False))

    # C25: Bid distribution by trump suit (suit contracts only)
    suit_deals = deal_df[deal_df["contract_type"] == "suit"]
    if not suit_deals.empty and "trump" in suit_deals.columns:
        fig, ax = plt.subplots(figsize=(10, 5))
        for trump_suit in sorted(suit_deals["trump"].dropna().unique()):
            subset = suit_deals[suit_deals["trump"] == trump_suit]
            ax.hist(
                subset["winning_bid"].dropna(),
                alpha=0.5,
                label=trump_suit,
                bins=range(4, 12),
            )
        ax.set_xlabel("Winning Bid")
        ax.set_ylabel("Count")
        ax.set_title("Bid Distribution by Trump Suit (Suit Contracts)")
        ax.legend()
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig.savefig(
                out / "bid_dist_by_trump_suit.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

    # C25: Bid distribution for high/low contracts
    hl_deals = deal_df[deal_df["contract_type"].isin(["high", "low"])]
    if not hl_deals.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        for ct in sorted(hl_deals["contract_type"].unique()):
            subset = hl_deals[hl_deals["contract_type"] == ct]
            ax.hist(
                subset["winning_bid"].dropna(),
                alpha=0.5,
                label=ct,
                bins=range(4, 12),
            )
        ax.set_xlabel("Winning Bid")
        ax.set_ylabel("Count")
        ax.set_title("Bid Distribution by Contract Type (High/Low)")
        ax.legend()
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig.savefig(out / "bid_dist_high_low.png", dpi=150, bbox_inches="tight")
        plt.show()
else:
    print("No data available for auction health.")

# %% [markdown]
# # S5 Bidder Performance
#
# **Make rate** = fraction of deals where the declaring team won at least
# as many tricks as the winning bid (`tricks_won >= winning_bid`).
# Range [0, 1]; healthy range 0.4-0.8.

# %%
_bidder_perf_gates = []

if not df.empty and "is_bidder" in df.columns:
    # Use the library composite figure (1x3: make rate, make rate curve, overbid)
    fig_bidder = plot_bidder_performance(df)
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_bidder.savefig(out / "bidder_performance.png", dpi=150, bbox_inches="tight")
    plt.show()

    # Per-contract make rate table with 95% binomial CI
    bidder_df = df[df["is_bidder"] == True].copy()  # noqa: E712
    if not bidder_df.empty and "contract_type" in bidder_df.columns:
        print("\n=== Make Rate by Contract Type (with 95% CI) ===")
        mr_rows = []
        for ctype in sorted(bidder_df["contract_type"].unique()):
            grp = bidder_df[bidder_df["contract_type"] == ctype]
            n = len(grp)
            if "made_bid" in grp.columns and n > 0:
                k = int(grp["made_bid"].sum())
                p = k / n

                # Binomial CI
                ci_lo, ci_hi = 0.0, 1.0
                if HAS_SCIPY and n > 0:
                    lo, hi = binom.interval(0.95, n, p)
                    ci_lo = lo / n
                    ci_hi = hi / n

                _bidder_perf_gates.append({"contract": ctype, "make_rate": p, "n": n})
                mr_rows.append(
                    {
                        "contract": ctype,
                        "n": n,
                        "made": k,
                        "make_rate": f"{p:.3f}",
                        "CI_lo": f"{ci_lo:.3f}",
                        "CI_hi": f"{ci_hi:.3f}",
                    }
                )
        print(pd.DataFrame(mr_rows).to_string(index=False))

    # C27: Standalone make rate by bid value chart
    if not bidder_df.empty and "made_bid" in bidder_df.columns:
        make_by_bid = bidder_df.groupby("winning_bid")["made_bid"].agg(
            ["mean", "count"]
        )
        make_by_bid.columns = ["make_rate", "n"]
        make_by_bid = make_by_bid[make_by_bid["n"] >= 3]
        if not make_by_bid.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(
                make_by_bid.index,
                make_by_bid["make_rate"],
                "o-",
                linewidth=2,
                markersize=8,
            )
            # CI bands using binomial approximation
            for bid_val in make_by_bid.index:
                n = make_by_bid.loc[bid_val, "n"]
                p = make_by_bid.loc[bid_val, "make_rate"]
                se = np.sqrt(p * (1 - p) / n) if n > 0 else 0
                ax.fill_between(
                    [bid_val - 0.1, bid_val + 0.1],
                    [p - 1.96 * se] * 2,
                    [p + 1.96 * se] * 2,
                    alpha=0.2,
                    color="blue",
                )
            ax.set_xlabel("Winning Bid")
            ax.set_ylabel("Make Rate")
            ax.set_title("Make Rate by Bid Value (with 95% CI)")
            ax.set_ylim(0, 1.05)
            ax.axhline(y=0.5, color="gray", linestyle="--", alpha=0.5)
            for _, row in make_by_bid.iterrows():
                ax.annotate(
                    f"n={int(row['n'])}",
                    (row.name, row["make_rate"]),
                    textcoords="offset points",
                    xytext=(0, 10),
                    ha="center",
                    fontsize=8,
                )
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig.savefig(out / "make_rate_by_bid.png", dpi=150, bbox_inches="tight")
            plt.show()

    # C28: Overbid/underbid histogram by contract type
    if not bidder_df.empty and "winning_bid" in bidder_df.columns:
        bidder_df["surplus"] = bidder_df["tricks_won"] - bidder_df["winning_bid"]
        ctypes_bidder = sorted(bidder_df["contract_type"].unique())
        fig, axes = plt.subplots(
            1, len(ctypes_bidder), figsize=(6 * len(ctypes_bidder), 4), sharey=True
        )
        if not hasattr(axes, "__len__"):
            axes = [axes]
        for ax, ct in zip(axes, ctypes_bidder):
            subset = bidder_df[bidder_df["contract_type"] == ct]
            ax.hist(
                subset["surplus"].dropna(),
                bins=range(-10, 11),
                color="steelblue",
                alpha=0.7,
                edgecolor="black",
            )
            ax.axvline(0, color="red", linestyle="--", linewidth=1.5)
            ax.set_xlabel("Surplus (tricks - bid)")
            ax.set_ylabel("Count")
            ax.set_title(f"Bid Accuracy: {ct} (n={len(subset)})")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig.savefig(out / "overbid_by_contract.png", dpi=150, bbox_inches="tight")
        plt.show()
else:
    print("No bidder flag available — skipping bidder performance.")

# %% [markdown]
# # S6 Distribution Analysis (CDF/CCDF)
#
# Cumulative distribution functions for tricks and points outcomes,
# faceted by contract type. Includes declaring vs defending splits
# and per-contract summary tables.

# %%
if not df.empty and "tricks_won" in df.columns and "contract_type" in df.columns:
    # C20: min-N guard for S6
    MIN_DEALS_PER_STRATUM_S6 = 30
    deal_counts_s6 = (
        df.drop_duplicates(subset=["deal_id"]).groupby("contract_type").size()
    )
    thin_strata_s6 = deal_counts_s6[deal_counts_s6 < MIN_DEALS_PER_STRATUM_S6]
    if len(thin_strata_s6) > 0:
        import warnings

        warnings.warn(
            f"Thin strata detected (< {MIN_DEALS_PER_STRATUM_S6} deals): "
            f"{thin_strata_s6.to_dict()}. CDF/CCDF curves may show step artifacts.",
            stacklevel=2,
        )

    # CDF by contract type
    fig_cdf = plot_cdf(df, column="tricks_won", group_by="contract_type")
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_cdf.savefig(out / "cdf_by_contract.png", dpi=150, bbox_inches="tight")
    plt.show()

    # CCDF by contract type
    fig_ccdf = plot_ccdf(df, column="tricks_won", group_by="contract_type")
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_ccdf.savefig(out / "ccdf_by_contract.png", dpi=150, bbox_inches="tight")
    plt.show()

    # C29: Tricks distribution summary table
    print("\n=== Tricks Distribution Summary (per contract type) ===")
    for ct in sorted(df["contract_type"].unique()):
        subset = df[df["contract_type"] == ct]
        print(f"\n  {ct} (n={len(subset)}):")
        print(f"    Mean: {subset['tricks_won'].mean():.3f}")
        print(f"    Median: {subset['tricks_won'].median():.1f}")
        print(f"    Std: {subset['tricks_won'].std():.3f}")
        pcts = subset["tricks_won"].value_counts(normalize=True).sort_index()
        for tricks_val, pct in pcts.items():
            print(f"    {int(tricks_val)} tricks: {pct:.1%}")

    # C30: Points analysis (requires points_won column from PR-0)
    if "points_won" in df.columns:
        print("\n=== Points Analysis (Declaring vs Defending) ===")
        for ct in sorted(df["contract_type"].unique()):
            subset = df[df["contract_type"] == ct]
            if "is_declaring_team" in subset.columns:
                decl = subset[subset["is_declaring_team"] == True]  # noqa: E712
                defd = subset[subset["is_declaring_team"] == False]  # noqa: E712
                decl_pts = decl.drop_duplicates(subset=["deal_id", "team"])[
                    "points_won"
                ]
                defd_pts = defd.drop_duplicates(subset=["deal_id", "team"])[
                    "points_won"
                ]
                print(f"\n  {ct}:")
                print(
                    f"    Declaring: mean={decl_pts.mean():.3f}, "
                    f"median={decl_pts.median():.1f}, std={decl_pts.std():.3f}"
                )
                print(
                    f"    Defending: mean={defd_pts.mean():.3f}, "
                    f"median={defd_pts.median():.1f}, std={defd_pts.std():.3f}"
                )

        # Points CDF (declaring team only)
        if "is_declaring_team" in df.columns:
            declaring_df = df[df["is_declaring_team"] == True].drop_duplicates(  # noqa: E712
                subset=["deal_id", "team"]
            )
            if not declaring_df.empty:
                fig_pts_cdf = plot_cdf(
                    declaring_df,
                    column="points_won",
                    group_by="contract_type",
                    title="Points Won CDF (Declaring Team)",
                )
                if CHART_OUTPUT_DIR:
                    out = Path(CHART_OUTPUT_DIR)
                    out.mkdir(parents=True, exist_ok=True)
                    fig_pts_cdf.savefig(
                        out / "points_cdf_declaring.png",
                        dpi=150,
                        bbox_inches="tight",
                    )
                plt.show()

                # Expected points by bid value (declaring team)
                if "winning_bid" in declaring_df.columns:
                    ep_by_bid = declaring_df.groupby("winning_bid")["points_won"].agg(
                        ["mean", "count"]
                    )
                    ep_by_bid.columns = ["expected_points", "n"]
                    ep_by_bid = ep_by_bid[ep_by_bid["n"] >= 3]
                    if not ep_by_bid.empty:
                        fig, ax = plt.subplots(figsize=(10, 5))
                        ax.plot(
                            ep_by_bid.index,
                            ep_by_bid["expected_points"],
                            "o-",
                            linewidth=2,
                            markersize=8,
                        )
                        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
                        ax.set_xlabel("Winning Bid")
                        ax.set_ylabel("Expected Points (Declaring)")
                        ax.set_title("Expected Points by Bid Value (Declaring Team)")
                        for _, row in ep_by_bid.iterrows():
                            ax.annotate(
                                f"n={int(row['n'])}",
                                (row.name, row["expected_points"]),
                                textcoords="offset points",
                                xytext=(0, 10),
                                ha="center",
                                fontsize=8,
                            )
                        plt.tight_layout()
                        if CHART_OUTPUT_DIR:
                            out = Path(CHART_OUTPUT_DIR)
                            out.mkdir(parents=True, exist_ok=True)
                            fig.savefig(
                                out / "expected_points_by_bid.png",
                                dpi=150,
                                bbox_inches="tight",
                            )
                        plt.show()
else:
    print("No data available for CDF/CCDF analysis.")

# %% [markdown]
# # S7 Summary
#
# Aggregated gate results from all sections. PASS = check satisfied,
# FAIL = hard gate violation, FLAG = soft warning for human review.

# %%
# Collect all gate results
_summary_gates = []

# S1: Fail-fast validation (all passed if we got here)
_summary_gates.append(
    {"section": "S1 Fail-Fast", "check": "tricks_won range", "status": "PASS"}
)
_summary_gates.append(
    {"section": "S1 Fail-Fast", "check": "team trick totals", "status": "PASS"}
)
_summary_gates.append(
    {"section": "S1 Fail-Fast", "check": "no missing contract_type", "status": "PASS"}
)
_summary_gates.append(
    {"section": "S1 Fail-Fast", "check": "no missing tricks_won", "status": "PASS"}
)

# S3: Team balance gates
for g in _team_balance_gates:
    status = "PASS" if g["pass"] else "FAIL"
    _summary_gates.append(
        {
            "section": "S3 Team Balance",
            "check": f"|delta| < 0.25 ({g['contract']})",
            "status": status,
        }
    )

# S5: Bidder performance (informational — no hard gate, but flag extremes)
for g in _bidder_perf_gates:
    status = "PASS" if 0.2 <= g["make_rate"] <= 0.95 else "FLAG"
    _summary_gates.append(
        {
            "section": "S5 Bidder Perf",
            "check": f"make_rate sane ({g['contract']})",
            "status": status,
        }
    )

print("=" * 60)
print("  OUTCOME HEALTH SUMMARY")
print("=" * 60)
print()
gate_df = pd.DataFrame(_summary_gates)
print(gate_df.to_string(index=False))

n_pass = (gate_df["status"] == "PASS").sum()
n_fail = (gate_df["status"] == "FAIL").sum()
n_flag = (gate_df["status"] == "FLAG").sum()
print(f"\nTotals: {n_pass} PASS, {n_fail} FAIL, {n_flag} FLAG")

# Key findings
print("\n--- Key Findings ---")
n_deals = df["deal_id"].nunique()
print(f"- {n_deals} deals analyzed ({MODE} mode, source={_data_source})")
if "contract_type" in df.columns:
    ct_counts = df[df["seat"] == 0]["contract_type"].value_counts()
    for ct, count in ct_counts.items():
        print(f"  - {ct}: {count} deals ({count / n_deals:.1%})")

if n_fail > 0:
    print("\n*** FAILURES DETECTED — review flagged sections above ***")
    failed = gate_df[gate_df["status"] == "FAIL"]
    for _, row in failed.iterrows():
        print(f"  - [{row['section']}] {row['check']}")

if n_flag > 0:
    print("\n* FLAGS for human review:")
    flagged = gate_df[gate_df["status"] == "FLAG"]
    for _, row in flagged.iterrows():
        print(f"  - [{row['section']}] {row['check']}")

if n_fail == 0 and n_flag == 0:
    print("\nAll checks passed. No flags for human review.")
