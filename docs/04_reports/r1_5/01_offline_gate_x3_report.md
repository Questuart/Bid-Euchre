# R1.5 Offline Gate X3 Report

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08
**Purpose:** Evaluate QUICK action-value model ranking quality against empirical oracle

## Executive Summary

Gate X3 (offline ranking accuracy) **failed all three sub-gates** against the
design spec thresholds. However, the failure is attributable to a specification
mismatch: the gate assumed an oracle built from averaged continuation rollouts,
but the dataset contains a single rollout per action. With ~47 actions per
state and bimodal make/set outcomes (net_points std = 8.1), the single-rollout
oracle is too noisy for exact top-1 agreement to be a meaningful metric.

Robust alternative metrics show the model has learned real structure: 84.6%
pairwise accuracy on the full action space (inflated by easy comparisons;
drops to ~55% on top-action slices), 3x lower regret than random, and a
positive mean outcome (+0.44 net_points) for the model's chosen action vs
-7.94 for random. The main behavioral concern is **over-passing**: the model
selects pass in 39.2% of states vs the oracle's 26.5%, and its regret
improvement over always-pass is only 16.1% (vs 67.6% over random).

**Decision:** X3 should not block promotion to gameplay screening. The gate
is mis-specified for single-rollout labels. Step 5 (3-seed gameplay screen)
is the right next test, with close attention to pass rate and net_eppd.

## 1. Motivation

The R1.5 design spec (plans/r1_5_training_plan.md, Step 3) defines Gate X3
as an offline screen before committing to gameplay evaluation. X3 checks
whether the action-value model can identify the best bidding action from a
menu of legal options without playing full games.

Three sub-gates were specified:

- **X3-rank:** Top-1 accuracy (model picks same action as oracle) >= 40%
  overall, >= 30% per family
- **X3-regret:** Mean regret (oracle_best - model_chosen) <= 1.5 net_points
- **X3-cal:** Cross-contract calibration — prediction gap <= 2.0, family
  agreement >= 60%

## 2. Methodology

### Dataset

- **Source:** QUICK action-value dataset (2,500 deals, seed 42)
- **Test split:** 250 deals, 1,000 states, 47,344 rows (10% by deal_id)
- **Actions per state:** Mean 47.3, median 61, range [13, 61]
- **Action structure:** 1 pass + up to 16 suit bids (4 trumps x 4 levels) +
  4 high + 4 low

### Oracle Definition

The oracle picks the action with the highest observed net_points from a
**single continuation rollout** per action. The design spec
(plans/r1_5_training_plan.md:445) defined the oracle as "the legal action
with highest empirical mean net_points (averaged over continuation rollouts),"
but the dataset generator (scripts/internal/generate_action_value_dataset.py)
produces one rollout per action. This is the root cause of the gate failure.

### Model

QUICK-trained action-value OLS (4 per-contract models). Artifact:
data/runs/action_value_quick_42/action_value_full.json

Gate X2 (training adequacy) passed: suit R^2=0.565, high R^2=0.533,
low R^2=0.514, pass R^2=0.046.

## 3. Results

### Gate X3 Formal Results (Failed)

| Sub-gate | Threshold | Actual | Verdict |
|----------|-----------|--------|---------|
| X3-rank (overall top-1) | >= 40% | 26.6% | FAIL |
| X3-rank (suit) | >= 30% | 15.7% | FAIL |
| X3-rank (high) | >= 30% | 6.7% | FAIL |
| X3-rank (low) | >= 30% | 16.9% | FAIL |
| X3-rank (pass) | >= 30% | 58.9% | PASS |
| X3-regret | <= 1.5 | 4.015 | FAIL |
| X3-cal (prediction gap) | <= 2.0 | 4.961 | FAIL |
| X3-cal (family agreement) | >= 60% | 46.8% | FAIL |

### Robust Alternative Metrics

#### Pairwise Accuracy

For every pair of actions in the same state, does the model order them
correctly (higher predicted value -> higher empirical outcome)?

