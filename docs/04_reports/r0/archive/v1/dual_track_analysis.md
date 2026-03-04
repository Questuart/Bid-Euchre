# R0 Dual-Track Analysis: Decision Quality vs Full-Game Performance

> **⚠ SUPERSEDED** — This is the v1 version, archived for reference.
> The current version is at [`../06_dual_track_analysis.md`](../06_dual_track_analysis.md).
> See [README.md](README.md) for the v1→v2 delta summary.

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-01
**Purpose:** Side-by-side analysis of two complementary evaluation tracks,
archetype classification, and roster meta-analysis

---

## 1. Summary

This report presents two independent evaluation tracks for the seven R0
bidders and analyzes where they agree and disagree. The two tracks measure
fundamentally different things:

- **Decision quality** (single-seat comparator): evaluates every bid/pass
  decision in isolation, producing absolute net_eppd scores.
- **Full-game** (H2H battery): evaluates competitive performance including
  both bidding and defending, producing pairwise win/loss/draw verdicts.

Both tracks use GluttonStrategy for card play (harmonized by C2c/#466),
making track disagreements primarily **estimand-driven** rather than
confounded by play quality differences.

The analysis also classifies bidders into three behavioral archetypes
(AGGRESSIVE, NEUTRAL, SELECTIVE) derived from single-seat comparator data,
and presents three scatter plots decomposing rankings into behavioral
components.

---

## 2. Dual-Track Rankings

### 2.1 Track Definitions

| Track | Estimand | Source | Key Metrics |
|-------|----------|--------|-------------|
| **Decision quality** | Declaring-only, every bid evaluated | Single-seat v4 comparator | net_eppd, bid_rate (per-hand propensity), make_rate |
| **Full-game** | Declaring + defending, auction winners only | H2H battery (self-play + cross-matchups) | W/L/D record, net_eppd_delta, dominance order |

**Key difference:** The single-seat comparator evaluates *every* hand (bid or
pass), and pass deals contribute zero to the numerator but count in the
denominator. The H2H battery evaluates only auction winners' outcomes and
measures the *relative* delta between two bidders competing on the same deals.

### 2.2 Decision-Quality Track (Single-Seat v4 Comparator)

Each bidder plays 20,000 deals (5,000/seat x 4 seats) against AlwaysPassBidder
sentinels with GluttonStrategy card play. Rankings by absolute net_eppd.

| Rank | Bidder | net_eppd | 95% CI | bid_rate | make_rate |
|------|--------|----------|--------|----------|-----------|
| 1 | modeloespecifico | +1.587 | [+1.529, +1.645] | 0.986 | 0.947 |
| 2 | hybrid_olsa | +0.455 | [+0.420, +0.491] | 0.197 | 0.886 |
| 3 | stricthellraiser | +0.076 | [+0.018, +0.132] | 1.000 | 0.943 |
| 4 | olsa_full | -0.168 | [-0.260, -0.078] | 1.000 | 0.763 |
| 5 | olsa | -0.342 | [-0.435, -0.250] | 1.000 | 0.749 |
| 6 | fiveheadfred | -2.570 | [-2.667, -2.473] | 1.000 | 0.649 |
| 7 | rankthetank | -9.767 | [-9.857, -9.675] | 1.000 | 0.145 |

Source: [comparator_rankings.md](comparator_rankings.md) v4, `comparator_cis_r0_v4.json`.

### 2.3 Full-Game Track (H2H Battery)

Pairwise head-to-head matchups at paired-deal resolution (FULL: 10,000 deals;
QUICK: 2,000 deals). Rankings by win/loss/draw record and dominance structure.

**Dominance structure (FULL, 10k deals):**

```
modeloespecifico  >  hybrid_olsa  >  olsa  ~  olsa_full
                                      ^         ^
                                      |_________|
                                     (not separated)
```

**Key pairwise results (FULL):**

| A vs B | delta | 95% CI | Verdict |
|--------|-------|--------|---------|
| modeloespecifico vs hybrid_olsa | +0.644 | [+0.545, +0.743] | modelo wins |
| hybrid_olsa vs olsa | +0.147 | [+0.014, +0.276] | hybrid wins |
| hybrid_olsa vs olsa_full | +0.033 | [-0.101, +0.160] | Draw |
| olsa_full vs olsa | -0.028 | [-0.168, +0.109] | Draw |
| modeloespecifico vs olsa | +0.016 | [-0.117, +0.147] | Draw |
| modeloespecifico vs olsa_full | -0.081 | [-0.214, +0.044] | Draw |

**W/L/D summary (QUICK, 49 cells, 2k deals):**

| Bidder | W | L | D |
|--------|---|---|---|
| modeloespecifico | 9 | 0 | 3 |
| hybrid_olsa | 7 | 2 | 3 |
| olsa_full | 7 | 0 | 5 |
| olsa | 5 | 3 | 4 |
| fiveheadfred | 4 | 7 | 1 |
| rankthetank | 2 | 10 | 0 |
| stricthellraiser | 0 | 12 | 0 |

Source: [h2h_battery_analysis.md](h2h_battery_analysis.md) SS4-4.

### 2.4 Track Agreement/Disagreement Analysis

**Where the tracks agree:**

1. **Top 2 ordering is consistent.** Both tracks rank modeloespecifico first
   and hybrid_olsa second. The H2H confirms the comparator gap (+0.644 to +0.777
   net_eppd_delta, CI excludes zero in both directions).

2. **Tier separation is preserved.** Both tracks show a large gap between
   the trained bidders (modeloespecifico, hybrid_olsa, olsa, olsa_full) and
   the simple heuristics (fiveheadfred, rankthetank). The tier boundary is
   the strongest signal in both instruments.

3. **hybrid_olsa > olsa.** The C33 wrapper effect is confirmed in both
   tracks: comparator (+0.797 net_eppd gap) and H2H (+0.147 delta, CI
   excludes zero).

**Where the tracks disagree:**

1. **stricthellraiser: rank 3 (comparator) vs rank 7 (H2H).** The most
   dramatic disagreement. In single-seat mode, stricthellraiser always bids
   3 Spades (degenerate operating point with `current_high_bid=0`), achieving
   a near-trivial positive net_eppd (+0.076). In H2H, it faces contested
   auctions and its raise-the-stakes rule produces 0W-12L-0D. This
   disagreement is **estimand-driven**: the comparator measures an operating
   point that never occurs in real play.

2. **modeloespecifico vs olsa: +1.929 gap (comparator) vs draw (H2H).** In
   self-play, modeloespecifico leads olsa by +1.929 net_eppd — but in H2H
   the difference is not significant (+0.016, CI spans zero). This suggests
   the comparator gap is driven by how each bidder interacts with
   GluttonStrategy's play patterns (a confound even after play-strategy
   harmonization), not by intrinsic superiority in contested auctions.

