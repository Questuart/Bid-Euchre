<!-- review-tier: medium -->
# Session Plan: Ops Index Hardening (#952, #953, #957)
**Date:** 2026-03-19
**Goal:** Ship one cohesive Author-A PR that fixes the `ops/index.py` correctness and testability bugs without overlapping Author-Scratch's active memory/compaction work.
**Closes:** #952, #953, #957

## Executive State

- Author-Scratch currently owns the ops persistence reliability slice in `memory.py` and `compaction.py` under `plans/sessions/2026-03-19_ops-persistence-hardening.md`.
- This execution slice owns only the `ops/index.py` bug cluster.
- The planned PR should stay focused on correctness and testability. The staleness-scan performance issue `#956` is a follow-up unless the executing agent can prove a fix stays local and test-backed without widening the query/read-path contract.

## Primary Sources Of Truth

- `plans/sessions/2026-03-19_ops-persistence-hardening.md`
- `src/bid_euchre/ops/index.py`
- `tests/unit/test_ops_index.py`
- `tests/unit/test_ops_cli.py`
- `scripts/internal/build_audit_index.py`
- `scripts/internal/ops.py`
- `.claude/CLAUDE.md`
- `docs/02_agent/AGENTS.md`
- `docs/02_agent/PLAN_REVIEW_TIERS.md`

## Coordination And Write Ownership

### Owned by this plan

- `src/bid_euchre/ops/index.py`
- `tests/unit/test_ops_index.py`
- `tests/unit/test_ops_cli.py` only if CLI-facing behavior or output changes
- `scripts/internal/build_audit_index.py` or `scripts/internal/ops.py` only if explicit `repo_root` plumbing becomes necessary

### Explicitly not owned by this plan

- `src/bid_euchre/ops/memory.py`
- `src/bid_euchre/ops/compaction.py`
- their corresponding test files

No code-edit overlap with Scratch is expected if this boundary is respected.

## Scope

### In scope

1. Fix `#952` by removing hardcoded CWD-relative auxiliary paths from `build_index()`.
2. Fix `#953` by completing the FTS5 external-content trigger set with an `AFTER UPDATE` trigger.
3. Fix `#957` by making `sources_indexed` accurate for compound ingestors.
4. Add regression tests for all in-scope issues.
5. Preserve backward compatibility for existing callers unless a minimal caller update is required.

### Out of scope

- `#950`, `#951`, `#954` in memory/compaction
- `#956` staleness-check performance and query/read-path semantics
- `#959` compaction symlink containment
- `#928`, `#929`, `#930` watchdog wiring
- `#829`, `#830`
- Manual GitHub issue housekeeping

## Autonomous Execution Requirements

Before writing code, the executing agent must:

1. Refresh context by reading the primary sources above and this plan.
2. Draft or refine the execution plan if source-level discovery changes the approach.
3. Spawn at least one reviewer agent to review that plan before major edits.
4. Create and maintain a bounded task list covering implementation, validation, and PR shipment.
5. Assess safe parallelism before delegating and only delegate disjoint write scopes.
6. Execute the work end to end autonomously:
   - implement
   - test
   - run focused failure-injection or direct-schema validation where relevant
   - commit
   - open or update the PR
   - include `Validation Performed` evidence in the PR body

Do not start implementation until the plan-review step and task-list setup are complete.

## Workstreams

### Workstream A — Repo-Root-Aware Path Resolution (`#952`)

**Objective:** Make `build_index()` derive all auxiliary scan paths from explicit inputs rather than the process CWD.

**Required changes**

- Eliminate direct `Path("data/runs")` and `Path("docs/04_reports")` usage inside `build_index()`.
- Introduce a repo-root-aware derivation strategy that preserves current behavior for existing callers.
- Keep test ergonomics simple: `tmp_path` fixtures should be able to provide all scanned paths without `chdir()`.

**Recommended approach**

- Add an optional `repo_root: Path | None = None` parameter to `build_index()`.
- Derive default `runtime_dir`, `plans_dir`, `data_runs_dir`, and `reports_dir` from `repo_root` when not explicitly passed.
- Prefer keeping call-site changes minimal. Only touch `scripts/internal/build_audit_index.py` or `scripts/internal/ops.py` if explicit `repo_root` passing is needed for clarity or correctness.

**Required tests**

- A `tmp_path`-backed repo-root fixture with:
  - a `data/runs/.../evidence_manifest*.json`
  - a `docs/04_reports/.../manifest*.json`
- Assert that `build_index()` ingests those sources without relying on `os.getcwd()`.

### Workstream B — FTS Schema Contract Completion (`#953`)

**Objective:** Complete the FTS5 external-content synchronization contract.

**Required changes**

- Add the missing `AFTER UPDATE` trigger to `init_schema()`.
- Keep insert/delete behavior unchanged.

**Required tests**

