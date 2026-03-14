# R1.5.3 Phase 2: GBT FULL Validation

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5.3 (model-architecture exploration)
**Date:** 2026-03-13
**Predecessor:** [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) (GBT QUICK — PROTOTYPE VALIDATED)
**Plan:** `plans/sessions/2026-03-12_r1-5-3-forward-plan-v2.md`, Phase 2

## 1. Goal

Validate the GBT action-value bidder at FULL scale (50,000 deals) with 3
independent seeds (42, 123, 456) to confirm QUICK-scale results and satisfy
promotion gate requirements.

## 2. Design

### 2.1 Battery Configuration

| Parameter | Value |
|-----------|-------|
| Mode | FULL (50,000 deals per matchup) |
| Seeds | 3 independent (42, 123, 456) |
| Roster | GBT AV v1, OLS AV v1, Hybrid R0 |
| Matchups | 9 per seed (3 self-play + 6 cross) |
| Play strategy | GluttonStrategy (all teams) |
| Paired deals | Yes (same deals across matchups within seed) |
| Total hands | 1,350,000 (450K per seed) |

### 2.2 Artifact Provenance

| Bidder | Artifact | Frozen | Training | R² (suit) |
|--------|----------|--------|----------|-----------|
| GBT AV v1 | `data/runs/phase1a_cell_c_gbt_n1/action_value_gbt.json` | No | QUICK (2,500 deals), seed 42, N=1 labels | 0.594 |
| Hybrid R0 | `data/artifacts/arc_d/r0/hybrid_r0_full.json` | Yes | FULL, R0 canonical | N/A (OLSa) |

**Note:** The OLS AV v1 artifact (`action_value_full.json`) loaded with
`target: "tricks_won"` and low R² (0.18/0.15/0.13), indicating a stale or
wrong artifact. OLS comparisons in this battery are unreliable and excluded
from analysis. The GBT vs Hybrid R0 comparison is unaffected.

### 2.3 Success Gates

| Gate | Criterion | Threshold |
|------|-----------|-----------|
| G1 | Pooled CI_low vs R0 | > 0.180 (delta floor from R0 calibration) |
| G2 | Suit delta vs R0 | > 0.0 (regression resolved) |
| G3 | No seed reversals | All 3 seeds show positive pooled delta |

## 3. Results

### 3.1 GBT vs Hybrid R0 — Per-Seed Directional Deltas

**GBT as team0:**

| Seed | Suit | High | Low | Pooled | CI |
|------|------|------|-----|--------|-----|
| 42 | +0.804 | +0.381 | +0.028 | **+0.577** | [+0.532, +0.623] |
| 123 | +0.800 | +0.259 | -0.045 | **+0.549** | [+0.503, +0.595] |
| 456 | +0.828 | +0.286 | -0.123 | **+0.551** | [+0.505, +0.597] |

**Hybrid R0 as team0 (GBT team1):**

| Seed | Suit | High | Low | Pooled | CI |
|------|------|------|-----|--------|-----|
| 42 | -0.882 | -0.427 | +0.081 | **-0.613** | [-0.659, -0.568] |
| 123 | -0.837 | -0.257 | +0.071 | **-0.564** | [-0.610, -0.518] |
| 456 | -0.809 | -0.386 | +0.056 | **-0.565** | [-0.611, -0.519] |

### 3.2 Symmetrized Deltas (Primary Evidence)

| Contract | Seed 42 | Seed 123 | Seed 456 | 3-Seed Mean | Significant? |
|----------|---------|----------|----------|-------------|--------------|
| **Suit** | **+0.843** | **+0.818** | **+0.819** | **+0.827** | **Yes** — all CIs exclude 0 |
| **High** | **+0.404** | **+0.258** | **+0.336** | **+0.333** | **Yes** — all CIs exclude 0 |
| **Low** | -0.027 | -0.008 | -0.089 | -0.041 | No — all CIs span 0 |
| **Pooled** | **+0.595** | **+0.557** | **+0.558** | **+0.570** | **Yes** — all CIs exclude 0 |

### 3.3 Cross-Seed Stability

| Metric | Range | CV (%) | Assessment |
|--------|-------|--------|------------|
| Pooled delta | 0.557–0.595 | 3.7% | Excellent stability |
| Suit delta | 0.818–0.843 | 1.6% | Excellent stability |
| High delta | 0.258–0.404 | 22% | Moderate variance (smaller n) |
| Low delta | -0.089 to -0.008 | — | Near zero, consistently |

### 3.4 Gate Results

| Gate | Criterion | Result | Status |
|------|-----------|--------|--------|
| G1 | Pooled CI_low > 0.180 | All 3 seeds: CI_low > +0.50 | **PASS** |
| G2 | Suit delta > 0 | All 3 seeds: +0.818 to +0.843 | **PASS** |
| G3 | No seed reversals | 3/3 positive (+0.557, +0.595, +0.558) | **PASS** |

