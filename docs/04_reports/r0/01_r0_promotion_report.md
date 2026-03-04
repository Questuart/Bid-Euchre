# R0 Promotion Report

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 (baseline)
**Decision:** PROMOTED
**Date:** 2026-02-22 (v1 decision); 2026-03-04 (v2 eval refresh)
**Methodology Review:** [20_measurement_integrity_r0.md](20_measurement_integrity_r0.md)

> **Naming convention:** Each model arm has two names — a **model name** used in
> self-play evaluation and a **strategy name** used in comparator/H2H batteries:
>
> | Model Name | Strategy Name | Arm | Artifact |
> |------------|---------------|-----|----------|
> | OLSa | hybrid_olsa | Constrained (attribution) | `hybrid_r0.json` |
> | OLSa_Full | hybrid_olsa_full | Promotional | `hybrid_r0_full.json` |
>
> Self-play sections use model names; comparator and H2H sections use strategy
> names. The "hybrid" prefix denotes the Gaussian EV wrapper + bid-level search;
> non-prefixed variants (olsa, olsa_full) use floor-based thresholds without search.

## Executive Summary

The R0 rung of Arc D's OLSa-Hybrid bidder was **PROMOTED** after passing all
Tier 1 artifact integrity checks and demonstrating positive net expected points
per deal across three independent evaluation seeds.

**Self-play evaluation** (seed 42, both arms):

| Metric | OLSa_Full (promotional) | OLSa (constrained) | Definition |
|--------|-------------------------|---------------------|------------|
| `net_eppd` | +1.932 | +1.953 | Net expected points per deal (bidder − opponent). **Differential.** |
| `eppd` | +5.795 | +5.815 | Expected points per deal (bidder only). **Absolute.** |
| `bid_rate` | 100.0% | 100.0% | Fraction of deals with an auction winner. v2 bid-level search bids every deal. |
| `make_rate` | 94.9% | 95.2% | Fraction of won auctions where declaring team makes contract. |
| `net_CVaR-5%` | −11.230 | −10.998 | Average of worst 5% of net point outcomes. **Differential tail risk.** Higher = less risky. |

**Comparator context** (single-seat vs GluttonStrategy, seed 42, both arms):

| Metric | hybrid_olsa_full (OLSa_Full) | hybrid_olsa (OLSa) | Definition |
|--------|------------------------------|---------------------|------------|
| `net_eppd` | +2.170 | +2.131 | Net expected points per deal. **Differential** vs always-pass sentinels. |
| `bid_rate` | 0.968 | 0.961 | Fraction of deals bid on. |
| `make_rate` | 1.000 | 1.000 | Fraction of bids that make contract. |
| Rank | 1 of 8 | 2 of 8 | Statistically tied (delta=+0.038, p=0.5457). |

Both arms rank 1-2 among 8 comparator bidders by net_eppd (v6 single-seat
comparator with GluttonStrategy, seed=42), statistically tied (p=0.5457) and
leading `modeloespecifico` (+1.604) by +0.5-0.6 points/deal (p < 0.001). The
v2 bid-level search transformed bidding behavior across both self-play and
comparator: self-play bid_rate rose from ~63-83% (v1) to 100% (v2), while
make_rate shifted from ~83-87% (v1) to ~95% (v2) as the model now bids on
every deal at the optimal level rather than passing marginal hands.

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
| `net_eppd` | +1.932 | +1.933 | +1.935 | 0.003 | Net expected points per deal (bidder − opponent). **Differential.** |
| `eppd` | +5.795 | +5.795 | +5.794 | 0.001 | Expected points per deal (bidder only). **Absolute.** |
| `bid_rate` | 1.000 | 1.000 | 1.000 | 0.000 | Fraction of deals with an auction winner. v2 bid-level search bids every deal. |
| `make_rate` | 0.949 | 0.949 | 0.949 | 0.001 | Fraction of won auctions where declaring team makes contract. |
| `net_CVaR-5%` | −11.230 | −11.208 | −11.213 | 0.022 | Average of worst 5% of net point outcomes. **Differential tail risk.** Higher = less risky. |

### OLSa (Attribution Arm) — self-play evaluation, 50,000 deals per seed

