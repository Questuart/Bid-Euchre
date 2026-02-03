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
#     codemirror_mode:
#       name: ipython
#       version: 3
#     file_extension: .py
#     mimetype: text/x-python
#     name: python
#     nbconvert_exporter: python
#     pygments_lexer: ipython3
#     version: 3.10.0
# ---

# %% [markdown]
# # Phase 0: Health Checks
#
# This notebook provides diagnostic visualizations for bidless simulation datasets.
# It helps verify data integrity, detect biases, and explore feature-label relationships.
#
# **Sections:**
# 0. Health Scorecard (quick pass/warn/fail summary)
# 1. Run Summary & Data Loading
# 2. Dataset Integrity Checks
# 3. Strata Completeness
# 4. Symmetry Analysis
#    - 4.1.0 By Contract_Type
#    - 4.1.1 By Suit (suit contracts only)
#    - 4.1.2 By High/Low (high vs low contracts)
#    - 4.2.0 By Team
#    - 4.3.0 By Seat
#    - 4.4.0 By Contract_Type and Team (interaction)
# 5. Feature Distributions
# 6. Feature-Label Relationships
#    - 6.1 Correlation Heatmaps
#    - 6.2 Correlation Tables
#    - 6.3 Scatter Plots
# 7. Time/Batch Drift Analysis
# 8. Summary

# %% [markdown]
# ## Configuration
#
# Set the path to your dataset directory here:

# %% tags=["parameters"]
# === CONFIGURATION (papermill parameters) ===

# --- Execution Mode ---
# MODE controls sample size: "SMOKE" (~100 deals), "QUICK" (~2k deals), "FULL" (~50k deals)
MODE = "QUICK"

# --- Data Source Mode ---
DEMO_MODE = True  # If True, generates synthetic data; if False, loads from RUN_DIR

# If DEMO_MODE=False, set this path:
RUN_DIR = "../../data/runs/YOUR_RUN_ID"  # Will load from RUN_DIR/datasets/

# --- Demo Mode Parameters (computed from MODE when DEMO_MODE=True) ---
DEMO_SEED = 42
_MODE_N_DEALS = {"SMOKE": 100, "QUICK": 2000, "FULL": 50000}
DEMO_N_DEALS = _MODE_N_DEALS.get(MODE, 2000)  # Fallback to QUICK

# --- Analysis Parameters ---
ROLLING_WINDOW = 100  # Window size for rolling mean plots
TOP_FEATURES = 9      # Number of features to show in distribution grid

# %% [markdown]
# ## Experimental Setup: Phase 0 Bidless
#
# **What is Phase 0?**
# - **No bidding phase**: Contracts and trumps are assigned exogenously (not chosen through bidding)
# - **Scenario-driven assignment**: Contracts/trumps come from explicit scenario list in experiment config (not uniform random sampling)
# - **Policy-dependent outcomes**: The `tricks_won` values depend on the play strategy used (e.g., RandomLegalStrategy, GreedyStrategy)
# - **Determinism**: Seed controls both deal generation and any strategy randomness
#
# **This dataset:**
# - Strategy: Check metadata for `strategies` field (typically RandomLegalStrategy with seed)
# - Scenarios: Check metadata for `scenarios` field (typically 6: suit×4 trumps + high + low)
# - Deals per scenario: Check metadata for `n_per` field
#
# See `meta.json` or use `load_meta()` to inspect these values.

# %%
# Standard imports
import sys
from pathlib import Path

import pandas as pd
from IPython.display import display

# Add src to path for local development
project_root = Path.cwd().parent.parent
if str(project_root / "src") not in sys.path:
    sys.path.insert(0, str(project_root / "src"))

# Diagnostic utilities
import matplotlib.pyplot as plt

from bid_euchre.diagnostics import (
    compute_health_scorecard,
    compute_seat_balance,
    display_issues,
    display_scorecard,
    load_bidless_dataset,
    load_meta,
)
from bid_euchre.diagnostics.loaders import get_dataset_summary

# Optional: seaborn for enhanced visualizations
try:
    import seaborn as sns
    sns.set_theme(style="whitegrid")
except ImportError:
    print("seaborn not available, using matplotlib defaults")

# Configure matplotlib
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['figure.dpi'] = 100

print("Imports successful!")


# %%
# ============================================================================
# SHARED PLOTTING HELPER
# ============================================================================

def plot_violin_box(data, x, y, ax, palette='Set2', box_width=0.15, **kwargs):
    """Violin plot with nested boxplot overlay.

    Falls back to simple boxplot if seaborn unavailable.
    """
    try:
        import seaborn as sns
        sns.violinplot(data=data, x=x, y=y, ax=ax,
                       inner=None, cut=0, palette=palette, **kwargs)
        sns.boxplot(data=data, x=x, y=y, ax=ax,
                    width=box_width, palette=palette,
                    boxprops={'zorder': 2},
                    flierprops={'marker': 'o', 'markersize': 3},
                    **kwargs)
    except ImportError:
        data.boxplot(column=y, by=x, ax=ax)


print("✅ Shared plotting helper loaded")


def is_paired_data(df: pd.DataFrame, group_col: str, value_col: str = 'hand_id') -> bool:
    """Check if same hand_ids/deal_ids appear across all groups (paired design).

    Args:
        df: DataFrame with observations
        group_col: Column defining groups (e.g., 'contract_type')
        value_col: Column to check for pairing (default 'hand_id')

    Returns:
        True if all IDs appear in all groups (paired data)
    """
    groups = df[group_col].unique()
    if len(groups) < 2:
        return False

    # Get IDs for each group
    id_sets = [set(df[df[group_col] == g][value_col].unique()) for g in groups]

    # Check if intersection equals all sets (same IDs in all groups)
    common_ids = set.intersection(*id_sets)
    all_ids = set.union(*id_sets)

    # Consider paired if >90% of IDs appear in all groups
    return len(common_ids) / len(all_ids) > 0.9 if all_ids else False


print("✅ Paired data helper loaded")


# %%
# ============================================================================
# DATA GENERATION FACTORY (for demo mode)
# ============================================================================

def build_demo_dataset(seed: int, n_deals: int) -> pd.DataFrame:
    """Build demo bidless dataset with features only (no simulation).

    Generates data for all 6 Phase 0 scenarios: 4 suit contracts + high + low.

    Args:
        seed: Random seed for reproducibility
        n_deals: Number of deals per scenario

    Returns:
        DataFrame with hand_id, seat, contract_type, trump_suit, feat_* columns
    """
    from bid_euchre.features.hand_eval import get_hand_features
    from bid_euchre.sim.deals import generate_deal

    contract_types = ['suit', 'suit', 'suit', 'suit', 'high', 'low']
    trumps = ['C', 'D', 'H', 'S', None, None]  # Aligned with contract_types

    hands_data = []
    for deal_id in range(n_deals):
        hands = generate_deal(seed, deal_id)

        for contract_type, trump in zip(contract_types, trumps):
            for seat in range(4):
                hand = hands[seat]
                features = get_hand_features(hand, contract_type, trump)
                hands_data.append({
                    'hand_id': f"{deal_id}_{contract_type}_{trump}",
                    'seat': seat,
                    'contract_type': contract_type,
                    'trump_suit': trump if contract_type == 'suit' else None,
                    **{f'feat_{k}': v for k, v in features.items()}
                })

    return pd.DataFrame(hands_data)


print("✅ Demo data factory loaded")

# %% [markdown]
# **Data Source Options:**
#
# 1. **Production mode** (`DEMO_MODE=False`):
#    - Point `RUN_DIR` to an existing experiment run
#    - Generate production dataset with:
#      ```bash
#      PYTHONPATH=src python experiments/run_experiment.py \
#        --config experiments/configs/bidless_dataset_collection.yaml \
#        --seed 42 \
#        --n_per 2000
#      ```
#    - Then set `RUN_DIR = "../../data/runs/<your_run_id>"`
#
# 2. **Demo mode** (`DEMO_MODE=True`):
#    - Generates synthetic data in-memory
#    - Uses `DEMO_N_DEALS=2000` (meets rigor standards for bias detection)
#    - Useful for testing, development, or when no pre-existing dataset available

# %%
# ============================================================================
# Data Loading / Generation
# ============================================================================

if not DEMO_MODE:
    print("📂 Loading existing dataset from RUN_DIR...")
    from pathlib import Path

    dataset_path = Path(RUN_DIR) / "datasets"
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}\n"
            f"Set RUN_DIR to your run directory, or use DEMO_MODE=True"
        )

    df = load_bidless_dataset(dataset_path)
    print(f"✅ Loaded {len(df):,} rows from {dataset_path}")

else:
    print("🎭 DEMO_MODE=True: Generating synthetic data...")
    print(f"   Seed: {DEMO_SEED}")
    print(f"   Deals per scenario: {DEMO_N_DEALS}")
    print("   Scenarios: 6 (4 suit + high + low)")

    df = build_demo_dataset(seed=DEMO_SEED, n_deals=DEMO_N_DEALS)
    dataset_path = None  # No disk path for demo data

    print(f"\n✅ Generated {len(df):,} rows (synthetic demo data)")
    print(f"   Expected: {DEMO_N_DEALS * 6 * 4:,} rows (n_deals × scenarios × seats)")

# %% [markdown]
# ---
# ## Section 0: Health Scorecard
#
# Quick pass/warn/fail summary of dataset health.

# %%
# Compute and display health scorecard
scorecard = compute_health_scorecard(df)
print(display_scorecard(scorecard))

# %% [markdown]
# ---
# ## Section 1: Run Summary & Data Loading
#
# Overview of the loaded dataset.

# %%
# Load metadata if available
if dataset_path is not None:
    try:
        meta = load_meta(dataset_path)
        print("=== Metadata ===")
        for key, value in meta.items():
            print(f"  {key}: {value}")
    except FileNotFoundError:
        print("No metadata file found (bidless_meta.json)")
else:
    print("=== Metadata ===")
    print("  No metadata (demo mode)")

# Dataset summary
print("\n=== Dataset Summary ===")
summary = get_dataset_summary(df)
for key, value in summary.items():
    if key != 'feature_columns':
        print(f"  {key}: {value}")

print(f"\n  Feature columns ({len(summary['feature_columns'])}):")
for col in summary['feature_columns'][:10]:
    print(f"    - {col}")
if len(summary['feature_columns']) > 10:
    print(f"    ... and {len(summary['feature_columns']) - 10} more")

# %%
# Preview the data
print("=== Data Preview ===")
display(df.head(8))

# %% [markdown]
# ---
# ## Section 2: Dataset Integrity Checks
#
# Detailed integrity verification.

# %%
# Check (hand_id, seat) uniqueness
print("=== Row Uniqueness ===")
duplicates = df.duplicated(subset=['hand_id', 'seat']).sum()
print(f"  Duplicate (hand_id, seat) pairs: {duplicates}")
status = '\u2705 PASS' if duplicates == 0 else '\u274c FAIL'
print(f"  Status: {status}")

# Check seats per hand
print("\n=== Seats Per Hand ===")
seats_per_hand = df.groupby('hand_id').size()
print(f"  Hands with exactly 4 seats: {(seats_per_hand == 4).sum()}")
print(f"  Hands with != 4 seats: {(seats_per_hand != 4).sum()}")

