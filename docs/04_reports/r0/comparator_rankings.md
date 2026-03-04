# R0 Comparator Rankings (v6, Single-Seat, 8 Bidders)

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-03 (v6; supersedes v1-v5 in git history)
**Methodology:** Single-seat · 20,000 deals/bidder (5,000/seat x 4 seats) · seed=42 · 10,000 bootstrap resamples · GluttonStrategy card play

## 1. Summary

This report presents the **decision-quality benchmark** for all eight R0
bidders evaluated in the single-seat comparator battery. Each bidder is tested
in isolation — one seat bids while three always-pass sentinels fill the
remaining seats — producing an **absolute** net_eppd score that measures
bidding quality without survivorship bias or auction interaction.

The single-seat comparator answers the question: *"Given every possible deal,
how much value does this bidder's bid-or-pass decision add?"* Every deal is
evaluated (bid or pass), and pass deals contribute zero to the numerator but
count in the denominator. This penalizes excessive passing and rewards
calibrated selectivity.

The v6 rankings reveal a dramatic shift from v4: **bid-level search**
(`compute_best_bid()`) transformed the hybrid variants from selective niche
bidders into high-volume, high-accuracy top performers. The rankings now
establish two clear tiers: three positive-net_eppd bidders
(hybrid_olsa_full, hybrid_olsa, modeloespecifico) forming a competitive
cluster, and five near-zero-to-negative bidders
(stricthellraiser, olsa_full, olsa, fiveheadfred, rankthetank). Three
adjacent pairs are NOT statistically distinguishable, indicating unresolved
ties in the 8-bidder field.

For competitive ordering between bidders in contested auctions, see the
[H2H battery analysis](h2h_battery_analysis.md). The comparator and H2H
instruments measure **different estimands** — see S2.4 for what this
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
| **net_eppd** | `sum(bidder_pts - opponent_pts for bid-hands) / total_deals` | All deals (bid + pass) |
| **eppd** | `sum(bidder_pts for bid-hands) / total_deals` | All deals |
| **bid_rate** | `hands_with_bids / total_deals` | Per-bidder propensity |
| **make_rate** | `bids_made / hands_with_bids` | Conditional on bidding |
| **CVaR-5%** | Mean of worst 5% of bid-hand outcomes | Bid-hands only |
| **net_CVaR-5%** | Mean of worst 5% of per-deal net differentials | All deals |
| **std(net_pts)** | Standard deviation of per-deal net points | All deals |

Pass deals contribute 0 to numerator terms but count in denominators. This
means a bidder that passes on every hand scores `net_eppd=0` — the neutral
baseline.

### 2.3 Version History

| Version | Date | Bidders | Deals | Mode | Play Strategy | Changes |
|---------|------|---------|-------|------|---------------|---------|
| v1 | 2026-02-23 | 5 | 10,000 | 4-way | GreedyStrategy | Initial battery |
| v2 | 2026-02-25 | 7 | 10,000 | 4-way | GreedyStrategy | Added olsa_full + olsa; identity clarification |
| v3 | 2026-02-28 | 7 | 20,000 | Single-seat | GreedyStrategy | Bidder fixes A/B/C; single-seat mode |
| v4 | 2026-02-28 | 7 | 20,000 | Single-seat | GluttonStrategy | Play strategy harmonization |
| **v6** | **2026-03-03** | **8** | **20,000** | **Single-seat** | **GluttonStrategy** | **Bid-level search + hybrid_olsa_full added** |

**v1->v2 identity change:** In v1, `hybrid_olsa` referred to the OLSa_Full
promotional arm (`hybrid_r0_full.json`, bid_rate~83%). In v2+, `hybrid_olsa`
refers to the constrained arm with Gaussian CDF wrapper (`hybrid_r0.json`),
and `olsa_full` is the full-arm variant.

**v2->v3 changes:** Three bidder fixes merged — (A) ModeloEspecifico bid
ceiling raised from 6 to 10, (B) OLSa bid floor lowered from 3 to 1,
(C) RanktheTank HIGH/LOW thresholds recalibrated and suit ceiling extended to
10. Single-seat mode eliminates auction interaction confounds.

