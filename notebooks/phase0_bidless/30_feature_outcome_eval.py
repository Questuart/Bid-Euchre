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
# - Strategy performance patterns (per-strategy breakdowns)
#
# **Methodology:**
# - Contract-type segregated analysis
# - Statistical validation (correlation, ANOVA with FDR correction)
# - Bootstrap confidence intervals

# %% [markdown]
# ## Outline
#
# - **Section 0: Configuration** - Mode, strategies, matchups
# - **Section 1: Data Loading** - Feature + outcome data validation
# - **Section 2: Strategy Comparison**
#   - 2.1 Win Rate Evaluation
#   - 2.2 Trick Distribution by Strategy
#   - 2.3 Matchup Summary Table
#   - 2.4 Performance by Contract Type
#   - 2.5 Performance by Suit
#   - 2.6 Performance by Team
#   - 2.7 Performance by Seat
#   - 2.8 Rolling Mean Delta
# - **Section 3: Feature-Outcome Correlations**
# - **Section 4: Predictive Modeling & Feature Importance**
# - **Section 5: Summary** - Health scorecard

# %% [markdown]
# ---
# ## Section 0: Configuration

# %% tags=["parameters"]
# Configuration (papermill parameters)
MODE = "QUICK"  # "SMOKE" (~30 deals), "QUICK" (~2k deals), or "FULL" (~50k deals)
SEED = 42

# Game parameters
CONTRACT_TYPES = ['suit', 'high', 'low']
TRUMPS_FOR_SUIT_CONTRACTS = ['C', 'D', 'H', 'S']
SEATS = [0, 1, 2, 3]

# Strategy configuration (head-to-head matchups)
STRATEGIES = [
    {"name": "greedy", "class_name": "GreedyStrategy"},
    {"name": "glutton", "class_name": "GluttonStrategy"},
    {"name": "random", "class_name": "RandomLegalStrategy"},
    {"name": "always_highest", "class_name": "AlwaysHighestLegalStrategy"},
    {"name": "always_lowest", "class_name": "AlwaysLowestLegalStrategy"},
]

MATCHUP_MODE = "reverse_matchups"  # "reverse_matchups" or "per_seat_rotations"
INCLUDE_REVERSE_MATCHUPS = True
INCLUDE_SELF_PLAY = True  # Include self-play matchups (strategy vs itself)
N_ROTATIONS = 4  # Used when MATCHUP_MODE="per_seat_rotations"

# Sample sizes by mode
SAMPLE_SIZES = {
    'SMOKE': 100,   # CI smoke test
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
from scipy.stats import f_oneway, pearsonr, ttest_ind
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
    plot_win_rate_heatmap,
)

# Display settings
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("Imports complete")


# %%
def build_round_robin_matchups(strategy_names, include_reverse=True, include_self_play=True):
    """Build matchups for team-based head-to-head evaluation.

    Args:
        strategy_names: List of strategy names
        include_reverse: Include reversed matchups (B vs A for each A vs B)
        include_self_play: Include self-play matchups (A vs A)

    Returns:
        List of matchup dicts with team0/team1 keys
    """
    pairs = list(itertools.combinations(strategy_names, 2))
    matchups = [{"team0": a, "team1": b} for a, b in pairs]
    if include_reverse:
        matchups += [{"team0": b, "team1": a} for a, b in pairs]
    if include_self_play:
        matchups += [{"team0": s, "team1": s} for s in strategy_names]
    return matchups


def build_per_seat_matchups(strategy_names, n_rotations=4, include_self_play=True):
    """Build matchups for per-seat strategy evaluation.

    Args:
        strategy_names: List of strategy names
        n_rotations: Number of seat rotations per pair
        include_self_play: Include self-play matchups (all seats same strategy)

    Returns:
        List of matchup dicts with seat_strategies keys
    """
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
    if include_self_play:
        matchups += [{"seat_strategies": [s, s, s, s]} for s in strategy_names]
    return matchups


STRATEGY_NAMES = [s["name"] for s in STRATEGIES]
if MATCHUP_MODE == "per_seat_rotations":
    MATCHUPS = build_per_seat_matchups(
        STRATEGY_NAMES, n_rotations=N_ROTATIONS, include_self_play=INCLUDE_SELF_PLAY
    )
