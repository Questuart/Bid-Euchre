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
# # Feature Health Analysis
#
# **Goal:** Comprehensive feature health diagnostics for Arc D evaluation data.
# Validates dataset integrity, strata completeness, symmetry across seats/suits/teams,
# feature distributions, and feature-label relationships.
#
# **Data source:** JSONL eval logs (primary) or synthetic demo data (CI fallback).
#
# **Workflow rules**
# - Edit this `.py` file (paired, reviewable).
# - Run `make notebook-sync` before committing.
# - Keep outputs cleared (`make notebook-check` verifies this).
# - Parameterize via papermill -- do not hardcode paths.

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
from scipy.stats import f_oneway

from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.diagnostics.charts import (
    plot_feature_correlation,
    plot_feature_distributions,
    plot_feature_heatmap_by_suit,
    plot_hand_value_by_contract,
    plot_hand_value_by_seat_and_contract,
)
from bid_euchre.diagnostics.health_checks import (
    compute_health_scorecard,
    display_scorecard,
)

matplotlib.use("Agg")

MODE_DEAL_COUNTS = {"SMOKE": 30, "QUICK": 2_000, "FULL": 50_000}
max_deals = MODE_DEAL_COUNTS.get(MODE)

# --- Data loading: JSONL primary, synthetic fallback ---
_data_source = "synthetic"
df = pd.DataFrame()

if EVAL_LOG_PATH:
    eval_path = Path(EVAL_LOG_PATH)
    if eval_path.is_dir():
        log_files = sorted(glob_mod.glob(str(eval_path / "logs" / "*.jsonl")))
        log_file = log_files[0] if log_files else None
    else:
        log_file = str(eval_path) if eval_path.exists() else None
    if log_file:
        try:
            df = build_eval_dataset(log_file, max_deals=max_deals)
            _data_source = "eval_logs"
            print(f"Loaded {len(df)} rows from {Path(log_file).name}")
            print(f"  Deals: {df['deal_id'].nunique()}, Source: {_data_source}")
        except (FileNotFoundError, ValueError) as exc:
            print(f"WARNING: Could not load eval logs: {exc}")

if df.empty:
    # Synthetic demo data for CI / SMOKE fallback
    rng = np.random.default_rng(42)
    n_deals = max_deals or 30
    rows = []
    for deal_id in range(n_deals):
        contract = rng.choice(["suit", "high", "low"])
        trump = rng.choice(["C", "D", "H", "S"]) if contract == "suit" else None
        t0 = int(rng.integers(0, 11))
        t1 = 10 - t0
        base_hv = float(rng.integers(200, 800))
        base_tc = int(rng.integers(0, 7))
        base_bow = int(rng.integers(0, 3))
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
                    "feat_hand_value": base_hv + float(rng.normal(0, 5)),
                    "feat_trump_count": base_tc + int(rng.integers(-1, 2)),
                    "feat_bowers": base_bow,
                }
            )
    df = pd.DataFrame(rows)
    _data_source = "synthetic"
    print(f"Using synthetic demo data ({n_deals} deals, {len(df)} rows)")

print(f"\nMODE={MODE}, data_source={_data_source}")
print(f"Shape: {df.shape}")
print(f"Columns: {sorted(df.columns.tolist())}")

# %% [markdown]
# # S1 Health Scorecard

# %%
if not df.empty:
    scorecard = compute_health_scorecard(df)
    scorecard_text = display_scorecard(scorecard)
    print(scorecard_text)

    # Summary counts
    summary = scorecard.summary()
    print(f"\nSummary: {summary}")

    # Health scorecard bar chart
    fig_sc, ax_sc = plt.subplots(figsize=(8, 1.5))
    statuses = ["PASS", "WARN", "FAIL"]
    colors_sc = {"PASS": "#2ecc71", "WARN": "#f39c12", "FAIL": "#e74c3c"}
    left = 0.0
    total = sum(summary.values())
    for status in statuses:
        count = summary[status]
        if count > 0:
            width = count / total if total > 0 else 0
            ax_sc.barh(
                0,
                width,
                left=left,
                color=colors_sc[status],
                label=f"{status} ({count})",
            )
            left += width
    ax_sc.set_xlim(0, 1)
    ax_sc.set_yticks([])
    ax_sc.set_xlabel("Proportion of checks")
    ax_sc.set_title("Health Scorecard Summary")
    ax_sc.legend(loc="lower right", fontsize=8)
    plt.tight_layout()
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_sc.savefig(out / "health_scorecard.png", dpi=150, bbox_inches="tight")
    plt.show()