**v3->v4 change:** Play strategy harmonized from GreedyStrategy (implicit
default) to GluttonStrategy (explicit). Both instruments (comparator + H2H)
now use the same card play policy, making track disagreements primarily
estimand-driven rather than confounded by play quality.

**v4->v6 changes:** Two code changes produced dramatic behavioral shifts:

1. **Bid-level search.** `compute_best_bid()` now evaluates ALL legal bid
   levels (1-10) for each contract and selects the max-utility bid. In v4,
   hybrid_olsa evaluated EV only at `floor(mu)`. This meant hands with
   `floor(mu)=0` were automatically passed. With bid-level search, the model
   can bid 1 or 2 on hands where the predicted EV at lower bid levels is
   positive. The result: hybrid_olsa bid_rate jumped from 19.7% to 96.1%.
2. **hybrid_olsa_full added.** The full-arm variant (forward-selected features
   from `hybrid_r0_full.json`) now uses the same Gaussian CDF wrapper +
   bid-level search as hybrid_olsa, entering the battery as the 8th bidder.

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
  reference point without running O(n^2) pairwise matchups.
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

All eight comparator bidders ranked by net_eppd descending. Bootstrap 95%
confidence intervals in brackets.

| Rank | Bidder | net_eppd [95% CI] | eppd [95% CI] | bid_rate | make_rate | CVaR-5% [95% CI] | net_CVaR-5% [95% CI] |
|------|--------|---------------------|-----------------|------------|-------------|---------------------|------------------------|
| 1 | hybrid_olsa_full | +2.170 [+2.081, +2.257] | +5.925 [+5.872, +5.977] | 0.968 | 1.000 | +2.822 [+2.760, +2.934] | -4.355 [-4.479, -4.132] |
| 2 | hybrid_olsa | +2.131 [+2.042, +2.216] | +5.869 [+5.813, +5.922] | 0.961 | 1.000 | +2.863 [+2.813, +2.979] | -4.275 [-4.375, -4.042] |
| 3 | modeloespecifico | +1.604 [+1.489, +1.720] | +5.593 [+5.515, +5.669] | 1.000 | 0.947 | -4.612 [-4.796, -4.088] | -11.152 [-11.204, -10.756] |
| 4 | stricthellraiser | +0.085 [-0.027, +0.197] | +4.912 [+4.845, +4.979] | 1.000 | 0.945 | -3.000 [-3.000, -2.832] | -11.272 [-11.352, -11.036] |
| 5 | olsa_full | -0.012 [-0.193, +0.173] | +3.911 [+3.767, +4.058] | 1.000 | 0.772 | -6.268 [-6.336, -6.204] | -12.328 [-12.408, -12.252] |
| 6 | olsa | -0.225 [-0.413, -0.037] | +3.722 [+3.574, +3.872] | 1.000 | 0.756 | -6.252 [-6.316, -6.192] | -12.416 [-12.508, -12.332] |
| 7 | fiveheadfred | -2.579 [-2.771, -2.384] | +2.248 [+2.098, +2.401] | 1.000 | 0.649 | -5.000 [-5.000, -5.000] | -13.272 [-13.352, -13.188] |
| 8 | rankthetank | -9.665 [-9.851, -9.483] | -5.552 [-5.712, -5.393] | 1.000 | 0.150 | -9.256 [-9.320, -9.196] | -15.088 [-15.160, -14.952] |

**Source:** extraction artifact (comparator_cis_r0_v6.json, schema `comparator_cis_v1`).

**Notes:**

1. **Positive CVaR-5% for hybrid variants.** Unlike all other bidders,
   hybrid_olsa (+2.863) and hybrid_olsa_full (+2.822) have *positive* worst-5%
   bid outcomes. With 100% make_rate and bid-level search selecting only
   profitable bids, even their worst-performing contracts are profitable.
   This is a qualitative change from v4, where hybrid_olsa had CVaR-5% of
   -6.152.

