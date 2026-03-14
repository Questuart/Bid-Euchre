# Feature Registry

**Schema version:** v7
**Feature count:** 39
**Source:** `src/bid_euchre/features/hand_eval.py` (`get_hand_features()`)
**Last updated:** 2026-03-04 (R0 canonical v2 freeze)

This registry documents every feature extracted from a 10-card Bid Euchre hand.
Features are computed per hand, per candidate contract (suit/high/low), and serve
as inputs to the OLSa and OLSa_Full bidding models.

---

## Contract Type Key

- **suit** — Suit contract with a trump suit and bowers (RB, LB).
- **high** — No-trump contract where Ace is high (A > K > Q > J > T).
- **low** — No-trump contract where Ten is high (T > J > Q > K > A).

For high/low contracts, all cards are treated as "offsuit" (no trump partition).
Trump-specific features are zero-filled for high/low contracts.

---

## Feature Catalog

### Trump Strength (suit contracts only)

These features describe the strength of the trump holding. All are zero for
high/low contracts because there is no trump suit.

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 1 | `bowers` | int | Count of bowers held (right + left, 0-2) | suit |
| 2 | `trump_count` | int | Total trump cards including bowers (0-10) | suit |
| 3 | `trump_rb_count` | int | Right bowers held (0-2) | suit |
| 4 | `trump_lb_count` | int | Left bowers held (0-2) | suit |
| 5 | `trump_ace_count` | int | Trump aces held (0-2) | suit |
| 6 | `trump_king_count` | int | Trump kings held (0-2) | suit |
| 7 | `trump_queen_count` | int | Trump queens held (0-2) | suit |
| 8 | `trump_ten_count` | int | Trump tens held (0-2) | suit |
| 9 | `highest_trump_rank` | int | Rank value of highest trump (6=RB, 5=LB, 4=A, 3=K, 2=Q, 1=T, 0=none) | suit |
| 10 | `second_highest_trump_rank` | int | Rank value of second-highest trump (same scale, 0 if <2 trump) | suit |
| 11 | `third_highest_trump_rank` | int | Rank value of third-highest trump (same scale, 0 if <3 trump) | suit |
| 12 | `trump_power_sum` | int | Sum of all trump rank values (higher = stronger trump holding) | suit |
| 13 | `trump_duplicate_pairs` | int | Count of trump ranks where both copies are held (0-6) | suit |

### Offsuit Control

These features describe the quality of non-trump holdings. For high/low contracts,
all cards are classified as offsuit, so these features capture the entire hand.

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 14 | `offsuit_aces` | int | Count of offsuit aces (0-6 suit, 0-8 high/low) | suit, high, low |
| 15 | `offsuit_non_ace_count` | int | Count of offsuit non-ace cards (K, Q, J, T) | suit, high, low |
| 16 | `offsuit_king_count_total` | int | Total offsuit kings across all suits | suit, high, low |
| 17 | `offsuit_queen_count_total` | int | Total offsuit queens across all suits | suit, high, low |
| 18 | `offsuit_suits_with_ace` | int | Number of offsuit suits containing at least one ace (0-3 suit, 0-4 high/low) | suit, high, low |
| 19 | `offsuit_suits_with_double_ace` | int | Number of offsuit suits containing both aces (0-3 suit, 0-4 high/low) | suit, high, low |
| 20 | `offsuit_suits_with_ace_and_king` | int | Number of offsuit suits with ace + king (strong control) | suit, high, low |

### Distribution

