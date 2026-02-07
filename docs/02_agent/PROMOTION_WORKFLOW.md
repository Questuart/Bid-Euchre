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
from bid_euchre.models.splits import load_split_manifest, verify_split_manifest
manifest = load_split_manifest("path/to/split_manifest.json")
verify_split_manifest(manifest, train_df, test_df)  # Raises on mismatch
```

## Freeze-Before-Test

Artifact freeze prevents accidental modification between training and evaluation.

**Requirements:**
- Artifact must be frozen before any promotion evaluation
- Frozen artifacts contain `frozen_at` (ISO timestamp) and `artifact_sha256` (integrity hash)
- Verification recomputes hash excluding `artifact_sha256` field, compares to stored value
- Re-freezing an already-frozen artifact raises `ValueError`

**Key files:**
- `src/bid_euchre/models/freeze.py` — `freeze_artifact()`, `verify_frozen()`, `require_frozen()`

**Usage:**
```python
from bid_euchre.models.freeze import freeze_artifact, verify_frozen, require_frozen

# After training
freeze_artifact("path/to/olsa_v1.json")

# Before evaluation
verify_frozen("path/to/olsa_v1.json")  # Raises on tamper

# In promotion-track code
artifact = require_frozen("path/to/olsa_v1.json", strict=True)
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

**Makefile target:**
```bash
make promotion-gate   # Run the full promotion gate locally
```

**CI behavior:** The promotion gate step runs only on PRs with the `promotion` label. It is a hard-fail gate — a failing promotion gate blocks the PR from merging.

## Lint Rules

The repo linter enforces promotion contract rules:

### `registry-requires-gate-reference`
Reports under `docs/04_reports/` (excluding `README.md`) must reference gate evidence (e.g., `notebook_gate.json`, `batch_gate.json`, `gate_status`).

### `canonical-runs-registry-consistency`
If a code registry file exists and a doc registry file changes, both must be updated together (and vice versa). Currently no-op since the code registry was removed in #305.

## Reviewer Checklist

When reviewing a promotion-track PR, verify:

- [ ] Split manifest emitted (`split_manifest.json`) with correct split type
- [ ] Artifact frozen (`frozen_at` and `artifact_sha256` present)
- [ ] Notebook gate passing (`notebook_gate.json` with `gate_status: PASS`)
- [ ] PR has `promotion` label and CI gate passed
- [ ] Report references gate evidence (lint rule enforced)
- [ ] Repro command with `--seed` included in PR description
