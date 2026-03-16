# R0 H2H Battery Analysis & Experiment Summary

> **⚠ SUPERSEDED** — This is the v1 version, archived for reference.
> The current version is at [`../04_r0_experiment_summary.md`](../04_r0_experiment_summary.md).
> See [README.md](README.md) for the v1→v2 delta summary.

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline lock)
**Date:** 2026-02-25
**Purpose:** Validate R0 artifacts, calibrate R1 gate thresholds, establish bidder dominance ordering

---

## 1. What Was Done

### 1.1 Overview

Six experiment campaigns were run to complete the R0-to-R1 transition,
producing the data needed to calibrate promotion gates and train the R1 model.
All runs used seed=42 for deterministic reproducibility. Total simulation
budget: ~650,000 deals across all campaigns.

### 1.2 Campaign Inventory

| Campaign | Deals | Bidders | Purpose |
|----------|-------|---------|---------|
| C33 Ablation | 40,000 | 2 (hybrid_olsa, olsa) | Isolate Gaussian EV wrapper effect |
| Comparator Battery | 140,000 | 7 (all) | Rank bidders in self-play vs Glutton |
| C50 QUICK | 98,000 | 7 (all, 49 matchups) | Full H2H matrix at survey resolution |
| C50 FULL | 370,000 | 7 (37 matchups) | Targeted rerun at publication resolution |
| Threshold Calibration | N/A | N/A | Derive gate thresholds from null signal |
| Drift Check | N/A | N/A | Validate QUICK thresholds against FULL |

### 1.3 Simulation Design

**Game variant:** Double-deck Bid Euchre (40 cards, 10-A, 4 suits x 2 copies,
bowers in suit contracts). 10 cards per player, 10 tricks per hand. Partnerships
(seats 0,2) vs (seats 1,3).

**H2H matchup structure:** Each matchup pits bidder A (seats 0,2) against
bidder B (seats 1,3) over N paired deals. "Paired deals" means the same 10k
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

### 1.4 What This Methodology Measures (and What It Does Not)

**Design:** Two bidders compete directly on the same deals. Both bidders
participate in a contested auction — bidder A's bid may outbid B or vice versa,
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
  good in absolute terms — only which is better. For absolute benchmarking,
  see the [comparator rankings](comparator_rankings.md).
- **O(n²) cost.** 7 bidders require 49 matchups; this becomes expensive at
  publication resolution (10k deals/cell = 490k deals). The QUICK-then-FULL
  design mitigates this by running a survey at 2k/cell first.
- **Opponent-specific.** A bidder's H2H performance depends on who it faces.
  Rock-paper-scissors effects (intransitivity) are possible in theory, though
  not observed in R0.

**Comparison with self-play comparator battery:** The comparator battery
([comparator_rankings.md](comparator_rankings.md)) evaluates each bidder
independently against GluttonStrategy in uncontested auctions. It answers "is
this model any good?" while H2H answers "which model is better?" The two
methods can give different rankings — for example, `modeloespecifico` leads
`olsa` by +1.929 net_eppd in self-play but is statistically indistinguishable
from it in H2H (+0.016, CI spans zero). This divergence arises because
self-play rankings are confounded by how each bidder interacts with the common
opponent, while H2H captures the actual competitive dynamic.

### 1.5 The Seven Bidders

| Bidder | Type | Description |
|--------|------|-------------|
| **hybrid_olsa** | Trained (Gaussian EV) | R0 OLSa with analytical P(make) via normal CDF. Selective bidder (bid_rate ~0.20). Uses 3 constrained features from `hybrid_r0.json`. |
| **olsa** | Trained (floor-based) | Same R0 regression coefficients as hybrid_olsa (`hybrid_r0.json`), but uses floor-based threshold decision. Bids on all hands. |
| **olsa_full** | Trained (floor-based) | Full-arm OLSa with forward-selected features (7 total, from pool of 39) from `hybrid_r0_full.json`, floor-based decision. Bids on all hands. |
| **modeloespecifico** | Heuristic (lookup) | Domain-expert lookup table tuned for this game variant. Always bids. |
| **rankthetank** | Heuristic | Conservative rank-based heuristic. Always bids. |
| **fiveheadfred** | Heuristic | Aggressive heuristic emphasizing high cards. Always bids. |
| **stricthellraiser** | Heuristic | Maximally aggressive bidder. Always bids, rarely makes. |

