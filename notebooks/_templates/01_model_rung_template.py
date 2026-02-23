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
# # Model Rung Evaluation Template
#
# **Goal:** Rich HITL evaluation of a model rung — deal/auction/gameplay
# health, model specifications, performance metrics, dual-arm comparison,
# and promotion gate outcome.
#
# **Data source:** JSONL eval logs (primary) or synthetic demo data (CI fallback).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
# - Parameterize via papermill — do not hardcode paths.

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
EVAL_RUN_DIR = ""  # path to eval run dir (contains logs/*.jsonl)
ARTIFACT_DIR = ""  # data/artifacts/arc_d/r{N}/ for model artifacts + bundle
RUNG_ID = ""  # rung identifier, e.g. "r0"
CHART_OUTPUT_DIR = ""  # dir for chart PNGs
PROMOTION_DECISION_PATH = ""  # path to promotion_decision_r{N}.json (optional)

# %% [markdown]
# # §0 Setup

# %%
import glob as glob_mod
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.reporting.evaluator import load_eval_metrics

matplotlib.use("Agg")

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
max_deals = MODE_DEAL_COUNTS.get(MODE)

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

if EVAL_RUN_DIR:
    eval_run = Path(EVAL_RUN_DIR)
    log_files = sorted(glob_mod.glob(str(eval_run / "logs" / "*.jsonl")))
    if log_files:
        # Use the first (typically only) log file
        try:
            df = build_eval_dataset(log_files[0], max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {Path(log_files[0]).name}")
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
        t0 = rng.integers(0, 11)
        t1 = 10 - t0
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
                    "feat_hand_value": float(rng.integers(200, 800)),
                    "feat_trump_count": int(rng.integers(0, 7)),
                    "feat_bowers": int(rng.integers(0, 3)),
                    "is_bidder": seat == 0,
                    "is_declaring_team": team == 0,
                    "winning_bid": int(rng.integers(5, 11)),
                    "made_bid": bool(rng.random() > 0.3),
                    "n_bids": int(rng.integers(1, 4)),
                    "n_passes": int(rng.integers(1, 4)),
                    "auction_rounds": 4,
                }
            )
    df = pd.DataFrame(rows)
    _data_source = "synthetic"
    print(f"Using synthetic demo data ({n_deals} deals, {len(df)} rows)")

print(f"MODE={MODE}, data_source={_data_source}")

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
    # Seat balance boxplot (hand_value, faceted by contract_type)
    balance_col = "feat_hand_value" if "feat_hand_value" in df.columns else "tricks_won"
    if "contract_type" in df.columns:
        ctypes = sorted(df["contract_type"].unique())
        fig, axes = plt.subplots(
            1, len(ctypes), figsize=(5 * len(ctypes), 4), sharey=True
        )
        if not hasattr(axes, "__len__"):
            axes = [axes]
        for ax, ctype in zip(axes, ctypes):
            grp = df[df["contract_type"] == ctype]
            seat_data = [
                grp.loc[grp["seat"] == s, balance_col].dropna() for s in range(4)
            ]
            ax.boxplot(seat_data, labels=[0, 1, 2, 3])
            ax.set_title(f"Seat balance: {ctype}")
            ax.set_xlabel("Seat")
            ax.set_ylabel(balance_col.replace("feat_", ""))
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig.savefig(out / "seat_balance_boxplot.png", dpi=150)
        plt.show()
    else:
        print("No contract_type column — skipping seat balance boxplot.")

    # Feature distribution summary (top features by variance, per contract)
    feat_cols = [c for c in df.columns if c.startswith("feat_")]
    numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]
    if numeric_feats and "contract_type" in df.columns:
        for ctype in sorted(df["contract_type"].unique()):
            grp = df[df["contract_type"] == ctype]
            desc = grp[numeric_feats].describe().T
            top = desc.nlargest(10, "std")
            print(f"\n=== {ctype}: Top 10 features by variance (n={len(grp)}) ===")
            print(top[["mean", "std", "min", "max"]].to_string())
else:
    print("No data available for deal health analysis.")

# %% [markdown]
# # §2 Auction Health
#
# Bid distribution, pass rate, and contract selection. Requires eval logs
# (auction transcript data is not available in synthetic mode).

