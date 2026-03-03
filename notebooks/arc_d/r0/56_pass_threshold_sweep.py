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
# # Pass-Threshold Tuning Sweep — B0 (v2: bid-level search)
#
# **Protocol:** `plans/r0_pass_threshold_protocol.md` v1 (pre-registered).
# v2 lineage: `plans/r0_canonical_v2_plan.md` §4a defines a v2 threshold
# protocol amendment; this notebook uses v1 protocol logic with v2 bid-level
# search policy (Amendment D: threshold before lambda).
#
# **v2 change:** Bid-level search enabled (`bid_level_search=True`). The bidder
# now searches all legal bid levels (1–10) for each contract, picking the level
# with highest utility. Previously, only `floor(mu)` was evaluated (v1 behavior).
# This matches the production `HybridOLSaBidder.choose_bid()` with bid-level
# search and `risk_lambda=0.0`.
#
# **Goal:** Determine whether shifting the pass gate from `utility <= 0`
# to `utility <= -t` (for some `t > 0`) recovers meaningful value from
# the 82% of regret attributed to the pass-threshold (PR #472).
#
# **Decision gate:**
# - **ADOPT** — delta > 0.05 SESOI, CI excludes 0, guardrails pass
# - **NOTE** — delta > 0 with CI excluding 0, but delta < SESOI
# - **RETAIN** — CI includes 0 or delta < 0
#
# **Sections:**
# - S0: Setup & data loading
# - S1: Feature-outcome join & pivot
# - S2: Model predictions & utilities (v2: bid-level search)
# - S3: Train/validation split
# - S4: Threshold sweep on train partition
# - S5: Guardrails & threshold selection
# - S6: Validation of selected threshold
# - S7: Decision gate
# - S8: Visualizations

# %% tags=["parameters"]
MODE = "QUICK"  # SMOKE (~1k deals), QUICK (~10k deals), FULL (50k deals)
CHART_OUTPUT_DIR = ""  # Set via papermill; empty = skip chart save

# %%
import hashlib
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import norm

from bid_euchre.datasets.join import join_features_outcomes

# %% [markdown]
# ## S0: Setup & Configuration

# %%
# --- Paths ---
DATA_ROOT = Path("data/runs/canonical_bidless_dataset_glutton_42_20260221_175752")
BIDLESS_PATH = DATA_ROOT / "datasets" / "bidless.parquet"
OUTCOMES_PATH = DATA_ROOT / "datasets" / "bidless_outcomes.parquet"
ARTIFACT_PATH = Path("data/artifacts/arc_d/r0/hybrid_r0.json")

for p in [BIDLESS_PATH, OUTCOMES_PATH, ARTIFACT_PATH]:
    assert p.exists(), f"Missing: {p}"

# --- Mode-dependent sample limits ---
MODE_LIMITS = {"SMOKE": 1_000, "QUICK": 10_000, "FULL": None}
DEAL_LIMIT = MODE_LIMITS[MODE]
print(f"MODE={MODE}, deal_limit={DEAL_LIMIT}")

# --- Protocol constants (locked by pre-registration) ---
THRESHOLD_GRID = [0.00, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 2.50, 3.00, 4.00, 5.00]
SPLIT_SEED = 42
BOOTSTRAP_SEED = 42
N_BOOTSTRAP = 10_000
SESOI = 0.05  # Smallest effect size of interest (net_diff per hand)

# Guardrails
MAKE_RATE_FLOOR = 0.60  # Hard: make_rate >= 60%
OVERBID_REGRET_CAP = 0.10  # Hard: overbid_regret_share <= 10%
BID_RATE_CAP = 0.95  # Soft: bid_rate <= 95%

# --- Load model artifact ---
with open(ARTIFACT_PATH) as f:
    artifact = json.load(f)

risk_lambda = artifact["risk_lambda"]
residual_var = artifact["residual_variance"]
sigma_by_contract = {k: math.sqrt(v) for k, v in residual_var.items()}

print(f"risk_lambda = {risk_lambda}")
print(f"sigma by contract: { {k: f'{v:.4f}' for k, v in sigma_by_contract.items()} }")
print(f"Threshold grid: {THRESHOLD_GRID}")
print(f"SESOI: {SESOI}")

