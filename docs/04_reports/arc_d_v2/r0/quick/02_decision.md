# R0 QUICK Decision Report

**Lineage:** arc_d_v2
**Rung:** r0 (hand-only context, action-value framework)
**Evidence tier:** QUICK
**gate_status:** QUICK-COMPLETE (directional evidence — not a promotion gate)
**Seed:** 42
**Date:** 2026-03-15
**Advance decision:** INVESTIGATE (H8 failed)

## Hypothesis Results

| ID | Description | Pass | Observed | Expected Bound | Surprise |
|----|-------------|------|----------|----------------|----------|
| H1 | GBT outperforms anchor on suit contract delta (H2H) | PASS | 0.876 | > 0.5 | No |
| H2 | GBT outperforms anchor on pooled net_eppd (H2H) | PASS | 1.061 | > 0.3 | No |
| H3 | GBT high-contract delta is positive vs anchor (H2H) | PASS | 1.868 | > 0.0 | No |
| H4 | GBT low-contract delta is non-negative vs anchor (H2H) | PASS | 1.337 | >= -0.1 | No |
| H5 | GBT suit R-squared exceeds selected OLS suit R-squared | PASS | 0.034 | > 0.0 | No |
| H6 | All models bid at least half the time | PASS | 0.911 | > 0.5 | No |
| H7 | GBT H2H win rate vs anchor exceeds 50% | PASS | 0.532 | > 0.5 | No |
| H8 | Two-stage model does not regress vs selected OLS on pooled net_eppd | **FAIL** | -0.315 | >= -0.2 | No |
| H9 | ModeloEspecifico heuristic is worst on pooled net_eppd (sanity) | PASS | -0.540 | < 0.0 | No |

**Result: 8/9 PASS, 1 FAIL (H8)**

## Key Findings

1. **GBT is the dominant model.** GBT achieves the highest suit R-squared (0.588) and
   best H2H performance vs the anchor (+1.061 pooled, 53.2% win rate). The action-value
   framework successfully translates offline accuracy into competitive advantage.

2. **OLS variants cluster together.** full_ols_av (2.236), constrained_ols_av (2.198),
   and selected_ols_av (2.194) are statistically indistinguishable in the comparator
   battery. Feature selection does not materially differentiate OLS performance.

3. **Two-stage model underperforms.** selected_two_stage_av achieves only 1.879 in the
   comparator battery, regressing -0.315 vs selected_ols_av (H8 FAIL). The two-stage
   architecture does not benefit from the action-value framework at R0 feature depth.

4. **Best comparator model is full_ols_av** (2.236), slightly above GBT (2.201). This
   divergence between comparator ranking and H2H ranking is expected: comparator measures
   absolute play quality against GluttonStrategy, while H2H measures relative advantage
   against the anchor bidder.

## Advance Decision: INVESTIGATE

H8 failure (two-stage regression) triggers INVESTIGATE per the advance check protocol.
This is non-blocking for lineage progression: the two-stage model is an experimental
variant, not the promotion candidate. GBT and OLS models all pass their hypotheses.

**Recommendation:** Proceed to R1 (partner + position context). The H8 finding is
noted but does not affect the primary GBT promotion path.

## Sufficiency Checks

| Check | Result |
|-------|--------|
| All tables generated | PASS (4/4) |
| Data sanity | PASS (23/23) |
| No blocked models | PASS (5/5) |

## Canary Warnings

- C3: Magnitude historical check WARN (pooled delta > 5.0 for some sentinel matchups).
  Expected for rankthetank pathological bidding.
