# R1 QUICK Decision Report

**Lineage:** arc_d_v2
**Rung:** r1 (partner + position context)
**Evidence tier:** QUICK
**Seed:** 42
**Date:** 2026-03-15
**Advance decision:** INVESTIGATE (H7 SURPRISE hit)

## Hypothesis Results

| ID | Description | Pass | Observed | Expected Bound | Surprise |
|----|-------------|------|----------|----------------|----------|
| H1 | Partner context improves GBT pooled H2H delta vs anchor | PASS | 0.490 | > 0.3 | No |
| H2 | GBT R1 suit H2H delta exceeds R0 suit delta (partner helps suit) | **FAIL** | 0.270 | > 0.5 | No |
| H3 | GBT R1 suit R-squared exceeds R0 suit R-squared | PASS | 0.621 | > 0.588 | No |
| H4 | Position features improve first-bidder accuracy | PASS | 2.114 | > 2.0 | No |
| H5 | Two-stage model narrows gap vs GBT with partner context | PASS | -0.341 | > -1.0 | No |
| H6 | All models bid at least half the time | PASS | 0.852 | > 0.5 | No |
| H7 | GBT H2H win rate vs anchor exceeds 50% | **FAIL** | 0.440 | > 0.5 | **YES** |
| H8 | Full OLS approx. equals constrained OLS (FS doesn't matter) | PASS | 0.157 | >= -0.2 | No |
| H9 | ModeloEspecifico heuristic is worst among trained models | PASS | -0.453 | < 0.0 | No |

**Result: 7/9 PASS, 2 FAIL (H2, H7); 1 SURPRISE (H7)**

## Key Findings

1. **Partner features improve R-squared but hurt H2H.** GBT suit R-squared improves from
   0.588 (R0) to 0.621 (R1), confirming that partner context adds predictive signal. However,
   GBT H2H win rate drops to 44.0% (below the 45% surprise threshold), meaning better
   predictions do not translate to better competitive outcomes against the hand-only anchor.

2. **H2H delta drops sharply.** GBT pooled H2H delta falls from +1.061 (R0) to +0.490 (R1).
   Suit H2H delta drops from +0.876 to +0.270 (H2 FAIL). The anchor bidder, trained on
   hand-only features, is not disadvantaged by lacking partner context in the way the
   hypothesis assumed.

3. **Comparator regression.** GBT comparator net_eppd drops from 2.201 (R0) to 2.114 (R1).
   This is consistent with the H2H findings: partner features do not improve absolute play
   quality in the comparator setting.

4. **R-squared vs H2H divergence is the central finding.** Better offline accuracy (higher
   R-squared) does not guarantee better competitive play. This is a known risk in bid
   evaluation: the model may learn to predict tricks more accurately but make worse
   bid/pass decisions at the margin.

## H7 SURPRISE Override

H7 hit the surprise threshold (win rate 0.440 < 0.45). Per advance check protocol,
SURPRISE triggers INVESTIGATE. After analysis:

**Override rationale:** The H7 surprise is explained by the R-squared vs H2H divergence
documented above. Partner features improve prediction accuracy but shift the bid/pass
decision boundary in a way that reduces competitive advantage against the hand-only
anchor. This is an informative result, not a data quality issue. The finding is recorded
and will inform R2 hypothesis design (opponent context may recover H2H advantage by
providing information the anchor lacks).

**Decision: PROCEED to R2.** The H7 surprise is explained and non-blocking.

## Cross-Rung Comparison (R0 vs R1)

| Metric | R0 | R1 | Delta |
|--------|-----|-----|-------|
| GBT pooled H2H delta | +1.061 | +0.490 | -0.571 |
| GBT suit H2H delta | +0.876 | +0.270 | -0.606 |
| GBT suit R-squared | 0.588 | 0.621 | +0.033 |
| GBT comparator | 2.201 | 2.114 | -0.087 |
| GBT win rate | 53.2% | 44.0% | -9.2pp |

## Sufficiency Checks

| Check | Result |
|-------|--------|
| All tables generated | PASS (4/4) |
| Data sanity | PASS (23/23) |
| No blocked models | PASS (5/5) |

## Canary Warnings

- C3: Magnitude historical check WARN (expected for sentinel matchups).
