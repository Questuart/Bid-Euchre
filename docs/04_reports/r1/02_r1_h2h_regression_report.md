# R1 H2H Regression Report

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R1 (partner context under trick-target objective)
**Status:** Gameplay regression documented; root cause diagnosed
**Date:** 2026-03-06
**Baseline:** [r1_baseline_statement.md](r1_baseline_statement.md)

## Summary

R1 coarse partner context improved training-layer fit (+0.40 R^2 for suit) but
did not improve deployed bidding performance under the trick-target decision
stack. The H2H battery showed a significant suit-contract regression of -0.76
net_eppd. High and low contracts showed no significant change. The primary
delta across all contracts was -0.348 net_eppd.

This regression is attributed to the decision layer (H10 bid-level search
degeneracy) as the primary bottleneck, with the objective mismatch
(tricks_won vs points_per_deal) as the structural enabler.

## Methodology

### Evaluation Instrument

Step 5 H2H battery: 6-bidder roster (3 R1 + 3 R0), pairwise matchups, paired
deals for variance reduction.

| Parameter | Value |
|-----------|-------|
| Mode | QUICK (2,000 deals per matchup) |
| Seeds | 3 independent seeds (42, 43, 44) |
| Roster | hybrid_olsa_full_r1, hybrid_olsa_r1, modeloespecifico_r1, hybrid_olsa_full_r0, hybrid_olsa_r0, modeloespecifico_r0 |
| Play strategy | GluttonStrategy (both teams) |
| Bid-level search | Enabled (all OLSa variants) |
| risk_lambda | 0.0 (all OLSa variants) |

### Metrics

- **net_eppd** (primary): Net expected points per deal (bidder team minus opponent team). Differential metric; positive means the bidder earns more than the opponent.
- **eppd** (secondary): Expected points per deal for bidder team only.
- **CVaR-5%**: Average of worst 5% of per-hand outcomes. Tail risk measure.

### Canonical Evidence Source

All H2H numbers in this report are reused from Step 5 of the R1 training plan.
These were documented during the regression investigation (PRs #543-#553) and
frozen in the baseline statement. No new H2H runs were performed for this
closeout — the existing evidence is sufficient and re-running would not change
the diagnosis.

## Self-Play Sanity

R1 self-play win rates were approximately 47%, a downward shift from R0's ~50%.
This is consistent with R1's increased bidding aggression (better trick
predictions lead to higher confidence, triggering more bids at minimum legal
level due to H10). More bids at minimum level means more set opportunities,
reducing self-play win rate.

Self-play win rate is not a quality signal for R1 — it reflects the interaction
between improved prediction and degenerate bid-level selection.

## Rung-over-Rung Deltas

### Primary: R1 Full vs R0 Full

| Metric | R1 Full | R0 Full | Delta | Significant? |
|--------|---------|---------|-------|-------------|
| net_eppd (overall) | — | — | **-0.348** | Yes |
| net_eppd (suit) | — | — | **-0.76** | Yes, CI [-0.99, -0.53] |
| net_eppd (high) | — | — | ~0 | No, CI spans zero |
| net_eppd (low) | — | — | ~0 | No, CI spans zero |

### Attribution: R1 Constrained vs R0 Constrained

The constrained arm (locked base 3/2/2 + partner features) shows a similar
pattern to the full arm, confirming the regression is due to partner feature
addition under the trick-target stack, not to changes in forward-selected
feature sets.

## Contract-Family Slicing

### Suit Contracts (Primary Regression)

The suit regression (-0.76 net_eppd) is the dominant signal. Partner features
have their strongest predictive effect on suit contracts (`partner_bid_level`
alone adds +0.329 R^2), but this improved prediction cannot reach bid-level
decisions because `_compute_ev_static()` produces EV values that are
monotonically non-increasing in `bid_n` for sigma > 0.

The practical effect: R1's better suit predictions make it more confident about
suit hands, leading to more suit bids at minimum legal level. These minimum-level
bids have lower points per made contract but no lower set penalty, degrading
net_eppd.

### High Contracts

No significant change. High-contract models selected only `partner_suit_match`
(sample-size confound documented — fewer high-contract training examples).
The partner signal is too weak to materially change behavior.

### Low Contracts

No significant change. Same pattern as high — `partner_suit_match` selected
but insufficient to shift behavior measurably.

## Key Findings

1. **Suit regression is real and significant.** CI [-0.99, -0.53] excludes
   zero. This is not noise.

2. **High/low are unaffected.** CIs span zero. Partner features had
   insufficient signal in these contract families to change behavior.

3. **The regression is decision-layer mediated.** Better suit predictions
   make R1 more likely to bid suit contracts at minimum legal level (H10
   degeneracy), which is a net-negative outcome under points-based evaluation.

4. **bid_bonus=0.25 partially reverses the regression.** The overall delta
   flips to +0.407 with a 0.25 bid bonus (PR #554), but the suit-specific
   deficit persists at -0.456. The decision layer is the major bottleneck but
   not the sole cause.

5. **ModeloEspecifico R1 is catastrophically bad.** Hand-coded partner weights
   without model calibration produced -10.49 net_eppd in the comparator,
   confirming that naive partner-weight injection is destructive.

## Attribution

The regression is attributed to three layers, with the decision layer as the
primary bottleneck:

| Layer | Role | Evidence |
|-------|------|----------|
| Training | Improved prediction (beneficial) | +0.40 R^2 suit, +0.329 from partner_bid_level alone |
| Decision | Degenerate bid-level selection (harmful) | H10: EV monotonically non-increasing in bid_n; always picks min_legal |
| Objective | Misaligned training target (structural) | Train tricks_won, evaluate points_per_deal; R^2 ≠ gameplay quality |

Specifically: R1 coarse partner context improved prediction quality but did not
improve deployed bidding performance under the trick-target decision stack. The
improved predictions amplified the H10 degeneracy's harmful effects on suit
contracts.

## Provenance

| Item | Reference |
|------|-----------|
| H2H battery (Step 5) | 3-seed QUICK, 2k deals/matchup, seeds 42/43/44 |
| H10 analytical proof | PR #552 (101 parametric tests) |
| bid_bonus diagnostic | PR #554 (6-bidder, 36 matchups) |
| Two-stage training ablation | PRs #548/#549 |
| Investigation log | PR #551 (Investigation J) |
| Baseline statement | `docs/04_reports/r1/r1_baseline_statement.md` |
| Training report | `data/artifacts/arc_d/r1/training_report_r1.json` |
