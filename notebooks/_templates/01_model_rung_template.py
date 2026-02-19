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
# **Goal:** Structured model evaluation with semantic gate emission.
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
# - Parameterize via papermill — do not hardcode paths.

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
SPLIT_TYPE = "three_way"  # split partition type
ACTIVE_SPLIT = "val"  # val | test
MODEL_ARTIFACT_PATH = ""  # path to trained model artifact
SEMANTIC_GATE_OUTPUT_DIR = ""  # dir for semantic_gate_{split}.json
CHART_OUTPUT_DIR = ""  # dir for chart PNGs (separate from gate JSON)
RUN_DIR = ""  # data/runs/<run_id>
SPLIT_MANIFEST_PATH = ""  # path to split_manifest.json

# %% [markdown]
# # §0 Imports

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bid_euchre.diagnostics.semantic_gate import (
    compute_semantic_gate,
    emit_semantic_gate,
)
from bid_euchre.diagnostics.split_guard import require_split
from bid_euchre.features.hand_eval import (
    score_hand_tuple,  # noqa: F401 — used in model-wired variants
)
from bid_euchre.models.splits import SplitManifest

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}

# %% [markdown]
# # §1 Data Loading

# %%
run_path = Path(RUN_DIR) if RUN_DIR else None

if run_path is not None:
    df_features = pd.read_parquet(run_path / "datasets" / "bidless.parquet")
    df_outcomes = pd.read_parquet(run_path / "datasets" / "bidless_outcomes.parquet")
    print(f"Features shape: {df_features.shape}")
    print(f"Outcomes shape: {df_outcomes.shape}")
else:
    df_features = pd.DataFrame()
    df_outcomes = pd.DataFrame()
    print("No RUN_DIR specified — using empty DataFrames.")

manifest = None
if SPLIT_MANIFEST_PATH:
    manifest = SplitManifest.load(SPLIT_MANIFEST_PATH)
    df_features = require_split(
        df_features, manifest, ACTIVE_SPLIT, SEED, active_split=ACTIVE_SPLIT
    )
    print(f"After split filter ({ACTIVE_SPLIT}): {len(df_features)} rows")
elif run_path is not None:
    # Safety: warn that split enforcement is bypassed.
    # For promotion, SPLIT_MANIFEST_PATH must be provided.
    print(
        "WARNING: SPLIT_MANIFEST_PATH not provided — split guard bypassed. "
        "Full dataset loaded without access control. "
        "Set SPLIT_MANIFEST_PATH for promotion-track evaluation."
    )

print(f"MODE={MODE}, max deals={MODE_DEAL_COUNTS.get(MODE, '?')}")

# %% [markdown]
# # §2 Fairness Assessment

# %%
if not df_features.empty and "seat" in df_features.columns:
    # Use hand_value for seat-balance chart (matches semantic gate check_seat_balance).
    # Fall back to tricks_won if hand_value is not available.
    balance_col = "hand_value" if "hand_value" in df_features.columns else "tricks_won"
    contract_col = "contract_type" if "contract_type" in df_features.columns else None
    if contract_col:
        fig, axes = plt.subplots(
            1,
            df_features[contract_col].nunique(),
            figsize=(5 * df_features[contract_col].nunique(), 4),
            sharey=True,
        )
        if not hasattr(axes, "__len__"):
            axes = [axes]
        for ax, (ctype, grp) in zip(axes, df_features.groupby(contract_col)):
            seat_data = [
                grp.loc[grp["seat"] == s, balance_col].dropna()
                for s in sorted(grp["seat"].unique())
            ]
            if seat_data:
                ax.boxplot(seat_data, labels=sorted(grp["seat"].unique()))
            ax.set_title(f"Seat balance: {ctype}")
            ax.set_xlabel("Seat")
            ax.set_ylabel(balance_col)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig.savefig(out / "seat_balance_boxplot.png", dpi=150)
            print(f"Saved seat_balance_boxplot.png to {out}")
        plt.show()
    else:
        print("No contract_type column — skipping fairness boxplot.")
else:
    print("No data available for fairness assessment.")

# %% [markdown]
# # §3 Directional Sanity

# %%
# Placeholder: pred_vs_actual scatter and residual distribution.
# These become real when a model artifact is wired in. For now, show
# tricks_won distribution as a stand-in visualization.

fig_scatter, ax_scatter = plt.subplots(figsize=(6, 5))
if not df_features.empty and "tricks_won" in df_features.columns:
    ax_scatter.hist(df_features["tricks_won"], bins=11, edgecolor="black", alpha=0.7)
    ax_scatter.set_title("Tricks Won Distribution (placeholder for pred vs actual)")
    ax_scatter.set_xlabel("Tricks Won")
    ax_scatter.set_ylabel("Count")
else:
    ax_scatter.text(0.5, 0.5, "No data", ha="center", va="center")
    ax_scatter.set_title("pred vs actual (no data)")
