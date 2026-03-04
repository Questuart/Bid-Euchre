# ARC_D Rung R0 Report

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Date:** 2026-02-24 (generated); 2026-03-01 (narrative refactor)
**gate_status:** PROMOTED

---

## Executive Summary

**What is this?** The R0 baseline establishment for Arc D's OLSa-Hybrid bidder
— the first trainable bidding model in the Bid Euchre framework.

**What did we do?** Six experiment campaigns totaling ~650,000 deals evaluated
two model arms (OLSa constrained + OLSa_Full promotional) across self-play,
comparator, and head-to-head batteries. All runs used seed=42 for deterministic
reproducibility.

**What did we find?** Both arms produce positive net_eppd (eval), ranking among
the top bidders in the framework:

| Metric | OLSa (constrained, eval) | OLSa_Full (promotional, eval) |
|--------|--------------------------|-------------------------------|
| net_eppd | +1.953 | +1.932 |
| eppd | +5.815 | +5.795 |
| bid_rate | 100% | 100% |
| make_rate | 95.2% | 94.9% |

In the v6 single-seat comparator (GluttonStrategy, 20k deals/bidder, 8
bidders), hybrid_olsa ranks 1-2 (tied with hybrid_olsa_full) among 8 bidders at
net_eppd +2.131 (comparator), leading modeloespecifico (+1.604, comparator) by
+0.527 points/deal (p < 0.001). The bid-level search (v2) dramatically changed
bidding behavior: bid_rate rose from 19.7% to 96.1%, make_rate from 88.6% to
100%, driving the net_eppd improvement from +0.455 to +2.131. The C33 ablation
shows a combined search effect (+0.43) and wrapper effect (+0.75).

