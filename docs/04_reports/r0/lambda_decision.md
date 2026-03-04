# Lambda Tuning Decision — Track D

> **Version:** v2 (PR #510) | New in v2

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0
**Date:** 2026-03-03
**Purpose:** Determine whether CVaR risk aversion (lambda > 0) improves R0 competitive performance

## Executive Summary

**Decision: RETAIN lambda=0.0 (FINAL)**

A simulation-based sweep of 7 lambda candidates (lambda in {0.0, 0.05, 0.1, 0.2, 0.5,
1.0, 2.0}) found that lambda=0.5 maximized self-play net_eppd at +3.122 (delta=+0.884
vs lambda=0.0, CI excludes zero). However, H2H confirmation **reversed** this advantage:
lambda=0.5 lost to lambda=0.0 by -1.146 net_eppd (95% CI [-1.186, -1.106]), a swing
of -2.03 net_eppd from the self-play result.

| Metric | lambda=0.0 | lambda=0.5 (provisional) |
|--------|-----------|-------------------------|
| Self-play net_eppd | +2.238 | +3.122 |
| H2H net_eppd (vs lambda=0.0) | -- | -1.146 |
| Auction win rate (H2H) | ~82% | ~18% |
| Make rate (self-play) | 96.9% | 100.0% |
| Seat bid propensity | 93.5% | 46.8% |

**Key insight:** Self-play and H2H measure fundamentally different things. In self-play,
lambda=0.5's selective bidding avoids losses on marginal hands symmetrically. In H2H,
the opponent captures those auction opportunities -- lambda=0.5 wins only 18% of auctions,
ceding 82% of scoring opportunities to the risk-neutral opponent. The make rate improvement
(100% vs 97%) is negligible compared to the auction share loss.

No code changes required. All config surfaces retain `risk_lambda: 0.0`.

## 1. Motivation

The `risk_lambda` parameter controls the weight of a CVaR (Conditional Value at Risk)
tail-risk penalty in the Gaussian wrapper's bidding utility calculation:

```
utility = EV(mu, sigma, bid_n) - risk_lambda * max(0, -CVaR_5%(mu, sigma, bid_n))
```

At `risk_lambda=0.0` (current default), the bidder is risk-neutral -- it ignores
downside tail risk. A positive lambda penalizes bids with large downside tails,
making the bidder more selective on high-variance hands.

The default `risk_lambda=0.0` was set as a placeholder in PR #493 (Amendment A). All
canonical config surfaces carry explicit `risk_lambda: 0.0` entries awaiting the result
of this protocol. This Track D investigation determines whether a non-zero lambda
improves competitive performance.

**Protocol:** `plans/r0_v2_lambda_tuning_protocol.md` (v1, amended to v4)

**Dependency:** Track D runs sequentially after Track C (pass-threshold tuning). The
Track C result (RETAIN t=0, see [pass_threshold_decision.md](pass_threshold_decision.md))
is used as a fixed input (`pass_threshold=0.0`) throughout this protocol.

## 2. Methodology

### 2.1 Phase 1: Simulation-Based Self-Play Sweep

The protocol evolved from offline replay (v1) to simulation-based evaluation (v2
amendment), which captures auction dynamics and opponent responses that offline replay
cannot model.

| Parameter | Value |
|-----------|-------|
| Mode | Self-play (all 4 seats use same lambda, GluttonStrategy trick play) |
| Seed | 42 |
| Deals per lambda | 10,000 (paired across grid) |
| Grid | {0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0} |
| Model artifact | hybrid_r0.json |
| pass_threshold | 0.0 (Track C result) |
| bid_level_search | true |
| Bootstrap | 10,000 resamples, grouped by deal_id, seed 42 |
| epsilon (selection) | 0.02 net_eppd |

**Selection rule (epsilon-greedy):** Among guardrail-passing candidates, select the
smallest lambda within epsilon of the best net_eppd. This prefers the most risk-neutral
option when performance differences are negligible.

**Guardrail correction (v3 amendment):** The original bid_rate guardrail measured
deal-level aggregate (`fraction of deals with any bid`), which inflates toward 1.0
in 4-seat self-play due to `deal_bid_rate ~ 1 - (1-p)^4`. Amendment v3 corrected
this to seat-level bid propensity, which is the behaviorally relevant metric. See
protocol section 9 for the full derivation.

### 2.2 Phase 2: H2H Confirmation

Per protocol section 8.5, any lambda* > 0 receives PROVISIONAL status requiring H2H
confirmation before config adoption.

| Parameter | Value |
|-----------|-------|
| Mode | Head-to-head matrix |
| Matchups | lambda=0.5 vs lambda=0.0 (both rotations) + 2 self-play diagnostics |
| Seed | 42 |
| Deals per matchup | 10,000 (pair_deals=true) |
| Total deals | 40,000 |
| Run ID | lambda_h2h_confirmation_42_20260302_223731 |

## 3. Results -- Self-Play Sweep

### 3.1 Full Grid Results

| lambda | net_eppd | delta vs 0.0 | 95% CI | Seat Propensity | Make Rate | Guardrails |
|--------|----------|-------------|--------|-----------------|-----------|------------|
| 0.0 | +2.238 | -- | -- | 93.5% | 96.9% | PASS |
| 0.05 | +2.270 | +0.032 | [+0.021, +0.044] | 91.7% | 97.0% | PASS |
| 0.1 | +2.685 | +0.447 | [+0.391, +0.502] | 81.8% | 99.2% | PASS |
| 0.2 | +2.905 | +0.666 | [+0.605, +0.727] | 74.2% | 99.7% | PASS |
| **0.5** | **+3.122** | **+0.884** | **[+0.815, +0.952]** | **46.8%** | **100.0%** | **PASS** |
| 1.0 | +2.216 | -0.023 | [-0.103, +0.058] | 16.9% | 100.0% | PASS |
| 2.0 | +0.696 | -1.542 | [-1.620, -1.462] | 3.4% | 100.0% | **FAIL** (floor) |

All CIs are bootstrap 95%, 10,000 resamples, grouped by deal_id.

Net_eppd rises monotonically from lambda=0.0 through lambda=0.5, then drops sharply.
Lambda=2.0 is disqualified by the seat-propensity floor guardrail (3.4% < 5%). The
epsilon-greedy rule selects lambda=0.5 (no other candidate within epsilon=0.02 of
its +3.122 net_eppd).

**Self-play selection: lambda*=0.5 (PROVISIONAL, requires H2H confirmation)**

### 3.2 Mechanism: Self-Play Advantage

The self-play net_eppd improvement at lambda=0.5 comes from two sources:

1. **Perfect make rate:** Lambda=0.5 bids only on high-confidence hands (seat
   propensity 46.8% vs 93.5%), achieving 100% make rate vs 96.9% at lambda=0.0.
   Avoiding set penalties on marginal hands improves net_eppd.

2. **Symmetric selectivity:** In self-play, both teams use the same lambda. When
   both teams pass on marginal hands, more deals see no bid (4.7% all-pass rate at
   lambda=0.5). The hands that are bid are high-quality, producing better outcomes
   for both teams symmetrically.

## 4. Results -- H2H Confirmation

### 4.1 Cross-Matchup Results

| Rotation | lambda=0.5 net_eppd | lambda=0.0 net_eppd | Delta (0.5 - 0.0) | 95% CI |
|----------|--------------------|--------------------|-------------------|--------|
| R1 (0.5 as team0) | 4.370 | 5.590 | -1.220 | [-1.296, -1.144] |
| R2 (0.0 as team0) | 4.440 | 5.513 | -1.072 | [-1.149, -0.997] |
| **Paired average** | **4.405** | **5.552** | **-1.146** | **[-1.186, -1.106]** |

Lambda=0.5 loses to lambda=0.0 by -1.146 net_eppd. The CI excludes zero in both
rotations and in the paired average. The result is consistent across rotations
(delta within 0.15 of each other), indicating no seat-order confound.

### 4.2 Auction Dynamics

| Rotation | lambda=0.5 wins auction | lambda=0.0 wins auction | All-pass |
|----------|------------------------|------------------------|----------|
| R1 (0.5 as team0) | 17.8% | 82.2% | 0.0% |
| R2 (0.0 as team0) | 18.9% | 81.1% | 0.0% |

Lambda=0.5 wins the auction only ~18% of the time. Lambda=0.0 outbids lambda=0.5
on the marginal hands that lambda=0.5 passes on, capturing ~82% of auctions. Despite
lambda=0.0's lower make rate (96.9% vs 100%), owning the vast majority of auctions
at ~5.5 net_eppd per deal is decisive.

### 4.3 Self-Play Diagnostics

| Metric | lambda=0.5 self-play | lambda=0.0 self-play |
|--------|---------------------|---------------------|
| fullgame_eppd | 4.767 | 4.894 |
| bid_rate (deal) | 95.3% | 100.0% |
| make_rate | 100.0% | 96.9% |
| seat_bid_propensity | 46.8% | 93.5% |

Even in self-play fullgame_eppd, lambda=0.0 produces higher total scoring (4.894 vs
4.767). The self-play net_eppd advantage of lambda=0.5 in the sweep reflects the
simulation-level metric (differential per deal), while fullgame_eppd captures the
absolute scoring rate. Both teams score more total points when bidding aggressively.

## 5. Interpretation

### 5.1 Why Self-Play Reversed in H2H

The self-play vs H2H divergence reveals a fundamental dynamic of auction games:

**Self-play (same lambda both teams):** When both teams are equally selective, marginal
hands go unbid symmetrically. Lambda=0.5 performs well because the bid pool is
restricted to high-confidence hands -- fewer set penalties, higher net-differential on
the hands that are bid.

**H2H (different lambdas):** Lambda=0.0 bids aggressively on marginal hands that
lambda=0.5 passes on. In head-to-head, this means lambda=0.0 wins ~82% of auctions.
Even with a slightly lower make rate (~97% vs 100%), owning 82% of auctions dominates
lambda=0.5's 18% auction share. The 3-percentage-point make rate improvement cannot
compensate for ceding 64 percentage points of auction share.

**Analogy:** A conservative poker player who only plays premium hands will have a high
win-when-played rate but will bleed chips by folding profitable-but-volatile spots. The
aggressive player captures those spots, and the aggregate effect dominates.

### 5.2 Self-Play as a Screening Tool

This result demonstrates that self-play evaluation is valuable as a screening tool
(identifying candidates that are clearly harmful, like lambda=2.0) but cannot serve as
the sole decision criterion for tuning parameters that affect bid selectivity. The H2H
confirmation step in the protocol (section 8.5) was specifically designed to catch this
failure mode.

### 5.3 Connection to Model Quality

The lambda result parallels the [pass_threshold_decision.md](pass_threshold_decision.md)
finding: R0's model is not accurate enough on marginal hands to benefit from selective
bidding. Both the threshold sweep and the lambda sweep point to the same root cause --
the model's predictions near the bid/pass boundary are insufficiently calibrated.
Improving prediction quality in R1 may make risk-averse lambda values viable.

## 6. Impact and Decisions

### 6.1 Decision

| Criterion | Result |
|-----------|--------|
| Self-play lambda* | 0.5 (PROVISIONAL) |
| H2H delta | -1.146 |
| H2H 95% CI | [-1.186, -1.106] |
| CI excludes 0 | Yes (lambda=0.5 is significantly worse) |
| **Decision** | **RETAIN lambda=0.0** |

### 6.2 Config Surface Impact

Since the decision is RETAIN, no config surface changes are needed. The existing
`risk_lambda: 0.0` placeholder values are confirmed as correct:

| Config location | File | Status |
|----------------|------|--------|
| Auction comparator | experiments/configs/auction_comparator.yaml | `risk_lambda: 0.0` (unchanged) |
| C33 ablation | experiments/configs/arc_d_r0_c33_ablation.yaml | `risk_lambda: 0.0` (unchanged) |
| H2H battery roster | scripts/internal/run_arc_d_h2h_battery.py | `risk_lambda: 0.0` (unchanged) |

### 6.3 Implications for R1

1. **CVaR machinery validated** -- the risk penalty code works correctly and produces
   meaningful differentiation across the lambda grid
2. **Lambda=0.0 is optimal given R0 model quality** -- the model's predictions on
   marginal hands are not accurate enough to benefit from tail-risk avoidance
3. **Re-tune lambda after R1 model improvements** -- if R1 training improves calibration
   near the bid/pass boundary, lambda > 0 may become beneficial
4. **Consider joint threshold-lambda optimization** -- the sequential approach
   (threshold first, then lambda) may miss interaction effects worth exploring in R1

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | RETAIN (D0 decision gate -- no code change) |
| Protocol | `plans/r0_v2_lambda_tuning_protocol.md` v1 (amended to v4) |
| Sweep artifact | data/artifacts/arc_d/r0/lambda_sweep_selfplay_v1.json |
| Sweep script | `scripts/internal/run_lambda_sweep.py` |
| Analysis notebook | `notebooks/arc_d/r0/59_lambda_simulation_sweep.py` |
| H2H run ID | lambda_h2h_confirmation_42_20260302_223731 |
| Model artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| Seed | 42 |
| Sweep deals per lambda | 10,000 |
| H2H deals per matchup | 10,000 |
| Bootstrap resamples | 10,000 |

## 8. Reproduction

### Self-Play Sweep

```bash
uv run python scripts/internal/run_lambda_sweep.py \
  --seed 42 \
  --n-per 10000 \
  --artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --output data/artifacts/arc_d/r0/lambda_sweep_selfplay_v1.json
```

### H2H Confirmation

```bash
uv run python experiments/run_experiment.py \
  --config experiments/configs/lambda_h2h_confirmation.yaml \
  --seed 42 --force
```

### Companion Reports

| Report | Focus |
|--------|-------|
| [pass_threshold_decision.md](pass_threshold_decision.md) | Track C threshold sweep (same root cause: model quality) |
| [normalizer_offline_screen.md](normalizer_offline_screen.md) | Track E normalizer pre-screen (related model quality limitation) |
| [model_arc_r0.md](model_arc_r0.md) | R0 rung report (overall model evaluation) |
| [h2h_battery_analysis.md](h2h_battery_analysis.md) | H2H battery analysis (competitive ordering) |
