# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: tags
#     formats: ipynb,py:percent
#     notebook_metadata_filter: jupytext,kernelspec,language_info
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
#   language_info:
#     name: python
# ---

# %% [markdown]
# # Contract Selection Oracle Analysis — Step 0
#
# **Goal:** Measure the oracle contract mix and regret distribution to determine
# whether a calibrator for HIGH/LOW contract selection is warranted.
#
# **Decision gate (from `plans/contract_selection_analysis.md`):**
# - Mean regret > 0.1 utility → calibrator worth pursuing → Steps 1–2
# - Mean regret ≤ 0.1 AND HIGH/LOW oracle share < 3% → not needed → proceed to B3
# - Mean regret ≤ 0.1 AND HIGH/LOW oracle share ≥ 3% → adequate → proceed to B3
#
# **Data:** Canonical single-policy bidless dataset (GluttonStrategy, seed=42,
# 50k deals, pair_deals=True). Same physical hands evaluated under all 6 contracts.
#
# **Sections:**
# - S0: Setup & data loading
# - S1: Feature-outcome join & pivot (construction path)
# - S2: Model predictions & predicted utilities
# - S3: Realized net-differentials & oracle selection
# - S4: Regret analysis (oracle - model)
# - S5: Oracle contract mix
# - S6: Decision gate evaluation
# - S7: Diagnostic deep-dive (faceted regret, root cause attribution)

# %% tags=["parameters"]
MODE = "QUICK"  # SMOKE (~1k deals), QUICK (~10k deals), FULL (50k deals)

# %%
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

# Project imports
from bid_euchre.datasets.join import join_features_outcomes

# %% [markdown]
# ## S0: Setup & Configuration

# %%
# --- Paths ---
DATA_ROOT = Path("data/runs/canonical_bidless_dataset_glutton_42_20260221_175752")
BIDLESS_PATH = DATA_ROOT / "datasets" / "bidless.parquet"
OUTCOMES_PATH = DATA_ROOT / "datasets" / "bidless_outcomes.parquet"
ARTIFACT_PATH = Path("data/artifacts/arc_d/r0/hybrid_r0.json")
ARTIFACT_FULL_PATH = Path("data/artifacts/arc_d/r0/hybrid_r0_full.json")

for p in [BIDLESS_PATH, OUTCOMES_PATH, ARTIFACT_PATH]:
    assert p.exists(), f"Missing: {p}"

# --- Mode-dependent sample limits ---
MODE_LIMITS = {"SMOKE": 1_000, "QUICK": 10_000, "FULL": None}
DEAL_LIMIT = MODE_LIMITS[MODE]
print(f"MODE={MODE}, deal_limit={DEAL_LIMIT}")

# --- Load model artifact (constrained arm — primary analysis) ---
with open(ARTIFACT_PATH) as f:
    artifact = json.load(f)

with open(ARTIFACT_FULL_PATH) as f:
    artifact_full = json.load(f)

risk_lambda = artifact["risk_lambda"]
residual_var = artifact["residual_variance"]
sigma_by_contract = {k: math.sqrt(v) for k, v in residual_var.items()}

print(f"risk_lambda = {risk_lambda}")
print(f"sigma by contract: { {k: f'{v:.4f}' for k, v in sigma_by_contract.items()} }")

# %% [markdown]
# ## S1: Feature-Outcome Join & Pivot
#
# Construction path from `plans/contract_selection_analysis.md`:
# 1. Use existing `join_features_outcomes()` to get per-seat tricks_won
# 2. Pivot wide on `(contract_type, trump_suit)` → 6 outcome columns per `(deal_id, seat)`
# 3. Validate 6 rows per group pre-pivot

# %%
# Step 1: Join features ↔ outcomes
joined = join_features_outcomes(str(BIDLESS_PATH), str(OUTCOMES_PATH))
print(f"Joined rows: {len(joined):,}")
print(f"Columns: {list(joined.columns[:10])}... ({len(joined.columns)} total)")

