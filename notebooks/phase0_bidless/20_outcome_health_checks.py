# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags
#     notebook_metadata_filter: jupytext,kernelspec,language_info
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3
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
#     version: 3.11.0
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

MODE = "QUICK"  # "SMOKE" (~30 deals), "QUICK" (~2k deals), or "FULL" (~50k deals)
SEED = 42

# Contract space
CONTRACT_TYPES = ['suit', 'high', 'low']
TRUMPS_FOR_SUIT_CONTRACTS = ['C', 'D', 'H', 'S']
SEATS = [0, 1, 2, 3]

# Strategy configuration
STRATEGIES = [
    {"name": "greedy", "class_name": "GreedyStrategy"},
    {"name": "glutton", "class_name": "GluttonStrategy"},
    {"name": "always_highest", "class_name": "AlwaysHighestLegalStrategy"},
    {"name": "always_lowest", "class_name": "AlwaysLowestLegalStrategy"},
]

# Plot downsampling (for performance; never affects validations)
PLOT_MAX_ROWS = 10_000
PLOT_SAMPLE_SEED = 42
DOWNSAMPLE_PLOTS = True

# Display
import warnings

warnings.filterwarnings('ignore')

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

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import f_oneway

# Add src to path
repo_root = Path.cwd().parent.parent
sys.path.insert(0, str(repo_root / 'src'))

from bid_euchre.diagnostics.notebook_data import load_or_generate_outcomes

print("\n✓ Imports complete")


# %%
# ============================================================================
# Matchup Matrix Builder (N×N)
# ============================================================================

STRATEGY_NAMES = [s["name"] for s in STRATEGIES]

# Build full N×N matchup matrix (16 matchups for 4 strategies)
MATCHUPS_MATRIX = [{"team0": a, "team1": b} for a in STRATEGY_NAMES for b in STRATEGY_NAMES]

print(f"Built {len(MATCHUPS_MATRIX)} matchups (full {len(STRATEGY_NAMES)}×{len(STRATEGY_NAMES)} matrix)")
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
    keys = ['deal_id', 'contract_type', 'trump', 'strategy_id']

    # Team 0: use seat 0 (which already has team0 tricks)
    df_team0 = (
        df[df.seat == 0][keys + ['tricks_won']]
        .rename(columns={'tricks_won': 'team0_tricks'})
    )

    # Team 1: use seat 1 (which already has team1 tricks)
    df_team1 = (
        df[df.seat == 1][keys + ['tricks_won']]
        .rename(columns={'tricks_won': 'team1_tricks'})
    )

    # Merge on stable keys
    df_deal = df_team0.merge(df_team1, on=keys)
    df_deal['delta_tricks'] = df_deal['team0_tricks'] - df_deal['team1_tricks']
    df_deal['team0_win'] = df_deal['team0_tricks'] >= 6

    return df_deal


def downsample_for_plot(df: pd.DataFrame) -> pd.DataFrame:
    """Downsample dataframe for plotting if enabled and needed."""
    if DOWNSAMPLE_PLOTS and len(df) > PLOT_MAX_ROWS:
        return df.sample(PLOT_MAX_ROWS, random_state=PLOT_SAMPLE_SEED)
    return df


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
            'team0_strategy': team0,
            'team1_strategy': team1,
        }
    # Single strategy (self-play)
    return {
        'team0_strategy': strategy_id,
        'team1_strategy': strategy_id,
    }


# Parse matchup metadata for head-to-head data
if 'strategy_id' in df_h2h.columns:
    matchup_meta = df_h2h['strategy_id'].apply(parse_matchup_id).apply(pd.Series)
    df_h2h = pd.concat([df_h2h, matchup_meta], axis=1)
    print("Parsed matchup IDs for head-to-head data")
    print(f"  Unique team0_strategy: {sorted(df_h2h['team0_strategy'].unique())}")
    print(f"  Unique team1_strategy: {sorted(df_h2h['team1_strategy'].unique())}")

# Also parse for self-play data
if 'strategy_id' in df_self.columns:
    matchup_meta_self = df_self['strategy_id'].apply(parse_matchup_id).apply(pd.Series)
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
print(df_self['contract_type'].value_counts().sort_index())
print("\nStrategy distribution:")
print(df_self['strategy_id'].value_counts())

