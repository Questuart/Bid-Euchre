# Training Data Documentation

## Bidder-Aware Training Data (Current)

**Generated:** 2026-01-03
**Schema Version:** v5
**Total Records:** 200,000 (50,000 hands × 4 players/hand)
**Data Split:** 70/15/15 (train/val/test)

### Files

- `bidder_aware_train.csv` - 140,000 records (training set)
- `bidder_aware_val.csv` - 30,000 records (validation set)
- `bidder_aware_test.csv` - 30,000 records (test set)

### Generation Pipeline

1. **Simulation** (`experiments/generate_bidder_training_data.py`)
   - Config: `experiments/configs/bidder_training_data.yaml`
   - Strategy: OLSa_SR_Floor self-play (all 4 players)
   - Hands: 50,000
   - Mode: Full bidding phase enabled
   - Output: JSONL logs in `data/runs/bidder_training_data_42_*/logs/`

2. **Splitting** (`experiments/split_train_val_test.py`)
   - Deterministic split by deal_id
   - Ratios: 70% train, 15% val, 15% test
   - Output: JSONL splits in `data/runs/bidder_training_data_42_*/splits/`

3. **CSV Conversion** (`experiments/convert_splits_to_csv.py`)
   - Extracts features per player-hand
   - Adds positional metadata
   - Output: CSV files in `data/training/`

### Schema

Each row represents one player's hand in one deal:

**Metadata:**
- `deal_id` - Unique deal identifier
- `player_idx` - Player position (0-3)
- `contract_type` - Contract type (suit/high/low)
- `trump_suit` - Trump suit (C/D/H/S or none)
- `dealer_position` - Dealer seat (0-3)
- `bidder_position` - Auction winner seat (0-3)

**Key Features:**
- `is_bidder` - Boolean: 1 if this player won the auction, 0 otherwise
- `actual_tricks` - Target variable: tricks won by this player's team

**Hand Features** (40 total):
- Trump features: `trump_count`, `trump_rb_count`, `trump_lb_count`, etc.
- Offsuit features: `offsuit_aces`, `offsuit_tens`, `offsuit_length_3plus_count`, etc.
- Derived features: `hand_value`, `rank_sum`, etc.

See `src/bid_euchre/features/hand_eval.py` for full feature definitions.

### Dataset Statistics

**Contract Distribution:**
- SUIT: 83.8% (167,600 records)
- HIGH: 7.1% (14,200 records)
- LOW: 9.2% (18,400 records)

**Bidder vs Defender:**
- Bidder hands: 25% (50,000 records - 1 per deal)
- Defender hands: 75% (150,000 records - 3 per deal)

**Trick Distribution:**
- Mean tricks (bidder teams): ~6.5
- Mean tricks (defender teams): ~3.5
- Bidder advantage varies by contract (see docs/BIDDER_MODELS.md)

### Reproducibility

To regenerate this dataset:

```bash
# Step 1: Run simulation
PYTHONPATH=src python experiments/generate_bidder_training_data.py

# Step 2: Split into train/val/test
python experiments/split_train_val_test.py \
  --input data/runs/bidder_training_data_42_*/logs/*.jsonl \
  --output data/runs/bidder_training_data_42_*/splits/ \
  --train-ratio 0.7 --val-ratio 0.15

# Step 3: Convert to CSV
python experiments/convert_splits_to_csv.py \
  --splits-dir data/runs/bidder_training_data_42_*/splits/ \
  --output-dir data/training/
```

### Models Trained From This Data

- **OLSa_v2** (`data/models/olsa_v2/`) - Baseline features + is_bidder
- **OLSa_SR_v2** (`data/models/olsa_sr_v2/`) - Hand Value + is_bidder

See `docs/BIDDER_MODELS.md` for model performance comparison.

### Usage Notes

1. **is_bidder is critical** - Models trained on this data MUST include `is_bidder` feature
2. **Position matters** - Bidder/defender role significantly affects trick-taking
3. **Imbalanced classes** - 25% bidders vs 75% defenders (by design)
4. **Strategy dependency** - Generated using OLSa_SR_Floor, may not generalize to other playstyles

### Historical Data

Previous training datasets (if any) are stored in `data/_deprecated/training/` with their own README files.

### Questions?

- Feature definitions: See `src/bid_euchre/features/hand_eval.py`
- Data generation: See `experiments/generate_bidder_training_data.py`
- Model training: See `experiments/train_bidder_aware_models.py`
- Schema documentation: See `docs/schemas/hand_record.md`
