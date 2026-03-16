# R1 Feature Effect vs Gameplay Report

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R1 (partner context under trick-target objective)
**Status:** Prediction-gameplay disconnect diagnosed across three layers
**gate_status:** X3 STOP (training R^2 +0.40, gameplay -0.348 net_eppd)
**Date:** 2026-03-06
**Baseline:** [r1_baseline_statement.md](r1_baseline_statement.md)

## The Disconnect

R1 demonstrates that prediction quality and gameplay quality can diverge. The
training layer showed the largest R^2 improvement in the project's history
(+0.40 for suit), yet the evaluation layer showed a significant regression
(-0.348 net_eppd overall, -0.76 for suit). This disconnect is not anomalous —
it is the expected outcome when the training objective (tricks_won) is
misaligned with the evaluation objective (points_per_deal) and a degenerate
decision layer sits between them.

## Training Layer Evidence

### R^2 Improvement

| Contract | R0 Test R^2 | R1 Constrained Test R^2 | R1 Full Test R^2 | Delta |
|----------|-------------|-------------------------|------------------|-------|
| Suit | ~0.25 | 0.618 | 0.627 | +0.37 to +0.38 |
| High | ~0.25 | 0.576 | 0.570 | +0.32 to +0.33 |
| Low | ~0.25 | 0.553 | 0.551 | +0.30 |

### Feature Importance (Suit, Constrained Arm)

The constrained arm's selected features for suit contracts:

| Feature | Source | Role |
|---------|--------|------|
| bowers | Hand (R0 base) | Trump strength |
| trump_count | Hand (R0 base) | Trump length |
| offsuit_aces | Hand (R0 base) | Side-suit winners |
| partner_bid_level | Partner (R1 new) | Partner hand strength proxy |
| partner_passed | Partner (R1 new) | Partner weakness signal |
| partner_suit_match | Partner (R1 new) | Contract-family alignment |

`partner_bid_level` alone accounts for +0.329 R^2 in ablation (forward
selection log). This is a genuine, strong signal — knowing what the partner
bid tells you a great deal about combined trick-taking potential.

### Full Arm Feature Differences

The full arm's forward selection chose a different feature set:

| Feature | Notes |
|---------|-------|
| hand_value | Composite hand quality (replaces individual hand features) |
| partner_bid_confidence | Removed post-selection (redundant with partner_bid_level) |
| partner_passed | Same as constrained |
| quick_tricks | Guaranteed trick count |
| low_card_count | Losing card exposure |
| partner_suit_match | Same as constrained |

Despite different feature sets, both arms achieved similar R^2 (0.618 vs
0.627), confirming that the partner signal is the dominant contributor, not
the specific hand features chosen.

### High/Low Training

Both high and low contract models selected `partner_suit_match` but not
`partner_bid_level` or `partner_passed`. With fewer training examples (12k-17k
vs 102k for suit), the forward selection procedure had insufficient power to
detect weaker partner signals. This is a documented sample-size confound, not
evidence that partner features are uninformative for high/low.

## Decision Layer Evidence

### H10: Bid-Level Search Degeneracy

The decision layer uses `_compute_ev_static()` to evaluate the expected value
of each bid level, then `compute_best_bid()` selects the level with highest EV.

**H10 finding (PR #552):** For sigma > 0 (which is always true with real
model predictions), `_compute_ev_static()` produces EV values that are
monotonically non-increasing in `bid_n`. This means `compute_best_bid()` with
`bid_level_search=True` always selects the minimum legal bid level, regardless
of the predicted trick count.

This was proven analytically and validated with 101 parametric tests covering
the full (mu, sigma, bid_n) parameter space.

### Practical Consequence

Better trick predictions increase the model's confidence (lower sigma relative
to mu), but cannot change the bid-level decision. The decision layer is a
bottleneck that discards the information content of improved predictions:

```
R0: predict 7.2 tricks (sigma=1.5) → bid min_legal → win/lose
R1: predict 7.8 tricks (sigma=1.3) → bid min_legal → win/lose (same decision)
```

The only behavioral change from better predictions is the *frequency* of
bidding: R1 bids more often on marginal hands because the model is more
confident. But these additional bids are at minimum legal level, which has
lower EV than passing in many cases.

### bid_bonus Diagnostic Probe