# %% [markdown]
# ## S1: Feature-Outcome Join & Pivot
#
# Same pipeline as notebook 55 — join features ↔ outcomes, create contract keys,
# validate 6 rows per (deal_id, seat), pivot wide.

# %%
# Step 1: Join features ↔ outcomes
joined = join_features_outcomes(str(BIDLESS_PATH), str(OUTCOMES_PATH))
print(f"Joined rows: {len(joined):,}")

# Apply deal limit for SMOKE/QUICK modes
if DEAL_LIMIT is not None:
    unique_deals = joined["deal_id"].unique()
    keep_deals = unique_deals[:DEAL_LIMIT]
    joined = joined[joined["deal_id"].isin(keep_deals)].copy()
    print(f"After deal limit ({DEAL_LIMIT}): {len(joined):,} rows")

# %%
# Step 2: Create contract key for pivoting
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
# Step 3: Validate 6 rows per group, pivot
group_sizes = joined.groupby(["deal_id", "seat"]).size()
complete_mask = group_sizes == 6
n_complete = complete_mask.sum()
n_incomplete = (~complete_mask).sum()
print(f"Complete groups (6 contracts): {n_complete:,}")
print(f"Incomplete groups (dropped): {n_incomplete:,}")

if n_incomplete > 0:
    complete_groups = group_sizes[complete_mask].index
    joined = joined.set_index(["deal_id", "seat"]).loc[complete_groups].reset_index()
    print(f"After dropping incomplete: {len(joined):,} rows")

n_hands = len(joined) // 6
print(f"Total analysis hands: {n_hands:,}")
assert n_hands >= 1_000, f"Insufficient hands: {n_hands} (need ≥1,000)"

# %% [markdown]
# ## S2: Model Predictions & Utilities
#
# **v2 change:** Bid-level search replaces `floor(mu)` single-level evaluation.
# For each hand and contract, we search all legal bid levels (1–10) and pick the
# level with highest utility. This matches `compute_best_bid()` in
# `bidding.py:788-850` with `risk_lambda=0.0`.
#
# The vectorized implementation below evaluates all 10 levels simultaneously via
# numpy broadcasting, producing identical results to calling `compute_best_bid()`
# per-hand (validated by spot-check below).
#
# **Pooling justification:** Metrics (net_diff, bid_rate, make_rate, regret shares)
# are reported pooled across contract types because the threshold `t` tunes the
# *cross-contract pass/bid decision* — each hand selects the single best contract
# among all 6 candidates. Per-contract-type breakout is not meaningful here since
# the unit of analysis is the hand-level bid/pass decision, not individual contract
# performance.

# %%
CONTRACT_KEYS = ["suit_C", "suit_D", "suit_H", "suit_S", "high", "low"]

from bid_euchre.strategy.bidding import compute_best_bid


def compute_ev_vectorized(
    mu: np.ndarray, sigma: float, bid_n: np.ndarray
) -> np.ndarray:
    """Vectorized HybridOLSaBidder._compute_ev() — Gaussian expected net-differential.

    Matches bidding.py _compute_ev_static() exactly.
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

    e_tricks_make = np.where(p_make > 1e-12, mu + sigma * pdf_z / p_make, mu)
    e_tricks_set = np.where(p_set > 1e-12, mu - sigma * pdf_z / p_set, mu)

    make_ev = 2.0 * e_tricks_make - 10.0
    set_ev = e_tricks_set - bid_n - 10.0

    return p_make * make_ev + p_set * set_ev


def bid_level_search_vectorized(
    mu_vals: np.ndarray, sigma: float, risk_lambda: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized bid-level search across all legal levels (1–10).

    For each hand, evaluates utility at every bid level and selects the level
    with highest utility. Tie-break: prefer higher bid level (matches
    compute_best_bid() at bidding.py:839-843).

    Returns:
        (best_bid_n, best_utility) arrays of shape (n_hands,)
    """
    n = len(mu_vals)
    best_bid_n = np.ones(n, dtype=int)
    best_utility = np.full(n, -np.inf)

    # Guard: risk_lambda != 0 requires CVaR penalty implementation (not yet vectorized).
    # Remove this assert and add penalty logic when lambda tuning is integrated.
    assert risk_lambda == 0.0, (
        f"risk_lambda={risk_lambda} but CVaR penalty not implemented in vectorized helper. "
        "Use compute_best_bid() from bidding.py for non-zero lambda."
    )

    # Iterate ascending; use >= so last (highest n) with max utility wins
    # This matches compute_best_bid() tie-break: prefer higher n on equal utility
    for bid_n in range(1, 11):
        ev = compute_ev_vectorized(mu_vals, sigma, np.full(n, bid_n))
        utility = ev  # At lambda=0, utility = EV (no CVaR penalty)
        better_or_tie = utility >= best_utility
        best_utility = np.where(better_or_tie, utility, best_utility)
        best_bid_n = np.where(better_or_tie, bid_n, best_bid_n)

    return best_bid_n, best_utility