print("\n--- Head-to-head Dataset ---")
print(f"Total observations: {len(df_h2h)}")
print("\nContract type distribution:")
print(df_h2h['contract_type'].value_counts().sort_index())
print("\nMatchup distribution (top 10):")
print(df_h2h['strategy_id'].value_counts().head(10))

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
    required_cols = ['deal_id', 'seat', 'contract_type', 'trump', 'tricks_won', 'strategy_id']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise AssertionError(f"{name}: Missing required columns: {missing_cols}")
    print("  ✓ Required columns present")

    # Check for nulls (trump can be null for high/low)
    non_null_cols = ['deal_id', 'seat', 'contract_type', 'tricks_won', 'strategy_id']
    for col in non_null_cols:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise AssertionError(f"{name}: Column '{col}' has {null_count} null values")
    print("  ✓ No nulls in key columns")

    # Check tricks_won range [0, 10]
    if not df['tricks_won'].between(0, 10).all():
        invalid_count = (~df['tricks_won'].between(0, 10)).sum()
        invalid_vals = df[~df['tricks_won'].between(0, 10)]['tricks_won'].unique()
        raise AssertionError(f"{name}: tricks_won out of range [0,10]: {sorted(invalid_vals)}")
    print("  ✓ All tricks_won in valid range [0, 10]")

    # Check contract_type values
    valid_contracts = {'suit', 'high', 'low'}
    actual_contracts = set(df['contract_type'].unique())
    invalid_contracts = actual_contracts - valid_contracts
    if invalid_contracts:
        raise AssertionError(f"{name}: Invalid contract_type values: {invalid_contracts}")
    print(f"  ✓ Contract types valid: {sorted(actual_contracts)}")

    # Check trump for suit contracts
    suit_df = df[df['contract_type'] == 'suit']
    if len(suit_df) > 0:
        valid_trumps = {'C', 'D', 'H', 'S'}
        actual_trumps = set(suit_df['trump'].dropna().unique())
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
    total_tricks = df_deal['team0_tricks'] + df_deal['team1_tricks']
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
canonical_cols = ['deal_id', 'seat', 'contract_type', 'trump', 'tricks_won', 'strategy_id']

# Sort both by stable keys for comparison
sort_keys = ['deal_id', 'seat', 'contract_type', 'trump', 'strategy_id']
df_self_sorted = df_self[canonical_cols].sort_values(sort_keys).reset_index(drop=True)
df_check_sorted = df_self_check[canonical_cols].sort_values(sort_keys).reset_index(drop=True)

print("\nComparing datasets (canonical columns only)...")
print(f"  Dataset 1 shape: {df_self_sorted.shape}")
print(f"  Dataset 2 shape: {df_check_sorted.shape}")

# Shape check
if df_self_sorted.shape != df_check_sorted.shape:
    raise AssertionError(f"Shape mismatch: {df_self_sorted.shape} vs {df_check_sorted.shape}")

# Value check - use fillna for null-safe comparison
df1_filled = df_self_sorted.fillna('__NULL__')
df2_filled = df_check_sorted.fillna('__NULL__')
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

# %%
# ============================================================================
# 2.1 Outcome Distribution by Contract Type (faceted by strategy)
# ============================================================================

print("\n2.1 Outcome distributions by contract type (faceted by strategy)...")

strategies = sorted(df_self['strategy_id'].unique())
n_strategies = len(strategies)

fig, axes = plt.subplots(n_strategies, 3, figsize=(15, 4 * n_strategies), sharey=True)
if n_strategies == 1:
    axes = axes.reshape(1, -1)

