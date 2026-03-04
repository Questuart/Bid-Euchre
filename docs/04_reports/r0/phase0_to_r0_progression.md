# Phase 0 → R0 Progression Report

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R0
**Date:** 2026-03-01 (v1); 2026-03-03 (v2 context note)
**Purpose:** Post-hoc cross-phase comparison documenting the transition from bidless
baseline (Phase 0) to first bidding model (R0)

---

## Executive Summary

Phase 0 (forced random contracts, n=300,000 hands × 3 contracts = 1,200,000 rows)
and R0 (auction-selected contracts, n=31,612 deals = 126,448 rows) show the expected
divergence in contract selection and outcome distributions:

- **Contract mix shift:** Phase 0 forced ~33/33/33 suit/high/low → R0 auctions
  produce 98.3% suit / 0.8% high / 0.9% low, driven by R0's 1-feature HIGH/LOW
  models that rarely find profitable non-suit contracts.
- **Variance direction (suit, declaring-side):** Phase 0 std(tricks_won) = 1.72 →
  R0 declaring-side std = 1.60. The 7% reduction is directionally consistent with
  auction selection filtering weak hands, though the comparison is confounded by the
  forced-vs-selected contract asymmetry.
- **Mean stability:** mean(tricks_won) = 5.00 in both phases across all contract types,
  confirming simulation fairness (symmetric self-play).
- **R0 role asymmetry:** R0 declaring teams average 6.92 tricks (suit), reflecting
  the auction's selection of strong hands. The overall R0 suit std (2.50) is higher
  than Phase 0's (1.72) due to pooling across roles with different means — this is a
  Simpson's paradox artifact, not a real variance increase.

R0 is already PROMOTED. This report validates retroactively and establishes the
progression report pattern for future rung transitions.

---

## 1. Motivation

The project lacked any cross-phase comparison between Phase 0 (bidless baseline) and
R0 (first bidding model). Phase 0 established ground-truth outcome distributions
under forced contracts — every hand plays every contract regardless of suitability.
R0 introduced auction-selected contracts where the bidding model filters hands based
on predicted payoff.

The core hypothesis: auction selection should reduce declaring-side outcome variance
within contract types, because the bidder avoids playing weak hands. This report
tests that hypothesis with appropriate caveats about comparability.

**Prior work:**
- Phase 0 baseline: [phase0_bidless_20260207.md](../phase0/phase0_bidless_20260207.md)
- R0 rung report: [model_arc_r0.md](model_arc_r0.md)
- R0 promotion decision: [r0_promotion_report.md](r0_promotion_report.md)

---

## 2. Methodology

### Data Sources

| Source | Dataset | Hands | Rows | Contracts | Mode |
|--------|---------|-------|------|-----------|------|
| Phase 0 | canonical_bidless_dataset_glutton_42_20260221_175752 | 300,000 | 1,200,000 | Forced (suit × 4 trumps + high + low) | Symmetric self-play, no auction |
| R0 | arc_d_eval_r0_42_20260221_180253 | 31,612 | 126,448 | Auction-selected | Symmetric self-play with OLSa_Full R0 bidder |

**Phase 0 loader:** `join_features_outcomes()` from `src/bid_euchre/datasets/join.py`
(same loader used by oracle notebook `55_contract_selection_oracle.py`).

**R0 loader:** `build_eval_dataset()` from `src/bid_euchre/datasets/eval_dataset.py`
applied to the R0 evaluation JSONL log.

### Statistics

- **Primary metric:** std(tricks_won) per contract_type, stratified by role where applicable
- **Contract mix:** proportion of deals per contract_type
- **Role stratification:** R0 is split by declaring/defending team; Phase 0 has no
  roles (all hands play all contracts, no auction)

### Comparability Caveat

Phase 0 forces every hand into every contract regardless of hand strength. R0
self-selects via auction. The variance comparison is a hypothesis with confounds,
not a controlled experiment. Differences could reflect:

1. **Selection effects** — auction filters weak hands (expected direction: lower declaring variance)
2. **Model imperfections** — R0's 1-feature HIGH/LOW models rarely bid non-suit contracts
3. **Role asymmetry** — R0 has declaring/defending teams; Phase 0 is symmetric
4. **Sample size imbalance** — Phase 0 has 800,000 suit rows vs R0's 124,280

---

## 3. Results

### Table 1: Per-Contract Tricks Won Statistics