# %%
# Build per-hand predictions for all 6 contracts
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
pred_parts = []
for contract_family in ["suit", "high", "low"]:
    model = artifact["payoff_model"][contract_family]
    sigma = sigma_by_contract[contract_family]
    mask = joined["contract_type"] == contract_family
    subset = joined[mask].copy()

    if len(subset) == 0:
        continue

    # Vectorized mu = bias + sum(w * feature)
    mu_vals = np.full(len(subset), model["bias"])
    for w, fname in zip(model["weights"], model["feature_names"]):
        mu_vals += w * subset[fname].values

    subset["mu"] = mu_vals
    subset["sigma"] = sigma

    # v2: Bid-level search — evaluate all legal levels, pick best utility
    best_bid_n, best_utility = bid_level_search_vectorized(mu_vals, sigma)
    subset["bid_n"] = best_bid_n
    subset["predicted_utility"] = best_utility

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
# Spot-check: vectorized results match compute_best_bid() (scalar reference impl)
_sample = pred_df.sample(min(100, len(pred_df)), random_state=42)
_mismatches = 0
for _, row in _sample.iterrows():
    result = compute_best_bid(
        mu=row["mu"],
        sigma=row["sigma"],
        current_high_bid=0,
        pass_threshold=0.0,
        bid_level_search=True,
        risk_lambda=0.0,
    )
    if result is None:
        # compute_best_bid returns None when utility <= 0
        # vectorized always returns a value; check utility is <= 0
        assert (
            row["predicted_utility"] <= 0 + 1e-9
        ), f"Mismatch: compute_best_bid=None but vectorized utility={row['predicted_utility']}"
    else:
        ref_n, ref_util = result
        assert (
            ref_n == row["bid_n"]
        ), f"bid_n mismatch: {ref_n} vs {row['bid_n']} (mu={row['mu']:.4f})"
        assert (
            abs(ref_util - row["predicted_utility"]) < 1e-9
        ), f"utility mismatch: {ref_util} vs {row['predicted_utility']}"
print(
    f"Spot-check: {len(_sample)} hands validated against compute_best_bid() — all match"
)

# %%
# Pivot predictions wide
pred_wide = pred_df.pivot_table(
    index=["deal_id", "seat"],
    columns="contract_key",
    values=["mu", "bid_n", "predicted_utility", "tricks_won"],
    aggfunc="first",
).reset_index()

pred_wide.columns = [
    f"{val}_{contract}" if contract else val for val, contract in pred_wide.columns
]

print(f"Prediction table shape: {pred_wide.shape}")

# Sanity: should have one row per hand
assert len(pred_wide) == n_hands, f"Expected {n_hands} hands, got {len(pred_wide)}"

# %%
# Compute realized net-differential for each contract
for ck in CONTRACT_KEYS:
    tricks = pred_wide[f"tricks_won_{ck}"].values
    bid_n = pred_wide[f"bid_n_{ck}"].values.astype(int)
    pred_wide[f"actual_net_{ck}"] = np.where(
        tricks >= bid_n,
        2.0 * tricks - 10.0,
        tricks - bid_n - 10.0,
    )

# %% [markdown]
# ## S3: Train/Validation Split
#
# Protocol: deterministic hash-based split, 60/40 by `deal_id`.
# Buckets 0-2 → train, 3-4 → validation. Grouped by deal_id to prevent leakage.


# %%
def deal_partition(deal_id: str, seed: int = SPLIT_SEED) -> str:
    """Deterministic partition assignment based on deal_id hash."""
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"