# Apply deal limit for SMOKE/QUICK modes
if DEAL_LIMIT is not None:
    unique_deals = joined["deal_id"].unique()
    keep_deals = unique_deals[:DEAL_LIMIT]
    joined = joined[joined["deal_id"].isin(keep_deals)].copy()
    print(f"After deal limit ({DEAL_LIMIT}): {len(joined):,} rows")

# %%
# Step 2: Create a contract key for pivoting
# Suit contracts: "suit_C", "suit_D", "suit_H", "suit_S"
# Non-suit: "high", "low"
joined["contract_key"] = joined.apply(
    lambda r: f"{r['contract_type']}_{r['trump_suit']}"
    if r["contract_type"] == "suit"
    else r["contract_type"],
    axis=1,
)

expected_keys = {"suit_C", "suit_D", "suit_H", "suit_S", "high", "low"}
actual_keys = set(joined["contract_key"].unique())
assert actual_keys == expected_keys, f"Expected {expected_keys}, got {actual_keys}"

# %%
# Step 3: Validate 6 rows per (deal_id, seat) group, then pivot
group_sizes = joined.groupby(["deal_id", "seat"]).size()
complete_mask = group_sizes == 6
n_complete = complete_mask.sum()
n_incomplete = (~complete_mask).sum()
print(f"Complete groups (6 contracts): {n_complete:,}")
print(f"Incomplete groups (dropped): {n_incomplete:,}")

if n_incomplete > 0:
    # Keep only complete groups
    complete_groups = group_sizes[complete_mask].index
    joined = joined.set_index(["deal_id", "seat"]).loc[complete_groups].reset_index()
    print(f"After dropping incomplete: {len(joined):,} rows")

# Sanity: total hands
n_hands = len(joined) // 6
print(f"Total analysis hands: {n_hands:,}")
assert n_hands >= 1_000, f"Insufficient hands: {n_hands} (need ≥1,000)"
if MODE == "FULL":
    assert n_hands >= 50_000, f"FULL mode requires ≥50k hands, got {n_hands:,}"

# %%
# Step 4: Pivot tricks_won wide — one row per (deal_id, seat) with 6 outcome columns
tricks_wide = joined.pivot_table(
    index=["deal_id", "seat"],
    columns="contract_key",
    values="tricks_won",
    aggfunc="first",
).reset_index()

# Flatten column names
tricks_wide.columns = [
    f"tricks_{c}" if c not in ("deal_id", "seat") else c for c in tricks_wide.columns
]

print(f"Pivoted shape: {tricks_wide.shape}")
print(f"Columns: {list(tricks_wide.columns)}")

# Sanity: no NaN in trick columns
trick_cols = [c for c in tricks_wide.columns if c.startswith("tricks_")]
assert not tricks_wide[trick_cols].isna().any().any(), "NaN in pivoted tricks!"

# %% [markdown]
# ## S2: Model Predictions & Predicted Utilities
#
# For each (deal_id, seat) and each of the 6 contracts, compute:
# - `mu(c)` — OLS prediction from model artifact
# - `bid_n(c)` = floor(mu)
# - `utility(c)` = compute_ev(mu, sigma, bid_n) — the Gaussian expected net-differential
#
# Since `risk_lambda = 0` at R0, utility = EV (no CVaR penalty).

# %%
# Extract per-contract features from the joined data (pre-pivot)
# We need one feature row per (deal_id, seat, contract_key)

# Identify feature columns (everything except metadata and tricks_won)
meta_cols = {
    "hand_id",
    "deal_id",
    "seat",
    "dealer_seat",
    "contract_type",
    "trump_suit",
    "tricks_won",
    "contract_key",
    "hand_cards",
    "hand_feature_schema_version",
}
feature_cols = [c for c in joined.columns if c not in meta_cols]
print(f"Feature columns ({len(feature_cols)}): {feature_cols[:5]}...")