2. **100% make_rate for hybrid variants.** Both hybrid_olsa and
   hybrid_olsa_full achieve make_rate=1.000 — every bid they place is made.
   The Gaussian CDF wrapper's risk adjustment, combined with bid-level search,
   means these bidders only bid when they expect to win the contracted number
   of tricks. The 3-4% of deals they pass are hands where no bid level yields
   positive expected utility.

3. **bid_rate and make_rate** are reported here as bare fractions.
   Bootstrap CIs on these rates, plus std(net_pts), are available in notebook
   `45_comparator_deep_dive` S5.

4. **CVaR-5% zero-width CIs** for fiveheadfred (-5.000) reflect that this
   bidder produces constant-bid outcomes with concentrated worst-case
   distributions.

See notebook `45_comparator_deep_dive`, Figure 1 for per-deal distributions.

## 4. Rankings by Contract Type

Per-contract-type breakdown (8 bidders x 3 contract types). `net_eppd_ct` uses
the unconditional denominator (`total_deals`), so per-facet values sum to the
pooled net_eppd in S3.

Data from notebook `45_comparator_deep_dive` S3.

*Deferred to R1.* FULL-mode compute budget was prioritized for the H2H battery
(370k+ deals). Contract-type breakdown is available in QUICK-mode data within
notebook `45_comparator_deep_dive` S3, but not at publication resolution.
Bidders that only bid one contract type (stricthellraiser: suit only;
fiveheadfred: suit only) would have entries only for that type.

## 5. Pairwise Significance

Bootstrap permutation test (two-sided) for net_eppd difference between
adjacent-ranked bidders. n=10,000 bootstrap resamples, seed=42.

| Pair | net_eppd diff | p-value | Significant? |
|------|---------------|---------|--------------|
| hybrid_olsa_full vs hybrid_olsa | +0.038 | 0.5457 | **No** |
| hybrid_olsa vs modeloespecifico | +0.527 | < 0.001 | Yes |
| modeloespecifico vs stricthellraiser | +1.520 | < 0.001 | Yes |
| stricthellraiser vs olsa_full | +0.096 | 0.3753 | **No** |
| olsa_full vs olsa | +0.213 | 0.1099 | **No** |
| olsa vs fiveheadfred | +2.355 | < 0.001 | Yes |
| fiveheadfred vs rankthetank | +7.086 | < 0.001 | Yes |

Three of seven adjacent pairs are NOT statistically separated at alpha=0.05.
This contrasts sharply with v4, where all six pairs were significant.

The three unresolved ties define three statistical clusters within the ranking:

1. **Top cluster:** hybrid_olsa_full ~ hybrid_olsa (delta=+0.038, p=0.546).
   These two bidders use identical mechanisms (Gaussian CDF + bid-level search)
   with different feature sets, producing near-identical performance. The
   full-arm's forward-selected features provide no measurable advantage at R0
   model quality.
2. **Middle cluster:** stricthellraiser ~ olsa_full ~ olsa
   (delta=+0.096, p=0.375; delta=+0.213, p=0.110). All three always bid and
   produce near-zero net_eppd. stricthellraiser's degenerate "always bid 3
   Spades" mode happens to land in the same band as the floor-based OLSa
   variants.
3. **Separated:** modeloespecifico is significantly above the middle cluster
   (+1.520, p<0.001) and significantly below the top cluster (-0.527,
   p<0.001). fiveheadfred and rankthetank are each significantly separated
   from their neighbors.

## 6. Behavioral Profiles

### 6a. Bidder Descriptions