**What are the caveats?** The attribution gap is negative (−0.14): the
constrained arm slightly outperforms the full arm on net_eppd, likely because
the constrained arm's hand-picked features are more robust at R0 model quality.
With v2 bid-level search both arms now bid ~100% of deals, so the gap reflects
pure model quality rather than bid-rate selectivity. HIGH/LOW contract types
have small sample sizes and only 1 feature each, producing high regret (oracle
analysis, PR #472). The v2 bid-level search substantially reduced
pass-threshold regret (CS regret share: 90.9%), though model accuracy remains
the binding constraint (pass-threshold decision: RETAIN t=0). Lambda tuning
(RETAIN lambda=0.0) and normalizer screening (NO_GO_DEFER_R1) were evaluated
and deferred.

**What's the decision?** **PROMOTED** — passes all Tier 1 artifact integrity
gates, stable across 3 evaluation seeds (net_eppd range < 0.06), and
establishes a working baseline for R1 feature enrichment.

### Companion Reports

| Report | Focus |
|--------|-------|
| [01_r0_promotion_report.md](01_r0_promotion_report.md) | Promotion decision, gate results, threshold calibration |
| [03_comparator_rankings.md](03_comparator_rankings.md) | v6 single-seat rankings (8 bidders, GluttonStrategy) |
| [04_r0_experiment_summary.md](04_r0_experiment_summary.md) | H2H battery (v4), competitive ordering, threshold derivation |
| [05_c33_ablation_report.md](05_c33_ablation_report.md) | C33 v2: search effect +0.43, wrapper effect +0.75 |
| [10_contract_selection_oracle.md](10_contract_selection_oracle.md) | Oracle regret analysis, CS regret share 90.9% |
| [11_pass_threshold_decision.md](11_pass_threshold_decision.md) | B0 threshold sweep: RETAIN t=0 |
| [12_lambda_decision.md](12_lambda_decision.md) | Lambda tuning: RETAIN lambda=0.0 (FINAL) |
| [13_normalizer_offline_screen.md](13_normalizer_offline_screen.md) | Normalizer screen: NO_GO_DEFER_R1 |
| [20_measurement_integrity_r0.md](20_measurement_integrity_r0.md) | Methodology limitations + deferral costs |

---

## Data Inventory

### Provenance

- **Bundle:** rung_bundle_r0.json
- **Rung:** r0
- **Split manifest:** data/artifacts/arc_d/r0/split_manifest_r0_suit.json

### Eval Dataset Summary

- **Total deals:** 50,000
- **Total rows:** 200,000
- **Seats per deal:** 4
- **Bid rate:** 100% (v2 bid-level search eliminates all-pass redeals)

### Per-Contract Deal Counts

| Contract Type | Deals | Rows | Pct |
|---------------|-------|------|-----|
| suit | 30,760 | 123,040 | 61.5% |
| high | 7,635 | 30,540 | 15.3% |
| low | 11,605 | 46,420 | 23.2% |

---

## Feature Health Summary

Data quality is clean across all 39 features and 3 contract types. No missing
values, no anomalies, and seat balance is tight (max deviation from grand mean =
0.58 on a mean of 491.7). Feature distributions are consistent with the Phase 0
bidless baseline.

> See notebook 10_feature_health for full feature distribution plots and
> seat-balance diagnostics.

### Seat Balance

Max deviation from grand mean = 0.58 (grand mean = 491.7)

| Seat | Mean hand_value |
|------|----------------|
| 0 | 492.1 |
| 1 | 492.1 |
| 2 | 491.1 |
| 3 | 491.4 |

### Per-Contract Feature Statistics

#### high (n=30,540)

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| hand_value | 300.00 | 66.52 | 170.00 | 460.00 |
| offsuit_best_rank_sum | 11.83 | 2.68 | 5.00 | 21.00 |
| quick_tricks | 2.14 | 2.65 | 0.00 | 9.00 |
| offsuit_aces | 2.00 | 2.40 | 0.00 | 7.00 |
| offsuit_non_ace_count | 8.00 | 2.40 | 3.00 | 10.00 |

#### low (n=46,420)

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| hand_value | 300.00 | 66.07 | 160.00 | 470.00 |
| quick_tricks | 2.14 | 2.67 | 0.00 | 9.00 |
| offsuit_best_rank_sum | 11.77 | 2.67 | 5.00 | 20.00 |
| offsuit_tens_count | 2.00 | 2.43 | 0.00 | 7.00 |
| offsuit_secondbest_rank_sum | 8.57 | 2.25 | 3.00 | 16.00 |

#### suit (n=123,040)

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| hand_value | 495.00 | 116.45 | 170.00 | 930.00 |
| trump_power_sum | 10.50 | 6.28 | 0.00 | 35.00 |
| trump_count_x_offsuit_ace | 4.44 | 4.00 | 0.00 | 25.00 |
| offsuit_best_rank_sum | 11.10 | 3.04 | 1.00 | 25.00 |
| trump_count_x_void_count | 3.68 | 2.86 | 0.00 | 27.00 |

---

## Outcome Health Summary

The overall mean tricks of 5.00 confirms the eval dataset is unbiased — in a
10-trick game with paired deals, the expected mean is exactly 5. The suit
contract distribution is tighter (std=2.15, P5=1.0-P95=9.0) than HIGH/LOW
(std~1.9), reflecting that trump contracts create more dispersed outcomes due
to role asymmetry (declaring mean ~6.3, defending mean ~3.7).

With v2 bid-level search producing 100% bid_rate, all 50,000 deals have auction
outcomes. HIGH (n=7,635 deals, 30,540 rows) and LOW (n=11,605 deals, 46,420 rows)
now far exceed the 2,000-deal minimum for reliable distribution characterization.

> See notebook 20_outcome_health for outcome distributions and make-rate
> analysis by contract type.

- **Overall mean tricks:** 5.00
- **Overall std:** 2.07
- **Range:** [0.0, 10.0]

### Per-Contract Outcome Statistics

| Contract | Mean | Std | P5 | P95 | n |
|----------|------|-----|-----|-----|---|
| suit | 5.00 | 2.15 | 1.0 | 9.0 | 123,040 |
| high | 5.00 | 1.94 | 2.0 | 8.0 | 30,540 |
| low | 5.00 | 1.92 | 2.0 | 8.0 | 46,420 |

**Overall make rate:** 0.952

| Contract | Make Rate | n |
|----------|-----------|---|
| suit | 0.956 | 30,760 |
| high | 0.954 | 7,635 |
| low | 0.937 | 11,605 |

---

## Auction Analysis

The v2 auction shows a dramatically diversified contract mix compared to v1.
Suit contracts account for 61.5% of deals, with HIGH (15.3%) and LOW (23.2%)
now meaningfully represented. This shift is driven by bid-level search (v2):
the model evaluates all legal bid levels and selects by maximum utility, enabling
it to bid lower on HIGH/LOW hands where the 1-feature models produce moderate
trick predictions. The oracle analysis
([10_contract_selection_oracle.md](10_contract_selection_oracle.md)) shows the
hindsight-optimal HIGH+LOW share is 31.9%; the v2 model achieves 38.5%,
overshooting slightly due to bidding on marginal hands that the oracle would pass.

Bid levels concentrate at 3-4 (mean 3.74), reflecting the model's willingness
to bid conservatively. The bid=4 level dominates at 73.9%, with bid=3 at 25.8%
and a small bid=2 tail (0.3%). The narrow range [2,4] contrasts sharply with
v1's [5,8] range — bid-level search finds profitable bids at lower levels that
the v1 floor-only policy missed. Seat balance in auction outcomes is verified
in notebook 25_auction_health.

> See notebook 25_auction_health for bid distribution histograms and seat-level
> auction balance diagnostics.

### Contract Selection Frequency

| Contract | Count | Pct |
|----------|-------|-----|
| suit | 30,760 | 61.5% |
| low | 11,605 | 23.2% |
| high | 7,635 | 15.3% |

### Bid Distribution

- **Mean winning bid:** 3.74
- **Bid range:** 2--4
- **Std:** 0.45

### Auction Summary

| Contract | Deals | Make Rate | Mean Bid |
|----------|-------|-----------|----------|
| high | 7,635 | 0.954 | 3.72 |
| low | 11,605 | 0.937 | 3.77 |
| suit | 30,760 | 0.956 | 3.73 |

### Auction Plumbing Validation

Auction mechanics are validated by 5 test files covering the full bidding and play pipeline:

- `tests/unit/test_auction_bidding_rules.py` — all-pass redeal, strict-increasing bids, winner determination, contract type selection
- `tests/unit/test_bidding_sequential_semantics.py` — LOD bidding order, strict-raise legality
- `tests/integration/test_rules_invariants.py` — bower ordering, trump beats non-trump, follow-suit, LOW rank reversal
- `tests/integration/test_auction_repeatability.py` — seed determinism for auction mode
- `tests/integration/test_simulation_validation.py` — trick distribution sums, team totals = 10, average in [4,6]

The comparator battery (including dumb bidders like rankthetank and fiveheadfred) runs through the full auction + play pipeline, serving as an implicit integration test across all contract types and bid levels.

---

## Model Specification & Feature Selection

R0 uses ordinary least squares (OLS) regression — a deliberate baseline choice.
Linear models are interpretable, fast to train, and provide a clear attribution
baseline against which more complex architectures can be measured.

The dual-arm design runs two models in parallel: a **constrained arm** (OLSa)
with hand-picked features locked across all rungs, and a **promotional arm**
(OLSa_Full) with forward-selected features that can evolve per rung. The
constrained arm serves as an attribution baseline — any improvement in the
promotional arm beyond the constrained arm's performance is attributable to
feature selection quality.

Feature selection for OLSa_Full uses forward selection with GroupKFold
(grouped by hand_id to prevent leakage). The `min_improvement` threshold
governs how aggressively features are added.

> See notebook 30_feature_outcome_eval for feature selection traces,
> coefficient stability analysis, and the forward selection progression.

### OLSa (constrained)

**Total features:** 5

- **high** (1): offsuit_aces
- **low** (1): offsuit_tens_count
- **suit** (3): bowers, trump_count, offsuit_aces

### OLSa_Full (promotional)

**Total features:** 7

- **high** (2): offsuit_non_ace_count, offsuit_best_rank_sum
- **low** (2): offsuit_tens_count, offsuit_best_rank_sum
- **suit** (3): hand_value, quick_tricks, low_card_count

### OLSa Coefficients

#### high

Bias: 3.5788

| Feature | Weight |
|---------|--------|
| offsuit_aces | +0.7106 |

#### low

Bias: 3.5694

| Feature | Weight |
|---------|--------|
| offsuit_tens_count | +0.7153 |

#### suit

Bias: 2.7455

| Feature | Weight |
|---------|--------|
| bowers | +0.4493 |
| trump_count | +0.4316 |
| offsuit_aces | +0.3403 |

### OLSa_Full Coefficients

#### high

Bias: 9.5419

| Feature | Weight |
|---------|--------|
| offsuit_non_ace_count | -0.6598 |
| offsuit_best_rank_sum | +0.0592 |

#### low

Bias: 2.9496

| Feature | Weight |
|---------|--------|
| offsuit_tens_count | +0.6654 |
| offsuit_best_rank_sum | +0.0578 |

#### suit

Bias: 0.2379

| Feature | Weight |
|---------|--------|
| hand_value | +0.0075 |
| quick_tricks | +0.1947 |
| low_card_count | +0.1511 |

---

## Model Performance

R² values of 0.24-0.29 are expected for R0's linear models predicting trick
outcomes in a high-variance card game. For context, the theoretical ceiling for
a hand-evaluation model (ignoring opponent hands and play dynamics) is likely
well below 1.0 — even a perfect hand evaluator cannot predict the random
elements of deal, trick play, and opponent decisions.

The HIGH/LOW R² values (0.28-0.29) are slightly higher than suit (0.24), but
this reflects the larger outcome variance in no-trump contracts (std~3.2 vs
2.5), not better predictions. MAE values are correspondingly higher for
HIGH/LOW (2.2 vs 1.8 tricks).

> See notebook 30_feature_outcome_eval, S6.1 for Gaussian assumption validation
> (residual distributions, Q-Q plots, normality tests).

### OLSa (constrained)

| Contract | R² | MAE | n |
|----------|-----|-----|---|
| high | 0.2793 | 2.2105 | 1044 |
| low | 0.2865 | 2.2524 | 1124 |
| suit | 0.2430 | 1.7775 | 124280 |

### OLSa_Full (promotional)

| Contract | R² | MAE | n |
|----------|-----|-----|---|
| high | 0.2799 | 2.1987 | 1044 |
| low | 0.2820 | 2.2554 | 1124 |
| suit | 0.2469 | 1.7730 | 124280 |

---

## Dual-Arm Comparison & Attribution Gap

### Arm Overview

| Metric | OLSa (constrained) | OLSa_Full (promotional) |
|--------|-------------------|------------------------|
| Features | high:1, low:1, suit:3 | high:2, low:2, suit:3 |
| Artifact SHA | 7b523cd6 | 5436b759 |
| Gate (val) | — | — |

### Attribution Gap

| Arm | net_eppd (eval) |
|-----|-----------------|
| OLSa (constrained) | +1.953 (eval) |
| OLSa_Full (promotional) | +1.932 (eval) |
| **Attribution Gap** | **+0.021** |

The attribution gap is near zero and slightly positive: the constrained arm
marginally outperforms the promotional arm by +0.021 net_eppd. This is benign
at R0 — the constrained arm's hand-picked features (bowers, trump_count,
offsuit_aces) are individually strong predictors, and the forward-selected
features add marginal complexity without improving trick prediction accuracy.
With v2 bid-level search, both arms bid on 100% of deals, so the gap reflects
pure model quality rather than bid-rate selectivity. The gap narrowed
substantially from v1 (−0.144) to v2 (+0.021), confirming that v1's apparent
gap was inflated by differential bid-rate effects. See
[01_r0_promotion_report.md](01_r0_promotion_report.md) §4 for full interpretation.