3. **olsa_full ranking: rank 4 (comparator) vs rank 2-3 by W/L/D (H2H).**
   olsa_full ranks above olsa in the comparator (+0.174, p=0.009) but the
   two are indistinguishable in H2H (-0.028, CI spans zero). The 39 extra
   features help against GluttonStrategy sentinels but do not translate to
   competitive advantage against peer bidders.

**Interpretation:** Track disagreements arise from two sources:

- **Estimand difference.** The comparator evaluates every deal; H2H evaluates
  only auction-winning deals. Bidders with extreme bid_rates (stricthellraiser,
  fiveheadfred) are evaluated on fundamentally different deal populations.
- **Residual confound.** Even with GluttonStrategy harmonization, the
  comparator's uncontested auction creates a different decision context than
  H2H's contested auction. The modeloespecifico vs olsa divergence is likely
  driven by this residual confound.

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
| **SELECTIVE** | bid_rate < 0.50 | hybrid_olsa |
| **NEUTRAL** | bid_rate > 0.95 AND make_rate >= 0.65 | stricthellraiser, olsa, olsa_full |

**Override:** modeloespecifico → SELECTIVE† (formal criteria = NEUTRAL; override
justified in §3.2 assignment table). Threshold criteria are intentionally coarse for
R0's 7-bidder roster; a continuous selectivity metric may replace them at R1+.

### 3.2 Archetype Assignment Table

| Bidder | bid_rate | make_rate | Archetype | Notes |
|--------|----------|-----------|-----------|-------|
| modeloespecifico | 0.986 | 0.947 | SELECTIVE† | Override: formally NEUTRAL by threshold; see note below |
| hybrid_olsa | 0.197 | 0.886 | SELECTIVE | Only 19.7% of hands pass risk threshold |
| stricthellraiser | 1.000 | 0.943 | NEUTRAL | Degenerate single-seat mode (always bids 3S) |
| olsa_full | 1.000 | 0.763 | NEUTRAL | Floor-based threshold, always bids |
| olsa | 1.000 | 0.749 | NEUTRAL | Floor-based threshold, always bids |
| fiveheadfred | 1.000 | 0.649 | AGGRESSIVE | Always bids 5S, wins 2/3 |
| rankthetank | 1.000 | 0.145 | AGGRESSIVE | Catastrophic overbidding post-recalibration |

