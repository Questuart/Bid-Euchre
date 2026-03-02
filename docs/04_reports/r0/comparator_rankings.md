# R0 Comparator Rankings (v4, Single-Seat, 7 Bidders)

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-02-28 (v4; supersedes v1-v3 in git history)
**Methodology:** Single-seat · 20,000 deals/bidder (5,000/seat × 4 seats) · seed=42 · 10,000 bootstrap resamples · GluttonStrategy card play

## 1. Summary

This report presents the **decision-quality benchmark** for all seven R0
bidders evaluated in the single-seat comparator battery. Each bidder is tested
in isolation — one seat bids while three always-pass sentinels fill the
remaining seats — producing an **absolute** net_eppd score that measures
bidding quality without survivorship bias or auction interaction.

The single-seat comparator answers the question: *"Given every possible deal,
how much value does this bidder's bid-or-pass decision add?"* Every deal is
evaluated (bid or pass), and pass deals contribute zero to the numerator but
count in the denominator. This penalizes excessive passing and rewards
calibrated selectivity.

The rankings establish three clear tiers: two positive-net_eppd bidders
(modeloespecifico, hybrid_olsa), a near-zero middle band
(stricthellraiser, olsa_full, olsa), and two negative-net_eppd bidders
(fiveheadfred, rankthetank). All adjacent pairs are statistically
distinguishable (§5).

For competitive ordering between bidders in contested auctions, see the
[H2H battery analysis](h2h_battery_analysis.md). The comparator and H2H
instruments measure **different estimands** — see §2.4 for what this
methodology captures and what it does not.

## 2. Methodology

### 2.1 Experimental Design

**Single-seat mode.** Each deal is evaluated from one seat at a time. The
bidder under test occupies the target seat; the other three seats use
`AlwaysPassBidder` (never bid, ensuring `current_high_bid=0`). Each bidder is
tested across all four seat positions (5,000 deals per seat, 20,000 deals
total), and results are merged across seats to eliminate positional artifacts.

**Card play.** All trick play uses `GluttonStrategy` for all four seats. This
is the same play strategy used in the H2H battery, eliminating play-strategy
confounds when comparing across instruments.

**Auction.** Sequential auction with `current_high_bid=0`. The test bidder
either bids (choosing contract type, trump suit, and bid level) or passes. No
competing bids exist, so the bidder's decision reflects its evaluation of the
hand in isolation.

### 2.2 Metric Definitions

| Metric | Formula | Scope |
|--------|---------|-------|
| **net_eppd** | `sum(bidder_pts − opponent_pts for bid-hands) / total_deals` | All deals (bid + pass) |
| **eppd** | `sum(bidder_pts for bid-hands) / total_deals` | All deals |
| **bid_rate** | `hands_with_bids / total_deals` | Per-bidder propensity |
| **make_rate** | `bids_made / hands_with_bids` | Conditional on bidding |
| **CVaR-5%** | Mean of worst 5% of bid-hand outcomes | Bid-hands only |
| **net_CVaR-5%** | Mean of worst 5% of per-deal net differentials | All deals |
| **std(net_pts)** | Standard deviation of per-deal net points | All deals (Source B) |

Pass deals contribute 0 to numerator terms but count in denominators. This
means a bidder that passes on every hand scores `net_eppd=0` — the neutral
baseline.

### 2.3 Version History

| Version | Date | Bidders | Deals | Mode | Play Strategy | Changes |
|---------|------|---------|-------|------|---------------|---------|
| v1 | 2026-02-23 | 5 | 10,000 | 4-way | GreedyStrategy | Initial battery |
| v2 | 2026-02-25 | 7 | 10,000 | 4-way | GreedyStrategy | Added olsa_full + olsa; identity clarification |
| v3 | 2026-02-28 | 7 | 20,000 | Single-seat | GreedyStrategy | Bidder fixes A/B/C; single-seat mode |
| **v4** | **2026-02-28** | **7** | **20,000** | **Single-seat** | **GluttonStrategy** | **Play strategy harmonization** |

**v1→v2 identity change:** In v1, `hybrid_olsa` referred to the OLSa_Full
promotional arm (`hybrid_r0_full.json`, bid_rate≈83%). In v2+, `hybrid_olsa`
refers to the constrained arm with Gaussian CDF wrapper (`hybrid_r0.json`),
and `olsa_full` is the full-arm variant.

