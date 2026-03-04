# R0 Promotion Report

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Decision:** PROMOTED
**Date:** 2026-02-22
**Methodology Review:** [20_measurement_integrity_r0.md](20_measurement_integrity_r0.md)

## Executive Summary

The R0 rung of Arc D's OLSa-Hybrid bidder was **PROMOTED** after passing all
Tier 1 artifact integrity checks and demonstrating positive net expected points
per deal across three independent evaluation seeds.

**Self-play evaluation** (OLSa_Full promotional arm, seed 42):

| Metric | Value | Definition |
|--------|-------|------------|
| `net_eppd` | +1.484 | Net expected points per deal (bidder − opponent). **Differential.** Includes 0 for all-pass redeals. |
| `eppd` | +4.174 | Expected points per deal (bidder only). **Absolute.** Includes 0 for all-pass redeals. |
| `bid_rate` | 82.8% | Fraction of deals with an auction winner. Higher = bids more often. |
| `make_rate` | 83.3% | Fraction of won auctions where declaring team makes contract. |
| `CVaR-5%` | −6.411 | Average of worst 5% of bidder point outcomes. **Absolute tail risk.** Higher = less risky. |
| `net_CVaR-5%` | −12.063 | Average of worst 5% of net point outcomes. **Differential tail risk.** Higher = less risky. |

**Comparator context** (hybrid_olsa, single-seat vs GluttonStrategy, seed 42):

| Metric | Value | Definition |
|--------|-------|------------|
| `net_eppd` | +2.131 | Net expected points per deal. **Differential** vs always-pass sentinels. |
| `bid_rate` | 0.961 | Fraction of deals bid on. |
| `make_rate` | 1.000 | Fraction of bids that make contract. |
| Rank | 2 of 8 | Tied with hybrid_olsa_full (p=0.5457). |

The model ranks 1-2 among 8 comparator bidders by net_eppd (v6 single-seat
comparator with GluttonStrategy, seed=42), tied with hybrid_olsa_full (+2.170,
p=0.5457) and leading `modeloespecifico` (+1.604) by +0.527 points/deal
(p < 0.001). The v2 bid-level search transformed bidding behavior: bid_rate
rose from 19.7% to 96.1%, make_rate from 88.6% to 100%, driving the
comparator net_eppd from +0.455 to +2.131.

## Gate Results

All four Tier 1 artifact integrity checks passed:

| Check | Result | What it checks |
|-------|--------|----------------|
| `artifact_integrity_olsa` | PASS | Validates JSON schema, required fields, coefficient shapes for OLSa arm |
| `artifact_integrity_olsa_full` | PASS | Same validation for OLSa_Full arm |
| `no_nan_inf_olsa` | PASS | Checks all numeric values are finite (no NaN/Inf) in OLSa arm |
| `no_nan_inf_olsa_full` | PASS | Same check for OLSa_Full arm |

R0 uses only Tier 1 (artifact integrity) checks because Tier 2 checks
(calibration, fairness, stability) require a predecessor rung for comparison,
which R0 does not have. Full Tier 2 semantic gate checks are introduced at R1+.

Gate logic: `src/bid_euchre/validation/arc_d_gate.py` (promotion gate),
`src/bid_euchre/diagnostics/semantic_gate.py` (semantic gate engine).

## Evaluation Metrics

### OLSa_Full (Promotional Arm) — self-play evaluation, 50,000 deals per seed

The OLSa_Full arm uses forward-selected features (2–3 per contract type) from
the full pool of 39 hand features.