# Check for NaN values in features
print("\n=== NaN Values in Features ===")
feat_cols = [c for c in df.columns if c.startswith('feat_')]
nan_counts = df[feat_cols].isna().sum()
total_nans = nan_counts.sum()
print(f"  Total NaN values: {total_nans}")
if total_nans > 0:
    print("  Columns with NaN:")
    for col, count in nan_counts[nan_counts > 0].items():
        print(f"    {col}: {count}")

# %% [markdown]
# ---
# ## Section 3: Strata Completeness
#
# Check that all contract types, trump suits, and seats are balanced.

# %%
print("=== Strata Completeness (Contract × Trump × Seat) ===")
print("\nCounts by contract type:")
contract_counts = df.groupby('contract_type').size()
display(contract_counts)

print("\nCounts by trump suit (suit contracts only):")
suit_df = df[df['contract_type'] == 'suit']
if len(suit_df) > 0:
    trump_counts = suit_df.groupby('trump_suit').size()
    display(trump_counts)

    # Check balance
    expected_per_trump = len(suit_df) / suit_df['trump_suit'].nunique()
    imbalance = trump_counts.max() - trump_counts.min()
    if imbalance > expected_per_trump * 0.1:  # 10% tolerance
        print(f"⚠️  Imbalance detected: {imbalance} row difference across trumps")
    else:
        print("✅ Trump distribution shows balanced counts (within 10% tolerance)")

print("\nCounts by seat:")
seat_counts = df.groupby('seat').size()
display(seat_counts)

# Check seat balance
expected_per_seat = len(df) / df['seat'].nunique()
imbalance = seat_counts.max() - seat_counts.min()
if imbalance > expected_per_seat * 0.05:  # 5% tolerance
    print(f"⚠️  Seat imbalance: {imbalance} row difference")
else:
    print("✅ Seat counts balanced")

# %% [markdown]
# ---
# ## Section 4: Symmetry Analysis
#
# Validates that hand value distributions are symmetric across contract types,
# trump suits, teams, and seats.

# %%
# ============================================================================
# SECTION 4.1.0: BY CONTRACT_TYPE
# ============================================================================

from scipy.stats import f_oneway, friedmanchisquare, ttest_ind

print("=" * 80)
print("SECTION 4.1.0: HAND VALUE BY CONTRACT_TYPE")
print("=" * 80)

# Statistics by contract type
print("\n=== Descriptive Statistics by Contract Type ===")
contract_stats = df.groupby('contract_type')['feat_hand_value'].agg(['count', 'mean', 'std', 'min', 'max'])
display(contract_stats)

# Statistical test across contract types (paired or independent)
contract_groups = [df[df['contract_type'] == ct]['feat_hand_value'].values
                   for ct in ['suit', 'high', 'low']]

# Check if paired (same hand_ids across contract types)
paired = is_paired_data(df, 'contract_type')
if paired and len(contract_groups) >= 3:
    min_len = min(len(g) for g in contract_groups)
    aligned = [g[:min_len] for g in contract_groups]
    stat, p_value = friedmanchisquare(*aligned)
    test_name = "Friedman"
else:
    stat, p_value = f_oneway(*contract_groups)
    test_name = "ANOVA"

print(f"\n=== {test_name}: Hand Value ~ Contract_Type ===")
print(f"  {'Chi-squared' if test_name == 'Friedman' else 'F'}-statistic: {stat:.4f}")
print(f"  p-value: {p_value:.4f}")
print("  Significance level: α = 0.05")
print(f"  Test type: {test_name} ({'paired' if paired else 'independent'})")

# Effect size (eta-squared)
grand_mean = df['feat_hand_value'].mean()
ss_between = sum(len(df[df['contract_type'] == ct]) *
                 (df[df['contract_type'] == ct]['feat_hand_value'].mean() - grand_mean)**2
                 for ct in ['suit', 'high', 'low'])
ss_total = ((df['feat_hand_value'] - grand_mean)**2).sum()
eta_squared = ss_between / ss_total if ss_total > 0 else 0

print(f"  Effect size (η²): {eta_squared:.4f}")
print(f"  Interpretation: {eta_squared*100:.2f}% of variance explained by contract_type")

# Violin+box plot by contract type
fig, ax = plt.subplots(figsize=(10, 6))
plot_violin_box(df, x='contract_type', y='feat_hand_value', ax=ax, palette='Set2')
ax.set_title(f'Hand Value by Contract Type (ANOVA p={p_value:.4f})')
ax.set_xlabel('Contract Type')
ax.set_ylabel('Hand Value')
plt.tight_layout()
plt.show()

# %%
# ============================================================================
# SECTION 4.1.1: BY SUIT (suit contracts only)
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 4.1.1: HAND VALUE BY TRUMP SUIT (Suit Contracts Only)")
print("=" * 80)

suit_df = df[df['contract_type'] == 'suit']

if len(suit_df) > 0:
    # Descriptive statistics
    print("\n=== Descriptive Statistics by Trump Suit ===")
    trump_stats = suit_df.groupby('trump_suit')['feat_hand_value'].agg(['count', 'mean', 'std'])
    display(trump_stats)

    # Statistical test for trump suit equivalence (paired or independent)
    groups = [suit_df[suit_df['trump_suit'] == suit]['feat_hand_value'].values
              for suit in ['C', 'D', 'H', 'S']]

    # Check if paired (same hand_ids across trump suits)
    paired = is_paired_data(suit_df, 'trump_suit')
    if paired and len(groups) >= 3:
        min_len = min(len(g) for g in groups)
        aligned = [g[:min_len] for g in groups]
        stat, p_value = friedmanchisquare(*aligned)
        test_name = "Friedman"
    else:
        stat, p_value = f_oneway(*groups)
        test_name = "ANOVA"

    print(f"\n=== {test_name}: Hand Value ~ Trump Suit ===")
    print(f"  {'Chi-squared' if test_name == 'Friedman' else 'F'}-statistic: {stat:.4f}")
    print(f"  p-value: {p_value:.4f}")
    print("  Significance level: α = 0.05")
    print(f"  Test type: {test_name} ({'paired' if paired else 'independent'})")

    # Effect size (eta-squared)
    grand_mean = suit_df['feat_hand_value'].mean()
    ss_between = sum(len(suit_df[suit_df['trump_suit'] == suit]) *
                     (suit_df[suit_df['trump_suit'] == suit]['feat_hand_value'].mean() - grand_mean)**2
                     for suit in ['C', 'D', 'H', 'S'])
    ss_total = ((suit_df['feat_hand_value'] - grand_mean)**2).sum()
    eta_squared = ss_between / ss_total if ss_total > 0 else 0

    print(f"  Effect size (η²): {eta_squared:.4f}")
    print(f"  Interpretation: {eta_squared*100:.2f}% of variance explained by trump suit")

    # Validation gate
    if p_value < 0.05:
        print(f"  ❌ FAIL: Trump suit bias detected (p={p_value:.4f})")
        print("         Mean hand values differ significantly across trump suits")

        # Post-hoc Tukey HSD
        from scipy.stats import tukey_hsd
        res = tukey_hsd(*groups)
        print("\n  Post-hoc pairwise comparisons (Tukey HSD):")
        suits = ['C', 'D', 'H', 'S']
        for i in range(len(suits)):
            for j in range(i+1, len(suits)):
                sig_marker = "***" if res.pvalue[i,j] < 0.05 else "n.s."
                print(f"    {suits[i]} vs {suits[j]}: p={res.pvalue[i,j]:.4f} {sig_marker}")
    else:
        print("  ✅ PASS: No significant trump suit bias")

    # Violin+box plot
    fig, ax = plt.subplots(figsize=(10, 6))
    plot_violin_box(suit_df, x='trump_suit', y='feat_hand_value', ax=ax, palette='Set2')
    ax.set_title(f'Hand Value by Trump Suit (ANOVA p={p_value:.4f})')
    ax.set_xlabel('Trump Suit')
    ax.set_ylabel('Hand Value')
    plt.tight_layout()
    plt.show()
else:
    print("No suit contracts in dataset")

# %%
# ============================================================================
# SECTION 4.1.2: BY HIGH/LOW (high vs low contracts)
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 4.1.2: HAND VALUE BY HIGH vs LOW")
print("=" * 80)

highlow_df = df[df['contract_type'].isin(['high', 'low'])]

if len(highlow_df) > 0:
    # Descriptive statistics
    print("\n=== Descriptive Statistics by Contract Type (High/Low) ===")
    hl_stats = highlow_df.groupby('contract_type')['feat_hand_value'].agg(['count', 'mean', 'std'])
    display(hl_stats)

    # Two-sample t-test
    high_vals = highlow_df[highlow_df['contract_type'] == 'high']['feat_hand_value'].values
    low_vals = highlow_df[highlow_df['contract_type'] == 'low']['feat_hand_value'].values

    t_stat, p_value = ttest_ind(high_vals, low_vals)

    print("\n=== t-test: Hand Value ~ High vs Low ===")
    print(f"  t-statistic: {t_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")
    print("  Significance level: α = 0.05")

    # Effect size (Cohen's d)
    mean_diff = high_vals.mean() - low_vals.mean()
    pooled_std = ((high_vals.std()**2 + low_vals.std()**2) / 2)**0.5
    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0

    print(f"  Effect size (Cohen's d): {cohens_d:.4f}")
    if abs(cohens_d) < 0.2:
        effect_interp = "negligible"
    elif abs(cohens_d) < 0.5:
        effect_interp = "small"
    elif abs(cohens_d) < 0.8:
        effect_interp = "medium"
    else:
        effect_interp = "large"
    print(f"  Interpretation: {effect_interp} effect")

    # Validation gate
    if p_value < 0.05:
        print(f"  ❌ FAIL: Significant difference between high and low (p={p_value:.4f})")
    else:
        print("  ✅ PASS: No significant difference between high and low")

    # Violin+box plot
    fig, ax = plt.subplots(figsize=(8, 6))
    plot_violin_box(highlow_df, x='contract_type', y='feat_hand_value', ax=ax, palette='Set2')
    ax.set_title(f'Hand Value: High vs Low (t-test p={p_value:.4f})')
    ax.set_xlabel('Contract Type')
    ax.set_ylabel('Hand Value')
    plt.tight_layout()
    plt.show()
else:
    print("No high/low contracts in dataset")

# %%
# ============================================================================
# SECTION 4.2.0: BY TEAM
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 4.2.0: HAND VALUE BY TEAM")
print("=" * 80)

df['team'] = df['seat'].apply(lambda s: 0 if s in [0, 2] else 1)

# Split by contract type for visualization
suit_contracts = df[df['contract_type'] == 'suit']
highlow_contracts = df[df['contract_type'].isin(['high', 'low'])]

# Create side-by-side visualizations with violin+box overlay
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Suit contracts
if len(suit_contracts) > 0:
    plot_violin_box(suit_contracts, x='team', y='feat_hand_value', ax=axes[0], palette='Blues')
    axes[0].set_xticklabels(['Team 0 (seats 0,2)', 'Team 1 (seats 1,3)'])
    axes[0].set_title('Hand Value by Team (Suit Contracts)')
    axes[0].set_xlabel('')
    axes[0].set_ylabel('Hand Value')