**v2→v3 changes:** Three bidder fixes merged — (A) ModeloEspecifico bid
ceiling raised from 6 to 10, (B) OLSa bid floor lowered from 3 to 1,
(C) RanktheTank HIGH/LOW thresholds recalibrated and suit ceiling extended to
10. Single-seat mode eliminates auction interaction confounds.

**v3→v4 change:** Play strategy harmonized from GreedyStrategy (implicit
default) to GluttonStrategy (explicit). Both instruments (comparator + H2H)
now use the same card play policy, making track disagreements primarily
estimand-driven rather than confounded by play quality.

### 2.4 What This Measures (and What It Does Not)

**Design:** Each bidder plays independently against GluttonStrategy card play.
There is no competing bidder in the auction — the bidder under test declares
contracts uncontested (`current_high_bid=0`), and Glutton handles all trick
play for both teams.

**Strengths:**

- **Absolute scale.** Provides a common benchmark for answering "is this model
  any good?" A positive net_eppd means the bidder adds value relative to a
  no-bid baseline.
- **Every bid evaluated.** Pass deals count in the denominator, preventing
  survivorship bias. A bidder cannot improve its score by simply avoiding
  difficult hands.
- **Progress tracking.** Enables rung-over-rung comparison against a fixed
  reference point without running O(n²) pairwise matchups.
- **Reproducible exam.** Same deals, same opponent, same conditions — isolates
  the bidding policy as the only variable.

**Limitations:**

- **No auction interaction.** Real games have contested auctions where one
  bidder's bid changes which contracts the opponent gets to play. This battery
  evaluates uncontested bidding — a fundamentally different task. Bidders whose
  behavior depends on `current_high_bid` (e.g., StrictHellRaiser) are
  evaluated only in their opening-bid mode.
- **Confounded by card play.** Rankings reflect how well each bidder interacts
  with GluttonStrategy, not intrinsic bidding quality. A bidder that calibrates
  well for Glutton's play patterns may score differently with other play
  strategies.
- **Self-play rankings may not match competitive ordering.** The H2H battery
  ([h2h_battery_analysis.md](h2h_battery_analysis.md)) shows that some
  self-play gaps do not replicate under direct opposition.

**Bottom line:** Use these rankings for absolute benchmarking and progress
tracking. For competitive ordering between bidders, see the
[H2H battery analysis](h2h_battery_analysis.md).

## 3. Rankings Table

All seven comparator bidders ranked by net_eppd descending. Bootstrap 95%
confidence intervals in brackets.

**Source A** columns derive from the extraction artifact (bootstrap CIs on
JSONL-computed metrics). **Source B** columns derive from notebook
`45_comparator_deep_dive` §S5 (bootstrap CIs on per-deal indicators).

| Rank | Bidder | net_eppd [95% CI]^A | eppd [95% CI]^A | bid_rate^A | make_rate^A | CVaR-5% [95% CI]^A | net_CVaR-5% [95% CI]^A |
|------|--------|---------------------|-----------------|------------|-------------|---------------------|------------------------|
| 1 | modeloespecifico | +1.587 [+1.529, +1.645] | +5.518 [+5.477, +5.557] | 0.986 | 0.947 | −4.614 [−4.725, −4.499] | −11.142 [−11.168, −11.113] |
| 2 | hybrid_olsa | +0.455 [+0.420, +0.491] | +1.098 [+1.058, +1.139] | 0.197 | 0.886 | −6.152 [−6.208, −6.102] | −11.365 [−11.462, −11.274] |
| 3 | stricthellraiser | +0.076 [+0.018, +0.132] | +4.902 [+4.867, +4.935] | 1.000 | 0.943 | −3.000 [−3.000, −3.000] | −11.281 [−11.318, −11.245] |
| 4 | olsa_full | −0.168 [−0.260, −0.078] | +3.782 [+3.709, +3.855] | 1.000 | 0.763 | −6.284 [−6.318, −6.250] | −12.320 [−12.359, −12.283] |
| 5 | olsa | −0.342 [−0.435, −0.250] | +3.623 [+3.548, +3.697] | 1.000 | 0.749 | −6.270 [−6.302, −6.238] | −12.372 [−12.413, −12.332] |
| 6 | fiveheadfred | −2.570 [−2.667, −2.473] | +2.256 [+2.181, +2.331] | 1.000 | 0.649 | −5.000 [−5.000, −5.000] | −13.281 [−13.318, −13.245] |
| 7 | rankthetank | −9.767 [−9.857, −9.675] | −5.630 [−5.706, −5.553] | 1.000 | 0.145 | −9.300 [−9.334, −9.267] | −15.055 [−15.126, −14.984] |