# %%
if _data_source == "eval_logs" and not df.empty:
    # Aggregate to one row per deal (use seat 0 since auction fields are identical)
    deal_df = df[df["seat"] == 0].copy()

    # Bid distribution by contract type
    if "contract_type" in deal_df.columns:
        print("=== Bid Distribution ===")
        for ctype in sorted(deal_df["contract_type"].unique()):
            grp = deal_df[deal_df["contract_type"] == ctype]
            if "winning_bid" in grp.columns:
                bid_dist = grp["winning_bid"].value_counts().sort_index()
                print(f"\n{ctype} (n={len(grp)}):")
                print(bid_dist.to_string())

    # Pass rate and auction length
    if "n_passes" in deal_df.columns and "auction_rounds" in deal_df.columns:
        print("\n=== Auction Summary ===")
        pass_rate = deal_df["n_passes"].mean() / deal_df["auction_rounds"].mean()
        print(f"Mean pass rate: {pass_rate:.3f}")
        print(f"Mean bids/deal: {deal_df['n_bids'].mean():.2f}")
        print(f"Mean passes/deal: {deal_df['n_passes'].mean():.2f}")

    # Contract selection frequency
    if "contract_type" in deal_df.columns:
        print("\n=== Contract Selection ===")
        print(deal_df["contract_type"].value_counts().to_string())
else:
    print(
        "Auction health requires eval logs (not synthetic data) — skipping."
        if _data_source != "eval_logs"
        else "No data available for auction health."
    )

# %% [markdown]
# # §3 Gameplay Health
#
# Tricks won distribution and team balance, faceted by contract type.

# %%
if not df.empty and "tricks_won" in df.columns and "contract_type" in df.columns:
    ctypes = sorted(df["contract_type"].unique())

    # Tricks won distribution by contract type
    fig, axes = plt.subplots(1, len(ctypes), figsize=(5 * len(ctypes), 4), sharey=True)
    if not hasattr(axes, "__len__"):
        axes = [axes]
    for ax, ctype in zip(axes, ctypes):
        grp = df[df["contract_type"] == ctype]
        ax.hist(grp["tricks_won"], bins=11, range=(0, 10), edgecolor="black", alpha=0.7)
        ax.set_title(f"Tricks Won: {ctype}")
        ax.set_xlabel("Tricks Won")
        ax.set_ylabel("Count")
    plt.tight_layout()
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / "tricks_won_by_contract.png", dpi=150)
    plt.show()

    # Team balance by contract type
    print("\n=== Team Balance (mean tricks_won) ===")
    if "team" in df.columns:
        team_bal = df.groupby(["contract_type", "team"])["tricks_won"].mean().unstack()
        print(team_bal.to_string())
else:
    print("No data available for gameplay health analysis.")

# %% [markdown]
# # §4 Auction Outcomes
#
# Bid accuracy and make rate, faceted by contract type.
# Uses bidder-only rows (one per deal) to avoid double-counting.

# %%
if not df.empty and "is_bidder" in df.columns:
    bidder_df = df[df["is_bidder"] == True].copy()  # noqa: E712

    if not bidder_df.empty and "contract_type" in bidder_df.columns:
        print("=== Bid Accuracy & Make Rate ===")
        for ctype in sorted(bidder_df["contract_type"].unique()):
            grp = bidder_df[bidder_df["contract_type"] == ctype]
            n = len(grp)
            if "made_bid" in grp.columns and n > 0:
                make_rate = grp["made_bid"].mean()
                print(f"\n{ctype} (n={n}):")
                print(f"  Make rate: {make_rate:.3f}")

            if "winning_bid" in grp.columns and "tricks_won" in grp.columns:
                overbid = (grp["tricks_won"] < grp["winning_bid"]).mean()
                underbid = (grp["tricks_won"] > grp["winning_bid"] + 1).mean()
                mean_surplus = (grp["tricks_won"] - grp["winning_bid"]).mean()
                print(f"  Overbid rate: {overbid:.3f}")
                print(f"  Underbid rate (>1 surplus): {underbid:.3f}")
                print(f"  Mean surplus: {mean_surplus:+.2f}")
    else:
        print("No bidder rows found — skipping auction outcomes.")
else:
    print("No bidder flag available — skipping auction outcomes.")

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
    else:
        print("No declaring team rows — skipping gameplay outcomes.")
else:
    print("No declaring team flag — skipping gameplay outcomes.")

# %% [markdown]
# # §6 Model Specs
#
# Feature selection and coefficient display for each model arm,
# faceted by contract type.

