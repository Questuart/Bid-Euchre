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
# - **Section 0: Configuration** - Mode, strategies, matchups, data source
# - **Section 1: Data Loading** - Feature + outcome data validation
# - **Section 2: Strategy Comparison**
#   - 2.1 Win Rate Evaluation
#   - 2.2 Trick Distribution by Strategy
#   - 2.3 Matchup Summary Table
#   - 2.4 Performance by Contract Type (Self-Play)
#   - 2.5 Performance by Suit (Self-Play)
#   - 2.6 Performance by Team (Self-Play)
#   - 2.7 Performance by Seat (Self-Play)
#   - 2.8 Rolling Mean Delta
#   - 2.9 Greedy vs Glutton Deep Dive
# - **Section 3: Feature-Outcome Correlations** (by matchup type)
# - **Section 4: Predictive Modeling & Feature Importance** (by matchup type)
# - **Section 5: Summary** - Health scorecard

# %% [markdown]
# ---
# ## Section 0: Configuration

# %% tags=["parameters"]
# Configuration (papermill parameters)
MODE = "QUICK"  # "SMOKE" (~30 deals), "QUICK" (~2k deals), or "FULL" (~50k deals)
SEED = 42

# --- Data Source Mode ---
DEMO_MODE = True  # If True, generates synthetic data; if False, loads from RUN_DIR

# If DEMO_MODE=False, set this path:
RUN_DIR = "../../data/runs/YOUR_RUN_ID"  # Will load outcomes from RUN_DIR/logs/

# Game parameters
CONTRACT_TYPES = ['suit', 'high', 'low']
TRUMPS_FOR_SUIT_CONTRACTS = ['C', 'D', 'H', 'S']
SEATS = [0, 1, 2, 3]

