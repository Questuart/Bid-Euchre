# R0 H2H Pairwise Analysis (v2)

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline lock)
**Date:** 2026-03-03
**Version:** v2
**Purpose:** H2H pairwise matchup analysis -- full matrix, dominance structure, behavioral asymmetry

Companion to [h2h_battery_analysis.md](h2h_battery_analysis.md) (experiment summary).

---

## 1. Average H2H Delta Rankings

Average pooled net_eppd_delta across all trained-bidder matchups (FULL, 10k
deals). Each pair's pooled delta = mean of |delta(A vs B)| and |delta(B vs A)|,
sign assigned to the winner. Win/Loss/Draw from QUICK (complete 8x8 matrix, 2k
deals) where a "win" means the CI on net_eppd_delta excludes zero in the
bidder's favor.

| Rank | Bidder | Avg H2H delta | Record (W/L/D) |
|------|--------|---------------|----------------|
| 1 | modeloespecifico | +0.230 | 5/0/2 |
| 2 | hybrid_olsa_full | +0.015 | 3/1/3 |
| 3 | olsa_full | -0.054 | 3/0/4 |
| 4 | hybrid_olsa | -0.063 | 3/1/3 |
| 5 | olsa | -0.128 | 2/4/1 |

Avg H2H delta is computed from FULL trained-vs-trained matchups only (4
opponents per bidder). Heuristic bidders (stricthellraiser, fiveheadfred,
rankthetank) are omitted from the delta ranking because they lose all
trained-bidder matchups by large margins (+0.35 to +10.5 net_eppd); their QUICK
records are 0/7/0, 2/5/0, and 1/6/0 respectively.

---

## 2. Design

**QUICK phase (v4):** 8 bidders x 8 bidders = 64 matchups (including
self-play), 2,000 paired deals per cell. Purpose: survey-resolution coverage
of the full matrix.

**FULL phase (v4):** 52 of 64 matchups rerun at 10,000 paired deals. Selection
criteria: all cells involving {hybrid_olsa, hybrid_olsa_full, olsa, olsa_full,
modeloespecifico} + key cross-tier matchups. Purpose: publication-resolution
data for key matchups and gate calibration.

---

## 3. Self-Play Sanity

Self-play cells should show `net_eppd_delta ~ 0` (a bidder playing itself
should not favor either team). CIs should span zero.

**FULL results (10k deals each):**

| Bidder | delta | 95% CI | Spans zero? | fullgame_eppd |
|--------|-------|--------|-------------|---------------|
| hybrid_olsa | -0.048 | [-0.132, +0.038] | Yes | 4.894 |
| hybrid_olsa_full | -0.022 | [-0.108, +0.062] | Yes | 4.890 |
| olsa | -0.017 | [-0.156, +0.122] | Yes | 3.714 |
| olsa_full | -0.066 | [-0.205, +0.069] | Yes | 3.747 |
| modeloespecifico | -0.083 | [-0.183, +0.020] | Yes | 4.691 |
| fiveheadfred | -0.107 | [-0.253, +0.034] | Yes | 3.540 |
| stricthellraiser | -0.020 | [-0.203, +0.162] | Yes | 2.150 |
| rankthetank | +0.061 | [-0.176, +0.294] | Yes | -1.645 |

All 8 self-play CIs span zero (pass). This is an improvement over v1, where
rankthetank showed a marginally significant positional bias. At 10k deals with
the v2 code, all bidders pass the self-play sanity check.

The fullgame_eppd values for self-play cells provide an absolute quality metric:
hybrid_olsa (4.894) and hybrid_olsa_full (4.890) achieve the highest self-play
eppd, indicating they extract the most value when both teams use the same
strategy. modeloespecifico follows at 4.691. The floor-based bidders (olsa
3.714, olsa_full 3.747) are substantially lower, reflecting their tendency to
bid on negative-EV hands.

---

## 4. Dominance Structure

**QUICK matrix (64 cells, 2k deals) -- Win/Loss/Draw:**

