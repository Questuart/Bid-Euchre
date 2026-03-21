# Review Quality Instrumentation

**Date:** 2026-03-20
**Status:** proposed
**Goal:** Add a bounded audit/instrumentation lane that measures where the
current local review loop misses issues or produces noisy findings, without
changing the merge gate or review-coordinator architecture.

## Relation to Active Bridge Work

This is a supporting lane that may run in parallel with the post-PR-5 bridge,
especially the local review-architecture reset.

It exists to answer a concrete question before `Platform-1`:

- what kinds of issues are still being missed pre-merge?
- which findings are high-noise and should not block?
- which repeated misses are strong candidates for deterministic checks?

This lane should inform later review-loop tightening, but it should not itself
become a review-architecture rewrite.

## Entry Conditions

- PR-5 closeout baseline cleanup is merged
- the review loop remains operational on `origin/main`
- the local review-architecture reset may be running in parallel

## Why This Exists

The repo has already accumulated evidence that:

1. hosted review surfaces are brittle
2. current local Codex CLI review is not catching enough important issues
3. some review-loop findings are noisy enough to waste cycles

Before broadening platform/autonomy scope, the repo should have a lightweight,
durable way to measure review effectiveness and identify the highest-signal next
improvements.

## Decisions Locked By This Plan

1. This lane is **measurement-first**, not architecture-first.
   - do not redesign the review loop here
   - do not change merge-gate ownership

2. This lane is **repo-local and bounded**.
   - prefer using existing local artifacts, PR metadata, committed reports, and
     review-loop outputs
   - avoid dependence on hosted review services

3. Output should be **operator-usable**.
   - findings should roll up into a short audit summary
   - the result should clearly separate:
     - missed blockers
     - noisy findings / false positives
     - candidate deterministic checks

4. This lane should not widen into broad data science/reporting infrastructure.

## Ownership / Non-Overlap Rules

This lane should avoid overlapping the active review reset lane unless a small,
explicitly coordinated hook is needed.

Preferred ownership:

- `scripts/internal/confidence_scorer.py`
- new audit/report helper(s) under `scripts/internal/`
- review-quality tests
- review-loop docs only where the instrumentation/report output is described

Avoid unless coordination is required:

- `scripts/internal/review_driver.py`
- canonical PR comment publication logic
- `reviewing-changes` status publication behavior
- broad state-machine changes

## Concrete Questions to Answer

The implementation should make it easy to answer:

1. Which post-merge follow-up fixes correspond to issues the review loop should
   have caught?
2. Which check IDs or finding classes are producing low-value noise?
3. Which file categories or PR shapes are most associated with misses?
4. Which misses are deterministic enough to promote into prechecks?

## Required Deliverables

### 1. Durable audit input shape

Add or document a stable way to collect review-quality inputs from repo-local
artifacts such as:

- review-loop round artifacts
- committed follow-up session plans / fix PRs
- PR metadata already available to repo tooling
- deterministic precheck outputs
- confidence scoring outputs

This does not need to be a large new schema. A small JSON summary or Markdown
report is enough if it is stable and testable.

### 2. Review-quality audit command or helper

Provide one repo-local way to generate a bounded audit/report from recent data.

Expected characteristics:

- works without hosted-review dependencies
- focuses on recent PRs or a bounded sample
- highlights:
  - missed pre-merge issues
  - noisy findings
  - deterministic-check candidates

### 3. Short operator-facing summary

The lane should produce a compact summary format that can support:

- handoffs
- plan amendments
- future deterministic-check prioritization

### 4. Tests

Add tests for:

- classification/rollup of review outcomes
- audit summary generation on synthetic sample inputs
- regression coverage for the chosen data model

## Likely Files

| File | Expected role |
|------|---------------|
| `scripts/internal/confidence_scorer.py` | reuse or extend scoring/audit helpers if appropriate |
| `scripts/internal/review_driver.py` | only if a small hook is truly needed |
| `scripts/internal/` | likely new audit/report helper |
| `tests/unit/test_confidence_scorer.py` | scoring/report tests if touched |
| `tests/unit/test_review_driver.py` | only if a small hook is added |
| `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` | describe the audit/instrumentation output if shipped |
| `plans/sessions/2026-03-20_review-quality-instrumentation.md` | fill outcome section after implementation |

