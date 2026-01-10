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

## Emitted vs Rollup-computed vs Planned Metrics

### Emitted in Results JSON
These keys are directly present in results JSON files at `data/runs/<run_id>/results/<strategy>/<scenario>.json`:

**Tricks (Always emitted):**
- `avg_team0`: Mean tricks for team 0
- `avg_team1`: Mean tricks for team 1
- `distribution_team0`: Count of hands by tricks taken (0-10)

**Points (Only when bidding occurs):**
- `avg_points_team0`: Mean points for team 0 (when bidding enabled)
- `avg_points_team1`: Mean points for team 1 (when bidding enabled)
- `distribution_points_team0`: Count of hands by points scored
- `distribution_points_team1`: Count of hands by points scored

### Rollup-computed Fields
These are computed by aggregation scripts from emitted keys:

**Tricks Delta:**
- `avg_tricks_delta`: `avg_team0 - avg_team1` (positive = team0 advantage)

**Points Delta (when available):**
- `avg_points_delta`: `avg_points_team0 - avg_points_team1` (positive = team0 advantage)

### Planned (Not Yet Implemented)
**Win Rate:**
- `win_rate`: Proportion of hands where team wins (≥6 tricks)
- `push_rate`: Proportion of hands with exactly 5 tricks (tie)
- `loss_rate`: Proportion of hands where team loses (≤4 tricks)
- Confidence intervals for all rates

## Auction Metrics (Optional)

Auction/bidding metrics are optional and clearly labeled as such until a bidding policy is implemented.

When bidding is enabled, additional metrics will include:
- Make rate: Proportion of hands where bidding team meets or exceeds their bid
- Set rate: Proportion of hands where bidding team falls short of their bid
- Average bid values

## Where to Find These Fields

### Results JSON Files
Located at: `data/runs/<run_id>/results/<strategy>/<scenario>.json`

Example from `data/runs/quick_test_42_20260105_193308/results/greedy/high.json`:
```json
{
  "hands": 50,
  "avg_team0": 4.98,
  "avg_team1": 5.02,
  "distribution_team0": {"0": 0, "1": 0, "2": 1, "3": 2, "4": 8, "5": 15, "6": 16, "7": 6, "8": 2, "9": 0, "10": 0}
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
- Code: `src/bid_euchre/sim/simulation.py` (simulate_many_hands function)
- Examples: `data/runs/*/results/*/*.json` files in repo