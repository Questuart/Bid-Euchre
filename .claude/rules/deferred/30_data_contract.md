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

## Knowledge-Base Commit Policy (Primitive C)

> **Authoritative sources:**
> - `plans/steward_platform/adrs/010-mcp-memory-service-evaluation.md` §Decision
> - `plans/steward_platform/3_primitive_C/shaping.md` §4.7

ADR 010 binds the steward platform to **"only promoted KB artifacts
are committed."** The tracked vs. gitignored path split:

**Tracked (committed):**
- `knowledge/NOTES.md`, `PLAYBOOKS.md`, `anti_patterns.md`,
  `harness_assumptions.md`, `agent_readability_scorecard.md`,
  `external_signal_sources.md`, `INDEX.md`
- `knowledge/adr/**/*.md`
- `knowledge/incidents/**/*.md`
- `knowledge/_promoted/**/*.md` — post-promotion archive; the audit trail

**Gitignored (NOT committed):**
- `knowledge/_candidates/**` — archivist inflow; session-local
- `knowledge/_scratch/**` — ad-hoc KB scratch space

**Promotion is operator-gated.** No automatic / autonomous promotion
path. Use `/run-archivist --promote <candidate>` or edit the target
file directly. Every promotion emits a `kb_artifact_promoted` event
with a mandatory `operator_id` field. Rollback (`--unpromote` or `git
revert`) emits `kb_artifact_unpromoted`.

**Review-driver V7 precheck** (behind `ENABLE_V7_COMMIT_POLICY` flag
until Primitive A archivist event emission is live) blocks PRs that
add `_promoted/` entries without a matching upstream
`archivist_candidate_generated` event (audit-trail integrity).
