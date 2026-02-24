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
# **Goal:** Validate outcome distributions, team balance, auction health,
# and bidder performance from an Arc D eval JSONL log.
#
# **Data source:** JSONL eval logs (primary) or synthetic demo data (CI fallback).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
# - Parameterize via papermill — do not hardcode paths.

# %% tags=["parameters"]
EVAL_LOG_PATH = ""  # path to JSONL eval log
MODE = "SMOKE"  # SMOKE | QUICK | FULL
RUNG_ID = ""  # e.g., "r0"
CHART_OUTPUT_DIR = ""  # dir for chart PNGs

# %% [markdown]
# # S0 Configuration & Data Loading

# %%
import glob as glob_mod
from pathlib import Path

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

SEED = 42
MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
max_deals = MODE_DEAL_COUNTS.get(MODE, 30)

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

if EVAL_LOG_PATH:
    log_path = Path(EVAL_LOG_PATH)
    if log_path.is_dir():
        # Directory: look for JSONL files inside logs/
        log_files = sorted(glob_mod.glob(str(log_path / "logs" / "*.jsonl")))
        if log_files:
            log_path = Path(log_files[0])
    if log_path.is_file():
        try:
            df = build_eval_dataset(log_path, max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {log_path.name}")
            print(f"  Deals: {df['deal_id'].nunique()}, Source: {_data_source}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"WARNING: Could not load eval logs: {exc}")

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
                }
            )
    df = pd.DataFrame(rows)
    _data_source = "synthetic"
    print(f"Using synthetic demo data ({n_deals} deals, {len(df)} rows)")

print(f"MODE={MODE}, data_source={_data_source}")

# Deal-level frame (one row per deal, using seat 0)
deal_df = df[df["seat"] == 0].copy()
print(f"deal_df: {len(deal_df)} deals")

# Dataset summary
print("\n=== Dataset Summary ===")
print(f"  Total rows: {len(df)}")
print(f"  Deals: {df['deal_id'].nunique()}")
print(f"  Seats: {sorted(df['seat'].unique())}")
if "contract_type" in df.columns:
    print(f"  Contracts: {dict(df['contract_type'].value_counts())}")

# %% [markdown]
# # S1 Fail-Fast Validation

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

# %%
if not df.empty and "tricks_won" in df.columns and "contract_type" in df.columns:
    ctypes = sorted(df["contract_type"].unique())

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
else:
    print("No data available for outcome distributions.")

# %% [markdown]
# # S3 Team & Seat Balance

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
else:
    print("No data available for team balance analysis.")

# %% [markdown]
# # S4 Auction Health (Arc D-specific)

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
else:
    print("No data available for auction health.")

# %% [markdown]
# # S5 Bidder Performance

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
    else:
        print("No bidder rows found.")
else:
    print("No bidder flag available — skipping bidder performance.")

# %% [markdown]
# # S6 Distribution Analysis (CDF/CCDF)

# %%
if not df.empty and "tricks_won" in df.columns and "contract_type" in df.columns:
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
else:
    print("No data available for CDF/CCDF analysis.")

# %% [markdown]
# # S7 Summary

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
