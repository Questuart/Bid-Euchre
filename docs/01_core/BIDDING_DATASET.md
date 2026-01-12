# Bidding Dataset Contract (v1)

## Purpose

This document defines the schema for bidding decision datasets produced by bid-euchre experiments. These datasets capture the inputs and outputs of bidding decisions made during gameplay, enabling analysis and modeling of bidding strategies.

## Row granularity

One row per player per hand at bid decision time. Each row represents a single bidding decision opportunity.

## Keys

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

## Attempted vs Effective Bids

The dataset records both attempted (proposed) and effective (accepted) bids to distinguish between legal and illegal bidding behavior.

### Attempted Bids (what was proposed)

### `attempted_bid_n` (int)
Number of tricks attempted to bid (0-10).
- 0 = pass

### `attempted_bid_contract` (str|null)
Contract type string for attempted bid:
- `"suit"` for suit contracts
- `"HIGH"` for high no-trump
- `"LOW"` for low no-trump
- `null` if attempted_bid_n = 0 (pass)

### `attempted_bid_trump_suit` (str|null)
Trump suit for attempted suit contracts:
- `"C"`, `"D"`, `"H"`, `"S"` for Clubs, Diamonds, Hearts, Spades
- `null` for non-suit contracts or passes

### Effective Bids (what actually happened)

### `effective_bid_n` (int)
Number of tricks effectively bid (0-10).
- 0 = pass (either actual pass or illegal bid)

### `effective_bid_contract` (str|null)
Effective contract type string:
- `"suit"` for suit contracts
- `"HIGH"` for high no-trump
- `"LOW"` for low no-trump
- `null` if effective_bid_n = 0

### `effective_bid_trump_suit` (str|null)
Effective trump suit for suit contracts:
- `"C"`, `"D"`, `"H"`, `"S"` for Clubs, Diamonds, Hearts, Spades
- `null` for non-suit contracts or passes

### `is_legal_raise` (bool)
Whether the attempted bid was a legal raise:
- `true` if attempted_bid_n > current_high_bid or attempted_bid_n = 0 (pass)
- `false` if attempted_bid_n <= current_high_bid (illegal raise, becomes pass)

### Bid Resolution Rules
- **Pass**: attempted_bid_n = 0 → effective_bid_n = 0, is_legal_raise = true
- **Illegal raise**: attempted_bid_n <= current_high_bid → effective_bid_n = 0, is_legal_raise = false
- **Legal raise**: attempted_bid_n > current_high_bid → attempted == effective, is_legal_raise = true

## Auction Outcome Metadata (debug-only)

These columns are for debugging redeals and are NOT intended for v1 training inputs.

### `auction_outcome` (str)
Auction result:
- `"won"` - Auction succeeded with a winning bid
- `"all_pass_redeal"` - All players passed, hand redealt

### `winning_seat` (int|null)
Seat that won the auction (0-3, null for redeals).

### `winning_bid_n` (int|null)
Winning bid number (1-10, null for redeals).

### `winning_bid_contract` (str|null)
Winning bid contract ("suit", "HIGH", "LOW", null for redeals).

## Legacy Labels (deprecated)

### `bid_n` (int)
**DEPRECATED**: Use `effective_bid_n` instead.
Number of tricks bid (0-10).
- 0 = pass

### `bid_contract` (str|null)
**DEPRECATED**: Use `effective_bid_contract` instead.
Contract type string:
- `"suit"` for suit contracts (requires `trump_suit`)
- `"high"` for high no-trump
- `"low"` for low no-trump
- `null` if bid_n = 0 (pass)

### `bid_trump_suit` (str|null)
**DEPRECATED**: Use `effective_bid_trump_suit` instead.
Trump suit for suit contracts:
- `"C"`, `"D"`, `"H"`, `"S"` for Clubs, Diamonds, Hearts, Spades
- `null` for non-suit contracts or passes

## Determinism

Dataset generation must be fully deterministic when a seed is provided to the experiment runner. Re-running the same seeded experiment must produce **byte-identical** Parquet files, even when run_id differs.

The `run_id` is stored in Parquet key-value metadata rather than row data to ensure identical output across runs with different identifiers.

## CLI Usage

Emit bidding datasets during experiments with:

```bash
# Default: emit Parquet (canonical) + JSONL (debug)
python experiments/run_experiment.py --config <config> --emit-bidding-dataset

# Emit only JSONL (debug format)
python experiments/run_experiment.py --config <config> --emit-bidding-dataset --bidding-dataset-format jsonl
```

## File location

By default, bidding datasets are emitted in Parquet format with JSONL available for debugging:

- Canonical: `data/runs/<run_id>/datasets/bidding.parquet` (always written when format=parquet, byte-identical deterministic)
- Debug: `data/runs/<run_id>/datasets/bidding.jsonl` (written when format=parquet, includes run_id for inspection)
- Metadata: `data/runs/<run_id>/datasets/bidding_meta.json` (run_id and schema versions)

The `run_id` is stored in:
- Parquet: Key-value metadata (not in row data, ensuring byte-identical output)
- JSONL: Row data (for debugging convenience)
- Meta JSON: Top-level field

## Forward compatibility

Future versions may add:
- Bidding history (previous bids in the round)
- Partner identity information
- Additional feature versions

These additions will be tracked with schema versioning.