| Contract | Phase | Mean | Std | P5 | P25 | P50 | P75 | P95 | n |
|----------|-------|------|-----|-----|-----|-----|-----|-----|---|
| suit | Phase 0 | 5.00 | 1.72 | 2.00 | 4.00 | 5.00 | 6.00 | 8.00 | 800,000 |
| suit | R0 (all) | 5.00 | 2.50 | 1.00 | 3.00 | 5.00 | 7.00 | 9.00 | 124,280 |
| suit | R0 declaring | 6.92 | 1.60 | 4.00 | 6.00 | 7.00 | 8.00 | 9.00 | 62,140 |
| suit | R0 defending | 3.08 | 1.60 | 1.00 | 2.00 | 3.00 | 4.00 | 6.00 | 62,140 |
| high | Phase 0 | 5.00 | 1.87 | 2.00 | 4.00 | 5.00 | 6.00 | 8.00 | 200,000 |
| high | R0 (all) | 5.00 | 3.14 | 0.00 | 2.00 | 5.00 | 8.00 | 10.00 | 1,044 |
| high | R0 declaring | 7.82 | 1.38 | — | — | — | — | — | 522 |
| high | R0 defending | 2.18 | 1.38 | — | — | — | — | — | 522 |
| low | Phase 0 | 5.00 | 1.88 | 2.00 | 4.00 | 5.00 | 6.00 | 8.00 | 200,000 |
| low | R0 (all) | 5.00 | 3.21 | 0.00 | 2.00 | 5.00 | 8.00 | 10.00 | 1,124 |
| low | R0 declaring | 7.88 | 1.42 | — | — | — | — | — | 562 |
| low | R0 defending | 2.12 | 1.42 | — | — | — | — | — | 562 |

Percentiles omitted for R0 high/low declaring/defending due to small samples (n<600).

### Table 2: Contract Mix Comparison

| Contract | Phase 0 | R0 |
|----------|---------|-----|
| suit | 66.7% (forced: 4 trumps × 2 = 8 of 12 slots) | 98.3% (121,280 / 126,448) |
| high | 16.7% (1 of 6 contract types) | 0.8% (1,044 / 126,448) |
| low | 16.7% (1 of 6 contract types) | 0.9% (1,124 / 126,448) |

Note: Phase 0 percentages reflect the bidless dataset structure where each hand
plays each contract type. Suit has 4 trump variants per hand while high and low have
1 each, giving a natural 4:1:1 ratio (66.7/16.7/16.7).

### Table 3: Variance Ratio (R0 Declaring / Phase 0)

| Contract | Phase 0 Std | R0 Declaring Std | Ratio | Direction |
|----------|-------------|-------------------|-------|-----------|
| suit | 1.72 | 1.60 | 0.93 | Lower (expected) |
| high | 1.87 | 1.38 | 0.74 | Lower (expected) |
| low | 1.88 | 1.42 | 0.75 | Lower (expected) |

All three contract types show reduced declaring-side variance in R0 compared to the
Phase 0 forced-contract baseline.

**Chart references:**
- Phase 0 outcome distributions: Phase 0 report §5b
- R0 outcome health: R0 notebook `20_outcome_health` S2

---

## 4. Interpretation

### Variance Direction Check: Confirmed

The directional hypothesis holds: R0 declaring-side std(tricks_won) is lower than
Phase 0 std in all three contract types. The suit contract ratio (0.93) represents a
modest 7% reduction; high and low show larger reductions (26% and 25%) but with
much smaller R0 samples (n~500 each).

### Why Overall R0 Variance Is Higher

The R0 overall (all-seats) suit std of 2.50 exceeds Phase 0's 1.72. This is expected
and is *not* evidence against the hypothesis. The inflation comes from pooling two
subpopulations with different means:

- R0 declaring: mean=6.92, std=1.60
- R0 defending: mean=3.08, std=1.60

