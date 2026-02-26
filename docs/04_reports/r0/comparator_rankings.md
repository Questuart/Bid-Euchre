# R0 Comparator Rankings (v2, 7 Bidders)

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-02-25 (v2; supersedes v1 5-bidder rankings in git history)
**Methodology:** 10,000 deals per bidder, seed=42, 10,000 bootstrap resamples

## Rankings Table

All 7 comparator bidders ranked by `net_eppd` (net expected points per deal)
descending. Bootstrap 95% confidence intervals in brackets.

| Rank | Bidder | net_eppd [95% CI] | eppd [95% CI] | bid_rate | make_rate | CVaR-5% [95% CI] | net_CVaR-5% [95% CI] |
|------|--------|-------------------|---------------|----------|-----------|-------------------|----------------------|
| 1 | modeloespecifico | +2.291 [+2.190, +2.390] | +5.705 [+5.629, +5.778] | 1.000 | 0.903 | −5.524 [−5.588, −5.462] | −11.618 [−11.706, −11.536] |
| 2 | **hybrid_olsa** | **+1.667 [+1.574, +1.760]** | **+3.567 [+3.477, +3.654]** | **0.625** | **0.877** | **−6.144 [−6.186, −6.103]** | **−11.712 [−11.827, −11.603]** |
| 3 | olsa_full | +0.690 [+0.548, +0.833] | +3.973 [+3.858, +4.090] | 1.000 | 0.747 | −7.016 [−7.042, −6.928] | −12.334 [−12.398, −12.272] |
| 4 | olsa | +0.429 [+0.282, +0.574] | +3.766 [+3.645, +3.884] | 1.000 | 0.732 | −7.000 [−7.000, −6.926] | −12.376 [−12.446, −12.310] |
| 5 | rankthetank | −3.170 [−3.331, −3.008] | +1.135 [+1.008, +1.266] | 1.000 | 0.546 | −6.000 [−6.000, −6.000] | −14.306 [−14.428, −14.182] |
| 6 | fiveheadfred | −3.521 [−3.671, −3.371] | +1.565 [+1.452, +1.680] | 1.000 | 0.582 | −5.000 [−5.000, −5.000] | −14.198 [−14.290, −14.088] |
| 7 | stricthellraiser | −6.114 [−6.276, −5.956] | −1.034 [−1.159, −0.911] | 1.000 | 0.384 | −6.000 [−6.000, −6.000] | −15.152 [−15.260, −15.044] |

## Pairwise Significance

Bootstrap permutation test (two-sided) for net_eppd difference between
adjacent-ranked bidders. n=10,000 bootstrap resamples, seed=42.

| Pair | net_eppd diff | p-value | Significant? |
|------|---------------|---------|--------------|
| modeloespecifico vs hybrid_olsa | +0.624 | < 0.001 | Yes |
| hybrid_olsa vs olsa_full | +0.978 | < 0.001 | Yes |
| olsa_full vs olsa | +0.261 | 0.015 | Yes |
| olsa vs rankthetank | +3.599 | < 0.001 | Yes |
| rankthetank vs fiveheadfred | +0.351 | 0.001 | Yes |
| fiveheadfred vs stricthellraiser | +2.593 | < 0.001 | Yes |

All 6 adjacent pairs are significantly separated at alpha=0.05. The tightest
gap (olsa_full vs olsa, +0.261, p=0.015) confirms the full-arm's 39 features
provide a small but real advantage over the constrained 3-feature arm in
self-play.

## Behavioral Profiles

**modeloespecifico** — Domain-expert heuristic bidder. Always bids (bid_rate=1.0)
with 90.3% make rate, achieving the highest net_eppd (+2.291). Represents the
upper bound for heuristic bidding quality. Its aggressive-but-accurate bidding
produces the best CVaR-5% (−5.524), indicating controlled downside risk.

**hybrid_olsa (R0)** — OLSa model with Gaussian CDF decision layer
(constrained 3-feature arm from `hybrid_r0.json`). The only bidder that
*passes* on some deals (bid_rate=62.5%), reflecting its analytical P(make)
threshold. Achieves 87.7% make rate on bid hands and ranks 2nd overall. Its
selective bidding means lower eppd (+3.567) but the highest net_eppd among
trained models (+1.667). See [c33_ablation_report.md](c33_ablation_report.md)
for the wrapper effect analysis.

**olsa_full** — Full-arm OLSa with all 39 forward-selected features from
`hybrid_r0_full.json`, using floor-based threshold. Always bids with 74.7%
make rate. Higher eppd than olsa (+3.973 vs +3.766) due to the additional
features, translating to a modest net_eppd advantage (+0.690 vs +0.429).

**olsa** — Constrained OLSa with 3 features from `hybrid_r0.json`, using
floor-based threshold. Always bids with 73.2% make rate. Uses identical
regression coefficients to hybrid_olsa but lacks the Gaussian CDF wrapper,
resulting in lower selectivity and lower net_eppd (+0.429 vs +1.667).

**rankthetank** — Heuristic bidder with moderate aggression. Always bids but
makes only 54.6% of contracts, leading to frequent penalties. Positive eppd
(+1.135) but strongly negative net_eppd (−3.170) indicates that the penalties
from set bids outweigh the gains from made bids.

