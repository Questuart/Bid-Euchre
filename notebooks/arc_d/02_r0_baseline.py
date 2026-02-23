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
# # R0 Baseline — Eval-Only Verification
#
# **Goal:** Retroactive eval-side HITL verification for R0 baseline lock.
#
# This notebook runs in **eval-only mode**: `RUN_DIR` is empty (§1–§7 skip
# gracefully), and `ARTIFACT_DIR` points to the R0 artifacts (§8–§12 active).
# If the artifacts are missing, §8 fails fast with `FileNotFoundError`.
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
# - Verify with: `make notebook-run-arc-d NOTEBOOK=notebooks/arc_d/02_r0_baseline.ipynb`

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE | QUICK | FULL
SEED = 42  # RNG seed
SPLIT_TYPE = "three_way"  # split partition type
ACTIVE_SPLIT = "val"  # val | test
MODEL_ARTIFACT_PATH = ""  # not used for eval-only
SEMANTIC_GATE_OUTPUT_DIR = ""  # not used for eval-only
CHART_OUTPUT_DIR = ""  # dir for chart PNGs (separate from gate JSON)
RUN_DIR = ""  # empty: eval-only mode
SPLIT_MANIFEST_PATH = ""  # not used for eval-only
ARTIFACT_DIR = "data/artifacts/arc_d/r0"  # R0 artifact directory
RUNG_ID = "r0"  # R0 baseline
PROMOTION_DECISION_PATH = "data/artifacts/arc_d/r0/promotion_decision_r0.json"

# %% [markdown]
# # §0 Imports

# %%
import json
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
from bid_euchre.reporting.evaluator import load_eval_metrics

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

# %% [markdown]
# # ── Eval-Side Verification ──
#
# Sections §8–§12 read **eval JSON artifacts** from `ARTIFACT_DIR`.
# They are independent of §1–§7 (which require training data via `RUN_DIR`).
# When `RUN_DIR` is empty and `ARTIFACT_DIR` is set, this is **eval-only mode**.
# When `ARTIFACT_DIR` is also empty (template default), §8–§12 skip gracefully.
# When `ARTIFACT_DIR` is set but files are missing, execution **fails fast**.

# %% [markdown]
# # §8 Eval Metrics Summary

# %%
# Canonical metric name -> display alias (single mapping point for §8–§12).
METRIC_ALIASES = {
    "net_expected_points_per_deal": "net_eppd",
    "expected_points_per_deal": "eppd",
    "bid_rate": "bid_rate",
    "make_rate": "make_rate",
    "cvar_5": "cvar_5",
    "downside_variance": "downside_variance",
}

_eval_available = False
_rung_bundle = None
_arm_metrics = {}

if not ARTIFACT_DIR:
    print("ARTIFACT_DIR not set — skipping eval-side verification (§8–§12).")
else:
    artifact_dir = Path(ARTIFACT_DIR)
    # Fail fast if ARTIFACT_DIR is set but bundle missing (Finding 8)
    bundle_path = artifact_dir / f"rung_bundle_{RUNG_ID}.json"
    with open(bundle_path) as f:
        _rung_bundle = json.load(f)

    # Load metrics for each arm
    for arm_key in ("olsa", "olsa_full"):
        arm_block = _rung_bundle.get(arm_key, {})
        eval_path = arm_block.get("eval_seed42")
        if eval_path:
            _arm_metrics[arm_key] = load_eval_metrics(eval_path)

    # Build summary table
    rows = []
    for arm_key, metrics in _arm_metrics.items():
        row = {"arm": arm_key}
        for canonical, alias in METRIC_ALIASES.items():
            row[alias] = metrics.get(canonical)
        rows.append(row)

    if rows:
        df_eval = pd.DataFrame(rows).set_index("arm")
        print(df_eval.to_string())
        _eval_available = True
    else:
        print("No eval metrics loaded — check bundle eval_seed42 paths.")

