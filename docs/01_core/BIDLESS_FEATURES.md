# Bidless Hand Features (v1)

## Overview

The **Bidless Hand Feature Extractor** transforms a 10-card hand (after bidding has concluded) into a fixed-order numeric feature vector for value model training. This extractor is deterministic and designed for predicting trick outcomes based on hand composition, trump strength, and positional context.

**Module**: `src/bid_euchre/features/bidless_hand_features.py`

**Schema Version**: v1

---

## Key Requirements

1. **Deterministic**: Same input always produces same output
2. **Stable Ordering**: Features always appear in the same order (no dict iteration randomness)
3. **Schema Versioned**: Includes version marker for forward compatibility
4. **Pure Function**: No side effects, no external state

---

## API

### Main Functions

#### `extract_bidless_hand_features(hand, contract_type, trump_suit, dealer_seat, leader_seat)`

Extracts features as a dictionary with stable key ordering.

**Args:**
- `hand` (List[Card]): The 10-card hand
- `contract_type` (str): "suit", "high", or "low"
- `trump_suit` (Optional[str]): Trump suit for suit contracts (e.g., "H"), None for high/low
- `dealer_seat` (Optional[int]): Dealer's seat index (0-3), or None if unknown
- `leader_seat` (Optional[int]): Leader's seat index (0-3), or None if unknown

**Returns:**
- `Dict[str, float]`: Feature dictionary with 31 features in stable order

**Raises:**
- `ValueError`: If `contract_type` is "suit" but `trump_suit` is None

---

#### `extract_feature_vector(hand, contract_type, trump_suit, dealer_seat, leader_seat)`

Convenience wrapper that returns features as a list instead of a dict, for direct use in ML frameworks.

**Returns:**
- `Tuple[List[float], List[str]]`: (feature_values, feature_names)

---

#### `get_feature_names()`

Returns the stable, ordered list of all 31 feature names.

**Returns:**
- `List[str]`: Feature names in extraction order

---

## Feature Schema (v1)

Total features: **31**

### 1. Schema Marker (1 feature)

| Feature | Type | Description |
|---------|------|-------------|
| `schema_version_marker` | float | Version identifier (v1 = 1.0) |

---

### 2. Hand Composition by Rank (5 features)

Counts of each rank in the hand, regardless of suit or trump status.

| Feature | Type | Description |
|---------|------|-------------|
| `count_aces` | float | Number of Aces in hand (0-10) |
| `count_kings` | float | Number of Kings in hand (0-10) |
| `count_queens` | float | Number of Queens in hand (0-10) |
| `count_jacks` | float | Number of Jacks in hand (0-10) |
| `count_tens` | float | Number of Tens in hand (0-10) |

---

### 3. Trump Features (7 features)

Trump strength indicators for suit contracts. For high/low contracts, all trump features are set to 0.

| Feature | Type | Description |
|---------|------|-------------|
| `trump_count` | float | Total trump cards (including bowers) (0-10) |
| `has_right_bower` | float | 1.0 if right bower present, else 0.0 |
| `has_left_bower` | float | 1.0 if left bower present, else 0.0 |
| `trump_aces` | float | Number of trump Aces (0-2) |
| `trump_kings` | float | Number of trump Kings (0-2) |
| `trump_queens` | float | Number of trump Queens (0-2) |
| `trump_tens` | float | Number of trump Tens (0-2) |

**Note**: In suit contracts:
- Right bower = Jack of trump suit
- Left bower = Jack of same-color suit (becomes trump)
- Trump cards are counted by their effective suit, not printed suit

---

### 4. Offsuit Distribution (6 features)

Suit length distribution, sorted longest to shortest for stability. In suit contracts, trump cards are excluded from offsuit counts.

| Feature | Type | Description |
|---------|------|-------------|
| `longest_offsuit_length` | float | Length of longest suit (0-10) |
| `second_longest_offsuit_length` | float | Length of 2nd longest suit (0-10) |
| `third_longest_offsuit_length` | float | Length of 3rd longest suit (0-10) |
| `shortest_offsuit_length` | float | Length of shortest suit (0-10) |
| `void_count` | float | Number of suits with 0 cards (0-4) |
| `singleton_count` | float | Number of suits with 1 card (0-4) |

