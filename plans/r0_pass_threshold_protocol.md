# R0 Pass-Threshold Tuning Protocol

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Date:** 2026-03-01
**Type:** Pre-registered analysis protocol
**Status:** PRE-REGISTERED (not yet executed)
**Governs:** MASTER_PLAN.md Phase B0

---

## 0. Registration Statement

This protocol is **pre-registered**: all analysis choices (candidate grid, primary
endpoint, split method, decision rule) are locked before execution. No post-hoc
adjustments to the grid, success criteria, or decision rules are permitted. If the
protocol is insufficient, it must be amended with a new version (v2) documenting
the rationale, and the amendment must be recorded before re-execution.

**Protocol version:** v1
**Registration PR:** (to be filled on merge)

---

## 1. Motivation

The contract selection oracle analysis (PR #472) revealed that **82% of total
regret** comes from the pass-threshold — the model passes on hands where the
oracle would profitably bid. The current pass gate is hardcoded at `utility <= 0`
(`bidding.py:1043`):

```python
if best_utility is None or best_utility <= 0:
    return BidAction.pass_bid()
```

This protocol investigates whether tuning the threshold `t` (passing when
`utility <= -t` instead of `utility <= 0`) recovers a meaningful share of
pass-threshold regret without introducing excessive over-bidding regret.

**Why not just lower the threshold ad-hoc?** The current threshold (`t = 0`)
interacts with model predictions (mu, sigma) in complex ways. Lowering the
threshold admits more hands into the bidding pool, but some of those hands
will fail to make their contracts, generating set penalties. The optimal `t`
balances the expected gain from newly-admitted profitable hands against the
expected loss from newly-admitted unprofitable hands. This balance depends on
the model's prediction quality — which varies by contract type and feature
count — so the optimal threshold is rung-specific.

### 1.1 Threshold as Hyperparameter

The pass threshold `t` is a **rung-level hyperparameter** of the bidding policy:

| Parameter | Where Set | When Re-tuned | Current Value |
|-----------|-----------|---------------|---------------|
| OLS coefficients | `hybrid_r0.json` | Per-rung (R0, R1, ...) | Per-contract arm |
| residual_variance (sigma) | `hybrid_r0.json` | Per-rung | Per-contract family |
| risk_lambda | Experiment config | Per-rung (planned R3+) | 0.0 |
| **pass_threshold (t)** | **Bidding policy** | **Per-rung** | **0.0** |

**Convention:** `t` is expressed as a non-negative number. The pass rule is
`utility <= -t`. When `t = 0`, this is `utility <= 0` (current behavior).
Positive `t` means the model tolerates negative expected utility before passing —
i.e., it bids more aggressively.

**Rung-specific tuning:** The optimal `t` depends on the model's prediction
accuracy, which changes with each rung (new features, better models). R0's
optimal `t` will likely differ from R1's. Each rung that changes model
coefficients should re-tune `t` using that rung's oracle data.

---

## 2. Protocol Design

### 2.1 Data Source

**Dataset:** `canonical_bidless_dataset_glutton_42_20260221_175752`
(same as oracle analysis, PR #472)

**Joined data:** 40,000 hand observations (10,000 deals x 4 seats), each with
6 paired contract outcomes, model predictions (mu, bid_n, predicted_utility),
and oracle labels.

### 2.2 Train/Validation Split

**Split method:** Stratified by `deal_id`, deterministic

| Partition | deal_id range | Deals | Hands | Purpose |
|-----------|--------------|-------|-------|---------|
| Train | deal_id hash % 5 in {0,1,2} | ~6,000 | ~24,000 | Select optimal threshold |
| Validation | deal_id hash % 5 in {3,4} | ~4,000 | ~16,000 | Evaluate selected threshold |

**Split implementation:**
```python
import hashlib

def deal_partition(deal_id: str, seed: int = 42) -> str:
    """Deterministic partition assignment based on deal_id hash."""
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"
```

**Rationale for 60/40 split:** The threshold grid has only 11 candidates, so
the train set does not need to be large. A generous validation set (40%) provides
tighter CIs on the held-out evaluation. Grouping by `deal_id` prevents leakage
(each deal's 4 seat observations stay in the same partition).

### 2.3 Candidate Threshold Grid

| t | Pass rule | Interpretation |
|---|-----------|----------------|
| 0.00 | utility <= 0 | **Current behavior (status quo)** |
| 0.25 | utility <= -0.25 | Mild aggression |
| 0.50 | utility <= -0.50 | Moderate aggression |
| 0.75 | utility <= -0.75 | High aggression |
| 1.00 | utility <= -1.00 | Very high aggression |
| 1.50 | utility <= -1.50 | Extreme aggression |
| 2.00 | utility <= -2.00 | Near-max aggression |
| 2.50 | utility <= -2.50 | Exploratory |
| 3.00 | utility <= -3.00 | Exploratory |
| 4.00 | utility <= -4.00 | Exploratory |
| 5.00 | utility <= -5.00 | Exploratory (near-always-bid) |

**Grid rationale:** Fine resolution in the 0–2 range where the optimal threshold
is most likely to fall (based on the oracle's mean regret of 3.92 utility and the
model's sigma ~1.6). Coarser exploratory points at 3–5 to bound the curve.

### 2.4 Primary Endpoint

**Mean net-differential per hand (net_diff_mean)** on the validation partition,
computed as:

For each hand in validation:
1. Compute `best_utility_t` = max utility across all 6 contracts
2. If `best_utility_t > -t`: model bids on `argmax` contract with `bid_n = floor(mu)`
3. If `best_utility_t <= -t`: model passes (net = 0 per oracle convention)
4. Net = `actual_net` for chosen contract using paired outcome data

This replicates the oracle analysis pipeline but with threshold `t` instead of 0.

### 2.5 Secondary Endpoints

| Endpoint | Definition | Purpose |
|----------|-----------|---------|
| bid_rate_t | Fraction of hands where model bids at threshold t | Measure aggression |
| make_rate_t | P(tricks >= bid_n) among hands that bid | Measure quality of admitted hands |
| mean_regret_t | Oracle regret at threshold t | Measure remaining gap |
| pass_regret_share_t | % of regret from pass-threshold category | Track regret rebalancing |
| cs_regret_share_t | % of regret from contract-selection category | Track regret rebalancing |
| overbid_regret_share_t | % of regret from over-bidding category | Guardrail |

### 2.6 Guardrails

The threshold must not degrade bidding quality below safety floors:

| Guardrail | Threshold | Rationale |
|-----------|-----------|-----------|
| make_rate_t >= 60% | Hard floor | Below 60% make rate, sets dominate and net becomes negative |
| overbid_regret_share_t <= 10% | Hard floor | Over-bidding should not become the dominant regret source |
| bid_rate_t <= 95% | Soft cap | Near-always-bid defeats the purpose of selective bidding |

If the optimal `t` by primary endpoint violates any hard guardrail, select the
largest `t` that satisfies all guardrails. If no `t > 0` satisfies guardrails,
retain `t = 0`.

---

## 3. Decision Rule

### 3.1 Selection on Train

1. Compute primary endpoint for each candidate `t` on **train** partition
2. Apply guardrails: discard candidates that violate hard floors
3. Select `t*_train` = candidate with highest net_diff_mean among survivors

### 3.2 Validation

1. Compute primary + secondary endpoints for `t*_train` and `t = 0` on
   **validation** partition
2. Compute improvement: `delta = net_diff_mean(t*_train) - net_diff_mean(t=0)`
3. Bootstrap 95% CI on delta (10,000 resamples, seed 42, grouped by deal_id)

### 3.3 R0-Specific SESOI

**Smallest Effect Size of Interest (SESOI): 0.05 net_diff per hand**

Rationale: This is a within-R0 hyperparameter change, not a model improvement.
0.05 represents ~5% of a typical bid's value (a successful 5-bid yields net = 0,
a successful 6-bid yields net = +2). The promotion floor (0.180 net_eppd) is the
cross-rung improvement threshold; the within-R0 SESOI should be meaningfully
lower since we're comparing the same model with a different operating point.

### 3.4 Decision Gate

| Condition | Decision | Action |
|-----------|----------|--------|
| delta > SESOI AND CI excludes 0 AND guardrails pass | **ADOPT** | Implement threshold in bidder, record as R0 hyperparameter |
| delta > 0 AND CI excludes 0 BUT delta < SESOI | **NOTE** | Record finding, don't change R0 model, revisit at R1 |
| delta CI includes 0 | **RETAIN** | Keep t=0, no change |
| delta < 0 | **RETAIN** | Threshold tuning harmful, keep t=0 |

### 3.5 Implementation (if ADOPT)

If the decision is ADOPT:
1. Add `pass_threshold` parameter to `HybridOLSaBidder.__init__()` with default 0.0
2. Change `bidding.py:1043` from `best_utility <= 0` to `best_utility <= -self.pass_threshold`
3. Store `t` in the model artifact (`hybrid_r0.json` → add `pass_threshold` field)
4. Re-run R0 eval experiments (3 seeds) with the new threshold
5. Update R0 reports with threshold-aware metrics
6. Record `t` in the rung bundle (`rung_bundle_r0.json`)

---

## 4. Execution Plan

### 4.1 Implementation Steps

| Step | Work | Output |
|------|------|--------|
| 1 | Create notebook `56_pass_threshold_sweep.py` | Threshold sweep analysis |
| 2 | Implement train/val split | Split assignment function |
| 3 | Run sweep on train partition | net_diff_mean by t (11 candidates) |
| 4 | Evaluate t*_train on validation | Primary + secondary endpoints, bootstrap CIs |
| 5 | Apply decision gate | ADOPT / NOTE / RETAIN decision |
| 6 | Write threshold decision report | `docs/04_reports/r0/pass_threshold_decision.md` |

### 4.2 Dependencies

- **Requires:** Oracle analysis data (PR #472 — merged)
- **Requires:** Joined feature-outcome dataset with model predictions
  (reconstructed from notebook 55 pipeline, or cached as intermediate artifact)
- **Blocks:** B3 (R0 report finalization) — threshold must be decided first
- **Does not block:** A2 (pipeline), A3 (C33 ablation) — independent tracks

### 4.3 Estimated Effort

- 1 notebook (analysis + visualization)
- 1 PR (notebook + decision report + optional bidder code change)
- ~2 hours implementation, ~30 min execution (QUICK mode)

---

## 5. Provenance

| Item | Value |
|------|-------|
| Protocol version | v1 |
| Oracle analysis | PR #472, `docs/04_reports/r0/contract_selection_oracle.md` |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Model artifact | `data/artifacts/arc_d/r0/hybrid_r0.json` |
| Bidder pass gate | `src/bid_euchre/strategy/bidding.py:1043` |
| Split seed | 42 |
| Bootstrap seed | 42 |
| Bootstrap resamples | 10,000 |
| SESOI | 0.05 net_diff per hand |
| Grid | [0.00, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 2.50, 3.00, 4.00, 5.00] |

---

## 6. Amendment Log

| Version | Date | Change | Rationale |
|---------|------|--------|-----------|
| v1 | 2026-03-01 | Initial protocol | Pre-registered before execution |
