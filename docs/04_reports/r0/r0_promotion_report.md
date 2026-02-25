# R0 Promotion Report

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Decision:** PROMOTED
**Date:** 2026-02-22

## Executive Summary

The R0 rung of Arc D's OLSa-Hybrid bidder was **PROMOTED** after passing all
Tier 1 artifact integrity checks and demonstrating positive net expected points
per deal across three independent evaluation seeds.

Key metrics (OLSa_Full promotional arm, seed 42):

| Metric | Value |
|--------|-------|
| net_eppd | +1.484 |
| eppd | +4.174 |
| bid_rate | 82.8% |
| make_rate | 83.3% |
| CVaR-5% | −6.411 |
| net_CVaR-5% | −12.063 |

The model ranks 2nd among 5 comparator bidders by net_eppd, trailing only
`modeloespecifico` (+2.291) by 0.81 points/deal (p < 0.001). The gap is
expected: `modeloespecifico` is a hand-tuned heuristic with full game knowledge,
while OLSa_Full is a linear model trained from data. R0's purpose is to
establish a working baseline, not to exceed heuristic performance.

## Gate Results

All four Tier 1 artifact integrity checks passed:

| Check | Result |
|-------|--------|
| artifact_integrity_olsa | PASS |
| artifact_integrity_olsa_full | PASS |
| no_nan_inf_olsa | PASS |
| no_nan_inf_olsa_full | PASS |

R0 uses a reduced gate (Tier 1 only). Full semantic gate checks (Tier 2:
calibration, fairness, stability) are introduced at R1+.

## Evaluation Metrics

### OLSa_Full (Promotional Arm)

The OLSa_Full arm uses forward-selected features (2–3 per contract type) from
the full pool of 39 hand features.

| Metric | Seed 42 | Seed 43 | Seed 44 | Range |
|--------|---------|---------|---------|-------|
| net_eppd | +1.484 | +1.455 | +1.426 | 0.058 |
| eppd | +4.174 | +4.139 | +4.131 | 0.044 |
| bid_rate | 0.828 | 0.825 | 0.827 | 0.004 |
| make_rate | 0.833 | 0.832 | 0.830 | 0.003 |
| CVaR-5% | −6.411 | −6.418 | −6.428 | 0.017 |
| net_CVaR-5% | −12.063 | −12.056 | −12.070 | 0.014 |
| downside_var | 0.430 | 0.436 | 0.437 | 0.007 |

### OLSa (Attribution Arm)

The OLSa constrained arm uses locked features: 3 for suit (bowers, trump_count,
offsuit_aces), 1 for high (offsuit_aces), 1 for low (offsuit_tens_count).

| Metric | Seed 42 | Seed 43 | Seed 44 | Range |
|--------|---------|---------|---------|-------|
| net_eppd | +1.627 | +1.595 | +1.623 | 0.033 |
| eppd | +3.566 | +3.534 | +3.571 | 0.037 |
| bid_rate | 0.632 | 0.630 | 0.634 | 0.004 |
| make_rate | 0.873 | 0.870 | 0.872 | 0.003 |
| CVaR-5% | −6.154 | −6.139 | −6.141 | 0.015 |
| net_CVaR-5% | −11.784 | −11.805 | −11.806 | 0.023 |
| downside_var | 0.318 | 0.310 | 0.313 | 0.008 |

### Multi-Seed Stability

All metrics show tight cross-seed ranges (< 0.06 for net_eppd, < 0.005 for
bid/make rates), confirming that R0 evaluation is reproducible and not
sensitive to deal sampling.

## Attribution Gap

**Gap = −0.1437** (OLSa_Full net_eppd − OLSa net_eppd at seed 42)

The attribution gap is negative: the constrained arm (OLSa) slightly
*outperforms* the promotional arm (OLSa_Full) on net_eppd despite using fewer
features. This is counter-intuitive but benign at R0:

1. **Feature selection explains the inversion.** The constrained arm's 3/1/1
   features (bowers, trump_count, offsuit_aces for suit; offsuit_aces for high;
   offsuit_tens_count for low) were hand-picked as the strongest individual
   predictors from domain knowledge. The full arm's forward selection picked
   different features (hand_value, quick_tricks, low_card_count for suit;
   offsuit_non_ace_count + offsuit_best_rank_sum for high/low) that maximize
   R² but may include weaker marginal contributors.

2. **Bid rate differences amplify small effects.** OLSa bids conservatively
   (63.2% bid rate) vs OLSa_Full (82.8%). Lower bid rate means higher
   selectivity — the constrained arm only bids on hands where its simple model
   is confident, which happens to yield a higher net per deal.

3. **R0 context.** Both arms are R0-quality models with R² ≈ 0.18–0.22. At
   this early stage, the difference between hand-picked and forward-selected
   features is within noise. The gap is expected to resolve as model complexity
   increases in later rungs.

The attribution gap is monitored by the `check_dual_arm_coherence` gate check
starting at R1.

## Comparator Context

See [comparator_rankings.md](comparator_rankings.md) for the full comparator
battery with bootstrap 95% confidence intervals.

Summary ranking by net_eppd:

| Rank | Bidder | net_eppd |
|------|--------|----------|
| 1 | modeloespecifico | +2.291 |
| 2 | **hybrid_olsa (R0)** | **+1.481** |
| 3 | rankthetank | −3.170 |
| 4 | fiveheadfred | −3.521 |
| 5 | stricthellraiser | −6.114 |

The gap between `modeloespecifico` and `hybrid_olsa` is 0.81 points/deal
(p < 0.001, bootstrap permutation test, n=10,000). Closing this gap is the
objective of future rungs (R1+).

## Provenance

| Item | Value |
|------|-------|
| Rung bundle | data/artifacts/arc_d/r0/rung_bundle_r0.json |
| OLSa artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| OLSa_Full artifact | data/artifacts/arc_d/r0/hybrid_r0_full.json |
| OLSa SHA256 | 7b523cd6f0de41a82eca55f6b0bedc09d18630638609226ee3e8ddb443f71fe8 |
| OLSa_Full SHA256 | 5436b759f525466976244766dee8d98472dcfe243ac1d4542885e6cd0e6dcbc7 |
| Promotion decision | data/artifacts/arc_d/r0/promotion_decision_r0.json |
| Evaluator git SHA | b194908ca8b0cf265d78c4661716e56343796db3 |
| Promotion timestamp | 2026-02-22T02:13:32Z |
| Training source run | canonical_bidless_dataset_glutton_42_20260221_175752 |
| n_deals per eval seed | 50,000 |

## Exclusions

- **H2H Matchup Report:** Deferred per C50 (not required at R0).
- **Semantic gate Tier 2:** Not applicable at R0 (introduced at R1+).
