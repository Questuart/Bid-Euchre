# Bid Euchre JSONL Log Schema

**Schema Version:** 3  
**Format:** JSONL (JSON Lines) - one JSON object per line

## Overview

The game logger produces structured JSONL files for reproducible analysis and future dashboard development.
Each log file contains a sequence of event records, with timestamps and a consistent schema version.

## Log Levels

| Level | Records Produced |
|-------|------------------|
| `none` | No output (default) |
| `hand` | `run_start`, `hand_end`, `run_end` |
| `trick` | All of the above + `trick_end` |

## Event Types

### `run_start`

Emitted once at the beginning of a logging session.

```json
{
  "schema_version": 3,
  "event": "run_start",
  "run_id": "baseline_greedy_42",
  "strategy_id": "greedy",
  "log_level": "hand",
  "timestamp": "2025-12-15T18:00:00.000000"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Schema version for backward compatibility |
| `event` | string | Always `"run_start"` |
| `run_id` | string | Unique identifier for this run |
| `strategy_id` | string | Strategy being used |
| `log_level` | string | Logging level: `"hand"` or `"trick"` |
| `timestamp` | string | ISO 8601 timestamp |

---

### `hand_end`

Emitted at the end of each hand.

```json
{
  "schema_version": 3,
  "event": "hand_end",
  "run_id": "baseline_greedy_42",
  "strategy_id": "greedy",
  "deal_id": 42,
  "seed": 42,
  "contract": "suit",
  "trump": "H",
  "leader": 2,
  "t0": 6,
  "t1": 4,
  "scores": [520, 410, 600, 390],
  "features": [
    {"bowers": 1, "trump_count": 4, "offsuit_aces": 2, "high_offsuit": 1, "rank_sum": 32},
    {"bowers": 0, "trump_count": 3, "offsuit_aces": 1, "high_offsuit": 2, "rank_sum": 28},
    {"bowers": 1, "trump_count": 2, "offsuit_aces": 3, "high_offsuit": 0, "rank_sum": 35},
    {"bowers": 0, "trump_count": 1, "offsuit_aces": 0, "high_offsuit": 3, "rank_sum": 25}
  ],
  "hands": [
    [["H","J"], ["H","K"], ["H","Q"], ["H","A"], ["C","A"], ["D","A"], ["S","T"], ["S","Q"], ["C","T"], ["D","Q"]],
    [["H","T"], ["H","T"], ["C","J"], ["C","K"], ["C","Q"], ["D","K"], ["D","T"], ["S","K"], ["S","A"], ["S","J"]],
    [["C","J"], ["H","J"], ["H","A"], ["C","K"], ["C","T"], ["D","A"], ["D","A"], ["D","Q"], ["S","Q"], ["S","A"]],
    [["H","K"], ["H","Q"], ["C","Q"], ["C","A"], ["D","J"], ["D","K"], ["D","T"], ["D","J"], ["S","K"], ["S","T"]]
  ],
  "timestamp": "2025-12-15T18:00:01.234567"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Schema version |
| `event` | string | Always `"hand_end"` |
| `run_id` | string | Unique identifier for this run |
| `strategy_id` | string | Strategy being used |
| `deal_id` | int | Hand number within this run (0-indexed) |
| `seed` | int\|null | Random seed used (null if unseeded) |
| `contract` | string | Contract type: `"suit"`, `"high"`, or `"low"` |
| `trump` | string\|null | Trump suit (`"C"`, `"D"`, `"H"`, `"S"`) or null for no-trump |
| `leader` | int | Player who led the first trick (0-3) |
| `t0` | int | Tricks won by team 0 (players 0, 2) |
| `t1` | int | Tricks won by team 1 (players 1, 3) |
| `scores` | array\|null | Array of 4 scalar hand scores, one per player (schema v2+) |
| `features` | array | Array of 4 feature dicts, one per player |
| `hands` | array\|null | Array of 4 hands, each card as `[suit, rank]` (schema v3+) |
| `timestamp` | string | ISO 8601 timestamp |

#### Feature Fields

| Field | Type | Description |
|-------|------|-------------|
| `bowers` | int | Number of bowers (0-4 in double deck) |
| `trump_count` | int | Number of trump cards (0-10) |
| `offsuit_aces` | int | Number of non-trump aces (0-6) |
| `high_offsuit` | int | Count of high non-trump cards |
| `rank_sum` | int | Sum of card ranks |

#### Hands Format (Schema v3+)

The `hands` field contains the full dealt hands for all 4 players. Each hand is an array of 10 cards, where each card is represented as a 2-element array `[suit, rank]`:

- **suit**: `"C"`, `"D"`, `"H"`, `"S"` (Clubs, Diamonds, Hearts, Spades)
- **rank**: `"T"`, `"J"`, `"Q"`, `"K"`, `"A"` (Ten, Jack, Queen, King, Ace)

Example:
```json
"hands": [
  [["H","J"], ["H","K"], ["H","Q"], ...],  // Player 0 (10 cards)
  [["C","J"], ["D","K"], ["S","A"], ...],  // Player 1 (10 cards)
  [["H","A"], ["C","K"], ["D","Q"], ...],  // Player 2 (10 cards)
  [["S","T"], ["C","A"], ["D","J"], ...]   // Player 3 (10 cards)
]
```

This format matches the `plays` format used in `trick_end` events for consistency.

---

### `trick_end`

Emitted at the end of each trick (only when log level is `"trick"`).

```json
{
  "schema_version": 1,
  "event": "trick_end",
  "run_id": "baseline_greedy_42",
  "deal_id": 42,
  "trick_num": 3,
  "leader": 1,
  "plays": [[1, "H", "K"], [2, "H", "T"], [3, "S", "A"], [0, "H", "Q"]],
  "winner": 1,
  "timestamp": "2025-12-15T18:00:01.234568"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Schema version |
| `event` | string | Always `"trick_end"` |
| `run_id` | string | Unique identifier for this run |
| `deal_id` | int | Hand number within this run |
| `trick_num` | int | Trick number within hand (0-9) |
| `leader` | int | Player who led this trick (0-3) |
| `plays` | array | Array of `[player_idx, suit, rank]` in play order |
| `winner` | int | Player who won the trick (0-3) |
| `timestamp` | string | ISO 8601 timestamp |

#### Play Format

Each play is a 3-element array: `[player_index, suit, rank]`
- `player_index`: 0-3
- `suit`: `"C"`, `"D"`, `"H"`, `"S"`
- `rank`: `"T"`, `"J"`, `"Q"`, `"K"`, `"A"`

---

### `run_end`

Emitted once at the end of a logging session.

```json
{
  "schema_version": 1,
  "event": "run_end",
  "run_id": "baseline_greedy_42",
  "timestamp": "2025-12-15T18:05:00.000000"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | int | Schema version |
| `event` | string | Always `"run_end"` |
| `run_id` | string | Unique identifier for this run |
| `timestamp` | string | ISO 8601 timestamp |

---

## Usage Examples

### CLI Flags

```bash
# No logging (default)
PYTHONPATH=src python experiments/run_baseline_greedy.py

# Log hand summaries only
PYTHONPATH=src python experiments/run_baseline_greedy.py --log-level hand --log-dir logs

# Log everything (including per-trick details)
PYTHONPATH=src python experiments/run_baseline_greedy.py --log-level trick --log-dir logs
```

### Reading JSONL Files

```python
import json

with open("logs/baseline_greedy_42.jsonl") as f:
    for line in f:
        record = json.loads(line)
        if record["event"] == "hand_end":
            print(f"Hand {record['deal_id']}: T0={record['t0']}, T1={record['t1']}")
```

### Filtering by Event Type

```bash
# Extract only hand_end records
grep '"event":"hand_end"' logs/baseline_greedy_42.jsonl | head -5
```

---

## Schema Versioning

The `schema_version` field ensures backward compatibility:

| Version | Changes |
|---------|---------|
| 1 | Initial schema |
| 2 | Added `scores` field to `hand_end` events (4 scalar hand scores, one per player) |
| 3 | Added `hands` field to `hand_end` events (full hand contents for each player) |

When the schema changes:
1. Bump `schema_version` in `game_logger.py`
2. Document changes in this file
3. Update consumers to handle multiple versions

### Backward Compatibility

- Schema v3 is backward compatible with v1 and v2
- The `scores` field (v2+) is optional and may be `null`
- The `hands` field (v3+) is optional and may be `null`
- Older consumers can ignore fields they don't recognize

---

## File Organization

```
logs/
├── baseline_greedy_42.jsonl      # Hand-level logging
├── baseline_greedy_trick_42.jsonl # Trick-level logging
└── ...
```

Log files are named `{run_id}.jsonl` by default.

