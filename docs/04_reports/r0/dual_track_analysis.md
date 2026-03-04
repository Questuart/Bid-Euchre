# R0 Dual-Track Analysis: Decision Quality vs Full-Game Performance

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-03
**Purpose:** Side-by-side analysis of two complementary evaluation tracks,
archetype classification, and roster meta-analysis

---

## 1. Summary

This report presents two independent evaluation tracks for the eight R0
bidders and analyzes where they agree and disagree. The two tracks measure
fundamentally different things:

- **Decision quality** (single-seat comparator): evaluates every bid/pass
  decision in isolation, producing absolute net_eppd scores.
- **Full-game** (H2H battery): evaluates competitive performance including
  both bidding and defending, producing pairwise win/loss/draw verdicts.

Both tracks use GluttonStrategy for card play (harmonized by C2c/#466),
making track disagreements primarily **estimand-driven** rather than
confounded by play quality differences.

The v6 comparator battery (8 bidders, bid-level search) and v4 H2H battery
(8 bidders, 10k deals FULL / 2k deals QUICK) present a substantially changed
landscape from the v4/v3 versions of these instruments. The hybrid variants'
transformation from selective to near-universal bidders altered both the
archetype classification and the track agreement/disagreement dynamics.

The analysis also classifies bidders into three behavioral archetypes
(AGGRESSIVE, NEUTRAL, SELECTIVE) derived from single-seat comparator data,
and presents three scatter plots decomposing rankings into behavioral
components.

---

## 2. Dual-Track Rankings

### 2.1 Track Definitions

| Track | Estimand | Source | Key Metrics |
|-------|----------|--------|-------------|
| **Decision quality** | Declaring-only, every bid evaluated | Single-seat v6 comparator | net_eppd, bid_rate (per-hand propensity), make_rate |
| **Full-game** | Declaring + defending, auction winners only | H2H battery v4 (self-play + cross-matchups) | W/L/D record, net_eppd_delta, dominance order |

**Key difference:** The single-seat comparator evaluates *every* hand (bid or
pass), and pass deals contribute zero to the numerator but count in the
denominator. The H2H battery evaluates only auction winners' outcomes and
measures the *relative* delta between two bidders competing on the same deals.

**H2H bid_rate note:** In H2H context, bid_rate measures team auction-win
frequency (the fraction of deals where a team's bidder wins the auction and
declares), not the per-hand bid propensity measured by the comparator. These
are different estimands: comparator bid_rate reflects a bidder's willingness
to bid; H2H bid_rate reflects the outcome of a contested auction.

### 2.2 Decision-Quality Track (Single-Seat v6 Comparator)

Each bidder plays 20,000 deals (5,000/seat x 4 seats) against AlwaysPassBidder
sentinels with GluttonStrategy card play. Rankings by absolute net_eppd.

| Rank | Bidder | net_eppd | 95% CI | bid_rate | make_rate |
|------|--------|----------|--------|----------|-----------|
| 1 | hybrid_olsa_full | +2.170 | [+2.081, +2.257] | 0.968 | 1.000 |
| 2 | hybrid_olsa | +2.131 | [+2.042, +2.216] | 0.961 | 1.000 |
| 3 | modeloespecifico | +1.604 | [+1.489, +1.720] | 1.000 | 0.947 |
| 4 | stricthellraiser | +0.085 | [-0.027, +0.197] | 1.000 | 0.945 |
| 5 | olsa_full | -0.012 | [-0.193, +0.173] | 1.000 | 0.772 |
| 6 | olsa | -0.225 | [-0.413, -0.037] | 1.000 | 0.756 |
| 7 | fiveheadfred | -2.579 | [-2.771, -2.384] | 1.000 | 0.649 |
| 8 | rankthetank | -9.665 | [-9.851, -9.483] | 1.000 | 0.150 |

Source: [comparator_rankings.md](comparator_rankings.md) v6, comparator_cis_r0_v6.json.

### 2.3 Full-Game Track (H2H Battery)

Pairwise head-to-head matchups at paired-deal resolution (FULL: 10,000 deals;
QUICK: 2,000 deals). Rankings by win/loss/draw record and dominance structure.

**Dominance structure (FULL, 10k deals, trained-bidder subset):**

```
modeloespecifico  >  hybrid_olsa_full  ~  hybrid_olsa  >  olsa  ~  olsa_full
                         ^                    ^
                         |____________________|
                           (not separated)
```

modelo beats all four trained bidders. hybrid_olsa_full and hybrid_olsa are
indistinguishable from each other but beat olsa (in at least one direction).
olsa and olsa_full are indistinguishable.

**Key pairwise results (FULL, 10k deals):**

| A vs B | delta | 95% CI | Verdict |
|--------|-------|--------|---------|
| modelo vs hybrid_olsa | +0.252 | [+0.153, +0.352] | modelo wins |
| modelo vs hybrid_olsa_full | +0.165 | [+0.064, +0.265] | modelo wins |
| hybrid_olsa vs olsa | +0.071 | [-0.065, +0.204] | Draw |
| hybrid_olsa_full vs olsa | +0.137 | [+0.000, +0.270] | hybrid_full wins |
| hybrid_olsa vs olsa_full | -0.065 | [-0.200, +0.064] | Draw |
| hybrid_olsa_full vs olsa_full | +0.000 | [-0.135, +0.131] | Draw |
| olsa_full vs olsa | -0.028 | [-0.168, +0.109] | Draw |
| hybrid_olsa_full vs hybrid_olsa | -0.002 | [-0.088, +0.082] | Draw |
| modelo vs olsa | +0.135 | [+0.002, +0.267] | modelo wins |
| modelo vs olsa_full | +0.032 | [-0.101, +0.158] | Draw |

The asymmetric matchups (bidder_a as team0 vs team1) sometimes yield different
verdicts — this reflects the paired-deal design where team position affects
which deals each team declares on. The table above shows one direction per pair;
the reverse direction is consistent in sign but may differ in significance for
marginal cases.

**Self-play diagnostics (FULL, 10k deals):**

| Bidder | fullgame_eppd | fullgame_cvar_5 |
|--------|---------------|-----------------|
| hybrid_olsa | 4.894 | -0.621 |
| hybrid_olsa_full | 4.890 | -0.719 |
| modeloespecifico | 4.691 | -3.221 |
| olsa | 3.714 | -6.505 |
| olsa_full | 3.747 | -6.535 |
| stricthellraiser | 2.150 | -6.000 |
| fiveheadfred | 3.540 | -5.000 |
| rankthetank | -1.645 | -9.563 |

hybrid_olsa self-play eppd (4.894) exceeds modeloespecifico (4.691) by +0.203.
This reversal from the comparator (where modelo ranked higher in v4) is
significant: in H2H self-play, hybrid_olsa's bid-level search produces higher
total game value than modelo's formula-based approach.

**W/L/D summary (QUICK, 56 cross-matchup cells, 2k deals):**

| Bidder | W | L | D |
|--------|---|---|---|
| modeloespecifico | 11 | 0 | 3 |
| hybrid_olsa_full | 7 | 2 | 5 |
| hybrid_olsa | 7 | 2 | 5 |
| olsa_full | 7 | 0 | 7 |
| olsa | 5 | 4 | 5 |
| fiveheadfred | 4 | 9 | 1 |
| rankthetank | 2 | 12 | 0 |
| stricthellraiser | 0 | 14 | 0 |

Source: [h2h_battery_analysis.md](h2h_battery_analysis.md), h2h_battery_quick_v4.json / h2h_battery_full_v4.json.

### 2.4 Track Agreement/Disagreement Analysis

**Where the tracks agree:**

1. **Top 3 bidders are consistent.** Both tracks rank the hybrid variants and
   modeloespecifico at the top. The comparator places hybrid_olsa_full and
   hybrid_olsa above modeloespecifico (+0.527, p<0.001), while H2H places
   modeloespecifico above both hybrids (+0.165 to +0.252, CIs exclude zero).
   The reversal is notable (see disagreement #1 below) but the three bidders
   consistently separate from the rest of the field in both tracks.

2. **Tier separation is preserved.** Both tracks show a large gap between
   the trained bidders (modeloespecifico, hybrid variants, olsa variants) and
   the simple heuristics (fiveheadfred, rankthetank). The tier boundary is
   the strongest signal in both instruments.

3. **olsa_full ~ olsa.** Both tracks find olsa_full and olsa
   indistinguishable: comparator (+0.213, p=0.110) and H2H (-0.028, CI spans
   zero). The forward-selected features provide no detectable advantage in
   either instrument.

4. **hybrid_olsa_full ~ hybrid_olsa.** Both tracks confirm these two bidders
   are statistically identical: comparator (+0.038, p=0.546) and H2H (-0.002,
   CI spans zero). The feature-set difference does not matter at R0 model
   quality.

**Where the tracks disagree:**

1. **Comparator vs H2H ranking reversal for hybrid vs modelo.** The comparator
   places hybrid_olsa above modeloespecifico (+0.527, p<0.001), while H2H
   places modeloespecifico above hybrid_olsa (+0.252, CI [+0.153, +0.352]).
   This is a genuine ranking reversal. The mechanism: in uncontested auctions
   (comparator), hybrid_olsa's bid-level search finds profitable contracts
   that modelo's formula misses (hybrid net_eppd +2.131 vs modelo +1.604).
   In contested auctions (H2H), modelo's multi-contract evaluation gives it
   an edge in head-to-head competition where auction dynamics matter.

2. **stricthellraiser: rank 4 (comparator) vs rank 8 (H2H).** The most
   dramatic disagreement, consistent with v4. In single-seat mode,
   stricthellraiser always bids 3 Spades (degenerate operating point with
   `current_high_bid=0`), achieving a near-trivial positive net_eppd (+0.085).
   In H2H, it faces contested auctions and its raise-the-stakes rule produces
   0W-14L-0D. This disagreement is **estimand-driven**: the comparator
   measures an operating point that never occurs in real play.

3. **olsa_full vs modeloespecifico divergence.** In the comparator,
   modeloespecifico leads olsa_full by +1.616 net_eppd. In H2H (FULL),
   modeloespecifico vs olsa_full is a draw (+0.032, CI spans zero). The
   comparator gap is driven by how each bidder interacts with
   GluttonStrategy's play patterns in uncontested auctions, while H2H's
   contested auction narrows the difference because both bidders' effective
   bid rates converge under competition.

**Interpretation:** Track disagreements arise from two sources:

- **Estimand difference.** The comparator evaluates every deal; H2H evaluates
  only auction-winning deals. The hybrid vs modelo reversal reflects that
  bid-level search's advantage (finding profitable low bids on marginal hands)
  is strongest in uncontested auctions, where those marginal hands are actually
  bid. In H2H, the opponent may outbid on those same hands, removing the
  advantage.
- **Auction interaction.** In H2H, modeloespecifico's formula-based
  multi-contract evaluation produces more competitive auction behavior than
  the hybrid variants' model-based approach. The hybrid bidders bid on ~96% of
  hands in isolation but only win ~42-49% of H2H auctions against modelo,
  suggesting modelo outbids them on contested hands.

---

## 3. Archetype Classification

### 3.1 Archetype Definitions

Archetypes are derived from **single-seat comparator data only** — specifically
`bid_rate` (per-hand propensity) and `make_rate` (conditional on bidding).

**CRITICAL:** These archetypes must NOT be derived from H2H `bid_rate`, which
measures team auction-win frequency (a different estimand). In H2H, bid_rate
reflects the outcome of a contested auction, not the bidder's propensity to
bid on a given hand.

| Archetype | Criterion (single-seat) | R0 Bidders |
|-----------|------------------------|------------|
| **AGGRESSIVE** | bid_rate > 0.95 AND make_rate < 0.65 | fiveheadfred, rankthetank |
| **SELECTIVE** | bid_rate < 0.50 | (none in v6 — was hybrid_olsa in v4) |
| **NEUTRAL** | bid_rate > 0.95 AND make_rate >= 0.65 | hybrid_olsa, hybrid_olsa_full, stricthellraiser, olsa, olsa_full |

**Override:** modeloespecifico -> SELECTIVE-dagger (formal criteria = NEUTRAL; override
justified in S3.2 assignment table). Threshold criteria are intentionally coarse for
R0's 8-bidder roster; a continuous selectivity metric may replace them at R1+.

**v4->v6 archetype shift:** In v4, hybrid_olsa was the sole SELECTIVE bidder
(bid_rate=0.197). With bid-level search in v6, hybrid_olsa's bid_rate jumped
to 0.961 and make_rate to 1.000, moving it firmly into the NEUTRAL archetype.
The SELECTIVE archetype is now EMPTY (no bidder has bid_rate < 0.50) except
for the modeloespecifico override. This collapse of the SELECTIVE archetype
reflects the effectiveness of bid-level search: the Gaussian CDF wrapper no
longer needs to pass on 80% of hands to maintain high make_rate.

### 3.2 Archetype Assignment Table

| Bidder | bid_rate | make_rate | Archetype | Notes |
|--------|----------|-----------|-----------|-------|
| hybrid_olsa_full | 0.968 | 1.000 | NEUTRAL | Bid-level search; was not in v4 roster |
| hybrid_olsa | 0.961 | 1.000 | NEUTRAL | Was SELECTIVE in v4 (bid_rate=0.197); bid-level search |
| modeloespecifico | 1.000 | 0.947 | SELECTIVE-dagger | Override: formally NEUTRAL by threshold; see note below |
| stricthellraiser | 1.000 | 0.945 | NEUTRAL | Degenerate single-seat mode (always bids 3S) |
| olsa_full | 1.000 | 0.772 | NEUTRAL | Floor-based threshold, always bids |
| olsa | 1.000 | 0.756 | NEUTRAL | Floor-based threshold, always bids |
| fiveheadfred | 1.000 | 0.649 | AGGRESSIVE | Always bids 5S, wins 2/3 |
| rankthetank | 1.000 | 0.150 | AGGRESSIVE | Catastrophic overbidding post-recalibration |

**dagger-Note on modeloespecifico override:** The formal threshold criteria
(bid_rate > 0.95 AND make_rate >= 0.65) place modeloespecifico in NEUTRAL.
It is overridden to SELECTIVE based on three quantitative observations:

1. **Multi-contract evaluation:** evaluates all 6 contracts per hand with a
   quality threshold (min score >= 3), unlike NEUTRAL bidders that bid
   unconditionally on a single contract
2. **Highest make_rate among always-bid bidders (0.947):** exceeds all
   NEUTRAL bidders (0.756-0.945), consistent with quality-gated bid selection
3. **Highest net_eppd among always-bid bidders (+1.604):** 19x the next
   NEUTRAL bidder (stricthellraiser +0.085), suggesting its hand evaluation
   filters out marginally unprofitable bids

The bid_rate=1.000 (was 0.986 in v4) means modeloespecifico now bids on every
deal, but its bid *quality* remains selective. The override captures the
qualitative distinction between "always bids something" and "always bids
the same thing" (stricthellraiser) or "always bids floor(mu)"
(olsa variants).

### 3.3 H2H Performance by Opponent Archetype

Mean H2H net_eppd_delta by row bidder when facing each opponent archetype
class. Positive values mean the row bidder outperforms the column archetype.
Values aggregated from QUICK (2k deals/cell) W/L/D data. Self-play matchups
excluded.

| Bidder | vs AGGRESSIVE | vs NEUTRAL | vs SELECTIVE-dagger |
|--------|---------------|------------|---------------------|
| **hybrid_olsa_full** | Wins all | Draws (hybrid_olsa, olsa, olsa_full); wins stricthellraiser | Loses to modelo |
| **hybrid_olsa** | Wins all | Draws (hybrid_full, olsa, olsa_full); wins stricthellraiser | Loses to modelo |
| **modeloespecifico** | Wins all | Wins or draws (trained); wins stricthellraiser | -- |
| **olsa_full** | Wins all | Draws | Draws (modelo) |
| **olsa** | Wins all | Draws | Draws or loses (modelo) |
| **stricthellraiser** | Loses all | Loses all | Loses all |
| **fiveheadfred** | -- | Loses to trained | Loses |
| **rankthetank** | -- | Loses to all | Loses |

**Key patterns:**

1. **All trained bidders dominate AGGRESSIVE opponents.** The gap is enormous
   (deltas +1 to +10 net_eppd). AGGRESSIVE bidders' overbidding creates easy
   wins for any calibrated opponent.

2. **NEUTRAL-vs-NEUTRAL matchups are the tightest.** The trained bidders
   (hybrid variants, olsa, olsa_full) cluster within draw range when facing
   each other. This is where the H2H diverges most from the comparator:
   the comparator separates hybrid_olsa (+2.131) from olsa (-0.225) by
   2.356 net_eppd, but in H2H they draw (+0.071, CI spans zero).

3. **stricthellraiser's H2H collapse is archetype-independent.** It loses
   to every opponent class — its raise-the-stakes rule fails in all contested
   auctions, not just against specific archetypes. The 0W-14L-0D record is
   total.

4. **Hybrid variants and olsa_full converge under competition.** Despite the
   comparator's 2+ point gap, hybrid_olsa and olsa_full draw in H2H
   (-0.065, CI spans zero). The bid-level search advantage that dominates
   in uncontested auctions vanishes when the opponent's bids determine which
   contracts are actually played.

---

## 4. Roster Meta-Analysis Scatter Plots

Three scatter plots decompose the decision-quality rankings into behavioral
components. All data from single-seat comparator v6 (decision-quality
estimand). Points labeled by bidder name, colored by archetype.

### 4.1 Calibration: bid_rate x make_rate

```
Chart: plot_roster_calibration(df)
Source: diagnostics.strategy_charts.plot_roster_calibration
```

**What it shows:** Who overbids vs who is well-calibrated. A "perfect"
bidder appears in the top-left (selective, high make_rate) or top-right
(bids often, still makes). Bottom-right indicates overbidding.

**R0 v6 observations:**

- **hybrid_olsa and hybrid_olsa_full** occupy the ideal top-right position:
  bid_rate 0.96-0.97 with make_rate=1.000. This is a dramatic shift from v4,
  where hybrid_olsa was in the top-left (bid_rate=0.197, make_rate=0.886).
  Bid-level search moved hybrid_olsa from "selective with occasional misses"
  to "near-universal with perfect accuracy."
- **modeloespecifico** clusters near the hybrid variants in the top-right:
  bid_rate=1.000, make_rate=0.947. The three top performers form a tight
  cluster — a qualitative change from v4 where modelo was the sole top-right
  occupant and hybrid_olsa was isolated in the top-left.
- **stricthellraiser** (make_rate=0.945) is surprisingly close to
  modeloespecifico in calibration space, but its degenerate "always 3 Spades"
  mode means this is an artifact of the low bid level, not genuine calibration.
- **olsa_full and olsa** form a NEUTRAL cluster at (1.0, ~0.76) — always
  bid, moderate make_rate.
- **fiveheadfred** and **rankthetank** anchor the bottom-right: always bid,
  low make_rate. rankthetank's make_rate (0.150) is catastrophically low.

### 4.2 Efficiency: bid_rate x net_eppd

```
Chart: plot_roster_efficiency(df)
Source: diagnostics.strategy_charts.plot_roster_efficiency
```

**What it shows:** The payoff curve of selectivity. Answers whether it is
better to bid rarely and make most, or bid often and accept sets.

**R0 v6 observations:**

- The v4 "non-monotonic relationship" between bid_rate and net_eppd has
  collapsed. In v4, both extremes worked: modeloespecifico (high volume,
  high net_eppd) and hybrid_olsa (low volume, moderate net_eppd). In v6, the
  top three bidders all cluster at bid_rate > 0.96 with net_eppd > +1.6.
  **High-volume, high-accuracy bidding now dominates.**
- The NEUTRAL cluster (bid_rate~1.0, net_eppd near zero) remains the
  "default" operating point where undiscriminating bidding barely breaks even.
- **Below the NEUTRAL cluster**, AGGRESSIVE bidders show that bidding
  everything without quality filtering destroys value. rankthetank
  (net_eppd=-9.665) demonstrates the floor.
- **The lesson has changed.** In v4, the gap to close was "how to make hybrid
  bid more often while keeping accuracy." In v6, bid-level search solved that
  problem entirely. The remaining gap (modelo vs hybrid in H2H) is about
  auction competition, not bid frequency.

### 4.3 Conversion: make_rate x net_eppd

```
Chart: plot_roster_conversion(df)
Source: diagnostics.strategy_charts.plot_roster_conversion
```

**What it shows:** Who turns makes into points efficiently. Two bidders with
the same make_rate can have different net_eppd if bid levels differ.

**R0 v6 observations:**

- **Strong positive correlation** between make_rate and net_eppd across the
  roster, consistent with v4. Higher make_rate translates directly into higher
  net_eppd.
- **hybrid_olsa and hybrid_olsa_full** are now the outliers: their
  make_rate=1.000 maps to net_eppd of +2.1, higher than modeloespecifico's
  make_rate=0.947 / net_eppd=+1.604. The hybrid variants convert makes into
  points more efficiently because bid-level search optimizes bid level, not
  just whether to bid.
- **modeloespecifico** falls slightly below the hybrid variants despite having
  make_rate=0.947. The 5.3% set rate (compared to 0% for hybrids) costs it
  roughly 0.5 net_eppd, accounting for most of the comparator gap.
- **olsa and olsa_full** have similar make_rates (0.756 vs 0.772) and similar
  net_eppd (-0.225 vs -0.012) — their floor-based thresholds produce nearly
  identical conversion efficiency.
- **rankthetank** anchors the bottom-left: the lowest make_rate (0.150) maps
  to the worst net_eppd (-9.665). At 15% make_rate, sets are nearly 6x more
  frequent than makes.

---

## 5. Discussion

### 5.1 What the Dual-Track Tells Us

The two evaluation tracks provide complementary views:

- The **comparator** is the *exam*: it tests whether a bidder can identify
  profitable hands in isolation. It answers "is this bidder any good?"
- The **H2H** is the *tournament*: it tests whether a bidder wins when
  facing a real opponent. It answers "which bidder is better?"

At R0, the key insight is that **the exam and tournament now disagree on the
top performer**: the comparator says hybrid_olsa > modeloespecifico (+0.527),
while H2H says modeloespecifico > hybrid_olsa (+0.252). This is a new dynamic
in v6 — in v4, both tracks agreed that modeloespecifico was best.

The reversal reveals that bid-level search's primary advantage — finding
profitable low bids on marginal hands — is strongest in the exam (uncontested
auctions where all marginal hands are actually bid) and weaker in the
tournament (contested auctions where the opponent may outbid on those hands).

### 5.2 Implications for R1

1. **The comparator gap is closed (and reversed).** hybrid_olsa (+2.131) now
   beats modeloespecifico (+1.604) by +0.527 in the comparator. The v4 target
   of "close the 1.132 gap" was achieved through bid-level search, not model
   quality improvements.

2. **The H2H gap remains.** modeloespecifico still beats hybrid_olsa in H2H
   (+0.252, CI [+0.153, +0.352]). The remaining R1+ target is competitive
   auction performance, which requires either better model predictions
   (reducing the information gap vs modelo's hand-coded formula) or
   auction-aware bidding (adjusting for `current_high_bid > 0`).

3. **Self-play eppd favors hybrid.** hybrid_olsa's self-play eppd (4.894) is
   the highest in the roster, exceeding modeloespecifico (4.691) by +0.203.
   This means hybrid_olsa produces more total game value when both teams use
   it — the bid-level search creates higher-quality declared contracts. The
   H2H delta loss (-0.252 to -0.455 when hybrid faces modelo) is driven by
   auction dynamics, not intrinsic game quality.

4. **The full-arm features remain irrelevant at R0.** Both tracks confirm
   hybrid_olsa_full ~ hybrid_olsa (comparator: p=0.546; H2H: draw). R1's
   model improvement should focus on prediction accuracy and auction awareness,
   not feature richness.

### 5.3 Archetype Utility

The archetype classification has changed character in v6:

- **SELECTIVE is now empty.** The hybrid variants' migration from SELECTIVE to
  NEUTRAL means the classification no longer distinguishes the top performers.
  The archetype system may need revision at R1+ to capture the quality
  distinction between "bids often with high accuracy" (hybrid variants) vs
  "bids often with moderate accuracy" (olsa variants).
- **The NEUTRAL archetype is overloaded.** It now contains five bidders with
  very different performance levels (hybrid_olsa at +2.131 vs olsa at -0.225).
  A continuous metric (e.g., net_eppd or make_rate) would better capture the
  variation within this archetype.
- **Regression testing value is preserved.** When adding a new bidder at R1,
  its H2H performance against each archetype class still provides a behavioral
  fingerprint: does it exploit AGGRESSIVE opponents? Can it compete with the
  high-accuracy NEUTRAL cluster?

---

## 6. Provenance

| Item | Value |
|------|-------|
| gate_status | PROMOTED |
| Comparator data | comparator_cis_r0_v6.json (single-seat, GluttonStrategy) |
| H2H data (QUICK) | h2h_battery_quick_v4.json (56 cross-matchup cells, 2k deals/cell) |
| H2H data (FULL) | h2h_battery_full_v4.json (44 cross-matchup cells, 10k deals/cell) |
| Archetype source | Single-seat comparator bid_rate + make_rate (NOT H2H) |
| Chart code | `src/bid_euchre/diagnostics/strategy_charts.py` |
| Chart functions | `plot_roster_calibration`, `plot_roster_efficiency`, `plot_roster_conversion` |
| Play strategy | GluttonStrategy (both tracks, harmonized by C2c/#466) |
| Seed | 42 |
| Related reports | [comparator_rankings.md](comparator_rankings.md), [h2h_battery_analysis.md](h2h_battery_analysis.md) |
