# Data Contract Rules

> **Authoritative sources:**
> - @docs/01_core/DATA_CONTRACT.md
> - @docs/01_core/METRICS.md
> - @docs/01_core/RULES.md

## Output Policy

**Golden rule:** No generated outputs outside `data/runs/<run_id>/...`

**Commit policy:**
- ✅ `data/fixtures/**` only (tiny test fixtures)
- ❌ `data/runs/`, `data/reports/`, `data/models/`, `data/training/`

## What Counts as Contract Change

Changes to any of these require doc updates + tests:

| Area | Contract Doc | Required Action |
|------|--------------|-----------------|
| Game rules, trick resolution | RULES.md | Unit + integration tests |
| Logging fields, schemas | DATA_CONTRACT.md | Schema version bump |
| Metrics, aggregation | METRICS.md | Verify rollup compatibility |
| Scoring logic | RULES.md §6 | Scoring tests |

## Testing Requirements

- **Rules/scoring changes:** unit tests + integration tests
- **Logging schema changes:** update `docs/01_core/schemas/`
- **Metrics changes:** verify drift detection still works

See @docs/01_core/DATA_CONTRACT.md for full schema details.
