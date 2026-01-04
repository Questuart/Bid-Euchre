# Architecture Overview

## High-level modules (intended)
- `simulation/`
  - game loop: shuffle/deal, bidding, trick play, scoring
  - configuration: number of hands/games, seed, strategy assignment
  - output: raw logs + summary tables

- `strategies/`
  - bidding strategies (choose bid/pass)
  - play strategies (choose card each trick)
  - each strategy should be deterministic given the same inputs (unless explicitly randomized)

- `hand_eval/`
  - functions that map a hand (+ possibly trump context) → scores
  - supports multiple evaluation "modes" (e.g., old eval vs tuple-based eval)

- `reports/` and `plots/`
  - aggregation: win rates, EV, contract success rate, trick distributions, etc.
  - plotting scripts that create versioned outputs

## Data flow
1) simulation deals a hand
2) `hand_eval` produces score(s)
3) strategy uses eval outputs + game state to bid/play
4) simulation records outcomes
5) reporting aggregates and plots

## Determinism
A run should be reproducible from:
- RNG seed
- strategy names + parameters
- rules/scoring config
- number of games/hands

If a run cannot be reproduced, it is not a valid experiment.

## Output conventions (recommended)
Write outputs under:
`outputs/<run_id>/<strategy_set>/...`

Where `<run_id>` includes timestamp + seed + short config hash.
