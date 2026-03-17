# Archive Manifest — Arc D v2 Non-Canonical Outputs

**Date:** 2026-03-16
**Archive location:** `../Bid-Euchre-archive/arc_d_v2_noncanonical_20260316/`
**Reason:** Continuation-policy drift discovered during FULL backfill. R1+ datasets
were generated with rung-local continuation artifacts instead of the fixed R0 anchor.
All outputs are non-canonical and must be regenerated with the repaired pipeline.

## What Was Archived

### Reports (tracked, git rm'd)

- `docs/04_reports/arc_d_v2/cross_rung_deltas.csv`
- `docs/04_reports/arc_d_v2/r0/quick/` — full report bundle (manifests, results, decisions, charts, tables, evidence)
- `docs/04_reports/arc_d_v2/r1/quick/` — full report bundle
- `docs/04_reports/arc_d_v2/r2/quick/` — full report bundle
- `docs/04_reports/arc_d_v2/r3/quick/` — full report bundle

### Runtime State (tracked, git rm'd)

- `plans/arc_d_v2/r0/{advance_check.json, execution_log.jsonl, state.json}`
- `plans/arc_d_v2/r1/{advance_check.json, execution_log.jsonl, state.json}`
- `plans/arc_d_v2/r2/{advance_check.json, execution_log.jsonl, state.json}`
- `plans/arc_d_v2/r3/{advance_check.json, execution_log.jsonl, state.json}`

### Untracked/Gitignored Data (moved before this manifest)

- `data/runs/` — all av_* run directories
- `data/artifacts/arc_d/` — trained model artifacts (except r0/hybrid_r0_full.json which is the anchor)
- Runtime manifests and logs

## Archive Directory Structure

```
arc_d_v2_noncanonical_20260316/
├── artifacts/       # Trained model artifacts
├── manifests/       # Runtime manifests
├── reports/         # Report bundles (r0-r3)
│   └── arc_d_v2/
│       ├── cross_rung_deltas.csv
│       ├── r0/quick/
│       ├── r1/quick/
│       ├── r2/quick/
│       └── r3/quick/
├── runs/            # Dataset and experiment runs
└── runtime_state/   # Orchestrator state files
    ├── r0/{advance_check.json, execution_log.jsonl, state.json}
    ├── r1/{advance_check.json, execution_log.jsonl, state.json}
    ├── r2/{advance_check.json, execution_log.jsonl, state.json}
    └── r3/{advance_check.json, execution_log.jsonl, state.json}
```

## Why Non-Canonical

The orchestrator's `execute_step_1()` and `execute_step_2()` used a rung-local
continuation artifact probe that fell back to R0 only when the local artifact
was missing. For R1+ rungs where trained artifacts already existed from prior
runs, this meant the continuation policy could be a non-R0 artifact, breaking
the comparability contract that all rungs use the same continuation policy
for dataset generation.

## Governing Amendment

See `plans/arc_d_v2/amendments.md` — Amendment LA-5 documents all repair changes.

## Regeneration Plan

New canonical outputs will be generated with:
- Fixed R0 anchor enforcement (no rung-local probe)
- Shared pre-R3 datasets (R0/R1/R2 share the same base data)
- Updated scale: SMOKE=25, QUICK=5000, FULL=50000
- Global UIDs: dataset_seed, deal_uid, hand_uid
