# R1.5.3 Step 0: Suit Decision Diagnostic

**Generated:** 2026-03-12T01:57:08.669809Z
**Seed:** 42
**Analysis SHA:** 186c603f1d69cc8dad7738a2d7abfecca4552d1c

## Summary

**Gate decision:** Track B (GBT) or further investigation

Errors spread across calibration range (boundary=28.5%). Nonlinear model or alternative approach may be needed.

## 1. Error Taxonomy (H2H Data)

Total suit hands where AV v1 is bidder: **51,741**

| Category | Count | Fraction | Avg Points |
|----------|-------|----------|------------|
| Over-bid (set) | 1,819 | 3.5% | -4.0 |
| Made | 49,922 | 96.5% | 6.4 |

Overall average points when AV v1 bids suit: **6.04**

### Wrong Contract (Counterfactual)

Of 10,000 suit-declared hands in CF data, **2,647** (26.5%) would have been better served by high/low. Average cost: -6.60 net_pts.

### Under-Bid (Counterfactual)

Of 10,000 pass hands in CF data, **6,273** (62.7%) had a profitable suit alternative. Average opportunity: 5.99 net_pts.

### Wrong Level (Counterfactual)

Of 10,000 multi-level suit hands, **516** (5.2%) would benefit from a different bid level. Average cost: -5.57 net_pts.

## 2. AV v1 vs R0 Suit Comparison

| Metric | AV v1 | R0 |
|--------|-------|-----|
| Suit hands (as bidder) | 51,741 | 52,702 |
| Suit made rate | 96.5% | 98.0% |
| Suit avg points | 6.04 | 6.21 |
| Suit set rate | 3.5% | 2.0% |

Suit bid rate ratio (AV v1 / R0): **0.98**

## 3. Make/Set Boundary Analysis

Suit R² (reconstructed): **0.588**
Rows analyzed: 266,340

### Bimodality
- P(make): 37.0%
- Made avg net_pts: 2.29
- Set avg net_pts: -13.43
- Gap: 15.72

### Error Concentration

| Region | N | Fraction | Abs Residual % | P(make) | Avg Predicted | Avg Actual |
|--------|---|----------|---------------|---------|--------------|------------|
| Boundary (0.3-0.7) | 41,406 | 15.5% | 28.5% | 45.5% | -5.34 | -4.98 |
| Clear make (>0.7) | 76,564 | 28.7% | 28.5% | 93.9% | -0.50 | 0.90 |
| Clear set (<0.3) | 148,370 | 55.7% | 43.0% | 5.4% | -12.20 | -12.73 |

## 4. Bid-Level Headroom (H13)

Hands analyzed: 10,000
Improvable by different level: **230** (2.3%)
Average improvement (when improvable): 5.73 net_pts
Headroom per hand (overall): 0.132 net_pts

### Optimal Level Distribution

| Level | Count | Fraction |
|-------|-------|----------|
| 1 | 3,581 | 35.8% |
| 5 | 927 | 9.3% |
| 6 | 2,770 | 27.7% |
| 7 | 2,194 | 21.9% |
| 8 | 493 | 4.9% |
| 9 | 35 | 0.4% |

## 5. Gate Decision

**Recommended track:** Track B (GBT) or further investigation

Errors spread across calibration range (boundary=28.5%). Nonlinear model or alternative approach may be needed.

### Gate Inputs

| Input | Value | Threshold |
|-------|-------|-----------|
| Boundary error % | 28.5% | >60% → Track A |
| Wrong contract fraction | 26.5% | >30% → New direction |
| Bid-level improvable % | 2.3% | >30% → Level fix |
| Headroom per hand | 0.132 | Qualitative |

## Provenance

| Item | Value |
|------|-------|
| gate_status | Track B (GBT) or further investigation |
| analysis_sha | 186c603f1d69cc8dad7738a2d7abfecca4552d1c |
| seed | 42 |
| h2h_source | data/runs/arc_d_r0_h2h_battery_42_20260308_173038 |
| cf_source | data/runs/action_value_quick_42_v2/datasets/action_value.parquet |