# %%
def compute_ev_vectorized(
    mu: np.ndarray, sigma: float, bid_n: np.ndarray
) -> np.ndarray:
    """Vectorized HybridOLSaBidder._compute_ev() — Gaussian expected net-differential.

    Matches bidding.py:910-952 exactly, operating on numpy arrays.
    sigma is scalar (same per contract family).
    """
    Z_CAP = 6.0

    if sigma == 0.0:
        return np.where(mu >= bid_n, 2.0 * mu - 10.0, mu - bid_n - 10.0)

    threshold = bid_n - 0.5
    z = (threshold - mu) / sigma
    z = np.clip(z, -Z_CAP, Z_CAP)

    p_make = 1.0 - norm.cdf(z)
    p_set = 1.0 - p_make
    pdf_z = norm.pdf(z)

    # Truncated normal expectations (safe division)
    e_tricks_make = np.where(p_make > 1e-12, mu + sigma * pdf_z / p_make, mu)
    e_tricks_set = np.where(p_set > 1e-12, mu - sigma * pdf_z / p_set, mu)

    make_ev = 2.0 * e_tricks_make - 10.0
    set_ev = e_tricks_set - bid_n - 10.0

    return p_make * make_ev + p_set * set_ev


def predict_mu(features: dict, contract_family: str, art: dict) -> float:
    """Predict tricks using OLS model from artifact."""
    model = art["payoff_model"][contract_family]
    mu = model["bias"]
    for w, fname in zip(model["weights"], model["feature_names"]):
        mu += w * features.get(fname, 0.0)
    return mu


def compute_actual_net(tricks_won: float, bid_n: int) -> float:
    """Compute realized net-differential payoff.

    Make (tricks >= bid): net = 2 * tricks - 10
    Set (tricks < bid):   net = tricks - bid - 10
    """
    if tricks_won >= bid_n:
        return 2.0 * tricks_won - 10.0
    else:
        return tricks_won - bid_n - 10.0


# %%
# Build per-hand predictions for all 6 contracts (vectorized per contract family)

pred_parts = []
for contract_family in ["suit", "high", "low"]:
    model = artifact["payoff_model"][contract_family]
    sigma = sigma_by_contract[contract_family]
    mask = joined["contract_type"] == contract_family
    subset = joined[mask].copy()

    if len(subset) == 0:
        continue

    # Vectorized mu computation: mu = bias + sum(w * feature)
    mu_vals = np.full(len(subset), model["bias"])
    for w, fname in zip(model["weights"], model["feature_names"]):
        mu_vals += w * subset[fname].values

    subset["mu"] = mu_vals
    subset["bid_n"] = np.floor(mu_vals).astype(int)
    subset["sigma"] = sigma

    # Fully vectorized utility computation
    subset["predicted_utility"] = compute_ev_vectorized(
        mu_vals, sigma, np.floor(mu_vals).astype(int)
    )

    pred_parts.append(
        subset[
            [
                "deal_id",
                "seat",
                "contract_key",
                "mu",
                "bid_n",
                "sigma",
                "predicted_utility",
                "tricks_won",
            ]
        ]
    )

pred_df = pd.concat(pred_parts, ignore_index=True)
print(f"Predictions: {len(pred_df):,} rows")

# %%
# Pivot predictions wide — one column per contract for mu, utility, tricks
pred_wide = pred_df.pivot_table(
    index=["deal_id", "seat"],
    columns="contract_key",
    values=["mu", "bid_n", "predicted_utility", "tricks_won"],
    aggfunc="first",
).reset_index()

# Flatten multi-level columns
pred_wide.columns = [
    f"{val}_{contract}" if contract else val for val, contract in pred_wide.columns
]

print(f"Prediction table shape: {pred_wide.shape}")

# %% [markdown]
# ## S3: Realized Net-Differentials & Oracle Selection
#
# For each hand and each contract:
# - Compute `actual_net(c)` = realized net-differential given model's bid for that contract
# - Oracle selects `c* = argmax(actual_net)`, or passes if all `actual_net ≤ 0`

# %%
CONTRACT_KEYS = ["suit_C", "suit_D", "suit_H", "suit_S", "high", "low"]

