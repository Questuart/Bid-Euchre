# Bidless Dataset Contract (v1)

## Purpose

This document defines the schema for bidless dataset collections produced during hand-value training simulations. These datasets capture hand strength/value data for declared contracts (no auction) to enable training of ML models for hand evaluation.

## Row granularity

One row per hand per player per declared contract context. Each row represents a single hand evaluation opportunity.

## Keys

- `hand_id` (int): Unique hand identifier within the run
- `seat` (int): Player seat position (0-3)
- `dealer_seat` (int): Dealer seat position (0-3)

## Context

### `deal_id` (int|null)
Optional deal identifier for reproducibility and debugging.

## Inputs (features)

### `hand_cards` (list[str])
Raw hand representation as list of card strings (e.g., `["AS", "KD", "QH", "JC", "TD"]`).
- Cards represented as rank + suit (e.g., "A♠" = "AS", "10♣" = "TC")
- Order preserved from the game state (not sorted)

### `hand_features` (dict)
Derived feature vector from `get_hand_features()` in `src/bid_euchre/features/hand_eval.py`.
- Schema version: `hand_feature_schema_version` = 1
- 40+ numeric features covering trump strength, offsuit control, distribution, and high/low specific features
- All values are integers or floats

## Contract Context

### `contract_type` (str)
Declared contract type:
- `"suit"` for suit contracts (requires `trump_suit`)
- `"HIGH"` for high no-trump
- `"LOW"` for low no-trump

### `trump_suit` (str|null)
Trump suit for suit contracts:
- `"C"`, `"D"`, `"H"`, `"S"` for Clubs, Diamonds, Hearts, Spades
- `null` for HIGH/LOW contracts

## Hand Value

The `hand_features` dict includes a computed `hand_value` field representing the hand's strength score for the given contract context.

## Determinism

Dataset generation must be fully deterministic when a seed is provided to the simulation. Re-running the same seeded simulation must produce **equivalent** Parquet files with identical row data, even when run_id differs.

The `run_id` is stored in Parquet key-value metadata rather than row data. However, Parquet files may not be byte-identical due to metadata timestamps and other implementation details.

## CLI Usage

Emit bidless datasets during simulations with:

```bash
# Default: emit Parquet (canonical) + JSONL (debug)
python experiments/run_experiment.py --config <config> --emit-bidless-dataset

# Emit only JSONL (debug format)
python experiments/run_experiment.py --config <config> --emit-bidless-dataset --bidless-dataset-format jsonl
```

## File location

By default, bidless datasets are emitted in Parquet format with JSONL available for debugging:

- Canonical: `data/runs/<run_id>/datasets/bidless.parquet` (always written when format=parquet, deterministic row data)
- Debug: `data/runs/<run_id>/datasets/bidless.jsonl` (written when format=parquet, includes run_id for inspection)
- Metadata: `data/runs/<run_id>/datasets/bidless_meta.json` (run_id and schema versions)

The `run_id` is stored in:
- Parquet: Key-value metadata (not in row data, ensuring byte-identical output)
- JSONL: Row data (for debugging convenience)
- Meta JSON: Top-level field

## Forward compatibility

Future versions may add:
- Additional hand feature schema versions
- Contract-specific feature subsets
- Multi-hand evaluation contexts

These additions will be tracked with schema versioning.
