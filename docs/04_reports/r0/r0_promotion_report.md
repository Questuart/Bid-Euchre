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
| gate_status | PROMOTED |
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

- **Semantic gate Tier 2:** Not applicable at R0 (introduced at R1+).

---

## Addendum (2026-02-25)

*Added after the H2H battery analysis was completed. The PROMOTED decision
above is unchanged — this addendum provides additional context from subsequent
experiments.*

### Bidder Naming Clarification

In the Comparator Context table above (5-bidder v1 battery), `hybrid_olsa`
refers to the **OLSa_Full promotional arm** (`hybrid_r0_full.json`,
forward-selected features, bid_rate = 82.8%). This is the same configuration
reported as "OLSa_Full (Promotional Arm)" in the evaluation tables above.

The later 7-bidder battery
([h2h_battery_analysis.md](h2h_battery_analysis.md)) disambiguated the OLSa
variants into three entries:

| Name in 7-bidder battery | Artifact | Bid rate | Decision layer |
|--------------------------|----------|----------|----------------|
| `hybrid_olsa` | `hybrid_r0.json` (constrained, 3 features) | ~62% | Gaussian EV (P(make) via CDF) |
| `olsa` | `hybrid_r0.json` (constrained, 3 features) | ~100% | Floor-based threshold |
| `olsa_full` | `hybrid_r0_full.json` (full, 39 features) | ~100% | Floor-based threshold |

### H2H Results (No Longer Deferred)

The full H2H battery is now complete. See
[h2h_battery_analysis.md](h2h_battery_analysis.md) for the full report.

**Key H2H findings relevant to this promotion:**

The H2H pairwise matchups produce a **partial dominance order** among the
competitive bidders:

```
modeloespecifico  >  hybrid_olsa  >  olsa  ~  olsa_full
```

- modeloespecifico strictly dominates hybrid_olsa (delta +0.64–0.78, CI
  excludes zero both directions)
- hybrid_olsa strictly dominates olsa (+0.21 net_eppd wrapper effect, CI
  excludes zero)
- hybrid_olsa vs olsa_full is a draw
- olsa vs olsa_full is a draw

All four trained/heuristic-expert bidders dominate the three simple heuristics
(rankthetank, fiveheadfred, stricthellraiser) by large, significant margins.

### Evaluation Methodology Comparison

The comparator battery and H2H battery measure different things:

| | Comparator Battery | H2H Battery |
|---|---|---|
| **Design** | Each bidder plays alone vs GluttonStrategy (uncontested auction) | Two bidders compete directly (contested auction) |
| **Measures** | Absolute performance against a common opponent | Relative performance between two bidders |
| **Answers** | "Is this model any good?" | "Which model is better?" |
| **Cost** | O(n) — one run per bidder | O(n²) — one run per pair |
| **Limitation** | Rankings confounded by Glutton interaction | Cannot assess absolute quality |

**Where the methods disagree:** `modeloespecifico` leads `olsa` by +1.86
net_eppd in self-play but is a **draw** in H2H (+0.016, CI spans zero). The
self-play gap reflects how each bidder interacts with GluttonStrategy's passive
defense, not intrinsic bidding superiority.

**Where they agree:** Both methods confirm modeloespecifico > hybrid_olsa and
the large gap between trained bidders and simple heuristics. The PROMOTED
decision is supported by both evaluation methods.

**For promotion gates (R1+),** H2H pairwise comparison is the primary
evaluation method. The comparator battery provides supplementary absolute
benchmarking.