Descriptions below reflect post-fix behavior (PRs #463, #464, #465) plus
v6 bid-level search changes.

**hybrid_olsa** — Sparse OLS with Gaussian CDF wrapper, CVaR risk penalty,
and bid-level search. Uses the constrained 3-feature arm (`hybrid_r0.json`:
bowers, trump_count, offsuit_aces). For each contract, predicts expected tricks
via OLS, then computes risk-adjusted expected value using Gaussian distribution
of outcomes. Risk penalty: `max(0, -CVaR_5%) * risk_lambda`. In v6,
`compute_best_bid()` evaluates ALL legal bid levels (1-10) for each contract
and selects the max-utility bid. This replaces the v4 behavior of evaluating
only at `floor(mu)`. Bid range: 1-10. Expected: high bid_rate (search finds
profitable bids at low levels), 100% make_rate (only bids when EV is positive),
top-tier net_eppd.

**hybrid_olsa_full** — Full-arm OLSa with Gaussian CDF wrapper, CVaR risk
penalty, and bid-level search. Uses forward-selected features (2-3 per
contract type, from pool of 39) from `hybrid_r0_full.json`. Identical
mechanism to hybrid_olsa but with richer features. Bid range: 1-10. Expected:
near-identical performance to hybrid_olsa — the additional features provide
minimal marginal value at R0 model quality.

**modeloespecifico** — Hand-coded feature-weighted formula. Evaluates all six
contracts (4 suits, HIGH, LOW) using locked weights: `1.0 x bowers + 0.5 x
trump_count + 0.5 x offsuit_aces` for suit contracts; `1.0 x offsuit_aces`
for HIGH; `1.0 x offsuit_tens_count` for LOW. Floors the score to an integer
bid level. Bid range: 3-10 (post-fix: ceiling raised from 6 to 10). Expected:
high bid_rate, high make_rate, strong performer due to hand-quality-aware
decisions and multi-contract evaluation.

**olsa_full** — Full-arm OLSa with forward-selected features (2-3 per contract
type, from pool of 39) from `hybrid_r0_full.json`, using floor-based threshold
(bids at `floor(mu)` where mu is predicted tricks). No risk adjustment or
bid-level search. Bid range: 1-10. Expected: always bids (floor threshold
almost always produces a valid bid), moderate make_rate, net_eppd near zero.

**olsa** — Constrained OLSa with 3 features from `hybrid_r0.json`, using
floor-based threshold. Uses identical regression coefficients as hybrid_olsa
but lacks the Gaussian CDF wrapper and bid-level search. Bid range: 1-10.
Expected: always bids, make_rate and net_eppd slightly below olsa_full due to
fewer features.

**rankthetank** — Heuristic bidder mapping hand strength to bid level via
calibrated threshold ladder. Uses `score_hand_scalar()` composite. Evaluates
all six contracts unconditionally (post-fix: HIGH/LOW no longer conditional on
card distribution). Suit thresholds: 200->bid 3, up to 750->bid 10. Bid range:
3-10. Expected: always bids (200 threshold almost always met), make_rate
dependent on threshold calibration quality.

**fiveheadfred** — Fixed-bid baseline. Always bids 5 Spades regardless of hand.
Bid range: 5 (constant). Expected: bid_rate=1.0, make_rate approximately the
proportion of hands that can win 5+ tricks in Spades, net_eppd negative (no
hand awareness).

**stricthellraiser** — Auction-state-only raising rule. Ignores hand quality.
If `current_high_bid=0`: bids 3 Spades. Otherwise: bids `current_high_bid+1`.
**Single-seat degeneracy:** With `current_high_bid=0` in every deal, always
bids exactly 3 Spades. This is the minimum legal bid — a degenerate operating
point that tells us "what happens when you always bid 3 Spades?" rather than
testing the bidder's intended raise-the-stakes behavior. Bid range: 3 (in
single-seat mode). Expected: bid_rate=1.0, high make_rate (3 is easy to make),
near-zero net_eppd.

### 6b. Expected vs Observed

**hybrid_olsa** — The most dramatic change from v4. Bid_rate surged from 0.197
(v4) to 0.961 (v6) — a 4.9x increase driven entirely by bid-level search.
In v4, `floor(mu)=0` on 80% of hands meant automatic passes. In v6,
`compute_best_bid()` finds profitable bids at levels 1-2 on most of these
hands, converting passes into profitable contracts. The result: net_eppd
jumped from +0.455 to +2.131 (4.7x), and make_rate reached 1.000 —
every single bid placed is made. The 3.9% of hands still passed
(197 out of 5,000 per seat) are genuinely unprofitable at any bid level.
This confirms the Gaussian CDF wrapper's value: rather than filtering out
80% of hands (v4), it now serves as a precision tool identifying the ~4% that
are truly unbiddable.

