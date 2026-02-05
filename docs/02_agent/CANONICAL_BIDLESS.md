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
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_greedy.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
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
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_mixed_play.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
```

### A.2) Training Dataset (Features + Outcomes, Single-Policy: Glutton)

**Config**: `experiments/configs/canonical_bidless_dataset_glutton.yaml`

**Purpose**: Collect hand features AND outcome labels for ML training using **glutton play policy**.

**Prerequisite**: Only run after play policy gate PASS (see [PLAY_POLICY_FREEZE.md](PLAY_POLICY_FREEZE.md)). Training labels must be single-policy and stable; switching policies mid-training invalidates prior labels.

**Strategies**: glutton only (1 strategy in self-play)

**Total hands**: 50,000 × 6 scenarios × 1 strategy = **300,000 hands**

**Command**:
```bash
PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_glutton.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset
```

### B) Shallow Matrix (Broad Coverage)

**Config**: `experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml`

**Purpose**: Cheap broad coverage across all 25 matchups for sanity checking.

**Strategies**: greedy, glutton, random_legal, always_highest, always_lowest (5 strategies)

**Matchups**: Full 5×5 matrix (25 ordered pairs including self-play)

**Total hands**: 2,000 × 6 scenarios × 25 matchups = **300,000 hands**

**Command**:
```bash
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml --seed 42
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
PYTHONPATH=src python experiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_zoom.yaml --seed 42
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
PYTHONPATH=src python scripts/generate_report.py \
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

For analyzing canonical runs in notebooks:

1. Set `DEMO_MODE = False` to use real data
2. Set `RUN_DIR` to point to your run directory:

```python
DEMO_MODE = False
RUN_DIR = "../../data/runs/<canonical_run_id>"
```

Diagnostics loaders prefer `bidless_outcomes.parquet` when present, so notebooks work without hand-level logs.

### Loading Outcomes Data

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
PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_greedy.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset

# Training dataset (single-policy glutton, for ML — requires gate PASS)
PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_glutton.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset

# Analysis dataset (multi-policy, for diagnostics)
PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_dataset_mixed_play.yaml --seed 42 --emit-bidless-dataset --emit-bidless-outcomes-dataset

# Shallow matrix (broad sanity checking)
PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml --seed 42

# Zoom run (high-precision decision cells)
PYTHONPATH=src uv run python experiments/run_experiment.py --config experiments/configs/canonical_bidless_outcomes_zoom.yaml --seed 42

# Generate report (after any run)
PYTHONPATH=src uv run python scripts/generate_report.py \
  --run-dir data/runs/<run_id>
```
