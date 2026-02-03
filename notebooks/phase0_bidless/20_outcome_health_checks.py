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
# **Scope:**
# - Outcome validity (range, contract-type breakdown)
# - Reproducibility checks
# - Outcome distributions by contract type, seat, trump
# - Strategy matchup analysis
# - CDF/CCDF tail analysis
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
# ## Section 0: Configuration & Setup
#
# Set experiment parameters and import utilities.

# %%
# ============================================================================
# Configuration
# ============================================================================

MODE = "QUICK"  # "QUICK" (~2k deals) or "FULL" (~50k deals)
SEED = 42

# Contract space
CONTRACT_TYPES = ['suit', 'high', 'low']
TRUMPS_FOR_SUIT_CONTRACTS = ['C', 'D', 'H', 'S']
SEATS = [0, 1, 2, 3]

# Strategy configuration (head-to-head matchups)
STRATEGIES = [
    {"name": "greedy", "class_name": "GreedyStrategy"},
    {"name": "glutton", "class_name": "GluttonStrategy"},
    {"name": "always_highest", "class_name": "AlwaysHighestLegalStrategy"},
    {"name": "always_lowest", "class_name": "AlwaysLowestLegalStrategy"},
]

MATCHUP_MODE = "reverse_matchups"  # "reverse_matchups" or "per_seat_rotations"
INCLUDE_REVERSE_MATCHUPS = True

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
print(f"  Matchup mode: {MATCHUP_MODE}")

# %%
# ============================================================================
# Imports
# ============================================================================

import itertools
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
# Matchup Builders
# ============================================================================

def build_round_robin_matchups(strategy_names, include_reverse=True):
    """Build team0 vs team1 matchups with optional reversals."""
    pairs = list(itertools.combinations(strategy_names, 2))
    matchups = [{"team0": a, "team1": b} for a, b in pairs]
    if include_reverse:
        matchups += [{"team0": b, "team1": a} for a, b in pairs]
    return matchups


STRATEGY_NAMES = [s["name"] for s in STRATEGIES]
MATCHUPS = build_round_robin_matchups(STRATEGY_NAMES, include_reverse=INCLUDE_REVERSE_MATCHUPS)

print(f"Built {len(MATCHUPS)} matchups")
print(f"Matchup examples: {MATCHUPS[:3]}")

# %%
# ============================================================================
# Load/Generate Outcome Data
# ============================================================================

outcome_df = load_or_generate_outcomes(
    mode=MODE,
    seed=SEED,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    seats=SEATS,
    strategies=STRATEGIES,
    matchups=MATCHUPS,
)

print(f"\nOutcome dataset shape: {outcome_df.shape}")
print(f"Columns: {list(outcome_df.columns)}")
print("\nFirst few rows:")
print(outcome_df.head())

# %%
# ============================================================================
# Data Overview
# ============================================================================

print("\nData Overview:")
print("=" * 70)
print(f"Total observations: {len(outcome_df)}")
print("\nContract type distribution:")
print(outcome_df['contract_type'].value_counts().sort_index())

if 'trump' in outcome_df.columns:
    print("\nTrump distribution:")
    print(outcome_df['trump'].value_counts().sort_index())

print("\nSeat distribution:")
print(outcome_df['seat'].value_counts().sort_index())

if 'strategy_id' in outcome_df.columns:
    print("\nStrategy distribution:")
    print(outcome_df['strategy_id'].value_counts())

print("=" * 70)


# %%
# ============================================================================
# Parse Matchup IDs and Derive seat_strategy
# ============================================================================