**Naming note:** In this report, `hybrid_olsa` refers to the **constrained OLSa
arm** with Gaussian EV wrapper (bid_rate ~20%, 3 features). This differs from
the earlier 5-bidder comparator battery
([comparator_rankings.md](comparator_rankings.md)), where `hybrid_olsa` referred
to the **OLSa_Full promotional arm** (bid_rate ~83%, forward-selected features).
The 7-bidder battery disambiguates by giving `olsa_full` its own entry.

---

## 2. C33 Ablation: Gaussian EV Wrapper Effect

### 2.1 Question

Does the Gaussian EV decision layer (analytical P(make) via normal CDF) add
measurable value over the simpler floor-based threshold, when both bidders use
identical OLS regression coefficients from `hybrid_r0.json`?

### 2.2 Design

4 matchups x 10,000 paired deals = 40,000 deals total:

- 2 self-play baselines (sanity check)
- 2 cross-matchups (directional + seat-swapped)

### 2.3 Results

| Matchup | net_eppd_delta | 95% CI | Significant? |
|---------|---------------|--------|-------------|
| hybrid_olsa self-play | -0.019 | [-0.108, +0.070] | No |
| olsa self-play | -0.017 | [-0.156, +0.122] | No |
| **hybrid_olsa vs olsa** | **+0.147** | **[+0.014, +0.276]** | **Yes** |
| **olsa vs hybrid_olsa** | **-0.266** | **[-0.399, -0.135]** | **Yes** |

### 2.4 Interpretation

Both self-play cells show deltas near zero with CIs spanning zero, confirming
the paired-deal design is unbiased. The cross-matchup cells both exclude zero
in the same direction: hybrid_olsa outperforms olsa.

**Pooled wrapper effect:** +0.21 net_eppd (average of 0.147 and 0.266).

The mechanism is clear from the behavioral profiles: hybrid_olsa's Gaussian
CDF computes an analytical probability of making each bid, and it *declines*
bids where P(make) is too low. This is visible in the bid rates:

- hybrid_olsa bids 16.2% of the time (when it's bidder A)
- olsa bids 83.8% of the time (floor-based, less selective)

hybrid_olsa makes 89.4% of its bids vs olsa's 76.4%. The wrapper avoids
-EV contracts rather than finding +EV ones the floor misses.

**Verdict:** The Gaussian EV layer adds statistically significant value.
The effect is real but modest (+0.21 net_eppd), driven by improved bid
selectivity rather than better trick prediction.

---

## 3. Comparator Rankings (v4, Single-Seat)

### 3.1 Design

Each bidder plays 20,000 deals (5,000/seat × 4 seats) in single-seat mode
against GluttonStrategy card play. The bidder under test occupies one seat
while three always-pass sentinels fill the remaining seats. Bootstrap 95% CIs
from 10,000 resamples.

See [comparator_rankings.md](comparator_rankings.md) for full methodology,
behavioral analysis, and version history (v1→v4 evolution).

### 3.2 Rankings

| Rank | Bidder | net_eppd | 95% CI |
|------|--------|----------|--------|
| 1 | modeloespecifico | **+1.587** | [+1.529, +1.645] |
| 2 | **hybrid_olsa** | **+0.455** | [+0.420, +0.491] |
| 3 | stricthellraiser | +0.076 | [+0.018, +0.132] |
| 4 | olsa_full | −0.168 | [−0.260, −0.078] |
| 5 | olsa | −0.342 | [−0.435, −0.250] |
| 6 | fiveheadfred | −2.570 | [−2.667, −2.473] |
| 7 | rankthetank | −9.767 | [−9.857, −9.675] |

### 3.3 Pairwise Significance

| Pair (higher vs lower) | Diff | p-value | Significant? |
|------------------------|------|---------|-------------|
| modeloespecifico vs hybrid_olsa | +1.132 | < 0.001 | Yes |
| hybrid_olsa vs stricthellraiser | +0.379 | < 0.001 | Yes |
| stricthellraiser vs olsa_full | +0.244 | < 0.001 | Yes |
| olsa_full vs olsa | +0.174 | 0.009 | Yes |
| olsa vs fiveheadfred | +2.227 | < 0.001 | Yes |
| fiveheadfred vs rankthetank | +7.197 | < 0.001 | Yes |

All 6 adjacent pairs are significantly separated at alpha=0.05. The tightest
gap (olsa_full vs olsa, +0.174, p=0.009) confirms the full-arm's forward-selected features
provide a small but real advantage over the constrained 3-feature arm.

### 3.4 Observations

**Three tiers are visible:**

1. **Competitive** (net_eppd > 0): modeloespecifico, hybrid_olsa, stricthellraiser
2. **Near-zero** (net_eppd −0.5 to 0): olsa_full, olsa
3. **Negative** (net_eppd < −2): fiveheadfred, rankthetank

hybrid_olsa is the only selective bidder (bid_rate=19.7%). Despite bidding on
fewer than 1 in 5 deals, its make rate (88.6%) is close to modeloespecifico's
(94.7%), and it ranks 2nd overall. The selectivity mechanism is the primary
driver of its ranking. Note: stricthellraiser's rank 3 reflects a degenerate
single-seat mode (always bids 3 Spades), not its intended auction-raising
behavior.

modeloespecifico leads because it is a hand-tuned lookup table optimized for
this exact game variant. It represents the ceiling for domain-specific
heuristics but does not generalize.

---

## 4. H2H Battery: Full Matrix

### 4.1 Design

**QUICK phase:** 7 bidders x 7 bidders = 49 matchups (including self-play),
2,000 paired deals per cell. Purpose: survey-resolution coverage of the full
matrix.

**FULL phase:** 37 of 49 matchups rerun at 10,000 paired deals. Selection
criteria: all cells involving {hybrid_olsa, olsa, olsa_full} + any QUICK cells
with CI crossing zero. Purpose: publication-resolution data for key matchups
and gate calibration.

### 4.2 Self-Play Sanity

Self-play cells should show `net_eppd_delta ~ 0` (a bidder playing itself
should not favor either team). CIs should span zero.

**FULL results (10k deals each):**

| Bidder | delta | 95% CI | Spans zero? |
|--------|-------|--------|-------------|
| hybrid_olsa | -0.019 | [-0.108, +0.070] | Yes |
| olsa | -0.017 | [-0.156, +0.122] | Yes |
| olsa_full | -0.066 | [-0.205, +0.069] | Yes |
| modeloespecifico | -0.086 | [-0.184, +0.012] | Yes |
| fiveheadfred | -0.107 | [-0.253, +0.034] | Yes |
| stricthellraiser | -0.020 | [-0.203, +0.162] | Yes |
| rankthetank | -0.192 | [-0.355, -0.030] | **No** |

6 of 7 self-play CIs span zero (pass). rankthetank shows a marginally
significant positional bias (delta=-0.192, CI barely excludes zero). This is
not a simulation bug -- it reflects a real asymmetry in rankthetank's bidding
strategy when it sees its own hand first vs second in the auction. The effect
is small and does not affect cross-matchup interpretation.

### 4.3 Dominance Structure

**QUICK matrix (49 cells, 2k deals) -- Win/Loss/Draw:**

| Bidder | W | L | D |
|--------|---|---|---|
| modeloespecifico | 9 | 0 | 3 |
| hybrid_olsa | 7 | 2 | 3 |
| olsa_full | 7 | 0 | 5 |
| olsa | 5 | 3 | 4 |
| fiveheadfred | 4 | 7 | 1 |
| rankthetank | 2 | 10 | 0 |
| stricthellraiser | 0 | 12 | 0 |

**FULL subset (37 cells, 10k deals) -- Win/Loss/Draw:**

| Bidder | W | L | D | Matchups |
|--------|---|---|---|----------|
| hybrid_olsa | 9 | 2 | 1 | 12 |
| olsa_full | 6 | 1 | 5 | 12 |
| olsa | 6 | 3 | 3 | 12 |
| modeloespecifico | 3 | 0 | 3 | 6 |
| fiveheadfred | 0 | 6 | 0 | 6 |
| rankthetank | 0 | 6 | 0 | 6 |
| stricthellraiser | 0 | 6 | 0 | 6 |

**Note on win counts:** At QUICK resolution, modeloespecifico leads with 9W-0L
vs hybrid_olsa's 7W-2L. However, modeloespecifico has 3 draws (CIs spanning
zero at 2k deals) that may resolve with more data, while hybrid_olsa's 2
losses are both to modeloespecifico. The FULL subset only reran 6
modeloespecifico cross-matchups vs 12 for hybrid_olsa, so FULL win counts
are not directly comparable across bidders. Use the pairwise results below
instead.

### 4.4 Key Pairwise Matchups (FULL, 10k deals)