### Comparator Battery (v6, Single-Seat, GluttonStrategy)

The single-seat comparator evaluates each bidder in isolation — one seat bids
while three always-pass sentinels fill the remaining seats — producing an
absolute benchmark free from auction interaction confounds. See
[03_comparator_rankings.md](03_comparator_rankings.md) for full methodology and
behavioral analysis.

| Rank | Bidder | net_eppd (comparator) | 95% CI | bid_rate | make_rate |
|------|--------|----------------------|--------|----------|-----------|
| 1 | **hybrid_olsa_full** | **+2.170** | **[+2.081, +2.257]** | 96.8% | 100% |
| 2 | **hybrid_olsa** | **+2.131** | **[+2.042, +2.216]** | 96.1% | 100% |
| 3 | modeloespecifico | +1.604 | [+1.489, +1.720] | 100% | 94.7% |
| 4 | stricthellraiser | +0.085 | [−0.027, +0.197] | 100% | 94.5% |
| 5 | olsa_full | −0.012 | [−0.193, +0.173] | 100% | 77.2% |
| 6 | olsa | −0.225 | [−0.413, −0.037] | 100% | 75.6% |
| 7 | fiveheadfred | −2.579 | [−2.771, −2.384] | 100% | 64.9% |
| 8 | rankthetank | −9.665 | [−9.851, −9.483] | 100% | 15.0% |