else:
    axes[0].text(0.5, 0.5, 'No suit contracts', ha='center', va='center')
    axes[0].set_title('Hand Value by Team (Suit Contracts)')

# Plot 2: High/Low contracts
if len(highlow_contracts) > 0:
    plot_violin_box(highlow_contracts, x='team', y='feat_hand_value', ax=axes[1], palette='Greens')
    axes[1].set_xticklabels(['Team 0 (seats 0,2)', 'Team 1 (seats 1,3)'])
    axes[1].set_title('Hand Value by Team (High/Low Contracts)')
    axes[1].set_xlabel('')
    axes[1].set_ylabel('Hand Value')
else:
    axes[1].text(0.5, 0.5, 'No high/low contracts', ha='center', va='center')
    axes[1].set_title('Hand Value by Team (High/Low Contracts)')

plt.tight_layout()
plt.show()

# Statistical tests for team balance
print("\n" + "=" * 70)
print("TEAM BALANCE ANALYSIS (BY CONTRACT TYPE)")
print("=" * 70)

# Test 1: Suit Contracts
if len(suit_contracts) > 0:
    print("\n=== Two-Sample t-test: Hand Value ~ Team (Suit Contracts) ===")

    suit_team_stats = suit_contracts.groupby('team')['feat_hand_value'].agg(['count', 'mean', 'std'])
    display(suit_team_stats)

    team0_suit = suit_contracts[suit_contracts['team'] == 0]['feat_hand_value'].values
    team1_suit = suit_contracts[suit_contracts['team'] == 1]['feat_hand_value'].values

    t_stat, p_value = ttest_ind(team0_suit, team1_suit)

    print(f"\n  t-statistic: {t_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")

    mean_diff = team0_suit.mean() - team1_suit.mean()
    pooled_std = ((team0_suit.std()**2 + team1_suit.std()**2) / 2)**0.5
    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
    print(f"  Effect size (Cohen's d): {cohens_d:.4f}")

    if p_value < 0.05:
        print(f"  ❌ FAIL: Team bias detected in suit contracts (p={p_value:.4f})")
    else:
        print("  ✅ PASS: No significant team bias in suit contracts")

# Test 2: High/Low Contracts
if len(highlow_contracts) > 0:
    print("\n=== Two-Sample t-test: Hand Value ~ Team (High/Low Contracts) ===")

    highlow_team_stats = highlow_contracts.groupby('team')['feat_hand_value'].agg(['count', 'mean', 'std'])
    display(highlow_team_stats)

    team0_hl = highlow_contracts[highlow_contracts['team'] == 0]['feat_hand_value'].values
    team1_hl = highlow_contracts[highlow_contracts['team'] == 1]['feat_hand_value'].values

    t_stat, p_value = ttest_ind(team0_hl, team1_hl)

    print(f"\n  t-statistic: {t_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")

    mean_diff = team0_hl.mean() - team1_hl.mean()
    pooled_std = ((team0_hl.std()**2 + team1_hl.std()**2) / 2)**0.5
    cohens_d = mean_diff / pooled_std if pooled_std > 0 else 0
    print(f"  Effect size (Cohen's d): {cohens_d:.4f}")

    if p_value < 0.05:
        print(f"  ❌ FAIL: Team bias detected in high/low contracts (p={p_value:.4f})")
    else:
        print("  ✅ PASS: No significant team bias in high/low contracts")

# Overall team balance
print("\n" + "=" * 70)
print("OVERALL TEAM BALANCE (ALL CONTRACTS)")
print("=" * 70)

team_stats = df.groupby('team')['feat_hand_value'].agg(['count', 'mean', 'std'])
display(team_stats)

# %%
# ============================================================================
# SECTION 4.3.0: BY SEAT
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 4.3.0: HAND VALUE BY SEAT")
print("=" * 80)

# Split into suit vs high/low contracts
suit_contracts = df[df['contract_type'] == 'suit']
highlow_contracts = df[df['contract_type'].isin(['high', 'low'])]

# Create side-by-side visualizations with violin+box overlay
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Suit contracts
if len(suit_contracts) > 0:
    plot_violin_box(suit_contracts, x='seat', y='feat_hand_value', ax=axes[0], palette='Blues')
    axes[0].set_title('Hand Value by Seat (Suit Contracts)')
    axes[0].set_xlabel('Seat')
    axes[0].set_ylabel('Hand Value')
else:
    axes[0].text(0.5, 0.5, 'No suit contracts', ha='center', va='center')
    axes[0].set_title('Hand Value by Seat (Suit Contracts)')

# Plot 2: High/Low contracts
if len(highlow_contracts) > 0:
    plot_violin_box(highlow_contracts, x='seat', y='feat_hand_value', ax=axes[1], palette='Greens')
    axes[1].set_title('Hand Value by Seat (High/Low Contracts)')
    axes[1].set_xlabel('Seat')
    axes[1].set_ylabel('Hand Value')
else:
    axes[1].text(0.5, 0.5, 'No high/low contracts', ha='center', va='center')
    axes[1].set_title('Hand Value by Seat (High/Low Contracts)')

plt.tight_layout()
plt.show()

# Statistical tests for seat balance
print("\n" + "=" * 70)
print("SEAT BALANCE ANALYSIS (BY CONTRACT TYPE)")
print("=" * 70)

# Test 1: Suit Contracts
if len(suit_contracts) > 0:
    print("\n=== ANOVA: Hand Value ~ Seat (Suit Contracts) ===")

    suit_seat_stats = suit_contracts.groupby('seat')['feat_hand_value'].agg(['count', 'mean', 'std'])
    display(suit_seat_stats)

    suit_groups = [suit_contracts[suit_contracts['seat'] == seat]['feat_hand_value'].values
                   for seat in range(4)]

    f_stat, p_value = f_oneway(*suit_groups)

    print(f"\n  F-statistic: {f_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")

    # Effect size (eta-squared)
    grand_mean = suit_contracts['feat_hand_value'].mean()
    ss_between = sum(len(suit_contracts[suit_contracts['seat'] == seat]) *
                     (suit_contracts[suit_contracts['seat'] == seat]['feat_hand_value'].mean() - grand_mean)**2
                     for seat in range(4))
    ss_total = ((suit_contracts['feat_hand_value'] - grand_mean)**2).sum()
    eta_squared = ss_between / ss_total if ss_total > 0 else 0

    print(f"  Effect size (η²): {eta_squared:.4f}")

    if p_value < 0.05:
        print(f"  ❌ FAIL: Seat bias detected in suit contracts (p={p_value:.4f})")

        from scipy.stats import tukey_hsd
        res = tukey_hsd(*suit_groups)
        print("\n  Post-hoc pairwise comparisons (Tukey HSD):")
        for i in range(4):
            for j in range(i+1, 4):
                sig_marker = "***" if res.pvalue[i,j] < 0.05 else "n.s."
                print(f"    Seat {i} vs Seat {j}: p={res.pvalue[i,j]:.4f} {sig_marker}")
    else:
        print("  ✅ PASS: No significant seat bias in suit contracts")

# Test 2: High/Low Contracts
if len(highlow_contracts) > 0:
    print("\n=== ANOVA: Hand Value ~ Seat (High/Low Contracts) ===")

    highlow_seat_stats = highlow_contracts.groupby('seat')['feat_hand_value'].agg(['count', 'mean', 'std'])
    display(highlow_seat_stats)

    highlow_groups = [highlow_contracts[highlow_contracts['seat'] == seat]['feat_hand_value'].values
                      for seat in range(4)]

    f_stat, p_value = f_oneway(*highlow_groups)

    print(f"\n  F-statistic: {f_stat:.4f}")
    print(f"  p-value: {p_value:.4f}")

    # Effect size (eta-squared)
    grand_mean = highlow_contracts['feat_hand_value'].mean()
    ss_between = sum(len(highlow_contracts[highlow_contracts['seat'] == seat]) *
                     (highlow_contracts[highlow_contracts['seat'] == seat]['feat_hand_value'].mean() - grand_mean)**2
                     for seat in range(4))
    ss_total = ((highlow_contracts['feat_hand_value'] - grand_mean)**2).sum()
    eta_squared = ss_between / ss_total if ss_total > 0 else 0

    print(f"  Effect size (η²): {eta_squared:.4f}")

    if p_value < 0.05:
        print(f"  ❌ FAIL: Seat bias detected in high/low contracts (p={p_value:.4f})")

        from scipy.stats import tukey_hsd
        res = tukey_hsd(*highlow_groups)
        print("\n  Post-hoc pairwise comparisons (Tukey HSD):")
        for i in range(4):
            for j in range(i+1, 4):
                sig_marker = "***" if res.pvalue[i,j] < 0.05 else "n.s."
                print(f"    Seat {i} vs Seat {j}: p={res.pvalue[i,j]:.4f} {sig_marker}")
    else:
        print("  ✅ PASS: No significant seat bias in high/low contracts")

# Overall seat balance
print("\n" + "=" * 70)
print("OVERALL SEAT BALANCE (ALL CONTRACTS)")
print("=" * 70)

balance = compute_seat_balance(df)
print(f"\n  Global mean: {balance.global_mean:.4f}")
print("  Seat means:")
for seat, mean in sorted(balance.seat_means.items()):
    dev = abs(mean - balance.global_mean)
    print(f"    Seat {seat}: {mean:.4f} (deviation: {dev:.4f})")
print(f"  Max deviation: {balance.max_deviation:.4f} (seat {balance.max_deviation_seat})")
balanced_status = '✅ Yes' if balance.is_balanced else '⚠️ No'
print(f"  Balanced: {balanced_status}")

# %%
# ============================================================================
# SECTION 4.4.0: BY CONTRACT_TYPE AND TEAM (interaction)
# ============================================================================

print("\n" + "=" * 80)
print("SECTION 4.4.0: CONTRACT_TYPE × TEAM INTERACTION")
print("=" * 80)

# Create 1×3 faceted subplots: one per contract_type
fig, axes = plt.subplots(1, 3, figsize=(18, 6))

contract_types = ['suit', 'high', 'low']
palettes = ['Blues', 'Greens', 'Purples']

for idx, (ct, palette) in enumerate(zip(contract_types, palettes)):
    ax = axes[idx]
    subset = df[df['contract_type'] == ct]

    if len(subset) > 0:
        plot_violin_box(subset, x='team', y='feat_hand_value', ax=ax, palette=palette)
        ax.set_xticklabels(['Team 0', 'Team 1'])
        ax.set_title(f'{ct.capitalize()} Contracts (n={len(subset):,})')
        ax.set_xlabel('Team')
        ax.set_ylabel('Hand Value')
    else:
        ax.text(0.5, 0.5, f'No {ct} contracts', ha='center', va='center')
        ax.set_title(f'{ct.capitalize()} Contracts')

plt.tight_layout()
plt.show()

# Two-way ANOVA with interaction using statsmodels
print("\n=== Two-Way ANOVA: Hand Value ~ Contract_Type * Team ===")