| Slice | Accuracy | N pairs | Notes |
|-------|----------|---------|-------|
| All pairs (excl ties) | 84.6% | 1,000,421 | Inflated by easy comparisons |
| Close pairs (\|diff\| <= 1) | 72.9% | — | Harder discrimination |
| Close pairs (\|diff\| <= 2) | 70.0% | — | — |
| Within empirical top-3 | 55.6% | — | Near-random on hardest slice |
| Within empirical top-5 | 54.2% | — | — |
| Random baseline | 50.0% | — | — |

The 84.6% headline is real but misleading. It includes many easy comparisons
(e.g., pass vs bid-10-clubs). On the hard slices that matter most for bidding
decisions — distinguishing between competitive actions — accuracy drops to
~55%, barely above chance.

#### Top-K Accuracy

| K | Model | Random Baseline | Multiple |
|---|-------|-----------------|----------|
| 1 | 26.6% | 2.1% | 13x |
| 3 | 46.7% | 6.4% | 7x |
| 5 | 56.6% | 10.6% | 5x |
| 10 | 69.0% | 21.3% | 3x |

#### Regret Analysis

| Policy | Mean Regret | Median | Std |
|--------|-------------|--------|-----|
| Model | 4.015 | 2.0 | 4.594 |
| Always-pass | 4.784 | 4.0 | 4.366 |
| Random | 12.396 | 15.0 | 8.053 |

- Model vs random: **67.6% regret reduction**
- Model vs always-pass: **16.1% regret reduction**

#### Mean Outcome of Chosen Action

| Policy | Mean net_points |
|--------|-----------------|
| Model | +0.443 |
| Always-pass | -0.326 |
| Random | -7.938 |

#### Family-Level Ranking

| Family | Model Choice Rate | Oracle Choice Rate |
|--------|-------------------|--------------------|
| suit | 38.2% | 53.6% |
| high | 7.7% | 7.5% |
| low | 14.9% | 12.4% |
| pass | 39.2% | 26.5% |

Family-level top-1 agreement: **46.8%** (random baseline ~25%).

### Within-Family Prediction Quality

| Family | Correlation (pred, actual) | R^2 (test) |
|--------|---------------------------|------------|
| suit | 0.746 | 0.557 |
| high | 0.725 | 0.525 |
| low | 0.717 | 0.514 |
| pass | 0.210 | 0.044 |

## 4. Interpretation

### Gate Failure Root Cause: Oracle Noise

The single-rollout oracle is unreliable because:

1. **Bimodal outcomes:** Bid Euchre scoring creates a cliff between "made"
   (positive) and "set" (negative). For bid-7-suit, outcomes cluster at
   [-17, -10] and [+4, +11] with almost nothing between. A single rollout
   lands in one mode or the other based on continuation play.

2. **Massive ties:** 80.3% of states have gap = 0 between the oracle's 1st
   and 2nd best action. The oracle is picking arbitrarily among tied actions.

3. **Action space size:** With ~47 actions per state, the probability that the
   truly best action also wins the "luckiest single rollout" tournament is low.

A model-independent consistency check supports this: comparing the
single-rollout oracle against a population-mean oracle (average net_points
per (contract_family, bid_n) across the training set) shows only 37.4%
agreement. This confirms the single-rollout oracle is unstable but should
NOT be interpreted as a hard ceiling on achievable X3-rank, because the
population-mean oracle uses a coarser action definition and ignores
hand-specific context. A better state-aware model could exceed 37.4%.

### Model Behavioral Profile

The model clearly has signal: within-family R^2 of 0.51-0.56 (test set) and
84.6% pairwise accuracy (though inflated). However, it exhibits a
**conservative bias toward passing:**

- Passes in 39.2% of states vs oracle 26.5%
- Regret improvement over always-pass is only 16.1% vs 67.6% over random
- The pass model has the lowest R^2 (0.044), suggesting the model can't
  reliably predict when passing is costly vs acceptable

This over-passing likely stems from the **cross-model calibration problem:**
four independently trained OLS models have no shared scale. If the pass model
systematically over-predicts (or the bid models under-predict), the argmax
across families will favor pass even when bidding is better. This is exactly
the failure mode X3-cal was designed to detect — the calibration issue is
real, even though the metric itself is noisy.