**Suit vs High/Low difference:**
- **Suit contracts**: Offsuit = non-trump suits (4 suits minus trump)
- **High/Low contracts**: Offsuit = all 4 suits (no trump concept)

---

### 5. Offsuit Control (2 features)

High-value offsuit cards that may control tricks.

| Feature | Type | Description |
|---------|------|-------------|
| `offsuit_aces` | float | Number of offsuit Aces (0-8) |
| `offsuit_kings` | float | Number of offsuit Kings (0-8) |

**Suit vs High/Low difference:**
- **Suit contracts**: Only non-trump Aces/Kings count
- **High/Low contracts**: All Aces/Kings count (no trump distinction)

---

### 6. Seat Context - Dealer (5 features)

One-hot encoding of dealer position. Exactly one feature is 1.0, others are 0.0.

| Feature | Type | Description |
|---------|------|-------------|
| `is_dealer_seat_0` | float | 1.0 if dealer at seat 0, else 0.0 |
| `is_dealer_seat_1` | float | 1.0 if dealer at seat 1, else 0.0 |
| `is_dealer_seat_2` | float | 1.0 if dealer at seat 2, else 0.0 |
| `is_dealer_seat_3` | float | 1.0 if dealer at seat 3, else 0.0 |
| `dealer_seat_unknown` | float | 1.0 if dealer unknown, else 0.0 |

---

### 7. Seat Context - Leader (5 features)

One-hot encoding of leader (first to play) position. Exactly one feature is 1.0, others are 0.0.

| Feature | Type | Description |
|---------|------|-------------|
| `is_leader_seat_0` | float | 1.0 if leader at seat 0, else 0.0 |
| `is_leader_seat_1` | float | 1.0 if leader at seat 1, else 0.0 |
| `is_leader_seat_2` | float | 1.0 if leader at seat 2, else 0.0 |
| `is_leader_seat_3` | float | 1.0 if leader at seat 3, else 0.0 |
| `leader_seat_unknown` | float | 1.0 if leader unknown, else 0.0 |

---

## Feature Ordering Guarantee

Features are always extracted in the order listed above. This is enforced by:

1. **Explicit insertion order** in `extract_bidless_hand_features()` (Python 3.7+ dicts maintain insertion order)
2. **Canonical name list** provided by `get_feature_names()`
3. **Unit tests** verifying order stability across calls

**Do not rely on dict iteration order from external code.** Always use `get_feature_names()` or `extract_feature_vector()` to ensure correct ordering.

---

## Contract Type Behavior

### Suit Contracts

- `trump_suit` must be specified (e.g., "H", "D", "C", "S")
- Bowers (right/left) are identified and counted as trump
- Offsuit features exclude trump cards
- Trump features are populated based on effective suit

**Example:**
```python
hand = [Card("H", "J"), Card("D", "J"), Card("H", "A"), ...]
features = extract_bidless_hand_features(
    hand, contract_type="suit", trump_suit="H"
)
# Result:
# - has_right_bower = 1.0 (HJ is right bower)
# - has_left_bower = 1.0 (DJ is left bower for H trump)
# - trump_count = 3.0 (HJ + DJ + HA)
```

---

### High Contracts

- No trump suit (set `trump_suit=None`)
- All trump features are 0.0
- All cards are treated as "offsuit"
- Ace is highest rank

**Example:**
```python
features = extract_bidless_hand_features(
    hand, contract_type="high"
)
# Result:
# - trump_count = 0.0
# - has_right_bower = 0.0
# - has_left_bower = 0.0
# - offsuit_aces = (all aces in hand)
```

---

### Low Contracts

- No trump suit (set `trump_suit=None`)
- All trump features are 0.0
- All cards are treated as "offsuit"
- Ten is highest rank, Ace is lowest

**Example:**
```python
features = extract_bidless_hand_features(
    hand, contract_type="low"
)
# Result:
# - trump_count = 0.0
# - has_right_bower = 0.0
# - has_left_bower = 0.0
# - offsuit_aces = (all aces in hand)
```

---

## Usage Examples

### Basic Extraction (Dict)

