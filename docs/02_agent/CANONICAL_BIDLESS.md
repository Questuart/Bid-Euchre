# Canonical Bidless Experiments

This document describes the canonical bidless experiment workflow for producing research-grade datasets and outcomes data.

## Overview

Canonical bidless experiments provide deterministic, paired-deals runs for:

## Blessed Runs Registry

See [CANONICAL_BIDLESS_RUNS.md](CANONICAL_BIDLESS_RUNS.md) for the authoritative registry of promoted canonical runs.

**Promotion artifacts** (in each blessed run):
- `artifacts/canonical_summary.json` — Machine-readable promotion record with PASS/WARN/FAIL/SKIP counts
- `artifacts/canonical_summary.md` — Human-readable summary

**Supporting evidence** (for troubleshooting):
- `reports/ANALYSIS_SUMMARY.md` — Detailed run analysis
- `reports/sanity_tests/strategy_sanity.json` — Full sanity test results

---

Canonical bidless experiments provide deterministic, paired-deals runs for:
- **ML Training Data**: Features and outcome labels for bidding model development
- **Strategy Comparison**: Head-to-head matchups with statistical validation
- **Sanity Checking**: Automated tests to validate strategy behavior

All canonical runs use:
- `seed=42` for reproducibility
- `pair_deals=true` for paired statistical tests
- `log_level=none` (no hand-level logs for scale)

## Configurations

### A) Training Dataset (Features + Outcomes, Single-Policy)

**Config**: `experiments/configs/canonical_bidless_dataset_greedy.yaml`

**Purpose**: Collect hand features AND outcome labels for ML training using a **single play policy** (greedy).

**Why single-policy?** Training labels reflect "tricks won under greedy play". Mixed-policy datasets conflate different play quality levels, making labels inconsistent unless the model conditions on play policy.

**Strategies**: greedy only (1 strategy in self-play)

**Total hands**: 50,000 × 6 scenarios × 1 strategy = **300,000 hands**

**Command**:
```bash
uv run pythonexperiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_greedy.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
```

**Outputs** (in `<run_dir>/datasets/`):
- `bidless.parquet` + `bidless.jsonl` + `bidless_meta.json` (features)
- `bidless_outcomes.parquet` + `bidless_outcomes.jsonl` + `bidless_outcomes_meta.json` (outcomes)

### A.1) Mixed-Play Dataset (Analysis Only)

**Config**: `experiments/configs/canonical_bidless_dataset_mixed_play.yaml`

**Purpose**: Collect diverse outcomes across multiple play policies for diagnostics and analysis.

> **Warning**: Do NOT train bidding models on this dataset without conditioning on play policy. Outcome labels mix greedy, glutton, and random play quality, making them inconsistent for supervised learning.

**Strategies**: greedy, glutton, random_legal (3 strategies in self-play)

**Total hands**: 50,000 × 6 scenarios × 3 strategies = **900,000 hands**

**Command**:
```bash
uv run pythonexperiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_mixed_play.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
```

### A.2) Training Dataset (Features + Outcomes, Single-Policy: Glutton)

**Config**: `experiments/configs/canonical_bidless_dataset_glutton.yaml`

**Purpose**: Collect hand features AND outcome labels for ML training using **glutton play policy**.

**Prerequisite**: Only run after play policy gate PASS (see [PLAY_POLICY_FREEZE.md](PLAY_POLICY_FREEZE.md)). Training labels must be single-policy and stable; switching policies mid-training invalidates prior labels.

**Strategies**: glutton only (1 strategy in self-play)

**Total hands**: 50,000 × 6 scenarios × 1 strategy = **300,000 hands**

**Command**:
```bash
uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_glutton.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
```

### B) Shallow Matrix (Broad Coverage)

**Config**: `experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml`

**Purpose**: Cheap broad coverage across all 25 matchups for sanity checking.

**Strategies**: greedy, glutton, random_legal, always_highest, always_lowest (5 strategies)

**Matchups**: Full 5×5 matrix (25 ordered pairs including self-play)

**Total hands**: 2,000 × 6 scenarios × 25 matchups = **300,000 hands**

**Command**:
```bash
uv run pythonexperiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml --seed 42
```

### C) Zoom Run (High Precision)

**Config**: `experiments/configs/canonical_bidless_outcomes_zoom.yaml`

**Purpose**: High-precision data for decision-relevant matchups.

**Matchups** (11 total):
- 5 self-play controls (fairness verification)
- 6 decision-relevant head-to-heads (glutton vs greedy, greedy vs random, glutton vs random, each direction)

**Total hands**: 50,000 × 6 scenarios × 11 matchups = **3,300,000 hands**

**Command**:
```bash
uv run pythonexperiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_zoom.yaml --seed 42
```

## Output Structure

After running an experiment:

```
data/runs/<run_id>/
├── meta.json                    # Run metadata
├── config_effective.yaml        # Effective configuration
├── datasets/                    # Dataset outputs (if --emit-* flags used)
│   ├── bidless.parquet
│   ├── bidless_outcomes.parquet
│   └── *.jsonl + *_meta.json
├── results/                     # Strategy matchup results
│   └── <matchup>/
│       ├── suit_C.json
│       ├── suit_D.json
│       ├── suit_H.json
│       ├── suit_S.json
│       ├── high.json
│       └── low.json
└── reports/                     # Generated by generate_report.py
    ├── ANALYSIS_SUMMARY.md
    └── sanity_tests/
        ├── strategy_sanity.json
        └── strategy_sanity.md
```

## Generating Reports

After running an experiment, generate reports with sanity tests:

```bash
uv run python scripts/generate_report.py \
  --run-dir data/runs/<run_id>
```

Reports include:
- **ANALYSIS_SUMMARY.md**: Run metadata, discovered files, summary
- **sanity_tests/**: Strategy sanity test results (JSON + Markdown)

## Sanity Tests

The following automated sanity tests validate strategy behavior:

### 1. Self-Play Fairness

Checks that team 0 ≈ team 1 in self-play matchups.

| Threshold | Status |
|-----------|--------|
| \|mean_delta\| < 0.25 | PASS |
| \|mean_delta\| >= 0.5 | FAIL |
| otherwise | WARN |

### 2. Random Dominance

Verifies that intelligent strategies (greedy, glutton) beat random_legal.

| Condition | Status |
|-----------|--------|
| win_rate > 0.52 | PASS |
| win_rate > 0.5 but ≤ 0.52 | WARN |
| win_rate ≤ 0.5 | FAIL |

### 3. Rank Stability

Measures ranking consistency across contract families using Kendall's tau.

| Threshold | Status |
|-----------|--------|
| min(tau) > 0.6 | PASS |
| any tau < 0.3 | WARN |
| otherwise | depends on median |

### 4. Transitivity

Checks for transitivity violations (A>B, B>C implies A>C).

| Condition | Status |
|-----------|--------|
| No violations | PASS |
| Any violations | WARN |

## Notebook Usage

Notebooks are controlled by the `MODE` parameter:

```python
# MODE controls notebook execution scale:
#   SMOKE (~30 deals) — CI smoke tests
#   QUICK (~2,000 deals) — development iteration
#   FULL  (~50,000 deals) — production analysis (manual execution only)
MODE = "QUICK"
```

### Via the runner CLI (SMOKE / QUICK only)

`scripts/run_notebooks.py` supports `--mode smoke` and `--mode quick`. It injects the `MODE` parameter automatically:

```bash
# SMOKE mode (CI, ~10s)
uv run python scripts/run_notebooks.py --mode smoke

# QUICK mode (development, ~2-5min)
uv run python scripts/run_notebooks.py --mode quick
```

Notebooks generate data on-the-fly via `load_or_generate_*()` helpers — no pre-existing run directory needed.

### Direct execution (FULL mode)

For production-scale analysis (`MODE = "FULL"`), execute notebooks directly (e.g., via Jupyter or `papermill`). The runner CLI does not support FULL mode.

### Loading from an existing run directory (optional)

If you have a pre-existing experiment run, notebooks can load data via `RUN_DIR` instead of generating on-the-fly:

```python
from bid_euchre.diagnostics.notebook_data import load_outcomes_from_run_dir
from pathlib import Path

run_dir = Path(RUN_DIR)
df = load_outcomes_from_run_dir(run_dir)
```

The loader will:
1. Try `datasets/bidless_outcomes.parquet` first
2. Fall back to parsing JSONL logs from `logs/` if parquet not present

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Hybrid matrix (shallow + zoom) | Concentrates budget on decision-relevant cells |
| No hand logs by default | Logs are huge and unnecessary with outcomes parquet |
| Single report script | One blessed path via `generate_report.py` |
| Results-driven reporting | JSON results already contain aggregates; no log parsing |
| Single-policy training dataset | Consistent labels (greedy-only for training) |
| Multi-policy analysis dataset | Strategy diversity (greedy, glutton, random for analysis) |
| `pair_deals: true` | Enables paired statistical tests across scenarios |

## Total Budget Summary

| Config | Hands | Purpose |
|--------|-------|---------|
| canonical_bidless_dataset_greedy | 300K | ML training data (single-policy) |
| canonical_bidless_dataset_glutton | 300K | ML training data (single-policy, if gate PASS) |
| canonical_bidless_dataset_mixed_play | 900K | Analysis/diagnostics (multi-policy) |
| canonical_bidless_outcomes_matrix_shallow | 300K | Broad sanity coverage |
| canonical_bidless_outcomes_zoom | 3.3M | High-precision comparisons |
| **Total** | **5.1M hands** | Full canonical baseline (if glutton gate PASS) |

## Quick Reference

```bash
# Training dataset (single-policy greedy, for ML)
uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_greedy.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset

# Training dataset (single-policy glutton, for ML — requires gate PASS)
uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_glutton.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset

# Analysis dataset (multi-policy, for diagnostics)
uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_mixed_play.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset

# Shallow matrix (broad sanity checking)
uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml --seed 42

# Zoom run (high-precision decision cells)
uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_zoom.yaml --seed 42

# Generate report (after any run)
uv run python scripts/generate_report.py \
  --run-dir data/runs/<run_id>
```

## Promotion Checklist

This section documents the sequential workflow for promoting canonical baseline runs with sanity gates.

**Key principle:** Shallow→zoom gating prevents wasting compute on a broken baseline. The shallow run is cheap (~300K hands); if it fails sanity tests, fix the issue before running the expensive zoom run (~3.3M hands).

### Step 1: Training Dataset (greedy-only)

Run the experiment:

```bash
uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_dataset_greedy.yaml --emit-bidless-dataset --emit-bidless-outcomes-dataset
```

Capture the run directory:

```bash
DATASET_RUN=$(ls -td data/runs/canonical_bidless_dataset_greedy_42_* | head -1)
```

Generate report (required to create `artifacts/canonical_summary.*`):

```bash
uv run python scripts/generate_report.py --run-dir "$DATASET_RUN"
```

Verify:
- `$DATASET_RUN/datasets/bidless.parquet` exists
- `$DATASET_RUN/datasets/bidless_outcomes.parquet` exists
- `$DATASET_RUN/artifacts/canonical_summary.json` exists

### Step 2: Shallow Matrix + Sanity Gate

Run the experiment:

```bash
uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml
```

Capture the run directory:

```bash
SHALLOW_RUN=$(ls -td data/runs/canonical_bidless_outcomes_matrix_shallow_42_* | head -1)
```

Run sanity gate:

```bash
uv run python scripts/generate_report.py --run-dir "$SHALLOW_RUN" --fail-on-sanity-failures
```

Gate semantics:
- **Exit 0:** PASS or WARN → Proceed to Step 3
- **Exit 1:** FAIL → **STOP.** Do not proceed. See "What to Do if Shallow FAILs" below.

WARN does not block promotion; only FAIL blocks.

### Step 3: Zoom Run (only if shallow passed)

Run the experiment:

```bash
uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_zoom.yaml
```

Capture the run directory:

```bash
ZOOM_RUN=$(ls -td data/runs/canonical_bidless_outcomes_zoom_42_* | head -1)
```

Run sanity gate:

```bash
uv run python scripts/generate_report.py --run-dir "$ZOOM_RUN" --fail-on-sanity-failures
```

### Step 4: Verify Artifacts Exist

For each run, confirm:
- `artifacts/canonical_summary.json` exists
- `artifacts/canonical_summary.md` exists
- `reports/sanity_tests/strategy_sanity.json` exists (for shallow and zoom)

### Step 5: Record in Registry

Extract fields from `artifacts/canonical_summary.json` and update [CANONICAL_BIDLESS_RUNS.md](CANONICAL_BIDLESS_RUNS.md):

| Field | Source |
|-------|--------|
| run_id | `canonical_summary.json → run_id` |
| git_sha | `canonical_summary.json → git_sha` |
| seed | `canonical_summary.json → seed` |
| n_per | `canonical_summary.json → n_per` |
| total_hands | `canonical_summary.json → total_hands` |
| PASS/WARN/FAIL/SKIP | `canonical_summary.json → sanity.*_count` |
| verdict | PASS if `fail_count == 0`, else FAIL |

### What to Do if Shallow FAILs

If `--fail-on-sanity-failures` exits non-zero on the shallow run:

1. **Do not proceed to zoom.** The gate prevents wasting compute on a broken baseline.

2. **Investigate the failure:**
   - Read `reports/sanity_tests/strategy_sanity.md` for details
   - Check which specific test(s) are marked FAIL

3. **Common causes and fixes:**

| Failure | Likely Cause | Action |
|---------|--------------|--------|
| Self-play bias | Simulation bug or RNG issue | Check `core/` changes, verify determinism |
| Random dominance | Strategy regression | Review strategy logic, check for bugs |
| Rank instability | Insufficient sample size | Increase `n_per`, rerun |

For any FAIL, check `strategy_sanity.md` for the specific test message and recommended action.

4. **Rerun with higher N (if sample-size related):**

```bash
uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml --n_per 5000
```

5. **Only after investigation and fix:** Re-execute from Step 2.

### Gate Logic Summary

| Sanity Result | Exit Code | Action |
|---------------|-----------|--------|
| All PASS | 0 | Proceed to next step |
| Any WARN | 0 | Proceed (review warnings) |
| Any FAIL | 1 | **STOP** — investigate before proceeding |
| All SKIP | 0 | Proceed (no outcomes data for tests) |

**Key:** WARN does not block; only FAIL blocks.

---

### Blessed Run Registry

See [CANONICAL_BIDLESS_RUNS.md](CANONICAL_BIDLESS_RUNS.md) for the current blessed runs and promotion history.

## Related Reports

- [Phase 0 Bidless Report](../04_reports/phase0/phase0_bidless_20260207.md) — Consolidated findings with embedded charts and provenance