def parse_matchup_id(strategy_id: str) -> dict:
    """Parse strategy_id to extract per-seat strategy mapping."""
    if "_vs_" in strategy_id:
        team0, team1 = strategy_id.split("_vs_", maxsplit=1)
        return {
            'team0_strategy': team0,
            'team1_strategy': team1,
            'seat0_strategy': team0,
            'seat1_strategy': team1,
            'seat2_strategy': team0,
            'seat3_strategy': team1,
        }
    if strategy_id.startswith("seatmap__"):
        parts = strategy_id.split("__")[1:]
        if len(parts) == 4:
            return {
                'team0_strategy': parts[0],
                'team1_strategy': parts[1],
                'seat0_strategy': parts[0],
                'seat1_strategy': parts[1],
                'seat2_strategy': parts[2],
                'seat3_strategy': parts[3],
            }
    return {}


def get_seat_strategy(row):
    """Map a row's seat to its strategy from the parsed matchup metadata."""
    seat = row['seat']
    col_name = f'seat{seat}_strategy'
    return row.get(col_name, None)


# Parse matchup metadata
if 'strategy_id' in outcome_df.columns:
    matchup_meta = outcome_df['strategy_id'].apply(parse_matchup_id).apply(pd.Series)
    outcome_df = pd.concat([outcome_df, matchup_meta], axis=1)

    # Derive seat_strategy
    if 'seat0_strategy' in outcome_df.columns:
        outcome_df['seat_strategy'] = outcome_df.apply(get_seat_strategy, axis=1)
        print("Derived seat_strategy column")
        print(f"Unique seat strategies: {sorted(outcome_df['seat_strategy'].dropna().unique())}")
    else:
        print("⚠️  Could not derive seat_strategy - matchup parsing failed")
else:
    print("⚠️  No strategy_id column - skipping matchup parsing")

# %% [markdown]
# ---
#
# ## Section 2: Fail-Fast Validation Tests
#
# Critical assertions that must pass before proceeding with analysis.

# %% [markdown]
# ### Test 3: Outcome Validity (with Contract-Type Breakdown)
#
# **Enhancement:** This test now breaks down outcome statistics by contract type to detect contract-specific simulation bugs.

# %%
# ============================================================================
# Test 3: Outcome Validity - tricks_won in Valid Range
# ============================================================================

print("\n" + "=" * 70)
print("TEST 3: Outcome Validity")
print("=" * 70)

if 'tricks_won' in outcome_df.columns:
    print("\nChecking tricks_won values...")

    # GLOBAL VALIDATION (fail-fast)
    min_tricks = outcome_df['tricks_won'].min()
    max_tricks = outcome_df['tricks_won'].max()
    mean_tricks = outcome_df['tricks_won'].mean()

    print(f"  Overall Range: [{min_tricks}, {max_tricks}]")
    print(f"  Overall Mean: {mean_tricks:.3f}")

    # Assert valid range [0, 10] - FAIL FAST
    if not outcome_df['tricks_won'].between(0, 10).all():
        invalid_count = (~outcome_df['tricks_won'].between(0, 10)).sum()
        invalid_values = outcome_df[~outcome_df['tricks_won'].between(0, 10)]['tricks_won'].unique()
        print("\n❌ FAIL-FAST ABORT: tricks_won out of valid range")
        print("=" * 70)
        print(f"Found {invalid_count} invalid values: {sorted(invalid_values)}")
        raise AssertionError("tricks_won contains values outside [0, 10] - simulation bug")

    print("  ✓ All tricks_won values in valid range [0, 10]")

    # CONTRACT-TYPE BREAKDOWN
    print("\n  Breakdown by contract type:")
    print("  " + "-" * 60)

    for contract_type in CONTRACT_TYPES:  # ['suit', 'high', 'low']
        contract_df = outcome_df[outcome_df['contract_type'] == contract_type]

        min_tricks_c = contract_df['tricks_won'].min()
        max_tricks_c = contract_df['tricks_won'].max()
        mean_tricks_c = contract_df['tricks_won'].mean()
        n_samples = len(contract_df)

        assert n_samples > 0, f"Empty contract group: {contract_type}"

        print(f"\n  Contract: {contract_type.upper()}")
        print(f"    Samples: {n_samples}")
        print(f"    Range: [{min_tricks_c}, {max_tricks_c}]")
        print(f"    Mean: {mean_tricks_c:.3f}")

        # Sanity check: mean should be close to 5.0 for fair self-play
        if not (4.0 <= mean_tricks_c <= 6.0):
            print(f"    ⚠️  WARNING: Mean = {mean_tricks_c:.3f}, expected ~5.0")
            print("        Review contract-specific logic if this persists")
        else:
            print("    ✓ Mean in expected range [4.0, 6.0]")

        # Tricks distribution for this contract type
        value_counts = contract_df['tricks_won'].value_counts().sort_index()
        print("    Distribution:")
        for tricks, count in value_counts.items():
            pct = 100 * count / len(contract_df)
            print(f"      {tricks} tricks: {count:5d} ({pct:5.1f}%)")

    print("\n" + "=" * 70)
    print("✅ Outcome validity check PASSED (all contract types)")
    print("=" * 70)

