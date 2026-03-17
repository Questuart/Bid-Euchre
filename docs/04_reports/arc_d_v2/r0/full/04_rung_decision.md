# R0 FULL — Rung Decision Report

**Lineage:** Arc D v2
**Rung:** R0 (baseline, full feature set)
**Mode:** FULL (50,000 deals × 3 seeds)
**Date:** 2026-03-17
**Provenance SHA:** `13ba62ee796891736b44b4bd5be380ab6b971938`

## Decision

**ADVANCE to R1.**

All 7 evaluated hypotheses pass. 2 hypotheses (H5, H8) are skipped because
`selected_ols_av` was trimmed from the FULL roster by LA-4. No surprise
thresholds triggered. All sufficiency checks (4/4 tables, 23/23 sanity, 5/5
models active) and canary checks (C1–C5) pass.

## Evidence Summary

### Comparator Rankings (pooled net_eppd)

| Model | net_eppd | 95% CI | Rank |
|-------|----------|--------|------|
| full_ols_av | 2.278 | [2.191, 2.365] | 1 |
| selected_two_stage_av | 1.962 | [1.869, 2.055] | 2 |
| gbt_av | 1.955 | [1.851, 2.058] | 3 |
| modeloespecifico | 1.633 | [1.517, 1.749] | 4 |

**Best in lineage:** `full_ols_av` at 2.278 net_eppd. This is consistent with
QUICK R0 where `full_ols_av` also ranked #1 at 2.256. The FULL estimate is
slightly higher (+0.022), well within CI overlap.

### GBT vs Anchor (Key H2H Results)

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H1 | suit delta | 0.727 | > 0.5 | PASS |
| H2 | pooled delta | 0.703 | > 0.3 | PASS |
| H3 | high delta | 0.716 | > 0.0 | PASS |
| H4 | low delta | 0.561 | >= -0.1 | PASS |
| H7 | win rate | 53.1% | > 50% | PASS |

GBT outperforms the anchor across all contract types and pooled, with a 53.1%
win rate. The H2H advantage is robust: the suit delta (0.727) exceeds its bound
by 0.227, and the pooled delta (0.703) exceeds its bound by 0.403.

### Behavioral Checks

| Hypothesis | Metric | Observed | Bound | Status |
|------------|--------|----------|-------|--------|
| H6 | min bid rate | 99.4% | > 50% | PASS |
| H9 | heuristic gap | -0.322 | < 0.0 | PASS |

No pathological passing detected. ModeloEspecifico is correctly the worst-ranked
learnable model (net_eppd 1.633 vs GBT 1.955), confirming the sanity ordering.

### Skipped Hypotheses

| Hypothesis | Reason |
|------------|--------|
| H5 | `selected_ols_av` not in FULL roster (LA-4 trim) |
| H8 | `selected_ols_av` not in FULL roster (LA-4 trim) |

These hypotheses compared GBT R² and two-stage regression against `selected_ols_av`,
which was trimmed from the FULL roster along with `constrained_ols_av`,
`stricthellraiser`, and `rankthetank` per Amendment LA-4. The comparisons are
not meaningful without the reference model. Both hypotheses will remain skipped
for all FULL rungs.

### Cross-Seed Stability

The seed sanity report flags 23 warnings across 3 seeds (42, 123, 456):
- **14 H2H seed outliers:** Expected with MAD-based outlier detection on 3 seeds.
  Small absolute differences — the largest is seed 42 with MAD=424.5x on
  `selected_two_stage_av_vs_gbt_av`, but the absolute delta range is
  [-0.933, -0.848], a spread of 0.085 net_eppd.
- **4 self-play sign flips:** All self-play deltas are near zero (expected), so
  sign flips are noise, not signal.
- **4 comparator outliers + 1 rank reversal:** `selected_two_stage_av` and
  `gbt_av` swap ranks between seeds 42 and 456 (gap: 0.007 net_eppd). This is
  expected given overlapping CIs [1.851, 2.058] vs [1.869, 2.055].

**Assessment:** Cross-seed variation is within expected bounds. The top model
(`full_ols_av`) is stable across all seeds. The rank reversal between #2 and #3
is not concerning given the 0.007 gap.

### QUICK → FULL Comparison

| Metric | QUICK (seed 42) | FULL (seeds 42,123,456) | Delta |
|--------|-----------------|-------------------------|-------|
| full_ols_av net_eppd | 2.256 | 2.278 | +0.022 |
| gbt_av net_eppd | 2.116 | 1.955 | -0.161 |
| GBT H2H win rate | 52.6% | 53.1% | +0.5pp |
| GBT pooled delta | +1.061 | +0.703 | -0.358 |

The ranking order is preserved at the top (`full_ols_av` #1) but shifts at
positions 2-3. GBT's H2H advantage vs anchor holds but its absolute comparator
score decreased. This is consistent with FULL training on 50k deals providing
more stable estimates than QUICK's single-seed 5k.

## Tail Risk

| Model | net_CVaR_5 |
|-------|------------|
| full_ols_av | -4.420 |
| selected_two_stage_av | -5.183 |
| gbt_av | -7.895 |
| modeloespecifico | -11.153 |

GBT has notably worse tail risk (-7.895) than `full_ols_av` (-4.420). This
pattern — GBT wins on average but has fatter tails — is a known characteristic
worth monitoring across rungs.

## Disposition

- **Advance check:** PROCEED (all evaluated checks pass)
- **Decision:** ADVANCE to R1
- **Best model carried forward:** `full_ols_av` (2.278 net_eppd)
- **Anchor for R1:** `anchor_hybrid_r0_full` (unchanged)
- **Watch items for R1:**
  - GBT tail risk gap vs OLS (CVaR spread = 3.475)
  - Rank stability of positions 2-3 (two-stage vs GBT overlap)
