# Experiment Commands — Quick Reference

Copy-paste ready commands. All require `--seed` for reproducibility.

## Smoke Test (10 deals)

```bash
uv run python experiments/run_experiment.py --seed 42 --config <cfg> --n_per 10
```

## Dry Run (Config Validation Only)

```bash
uv run python experiments/run_experiment.py --seed 42 --dry-run --config <cfg>
```

## Suite Execution

```bash
uv run python scripts/run_suite.py --suite experiments/suites/<suite>.yaml --seed 42 --n-per 20
```

## Compare Two Runs

```bash
uv run python scripts/compare_runs.py \
  --baseline data/runs/<baseline_id> \
  --candidate data/runs/<candidate_id> \
  --seed 42 \
  --n-bootstrap 10000 \
  --format markdown
```

## Sample Size Guide

| Purpose | Minimum `--n-per` |
|---------|-------------------|
| Smoke test | 10 |
| Quick validation | 200 |
| Bias detection | 2,000 |
| Production report | 50,000 |

## Config Locations

- Experiment configs: `experiments/configs/*.yaml`
- Suite definitions: `experiments/suites/*.yaml`
- Output directory: `data/runs/<run_id>/` (never commit)