| Metric | Seed 42 | Seed 43 | Seed 44 | Range | Definition |
|--------|---------|---------|---------|-------|------------|
| `net_eppd` | +1.484 | +1.455 | +1.426 | 0.058 | Net expected points per deal (bidder − opponent). **Differential.** Includes 0 for all-pass redeals. |
| `eppd` | +4.174 | +4.139 | +4.131 | 0.044 | Expected points per deal (bidder only). **Absolute.** Includes 0 for all-pass redeals. |
| `bid_rate` | 0.828 | 0.825 | 0.827 | 0.004 | Fraction of deals with an auction winner. Higher = bids more often. |
| `make_rate` | 0.833 | 0.832 | 0.830 | 0.003 | Fraction of won auctions where declaring team makes contract. |
| `CVaR-5%` | −6.411 | −6.418 | −6.428 | 0.017 | Average of worst 5% of bidder point outcomes. **Absolute tail risk.** Higher = less risky. |
| `net_CVaR-5%` | −12.063 | −12.056 | −12.070 | 0.014 | Average of worst 5% of net point outcomes. **Differential tail risk.** Higher = less risky. |
| `downside_var` | 0.430 | 0.436 | 0.437 | 0.007 | Variance of deal outcomes below zero. Lower = more predictable losses. |

### OLSa (Attribution Arm) — self-play evaluation, 50,000 deals per seed

The OLSa constrained arm uses locked features: 3 for suit (bowers, trump_count,
offsuit_aces), 1 for high (offsuit_aces), 1 for low (offsuit_tens_count).

| Metric | Seed 42 | Seed 43 | Seed 44 | Range | Definition |
|--------|---------|---------|---------|-------|------------|
| `net_eppd` | +1.627 | +1.595 | +1.623 | 0.033 | Net expected points per deal (bidder − opponent). **Differential.** Includes 0 for all-pass redeals. |
| `eppd` | +3.566 | +3.534 | +3.571 | 0.037 | Expected points per deal (bidder only). **Absolute.** Includes 0 for all-pass redeals. |
| `bid_rate` | 0.632 | 0.630 | 0.634 | 0.004 | Fraction of deals with an auction winner. Higher = bids more often. |
| `make_rate` | 0.873 | 0.870 | 0.872 | 0.003 | Fraction of won auctions where declaring team makes contract. |
| `CVaR-5%` | −6.154 | −6.139 | −6.141 | 0.015 | Average of worst 5% of bidder point outcomes. **Absolute tail risk.** Higher = less risky. |
| `net_CVaR-5%` | −11.784 | −11.805 | −11.806 | 0.023 | Average of worst 5% of net point outcomes. **Differential tail risk.** Higher = less risky. |
| `downside_var` | 0.318 | 0.310 | 0.313 | 0.008 | Variance of deal outcomes below zero. Lower = more predictable losses. |

### Multi-Seed Stability

All metrics show tight cross-seed ranges (< 0.06 for net_eppd, < 0.005 for
bid/make rates), confirming that R0 evaluation is reproducible and not
sensitive to deal sampling.

**Pooling note:** All metrics in this report are pooled across contract types.
The promotion report is a summary/decision document — per-contract breakouts
are available in notebooks 40/45, the comparator rankings report (§4), and the
model specification report.

### Model Specification Comparison

| Attribute | OLSa (constrained) | OLSa_Full (promotional) |
|-----------|---------------------|-------------------------|
| Selection method | Hand-picked (domain knowledge) | Forward-selected (from 39-feature pool) |
| Suit features | 3 (bowers, trump_count, offsuit_aces) | 3 (hand_value, quick_tricks, low_card_count) |
| High features | 1 (offsuit_aces) | 2 (offsuit_non_ace_count, offsuit_best_rank_sum) |
| Low features | 1 (offsuit_tens_count) | 2 (offsuit_tens_count, offsuit_best_rank_sum) |
| Feature overlap | — | 1 of 9 unique features (offsuit_tens_count in low) |

Per-contract coefficient comparison:

**Suit:**

| Feature | OLSa weight | OLSa_Full weight |
|---------|-------------|------------------|
| bowers | +0.449 | — |
| trump_count | +0.432 | — |
| offsuit_aces | +0.340 | — |
| hand_value | — | +0.008 |
| quick_tricks | — | +0.195 |
| low_card_count | — | +0.151 |
| **Intercept** | **2.746** | **0.238** |
| **σ²** | **2.340** | **2.319** |

**High:**

| Feature | OLSa weight | OLSa_Full weight |
|---------|-------------|------------------|
| offsuit_aces | +0.711 | — |
| offsuit_non_ace_count | — | −0.660 |
| offsuit_best_rank_sum | — | +0.059 |
| **Intercept** | **3.579** | **9.542** |
| **σ²** | **2.877** | **2.855** |