else:
    print("No data loaded -- cannot compute health scorecard.")

# %% [markdown]
# # S2 Dataset Integrity

# %%
if not df.empty:
    integrity_results = []

    # Check 1: 4 rows per deal
    if "deal_id" in df.columns:
        rows_per_deal = df.groupby("deal_id").size()
        n_bad = (rows_per_deal != 4).sum()
        integrity_results.append(
            {
                "check": "4 rows per deal",
                "status": "PASS" if n_bad == 0 else "FAIL",
                "detail": f"{n_bad} deals with != 4 rows" if n_bad > 0 else "OK",
            }
        )
        if n_bad > 0:
            print(f"WARNING: {n_bad} deals do not have exactly 4 rows")
    else:
        integrity_results.append(
            {
                "check": "4 rows per deal",
                "status": "SKIP",
                "detail": "No deal_id column",
            }
        )

    # Check 2: feat_* columns present
    feat_cols = sorted([c for c in df.columns if c.startswith("feat_")])
    n_feat = len(feat_cols)
    integrity_results.append(
        {
            "check": "feat_* columns",
            "status": "PASS" if n_feat > 0 else "WARN",
            "detail": f"{n_feat} feature columns found",
        }
    )
    if feat_cols:
        print(f"Feature columns ({n_feat}): {feat_cols}")

    # Check 3: NaN audit
    nan_counts = df[feat_cols].isna().sum() if feat_cols else pd.Series(dtype=int)
    cols_with_nans = nan_counts[nan_counts > 0]
    integrity_results.append(
        {
            "check": "NaN audit",
            "status": "PASS" if len(cols_with_nans) == 0 else "WARN",
            "detail": f"{len(cols_with_nans)} columns with NaN"
            if len(cols_with_nans) > 0
            else "No NaNs",
        }
    )
    if len(cols_with_nans) > 0:
        print(f"Columns with NaN values:\n{cols_with_nans.to_string()}")

    # Check 4: Duplicate (deal_id, seat) check
    if "deal_id" in df.columns and "seat" in df.columns:
        n_dups = df.duplicated(subset=["deal_id", "seat"]).sum()
        integrity_results.append(
            {
                "check": "No duplicate (deal_id, seat)",
                "status": "PASS" if n_dups == 0 else "FAIL",
                "detail": f"{n_dups} duplicates" if n_dups > 0 else "OK",
            }
        )
    else:
        integrity_results.append(
            {
                "check": "No duplicate (deal_id, seat)",
                "status": "SKIP",
                "detail": "Missing deal_id or seat",
            }
        )

    integrity_df = pd.DataFrame(integrity_results)
    print("\n=== Dataset Integrity Checks ===")
    print(integrity_df.to_string(index=False))
else:
    print("No data loaded -- skipping integrity checks.")

# %% [markdown]
# # S3 Strata Completeness

