# Head-to-Head Strategy Evaluation

## Overview

The head-to-head evaluation system tests strategies against each other in direct matchups using common deals. This provides a clear answer to "does strategy X beat strategy Y?"

## Key Difference from Self-Play

| Mode | Setup | Measures |
|------|-------|----------|
| **Self-Play** | All 4 players use same strategy | Strategy behavior / game dynamics |
| **Head-to-Head** | Team 0 vs Team 1 (2v2) | Competitive advantage |

**Example**: In self-play, if all players are greedy, average tricks ≈ 5.0 (symmetric). In head-to-head, greedy vs random shows greedy wins ~6.3 tricks vs ~3.7.

## Quick Start

### Run Head-to-Head Experiment

```bash
# Test strategies against RandomLegal baseline
PYTHONPATH=src python experiments/run_head_to_head.py \
    --config experiments/configs/head_to_head_vs_random.yaml

# With custom parameters
PYTHONPATH=src python experiments/run_head_to_head.py \
    --config experiments/configs/head_to_head_vs_random.yaml \
    --n_per 50000 --seed 42
```

### Generate Reports

```bash
PYTHONPATH=src python experiments/generate_head_to_head_report.py \
    --run-dir data/runs/<run_id>
```

## Output Structure

```
data/runs/<experiment_name>_<seed>_<timestamp>/
├── meta.json                      # Experiment configuration
├── perf.json                      # Performance metrics
├── results/
│   ├── greedy_vs_random/          # One folder per matchup
│   │   ├── suit_C.json
│   │   └── ...
│   └── random_vs_greedy/          # Seat-swapped matchup
│       └── ...
├── logs/
│   ├── <run_id>_greedy_vs_random.jsonl
│   └── ...
└── reports/
    ├── summary.md                 # Key findings with stats
    └── comparison_matrix.png      # Win rate heatmap
```

## Key Findings from Initial Experiments

### vs RandomLegal Baseline (6,000 hands)

| Strategy | Δ Tricks | Win Rate | Significance |
|----------|----------|----------|--------------|
| **ImprovedGreedy** | +2.87 | 67.5% | ✅ Significantly better |
| **Greedy** | +2.60 | 65.2% | ✅ Significantly better |
| **AlwaysHighest** | +0.29 | 41.9% | ❌ Significantly worse |
| **AlwaysLowest** | -1.35 | 26.2% | ❌ Significantly worse |

### Interpretation

1. **Greedy strategies DO beat random** - This answers the key question
2. **Partner awareness helps** - ImprovedGreedy (+0.27 tricks vs Greedy)
3. **Playing highest card is bad** - Worse than random (wastes power)
4. **Playing lowest card is terrible** - Never takes tricks when possible

## Creating Custom Matchups

Edit `experiments/configs/head_to_head_vs_random.yaml`:

```yaml
matchups:
  # Your custom matchup
  - team0: my_new_strategy
    team1: greedy
  
  # Always include seat swap to check for positional bias
  - team0: greedy
    team1: my_new_strategy
```

## Architecture Notes

- **Common deals**: All matchups use same seed → fair comparison
- **Seat swap**: Running both T0 vs T1 and T1 vs T0 checks for first-player advantage
- **Separate from self-play**: Different runner/reporter for clarity
- **Source of truth**: JSONL logs contain all hand-level data
- **Regeneratable**: Reports can be regenerated without re-running simulations

## Next Steps

1. **Run full-scale experiment**: Use `--n_per 50000` for statistical power
2. **Test new strategies**: Add to config and compare vs baselines
3. **Analyze specific scenarios**: Filter JSONL logs by contract type
4. **Perfect information baseline**: Compare to oracle that sees all cards