```python
from bid_euchre.core.cards import Card
from bid_euchre.features.bidless_hand_features import extract_bidless_hand_features

hand = [
    Card("H", "J"),  # Right bower
    Card("H", "A"),
    Card("H", "K"),
    Card("C", "A"),
    Card("C", "K"),
    Card("D", "A"),
    Card("D", "T"),
    Card("S", "Q"),
    Card("S", "T"),
    Card("S", "T"),
]

features = extract_bidless_hand_features(
    hand,
    contract_type="suit",
    trump_suit="H",
    dealer_seat=0,
    leader_seat=1,
)

print(features["trump_count"])        # 3.0 (RB, HA, HK)
print(features["has_right_bower"])    # 1.0
print(features["offsuit_aces"])       # 2.0 (CA, DA)
```

---

### Feature Vector (List)

```python
from bid_euchre.features.bidless_hand_features import extract_feature_vector

values, names = extract_feature_vector(
    hand,
    contract_type="suit",
    trump_suit="H",
    dealer_seat=0,
    leader_seat=1,
)

# Use in scikit-learn, PyTorch, etc.
import numpy as np
X = np.array([values])  # Shape: (1, 31)

# Check feature names
print(names[0])   # "schema_version_marker"
print(names[1])   # "count_aces"
print(len(names)) # 31
```

---

### Get Feature Names Only

```python
from bid_euchre.features.bidless_hand_features import get_feature_names

names = get_feature_names()
print(len(names))  # 31
print(names[:5])   # ["schema_version_marker", "count_aces", "count_kings", ...]
```

---

## Testing

Comprehensive unit tests are provided in `tests/unit/test_bidless_hand_features.py`.

**Test coverage includes:**
- Feature name stability and ordering
- Deterministic output for same input
- Schema version marker presence
- All contract types (suit, high, low)
- Bower identification
- Rank counting
- Trump feature calculation
- Offsuit distribution (voids, singletons, sorted lengths)
- Offsuit control (aces, kings)
- Seat context encoding (dealer, leader, unknown)
- Feature vector consistency with dict
- Edge cases (empty hand, all trump, all jacks, etc.)

**Run tests:**
```bash
pytest tests/unit/test_bidless_hand_features.py -v
```

---

## Design Rationale

### Why Stable Ordering?

Dictionary iteration order became stable in Python 3.7+, but relying on insertion order makes the code fragile to refactoring. By providing `get_feature_names()` as the canonical ordering, we ensure:
- Features can be extracted as numpy arrays with consistent column meaning
- Training and inference use the same feature order
- Feature importance analysis maps correctly to feature names

---

### Why One-Hot Encoding for Seats?

Seat position is categorical, not ordinal. One-hot encoding prevents the model from learning spurious ordinal relationships (e.g., "seat 3 is 3x more important than seat 1").

---

### Why Schema Version Marker?

As models evolve, feature definitions may change (new features added, old ones removed, semantics adjusted). The schema version marker allows:
- Training scripts to validate feature compatibility
- Models to reject incompatible feature vectors
- Forward compatibility planning (e.g., v1 vs v2 extractors)

---

## Future Extensions (Not in v1)

Potential future additions (would require schema v2):
- Trick-by-trick state features (cards played so far)
- Partner's bid information
- Opponent modeling features
- Hand evaluation scores (from `hand_eval.py`)
- Interaction terms (e.g., trump_count × offsuit_aces)

**For v1, we keep it simple and deterministic.**

---

## Related Documentation

- **Hand Evaluation**: `src/bid_euchre/features/hand_eval.py` (bidding-phase features)
- **Card Primitives**: `src/bid_euchre/core/cards.py` (Card, effective_suit, bowers)
- **Rules**: `docs/01_core/RULES.md` (game rules and trump mechanics)
- **Bidding Dataset**: `docs/01_core/BIDDING_DATASET.md` (pre-bidding features)

---

## Changelog

### v1 (Initial Release)
- 31 features covering hand composition, trump strength, offsuit distribution, and seat context
- Deterministic, stable-order extraction
- Support for suit, high, and low contracts
- One-hot encoding for dealer and leader seats
- Schema version marker for forward compatibility
