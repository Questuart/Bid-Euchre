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

# Strategy configuration (head-to-head matchups)
STRATEGIES = [
    {"name": "greedy", "class_name": "GreedyStrategy"},
    {"name": "glutton", "class_name": "GluttonStrategy"},
    {"name": "always_highest", "class_name": "AlwaysHighestLegalStrategy"},
    {"name": "always_lowest", "class_name": "AlwaysLowestLegalStrategy"},
]

MATCHUP_MODE = "reverse_matchups"  # "reverse_matchups" or "per_seat_rotations"
INCLUDE_REVERSE_MATCHUPS = True
N_ROTATIONS = 4  # Used when MATCHUP_MODE="per_seat_rotations"

# Sample sizes by mode
SAMPLE_SIZES = {
    'QUICK': 1000,  # Quick validation
    'FULL': 10000,  # Statistical rigor
}

N_DEALS = SAMPLE_SIZES[MODE]
print(f"Mode: {MODE}")
print(f"Sample size: {N_DEALS} deals")
print(f"Total observations: {N_DEALS * len(SEATS) * (len(CONTRACT_TYPES) - 1 + len(TRUMPS_FOR_SUIT_CONTRACTS))}")
print(f"Strategies: {[s['name'] for s in STRATEGIES]}")
print(f"Matchup mode: {MATCHUP_MODE}")

# %% [markdown]
# ### Imports

# %%
import itertools
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from IPython.display import display
from scipy.stats import f_oneway, pearsonr
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.multitest import multipletests

warnings.filterwarnings('ignore')

# Project imports
from bid_euchre.diagnostics.notebook_data import (
    load_or_generate_features,
)
from bid_euchre.diagnostics.strategy_charts import (
    plot_matchup_summary,
    plot_tricks_distribution_comparison,
    plot_win_rate_heatmap,
)

# Display settings
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("Imports complete")


# %%
def build_round_robin_matchups(strategy_names, include_reverse=True):
    pairs = list(itertools.combinations(strategy_names, 2))
    matchups = [{"team0": a, "team1": b} for a, b in pairs]
    if include_reverse:
        matchups += [{"team0": b, "team1": a} for a, b in pairs]
    return matchups


def build_per_seat_matchups(strategy_names, n_rotations=4):
    pairs = list(itertools.combinations(strategy_names, 2))
    rotations = [
        (0, 1, 2, 3),
        (1, 0, 3, 2),
        (2, 3, 0, 1),
        (3, 2, 1, 0),
    ]
    rotations = rotations[:max(1, min(n_rotations, len(rotations)))]

    matchups = []
    for a, b in pairs:
        base = [a, b, a, b]
        for perm in rotations:
            seat_strategies = [base[i] for i in perm]
            matchups.append({"seat_strategies": seat_strategies})
    return matchups


STRATEGY_NAMES = [s["name"] for s in STRATEGIES]
if MATCHUP_MODE == "per_seat_rotations":
    MATCHUPS = build_per_seat_matchups(STRATEGY_NAMES, n_rotations=N_ROTATIONS)
else:
    MATCHUPS = build_round_robin_matchups(STRATEGY_NAMES, include_reverse=INCLUDE_REVERSE_MATCHUPS)

print(f"Matchups: {len(MATCHUPS)}")

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
    strategies=STRATEGIES,
    matchups=MATCHUPS,
)

print(f"Loaded {len(data_df)} observations")
print(f"\nColumns: {list(data_df.columns)}")
print("\nContract distribution:")
print(data_df['contract_type'].value_counts())
print("\nSeat distribution:")
print(data_df['seat'].value_counts())
print("\nStrategy distribution:")
print(data_df['strategy_id'].value_counts().head(10))

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
# ## Section 2: Strategy Comparison (Head-to-Head)
#
# Evaluate which strategies perform best in head-to-head matchups and whether performance drifts over time.

