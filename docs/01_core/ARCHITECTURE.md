# Architecture

This document defines the repository structure, module boundaries, and canonical execution paths.

## Repo Layers and Boundaries

### `src/bid_euchre/`
**Library code only.** Contains importable modules for game simulation, strategies, and analysis.

**Hard rule**: Code in `src/` must NOT import from `experiments/` or `tests/`.

Submodules:
- `core/` — Game mechanics (cards, rules)
- `strategy/` — Strategy implementations
- `features/` — Hand evaluation
- `sim/` — Simulation engines
- `experiments/` — Configuration system (StrategyConfig, ExperimentConfig)
- `reporting/`, `logging/`, `analysis/`, `utils/` — Supporting utilities

### `experiments/`
**Experiment configurations and canonical runner.**

Structure:
- **`run_experiment.py`** — **Blessed canonical runner** (use this for production workflows)
- `configs/` — YAML experiment configurations (reproducible inputs)
- `_deprecated/` — Legacy scripts (do not use or extend)
- `comparisons/`, `training/` — Exploratory research scripts (not canonical; for ad-hoc exploration)

**Note**: Only `run_experiment.py` is the blessed entrypoint. Other scripts in subfolders are for research exploration and must not define competing canonical paths.

### `scripts/`
**Blessed tooling entrypoints.**

Current scripts:
- `generate_report.py` — Per-run report generator
- `lint_repo.py` — Repository linter (enforces boundaries and data policy)
- `run_suite.py` — Suite runner (batches experiments with rollup generation)
- `compare_rollup.py` — Drift detection (compares rollup against baseline fixture)
- `run_tests.py`, `validate_tests.py` — Test utilities

### `tests/`
**Test suite only.**

Structure:
- `unit/` — Fast, isolated tests
- `integration/` — Multi-component tests
- `performance/` — Benchmarks (marked as slow)

### `data/`
**Generated outputs and fixtures.**

**Commit policy**:
- ✅ **Allowed**: `data/fixtures/` only (tiny, intentional test/doc fixtures)
- ❌ **Forbidden**: All generated outputs (`data/runs/`, legacy paths)

See `DATA_CONTRACT.md` for full details.

---

## Gold Path Commands

Run before opening a PR:

```bash
make check          # Full validation (repo-lint + lint + tests)
```

Individual checks:

```bash
make repo-lint      # Repository linter only
make lint           # Ruff (format + lint) only
make test           # Pytest (fast suite) only
```

**Agents must use these commands. Do not invent one-off runners.**

---

## Canonical Execution Paths

### Run an experiment

Use the unified runner:

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/<config>.yaml \
  --seed <seed> \
  --n_per <hands>
```

**Required**: `--seed` (unless you opt in to nondeterminism via `--allow-nondeterministic`)

### Generate a report

Use the blessed report entrypoint:

```bash
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/<run_id>
```

**Options**: `--overwrite` to regenerate existing reports

---

## Run Output Contract

Every experiment run creates a standardized directory under `data/runs/<run_id>/` containing:

- `meta.json` — Run metadata (schema v2)
- `config_effective.yaml` — Resolved configuration snapshot
- `results/` — Machine-readable outputs (JSON, CSV)
- `logs/` — Structured logs (JSONL hand logs)
- `reports/` — Generated charts and dashboards
- `splits/` — Train/test/validation data (if generated)
- `artifacts/` — Model binaries and intermediates (if generated)

**Full details**: See `EXPERIMENTS.md` for complete run output structure and reproduction instructions.

---

## Design Principles

1. **Single source of truth**: One canonical runner (`run_experiment.py`), one report generator (`generate_report.py`)
2. **Determinism by default**: Seed required unless explicitly opted out
3. **Output hygiene**: All outputs written inside run directories (`data/runs/<run_id>/`)
4. **Library separation**: `src/` is import-only; no CLI logic in library code
5. **Gated changes**: All PRs must pass `make check`