for i, strat in enumerate(strategies):
    strat_df = df_self[df_self['strategy_id'] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    for j, contract_type in enumerate(CONTRACT_TYPES):
        ax = axes[i, j]
        contract_df = strat_df_plot[strat_df_plot['contract_type'] == contract_type]
        contract_df_full = strat_df[strat_df['contract_type'] == contract_type]

        if len(contract_df) > 0:
            sns.violinplot(data=contract_df, y='tricks_won', ax=ax, color='lightblue', inner='quartile')

            mean_val = contract_df_full['tricks_won'].mean()
            ax.axhline(mean_val, color='red', linestyle='--', linewidth=1, alpha=0.7,
                       label=f'Mean={mean_val:.2f}')
            ax.legend(loc='upper right', fontsize=8)

        ax.set_title(f"{strat}\n{contract_type.upper()} (n={len(contract_df_full)})")
        ax.set_ylabel("Tricks Won" if j == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Contract-type distributions plotted (faceted by strategy)")

# %% [markdown]
# ### 2.1.1 By Suit (suit contracts only)
#
# Includes ANOVA test for trump bias.

# %%
# ============================================================================
# 2.1.1 Outcome Distribution by Trump Suit (faceted by strategy)
# ============================================================================

print("\n2.1.1 Outcome distributions by trump suit (faceted by strategy)...")

suit_df_self = df_self[df_self['contract_type'] == 'suit']

if len(suit_df_self) > 0:
    fig, axes = plt.subplots(1, n_strategies, figsize=(5 * n_strategies, 5), sharey=True)
    if n_strategies == 1:
        axes = [axes]

    for i, strat in enumerate(strategies):
        ax = axes[i]
        strat_df = suit_df_self[suit_df_self['strategy_id'] == strat]
        strat_df_plot = downsample_for_plot(strat_df)

        if len(strat_df_plot) > 0:
            sns.violinplot(data=strat_df_plot, x='trump', y='tricks_won', ax=ax,
                           palette='Set1', inner='quartile',
                           order=TRUMPS_FOR_SUIT_CONTRACTS)

            # ANOVA test for trump bias
            trump_groups = [strat_df[strat_df['trump'] == t]['tricks_won']
                            for t in TRUMPS_FOR_SUIT_CONTRACTS]
            trump_groups = [g for g in trump_groups if len(g) > 0]

            if len(trump_groups) >= 2:
                f_stat, p_value = f_oneway(*trump_groups)
                status = "⚠️" if p_value < 0.05 else "✓"
                ax.set_title(f"{strat}\n(n={len(strat_df)}, ANOVA p={p_value:.3f} {status})")
            else:
                ax.set_title(f"{strat}\n(n={len(strat_df)})")

        ax.set_xlabel("Trump Suit")
        ax.set_ylabel("Tricks Won" if i == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.show()

    print("✓ Trump suit distributions plotted with ANOVA tests")
else:
    print("⚠️  No suit contracts found - skipping trump analysis")

# %% [markdown]
# ### 2.1.2 By High/Low

# %%
# ============================================================================
# 2.1.2 Outcome Distribution: High vs Low (faceted by strategy)
# ============================================================================

print("\n2.1.2 Outcome distributions: high vs low contracts (faceted by strategy)...")

highlow_df = df_self[df_self['contract_type'].isin(['high', 'low'])]

if len(highlow_df) > 0:
    fig, axes = plt.subplots(1, n_strategies, figsize=(4 * n_strategies, 5), sharey=True)
    if n_strategies == 1:
        axes = [axes]

    for i, strat in enumerate(strategies):
        ax = axes[i]
        strat_df = highlow_df[highlow_df['strategy_id'] == strat]
        strat_df_plot = downsample_for_plot(strat_df)

        if len(strat_df_plot) > 0:
            sns.violinplot(data=strat_df_plot, x='contract_type', y='tricks_won', ax=ax,
                           palette='Set2', inner='quartile', order=['high', 'low'])

        ax.set_title(f"{strat}\n(n={len(strat_df)})")
        ax.set_xlabel("Contract Type")
        ax.set_ylabel("Tricks Won" if i == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.show()

    print("✓ High vs Low distributions plotted")
else:
    print("⚠️  No high/low contracts found")

# %% [markdown]
# ### 2.2 By Team
#
# Using deal-level frame to compare team0_tricks vs team1_tricks distributions.
# Self-play should be symmetric (both distributions should be similar).

# %%
# ============================================================================
# 2.2 Outcome Distribution by Team (faceted by strategy)
# ============================================================================

print("\n2.2 Outcome distributions by team (faceted by strategy)...")

df_self_deal = make_deal_frame(df_self)

fig, axes = plt.subplots(1, n_strategies, figsize=(5 * n_strategies, 5), sharey=True)
if n_strategies == 1:
    axes = [axes]

for i, strat in enumerate(strategies):
    ax = axes[i]
    strat_df = df_self_deal[df_self_deal['strategy_id'] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    # Melt to long format for violin plot
    team_data = pd.melt(
        strat_df_plot,
        value_vars=['team0_tricks', 'team1_tricks'],
        var_name='team',
        value_name='tricks'
    )
    team_data['team'] = team_data['team'].map({
        'team0_tricks': 'Team 0',
        'team1_tricks': 'Team 1'
    })

    if len(team_data) > 0:
        sns.violinplot(data=team_data, x='team', y='tricks', ax=ax,
                       palette='Pastel1', inner='quartile')

        # Show means
        mean0 = strat_df['team0_tricks'].mean()
        mean1 = strat_df['team1_tricks'].mean()
        ax.set_title(f"{strat}\n(μ₀={mean0:.2f}, μ₁={mean1:.2f})")

    ax.set_xlabel("Team")
    ax.set_ylabel("Tricks Won" if i == 0 else "")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Team distributions plotted (self-play should be symmetric)")

# %% [markdown]
# ### 2.3 By Seat
#
# **Important:** Due to the logging schema, seats within the same team have
# identical `tricks_won` values:
# - Seats 0 & 2 (Team 0) show team0_tricks
# - Seats 1 & 3 (Team 1) show team1_tricks

# %%
# ============================================================================
# 2.3 Outcome Distribution by Seat (faceted by strategy)
# ============================================================================

print("\n2.3 Outcome distributions by seat (faceted by strategy)...")
print("Note: Seats 0&2 (Team 0) and seats 1&3 (Team 1) show identical values due to team-level logging.")

fig, axes = plt.subplots(n_strategies, 3, figsize=(15, 4 * n_strategies), sharey=True)
if n_strategies == 1:
    axes = axes.reshape(1, -1)

for i, strat in enumerate(strategies):
    strat_df = df_self[df_self['strategy_id'] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    for j, contract_type in enumerate(CONTRACT_TYPES):
        ax = axes[i, j]
        contract_df = strat_df_plot[strat_df_plot['contract_type'] == contract_type]

        if len(contract_df) > 0:
            sns.violinplot(data=contract_df, x='seat', y='tricks_won', ax=ax,
                           palette='Set2', inner='quartile')

        ax.set_title(f"{strat} - {contract_type.upper()}")
        ax.set_xlabel("Seat")
        ax.set_ylabel("Tricks Won" if j == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Seat-level distributions plotted")

# %% [markdown]
# ### 2.4 By Contract_Type and Team

# %%
# ============================================================================
# 2.4 Outcome Distribution by Contract Type and Team
# ============================================================================

print("\n2.4 Outcome distributions by contract type and team...")

fig, axes = plt.subplots(n_strategies, len(CONTRACT_TYPES), figsize=(15, 4 * n_strategies), sharey=True)
if n_strategies == 1:
    axes = axes.reshape(1, -1)

for i, strat in enumerate(strategies):
    strat_df = df_self_deal[df_self_deal['strategy_id'] == strat]
    strat_df_plot = downsample_for_plot(strat_df)

    for j, contract_type in enumerate(CONTRACT_TYPES):
        ax = axes[i, j]
        contract_df = strat_df_plot[strat_df_plot['contract_type'] == contract_type]
        contract_df_full = strat_df[strat_df['contract_type'] == contract_type]

        if len(contract_df) > 0:
            # Melt for team comparison
            team_data = pd.melt(
                contract_df,
                value_vars=['team0_tricks', 'team1_tricks'],
                var_name='team',
                value_name='tricks'
            )
            team_data['team'] = team_data['team'].map({
                'team0_tricks': 'T0',
                'team1_tricks': 'T1'
            })

            sns.violinplot(data=team_data, x='team', y='tricks', ax=ax,
                           palette='Pastel1', inner='quartile')

            mean0 = contract_df_full['team0_tricks'].mean()
            mean1 = contract_df_full['team1_tricks'].mean()
            ax.set_title(f"{strat} / {contract_type.upper()}\n(μ₀={mean0:.2f}, μ₁={mean1:.2f})")

        ax.set_xlabel("Team")
        ax.set_ylabel("Tricks Won" if j == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Contract×Team distributions plotted")

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
    df_h2h[['deal_id', 'contract_type', 'trump', 'strategy_id', 'team0_strategy', 'team1_strategy']].drop_duplicates(),
    on=['deal_id', 'contract_type', 'trump', 'strategy_id'],
    how='left'
)

print(f"Deal-level H2H frame: {len(df_h2h_deal)} rows")
print(f"Unique matchups: {df_h2h_deal.groupby(['team0_strategy', 'team1_strategy']).ngroups}")

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
win_rate_pivot = df_h2h_deal.groupby(['team0_strategy', 'team1_strategy'])['team0_win'].mean().unstack()

# Ensure consistent ordering
win_rate_pivot = win_rate_pivot.reindex(index=STRATEGY_NAMES, columns=STRATEGY_NAMES)

plt.figure(figsize=(10, 8))
sns.heatmap(win_rate_pivot, annot=True, fmt='.3f', cmap='RdYlGn',
            vmin=0, vmax=1, center=0.5,
            xticklabels=STRATEGY_NAMES, yticklabels=STRATEGY_NAMES)
plt.title("Win Rate Heatmap: P(Team 0 Wins)\nRows = Team 0 strategy, Cols = Team 1 strategy")
plt.xlabel("Team 1 Strategy")
plt.ylabel("Team 0 Strategy")
plt.tight_layout()
plt.show()

print("✓ Win rate heatmap plotted")
print("\nExpected: Diagonal (self-play) should be ~0.5")
diag_values = [win_rate_pivot.loc[s, s] for s in STRATEGY_NAMES if pd.notna(win_rate_pivot.loc[s, s])]
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
delta_pivot = df_h2h_deal.groupby(['team0_strategy', 'team1_strategy'])['delta_tricks'].mean().unstack()

# Ensure consistent ordering
delta_pivot = delta_pivot.reindex(index=STRATEGY_NAMES, columns=STRATEGY_NAMES)

plt.figure(figsize=(10, 8))
sns.heatmap(delta_pivot, annot=True, fmt='.2f', cmap='RdBu_r',
            vmin=-5, vmax=5, center=0,
            xticklabels=STRATEGY_NAMES, yticklabels=STRATEGY_NAMES)
plt.title("Mean Delta Heatmap: E[Team 0 Tricks - Team 1 Tricks]\nRows = Team 0 strategy, Cols = Team 1 strategy")
plt.xlabel("Team 1 Strategy")
plt.ylabel("Team 0 Strategy")
plt.tight_layout()
plt.show()

print("✓ Mean delta heatmap plotted")
print("\nExpected: Diagonal (self-play) should be ~0")
diag_deltas = [delta_pivot.loc[s, s] for s in STRATEGY_NAMES if pd.notna(delta_pivot.loc[s, s])]
if diag_deltas:
    print(f"Diagonal deltas: {[f'{v:.2f}' for v in diag_deltas]}")

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
            (df_h2h_deal['team0_strategy'] == s0) &
            (df_h2h_deal['team1_strategy'] == s1)
        ]

        if len(matchup_df) > 0:
            matchup_plot = downsample_for_plot(matchup_df)
            # Violin only (no box overlay as per plan)
            ax.violinplot(matchup_plot['team0_tricks'].dropna(), positions=[0], showmedians=True)
            mean_val = matchup_df['team0_tricks'].mean()
            ax.axhline(mean_val, color='red', linestyle='--', linewidth=0.5, alpha=0.7)
            ax.text(0.95, 0.95, f'μ={mean_val:.1f}', transform=ax.transAxes,
                    fontsize=7, va='top', ha='right')

        ax.set_ylim(-0.5, 10.5)
        ax.set_xticks([])
        ax.grid(axis='y', alpha=0.3)

        # Labels
        if i == 0:
            ax.set_title(s1[:8], fontsize=9)
        if j == 0:
            ax.set_ylabel(s0[:8], fontsize=9)

fig.suptitle("Team 0 Tricks by Matchup\n(rows = team0, cols = team1)", y=1.02, fontsize=12)
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
            (df_h2h_deal['team0_strategy'] == s0) &
            (df_h2h_deal['team1_strategy'] == s1)
        ]

        if len(matchup_df) > 0:
            matchup_plot = downsample_for_plot(matchup_df)
            ax.violinplot(matchup_plot['delta_tricks'].dropna(), positions=[0], showmedians=True)
            mean_val = matchup_df['delta_tricks'].mean()
            ax.axhline(mean_val, color='red', linestyle='--', linewidth=0.5, alpha=0.7)
            ax.axhline(0, color='gray', linestyle='-', linewidth=0.5, alpha=0.5)
            ax.text(0.95, 0.95, f'μ={mean_val:+.1f}', transform=ax.transAxes,
                    fontsize=7, va='top', ha='right')

        ax.set_ylim(-10.5, 10.5)
        ax.set_xticks([])
        ax.grid(axis='y', alpha=0.3)

        # Labels
        if i == 0:
            ax.set_title(s1[:8], fontsize=9)
        if j == 0:
            ax.set_ylabel(s0[:8], fontsize=9)

fig.suptitle("Delta Tricks by Matchup (Team 0 - Team 1)\n(rows = team0, cols = team1)", y=1.02, fontsize=12)
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

matchup_summary = df_h2h_deal.groupby(['team0_strategy', 'team1_strategy']).agg(
    n=('deal_id', 'count'),
    mean_team0=('team0_tricks', 'mean'),
    mean_delta=('delta_tricks', 'mean'),
    win_rate=('team0_win', 'mean'),
).round(3).reset_index()

matchup_summary = matchup_summary.rename(columns={
    'team0_strategy': 'team0',
    'team1_strategy': 'team1',
})

print("\nMatchup Summary Table:")
print(matchup_summary.to_string(index=False))

# %% [markdown]
# ---
#
# ## Section 4: Distribution Analysis (CDF/CCDF)
#
# Cumulative distribution functions to examine tail behavior.

# %%
# ============================================================================
# CDF: Cumulative Distribution Function (by contract type)
# ============================================================================

print("\n4.1 CDF of tricks_won by contract type...")

fig, ax = plt.subplots(figsize=(10, 6))

# Use self-play data for clean CDF
for contract_type in CONTRACT_TYPES:
    contract_df = df_self[df_self['contract_type'] == contract_type]

    # Compute CDF
    sorted_tricks = np.sort(contract_df['tricks_won'])
    cdf = np.arange(1, len(sorted_tricks) + 1) / len(sorted_tricks)

    ax.plot(sorted_tricks, cdf, marker='o', markersize=3, linestyle='-',
            label=f"{contract_type.upper()} (n={len(contract_df)})", alpha=0.7)

ax.set_xlabel("Tricks Won")
ax.set_ylabel("Cumulative Probability")
ax.set_title("CDF of Tricks Won by Contract Type (Self-play)")
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(0, 1)
ax.grid(alpha=0.3)
ax.legend()
plt.tight_layout()
plt.show()

print("✓ CDF plotted")


# %%
# ============================================================================
# CCDF: Discrete Survival Function P(X >= k)
# ============================================================================

print("\n4.2 CCDF (discrete survival) of tricks_won by contract type...")

fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Full range plot
ax1 = axes[0]
for contract_type in CONTRACT_TYPES:
    contract_df = df_self[df_self['contract_type'] == contract_type]

    # Compute discrete survival P(X >= k) for k = 0..10
    k_values = np.arange(11)
    survival_probs = [(contract_df['tricks_won'] >= k).mean() for k in k_values]

    ax1.step(k_values, survival_probs, where='post', marker='o', markersize=4,
             label=f"{contract_type.upper()} (n={len(contract_df)})", alpha=0.8)

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
    contract_df = df_self[df_self['contract_type'] == contract_type]

    k_values = np.arange(6, 11)
    survival_probs = [(contract_df['tricks_won'] >= k).mean() for k in k_values]

    ax2.step(k_values, survival_probs, where='post', marker='o', markersize=4,
             label=f"{contract_type.upper()}", alpha=0.8)

ax2.set_xlabel("k (Tricks)")
ax2.set_ylabel("P(Tricks >= k)")
ax2.set_title("CCDF: Tail Analysis (k >= 6, log scale)")
ax2.set_xlim(5.5, 10.5)
ax2.set_yscale('log')
ax2.set_ylim(0.001, 1)
ax2.grid(alpha=0.3, which='both')
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

summary = {
    'passes': [],
    'warnings': [],
    'failures': []
}

# Test 1.1: Outcome validity (already passed if we got here)
summary['passes'].append("✅ 1.1 Outcome validity: All tricks_won in [0, 10], valid contract types")

# Test 1.2: Deal-level invariant (already passed if we got here)
summary['passes'].append("✅ 1.2 Deal invariant: team0_tricks + team1_tricks == 10")

# Test 1.3: Reproducibility (already passed if we got here)
summary['passes'].append("✅ 1.3 Reproducibility: Outcomes deterministic with same seed")

# Contract-specific mean checks
for contract_type in CONTRACT_TYPES:
    contract_df = df_self[df_self['contract_type'] == contract_type]
    mean_tricks = contract_df['tricks_won'].mean()
    if 4.0 <= mean_tricks <= 6.0:
        summary['passes'].append(f"  ✅ {contract_type.upper()}: mean={mean_tricks:.3f} in [4.0, 6.0]")
    else:
        summary['warnings'].append(f"  ⚠️  {contract_type.upper()}: mean={mean_tricks:.3f} outside [4.0, 6.0]")

# Trump suit balance (suit contracts only)
suit_df = df_self[df_self['contract_type'] == 'suit']
if len(suit_df) > 0:
    for strat in strategies:
        strat_suit_df = suit_df[suit_df['strategy_id'] == strat]
        if len(strat_suit_df) > 0:
            trump_groups = [strat_suit_df[strat_suit_df['trump'] == t]['tricks_won']
                            for t in TRUMPS_FOR_SUIT_CONTRACTS]
            trump_groups = [g for g in trump_groups if len(g) > 0]
            if len(trump_groups) >= 2:
                f_stat, p_value = f_oneway(*trump_groups)
                if p_value >= 0.05:
                    summary['passes'].append(f"✅ Trump balance ({strat}): p={p_value:.3f}")
                else:
                    summary['warnings'].append(f"⚠️  Trump bias ({strat}): p={p_value:.3f}")

# Heatmap checks (diagonal should show ~0.5 win rate, ~0 delta)
if 'win_rate_pivot' in dir() and win_rate_pivot is not None:
    for strat in STRATEGY_NAMES:
        if strat in win_rate_pivot.index and strat in win_rate_pivot.columns:
            diag_win = win_rate_pivot.loc[strat, strat]
            if pd.notna(diag_win):
                if 0.4 <= diag_win <= 0.6:
                    summary['passes'].append(f"✅ Self-play win rate ({strat}): {diag_win:.3f} ~= 0.5")
                else:
                    summary['warnings'].append(f"⚠️  Self-play win rate ({strat}): {diag_win:.3f} != 0.5")

if 'delta_pivot' in dir() and delta_pivot is not None:
    for strat in STRATEGY_NAMES:
        if strat in delta_pivot.index and strat in delta_pivot.columns:
            diag_delta = delta_pivot.loc[strat, strat]
            if pd.notna(diag_delta):
                if abs(diag_delta) < 0.5:
                    summary['passes'].append(f"✅ Self-play delta ({strat}): {diag_delta:.2f} ~= 0")
                else:
                    summary['warnings'].append(f"⚠️  Self-play delta ({strat}): {diag_delta:.2f} != 0")

# Print summary
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print("\nPASSES:")
for item in summary['passes']:
    print(f"  {item}")

if summary['warnings']:
    print("\nWARNINGS:")
    for item in summary['warnings']:
        print(f"  {item}")

if summary['failures']:
    print("\nFAILURES:")
    for item in summary['failures']:
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