# %%
# Build per-deal matchup summaries
matchup_df = data_df.copy()


def parse_matchup_id(strategy_id: str) -> dict:
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


matchup_meta = matchup_df['strategy_id'].apply(parse_matchup_id).apply(pd.Series)
matchup_df = pd.concat([matchup_df, matchup_meta], axis=1)
matchup_df = matchup_df[matchup_df['team0_strategy'].notna()]

# Aggregate team tricks per deal
team0_seats = {0, 2}
team1_seats = {1, 3}


def _deal_team_tricks(group: pd.DataFrame) -> pd.Series:
    team0_tricks = group[group['seat'].isin(team0_seats)]['tricks_won'].mean()
    team1_tricks = group[group['seat'].isin(team1_seats)]['tricks_won'].mean()
    return pd.Series({
        'team0_tricks': team0_tricks,
        'team1_tricks': team1_tricks,
        'delta_tricks': team0_tricks - team1_tricks,
    })


deal_summary = matchup_df.groupby(
    ['strategy_id', 'team0_strategy', 'team1_strategy', 'deal_id', 'contract_type', 'trump'],
    dropna=False,
).apply(_deal_team_tricks).reset_index()

# Build matchup results for plotting
matchup_results = {}
summary_rows = []
for (team0, team1), group in deal_summary.groupby(['team0_strategy', 'team1_strategy']):
    win_rate = (group['team0_tricks'] > 5).mean()
    mean_team0 = group['team0_tricks'].mean()
    mean_team1 = group['team1_tricks'].mean()
    matchup_results[(team0, team1)] = {
        'win_rate': win_rate,
        'tricks_team0': group['team0_tricks'].tolist(),
        'tricks_team1': group['team1_tricks'].tolist(),
        'mean_tricks_team0': mean_team0,
        'mean_tricks_team1': mean_team1,
        'n_deals': len(group),
    }
    summary_rows.append({
        'team0': team0,
        'team1': team1,
        'n_deals': len(group),
        'win_rate_team0': win_rate,
        'mean_tricks_team0': mean_team0,
        'mean_tricks_team1': mean_team1,
        'mean_delta': (mean_team0 - mean_team1),
    })

summary_df = pd.DataFrame(summary_rows).sort_values('mean_delta', ascending=False)
summary_df.head(10)

# %%
# Win-rate heatmap (Team 0 vs Team 1)
fig = plot_win_rate_heatmap(matchup_results, metric="win_rate")
plt.show()

# Matchup summary table
plot_matchup_summary(matchup_results)
plt.show()

# %%
# Trick distribution comparisons (Team 0 perspective)
plot_tricks_distribution_comparison(matchup_results, team=0)
plt.show()

# Rolling delta timeline to detect drift
ROLLING_WINDOW = 50

rolling_rows = []
for (team0, team1), group in deal_summary.groupby(['team0_strategy', 'team1_strategy']):
    group_sorted = group.sort_values('deal_id')
    rolling = group_sorted['delta_tricks'].rolling(ROLLING_WINDOW, min_periods=10).mean()
    rolling_rows.append(pd.DataFrame({
        'deal_id': group_sorted['deal_id'],
        'rolling_delta': rolling,
        'matchup': f"{team0}_vs_{team1}",
    }))

rolling_df = pd.concat(rolling_rows, ignore_index=True)
plt.figure(figsize=(12, 6))
sns.lineplot(data=rolling_df, x='deal_id', y='rolling_delta', hue='matchup', alpha=0.7)
plt.axhline(0, color='black', linewidth=0.8)
plt.title(f"Rolling mean delta (Team0 - Team1), window={ROLLING_WINDOW}")
plt.ylabel("Rolling delta tricks")
plt.xlabel("Deal ID")
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
plt.tight_layout()
plt.show()


