# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags
#     formats: py:percent,ipynb
#     notebook_metadata_filter: jupytext,kernelspec,language_info
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: bid-euchre
#     language: python
#     name: python3
#   language_info:
#     codemirror_mode:
#       name: ipython
#       version: 3
#     file_extension: .py
#     mimetype: text/x-python
#     name: python
#     nbconvert_exporter: python
#     pygments_lexer: ipython3
#     version: 3.14.2
# ---

# %% [markdown]
# # Phase 0: Outcome Health Checks
#
# This notebook validates simulation **outcomes** (tricks_won) for the bidless Euchre dataset.
#
# **Sections:**
# - Section 0: Configuration and Setup
# - Section 1: Fail-Fast Validation Tests
# - Section 2: Outcome Distribution Analysis (Self-play)
# - Section 3: Strategy Analysis (Head-to-head)
#   - 3.1-3.5: Heatmaps and distribution grids
#   - 3.6: Strategy Sanity Tests
# - Section 4: Distribution Analysis (CDF/CCDF)
# - Section 5: Summary
#
# **Counterpart:**
# - See `10_feature_health_checks.ipynb` for feature validation
#
# **Quick start:**
# 1. Set `MODE = "QUICK"` or `MODE = "FULL"`
# 2. Run all cells
# 3. Review fail-fast assertions and summary

# %% [markdown]
# ---
#
# ## Section 0: Configuration and Setup
#
# Set experiment parameters, import utilities, and load datasets.

# %% tags=["parameters"]
# ============================================================================
# Configuration (papermill parameters)
# ============================================================================

MODE = "FULL"  # "SMOKE" (~30 deals), "QUICK" (~2k deals), or "FULL" (~50k deals)
SEED = 42

# Contract space
CONTRACT_TYPES = ["suit", "high", "low"]
TRUMPS_FOR_SUIT_CONTRACTS = ["C", "D", "H", "S"]
SEATS = [0, 1, 2, 3]

# Strategy configuration
STRATEGIES = [
    {"name": "greedy", "class_name": "GreedyStrategy"},
    {"name": "glutton", "class_name": "GluttonStrategy"},
    {"name": "random", "class_name": "RandomLegalStrategy"},
    {"name": "always_highest", "class_name": "AlwaysHighestLegalStrategy"},
    {"name": "always_lowest", "class_name": "AlwaysLowestLegalStrategy"},
]

# Plot downsampling (for performance; never affects validations)
PLOT_MAX_ROWS = 10_000
PLOT_SAMPLE_SEED = 42
DOWNSAMPLE_PLOTS = True

# Display
import warnings

warnings.filterwarnings("ignore")

print("Configuration:")
print(f"  Mode: {MODE}")
print(f"  Seed: {SEED}")
print(f"  Contract types: {CONTRACT_TYPES}")
print(f"  Trumps (suit contracts): {TRUMPS_FOR_SUIT_CONTRACTS}")
print(f"  Seats: {SEATS}")
print(f"  Strategies: {[s['name'] for s in STRATEGIES]}")
print(f"  Plot downsampling: {DOWNSAMPLE_PLOTS} (max {PLOT_MAX_ROWS} rows)")

# %%
# ============================================================================
# Imports
# ============================================================================

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import f_oneway, friedmanchisquare, kendalltau, ttest_rel

# Optional: seaborn for enhanced visualizations
try:
    import seaborn as sns

    sns.set_theme(style="whitegrid")
    HAS_SEABORN = True
except ImportError:
    print("seaborn not available, using matplotlib defaults")
    HAS_SEABORN = False

# PYTHONPATH=src is set by papermill/uv run — no sys.path manipulation needed
repo_root = Path.cwd().parent.parent

from bid_euchre.diagnostics.notebook_data import (
    load_or_generate_outcomes,
)

print("\n✓ Imports complete")


# %%
# ============================================================================
# Matchup Matrix Builder (N×N)
# ============================================================================

STRATEGY_NAMES = [s["name"] for s in STRATEGIES]

# Build full N×N matchup matrix (16 matchups for 4 strategies)
MATCHUPS_MATRIX = [
    {"team0": a, "team1": b} for a in STRATEGY_NAMES for b in STRATEGY_NAMES
]

print(
    f"Built {len(MATCHUPS_MATRIX)} matchups (full {len(STRATEGY_NAMES)}×{len(STRATEGY_NAMES)} matrix)"
)
print(f"Matchup examples: {MATCHUPS_MATRIX[:3]}")


# %%
# ============================================================================
# Deal-Level Frame Helper
# ============================================================================


