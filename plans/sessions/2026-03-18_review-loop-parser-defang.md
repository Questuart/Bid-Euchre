# Defang Review Loop Parser Failures

**Date:** 2026-03-18
**Goal:** Stop infrastructure/parser failures from producing false blocking verdicts in both plan and PR review loops.

## Problem Statement

The review loops (plan + PR) convert parser/backend failures into synthetic CRITICAL findings with `NOT_READY` verdicts. This causes two distinct failure modes:

1. **Backend unavailability → synthetic CRITICAL:** When both Codex CLI and Claude fallback fail (timeout, crash, unavailability), `plan_review_driver.py:382-400` injects a synthetic CRITICAL finding. All 9/11 plan reviews failed this way.

2. **Parser brittleness → false rejection:** When Codex returns valid output (clean verdict or real findings) in prose that doesn't match the structured parser OR the 34-pattern clean-review regex, both adapters treat this as a hard failure (`success=False`). 6/8 PR review failures were this mode. Examples:
   - PR #793: Codex said "this change does not introduce a correctness issue" → rejected (phrasing not in clean list)
   - PR #757: Codex said "git diff is empty, no tracked changes to review" → rejected
   - PR #747: Codex output `[P1]` findings with absolute paths and multi-paragraph format → parser expected single-line format with `src/` relative paths

3. **Doc drift:** Three docs reference `make check` as a loop step, but the code removed it months ago.

## Data (from runtime artifacts)

| Category | PR Reviews (61 total) | Plan Reviews (11 total) |
|----------|----------------------|------------------------|
| Succeeded (merged/clean) | 9 (14.8%) | 0 (0%) |
| CI failure (not parser) | 30 (49.2%) | — |
| Parser/backend failure | 8 (13.1%) | 11 (100%) |
| In-progress/waiting | 14 (23.0%) | — |

Of the 8 PR parser failures: 6 were "clean prose rejected", 2 were Codex CLI interrupted.

## Plan

### PR 1: Defang parser failures (code changes)

**Scope:** Stop treating parser/backend failures as blocking findings. Three changes:

#### Step 1: Add REVIEW_UNAVAILABLE verdict to plan review driver

**File:** `scripts/internal/plan_review_driver.py`
- In `_compute_verdict()` (lines 77-93): Add `REVIEW_UNAVAILABLE` as a distinct return value. Distinguish from INFO/WARNING: check for findings with `source="infrastructure"` specifically, not just severity.
- At lines 382-400: Replace synthetic CRITICAL injection with an INFO-severity finding from source `"infrastructure"`, and set verdict to `REVIEW_UNAVAILABLE` instead of `NOT_READY`
- Update `_write_sidecar()` (line ~178) to render REVIEW_UNAVAILABLE as "Review system unavailable — plan not reviewed" rather than "NOT_READY — CRITICAL findings"
- Update `PlanReviewLoopResult.verdict` (set at line ~466 in `run_plan_review_loop()`) to propagate `REVIEW_UNAVAILABLE` consistently — both the sidecar text and the returned result must agree

#### Step 2: Flip the parser default — unparseable output is advisory, not blocking

**File:** `scripts/internal/codex_plan_review_adapter.py` (lines 479-495)
**File:** `scripts/internal/codex_review_adapter.py` (lines 548-567)

Current behavior: `if not findings and output.strip() and not _CLEAN_REVIEW_PATTERNS.search(output)` → `success=False`

New behavior: Return `success=True` with `findings=[]` and a logged warning. The raw output is already persisted to `codex_output_raw.txt` for human inspection. Rationale: if the parser can't understand the output, the correct response is "I don't know" (advisory), not "this is blocked" (CRITICAL).

Add a new field `parse_confidence: str` to both result dataclasses (`"structured"`, `"clean_signal"`, `"unparseable"`) so callers can distinguish how the result was determined.