# %% [markdown]
# ---
# ## Section 3: Strategy Performance Analysis (Per-Seat)
#
# Analyze outcomes by **individual strategy** (not matchup-level), breaking down by seat position, contract type, and trump suit.
#
# **Critical Note:** In head-to-head mode, `strategy_id` is a matchup identifier (e.g., `"greedy_vs_glutton"`), NOT the per-seat strategy. We derive `seat_strategy` from the matchup metadata to analyze per-strategy performance.

# %%
# Derive per-seat strategy from matchup metadata
# CRITICAL: In head-to-head mode, strategy_id is a matchup ID (e.g., "greedy_vs_glutton")
# We must map each row's seat to its corresponding strategy

def get_seat_strategy(row):
    """Map a row's seat to its strategy from the parsed matchup metadata."""
    seat = row['seat']
    col_name = f'seat{seat}_strategy'
    return row.get(col_name, None)

# Apply to matchup_df (already has seat{N}_strategy columns from parse_matchup_id)
matchup_df['seat_strategy'] = matchup_df.apply(get_seat_strategy, axis=1)

# Filter to rows with valid seat_strategy
analysis_df = matchup_df[matchup_df['seat_strategy'].notna()].copy()

print(f"Analysis rows with seat_strategy: {len(analysis_df)}")
print(f"Unique seat strategies: {sorted(analysis_df['seat_strategy'].unique())}")
print("\nSeat strategy distribution:")
print(analysis_df['seat_strategy'].value_counts())

# %%
# Strategy × Seat Heatmap
# Shows mean tricks won by each strategy at each seat position (aggregated across contracts)

strategy_seat = analysis_df.groupby(['seat_strategy', 'seat'])['tricks_won'].mean().unstack()

fig, ax = plt.subplots(figsize=(10, 6))
sns.heatmap(strategy_seat, annot=True, fmt='.2f', cmap='RdYlGn', center=5.0, ax=ax)
ax.set_title('Mean Tricks Won by Strategy × Seat Position')
ax.set_xlabel('Seat Position')
ax.set_ylabel('Strategy')
plt.tight_layout()
plt.show()

# Sample size check
print("\nSample sizes per Strategy × Seat:")
strategy_seat_counts = analysis_df.groupby(['seat_strategy', 'seat']).size().unstack()
print(strategy_seat_counts)

min_cell = strategy_seat_counts.min().min()
if min_cell < 100:
    print(f"\n⚠️  WARNING: Minimum cell count = {min_cell}. Consider MODE='FULL' for robust estimates.")

# %%
# Strategy × Contract Type Comparison
# Shows mean tricks won by each strategy for each contract type

strategy_contract = analysis_df.groupby(['seat_strategy', 'contract_type'])['tricks_won'].mean().unstack()

fig, ax = plt.subplots(figsize=(12, 6))
strategy_contract.plot(kind='bar', ax=ax, width=0.8)
ax.set_title('Mean Tricks Won by Strategy × Contract Type')
ax.set_xlabel('Strategy')
ax.set_ylabel('Mean Tricks Won')
ax.axhline(5.0, color='black', linestyle='--', alpha=0.5, label='Expected (5.0)')
ax.legend(title='Contract Type')
ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
plt.tight_layout()
plt.show()

# Show numeric table
print("\nStrategy × Contract Type (mean tricks):")
print(strategy_contract.round(2))

# %%
# Strategy × Trump Suit Comparison (Suit Contracts Only)
# Shows mean tricks won by each strategy for each trump suit

suit_only = analysis_df[analysis_df['contract_type'] == 'suit']