**†Note on modeloespecifico override:** The formal threshold criteria
(bid_rate > 0.95 AND make_rate >= 0.65) place modeloespecifico in NEUTRAL.
It is overridden to SELECTIVE based on three quantitative observations:

1. **Multi-contract evaluation:** evaluates all 6 contracts per hand with a
   quality threshold (min score ≥ 3), unlike NEUTRAL bidders that bid
   unconditionally on a single contract
2. **Highest make_rate (0.947):** exceeds all NEUTRAL bidders (0.749–0.943),
   consistent with quality-gated bid selection
3. **Highest net_eppd (+1.587):** 3.5× the next NEUTRAL bidder, suggesting
   its hand evaluation filters out marginally unprofitable bids

The 1.4% pass rate (276/20,000 deals unprofitable) is small but non-zero —
modeloespecifico does reject hands. Its behavioral profile is qualitatively
distinct from the NEUTRAL cluster (always-bid, moderate make_rate).

### 3.3 H2H Performance by Opponent Archetype

Mean H2H net_eppd_delta by row bidder when facing each opponent archetype
class. Positive values mean the row bidder outperforms the column archetype.
Values aggregated from QUICK (2k deals/cell) W/L/D data. Self-play matchups
excluded.

| Bidder | vs AGGRESSIVE | vs NEUTRAL | vs SELECTIVE |
|--------|---------------|------------|--------------|
| **modeloespecifico** | Wins all | Draws (olsa, olsa_full); wins rest | -- |
| **hybrid_olsa** | Wins all | Wins (olsa); draws (olsa_full, stricthellraiser) | Loses to modelo |
| **olsa_full** | Wins all | Draws | Draws (modelo, hybrid) |
| **olsa** | Wins all | Draws | Draws (modelo); loses to hybrid |
| **stricthellraiser** | Loses all | Loses all | Loses all |
| **fiveheadfred** | -- | Loses to trained | Loses to both |
| **rankthetank** | -- | Loses to all | Loses to both |

**Key patterns:**

1. **All trained bidders dominate AGGRESSIVE opponents.** The gap is enormous
   (deltas +1 to +8 net_eppd). AGGRESSIVE bidders' overbidding creates easy
   wins for any calibrated opponent.

2. **NEUTRAL opponents are the tightest matchups.** The trained bidders
   (modelo, hybrid, olsa, olsa_full) cluster within draw range when facing
   each other. This is where the H2H diverges most from the comparator.

3. **stricthellraiser's H2H collapse is archetype-independent.** It loses
   to every opponent class — its raise-the-stakes rule fails in all contested
   auctions, not just against specific archetypes.

---

## 4. Roster Meta-Analysis Scatter Plots

Three scatter plots decompose the decision-quality rankings into behavioral
components. All data from single-seat comparator v4 (decision-quality
estimand). Points labeled by bidder name, colored by archetype.

### 4.1 Calibration: bid_rate x make_rate

```
Chart: plot_roster_calibration(df)
Source: diagnostics.strategy_charts.plot_roster_calibration
```

**What it shows:** Who overbids vs who is well-calibrated. A "perfect"
bidder appears in the top-left (selective, high make_rate) or top-right
(bids often, still makes). Bottom-right indicates overbidding.

**R0 observations:**

- **modeloespecifico** occupies the ideal top-right position: bids on 98.6%
  of hands while making 94.7% — near-perfect calibration.
- **hybrid_olsa** is in the top-left: extreme selectivity (19.7% bid_rate)
  with 88.6% make_rate. The Gaussian CDF wrapper is conservative.
- **stricthellraiser, olsa_full, olsa** form a NEUTRAL cluster in the
  center-right (always bids, make_rate 0.75-0.94).
- **fiveheadfred** and **rankthetank** anchor the bottom-right: always bid,
  low make_rate. rankthetank's make_rate (0.145) is catastrophically low.

### 4.2 Efficiency: bid_rate x net_eppd

```
Chart: plot_roster_efficiency(df)
Source: diagnostics.strategy_charts.plot_roster_efficiency
```

**What it shows:** The payoff curve of selectivity. Answers whether it is
better to bid rarely and make most, or bid often and accept sets.

**R0 observations:**

- The plot reveals a **non-monotonic relationship** between bid_rate and
  net_eppd. Both extremes can work: modeloespecifico (bid_rate=0.986,
  net_eppd=+1.587) and hybrid_olsa (bid_rate=0.197, net_eppd=+0.455)
  achieve positive net_eppd via different mechanisms.