else:
    MATCHUPS = build_round_robin_matchups(
        STRATEGY_NAMES, include_reverse=INCLUDE_REVERSE_MATCHUPS, include_self_play=INCLUDE_SELF_PLAY
    )

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
# ## Section 2: Strategy Comparison
#
# Evaluate strategy performance through multiple lenses: win rates, trick distributions,
# and breakdowns by contract type, suit, team, and seat. Each subsection uses the
# "B = one panel per strategy" pattern for consistent visualization.
#
# **Definitions:**
# - `strategy_id`: Matchup identifier (e.g., "greedy_vs_glutton" or self-play "greedy_vs_greedy")
# - Team win: `team0_tricks > 5` (more than half of 10 tricks)
# - Win rate: P(team0_tricks > 5) per matchup
# - Delta: `team0_tricks - team1_tricks`
#
# **Sample size note:** For stable ANOVA bias detection, ~2,000 deals per factor level is recommended.

# %%
# Build per-deal matchup summaries
matchup_df = data_df.copy()


def parse_matchup_id(strategy_id: str) -> dict:
    """Parse strategy_id to extract team and seat strategies."""
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
    """Compute team-level trick aggregates for a deal."""
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

# Derive per-seat strategy for per-strategy analysis
def get_seat_strategy(row):
    """Map a row's seat to its strategy from the parsed matchup metadata."""
    seat = row['seat']
    col_name = f'seat{seat}_strategy'
    return row.get(col_name, None)

matchup_df['seat_strategy'] = matchup_df.apply(get_seat_strategy, axis=1)
analysis_df = matchup_df[matchup_df['seat_strategy'].notna()].copy()

print(f"Deal summaries: {len(deal_summary)}")
print(f"Analysis rows with seat_strategy: {len(analysis_df)}")
print(f"Unique seat strategies: {sorted(analysis_df['seat_strategy'].unique())}")

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

# %% [markdown]
# ### 2.1 Win Rate Evaluation
#
# Two-metric heatmaps showing win rate and mean delta across matchups, plus ANOVA on delta for fairness.

# %%
# Win-rate heatmap (Team 0 vs Team 1)
fig = plot_win_rate_heatmap(matchup_results, metric="win_rate")
plt.show()

# Mean delta heatmap
fig = plot_win_rate_heatmap(matchup_results, metric="mean_tricks_team0", title="Mean Tricks (Team 0) Heatmap")
plt.show()

# Fairness check: ANOVA on delta_tricks across matchups
print("\nFairness Check: ANOVA on delta_tricks across matchups")
print("=" * 60)
matchup_groups = [
    group['delta_tricks'].values
    for _, group in deal_summary.groupby(['team0_strategy', 'team1_strategy'])
]
f_stat, p_value = f_oneway(*matchup_groups)
n_matchups = len(matchup_groups)
n_obs = sum(len(g) for g in matchup_groups)
# Eta-squared effect size
ss_between = sum(len(g) * (np.mean(g) - deal_summary['delta_tricks'].mean())**2 for g in matchup_groups)
ss_total = ((deal_summary['delta_tricks'] - deal_summary['delta_tricks'].mean())**2).sum()
eta_sq = ss_between / ss_total if ss_total > 0 else 0

print(f"  Matchups: {n_matchups}, Total observations: {n_obs}")
print(f"  F-statistic: {f_stat:.4f}")
print(f"  p-value: {p_value:.4f}")
print(f"  η² (effect size): {eta_sq:.4f}")
if p_value < 0.05:
    print("  ⚠️  Significant matchup effect detected (p < 0.05)")
else:
    print("  ✓ No significant matchup effect (p >= 0.05)")

# %% [markdown]
# ### 2.2 Trick Distribution by Strategy (B pattern)
#
# Faceted grid showing strategy-normalized delta for each strategy.
# For each deal where a strategy appears, the delta is oriented so positive = advantage for that strategy.

# %%
# Build strategy-normalized delta DataFrame
strategy_delta_rows = []
for _, row in deal_summary.iterrows():
    team0, team1 = row['team0_strategy'], row['team1_strategy']
    delta = row['delta_tricks']
    deal_id = row['deal_id']

    # Strategy as team0: positive delta = advantage
    strategy_delta_rows.append({
        'strategy': team0,
        'normalized_delta': delta,
        'deal_id': deal_id,
    })
    # Strategy as team1: negative delta = advantage (flip sign)
    if team0 != team1:  # Avoid double-counting self-play
        strategy_delta_rows.append({
            'strategy': team1,
            'normalized_delta': -delta,
            'deal_id': deal_id,
        })