These features describe suit-length distribution. For suit contracts, suit lengths
are computed over offsuit cards only (the 4 natural suits, with trump cards
excluded from their natural suit). For high/low, all 4 suits are used.

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 21 | `void_count` | int | Number of void suits (length 0) in offsuit | suit, high, low |
| 22 | `max_suit_len` | int | Length of longest offsuit suit | suit, high, low |
| 23 | `second_suit_len` | int | Length of second-longest offsuit suit | suit, high, low |
| 24 | `third_suit_len` | int | Length of third-longest offsuit suit | suit, high, low |
| 25 | `fourth_suit_len` | int | Length of shortest offsuit suit | suit, high, low |
| 26 | `num_singletons` | int | Number of singleton suits (length 1) in offsuit | suit, high, low |
| 27 | `num_doubletons` | int | Number of doubleton suits (length 2) in offsuit | suit, high, low |
| 28 | `offsuit_tens_count` | int | Total offsuit tens across all suits | suit, high, low |
| 29 | `offsuit_length_3plus_count` | int | Number of offsuit suits with 3+ cards | suit, high, low |
| 30 | `offsuit_best_rank_sum` | int | Rank-strength sum of strongest offsuit suit (rank_strength+1 per card) | suit, high, low |
| 31 | `offsuit_secondbest_rank_sum` | int | Rank-strength sum of second-strongest offsuit suit | suit, high, low |

### High/Low Specific

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 32 | `double_ten_jack_count` | int | Number of suits with both tens AND at least one jack | suit, high, low |
| 33 | `high_card_count` | int | Count of aces + kings in hand (regardless of trump/offsuit) | suit, high, low |
| 34 | `low_card_count` | int | Count of jacks + tens in hand (regardless of trump/offsuit) | suit, high, low |

### Interaction Terms

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 35 | `trump_count_x_void_count` | int | trump_count * void_count (ruffing potential; 0 for high/low) | suit |
| 36 | `trump_count_x_offsuit_ace` | int | trump_count * offsuit_aces (trump length + side tricks; 0 for high/low) | suit |

### Composite Score

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 37 | `hand_value` | int | Scalar hand score (uniform rank weighting). Suit: RB=120, LB=110, trump A=100..T=60, offsuit A=50..T=10. High/Low: (rank_strength+1)*10. | suit, high, low |

### Bridge-Inspired Features

| # | Feature | Type | Description | Contracts |
|---|---------|------|-------------|-----------|
| 38 | `losing_tricks_count` | int | Losing Tricks Count adapted for double-deck. Per-suit: honors missing from top-N (N=min(suit_len,3)). Suit trump honors: RB, LB, A. Suit offsuit / high: A, K, Q. Low: T, J, Q. Voids contribute 0 losers. | suit, high, low |
| 39 | `quick_tricks` | float | Quick Tricks using double-deck chain rule. Per-rank: 2 copies=+2.0 continue, 1 copy=+1.0 stop, 0=stop. Suit voids contribute +1.0 (ruff). High/low voids contribute 0. | suit, high, low |

---

## R0 Model Arm Feature Sets

### Constrained Arm (OLSa) — 3/1/1 locked features

The constrained arm uses a minimal, interpretable feature set locked at R0.
Defined in `src/bid_euchre/models/train_olsa.py`.

| Contract | Features |
|----------|----------|
| suit | `bowers`, `trump_count`, `offsuit_aces` |
| high | `offsuit_aces` |
| low | `offsuit_tens_count` |

### Full Arm (OLSa_Full) — forward-selected features

The full arm uses forward selection with GroupKFold cross-validation to choose
from all 39 available features. The selected set changes per rung as training
data and feature availability evolve.

**R0 selected features:**

| Contract | Features |
|----------|----------|
| suit | `hand_value`, `quick_tricks`, `low_card_count` |
| high | `offsuit_non_ace_count`, `offsuit_best_rank_sum` |
| low | `offsuit_non_ace_count`, `offsuit_best_rank_sum` |

---

## Schema History

| Version | Features | Changes |
|---------|----------|---------|
| v7 (current) | 39 | Stable since R0 v2. Renamed `high_offsuit` to `offsuit_non_ace_count`. |

---

## R1 Planned Changes

R1 is expected to add partner context features (e.g., partner's bid level,
partner's contract choice) and potentially positional features. These are planned
but not yet implemented. The feature count will increase and the schema version
will bump accordingly.

See `plans/archive/pre_v1/r1_master_plan.md` for the R1 feature enrichment roadmap.
