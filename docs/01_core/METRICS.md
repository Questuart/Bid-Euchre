# Metrics Contract v1

This document defines the authoritative metrics contract for bid euchre experiments and analysis.

## Definitions

### Hand
A single deal of cards played to completion between two teams of 2 players each. A hand consists of:
- Card dealing and bidding (if applicable)
- Trick play until all 5 tricks are taken
- Scoring based on final trick counts

### Match
A collection of hands played between the same two strategies/teams under identical conditions (contract type, trump suit, etc.).

### Run
A single execution of an experiment configuration that produces results for one or more matches.

### Config
A YAML configuration file defining an experiment setup, including strategies, scenarios, and parameters.

### Suite
A collection of related configs that are run together, with aggregated results and rollup reporting.

## Required Metrics for Non-Auction Matchups

### Win Rate (Planned - Not Yet Emitted)
**Definition**: Proportion of hands where a team wins (takes ≥6 tricks).

**Computation**: `n_wins / n_total_hands`

**Expected Range**: [0.0, 1.0]

**Keys**: `win_rate`, `push_rate`, `loss_rate` (with confidence intervals)

**Status**: Planned for future implementation. Currently not emitted in results JSON.

### Points
**Definition**: Average points scored per hand under euchre point-based scoring rules.

**Computation**: Mean of points across all simulated hands.

**Expected Range**: [-10.0, +10.0] (negative values possible for sets)

**Keys**:
- `avg_points_team0`: Mean points for team 0
- `avg_points_team1`: Mean points for team 1
- `avg_points_delta`: team0 - team1 (positive = team0 advantage)

### Tricks
**Definition**: Average tricks taken per hand.

**Computation**: Mean of trick counts across all simulated hands.

**Expected Range**: [0.0, 10.0]

**Keys**:
- `avg_tricks_team0`: Mean tricks for team 0
- `avg_tricks_team1`: Mean tricks for team 1
- `avg_tricks_delta`: team0 - team1 (positive = team0 advantage)

## Auction Metrics (Optional)

Auction/bidding metrics are optional and clearly labeled as such until a bidding policy is implemented.

When bidding is enabled, additional metrics will include:
- Make rate: Proportion of hands where bidding team meets or exceeds their bid
- Set rate: Proportion of hands where bidding team falls short of their bid
- Average bid values

## Source of Truth

### Results JSON Keys vs Rollup Computed Fields

**Results JSON** (primary source):
- `avg_points_team0`, `avg_points_team1` - Directly computed from simulation
- `avg_tricks_team0`, `avg_tricks_team1` - Directly computed from simulation (stored as `avg_team0`, `avg_team1` in current code)

**Rollup Computed Fields**:
- `avg_points_delta` - Computed as `avg_points_team0 - avg_points_team1`
- `avg_tricks_delta` - Computed as `avg_tricks_team0 - avg_tricks_team1`
- `win_rate` - Planned: computed from trick distributions using ≥6 tricks threshold

### Delta Directionality

All delta metrics follow the convention: **team0 - team1**
- Positive values indicate team0 advantage
- Negative values indicate team1 advantage
- Zero indicates parity

### Validation

Current results JSON example (from `data/fixtures/baseline_tiny/expected_metrics_seed42_nper3.json`):
- Top-level keys: `['suite_name', 'seed', 'n_per', 'configs']`
- No example JSON found with individual metric keys; contract based on code search in `src/bid_euchre/sim/simulation.py` and `src/bid_euchre/reporting/metrics.py`