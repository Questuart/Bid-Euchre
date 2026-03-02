# R0 v2 Pass-Threshold Tuning Protocol

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 v2 (corrected baseline)
**Date:** 2026-03-02
**Type:** Pre-registered analysis protocol
**Status:** PRE-REGISTERED (not yet executed)
**Governs:** Track C (Threshold Tuning) of R0 Canonical v2
**Supersedes:** `plans/r0_pass_threshold_protocol.md` (v1)

---

## 0. Registration Statement

This protocol is **pre-registered**: all analysis choices (candidate grid, primary
endpoint, split method, decision rule) are locked before execution. No post-hoc
adjustments to the grid, success criteria, or decision rules are permitted. If the
protocol is insufficient, it must be amended with a new version (v3) documenting
the rationale, and the amendment must be recorded before re-execution.

**Protocol version:** v2
**Predecessor:** `plans/r0_pass_threshold_protocol.md` (v1, executed, decision: RETAIN t=0.0)
**Registration PR:** (to be filled on merge)

---

## 1. Motivation

### 1.1 Relationship to v1

The v1 pass-threshold protocol (`plans/r0_pass_threshold_protocol.md`) was executed
during the R0 finalization sprint. The result was **RETAIN**: t=0.0 was optimal for
the v1 bidding policy, which used `floor(mu)` as the sole bid-level candidate. Net
differential decreased monotonically with higher thresholds, indicating that marginal
hands admitted by lowering the pass gate could not be profitably bid under the
floor-only policy.

### 1.2 Why v2 May Differ

The v2 bidding policy introduces `compute_best_bid()` with `bid_level_search=True`
(`bidding.py:788`). Instead of evaluating only `floor(mu)`, the v2 policy searches
all legal bid levels (1-10) and selects the level with highest utility. This changes
the utility landscape in two ways:

1. **Higher utility for marginal hands:** Hands near the pass boundary may have
   negative utility at `floor(mu)` but positive utility at a lower bid level.
   Bid-level search discovers these opportunities.

2. **Different optimal bid distribution:** The search may shift the bid-level
   distribution downward (more conservative bids that make more often), altering
   the make_rate vs bid_rate tradeoff.

These changes mean the optimal pass threshold `t` for the v2 policy may differ
from the v1 result. The threshold must be re-tuned against the v2 decision layer.

### 1.3 Threshold as Hyperparameter

The pass threshold `t` is a **rung-level hyperparameter** of the bidding policy:

| Parameter | Where Set | When Re-tuned | Current Value |
|-----------|-----------|---------------|---------------|
| OLS coefficients | `hybrid_r0.json` | Per-rung | Per-contract arm |
| residual_variance (sigma) | `hybrid_r0.json` | Per-rung | Per-contract family |
| risk_lambda | Experiment config | Per-rung (Track D) | 0.0 |
| **pass_threshold (t)** | **Bidding policy** | **Per-rung / per-policy-version** | **0.0** |
| bid_level_search | Experiment config | Per-policy-version | `true` (v2) |

**Convention:** `t` is non-negative. Pass rule: `utility <= -t` (`bidding.py:847`).
Positive `t` means the model tolerates negative expected utility before passing.

---

## 2. Protocol Design

### 2.1 Data Source