Pooling these into a single distribution produces a bimodal-like spread with inflated
standard deviation (Simpson's paradox in variance). Phase 0 has no declaring/defending
distinction — all seats are symmetric.

### Contract Mix Concentration

R0 produces 98.3% suit contracts because the R0 model uses only 1 feature each for
HIGH (offsuit_aces) and LOW (offsuit_tens_count). These sparse specifications rarely
produce positive expected value, so the bidder almost always selects suit contracts
where the 3-feature model provides better discrimination. This is a known R0 limitation
documented in the [model specification](model_arc_r0.md) and motivating R1's
HIGH/LOW feature enrichment.

### Confound Analysis

1. **Forced vs selected contracts:** Phase 0 includes all hands regardless of strength;
   R0's auction self-selects. The declaring-side variance reduction could reflect
   genuine filtering (weak hands pass) or mean-shift mechanics (declaring teams always
   have stronger hands by construction).
2. **Symmetric vs asymmetric play:** Phase 0 uses GluttonStrategy for all 4 seats
   (pure play, no bidding). R0 uses OLSa_Full R0 for all 4 seats (self-play with
   auction). The introduction of an auction changes both hand selection and play dynamics.
3. **Sample size:** R0 high/low have <600 declaring observations each. The variance
   ratios for these contracts are suggestive but not statistically robust.

### Mean Stability

mean(tricks_won) = 5.00 in both phases across all contract types and roles. This
confirms the simulation's zero-sum property: in self-play, average tricks per seat
must equal 10/4 = 2.5, and per team must equal 10/2 = 5.0. This is a structural
property, not a coincidence.

---

## 5. Impact & Decisions

- **R0 is PROMOTED** — already decided via the [R0 promotion gate](r0_promotion_report.md).
  This report validates retroactively and does not change any decision.
- **Variance results inform R1 priorities:** The extreme contract mix concentration
  (98.3% suit) and sparse HIGH/LOW models confirm that HIGH/LOW feature enrichment
  is the correct R1 priority (see P1 in R1 follow-ups).
- **V2 bid-level search context:** The v2 policy (bid-level search) dramatically
  changed R0's bidding behavior in the comparator instrument: bid_rate rose from
  19.7% to 96.1%, net_eppd from +0.455 to +2.131, and hybrid_olsa now leads
  modeloespecifico by +0.527 (v6 comparator). The eval dataset statistics in this
  report reflect the pre-v2 self-play runs and remain valid for the Phase 0 to R0
  progression comparison. The v2 comparator numbers characterize R0's competitive
  position but do not change the self-play outcome distributions analyzed here.
- **Progression report pattern:** This report establishes the template for future
  rung-to-rung comparisons. Starting at R1, a `progression_report` is a required
  bundle artifact enforced by the rung bundle validator.

---

## 6. Arc Context

```
Phase 0 (bidless baseline)
  ↓  [this report]
R0 (first bidding model, OLSa-Hybrid with 3/1/1 features)
  ↓  R0 v2: bid-level search adopted, lambda=0.0 retained, normalizer deferred
  ↓  [R1 follow-ups: HIGH/LOW enrichment, 2×2 factorial design]
R1 (enriched features, auction-trained data)
  ↓
R2+ (context features, risk adjustment)
```

Phase 0 provides the unconditional baseline — what outcomes look like when every hand
plays every contract. R0 introduces selection via auction, reducing declaring-side
variance and concentrating contracts. The v2 canonical update added bid-level search,
which dramatically improved R0's comparator ranking (net_eppd +0.455 to +2.131) without
changing the underlying model. R1 will address the HIGH/LOW feature gap and train on
auction-generated data for the first time.

---

## 7. Provenance

| Field | Value |
|-------|-------|
| gate_status | N/A (post-hoc retroactive report, not a gate input) |
| Phase 0 dataset | `data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless.parquet` + `bidless_outcomes.parquet` |
| R0 eval run | `data/runs/arc_d_eval_r0_42_20260221_180253/logs/arc_d_eval_r0_42_20260221_180253_hybrid_olsa_r0.jsonl` |
| Phase 0 seed | 42 |
| R0 seed | 42 |
| Phase 0 sample | 300,000 hands × 4 seats = 1,200,000 rows |
| R0 sample | 31,612 deals × 4 seats = 126,448 rows |
| R0 promotion decision | PROMOTED (see r0_promotion_report.md) |
| V2 comparator | v6 (8 bidders, hybrid_olsa net_eppd +2.131) |

---

## 8. Reproduction

### Phase 0 Statistics

```bash
PYTHONPATH=src uv run python -c "
from bid_euchre.datasets.join import join_features_outcomes
df = join_features_outcomes(
    'data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless.parquet',
    'data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless_outcomes.parquet',
)
print(df.groupby('contract_type')['tricks_won'].agg(['mean','std','count']))
for ct in ['suit', 'high', 'low']:
    sub = df[df['contract_type'] == ct]['tricks_won']
    print(f'{ct}: P5={sub.quantile(0.05):.1f}, P25={sub.quantile(0.25):.1f}, '
          f'P75={sub.quantile(0.75):.1f}, P95={sub.quantile(0.95):.1f}')
"
```

### R0 Statistics

```bash
PYTHONPATH=src uv run python -c "
from bid_euchre.datasets.eval_dataset import build_eval_dataset
df = build_eval_dataset(
    'data/runs/arc_d_eval_r0_42_20260221_180253/logs/'
    'arc_d_eval_r0_42_20260221_180253_hybrid_olsa_r0.jsonl'
)
print(df.groupby('contract_type')['tricks_won'].agg(['mean','std','count']))
for ct in ['suit', 'high', 'low']:
    for role in [True, False]:
        sub = df[(df['is_declaring_team'] == role) & (df['contract_type'] == ct)]
        label = 'declaring' if role else 'defending'
        if len(sub) > 0:
            print(f'{ct} {label}: mean={sub[\"tricks_won\"].mean():.3f}, '
                  f'std={sub[\"tricks_won\"].std():.3f}, n={len(sub)}')
"
```