else:
    print("\n⚠️  SKIPPED: outcome_df does not have tricks_won column")

# %% [markdown]
# ### Test 4: Reproducibility Check (Outcome Portion)
#
# Verify that running with the same seed produces identical outcomes.

# %%
# ============================================================================
# Test 4: Reproducibility - Verify Deterministic Outcomes
# ============================================================================

print("\n" + "=" * 70)
print("TEST 4: Reproducibility Check (Outcomes)")
print("=" * 70)

# Generate second dataset with same seed
print(f"\nGenerating second outcome dataset with seed={SEED}...")
outcome_df2 = load_or_generate_outcomes(
    mode=MODE,
    seed=SEED,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    seats=SEATS,
)

# Compare
print("\nComparing datasets...")
print(f"  Dataset 1 shape: {outcome_df.shape}")
print(f"  Dataset 2 shape: {outcome_df2.shape}")

assert outcome_df.shape == outcome_df2.shape, "Shape mismatch"

# Compare tricks_won column
if 'tricks_won' in outcome_df.columns:
    tricks_match = (outcome_df['tricks_won'] == outcome_df2['tricks_won']).all()
    print(f"  tricks_won match: {tricks_match}")

    if not tricks_match:
        diff_count = (outcome_df['tricks_won'] != outcome_df2['tricks_won']).sum()
        print(f"\n❌ FAIL: {diff_count} mismatches in tricks_won")
        print("\nFirst 10 mismatches:")
        mismatches = outcome_df[outcome_df['tricks_won'] != outcome_df2['tricks_won']].head(10)
        print(mismatches[['deal_id', 'seat', 'contract_type', 'tricks_won']])
        print("\nvs Dataset 2:")
        print(outcome_df2.loc[mismatches.index, ['deal_id', 'seat', 'contract_type', 'tricks_won']])
        raise AssertionError("Non-deterministic outcomes detected")

    print("  ✓ All tricks_won values match")

# Compare deal_id alignment
if 'deal_id' in outcome_df.columns:
    deal_match = (outcome_df['deal_id'] == outcome_df2['deal_id']).all()
    print(f"  deal_id match: {deal_match}")
    assert deal_match, "deal_id mismatch - deal order changed"

print("\n" + "=" * 70)
print("✅ Reproducibility check PASSED")
print("=" * 70)

# %% [markdown]
# ---
#
# ## Section 3: Outcome Distributions by Contract Type
#
# Visualize outcome distributions segregated by contract type using violin plots.

# %%
# ============================================================================
# Outcome Distribution by Contract Type
# ============================================================================

print("\nPlotting outcome distributions by contract type...")

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

