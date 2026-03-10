# R1.5 Open Questions & Answers

**Source plan:** `plans/sessions/2026-03-09_r1-5-v2-diagnostic-plan.md`
**Last updated:** 2026-03-09

---

## Q1: Do R1.5's new features (52 vs R0's 39) explain the improvement?

**Status:** ANSWERED
**Phase:** 1 | **Step:** 3 (Cell A)

**Finding:** R^2 delta < 0.005 between R0 features (39) and full features (52)
on net_points target. Features are NOT a significant contributor to the R1.5
improvement. The 13 additional features (action features + state features)
add negligible predictive power once the objective and architecture changes
are accounted for.

---

## Q2: What is the relative contribution of objective vs dataset vs architecture?

**Status:** PARTIALLY ANSWERED
**Phase:** 1 | **Step:** 3 (Cells B'+C)

**Finding:** Feature ablation clean (Cell A). Objective effect proven via H2H:
Cell B' (tricks_won + AV architecture) bids 10 every hand, 1% make rate —
catastrophically worse than AV v1 and R0. Data+architecture effect confounded.
Option A R^2 comparison shows counterfactual data is WORSE for R0-style
predictions (suit R^2=0.084 vs 0.223 on bidless data). Data effect is negative;
architecture+objective alignment carry the improvement.

**Open:** Clean separation of architecture from objective alignment requires a
different experimental design (deferred to v3).

---

## Q3: Is the improvement from the objective (net_points) or the decision layer (argmax EV)?

**Status:** ANSWERED
**Phase:** 1 | **Step:** 3 (Cell B')

**Finding:** H2H proves objective matters. Cell B' (tricks_won target, same AV
architecture) bids 10 on every hand, gets set 99% of the time. The argmax
decision layer requires net_points target to function — tricks_won creates
perverse incentive (higher bid = higher predicted tricks, but ignores set
penalty). The decision layer and objective are tightly coupled: argmax over
tricks_won EV always prefers the highest bid level.

---

## Q4: What causes the suit regression (-0.142 net_eppd)?

**Status:** PARTIALLY ANSWERED (updated)
**Phase:** 1 | **Step:** 0

**Finding:** Suit has BEST R^2 (0.557 vs 0.525 high, 0.514 low). The suit
regression is NOT from poor model fit. Bimodality is universal across all
contracts. The suit deficit is likely a decision-layer interaction — suit's
steeper make/set cliff (bowers create binary outcomes) causes the between-mode
OLS prediction to produce worse bid decisions despite better predictions.
The two-stage decomposition (Phase 2) should isolate whether separating
P(make) from E[points|regime] fixes the suit decision quality.

---

## Q5: Is OLS linearity the problem, or missing features?

**Status:** ANSWERED
**Phase:** 3 | **Step:** 8

**No — OLS linearity is NOT the problem.**

Three interaction terms tested (bowers × trump_count, trump_count², bowers²):
- R² delta < 0.001 for all contracts (suit: -0.0001, high: +0.0001, low: +0.0004)
- H2H: interaction vs AV v1 = +0.002 pts/deal (noise)
- H2H: interaction vs R0 = +0.165 (identical to AV v1 vs R0)

The suit regression (-0.142 net_eppd) is structural: OLS predicts the mean of
a bimodal make/set distribution, producing suboptimal bid decisions. Feature
engineering cannot fix this — the problem is in the target distribution, not the
feature space.

Evidence: data/runs/r1_5_v2_interaction_h2h_42_20260310_160346/

---

## Q6: Is the deficit at the prediction level or the decision level?

**Status:** PLANNED
**Phase:** 1 | **Step:** 0

Partially addressed by diagnostics: suit has the best R^2, so prediction
quality is not the bottleneck. Full prediction-vs-decision isolation requires
comparing calibration-adjusted predictions against raw predictions in H2H.

---

## Q7: Why does AV v1 only bid at level 4?

**Status:** ANSWERED
**Phase:** — | **Step:** — (diagnostic only)

**Finding:** AV v1 ALWAYS bids at level 4, never above. The model's predicted
net_points for bid_n > 4 are negative due to the quadratic bid_n_sq term
creating a concave EV curve. The argmax over bid levels always selects
bid_n=4 as the maximum of this concave curve, regardless of hand strength.

---

## Q8: Is AV v1 bidding quantity over quality?

**Status:** PLANNED (diagnostic only)
**Phase:** — | **Step:** —

Not directly blocking. Related to Q7 — the level-4-only bidding pattern
means AV v1 never explores higher bid levels even when hand strength warrants it.

---

## Q9: Can the pass boundary be calibrated?

**Status:** PLANNED
**Phase:** — | **Step:** —

Addressed if two-stage decomposition fixes pass rate. Currently AV v1 has
near-zero pass rate (0.007%).

---

## Q10: Is contract-type balance an issue in training data?

**Status:** ANSWERED
**Phase:** 1 | **Step:** 1

**Finding:** suit=65.3%, high=16.3%, low=16.3%, pass=2.1% in training data.
Suit is overrepresented (continuation policy bids suit most often), not
underrepresented. The suit regression is not a data balance issue — suit has
the most training data AND the best R^2.

---

## Q11: How sensitive are results to dataset size?

**Status:** DEFERRED
**Phase:** — | **Step:** —

Deferred to FULL retraining in Phase 2. Current QUICK-scale (2,500 deals)
results are sufficient for diagnostic purposes.

---

## Q12: Do partner features contribute?

**Status:** ANSWERED
**Phase:** 1 | **Step:** 7b

**Yes — partner features are the single most valuable component of AV v1.**

R² shows near-zero contribution for suit/high/low (delta < 0.005), but pass R²
drops from 0.046 to 0.005 without partner context. In H2H gameplay:
- AV v1 vs R0: **+0.224** pts/deal
- No-partner vs R0: **-0.492** pts/deal (worse than R0)
- No-partner vs AV v1: **-0.752** pts/deal

Partner features don't improve *prediction accuracy* for a given action, but
they critically improve *action selection* — particularly pass decisions. Without
partner context, the bidder's pass model degrades to near-random.

Evidence: data/runs/r1_5_v2_partner_ablation_h2h_42_20260310_130936/

---

## Q13: How does AV v1 compare to R1 HybridOLSa?

**Status:** DEFERRED
**Phase:** — | **Step:** —

Deferred — add R1 to the comparison roster in Phase 2 if needed.

---

## Q14: Does bimodality in net_points drive the suit regression?

**Status:** HYPOTHESIS STRENGTHENED
**Phase:** 1+2 | **Steps:** 1, 4-6

**Finding:** Bimodality confirmed as universal (GMM BIC: suit=4,081,
high=1,469, low=1,286). All R1.5 contracts show strong bimodal residuals.
R0 high/low are unimodal (tricks_won is naturally unimodal). This strongly
supports the two-stage regime decomposition approach for Phase 2.

The target variable itself is strongly bimodal in all contracts (training data
GMM BIC: suit=249,573, high=58,648, low=57,949). The OLS model inherits this
bimodality in its residuals because it predicts the mean of the bimodal
distribution. Phase 2 go/no-go gate: conditional evidence needed (per-regime
R^2 improvement after declare/defend split).

---

## Q15: What do cross-rung calibration diagnostics reveal?

**Status:** ANSWERED
**Phase:** 1 | **Step:** 0

**Finding:** Calibration diagnostics generated (18 charts + summary JSON in
`data/reports/arc_d/r1_5_v2/diagnostics/`). R1.5 predictions show systematic
positive bias (mean residual ~0.1 for all contracts) and bimodal residual
clusters. R0 predictions are well-calibrated (mean residual approximately 0).
The qualitative calibration patterns differ fundamentally: R1.5 has
heteroscedastic bimodal residuals, R0 has near-homoscedastic unimodal
residuals.

See `docs/04_reports/r1_5/diagnostic_calibration.md` for the full report.

---

## Q16: Should the two-stage model use two levels or three?

**Status:** PLANNED
**Phase:** 1 | **Step:** 0-1 diagnostics inform

Investigate during Phase 1 diagnostics. The declare/defend split is two-level;
a three-level split (declare-make, declare-set, defend) may be more
appropriate if the declare regime itself is bimodal.

---

## Q17: Should we try quantile regression or Huber loss?

**Status:** RESOLVED
**Phase:** — | **Step:** —

Resolved: wrong loss function for an EV-based decision rule. The argmax
decision layer requires mean predictions (EV), not quantile or robust
estimates. Quantile regression optimizes for a different objective than
the decision layer needs.

---

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — diagnostic Q&A log, no formal gate |
| Source reports | `docs/04_reports/r1_5/diagnostic_calibration.md`, Steps 3, 5, 6, 8, 9 in `docs/04_reports/r1_5/` |
| Diagnostic data | data/reports/arc_d/r1_5_v2/diagnostics/diagnostic_summary.json (18 charts + JSON, gitignored) |
| Ablation artifacts | Cell A: `data/runs/cell_a_r0_features_42/action_value_r0_features.json`, Cell B': `data/runs/action_value_quick_42_v2/action_value_full.json` |
| Ablation H2H run | `data/runs/r1_5_v2_ablation_h2h_42_20260309_202431/` (9 matchups, seed=42, n=2500) |
| Option A data | Inline R² calculation on `data/runs/action_value_quick_42_v2/datasets/action_value.parquet` (collapsed to bidless format, R0 CONTRACT_FEATURES, seed=42) |
| Dataset v2 | `data/runs/action_value_quick_42_v2/datasets/action_value.parquet` (468,388 rows, with tricks_won + focal_declared) |
| analysis_base_sha | 113d77a |
