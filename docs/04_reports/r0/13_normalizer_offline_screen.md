# Normalizer Offline Screen — Track E Pre-Screen

> **Version:** v2 (PR #508) | New in v2

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-03
**Purpose:** Fast offline go/no-go screen for cross-contract utility normalizer

## Executive Summary

**Decision: NO_GO_DEFER_R1**

An offline screening pipeline evaluated whether an affine normalizer could improve
R0's cross-contract bid selection. The normalizer was triggered by nb55 v2 oracle
analysis finding 90.9% of regret attributable to contract selection (threshold: 25%).

The screen fit a 6-parameter affine transform (alpha, beta per contract family) via
softmax NLL on 191,552 hands (50,000 deals, seed=42, 60/40 deal-grouped split).

| Metric | Baseline | Normalized | Delta |
|--------|----------|------------|-------|
| `accuracy` | 33.3% | 37.3% | +4.0% |
| `net_eppd` | 2.036 | 1.767 | **-0.269** |
| 95% CI (delta) | | | [-0.287, -0.251] |
| Bid rate | 95.8% | 97.1% | +1.3pp |
| Make rate | — | 99.9% | — |
| Guardrails | — | FAIL | bid_rate > 0.95 |

**Key finding:** The normalizer correctly identifies that HIGH and LOW contracts are
undervalued relative to suit contracts — accuracy improves by 4 percentage points.
However, net_eppd **drops** by 0.269 points because R0's 1-feature HIGH/LOW models
cannot distinguish good from bad high/low hands. The normalizer redirects hands
toward contracts the model lacks the features to evaluate well, converting baseline
suit-contract profits into high/low-contract losses.

**This is model poverty, not miscalibration.** A normalizer cannot fix the underlying
problem: R0's HIGH model uses only `offsuit_aces` and LOW uses only
`offsuit_tens_count` — one feature each versus three for suit. Richer features
(R1+) are the prerequisite for meaningful cross-contract calibration.

## 1. Motivation

The contract selection oracle analysis (nb55 v2, PR #497) decomposed total regret
into three components:

| Component | Share |
|-----------|-------|
| Contract selection | 90.9% |
| Pass threshold | 5.3% |
| Over-bidding (bid level) | 3.7% |

At 90.9% share, the contract-selection regret exceeded the protocol's 25% trigger
threshold, activating Track E (normalizer evaluation). However, a high CS regret
share alone does not confirm that a normalizer will help — the regret could stem
from miscalibrated cross-contract utilities (normalizer-fixable) or from poor
within-contract predictions (model-quality issue, not normalizer-fixable).

This offline screen distinguishes between these two failure modes before committing
to full A/B integration.

**Protocol:** plans/r0_v2_normalizer_protocol.md (pre-registered)
**Spec:** plans/r0_v2_normalizer_screen_spec.md

## 2. Methodology

### Data

- **Source:** canonical_bidless_dataset_glutton_42_20260221_175752
- **Size:** 50,000 deals x 4 seats x 6 contracts = 1,200,000 rows
- **Complete hands:** 191,552 (after filtering incomplete deal/seat groups)
- **Split:** 60/40 by deal_id hash (seed=42). Train: 111,248. Val: 80,304

### Normalizer Design

Affine transform per contract family (3 families: suit, high, low):

```
u_norm[ct] = alpha[family] * u_raw[ct] + beta[family]
```

6 parameters total. The 4 suit contracts (C, D, H, S) share one (alpha, beta) pair.

### Fitting

- **Objective:** Softmax negative log-likelihood of oracle contract
- **Optimizer:** L-BFGS-B
- **Bounds:** alpha in [0.5, 2.0], beta in [-5.0, 5.0]
- **Regularization:** L2 toward identity (alpha=1, beta=0), weight 1e-3
- **Oracle:** argmax actual_net across all 6 contracts per hand

### Evaluation

- **Primary metric:** delta_net_eppd (normalized minus baseline mean actual_net)
- **Uncertainty:** 95% CI via deal-grouped bootstrap (10,000 resamples, seed=42)
- **Secondary:** accuracy lift, bid rate shift, make rate, guardrails

### Contract Selection

- **Baseline model:** argmax utility where utility > 0 (tie-break: higher bid_n, then contract_key)
- **Normalized model:** same argmax logic applied to normalized utilities

## 3. Results

### 3.1 Diagnostic Zero

Before fitting, we analyzed the utility gap on disagreement hands (where model
and oracle select different contracts):

| Metric | Value |
|--------|-------|
| Total bidding hands | 191,552 |
| Disagreement hands | 124,972 (65.2%) |
| Utility gap p25 | 0.744 |
| Utility gap p50 | 1.545 |
| Utility gap p75 | 2.666 |
| Utility gap p90 | 3.650 |
| Early exit triggered | No |

The gap distribution approaches but does not cross the early-exit thresholds
(median > 2.0 AND p75 > 3.0). The high disagreement rate (65.2%) and elevated
p75/p90 gaps signal that the model is confidently wrong on many hands, a pattern
more consistent with model poverty than with miscalibration.

### 3.2 Fitted Parameters

| Parameter | High | Low | Suit |
|-----------|------|-----|------|
| alpha | **0.500** (lower bound) | **0.500** (lower bound) | **0.500** (lower bound) |
| beta | +0.289 | +0.247 | -0.535 |

All three alpha values hit the lower bound (0.5), indicating the optimizer wants to
**shrink all raw utilities toward zero** rather than selectively rescale across families.
The betas apply small family-specific offsets: boost high (+0.29) and low (+0.25),
suppress suit (-0.54). This is a compression + reranking strategy, not a targeted
calibration.

Train loss decreased from identity (confirming optimizer progress):

| Metric | Value |
|--------|-------|
| Final loss (NLL + reg) | 1.552 |
| Train accuracy baseline | 33.3% |
| Train accuracy normalized | 37.8% |

### 3.3 Validation Results

| Metric | Baseline | Normalized | Delta | Status |
|--------|----------|------------|-------|--------|
| `accuracy` | 33.27% | 37.31% | +4.04% | Positive |
| `net_eppd` | 2.036 | 1.767 | -0.269 | **Negative** |
| 95% CI (delta) | — | — | [-0.287, -0.251] | Excludes 0 (wrong direction) |
| Bid rate | 95.77% | 97.07% | +1.30pp | — |
| New bidders (pass to bid) | — | 2,560 | — | — |
| Lost bidders (bid to pass) | — | 1,518 | — | — |
| Make rate (normalized) | — | 99.92% | — | Healthy |
| Guardrails | — | FAIL | — | bid_rate > 0.95 cap |

The paradox — accuracy up, net_eppd down — reveals the normalizer's failure mode.
Matching the oracle's contract choice more often does not translate to better outcomes
because the model's utility predictions within high/low contracts are unreliable.

### 3.4 Pass-Decision Shift

The normalizer converts 2,560 hands from pass to bid and 1,518 from bid to pass,
net +1,042 additional bidding hands. The resulting 97.1% bid rate exceeds the
protocol's 0.95 cap guardrail. The extremely high make rate (99.9%) suggests the
normalizer is not causing reckless overbidding — it is selectively enabling bids
on high-confidence hands — but the bid rate itself is above the safety threshold.

## 4. Interpretation

### Why Accuracy Improves but Net EPPD Drops

The normalizer's beta values tell the story: it boosts high (+0.29) and low (+0.25)
while suppressing suit (-0.54). This correctly identifies that the baseline model
undervalues high/low contracts relative to suit — the oracle does indeed select
high/low more often than the baseline model.

However, the model's predictions for high/low contracts are based on a single feature
each (`offsuit_aces` for HIGH, `offsuit_tens_count` for LOW). When the normalizer redirects a hand from suit to high,
the model's confidence in the suit prediction was based on 3 features (bowers,
trump_count, offsuit_aces), while the high prediction is based on
just 1 feature. The redirect sacrifices information-rich predictions for
information-poor ones.

### Model Poverty Diagnosis

Three signals converge on the model-poverty diagnosis:

1. **All alphas at lower bound:** The optimizer wants to shrink utilities below 0.5x,
   not selectively recalibrate. This means raw utility magnitudes are unreliable
   across all families.
2. **High disagreement rate (65.2%):** The model and oracle disagree on nearly
   two-thirds of hands — far beyond what miscalibration alone would explain.
3. **Accuracy-net_eppd divergence:** Better oracle matching produces worse outcomes,
   indicating the oracle's choices depend on information the model does not have.

### Overestimate Caveat

The offline replay uses counterfactual outcomes (all 6 contracts simulated per hand).
In a real A/B, the normalizer's effect would be smaller because defending strategy
adapts to the declared contract. The protocol expects 50-75% of offline estimates in
practice. Since the offline estimate is already negative, the real-world effect would
be even worse.

## 5. Impact & Decisions

### Go/No-Go Gate

**NO_GO criteria** (any one triggers NO_GO):

| Criterion | Threshold | Result | Triggered? |
|-----------|-----------|--------|------------|
| delta_net_eppd <= 0 | Must be > 0 | -0.269 | **Yes** |
| CI upper bound < +0.03 | Must be >= +0.03 | -0.251 | **Yes** |
| accuracy_lift < 0.02 | Must be >= 0.02 | +0.040 | No |

**GO criteria** (all required for GO -- not evaluated since NO_GO triggered):

| Criterion | Threshold | Result | Met? |
|-----------|-----------|--------|------|
| delta_net_eppd >= +0.08 | >= +0.08 | -0.269 | No |
| CI excludes 0 (positive) | ci_low > 0 | -0.287 | No |
| Guardrails pass | All pass | FAIL | No |
| accuracy_lift >= 0.03 | >= 0.03 | +0.040 | Yes |

**Two NO_GO criteria triggered:** delta <= 0 and ci_high < +0.03. Decision:
**NO_GO_DEFER_R1**.

### What This Means for R0

- No normalizer will be integrated into the R0 canonical freeze
- The model artifact (hybrid_r0.json) remains unchanged
- No recascade of batteries or notebooks is needed
- The normalizer finding is documented but does not block promotion

### What This Means for R1

The normalizer screen provides a clear signal for R1 feature engineering priorities:

1. **HIGH/LOW features are the bottleneck.** The 1-feature models for high and low
   contracts are the primary source of contract-selection regret.
2. **Cross-contract calibration has ceiling potential.** The +4% accuracy lift shows
   the normalizer correctly identifies the direction of miscalibration. With better
   underlying predictions, this signal could translate to net_eppd improvement.
3. **Normalizer retry at R1** should be conditional on HIGH/LOW model improvement
   (at least 3 features per family, with R-squared > 0.15 on held-out data).

## 6. Arc Context

This screen is part of the R0 Canonical v2 execution plan (Phase 1b). It sits
between the lambda freeze decision (Phase 0, RETAIN lambda=0.0) and the full
report regeneration cycle (Phase 3).

**Predecessor:** nb55 v2 oracle analysis (CS regret = 90.9%, normalizer triggered)
**This report:** Offline screen confirms deferral
**Successor:** Report suite regeneration (11 existing + 2 new reports)

The full Track E protocol (A/B integration, comparator evaluation, H2H confirmation)
is skipped. If R1 improves HIGH/LOW model quality, Track E re-evaluation should use
the same offline screen as a first gate before committing to full integration.

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A (pre-screen, not a formal gate) |
| Artifact path | data/artifacts/arc_d/r0/normalizer_offline_screen_v1.json |
| Schema | normalizer_offline_screen_v1 |
| Script | scripts/internal/run_normalizer_offline_screen.py |
| Git SHA | d33011f (PR #507) |
| Seed | 42 |
| n_deals | 50,000 |
| n_hands | 191,552 (bidding hands in validation split: 80,304) |
| n_bootstrap | 10,000 |
| pass_threshold | 0.0 |
| risk_lambda | 0.0 |
| Data source | canonical_bidless_dataset_glutton_42_20260221_175752 |

## 8. Reproduction

```bash
uv run python scripts/internal/run_normalizer_offline_screen.py \
  --bidless-path data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless.parquet \
  --outcomes-path data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless_outcomes.parquet \
  --artifact-path data/artifacts/arc_d/r0/hybrid_r0.json \
  --seed 42 --pass-threshold 0.0 --risk-lambda 0.0 --n-bootstrap 10000 \
  --output data/artifacts/arc_d/r0/normalizer_offline_screen_v1.json
```
