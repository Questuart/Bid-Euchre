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
# # Feature-Outcome Evaluation Template (Arc D)
#
# **Goal:** Model-focused HITL evaluation — feature-outcome correlations,
# model coefficients, prediction diagnostics, dual-arm comparison,
# calibration analysis, and promotion readiness assessment.
#
# **Data source:** JSONL eval logs (primary) or synthetic demo data (CI fallback).
#
# **Workflow rules**
# - This template is COPIED per rung (not parameterized via papermill).
# - Section 6 is filled per-rung with rung-specific analysis.
# - Edit the `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
EVAL_LOG_PATH = ""  # R1 eval log (populate when R1 data exists)
ARTIFACT_DIR = "data/artifacts/arc_d/r1"
MODE = "SMOKE"  # SMOKE | QUICK | FULL
RUNG_ID = "r1"
CHART_OUTPUT_DIR = ""  # dir for chart PNGs

# %% [markdown]
# # S0 Configuration & Data Loading

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

# %%
import json

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

try:
    from scipy import stats as scipy_stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.reporting.evaluator import load_eval_metrics

SEED = 42
MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
max_deals = MODE_DEAL_COUNTS.get(MODE)

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

if EVAL_LOG_PATH:
    eval_log = Path(EVAL_LOG_PATH)
    if eval_log.is_dir():
        # Convention: logs/ subdir contains JSONL files
        candidates = sorted(eval_log.glob("logs/*.jsonl"))
        if not candidates:
            candidates = sorted(eval_log.glob("*.jsonl"))
        if candidates:
            eval_log = candidates[0]
            print(f"  Resolved directory to: {eval_log.name}")
        else:
            print(f"WARNING: No .jsonl files found in {eval_log}")
    if eval_log.exists() and eval_log.is_file():
        try:
            df = build_eval_dataset(str(eval_log), max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {eval_log.name}")
            print(f"  Deals: {df['deal_id'].nunique()}, Source: {_data_source}")
        except (FileNotFoundError, ValueError, IsADirectoryError) as exc:
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
    _synth_features = [
        "hand_value",
        "trump_count",
        "bowers",
        "aces",
        "voids",
        "singletons",
        "long_suit_length",
        "short_suit_count",
        "offsuit_aces",
        "offsuit_non_ace_count",
    ]
    for deal_id in range(n_deals):
        contract = rng.choice(["suit", "high", "low"])
        trump = rng.choice(["C", "D", "H", "S"]) if contract == "suit" else None
        t0 = int(rng.integers(0, 11))
        t1 = 10 - t0
        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            row = {
                "deal_id": deal_id,
                "hand_id": deal_id,
                "seat": seat,
                "team": team,
                "contract_type": contract,
                "trump": trump,
                "tricks_won": t0 if seat in (0, 2) else t1,
                "is_bidder": seat == 0,
                "is_declaring_team": team == 0,
                "winning_bid": int(rng.integers(5, 11)),
                "made_bid": bool(rng.random() > 0.3),
                "n_bids": int(rng.integers(1, 4)),
                "n_passes": int(rng.integers(1, 4)),
                "auction_rounds": 4,
            }
            # Synthetic features
            for feat_name in _synth_features:
                row[f"feat_{feat_name}"] = float(rng.normal(5.0, 2.0))
            rows.append(row)
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

        def _resolve_path(ref: str, anchor: Path) -> Path:
            """Resolve a repo-root-relative path via bundle location."""
            p = Path(ref)
            if p.exists():
                return p
            for ancestor in anchor.resolve().parents:
                candidate = ancestor / ref
                if candidate.exists():
                    return candidate
            return p

        # Load eval metrics for each arm
        for arm_key in ("olsa", "olsa_full"):
            arm_block = _rung_bundle.get(arm_key, {})
            eval_path = arm_block.get("eval_seed42")
            if eval_path:
                try:
                    _arm_metrics[arm_key] = load_eval_metrics(
                        str(_resolve_path(eval_path, bundle_path))
                    )
                except (FileNotFoundError, json.JSONDecodeError):
                    pass

            # Load model artifact for predictions
            model_path = arm_block.get("artifact_path")
            if model_path:
                resolved_model = _resolve_path(model_path, bundle_path)
                if resolved_model.exists():
                    with open(resolved_model) as f:
                        _model_artifacts[arm_key] = json.load(f)

        if _arm_metrics:
            _eval_available = True
            print(f"Loaded eval metrics for arms: {list(_arm_metrics.keys())}")
        print(f"Loaded model artifacts for arms: {list(_model_artifacts.keys())}")
    else:
        print(f"Bundle not found: {bundle_path} -- eval sections will skip.")
else:
    print("ARTIFACT_DIR not set -- model/eval sections will use data-only analysis.")

# Canonical metric aliases (single mapping point for eval sections)
METRIC_ALIASES = {
    "net_expected_points_per_deal": "net_eppd",
    "expected_points_per_deal": "eppd",
    "bid_rate": "bid_rate",
    "make_rate": "make_rate",
    "cvar_5": "cvar_5",
    "downside_variance": "downside_variance",
}

# Data summary
feat_cols = [c for c in df.columns if c.startswith("feat_")]
print(f"\nDataset shape: {df.shape}")
print(f"Feature columns: {len(feat_cols)}")
if "contract_type" in df.columns:
    print(f"Contract types: {sorted(df['contract_type'].unique())}")
    print("Deals per contract:")
    for ct in sorted(df["contract_type"].unique()):
        n = df[df["contract_type"] == ct]["deal_id"].nunique()
        print(f"  {ct}: {n}")

# %% [markdown]
# # S1 Feature-Outcome Correlations
#
# Per-contract Pearson correlation of each feature with tricks_won.
# Faceted by contract_type as required by the contract-type faceting rule.

# %%
if not df.empty and "tricks_won" in df.columns and feat_cols:
    # --- Feature-outcome correlation heatmap ---
    ctypes = (
        sorted(df["contract_type"].unique()) if "contract_type" in df.columns else []
    )

    if ctypes:
        # Build correlation matrix: rows=features, columns=contract_types
        corr_data = {}
        for ct in ctypes:
            grp = df[df["contract_type"] == ct]
            ct_corrs = {}
            for fc in feat_cols:
                if pd.api.types.is_numeric_dtype(grp[fc]):
                    valid = grp[fc].notna() & grp["tricks_won"].notna()
                    if valid.sum() > 2:
                        ct_corrs[fc] = grp.loc[valid, fc].corr(
                            grp.loc[valid, "tricks_won"]
                        )
                    else:
                        ct_corrs[fc] = np.nan
            corr_data[ct] = ct_corrs

        corr_df = pd.DataFrame(corr_data)
        corr_df.index = [c.replace("feat_", "") for c in corr_df.index]

        # Heatmap
        fig, ax = plt.subplots(figsize=(8, max(4, len(corr_df) * 0.35)))
        vmax = max(abs(corr_df.min().min()), abs(corr_df.max().max()))
        vmax = max(vmax, 0.1)  # minimum scale
        im = ax.imshow(
            corr_df.values, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax
        )
        ax.set_xticks(range(len(ctypes)))
        ax.set_xticklabels(ctypes)
        ax.set_yticks(range(len(corr_df)))
        ax.set_yticklabels(corr_df.index, fontsize=8)
        ax.set_title("Feature-Outcome Correlation (Pearson r vs tricks_won)")
        plt.colorbar(im, ax=ax, label="Pearson r")
        # Annotate cells
        for i in range(len(corr_df)):
            for j in range(len(ctypes)):
                val = corr_df.iloc[i, j]
                if not np.isnan(val):
                    color = "white" if abs(val) > vmax * 0.6 else "black"
                    ax.text(
                        j,
                        i,
                        f"{val:.2f}",
                        ha="center",
                        va="center",
                        fontsize=7,
                        color=color,
                    )
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig.savefig(
                out / "feature_outcome_heatmap.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # --- Top 5 features by |r| per contract (grouped bar chart) ---
        top_n = 5
        fig_top, axes_top = plt.subplots(
            1, len(ctypes), figsize=(6 * len(ctypes), 5), sharey=True
        )
        if not hasattr(axes_top, "__len__"):
            axes_top = [axes_top]

        for ax_i, ct in zip(axes_top, ctypes):
            ct_series = corr_df[ct].dropna().abs().nlargest(top_n)
            colors = [
                "#2ecc71" if corr_df.loc[f, ct] > 0 else "#e74c3c"
                for f in ct_series.index
            ]
            bars = ax_i.barh(
                range(len(ct_series)), ct_series.values, color=colors, alpha=0.8
            )
            ax_i.set_yticks(range(len(ct_series)))
            ax_i.set_yticklabels(ct_series.index, fontsize=9)
            ax_i.set_xlabel("|Pearson r|")
            ax_i.set_title(f"Top {top_n} Features: {ct}")
            ax_i.invert_yaxis()
            ax_i.set_xlim(0, 1.0)
            ax_i.grid(True, alpha=0.3, axis="x")
            # Annotate with signed r
            for bar, feat in zip(bars, ct_series.index):
                signed_r = corr_df.loc[feat, ct]
                ax_i.text(
                    bar.get_width() + 0.02,
                    bar.get_y() + bar.get_height() / 2,
                    f"r={signed_r:+.3f}",
                    va="center",
                    fontsize=8,
                )

        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_top.savefig(
                out / "top_features_by_correlation.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # --- Full correlation table with p-values ---
        print("\n=== Full Feature-Outcome Correlation Table ===")
        for ct in ctypes:
            grp = df[df["contract_type"] == ct]
            print(f"\n--- {ct} (n={len(grp)}) ---")
            rows_table = []
            for fc in feat_cols:
                if not pd.api.types.is_numeric_dtype(grp[fc]):
                    continue
                valid = grp[fc].notna() & grp["tricks_won"].notna()
                n_valid = valid.sum()
                if n_valid > 2:
                    r_val = grp.loc[valid, fc].corr(grp.loc[valid, "tricks_won"])
                    if HAS_SCIPY and n_valid > 2:
                        _, p_val = scipy_stats.pearsonr(
                            grp.loc[valid, fc], grp.loc[valid, "tricks_won"]
                        )
                    else:
                        p_val = np.nan
                    rows_table.append(
                        {
                            "feature": fc.replace("feat_", ""),
                            "pearson_r": round(r_val, 4),
                            "p_value": round(p_val, 6) if not np.isnan(p_val) else None,
                            "n": n_valid,
                        }
                    )
            if rows_table:
                tbl = pd.DataFrame(rows_table).sort_values(
                    "pearson_r", key=abs, ascending=False
                )
                print(tbl.to_string(index=False))
    else:
        print("No contract_type column -- skipping faceted correlation analysis.")
else:
    print("Insufficient data for feature-outcome correlations.")

# %% [markdown]
# # S2 Model Specification
#
# Feature selection and coefficient display for each model arm,
# faceted by contract type. Includes coefficient heatmap and
# side-by-side comparison of OLSa vs OLSa_Full.

# %%
if _model_artifacts:
    # --- Display model specifications ---
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
                pairs = sorted(
                    zip(fnames, weights), key=lambda x: abs(x[1]), reverse=True
                )
                for fname, w in pairs:
                    print(f"    {fname:40s} {w:+.6f}")

    # --- Coefficient heatmap for primary arm ---
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
        all_features_sorted = sorted(all_features)

        if all_features_sorted and contracts:
            # Build coefs_by_contract dict for plot_coefficient_heatmap
            coefs_by_contract = {}
            for contract in contracts:
                model = payoff[contract]
                fnames = model.get("feature_names", [])
                weights = model.get("weights", [])
                series_data = {fn: 0.0 for fn in all_features_sorted}
                for fn, w in zip(fnames, weights):
                    series_data[fn] = w
                coefs_by_contract[contract] = pd.Series(series_data)

            try:
                from bid_euchre.diagnostics.charts import plot_coefficient_heatmap

                fig = plot_coefficient_heatmap(
                    coefs_by_contract,
                    top_n=len(all_features_sorted),
                    title=f"Coefficient Heatmap: {primary_arm}",
                )
            except ImportError:
                # Fallback: manual heatmap
                coef_matrix = np.zeros((len(all_features_sorted), len(contracts)))
                for j, contract in enumerate(contracts):
                    model = payoff[contract]
                    fnames = model.get("feature_names", [])
                    weights = model.get("weights", [])
                    for fname, w in zip(fnames, weights):
                        if fname in all_features_sorted:
                            coef_matrix[all_features_sorted.index(fname), j] = w

                fig, ax = plt.subplots(
                    figsize=(8, max(4, len(all_features_sorted) * 0.4))
                )
                im = ax.imshow(coef_matrix, aspect="auto", cmap="RdBu_r")
                ax.set_xticks(range(len(contracts)))
                ax.set_xticklabels(contracts)
                ax.set_yticks(range(len(all_features_sorted)))
                ax.set_yticklabels(all_features_sorted, fontsize=8)
                ax.set_title(f"Coefficient Heatmap: {primary_arm}")
                plt.colorbar(im, ax=ax, label="Weight")

            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig.savefig(
                    out / "coefficient_heatmap.png", dpi=150, bbox_inches="tight"
                )
            plt.show()

    # --- Coefficient comparison: OLSa vs OLSa_Full ---
    if len(_model_artifacts) >= 2:
        arm_keys = list(_model_artifacts.keys())
        # Gather per-contract coefficient comparisons
        for arm0_key, arm1_key in [(arm_keys[0], arm_keys[1])]:
            payoff0 = _model_artifacts[arm0_key].get("payoff_model", {})
            payoff1 = _model_artifacts[arm1_key].get("payoff_model", {})

            all_contracts = sorted(set(payoff0.keys()) | set(payoff1.keys()))
            ncols = len(all_contracts)
            if ncols == 0:
                continue

            fig_comp, axes_comp = plt.subplots(
                1, ncols, figsize=(6 * ncols, 5), sharey=False
            )
            if not hasattr(axes_comp, "__len__"):
                axes_comp = [axes_comp]

            for ax_c, ct in zip(axes_comp, all_contracts):
                m0 = payoff0.get(ct, {})
                m1 = payoff1.get(ct, {})
                features_union = sorted(
                    set(m0.get("feature_names", [])) | set(m1.get("feature_names", []))
                )
                if not features_union:
                    ax_c.text(0.5, 0.5, "No features", ha="center", va="center")
                    continue

                w0_map = dict(
                    zip(
                        m0.get("feature_names", []),
                        m0.get("weights", []),
                    )
                )
                w1_map = dict(
                    zip(
                        m1.get("feature_names", []),
                        m1.get("weights", []),
                    )
                )

                y_pos = np.arange(len(features_union))
                bar_h = 0.35
                vals0 = [w0_map.get(f, 0.0) for f in features_union]
                vals1 = [w1_map.get(f, 0.0) for f in features_union]

                ax_c.barh(
                    y_pos - bar_h / 2,
                    vals0,
                    bar_h,
                    label=arm0_key,
                    alpha=0.8,
                    color="#3498db",
                )
                ax_c.barh(
                    y_pos + bar_h / 2,
                    vals1,
                    bar_h,
                    label=arm1_key,
                    alpha=0.8,
                    color="#e67e22",
                )
                ax_c.set_yticks(y_pos)
                ax_c.set_yticklabels(features_union, fontsize=8)
                ax_c.axvline(0, color="black", linewidth=0.8)
                ax_c.set_xlabel("Weight")
                ax_c.set_title(f"{ct}")
                ax_c.legend(fontsize=8)
                ax_c.grid(True, alpha=0.3, axis="x")

            fig_comp.suptitle("Coefficient Comparison by Contract", fontsize=13, y=1.02)
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_comp.savefig(
                    out / "coefficient_comparison.png", dpi=150, bbox_inches="tight"
                )
            plt.show()

    # --- Full coefficient table ---
    print("\n=== Full Coefficient Table ===")
    for arm_key, artifact in _model_artifacts.items():
        payoff = artifact.get("payoff_model", {})
        for contract, model in sorted(payoff.items()):
            fnames = model.get("feature_names", [])
            weights = model.get("weights", [])
            bias = model.get("bias", 0.0)
            if fnames:
                coef_tbl = pd.DataFrame(
                    {
                        "feature": fnames,
                        "weight": [round(w, 6) for w in weights],
                        "abs_weight": [round(abs(w), 6) for w in weights],
                    }
                ).sort_values("abs_weight", ascending=False)
                print(f"\n{arm_key} / {contract} (bias={bias:.4f}):")
                print(coef_tbl[["feature", "weight"]].to_string(index=False))
else:
    print("No model artifacts loaded -- skipping model specifications.")

# %% [markdown]
# # S3 Model Performance Diagnostics
#
# Predicted vs actual tricks, residual distribution, residuals vs predicted,
# and bootstrap R2/MAE confidence intervals by contract type.

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
    all_contracts = []
    per_contract_metrics = []

    for contract, model in sorted(payoff.items()):
        feature_names = model.get("feature_names", [])
        weights = np.array(model.get("weights", []))
        bias = model.get("bias", 0.0)

        if not feature_names or len(weights) == 0:
            continue

        feat_c = [f"feat_{fn}" for fn in feature_names]
        subset = df[df["contract_type"] == contract].copy()

        missing = [c for c in feat_c if c not in subset.columns]
        if missing:
            print(f"[{contract}] Missing features: {missing} -- skipping.")
            continue

        if len(subset) == 0:
            continue

        X = subset[feat_c].values.astype(np.float64)
        y_actual = subset["tricks_won"].values.astype(np.float64)
        y_pred = X @ weights + bias

        all_y.extend(y_actual)
        all_pred.extend(y_pred)
        all_contracts.extend([contract] * len(y_actual))

        # Per-contract metrics
        ss_res = np.sum((y_actual - y_pred) ** 2)
        ss_tot = np.sum((y_actual - y_actual.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        mae = np.mean(np.abs(y_actual - y_pred))
        residuals = y_actual - y_pred

        per_contract_metrics.append(
            {
                "contract": contract,
                "R2": round(r2, 4),
                "MAE": round(mae, 4),
                "N": len(subset),
                "mean_residual": round(np.mean(residuals), 4),
                "std_residual": round(np.std(residuals), 4),
                "P5_residual": round(np.percentile(residuals, 5), 4),
                "P95_residual": round(np.percentile(residuals, 95), 4),
                "max_abs_residual": round(np.max(np.abs(residuals)), 4),
            }
        )
        print(f"[{contract}] R2={r2:.4f}, MAE={mae:.4f} (n={len(subset)})")

    if all_y and all_pred:
        all_y_arr = np.array(all_y)
        all_pred_arr = np.array(all_pred)
        all_contracts_arr = np.array(all_contracts)

        # --- Use plot_model_diagnostics from diagnostics.model_charts ---
        try:
            from bid_euchre.diagnostics.model_charts import plot_model_diagnostics

            fig_diag = plot_model_diagnostics(
                all_y_arr,
                all_pred_arr,
                all_contracts_arr,
                title=f"Model Diagnostics: {primary_arm}",
            )
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_diag.savefig(
                    out / "pred_vs_actual_scatter.png", dpi=150, bbox_inches="tight"
                )
            plt.show()
        except ImportError:
            # Fallback: manual scatter + residual plots
            fig_s, ax_s = plt.subplots(figsize=(6, 5))
            ax_s.scatter(all_y_arr, all_pred_arr, alpha=0.3, s=5)
            lims = [
                min(all_y_arr.min(), all_pred_arr.min()),
                max(all_y_arr.max(), all_pred_arr.max()),
            ]
            ax_s.plot(lims, lims, "r--", linewidth=1, label="y=x")
            ax_s.set_xlabel("Actual Tricks Won")
            ax_s.set_ylabel("Predicted Tricks Won")
            ax_s.set_title(f"Pred vs Actual: {primary_arm}")
            ax_s.legend()
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_s.savefig(
                    out / "pred_vs_actual_scatter.png", dpi=150, bbox_inches="tight"
                )
            plt.show()

        # --- Residual distribution (standalone) ---
        all_residuals = all_y_arr - all_pred_arr
        fig_resid, ax_resid = plt.subplots(figsize=(7, 5))
        ctypes_present = sorted(set(all_contracts_arr))
        for ct in ctypes_present:
            mask = all_contracts_arr == ct
            ax_resid.hist(
                all_residuals[mask],
                bins=30,
                alpha=0.5,
                label=ct,
                edgecolor="black",
                linewidth=0.3,
            )
        ax_resid.axvline(0, color="red", linestyle="--", linewidth=1)
        ax_resid.set_xlabel("Residual (actual - predicted)")
        ax_resid.set_ylabel("Count")
        ax_resid.set_title(f"Residual Distribution: {primary_arm}")
        ax_resid.legend()
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_resid.savefig(
                out / "residual_distribution.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # --- Residuals vs Predicted (standalone) ---
        fig_rvp, ax_rvp = plt.subplots(figsize=(7, 5))
        for ct in ctypes_present:
            mask = all_contracts_arr == ct
            ax_rvp.scatter(
                all_pred_arr[mask],
                all_residuals[mask],
                alpha=0.3,
                s=10,
                label=ct,
            )
        ax_rvp.axhline(0, color="red", linestyle="--", linewidth=1)
        ax_rvp.set_xlabel("Predicted")
        ax_rvp.set_ylabel("Residual (actual - predicted)")
        ax_rvp.set_title(f"Residuals vs Predicted: {primary_arm}")
        ax_rvp.legend()
        ax_rvp.grid(True, alpha=0.3)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_rvp.savefig(
                out / "residual_vs_predicted.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # --- Bootstrap R2 with CIs (skip in SMOKE) ---
        if MODE != "SMOKE" and len(all_y_arr) >= 50:
            boot_rng = np.random.default_rng(SEED)
            n_boot = 1_000 if MODE == "FULL" else 100
            boot_r2 = []
            boot_mae = []
            for _ in range(n_boot):
                idx = boot_rng.integers(0, len(all_y_arr), size=len(all_y_arr))
                y_b, p_b = all_y_arr[idx], all_pred_arr[idx]
                ss_res_b = np.sum((y_b - p_b) ** 2)
                ss_tot_b = np.sum((y_b - y_b.mean()) ** 2)
                boot_r2.append(
                    1 - ss_res_b / ss_tot_b if ss_tot_b > 0 else float("nan")
                )
                boot_mae.append(np.mean(np.abs(y_b - p_b)))

            # Histogram of bootstrap R2
            fig_boot, ax_boot = plt.subplots(figsize=(7, 5))
            ax_boot.hist(
                boot_r2, bins=30, edgecolor="black", alpha=0.7, color="#3498db"
            )
            r2_ci = np.nanpercentile(boot_r2, [2.5, 97.5])
            overall_r2 = 1 - np.sum((all_y_arr - all_pred_arr) ** 2) / np.sum(
                (all_y_arr - all_y_arr.mean()) ** 2
            )
            ax_boot.axvline(
                overall_r2,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"R2={overall_r2:.4f}",
            )
            ax_boot.axvline(
                r2_ci[0],
                color="gray",
                linestyle=":",
                linewidth=1,
                label=f"95% CI [{r2_ci[0]:.4f}, {r2_ci[1]:.4f}]",
            )
            ax_boot.axvline(r2_ci[1], color="gray", linestyle=":", linewidth=1)
            ax_boot.set_xlabel("Bootstrap R2")
            ax_boot.set_ylabel("Count")
            ax_boot.set_title(f"Bootstrap R2 Distribution (n_boot={n_boot})")
            ax_boot.legend(fontsize=9)
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_boot.savefig(out / "bootstrap_r2.png", dpi=150, bbox_inches="tight")
            plt.show()

            mae_ci = np.nanpercentile(boot_mae, [2.5, 97.5])
            overall_mae = np.mean(np.abs(all_y_arr - all_pred_arr))
            print(f"\nOverall R2={overall_r2:.4f} [{r2_ci[0]:.4f}, {r2_ci[1]:.4f}]")
            print(f"Overall MAE={overall_mae:.4f} [{mae_ci[0]:.4f}, {mae_ci[1]:.4f}]")

            # Add CIs to per-contract table
            for pm in per_contract_metrics:
                ct = pm["contract"]
                ct_mask = all_contracts_arr == ct
                if ct_mask.sum() < 10:
                    continue
                yt = all_y_arr[ct_mask]
                yp = all_pred_arr[ct_mask]
                ct_boot_r2 = []
                ct_boot_mae = []
                for _ in range(n_boot):
                    idx = boot_rng.integers(0, len(yt), size=len(yt))
                    ss_r = np.sum((yt[idx] - yp[idx]) ** 2)
                    ss_t = np.sum((yt[idx] - yt[idx].mean()) ** 2)
                    ct_boot_r2.append(1 - ss_r / ss_t if ss_t > 0 else float("nan"))
                    ct_boot_mae.append(np.mean(np.abs(yt[idx] - yp[idx])))
                r2_lo, r2_hi = np.nanpercentile(ct_boot_r2, [2.5, 97.5])
                mae_lo, mae_hi = np.nanpercentile(ct_boot_mae, [2.5, 97.5])
                pm["R2_95CI"] = f"[{r2_lo:.4f}, {r2_hi:.4f}]"
                pm["MAE_95CI"] = f"[{mae_lo:.4f}, {mae_hi:.4f}]"

        # --- Performance table ---
        print("\n=== Per-Contract Performance ===")
        perf_df = pd.DataFrame(per_contract_metrics)
        cols_show = ["contract", "R2", "MAE", "N"]
        if "R2_95CI" in perf_df.columns:
            cols_show.extend(["R2_95CI", "MAE_95CI"])
        print(perf_df[cols_show].to_string(index=False))

        # --- Residual summary table ---
        print("\n=== Residual Summary ===")
        resid_cols = [
            "contract",
            "mean_residual",
            "std_residual",
            "P5_residual",
            "P95_residual",
            "max_abs_residual",
        ]
        resid_cols_present = [c for c in resid_cols if c in perf_df.columns]
        print(perf_df[resid_cols_present].to_string(index=False))
    else:
        print("No predictions generated -- check feature columns.")
else:
    if not _model_artifacts:
        print("No model artifacts loaded -- skipping model performance diagnostics.")
    else:
        print("No data or tricks_won column -- skipping model performance diagnostics.")

# %% [markdown]
# # S3.5 Gaussian Assumption Diagnostics
#
# The HybridOLSa bidder assumes tricks_won ~ Normal(mu, sigma^2).
# Three checks, all faceted by contract_type:
# - (a) Residual skewness/kurtosis by predicted-mu bucket
# - (b) Heteroscedasticity: observed variance vs constant-sigma assumption
# - (c) P(make) calibration: Gaussian-predicted vs observed make rate

# %%
# --- S3.5: Gaussian Assumption Diagnostics ---
print("=" * 60)
print("S3.5: Gaussian Assumption Diagnostics")
print("=" * 60)

# Sample-size constants for gating
_MIN_BUCKET_N = 30  # min samples per mu-bucket for skewness checks
_MIN_CAL_BINS = 3  # min populated bins for MACE gate
_MIN_BIN_N = 20  # min samples per calibration bin
_Z_CAP = 6.0  # matches HybridOLSaBidder._Z_CAP

# Decision-relevant mu midpoint range (bids of 5-8 are most common)
_DECISION_MU_RANGE = (5.0, 8.0)

# mu buckets for residual analysis
_MU_BUCKETS = [(3, 4), (4, 5), (5, 6), (6, 7), (7, 8), (8, 9)]


def _is_decision_relevant(bucket_lo: int, bucket_hi: int) -> bool:
    """Check if a mu bucket overlaps the decision-relevant range."""
    return bucket_lo < _DECISION_MU_RANGE[1] and bucket_hi > _DECISION_MU_RANGE[0]


# Guard: S3 must have produced prediction arrays
_s35_available = False
try:
    _ = all_y_arr  # noqa: F841
    _s35_available = True
except NameError:
    pass

if _model_artifacts and not df.empty and "tricks_won" in df.columns and _s35_available:
    # --- Extract residual_variance from artifact ---
    primary_arm = (
        "olsa_full" if "olsa_full" in _model_artifacts else next(iter(_model_artifacts))
    )
    artifact = _model_artifacts[primary_arm]

    # Handle flat (pre-R5) vs nested (R5+) residual_variance schema
    _rv_raw = artifact.get("residual_variance", {})
    _rv_sigma2 = {}
    _rv_is_nested = False
    for _rv_key, _rv_val in _rv_raw.items():
        if isinstance(_rv_val, dict):
            _rv_is_nested = True
            _rv_sigma2[_rv_key] = _rv_val.get("offensive", 0.0)
        else:
            _rv_sigma2[_rv_key] = float(_rv_val)

    if not _rv_sigma2:
        # Synthetic fallback: use empirical variance per contract
        for ct in sorted(set(all_contracts_arr)):
            mask = all_contracts_arr == ct
            _rv_sigma2[ct] = float(np.var(all_residuals[mask]))
        print(
            "  WARNING: No residual_variance in artifact -- using empirical variance."
        )

    print(f"  Artifact residual_variance (sigma^2): {_rv_sigma2}")
    if _rv_is_nested:
        print("  (nested R5+ schema detected -- using 'offensive' role)")

    # ================================================================
    # (a) Residual Distribution by mu Bucket — faceted by contract_type
    # ================================================================
    print("\n--- (a) Residual Skewness/Kurtosis by mu Bucket ---")

    ctypes_s35 = sorted(set(all_contracts_arr))
    _skew_results = {}  # {ct: [(bucket, n, skew, kurt), ...]}

    for ct in ctypes_s35:
        ct_mask = all_contracts_arr == ct
        ct_pred = all_pred_arr[ct_mask]
        ct_resid = all_residuals[ct_mask]
        ct_rows = []

        for lo, hi in _MU_BUCKETS:
            bucket_mask = (ct_pred >= lo) & (ct_pred < hi)
            n_bucket = int(bucket_mask.sum())
            if n_bucket < 5:
                continue  # too few for any stats

            bucket_resid = ct_resid[bucket_mask]
            if HAS_SCIPY and n_bucket >= 8:
                skew_val = float(scipy_stats.skew(bucket_resid))
                kurt_val = float(scipy_stats.kurtosis(bucket_resid))  # excess
            else:
                skew_val = float("nan")
                kurt_val = float("nan")
            ct_rows.append((lo, hi, n_bucket, skew_val, kurt_val))

        _skew_results[ct] = ct_rows

    # Grid chart: rows=contract_types, cols=mu_buckets, histograms + normal overlay
    n_ct = len(ctypes_s35)
    n_bk = len(_MU_BUCKETS)
    if n_ct > 0 and any(_skew_results.values()):
        fig_skew, axes_skew = plt.subplots(
            n_ct, n_bk, figsize=(3 * n_bk, 3 * n_ct), squeeze=False
        )
        for i_ct, ct in enumerate(ctypes_s35):
            ct_mask = all_contracts_arr == ct
            ct_pred = all_pred_arr[ct_mask]
            ct_resid = all_residuals[ct_mask]

            for j_bk, (lo, hi) in enumerate(_MU_BUCKETS):
                ax = axes_skew[i_ct, j_bk]
                bucket_mask = (ct_pred >= lo) & (ct_pred < hi)
                n_bucket = int(bucket_mask.sum())

                if n_bucket < 5:
                    ax.text(
                        0.5,
                        0.5,
                        f"n={n_bucket}",
                        ha="center",
                        va="center",
                        transform=ax.transAxes,
                        fontsize=9,
                    )
                    ax.set_title(f"mu [{lo},{hi})", fontsize=8)
                    if j_bk == 0:
                        ax.set_ylabel(ct, fontsize=9)
                    continue

                bucket_resid = ct_resid[bucket_mask]
                ax.hist(
                    bucket_resid,
                    bins=min(20, max(5, n_bucket // 5)),
                    density=True,
                    alpha=0.6,
                    edgecolor="black",
                    linewidth=0.3,
                )
                # Normal overlay
                if HAS_SCIPY:
                    x_range = np.linspace(
                        bucket_resid.min() - 0.5, bucket_resid.max() + 0.5, 100
                    )
                    mu_r = np.mean(bucket_resid)
                    std_r = np.std(bucket_resid)
                    if std_r > 0:
                        ax.plot(
                            x_range,
                            scipy_stats.norm.pdf(x_range, mu_r, std_r),
                            "r-",
                            linewidth=1.5,
                            alpha=0.8,
                        )
                ax.set_title(f"mu [{lo},{hi}) n={n_bucket}", fontsize=8)
                if j_bk == 0:
                    ax.set_ylabel(ct, fontsize=9)
                ax.tick_params(labelsize=6)

        fig_skew.suptitle(
            "S3.5(a): Residual Distribution by mu Bucket", fontsize=12, y=1.02
        )
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_skew.savefig(
                out / "gaussian_residual_by_mu_bucket.png",
                dpi=150,
                bbox_inches="tight",
            )
        plt.show()

    # Skewness table output per contract_type
    _skew_flags = []  # collect (ct, bucket, skew, is_decision_relevant) for gating
    for ct in ctypes_s35:
        rows_ct = _skew_results.get(ct, [])
        if not rows_ct:
            print(f"  {ct}: no populated buckets")
            continue
        print(f"\n  {ct}:")
        print(f"    {'Bucket':>10s} {'N':>6s} {'Skew':>8s} {'Kurt':>8s}  Flag")
        for lo, hi, n_b, sk, ku in rows_ct:
            flag = ""
            if n_b >= _MIN_BUCKET_N and not np.isnan(sk):
                if abs(sk) > 1.0:
                    flag = "*** HARD"
                elif abs(sk) > 0.5:
                    flag = "* soft"
                if flag and _is_decision_relevant(lo, hi):
                    flag += " [decision-relevant]"
                _skew_flags.append(
                    (ct, f"[{lo},{hi})", n_b, sk, _is_decision_relevant(lo, hi))
                )
            sk_str = f"{sk:.3f}" if not np.isnan(sk) else "n/a"
            ku_str = f"{ku:.3f}" if not np.isnan(ku) else "n/a"
            print(f"    [{lo},{hi})  {n_b:6d} {sk_str:>8s} {ku_str:>8s}  {flag}")

    # ================================================================
    # (b) Heteroscedasticity Check — faceted by contract_type
    # ================================================================
    print("\n--- (b) Heteroscedasticity Check ---")

    _hetero_results = {}  # {ct: (ratio, bucket_vars)}
    for ct in ctypes_s35:
        ct_mask = all_contracts_arr == ct
        ct_pred = all_pred_arr[ct_mask]
        ct_resid = all_residuals[ct_mask]
        sigma2_artifact = _rv_sigma2.get(ct, 0.0)

        bucket_vars = []
        bucket_labels = []
        for lo, hi in _MU_BUCKETS:
            bucket_mask = (ct_pred >= lo) & (ct_pred < hi)
            n_bucket = int(bucket_mask.sum())
            if n_bucket >= _MIN_BUCKET_N:
                bvar = float(np.var(ct_resid[bucket_mask]))
                bucket_vars.append(bvar)
                bucket_labels.append(f"[{lo},{hi})")

        if len(bucket_vars) >= 2:
            ratio = max(bucket_vars) / max(min(bucket_vars), 1e-12)
            _hetero_results[ct] = (ratio, list(zip(bucket_labels, bucket_vars)))
            flag = " *** WARNING" if ratio > 4.0 else ""
            print(f"  {ct}: variance ratio = {ratio:.2f}{flag}")
            print(f"    artifact sigma^2 = {sigma2_artifact:.4f}")
            for lbl, bv in zip(bucket_labels, bucket_vars):
                print(f"    {lbl}: observed var = {bv:.4f}")
        else:
            print(
                f"  {ct}: insufficient populated buckets for heteroscedasticity check"
            )

    # Heteroscedasticity chart
    if _hetero_results:
        n_ct_h = len(_hetero_results)
        fig_het, axes_het = plt.subplots(
            1, n_ct_h, figsize=(6 * n_ct_h, 4), squeeze=False
        )
        for idx, (ct, (ratio, bvar_data)) in enumerate(sorted(_hetero_results.items())):
            ax = axes_het[0, idx]
            labels = [d[0] for d in bvar_data]
            vars_obs = [d[1] for d in bvar_data]
            sigma2_ref = _rv_sigma2.get(ct, 0.0)

            ax.bar(
                range(len(labels)),
                vars_obs,
                alpha=0.7,
                color="#3498db",
                label="Observed var",
            )
            ax.axhline(
                sigma2_ref,
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"Artifact sigma^2={sigma2_ref:.3f}",
            )
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, fontsize=8, rotation=45)
            ax.set_ylabel("Variance")
            ax.set_title(f"{ct} (ratio={ratio:.2f})")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3, axis="y")

        fig_het.suptitle(
            "S3.5(b): Heteroscedasticity — Observed vs Artifact Variance",
            fontsize=12,
            y=1.02,
        )
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_het.savefig(
                out / "gaussian_heteroscedasticity.png",
                dpi=150,
                bbox_inches="tight",
            )
        plt.show()

    # ================================================================
    # (c) P(make) Calibration — faceted by contract_type (bidder-only)
    # ================================================================
    print("\n--- (c) P(make) Calibration (bidder-only cohort) ---")

    payoff = artifact.get("payoff_model", {})
    _pmake_results = {}  # {ct: {mace, n_bins_populated, bin_data}}

    # Build bidder-only predictions per contract
    if not HAS_SCIPY:
        print("  scipy not available -- skipping P(make) calibration.")
    elif len(df[df["is_bidder"] == True]) == 0:  # noqa: E712
        print("  No bidder rows found -- skipping P(make) calibration.")
    else:
        df_bidder = df[df["is_bidder"] == True].copy()  # noqa: E712
        for ct in sorted(payoff.keys()):
            model = payoff[ct]
            feature_names = model.get("feature_names", [])
            weights_arr = np.array(model.get("weights", []))
            bias = model.get("bias", 0.0)

            if not feature_names or len(weights_arr) == 0:
                continue

            feat_c = [f"feat_{fn}" for fn in feature_names]
            subset = df_bidder[df_bidder["contract_type"] == ct].copy()
            missing = [c for c in feat_c if c not in subset.columns]
            if missing or len(subset) == 0:
                continue

            X_bid = subset[feat_c].values.astype(np.float64)
            y_bid = subset["tricks_won"].values.astype(np.float64)
            mu_bid = X_bid @ weights_arr + bias

            # Replicate bidding.py logic
            bid_n_arr = np.floor(mu_bid).astype(int)

            # Filter to valid bid range [3, 10]
            valid_mask = (bid_n_arr >= 3) & (bid_n_arr <= 10)
            if valid_mask.sum() == 0:
                print(f"  {ct}: no valid bids in [3,10] -- skipping")
                continue

            mu_valid = mu_bid[valid_mask]
            bid_n_valid = bid_n_arr[valid_mask]
            y_valid = y_bid[valid_mask]

            # sigma from artifact
            sigma2_ct = _rv_sigma2.get(ct, 0.0)
            sigma_ct = np.sqrt(max(0.0, sigma2_ct))

            if sigma_ct == 0.0:
                print(f"  {ct}: sigma=0 -- skipping P(make) calibration")
                continue

            # Compute Gaussian P(make) — replicating bidding.py:913-920
            threshold = bid_n_valid - 0.5
            z = (threshold - mu_valid) / sigma_ct
            z = np.clip(z, -_Z_CAP, _Z_CAP)
            p_make_pred = 1.0 - scipy_stats.norm.cdf(z)

            # Actual make: tricks_won >= bid_n (integer comparison)
            actual_make = (y_valid >= bid_n_valid).astype(float)

            # Bin into 10 equal-width bins [0, 1]
            n_cal_bins = 10
            bin_edges = np.linspace(0, 1, n_cal_bins + 1)
            bin_data = []
            for b_idx in range(n_cal_bins):
                b_lo, b_hi = bin_edges[b_idx], bin_edges[b_idx + 1]
                if b_idx == n_cal_bins - 1:
                    b_mask = (p_make_pred >= b_lo) & (p_make_pred <= b_hi)
                else:
                    b_mask = (p_make_pred >= b_lo) & (p_make_pred < b_hi)
                n_in_bin = int(b_mask.sum())
                if n_in_bin > 0:
                    mean_pred_p = float(np.mean(p_make_pred[b_mask]))
                    mean_actual_p = float(np.mean(actual_make[b_mask]))
                else:
                    mean_pred_p = (b_lo + b_hi) / 2.0
                    mean_actual_p = float("nan")
                bin_data.append(
                    {
                        "bin_lo": round(b_lo, 2),
                        "bin_hi": round(b_hi, 2),
                        "n": n_in_bin,
                        "mean_pred_p": round(mean_pred_p, 4),
                        "mean_actual_p": round(mean_actual_p, 4),
                    }
                )

            # MACE: mean absolute calibration error (over populated bins)
            populated = [
                b
                for b in bin_data
                if b["n"] >= _MIN_BIN_N and not np.isnan(b["mean_actual_p"])
            ]
            if populated:
                mace = float(
                    np.mean(
                        [abs(b["mean_actual_p"] - b["mean_pred_p"]) for b in populated]
                    )
                )
            else:
                mace = float("nan")

            _pmake_results[ct] = {
                "mace": mace,
                "n_bins_populated": len(populated),
                "n_total": int(valid_mask.sum()),
                "bin_data": bin_data,
                "p_make_pred": p_make_pred,
                "actual_make": actual_make,
            }

            mace_str = f"{mace:.4f}" if not np.isnan(mace) else "n/a"
            print(
                f"  {ct}: MACE={mace_str}, "
                f"populated_bins={len(populated)}/{n_cal_bins}, "
                f"n={int(valid_mask.sum())}"
            )

        # P(make) calibration chart
        if _pmake_results:
            n_ct_p = len(_pmake_results)
            fig_pmake, axes_pmake = plt.subplots(
                1, n_ct_p, figsize=(6 * n_ct_p, 5), squeeze=False
            )
            for idx, (ct, pdata) in enumerate(sorted(_pmake_results.items())):
                ax = axes_pmake[0, idx]
                bdata = pdata["bin_data"]
                pred_p = [b["mean_pred_p"] for b in bdata if b["n"] > 0]
                act_p = [
                    b["mean_actual_p"]
                    for b in bdata
                    if b["n"] > 0 and not np.isnan(b["mean_actual_p"])
                ]
                pred_p_valid = [
                    b["mean_pred_p"]
                    for b in bdata
                    if b["n"] > 0 and not np.isnan(b["mean_actual_p"])
                ]
                sizes = [
                    b["n"]
                    for b in bdata
                    if b["n"] > 0 and not np.isnan(b["mean_actual_p"])
                ]

                if pred_p_valid and act_p:
                    ax.scatter(
                        pred_p_valid,
                        act_p,
                        s=[max(20, min(200, s * 2)) for s in sizes],
                        alpha=0.7,
                        color="#3498db",
                        edgecolors="black",
                        linewidth=0.5,
                    )
                ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5, label="Perfect")
                ax.set_xlim(-0.05, 1.05)
                ax.set_ylim(-0.05, 1.05)
                ax.set_xlabel("Predicted P(make)")
                ax.set_ylabel("Observed P(make)")
                mace_v = pdata["mace"]
                mace_label = f"{mace_v:.4f}" if not np.isnan(mace_v) else "n/a"
                ax.set_title(f"{ct} (MACE={mace_label}, n={pdata['n_total']})")
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)

            fig_pmake.suptitle(
                "S3.5(c): P(make) Calibration — Gaussian vs Observed",
                fontsize=12,
                y=1.02,
            )
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_pmake.savefig(
                    out / "gaussian_pmake_calibration.png",
                    dpi=150,
                    bbox_inches="tight",
                )
            plt.show()

            # Calibration bin tables
            for ct, pdata in sorted(_pmake_results.items()):
                print(f"\n  {ct} P(make) bins:")
                bdf = pd.DataFrame(pdata["bin_data"])
                print(bdf.to_string(index=False))

    # ================================================================
    # Assert Gates
    # ================================================================
    print("\n--- S3.5 Gate Checks ---")

    _is_real_data = _data_source != "synthetic"
    _is_gated_mode = MODE not in ("SMOKE",)

    # (a) Skewness gate
    _hard_skew_violations = [
        (ct, bk, n, sk)
        for ct, bk, n, sk, dr in _skew_flags
        if abs(sk) > 1.0 and n >= _MIN_BUCKET_N and dr
    ]
    _soft_skew_violations = [
        (ct, bk, n, sk)
        for ct, bk, n, sk, dr in _skew_flags
        if 0.5 < abs(sk) <= 1.0 and n >= _MIN_BUCKET_N
    ]

    if _hard_skew_violations:
        msg = "HARD skewness violations in decision-relevant buckets:\n"
        for ct, bk, n, sk in _hard_skew_violations:
            msg += f"  {ct} {bk}: skew={sk:.3f} (n={n})\n"
        if _is_gated_mode and _is_real_data:
            assert False, msg  # noqa: B011
        else:
            print(
                f"  [SKIPPED — {MODE}/{'synthetic' if not _is_real_data else 'real'}] {msg}"
            )

    if _soft_skew_violations:
        print("  Soft skewness warnings:")
        for ct, bk, n, sk in _soft_skew_violations:
            print(f"    {ct} {bk}: skew={sk:.3f} (n={n})")

    if not _hard_skew_violations and not _soft_skew_violations:
        print("  Skewness: PASS (all |skew| <= 0.5 in gated buckets)")

    # (b) Heteroscedasticity gate
    _hetero_warnings = [
        (ct, ratio) for ct, (ratio, _) in _hetero_results.items() if ratio > 4.0
    ]
    if _hetero_warnings:
        for ct, ratio in _hetero_warnings:
            print(f"  WARNING: {ct} heteroscedasticity ratio = {ratio:.2f} > 4.0")
    else:
        if _hetero_results:
            print("  Heteroscedasticity: PASS (all ratios <= 4.0)")
        else:
            print("  Heteroscedasticity: SKIP (insufficient data)")

    # (c) P(make) MACE gate
    for ct, pdata in sorted(_pmake_results.items()):
        mace = pdata["mace"]
        n_pop = pdata["n_bins_populated"]
        if np.isnan(mace) or n_pop < _MIN_CAL_BINS:
            print(f"  P(make) {ct}: SKIP (populated_bins={n_pop} < {_MIN_CAL_BINS})")
            continue
        if mace > 0.15:
            msg = f"P(make) MACE too high: {ct} MACE={mace:.4f} > 0.15"
            if _is_gated_mode and _is_real_data:
                assert False, msg  # noqa: B011
            else:
                print(
                    f"  [SKIPPED — {MODE}/{'synthetic' if not _is_real_data else 'real'}] {msg}"
                )
        elif mace > 0.10:
            print(f"  P(make) {ct}: marginal (MACE={mace:.4f})")
        else:
            print(f"  P(make) {ct}: PASS (MACE={mace:.4f})")

    # ================================================================
    # Report Generation
    # ================================================================
    def _generate_gaussian_report() -> str:
        """Generate markdown report for Gaussian EV diagnostics."""
        lines = []
        lines.append("# Gaussian EV Assumption Diagnostics\n")
        lines.append(f"**Rung:** {RUNG_ID}")
        lines.append(
            f"**Generated by:** `notebooks/arc_d/{RUNG_ID}/30_feature_outcome_eval.py` (S3.5)"
        )
        lines.append(f"**Mode:** {MODE}")
        lines.append(f"**Data source:** {_data_source}")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("|-------|-------|")
        lines.append(f"| gate_status | INFORMATIONAL ({RUNG_ID} diagnostics) |")
        lines.append("")

        # --- Verdict ---
        max_skew = 0.0
        for ct_rows in _skew_results.values():
            for _, _, n_b, sk, _ in ct_rows:
                if n_b >= _MIN_BUCKET_N and not np.isnan(sk):
                    max_skew = max(max_skew, abs(sk))

        max_ratio = 0.0
        for _, (ratio, _) in _hetero_results.items():
            max_ratio = max(max_ratio, ratio)

        max_mace = 0.0
        for pdata in _pmake_results.values():
            if (
                not np.isnan(pdata["mace"])
                and pdata["n_bins_populated"] >= _MIN_CAL_BINS
            ):
                max_mace = max(max_mace, pdata["mace"])

        if max_skew > 1.0 or max_ratio > 4.0 or max_mace > 0.10:
            verdict = "needs upgrade"
        elif max_skew > 0.5 or max_ratio > 2.0 or max_mace > 0.05:
            verdict = "marginal"
        else:
            verdict = "adequate"

        lines.append(f"## Summary Verdict: **{verdict}**\n")
        lines.append(
            f"- Max |skewness|: {max_skew:.3f} "
            f"({'ok' if max_skew <= 0.5 else 'elevated' if max_skew <= 1.0 else 'HIGH'})"
        )
        lines.append(
            f"- Max variance ratio: {max_ratio:.2f} "
            f"({'ok' if max_ratio <= 2.0 else 'elevated' if max_ratio <= 4.0 else 'HIGH'})"
        )
        lines.append(
            f"- Max MACE: {max_mace:.4f} "
            f"({'ok' if max_mace <= 0.05 else 'elevated' if max_mace <= 0.10 else 'HIGH'})"
        )
        lines.append("")

        # --- Skewness tables ---
        lines.append("## Skewness/Kurtosis by mu Bucket\n")
        for ct in ctypes_s35:
            ct_rows = _skew_results.get(ct, [])
            if not ct_rows:
                continue
            lines.append(f"### {ct}\n")
            lines.append("| Bucket | N | Skewness | Kurtosis | Flag |")
            lines.append("|--------|---|----------|----------|------|")
            for lo, hi, n_b, sk, ku in ct_rows:
                sk_s = f"{sk:.3f}" if not np.isnan(sk) else "n/a"
                ku_s = f"{ku:.3f}" if not np.isnan(ku) else "n/a"
                flag = ""
                if n_b >= _MIN_BUCKET_N and not np.isnan(sk):
                    if abs(sk) > 1.0:
                        flag = "HARD"
                    elif abs(sk) > 0.5:
                        flag = "soft"
                lines.append(f"| [{lo},{hi}) | {n_b} | {sk_s} | {ku_s} | {flag} |")
            lines.append("")

        # --- Heteroscedasticity ---
        lines.append("## Heteroscedasticity Ratios\n")
        lines.append("| Contract | Ratio | Artifact sigma^2 | Status |")
        lines.append("|----------|-------|-------------------|--------|")
        for ct in ctypes_s35:
            if ct in _hetero_results:
                ratio, _ = _hetero_results[ct]
                s2 = _rv_sigma2.get(ct, 0.0)
                status = (
                    "ok" if ratio <= 2.0 else ("warning" if ratio <= 4.0 else "HIGH")
                )
                lines.append(f"| {ct} | {ratio:.2f} | {s2:.4f} | {status} |")
        lines.append("")

        # --- P(make) calibration ---
        lines.append("## P(make) Calibration\n")
        for ct, pdata in sorted(_pmake_results.items()):
            mace = pdata["mace"]
            mace_s = f"{mace:.4f}" if not np.isnan(mace) else "n/a"
            lines.append(f"### {ct} (MACE={mace_s}, n={pdata['n_total']})\n")
            lines.append("| Bin | N | Pred P(make) | Obs P(make) |")
            lines.append("|-----|---|--------------|-------------|")
            for b in pdata["bin_data"]:
                act_s = (
                    f"{b['mean_actual_p']:.4f}"
                    if not np.isnan(b["mean_actual_p"])
                    else "n/a"
                )
                lines.append(
                    f"| [{b['bin_lo']:.2f},{b['bin_hi']:.2f}) "
                    f"| {b['n']} | {b['mean_pred_p']:.4f} | {act_s} |"
                )
            lines.append("")

        # --- Implications ---
        lines.append("## Implications\n")
        if verdict == "adequate":
            lines.append(
                "The Gaussian assumption appears adequate for the current model. "
                "No immediate action required."
            )
        elif verdict == "marginal":
            lines.append(
                "The Gaussian assumption shows some deviations but remains usable. "
                "Monitor these metrics in future rungs. Consider mixture models or "
                "non-parametric approaches if deviations worsen."
            )
        else:
            lines.append(
                "The Gaussian assumption shows significant violations. Consider:\n"
                "- Truncated normal or beta distribution for bounded outcomes\n"
                "- Heteroscedastic models (variance as function of mu)\n"
                "- Non-parametric P(make) estimation\n"
            )
        lines.append("")
        return "\n".join(lines)

    # Write report if conditions met
    if RUNG_ID and MODE != "SMOKE" and _data_source != "synthetic":
        report_dir = Path(f"docs/04_reports/{RUNG_ID}")
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "gaussian_ev_diagnostics.md"
        report_content = _generate_gaussian_report()
        report_path.write_text(report_content)
        print(f"\n  Report written to: {report_path}")
    else:
        reasons = []
        if not RUNG_ID:
            reasons.append("RUNG_ID empty")
        if MODE == "SMOKE":
            reasons.append("SMOKE mode")
        if _data_source == "synthetic":
            reasons.append("synthetic data")
        print(f"\n  Report not written ({', '.join(reasons)})")
        # Still generate for display
        print("\n  --- Report Preview ---")
        print(_generate_gaussian_report())

else:
    if not _s35_available:
        print("  S3 did not produce prediction arrays -- skipping S3.5.")
        print("  (This is expected if model features are missing from the dataset.)")
    elif not _model_artifacts:
        print("  No model artifacts -- skipping Gaussian diagnostics.")
    else:
        print("  Insufficient data -- skipping Gaussian diagnostics.")

# %% [markdown]
# # S4 Dual-Arm Comparison
#
# Side-by-side OLSa vs OLSa_Full: eval metrics, per-contract R2 bars,
# and attribution gap analysis.

# %%
if _model_artifacts and len(_model_artifacts) >= 2 and not df.empty:
    # --- Compute per-contract R2 for each arm ---
    arm_r2_by_contract = {}
    arm_overall_metrics = {}

    for arm_key, artifact in _model_artifacts.items():
        payoff = artifact.get("payoff_model", {})
        r2_by_ct = {}
        arm_y, arm_pred = [], []

        for contract, model in sorted(payoff.items()):
            feature_names = model.get("feature_names", [])
            weights = np.array(model.get("weights", []))
            bias = model.get("bias", 0.0)

            if not feature_names or len(weights) == 0:
                continue

            feat_c = [f"feat_{fn}" for fn in feature_names]
            subset = df[df["contract_type"] == contract].copy()
            missing = [c for c in feat_c if c not in subset.columns]
            if missing or len(subset) == 0:
                continue

            X = subset[feat_c].values.astype(np.float64)
            y_actual = subset["tricks_won"].values.astype(np.float64)
            y_pred_arm = X @ weights + bias

            ss_res = np.sum((y_actual - y_pred_arm) ** 2)
            ss_tot = np.sum((y_actual - y_actual.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
            r2_by_ct[contract] = r2

            arm_y.extend(y_actual)
            arm_pred.extend(y_pred_arm)

        arm_r2_by_contract[arm_key] = r2_by_ct

        # Overall R2
        if arm_y:
            arm_y_arr = np.array(arm_y)
            arm_pred_arr = np.array(arm_pred)
            ss_res_all = np.sum((arm_y_arr - arm_pred_arr) ** 2)
            ss_tot_all = np.sum((arm_y_arr - arm_y_arr.mean()) ** 2)
            arm_overall_metrics[arm_key] = {
                "overall_r2": 1 - ss_res_all / ss_tot_all if ss_tot_all > 0 else np.nan,
                "overall_mae": np.mean(np.abs(arm_y_arr - arm_pred_arr)),
                "r2_by_contract": r2_by_ct,
            }

    # --- Use plot_dual_arm_comparison if eval metrics available ---
    if _eval_available and len(_arm_metrics) >= 2:
        metrics_for_plot = {}
        for arm_key, metrics in _arm_metrics.items():
            arm_dict = {}
            for canonical, alias in METRIC_ALIASES.items():
                val = metrics.get(canonical)
                if val is not None:
                    arm_dict[alias] = val
            if arm_key in arm_r2_by_contract:
                arm_dict["r2_by_contract"] = arm_r2_by_contract[arm_key]
            metrics_for_plot[arm_key] = arm_dict

        try:
            from bid_euchre.diagnostics.model_charts import plot_dual_arm_comparison

            fig_dual = plot_dual_arm_comparison(
                metrics_for_plot,
                title="Dual-Arm Comparison: OLSa vs OLSa_Full",
            )
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_dual.savefig(
                    out / "dual_arm_comparison.png", dpi=150, bbox_inches="tight"
                )
            plt.show()
        except ImportError:
            print("plot_dual_arm_comparison not available -- skipping.")

    # --- Per-contract R2 comparison bar chart ---
    if arm_r2_by_contract:
        arms = list(arm_r2_by_contract.keys())
        all_cts = sorted(
            set().union(*(r2d.keys() for r2d in arm_r2_by_contract.values()))
        )

        if all_cts:
            fig_r2, ax_r2 = plt.subplots(figsize=(8, 5))
            width = 0.35
            x = np.arange(len(all_cts))
            colors_r2 = ["#3498db", "#e67e22", "#2ecc71", "#e74c3c"]

            for i, arm in enumerate(arms):
                r2_vals = [arm_r2_by_contract[arm].get(ct, 0.0) for ct in all_cts]
                bars = ax_r2.bar(
                    x + i * width,
                    r2_vals,
                    width,
                    label=arm,
                    alpha=0.8,
                    color=colors_r2[i % len(colors_r2)],
                )
                for bar, val in zip(bars, r2_vals):
                    ax_r2.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height(),
                        f"{val:.3f}",
                        ha="center",
                        va="bottom",
                        fontsize=8,
                    )

            ax_r2.set_xticks(x + width / 2)
            ax_r2.set_xticklabels(all_cts)
            ax_r2.set_ylabel("R2")
            ax_r2.set_title("Per-Contract R2 Comparison")
            ax_r2.legend()
            ax_r2.grid(True, alpha=0.3, axis="y")
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_r2.savefig(
                    out / "per_contract_r2_comparison.png", dpi=150, bbox_inches="tight"
                )
            plt.show()

    # --- Attribution gap analysis ---
    print("\n=== Attribution Gap Analysis ===")
    if _eval_available and len(_arm_metrics) >= 2:
        full_net = _arm_metrics.get("olsa_full", {}).get("net_expected_points_per_deal")
        base_net = _arm_metrics.get("olsa", {}).get("net_expected_points_per_deal")
        if full_net is not None and base_net is not None:
            attr_gap = round(full_net - base_net, 6)
            sign = (
                "positive (Full > Base)"
                if attr_gap > 0
                else ("negative (Base > Full)" if attr_gap < 0 else "zero")
            )
            print(f"Attribution gap (net_eppd): {attr_gap:.6f} ({sign})")
            print(f"  OLSa_Full net_eppd: {full_net}")
            print(f"  OLSa net_eppd:      {base_net}")
        else:
            print("Cannot compute attribution gap -- need both arms' net_eppd.")

    # --- Arm comparison table ---
    if _eval_available:
        arm_rows = []
        for arm_key, metrics in _arm_metrics.items():
            row = {"arm": arm_key}
            for canonical, alias in METRIC_ALIASES.items():
                row[alias] = metrics.get(canonical)
            arm_rows.append(row)
        df_arms = pd.DataFrame(arm_rows).set_index("arm")
        print("\n=== Arm Comparison Table ===")
        print(df_arms.to_string())

elif _model_artifacts and not df.empty:
    print("Need both arms for dual-arm comparison -- only one arm loaded.")
elif not _model_artifacts:
    print("No model artifacts loaded -- skipping dual-arm comparison.")
else:
    print("No data available -- skipping dual-arm comparison.")

# %% [markdown]
# # S5 Calibration Analysis
#
# Calibration curve (binned predicted vs actual mean) and prediction
# distribution, per contract type.

# %%
if _model_artifacts and not df.empty and "tricks_won" in df.columns:
    # Recompute predictions for all contracts using primary arm
    primary_arm = (
        "olsa_full" if "olsa_full" in _model_artifacts else next(iter(_model_artifacts))
    )
    artifact = _model_artifacts[primary_arm]
    payoff = artifact.get("payoff_model", {})

    cal_y = []
    cal_pred = []
    cal_contracts = []

    for contract, model in sorted(payoff.items()):
        feature_names = model.get("feature_names", [])
        weights = np.array(model.get("weights", []))
        bias = model.get("bias", 0.0)

        if not feature_names or len(weights) == 0:
            continue

        feat_c = [f"feat_{fn}" for fn in feature_names]
        subset = df[df["contract_type"] == contract].copy()
        missing = [c for c in feat_c if c not in subset.columns]
        if missing or len(subset) == 0:
            continue

        X = subset[feat_c].values.astype(np.float64)
        y_actual = subset["tricks_won"].values.astype(np.float64)
        y_pred_cal = X @ weights + bias

        cal_y.extend(y_actual)
        cal_pred.extend(y_pred_cal)
        cal_contracts.extend([contract] * len(y_actual))

    if cal_y:
        cal_y_arr = np.array(cal_y)
        cal_pred_arr = np.array(cal_pred)
        cal_contracts_arr = np.array(cal_contracts)

        # --- Use plot_calibration_curve from diagnostics.model_charts ---
        try:
            from bid_euchre.diagnostics.model_charts import plot_calibration_curve

            fig_cal = plot_calibration_curve(
                cal_y_arr,
                cal_pred_arr,
                cal_contracts_arr,
                title=f"Calibration: {primary_arm}",
            )
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_cal.savefig(
                    out / "calibration_curve.png", dpi=150, bbox_inches="tight"
                )
            plt.show()
        except ImportError:
            # Fallback: manual calibration
            fig_cal, (ax_cal, ax_dist) = plt.subplots(1, 2, figsize=(14, 5))
            ctypes_cal = sorted(set(cal_contracts_arr))

            # Calibration curve
            for ct in ctypes_cal:
                mask = cal_contracts_arr == ct
                yp = cal_pred_arr[mask]
                yt = cal_y_arr[mask]
                if len(yp) < 10:
                    continue
                try:
                    bin_idx = pd.qcut(yp, q=10, labels=False, duplicates="drop")
                    pred_means = [
                        np.mean(yp[bin_idx == b]) for b in sorted(set(bin_idx))
                    ]
                    true_means = [
                        np.mean(yt[bin_idx == b]) for b in sorted(set(bin_idx))
                    ]
                    ax_cal.plot(pred_means, true_means, "o-", label=ct, linewidth=2)
                except ValueError:
                    pass

            lims = [
                min(cal_y_arr.min(), cal_pred_arr.min()),
                max(cal_y_arr.max(), cal_pred_arr.max()),
            ]
            ax_cal.plot(
                lims, lims, "k--", linewidth=1, alpha=0.5, label="Perfect calibration"
            )
            ax_cal.set_xlabel("Mean Predicted")
            ax_cal.set_ylabel("Mean Actual")
            ax_cal.set_title("Calibration Curve")
            ax_cal.legend(fontsize=8)
            ax_cal.grid(True, alpha=0.3)

            # Prediction distribution
            for ct in ctypes_cal:
                mask = cal_contracts_arr == ct
                ax_dist.hist(
                    cal_pred_arr[mask],
                    bins=30,
                    alpha=0.5,
                    label=ct,
                    edgecolor="black",
                    linewidth=0.3,
                )
            ax_dist.set_xlabel("Predicted Value")
            ax_dist.set_ylabel("Count")
            ax_dist.set_title("Prediction Distribution")
            ax_dist.legend(fontsize=8)

            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_cal.savefig(
                    out / "calibration_curve.png", dpi=150, bbox_inches="tight"
                )
            plt.show()

        # --- Standalone prediction distribution ---
        fig_pdist, ax_pdist = plt.subplots(figsize=(7, 5))
        ctypes_cal = sorted(set(cal_contracts_arr))
        for ct in ctypes_cal:
            mask = cal_contracts_arr == ct
            ax_pdist.hist(
                cal_pred_arr[mask],
                bins=30,
                alpha=0.5,
                label=ct,
                edgecolor="black",
                linewidth=0.3,
            )
        ax_pdist.set_xlabel("Predicted Value")
        ax_pdist.set_ylabel("Count")
        ax_pdist.set_title(f"Prediction Distribution: {primary_arm}")
        ax_pdist.legend()
        ax_pdist.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_pdist.savefig(
                out / "prediction_distribution.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # --- Calibration bins table ---
        print("\n=== Calibration Bins ===")
        n_bins = 10
        for ct in ctypes_cal:
            mask = cal_contracts_arr == ct
            yp = cal_pred_arr[mask]
            yt = cal_y_arr[mask]
            if len(yp) < n_bins:
                continue
            try:
                bin_idx = pd.qcut(yp, q=n_bins, labels=False, duplicates="drop")
                bin_rows = []
                for b in sorted(set(bin_idx)):
                    b_mask = bin_idx == b
                    bin_rows.append(
                        {
                            "bin": b,
                            "N": int(b_mask.sum()),
                            "pred_lo": round(yp[b_mask].min(), 3),
                            "pred_hi": round(yp[b_mask].max(), 3),
                            "mean_pred": round(np.mean(yp[b_mask]), 4),
                            "mean_actual": round(np.mean(yt[b_mask]), 4),
                            "deviation": round(
                                np.mean(yt[b_mask]) - np.mean(yp[b_mask]), 4
                            ),
                        }
                    )
                print(f"\n--- {ct} ---")
                print(pd.DataFrame(bin_rows).to_string(index=False))
            except ValueError:
                print(f"\n--- {ct}: insufficient unique values for binning ---")
    else:
        print("No predictions available for calibration analysis.")
else:
    print("No model artifacts or data -- skipping calibration analysis.")

# %% [markdown]
# # S6 Rung-Specific Analysis
#
# This section is intentionally left as a placeholder.
# When copying this template for a specific rung (e.g., R0, R1a),
# add rung-specific analysis here:
#
# Examples for R0:
#   - Compare OLSa predictions to Phase 0 Ridge diagnostic
#   - Feature selection justification (why these 3/1/1 features?)
#   - Comparator landscape from comparator_battery_r0.json
#   - Attribution gap investigation (gap = -0.1437)
#   - Seed sensitivity across 42/43/44
#
# Examples for R1a+:
#   - Auction dataset quality checks
#   - Comparison with previous rung's model
#   - Feature stability analysis across rungs

# %%
print("S6 is a placeholder -- fill when copying template for a specific rung.")

# %% [markdown]
# # S7 Summary & Promotion Readiness
#
# Overall assessment combining feature health, outcome health,
# and model diagnostics. Gate check summary and promotion recommendation.

# %%
print("=" * 60)
print("S7: Summary & Promotion Readiness")
print("=" * 60)

# --- Feature health summary ---
if not df.empty and feat_cols:
    numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]
    n_feats = len(numeric_feats)
    n_nan = sum(df[c].isna().any() for c in numeric_feats)
    n_zero_var = sum(df[c].var() == 0 for c in numeric_feats if df[c].notna().sum() > 1)
    print("\nFeature Health:")
    print(f"  Total features: {n_feats}")
    print(f"  Features with NaN: {n_nan}")
    print(f"  Zero-variance features: {n_zero_var}")
    if n_nan > 0:
        print(f"  WARNING: {n_nan} features have missing values")
    if n_zero_var > 0:
        print(f"  WARNING: {n_zero_var} features have zero variance")

# --- Outcome health summary ---
if not df.empty and "tricks_won" in df.columns:
    print("\nOutcome Health:")
    print(f"  tricks_won range: [{df['tricks_won'].min()}, {df['tricks_won'].max()}]")
    print(f"  tricks_won mean: {df['tricks_won'].mean():.2f}")
    if "contract_type" in df.columns:
        for ct in sorted(df["contract_type"].unique()):
            grp = df[df["contract_type"] == ct]
            print(
                f"  {ct}: mean={grp['tricks_won'].mean():.2f}, "
                f"std={grp['tricks_won'].std():.2f}, n={len(grp)}"
            )

# --- Model diagnostics summary ---
if _model_artifacts:
    print("\nModel Diagnostics:")
    print(f"  Arms loaded: {list(_model_artifacts.keys())}")
    for arm_key, artifact in _model_artifacts.items():
        payoff = artifact.get("payoff_model", {})
        n_contracts = len(payoff)
        total_features = sum(len(m.get("feature_names", [])) for m in payoff.values())
        print(
            f"  {arm_key}: {n_contracts} contracts, "
            f"{total_features} total feature slots"
        )

# --- Gate check summary ---
if _eval_available:
    print("\nEval Metrics Summary:")
    for arm_key, metrics in _arm_metrics.items():
        net_eppd = metrics.get("net_expected_points_per_deal")
        make_rate = metrics.get("make_rate")
        bid_rate = metrics.get("bid_rate")
        print(
            f"  {arm_key}: net_eppd={net_eppd}, "
            f"make_rate={make_rate}, bid_rate={bid_rate}"
        )

    # Attribution gap
    full_net = _arm_metrics.get("olsa_full", {}).get("net_expected_points_per_deal")
    base_net = _arm_metrics.get("olsa", {}).get("net_expected_points_per_deal")
    if full_net is not None and base_net is not None:
        attr_gap = round(full_net - base_net, 6)
        print(f"\n  Attribution gap: {attr_gap:.6f}")

# --- Limitations ---
print("\nKey Limitations:")
print(f"  MODE={MODE} (max_deals={max_deals})")
print(f"  Data source: {_data_source}")
if _data_source == "synthetic":
    print(
        "  WARNING: Using synthetic data -- results are for template validation only."
    )
if MODE == "SMOKE":
    print("  WARNING: SMOKE mode -- sample size too small for statistical inference.")
    print("  Re-run in QUICK (2K deals) or FULL (50K deals) mode for real analysis.")

# --- Promotion recommendation ---
print("\nPromotion Recommendation:")
if not _eval_available:
    print("  Cannot assess -- no eval metrics loaded.")
    print("  Run model evaluation first, then re-execute this notebook.")
elif _data_source == "synthetic":
    print("  Cannot assess -- using synthetic data.")
    print("  Load real eval logs to generate promotion recommendation.")
else:
    print("  Review all sections above before making a promotion decision.")
    print("  Key checks:")
    print("    1. Feature-outcome correlations plausible (S1)")
    print("    2. Model coefficients interpretable (S2)")
    print("    3. R2 and residuals acceptable (S3)")
    print("    4. Dual-arm comparison reasonable (S4)")
    print("    5. Calibration adequate (S5)")
    print("    6. Rung-specific analysis complete (S6)")
