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
# # Lambda Tuning Sweep — Track D (R0 v2)
#
# **Protocol:** `plans/r0_v2_lambda_tuning_protocol.md`
#
# **Goal:** Select the optimal `risk_lambda` for the HybridOLSa bidder.
# `risk_lambda` weights a CVaR tail-risk penalty: higher lambda = more
# conservative bidding (penalizes downside risk). `lambda=0.0` is the
# risk-neutral R0 default.
#
# **Design:** This tunes the *decision policy*, not the model. We hold the
# OLS coefficients fixed (from `hybrid_r0.json`) and replay bidding decisions
# with different lambda values, evaluating which produces the best outcomes.
#
# **Split:** Deterministic 60/40 hash split by `deal_id` (protocol §2.2).
# Select `lambda*` on train (60%), evaluate on validation (40%).
#
# **Grid:** `[0.0, 0.1, 0.2, 0.5, 1.0, 2.0]`
#
# **Primary endpoint:** net_eppd (net expected points per deal) on validation
#
# **Guardrails:**
# - bid_rate in [0.05, 0.95]
# - make_rate >= 0.45
#
# **Sections:**
# - S0: Setup & configuration
# - S1: Data loading & preparation
# - S2: Lambda grid sweep (full-data overview)
# - S3: Train/validation split + selection
# - S4: Validation evaluation + bootstrap CI
# - S5: Report summary & visualizations

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE (~100 deals), QUICK (~2000 deals), FULL (all)
SEED = 42
ARTIFACT_PATH = "data/artifacts/arc_d/r0/hybrid_r0.json"
CHART_OUTPUT_DIR = ""  # Set via papermill; empty = skip chart save
# Track C output — update after threshold sweep completes.
# If Track C retains t=0.0, this stays 0.0.
PASS_THRESHOLD = 0.0

# %%
import hashlib
import json
import math
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from bid_euchre.strategy.bidding import compute_best_bid

# %% [markdown]
# ## S0: Setup & Configuration

# %%
# --- CWD-to-repo-root ---
# Notebooks may be launched from the notebook dir; ensure we're at repo root.
_cwd = Path.cwd()
if _cwd.name == "r0" or _cwd.name == "arc_d":
    import os

    os.chdir(_cwd.parents[2] if _cwd.name == "r0" else _cwd.parents[1])
    print(f"Changed CWD to: {Path.cwd()}")

# --- Validate paths ---
artifact_path = Path(ARTIFACT_PATH)
assert artifact_path.exists(), f"Missing artifact: {artifact_path}"

# --- Mode-dependent sample limits ---
MODE_LIMITS = {"SMOKE": 100, "QUICK": 2_000, "FULL": None}
DEAL_LIMIT = MODE_LIMITS[MODE]
print(f"MODE={MODE}, SEED={SEED}, deal_limit={DEAL_LIMIT}")
print(f"PASS_THRESHOLD={PASS_THRESHOLD}")

# --- Protocol constants ---
LAMBDA_GRID = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0]
BOOTSTRAP_SEED = SEED
N_BOOTSTRAP = 10_000

# Guardrails
BID_RATE_FLOOR = 0.05
BID_RATE_CAP = 0.95
MAKE_RATE_FLOOR = 0.45

# --- Load model artifact ---
with open(artifact_path) as f:
    artifact = json.load(f)

assert (
    artifact.get("artifact_type") == "hybrid_olsa_v1"
), f"Unexpected artifact type: {artifact.get('artifact_type')}"

residual_var = artifact["residual_variance"]
sigma_by_contract = {k: math.sqrt(v) for k, v in residual_var.items()}

print(f"Artifact: {artifact_path}")
print(f"Current risk_lambda in artifact: {artifact.get('risk_lambda')}")
print(f"Sigma by contract: { {k: f'{v:.4f}' for k, v in sigma_by_contract.items()} }")
print(f"Lambda grid: {LAMBDA_GRID}")
print(
    f"Guardrails: bid_rate in [{BID_RATE_FLOOR}, {BID_RATE_CAP}], make_rate >= {MAKE_RATE_FLOOR}"
)

