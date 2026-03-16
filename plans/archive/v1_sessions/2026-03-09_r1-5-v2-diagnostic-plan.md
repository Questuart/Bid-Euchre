# R1.5-v2 Diagnostic Plan — Calibration Analysis + Two-Stage Decomposition

**Date:** 2026-03-09
**Status:** REVIEWED — two review rounds complete (internal + Codex). Fixes: Step 1/2 sequencing, Phase 2 gate upgraded to conditional evidence, Cell B dropped/replaced with B' (objective isolation), cross-rung comparison scoped to pattern-only, causal identification limits documented.
**Governs:** R1.5-v2 execution — diagnostic experiments and regime-mixture modeling
**Prerequisites:** R1.5-v1 ADVANCED (PR #582), report restructure (PR #584)
**Q&A source:** `docs/04_reports/arc_d_v1/qa/r1_5_questions.md`

---

## Goal

Diagnose the root cause of the R1.5-v1 suit regression (-0.142 net_eppd) and
near-zero pass rate (0.007%) through targeted calibration analysis and ablation
experiments. Then implement a two-stage offense/defense decomposition to test the
bimodality hypothesis (Q14).

**Central hypothesis:** The suit regression and pass calibration failure share a
common cause — OLS models averaging over bimodal declare/defend outcome
distributions. If confirmed, a two-stage decomposition should improve both.

**Non-goal:** This plan does not aim for PROMOTED status. The goal is to understand
what's limiting AV v1 and build the next iteration with that understanding.

---

## Phase 1: Diagnostic (Steps 0–3)

Calibration analysis and targeted ablations to answer Q4, Q6, Q10, Q15.
No new model architecture — just analysis of existing artifacts.

### Step 0: Generate Cross-Rung Calibration Report

**Answers:** Q15 (cross-rung calibration), Q4 (suit regression cause), Q6 (prediction vs decision level)

**What:**
Generate calibration charts and residual diagnostics for R0 and R1.5 suit/high/low
models. Produce a written diagnostic report comparing calibration shape across rungs
and contract types.

**Implementation:**
1. Run `generate_rung_charts.py` for R0 (if not already cached):
   ```bash
   uv run python scripts/internal/generate_rung_charts.py \
     --rung r0 \
     --eval-dir data/runs/<r0_eval_dir> \
     --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
     --output-dir data/reports/arc_d/r0/charts/
   ```
2. For R1.5 we need a parallel chart generator that works with the action-value
   model's predictions. The existing `generate_rung_charts.py` assumes HybridOLSa
   structure (dual-arm, tricks_won target). We need a lightweight adapter or new
   script that:
   - Loads R1.5 model artifacts (`action_value_full.json`)
   - Runs predictions on the training/test split
   - Calls `plot_model_diagnostics()` and `plot_calibration_curve()` with
     `net_points` as the target
   - Generates per-contract residual analysis
3. Write diagnostic report: `docs/04_reports/arc_d_v1/r1_5/diagnostic_calibration.md`

**Key diagnostics to produce:**

*Within-rung diagnostics (directly comparable):*
- Per-contract predicted vs actual scatter
- Per-contract residual distributions — check for bimodality in suit residuals
- Per-contract calibration curves (binned mean predicted vs mean actual)
- Residual heteroscedasticity (residuals vs predicted) — does variance increase
  for mid-range predictions (the make/set boundary)?
- R1.5 suit residuals conditioned on bower count (0, 1, 2+)

*Cross-rung pattern comparison (shape only, not absolute values):*
R0 predicts `tricks_won` and R1.5 predicts `net_points` — these are different
scales with different variance and payoff geometry. Raw R², residual magnitude,
and calibration slopes are **not directly comparable** across rungs. The
cross-rung comparison focuses on qualitative patterns:
- Is suit the worst-calibrated contract in both rungs, or only R1.5?
- Does R0's suit model show the same heteroscedasticity pattern as R1.5's?
- Are residual distributions unimodal (R0) vs bimodal (R1.5) — or bimodal in both?
- Does the *relative* R² ranking across contracts differ (suit vs high vs low)?

**Acceptance criteria:**
- All charts generated and embedded in diagnostic report
- Bimodality diagnosis: residual distribution for suit either shows bimodal shape
  (supports Q14) or unimodal shape (refutes Q14)
- Specific recommendations for Phase 2 based on findings

**Files touched:**
- `scripts/internal/generate_r1_5_diagnostics.py` — new script (create)
- `docs/04_reports/arc_d_v1/r1_5/diagnostic_calibration.md` — new report (create)
- `src/bid_euchre/diagnostics/model_charts.py` — may need minor extension for
  residual bimodality test (edit, if needed)

**Testing:** Validate chart output files exist and are non-empty. Spot-check one
calibration curve bin against manual calculation from the underlying data.

**Estimated effort:** 1 PR

### Step 1: Training Data Distribution Analysis

**Answers:** Q10 (contract-type balance), Q11 (dataset size sensitivity)

**What:**
Analyze the counterfactual training dataset for contract-type balance and
net_points distribution shape per contract. Declare/defend analysis deferred
to after Step 2 (which adds the `focal_declared` column).

**Implementation:**
1. Load `data/runs/action_value_quick_42/datasets/action_value.parquet`
2. Compute:
   - Contract-type distribution (suit/high/low/pass action counts)
   - Per-contract net_points distribution (mean, std, skewness, kurtosis)
   - Per-contract net_points histogram — check bimodality visually and with
     Hartigan's dip test or similar
3. Include in diagnostic report from Step 0
4. **After Step 2 lands:** re-run with augmented dataset to add declare/defend
   ratio per contract and conditional distributions (net_points | declared,
   net_points | defended). This is a follow-up addition to the diagnostic report,
   not a blocker for the initial PR.

**Key question:** Is the suit net_points distribution bimodal (make/set cliff) while
high/low are more unimodal? If so, this is preliminary evidence for the regime
hypothesis, but the definitive test requires conditional analysis after Step 2.

**Acceptance criteria:**
- Contract-type balance documented with counts and percentages
- Per-contract net_points distributions plotted and tested for bimodality
- Dip test or mixture-model BIC for suit vs high/low bimodality comparison
- Declare/defend conditional analysis explicitly deferred to post-Step-2 follow-up

**Files touched:**
- `scripts/internal/generate_r1_5_diagnostics.py` — extend (edit)
- `docs/04_reports/arc_d_v1/r1_5/diagnostic_calibration.md` — extend (edit)

**Estimated effort:** same PR as Step 0

### Step 2: Augment Dataset with Declare/Defend Label

**Answers:** prerequisite for Q14 (two-stage decomposition)

**What:**
Add a `focal_declared` boolean column to the counterfactual dataset. This is
derivable from the existing simulation: compare `focal_seat` to `bidder_pos`
(the auction winner). If focal_seat's team won the auction, `focal_declared=True`.

**Implementation:**
1. Modify `scripts/internal/generate_action_value_dataset.py`:
   - In `simulate_counterfactual()`, return `bidder_pos` alongside `net_points`
   - In `generate_dataset()`, compute `focal_declared = (bidder_pos % 2 == focal_seat % 2)`
   - Add `focal_declared` to output columns
2. Regenerate dataset at QUICK scale (2,500 deals):
   ```bash
   uv run python scripts/internal/generate_action_value_dataset.py \
     --seed 42 --n-deals 2500 --mode QUICK \
     --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
     --output-dir data/runs/action_value_quick_42_v2
   ```
3. Verify backward compatibility — existing training pipeline should still work
   (new column is metadata, not a feature)

**Acceptance criteria:**
- `focal_declared` column present in output parquet
- Declare/defend split documented per contract type
- Existing training pipeline runs without modification on new dataset
- Unit test for the new column

**Files touched:**
- `scripts/internal/generate_action_value_dataset.py` — add focal_declared (edit)
- `tests/unit/test_action_value_dataset.py` — add test (edit or create)

**Estimated effort:** 1 PR

### Step 3: Feature × Dataset Ablation Matrix

**Answers:** Q1 (feature effect), Q2 (dataset effect), plus R1 cross-check

**What:**
The R0→R1.5 transition changed three things simultaneously: features (39→52),
objective (tricks_won→net_points), and training data (bidless→counterfactual).
To isolate these effects, build a 2×2 ablation matrix:

| | Bidless data | Counterfactual data |
|--|--|--|
| **R0 features (39)** | R0 baseline (exists) | **A: AV + R0 features + counterfactual** |
| **R1.5 features (52)** | **B: AV + R1.5 features + bidless** | AV v1 (exists) |

Plus an R1 cross-check:
- **C: R1 HybridOLSa on counterfactual data** — isolates the dataset effect for R1

**Implementation:**
1. **Cell A (R0 features + counterfactual):** Add feature-set parameter to
   `train_action_value.py`. Train with 39 R0 features on existing counterfactual
   dataset. Run QUICK H2H vs R0 baselines.
2. **Cell B — DROPPED.** The original design called for "R1.5 features + bidless
   data" to isolate the dataset effect. However, the bidless dataset has a
   fundamentally different schema (no action features, one row per hand per
   contract), and any adapter that preserves the AV schema changes more than
   just the dataset — it also changes intervention semantics and policy
   distribution. This makes Cell B's causal interpretation ("dataset doesn't
   matter" vs "counterfactual data is important") invalid.

   **Replacement — Cell B' (objective isolation):** Train AV with `tricks_won` as
   target on the *same* counterfactual data. This cleanly isolates the objective
   effect (tricks_won → net_points) while holding dataset, features, and
   architecture constant. This is a tighter ablation than the original Cell B.
   Run QUICK H2H vs R0 baselines and vs AV v1.
3. **Cell C (R1 + counterfactual):** Train R1 HybridOLSa-style model on
   counterfactual data. The counterfactual dataset records `net_points`; HybridOLSa
   expects `tricks_won`. Options: (a) extract `tricks_won` from counterfactual
   rollouts (it's computed internally but not currently saved — requires a small
   change to `generate_action_value_dataset.py` to emit `tricks_won` alongside
   `net_points`), or (b) generate a parallel counterfactual dataset with
   `tricks_won` target. Option (a) is simpler.
   Run QUICK H2H vs R1 baselines.

**Interpretation guide:**
- A matches AV v1 → new features don't matter, improvement is from objective + architecture
- A regresses from AV v1 → new features contribute positively
- B' matches AV v1 → objective change (tricks→points) doesn't matter, improvement is
  from architecture + features
- B' regresses from AV v1 → objective alignment is a real contributor
- C improves over R1 → dataset structure was a significant factor in R1's STOP
- C matches R1 → R1's problem was genuinely the decision layer, not the data

**Note on causal identification:** The ablation matrix isolates features (A vs v1),
objective (B' vs v1), and dataset structure (C vs R1). It does NOT cleanly separate
dataset from architecture effects, because counterfactual data inherently couples
with the AV action-enumeration architecture. This is a known limitation.

**Acceptance criteria:**
- All 3 cells + R1 cross-check documented with per-contract deltas and bootstrap CIs
- Effect decomposition: feature contribution, objective contribution, dataset
  contribution (with caveats on identification limits)
- R1 cross-check documented
- Written up as ablation section in diagnostic report

**Testing:** Validate each ablation cell's training pipeline runs end-to-end with
`--dry-run` or SMOKE-scale before committing to QUICK. For Cell C, verify
HybridOLSa loads the adapted counterfactual data without schema errors.

**Files touched:**
- `scripts/internal/train_action_value.py` — add feature-set parameter + target
  column parameter (edit)
- `scripts/internal/generate_action_value_dataset.py` — add `tricks_won` output
  column for Cell B' and Cell C compatibility (edit)
- `experiments/configs/r1_5_ablation_*.yaml` — new configs (create, 2-3 files)

**Estimated effort:** 2 PRs (one for infrastructure + Cell A, one for Cells B'+C)

---

## Phase 2: Two-Stage Decomposition (Steps 4–7)

Build and evaluate the regime-mixture model. Contingent on Phase 1 confirming
bimodality in suit net_points distributions.

**Go/no-go gate:** The gate is based on **conditional** evidence, not raw
unconditional bimodality. Raw suit net_points can be bimodal regardless of whether
a declare/defend split is the right fix. The gate requires at least one of:

1. **Conditional residual improvement:** After Step 2 augments the dataset with
   `focal_declared`, fit separate OLS models on declared-only and defended-only
   suit subsets. If per-regime R² improves meaningfully over the pooled model
   (e.g., >0.05 R² gain), the regime split has predictive value.
2. **Declare/defend mixing is a dominant error source:** Residual analysis from
   Step 0 shows that the AV v1 suit model's largest errors concentrate at the
   declare/defend boundary (e.g., residuals are bimodal *conditional on predicted
   value*, not just unconditionally).
3. **Small pilot:** Train a quick two-stage suit-only model on SMOKE data and
   show improved suit calibration or R² vs the single-stage model.

If none of these hold, skip to Phase 3 (interaction terms) — the regime
decomposition is not the right fix even if the data is bimodal.

### Step 4: Two-Stage Model Infrastructure

**Answers:** Q14 (regime-mixture hypothesis)

**What:**
Implement the two-stage ActionValueBidder:
- Stage 1: Logistic regression predicting P(focal_declared | state, action)
- Stage 2a: OLS predicting E[net_points | focal_declared=True, state, action]
- Stage 2b: OLS predicting E[net_points | focal_declared=False, state, action]
- Decision: EV = P(declared) × E[points|declared] + (1-P(declared)) × E[points|defended]

**Implementation:**
1. New class `TwoStageActionValueBidder` in `src/bid_euchre/strategy/bidding.py`
   - Inherits from `ActionValueBidder` for shared infrastructure
   - Overrides `choose_bid()` to use two-stage EV calculation
   - Loads 3 model sets per contract: declare_model, defend_model, gate_model
2. New training script `scripts/internal/train_two_stage_action_value.py`
   - Splits training data by `focal_declared` column
   - Trains logistic gate + 2 OLS models per contract (8 models + 4 gates = 12 total)
   - Saves artifacts in standard format
3. Unit tests for the new bidder class

**Key design decisions:**
- Keep OLS for all regression components (interpretability preserved)
- Use sklearn LogisticRegression for the gate (inspectable coefficients)
- Same 52-column feature set as AV v1 (no new features — isolate the architecture effect)

**Acceptance criteria:**
- `TwoStageActionValueBidder` class implemented and unit tested
- Training script produces artifacts loadable by the bidder
- Gate X2 equivalent: R² for declare/defend models ≥ thresholds per contract
- Gate accuracy for logistic gate documented

**Files touched:**
- `src/bid_euchre/strategy/bidding.py` — add TwoStageActionValueBidder (edit)
- `scripts/internal/train_two_stage_action_value.py` — new (create)
- `tests/unit/test_two_stage_bidder.py` — new (create)
- `src/bid_euchre/experiments/config.py` — register new strategy (edit)

**Estimated effort:** 1-2 PRs

### Step 5: Train and Evaluate Two-Stage Models

**What:**
Train the two-stage models on QUICK data, run self-play screen, then QUICK H2H.

**Implementation:**
1. Train two-stage models:
   ```bash
   uv run python scripts/internal/train_two_stage_action_value.py \
     --seed 42 \
     --dataset data/runs/action_value_quick_42_v2/datasets/action_value.parquet \
     --output-dir data/runs/two_stage_quick_42
   ```
2. Self-play screen (3 seeds, 2,500 deals each) — check for catastrophic behavior
3. QUICK H2H battery: TwoStage vs AV_v1 vs HO_full_R0

**Key metrics:**
- Per-contract deltas: does the two-stage model improve suit specifically?
- Pass rate: does it increase from near-zero to a reasonable level?
- Gate logistic accuracy: does P(declared) predict well?
- Behavioral profile: bid rate, make rate, bid level distribution

**Acceptance criteria:**
- Self-play screen passes (no catastrophic behavior)
- Per-contract deltas documented with bootstrap CIs
- Pass rate comparison: TwoStage vs AV_v1 vs R0
- Written report: `docs/04_reports/arc_d_v1/r1_5/diagnostic_two_stage_eval.md`

**Files touched:**
- `experiments/configs/r1_5_two_stage_self_play.yaml` — new (create)
- `experiments/configs/r1_5_two_stage_h2h.yaml` — new (create)
- `docs/04_reports/arc_d_v1/r1_5/diagnostic_two_stage_eval.md` — new (create)

**Estimated effort:** 1 PR

### Step 6: Calibration Comparison — v1 vs Two-Stage

**What:**
Generate the same calibration diagnostics from Step 0 for the two-stage model.
Produce a side-by-side comparison showing whether the two-stage model fixes the
suit residual bimodality and improves pass calibration.

**Acceptance criteria:**
- Side-by-side residual distribution plots (v1 vs two-stage) for suit
- Calibration curve comparison per contract
- If two-stage fixes suit: proceed to FULL evaluation
- If two-stage doesn't fix suit: investigate interaction terms (Phase 3)

**Estimated effort:** same PR as Step 5

### Step 7: FULL Evaluation (Conditional)

**Gate:** Only if Step 5 shows suit delta improvement AND overall delta positive.

**What:**
Full-scale H2H battery (50,000 deals × 9 matchups) with the two-stage model.
Follows the same protocol as R1.5-v1 FULL evaluation.

**Acceptance criteria:**
- Per-contract deltas with CIs
- Gate X4 evaluation against promotion thresholds
- Formal promotion decision

**Estimated effort:** 1 PR

---

## Phase 3: Fallback — Interaction Terms (Steps 8–9)

Only if Phase 2 does not close the suit gap. Tests whether the suit problem is
feature-level rather than target-level.

### Step 8: Suit Interaction Features

**Answers:** Q5 (OLS linearity vs missing features)

**What:**
Add interaction terms to the suit model only. Use actual feature names from
`FEATURE_REGISTRY.md` (v7 schema):

- `bowers × trump_count` — bower strength × trump length (NEW)
- `trump_count × trump_count` — quadratic trump length (NEW)
- `bowers × bowers` — quadratic bower count (NEW, only meaningful for 0/1/2)

Note: `trump_count_x_offsuit_ace` (feature #36) already exists in the registry.
These new terms target bower-specific non-linearities that #36 doesn't capture.

Retrain suit model with interaction terms. Compare R² and H2H suit delta.

### Step 9: Combined Model

If interaction terms improve suit, combine with two-stage decomposition
(if Phase 2 showed pass calibration improvement). Build the best-of-both
model and evaluate.

---

## Question Coverage

| Question | Phase | Step | Status |
|----------|-------|------|--------|
| Q1 (R0 features) | 1 | 3 (Cell A) | Planned |
| Q2 (objective + dataset effect) | 1 | 3 (Cells B'+C) | Planned — Cell B' isolates objective; Cell C isolates dataset for R1. Full dataset effect not cleanly identifiable (see causal note). |
| Q3 (objective vs decision layer) | — | — | Partially addressed by ablation matrix; full isolation deferred to v3 |
| Q4 (suit regression cause) | 1 | 0 | Planned |
| Q5 (OLS vs features) | 3 | 8 | Fallback |
| Q6 (prediction vs decision) | 1 | 0 | Planned |
| Q7 (bid level 4 only) | — | — | Diagnostic only — not blocking |
| Q8 (quantity over quality) | — | — | Diagnostic only — not blocking |
| Q9 (pass boundary) | — | — | Addressed if two-stage fixes pass rate |
| Q10 (contract balance) | 1 | 1 | Planned |
| Q11 (dataset size) | — | — | Deferred — FULL retraining in Phase 2 |
| Q12 (partner features) | — | — | Deferred — implicit in feature ablation |
| Q13 (vs R1) | — | — | Deferred — add R1 to roster in Phase 2 |
| Q14 (bimodality) | 1+2 | 1, 4–6 | Primary hypothesis |
| Q15 (calibration) | 1 | 0 | Planned |
| Q16 (two-level vs three-level) | 1 | 0–1 diagnostics inform | Investigate during Phase 1 |
| Q17 (quantile/Huber rejection) | — | — | Resolved: wrong loss for EV decision rule |

## Deliverables

1. **Diagnostic calibration report** (`docs/04_reports/arc_d_v1/r1_5/diagnostic_calibration.md`)
   — Cross-rung calibration comparison, residual analysis, bimodality test
2. **R0-features ablation report** (section in calibration report or standalone)
3. **Two-stage evaluation report** (`docs/04_reports/arc_d_v1/r1_5/diagnostic_two_stage_eval.md`)
   — If Phase 2 proceeds
4. **Updated Q&A log** with answers from each step

## Estimated PR Sequence

| PR | Content | Phase |
|----|---------|-------|
| 1 | Diagnostic charts + training data analysis + report (Steps 0-1) | 1 |
| 2 | Dataset augmentation with focal_declared (Step 2) | 1 |
| 3 | Ablation matrix Cell A: R0 features + counterfactual (Step 3) | 1 |
| 3b | Ablation matrix Cells B'+C: objective isolation + R1 cross-check (Step 3) | 1 |
| 4 | Two-stage bidder infrastructure (Step 4) | 2 |
| 5 | Two-stage training + evaluation + report (Steps 5-6) | 2 |
| 6 | FULL evaluation (Step 7, conditional) | 2 |

## Outcome

**Phase 1: COMPLETE** — All ablation experiments run, findings documented.

### Key Findings

1. **Features are irrelevant** — R² delta < 0.005 between R0 (39) and full (52) feature sets
2. **Objective alignment is critical** — Cell B' (tricks_won + AV argmax) bids 10 every hand,
   1% make rate, -13.7 net_eppd vs AV v1. Architecture requires net_points to function.
3. **Counterfactual data is noisier for R0** — R0 sparse OLS on counterfactual data: suit R²=0.084
   vs 0.223 on bidless data. Data alone is not an improvement source.
4. **Declare/defend gate FAILED** — Criterion #1: +0.01 R² (threshold >0.05). Defend R² ≈ 0
   because focal player's hand can't predict opponent outcomes. Criteria #2/#3 moot.
5. **R1.5 improvement is synergistic** — The +0.152 net_eppd comes from net_points + argmax +
   counterfactual action enumeration working together. No single component is cleanly attributable.

### Phase 2 Decision

Phase 2 (two-stage declare/defend model) **SKIPPED** — gate criterion #1 failed, and the
fundamental limitation (defend R² ≈ 0) makes criteria #2/#3 unlikely to pass. The productive
decomposition is make/set within the declaring regime, not declare/defend.

### Resulting PRs

| PR | Content | Status |
|----|---------|--------|
| #588 | Diagnostic plan | Merged |
| #589 | Dataset augmentation (focal_declared + tricks_won) | Merged |
| #590 | Ablation infra (--feature-set + --target) | Merged |
| #591 | Calibration diagnostics script + report template | Merged |
| #595 | Diagnostic findings + Q&A updates | Open (pending merge) |
| #599 | Ablation analysis report | Open (pending merge) |

### Reports

- `docs/04_reports/arc_d_v1/r1_5/diagnostic_calibration.md` — calibration diagnostics + training data analysis
- `docs/04_reports/arc_d_v1/r1_5/v2_ablation_analysis.md` — R² ablation matrix + H2H decomposition + gate results
- `docs/04_reports/arc_d_v1/r1_5/r1_5_questions.md` — Q&A log (17 questions, 8+ answered)