try:
    from statsmodels.formula.api import ols
    from statsmodels.stats.anova import anova_lm

    model = ols('feat_hand_value ~ C(contract_type) * C(team)', data=df).fit()
    anova_table = anova_lm(model, typ=2)
    print("\nType II ANOVA Table:")
    display(anova_table)

    # Interpretation
    ct_p = anova_table.loc['C(contract_type)', 'PR(>F)']
    team_p = anova_table.loc['C(team)', 'PR(>F)']
    interaction_p = anova_table.loc['C(contract_type):C(team)', 'PR(>F)']

    print("\n  Main effect (Contract_Type): " + ("❌ SIGNIFICANT" if ct_p < 0.05 else "✅ Not significant"))
    print("  Main effect (Team): " + ("❌ SIGNIFICANT" if team_p < 0.05 else "✅ Not significant"))
    print("  Interaction: " + ("❌ SIGNIFICANT" if interaction_p < 0.05 else "✅ Not significant"))

except ImportError:
    print("statsmodels unavailable, running per-contract t-tests instead")
    for ct in ['suit', 'high', 'low']:
        subset = df[df['contract_type'] == ct]
        if len(subset) > 0:
            team0 = subset[subset['team'] == 0]['feat_hand_value']
            team1 = subset[subset['team'] == 1]['feat_hand_value']
            t_stat, p_val = ttest_ind(team0, team1)
            status = "❌ FAIL" if p_val < 0.05 else "✅ PASS"
            print(f"  {ct}: t={t_stat:.4f}, p={p_val:.4f} {status}")

# Clean up team column
df.drop('team', axis=1, inplace=True)

print("\n✅ Section 4 Symmetry Analysis completed")

# %% [markdown]
# ---
# ## Section 5: Feature Distributions
#
# Histograms of key features.

# %%
# ============================================================================
# SECTION 5: FEATURE DISTRIBUTIONS
# ============================================================================

print("=" * 80)
print("SECTION 5: FEATURE DISTRIBUTIONS")
print("=" * 80)

import numpy as np
from scipy.stats import chi2_contingency, ks_2samp

# ============================================================================
# PART 1: SUIT CONTRACT FEATURE DISTRIBUTIONS
# ============================================================================

suit_df = df[df['contract_type'] == 'suit'].copy()