if len(suit_only) > 0:
    strategy_trump = suit_only.groupby(['seat_strategy', 'trump'])['tricks_won'].mean().unstack()

    fig, ax = plt.subplots(figsize=(12, 6))
    strategy_trump.plot(kind='bar', ax=ax, width=0.8)
    ax.set_title('Mean Tricks Won by Strategy × Trump Suit (Suit Contracts Only)')
    ax.set_xlabel('Strategy')
    ax.set_ylabel('Mean Tricks Won')
    ax.axhline(5.0, color='black', linestyle='--', alpha=0.5)
    ax.legend(title='Trump Suit')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    plt.show()

    # Show numeric table
    print("\nStrategy × Trump (mean tricks, suit contracts only):")
    print(strategy_trump.round(2))

    # Sample size warning
    strategy_trump_counts = suit_only.groupby(['seat_strategy', 'trump']).size().unstack()
    min_cell = strategy_trump_counts.min().min()
    if min_cell < 50:
        print(f"\n⚠️  WARNING: Minimum cell count = {min_cell}. Recommend MODE='FULL' for Strategy × Trump analysis.")
else:
    print("⚠️  No suit contracts available for Strategy × Trump analysis")

# %% [markdown]
# ---
# ## Section 4: Feature-Outcome Correlations
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

# Apply FDR correction per contract type
corr_df['p_adj'] = np.nan
corr_df['significant_adj'] = False
for contract_type in CONTRACT_TYPES:
    mask = corr_df['contract_type'] == contract_type
    pvals = corr_df.loc[mask, 'p_value'].values
    if len(pvals) > 0:
        _, p_adj, _, _ = multipletests(pvals, method="fdr_bh")
        corr_df.loc[mask, 'p_adj'] = p_adj
        corr_df.loc[mask, 'significant_adj'] = p_adj < 0.05

# Display top correlations by contract type (as tables)
print("Top Correlations by Contract Type")
print("=" * 80)