| Bidder | W | L | D |
|--------|---|---|---|
| modeloespecifico | 5 | 0 | 2 |
| hybrid_olsa_full | 3 | 1 | 3 |
| hybrid_olsa | 3 | 1 | 3 |
| olsa_full | 3 | 0 | 4 |
| olsa | 2 | 4 | 1 |
| fiveheadfred | 2 | 5 | 0 |
| rankthetank | 1 | 6 | 0 |
| stricthellraiser | 0 | 7 | 0 |

**FULL subset (52 cells, 10k deals) -- Win/Loss/Draw:**

| Bidder | W | L | D | Matchups |
|--------|---|---|---|----------|
| hybrid_olsa_full | 4 | 1 | 2 | 7 |
| modeloespecifico | 3 | 0 | 1 | 4 |
| hybrid_olsa | 3 | 1 | 3 | 7 |
| olsa_full | 3 | 2 | 2 | 7 |
| olsa | 3 | 3 | 1 | 7 |
| fiveheadfred | 0 | 4 | 0 | 4 |
| stricthellraiser | 0 | 4 | 0 | 4 |
| rankthetank | 0 | 4 | 0 | 4 |

**Note on win counts:** At QUICK resolution, modeloespecifico leads with 5W-0L
while the hybrid bidders show 3W-1L (both losing only to modeloespecifico). At
FULL resolution with more data, hybrid_olsa_full resolves an additional draw
into a win (4W-1L). The single loss for both hybrids is to modeloespecifico. Use
the pairwise results below for precise dominance ordering.

---

## 5. Key Pairwise Matchups (FULL, 10k deals)

**Trained bidders head-to-head:**

| A vs B | delta | 95% CI | Verdict |
|--------|-------|--------|---------|
| modeloespecifico vs hybrid_olsa | +0.252 | [+0.153, +0.352] | **modelo wins** |
| hybrid_olsa vs modeloespecifico | -0.455 | [-0.556, -0.357] | **modelo wins** |
| modeloespecifico vs hybrid_olsa_full | +0.165 | [+0.064, +0.265] | **modelo wins** |
| hybrid_olsa_full vs modeloespecifico | -0.355 | [-0.457, -0.256] | **modelo wins** |
| hybrid_olsa vs olsa | +0.071 | [-0.065, +0.204] | Draw |
| olsa vs hybrid_olsa | -0.183 | [-0.315, -0.054] | **hybrid wins** |
| hybrid_olsa_full vs olsa | +0.137 | [+0.000, +0.270] | **hybrid_full wins** |
| olsa vs hybrid_olsa_full | -0.270 | [-0.404, -0.140] | **hybrid_full wins** |
| hybrid_olsa vs hybrid_olsa_full | -0.075 | [-0.159, +0.010] | Draw |
| hybrid_olsa_full vs hybrid_olsa | -0.003 | [-0.088, +0.082] | Draw |
| hybrid_olsa vs olsa_full | -0.065 | [-0.200, +0.064] | Draw |
| olsa_full vs hybrid_olsa | -0.096 | [-0.226, +0.031] | Draw |
| hybrid_olsa_full vs olsa_full | +0.000 | [-0.135, +0.131] | Draw |
| olsa_full vs hybrid_olsa_full | -0.149 | [-0.280, -0.020] | **hybrid_full wins** |
| modeloespecifico vs olsa | +0.135 | [+0.002, +0.267] | **modelo wins** |
| olsa vs modeloespecifico | -0.263 | [-0.396, -0.132] | **modelo wins** |
| modeloespecifico vs olsa_full | +0.032 | [-0.101, +0.158] | Draw |
| olsa_full vs modeloespecifico | -0.184 | [-0.313, -0.052] | **modelo wins** |
| olsa vs olsa_full | -0.061 | [-0.198, +0.076] | Draw |
| olsa_full vs olsa | -0.028 | [-0.168, +0.109] | Draw |

**Interpretation:**

