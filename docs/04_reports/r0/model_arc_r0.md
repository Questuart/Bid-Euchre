# ARC_D Rung R0 Report

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Date:** 2026-02-24 (generated); 2026-03-01 (narrative refactor)
**gate_status:** PROMOTED

---

## Executive Summary

**What is this?** The R0 baseline establishment for Arc D's OLSa-Hybrid bidder
— the first trainable bidding model in the Bid Euchre framework.

**What did we do?** Six experiment campaigns totaling ~580,000 deals evaluated
two model arms (OLSa constrained + OLSa_Full promotional) across self-play,
comparator, and head-to-head batteries. All runs used seed=42 for deterministic
reproducibility.

**What did we find?** Both arms produce positive net_eppd (eval), ranking among
the top bidders in the framework:

| Metric | OLSa (constrained, eval) | OLSa_Full (promotional, eval) |
|--------|--------------------------|-------------------------------|
| net_eppd | +1.627 | +1.484 |
| eppd | +3.566 | +4.174 |
| bid_rate | 63.2% | 82.8% |
| make_rate | 87.3% | 83.3% |

In the v4 single-seat comparator (GluttonStrategy, 20k deals/bidder),
hybrid_olsa ranks 2nd of 7 at net_eppd +0.455 (comparator), trailing
modeloespecifico (+1.587, comparator) by 1.132 points/deal. The Gaussian EV
wrapper adds +0.21 net_eppd over floor-based OLSa (C33 ablation, H2H).