^A Source A: extraction artifact (comparator_cis_r0_v4.json, schema `comparator_cis_v1`).

**Notes:**

1. **CVaR-5% zero-width CIs** for fiveheadfred (−5.000) and stricthellraiser
   (−3.000) reflect that these bidders produce constant-bid outcomes with
   concentrated worst-case distributions. The 5th-percentile boundary falls on
   a mass point, so bootstrap resamples produce identical values.

2. **bid_rate and make_rate** are reported here as bare fractions from Source A.
   Bootstrap CIs on these rates, plus std(net_pts), are available in notebook
   `45_comparator_deep_dive` §S5.

See notebook `45_comparator_deep_dive`, Figure 1 for per-deal distributions.

## 4. Rankings by Contract Type

Per-contract-type breakdown (7 bidders × 3 contract types). `net_eppd_ct` uses
the unconditional denominator (`total_deals`), so per-facet values sum to the
pooled net_eppd in §3.

Data from notebook `45_comparator_deep_dive` §S3.

*Deferred to R1.* FULL-mode compute budget was prioritized for the H2H battery
(370k deals). Contract-type breakdown is available in QUICK-mode data within
notebook `45_comparator_deep_dive` §S3, but not at publication resolution.
Bidders that only bid one contract type (stricthellraiser: suit only;
fiveheadfred: suit only) would have entries only for that type.

## 5. Pairwise Significance

Bootstrap permutation test (two-sided) for net_eppd difference between
adjacent-ranked bidders. n=10,000 bootstrap resamples, seed=42.

| Pair | net_eppd diff | p-value | Significant? |
|------|---------------|---------|--------------|
| modeloespecifico vs hybrid_olsa | +1.132 | < 0.001 | Yes |
| hybrid_olsa vs stricthellraiser | +0.379 | < 0.001 | Yes |
| stricthellraiser vs olsa_full | +0.244 | < 0.001 | Yes |
| olsa_full vs olsa | +0.174 | 0.009 | Yes |
| olsa vs fiveheadfred | +2.227 | < 0.001 | Yes |
| fiveheadfred vs rankthetank | +7.197 | < 0.001 | Yes |

All six adjacent pairs are significantly separated at alpha=0.05. The tightest
gap (olsa_full vs olsa, +0.174, p=0.009) confirms the full-arm's 39 features
provide a small but real advantage over the constrained 3-feature arm.

## 6. Behavioral Profiles

### 6a. Bidder Descriptions

Descriptions below reflect post-fix behavior (PRs #463, #464, #465) and
predictions written before examining v4 results.

**modeloespecifico** — Hand-coded feature-weighted formula. Evaluates all six
contracts (4 suits, HIGH, LOW) using locked weights: `1.0 × bowers + 0.5 ×
trump_count + 0.5 × offsuit_aces` for suit contracts; `1.0 × offsuit_aces`
for HIGH; `1.0 × offsuit_tens_count` for LOW. Floors the score to an integer
bid level. Bid range: 3–10 (post-fix: ceiling raised from 6 to 10). Expected:
high bid_rate, high make_rate, top performer due to hand-quality-aware
decisions.

**hybrid_olsa** — Sparse OLS with Gaussian CDF wrapper and CVaR risk penalty.
Uses the constrained 3-feature arm (`hybrid_r0.json`: bowers, trump_count,
offsuit_aces). For each contract, predicts expected tricks via OLS, then
computes risk-adjusted expected value using Gaussian distribution of outcomes.
Risk penalty: `max(0, −CVaR_5%) × risk_lambda`. The only bidder that
systematically passes — bids only when risk-adjusted EV exceeds zero. Bid
range: 1–10. Expected: low bid_rate, high make_rate on bid hands, net_eppd
driven by quality of pass/bid boundary.

**olsa_full** — Full-arm OLSa with all 39 forward-selected features from
`hybrid_r0_full.json`, using floor-based threshold (bids at `floor(mu)` where
mu is predicted tricks). No risk adjustment. Bid range: 1–10. Expected: always
bids (floor threshold almost always produces a valid bid), moderate make_rate,
net_eppd above olsa due to richer features.

**olsa** — Constrained OLSa with 3 features from `hybrid_r0.json`, using
floor-based threshold. Uses identical regression coefficients as hybrid_olsa
but lacks the Gaussian CDF wrapper. Bid range: 1–10. Expected: always bids,
make_rate and net_eppd slightly below olsa_full due to fewer features.

**rankthetank** — Heuristic bidder mapping hand strength to bid level via
calibrated threshold ladder. Uses `score_hand_scalar()` composite. Evaluates
all six contracts unconditionally (post-fix: HIGH/LOW no longer conditional on
card distribution). Suit thresholds: 200→bid 3, up to 750→bid 10. Bid range:
3–10. Expected: always bids (200 threshold almost always met), make_rate
dependent on threshold calibration quality.

**fiveheadfred** — Fixed-bid baseline. Always bids 5 Spades regardless of hand.
Bid range: 5 (constant). Expected: bid_rate=1.0, make_rate ≈ proportion of
hands that can win 5+ tricks in Spades, net_eppd negative (no hand awareness).

**stricthellraiser** — Auction-state-only raising rule. Ignores hand quality.
If `current_high_bid=0`: bids 3 Spades. Otherwise: bids `current_high_bid+1`.
**Single-seat degeneracy:** With `current_high_bid=0` in every deal, always
bids exactly 3 Spades. This is the minimum legal bid — a degenerate operating
point that tells us "what happens when you always bid 3 Spades?" rather than
testing the bidder's intended raise-the-stakes behavior. Bid range: 3 (in
single-seat mode). Expected: bid_rate=1.0, high make_rate (3 is easy to make),
near-zero net_eppd.

