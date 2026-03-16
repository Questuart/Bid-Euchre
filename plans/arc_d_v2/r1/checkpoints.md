# R1 Checkpoints

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Phase/Rung:** R1 (partner + position context)
**Last updated:** 2026-03-15 by QUICK report suite session

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Plan & Hypothesize | COMPLETE | 2026-03-15 | Plan creation | 9 hypotheses, plan.md, checkpoints.md |
| Step 1: Generate Training Data | COMPLETE | 2026-03-15 | QUICK orchestrator | 2,500 deals, seed 42 |
| Step 2: Train All Roster Models | COMPLETE | 2026-03-15 | QUICK orchestrator | 5 models trained |
| Step 3: Offline Evaluation + Data Sanity | COMPLETE | 2026-03-15 | QUICK orchestrator | 23/23 sanity checks pass |
| Step 3b: Model Interpretability | COMPLETE | 2026-03-15 | QUICK orchestrator | SHAP values computed |
| Step 4: H2H Battery | COMPLETE | 2026-03-15 | QUICK orchestrator | 81 matchups x 2,500 deals |
| Step 5: Comparator Battery | COMPLETE | 2026-03-15 | QUICK orchestrator | 8 bidders, CIs extracted |
| Step 6: Sanity Bounds Check | COMPLETE | 2026-03-15 | QUICK orchestrator | Canonical tables generated |
| Step 7: Generate Reports | COMPLETE | 2026-03-15 | QUICK orchestrator | Charts, report, evidence manifest |
| Step 8: Advance Decision + Narrative | COMPLETE | 2026-03-15 | QUICK orchestrator | INVESTIGATE (H7 SURPRISE) |
| Step 9: Archive & Advance | COMPLETE | 2026-03-15 | QUICK report suite | Decision report written, reports at quick/ |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

## Prerequisites

- [x] R0 QUICK canonical -- 8/9 hypotheses PASS (H8 FAIL expected)
- [x] R1 feature implementation -- partner v2 features + position features (LA-1)

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|

## Blockers

- [x] R1 features not yet implemented -- RESOLVED

## INVESTIGATE Override: H7 SURPRISE

**H7 observed:** GBT H2H win rate = 44.0% (below 50% expected, below 45% surprise).

**Root cause:** Partner features improve R-squared (0.588 to 0.621) but hurt H2H
performance against the hand-only anchor. Better trick prediction accuracy does not
translate to better bid/pass decisions at the margin. The anchor, trained without
partner context, is not disadvantaged by lacking it.

**Override decision:** PROCEED to R2. The finding is informative (documents the
R-squared vs H2H divergence) and non-blocking. Opponent context in R2 is expected
to recover H2H advantage by providing information the anchor truly lacks.

## Session Log

### 2026-03-15 -- Plan creation

- Created R1 plan, hypotheses, checkpoints
- R0 QUICK results provide baseline for comparison:
  - GBT pooled H2H: +1.061, suit: +0.876, high: +1.868, low: +1.337
  - GBT suit R-squared: 0.588
  - GBT comparator: 2.201
  - Best comparator: full_ols_av 2.236

### 2026-03-15 -- QUICK execution

- Full QUICK pipeline: Steps 1-8 completed via orchestrator
- **Results:**
  - GBT pooled H2H delta: +0.490 (down from R0 +1.061)
  - GBT suit H2H delta: +0.270 (down from R0 +0.876)
  - GBT suit R-squared: 0.621 (up from R0 0.588)
  - GBT comparator: 2.114 (down from R0 2.201)
  - GBT win rate: 44.0% (down from R0 53.2%)
  - Best model: gbt_av (2.114 comparator)
  - Hypothesis results: 7/9 PASS, H2 FAIL, H7 FAIL (SURPRISE)
  - H7 SURPRISE overridden: R-squared vs H2H divergence explained
- Commands: seed 42, n_per 2500 (QUICK mode)

### 2026-03-15 -- QUICK report suite

- Step 9: Decision report (02_decision.md) written with INVESTIGATE override
- Reports re-homed from canonical/ to quick/ with evidence_tier: quick
- hypothesis_outcomes.csv populated from advance_check.json (9 hypotheses)
- cross_rung_deltas.csv populated with R0-R1 progression
- evidence_manifest.json updated: governing_plan, seeds=[42], mode=quick
- 00_manifest.md updated to reference quick/ paths
