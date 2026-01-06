# Bidder-Aware Models: OLSa_v2 vs OLSa_SR_v2

## Overview

Trained two families of bidder-aware models to compare feature engineering approaches:

1. **OLSa_v2**: Baseline trump/offsuit features + `is_bidder`
2. **OLSa_SR_v2**: Hand Value (single aggregated score) + `is_bidder`

**Training Data**: 50k hands of OLSa_SR_Floor self-play (200k player-hand records)
**Splits**: 70% train / 15% val / 15% test
**Date**: 2026-01-04

---

## Quick Results

### Test Set Performance

| Contract | Winner      | R² (Winner) | R² (Loser) | R² Δ     | MAE (Winner) |
|----------|-------------|-------------|------------|----------|--------------|
| **SUIT** | **OLSa_v2** | **0.2624**  | 0.2328     | +0.0296  | **1.683**    |
| **HIGH** | **OLSa_v2** | **0.2585**  | 0.1947     | +0.0638  | **1.542**    |
| **LOW**  | **OLSa_SR_v2** | **0.1422** | 0.1035   | +0.0387  | **1.438**    |

**Overall Winner**: **OLSa_v2** (2 out of 3 contracts, larger margins)

---

## Key Findings

### 1. Feature Engineering Matters

**OLSa_v2** (multi-feature baseline) significantly outperforms **OLSa_SR_v2** (hand value) for SUIT (+12.7% R²) and HIGH (+32.8% R²) contracts.

**Why?**
- `hand_value` is surprisingly weak as a single predictor
- Trump-specific features (bowers, trump count) capture nuance better
- Aggregated scores lose information

### 2. Bidder Advantage Varies Dramatically by Contract

From OLSa_v2 coefficients:

| Contract | `is_bidder` Coefficient | Interpretation |
|----------|------------------------|----------------|
| **SUIT** | **+0.646** | Moderate advantage (~0.65 extra tricks) |
| **HIGH** | **-0.108** | Slight *disadvantage* (counter-intuitive!) |
| **LOW**  | **+1.403** | Massive advantage (~1.4 extra tricks!) |

**Insights:**
- **LOW contracts**: Bidder chooses trump to protect weak suits → huge edge
- **HIGH contracts**: Holding high cards doesn't benefit from trump selection
- **SUIT contracts**: Balanced advantage from trump selection

### 3. Low Contracts Are Hard to Predict

Both models struggle with LOW contracts (R² ~0.10-0.14 vs. ~0.23-0.26 for SUIT/HIGH).

**Possible reasons:**
- HIGH variability in outcomes
- Trump selection (by bidder) introduces strategic complexity
- Hand value inversion logic may confuse models
- Defender coordination more impactful

### 4. Hand Value Feature Needs Work

OLSa_SR_v2 `hand_value` coefficients are suspiciously weak or negative:
- SUIT: 0.008 (near zero)
- HIGH: 0.016 (weak)
- LOW: -0.015 (negative!)

This suggests `hand_value` calculation may need:
- Contract-specific normalization
- Better trump awareness
- Separate scoring for bidder vs defender roles

---

## Model Details

### OLSa_v2 (Baseline + is_bidder)

**SUIT Contract**
```
Features: trump_count, trump_rb_count, trump_lb_count, offsuit_aces, is_bidder
Test R²: 0.2624  |  MAE: 1.683

Coefficients:
  trump_count         0.414
  trump_rb_count      0.659  ← strongest predictor
  trump_lb_count      0.276
  offsuit_aces        0.529
  is_bidder           0.646  ← adds ~0.65 tricks
  intercept           2.336
```

**HIGH Contract**
```
Features: offsuit_aces, offsuit_length_3plus_count, is_bidder
Test R²: 0.2585  |  MAE: 1.542

Coefficients:
  offsuit_aces                0.732  ← dominant predictor
  offsuit_length_3plus_count  0.016
  is_bidder                  -0.108  ← slight disadvantage!
  intercept                   3.532
```

**LOW Contract**
```
Features: offsuit_length_3plus_count, is_bidder
Test R²: 0.1035  |  MAE: 1.479

Coefficients:
  offsuit_length_3plus_count  -0.024
  is_bidder                    1.403  ← huge advantage!
  intercept                    4.696
```

### OLSa_SR_v2 (Hand Value + is_bidder)

**SUIT Contract**
```
Features: hand_value, is_bidder
Test R²: 0.2328  |  MAE: 1.715

Coefficients:
  hand_value   0.008  ← very weak!
  is_bidder    0.598
  intercept    0.861
```

**HIGH Contract**
```
Features: hand_value, is_bidder
Test R²: 0.1947  |  MAE: 1.610

Coefficients:
  hand_value   0.016  ← weak
  is_bidder   -0.057
  intercept    0.350
```

**LOW Contract**
```
Features: hand_value, is_bidder
Test R²: 0.1422  |  MAE: 1.438

Coefficients:
  hand_value  -0.015  ← negative! (inverted logic?)
  is_bidder   -0.044  ← negative (suspicious)
  intercept    9.536
```

---

## Recommendations

### For Production Bidding

1. **Use OLSa_v2 for SUIT and HIGH contracts**
   - Better predictive performance
   - More interpretable coefficients
   - Trump-specific features are valuable

2. **Use OLSa_v2 for LOW contracts (despite lower R²)**
   - OLSa_SR_v2 has suspicious negative coefficients
   - OLSa_v2 is more interpretable (huge `is_bidder` advantage)
   - Consistency across all contracts preferred

3. **Critical: Account for Bidder Advantage**
   - SUIT: +0.65 tricks
   - HIGH: -0.11 tricks (minimal)
   - LOW: +1.40 tricks (massive!)

### For Future Model Development

1. **Investigate `hand_value` calculation**
   - Why is it such a weak predictor?
   - Contract-specific scaling needed?
   - Separate formulas for bidder vs defender?

2. **Improve LOW contract predictions**
   - Add interaction features
   - Consider non-linear models
   - Analyze defender coordination patterns

3. **Explore advanced feature engineering**
   - Polynomial features
   - Trump × offsuit interactions
   - Positional features (dealer, LOD, etc.)

4. **Consider ensemble approaches**
   - Combine OLSa_v2 and OLSa_SR_v2 predictions
   - Use different models for different game phases

5. **Separate bidder and defender models**
   - Current models mix both roles
   - Role-specific features could improve performance

---

## Files

**Models:**
- `data/models/olsa_v2/olsa_v2_{suit,high,low}.pkl`
- `data/models/olsa_sr_v2/olsa_sr_v2_{suit,high,low}.pkl`

**Reports:**
- `data/reports/bidder_models_comparison.txt` (detailed comparison)
- `data/reports/bidder_models_dashboard.png` (visual comparison)

**Training Data:**
- `data/training/bidder_aware_{train,val,test}.csv`

**Scripts:**
- `experiments/train_bidder_aware_models.py` (training)
- `experiments/generate_bidder_models_dashboard.py` (visualization)

---

## Conclusion

**OLSa_v2** (Baseline + is_bidder) is the clear winner for production use:
- Wins 2/3 contracts with significant margins
- More interpretable feature coefficients
- Captures trump-specific nuance that `hand_value` misses

The `is_bidder` feature is critical, especially for LOW contracts where the bidder advantage is enormous (~1.4 tricks).

Next step: Test OLSa_v2 models in head-to-head simulations against existing strategies.
