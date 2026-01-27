# sim/ — Simulation Engine

Game loop orchestration and deterministic deal generation.

## Key Files

| File | Purpose |
|------|---------|
| `simulation.py` | `simulate_many_hands()` — core game loop, runs hands with strategies |
| `deals.py` | Deterministic deal generation with seeding |

## Usage
Called by `experiments/run_experiment.py`. For experiments, use the unified runner rather than calling `sim` directly.

## Dependencies
- Imports from: `core/` (cards, rules)
- Used by: `experiments/`, `datasets/`

## Contract
- Deals must be reproducible given the same seed
- See [docs/01_core/REPRODUCIBILITY.md](../../../docs/01_core/REPRODUCIBILITY.md) for seeding requirements