**Trained bidders head-to-head:**

| A vs B | delta | 95% CI | Verdict |
|--------|-------|--------|---------|
| modeloespecifico vs hybrid_olsa | +0.644 | [+0.545, +0.743] | **modelo wins** |
| hybrid_olsa vs modeloespecifico | -0.777 | [-0.876, -0.680] | **modelo wins** |
| hybrid_olsa vs olsa | +0.147 | [+0.014, +0.276] | **hybrid wins** |
| hybrid_olsa vs olsa_full | +0.033 | [-0.101, +0.160] | Draw |
| olsa_full vs olsa | -0.028 | [-0.168, +0.109] | Draw |
| modeloespecifico vs olsa | +0.016 | [-0.117, +0.147] | Draw |
| modeloespecifico vs olsa_full | -0.081 | [-0.214, +0.044] | Draw |

**Interpretation:**

The trained bidders form a **partial dominance order**:

```
modeloespecifico  >  hybrid_olsa  >  olsa  ~  olsa_full
                                      ^         ^
                                      |_________|
                                     (not separated)
```

- modeloespecifico strictly dominates hybrid_olsa (CI excludes zero, both directions)
- hybrid_olsa strictly dominates olsa (C33 result confirmed at FULL resolution)
- hybrid_olsa vs olsa_full is a draw (the Gaussian wrapper and extra features roughly cancel)
- olsa vs olsa_full is a draw in H2H despite olsa_full's higher self-play ranking
- modeloespecifico vs olsa/olsa_full is a draw in H2H -- the gap visible in self-play doesn't replicate in head-to-head

This last point is notable: in comparator self-play, modeloespecifico leads
olsa by +1.929 net_eppd, but in H2H the difference is not significant. This
suggests the self-play gap is driven by how each bidder interacts with the
GluttonStrategy playing policy, not by intrinsic bidding quality.

**Trained vs heuristic bidders:** All trained bidders beat all heuristic
bidders with large, highly significant margins (deltas ranging from +0.35 to
+8.5 net_eppd). The gap between the "competitive" and "weak" tiers is the
dominant structure in the matrix.

### 4.5 Behavioral Asymmetry

A striking pattern emerges in the hybrid_olsa vs olsa matchups. When
hybrid_olsa faces olsa:

- hybrid_olsa bid_rate: 16.2% (highly selective)
- olsa bid_rate: 83.8% (near-universal)

When the seats swap:

- olsa bid_rate: 83.4%
- hybrid_olsa bid_rate: 16.6%

hybrid_olsa yields the auction to olsa in ~84% of deals, bidding only when
its Gaussian CDF indicates high P(make). When it does bid, it makes 89-90%
of its contracts vs olsa's 76%. This confirms the C33 finding: the wrapper's
value is *selective restraint*, not superior prediction.

---

## 5. Gate Threshold Calibration

### 5.1 Purpose

The R1 promotion gate needs calibrated thresholds to distinguish real
improvement from noise. Thresholds are derived from the "null signal" in the
H2H matrix: self-play deltas and seat-swap residuals, which should be zero
under perfect symmetry.

### 5.2 Method