# %% [markdown]
# ## S1: Data Loading & Preparation
#
# Use the bidless dataset (features + outcomes) which provides all 6
# contract scenarios per deal. Each `deal_id` maps to 6 `hand_id`s
# (suit_C, suit_D, suit_H, suit_S, high, low) with 4 seats each,
# giving 24 rows per deal. This lets us replay the full contract
# selection + bid decision at each lambda value.

# %%
from bid_euchre.datasets.join import join_features_outcomes

BIDLESS_PATH = Path(
    "data/runs/canonical_bidless_dataset_glutton_42_20260221_175752"
    "/datasets/bidless.parquet"
)
OUTCOMES_PATH = Path(
    "data/runs/canonical_bidless_dataset_glutton_42_20260221_175752"
    "/datasets/bidless_outcomes.parquet"
)

assert BIDLESS_PATH.exists(), f"Missing: {BIDLESS_PATH}"
assert OUTCOMES_PATH.exists(), f"Missing: {OUTCOMES_PATH}"

joined = join_features_outcomes(str(BIDLESS_PATH), str(OUTCOMES_PATH))
print(f"Joined rows: {len(joined):,}")

# Apply deal limit — limit by deal_id (not hand_id) to keep all 6 contracts
# per deal. Each deal_id has 6 hand_ids (one per contract scenario).
if DEAL_LIMIT is not None:
    unique_deal_ids = joined["deal_id"].unique()
    keep_deals = unique_deal_ids[:DEAL_LIMIT]
    joined = joined[joined["deal_id"].isin(keep_deals)].copy()
    print(f"After deal limit ({DEAL_LIMIT} deals): {len(joined):,} rows")

# Create contract_key for pivoting
joined["contract_key"] = joined.apply(
    lambda r: f"{r['contract_type']}_{r['trump_suit']}"
    if r["contract_type"] == "suit"
    else r["contract_type"],
    axis=1,
)

# Validate: 6 contracts per deal, 4 seats per contract
expected_keys = {"suit_C", "suit_D", "suit_H", "suit_S", "high", "low"}
actual_keys = set(joined["contract_key"].unique())
assert actual_keys == expected_keys, f"Expected {expected_keys}, got {actual_keys}"

n_deals_loaded = joined["deal_id"].nunique()
print(f"Deals loaded: {n_deals_loaded:,}")
print(f"Contract keys: {sorted(actual_keys)}")


# %% [markdown]
# ## S2: Lambda Grid Sweep (Per-Hand Replay)
#
# For each hand, replay the bidding decision at each lambda value:
# 1. Compute mu from OLS model for each contract
# 2. Compute utility = EV - risk_penalty for each contract at each lambda
# 3. Select best contract (max utility) and decide bid vs pass
# 4. Measure realized net-differential from actual tricks
#
# **Pooling justification:** Metrics (net_eppd, bid_rate, make_rate) are reported
# pooled across contract types because lambda tunes the *cross-contract decision
# policy* — each hand selects the single best contract among all 6 candidates.
# Per-contract-type breakout is not meaningful here since the unit of analysis is
# the hand-level bid/pass decision, not individual contract performance.

# %%
CONTRACT_KEYS = ["suit_C", "suit_D", "suit_H", "suit_S", "high", "low"]
CONTRACT_FAMILY_MAP = {
    "suit_C": "suit",
    "suit_D": "suit",
    "suit_H": "suit",
    "suit_S": "suit",
    "high": "high",
    "low": "low",
}


def compute_actual_net(tricks_won: float, bid_n: int) -> float:
    """Compute actual net-differential for a declaring team."""
    if tricks_won >= bid_n:
        return 2.0 * tricks_won - 10.0
    return tricks_won - bid_n - 10.0


# %%
# --- Build prediction table (contract-level) ---
# Compute mu (predicted tricks) for each (deal_id, seat, contract) row.

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
    subset["contract_family"] = contract_family

    pred_parts.append(
        subset[
            [
                "deal_id",
                "seat",
                "contract_key",
                "contract_family",
                "mu",
                "sigma",
                "tricks_won",
            ]
        ].rename(columns={"tricks_won": "actual_tricks"})
    )

pred_df = pd.concat(pred_parts, ignore_index=True)
n_deals = pred_df["deal_id"].nunique()
print(f"Prediction rows: {len(pred_df):,} ({n_deals:,} deals)")