# Compute realized net-differential for each contract (vectorized)
for ck in CONTRACT_KEYS:
    tricks = pred_wide[f"tricks_won_{ck}"].values
    bid_n = pred_wide[f"bid_n_{ck}"].values.astype(int)
    pred_wide[f"actual_net_{ck}"] = np.where(
        tricks >= bid_n,
        2.0 * tricks - 10.0,
        tricks - bid_n - 10.0,
    )

# %%
# Model choice: argmax predicted_utility (pass if max utility <= 0)
utility_cols = [f"predicted_utility_{ck}" for ck in CONTRACT_KEYS]
actual_net_cols = [f"actual_net_{ck}" for ck in CONTRACT_KEYS]

pred_wide["model_choice"] = pred_wide[utility_cols].values.argmax(axis=1)
pred_wide["model_choice"] = pred_wide["model_choice"].map(
    {i: ck for i, ck in enumerate(CONTRACT_KEYS)}
)
pred_wide["model_max_utility"] = pred_wide[utility_cols].max(axis=1)
pred_wide["model_passes"] = pred_wide["model_max_utility"] <= 0

# Model's realized net (what actually happened with the model's choice)
# Vectorized: look up actual_net for model's chosen contract
_model_nets = np.zeros(len(pred_wide))
for i, ck in enumerate(CONTRACT_KEYS):
    mask = (pred_wide["model_choice"] == ck) & ~pred_wide["model_passes"]
    _model_nets[mask.values] = pred_wide.loc[mask, f"actual_net_{ck}"].values
pred_wide["model_actual_net"] = _model_nets

# %%
# Oracle choice: argmax actual_net (pass if max actual_net <= 0)
pred_wide["oracle_choice"] = pred_wide[actual_net_cols].values.argmax(axis=1)
pred_wide["oracle_choice"] = pred_wide["oracle_choice"].map(
    {i: ck for i, ck in enumerate(CONTRACT_KEYS)}
)
pred_wide["oracle_max_net"] = pred_wide[actual_net_cols].max(axis=1)
pred_wide["oracle_passes"] = pred_wide["oracle_max_net"] <= 0

# Oracle's realized net (vectorized)
_oracle_nets = np.zeros(len(pred_wide))
for i, ck in enumerate(CONTRACT_KEYS):
    mask = (pred_wide["oracle_choice"] == ck) & ~pred_wide["oracle_passes"]
    _oracle_nets[mask.values] = pred_wide.loc[mask, f"actual_net_{ck}"].values
pred_wide["oracle_actual_net"] = _oracle_nets

# %% [markdown]
# ## S4: Regret Analysis
#
# Regret = oracle_actual_net - model_actual_net
#
# This measures how much net-differential the model left on the table
# by choosing the wrong contract (or by passing when it shouldn't have,
# or by bidding when it should have passed).

# %%
pred_wide["regret"] = pred_wide["oracle_actual_net"] - pred_wide["model_actual_net"]

# Sanity: regret >= 0 (oracle is always at least as good as model)
assert (pred_wide["regret"] >= -1e-9).all(), "Negative regret found!"

n_hands = len(pred_wide)
mean_regret = pred_wide["regret"].mean()
median_regret = pred_wide["regret"].median()
p95_regret = pred_wide["regret"].quantile(0.95)
max_regret = pred_wide["regret"].max()
pct_zero_regret = (pred_wide["regret"] < 1e-9).mean() * 100

print(f"{'=' * 60}")
print(f"REGRET SUMMARY (n={n_hands:,} hands)")
print(f"{'=' * 60}")
print(f"  Mean regret:      {mean_regret:.4f} utility")
print(f"  Median regret:    {median_regret:.4f} utility")
print(f"  P95 regret:       {p95_regret:.4f} utility")
print(f"  Max regret:       {max_regret:.4f} utility")
print(f"  Zero-regret pct:  {pct_zero_regret:.1f}%")
print(f"{'=' * 60}")

