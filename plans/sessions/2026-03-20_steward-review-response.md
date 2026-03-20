# Steward Review Response — 2026-03-20

## Context

Consolidated steward review (2026-03-20 18:22–18:27 UTC) identified findings
across PRs #1027, #1025, #1022, and #1024. This plan addresses all actionable
findings that belong to the author-b lane.

## Triage Summary

### Already Addressed by PR #1030 (`fix/review-sweep-batch-6`)

PR #1030 is open and contains fixes for all CRITICAL and HIGH severity findings:

| Finding | Severity | Status | What PR #1030 Does |
|---------|----------|--------|--------------------|
| #1027 C1 | CRITICAL | ✅ Fixed | Restores `allowed_tools` allowlist to `claude.yml` |
| #1027 C2 | CRITICAL | ✅ Fixed | Restores `pull-requests: write` and `issues: write` in both workflows |
| #1027 C3 | CRITICAL | ✅ Fixed | Restores infra failure detection step in `claude-code-review.yml` |
| #1027 H1 | HIGH | ✅ Fixed | Restores path filter (`src/`, `scripts/`, `tests/`, `experiments/`, `notebooks/`) |
| #1027 H2 | HIGH | ✅ Fixed | Restores custom review prompt + `--max-turns 5` cost control |
| #1022 H1 | HIGH | ✅ Fixed | Adds dedup guard to `_evaluate_retries_for_findings()` in scheduler.py |

### Out of Scope

| Finding | Severity | Reason |
|---------|----------|--------|
| #1025 * | CLEAN | No fixes needed — review confirmed clean |
| #1024 * | ADVISORY | On author-c lane (PR #1024, branch `codex/steward-author-c`) — already has `5ebb519 fix: address review findings` |
| #1027 M1 | MEDIUM | Process issue (empty PR template) — not a code fix |
| #1027 M2 | MEDIUM | Process issue (22s auto-merge) — not a code fix |
| #1022 M1 | MEDIUM | `emit_scope_snapshot()` untracked files — explicitly out of scope per session plan (task-state wiring issue, tracked via #929) |

### Remaining Actionable Findings (This Plan)

| ID | Source | Severity | Finding | Fix |
|----|--------|----------|---------|-----|
| R1 | #1022 M2 | MEDIUM | `emit_scope_snapshot()` silently swallows git failures without logging | Add `logger.warning()` in the exception handler |
| R2 | #1022 L1 | LOW | `_EVENT_MAP` dict allocated inside `emit_retry_event()` function body on every call | Move to module-level constant |
| R3 | #1022 M3 | MEDIUM | Plan outcome section left empty | Fill in outcome in existing session plan |

## Implementation Plan

### Phase 1: Land PR #1030 (Priority: IMMEDIATE)

PR #1030 addresses all 3 CRITICAL + 2 HIGH findings. It needs:

1. **Rebase onto origin/main** — branch is based on `57a50d4`, main is at `d0a3521`
   (includes #1025 `fix: classify checks` and #1027 itself — the rebase will apply
   our workflow file restorations on top of the broken #1027 state)
2. **Run `make check-quiet`** — verify no regressions after rebase
3. **Force-push** — update PR #1030
4. **Merge** — once CI passes

### Phase 2: Address Remaining MEDIUM/LOW Findings

Apply R1-R2 as a new commit on the PR branch before merging. R3 is post-merge
(plan outcome fill-in).

#### R1: Add logging to `emit_scope_snapshot()` git failure handler

**File:** `src/bid_euchre/ops/status.py` (around line 966+)
**Change:** In the `except` block, add `logger.warning("git diff failed: %s", e)`
instead of silently passing.

#### R2: Hoist `_EVENT_MAP` to module level

**File:** `src/bid_euchre/ops/recovery.py` (line 519)
**Change:** Move `_EVENT_MAP: dict[str, str] = {...}` from inside `emit_retry_event()`
to module level (above the function). No functional change, avoids dict allocation
per call.

#### R3: Fill plan outcome

**File:** `plans/sessions/2026-03-20_review-sweep-fixes.md`
**Change:** Fill `## Outcome` with PR #1030 link and summary.

### Validation

- `uv run python -m pytest tests/unit/test_ops_status.py tests/unit/test_ops_recovery.py tests/unit/test_ops_scheduler.py`
- `make check-quiet` before final PR

## Execution Order

1. Rebase PR #1030 onto origin/main
2. Apply R1 (scope snapshot logging)
3. Apply R2 (hoist _EVENT_MAP)
4. Run targeted tests (Tier 1)
5. Run `make check-quiet` (Tier 2)
6. Commit, push, merge PR #1030
7. Fill plan outcomes (R3)

## Outcome

<!-- Filled after implementation -->
