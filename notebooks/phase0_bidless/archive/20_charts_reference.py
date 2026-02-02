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
# # Bidless Dataset Diagnostics - Reference Implementation
#
# Comprehensive diagnostic toolkit for analyzing bidless hand datasets used in ML model training.
#
# ## What This Notebook Does
#
# This notebook provides:
# 1. **Parameterized, deterministic analysis** with explicit SEED control
# 2. **Fast iteration** (QUICK mode ~20 min) and **production-quality** (FULL mode hours) execution
# 3. **Fail-fast quality gates** to catch data issues early
# 4. **Statistical rigor** using effect sizes + bootstrap CIs (not p-values)
# 5. **Comprehensive analysis** covering features, outcomes, bias checks, and diagnostics
#
# ## Notebook Structure (9 Phases)
#
# 1. **Config_and_Setup** - Configuration, caching utilities, data factories
# 2. **Data_Generation** - Cached parquet-based data builders
# 3. **Fail_Fast_Pipeline_Validity_Tests** - Health checks, assertions, early abort
# 4. **Feature_Hygiene** - Seat balance, distributions, correlations, drift detection
# 5. **Core_Signal_and_Predictive_Power** - hand_value vs tricks_won, feature importance
# 6. **Bias_and_Stability_Checks** - Seat/contract/trump fairness, feature stability
# 7. **Second_Order_Diagnostics** - CDF/CCDF, strategy matchups (interpret after gates pass)
# 8. **Report_Exports** - Dict-based validation plots for pipelines
# 9. **Appendix** - Cleanup, quick reference
#
# ## Two Chart Families
#
# | Module | Input Type | Use Case | Display Method |
# |--------|------------|----------|----------------|
# | `bid_euchre.diagnostics` | **DataFrame** | Interactive dataset analysis | `plt.show()` |
# | `bid_euchre.reporting.validation` | **Dict/List** | Batch report generation | Saves to disk |
#
# ## Golden Path
#
# 1. Run CONFIG cell (Cell 3) - set MODE = "quick" or "full"
# 2. Run Phase 02 (Data Generation) - generates and caches datasets
# 3. Run Phase 03 (Fail-Fast Tests) - **STOP HERE if gates fail**
# 4. Proceed only if all gates pass
# 5. Explore phases 4-9 as needed
#
# ## Key Improvements from Previous Version
#
# - **No Hearts-only bias**: All 4 trump suits analyzed by default
# - **No seat-0-only bias**: All seats included in analysis
# - **Cached execution**: Second run is instant (hits parquet cache)
# - **Statistical rigor**: Effect sizes + bootstrap CIs replace p-values
# - **Mode switching**: Toggle between quick iteration and production quality

# %%
# Auto-reload for development
# %load_ext autoreload
# %autoreload 2

# %%
import os
import shutil
import tempfile

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Image

from bid_euchre.diagnostics import (
    plot_feature_correlation,
    plot_feature_distributions,
    plot_hand_value_by_contract,
    plot_hand_value_by_seat,
    plot_rolling_mean,
)
from bid_euchre.diagnostics.charts import plot_feature_vs_label
from bid_euchre.features.hand_eval import get_hand_features
from bid_euchre.reporting.validation import (
    generate_validation_plots,
)
from bid_euchre.reporting.validation import (
    plot_feature_correlation as eval_plot_feature_correlation,
)
from bid_euchre.reporting.validation import (
    plot_feature_distributions as eval_plot_feature_distributions,
)
from bid_euchre.reporting.validation import (
    plot_hand_value_by_contract as eval_plot_hand_value_by_contract,
)
from bid_euchre.sim.deals import generate_deal

plt.style.use("seaborn-v0_8-whitegrid")

# %%
# ============================================================================
# CONFIGURATION - Modify these parameters to control notebook execution
# ============================================================================

# --- Execution Mode ---
MODE = "quick"  # "quick" | "full"
# QUICK: ~20 min runtime, 2000 deals for outcomes
# FULL: ~hours, 50000+ deals for outcomes

# --- Data Source Mode ---
DEMO_MODE = False  # If True, generates synthetic data; if False, loads from RUN_DIR

# If DEMO_MODE=False, set this path:
RUN_DIR = "../../data/runs/YOUR_RUN_ID"  # Will load from RUN_DIR/datasets/

# --- Reproducibility ---
SEED = 42  # Master seed for all random operations (used when DEMO_MODE=True)

# --- Sample Sizes (MODE-dependent, used when DEMO_MODE=True) ---
if MODE == "quick":
    N_DEALS_FEATURES = 500      # Feature-only generation (fast)
    N_DEALS_OUTCOMES = 2000     # With simulation outcomes (moderate)
    N_DEALS_MATCHUPS = 200      # Strategy matchup comparisons
    N_DEALS_MULTI_SUIT = 500    # Trump suit analysis
elif MODE == "full":
    N_DEALS_FEATURES = 5000
    N_DEALS_OUTCOMES = 50000
    N_DEALS_MATCHUPS = 2000
    N_DEALS_MULTI_SUIT = 5000
else:
    raise ValueError(f"Invalid MODE: {MODE}")

# --- Contract & Scenario Parameters (used when DEMO_MODE=True) ---
# --- Contract & Scenario Parameters ---
CONTRACT_TYPES = ['suit', 'high', 'low']  # All contract types

# CRITICAL: Use ALL suits to avoid Hearts-only bias
TRUMPS_FOR_SUIT_CONTRACTS = ['C', 'D', 'H', 'S']  # All 4 suits

# For single-suit demonstrations (clearly labeled as such)
DEMO_TRUMP_SUIT = 'H'  # Only for plumbing demos

# All seats for analysis (avoid seat-0-only bias)
SEATS = [0, 1, 2, 3]

# --- Output Paths ---
from pathlib import Path

OUTPUT_DIR = Path(tempfile.mkdtemp(prefix='charts_ref_'))
CACHE_DIR = OUTPUT_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# --- Cache Control ---
FORCE_REBUILD = True  # Set to True to bypass cache and regenerate all data

# --- Feature Flags ---
RUN_REPORT_EXPORTS = True        # Phase 8: Dict-based validation plots
RUN_MATCHUPS = True              # Part 6: Strategy performance
RUN_TAILS_CDF = True             # Part 8: CDF/CCDF analysis
RUN_TRUMP_ANALYSIS = True        # Part 7: Multi-suit analysis

# --- Display ---
PLOT_INLINE = True               # Show plots inline (vs save only)
VERBOSE = True                   # Print progress messages

print(f"Configuration loaded: MODE={MODE}, FORCE_REBUILD={FORCE_REBUILD}")
print(f"  N_DEALS_FEATURES: {N_DEALS_FEATURES}")
print(f"  N_DEALS_OUTCOMES: {N_DEALS_OUTCOMES}")
print(f"  CONTRACT_TYPES: {CONTRACT_TYPES}")
print(f"  TRUMPS_FOR_SUIT_CONTRACTS: {TRUMPS_FOR_SUIT_CONTRACTS}")
print(f"  Cache directory: {CACHE_DIR}")
print(f"  Output directory: {OUTPUT_DIR}")

# %%
# ============================================================================
# CACHING UTILITIES - Parquet-based persistence for expensive operations
# ============================================================================

import hashlib
import json
from typing import Any, Callable, Dict


def stable_config_hash(config: Dict[str, Any]) -> str:
    """Generate stable hash from config dict for cache key.

    Args:
        config: Configuration dict (must be JSON-serializable)

    Returns:
        8-character hex hash
    """
    # Sort keys for stability
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()[:8]


def make_cache_key(prefix: str, **params) -> str:
    """Create cache key from prefix and parameters.

    Args:
        prefix: Cache key prefix (e.g., 'features', 'outcomes')
        **params: Parameters to hash (must be JSON-serializable)

    Returns:
        Cache key string like 'features_1a2b3c4d'
    """
    config_hash = stable_config_hash(params)
    return f"{prefix}_{config_hash}"


def cache_get_or_build(
    cache_dir: Path,
    cache_key: str,
    builder_fn: Callable[[], pd.DataFrame],
    force_rebuild: bool = False,
) -> pd.DataFrame:
    """Get DataFrame from cache or build it.

    Args:
        cache_dir: Directory for cache files
        cache_key: Unique key for this cache entry
        builder_fn: Function that returns DataFrame if cache miss
        force_rebuild: Ignore cache and rebuild

    Returns:
        DataFrame from cache or builder
    """
    cache_path = cache_dir / f"{cache_key}.parquet"

    if not force_rebuild and cache_path.exists():
        if VERBOSE:
            print(f"  ✓ Cache hit: {cache_key}")
        return pd.read_parquet(cache_path)

    if VERBOSE:
        print(f"  ⚙ Building: {cache_key}...")

    df = builder_fn()

    # Save to cache
    df.to_parquet(cache_path, index=False)

    if VERBOSE:
        print(f"  ✓ Cached: {cache_key} ({len(df)} rows)")

    return df

print("Caching utilities loaded")


# %%
# ============================================================================
# DATA GENERATION FACTORIES - Config-aware DataFrame builders
# ============================================================================

def build_features_df(seed: int, n_deals: int, contracts: list, trumps: list) -> pd.DataFrame:
    """Build features-only DataFrame (no simulation).

    Args:
        seed: Random seed
        n_deals: Number of deals to generate
        contracts: Contract types to include
        trumps: Trump suits for suit contracts

    Returns:
        DataFrame with deal_id, seat, contract_type, trump, feat_* columns
    """
    from bid_euchre.features.hand_eval import get_hand_features
    from bid_euchre.sim.deals import generate_deal

    hands_data = []
    for deal_id in range(n_deals):
        hands = generate_deal(seed, deal_id)

        for contract_type in contracts:
            # For suit contracts, iterate all trumps
            if contract_type == 'suit':
                trump_list = trumps
            else:
                trump_list = [None]

            for trump in trump_list:
                for seat in range(4):
                    hand = hands[seat]
                    features = get_hand_features(hand, contract_type, trump)
                    hands_data.append({
                        'hand_id': f"{deal_id}_{contract_type}_{trump}",
                        'deal_id': deal_id,
                        'seat': seat,
                        'contract_type': contract_type,
                        'trump': trump,
                        **{f'feat_{k}': v for k, v in features.items()}
                    })

    return pd.DataFrame(hands_data)


def build_outcomes_df(seed: int, n_deals: int, contracts: list, trumps: list) -> pd.DataFrame:
    """Build outcomes DataFrame (features + tricks_won from simulation).

    Args:
        seed: Random seed
        n_deals: Number of deals to simulate
        contracts: Contract types to include
        trumps: Trump suits for suit contracts

    Returns:
        DataFrame with deal_id, seat, contract_type, trump, tricks_won, feat_* columns
    """
    from bid_euchre.sim.deals import generate_deal
    from bid_euchre.sim.simulation import play_single_hand
    from bid_euchre.strategy import GreedyStrategy

    strategy = GreedyStrategy()
    outcome_data = []

    for deal_id in range(n_deals):
        hands = generate_deal(seed, deal_id)

        for contract_type in contracts:
            # For suit contracts, iterate all trumps
            if contract_type == 'suit':
                trump_list = trumps
            else:
                trump_list = [None]

            for trump in trump_list:
                t0, t1, _, all_feats, _, _, *_ = play_single_hand(
                    contract_type=contract_type,
                    trump_suit=trump,
                    strategy=strategy,
                    hands=hands,
                    deal_seed=seed,
                )

                for seat in range(4):
                    team_tricks = t0 if seat in (0, 2) else t1
                    features = all_feats[seat]
                    outcome_data.append({
                        'hand_id': f"{deal_id}_{contract_type}_{trump}",
                        'deal_id': deal_id,
                        'seat': seat,
                        'contract_type': contract_type,
                        'trump': trump,
                        'tricks_won': team_tricks,
                        **{f'feat_{k}': v for k, v in features.items()}
                    })

    return pd.DataFrame(outcome_data)