strategy_delta_df = pd.DataFrame(strategy_delta_rows)

# Faceted grid: one subplot per strategy
strategies = sorted(strategy_delta_df['strategy'].unique())
n_strategies = len(strategies)
n_cols = min(4, n_strategies)
n_rows = (n_strategies + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
if n_strategies == 1:
    axes = np.array([[axes]])
axes = np.atleast_2d(axes)

for idx, strategy in enumerate(strategies):
    row_idx, col_idx = divmod(idx, n_cols)
    ax = axes[row_idx, col_idx]

    strat_data = strategy_delta_df[strategy_delta_df['strategy'] == strategy]['normalized_delta']
    n_samples = len(strat_data)

    # Violin + box overlay
    parts = ax.violinplot([strat_data.values], positions=[0], showmeans=False, showmedians=False)
    for pc in parts['bodies']:
        pc.set_facecolor('steelblue')
        pc.set_alpha(0.6)
    ax.boxplot([strat_data.values], positions=[0], widths=0.2)

    ax.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax.set_title(f"{strategy}\n(n={n_samples})")
    ax.set_ylabel("Normalized Delta")
    ax.set_xticks([])
    ax.set_ylim(-6, 6)
    ax.grid(axis='y', alpha=0.3)

# Hide unused axes
for idx in range(n_strategies, n_rows * n_cols):
    row_idx, col_idx = divmod(idx, n_cols)
    axes[row_idx, col_idx].axis('off')

fig.suptitle("Strategy-Normalized Trick Delta (positive = strategy advantage)", fontsize=12)
plt.tight_layout()
plt.show()

# %% [markdown]
# ### 2.3 Matchup Summary Table

# %%
# Display matchup summary
print("Matchup Summary (sorted by mean_delta):")
display(summary_df.round(3))

# 3-panel summary plot (uses fixed plot_matchup_summary)
plot_matchup_summary(matchup_results, metric_key="mean_tricks_team0")
plt.show()

# %% [markdown]
# ### 2.4 Strategy Performance by Contract Type (B pattern)
#
# One subplot per strategy showing trick distribution by contract type, with ANOVA + FDR correction.

# %%
strategies = sorted(analysis_df['seat_strategy'].unique())
n_strategies = len(strategies)
n_cols = min(4, n_strategies)
n_rows = (n_strategies + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
if n_strategies == 1:
    axes = np.array([[axes]])
axes = np.atleast_2d(axes)

anova_results_contract = []

for idx, strategy in enumerate(strategies):
    row_idx, col_idx = divmod(idx, n_cols)
    ax = axes[row_idx, col_idx]

    strat_df = analysis_df[analysis_df['seat_strategy'] == strategy]

    # ANOVA across contract types
    contract_groups = [
        strat_df[strat_df['contract_type'] == ct]['tricks_won'].values
        for ct in CONTRACT_TYPES
        if len(strat_df[strat_df['contract_type'] == ct]) > 0
    ]

    if len(contract_groups) >= 2 and all(len(g) > 0 for g in contract_groups):
        f_stat, p_value = f_oneway(*contract_groups)
        # Eta-squared
        overall_mean = strat_df['tricks_won'].mean()
        ss_between = sum(len(g) * (np.mean(g) - overall_mean)**2 for g in contract_groups)
        ss_total = ((strat_df['tricks_won'] - overall_mean)**2).sum()
        eta_sq = ss_between / ss_total if ss_total > 0 else 0
    else:
        f_stat, p_value, eta_sq = np.nan, np.nan, np.nan

    anova_results_contract.append({
        'strategy': strategy,
        'f_stat': f_stat,
        'p_value': p_value,
        'eta_sq': eta_sq,
        'n': len(strat_df),
    })

    # Violin plot by contract type
    contract_data = [strat_df[strat_df['contract_type'] == ct]['tricks_won'].values for ct in CONTRACT_TYPES]
    positions = range(len(CONTRACT_TYPES))

    parts = ax.violinplot(contract_data, positions=positions, showmeans=False, showmedians=False)
    for pc in parts['bodies']:
        pc.set_facecolor('steelblue')
        pc.set_alpha(0.6)
    ax.boxplot(contract_data, positions=positions, widths=0.2)

    ax.axhline(5.0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax.set_title(f"{strategy}\n(n={len(strat_df)}, η²={eta_sq:.3f})")
    ax.set_xticks(positions)
    ax.set_xticklabels(CONTRACT_TYPES, fontsize=8)
    ax.set_ylabel("Tricks Won")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

# Hide unused axes
for idx in range(n_strategies, n_rows * n_cols):
    row_idx, col_idx = divmod(idx, n_cols)
    axes[row_idx, col_idx].axis('off')

fig.suptitle("Strategy Performance by Contract Type", fontsize=12)
plt.tight_layout()
plt.show()

# FDR correction
anova_contract_df = pd.DataFrame(anova_results_contract)
valid_p = anova_contract_df['p_value'].dropna()
if len(valid_p) > 0:
    _, p_adj, _, _ = multipletests(valid_p.values, method='fdr_bh')
    anova_contract_df.loc[valid_p.index, 'p_adj'] = p_adj

print("\nANOVA Results by Strategy (Contract Type Effect):")
print("Note: Tricks are discrete (0-10); ANOVA is robust but Kruskal-Wallis is an alternative.")
display(anova_contract_df.round(4))

# %% [markdown]
# ### 2.5 Strategy Performance by Suit (B pattern)
#
# Suit contracts only: one subplot per strategy showing trick distribution by trump suit.

# %%
suit_only = analysis_df[analysis_df['contract_type'] == 'suit']

if len(suit_only) > 0:
    strategies = sorted(suit_only['seat_strategy'].unique())
    n_strategies = len(strategies)
    n_cols = min(4, n_strategies)
    n_rows = (n_strategies + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
    if n_strategies == 1:
        axes = np.array([[axes]])
    axes = np.atleast_2d(axes)

    anova_results_suit = []

    for idx, strategy in enumerate(strategies):
        row_idx, col_idx = divmod(idx, n_cols)
        ax = axes[row_idx, col_idx]

        strat_df = suit_only[suit_only['seat_strategy'] == strategy]

        # ANOVA across trump suits
        suit_groups = [
            strat_df[strat_df['trump'] == t]['tricks_won'].values
            for t in TRUMPS_FOR_SUIT_CONTRACTS
            if len(strat_df[strat_df['trump'] == t]) > 0
        ]

        if len(suit_groups) >= 2 and all(len(g) > 0 for g in suit_groups):
            f_stat, p_value = f_oneway(*suit_groups)
            overall_mean = strat_df['tricks_won'].mean()
            ss_between = sum(len(g) * (np.mean(g) - overall_mean)**2 for g in suit_groups)
            ss_total = ((strat_df['tricks_won'] - overall_mean)**2).sum()
            eta_sq = ss_between / ss_total if ss_total > 0 else 0
        else:
            f_stat, p_value, eta_sq = np.nan, np.nan, np.nan

        anova_results_suit.append({
            'strategy': strategy,
            'f_stat': f_stat,
            'p_value': p_value,
            'eta_sq': eta_sq,
            'n': len(strat_df),
        })

        # Violin plot by trump suit
        suit_data = [strat_df[strat_df['trump'] == t]['tricks_won'].values for t in TRUMPS_FOR_SUIT_CONTRACTS]
        positions = range(len(TRUMPS_FOR_SUIT_CONTRACTS))

        parts = ax.violinplot(suit_data, positions=positions, showmeans=False, showmedians=False)
        for pc in parts['bodies']:
            pc.set_facecolor('darkgreen')
            pc.set_alpha(0.6)
        ax.boxplot(suit_data, positions=positions, widths=0.2)

        ax.axhline(5.0, color='red', linestyle='--', linewidth=1, alpha=0.7)
        ax.set_title(f"{strategy}\n(n={len(strat_df)}, η²={eta_sq:.3f})")
        ax.set_xticks(positions)
        ax.set_xticklabels(TRUMPS_FOR_SUIT_CONTRACTS, fontsize=8)
        ax.set_ylabel("Tricks Won")
        ax.set_ylim(-0.5, 10.5)
        ax.grid(axis='y', alpha=0.3)

    # Hide unused axes
    for idx in range(n_strategies, n_rows * n_cols):
        row_idx, col_idx = divmod(idx, n_cols)
        axes[row_idx, col_idx].axis('off')

    fig.suptitle("Strategy Performance by Trump Suit (Suit Contracts Only)", fontsize=12)
    plt.tight_layout()
    plt.show()

    # FDR correction
    anova_suit_df = pd.DataFrame(anova_results_suit)
    valid_p = anova_suit_df['p_value'].dropna()
    if len(valid_p) > 0:
        _, p_adj, _, _ = multipletests(valid_p.values, method='fdr_bh')
        anova_suit_df.loc[valid_p.index, 'p_adj'] = p_adj

    print("\nANOVA Results by Strategy (Trump Suit Effect):")
    display(anova_suit_df.round(4))
else:
    print("⚠️  No suit contracts available for suit analysis")

# %% [markdown]
# ### 2.6 Strategy Performance by Team (B pattern)
#
# One subplot per strategy showing trick distribution by team assignment (0 vs 1).

# %%
# Convert deal_summary to long form with team perspective per strategy
team_performance_rows = []
for _, row in deal_summary.iterrows():
    team0, team1 = row['team0_strategy'], row['team1_strategy']
    deal_id = row['deal_id']

    # Team 0 strategy's perspective
    team_performance_rows.append({
        'strategy': team0,
        'team_assignment': 'team0',
        'team_tricks': row['team0_tricks'],
        'deal_id': deal_id,
    })
    # Team 1 strategy's perspective
    if team0 != team1:  # Avoid double-counting self-play
        team_performance_rows.append({
            'strategy': team1,
            'team_assignment': 'team1',
            'team_tricks': row['team1_tricks'],
            'deal_id': deal_id,
        })

team_perf_df = pd.DataFrame(team_performance_rows)

strategies = sorted(team_perf_df['strategy'].unique())
n_strategies = len(strategies)
n_cols = min(4, n_strategies)
n_rows = (n_strategies + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
if n_strategies == 1:
    axes = np.array([[axes]])
axes = np.atleast_2d(axes)

ttest_results_team = []

for idx, strategy in enumerate(strategies):
    row_idx, col_idx = divmod(idx, n_cols)
    ax = axes[row_idx, col_idx]

    strat_df = team_perf_df[team_perf_df['strategy'] == strategy]
    team0_data = strat_df[strat_df['team_assignment'] == 'team0']['team_tricks'].values
    team1_data = strat_df[strat_df['team_assignment'] == 'team1']['team_tricks'].values

    # T-test for team0 vs team1
    if len(team0_data) > 0 and len(team1_data) > 0:
        t_stat, p_value = ttest_ind(team0_data, team1_data)
        # Cohen's d
        pooled_std = np.sqrt(((len(team0_data) - 1) * np.var(team0_data, ddof=1) +
                              (len(team1_data) - 1) * np.var(team1_data, ddof=1)) /
                             (len(team0_data) + len(team1_data) - 2))
        cohens_d = (np.mean(team0_data) - np.mean(team1_data)) / pooled_std if pooled_std > 0 else 0
    else:
        t_stat, p_value, cohens_d = np.nan, np.nan, np.nan

    ttest_results_team.append({
        'strategy': strategy,
        't_stat': t_stat,
        'p_value': p_value,
        'cohens_d': cohens_d,
        'n_team0': len(team0_data),
        'n_team1': len(team1_data),
    })

    # Violin plot by team assignment
    team_data = [team0_data, team1_data]
    positions = [0, 1]

    parts = ax.violinplot(team_data, positions=positions, showmeans=False, showmedians=False)
    for pc in parts['bodies']:
        pc.set_facecolor('darkorange')
        pc.set_alpha(0.6)
    ax.boxplot(team_data, positions=positions, widths=0.2)

    ax.axhline(5.0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax.set_title(f"{strategy}\n(d={cohens_d:.3f})")
    ax.set_xticks(positions)
    ax.set_xticklabels(['Team 0', 'Team 1'], fontsize=8)
    ax.set_ylabel("Team Tricks")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

# Hide unused axes
for idx in range(n_strategies, n_rows * n_cols):
    row_idx, col_idx = divmod(idx, n_cols)
    axes[row_idx, col_idx].axis('off')

fig.suptitle("Strategy Performance by Team Assignment", fontsize=12)
plt.tight_layout()
plt.show()

# FDR correction
ttest_team_df = pd.DataFrame(ttest_results_team)
valid_p = ttest_team_df['p_value'].dropna()
if len(valid_p) > 0:
    _, p_adj, _, _ = multipletests(valid_p.values, method='fdr_bh')
    ttest_team_df.loc[valid_p.index, 'p_adj'] = p_adj

print("\nT-Test Results by Strategy (Team Assignment Effect):")
display(ttest_team_df.round(4))

# %% [markdown]
# ### 2.7 Strategy Performance by Seat (B pattern)
#
# One subplot per strategy showing trick distribution by seat position (0-3).

# %%
strategies = sorted(analysis_df['seat_strategy'].unique())
n_strategies = len(strategies)
n_cols = min(4, n_strategies)
n_rows = (n_strategies + n_cols - 1) // n_cols

fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 4 * n_rows))
if n_strategies == 1:
    axes = np.array([[axes]])
axes = np.atleast_2d(axes)

anova_results_seat = []

for idx, strategy in enumerate(strategies):
    row_idx, col_idx = divmod(idx, n_cols)
    ax = axes[row_idx, col_idx]

    strat_df = analysis_df[analysis_df['seat_strategy'] == strategy]

    # ANOVA across seats
    seat_groups = [
        strat_df[strat_df['seat'] == s]['tricks_won'].values
        for s in SEATS
        if len(strat_df[strat_df['seat'] == s]) > 0
    ]

    if len(seat_groups) >= 2 and all(len(g) > 0 for g in seat_groups):
        f_stat, p_value = f_oneway(*seat_groups)
        overall_mean = strat_df['tricks_won'].mean()
        ss_between = sum(len(g) * (np.mean(g) - overall_mean)**2 for g in seat_groups)
        ss_total = ((strat_df['tricks_won'] - overall_mean)**2).sum()
        eta_sq = ss_between / ss_total if ss_total > 0 else 0
    else:
        f_stat, p_value, eta_sq = np.nan, np.nan, np.nan

    anova_results_seat.append({
        'strategy': strategy,
        'f_stat': f_stat,
        'p_value': p_value,
        'eta_sq': eta_sq,
        'n': len(strat_df),
    })

    # Violin plot by seat
    seat_data = [strat_df[strat_df['seat'] == s]['tricks_won'].values for s in SEATS]
    positions = range(len(SEATS))

    parts = ax.violinplot(seat_data, positions=positions, showmeans=False, showmedians=False)
    for pc in parts['bodies']:
        pc.set_facecolor('purple')
        pc.set_alpha(0.6)
    ax.boxplot(seat_data, positions=positions, widths=0.2)

    ax.axhline(5.0, color='red', linestyle='--', linewidth=1, alpha=0.7)
    ax.set_title(f"{strategy}\n(n={len(strat_df)}, η²={eta_sq:.3f})")
    ax.set_xticks(positions)
    ax.set_xticklabels([f"Seat {s}" for s in SEATS], fontsize=8)
    ax.set_ylabel("Tricks Won")
    ax.set_ylim(-0.5, 10.5)
    ax.grid(axis='y', alpha=0.3)

# Hide unused axes
for idx in range(n_strategies, n_rows * n_cols):
    row_idx, col_idx = divmod(idx, n_cols)
    axes[row_idx, col_idx].axis('off')

fig.suptitle("Strategy Performance by Seat Position", fontsize=12)
plt.tight_layout()
plt.show()

# FDR correction
anova_seat_df = pd.DataFrame(anova_results_seat)
valid_p = anova_seat_df['p_value'].dropna()
if len(valid_p) > 0:
    _, p_adj, _, _ = multipletests(valid_p.values, method='fdr_bh')
    anova_seat_df.loc[valid_p.index, 'p_adj'] = p_adj

print("\nANOVA Results by Strategy (Seat Position Effect):")
display(anova_seat_df.round(4))

# %% [markdown]
# ### 2.8 Rolling Mean Delta
#
# Rolling mean of per-deal Δ (team0 - team1) for each matchup, ordered by deal_id.
# Used to detect drift over time.

# %%
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
plt.title(f"Rolling Mean Delta (Team0 - Team1), window={ROLLING_WINDOW}")
plt.ylabel("Rolling Delta (tricks)")
plt.xlabel("Deal ID")
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8)
plt.tight_layout()
plt.show()

print("Caption: Rolling mean of per-deal Δ (team0 - team1) for each matchup, ordered by deal_id.")
print("         Stable lines near 0 indicate no drift; divergence may indicate seed/config issues.")

# %% [markdown]
# ---
# ## Section 3: Feature-Outcome Correlations
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
# ## Section 4: Predictive Modeling & Feature Importance
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
# ## Section 5: Summary
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
print("  4. Review per-strategy bias results (Section 2.4-2.7) for significant effects")
