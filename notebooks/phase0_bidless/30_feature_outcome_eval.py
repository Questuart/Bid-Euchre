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
#     name: python
#     version: 3.11.0
# ---

# %% [markdown]
# # Feature-Outcome Relationship Analysis
#
# **Purpose:** Analyze relationships between hand features and game outcomes (tricks won).
#
# **Focus:**
# - Predictive power of features
# - Feature importance by contract type
# - Seat position effects
# - Strategy performance patterns
#
# **Methodology:**
# - Contract-type segregated analysis
# - Statistical validation (correlation, ANOVA)
# - Bootstrap confidence intervals

# %% [markdown]
# ---
# ## Section 0: Configuration

# %%
# Configuration
MODE = "QUICK"  # or "FULL"
SEED = 42

# Game parameters
CONTRACT_TYPES = ['suit', 'high', 'low']
TRUMPS_FOR_SUIT_CONTRACTS = ['C', 'D', 'H', 'S']
SEATS = [0, 1, 2, 3]

# Sample sizes by mode
SAMPLE_SIZES = {
    'QUICK': 1000,  # Quick validation
    'FULL': 10000,  # Statistical rigor
}

N_DEALS = SAMPLE_SIZES[MODE]
print(f"Mode: {MODE}")
print(f"Sample size: {N_DEALS} deals")
print(f"Total observations: {N_DEALS * len(SEATS) * (len(CONTRACT_TYPES) - 1 + len(TRUMPS_FOR_SUIT_CONTRACTS))}")

# %% [markdown]
# ### Imports

# %%
import warnings

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy.stats import f_oneway, pearsonr

warnings.filterwarnings('ignore')

# Project imports
from bid_euchre.diagnostics.notebook_data import (
    load_or_generate_features,
)

# Display settings
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("Imports complete")

# %% [markdown]
# ---
# ## Section 1: Data Loading

# %%
# Load feature + outcome data
data_df = load_or_generate_features(
    mode=MODE,
    seed=SEED,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    seats=SEATS,
)

print(f"Loaded {len(data_df)} observations")
print(f"\nColumns: {list(data_df.columns)}")
print("\nContract distribution:")
print(data_df['contract_type'].value_counts())
print("\nSeat distribution:")
print(data_df['seat'].value_counts())

# %%
# Validate data quality
print("Data Quality Checks:")
print(f"Missing values: {data_df.isnull().sum().sum()}")
print(f"Tricks won range: [{data_df['tricks_won'].min()}, {data_df['tricks_won'].max()}]")

# Get feature columns
feat_cols = [c for c in data_df.columns if c.startswith('feat_')]
print(f"\nFeature columns ({len(feat_cols)}):")
for col in sorted(feat_cols)[:10]:  # Show first 10
    print(f"  - {col}")
if len(feat_cols) > 10:
    print(f"  ... and {len(feat_cols) - 10} more")

# Display sample
print("\nSample data:")
display_cols = ['deal_id', 'seat', 'contract_type', 'trump', 'tricks_won'] + feat_cols[:5]
data_df[display_cols].head(10)

# %% [markdown]
# ---
# ## Section 2: Feature-Outcome Correlations
#
# Identify which hand features correlate with tricks won.

# %%
# Compute correlations by contract type
feat_cols = [c for c in data_df.columns if c.startswith('feat_')]

correlation_results = []
for contract_type in CONTRACT_TYPES:
    contract_df = data_df[data_df['contract_type'] == contract_type]

    for feat in feat_cols:
        # Skip if feature has no variance
        if contract_df[feat].std() == 0:
            continue

        # Compute Pearson correlation
        corr, p_value = pearsonr(contract_df[feat], contract_df['tricks_won'])

        correlation_results.append({
            'contract_type': contract_type,
            'feature': feat,
            'correlation': corr,
            'p_value': p_value,
            'significant': p_value < 0.05,
            'n_samples': len(contract_df),
        })

corr_df = pd.DataFrame(correlation_results)

# Display top correlations by contract type
print("Top Correlations by Contract Type:")
print("=" * 80)
for contract_type in CONTRACT_TYPES:
    print(f"\n{contract_type.upper()} Contracts:")
    contract_corrs = corr_df[corr_df['contract_type'] == contract_type].sort_values(
        'correlation', key=abs, ascending=False
    ).head(10)

    for _, row in contract_corrs.iterrows():
        sig_marker = "***" if row['significant'] else "   "
        print(f"  {sig_marker} {row['feature']:30s}: r={row['correlation']:+.3f} (p={row['p_value']:.4f})")

