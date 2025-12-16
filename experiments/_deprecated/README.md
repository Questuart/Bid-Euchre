# Deprecated Scripts

These scripts are **deprecated** and superseded by unified, modular alternatives.

## Why Deprecated?

### Experiment Runners
These scripts were refactored into a single, YAML-driven runner to eliminate code duplication and improve maintainability.

#### Old Approach (Deprecated)
- `run_baseline_greedy.py` (~260 lines)
- `run_strategy_comparison.py` (~214 lines)
- `run_extended_comparison.py` (~220 lines)

**Total**: ~700 lines with ~80% duplication

### Report Generators
- `generate_strategy_comparison.py` - Superseded by `generate_paired_comparison.py` which provides superior statistical rigor (paired t-tests, CI, effect sizes)

### New Approach (Current)
- `experiments/run_experiment.py` (271 lines, unified)
- YAML configs in `experiments/configs/`

**Total**: ~320 lines (including configs), handles all cases

## Migration

### Old Way
```bash
PYTHONPATH=src python experiments/run_baseline_greedy.py --n_per 50000 --seed 42
PYTHONPATH=src python experiments/run_strategy_comparison.py --n_per 50000 --seed 42
PYTHONPATH=src python experiments/run_extended_comparison.py --n_per 50000 --seed 42
```

### New Way
```bash
# Baseline greedy
PYTHONPATH=src python experiments/run_experiment.py \\
    --config experiments/configs/baseline_greedy.yaml

# Strategy comparison
PYTHONPATH=src python experiments/run_experiment.py \\
    --config experiments/configs/strategy_comparison.yaml

# Override parameters
PYTHONPATH=src python experiments/run_experiment.py \\
    --config experiments/configs/strategy_comparison.yaml \\
    --n_per 10000 --seed 99
```

## Should You Use These?

**No.** Use `experiments/run_experiment.py` instead.

These files are kept for reference only. They will be removed in a future cleanup.

## See Also

- `experiments/run_experiment.py` - Unified runner
- `experiments/configs/` - Example YAML configurations
- `REFACTORING_NOTES.md` - Complete refactoring documentation

