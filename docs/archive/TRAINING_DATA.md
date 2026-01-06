# Bidder Training Data Generation

## Overview

This document describes the training data generated for bidder-aware regression models. The data captures hands from realistic bidding simulations to train models that understand the bidder/defender dynamic (+3.41 trick advantage for bidders).

---

## Dataset Summary

**Generated:** 2026-01-03
**Strategy:** OLSa_SR_Floor (Hand Value OLS, floor policy)
**Mode:** Self-play with full bidding
**Total Hands:** 50,000
**Total Records:** 200,000 (50k hands × 4 players)
**Seed:** 42 (reproducible)

### Splits

| Split | Hands | Records | Percentage |
|-------|-------|---------|------------|
| Train | 35,000 | 140,000 | 70% |
| Val | 7,500 | 30,000 | 15% |
| Test | 7,500 | 30,000 | 15% |

### Role Distribution

| Role | Count | Percentage |
|------|-------|------------|
| Bidders | 50,000 | 25.0% |
| Defenders | 150,000 | 75.0% |

*Note: 1 bidder per hand (25%) vs 3 defenders (75%)*

### Contract Distribution (Train Set)

| Contract | Count | Percentage |
|----------|-------|------------|
| Suit | 117,304 | 83.8% |
| High | 9,884 | 7.1% |
| Low | 12,812 | 9.2% |

*Reflects OLSa_SR_Floor's preference for suit contracts when hand quality allows*

---

## Data Format

### CSV Files

```
data/training/
├── bidder_aware_train.csv  (140,000 rows)
├── bidder_aware_val.csv    (30,000 rows)
└── bidder_aware_test.csv   (30,000 rows)
```

### Schema

Each row represents one player's hand with:

#### Metadata Fields
- `deal_id`: Hand number (0-49,999)
- `player_idx`: Player seat (0-3)
- `contract_type`: Final contract ("suit", "high", "low")
- `trump_suit`: Trump suit for suit contracts ("C", "D", "H", "S", or "none")
- `is_bidder`: **KEY FEATURE** - 1 if this player won auction, 0 otherwise
- `actual_tricks`: Team tricks won (0-10)
- `dealer_position`: Dealer seat (0-3)
- `bidder_position`: Auction winner seat (0-3)

#### Hand Features (40+ features)

**Trump Features (suit contracts):**
- `bowers`, `trump_count`, `trump_rb_count`, `trump_lb_count`
- `trump_ace_count`, `trump_king_count`, `trump_queen_count`, `trump_ten_count`
- `trump_power_sum`, `trump_power_avg`, `trump_duplicate_pairs`
- `highest_trump_rank`, `second_highest_trump_rank`, `third_highest_trump_rank`

**Offsuit Control:**
- `offsuit_aces`, `offsuit_king_count_total`, `offsuit_queen_count_total`
- `offsuit_suits_with_ace`, `offsuit_suits_with_double_ace`, `offsuit_suits_with_ace_and_king`

**Distribution:**
- `void_count`, `num_singletons`, `num_doubletons`
- `max_suit_len`, `second_suit_len`, `third_suit_len`, `fourth_suit_len`
- `offsuit_length_3plus_count`

**High/Low Specific:**
- `high_card_count`, `low_card_count`, `offsuit_tens_count`
- `double_ten_jack_count`

**Composite:**
- `hand_value` (rank-based hand strength)
- `rank_sum` (sum of card ranks)
- Interaction terms: `trump_count_x_void_count`, `trump_count_x_offsuit_ace`

---

## Generation Pipeline

### 1. Data Generation
```bash
PYTHONPATH=src python experiments/generate_bidder_training_data.py \
    --hands 50000 --seed 42
```

**Output:** `data/runs/bidder_training_data_42_<timestamp>/logs/*.jsonl`
**Duration:** ~53.6 seconds (933 hands/sec)

### 2. Split into Train/Val/Test
```bash
python experiments/split_train_val_test.py \
    data/runs/bidder_training_data_42_<timestamp>
```

**Output:** `data/runs/bidder_training_data_42_<timestamp>/splits/*.{train,val,test}.jsonl`
**Split Logic:** Deterministic based on `deal_id` ranges

### 3. Convert to CSV
```bash
python experiments/convert_splits_to_csv.py \
    data/runs/bidder_training_data_42_<timestamp>
```

**Output:** `data/training/bidder_aware_{train,val,test}.csv`

---

## Key Design Decisions

### Why OLSa_SR_Floor?

