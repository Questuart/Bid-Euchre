# Diagnostic Tricks-Model Evaluation

> **Purpose:** Full-feature Ridge regression on `tricks_won` from canonical bidless data.
> Coefficients are standardized and exploratory. Correlated features share variance.
> This diagnostic is separate from the B0 hand-value regression in `train_b0.py`.

## Methodology

- **Model:** Ridge regression (alpha=1.0) with standardized features (z-scored)
- **Target:** `tricks_won` (per-seat, derived from team trick counts)
- **Split:** Grouped by `hand_id` (80/20 train/test) to prevent leakage across 4 seat rows
- **Features:** All 41 hand features from `get_hand_features()`

## Greedy Play Policy

- **Training:** 240,000 hands (960,000 seat-rows)
- **Test:** 60,000 hands (240,000 seat-rows)
- **R² (train):** 0.2070
- **R² (test):** 0.2088
- **MAE (train):** 1.3714
- **MAE (test):** 1.3777
- **Intercept:** 5.0000

### Top 10 Standardized Coefficients

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `highest_trump_rank` | -0.4468 |
| 2 | `rank_sum` | +0.4115 |
| 3 | `trump_rb_count` | +0.3632 |
| 4 | `trump_power_avg` | -0.3610 |
| 5 | `second_highest_trump_rank` | -0.3419 |
| 6 | `trump_count_x_void_count` | +0.3050 |
| 7 | `bowers` | +0.2695 |
| 8 | `hand_value` | +0.2679 |
| 9 | `offsuit_tens_count` | +0.2415 |
| 10 | `max_suit_len` | -0.1870 |

## Glutton Play Policy

- **Training:** 240,000 hands (960,000 seat-rows)
- **Test:** 60,000 hands (240,000 seat-rows)
- **R² (train):** 0.1917
- **R² (test):** 0.1928
- **MAE (train):** 1.2809
- **MAE (test):** 1.2867
- **Intercept:** 5.0000

### Top 10 Standardized Coefficients

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `trump_power_avg` | -0.6148 |
| 2 | `rank_sum` | +0.3992 |
| 3 | `trump_count_x_void_count` | +0.2562 |
| 4 | `offsuit_tens_count` | +0.2277 |
| 5 | `trump_rb_count` | +0.2157 |
| 6 | `fourth_suit_len` | +0.1902 |
| 7 | `hand_value` | +0.1868 |
| 8 | `bowers` | +0.1826 |
| 9 | `trump_count_x_offsuit_ace` | -0.1774 |
| 10 | `void_count` | +0.1591 |

## Per-Contract Breakdown: Greedy

| Contract | R² (test) | MAE (test) | N (test rows) | OLSa Feature Validation |
|----------|-----------|------------|---------------|------------------------|
| high | 0.2043 | 1.2807 | 40,000 | OK: {'offsuit_aces'} all in top 10 |
| low | 0.2133 | 1.2881 | 40,000 | OK: {'offsuit_tens_count'} all in top 10 |
| suit | 0.2295 | 1.4033 | 160,000 | WARN: {'trump_count', 'offsuit_aces'} not in top 10 |

### Greedy — contract=high top 5

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `high_offsuit` | -0.1764 |
| 2 | `offsuit_aces` | +0.1764 |
| 3 | `offsuit_suits_with_ace` | +0.1610 |
| 4 | `offsuit_king_count_total` | -0.1092 |
| 5 | `offsuit_suits_with_double_ace` | +0.1041 |

### Greedy — contract=low top 5

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `offsuit_tens_count` | +0.6255 |
| 2 | `rank_sum` | +0.1244 |
| 3 | `hand_value` | +0.1244 |
| 4 | `offsuit_secondbest_rank_sum` | +0.1100 |
| 5 | `offsuit_best_rank_sum` | +0.0949 |

### Greedy — contract=suit top 5

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `trump_rb_count` | +0.3050 |
| 2 | `second_highest_trump_rank` | -0.2984 |
| 3 | `highest_trump_rank` | -0.2936 |
| 4 | `trump_count_x_void_count` | +0.2792 |
| 5 | `bowers` | +0.2082 |

## Per-Contract Breakdown: Glutton

| Contract | R² (test) | MAE (test) | N (test rows) | OLSa Feature Validation |
|----------|-----------|------------|---------------|------------------------|
| high | 0.1893 | 1.3426 | 40,000 | OK: {'offsuit_aces'} all in top 10 |
| low | 0.1949 | 1.3511 | 40,000 | OK: {'offsuit_tens_count'} all in top 10 |
| suit | 0.2353 | 1.2189 | 160,000 | WARN: {'trump_count', 'offsuit_aces'} not in top 10 |

### Glutton — contract=high top 5

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `offsuit_aces` | +0.1642 |
| 2 | `high_offsuit` | -0.1642 |
| 3 | `offsuit_best_rank_sum` | +0.1436 |
| 4 | `offsuit_suits_with_ace` | +0.1394 |
| 5 | `offsuit_secondbest_rank_sum` | +0.1186 |

### Glutton — contract=low top 5

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `offsuit_tens_count` | +0.5753 |
| 2 | `offsuit_best_rank_sum` | +0.1726 |
| 3 | `offsuit_secondbest_rank_sum` | +0.1488 |
| 4 | `rank_sum` | +0.1142 |
| 5 | `hand_value` | +0.1142 |

### Glutton — contract=suit top 5

| Rank | Feature | Coefficient |
|------|---------|-------------|
| 1 | `void_count` | +0.2022 |
| 2 | `trump_rb_count` | +0.1615 |
| 3 | `bowers` | +0.1296 |
| 4 | `offsuit_length_3plus_count` | -0.1130 |
| 5 | `num_singletons` | +0.1129 |

## Caveats

- Coefficients are standardized (z-scored features) and exploratory only
- Correlated features share variance; coefficients do not imply causal importance
- This diagnostic is separate from the B0 hand-value regression pipeline
- Use Ridge (not raw OLS) for 40+ correlated features to avoid numerical instability