pred_wide["partition"] = pred_wide["deal_id"].apply(deal_partition)

n_train = (pred_wide["partition"] == "train").sum()
n_val = (pred_wide["partition"] == "val").sum()
n_train_deals = pred_wide.loc[pred_wide["partition"] == "train", "deal_id"].nunique()
n_val_deals = pred_wide.loc[pred_wide["partition"] == "val", "deal_id"].nunique()

print(
    f"Train: {n_train:,} hands ({n_train_deals:,} deals, {n_train / len(pred_wide):.1%})"
)
print(f"Val:   {n_val:,} hands ({n_val_deals:,} deals, {n_val / len(pred_wide):.1%})")

# Sanity: no overlap
assert pred_wide.groupby("deal_id")["partition"].nunique().max() == 1, "Deal leakage!"

# %% [markdown]
# ## S4: Threshold Sweep on Train Partition
#
# For each candidate threshold `t`, simulate the bidding decision:
# - If `max_utility > -t`: bid on argmax contract → actual_net for that contract
# - If `max_utility <= -t`: pass → net = 0
#
# Compute primary + secondary endpoints.

# %%
utility_cols = [f"predicted_utility_{ck}" for ck in CONTRACT_KEYS]
actual_net_cols = [f"actual_net_{ck}" for ck in CONTRACT_KEYS]


def evaluate_threshold(df: pd.DataFrame, t: float) -> dict:
    """Evaluate a single threshold on a DataFrame of hands.

    Returns dict of primary + secondary endpoints.
    """
    n = len(df)

    # Model's best utility and choice
    utilities = df[utility_cols].values  # (n, 6)
    actual_nets = df[actual_net_cols].values  # (n, 6)

    max_utility = utilities.max(axis=1)
    best_contract_idx = utilities.argmax(axis=1)

    # Pass/bid decision at threshold t
    passes = max_utility <= -t
    bids = ~passes

    n_bid = bids.sum()
    n_pass = passes.sum()
    bid_rate = n_bid / n

    # Net for each hand: bid → actual_net of chosen contract; pass → 0
    model_net = np.zeros(n)
    if n_bid > 0:
        model_net[bids] = actual_nets[bids, best_contract_idx[bids]]

    # Oracle (same as notebook 55)
    oracle_max_net = actual_nets.max(axis=1)
    oracle_passes = oracle_max_net <= 0
    oracle_best_idx = actual_nets.argmax(axis=1)

    oracle_net = np.zeros(n)
    oracle_bids = ~oracle_passes
    if oracle_bids.sum() > 0:
        oracle_net[oracle_bids] = actual_nets[oracle_bids, oracle_best_idx[oracle_bids]]

    # Primary endpoint
    net_diff_mean = model_net.mean()

    # Regret decomposition
    regret = oracle_net - model_net
    total_regret = regret.sum()

    # Classify regret categories
    model_passes_mask = passes
    oracle_passes_mask = oracle_passes

    pass_threshold_mask = model_passes_mask & ~oracle_passes_mask
    over_bidding_mask = ~model_passes_mask & oracle_passes_mask
    both_bid_mask = ~model_passes_mask & ~oracle_passes_mask

    pass_regret = regret[pass_threshold_mask].sum()
    overbid_regret = regret[over_bidding_mask].sum()
    cs_regret = regret[both_bid_mask].sum()

    # Make rate: among hands that bid, fraction that make their contract
    make_rate = np.nan
    if n_bid > 0:
        bid_n_chosen = np.array(
            [
                df[f"bid_n_{CONTRACT_KEYS[best_contract_idx[i]]}"].iloc[i]
                for i in range(n)
                if bids[i]
            ]
        )
        tricks_chosen = np.array(
            [
                df[f"tricks_won_{CONTRACT_KEYS[best_contract_idx[i]]}"].iloc[i]
                for i in range(n)
                if bids[i]
            ]
        )
        make_rate = (tricks_chosen >= bid_n_chosen).mean()

    return {
        "t": t,
        "net_diff_mean": net_diff_mean,
        "bid_rate": bid_rate,
        "make_rate": make_rate,
        "mean_regret": regret.mean(),
        "total_regret": total_regret,
        "pass_regret_share": pass_regret / total_regret if total_regret > 0 else 0.0,
        "cs_regret_share": cs_regret / total_regret if total_regret > 0 else 0.0,
        "overbid_regret_share": overbid_regret / total_regret
        if total_regret > 0
        else 0.0,
        "n_bid": int(n_bid),
        "n_pass": int(n_pass),
        "n_total": n,
    }