for i, contract_type in enumerate(CONTRACT_TYPES):
    ax = axes[i]
    contract_df = outcome_df[outcome_df['contract_type'] == contract_type]

    # Violin plot with box overlay
    sns.violinplot(data=contract_df, y='tricks_won', ax=ax, color='lightblue')
    sns.boxplot(data=contract_df, y='tricks_won', ax=ax,
                width=0.3, boxprops={'zorder': 2}, color='white')

    ax.set_title(f"{contract_type.upper()} Contracts (n={len(contract_df)})")
    ax.set_ylabel("Tricks Won" if i == 0 else "")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

    # Add mean line
    mean_val = contract_df['tricks_won'].mean()
    ax.axhline(mean_val, color='red', linestyle='--', linewidth=1, alpha=0.7,
               label=f'Mean={mean_val:.2f}')
    ax.legend(loc='upper right', fontsize=8)

plt.tight_layout()
plt.show()

print("✓ Contract-type distributions plotted")

# %%
# ============================================================================
# Outcome Distribution by Seat (within each contract type)
# ============================================================================

print("\nPlotting outcome distributions by seat (per contract type)...")

fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)

for i, contract_type in enumerate(CONTRACT_TYPES):
    ax = axes[i]
    contract_df = outcome_df[outcome_df['contract_type'] == contract_type]

    # Violin plot by seat
    sns.violinplot(data=contract_df, x='seat', y='tricks_won', ax=ax,
                   palette='Set2', inner='quartile')

    ax.set_title(f"{contract_type.upper()} Contracts - By Seat")
    ax.set_xlabel("Seat")
    ax.set_ylabel("Tricks Won" if i == 0 else "")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

    # Add overall mean line
    mean_val = contract_df['tricks_won'].mean()
    ax.axhline(mean_val, color='red', linestyle='--', linewidth=1, alpha=0.5,
               label=f'Overall={mean_val:.2f}')
    ax.legend(loc='upper right', fontsize=8)

plt.tight_layout()
plt.show()

print("✓ Seat-level outcome distributions plotted")

# %% [markdown]
# ---
#
# ## Section 4: Strategy Matchup Analysis
#
# Compare outcomes across different strategy pairings (if applicable).

# %%
# ============================================================================
# Check for Strategy Data
# ============================================================================

if 'strategy_id' in outcome_df.columns and outcome_df['strategy_id'].nunique() > 1:
    print("\nStrategy data available - generating matchup analysis...")
    has_strategies = True
else:
    print("\n⚠️  No strategy variation detected - skipping matchup analysis")
    print("    (This is expected for self-play datasets)")
    has_strategies = False

# %%
# ============================================================================
# Strategy Win Rate Heatmap
# ============================================================================

if has_strategies:
    print("\nComputing strategy win rates...")

    # Define "win" threshold (>= 6 tricks)
    outcome_df['won'] = outcome_df['tricks_won'] >= 6

    # Aggregate by strategy
    strategy_stats = outcome_df.groupby('strategy_id').agg({
        'won': 'mean',
        'tricks_won': ['mean', 'std', 'count']
    }).round(3)

    strategy_stats.columns = ['win_rate', 'mean_tricks', 'std_tricks', 'n_samples']
    print("\nStrategy Statistics:")
    print(strategy_stats)

    # Heatmap if multiple strategies
    strategies = sorted(outcome_df['strategy_id'].unique())
    if len(strategies) > 1:
        win_matrix = np.zeros((len(strategies), len(strategies)))

        for i, strat in enumerate(strategies):
            strat_df = outcome_df[outcome_df['strategy_id'] == strat]
            win_matrix[i, :] = strat_df.groupby('strategy_id')['won'].mean().reindex(strategies, fill_value=0)

        plt.figure(figsize=(8, 6))
        sns.heatmap(win_matrix, annot=True, fmt='.3f', cmap='RdYlGn',
                    xticklabels=strategies, yticklabels=strategies,
                    vmin=0, vmax=1, center=0.5)
        plt.title("Strategy Win Rate Matrix (rows vs columns)")
        plt.xlabel("Opponent Strategy")
        plt.ylabel("Player Strategy")
        plt.tight_layout()
        plt.show()

        print("✓ Strategy matchup heatmap plotted")
else:
    print("  (Skipped - no strategy variation)")