# %% [markdown]
# ### Pivot to wide format
#
# Pivot so each row is one (deal_id, seat) with columns for each
# contract's mu, sigma, and actual_tricks.

# %%
# Pivot wide: one row per (deal_id, seat) with 6 contracts' mu, sigma, actual_tricks
pred_wide = pred_df.pivot_table(
    index=["deal_id", "seat"],
    columns="contract_key",
    values=["mu", "sigma", "actual_tricks"],
    aggfunc="first",
).reset_index()

pred_wide.columns = [
    f"{val}_{contract}" if contract else val for val, contract in pred_wide.columns
]

n_hands = len(pred_wide)
print(f"Wide prediction table: {n_hands:,} hands x {pred_wide.shape[1]} columns")

# Verify completeness — need all 6 contracts
for ck in CONTRACT_KEYS:
    assert f"mu_{ck}" in pred_wide.columns, f"Missing mu for {ck}"
    assert f"actual_tricks_{ck}" in pred_wide.columns, f"Missing actual_tricks for {ck}"

# Sanity: check for NaN (would indicate incomplete deal_id coverage)
n_nan = pred_wide[[f"mu_{ck}" for ck in CONTRACT_KEYS]].isna().any(axis=1).sum()
if n_nan > 0:
    print(f"WARNING: {n_nan:,} hands with incomplete contracts — dropping")
    pred_wide = pred_wide.dropna(subset=[f"mu_{ck}" for ck in CONTRACT_KEYS]).copy()
    n_hands = len(pred_wide)
    print(f"After NaN drop: {n_hands:,} hands")


# %%
def evaluate_lambda(
    df: pd.DataFrame, risk_lambda: float, pass_threshold: float = 0.0
) -> dict:
    """Evaluate a lambda value on wide-format data (6 contracts per hand).

    For each hand, find the best contract via compute_best_bid logic:
    - For each of 6 contracts, compute utility = EV - risk_penalty at optimal bid_n
    - Select the contract with max utility
    - If best utility <= -pass_threshold, the hand passes (net=0)
    - If hand bids, compute actual net from realized tricks

    Returns dict of endpoint metrics including per-hand net array.
    """
    n = len(df)
    net_per_hand = np.zeros(n)
    bid_flags = np.zeros(n, dtype=bool)
    make_flags = np.full(n, np.nan)
    bid_n_chosen = np.zeros(n, dtype=int)
    deal_ids = df["deal_id"].values

    for i in range(n):
        best_utility = None
        best_contract = None
        best_bid_n = None

        for ck in CONTRACT_KEYS:
            mu = df.iloc[i][f"mu_{ck}"]
            sigma = df.iloc[i][f"sigma_{ck}"]

            if pd.isna(mu) or pd.isna(sigma):
                continue

            # Use compute_best_bid to find optimal bid_n for this contract
            result = compute_best_bid(
                mu,
                sigma,
                current_high_bid=0,
                pass_threshold=pass_threshold,
                bid_level_search=True,
                risk_lambda=risk_lambda,
                seed=SEED,
            )

            if result is None:
                continue

            bid_n, utility = result

            # Tie-break matches HybridOLSaBidder.choose_bid() (bidding.py:1191-1198):
            # on equal utility, prefer higher (bid_n, contract_key) tuple.
            if (
                best_utility is None
                or utility > best_utility
                or (
                    utility == best_utility
                    and (bid_n, ck) > (best_bid_n, best_contract)
                )
            ):
                best_utility = utility
                best_contract = ck
                best_bid_n = bid_n

        # Decision: bid or pass (compute_best_bid already applies pass_threshold
        # per-contract; if we got a result, it passed the threshold)
        if best_contract is not None:
            bid_flags[i] = True
            bid_n_chosen[i] = best_bid_n
            actual_tricks = df.iloc[i][f"actual_tricks_{best_contract}"]
            net_per_hand[i] = compute_actual_net(actual_tricks, best_bid_n)
            make_flags[i] = 1.0 if actual_tricks >= best_bid_n else 0.0
        else:
            # Pass: net = 0 (no bid made)
            net_per_hand[i] = 0.0

    n_bid = bid_flags.sum()
    n_pass = n - n_bid
    bid_rate = n_bid / n if n > 0 else 0.0
    make_rate = float(np.nanmean(make_flags[bid_flags])) if n_bid > 0 else np.nan

    return {
        "risk_lambda": risk_lambda,
        "net_eppd": net_per_hand.mean(),
        "bid_rate": bid_rate,
        "make_rate": make_rate,
        "n_bid": int(n_bid),
        "n_pass": int(n_pass),
        "n_total": n,
        "mean_bid_n": float(bid_n_chosen[bid_flags].mean()) if n_bid > 0 else np.nan,
        "net_per_hand": net_per_hand,  # Keep for bootstrap
        "deal_ids": deal_ids,  # Keep for deal-level grouping
    }