- The NEUTRAL cluster (bid_rate~1.0, net_eppd near zero) represents the
  "default" operating point where undiscriminating bidding barely breaks even.
- **Below the NEUTRAL cluster**, AGGRESSIVE bidders show that bidding
  everything without quality filtering destroys value. rankthetank
  (net_eppd=-9.767) demonstrates the floor.
- **The gap to close:** modeloespecifico shows that high-volume bidding *can*
  be optimal — if the quality filter is good enough. hybrid_olsa's R1+ path
  is to improve its quality filter, not to bid more often.

### 4.3 Conversion: make_rate x net_eppd

```
Chart: plot_roster_conversion(df)
Source: diagnostics.strategy_charts.plot_roster_conversion
```

**What it shows:** Who turns makes into points efficiently. Two bidders with
the same make_rate can have different net_eppd if bid levels differ.

**R0 observations:**

- **Strong positive correlation** between make_rate and net_eppd across the
  roster. Higher make_rate translates directly into higher net_eppd — the
  cost of sets dominates the scoring equation.
- **modeloespecifico** is the outlier: its net_eppd (+1.587) is higher than
  what pure make_rate (0.947) would predict, because it bids at appropriate
  levels (not just "can I make *something*" but "can I make *this many*").
- **olsa and olsa_full** have similar make_rates (0.749 vs 0.763) and similar
  net_eppd (-0.342 vs -0.168) — their floor-based thresholds produce nearly
  identical conversion efficiency.
- **rankthetank** anchors the bottom-left: the lowest make_rate (0.145) maps
  to the worst net_eppd (-9.767). At 14.5% make_rate, sets are 6x more
  frequent than makes.

---

## 5. Discussion

### 5.1 What the Dual-Track Tells Us

The two evaluation tracks provide complementary views:

- The **comparator** is the *exam*: it tests whether a bidder can identify
  profitable hands in isolation. It answers "is this bidder any good?"
- The **H2H** is the *tournament*: it tests whether a bidder wins when
  facing a real opponent. It answers "which bidder is better?"

At R0, the key insight is that **the exam and tournament mostly agree on
the top performers** (modeloespecifico > hybrid_olsa) but **disagree on
the middle tier** (olsa vs olsa_full are separable in the exam but
indistinguishable in the tournament).

### 5.2 Implications for R1

1. **The gap to close is +1.132 net_eppd** (comparator track,
   modeloespecifico vs hybrid_olsa). The H2H gap (+0.644 to +0.777) is
   narrower but still significant.

2. **Selectivity vs accuracy trade-off.** hybrid_olsa bids on 19.7% of
   deals with 88.6% make_rate; modeloespecifico bids on 98.6% with 94.7%
   make_rate. R1 improvements can target either: better pass/bid boundary
   (more accurate selectivity) or better bid-level calibration (higher
   make_rate when bidding).

3. **The full-arm features (olsa_full) help in the exam but not in the
   tournament.** This suggests the 39 features improve calibration against
   GluttonStrategy's specific play patterns, but that advantage vanishes
   under contested auction dynamics.

### 5.3 Archetype Utility

The archetype classification is useful for R1+ in two ways:

- **Regression testing.** When adding a new bidder at R1, its H2H
  performance against each archetype class provides a behavioral fingerprint:
  does it exploit AGGRESSIVE opponents? Can it beat NEUTRALs?
- **Context feature design.** When context-aware bidders arrive (R2+), the
  archetype classification tells us which opponent types matter most for
  bid adjustment.

---

## 6. Provenance

| Item | Value |
|------|-------|
| gate_status | PROMOTED |
| Comparator data | comparator_cis_r0_v4.json (single-seat, GluttonStrategy) |
| H2H data (QUICK) | h2h_battery_quick.json (49 cells, 2k deals/cell) |
| H2H data (FULL) | h2h_battery_full.json (37 cells, 10k deals/cell) |
| Archetype source | Single-seat comparator bid_rate + make_rate (NOT H2H) |
| Chart code | `src/bid_euchre/diagnostics/strategy_charts.py` |
| Chart functions | `plot_roster_calibration`, `plot_roster_efficiency`, `plot_roster_conversion` |
| Play strategy | GluttonStrategy (both tracks, harmonized by C2c/#466) |
| Seed | 42 |
| Related reports | [comparator_rankings.md](comparator_rankings.md), [h2h_battery_analysis.md](h2h_battery_analysis.md) |
