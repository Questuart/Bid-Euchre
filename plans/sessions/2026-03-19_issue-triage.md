# Issue Triage — 37 Open Issues

**Date:** 2026-03-19
**Goal:** Categorize all 37 open issues by priority/domain, identify closable issues, and define actionable batches.

## Summary

| Category | Count | Action |
|----------|-------|--------|
| Close immediately (already fixed) | 6 | PR #949 merged but didn't auto-close |
| Close (insufficient detail / won't-fix) | 1 | #1004 |
| Already closed (other PRs) | 4 | #970, #986, #987, #960 |
| P0 — Data safety | 3 | Batch A |
| P1 — Functional bugs | 4 | Batch B |
| P1-P2 — index.py | 4 | Batch C |
| P1 — CI infrastructure | 1 | Batch D (reduced — 3 already closed) |
| P2 — Review infra refactor | 3 | Batch E |
| P2 — Convention follow-ups | 4 | Batch F |
| P2 — Report data | 2 | Batch G |
| P2 — Code quality / DRY / docs | 2 | Batch H (reduced — #960 closed) |
| P3 — Future wiring | 3 | Batch I |
| **Remaining open** | **26** | |

---

## 1. Close Immediately (6 issues)

PR #949 was merged to main with `Closes #935, #937, #890, #925, #944, #943` in the body,
but GitHub failed to auto-close them. Verify the fixes are on main and close manually.

| Issue | Title | Fixed By |
|-------|-------|----------|
| #890 | follow-up for PR #889 | PR #949 (manifest regeneration) |
| #925 | follow-up for PR #923 | PR #949 (manifest regeneration) |
| #935 | Duplicate severity-mapping logic | PR #949 (review_common.py extraction) |
| #937 | Missing multi-seed merge test | PR #949 (test added) |
| #943 | worktree-guard unbounded creation | PR #949 (guard fix) |
| #944 | follow-up for PR #942 | PR #949 (manifest regeneration) |

## 2. Close as Won't-Fix (1 issue)

| Issue | Title | Reason |
|-------|-------|--------|
| #1004 | Fragile test assertions (2 unspecified) | No file refs, no line numbers, no specifics. Unactionable. |

---

## 3. Prioritized Batches

### Batch A — Data Safety (P0) — `memory.py` hardening

**Risk:** Silent data loss from crash, corruption, or concurrent writes.

| Issue | Title | Severity |
|-------|-------|----------|
| #950 | memory.py silent total data loss on partial JSON corruption | P0 |
| #951 | memory.py non-atomic file writes risk truncation | P0 |
| #1002 | save_memory() no file locking for concurrent writes | P0 |

**Approach:** Single PR. Atomic write (write-to-temp + fsync + rename) fixes #951.
Graceful partial load (skip bad entries, don't discard all) fixes #950.
flock() on read-modify-write cycle fixes #1002.

**Estimated scope:** 1 file (`memory.py`) + tests. ~50 lines changed.

---

### Batch B — Ops Functional Bugs (P1)

| Issue | Title | Severity |
|-------|-------|----------|
| #967 | ops.py --force not passed to git | P1 bug |
| #954 | compaction partial archive blocks re-archival | P1 bug |
| #959 | compaction symlink traversal | P1 safety (low practical risk) |
| #938 | flock/rename race in event draining | P1 theoretical race |

**Approach:** Single PR across ops tooling. All are small fixes (guard clauses, cleanup).

**Estimated scope:** 3-4 files, ~80 lines changed.

---

### Batch C — `index.py` Issues (P1-P2)

| Issue | Title | Severity |
|-------|-------|----------|
| #952 | Hardcoded CWD-relative paths bypass injected params | P1 |
| #953 | Missing FTS5 AFTER UPDATE trigger | P1 (latent) |
| #956 | Staleness check full table scan on every query | P2 perf |
| #957 | sources_indexed counter inaccurate | P2 accuracy |

**Approach:** Single PR. All in `index.py`. The hardcoded paths (#952) and
FTS trigger (#953) are correctness issues; the others are quality.

**Estimated scope:** 1 file + tests. ~60 lines changed.

---

### Batch D — CI / Review Infrastructure (P1)

| Issue | Title | Severity |
|-------|-------|----------|
| #934 | CI classifier input mismatch with paths-filter | P1 |

**Note:** #970, #986, #987 were already closed by other PRs. Only #934 remains.

**Approach:** Align CI classifier to consume dorny/paths-filter output directly.

**Estimated scope:** 1-2 files, ~20 lines.

---

### Batch E — Review Infra Refactoring (P2)

| Issue | Title | Severity |
|-------|-------|----------|
| #936 | Inconsistent JSON schema between precheck/review state | P2 |
| #829 | Review driver should checkout PR branch before Codex | P2 refactor |
| #830 | Port reversed-format parser to plan review adapter | P2 completeness |

**Approach:** Single PR. Schema alignment (#936) first, then branch checkout (#829),
then parser port (#830).

**Estimated scope:** 3 files, ~100 lines.

---

### Batch F — Convention Follow-ups (P2)

| Issue | Title | Severity |
|-------|-------|----------|
| #946 | follow-up for PR #945 (test assertion) | P2 |
| #963 | follow-up for PR #948 (status files) | P2 |
| #995 | follow-up for PR #993 (plan claim scope) | P2 |
| #1001 | manifest governing_plan empty in 7/12 manifests | P2 |

**Approach:** Single batch PR. Manifest metadata fixes + minor convention items.

**Estimated scope:** ~10 files (mostly report manifests), ~40 lines of code.

---

### Batch G — Report Data Quality (P2)

| Issue | Title | Severity |
|-------|-------|----------|
| #921 | R2 FULL hypothesis_outcomes.csv stale R1 values | P2 data |
| #1003 | R3 seed downgrade / R2 caveat removal | P2 interpretive |

**Approach:** #921 requires regenerating R2 hypothesis data from correct source.
#1003 requires reviewing and potentially restoring interpretive context.
Single PR.

**Estimated scope:** 2-3 report files, careful data regeneration.

---

### Batch H — Code Quality / DRY / Docs (P2)

| Issue | Title | Severity |
|-------|-------|----------|
| #958 | Extract duplicated _find_repo_root() | P2 DRY |
| #955 | CLI docstrings --json position | P2 docs |

**Note:** #960 was already closed.

**Approach:** Single PR. Extract shared utility + fix docstrings.

**Estimated scope:** 5 files, ~35 lines.

---

### Batch I — Watchdog Wiring (P3 — Future)

| Issue | Title | Severity |
|-------|-------|----------|
| #928 | Wire CI event producers for check_ci_stuck() | P3 |
| #929 | Wire scope fields in task_state for scope drift | P3 |
| #930 | Wire retry_attempted and task_rerouted events | P3 |

**Approach:** These are Phase 3D plumbing that enables watchdog features.
Not blocking anything currently. Defer until ops infrastructure is actively used.

**Label:** `deferred`, `enhancement`

---

## 4. Recommended Execution Order

1. ~~**Close 7 issues**~~ ✅ Done (6 from PR #949 + 1 won't-fix)
2. **Batch A** (P0 data safety) — highest priority, single focused PR
3. **Batch B** (P1 ops bugs) — next, small fixes
4. **Batch D** (P1 CI #934) — single issue, CI classifier alignment
5. **Batch C** (P1-P2 index.py) — self-contained
6. **Batch F** (P2 conventions) — manifest fixes
7. **Batch G** (P2 report data) — data regeneration
8. **Batch E** (P2 review refactor) — larger refactor
9. **Batch H** (P2 quality) — low urgency DRY/docs
10. **Batch I** (P3 wiring) — defer

### Parallelism Opportunities

- **Batches A + D** can run in parallel (disjoint files: memory.py vs CI workflow)
- **Batches C + B** can run in parallel (index.py vs ops/compaction.py)
- **Batches F + G + H** are all P2 and can be combined into 1-2 PRs

## 5. Label Gaps

Issues missing labels that should be added:

| Issue | Missing Label | Should Be |
|-------|--------------|-----------|
| #890 | (no labels) | follow-up, fix:convention |
| #925 | (no labels) | follow-up, fix:convention |
| #960 | (no labels) | follow-up, fix:docs |
| #1003 | (no labels) | follow-up, fix:docs |
| #928, #929, #930 | (no fix: label) | enhancement |

## Outcome
- Closed 7 issues (6 from PR #949 auto-close failure + 1 won't-fix #1004)
- Discovered 4 more already closed (#970, #986, #987, #960)
- Added missing labels to 5 issues (#960 label retroactive, #928, #929, #930, #1003)
- **26 open issues remain**, organized into 9 batches (A through I)
- Recommended execution: Batch A (P0 data safety) → B (P1 ops bugs) → D (P1 CI) → C (index.py) → F/G/E/H → I (defer)