The OLSa constrained arm uses locked features: 3 for suit (bowers, trump_count,
offsuit_aces), 1 for high (offsuit_aces), 1 for low (offsuit_tens_count).

| Metric | Seed 42 | Seed 43 | Seed 44 | Range | Definition |
|--------|---------|---------|---------|-------|------------|
| `net_eppd` | +1.953 | +1.954 | +1.951 | 0.003 | Net expected points per deal (bidder − opponent). **Differential.** |
| `eppd` | +5.815 | +5.816 | +5.812 | 0.004 | Expected points per deal (bidder only). **Absolute.** |
| `bid_rate` | 1.000 | 1.000 | 1.000 | 0.000 | Fraction of deals with an auction winner. v2 bid-level search bids every deal. |
| `make_rate` | 0.952 | 0.952 | 0.951 | 0.001 | Fraction of won auctions where declaring team makes contract. |
| `net_CVaR-5%` | −10.998 | −10.894 | −11.044 | 0.150 | Average of worst 5% of net point outcomes. **Differential tail risk.** Higher = less risky. |

### Multi-Seed Stability

All metrics show tight cross-seed ranges (< 0.003 for net_eppd, 0.000 for
bid_rate, < 0.001 for make_rate), confirming that R0 evaluation is
reproducible and not sensitive to deal sampling. The v2 bid-level search
produces exceptionally stable results because every deal is bid on (100%
bid_rate), eliminating the pass/bid boundary as a source of cross-seed
variance.

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

**Gap = −0.0207** (OLSa_Full net_eppd − OLSa net_eppd at seed 42)

The attribution gap is negative but near zero: the constrained arm (OLSa)
slightly *outperforms* the promotional arm (OLSa_Full) on net_eppd despite
using fewer features. The gap narrowed dramatically from v1 (−0.144) to v2
(−0.021), consistent with the v2 bid-level search equalizing bid behavior
across both arms:

1. **Bid-level search eliminates the bid_rate confound.** In v1, the two arms
   had very different bid rates (OLSa 63.2% vs OLSa_Full 82.8%), meaning the
   gap reflected both feature quality *and* bid selectivity differences. In v2,
   both arms bid on 100% of deals at their respective optimal levels, isolating
   the gap to pure feature quality differences.

2. **Feature selection explains the residual inversion.** The constrained arm's
   3/1/1 features (bowers, trump_count, offsuit_aces for suit; offsuit_aces for
   high; offsuit_tens_count for low) were hand-picked as the strongest
   individual predictors from domain knowledge. The full arm's forward selection
   picked different features (hand_value, quick_tricks, low_card_count for suit;
   offsuit_non_ace_count + offsuit_best_rank_sum for high/low) that maximize
   R² but may include weaker marginal contributors.

3. **R0 context.** Both arms are R0-quality models with R² ≈ 0.24–0.29. At
   this early stage, the difference between hand-picked and forward-selected
   features is within noise. The near-zero gap (−0.021) confirms that feature
   choice is a minor factor at R0. The gap is expected to resolve as model
   complexity increases in later rungs.

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
| 1 | **hybrid_olsa_full** (OLSa_Full) | **+2.170** | **[+2.081, +2.257]** |
| 2 | **hybrid_olsa** (OLSa) | **+2.131** | **[+2.042, +2.216]** |
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
| Evaluator git SHA (v1) | b194908ca8b0cf265d78c4661716e56343796db3 |
| Evaluator git SHA (v2) | 2b674e85f9ffd780748830a517c7fafd7388bb4a |
| Promotion timestamp (v1) | 2026-02-22T02:13:32Z |
| V2 eval refresh timestamp | 2026-03-04T04:38:04Z |
| Training source run | canonical_bidless_dataset_glutton_42_20260221_175752 |
| n_deals per eval seed | 50,000 |
| Eval policy | bid_level_search: true (v2) |
| OLSa eval runs | arc_d_eval_r0_42_20260303_201729, arc_d_eval_r0_43_20260303_201730, arc_d_eval_r0_44_20260303_201731 |
| OLSa_Full eval runs | arc_d_eval_r0_full_42_20260303_201732, arc_d_eval_r0_full_43_20260303_201734, arc_d_eval_r0_full_44_20260303_201735 |
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
