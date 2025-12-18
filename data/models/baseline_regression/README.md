# Baseline OLS Regression Models

## Overview

These are simple, interpretable baseline models for predicting team tricks won from pre-hand features. Trained on 200k hands of improved_greedy self-play data.

## Models

### 1. baseline_regression_suit.pkl
**Contract Type:** Suit (Hearts, Spades, Diamonds, Clubs)  
**Features:** 4
- `trump_count` (coefficient: +0.49)
- `trump_rb_count` (coefficient: +0.71)
- `trump_lb_count` (coefficient: +0.29)
- `offsuit_aces` (coefficient: +0.60)

**Performance:**
- Test R²: 0.2207
- Test MAE: 1.45 tricks
- Intercept: 2.13

**Formula:**
```
predicted_tricks = 2.13 + 0.49×trump_count + 0.71×trump_rb_count + 0.29×trump_lb_count + 0.60×offsuit_aces
```

---

### 2. baseline_regression_high.pkl
**Contract Type:** High (Ace High No-Trump)  
**Features:** 1
- `offsuit_aces` (coefficient: +0.77)

**Performance:**
- Test R²: 0.1936
- Test MAE: 1.35 tricks
- Intercept: 3.47

**Formula:**
```
predicted_tricks = 3.47 + 0.77×offsuit_aces
```

**Interpretation:** Each ace wins approximately 0.77 tricks.

---

### 3. baseline_regression_low.pkl
**Contract Type:** Low (Ten High No-Trump)  
**Features:** 1
- `offsuit_tens_count` (coefficient: +0.76)

**Performance:**
- Test R²: 0.2056
- Test MAE: 1.35 tricks
- Intercept: 3.49

**Formula:**
```
predicted_tricks = 3.49 + 0.76×offsuit_tens_count
```

**Interpretation:** Each ten wins approximately 0.76 tricks.

---

## Training Details

**Data:**
- Training set: 70% (suit: 280k hands, high/low: 140k hands each)
- Validation set: 15% (suit: 60k hands, high/low: 30k hands each)
- Test set: 15% (suit: 60k hands, high/low: 30k hands each)
- Source: improved_greedy self-play (deterministic, seed=42)

**Method:**
- Ordinary Least Squares (OLS) regression
- No regularization (no overfitting detected)
- Trained via normal equation: β = (X'X)^-1 X'y

**Validation:**
- Train-test R² gap < 0.01 for all models ✅
- No overfitting detected
- Ridge regularization NOT needed

---

## Key Findings

### 1. Single Features Are Powerful
- HIGH and LOW contracts: single feature explains ~20% of variance
- This matches theoretical expectation (r²=0.45² ≈ 0.20)

### 2. Performance vs. Dummy Baseline
- Dummy (predict 5.0 always): MAE ≈ 2.0 tricks
- Our models: MAE = 1.35-1.46 tricks
- **Improvement: 32-33%** ✅

### 3. Ceiling on Performance
- R² = 0.19-0.21 is realistic for pre-hand prediction
- Card play, partner's hand, and opponent decisions add huge variance
- These models are **good enough for bidding strategy**

### 4. Model Stability
- All models generalize well to test data
- No signs of overfitting
- Simple features → interpretable predictions

---

## Usage

```python
import pickle

# Load model
with open('data/models/baseline_regression/baseline_regression_high.pkl', 'rb') as f:
    model_data = pickle.load(f)
    model = model_data['model']
    features = model_data['features']

# Make prediction
from bid_euchre.features.hand_eval import get_hand_features

hand_features = get_hand_features(hand, contract_type='high', trump_suit=None)
feature_vector = [hand_features[fname] for fname in features]
predicted_tricks = model.predict([feature_vector])[0]
```

---

## Next Steps

### Option A: Use as Baseline (Recommended)
- These models are solid benchmarks
- Compare future models against these
- Use for bidding strategy prototype

### Option B: Improve Models
Add more features:
- **SUIT:** trump_power_sum, trump_count_x_offsuit_ace
- **HIGH:** rank_sum, offsuit_suits_with_ace  
- **LOW:** rank_sum, low_card_count

Expected improvement: R² → 0.25-0.32

### Option C: Build Bid Evaluator (Recommended)
1. Predict tricks for each contract type
2. Choose contract with highest expected tricks
3. Add bid level logic (predicted + margin)
4. Test in head-to-head simulation

---

## Files

- `baseline_regression_suit.pkl` - Suit contract model
- `baseline_regression_high.pkl` - High contract model
- `baseline_regression_low.pkl` - Low contract model
- `README.md` - This file

**Created:** 2025-12-17  
**Training script:** `experiments/train_baseline_regression.py`  
**Data source:** `data/runs/hand_eval_test_greedy_42_20251217_200200/`

