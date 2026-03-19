# Session Plan: Post-Merge Review Fixes

**Date:** 2026-03-19
**Status:** IN PROGRESS
**Branch:** `fix/post-merge-review-batch`

## Context

Post-merge review of last 10 PRs produced 23 findings. After code verification,
**6 findings are phantom** (reference functions/code that doesn't exist) and
**5 are real code issues**. Additionally, 3 session plans have unfilled Outcome sections.

## Phantom Findings (Dismissed)

| # | Claimed Finding | Why Phantom |
|---|----------------|-------------|
| 1 | `task_id` path traversal in status.py | `task_id` is never used in path construction — filenames come from `glob("*.json")` |
| 2 | `update_task_scope()` TOCTOU race | Function does not exist anywhere in codebase |
| 3 | `_emit_retry_event` typed as `object` | Function does not exist anywhere in codebase |
| 4 | §16.2 claims outcome_summary "fully resolved" | §16.2 is about exploratory registry, not outcome_summary |
| 10 | `ci_poller.sh` lane_id inference incomplete | ci_poller.sh has no lane_id logic whatsoever |
| 8 | FTS5 schema mismatch with session plan | FTS5 schema matches: `content` column in `entries_fts`, backed by `entries` table |

## Verified Fixes

### Fix 1: `_generate_id()` collision window (memory.py:112-122)

**Problem:** Hash is `sha256(f"{category}:{key}:{now}")` where `now` is
`datetime.now(utc).isoformat()`. Two calls in the same microsecond with
identical key+category produce the same ID.

**Fix:** Add a random nonce: `os.urandom(8).hex()` appended to the hash input.

**File:** `src/bid_euchre/ops/memory.py` (lines 112-122)

### Fix 2: `_find_repo_root()` 4× duplication in scripts/internal/

**Problem:** Four identical copies of the same function:
- `scripts/internal/build_audit_index.py:15-22`
- `scripts/internal/compact_session_context.py:20-27`
- `scripts/internal/build_curated_memory.py:19-26`
- `scripts/internal/ops.py:30-37`

(Note: `src/bid_euchre/arc_d_v2/tables.py:738-748` is intentionally different —
`__file__`-based with `@lru_cache`, returns `Path | None`. Leave it alone.)

**Fix:** Create `scripts/internal/_repo_utils.py` with a shared `find_repo_root()`,
import from all 4 scripts.

**Files:**
- NEW: `scripts/internal/_repo_utils.py`
- EDIT: `scripts/internal/build_audit_index.py` — remove, import
- EDIT: `scripts/internal/compact_session_context.py` — remove, import
- EDIT: `scripts/internal/build_curated_memory.py` — remove, import
- EDIT: `scripts/internal/ops.py` — remove, import

### Fix 3: `except Exception` in `_ingest_report_metadata()` (index.py:591)

**Problem:** `except Exception as e:` catches all exceptions including
`TypeError`, `AttributeError`, etc. that indicate programming errors.

**Fix:** Narrow to `(json.JSONDecodeError, OSError, KeyError, ValueError)` —
the expected failure modes for JSON parsing and file I/O.

**File:** `src/bid_euchre/ops/index.py` (line 591)

### Fix 4: `build_index()` relative default paths (index.py:634-637)

**Problem:** Default paths `Path(".claude/runtime")` and `Path("plans/")` are
relative, meaning they break if cwd ≠ repo root.

**Fix:** Resolve relative defaults against the repo root using the new
`find_repo_root()` utility, falling back to cwd (existing behavior) if
outside a git repo.

**File:** `src/bid_euchre/ops/index.py` (lines 634-637)

### Fix 5: `save_memory()` no file locking (memory.py:150-155)

**Problem:** `memory_path.write_text(...)` has no atomicity guarantee. Concurrent
agent writes could corrupt the JSON file.

**Fix:** Use `fcntl.flock(LOCK_EX)` pattern from `events.py:102-108` —
open file, acquire exclusive lock, write, release.

**File:** `src/bid_euchre/ops/memory.py` (lines 150-155)

### Fix 6: Session plan Outcome sections (3 files)

**Problem:** Three session plans have `_To be filled after implementation._`

**Fix:** Fill each Outcome with PR number and one-line summary from MEMORY.md.

**Files:**
- `plans/sessions/2026-03-19_deferred-review-findings.md`
- `plans/sessions/2026-03-19_convention-followup-batch-2.md`
- `plans/sessions/2026-03-19_r3-full-closeout.md`

## Out of Scope

- **Finding #9 (R0 pooled metrics changed):** Lineage is frozen/COMPLETE. Not actionable.
- **Finding #4 (outcome_summary.csv in manifests):** 4 canonical manifests reference
  `outcome_summary.csv` files that were removed from generation. These are frozen
  lineage artifacts — modifying them would be more disruptive than leaving them.
- **Finding #16 (broken dashboard.yml):** Existing known issue, separate concern.
- **Finding #22 (weakened test assertion):** Test correctly checks invariant
  (no absolute paths, correct suffix) — not "weakened", just more portable.

## Validation

- Tier 1: `uv run python -m pytest tests/unit/test_memory.py tests/unit/test_audit_index.py -v`
- Tier 2: `make check-quiet` before PR

## Parallelism Assessment

Fixes 1, 3, 5 touch different files but are small enough to do sequentially.
Fix 2 and 4 both touch `scripts/internal/` and `index.py` (Fix 4 imports
the new utility from Fix 2). **Execute in order: Fix 2 → Fix 4 → Fix 1 → Fix 5 → Fix 3 → Fix 6.**

## Outcome

_To be filled after implementation._