for contract_type in CONTRACT_TYPES:
    contract_corrs = corr_df[corr_df['contract_type'] == contract_type].sort_values(
        'correlation', key=abs, ascending=False
    ).head(15).copy()
    contract_corrs['feature'] = contract_corrs['feature'].str.replace('feat_', '', regex=False)
    display_cols = ['feature', 'correlation', 'p_value', 'p_adj', 'significant_adj', 'n_samples']
    print(f"\n{contract_type.upper()} Contracts")
    display(contract_corrs[display_cols])

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

    # Plot horizontal bar chart (highest correlations on top)
    colors = ['red' if c < 0 else 'green' for c in corrs]
    ax.barh(range(len(features)), corrs, color=colors, alpha=0.6)
    ax.set_yticks(range(len(features)))
    ax.set_yticklabels([f.replace('feat_', '') for f in features], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('Correlation with Tricks Won')
    ax.set_title(f'{contract_type.upper()} Contracts\n(Top 15 Features)')
    ax.axvline(0, color='black', linestyle='-', linewidth=0.5)
    ax.grid(axis='x', alpha=0.3)

plt.tight_layout()
plt.show()

print("✓ Correlation analysis complete")

# %% [markdown]
# ---
# ## Section 5: Predictive Modeling & Feature Importance
#
# Train simple predictive models per contract type and compute permutation-based feature importance.

# %%
# Train/test models per contract type
model_rows = []
importance_tables = {}
ols_tables = {}

feat_cols = [c for c in data_df.columns if c.startswith('feat_')]

for contract_type in CONTRACT_TYPES:
    contract_df = data_df[data_df['contract_type'] == contract_type]
    X = contract_df[feat_cols].select_dtypes(include=[np.number])
    y = contract_df['tricks_won']

    if len(contract_df) < 50:
        print(f"Skipping {contract_type}: not enough data")
        continue

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=SEED
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    ridge = Ridge(alpha=1.0, random_state=SEED)
    ridge.fit(X_train_scaled, y_train)

    y_pred = ridge.predict(X_test_scaled)
    model_rows.append({
        'contract_type': contract_type,
        'r2': r2_score(y_test, y_pred),
        'mae': mean_absolute_error(y_test, y_pred),
        'n_train': len(X_train),
        'n_test': len(X_test),
    })

    perm = permutation_importance(
        ridge, X_test_scaled, y_test, n_repeats=5, random_state=SEED
    )
    perm_df = pd.DataFrame({
        'feature': X.columns,
        'perm_importance': perm.importances_mean,
        'perm_std': perm.importances_std,
    }).sort_values('perm_importance', ascending=False)
    perm_df['feature'] = perm_df['feature'].str.replace('feat_', '', regex=False)
    importance_tables[contract_type] = perm_df

    X_train_sm = sm.add_constant(X_train_scaled)
    ols = sm.OLS(y_train, X_train_sm).fit()
    ci = ols.conf_int()
    ols_df = pd.DataFrame({
        'feature': ['const'] + list(X.columns),
        'coef': ols.params,
        'p_value': ols.pvalues,
        'ci_lower': ci[0].values,
        'ci_upper': ci[1].values,
    })
    ols_df['feature'] = ols_df['feature'].str.replace('feat_', '', regex=False)
    ols_tables[contract_type] = ols_df

model_summary_df = pd.DataFrame(model_rows)
model_summary_df

# %%
# Display importance and coefficient summaries
for contract_type in CONTRACT_TYPES:
    if contract_type not in importance_tables:
        continue
    print(f"\n{contract_type.upper()} - Permutation Importance (Top 10)")
    display(importance_tables[contract_type].head(10))

    coef_df = ols_tables[contract_type]
    coef_df = coef_df[coef_df['feature'] != 'const'].copy()
    coef_df['abs_coef'] = coef_df['coef'].abs()
    print(f"\n{contract_type.upper()} - OLS Coefficients (Top 10 by |coef|)")
    display(coef_df.sort_values('abs_coef', ascending=False).head(10))

# %%
# Top-9 feature relationship plots per contract type
for contract_type in CONTRACT_TYPES:
    if contract_type not in importance_tables:
        continue

    contract_df = data_df[data_df['contract_type'] == contract_type]
    top_feats = importance_tables[contract_type]['feature'].head(9).tolist()
    feat_cols_for_plot = [f"feat_{name}" for name in top_feats if f"feat_{name}" in contract_df.columns]

    if not feat_cols_for_plot:
        continue

    fig, axes = plt.subplots(3, 3, figsize=(14, 12))
    axes = axes.flatten()

    for ax, feat_col in zip(axes, feat_cols_for_plot):
        sns.regplot(
            data=contract_df,
            x=feat_col,
            y='tricks_won',
            ax=ax,
            scatter_kws={'alpha': 0.3, 's': 10},
            line_kws={'color': 'red'},
        )
        ax.set_title(feat_col.replace('feat_', ''))
        ax.set_xlabel('')
        ax.set_ylabel('')

    for ax in axes[len(feat_cols_for_plot):]:
        ax.axis('off')

    fig.suptitle(f"{contract_type.upper()} Contracts - Top Feature Relationships", y=1.02)
    plt.tight_layout()
    plt.show()

# %% [markdown]
# ---
# ## Section 6: Seat Position Effects
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
# ## Section 7: Trump Suit Effects (Suit Contracts Only)
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
# ### Matchup Mode Notes
#
# - `reverse_matchups` uses team0/team1 with reversals to mitigate team assignment bias.
# - `per_seat_rotations` uses `seat_strategies` permutations to explore seat effects (higher runtime).

# %%
if MATCHUP_MODE == "per_seat_rotations":
    print(f"Per-seat rotations enabled (N_ROTATIONS={N_ROTATIONS})")
else:
    print("Reverse matchups enabled")

# %% [markdown]
# ---
# ## Section 8: Summary
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
n_significant = len(corr_df[corr_df['significant_adj']])
summary['info'].append(f"ℹ️  Features analyzed: {n_features}")
summary['info'].append(
    f"ℹ️  Significant correlations (FDR): {n_significant}/{len(corr_df)} "
    f"({100*n_significant/len(corr_df):.1f}%)"
)

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
