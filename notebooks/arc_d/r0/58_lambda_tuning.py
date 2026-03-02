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
# **Grid:** `[0.0, 0.1, 0.2, 0.5, 1.0, 2.0]`
#
# **Primary endpoint:** net_eppd (net expected points per deal) on held-out folds
#
# **Guardrails:**
# - bid_rate in [0.05, 0.95]
# - make_rate >= 0.45
#
# **Selection:** max net_eppd subject to guardrails passing
#
# **Sections:**
# - S0: Setup & configuration
# - S1: Data loading & preparation
# - S2: Lambda grid sweep (per-hand replay)
# - S3: GroupKFold cross-validation
# - S4: Selection + guardrails
# - S5: Report summary & visualizations

# %% tags=["parameters"]
MODE = "SMOKE"  # SMOKE (~100 deals), QUICK (~2000 deals), FULL (all)
SEED = 42
ARTIFACT_PATH = "data/artifacts/arc_d/r0/hybrid_r0.json"
CHART_OUTPUT_DIR = ""  # Set via papermill; empty = skip chart save

# %%
import hashlib
import json
import math
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

# --- Protocol constants ---
LAMBDA_GRID = [0.0, 0.1, 0.2, 0.5, 1.0, 2.0]
N_FOLDS = 5
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
def evaluate_lambda(df: pd.DataFrame, risk_lambda: float) -> dict:
    """Evaluate a lambda value on wide-format data (6 contracts per hand).

    For each hand, find the best contract via compute_best_bid logic:
    - For each of 6 contracts, compute utility = EV - risk_penalty at optimal bid_n
    - Select the contract with max utility
    - If best utility <= 0 (pass threshold), the hand passes (net=0)
    - If hand bids, compute actual net from realized tricks

    Returns dict of endpoint metrics.
    """
    n = len(df)
    net_per_hand = np.zeros(n)
    bid_flags = np.zeros(n, dtype=bool)
    make_flags = np.full(n, np.nan)
    bid_n_chosen = np.zeros(n, dtype=int)

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
                pass_threshold=0.0,
                bid_level_search=True,
                risk_lambda=risk_lambda,
                seed=SEED,
            )

            if result is None:
                continue

            bid_n, utility = result

            if best_utility is None or utility > best_utility:
                best_utility = utility
                best_contract = ck
                best_bid_n = bid_n

        # Decision: bid or pass
        if best_utility is not None and best_utility > 0:
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
    }


# %%
# Quick full-data sweep for overview (before CV)
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
    result = evaluate_lambda(pred_wide, lam)
    overview_results.append(result)
    print(
        f"{lam:>8.1f} {result['net_eppd']:>10.4f} {result['bid_rate']:>10.3f} "
        f"{result['make_rate']:>10.3f} {result['mean_bid_n']:>10.2f} "
        f"{result['n_bid']:>8d}"
    )

overview_df = pd.DataFrame(
    [{k: v for k, v in r.items() if k != "net_per_hand"} for r in overview_results]
)
print(f"{'=' * 90}")

# %% [markdown]
# ## S3: GroupKFold Cross-Validation
#
# Split deals into K=5 folds by deal_id (GroupKFold). For each fold:
# - Evaluate all lambda values on the held-out fold
# - The "training" step is just selecting which lambda is best on the
#   non-held-out folds (we're tuning a decision hyperparameter, not
#   retraining OLS coefficients)

# %%
# Assign fold IDs deterministically by hashing deal_id
deal_ids = pred_wide["deal_id"].unique()


def assign_fold(deal_id, n_folds: int = N_FOLDS, seed: int = SEED) -> int:
    """Deterministic fold assignment based on deal_id hash."""
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    return int(h[:8], 16) % n_folds


fold_map = {did: assign_fold(did) for did in deal_ids}
pred_wide["fold"] = pred_wide["deal_id"].map(fold_map)

fold_counts = pred_wide.groupby("fold")["deal_id"].nunique()
print("Fold distribution (n_deals per fold):")
for fold_id, count in fold_counts.items():
    print(f"  Fold {fold_id}: {count:,} deals")

# Validate: no deal appears in multiple folds
assert pred_wide.groupby("deal_id")["fold"].nunique().max() == 1, "Fold leakage!"

# %%
# Cross-validation sweep
cv_results = []