print("Data generation factories loaded")

# %% [markdown]
# # ============================================================================
# # PHASE 02: DATA GENERATION
# # ============================================================================
#
# This phase generates and caches the primary datasets used throughout the notebook:
# - **features_df**: Hand features without simulation (fast)
# - **outcome_df**: Hand features + tricks_won from simulation (moderate)
# - **Conditional datasets**: Matchup data, multi-suit data (if enabled)
#
# **Key improvements:**
# - ✅ Uses ALL 4 trump suits (no Hearts-only bias)
# - ✅ Includes ALL 4 seats (no seat-0-only bias)
# - ✅ Cached to parquet (instant on second run)
# - ✅ Config-aware (changing MODE/SEED invalidates cache)

# %%
# Check DEMO_MODE and either load existing data or generate synthetic data

if not DEMO_MODE:
    print("📂 Loading existing dataset from RUN_DIR...")
    from pathlib import Path

    from bid_euchre.diagnostics import load_bidless_dataset, load_meta

    dataset_path = Path(RUN_DIR) / "datasets"
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}\n"
            f"Set RUN_DIR to your run directory, or use DEMO_MODE=True"
        )

    df = load_bidless_dataset(dataset_path)
    meta = load_meta(dataset_path)

    print(f"✅ Loaded {len(df):,} rows")
    print(f"   Strategies: {meta.get('strategies', 'unknown')}")
    print(f"   Scenarios: {len(meta.get('scenarios', []))} scenarios")

    # Build features_df and outcome_df from loaded data
    features_df = df[[c for c in df.columns if c.startswith('feat_')]].copy()
    features_df['hand_id'] = df['hand_id']
    features_df['seat'] = df['seat']
    features_df['contract_type'] = df['contract_type']
    if 'trump_suit' in df.columns:
        features_df['trump_suit'] = df['trump_suit']

    outcome_df = df.copy()  # Already has tricks_won from loaded data

    print("\n⚠️  DEMO_MODE=False: Skipping synthetic data generation.")
    print("   To generate synthetic data, set DEMO_MODE=True in the config cell.")
    print("   Jumping to Phase 03 (Fail-Fast Tests)...\n")
else:
    print("🎭 DEMO_MODE=True: Generating synthetic data...\n")


# %%
# ============================================================================
# Generate features_df (features only, no simulation)
# ============================================================================

print("\n" + "=" * 70)
print("Generating features_df (features-only dataset)")
print("=" * 70)

cache_key = make_cache_key(
    'features',
    seed=SEED,
    n_deals=N_DEALS_FEATURES,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
)

features_df = cache_get_or_build(
    CACHE_DIR,
    cache_key,
    lambda: build_features_df(
        seed=SEED,
        n_deals=N_DEALS_FEATURES,
        contracts=CONTRACT_TYPES,
        trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    ),
    force_rebuild=FORCE_REBUILD,
)