if len(suit_df) > 0:
    print("\n" + "=" * 80)
    print("SUIT CONTRACT FEATURES (Stacked by Trump Suit)")
    print("=" * 80)

    # Trump features to analyze (top 9 most important)
    features_to_plot = [
        'trump_count', 'bowers', 'trump_ace_count', 'trump_king_count',
        'top_trump_count', 'highest_trump_rank', 'trump_power_sum',
        'trump_power_avg', 'trump_duplicate_pairs'
    ]

    # Create grid of stacked bar charts
    n_features = len(features_to_plot)
    n_cols = 3
    n_rows = int(np.ceil(n_features / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows * 4))
    axes = axes.flatten() if n_features > 1 else [axes]

    # Color scheme for trump suits
    suit_colors = {'C': 'tab:blue', 'D': 'tab:orange', 'H': 'tab:red', 'S': 'tab:green'}

    for idx, feat_name in enumerate(features_to_plot):
        ax = axes[idx]
        col_name = f'feat_{feat_name}'

        if col_name not in suit_df.columns:
            ax.text(0.5, 0.5, f'{feat_name}\nnot found', ha='center', va='center')
            ax.set_title(feat_name.replace('_', ' ').title())
            continue

        # Get unique values for this feature
        feat_values = sorted(suit_df[col_name].unique())

        # Count occurrences for each (value, trump_suit) pair
        counts_by_suit = {suit: [] for suit in ['C', 'D', 'H', 'S']}

        for val in feat_values:
            for suit in ['C', 'D', 'H', 'S']:
                count = len(suit_df[(suit_df[col_name] == val) & (suit_df['trump_suit'] == suit)])
                counts_by_suit[suit].append(count)

        # Create stacked bar chart
        x = np.arange(len(feat_values))
        width = 0.8
        bottom = np.zeros(len(feat_values))

        for suit in ['C', 'D', 'H', 'S']:
            ax.bar(x, counts_by_suit[suit], width, bottom=bottom,
                   label=suit, color=suit_colors[suit], alpha=0.8)
            bottom += counts_by_suit[suit]

        ax.set_xlabel('Feature Value')
        ax.set_ylabel('Count')
        ax.set_title(feat_name.replace('_', ' ').title())

        # Fix x-axis readability for features with many unique values
        if feat_name in ['trump_power_avg', 'trump_power_sum'] and len(feat_values) > 10:
            # Select ~10 evenly spaced ticks
            tick_indices = np.linspace(0, len(feat_values) - 1, 10, dtype=int)
            ax.set_xticks([x[i] for i in tick_indices])
            ax.set_xticklabels([f'{feat_values[i]:.1f}' if isinstance(feat_values[i], float)
                               else str(feat_values[i]) for i in tick_indices], rotation=45)
        else:
            ax.set_xticks(x)
            ax.set_xticklabels([f'{v:.1f}' if isinstance(v, float) else str(v)
                                for v in feat_values], rotation=45)

        if idx == 0:
            ax.legend(title='Trump Suit', loc='upper right')

    # Hide unused subplots
    for idx in range(n_features, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()
    plt.show()

    # ========================================================================
    # STATISTICAL VALIDATION: Chi-square tests for trump suit uniformity
    # ========================================================================

    print("\n" + "=" * 80)
    print("STATISTICAL VALIDATION: Trump Suit Uniformity")
    print("=" * 80)

    # All trump features for testing
    trump_features = [
        'trump_count', 'trump_rb_count', 'trump_lb_count', 'trump_ace_count',
        'trump_king_count', 'trump_queen_count', 'trump_ten_count',
        'top_trump_count', 'highest_trump_rank', 'second_highest_trump_rank',
        'third_highest_trump_rank', 'trump_power_sum', 'trump_power_avg',
        'trump_duplicate_pairs', 'top_trump_sum', 'bowers',
        'trump_count_x_void_count', 'trump_count_x_offsuit_ace'
    ]

    print("\nChi-square goodness-of-fit tests for trump features:")
    print("H0: Feature values are uniformly distributed across trump suits C, D, H, S")
    print("Significance level: α = 0.05\n")

    failed_features = []

    for feat_name in trump_features:
        col_name = f'feat_{feat_name}'

        if col_name not in suit_df.columns:
            continue

        # Create contingency table: rows = feature values, cols = trump suits
        contingency = pd.crosstab(suit_df[col_name], suit_df['trump_suit'])

        # Chi-square test
        chi2, p_value, dof, expected = chi2_contingency(contingency)

        # Validation gate
        status = "✅ PASS" if p_value >= 0.05 else "❌ FAIL"

        print(f"  {feat_name:30s}  χ²={chi2:8.4f}  p={p_value:.4f}  {status}")

        if p_value < 0.05:
            failed_features.append(feat_name)

    # Summary
    print("\n" + "-" * 80)
    if len(failed_features) == 0:
        print("✅ ALL FEATURES PASSED: No significant trump suit bias detected")
    else:
        print(f"❌ {len(failed_features)} FEATURE(S) FAILED:")
        for feat in failed_features:
            print(f"   - {feat}")
        print("\nThis indicates potential bias in deal generation or feature extraction.")
    print("-" * 80)

# ============================================================================
# PART 2: HIGH/LOW CONTRACT FEATURE DISTRIBUTIONS
# ============================================================================

highlow_df = df[df['contract_type'].isin(['high', 'low'])].copy()

if len(highlow_df) > 0:
    print("\n\n" + "=" * 80)
    print("HIGH/LOW CONTRACT FEATURES (Stacked by Contract Type)")
    print("=" * 80)

    # Features to analyze for high/low contracts
    highlow_features = [
        'offsuit_aces', 'high_card_count', 'low_card_count',
        'void_count', 'max_suit_len', 'num_singletons',
        'offsuit_king_count_total', 'offsuit_queen_count_total',
        'double_ten_jack_count', 'rank_sum', 'hand_value'
    ]

    # Create grid of stacked bar charts
    n_features = len(highlow_features)
    n_cols = 3
    n_rows = int(np.ceil(n_features / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows * 4))
    axes = axes.flatten() if n_features > 1 else [axes]

    # Color scheme for contract types
    contract_colors = {'high': 'tab:green', 'low': 'tab:purple'}

    for idx, feat_name in enumerate(highlow_features):
        ax = axes[idx]
        col_name = f'feat_{feat_name}'

        if col_name not in highlow_df.columns:
            ax.text(0.5, 0.5, f'{feat_name}\nnot found', ha='center', va='center')
            ax.set_title(feat_name.replace('_', ' ').title())
            continue

        # Get unique values for this feature
        feat_values = sorted(highlow_df[col_name].unique())

        # Limit to reasonable number of bins for continuous features
        if len(feat_values) > 20:
            # Bin continuous features
            bins = np.linspace(highlow_df[col_name].min(),
                              highlow_df[col_name].max(), 15)
            highlow_df['_binned'] = pd.cut(highlow_df[col_name], bins=bins)
            feat_values = sorted(highlow_df['_binned'].dropna().unique())
            binned_col = '_binned'
        else:
            binned_col = col_name

        # Count occurrences for each (value, contract_type) pair
        counts_by_contract = {ct: [] for ct in ['high', 'low']}

        for val in feat_values:
            for ct in ['high', 'low']:
                count = len(highlow_df[(highlow_df[binned_col] == val) &
                                       (highlow_df['contract_type'] == ct)])
                counts_by_contract[ct].append(count)

        # Create stacked bar chart
        x = np.arange(len(feat_values))
        width = 0.8
        bottom = np.zeros(len(feat_values))

        for ct in ['high', 'low']:
            ax.bar(x, counts_by_contract[ct], width, bottom=bottom,
                   label=ct, color=contract_colors[ct], alpha=0.8)
            bottom += counts_by_contract[ct]

        ax.set_xlabel('Feature Value')
        ax.set_ylabel('Count')
        ax.set_title(feat_name.replace('_', ' ').title())
        ax.set_xticks(x[::max(1, len(x)//10)])  # Show subset of labels
        ax.set_xticklabels([str(feat_values[i])[:6] for i in range(0, len(feat_values),
                           max(1, len(x)//10))], rotation=45)
        if idx == 0:
            ax.legend(title='Contract Type', loc='upper right')

        # Clean up temp column
        if '_binned' in highlow_df.columns:
            highlow_df.drop('_binned', axis=1, inplace=True)

    # Hide unused subplots
    for idx in range(n_features, len(axes)):
        axes[idx].axis('off')

    plt.tight_layout()
    plt.show()

    # ========================================================================
    # STATISTICAL VALIDATION: KS tests for distribution differences
    # ========================================================================

    print("\n" + "=" * 80)
    print("STATISTICAL VALIDATION: High vs Low Distribution Differences")
    print("=" * 80)

    print("\nKolmogorov-Smirnov two-sample tests:")
    print("H0: Feature distributions are identical for high and low contracts")
    print("Significance level: α = 0.05\n")

    discriminative_features = []

    for feat_name in highlow_features:
        col_name = f'feat_{feat_name}'

        if col_name not in highlow_df.columns:
            continue

        # Extract values for each contract type
        high_vals = highlow_df[highlow_df['contract_type'] == 'high'][col_name].values
        low_vals = highlow_df[highlow_df['contract_type'] == 'low'][col_name].values

        # KS test
        ks_stat, p_value = ks_2samp(high_vals, low_vals)

        # Interpretation
        if p_value < 0.05:
            status = "🔍 DIFFERENT"
            discriminative_features.append(feat_name)
        else:
            status = "✅ SIMILAR"

        print(f"  {feat_name:30s}  KS={ks_stat:.4f}  p={p_value:.4f}  {status}")

    # Summary
    print("\n" + "-" * 80)
    if len(discriminative_features) > 0:
        print(f"🔍 {len(discriminative_features)} DISCRIMINATIVE FEATURE(S):")
        for feat in discriminative_features:
            print(f"   - {feat}")
        print("\nThese features have significantly different distributions in high vs low.")
    else:
        print("✅ NO DISCRIMINATIVE FEATURES: High and low distributions are similar")
    print("-" * 80)

print("\n" + "=" * 80)
print("END SECTION 5")
print("=" * 80)

# %%
# ============================================================================
# FEATURE STATISTICS (BY CONTRACT TYPE)
# ============================================================================

print("=" * 80)
print("FEATURE STATISTICS")
print("=" * 80)

# ============================================================================
# PART 1: SUIT CONTRACT FEATURE STATISTICS
# ============================================================================

suit_df = df[df['contract_type'] == 'suit']

if len(suit_df) > 0:
    print("\n" + "=" * 80)
    print("SUIT CONTRACT FEATURE STATISTICS")
    print("=" * 80)

    # Trump features to analyze
    trump_feature_cols = [
        'feat_trump_count', 'feat_bowers', 'feat_trump_ace_count',
        'feat_trump_king_count', 'feat_trump_queen_count', 'feat_trump_ten_count',
        'feat_top_trump_count', 'feat_highest_trump_rank', 'feat_trump_power_sum',
        'feat_trump_power_avg', 'feat_trump_rb_count', 'feat_trump_lb_count',
        'feat_top_trump_sum', 'feat_second_highest_trump_rank',
        'feat_third_highest_trump_rank', 'feat_trump_duplicate_pairs'
    ]

    # Filter to only features that exist
    trump_feature_cols = [col for col in trump_feature_cols if col in suit_df.columns]

    if trump_feature_cols:
        stats_df = suit_df[trump_feature_cols].describe().T
        stats_df = stats_df[['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']]
        stats_df.index = [col.replace('feat_', '') for col in stats_df.index]

        print("\nTrump features (suit contracts only):")
        display(stats_df)

# ============================================================================
# PART 2: HIGH/LOW CONTRACT FEATURE STATISTICS
# ============================================================================

highlow_df = df[df['contract_type'].isin(['high', 'low'])]

if len(highlow_df) > 0:
    print("\n" + "=" * 80)
    print("HIGH/LOW CONTRACT FEATURE STATISTICS")
    print("=" * 80)

    # High/low specific features
    highlow_feature_cols = [
        'feat_high_card_count', 'feat_low_card_count', 'feat_double_ten_jack_count',
        'feat_offsuit_aces', 'feat_offsuit_king_count_total',
        'feat_offsuit_queen_count_total', 'feat_void_count', 'feat_max_suit_len',
        'feat_num_singletons', 'feat_rank_sum', 'feat_hand_value'
    ]

    # Filter to only features that exist
    highlow_feature_cols = [col for col in highlow_feature_cols if col in highlow_df.columns]

    if highlow_feature_cols:
        # Overall stats
        stats_df = highlow_df[highlow_feature_cols].describe().T
        stats_df = stats_df[['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']]
        stats_df.index = [col.replace('feat_', '') for col in stats_df.index]

        print("\nHigh/Low features (all):")
        display(stats_df)

        # Break down by contract type
        print("\n" + "-" * 80)
        print("BY CONTRACT TYPE (High vs Low)")
        print("-" * 80)

        for contract_type in ['high', 'low']:
            contract_subset = highlow_df[highlow_df['contract_type'] == contract_type]

            if len(contract_subset) > 0:
                stats_df = contract_subset[highlow_feature_cols].describe().T
                stats_df = stats_df[['count', 'mean', 'std', 'min', 'max']]
                stats_df.index = [col.replace('feat_', '') for col in stats_df.index]

                print(f"\n{contract_type.upper()} contracts:")
                display(stats_df)

# ============================================================================
# PART 3: GENERAL FEATURES (ALL CONTRACTS)
# ============================================================================

print("\n" + "=" * 80)
print("GENERAL FEATURE STATISTICS (ALL CONTRACTS)")
print("=" * 80)

# General features that apply to all contract types
general_feature_cols = [
    'feat_void_count', 'feat_max_suit_len', 'feat_num_singletons',
    'feat_num_doubletons', 'feat_rank_sum', 'feat_hand_value',
    'feat_offsuit_aces', 'feat_offsuit_king_count_total',
    'feat_offsuit_queen_count_total'
]

# Filter to only features that exist
general_feature_cols = [col for col in general_feature_cols if col in df.columns]

if general_feature_cols:
    # Overall stats
    stats_df = df[general_feature_cols].describe().T
    stats_df = stats_df[['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']]
    stats_df.index = [col.replace('feat_', '') for col in stats_df.index]

    print("\nAll contracts:")
    display(stats_df)

    # Break down by contract type
    print("\n" + "-" * 80)
    print("BY CONTRACT TYPE (Suit vs High vs Low)")
    print("-" * 80)

    for contract_type in ['suit', 'high', 'low']:
        contract_subset = df[df['contract_type'] == contract_type]

        if len(contract_subset) > 0:
            stats_df = contract_subset[general_feature_cols].describe().T
            stats_df = stats_df[['count', 'mean', 'std', 'min', 'max']]
            stats_df.index = [col.replace('feat_', '') for col in stats_df.index]

            print(f"\n{contract_type.upper()} contracts:")
            display(stats_df)

print("\n" + "=" * 80)
print("END FEATURE STATISTICS")
print("=" * 80)

# %% [markdown]
# ---
# ## Section 6: Feature-Label Relationships
#
# Correlation analysis and scatter plots.

# %%
# ============================================================================
# SECTION 6.1: CORRELATION HEATMAPS BY CONTRACT TYPE
# ============================================================================

print("=" * 80)
print("SECTION 6.1: CORRELATION HEATMAPS BY CONTRACT TYPE")
print("=" * 80)

import numpy as np

# Split by contract type
suit_df = df[df['contract_type'] == 'suit']
highlow_df = df[df['contract_type'].isin(['high', 'low'])]

# Get feature columns
feat_cols = [c for c in df.columns if c.startswith('feat_')]

# Define feature sets
trump_features = [c for c in feat_cols if 'trump' in c or c == 'feat_bowers']
general_features = [c for c in feat_cols if c not in trump_features]
highlow_features = [c for c in feat_cols if any(x in c for x in ['high_card', 'low_card', 'double_ten_jack'])]

# Create 3-panel heatmap
fig, axes = plt.subplots(1, 3, figsize=(20, 6))

# Panel 1: Suit contracts (trump + general features)
if len(suit_df) > 0:
    suit_features = [c for c in trump_features + general_features if c in suit_df.columns]
    # Limit to top features by variance to keep heatmap readable
    variances = suit_df[suit_features].var()
    top_suit_features = variances.nlargest(15).index.tolist()

    if len(top_suit_features) > 0:
        corr_suit = suit_df[top_suit_features].corr()

        try:
            import seaborn as sns
            sns.heatmap(corr_suit, ax=axes[0], cmap='RdBu_r', center=0, vmin=-1, vmax=1,
                       cbar_kws={'label': 'Correlation'}, annot=False, fmt='.2f')
        except ImportError:
            im = axes[0].imshow(corr_suit, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            axes[0].set_xticks(range(len(top_suit_features)))
            axes[0].set_yticks(range(len(top_suit_features)))
            axes[0].set_xticklabels([c.replace('feat_', '') for c in top_suit_features], rotation=90)
            axes[0].set_yticklabels([c.replace('feat_', '') for c in top_suit_features])
            plt.colorbar(im, ax=axes[0])

        axes[0].set_title(f'Suit Contracts (n={len(suit_df):,})\nTop 15 Features by Variance')

        # Clean up tick labels
        axes[0].set_xticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[0].get_xticklabels()], rotation=45, ha='right')
        axes[0].set_yticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[0].get_yticklabels()], rotation=0)
else:
    axes[0].text(0.5, 0.5, 'No suit contracts', ha='center', va='center')
    axes[0].set_title('Suit Contracts')

# Panel 2: High/low contracts
if len(highlow_df) > 0:
    hl_features = [c for c in highlow_features + general_features if c in highlow_df.columns]
    # Limit to top features by variance
    variances = highlow_df[hl_features].var()
    top_hl_features = variances.nlargest(15).index.tolist()

    if len(top_hl_features) > 0:
        corr_highlow = highlow_df[top_hl_features].corr()

        try:
            import seaborn as sns
            sns.heatmap(corr_highlow, ax=axes[1], cmap='RdBu_r', center=0, vmin=-1, vmax=1,
                       cbar_kws={'label': 'Correlation'}, annot=False, fmt='.2f')
        except ImportError:
            im = axes[1].imshow(corr_highlow, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            axes[1].set_xticks(range(len(top_hl_features)))
            axes[1].set_yticks(range(len(top_hl_features)))
            axes[1].set_xticklabels([c.replace('feat_', '') for c in top_hl_features], rotation=90)
            axes[1].set_yticklabels([c.replace('feat_', '') for c in top_hl_features])
            plt.colorbar(im, ax=axes[1])

        axes[1].set_title(f'High/Low Contracts (n={len(highlow_df):,})\nTop 15 Features by Variance')

        # Clean up tick labels
        axes[1].set_xticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[1].get_xticklabels()], rotation=45, ha='right')
        axes[1].set_yticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[1].get_yticklabels()], rotation=0)
else:
    axes[1].text(0.5, 0.5, 'No high/low contracts', ha='center', va='center')
    axes[1].set_title('High/Low Contracts')

# Panel 3: General features (all contracts)
if len(general_features) > 0:
    available_general = [c for c in general_features if c in df.columns]
    # Limit to top features by variance
    variances = df[available_general].var()
    top_general_features = variances.nlargest(15).index.tolist()

    if len(top_general_features) > 0:
        corr_general = df[top_general_features].corr()

        try:
            import seaborn as sns
            sns.heatmap(corr_general, ax=axes[2], cmap='RdBu_r', center=0, vmin=-1, vmax=1,
                       cbar_kws={'label': 'Correlation'}, annot=False, fmt='.2f')
        except ImportError:
            im = axes[2].imshow(corr_general, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            axes[2].set_xticks(range(len(top_general_features)))
            axes[2].set_yticks(range(len(top_general_features)))
            axes[2].set_xticklabels([c.replace('feat_', '') for c in top_general_features], rotation=90)
            axes[2].set_yticklabels([c.replace('feat_', '') for c in top_general_features])
            plt.colorbar(im, ax=axes[2])

        axes[2].set_title(f'All Contracts (n={len(df):,})\nGeneral Features Only')

        # Clean up tick labels
        axes[2].set_xticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[2].get_xticklabels()], rotation=45, ha='right')
        axes[2].set_yticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[2].get_yticklabels()], rotation=0)

