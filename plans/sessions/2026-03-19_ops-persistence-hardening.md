<!-- review-tier: medium -->
# Session Plan: Ops Persistence Hardening (#950, #951, #954)
**Date:** 2026-03-19
**Goal:** Ship one cohesive PR that removes the verified data-loss chain in curated memory and the retry-blocking partial-archive failure in session compaction, with regression coverage and autonomous PR shipment.
**Closes:** #950, #951, #954

## Summary

- Fix three follow-up bugs from PR #940 in the ops persistence layer.
- Keep index configurability, index performance, schema-completeness, and compaction symlink hardening out of scope for this PR.
- Require the executing agent to follow the repo implementation-handoff protocol before code changes begin.

## Primary Sources Of Truth

- `src/bid_euchre/ops/memory.py`
- `src/bid_euchre/ops/compaction.py`
- `tests/unit/test_ops_memory.py`
- `tests/unit/test_ops_compaction.py`
- `.claude/CLAUDE.md`
- `docs/02_agent/AGENTS.md`
- `docs/02_agent/PLAN_REVIEW_TIERS.md`

## Scope

### In scope

1. Fix `#950` in `load_memory()` so malformed entries are skipped individually and valid entries are preserved.
2. Fix `#951` in `save_memory()` so curated memory writes are atomic.
3. Fix `#954` in `compact_session()` so failed archive writes do not leave a blocking partial archive behind.
4. Add regression tests for each failure mode above.
5. Ship a single PR with validation evidence.

### Out of scope

- `#952` `#953` `#956` `#957` in `src/bid_euchre/ops/index.py`
- `#959` symlink-containment hardening in `delete_archive()`
- `#928` `#929` `#930` watchdog/event wiring
- `#829` review-driver architecture work
- `#830` unless the executing agent reproduces a real parser failure on current `main`
- Manual GitHub housekeeping for stale-open issues from PR #949

## Autonomous Execution Requirements

Before writing code, the executing agent must:

1. Refresh context by reading the primary sources above and this plan.
2. Draft or refine a concrete execution plan if new source-level discoveries require adjustment.
3. Spawn at least one reviewer agent to review that plan before major edits.
4. Create and maintain a bounded task list covering implementation, validation, and PR shipment.
5. Assess safe parallelism before delegating and only delegate disjoint write scopes.
6. Execute the work end to end autonomously:
   - implement
   - test
   - run failure-injection or interrupted-write validation
   - commit
   - open or update the PR
   - include `Validation Performed` evidence in the PR body

Do not start implementation until the plan-review step and task-list setup are complete.

## Implementation Plan

### Workstream A — Curated Memory Resilience

**Objective:** Remove the current data-loss chain in `ops/memory.py`.

**Required changes**

- `load_memory()` must preserve valid entries even when one entry is malformed.
- `save_memory()` must stop writing directly to the canonical JSON path.
- Warning logs should identify malformed entries or failed load/save paths clearly enough for diagnosis.

**Implementation notes**

- Parse the top-level JSON once, then validate or construct entries individually.
- Preserve `version` and `last_updated` from the file even when some entries are skipped.
- Use a same-directory temp file plus `os.replace()` or equivalent atomic rename.
- Ensure failed temp-file writes do not destroy the previous good store.

### Workstream B — Session Compaction Atomicity

**Objective:** Make archive creation atomic-or-absent from the caller perspective.

**Required changes**

- If `compact_session()` fails after creating the session directory, remove the partial archive before returning failure.
- Cleanup must be limited to the session directory created for the active `session_id`.
- Existing duplicate-archive behavior should remain unchanged for already-complete archives.

### Workstream C — Regression Coverage

**Objective:** Prove the failure modes are fixed and stay fixed.

**Required tests**

- Corrupt-entry load test:
  - one valid entry
  - one malformed entry
  - one additional valid entry
  - expected result: valid entries survive, malformed entry is skipped
- Interrupted-save or write-failure test:
  - simulate a write failure before final replace
  - expected result: prior on-disk file remains readable and unchanged
- Partial-archive failure test:
  - force a write failure after `session_dir.mkdir()`
  - expected result: `compact_session()` returns failure and the session directory does not remain on disk

## Files

- `src/bid_euchre/ops/memory.py` — per-entry load resilience and atomic save path
- `src/bid_euchre/ops/compaction.py` — cleanup on partial archive failure
- `tests/unit/test_ops_memory.py` — load/save regression tests
- `tests/unit/test_ops_compaction.py` — compaction failure-path regression test

## Bounded Task List

1. Review current implementation and tests.
2. Run one plan-review sub-agent and incorporate material feedback.
3. Create the execution task list.
4. Implement `ops/memory.py` fixes.
5. Add `test_ops_memory.py` regressions.
6. Implement `ops/compaction.py` cleanup fix.
7. Add `test_ops_compaction.py` failure-path regression.
8. Run targeted tests.
9. Run `make check-quiet`.
10. Commit on a `codex/` branch.
11. Open or update the PR with `Validation Performed` evidence.

## Parallelism Guidance

This slice is small enough that no code-edit parallelism is required by default.

Safe parallelism, if the executing agent judges it worthwhile:

- Reviewer agent: plan review only
- Worker A: `ops/memory.py` + `test_ops_memory.py`
- Worker B: `ops/compaction.py` + `test_ops_compaction.py`

Do not allow multiple agents to edit the same source file or the same test file.
Keep final integration, validation, and PR preparation in the main agent.

## Risks And Rollback

### Risk 1 — Atomic write implementation leaks temp files

Mitigation:
- Create temp files in the destination directory.
- Clean up orphaned temp files on failure when possible.

### Risk 2 — Cleanup path deletes more than intended

Mitigation:
- Only remove the specific `session_dir` for the active `session_id`.
- Preserve the current duplicate-archive early-return guard.

### Rollback

- Revert the branch or commit if targeted regressions fail unexpectedly.
- Do not broaden scope into index changes while debugging; record deferrals instead.

## Validation Requirements

Minimum required commands:

```bash
uv run python -m pytest -q tests/unit/test_ops_memory.py tests/unit/test_ops_compaction.py
```

```bash
make check-quiet
```

Required behavioral checks:

- confirm malformed memory entries no longer wipe valid entries
- confirm failed memory save attempts preserve the previous on-disk file
- confirm partial archive directories do not block re-archival after a forced failure

## Deliverables

1. Code and tests committed on a `codex/` branch.
2. PR opened or updated.
3. PR body includes:
   - brief summary of issues fixed
   - exact validation commands run
   - results of failure-injection checks
   - note of explicitly deferred follow-ups

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / deferred
- Notes: record any scope changes or deferred follow-ups