**hybrid_olsa_full** — Matched expectations: near-identical to hybrid_olsa
(net_eppd +2.170 vs +2.131, delta=+0.038, p=0.546). The forward-selected
features provide no statistically detectable advantage. Bid_rate (0.968) and
make_rate (1.000) are functionally equivalent to hybrid_olsa. This replicates
the v4 finding that olsa_full's feature advantage over olsa was marginal
(+0.174) — the constraint holds regardless of whether the wrapper uses
floor-based or CDF-based bidding.

**modeloespecifico** — Minimal change from v4 (+1.587 -> +1.604). This is
expected: modeloespecifico already evaluated all contracts and used its own
floor-based bid-level selection, so it was unaffected by the hybrid variants'
bid-level search changes. Bid_rate remains at 1.000 (was 0.986 in v4 — the
small increase is within noise given the per-seat sampling). Make_rate (0.947)
is stable. The key v6 story for modeloespecifico is relative, not absolute:
it dropped from rank 1 to rank 3 as the hybrid variants leapfrogged it.

**stricthellraiser** — Unchanged behavior: always bids 3 Spades in single-seat
mode (bid_rate=1.000, make_rate=0.945). net_eppd (+0.085) is consistent with
v4 (+0.076). Confirmed degenerate in single-seat mode.

**olsa_full and olsa** — As expected, both always bid and olsa_full outperforms
olsa (+0.213 net_eppd, p=0.110 — NOT significant at v6, vs p=0.009 at v4).
The significance change reflects that olsa_full's net_eppd improved slightly
(-0.168 -> -0.012, now near zero) while olsa also improved (-0.342 -> -0.225).
Both remain floor-based bidders unaffected by bid-level search. The narrowing
gap is consistent with sampling variation rather than a real behavioral change.

**fiveheadfred** — As expected: bid_rate=1.0, make_rate=0.649, net_eppd=-2.579.
Stable from v4 (-2.570).

**rankthetank** — Stable from v4: bid_rate=1.0, make_rate=0.150 (was 0.145),
net_eppd=-9.665 (was -9.767). Remains the worst performer with catastrophic
overbidding.

## 7. Key Observations

1. **Two tiers, not three.** The v4 three-tier structure has collapsed into
   two: (a) positive (hybrid_olsa_full, hybrid_olsa, modeloespecifico, all
   net_eppd > +1.6) and (b) near-zero-to-negative (stricthellraiser through
   rankthetank, net_eppd from +0.085 to -9.665). The former "near-zero middle
   band" (olsa_full, olsa) remains, but stricthellraiser now falls within
   their range, making it a single diffuse lower tier.

2. **Bid-level search is transformative.** The v4->v6 changes affected only the
   hybrid variants, yet they produced the largest ranking changes in the
   battery's history. hybrid_olsa gained +1.676 net_eppd (from +0.455 to
   +2.131) and overtook modeloespecifico (from a -1.132 deficit to a +0.527
   advantage). The mechanism is clear: bid-level
   search converts the Gaussian CDF wrapper from a conservative gate (pass 80%
   of hands) into an optimizing selector (find the best bid for 96% of hands).

3. **The hybrid variants now BEAT modeloespecifico.** In v4, modeloespecifico
   led hybrid_olsa by +1.132 (p<0.001). In v6, hybrid_olsa leads
   modeloespecifico by +0.527 (p<0.001). This is a 1.659-point reversal — the
   primary R1+ improvement target has been achieved at R0 through algorithmic
   improvement rather than model quality improvement.

4. **100% make_rate with 96% bid_rate.** hybrid_olsa achieves the seemingly
   paradoxical combination of near-universal bidding AND perfect accuracy.
   The mechanism: bid-level search allows bidding at level 1 or 2 on hands
   that are too weak for the model's original `floor(mu)` threshold but still
   profitable at low bid levels. Since bid level 1 requires winning only 1 of
   10 tricks, most hands can achieve this.