### 6b. Expected vs Observed

**modeloespecifico** — Matched expectations. Highest net_eppd (+1.587),
near-universal bidding (bid_rate=0.986), and excellent make_rate (0.947).
Post-fix ceiling extension from 6→10 allows the formula to express strong
hands as higher bids. The 1.4% pass rate (276 passes out of 20,000 deals)
occurs when no contract's score reaches the minimum bid threshold (3) — these
are genuinely weak hands.

**hybrid_olsa** — Matched expectations directionally, but the bid_rate of
0.197 is lower than the v2 value of 0.625. This is explained by the mode
change: in v2's 4-way mode, 4 instances of hybrid_olsa competed in each
auction, so `P(at least one bids) ≈ 1 − (1 − 0.20)^4 ≈ 0.59`, consistent
with the observed 0.625. The single-seat bid_rate reveals the per-hand bid
propensity: only 19.7% of hands pass hybrid_olsa's risk threshold. Despite
bidding rarely, it achieves make_rate=0.886 and ranks 2nd — the Gaussian CDF
wrapper's selectivity converts accuracy into net_eppd efficiently.

**stricthellraiser** — Confirmed degenerate in single-seat mode. Always bids
3 Spades (verified in notebook S4), make_rate=0.943 — nearly every hand can
win 3 of 10 tricks. The positive net_eppd (+0.076) means that "always bid 3
Spades with Glutton playing" slightly beats doing nothing. This is not a
meaningful assessment of StrictHellRaiser's intended behavior (raise-the-stakes
in contested auctions). Rank 3 placement is an artifact of the degenerate
operating point.

**olsa_full and olsa** — As expected, both always bid and olsa_full outperforms
olsa (+0.174 net_eppd, p=0.009). Both have negative net_eppd, meaning their
floor-based thresholds overbid on average — the predicted tricks exceed actual
tricks often enough that set penalties outweigh make rewards. The 39 features
of olsa_full provide modestly better calibration (make_rate 0.763 vs 0.749).

**fiveheadfred** — As expected: bid_rate=1.0, make_rate=0.649, net_eppd=−2.570.
Makes about 2 in 3 five-Spades contracts, but the sets cost more than the
makes earn.

