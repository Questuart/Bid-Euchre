# Convention Batch 4 — Batch 5 from triage plan

## Context

7 issues assigned to Batch 5 (convention follow-ups). After investigation,
2 are already fixed and 1 should close as out-of-scope. Remaining 4 are
small fixes suitable for a single PR.

## Already Fixed — Close Immediately

### #958 — extract duplicated _find_repo_root()
Already extracted to `scripts/internal/_repo_utils.py`. All 4 scripts now
import `from _repo_utils import find_repo_root`. Close.

### #963 — outcome_distributions.status, 04_rung_decision.md, plan status
All three findings are stale:
- `outcome_distributions.status` — files already removed (confirmed: no matches in `docs/04_reports/`)
- `04_rung_decision.md` for R2/full — file no longer exists
- Plan status already marked resolved with "✅ Fully resolved" comments
Close as stale.

## Close as Out-of-Scope

### #936 — Inconsistent JSON schema between precheck and review loop
The issue itself notes: "Low — both systems work independently and the
inconsistency only matters if building cross-system aggregation." The two
systems (`deterministic_prechecks.py` Finding dataclass vs `review_driver.py`
Codex finding dict) serve different purposes and have intentionally different
shapes. Schema alignment would require significant refactoring of both systems
with no functional benefit. Close as won't-fix with explanation.

## Fixes — Single PR

### #955 — CLI docstrings show --json in wrong position

**Files:** `scripts/internal/build_curated_memory.py`, `scripts/internal/compact_session_context.py`

`--json` is on the parent parser (line 24/25 in each), but docstrings show it
after the subcommand (e.g., `list [--json]`). Fix: move `[--json]` to before
the subcommand name in each usage line.

### #946 — Assert WARNING severity in prose fallback test

**File:** `tests/unit/test_codex_plan_review_adapter.py`

The issue requests adding a severity assertion so prose fallback regressions
are caught. Need to find the test that exercises prose fallback parsing and
verify it asserts `severity == "WARNING"`.

### #995 — Limit DS-3 chart-regeneration claim to R0-R2/FULL

**File:** `plans/arc_d_v2/reporting_refactor_full_plan.md`

The DS-3 resolution note at line ~1106 should clarify that chart regeneration
was for R0-R2/FULL only (R3 was regenerated before the chart pipeline update).

### #1001 — Backfill governing_plan in 7 evidence manifests

**Files:** 7 `evidence_manifest.json` files under `docs/04_reports/arc_d_v2/`

Set `governing_plan` to `"plans/arc_d_v2/lineage_plan.md"` in:
- r0/canonical, r1/quick, r1/canonical, r2/quick, r2/canonical, r3/quick, r3/canonical

## Validation

- `uv run python -m pytest tests/unit/test_codex_plan_review_adapter.py -v` (for #946)
- `uv run ruff check && uv run ruff format` on changed Python files
- `make check-quiet` (Tier 2)

## Outcome

_(To be filled after implementation)_
