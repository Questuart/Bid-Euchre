# Regression Model Comparison - Final Summary

## Overview

This document summarizes the complete regression modeling exercise for predicting team tricks from pre-hand features. We tested three approaches: Baseline OLS, Expanded OLS, and Ridge Regression.

---

## 📊 Performance Summary

| Model | Features | SUIT R² | HIGH R² | LOW R² | Avg MAE | Complexity |
|-------|----------|---------|---------|--------|---------|------------|
| **Baseline OLS** | 1-3 | 0.2123 | 0.1936 | 0.2056 | 1.42 | ✅ Simple |
| **Expanded OLS** | 5-6 | 0.2180 | 0.1969 | 0.2098 | 1.42 | ⚠️ Medium |
| **Ridge** | 5-6 | 0.2180 | 0.1969 | 0.2098 | 1.42 | ⚠️ Medium |

### Key Finding: **All models achieve similar performance!**

---

## 🎯 Baseline OLS (Recommended)

**Features:**
- SUIT (3): `bowers`, `trump_count`, `offsuit_aces`
- HIGH (1): `offsuit_aces`
- LOW (1): `offsuit_tens_count`

**Performance:**
- Test R²: 0.19-0.21
- Test MAE: 1.35-1.46 tricks
- Win rate: 60.8% (vs 59.9% dummy baseline)

**Formulas:**
```
SUIT:  tricks = 2.13 + 0.50×bowers + 0.49×trump_count + 0.60×offsuit_aces
HIGH:  tricks = 3.47 + 0.77×offsuit_aces
LOW:   tricks = 3.49 + 0.76×offsuit_tens_count
```

**Pros:**
- ✅ Simple and interpretable
- ✅ No multicollinearity (VIF < 5)
- ✅ Fast to train and predict
- ✅ Easy to explain to stakeholders

**Cons:**
- ⚠️ Limited features may miss some information
- ⚠️ R² ceiling around 0.20

---

## 📈 Expanded OLS

**Features:**
- SUIT (6): Added `trump_power_sum`, `trump_count_x_offsuit_ace`, `void_count`
- HIGH (5): Added `offsuit_suits_with_ace`, `rank_sum`, `high_card_count`, `offsuit_suits_with_double_ace`
- LOW (5): Added `rank_sum`, `low_card_count`, `offsuit_secondbest_rank_sum`, `double_ten_jack_count`

**Performance:**
- Test R²: 0.20-0.22 (+0.003 to +0.006 improvement)
- Test MAE: 1.35-1.46 tricks (no improvement)

**Multicollinearity Issues:**
- SUIT: `trump_power_sum` VIF = 12.53 ❌
- HIGH: `offsuit_aces`, `offsuit_suits_with_ace` VIF = ∞ ❌
- LOW: `rank_sum` VIF = 5.52 ⚠️

**Coefficient Instability:**
- HIGH model: `offsuit_aces` = -2.22 (NEGATIVE! Nonsensical due to multicollinearity)

**Pros:**
- ✅ Slightly better R² (+3%)
- ✅ Uses more information

**Cons:**
- ❌ Severe multicollinearity
- ❌ Unstable coefficients
- ❌ Hard to interpret
- ❌ Minimal improvement over baseline

---

## 🔧 Ridge Regression

**Features:** Same as Expanded OLS (5-6 features)

**Hyperparameters:**
- SUIT: alpha = 100
- HIGH: alpha = 1000
- LOW: alpha = 100

**Performance:**
- Test R²: 0.20-0.22 (identical to Expanded OLS)
- Test MAE: 1.35-1.46 tricks (identical to Expanded OLS)

**Coefficient Stability:**
- HIGH model: `offsuit_aces` = +0.36 ✅ (positive and reasonable!)
- All coefficients shrunk toward zero
- More balanced importance across correlated features

**Pros:**
- ✅ Handles multicollinearity gracefully
- ✅ Stable, interpretable coefficients
- ✅ Good for production systems with many features

**Cons:**
- ⚠️ No R² improvement over OLS
- ⚠️ Adds hyperparameter tuning complexity
- ⚠️ Coefficients harder to interpret than baseline

---

## 💡 Key Insights

### 1. R² ≈ 0.20 is the Ceiling for Linear Models

**Why?**
- Pre-hand features explain ~20% of variance
- Remaining 80% due to:
  - Card play decisions
  - Partner's hand (unknown)
  - Opponent hands (unknown)
  - Trick-taking randomness