**rankthetank** — The largest surprise. Bid_rate=1.0 (expected — 200 threshold
almost always met), but make_rate collapsed to 0.145 (14.5%), producing the
worst net_eppd (−9.767) and the only negative eppd (−5.630). The post-fix
threshold recalibration (PR #465) made the bidder more aggressive: extending
suit ceiling to 10 and recalibrating HIGH/LOW thresholds. The result is
catastrophic overbidding — the recalibrated thresholds do not match actual
card-play outcomes with GluttonStrategy.

## 7. Key Observations

1. **Three tiers are visible.** The seven bidders separate into: (a)
   competitive (net_eppd > 0: modeloespecifico, hybrid_olsa,
   stricthellraiser), (b) near-zero (net_eppd −0.5 to 0: olsa_full, olsa),
   and (c) negative (net_eppd < −2: fiveheadfred, rankthetank). The tier
   boundaries are stable — the smallest cross-tier gap (olsa → fiveheadfred,
   +2.227) is 13× larger than the tightest within-tier gap (olsa_full → olsa,
   +0.174).

2. **Selectivity produces outsized returns.** hybrid_olsa bids on only 19.7%
   of deals yet ranks 2nd overall — the Gaussian CDF wrapper converts
   selective bidding into a +0.455 net_eppd. This is below modeloespecifico
   (+1.587), which bids on 98.6% of deals but with exceptional accuracy
   (make_rate=0.947). The gap between them (+1.132, p<0.001) is the primary
   R1+ improvement target.

3. **StrictHellRaiser's rank 3 is misleading.** Its positive net_eppd reflects
   the degenerate "always bid 3 Spades" mode, not the intended auction-raising
   behavior. A dedicated low-bid baseline would produce a similar result —
   bidding 3 of any suit has an inherently high make probability.

4. **OLS floor thresholds overbid.** Both olsa variants have negative net_eppd,
   meaning `floor(predicted_tricks)` overestimates bid-worthy hands. The hybrid
   wrapper's risk adjustment corrects this: hybrid_olsa passes on 80% of deals
   where olsa would bid (and often lose).

5. **RanktheTank's recalibration backfired.** The PR #465 threshold changes
   moved it from rank 5 (v2: net_eppd=−3.170, make_rate=0.546) to rank 7
   (v4: net_eppd=−9.767, make_rate=0.145). The recalibrated thresholds are
   far too aggressive for GluttonStrategy card play outcomes.

6. **Gap to close.** The 1.132 point/deal gap between modeloespecifico and
   hybrid_olsa is the primary target for R1+ improvements. The gap's
   significance (p<0.001) confirms it is real. Potential improvement vectors:
   more features (hybrid_olsa uses only 3), better sigma estimates, or
   opponent-context features.

## 8. Auction-Pressure Sensitivity

*Deferred — single-seat is the canonical comparator instrument.*

The single-seat design intentionally evaluates bidding quality in uncontested
auctions (§2.4). A 4-way rerun would show how rankings change under contested
auctions (`current_high_bid > 0`), but this is better addressed by the H2H
battery ([h2h_battery_analysis.md](h2h_battery_analysis.md)), which already
captures auction interaction effects in a more rigorous paired-deal design.

The v2 4-way data cannot be used because it used pre-fix bidders with three
known bugs (ModeloEspecifico bid ceiling, OLSa bid floor, RanktheTank
thresholds). A fresh 4-way rerun adds little value given the H2H battery's
coverage of competitive dynamics.

## 9. Provenance & Reproduction

### Provenance

| Item | Value |
|------|-------|
| gate_status | PASS |
| Primary artifact | data/artifacts/arc_d/r0/comparator_cis_r0_v4.json |
| Battery metadata | data/artifacts/arc_d/r0/comparator_battery_r0_v4.json |
| Extraction script | scripts/internal/extract_comparator_cis.py |
| Notebook | notebooks/arc_d/r0/45_comparator_deep_dive.py |
| Schema | `comparator_cis_v1` |
| Git SHA | (see PR) |
| Seed | 42 |
| n_deals | 20,000 per bidder (5,000/seat × 4 seats) |
| n_bootstrap | 10,000 |
| Play strategy | GluttonStrategy |
| Mode | single_seat |

### Reproduction

**Step 1 — Run battery** (7 bidders × 4 seats = 28 sub-experiments):

    PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
        --config experiments/configs/auction_comparator.yaml \
        --seed 42 \
        --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
        --bidder-class HybridOLSaBidder \
        --bidder-name hybrid_olsa \
        --single-seat \
        --n-per 20000 \
        --output-format json \
        --output data/artifacts/arc_d/r0/comparator_battery_r0_v4.json

**Step 2 — Extract CIs:**

    PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
        --artifacts-dir data/artifacts/arc_d/r0 \
        --runs-dir data/runs \
        --seed 42 --n-bootstrap 10000 \
        --battery-file comparator_battery_r0_v4.json \
        --single-seat \
        --output data/artifacts/arc_d/r0/comparator_cis_r0_v4.json

**Step 3 — Run notebook** (cross-validates Source A, produces Source B):

    uv run jupytext --to ipynb --output notebooks/arc_d/r0/45_comparator_deep_dive.ipynb \
        notebooks/arc_d/r0/45_comparator_deep_dive.py
    uv run jupyter execute notebooks/arc_d/r0/45_comparator_deep_dive.ipynb \
        --ExecutePreprocessor.timeout=600

Or via make targets:

    make notebook-sync
    MODE=FULL make notebook-run
