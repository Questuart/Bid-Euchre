# OLSa R0 Model Specification

Concrete R0 model parameters for both arms of the Arc D OLSa-Hybrid bidder.
For the general artifact schema, see hybrid_olsa_v1.md.

## Artifact Identity

| Field | OLSa (constrained) | OLSa_Full (promotional) |
|-------|---------------------|-------------------------|
| Artifact path | data/artifacts/arc_d/r0/hybrid_r0.json | data/artifacts/arc_d/r0/hybrid_r0_full.json |
| SHA256 | 7b523cd6f0de41a82eca55f6b0bedc09d18630638609226ee3e8ddb443f71fe8 | 5436b759f525466976244766dee8d98472dcfe243ac1d4542885e6cd0e6dcbc7 |
| Frozen at | 2026-02-22T02:01:51Z | 2026-02-22T02:02:31Z |
| Schema | hybrid_olsa_v1 | hybrid_olsa_v1 |
| Rung | r0 | r0 |

## Configuration

| Parameter | Value |
|-----------|-------|
| risk_lambda | 0.0 |
| context_features | [] (none at R0) |
| split_type | three_way |
| training_seed | 42 |
| training_run | canonical_bidless_dataset_glutton_42_20260221_175752 |

## OLSa (Constrained Arm)

Locked feature budget: 3 features for suit, 1 for high, 1 for low.

### Suit Contract

| Feature | Weight | Description |
|---------|--------|-------------|
| bowers | +0.4493 | Count of bower cards (right + left) |
| trump_count | +0.4316 | Total trump suit cards in hand |
| offsuit_aces | +0.3403 | Count of aces in non-trump suits |

- **Bias:** 2.7455
- **Residual variance:** 2.3395

### High Contract (no-trump, A high)

| Feature | Weight | Description |
|---------|--------|-------------|
| offsuit_aces | +0.7106 | Count of aces across all suits |

- **Bias:** 3.5788
- **Residual variance:** 2.8772

### Low Contract (no-trump, 10 high)

| Feature | Weight | Description |
|---------|--------|-------------|
| offsuit_tens_count | +0.7153 | Count of 10s across all suits |

- **Bias:** 3.5694
- **Residual variance:** 2.8983

## OLSa_Full (Promotional Arm)

Forward-selected features from all 39 available. Selection uses GroupKFold
cross-validation with R² improvement threshold of 0.005.

### Suit Contract

| Feature | Weight | Description |
|---------|--------|-------------|
| hand_value | +0.0075 | Composite hand strength score |
| quick_tricks | +0.1947 | Estimated quick tricks (top winners) |
| low_card_count | +0.1511 | Count of low-ranking cards |

- **Bias:** 0.2379
- **Residual variance:** 2.3189

### High Contract (no-trump, A high)

| Feature | Weight | Description |
|---------|--------|-------------|
| offsuit_non_ace_count | −0.6598 | Non-ace cards in offsuit (negative = fewer is better) |
| offsuit_best_rank_sum | +0.0592 | Sum of best ranks per offsuit |

- **Bias:** 9.5419
- **Residual variance:** 2.8545

### Low Contract (no-trump, 10 high)

| Feature | Weight | Description |
|---------|--------|-------------|
| offsuit_tens_count | +0.6654 | Count of 10s across all suits |
| offsuit_best_rank_sum | +0.0578 | Sum of best ranks per offsuit |

- **Bias:** 2.9496
- **Residual variance:** 2.8766

## Feature Selection Log (Full Arm)

Forward selection steps showing R² improvement at each step.

### Suit

| Step | Feature added | R² | Improvement |
|------|---------------|-----|-------------|
| 1 | hand_value | 0.1877 | — |
| 2 | quick_tricks | 0.2039 | +0.0162 |
| 3 | low_card_count | 0.2178 | +0.0139 |

### High

| Step | Feature added | R² | Improvement |
|------|---------------|-----|-------------|
| 1 | offsuit_non_ace_count | 0.1776 | — |
| 2 | offsuit_best_rank_sum | 0.1841 | +0.0065 |

### Low

| Step | Feature added | R² | Improvement |
|------|---------------|-----|-------------|
| 1 | offsuit_tens_count | 0.1785 | — |
| 2 | offsuit_best_rank_sum | 0.1846 | +0.0061 |

## Training Provenance

All metrics computed on the canonical glutton dataset (200k suit hands,
50k high, 50k low) with three-way split (80/10/10).

### OLSa (Constrained)

| Contract | R²_train | R²_val | R²_test | MAE_train | MAE_test | n_train | n_val | n_test |
|----------|----------|--------|---------|-----------|----------|---------|-------|--------|
| suit | 0.2109 | 0.2184 | 0.2153 | 1.232 | 1.235 | 640,000 | 80,000 | 80,000 |
| high | 0.1777 | 0.1764 | 0.1797 | 1.358 | 1.342 | 160,000 | 20,000 | 20,000 |
| low | 0.1785 | 0.1829 | 0.1871 | 1.364 | 1.353 | 160,000 | 20,000 | 20,000 |

### OLSa_Full (Promotional)

| Contract | R²_train | R²_val | R²_test | MAE_train | MAE_test | n_train | n_val | n_test |
|----------|----------|--------|---------|-----------|----------|---------|-------|--------|
| suit | 0.2178 | 0.2259 | 0.2220 | 1.226 | 1.229 | 640,000 | 80,000 | 80,000 |
| high | 0.1842 | 0.1820 | 0.1862 | 1.356 | 1.339 | 160,000 | 20,000 | 20,000 |
| low | 0.1847 | 0.1882 | 0.1921 | 1.362 | 1.353 | 160,000 | 20,000 | 20,000 |

### Observations

- Suit models explain ~21% of variance (R² ≈ 0.21–0.22), while no-trump
  models explain ~18% (R² ≈ 0.18–0.19). Suit contracts have more structure
  for linear models to exploit (bowers, trump count).

- Train/val/test R² values are consistent within each contract type (no
  overfitting signal). The slight test > train pattern in some rows is within
  sampling noise given the large sample sizes.

- Full arm shows marginal R² improvement over constrained (+0.007 for suit,
  +0.007 for high, +0.005 for low), consistent with the small performance
  difference between arms at R0.

- n_train for suit is 640,000 (= 200k hands × 4 seats × 80% split) vs
  160,000 for high/low (= 50k × 4 × 80%), reflecting the contract_type
  distribution in the glutton dataset.

## Split Manifests

| Contract | Manifest | Total hands | Train | Val | Test |
|----------|----------|-------------|-------|-----|------|
| suit | split_manifest_r0_suit.json | 200,000 | 160,000 | 20,000 | 20,000 |
| high | split_manifest_r0_high.json | 50,000 | 40,000 | 5,000 | 5,000 |
| low | split_manifest_r0_low.json | 50,000 | 40,000 | 5,000 | 5,000 |

Source parquet SHA256: 03b3b99836f090e07dff75b8d94b03a86851ea5ef275d48420f8e5d66ae8b5c3

## Git SHA

Evaluator code at promotion: b194908ca8b0cf265d78c4661716e56343796db3
Training code: 5c30bc43ad9b5cf9259ab503531338dd3da1af90