1. **Best current strategy** (risk-adjusted return: 1.249)
2. **Well-calibrated bids** (high make-rate)
3. **Realistic gameplay** (training reflects actual strong play)
4. **Floor policy** (conservative, less volatile)

### Why Self-Play?

- Consistent strategy across all 4 players
- Clean signal (no strategy mismatch noise)
- Can expand to mixed strategies later if needed

### Why No `bid_amount` Feature?

**Circular reasoning:** Using bid amount to predict tricks creates:
```
bid_amount=7 → model predicts 7.5 tricks → bid 8 → model predicts 8.2 → ...
```

**Solution:** Train models without `bid_amount`, rely only on:
- Hand features (trump count, aces, etc.)
- `is_bidder` flag (captures lead/information advantage)

### Why Include Defender Hands?

1. **4× more training data** (75% of records)
2. **Better model robustness** (learns both regimes)
3. **Future use:** Evaluate opponent strength during bidding

---

## Statistical Properties

### Bidder Advantage (From Position Analysis)

```
Bidder Team Avg Tricks:   6.71
Defender Team Avg Tricks: 3.29
Bidder Advantage:         +3.41 tricks (+68%!)
```

**This is the signal `is_bidder` captures!**

### Expected Model Improvement

| Metric | Current (OLSa) | Expected (Bidder-Aware) | Improvement |
|--------|----------------|-------------------------|-------------|
| R² (suit) | ~0.22 | ~0.38-0.45 | +73-105% |
| MAE | ~1.2 | ~0.75-0.9 | -25-38% |
| Make-Bid Rate | ~56% | ~62-65% | +6-9% |

---

## Next Steps

### Phase 1: Train Bidder/Defender Models

**Two model sets (6 models total):**
1. **Bidder Models** (suit/high/low) - Train on `is_bidder=1`
2. **Defender Models** (suit/high/low) - Train on `is_bidder=0`

**Usage:**
- **Bidding decisions:** Use bidder models (set `is_bidder=1`)
- **Post-hoc analysis:** Use appropriate model based on actual role
- **Opponent evaluation:** Use defender model to estimate their strength

### Phase 2: Feature Discovery

After establishing baseline with `is_bidder`:
1. **Residual analysis** - Where do models fail?
2. **Feature importance** - Which unused features matter?
3. **Interaction terms** - Do features interact with `is_bidder`?

Example candidate features:
- `is_bidder × void_count` (ruffing only works when leading)
- `is_bidder × trump_power_sum` (trump quality matters more for bidder)

### Phase 3: Model Comparison

**Test:** New bidder-aware models vs current OLSa models
**Metrics:** R², MAE, make-bid rate, points per hand
**Goal:** +10-15% improvement in bidding performance

---

## Files Created

### Core Infrastructure
- `experiments/generate_bidder_training_data.py` - Data generation runner
- `experiments/convert_splits_to_csv.py` - JSONL → CSV converter
- `experiments/configs/bidder_training_data.yaml` - Config (unused but documented)

### Generated Data
- `data/runs/bidder_training_data_42_20260103_173134/` - JSONL logs and splits
- `data/training/bidder_aware_train.csv` - 140k training records
- `data/training/bidder_aware_val.csv` - 30k validation records
- `data/training/bidder_aware_test.csv` - 30k test records

### Documentation
- `docs/TRAINING_DATA.md` - This file
- `docs/POSITION_IMPACT.md` - Positional analysis findings

---

## Validation Checks

### Data Integrity
✅ All 50k hands logged with schema v5
✅ Bidder/defender split exactly 25/75
✅ Contract types correctly logged (not null)
✅ Proper train/val/test split (70/15/15)
✅ All 40+ features present in CSV
✅ No misdeals in training data (leader != -1)

### Reproducibility
✅ Seed 42 for deterministic generation
✅ Split logic based on deal_id ranges
✅ All scripts committed to git
✅ Clear pipeline documentation

---

## Technical Notes

### Schema Version 5

The logs use schema v5 which includes:
- `dealer_position` - Who deals
- `bidder_position` - Who won auction
- `winning_bid` - Bid amount (not used in features)

### Bidding Mechanics

From `simulation.py`:
1. Dealer determined (or inferred from initial_leader)
2. Bidding order: LOD → Partner → ROD → Dealer
3. Dealer-partner pass rule (dealer auto-passes if partner leads)
4. Winner leads first trick

### Performance

**Generation:** 933 hands/sec (50k hands in 53.6s)
**Splitting:** ~instant
**Conversion:** ~2-3 seconds

---

**Status:** ✅ Dataset ready for model training
**Next:** Train bidder/defender models and compare to baseline
