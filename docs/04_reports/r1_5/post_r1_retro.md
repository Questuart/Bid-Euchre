# Post-R1 Research Retrospective

**Arc:** D — OLSa-Hybrid Bidder
**Scope:** R1 through R1.5.2 diagnostics (commits `73b3ef0`..`f74ff62`)
**Date:** 2026-03-10
**PRs covered:** #493–#603 (111 merged PRs, 2026-03-02 through 2026-03-10)
**Experiment ledger:** [appendix_experiment_ledger.md](appendix_experiment_ledger.md)

## 1. Scope and Boundary

This retrospective covers all research-repo work since the R0 incumbent was
frozen at `r0-canonical-v2` (tag at commit `4e26d44`). It encompasses:

- **R0 Canonical v2 finalization** (#493–#527): bid-level search adoption,
  lambda tuning (RETAIN λ=0.0), normalizer screen (NO_GO_DEFER_R1),
  HITL sign-off, v2 report suite regeneration, plan archival
- **R1 Training Cycle** (#528–#554): partner context features, training,
  H2H battery, regression investigation, H10 proof, bid_bonus sweep
- **R1.5 v1 Objective Alignment** (#555–#584): design spec, action-value
  bidder, counterfactual datasets, training pipeline, gameplay screen,
  H2H QUICK/FULL, promotion decision (ADVANCED)
- **R1.5.2 Diagnostics** (#588–#603): calibration diagnostics, feature
  ablation matrix, partner ablation, interaction terms, declare/defend gate
- **Review Infrastructure** (#556–#601): commit status, autonomous review
  loop, Codex integration (GitHub + CLI fallback), deterministic prechecks

**Out of scope:** Review infrastructure PRs are not analyzed for research
content — they are workflow improvements, not experiments.

**Incumbent throughout:** `hybrid_olsa_full` R0 (`hybrid_r0_full.json`).
No rung was promoted; R0 remains the incumbent bidder.

## 2. Experiment Ledger (Summary)

See [appendix_experiment_ledger.md](appendix_experiment_ledger.md) for the
full structured ledger with one row per experiment.

**Experiment count by phase:**

| Phase | Experiments | Decisive | Suggestive |
|-------|------------|----------|------------|
| R0 v2 finalization | 3 | 3 | 0 |
| R1 training + investigation | 8 | 5 | 3 |
| R1.5 v1 pipeline | 7 | 4 | 3 |
| R1.5.2 diagnostics | 7 | 6 | 1 |
| **Total** | **25** | **18** | **4** |

**Key principle:** An experiment is "decisive" if its result, taken alone,
would change a design decision. It is "suggestive" if it provides evidence
toward a conclusion but requires corroboration.

## 3. Hypothesis Ledger

Each hypothesis is tracked with formal status. Evidence quality is
classified as:
- **Decisive:** Result directly proves/disproves the hypothesis with
  statistical significance or analytical proof
- **Suggestive:** Result supports/weakens the hypothesis but has caveats
  (single seed, confounded factors, small sample)

### 3.1 Confirmed Hypotheses

| ID | Hypothesis | Status | Evidence | Quality |
|----|-----------|--------|----------|---------|
| H1 | Objective mismatch (tricks_won → points_per_deal) was the main R1 failure mode | **CONFIRMED** | Cell B' bids 10 every hand with AV architecture + tricks_won target (1% make rate, -13.7 net_eppd). R1.5 reverses R1 regression (+0.152 vs -0.348). bid_bonus=0.25 partially reverses R1 but suit deficit persists. | Decisive — Cell B' proves the objective is necessary; R1→R1.5 delta reversal proves it is sufficient for high/low |
| H2 | Decision-layer bottleneck (H10: Gaussian EV non-increasing in bid_n) | **CONFIRMED** | Analytical proof (PR #552, 101 parametric tests). `_compute_ev_static()` EV monotonically non-increasing in bid_n for sigma > 0. `compute_best_bid()` always selects min_legal. | Decisive — mathematical proof, not statistical |
| H3 | Partner features matter for action selection (not just prediction) | **CONFIRMED** | R² delta < 0.005 for suit/high/low but pass R² drops 0.046→0.005. H2H: no-partner vs R0 = -0.492 (worse than R0), AV v1 vs R0 = +0.224. Partner features worth ~0.75 pts/deal. | Decisive — H2H comparison with controlled ablation |
| H4 | Objective and decision layer are synergistic (not separable) | **CONFIRMED** | Cell B' catastrophe proves argmax requires net_points. R0's Gaussian EV compensates for wrong objective. Neither component works alone. +0.152 total delta is non-decomposable. | Decisive — Cell B' is the key evidence |

### 3.2 Refuted Hypotheses

| ID | Hypothesis | Status | Evidence | Quality |
|----|-----------|--------|----------|---------|
| H5 | Suit regression caused by poor model fit | **REFUTED** | Suit has BEST R² (0.557) among all R1.5 contracts. The regression is decision-level, not prediction-level. | Decisive — direct R² comparison |
| H6 | More features (39→52) explain the R1.5 improvement | **REFUTED** | Cell A: R² delta < 0.005 between R0 features and full features on same target and data. 13 extra features contribute negligible predictive power. | Decisive — controlled ablation on same dataset |
| H7 | Non-linear interaction terms fix suit regression | **REFUTED** | 3 interaction terms (bower×trump, trump², bowers²): R² delta < 0.001, H2H +0.002 (noise). Q5 answered: OLS linearity is NOT the problem. | Decisive — null effect in both offline and gameplay |
| H8 | Partner features are intrinsically harmful to bidding | **REFUTED** | R1 regression was caused by decision-layer degeneracy (H2), not by partner features themselves. R1.5 uses same partner features with positive delta. Partner ablation shows they are AV v1's most valuable component. | Decisive — R1.5 success with same features that "caused" R1 regression |
| H9 | Counterfactual data improves R0-style models | **REFUTED** | Option A: R0 sparse OLS on counterfactual data yields suit R²=0.084 vs 0.223 on bidless data. Off-policy actions create noisier targets. | Decisive — direct R² comparison, same model architecture |
| H10 | Partner features are irrelevant to AV v1 | **REFUTED** | Zero-mask ablation: no-partner AV loses to R0 by -0.492 despite having objective alignment + argmax architecture. Partner features are essential, not optional. | Decisive — H2H with controlled ablation |

### 3.3 Weakened Hypotheses

| ID | Hypothesis | Status | Evidence | Quality |
|----|-----------|--------|----------|---------|
| H11 | Declare/defend regime split addresses bimodality | **WEAKENED** | Gate criterion #1 FAILED: +0.01 R² (threshold >0.05). Defend R²≈0 because hand can't predict other team's outcome. 87% of data is declaring anyway. However: this tests the WRONG decomposition. Make/set split within declaring is untested. | Suggestive — the specific implementation failed, but the general principle (regime decomposition) remains viable on a different axis |

### 3.4 Open Hypotheses

| ID | Hypothesis | Status | Evidence | Quality |
|----|-----------|--------|----------|---------|
| H12 | Bimodal make/set target causes suit regression via between-mode OLS prediction | **OPEN (leading theory)** | Bimodality confirmed: suit GMM delta_BIC=4,081. OLS predicts between modes (mean residual +0.087, heteroscedastic bimodal clusters). Suit has best R² but worst gameplay delta. Interaction terms don't help. But: the hypothesis has not been directly tested — no decomposed model has been built and evaluated. | Suggestive — strong correlational evidence, no interventional test yet |
| H13 | AV v1's always-bid-4 behavior leaves value on the table | **OPEN** | bid_n_sq creates concave EV curve peaking at bid_n=4. Not directly tested whether strong hands would benefit from higher bids. | Untested |
| H14 | FULL retraining (50k deals) would improve prediction quality | **OPEN** | All AV v1 results use QUICK-trained models. QUICK→FULL shrinkage was only 8% for H2H delta, suggesting QUICK models are adequate. But prediction variance reduction from more data is unquantified. | Untested |

## 4. Causal Attribution Table

The R1.5 improvement over R0 (+0.152 net_eppd) decomposes across five
causal factors. These factors are not fully separable — some are synergistic
(marked below).

| Factor | Direction | Magnitude | Separable? | Evidence Source | Confidence |
|--------|-----------|-----------|------------|----------------|------------|
| **Objective** (tricks_won → net_points) | Positive | Dominant | No — synergistic with decision rule | Cell B' catastrophe proves necessity; R1→R1.5 delta reversal proves sufficiency for high/low | High |
| **Decision rule** (Gaussian EV → argmax) | Positive | Dominant | No — synergistic with objective | H10 proof shows Gaussian EV is degenerate; argmax eliminates the degeneracy but requires net_points to function | High |
| **Partner context** (3 features) | Positive | +0.75 pts/deal | Yes — controlled ablation available | No-partner ablation: -0.492 vs R0 without, +0.224 with | High |
| **Data generation** (bidless → counterfactual) | Neutral/Negative for R0-style; Enabling for AV | N/A | Partially — Option A isolates data effect for R0 | Counterfactual data is worse for R0 sparse models (suit R² 0.084 vs 0.223). For AV, counterfactual data is *required* (provides action-value labels), not an independent improvement source. | Medium |
| **Model capacity / target structure** | Negative (suit) | -0.142 suit deficit | Yes — isolated to suit contract | Bimodality analysis (BIC=4,081), interaction terms null, declare/defend null. Structural OLS limitation on bimodal target. | High (diagnosis); Low (remedy untested) |

### 4.1 Attribution Summary

The +0.152 pooled delta breaks down by contract type as the most informative
attribution axis:

| Contract | Delta | Primary Factor | Secondary Factor |
|----------|-------|---------------|-----------------|
| High | +0.430 | Objective + decision rule | Partner context |
| Low | +0.495 | Objective + decision rule | Partner context |
| Suit | -0.142 | Model capacity (bimodal target, *negative*) | Partially offset by objective improvement |

The **objective + decision rule** change is the dominant positive factor,
delivering large gains in high/low where the relationship between hand
features and net_points is approximately linear. The **model capacity**
limitation (OLS on bimodal target) is the dominant negative factor, causing
the suit regression where bower interactions create a steeper make/set cliff.

### 4.2 What Cannot Be Attributed

- **Objective vs decision rule:** These are confounded. No intermediate
  bidder (net_points objective + Gaussian EV decision) was built. The
  Cell B' result proves they are synergistic (argmax requires net_points),
  but we cannot quantify the independent contribution of each.
- **Feature set vs architecture:** R1.5 uses 52-column features vs R0's 39,
  but Cell A shows the extra features contribute negligibly. The feature
  set change is a non-factor, not a confound.

## 5. What Worked / What Did Not

### 5.1 What Worked

1. **Objective alignment.** The single most impactful intervention across the
   entire R1→R1.5 arc. Switching from tricks_won to net_points reversed R1's
   regression (-0.348 → +0.152) and unlocked previously inaccessible high/low
   gains (+0.43/+0.49). This validates the R1 closeout diagnosis that the
   objective mismatch was the primary bottleneck.

2. **Partner features for action selection.** Despite contributing < 0.005
   R² to per-action prediction quality, partner features are AV v1's most
   valuable component (+0.75 pts/deal). They work through action selection
   (particularly pass decisions), not prediction accuracy — a distinction the
   R² metric alone cannot reveal.

3. **Argmax decision layer.** Eliminated the H10 degeneracy (EV
   non-increasing in bid_n) that plagued R0/R1. The simplicity of argmax
   removes hand-coded utility assumptions and lets the model's predictions
   directly drive decisions.

4. **Counterfactual dataset design.** Forced-action rollouts provide the
   action-value labels that make argmax viable. Without counterfactual data,
   the model cannot compare "what happens if I bid suit-4 vs high-4 vs pass"
   for the same hand.

5. **Pre-registered gating methodology.** Each experiment had formal gates
   with pre-specified thresholds. This prevented premature promotion (CI_low
   +0.124 < 0.180) and identified real blockers (suit regression). The
   adjudication process for Gate X3 (offline ranking) demonstrated that
   gates can be overridden with documented justification when the gate
   specification itself is flawed.

6. **Systematic hypothesis elimination.** The R1.5.2 diagnostic phase eliminated
   five hypotheses (features, linearity, interaction terms, regime split,
   partner irrelevance) in a structured campaign, narrowing the suit
   regression to a single leading theory (bimodal target structure).

### 5.2 What Did Not Work

1. **R1 approach (better predictions through misaligned pipeline).** Adding
   partner features to the tricks_won → Gaussian EV pipeline actively hurt
   performance. Better predictions amplified the H10 degeneracy for suit
   contracts. The lesson: improving a component in isolation can degrade the
   system if the interface between components is misaligned.

2. **Feature engineering.** Both expanding features (39→52) and adding
   non-linear interaction terms (bower×trump, trump², bowers²) yielded
   zero measurable improvement. The problem is in the target distribution
   structure, not the feature space.

3. **Declare/defend regime split.** Tested the wrong decomposition axis.
   Defend R²≈0 makes the defend model worthless. The productive
   decomposition is make/set within the declaring regime (H12, untested).

4. **Counterfactual data for R0-style models.** Off-policy actions create
   noisier tricks_won targets, degrading R0 sparse model fit (suit R²
   drops from 0.223 to 0.084).

5. **ModeloEspecifico R1 (hand-coded partner weights).** Catastrophically
   bad (-10.49 net_eppd). Naive partner-weight injection without model
   calibration is destructive. Positive feedback loop between partners
   (both bid aggressively based on each other's bids) was the mechanism.

### 5.3 Emergent Findings

1. **Quantity-over-quality strategy.** AV v1 independently discovered a
   valid bidding strategy: bid on ~57% of hands at minimum level (bid=4),
   accepting low set risk. This contrasts with R0's selective strategy
   (~43% bid rate, variable levels). Neither is obviously superior — AV v1
   wins overall but loses on suit.

2. **R² ≠ gameplay quality.** R1 had higher R² than R0 but worse gameplay.
   R1.5 suit has the best R² (0.557) but the worst gameplay delta (-0.142).
   Prediction accuracy and decision quality are distinct — a finding that
   should inform all future evaluation.

3. **Bimodality is universal, not suit-specific.** All R1.5 contracts show
   bimodal residuals (high BIC=1,469; low BIC=1,286). The difference is
   that high/low gains are large enough to overcome their bimodality; suit's
   steeper bower-driven make/set cliff makes the between-mode prediction
   more costly.

## 6. Decision Log

### 6.1 Active Decision: Next Research Direction

**Decision:** Pursue R1.5.3 (alternative model approaches) with three tracks:
(A) two-stage decomposed model testing H12, (B) gradient boosted trees, and
(C) pairwise policy optimization. See
[forward decision tree](../../../plans/r1_5_forward_decision_tree.md) and
[R1.5.3 plan](../../../plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md).

**Rationale:** All "easy" hypotheses have been eliminated. H12 is the sole
remaining leading theory with strong correlational evidence but no
interventional test. Track A tests H12 directly; Tracks B and C provide
alternative architectures if H12 is refuted.

### 6.2 Deferred Directions (with rationale)

| Direction | Why Deferred | Reactivation Trigger |
|-----------|-------------|---------------------|
| **Generic feature engineering sweep** | H6 and H7 show features are not the bottleneck. Interaction terms yielded zero effect. More feature engineering is not indicated. | Evidence that the suit problem is in the feature space (currently contradicted) |
| **Partner-feature removal** | H3 and H10 prove partner features are AV v1's most valuable component. Removing them regresses below R0. | N/A — definitively refuted |
| **Hybrid routing (AV high/low + R0 suit) as primary line** | Captures gains but teaches nothing about suit. Poor for causal cleanliness. Remains available as fallback for promotion pressure. | Decomposed suit model fails AND promotion pressure is urgent |
| **R1.5.4 partner-context improvements** | Premature — the suit regression may have a simpler cause (bimodal target) that doesn't require richer partner modeling. | R1.5.3 fails, confirming the problem is not target bimodality |
| **FULL retraining** | Optimization step, not direction-choosing. QUICK→FULL shrinkage was only 8%. | After a viable v2 architecture is validated |
| **Broad comparator batteries** | Unnecessary for diagnostic phase. Useful only for promotion validation. | After suit regression is resolved and promotion candidate exists |
| **Declare/defend split revival** | Gate criterion FAILED (+0.01 R²). Defend R²≈0 is a fundamental limitation. Wrong decomposition axis. | Strong new evidence that defend-regime modeling is viable (none expected) |
| **Quantile/Huber regression** | Wrong loss function for EV-based argmax decisions. Argmax requires mean predictions (EV), not quantile estimates. | Architecture change that doesn't use argmax EV (e.g., policy optimization) |

### 6.3 Fallback Hierarchy

If R1.5.3 alternative model approaches fail:

1. **Hybrid routing** — Immediate promotion path. Use AV v1 for high/low,
   R0 for suit. Expected pooled delta ≈ high/low gains with no suit penalty.
   Does not advance suit understanding.
2. **R1.5.4 partner context** — Richer partner modeling for suit contracts.
   Indicated if suit regression is not caused by target bimodality.

See [forward decision tree](../../../plans/r1_5_forward_decision_tree.md) for
the full phase sequencing and rung ladder.

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — retrospective document, not a gate artifact |
| R0 incumbent | hybrid_olsa_full R0 (`hybrid_r0_full.json`) |
| R0 tag | `r0-canonical-v2` at commit `4e26d44` |
| R1 closeout | `docs/04_reports/r1/01_r1_outcome_summary.md` |
| R1.5 closeout | `docs/04_reports/r1_5/rung_closeout.md` |
| R1.5.2 ablation | `docs/04_reports/r1_5/v2_ablation_analysis.md` |
| Experiment ledger | `docs/04_reports/r1_5/appendix_experiment_ledger.md` |
| Next experiment plan | `plans/archive/v1_sessions/2026-03-11_r1-5-3-alternative-approaches.md` |
| Forward decision tree | `plans/archive/v1_root/r1_5_forward_decision_tree.md` |
| analysis_base_sha | f74ff62 |
