# Data contracts

This folder documents **stable schemas** produced/consumed by the project.
If you change a schema, update the relevant doc and bump schema versions where applicable.

## Run artifacts

- **meta.json (schema v2):** see `docs/01_core/schemas/meta_json.md`
- **results JSON**: Strategy performance metrics including scoring/points aggregates; see `docs/01_core/SCORING.md`
- **JSONL game log (schema v6):** see below

## JSONL Game Log Schema

Source: `src/bid_euchre/logging/game_logger.py`

Each `hand_end` record contains:

| Field | Type | Since | Notes |
|-------|------|-------|-------|
| `schema_version` | int | v1 | Always present; current = 6 |
| `event` | str | v1 | Always `"hand_end"` |
| `run_id` | str | v1 | Run identifier |
| `strategy_id` | str | v1 | Strategy name |
| `deal_id` | int | v1 | Hand index within run |
| `seed` | int\|null | v1 | RNG seed (null if nondeterministic) |
| `contract` | str | v1 | `"suit"`, `"high"`, or `"low"` |
| `trump` | str\|null | v1 | `"C"`, `"D"`, `"H"`, `"S"` or null |
| `leader` | int | v1 | First-trick leader seat (0–3) |
| `t0` | int | v1 | Tricks won by team 0 (seats 0 & 2) |
| `t1` | int | v1 | Tricks won by team 1 (seats 1 & 3) |
| `features` | list | v1 | 4 feature dicts (one per seat) |
| `scores` | list\|null | v2 | 4 scalar scores; null on pre-v2 logs |
| `hands` | list\|null | v3 | 4 hand contents; null on pre-v3 logs |
| `winning_bid` | int\|null | v4 | High bid; null on pre-v4 logs |
| `dealer_position` | int\|null | v5 | Dealer seat (0–3); null on pre-v5 logs |
| `bidder_position` | int\|null | v5 | Auction winner seat; null on pre-v5 logs |
| `redeal_flag` | bool\|null | v6 | True if all players passed (all-pass redeal); null on pre-v6 logs |
| `made_bid` | bool\|null | v6 | True if declaring team made their bid; null on pre-v6 logs |
| `timestamp` | str | v1 | ISO-8601 timestamp |

**Backward compatibility:** All versioned fields have `null` defaults. Old logs can be read safely using `.get(field)`.

**Filtering note:** `redeal_flag=true` records have `t0=0, t1=0` (no play occurred). Exclude them when computing comparative metrics.

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

**Legacy paths** (may exist locally; no longer tracked):
- `data/_deprecated/` - Old dashboard PNGs
- `data/hand_logs/` - Loose experiment logs
- `data/training/` - Training CSVs
- `data/models/` - Model binaries / legacy models
- `data/reports/` - Top-level aggregated reports

These paths are now ignored by git. Do not write new outputs to these locations.

### Migration note

If you have local files in legacy paths (`data/models/`, `data/training/`, etc.), they are now ignored by git. You can:
- Keep them locally (ignored)
- Delete them manually if no longer needed
- Archive them externally if important

Going forward, runner outputs must land under `data/runs/<run_id>/`.

## Notes
- Keep schemas small and versioned.
- Prefer adding new fields over deleting/renaming existing ones (backward compatibility).
