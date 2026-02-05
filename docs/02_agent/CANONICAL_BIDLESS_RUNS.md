# Canonical Bidless Runs Registry

This file is the **single source of truth** for blessed canonical run IDs and their validation summaries.

## Promotion Rules

1. **Update only on intentional promotion** — Do not add runs speculatively
2. **Require full provenance** — Every promoted run must include:
   - Run ID (directory name in `data/runs/`)
   - Git SHA at time of run
   - Seed and n_per values
   - PASS/WARN/FAIL/SKIP counts from `artifacts/canonical_summary.json`
3. **Reference promotion artifacts** — The canonical artifacts are:
   - `artifacts/canonical_summary.json` (machine-readable)
   - `artifacts/canonical_summary.md` (human-readable)
4. **One row per config** — Each config has exactly one blessed run at a time

## Registry Table

| experiment_name | run_id | date | git_sha | seed | n_per | total_hands | PASS | WARN | FAIL | SKIP | canonical_summary_json_path | notes |
|-----------------|--------|------|---------|------|-------|-------------|------|------|------|------|------------------------------|-------|
| canonical_bidless_dataset_greedy | TBD | - | - | 42 | 50000 | 300K | - | - | - | - | artifacts/canonical_summary.json | - |
| canonical_bidless_dataset_glutton | TBD | - | - | 42 | 50000 | 300K | - | - | - | - | artifacts/canonical_summary.json | Only if gate PASS |
| canonical_bidless_outcomes_matrix_shallow | TBD | - | - | 42 | 2000 | 300K | - | - | - | - | artifacts/canonical_summary.json | - |
| canonical_bidless_outcomes_zoom | TBD | - | - | 42 | 50000 | 3.3M | - | - | - | - | artifacts/canonical_summary.json | - |

## Policy Freeze Record

Documents the frozen play policy decision for bidding model training.

| Field | Value |
|-------|-------|
| **Chosen policy** | TBD (greedy or glutton) |
| **Decision date** | TBD |
| **Gate run_id(s)** | TBD |
| **Gate output path** | `data/runs/<run_id>/artifacts/play_policy_gate.json` |
| **Gate result** | TBD (PASS/WARN/FAIL) |
| **Rationale** | TBD (1-2 sentences) |

### Update Process

1. Run gate: `PYTHONPATH=src uv run python scripts/play_policy_gate.py --seeds 42,43,44 --n-per 20000`
2. Record result in table above
3. If PASS: Run and promote glutton dataset
4. If WARN/FAIL: Keep greedy as frozen policy and document rationale

## How to Regenerate

Follow the [Promotion Checklist](CANONICAL_BIDLESS.md#promotion-checklist) for the full step-by-step procedure with sanity gates.

Quick reference commands (without gates—use checklist for full workflow):

```bash
PYTHONPATH=src uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_dataset_greedy.yaml --emit-bidless-dataset --emit-bidless-outcomes-dataset

PYTHONPATH=src uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml

PYTHONPATH=src uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_zoom.yaml
```

## How to Promote

See the full [Promotion Checklist](CANONICAL_BIDLESS.md#promotion-checklist) for the sequential procedure with sanity gates.

Summary:
1. Run dataset_greedy + generate report
2. Run matrix_shallow + `--fail-on-sanity-failures` gate
3. Run zoom (only if shallow passed) + `--fail-on-sanity-failures` gate
4. Verify `artifacts/canonical_summary.json` exists for each run
5. Update registry table with run metadata
6. Commit registry update with PR

## Validation Criteria

A run is eligible for promotion when:
- **FAIL = 0** — No failing sanity tests
- **WARN ≤ 2** — At most minor warnings (e.g., marginal thresholds)
- **Determinism verified** — Same seed + config reproduces identical results