# %%
# Run sweep on train partition
train_df = pred_wide[pred_wide["partition"] == "train"].copy()

train_results = []
for t in THRESHOLD_GRID:
    result = evaluate_threshold(train_df, t)
    train_results.append(result)

train_sweep = pd.DataFrame(train_results)

print(f"\n{'=' * 90}")
print(f"TRAIN PARTITION SWEEP (n={n_train:,} hands)")
print(f"{'=' * 90}")
print(
    f"{'t':>6} {'net_diff':>10} {'bid_rate':>10} {'make_rate':>10} "
    f"{'pass_reg%':>10} {'cs_reg%':>10} {'overbid%':>10}"
)
print(f"{'-' * 90}")
for _, row in train_sweep.iterrows():
    print(
        f"{row['t']:>6.2f} {row['net_diff_mean']:>10.4f} {row['bid_rate']:>10.3f} "
        f"{row['make_rate']:>10.3f} {row['pass_regret_share']:>10.3f} "
        f"{row['cs_regret_share']:>10.3f} {row['overbid_regret_share']:>10.3f}"
    )
print(f"{'=' * 90}")

# %% [markdown]
# ## S5: Guardrails & Threshold Selection
#
# Apply **hard** guardrails (make_rate, overbid) to discard unsafe candidates.
# Bid rate cap is **soft** (flagged but not disqualifying per protocol v1 §2.6).
# Select `t*` as the candidate with highest `net_diff_mean` among survivors.

# %%
# Apply guardrails — hard floors disqualify, soft cap is advisory only
train_sweep["pass_make_rate"] = train_sweep["make_rate"] >= MAKE_RATE_FLOOR
train_sweep["pass_overbid"] = train_sweep["overbid_regret_share"] <= OVERBID_REGRET_CAP
train_sweep["pass_bid_rate"] = (
    train_sweep["bid_rate"] <= BID_RATE_CAP
)  # Soft cap (advisory)
train_sweep["all_guardrails"] = (
    train_sweep["pass_make_rate"] & train_sweep["pass_overbid"]  # Hard floors only
)

survivors = train_sweep[train_sweep["all_guardrails"]]
disqualified = train_sweep[~train_sweep["all_guardrails"]]

print(f"Survivors: {len(survivors)} / {len(train_sweep)} candidates")
if len(disqualified) > 0:
    print(f"Disqualified (hard guardrail violation): {list(disqualified['t'].values)}")
    for _, row in disqualified.iterrows():
        reasons = []
        if not row["pass_make_rate"]:
            reasons.append(f"make_rate={row['make_rate']:.3f} < {MAKE_RATE_FLOOR}")
        if not row["pass_overbid"]:
            reasons.append(
                f"overbid_share={row['overbid_regret_share']:.3f} > {OVERBID_REGRET_CAP}"
            )
        print(f"  t={row['t']:.2f}: {', '.join(reasons)}")

# Soft cap advisory: flag but don't disqualify
soft_cap_violations = train_sweep[
    ~train_sweep["pass_bid_rate"] & train_sweep["all_guardrails"]
]
if len(soft_cap_violations) > 0:
    print(
        f"Soft cap advisory (bid_rate > {BID_RATE_CAP}): {list(soft_cap_violations['t'].values)}"
    )
    print("  (These remain eligible per protocol v1 §2.6 — soft cap is non-blocking)")

# %%
# Select t* — best net_diff_mean among survivors
if len(survivors) == 0:
    print("WARNING: No candidates pass all guardrails. Retaining t=0.")
    t_star = 0.0
else:
    best_row = survivors.loc[survivors["net_diff_mean"].idxmax()]
    t_star = best_row["t"]

t_star_result = train_sweep[train_sweep["t"] == t_star].iloc[0]
baseline_result = train_sweep[train_sweep["t"] == 0.0].iloc[0]

train_delta = t_star_result["net_diff_mean"] - baseline_result["net_diff_mean"]

