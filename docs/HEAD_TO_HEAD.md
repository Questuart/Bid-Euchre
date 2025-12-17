# Head-to-Head Strategy Evaluation

## Overview

Head-to-head evaluation tests strategies against each other in **direct 2v2 matchups** on **common deals**. This answers the practical question: **“does strategy X beat strategy Y?”**

## Key Difference from Self-Play

| Mode | Setup | Measures |
|------|-------|----------|
| **Self-play** | All 4 seats use the same strategy | Behavior / calibration (symmetric results) |
| **Head-to-head** | Team 0 vs Team 1 (seats 0&2 vs 1&3) | Competitive advantage |

## Quick Start

### Run a head-to-head matrix experiment (recommended)

```bash
# Run the matchup matrix defined in YAML
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/head_to_head_vs_random.yaml \
  --mode head_to_head_matrix

# Override parameters
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/head_to_head_vs_random.yaml \
  --mode head_to_head_matrix \
  --n_per 50000 \
  --seed 42
```

> Note: `experiments/run_head_to_head.py` is kept only as a deprecated wrapper.

### Generate reports

```bash
# Mode-aware: generates the correct report suite for the run
PYTHONPATH=src python experiments/generate_all_reports.py \
  --run-dir data/runs/<run_id>

# Or run the head-to-head report directly
PYTHONPATH=src python experiments/generate_head_to_head_report.py \
  --run-dir data/runs/<run_id>
```

## Output Structure

```
data/runs/<experiment_name>_<seed>_<timestamp>/
├── meta.json
├── perf.json
├── results/
│   ├── greedy_vs_random_legal/
│   │   ├── suit_C.json
│   │   └── ...
│   └── random_legal_vs_greedy/
│       └── ...
├── logs/                          # Optional (depends on log level)
│   ├── <run_id>_<matchup>.jsonl
│   └── ...
└── reports/
    └── head_to_head/
        ├── comparison_matrix.png
        ├── summary.md
        └── matchups/
            ├── greedy_vs_random_legal.png
            └── ...
```

## Creating Custom Matchups

Edit `experiments/configs/head_to_head_vs_random.yaml`:

```yaml
mode: head_to_head_matrix

matchups:
  - team0: greedy
    team1: random_legal

  # Always include seat swap to check positional bias
  - team0: random_legal
    team1: greedy
```

## Notes / Guardrails

- **Common deals**: comparisons are only meaningful if matchups share the same deals.
- **Seat swap**: running both directions helps detect positional bias.
- **Source of truth**: JSONL logs are the most detailed dataset (when enabled).