# Strategy configuration (head-to-head matchups)
# Only greedy and glutton are used in the analysis (KEY_MATCHUP_TYPES, SMART_STRATEGIES).
# Using all 5 strategies generates 25 matchups causing OOM in CI.
STRATEGIES = [
    {"name": "greedy", "class_name": "GreedyStrategy"},
    {"name": "glutton", "class_name": "GluttonStrategy"},
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
print(f"Demo mode: {DEMO_MODE}")

# %% [markdown]
# ### Imports

# %%
import itertools
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import display
from scipy.stats import f_oneway, friedmanchisquare, pearsonr, ttest_ind

# Optional: seaborn for enhanced visualizations
try:
    import seaborn as sns
    sns.set_theme(style="whitegrid")
    HAS_SEABORN = True
except ImportError:
    print("seaborn not available, using matplotlib defaults")
    HAS_SEABORN = False
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.multitest import multipletests

warnings.filterwarnings('ignore')

# Project imports
from bid_euchre.diagnostics.notebook_data import (
    load_features_and_outcomes_from_run_dir,
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


def is_paired_data(df: pd.DataFrame, group_col: str, value_col: str = 'deal_id') -> bool:
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
# ============================================================================
# Data Loading Helper for Production Mode
# ============================================================================

# %%
# Load feature + outcome data
if DEMO_MODE:
    print(f"DEMO_MODE: Generating synthetic data (mode={MODE}, seed={SEED})...")
    data_df = load_or_generate_features(
        mode=MODE,
        seed=SEED,
        contracts=CONTRACT_TYPES,
        trumps=TRUMPS_FOR_SUIT_CONTRACTS,
        seats=SEATS,
        strategies=STRATEGIES,
        matchups=MATCHUPS,
    )
else:
    print(f"Loading data from RUN_DIR: {RUN_DIR}")
    data_df = load_features_and_outcomes_from_run_dir(RUN_DIR)

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

# Create head-to-head only filtered DataFrames for Sections 2.4-2.7
# These exclude self-play matchups (team0_strategy == team1_strategy)
analysis_df_h2h = analysis_df[
    analysis_df['team0_strategy'] != analysis_df['team1_strategy']
].copy()

deal_summary_h2h = deal_summary[
    deal_summary['team0_strategy'] != deal_summary['team1_strategy']
].copy()

print(f"Deal summaries: {len(deal_summary)}")
print(f"Analysis rows with seat_strategy: {len(analysis_df)}")
print(f"Unique seat strategies: {sorted(analysis_df['seat_strategy'].unique())}")

# Build matchup results for plotting
matchup_results = {}
summary_rows = []
for (team0, team1), group in deal_summary.groupby(['team0_strategy', 'team1_strategy']):
    # Weighted win rate: full wins (>=6) + 0.5 × ties (=5)
    full_wins = (group['team0_tricks'] > 5).sum()
    ties = (group['team0_tricks'] == 5).sum()
    win_rate = (full_wins + 0.5 * ties) / len(group)
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

# Mean tricks heatmap (using fmt=".1f" for integer-like display)
fig = plot_win_rate_heatmap(matchup_results, metric="mean_tricks_team0", title="Mean Tricks (Team 0) Heatmap", fmt=".1f")
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
#
# **Strategy-Normalized Trick Delta:**
#
# For each strategy, delta is computed from that strategy's perspective:
# - When assigned to Team 0: delta = team0_tricks - team1_tricks
# - When assigned to Team 1: delta = team1_tricks - team0_tricks (sign flipped)
#
# This allows direct comparison of how each strategy performs across all its matchups.
# Positive values indicate the strategy gained tricks; negative indicates lost tricks.

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
    ax.grid(axis='y', alpha=0.3)

# Hide unused axes
for idx in range(n_strategies, n_rows * n_cols):
    row_idx, col_idx = divmod(idx, n_cols)
    axes[row_idx, col_idx].axis('off')

# Apply dynamic y-limits based on data percentiles (avoids outlier flattening)
all_deltas = strategy_delta_df['normalized_delta']
if len(all_deltas) == 0 or all_deltas.std() == 0:
    y_limit = 1.0  # fallback
else:
    p1, p99 = np.percentile(all_deltas, [1, 99])
    y_limit = max(abs(p1), abs(p99)) * 1.1

for ax_row in axes:
    for ax in np.atleast_1d(ax_row):
        if ax.axison:  # Only set for visible axes
            ax.set_ylim(-y_limit, y_limit)

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
# **Head-to-head matchups only** (excludes self-play).

# %%
strategies = sorted(analysis_df_h2h['seat_strategy'].unique())
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

    strat_df = analysis_df_h2h[analysis_df_h2h['seat_strategy'] == strategy]

    # Statistical test across contract types (paired or independent)
    contract_groups = [
        strat_df[strat_df['contract_type'] == ct]['tricks_won'].values
        for ct in CONTRACT_TYPES
        if len(strat_df[strat_df['contract_type'] == ct]) > 0
    ]

    test_name = "ANOVA"
    if len(contract_groups) >= 2 and all(len(g) > 0 for g in contract_groups):
        # Check if paired (same deal_ids across contract types)
        paired = is_paired_data(strat_df, 'contract_type')
        if paired and len(contract_groups) >= 3:
            min_len = min(len(g) for g in contract_groups)
            aligned = [g[:min_len] for g in contract_groups]
            stat, p_value = friedmanchisquare(*aligned)
            test_name = "Friedman"
        else:
            stat, p_value = f_oneway(*contract_groups)
        # Eta-squared (approximation for both tests)
        overall_mean = strat_df['tricks_won'].mean()
        ss_between = sum(len(g) * (np.mean(g) - overall_mean)**2 for g in contract_groups)
        ss_total = ((strat_df['tricks_won'] - overall_mean)**2).sum()
        eta_sq = ss_between / ss_total if ss_total > 0 else 0
    else:
        stat, p_value, eta_sq = np.nan, np.nan, np.nan

    anova_results_contract.append({
        'strategy': strategy,
        'test': test_name,
        'stat': stat if 'stat' in dir() else np.nan,
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

fig.suptitle("Strategy Performance by Contract Type (Head-to-Head Matchups)", fontsize=12)
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
# **Head-to-head matchups only** (excludes self-play).

# %%
suit_only = analysis_df_h2h[analysis_df_h2h['contract_type'] == 'suit']

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

        # Statistical test across trump suits (paired or independent)
        suit_groups = [
            strat_df[strat_df['trump'] == t]['tricks_won'].values
            for t in TRUMPS_FOR_SUIT_CONTRACTS
            if len(strat_df[strat_df['trump'] == t]) > 0
        ]

        test_name = "ANOVA"
        if len(suit_groups) >= 2 and all(len(g) > 0 for g in suit_groups):
            # Check if paired (same deal_ids across trump suits)
            paired = is_paired_data(strat_df, 'trump')
            if paired and len(suit_groups) >= 3:
                min_len = min(len(g) for g in suit_groups)
                aligned = [g[:min_len] for g in suit_groups]
                stat, p_value = friedmanchisquare(*aligned)
                test_name = "Friedman"
            else:
                stat, p_value = f_oneway(*suit_groups)
            overall_mean = strat_df['tricks_won'].mean()
            ss_between = sum(len(g) * (np.mean(g) - overall_mean)**2 for g in suit_groups)
            ss_total = ((strat_df['tricks_won'] - overall_mean)**2).sum()
            eta_sq = ss_between / ss_total if ss_total > 0 else 0
        else:
            stat, p_value, eta_sq = np.nan, np.nan, np.nan

        anova_results_suit.append({
            'strategy': strategy,
            'test': test_name,
            'stat': stat if 'stat' in dir() else np.nan,
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

    fig.suptitle("Strategy Performance by Trump Suit (Head-to-Head Matchups)", fontsize=12)
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
# **Head-to-head matchups only** (excludes self-play).

# %%
# Convert deal_summary_h2h to long form with team perspective per strategy
# Head-to-head only: both perspectives are valid (no self-play double-counting issue)
team_performance_rows = []
for _, row in deal_summary_h2h.iterrows():
    team0, team1 = row['team0_strategy'], row['team1_strategy']
    deal_id = row['deal_id']

    # Team 0 strategy's perspective
    team_performance_rows.append({
        'strategy': team0,
        'team_assignment': 'team0',
        'team_tricks': row['team0_tricks'],
        'deal_id': deal_id,
    })
    # Team 1 strategy's perspective (always included in h2h since team0 != team1)
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

fig.suptitle("Strategy Performance by Team Assignment (Head-to-Head Matchups)", fontsize=12)
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
# **Head-to-head matchups only** (excludes self-play).

# %%
strategies = sorted(analysis_df_h2h['seat_strategy'].unique())
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

    strat_df = analysis_df_h2h[analysis_df_h2h['seat_strategy'] == strategy]

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

fig.suptitle("Strategy Performance by Seat Position (Head-to-Head Matchups)", fontsize=12)
plt.tight_layout()
plt.show()

# FDR correction
anova_seat_df = pd.DataFrame(anova_results_seat)
valid_p = anova_seat_df['p_value'].dropna()
if len(valid_p) > 0:
    _, p_adj, _, _ = multipletests(valid_p.values, method='fdr_bh')
    anova_seat_df.loc[valid_p.index, 'p_adj'] = p_adj

print("\nANOVA Results by Strategy (Seat Position Effect):")
print("\n" + "=" * 70)
print("WARNING: SEAT-LEVEL ANALYSIS CAVEAT")
print("=" * 70)
print("Due to team-level logging, seats within the same team share identical tricks_won.")
print("  - Seats 0 & 2 (Team 0): show identical team0_tricks")
print("  - Seats 1 & 3 (Team 1): show identical team1_tricks")
print("Apparent seat effects reflect team assignment, not individual seat performance.")
print("=" * 70 + "\n")
display(anova_seat_df.round(4))

# %% [markdown]
# ### 2.8 Rolling Mean Delta
#
# Rolling mean of per-deal Δ (team0 - team1) for each matchup, ordered by deal_id.
# Used to detect drift over time.

# %%
ROLLING_WINDOW = 50

# Define smart strategies for highlighting
SMART_STRATEGIES = {'greedy', 'glutton'}

rolling_rows = []
for (team0, team1), group in deal_summary.groupby(['team0_strategy', 'team1_strategy']):
    group_sorted = group.sort_values('deal_id')
    rolling = group_sorted['delta_tricks'].rolling(ROLLING_WINDOW, min_periods=10).mean()
    # Determine if this is a smart strategy matchup
    is_smart = team0 in SMART_STRATEGIES and team1 in SMART_STRATEGIES
    rolling_rows.append(pd.DataFrame({
        'deal_id': group_sorted['deal_id'],
        'rolling_delta': rolling,
        'matchup': f"{team0}_vs_{team1}",
        'is_smart_matchup': is_smart,
    }))

rolling_df = pd.concat(rolling_rows, ignore_index=True)
n_deals_total = len(deal_summary)

# Create plot with highlighted smart matchups
plt.figure(figsize=(12, 6))

# Plot non-smart matchups in gray (background)
non_smart_df = rolling_df[~rolling_df['is_smart_matchup']]
if len(non_smart_df) > 0:
    for matchup in non_smart_df['matchup'].unique():
        matchup_data = non_smart_df[non_smart_df['matchup'] == matchup]
        plt.plot(matchup_data['deal_id'], matchup_data['rolling_delta'],
                 color='gray', alpha=0.3, linewidth=1, label=None)

# Plot smart matchups in distinct colors (foreground)
smart_df = rolling_df[rolling_df['is_smart_matchup']]
smart_colors = {'greedy_vs_greedy': 'blue', 'glutton_vs_glutton': 'orange',
                'greedy_vs_glutton': 'green', 'glutton_vs_greedy': 'red'}
for matchup in smart_df['matchup'].unique():
    matchup_data = smart_df[smart_df['matchup'] == matchup]
    color = smart_colors.get(matchup, 'purple')
    plt.plot(matchup_data['deal_id'], matchup_data['rolling_delta'],
             color=color, alpha=0.9, linewidth=2, label=matchup)

plt.axhline(0, color='black', linewidth=0.8)
plt.title(f"Rolling Mean Delta (n={n_deals_total} deals, window={ROLLING_WINDOW})")
plt.ylabel("Rolling Delta (tricks)")
plt.xlabel("Deal ID")
plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=8,
           title="Smart Matchups\n(others in gray)")
plt.tight_layout()
plt.show()

print("Caption: Rolling mean of per-deal Δ (team0 - team1) for each matchup, ordered by deal_id.")
print("         Smart strategy matchups (greedy/glutton) highlighted; others in gray.")
print("         Stable lines near 0 indicate no drift; divergence may indicate seed/config issues.")

# %% [markdown]
# ### 2.9 Greedy vs Glutton Deep Dive
#
# Detailed analysis of smart strategy matchups including:
# - **greedy vs greedy** (self-play)
# - **glutton vs glutton** (self-play)
# - **greedy vs glutton** (head-to-head, both directions)

# %%
# ============================================================================
# Section 2.9: Greedy vs Glutton Deep Dive
# ============================================================================

print("\n" + "=" * 70)
print("SECTION 2.9: GREEDY VS GLUTTON DEEP DIVE")
print("=" * 70)

# Filter deal_summary for smart strategy matchups
SMART_STRATEGIES = ['greedy', 'glutton']
smart_matchups = deal_summary[
    (deal_summary['team0_strategy'].isin(SMART_STRATEGIES)) &
    (deal_summary['team1_strategy'].isin(SMART_STRATEGIES))
].copy()

# Create matchup type column
def classify_matchup(row):
    t0, t1 = row['team0_strategy'], row['team1_strategy']
    if t0 == t1 == 'greedy':
        return 'greedy_self_play'
    elif t0 == t1 == 'glutton':
        return 'glutton_self_play'
    else:
        return 'greedy_vs_glutton'

smart_matchups['matchup_type'] = smart_matchups.apply(classify_matchup, axis=1)

print(f"\nSmart matchup deals: {len(smart_matchups)}")
print("\nMatchup type distribution:")
print(smart_matchups['matchup_type'].value_counts())

# %%
# Panel 1: Performance summary table
print("\n--- Performance Summary by Matchup Type ---")

summary_stats = []
for matchup_type in ['greedy_self_play', 'glutton_self_play', 'greedy_vs_glutton']:
    subset = smart_matchups[smart_matchups['matchup_type'] == matchup_type]
    if len(subset) == 0:
        continue

    # For head-to-head, compute from greedy's perspective
    if matchup_type == 'greedy_vs_glutton':
        greedy_as_t0 = subset[subset['team0_strategy'] == 'greedy']
        greedy_as_t1 = subset[subset['team0_strategy'] == 'glutton']

        # Normalize delta from greedy's perspective
        greedy_deltas = list(greedy_as_t0['delta_tricks']) + list(-greedy_as_t1['delta_tricks'])
        mean_delta = np.mean(greedy_deltas) if greedy_deltas else 0
        std_delta = np.std(greedy_deltas) if greedy_deltas else 0
        n = len(greedy_deltas)

        # Win rate from greedy's perspective (weighted: full wins + 0.5 × ties)
        greedy_full_wins = (greedy_as_t0['team0_tricks'] > 5).sum() + (greedy_as_t1['team1_tricks'] > 5).sum()
        greedy_ties = (greedy_as_t0['team0_tricks'] == 5).sum() + (greedy_as_t1['team1_tricks'] == 5).sum()
        win_rate = (greedy_full_wins + 0.5 * greedy_ties) / n if n > 0 else 0
    else:
        # Self-play: delta should be ~0, win rate ~0.5
        mean_delta = subset['delta_tricks'].mean()
        std_delta = subset['delta_tricks'].std()
        n = len(subset)
        # Weighted win rate: full wins + 0.5 × ties
        full_wins = (subset['team0_tricks'] > 5).sum()
        ties = (subset['team0_tricks'] == 5).sum()
        win_rate = (full_wins + 0.5 * ties) / n if n > 0 else 0

    # Bootstrap 95% CI for mean delta
    ci_lower, ci_upper = np.nan, np.nan
    if n >= 10:
        bootstrap_means = []
        rng = np.random.default_rng(SEED)
        for _ in range(1000):
            if matchup_type == 'greedy_vs_glutton':
                sample = rng.choice(greedy_deltas, size=n, replace=True)
            else:
                sample = rng.choice(subset['delta_tricks'].values, size=n, replace=True)
            bootstrap_means.append(np.mean(sample))
        ci_lower, ci_upper = np.percentile(bootstrap_means, [2.5, 97.5])

    summary_stats.append({
        'matchup_type': matchup_type,
        'n_deals': n,
        'mean_delta': mean_delta,
        'std_delta': std_delta,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'win_rate': win_rate,
    })

summary_stats_df = pd.DataFrame(summary_stats)
display(summary_stats_df.round(3))

# %%
# Panel 2: Win rate bar chart by matchup type
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# Win rate comparison
ax1 = axes[0]
colors = ['steelblue', 'darkorange', 'green']
bars = ax1.bar(summary_stats_df['matchup_type'], summary_stats_df['win_rate'], color=colors, alpha=0.7)
ax1.axhline(0.5, color='red', linestyle='--', linewidth=1, label='Fair (0.5)')
ax1.set_ylabel("Win Rate")
ax1.set_title("Win Rate by Matchup Type\n(greedy_vs_glutton: from greedy's perspective)")
ax1.set_ylim(0, 1)
ax1.tick_params(axis='x', rotation=45)
for bar, rate in zip(bars, summary_stats_df['win_rate']):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
             f'{rate:.3f}', ha='center', fontsize=9)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# Mean delta comparison
ax2 = axes[1]
bars = ax2.bar(summary_stats_df['matchup_type'], summary_stats_df['mean_delta'], color=colors, alpha=0.7)
ax2.errorbar(range(len(summary_stats_df)), summary_stats_df['mean_delta'],
             yerr=[(summary_stats_df['mean_delta'] - summary_stats_df['ci_lower']).values,
                   (summary_stats_df['ci_upper'] - summary_stats_df['mean_delta']).values],
             fmt='none', color='black', capsize=5)
ax2.axhline(0, color='red', linestyle='--', linewidth=1)
ax2.set_ylabel("Mean Delta (tricks)")
ax2.set_title("Mean Delta with 95% CI\n(greedy_vs_glutton: from greedy's perspective)")
ax2.tick_params(axis='x', rotation=45)
ax2.grid(axis='y', alpha=0.3)

# Sample size
ax3 = axes[2]
bars = ax3.bar(summary_stats_df['matchup_type'], summary_stats_df['n_deals'], color=colors, alpha=0.7)
ax3.set_ylabel("Number of Deals")
ax3.set_title("Sample Size by Matchup Type")
ax3.tick_params(axis='x', rotation=45)
for bar, n in zip(bars, summary_stats_df['n_deals']):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
             f'{n}', ha='center', fontsize=9)
ax3.grid(axis='y', alpha=0.3)

plt.tight_layout()
plt.show()

# %%
# Panel 3: Delta distribution (violin + box) for each matchup - DUAL PERSPECTIVE
# Row 1: Greedy perspective, Row 2: Glutton perspective
fig, axes = plt.subplots(2, 3, figsize=(15, 10))

matchup_types = ['greedy_self_play', 'glutton_self_play', 'greedy_vs_glutton']
perspective_labels = ['Greedy Perspective', 'Glutton Perspective']

# Helper function to compute deltas from a given perspective
def compute_perspective_deltas(subset, mtype, perspective):
    """Compute normalized deltas from the given perspective."""
    if mtype == 'greedy_vs_glutton':
        if perspective == 'greedy':
            # Greedy perspective: positive = greedy advantage
            greedy_as_t0 = subset[subset['team0_strategy'] == 'greedy']['delta_tricks']
            greedy_as_t1 = -subset[subset['team0_strategy'] == 'glutton']['delta_tricks']
            return pd.concat([greedy_as_t0, greedy_as_t1]).values
        else:  # glutton perspective
            # Glutton perspective: positive = glutton advantage (flip sign)
            glutton_as_t0 = subset[subset['team0_strategy'] == 'glutton']['delta_tricks']
            glutton_as_t1 = -subset[subset['team0_strategy'] == 'greedy']['delta_tricks']
            return pd.concat([glutton_as_t0, glutton_as_t1]).values
    else:
        # Self-play: symmetric, same for both perspectives
        return subset['delta_tricks'].values

# Collect all deltas for dynamic y-limit
all_panel3_deltas = []
for mtype in matchup_types:
    subset = smart_matchups[smart_matchups['matchup_type'] == mtype]
    for perspective in ['greedy', 'glutton']:
        data = compute_perspective_deltas(subset, mtype, perspective)
        if len(data) > 0:
            all_panel3_deltas.extend(data)

# Compute dynamic y-limit
if len(all_panel3_deltas) == 0 or np.std(all_panel3_deltas) == 0:
    y_limit_p3 = 10.0
else:
    p1, p99 = np.percentile(all_panel3_deltas, [1, 99])
    y_limit_p3 = max(abs(p1), abs(p99)) * 1.1

for row_idx, perspective in enumerate(['greedy', 'glutton']):
    for col_idx, mtype in enumerate(matchup_types):
        ax = axes[row_idx, col_idx]
        subset = smart_matchups[smart_matchups['matchup_type'] == mtype]
        data = compute_perspective_deltas(subset, mtype, perspective)

        if len(data) > 0:
            color = 'steelblue' if perspective == 'greedy' else 'darkorange'
            parts = ax.violinplot([data], positions=[0], showmeans=False, showmedians=False)
            for pc in parts['bodies']:
                pc.set_facecolor(color)
                pc.set_alpha(0.6)
            ax.boxplot([data], positions=[0], widths=0.2)
            ax.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.7)

            mean_val = np.mean(data)
            ax.axhline(mean_val, color='green', linestyle='-', linewidth=1, alpha=0.7)
            ax.text(0.4, mean_val, f'μ={mean_val:.2f}', fontsize=9, va='center')

        # Titles: top row only shows matchup type, left column shows perspective
        if row_idx == 0:
            mtype_title = mtype.replace('_', ' ').title()
            ax.set_title(f"{mtype_title}\n(n={len(data)})")
        else:
            ax.set_title(f"(n={len(data)})")

        if col_idx == 0:
            ax.set_ylabel(f"{perspective_labels[row_idx]}\nDelta (tricks)")
        else:
            ax.set_ylabel("")

        ax.set_xticks([])
        ax.set_ylim(-y_limit_p3, y_limit_p3)
        ax.grid(axis='y', alpha=0.3)

plt.suptitle("Delta Distribution by Matchup Type (Dual Perspective)", fontsize=12, y=1.02)
plt.tight_layout()
plt.show()

# %%
# Panel 4: Performance by contract type for greedy vs glutton - DUAL PERSPECTIVE
# Row 1: Greedy perspective, Row 2: Glutton perspective
h2h_only = smart_matchups[smart_matchups['matchup_type'] == 'greedy_vs_glutton']

if len(h2h_only) > 0:
    fig, axes = plt.subplots(2, len(CONTRACT_TYPES), figsize=(5 * len(CONTRACT_TYPES), 10))
    if len(CONTRACT_TYPES) == 1:
        axes = axes.reshape(2, 1)

    # Helper to compute perspective deltas by contract type
    def compute_ct_perspective_deltas(ct_data, perspective):
        if perspective == 'greedy':
            greedy_t0 = ct_data[ct_data['team0_strategy'] == 'greedy']['delta_tricks']
            greedy_t1 = -ct_data[ct_data['team0_strategy'] == 'glutton']['delta_tricks']
            return pd.concat([greedy_t0, greedy_t1]).values if len(greedy_t0) + len(greedy_t1) > 0 else np.array([])
        else:  # glutton perspective
            glutton_t0 = ct_data[ct_data['team0_strategy'] == 'glutton']['delta_tricks']
            glutton_t1 = -ct_data[ct_data['team0_strategy'] == 'greedy']['delta_tricks']
            return pd.concat([glutton_t0, glutton_t1]).values if len(glutton_t0) + len(glutton_t1) > 0 else np.array([])

    # Collect all deltas for dynamic y-limit
    all_panel4_deltas = []
    for ct in CONTRACT_TYPES:
        ct_data = h2h_only[h2h_only['contract_type'] == ct]
        for perspective in ['greedy', 'glutton']:
            data = compute_ct_perspective_deltas(ct_data, perspective)
            if len(data) > 0:
                all_panel4_deltas.extend(data)

    # Compute dynamic y-limit
    if len(all_panel4_deltas) == 0 or np.std(all_panel4_deltas) == 0:
        y_limit_p4 = 10.0
    else:
        p1, p99 = np.percentile(all_panel4_deltas, [1, 99])
        y_limit_p4 = max(abs(p1), abs(p99)) * 1.1

    perspective_labels = ['Greedy Perspective', 'Glutton Perspective']
    perspective_colors = {'greedy': 'steelblue', 'glutton': 'darkorange'}

    from scipy.stats import ttest_1samp

    for row_idx, perspective in enumerate(['greedy', 'glutton']):
        for col_idx, ct in enumerate(CONTRACT_TYPES):
            ax = axes[row_idx, col_idx]
            ct_data = h2h_only[h2h_only['contract_type'] == ct]
            deltas = compute_ct_perspective_deltas(ct_data, perspective)

            if len(deltas) > 0:
                parts = ax.violinplot([deltas], positions=[0], showmeans=False, showmedians=False)
                for pc in parts['bodies']:
                    pc.set_facecolor(perspective_colors[perspective])
                    pc.set_alpha(0.6)
                ax.boxplot([deltas], positions=[0], widths=0.2)
                ax.axhline(0, color='red', linestyle='--', linewidth=1, alpha=0.7)

                mean_val = np.mean(deltas)
                ax.text(0.4, mean_val, f'μ={mean_val:.2f}', fontsize=9, va='center')

                # T-test against 0
                if len(deltas) > 1:
                    t_stat, p_val = ttest_1samp(deltas, 0)
                    status = "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
                    title_suffix = f"p={p_val:.3f}{status}"
                else:
                    title_suffix = ""

                if row_idx == 0:
                    ax.set_title(f"{ct.upper()}\n(n={len(deltas)}, {title_suffix})")
                else:
                    ax.set_title(f"(n={len(deltas)}, {title_suffix})")
            else:
                if row_idx == 0:
                    ax.set_title(f"{ct.upper()}\n(no data)")
                else:
                    ax.set_title("(no data)")

            if col_idx == 0:
                ax.set_ylabel(f"{perspective_labels[row_idx]}\nDelta (tricks)")
            else:
                ax.set_ylabel("")

            ax.set_xticks([])
            ax.set_ylim(-y_limit_p4, y_limit_p4)
            ax.grid(axis='y', alpha=0.3)

    plt.suptitle("Greedy vs Glutton: Delta by Contract Type (Dual Perspective)", fontsize=12, y=1.02)
    plt.tight_layout()
    plt.show()
else:
    print("No greedy vs glutton matchups found")

# %%
# Statistical tests summary
print("\n--- Statistical Summary ---")

# Self-play fairness check (delta should be ~0)
for mtype in ['greedy_self_play', 'glutton_self_play']:
    subset = smart_matchups[smart_matchups['matchup_type'] == mtype]
    if len(subset) > 1:
        from scipy.stats import ttest_1samp
        t_stat, p_val = ttest_1samp(subset['delta_tricks'], 0)
        mean_delta = subset['delta_tricks'].mean()
        status = "PASS" if abs(mean_delta) < 0.5 else "WARN"
        print(f"{mtype}: mean_delta={mean_delta:.3f}, t={t_stat:.3f}, p={p_val:.3f} [{status}]")

# Greedy vs glutton comparison
if len(h2h_only) > 0:
    greedy_t0 = h2h_only[h2h_only['team0_strategy'] == 'greedy']['delta_tricks']
    greedy_t1 = -h2h_only[h2h_only['team0_strategy'] == 'glutton']['delta_tricks']
    all_deltas = pd.concat([greedy_t0, greedy_t1]).values

    if len(all_deltas) > 1:
        from scipy.stats import ttest_1samp
        t_stat, p_val = ttest_1samp(all_deltas, 0)
        mean_delta = np.mean(all_deltas)
        status = "SIGNIFICANT" if p_val < 0.05 else "NOT SIGNIFICANT"
        print(f"greedy_vs_glutton: mean_delta={mean_delta:.3f}, t={t_stat:.3f}, p={p_val:.3f} [{status}]")

        if p_val < 0.05:
            winner = "greedy" if mean_delta > 0 else "glutton"
            print(f"  -> {winner} significantly outperforms the other (p < 0.05)")

print("\n" + "=" * 70)

# %% [markdown]
# ---
# ## Section 3: Feature-Outcome Correlations (3×3 Grid)
#
# Unified analysis of feature-outcome correlations across:
# - **Rows:** Contract types (suit, high, low)
# - **Columns:** Matchup types (greedy_self_play, glutton_self_play, greedy_vs_glutton)
#
# Each cell shows top-10 features by |r| with FDR-adjusted significance markers.

# %%
# ============================================================================
# Section 3: Unified 3×3 Correlation Grid (contract_type × matchup_type)
# ============================================================================

print("\n" + "=" * 70)
print("FEATURE-OUTCOME CORRELATIONS (3×3 GRID)")
print("=" * 70)

# Define key matchups for faceting
data_df_with_matchup = data_df.copy()

def get_matchup_type(strategy_id):
    """Classify strategy_id into matchup type."""
    if '_vs_' in strategy_id:
        parts = strategy_id.split('_vs_')
        t0, t1 = parts[0], parts[1]
        if t0 == t1 == 'greedy':
            return 'greedy_self_play'
        elif t0 == t1 == 'glutton':
            return 'glutton_self_play'
        elif {t0, t1} == {'greedy', 'glutton'}:
            return 'greedy_vs_glutton'
    return 'other'

data_df_with_matchup['matchup_type'] = data_df_with_matchup['strategy_id'].apply(get_matchup_type)

KEY_MATCHUP_TYPES = ['greedy_self_play', 'glutton_self_play', 'greedy_vs_glutton']
smart_data = data_df_with_matchup[data_df_with_matchup['matchup_type'].isin(KEY_MATCHUP_TYPES)]

print(f"\nData filtered to smart matchups: {len(smart_data)} rows")
print(smart_data.groupby(['contract_type', 'matchup_type']).size().unstack(fill_value=0))

feat_cols = [c for c in data_df.columns if c.startswith('feat_')]

# %%
# Compute correlations for each (contract_type, matchup_type) cell
correlation_results_grid = []

for contract_type in CONTRACT_TYPES:
    for matchup_type in KEY_MATCHUP_TYPES:
        cell_df = smart_data[
            (smart_data['contract_type'] == contract_type) &
            (smart_data['matchup_type'] == matchup_type)
        ]

        if len(cell_df) < 50:
            print(f"Skipping ({contract_type}, {matchup_type}): insufficient data ({len(cell_df)} rows)")
            continue

        for feat in feat_cols:
            if cell_df[feat].std() == 0:
                continue

            corr, p_value = pearsonr(cell_df[feat], cell_df['tricks_won'])

            correlation_results_grid.append({
                'contract_type': contract_type,
                'matchup_type': matchup_type,
                'feature': feat,
                'correlation': corr,
                'p_value': p_value,
                'significant': p_value < 0.05,
                'n_samples': len(cell_df),
            })

corr_grid_df = pd.DataFrame(correlation_results_grid)

# Apply FDR correction within each cell (contract_type, matchup_type)
corr_grid_df['p_adj'] = np.nan
corr_grid_df['significant_adj'] = False

for contract_type in CONTRACT_TYPES:
    for matchup_type in KEY_MATCHUP_TYPES:
        mask = (corr_grid_df['contract_type'] == contract_type) & (corr_grid_df['matchup_type'] == matchup_type)
        pvals = corr_grid_df.loc[mask, 'p_value'].values
        if len(pvals) > 0:
            _, p_adj, _, _ = multipletests(pvals, method="fdr_bh")
            corr_grid_df.loc[mask, 'p_adj'] = p_adj
            corr_grid_df.loc[mask, 'significant_adj'] = p_adj < 0.05

print(f"\nTotal correlation results: {len(corr_grid_df)}")
print(f"Significant (FDR < 0.05): {corr_grid_df['significant_adj'].sum()}")

# %%
# Display top correlations for each cell
print("\n" + "=" * 80)
print("TOP CORRELATIONS BY CELL (contract_type × matchup_type)")
print("=" * 80)

for contract_type in CONTRACT_TYPES:
    for matchup_type in KEY_MATCHUP_TYPES:
        cell_corrs = corr_grid_df[
            (corr_grid_df['contract_type'] == contract_type) &
            (corr_grid_df['matchup_type'] == matchup_type)
        ]
        if len(cell_corrs) == 0:
            continue
        top_corrs = cell_corrs.sort_values('correlation', key=abs, ascending=False).head(10).copy()
        top_corrs['feature'] = top_corrs['feature'].str.replace('feat_', '', regex=False)
        n_samples = top_corrs['n_samples'].iloc[0] if len(top_corrs) > 0 else 0
        display_cols = ['feature', 'correlation', 'p_adj', 'significant_adj']
        print(f"\n{contract_type.upper()} × {matchup_type} (n={n_samples})")
        display(top_corrs[display_cols].round(4))

# %%
# 3×3 Correlation Grid Visualization
matchup_colors = {
    'greedy_self_play': 'steelblue',
    'glutton_self_play': 'darkorange',
    'greedy_vs_glutton': 'green',
}

fig, axes = plt.subplots(3, 3, figsize=(18, 15))

for row_idx, contract_type in enumerate(CONTRACT_TYPES):
    for col_idx, matchup_type in enumerate(KEY_MATCHUP_TYPES):
        ax = axes[row_idx, col_idx]

        cell_corrs = corr_grid_df[
            (corr_grid_df['contract_type'] == contract_type) &
            (corr_grid_df['matchup_type'] == matchup_type)
        ]

        if len(cell_corrs) == 0:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', fontsize=12)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
        else:
            top_corrs = cell_corrs.sort_values('correlation', key=abs, ascending=False).head(10)
            features = top_corrs['feature'].values
            corrs = top_corrs['correlation'].values
            sig_adj = top_corrs['significant_adj'].values

            base_color = matchup_colors.get(matchup_type, 'gray')
            colors = ['red' if c < 0 else base_color for c in corrs]

            bars = ax.barh(range(len(features)), corrs, color=colors, alpha=0.7)

            # Add significance markers
            for i, (bar, sig) in enumerate(zip(bars, sig_adj)):
                if sig:
                    x_pos = bar.get_width()
                    offset = 0.02 if x_pos >= 0 else -0.02
                    ax.text(x_pos + offset, i, '*', fontsize=12, va='center',
                            ha='left' if x_pos >= 0 else 'right', fontweight='bold')

            ax.set_yticks(range(len(features)))
            ax.set_yticklabels([f.replace('feat_', '') for f in features], fontsize=7)
            ax.invert_yaxis()
            ax.axvline(0, color='black', linestyle='-', linewidth=0.5)
            ax.grid(axis='x', alpha=0.3)
            ax.set_xlim(-0.6, 0.6)

        # Labels
        if row_idx == 0:
            ax.set_title(matchup_type.replace('_', '\n'), fontsize=10)
        if col_idx == 0:
            ax.set_ylabel(f"{contract_type.upper()}\n\nCorrelation", fontsize=10)
        else:
            ax.set_ylabel('')
        if row_idx == 2:
            ax.set_xlabel('Pearson r')

        n_samples = cell_corrs['n_samples'].iloc[0] if len(cell_corrs) > 0 else 0
        ax.text(0.98, 0.02, f'n={n_samples}', transform=ax.transAxes,
                fontsize=8, ha='right', va='bottom', alpha=0.7)

plt.suptitle("Feature-Outcome Correlations: 3×3 Grid (contract_type × matchup_type)\n* = FDR-adjusted p < 0.05",
             fontsize=12, y=1.02)
plt.tight_layout()
plt.show()

# %%
# Also compute by-contract and by-matchup aggregates for backward compatibility
# These are used in Section 5 summary
# NOTE: Uses smart_data (filtered to KEY_MATCHUP_TYPES) for consistency with 3x3 grid

# By matchup type (aggregated across contracts)
corr_by_matchup_df = corr_grid_df.groupby(['matchup_type', 'feature']).agg({
    'correlation': 'mean',
    'p_value': 'mean',
    'n_samples': 'sum'
}).reset_index()

# By contract type (aggregated across matchups)
correlation_results = []
for contract_type in CONTRACT_TYPES:
    contract_df = smart_data[smart_data['contract_type'] == contract_type]
    for feat in feat_cols:
        if contract_df[feat].std() == 0:
            continue
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
corr_df['p_adj'] = np.nan
corr_df['significant_adj'] = False
for contract_type in CONTRACT_TYPES:
    mask = corr_df['contract_type'] == contract_type
    pvals = corr_df.loc[mask, 'p_value'].values
    if len(pvals) > 0:
        _, p_adj, _, _ = multipletests(pvals, method="fdr_bh")
        corr_df.loc[mask, 'p_adj'] = p_adj
        corr_df.loc[mask, 'significant_adj'] = p_adj < 0.05

print("\n✓ Correlation analysis complete (3×3 grid + aggregates)")

# Legacy variables for Section 5 compatibility
# corr_df and corr_by_matchup_df are now available

# %% [markdown]
# ---
# ## Section 4: Predictive Modeling & Feature Importance (3×3 Grid)
#
# Train Ridge regression models using a 3×3 grid (contract_type × matchup_type).
#
# **Critical improvement:** Uses deal-grouped train/test split to prevent data leakage
# (multiple rows from the same deal cannot appear in both train and test sets).
#
# - **Rows:** Contract types (suit, high, low)
# - **Columns:** Matchup types (greedy_self_play, glutton_self_play, greedy_vs_glutton)

# %%
# ============================================================================
# Section 4: 3×3 Modeling Grid with Deal-Grouped Split
# ============================================================================

print("\n" + "=" * 70)
print("PREDICTIVE MODELING (3×3 GRID WITH DEAL-GROUPED SPLIT)")
print("=" * 70)

feat_cols = [c for c in data_df.columns if c.startswith('feat_')]

matchup_colors = {
    'greedy_self_play': 'steelblue',
    'glutton_self_play': 'darkorange',
    'greedy_vs_glutton': 'green',
}

# Store results for all cells
model_results_grid = []
importance_tables_grid = {}

MIN_DEALS_THRESHOLD = 50  # Minimum unique deals required

for contract_type in CONTRACT_TYPES:
    for matchup_type in KEY_MATCHUP_TYPES:
        cell_df = smart_data[
            (smart_data['contract_type'] == contract_type) &
            (smart_data['matchup_type'] == matchup_type)
        ].copy()

        n_deals = cell_df['deal_id'].nunique() if 'deal_id' in cell_df.columns else len(cell_df)

        if n_deals < MIN_DEALS_THRESHOLD:
            print(f"Skipping ({contract_type}, {matchup_type}): insufficient deals ({n_deals} < {MIN_DEALS_THRESHOLD})")
            model_results_grid.append({
                'contract_type': contract_type,
                'matchup_type': matchup_type,
                'r2': np.nan,
                'mae': np.nan,
                'n_train': 0,
                'n_test': 0,
                'n_deals_train': 0,
                'n_deals_test': 0,
                'status': 'insufficient_data',
            })
            continue

        X = cell_df[feat_cols].select_dtypes(include=[np.number])
        y = cell_df['tricks_won']
        groups = cell_df['deal_id'] if 'deal_id' in cell_df.columns else pd.Series(range(len(cell_df)))

        # Deal-grouped split to prevent data leakage
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
        train_idx, test_idx = next(gss.split(X, y, groups=groups))

        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        n_deals_train = groups.iloc[train_idx].nunique()
        n_deals_test = groups.iloc[test_idx].nunique()

        # Fit model
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        ridge = Ridge(alpha=1.0, random_state=SEED)
        ridge.fit(X_train_scaled, y_train)

        y_pred = ridge.predict(X_test_scaled)
        r2 = r2_score(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)

        model_results_grid.append({
            'contract_type': contract_type,
            'matchup_type': matchup_type,
            'r2': r2,
            'mae': mae,
            'n_train': len(X_train),
            'n_test': len(X_test),
            'n_deals_train': n_deals_train,
            'n_deals_test': n_deals_test,
            'status': 'ok',
        })

        # Permutation importance on test set
        perm = permutation_importance(
            ridge, X_test_scaled, y_test, n_repeats=5, random_state=SEED
        )
        perm_df = pd.DataFrame({
            'feature': X.columns,
            'perm_importance': perm.importances_mean,
            'perm_std': perm.importances_std,
        }).sort_values('perm_importance', ascending=False)
        perm_df['feature'] = perm_df['feature'].str.replace('feat_', '', regex=False)
        importance_tables_grid[(contract_type, matchup_type)] = perm_df

model_results_grid_df = pd.DataFrame(model_results_grid)
print("\nModel Summary (3×3 Grid):")
display(model_results_grid_df[model_results_grid_df['status'] == 'ok'].round(4))

# %%
# 3×3 R² Heatmap
r2_matrix = model_results_grid_df.pivot(
    index='contract_type', columns='matchup_type', values='r2'
)
# Reorder to match CONTRACT_TYPES and KEY_MATCHUP_TYPES order
r2_matrix = r2_matrix.reindex(index=CONTRACT_TYPES, columns=KEY_MATCHUP_TYPES)

fig, ax = plt.subplots(figsize=(10, 6))
mask = r2_matrix.isna()
sns.heatmap(
    r2_matrix, annot=True, fmt='.3f', cmap='RdYlGn', center=0,
    mask=mask, ax=ax, vmin=-0.1, vmax=0.5,
    cbar_kws={'label': 'R²'}
)
ax.set_title("R² by Contract Type × Matchup Type\n(Deal-Grouped Split)", fontsize=12)
ax.set_xlabel("Matchup Type")
ax.set_ylabel("Contract Type")

# Add "insufficient data" annotations for NaN cells
for i, ct in enumerate(CONTRACT_TYPES):
    for j, mt in enumerate(KEY_MATCHUP_TYPES):
        if pd.isna(r2_matrix.loc[ct, mt]):
            ax.text(j + 0.5, i + 0.5, 'N/A', ha='center', va='center',
                    fontsize=10, color='gray')

plt.tight_layout()
plt.show()

# %%
# Display importance summaries per cell
print("\n" + "=" * 70)
print("TOP FEATURE IMPORTANCE BY CELL")
print("=" * 70)

for contract_type in CONTRACT_TYPES:
    for matchup_type in KEY_MATCHUP_TYPES:
        key = (contract_type, matchup_type)
        if key not in importance_tables_grid:
            continue
        perm_df = importance_tables_grid[key]
        cell_result = model_results_grid_df[
            (model_results_grid_df['contract_type'] == contract_type) &
            (model_results_grid_df['matchup_type'] == matchup_type)
        ].iloc[0]
        r2 = cell_result['r2']
        n_test = cell_result['n_test']
        print(f"\n{contract_type.upper()} × {matchup_type} (R²={r2:.3f}, n_test={n_test})")
        display(perm_df.head(10).round(4))

# %%
# Per-row importance comparison (one row per contract type, 3 matchup columns)
for contract_type in CONTRACT_TYPES:
    available_matchups = [
        mt for mt in KEY_MATCHUP_TYPES
        if (contract_type, mt) in importance_tables_grid
    ]

    if len(available_matchups) == 0:
        print(f"\n{contract_type.upper()}: No models available")
        continue

    n_cols = len(available_matchups)
    fig, axes = plt.subplots(1, n_cols, figsize=(6 * n_cols, 8))
    if n_cols == 1:
        axes = [axes]

    for ax, matchup_type in zip(axes, available_matchups):
        perm_df = importance_tables_grid[(contract_type, matchup_type)].head(15)

        features = perm_df['feature'].values
        importances = perm_df['perm_importance'].values
        stds = perm_df['perm_std'].values

        color = matchup_colors.get(matchup_type, 'gray')
        ax.barh(range(len(features)), importances, xerr=stds, color=color, alpha=0.7, capsize=3)
        ax.set_yticks(range(len(features)))
        ax.set_yticklabels(features, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel('Permutation Importance')

        cell_result = model_results_grid_df[
            (model_results_grid_df['contract_type'] == contract_type) &
            (model_results_grid_df['matchup_type'] == matchup_type)
        ].iloc[0]
        r2 = cell_result['r2']
        n_train = cell_result['n_train']
        ax.set_title(f'{matchup_type}\n(n={n_train}, R²={r2:.3f})')
        ax.grid(axis='x', alpha=0.3)

    fig.suptitle(f"{contract_type.upper()} Contracts: Feature Importance Comparison", fontsize=12, y=1.02)
    plt.tight_layout()
    plt.show()

# %%
# Legacy variables for backward compatibility
importance_tables = {}
importance_tables_by_matchup = {}

# Aggregate importance by contract type (across matchups)
for contract_type in CONTRACT_TYPES:
    dfs = [importance_tables_grid[(contract_type, mt)] for mt in KEY_MATCHUP_TYPES
           if (contract_type, mt) in importance_tables_grid]
    if dfs:
        combined = pd.concat(dfs).groupby('feature').agg({
            'perm_importance': 'mean',
            'perm_std': 'mean'
        }).reset_index().sort_values('perm_importance', ascending=False)
        importance_tables[contract_type] = combined

# Aggregate importance by matchup type (across contracts)
for matchup_type in KEY_MATCHUP_TYPES:
    dfs = [importance_tables_grid[(ct, matchup_type)] for ct in CONTRACT_TYPES
           if (ct, matchup_type) in importance_tables_grid]
    if dfs:
        combined = pd.concat(dfs).groupby('feature').agg({
            'perm_importance': 'mean',
            'perm_std': 'mean'
        }).reset_index().sort_values('perm_importance', ascending=False)
        importance_tables_by_matchup[matchup_type] = combined

print("\n✓ Modeling complete (3×3 grid with deal-grouped split)")

# %%
# Top-9 feature relationship plots per contract type
# Uses aggregated importance from the grid

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

    fig.suptitle(f"{contract_type.upper()} Contracts - Top Feature Relationships (by contract)", y=1.02)
    plt.tight_layout()
    plt.show()

# %%
# Top-9 feature relationship plots by matchup type (greedy_vs_glutton only)
# Faceted by contract type

if 'greedy_vs_glutton' in importance_tables_by_matchup:
    top_feats_h2h = importance_tables_by_matchup['greedy_vs_glutton']['feature'].head(9).tolist()
    feat_cols_h2h = [f"feat_{name}" for name in top_feats_h2h if f"feat_{name}" in smart_data.columns]

    if feat_cols_h2h:
        h2h_data = smart_data[smart_data['matchup_type'] == 'greedy_vs_glutton']

        fig, axes = plt.subplots(3, 3, figsize=(14, 12))
        axes = axes.flatten()

        for ax, feat_col in zip(axes, feat_cols_h2h):
            sns.regplot(
                data=h2h_data,
                x=feat_col,
                y='tricks_won',
                ax=ax,
                scatter_kws={'alpha': 0.3, 's': 10},
                line_kws={'color': 'red'},
            )
            ax.set_title(feat_col.replace('feat_', ''))
            ax.set_xlabel('')
            ax.set_ylabel('')

        for ax in axes[len(feat_cols_h2h):]:
            ax.axis('off')

        fig.suptitle("Greedy vs Glutton - Top Feature Relationships (by matchup)", y=1.02)
        plt.tight_layout()
        plt.show()

# %% [markdown]
# ---
# ## Section 4b: Deal-Level Wide Dataset Modeling
#
# **Different question than seat-level modeling:**
# - **Seat-level (Section 4):** "Given one seat's features, how many tricks will that team win?"
# - **Deal-level wide:** "Given all four seats' features together, how many tricks will team 0 win?"
#
# The wide dataset answers: "How do the features of all hands in a deal jointly predict the outcome?"
#
# This is useful for:
# - Understanding feature interactions across seats
# - Modeling the deal as a whole (all information available)
# - Comparing to seat-level to see if more information helps
#
# **Methodology:**
# - Pivot seat-level data to one row per deal with seat-prefixed features
# - Predict `team0_tricks` from all 4 seats' features
# - Use GroupShuffleSplit to prevent data leakage (same deal_id cannot appear in train and test)

# %%
# ============================================================================
# Section 4b: Deal-Level Wide Dataset Modeling
# ============================================================================


def pivot_to_deal_level_wide(df: pd.DataFrame) -> pd.DataFrame:
    """Transform seat-level DataFrame to deal-level with seat-prefixed features.

    Input: seat-level DF with columns including deal_id, seat, contract_type, trump,
           strategy_id, tricks_won, feat_* columns
    Output: one row per deal with:
        - seat0_feat_*, seat1_feat_*, seat2_feat_*, seat3_feat_*
        - team0_tricks, team1_tricks, delta_tricks
        - contract_type, trump, strategy_id

    Args:
        df: Seat-level DataFrame with features and outcomes

    Returns:
        Deal-level DataFrame with seat-prefixed features
    """
    # Get feature columns
    feat_cols = [c for c in df.columns if c.startswith('feat_')]

    # Key columns for joining
    deal_keys = ['deal_id', 'contract_type', 'trump', 'strategy_id']

    # Build wide dataset by pivoting each seat
    wide_dfs = []
    for seat in range(4):
        seat_df = df[df['seat'] == seat].copy()
        # Rename feature columns with seat prefix
        rename_map = {feat: f'seat{seat}_{feat}' for feat in feat_cols}
        rename_map['tricks_won'] = f'seat{seat}_tricks_won'
        seat_df = seat_df.rename(columns=rename_map)
        # Keep only deal keys and renamed columns
        keep_cols = deal_keys + [c for c in seat_df.columns if c.startswith(f'seat{seat}_')]
        wide_dfs.append(seat_df[keep_cols])

    # Merge all seats on deal keys
    result = wide_dfs[0]
    for seat_df in wide_dfs[1:]:
        result = result.merge(seat_df, on=deal_keys, how='inner')

    # Add team-level outcomes (seats 0 & 2 are team 0, seats 1 & 3 are team 1)
    # Note: tricks_won is already team-level in our logging, so seat0 == seat2 and seat1 == seat3
    result['team0_tricks'] = result['seat0_seat0_tricks_won'] if 'seat0_seat0_tricks_won' in result.columns else result['seat0_tricks_won']
    result['team1_tricks'] = result['seat1_seat1_tricks_won'] if 'seat1_seat1_tricks_won' in result.columns else result['seat1_tricks_won']

    # Handle column name variants
    for col in result.columns:
        if col.endswith('_tricks_won'):
            if col.startswith('seat0_') and 'team0_tricks' not in result.columns:
                result['team0_tricks'] = result[col]
            elif col.startswith('seat1_') and 'team1_tricks' not in result.columns:
                result['team1_tricks'] = result[col]

    result['delta_tricks'] = result['team0_tricks'] - result['team1_tricks']

    return result


print("\n" + "=" * 70)
print("DEAL-LEVEL WIDE DATASET MODELING")
print("=" * 70)

# Pivot to wide format using smart_data (filtered to key matchups)
wide_df = pivot_to_deal_level_wide(smart_data)
print(f"\nWide dataset shape: {wide_df.shape}")
print(f"Unique deals: {wide_df['deal_id'].nunique()}")

# Get all seat-prefixed feature columns
wide_feat_cols = [c for c in wide_df.columns if any(c.startswith(f'seat{s}_feat_') for s in range(4))]
print(f"Total wide features: {len(wide_feat_cols)} (4 seats × {len(wide_feat_cols)//4} features)")

# %%
# Train wide model for greedy_vs_glutton matchup
print("\n--- Training Deal-Level Wide Model (greedy_vs_glutton) ---")

wide_h2h = wide_df[wide_df['strategy_id'].str.contains('greedy') & wide_df['strategy_id'].str.contains('glutton')]

if len(wide_h2h) >= MIN_DEALS_THRESHOLD:
    X_wide = wide_h2h[wide_feat_cols].select_dtypes(include=[np.number])
    y_wide = wide_h2h['team0_tricks']
    groups_wide = wide_h2h['deal_id']

    # Deal-grouped split
    gss_wide = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    train_idx_w, test_idx_w = next(gss_wide.split(X_wide, y_wide, groups=groups_wide))

    X_train_w, X_test_w = X_wide.iloc[train_idx_w], X_wide.iloc[test_idx_w]
    y_train_w, y_test_w = y_wide.iloc[train_idx_w], y_wide.iloc[test_idx_w]

    n_deals_train_w = groups_wide.iloc[train_idx_w].nunique()
    n_deals_test_w = groups_wide.iloc[test_idx_w].nunique()

    # Fit model
    scaler_wide = StandardScaler()
    X_train_w_scaled = scaler_wide.fit_transform(X_train_w)
    X_test_w_scaled = scaler_wide.transform(X_test_w)

    ridge_wide = Ridge(alpha=1.0, random_state=SEED)
    ridge_wide.fit(X_train_w_scaled, y_train_w)

    y_pred_w = ridge_wide.predict(X_test_w_scaled)
    r2_wide = r2_score(y_test_w, y_pred_w)
    mae_wide = mean_absolute_error(y_test_w, y_pred_w)

    print(f"  Train deals: {n_deals_train_w}, Test deals: {n_deals_test_w}")
    print(f"  R² (wide model): {r2_wide:.4f}")
    print(f"  MAE (wide model): {mae_wide:.4f}")

    # Compare to seat-level model R² for same matchup
    seat_level_r2 = None
    for ct in CONTRACT_TYPES:
        key = (ct, 'greedy_vs_glutton')
        if key in importance_tables_grid:
            cell_result = model_results_grid_df[
                (model_results_grid_df['contract_type'] == ct) &
                (model_results_grid_df['matchup_type'] == 'greedy_vs_glutton')
            ]
            if len(cell_result) > 0 and not pd.isna(cell_result.iloc[0]['r2']):
                if seat_level_r2 is None:
                    seat_level_r2 = cell_result.iloc[0]['r2']
                else:
                    seat_level_r2 = max(seat_level_r2, cell_result.iloc[0]['r2'])

    if seat_level_r2 is not None:
        improvement = r2_wide - seat_level_r2
        print("\n  Comparison to seat-level:")
        print(f"    Best seat-level R²: {seat_level_r2:.4f}")
        print(f"    Wide model R²: {r2_wide:.4f}")
        print(f"    Improvement: {improvement:+.4f}")

    # Permutation importance for wide model
    perm_wide = permutation_importance(
        ridge_wide, X_test_w_scaled, y_test_w, n_repeats=5, random_state=SEED
    )
    perm_wide_df = pd.DataFrame({
        'feature': X_wide.columns,
        'perm_importance': perm_wide.importances_mean,
        'perm_std': perm_wide.importances_std,
    }).sort_values('perm_importance', ascending=False)

    print("\n  Top 15 features (wide model):")
    display(perm_wide_df.head(15).round(4))

    # Plot top features
    fig, ax = plt.subplots(figsize=(12, 8))
    top_wide = perm_wide_df.head(20)
    colors = []
    for feat in top_wide['feature']:
        if 'seat0_' in feat or 'seat2_' in feat:
            colors.append('steelblue')  # Team 0
        else:
            colors.append('darkorange')  # Team 1

    ax.barh(range(len(top_wide)), top_wide['perm_importance'].values,
            xerr=top_wide['perm_std'].values, color=colors, alpha=0.7, capsize=3)
    ax.set_yticks(range(len(top_wide)))
    ax.set_yticklabels([f.replace('feat_', '') for f in top_wide['feature']], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel('Permutation Importance')
    ax.set_title(f'Deal-Level Wide Model: Top 20 Features\n(R²={r2_wide:.3f}, greedy_vs_glutton)\nBlue=Team0 seats, Orange=Team1 seats')
    ax.grid(axis='x', alpha=0.3)
    plt.tight_layout()
    plt.show()

else:
    print(f"  Insufficient data for wide model (n={len(wide_h2h)} < {MIN_DEALS_THRESHOLD})")

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
    summary['info'].append(
        f"ℹ️  Top feature ({contract_type}): {feat_name} "
        f"(r={top_feat['correlation']:+.3f}, n={top_feat['n_samples']})"
    )

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