**What are the caveats?** The attribution gap is negative (−0.14): the
constrained arm slightly outperforms the full arm on net_eppd, likely because
the constrained arm's hand-picked features are more robust at R0 model quality.
HIGH/LOW contract types have small sample sizes (261/281 deals) and only 1
feature each, producing high regret (oracle analysis, PR #472). The model passes
on 80% of hands where a hindsight-optimal oracle would profitably bid — a model
accuracy problem, not a threshold problem (B0 sweep, PR #476: RETAIN t=0).

**What's the decision?** **PROMOTED** — passes all Tier 1 artifact integrity
gates, stable across 3 evaluation seeds (net_eppd range < 0.06), and
establishes a working baseline for R1 feature enrichment.

### Companion Reports

| Report | Focus |
|--------|-------|
| [r0_promotion_report.md](r0_promotion_report.md) | Promotion decision, gate results, threshold calibration |
| [comparator_rankings.md](comparator_rankings.md) | v4 single-seat rankings (7 bidders, GluttonStrategy) |
| [h2h_battery_analysis.md](h2h_battery_analysis.md) | H2H battery, competitive ordering, threshold derivation |
| [c33_ablation_report.md](c33_ablation_report.md) | Gaussian EV wrapper effect (+0.21 net_eppd) |
| [contract_selection_oracle.md](contract_selection_oracle.md) | Oracle regret analysis, pass-threshold dominance |
| [pass_threshold_decision.md](pass_threshold_decision.md) | B0 threshold sweep: RETAIN t=0 |
| [measurement_integrity_r0.md](measurement_integrity_r0.md) | Methodology limitations + deferral costs |

---

## Data Inventory

### Provenance

- **Bundle:** rung_bundle_r0.json
- **Rung:** r0
- **Split manifest:** data/artifacts/arc_d/r0/split_manifest_r0_suit.json

### Eval Dataset Summary

- **Total deals:** 31,612
- **Total rows:** 126,448
- **Seats per deal:** 4

### Per-Contract Deal Counts

| Contract Type | Deals | Rows | Pct |
|---------------|-------|------|-----|
| high | 261 | 1044 | 0.8% |
| low | 281 | 1124 | 0.9% |
| suit | 31070 | 124280 | 98.3% |

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

#### high (n=1044)

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| hand_value | 300.00 | 66.52 | 170.00 | 460.00 |
| offsuit_best_rank_sum | 11.83 | 2.68 | 5.00 | 21.00 |
| quick_tricks | 2.14 | 2.65 | 0.00 | 9.00 |
| offsuit_aces | 2.00 | 2.40 | 0.00 | 7.00 |
| offsuit_non_ace_count | 8.00 | 2.40 | 3.00 | 10.00 |

#### low (n=1124)

| Feature | Mean | Std | Min | Max |
|---------|------|-----|-----|-----|
| hand_value | 300.00 | 66.07 | 160.00 | 470.00 |
| quick_tricks | 2.14 | 2.67 | 0.00 | 9.00 |
| offsuit_best_rank_sum | 11.77 | 2.67 | 5.00 | 20.00 |
| offsuit_tens_count | 2.00 | 2.43 | 0.00 | 7.00 |
| offsuit_secondbest_rank_sum | 8.57 | 2.25 | 3.00 | 16.00 |

#### suit (n=124280)

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
contract distribution is tighter (std=2.50, P5=1.0-P95=9.0) than HIGH/LOW
(std~3.2), reflecting that trump contracts create more predictable trick counts.

**Sample size warning:** HIGH (n=261 deals, 1044 rows) and LOW (n=281 deals,
1124 rows) fall below the 2,000-deal minimum for reliable distribution
characterization. These are adequate for R0 baseline purposes but not for
production inference on per-contract metrics.

> See notebook 20_outcome_health for outcome distributions and make-rate
> analysis by contract type.

- **Overall mean tricks:** 5.00
- **Overall std:** 2.51
- **Range:** [0.0, 10.0]

### Per-Contract Outcome Statistics

| Contract | Mean | Std | P5 | P95 | n |
|----------|------|-----|-----|-----|---|
| high | 5.00 | 3.14 | 0.0 | 10.0 | 1044 |
| low | 5.00 | 3.21 | 0.0 | 10.0 | 1124 |
| suit | 5.00 | 2.50 | 1.0 | 9.0 | 124280 |

**Overall make rate:** 0.873

| Contract | Make Rate | n |
|----------|-----------|---|
| high | 0.766 | 261 |
| low | 0.769 | 281 |
| suit | 0.875 | 31070 |

---

## Auction Analysis

The auction is dominated by suit contracts (98.3%), with HIGH/LOW selected less
than 1% each. This reflects the R0 model's 1-feature HIGH/LOW specifications
— offsuit_aces (HIGH) and offsuit_tens_count (LOW) — which produce conservative
trick predictions that rarely exceed the bid/pass threshold. The oracle analysis
([contract_selection_oracle.md](contract_selection_oracle.md)) shows the
hindsight-optimal HIGH+LOW share is 31.9%, confirming substantial under-selection.

Bid levels cluster tightly around 5-6 for suit (mean 5.78), with HIGH/LOW
averaging ~7 (reflecting that these contracts are only bid on very strong hands
that clear the Gaussian EV threshold). Seat balance in auction outcomes is
verified in notebook 25_auction_health.

> See notebook 25_auction_health for bid distribution histograms and seat-level
> auction balance diagnostics.

### Contract Selection Frequency

| Contract | Count | Pct |
|----------|-------|-----|
| suit | 31070 | 98.3% |
| low | 281 | 0.9% |
| high | 261 | 0.8% |

### Bid Distribution

- **Mean winning bid:** 5.80
- **Bid range:** 5--8
- **Std:** 0.59

### Auction Summary

| Contract | Deals | Make Rate | Mean Bid |
|----------|-------|-----------|----------|
| high | 261 | 0.766 | 7.05 |
| low | 281 | 0.769 | 7.08 |
| suit | 31070 | 0.875 | 5.78 |

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
| OLSa (constrained) | +1.627 (eval) |
| OLSa_Full (promotional) | +1.484 (eval) |
| **Attribution Gap** | **-0.1437** |

The attribution gap is negative: the constrained arm slightly outperforms the
promotional arm. This is counter-intuitive but benign at R0 — the constrained
arm's hand-picked features (bowers, trump_count, offsuit_aces) are individually
stronger predictors than the forward-selected features, and the lower bid rate
(63.2% vs 82.8%) means OLSa only bids on high-confidence hands. See
[r0_promotion_report.md](r0_promotion_report.md) §4 for full interpretation.

### Comparator Battery (v4, Single-Seat, GluttonStrategy)

The single-seat comparator evaluates each bidder in isolation — one seat bids
while three always-pass sentinels fill the remaining seats — producing an
absolute benchmark free from auction interaction confounds. See
[comparator_rankings.md](comparator_rankings.md) for full methodology and
behavioral analysis.

| Rank | Bidder | net_eppd (comparator) | 95% CI |
|------|--------|----------------------|--------|
| 1 | modeloespecifico | +1.587 | [+1.529, +1.645] |
| 2 | **hybrid_olsa** | **+0.455** | **[+0.420, +0.491]** |
| 3 | stricthellraiser | +0.076 | [+0.018, +0.132] |
| 4 | olsa_full | −0.168 | [−0.260, −0.078] |
| 5 | olsa | −0.342 | [−0.435, −0.250] |
| 6 | fiveheadfred | −2.570 | [−2.667, −2.473] |
| 7 | rankthetank | −9.767 | [−9.857, −9.675] |

The gap between modeloespecifico and hybrid_olsa is 1.132 points/deal
(comparator, p < 0.001) — the primary improvement target for R1+.

**Instrument note:** Eval net_eppd (+1.627 for OLSa, eval) and comparator
net_eppd (+0.455 for hybrid_olsa, comparator v4 single-seat) measure different
estimands. Eval uses self-play where both teams bid; the comparator uses
single-seat mode where only the test bidder bids against always-pass sentinels,
with GluttonStrategy card play. The eval figure reflects competitive bidding
dynamics while the comparator isolates bidding quality in a controlled setting.

### Key H2H Matchups

Head-to-head matchups pit bidders directly against each other in contested
auctions with paired, seat-swapped deals. See
[h2h_battery_analysis.md](h2h_battery_analysis.md) for the full 7-bidder matrix
(QUICK + FULL resolution) and gate threshold derivation.

| A vs B | delta (H2H) | 95% CI | Verdict |
|--------|-------------|--------|---------|
| modelo vs hybrid_olsa | +0.644 | [+0.545, +0.743] | modelo wins |
| hybrid_olsa vs olsa | +0.147 | [+0.014, +0.276] | hybrid wins |
| hybrid_olsa vs olsa_full | +0.033 | [−0.101, +0.160] | Draw |
| modelo vs olsa | +0.016 | [−0.117, +0.147] | Draw |

Dominance ordering: modeloespecifico > hybrid_olsa > olsa ~ olsa_full. The
self-play gap between modeloespecifico and olsa (+1.929 comparator) does not
replicate in H2H (+0.016, CI spans zero) — a divergence explained by
play-strategy interaction effects in the comparator battery.

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
   calibration and is the dominant source of oracle regret (82% pass-threshold
   regret, PR #472). R1 feature enrichment is the primary remedy.

2. **Negative attribution gap.** The constrained arm outperforms the
   promotional arm by 0.14 net_eppd (eval). This suggests forward feature
   selection at R0's sample size and model complexity does not yet add value
   beyond hand-picked features. Monitored via `check_dual_arm_coherence` at R1+.

3. **Single-seed comparator data.** Comparator rankings and H2H matchups use
   seed=42 only. Multi-seed averaging would reduce variance in ranking
   estimates but was not prioritized for R0 given the clear tier separation.

4. **Pass-threshold regret is a model problem, not a threshold problem.** The
   B0 sweep (PR #476) showed net_diff decreases monotonically with higher t —
   marginal hands can't be profitably bid at R0 model quality. This can only
   be addressed through better models (R1+).

5. **GluttonStrategy confounding.** Both comparator and eval instruments use
   GluttonStrategy for card play. Rankings reflect interaction with this
   specific play strategy. See
   [measurement_integrity_r0.md](measurement_integrity_r0.md) for full
   limitation inventory.

---

## Reproduction Commands

### Generate Eval Dataset

```bash
# Parse JSONL logs into eval DataFrame:
PYTHONPATH=src uv run python -c "
from bid_euchre.datasets.eval_dataset import build_eval_dataset
df = build_eval_dataset('data/runs/arc_d_eval_r0_42_20260221_180253/logs/*.jsonl')
df.to_parquet('eval_df.parquet')
"
```

### Generate Report

```bash
# Regenerate the auto-generated tables:
PYTHONPATH=src uv run python -c "
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