# %%
# ============================================================================
# Tricks Distribution Comparison (by strategy)
# ============================================================================

if has_strategies:
    strategies = sorted(outcome_df['strategy_id'].unique())

    fig, axes = plt.subplots(1, len(strategies), figsize=(5*len(strategies), 5), sharey=True)
    if len(strategies) == 1:
        axes = [axes]

    for i, strat in enumerate(strategies):
        ax = axes[i]
        strat_df = outcome_df[outcome_df['strategy_id'] == strat]

        sns.violinplot(data=strat_df, y='tricks_won', ax=ax, color='skyblue')
        sns.boxplot(data=strat_df, y='tricks_won', ax=ax, width=0.3,
                    boxprops={'zorder': 2}, color='white')

        ax.set_title(f"Strategy: {strat}\n(n={len(strat_df)})")
        ax.set_ylabel("Tricks Won" if i == 0 else "")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

        mean_val = strat_df['tricks_won'].mean()
        ax.axhline(mean_val, color='red', linestyle='--', linewidth=1, alpha=0.7,
                   label=f'Mean={mean_val:.2f}')
        ax.legend(loc='upper right', fontsize=8)

    plt.tight_layout()
    plt.show()

    print("✓ Strategy outcome distributions plotted")
else:
    print("  (Skipped - no strategy variation)")

# %% [markdown]
# ---
#
# ## Section 5: Trump Suit Analysis (Suit Contracts Only)
#
# Examine outcome variation by trump suit for suit contracts.

# %%
# ============================================================================
# Outcome by Trump Suit (Suit Contracts)
# ============================================================================

if 'trump' in outcome_df.columns:
    suit_df = outcome_df[outcome_df['contract_type'] == 'suit']

    if len(suit_df) > 0:
        print(f"\nAnalyzing trump suit outcomes (n={len(suit_df)} suit contracts)...")

        # Summary statistics
        trump_stats = suit_df.groupby('trump')['tricks_won'].agg(['mean', 'std', 'count'])
        print("\nTrump Suit Statistics:")
        print(trump_stats)

        # Violin plot by trump
        plt.figure(figsize=(10, 6))
        sns.violinplot(data=suit_df, x='trump', y='tricks_won', palette='Set1', inner='quartile')
        plt.title(f"Outcome by Trump Suit (Suit Contracts Only, n={len(suit_df)})")
        plt.xlabel("Trump Suit")
        plt.ylabel("Tricks Won")
        plt.ylim(-0.5, 10.5)
        plt.grid(axis='y', alpha=0.3)

        # Add overall mean line
        overall_mean = suit_df['tricks_won'].mean()
        plt.axhline(overall_mean, color='red', linestyle='--', linewidth=1, alpha=0.5,
                    label=f'Overall={overall_mean:.2f}')
        plt.legend()
        plt.tight_layout()
        plt.show()

        # Statistical test for trump bias
        from scipy.stats import f_oneway
        trump_groups = [suit_df[suit_df['trump'] == t]['tricks_won'] for t in TRUMPS_FOR_SUIT_CONTRACTS]
        f_stat, p_value = f_oneway(*trump_groups)

        print("\nANOVA Test for Trump Suit Bias:")
        print(f"  F-statistic: {f_stat:.4f}")
        print(f"  p-value: {p_value:.4f}")

        if p_value < 0.05:
            print("  ⚠️  WARNING: Significant trump bias detected (p < 0.05)")
        else:
            print("  ✓ No significant trump bias (p >= 0.05)")

        print("\n✓ Trump suit analysis complete")
    else:
        print("\n⚠️  No suit contracts found - skipping trump analysis")
else:
    print("\n⚠️  No trump column - skipping trump analysis")

# %% [markdown]
# ---
#
# ## Section 6: Distribution Analysis (CDF/CCDF)
#
# Cumulative distribution functions to examine tail behavior.

# %%
# ============================================================================
# CDF: Cumulative Distribution Function
# ============================================================================