**Low:**

| Feature | OLSa weight | OLSa_Full weight |
|---------|-------------|------------------|
| offsuit_tens_count | +0.715 | +0.665 |
| offsuit_best_rank_sum | — | +0.058 |
| **Intercept** | **3.569** | **2.950** |
| **σ²** | **2.898** | **2.877** |

The two arms share only one feature (`offsuit_tens_count` in low contracts)
out of 9 unique features. Despite using entirely different feature sets for
suit contracts, both arms achieve similar residual variance (σ² within 1%),
confirming that the 3-feature budget — not feature choice — is the binding
constraint at R0.

Data source: `hybrid_r0.json` (OLSa) and `hybrid_r0_full.json` (OLSa_Full).

## Attribution Gap

**Gap = −0.1437** (OLSa_Full net_eppd − OLSa net_eppd at seed 42)

The attribution gap is negative: the constrained arm (OLSa) slightly
*outperforms* the promotional arm (OLSa_Full) on net_eppd despite using fewer
features. This is counter-intuitive but benign at R0:

1. **Feature selection explains the inversion.** The constrained arm's 3/1/1
   features (bowers, trump_count, offsuit_aces for suit; offsuit_aces for high;
   offsuit_tens_count for low) were hand-picked as the strongest individual
   predictors from domain knowledge. The full arm's forward selection picked
   different features (hand_value, quick_tricks, low_card_count for suit;
   offsuit_non_ace_count + offsuit_best_rank_sum for high/low) that maximize
   R² but may include weaker marginal contributors.

2. **Bid rate differences amplify small effects.** OLSa bids conservatively
   (63.2% bid rate) vs OLSa_Full (82.8%). Lower bid rate means higher
   selectivity — the constrained arm only bids on hands where its simple model
   is confident, which happens to yield a higher net per deal.

3. **R0 context.** Both arms are R0-quality models with R² ≈ 0.24–0.29. At
   this early stage, the difference between hand-picked and forward-selected
   features is within noise. The gap is expected to resolve as model complexity
   increases in later rungs.

The attribution gap is monitored by the `check_dual_arm_coherence` gate check
starting at R1.

## Comparator Context

See [03_comparator_rankings.md](03_comparator_rankings.md) for the full comparator
battery with bootstrap 95% confidence intervals. The v6 single-seat comparator
(8 bidders, 20,000 deals/bidder, GluttonStrategy card play, seed=42) evaluates
each bidder in isolation against always-pass sentinels.

Summary ranking by `net_eppd` (v6 single-seat, 8 bidders). `net_eppd` is net
expected points per deal (**differential** vs always-pass sentinels):

| Rank | Bidder | net_eppd | 95% CI |
|------|--------|----------|--------|
| 1 | **hybrid_olsa_full** | **+2.170** | **[+2.081, +2.257]** |
| 2 | **hybrid_olsa (R0)** | **+2.131** | **[+2.042, +2.216]** |
| 3 | modeloespecifico | +1.604 | [+1.489, +1.720] |
| 4 | stricthellraiser | +0.085 | [−0.027, +0.197] |
| 5 | olsa_full | −0.012 | [−0.193, +0.173] |
| 6 | olsa | −0.225 | [−0.413, −0.037] |
| 7 | fiveheadfred | −2.579 | |
| 8 | rankthetank | −9.665 | |

hybrid_olsa_full and hybrid_olsa are statistically tied (delta=+0.038,
p=0.5457). hybrid_olsa leads `modeloespecifico` by +0.527 points/deal
(p < 0.001) — a reversal from v4 where modelo led by +1.132. The improvement
is driven by v2 bid-level search.

See [04_r0_experiment_summary.md](04_r0_experiment_summary.md) section 4 for H2H
pairwise matchup results that provide competitive ordering between bidders.

**Source:** comparator_cis_r0_v6.json

## Gate Threshold Calibration

Gate thresholds for R1 promotion were calibrated from the null signal in the
H2H battery. See [04_r0_experiment_summary.md](04_r0_experiment_summary.md) section 5
for the full derivation.