5. **hybrid_olsa_full vs hybrid_olsa: statistically indistinguishable.** The
   full-arm's forward-selected features provide +0.038 net_eppd (p=0.546) —
   no advantage at R0 model quality. This is consistent across both the v4
   finding (olsa_full vs olsa: +0.174, p=0.009, small effect) and the v6
   finding, and suggests the R0 model's predictive bottleneck is not feature
   richness.

6. **OLS floor thresholds still overbid.** Despite the improvements in the
   hybrid variants, the floor-based olsa and olsa_full remain near zero or
   slightly negative. They lack both the CDF wrapper's risk adjustment and
   bid-level search's optimization, confirming that both components are needed
   for positive net_eppd at R0 model quality.

7. **Three unresolved ties.** The 8-bidder field has three adjacent pairs that
   are not statistically separated: hybrid_olsa_full~hybrid_olsa (p=0.546),
   stricthellraiser~olsa_full (p=0.375), and olsa_full~olsa (p=0.110). This
   contrasts with v4 where all pairs were significant, and reflects both the
   addition of the near-identical hybrid_olsa_full and small shifts in the
   middle-tier bidders.

## 8. Auction-Pressure Sensitivity

*Deferred — single-seat is the canonical comparator instrument.*

The single-seat design intentionally evaluates bidding quality in uncontested
auctions (S2.4). A 4-way rerun would show how rankings change under contested
auctions (`current_high_bid > 0`), but this is better addressed by the H2H
battery ([h2h_battery_analysis.md](h2h_battery_analysis.md)), which already
captures auction interaction effects in a more rigorous paired-deal design.

## 9. Provenance & Reproduction

### Provenance

| Item | Value |
|------|-------|
| gate_status | PROMOTED |
| Primary artifact | data/artifacts/arc_d/r0/comparator_cis_r0_v6.json |
| Battery metadata | data/artifacts/arc_d/r0/comparator_battery_r0_v6.json |
| Extraction script | scripts/internal/extract_comparator_cis.py |
| Notebook | notebooks/arc_d/r0/45_comparator_deep_dive.py |
| Schema | `comparator_cis_v1` |
| Git SHA | (see PR) |
| Seed | 42 |
| n_deals | 20,000 per bidder (5,000/seat x 4 seats) |
| n_bootstrap | 10,000 |
| Play strategy | GluttonStrategy |
| Mode | single_seat |

### Reproduction

**Step 1 — Run battery** (8 bidders x 4 seats = 32 sub-experiments):

    uv run python scripts/internal/run_auction_comparator.py \
        --config experiments/configs/auction_comparator.yaml \
        --seed 42 --single-seat --n-per 20000 \
        --output-format json \
        --output data/artifacts/arc_d/r0/comparator_battery_r0_v6.json

**Step 2 — Extract CIs** (use the batch manifest from Step 1 for coherence validation):

    MANIFEST=$(ls -t data/runs/batch_manifest_auction_comparator_42_*.json | head -1)
    uv run python scripts/internal/extract_comparator_cis.py \
        --artifacts-dir data/artifacts/arc_d/r0 \
        --runs-dir data/runs \
        --seed 42 --n-bootstrap 10000 \
        --battery-file comparator_battery_r0_v6.json \
        --single-seat \
        --manifest "$MANIFEST" \
        --output data/artifacts/arc_d/r0/comparator_cis_r0_v6.json

**Step 3 — Run notebook** (cross-validates extraction artifact, produces additional metrics):

    uv run jupytext --to ipynb --output notebooks/arc_d/r0/45_comparator_deep_dive.ipynb \
        notebooks/arc_d/r0/45_comparator_deep_dive.py
    uv run jupyter execute notebooks/arc_d/r0/45_comparator_deep_dive.ipynb \
        --ExecutePreprocessor.timeout=600

Or via make targets:

    make notebook-sync
    MODE=FULL make notebook-run