plt.tight_layout()
plt.show()

print("\n✅ Variance-based correlation heatmaps completed")

# ============================================================================
# SECTION 6.1b: CORRELATION HEATMAPS - TOP 15 BY |CORR WITH HAND_VALUE|
# ============================================================================

print("\n" + "=" * 80)
print("TOP 15 FEATURES BY |CORRELATION WITH HAND_VALUE|")
print("=" * 80)

fig, axes = plt.subplots(1, 3, figsize=(20, 6))

# Panel 1: Suit contracts - top 15 by |corr with hand_value|
suit_df = df[df['contract_type'] == 'suit']
if len(suit_df) > 0 and 'feat_hand_value' in suit_df.columns:
    suit_feat_cols = [c for c in suit_df.columns if c.startswith('feat_') and c != 'feat_hand_value']
    corrs = suit_df[suit_feat_cols].corrwith(suit_df['feat_hand_value']).abs()
    top_by_corr = corrs.nlargest(15).index.tolist()

    if len(top_by_corr) > 0:
        # Feature-feature correlation matrix (excluding hand_value)
        corr_matrix = suit_df[top_by_corr].corr()
        try:
            import seaborn as sns
            sns.heatmap(corr_matrix, ax=axes[0], cmap='RdBu_r', center=0, vmin=-1, vmax=1,
                       cbar_kws={'label': 'Correlation'}, annot=False)
        except ImportError:
            im = axes[0].imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            plt.colorbar(im, ax=axes[0])

        axes[0].set_title(f'Suit Contracts (n={len(suit_df):,})\nTop 15 by |corr with hand_value|')
        axes[0].set_xticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[0].get_xticklabels()], rotation=45, ha='right')
        axes[0].set_yticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[0].get_yticklabels()], rotation=0)
else:
    axes[0].text(0.5, 0.5, 'No suit contracts', ha='center', va='center')
    axes[0].set_title('Suit Contracts')

# Panel 2: High/Low contracts - top 15 by |corr with hand_value|
highlow_df = df[df['contract_type'].isin(['high', 'low'])]
if len(highlow_df) > 0 and 'feat_hand_value' in highlow_df.columns:
    hl_feat_cols = [c for c in highlow_df.columns if c.startswith('feat_') and c != 'feat_hand_value']
    corrs = highlow_df[hl_feat_cols].corrwith(highlow_df['feat_hand_value']).abs()
    top_by_corr = corrs.nlargest(15).index.tolist()

    if len(top_by_corr) > 0:
        corr_matrix = highlow_df[top_by_corr].corr()
        try:
            import seaborn as sns
            sns.heatmap(corr_matrix, ax=axes[1], cmap='RdBu_r', center=0, vmin=-1, vmax=1,
                       cbar_kws={'label': 'Correlation'}, annot=False)
        except ImportError:
            im = axes[1].imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            plt.colorbar(im, ax=axes[1])

        axes[1].set_title(f'High/Low Contracts (n={len(highlow_df):,})\nTop 15 by |corr with hand_value|')
        axes[1].set_xticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[1].get_xticklabels()], rotation=45, ha='right')
        axes[1].set_yticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[1].get_yticklabels()], rotation=0)
else:
    axes[1].text(0.5, 0.5, 'No high/low contracts', ha='center', va='center')
    axes[1].set_title('High/Low Contracts')

# Panel 3: All contracts - top 15 general features by |corr with hand_value|
if 'feat_hand_value' in df.columns:
    all_feat_cols = [c for c in df.columns if c.startswith('feat_') and c != 'feat_hand_value']
    corrs = df[all_feat_cols].corrwith(df['feat_hand_value']).abs()
    top_by_corr = corrs.nlargest(15).index.tolist()

    if len(top_by_corr) > 0:
        corr_matrix = df[top_by_corr].corr()
        try:
            import seaborn as sns
            sns.heatmap(corr_matrix, ax=axes[2], cmap='RdBu_r', center=0, vmin=-1, vmax=1,
                       cbar_kws={'label': 'Correlation'}, annot=False)
        except ImportError:
            im = axes[2].imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
            plt.colorbar(im, ax=axes[2])

        axes[2].set_title(f'All Contracts (n={len(df):,})\nTop 15 by |corr with hand_value|')
        axes[2].set_xticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[2].get_xticklabels()], rotation=45, ha='right')
        axes[2].set_yticklabels([label.get_text().replace('feat_', '')
                                 for label in axes[2].get_yticklabels()], rotation=0)

plt.tight_layout()
plt.show()

print("\n✅ Correlation-based heatmaps completed")

# %%
# ============================================================================
# SECTION 6.2: CORRELATION TABLES BY CONTRACT TYPE
# ============================================================================

print("=" * 80)
print("SECTION 6.2: CORRELATION WITH HAND_VALUE BY CONTRACT TYPE")
print("=" * 80)

# Split by contract type
suit_df = df[df['contract_type'] == 'suit']
highlow_df = df[df['contract_type'].isin(['high', 'low'])]

# --- Suit contracts ---
if len(suit_df) > 0 and 'feat_hand_value' in suit_df.columns:
    print("\n=== SUIT CONTRACTS: Top Correlations with hand_value ===")

    suit_feat_cols = [c for c in suit_df.columns if c.startswith('feat_') and c != 'feat_hand_value']
    suit_corr = suit_df[suit_feat_cols].corrwith(suit_df['feat_hand_value'])
    suit_corr_sorted = suit_corr.abs().sort_values(ascending=False)

    # Create DataFrame with both absolute and actual correlation
    suit_corr_df = pd.DataFrame({
        'feature': [c.replace('feat_', '') for c in suit_corr_sorted.index[:15]],
        'correlation': [suit_corr[c] for c in suit_corr_sorted.index[:15]],
        'abs_correlation': suit_corr_sorted.values[:15]
    })

    display(suit_corr_df)

# --- High/Low contracts ---
if len(highlow_df) > 0 and 'feat_hand_value' in highlow_df.columns:
    print("\n=== HIGH/LOW CONTRACTS: Top Correlations with hand_value ===")

    highlow_feat_cols = [c for c in highlow_df.columns if c.startswith('feat_') and c != 'feat_hand_value']
    highlow_corr = highlow_df[highlow_feat_cols].corrwith(highlow_df['feat_hand_value'])
    highlow_corr_sorted = highlow_corr.abs().sort_values(ascending=False)

    # Create DataFrame with both absolute and actual correlation
    highlow_corr_df = pd.DataFrame({
        'feature': [c.replace('feat_', '') for c in highlow_corr_sorted.index[:15]],
        'correlation': [highlow_corr[c] for c in highlow_corr_sorted.index[:15]],
        'abs_correlation': highlow_corr_sorted.values[:15]
    })

    display(highlow_corr_df)

# --- Comparison table: Top 10 features side-by-side ---
print("\n=== COMPARISON: Top 10 Features Across Contract Types ===")

comparison_data = []

# Get top 10 from each contract type
if len(suit_df) > 0 and 'feat_hand_value' in suit_df.columns:
    suit_top10 = suit_corr_sorted.head(10)
    for idx, (feat, abs_corr) in enumerate(suit_top10.items()):
        comparison_data.append({
            'Rank': idx + 1,
            'Suit Feature': feat.replace('feat_', ''),
            'Suit Corr': f"{suit_corr[feat]:.3f}"
        })

if len(highlow_df) > 0 and 'feat_hand_value' in highlow_df.columns:
    highlow_top10 = highlow_corr_sorted.head(10)
    for idx, (feat, abs_corr) in enumerate(highlow_top10.items()):
        if idx < len(comparison_data):
            comparison_data[idx]['H/L Feature'] = feat.replace('feat_', '')
            comparison_data[idx]['H/L Corr'] = f"{highlow_corr[feat]:.3f}"
        else:
            comparison_data.append({
                'Rank': idx + 1,
                'H/L Feature': feat.replace('feat_', ''),
                'H/L Corr': f"{highlow_corr[feat]:.3f}"
            })

comparison_df = pd.DataFrame(comparison_data)
display(comparison_df)

print("\n✅ Correlation analysis completed")

# %%
# ============================================================================
# SECTION 6.3: SCATTER PLOTS BY CONTRACT TYPE
# ============================================================================

print("=" * 80)
print("SECTION 6.3: FEATURE-LABEL SCATTER PLOTS BY CONTRACT TYPE")
print("=" * 80)

# Split by contract type
suit_df = df[df['contract_type'] == 'suit']
highlow_df = df[df['contract_type'].isin(['high', 'low'])]

# Create 2×2 grid of scatter plots
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# ============================================================================
# Panel 1: Trump count vs hand value (suit contracts, colored by trump suit)
# ============================================================================
ax = axes[0, 0]

if len(suit_df) > 0 and 'feat_trump_count' in suit_df.columns and 'feat_hand_value' in suit_df.columns:
    suit_colors = {'C': 'tab:blue', 'D': 'tab:orange', 'H': 'tab:red', 'S': 'tab:green'}

    for suit, color in suit_colors.items():
        subset = suit_df[suit_df['trump_suit'] == suit]
        if len(subset) > 0:
            ax.scatter(subset['feat_trump_count'], subset['feat_hand_value'],
                      c=color, alpha=0.4, label=suit, s=20)

    ax.set_xlabel('Trump Count')
    ax.set_ylabel('Hand Value')
    ax.set_title(f'Trump Count vs Hand Value\n(Suit Contracts, n={len(suit_df):,})')
    ax.legend(title='Trump Suit')
    ax.grid(True, alpha=0.3)
else:
    ax.text(0.5, 0.5, 'No suit contract data', ha='center', va='center')
    ax.set_title('Trump Count vs Hand Value')

# ============================================================================
# Panel 2: High card count vs hand value (high/low, colored by contract)
# ============================================================================
ax = axes[0, 1]

if len(highlow_df) > 0 and 'feat_high_card_count' in highlow_df.columns and 'feat_hand_value' in highlow_df.columns:
    contract_colors = {'high': 'tab:green', 'low': 'tab:purple'}

    for ct, color in contract_colors.items():
        subset = highlow_df[highlow_df['contract_type'] == ct]
        if len(subset) > 0:
            ax.scatter(subset['feat_high_card_count'], subset['feat_hand_value'],
                      c=color, alpha=0.4, label=ct, s=20)

    ax.set_xlabel('High Card Count')
    ax.set_ylabel('Hand Value')
    ax.set_title(f'High Card Count vs Hand Value\n(High/Low Contracts, n={len(highlow_df):,})')
    ax.legend(title='Contract Type')
    ax.grid(True, alpha=0.3)
else:
    ax.text(0.5, 0.5, 'No high/low contract data', ha='center', va='center')
    ax.set_title('High Card Count vs Hand Value')

# ============================================================================
# Panel 3: Bowers vs hand value (suit contracts, colored by trump suit)
# ============================================================================
ax = axes[1, 0]