`bid_bonus=0.25` (PR #554) adds a fixed bonus per bid level to the EV
computation, partially breaking the H10 degeneracy. Results:

- Overall delta reversed: -0.348 to +0.407 (CI [+0.19, +0.62])
- Suit deficit persisted: -0.456
- Higher bonus values (0.50+) not significant — overbidding starts

This confirms the decision layer is the major bottleneck but also reveals that
suit contracts have an additional deficit beyond bid-level selection. The
suit-specific issue may be related to contract-selection logic or
trump-evaluation specifics that persist even with corrected bid levels.

## Comparator Evidence

The dual-seat comparator battery (n=5,000, seed=42) provides a
GluttonStrategy-opponent reference:

| Rank | Bidder | net_eppd | 95% CI | Rung |
|------|--------|----------|--------|------|
| 1 | hybrid_olsa_full_r0 | +2.171 | [+2.083, +2.259] | R0 |
| 2 | hybrid_olsa_r0 | +2.143 | [+2.056, +2.229] | R0 |
| 3 | hybrid_olsa_r1 | +2.108 | [+2.028, +2.190] | R1 |
| 4 | hybrid_olsa_full_r1 | +2.103 | [+2.023, +2.185] | R1 |
| 5 | modeloespecifico_r0 | +1.988 | [+1.868, +2.106] | R0 |
| 6 | modeloespecifico_r1 | -10.494 | [-10.672, -10.314] | R1 |

All adjacent pairwise differences between ranks 1-4 are non-significant (p > 0.5).
The R1 OLSa variants are statistically indistinguishable from R0 in this
GluttonStrategy-opponent comparator, consistent with the H2H finding that the
regression is moderate and primarily suit-specific.

The comparator's GluttonStrategy opponent does not bid, so the bidder's
partner-context features receive no informative signal from the opponent. This
may attenuate the R1 regression signal compared to the H2H setting where both
teams bid.

ModeloEspecifico R1's catastrophic failure (-10.49) demonstrates that
hand-coded partner weight injection without model calibration is destructive
— the feature effect is real but must be channeled through proper training,
not additive heuristics.

## Reconciliation: Three-Layer Diagnosis

The prediction-gameplay disconnect resolves cleanly when analyzed per layer:

```
Training layer:     R1 IMPROVED     (R^2 +0.40, partner features informative)
                         ↓
Decision layer:     R1 DEGENERATE   (H10: always picks min_legal bid)
                         ↓
Evaluation layer:   R1 REGRESSED    (points_per_deal penalizes min-level bids)
```

Each layer's contribution is independently verified:

1. **Training improvement is real:** R^2 increase is consistent across arms,
   cross-validation folds, and contract types. Partner features capture genuine
   signal about combined trick-taking potential.

2. **Decision degeneracy is proven:** H10 is analytically demonstrated and
   parametrically tested. The decision layer discards prediction improvements.

3. **Evaluation regression follows logically:** If the decision layer cannot
   use better predictions, but those predictions change bidding *frequency*
   (more marginal bids at min level), the points-based evaluation must show
   a regression — more low-level bids means more set-risk without
   compensating point upside.

**The takeaway is not that partner features are bad, but that the decision
stack was insufficient to exploit them.** R1.5 (objective-alignment) must
fix the decision layer before partner features can be properly evaluated
for gameplay impact.

## Implications for R1.5

1. **Objective alignment is prerequisite:** R1.5 must train on or otherwise
   optimize for points_per_deal, not tricks_won, before partner features can
   demonstrate gameplay value.

2. **bid_bonus is a diagnostic tool, not a fix:** The 0.25 bonus showed the
   decision layer is the bottleneck, but a fixed bonus is not a principled
   solution. R1.5 needs E[points|state,bid_n,contract] or equivalent.

3. **Partner features should be preserved:** The training evidence strongly
   supports their predictive value. They should be available as candidate
   features under the new objective.

4. **Suit contracts need special attention:** The persistent suit deficit
   under bid_bonus=0.25 suggests contract-selection or trump-evaluation
   issues beyond bid-level degeneracy.

5. **ModeloEspecifico-style heuristics should be abandoned:** The R1
   comparator confirms that hand-coded partner weights are destructive.
   Partner information must flow through trained models.

## Provenance

| Item | Reference |
|------|-----------|
| Training report | `data/artifacts/arc_d/r1/training_report_r1.json` |
| Feature selection logs | `data/artifacts/arc_d/r1/feature_selection_log_r1_{constrained,full}.json` |
| Comparator battery | `data/artifacts/arc_d/r1/comparator_battery_r1_dual.json` |
| Comparator CIs | `data/artifacts/arc_d/r1/comparator_cis_r1.json` |
| H10 analytical proof | PR #552 (101 parametric tests) |
| bid_bonus diagnostic | PR #554 (6-bidder, 36 matchups) |
| H2H battery (Step 5) | 3-seed QUICK, 2k deals/matchup |
| Baseline statement | `docs/04_reports/arc_d_v1/r1/r1_baseline_statement.md` |
| Comparator config | `experiments/configs/auction_comparator_r1_dual.yaml` |
| Comparator command | `uv run python scripts/internal/run_auction_comparator.py --config experiments/configs/auction_comparator_r1_dual.yaml --dual-seat --seed 42 --n-per 5000` |