# %%
if not df.empty:
    # Contract type distribution
    if "contract_type" in df.columns:
        print("=== Contract Type Distribution ===")
        ct_counts = df.groupby("contract_type")["deal_id"].nunique()
        print(ct_counts.to_string())

    # Trump suit distribution (suit contracts only)
    if "trump" in df.columns and "contract_type" in df.columns:
        suit_df = df[df["contract_type"] == "suit"].copy()
        if not suit_df.empty:
            print("\n=== Trump Suit Distribution (suit contracts) ===")
            trump_counts = suit_df.groupby("trump")["deal_id"].nunique()
            print(trump_counts.to_string())

    # Seat distribution
    if "seat" in df.columns:
        print("\n=== Seat Distribution ===")
        seat_counts = df["seat"].value_counts().sort_index()
        print(seat_counts.to_string())

    # Team distribution
    if "team" in df.columns:
        print("\n=== Team Distribution ===")
        team_counts = df["team"].value_counts().sort_index()
        print(team_counts.to_string())

    # Stacked bar: deal counts by contract_type x trump
    if "contract_type" in df.columns:
        deal_level = df.drop_duplicates(subset=["deal_id"])
        deal_level_trump = deal_level.copy()
        deal_level_trump["trump"] = deal_level_trump["trump"].fillna("__NONE__")

        ct_order = ["suit", "high", "low"]
        present_ct = [
            c for c in ct_order if c in deal_level_trump["contract_type"].values
        ]
        all_trumps = sorted(deal_level_trump["trump"].unique())

        fig_strata, ax_strata = plt.subplots(figsize=(10, 5))
        bottom = np.zeros(len(present_ct))
        cmap = plt.cm.Set2
        for i, trump_val in enumerate(all_trumps):
            counts = []
            for ct in present_ct:
                mask = (deal_level_trump["contract_type"] == ct) & (
                    deal_level_trump["trump"] == trump_val
                )
                counts.append(mask.sum())
            label = trump_val if trump_val != "__NONE__" else "no-trump"
            ax_strata.bar(
                present_ct,
                counts,
                bottom=bottom,
                label=label,
                color=cmap(i / max(len(all_trumps), 1)),
            )
            bottom += np.array(counts, dtype=float)

        ax_strata.set_xlabel("Contract Type")
        ax_strata.set_ylabel("Deal Count")
        ax_strata.set_title("Strata Completeness: Deals by Contract Type x Trump")
        ax_strata.legend(title="Trump", bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_strata.savefig(
                out / "strata_completeness.png", dpi=150, bbox_inches="tight"
            )
        plt.show()
else:
    print("No data loaded -- skipping strata completeness.")

# %% [markdown]
# # S4 Symmetry Analysis

# %% [markdown]
# ## S4.1 By Contract Type

# %%
if not df.empty and "feat_hand_value" in df.columns and "contract_type" in df.columns:
    fig_hv_ct = plot_hand_value_by_contract(df)
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_hv_ct.savefig(
            out / "hand_value_by_contract.png", dpi=150, bbox_inches="tight"
        )
    plt.show()

    # Summary stats table
    print("\n=== Hand Value Summary by Contract Type ===")
    ct_stats = df.groupby("contract_type")["feat_hand_value"].describe()
    print(ct_stats.to_string())
else:
    print("Skipping contract type symmetry (missing data or columns).")

# %% [markdown]
# ## S4.2 By Trump Suit (suit contracts only)

# %%
if not df.empty and "feat_hand_value" in df.columns and "trump" in df.columns:
    suit_df = df[df["trump"].notna()].copy()
    if len(suit_df) > 0:
        trump_suits = sorted(suit_df["trump"].unique())

        # ANOVA: hand_value across trump suits
        if len(trump_suits) >= 2:
            groups = [
                suit_df.loc[suit_df["trump"] == s, "feat_hand_value"].dropna().values
                for s in trump_suits
            ]
            groups = [g for g in groups if len(g) > 0]
            if len(groups) >= 2:
                f_stat, p_val = f_oneway(*groups)
                print(f"ANOVA hand_value ~ trump_suit: F={f_stat:.3f}, p={p_val:.4f}")
            else:
                f_stat, p_val = np.nan, np.nan
                print("Not enough groups for ANOVA.")
        else:
            f_stat, p_val = np.nan, np.nan
            print("Only one trump suit found -- skipping ANOVA.")

        # Boxplot
        fig_trump, ax_trump = plt.subplots(figsize=(8, 5))
        data_by_suit = [
            suit_df.loc[suit_df["trump"] == s, "feat_hand_value"].dropna().values
            for s in trump_suits
        ]
        bp = ax_trump.boxplot(data_by_suit, labels=trump_suits, patch_artist=True)
        for patch in bp["boxes"]:
            patch.set_facecolor("#7fb3d8")
            patch.set_alpha(0.7)
        title_suffix = f" (ANOVA p={p_val:.3f})" if not np.isnan(p_val) else ""
        ax_trump.set_title(f"Hand Value by Trump Suit{title_suffix}")
        ax_trump.set_xlabel("Trump Suit")
        ax_trump.set_ylabel("Hand Value")
        ax_trump.grid(True, alpha=0.3, axis="y")
        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_trump.savefig(
                out / "hand_value_by_trump.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # Per-suit stats table
        print("\n=== Per-Suit Stats ===")
        trump_stats = suit_df.groupby("trump")["feat_hand_value"].agg(
            ["count", "mean", "std", "min", "max"]
        )
        print(trump_stats.to_string())
    else:
        print("No suit contracts found -- skipping trump suit analysis.")
else:
    print("Skipping trump suit symmetry (missing data or columns).")

# %% [markdown]
# ## S4.3 By Team

# %%
if not df.empty and "feat_hand_value" in df.columns and "team" in df.columns:
    if "contract_type" in df.columns:
        ctypes = sorted(df["contract_type"].unique())
        n_ct = len(ctypes)
        fig_team, axes_team = plt.subplots(
            1, max(n_ct, 1), figsize=(5 * max(n_ct, 1), 5), squeeze=False
        )
        axes_team = axes_team[0]

        for idx, ct in enumerate(ctypes):
            ax = axes_team[idx]
            subset = df[df["contract_type"] == ct]
            teams = sorted(subset["team"].unique())
            team_data = [
                subset.loc[subset["team"] == t, "feat_hand_value"].dropna().values
                for t in teams
            ]
            parts = ax.violinplot(
                team_data, positions=teams, showmeans=True, showmedians=True
            )
            ax.set_title(f"Hand Value by Team: {ct}")
            ax.set_xlabel("Team")
            ax.set_ylabel("Hand Value" if idx == 0 else "")
            ax.set_xticks(teams)
            ax.grid(True, alpha=0.3, axis="y")

        plt.tight_layout()
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_team.savefig(
                out / "hand_value_by_team.png", dpi=150, bbox_inches="tight"
            )
        plt.show()
    else:
        print("No contract_type column -- skipping team symmetry.")
else:
    print("Skipping team symmetry (missing data or columns).")

# %% [markdown]
# ## S4.4 By Seat

# %%
if (
    not df.empty
    and "feat_hand_value" in df.columns
    and "seat" in df.columns
    and "contract_type" in df.columns
):
    fig_seat = plot_hand_value_by_seat_and_contract(df)
    if CHART_OUTPUT_DIR:
        out = Path(CHART_OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        fig_seat.savefig(out / "seat_balance_boxplot.png", dpi=150, bbox_inches="tight")
    plt.show()

    # ANOVA for seat balance per contract type
    print("\n=== Seat Balance ANOVA (per contract type) ===")
    for ct in sorted(df["contract_type"].unique()):
        subset = df[df["contract_type"] == ct]
        seats = sorted(subset["seat"].unique())
        groups = [
            subset.loc[subset["seat"] == s, "feat_hand_value"].dropna().values
            for s in seats
        ]
        groups = [g for g in groups if len(g) > 0]
        if len(groups) >= 2:
            f_stat, p_val = f_oneway(*groups)
            print(f"  {ct}: F={f_stat:.3f}, p={p_val:.4f}")
        else:
            print(f"  {ct}: Not enough groups for ANOVA")
else:
    print("Skipping seat symmetry (missing data or columns).")

# %% [markdown]
# ## S4.5 Feature-Level Symmetry

# %%
if not df.empty and "seat" in df.columns:
    feat_cols = sorted([c for c in df.columns if c.startswith("feat_")])
    numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]

    if numeric_feats:
        # Compute variance of seat means for each feature
        seat_mean_vars = {}
        for col in numeric_feats:
            seat_means = df.groupby("seat")[col].mean()
            seat_mean_vars[col] = seat_means.var()

        # Top 5 features by variance across seats
        top5_by_seat_var = sorted(seat_mean_vars, key=seat_mean_vars.get, reverse=True)[
            :5
        ]
        print("=== Top 5 Features by Variance Across Seats ===")
        for col in top5_by_seat_var:
            seat_means = df.groupby("seat")[col].mean()
            print(
                f"  {col}: seat_var={seat_mean_vars[col]:.4f}, means={seat_means.to_dict()}"
            )

        # Feature heatmap by suit (Z-score)
        if "trump" in df.columns and df["trump"].notna().any():
            fig_hm = plot_feature_heatmap_by_suit(df)
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_hm.savefig(
                    out / "feature_symmetry_heatmap.png",
                    dpi=150,
                    bbox_inches="tight",
                )
            plt.show()
        else:
            print("No trump data available -- skipping feature heatmap by suit.")
    else:
        print("No numeric feature columns found.")
else:
    print("Skipping feature-level symmetry (missing data or columns).")

# %% [markdown]
# # S5 Feature Distributions

# %%
if not df.empty:
    feat_cols = sorted([c for c in df.columns if c.startswith("feat_")])
    numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]

    if numeric_feats:
        # Top 9 features by variance (per contract pooled)
        variances = {c: df[c].var() for c in numeric_feats}
        top_9 = sorted(variances, key=variances.get, reverse=True)[:9]
        top_9_names = [c.replace("feat_", "") for c in top_9]

        fig_dist = plot_feature_distributions(df, features=top_9_names)
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_dist.savefig(
                out / "feature_distributions.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # Correlation matrix: top 15
        top_15 = sorted(variances, key=variances.get, reverse=True)[:15]
        top_15_names = [c.replace("feat_", "") for c in top_15]

        fig_corr = plot_feature_correlation(df, features=top_15_names)
        if CHART_OUTPUT_DIR:
            out = Path(CHART_OUTPUT_DIR)
            out.mkdir(parents=True, exist_ok=True)
            fig_corr.savefig(
                out / "feature_correlation_matrix.png", dpi=150, bbox_inches="tight"
            )
        plt.show()

        # Summary stats table
        print("\n=== Feature Summary Stats ===")
        desc = df[numeric_feats].describe().T
        print(desc[["count", "mean", "std", "min", "max"]].to_string())
    else:
        print("No numeric feature columns found.")
else:
    print("No data loaded -- skipping feature distributions.")

# %% [markdown]
# # S6 Feature-Label Relationships

# %%
if not df.empty and "tricks_won" in df.columns:
    feat_cols = sorted([c for c in df.columns if c.startswith("feat_")])
    numeric_feats = [c for c in feat_cols if pd.api.types.is_numeric_dtype(df[c])]

    if numeric_feats and "contract_type" in df.columns:
        # Pearson correlation per contract type
        ctypes = sorted(df["contract_type"].unique())
        corr_data = {}
        for ct in ctypes:
            subset = df[df["contract_type"] == ct]
            corrs = {}
            for col in numeric_feats:
                valid = subset[col].notna() & subset["tricks_won"].notna()
                if valid.sum() > 2:
                    r = subset.loc[valid, col].corr(subset.loc[valid, "tricks_won"])
                    corrs[col.replace("feat_", "")] = r
            corr_data[ct] = corrs

        corr_df = pd.DataFrame(corr_data)
        if not corr_df.empty:
            # Heatmap: feature x contract correlations
            fig_foc, ax_foc = plt.subplots(
                figsize=(max(8, len(ctypes) * 3), max(6, len(corr_df) * 0.35))
            )
            corr_matrix = corr_df.fillna(0).values
            im = ax_foc.imshow(
                corr_matrix, aspect="auto", cmap="RdBu_r", vmin=-1, vmax=1
            )
            ax_foc.set_xticks(range(len(ctypes)))
            ax_foc.set_xticklabels(ctypes)
            ax_foc.set_yticks(range(len(corr_df)))
            ax_foc.set_yticklabels(corr_df.index, fontsize=8)
            ax_foc.set_title("Feature-Outcome Correlations (Pearson r vs tricks_won)")
            plt.colorbar(im, ax=ax_foc, label="Pearson r")
            # Annotate cells
            for i in range(len(corr_df)):
                for j in range(len(ctypes)):
                    val = corr_matrix[i, j]
                    color = "white" if abs(val) > 0.5 else "black"
                    ax_foc.text(
                        j,
                        i,
                        f"{val:.2f}",
                        ha="center",
                        va="center",
                        color=color,
                        fontsize=7,
                    )
            plt.tight_layout()
            if CHART_OUTPUT_DIR:
                out = Path(CHART_OUTPUT_DIR)
                out.mkdir(parents=True, exist_ok=True)
                fig_foc.savefig(
                    out / "feature_outcome_heatmap.png", dpi=150, bbox_inches="tight"
                )
            plt.show()

            # Table: top 10 features by |r| per contract
            print("\n=== Top 10 Features by |r| per Contract Type ===")
            for ct in ctypes:
                if ct in corr_df.columns:
                    ranked = corr_df[ct].dropna().abs().nlargest(10)
                    print(f"\n{ct}:")
                    for feat, abs_r in ranked.items():
                        actual_r = corr_df.loc[feat, ct]
                        print(f"  {feat:30s} r={actual_r:+.4f}")

            # Scatter: top 3 features by max |r| across contracts
            max_abs_r = corr_df.abs().max(axis=1).nlargest(3)
            top3_feats = max_abs_r.index.tolist()

            if top3_feats:
                fig_scatter, axes_scatter = plt.subplots(
                    1, len(top3_feats), figsize=(6 * len(top3_feats), 5)
                )
                if not hasattr(axes_scatter, "__len__"):
                    axes_scatter = [axes_scatter]

                for ax, feat_name in zip(axes_scatter, top3_feats):
                    col = f"feat_{feat_name}"
                    if col in df.columns:
                        for ct in ctypes:
                            subset = df[df["contract_type"] == ct]
                            ax.scatter(
                                subset[col],
                                subset["tricks_won"],
                                alpha=0.3,
                                s=8,
                                label=ct,
                            )
                        ax.set_xlabel(feat_name)
                        ax.set_ylabel("tricks_won")
                        ax.set_title(feat_name)
                        ax.legend(fontsize=7)
                        ax.grid(True, alpha=0.3)

                plt.tight_layout()
                if CHART_OUTPUT_DIR:
                    out = Path(CHART_OUTPUT_DIR)
                    out.mkdir(parents=True, exist_ok=True)
                    fig_scatter.savefig(
                        out / "feature_vs_tricks_scatter.png",
                        dpi=150,
                        bbox_inches="tight",
                    )
                plt.show()
        else:
            print("No valid feature-outcome correlations computed.")
    else:
        print("Missing numeric features or contract_type column.")
else:
    print("Skipping feature-label relationships (no tricks_won column or no data).")

# %% [markdown]
# # S7 Summary

# %%
if not df.empty:
    print("=" * 60)
    print(f"Feature Health Report -- {RUNG_ID or 'unknown rung'}")
    print("=" * 60)

    # Recap scorecard
    if "scorecard" in dir():
        summary = scorecard.summary()
        print(
            f"\nHealth Scorecard: {summary['PASS']} PASS, {summary['WARN']} WARN, {summary['FAIL']} FAIL"
        )
        if summary["FAIL"] > 0:
            print("  BLOCKING FAILURES:")
            for chk in scorecard.get_failures():
                print(f"    - {chk.name}: {chk.message}")
        if summary["WARN"] > 0:
            print("  WARNINGS:")
            for chk in scorecard.get_warnings():
                print(f"    - {chk.name}: {chk.message}")

    # Dataset summary
    n_deals = df["deal_id"].nunique() if "deal_id" in df.columns else "?"
    n_feats = len([c for c in df.columns if c.startswith("feat_")])
    print(f"\nDataset: {n_deals} deals, {len(df)} rows, {n_feats} features")
    print(f"Data source: {_data_source}")
    print(f"MODE: {MODE}")

    # Key findings
    print("\nKey findings:")
    if "contract_type" in df.columns:
        ct_dist = df["contract_type"].value_counts()
        print(f"  - Contract types: {ct_dist.to_dict()}")
    if "seat" in df.columns and "feat_hand_value" in df.columns:
        seat_means = df.groupby("seat")["feat_hand_value"].mean()
        seat_range = seat_means.max() - seat_means.min()
        print(f"  - Seat hand_value range: {seat_range:.2f}")

    # Links to companion notebooks
    print("\nCompanion notebooks:")
    print("  - 01_model_rung_template.py (full model evaluation)")
    print("  - 20_matchup_analysis.py (strategy matchup)")
else:
    print("No data loaded -- report is empty.")
