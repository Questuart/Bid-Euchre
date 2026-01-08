# Scoring Contract

This document specifies the scoring/points fields emitted in Bid Euchre experiment results JSON. All definitions are grounded in the current code implementation.

## What Gets Emitted

Results JSON includes the following scoring/points-related fields:

### Always-Present Fields

- **`avg_points_team0`** (float): Average points earned by team 0 (seats 0, 2) across all hands
- **`avg_points_team1`** (float): Average points earned by team 1 (seats 1, 3) across all hands
- **`distribution_points_team0`** (object): Frequency distribution of point values for team 0, keyed by point value
- **`distribution_points_team1`** (object): Frequency distribution of point values for team 1, keyed by point value
- **`bidding_points`** (object): Bidding-specific scoring metrics (see below)

### bidding_points Object (Always Present)

- **`enabled`** (boolean): `true` if any hands had actual bidding activity (`hands_with_bids > 0`), `false` otherwise. Note: Auction mode can be configured but still result in `enabled: false` if all players pass in every hand.
- **`hands_with_bids`** (integer): Count of hands where at least one player placed a bid (did not pass)

#### Conditional Subfields (Present Only When `hands_with_bids > 0`)

- **`avg_bid`** (float): Average bid amount across all hands with bidding
- **`bid_distribution`** (object): Frequency distribution of bid amounts, keyed by bid value
- **`make_rate`** (float): Fraction of bidding hands where the bid was made (0.0 to 1.0)
- **`set_rate`** (float): Fraction of bidding hands where the bid was set (0.0 to 1.0)

## Definitions and Sign Conventions

Point calculations follow euchre scoring rules as implemented in `src/bid_euchre/scoring.py`:

**Scenario types:**
- **Fixed contract** (no auction): `contract_type` is a fixed value ("suit", "high", or "low") specified in configuration. All hands play with this predetermined contract.
- **Auction mode**: `contract_type` is `null` in configuration. Each hand runs a bidding phase to determine the contract and bidder.

**Scoring rules (from `src/bid_euchre/scoring.py::compute_points`):**
- **Fixed contract case**: Both teams receive their trick count as points
- **Bid made case**: Bid team receives their trick count; non-bid team receives their trick count
- **Bid set case**: Bid team receives negative bid amount (penalty); non-bid team receives their trick count

Sign conventions:
- Positive points: Tricks taken (both teams) or successful bid completion
- Negative points: Failed bid penalty (only applied to bid team when set)
- Zero points: Possible but rare (team takes 0 tricks)

## Where Computed/Emitted

- **Point calculation per hand**: `src/bid_euchre/scoring.py::compute_points`
- **Aggregation and distribution tracking**: `src/bid_euchre/sim/simulation.py::run_scenario`
- **bidding_points object assembly**: `src/bid_euchre/sim/simulation.py::run_scenario`
- **Results JSON emission**: `src/bid_euchre/sim/simulation.py::run_scenario` (return statement)

## Notes on Determinism/Stability

- **Per-hand scoring**: Deterministic given fixed seed (same hand always produces same point outcome)
- **Aggregate statistics** (`avg_points_*`, `distribution_points_*`): Vary with sample size but converge to true distribution as `n_per` increases
- **Bidding metrics**: Conditional subfields appear only when `hands_with_bids > 0`. Auction mode (`contract_type: null`) enables bidding opportunity, but actual bidding activity determines metric presence.
- **Backward compatibility**: All fields follow existing JSON schema contracts in `docs/01_core/DATA_CONTRACT.md`
