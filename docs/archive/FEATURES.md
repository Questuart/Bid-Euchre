# Hand Features Documentation

**Last Updated**: December 17, 2025
**Total Features**: 40

---

## Overview

The `get_hand_features()` function extracts 40 comprehensive features from each hand, covering trump strength, offsuit control, distribution, and contract-specific metrics.

---

## Feature Categories

### 1. Legacy Features (Backward Compatible)

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `bowers` | int | 0-4 | Total bowers (RB + LB) |
| `trump_count` | int | 0-10 | Total trump cards (suit contracts only) |
| `offsuit_aces` | int | 0-6 | Aces in non-trump suits |
| `high_offsuit` | int | 0-10 | High offsuit cards (K, Q, J, T) |
| `rank_sum` | int | 10-50 | Sum of rank strengths (+1 each) |

---

### 2. Trump Features (Suit Contracts Only)

#### Individual Trump Rank Counts

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `trump_rb_count` | int | 0-2 | Right bowers |
| `trump_lb_count` | int | 0-2 | Left bowers |
| `trump_ace_count` | int | 0-2 | Trump aces |
| `trump_king_count` | int | 0-2 | Trump kings |
| `trump_queen_count` | int | 0-2 | Trump queens |
| `trump_ten_count` | int | 0-2 | Trump tens |

#### Trump Strength Metrics

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `top_trump_count` | int | 0-6 | RB + LB + Ace |
| `highest_trump_rank` | int | 0-6 | Best trump (6=RB, 5=LB, 4=A, 3=K, 2=Q, 1=T) |
| `second_highest_trump_rank` | int | 0-6 | Second-best trump rank |
| `third_highest_trump_rank` | int | 0-6 | Third-best trump rank |
| `trump_power_sum` | int | 0-60 | Sum of all trump rank values |
| `trump_power_avg` | float | 0.0-6.0 | Average trump rank strength |
| `trump_duplicate_pairs` | int | 0-3 | Count of ranks with exactly 2 cards |
| `top_trump_sum` | int | 0-6 | Bowers + Aces |

**Trump Rank Scale** (Suit Contracts):
- Right Bower (RB) = 6
- Left Bower (LB) = 5
- Ace (A) = 4
- King (K) = 3
- Queen (Q) = 2
- Ten (T) = 1

---

### 3. Offsuit Control Features

#### Offsuit Rank Counts

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `offsuit_king_count_total` | int | 0-6 | Total offsuit kings |
| `offsuit_queen_count_total` | int | 0-6 | Total offsuit queens |

#### Offsuit Suit Quality

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `offsuit_suits_with_ace` | int | 0-4 | Suits with at least 1 ace |
| `offsuit_suits_with_double_ace` | int | 0-4 | Suits with exactly 2 aces |
| `offsuit_suits_with_ace_and_king` | int | 0-4 | Suits with ace(s) and king(s) |

---

### 4. Distribution Features

#### Suit Lengths

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `void_count` | int | 0-4 | Number of suits with 0 cards |
| `max_suit_len` | int | 0-10 | Longest suit |
| `second_suit_len` | int | 0-10 | Second-longest suit |
| `third_suit_len` | int | 0-10 | Third-longest suit |
| `fourth_suit_len` | int | 0-10 | Shortest suit |
| `num_singletons` | int | 0-4 | Suits with exactly 1 card |
| `num_doubletons` | int | 0-4 | Suits with exactly 2 cards |

#### Offsuit Details

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `offsuit_tens_count` | int | 0-8 | Total offsuit tens |
| `offsuit_length_3plus_count` | int | 0-4 | Offsuit suits with 3+ cards |
| `offsuit_best_rank_sum` | int | 0-50 | Rank sum of best offsuit suit |
| `offsuit_secondbest_rank_sum` | int | 0-50 | Rank sum of second-best offsuit suit |

---

### 5. High/Low Contract Features

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `high_card_count` | int | 0-8 | Total aces + kings |
| `low_card_count` | int | 0-8 | Total jacks + tens |
| `double_ten_jack_count` | int | 0-4 | Suits with 2 tens AND 1+ jack |

---

### 6. Interaction Features

| Feature | Type | Range | Description |
|---------|------|-------|-------------|
| `trump_count_x_void_count` | int | 0-40 | Trump count × void count (suit only) |
| `trump_count_x_offsuit_ace` | int | 0-60 | Trump count × offsuit aces (suit only) |

---

## Usage

### Basic Feature Extraction

```python
from bid_euchre.features.hand_eval import get_hand_features
from bid_euchre.core.cards import Card

hand = [
    Card('H', 'J'),  # Right bower (if trump=H)
    Card('H', 'A'),
    # ... more cards
]

# Suit contract
features = get_hand_features(hand, 'suit', 'H')
print(f"Trump count: {features['trump_count']}")
print(f"Right bowers: {features['trump_rb_count']}")

# High/Low contract
features = get_hand_features(hand, 'high', None)
print(f"High cards: {features['high_card_count']}")
```

### In Simulations

Features are automatically extracted for all 4 players during simulation:

```python
from bid_euchre.sim.simulation import simulate_many_hands

results = simulate_many_hands(
    n=1000,
    contract_type='suit',
    trump_suit='H',
    seed=42
)

# Features are logged to JSONL files if logger is enabled
```

---

## Feature Design Principles

### 1. Completeness
- Cover all aspects: trump, offsuit, distribution
- Support all contract types: suit, high, low

### 2. Independence
- Each feature captures distinct information
- Minimal redundancy (except backward compatibility)

### 3. Interpretability
- Clear naming conventions
- Documented ranges and meanings
- Suitable for ML feature importance analysis

### 4. Performance
- All features computed in single pass
- ~3 microseconds per hand
- Negligible overhead (<0.5% of simulation time)

---

## Contract-Specific Behavior

### Suit Contracts
- All trump features are meaningful (non-zero)
- Offsuit excludes trump suit and left bower
- Interaction terms are computed

### High/Low Contracts
- All trump features are zero
- All cards treated as offsuit
- Interaction terms are zero (by design)
- Distribution features apply to all 4 suits

---

## Backward Compatibility

The 5 legacy features remain unchanged:
- `bowers`
- `trump_count`
- `offsuit_aces`
- `high_offsuit`
- `rank_sum`

All existing code continues to work. New features are additive.

---

## Future Extensions

Potential additions (not yet implemented):
- Bidding-specific features
- Positional features (seat, dealer)
- Partner/opponent modeling features
- Trick-level dynamic features

---

## Performance

**Benchmark** (100k hands):
```
Feature extraction: 2.8 μs per hand
Full simulation: ~100 μs per hand
Feature overhead: <3% of total time
```

**Memory**: O(1) per hand (features discarded after logging)

---

## See Also

- `src/bid_euchre/features/hand_eval.py` - Implementation
- `docs/schemas/hand_record.md` - Log format
- `docs/HAND_EVAL.md` - Hand evaluation overview
- `tests/test_cards.py` - Feature tests