print(f"\n{'=' * 60}")
print("TRAIN SELECTION")
print(f"{'=' * 60}")
print(f"  t* (selected):        {t_star:.2f}")
print(f"  net_diff(t*):         {t_star_result['net_diff_mean']:.4f}")
print(f"  net_diff(t=0):        {baseline_result['net_diff_mean']:.4f}")
print(f"  Train delta:          {train_delta:+.4f}")
print(f"  bid_rate(t*):         {t_star_result['bid_rate']:.3f}")
print(f"  make_rate(t*):        {t_star_result['make_rate']:.3f}")
print(f"{'=' * 60}")

# %% [markdown]
# ## S6: Validation of Selected Threshold
#
# Evaluate `t*` and `t=0` on the held-out validation partition.
# Bootstrap 95% CI on the delta, grouped by deal_id.

# %%
val_df = pred_wide[pred_wide["partition"] == "val"].copy()

val_t_star = evaluate_threshold(val_df, t_star)
val_baseline = evaluate_threshold(val_df, 0.0)

val_delta = val_t_star["net_diff_mean"] - val_baseline["net_diff_mean"]

print(f"\n{'=' * 60}")
print(f"VALIDATION PARTITION (n={n_val:,} hands)")
print(f"{'=' * 60}")
print(f"  t*:                   {t_star:.2f}")
print(f"  net_diff(t*):         {val_t_star['net_diff_mean']:.4f}")
print(f"  net_diff(t=0):        {val_baseline['net_diff_mean']:.4f}")
print(f"  Val delta:            {val_delta:+.4f}")
print(f"  bid_rate(t*):         {val_t_star['bid_rate']:.3f}")
print(f"  make_rate(t*):        {val_t_star['make_rate']:.3f}")
print(f"  overbid_regret_share: {val_t_star['overbid_regret_share']:.3f}")
print(f"{'=' * 60}")

# %%
# Bootstrap 95% CI on delta, grouped by deal_id
# Resample deals (not hands) to respect grouping
rng = np.random.RandomState(BOOTSTRAP_SEED)

val_deal_ids = val_df["deal_id"].unique()
n_val_deals_arr = len(val_deal_ids)

# Pre-compute per-deal net for t* and t=0
val_df_copy = val_df.copy()

# t* nets
utilities_val = val_df_copy[utility_cols].values
actual_nets_val = val_df_copy[actual_net_cols].values
max_util_val = utilities_val.max(axis=1)
best_idx_val = utilities_val.argmax(axis=1)

# t* pass/bid
passes_star = max_util_val <= -t_star
net_star = np.zeros(len(val_df_copy))
bids_star = ~passes_star
if bids_star.sum() > 0:
    net_star[bids_star] = actual_nets_val[bids_star, best_idx_val[bids_star]]

# t=0 pass/bid
passes_0 = max_util_val <= 0
net_0 = np.zeros(len(val_df_copy))
bids_0 = ~passes_0
if bids_0.sum() > 0:
    net_0[bids_0] = actual_nets_val[bids_0, best_idx_val[bids_0]]

val_df_copy["net_star"] = net_star
val_df_copy["net_0"] = net_0
val_df_copy["net_delta"] = net_star - net_0

# Per-deal means (for grouped bootstrap)
deal_deltas = val_df_copy.groupby("deal_id")["net_delta"].mean()

boot_deltas = np.array(
    [
        deal_deltas.sample(n=n_val_deals_arr, replace=True, random_state=rng).mean()
        for _ in range(N_BOOTSTRAP)
    ]
)
ci_lo, ci_hi = np.percentile(boot_deltas, [2.5, 97.5])

print("\nBootstrap 95% CI on validation delta:")
print(f"  Delta: {val_delta:+.4f} [{ci_lo:+.4f}, {ci_hi:+.4f}]")
print(f"  CI excludes 0: {ci_lo > 0 or ci_hi < 0}")

# %% [markdown]
# ## S7: Decision Gate
#
# | Condition | Decision |
# |-----------|----------|
# | delta > SESOI AND CI excludes 0 AND guardrails pass | **ADOPT** |
# | delta > 0 AND CI excludes 0 BUT delta < SESOI | **NOTE** |
# | CI includes 0 | **RETAIN** |
# | delta < 0 | **RETAIN** |

