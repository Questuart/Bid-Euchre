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

**Default behavior:** Training defaults to `two_way` (exploration is the common workflow). Promotion-track training must explicitly pass `--split-type three_way`. The eligibility engine enforces this at gate time.

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
- Frozen artifacts contain `frozen_at` (ISO timestamp) and `artifact_sha256` (content-based integrity hash)
- `artifact_sha256` is computed from a canonical JSON serialization of the artifact content (excluding `frozen_at` and `artifact_sha256` fields themselves), using `sort_keys=True` and compact separators
- `verify_frozen()` recomputes the content hash and compares it to the stored `artifact_sha256` — detecting any post-freeze tampering
- The eligibility engine uses `verify_frozen()` for integrity verification (not raw field checks)
- Re-freezing an already-frozen artifact raises `ValueError`
- Artifacts frozen before content-based hashing must be re-frozen to pass verification

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

## Semantic Gate

The semantic gate provides deep health and quality checks for model evaluation data. It runs inside the model-rung evaluation notebook and emits machine-readable gate artifacts.

**Dual-gate flow:**
1. **Val gate** — run on validation split during HITL development
2. **Freeze** — freeze model artifact after val gate passes
3. **Test gate** — run on test split after freeze (final verification)
4. **Promotion** — both val and test gates must PASS

**File naming convention:**
- `semantic_gate_val.json` — val split gate artifact
- `semantic_gate_test.json` — test split gate artifact

**Requirements for promotion:**
- Both `semantic_gate_val.json` and `semantic_gate_test.json` must exist
- Both must have `gate_status: "PASS"`
- The eligibility engine checks both with distinct rule names (`semantic_gate_val`, `semantic_gate_test`)

**Key files:**
- `src/bid_euchre/diagnostics/semantic_gate.py` — `compute_semantic_gate()`, `emit_semantic_gate()`
- `src/bid_euchre/diagnostics/split_guard.py` — `require_split()` access control
- `src/bid_euchre/reporting/eligibility.py` — `check_semantic_gate()` eligibility check
- notebooks/_templates/01_model_rung_template.py — evaluation notebook template

## CI Gate

The CI workflow enforces promotion checks on PRs labeled `promotion`.

**Trigger:** Add the `promotion` label to a PR.

**What runs:**
1. `make repo-lint` — repository boundary linter (includes promotion registry lint rules)
2. `make notebook-run` (SMOKE mode with `--gate-output-dir`) — notebook preflight
3. Notebook gate assertion — verifies `gate_status == PASS`
4. Artifact freeze check — verifies all model artifacts in ARTIFACT_DIR pass `verify_frozen()` with content-based hash validation (required, not opt-in)
5. Rollup validation — verifies ROLLUP_JSON is readable and warns if `batch_purpose != "promotion"`
6. Split manifest validation (optional) — if SPLIT_MANIFEST_DIR is provided, verifies manifests have `three_way` split_type
7. Semantic gate validation (required) — verifies both `semantic_gate_val.json` and `semantic_gate_test.json` exist and have `gate_status == PASS`

**Makefile target:**
```bash
# ARTIFACT_DIR, ROLLUP_JSON, and SEMANTIC_GATE_DIR are required for promotion gate
make promotion-gate ARTIFACT_DIR=/path/to/artifacts ROLLUP_JSON=/path/to/rollup.json SEMANTIC_GATE_DIR=/path/to/gates

# Optionally include split manifest validation
make promotion-gate ARTIFACT_DIR=/path/to/artifacts ROLLUP_JSON=/path/to/rollup.json SPLIT_MANIFEST_DIR=/path/to/splits SEMANTIC_GATE_DIR=/path/to/gates
```

**CI behavior:** The promotion gate step runs only on PRs with the `promotion` label. It is a hard-fail gate — a failing promotion gate blocks the PR from merging. `ARTIFACT_DIR`, `ROLLUP_JSON`, and `SEMANTIC_GATE_DIR` must be set as repository variables for promotion PRs to pass CI. `SPLIT_MANIFEST_DIR` is optional.

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

### `semantic-gate-schema`
Semantic gate JSON files (`semantic_gate*.json`) must have full schema: 11 top-level required fields (`schema_version`, `gate_status`, `created_at_utc`, `active_split`, `mode`, `seed`, `total_hands`, `total_checks`, `passed_checks`, `failed_checks`, `checks`) and each check entry must have 6 required fields (`check_id`, `category`, `status`, `threshold`, `observed`, `detail`).

### `split-manifest-schema`
Split manifest JSON files (`split_manifest*.json`) must have valid schema (required fields: `schema_version`, `split_type`, `split_seed`, `total_hand_ids`, `partition_hashes`) and `split_type` must be `two_way` or `three_way`.

## Arc D Gate Model

Arc D uses an **always-advance** gate model for iterative model improvement.
The gate runner evaluates a candidate model against the current incumbent and
returns one of three outcomes:

| Outcome | Meaning |
|---------|---------|
| **PROMOTED** | Model advances to the next rung AND becomes the new incumbent (replaces current best) |
| **ADVANCED** | Model advances to the next rung but does NOT become incumbent (insufficient improvement over current best) |
| **HALT** | Model fails health or quality checks; advancement is blocked |

### Dual-Arm Convention

Arc D trains two model arms per rung:

- **OLSa** (constrained) — locked 3/1/1 feature set per contract type; used for attribution and interpretability
- **OLSa_Full** (promotional) — forward-selected from all 39 features; used for promotional gate evaluation

The promotional arm (OLSa_Full) determines whether the candidate advances or halts.
The constrained arm (OLSa) provides stable attribution baselines across rungs.

### Artifact Validation

- **Hybrid OLSa schema:** `docs/01_core/schemas/hybrid_olsa_v1.md`
- **Bundle validation:** `src/bid_euchre/validation/arc_d_bundle.py` validates rung bundle structure (both arms, split manifest, training report)
- **Gate runner:** `src/bid_euchre/validation/arc_d_gate.py` implements the promotion gate logic (metric normalization, threshold comparison, decision emission)
- **CLI entry point:** `scripts/internal/run_arc_d_gate.py`
- **Artifact integrity:** Both arms must pass `verify_frozen()` from `src/bid_euchre/models/freeze.py` before gate evaluation

### Gate Flow

1. Train both arms (OLSa + OLSa_Full) with shared split manifest
2. Freeze both artifacts
3. Evaluate both arms on held-out test split
4. Run gate: compare OLSa_Full metrics against incumbent thresholds
5. Emit promotion decision (PROMOTED / ADVANCED / HALT) with reasons

## Reviewer Checklist

When reviewing a promotion-track PR, verify:

- [ ] Split manifest emitted (`split_manifest.json`) with correct split type
- [ ] Artifact frozen (`frozen_at` and `artifact_sha256` present)
- [ ] Notebook gate passing (`notebook_gate.json` with `gate_status: PASS`)
- [ ] Semantic gates passing (both `semantic_gate_val.json` and `semantic_gate_test.json` with `gate_status: PASS`)
- [ ] PR has `promotion` label and CI gate passed
- [ ] Report references gate evidence (lint rule enforced)
- [ ] Repro command with `--seed` included in PR description