**All gates PASS.**

## 4. QUICK→FULL Comparison

| Metric | QUICK (2,500) | FULL (3-seed mean) | Shrinkage |
|--------|---------------|-------------------|-----------|
| Pooled | +1.067 | +0.570 | **47%** |
| Suit | +1.110 | +0.827 | 25% |
| High | +1.467 | +0.333 | 77% |
| Low | +0.736 | -0.041 | ~100% |

### 4.1 Shrinkage Analysis

The 47% pooled QUICK→FULL shrinkage is substantially larger than the 8% seen
with OLS AV v1 in R1.5. Three factors contribute:

1. **QUICK-trained model at FULL scale.** GBT was trained on 2,500 deals but
   evaluated on 50,000. The model encounters deal distributions underrepresented
   in training data. OLS AV v1's shrinkage was smaller because linear models
   generalize more smoothly (at the cost of missing non-linear structure).

2. **High-contract sample variance.** High contracts comprise only ~12% of
   hands. At QUICK scale (n≈300 high hands), GBT's advantage was overstated.
   At FULL (n≈6,000), the more precise estimate is +0.333.

3. **Low-contract parity is real.** The QUICK result (+0.736) appears to be
   noise. At FULL scale, GBT and Hybrid R0 converge to near-identical
   performance on low contracts — the simplest scoring structure (no trump,
   10 high) is well-served by both approaches.

**Despite the shrinkage, the promotion case is strong:** Pooled CI_low (+0.50+)
is 2.8× the delta floor (0.180), and the suit regression is decisively
resolved (+0.827).

## 5. Behavioral Profile (FULL Scale)

### 5.1 Self-Play Metrics

| Metric | GBT AV v1 | Hybrid R0 |
|--------|-----------|-----------|
| Self-play eppd | 4.16 | 4.89 |
| Bid rate | ~50% | ~50% |
| Make rate | 84.6% | 96.7% |
| CVaR₅ | -6.84 | -0.74 |

### 5.2 Cross-Matchup Behavior (GBT vs Hybrid R0)

| Metric | GBT (team0) | Hybrid R0 (team1) |
|--------|-------------|-------------------|
| Bid rate | ~68% | ~32% |
| Make rate | ~90% | ~95% |
| Win rate (GBT) | ~61% | — |

GBT bids more aggressively than Hybrid R0 in head-to-head (68% vs 32%) while
maintaining ~90% make rate. The selective bidding strategy discovered at QUICK
scale persists at FULL.

### 5.3 Variance–Return Tradeoff

GBT's higher tail risk (CVaR₅ -6.84 vs R0's -0.74) persists at FULL scale.
This reflects the aggressive bidding strategy: GBT accepts higher variance in
exchange for +0.570 expected-value advantage. The tradeoff is favorable in
expected-value terms but may warrant risk treatment in future rungs.

## 6. Comparison to R1.5 v1 (OLS FULL)

| Metric | OLS AV v1 (FULL) | GBT AV v1 (FULL) | Delta |
|--------|-----------------|------------------|-------|
| Pooled vs R0 | +0.152 | +0.570 | +0.418 |
| Suit vs R0 | -0.142 | +0.827 | +0.969 |
| High vs R0 | +0.430 | +0.333 | -0.097 |
| Low vs R0 | +0.495 | -0.041 | -0.536 |
| CI_low (pooled) | +0.124 | +0.50+ | +0.38+ |

GBT's pooled advantage over OLS comes entirely from suit resolution (+0.969).
OLS actually outperforms GBT in high (+0.097) and low (+0.536) contracts. This
is consistent with the H15 finding: OLS captures no-trump structure well but
cannot model the bimodal suit target.

**Note:** The OLS numbers above are from the R1.5 v1 FULL battery (report 05),
not from this battery, due to the stale OLS artifact issue documented in §2.2.

## 7. Provenance

| Item | Value |
|------|-------|
| gate_status | ALL GATES PASS — promotable |
| Seeds | 42, 123, 456 |
| n_per | 50,000 per matchup |
| Total hands | 1,350,000 |
| Seed 42 run | `data/runs/arc_d_r0_h2h_battery_42_20260313_113526/` |
| Seed 123 run | `data/runs/arc_d_r0_h2h_battery_123_20260313_151604/` |
| Seed 456 run | `data/runs/arc_d_r0_h2h_battery_456_20260313_163624/` |
| GBT artifact | `data/runs/phase1a_cell_c_gbt_n1/action_value_gbt.json` |
| Hybrid R0 artifact | `data/artifacts/arc_d/r0/hybrid_r0_full.json` |
| Battery config | `data/runs/gbt_full_validation/h2h_battery_full_config.yaml` |
| Predecessor | [08_gbt_prototype_evaluation.md](08_gbt_prototype_evaluation.md) |
| analysis_base_sha | 078cecc |