print("\n*** = significant at p < 0.05")

# %%
# Correlation heatmap by contract type
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

for i, contract_type in enumerate(CONTRACT_TYPES):
    ax = axes[i]
    contract_corrs = corr_df[corr_df['contract_type'] == contract_type].sort_values(
        'correlation', key=abs, ascending=False
    ).head(15)  # Top 15 features

    # Create heatmap data
    features = contract_corrs['feature'].values
    corrs = contract_corrs['correlation'].values

    # Plot horizontal bar chart
    colors = ['red' if c < 0 else 'green' for c in corrs]
    ax.barh(range(len(features)), corrs, color=colors, alpha=0.6)
    ax.set_yticks(range(len(features)))
    ax.set_yticklabels([f.replace('feat_', '') for f in features], fontsize=8)
    ax.set_xlabel('Correlation with Tricks Won')
    ax.set_title(f'{contract_type.upper()} Contracts\n(Top 15 Features)')
    ax.axvline(0, color='black', linestyle='-', linewidth=0.5)
    ax.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Correlation analysis complete")

# %% [markdown]
# ---
# ## Section 3: Seat Position Effects
#
# Analyze how seat position affects feature importance and outcomes.

# %%
# ANOVA test for seat effects on outcomes
print("Seat Position Analysis:")
print("=" * 80)

for contract_type in CONTRACT_TYPES:
    contract_df = data_df[data_df['contract_type'] == contract_type]

    # Group by seat
    seat_groups = [contract_df[contract_df['seat'] == s]['tricks_won'] for s in SEATS]

    # ANOVA test
    f_stat, p_value = f_oneway(*seat_groups)

    print(f"\n{contract_type.upper()} Contracts:")
    print(f"  F-statistic: {f_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")

    if p_value < 0.05:
        print("  ⚠️  WARNING: Significant seat bias detected (p < 0.05)")
    else:
        print("  ✓ No significant seat bias (p >= 0.05)")

    # Show mean tricks won by seat
    print("  Mean tricks won by seat:")
    for seat in SEATS:
        mean_tricks = contract_df[contract_df['seat'] == seat]['tricks_won'].mean()
        print(f"    Seat {seat}: {mean_tricks:.2f}")

print("\n" + "=" * 80)

# %%
# Violin plots of tricks won by seat and contract type
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

for i, contract_type in enumerate(CONTRACT_TYPES):
    ax = axes[i]
    contract_df = data_df[data_df['contract_type'] == contract_type]

    sns.violinplot(data=contract_df, x='seat', y='tricks_won', ax=ax,
                   palette='Set2', inner='quartile')

    ax.set_title(f'{contract_type.upper()} Contracts - Tricks Won by Seat')
    ax.set_xlabel('Seat Position')
    ax.set_ylabel('Tricks Won')
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

    # Add overall mean line
    mean_val = contract_df['tricks_won'].mean()
    ax.axhline(mean_val, color='red', linestyle='--', linewidth=1, alpha=0.5,
               label=f'Overall={mean_val:.2f}')
    ax.legend(loc='upper right', fontsize=8)

plt.tight_layout()
plt.show()

print("✓ Seat analysis complete")

# %% [markdown]
# ---
# ## Section 4: Trump Suit Effects (Suit Contracts Only)
#
# Examine how trump suit affects feature distributions and predictive power.

# %%
# Trump suit analysis (suit contracts only)
suit_df = data_df[data_df['contract_type'] == 'suit']

if len(suit_df) > 0:
    print("Trump Suit Analysis:")
    print("=" * 80)

    # ANOVA test for trump bias
    trump_groups = [suit_df[suit_df['trump'] == t]['tricks_won'] for t in TRUMPS_FOR_SUIT_CONTRACTS]
    f_stat, p_value = f_oneway(*trump_groups)

    print("\nANOVA Test for Trump Suit Bias:")
    print(f"  F-statistic: {f_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")

    if p_value < 0.05:
        print("  ⚠️  WARNING: Significant trump bias detected (p < 0.05)")
    else:
        print("  ✓ No significant trump bias (p >= 0.05)")

    # Show mean tricks won by trump
    print("\n  Mean tricks won by trump suit:")
    for trump in TRUMPS_FOR_SUIT_CONTRACTS:
        mean_tricks = suit_df[suit_df['trump'] == trump]['tricks_won'].mean()
        n_samples = len(suit_df[suit_df['trump'] == trump])
        print(f"    {trump}: {mean_tricks:.2f} (n={n_samples})")

    print("\n" + "=" * 80)