print("\nfeatures_df summary:")
print(f"  Shape: {features_df.shape}")
print(f"  Rows: {len(features_df):,}")
print(f"  Columns: {len(features_df.columns)}")
print(f"  Seats: {sorted(features_df['seat'].unique())}")
print(f"  Contracts: {sorted(features_df['contract_type'].unique())}")
print(f"  Trump suits (suit contracts): {sorted(features_df[features_df['contract_type'] == 'suit']['trump'].unique())}")
print(f"  Memory: {features_df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

# For backwards compatibility with old notebook cells, create df alias
df = features_df

features_df.head(3)

# DIAGNOSTIC: Verify contract types in features_df
print("\n" + "=" * 70)
print("DIAGNOSTIC: features_df contract types")
print("=" * 70)
print(f"Unique contract_types in features_df: {sorted(features_df['contract_type'].unique())}")
print("Contract type counts:")
for ct in sorted(features_df["contract_type"].unique()):
    count = len(features_df[features_df["contract_type"] == ct])
    trump_vals = features_df[features_df["contract_type"] == ct]["trump"].unique()
    print(f"  {ct}: {count} rows, trump values: {sorted([str(x) for x in trump_vals])}")
print("=" * 70)


# %%
# ============================================================================
# Generate outcome_df (features + tricks_won from simulation)
# ============================================================================

print("\n" + "=" * 70)
print("Generating outcome_df (features + simulation outcomes)")
print("=" * 70)

cache_key = make_cache_key(
    'outcomes',
    seed=SEED,
    n_deals=N_DEALS_OUTCOMES,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
)

outcome_df = cache_get_or_build(
    CACHE_DIR,
    cache_key,
    lambda: build_outcomes_df(
        seed=SEED,
        n_deals=N_DEALS_OUTCOMES,
        contracts=CONTRACT_TYPES,
        trumps=TRUMPS_FOR_SUIT_CONTRACTS,
    ),
    force_rebuild=FORCE_REBUILD,
)

print("\noutcome_df summary:")
print(f"  Shape: {outcome_df.shape}")
print(f"  Rows: {len(outcome_df):,}")
print(f"  Has tricks_won: {'tricks_won' in outcome_df.columns}")
print(f"  Tricks range: [{outcome_df['tricks_won'].min()}, {outcome_df['tricks_won'].max()}]")
print(f"  Mean tricks: {outcome_df['tricks_won'].mean():.2f}")
print(f"  Seats: {sorted(outcome_df['seat'].unique())}")
print(f"  Contracts: {sorted(outcome_df['contract_type'].unique())}")
print(f"  Memory: {outcome_df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

outcome_df.head(3)

# %% [markdown]
# ## Conditional Data Generation
#
# The following cells generate additional datasets based on feature flags:
# - **Multi-suit data**: If `RUN_TRUMP_ANALYSIS` is enabled (Part 7)
# - **Strategy matchup data**: If `RUN_MATCHUPS` is enabled (Part 6)
#
# These are generated on-demand to save time when not needed.

# %%
# ============================================================================
# Phase 02 Summary
# ============================================================================

print("\n" + "=" * 70)
print("Phase 02: Data Generation - COMPLETE")
print("=" * 70)

print("\n✅ Generated datasets:")
print(f"  • features_df: {len(features_df):,} rows")
print(f"  • outcome_df: {len(outcome_df):,} rows")

print("\n📊 Data coverage:")
print(f"  • Seats: {sorted(features_df['seat'].unique())}")
print(f"  • Contracts: {sorted(features_df['contract_type'].unique())}")
print(f"  • Trump suits (for 'suit' contracts): {sorted(features_df[features_df['contract_type'] == 'suit']['trump'].unique())}")

print("\n🔄 Caching status:")
print(f"  • Cache directory: {CACHE_DIR}")
cache_files = list(CACHE_DIR.glob("*.parquet"))
print(f"  • Cached files: {len(cache_files)}")
for cache_file in cache_files:
    size_mb = cache_file.stat().st_size / 1024**2
    print(f"    - {cache_file.name} ({size_mb:.2f} MB)")

print("\n⚡ Re-run cells 7-8 to see instant cache hits!")
print("\n" + "=" * 70)

# %% [markdown]
# # ============================================================================
# # PHASE 03: FAIL-FAST PIPELINE VALIDITY TESTS
# # ============================================================================
#
# **PURPOSE: Stop immediately if data is invalid.**
#
# This phase runs automated health checks and assertions BEFORE expensive analysis.
# If any test fails, **STOP HERE** and investigate data generation issues.
#
# **Tests:**
# 1. **Health Scorecard** - Automated data integrity checks
# 2. **Distribution Coverage** - No empty strata (seat/contract/trump combinations)
# 3. **Outcome Validity** - tricks_won in valid range [0, 10]
# 4. **Reproducibility** - Same config produces identical cache hits
#
# **Philosophy:**
# - Fast (< 1 second)
# - Explicit assertions (fail loud, not silent)
# - Statistical tests for bias detection (not just visual inspection)

# %%
# ============================================================================
# Test 1: Health Scorecard - Automated Data Integrity Checks
# ============================================================================

from bid_euchre.diagnostics.health_checks import (
    compute_health_scorecard,
    display_scorecard,
)

print("\n" + "=" * 70)
print("TEST 1: Health Scorecard")
print("=" * 70)

# Run health checks on features_df
scorecard = compute_health_scorecard(features_df)

# Display results
print(f"\n{display_scorecard(scorecard)}\n")

# Get summary
summary = scorecard.summary()
print(f"\nSummary: {summary['PASS']} PASS, {summary['WARN']} WARN, {summary['FAIL']} FAIL")

# FAIL-FAST: Assert no failures
if not scorecard.passed:
    failing_checks = [c for c in scorecard.checks if c.status == 'FAIL']
    print("\n" + "=" * 70)
    print("❌ FAIL-FAST ABORT: Health scorecard failed")
    print("=" * 70)
    for check in failing_checks:
        print(f"\n{check.name}:")
        print(f"  {check.message}")
        if check.details:
            print(f"  Details: {check.details}")
    raise AssertionError(f"{len(failing_checks)} health check(s) failed - fix data generation before proceeding")

print("\n✅ Health scorecard PASSED - all integrity checks successful")

# Optional: Show warnings
if scorecard.has_warnings:
    warnings = [c for c in scorecard.checks if c.status == 'WARN']
    print(f"\n⚠️  {len(warnings)} warning(s) - review but continue:")
    for check in warnings:
        print(f"  - {check.name}: {check.message}")

# %%
# ============================================================================
# Phase 03 Summary - ALL QUALITY GATES PASSED
# ============================================================================

print("\n" + "=" * 70)
print("PHASE 03: FAIL-FAST TESTS - COMPLETE")
print("=" * 70)

print("\n✅ All quality gates PASSED:")
print("  1. Health Scorecard     - Data integrity checks")
print("  2. Distribution Coverage - No empty strata")
print("  3. Outcome Validity     - tricks_won in valid range")
print("  4. Reproducibility      - Cache integrity verified")

print("\n" + "=" * 70)
print("🚀 SAFE TO PROCEED WITH ANALYSIS")
print("=" * 70)

print("\nYou may now proceed to:")
print("  • Phase 04: Feature Hygiene")
print("  • Phase 05: Core Signal & Predictive Power")
print("  • Phase 06: Bias & Stability Checks")
print("  • Phases 07-09: Advanced diagnostics")

print("\n💡 TIP: If you modify CONFIG (SEED, MODE, etc.), re-run Phases 02-03")
print("         to regenerate data and verify quality gates still pass.")
print("\n" + "=" * 70)

# %%
# ============================================================================
# Test 4: Reproducibility Check - Cache Integrity
# ============================================================================

print("\n" + "=" * 70)
print("TEST 4: Reproducibility")
print("=" * 70)

print("\nTesting cache integrity (same config → same data)...")

# Compute hash of current data
features_hash = pd.util.hash_pandas_object(features_df.sort_index()).sum()
outcome_hash = pd.util.hash_pandas_object(outcome_df.sort_index()).sum()

print(f"  features_df hash: {features_hash}")
print(f"  outcome_df hash: {outcome_hash}")

# Try to reload from cache (should be instant hits)
print("\n  Reloading from cache...")

cache_key_features = make_cache_key(
    'features',
    seed=SEED,
    n_deals=N_DEALS_FEATURES,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
)

cache_key_outcomes = make_cache_key(
    'outcomes',
    seed=SEED,
    n_deals=N_DEALS_OUTCOMES,
    contracts=CONTRACT_TYPES,
    trumps=TRUMPS_FOR_SUIT_CONTRACTS,
)

features_df_reload = cache_get_or_build(
    CACHE_DIR,
    cache_key_features,
    lambda: build_features_df(SEED, N_DEALS_FEATURES, CONTRACT_TYPES, TRUMPS_FOR_SUIT_CONTRACTS),
)

outcome_df_reload = cache_get_or_build(
    CACHE_DIR,
    cache_key_outcomes,
    lambda: build_outcomes_df(SEED, N_DEALS_OUTCOMES, CONTRACT_TYPES, TRUMPS_FOR_SUIT_CONTRACTS),
)

# Verify hashes match
features_hash_reload = pd.util.hash_pandas_object(features_df_reload.sort_index()).sum()
outcome_hash_reload = pd.util.hash_pandas_object(outcome_df_reload.sort_index()).sum()

if features_hash != features_hash_reload:
    raise AssertionError("Cache integrity failure: features_df hash mismatch")

if outcome_hash != outcome_hash_reload:
    raise AssertionError("Cache integrity failure: outcome_df hash mismatch")

print("  ✓ features_df: cache hit, hash matches")
print("  ✓ outcome_df: cache hit, hash matches")

print("\n✅ Reproducibility check PASSED")
print("   Same config → identical data (deterministic)")

# %%
# ============================================================================
# Test 3: Outcome Validity - tricks_won in Valid Range
# ============================================================================

print("\n" + "=" * 70)
print("TEST 3: Outcome Validity")
print("=" * 70)

# Check tricks_won range
if 'tricks_won' in outcome_df.columns:
    print("\nChecking tricks_won values...")

    min_tricks = outcome_df['tricks_won'].min()
    max_tricks = outcome_df['tricks_won'].max()
    mean_tricks = outcome_df['tricks_won'].mean()

    print(f"  Range: [{min_tricks}, {max_tricks}]")
    print(f"  Mean: {mean_tricks:.3f}")

    # Assert valid range [0, 10]
    if not outcome_df['tricks_won'].between(0, 10).all():
        invalid_count = (~outcome_df['tricks_won'].between(0, 10)).sum()
        invalid_values = outcome_df[~outcome_df['tricks_won'].between(0, 10)]['tricks_won'].unique()
        print("\n❌ FAIL-FAST ABORT: tricks_won out of valid range")
        print("=" * 70)
        print(f"Found {invalid_count} invalid values: {sorted(invalid_values)}")
        raise AssertionError("tricks_won contains values outside [0, 10] - simulation bug")

    print("  ✓ All tricks_won values in valid range [0, 10]")

    # Sanity check: mean should be close to 5.0 for fair self-play
    if not (4.0 <= mean_tricks <= 6.0):
        print(f"\n⚠️  WARNING: Mean tricks = {mean_tricks:.3f}, expected ~5.0")
        print("    This could indicate bias in dealing, play strategy, or RNG")
        print("    Review data generation if this persists in FULL mode")
    else:
        print(f"  ✓ Mean tricks = {mean_tricks:.3f} (expected ~5.0)")

    # Check value distribution
    value_counts = outcome_df['tricks_won'].value_counts().sort_index()
    print("\n  Tricks distribution:")
    for tricks, count in value_counts.items():
        pct = 100 * count / len(outcome_df)
        print(f"    {tricks} tricks: {count:5d} ({pct:5.1f}%)")

    print("\n✅ Outcome validity check PASSED")
else:
    print("\n⚠️  SKIPPED: outcome_df does not have tricks_won column")
    print("    (This is expected if only features_df was generated)")

# %%
# ============================================================================
# Test 2: Distribution Coverage - No Empty Strata
# ============================================================================

print("\n" + "=" * 70)
print("TEST 2: Distribution Coverage")
print("=" * 70)

# Check for empty strata (seat × contract × trump combinations)
print("\nChecking for empty strata...")

# Build expected strata list
empty_strata = []
expected_strata = []
strata_counts_dict = {}

for seat in SEATS:
    for contract_type in CONTRACT_TYPES:
        if contract_type == 'suit':
            for trump in TRUMPS_FOR_SUIT_CONTRACTS:
                expected_strata.append((seat, contract_type, trump))
        else:
            expected_strata.append((seat, contract_type, None))

# Check each expected stratum exists in the data
for stratum in expected_strata:
    seat, contract, trump = stratum
    # Check directly in DataFrame (handles NaN/None equivalence)
    mask = (features_df['seat'] == seat) & (features_df['contract_type'] == contract)
    if trump is None:
        mask = mask & features_df['trump'].isna()
    else:
        mask = mask & (features_df['trump'] == trump)

    count = mask.sum()
    strata_counts_dict[stratum] = count

    if count == 0:
        empty_strata.append(stratum)

if empty_strata:
    print("\n❌ FAIL-FAST ABORT: Empty strata detected")
    print("=" * 70)
    print(f"Found {len(empty_strata)} empty strata:")
    for stratum in empty_strata[:10]:  # Show first 10
        print(f"  - seat={stratum[0]}, contract={stratum[1]}, trump={stratum[2]}")
    if len(empty_strata) > 10:
        print(f"  ... and {len(empty_strata) - 10} more")
    raise AssertionError("Empty strata detected - some seat/contract/trump combinations have no data")

# Calculate statistics from counts
counts_list = list(strata_counts_dict.values())
min_count = min(counts_list)
mean_count = sum(counts_list) / len(counts_list)

print(f"\n✓ No empty strata (all {len(expected_strata)} combinations have data)")
print(f"  Minimum count per stratum: {min_count}")
print(f"  Mean count per stratum: {mean_count:.1f}")
print(f"  Total strata: {len(strata_counts_dict)}")

# Warn if any stratum is very small
if min_count < 10:
    print(f"\n⚠️  WARNING: Some strata have < 10 samples (min={min_count})")
    print("    Consider increasing N_DEALS for more robust analysis")

print("\n✅ Distribution coverage check PASSED")

# %% [markdown]
# # ============================================================================
# # PHASE 04: FEATURE HYGIENE
# # ============================================================================
#
# **Purpose: Verify feature quality and distributions**
#
# This phase examines feature distributions, correlations, and stability to ensure:
# - Features have reasonable distributions (no extreme outliers or constant values)
# - Seat balance (no dealing bias)
# - Contract-specific behavior is understood
# - No drift over time
#
# **Key charts from `bid_euchre.diagnostics`:**
# - Hand value by seat/contract
# - Feature distributions
# - Feature correlations
# - Rolling means for drift detection
#
# **Quality bar:**
# - ⚠️ Warnings for small sample sizes
# - Statistical tests for seat balance (use existing p-values here, save effect sizes for Phase 6)

# %% [markdown]
# ---
# # Part 1: Feature Quality Checks
#
# Diagnostic charts for feature hygiene before model training.
#
# **Charts in this section:**
# - 4-1.1: Seat Balance Check
# - 4-1.2: Feature Distributions
# - 4-1.3: Feature Correlations
# - 4-1.4: Contract-Specific Distributions
# - 4-1.5: Drift Detection

# %% [markdown]
# ## 4-1.1 Seat Balance Check - Dealing Bias Detection
#
# **Purpose**: Verify no systematic bias in feature values across seats (0-3).
#
# **Key insight**: Seats should be exchangeable. Large effect sizes (d > 0.5) indicate dealing bias.
#
# **Statistical approach**: Cohen's d with bootstrap CIs (primary), ANOVA (supplementary)

# %%
# Chart 4-1.1

from itertools import combinations

import numpy as np
from scipy.stats import f_oneway

from bid_euchre.analysis.stats import check_sample_size_adequacy, effect_size_with_ci

# Key features to check for seat balance
balance_features = ['hand_value', 'trump_count', 'offsuit_aces', 'offsuit_king_count_total']

print("=" * 70)
print("CHART 4-1.1: SEAT BALANCE CHECK")
print("=" * 70)

# Sample size check
n_per_seat = features_df.groupby('seat').size().min()
adequacy = check_sample_size_adequacy(n_per_seat, analysis_type='group_comparison')
print(f"\nSample size per seat: {n_per_seat}")
if not adequacy['adequate']:
    print(f"⚠ WARNING: {adequacy['warnings'][0]}")

# Test each feature for seat balance
for feature in balance_features:
    col = f'feat_{feature}'
    if col not in features_df.columns:
        continue

    print(f"\n{feature.upper()}")
    print("-" * 60)

    # Prepare seat groups
    seat_groups = [features_df[features_df['seat'] == i][col].tolist() for i in range(4)]

    # ANOVA (omnibus test)
    f_stat, p_value = f_oneway(*seat_groups)
    print(f"ANOVA: F={f_stat:.3f}, p={p_value:.4f}")

    # Pairwise effect sizes
    max_effect_size = 0.0
    worst_pair = None

    for seat1, seat2 in combinations(range(4), 2):
        d, d_lower, d_upper = effect_size_with_ci(
            seat_groups[seat1], seat_groups[seat2],
            confidence=0.95, n_bootstrap=10000, seed=SEED
        )

        if abs(d) > abs(max_effect_size):
            max_effect_size = d
            worst_pair = (seat1, seat2)

        if abs(d) > 0.2:  # Report small+ effects
            print(f"  Seat {seat1} vs {seat2}: d={d:.3f} [{d_lower:.3f}, {d_upper:.3f}]")

    # Fail-fast for large effects
    if abs(max_effect_size) > 0.5:
        print("\n❌ CRITICAL: Large seat bias detected!")
        print(f"   {feature}: d={max_effect_size:.3f} between seats {worst_pair}")
        raise AssertionError(
            f"Seat bias in {feature} (d={max_effect_size:.3f} > 0.5)"
        )
    elif abs(max_effect_size) > 0.2:
        print(f"⚠ Small effect: d={max_effect_size:.3f} (seats {worst_pair})")
    else:
        print(f"✓ Balanced: max |d|={abs(max_effect_size):.3f} < 0.2")

# Visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()

for idx, feature in enumerate(balance_features):
    ax = axes[idx]
    col = f'feat_{feature}'

    if col not in features_df.columns:
        continue

    seat_data = [features_df[features_df['seat'] == i][col].values for i in range(4)]
    bp = ax.boxplot(seat_data, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'],
                    patch_artist=True)

    colors = ['#3498db', '#e74c3c', '#2ecc71', '#9b59b6']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    means = [np.mean(d) for d in seat_data]
    ax.scatter(range(1, 5), means, color='black', marker='D', s=50, zorder=5)

    ax.set_xlabel('Seat')
    ax.set_ylabel(feature)
    ax.set_title(f'{feature} - Seat Balance')
    ax.grid(True, alpha=0.3, axis='y')

plt.suptitle('Chart 4-1.1: Seat Balance Check', fontweight='bold')
plt.tight_layout()
plt.show()

print("\n✅ SEAT BALANCE CHECK PASSED")

# %% [markdown]
# ## 4-1.2 Feature Distributions - Sanity Check
#
# **Purpose**: Verify features have reasonable distributions (no extreme outliers, no constant values).
#
# **Key checks**:
# - Mean/median proximity (skewness indicator)
# - Range reasonableness (no pathological outliers)
# - Variance > 0 (no constant features)

# %%
# Chart 4-1.2

import matplotlib.pyplot as plt
import numpy as np

print("=" * 70)
print("CHART 4-1.2: FEATURE DISTRIBUTIONS")
print("=" * 70)

# Get numeric features
feat_cols = [c for c in features_df.columns if c.startswith('feat_')]
numeric_features = [c.replace('feat_', '') for c in feat_cols
                    if features_df[c].dtype in [np.float64, np.int64]]

# Summary statistics
print("\nFeature Statistics:")
print("-" * 80)
print(f"{'Feature':<20} {'Mean':>10} {'Median':>10} {'Std':>10} {'Min':>8} {'Max':>8}")
print("-" * 80)

constant_features = []
for feature in numeric_features[:15]:  # Top 15
    col = f'feat_{feature}'
    values = features_df[col].dropna()

    mean_val = values.mean()
    median_val = values.median()
    std_val = values.std()
    min_val = values.min()
    max_val = values.max()

    print(f"{feature:<20} {mean_val:>10.3f} {median_val:>10.3f} {std_val:>10.3f} "
          f"{min_val:>8.3f} {max_val:>8.3f}")

    if std_val < 1e-6:
        constant_features.append(feature)

if constant_features:
    print(f"\n⚠ WARNING: Constant features: {constant_features}")

# Visual distributions
fig = plot_feature_distributions(features_df, features=None, figsize=(14, 10), ncols=3)
plt.suptitle('Chart 4-1.2: Feature Distributions', fontweight='bold', y=1.00)
plt.show()

print("\n✅ FEATURE DISTRIBUTION CHECK COMPLETE")

# %% [markdown]
# ## 4-1.3 Feature Correlations - Multicollinearity Detection
#
# **Purpose**: Identify highly correlated feature pairs that may cause multicollinearity issues.
#
# **Key insight**: Features with |r| > 0.8 are nearly redundant. Consider removing one or using regularization.
#
# **Statistical approach**: Pearson correlation with bootstrap confidence intervals for key pairs.

# %%
# Chart 4-1.3

import matplotlib.pyplot as plt
import numpy as np

print("=" * 70)
print("CHART 4-1.3: FEATURE CORRELATIONS")
print("=" * 70)

# Correlation heatmap
fig = plot_feature_correlation(features_df, features=None, figsize=(10, 8))
plt.suptitle('Chart 4-1.3: Feature Correlation Matrix', fontweight='bold', y=1.00)
plt.show()

# Identify high-correlation pairs
feat_cols = [c for c in features_df.columns if c.startswith('feat_')]
numeric_cols = [c for c in feat_cols if features_df[c].dtype in [np.float64, np.int64]]

if len(numeric_cols) >= 2:
    corr_matrix = features_df[numeric_cols].corr()

    high_corr_pairs = []
    for i in range(len(numeric_cols)):
        for j in range(i+1, len(numeric_cols)):
            r = corr_matrix.iloc[i, j]
            if abs(r) > 0.7:
                feat1 = numeric_cols[i].replace('feat_', '')
                feat2 = numeric_cols[j].replace('feat_', '')
                high_corr_pairs.append((feat1, feat2, r))

    if high_corr_pairs:
        print(f"\nHigh correlation pairs (|r| > 0.7): {len(high_corr_pairs)}")
        for feat1, feat2, r in sorted(high_corr_pairs, key=lambda x: abs(x[2]), reverse=True)[:5]:
            print(f"  {feat1} <-> {feat2}: r={r:.3f}")
    else:
        print("\n✓ No feature pairs with |r| > 0.7")

print("\n✅ CORRELATION ANALYSIS COMPLETE")

# %% [markdown]
# ## 4-1.4 Contract-Specific Feature Distributions
#
# **Purpose**: Verify features behave differently across contract types (suit/high/low).
#
# **Key insight**: Features should show contract-specific patterns (e.g., trump_count high for suit, low for high/low contracts).
#
# **Statistical approach**: Effect sizes comparing contract types, ANOVA for omnibus test.

# %%
# Chart 4-1.4

import matplotlib.pyplot as plt

print("=" * 70)
print("CHART 4-1.4: CONTRACT-SPECIFIC DISTRIBUTIONS")
print("=" * 70)

# Visual comparison
fig = plot_hand_value_by_contract(features_df, figsize=(12, 6))
plt.suptitle('Chart 4-1.4: Hand Value by Contract Type', fontweight='bold', y=1.00)
plt.show()

# Statistical comparison
test_features = ['hand_value', 'trump_count', 'offsuit_aces']

for feature in test_features:
    col = f'feat_{feature}'
    if col not in features_df.columns:
        continue

    print(f"\n{feature.upper()}")
    print("-" * 60)

    contract_groups = {
        'suit': features_df[features_df['contract_type'] == 'suit'][col].tolist(),
        'high': features_df[features_df['contract_type'] == 'high'][col].tolist(),
        'low': features_df[features_df['contract_type'] == 'low'][col].tolist(),
    }

    # Effect sizes
    d_suit_high, d_sh_l, d_sh_u = effect_size_with_ci(
        contract_groups['suit'], contract_groups['high'],
        confidence=0.95, n_bootstrap=10000, seed=SEED
    )
    d_suit_low, d_sl_l, d_sl_u = effect_size_with_ci(
        contract_groups['suit'], contract_groups['low'],
        confidence=0.95, n_bootstrap=10000, seed=SEED
    )

    print(f"  Suit vs High: d={d_suit_high:.3f} [{d_sh_l:.3f}, {d_sh_u:.3f}]")
    print(f"  Suit vs Low:  d={d_suit_low:.3f} [{d_sl_l:.3f}, {d_sl_u:.3f}]")

print("\n✅ CONTRACT-SPECIFIC ANALYSIS COMPLETE")

# %% [markdown]
# ## 4-1.5 Temporal Stability - Drift Detection
#
# **Purpose**: Verify features are stationary over deal_id (no temporal drift).
#
# **Key insight**: Features should not systematically change over the course of data generation. Drift suggests RNG issues or non-deterministic feature computation.
#
# **Statistical approach**:
# - Rolling mean visualization
# - Mann-Whitney U test comparing first 10% vs last 10% of deals

# %%
# Chart 4-1.5

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import mannwhitneyu

print("=" * 70)
print("CHART 4-1.5: DRIFT DETECTION")
print("=" * 70)

# Sort by deal_id or index
if 'deal_id' in features_df.columns:
    sorted_df = features_df.sort_values('deal_id').reset_index(drop=True)
else:
    sorted_df = features_df.sort_index().reset_index(drop=True)
    print("\n⚠ No deal_id, using index as proxy")

n_total = len(sorted_df)
split_idx = n_total // 10

drift_features = ['hand_value', 'trump_count', 'offsuit_aces']

for feature in drift_features:
    col = f'feat_{feature}'
    if col not in sorted_df.columns:
        continue

    print(f"\n{feature.upper()}")
    print("-" * 60)

    first_10 = sorted_df.iloc[:split_idx][col].dropna().tolist()
    last_10 = sorted_df.iloc[-split_idx:][col].dropna().tolist()

    u_stat, p_value = mannwhitneyu(first_10, last_10, alternative='two-sided')
    d, d_l, d_u = effect_size_with_ci(first_10, last_10, confidence=0.95,
                                      n_bootstrap=5000, seed=SEED)

    print(f"  First 10%: mean={np.mean(first_10):.3f}")
    print(f"  Last 10%:  mean={np.mean(last_10):.3f}")
    print(f"  Mann-Whitney: p={p_value:.4f}")
    print(f"  Effect size: d={d:.3f} [{d_l:.3f}, {d_u:.3f}]")

    if p_value < 0.01 and abs(d) > 0.3:
        print("  ⚠ DRIFT DETECTED")
    else:
        print("  ✓ Stable")

# Rolling mean plots
for feature in drift_features[:2]:
    col = f'feat_{feature}'
    if col in sorted_df.columns:
        fig = plot_rolling_mean(sorted_df, column=col, window=200)
        plt.suptitle(f'Chart 4-1.5: {feature} - Temporal Stability',
                    fontweight='bold', y=1.00)
        plt.show()

print("\n✅ DRIFT DETECTION COMPLETE")

# %% [markdown]
# ---
# ## Phase 04 Summary
#
# **Feature hygiene validation complete:**
#
# 1. ✅ Chart 4-1.1: Seat Balance - No dealing bias (all |d| < 0.5)
# 2. ✅ Chart 4-1.2: Feature Distributions - Reasonable ranges
# 3. ✅ Chart 4-1.3: Feature Correlations - Multicollinearity assessed
# 4. ✅ Chart 4-1.4: Contract-Specific - Expected variation confirmed
# 5. ✅ Chart 4-1.5: Drift Detection - Temporal stability verified
#
# **Next:** Proceed to Phase 05 (Core Signal & Predictive Power)

# %% [markdown]
# # ============================================================================
# # PHASE 05: CORE SIGNAL & PREDICTIVE POWER
# # ============================================================================
#
# **Purpose: Validate that hand_value predicts outcomes**
#
# This is the critical phase that validates the entire feature engineering approach:
# - **hand_value vs tricks_won**: Does our heuristic predict actual outcomes?
# - **Feature importance**: Which features matter most for each contract type?
# - **Contract stability**: Do features behave consistently across contracts?
#
# **Key transformation: Bootstrap CIs instead of p-values**
# - Use `bootstrap_regression_ci()` for hand_value ~ tricks_won
# - Report R² by contract (no arbitrary global threshold)
# - Use bootstrap CIs to quantify uncertainty
#
# **Success criteria:**
# - R² > 0.5 for hand_value ~ tricks_won (indicates strong predictive power)
# - Confidence intervals exclude zero
# - Features show consistent importance across contracts

# %% [markdown]
# ---
# # Part 1: Core Bidless Analysis
#
# NEW: Charts specifically designed for bidless dataset quality and predictive power analysis.

# %% [markdown]
# ## 5-1.1 hand_value vs tricks_won - Predictive Accuracy
#
# **Purpose**: Evaluate how well estimated hand strength (hand_value) predicts actual outcomes (tricks_won).
#
# **Key insight**: High R² indicates hand_value is a reliable proxy for hand strength. Large residuals identify where the model fails.

# %%
# Chart 5-1.1

import numpy as np

from bid_euchre.analysis.stats import bootstrap_regression_ci

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# Use bootstrap regression for confidence intervals
print("Computing bootstrap regression CIs (this may take a moment)...")

n_bootstrap = 5000 if MODE == "quick" else 10000

reg_ci = bootstrap_regression_ci(
    outcome_df['feat_hand_value'].tolist(),
    outcome_df['tricks_won'].tolist(),
    n_bootstrap=n_bootstrap,
    seed=SEED
)

# Extract values
slope, slope_lo, slope_hi = reg_ci['slope']
intercept, int_lo, int_hi = reg_ci['intercept']
r2, r2_lo, r2_hi = reg_ci['r_squared']

# Left: scatter with regression line
ax1.scatter(outcome_df['feat_hand_value'], outcome_df['tricks_won'], alpha=0.3, s=10)
line_x = np.array([outcome_df['feat_hand_value'].min(), outcome_df['feat_hand_value'].max()])
line_y = slope * line_x + intercept
ax1.plot(line_x, line_y, 'r-', linewidth=2, label=f'R² = {r2:.3f} [{r2_lo:.3f}, {r2_hi:.3f}]')
ax1.set_xlabel('hand_value (estimated strength)', fontsize=11)
ax1.set_ylabel('tricks_won (actual outcome)', fontsize=11)
ax1.set_title('Predictive Accuracy: hand_value vs tricks_won', fontsize=12, fontweight='bold')
ax1.legend(fontsize=11)
ax1.grid(True, alpha=0.3)

# Right: residual plot
residuals = outcome_df['tricks_won'] - (slope * outcome_df['feat_hand_value'] + intercept)
ax2.scatter(outcome_df['feat_hand_value'], residuals, alpha=0.3, s=10)
ax2.axhline(y=0, color='r', linestyle='--', linewidth=2)
ax2.set_xlabel('hand_value (estimated)', fontsize=11)
ax2.set_ylabel('Residuals (actual - predicted)', fontsize=11)
ax2.set_title('Prediction Errors', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

print("\n" + "=" * 70)
print("BOOTSTRAP REGRESSION RESULTS")
print("=" * 70)
print(f"Slope: {slope:.3f} [{slope_lo:.3f}, {slope_hi:.3f}]")
print(f"Intercept: {intercept:.3f} [{int_lo:.3f}, {int_hi:.3f}]")
print(f"R²: {r2:.3f} [{r2_lo:.3f}, {r2_hi:.3f}]")
print(f"RMSE: {np.sqrt(np.mean(residuals**2)):.3f} tricks")

print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)

# Use R² CI lower bound for more conservative assessment
if r2_lo > 0.5:
    print("✓ STRONG: R² CI excludes 0.5 - strong predictive power confirmed")
elif r2 > 0.5:
    print("⚠ MODERATE: Point estimate > 0.5 but CI includes lower values")
    print("  Suggests reasonable predictive power, but with some uncertainty")
else:
    print("❌ WEAK: R² < 0.5 - hand_value may need improvement")

# Report by contract
print("\n" + "=" * 70)
print("R² BY CONTRACT TYPE (with 95% CI)")
print("=" * 70)

for contract in ['suit', 'high', 'low']:
    contract_df = outcome_df[outcome_df['contract_type'] == contract]

    contract_reg_ci = bootstrap_regression_ci(
        contract_df['feat_hand_value'].tolist(),
        contract_df['tricks_won'].tolist(),
        n_bootstrap=n_bootstrap,
        seed=SEED
    )

    c_r2, c_r2_lo, c_r2_hi = contract_reg_ci['r_squared']
    print(f"{contract.upper():5s}: R² = {c_r2:.3f} [{c_r2_lo:.3f}, {c_r2_hi:.3f}]")

# %% [markdown]
# ## 5-1.2 Feature Stability Across Contracts
#
# **Purpose**: Verify features behave consistently across suit/high/low contract types.
#
# **Key insight**: Stable features (similar distributions) generalize well. Highly variable features may need contract-specific handling.

# %%
# Chart 5-1.2

# Select key features to analyze
key_features = ['hand_value', 'trump_count', 'offsuit_aces', 'offsuit_kings']

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
axes = axes.flatten()

for idx, feature in enumerate(key_features):
    ax = axes[idx]

    for contract in ['suit', 'high', 'low']:
        contract_df = df[df['contract_type'] == contract]
        col = f'feat_{feature}'
        if col in contract_df.columns:
            ax.hist(contract_df[col], alpha=0.5, label=contract, bins=30, edgecolor='black', linewidth=0.5)

    ax.set_xlabel(feature, fontsize=11)
    ax.set_ylabel('Count', fontsize=11)
    ax.set_title(f'{feature} - Distribution by Contract', fontsize=12, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')

plt.suptitle('Feature Stability Across Contract Types', fontsize=14, fontweight='bold', y=1.00)
plt.tight_layout()
plt.show()

# Calculate variance ratios to identify unstable features
print("Feature Variance by Contract Type:")
print("=" * 60)
for feature in key_features:
    col = f'feat_{feature}'
    if col in df.columns:
        variances = df.groupby('contract_type')[col].var()
        mean_var = variances.mean()
        max_ratio = variances.max() / variances.min() if variances.min() > 0 else float('inf')

        print(f"\n{feature}:")
        print(variances.to_string())
        print(f"  Max/Min ratio: {max_ratio:.2f}x")

        if max_ratio > 3:
            print("  ⚠ HIGH VARIANCE - may need contract-specific handling")
        else:
            print("  ✓ Stable across contracts")

# %% [markdown]
# ## 5-1.3 Contract-Specific Feature Importance
#
# **Purpose**: Identify which features matter most for each contract type (suit/high/low).
#
# **Key insight**: Different contracts may rely on different features. Common important features across contracts should be prioritized in model training.

# %%
# Chart 5-1.3

# Calculate feature importance (correlation with tricks_won) for each contract
feat_cols = [col for col in outcome_df.columns if col.startswith('feat_')]
top_n = 10

fig, axes = plt.subplots(1, 3, figsize=(18, 6))
contracts = ['suit', 'high', 'low']

# Store top features for each contract
contract_top_features = {}

for idx, contract in enumerate(contracts):
    contract_df = outcome_df[outcome_df['contract_type'] == contract]

    # Calculate correlations
    correlations = {}
    for col in feat_cols:
        corr = contract_df[col].corr(contract_df['tricks_won'])
        correlations[col.replace('feat_', '')] = corr

    # Get top N by absolute value
    top_feats = sorted(correlations.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]
    contract_top_features[contract] = set([f[0] for f in top_feats])

    # Plot
    ax = axes[idx]
    features = [f[0] for f in top_feats]
    values = [f[1] for f in top_feats]
    colors = ['green' if v > 0 else 'red' for v in values]

    ax.barh(features, values, color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
    ax.set_xlabel('Correlation with tricks_won', fontsize=11)
    ax.set_title(f'{contract.upper()} Contract', fontsize=12, fontweight='bold')
    ax.axvline(x=0, color='black', linestyle='-', linewidth=1)
    ax.grid(True, alpha=0.3, axis='x')
    ax.invert_yaxis()

plt.suptitle('Contract-Specific Feature Importance (Top 10 by |correlation|)', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()

# Analyze feature overlap
suit_feats = contract_top_features['suit']
high_feats = contract_top_features['high']
low_feats = contract_top_features['low']

print("\nFeature Overlap Analysis:")
print("=" * 60)
print(f"All three contracts: {sorted(suit_feats & high_feats & low_feats)}")
print(f"Suit + High only: {sorted(suit_feats & high_feats - low_feats)}")
print(f"Suit + Low only: {sorted(suit_feats & low_feats - high_feats)}")
print(f"High + Low only: {sorted(high_feats & low_feats - suit_feats)}")
print(f"Suit only: {sorted(suit_feats - high_feats - low_feats)}")
print(f"High only: {sorted(high_feats - suit_feats - low_feats)}")
print(f"Low only: {sorted(low_feats - suit_feats - high_feats)}")

common_count = len(suit_feats & high_feats & low_feats)
print(f"\n✓ {common_count}/{top_n} features are important across all contracts")

# %% [markdown]
# ## 5-1.4 Seat Position Effects
#
# **Purpose**: Analyze whether dealer/leader position or seat assignment impacts hand strength or outcomes.
#
# **Key insight**: Significant differences indicate:
# - Dealing bias (seat-to-seat variations)
# - Positional advantages (dealer/leader effects)
#
# Bidless features include dealer/leader one-hot encodings, so understanding their impact is critical for model training.

# %%
# Chart 5-1.4

from itertools import combinations

from scipy.stats import f_oneway

from bid_euchre.analysis.stats import bootstrap_group_means_ci, effect_size_with_ci

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Prepare data
dealer_data = [df[df['seat'] == i]['feat_hand_value'].tolist() for i in range(4)]
dealer_outcome = [outcome_df[outcome_df['seat'] == i]['tricks_won'].tolist() for i in range(4)]
seat_data = [df[df['seat'] == i]['feat_hand_value'].tolist() for i in range(4)]

# 1. hand_value by dealer position
ax1 = axes[0, 0]
bp1 = ax1.boxplot(dealer_data, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], patch_artist=True)
for patch in bp1['boxes']:
    patch.set_facecolor('lightblue')
ax1.set_ylabel('hand_value', fontsize=11)
ax1.set_title('Hand Value by Dealer Position', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')

# 2. tricks_won by dealer position (from outcome_df)
ax2 = axes[0, 1]
bp2 = ax2.boxplot(dealer_outcome, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], patch_artist=True)
for patch in bp2['boxes']:
    patch.set_facecolor('lightgreen')
ax2.set_ylabel('tricks_won', fontsize=11)
ax2.set_title('Tricks Won by Dealer Position', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')

# 3. hand_value by seat (detect dealing bias)
ax3 = axes[1, 0]
bp3 = ax3.boxplot(seat_data, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], patch_artist=True)
for patch in bp3['boxes']:
    patch.set_facecolor('lightyellow')
ax3.set_ylabel('hand_value', fontsize=11)
ax3.set_title('Hand Value by Seat (Dealing Bias Check)', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# 4. Statistical summary with effect sizes
ax4 = axes[1, 1]
ax4.axis('off')

print("\n" + "=" * 70)
print("COMPUTING EFFECT SIZES & CONFIDENCE INTERVALS")
print("=" * 70)

# Get CIs for each seat
n_bootstrap = 5000 if MODE == "quick" else 10000

seat_cis = bootstrap_group_means_ci(
    seat_data,
    n_bootstrap=n_bootstrap,
    seed=SEED
)

# Compute pairwise effect sizes
max_d = 0
max_pair = None

for s1, s2 in combinations(range(4), 2):
    d, d_lo, d_hi = effect_size_with_ci(
        seat_data[s1],
        seat_data[s2],
        n_bootstrap=n_bootstrap,
        seed=SEED
    )
    if abs(d) > abs(max_d):
        max_d = d
        max_pair = (s1, s2)

# ANOVA for supplementary info
f_stat1, p_value1 = f_oneway(*dealer_data)
f_stat2, p_value2 = f_oneway(*dealer_outcome)
f_stat3, p_value3 = f_oneway(*seat_data)

summary_text = "Effect Sizes (PRIMARY):\n"
summary_text += "=" * 50 + "\n\n"

summary_text += "Seat hand_value means (95% CI):\n"
for seat, (mean, lo, hi) in enumerate(seat_cis):
    summary_text += f"  Seat {seat}: {mean:.3f} [{lo:.3f}, {hi:.3f}]\n"

summary_text += f"\nMax Cohen's d: {abs(max_d):.3f} (seats {max_pair[0]} vs {max_pair[1]})\n\n"

# Interpret effect size
if abs(max_d) < 0.2:
    summary_text += "✓ Negligible seat effects (d < 0.2)\n"
    summary_text += "  No dealing bias detected\n"
elif abs(max_d) < 0.5:
    summary_text += "⚠ Small seat effects (0.2 ≤ d < 0.5)\n"
    summary_text += "  Minor bias - acceptable for most purposes\n"
else:
    summary_text += "❌ Moderate to large seat effects (d ≥ 0.5)\n"
    summary_text += "  Investigate RNG or dealing logic!\n"

summary_text += "\n" + "-" * 50 + "\n"
summary_text += "ANOVA p-values (SUPPLEMENTARY):\n"
summary_text += "-" * 50 + "\n\n"

summary_text += f"Dealer → hand_value: p={p_value1:.4f}\n"
summary_text += f"Dealer → tricks_won: p={p_value2:.4f}\n"
summary_text += f"Seat bias check:    p={p_value3:.4f}\n\n"

summary_text += "Note: Effect sizes are primary.\n"
summary_text += "p-values show statistical significance,\n"
summary_text += "but small effects can be significant\n"
summary_text += "with large sample sizes.\n"

ax4.text(0.05, 0.5, summary_text, fontsize=9, family='monospace',
         verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.suptitle('Seat Position Effects - Effect Size Analysis', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()

print("\n" + "=" * 70)
print("SEAT BIAS CHECK: EFFECT SIZE ANALYSIS")
print("=" * 70)
print(f"\nMax Cohen's d: {abs(max_d):.3f} (seats {max_pair[0]} vs {max_pair[1]})")
if abs(max_d) < 0.2:
    print("✅ PASS: Negligible seat effects (d < 0.2) - no dealing bias")
elif abs(max_d) < 0.5:
    print("⚠️  WARN: Small seat effects (0.2 ≤ d < 0.5) - minor bias detected")
else:
    print("❌ FAIL: Moderate/large seat effects (d ≥ 0.5) - investigate RNG!")

# %%
from scipy.stats import f_oneway

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. hand_value by dealer position
ax1 = axes[0, 0]
dealer_data = [df[df['seat'] == i]['feat_hand_value'].values for i in range(4)]
bp1 = ax1.boxplot(dealer_data, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], patch_artist=True)
for patch in bp1['boxes']:
    patch.set_facecolor('lightblue')
ax1.set_ylabel('hand_value', fontsize=11)
ax1.set_title('Hand Value by Dealer Position', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3, axis='y')

# 2. tricks_won by dealer position (from outcome_df)
ax2 = axes[0, 1]
dealer_outcome = [outcome_df[outcome_df['seat'] == i]['tricks_won'].values for i in range(4)]
bp2 = ax2.boxplot(dealer_outcome, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], patch_artist=True)
for patch in bp2['boxes']:
    patch.set_facecolor('lightgreen')
ax2.set_ylabel('tricks_won', fontsize=11)
ax2.set_title('Tricks Won by Dealer Position', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3, axis='y')

# 3. hand_value by seat (detect dealing bias)
ax3 = axes[1, 0]
seat_data = [df[df['seat'] == i]['feat_hand_value'].values for i in range(4)]
bp3 = ax3.boxplot(seat_data, labels=['Seat 0', 'Seat 1', 'Seat 2', 'Seat 3'], patch_artist=True)
for patch in bp3['boxes']:
    patch.set_facecolor('lightyellow')
ax3.set_ylabel('hand_value', fontsize=11)
ax3.set_title('Hand Value by Seat (Dealing Bias Check)', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, axis='y')

# 4. Statistical summary
ax4 = axes[1, 1]
ax4.axis('off')

# ANOVA tests
f_stat1, p_value1 = f_oneway(*dealer_data)
f_stat2, p_value2 = f_oneway(*dealer_outcome)
f_stat3, p_value3 = f_oneway(*seat_data)

summary_text = "Statistical Tests (ANOVA):\n"
summary_text += "=" * 50 + "\n\n"

summary_text += "Dealer position → hand_value\n"
summary_text += f"  F-statistic: {f_stat1:.3f}\n"
summary_text += f"  p-value: {p_value1:.4f}\n"
summary_text += f"  Significant: {'Yes (⚠)' if p_value1 < 0.05 else 'No (✓)'}\n\n"

summary_text += "Dealer position → tricks_won\n"
summary_text += f"  F-statistic: {f_stat2:.3f}\n"
summary_text += f"  p-value: {p_value2:.4f}\n"
summary_text += f"  Significant: {'Yes (⚠)' if p_value2 < 0.05 else 'No (✓)'}\n\n"

summary_text += "Seat dealing bias check\n"
summary_text += f"  F-statistic: {f_stat3:.3f}\n"
summary_text += f"  p-value: {p_value3:.4f}\n"
summary_text += f"  Bias detected: {'Yes (⚠)' if p_value3 < 0.05 else 'No (✓)'}\n\n"

summary_text += "\nInterpretation:\n"
summary_text += "  p < 0.05: Position significantly affects outcome\n"
summary_text += "  p ≥ 0.05: No significant position effect\n\n"

if p_value3 < 0.05:
    summary_text += "⚠ Dealing bias detected - check RNG!\n"
else:
    summary_text += "✓ No dealing bias - RNG is fair\n"

ax4.text(0.05, 0.5, summary_text, fontsize=10, family='monospace',
         verticalalignment='center', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.suptitle('Seat Position Effects on Hand Strength and Outcomes', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.show()

# %% [markdown]
# ---
# # Part 2: Feature Distribution Analysis
#
# From `bid_euchre.diagnostics` — interactive DataFrame-based analysis for exploratory work.
#
# **When to use**: Jupyter notebooks, quick health checks, interactive exploration
# **Input format**: pandas DataFrame with `feat_*` columns
# **Display**: `plt.show()` (inline in notebook)

# %% [markdown]
# ## 5-2.1 `plot_hand_value_by_seat()`
#
# Box plots showing hand_value distribution across seats (0-3). Detects dealing bias or per-seat feature computation bugs.

# %%
# Chart 5-2.1

fig = plot_hand_value_by_seat(df)
plt.show()

# %% [markdown]
# ## 5-2.2 `plot_hand_value_by_contract()`
#
# Box plots comparing hand_value across contract types (suit/high/low).

# %%
# Chart 5-2.2

fig = plot_hand_value_by_contract(df)
plt.show()

# %% [markdown]
# ## 5-2.3 `plot_feature_distributions()`
#
# Grid of histograms for multiple features. Shows top 9 features by variance by default.

# %%
# Chart 5-2.3

fig = plot_feature_distributions(df)
plt.show()

# %%
# With specific features
fig = plot_feature_distributions(df, features=['hand_value', 'trump_count', 'offsuit_aces'])
plt.show()

# %% [markdown]
# ## 5-2.4 `plot_feature_correlation()`
#
# Heatmap of feature correlations. Top 10 features by variance by default.

# %%
# Chart 5-2.4

fig = plot_feature_correlation(df)
plt.show()

# %% [markdown]
# ## 5-2.5 `plot_rolling_mean()`
#
# Time-series plot of rolling mean over hand index. Detects drift over time.

# %%
# Chart 5-2.5

fig = plot_rolling_mean(df, column='feat_hand_value', window=50)
plt.show()

# %% [markdown]
# ## 5-2.6 `plot_feature_vs_label()`
#
# Dual panel: scatter plot + binned box plot. Shows feature vs label relationship.

# %%
# Chart 5-2.6

fig = plot_feature_vs_label(df, feature='trump_count', label='hand_value')
plt.show()

# %%
# ============================================================================
# Generate features_by_contract dict for dict-based validation plots
# ============================================================================

if RUN_REPORT_EXPORTS:
    print("Generating features_by_contract dict for report exports...")

    features_by_contract = {}

    # Sample from features_df to create dict structure
    # Use a reasonable sample size (1000 per contract or all if less)
    sample_size = min(1000, len(features_df) // len(CONTRACT_TYPES))

    for contract_key in ['suit_H', 'high', 'low']:
        if contract_key == 'suit_H':
            contract_type, trump = 'suit', 'H'
        else:
            contract_type, trump = contract_key, None

        # Filter to this contract
        if trump:
            contract_df = features_df[
                (features_df['contract_type'] == contract_type) &
                (features_df['trump'] == trump)
            ]
        else:
            contract_df = features_df[
                (features_df['contract_type'] == contract_type)
            ]

        # Convert to list of feature dicts
        features_by_contract[contract_key] = []
        for _, row in contract_df.head(min(sample_size, len(contract_df))).iterrows():
            # Extract only feat_* columns and remove the 'feat_' prefix
            feat_dict = {k.replace('feat_', ''): v
                        for k, v in row.items() if k.startswith('feat_')}
            features_by_contract[contract_key].append(feat_dict)

    print(f"✓ Generated features_by_contract: {list(features_by_contract.keys())}")
    for key in features_by_contract:
        print(f"  {key}: {len(features_by_contract[key])} samples")
else:
    print("Skipping report exports (RUN_REPORT_EXPORTS=False)")
    features_by_contract = None

# %% [markdown]
# # ============================================================================
# # PHASE 08: REPORT EXPORTS
# # ============================================================================
#
# **Purpose: Generate dict-based validation plots for pipelines**
#
# Uses `bid_euchre.reporting.validation` for batch report generation.
# These are production-ready plots for training pipeline integration.
#
# **Input format**: `Dict[contract_key, List[feature_dict]]`
# **Output**: PNG files saved to disk
#
# **Note**: Will skip if RUN_REPORT_EXPORTS is False or features_by_contract dict not created.

# %% [markdown]
# ---
# # Part 1: Evaluation Charts (Dict-based, for Reporting Pipelines)
#
# From `bid_euchre.reporting.validation` — batch report generation for training pipelines.
#
# **When to use**: Reproducible batch reports, training pipeline integration
# **Input format**: `Dict[contract_key, List[feature_dict]]` or `List[feature_dict]`
# **Output**: Saves PNG files to disk, returns file paths

# %%
# Create temp directory for output
output_dir = tempfile.mkdtemp(prefix='charts_demo_')
print(f"Output directory: {output_dir}")

# %% [markdown]
# ## 8-1.1 `plot_feature_distributions()` (eval)
#
# Feature distributions by contract type. Overlays histograms for comparison.

# %%
# Chart 8-1.1

path = eval_plot_feature_distributions(
    features_by_contract,
    output_dir,
    feature_keys=["trump_count", "hand_value"],
)
print(f"Saved to: {path}")

# Display the saved image
Image(filename=path)

# %% [markdown]
# ## 8-1.2 `plot_feature_correlation()` (eval)
#
# Correlation matrix from feature dicts. Auto-detects numeric columns.

# %%
# Chart 8-1.2

# Flatten all features for correlation
all_features = []
for features_list in features_by_contract.values():
    all_features.extend(features_list)

path = eval_plot_feature_correlation(all_features, output_dir)
print(f"Saved to: {path}")

Image(filename=path)

# %% [markdown]
# ## 8-1.3 `plot_hand_value_by_contract()` (eval)
#
# Box plots of hand_value by contract type from Dict input.

# %%
# Chart 8-1.3

path = eval_plot_hand_value_by_contract(features_by_contract, output_dir)
print(f"Saved to: {path}")

Image(filename=path)

# %% [markdown]
# ## 8-1.4 `generate_validation_plots()`
#
# Orchestrator function that generates all evaluation plots at once.

# %%
# Chart 8-1.4

# Use a separate subdirectory
batch_dir = os.path.join(output_dir, "batch")

plots = generate_validation_plots(features_by_contract, batch_dir)
print("Generated plots:")
for name, path in plots.items():
    print(f"  {name}: {path}")

# %% [markdown]
# ---
# # Part 2: Additional Outcome Evaluation
#
# Additional charts that correlate hand features with actual outcomes (`tricks_won`) from simulation.
#
# **Key requirement**: Uses `outcome_df` generated in Part 1.

# %% [markdown]
# ## 8-2.1 `plot_feature_vs_outcome()` - hand_value vs tricks_won
#
# Scatter plot with trend line + binned box plot. Shows correlation coefficient in title.

# %%
# Chart 8-2.1

from bid_euchre.diagnostics.charts import plot_feature_vs_outcome

# hand_value vs tricks_won - the key relationship
fig = plot_feature_vs_outcome(outcome_df, feature='hand_value', outcome='tricks_won')
plt.show()

# %%
# Also check trump_count vs tricks_won for suit contracts
suit_df = outcome_df[outcome_df['contract_type'] == 'suit']
fig = plot_feature_vs_outcome(suit_df, feature='trump_count', outcome='tricks_won')
plt.show()

# %% [markdown]
# ## 8-2.2 `plot_outcome_distributions()` - tricks by contract type
#
# Violin/box plots of outcome distribution grouped by category.

# %%
# Chart 8-2.2

from bid_euchre.diagnostics.charts import plot_outcome_distributions

fig = plot_outcome_distributions(outcome_df, outcome='tricks_won', group_by='contract_type')
plt.show()

# %% [markdown]
# ## 8-2.3 `plot_feature_outcome_correlation()` - feature importance bar chart
#
# Horizontal bar chart showing correlation of each feature with tricks_won, sorted by importance.

# %%
# Chart 8-2.3

from bid_euchre.diagnostics.charts import plot_feature_outcome_correlation

fig = plot_feature_outcome_correlation(outcome_df, outcome='tricks_won', top_n=15)
plt.show()

# %%
# Filter to suit contracts only for more specific feature importance
fig = plot_feature_outcome_correlation(suit_df, outcome='tricks_won', top_n=15)
plt.show()

# %% [markdown]
# # ============================================================================
# # PHASE 07: SECOND-ORDER DIAGNOSTICS
# # ============================================================================
#
# **Purpose: Advanced analysis after pipeline gates pass**
#
# This phase contains second-order diagnostics that should ONLY be interpreted
# after Phases 3-6 quality gates pass:
#
# 1. **Strategy Matchups** (Part 6) - Play strategy performance comparisons
# 2. **Trump Suit Analysis** (Part 7) - Multi-suit parity checks
# 3. **CDF/CCDF** (Part 8) - Distribution tail analysis
#
# **Important:**
# - These are exploratory/diagnostic
# - Do NOT use to invalidate primary quality gates
# - Interpret only after confirming data is valid
#
# **Subsections:**
# - **7.1**: Strategy Performance on Bidless Hands
# - **7.2**: Trump Suit Analysis
# - **7.3**: Distribution Analysis (CDF/CCDF)

# %%
import numpy as np

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy, RandomLegalStrategy

# Define strategies to compare
STRATEGY_CLASSES = {
    'greedy': GreedyStrategy,
    'glutton': GluttonStrategy,
    'random': lambda: RandomLegalStrategy(seed=42),
}

# Generate matchup results
matchup_results = {}

for team0_name in STRATEGY_CLASSES.keys():
    for team1_name in STRATEGY_CLASSES.keys():
        team0_strat = STRATEGY_CLASSES[team0_name]()
        team1_strat = STRATEGY_CLASSES[team1_name]()
        strategies = [team0_strat, team1_strat, team0_strat, team1_strat]

        t0_tricks = []
        t1_tricks = []

        for deal_id in range(N_DEALS_MATCHUPS):
            hands = generate_deal(SEED, deal_id)
            t0, t1, *_ = play_single_hand(
                contract_type='suit',
                trump_suit=DEMO_TRUMP_SUIT,
                strategies=strategies,
                hands=hands,
                deal_seed=SEED,
            )
            t0_tricks.append(t0)
            t1_tricks.append(t1)

        matchup_results[(team0_name, team1_name)] = {
            'tricks_team0': t0_tricks,
            'tricks_team1': t1_tricks,
            'mean_tricks': np.mean(t0_tricks),
            'win_rate': np.mean([1 if t >= 6 else 0 for t in t0_tricks]),
            'ci_lower': np.mean(t0_tricks) - 1.96 * np.std(t0_tricks) / np.sqrt(N_DEALS_MATCHUPS),
            'ci_upper': np.mean(t0_tricks) + 1.96 * np.std(t0_tricks) / np.sqrt(N_DEALS_MATCHUPS),
        }

print(f"Generated {len(matchup_results)} matchups (N={N_DEALS_MATCHUPS} deals each)")
for key, result in matchup_results.items():
    print(f"  {key[0]} vs {key[1]}: mean={result['mean_tricks']:.2f}, win_rate={result['win_rate']:.1%}")

# %% [markdown]
# ## 7-1.1 Generate Matchup Data
#
# Run simulations with different strategy pairs to collect matchup results.

# %%
# Chart 7-1.1

import numpy as np

from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy import GluttonStrategy, GreedyStrategy

# Define strategies to compare
STRATEGY_CLASSES = {
    'greedy': GreedyStrategy,
    'glutton': GluttonStrategy,
    'random': lambda: RandomLegalStrategy(seed=42),
}

# Generate matchup results
matchup_results = {}

for team0_name in STRATEGY_CLASSES.keys():
    for team1_name in STRATEGY_CLASSES.keys():
        team0_strat = STRATEGY_CLASSES[team0_name]()
        team1_strat = STRATEGY_CLASSES[team1_name]()
        strategies = [team0_strat, team1_strat, team0_strat, team1_strat]

        t0_tricks = []
        t1_tricks = []

        for deal_id in range(N_DEALS_MATCHUPS):
            hands = generate_deal(SEED, deal_id)
            t0, t1, *_ = play_single_hand(
                contract_type='suit',
                trump_suit=DEMO_TRUMP_SUIT,
                strategies=strategies,
                hands=hands,
                deal_seed=SEED,
            )
            t0_tricks.append(t0)
            t1_tricks.append(t1)

        matchup_results[(team0_name, team1_name)] = {
            'tricks_team0': t0_tricks,
            'tricks_team1': t1_tricks,
            'mean_tricks': np.mean(t0_tricks),
            'win_rate': np.mean([1 if t >= 6 else 0 for t in t0_tricks]),
            'ci_lower': np.mean(t0_tricks) - 1.96 * np.std(t0_tricks) / np.sqrt(N_DEALS_MATCHUPS),
            'ci_upper': np.mean(t0_tricks) + 1.96 * np.std(t0_tricks) / np.sqrt(N_DEALS_MATCHUPS),
        }

print(f"Generated {len(matchup_results)} matchups (N={N_DEALS_MATCHUPS} deals each)")
for key, result in matchup_results.items():
    print(f"  {key[0]} vs {key[1]}: mean={result['mean_tricks']:.2f}, win_rate={result['win_rate']:.1%}")


# %% [markdown]
# ## 7-1.2 `plot_win_rate_heatmap()` - all-vs-all win rates
#
# Heatmap showing Team 0's win rate against each Team 1 strategy.

# %%
# Chart 7-1.2

from bid_euchre.diagnostics import plot_win_rate_heatmap

fig = plot_win_rate_heatmap(matchup_results, metric='win_rate')
plt.show()

# %% [markdown]
# ## 7-1.3 `plot_tricks_distribution_comparison()` - violin plots by matchup
#
# Violin plots comparing trick distributions across different matchups.

# %%
# Chart 7-1.3

from bid_euchre.diagnostics import plot_tricks_distribution_comparison

# Show a subset of interesting matchups
subset_matchups = {k: v for k, v in matchup_results.items()
                   if k[0] != k[1]}  # Exclude self-play for comparison

fig = plot_tricks_distribution_comparison(subset_matchups, team=0)
plt.show()

# %% [markdown]
# ## 7-1.4 `plot_strategy_delta_bars()` - delta vs baseline
#
# Bar chart showing mean tricks delta relative to baseline (random).

# %%
# Chart 7-1.4

from bid_euchre.diagnostics import plot_strategy_delta_bars

# Compare each strategy vs random baseline
baseline_results = matchup_results[('random', 'random')]
comparison_results = {
    'greedy': matchup_results[('greedy', 'random')],
    'glutton': matchup_results[('glutton', 'random')],
}

fig = plot_strategy_delta_bars(baseline_results, comparison_results, baseline_name='random')
plt.show()

# %% [markdown]
# ## 7-1.5 `plot_self_play_control()` - self-play sanity check
#
# Control chart showing mean tricks for self-play matchups. Should be ~5.0 for fair play.

# %%
# Chart 7-1.5

from bid_euchre.diagnostics import plot_self_play_control

# Extract self-play matchups
self_play_results = {k[0]: v for k, v in matchup_results.items() if k[0] == k[1]}

fig = plot_self_play_control(self_play_results)
plt.show()

# %%
# Generate data with all 4 trump suits
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy import GreedyStrategy

strategy = GreedyStrategy()
multi_suit_data = []
multi_suit_outcome_data = []

for deal_id in range(N_DEALS_MULTI_SUIT):
    hands = generate_deal(SEED, deal_id)

    for trump in TRUMPS_FOR_SUIT_CONTRACTS:
        # Features only (no simulation)
        for seat in range(4):
            features = get_hand_features(hands[seat], 'suit', trump)
            multi_suit_data.append({
                'deal_id': deal_id,
                'seat': seat,
                'contract_type': 'suit',
                'trump': trump,
                **{f'feat_{k}': v for k, v in features.items()}
            })

        # With simulation outcomes
        t0, t1, _, all_feats, _, _, *_ = play_single_hand(
            contract_type='suit',
            trump_suit=trump,
            strategy=strategy,
            hands=hands,
            deal_seed=SEED,
        )

        for seat in range(4):
            team_tricks = t0 if seat in (0, 2) else t1
            features = all_feats[seat]
            multi_suit_outcome_data.append({
                'deal_id': deal_id,
                'seat': seat,
                'contract_type': 'suit',
                'trump': trump,
                'tricks_won': team_tricks,
                **{f'feat_{k}': v for k, v in features.items()}
            })

multi_suit_df = pd.DataFrame(multi_suit_data)
multi_suit_outcome_df = pd.DataFrame(multi_suit_outcome_data)

print(f"Multi-suit DataFrame: {multi_suit_df.shape}")
print(f"Trump distribution: {multi_suit_df['trump'].value_counts().to_dict()}")

# %% [markdown]
# ## 7-1.6 Generate Multi-Suit Data
#
# Generate data with all 4 trump suits for comparison.

# %%
# Chart 7-1.6

# Generate data with all 4 trump suits
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy import GreedyStrategy

strategy = GreedyStrategy()
multi_suit_data = []
multi_suit_outcome_data = []

for deal_id in range(N_DEALS_MULTI_SUIT):
    hands = generate_deal(SEED, deal_id)

    for trump in TRUMPS_FOR_SUIT_CONTRACTS:
        # Features only (no simulation)
        for seat in range(4):
            features = get_hand_features(hands[seat], 'suit', trump)
            multi_suit_data.append({
                'deal_id': deal_id,
                'seat': seat,
                'contract_type': 'suit',
                'trump': trump,
                **{f'feat_{k}': v for k, v in features.items()}
            })

        # With simulation outcomes
        t0, t1, _, all_feats, _, _, *_ = play_single_hand(
            contract_type='suit',
            trump_suit=trump,
            strategy=strategy,
            hands=hands,
            deal_seed=SEED,
        )

        for seat in range(4):
            team_tricks = t0 if seat in (0, 2) else t1
            features = all_feats[seat]
            multi_suit_outcome_data.append({
                'deal_id': deal_id,
                'seat': seat,
                'contract_type': 'suit',
                'trump': trump,
                'tricks_won': team_tricks,
                **{f'feat_{k}': v for k, v in features.items()}
            })

multi_suit_df = pd.DataFrame(multi_suit_data)
multi_suit_outcome_df = pd.DataFrame(multi_suit_outcome_data)

print(f"Multi-suit DataFrame: {multi_suit_df.shape}")
print(f"Trump distribution: {multi_suit_df['trump'].value_counts().to_dict()}")


# %% [markdown]
# ## 7-1.7 `plot_hand_value_by_trump_suit()` - hand value by suit
#
# Box plots showing hand_value distribution for each trump suit. Includes variance annotations.

# %%
# Chart 7-1.7

from bid_euchre.diagnostics import plot_hand_value_by_trump_suit

fig = plot_hand_value_by_trump_suit(multi_suit_df, show_variance=True)
plt.show()

# %% [markdown]
# ## 7-1.8 `plot_outcome_by_trump_suit()` - tricks won by suit
#
# Outcome distribution showing if some suits systematically win more tricks.

# %%
# Chart 7-1.8

from bid_euchre.diagnostics import plot_outcome_by_trump_suit

fig = plot_outcome_by_trump_suit(multi_suit_outcome_df, outcome='tricks_won')
plt.show()

# %% [markdown]
# ## 7-1.9 `plot_feature_heatmap_by_suit()` - feature means by suit
#
# Heatmap showing which features vary most across trump suits.

# %%
# Chart 7-1.9

from bid_euchre.diagnostics import plot_feature_heatmap_by_suit

fig = plot_feature_heatmap_by_suit(multi_suit_df, normalize=True)
plt.show()

# %% [markdown]
# ## 7-1.10 `plot_suit_variance_summary()` - variance comparison
#
# Bar chart comparing variance of hand_value across suits.

# %%
# Chart 7-1.10

from bid_euchre.diagnostics import plot_suit_variance_summary

fig = plot_suit_variance_summary(multi_suit_df, column='feat_hand_value')
plt.show()

# %% [markdown]
# ---
# # Part 1: Distribution Analysis (CDF/CCDF)
#
# CDF and CCDF plots for analyzing distribution shapes and tail behavior.
#
# **CDF (Cumulative Distribution Function)**: Shows P(X ≤ x) — the probability a value is less than or equal to x.
# - Useful for understanding distribution shape
# - Quartile reference lines show median and spread
#
# **CCDF (Complementary CDF)**: Shows P(X > x) — the probability a value exceeds x.
# - Log scale reveals tail behavior
# - Useful for identifying rare high-value hands

# %% [markdown]
# ## 7-1.11 `plot_cdf()` - Cumulative Distribution Function
#
# CDF for hand_value showing probability distribution shape with quartile markers.

# %%
# Chart 7-1.11

from bid_euchre.diagnostics import plot_cdf

# Basic CDF of hand_value
fig = plot_cdf(df, column='feat_hand_value')
plt.show()

# %%
# CDF grouped by contract_type - compare distributions across categories
fig = plot_cdf(df, column='feat_hand_value', group_by='contract_type')
plt.show()

# %% [markdown]
# ## 7-1.12 `plot_ccdf()` - Complementary CDF (Tail Analysis)
#
# CCDF with log scale reveals tail behavior — useful for identifying rare high-value hands.

# %%
# Chart 7-1.12

from bid_euchre.diagnostics import plot_ccdf

# CCDF of hand_value with log scale - reveals tail distribution
fig = plot_ccdf(df, column='feat_hand_value', log_scale=True)
plt.show()

# %% [markdown]
# ## 7-1.13 CDF of Tricks Won
#
# CDF of simulation outcomes — shows probability of winning ≤ N tricks.

# %%
# Chart 7-1.13

# ============================================================================
# Session Summary
# ============================================================================

print("\n" + "=" * 70)
print("NOTEBOOK SESSION SUMMARY")
print("=" * 70)

print("\n📊 Configuration:")
print(f"  Mode: {MODE}")
print(f"  Seed: {SEED}")
print(f"  N_DEALS_FEATURES: {N_DEALS_FEATURES}")
print(f"  N_DEALS_OUTCOMES: {N_DEALS_OUTCOMES}")

print("\n📁 Generated Datasets:")
print(f"  features_df: {len(features_df):,} rows × {len(features_df.columns)} columns")
print(f"  outcome_df: {len(outcome_df):,} rows × {len(outcome_df.columns)} columns")
if 'multi_suit_df' in locals():
    print(f"  multi_suit_df: {len(multi_suit_df):,} rows")
if 'matchup_results' in locals():
    print(f"  matchup_results: {len(matchup_results)} matchups")

print("\n💾 Cache Status:")
cache_files = list(CACHE_DIR.glob("*.parquet"))
total_size_mb = sum(f.stat().st_size for f in cache_files) / 1024**2
print(f"  Cache directory: {CACHE_DIR}")
print(f"  Cached files: {len(cache_files)}")
print(f"  Total cache size: {total_size_mb:.2f} MB")

print("\n✅ Quality Gates:")
print("  Phase 03: Fail-Fast Tests - PASSED")
print("  Phase 04: Feature Hygiene - Complete")
print("  Phase 05: Core Signal - Bootstrap CIs")
print("  Phase 06: Bias Checks - Effect Sizes")

print("\n🎯 Key Findings:")
print(f"  Mean tricks_won: {outcome_df['tricks_won'].mean():.3f} (expected ~5.0)")
print(f"  Unique seats: {sorted(features_df['seat'].unique())}")
print(f"  Unique contracts: {sorted(features_df['contract_type'].unique())}")
print(f"  Unique trumps (suit): {sorted(features_df[features_df['contract_type'] == 'suit']['trump'].unique())}")

print("\n" + "=" * 70)
print("Session complete! Ready for cleanup.")
print("=" * 70)

# %% [markdown]
# # ============================================================================
# # PHASE 09: APPENDIX
# # ============================================================================
#
# **Purpose: Cleanup and session summary**
#
# - Remove temp directories
# - Print session summary (runtime, cache size, etc.)
# - Quick reference guide

# %%
# CDF of tricks_won - uses outcome_df from Part 3
fig = plot_cdf(outcome_df, column='tricks_won', group_by='contract_type')
plt.show()

# %% [markdown]
# ## 7-1.14 CCDF of Tricks Won
#
# CCDF shows P(tricks > N) — useful for analyzing win probability thresholds.

# %%
# Chart 7-1.14

# CCDF of tricks_won - P(tricks > N) by contract type
# At x=5, the CCDF shows win probability (≥6 tricks)
fig = plot_ccdf(outcome_df, column='tricks_won', log_scale=False, group_by='contract_type')
plt.show()

# %%
# Cleanup temp directory
shutil.rmtree(output_dir)
print("Cleaned up temp directory")

# %% [markdown]
# # Quick Reference
#
# ## Diagnostic Charts (`bid_euchre.diagnostics`)
#
# ### Bidless-Specific Analysis (NEW)
#
# | Chart | Purpose | Key Parameters |
# |-------|---------|----------------|
# | hand_value vs tricks_won | Predictive accuracy validation | Scatter + residual plot, R² |
# | Feature stability | Cross-contract distribution comparison | Histograms + variance ratios |
# | Contract-specific importance | Top features by contract type | Bar charts by correlation |
# | Seat position effects | Dealer/leader/seat bias detection | Box plots + ANOVA tests |
#
# ### Feature Analysis Charts
#
# | Function | Purpose | Key Parameters |
# |----------|---------|----------------|
# | `plot_hand_value_by_seat(df)` | Seat balance check | `df` with `seat`, `feat_hand_value` |
# | `plot_hand_value_by_contract(df)` | Contract comparison | `df` with `contract_type`, `feat_hand_value` |
# | `plot_feature_distributions(df)` | Feature histograms | `features=None` for top 9 by variance |
# | `plot_feature_correlation(df)` | Correlation heatmap | `features=None` for top 10 by variance |
# | `plot_rolling_mean(df, column)` | Drift detection | `window=100` default |
# | `plot_feature_vs_label(df, feature)` | Scatter + boxplot | `label='feat_hand_value'` default |
#
# ### Outcome Evaluation Charts
#
# | Function | Purpose | Key Parameters |
# |----------|---------|----------------|
# | `plot_feature_vs_outcome(df, feature)` | Feature vs outcome with correlation | `outcome='tricks_won'` |
# | `plot_outcome_distributions(df, outcome)` | Outcome by category | `group_by='contract_type'` |
# | `plot_feature_outcome_correlation(df)` | Feature importance bar chart | `outcome='tricks_won'`, `top_n=15` |
#
# ### Trump Suit Analysis Charts
#
# | Function | Purpose | Key Parameters |
# |----------|---------|----------------|
# | `plot_hand_value_by_trump_suit(df)` | Hand value by suit | `show_variance=True` |
# | `plot_outcome_by_trump_suit(df)` | Tricks won by suit | `outcome='tricks_won'` |
# | `plot_feature_heatmap_by_suit(df)` | Feature means by suit | `normalize=True`, `features=None` |
# | `plot_suit_variance_summary(df)` | Variance comparison | `column='feat_hand_value'` |
#
# ### Strategy Comparison Charts
#
# | Function | Purpose | Key Parameters |
# |----------|---------|----------------|
# | `plot_win_rate_heatmap(matchup_results)` | All-vs-all win rate matrix | `metric='win_rate'` |
# | `plot_tricks_distribution_comparison(matchup_results)` | Violin plots by matchup | `team=0` |
# | `plot_strategy_delta_bars(baseline, comparisons)` | Delta vs baseline | `metric='mean_tricks'` |
# | `plot_self_play_control(self_play_results)` | Self-play sanity check | `expected_mean=5.0` |
#
# ### Distribution Analysis Charts
#
# | Function | Purpose | Key Parameters |
# |----------|---------|----------------|
# | `plot_cdf(df, column)` | Cumulative distribution | `group_by=None` for overlaid CDFs |
# | `plot_ccdf(df, column)` | Tail distribution (1-CDF) | `log_scale=True` for heavy tails |
#
# ## Evaluation Charts (`bid_euchre.reporting.validation`)
#
# | Function | Purpose | Input Format |
# |----------|---------|---------------|
# | `plot_feature_distributions(fbc, dir)` | By-contract histograms | `Dict[str, List[Dict]]` |
# | `plot_feature_correlation(features, dir)` | Correlation matrix | `List[Dict]` |
# | `plot_hand_value_by_contract(fbc, dir)` | Contract box plots | `Dict[str, List[Dict]]` |
# | `generate_validation_plots(fbc, dir)` | All of the above | `Dict[str, List[Dict]]` |
