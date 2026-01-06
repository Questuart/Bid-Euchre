# Data contracts

This folder documents **stable schemas** produced/consumed by the project.
If you change a schema, update the relevant doc and bump schema versions where applicable.

## Run artifacts

- **meta.json (schema v2):** see `docs/01_core/schemas/meta_json.md`

## Directory Layout and Commit Policy

### Target layout (end-state)

```
data/
  fixtures/          # Committed: tiny, intentional test/doc fixtures
  runs/              # Ignored: all experiment outputs
    <run_id>/
      results/       # Machine-readable outputs (json/jsonl/csv/parquet)
      logs/          # JSONL hand logs / structured logs
      reports/       # Charts, dashboards, analyses
      splits/        # Train/test/val splits (if generated)
      artifacts/     # Model binaries, intermediate artifacts (if generated)
      meta.json      # Run metadata (schema v2)
      perf.json      # Performance metrics (optional)
```

### Policy

**The golden rule**: No generated outputs may be written outside `data/runs/<run_id>/...`

**Commit policy:**
- ✅ **Allowed**: `data/fixtures/**` only (tiny, intentional; referenced by tests/docs)
- ❌ **Forbidden**: Any generated outputs (runs, logs, models, training data, dashboards)

**Legacy paths** (present today; to be removed from git in PR #14):
- `data/_deprecated/` - Old dashboard PNGs
- `data/hand_logs/` - Loose experiment logs
- `data/training/` - Training CSVs
- `data/models/` - Model binaries / legacy models
- `data/reports/` - Top-level aggregated reports

These are now ignored for new writes, but contain tracked artifacts that will be cleaned up in a future PR.

### Migration note

If you have local files in legacy paths (`data/models/`, `data/training/`, etc.), they are now ignored by git. You can:
- Keep them locally (ignored)
- Delete them manually if no longer needed
- Archive them externally if important

Going forward, runner outputs must land under `data/runs/<run_id>/`.

## Notes
- Keep schemas small and versioned.
- Prefer adding new fields over deleting/renaming existing ones (backward compatibility).
