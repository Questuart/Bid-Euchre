# R1.5 Open Questions Log

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Purpose:** Catalog unanswered questions from R1.5 v1 evaluation to guide v2 planning

## Attribution / Ablation

### Q1: What is the effect of the ActionValueBidder architecture using only R0 features?

**Status:** UNANSWERED
**Why it matters:** R1.5 introduced 52-column features (39 R0 hand + bid_n, bid_n_sq,
state columns). We don't know how much of the +0.152 delta comes from the new features
vs the new decision approach (argmax over per-contract models).
**Test:** Build AV bidder restricted to 39 R0 hand features. Run H2H vs R0.

### Q2: How much of the improvement comes from different training data vs different modeling technique?

**Status:** UNANSWERED → UPGRADED TO ABLATION MATRIX (Session 2026-03-09)
**Why it matters:** R1.5 changed three things simultaneously: features (39→52),
objective (tricks_won→net_points), and training data (bidless→counterfactual). The
R0-features ablation (Q1) only controls for features — it still uses counterfactual
data. To properly isolate effects, we need a 2×2 matrix:

| | Bidless data | Counterfactual data |
|--|--|--|
| **R0 features (39)** | R0 baseline (exists) | AV on R0 features + counterfactual (Q1) |
| **R1.5 features (52)** | AV on R1.5 features + bidless (NEW) | AV v1 (exists) |

The off-diagonal cells isolate the dataset effect (holding features constant) and the
feature effect (holding dataset constant).

**Additional R1 cross-check:** Train R1 HybridOLSa on counterfactual data (tricks_won
target, counterfactual generation). If counterfactual data alone improves R1, then the
dataset structure was always a significant factor — not just the objective/decision layer.
This would reframe the R1 STOP diagnosis.

**Tests:**
1. **Cell A:** AV bidder with R0 features on counterfactual data (isolates features)
2. **Cell B' (replaces original Cell B):** AV bidder with R1.5 features trained on
   `tricks_won` target (same counterfactual data, different objective). Isolates the
   objective effect cleanly. Original Cell B (bidless data) was dropped because the
   bidless schema is fundamentally incompatible with the AV action-enumeration
   architecture — any adapter changes more than just the dataset.
3. **Cell C:** R1 HybridOLSa on counterfactual data with `tricks_won` target (isolates
   dataset effect for R1)

