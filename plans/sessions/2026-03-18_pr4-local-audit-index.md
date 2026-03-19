# PR-4: Local Audit Index

**Date:** 2026-03-18
**Parent plan:** `plans/sessions/2026-03-15_autonomous-agent-ops-workflow.md` (PR-4)
**Branch:** `codex/steward-author-c`

## Goal

Implement the two-layer memory system: curated memory for stable operator facts
plus a local SQLite audit index over execution logs, CI/review outcomes,
checkpoints, and manifests for searchable history. Add session compaction for
non-lossy context archival.

## Deliverables

### New modules (src/bid_euchre/ops/)

| File | Purpose |
|------|---------|
| `index.py` | SQLite FTS5 audit index — schema, build/rebuild, query helpers |
| `memory.py` | Curated memory — ingestion, provenance validation, query |
| `compaction.py` | Session compaction — non-lossy archive, artifact index |

### New scripts (scripts/internal/)

| File | Purpose |
|------|---------|
| `build_audit_index.py` | CLI to build/rebuild the audit index |
| `build_curated_memory.py` | CLI to ingest/update curated memory |
| `compact_session_context.py` | CLI to compact and archive session context |

### ops.py extensions

New subcommands: `memory`, `index`, `compact`, `query`

### Runtime storage (gitignored)

| Path | Purpose |
|------|---------|
| `.claude/runtime/audit_index/` | SQLite database file |
| `.claude/runtime/curated_memory/` | JSON memory store |
| `.claude/runtime/session_archive/` | Archived session context |

### Tests

| File | Coverage |
|------|----------|
| `tests/unit/test_ops_index.py` | Index build, query, FTS, graceful degradation |
| `tests/unit/test_ops_memory.py` | Memory CRUD, provenance validation |
| `tests/unit/test_ops_compaction.py` | Compaction, archive lookup, failure injection |

## Architecture Decisions

1. **SQLite FTS5** for audit index — lightweight, no external deps, good enough
   for operational queries. No DuckDB needed.
2. **JSON file** for curated memory — small, explicit, human-readable. Not SQLite
   because curated memory is small (<100 entries) and benefits from easy inspection.
3. **Provenance-backed memory** — every curated entry has `source_file`, `added_by`,
   `added_at` fields. No anonymous entries.
4. **Non-lossy compaction** — archived sessions retain full detail on disk, with a
   metadata index for retrieval. Compaction produces a summary + artifact index,
   not an opaque replacement.
5. **Graceful degradation** — all query functions return empty/fallback results when
   index is stale or absent. Never crash on missing index.

## SQLite Schema

```sql
CREATE TABLE sources (
    source_id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,  -- 'event', 'checkpoint', 'manifest', 'state', 'execution_log', 'review'
    file_path TEXT NOT NULL,
    indexed_at TEXT NOT NULL,
    file_mtime TEXT,
    file_size INTEGER
);

CREATE VIRTUAL TABLE entries USING fts5(
    source_id,
    entry_type,    -- 'event', 'checkpoint_step', 'manifest_artifact', 'rung_state', 'log_entry', 'review_outcome'
    timestamp,
    content,       -- searchable text content
    metadata,      -- JSON blob for structured data
    content=''     -- contentless for space efficiency
);

CREATE TABLE index_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

## Implementation Order

1. Write session plan (this file)
2. Implement `ops/index.py` — schema, build, query
3. Implement `ops/memory.py` — CRUD, provenance
4. Implement `ops/compaction.py` — archive, metadata index
5. Add CLI scripts + ops.py subcommands
6. Add unit tests (parallel with 2-4 where possible)
7. Run `make check-quiet`
8. Commit and open PR

## Validation Plan

### Automated tests
- Unit tests for index build/rebuild idempotency
- Unit tests for FTS query with source-backed results
- Unit tests for curated memory CRUD + provenance
- Unit tests for compaction archive + lookup
- Failure injection: stale index, malformed artifacts, provenance-invalid memory,
  empty index queries, already-archived sessions

### Manual smoke
- Build index from current runtime artifacts
- Run representative queries
- Verify source-backed references in answers
- Run compaction on test fixture

### Rollback path
- All new files are additive — removal reverts to pre-PR state
- Runtime storage is gitignored — no cleanup needed
- No changes to existing ops modules

## Outcome
<!-- Filled after implementation -->
