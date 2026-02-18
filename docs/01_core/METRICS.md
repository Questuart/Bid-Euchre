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

## Auction Metrics (Optional)

Auction/bidding metrics are optional and clearly labeled as such until a bidding policy is implemented.

When bidding is enabled, additional metrics will include:
- Make rate: Proportion of hands where bidding team meets or exceeds their bid
- Set rate: Proportion of hands where bidding team falls short of their bid
- Average bid values

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
