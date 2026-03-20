# Issue Triage — 2026-03-20

## Context

37 open issues, all unassigned. Most created 2026-03-19 by post-merge review
automation. No new initiative work planned — this is a housekeeping session to
reduce the backlog into actionable batches and close stale items.

Both author-a and author-b produced independent triage plans. This document is
the **reconciled version** with lane assignments for parallel execution.

## Closures (completed)

### Already-fixed by PR #949 (GitHub didn't auto-close)
Closed: #890, #925, #935, #937, #943, #944

### Won't-fix / trivial / pre-closed
Closed: #960 (trivial doc typo), #970 (external dep), #986 (downstream of #970),
#987 (downstream of #970), #1004 (closed by another lane — unspecified instances)

**37 → 26 open issues remain.**

## Consolidated Batch Plan

After comparing both triages, the key difference was batch boundaries. Author-a
scoped Batch A tighter (memory.py only, 3 issues) and pulled compaction bugs into
a separate ops batch. Author-b grouped all persistence code together (5 issues).

**Adopted split:** Author-a's tighter scoping. Memory-only is a cleaner single-file PR.

### Batch 1 — `memory.py` Data Safety (author-a)

**Owner: author-a** · Priority: P0 · Single PR · File: `src/bid_euchre/ops/memory.py`

| Issue | Title | Fix |
|-------|-------|-----|
| #950 | Silent total data loss on partial JSON corruption | Per-entry error handling in `load_memory()` |
| #951 | Non-atomic file writes risk truncation | Atomic write via tmp+rename |
| #1002 | No file locking for concurrent writes | flock wrapper around write |

### Batch 2 — `index.py` Correctness & Performance (author-b)

**Owner: author-b** · Priority: P1 · Single PR · File: `src/bid_euchre/ops/index.py`

| Issue | Title | Fix |
|-------|-------|-----|
| #953 | Missing AFTER UPDATE trigger on FTS5 content-sync | Add trigger (correctness) |
| #952 | Hardcoded CWD-relative paths bypass injected params | Parameterize all paths |
| #956 | Full table scan with `stat()` on every query | Cache/TTL staleness check |
| #957 | `sources_indexed` counter inaccurate for compound ingestors | Fix counting logic |

### Batch 3 — Ops Bugs (unassigned)

Priority: P1 · Single PR · Files: `ops.py`, `compaction.py`, event code

| Issue | Title | Fix |
|-------|-------|-----|
| #967 | `worktrees archive --force` doesn't pass `--force` to git | Flag passthrough |
| #954 | Compaction partial archive blocks re-archival | Cleanup on failure |
| #959 | Compaction `delete_archive` follows symlinks | realpath containment check |
| #938 | flock/rename race condition in event draining | Atomic drain pattern |

### Batch 4 — CI/Process (unassigned)

Priority: P2 · Single PR

| Issue | Title | Fix |
|-------|-------|-----|
| #934 | CI classifier input mismatch with dorny/paths-filter | Fix input mapping |

### Batch 5 — Convention Follow-ups (unassigned)

Priority: P2 · Single PR · "Convention batch 4" pattern

| Issue | Title |
|-------|-------|
| #936 | Inconsistent JSON schema between precheck/review-loop |
| #946 | follow-up for PR #945 |
| #955 | CLI docstrings --json position wrong |
| #958 | Extract duplicated `_find_repo_root()` |
| #963 | follow-up for PR #948 |
| #995 | follow-up for PR #993 |
| #1001 | manifest governing_plan empty in 7/12 evidence manifests |

### Batch 6 — Arc D v2 Report Polish (unassigned)

Priority: P3 · Single PR · Non-blocking

| Issue | Title |
|-------|-------|
| #921 | R2 hypothesis_outcomes.csv stale R1-era values |
| #1003 | R3 seed downgrade / R2 caveat removal reduce interpretive context |

### Batch 7 — Review Infra (unassigned)

Priority: P3 · Single PR

| Issue | Title |
|-------|-------|
| #829 | Review driver should checkout PR branch before running Codex |
| #830 | Port reversed-format parser to codex_plan_review_adapter.py |

### Backlog — Defer Indefinitely

| Issue | Title |
|-------|-------|
| #928 | Wire CI event producers for check_ci_stuck() watchdog |
| #929 | Wire scope fields in task_state for check_scope_drift() watchdog |
| #930 | Wire retry_attempted and task_rerouted event emission |

## Lane Assignments

| Lane | Batch | Issues | File Scope |
|------|-------|--------|------------|
| **author-a** | 1 (memory.py) | #950, #951, #1002 | `memory.py` only |
| **author-b** | 2 (index.py) | #952, #953, #956, #957 | `index.py` only |

**No file overlap.** Batches can run in parallel with zero coordination needed.

Batches 3–7 are unassigned and available for either lane after their current
batch merges.

## Outcome

**Triage completed 2026-03-20.**

- Closed 11 issues (6 already fixed, 4 won't-fix, 1 pre-closed)
- **26 open issues** remain in 7 batches + 3 backlog
- **Parallel execution:** author-a → Batch 1 (memory.py), author-b → Batch 2 (index.py)
- Zero file overlap between active batches
