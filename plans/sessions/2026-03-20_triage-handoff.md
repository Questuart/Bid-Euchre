# Triage Handoff — Lane Coordination (2026-03-20)

## For: author-a (from author-b)

Both lanes produced independent triage plans on the same 37-issue backlog. We
agreed on closures (11 issues closed, 26 remain) and converged on batch
boundaries. This handoff records the lane split.

## Your assignment: Batch 1 — `memory.py` Data Safety

**Issues:** #950, #951, #1002
**File:** `src/bid_euchre/ops/memory.py`
**Priority:** P0 — highest data-loss risk

| Issue | Title | Fix approach |
|-------|-------|-------------|
| #950 | Silent total data loss on partial JSON corruption | Per-entry error handling in `load_memory()` — catch `KeyError` per entry, skip corrupt entries instead of discarding entire store |
| #951 | Non-atomic file writes risk truncation | Atomic write pattern: write to `.tmp` then `os.rename()` |
| #1002 | No file locking for concurrent writes | `fcntl.flock()` wrapper around the write path |

**Scope boundary:** Only `memory.py`. The related compaction bugs (#954, #959)
are in Batch 3 (unassigned, available after these merge).

## My assignment: Batch 2 — `index.py` Correctness & Performance

**Issues:** #952, #953, #956, #957
**File:** `src/bid_euchre/ops/index.py`
**Priority:** P1

**Zero file overlap with Batch 1.** We can work in parallel with no coordination.

## Reconciled triage plan

Full consolidated plan with all 7 batches + backlog:
`plans/sessions/2026-03-20_issue-triage.md` (in author-b worktree)

Your original plan:
`plans/sessions/2026-03-19_issue-triage.md` (in author-a worktree)

## After these batches merge

Unassigned batches available for either lane:
- **Batch 3** (P1): #967, #954, #959, #938 — ops bugs (ops.py, compaction.py, events)
- **Batch 4** (P2): #934 — CI classifier fix
- **Batch 5** (P2): #936, #946, #955, #958, #963, #995, #1001 — convention batch 4
- **Batch 6** (P3): #921, #1003 — Arc D v2 report polish
- **Batch 7** (P3): #829, #830 — review infra
