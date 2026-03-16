# R1.5.3 Forward Plan v2: Label Quality + Model Architecture

**Date:** 2026-03-12
**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Supersedes:** `plans/sessions/2026-03-12_r1-5-3-forward-plan.md` (PR #618)
**Governing doc:** `plans/r1_5_forward_decision_tree.md`
**Discussion log:** `plans/sessions/2026-03-11_model-alternatives-discussion.md` (PR #622)

## Goal

Determine the best combination of **model architecture** and **label quality**
for the action-value bidder that:
1. Resolves the R1.5 suit regression (-0.142 net_eppd vs R0 Hybrid)
2. Clears the promotion threshold (CI_low > 0.180)
3. Preserves interpretability and attribution where possible
4. Maintains acceptable tail risk

## What Changed (v1 → v2)

v1 explored model architecture only (GBT vs two-stage). PR #622's discussion
log identified a potentially orthogonal improvement: **label quality**. Current
training uses single deterministic rollouts per action. Imperfect-information
rollouts (averaging over opponent hand configurations) could smooth the bimodal
suit labels and potentially restore OLS viability.

**Key correction:** The discussion log's multi-rollout proposal assumed that
looping `simulate_counterfactual()` N times would produce different outcomes.
It would not — the simulation is fully deterministic (no randomness in
continuation policy or play policy). Meaningful label smoothing requires
**opponent hand resampling**: hold the focal player's hand AND partner's hand
fixed, deal new opponent hands from the remaining 20 cards, simulate each
configuration. Partner hand must stay fixed because partner context features
(`partner_bid_confidence`, `partner_suit_match`, `partner_high_card_signal`)
describe the partner's actual hand/bidding — resampling the partner would
create features↔labels misalignment (features describe partner X, labels
reflect outcomes with partner Y). This is architecturally different from
"add a loop" and requires ~50-100 lines of new code + tests.

## Hypothesis Ledger

| ID | Hypothesis | Status | Tested By |
|----|-----------|--------|-----------|
| H12 | Bimodal make/set target causes suit regression via between-mode OLS prediction | OPEN | Phase 0 (label smoothing) and Phase 1B (two-stage, conditional) |
| H13 | AV v1's always-bid-4 behavior leaves value on the table | ANSWERED (yes) | GBT prototype (PR #614) |
| H14 | Imperfect-info label averaging improves OLS suit fit | NEW | Phase 0 diagnostic |

## Current State

Track B (GBT) prototype results (QUICK, 2,500 deals, seed=42):

| Comparison | Pooled | Suit | High | Low |
|------------|--------|------|------|-----|
| GBT vs OLS AV | +1.112 [+0.986, +1.244] | +1.190 | +1.112 | +0.931 |
| GBT vs Hybrid R0 | +1.067 [+0.951, +1.188] | +1.110 | +1.467 | +0.736 |
| OLS AV vs Hybrid R0 | +0.165 [+0.080, +0.249] | -0.136 | +0.454 | +0.519 |

## Plan Overview

Five phases. Phase 0 is new (cheapest, most informative). The remaining phases
branch based on Phase 0 results.

```
Phase 0: Imperfect-Info Label Diagnostic (NEW — cheap, high info value)
  │
  ├── H14 CONFIRMED (OLS suit R² improves > 0.03)
  │   └── Phase 1A: Multi-Rollout QUICK + 2×2 Model×Label Matrix
  │       └── Phase 2: FULL Validation of winner
  │
  └── H14 REFUTED (OLS suit R² flat)
      └── Phase 1B: GBT FULL Validation (original Phase 1)
          │
          ├── PASS → Phase 2: Promotion decision
          └── FAIL → Phase 1C: Two-Stage as last resort

Phase 3: Decision Report (after any Phase 2)

Phase 4: Artifact Governance — DONE (PR #621)
```

---

## Phase 0: Imperfect-Information Label Diagnostic

**Objective:** Test whether smoothing training labels via opponent hand
resampling improves OLS suit R². This is the cheapest experiment with the
highest information value — it could make the model-class question moot.

**Why this is first:** At SMOKE scale (~3 min), this answers whether the suit
regression is fundamentally a label-quality problem or a model-capacity problem.
If label quality, OLS may be sufficient and the rung ladder is preserved.
If not, we know to invest in GBT FULL validation without further detours.

### Step 0.1: Implementation (1 PR)

Add imperfect-information rollout capability to the dataset generator:

**Changes to `generate_action_value_dataset.py`:**
- Add `--n-opponent-samples N` parameter (default 1 = current behavior)
- For each (deal, focal_seat, action), when N > 1:
  - Hold focal player's hand AND partner's hand fixed (preserves partner
    context feature alignment — partner features describe the partner's
    actual hand/bidding, so the partner must stay fixed or features↔labels
    become misaligned)
  - Sample N opponent hand configurations from the remaining 20 cards
    (40 total - 10 focal - 10 partner = 20 opponent cards)
  - Run `simulate_counterfactual()` for each configuration
  - Record `mean(net_points)` and `mean(tricks_won)` as the label
  - Also record `std(net_points)` and `n_samples` as metadata columns
- Seed the opponent hand sampler deterministically: `rng = Random(seed + deal_id * 10000 + focal_seat)`

**New function:** `sample_opponent_hands(focal_hand, partner_hand, remaining_cards, n_samples, rng)`
- Deals the remaining 20 cards (opponents only) into 2 hands of 10
- Returns list of (opp1_hand, opp2_hand) tuples
- Focal and partner hands are unchanged across all samples

**Tests:**
- Determinism: same seed → same opponent samples
- N=1 matches existing single-rollout behavior exactly
- Label averaging: std(net_points) > 0 for suit actions at N > 1
- Schema compatibility: output parquet has same columns + optional metadata

**Gate:** Implementation passes `make check`. N=1 output is byte-identical
to current generator output (backward compatibility).

### Step 0.2: SMOKE Diagnostic (same PR)

**Config:** 500 deals, N=20 opponent samples, seed=42

**Commands:**
```bash
# Single-rollout baseline (current behavior)
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 500 --n-opponent-samples 1 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_label_diagnostic_1x_42

uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class ols \
  --dataset data/runs/av_label_diagnostic_1x_42/datasets/action_value.parquet \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_label_diagnostic_1x_42

# Multi-sample labels
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 500 --n-opponent-samples 20 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_label_diagnostic_20x_42

uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class ols \
  --dataset data/runs/av_label_diagnostic_20x_42/datasets/action_value.parquet \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_label_diagnostic_20x_42

# Also train GBT on multi-sample for comparison
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class gbt \
  --dataset data/runs/av_label_diagnostic_20x_42/datasets/action_value.parquet \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_label_diagnostic_20x_42
```

**Metrics:**
- Label distribution: histogram of suit net_points for N=1 vs N=20
  (N=1 should be bimodal; N=20 should show smoothing toward unimodal)
- OLS R² per contract family at N=1 vs N=20
  (baseline: suit=0.557, high=0.533, low=0.514, pass=0.046)
- GBT R² at N=20 (comparison point)
- Label variance: mean(std_net_points) by contract family
  (suit should have highest variance reflecting make/set split)

**Gate criteria:**
- **H14 CONFIRMED:** OLS suit R² improves by > 0.03 (from 0.557 to > 0.587)
  → Proceed to Phase 1A
- **H14 REFUTED:** OLS suit R² change < 0.03
  → Proceed to Phase 1B (GBT FULL)
- **INFORMATIONAL:** If pass R² rises substantially from 0.046, this
  confirms single-rollout noise was a bottleneck there too

### Step 0.3: Sample Count Sweep (same PR, parallel with 0.2)

**Goal:** Find the cost/benefit curve for opponent sample count.

**Config:** 500 deals, N ∈ {1, 5, 20}, seed=42. Train OLS on each.

**Deliverable:** R² vs N plot per contract family. Identify the "knee" where
additional samples have diminishing returns. This informs FULL-scale cost.

**Cost:** (1+5+20) × 500 = ~13K simulation-equivalents. ~5 min.

### Step 0.4: Report

Write diagnostic report following 8-section template:
`docs/04_reports/arc_d_v1/r1_5/09_multi_rollout_diagnostic.md`

Must include:
- Label distribution comparison (N=1 vs N=20 histograms)
- R² comparison table (per contract, per N)
- R² vs N curve (from sweep)
- H14 verdict with evidence
- Next-phase recommendation

**Report traceability:** References `08_gbt_prototype_evaluation.md` for
GBT baseline numbers. Updates hypothesis ledger (H14 status).

**Deliverable:** 1 PR (implementation + diagnostic + report)

---

## Phase 1A: Multi-Rollout QUICK + 2×2 Model×Label Matrix

**Triggered by:** Phase 0 gate PASS (H14 confirmed — label smoothing helps OLS).

**Objective:** Measure the gameplay impact of label quality vs model capacity
at QUICK scale. The 2×2 {OLS, GBT} × {1-sample, 20-sample} comparison
decomposes which lever matters more.

### Step 1A.1: QUICK Dataset Generation

Generate two QUICK datasets (2,500 deals each, seed=42):
- N=1 (already exists from R1.5 Step 1)
- N=20 (new)

### Step 1A.2: Train 4 Models

| Cell | Model | Labels | Artifact |
|------|-------|--------|----------|
| A | OLS | 1-sample | Existing (action_value_full.json) |
| B | OLS | 20-sample | New |
| C | GBT | 1-sample | Existing (action_value_gbt.json) |
| D | GBT | 20-sample | New |

### Step 1A.3: H2H Battery

5-bidder roster: Cells A-D + Hybrid R0 (incumbent).
25 pairwise matchups, 2,500 deals, seed=42.

**Key comparisons:**
- B vs A: multi-rollout OLS improvement over single-rollout OLS (label effect)
- C vs A: GBT improvement over OLS on same labels (model effect)
- D vs C: multi-rollout improvement on GBT (label effect on better model)
- B vs C: does multi-rollout OLS match or beat single-rollout GBT?
  (THE critical question — if yes, labels > model capacity)

**Success gates:**
- Best candidate pooled delta vs R0 CI_low > 0 (statistically positive)
- Best candidate suit delta vs R0 > -0.092 (improvement from -0.142)
- At least one candidate's suit delta > 0 (suit regression resolved)

### Step 1A.4: Report

`docs/04_reports/arc_d_v1/r1_5/10_model_label_matrix.md`

Must include:
- 2×2 effect decomposition table (label effect, model effect, interaction)
- Per-contract faceted results for all 4 cells
- Behavioral profiles (avg_bid, make_rate, pass_rate per cell)
- Tail risk comparison (CVaR_5 per cell)
- Winner identification + rationale

**Report traceability:** References `09_multi_rollout_diagnostic.md` for R²
findings and `08_gbt_prototype_evaluation.md` for GBT baseline.

**Deliverable:** 1 PR (datasets + training + H2H + report)

→ Winner advances to Phase 2 (FULL validation).

---

## Phase 1B: GBT FULL Validation

**Triggered by:** Phase 0 gate FAIL (H14 refuted — label smoothing doesn't
help OLS, suit regression is model-capacity problem).

**Objective:** Confirm GBT QUICK results at FULL scale with multi-seed
validation. Identical to v1 Phase 1.

### Step 1B.1: FULL H2H Battery

**Config:** 3-bidder roster (GBT AV, OLS AV v1, Hybrid R0), 50,000 deals
per matchup, paired deals, 9 matchups.

**Seeds:** 42, 123, 456 (3-seed protocol).

**Success gates:**
- Pooled GBT vs Hybrid: CI_low > 0.180 (promotion threshold)
- GBT vs OLS AV: CI excludes zero
- Suit GBT vs Hybrid: delta > 0 (suit regression resolved)
- Self-play sanity: net_eppd within [-0.1, +0.1]
- Multi-seed stability: no seed-dependent reversals

**Failure gates:**
- Pooled delta shrinks below +0.5 (QUICK→FULL shrinkage > 50%)
- Suit regression reappears (suit delta < 0 at FULL)
- Any seed reversal

**Tail risk:** CVaR_5, CVaR_10 at FULL scale. Flag if CVaR_5 < -8.0.

### Step 1B.2: Report

`docs/04_reports/arc_d_v1/r1_5/10_gbt_full_validation.md`

Must include:
- Multi-seed stability analysis
- Contract-faceted results with per-seed breakdown
- Tail risk comparison (CVaR_5 CIs)
- Behavioral profile at FULL scale
- Reference to H14 refutation (why GBT is the path)

**Report traceability:** References `09_multi_rollout_diagnostic.md` (H14
refuted) and `08_gbt_prototype_evaluation.md` (GBT QUICK results).

**Deliverable:** 1 PR (experiment + report)

→ If PASS: proceed to Phase 2 (promotion decision).
→ If FAIL: proceed to Phase 1C (two-stage as last resort).

---

## Phase 1C: Two-Stage Make/Set Experiment (Conditional)

**Triggered by:** Phase 1B FAIL (GBT doesn't hold up at FULL) AND Phase 0
FAIL (multi-rollout didn't help OLS). This is the last resort before
declaring the suit regression unresolvable at this rung.

**Objective:** Test H12 interventionally. If neither label smoothing (H14)
nor model capacity (GBT) resolves suit, try explicit regime decomposition.

**Design:** Identical to v1 Phase 2 (Steps 2.1-2.8). See v1 plan for full
specification. Key elements:

- P(make) logistic classifier (gate: AUC > 0.70)
- Conditional payoff OLS models (make/set)
- Composite predictor for suit only; OLS AV v1 for high/low/pass
- Offline eval + behavioral screen + QUICK H2H
- Calibration diagnostics

**Report:** `docs/04_reports/arc_d_v1/r1_5/11_two_stage_evaluation.md`

**Deliverable:** 1-2 PRs

---

## Phase 2: FULL Validation + Promotion Gate

**Triggered by:** Any Phase 1 variant produces a viable candidate.

**Objective:** FULL-scale validation of the winning candidate with multi-seed
stability and promotion gate evaluation.

If Phase 1A produced the winner: run the winning cell at FULL scale.
If Phase 1B produced the winner: already at FULL (GBT FULL was Phase 1B).

**Promotion criteria:**
- Pooled delta vs R0 Hybrid: CI_low > 0.180
- Suit delta > 0 (regression resolved)
- No catastrophic tail risk (CVaR_5 > -10.0)
- Multi-seed stability (3 seeds, no reversals)

**Report:** `docs/04_reports/arc_d_v1/r1_5/11_full_validation.md` or
`docs/04_reports/arc_d_v1/r1_5/12_full_validation.md` (numbering depends on path)

---

## Phase 3: R1.5.3 Decision Report

**Triggered by:** Phase 2 complete.

**Objective:** Synthesize all findings into a promotion decision with full
traceability from diagnosis through candidate evaluation to decision.

**Report:** `docs/04_reports/arc_d_v1/r1_5/12_r1_5_3_promotion_decision.md` (or 13,
depending on path)

Must include:
- Complete hypothesis ledger with verdicts (H12, H13, H14)
- Summary of all candidates evaluated and their results
- Cross-references to every prior report in the chain
- Promotion decision: PROMOTED, ADVANCED, or HALT
- Implications for R1.5.4 (partner context) and R2 (opponent context)
- Attribution strategy going forward (if GBT: how to handle feature importance)

### Report Traceability Chain

```
08_gbt_prototype_evaluation.md     GBT QUICK: +1.1, suit resolved, prototype validated
  ↓
09_multi_rollout_diagnostic.md     H14 test: does label smoothing help OLS?
  ↓
10_model_label_matrix.md           2×2 decomposition (if H14 confirmed)
  OR                                  OR
10_gbt_full_validation.md          GBT at FULL scale (if H14 refuted)
  ↓
11_full_validation.md              Winner at FULL, 3-seed stability
  ↓
12_r1_5_3_promotion_decision.md    Final decision + hypothesis verdicts
```

Each report MUST include:
- **Provenance section** with seed, N, reproduction commands
- **Cross-reference** to predecessor report(s)
- **Hypothesis update** — which hypotheses this report tests and their verdict
- **Gate result** — PASS/FAIL with quantitative evidence

---

## Phase 4: Artifact Governance — DONE

PR #621 shipped: quarantine rejection, R² warning, behavioral validation script.

---

## Rejected Proposals

### Experiment 4: Learned Decision Policy

**Source:** Discussion log, Approach 4.
**Reason for rejection (three arguments):**

1. **Structurally Track C.** Track C (Pairwise Policy Optimization) is
   defined in the forward decision tree as: change the learning objective
   from "predict value" to "select correct action." Exp 4 does exactly
   this — the second model's labels aren't EV predictions, they're action
   selections (which action yielded the best net_points). The OLS
   predictions just become input features for what is essentially a policy
   classifier. The decision tree defers Track C because "it changes the
   learning objective, making failures hard to diagnose"
   (`plans/r1_5_forward_decision_tree.md`, line 137-138). Exp 4 inherits
   this problem — if the two-layer system makes bad bids, is it the OLS
   predictions that are wrong, or the decision model that's
   misinterpreting them?

2. **Historical precedent is unfavorable.** HybridOLSaBidder *was* model +
   decision layer. OLS predicted tricks, the Gaussian EV formula was the
   decision layer that converted predictions into action selection. That
   decision layer had H10 — a subtle bug where EV was monotonically
   non-increasing in bid level, causing the bidder to always pick the
   minimum legal bid. Exp 4 replaces the handcrafted formula with a learned
   one, which avoids that *specific* bug, but the general failure mode —
   "the decision layer has its own errors that compound with the prediction
   layer's errors" — remains.

3. **GBT already collapses the two layers.** GBT's `ActionValueBidder`
   predicts net_points directly and takes argmax. There's no separate
   decision layer to get wrong. The prototype already showed this works
   (+1.1 net_eppd at QUICK).

**Counter-argument acknowledged:** Exp 4 isn't pure Track C because it uses
OLS EV estimates as features rather than learning from raw hand features.
That's "Track B.5" rather than Track C. But arguments 2 and 3 still hold —
it adds complexity that GBT sidesteps, and the historical precedent for
model+decision-layer in this repo is unfavorable.

**When to reconsider:** Only if GBT fails at FULL AND multi-rollout doesn't
help OLS — the Phase 1C "last resort" scenario.

### Experiment 6: Selective Multi-Rollout

**Source:** Discussion log, Experiment 6.
**Reason for rejection:** Premature optimization. Don't optimize generation
cost before validating that multi-rollout helps at all. If Phase 0 confirms
H14, the sample count sweep (Step 0.3) provides the cost/benefit curve.
Selective-by-family optimization can be considered for FULL-scale generation
at that point, but doesn't warrant a separate experiment now.

### Naive Multi-Rollout (Repeated Deterministic Rollouts)

**Source:** Discussion log, Experiment 1 as originally described.
**Reason for correction:** `simulate_counterfactual()` is fully deterministic.
Continuation policy (HybridOLSaBidder) and play policy (GluttonStrategy) have
no randomness. Running the same (deal, hands, action) N times produces N
identical outcomes. The corrected approach (opponent hand resampling with
partner hand fixed) introduces meaningful variation by sampling from the
focal player's information set — only opponent hands are resampled, partner
hand stays fixed to preserve partner context feature alignment.

---

## Implementation Order

| Step | Phase | Est. PRs | Dependencies |
|------|-------|----------|-------------|
| 1 | Phase 4: Artifact governance | 1 | DONE (PR #621) |
| 2 | Phase 0: Imperfect-info diagnostic | 1 | None |
| 3a | Phase 1A: 2×2 matrix (if H14 confirmed) | 1 | Phase 0 PASS |
| 3b | Phase 1B: GBT FULL (if H14 refuted) | 1 | Phase 0 FAIL |
| 3c | Phase 1C: Two-stage (if 1B fails) | 1-2 | Phase 1B FAIL |
| 4 | Phase 2: FULL validation of winner | 0-1 | Phase 1 |
| 5 | Phase 3: Decision report | 1 | Phase 2 |

**Total estimated PRs:** 4-5 (depending on path)

**Critical path (fastest):** Phase 0 → Phase 1A or 1B → Phase 2 → Phase 3
(3-4 PRs, ~4-5 experiment runs)

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Opponent resampling doesn't smooth labels (hand features dominate outcome) | Medium | Low | Phase 0 is cheap; fail fast |
| GBT QUICK→FULL shrinkage > 50% | Low | High | 3-seed protocol catches instability |
| Multi-rollout OLS matches GBT but has worse tail risk | Low | Medium | CVaR comparison in 2×2 matrix |
| Opponent sampling introduces play-policy confound | Medium | Medium | Reuse same GluttonStrategy; compare label variance to null |
| Both multi-rollout and GBT fail at FULL | Very Low | High | Two-stage (Phase 1C) as last resort; hybrid routing as fallback |
| Opponent sampling 20x cost makes FULL-scale infeasible | Medium | Medium | Sweep finds "knee"; selective-by-family as future optimization |

## Outcome

_To be filled after implementation._

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — plan document |
| GBT prototype PR | #614 |
| GBT report PR | #618 |
| Artifact governance PR | #621 |
| Discussion log PR | #622 |
| Governing decision tree | plans/r1_5_forward_decision_tree.md |
| Key hypotheses | H12 (OPEN), H14 (NEW) |
| Superseded plan | plans/sessions/2026-03-12_r1-5-3-forward-plan.md |