hybrid_olsa_full and hybrid_olsa are statistically tied (delta=+0.038,
p=0.5457). hybrid_olsa now leads modeloespecifico by +0.527 points/deal
(p < 0.001) — a reversal from v4 where modelo led by +1.132. The improvement
is driven by bid-level search (v2): hybrid_olsa bid_rate rose from 19.7% to
96.1% and make_rate from 88.6% to 100%.

**Instrument note:** Eval net_eppd (+1.953 for OLSa, eval) and comparator
net_eppd (+2.131 for hybrid_olsa, comparator v6 single-seat) measure different
estimands. Eval uses self-play where both teams bid; the comparator uses
single-seat mode where only the test bidder bids against always-pass sentinels,
with GluttonStrategy card play. The eval figure reflects competitive bidding
dynamics while the comparator isolates bidding quality in a controlled setting.

**Source:** comparator_cis_r0_v6.json

### H2H Self-Play Baseline

Head-to-head matchups pit bidders directly against each other in contested
auctions with paired, seat-swapped deals. See
[04_r0_experiment_summary.md](04_r0_experiment_summary.md) for the full H2H matrix
(QUICK + FULL resolution, v4) and gate threshold derivation.

**H2H Self-Play (FULL, v4):** delta=−0.048, CI=[−0.132, +0.038],
fullgame_eppd=4.894. The near-zero delta confirms self-play symmetry; the
fullgame_eppd of 4.894 establishes the H2H baseline.