# %%
# Bootstrap 95% CI for mean regret
rng = np.random.RandomState(42)
n_bootstrap = 10_000
boot_means = np.array(
    [
        pred_wide["regret"].sample(n=n_hands, replace=True, random_state=rng).mean()
        for _ in range(n_bootstrap)
    ]
)
ci_lo, ci_hi = np.percentile(boot_means, [2.5, 97.5])
print(f"Mean regret: {mean_regret:.4f} [{ci_lo:.4f}, {ci_hi:.4f}] (95% bootstrap CI)")

# %% [markdown]
# ### S4b: Regret Decomposition
#
# The total regret conflates three distinct error types. Decomposing reveals
# whether the gap comes from contract selection or the pass/bid threshold.
#
# | Category | Condition | Interpretation |
# |----------|-----------|----------------|
# | **Pass-threshold** | Model passes, oracle bids | Model too conservative (dominates) |
# | **Contract-selection** | Both bid, different contracts | Wrong contract among biddable hands |
# | **Over-bidding** | Model bids, oracle passes | Model too aggressive |
# | **Correct** | Same decision (incl. both pass) | No regret |

# %%
# Classify each hand (vectorized)
conditions = [
    pred_wide["model_passes"] & pred_wide["oracle_passes"],
    pred_wide["model_passes"] & ~pred_wide["oracle_passes"],
    ~pred_wide["model_passes"] & pred_wide["oracle_passes"],
    ~pred_wide["model_passes"]
    & ~pred_wide["oracle_passes"]
    & (pred_wide["model_choice"] == pred_wide["oracle_choice"]),
]
choices = [
    "correct_both_pass",
    "pass_threshold",
    "over_bidding",
    "correct_same_contract",
]
pred_wide["regret_category"] = np.select(
    conditions, choices, default="contract_selection"
)

# Decomposition summary
decomp = (
    pred_wide.groupby("regret_category")
    .agg(
        count=("regret", "size"),
        mean_regret=("regret", "mean"),
        total_regret=("regret", "sum"),
        median_regret=("regret", "median"),
    )
    .reset_index()
)
decomp["pct_hands"] = decomp["count"] / n_hands * 100
decomp["pct_total_regret"] = decomp["total_regret"] / pred_wide["regret"].sum() * 100
decomp = decomp.sort_values("total_regret", ascending=False)

print(f"\n{'=' * 80}")
print(f"REGRET DECOMPOSITION (n={n_hands:,} hands)")
print(f"{'=' * 80}")
print(f"{'Category':<25} {'Hands':>8} {'%Hands':>8} {'MeanReg':>10} {'%TotalReg':>10}")
print(f"{'-' * 61}")
for _, row in decomp.iterrows():
    print(
        f"{row['regret_category']:<25} {row['count']:>8,} {row['pct_hands']:>7.1f}% "
        f"{row['mean_regret']:>9.4f} {row['pct_total_regret']:>9.1f}%"
    )
print(f"{'=' * 80}")

# %%
# Contract-selection-only regret (the core question for calibrator design)
both_bid = pred_wide[~pred_wide["model_passes"] & ~pred_wide["oracle_passes"]]
n_both_bid = len(both_bid)
if n_both_bid > 0:
    cs_regret = both_bid["regret"]
    cs_mean = cs_regret.mean()
    cs_pct_wrong = (both_bid["model_choice"] != both_bid["oracle_choice"]).mean() * 100

    # Bootstrap CI for contract-selection regret
    boot_cs = np.array(
        [
            cs_regret.sample(n=n_both_bid, replace=True, random_state=rng).mean()
            for _ in range(n_bootstrap)
        ]
    )
    cs_ci_lo, cs_ci_hi = np.percentile(boot_cs, [2.5, 97.5])

    print(f"\n{'=' * 60}")
    print("CONTRACT-SELECTION-ONLY REGRET")
    print("  (restricted to hands where BOTH model and oracle bid)")
    print(f"{'=' * 60}")
    print(
        f"  Hands in scope:     {n_both_bid:,} ({n_both_bid / n_hands * 100:.1f}% of total)"
    )
    print(f"  Wrong contract:     {cs_pct_wrong:.1f}%")
    print(f"  Mean CS regret:     {cs_mean:.4f} [{cs_ci_lo:.4f}, {cs_ci_hi:.4f}]")
    print(f"  Gate threshold:     {0.1}")
    print(f"{'=' * 60}")