**Also handle non-zero exit / "interrupted" failures:** In `codex_review_adapter.py` around line 527, the non-zero exit path (which catches "Review was interrupted. Please re-run /review") currently returns `success=False`. Add detection for known retryable backend messages (regex: `r"interrupted|re-run|try again"`) and return `success=True, findings=[], parse_confidence="backend_error"` for those. True invocation errors (missing binary, permission denied) remain `success=False`.

#### Step 2a: PR review driver must branch on parse_confidence

**File:** `scripts/internal/review_driver.py`

The adapters now return `success=True` for unparseable/backend_error cases, but the PR review driver (around lines 986-1001 in `_step_scoring_findings()`) treats `success=True, findings=[]` as "Review passed — clean" and transitions to `ready_to_merge`. That would silently promote "I don't know" to "clean pass."

Fix: After receiving the `CodexReviewResult`, check `result.parse_confidence`:
- `"structured"` or `"clean_signal"` → proceed normally (real clean pass)
- `"unparseable"` or `"backend_error"` → publish advisory status `"success"` with description `"Review degraded — Codex output unparseable (advisory)"`, log a warning, and transition to `ready_to_merge` **only if** GitHub CI has passed (the CI gate remains authoritative). The GitHub status description distinguishes this from a true clean review.

Add `REVIEW_DEGRADED` to `REVIEW_STATUS_MAP` in `review_state.py` (maps to GitHub `"success"` state but with distinct description text) so status consumers can distinguish clean from degraded.

**Test:** `test_unparseable_codex_output_publishes_degraded_status` in `tests/unit/test_review_driver.py` — assert status description contains "degraded", not "clean".

#### Step 3: Expand clean-review patterns for known missed phrasings

**File:** `scripts/internal/codex_review_adapter.py` (lines 152-184)

Add patterns observed in failed reviews:
- `r"no\s+tracked\s+changes"` (pr_757)
- `r"does\s+not\s+introduce\s+(?:a\s+)?(?:correctness\s+)?issue"` (pr_793)
- `r"no\s+patch\s+to\s+flag"` (common Codex phrasing)
- `r"did\s+not\s+find\s+any\s+(?:discrete|actionable).*bugs?"` (pr_782)
- `r"no\s+(?:code|functional)\s+changes?"` (empty-diff variant)

This is a belt-and-suspenders complement to Step 2 — even with the default flipped, explicit clean detection improves logging clarity.

#### Step 4: Add/update tests

**File:** `tests/unit/test_plan_review_driver.py` (new or existing)
**File:** `tests/unit/test_codex_review_adapter.py` (existing)
**File:** `tests/unit/test_codex_plan_review_adapter.py` (existing)

Tests to add:
- `test_both_reviewers_fail_produces_review_unavailable` — verify verdict is REVIEW_UNAVAILABLE, not NOT_READY; assert both `result.verdict` and sidecar text agree
- `test_unparseable_output_returns_success_true` — verify parser default flip for both adapters
- `test_clean_patterns_match_known_codex_phrasings` — parametrized test with the 5 new patterns plus the pr_782/pr_793 actual output strings
- `test_parse_confidence_field_set_correctly` — verify structured/clean_signal/unparseable/backend_error is set
- `test_interrupted_codex_returns_backend_error` — verify "Review was interrupted" exit-1 returns `success=True, parse_confidence="backend_error"` (in `test_codex_review_adapter.py`)
- `test_unparseable_codex_output_publishes_degraded_status` — verify PR loop publishes "degraded" status description, not "clean" (in `test_review_driver.py`)
- `test_unparseable_does_not_block_ci_gated_merge` — verify PR loop still transitions to `ready_to_merge` when CI passes but status text distinguishes from clean (in `test_review_driver.py`)

### PR 2: Fix doc drift (docs-only)

**Scope:** Align three docs with actual code behavior (no `make check` in loop).

#### Step 1: Fix CODEX_GITHUB_REVIEW.md

