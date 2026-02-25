# R0 Comparator Rankings

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-02-23
**Methodology:** 10,000 deals per bidder, seed=42, 10,000 bootstrap resamples

## Rankings Table

All 5 comparator bidders ranked by `net_eppd` (net expected points per deal)
descending. Bootstrap 95% confidence intervals in brackets.

| Rank | Bidder | net_eppd [95% CI] | eppd [95% CI] | bid_rate | make_rate | CVaR-5% [95% CI] | net_CVaR-5% [95% CI] |
|------|--------|-------------------|---------------|----------|-----------|-------------------|----------------------|
| 1 | modeloespecifico | +2.291 [+2.190, +2.390] | +5.705 [+5.629, +5.778] | 1.000 | 0.903 | −5.524 [−5.588, −5.462] | −11.618 [−11.706, −11.536] |
| 2 | **hybrid_olsa** | **+1.481 [+1.364, +1.596]** | **+4.162 [+4.062, +4.258]** | **0.828** | **0.830** | **−6.408 [−6.473, −6.345]** | **−12.072 [−12.191, −11.961]** |
| 3 | rankthetank | −3.170 [−3.331, −3.008] | +1.135 [+1.008, +1.266] | 1.000 | 0.546 | −6.000 [−6.000, −6.000] | −14.306 [−14.428, −14.182] |
| 4 | fiveheadfred | −3.521 [−3.671, −3.371] | +1.565 [+1.452, +1.680] | 1.000 | 0.582 | −5.000 [−5.000, −5.000] | −14.198 [−14.290, −14.088] |
| 5 | stricthellraiser | −6.114 [−6.276, −5.956] | −1.034 [−1.159, −0.911] | 1.000 | 0.384 | −6.000 [−6.000, −6.000] | −15.152 [−15.260, −15.044] |

## Pairwise Significance

Bootstrap permutation test (two-sided) for net_eppd difference between
adjacent-ranked bidders. n=10,000 bootstrap resamples, seed=42.

| Pair | net_eppd diff | p-value | Significant? |
|------|---------------|---------|--------------|
| modeloespecifico vs hybrid_olsa | +0.810 | < 0.001 | Yes |
| hybrid_olsa vs rankthetank | +4.651 | < 0.001 | Yes |
| rankthetank vs fiveheadfred | +0.351 | 0.001 | Yes |
| fiveheadfred vs stricthellraiser | +2.593 | < 0.001 | Yes |

All adjacent pairs are significantly different at alpha=0.05.
The smallest gap (rankthetank vs fiveheadfred, +0.351) is still significant
(p=0.001).

## Behavioral Profiles

**modeloespecifico** — Domain-expert heuristic bidder. Always bids (bid_rate=1.0)
with 90.3% make rate, achieving the highest net_eppd (+2.291). Represents the
upper bound for heuristic bidding quality. Its aggressive-but-accurate bidding
produces the best CVaR-5% (−5.524), indicating controlled downside risk.

**hybrid_olsa (R0)** — Linear OLSa model with forward-selected features. The
only bidder that *passes* on some deals (bid_rate=82.8%), reflecting its
uncertainty-aware decision boundary. Despite lower bid frequency, achieves
83.0% make rate on bid hands and ranks 2nd overall. Its selective bidding
means lower eppd (+4.162) but competitive net_eppd (+1.481).

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

1. **Selective bidding pays off.** `hybrid_olsa` is the only bidder that passes
   on some deals, and this selectivity produces a dramatically better net_eppd
   than the three always-bid heuristics (rankthetank, fiveheadfred,
   stricthellraiser) despite a simpler model.

2. **Make rate is the dominant driver.** The ranking by net_eppd closely tracks
   make rate: modeloespecifico (90.3%) > hybrid_olsa (83.0%) > fiveheadfred
   (58.2%) > rankthetank (54.6%) > stricthellraiser (38.4%).

3. **Gap to close.** The 0.81 point/deal gap between modeloespecifico and
   hybrid_olsa is the primary target for R1+ improvements. The gap's
   significance (p < 0.001) confirms it is not due to sampling noise.

4. **Cliff between ranks 2 and 3.** The +4.651 gap between hybrid_olsa and
   rankthetank is the largest in the table, highlighting that any bid-selection
   strategy dramatically outperforms always-bid heuristics.

## Methodology

- **Deal count:** 10,000 deals per bidder
- **Seed:** 42 (all bidders evaluated on identical deal sequences)
- **Bootstrap:** 10,000 resamples for CIs and permutation tests
- **Net_eppd definition:** sum(bidder_pts − opponent_pts for bid-hands) / total_deals.
  Pass deals contribute 0 to the numerator but count in the denominator.
- **CVaR-5%:** Mean of the worst 5% of bid-hand outcomes
- **Extraction script:** scripts/internal/extract_comparator_cis.py
- **Source data:** data/artifacts/arc_d/r0/comparator_cis_r0.json (gitignored)
- **Battery metadata:** data/artifacts/arc_d/r0/comparator_battery_r0.json
