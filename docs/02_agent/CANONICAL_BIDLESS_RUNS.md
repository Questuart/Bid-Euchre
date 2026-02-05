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
| canonical_bidless_outcomes_matrix_shallow | TBD | - | - | 42 | 2000 | 300K | - | - | - | - | artifacts/canonical_summary.json | - |
| canonical_bidless_outcomes_zoom | TBD | - | - | 42 | 50000 | 3.3M | - | - | - | - | artifacts/canonical_summary.json | - |

## How to Regenerate

Run the canonical experiments with these commands:

```bash
uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_dataset_greedy.yaml --emit-bidless-dataset --emit-bidless-outcomes-dataset

uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_matrix_shallow.yaml

uv run python experiments/run_experiment.py --seed 42 --config experiments/configs/canonical_bidless_outcomes_zoom.yaml
```

## How to Promote

1. **Run the canonical experiment** using one of the commands above
2. **Generate report**:
   ```bash
   uv run python scripts/generate_report.py --run-dir data/runs/<run_id>
   ```
3. **Verify `artifacts/canonical_summary.json`** exists and shows expected PASS/WARN/FAIL/SKIP counts
4. **Update registry table** with run metadata:
   - Replace TBD with actual run_id
   - Fill in date, git_sha, and validation counts
5. **Commit registry update** with PR linking to run provenance

## Validation Criteria

A run is eligible for promotion when:
- **FAIL = 0** — No failing sanity tests
- **WARN ≤ 2** — At most minor warnings (e.g., marginal thresholds)
- **Determinism verified** — Same seed + config reproduces identical results