if len(suit_df) > 0 and 'feat_bowers' in suit_df.columns and 'feat_hand_value' in suit_df.columns:
    suit_colors = {'C': 'tab:blue', 'D': 'tab:orange', 'H': 'tab:red', 'S': 'tab:green'}

    for suit, color in suit_colors.items():
        subset = suit_df[suit_df['trump_suit'] == suit]
        if len(subset) > 0:
            # Add jitter to bowers (discrete values) for visibility
            jitter = np.random.normal(0, 0.05, len(subset))
            ax.scatter(subset['feat_bowers'] + jitter, subset['feat_hand_value'],
                      c=color, alpha=0.4, label=suit, s=20)

    ax.set_xlabel('Bowers (with jitter)')
    ax.set_ylabel('Hand Value')
    ax.set_title(f'Bowers vs Hand Value\n(Suit Contracts, n={len(suit_df):,})')
    ax.legend(title='Trump Suit')
    ax.grid(True, alpha=0.3)
else:
    ax.text(0.5, 0.5, 'No bower data', ha='center', va='center')
    ax.set_title('Bowers vs Hand Value')

# ============================================================================
# Panel 4: Offsuit aces vs hand value (all contracts, colored by contract type)
# ============================================================================
ax = axes[1, 1]

if 'feat_offsuit_aces' in df.columns and 'feat_hand_value' in df.columns:
    contract_colors = {'suit': 'tab:blue', 'high': 'tab:green', 'low': 'tab:purple'}

    for ct, color in contract_colors.items():
        if ct == 'suit':
            subset = df[df['contract_type'] == ct]
        else:
            subset = df[df['contract_type'] == ct]

        if len(subset) > 0:
            # Add jitter to offsuit_aces (discrete values) for visibility
            jitter = np.random.normal(0, 0.05, len(subset))
            ax.scatter(subset['feat_offsuit_aces'] + jitter, subset['feat_hand_value'],
                      c=color, alpha=0.3, label=ct, s=15)

    ax.set_xlabel('Offsuit Aces (with jitter)')
    ax.set_ylabel('Hand Value')
    ax.set_title(f'Offsuit Aces vs Hand Value\n(All Contracts, n={len(df):,})')
    ax.legend(title='Contract Type')
    ax.grid(True, alpha=0.3)
else:
    ax.text(0.5, 0.5, 'No offsuit ace data', ha='center', va='center')
    ax.set_title('Offsuit Aces vs Hand Value')

plt.tight_layout()
plt.show()

print("\n✅ Scatter plots completed")
print("\nExpected patterns:")
print("- Suit contracts: Positive correlation between trump_count/bowers and hand_value")
print("- High contracts: Positive correlation between high_card_count and hand_value")
print("- Low contracts: Negative correlation (or weak positive) with high_card_count")
print("- Similar patterns across trump suits (C, D, H, S) for suit contracts")

# %% [markdown]
# ---
# ## Section 7: Time/Batch Drift Analysis
#
# Check for drift over the course of data collection.

# %%
# ============================================================================
# SECTION 7.1: ROLLING MEAN BY CONTRACT TYPE
# ============================================================================

print("=" * 80)
print("SECTION 7.1: ROLLING MEAN ANALYSIS BY CONTRACT TYPE")
print("=" * 80)

# Split by contract type
suit_df = df[df['contract_type'] == 'suit'].copy()
highlow_df = df[df['contract_type'].isin(['high', 'low'])].copy()

# Create 3 subplots vertically stacked
fig, axes = plt.subplots(3, 1, figsize=(16, 12))

# ============================================================================
# Panel 1: Suit contracts by trump suit
# ============================================================================
ax = axes[0]

if len(suit_df) > 0 and 'feat_hand_value' in suit_df.columns:
    suit_colors = {'C': 'tab:blue', 'D': 'tab:orange', 'H': 'tab:red', 'S': 'tab:green'}

    for suit, color in suit_colors.items():
        subset = suit_df[suit_df['trump_suit'] == suit].reset_index(drop=True)
        if len(subset) > 0:
            rolling = subset['feat_hand_value'].rolling(window=ROLLING_WINDOW, min_periods=1).mean()
            ax.plot(rolling, color=color, label=suit, alpha=0.8, linewidth=2)

    ax.set_xlabel('Row Index (within suit contract subset)')
    ax.set_ylabel('Hand Value (Rolling Mean)')
    ax.set_title(f'Rolling Mean: Suit Contracts by Trump Suit\n(window={ROLLING_WINDOW})')
    ax.legend(title='Trump Suit', loc='best')
    ax.grid(True, alpha=0.3)

    # Add horizontal line at overall mean
    overall_mean = suit_df['feat_hand_value'].mean()
    ax.axhline(overall_mean, color='black', linestyle='--', alpha=0.5,
               label=f'Overall mean: {overall_mean:.2f}')
else:
    ax.text(0.5, 0.5, 'No suit contract data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Rolling Mean: Suit Contracts')

# ============================================================================
# Panel 2: High/low contracts by contract type
# ============================================================================
ax = axes[1]

if len(highlow_df) > 0 and 'feat_hand_value' in highlow_df.columns:
    contract_colors = {'high': 'tab:green', 'low': 'tab:purple'}

    for ct, color in contract_colors.items():
        subset = highlow_df[highlow_df['contract_type'] == ct].reset_index(drop=True)
        if len(subset) > 0:
            rolling = subset['feat_hand_value'].rolling(window=ROLLING_WINDOW, min_periods=1).mean()
            ax.plot(rolling, color=color, label=ct, alpha=0.8, linewidth=2)

    ax.set_xlabel('Row Index (within high/low contract subset)')
    ax.set_ylabel('Hand Value (Rolling Mean)')
    ax.set_title(f'Rolling Mean: High/Low Contracts\n(window={ROLLING_WINDOW})')
    ax.legend(title='Contract Type', loc='best')
    ax.grid(True, alpha=0.3)

    # Add horizontal line at overall mean
    overall_mean = highlow_df['feat_hand_value'].mean()
    ax.axhline(overall_mean, color='black', linestyle='--', alpha=0.5,
               label=f'Overall mean: {overall_mean:.2f}')
else:
    ax.text(0.5, 0.5, 'No high/low contract data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Rolling Mean: High/Low Contracts')

# ============================================================================
# Panel 3: All contracts (overall)
# ============================================================================
ax = axes[2]

if 'feat_hand_value' in df.columns:
    rolling = df['feat_hand_value'].rolling(window=ROLLING_WINDOW, min_periods=1).mean()
    ax.plot(rolling, color='tab:gray', alpha=0.8, linewidth=2)

    ax.set_xlabel('Row Index (all contracts)')
    ax.set_ylabel('Hand Value (Rolling Mean)')
    ax.set_title(f'Rolling Mean: All Contracts\n(window={ROLLING_WINDOW})')
    ax.grid(True, alpha=0.3)

    # Add horizontal line at overall mean
    overall_mean = df['feat_hand_value'].mean()
    ax.axhline(overall_mean, color='black', linestyle='--', alpha=0.5,
               label=f'Overall mean: {overall_mean:.2f}')
    ax.legend(loc='best')
else:
    ax.text(0.5, 0.5, 'No hand_value data', ha='center', va='center', transform=ax.transAxes)
    ax.set_title('Rolling Mean: All Contracts')

plt.tight_layout()
plt.show()

print("\n✅ Rolling mean analysis completed")
print("\nExpected: Flat rolling means (no upward/downward trends)")
print("         Similar patterns across all trump suits and contract types")

# %%
# ============================================================================
# SECTION 7.2: DECILE ANALYSIS + STATISTICAL TESTS
# ============================================================================

print("=" * 80)
print("SECTION 7.2: DECILE PROGRESSION ANALYSIS")
print("=" * 80)

from scipy.stats import f_oneway, linregress