print("\nPlotting CDF of tricks_won by contract type...")

fig, ax = plt.subplots(figsize=(10, 6))

for contract_type in CONTRACT_TYPES:
    contract_df = outcome_df[outcome_df['contract_type'] == contract_type]

    # Compute CDF
    sorted_tricks = np.sort(contract_df['tricks_won'])
    cdf = np.arange(1, len(sorted_tricks) + 1) / len(sorted_tricks)

    ax.plot(sorted_tricks, cdf, marker='o', markersize=3, linestyle='-',
            label=f"{contract_type.upper()} (n={len(contract_df)})", alpha=0.7)

ax.set_xlabel("Tricks Won")
ax.set_ylabel("Cumulative Probability")
ax.set_title("CDF of Tricks Won by Contract Type")
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(0, 1)
ax.grid(alpha=0.3)
ax.legend()
plt.tight_layout()
plt.show()

print("✓ CDF plotted")

# %%
# ============================================================================
# CCDF: Complementary Cumulative Distribution Function (1 - CDF)
# ============================================================================

print("\nPlotting CCDF of tricks_won by contract type...")

fig, ax = plt.subplots(figsize=(10, 6))

for contract_type in CONTRACT_TYPES:
    contract_df = outcome_df[outcome_df['contract_type'] == contract_type]

    # Compute CCDF (1 - CDF)
    sorted_tricks = np.sort(contract_df['tricks_won'])
    ccdf = 1 - (np.arange(1, len(sorted_tricks) + 1) / len(sorted_tricks))

    ax.plot(sorted_tricks, ccdf, marker='o', markersize=3, linestyle='-',
            label=f"{contract_type.upper()} (n={len(contract_df)})", alpha=0.7)

ax.set_xlabel("Tricks Won")
ax.set_ylabel("P(Tricks >= x)")
ax.set_title("CCDF of Tricks Won by Contract Type (Tail Probabilities)")
ax.set_xlim(-0.5, 10.5)
ax.set_ylim(0, 1)
ax.set_yscale('log')  # Log scale to see tail behavior
ax.grid(alpha=0.3, which='both')
ax.legend()
plt.tight_layout()
plt.show()

print("✓ CCDF plotted")

# %% [markdown]
# ---
#
# ## Section 7: Summary
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

# Test 3: Outcome validity
if 'tricks_won' in outcome_df.columns:
    if outcome_df['tricks_won'].between(0, 10).all():
        summary['passes'].append("✅ Test 3: All tricks_won in valid range [0, 10]")

        # Check contract-specific means
        for contract_type in CONTRACT_TYPES:
            contract_df = outcome_df[outcome_df['contract_type'] == contract_type]
            mean_tricks = contract_df['tricks_won'].mean()
            if 4.0 <= mean_tricks <= 6.0:
                summary['passes'].append(f"  ✅ {contract_type.upper()}: mean={mean_tricks:.3f} in [4.0, 6.0]")
            else:
                summary['warnings'].append(f"  ⚠️  {contract_type.upper()}: mean={mean_tricks:.3f} outside [4.0, 6.0]")
    else:
        summary['failures'].append("❌ Test 3: tricks_won contains invalid values")

# Test 4: Reproducibility
try:
    if (outcome_df['tricks_won'] == outcome_df2['tricks_won']).all():
        summary['passes'].append("✅ Test 4: Outcomes are deterministic")
    else:
        summary['failures'].append("❌ Test 4: Non-deterministic outcomes detected")
except Exception:
    summary['warnings'].append("⚠️  Test 4: Could not verify reproducibility")