def make_deal_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build one row per deal with team0_tricks, team1_tricks, delta_tricks.

    Note: load_or_generate_outcomes logs tricks_won as TEAM tricks:
    - Seats 0 & 2 get team0_tricks
    - Seats 1 & 3 get team1_tricks

    So we can use seat 0 for team0 and seat 1 for team1 directly.

    Args:
        df: Outcome dataframe with seat-level rows

    Returns:
        DataFrame with columns: deal_id, contract_type, trump, strategy_id,
                                team0_tricks, team1_tricks, delta_tricks, team0_win
    """
    keys = ["deal_id", "contract_type", "trump", "strategy_id"]

    # Team 0: use seat 0 (which already has team0 tricks)
    df_team0 = df[df.seat == 0][keys + ["tricks_won"]].rename(
        columns={"tricks_won": "team0_tricks"}
    )

    # Team 1: use seat 1 (which already has team1 tricks)
    df_team1 = df[df.seat == 1][keys + ["tricks_won"]].rename(
        columns={"tricks_won": "team1_tricks"}
    )

    # Fill NaN trump with sentinel before merge (pandas doesn't match NaN == NaN)
    for _df in [df_team0, df_team1]:
        _df["trump"] = _df["trump"].fillna("__NONE__")
    df_deal = df_team0.merge(df_team1, on=keys)
    df_deal["trump"] = df_deal["trump"].replace("__NONE__", None)
    df_deal["delta_tricks"] = df_deal["team0_tricks"] - df_deal["team1_tricks"]
    # Weighted win: 1.0 for win (>=6), 0.5 for tie (=5), 0.0 for loss (<=4)
    df_deal["team0_win"] = np.where(
        df_deal["team0_tricks"] >= 6,
        1.0,
        np.where(df_deal["team0_tricks"] == 5, 0.5, 0.0),
    )

    return df_deal


def downsample_for_plot(df: pd.DataFrame) -> pd.DataFrame:
    """Downsample dataframe for plotting if enabled and needed."""
    if DOWNSAMPLE_PLOTS and len(df) > PLOT_MAX_ROWS:
        return df.sample(PLOT_MAX_ROWS, random_state=PLOT_SAMPLE_SEED)
    return df


def is_paired_data(
    df: pd.DataFrame, group_col: str, value_col: str = "deal_id"
) -> bool:
    """Check if same deal_ids appear across all groups (paired design).

    Args:
        df: DataFrame with observations
        group_col: Column defining groups (e.g., 'contract_type')
        value_col: Column to check for pairing (default 'deal_id')

    Returns:
        True if all deal_ids appear in all groups (paired data)
    """
    groups = df[group_col].unique()
    if len(groups) < 2:
        return False

    # Get deal_ids for each group
    deal_sets = [set(df[df[group_col] == g][value_col].unique()) for g in groups]

    # Check if intersection equals all sets (same deals in all groups)
    common_deals = set.intersection(*deal_sets)
    all_deals = set.union(*deal_sets)

    # Consider paired if >90% of deals appear in all groups
    return len(common_deals) / len(all_deals) > 0.9 if all_deals else False


def run_contract_comparison(
    df: pd.DataFrame, groups: list, group_names: list, value_col: str = "team0_tricks"
) -> tuple:
    """Run appropriate statistical test based on data pairing.

    Args:
        df: DataFrame with observations
        groups: List of arrays, one per group
        group_names: Names of the groups
        value_col: Column being compared

    Returns:
        (stat, p_value, test_name) tuple
    """
    # Check if data is paired by examining deal_id overlap
    if "deal_id" not in df.columns:
        # No deal_id, use independent test
        f_stat, p_value = f_oneway(*groups)
        return f_stat, p_value, "ANOVA"

    # For paired test, we need equal-sized groups with matching deal_ids
    # Try to detect if this is paired data
    paired = is_paired_data(
        df, "contract_type" if "contract_type" in df.columns else df.columns[0]
    )

    if paired and len(groups) >= 2:
        # For paired data, use Friedman test (non-parametric repeated measures)
        # Need to align data by deal_id
        try:
            # Friedman requires equal-length arrays
            min_len = min(len(g) for g in groups)
            if min_len > 0:
                aligned_groups = [g[:min_len] for g in groups]
                if len(aligned_groups) >= 3:
                    stat, p_value = friedmanchisquare(*aligned_groups)
                    return stat, p_value, "Friedman"
                elif len(aligned_groups) == 2:
                    stat, p_value = ttest_rel(aligned_groups[0], aligned_groups[1])
                    return stat, p_value, "Paired t-test"
        except Exception:
            pass  # Fall back to ANOVA

    # Default: independent ANOVA
    f_stat, p_value = f_oneway(*groups)
    return f_stat, p_value, "ANOVA"


print("✓ Helper functions defined")


# %%
# ============================================================================
# Load/Generate Outcome Data: Self-play and Head-to-head
# ============================================================================

print("\n" + "=" * 70)
print("LOADING DATASETS")
print("=" * 70)

# Self-play dataset (each strategy plays against itself)
print(f"\n1. Loading SELF-PLAY dataset (mode={MODE}, seed={SEED})...")
df_self = load_or_generate_outcomes(
    mode=MODE,
    seed=SEED,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    seats=SEATS,
    strategies=STRATEGIES,
    matchups=None,  # None = self-play for each strategy
)

print(f"   Self-play shape: {df_self.shape}")
print(f"   Unique strategy_ids: {sorted(df_self['strategy_id'].unique())}")

# Head-to-head dataset (full N×N matchup matrix)
print(f"\n2. Loading HEAD-TO-HEAD dataset (mode={MODE}, seed={SEED})...")
df_h2h = load_or_generate_outcomes(
    mode=MODE,
    seed=SEED,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    seats=SEATS,
    strategies=STRATEGIES,
    matchups=MATCHUPS_MATRIX,
)

print(f"   Head-to-head shape: {df_h2h.shape}")
print(f"   Unique strategy_ids: {sorted(df_h2h['strategy_id'].unique())}")

print("\n" + "=" * 70)
print("✓ Both datasets loaded")
print("=" * 70)


# %%
# ============================================================================
# Parse Matchup IDs (for head-to-head data)
# ============================================================================


def parse_matchup_id(strategy_id: str) -> dict:
    """Parse strategy_id to extract per-seat strategy mapping."""
    if "_vs_" in strategy_id:
        team0, team1 = strategy_id.split("_vs_", maxsplit=1)
        return {
            "team0_strategy": team0,
            "team1_strategy": team1,
        }
    # Single strategy (self-play)
    return {
        "team0_strategy": strategy_id,
        "team1_strategy": strategy_id,
    }


# Parse matchup metadata for head-to-head data
if "strategy_id" in df_h2h.columns:
    matchup_meta = df_h2h["strategy_id"].apply(parse_matchup_id).apply(pd.Series)
    # Drop columns already present (e.g. from parquet join) to avoid duplicates
    existing_cols = set(df_h2h.columns) & set(matchup_meta.columns)
    matchup_meta = matchup_meta.drop(columns=existing_cols, errors="ignore")
    df_h2h = pd.concat([df_h2h, matchup_meta], axis=1)
    print("Parsed matchup IDs for head-to-head data")
    print(f"  Unique team0_strategy: {sorted(df_h2h['team0_strategy'].unique())}")
    print(f"  Unique team1_strategy: {sorted(df_h2h['team1_strategy'].unique())}")

# Also parse for self-play data
if "strategy_id" in df_self.columns:
    matchup_meta_self = df_self["strategy_id"].apply(parse_matchup_id).apply(pd.Series)
    existing_cols_self = set(df_self.columns) & set(matchup_meta_self.columns)
    matchup_meta_self = matchup_meta_self.drop(
        columns=existing_cols_self, errors="ignore"
    )
    df_self = pd.concat([df_self, matchup_meta_self], axis=1)
    print("Parsed matchup IDs for self-play data")


# %%
# ============================================================================
# Data Overview
# ============================================================================

print("\n" + "=" * 70)
print("DATA OVERVIEW")
print("=" * 70)

print("\n--- Self-play Dataset ---")
print(f"Total observations: {len(df_self)}")
print("\nContract type distribution:")
print(df_self["contract_type"].value_counts().sort_index())
print("\nStrategy distribution:")
print(df_self["strategy_id"].value_counts())

print("\n--- Head-to-head Dataset ---")
print(f"Total observations: {len(df_h2h)}")
print("\nContract type distribution:")
print(df_h2h["contract_type"].value_counts().sort_index())
print("\nMatchup distribution (top 10):")
print(df_h2h["strategy_id"].value_counts().head(10))

print("=" * 70)

# %% [markdown]
# ---
#
# ## Section 1: Fail-Fast Validation Tests
#
# Critical assertions that must pass before proceeding with analysis.
# Applied to both self-play and head-to-head datasets.

# %%
# ============================================================================
# Test 1.1: Outcome Validity
# ============================================================================

print("\n" + "=" * 70)
print("TEST 1.1: Outcome Validity")
print("=" * 70)

for name, df in [("Self-play", df_self), ("Head-to-head", df_h2h)]:
    print(f"\n--- {name} Dataset ---")

    # Check required columns
    required_cols = [
        "deal_id",
        "seat",
        "contract_type",
        "trump",
        "tricks_won",
        "strategy_id",
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise AssertionError(f"{name}: Missing required columns: {missing_cols}")
    print("  ✓ Required columns present")

    # Check for nulls (trump can be null for high/low)
    non_null_cols = ["deal_id", "seat", "contract_type", "tricks_won", "strategy_id"]
    for col in non_null_cols:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise AssertionError(f"{name}: Column '{col}' has {null_count} null values")
    print("  ✓ No nulls in key columns")

    # Check tricks_won range [0, 10]
    if not df["tricks_won"].between(0, 10).all():
        invalid_count = (~df["tricks_won"].between(0, 10)).sum()
        invalid_vals = df[~df["tricks_won"].between(0, 10)]["tricks_won"].unique()
        raise AssertionError(
            f"{name}: tricks_won out of range [0,10]: {sorted(invalid_vals)}"
        )
    print("  ✓ All tricks_won in valid range [0, 10]")

    # Check contract_type values
    valid_contracts = {"suit", "high", "low"}
    actual_contracts = set(df["contract_type"].unique())
    invalid_contracts = actual_contracts - valid_contracts
    if invalid_contracts:
        raise AssertionError(
            f"{name}: Invalid contract_type values: {invalid_contracts}"
        )
    print(f"  ✓ Contract types valid: {sorted(actual_contracts)}")

    # Check trump for suit contracts
    suit_df = df[df["contract_type"] == "suit"]
    if len(suit_df) > 0:
        valid_trumps = {"C", "D", "H", "S"}
        actual_trumps = set(suit_df["trump"].dropna().unique())
        invalid_trumps = actual_trumps - valid_trumps
        if invalid_trumps:
            raise AssertionError(f"{name}: Invalid trump values: {invalid_trumps}")
        print("  ✓ Trump suits valid for suit contracts")

print("\n" + "=" * 70)
print("✅ Outcome validity PASSED (both datasets)")
print("=" * 70)


# %%
# ============================================================================
# Test 1.2: Deal-Level Invariant (team0_tricks + team1_tricks == 10)
# ============================================================================

print("\n" + "=" * 70)
print("TEST 1.2: Deal-Level Invariant")
print("=" * 70)

for name, df in [("Self-play", df_self), ("Head-to-head", df_h2h)]:
    print(f"\n--- {name} Dataset ---")

    df_deal = make_deal_frame(df)

    # Check that team0_tricks + team1_tricks == 10
    total_tricks = df_deal["team0_tricks"] + df_deal["team1_tricks"]
    if not (total_tricks == 10).all():
        invalid_count = (total_tricks != 10).sum()
        print(f"\n❌ FAIL: {invalid_count} deals violate invariant")
        print("\nSample violations:")
        print(df_deal[total_tricks != 10].head())
        raise AssertionError(f"{name}: team0_tricks + team1_tricks != 10")

    print(f"  ✓ All {len(df_deal)} deals satisfy: team0_tricks + team1_tricks == 10")

print("\n" + "=" * 70)
print("✅ Deal-level invariant PASSED (both datasets)")
print("=" * 70)


# %%
# ============================================================================
# Test 1.3: Reproducibility Check
# ============================================================================

print("\n" + "=" * 70)
print("TEST 1.3: Reproducibility Check")
print("=" * 70)

if True:  # Always generate (reproducibility check needs on-the-fly generation)
    # Re-generate self-play dataset with same seed
    print(f"\nRe-generating self-play dataset with seed={SEED}...")
    df_self_check = load_or_generate_outcomes(
        mode=MODE,
        seed=SEED,
        contracts=CONTRACT_TYPES,
        trumps=TRUMPS_FOR_SUIT_CONTRACTS,
        seats=SEATS,
        strategies=STRATEGIES,
        matchups=None,
    )

    # Compare canonical columns only
    canonical_cols = [
        "deal_id",
        "seat",
        "contract_type",
        "trump",
        "tricks_won",
        "strategy_id",
    ]

    # Sort both by stable keys for comparison
    sort_keys = ["deal_id", "seat", "contract_type", "trump", "strategy_id"]
    df_self_sorted = (
        df_self[canonical_cols].sort_values(sort_keys).reset_index(drop=True)
    )
    df_check_sorted = (
        df_self_check[canonical_cols].sort_values(sort_keys).reset_index(drop=True)
    )

    print("\nComparing datasets (canonical columns only)...")
    print(f"  Dataset 1 shape: {df_self_sorted.shape}")
    print(f"  Dataset 2 shape: {df_check_sorted.shape}")

    # Shape check
    if df_self_sorted.shape != df_check_sorted.shape:
        raise AssertionError(
            f"Shape mismatch: {df_self_sorted.shape} vs {df_check_sorted.shape}"
        )

    # Value check - use fillna for null-safe comparison
    df1_filled = df_self_sorted.fillna("__NULL__")
    df2_filled = df_check_sorted.fillna("__NULL__")
    mismatches = (df1_filled != df2_filled).any(axis=1)
    if mismatches.any():
        mismatch_count = mismatches.sum()
        print(f"\n❌ FAIL: {mismatch_count} rows differ")
        print("\nFirst 5 mismatches (original):")
        print(df_self_sorted[mismatches].head())
        print("\nFirst 5 mismatches (regenerated):")
        print(df_check_sorted[mismatches].head())
        raise AssertionError("Non-deterministic outcomes detected")

    print("  ✓ All rows match")

    print("\n" + "=" * 70)
    print("✅ Reproducibility check PASSED")
    print("=" * 70)
else:
    print("\n⚠️  Reproducibility check skipped (generation disabled)")
    print("    To verify reproducibility, re-run the experiment with the same seed.")
    print("=" * 70)

# %% [markdown]
# ---
#
# ## Section 2: Outcome Distribution Analysis (Self-play)
#
# Analyze outcome distributions using the self-play dataset.
# All plots are faceted by strategy.
#
# **Note:** The logging schema records `tricks_won` as team-level values:
# - Seats 0 & 2 get team0 tricks
# - Seats 1 & 3 get team1 tricks
#
# So seat-level plots show team distributions, not individual performance.

# %% [markdown]
# ### 2.1 By Contract_Type
#
# Outcome distributions grouped by contract type within each strategy.
# Includes ANOVA test to check for differences across contract types.

# %%
# ============================================================================
# 2.1 Outcome Distribution by Contract Type (1 row × N strategies)
# ============================================================================

print("\n2.1 Outcome distributions by contract type (faceted by strategy)...")

strategies = sorted(df_self["strategy_id"].unique())
n_strategies = len(strategies)

# Use deal-level data for proper team separation
df_self_deal = make_deal_frame(df_self)

fig, axes = plt.subplots(1, n_strategies, figsize=(5 * n_strategies, 5), sharey=True)
if n_strategies == 1:
    axes = [axes]

for i, strat in enumerate(strategies):
    ax = axes[i]
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    if len(strat_df_plot) > 0:
        sns.violinplot(
            data=strat_df_plot,
            x="contract_type",
            y="team0_tricks",
            ax=ax,
            palette="Set2",
            inner="quartile",
            order=CONTRACT_TYPES,
        )

        # Statistical test across contract types (paired or independent)
        contract_groups = [
            strat_df[strat_df["contract_type"] == ct]["team0_tricks"].values
            for ct in CONTRACT_TYPES
        ]
        contract_groups = [g for g in contract_groups if len(g) > 0]

        if len(contract_groups) >= 2:
            stat, p_value, test_name = run_contract_comparison(
                strat_df, contract_groups, CONTRACT_TYPES
            )
            status = "⚠️" if p_value < 0.05 else "✓"
            ax.set_title(
                f"{strat}\n(n={len(strat_df)}, {test_name} p={p_value:.3f} {status})"
            )
        else:
            ax.set_title(f"{strat}\n(n={len(strat_df)})")

    ax.set_xlabel("Contract Type")
    ax.set_ylabel("Team 0 Tricks" if i == 0 else "")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis="y", alpha=0.3)

plt.suptitle("Outcome Distribution by Contract Type (deal-level team0_tricks)", y=1.02)
plt.tight_layout()
plt.show()

print("✓ Contract-type distributions plotted with ANOVA tests")

# %% [markdown]
# ### 2.1.1 By Suit (suit contracts only)
#
# Includes ANOVA test for trump bias.

# %%
# ============================================================================
# 2.1.1 Outcome Distribution by Trump Suit (faceted by strategy)
# ============================================================================

print("\n2.1.1 Outcome distributions by trump suit (faceted by strategy)...")

suit_df_self = df_self[df_self["contract_type"] == "suit"]

if len(suit_df_self) > 0:
    fig, axes = plt.subplots(
        1, n_strategies, figsize=(5 * n_strategies, 5), sharey=True
    )
    if n_strategies == 1:
        axes = [axes]

    for i, strat in enumerate(strategies):
        ax = axes[i]
        strat_df = suit_df_self[suit_df_self["strategy_id"] == strat]
        strat_df_plot = downsample_for_plot(strat_df)

        if len(strat_df_plot) > 0:
            sns.violinplot(
                data=strat_df_plot,
                x="trump",
                y="tricks_won",
                ax=ax,
                palette="Set1",
                inner="quartile",
                order=TRUMPS_FOR_SUIT_CONTRACTS,
            )

            # Statistical test for trump bias (paired or independent)
            trump_groups = [
                strat_df[strat_df["trump"] == t]["tricks_won"].values
                for t in TRUMPS_FOR_SUIT_CONTRACTS
            ]
            trump_groups = [g for g in trump_groups if len(g) > 0]

            if len(trump_groups) >= 2:
                # Check if paired (same deal_ids across trump suits)
                paired = is_paired_data(strat_df, "trump")
                if paired and len(trump_groups) >= 3:
                    min_len = min(len(g) for g in trump_groups)
                    aligned = [g[:min_len] for g in trump_groups]
                    stat, p_value = friedmanchisquare(*aligned)
                    test_name = "Friedman"
                else:
                    stat, p_value = f_oneway(*trump_groups)
                    test_name = "ANOVA"
                status = "⚠️" if p_value < 0.05 else "✓"
                ax.set_title(
                    f"{strat}\n(n={len(strat_df)}, {test_name} p={p_value:.3f} {status})"
                )
            else:
                ax.set_title(f"{strat}\n(n={len(strat_df)})")

        ax.set_xlabel("Trump Suit")
        ax.set_ylabel("Tricks Won" if i == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.show()

    print("✓ Trump suit distributions plotted with ANOVA tests")
else:
    print("⚠️  No suit contracts found - skipping trump analysis")

# %% [markdown]
# ### 2.1.2 By High/Low
#
# Includes ANOVA (F-test) comparing high vs low contract distributions.

# %%
# ============================================================================
# 2.1.2 Outcome Distribution: High vs Low (faceted by strategy)
# ============================================================================

print("\n2.1.2 Outcome distributions: high vs low contracts (faceted by strategy)...")

highlow_df = df_self_deal[df_self_deal["contract_type"].isin(["high", "low"])]

if len(highlow_df) > 0:
    fig, axes = plt.subplots(
        1, n_strategies, figsize=(4 * n_strategies, 5), sharey=True
    )
    if n_strategies == 1:
        axes = [axes]

    for i, strat in enumerate(strategies):
        ax = axes[i]
        strat_df = highlow_df[highlow_df["strategy_id"] == strat]
        strat_df_plot = downsample_for_plot(strat_df)

        if len(strat_df_plot) > 0:
            sns.violinplot(
                data=strat_df_plot,
                x="contract_type",
                y="team0_tricks",
                ax=ax,
                palette="Set2",
                inner="quartile",
                order=["high", "low"],
            )

            # Statistical test for high vs low (paired or independent)
            high_vals = strat_df[strat_df["contract_type"] == "high"][
                "team0_tricks"
            ].values
            low_vals = strat_df[strat_df["contract_type"] == "low"][
                "team0_tricks"
            ].values

            if len(high_vals) > 0 and len(low_vals) > 0:
                # Check if paired (same deal_ids in high and low)
                paired = is_paired_data(strat_df, "contract_type")
                if paired:
                    # Align by deal_id for paired t-test
                    high_df = strat_df[strat_df["contract_type"] == "high"][
                        ["deal_id", "team0_tricks"]
                    ]
                    low_df = strat_df[strat_df["contract_type"] == "low"][
                        ["deal_id", "team0_tricks"]
                    ]
                    merged = high_df.merge(
                        low_df, on="deal_id", suffixes=("_high", "_low")
                    )
                    if len(merged) > 1:
                        stat, p_value = ttest_rel(
                            merged["team0_tricks_high"], merged["team0_tricks_low"]
                        )
                        test_name = "Paired t"
                    else:
                        stat, p_value = f_oneway(high_vals, low_vals)
                        test_name = "F"
                else:
                    stat, p_value = f_oneway(high_vals, low_vals)
                    test_name = "F"
                status = "⚠️" if p_value < 0.05 else "✓"
                ax.set_title(
                    f"{strat}\n(n={len(strat_df)}, {test_name}={stat:.2f}, p={p_value:.3f} {status})"
                )
            else:
                ax.set_title(f"{strat}\n(n={len(strat_df)})")

        ax.set_xlabel("Contract Type")
        ax.set_ylabel("Team 0 Tricks" if i == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.show()

    print("✓ High vs Low distributions plotted with ANOVA")
else:
    print("⚠️  No high/low contracts found")

# %% [markdown]
# ### 2.2 By Team
#
# Using deal-level frame to compare team0_tricks vs team1_tricks distributions.
# Self-play should be symmetric (both distributions should be similar).
#
# Includes paired t-test to verify symmetry (expect p >> 0.05 for self-play).

# %%
# ============================================================================
# 2.2 Outcome Distribution by Team (faceted by strategy)
# ============================================================================

print("\n2.2 Outcome distributions by team (faceted by strategy)...")

fig, axes = plt.subplots(1, n_strategies, figsize=(5 * n_strategies, 5), sharey=True)
if n_strategies == 1:
    axes = [axes]

for i, strat in enumerate(strategies):
    ax = axes[i]
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    # Melt to long format for violin plot
    team_data = pd.melt(
        strat_df_plot,
        value_vars=["team0_tricks", "team1_tricks"],
        var_name="team",
        value_name="tricks",
    )
    team_data["team"] = team_data["team"].map(
        {"team0_tricks": "Team 0", "team1_tricks": "Team 1"}
    )

    if len(team_data) > 0:
        sns.violinplot(
            data=team_data,
            x="team",
            y="tricks",
            ax=ax,
            palette="Pastel1",
            inner="quartile",
        )

        # Paired t-test for team symmetry
        mean0 = strat_df["team0_tricks"].mean()
        mean1 = strat_df["team1_tricks"].mean()

        if len(strat_df) > 1:
            t_stat, p_value = ttest_rel(
                strat_df["team0_tricks"], strat_df["team1_tricks"]
            )
            status = "⚠️" if p_value < 0.05 else "✓"
            ax.set_title(
                f"{strat}\n(μ₀={mean0:.2f}, μ₁={mean1:.2f})\nt-test p={p_value:.3f} {status}"
            )
        else:
            ax.set_title(f"{strat}\n(μ₀={mean0:.2f}, μ₁={mean1:.2f})")

    ax.set_xlabel("Team")
    ax.set_ylabel("Tricks Won" if i == 0 else "")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()

print(
    "✓ Team distributions plotted with paired t-tests (self-play should be symmetric)"
)

# %% [markdown]
# ### 2.3 By Seat
#
# ⚠️ **IMPORTANT: Currently Invalid Analysis**
#
# Due to the team-level logging schema, seats within the same team have
# **identical** `tricks_won` values:
# - Seats 0 & 2 (Team 0): show team0_tricks
# - Seats 1 & 3 (Team 1): show team1_tricks
#
# **This section is retained for future use** when seat-level play logging
# is implemented. Until then, these plots show team distributions duplicated
# per seat, NOT individual seat performance.
#
# The violin plots below will show seats 0 & 2 as identical, and seats 1 & 3
# as identical, which is expected given the current logging schema.

# %%
# ============================================================================
# 2.3 Outcome Distribution by Seat (faceted by strategy)
# ============================================================================

print("\n2.3 Outcome distributions by seat (faceted by strategy)...")
print("\n" + "=" * 70)
print("⚠️  WARNING: SEAT-LEVEL ANALYSIS CURRENTLY INVALID")
print("=" * 70)
print("Due to team-level logging schema:")
print("  - Seats 0 & 2 (Team 0): show identical team0_tricks")
print("  - Seats 1 & 3 (Team 1): show identical team1_tricks")
print("\nThese plots show TEAM distributions duplicated per seat,")
print("NOT individual seat performance.")
print("=" * 70 + "\n")

fig, axes = plt.subplots(n_strategies, 3, figsize=(15, 4 * n_strategies), sharey=True)
if n_strategies == 1:
    axes = axes.reshape(1, -1)

for i, strat in enumerate(strategies):
    strat_df = df_self[df_self["strategy_id"] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    for j, contract_type in enumerate(CONTRACT_TYPES):
        ax = axes[i, j]
        contract_df = strat_df_plot[strat_df_plot["contract_type"] == contract_type]

        if len(contract_df) > 0:
            sns.violinplot(
                data=contract_df,
                x="seat",
                y="tricks_won",
                ax=ax,
                palette="Set2",
                inner="quartile",
            )

        ax.set_title(f"{strat} - {contract_type.upper()}\n(⚠️ Team-level data)")
        ax.set_xlabel("Seat")
        ax.set_ylabel("Tricks Won" if j == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Seat-level distributions plotted (note: shows team-level data)")

# %% [markdown]
# ### 2.4 By Contract_Type and Team
#
# Includes t-test per contract type comparing team0 vs team1.

# %%
# ============================================================================
# 2.4 Outcome Distribution by Contract Type and Team
# ============================================================================

print("\n2.4 Outcome distributions by contract type and team...")

fig, axes = plt.subplots(
    n_strategies, len(CONTRACT_TYPES), figsize=(15, 4 * n_strategies), sharey=True
)
if n_strategies == 1:
    axes = axes.reshape(1, -1)

for i, strat in enumerate(strategies):
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    for j, contract_type in enumerate(CONTRACT_TYPES):
        ax = axes[i, j]
        contract_df = strat_df_plot[strat_df_plot["contract_type"] == contract_type]
        contract_df_full = strat_df[strat_df["contract_type"] == contract_type]

        if len(contract_df) > 0:
            # Melt for team comparison
            team_data = pd.melt(
                contract_df,
                value_vars=["team0_tricks", "team1_tricks"],
                var_name="team",
                value_name="tricks",
            )
            team_data["team"] = team_data["team"].map(
                {"team0_tricks": "T0", "team1_tricks": "T1"}
            )

            sns.violinplot(
                data=team_data,
                x="team",
                y="tricks",
                ax=ax,
                palette="Pastel1",
                inner="quartile",
            )

            mean0 = contract_df_full["team0_tricks"].mean()
            mean1 = contract_df_full["team1_tricks"].mean()

            # Paired t-test for this contract type
            if len(contract_df_full) > 1:
                t_stat, p_value = ttest_rel(
                    contract_df_full["team0_tricks"], contract_df_full["team1_tricks"]
                )
                status = "⚠️" if p_value < 0.05 else "✓"
                ax.set_title(
                    f"{strat} / {contract_type.upper()}\n(μ₀={mean0:.2f}, μ₁={mean1:.2f})\np={p_value:.3f} {status}"
                )
            else:
                ax.set_title(
                    f"{strat} / {contract_type.upper()}\n(μ₀={mean0:.2f}, μ₁={mean1:.2f})"
                )

        ax.set_xlabel("Team")
        ax.set_ylabel("Tricks Won" if j == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Contract×Team distributions plotted with t-tests")

# %% [markdown]
# ---
#
# ## Section 3: Strategy Analysis (Head-to-head)
#
# Analyze strategy matchups using the head-to-head dataset with full N×N matrix.

# %%
# ============================================================================
# Build Deal-Level Head-to-Head Frame
# ============================================================================

print("\nBuilding deal-level head-to-head frame...")

# Create deal-level frame from h2h data
df_h2h_deal = make_deal_frame(df_h2h)

# Add team strategy columns
df_h2h_deal = df_h2h_deal.merge(
    df_h2h[
        [
            "deal_id",
            "contract_type",
            "trump",
            "strategy_id",
            "team0_strategy",
            "team1_strategy",
        ]
    ].drop_duplicates(),
    on=["deal_id", "contract_type", "trump", "strategy_id"],
    how="left",
)

print(f"Deal-level H2H frame: {len(df_h2h_deal)} rows")
print(
    f"Unique matchups: {df_h2h_deal.groupby(['team0_strategy', 'team1_strategy']).ngroups}"
)

# %% [markdown]
# ### 3.1 Win Rate Heatmap
#
# N×N matrix showing P(team0_tricks >= 6) for each matchup.

# %%
# ============================================================================
# Heatmap A: Win Rate (P(team0_tricks >= 6))
# ============================================================================

print("\n3.1 Win rate heatmap (P(team0 wins))...")

# Compute win rate for each matchup
win_rate_pivot = (
    df_h2h_deal.groupby(["team0_strategy", "team1_strategy"])["team0_win"]
    .mean()
    .unstack()
)

# Ensure consistent ordering
win_rate_pivot = win_rate_pivot.reindex(index=STRATEGY_NAMES, columns=STRATEGY_NAMES)

plt.figure(figsize=(10, 8))
sns.heatmap(
    win_rate_pivot,
    annot=True,
    fmt=".3f",
    cmap="RdYlGn",
    vmin=0,
    vmax=1,
    center=0.5,
    xticklabels=STRATEGY_NAMES,
    yticklabels=STRATEGY_NAMES,
)
plt.title(
    "Win Rate Heatmap: P(Team 0 Wins)\nRows = Team 0 strategy, Cols = Team 1 strategy"
)
plt.xlabel("Team 1 Strategy")
plt.ylabel("Team 0 Strategy")
plt.tight_layout()
plt.show()

print("✓ Win rate heatmap plotted")
print("\nExpected: Diagonal (self-play) should be ~0.5")
diag_values = [
    win_rate_pivot.loc[s, s]
    for s in STRATEGY_NAMES
    if pd.notna(win_rate_pivot.loc[s, s])
]
if diag_values:
    print(f"Diagonal win rates: {[f'{v:.3f}' for v in diag_values]}")

# %% [markdown]
# ### 3.2 Mean Delta Heatmap
#
# N×N matrix showing E[team0_tricks - team1_tricks] for each matchup.

# %%
# ============================================================================
# Heatmap B: Mean Delta (E[team0_tricks - team1_tricks])
# ============================================================================

print("\n3.2 Mean delta heatmap (E[delta])...")

# Compute mean delta for each matchup
delta_pivot = (
    df_h2h_deal.groupby(["team0_strategy", "team1_strategy"])["delta_tricks"]
    .mean()
    .unstack()
)

# Ensure consistent ordering
delta_pivot = delta_pivot.reindex(index=STRATEGY_NAMES, columns=STRATEGY_NAMES)

plt.figure(figsize=(10, 8))
sns.heatmap(
    delta_pivot,
    annot=True,
    fmt=".2f",
    cmap="RdBu_r",
    vmin=-5,
    vmax=5,
    center=0,
    xticklabels=STRATEGY_NAMES,
    yticklabels=STRATEGY_NAMES,
)
plt.title(
    "Mean Delta Heatmap: E[Team 0 Tricks - Team 1 Tricks]\nRows = Team 0 strategy, Cols = Team 1 strategy"
)
plt.xlabel("Team 1 Strategy")
plt.ylabel("Team 0 Strategy")
plt.tight_layout()
plt.show()

print("✓ Mean delta heatmap plotted")
print("\nExpected: Diagonal (self-play) should be ~0")
diag_deltas = [
    delta_pivot.loc[s, s] for s in STRATEGY_NAMES if pd.notna(delta_pivot.loc[s, s])
]
if diag_deltas:
    print(f"Diagonal deltas: {[f'{v:.2f}' for v in diag_deltas]}")

# Explain non-zero diagonal
print("\n📊 Note: Diagonal values may not be exactly 0")
print("   Self-play delta should theoretically be 0, but finite samples")
print("   introduce sampling variance. With N deals, expect |δ| ≈ σ/√N")
n_deals_approx = (
    len(df_h2h_deal) // len(MATCHUPS_MATRIX) if len(MATCHUPS_MATRIX) > 0 else 100
)
std_approx = df_h2h_deal["delta_tricks"].std()
expected_delta = std_approx / np.sqrt(n_deals_approx) if n_deals_approx > 0 else 0
print(
    f"   For N≈{n_deals_approx}, σ≈{std_approx:.1f}, expect |δ| ≈ {expected_delta:.2f}"
)

# %% [markdown]
# ### 3.3 Distribution Grid: Team 0 Tricks
#
# N×N subplot grid showing violin plots of team0_tricks for each matchup.

# %%
# ============================================================================
# Distribution Grid 1: Team 0 Tricks
# ============================================================================

print("\n3.3 Distribution grid: team0_tricks...")

n = len(STRATEGY_NAMES)
fig, axes = plt.subplots(n, n, figsize=(3 * n, 3 * n), sharex=True, sharey=True)

for i, s0 in enumerate(STRATEGY_NAMES):
    for j, s1 in enumerate(STRATEGY_NAMES):
        ax = axes[i, j]
        matchup_df = df_h2h_deal[
            (df_h2h_deal["team0_strategy"] == s0)
            & (df_h2h_deal["team1_strategy"] == s1)
        ]

        if len(matchup_df) > 0:
            matchup_plot = downsample_for_plot(matchup_df)
            # Violin only (no box overlay as per plan)
            ax.violinplot(
                matchup_plot["team0_tricks"].dropna(), positions=[0], showmedians=True
            )
            mean_val = matchup_df["team0_tricks"].mean()
            ax.axhline(mean_val, color="red", linestyle="--", linewidth=0.5, alpha=0.7)
            ax.text(
                0.95,
                0.95,
                f"μ={mean_val:.1f}",
                transform=ax.transAxes,
                fontsize=7,
                va="top",
                ha="right",
            )

        ax.set_ylim(-0.5, 10.5)
        ax.set_xticks([])
        ax.grid(axis="y", alpha=0.3)

        # Labels
        if i == 0:
            ax.set_title(s1[:8], fontsize=9)
        if j == 0:
            ax.set_ylabel(s0[:8], fontsize=9)

fig.suptitle(
    "Team 0 Tricks by Matchup\n(rows = team0, cols = team1)", y=1.02, fontsize=12
)
plt.tight_layout()
plt.show()

print("✓ Team 0 tricks distribution grid plotted")

# %% [markdown]
# ### 3.4 Distribution Grid: Delta Tricks
#
# N×N subplot grid showing violin plots of delta_tricks for each matchup.

# %%
# ============================================================================
# Distribution Grid 2: Delta Tricks
# ============================================================================

print("\n3.4 Distribution grid: delta_tricks...")

fig, axes = plt.subplots(n, n, figsize=(3 * n, 3 * n), sharex=True, sharey=True)

for i, s0 in enumerate(STRATEGY_NAMES):
    for j, s1 in enumerate(STRATEGY_NAMES):
        ax = axes[i, j]
        matchup_df = df_h2h_deal[
            (df_h2h_deal["team0_strategy"] == s0)
            & (df_h2h_deal["team1_strategy"] == s1)
        ]

        if len(matchup_df) > 0:
            matchup_plot = downsample_for_plot(matchup_df)
            ax.violinplot(
                matchup_plot["delta_tricks"].dropna(), positions=[0], showmedians=True
            )
            mean_val = matchup_df["delta_tricks"].mean()
            ax.axhline(mean_val, color="red", linestyle="--", linewidth=0.5, alpha=0.7)
            ax.axhline(0, color="gray", linestyle="-", linewidth=0.5, alpha=0.5)
            ax.text(
                0.95,
                0.95,
                f"μ={mean_val:+.1f}",
                transform=ax.transAxes,
                fontsize=7,
                va="top",
                ha="right",
            )

        ax.set_ylim(-10.5, 10.5)
        ax.set_xticks([])
        ax.grid(axis="y", alpha=0.3)

        # Labels
        if i == 0:
            ax.set_title(s1[:8], fontsize=9)
        if j == 0:
            ax.set_ylabel(s0[:8], fontsize=9)

fig.suptitle(
    "Delta Tricks by Matchup (Team 0 - Team 1)\n(rows = team0, cols = team1)",
    y=1.02,
    fontsize=12,
)
plt.tight_layout()
plt.show()

print("✓ Delta tricks distribution grid plotted")

# %% [markdown]
# ### 3.5 Tabular Summary

# %%
# ============================================================================
# Tabular Summary of All Matchups
# ============================================================================

print("\n3.5 Tabular summary of all matchups...")

matchup_summary = (
    df_h2h_deal.groupby(["team0_strategy", "team1_strategy"])
    .agg(
        n=("deal_id", "count"),
        mean_team0=("team0_tricks", "mean"),
        mean_delta=("delta_tricks", "mean"),
        win_rate=("team0_win", "mean"),
    )
    .round(3)
    .reset_index()
)

matchup_summary = matchup_summary.rename(
    columns={
        "team0_strategy": "team0",
        "team1_strategy": "team1",
    }
)

print("\nMatchup Summary Table:")
print(matchup_summary.to_string(index=False))

# %% [markdown]
# ### 3.6 Strategy Sanity Tests
#
# Automated validation tests for strategy behavior:
# - **3.6.1 Self-Play Fairness**: Self-play delta should be ~0
# - **3.6.2 Transitivity Sanity**: If A > B and B > C, then A should > C (WARN on violations)
# - **3.6.3 Random Baseline Dominance**: Smart strategies must beat random
# - **3.6.4 Deterministic Strategy Consistency**: Variance check for deterministic strategies
# - **3.6.5 Rankings Stability**: Kendall's tau for strategy rankings across contract types

# %%
# ============================================================================
# Section 3.6: Strategy Sanity Tests
# ============================================================================

print("\n" + "=" * 70)
print("SECTION 3.6: STRATEGY SANITY TESTS")
print("=" * 70)

sanity_results = {"passes": [], "warnings": [], "failures": []}

# %%
# --- 3.6.1 Self-Play Fairness ---
print("\n--- 3.6.1 Self-Play Fairness ---")
print("Test: Self-play mean delta should be ~0 (within CI)")

for strat in STRATEGY_NAMES:
    # Filter self-play matchups for this strategy
    self_play_df = df_h2h_deal[
        (df_h2h_deal["team0_strategy"] == strat)
        & (df_h2h_deal["team1_strategy"] == strat)
    ]

    if len(self_play_df) < 10:
        sanity_results["warnings"].append(
            f"3.6.1 {strat}: Insufficient self-play data (n={len(self_play_df)})"
        )
        continue

    mean_delta = self_play_df["delta_tricks"].mean()
    std_delta = self_play_df["delta_tricks"].std()
    n = len(self_play_df)

    # Bootstrap 95% CI
    rng = np.random.default_rng(SEED)
    bootstrap_means = [
        np.mean(rng.choice(self_play_df["delta_tricks"].values, size=n, replace=True))
        for _ in range(1000)
    ]
    ci_lower, ci_upper = np.percentile(bootstrap_means, [2.5, 97.5])

    # Test: CI contains 0 OR |mean| < 0.25
    ci_contains_zero = ci_lower <= 0 <= ci_upper
    mean_near_zero = abs(mean_delta) < 0.25

    if ci_contains_zero or mean_near_zero:
        sanity_results["passes"].append(
            f"3.6.1 {strat}: Self-play fair (μ={mean_delta:.3f}, CI=[{ci_lower:.3f}, {ci_upper:.3f}])"
        )
        print(
            f"  PASS: {strat} μ={mean_delta:.3f}, 95% CI=[{ci_lower:.3f}, {ci_upper:.3f}]"
        )
    elif abs(mean_delta) >= 0.5:
        sanity_results["failures"].append(
            f"3.6.1 {strat}: Self-play bias detected (μ={mean_delta:.3f}, CI=[{ci_lower:.3f}, {ci_upper:.3f}])"
        )
        print(
            f"  FAIL: {strat} μ={mean_delta:.3f}, 95% CI=[{ci_lower:.3f}, {ci_upper:.3f}] (|μ| >= 0.5)"
        )
    else:
        sanity_results["warnings"].append(
            f"3.6.1 {strat}: Self-play marginal (μ={mean_delta:.3f}, CI=[{ci_lower:.3f}, {ci_upper:.3f}])"
        )
        print(
            f"  WARN: {strat} μ={mean_delta:.3f}, 95% CI=[{ci_lower:.3f}, {ci_upper:.3f}]"
        )

# %%
# --- 3.6.2 Transitivity Sanity ---
print("\n--- 3.6.2 Transitivity Sanity ---")
print("Test: If A > B and B > C, then A should > C (informational)")

# Build win matrix from head-to-head results
win_matrix = {}
for strat in STRATEGY_NAMES:
    win_matrix[strat] = {}
    for opp in STRATEGY_NAMES:
        if strat == opp:
            win_matrix[strat][opp] = 0.5
            continue
        matchup_df = df_h2h_deal[
            (df_h2h_deal["team0_strategy"] == strat)
            & (df_h2h_deal["team1_strategy"] == opp)
        ]
        if len(matchup_df) > 0:
            win_matrix[strat][opp] = matchup_df["team0_win"].mean()
        else:
            win_matrix[strat][opp] = np.nan

# Check transitivity
transitivity_violations = []
for a in STRATEGY_NAMES:
    for b in STRATEGY_NAMES:
        if a == b:
            continue
        for c in STRATEGY_NAMES:
            if c == a or c == b:
                continue
            # A > B means win_matrix[A][B] > 0.5
            a_beats_b = win_matrix[a].get(b, np.nan) > 0.5
            b_beats_c = win_matrix[b].get(c, np.nan) > 0.5
            a_beats_c = win_matrix[a].get(c, np.nan) > 0.5

            if a_beats_b and b_beats_c and not a_beats_c:
                transitivity_violations.append(
                    f"{a} > {b} > {c}, but {a} does not > {c}"
                )

if transitivity_violations:
    for v in transitivity_violations[:5]:  # Show max 5
        print(f"  WARN: {v}")
    sanity_results["warnings"].append(
        f"3.6.2 Transitivity: {len(transitivity_violations)} violation(s) detected"
    )
else:
    sanity_results["passes"].append("3.6.2 Transitivity: No violations detected")
    print("  PASS: No transitivity violations detected")

# %%
# --- 3.6.3 Random Baseline Dominance ---
print("\n--- 3.6.3 Random Baseline Dominance ---")
print("Test: greedy and glutton must beat random (win_rate > 0.5)")

SMART_STRATEGIES = ["greedy", "glutton"]
RANDOM_STRATEGY = "random"

for smart in SMART_STRATEGIES:
    # Smart as team0 vs random as team1
    matchup_df = df_h2h_deal[
        (df_h2h_deal["team0_strategy"] == smart)
        & (df_h2h_deal["team1_strategy"] == RANDOM_STRATEGY)
    ]

    if len(matchup_df) < 10:
        sanity_results["warnings"].append(
            f"3.6.3 {smart} vs random: Insufficient data (n={len(matchup_df)})"
        )
        continue

    win_rate = matchup_df["team0_win"].mean()
    n = len(matchup_df)

    # Wilson score confidence interval
    z = 1.96  # 95% CI
    p = win_rate
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    wilson_lower = center - margin
    wilson_upper = center + margin

    if win_rate > 0.5 and wilson_lower > 0.5:
        sanity_results["passes"].append(
            f"3.6.3 {smart} vs random: Dominance confirmed (win_rate={win_rate:.3f}, CI=[{wilson_lower:.3f}, {wilson_upper:.3f}])"
        )
        print(
            f"  PASS: {smart} beats random (win_rate={win_rate:.3f}, Wilson CI=[{wilson_lower:.3f}, {wilson_upper:.3f}])"
        )
    elif win_rate <= 0.5:
        sanity_results["failures"].append(
            f"3.6.3 {smart} vs random: Failed to beat random (win_rate={win_rate:.3f})"
        )
        print(f"  FAIL: {smart} does not beat random (win_rate={win_rate:.3f})")
    else:
        sanity_results["warnings"].append(
            f"3.6.3 {smart} vs random: Marginal (win_rate={win_rate:.3f}, CI lower={wilson_lower:.3f})"
        )
        print(
            f"  WARN: {smart} marginally beats random (win_rate={win_rate:.3f}, Wilson CI lower={wilson_lower:.3f})"
        )

# %%
# --- 3.6.4 Deterministic Strategy Consistency ---
print("\n--- 3.6.4 Deterministic Strategy Consistency ---")
print("Test: Deterministic strategies should have variance <= random * 1.2")

DETERMINISTIC_STRATEGIES = ["always_highest", "always_lowest", "greedy", "glutton"]

# Get random strategy variance as baseline
random_self_play = df_h2h_deal[
    (df_h2h_deal["team0_strategy"] == "random")
    & (df_h2h_deal["team1_strategy"] == "random")
]
if len(random_self_play) > 0:
    random_variance = random_self_play["delta_tricks"].var()
    print(f"  Random self-play variance: {random_variance:.3f}")

    for strat in DETERMINISTIC_STRATEGIES:
        strat_self_play = df_h2h_deal[
            (df_h2h_deal["team0_strategy"] == strat)
            & (df_h2h_deal["team1_strategy"] == strat)
        ]

        if len(strat_self_play) < 10:
            continue

        strat_variance = strat_self_play["delta_tricks"].var()
        variance_ratio = (
            strat_variance / random_variance if random_variance > 0 else np.inf
        )

        if variance_ratio <= 1.2:
            sanity_results["passes"].append(
                f"3.6.4 {strat}: Variance consistent (var={strat_variance:.3f}, ratio={variance_ratio:.2f})"
            )
            print(
                f"  PASS: {strat} var={strat_variance:.3f}, ratio to random={variance_ratio:.2f}"
            )
        else:
            sanity_results["warnings"].append(
                f"3.6.4 {strat}: Higher variance than expected (var={strat_variance:.3f}, ratio={variance_ratio:.2f})"
            )
            print(
                f"  WARN: {strat} var={strat_variance:.3f}, ratio to random={variance_ratio:.2f} > 1.2"
            )
else:
    sanity_results["warnings"].append("3.6.4: No random self-play data for baseline")
    print("  SKIP: No random self-play data available")

# %%
# --- 3.6.5 Rankings Stability ---
print("\n--- 3.6.5 Rankings Stability ---")
print(
    "Test: Strategy rankings should be stable across contract types (Kendall's tau > 0.6)"
)

# Compute rankings per contract type
rankings_by_contract = {}
for ct in CONTRACT_TYPES:
    ct_df = df_h2h_deal[df_h2h_deal["contract_type"] == ct]

    # Compute average delta for each strategy (as team0)
    strat_performance = {}
    for strat in STRATEGY_NAMES:
        strat_df = ct_df[ct_df["team0_strategy"] == strat]
        if len(strat_df) > 0:
            strat_performance[strat] = strat_df["delta_tricks"].mean()

    if len(strat_performance) >= 3:
        # Rank strategies by performance (higher delta = better)
        rankings_by_contract[ct] = sorted(
            strat_performance.keys(), key=lambda s: strat_performance[s], reverse=True
        )

# Compute pairwise Kendall's tau
if len(rankings_by_contract) >= 2:
    contract_types_with_rankings = list(rankings_by_contract.keys())
    tau_results = []

    for i, ct1 in enumerate(contract_types_with_rankings):
        for ct2 in contract_types_with_rankings[i + 1 :]:
            # Convert rankings to numeric for Kendall's tau
            rank1 = rankings_by_contract[ct1]
            rank2 = rankings_by_contract[ct2]

            # Get common strategies
            common = [s for s in rank1 if s in rank2]
            if len(common) < 3:
                continue

            # Create rank arrays
            r1 = [rank1.index(s) for s in common]
            r2 = [rank2.index(s) for s in common]

            tau, p_val = kendalltau(r1, r2)
            tau_results.append(
                {
                    "contract1": ct1,
                    "contract2": ct2,
                    "tau": tau,
                    "p_value": p_val,
                }
            )
            print(f"  {ct1} vs {ct2}: tau={tau:.3f}, p={p_val:.3f}")

    if tau_results:
        all_tau = [r["tau"] for r in tau_results]
        min_tau = min(all_tau)

        if min_tau > 0.6:
            sanity_results["passes"].append(
                f"3.6.5 Rankings: Stable across contracts (min tau={min_tau:.3f})"
            )
            print(f"  PASS: All pairwise tau > 0.6 (min={min_tau:.3f})")
        elif min_tau >= 0.3:
            sanity_results["warnings"].append(
                f"3.6.5 Rankings: Moderate stability (min tau={min_tau:.3f})"
            )
            print(f"  WARN: Some pairwise tau in [0.3, 0.6] (min={min_tau:.3f})")
        else:
            sanity_results["failures"].append(
                f"3.6.5 Rankings: Unstable (min tau={min_tau:.3f})"
            )
            print(f"  FAIL: Rankings unstable (min tau={min_tau:.3f} < 0.3)")
else:
    sanity_results["warnings"].append(
        "3.6.5 Rankings: Insufficient contract types for comparison"
    )
    print("  SKIP: Insufficient contract types for ranking comparison")

# %%
# --- Sanity Test Summary ---
print("\n" + "=" * 70)
print("STRATEGY SANITY TEST SUMMARY")
print("=" * 70)

print(f"\nPASSES ({len(sanity_results['passes'])}):")
for item in sanity_results["passes"]:
    print(f"  ✅ {item}")

if sanity_results["warnings"]:
    print(f"\nWARNINGS ({len(sanity_results['warnings'])}):")
    for item in sanity_results["warnings"]:
        print(f"  ⚠️  {item}")

if sanity_results["failures"]:
    print(f"\nFAILURES ({len(sanity_results['failures'])}):")
    for item in sanity_results["failures"]:
        print(f"  ❌ {item}")

    print("\n" + "=" * 70)
    print("⚠️  STRATEGY SANITY TESTS DETECTED FAILURES")
    print("=" * 70)
    # Note: We don't raise AssertionError in SMOKE mode as data may be insufficient
    if MODE != "SMOKE":
        assert (
            len(sanity_results["failures"]) == 0
        ), f"Strategy sanity tests failed: {sanity_results['failures']}"
else:
    print("\n" + "=" * 70)
    print("✅ ALL STRATEGY SANITY TESTS PASSED")
    print("=" * 70)

# %% [markdown]
# ---
#
# ## Section 4: Distribution Analysis (CDF/CCDF)
#
# Cumulative distribution functions to examine tail behavior.
#
# **Important:** CDFs are computed from deal-level data using `team0_tricks` only
# to avoid mixing complementary distributions (team0 + team1 = 10 tricks).

# %% [markdown]
# ### 4.1 CDF by Contract Type

# %%
# ============================================================================
# 4.1 CDF: Cumulative Distribution Function (by contract type)
# ============================================================================

print("\n4.1 CDF of team0_tricks by contract type (deal-level)...")

fig, ax = plt.subplots(figsize=(10, 6))

# Use deal-level self-play data for clean CDF
for contract_type in CONTRACT_TYPES:
    contract_df = df_self_deal[df_self_deal["contract_type"] == contract_type]

    if len(contract_df) > 0:
        # Compute CDF using team0_tricks only
        sorted_tricks = np.sort(contract_df["team0_tricks"])
        cdf = np.arange(1, len(sorted_tricks) + 1) / len(sorted_tricks)

        ax.plot(
            sorted_tricks,
            cdf,
            marker="o",
            markersize=3,
            linestyle="-",
            label=f"{contract_type.upper()} (n={len(contract_df)})",
            alpha=0.7,
        )

ax.set_xlabel("Team 0 Tricks")
ax.set_ylabel("Cumulative Probability")
ax.set_title("CDF of Team 0 Tricks by Contract Type (Self-play, deal-level)")
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(0, 1)
ax.grid(alpha=0.3)
ax.legend()
plt.tight_layout()
plt.show()

print("✓ CDF plotted (deal-level team0_tricks)")

# %% [markdown]
# ### 4.2 CDF by Strategy

# %%
# ============================================================================
# 4.2 CDF by Strategy (self-play)
# ============================================================================

print("\n4.2 CDF of team0_tricks by strategy...")

fig, ax = plt.subplots(figsize=(10, 6))

for strat in strategies:
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]

    if len(strat_df) > 0:
        sorted_tricks = np.sort(strat_df["team0_tricks"])
        cdf = np.arange(1, len(sorted_tricks) + 1) / len(sorted_tricks)

        ax.plot(
            sorted_tricks,
            cdf,
            marker="o",
            markersize=3,
            linestyle="-",
            label=f"{strat} (n={len(strat_df)})",
            alpha=0.7,
        )

ax.set_xlabel("Team 0 Tricks")
ax.set_ylabel("Cumulative Probability")
ax.set_title("CDF of Team 0 Tricks by Strategy (Self-play, deal-level)")
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(0, 1)
ax.grid(alpha=0.3)
ax.legend()
plt.tight_layout()
plt.show()

print("✓ CDF by strategy plotted")

# %% [markdown]
# ### 4.3 CDF by Contract Type × Strategy

# %%
# ============================================================================
# 4.3 CDF by Contract Type and Strategy (facet grid)
# ============================================================================

print("\n4.3 CDF by contract type and strategy...")

fig, axes = plt.subplots(
    1, len(CONTRACT_TYPES), figsize=(5 * len(CONTRACT_TYPES), 5), sharey=True
)

for j, contract_type in enumerate(CONTRACT_TYPES):
    ax = axes[j]

    for strat in strategies:
        strat_contract_df = df_self_deal[
            (df_self_deal["strategy_id"] == strat)
            & (df_self_deal["contract_type"] == contract_type)
        ]

        if len(strat_contract_df) > 0:
            sorted_tricks = np.sort(strat_contract_df["team0_tricks"])
            cdf = np.arange(1, len(sorted_tricks) + 1) / len(sorted_tricks)

            ax.plot(
                sorted_tricks,
                cdf,
                marker="o",
                markersize=2,
                linestyle="-",
                label=strat,
                alpha=0.7,
            )

    ax.set_xlabel("Team 0 Tricks")
    ax.set_ylabel("Cumulative Probability" if j == 0 else "")
    ax.set_title(f"{contract_type.upper()} Contracts")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)

plt.suptitle("CDF by Contract Type × Strategy (Self-play)", y=1.02)
plt.tight_layout()
plt.show()

print("✓ CDF by contract×strategy plotted")

# %% [markdown]
# ### 4.4 KDE Overall Distribution

# %%
# ============================================================================
# 4.4 KDE: Kernel Density Estimate of Tricks Distribution
# ============================================================================

print("\n4.4 KDE of team0_tricks (overall distribution)...")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# KDE by contract type
ax1 = axes[0]
for contract_type in CONTRACT_TYPES:
    contract_df = df_self_deal[df_self_deal["contract_type"] == contract_type]
    if len(contract_df) > 10:  # Need enough points for KDE
        sns.kdeplot(
            data=contract_df,
            x="team0_tricks",
            ax=ax1,
            label=f"{contract_type.upper()} (n={len(contract_df)})",
            fill=True,
            alpha=0.3,
        )

ax1.set_xlabel("Team 0 Tricks")
ax1.set_ylabel("Density")
ax1.set_title("KDE by Contract Type (Self-play)")
ax1.set_xlim(-0.5, 10.5)
ax1.legend()
ax1.grid(alpha=0.3)

# KDE by strategy
ax2 = axes[1]
for strat in strategies:
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]
    if len(strat_df) > 10:
        sns.kdeplot(
            data=strat_df, x="team0_tricks", ax=ax2, label=strat, fill=True, alpha=0.3
        )

ax2.set_xlabel("Team 0 Tricks")
ax2.set_ylabel("Density")
ax2.set_title("KDE by Strategy (Self-play)")
ax2.set_xlim(-0.5, 10.5)
ax2.legend()
ax2.grid(alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ KDE distributions plotted")

# %% [markdown]
# ### 4.5 PMF: Probability Mass Function (Percentile Plot)

# %%
# ============================================================================
# 4.5 PMF: P(tricks_won = k) for k = 0..10
# ============================================================================

print("\n4.5 PMF of team0_tricks (probability mass function)...")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# PMF by contract type
ax1 = axes[0]
k_values = np.arange(11)
width = 0.25
offsets = np.linspace(-width, width, len(CONTRACT_TYPES))

for idx, contract_type in enumerate(CONTRACT_TYPES):
    contract_df = df_self_deal[df_self_deal["contract_type"] == contract_type]
    if len(contract_df) > 0:
        pmf = [(contract_df["team0_tricks"] == k).mean() for k in k_values]
        ax1.bar(
            k_values + offsets[idx],
            pmf,
            width=width,
            label=contract_type.upper(),
            alpha=0.7,
        )

ax1.set_xlabel("Team 0 Tricks (k)")
ax1.set_ylabel("P(tricks = k)")
ax1.set_title("PMF by Contract Type")
ax1.set_xticks(k_values)
ax1.legend()
ax1.grid(axis="y", alpha=0.3)

# PMF by strategy
ax2 = axes[1]
offsets_strat = np.linspace(-0.3, 0.3, len(strategies))
width_strat = 0.6 / len(strategies)

for idx, strat in enumerate(strategies):
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]
    if len(strat_df) > 0:
        pmf = [(strat_df["team0_tricks"] == k).mean() for k in k_values]
        ax2.bar(
            k_values + offsets_strat[idx],
            pmf,
            width=width_strat,
            label=strat,
            alpha=0.7,
        )

ax2.set_xlabel("Team 0 Tricks (k)")
ax2.set_ylabel("P(tricks = k)")
ax2.set_title("PMF by Strategy")
ax2.set_xticks(k_values)
ax2.legend(fontsize=8)
ax2.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.show()

# Print percentile table
print("\nPercentile Table (% of deals where team0 wins k tricks):")
print("-" * 60)
print(f"{'k':>4} | ", end="")
for ct in CONTRACT_TYPES:
    print(f"{ct:>10}", end=" | ")
print()
print("-" * 60)
for k in k_values:
    print(f"{k:>4} | ", end="")
    for ct in CONTRACT_TYPES:
        ct_df = df_self_deal[df_self_deal["contract_type"] == ct]
        if len(ct_df) > 0:
            pct = (ct_df["team0_tricks"] == k).mean() * 100
            print(f"{pct:>9.1f}%", end=" | ")
        else:
            print(f"{'N/A':>10}", end=" | ")
    print()
print("-" * 60)

# Print percentile table by strategy (overall)
print("\nPercentile Table by Strategy (% of deals where team0 wins k tricks):")
print("-" * 80)
header = f"{'k':>4} | "
for strat in strategies:
    header += f"{strat[:12]:>12} | "
print(header)
print("-" * 80)
for k in k_values:
    row = f"{k:>4} | "
    for strat in strategies:
        strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]
        if len(strat_df) > 0:
            pct = (strat_df["team0_tricks"] == k).mean() * 100
            row += f"{pct:>11.1f}% | "
        else:
            row += f"{'N/A':>12} | "
    print(row)
print("-" * 80)

# Print percentile tables by strategy × contract type
for ct in CONTRACT_TYPES:
    ct_df = df_self_deal[df_self_deal["contract_type"] == ct]
    if len(ct_df) == 0:
        continue

    print(f"\nPercentile Table: {ct.upper()} Contracts by Strategy")
    print("-" * 80)
    header = f"{'k':>4} | "
    for strat in strategies:
        header += f"{strat[:12]:>12} | "
    print(header)
    print("-" * 80)
    for k in k_values:
        row = f"{k:>4} | "
        for strat in strategies:
            strat_ct_df = ct_df[ct_df["strategy_id"] == strat]
            if len(strat_ct_df) > 0:
                pct = (strat_ct_df["team0_tricks"] == k).mean() * 100
                row += f"{pct:>11.1f}% | "
            else:
                row += f"{'N/A':>12} | "
        print(row)
    print("-" * 80)

print("✓ PMF plotted")

# %% [markdown]
# ### 4.6 CDF by Team (Symmetry Check)

# %%
# ============================================================================
# 4.6 CDF by Team: Compare team0 vs team1 distributions
# ============================================================================

print("\n4.6 CDF comparison: team0 vs team1 (symmetry check)...")

fig, axes = plt.subplots(1, n_strategies, figsize=(5 * n_strategies, 5), sharey=True)
if n_strategies == 1:
    axes = [axes]

for i, strat in enumerate(strategies):
    ax = axes[i]
    strat_df = df_self_deal[df_self_deal["strategy_id"] == strat]

    if len(strat_df) > 0:
        # CDF for team0
        sorted_t0 = np.sort(strat_df["team0_tricks"])
        cdf_t0 = np.arange(1, len(sorted_t0) + 1) / len(sorted_t0)
        ax.plot(
            sorted_t0, cdf_t0, "b-", marker="o", markersize=3, alpha=0.7, label="Team 0"
        )

        # CDF for team1
        sorted_t1 = np.sort(strat_df["team1_tricks"])
        cdf_t1 = np.arange(1, len(sorted_t1) + 1) / len(sorted_t1)
        ax.plot(
            sorted_t1,
            cdf_t1,
            "r--",
            marker="x",
            markersize=3,
            alpha=0.7,
            label="Team 1",
        )

        # Note: In self-play, these should overlap perfectly
        ax.set_title(f"{strat}\n(n={len(strat_df)})")

    ax.set_xlabel("Tricks Won")
    ax.set_ylabel("Cumulative Probability" if i == 0 else "")
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend()

plt.suptitle(
    "CDF by Team (Self-play symmetry check)\nBlue=Team0, Red=Team1 (should overlap in self-play)",
    y=1.02,
)
plt.tight_layout()
plt.show()

print("✓ Team symmetry CDF plotted")
print("Note: In self-play, team0 and team1 CDFs should overlap perfectly.")

# %% [markdown]
# ### 4.7 CCDF: Discrete Survival Function

# %%
# ============================================================================
# 4.7 CCDF: Discrete Survival Function P(X >= k)
# ============================================================================

print("\n4.7 CCDF (discrete survival) of team0_tricks by contract type...")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Full range plot
ax1 = axes[0]
for contract_type in CONTRACT_TYPES:
    contract_df = df_self_deal[df_self_deal["contract_type"] == contract_type]

    if len(contract_df) > 0:
        # Compute discrete survival P(X >= k) for k = 0..10
        k_values = np.arange(11)
        survival_probs = [(contract_df["team0_tricks"] >= k).mean() for k in k_values]

        ax1.step(
            k_values,
            survival_probs,
            where="post",
            marker="o",
            markersize=4,
            label=f"{contract_type.upper()} (n={len(contract_df)})",
            alpha=0.8,
        )

ax1.set_xlabel("k (Tricks)")
ax1.set_ylabel("P(Tricks >= k)")
ax1.set_title("CCDF: Survival Function (Full Range)")
ax1.set_xlim(-0.5, 10.5)
ax1.set_ylim(0, 1.05)
ax1.grid(alpha=0.3)
ax1.legend()

# Tail-only plot (k >= 6) with log scale
ax2 = axes[1]
for contract_type in CONTRACT_TYPES:
    contract_df = df_self_deal[df_self_deal["contract_type"] == contract_type]

    if len(contract_df) > 0:
        k_values = np.arange(6, 11)
        survival_probs = [(contract_df["team0_tricks"] >= k).mean() for k in k_values]

        ax2.step(
            k_values,
            survival_probs,
            where="post",
            marker="o",
            markersize=4,
            label=f"{contract_type.upper()}",
            alpha=0.8,
        )

ax2.set_xlabel("k (Tricks)")
ax2.set_ylabel("P(Tricks >= k)")
ax2.set_title("CCDF: Tail Analysis (k >= 6, log scale)")
ax2.set_xlim(5.5, 10.5)
ax2.set_yscale("log")
ax2.set_ylim(0.001, 1)
ax2.grid(alpha=0.3, which="both")
ax2.legend()

plt.tight_layout()
plt.show()

print("✓ CCDF (discrete survival) plotted")

# %% [markdown]
# ---
#
# ## Section 5: Summary
#
# Final health scorecard for outcome validation.

# %%
# ============================================================================
# Outcome Health Summary
# ============================================================================

print("\n" + "=" * 70)
print("OUTCOME HEALTH SUMMARY")
print("=" * 70)

summary = {"passes": [], "warnings": [], "failures": []}

# Test 1.1: Outcome validity (already passed if we got here)
summary["passes"].append(
    "✅ 1.1 Outcome validity: All tricks_won in [0, 10], valid contract types"
)

# Test 1.2: Deal-level invariant (already passed if we got here)
summary["passes"].append("✅ 1.2 Deal invariant: team0_tricks + team1_tricks == 10")

# Test 1.3: Reproducibility (already passed if we got here)
if True:  # Always generate (reproducibility check needs on-the-fly generation)
    summary["passes"].append(
        "✅ 1.3 Reproducibility: Outcomes deterministic with same seed"
    )
else:
    summary["warnings"].append("⚠️  1.3 Reproducibility: Skipped (generation disabled)")

# Contract-specific mean checks (using deal-level data)
for contract_type in CONTRACT_TYPES:
    contract_df = df_self_deal[df_self_deal["contract_type"] == contract_type]
    if len(contract_df) > 0:
        mean_tricks = contract_df["team0_tricks"].mean()
        if 4.0 <= mean_tricks <= 6.0:
            summary["passes"].append(
                f"  ✅ {contract_type.upper()}: mean={mean_tricks:.3f} in [4.0, 6.0]"
            )
        else:
            summary["warnings"].append(
                f"  ⚠️  {contract_type.upper()}: mean={mean_tricks:.3f} outside [4.0, 6.0]"
            )

# Trump suit balance (suit contracts only)
suit_df = df_self[df_self["contract_type"] == "suit"]
if len(suit_df) > 0:
    for strat in strategies:
        strat_suit_df = suit_df[suit_df["strategy_id"] == strat]
        if len(strat_suit_df) > 0:
            trump_groups = [
                strat_suit_df[strat_suit_df["trump"] == t]["tricks_won"]
                for t in TRUMPS_FOR_SUIT_CONTRACTS
            ]
            trump_groups = [g for g in trump_groups if len(g) > 0]
            if len(trump_groups) >= 2:
                f_stat, p_value = f_oneway(*trump_groups)
                if p_value >= 0.05:
                    summary["passes"].append(
                        f"✅ Trump balance ({strat}): p={p_value:.3f}"
                    )
                else:
                    summary["warnings"].append(
                        f"⚠️  Trump bias ({strat}): p={p_value:.3f}"
                    )

# Heatmap checks (diagonal should show ~0.5 win rate, ~0 delta)
if "win_rate_pivot" in dir() and win_rate_pivot is not None:
    for strat in STRATEGY_NAMES:
        if strat in win_rate_pivot.index and strat in win_rate_pivot.columns:
            diag_win = win_rate_pivot.loc[strat, strat]
            if pd.notna(diag_win):
                if 0.4 <= diag_win <= 0.6:
                    summary["passes"].append(
                        f"✅ Self-play win rate ({strat}): {diag_win:.3f} ~= 0.5"
                    )
                else:
                    summary["warnings"].append(
                        f"⚠️  Self-play win rate ({strat}): {diag_win:.3f} != 0.5"
                    )

if "delta_pivot" in dir() and delta_pivot is not None:
    for strat in STRATEGY_NAMES:
        if strat in delta_pivot.index and strat in delta_pivot.columns:
            diag_delta = delta_pivot.loc[strat, strat]
            if pd.notna(diag_delta):
                if abs(diag_delta) < 0.5:
                    summary["passes"].append(
                        f"✅ Self-play delta ({strat}): {diag_delta:.2f} ~= 0"
                    )
                else:
                    summary["warnings"].append(
                        f"⚠️  Self-play delta ({strat}): {diag_delta:.2f} != 0"
                    )

# Print summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print("\nPASSES:")
for item in summary["passes"]:
    print(f"  {item}")

if summary["warnings"]:
    print("\nWARNINGS:")
    for item in summary["warnings"]:
        print(f"  {item}")

if summary["failures"]:
    print("\nFAILURES:")
    for item in summary["failures"]:
        print(f"  {item}")
    print("\n⚠️  CRITICAL ISSUES DETECTED - Review failures above")
else:
    print("\n✅ ALL CRITICAL TESTS PASSED")

print("=" * 70)

# %% [markdown]
# ---
#
# ## End of Notebook
#
# **Next steps:**
# - If failures detected, investigate simulation logic
# - If warnings present, consider increasing sample size (use MODE="FULL")
# - See `10_feature_health_checks.ipynb` for feature validation
# - See `30_feature_outcome_eval.ipynb` for feature-label relationships