plt.tight_layout()
if CHART_OUTPUT_DIR:
    out = Path(CHART_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    fig_scatter.savefig(out / "pred_vs_actual_scatter.png", dpi=150)
    print(f"Saved pred_vs_actual_scatter.png to {out}")
plt.show()

fig_resid, ax_resid = plt.subplots(figsize=(6, 5))
if not df_features.empty and "tricks_won" in df_features.columns:
    residuals = df_features["tricks_won"] - df_features["tricks_won"].mean()
    ax_resid.hist(residuals, bins=21, edgecolor="black", alpha=0.7)
    ax_resid.set_title("Residual Distribution (placeholder — mean-baseline)")
    ax_resid.set_xlabel("Residual")
    ax_resid.set_ylabel("Count")
else:
    ax_resid.text(0.5, 0.5, "No data", ha="center", va="center")
    ax_resid.set_title("Residual distribution (no data)")
plt.tight_layout()
if CHART_OUTPUT_DIR:
    out = Path(CHART_OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    fig_resid.savefig(out / "residual_distribution.png", dpi=150)
    print(f"Saved residual_distribution.png to {out}")
plt.show()

# %% [markdown]
# # §4 Performance Metrics

# %%
if MODE == "SMOKE":
    print("SMOKE mode — skipping bootstrap performance metrics (need QUICK or FULL).")
elif not df_features.empty and "tricks_won" in df_features.columns:
    rng = np.random.default_rng(SEED)
    contract_col = "contract_type" if "contract_type" in df_features.columns else None
    groups = (
        df_features.groupby(contract_col) if contract_col else [("all", df_features)]
    )
    for ctype, grp in groups:
        y = grp["tricks_won"].values
        y_mean = y.mean()
        # Baseline: predict mean (placeholder until model wired)
        preds = np.full_like(y, fill_value=y_mean, dtype=float)
        ss_res = np.sum((y - preds) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mae = np.mean(np.abs(y - preds))

        # Bootstrap CIs
        n_boot = 1_000
        boot_r2 = []
        boot_mae = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(y), size=len(y))
            y_b = y[idx]
            p_b = preds[idx]
            ss_res_b = np.sum((y_b - p_b) ** 2)
            ss_tot_b = np.sum((y_b - y_b.mean()) ** 2)
            boot_r2.append(1 - ss_res_b / ss_tot_b if ss_tot_b > 0 else float("nan"))
            boot_mae.append(np.mean(np.abs(y_b - p_b)))

        r2_ci = np.nanpercentile(boot_r2, [2.5, 97.5])
        mae_ci = np.nanpercentile(boot_mae, [2.5, 97.5])
        print(
            f"[{ctype}] R²={r2:.4f} [{r2_ci[0]:.4f}, {r2_ci[1]:.4f}] "
            f"MAE={mae:.4f} [{mae_ci[0]:.4f}, {mae_ci[1]:.4f}]  (mean-baseline)"
        )
else:
    print("No data available for performance metrics.")

# %% [markdown]
# # §5 Feature Analysis

# %%
if not df_features.empty:
    # Identify feature columns (exclude metadata)
    exclude_cols = {
        "hand_id",
        "seat",
        "contract_type",
        "trump_suit",
        "tricks_won",
        "bid",
        "made_bid",
    }
    feature_cols = [c for c in df_features.columns if c not in exclude_cols]
    contract_col = "contract_type" if "contract_type" in df_features.columns else None
    groups = (
        df_features.groupby(contract_col) if contract_col else [("all", df_features)]
    )
    for ctype, grp in groups:
        print(f"\n=== {ctype} (n={len(grp)}) ===")
        desc = grp[feature_cols].describe().T
        # Show top-N by mean
        top_n = desc.nlargest(10, "mean")
        print(top_n[["mean", "std", "min", "max"]].to_string())
else:
    feature_cols = []
    print("No data available for feature analysis.")

# %% [markdown]
# # §6 Semantic Gate Emission

# %%
eval_df = df_features

if not eval_df.empty:
    gate = compute_semantic_gate(
        df=eval_df,
        mode=MODE,
        active_split=ACTIVE_SPLIT,
        seed=SEED,
        manifest=manifest,
        feature_cols=feature_cols if feature_cols else None,
    )
    print(f"Gate status: {gate['gate_status']}")
    for check in gate.get("checks", []):
        print(
            f"  {check['check_name']}: {check['status']} — {check.get('message', '')}"
        )

    if SEMANTIC_GATE_OUTPUT_DIR:
        path = emit_semantic_gate(
            gate, SEMANTIC_GATE_OUTPUT_DIR, active_split=ACTIVE_SPLIT
        )
        print(f"\nGate artifact written to: {path}")
else:
    print("No data — skipping semantic gate computation.")

# %% [markdown]
# # §7 Summary
#
# Review the gate status above. A **PASS** gate means all Tier-1 (health)
# and Tier-2 (quality) checks passed. A **FAIL** gate requires investigation
# before promotion. **SKIP** checks indicate preconditions were not met
# (e.g., SMOKE mode, missing manifest) and are non-blocking.
#
# **Next steps:**
# - If gate PASS → proceed to promotion workflow.
# - If gate FAIL → investigate failing checks, fix, re-run.
# - If many SKIP → ensure required inputs (manifest, predictions) are provided.