for fold_id in range(N_FOLDS):
    val_mask = pred_wide["fold"] == fold_id
    val_fold = pred_wide[val_mask]
    train_fold = pred_wide[~val_mask]

    for lam in LAMBDA_GRID:
        val_result = evaluate_lambda(val_fold, lam)
        train_result = evaluate_lambda(train_fold, lam)

        cv_results.append(
            {
                "fold": fold_id,
                "risk_lambda": lam,
                "val_net_eppd": val_result["net_eppd"],
                "val_bid_rate": val_result["bid_rate"],
                "val_make_rate": val_result["make_rate"],
                "val_n_bid": val_result["n_bid"],
                "val_n_total": val_result["n_total"],
                "train_net_eppd": train_result["net_eppd"],
                "train_bid_rate": train_result["bid_rate"],
                "train_make_rate": train_result["make_rate"],
            }
        )

cv_df = pd.DataFrame(cv_results)
print(f"CV results: {len(cv_df)} rows ({N_FOLDS} folds x {len(LAMBDA_GRID)} lambdas)")

# %%
# Aggregate CV results: mean +/- std across folds
cv_agg = (
    cv_df.groupby("risk_lambda")
    .agg(
        mean_val_net_eppd=("val_net_eppd", "mean"),
        std_val_net_eppd=("val_net_eppd", "std"),
        mean_val_bid_rate=("val_bid_rate", "mean"),
        std_val_bid_rate=("val_bid_rate", "std"),
        mean_val_make_rate=("val_make_rate", "mean"),
        std_val_make_rate=("val_make_rate", "std"),
        mean_train_net_eppd=("train_net_eppd", "mean"),
        std_train_net_eppd=("train_net_eppd", "std"),
    )
    .reset_index()
)

print(f"\n{'=' * 100}")
print(f"CROSS-VALIDATION SUMMARY ({N_FOLDS}-fold GroupKFold)")
print(f"{'=' * 100}")
print(
    f"{'lambda':>8} {'val_eppd':>10} {'(std)':>8} {'train_eppd':>12} "
    f"{'val_bid%':>10} {'val_make%':>10}"
)
print(f"{'-' * 100}")
for _, row in cv_agg.iterrows():
    print(
        f"{row['risk_lambda']:>8.1f} {row['mean_val_net_eppd']:>10.4f} "
        f"({row['std_val_net_eppd']:>6.4f}) {row['mean_train_net_eppd']:>12.4f} "
        f"{row['mean_val_bid_rate']:>10.3f} {row['mean_val_make_rate']:>10.3f}"
    )
print(f"{'=' * 100}")

# %% [markdown]
# ## S4: Selection + Guardrails
#
# Apply guardrails to filter candidates, then select the lambda with
# the highest mean cross-validated net_eppd.

# %%
# Apply guardrails
cv_agg["pass_bid_rate_floor"] = cv_agg["mean_val_bid_rate"] >= BID_RATE_FLOOR
cv_agg["pass_bid_rate_cap"] = cv_agg["mean_val_bid_rate"] <= BID_RATE_CAP
cv_agg["pass_make_rate"] = cv_agg["mean_val_make_rate"] >= MAKE_RATE_FLOOR
cv_agg["all_guardrails"] = (
    cv_agg["pass_bid_rate_floor"]
    & cv_agg["pass_bid_rate_cap"]
    & cv_agg["pass_make_rate"]
)

survivors = cv_agg[cv_agg["all_guardrails"]]
disqualified = cv_agg[~cv_agg["all_guardrails"]]

print(f"Survivors: {len(survivors)} / {len(cv_agg)} candidates")
if len(disqualified) > 0:
    print(f"Disqualified: {list(disqualified['risk_lambda'].values)}")
    for _, row in disqualified.iterrows():
        reasons = []
        if not row["pass_bid_rate_floor"]:
            reasons.append(
                f"bid_rate={row['mean_val_bid_rate']:.3f} < {BID_RATE_FLOOR}"
            )
        if not row["pass_bid_rate_cap"]:
            reasons.append(f"bid_rate={row['mean_val_bid_rate']:.3f} > {BID_RATE_CAP}")
        if not row["pass_make_rate"]:
            reasons.append(
                f"make_rate={row['mean_val_make_rate']:.3f} < {MAKE_RATE_FLOOR}"
            )
        print(f"  lambda={row['risk_lambda']:.1f}: {', '.join(reasons)}")

# %%
# Select best lambda among survivors
if len(survivors) == 0:
    print("WARNING: No candidates pass all guardrails. Retaining lambda=0.0.")
    lambda_star = 0.0
else:
    best_row = survivors.loc[survivors["mean_val_net_eppd"].idxmax()]
    lambda_star = best_row["risk_lambda"]

