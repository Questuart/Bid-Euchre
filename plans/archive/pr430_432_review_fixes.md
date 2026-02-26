# Plan: PR 430–432 Review Fixes

Date: 2026-02-25
Status: Draft — awaiting approval
Scope: 2 findings (P1 blocking, P2 correctness), single PR

## Findings Summary

| ID | Severity | PR | File | Issue |
|----|----------|----|------|-------|
| P1 | Blocking | 432 | `20_outcome_health.py:115` | `Path.glob()` returns full paths; prepending `log_path / "logs"` again doubles the prefix |
| P2 | Correctness | 430 | `50_r0_matchups.py:130,264,271,471` | `deal_id` alone is not unique across matchups — causes undercount |

## PR Structure

**Single PR** — both fixes are small, independent, and review-fix scoped.

Branch: `fix/pr430-432-review-fixes`

## Fix Details

### P1: Double-prefix in log discovery (20_outcome_health.py)

**Root cause:** `Path.glob()` returns complete Path objects (absolute or repo-relative).
Wrapping them in `log_path / "logs" / f` duplicates the `logs/` component.

**Current code** (line 114–116):
```python
log_files = sorted(
    log_path / "logs" / f for f in (log_path / "logs").glob("*.jsonl")
)
```

**Fix** — use glob results directly (they're already full paths):
```python
log_files = sorted((log_path / "logs").glob("*.jsonl"))
```

This matches the pattern used by all other R0 notebooks:
- `10_feature_health.py:111` — `sorted(str(p) for p in (eval_path / "logs").glob("*.jsonl"))`
- `30_feature_outcome_eval.py:105` — `sorted(eval_log.glob("logs/*.jsonl"))`
- `50_r0_matchups.py:104` — `sorted(str(p) for p in logs_dir.glob("*.jsonl"))`

**Files changed:** `notebooks/arc_d/r0/20_outcome_health.py`

### P2: Deal uniqueness across matchups (50_r0_matchups.py)

**Root cause:** `build_eval_dataset` takes `deal_id` from the JSONL record
(eval_dataset.py:64). Each matchup simulation starts deal_id at 0, so
concatenating multiple matchup DataFrames creates colliding deal_ids.

Within a single matchup (filtered by `matchup_id`), `deal_id` is unique —
those call sites are fine. The bug is in **cross-matchup** contexts.

**Affected lines:**

| Line | Current | Fix |
|------|---------|-----|
| 130 | `df_all['deal_id'].nunique()` | `df_all.drop_duplicates(subset=['matchup_id', 'deal_id']).shape[0]` |
| 264 | `df_all['deal_id'].nunique()` | `df_all.drop_duplicates(subset=['matchup_id', 'deal_id']).shape[0]` |
| 271 | `df_all.drop_duplicates('deal_id')` | `df_all.drop_duplicates(subset=['matchup_id', 'deal_id'])` |
| 471 | `opp_df["deal_id"].nunique()` | `opp_df.drop_duplicates(subset=['matchup_id', 'deal_id']).shape[0]` |

**Lines NOT changed** (already scoped to single matchup):
- Line 121 — inside per-file loading loop (`mdf` = one matchup)
- Line 286 — inside `for mid in matchup_ids` loop (`mdf` = one matchup)
- Line 558 — inside `for mid in matchup_ids` loop (`mdf` = one matchup)

**Files changed:** `notebooks/arc_d/r0/50_r0_matchups.py`

## Helper extraction (optional but recommended)

To avoid repeating `drop_duplicates(subset=['matchup_id', 'deal_id']).shape[0]`
four times, define a one-liner near the top of the data loading section:

```python
def _n_deals(frame: pd.DataFrame) -> int:
    """Count unique deals using (matchup_id, deal_id) composite key."""
    if "matchup_id" in frame.columns:
        return frame.drop_duplicates(subset=["matchup_id", "deal_id"]).shape[0]
    return frame["deal_id"].nunique()
```

Then all four call sites become `_n_deals(df_all)` / `_n_deals(opp_df)`.
The fallback ensures the function works when matchup_id is absent (e.g., synthetic data).

## Validation

1. `make lint` — ruff check + format on both .py files
2. `make notebook-sync` — regenerate paired .ipynb files
3. Tier 1 tests — `uv run python -m pytest tests/ -k "notebook or eval_dataset"` (if any)
4. `make notebook-check` — verify no uncommitted notebook diffs
5. `make check-quiet` — full Tier 2 before opening PR

Manual spot-check: run `20_outcome_health` with a relative `EVAL_LOG_PATH` and verify
log files resolve without the doubled `logs/` prefix.

## Trace Matrix

| Finding | File | Lines | PR origin |
|---------|------|-------|-----------|
| P1 | `notebooks/arc_d/r0/20_outcome_health.py` | 114–116 | PR 432 |
| P2 | `notebooks/arc_d/r0/50_r0_matchups.py` | 130, 264, 271, 471 | PR 430 |