### Honest Assessment of Pairwise Accuracy

The 84.6% pairwise accuracy is the most robust metric to oracle noise, but it
overstates model quality because:

- It includes many trivially easy comparisons (pass vs extreme bids)
- On hard slices (close pairs, top-action discrimination), accuracy drops to
  55% — barely above the 50% random baseline
- The per-family exact-match rates (suit 15.7%, high 6.7%, low 16.9%) confirm
  the model struggles to discriminate within families

The strongest support for the model comes from the **ensemble of weaker
signals:** top-k accuracy consistently above random, positive mean outcome
for model choices, and 67.6% regret reduction vs random. No single metric is
definitive, but taken together they indicate the model has learned structure
beyond noise.

## 5. Impact & Decisions

### Gate X3: Mis-Specified, Not Failed

The X3 thresholds assumed an oracle built from averaged rollouts per action.
With single-rollout labels, the thresholds are not calibrated to the
evaluation methodology. X3 should not block progression to gameplay screening.

### Specification Correction Needed

For future model iterations, X3 should be re-specified using one of:

1. **Repeated-rollout oracle (preferred):** K=10-20 rollouts per action,
   averaged. This creates a reliable oracle and makes the thresholds meaningful.
2. **Robust single-rollout metrics:** Pairwise accuracy, top-k, and regret
   vs baselines as the primary gates instead of exact top-1 agreement.
3. **Diagnostic subset:** Run K=10 rollouts on a few hundred states to
   calibrate what thresholds are achievable before setting gates.

### Risk Flags for Gameplay

- **Over-passing (39.2% vs 26.5%):** May cause the ActionValueBidder to
  underbid, losing contract opportunities to opponents.
- **Low pass model quality (R^2=0.044):** The model cannot distinguish good
  pass opportunities from poor ones.
- **Cross-model miscalibration:** Four independent OLS models have no shared
  prediction scale, leading to suboptimal cross-family comparisons.

### Next Step

Proceed to **Step 5: 3-seed gameplay screen**. Monitor:

- Pass rate (flag if >50% — spec threshold is 70% but over-passing risk
  warrants a tighter watch)
- Self-play win rate (must be in [40%, 60%])
- Self-play net_eppd (must be non-negative)

## 6. Arc Context

This is the first offline evaluation in the R1.5 rung. Prior steps:

- **Step 0 (PR #560):** Foundations — enumerate_legal_actions, ActionValueBidder
  skeleton, extract_state_features
- **Step 1 (PRs #564, #565):** Counterfactual dataset generator + engine
  alignment fixes
- **Step 2 (PR #567):** Training pipeline, Gate X2 passed

Next: Step 5 (3-seed gameplay screen), then Step 6 (H2H battery) if
catastrophic-behavior screen clears.

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | FAILED (X3-rank, X3-regret, X3-cal all below threshold; adjudicated non-blocking due to oracle specification mismatch — see §4) |
| Artifact | data/runs/action_value_quick_42/action_value_full.json |
| Dataset | data/runs/action_value_quick_42/datasets/action_value.parquet |
| Analysis script | scripts/internal/evaluate_gate_x3.py |
| analysis_base_sha | a20b177 (HEAD of main at time of analysis) |
| Seed | 42 |
| n_deals | 2,500 (QUICK) |
| Test split | 250 deals, 1,000 states, 47,344 rows |

## 8. Reproduction

```bash
# Generate QUICK dataset
uv run python scripts/internal/generate_action_value_dataset.py \
    --seed 42 --mode QUICK \
    --output-dir data/runs/action_value_quick_42/datasets

# Train models
uv run python scripts/internal/train_action_value.py \
    --seed 42 \
    --dataset data/runs/action_value_quick_42/datasets/action_value.parquet \
    --output-dir data/runs/action_value_quick_42 \
    --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

# Gate X3 offline evaluation
uv run python scripts/internal/evaluate_gate_x3.py \
    --seed 42 \
    --dataset data/runs/action_value_quick_42/datasets/action_value.parquet \
    --artifact data/runs/action_value_quick_42/action_value_full.json
```