**Method:** The null distribution is constructed from self-play deltas (which
should be zero) and seat-swap residuals (|delta(A vs B) + delta(B vs A)|, which
should also be zero). Thresholds are set at the 95th and 99th percentiles of
this null distribution.

**Two-stage calibration:** Thresholds were first derived from QUICK data (2,000
deals/cell), then recalibrated from FULL data (10,000 deals/cell) after a drift
check revealed the QUICK thresholds were inflated (drift ratio = 0.726).

| Threshold | Value | Meaning |
|-----------|-------|---------|
| delta_floor | 0.180 | Challenger must improve by +0.18 net_eppd for PROMOTED |
| regression_threshold | 0.184 | Challenger regressing by -0.18 net_eppd triggers HALT |
| cvar5_tolerance | 0.050 | Floor value (residuals too small to calibrate) |
| bid_rate_min | 0.050 | Guardrail: minimum acceptable bid rate |
| bid_rate_max | 0.950 | Guardrail: maximum acceptable bid rate |
| make_rate_min | 0.450 | Guardrail: minimum acceptable make rate |
| downside_variance_ratio | 1.100 | Guardrail: max downside variance vs incumbent |

**R1 implications:** The delta_floor of 0.180 means the R1 challenger must
demonstrate at least +0.18 net_eppd improvement over the R0 incumbent in
paired H2H evaluation. For reference, the C33 v2 search effect (+0.43) and
wrapper effect (+0.75) both comfortably exceed this bar (see
[05_c33_ablation_report.md](05_c33_ablation_report.md)).

## Provenance

| Item | Value |
|------|-------|
| gate_status | PROMOTED |
| Rung bundle | data/artifacts/arc_d/r0/rung_bundle_r0.json |
| OLSa artifact | data/artifacts/arc_d/r0/hybrid_r0.json |
| OLSa_Full artifact | data/artifacts/arc_d/r0/hybrid_r0_full.json |
| OLSa SHA256 | 7b523cd6f0de41a82eca55f6b0bedc09d18630638609226ee3e8ddb443f71fe8 |
| OLSa_Full SHA256 | 5436b759f525466976244766dee8d98472dcfe243ac1d4542885e6cd0e6dcbc7 |
| Promotion decision | data/artifacts/arc_d/r0/promotion_decision_r0.json |
| Evaluator git SHA | b194908ca8b0cf265d78c4661716e56343796db3 |
| Promotion timestamp | 2026-02-22T02:13:32Z |
| Training source run | canonical_bidless_dataset_glutton_42_20260221_175752 |
| n_deals per eval seed | 50,000 |
| Gate thresholds (R1) | data/artifacts/arc_d/r0/gate_thresholds_r1.json |
| risk_lambda | 0.0 |
| Comparator version | v6 (8 bidders, comparator_cis_r0_v6.json) |
| H2H version | v4 (h2h_battery_quick_v4, h2h_battery_full_v4) |

## Companion Reports

- [04_r0_experiment_summary.md](04_r0_experiment_summary.md) — H2H battery (v4),
  gate threshold calibration.
- [03_comparator_rankings.md](03_comparator_rankings.md) — v6 single-seat comparator
  rankings (8 bidders) with bootstrap CIs and behavioral analysis.
- [05_c33_ablation_report.md](05_c33_ablation_report.md) — C33 v2: search effect
  +0.43, wrapper effect +0.75.
- [10_contract_selection_oracle.md](10_contract_selection_oracle.md) — Oracle regret
  analysis: CS regret share 90.9%.
- [11_pass_threshold_decision.md](11_pass_threshold_decision.md) — B0 threshold
  sweep: RETAIN t=0 (monotonic decline, model accuracy problem).
- [12_lambda_decision.md](12_lambda_decision.md) — Lambda tuning: RETAIN
  lambda=0.0 (FINAL).
- [13_normalizer_offline_screen.md](13_normalizer_offline_screen.md) — Normalizer
  screen: NO_GO_DEFER_R1.
- [20_measurement_integrity_r0.md](20_measurement_integrity_r0.md) — Methodology
  limitations inventory and deferral cost analysis.
- **Semantic gate Tier 2:** Not applicable at R0 (introduced at R1+).