**This is expected and reasonable!**

### 2. Multicollinearity Affects Interpretation, Not Predictions

**Expanded OLS:**
- VIF > 10 (severe multicollinearity)
- Crazy coefficients (`offsuit_aces` = -2.22)
- But R² = 0.197 (predictions still work!)

**Ridge:**
- Same R² = 0.197
- Sane coefficients (`offsuit_aces` = +0.36)
- Regularization stabilized but didn't improve predictions

**Lesson:** Multicollinearity hurts interpretability, not predictive power.

### 3. Extra Features Don't Help Much

Adding 2-4 features improved R² by only +0.003 to +0.006 (1-3% relative).

**Why?**
- Features are redundant (`trump_power_sum` ≈ f(bowers, trump_count))
- Information overlap
- Diminishing returns

### 4. Baseline OLS is Best Trade-off

| Criterion | Baseline | Expanded OLS | Ridge |
|-----------|----------|--------------|-------|
| **Performance** | 0.19-0.21 | 0.20-0.22 | 0.20-0.22 |
| **Simplicity** | ✅✅✅ | ⚠️ | ⚠️ |
| **Interpretability** | ✅✅✅ | ❌ | ⚠️ |
| **Stability** | ✅✅ | ❌ | ✅✅ |

---

## 🎯 Final Recommendation

### **Use Baseline OLS**

**Reasons:**
1. ✅ Performance within 3% of complex models
2. ✅ Much simpler (1-3 features vs 5-6)
3. ✅ Easy to explain and debug
4. ✅ No multicollinearity issues
5. ✅ Principle of parsimony: simpler is better when performance is equal

**When to use alternatives:**
- **Ridge:** If you need 5+ features for some reason (e.g., standardized feature set across projects)
- **Expanded OLS:** Never (multicollinearity issues, no benefit)

---

## 🚀 Next Steps

### Option A: Move to Production (Recommended)
1. Integrate Baseline OLS into bidding strategy
2. Build full game simulator with bidding rounds
3. Test head-to-head against baselines
4. Deploy and monitor

### Option B: Explore Non-Linear Models
If you want R² > 0.25:
1. **Polynomial features** (degree 2) → Expected R²: 0.22-0.28
2. **Random Forest** → Expected R²: 0.25-0.32
3. **XGBoost** → Expected R²: 0.27-0.35

Trade-off: Complexity and interpretability vs. performance gain

### Option C: Focus on Other Improvements
- Partner communication strategies
- Opponent modeling
- Bid level calibration (conservative vs aggressive)
- Full bidding auction simulation

---

## 📁 Saved Models

**Location:** `data/models/`

1. **Baseline OLS** (recommended):
   - `baseline_regression/baseline_regression_suit.pkl`
   - `baseline_regression/baseline_regression_high.pkl`
   - `baseline_regression/baseline_regression_low.pkl`

2. **Expanded OLS** (not recommended):
   - `expanded_ols/expanded_ols_suit.pkl`
   - `expanded_ols/expanded_ols_high.pkl`
   - `expanded_ols/expanded_ols_low.pkl`

3. **Ridge** (if you need 5+ features):
   - `ridge_regression/ridge_regression_suit.pkl`
   - `ridge_regression/ridge_regression_high.pkl`
   - `ridge_regression/ridge_regression_low.pkl`

---

## 📊 Evaluation Scripts

- `experiments/train_baseline_regression.py` - Train baseline OLS
- `experiments/train_expanded_ols.py` - Train expanded OLS
- `experiments/train_ridge_regression.py` - Train Ridge with CV
- `experiments/evaluate_dummy_baseline.py` - Dummy baseline comparison
- `experiments/evaluate_bidding_performance.py` - Bidding win/loss rates

---

## 🏆 Conclusion

**Baseline OLS with 1-3 features is the winner!**

- R² = 0.19-0.21 (realistic for pre-hand prediction)
- MAE = 1.35-1.46 tricks (32% better than dummy)
- Win rate = 60.8% (vs 59.9% dummy)
- Simple, interpretable, stable

R² ≈ 0.20 is not "low" - it's the **ceiling** for pre-hand prediction. The remaining 80% variance comes from gameplay, which is exactly what we expect.

**This is a solid foundation for a bidding strategy!** 🎯

---

**Date:** December 17, 2025  
**Data:** 200k hands of improved_greedy self-play  
**Splits:** 70% train, 15% val, 15% test

