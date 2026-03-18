<!-- review-tier: small -->
# Session Plan: Three Follow-Up Issue Fixes (#830, #833, #840)

**Date:** 2026-03-18
**Lane:** author-d
**Branch:** `codex/steward-author-d`
**Strategy:** Single PR with three focused commits (all are small follow-up fixes)

## Goal

Resolve three open follow-up issues filed by the autonomous review loop.
All are bounded, independent fixes touching different modules.

---

## Issue #830: Port reversed-format parser to plan review adapter

### Analysis

The plan review adapter (`scripts/internal/codex_plan_review_adapter.py`)
already delegates Codex output parsing to `parse_codex_output()` from
`codex_review_adapter.py` (line 471, 691). That function already includes
Pass 1.5 (reversed format), line-range handling, and expanded file extensions.

**No code port is needed.** The fix is to add tests confirming the delegation
path works for reversed-format input, then close the issue.

### Changes

| File | Change |
|------|--------|
| `tests/unit/test_codex_plan_review_adapter.py` | Add `TestParsePlanFindingsReversedFormat` class with 3-4 tests |

### Tests to Add

1. `test_parse_reversed_format_through_delegation` — reversed-format line
   (`- [P1] message — src/foo.py:42`) parsed via `parse_plan_findings()`
2. `test_parse_reversed_format_line_range` — line range (`src/foo.py:90-95`)
   extracts start line (90)
3. `test_parse_reversed_format_absolute_path` — absolute path is stripped to
   repo-relative
4. `test_parse_reversed_format_shell_extension` — `.sh` file extension is recognized

---

## Issue #833: Fix CSV artifact clobbering in tables.py

### Analysis

In `src/bid_euchre/arc_d_v2/tables.py`, the `generate_chart_data()` function:

- **Step 6** (line 1048-1056): Writes `feature_importances.csv` using
  `_extract_feature_importance()` → schema: `model, contract, rank, feature_name, importance`
- **Step 8** (line 1066-1072): Writes `feature_importances.csv` AGAIN using
  `_extract_feature_importances_flat()` → schema: `model, contract, feature_name, importance`

Step 8 unconditionally clobbers step 6's output. The flat schema lacks the `rank`
column, breaking the interpretability chart generator which expects
`_FEATURE_IMPORTANCE_COLS = {"model", "contract", "rank", "feature_name", "importance"}`.

### Fix

1. **tables.py:** Guard step 8 so it only writes `feature_importances.csv` when
   step 6 did NOT produce the file. This preserves the richer ranked schema when
   selection logs are available.
2. **generate_interpretability_charts.py:** Add a `_FLAT_IMPORTANCE_COLS` set
   (`model, contract, feature_name, importance`) as a fallback schema for the
   feature importance chart, so the chart works with either schema.

### Changes

| File | Change |
|------|--------|
| `src/bid_euchre/arc_d_v2/tables.py` | Guard step 8 with `if "feature_importances.csv" not in generated:` |
| `scripts/internal/generate_interpretability_charts.py` | Add flat schema fallback for feature importance chart |

### Validation

- `uv run python -m pytest tests/unit/test_tables.py -x -q` (if exists)
- `uv run python -m pytest tests/ -k "feature_importance" -x -q`

---

## Issue #840: Reconcile doc contradictions in operator workflow

### Analysis

PR #839 added the "Task Discipline and Lane Governance" section. Two
contradictions exist:

1. **Task-record requirement vs exemptions:** The new "One Task Per Lane"
   section implies all work needs a task record, but the existing "When to
   Create a Task Record" section exempts simple work (single-file edits,
   running commands). Fix: add a qualifier to "One Task Per Lane" clarifying
   it applies only when a task record is warranted per the creation criteria.

2. **Online-first claim without linked doc update:** The PR #839 declared
   review loops as "transitional" and migrating to "online-first", but
   `AUTONOMOUS_REVIEW_LOOP.md` doesn't mention this status. Fix: add a
   brief note to the review loop doc referencing the transitional status.

### Changes

| File | Change |
|------|--------|
| `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` | Qualify "One Task Per Lane" to reference the creation criteria |
| `docs/02_agent/AUTONOMOUS_REVIEW_LOOP.md` | Add "Transitional Status" note referencing the migration plan |

---

## Execution Plan

### Dependencies

All three issues are independent. They touch different modules and can be
implemented in any order. However, since they share a branch and PR, they
must be committed sequentially.

### Ordering

1. **#833** (code fix — most impactful, has testable behavior)
2. **#830** (test-only addition — fast, no production code changes)
3. **#840** (docs-only — no test risk)

### PR Strategy

Single PR titled: `fix: resolve 3 follow-up issues (#830, #833, #840)`

One commit per issue for clean git history.

### Validation

- Tier 1: targeted tests after each fix
- Tier 2: `make check-quiet` before PR

## Outcome

_To be filled after implementation._
