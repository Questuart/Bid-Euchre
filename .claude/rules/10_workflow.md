# Workflow Rules

> **Authoritative source:** @docs/02_agent/AGENTS.md

## Gold Path Commands

Run before any PR:
```bash
make check          # Full validation: repo-lint + ruff + pytest
```

Individual checks:
```bash
make repo-lint      # Repo linter only
make lint           # Ruff only
make test           # Pytest fast suite only
```

## Smoke Experiment (Optional)

Validate changes with a seeded run:
```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42
```

## Key Rules

1. **Use canonical runner only** — `experiments/run_experiment.py` + YAML configs
2. **Do not create new top-level directories** without explicit instruction
3. **Library code in `src/`** — CLI scripts go in `scripts/` or `experiments/`
4. **Run `make check` before claiming PR is done**

See @docs/02_agent/AGENTS.md for full workflow details.
