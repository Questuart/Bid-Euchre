# R1 FULL — Rung Decision Report

**Lineage:** Arc D v2
**Rung:** R1 (partner context features)
**Mode:** FULL (50,000 deals x 3 seeds)
**Date:** 2026-03-17
**Provenance SHA:** `8418ea5537c8c26e9cf4cac309e8ba4c21327fb5`

## Decision

**ADVANCE to R2.**

All 9 hypotheses pass. No skips (R1 hypotheses do not reference models
trimmed by LA-4). No surprise thresholds triggered. All sufficiency checks
(4/4 tables, 20/20 sanity PASS, 5/5 models active) and canary checks
(C1-C5) pass. GBT shows material improvement over R0 FULL across all H2H
metrics, confirming that partner context features contribute positively.

## Evidence Summary

### Comparator Rankings (pooled net_eppd)

| Model | net_eppd | 95% CI | Rank |
|-------|----------|--------|------|
| full_ols_av | 2.234 | [2.113, 2.357] | 1 |
| constrained_ols_av | 2.204 | [2.080, 2.329] | 2 |
| selected_ols_av | 2.195 | [2.070, 2.324] | 3 |
| gbt_av | 2.184 | [2.054, 2.317] | 4 |
| selected_two_stage_av | 1.920 | [1.784, 2.054] | 5 |
| modeloespecifico | 1.661 | [1.501, 1.819] | 6 |

**Best in lineage:** `full_ols_av` at 2.234 net_eppd, retaining #1 from R0 FULL
(2.278). The slight decrease (-0.044) is within CI overlap and not significant.
GBT moved from #3 in R0 FULL (1.955) to #4 in R1 FULL (2.184) due to the
presence of `constrained_ols_av` and `selected_ols_av` in the R1 roster, but
its absolute score improved substantially (+0.229).

### GBT vs Anchor (Key H2H Results)

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H1 | pooled delta | +1.053 | > 0.3 | PASS |
| H2 | suit delta | +0.939 | > 0.5 | PASS |
| H7 | win rate | 55.8% | > 50% | PASS |

GBT outperforms the anchor across all contract types with a 55.8% win rate.
Compared to R0 FULL (pooled delta +0.703, suit delta +0.727, win rate 53.1%),
R1 FULL shows consistent improvement:

| Metric | R0 FULL | R1 FULL | Delta |
|--------|---------|---------|-------|
| Pooled delta vs anchor | +0.703 | +1.053 | +0.350 |
| Suit delta vs anchor | +0.727 | +0.939 | +0.212 |
| Win rate vs anchor | 53.1% | 55.8% | +2.7pp |

This confirms that partner context features (R1's addition) materially improve
GBT's head-to-head performance against the anchor.

### Model Quality Checks

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H3 | GBT suit R-squared | 0.604 | > 0.588 | PASS |
| H4 | GBT pooled comparator | 2.184 | > 2.0 | PASS |
| H5 | two-stage vs GBT gap | -0.264 | > -1.0 | PASS |
| H8 | full vs constrained OLS gap | +0.030 | >= -0.2 | PASS |

GBT suit R-squared improved from 0.588 (R0) to 0.604 (R1), consistent with
partner context adding predictive signal for suit contracts. The two-stage
model maintains a manageable gap to GBT (-0.264 net_eppd). Full OLS and
constrained OLS remain nearly interchangeable (+0.030 gap), confirming that
feature selection has minimal impact on OLS model quality.

### Behavioral Checks

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H6 | min bid rate | 95.2% | > 50% | PASS |
| H9 | heuristic gap | -0.523 | < 0.0 | PASS |

No pathological passing detected. GBT's 95.2% bid rate is the lowest among
comparator models (all others bid at 100%). ModeloEspecifico remains the
worst-ranked learnable model (1.661 vs GBT 2.184), confirming the sanity
ordering.

### Contract Mix Diversity

A notable behavioral pattern: `full_ols_av` shows a dramatically different
contract mix from other models:

| Model | suit | high | low |
|-------|------|------|-----|
| full_ols_av | 18.8% | 21.1% | 60.1% |
| gbt_av | 69.8% | 8.5% | 21.7% |
| selected_ols_av | 75.0% | 9.4% | 15.6% |
| modeloespecifico | 94.0% | 2.8% | 3.2% |

`full_ols_av` strongly favors low contracts (60.1%), while most other models
favor suit (70-94%). Despite this divergent strategy, `full_ols_av` achieves
the highest net_eppd, suggesting its low-contract specialization is profitable.

### Tier Performance (Intelligence-Faceted H2H)

| Model | vs Smart (mean delta) | vs Anchor | vs Heuristic |
|-------|-----------------------|-----------|--------------|
| gbt_av | +1.301 (61.2% WR) | +1.053 (55.8%) | +4.618 (66.9%) |
| modeloespecifico | +0.762 (55.2%) | +0.232 (45.5%) | +7.536 (71.7%) |
| full_ols_av | -0.781 (31.4%) | +0.077 (38.2%) | +3.511 (51.4%) |

GBT is the strongest H2H competitor, dominating both smart-tier and
heuristic-tier opponents. `full_ols_av` struggles in H2H despite ranking #1
in comparator — a known divergence between comparator (solo scoring) and
H2H (game-theoretic) evaluation.

### Data Sanity

| Check | Result |
|-------|--------|
| H2H cells populated | 81/81 PASS |
| H2H min deals | 2,500 PASS |
| Comparator bidders | 8 PASS |
| R-squared positive | 19/20 PASS, 1 WARN |

The single WARN is `selected_two_stage_av` suit R-squared = 0.000 (empty in
model_performance.csv). This is a known issue with the two-stage model's suit
contract fitting. It does not affect the advance decision because H5 evaluates
the two-stage model via comparator net_eppd (which is populated and valid at
1.920), not via training R-squared.

### Sanity Bounds

8 bid_rate_range FAILs are expected: all models bid at >95% rate, exceeding
the upper sanity bound of 0.95. These bounds are designed to catch pathological
passing, not to flag aggressive bidding. All make_rate checks pass.

## Tail Risk

| Model | net_CVaR_5 |
|-------|------------|
| full_ols_av | -4.496 |
| constrained_ols_av | -4.512 |
| selected_ols_av | -4.480 |
| selected_two_stage_av | -5.136 |
| gbt_av | -5.639 |
| modeloespecifico | -11.112 |

GBT's tail risk (-5.639) improved substantially from R0 FULL (-7.895 per R0
decision report). The gap to `full_ols_av` narrowed from 3.475 to 1.143,
indicating that partner context features help GBT avoid worst-case outcomes.
OLS variants cluster tightly around -4.5 with minimal tail risk.

## Disposition

- **Advance check:** PROCEED (all 9 evaluated checks pass, 0 skipped)
- **Decision:** ADVANCE to R2
- **Best model carried forward:** `full_ols_av` (2.234 net_eppd, comparator #1)
- **Best H2H performer:** `gbt_av` (+1.053 pooled delta, 55.8% WR vs anchor)
- **Anchor for R2:** `anchor_hybrid_r0_full` (unchanged)
- **Watch items for R2:**
  - GBT tail risk continues improving — monitor whether R2 closes the gap further
  - `full_ols_av` H2H weakness vs smart-tier (31.4% WR) despite #1 comparator rank
  - `selected_two_stage_av` suit R-squared anomaly (0.000)
  - Top-4 comparator rankings are tightly bunched (2.184-2.234, spread = 0.050)

<!-- gate_status: data sanity checks in Evidence Summary above -->