For pairwise competitive matchups, see the
[H2H pairwise analysis](07_h2h_pairwise_analysis.md) companion report. Key
results: modeloespecifico beats hybrid_olsa by ~0.35 net_eppd delta (both
rotations significant); hybrid_olsa dominates stricthellraiser by ~1.53 delta.

**Source:** h2h_battery_quick_v4, h2h_battery_full_v4

### Promotion Decision

- **Outcome:** PROMOTED
- **gate_status:** PROMOTED

### Feature Correlations

Top features by absolute Pearson correlation with `tricks_won`, per contract type.

#### high

| Feature | r |
|---------|---|
| quick_tricks | +0.5328 |
| offsuit_aces | +0.5287 |
| offsuit_non_ace_count | -0.5287 |
| hand_value | +0.5150 |
| offsuit_suits_with_ace | +0.5148 |

#### low

| Feature | r |
|---------|---|
| quick_tricks | +0.5385 |
| offsuit_tens_count | +0.5353 |
| hand_value | +0.4726 |
| low_card_count | +0.4516 |
| offsuit_secondbest_rank_sum | +0.3927 |

#### suit

| Feature | r |
|---------|---|
| hand_value | +0.4755 |
| offsuit_non_ace_count | -0.4717 |
| trump_power_sum | +0.4535 |
| trump_count | +0.4239 |
| third_highest_trump_rank | +0.4233 |

