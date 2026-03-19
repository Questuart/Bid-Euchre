# Post-Merge Review Batch Follow-ups
**Date:** 2026-03-18
**Goal:** Fix div-by-zero bug, document metric semantics, and file follow-up issues for all WARN findings from the PR #903/#906/#909/#918 post-merge review batch.

## Context

Post-merge reviews of 4 PRs produced 10 WARN findings total, 0 BLOCKs. This plan addresses all follow-up actions, prioritized by risk.

## Plan

### PR 1: fix/dashboard-divzero — Bug fix + smoke tests
**Branch:** `fix/dashboard-divzero`
**Scope:** `scripts/generate_dashboard.py`, new test file

**Changes:**
1. Guard division in `_draw_bollinger_panel` (line 354-356) when `n_valid == 0`
   - Wrap the stats bar text in `if n_valid > 0:` guard
   - When `n_valid == 0`, display "No valid Bollinger data" instead
2. Fix misleading `WINDOW` comment at line 32 ("10 working days ≈ 2 calendar weeks") — the data includes all days with commits, not just weekdays. Change to "10 active days".
3. Add `tests/unit/test_generate_dashboard.py` with:
   - `test_bollinger_empty_data` — n < WINDOW, verifies no crash
   - `test_bollinger_basic` — verifies SMA/band computation for known input
   - `test_draw_bollinger_panel_zero_valid` — matplotlib panel renders without error when n_valid=0
   - `test_generate_dashboard_smoke` — end-to-end with a tiny git repo fixture

**Key function signatures (from code read):**
- `_bollinger(data: np.ndarray, window: int, num_std: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]`
- `_draw_bollinger_panel(ax, x, data, sma, upper, lower, pct_b, valid, latest_idx, *, band_color, sma_color, dot_color) -> None`
- `generate_dashboard(repo: str, output: str) -> None`

**Validation:** `uv run python -m pytest tests/unit/test_generate_dashboard.py -v`

### PR 2: docs/metric-denominator-semantics — Documentation
**Branch:** `docs/metric-denominator-semantics`
**Scope:** `docs/01_core/METRICS.md` only

**Changes:**
Add a new subsection under "Auction Metrics" documenting the denominator difference:
- Pooled `net_eppd`: denominator = all deals (including all-pass redeals)
- Per-contract `net_eppd`: denominator = only deals with actual bids in that contract type
- Per-contract `bid_rate` is always 1.0 by construction (all-pass excluded)
- Caveat: pooled and per-contract `net_eppd` are NOT directly comparable due to different denominators

**Validation:** `make docs-check`

### Issue 3: File 5 follow-up issues
**No branch needed — GitHub issues only.**

| # | PR | Finding | Label |
|---|-----|---------|-------|
| 1 | #906 | CI classifier input mismatch — `changed_files` list may diverge from `dorny/paths-filter` output | `follow-up`, `fix:process` |
| 2 | #906 | Duplicate severity-mapping logic in `review_driver.py` and `prechecks.py` | `follow-up`, `fix:convention` |
| 3 | #906 | Inconsistent JSON schema between precheck output and review loop state | `follow-up`, `fix:convention` |
| 4 | #909 | Missing test coverage for multi-seed merge path with `bidders_by_contract` | `follow-up`, `fix:test` |
| 5 | #918 | flock/rename race condition in event draining | `follow-up`, `fix:process` |

## Files
- `scripts/generate_dashboard.py` — guard div-by-zero, fix comment
- `tests/unit/test_generate_dashboard.py` — new test file (smoke tests)
- `docs/01_core/METRICS.md` — add per-contract denominator semantics section

## Rollback
Both PRs are low-risk and reversible via `git revert`. No data migrations or schema changes.

## Execution Order
1. PR 1 (bug fix) — highest priority, real correctness bug
2. PR 2 (docs) — can run in parallel with PR 1
3. Issues — file after PRs are created (reference PR URLs in issue bodies)

## Outcome
- PR 1: #933 — fix: guard division-by-zero in dashboard Bollinger stats bar
- PR 2: #931 — docs: document per-contract vs pooled net_eppd denominator semantics
- Issues: #934, #935, #936, #937, #938
- Labels created: `fix:process` (#c5def5), `fix:convention` (#0075ca)