**Dataset:** `canonical_bidless_dataset_glutton_42_20260221_175752`
(same as v1 protocol and oracle analysis, PR #472)

**Joined data:** 40,000 hand observations (10,000 deals x 4 seats), each with
6 paired contract outcomes, model predictions (mu, sigma, predicted_utility),
and oracle labels.

### 2.2 Train/Validation Split

**Split method:** GroupKFold by `deal_id` to avoid seat-level leakage
(each deal's 4 seat observations stay in the same partition)

| Partition | Allocation | Deals | Hands | Purpose |
|-----------|-----------|-------|-------|---------|
| Train | deal_id hash % 5 in {0,1,2} | ~6,000 | ~24,000 | Select optimal threshold |
| Validation | deal_id hash % 5 in {3,4} | ~4,000 | ~16,000 | Evaluate selected threshold |

**Split implementation:** Same deterministic hash-based partition as v1:
```python
import hashlib

def deal_partition(deal_id: str, seed: int = 42) -> str:
    """Deterministic partition assignment based on deal_id hash."""
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"
```

**Rationale for 60/40 split:** The threshold grid has only 7 candidates, so
the train set does not need to be large. A generous validation set (40%) provides
tighter CIs on the held-out evaluation. Grouping by `deal_id` prevents leakage.

### 2.3 Candidate Threshold Grid

| t | Pass rule | Interpretation |
|---|-----------|----------------|
| 0.0 | utility <= 0 | **Current behavior (status quo)** |
| 0.1 | utility <= -0.1 | Mild aggression |
| 0.2 | utility <= -0.2 | Mild-moderate aggression |
| 0.5 | utility <= -0.5 | Moderate aggression |
| 1.0 | utility <= -1.0 | High aggression |
| 2.0 | utility <= -2.0 | Very high aggression |
| 5.0 | utility <= -5.0 | Exploratory (near-always-bid) |

**Grid rationale:** Same 7-point grid as specified in the R0 v2 plan. Sparser than
v1's 11-point grid because the v1 result showed monotonic decline across all
candidates -- the v2 grid focuses on the low end (0.0-0.5) where bid-level search
is most likely to change the outcome, with wider exploratory points for bounding.

### 2.4 Key Change from v1: Utility Calculation

In v1, utility was computed using `floor(mu)` as the sole bid level. In v2,
utility is computed via `compute_best_bid()` (`bidding.py:788`) with
`bid_level_search=True`:

```python
result = compute_best_bid(
    mu=mu,
    sigma=sigma,
    current_high_bid=0,  # opening position
    pass_threshold=t,
    bid_level_search=True,
    risk_lambda=risk_lambda,  # from Track D, initially 0.0
    seed=42,
)
```

This searches all legal bid levels (1-10) and returns the `(bid_n, utility)` pair
with highest utility, or `None` if no level exceeds `-t`.

### 2.5 Primary Endpoint

**net_eppd on the validation partition**, computed as:

For each hand in validation:
1. For each of the 6 contracts, call `compute_best_bid()` with threshold `t`
   and `bid_level_search=True`
2. Select the contract with highest utility (if any pass the threshold)
3. If the model bids: use `bid_n` from search, look up actual outcome from
   paired data, compute `net = actual_net` for chosen contract at chosen level
4. If the model passes: net = 0 (per oracle convention)

### 2.6 Guardrails

| Guardrail | Threshold | Rationale |
|-----------|-----------|-----------|
| bid_rate in [0.05, 0.95] | Hard bounds | Below 5%: model nearly always passes (too conservative). Above 95%: near-always-bid defeats selective bidding |
| make_rate >= 0.45 | Hard floor | Below 45%, sets dominate and returns are structurally negative |

If the optimal `t` by primary endpoint violates any guardrail, select the
largest `t` that satisfies all guardrails. If no `t > 0` satisfies guardrails,
retain `t = 0.0`.

---

## 3. Decision Rule

### 3.1 Selection on Train

1. Compute primary endpoint for each candidate `t` on **train** partition,
   using `compute_best_bid()` with `bid_level_search=True`
2. Apply guardrails: discard candidates that violate hard bounds
3. Select `t*_train` = candidate with highest net_eppd among survivors

### 3.2 Validation

1. Compute primary endpoint + guardrail metrics for `t*_train` and `t = 0.0`
   on **validation** partition
2. Compute improvement: `delta = net_eppd(t*_train) - net_eppd(t=0.0)`
3. Bootstrap 95% CI on delta (10,000 resamples, seed 42, grouped by deal_id)

### 3.3 Decision Gate

| Condition | Decision | Action |
|-----------|----------|--------|
| delta > 0 AND CI excludes 0 AND guardrails pass | **ADOPT** | Set threshold for v2 policy, record in model artifact |
| delta CI includes 0 | **RETAIN** | Keep t=0.0, no change |
| delta < 0 | **RETAIN** | Threshold tuning harmful, keep t=0.0 |

**Note:** Unlike v1 (which had a 0.05 SESOI for within-R0 hyperparameter changes),
v2 threshold tuning uses only CI-excludes-0 as the adoption gate. The rationale:
threshold tuning is a free parameter of the v2 policy being established, not an
incremental tweak to an existing baseline. Any statistically significant improvement
is worth adopting at no additional cost.

### 3.4 Implementation (if ADOPT)

If the decision is ADOPT:
1. Record `pass_threshold: t*` in the corrected baseline configuration
2. Update `risk_lambda: 0.0` placeholders after Track D selects lambda
   (threshold and lambda are tuned sequentially -- threshold first, lambda second)
3. Re-run validation with both threshold and lambda applied
4. Store `t*` in the rung bundle for reproducibility

---

## 4. Interaction with Track D (Lambda Tuning)

Threshold and lambda tuning are **sequential**, not joint:

1. **Track C (this protocol):** Tune threshold `t` with `risk_lambda=0.0`
2. **Track D (`plans/r0_v2_lambda_tuning_protocol.md`):** Tune lambda with
   `pass_threshold=t*` (from Track C result)

If Track C selects `t* = 0.0` (RETAIN), Track D proceeds with `t = 0.0`.
If Track C adopts a non-zero threshold, Track D uses it.

**Why not joint optimization?** The 7x6 = 42 cell grid is feasible but the
sequential approach is simpler to validate, and the interaction between `t` and
`lambda` is expected to be weak: `t` controls which hands enter the bidding pool,
while `lambda` controls the risk penalty on hands already in the pool.

---

## 5. Provenance

| Item | Value |
|------|-------|
| Protocol version | v2 |
| Predecessor | `plans/r0_pass_threshold_protocol.md` (v1, RETAIN) |
| v1 decision report | `docs/04_reports/r0/pass_threshold_decision.md` |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Model artifact | `data/artifacts/arc_d/r0/hybrid_r0.json` |
| Bidder entry point | `compute_best_bid()` (`bidding.py:788`) |
| Pass gate | `bidding.py:847` (`best_utility <= -pass_threshold`) |
| Split seed | 42 |
| Bootstrap seed | 42 |
| Bootstrap resamples | 10,000 |
| Grid | [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0] |

---

## 6. Amendment Log

| Version | Date | Change | Rationale |
|---------|------|--------|-----------|
| v1 | 2026-03-01 | Initial protocol | Pre-registered before execution |
| v1-exec | 2026-03-02 | Executed; decision RETAIN (t=0 optimal for floor-only policy) | Monotonic decline in net_diff |
| v2 | 2026-03-02 | Re-tune for `bid_level_search=True` policy | v2 policy changes utility landscape; v1 result may not transfer |
