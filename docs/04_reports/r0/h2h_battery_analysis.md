# R0 H2H Battery Analysis & Experiment Summary (v2)

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline lock)
**Date:** 2026-03-03
**Purpose:** Validate R0 artifacts, calibrate R1 gate thresholds, establish bidder dominance ordering

v2; supersedes v1 in git history. Key changes: 8-bidder roster (hybrid_olsa_full
added), bid-level search in HybridOLSa, QUICK/FULL both at v4, comparator at v6.

---

## 1. What Was Done

### 1.1 Overview

Seven experiment campaigns were run to complete the R0-to-R1 transition,
producing the data needed to calibrate promotion gates and train the R1 model.
All runs used seed=42 for deterministic reproducibility. Total simulation
budget: ~808,000 deals across all campaigns.

### 1.2 Campaign Inventory

| Campaign | Deals | Bidders | Purpose |
|----------|-------|---------|---------|
| C33 Ablation (v2) | 40,000 | 2 (hybrid_olsa, olsa) | Isolate combined wrapper + search effect |
| Comparator Battery (v6) | 160,000 | 8 (all) | Rank bidders in self-play vs Glutton |
| C50 QUICK (v4) | 128,000 | 8 (all, 64 matchups) | Full H2H matrix at survey resolution |
| C50 FULL (v4) | 520,000 | 8 (all, 52 matchups) | Targeted rerun at publication resolution |
| Threshold Calibration | N/A | N/A | Derive gate thresholds from null signal |
| Drift Check | N/A | N/A | Validate QUICK thresholds against FULL |

### 1.3 Simulation Design

**Game variant:** Double-deck Bid Euchre (40 cards, 10-A, 4 suits x 2 copies,
bowers in suit contracts). 10 cards per player, 10 tricks per hand. Partnerships
(seats 0,2) vs (seats 1,3).

**H2H matchup structure:** Each matchup pits bidder A (seats 0,2) against
bidder B (seats 1,3) over N paired deals. "Paired deals" means the same
shuffles are used for each matchup, and each deal is played twice with seats
swapped (A on team 0, then A on team 1). This controls for deal luck and
isolates bidding skill.

**Metric:** `net_eppd` (net expected points per deal) is the primary metric.
It accounts for both making and setting: declaring team gets `2*tricks - 10`
when making, `tricks - bid - 10` when set; defending team always gets
`tricks_won`. This net differential penalizes aggressive overbidding more than
raw `eppd`.

**Statistical method:** Bootstrap 95% confidence intervals (10,000 resamples,
seed=42). A matchup is "significant" when the CI on `net_eppd_delta` excludes
zero.

**Terminology note -- bid_rate in H2H context:** Throughout this report,
`bid_rate` in H2H matchups refers to **team auction-win frequency** -- the
fraction of deals where a bidder's team wins the contested auction. This is NOT
the individual bid propensity measured in the comparator battery. In H2H
matchups, both teams participate in a contested auction where one team's bid may
outbid the other. A bidder with high team auction-win frequency does not
necessarily bid more often in absolute terms; it may simply bid higher or more
effectively than the opponent. For uncontested bid propensity, see the
comparator rankings (section 3).

### 1.4 What This Methodology Measures (and What It Does Not)

**Design:** Two bidders compete directly on the same deals. Both bidders
participate in a contested auction -- bidder A's bid may outbid B or vice versa,
changing which contracts each side plays. Deals are seat-swapped to control for
positional advantage.

**Strengths:**

- **True competitive ordering.** Measures which bidder is actually better when
  they face each other in a contested auction. This is the only evaluation
  method that captures auction interaction effects.
- **Controlled for deal luck.** Paired deals + seat-swapping isolate bidding
  skill from card distribution variance.
- **Used for promotion gates.** The R1 promotion gate requires the challenger
  to beat the incumbent by a calibrated delta_floor in direct H2H, not in
  self-play.

**Limitations:**

