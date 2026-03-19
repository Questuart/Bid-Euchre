---
name: running-experiments
description: Guides experiment execution: config validation, seeded runs, suite execution, and result comparison. Use when running experiments, comparing runs, or validating strategy changes.
---

# Experiment Execution Guide

Run seeded experiments, suites, and comparisons following the repo's determinism and rigor requirements.

## Phase 0 — Pre-flight

1. Verify you are in a worktree (not main checkout):
   ```bash
   git rev-parse --show-toplevel
   git branch --show-current
   ```

2. Check the config exists and is valid:
   ```bash
   uv run python experiments/run_experiment.py --seed 42 --dry-run --config <cfg>
   ```

3. Confirm the output directory is clean:
   ```bash
   ls data/runs/  # Should not contain prior runs you plan to compare against
   ```

## Phase 1 — Smoke Run

Quick validation that the config works end-to-end:

```bash
uv run python experiments/run_experiment.py --seed 42 --config <cfg> --n_per 10
```

This produces ~10 deals per seat — enough to confirm execution but NOT for any statistical claims.

## Phase 2 — Suite Execution

For multi-config comparisons, use the suite runner:

```bash
uv run python scripts/run_suite.py --suite <suite.yaml> --seed 42 --n-per 20
```

Suite YAML files live in `experiments/suites/`. Choose the appropriate tier:
- `baseline_tiny.yaml` — smoke test (~10s)
- Production suites require `--n-per` ≥ 50,000

## Phase 3 — Comparison

Compare two runs with bootstrap statistics:

```bash
uv run python scripts/compare_runs.py \
  --baseline data/runs/<baseline_run_id> \
  --candidate data/runs/<candidate_run_id> \
  --seed 42 \
  --n-bootstrap 10000 \
  --format markdown
```

Use `--format markdown` to generate PR-ready output.

## Phase 4 — Interpretation

Key metrics from comparison output:

| Metric | Meaning | Healthy Range |
|--------|---------|---------------|
| net_eppd | Expected points per deal delta | Context-dependent |
| bid_rate | Fraction of hands where strategy bids | 0.3–0.7 typical |
| make_rate | Fraction of bids that succeed | 0.5–0.8 typical |
| R² | Variance explained by model | Higher is better |

## Gotchas

- Missing `--seed` silently produces non-reproducible results — always specify `--seed <int>`
- `--n-per 10` is smoke-only; production claims need ≥50,000 deals (per `05_rigor.md`)
- `--allow-nondeterministic` voids ALL comparison claims — use only for exploration
- `compare_runs.py` requires both runs to use the same config structure
- Output goes to `data/runs/<run_id>/` — **never commit** these (data policy)
- Same seed + same config MUST produce identical results — if they don't, you have a determinism bug

## References

For deeper context, read these on demand:
- `docs/01_core/EXPERIMENTS.md` — Experiment runner and output structure
- `docs/01_core/REPRODUCIBILITY.md` — Seeding and determinism guarantees
- `docs/01_core/METRICS.md` — Metric definitions and statistical requirements
- See also [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for a copy-paste command cheat-sheet