else:
    print("No hands where both model and oracle bid — cannot compute CS regret")
    cs_mean = 0.0
    cs_ci_lo = cs_ci_hi = 0.0

# %% [markdown]
# ## S5: Oracle Contract Mix

# %%
# Contract family for display (suit_C/D/H/S → suit)
pred_wide["oracle_family"] = pred_wide["oracle_choice"].apply(
    lambda x: "suit" if x.startswith("suit") else x
)
pred_wide["model_family"] = pred_wide["model_choice"].apply(
    lambda x: "suit" if x.startswith("suit") else x
)

# Handle pass cases
non_pass = pred_wide[~pred_wide["oracle_passes"]]
non_pass_model = pred_wide[~pred_wide["model_passes"]]

oracle_mix = non_pass["oracle_family"].value_counts(normalize=True).sort_index() * 100
model_mix = (
    non_pass_model["model_family"].value_counts(normalize=True).sort_index() * 100
)

# Also compute pass rates
oracle_pass_rate = pred_wide["oracle_passes"].mean() * 100
model_pass_rate = pred_wide["model_passes"].mean() * 100

print(f"\n{'=' * 60}")
print(f"CONTRACT MIX (n={n_hands:,} hands)")
print(f"{'=' * 60}")
print(f"{'Contract':<12} {'Oracle %':>10} {'Model %':>10} {'Delta':>10}")
print(f"{'-' * 42}")
for contract in ["high", "low", "suit"]:
    o_pct = oracle_mix.get(contract, 0.0)
    m_pct = model_mix.get(contract, 0.0)
    print(f"{contract:<12} {o_pct:>9.1f}% {m_pct:>9.1f}% {o_pct - m_pct:>+9.1f}pp")
print(
    f"{'PASS':<12} {oracle_pass_rate:>9.1f}% {model_pass_rate:>9.1f}% "
    f"{oracle_pass_rate - model_pass_rate:>+9.1f}pp"
)
print(f"{'=' * 60}")

# Oracle HIGH+LOW combined share (excluding passes)
oracle_hl_share = oracle_mix.get("high", 0.0) + oracle_mix.get("low", 0.0)
print(f"\nOracle HIGH+LOW share: {oracle_hl_share:.1f}%")

# %%
# Detailed oracle mix by specific contract (suit broken out by trump)
oracle_detailed = (
    non_pass["oracle_choice"].value_counts(normalize=True).sort_index() * 100
)
model_detailed = (
    non_pass_model["model_choice"].value_counts(normalize=True).sort_index() * 100
)

print(f"\n{'=' * 60}")
print("DETAILED CONTRACT MIX")
print(f"{'=' * 60}")
print(f"{'Contract':<12} {'Oracle %':>10} {'Model %':>10}")
print(f"{'-' * 32}")
for ck in CONTRACT_KEYS:
    o = oracle_detailed.get(ck, 0.0)
    m = model_detailed.get(ck, 0.0)
    print(f"{ck:<12} {o:>9.1f}% {m:>9.1f}%")

# %% [markdown]
# ## S6: Decision Gate Evaluation

# %%
REGRET_THRESHOLD = 0.1  # utility units
HL_THRESHOLD = 0.03  # 3% combined HIGH+LOW oracle share

print(f"\n{'=' * 70}")
print("DECISION GATE — Step 0")
print(f"{'=' * 70}")
print(
    f"  TOTAL mean regret:          {mean_regret:.4f} (threshold: {REGRET_THRESHOLD})"
)
print(f"  TOTAL regret CI:            [{ci_lo:.4f}, {ci_hi:.4f}]")
print(f"  CONTRACT-SELECTION regret:  {cs_mean:.4f} [{cs_ci_lo:.4f}, {cs_ci_hi:.4f}]")
print(
    f"  Oracle H+L share:           {oracle_hl_share:.1f}% (threshold: {HL_THRESHOLD * 100:.0f}%)"
)
print(f"  Model pass rate:            {model_pass_rate:.1f}%")
print(f"  Oracle pass rate:           {oracle_pass_rate:.1f}%")
print()

