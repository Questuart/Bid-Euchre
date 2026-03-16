# R1 Outcome Summary

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R1 (partner context under trick-target objective)
**Decision:** STOP — not promoted
**gate_status:** X3 STOP (primary delta -0.348 net_eppd)
**Date:** 2026-03-06
**Baseline:** [r1_baseline_statement.md](r1_baseline_statement.md)

## Executive Summary

R1 added coarse partner features (`partner_bid_level`, `partner_passed`,
`partner_suit_match`) to the R0 trick-prediction architecture. Training-layer
fit improved substantially (suit R^2: ~0.25 to ~0.63), but gameplay performance
**regressed** in H2H evaluation. Gate X3 returned STOP. R1 is preserved as a
historical trick-target rung; the objective-alignment rung (R1.5) is the
designated successor.

## What Changed (R0 to R1)

| Layer | Change | Outcome |
|-------|--------|---------|
| Data | Auction-context dataset with partner bid transcripts | 41,424 hands from 50k deals |
| Features | +3 partner features (bid_level, passed, suit_match) | `partner_bid_level` added +0.329 R^2 alone |
| Training | Dual-arm forward selection (constrained 3/2/2 + full) | Suit test R^2: 0.618 (constrained), 0.627 (full) |
| Decision | No change — same `_compute_ev_static()` + `compute_best_bid()` stack | H10 degeneracy persisted; better predictions did not reach bid decisions |

## Gate Results

| Gate | Criterion | Result |
|------|-----------|--------|
| X1 (smoke test) | Both arms train, partner features auto-discovered | **PASS** |
| X2 (training quality) | R^2 improvement >= +0.05 over R0 | **PASS** (+0.40 suit) |
| X3 (gameplay) | H2H net_eppd delta >= 0 vs R0 | **STOP** (delta = -0.348) |

## Comparator Rankings (Dual-Seat, n=5,000)

New comparator battery run against GluttonStrategy opponents, both partnership
seats using the same bidder (dual-seat mode):

| Rank | Bidder | net_eppd | 95% CI | Rung |
|------|--------|----------|--------|------|
| 1 | hybrid_olsa_full_r0 | +2.171 | [+2.083, +2.259] | R0 |
| 2 | hybrid_olsa_r0 | +2.143 | [+2.056, +2.229] | R0 |
| 3 | hybrid_olsa_r1 | +2.108 | [+2.028, +2.190] | R1 |
| 4 | hybrid_olsa_full_r1 | +2.103 | [+2.023, +2.185] | R1 |
| 5 | modeloespecifico_r0 | +1.988 | [+1.868, +2.106] | R0 |
| 6 | modeloespecifico_r1 | -10.494 | [-10.672, -10.314] | R1 |

**Key observations:**
- R1 OLSa variants rank 3-4, statistically tied with R0 variants (adjacent
  pairwise p-values > 0.5). The small negative delta (-0.03 to -0.07) is
  consistent with H2H evidence but not significant in this comparator.
- ModeloEspecifico R1 (hand-coded partner weights) is catastrophically bad
  (-10.49 net_eppd), confirming that naive partner-weight injection without
  proper calibration is destructive.

## H2H Key Matchups (Step 5 Canonical Evidence)

From the Step 5 battery (3-seed, QUICK mode, 2k deals/matchup):

| Matchup | Primary Delta (net_eppd) | 95% CI |
|---------|--------------------------|--------|
| R1 full vs R0 full (overall) | **-0.348** | significant |
| R1 full vs R0 full (suit) | **-0.76** | [-0.99, -0.53] |
| R1 full vs R0 full (high) | ~0 | CI spans zero |
| R1 full vs R0 full (low) | ~0 | CI spans zero |

The regression is isolated to suit contracts, where the partner features have
the strongest effect on trick prediction but cannot reach bid decisions through
the degenerate decision stack.

## Root Cause Summary

Three-layer diagnosis:

1. **Training layer (improved):** Partner features substantially improve trick
   prediction. `partner_bid_level` alone accounts for +0.329 R^2. This is a
   genuine signal about partner hand strength.

2. **Decision layer (degenerate):** `_compute_ev_static()` computes EV that is
   monotonically non-increasing in `bid_n` for sigma > 0 (H10, proven
   analytically in PR #552, 101 parametric tests). `compute_best_bid()` with
   `bid_level_search=True` always selects `min_legal`. Better trick predictions
   do not translate to better bid-level decisions.

3. **Evaluation layer (misaligned):** The model trains on `tricks_won` but is
   evaluated on `points_per_deal`. Points depend on bid level, contract
   selection, and make/set — none of which are optimized by trick-count
   prediction alone.

**Diagnostic probe:** `bid_bonus=0.25` reversed the overall delta to +0.407
(PR #554), but the suit-specific deficit persisted (-0.456). The decision layer
is the major bottleneck, but not the sole cause of the suit regression.

## What R1 Established for R1.5

1. Coarse partner features improve trick prediction substantially (+0.40 R^2)
2. Improved trick prediction does not guarantee improved gameplay
3. The trick-target to hand-coded-utility to bidding chain breaks at the utility step
4. Partner features are not intrinsically harmful — the decision stack was insufficient
5. ModeloEspecifico-style hand-coded partner weights are destructive without calibration
6. The dual-seat comparator instrument works for partner-aware evaluation

## Artifact Manifest

| Artifact | Path |
|----------|------|
| R1 model (constrained) | `data/artifacts/arc_d/r1/hybrid_r1.json` |
| R1 model (full) | `data/artifacts/arc_d/r1/hybrid_r1_full.json` |
| Training report | `data/artifacts/arc_d/r1/training_report_r1.json` |
| Comparator battery | `data/artifacts/arc_d/r1/comparator_battery_r1_dual.json` |
| Comparator CIs | `data/artifacts/arc_d/r1/comparator_cis_r1.json` |
| H2H battery config | `data/artifacts/arc_d/r1/h2h_battery_quick.json` |
| Feature selection logs | `data/artifacts/arc_d/r1/feature_selection_log_r1_{constrained,full}.json` |
| H10 validation | PR #552 (101 parametric tests) |
| bid_bonus sweep | PR #554 (6-bidder, 36 matchups) |
| Baseline statement | `docs/04_reports/arc_d_v1/r1/r1_baseline_statement.md` |

---

**Provenance:**
- Comparator battery: seed=42, n_per=5000, dual-seat mode, `experiments/configs/auction_comparator_r1_dual.yaml`
- Comparator CIs: 10,000 bootstrap resamples, seed=42
- H2H evidence: Step 5 canonical (3-seed QUICK, 2k deals/matchup)
- Training: seed=42, `canonical_auction_r1_42` dataset (41,424 hands)