# %%
# --- Timing estimate ---
# Run a small sample to estimate FULL runtime before committing
_t0 = time.time()
_timing_sample = pred_wide.head(min(200, len(pred_wide)))
_ = evaluate_lambda(_timing_sample, risk_lambda=1.0, pass_threshold=PASS_THRESHOLD)
_t1 = time.time()
_per_hand_ms = (_t1 - _t0) / len(_timing_sample) * 1000
_est_full_s = _per_hand_ms * n_hands * len(LAMBDA_GRID) / 1000
print(f"Timing: {_per_hand_ms:.1f} ms/hand (lambda>0, bid_level_search=True)")
print(f"Estimated full sweep: {_est_full_s:.0f}s ({_est_full_s / 60:.1f} min)")
if DEAL_LIMIT is None and _est_full_s > 3600:
    print(
        "WARNING: Estimated runtime > 1 hour. "
        "Consider QUICK mode for initial validation."
    )

# %%
# Quick full-data sweep for overview (before train/val split)
print(f"\n{'=' * 90}")
print(f"FULL-DATA LAMBDA SWEEP (n={n_hands:,} hands)")
print(f"{'=' * 90}")
print(
    f"{'lambda':>8} {'net_eppd':>10} {'bid_rate':>10} "
    f"{'make_rate':>10} {'mean_bid_n':>10} {'n_bid':>8}"
)
print(f"{'-' * 90}")

overview_results = []
for lam in LAMBDA_GRID:
    result = evaluate_lambda(pred_wide, lam, pass_threshold=PASS_THRESHOLD)
    overview_results.append(result)
    print(
        f"{lam:>8.1f} {result['net_eppd']:>10.4f} {result['bid_rate']:>10.3f} "
        f"{result['make_rate']:>10.3f} {result['mean_bid_n']:>10.2f} "
        f"{result['n_bid']:>8d}"
    )

overview_df = pd.DataFrame(
    [
        {k: v for k, v in r.items() if k not in ("net_per_hand", "deal_ids")}
        for r in overview_results
    ]
)
print(f"{'=' * 90}")

# %% [markdown]
# ## S3: Train/Validation Split + Selection
#
# **Protocol §2.2:** Deterministic 60/40 split by `deal_id` hash.
# - Train: `deal_id hash % 5 in {0, 1, 2}` (60%)
# - Validation: `deal_id hash % 5 in {3, 4}` (40%)
#
# Select `lambda*` on **train** partition only (protocol §3.1).


# %%
# Deterministic hash-based train/val split (protocol §2.2)
def deal_partition(deal_id: str, seed: int = 42) -> str:
    """Deterministic partition assignment based on deal_id hash."""
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"


pred_wide["partition"] = pred_wide["deal_id"].apply(
    lambda d: deal_partition(d, seed=SEED)
)

train_df = pred_wide[pred_wide["partition"] == "train"].copy()
val_df = pred_wide[pred_wide["partition"] == "val"].copy()

n_train_deals = train_df["deal_id"].nunique()
n_val_deals = val_df["deal_id"].nunique()
n_train_hands = len(train_df)
n_val_hands = len(val_df)

print(f"Train: {n_train_deals:,} deals, {n_train_hands:,} hands")
print(f"Val:   {n_val_deals:,} deals, {n_val_hands:,} hands")
print(
    f"Split: {n_train_deals / (n_train_deals + n_val_deals):.1%} / "
    f"{n_val_deals / (n_train_deals + n_val_deals):.1%}"
)