- **Relative only.** Two equally weak models produce delta ~ 0, just as two
  equally strong models do. H2H cannot tell you whether the models are any
  good in absolute terms -- only which is better. For absolute benchmarking,
  see the [comparator rankings](comparator_rankings.md).
- **O(n^2) cost.** 8 bidders require 64 matchups; this becomes expensive at
  publication resolution (10k deals/cell = 640k deals). The QUICK-then-FULL
  design mitigates this by running a survey at 2k/cell first.
- **Opponent-specific.** A bidder's H2H performance depends on who it faces.
  Rock-paper-scissors effects (intransitivity) are possible in theory, though
  not observed in R0.

**Comparison with self-play comparator battery:** The comparator battery
([comparator_rankings.md](comparator_rankings.md)) evaluates each bidder
independently against GluttonStrategy in uncontested auctions. It answers "is
this model any good?" while H2H answers "which model is better?" The two
methods can give different rankings -- for example, in v2 the hybrid bidders
(hybrid_olsa +2.131, hybrid_olsa_full +2.170) lead modeloespecifico (+1.604) in
self-play by ~0.5 net_eppd, while in H2H modeloespecifico strictly dominates
both. This divergence arises because self-play rankings are confounded by how
each bidder interacts with the common opponent, while H2H captures the actual
competitive dynamic.

### 1.5 The Eight Bidders

| Bidder | Type | Description |
|--------|------|-------------|
| **hybrid_olsa** | Trained (Gaussian EV + search) | R0 OLSa with analytical P(make) via normal CDF and bid-level search across all legal bids. Uses 3 constrained features from `hybrid_r0.json`. |
| **hybrid_olsa_full** | Trained (Gaussian EV + search) | Full-arm OLSa with analytical P(make) via normal CDF and bid-level search. Uses forward-selected features (7 total, from pool of 39) from `hybrid_r0_full.json`. |
| **olsa** | Trained (floor-based) | Same R0 regression coefficients as hybrid_olsa (`hybrid_r0.json`), but uses floor-based threshold decision and floor(mu) bid level. No bid-level search. |
| **olsa_full** | Trained (floor-based) | Full-arm OLSa with forward-selected features from `hybrid_r0_full.json`, floor-based decision. No bid-level search. |
| **modeloespecifico** | Heuristic (lookup) | Domain-expert lookup table tuned for this game variant. Always bids. |
| **rankthetank** | Heuristic | Conservative rank-based heuristic. Always bids. |
| **fiveheadfred** | Heuristic | Aggressive heuristic emphasizing high cards. Always bids. |
| **stricthellraiser** | Heuristic | Maximally aggressive bidder. Always bids, rarely makes. |

**v2 architecture note:** In v2, both hybrid_olsa and hybrid_olsa_full use
**bid-level search** -- they evaluate all legal bid levels and select the one
with maximum expected utility, rather than using floor(mu). Combined with the
Gaussian EV wrapper, this produces bid rates of ~96% in self-play comparator
(up from ~20% in v1). The OLSa variants (olsa, olsa_full) remain floor-based
without search.

---

## 2. C33 Ablation: Combined Wrapper + Search Effect (v2)

### 2.1 Question

In v2, the hybrid_olsa bidder differs from olsa in TWO ways: (a) the Gaussian
EV wrapper (analytical P(make) via normal CDF), and (b) bid-level search
(evaluating all legal bid levels vs floor(mu)). The C33 ablation captures their
**combined effect** in direct H2H competition.

### 2.2 Design

4 matchups x 10,000 paired deals = 40,000 deals total:

- 2 self-play baselines (sanity check)
- 2 cross-matchups (directional + seat-swapped)

### 2.3 Results

| Matchup | net_eppd_delta | 95% CI | Significant? |
|---------|----------------|--------|--------------|
| hybrid_olsa self-play | -0.048 | [-0.132, +0.038] | No |
| olsa self-play | -0.017 | [-0.156, +0.122] | No |
| **hybrid_olsa vs olsa** | **+0.071** | **[-0.065, +0.204]** | **No** |
| **olsa vs hybrid_olsa** | **-0.183** | **[-0.315, -0.054]** | **Yes** |