# %% [markdown]
# # §9 Dual-Arm Comparison

# %%
if _eval_available and len(_arm_metrics) == 2:
    rate_keys = ["bid_rate", "make_rate"]
    point_keys = ["net_eppd", "eppd", "cvar_5", "downside_variance"]
    arms = list(_arm_metrics.keys())

    fig, (ax_rates, ax_points) = plt.subplots(1, 2, figsize=(14, 5))

    # Left: rate metrics [0, 1]
    x_r = np.arange(len(rate_keys))
    width = 0.35
    for i, arm in enumerate(arms):
        vals = []
        for rk in rate_keys:
            # Find canonical key for this alias
            canonical = next((c for c, a in METRIC_ALIASES.items() if a == rk), rk)
            vals.append(_arm_metrics[arm].get(canonical, 0) or 0)
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
            vals.append(_arm_metrics[arm].get(canonical, 0) or 0)
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
        print(f"Saved dual_arm_comparison.png to {out}")
    plt.show()
elif not _eval_available:
    print("Eval metrics not available — skipping dual-arm comparison.")
else:
    print("Need both arms for dual-arm comparison — skipping.")

# %% [markdown]
# # §10 Seed Sensitivity

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
            if (vals and len(vals) >= 2 and mean_val and abs(mean_val) > 1e-9)
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

    # Warning (not assert) if CV >= 10% (Finding 3)
    for _, row in df_seeds.iterrows():
        if row.get("CV(%)") is not None and row["CV(%)"] >= 10.0:
            print(
                f"\n**WARNING:** {row.name} has CV={row['CV(%)']:.1f}% >= 10% "
                "— high seed sensitivity detected."
            )
else:
    print("Eval metrics not available — skipping seed sensitivity.")

# %% [markdown]
# # §11 Attribution Gap

# %%
if _eval_available:
    _attr_gap = None
    _attr_source = None

    # Try reading from promotion decision JSON first
    if PROMOTION_DECISION_PATH and Path(PROMOTION_DECISION_PATH).exists():
        with open(PROMOTION_DECISION_PATH) as f:
            decision = json.load(f)
        _attr_gap = decision.get("attribution_gap")
        _attr_source = "promotion_decision"
    else:
        # Compute from seed-42 metrics: OLSa_Full - OLSa
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
else:
    print("Eval metrics not available — skipping attribution gap.")

# %% [markdown]
# # §12 Promotion Gate Outcome

# %%
if PROMOTION_DECISION_PATH and Path(PROMOTION_DECISION_PATH).exists():
    with open(PROMOTION_DECISION_PATH) as f:
        _decision_data = json.load(f)

    print(f"Decision: {_decision_data.get('decision', 'UNKNOWN')}")
    print(f"Rung: {_decision_data.get('rung_id', '?')}")
    print(f"Arc: {_decision_data.get('arc', '?')}")
    print()

    # Tier 1 checks table
    tier1 = _decision_data.get("tier_1_checks", {})
    if tier1:
        df_tier1 = pd.DataFrame([{"check": k, "status": v} for k, v in tier1.items()])
        print("Tier 1 Checks:")
        print(df_tier1.to_string(index=False))
        print()

    # Gate results summary
    gate_results = _decision_data.get("gate_results", {})
    if gate_results:
        print("Gate Results:")
        for key, val in gate_results.items():
            if isinstance(val, dict):
                print(f"  {key}: pass={val.get('pass')} — {val.get('note', '')}")
            else:
                print(f"  {key}: {val}")
        print()

    # Cross-reference attribution gap
    ag = _decision_data.get("attribution_gap")
    if ag is not None:
        print(f"Attribution gap (from decision): {ag:.6f}")
elif PROMOTION_DECISION_PATH:
    print(f"Promotion decision file not found: {PROMOTION_DECISION_PATH}")
else:
    print("PROMOTION_DECISION_PATH not set — skipping promotion gate outcome.")