# Validate no deal leakage
train_deal_set = set(train_df["deal_id"].unique())
val_deal_set = set(val_df["deal_id"].unique())
assert len(train_deal_set & val_deal_set) == 0, "Train/val deal leakage!"
print("No train/val deal leakage.")

# %%
# Evaluate all lambda candidates on TRAIN partition (protocol §3.1)
print(f"\n{'=' * 90}")
print(f"TRAIN PARTITION SWEEP (n={n_train_hands:,} hands, {n_train_deals:,} deals)")
print(f"{'=' * 90}")
print(
    f"{'lambda':>8} {'net_eppd':>10} {'bid_rate':>10} "
    f"{'make_rate':>10} {'mean_bid_n':>10} {'n_bid':>8}"
)
print(f"{'-' * 90}")

train_results = []
for lam in LAMBDA_GRID:
    result = evaluate_lambda(train_df, lam, pass_threshold=PASS_THRESHOLD)
    train_results.append(result)
    print(
        f"{lam:>8.1f} {result['net_eppd']:>10.4f} {result['bid_rate']:>10.3f} "
        f"{result['make_rate']:>10.3f} {result['mean_bid_n']:>10.2f} "
        f"{result['n_bid']:>8d}"
    )

train_df_summary = pd.DataFrame(
    [
        {k: v for k, v in r.items() if k not in ("net_per_hand", "deal_ids")}
        for r in train_results
    ]
)
print(f"{'=' * 90}")

# %%
# Apply guardrails on train results (protocol §3.1)
train_df_summary["pass_bid_rate_floor"] = train_df_summary["bid_rate"] >= BID_RATE_FLOOR
train_df_summary["pass_bid_rate_cap"] = train_df_summary["bid_rate"] <= BID_RATE_CAP
train_df_summary["pass_make_rate"] = train_df_summary["make_rate"] >= MAKE_RATE_FLOOR
train_df_summary["all_guardrails"] = (
    train_df_summary["pass_bid_rate_floor"]
    & train_df_summary["pass_bid_rate_cap"]
    & train_df_summary["pass_make_rate"]
)

survivors = train_df_summary[train_df_summary["all_guardrails"]]
disqualified = train_df_summary[~train_df_summary["all_guardrails"]]

print(f"Survivors: {len(survivors)} / {len(train_df_summary)} candidates")
if len(disqualified) > 0:
    print(f"Disqualified: {list(disqualified['risk_lambda'].values)}")
    for _, row in disqualified.iterrows():
        reasons = []
        if not row["pass_bid_rate_floor"]:
            reasons.append(f"bid_rate={row['bid_rate']:.3f} < {BID_RATE_FLOOR}")
        if not row["pass_bid_rate_cap"]:
            reasons.append(f"bid_rate={row['bid_rate']:.3f} > {BID_RATE_CAP}")
        if not row["pass_make_rate"]:
            reasons.append(f"make_rate={row['make_rate']:.3f} < {MAKE_RATE_FLOOR}")
        print(f"  lambda={row['risk_lambda']:.1f}: {', '.join(reasons)}")

# Select lambda* = max net_eppd among survivors (protocol §3.1)
if len(survivors) == 0:
    print("WARNING: No candidates pass all guardrails. Retaining lambda=0.0.")
    lambda_star = 0.0
else:
    best_row = survivors.loc[survivors["net_eppd"].idxmax()]
    lambda_star = best_row["risk_lambda"]

print(f"\nlambda* (selected on train): {lambda_star:.1f}")

# %% [markdown]
# ## S4: Validation Evaluation + Bootstrap CI
#
# Evaluate `lambda*` and `lambda=0.0` on the **held-out validation** partition
# (protocol §3.2). Bootstrap CI is grouped by `deal_id` to respect the
# deal-level sampling unit.

# %%
# Evaluate lambda* and baseline on VALIDATION partition (protocol §3.2)
val_result_star = evaluate_lambda(val_df, lambda_star, pass_threshold=PASS_THRESHOLD)
val_result_base = evaluate_lambda(val_df, 0.0, pass_threshold=PASS_THRESHOLD)

val_delta = val_result_star["net_eppd"] - val_result_base["net_eppd"]

