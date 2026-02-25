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
# # R0 Baseline — Eval Verification
#
# **Goal:** Full HITL evaluation of R0 baseline lock with rich analysis
# from JSONL eval logs plus artifact-side metrics and promotion gate.
#
# **Data source:** JSONL eval logs from `EVAL_RUN_DIR` (primary) or
# synthetic demo data (CI fallback when logs are not available).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
EVAL_RUN_DIR = "data/runs/arc_d_eval_r0_42_20260221_180253"  # R0 eval run
ARTIFACT_DIR = "data/artifacts/arc_d/r0"  # R0 artifact directory
RUNG_ID = "r0"  # R0 baseline
CHART_OUTPUT_DIR = ""  # dir for chart PNGs
PROMOTION_DECISION_PATH = "data/artifacts/arc_d/r0/promotion_decision_r0.json"

# %% [markdown]
# # §0 Setup

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
# C1: use Path.glob instead of glob module
for _p in (
    sorted(Path("data/runs").glob("arc_d_eval*")) if Path("data/runs").exists() else []
):
    print(_p)

# %%
import json
import warnings

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import mannwhitneyu, pearsonr

from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.diagnostics.charts import (
    plot_ccdf,
    plot_cdf,
    plot_coefficient_heatmap,
    plot_feature_distributions,
    plot_feature_heatmap_by_suit,
    plot_feature_outcome_correlation,
    plot_hand_value_by_contract,
    plot_hand_value_by_seat,
    plot_hand_value_by_trump_suit,
    plot_outcome_by_trump_suit,
    plot_outcome_distributions,
    plot_rolling_mean,
)

# Diagnostics library imports
from bid_euchre.diagnostics.health_checks import (
    compute_health_scorecard,
    display_scorecard,
)
from bid_euchre.diagnostics.stats import (
    compare_first_last_batch,
    compute_seat_balance,
)
from bid_euchre.reporting.evaluator import load_eval_metrics

matplotlib.use("Agg")

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
# C2: safe fallback for unknown MODE
_max_deals = MODE_DEAL_COUNTS.get(MODE, 30)
if MODE not in MODE_DEAL_COUNTS:
    warnings.warn(f"Unknown MODE={MODE!r}, defaulting to 30 deals", stacklevel=2)
max_deals = _max_deals

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