**fiveheadfred** — Aggressive heuristic bidder. Always bids with 58.2% make
rate. Higher eppd than rankthetank (+1.565 vs +1.135) due to occasionally
winning bigger contracts, but worse net_eppd (−3.521) because failed bids are
more costly. CVaR-5% of −5.000 indicates a floor on worst-case outcomes.

**stricthellraiser** — The most aggressive bidder. Always bids with the lowest
make rate (38.4%), resulting in the only negative eppd (−1.034) and worst
net_eppd (−6.114). Demonstrates that overbidding is heavily penalized by the
scoring system.

## Key Observations

1. **Three tiers are visible.** The 7 bidders separate into: competitive
   (net_eppd > 0: modeloespecifico, hybrid_olsa, olsa_full, olsa), weak
   (net_eppd −4 to −3: rankthetank, fiveheadfred), and degenerate
   (net_eppd < −6: stricthellraiser).

2. **Selective bidding pays off.** `hybrid_olsa` is the only bidder that passes
   on some deals, and this selectivity produces a dramatically better net_eppd
   than even `olsa_full` (which uses more features but always bids). The +0.978
   gap between hybrid_olsa and olsa_full is larger than the gap to
   modeloespecifico (+0.624).

3. **Make rate is the dominant driver.** The ranking by net_eppd closely tracks
   make rate: modeloespecifico (90.3%) > hybrid_olsa (87.7%) > olsa_full
   (74.7%) > olsa (73.2%) > fiveheadfred (58.2%) > rankthetank (54.6%) >
   stricthellraiser (38.4%).

4. **Gap to close.** The 0.624 point/deal gap between modeloespecifico and
   hybrid_olsa is the primary target for R1+ improvements. The gap's
   significance (p < 0.001) confirms it is not due to sampling noise.

5. **Cliff between ranks 4 and 5.** The +3.599 gap between olsa and
   rankthetank is the largest in the table, highlighting that any OLS-trained
   bidder dramatically outperforms always-bid heuristics.

## Methodology

- **Deal count:** 10,000 deals per bidder
- **Seed:** 42 (all bidders evaluated on identical deal sequences)
- **Bootstrap:** 10,000 resamples for CIs and permutation tests
- **Net_eppd definition:** sum(bidder_pts − opponent_pts for bid-hands) / total_deals.
  Pass deals contribute 0 to the numerator but count in the denominator.
- **CVaR-5%:** Mean of the worst 5% of bid-hand outcomes
- **Extraction script:** scripts/internal/extract_comparator_cis.py
- **Source data:** data/artifacts/arc_d/r0/comparator_cis_r0_v2.json (gitignored)
- **Battery metadata:** data/artifacts/arc_d/r0/comparator_battery_r0_v2.json
- **gate_status:** PROMOTED (see [r0_promotion_report.md](r0_promotion_report.md))

### Supersession Note

This is the **v2** comparator rankings report (7 bidders). The original v1
report (5 bidders, using `comparator_cis_r0.json`) is preserved in git history.
The v2 battery added `olsa_full` and `olsa` as separate entries; the v1
`hybrid_olsa` entry mapped to the OLSa_Full promotional arm
(`hybrid_r0_full.json`, bid_rate ~83%). In v2, `hybrid_olsa` refers to the
constrained arm with Gaussian CDF wrapper (`hybrid_r0.json`, bid_rate ~62.5%).

### Bidder Identity Note

In this battery, `hybrid_olsa` refers to the **constrained OLSa arm** with
Gaussian CDF wrapper using the `hybrid_r0.json` artifact (3 features,
bid_rate=62.5%). This differs from the v1 battery where `hybrid_olsa` referred
to the OLSa_Full promotional arm. The 7-bidder battery disambiguates by giving
each variant its own entry.

### What This Methodology Measures (and What It Does Not)

**Design:** Each bidder plays independently against GluttonStrategy (the
card-playing policy that controls all four seats). There is no competing bidder
in the auction — the bidder under test declares contracts uncontested, and
Glutton handles all card play for both teams.

**Strengths:**

- **Absolute scale.** Provides a common benchmark for answering "is this model
  any good?" A positive net_eppd means the bidder adds value relative to a
  no-bid baseline.
- **Progress tracking.** Enables rung-over-rung comparison against a fixed
  reference point without running O(n²) pairwise matchups.
- **Reproducible exam.** Same deals, same opponent, same conditions — isolates
  the bidding policy as the only variable.

**Limitations:**

- **Confounded by the common opponent.** Rankings reflect how well each bidder
  interacts with GluttonStrategy, not intrinsic bidding quality. A bidder tuned
  to exploit Glutton's tendencies may score well here but show no advantage in
  direct competition.
- **No auction interaction.** Real games have contested auctions where one
  bidder's bid changes which contracts the opponent gets to play. This battery
  evaluates uncontested bidding — a fundamentally different task.
- **Self-play rankings may not match competitive ordering.** The H2H battery
  ([h2h_battery_analysis.md](h2h_battery_analysis.md)) shows that some self-play
  gaps do not replicate under direct opposition. For example,
  `modeloespecifico` leads `olsa` by +1.86 net_eppd in self-play, but the two
  are statistically indistinguishable in head-to-head (+0.016, CI spans zero).

**Bottom line:** Use these rankings for absolute benchmarking and progress
tracking. For competitive ordering between bidders, see the
[H2H battery analysis](h2h_battery_analysis.md).