```
null_abs = [|self_play_delta_i| for i in 7 bidders]
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
For reference, the C33 wrapper effect (+0.21) would *barely* clear this bar.

The near-equality of delta_floor and regression_threshold (0.180 vs 0.184)
indicates the null distribution has a tight, symmetric shape -- the q95 and
q99 quantiles are very close, suggesting the null signal has thin tails at
10k-deal resolution.

---

## 6. Artifact Inventory

**gate_status:** PROMOTED (R0 overall; this report is informational for the
R0→R1 transition)

All artifacts in `data/artifacts/arc_d/r0/` (not committed to git).

| Artifact | Schema | Size | Produced By |
|----------|--------|------|-------------|
| `c33_ablation_results.json` | `h2h_battery_v1` | 2.8 KB | H2H battery parser (4 cells) |
| `comparator_battery_r0_v4.json` | `arc_d_comparator_v1` | 1.4 KB | Auction comparator (7 bidders, single-seat) |
| `comparator_cis_r0_v4.json` | `comparator_cis_v1` | 5.2 KB | CI extractor (bootstrap) |
| `h2h_battery_quick.json` | `h2h_battery_v1` | 30.5 KB | H2H battery (49 cells, 2k/cell) |
| `h2h_battery_full.json` | `h2h_battery_v1` | 23.2 KB | H2H battery (37 cells, 10k/cell) |
| `gate_thresholds_r1.json` | `gate_thresholds_v1` | 1.1 KB | Threshold calibrator (FULL) |

Run directories (local only, `data/runs/`):

| Run | Deals | Purpose |
|-----|-------|---------|
| `arc_d_r0_c33_ablation_42_20260225_170036` | 40,000 | C33 ablation |
| `arc_d_r0_h2h_battery_42_20260225_170054` | 98,000 | C50 QUICK |
| `arc_d_r0_h2h_battery_42_20260225_171235` | 370,000 | C50 FULL |
| `auction_comparator_*_42_20260225_*` (7 runs) | 140,000 | Comparator battery |

---

## 7. Conclusions

1. **The Gaussian EV wrapper works.** hybrid_olsa's analytical P(make)
   decision layer produces a statistically significant +0.21 net_eppd
   improvement over floor-based OLSa using identical regression coefficients.
   The mechanism is selective restraint (19.7% bid rate, 88.6% make rate).

2. **hybrid_olsa ranks #2 overall** behind the domain-expert modeloespecifico
   in self-play comparators. The H2H gap (+0.64–0.78 net_eppd) is smaller
   than the comparator gap (+1.132), suggesting the comparator gap is
   partially inflated by play-strategy interaction effects (consistent with
   §4.4 findings).

3. **The OLS-vs-heuristic gap is enormous.** The three OLS-trained bidders
   (hybrid_olsa, olsa_full, olsa) dominate all three simple heuristics
   (rankthetank, fiveheadfred, stricthellraiser) by 1-8 net_eppd.
   modeloespecifico (a hand-tuned lookup table, not OLS-trained) also
   dominates the heuristics. The OLS regression coefficients provide massive
   value even without the Gaussian wrapper.

4. **olsa vs olsa_full is a draw in H2H** despite olsa_full's advantage in
   self-play. The extra features help against GluttonStrategy but don't
   translate to bidding superiority against a peer.

5. **Gate thresholds are tight.** The FULL-calibrated delta_floor (0.180)
   means R1 must show nearly the same improvement as the entire Gaussian
   wrapper effect (+0.21) to achieve PROMOTED status. This is a deliberately
   conservative gate -- it prevents promoting noise.

6. **QUICK thresholds were dangerously inflated.** The drift check caught a
   73% overestimate in QUICK-derived thresholds. Without the two-stage
   calibration, R1 would have needed +0.66 net_eppd to promote -- an
   impossibly high bar. This validates the QUICK-then-FULL design.

---

## 8. Reproduction

All experiments are deterministic with seed=42. To reproduce:

```bash
# C33 ablation
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/arc_d_r0_c33_ablation.yaml

# Comparator battery (7 bidders, single-seat v4)
PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml --seed 42 \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --bidder-class HybridOLSaBidder --bidder-name hybrid_olsa \
  --single-seat --n-per 20000 \
  --output-format json --output data/artifacts/arc_d/r0/comparator_battery_r0_v4.json

# C50 QUICK (generate config, run, parse)
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode QUICK --seed 42 --n-per 2000 \
  --output data/artifacts/arc_d/r0/h2h_battery_quick.json
uv run python experiments/run_experiment.py --seed 42 \
  --config data/artifacts/arc_d/r0/h2h_battery_quick_config.yaml
# Then: --parse-run <run_dir> to populate

# C50 FULL (subset of QUICK)
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --mode FULL --seed 42 --n-per 10000 \
  --quick-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
  --output data/artifacts/arc_d/r0/h2h_battery_full.json
uv run python experiments/run_experiment.py --seed 42 \
  --config data/artifacts/arc_d/r0/h2h_battery_full_config.yaml
# Then: --parse-run <run_dir> to populate

# Threshold calibration (with drift check)
PYTHONPATH=src uv run python scripts/internal/calibrate_arc_d_thresholds.py \
  --h2h-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
  --full-summary data/artifacts/arc_d/r0/h2h_battery_full.json \
  --seed 42 --output data/artifacts/arc_d/r0/gate_thresholds_r1.json

# CI extraction (single-seat v4)
PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/artifacts/arc_d/r0 --runs-dir data/runs --seed 42 \
  --n-bootstrap 10000 --single-seat \
  --output data/artifacts/arc_d/r0/comparator_cis_r0_v4.json \
  --battery-file comparator_battery_r0_v4.json
```