lambda_star_agg = cv_agg[cv_agg["risk_lambda"] == lambda_star].iloc[0]
baseline_agg = cv_agg[cv_agg["risk_lambda"] == 0.0].iloc[0]

cv_delta = lambda_star_agg["mean_val_net_eppd"] - baseline_agg["mean_val_net_eppd"]

print(f"\n{'=' * 60}")
print("SELECTION RESULT")
print(f"{'=' * 60}")
print(f"  lambda* (selected):   {lambda_star:.1f}")
print(f"  CV net_eppd(lambda*): {lambda_star_agg['mean_val_net_eppd']:.4f}")
print(f"  CV net_eppd(0.0):     {baseline_agg['mean_val_net_eppd']:.4f}")
print(f"  CV delta:             {cv_delta:+.4f}")
print(f"  CV bid_rate:          {lambda_star_agg['mean_val_bid_rate']:.3f}")
print(f"  CV make_rate:         {lambda_star_agg['mean_val_make_rate']:.3f}")
print(f"{'=' * 60}")

# %%
# Bootstrap 95% CI on delta (lambda* vs lambda=0) using per-fold results
# Resample folds to estimate uncertainty in the CV mean difference

# Get per-fold deltas
fold_deltas = []
for fold_id in range(N_FOLDS):
    fold_cv = cv_df[cv_df["fold"] == fold_id]
    star_eppd = fold_cv.loc[
        fold_cv["risk_lambda"] == lambda_star, "val_net_eppd"
    ].values[0]
    base_eppd = fold_cv.loc[fold_cv["risk_lambda"] == 0.0, "val_net_eppd"].values[0]
    fold_deltas.append(star_eppd - base_eppd)

fold_deltas = np.array(fold_deltas)
print(f"Per-fold deltas (lambda*={lambda_star:.1f} vs 0.0): {fold_deltas}")

# Also do deal-level bootstrap for tighter CI
# Get per-deal net for lambda* and lambda=0 from the full-data sweep
net_star = overview_results[LAMBDA_GRID.index(lambda_star)]["net_per_hand"]
net_baseline = overview_results[LAMBDA_GRID.index(0.0)]["net_per_hand"]
deal_deltas = net_star - net_baseline

rng = np.random.RandomState(BOOTSTRAP_SEED)
boot_deltas = np.array(
    [
        rng.choice(deal_deltas, size=len(deal_deltas), replace=True).mean()
        for _ in range(N_BOOTSTRAP)
    ]
)
ci_lo, ci_hi = np.percentile(boot_deltas, [2.5, 97.5])
ci_excludes_zero = ci_lo > 0 or ci_hi < 0

print("\nBootstrap 95% CI on delta (deal-level):")
print(f"  Delta: {cv_delta:+.4f}")
print(f"  95% CI: [{ci_lo:+.4f}, {ci_hi:+.4f}]")
print(f"  CI excludes 0: {ci_excludes_zero}")

# %% [markdown]
# ## S5: Report Summary & Visualizations

# %%
# --- Decision summary ---
print(f"\n{'=' * 70}")
print("LAMBDA TUNING DECISION SUMMARY")
print(f"{'=' * 70}")
print(f"  Selected lambda*:     {lambda_star:.1f}")
print(f"  CV net_eppd delta:    {cv_delta:+.4f} (lambda* vs 0.0)")
print(f"  Bootstrap 95% CI:     [{ci_lo:+.4f}, {ci_hi:+.4f}]")
print(f"  CI excludes 0:        {ci_excludes_zero}")
print(f"  CV bid_rate:          {lambda_star_agg['mean_val_bid_rate']:.3f}")
print(f"  CV make_rate:         {lambda_star_agg['mean_val_make_rate']:.3f}")
print()

if lambda_star == 0.0:
    print("  RESULT: lambda=0.0 is optimal. No risk penalty improves net_eppd.")
    print("  ACTION: Retain risk_lambda=0.0 in all configs (no change needed).")
elif ci_excludes_zero and cv_delta > 0:
    print(f"  RESULT: lambda={lambda_star:.1f} significantly improves net_eppd.")
    print(f"  ACTION: Update risk_lambda to {lambda_star:.1f} in canonical configs:")
    print("    - experiments/configs/auction_comparator.yaml")
    print("    - experiments/configs/arc_d_r0_c33_ablation.yaml")
    print("    - scripts/internal/run_arc_d_h2h_battery.py (DEFAULT_ROSTER)")
else:
    print(f"  RESULT: lambda={lambda_star:.1f} selected but CI includes 0.")
    print("  ACTION: Retain risk_lambda=0.0 (effect not significant).")

