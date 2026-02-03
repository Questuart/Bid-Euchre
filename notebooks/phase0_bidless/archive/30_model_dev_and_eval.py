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
#     version: 3.12.0
# ---

# %% [markdown]
# # ⚠️ ARCHIVED EXPLORATORY ANALYSIS
#
# **Status:** This notebook contains exploratory visualizations from early model development.
#
# **Limitations:**
# - Plots are visual-only (no statistical tests)
# - No inference should be drawn from these results
# - Superseded by newer analysis in active notebooks
#
# **Use case:** Historical reference only

# %% [markdown]
# # Phase 0: Model Development & Evaluation
#
# **Purpose:** Exploratory notebook for developing and evaluating bidless hand value models.
#
# ⚠️ **This is NOT a quality gate.** Use `10_health_checks.ipynb` for dataset validation.
#
# **Usage:**
# - Explore feature engineering ideas
# - Build initial value models (hand + contract → expected tricks)
# - Compare policy performance (if adding strategy comparison)
# - Test hypotheses about feature importance
#
# **Template:** Feel free to modify this notebook for your experiments. For dated explorations, copy to `notebooks/sandbox/YYYY_MM_DD_topic.ipynb`.

# %%
# Auto-reload for development
# %load_ext autoreload
# %autoreload 2

# %%
# Standard imports
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from bid_euchre.features.hand_eval import get_hand_features

# Project imports
from bid_euchre.sim.deals import generate_deal

# Configure plots
plt.style.use('seaborn-v0_8-whitegrid')
sns.set_palette('husl')

# %% [markdown]
# ## Generate Sample Hands
#
# Use deterministic seeding for reproducibility.

# %%
# Generate some sample hands
SEED = 42
N_DEALS = 100

hands_data = []
for deal_id in range(N_DEALS):
    hands = generate_deal(SEED, deal_id)
    for seat in range(4):
        hand = hands[seat]
        # Get features for hearts trump
        features = get_hand_features(hand, 'suit', 'H')
        hands_data.append({
            'deal_id': deal_id,
            'seat': seat,
            'cards': [f"{c.rank}{c.suit}" for c in hand],
            **features
        })

df = pd.DataFrame(hands_data)
print(f"Generated {len(df)} hand records")
df.head()

# %% [markdown]
# ## Explore Feature Distributions

# %%
# Plot trump count distribution
fig, ax = plt.subplots(figsize=(8, 5))
df['trump_count'].hist(ax=ax, bins=range(8), align='left', rwidth=0.8)
ax.set_xlabel('Trump Count')
ax.set_ylabel('Frequency')
ax.set_title('Distribution of Trump Cards per Hand')
plt.tight_layout()

# %%
# Feature correlation heatmap
numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
numeric_cols = [c for c in numeric_cols if c not in ['deal_id', 'seat']]

fig, ax = plt.subplots(figsize=(10, 8))
corr = df[numeric_cols].corr()
sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0, ax=ax)
ax.set_title('Feature Correlations')
plt.tight_layout()

# %% [markdown]
# ## Next Steps
#
# ### For Feature Engineering:
# - Load full dataset: `load_bidless_dataset("../../data/runs/.../datasets")`
# - Compare features across contract types (suit vs high vs low)
# - Build correlation matrix with `tricks_won`
# - Explore feature interactions and derived features
#
# ### For Model Development:
# - Use helpers from `src/bid_euchre/diagnostics/stats.py`
# - Report effect sizes (R², Cohen's d) not just p-values
# - Bootstrap confidence intervals for robust inference
# - Cross-validate on different contract types
#
# ### For Policy Comparison:
# - Use `src/bid_euchre/diagnostics/strategy_charts.py` helpers
# - Self-play control: mean should be ~5.0 tricks (sanity check)
# - Report win rates with confidence intervals
# - Hypothesis: glutton > greedy > random (test with effect sizes, not thresholds)
#
# **Remember:** Exploratory analysis generates hypotheses; use rigorous tests to validate them.
#
# **Sample size guidance:**
# - Quick exploration: ≥1,000 samples per group
# - Feature correlation: ≥2,000 deals
# - Policy comparison: ≥5,000 deals per matchup
# - Production validation: ≥50,000 deals
#
# See `docs/rules/05_rigor.md` for detailed requirements.