**Causal identification note:** The ablation matrix isolates features (A vs v1),
objective (B' vs v1), and dataset structure (C vs R1). It does NOT cleanly separate
dataset from architecture effects for the R0→R1.5 transition, because counterfactual
data inherently couples with the AV action-enumeration architecture.

### Q3: Is the improvement from changing the objective (tricks_won → net_points) or the decision layer (Gaussian EV → argmax)?

**Status:** UNANSWERED
**Why it matters:** The R1 closeout diagnosed the decision layer as the bottleneck, but
R1.5 changed both the objective and the decision layer simultaneously. We attributed the
improvement to "objective alignment" but this is unproven.
**Test:** Build AV bidder trained on tricks_won (same architecture, different objective).
If it performs similarly to R1.5 v1, the decision layer matters more. If it regresses,
the objective matters more.

## Suit-Contract Regression

### Q4: Why does the action-value model regress on suit contracts specifically?

**Status:** PARTIALLY ANSWERED
**Current understanding:** Suit contracts involve bower interactions and trump effects
that create non-linearities the OLS model cannot capture. But we haven't verified this
hypothesis — it could also be a training data issue (fewer suit observations, different
reward distributions) or a feature gap (missing bower-specific features).
**Test:** Examine per-contract R² and residual patterns. Check if suit model has
systematically higher residuals on hands with bowers. Compare feature importance
across contract types.

### Q5: Is the suit regression from the model architecture (OLS) or from missing features?

**Status:** UNANSWERED
**Why it matters:** If OLS can't capture suit dynamics with any features, we need a
non-linear model. If the right features would fix it, OLS may be sufficient.
**Test:** Add interaction terms (e.g., bower_count × trump_length) to the suit model
and retrain. If R² improves significantly, features are the bottleneck. If not,
architecture is the bottleneck.

### Q6: Does the suit regression exist at the prediction level or only at the decision level?

**Status:** UNANSWERED
**Why it matters:** The suit model might predict net_points accurately but make poor
bid decisions (e.g., overbidding on marginal suit hands). Or it might have poor
predictions entirely.
**Test:** Compare suit model R² and calibration vs high/low models. Check if the suit
model's argmax decisions agree with oracle more or less than high/low models.

## Behavioral Analysis

### Q7: Why does AV v1 never bid above level 4?

**Status:** PARTIALLY ANSWERED
**Current understanding:** The model's net_points predictions for bid_n > 4 are likely
negative (set penalty outweighs the marginal point gain). But we haven't verified the
prediction surface — it could be that the quadratic action encoding (bid_n, bid_n_sq)
creates a monotonically decreasing EV curve above 4.
**Test:** For a sample of strong hands, plot model predictions across all legal bid
levels. Identify whether the model ever predicts positive EV for bid_n > 4.

### Q8: Is the "quantity over quality" strategy optimal or a model artifact?

**Status:** UNANSWERED
**Why it matters:** AV v1 bids on 56-57% of hands at minimum level. This could be a
genuine strategic insight (bidding on marginal hands at low risk is +EV) or a model
failure (inability to distinguish strong from weak hands, defaulting to always-bid).
**Test:** Compare AV v1's bid decisions to the oracle (counterfactual best action) on
hands where AV bids but R0 passes. Is AV right more often than R0?

### Q9: What happens at the boundary — hands where AV v1 barely bids vs barely passes?

**Status:** UNANSWERED
**Why it matters:** With only 0.007% pass rate, the pass/bid boundary is nearly
degenerate. Understanding what the few passed hands look like reveals the model's
effective decision threshold.
**Test:** Examine the ~2 hands (out of 7,500) where AV v1 passed in the 3-seed
gameplay screen. What features distinguish them?

## Training Data

### Q10: Does the counterfactual dataset have balanced contract-type representation?

**Status:** UNANSWERED
**Why it matters:** If suit contracts are underrepresented in training data (because
the continuation policy bids suit less often), the suit model trains on fewer examples,
possibly explaining worse performance.
**Test:** Count contract-type distribution in the training dataset. Compare to the
distribution of legal actions in gameplay.

### Q11: How sensitive are the models to training dataset size?

**Status:** PARTIALLY ANSWERED
**Current understanding:** QUICK-trained models (2k deals) showed similar H2H deltas
to what we'd expect from FULL-trained models (+0.165 QUICK → +0.152 FULL, stable).
But we didn't actually retrain at FULL scale to compare model quality directly.
**Test:** Retrain on FULL dataset (50k deals). Compare R², residuals, and H2H
performance to QUICK-trained models.

## Bimodality / Regime Mixture (Session 2026-03-09)

### Q14: Is the suit regression caused by bimodal target distributions, not OLS linearity?

**Status:** HYPOTHESIS — UNTESTED
**Why it matters:** Suit contracts have sharper make/set cliffs than high/low (bowers
create bimodal outcome distributions). A single OLS model predicting the *mean* of a
bimodal distribution will be wrong in both modes. This same bimodality may explain both
the suit regression (-0.142) and the near-zero pass rate (pass model R²=0.046).
**Hypothesis:** The suit problem and the pass problem are the same problem — OLS
averaging over fundamentally different offensive/defensive regimes.
**Test:** Two-stage decomposition:
- Stage 1: P(declare | state, action) — logistic/classification
- Stage 2a: E[net_points | declare, state, action] — OLS within declaring regime
- Stage 2b: E[net_points | defend, state, action] — OLS within defending regime
- Decision: EV = P(declare) × E[points|declare] + (1-P(declare)) × E[points|defend]

This keeps OLS (interpretable) but separates the bimodal regimes. Each stage's target
should be closer to unimodal and more OLS-friendly.

**Key insight from discussion:** This is a regime-mixture problem, not an instrumental
variable problem. The declare/defend regime is *observed* in training data, so we can
split directly without latent variable machinery.

**Expected impact:**
- Pass calibration: HIGH — directly addresses the near-zero pass rate
- Suit regression: MEDIUM-HIGH — separating make/set regimes may be more impactful than
  interaction terms, since the non-linearity may be in the target distribution, not the
  feature space
- High/low: LOW — already performing well with single-stage OLS

### Q16: Should the regime decomposition be two-level or three-level?

**Status:** OPEN — INVESTIGATE DURING PHASE 1 DIAGNOSTICS
**Why it matters:** The two-stage decomposition (Q14) splits declare/defend. But within
the declaring regime, there's a further bimodal split: make vs set. The full structure is:

```
EV = P(declare|s,a) × [ P(make|declare,s,a) × E[pts|declare,make,s,a]
                       + P(set|declare,s,a)  × E[pts|declare,set,s,a] ]
   + P(defend|s,a) × E[pts|defend,s,a]
```

This is more expressive than two-stage because the make/set cliff is where suit
bimodality actually lives — a hand with both bowers almost always makes, a hand with
zero bowers in a suit bid often gets set. The defending regime is likely closer to
unimodal (you're collecting whatever tricks you can), so it may not need the extra split.

**Model count:** 5 per contract × 4 contracts = 20 models (vs 12 for two-stage).
**Tradeoff:** More models = better regime separation but smaller training samples per
model and more parameters to fit. May require FULL-scale training data (50k deals).

**Decision criteria:** Examine Phase 1 diagnostics (Step 0-1):
- If suit residuals show clear bimodality *within the declaring subset*, three-level
  is justified
- If declaring-only residuals are closer to unimodal, the make/set split adds
  complexity without benefit
- If the defend subset is already well-fit by single OLS, skip the defend-side split

### Q17: Why quantile/Huber regression are poor fits for this problem

**Status:** RESOLVED — NOT RECOMMENDED
**Analysis:** The decision rule is argmax over E[net_points]. Methods that optimize
different loss functions (quantile → median, Huber → downweighted outliers) can rank
actions incorrectly even when they produce more stable predictions.

Key argument: in a bimodal distribution, the "other mode" is not noise — it's the
phenomenon the model needs to understand. Downweighting it (Huber) or ignoring it
(quantile) makes fitting prettier but the bidder worse at recognizing high-variance
positive-EV actions.

Example: Action A (50% chance +10, 50% chance -2, mean +4) vs Action B (always +1).
Median-based ranking may prefer B; EV-based ranking correctly prefers A.

**Conclusion:** The right approach is to model the regimes explicitly (observed-regime
decomposition), not to suppress them with robust estimators. Methods ranked:
1. Observed-regime decomposition (hurdle / two-stage / three-stage)
2. Interaction terms / nonlinear features (if regime decomposition isn't sufficient)
3. Averaged rollouts (noise reduction, complementary)
4. Quantile / Huber (wrong statistical problem for this decision rule)

### Q15: Cross-rung calibration comparison — where exactly do predictions go wrong?

**Status:** UNANSWERED — INFRASTRUCTURE EXISTS
**Why it matters:** We know R1.5 regresses on suit and improves on high/low, but we
don't know *how* the predictions fail. Is the suit model systematically biased
(over/under-predicting)? Is the variance higher? Are the errors concentrated on
specific hand types (bower-heavy, trump-short)?
**Infrastructure:** `plot_calibration_curve()` and `plot_model_diagnostics()` in
`src/bid_euchre/diagnostics/model_charts.py` already generate per-contract calibration
charts. The `30_feature_outcome_eval.py` notebooks use them per-rung.
**What's missing:** A cross-rung comparison on the same axes. R0 predicts `tricks_won`
and R1.5 predicts `net_points`, so raw predictions aren't directly comparable. But
calibration *shape* (systematic bias, heteroscedasticity pattern) is comparable.
**Test:** Generate calibration + residual plots for R0 and R1.5 suit models. Compare:
- Bias direction (over- vs under-prediction) and magnitude
- Residual variance (homoscedastic vs heteroscedastic)
- Residual pattern by hand strength (are errors concentrated on marginal hands?)

## Cross-Cutting

### Q12: Would the R1 partner features help the action-value model?

**Status:** UNANSWERED
**Why it matters:** R1.5 uses the same 3 partner features as R1 (partner_bid_level,
partner_suit_match, partner_high_card_signal). The R1 results showed these had minimal
impact on HybridOLSa (+0.028 delta). But they might interact differently with the
action-value approach.
**Test:** Already implicitly included — R1.5 uses partner features. But could test
AV without partner features to measure their contribution in this architecture.

### Q13: How does AV v1 compare to R1 HybridOLSa (not just R0)?

**Status:** UNANSWERED
**Why it matters:** We compared AV v1 to R0 baselines only. R1 HybridOLSa had better
tricks_won models but worse gameplay (due to decision layer). AV v1 bypasses the
decision layer — comparing to R1 would show whether AV v1 captured the R1 model
improvements that were previously lost.
**Test:** Add R1 HybridOLSa to the H2H roster and run a battery.

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — diagnostic log, no formal gate |
| Source reports | Steps 3, 5, 6, 8, 9 in `docs/04_reports/r1_5/` |
| analysis_base_sha | 55a33ee |