---

## Semantic Gate Summary

R0 uses a reduced gate (Tier 1 only — artifact integrity checks). The 4
Tier 1 checks all pass:

| Check | Result |
|-------|--------|
| artifact_integrity_olsa | PASS |
| artifact_integrity_olsa_full | PASS |
| no_nan_inf_olsa | PASS |
| no_nan_inf_olsa_full | PASS |

Full semantic gate (Tier 2: calibration, fairness, stability) is introduced at
R1+, where model improvements justify the additional verification overhead.

**Overall gate status:** PROMOTED

---

## Known Limitations

These are R0-specific limitations, not generic caveats:

1. **Feature poverty for HIGH/LOW.** The HIGH model uses 1 feature
   (offsuit_aces) and the LOW model uses 1 feature (offsuit_tens_count),
   producing ~9 discrete predicted-trick values each. This prevents meaningful
   calibration and is the dominant source of oracle regret (CS regret share
   90.9%). R1 feature enrichment is the primary remedy.

2. **Negative attribution gap.** The constrained arm outperforms the
   promotional arm by 0.14 net_eppd (eval). This suggests forward feature
   selection at R0's sample size and model complexity does not yet add value
   beyond hand-picked features. Monitored via `check_dual_arm_coherence` at R1+.

3. **Single-seed comparator data.** Comparator rankings (v6) and H2H matchups
   (v4) use seed=42 only. Multi-seed averaging would reduce variance in ranking
   estimates but was not prioritized for R0 given the clear tier separation.

4. **Pass-threshold regret is a model problem, not a threshold problem.** The
   B0 sweep (PR #476) showed net_diff decreases monotonically with higher t —
   marginal hands can't be profitably bid at R0 model quality. Bid-level search
   (v2) drives bid_rate to ~100% for both arms (eval) and substantially
   improved bidding behavior, but model accuracy remains the binding constraint.
   This can only be further addressed through better models (R1+).

5. **GluttonStrategy confounding.** Both comparator and eval instruments use
   GluttonStrategy for card play. Rankings reflect interaction with this
   specific play strategy. See
   [20_measurement_integrity_r0.md](20_measurement_integrity_r0.md) for full
   limitation inventory.

6. **Normalizer deferred to R1.** Offline screening showed normalizer adds
   +4% accuracy but degrades net_eppd by −0.269 (CI [−0.287, −0.251]). This
   is a model poverty problem, not a miscalibration — deferred to R1 where
   richer models may benefit from normalization. See
   [13_normalizer_offline_screen.md](13_normalizer_offline_screen.md).

---

## Reproduction Commands

### Generate Eval Dataset

```bash
# Parse JSONL logs into eval DataFrame:
uv run python -c "
from bid_euchre.datasets.eval_dataset import build_eval_dataset
df = build_eval_dataset('data/runs/arc_d_eval_r0_42_20260303_201729/logs/*.jsonl')
df.to_parquet('eval_df.parquet')
"
```

### Generate Report

```bash
# Regenerate the auto-generated tables:
uv run python -c "
from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
import pandas as pd
df = pd.read_parquet('eval_df.parquet')
generate_arc_d_rung_report('data/artifacts/arc_d/r0/rung_bundle_r0.json', eval_df=df, output_path='report.md')
"
```

### Run Notebooks

```bash
# Execute the evaluation notebooks:
uv run jupyter nbconvert --to notebook --execute \
  notebooks/arc_d/r0/10_feature_health.ipynb
uv run jupyter nbconvert --to notebook --execute \
  notebooks/arc_d/r0/20_outcome_health.ipynb
uv run jupyter nbconvert --to notebook --execute \
  notebooks/arc_d/r0/30_feature_outcome_eval.ipynb
```
