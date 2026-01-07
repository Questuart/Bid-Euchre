# Running Experiments

## Quick Start

Run an experiment with a configuration file:

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42 \
  --n_per 10
```

## Run Output Structure

Every experiment run creates a standardized output directory under `data/runs/<run_id>/` with the following structure:

```
data/runs/<run_id>/
├── meta.json                 # Run metadata (schema v2)
├── config_effective.yaml     # Effective configuration snapshot
├── perf.json                 # Performance metrics (timing, throughput)
├── results/                  # Machine-readable outputs (JSON/CSV)
│   └── <strategy>/
│       ├── suit_H.json
│       └── high.json
├── logs/                     # Structured logs (JSONL hand logs)
├── reports/                  # Generated charts and dashboards
├── splits/                   # Train/test/val data splits (if generated)
└── artifacts/                # Model binaries and intermediates (if generated)
```

### Required Files

- **`meta.json`**: Run metadata including git SHA, config path, seed, and parameters (schema v2)
- **`config_effective.yaml`**: Snapshot of the fully-resolved configuration used for the run, including all CLI overrides

### Required Directories

All directories are created for every run, even if empty:

- **`results/`**: Machine-readable outputs (JSON, JSONL, CSV, Parquet)
- **`logs/`**: Structured logs and JSONL hand logs
- **`reports/`**: Generated charts, dashboards, and analyses
- **`splits/`**: Train/test/validation data splits (if training/evaluation workflows generate them)
- **`artifacts/`**: Model binaries, checkpoints, and intermediate artifacts

## Configuration Snapshot

The `config_effective.yaml` file is the authoritative record of the configuration used for the run. It includes:

- Original configuration file contents
- All CLI overrides applied (`--seed`, `--n_per`, `--log-level`, etc.)
- Resolved default values

This file can be used to:
- Reproduce the exact run configuration
- Debug configuration issues
- Compare configurations across runs

**Example**:

```yaml
experiment_name: quick_test
mode: self_play
parameters:
  log_level: none
  n_per: 10      # from CLI (original config: 1000)
  seed: 42       # from CLI (original config: 42)
scenarios:
- contract_type: suit
  trump_suit: H
- contract_type: high
strategies:
- class_name: GreedyStrategy
  name: greedy
```

## Reproducing a Run

To reproduce a run from its metadata:

1. Open the run's `meta.json` to get the original config path
2. Use the `config_effective.yaml` or extract parameters from `meta.json`
3. Run with the same parameters:

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config <config_path from meta.json> \
  --seed <seed from meta.json> \
  --n_per <n_per from meta.json>
```

Or use the effective config directly:

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config data/runs/<run_id>/config_effective.yaml \
  --seed <seed>
```

## Generating Reports

After running an experiment, generate reports and visualizations for analysis:

```bash
# Run an experiment first
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42 \
  --n_per 10

# Generate report for that run
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/<run_id>
```

### Report Generator Behavior

The report generator enforces a **strict I/O contract**:

- **Reads only**: `<run_dir>/results/**`, `<run_dir>/meta.json`, `<run_dir>/config_effective.yaml`
- **Writes only**: `<run_dir>/reports/**` (no outputs outside the run directory)

**Overwrite behavior**:
- If `reports/` is empty: proceeds normally
- If `reports/` contains files and `--overwrite` not specified: exits with error
- If `reports/` contains files and `--overwrite` specified: cleans and regenerates

**Empty results handling**:
- If `results/` is empty or contains no valid files: still generates `ANALYSIS_SUMMARY.md` noting "No results found"
- Exit code 0 (success) even with no results

### Report Outputs

Every report generation creates:

- **`ANALYSIS_SUMMARY.md`**: Text summary with run metadata, discovered results, and generated charts
- Additional visualizations (if implemented): charts, dashboards, comparison plots

### Examples

```bash
# Generate report (first time or empty reports/)
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/quick_test_42_20260105_123456

# Regenerate report (overwrite existing)
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/quick_test_42_20260105_123456 \
  --overwrite

# Verbose mode (see discovered files and progress)
PYTHONPATH=src python scripts/generate_report.py \
  --run-dir data/runs/quick_test_42_20260105_123456 \
  --verbose
```

## Baseline

The **baseline suite** provides a deterministic health check and regression anchor for the simulation.

**Full specification**: See `docs/01_core/BASELINE.md`

**Suite definition**: `experiments/suites/baseline_tiny.yaml`

### `baseline_tiny` — Developer-Friendly Health Check

**Purpose**: Fast, deterministic regression guard (play-only)

**Total hands**: ~760 (completes in seconds)

**Parameters**: `seed=42`, `n_per=20`

**Includes 3 configs**:
1. `quick_test_random.yaml` — RandomLegal sanity (2 scenarios, 40 hands)
2. `baseline_greedy.yaml` — Greedy anchor (6 scenarios, 120 hands)
3. `strategy_comparison.yaml` — Multi-strategy comparison (6 scenarios × 5 strategies, 600 hands)

### Running `baseline_tiny` (Manual)

Run these commands in order (copy/paste):

```bash
# 1. Quick random sanity (2 scenarios)
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test_random.yaml \
  --seed 42 \
  --n_per 20 \
  --log-level none

# 2. Greedy anchor (full scenario set)
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/baseline_greedy.yaml \
  --seed 42 \
  --n_per 20 \
  --log-level none

# 3. Multi-strategy comparison (full scenario set, common deals)
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/strategy_comparison.yaml \
  --seed 42 \
  --n_per 20 \
  --log-level none
```

**Suite runner** (now available):

```bash
PYTHONPATH=src python scripts/run_suite.py \
  --suite experiments/suites/baseline_tiny.yaml \
  --seed 42 \
  --n-per 20
```

**Outputs**: All runs go to `data/runs/<run_id>/` (never committed).

See `docs/01_core/BASELINE.md` for full details on baseline tiers, regression detection, and determinism requirements.

---

## Output Location

By default, runs are written to `data/runs/`. You can customize the output directory:

```bash
PYTHONPATH=src python experiments/run_experiment.py \
  --config experiments/configs/quick_test.yaml \
  --seed 42 \
  --run-dir /path/to/custom/location
```

All outputs are self-contained within the run directory. No artifacts are written outside this location.