# Apply the decision gate using TOTAL regret per the plan
if mean_regret > REGRET_THRESHOLD:
    decision = "CALIBRATOR_WARRANTED"
    rationale = (
        f"Mean total regret {mean_regret:.4f} > {REGRET_THRESHOLD} threshold. "
        "However, regret decomposition (S4b) reveals the dominant source."
    )
elif oracle_hl_share < HL_THRESHOLD * 100:
    decision = "NOT_NEEDED"
    rationale = (
        f"Mean regret {mean_regret:.4f} ≤ {REGRET_THRESHOLD} AND "
        f"oracle HIGH/LOW share {oracle_hl_share:.1f}% < {HL_THRESHOLD * 100:.0f}%. "
        "Calibrator not needed. Proceed to B3 with current data."
    )
else:
    decision = "ADEQUATE"
    rationale = (
        f"Mean regret {mean_regret:.4f} ≤ {REGRET_THRESHOLD} AND "
        f"oracle HIGH/LOW share {oracle_hl_share:.1f}% ≥ {HL_THRESHOLD * 100:.0f}%. "
        "Contract selection matters but current model captures it adequately. "
        "Proceed to B3 with current data. Document oracle mix for future reference."
    )

print(f"  DECISION: {decision}")
print(f"  {rationale}")
print()
print("  INTERPRETATION NOTE:")
print("  The decomposition in S4b separates pass-threshold regret (model too")
print("  conservative) from contract-selection regret (wrong contract among")
print("  biddable hands). If pass-threshold dominates, the fix is better model")
print("  accuracy or threshold tuning, NOT a calibrator. Review S4b before")
print("  committing to the calibrator path.")
print(f"{'=' * 70}")

# Machine-readable gate result
gate_result = {
    "decision": decision,
    "mean_regret_total": round(mean_regret, 6),
    "mean_regret_total_ci": [round(ci_lo, 6), round(ci_hi, 6)],
    "mean_regret_contract_selection": round(cs_mean, 6),
    "mean_regret_cs_ci": [round(cs_ci_lo, 6), round(cs_ci_hi, 6)],
    "oracle_hl_share_pct": round(oracle_hl_share, 2),
    "model_pass_rate_pct": round(model_pass_rate, 2),
    "oracle_pass_rate_pct": round(oracle_pass_rate, 2),
    "n_hands": n_hands,
    "mode": MODE,
}
print(f"\nGate result (JSON): {json.dumps(gate_result, indent=2)}")

# %% [markdown]
# ## S7: Diagnostic Deep-Dive

# %%
# Regret distribution histogram
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Left: full distribution
ax = axes[0]
ax.hist(pred_wide["regret"], bins=100, edgecolor="black", alpha=0.7)
ax.axvline(mean_regret, color="red", linestyle="--", label=f"Mean={mean_regret:.4f}")
ax.axvline(
    REGRET_THRESHOLD,
    color="orange",
    linestyle=":",
    label=f"Threshold={REGRET_THRESHOLD}",
)
ax.set_xlabel("Regret (utility)")
ax.set_ylabel("Count")
ax.set_title("Regret Distribution (all hands)")
ax.legend()

# Right: non-zero regret only
nonzero = pred_wide[pred_wide["regret"] > 1e-9]["regret"]
ax = axes[1]
if len(nonzero) > 0:
    ax.hist(nonzero, bins=80, edgecolor="black", alpha=0.7, color="coral")
    ax.axvline(
        nonzero.mean(),
        color="red",
        linestyle="--",
        label=f"Mean(non-zero)={nonzero.mean():.4f}",
    )
    ax.set_xlabel("Regret (utility)")
    ax.set_ylabel("Count")
    ax.set_title(
        f"Non-Zero Regret (n={len(nonzero):,}, {len(nonzero) / n_hands * 100:.1f}%)"
    )
    ax.legend()