# C1: use Path.glob instead of glob_mod
if EVAL_RUN_DIR:
    eval_run = Path(EVAL_RUN_DIR)
    log_files = sorted(eval_run.glob("logs/*.jsonl"))
    if log_files:
        # Use the first (typically only) log file
        try:
            df = build_eval_dataset(str(log_files[0]), max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {log_files[0].name}")
            print(f"  Deals: {df['deal_id'].nunique()}, Source: {_data_source}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"WARNING: Could not load eval logs: {exc}")

if EVAL_RUN_DIR and df.empty:
    print(
        f"WARNING: EVAL_RUN_DIR={EVAL_RUN_DIR!r} is set but no data was loaded.\n"
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
        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            tricks = t0 if seat in (0, 2) else t1
            # points_won: declaring gets -bid on set, tricks otherwise
            if team == 0:
                pts = tricks if made else -winning_bid
            else:
                pts = tricks
            rows.append(
                {
                    "deal_id": deal_id,
                    "hand_id": deal_id,
                    "seat": seat,
                    "team": team,
                    "contract_type": contract,
                    "trump": trump,
                    "tricks_won": tricks,
                    "points_won": pts,
                    "feat_hand_value": float(rng.integers(200, 800)),
                    "feat_trump_count": int(rng.integers(0, 7)),
                    "feat_bowers": int(rng.integers(0, 3)),
                    "is_bidder": seat == 0,
                    "is_declaring_team": team == 0,
                    "winning_bid": winning_bid,
                    "made_bid": made,
                    "n_bids": int(rng.integers(1, 4)),
                    "n_passes": int(rng.integers(1, 4)),
                    "auction_rounds": 4,
                }
            )
    df = pd.DataFrame(rows)
    _data_source = "synthetic"
    print(f"Using synthetic demo data ({n_deals} deals, {len(df)} rows)")

print(f"MODE={MODE}, data_source={_data_source}")

# C22: Run metadata summary
print()
print("=" * 60)
print("RUN METADATA")
print("=" * 60)
print(f"  Data source:    {_data_source}")
print(f"  Run directory:  {EVAL_RUN_DIR or 'N/A (synthetic)'}")
print(f"  Total deals:    {df['deal_id'].nunique():,}")
print(f"  Total rows:     {len(df):,} (4 per deal)")
print(f"  Mode:           {MODE}")
print(f"  Seed:           {SEED}")
if "contract_type" in df.columns:
    ct_counts = dict(df.drop_duplicates("deal_id")["contract_type"].value_counts())
    print(f"  Contract types: {ct_counts}")

# --- Health scorecard ---
if not df.empty:
    scorecard = compute_health_scorecard(df)
    print(display_scorecard(scorecard))

# --- Load artifact bundle if available ---
_rung_bundle = None
_arm_metrics = {}
_eval_available = False
_model_artifacts = {}

if ARTIFACT_DIR:
    artifact_dir = Path(ARTIFACT_DIR)
    bundle_path = artifact_dir / f"rung_bundle_{RUNG_ID}.json"
    if bundle_path.exists():
        with open(bundle_path) as f:
            _rung_bundle = json.load(f)

        # Load eval metrics for each arm
        for arm_key in ("olsa", "olsa_full"):
            arm_block = _rung_bundle.get(arm_key, {})
            eval_path = arm_block.get("eval_seed42")
            if eval_path:
                try:
                    _arm_metrics[arm_key] = load_eval_metrics(eval_path)
                except (FileNotFoundError, json.JSONDecodeError):
                    pass

            # Load model artifact for predictions
            model_path = arm_block.get("artifact_path")
            if model_path and Path(model_path).exists():
                with open(model_path) as f:
                    _model_artifacts[arm_key] = json.load(f)

        if _arm_metrics:
            _eval_available = True
            print(f"Loaded eval metrics for arms: {list(_arm_metrics.keys())}")
        print(f"Loaded model artifacts for arms: {list(_model_artifacts.keys())}")
    else:
        print(f"Bundle not found: {bundle_path} — eval sections will skip.")
else:
    print("ARTIFACT_DIR not set — eval-side sections (§8–§10) will skip.")

# Canonical metric aliases (single mapping point for eval sections)
METRIC_ALIASES = {
    "net_expected_points_per_deal": "net_eppd",
    "expected_points_per_deal": "eppd",
    "bid_rate": "bid_rate",
    "make_rate": "make_rate",
    "cvar_5": "cvar_5",
    "downside_variance": "downside_variance",
}

# %% [markdown]
# # §1 Deal Health
#
# Feature distributions and seat balance, faceted by contract type.

# %%
if not df.empty and "seat" in df.columns:
    # Seat balance boxplot using diagnostics library
    fig_seat = plot_hand_value_by_seat(df)
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_seat.savefig(out / "seat_balance_boxplot.png", dpi=150)
    plt.show()

    # Hand value by contract type
    fig_contract = plot_hand_value_by_contract(df)
    plt.show()

    # Feature distribution summary (top features by variance, per contract)
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]

    # Top 5 features by variance for distribution plots
    # C38: strip feat_ prefix — plot_feature_distributions expects unprefixed names
    if numeric_feats:
        top5_by_var = [
            c.removeprefix("feat_")
            for c in df[numeric_feats].var().nlargest(5).index.tolist()
        ]
        fig_feat = plot_feature_distributions(df, features=top5_by_var)
        plt.show()

    if numeric_feats and "contract_type" in df.columns:
        for ctype in sorted(df["contract_type"].unique()):
            grp = df[df["contract_type"] == ctype]
            desc = grp[numeric_feats].describe().T
            top = desc.nlargest(10, "std")
            print(f"\n=== {ctype}: Top 10 features by variance (n={len(grp)}) ===")
            print(top[["mean", "std", "min", "max"]].to_string())

    # Seat balance stats
    if "feat_hand_value" in df.columns:
        sb = compute_seat_balance(df)
        print(
            f"\nSeat balance: max_deviation={sb.max_deviation:.4f}, "
            f"is_balanced={sb.is_balanced}"
        )
else:
    print("No data available for deal health analysis.")

# %% [markdown]
# # §2 Auction Health
#
# Auction health analysis has been extracted to a dedicated notebook.
# See `25_auction_health.py` for bid distributions, seat analysis,
# and auction length diagnostics.

# %% [markdown]
# # §3 Gameplay Health
#
# Tricks won distribution and team balance, faceted by contract type.

# %%
if not df.empty and "tricks_won" in df.columns and "contract_type" in df.columns:
    # Outcome distribution using diagnostics library (faceted by contract_type)
    fig_outcomes = plot_outcome_distributions(
        df,
        outcome="tricks_won",
        group_by="contract_type",
        title="Tricks Won by Contract Type",
    )
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_outcomes.savefig(out / "tricks_won_by_contract.png", dpi=150)
    plt.show()

    # Team balance by contract type with Mann-Whitney U test (C11)
    print("\n=== Team Balance (mean tricks_won) ===")
    if "team" in df.columns:
        team_bal = df.groupby(["contract_type", "team"])["tricks_won"].mean().unstack()
        print(team_bal.to_string())

        for ct in sorted(df["contract_type"].unique()):
            subset = df[df["contract_type"] == ct]
            t0 = subset[subset["team"] == 0]["tricks_won"]
            t1 = subset[subset["team"] == 1]["tricks_won"]
            if len(t0) >= 2 and len(t1) >= 2:
                stat, p_val = mannwhitneyu(t0, t1, alternative="two-sided")
                print(
                    f"  {ct}: team0={t0.mean():.3f}, team1={t1.mean():.3f}, "
                    f"MWU p={p_val:.4f}"
                )

    # C23-T1: declaring vs defending split + stat test
    if "is_declaring_team" in df.columns:
        print("\n=== Declaring vs Defending (per contract type) ===")
        for ct in sorted(df["contract_type"].unique()):
            subset = df[df["contract_type"] == ct]
            decl = subset[subset["is_declaring_team"] == True]["tricks_won"]  # noqa: E712
            defd = subset[subset["is_declaring_team"] == False]["tricks_won"]  # noqa: E712
            if len(decl) >= 2 and len(defd) >= 2:
                stat, p_val = mannwhitneyu(decl, defd, alternative="two-sided")
                print(
                    f"  {ct}: declaring={decl.mean():.3f}, "
                    f"defending={defd.mean():.3f}, MWU p={p_val:.4f}"
                )

    # C41: points_won analysis
    if "points_won" in df.columns:
        print("\n=== Points Won by Contract Type ===")
        for ct in sorted(df["contract_type"].unique()):
            subset = df[df["contract_type"] == ct]
            pts = subset["points_won"]
            print(
                f"  {ct}: mean={pts.mean():.3f}, median={pts.median():.1f}, "
                f"std={pts.std():.3f}"
            )

    # C55: points vs tricks scatter
    if "points_won" in df.columns:
        fig_pts_scatter, ax_pts = plt.subplots(figsize=(8, 6))
        for ct in sorted(df["contract_type"].unique()):
            subset = df[df["contract_type"] == ct].drop_duplicates(
                subset=["deal_id", "team"]
            )
            ax_pts.scatter(
                subset["tricks_won"], subset["points_won"], alpha=0.3, s=8, label=ct
            )
        ax_pts.plot([0, 10], [0, 10], "k--", alpha=0.5, label="y=x")
        ax_pts.set_xlabel("Tricks Won")
        ax_pts.set_ylabel("Points Won")
        ax_pts.set_title("Points vs Tricks (set penalty visible below diagonal)")
        ax_pts.legend()
        plt.tight_layout()
        plt.show()
else:
    print("No data available for gameplay health analysis.")

# %% [markdown]
# # §4 Auction Outcomes
#
# Bid accuracy and make rate analysis have been extracted to
# `25_auction_health.py` §S4–S5.

# %% [markdown]
# # §5 Gameplay Outcomes
#
# Points distribution and tail risk for the declaring team,
# faceted by contract type.

# %%
if not df.empty and "is_declaring_team" in df.columns:
    # One row per deal-team (declaring perspective)
    declaring_df = df[df["is_declaring_team"] == True].drop_duplicates(  # noqa: E712
        subset=["deal_id", "team"]
    )

    if not declaring_df.empty and "contract_type" in declaring_df.columns:
        print("=== Declaring Team Outcomes ===")
        for ctype in sorted(declaring_df["contract_type"].unique()):
            grp = declaring_df[declaring_df["contract_type"] == ctype]
            n = len(grp)
            if n > 0 and "tricks_won" in grp.columns:
                print(f"\n{ctype} (n={n}):")
                print(f"  Mean tricks: {grp['tricks_won'].mean():.2f}")
                print(f"  Std: {grp['tricks_won'].std():.2f}")
                print(f"  5th pctl: {grp['tricks_won'].quantile(0.05):.1f}")
                print(f"  95th pctl: {grp['tricks_won'].quantile(0.95):.1f}")

        # C23-T2: defending team stats for contrast
        defending_df = df[
            df["is_declaring_team"] == False  # noqa: E712
        ].drop_duplicates(subset=["deal_id", "team"])
        if not defending_df.empty:
            print("\n=== Defending Team Outcomes ===")
            for ctype in sorted(defending_df["contract_type"].unique()):
                grp = defending_df[defending_df["contract_type"] == ctype]
                n = len(grp)
                if n > 0 and "tricks_won" in grp.columns:
                    print(f"\n{ctype} (n={n}):")
                    print(f"  Mean tricks: {grp['tricks_won'].mean():.2f}")
                    print(f"  Std: {grp['tricks_won'].std():.2f}")
                    print(f"  5th pctl: {grp['tricks_won'].quantile(0.05):.1f}")
                    print(f"  95th pctl: {grp['tricks_won'].quantile(0.95):.1f}")

        # C47: explicit scope label on CDF/CCDF
        fig_cdf = plot_cdf(
            df,
            column="tricks_won",
            group_by="contract_type",
            title="CDF of Tricks Won (All Seats)",
        )
        plt.show()

        fig_ccdf = plot_ccdf(
            df,
            column="tricks_won",
            group_by="contract_type",
            title="CCDF of Tricks Won (All Seats)",
        )
        plt.show()

        # C44: CDF faceted by team and seat
        fig_team_cdf = plot_cdf(
            df,
            column="tricks_won",
            group_by="team",
            title="CDF Tricks Won by Team",
        )
        plt.show()

        fig_seat_cdf = plot_cdf(
            df,
            column="tricks_won",
            group_by="seat",
            title="CDF Tricks Won by Seat",
        )
        plt.show()

        # C45: percentage table of tricks distribution
        xtab = pd.crosstab(
            declaring_df["contract_type"],
            declaring_df["tricks_won"],
            normalize="index",
        )
        print("\n=== Tricks Distribution (% by contract type, declaring team) ===")
        print(xtab.round(3).to_string())

        # C46: points_won CDF and declaring stats
        if "points_won" in declaring_df.columns:
            print("\n=== Points Won: Declaring Team Summary ===")
            for ct in sorted(declaring_df["contract_type"].unique()):
                pts = declaring_df[declaring_df["contract_type"] == ct]["points_won"]
                if len(pts) > 0:
                    print(
                        f"  {ct}: mean={pts.mean():.3f}, "
                        f"median={pts.median():.1f}, "
                        f"5th={pts.quantile(0.05):.1f}, "
                        f"95th={pts.quantile(0.95):.1f}"
                    )

            fig_pts_cdf = plot_cdf(
                declaring_df,
                column="points_won",
                group_by="contract_type",
                title="Points CDF (Declaring Team)",
            )
            plt.show()
    else:
        print("No declaring team rows — skipping gameplay outcomes.")
else:
    print("No declaring team flag — skipping gameplay outcomes.")

# %% [markdown]
# # §6 Model Specs
#
# Feature selection and coefficient display for each model arm,
# faceted by contract type. Includes statsmodels OLS summary tables
# for statistical inference (coefs, std errors, t-stats, p-values, CIs).

# %%
if _model_artifacts:
    for arm_key, artifact in _model_artifacts.items():
        print(f"\n{'=' * 60}")
        print(f"Model: {arm_key} (type={artifact.get('artifact_type', '?')})")
        print(f"{'=' * 60}")

        payoff = artifact.get("payoff_model", {})
        for contract, model in sorted(payoff.items()):
            fnames = model.get("feature_names", [])
            weights = model.get("weights", [])
            bias = model.get("bias", 0.0)
            print(f"\n  {contract}: {len(fnames)} features, bias={bias:.4f}")

            if fnames and weights:
                # Sort by absolute weight
                pairs = sorted(
                    zip(fnames, weights), key=lambda x: abs(x[1]), reverse=True
                )
                for fname, w in pairs:
                    print(f"    {fname:40s} {w:+.6f}")

    # C34: statsmodels OLS summary tables (refit for display only)
    # Actual bidder uses frozen artifact weights; this is for inference diagnostics
    if not df.empty and "tricks_won" in df.columns:
        for arm_key, artifact in _model_artifacts.items():
            payoff = artifact.get("payoff_model", {})
            for contract, model in sorted(payoff.items()):
                fnames = model.get("feature_names", [])
                if not fnames:
                    continue
                feat_cols_ols = [f"feat_{fn}" for fn in fnames]
                subset = df[df["contract_type"] == contract]
                missing = [c for c in feat_cols_ols if c not in subset.columns]
                if missing or len(subset) < len(fnames) + 2:
                    continue
                X = subset[feat_cols_ols].values.astype(np.float64)
                X_const = sm.add_constant(X)
                y = subset["tricks_won"].values.astype(np.float64)
                try:
                    result = sm.OLS(y, X_const).fit()
                    print(f"\n--- OLS Summary: {arm_key} / {contract} ---")
                    print(result.summary(xname=["const"] + fnames))
                except Exception as exc:
                    print(f"OLS refit failed for {arm_key}/{contract}: {exc}")

    # Coefficient heatmap (keep alongside OLS tables for visual overview)
    primary_arm = (
        "olsa_full"
        if "olsa_full" in _model_artifacts
        else next(iter(_model_artifacts), None)
    )
    if primary_arm:
        artifact = _model_artifacts[primary_arm]
        payoff = artifact.get("payoff_model", {})
        coefs_by_contract = {}
        for contract, model in payoff.items():
            fnames = model.get("feature_names", [])
            weights = model.get("weights", [])
            if fnames and weights:
                coefs_by_contract[contract] = dict(zip(fnames, weights))

        if coefs_by_contract:
            fig_heatmap = plot_coefficient_heatmap(
                coefs_by_contract, title=f"Coefficient Heatmap: {primary_arm}"
            )
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_heatmap.savefig(out / "coefficient_heatmap.png", dpi=150)
            plt.show()
else:
    print("No model artifacts loaded — skipping model specs.")

# %% [markdown]
# # §7 Model Performance
#
# Predicted vs actual tricks, residual distribution, and bootstrap R²/MAE
# by contract type. Uses actual model weights from artifacts.
# Charts faceted by contract type.

# %%
if _model_artifacts and not df.empty and "tricks_won" in df.columns:
    # Use primary arm for performance plots
    primary_arm = (
        "olsa_full" if "olsa_full" in _model_artifacts else next(iter(_model_artifacts))
    )
    artifact = _model_artifacts[primary_arm]
    payoff = artifact.get("payoff_model", {})

    # C35: collect per-contract predictions for faceted plots
    contract_results = {}

    for contract, model in sorted(payoff.items()):
        feature_names = model.get("feature_names", [])
        weights = np.array(model.get("weights", []))
        bias = model.get("bias", 0.0)

        if not feature_names or len(weights) == 0:
            continue

        feat_cols_pred = [f"feat_{fn}" for fn in feature_names]
        subset = df[df["contract_type"] == contract].copy()

        # Check all feature columns exist
        missing = [c for c in feat_cols_pred if c not in subset.columns]
        if missing:
            print(f"[{contract}] Missing features: {missing} — skipping.")
            continue

        if len(subset) == 0:
            continue

        X = subset[feat_cols_pred].values.astype(np.float64)
        y_actual = subset["tricks_won"].values.astype(np.float64)
        y_pred = X @ weights + bias

        contract_results[contract] = {
            "y_actual": y_actual,
            "y_pred": y_pred,
            "residuals": y_actual - y_pred,
            "deal_ids": subset["deal_id"].values,
        }

        # Per-contract metrics
        ss_res = np.sum((y_actual - y_pred) ** 2)
        ss_tot = np.sum((y_actual - y_actual.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mae = np.mean(np.abs(y_actual - y_pred))
        print(f"[{contract}] R²={r2:.4f}, MAE={mae:.4f} (n={len(subset)})")

    if contract_results:
        # C35: faceted pred vs actual scatter
        n_contracts = len(contract_results)
        fig_scatter, axes_scatter = plt.subplots(
            1, n_contracts, figsize=(6 * n_contracts, 5), squeeze=False
        )
        for idx, (ct, res) in enumerate(sorted(contract_results.items())):
            ax = axes_scatter[0, idx]
            ax.scatter(res["y_actual"], res["y_pred"], alpha=0.3, s=5)
            lims = [
                min(res["y_actual"].min(), res["y_pred"].min()),
                max(res["y_actual"].max(), res["y_pred"].max()),
            ]
            ax.plot(lims, lims, "r--", linewidth=1, label="y=x")
            ax.set_xlabel("Actual Tricks Won")
            ax.set_ylabel("Predicted Tricks Won")
            ax.set_title(f"Pred vs Actual: {ct}")
            ax.legend()
        plt.suptitle(f"Model: {primary_arm}", fontsize=12)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_scatter.savefig(out / "pred_vs_actual_scatter.png", dpi=150)
        plt.show()

        # C35: faceted residual distribution
        fig_resid, axes_resid = plt.subplots(
            1, n_contracts, figsize=(6 * n_contracts, 5), squeeze=False
        )
        for idx, (ct, res) in enumerate(sorted(contract_results.items())):
            ax = axes_resid[0, idx]
            ax.hist(res["residuals"], bins=31, edgecolor="black", alpha=0.7)
            ax.axvline(0, color="red", linestyle="--", linewidth=1)
            ax.set_xlabel("Residual (actual - predicted)")
            ax.set_ylabel("Count")
            ax.set_title(f"Residuals: {ct}")
        plt.suptitle(f"Model: {primary_arm}", fontsize=12)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_resid.savefig(out / "residual_distribution.png", dpi=150)
        plt.show()

        # C51: error analysis — top 10 worst mispredictions per contract
        for ct, res in sorted(contract_results.items()):
            abs_resid = np.abs(res["residuals"])
            top_idx = np.argsort(abs_resid)[-10:][::-1]
            print(f"\n=== Top 10 Mispredictions: {ct} ===")
            print(
                f"{'deal_id':>10s} {'predicted':>10s} {'actual':>8s} {'residual':>10s}"
            )
            for i in top_idx:
                print(
                    f"{res['deal_ids'][i]:10d} {res['y_pred'][i]:10.3f} "
                    f"{res['y_actual'][i]:8.1f} {res['residuals'][i]:+10.3f}"
                )

        # Bootstrap R²/MAE with CIs (skip in SMOKE)
        all_y = np.concatenate([r["y_actual"] for r in contract_results.values()])
        all_pred = np.concatenate([r["y_pred"] for r in contract_results.values()])
        if MODE != "SMOKE" and len(all_y) >= 50:
            rng = np.random.default_rng(SEED)
            n_boot = 1_000
            boot_r2, boot_mae = [], []
            for _ in range(n_boot):
                idx = rng.integers(0, len(all_y), size=len(all_y))
                y_b, p_b = all_y[idx], all_pred[idx]
                ss_res_b = np.sum((y_b - p_b) ** 2)
                ss_tot_b = np.sum((y_b - y_b.mean()) ** 2)
                boot_r2.append(
                    1 - ss_res_b / ss_tot_b if ss_tot_b > 0 else float("nan")
                )
                boot_mae.append(np.mean(np.abs(y_b - p_b)))

            r2_ci = np.nanpercentile(boot_r2, [2.5, 97.5])
            mae_ci = np.nanpercentile(boot_mae, [2.5, 97.5])
            overall_r2 = 1 - np.sum((all_y - all_pred) ** 2) / np.sum(
                (all_y - all_y.mean()) ** 2
            )
            overall_mae = np.mean(np.abs(all_y - all_pred))
            print(f"\nOverall R²={overall_r2:.4f} [{r2_ci[0]:.4f}, {r2_ci[1]:.4f}]")
            print(f"Overall MAE={overall_mae:.4f} [{mae_ci[0]:.4f}, {mae_ci[1]:.4f}]")
    else:
        print("No predictions generated — check feature columns.")
else:
    if not _model_artifacts:
        # Fallback: placeholder charts for template contract
        fig_scatter, ax_scatter = plt.subplots(figsize=(6, 5))
        ax_scatter.text(0.5, 0.5, "No model artifacts", ha="center", va="center")
        ax_scatter.set_title("pred vs actual (no model)")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_scatter.savefig(out / "pred_vs_actual_scatter.png", dpi=150)
        plt.show()

        fig_resid, ax_resid = plt.subplots(figsize=(6, 5))
        ax_resid.text(0.5, 0.5, "No model artifacts", ha="center", va="center")
        ax_resid.set_title("Residual distribution (no model)")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_resid.savefig(out / "residual_distribution.png", dpi=150)
        plt.show()
    print("No model artifacts or data — skipping model performance.")

# %% [markdown]
# # §7.5 Feature-Outcome Correlations
#
# Top features by absolute Pearson correlation with `tricks_won`,
# per contract type. Includes p-values and declaring/defending split.

# %%
feat_cols = [c for c in df.columns if c.startswith("feat_")]
numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]
if not df.empty and "tricks_won" in df.columns and numeric_feats:
    # C38: strip feat_ prefix — plot_feature_outcome_correlation expects unprefixed
    unprefixed_feats = [c.removeprefix("feat_") for c in numeric_feats]

    fig_corr = plot_feature_outcome_correlation(
        df,
        outcome="tricks_won",
        features=unprefixed_feats,
        title="Feature-Outcome Correlations (tricks_won)",
    )
    plt.show()

    # C15: per-contract correlation table with p-values
    if "contract_type" in df.columns:
        for ctype in sorted(df["contract_type"].unique()):
            grp = df[df["contract_type"] == ctype]
            if len(grp) < 10:
                continue
            corrs = {}
            for fc in numeric_feats:
                try:
                    valid = grp[[fc, "tricks_won"]].dropna()
                    if len(valid) >= 3:
                        r, p = pearsonr(valid[fc], valid["tricks_won"])
                        corrs[fc] = (r, p)
                except Exception:
                    pass
            if corrs:
                # Filter NaN before sorting
                valid_corrs = {k: v for k, v in corrs.items() if not np.isnan(v[0])}
                top10 = sorted(
                    valid_corrs.items(), key=lambda x: abs(x[1][0]), reverse=True
                )[:10]
                print(f"\n=== {ctype}: Top 10 features by |r| with tricks_won ===")
                for fname, (r, p) in top10:
                    print(f"  {fname.replace('feat_', ''):30s} r={r:+.4f}  p={p:.4f}")

    # C23-T2: split correlations by declaring/defending
    if "is_declaring_team" in df.columns and "contract_type" in df.columns:
        for role_flag, role_label in [(True, "declaring"), (False, "defending")]:
            role_df = df[df["is_declaring_team"] == role_flag]
            if len(role_df) < 10:
                continue
            print(f"\n--- Feature-Outcome Correlations ({role_label}) ---")
            for ctype in sorted(role_df["contract_type"].unique()):
                grp = role_df[role_df["contract_type"] == ctype]
                if len(grp) < 10:
                    continue
                corrs = {}
                for fc in numeric_feats:
                    try:
                        valid = grp[[fc, "tricks_won"]].dropna()
                        if len(valid) >= 3:
                            r, _ = pearsonr(valid[fc], valid["tricks_won"])
                            if not np.isnan(r):
                                corrs[fc] = r
                    except Exception:
                        pass
                if corrs:
                    top5 = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[
                        :5
                    ]
                    print(f"  {ctype} ({role_label}, n={len(grp)}):")
                    for fname, r in top5:
                        print(f"    {fname.replace('feat_', ''):30s} r={r:+.4f}")
else:
    print(
        f"Insufficient data for feature-outcome correlations "
        f"(feat_cols={len(feat_cols)}, numeric={len(numeric_feats)})."
    )

# %% [markdown]
# # §7.6 Trump Suit Invariance
#
# For suit contracts: hand_value and tricks_won by trump suit.
# Feature heatmap for detecting suit-specific patterns.

# %%
if not df.empty and "trump" in df.columns and "contract_type" in df.columns:
    suit_df = df[df["contract_type"] == "suit"].copy()
    if not suit_df.empty and suit_df["trump"].notna().any():
        # Hand value by trump suit
        fig_trump_hv = plot_hand_value_by_trump_suit(
            suit_df,
            title="Hand Value by Trump Suit (suit contracts)",
        )
        plt.show()

        # Outcome by trump suit
        fig_trump_out = plot_outcome_by_trump_suit(
            suit_df,
            outcome="tricks_won",
            title="Tricks Won by Trump Suit (suit contracts)",
        )
        plt.show()

        # Feature heatmap by suit
        # C59: strip feat_ prefix — plot_feature_heatmap_by_suit expects unprefixed
        feat_cols_suit = [c for c in suit_df.columns if c.startswith("feat_")]
        if len(feat_cols_suit) > 2:
            unprefixed_suit = [c.removeprefix("feat_") for c in feat_cols_suit[:10]]
            fig_heatmap_suit = plot_feature_heatmap_by_suit(
                suit_df,
                features=unprefixed_suit,
                title="Feature Means by Trump Suit",
            )
            plt.show()
    else:
        print("No suit contract data with trump info — skipping trump invariance.")
else:
    print("No trump suit data available — skipping trump invariance.")

# %% [markdown]
# # §7.7 Drift Detection
#
# Rolling mean of feat_hand_value by deal order. Mann-Whitney U test
# comparing first 10% vs last 10% of deals to detect temporal drift.

# %%
if not df.empty and "feat_hand_value" in df.columns and len(df) >= 40:
    # Rolling mean plot
    fig_drift = plot_rolling_mean(
        df,
        column="feat_hand_value",
        window=max(10, len(df) // 50),
        title="Rolling Mean: feat_hand_value (drift check)",
    )
    plt.show()

    # First vs last batch comparison
    batch_result = compare_first_last_batch(df, column="feat_hand_value")
    if batch_result.mannwhitney_pvalue is not None:
        print(
            f"Drift detection: statistic={batch_result.mannwhitney_stat:.4f}, "
            f"p_value={batch_result.mannwhitney_pvalue:.4f}"
        )
        if batch_result.mannwhitney_pvalue < 0.05:
            print("WARNING: Significant drift detected (p < 0.05).")
        else:
            print("No significant drift detected.")
    else:
        print("Drift detection: Mann-Whitney test not computed (insufficient data).")

    # C58: rolling net_eppd drift (points_won)
    if "points_won" in df.columns and "is_declaring_team" in df.columns:
        declaring_drift = (
            df[df["is_declaring_team"] == True]  # noqa: E712
            .drop_duplicates(subset=["deal_id", "team"])
            .sort_values("deal_id")
        )
        if len(declaring_drift) >= 20:
            window = max(20, len(declaring_drift) // 10)
            declaring_drift = declaring_drift.copy()
            declaring_drift["rolling_points"] = (
                declaring_drift["points_won"]
                .rolling(window, min_periods=window // 2)
                .mean()
            )
            fig_drift_pts, ax_drift_pts = plt.subplots(figsize=(12, 4))
            ax_drift_pts.plot(
                declaring_drift["deal_id"],
                declaring_drift["rolling_points"],
                linewidth=1,
            )
            ax_drift_pts.set_xlabel("Deal ID")
            ax_drift_pts.set_ylabel(f"Rolling Mean Points (window={window})")
            ax_drift_pts.set_title("Rolling Net Points Drift (Declaring Team)")
            ax_drift_pts.axhline(
                declaring_drift["points_won"].mean(),
                color="red",
                linestyle="--",
                alpha=0.5,
            )
            plt.tight_layout()
            plt.show()
else:
    print("Insufficient data for drift detection.")

# %% [markdown]
# # §8 Dual-Arm Comparison
#
# Side-by-side OLSa vs OLSa_Full metrics from eval JSON artifacts.
#
# **Metric Glossary:**
#
# | Metric | Definition | Source |
# |--------|-----------|--------|
# | **net_eppd** | Net expected points per deal (declaring + defending). Primary optimization target. | Simulation eval |
# | **eppd** | Expected points per deal (declaring only). Measures bidder aggressiveness payoff. | Simulation eval |
# | **bid_rate** | Fraction of deals where this bidder wins the auction. | Simulation eval |
# | **make_rate** | Fraction of bid deals where declaring team makes the contract. | Simulation eval |
# | **cvar_5** | Conditional Value at Risk at 5th percentile. Worst-case tail risk for points. | Simulation eval |
# | **downside_variance** | Variance of negative point outcomes. Measures set penalty risk. | Simulation eval |
#
# All metrics come from simulation evaluation (JSONL logs), not from
# regression fit diagnostics. The regression R²/MAE in §7 measure
# prediction quality; these metrics measure bidding strategy quality.

# %%
if _eval_available and len(_arm_metrics) == 2:
    # Summary table
    rows = []
    for arm_key, metrics in _arm_metrics.items():
        row = {"arm": arm_key}
        for canonical, alias in METRIC_ALIASES.items():
            row[alias] = metrics.get(canonical)
        rows.append(row)
    df_eval = pd.DataFrame(rows).set_index("arm")
    print(df_eval.to_string())

    # Bar chart comparison
    rate_keys = ["bid_rate", "make_rate"]
    point_keys = ["net_eppd", "eppd", "cvar_5", "downside_variance"]
    arms = list(_arm_metrics.keys())

    fig, (ax_rates, ax_points) = plt.subplots(1, 2, figsize=(14, 5))
    width = 0.35

    # Left: rate metrics [0, 1]
    x_r = np.arange(len(rate_keys))
    for i, arm in enumerate(arms):
        vals = []
        for rk in rate_keys:
            canonical = next((c for c, a in METRIC_ALIASES.items() if a == rk), rk)
            v = _arm_metrics[arm].get(canonical, 0)
            vals.append(v if v is not None else 0)
        bars = ax_rates.bar(x_r + i * width, vals, width, label=arm)
        for bar, v in zip(bars, vals):
            ax_rates.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{v:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax_rates.set_xticks(x_r + width / 2)
    ax_rates.set_xticklabels(rate_keys)
    ax_rates.set_title("Rate Metrics")
    ax_rates.legend()

    # Right: point metrics (natural scale)
    x_p = np.arange(len(point_keys))
    for i, arm in enumerate(arms):
        vals = []
        for pk in point_keys:
            canonical = next((c for c, a in METRIC_ALIASES.items() if a == pk), pk)
            v = _arm_metrics[arm].get(canonical, 0)
            vals.append(v if v is not None else 0)
        bars = ax_points.bar(x_p + i * width, vals, width, label=arm)
        for bar, v in zip(bars, vals):
            ax_points.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{v:.3f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax_points.set_xticks(x_p + width / 2)
    ax_points.set_xticklabels(point_keys)
    ax_points.set_title("Point Metrics")
    ax_points.legend()

    plt.tight_layout()
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / "dual_arm_comparison.png", dpi=150)
    plt.show()

    # C52: contract selection comparison
    if not df.empty and "contract_type" in df.columns:
        print("\n=== Contract Selection Frequency (from eval data) ===")
        deal_level = df.drop_duplicates(subset=["deal_id"])
        ct_freq = deal_level["contract_type"].value_counts(normalize=True)
        print(ct_freq.round(3).to_string())
        print(
            "\n(Note: both arms evaluated on the same deals; "
            "contract selection comparison requires per-arm eval runs.)"
        )
elif not _eval_available:
    print("Eval metrics not available — skipping dual-arm comparison.")
else:
    print("Need both arms for dual-arm comparison — skipping.")

# %% [markdown]
# # §9 Seed Sensitivity
#
# Multi-seed stability analysis. Warns if CV >= 10%.

# %%
if _eval_available and _rung_bundle is not None:
    seed_rows = []
    for arm_key in ("olsa", "olsa_full"):
        arm_block = _rung_bundle.get(arm_key, {})
        seed_vals = {}
        for seed_key in ("eval_seed42", "eval_seed43", "eval_seed44"):
            path = arm_block.get(seed_key)
            if path:
                try:
                    m = load_eval_metrics(path)
                    seed_vals[seed_key] = m.get("net_expected_points_per_deal")
                except (FileNotFoundError, json.JSONDecodeError):
                    seed_vals[seed_key] = None
            else:
                seed_vals[seed_key] = None

        vals = [v for v in seed_vals.values() if v is not None]
        val_range = max(vals) - min(vals) if len(vals) >= 2 else None
        mean_val = np.mean(vals) if vals else None
        cv_pct = (
            (np.std(vals) / abs(mean_val) * 100)
            if (
                vals
                and len(vals) >= 2
                and mean_val is not None
                and abs(mean_val) > 1e-9
            )
            else None
        )

        seed_rows.append(
            {
                "arm": arm_key,
                "seed42": seed_vals.get("eval_seed42"),
                "seed43": seed_vals.get("eval_seed43"),
                "seed44": seed_vals.get("eval_seed44"),
                "range": val_range,
                "CV(%)": round(cv_pct, 2) if cv_pct is not None else None,
            }
        )

    df_seeds = pd.DataFrame(seed_rows).set_index("arm")
    print(df_seeds.to_string())

    for _, row in df_seeds.iterrows():
        if row.get("CV(%)") is not None and row["CV(%)"] >= 10.0:
            print(
                f"\n**WARNING:** {row.name} has CV={row['CV(%)']:.1f}% >= 10% "
                "— high seed sensitivity detected."
            )
else:
    print("Eval metrics not available — skipping seed sensitivity.")

# %% [markdown]
# # §10 Promotion Summary
#
# Gate outcome, attribution gap, and final decision.

# %%
# Attribution gap
if _eval_available:
    _attr_gap = None
    _attr_source = None

    if PROMOTION_DECISION_PATH and Path(PROMOTION_DECISION_PATH).exists():
        with open(PROMOTION_DECISION_PATH) as f:
            decision = json.load(f)
        _attr_gap = decision.get("attribution_gap")
        _attr_source = "promotion_decision"
    else:
        full_net = _arm_metrics.get("olsa_full", {}).get("net_expected_points_per_deal")
        base_net = _arm_metrics.get("olsa", {}).get("net_expected_points_per_deal")
        if full_net is not None and base_net is not None:
            _attr_gap = round(full_net - base_net, 6)
            _attr_source = "computed"

    if _attr_gap is not None:
        sign = (
            "positive (Full > Base)"
            if _attr_gap > 0
            else ("negative (Base > Full)" if _attr_gap < 0 else "zero")
        )
        print(f"Attribution gap: {_attr_gap:.6f} ({sign})")
        print(f"Source: {_attr_source}")
    else:
        print("Attribution gap: unavailable (need both arms' net_eppd).")

# Promotion decision
if PROMOTION_DECISION_PATH and Path(PROMOTION_DECISION_PATH).exists():
    with open(PROMOTION_DECISION_PATH) as f:
        _decision_data = json.load(f)

    print(f"\nDecision: {_decision_data.get('decision', 'UNKNOWN')}")
    print(f"Rung: {_decision_data.get('rung_id', '?')}")
    print(f"Arc: {_decision_data.get('arc', '?')}")

    tier1 = _decision_data.get("tier_1_checks", {})
    if tier1:
        print("\nTier 1 Checks:")
        df_tier1 = pd.DataFrame([{"check": k, "status": v} for k, v in tier1.items()])
        print(df_tier1.to_string(index=False))

    gate_results = _decision_data.get("gate_results", {})
    if gate_results:
        print("\nGate Results:")
        for key, val in gate_results.items():
            if isinstance(val, dict):
                print(f"  {key}: pass={val.get('pass')} — {val.get('note', '')}")
            else:
                print(f"  {key}: {val}")

    ag = _decision_data.get("attribution_gap")
    if ag is not None:
        print(f"\nAttribution gap (from decision): {ag:.6f}")
elif PROMOTION_DECISION_PATH:
    print(f"Promotion decision file not found: {PROMOTION_DECISION_PATH}")
elif not _eval_available:
    print("No eval metrics or promotion decision — skipping promotion summary.")
else:
    print("PROMOTION_DECISION_PATH not set — skipping promotion gate detail.")

# %%
# C53: win rate by bid value
if not df.empty and "is_declaring_team" in df.columns and "winning_bid" in df.columns:
    decl_bidder = df[
        (df["is_declaring_team"] == True) & (df["is_bidder"] == True)  # noqa: E712
    ]
    if not decl_bidder.empty and "made_bid" in decl_bidder.columns:
        wr_by_bid = decl_bidder.groupby("winning_bid").agg(
            make_rate=("made_bid", "mean"),
            mean_tricks=("tricks_won", "mean"),
            n=("made_bid", "count"),
        )
        wr_by_bid["mean_surplus"] = decl_bidder.groupby("winning_bid").apply(
            lambda g: (g["tricks_won"] - g["winning_bid"]).mean(),
            include_groups=False,
        )
        print("\n=== Win Rate by Bid Value (Declaring Bidder) ===")
        print(wr_by_bid.round(3).to_string())

        fig_wr, ax_wr = plt.subplots(figsize=(8, 5))
        ax_wr.bar(
            wr_by_bid.index.astype(str),
            wr_by_bid["make_rate"],
            color="#2196F3",
            edgecolor="black",
        )
        ax_wr.set_xlabel("Bid Value")
        ax_wr.set_ylabel("Make Rate")
        ax_wr.set_title("Make Rate by Bid Value (Declaring Bidder)")
        for i, (bid, row) in enumerate(wr_by_bid.iterrows()):
            ax_wr.text(
                i,
                row["make_rate"],
                f"n={row['n']:.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        plt.tight_layout()
        plt.show()

# %%
# C54: confusion matrix — bid x actual tricks
if not df.empty and "is_bidder" in df.columns:
    bidder_df_cm = df[df["is_bidder"] == True]  # noqa: E712
    if (
        not bidder_df_cm.empty
        and "winning_bid" in bidder_df_cm.columns
        and "tricks_won" in bidder_df_cm.columns
    ):
        confusion = pd.crosstab(bidder_df_cm["winning_bid"], bidder_df_cm["tricks_won"])
        fig_cm, ax_cm = plt.subplots(figsize=(10, 6))
        im = ax_cm.imshow(confusion.values, cmap="YlOrRd", aspect="auto")
        ax_cm.set_xticks(range(confusion.shape[1]))
        ax_cm.set_xticklabels(confusion.columns)
        ax_cm.set_yticks(range(confusion.shape[0]))
        ax_cm.set_yticklabels(confusion.index)
        ax_cm.set_xlabel("Actual Tricks Won")
        ax_cm.set_ylabel("Winning Bid")
        ax_cm.set_title("Bid x Actual Tricks Confusion Matrix")
        plt.colorbar(im, ax=ax_cm)
        for i in range(confusion.shape[0]):
            for j in range(confusion.shape[1]):
                ax_cm.text(
                    j,
                    i,
                    str(confusion.values[i, j]),
                    ha="center",
                    va="center",
                    fontsize=8,
                )
        plt.tight_layout()
        plt.show()

# %% [markdown]
# # §11 Comparator Battery
#
# Ranked net_eppd comparison across heuristic bidders.
# Data source: comparator_battery key in rung bundle or
# comparator_battery_r0.json alongside the bundle.

# %%
_comparator_data = None
if _rung_bundle is not None:
    _cb_raw = _rung_bundle.get("comparator_battery")
    if isinstance(_cb_raw, str):
        # Bundle stores a path string — resolve and load
        _cb_file = (
            Path(ARTIFACT_DIR) / Path(_cb_raw).name if ARTIFACT_DIR else Path(_cb_raw)
        )
        if not _cb_file.exists():
            _cb_file = Path(_cb_raw)
        if _cb_file.exists():
            with open(_cb_file) as f:
                _comparator_data = json.load(f)
    elif isinstance(_cb_raw, dict):
        _comparator_data = _cb_raw

# Also try loading standalone comparator battery JSON
if _comparator_data is None and ARTIFACT_DIR:
    cb_path = Path(ARTIFACT_DIR) / f"comparator_battery_{RUNG_ID}.json"
    if cb_path.exists():
        with open(cb_path) as f:
            _comparator_data = json.load(f)

# Drill into "bidders" key if present (comparator battery JSON schema)
if isinstance(_comparator_data, dict) and "bidders" in _comparator_data:
    _comparator_data = _comparator_data["bidders"]

if _comparator_data and isinstance(_comparator_data, dict):
    # C48: build full metrics table (all 6 metrics, not just net_eppd)
    all_comp_metrics = []
    for bidder_name, metrics in _comparator_data.items():
        if isinstance(metrics, dict):
            all_comp_metrics.append(
                {
                    "bidder": bidder_name,
                    "net_eppd": metrics.get("net_eppd"),
                    "eppd": metrics.get("eppd"),
                    "bid_rate": metrics.get("bid_rate"),
                    "make_rate": metrics.get("make_rate"),
                    "cvar_5": metrics.get("cvar_5"),
                    "net_cvar_5": metrics.get("net_cvar_5"),
                }
            )

    if all_comp_metrics:
        df_comp = pd.DataFrame(all_comp_metrics).sort_values(
            "net_eppd", ascending=False
        )
        print("=== Comparator Battery: Full Metrics ===")
        print(df_comp.to_string(index=False))

        # Horizontal bar chart: net_eppd ranking (kept for quick overview)
        fig_comp, ax_comp = plt.subplots(
            figsize=(10, max(3, len(all_comp_metrics) * 0.5))
        )
        colors = [
            "#2196F3"
            if "hybrid" in r["bidder"].lower() or "olsa" in r["bidder"].lower()
            else "#9E9E9E"
            for r in df_comp.to_dict("records")
        ]
        ax_comp.barh(df_comp["bidder"], df_comp["net_eppd"], color=colors)
        ax_comp.set_xlabel("net_eppd")
        ax_comp.set_title("Comparator Battery: net_eppd Ranking")
        ax_comp.invert_yaxis()
        plt.tight_layout()
        plt.show()

        # C48: grouped-bar chart — rate metrics + point metrics
        comp_bidders = df_comp["bidder"].tolist()
        n_bidders = len(comp_bidders)
        rate_keys_comp = ["bid_rate", "make_rate"]
        point_keys_comp = ["net_eppd", "eppd", "cvar_5"]

        fig_comp2, (ax_cr, ax_cp) = plt.subplots(
            1, 2, figsize=(16, max(5, n_bidders * 0.4))
        )

        # Left panel: rate metrics
        x_b = np.arange(n_bidders)
        bar_width = 0.35
        for i, metric in enumerate(rate_keys_comp):
            vals = df_comp[metric].fillna(0).values
            ax_cr.barh(x_b + i * bar_width, vals, bar_width, label=metric)
        ax_cr.set_yticks(x_b + bar_width / 2)
        ax_cr.set_yticklabels(comp_bidders)
        ax_cr.set_xlabel("Value")
        ax_cr.set_title("Rate Metrics by Bidder")
        ax_cr.legend()
        ax_cr.invert_yaxis()

        # Right panel: point metrics
        bar_w = 0.25
        for i, metric in enumerate(point_keys_comp):
            vals = df_comp[metric].fillna(0).values
            ax_cp.barh(x_b + i * bar_w, vals, bar_w, label=metric)
        ax_cp.set_yticks(x_b + bar_w)
        ax_cp.set_yticklabels(comp_bidders)
        ax_cp.set_xlabel("Value")
        ax_cp.set_title("Point Metrics by Bidder")
        ax_cp.legend()
        ax_cp.invert_yaxis()

        plt.tight_layout()
        plt.show()
    else:
        print("Comparator battery data found but no metric values.")
else:
    print("No comparator battery data available — skipping.")
