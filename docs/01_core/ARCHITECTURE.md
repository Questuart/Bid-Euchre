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
- `reporting/`, `logging/`, `analysis/` — Supporting utilities
- `scoring.py` — Top-level scoring module (compute_points)

### `experiments/`
**Experiment configurations and canonical runner.**

Structure:
- **`run_experiment.py`** — **Blessed canonical runner** (use this for production workflows)
- `configs/` — YAML experiment configurations (reproducible inputs)
- `_deprecated/` — Legacy scripts (do not use or extend)
- `comparisons/`, `training/` — Exploratory research scripts (not canonical; for ad-hoc exploration)

**Note**: Only `run_experiment.py` is the blessed entrypoint. Other scripts in subfolders are for research exploration and must not define competing canonical paths.

**Disambiguation**: `experiments/` is a filesystem directory (YAML configs + runner). `bid_euchre.experiments` (under `src/bid_euchre/experiments/`) is the library config module. Do not `import experiments` as a Python package.

### `scripts/`
**Blessed tooling entrypoints.**

Canonical scripts:
- `check_docs_freshness.py` — Docs freshness gate (path refs + script list completeness)
- `compare_rollup.py` — Drift detection (compares rollup against baseline fixture)
- `compare_runs.py` — Run comparison utility with bootstrap statistics
- `generate_report.py` — Per-run report generator
- `lint_repo.py` — Repository linter (enforces boundaries and data policy)
- `run_bidless_diagnostics.py` — Bidless feature dataset diagnostics
- `run_charts.py` — Production chart generation (extracted from `reporting.chart_runner`)
- `run_notebooks.py` — Notebook execution via papermill (CI tooling)
- `run_suite.py` — Suite runner (batches experiments with rollup generation)
- `run_tests.py` — Test runner utility
- `train_b0.py` — B0 hand value model training (extracted from `models.train_b0`)
- `train_bidder.py` — Bidder model training
- `train_hybrid_olsa.py` — Hybrid OLSa training pipeline (Arc D)
- `train_olsa.py` — OLSa model training (extracted from `models.train_olsa`)
- `update_r0_bundle.py` — Update R0 rung bundle with eval paths (Arc D)
- `validate_configs.py` — Config validation utility
- `validate_teacher_roster.py` — Teacher roster validation
- `write_r0_promotion.py` — Write R0 auto-promotion decision (Arc D)

Deprecation wrappers (forward to `scripts/internal/` with a warning):
- `evaluate_diagnostic_tricks.py`, `play_policy_gate.py`, `run_auction_comparator.py`

Shell scripts:
- `run_r0b.sh` — R0 baseline lock reproduction commands (Arc D Wave 3)

### `scripts/internal/`
**Research and internal tooling.** Not part of the canonical workflow.

- `audit_analysis.py` — Review pipeline audit (follow-up rates, corrective PRs, per-PR trail)
- `evaluate_diagnostic_tricks.py` — Diagnostic Ridge evaluation
- `evaluate_gate_x3.py` — R1.5 Gate X3 offline ranking evaluation (action-value model vs oracle)
- `extract_comparator_cis.py` — Bootstrap CIs for comparator battery metrics
- `generate_arc_dashboard.py` — Cross-rung Arc D progression dashboard
- `generate_auction_context_dataset.py` — Auction-context dataset generator (R1 partner features)
- `generate_batch_report.py` — Batch report + eligibility gate
- `generate_r4_charts.py` — One-off report chart regeneration utility
- `play_policy_gate.py` — Play policy stability gate
- `calibrate_arc_d_thresholds.py` — Arc D gate threshold calibration from H2H null signal
- `run_arc_d_gate.py` — Arc D promotion gate runner
- `run_arc_d_h2h_battery.py` — H2H all-vs-all battery runner (competitive validation)
- `run_auction_comparator.py` — Auction comparator orchestrator
- `run_lambda_sweep.py` — Simulation-based risk_lambda tuning sweep
- `run_normalizer_offline_screen.py` — Normalizer go/no-go offline screening pipeline
- `run_threshold_sweep.py` — Grid search over pass_threshold values (R1 threshold tuning)
- `train_unified_model.py` — Unified cross-contract OLS training (Track F OneModel)
- `update_arc_registry.py` — Arc D registry updater (MODEL_ARC_RUNS.md)
- `validate_arc_d_rung_contract.py` — Arc D rung bundle validator