print(f"{'=' * 70}")

# %%
# --- Visualization ---
fig, axes = plt.subplots(2, 3, figsize=(16, 10))
fig.suptitle(f"Lambda Tuning Sweep (Track D, R0 v2) -- MODE={MODE}", fontsize=14)

# Plot 1: Net EPPD vs lambda
ax = axes[0, 0]
ax.errorbar(
    cv_agg["risk_lambda"],
    cv_agg["mean_val_net_eppd"],
    yerr=cv_agg["std_val_net_eppd"],
    fmt="o-",
    label="Val (CV mean +/- std)",
    color="C1",
    capsize=4,
)
ax.plot(
    cv_agg["risk_lambda"],
    cv_agg["mean_train_net_eppd"],
    "s--",
    label="Train (CV mean)",
    color="C0",
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
ax.set_ylabel("Mean Net EPPD")
ax.set_title("Primary: Net EPPD vs Lambda")
ax.legend(fontsize=8)
ax.grid(True, alpha=0.3)

# Plot 2: Bid rate vs lambda
ax = axes[0, 1]
ax.errorbar(
    cv_agg["risk_lambda"],
    cv_agg["mean_val_bid_rate"],
    yerr=cv_agg["std_val_bid_rate"],
    fmt="o-",
    label="Val (CV)",
    color="C1",
    capsize=4,
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
ax.errorbar(
    cv_agg["risk_lambda"],
    cv_agg["mean_val_make_rate"],
    yerr=cv_agg["std_val_make_rate"],
    fmt="o-",
    label="Val (CV)",
    color="C1",
    capsize=4,
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

# Plot 4: Per-fold net_eppd profiles
ax = axes[1, 0]
for fold_id in range(N_FOLDS):
    fold_data = cv_df[cv_df["fold"] == fold_id]
    ax.plot(
        fold_data["risk_lambda"],
        fold_data["val_net_eppd"],
        "o-",
        alpha=0.5,
        label=f"Fold {fold_id}",
        markersize=4,
    )
ax.plot(
    cv_agg["risk_lambda"],
    cv_agg["mean_val_net_eppd"],
    "k-",
    linewidth=2,
    label="CV Mean",
)
ax.axvline(lambda_star, color="red", linestyle=":", alpha=0.7)
ax.set_xlabel("risk_lambda")
ax.set_ylabel("Val Net EPPD")
ax.set_title("Per-Fold Val Net EPPD")
ax.legend(fontsize=7, ncol=2)
ax.grid(True, alpha=0.3)

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
    cv_delta, color="blue", linestyle="-", alpha=0.7, label=f"Delta={cv_delta:+.4f}"
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
    f"CV delta: {cv_delta:+.4f}\n"
    f"Bootstrap 95% CI: [{ci_lo:+.4f}, {ci_hi:+.4f}]\n"
    f"CI excludes 0: {ci_excludes_zero}\n\n"
    f"CV bid_rate: {lambda_star_agg['mean_val_bid_rate']:.3f}\n"
    f"CV make_rate: {lambda_star_agg['mean_val_make_rate']:.3f}\n\n"
    f"MODE={MODE}, n_hands={n_hands:,}\n"
    f"Grid: {LAMBDA_GRID}\n"
    f"K-fold: {N_FOLDS}\n"
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
print(f"\n{'=' * 110}")
print("FULL CROSS-VALIDATION RESULTS TABLE")
print(f"{'=' * 110}")
print(
    f"{'lambda':>8} | {'CV val_eppd':>12} {'(std)':>8} | "
    f"{'CV bid_rate':>12} {'(std)':>8} | "
    f"{'CV make_rate':>12} {'(std)':>8} | {'Guards':>6}"
)
print(f"{'-' * 110}")
for _, row in cv_agg.iterrows():
    guard = "PASS" if row["all_guardrails"] else "FAIL"
    marker = " <- lambda*" if row["risk_lambda"] == lambda_star else ""
    print(
        f"{row['risk_lambda']:>8.1f} | {row['mean_val_net_eppd']:>12.4f} "
        f"({row['std_val_net_eppd']:>6.4f}) | "
        f"{row['mean_val_bid_rate']:>12.3f} ({row['std_val_bid_rate']:>6.4f}) | "
        f"{row['mean_val_make_rate']:>12.3f} ({row['std_val_make_rate']:>6.4f}) | "
        f"{guard:>6}{marker}"
    )
print(f"{'=' * 110}")