print(f"\n{'=' * 70}")
print(f"VALIDATION RESULTS (n={n_val_hands:,} hands, {n_val_deals:,} deals)")
print(f"{'=' * 70}")
print(f"  lambda*={lambda_star:.1f}:")
print(f"    net_eppd:   {val_result_star['net_eppd']:.4f}")
print(f"    bid_rate:   {val_result_star['bid_rate']:.3f}")
print(f"    make_rate:  {val_result_star['make_rate']:.3f}")
print(f"    mean_bid_n: {val_result_star['mean_bid_n']:.2f}")
print("  lambda=0.0 (baseline):")
print(f"    net_eppd:   {val_result_base['net_eppd']:.4f}")
print(f"    bid_rate:   {val_result_base['bid_rate']:.3f}")
print(f"    make_rate:  {val_result_base['make_rate']:.3f}")
print(f"    mean_bid_n: {val_result_base['mean_bid_n']:.2f}")
print(f"  Delta:        {val_delta:+.4f}")
print(f"{'=' * 70}")

# %%
# Check validation guardrails for lambda*
val_guardrails_pass = (
    BID_RATE_FLOOR <= val_result_star["bid_rate"] <= BID_RATE_CAP
    and val_result_star["make_rate"] >= MAKE_RATE_FLOOR
)
print(
    f"Validation guardrails for lambda*={lambda_star:.1f}: "
    f"{'PASS' if val_guardrails_pass else 'FAIL'}"
)
if not val_guardrails_pass:
    print(
        f"  bid_rate={val_result_star['bid_rate']:.3f}, "
        f"make_rate={val_result_star['make_rate']:.3f}"
    )

# %%
# Bootstrap 95% CI on delta, grouped by deal_id (protocol §3.2)
# Each deal has 4 hands (seats) — resample at deal level to preserve grouping.

# Build per-deal net arrays for lambda* and baseline
val_deal_ids = val_result_star["deal_ids"]
net_star = val_result_star["net_per_hand"]
net_base = val_result_base["net_per_hand"]

# Group by deal_id: compute mean net per deal
val_deal_df = pd.DataFrame(
    {
        "deal_id": val_deal_ids,
        "net_star": net_star,
        "net_base": net_base,
    }
)
deal_means = (
    val_deal_df.groupby("deal_id")
    .agg(
        net_star_mean=("net_star", "mean"),
        net_base_mean=("net_base", "mean"),
    )
    .reset_index()
)

deal_deltas = (deal_means["net_star_mean"] - deal_means["net_base_mean"]).values
n_deals_val = len(deal_deltas)

assert (
    n_deals_val == n_val_deals
), f"Deal count mismatch: {n_deals_val} vs {n_val_deals}"

# Bootstrap: resample deals, compute mean delta
rng = np.random.RandomState(BOOTSTRAP_SEED)
boot_deltas = np.array(
    [
        rng.choice(deal_deltas, size=n_deals_val, replace=True).mean()
        for _ in range(N_BOOTSTRAP)
    ]
)
ci_lo, ci_hi = np.percentile(boot_deltas, [2.5, 97.5])
ci_excludes_zero = ci_lo > 0 or ci_hi < 0

print(
    f"\nDeal-level bootstrap 95% CI (n_deals={n_deals_val:,}, "
    f"n_bootstrap={N_BOOTSTRAP:,}):"
)
print(f"  Delta (val):  {val_delta:+.4f}")
print(f"  95% CI:       [{ci_lo:+.4f}, {ci_hi:+.4f}]")
print(f"  CI excludes 0: {ci_excludes_zero}")

# %% [markdown]
# ## S5: Report Summary & Visualizations

# %%
# --- Decision summary (protocol §3.3) ---
print(f"\n{'=' * 70}")
print("LAMBDA TUNING DECISION SUMMARY")
print(f"{'=' * 70}")
print(f"  Selected lambda*:        {lambda_star:.1f}")
print(f"  pass_threshold (from C): {PASS_THRESHOLD:.1f}")
print(f"  Val net_eppd delta:      {val_delta:+.4f} (lambda* vs 0.0)")
print(f"  Bootstrap 95% CI:        [{ci_lo:+.4f}, {ci_hi:+.4f}]")
print(f"  CI excludes 0:           {ci_excludes_zero}")
print(f"  Val guardrails:          {'PASS' if val_guardrails_pass else 'FAIL'}")
print(f"  Val bid_rate:            {val_result_star['bid_rate']:.3f}")
print(f"  Val make_rate:           {val_result_star['make_rate']:.3f}")
print()