# %%
ci_excludes_zero = ci_lo > 0 or ci_hi < 0

# Re-check hard guardrails on validation (soft cap is advisory only)
val_guardrails_pass = (
    val_t_star["make_rate"] >= MAKE_RATE_FLOOR
    and val_t_star["overbid_regret_share"] <= OVERBID_REGRET_CAP
)
val_soft_cap_warn = val_t_star["bid_rate"] > BID_RATE_CAP

if val_delta > SESOI and ci_excludes_zero and val_guardrails_pass:
    decision = "ADOPT"
elif val_delta > 0 and ci_excludes_zero:
    decision = "NOTE"
elif not ci_excludes_zero:
    decision = "RETAIN"
else:
    decision = "RETAIN"

print(f"\n{'=' * 60}")
print("DECISION GATE")
print(f"{'=' * 60}")
print(f"  Validation delta:     {val_delta:+.4f}")
print(f"  SESOI:                {SESOI}")
print(f"  Bootstrap 95% CI:     [{ci_lo:+.4f}, {ci_hi:+.4f}]")
print(f"  CI excludes 0:        {ci_excludes_zero}")
print(f"  Val guardrails pass:  {val_guardrails_pass} (hard floors)")
if val_soft_cap_warn:
    print(
        f"  Val bid_rate warning:  {val_t_star['bid_rate']:.3f} > {BID_RATE_CAP} (soft cap)"
    )
print("  ────────────────────────────────────────")
print(f"  DECISION:             {decision}")
print(f"{'=' * 60}")

if decision == "ADOPT":
    print(f"\n  → Implement pass_threshold={t_star:.2f} in HybridOLSaBidder")
    print("  → Re-run R0 eval experiments with new threshold")
elif decision == "NOTE":
    print(f"\n  → Effect real but below SESOI ({val_delta:.4f} < {SESOI})")
    print("  → Record finding, revisit at R1 with better model")
else:
    print("\n  → No significant improvement found")
    print("  → Keep t=0 (current behavior)")

# %% [markdown]
# ## S8: Visualizations

# %%
# Run full sweep on both partitions for plotting
val_results = []
for t in THRESHOLD_GRID:
    result = evaluate_threshold(val_df, t)
    val_results.append(result)
val_sweep = pd.DataFrame(val_results)

# %%
fig, axes = plt.subplots(2, 3, figsize=(15, 10))
fig.suptitle(f"Pass-Threshold Sweep (B0) — MODE={MODE}", fontsize=14)

# --- Plot 1: Net Diff Mean ---
ax = axes[0, 0]
ax.plot(train_sweep["t"], train_sweep["net_diff_mean"], "o-", label="Train", color="C0")
ax.plot(val_sweep["t"], val_sweep["net_diff_mean"], "s--", label="Val", color="C1")
ax.axvline(t_star, color="red", linestyle=":", alpha=0.7, label=f"t*={t_star:.2f}")
ax.axhline(baseline_result["net_diff_mean"], color="gray", linestyle=":", alpha=0.5)
ax.set_xlabel("Threshold (t)")
ax.set_ylabel("Mean Net-Diff per Hand")
ax.set_title("Primary Endpoint: Net-Differential")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# --- Plot 2: Bid Rate ---
ax = axes[0, 1]
ax.plot(train_sweep["t"], train_sweep["bid_rate"], "o-", label="Train", color="C0")
ax.plot(val_sweep["t"], val_sweep["bid_rate"], "s--", label="Val", color="C1")
ax.axvline(t_star, color="red", linestyle=":", alpha=0.7)
ax.axhline(
    BID_RATE_CAP,
    color="orange",
    linestyle="--",
    alpha=0.7,
    label=f"Soft cap ({BID_RATE_CAP})",
)
ax.set_xlabel("Threshold (t)")
ax.set_ylabel("Bid Rate")
ax.set_title("Bid Rate (fraction of hands that bid)")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# --- Plot 3: Make Rate ---
ax = axes[0, 2]
ax.plot(train_sweep["t"], train_sweep["make_rate"], "o-", label="Train", color="C0")
ax.plot(val_sweep["t"], val_sweep["make_rate"], "s--", label="Val", color="C1")
ax.axvline(t_star, color="red", linestyle=":", alpha=0.7)
ax.axhline(
    MAKE_RATE_FLOOR,
    color="red",
    linestyle="--",
    alpha=0.7,
    label=f"Floor ({MAKE_RATE_FLOOR})",
)
ax.set_xlabel("Threshold (t)")
ax.set_ylabel("Make Rate")
ax.set_title("Make Rate (P(tricks >= bid) | bid)")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# --- Plot 4: Regret Decomposition (train) ---
ax = axes[1, 0]
ax.stackplot(
    train_sweep["t"],
    train_sweep["pass_regret_share"],
    train_sweep["cs_regret_share"],
    train_sweep["overbid_regret_share"],
    labels=["Pass-threshold", "Contract-selection", "Over-bidding"],
    alpha=0.7,
)
ax.axvline(t_star, color="red", linestyle=":", alpha=0.7)
ax.axhline(OVERBID_REGRET_CAP, color="red", linestyle="--", alpha=0.3)
ax.set_xlabel("Threshold (t)")
ax.set_ylabel("Regret Share")
ax.set_title("Regret Decomposition (Train)")
ax.legend(fontsize=8, loc="center right")
ax.grid(True, alpha=0.3)