## Suggested Implementation Shape

1. Validate what local artifacts already exist and are reliable enough to mine.
2. Add the smallest useful audit/report helper.
3. Generate bounded rollups by finding class / source / outcome.
4. Ensure the output explicitly distinguishes:
   - misses that should have blocked
   - warnings/noise that should be downgraded or filtered
   - candidates for deterministic prechecks
5. Update docs only enough to explain how to run and interpret the audit.

## Out of Scope

- replacing the review loop
- changing the `reviewing-changes` contract
- broad prompt redesign
- hosted review experimentation
- automatic public PR replies
- platform/orchestrator/dashboard work

## Done When

- [ ] there is one repo-local way to generate a bounded review-quality audit
- [ ] the output distinguishes misses, noise, and deterministic-check
      candidates
- [ ] tests cover the chosen summary/report behavior
- [ ] docs are updated if operator-facing usage changed
- [ ] the implementation stays out of merge-gate / coordinator redesign
- [ ] `make check-quiet` passes

## Suggested Validation

- `uv run pytest -q tests/unit/test_confidence_scorer.py tests/unit/test_review_driver.py`
- targeted tests for any new audit helper
- `make check-quiet`

## Outcome

**PR:** (pending — opened after `make check-quiet` passes)
**Branch:** `codex/steward-author-c`

### Delivered

1. **`scripts/internal/review_quality_audit.py`** — bounded audit helper
   - Scans `.claude/runtime/review_loops/pr_*/` state files and round artifacts
   - Aggregates findings by `(check_id, source)` across all rounds
   - Identifies noisy check_ids (high confidence-filter rate)
   - Identifies deterministic-check candidates (recurring Codex findings not yet in prechecks)
   - Correlates post-merge fix PRs as missed-blocker signals
   - Produces Markdown or JSON summary output
   - CLI: `python scripts/internal/review_quality_audit.py [--json] [--base PATH]`

2. **`tests/unit/test_review_quality_audit.py`** — 49 tests covering:
   - Loop outcome scanning (state file parsing, enrichment from rounds)
   - Finding aggregation (precheck + codex + scoring + fix counts)
   - Noise detection (filter-rate thresholds)
   - Missed-blocker extraction (fix PR title classification)
   - Deterministic-candidate identification (codex-only, excludes existing prechecks)
   - Summary generation and Markdown formatting
   - Full pipeline integration (scan → aggregate → summary → format)
   - Edge cases (empty data, malformed JSON, non-PR directories)

3. **`docs/01_core/ARCHITECTURE.md`** — registered new script in the internal tooling table

### Validated Data Sources

| Source | Location | Shape |
|--------|----------|-------|
| Loop state files | `.claude/runtime/review_loops/pr_<N>/state.json` | `ReviewLoopState` JSON |
| Precheck findings | `round_<N>/prechecks.json` | list of Finding dicts |
| Codex review | `round_<N>/codex_review.json` | `{success, findings, raw_output}` |
| Confidence scoring | `round_<N>/confidence_scoring.json` | `{total_findings, passed, filtered, findings}` |
| Fix summary | `round_<N>/fix_summary.json` | `{fixes_applied, fixes_skipped, actions}` |

### Key Findings from Local Data (77 loops)

- **Completion rate:** 26% (20/77 merged)
- **Top failure mode:** `stopped_ci_failure` (32/77 = 42%)
- **Review availability:** `stopped_review_failure` (8/77) + `waiting_for_codex` (12/77) = 26% stuck on Codex
- **Codex findings often lack `check_id`** — marked `unstructured`, not promotable to deterministic checks
- **Confidence scorer filters mostly work** — noisy P2 findings on unmodified lines correctly filtered

### Residual Gaps

- No automated GitHub API integration for fix-PR correlation — requires `--fix-prs-json` input file
- Cannot distinguish "CI failure on PR code" from "CI failure on infra" without parsing CI logs
- `waiting_for_codex` loops may be live or dead — no timeout detection in the audit