if lambda_star == 0.0:
    print(
        "  RESULT: lambda=0.0 is optimal on train. No risk penalty improves net_eppd."
    )
    print("  ACTION: Retain risk_lambda=0.0 in all configs (no change needed).")
elif val_delta > 0 and ci_excludes_zero and val_guardrails_pass:
    print(
        f"  RESULT: lambda={lambda_star:.1f} significantly improves net_eppd on validation."
    )
    print(
        f"  ACTION: ADOPT — update risk_lambda to {lambda_star:.1f} in canonical configs:"
    )
    print("    - experiments/configs/auction_comparator.yaml")
    print("    - experiments/configs/arc_d_r0_c33_ablation.yaml")
    print("    - scripts/internal/run_arc_d_h2h_battery.py (DEFAULT_ROSTER)")
elif val_delta > 0 and not ci_excludes_zero:
    print(
        f"  RESULT: lambda={lambda_star:.1f} selected on train, but CI includes 0 on validation."
    )
    print("  ACTION: RETAIN — retain risk_lambda=0.0 (effect not significant).")
else:
    print(f"  RESULT: lambda={lambda_star:.1f} does not improve validation net_eppd.")
    print("  ACTION: RETAIN — retain risk_lambda=0.0.")

print(f"{'=' * 70}")

# %%
# --- Visualization ---
fig, axes = plt.subplots(2, 3, figsize=(16, 10))
fig.suptitle(
    f"Lambda Tuning Sweep (Track D, R0 v2) — MODE={MODE}, "
    f"pass_threshold={PASS_THRESHOLD}",
    fontsize=14,
)

# Plot 1: Full-data net_eppd vs lambda (overview)
ax = axes[0, 0]
ax.plot(
    overview_df["risk_lambda"],
    overview_df["net_eppd"],
    "o-",
    label="Full data",
    color="C0",
)
ax.plot(
    train_df_summary["risk_lambda"],
    train_df_summary["net_eppd"],
    "s--",
    label="Train (60%)",
    color="C1",
    alpha=0.7,
)
ax.axvline(
    lambda_star,
    color="red",
    linestyle=":",
    alpha=0.7,
    label=f"lambda*={lambda_star:.1f}",
)
ax.set_xlabel("risk_lambda")
ax.set_ylabel("Net EPPD")
ax.set_title("Net EPPD vs Lambda")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Plot 2: Bid rate vs lambda
ax = axes[0, 1]
ax.plot(
    overview_df["risk_lambda"],
    overview_df["bid_rate"],
    "o-",
    label="Full data",
    color="C0",
)
ax.axhline(
    BID_RATE_FLOOR,
    color="red",
    linestyle="--",
    alpha=0.5,
    label=f"Floor ({BID_RATE_FLOOR})",
)
ax.axhline(
    BID_RATE_CAP,
    color="orange",
    linestyle="--",
    alpha=0.5,
    label=f"Cap ({BID_RATE_CAP})",
)
ax.axvline(lambda_star, color="red", linestyle=":", alpha=0.7)
ax.set_xlabel("risk_lambda")
ax.set_ylabel("Bid Rate")
ax.set_title("Bid Rate vs Lambda")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Plot 3: Make rate vs lambda
ax = axes[0, 2]
ax.plot(
    overview_df["risk_lambda"],
    overview_df["make_rate"],
    "o-",
    label="Full data",
    color="C0",
)
ax.axhline(
    MAKE_RATE_FLOOR,
    color="red",
    linestyle="--",
    alpha=0.5,
    label=f"Floor ({MAKE_RATE_FLOOR})",
)
ax.axvline(lambda_star, color="red", linestyle=":", alpha=0.7)
ax.set_xlabel("risk_lambda")
ax.set_ylabel("Make Rate")
ax.set_title("Make Rate vs Lambda")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Plot 4: Train vs validation net_eppd for lambda* and baseline
ax = axes[1, 0]
train_star = train_df_summary.loc[
    train_df_summary["risk_lambda"] == lambda_star, "net_eppd"
].values[0]
train_base = train_df_summary.loc[
    train_df_summary["risk_lambda"] == 0.0, "net_eppd"
].values[0]
labels = ["lambda=0.0", f"lambda*={lambda_star:.1f}"]
train_vals = [train_base, train_star]
val_vals = [val_result_base["net_eppd"], val_result_star["net_eppd"]]
x = np.arange(len(labels))
width = 0.35
ax.bar(x - width / 2, train_vals, width, label="Train", color="C1", alpha=0.7)
ax.bar(x + width / 2, val_vals, width, label="Val", color="C2", alpha=0.7)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Net EPPD")
ax.set_title("Train vs Val: lambda* vs Baseline")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3, axis="y")