The trained bidders form a **partial dominance order with asymmetric evidence:**

```
modeloespecifico  >  hybrid_olsa_full  ~  hybrid_olsa  >  olsa  ~  olsa_full
                         |                    |
                         +----(draw)-----------+
```

- **modeloespecifico strictly dominates all** -- beats hybrid_olsa (both
  directions significant), hybrid_olsa_full (both directions significant), olsa
  (both directions significant), and olsa_full (significant in one direction).
- **hybrid_olsa_full and hybrid_olsa are draws** against each other (CI spans
  zero both ways). Their competitive positions are effectively identical.
- **hybrid_olsa vs olsa** is asymmetric: significant in one direction only.
  The pooled effect (+0.13) favors hybrid_olsa.
- **hybrid_olsa_full beats olsa and olsa_full** more cleanly than hybrid_olsa
  does (both directions significant for olsa, one direction for olsa_full).
- **olsa vs olsa_full is a draw** in H2H despite olsa_full's higher self-play
  ranking.

**v1-to-v2 shift in the modelo gap:** In v1, modeloespecifico led hybrid_olsa by
+0.644/-0.777 net_eppd in H2H. In v2, the gap narrowed to +0.252/-0.455 --
roughly half the v1 gap. Bid-level search made the hybrid bidders substantially
more competitive against the domain-expert heuristic, though modeloespecifico
retains a statistically significant edge.

**Trained vs heuristic bidders:** All trained bidders beat all heuristic
bidders with large, highly significant margins (deltas ranging from +0.35 to
+10.5 net_eppd). The gap between the "competitive" and "weak" tiers is the
dominant structure in the matrix.

---

## 6. Behavioral Asymmetry

A striking pattern emerges in the hybrid vs floor-based matchups. When
hybrid_olsa faces olsa:

- hybrid_olsa team auction-win frequency: 11.7% (highly selective)
- olsa team auction-win frequency: 88.3% (near-universal)

When the seats swap:

- olsa team auction-win frequency: 87.8%
- hybrid_olsa team auction-win frequency: 12.3%

hybrid_olsa yields the auction to olsa in ~88% of deals, bidding only when
its Gaussian CDF indicates high P(make). When it does bid, it makes 90% of its
contracts vs olsa's 76%. This is the same selective restraint mechanism seen in
v1, but v2's bid-level search means hybrid_olsa selects optimal bid levels when
it does bid.

A parallel pattern appears in the hybrid_olsa vs modeloespecifico matchups:

- hybrid_olsa team auction-win frequency: 41.6% vs modelo's 58.4%
- modelo team auction-win frequency: 58.2% vs hybrid_olsa's 41.9%

The auction-win frequencies are much more balanced between these two
because both are selective, high-make-rate bidders. modeloespecifico edges out
hybrid_olsa in the auction roughly 58% of the time, which drives its competitive
advantage.

---

## 7. Provenance

**Source data:**
- H2H battery QUICK v4: `data/artifacts/arc_d/r0/h2h_battery_quick_v4.json`
- H2H battery FULL v4: `data/artifacts/arc_d/r0/h2h_battery_full_v4.json`

**Experiment runs:**
- C50 QUICK: `data/runs/arc_d_r0_h2h_battery_42_20260302_230409` (128,000 deals)
- C50 FULL: `data/runs/arc_d_r0_h2h_battery_42_20260302_231835` (520,000 deals)

**Parent report:** [h2h_battery_analysis.md](h2h_battery_analysis.md) (experiment
summary with C33 ablation, comparator rankings, and gate threshold calibration)

**Related reports:**
- [c33_ablation_report.md](c33_ablation_report.md) -- Wrapper + search decomposition
- [comparator_rankings.md](comparator_rankings.md) -- Absolute benchmarking (v6)
- [r0_promotion_report.md](r0_promotion_report.md) -- Gate results, multi-seed

| Item | Value |
|------|-------|
| gate_status | N/A (pairwise analysis, not a gate evaluation) |
