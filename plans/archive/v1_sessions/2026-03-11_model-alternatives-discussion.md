# Model Alternatives Discussion Log

**Date:** 2026-03-11
**Arc:** D — OLSa-Hybrid Bidder
**Parent:** R1.5.3 Track B (GBT prototype, PR #614)
**Status:** DISCUSSION — experiment proposals, not yet executed

## Purpose

Design discussion exploring how GBT's introduction at R1.5.3 affects the
forward rung ladder, what alternative model architectures could address the
suit regression without abandoning OLS, and whether the bimodality problem
is better addressed at the label level than the model level.

## Context

The original Arc D execution plan (`plans/archive/arc_d_execution_plan.md` v3)
explicitly banned non-OLS models (line 59: "OLSa-hybrid family only. No neural
nets, tree models, or non-OLS regressors"). The plan assumed OLS was sufficient
and the bottleneck was information (missing context features), not model capacity.

R1.5.2 diagnostics proved the bottleneck was model capacity, not information.
OLS on bimodal suit targets (make/set, ~15 points apart) produces between-mode
predictions that match neither regime. Six alternative hypotheses eliminated.
GBT introduced as Track B after Step 0 diagnostic showed errors spread across
calibration range (28.5% at boundary < 60% Track A threshold).

## Key Differences: Original Plan vs. GBT Reality

| Aspect | Original Plan (OLS ladder) | GBT Reality |
|--------|---------------------------|-------------|
| Model class | Fixed OLS across all rungs | Changed at R1.5.3 |
| Improvement source | Progressive context features | Model capacity (nonlinear boundaries) |
| Attribution method | Dual-arm (OLSa vs OLSa_Full) | Broken — two variables changed |
| Bimodality handling | Not considered | GBT handles indirectly via tree splits |
| Feature importance | Requires dual-arm protocol | GBT provides natively (impurity reduction) |

## Implications for R1.5.4 (Partner Context) and R2 (Opponent Context)

### 1. Mechanically straightforward
GBTActionValueBidder consumes features through `STATE_FEATURE_NAMES` (52 cols).
Adding context features = wider feature vector + retrain. Same as OLS was.

### 2. Attribution design is compromised
Original ladder held model fixed, changed features → clean attribution. With
GBT, adding context features can't distinguish:
- Context features genuinely helping
- GBT being better at exploiting new features than OLS would be
- Nonlinear interactions between hand + context features

### 3. GBT may reduce need for context features
OLS needed hand-engineered features for nonlinear relationships. GBT discovers
interactions automatically through tree splits. Marginal value of context
features may be **smaller** under GBT than under OLS.

### 4. Training cost increases
OLS = instant (closed-form). GBT with 200 trees x depth 5 is heavier. More
features = more candidate split points per node. Not a blocker at ~40-50K
hands but changes sweep/ablation economics.

### 5. Overfitting risk increases
OLS can't overfit (convex, unique solution). GBT can — especially with
single-rollout noisy labels. Current mitigations: `max_depth=5, subsample=0.8`.
Adding 4-8 context features warrants hyperparameter re-sweep or early stopping.

## Open Questions for Forward Planning

1. **Attribution strategy:** Accept attribution loss (treat GBT as new fixed
   model class, restart context ladder from GBT baseline)? Or run parallel
   OLS/GBT arms (expensive but preserves interpretability)?

2. **Do context features still matter?** GBT's nonlinear capacity may already
   capture information that OLS needed explicit context features to access.
   Need to test empirically.

3. **Dual-arm design:** Does the OLSa vs OLSa_Full protocol make sense for
   GBT? GBT's native feature importance partially compensates but is less
   rigorous.

## Alternative Architectures Considered (OLS + Decision Layer)

Discussion explored whether GBT (full model replacement) is the right path,
or whether OLS could be preserved with a smarter decision layer on top.

### Approaches Evaluated

| # | Approach | Concept | Addresses suit bimodality? | Verdict |
|---|----------|---------|---------------------------|---------|
| 1 | KNN lookup | K nearest neighbors override OLS at inference | Partially (local averaging) | Curse of dimensionality at 52 features; inference cost; effectively a slower GBT |
| 2 | Confidence gate | Classifier routes "uncertain" predictions to conservative fallback | No — 43% of deficit is "confidently wrong", not uncertain | Wrong error profile |
| 3 | Regime detector | P(make) classifier + two conditional OLS models (= Track A) | Directly | Deprioritized by Step 0 gate (boundary = 28.5% < 60%) |
| 4 | Learned decision policy | OLS predictions become features for a second model that selects actions | Yes — learns OLS's systematic biases | Most promising "keep OLS" option |
| 5 | Calibration mapping | Isotonic regression on OLS predictions | No — bimodal, not miscalibrated | Can't fix between-mode predictions |

### Approach 4 (Learned Decision Policy) — Most Promising "Keep OLS" Option

```
Hand → OLS → [EV_suit_4, EV_suit_5, EV_high_4, ..., EV_pass]
                                    ↓
                        Decision model (logistic, GBT, or NN)
                                    ↓
                              Action selection
```

- OLS predictions become *features* for a decision model that learns which
  action to take (not what the EV is).
- Decision model can learn that "when OLS_suit = +0.5, always pick high because
  OLS is systematically overestimating suit in this region."
- Training labels exist: counterfactual dataset has true net_points per action.
- Conceptually "teacher-student": OLS teaches, decision model learns when to
  trust the teacher.
- Concern: related to Track C (pairwise policy optimization), which was deferred
  for interpretability reasons.
- Risk: decision model overfits to OLS's specific errors; if OLS retrains,
  corrections go stale.

### Key Insight: Repo Already Tried Model + Decision Layer

HybridOLSaBidder was this pattern: OLS predicts tricks, Gaussian EV formula
is the decision layer. That handcrafted layer had its own bugs (H10: EV
monotonically non-increasing in bid_n). A *learned* layer avoids the formula's
brittleness, but every added layer is a layer that can be wrong in
hard-to-diagnose ways. GBT's appeal is partly collapsing prediction + decision
into one trainable system.

### KNN as Diagnostic Tool (Alternative Role)

Rather than decision-making, KNN excels at *debugging*: "show me the 10
training hands most similar to this misclassified hand." This could be valuable
for understanding GBT failures without the dual-arm attribution protocol.

## Monte Carlo EV Estimation (Approach 6)

Discussion explored using Monte Carlo methods instead of or alongside the
current prediction models. Three distinct versions identified:

### Version 1: Replace Gaussian EV Formula (HybridOLSa only)

Replace `_compute_ev()` Gaussian analytical formula with MC sampling from a
better-fitting distribution (e.g., GMM). Only applies to HybridOLSaBidder
(R0 architecture). ActionValueBidder/GBT skip the Gaussian formula entirely
(they predict net_points directly). Going backward in the pipeline, not forward.

### Version 2: Multi-Rollout Counterfactual Labels — MOST PROMISING

Current dataset uses single rollouts per (deal, seat, action) — each label is
one sample from a bimodal outcome distribution. Multi-rollout (e.g., 20-50
rollouts per action) averages the label toward the true expected value.

**Why this is significant:**
- Attacks bimodality at the source (labeling), not the model
- Smoothed labels → label distribution becomes unimodal (centered on true EV)
- OLS could potentially work again on smoothed labels (no model-class change needed)
- GBT would also benefit (less overfitting to noisy labels)
- Complementary to any model choice — orthogonal improvement axis
- X3 gate failure (pass R²=0.046) was partly due to single-rollout noise
- Infrastructure exists: `simulate_counterfactual()` just needs a loop
- R1.5.3 plan already mentioned "repeated-rollout subset" as diagnostic option
  (lines 120-126 of alternative approaches plan); this extends it to a primary treatment

**Cost:** Dataset generation scales linearly with N rollouts. Could mitigate
by doing multi-rollout selectively (suit only, or boundary hands only).

**Key reframing:** The R1.5 conclusion was "OLS can't handle bimodal targets."
But the bimodality is partly a labeling artifact — single rollouts produce
binary make/set labels. Multi-rollout labels are smooth EVs. The model-capacity
problem might be a label-quality problem.

### Version 3: Online MCTS Simulation (At Bid Time)

Sample opponent hands, simulate full game forward, average outcomes. No model
needed. Conceptually MCTS (Monte Carlo Tree Search).

- No model bias at all; naturally handles bimodality
- Extremely expensive: ~100-1000 sims × ~20 actions × 4 seats = 8K-80K sims/deal
- Imperfect information (unknown opponent hands) requires sampling from info set
- Play policy quality (Glutton) directly biases simulation outcomes
- Not viable at current H2H battery scale (50K deals)

### Assessment

| Version | Bimodality fix? | Where applied | Cost | Best for |
|---------|----------------|---------------|------|----------|
| 1: Gaussian replacement | Partial | R0 inference | Low | Dead end (R0 architecture) |
| 2: Multi-rollout labels | **Source fix** | Training data | 5-20x gen time | Any model (OLS, GBT, etc.) |
| 3: Online MCTS | Full | Inference | 100-1000x per bid | Small-scale eval only |

**Version 2 deserves investigation as it could make the model-class question
moot.** If multi-rollout labels fix the bimodality at the source, OLS may be
sufficient, preserving the original rung ladder design and attribution protocol.

## Proposed Experiments

Six experiments designed to test the alternative approaches. Ordered by
information value per cost — cheapest/most informative first.

### Experiment 1: Multi-Rollout Label Diagnostic (SMOKE)

**Goal:** Does averaging multiple rollouts per action smooth the label
distribution from bimodal to unimodal? Does OLS R² improve on smoothed labels?

**Method:** Modify `generate_action_value_dataset.py` to accept a
`--n-rollouts N` parameter. For each (deal, seat, action), run N rollouts
and record `mean(net_points)` as the label. Generate a small dataset at
SMOKE scale with N=20 rollouts.

**Commands:**
```bash
# 1. Generate multi-rollout SMOKE dataset (500 deals × 4 seats × ~40 actions × 20 rollouts)
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --n-deals 500 --n-rollouts 20 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_multirollout_smoke_42

# 2. Train OLS on multi-rollout labels
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class ols \
  --dataset data/runs/av_multirollout_smoke_42/datasets/action_value.parquet \
  --output-dir data/runs/av_multirollout_smoke_42

# 3. Train GBT on multi-rollout labels (comparison)
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class gbt \
  --dataset data/runs/av_multirollout_smoke_42/datasets/action_value.parquet \
  --output-dir data/runs/av_multirollout_smoke_42
```

**Metrics:**
- Label distribution: plot net_points histogram for suit declared rows.
  Single-rollout should be bimodal; multi-rollout should be unimodal.
- OLS R² per contract family (compare vs single-rollout: suit=0.557, high=0.533, low=0.514, pass=0.046)
- GBT R² per contract family (compare vs single-rollout: suit=0.594)
- If pass R² rises substantially from 0.046, this confirms single-rollout noise was the bottleneck.

**Gate criterion:** OLS suit R² improves by > 0.03 (from 0.557 to > 0.587).
If met, proceed to Experiment 2 (QUICK scale). If not, multi-rollout labels
don't help OLS, and the suit issue is genuinely structural.

**Cost:** ~500 deals × 20 rollouts = ~10K rollout-equivalents. At ~50 deals/s
(single-rollout rate), this is ~200s (~3 min). Manageable.

**Implementation:** 1 PR — add `--n-rollouts` to `generate_action_value_dataset.py`,
loop `simulate_counterfactual()` N times, average net_points/tricks_won. Minimal
code change (~15 lines in `generate_dataset()`).

---

### Experiment 2: Multi-Rollout Label Validation (QUICK)

**Goal:** Confirm SMOKE findings at QUICK scale (2,500 deals). Run H2H battery
to measure gameplay delta, not just offline R².

**Prerequisite:** Experiment 1 gate passes (OLS suit R² > 0.587).

**Method:** Generate QUICK dataset with N=20 rollouts. Train OLS + GBT. Run
H2H battery against R0 incumbent.

**Commands:**
```bash
# 1. Generate multi-rollout QUICK dataset (~2500 deals × 20 rollouts)
uv run python scripts/internal/generate_action_value_dataset.py \
  --seed 42 --mode QUICK --n-rollouts 20 \
  --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
  --output-dir data/runs/av_multirollout_quick_42

# 2. Train both model classes
uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class ols \
  --dataset data/runs/av_multirollout_quick_42/datasets/action_value.parquet \
  --output-dir data/runs/av_multirollout_quick_42

uv run python scripts/internal/train_action_value.py \
  --seed 42 --model-class gbt \
  --dataset data/runs/av_multirollout_quick_42/datasets/action_value.parquet \
  --output-dir data/runs/av_multirollout_quick_42

# 3. H2H battery (multirollout-OLS vs R0, multirollout-GBT vs R0)
# Use existing H2H runner with new artifacts
```

**Metrics:**
- R² per contract (both OLS and GBT)
- H2H net_eppd delta vs R0 for each model class
- Suit delta specifically (target: improve from -0.142)
- Compare: multi-rollout OLS vs single-rollout GBT (is label quality or model
  class the bigger lever?)

**Gate criterion:** Multi-rollout OLS suit delta > -0.092 (same threshold as
Track A/B). If multi-rollout OLS beats single-rollout GBT, label quality is
the primary lever and the rung ladder can be preserved.

**Cost:** ~2,500 × 20 = ~50K rollout-equivalents. At ~50 deals/s base rate,
~17 min for generation. Training + H2H adds ~10 min. Total ~30 min.

---

### Experiment 3: Rollout Count Sweep

**Goal:** Find the minimum rollout count that captures most of the label-quality
benefit. Diminishing returns expected — does N=5 capture 80% of the N=50 gain?

**Method:** Generate datasets at N=1, 5, 10, 20, 50 rollouts (same 500 SMOKE
deals, same seed). Train OLS on each. Plot R² vs N.

**Commands:**
```bash
for N in 1 5 10 20 50; do
  uv run python scripts/internal/generate_action_value_dataset.py \
    --seed 42 --n-deals 500 --n-rollouts $N \
    --output-dir data/runs/av_rollout_sweep_${N}_42 \
    --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json

  uv run python scripts/internal/train_action_value.py \
    --seed 42 --model-class ols \
    --dataset data/runs/av_rollout_sweep_${N}_42/datasets/action_value.parquet \
    --output-dir data/runs/av_rollout_sweep_${N}_42
done
```

**Deliverable:** R² vs N plot per contract family. Identify the "knee" where
additional rollouts have diminishing returns. This informs the FULL-scale
dataset generation cost.

**Cost:** (1+5+10+20+50) × 500 = ~43K rollout-equivalents. ~15 min total.

---

### Experiment 4: Learned Decision Policy Prototype

**Goal:** Test whether OLS predictions can be used as features for a second
model that makes better action selections (Approach 4).

**Prerequisite:** Experiments 1-3 complete (to know whether label quality
or model architecture is the primary lever).

**Method:**
1. Load existing counterfactual dataset (single-rollout, QUICK)
2. For each (deal, seat), run OLS predictions for all legal actions
3. Build decision features: [OLS_EV_best_suit, OLS_EV_best_high, OLS_EV_best_low,
   OLS_EV_pass, gap_1st_2nd, max_suit_count, ...]
4. Label = index of action with highest true net_points (or the true net_points
   difference between OLS's chosen action and the oracle-best action)
5. Train a lightweight decision model (logistic regression or small GBT)
6. Evaluate: does the decision model pick better actions than raw OLS argmax?

**Metrics:**
- Action agreement rate: how often does decision model pick the same action as
  OLS? As oracle?
- Regret reduction: mean(oracle_net_points - chosen_net_points) for OLS argmax
  vs decision model
- Suit-specific: does the decision model learn to avoid OLS's suit overestimates?

**Gate criterion:** Regret reduction > 10% vs OLS argmax on held-out data.

**Cost:** No new dataset generation — uses existing data. Implementation is a
new script (~100 lines). Training is fast (logistic regression on ~10K rows).
Total: ~1 hour implementation + ~5 min runtime.

---

### Experiment 5: Multi-Rollout + GBT Combined (QUICK)

**Goal:** Test the strongest combination: better labels AND better model.

**Prerequisite:** Experiment 2 results (to know individual contributions).

**Method:** Train GBT on multi-rollout QUICK dataset (from Experiment 2).
Run H2H.

**Metrics:**
- Compare 4 cells: {OLS, GBT} × {single-rollout, multi-rollout}
- Decompose: how much improvement comes from labels vs model class?
- Is the combination additive or sub-additive?

**Gate criterion:** Multi-rollout GBT suit delta > 0 (positive, not just
"less negative"). If achieved, suit regression is solved.

**Cost:** Reuses Experiment 2 dataset. Training + H2H only. ~15 min.

---

### Experiment 6: Selective Multi-Rollout (Cost Optimization)

**Goal:** Can we get most of the label-quality benefit by multi-rolling only
suit contracts (the bimodal problem area)?

**Method:** Modify dataset generator to accept `--multi-rollout-families suit`
flag. Suit actions get N=20 rollouts; high/low/pass get N=1. Compare R² and
H2H against uniform N=20.

**Metrics:**
- Suit R² (should match uniform multi-rollout)
- High/low/pass R² (should be similar to single-rollout — these weren't bimodal)
- H2H delta (does selective multi-rollout match uniform?)
- Generation time savings (expect ~60-70% reduction vs uniform N=20)

**Gate criterion:** Suit R² within 0.01 of uniform multi-rollout. If met,
FULL-scale generation is feasible at ~3-4x cost instead of 20x.

**Cost:** Uses same 500 SMOKE deals. ~5 min.

---

### Experiment Dependency Graph

```
Exp 1 (SMOKE multi-rollout diagnostic)
  │
  ├── PASS (R² improves) ─────► Exp 2 (QUICK validation + H2H)
  │                                │
  │                                ├──► Exp 5 (multi-rollout + GBT combined)
  │                                └──► Exp 6 (selective multi-rollout)
  │
  ├── FAIL (R² flat) ─────────► Exp 4 (learned decision policy)
  │                               (multi-rollout doesn't help OLS;
  │                                try smarter decision layer instead)
  │
  └── Exp 3 (rollout sweep — run in parallel with Exp 1 to inform cost)
```

### Total Experimental Cost

| Experiment | Deals | Rollouts | Time Est. | Prerequisite |
|-----------|-------|----------|-----------|-------------|
| 1 (SMOKE diagnostic) | 500 | 20 | ~3 min | None |
| 2 (QUICK validation) | 2,500 | 20 | ~30 min | Exp 1 PASS |
| 3 (Rollout sweep) | 500 × 5 | 1-50 | ~15 min | None |
| 4 (Decision policy) | 0 (reuse) | 0 | ~1 hr impl | Exp 1 FAIL |
| 5 (Combined) | 0 (reuse) | 0 | ~15 min | Exp 2 |
| 6 (Selective) | 500 | 20 (suit) | ~5 min | Exp 2 |

Fastest path to answer: Exp 1 + Exp 3 in parallel (~15 min), then branch.

## Outcome

_To be filled after experiments are executed._

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — discussion log |
| Parent plan | `plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md` |
| Decision tree | `plans/r1_5_forward_decision_tree.md` |
| analysis_base_sha | 10ae54c |
