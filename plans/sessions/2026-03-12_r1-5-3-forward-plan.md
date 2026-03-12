# R1.5.3 Forward Plan: GBT Validation + Two-Stage Experiment

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Prerequisite:** GBT prototype VALIDATED (PR #614, report PR #618)
**Governing doc:** `plans/r1_5_forward_decision_tree.md`

## Goal

Determine the best model architecture for the action-value bidder that:
1. Resolves the R1.5 suit regression (-0.142 net_eppd vs R0 Hybrid)
2. Clears the promotion threshold (CI_low > 0.180)
3. Preserves interpretability where possible
4. Maintains acceptable tail risk

## Current State

Track B (GBT) prototype results (QUICK, 2,500 deals, seed=42):

| Comparison | Pooled | Suit | High | Low |
|------------|--------|------|------|-----|
| GBT vs OLS AV | +1.112 [+0.986, +1.244] | +1.190 | +1.112 | +0.931 |
| GBT vs Hybrid R0 | +1.067 [+0.951, +1.188] | +1.110 | +1.467 | +0.736 |
| OLS AV vs Hybrid R0 | +0.165 [+0.080, +0.249] | -0.136 | +0.454 | +0.519 |

Key behavioral findings:
- GBT passes 31.9% of auction actions (vs OLS 0%, Hybrid 5.7%)
- GBT avg_bid = 5.44 (vs OLS 4.00, Hybrid 3.77)
- GBT make_rate = 87.1% (vs OLS 94.6%, Hybrid 96.6%)
- GBT CVaR_5 = -6.63 (vs OLS -1.80, Hybrid -0.71)

Open hypotheses:
- **H12:** Bimodal make/set target causes suit regression via between-mode OLS
  prediction. OPEN (leading theory, untested interventionally).
- **H13:** AV v1's always-bid-4 behavior leaves value on the table. ANSWERED
  by GBT prototype (yes — selective bidding + higher bids = +1.1 net_eppd).

## Plan Overview

Four phases, executed sequentially with gates:

```
Phase 1: GBT FULL Validation (50k deals, 3 seeds)
  │
  ├── PASS → Phase 3 (GBT is a viable candidate)
  └── FAIL → Re-evaluate (QUICK result was noise)

Phase 2: Two-Stage Make/Set Experiment (H12 interventional test)
  │
  ├── PASS → Phase 3 (two-stage is a viable candidate)
  └── FAIL → H12 refuted; GBT is the only path forward

Phase 3: Comparative Decision
  │
  Compare GBT vs two-stage (if both pass) or promote winner
  │
  └── Promotion gate or next rung

Phase 4: Artifact Governance (infrastructure, parallel)
  │
  Validation gates + lightweight registry
```

---

## Phase 1: GBT FULL Validation

**Objective:** Confirm QUICK results at FULL scale with multi-seed validation.

**Why this is first:** The QUICK results (+1.1 net_eppd) are below the 2,000-deal
per-contract-facet rigor threshold. The GBT prototype used default sklearn
hyperparameters and a single seed. Before investing in alternatives, confirm the
baseline result is real.

### Step 1.1: GBT Hyperparameter Tuning (Optional Pre-Step)

Before running FULL, consider whether default hyperparameters are leaving
performance on the table (or overstating it).

**Approach:** Grid search on QUICK data with cross-validated suit R²:
- `n_estimators`: [100, 200, 500]
- `max_depth`: [3, 5, 7]
- `learning_rate`: [0.05, 0.1, 0.2]
- `min_samples_leaf`: [10, 50, 100]

**Gate:** If tuned R² differs from default by > 0.02 on any contract, retrain
with tuned hyperparameters before FULL. Otherwise proceed with defaults.

**Skip criterion:** If time pressure exists, skip tuning and proceed with
defaults. The QUICK prototype already shows massive gameplay gains; tuning is
optimization, not validation.

### Step 1.2: FULL H2H Battery

**Config:** Same 3-bidder roster (GBT AV, OLS AV v1, Hybrid R0), 50,000 deals
per matchup, paired deals, 9 matchups.

**Seeds:** 42, 123, 456 (3-seed protocol, matching R1.5 v1 precedent).

**Success gates:**
- Pooled GBT vs Hybrid: CI_low > 0.180 (promotion threshold)
- GBT vs OLS AV: CI excludes zero
- Suit GBT vs Hybrid: delta > 0 (suit regression resolved)
- Self-play sanity: net_eppd within [-0.1, +0.1] for all 3 bidders
- Multi-seed stability: deltas consistent across seeds (no seed-dependent reversals)

**Failure gates:**
- Pooled delta shrinks below +0.5 (QUICK→FULL shrinkage > 50%)
- Suit regression reappears (suit delta < 0 at FULL)
- Any seed shows reversal (GBT loses to Hybrid on any seed)

**Tail risk assessment:** Compute CVaR_5, CVaR_10, scoring std, and min-score
distribution at FULL scale. Flag if CVaR_5 < -8.0 (indicating systematic
overbidding pathology).

### Step 1.3: Report

Write FULL battery report following 8-section template. Include:
- Multi-seed stability analysis
- Contract-faceted results with per-seed breakdown
- Tail risk comparison (CVaR_5 confidence intervals)
- Behavioral profile comparison at FULL scale

**Deliverable:** 1 PR (experiment + report)

---

## Phase 2: Two-Stage Make/Set Experiment

**Objective:** Test H12 interventionally by building a suit-only two-stage
model and evaluating whether it matches GBT's suit improvement while preserving
interpretability.

**Why test this even though GBT works:** GBT resolves the suit regression but
sacrifices interpretability and has higher tail risk. If a simpler, interpretable
model achieves similar gains, it's preferable. Additionally, testing H12 has
scientific value — we need to know whether bimodal make/set averaging is the
actual mechanism, regardless of the practical model choice.

### Hypothesis

**H12 (interventional test):** A two-stage suit model that predicts P(make)
and regime-conditional payoffs will improve suit decision quality without
sacrificing interpretability.

Model:
```
E[net_points | state, action] =
    P(make | state, action) × E[net_points | make, state, action]
  + P(set  | state, action) × E[net_points | set,  state, action]
```

This is different from the already-tested declare/defend split (H11, WEAKENED).
The new experiment decomposes the **declaring** regime on the make/set axis.

### Step 2.1: Data Preparation

Use the existing counterfactual dataset. For each suit action row:
- Label `made_bid` (binary) from the rollout outcome
- Compute `net_points_if_made` and `net_points_if_set` from the scoring rules
  (these are deterministic given t0/t1 and bid level)
- Keep high/low/pass models unchanged (OLS AV v1)
- **Scope:** Train only on rows where the focal team declares the suit contract.
  This isolates the suspected cliff instead of mixing in defend rows that have
  weak hand-signal.

**Sanity checks:**
- Verify make rate by bid level (should decrease with higher bids)
- Verify net_points_if_made > net_points_if_set (by definition)
- Check sample sizes per bid level × make/set (flag if n < 100)

### Step 2.1b: Offline Baselines

Build three suit-only offline baselines on the same train/test split to attribute
gains to regime decomposition (not just extra machinery):

1. **Pooled OLS:** Current AV v1 suit model (single E[net_points] prediction)
2. **Constant-rate two-stage:** Global P(make) frequency + conditional means
   (no features, just make/set averages by bid level)
3. **Proposed two-stage:** Logistic P(make) + conditional OLS (Steps 2.2-2.4)

Compare all three on the same offline metrics (regret, top-1 accuracy, R²).
If the constant-rate baseline matches the proposed model, regime decomposition
alone explains the gain. If the proposed model beats both, the learned P(make)
adds value beyond simple regime splitting.

### Step 2.2: Stage 1 — P(make) Classifier

**Model:** Logistic regression on suit features + bid_n + bid_n_sq.

**Metrics:**
- AUC (must exceed 0.70)
- Brier score (must beat naive frequency baseline)
- Calibration by bid level (slope should be sane)
- Calibration in boundary region P(make) ∈ [0.3, 0.7]

**Gate:** AUC < 0.70 → STOP (hand features can't predict make/set).

### Step 2.3: Stage 2 — Conditional Payoff Models

**Models:** Two OLS regressions on suit declaring rows:
- E[net_points | make, state, action] (trained on made_bid=True rows)
- E[net_points | set, state, action] (trained on made_bid=False rows)

**Metrics:**
- R², MAE for each
- Coefficient stability (no explosion at high bid levels)
- Residual spread by bid level

**Gate:** Both models numerically stable, no coefficient explosion.

### Step 2.4: Composite Predictor

Assemble the two-stage predictor for suit actions only:
```python
p_make = logistic_model.predict_proba(state_action)[:, 1]
ev_make = ols_make.predict(state_action)
ev_set = ols_set.predict(state_action)
ev_combined = p_make * ev_make + (1 - p_make) * ev_set
```

Keep high/low/pass as standard OLS AV v1.

### Step 2.5: Offline Evaluation

Compare on held-out suit states:
- Oracle regret (vs observed best action)
- Bid-level choice accuracy
- Family+bid ranking against observed best action

**Primary offline gate:**
- Suit regret improves by ≥ 0.25 net_points vs OLS AV v1
- OR suit top-1 accuracy improves by ≥ 5 percentage points

### Step 2.6: Behavioral Screen

Self-play or sampled auction screen before H2H:
- avg_bid, bid histogram, bid_10_rate
- make rate, suit contract share, pass rate

**Gate:**
- avg_bid < 7.0 (no saturation)
- make_rate > 70% (no collapse)
- bid_10_rate < 5% (no degeneracy)

### Step 2.7: QUICK H2H

3-bidder comparison:
- two_stage_suit + AV_v1_high_low_pass
- OLS AV v1
- Hybrid R0

2,500 deals, seed=42, paired deals.

**Success gates:**
- Suit delta vs Hybrid R0: > -0.092 (improve from -0.142 by at least 0.05)
- Pooled delta vs Hybrid R0: not regressed by > 0.03 from AV v1's +0.165

**Report:** Comparison with GBT QUICK results. Does two-stage match GBT's
+1.1 net_eppd advantage? Or does it fall short?

### Step 2.7b: Calibration Diagnostics

Generate side-by-side diagnostic comparisons (the interpretability payoff):

1. **P(make) calibration:** Predicted vs actual make rate by bid level and
   by predicted probability decile. Shows whether the logistic model is
   well-calibrated where decisions are made.
2. **Predicted vs actual net_points:** Pooled OLS vs two-stage scatter plots.
   Two-stage should show tighter residuals if regime decomposition helps.
3. **Residuals split by make/set:** For each model, plot residual distributions
   conditioned on make/set outcome. Pooled OLS should show bimodal residuals
   that the two-stage model resolves.
4. **Decision boundary visualization:** Heatmap of which bid levels the
   two-stage model selects vs pooled OLS, keyed by hand_value or quick_tricks.

These diagnostics are informational (no gate), but they explain *why* the
two-stage model improves (or doesn't). If the approach works, these plots
should make the mechanism visually obvious.

### Step 2.8: Decision

| Two-Stage Result | GBT Result | Action |
|-----------------|------------|--------|
| Matches GBT (~+1.0 net_eppd) | FULL confirmed | **Prefer two-stage** (interpretable, lower risk) |
| Moderate improvement (+0.3–0.8) | FULL confirmed | Run two-stage at FULL; compare tail risk |
| Fails (< +0.3 or suit still negative) | FULL confirmed | **Go with GBT**; H12 refuted as intervention |
| Any result | FULL fails | Re-evaluate both; possible data/label problem |

**Deliverable:** 2-3 PRs (data prep + training pipeline, evaluation + report)

---

## Phase 3: Comparative Decision

**Triggered by:** Phase 1 and Phase 2 complete.

### Decision Framework

| Criterion | GBT | Two-Stage | Weight |
|-----------|-----|-----------|--------|
| Pooled net_eppd vs R0 | Known: ~+1.1 QUICK | TBD | High |
| Suit delta vs R0 | Known: ~+1.1 QUICK | TBD | High |
| Interpretability | Low (feature importances only) | High (coefficients + P(make) curve) | Medium |
| Tail risk (CVaR_5) | Known: -6.63 | TBD | Medium |
| Implementation complexity | Simple (drop-in) | Moderate (3 models + assembly) | Low |
| Pass behavior | 31.9% pass rate (emergent) | TBD | Informational |

### Promotion Criteria

To be PROMOTED over R0 Hybrid:
- Pooled delta CI_low > 0.180 (existing threshold)
- Suit delta > 0 (regression resolved)
- No catastrophic tail risk (CVaR_5 > -10.0)
- Multi-seed stability (3 seeds, no reversals)

If two candidates both pass, prefer:
1. Interpretability (two-stage > GBT, all else equal)
2. Lower tail risk (CVaR_5 closer to R0's -0.71)
3. Higher pooled delta (tiebreaker)

---

## Phase 4: Artifact Governance (Parallel)

**Objective:** Prevent future stale-artifact reuse. Lightweight approach.

### What Happened

The initial GBT H2H used a stale OLS artifact (R²=0.18, always bids 10) instead
of the correct Step 6 baseline (R²=0.565, bids at level 4). This produced an
invalid comparison that was caught only by manual inspection of avg_bid = 10.0.

### Root Cause

No validation gate between "trained" and "used in experiment." Artifacts are
referenced by file path, and nothing prevents referencing a wrong/stale artifact.

### Minimal Fixes (1 PR)

1. **Post-train behavioral screen:** Add `validate_action_value_artifact.py`
   that runs a deterministic 50-deal self-play after training and checks:
   - avg_bid < 7.0
   - bid_10_rate < 5%
   - make_rate > 50%
   - pass_rate > 0% OR explicit override flag
   - Fail loudly if any threshold violated

2. **Artifact quarantine:** Move known-bad artifacts to a `quarantined/`
   subdirectory or add `"status": "quarantined"` to their JSON metadata.
   Update artifact loading to reject quarantined artifacts.

3. **Config-level artifact validation:** When loading an AV artifact in
   `ActionValueBidder.__init__`, log a warning if R² < 0.30 on any bid
   contract. This catches "wrong target" artifacts before gameplay.

### Deferred (Future)

- Full artifact registry with SHA-based resolution
- Status lifecycle (draft → blessed → superseded → quarantined)
- Config resolution through artifact_id instead of raw paths

These are valuable but over-engineered for a research repo at this stage.
The minimal fixes above would have caught the actual failure mode.

---

## Implementation Order

| Step | Phase | Est. PRs | Dependencies |
|------|-------|----------|-------------|
| 1 | Phase 4: Artifact governance | 1 | None — can start immediately |
| 2 | Phase 1.1: GBT tuning (optional) | 0-1 | Phase 4 |
| 3 | Phase 1.2: GBT FULL H2H | 1 | Phase 1.1 or skip |
| 4 | Phase 2.1-2.4: Two-stage build | 1-2 | Counterfactual dataset exists |
| 5 | Phase 2.5-2.7: Two-stage eval | 1 | Phase 2.1-2.4 |
| 6 | Phase 3: Decision | 1 (report) | Phase 1 + Phase 2 |

**Total estimated PRs:** 4-6

**Parallelism:** Phase 2 (two-stage) can begin while Phase 1 (GBT FULL) runs,
since they use the same dataset and don't share infrastructure.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| GBT QUICK→FULL shrinkage > 50% | Low | High | 3-seed protocol catches instability |
| Two-stage P(make) AUC < 0.70 | Medium | Low | Expected if suit make/set is truly unpredictable from hand features; validates H12 refutation |
| GBT tail risk unacceptable (CVaR_5 < -10) | Medium | Medium | Cap bid level at 8 or add risk-aware argmax as variant |
| Both approaches fail at FULL | Very Low | High | Hybrid routing (AV for high/low, R0 for suit) as fallback |
| New stale-artifact incident | Medium (pre-Phase 4) | Medium | Phase 4 first to prevent recurrence |

## Outcome

_To be filled after implementation._

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — plan document |
| GBT prototype PR | #614 |
| GBT report PR | #618 |
| Governing decision tree | plans/r1_5_forward_decision_tree.md |
| Key hypothesis | H12 (bimodal make/set target, OPEN) |