# Plot 5: Bootstrap distribution of delta
ax = axes[1, 1]
ax.hist(boot_deltas, bins=50, alpha=0.7, color="C2", edgecolor="black", linewidth=0.5)
ax.axvline(0, color="black", linestyle="-", linewidth=1)
ax.axvline(
    ci_lo,
    color="red",
    linestyle="--",
    alpha=0.7,
    label=f"95% CI [{ci_lo:+.4f}, {ci_hi:+.4f}]",
)
ax.axvline(ci_hi, color="red", linestyle="--", alpha=0.7)
ax.axvline(
    val_delta, color="blue", linestyle="-", alpha=0.7, label=f"Delta={val_delta:+.4f}"
)
ax.set_xlabel("Delta (lambda* - 0.0)")
ax.set_ylabel("Count")
ax.set_title(f"Bootstrap Delta Distribution (n={N_BOOTSTRAP:,})")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Plot 6: Decision summary text
ax = axes[1, 2]
ax.axis("off")
summary_text = (
    f"Lambda Tuning Result\n"
    f"{'=' * 30}\n\n"
    f"Selected lambda*: {lambda_star:.1f}\n"
    f"pass_threshold: {PASS_THRESHOLD:.1f}\n"
    f"Val delta: {val_delta:+.4f}\n"
    f"Bootstrap 95% CI: [{ci_lo:+.4f}, {ci_hi:+.4f}]\n"
    f"CI excludes 0: {ci_excludes_zero}\n\n"
    f"Val bid_rate: {val_result_star['bid_rate']:.3f}\n"
    f"Val make_rate: {val_result_star['make_rate']:.3f}\n\n"
    f"Train: {n_train_deals:,} deals, Val: {n_val_deals:,} deals\n"
    f"MODE={MODE}\n"
    f"Grid: {LAMBDA_GRID}\n"
    f"Guardrails: bid_rate [{BID_RATE_FLOOR}, {BID_RATE_CAP}],\n"
    f"  make_rate >= {MAKE_RATE_FLOOR}"
)
ax.text(
    0.05,
    0.95,
    summary_text,
    transform=ax.transAxes,
    fontsize=10,
    verticalalignment="top",
    fontfamily="monospace",
    bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
)
ax.set_title("Decision Summary")

plt.tight_layout()
if CHART_OUTPUT_DIR:
    _chart_out = Path(CHART_OUTPUT_DIR)
    _chart_out.mkdir(parents=True, exist_ok=True)
    fig.savefig(_chart_out / "lambda_tuning_sweep.png", dpi=150, bbox_inches="tight")
    print(f"Saved: {_chart_out / 'lambda_tuning_sweep.png'}")
plt.show()

# %%
# --- Full results table ---
print(f"\n{'=' * 100}")
print("FULL-DATA OVERVIEW RESULTS TABLE")
print(f"{'=' * 100}")
print(
    f"{'lambda':>8} | {'net_eppd':>10} | "
    f"{'bid_rate':>10} | "
    f"{'make_rate':>10} | {'mean_bid_n':>10} | {'n_bid':>8}"
)
print(f"{'-' * 100}")
for _, row in overview_df.iterrows():
    marker = " <- lambda*" if row["risk_lambda"] == lambda_star else ""
    print(
        f"{row['risk_lambda']:>8.1f} | {row['net_eppd']:>10.4f} | "
        f"{row['bid_rate']:>10.3f} | "
        f"{row['make_rate']:>10.3f} | "
        f"{row['mean_bid_n']:>10.2f} | "
        f"{row['n_bid']:>8.0f}{marker}"
    )
print(f"{'=' * 100}")