### 2.4 Interpretation

Both self-play cells show deltas near zero with CIs spanning zero, confirming
the paired-deal design is unbiased.

**Pooled combined effect:** +0.13 net_eppd (average of |0.071| and |0.183|).

The v2 C33 result is notable: the asymmetry between directions is larger than in
v1, and one direction (hybrid_olsa vs olsa) is no longer individually
significant, though the other direction (olsa vs hybrid_olsa) remains
significant. The pooled effect (+0.13) is *smaller* in H2H than the v1 pooled
effect (+0.21), despite the addition of bid-level search. This apparent paradox
is explained by the behavioral change: in v2, hybrid_olsa's bid-level search
means it bids at higher levels when it does bid, which changes the auction
dynamics with olsa.

**Decomposition of the wrapper + search effect:** The combined effect (+0.13
in H2H) underestimates the individual component values because H2H measures
competitive advantage, not absolute improvement. The decomposition is best
understood from the comparator battery, where the effects are additive:
- **Search effect:** +0.43 net_eppd (estimated from v1-to-v2 improvement after
  isolating search)
- **Wrapper effect:** +0.75 net_eppd (estimated from v1-to-v2 improvement
  attributable to wrapper + search synergy)

See [c33_ablation_report.md](c33_ablation_report.md) for full decomposition
analysis.

**Team auction-win frequency profile:**

| Matchup | Team | net_eppd | team auction-win freq | make_rate |
|---------|------|----------|-----------------------|-----------|
| hybrid_olsa vs olsa | team0 (hybrid_olsa) | 3.862 | 11.7% | 89.6% |
| hybrid_olsa vs olsa | team1 (olsa) | 3.790 | 88.3% | 76.1% |
| olsa vs hybrid_olsa | team0 (olsa) | 3.744 | 87.8% | 75.9% |
| olsa vs hybrid_olsa | team1 (hybrid_olsa) | 3.928 | 12.3% | 90.9% |

The behavioral pattern matches v1: hybrid_olsa yields the auction to olsa in
~88% of deals, bidding only when its Gaussian CDF indicates high P(make). When
it does bid, it makes 89-91% of its contracts vs olsa's 76%. The v2 bid-level
search changes *which* deals hybrid_olsa bids on and at what level, but the
overall selectivity pattern remains.

---

## 3. Comparator Rankings (v6, Single-Seat)

### 3.1 Design

Each bidder plays 20,000 deals (5,000/seat x 4 seats) in single-seat mode
against GluttonStrategy card play. The bidder under test occupies one seat
while three always-pass sentinels fill the remaining seats. Bootstrap 95% CIs
from 10,000 resamples.

See [comparator_rankings.md](comparator_rankings.md) for full methodology,
behavioral analysis, and version history.

### 3.2 Rankings

| Rank | Bidder | net_eppd | 95% CI |
|------|--------|----------|--------|
| 1 | **hybrid_olsa_full** | **+2.170** | [+2.081, +2.257] |
| 2 | **hybrid_olsa** | **+2.131** | [+2.042, +2.216] |
| 3 | modeloespecifico | +1.604 | [+1.489, +1.720] |
| 4 | stricthellraiser | +0.085 | [-0.027, +0.197] |
| 5 | olsa_full | -0.012 | [-0.193, +0.173] |
| 6 | olsa | -0.225 | [-0.413, -0.037] |
| 7 | fiveheadfred | -2.579 | [-2.771, -2.384] |
| 8 | rankthetank | -9.665 | [-9.851, -9.483] |

### 3.3 Pairwise Significance