Deprecation wrappers at old paths (`scripts/*.py`) forward to `scripts/internal/` with a warning.

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

Run before opening a PR (either one):

```bash
make check-quiet    # Same validation, minimal output — preferred (logs to tmpfile)
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
uv run python experiments/run_experiment.py --config experiments/configs/quick_test.yaml --seed 42
```

**Required**: `--seed` (unless you opt in to nondeterminism via `--allow-nondeterministic`)

### Generate a report

Use the blessed report entrypoint:

```bash
uv run python scripts/generate_report.py \
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
| `scripts/check_docs_freshness.py` | Docs freshness gate (path refs + script list) |
| `scripts/compare_runs.py` | Compare two runs with bootstrap statistics |
| `scripts/compare_rollup.py` | Drift detection against baseline fixture |
| `scripts/lint_repo.py` | Repository linter |
| `scripts/run_charts.py` | Production chart generation |
| `scripts/run_notebooks.py` | Notebook execution via papermill (CI) |
| `scripts/run_tests.py` | Test runner utility |
| `scripts/validate_configs.py` | Config validation |
| `scripts/validate_teacher_roster.py` | Teacher roster validation |

### Internal tooling (`scripts/internal/`)

| Command | Purpose |
|---------|---------|
| `scripts/internal/audit_analysis.py` | Review pipeline audit (follow-up rates, corrective PRs) |
| `scripts/internal/evaluate_diagnostic_tricks.py` | Diagnostic Ridge evaluation |
| `scripts/internal/evaluate_gate_x3.py` | R1.5 Gate X3 offline ranking evaluation (action-value model vs oracle) |
| `scripts/internal/extract_comparator_cis.py` | Bootstrap CIs for comparator battery metrics |
| `scripts/internal/generate_action_value_dataset.py` | Counterfactual action-value dataset generator (R1.5) |
| `scripts/internal/generate_arc_dashboard.py` | Cross-rung Arc D progression dashboard |
| `scripts/internal/generate_auction_context_dataset.py` | Auction-context dataset generator (R1 partner features) |
| `scripts/internal/generate_batch_report.py` | Batch report + eligibility gate |
| `scripts/internal/generate_r4_charts.py` | One-off report chart regeneration utility |
| `scripts/internal/generate_rung_charts.py` | Rung report chart generation from eval data + model artifacts |
| `scripts/internal/play_policy_gate.py` | Play policy stability gate |
| `scripts/internal/calibrate_arc_d_thresholds.py` | Arc D gate threshold calibration from H2H null signal |
| `scripts/internal/run_arc_d_gate.py` | Arc D promotion gate runner |
| `scripts/internal/run_arc_d_h2h_battery.py` | H2H all-vs-all battery runner (competitive validation) |
| `scripts/internal/run_auction_comparator.py` | Auction comparator orchestrator |
| `scripts/internal/run_lambda_sweep.py` | Simulation-based risk_lambda tuning sweep |
| `scripts/internal/run_normalizer_offline_screen.py` | Normalizer go/no-go offline screening pipeline |
| `scripts/internal/run_threshold_sweep.py` | Grid search over pass_threshold values (R1 threshold tuning) |
| `scripts/internal/train_action_value.py` | Action-value OLS training pipeline (R1.5) |
| `scripts/internal/train_unified_model.py` | Unified cross-contract OLS training (Track F OneModel) |
| `scripts/internal/update_arc_registry.py` | Arc D registry updater (MODEL_ARC_RUNS.md) |
| `scripts/internal/validate_arc_d_rung_contract.py` | Arc D rung bundle validator |

### Research tooling (canonical path)

| Command | Purpose |
|---------|---------|
| `scripts/run_bidless_diagnostics.py` | Bidless diagnostics |
| `scripts/train_b0.py` | B0 hand value model training |
| `scripts/train_bidder.py` | Bidder model training |
| `scripts/train_hybrid_olsa.py` | Hybrid OLSa training (Arc D) |
| `scripts/train_olsa.py` | OLSa model training |
| `scripts/update_r0_bundle.py` | Update R0 rung bundle with eval paths (Arc D) |
| `scripts/write_r0_promotion.py` | Write R0 auto-promotion decision (Arc D) |

---

## Module Dependency Contract

The following import edges are explicitly allowed between `reporting/` and `diagnostics/`:

| Edge | Status | Reason |
|------|--------|--------|
| `diagnostics/*.py` → `reporting.style` | Allowed | Shared styling constants |
| `reporting.charts` → `diagnostics.charts` | Allowed | Direct import for chart composition |
| `reporting.__init__` → `reporting.charts` | **Forbidden** | Would trigger circular import |
| `reporting.style` → `diagnostics.*` | **Forbidden** | Back-edge would create cycle |

These constraints are enforced by `tests/unit/test_import_contract.py`.

---

## Integration Policy

1. **Fresh branch from `origin/main`** per PR — never merge stale heads directly
2. **Cherry-pick or re-implement** intended commits only when rebasing across PRs
3. **One concept per PR** — mixed refactor + feature PRs are rejected
4. **Worktree-only workflow** — all code changes happen in dedicated worktrees, never on `main`

---

## Promotion Workflow

Promotion-track PRs (labeled `promotion`) must pass the promotion CI gate:
`make promotion-gate` (repo-lint + notebook smoke + gate assertion).

See `docs/02_agent/PROMOTION_WORKFLOW.md` for the full end-to-end workflow including
split manifests, artifact freeze, notebook gates, and reviewer checklist.

---

## Developer Notes

### Strategy Registration Pattern

When adding a new strategy to the framework, four files must be updated in
coordination. Missing any one of them will cause either import errors or
silent config failures:

1. **Implementation** (`src/bid_euchre/strategy/<name>.py`) — The strategy
   class itself. Must accept a `seed` parameter and use a local
   `random.Random(seed)` instance for all stochastic decisions. Global
   `random.*` calls violate the determinism contract and will be caught by
   the review gate (check C1).

2. **Package export** (`src/bid_euchre/strategy/__init__.py`) — Add the class
   to the public API. Without this, YAML configs that reference the strategy
   by name will fail at runtime with an `AttributeError`.

3. **Config registration** (`src/bid_euchre/experiments/config.py`) — Register
   the strategy name in `StrategyConfig.create_strategy()`. This is the
   mapping between YAML string identifiers and Python classes. Forgetting
   this step produces a `ValueError` at experiment startup.

4. **YAML config** (`experiments/configs/<name>.yaml`) — Create at least one
   config file that exercises the new strategy. This serves as both
   documentation and a smoke-test target.

### Common Pitfalls

- **Circular imports in `__init__.py`**: When re-exporting modules from
  package init files, avoid importing submodules that themselves import from
  sibling packages. The `reporting` and `diagnostics` modules have explicit
  import-edge constraints documented above in the Module Dependency Contract.

- **NaN handling in sort operations**: Python's `sorted()` with `key=abs`
  produces undefined behavior when NaN values are present. Always filter
  NaN values before sorting.

- **Falsy numeric guards**: The pattern `x = x or fallback` silently
  replaces `0.0` with `fallback` because `0.0` is falsy in Python. Use
  `x = fallback if x is None else x` instead. This is a merge-blocking
  finding (check C2) in the review gate.

- **PyArrow list columns**: When converting PyArrow list-type columns to
  hashable values for grouping, use `tuple(sorted(x))` unconditionally
  rather than attempting direct comparison.

---

## Design Principles

1. **Single source of truth**: One canonical runner (`run_experiment.py`), one report generator (`generate_report.py`)
2. **Determinism by default**: Seed required unless explicitly opted out
3. **Output hygiene**: All outputs written inside run directories (`data/runs/<run_id>/`)
4. **Library separation**: `src/` is import-only; no CLI logic in library code
5. **Gated changes**: All PRs must pass `make check`
6. **Promotion gates**: Promotion-track PRs must additionally pass `make promotion-gate`
