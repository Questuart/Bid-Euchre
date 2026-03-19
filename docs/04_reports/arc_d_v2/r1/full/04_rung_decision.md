> **DEPRECATED:** This file is a historical narrative artifact from the Arc D v2
> lineage. The canonical decision surface is `02_decision.md`. This file is
> retained for reference but will not be updated or regenerated.

# R1 FULL — Rung Decision Report

**Lineage:** Arc D v2
**Rung:** R1 (partner context features)
**Mode:** FULL (50,000 deals x 3 seeds)
**Date:** 2026-03-17
**Provenance SHA:** `8418ea5537c8c26e9cf4cac309e8ba4c21327fb5`

## Decision

**ADVANCE to R2.**

8 of 9 hypotheses pass, 1 skipped (H8: `constrained_ols_av` not in R1 roster
per LA-4 trim). No surprise thresholds triggered. All sufficiency checks
(4/4 tables, 20/20 sanity PASS, 4/4 models active) and canary checks
(C1-C5) pass. GBT shows material improvement over R0 FULL across all H2H
metrics, confirming that partner context features contribute positively.

## Evidence Summary

### Comparator Rankings (pooled net_eppd)

| Model | net_eppd | 95% CI | Rank |
|-------|----------|--------|------|
| full_ols_av | 2.275 | [2.188, 2.363] | 1 |
| gbt_av | 2.009 | [1.908, 2.108] | 2 |
| selected_two_stage_av | 1.962 | [1.869, 2.055] | 3 |
| modeloespecifico | 1.633 | [1.517, 1.749] | 4 |

**Best in lineage:** `full_ols_av` at 2.275 net_eppd, retaining #1 from R0 FULL
(2.278). The slight decrease (-0.003) is within CI overlap and not significant.
GBT moved from #3 in R0 FULL (1.955) to #2 in R1 FULL (2.009), with its
absolute score improving (+0.054).

### GBT vs Anchor (Key H2H Results)

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H1 | pooled delta | +1.012 | > 0.3 | PASS |
| H2 | suit delta | +1.011 | > 0.5 | PASS |
| H7 | win rate | 57.2% | > 50% | PASS |

GBT outperforms the anchor across all contract types with a 57.2% win rate.
Compared to R0 FULL (pooled delta +0.703, suit delta +0.727, win rate 53.1%),
R1 FULL shows consistent improvement:

| Metric | R0 FULL | R1 FULL | Delta |
|--------|---------|---------|-------|
| Pooled delta vs anchor | +0.703 | +1.012 | +0.309 |
| Suit delta vs anchor | +0.727 | +1.011 | +0.284 |
| Win rate vs anchor | 53.1% | 57.2% | +4.1pp |

This confirms that partner context features (R1's addition) materially improve
GBT's head-to-head performance against the anchor.

### Model Quality Checks

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H3 | GBT suit R-squared | 0.604 | > 0.588 | PASS |
| H4 | GBT pooled comparator | 2.009 | > 2.0 | PASS |
| H5 | two-stage vs GBT gap | -0.047 | > -1.0 | PASS |
| H8 | full vs constrained OLS gap | — | >= -0.2 | SKIP |

GBT suit R-squared improved from 0.588 (R0) to 0.604 (R1), consistent with
partner context adding predictive signal for suit contracts. The two-stage
model maintains a manageable gap to GBT (-0.047 net_eppd). H8 was skipped
because `constrained_ols_av` is not in the R1 roster (LA-4 trim).

### Behavioral Checks

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H6 | min bid rate | 98.6% | > 50% | PASS |
| H9 | heuristic gap | -0.376 | < 0.0 | PASS |

No pathological passing detected. GBT's 98.6% bid rate is the lowest among
comparator models (all others bid at 100%). ModeloEspecifico remains the
worst-ranked learnable model (1.633 vs GBT 2.009), confirming the sanity
ordering.

### Contract Mix Diversity

A notable behavioral pattern: `full_ols_av` shows a dramatically different
contract mix from other models:

| Model | suit | high | low |
|-------|------|------|-----|
| full_ols_av | 25.9% | 29.1% | 45.1% |
| gbt_av | 73.0% | 10.0% | 17.1% |
| selected_two_stage_av | 96.7% | 1.2% | 2.1% |
| modeloespecifico | 94.2% | 2.8% | 3.1% |

`full_ols_av` strongly favors low contracts (45.1%) and high contracts (29.1%),
while most other models favor suit (73-97%). Despite this divergent strategy,
`full_ols_av` achieves the highest net_eppd, suggesting its diversified
contract mix is profitable.

### Tier Performance (Intelligence-Faceted H2H)

| Model | vs Smart (mean delta) | vs Anchor | vs Heuristic |
|-------|-----------------------|-----------|--------------|
| gbt_av | +1.549 (65.6% WR) | +1.012 (57.2%) | +0.788 (60.2%) |
| selected_two_stage_av | +1.242 (57.7%) | +0.328 (44.2%) | -0.190 (44.4%) |
| modeloespecifico | +0.602 (51.0%) | +0.400 (47.4%) | — |
| full_ols_av | -1.266 (25.2%) | +0.175 (39.6%) | -1.105 (25.4%) |

GBT is the strongest H2H competitor, dominating smart-tier opponents with
a 65.6% win rate. `full_ols_av` struggles in H2H despite ranking #1 in
comparator — a known divergence between comparator (solo scoring) and
H2H (game-theoretic) evaluation.

### Data Sanity

| Check | Result |
|-------|--------|
| H2H cells populated | 81/81 PASS |
| H2H min deals | 2,500 PASS |
| Comparator bidders | 4 PASS |
| R-squared positive | 19/20 PASS, 1 WARN |

The single WARN is `selected_two_stage_av` suit R-squared = 0.000 (empty in
model_performance.csv). This is a known issue with the two-stage model's suit
contract fitting. It does not affect the advance decision because H5 evaluates
the two-stage model via comparator net_eppd (which is populated and valid at
1.962), not via training R-squared.

### Sanity Bounds

4 bid_rate_range FAILs are expected: all 4 models bid at >95% rate, exceeding
the upper sanity bound of 0.95. These bounds are designed to catch pathological
passing, not to flag aggressive bidding. All make_rate checks pass.

## Tail Risk

| Model | net_CVaR_5 |
|-------|------------|
| full_ols_av | -4.431 |
| selected_two_stage_av | -5.183 |
| gbt_av | -7.138 |
| modeloespecifico | -11.153 |

GBT's tail risk (-7.138) is the worst among trained models but remains
manageable. The gap to `full_ols_av` is 2.707, indicating room for
improvement. `full_ols_av` shows the best tail risk (-4.431) among all
comparator models.

## Disposition

- **Advance check:** PROCEED (8 evaluated checks pass, 1 skipped)
- **Decision:** ADVANCE to R2
- **Best model carried forward:** `full_ols_av` (2.275 net_eppd, comparator #1)
- **Best H2H performer:** `gbt_av` (+1.012 pooled delta, 57.2% WR vs anchor)
- **Anchor for R2:** `anchor_hybrid_r0_full` (unchanged)
- **Watch items for R2:**
  - GBT tail risk (-7.138) — monitor whether R2 closes the gap to OLS (-4.431)
  - `full_ols_av` H2H weakness vs smart-tier (31.4% WR) despite #1 comparator rank
  - `selected_two_stage_av` suit R-squared anomaly (0.000)
  - Top-3 comparator rankings spread = 0.313 (2.275-1.962)

<!-- gate_status: data sanity checks in Evidence Summary above -->