| Pair (higher vs lower) | Diff | p-value | Significant? |
|------------------------|------|---------|--------------|
| hybrid_olsa_full vs hybrid_olsa | +0.038 | 0.546 | No |
| hybrid_olsa vs modeloespecifico | +0.527 | < 0.001 | Yes |
| modeloespecifico vs stricthellraiser | +1.520 | < 0.001 | Yes |
| stricthellraiser vs olsa_full | +0.096 | 0.375 | No |
| olsa_full vs olsa | +0.213 | 0.110 | No |
| olsa vs fiveheadfred | +2.355 | < 0.001 | Yes |
| fiveheadfred vs rankthetank | +7.086 | < 0.001 | Yes |

### 3.4 Observations

**Three tiers are visible:**

1. **Competitive** (net_eppd > +1.5): hybrid_olsa_full, hybrid_olsa, modeloespecifico
2. **Near-zero** (net_eppd -0.5 to +0.2): stricthellraiser, olsa_full, olsa
3. **Negative** (net_eppd < -2): fiveheadfred, rankthetank

**v1-to-v2 shift:** The headline change is that both hybrid bidders jumped from
the near-zero tier to the competitive tier, now *leading* modeloespecifico. In
v1, hybrid_olsa was at +0.455 (rank 2) behind modeloespecifico (+1.587). In v2,
bid-level search + wrapper pushes hybrid_olsa to +2.131, a gain of +1.676
net_eppd. The make_rate jumped from 88.6% to 100% because bid-level search
ensures the bidder only bids at levels it can make.

hybrid_olsa_full and hybrid_olsa are statistically indistinguishable
(p=0.546). Both achieve 100% make_rate and ~96-97% bid rate in comparator
self-play. The forward-selected features in hybrid_olsa_full provide negligible
additional value at R0 model quality.

Note: stricthellraiser's rank 4 reflects a degenerate single-seat mode (always
bids 3 Spades), not its intended auction-raising behavior.

---

## 4. H2H Battery: Full Matrix

### 4.1 Design

**QUICK phase (v4):** 8 bidders x 8 bidders = 64 matchups (including
self-play), 2,000 paired deals per cell. Purpose: survey-resolution coverage
of the full matrix.

**FULL phase (v4):** 52 of 64 matchups rerun at 10,000 paired deals. Selection
criteria: all cells involving {hybrid_olsa, hybrid_olsa_full, olsa, olsa_full,
modeloespecifico} + key cross-tier matchups. Purpose: publication-resolution
data for key matchups and gate calibration.

### 4.2 Self-Play Sanity

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

### 4.3 Dominance Structure

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

### 4.4 Key Pairwise Matchups (FULL, 10k deals)

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
+0.644/−0.777 net_eppd in H2H. In v2, the gap narrowed to +0.252/−0.455 --
roughly half the v1 gap. Bid-level search made the hybrid bidders substantially
more competitive against the domain-expert heuristic, though modeloespecifico
retains a statistically significant edge.

**Trained vs heuristic bidders:** All trained bidders beat all heuristic
bidders with large, highly significant margins (deltas ranging from +0.35 to
+10.5 net_eppd). The gap between the "competitive" and "weak" tiers is the
dominant structure in the matrix.

### 4.5 Behavioral Asymmetry

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

## 5. Gate Threshold Calibration

### 5.1 Purpose

The R1 promotion gate needs calibrated thresholds to distinguish real
improvement from noise. Thresholds are derived from the "null signal" in the
H2H matrix: self-play deltas and seat-swap residuals, which should be zero
under perfect symmetry.

### 5.2 Method

```
null_abs = [|self_play_delta_i| for i in 8 bidders]
         + [|delta(A_vs_B) + delta(B_vs_A)| for (A,B) in bidder pairs]

delta_floor          = max(0.01, percentile(null_abs, 95))
regression_threshold = max(0.05, percentile(null_abs, 99))
cvar5_tolerance      = max(0.05, 2.0 * std(cvar5_pairwise_residuals))
```

### 5.3 Two-Stage Calibration

**Stage 1 (QUICK, 2k deals):**
- delta_floor = 0.658
- regression_threshold = 0.768

