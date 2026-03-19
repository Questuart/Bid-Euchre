# Steward Review Batch Fixes

**Date:** 2026-03-18
**Goal:** Address verified findings from the steward review of PRs #875, #878, and #892 in three scoped follow-up PRs.

## Verified Findings

| ID | Source | Finding | Severity | Action |
|----|--------|---------|----------|--------|
| 875-H1 | #875 | `"PP1"` typo → vacuously true test (lines 561, 580) | CRITICAL | Fix |
| 875-M1/M2 | #875 | 2 tests removed with narrower replacements | MEDIUM | Restore |
| 878-H1 | #878 | Drain atomicity — dupes on crash, not loss | MEDIUM | Document |
| 878-H2 | #878 | Concurrent JSONL writes — no locking | MEDIUM | Fix |
| 878-M1 | #878 | Subprocess timeouts missing | FALSE | — |
| 878-M3 | #878 | Dead code: `count_events`, `drain_events` never called | LOW | Remove |
| 878-M5 | #878 | v1 role map falls back to raw role string | LOW | Fix |
| 892-M1 | #892 | Shell vars unquoted in Python heredoc | LOW | Fix |
| 892-M2 | #892 | Quarantine misses untracked files | CRITICAL | Fix |
| 892-M3 | #892 | Dry-run skips dirty check → inaccurate preview | MEDIUM | Fix |
| 892-M4 | #892 | `archive_worktree` doesn't clean registry | MEDIUM | Fix |

Not actioned: 878-M2 (silent fallback is acceptable), 878-M4 (no mismatch found).

## Plan — 3 Independent PRs

### PR 1: `fix/test-precheck-correctness`

**Scope:** `tests/unit/test_deterministic_prechecks.py` only

1. Fix `"PP1"` → `"P1"` typo on lines 561 and 580
2. Fix vacuously true assertion on line 564:
   - Current: `"plan_a.md" in files or len(pp1) >= 0` (always True)
   - Fixed: `"plan_a.md" in files` (straight membership check) or
     `len(p1_findings) > 0` + `"plan_a.md" in files`
3. Verify test now actually exercises the P1 check by running it
4. Evaluate M1/M2 (removed tests): add back meaningful assertions for
   `changed_files` scope restriction if coverage gap is real

**Validation:** `uv run python -m pytest tests/unit/test_deterministic_prechecks.py -v`

### PR 2: `fix/worktree-safety`

**Scope:** `src/bid_euchre/ops/worktrees.py` + `tests/unit/test_ops_worktrees.py`

1. **Quarantine untracked files (892-M2):** After `git diff HEAD`, also run
   `git ls-files --others --exclude-standard` and append an "untracked files"
   section to the saved diff. Update docstring.
2. **Registry cleanup after archive (892-M4):** In `archive_worktree()`,
   after successful `git worktree remove`, find and delete the matching
   registry JSON file from `worktree_registry/`.
3. **Dry-run dirty accuracy (892-M3):** Change `prune_worktrees()` to always
   pass `check_dirty=True`. In dry-run mode, still report dirty status but
   prefix action with "Would". This makes dry-run predictions accurate.
4. Add/update tests for all three changes.

**Validation:** `uv run python -m pytest tests/unit/test_ops_worktrees.py -v`

### PR 3: `fix/ops-events-reliability`

**Scope:** `src/bid_euchre/ops/events.py`, `src/bid_euchre/ops/status.py`,
`src/bid_euchre/ops/worktrees.py` (v1 map only), `.claude/hooks/post-task-event.sh`,
tests

1. **Concurrent write safety (878-H2):** Add `fcntl.flock(f, LOCK_EX)` around
   the write in `append_event()`. Release on context exit.
2. **Drain atomicity docs (878-H1):** Add docstring note to `drain_events()`
   explaining the duplicate-on-crash window and why it's acceptable (archive
   is idempotent, events are advisory).
3. **Remove dead code (878-M3):** Remove `count_events()` and `drain_events()`.
   They have no callers. If needed later, they can be re-added from git history.
   Actually — `drain_events` is documented API. Keep it, just add the atomicity
   note. Remove only `count_events()` which is truly redundant (can be done
   via `len(read_events(...))`).
4. **v1 role map fallback (878-M5):** Change both `lane_id_map.get(role, role)`
   calls to `lane_id_map.get(role, "unknown")` in `worktrees.py:171` and
   `status.py:104`.
5. **Shell quoting (892-M1):** In `post-task-event.sh`, switch from string
   interpolation to passing args via environment variables or use proper quoting.

**Validation:** `uv run python -m pytest tests/unit/test_ops_events.py tests/unit/test_ops_worktrees.py tests/unit/test_ops_status.py -v`

## Parallelism

All 3 PRs are independent (different file scopes):
- PR 1 touches only test files
- PR 2 touches worktrees.py + its tests
- PR 3 touches events.py, status.py, v1 map in worktrees.py, shell script + tests

PR 2 and PR 3 both touch `worktrees.py` but at different locations (PR 2:
quarantine/archive/prune functions; PR 3: v1 role map in `list_worktrees_registry`).
No conflict expected.

**Execution:** Implement all 3 in parallel using separate worktrees.

## Outcome

All 3 PRs shipped in parallel via isolated worktree agents:

| PR | Title | Status | CI |
|----|-------|--------|-----|
| #901 | fix: correct PP1 typo and vacuously true assertion in precheck tests | ✅ MERGED | All pass |
| #902 | fix: event write locking, v1 role map fallback, shell quoting, dead code removal | OPEN | tests pass, review pending |
| #905 | fix: quarantine untracked files, clean registry on archive, accurate dry-run | OPEN | CI running |

**Deviations from plan:**
- PR 2 (fix/worktree-safety): Fix 3 (892-M3, dry-run dirty accuracy) was already fixed in PR #896.
  Agent correctly identified this and skipped it. Only Fixes 1 and 2 were implemented.
- PR 3 (fix/ops-events-reliability): Agent also fixed `lane_class_map.get(role, role)` → `"unknown"`
  at `worktrees.py:173`, which the plan missed but the plan reviewer (R4) flagged.

**Plan review findings (post-hoc):**
- P15 WARNING: shared worktrees.py edit — managed via merge ordering (no actual conflict)
- R4 WARNING: lane_class_map fallback — addressed by PR #902 agent proactively
- R2 INFO: fcntl.flock portability — acceptable (macOS + Linux both support flock)