else:
    print("⚠️  No suit contracts found - skipping trump analysis")

# %% [markdown]
# ---
# ## Section 5: Contract Type Comparison
#
# Compare feature importance and outcome distributions across contract types.

# %%
# Feature importance ranking by contract type
print("Feature Importance Ranking by Contract Type:")
print("=" * 80)

for contract_type in CONTRACT_TYPES:
    print(f"\n{contract_type.upper()} Contracts - Top 10 Features:")
    contract_corrs = corr_df[corr_df['contract_type'] == contract_type].sort_values(
        'correlation', key=abs, ascending=False
    ).head(10)

    for rank, (_, row) in enumerate(contract_corrs.iterrows(), 1):
        feat_name = row['feature'].replace('feat_', '')
        corr = row['correlation']
        sig = "***" if row['significant'] else ""
        print(f"  {rank:2d}. {feat_name:30s}: r={corr:+.3f} {sig}")

print("\n" + "=" * 80)

# %% [markdown]
# ---
# ## Section 6: Summary
#
# Health scorecard and recommendations for model development.

# %%
# Health Scorecard
print("\n" + "=" * 80)
print("FEATURE-OUTCOME ANALYSIS SUMMARY")
print("=" * 80)

summary = {
    'passes': [],
    'warnings': [],
    'info': []
}

# Sample size check
total_obs = len(data_df)
summary['passes'].append(f"✅ Sample size: {total_obs:,} observations")

if total_obs < 1000:
    summary['warnings'].append(f"⚠️  WARNING: Sample size ({total_obs}) < 1000 (recommended minimum for correlation analysis)")

# Seat balance check
for contract_type in CONTRACT_TYPES:
    contract_df = data_df[data_df['contract_type'] == contract_type]
    seat_groups = [contract_df[contract_df['seat'] == s]['tricks_won'] for s in SEATS]
    f_stat, p_value = f_oneway(*seat_groups)

    if p_value >= 0.05:
        summary['passes'].append(f"✅ Seat balance ({contract_type}): p={p_value:.3f} (no bias)")
    else:
        summary['warnings'].append(f"⚠️  Seat bias ({contract_type}): p={p_value:.3f} < 0.05")

# Trump balance check (suit contracts only)
suit_df = data_df[data_df['contract_type'] == 'suit']
if len(suit_df) > 0:
    trump_groups = [suit_df[suit_df['trump'] == t]['tricks_won'] for t in TRUMPS_FOR_SUIT_CONTRACTS]
    f_stat, p_value = f_oneway(*trump_groups)

    if p_value >= 0.05:
        summary['passes'].append(f"✅ Trump balance: p={p_value:.3f} (no bias)")
    else:
        summary['warnings'].append(f"⚠️  Trump bias: p={p_value:.3f} < 0.05")

# Feature correlation summary
n_features = len(feat_cols)
n_significant = len(corr_df[corr_df['significant']])
summary['info'].append(f"ℹ️  Features analyzed: {n_features}")
summary['info'].append(f"ℹ️  Significant correlations: {n_significant}/{len(corr_df)} ({100*n_significant/len(corr_df):.1f}%)")

# Top features by contract type
for contract_type in CONTRACT_TYPES:
    top_feat = corr_df[corr_df['contract_type'] == contract_type].sort_values(
        'correlation', key=abs, ascending=False
    ).iloc[0]
    feat_name = top_feat['feature'].replace('feat_', '')
    summary['info'].append(f"ℹ️  Top feature ({contract_type}): {feat_name} (r={top_feat['correlation']:+.3f})")

# Print summary
print("\nPASSES:")
for item in summary['passes']:
    print(f"  {item}")

if summary['warnings']:
    print("\nWARNINGS:")
    for item in summary['warnings']:
        print(f"  {item}")

print("\nINFO:")
for item in summary['info']:
    print(f"  {item}")

if not summary['warnings']:
    print("\n✅ ALL HEALTH CHECKS PASSED")
else:
    print(f"\n⚠️  {len(summary['warnings'])} WARNING(S) DETECTED - Review above")

print("=" * 80)
print("\n🎯 Next Steps:")
print("  1. If sample size warnings, run with MODE='FULL' for more data")
print("  2. Use top features for model development")
print("  3. Consider contract-specific models given different feature importance")
print("  4. Review seat/trump warnings if present")