**File:** `docs/02_agent/CODEX_GITHUB_REVIEW.md`
- Line 14: Remove "2. Runs `make check-quiet`" from the loop description
- Line 63: Change "prechecks → make check → Codex CLI" to "prechecks → waits for CI → Codex CLI"

#### Step 2: Fix 60_review_gate.md Operating Model

**File:** `.claude/rules/deferred/60_review_gate.md`
- Line 13: Remove `, make check` from the Operating Model summary

#### Step 3: Verify AUTONOMOUS_REVIEW_LOOP.md is correct (read-only)

**File:** `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md`
- Lines 49-53 already correctly document the removal. No changes needed.

## Files

### PR 1 (code)
- `scripts/internal/plan_review_driver.py` — REVIEW_UNAVAILABLE verdict, remove synthetic CRITICAL, update `_write_sidecar()` and `PlanReviewLoopResult`
- `scripts/internal/codex_plan_review_adapter.py` — flip parser default to advisory, add `parse_confidence` field
- `scripts/internal/codex_review_adapter.py` — flip parser default to advisory, add clean patterns, add `parse_confidence` field, handle "interrupted" exit-1
- `scripts/internal/review_driver.py` — branch on `parse_confidence` in `_step_scoring_findings()`, publish degraded status
- `scripts/internal/review_state.py` — add REVIEW_UNAVAILABLE and REVIEW_DEGRADED to state/verdict enums
- `tests/unit/test_plan_review_driver.py` — REVIEW_UNAVAILABLE verdict + sidecar consistency tests
- `tests/unit/test_codex_review_adapter.py` — parser default + clean pattern + interrupted + parse_confidence tests
- `tests/unit/test_codex_plan_review_adapter.py` — parser default + parse_confidence tests
- `tests/unit/test_review_driver.py` — degraded status + unparseable merge path tests

### PR 2 (docs)
- `docs/02_agent/CODEX_GITHUB_REVIEW.md` — remove stale `make check` references
- `.claude/rules/deferred/60_review_gate.md` — remove stale `make check` reference

## What this does NOT do

- **Does not add structured output contract (JSON schema for Codex responses).** That's a larger change that requires modifying the Codex CLI invocation prompt, which is in an external skill file (`~/.codex/skills/`). Worth doing eventually but out of scope.
- **Does not fix the prose finding parser** (absolute paths, multi-line findings). The parser is best-effort; flipping the default to advisory makes this non-urgent.
- **Does not change the CI gate.** GitHub CI remains the authoritative merge gate. The PR review loop continues to require CI passage before `ready_to_merge`. What changes: Codex parser/backend failure no longer prevents reaching `ready_to_merge`.
- **Does not remove the Claude fallback.** It stays as-is. If it works, great; if not, the failure is now advisory rather than blocking.
- **Does not handle true invocation errors as advisory.** Missing binary, permission denied, and other non-retryable errors remain `success=False` → `STOPPED_REVIEW_FAILURE`. Only parser brittleness and known backend interruptions are defanged.

## Merge order

PR 2 (docs) has no dependency on PR 1 — can merge in either order or in parallel.

## Validation

- `make check` passes
- Targeted: `uv run python -m pytest tests/unit/test_codex_review_adapter.py tests/unit/test_codex_plan_review_adapter.py tests/unit/test_plan_review_driver.py tests/unit/test_review_driver.py -v`
- Key test commands from review findings:
  - `uv run python -m pytest tests/unit/test_review_driver.py -k "unparseable or ready_to_merge or degraded" -v`
  - `uv run python -m pytest tests/unit/test_codex_review_adapter.py -k "parse_confidence or interrupted" -v`
  - `uv run python -m pytest tests/unit/test_plan_review_driver.py -k "review_unavailable or sidecar" -v`
- Manual: Run `/review-plan` on a session plan and verify verdict is REVIEW_UNAVAILABLE (not NOT_READY) when Codex is unavailable

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
