# Promotion Workflow

This document describes the end-to-end promotion workflow for advancing model artifacts from exploration to production.

## Overview

Promotion is the process of certifying that a model artifact (e.g., OLSa coefficients, B0 weights) meets quality and reproducibility standards before it can be used in production evaluation or published reports.

The workflow enforces three gates:
1. **Split manifest** — deterministic, grouped-by-hand_id train/test partitioning
2. **Artifact freeze** — immutable artifact with SHA256 integrity hash
3. **Notebook preflight** — SMOKE-mode notebook execution with gate artifact emission

## Prerequisites

Before submitting a promotion-track PR:

- Model artifact trained with `--split-type two_way` or `three_way` (split manifest emitted)
- Artifact frozen via `freeze_artifact()` (frozen_at + artifact_sha256 stamped)
- Notebook gate passing (`notebook_gate.json` with `gate_status: PASS`)

## Split Manifest Policy

Split manifests ensure reproducible and leakage-free train/test partitions.

**Requirements:**
- All splits are grouped by `hand_id` (4 seat rows per hand must stay together)
- Deterministic via `np.random.RandomState(seed)`
- Partition hashes (SHA256 of sorted hand_ids) recorded for verification
- Two-way splits (`train`/`test`) for exploration; three-way (`train`/`val`/`test`) for promotion-track

**Key files:**
- `src/bid_euchre/models/splits.py` — `SplitManifest`, `create_grouped_split()`, `verify_split_manifest()`

**Verification:**
```python
from bid_euchre.models.splits import SplitManifest, verify_split_manifest
manifest = SplitManifest.load("path/to/split_manifest.json")
verify_split_manifest(manifest, df, seed=42)  # Returns True if partition hashes match
```

## Freeze-Before-Test

Artifact freeze prevents accidental modification between training and evaluation.

**Requirements:**
- Artifact must be frozen before any promotion evaluation
- Frozen artifacts contain `frozen_at` (ISO timestamp) and `artifact_sha256` (integrity hash)
- `verify_frozen()` checks that both `frozen_at` and `artifact_sha256` are present (not None)
- The eligibility engine uses `verify_frozen()` for integrity verification (not raw field checks)
- Re-freezing an already-frozen artifact raises `ValueError`

**Key files:**
- `src/bid_euchre/models/freeze.py` — `freeze_artifact()`, `verify_frozen()`, `require_frozen()`

**Usage:**
```bash
# Auto-freeze via CLI (recommended for promotion-track training)
PYTHONPATH=src python scripts/train_olsa.py \
    --run-dir data/runs/... --seed 42 --output /tmp/artifacts/ --freeze
```

```python
from bid_euchre.models.freeze import freeze_artifact, verify_frozen, require_frozen

# After training (manual freeze)
freeze_artifact("path/to/olsa_v1.json")

# Before evaluation
verify_frozen("path/to/olsa_v1.json")  # Returns True/False

# In promotion-track code (strict gate)
require_frozen("path/to/olsa_v1.json", strict=True)  # Raises on not frozen
```

## Notebook Gate

Notebooks emit gate artifacts during execution that certify data pipeline health.

**Requirements:**
- Run notebooks with `--gate-output-dir` to emit gate artifacts
- Gate artifact schema is frozen at `NOTEBOOK_GATE_SCHEMA_VERSION = 1`
- `gate_status` must be `PASS` for promotion

**Key files:**
- `scripts/run_notebooks.py` — `--gate-output-dir` flag
- Gate output: `notebook_gate.json` in specified directory

## CI Gate

The CI workflow enforces promotion checks on PRs labeled `promotion`.

**Trigger:** Add the `promotion` label to a PR.

**What runs:**
1. `make repo-lint` — repository boundary linter (includes promotion registry lint rules)
2. `make notebook-run` (SMOKE mode with `--gate-output-dir`) — notebook preflight
3. Notebook gate assertion — verifies `gate_status == PASS`
4. Artifact freeze check — verifies all model artifacts in ARTIFACT_DIR pass `verify_frozen()` (required, not opt-in)

**Makefile target:**
```bash
# ARTIFACT_DIR is required for promotion gate
make promotion-gate ARTIFACT_DIR=/path/to/artifacts
```

**CI behavior:** The promotion gate step runs only on PRs with the `promotion` label. It is a hard-fail gate — a failing promotion gate blocks the PR from merging. `ARTIFACT_DIR` must be set as a repository variable for promotion PRs to pass CI.

## Lint Rules

The repo linter enforces promotion contract rules:

### `registry-requires-gate-reference`
Reports under `docs/04_reports/` (excluding `README.md`) must reference gate evidence (e.g., `notebook_gate.json`, `batch_gate.json`, `gate_status`).

### `canonical-runs-registry-consistency`
If a code registry file exists and a doc registry file changes, both must be updated together (and vice versa). Currently no-op since the code registry was removed in #305.

### `artifact-requires-freeze`
Model artifact JSON files (matching `olsa`, `b0`, `teacher` patterns) under `data/` must have a non-null `frozen_at` field.

### `gate-artifact-schema`
Gate artifact JSON files (`*gate*.json`) under `data/` must have valid schema (required fields: `schema_version`, `gate_status`, `created_at_utc`) and `gate_status` must be `PASS`.

### `split-manifest-schema`
Split manifest JSON files (`split_manifest*.json`) must have valid schema (required fields: `schema_version`, `split_type`, `split_seed`, `total_hand_ids`, `partition_hashes`) and `split_type` must be `two_way` or `three_way`.

## Reviewer Checklist

When reviewing a promotion-track PR, verify:

- [ ] Split manifest emitted (`split_manifest.json`) with correct split type
- [ ] Artifact frozen (`frozen_at` and `artifact_sha256` present)
- [ ] Notebook gate passing (`notebook_gate.json` with `gate_status: PASS`)
- [ ] PR has `promotion` label and CI gate passed
- [ ] Report references gate evidence (lint rule enforced)
- [ ] Repro command with `--seed` included in PR description