# Trump suit balance (if applicable)
if 'trump' in outcome_df.columns and outcome_df['contract_type'].eq('suit').any():
    try:
        suit_df = outcome_df[outcome_df['contract_type'] == 'suit']
        trump_groups = [suit_df[suit_df['trump'] == t]['tricks_won'] for t in TRUMPS_FOR_SUIT_CONTRACTS]
        f_stat, p_value = f_oneway(*trump_groups)
        if p_value >= 0.05:
            summary['passes'].append(f"✅ Trump balance: no significant bias (p={p_value:.3f})")
        else:
            summary['warnings'].append(f"⚠️  Trump balance: bias detected (p={p_value:.3f})")
    except Exception:
        summary['warnings'].append("⚠️  Could not test trump balance")

# Per-strategy seat bias checks
if 'seat_strategy' in outcome_df.columns:
    print("\nPer-Strategy Seat Bias Checks:")
    print("-" * 50)
    for strategy in sorted(outcome_df['seat_strategy'].dropna().unique()):
        strat_df = outcome_df[outcome_df['seat_strategy'] == strategy]
        for contract_type in CONTRACT_TYPES:
            contract_df = strat_df[strat_df['contract_type'] == contract_type]
            if len(contract_df) < 20:
                continue
            seat_groups = [contract_df[contract_df['seat'] == s]['tricks_won'] for s in SEATS]
            # Filter out empty groups
            seat_groups = [g for g in seat_groups if len(g) > 0]
            if len(seat_groups) < 2:
                continue
            f_stat, p_value = f_oneway(*seat_groups)
            status = "⚠️  BIAS" if p_value < 0.05 else "✓"
            print(f"  {strategy} / {contract_type}: p={p_value:.3f} {status}")
            if p_value < 0.05:
                summary['warnings'].append(f"⚠️  Seat bias ({strategy}/{contract_type}): p={p_value:.3f}")
            else:
                summary['passes'].append(f"✅ Seat balance ({strategy}/{contract_type}): p={p_value:.3f}")

# Reversal consistency check (if reverse matchups enabled)
if INCLUDE_REVERSE_MATCHUPS and 'team0_strategy' in outcome_df.columns:
    print("\nReversal Consistency Check:")
    print("-" * 50)

    # Aggregate to deal level with team tricks
    team0_seats = {0, 2}
    team1_seats = {1, 3}

    def _deal_team_tricks(group):
        team0_tricks = group[group['seat'].isin(team0_seats)]['tricks_won'].mean()
        team1_tricks = group[group['seat'].isin(team1_seats)]['tricks_won'].mean()
        return pd.Series({
            'team0_tricks': team0_tricks,
            'team1_tricks': team1_tricks,
            'delta_tricks': team0_tricks - team1_tricks,
        })

    deal_summary = outcome_df.groupby(
        ['strategy_id', 'team0_strategy', 'team1_strategy', 'deal_id'],
        dropna=False,
    ).apply(_deal_team_tricks).reset_index()

    # Check each pair for reversal consistency
    checked_pairs = set()
    for (a, b), group_ab in deal_summary.groupby(['team0_strategy', 'team1_strategy']):
        if pd.isna(a) or pd.isna(b):
            continue
        pair = tuple(sorted([a, b]))
        if pair in checked_pairs:
            continue
        checked_pairs.add(pair)

        # Find reverse matchup
        group_ba = deal_summary[
            (deal_summary['team0_strategy'] == b) &
            (deal_summary['team1_strategy'] == a)
        ]

        if len(group_ba) > 0:
            delta_ab = group_ab['delta_tricks'].mean()
            delta_ba = group_ba['delta_tricks'].mean()
            actual_sum = delta_ab + delta_ba
            status = "✓" if abs(actual_sum) < 0.5 else "⚠️"
            print(f"  {a} vs {b}: delta_ab={delta_ab:+.2f}, delta_ba={delta_ba:+.2f}, sum={actual_sum:+.2f} {status}")

            if abs(actual_sum) >= 0.5:
                summary['warnings'].append(f"⚠️  Reversal asymmetry ({a} vs {b}): sum={actual_sum:+.2f}")
            else:
                summary['passes'].append(f"✅ Reversal consistent ({a} vs {b})")

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