# Create decile labels (0-9 for 10 deciles)
n = len(df)
decile_size = n // 10
df['decile'] = pd.Series((df.index // decile_size), index=df.index).clip(0, 9)

# Decile label mapping for display
decile_labels = {
    0: "0-10%", 1: "10-20%", 2: "20-30%", 3: "30-40%", 4: "40-50%",
    5: "50-60%", 6: "60-70%", 7: "70-80%", 8: "80-90%", 9: "90-100%"
}

# ============================================================================
# PART 1: SUIT CONTRACTS BY TRUMP SUIT
# ============================================================================

suit_df = df[df['contract_type'] == 'suit'].copy()

if len(suit_df) > 0 and 'feat_hand_value' in suit_df.columns:
    print("\n" + "=" * 80)
    print("SUIT CONTRACTS: Decile Progression by Trump Suit")
    print("=" * 80)

    # Create deciles within suit contract subset
    suit_df_indexed = suit_df.reset_index(drop=True)
    n_suit = len(suit_df_indexed)
    decile_size_suit = n_suit // 10
    suit_df['decile'] = pd.Series((suit_df_indexed.index // decile_size_suit), index=suit_df.index).clip(0, 9)

    # Compute mean hand_value for each (decile, trump_suit) pair
    suit_decile_stats = suit_df.groupby(['decile', 'trump_suit'])['feat_hand_value'].mean().unstack()

    # Add row labels
    suit_decile_stats.index = [decile_labels[i] for i in suit_decile_stats.index]

    print("\nMean hand_value by decile and trump suit:")
    display(suit_decile_stats)

    # ========================================================================
    # STATISTICAL TESTS: Linear regression for trend detection
    # ========================================================================

    print("\n" + "-" * 80)
    print("STATISTICAL VALIDATION: Drift Detection (Linear Regression)")
    print("-" * 80)
    print("H0: No monotonic trend across deciles (slope = 0)")
    print("Significance level: α = 0.05\n")

    failed_trumps = []

    for suit in ['C', 'D', 'H', 'S']:
        if suit not in suit_decile_stats.columns:
            continue

        deciles = range(10)
        means = suit_decile_stats[suit].values

        # Linear regression
        slope, intercept, r_value, p_value, std_err = linregress(deciles, means)

        # Validation gate
        status = "❌ FAIL" if p_value < 0.05 else "✅ PASS"

        print(f"  Trump {suit}:  slope={slope:+.4f}  p={p_value:.4f}  R²={r_value**2:.4f}  {status}")

        if p_value < 0.05:
            failed_trumps.append(suit)

    # Summary
    print("\n" + "-" * 80)
    if len(failed_trumps) == 0:
        print("✅ ALL TRUMPS PASSED: No significant drift detected")
    else:
        print(f"❌ {len(failed_trumps)} TRUMP(S) FAILED:")
        for suit in failed_trumps:
            print(f"   - Trump {suit}: Significant drift detected")
        print("\nThis indicates non-uniform data generation over time.")
    print("-" * 80)

    # Clean up
    suit_df.drop('decile', axis=1, inplace=True)

# ============================================================================
# PART 2: HIGH/LOW CONTRACTS BY CONTRACT TYPE
# ============================================================================

highlow_df = df[df['contract_type'].isin(['high', 'low'])].copy()

if len(highlow_df) > 0 and 'feat_hand_value' in highlow_df.columns:
    print("\n\n" + "=" * 80)
    print("HIGH/LOW CONTRACTS: Decile Progression by Contract Type")
    print("=" * 80)

    # Create deciles within high/low contract subset
    highlow_df_indexed = highlow_df.reset_index(drop=True)
    n_highlow = len(highlow_df_indexed)
    decile_size_highlow = n_highlow // 10
    highlow_df['decile'] = pd.Series((highlow_df_indexed.index // decile_size_highlow), index=highlow_df.index).clip(0, 9)

    # Compute mean hand_value for each (decile, contract_type) pair
    highlow_decile_stats = highlow_df.groupby(['decile', 'contract_type'])['feat_hand_value'].mean().unstack()

    # Add row labels
    highlow_decile_stats.index = [decile_labels[i] for i in highlow_decile_stats.index]

    print("\nMean hand_value by decile and contract type:")
    display(highlow_decile_stats)

    # ========================================================================
    # STATISTICAL TESTS: Linear regression for trend detection
    # ========================================================================

    print("\n" + "-" * 80)
    print("STATISTICAL VALIDATION: Drift Detection (Linear Regression)")
    print("-" * 80)
    print("H0: No monotonic trend across deciles (slope = 0)")
    print("Significance level: α = 0.05\n")

    failed_contracts = []

    for ct in ['high', 'low']:
        if ct not in highlow_decile_stats.columns:
            continue

        deciles = range(10)
        means = highlow_decile_stats[ct].values

        # Linear regression
        slope, intercept, r_value, p_value, std_err = linregress(deciles, means)

        # Validation gate
        status = "❌ FAIL" if p_value < 0.05 else "✅ PASS"

        print(f"  {ct.capitalize():5s}:  slope={slope:+.4f}  p={p_value:.4f}  R²={r_value**2:.4f}  {status}")

        if p_value < 0.05:
            failed_contracts.append(ct)

    # Summary
    print("\n" + "-" * 80)
    if len(failed_contracts) == 0:
        print("✅ ALL CONTRACT TYPES PASSED: No significant drift detected")
    else:
        print(f"❌ {len(failed_contracts)} CONTRACT TYPE(S) FAILED:")
        for ct in failed_contracts:
            print(f"   - {ct.capitalize()}: Significant drift detected")
        print("\nThis indicates non-uniform data generation over time.")
    print("-" * 80)

    # Clean up
    highlow_df.drop('decile', axis=1, inplace=True)

# ============================================================================
# PART 3: OVERALL DECILE PROGRESSION (ALL CONTRACTS)
# ============================================================================

if 'feat_hand_value' in df.columns:
    print("\n\n" + "=" * 80)
    print("OVERALL DECILE PROGRESSION (ALL CONTRACTS)")
    print("=" * 80)

    # Compute mean hand_value for each decile
    overall_decile_stats = df.groupby('decile')['feat_hand_value'].agg(['mean', 'std', 'count'])

    # Add row labels
    overall_decile_stats.index = [decile_labels[i] for i in overall_decile_stats.index]

    print("\nMean hand_value by decile (all contracts):")
    display(overall_decile_stats)

    # ========================================================================
    # STATISTICAL TESTS
    # ========================================================================

    print("\n" + "-" * 80)
    print("STATISTICAL VALIDATION: Overall Drift Detection")
    print("-" * 80)

    # Linear regression
    deciles = range(10)
    means = df.groupby('decile')['feat_hand_value'].mean().values
    slope, intercept, r_value, p_value, std_err = linregress(deciles, means)

    print("Linear Regression Test:")
    print("H0: No monotonic trend across deciles (slope = 0)")
    print("Significance level: α = 0.05\n")
    print(f"  Slope: {slope:+.4f}")
    print(f"  p-value: {p_value:.4f}")
    print(f"  R²: {r_value**2:.4f}")

    status = "❌ FAIL" if p_value < 0.05 else "✅ PASS"
    print(f"  Status: {status}")

    if p_value < 0.05:
        print("\n  ⚠️  WARNING: Significant drift detected in overall data")
        print("      Investigate data generation process for batch effects")

    # ANOVA test
    print("\n" + "-" * 80)
    print("ANOVA Test:")
    print("H0: All decile means are equal")
    print("Significance level: α = 0.05\n")

    # Extract values by decile
    decile_groups = [df[df['decile'] == d]['feat_hand_value'].values for d in range(10)]
    f_stat, p_value_anova = f_oneway(*decile_groups)

    print(f"  F-statistic: {f_stat:.4f}")
    print(f"  p-value: {p_value_anova:.4f}")

    status_anova = "❌ FAIL" if p_value_anova < 0.05 else "✅ PASS"
    print(f"  Status: {status_anova}")

    if p_value_anova < 0.05:
        print("\n  ⚠️  WARNING: Decile means differ significantly")

    print("-" * 80)

# Clean up temporary column
df.drop('decile', axis=1, inplace=True)

print("\n✅ Decile analysis completed")

# %%
# ============================================================================
# SECTION 7.3: DECILE BOXPLOTS BY CONTRACT TYPE
# ============================================================================

print("=" * 80)
print("SECTION 7.3: DECILE BOXPLOTS BY CONTRACT TYPE")
print("=" * 80)

# Create decile labels
n = len(df)
decile_size = n // 10
df['decile'] = pd.Series((df.index // decile_size), index=df.index).clip(0, 9)

# Split by contract type
suit_df = df[df['contract_type'] == 'suit'].copy()
highlow_df = df[df['contract_type'].isin(['high', 'low'])].copy()

# ============================================================================
# Create 2×3 grid: Row 1 = 4 suit plots (C,D,H,S), Row 2 = 2 h/l plots + overall
# ============================================================================

fig, axes = plt.subplots(2, 3, figsize=(18, 12))

# ============================================================================
# Row 1, Col 0-2: Suit contracts by trump suit (C, D, H in row 1)
# Row 2, Col 0: Suit contract trump S
# ============================================================================

if len(suit_df) > 0 and 'feat_hand_value' in suit_df.columns:
    # Create deciles within suit contract subset
    suit_df_indexed = suit_df.reset_index(drop=True)
    n_suit = len(suit_df_indexed)
    decile_size_suit = n_suit // 10
    suit_df['decile'] = pd.Series((suit_df_indexed.index // decile_size_suit), index=suit_df.index).clip(0, 9)

    suit_colors = {'C': 'tab:blue', 'D': 'tab:orange', 'H': 'tab:red', 'S': 'tab:green'}
    suit_positions = {'C': (0, 0), 'D': (0, 1), 'H': (0, 2), 'S': (1, 0)}

    for suit, color in suit_colors.items():
        subset = suit_df[suit_df['trump_suit'] == suit]
        if len(subset) > 0:
            row, col = suit_positions[suit]
            ax = axes[row, col]

            try:
                import seaborn as sns
                sns.boxplot(data=subset, x='decile', y='feat_hand_value', ax=ax, color=color)
            except ImportError:
                subset.boxplot(column='feat_hand_value', by='decile', ax=ax)

            ax.set_title(f'Suit: Trump {suit}\n(n={len(subset):,})')
            ax.set_xlabel('Decile')
            ax.set_ylabel('Hand Value')
            ax.set_xticklabels(['0-10%', '10-20%', '20-30%', '30-40%', '40-50%',
                                '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'],
                               rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
        else:
            row, col = suit_positions[suit]
            ax = axes[row, col]
            ax.text(0.5, 0.5, f'No trump {suit} data', ha='center', va='center')
            ax.set_title(f'Suit: Trump {suit}')

    # Clean up
    suit_df.drop('decile', axis=1, inplace=True)
else:
    for suit, (row, col) in [('C', (0, 0)), ('D', (0, 1)), ('H', (0, 2)), ('S', (1, 0))]:
        ax = axes[row, col]
        ax.text(0.5, 0.5, 'No suit contract data', ha='center', va='center')
        ax.set_title(f'Suit: Trump {suit}')

# ============================================================================
# Row 2, Col 1-2: High/low contracts
# ============================================================================

if len(highlow_df) > 0 and 'feat_hand_value' in highlow_df.columns:
    # Create deciles within high/low contract subset
    highlow_df_indexed = highlow_df.reset_index(drop=True)
    n_highlow = len(highlow_df_indexed)
    decile_size_highlow = n_highlow // 10
    highlow_df['decile'] = pd.Series((highlow_df_indexed.index // decile_size_highlow), index=highlow_df.index).clip(0, 9)

    contract_colors = {'high': 'tab:green', 'low': 'tab:purple'}
    contract_positions = {'high': (1, 1), 'low': (1, 2)}

    for ct, color in contract_colors.items():
        subset = highlow_df[highlow_df['contract_type'] == ct]
        if len(subset) > 0:
            row, col = contract_positions[ct]
            ax = axes[row, col]

            try:
                import seaborn as sns
                sns.boxplot(data=subset, x='decile', y='feat_hand_value', ax=ax, color=color)
            except ImportError:
                subset.boxplot(column='feat_hand_value', by='decile', ax=ax)

            ax.set_title(f'{ct.capitalize()} Contracts\n(n={len(subset):,})')
            ax.set_xlabel('Decile')
            ax.set_ylabel('Hand Value')
            ax.set_xticklabels(['0-10%', '10-20%', '20-30%', '30-40%', '40-50%',
                                '50-60%', '60-70%', '70-80%', '80-90%', '90-100%'],
                               rotation=45, ha='right')
            ax.grid(True, alpha=0.3)
        else:
            row, col = contract_positions[ct]
            ax = axes[row, col]
            ax.text(0.5, 0.5, f'No {ct} contract data', ha='center', va='center')
            ax.set_title(f'{ct.capitalize()} Contracts')

    # Clean up
    highlow_df.drop('decile', axis=1, inplace=True)
else:
    for ct, (row, col) in [('high', (1, 1)), ('low', (1, 2))]:
        ax = axes[row, col]
        ax.text(0.5, 0.5, 'No high/low contract data', ha='center', va='center')
        ax.set_title(f'{ct.capitalize()} Contracts')

plt.tight_layout()
plt.show()

# Clean up temporary column
df.drop('decile', axis=1, inplace=True)

print("\n✅ Decile boxplot analysis completed")
print("\nExpected: Consistent distributions across all 10 deciles")
print("         No systematic upward/downward shift in medians or IQRs")
print("         Similar patterns across trump suits and contract types")

# %% [markdown]
# ---
# ## Section 8: Summary
#
# Final health status and key findings.

# %%
print("=" * 60)
print("FINAL HEALTH SUMMARY")
print("=" * 60)

summary = scorecard.summary()
if summary['FAIL'] == 0 and summary['WARN'] == 0:
    print("\n✅ ALL CHECKS PASSED - Dataset looks healthy!")
elif summary['FAIL'] == 0:
    print(f"\n⚠️  {summary['WARN']} WARNING(S)")
else:
    print(f"\n❌ {summary['FAIL']} FAILURE(S)")

# Show compact issue list for quick reference
if summary['FAIL'] > 0 or summary['WARN'] > 0:
    print("\n" + display_issues(scorecard))

print(f"\n  Passed: {summary['PASS']}")
print(f"  Warnings: {summary['WARN']}")
print(f"  Failures: {summary['FAIL']}")

print("\n" + "=" * 60)
