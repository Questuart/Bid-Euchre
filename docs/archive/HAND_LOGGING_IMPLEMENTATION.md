# Hand Logging Implementation - Schema v3

**Date**: December 17, 2025
**Status**: ✅ Complete and Tested

---

## Overview

Added full hand logging to the simulation framework. Each player's complete dealt hand is now captured in JSONL logs for reproducibility, debugging, and future ML training datasets.

---

## Changes Made

### 1. Schema Version Bump (v2 → v3)

**File**: `src/bid_euchre/logging/game_logger.py`

- Bumped `SCHEMA_VERSION` from 2 to 3
- Added `hands` field to `HandEndRecord` dataclass
- Updated `log_hand_end()` method to accept and serialize hands

**Changes**:
- `HandEndRecord` now includes: `hands: Optional[List[List[List[str]]]]`
- Card serialization converts `Card` objects to `[suit, rank]` format
- Format matches existing `trick_end` plays for consistency

### 2. Simulation Updates

**File**: `src/bid_euchre/sim/simulation.py`

**`play_single_hand()` function**:
- Return signature changed from 5 to 6 values
- Now returns: `(team0_tricks, team1_tricks, all_player_scores, all_player_features, initial_leader, starting_hands)`
- Updated docstring to document new return value

**`simulate_many_hands()` function**:
- Updated both call sites to capture `starting_hands`
- Passes `starting_hands` to `logger.log_hand_end()`

### 3. Schema Documentation

**File**: `docs/schemas/hand_record.md`

- Updated schema version to 3
- Added `hands` field documentation
- Provided example JSON with full hands
- Updated version history table
- Added "Hands Format" section explaining card representation

### 4. Test Updates

**File**: `tests/test_integration.py`

- Updated `test_full_hand_simulation_basic_strategy()` to handle new return signature
- Added validation for `starting_hands` structure

---

## Format Specification

### Card Representation (Option B - Structured Tuples)

Each card is represented as a 2-element array: `[suit, rank]`

**Suits**: `"C"`, `"D"`, `"H"`, `"S"` (Clubs, Diamonds, Hearts, Spades)
**Ranks**: `"T"`, `"J"`, `"Q"`, `"K"`, `"A"` (Ten, Jack, Queen, King, Ace)

### Hand Format

The `hands` field contains 4 hands (one per player), each with 10 cards:

```json
{
  "hands": [
    [["H","J"], ["H","K"], ["H","Q"], ...],  // Player 0 (10 cards)
    [["C","J"], ["D","K"], ["S","A"], ...],  // Player 1 (10 cards)
    [["H","A"], ["C","K"], ["D","Q"], ...],  // Player 2 (10 cards)
    [["S","T"], ["C","A"], ["D","J"], ...]   // Player 3 (10 cards)
  ]
}
```

---

## Backward Compatibility

✅ **Fully backward compatible**:
- `hands` field is optional (can be `null`)
- Old log consumers can ignore the new field
- Code without logger still works (hands parameter is optional)
- Existing schema v2 logs remain valid

---

## Validation Results

All tests passed:

```
✅ play_single_hand returns 6 values (added starting_hands)
✅ starting_hands structure validated (4 hands × 10 cards)
✅ Schema v3 logs generated correctly
✅ Card format validated: [[suit, rank], ...]
✅ Backward compatibility confirmed
```

**Test coverage**:
- Return signature validation
- Hand structure validation
- Schema version detection
- Card format validation (suit/rank values)
- Logging enabled/disabled scenarios

---

## Usage Example

```python
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy import GreedyStrategy
from bid_euchre.logging import GameLogger, LogLevel

# Create logger
logger = GameLogger(
    run_id='my_experiment',
    strategy_id='greedy',
    level=LogLevel.HAND,
    output_dir='logs'
)

# Run simulation with hand logging
with logger:
    results = simulate_many_hands(
        n=1000,
        contract_type='suit',
        trump_suit='H',
        seed=42,
        strategy=GreedyStrategy(),
        logger=logger
    )

# Logs will contain full hands for each deal
```

---

## Files Modified

| File | Lines Changed | Description |
|------|---------------|-------------|
| `src/bid_euchre/logging/game_logger.py` | ~30 | Schema v3, hands field, serialization |
| `src/bid_euchre/sim/simulation.py` | ~15 | Return starting_hands, pass to logger |
| `docs/schemas/hand_record.md` | ~60 | Documentation updates |
| `tests/test_integration.py` | ~10 | Test updates for new signature |

**Total**: ~115 lines changed across 4 files

---

## Benefits

1. **Reproducibility**: Exact hands can be reconstructed for debugging
2. **Analysis**: Full hand visibility enables deep statistical analysis
3. **ML Training**: Complete ground truth data for supervised learning
4. **Debugging**: Can replay specific problematic hands
5. **Validation**: Verify hand evaluation functions against actual cards

---

## Next Steps (Optional)

Potential future enhancements:
1. Add `dealer_seat` field (currently no dealer concept exists)
2. Add hand replay utility function
3. Add hand visualization tools
4. Create hand database for interesting scenarios

---

**Implementation Time**: ~30 minutes
**Token Cost**: ~8,000 tokens (including testing and documentation)
**Difficulty**: Easy ⭐
**Risk**: Low (backward compatible, well-tested)
