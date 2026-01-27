# Bidding Development Plan: Blog Alignment

**Last Updated:** 2026-01-27
**Status:** Phase 0 (Pre-req complete)

This document outlines the implementation plan to align the codebase with the blog post "Bid Euchre, Part 4: How Do You Teach a Computer to Bid?"

---

## Completed Steps

### Pre-requisite: Rename HeuristicsBidder → RanktheTank ✅ DONE

The pre-requisite rename has been completed:
- Renamed `HeuristicsBidder` class to `RanktheTank` in `src/bid_euchre/strategy/bidding.py`
- Updated all imports, exports, tests, YAML configs, and documentation
- All tests pass (`make check`)

---

## Implementation Phases

### Phase 0: Validate Play Strategies (NEXT)

**Goal:** Confirm that Glutton is meaningfully better than simpler strategies.

**Command:**
```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --n_per 10000 \
  --seed 42
```

**Expected results:**
| Strategy | Expected Avg Tricks |
|----------|---------------------|
| Random | ~5.0 (baseline) |
| AlwaysLowest | ~4.5 (passive) |
| AlwaysHighest | ~4.8 (wasteful) |
| Greedy | ~5.5-6.0 |
| **Glutton** | **~6.0-6.5** |

**Success criteria:** Glutton > Greedy > Random with statistical significance.

---

### Phase 1: B0 on Tricks

**Goal:** Get a working tricks-prediction model.

**Steps:**
1. Wire dataset collection (`scripts/collect_bidless_dataset.py`)
2. Train B0 on `tricks_won` using `get_hand_features()`
3. Create `B0TricksBidder` class
4. Register in config system

**Verification:**
```bash
# Collect bidless data
PYTHONPATH=src python scripts/collect_bidless_dataset.py --n_hands 50000 --seed 42

# Train B0
PYTHONPATH=src python scripts/train_b0.py --data data/bidless/... --output data/models/b0_tricks.json
```

---

### Phase 2: Generate Bid Data

**Goal:** Generate hands with actual bids and points.

**Steps:**
1. Create `experiments/configs/bid_dataset_collection.yaml`
2. Run simulation with B0TricksBidder + Glutton play
3. Log: `hand_features, bid, contract, tricks_won, points`

---

### Phase 3: Train on Actual Points

**Goal:** Train model predicting expected points given a bid.

**Steps:**
1. Create `scripts/train_b0_points.py`
2. Train on `hand_features + [bid_level]` → `points_earned`
3. Create `B0PointsBidder` class

---

### Phase 4: Comparison Tournament

**Goal:** Validate improvement chain.

**Metrics:**
- `make_rate` - % of bids made
- `avg_points` - average points per hand
- `cvar_5` - worst 5% outcomes (risk metric)

**Expected ordering:**
```
FiveHeadFred < RanktheTank ≤ B0TricksBidder < B0PointsBidder
```

---

## Files to Create/Modify

| Phase | File | Action |
|-------|------|--------|
| Pre | `src/bid_euchre/strategy/bidding.py` | ✅ Renamed to `RanktheTank` |
| Pre | All imports/tests/configs | ✅ Updated |
| 0 | `experiments/configs/strategy_comparison.yaml` | Verify exists, run |
| 1 | `scripts/collect_bidless_dataset.py` | Wire collector |
| 1 | `src/bid_euchre/strategy/bidding.py` | Add `B0TricksBidder` |
| 2 | `experiments/configs/bid_dataset_collection.yaml` | Create |
| 3 | `scripts/train_b0_points.py` | Create |
| 3 | `src/bid_euchre/strategy/bidding.py` | Add `B0PointsBidder` |
| 4 | `experiments/configs/bidder_comparison.yaml` | Create |

---

## Background: Why Points Sooner?

The blog's progression starts with tricks, but Bid Euchre scoring creates asymmetry:
- **Make bid:** Score = `tricks_won`
- **Get set:** Score = `-bid_tricks` (NEGATIVE!)

Example: Bid 6, win 5 tricks → **-6 points** (11-point swing vs defending!)

**Solution:** Use post-hoc scoring during training:
```python
# For each hand with tricks_won, compute points for each possible bid:
if tricks_won >= bid:
    points = tricks_won  # Made
else:
    points = -bid  # Set
```

This creates bid-conditional targets, letting B0 predict "expected points if I bid X."

---

## Reference

Full analysis in: `/Users/Quentin/.claude/plans/imperative-twirling-swing.md`