These are unusably high -- a challenger would need to improve by +0.66 net_eppd
to pass the promotion gate. This reflects the high variance inherent in 2k-deal
estimates.

**Stage 2 (FULL, 10k deals):**
- delta_floor = 0.180
- regression_threshold = 0.184

**Drift check:** The calibration script automatically compared QUICK and FULL
thresholds. Drift ratio = 0.726 (QUICK q95 was 73% higher than FULL q95),
exceeding the 0.25 threshold for automatic recalibration. The final thresholds
are derived from FULL data.

### 5.4 Final Thresholds

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `delta_floor` | 0.180 | Challenger must improve by +0.18 net_eppd for PROMOTED |
| `regression_threshold` | 0.184 | Challenger regressing by -0.18 net_eppd triggers HALT |
| `cvar5_tolerance` | 0.050 | Floor value (CVaR-5 residuals too small to calibrate) |
| `bid_rate_min` | 0.050 | Guardrail: minimum acceptable bid rate |
| `bid_rate_max` | 0.950 | Guardrail: maximum acceptable bid rate |
| `make_rate_min` | 0.450 | Guardrail: minimum acceptable make rate |
| `downside_variance_ratio` | 1.100 | Guardrail: max downside variance vs incumbent |

### 5.5 Implications for R1

The delta_floor of 0.180 means the R1 challenger must demonstrate at least
+0.18 net_eppd improvement over the R0 incumbent in paired H2H evaluation.
For reference, the v2 pooled H2H wrapper+search effect (+0.13) would NOT
clear this bar, though the v1 wrapper effect (+0.21) would barely do so.

The near-equality of delta_floor and regression_threshold (0.180 vs 0.184)
indicates the null distribution has a tight, symmetric shape -- the q95 and
q99 quantiles are very close, suggesting the null signal has thin tails at
10k-deal resolution.

---

## 6. Artifact Inventory

**gate_status:** PROMOTED (R0 overall; this report is informational for the
R0-to-R1 transition)

All artifacts in data/artifacts/arc_d/r0/ (not committed to git).

| Artifact | Schema | Produced By |
|----------|--------|-------------|
| h2h_battery_quick_v4.json | h2h_battery_v2 | H2H battery (64 cells, 2k/cell) |
| h2h_battery_full_v4.json | h2h_battery_v2 | H2H battery (52 cells, 10k/cell) |
| comparator_battery_r0_v6.json | arc_d_comparator_v1 | Auction comparator (8 bidders, single-seat) |
| comparator_cis_r0_v6.json | comparator_cis_v1 | CI extractor (bootstrap) |
| gate_thresholds_r1.json | gate_thresholds_v1 | Threshold calibrator (FULL) |

Run directories (local only, data/runs/):

| Run | Deals | Purpose |
|-----|-------|---------|
| arc_d_r0_c33_ablation_42_20260302_230400 | 90,000 | C33 dedicated run (3 policies, v1 source) |
| arc_d_r0_h2h_battery_42_20260302_230409 | 128,000 | C50 QUICK (v4) |
| arc_d_r0_h2h_battery_42_20260302_231835 | 520,000 | C50 FULL (v4) |
| auction_comparator_*_42_20260302_* (32 runs) | 160,000 | Comparator battery (v6) |

---

## 7. Conclusions

1. **Bid-level search transforms the hybrid bidders.** The v2 hybrid_olsa
   jumped from comparator rank 2 (+0.455) to rank 1-2 (+2.131), leapfrogging
   modeloespecifico (+1.604) in self-play. The combination of Gaussian EV
   wrapper and bid-level search produces a bid_rate of 96% with 100% make_rate
   in comparator -- the bidder now bids on nearly every hand, but only at levels
   it can make.

2. **modeloespecifico retains the H2H crown** despite being dethroned in
   self-play. The gap narrowed dramatically: v1 H2H deltas of +0.64/-0.78
   became +0.25/-0.46 in v2. The domain-expert heuristic's advantage in
   contested auctions persists but is now less than half its v1 size.