# %%
if _model_artifacts:
    for arm_key, artifact in _model_artifacts.items():
        print(f"\n{'='*60}")
        print(f"Model: {arm_key} (type={artifact.get('artifact_type', '?')})")
        print(f"{'='*60}")

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

    # Coefficient heatmap for the primary arm
    primary_arm = (
        "olsa_full"
        if "olsa_full" in _model_artifacts
        else next(iter(_model_artifacts), None)
    )
    if primary_arm:
        artifact = _model_artifacts[primary_arm]
        payoff = artifact.get("payoff_model", {})
        contracts = sorted(payoff.keys())
        all_features = set()
        for model in payoff.values():
            all_features.update(model.get("feature_names", []))
        all_features = sorted(all_features)

        if all_features and contracts:
            coef_matrix = np.zeros((len(all_features), len(contracts)))
            for j, contract in enumerate(contracts):
                model = payoff[contract]
                fnames = model.get("feature_names", [])
                weights = model.get("weights", [])
                for fname, w in zip(fnames, weights):
                    if fname in all_features:
                        coef_matrix[all_features.index(fname), j] = w

            fig, ax = plt.subplots(figsize=(8, max(4, len(all_features) * 0.4)))
            im = ax.imshow(coef_matrix, aspect="auto", cmap="RdBu_r")
            ax.set_xticks(range(len(contracts)))
            ax.set_xticklabels(contracts)
            ax.set_yticks(range(len(all_features)))
            ax.set_yticklabels(all_features, fontsize=8)
            ax.set_title(f"Coefficient Heatmap: {primary_arm}")
            plt.colorbar(im, ax=ax, label="Weight")
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig.savefig(out / "coefficient_heatmap.png", dpi=150)
            plt.show()
else:
    print("No model artifacts loaded — skipping model specs.")

# %% [markdown]
# # §7 Model Performance
#
# Predicted vs actual tricks, residual distribution, and bootstrap R²/MAE
# by contract type. Uses actual model weights from artifacts.

# %%
if _model_artifacts and not df.empty and "tricks_won" in df.columns:
    # Use primary arm for performance plots
    primary_arm = (
        "olsa_full" if "olsa_full" in _model_artifacts else next(iter(_model_artifacts))
    )
    artifact = _model_artifacts[primary_arm]
    payoff = artifact.get("payoff_model", {})

    all_y = []
    all_pred = []
    all_residuals = []

    for contract, model in sorted(payoff.items()):
        feature_names = model.get("feature_names", [])
        weights = np.array(model.get("weights", []))
        bias = model.get("bias", 0.0)

        if not feature_names or len(weights) == 0:
            continue

        feat_cols = [f"feat_{fn}" for fn in feature_names]
        subset = df[df["contract_type"] == contract].copy()

        # Check all feature columns exist
        missing = [c for c in feat_cols if c not in subset.columns]
        if missing:
            print(f"[{contract}] Missing features: {missing} — skipping.")
            continue

        if len(subset) == 0:
            continue

        X = subset[feat_cols].values.astype(np.float64)
        y_actual = subset["tricks_won"].values.astype(np.float64)
        y_pred = X @ weights + bias

        all_y.extend(y_actual)
        all_pred.extend(y_pred)
        all_residuals.extend(y_actual - y_pred)

        # Per-contract metrics
        ss_res = np.sum((y_actual - y_pred) ** 2)
        ss_tot = np.sum((y_actual - y_actual.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mae = np.mean(np.abs(y_actual - y_pred))
        print(f"[{contract}] R²={r2:.4f}, MAE={mae:.4f} (n={len(subset)})")

    if all_y and all_pred:
        all_y = np.array(all_y)
        all_pred = np.array(all_pred)
        all_residuals = np.array(all_residuals)

        # Pred vs Actual scatter
        fig_scatter, ax_scatter = plt.subplots(figsize=(6, 5))
        ax_scatter.scatter(all_y, all_pred, alpha=0.3, s=5)
        lims = [min(all_y.min(), all_pred.min()), max(all_y.max(), all_pred.max())]
        ax_scatter.plot(lims, lims, "r--", linewidth=1, label="y=x")
        ax_scatter.set_xlabel("Actual Tricks Won")
        ax_scatter.set_ylabel("Predicted Tricks Won")
        ax_scatter.set_title(f"Pred vs Actual: {primary_arm}")
        ax_scatter.legend()
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_scatter.savefig(out / "pred_vs_actual_scatter.png", dpi=150)
        plt.show()

        # Residual distribution
        fig_resid, ax_resid = plt.subplots(figsize=(6, 5))
        ax_resid.hist(all_residuals, bins=31, edgecolor="black", alpha=0.7)
        ax_resid.axvline(0, color="red", linestyle="--", linewidth=1)
        ax_resid.set_xlabel("Residual (actual - predicted)")
        ax_resid.set_ylabel("Count")
        ax_resid.set_title(f"Residual Distribution: {primary_arm}")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_resid.savefig(out / "residual_distribution.png", dpi=150)
        plt.show()

        # Bootstrap R²/MAE with CIs (skip in SMOKE)
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
# # §8 Dual-Arm Comparison
#
# Side-by-side OLSa vs OLSa_Full metrics from eval JSON artifacts.

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