# --- Plot 5: Mean Regret ---
ax = axes[1, 1]
ax.plot(train_sweep["t"], train_sweep["mean_regret"], "o-", label="Train", color="C0")
ax.plot(val_sweep["t"], val_sweep["mean_regret"], "s--", label="Val", color="C1")
ax.axvline(t_star, color="red", linestyle=":", alpha=0.7)
ax.set_xlabel("Threshold (t)")
ax.set_ylabel("Mean Regret per Hand")
ax.set_title("Total Mean Regret")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# --- Plot 6: Decision summary text ---
ax = axes[1, 2]
ax.axis("off")
summary_text = (
    f"Decision: {decision}\n\n"
    f"Selected t*: {t_star:.2f}\n"
    f"Val delta: {val_delta:+.4f}\n"
    f"Bootstrap 95% CI: [{ci_lo:+.4f}, {ci_hi:+.4f}]\n"
    f"SESOI: {SESOI}\n\n"
    f"Val bid_rate: {val_t_star['bid_rate']:.3f}\n"
    f"Val make_rate: {val_t_star['make_rate']:.3f}\n"
    f"Val overbid_share: {val_t_star['overbid_regret_share']:.3f}\n\n"
    f"MODE={MODE}, n_hands={n_hands:,}\n"
    f"Protocol: r0_pass_threshold_protocol.md v1"
)
ax.text(
    0.05,
    0.95,
    summary_text,
    transform=ax.transAxes,
    fontsize=11,
    verticalalignment="top",
    fontfamily="monospace",
    bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
)
ax.set_title("Decision Summary")

plt.tight_layout()
if CHART_OUTPUT_DIR:
    _chart_out = Path(CHART_OUTPUT_DIR)
    _chart_out.mkdir(parents=True, exist_ok=True)
    fig.savefig(_chart_out / "b0_threshold_sweep.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {_chart_out / 'b0_threshold_sweep.png'}")
plt.show()

# %%
# Final summary table: train vs val for all candidates
print(f"\n{'=' * 100}")
print("FULL SWEEP COMPARISON: TRAIN vs VALIDATION")
print(f"{'=' * 100}")
print(
    f"{'t':>6} │ {'Train net':>10} {'Val net':>10} │ "
    f"{'Train bid%':>10} {'Val bid%':>10} │ "
    f"{'Train make%':>10} {'Val make%':>10} │ {'Guards':>6}"
)
print(f"{'─' * 100}")
for i in range(len(THRESHOLD_GRID)):
    tr = train_sweep.iloc[i]
    vr = val_sweep.iloc[i]
    guard = "✓" if tr["all_guardrails"] else "✗"
    marker = " ← t*" if tr["t"] == t_star else ""
    print(
        f"{tr['t']:>6.2f} │ {tr['net_diff_mean']:>10.4f} {vr['net_diff_mean']:>10.4f} │ "
        f"{tr['bid_rate']:>10.3f} {vr['bid_rate']:>10.3f} │ "
        f"{tr['make_rate']:>10.3f} {vr['make_rate']:>10.3f} │ {guard:>6}{marker}"
    )
print(f"{'=' * 100}")