- Initialize a test database.
- Insert a source and entry.
- Directly `UPDATE entries SET content = ...`.
- Assert FTS-backed query results reflect the updated content rather than stale text.

### Workstream C — Accurate Source Accounting (`#957`)

**Objective:** Make `BuildResult.sources_indexed` reflect actual upserted sources for compound ingestors.

**Required changes**

- Fix the mismatch where `_ingest_review_loop`, `_ingest_plan_reviews`, and `_ingest_report_metadata` may upsert many sources but `build_index()` counts each call as one source.
- Keep `entries_indexed` behavior unchanged.
- Prefer a small internal API change over ad hoc counter patches.

**Recommended approach**

- Have compound ingestors return both `sources_count` and `entries_count`, or return a small internal result object with both fields.
- Update `build_index()` to aggregate exact counts from those ingestors.

**Required tests**

- Create review-loop sidecars with:
  - one `state.json`
  - two per-round artifacts
- Create one plan-review artifact.
- Create one report metadata manifest.
- Assert `sources_indexed` matches the true number of ingested sources, not the number of ingestor calls.

### Workstream D — Deferred Performance Follow-Up (`#956`)

**Objective:** Keep the first PR bounded.

`#956` is intentionally deferred unless the executing agent can prove that:

- the fix stays local to `src/bid_euchre/ops/index.py`
- the query/read-path contract remains clear
- targeted tests cover the changed behavior without broad CLI or API churn

If those conditions are not met, record `#956` as an explicit follow-up in the PR body and closeout note.

## Files

- `src/bid_euchre/ops/index.py` — main implementation
- `tests/unit/test_ops_index.py` — regression coverage for `#952`, `#953`, `#957`
- `tests/unit/test_ops_cli.py` — only if CLI-facing behavior changes
- `scripts/internal/build_audit_index.py` — only if explicit repo-root plumbing is needed
- `scripts/internal/ops.py` — only if explicit repo-root plumbing is needed

## Bounded Task List

1. Review current `index.py` implementation and test coverage gaps.
2. Run one plan-review sub-agent and incorporate material feedback.
3. Create the execution task list.
4. Implement `#952` path derivation fix.
5. Add `#952` regression tests.
6. Implement `#953` update trigger.
7. Add `#953` regression test.
8. Implement `#957` source-count fix.
9. Add `#957` exact-count regression test.
10. Reassess whether `#956` is still best deferred.
11. Run targeted tests.
12. Run `make check-quiet`.
13. Commit on a `codex/` branch.
14. Open or update the PR with `Validation Performed` evidence.

## Parallelism Guidance

No code-edit parallelism is recommended by default because the main write scope is one source file and one primary test file.

Safe parallelism, if the executing agent judges it worthwhile:

- Reviewer agent: plan review only
- Worker A: source-level implementation design notes for `index.py`
- Worker B: test-design proposal for `tests/unit/test_ops_index.py`

Keep actual file edits, integration, validation, and PR preparation in the main agent unless write scopes are truly disjoint.

## Risks And Rollback

### Risk 1 — Repo-root fix widens public API more than necessary

Mitigation:
- Keep `repo_root` optional.
- Preserve existing caller behavior by default.
- Touch call sites only if required.

### Risk 2 — Source-count fix becomes a broad internal refactor

Mitigation:
- Restrict the API change to the three compound ingestors.
- Do not refactor every simple ingestor unless required.

### Risk 3 — `#956` slips into the same PR and broadens scope

Mitigation:
- Treat `#956` as deferred by default.
- Include it only with explicit justification and dedicated tests.

### Rollback

- Revert the branch or commit if targeted regressions fail unexpectedly.
- If one issue proves larger than expected, split it out and keep the rest of the PR shippable.

## Validation Requirements

Minimum required commands:

```bash
uv run python -m pytest -q tests/unit/test_ops_index.py
```

```bash
make check-quiet
```

Run this if `tests/unit/test_ops_cli.py`, `scripts/internal/ops.py`, or `scripts/internal/build_audit_index.py` change:

```bash
uv run python -m pytest -q tests/unit/test_ops_cli.py -k "index or query"
```

Required behavioral checks:

- confirm `build_index()` can ingest `data/runs` and `docs/04_reports` sources from a `tmp_path`-backed repo root without relying on CWD
- confirm a direct SQL update to `entries.content` is reflected in FTS query results
- confirm `sources_indexed` reflects the true number of upserted sources for review loops, plan reviews, and report metadata

## Deliverables

1. Code and tests committed on a `codex/` branch.
2. PR opened or updated.
3. PR body includes:
   - summary of `#952`, `#953`, `#957`
   - exact validation commands run
   - whether `#956` was deferred or included
   - explicit non-overlap note with Scratch's memory/compaction work

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / deferred
- Notes: record any scope changes, caller updates, or `#956` deferral
