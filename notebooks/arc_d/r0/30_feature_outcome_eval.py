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
# - This is the R0 rung-specific instance (copied from template, with R0-specific S6 analysis).
# - Edit the `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).

# %% tags=["parameters"]
EVAL_LOG_PATH = "data/runs/arc_d_eval_r0_42_20260221_180253"
ARTIFACT_DIR = "data/artifacts/arc_d/r0"
MODE = "QUICK"
RUNG_ID = "r0"
CHART_OUTPUT_DIR = ""
SEED = 42

# %% [markdown]
# # S0 Configuration & Data Loading
#
# Load evaluation logs (JSONL primary, synthetic fallback), artifact bundles,
# and eval metrics. Establishes all data dependencies for subsequent sections.

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
import json
import warnings

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

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
# C2: MODE fallback with warning
_max_deals = MODE_DEAL_COUNTS.get(MODE, 30)
if MODE not in MODE_DEAL_COUNTS:
    warnings.warn(f"Unknown MODE={MODE!r}, defaulting to 30 deals", stacklevel=2)

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
            df = build_eval_dataset(str(eval_log), max_deals=_max_deals)
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
    n_deals = _max_deals or 30
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
        _winning_bid = int(rng.integers(5, 11))
        _made = bool(rng.random() > 0.3)
        for seat in range(4):
            team = 0 if seat in (0, 2) else 1
            tricks = t0 if seat in (0, 2) else t1
            # Compute points_won using scoring semantics
            if _made or team == 1:
                points = tricks
            else:
                points = -_winning_bid
            row = {
                "deal_id": deal_id,
                "hand_id": deal_id,
                "seat": seat,
                "team": team,
                "contract_type": contract,
                "trump": trump,
                "tricks_won": tricks,
                "points_won": points,
                "is_bidder": seat == 0,
                "is_declaring_team": team == 0,
                "winning_bid": _winning_bid,
                "made_bid": _made,
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

# C22: Run metadata summary
feat_cols = [c for c in df.columns if c.startswith("feat_")]
print("=" * 60)
print("RUN METADATA")
print("=" * 60)
print(f"  Data source:    {_data_source}")
print(f"  Eval log path:  {EVAL_LOG_PATH or 'N/A (synthetic)'}")
print(f"  Artifact dir:   {ARTIFACT_DIR or 'N/A'}")
print(f"  Rung:           {RUNG_ID}")
print(f"  Mode:           {MODE} (max_deals={_max_deals})")
print(f"  Seed:           {SEED}")
print(f"  Total deals:    {df['deal_id'].nunique():,}")
print(f"  Total rows:     {len(df):,} (4 per deal)")
print(f"  Feature columns: {len(feat_cols)}")
if _model_artifacts:
    print(f"  Arms loaded:    {list(_model_artifacts.keys())}")
if "contract_type" in df.columns:
    ct_counts = df.drop_duplicates("deal_id")["contract_type"].value_counts()
    print(f"  Contract types: {dict(ct_counts)}")

# %% [markdown]
# ## Fail-Fast Validation
#
# Assert-style checks on loaded data to catch pipeline issues early.
# All checks must pass before proceeding to model analysis.

# %%
# C6: Fail-fast validation
_validation_results = []

# Check 1: tricks_won in valid range [0, 10]
_range_ok = df["tricks_won"].between(0, 10).all()
_validation_results.append(
    {"check": "tricks_won range [0,10]", "status": "PASS" if _range_ok else "FAIL"}
)
assert _range_ok, f"tricks_won out of range: {df['tricks_won'].describe()}"

# Check 2: team0 + team1 tricks == 10 (zero-sum per deal)
_deal_tricks = df.groupby("deal_id").apply(
    lambda g: g.drop_duplicates("team")["tricks_won"].sum()
)
_zerosum_ok = (_deal_tricks == 10).all()
_validation_results.append(
    {"check": "zero-sum (t0+t1=10)", "status": "PASS" if _zerosum_ok else "FAIL"}
)
assert _zerosum_ok, "Zero-sum violation detected"

# Check 3: no missing contract_type
_ct_ok = df["contract_type"].notna().all()
_validation_results.append(
    {"check": "no missing contract_type", "status": "PASS" if _ct_ok else "FAIL"}
)
assert _ct_ok, f"Missing contract_type: {df['contract_type'].isna().sum()} nulls"

# Check 4: no missing tricks_won
_tw_ok = df["tricks_won"].notna().all()
_validation_results.append(
    {"check": "no missing tricks_won", "status": "PASS" if _tw_ok else "FAIL"}
)
assert _tw_ok, f"Missing tricks_won: {df['tricks_won'].isna().sum()} nulls"

# Check 5: feature columns present
_feat_ok = len(feat_cols) > 0
_validation_results.append(
    {
        "check": f"feat_* columns present ({len(feat_cols)})",
        "status": "PASS" if _feat_ok else "FAIL",
    }
)
assert _feat_ok, "No feat_* columns found"

print("=== Fail-Fast Validation ===")
for r in _validation_results:
    print(f"  [{r['status']}] {r['check']}")
print(f"\nAll {len(_validation_results)} checks passed.")

# %% [markdown]
# ## Balance & Symmetry Check
#
# Verify team balance across contract types before model analysis.
# Detects systematic team bias that would confound feature-outcome analysis.

# %%
# C12: Balance/symmetry check
print("=== Team Balance by Contract Type ===")
if "contract_type" in df.columns and "team" in df.columns:
    for ct in sorted(df["contract_type"].unique()):
        subset = df[df["contract_type"] == ct]
        t0 = subset[subset["team"] == 0]["tricks_won"]
        t1 = subset[subset["team"] == 1]["tricks_won"]
        if len(t0) >= 2 and len(t1) >= 2:
            if HAS_SCIPY:
                stat, p_val = scipy_stats.mannwhitneyu(t0, t1, alternative="two-sided")
                print(
                    f"  {ct}: team0={t0.mean():.3f}, "
                    f"team1={t1.mean():.3f}, MWU p={p_val:.4f}"
                )
            else:
                print(
                    f"  {ct}: team0={t0.mean():.3f}, "
                    f"team1={t1.mean():.3f} (scipy not available for MWU test)"
                )
        else:
            print(f"  {ct}: insufficient data for balance check")
else:
    print("  Missing contract_type or team column -- skipping.")

# %% [markdown]
# # S1 Feature-Outcome Correlations
#
# Per-contract Pearson correlation of each feature with tricks_won.
# Faceted by contract_type as required by the contract-type faceting rule.
# Includes declaring/defending split and dual-target (tricks + points) analysis.

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

        # C23-T2: Feature x points_won heatmap
        if "points_won" in df.columns:
            pts_corr_data = {}
            for ct in ctypes:
                grp = df[df["contract_type"] == ct]
                ct_pts_corrs = {}
                for fc in feat_cols:
                    if pd.api.types.is_numeric_dtype(grp[fc]):
                        valid = grp[fc].notna() & grp["points_won"].notna()
                        if valid.sum() > 2:
                            ct_pts_corrs[fc] = grp.loc[valid, fc].corr(
                                grp.loc[valid, "points_won"]
                            )
                        else:
                            ct_pts_corrs[fc] = np.nan
                pts_corr_data[ct] = ct_pts_corrs

            pts_corr_df = pd.DataFrame(pts_corr_data)
            pts_corr_df.index = [c.replace("feat_", "") for c in pts_corr_df.index]

            fig_pts, ax_pts = plt.subplots(figsize=(8, max(4, len(pts_corr_df) * 0.35)))
            vmax_pts = max(abs(pts_corr_df.min().min()), abs(pts_corr_df.max().max()))
            vmax_pts = max(vmax_pts, 0.1)
            im_pts = ax_pts.imshow(
                pts_corr_df.values,
                aspect="auto",
                cmap="RdBu_r",
                vmin=-vmax_pts,
                vmax=vmax_pts,
            )
            ax_pts.set_xticks(range(len(ctypes)))
            ax_pts.set_xticklabels(ctypes)
            ax_pts.set_yticks(range(len(pts_corr_df)))
            ax_pts.set_yticklabels(pts_corr_df.index, fontsize=8)
            ax_pts.set_title("Feature-Outcome Correlation (Pearson r vs points_won)")
            plt.colorbar(im_pts, ax=ax_pts, label="Pearson r")
            for i in range(len(pts_corr_df)):
                for j in range(len(ctypes)):
                    val = pts_corr_df.iloc[i, j]
                    if not np.isnan(val):
                        color = "white" if abs(val) > vmax_pts * 0.6 else "black"
                        ax_pts.text(
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
                fig_pts.savefig(
                    out / "feature_points_won_heatmap.png",
                    dpi=150,
                    bbox_inches="tight",
                )
            plt.show()

        # C23-T2: Declaring/defending split heatmaps
        if "is_declaring_team" in df.columns:
            for role_label, role_val in [("Declaring", True), ("Defending", False)]:
                role_df = df[df["is_declaring_team"] == role_val]
                role_corr_data = {}
                for ct in ctypes:
                    grp = role_df[role_df["contract_type"] == ct]
                    ct_role_corrs = {}
                    for fc in feat_cols:
                        if pd.api.types.is_numeric_dtype(grp[fc]):
                            valid = grp[fc].notna() & grp["tricks_won"].notna()
                            if valid.sum() > 2:
                                ct_role_corrs[fc] = grp.loc[valid, fc].corr(
                                    grp.loc[valid, "tricks_won"]
                                )
                            else:
                                ct_role_corrs[fc] = np.nan
                    role_corr_data[ct] = ct_role_corrs

                role_corr_df = pd.DataFrame(role_corr_data)
                if role_corr_df.empty:
                    continue
                role_corr_df.index = [
                    c.replace("feat_", "") for c in role_corr_df.index
                ]

                fig_role, ax_role = plt.subplots(
                    figsize=(8, max(4, len(role_corr_df) * 0.35))
                )
                vmax_role = max(
                    abs(role_corr_df.min().min()), abs(role_corr_df.max().max())
                )
                vmax_role = max(vmax_role, 0.1)
                im_role = ax_role.imshow(
                    role_corr_df.values,
                    aspect="auto",
                    cmap="RdBu_r",
                    vmin=-vmax_role,
                    vmax=vmax_role,
                )
                ax_role.set_xticks(range(len(ctypes)))
                ax_role.set_xticklabels(ctypes)
                ax_role.set_yticks(range(len(role_corr_df)))
                ax_role.set_yticklabels(role_corr_df.index, fontsize=8)
                ax_role.set_title(
                    f"Feature-Outcome Correlation ({role_label}, Pearson r vs tricks_won)"
                )
                plt.colorbar(im_role, ax=ax_role, label="Pearson r")
                for i in range(len(role_corr_df)):
                    for j in range(len(ctypes)):
                        val = role_corr_df.iloc[i, j]
                        if not np.isnan(val):
                            color = "white" if abs(val) > vmax_role * 0.6 else "black"
                            ax_role.text(
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
                    fig_role.savefig(
                        out / f"feature_outcome_heatmap_{role_label.lower()}.png",
                        dpi=150,
                        bbox_inches="tight",
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
                            "p_value": (
                                round(p_val, 6) if not np.isnan(p_val) else None
                            ),
                            "n": n_valid,
                        }
                    )
            if rows_table:
                tbl = pd.DataFrame(rows_table).sort_values(
                    "pearson_r", key=abs, ascending=False
                )
                print(tbl.to_string(index=False))

        # C23-T2: Dual-target correlation (features x points_won)
        if "points_won" in df.columns:
            print("\n=== Feature x points_won Correlation (per contract type) ===")
            for ct in ctypes:
                grp = df[df["contract_type"] == ct]
                print(f"\n--- {ct} (n={len(grp)}) ---")
                pts_rows = []
                for fc in feat_cols:
                    if not pd.api.types.is_numeric_dtype(grp[fc]):
                        continue
                    valid = grp[fc].notna() & grp["points_won"].notna()
                    n_valid = valid.sum()
                    if n_valid > 2:
                        r_val = grp.loc[valid, fc].corr(grp.loc[valid, "points_won"])
                        if HAS_SCIPY:
                            _, p_val = scipy_stats.pearsonr(
                                grp.loc[valid, fc], grp.loc[valid, "points_won"]
                            )
                        else:
                            p_val = np.nan
                        pts_rows.append(
                            {
                                "feature": fc.replace("feat_", ""),
                                "pearson_r": round(r_val, 4),
                                "p_value": (
                                    round(p_val, 6) if not np.isnan(p_val) else None
                                ),
                                "n": n_valid,
                            }
                        )
                if pts_rows:
                    tbl_pts = pd.DataFrame(pts_rows).sort_values(
                        "pearson_r", key=abs, ascending=False
                    )
                    print(tbl_pts.to_string(index=False))

        # C23-T2: Declaring vs defending split
        if "is_declaring_team" in df.columns:
            for role_label, role_val in [("declaring", True), ("defending", False)]:
                print(f"\n=== Feature-Outcome Correlations ({role_label}) ===")
                role_df = df[df["is_declaring_team"] == role_val]
                for ct in ctypes:
                    grp = role_df[role_df["contract_type"] == ct]
                    if len(grp) < 5:
                        continue
                    print(f"\n--- {ct} / {role_label} (n={len(grp)}) ---")
                    role_rows = []
                    for fc in feat_cols:
                        if not pd.api.types.is_numeric_dtype(grp[fc]):
                            continue
                        valid = grp[fc].notna() & grp["tricks_won"].notna()
                        n_valid = valid.sum()
                        if n_valid > 2:
                            r_val = grp.loc[valid, fc].corr(
                                grp.loc[valid, "tricks_won"]
                            )
                            role_rows.append(
                                {
                                    "feature": fc.replace("feat_", ""),
                                    "pearson_r": round(r_val, 4),
                                    "n": n_valid,
                                }
                            )
                    if role_rows:
                        tbl_role = pd.DataFrame(role_rows).sort_values(
                            "pearson_r", key=abs, ascending=False
                        )
                        print(tbl_role.to_string(index=False))
    else:
        print("No contract_type column -- skipping faceted correlation analysis.")
else:
    print("Insufficient data for feature-outcome correlations.")

# %% [markdown]
# # S2 Model Specification
#
# Feature selection and coefficient display for each model arm,
# faceted by contract type. Includes statsmodels OLS summary tables
# (with std errors, t-stats, p-values, CIs) and side-by-side coefficient
# comparison of OLSa vs OLSa_Full.

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

    # C34: statsmodels OLS summary tables (display-only refit)
    try:
        import statsmodels.api as sm

        for arm_key, artifact in _model_artifacts.items():
            payoff = artifact.get("payoff_model", {})
            for contract, model in sorted(payoff.items()):
                feat_names = model.get("feature_names", [])
                if not feat_names:
                    continue
                contract_df = df[df["contract_type"] == contract]
                feat_c = [f"feat_{fn}" for fn in feat_names]
                missing = [c for c in feat_c if c not in contract_df.columns]
                if missing or len(contract_df) < len(feat_names) + 2:
                    continue
                X = contract_df[feat_c].values.astype(np.float64)
                X_const = sm.add_constant(X)
                y = contract_df["tricks_won"].values.astype(np.float64)
                try:
                    result = sm.OLS(y, X_const).fit()
                    print(f"\n{'=' * 60}")
                    print(f"OLS Summary: {arm_key} / {contract}")
                    print(f"{'=' * 60}")
                    print(result.summary(xname=["const"] + list(feat_names)))
                except Exception as e:
                    print(f"  Could not fit {arm_key}/{contract}: {e}")
    except ImportError:
        print("statsmodels not available -- skipping OLS summary tables.")

    # --- Coefficient comparison: OLSa vs OLSa_Full ---
    if len(_model_artifacts) >= 2:
        arm_keys = list(_model_artifacts.keys())
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
                    out / "coefficient_comparison.png",
                    dpi=150,
                    bbox_inches="tight",
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
# and bootstrap R2/MAE confidence intervals. All charts faceted by contract
# type into separate panels, with pooled summary retained for overview.

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
        all_residuals = all_y_arr - all_pred_arr

        # --- Pooled model diagnostics (summary overview) ---
        try:
            from bid_euchre.diagnostics.model_charts import plot_model_diagnostics

            fig_diag = plot_model_diagnostics(
                all_y_arr,
                all_pred_arr,
                all_contracts_arr,
                title=f"Model Diagnostics (pooled): {primary_arm}",
            )
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_diag.savefig(
                    out / "pred_vs_actual_scatter.png",
                    dpi=150,
                    bbox_inches="tight",
                )
            plt.show()
        except ImportError:
            fig_s, ax_s = plt.subplots(figsize=(6, 5))
            ax_s.scatter(all_y_arr, all_pred_arr, alpha=0.3, s=5)
            lims = [
                min(all_y_arr.min(), all_pred_arr.min()),
                max(all_y_arr.max(), all_pred_arr.max()),
            ]
            ax_s.plot(lims, lims, "r--", linewidth=1, label="y=x")
            ax_s.set_xlabel("Actual Tricks Won")
            ax_s.set_ylabel("Predicted Tricks Won")
            ax_s.set_title(f"Pred vs Actual (pooled): {primary_arm}")
            ax_s.legend()
            plt.tight_layout()
            plt.show()

        # C35: Faceted diagnostics by contract type
        ctypes_present = sorted(set(all_contracts_arr))

        # --- Faceted Pred vs Actual scatter ---
        n_ct = len(ctypes_present)
        fig_fpa, axes_fpa = plt.subplots(1, n_ct, figsize=(6 * n_ct, 5), sharey=True)
        if not hasattr(axes_fpa, "__len__"):
            axes_fpa = [axes_fpa]
        for ax_f, ct in zip(axes_fpa, ctypes_present):
            mask = all_contracts_arr == ct
            ax_f.scatter(
                all_y_arr[mask], all_pred_arr[mask], alpha=0.3, s=10, color="#3498db"
            )
            lims_ct = [
                min(all_y_arr[mask].min(), all_pred_arr[mask].min()),
                max(all_y_arr[mask].max(), all_pred_arr[mask].max()),
            ]
            ax_f.plot(lims_ct, lims_ct, "r--", linewidth=1, label="y=x")
            ax_f.set_xlabel("Actual Tricks Won")
            ax_f.set_ylabel("Predicted Tricks Won")
            ax_f.set_title(f"Pred vs Actual: {ct}")
            ax_f.legend(fontsize=8)
            ax_f.grid(True, alpha=0.3)
        plt.suptitle(f"Per-Contract Pred vs Actual: {primary_arm}", y=1.02)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_fpa.savefig(
                out / "pred_vs_actual_faceted.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # --- Faceted Residual distribution ---
        fig_frd, axes_frd = plt.subplots(1, n_ct, figsize=(6 * n_ct, 5), sharey=True)
        if not hasattr(axes_frd, "__len__"):
            axes_frd = [axes_frd]
        for ax_f, ct in zip(axes_frd, ctypes_present):
            mask = all_contracts_arr == ct
            ax_f.hist(
                all_residuals[mask],
                bins=30,
                alpha=0.7,
                color="#3498db",
                edgecolor="black",
                linewidth=0.3,
            )
            ax_f.axvline(0, color="red", linestyle="--", linewidth=1)
            ax_f.set_xlabel("Residual (actual - predicted)")
            ax_f.set_ylabel("Count")
            ax_f.set_title(f"Residuals: {ct}")
        plt.suptitle(f"Per-Contract Residual Distribution: {primary_arm}", y=1.02)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_frd.savefig(
                out / "residual_distribution_faceted.png",
                dpi=150,
                bbox_inches="tight",
            )
        plt.show()

        # --- Faceted Residuals vs Predicted ---
        fig_frvp, axes_frvp = plt.subplots(1, n_ct, figsize=(6 * n_ct, 5), sharey=True)
        if not hasattr(axes_frvp, "__len__"):
            axes_frvp = [axes_frvp]
        for ax_f, ct in zip(axes_frvp, ctypes_present):
            mask = all_contracts_arr == ct
            ax_f.scatter(
                all_pred_arr[mask],
                all_residuals[mask],
                alpha=0.3,
                s=10,
                color="#3498db",
            )
            ax_f.axhline(0, color="red", linestyle="--", linewidth=1)
            ax_f.set_xlabel("Predicted")
            ax_f.set_ylabel("Residual")
            ax_f.set_title(f"Resid vs Pred: {ct}")
            ax_f.grid(True, alpha=0.3)
        plt.suptitle(f"Per-Contract Residuals vs Predicted: {primary_arm}", y=1.02)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_frvp.savefig(
                out / "residual_vs_predicted_faceted.png",
                dpi=150,
                bbox_inches="tight",
            )
        plt.show()

        # --- Bootstrap R2 with CIs (skip in SMOKE) ---
        if MODE != "SMOKE" and len(all_y_arr) >= 50:
            boot_rng = np.random.default_rng(SEED)
            n_boot = 1_000 if MODE == "FULL" else 100

            # C35: Faceted bootstrap R2 per contract type
            for ct in ctypes_present:
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

                ss_res_ct = np.sum((yt - yp) ** 2)
                ss_tot_ct = np.sum((yt - yt.mean()) ** 2)
                r2_ct = 1 - ss_res_ct / ss_tot_ct if ss_tot_ct > 0 else float("nan")
                r2_ci_ct = np.nanpercentile(ct_boot_r2, [2.5, 97.5])
                mae_ci_ct = np.nanpercentile(ct_boot_mae, [2.5, 97.5])

                print(
                    f"[{ct}] R2={r2_ct:.4f} "
                    f"[{r2_ci_ct[0]:.4f}, {r2_ci_ct[1]:.4f}], "
                    f"MAE={np.mean(np.abs(yt - yp)):.4f} "
                    f"[{mae_ci_ct[0]:.4f}, {mae_ci_ct[1]:.4f}]"
                )

                # Update per_contract_metrics with CIs
                for pm in per_contract_metrics:
                    if pm["contract"] == ct:
                        pm["R2_95CI"] = f"[{r2_ci_ct[0]:.4f}, {r2_ci_ct[1]:.4f}]"
                        pm["MAE_95CI"] = f"[{mae_ci_ct[0]:.4f}, {mae_ci_ct[1]:.4f}]"

            # Pooled bootstrap R2
            boot_rng_pooled = np.random.default_rng(SEED + 1)
            boot_r2 = []
            for _ in range(n_boot):
                idx = boot_rng_pooled.integers(0, len(all_y_arr), size=len(all_y_arr))
                y_b, p_b = all_y_arr[idx], all_pred_arr[idx]
                ss_res_b = np.sum((y_b - p_b) ** 2)
                ss_tot_b = np.sum((y_b - y_b.mean()) ** 2)
                boot_r2.append(
                    1 - ss_res_b / ss_tot_b if ss_tot_b > 0 else float("nan")
                )

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
            ax_boot.set_title(f"Bootstrap R2 Distribution (pooled, n_boot={n_boot})")
            ax_boot.legend(fontsize=9)
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_boot.savefig(out / "bootstrap_r2.png", dpi=150, bbox_inches="tight")
            plt.show()

            overall_mae = np.mean(np.abs(all_y_arr - all_pred_arr))
            print(f"\nOverall R2={overall_r2:.4f} [{r2_ci[0]:.4f}, {r2_ci[1]:.4f}]")
            print(f"Overall MAE={overall_mae:.4f}")

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
# # S4 Dual-Arm Comparison
#
# Side-by-side OLSa vs OLSa_Full: eval metrics, attribution gap analysis,
# and arm comparison table. R2 is computed from regression fit on this
# notebook's eval data; all other metrics (net_eppd, make_rate, etc.)
# come from simulation evaluation runs loaded in S0.

# %% [markdown]
# ### Metric Glossary
#
# | Metric | Definition | Source |
# |--------|-----------|--------|
# | net_eppd | Net expected points per deal (bidder - opponent) | Simulation eval |
# | eppd | Expected points per deal (bidder team only) | Simulation eval |
# | bid_rate | Fraction of deals where bidder chose to bid | Simulation eval |
# | make_rate | Fraction of bid deals where declaring team made bid | Simulation eval |
# | cvar_5 | Average points in worst 5% of deals (tail risk) | Simulation eval |
# | downside_variance | Variance of points in deals where bidder was set | Simulation eval |
# | R2 | Variance explained in tricks_won by model predictions | Notebook-computed |
# | attribution_gap | net_eppd(OLSa_Full) - net_eppd(OLSa) | Derived |

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
                "overall_r2": (
                    1 - ss_res_all / ss_tot_all if ss_tot_all > 0 else np.nan
                ),
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
            from bid_euchre.diagnostics.model_charts import (
                plot_dual_arm_comparison,
            )

            fig_dual = plot_dual_arm_comparison(
                metrics_for_plot,
                title="Dual-Arm Comparison: OLSa vs OLSa_Full",
            )
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_dual.savefig(
                    out / "dual_arm_comparison.png",
                    dpi=150,
                    bbox_inches="tight",
                )
            plt.show()
        except ImportError:
            print("plot_dual_arm_comparison not available -- skipping.")

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
# distribution faceted by contract type with actual tricks_won overlay.

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
                    out / "calibration_curve.png",
                    dpi=150,
                    bbox_inches="tight",
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
                lims,
                lims,
                "k--",
                linewidth=1,
                alpha=0.5,
                label="Perfect calibration",
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
                    out / "calibration_curve.png",
                    dpi=150,
                    bbox_inches="tight",
                )
            plt.show()

        # C37: Faceted prediction distribution with actual overlay
        ctypes_cal = sorted(set(cal_contracts_arr))
        n_ct_cal = len(ctypes_cal)
        fig_pdist, axes_pdist = plt.subplots(
            1, n_ct_cal, figsize=(6 * n_ct_cal, 4), sharey=True
        )
        if not hasattr(axes_pdist, "__len__"):
            axes_pdist = [axes_pdist]
        for ax_pd, ct in zip(axes_pdist, ctypes_cal):
            mask = cal_contracts_arr == ct
            ax_pd.hist(
                cal_pred_arr[mask],
                bins=20,
                alpha=0.5,
                label="Predicted",
                color="blue",
                edgecolor="black",
                linewidth=0.3,
            )
            ax_pd.hist(
                cal_y_arr[mask],
                bins=20,
                alpha=0.5,
                label="Actual",
                color="orange",
                edgecolor="black",
                linewidth=0.3,
            )
            ax_pd.set_title(f"Pred vs Actual: {ct}")
            ax_pd.set_xlabel("Value")
            ax_pd.legend(fontsize=8)
            ax_pd.grid(True, alpha=0.3, axis="y")
        plt.suptitle(f"Prediction vs Actual Distribution: {primary_arm}", y=1.02)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_pdist.savefig(
                out / "prediction_distribution_faceted.png",
                dpi=150,
                bbox_inches="tight",
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
# # S6 Rung-Specific Analysis (R0)
#
# R0-specific model analysis: Gaussian assumption validation, feature selection
# justification, residual structure analysis, bid decision audit, and
# permutation importance. These analyses are unique to 30_'s model-focused
# perspective and do not overlap with 40_'s comparator/seed sensitivity scope.

# %%
# --- S6.1: Gaussian Assumption Validation ---
# HybridOLSa assumes tricks ~ N(mu, sigma^2). Test per-contract residuals.
print("=" * 60)
print("S6.1: Gaussian Assumption Validation")
print("=" * 60)

if _model_artifacts and not df.empty:
    primary_arm = (
        "olsa_full" if "olsa_full" in _model_artifacts else next(iter(_model_artifacts))
    )
    artifact = _model_artifacts[primary_arm]
    payoff = artifact.get("payoff_model", {})
    contracts = sorted(payoff.keys())

    _s6_residuals_by_ct = {}
    for contract in contracts:
        model = payoff[contract]
        feature_names = model.get("feature_names", [])
        weights = np.array(model.get("weights", []))
        bias = model.get("bias", 0.0)
        if not feature_names or len(weights) == 0:
            continue
        feat_c = [f"feat_{fn}" for fn in feature_names]
        subset = df[df["contract_type"] == contract]
        missing = [c for c in feat_c if c not in subset.columns]
        if missing or len(subset) == 0:
            continue
        X = subset[feat_c].values.astype(np.float64)
        y_actual = subset["tricks_won"].values.astype(np.float64)
        y_pred_s6 = X @ weights + bias
        resid = y_actual - y_pred_s6
        _s6_residuals_by_ct[contract] = resid

        if HAS_SCIPY and len(resid) >= 20:
            # Shapiro-Wilk limited to 5000 samples
            test_resid = resid[:5000] if len(resid) > 5000 else resid
            stat, p = scipy_stats.shapiro(test_resid)
            print(
                f"  {contract}: Shapiro-Wilk stat={stat:.4f}, "
                f"p={p:.4f} (n={len(test_resid)})"
            )
            if p < 0.05:
                print(
                    "    -> Rejects normality at alpha=0.05. "
                    "Gaussian EV may be approximate."
                )
            else:
                print("    -> Cannot reject normality at alpha=0.05.")
        else:
            print(f"  {contract}: n={len(resid)} (need >=20 + scipy for Shapiro-Wilk)")

    # Q-Q plot
    if _s6_residuals_by_ct and HAS_SCIPY:
        n_qq = len(_s6_residuals_by_ct)
        fig_qq, axes_qq = plt.subplots(1, n_qq, figsize=(5 * n_qq, 4), sharey=True)
        if not hasattr(axes_qq, "__len__"):
            axes_qq = [axes_qq]
        for ax_qq, (ct, resid) in zip(axes_qq, sorted(_s6_residuals_by_ct.items())):
            scipy_stats.probplot(resid, dist="norm", plot=ax_qq)
            ax_qq.set_title(f"Q-Q Plot: {ct}")
        plt.suptitle("Residual Q-Q Plots (Normal Reference)", y=1.02)
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_qq.savefig(out / "qq_residuals.png", dpi=150, bbox_inches="tight")
        plt.show()
else:
    print("  No model artifacts -- skipping Gaussian validation.")

# %%
# --- S6.2: Feature Selection Justification ---
# Explain the 3/1/1 sparse features vs top correlation features.
print("=" * 60)
print("S6.2: Feature Selection Justification")
print("=" * 60)

if _model_artifacts:
    # Show which features each arm uses per contract
    for arm_key, artifact in _model_artifacts.items():
        payoff = artifact.get("payoff_model", {})
        print(f"\n  {arm_key}:")
        for contract, model in sorted(payoff.items()):
            fnames = model.get("feature_names", [])
            print(f"    {contract}: {fnames}")

    # Compare with top correlation features from S1
    if not df.empty and feat_cols:
        print("\n  --- Comparison: Model Features vs Top Correlated ---")
        sparse_arm = "olsa" if "olsa" in _model_artifacts else None
        if sparse_arm:
            payoff_s = _model_artifacts[sparse_arm].get("payoff_model", {})
            for contract, model in sorted(payoff_s.items()):
                selected = set(model.get("feature_names", []))
                subset = df[df["contract_type"] == contract]
                if len(subset) < 5:
                    continue
                # Top features by |r| with tricks_won
                corr_vals = {}
                for fc in feat_cols:
                    if pd.api.types.is_numeric_dtype(subset[fc]):
                        valid = subset[fc].notna() & subset["tricks_won"].notna()
                        if valid.sum() > 2:
                            corr_vals[fc.replace("feat_", "")] = abs(
                                subset.loc[valid, fc].corr(
                                    subset.loc[valid, "tricks_won"]
                                )
                            )
                if corr_vals:
                    # Filter NaN before sorting
                    corr_clean = {k: v for k, v in corr_vals.items() if not np.isnan(v)}
                    top_by_corr = sorted(
                        corr_clean.items(), key=lambda x: x[1], reverse=True
                    )[:5]
                    top_names = [t[0] for t in top_by_corr]
                    overlap = selected & set(top_names)
                    print(
                        f"\n    {contract}:"
                        f"\n      Model features:      {sorted(selected)}"
                        f"\n      Top-5 by |r|:        {top_names}"
                        f"\n      Overlap:             {sorted(overlap)}"
                        f"\n      Not in top-5:        "
                        f"{sorted(selected - set(top_names))}"
                    )
else:
    print("  No model artifacts -- skipping feature selection justification.")

# %%
# --- S6.3: Residual Structure Analysis ---
# Correlate residuals with features NOT in the model to find missed signal.
print("=" * 60)
print("S6.3: Residual Structure Analysis")
print("=" * 60)

if _model_artifacts and not df.empty:
    sparse_arm = "olsa" if "olsa" in _model_artifacts else None
    if sparse_arm:
        payoff_s = _model_artifacts[sparse_arm].get("payoff_model", {})
        for contract, model in sorted(payoff_s.items()):
            selected_feats = set(model.get("feature_names", []))
            feature_names = model.get("feature_names", [])
            weights_s = np.array(model.get("weights", []))
            bias_s = model.get("bias", 0.0)
            if not feature_names or len(weights_s) == 0:
                continue
            feat_c = [f"feat_{fn}" for fn in feature_names]
            subset = df[df["contract_type"] == contract].copy()
            missing = [c for c in feat_c if c not in subset.columns]
            if missing or len(subset) < 10:
                continue
            X = subset[feat_c].values.astype(np.float64)
            y_actual = subset["tricks_won"].values.astype(np.float64)
            resid = y_actual - (X @ weights_s + bias_s)

            # Correlate residuals with excluded features
            excluded = [
                fc for fc in feat_cols if fc.replace("feat_", "") not in selected_feats
            ]
            if not excluded:
                continue
            print(f"\n  --- {contract} (OLSa residuals vs excluded features) ---")
            excl_rows = []
            for fc in excluded:
                if not pd.api.types.is_numeric_dtype(subset[fc]):
                    continue
                vals = subset[fc].values.astype(np.float64)
                valid_mask = ~np.isnan(vals)
                if valid_mask.sum() > 2:
                    r_val = np.corrcoef(resid[valid_mask], vals[valid_mask])[0, 1]
                    if HAS_SCIPY:
                        _, p_val = scipy_stats.pearsonr(
                            resid[valid_mask], vals[valid_mask]
                        )
                    else:
                        p_val = np.nan
                    excl_rows.append(
                        {
                            "feature": fc.replace("feat_", ""),
                            "resid_corr": round(r_val, 4),
                            "p_value": (
                                round(p_val, 6) if not np.isnan(p_val) else None
                            ),
                        }
                    )
            if excl_rows:
                excl_df = pd.DataFrame(excl_rows).sort_values(
                    "resid_corr", key=abs, ascending=False
                )
                print(excl_df.to_string(index=False))
                strong = excl_df[excl_df["resid_corr"].abs() > 0.1]
                if len(strong) > 0:
                    print(
                        f"  -> {len(strong)} excluded features with |r|>0.1 "
                        f"— consider for R1a+"
                    )
    else:
        print("  No OLSa arm available for residual structure analysis.")
else:
    print("  No model artifacts -- skipping residual structure analysis.")

# %%
# --- S6.4: Bid Decision Audit ---
# Trace sample deals through the pipeline to show how model math plays out.
print("=" * 60)
print("S6.4: Bid Decision Audit")
print("=" * 60)

if _model_artifacts and not df.empty:
    primary_arm = (
        "olsa_full" if "olsa_full" in _model_artifacts else next(iter(_model_artifacts))
    )
    artifact = _model_artifacts[primary_arm]
    payoff = artifact.get("payoff_model", {})
    sigma_model = artifact.get("sigma_model", {})

    # Select up to 10 sample bidder deals
    bidder_df = df[df["is_bidder"] == True].copy()  # noqa: E712
    if len(bidder_df) > 0:
        sample_n = min(10, len(bidder_df))
        sample_rng = np.random.default_rng(SEED)
        sample_idx = sample_rng.choice(len(bidder_df), size=sample_n, replace=False)
        sample_rows = bidder_df.iloc[sample_idx]

        print(f"\n  Tracing {sample_n} sample deals through {primary_arm}:\n")
        for _, row in sample_rows.iterrows():
            ct = row.get("contract_type", "?")
            model = payoff.get(ct, {})
            feat_names = model.get("feature_names", [])
            weights_a = np.array(model.get("weights", []))
            bias_a = model.get("bias", 0.0)

            if not feat_names or len(weights_a) == 0:
                print(f"  deal_id={row['deal_id']}: no model for {ct}")
                continue

            feat_vals = []
            for fn in feat_names:
                col = f"feat_{fn}"
                feat_vals.append(row.get(col, np.nan))
            feat_arr = np.array(feat_vals, dtype=np.float64)
            mu = float(feat_arr @ weights_a + bias_a)

            # Get sigma if available
            sigma_info = sigma_model.get(ct, {})
            sigma = sigma_info.get("sigma", None)
            sigma_str = f"{sigma:.3f}" if sigma is not None else "N/A"

            actual = row.get("tricks_won", "?")
            bid = row.get("winning_bid", "?")
            made = row.get("made_bid", "?")

            outcome = "MADE" if made else "SET"
            print(
                f"  deal={row['deal_id']:>5}, "
                f"ct={ct:>4}, "
                f"bid={bid}, "
                f"mu={mu:+.2f}, "
                f"sigma={sigma_str}, "
                f"actual={actual}, "
                f"outcome={outcome}"
            )
        print("\n  Legend: mu=predicted tricks, sigma=residual std, outcome=MADE/SET")
    else:
        print("  No bidder rows found -- skipping audit.")
else:
    print("  No model artifacts -- skipping bid decision audit.")

# %%
# --- S6.5: Permutation Importance (C56) ---
# For each feature in the model, permute column and measure R2 drop.
print("=" * 60)
print("S6.5: Permutation Feature Importance")
print("=" * 60)

if _model_artifacts and not df.empty:
    perm_rng = np.random.default_rng(SEED)

    for arm_key, artifact in _model_artifacts.items():
        payoff = artifact.get("payoff_model", {})
        print(f"\n  --- {arm_key} ---")

        for contract, model in sorted(payoff.items()):
            feature_names = model.get("feature_names", [])
            weights_p = np.array(model.get("weights", []))
            bias_p = model.get("bias", 0.0)
            if not feature_names or len(weights_p) == 0:
                continue

            feat_c = [f"feat_{fn}" for fn in feature_names]
            subset = df[df["contract_type"] == contract]
            missing = [c for c in feat_c if c not in subset.columns]
            if missing or len(subset) < 20:
                continue

            X = subset[feat_c].values.astype(np.float64)
            y = subset["tricks_won"].values.astype(np.float64)
            y_pred_base = X @ weights_p + bias_p
            ss_tot = np.sum((y - y.mean()) ** 2)
            if ss_tot == 0:
                continue
            ss_res_base = np.sum((y - y_pred_base) ** 2)
            r2_base = 1 - ss_res_base / ss_tot

            importance_rows = []
            for feat_idx, feat_name in enumerate(feature_names):
                X_perm = X.copy()
                X_perm[:, feat_idx] = perm_rng.permutation(X_perm[:, feat_idx])
                y_pred_perm = X_perm @ weights_p + bias_p
                ss_res_perm = np.sum((y - y_pred_perm) ** 2)
                r2_perm = 1 - ss_res_perm / ss_tot
                importance = r2_base - r2_perm
                importance_rows.append(
                    {
                        "feature": feat_name,
                        "R2_base": round(r2_base, 4),
                        "R2_permuted": round(r2_perm, 4),
                        "R2_drop": round(importance, 4),
                    }
                )

            if importance_rows:
                imp_df = pd.DataFrame(importance_rows).sort_values(
                    "R2_drop", ascending=False
                )
                print(f"\n    {contract} (base R2={r2_base:.4f}):")
                print("    " + imp_df.to_string(index=False).replace("\n", "\n    "))
else:
    print("  No model artifacts -- skipping permutation importance.")

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
print(f"  MODE={MODE} (max_deals={_max_deals})")
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
