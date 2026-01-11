# Bidding Dataset Contract (v1)

## Purpose

This document defines the schema for bidding decision datasets produced by bid-euchre experiments. These datasets capture the inputs and outputs of bidding decisions made during gameplay, enabling analysis and modeling of bidding strategies.

## Row granularity

One row per player per hand at bid decision time. Each row represents a single bidding decision opportunity.

## Keys

- `run_id` (str): Unique run identifier (directory name under `data/runs/`)
- `hand_id` (str): Unique hand identifier within the run
- `seat` (int): Player seat position (0-3)
- `dealer_seat` (int): Dealer seat position (0-3)

## Inputs (features)

### `hand_cards` (list[str])
Raw hand representation as list of card strings (e.g., `["AS", "KD", "QH", "JC", "TD"]`).
- Cards represented as rank + suit (e.g., "A♠" = "AS", "10♣" = "TC")
- Sorted alphabetically for consistency

### `hand_features` (dict)
Derived feature vector from `get_hand_features()` in `src/bid_euchre/features/hand_eval.py`.
- Schema version: `hand_feature_schema_version` = 1
- 40+ numeric features covering trump strength, offsuit control, distribution, and high/low specific features
- All values are integers or floats

### `current_high_bid` (int)
The highest bid amount so far in this bidding round (0-10).

## Labels

### `bid_n` (int)
Number of tricks bid (0-10).
- 0 = pass

### `bid_contract` (str|null)
Contract type string:
- `"suit"` for suit contracts (requires `trump_suit`)
- `"high"` for high no-trump
- `"low"` for low no-trump
- `null` if bid_n = 0 (pass)

### `bid_trump_suit` (str|null)
Trump suit for suit contracts:
- `"C"`, `"D"`, `"H"`, `"S"` for Clubs, Diamonds, Hearts, Spades
- `null` for non-suit contracts or passes

## Determinism

Dataset generation must be fully deterministic when a seed is provided to the experiment runner. Re-running the same seeded experiment must produce identical bidding datasets.

## File location

- Primary: `data/runs/<run_id>/datasets/bidding.parquet`
- Debug: `data/runs/<run_id>/datasets/bidding.jsonl` (optional, for inspection)

## Forward compatibility

Future versions may add:
- Bidding history (previous bids in the round)
- Partner identity information
- Additional feature versions

These additions will be tracked with schema versioning.