3. **hybrid_olsa and hybrid_olsa_full are indistinguishable.** Both in
   self-play (p=0.546) and H2H (CIs span zero in both directions), the
   3-feature constrained arm matches the 7-feature promotional arm. The extra
   features provide no detectable advantage at R0 model quality.

4. **The combined wrapper+search effect is +0.13 in H2H** (pooled from the
   C33 cross-matchups). This is *smaller* than the v1 wrapper-only effect
   (+0.21 in H2H), which seems paradoxical. The explanation is that bid-level
   search changes the auction dynamics: hybrid_olsa now bids at higher levels,
   altering the competitive interaction with olsa in ways that compress the
   net_eppd_delta.

5. **Gate thresholds are tight.** The FULL-calibrated delta_floor (0.180)
   means R1 must show nearly the same improvement as the entire v1 Gaussian
   wrapper effect (+0.21) to achieve PROMOTED status. This is a deliberately
   conservative gate -- it prevents promoting noise.

6. **QUICK thresholds were dangerously inflated.** The drift check caught a
   73% overestimate in QUICK-derived thresholds. Without the two-stage
   calibration, R1 would have needed +0.66 net_eppd to promote -- an
   impossibly high bar. This validates the QUICK-then-FULL design.

7. **The OLS-vs-heuristic gap is enormous.** All trained bidders dominate all
   heuristic bidders (stricthellraiser, fiveheadfred, rankthetank) by 1-10
   net_eppd. The OLS regression coefficients provide massive value.

### Companion Reports

| Report | Focus |
|--------|-------|
| [c33_ablation_report.md](c33_ablation_report.md) | Wrapper + search decomposition |
| [comparator_rankings.md](comparator_rankings.md) | Absolute benchmarking (v6) |
| [r0_promotion_report.md](r0_promotion_report.md) | Gate results, multi-seed |

---

## 8. Reproduction

All experiments are deterministic with seed=42. To reproduce:

```bash
# C33 ablation (v2)
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/arc_d_r0_c33_ablation.yaml

# Comparator battery (8 bidders, single-seat v6)
PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml --seed 42 \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --bidder-class HybridOLSaBidder --bidder-name hybrid_olsa \
  --single-seat --n-per 20000 \
  --output-format json --output data/artifacts/arc_d/r0/comparator_battery_r0_v6.json

# C50 QUICK v4 (generate config, run, parse)
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 \
  --output data/artifacts/arc_d/r0/h2h_battery_quick_v4.json
uv run python experiments/run_experiment.py --seed 42 \
  --config data/artifacts/arc_d/r0/h2h_battery_quick_v4_config.yaml
# Then: --parse-run <run_dir> to populate

# C50 FULL v4 (subset of QUICK)
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode FULL --seed 42 --n-per 10000 \
  --quick-summary data/artifacts/arc_d/r0/h2h_battery_quick_v4.json \
  --output data/artifacts/arc_d/r0/h2h_battery_full_v4.json
uv run python experiments/run_experiment.py --seed 42 \
  --config data/artifacts/arc_d/r0/h2h_battery_full_v4_config.yaml
# Then: --parse-run <run_dir> to populate

# Threshold calibration (with drift check)
PYTHONPATH=src uv run python scripts/internal/calibrate_arc_d_thresholds.py \
  --h2h-summary data/artifacts/arc_d/r0/h2h_battery_quick_v4.json \
  --full-summary data/artifacts/arc_d/r0/h2h_battery_full_v4.json \
  --seed 42 --output data/artifacts/arc_d/r0/gate_thresholds_r1.json

# CI extraction (single-seat v6)
PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/artifacts/arc_d/r0 --runs-dir data/runs --seed 42 \
  --n-bootstrap 10000 --single-seat \
  --output data/artifacts/arc_d/r0/comparator_cis_r0_v6.json \
  --battery-file comparator_battery_r0_v6.json
```