else:
    ax.text(
        0.5, 0.5, "No non-zero regret", ha="center", va="center", transform=ax.transAxes
    )
    ax.set_title("Non-Zero Regret")

plt.tight_layout()
plt.show()

# %%
# Regret faceted by (model_choice_family, oracle_choice_family) — the confusion matrix
confusion = (
    pred_wide.groupby(["model_family", "oracle_family"])
    .agg(
        count=("regret", "size"),
        mean_regret=("regret", "mean"),
        total_regret=("regret", "sum"),
    )
    .reset_index()
)

confusion["pct_of_total"] = confusion["count"] / n_hands * 100
confusion = confusion.sort_values("total_regret", ascending=False)

print(f"\n{'=' * 70}")
print("REGRET BY (MODEL CHOICE → ORACLE CHOICE) — Top Contributors")
print(f"{'=' * 70}")
print(
    f"{'Model→Oracle':<20} {'Count':>8} {'%Hands':>8} {'MeanReg':>10} {'TotalReg':>10}"
)
print(f"{'-' * 56}")
for _, row in confusion.head(10).iterrows():
    pair = f"{row['model_family']}→{row['oracle_family']}"
    print(
        f"{pair:<20} {row['count']:>8,} {row['pct_of_total']:>7.1f}% "
        f"{row['mean_regret']:>9.4f} {row['total_regret']:>9.1f}"
    )

# %%
# Regret by contract family — where does regret concentrate?
regret_by_model = (
    pred_wide.groupby("model_family")
    .agg(
        count=("regret", "size"),
        mean_regret=("regret", "mean"),
        pct_nonzero=("regret", lambda x: (x > 1e-9).mean() * 100),
    )
    .reset_index()
)

print(f"\n{'=' * 50}")
print("REGRET BY MODEL'S CHOSEN CONTRACT FAMILY")
print(f"{'=' * 50}")
print(regret_by_model.to_string(index=False))

# %%
# Mean predicted utility vs mean actual net by contract — are predictions calibrated?
calibration = (
    pred_df.groupby("contract_key")
    .agg(
        mean_mu=("mu", "mean"),
        mean_bid_n=("bid_n", "mean"),
        mean_pred_utility=("predicted_utility", "mean"),
        mean_tricks=("tricks_won", "mean"),
    )
    .reset_index()
)

# Compute mean actual net per contract from wide table
for ck in CONTRACT_KEYS:
    vals = pred_wide[f"actual_net_{ck}"]
    calibration.loc[calibration["contract_key"] == ck, "mean_actual_net"] = vals.mean()

print(f"\n{'=' * 70}")
print("CALIBRATION TABLE — Predicted vs Realized")
print(f"{'=' * 70}")
print(calibration.to_string(index=False, float_format="{:.3f}".format))

# %%
# Visualization: oracle vs model contract mix (bar chart)
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(3)
width = 0.35

families = ["high", "low", "suit"]
oracle_vals = [oracle_mix.get(f, 0.0) for f in families]
model_vals = [model_mix.get(f, 0.0) for f in families]

bars1 = ax.bar(x - width / 2, oracle_vals, width, label="Oracle", color="steelblue")
bars2 = ax.bar(x + width / 2, model_vals, width, label="Model", color="coral")

ax.set_ylabel("Share (%)")
ax.set_title("Contract Mix: Oracle vs Model")
ax.set_xticks(x)
ax.set_xticklabels(families)
ax.legend()

# Add value labels
for bar in bars1:
    height = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        height + 0.5,
        f"{height:.1f}%",
        ha="center",
        va="bottom",
        fontsize=9,
    )
for bar in bars2:
    height = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        height + 0.5,
        f"{height:.1f}%",
        ha="center",
        va="bottom",
        fontsize=9,
    )

plt.tight_layout()
plt.show()

# %% [markdown]
# ## Summary
#
# This notebook computed the oracle contract mix and regret distribution for the
# OLSa constrained bidder (R0). The decision gate result above determines whether
# a calibrator for HIGH/LOW contract selection is warranted.
