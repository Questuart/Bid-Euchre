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
- `datasets/` — Dataset collectors (bidding, bidless)
- `models/` — Model training/inference
- `diagnostics/` — Visualization and analysis tools
- `validation/` — Schema validation
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
- `compare_rollup.py` — Drift detection (compares rollup against baseline fixture)
- `compare_runs.py` — Run comparison utility with bootstrap statistics
- `evaluate_diagnostic_tricks.py` — Diagnostic Ridge evaluation
- `generate_report.py` — Per-run report generator
- `lint_repo.py` — Repository linter (enforces boundaries and data policy)
- `play_policy_gate.py` — Play policy stability gate
- `run_auction_comparator.py` — Auction comparator orchestrator
- `run_bidless_diagnostics.py` — Bidless feature dataset diagnostics
- `run_notebooks.py` — Notebook execution via papermill (CI tooling)
- `run_suite.py` — Suite runner (batches experiments with rollup generation)
- `run_tests.py` — Test runner utility
- `train_bidder.py` — Bidder model training
- `validate_configs.py` — Config validation utility
- `validate_teacher_roster.py` — Teacher roster validation

### `tests/`
**Test suite only.**

Structure:
- `unit/` — Fast, isolated tests
- `integration/` — Multi-component tests
- `performance/` — Benchmarks (marked as slow)
- `property/` — Property-based tests

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
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42
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

## Canonical CLI Contract

### Primary commands (production workflows)

| Command | Purpose |
|---------|---------|
| `experiments/run_experiment.py` | Run experiments (seed required) |
| `scripts/generate_report.py` | Generate per-run reports |
| `scripts/run_suite.py` | Batch experiment runner |

### Supporting tooling

| Command | Purpose |
|---------|---------|
| `scripts/compare_runs.py` | Compare two runs with bootstrap statistics |
| `scripts/compare_rollup.py` | Drift detection against baseline fixture |
| `scripts/lint_repo.py` | Repository linter |
| `scripts/run_notebooks.py` | Notebook execution via papermill (CI) |
| `scripts/validate_configs.py` | Config validation |
| `scripts/validate_teacher_roster.py` | Teacher roster validation |

### Research/internal tooling

| Command | Purpose |
|---------|---------|
| `scripts/run_auction_comparator.py` | Auction comparator orchestrator |
| `scripts/evaluate_diagnostic_tricks.py` | Diagnostic Ridge evaluation |
| `scripts/play_policy_gate.py` | Play policy stability gate |
| `scripts/run_bidless_diagnostics.py` | Bidless diagnostics |
| `scripts/train_bidder.py` | Bidder model training |

---

## Design Principles

1. **Single source of truth**: One canonical runner (`run_experiment.py`), one report generator (`generate_report.py`)
2. **Determinism by default**: Seed required unless explicitly opted out
3. **Output hygiene**: All outputs written inside run directories (`data/runs/<run_id>/`)
4. **Library separation**: `src/` is import-only; no CLI logic in library code
5. **Gated changes**: All PRs must pass `make check`
