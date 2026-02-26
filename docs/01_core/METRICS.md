# Metrics Contract v1

This document defines the authoritative metrics contract for bid euchre experiments and analysis.

## Definitions

### Hand
A single deal of cards played to completion between two teams of 2 players each. A hand consists of:
- Card dealing and bidding (if applicable)
- Trick play until all 10 tricks are taken
- Scoring based on final trick counts

### Match
A collection of hands played between the same two strategies/teams under identical conditions (contract type, trump suit, etc.).

### Run
A single execution of an experiment configuration that produces results for one or more matches.

### Config
A YAML configuration file defining an experiment setup, including strategies, scenarios, and parameters.

### Suite
A collection of related configs that are run together, with aggregated results and rollup reporting.

## Emitted vs Rollup-computed vs Planned Metrics

### Emitted in Results JSON
These keys are directly present in results JSON files at `data/runs/<run_id>/results/<strategy>/<scenario>.json`:

**Tricks (Always emitted):**
- `avg_team0`: Mean tricks for team 0
- `avg_team1`: Mean tricks for team 1
- `distribution_team0`: Count of hands by tricks taken (0-10)

**Win Rates (Always emitted):**
- `win_rate_team0`: Weighted win rate for team 0 = (count(tricks ≥ 6) + 0.5 × count(tricks = 5)) / total_hands
- `win_rate_team1`: Weighted win rate for team 1 = (count(tricks ≥ 6) + 0.5 × count(tricks = 5)) / total_hands
- `tie_rate`: Proportion of hands with exactly 5 tricks (tie, None if hands=0)

**Note:** Ties (exactly 5 tricks) contribute 0.5 to each team's win rate, ensuring win_rate_team0 + win_rate_team1 = 1.0

**Points (Only when bidding occurs):**
- `avg_points_team0`: Mean points for team 0 (when bidding enabled)
- `avg_points_team1`: Mean points for team 1 (when bidding enabled)
- `distribution_points_team0`: Count of hands by points scored
- `distribution_points_team1`: Count of hands by points scored

### Rollup-computed Fields
These are computed by aggregation scripts from emitted keys:

**Tricks Aggregation:**
- `avg_tricks`: Weighted average of `avg_team0` across all configs (weighted by hands)

### Drift v1 Contract (Tricks-Only)
Drift v1 compares the `avg_tricks_team0` field from rollup summary against expected values in `data/fixtures/baseline_full_expected.json`. This is the primary regression signal for tricks-based strategies.

## Auction Metrics

When bidding is enabled (`contract_type: null` in scenario config), the evaluator emits the following metrics. The primary series is `bidder_team_points` from `compute_points()`.

| Metric | Definition |
|--------|-----------|
| `expected_points` | Mean of `bidder_team_points` across hands where an auction winner exists |
| `expected_points_per_deal` | Mean of `bidder_team_points` across all deals (0 for all-pass redeals) |
| `make_rate` | Fraction of auction-won hands where `bidder_team_points >= 0` |
| `bid_rate` | Fraction of deals with an auction winner (i.e., not all-pass) |
| `pass_rate` | Fraction of deals that resulted in all-pass redeals |
| `cvar_5` | Mean of the worst 5% of `bidder_team_points` values (conditional value at risk) |
| `downside_variance` | Variance of negative `bidder_team_points` values (downside risk) |

**Source:** `src/bid_euchre/reporting/evaluator.py`

## Where to Find These Fields

### Results JSON Files
Located at: `data/runs/<run_id>/results/<strategy>/<scenario>.json`

Example from simulation results:
```json
{
  "hands": 50,
  "avg_team0": 4.98,
  "avg_team1": 5.02,
  "distribution_team0": {"0": 0, "1": 0, "2": 1, "3": 2, "4": 8, "5": 15, "6": 16, "7": 6, "8": 2, "9": 0, "10": 0},
  "win_rate_team0": 0.52,
  "win_rate_team1": 0.48,
  "tie_rate": 0.0
}
```

### Rollup Aggregation
Suite rollups compute deltas from individual results files using `scripts/run_suite.py`.

### Delta Directionality

All delta metrics follow the convention: **team0 - team1**
- Positive values indicate team0 advantage
- Negative values indicate team1 advantage
- Zero indicates parity

### Validation

Results JSON keys verified from:
- Code: `src/bid_euchre/sim/simulation.py` lines 265-270 (simulate_many_hands function return type)
- Rollup computation: `scripts/run_suite.py` lines 142-213 (compute_suite_metrics function)
- Drift comparison: `scripts/compare_rollup.py` lines 153-196 (drift detection logic)

## Scoring Fields

This section specifies the scoring/points fields emitted in Bid Euchre experiment results JSON. All definitions are grounded in the current code implementation.

### Always-Present Scoring Fields

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

### Scoring Definitions and Sign Conventions

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

### Where Scoring Is Computed/Emitted

- **Point calculation per hand**: `src/bid_euchre/scoring.py::compute_points`
- **Aggregation and distribution tracking**: `src/bid_euchre/sim/simulation.py::run_scenario`
- **bidding_points object assembly**: `src/bid_euchre/sim/simulation.py::run_scenario`
- **Results JSON emission**: `src/bid_euchre/sim/simulation.py::run_scenario` (return statement)

### Scoring Determinism/Stability Notes

- **Per-hand scoring**: Deterministic given fixed seed (same hand always produces same point outcome)
- **Aggregate statistics** (`avg_points_*`, `distribution_points_*`): Vary with sample size but converge to true distribution as `n_per` increases
- **Bidding metrics**: Conditional subfields appear only when `hands_with_bids > 0`. Auction mode (`contract_type: null`) enables bidding opportunity, but actual bidding activity determines metric presence.
- **Backward compatibility**: All fields follow existing JSON schema contracts in `docs/01_core/DATA_CONTRACT.md`
