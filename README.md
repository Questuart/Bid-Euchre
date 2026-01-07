# Bid Euchre AI Research Framework

A Python framework for deterministic simulation and strategy evaluation of the card game Bid Euchre.

## Quick Start

```bash
# Verify setup
make check

# Run a quick deterministic experiment
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42 \
  --n_per 5
```

**Note**: Experiment outputs go to `data/runs/<run_id>/` and are not committed to git.

## Documentation

See **[docs/README.md](docs/README.md)** for full documentation.

Key references:
- [docs/01_core/ARCHITECTURE.md](docs/01_core/ARCHITECTURE.md) — System structure and boundaries
- [docs/02_agent/AGENTS.md](docs/02_agent/AGENTS.md) — Development workflow and best practices

## Requirements

- Python 3.10+
- See `requirements.txt` or `pyproject.toml` for dependencies
