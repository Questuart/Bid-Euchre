# R0 Advance Check Correctness Fixes

**Date:** 2026-03-15
**Status:** proposed
**Trigger:** Codex review findings on PR #688 (2 CRITICAL, 1 WARNING)

---

## Goal

Fix the two CRITICAL correctness issues found by Codex review of PR #688, plus
add missing Step 4 positive-path test coverage. These must be resolved before
the R0 QUICK canonical rerun can be trusted.

## Plan

### Fix 1: Deterministic artifact selection (CRITICAL)

**Problem:** `_load_json_glob()` in `tables.py` picks the newest artifact by mtime.
With stale artifacts from different modes/seeds in the same directory, this is
nondeterministic. A SMOKE artifact could be silently used for a QUICK table run.

**Fix:** Add `--mode` and `--seed` CLI args to `generate_rung_tables.py`. Pass them
from the orchestrator's Step 6. Update `generate_all_tables()` to construct exact
filenames (`h2h_battery_{mode}_{seed}.json`, `comparator_cis_{rung}_{seed}.json`)
when mode/seed are provided. Fall back to glob only when they're not (backwards
compatibility for manual invocation).

**Files:**
- `src/bid_euchre/arc_d_v2/tables.py` — `generate_all_tables()` accepts optional `mode`/`seed`
- `scripts/internal/generate_rung_tables.py` — add `--mode`/`--seed` CLI args
- `src/bid_euchre/arc_d_v2/orchestration.py` — Step 6 passes mode/seed to script

### Fix 2: Aggregate hypothesis evaluation for H6 (CRITICAL)

**Problem:** `_read_csv_value()` returns the first matching row. H6 checks "all models
bid > 50%" but only evaluates the first pooled row. The hypothesis semantics require
a minimum across all matching rows.

**Fix:** Add `_read_csv_aggregate()` function that collects ALL matching values and
applies an aggregate (`min`/`max`). Support a new `computation` value of `"min"` in
`evaluate_hypothesis()`. Update H6 in `hypotheses.json` to use `"computation": "min"`.

**Files:**
- `src/bid_euchre/arc_d_v2/advance_check.py` — add `_read_csv_aggregate()`, support `min`/`max` computations
- `plans/arc_d_v2/r0/hypotheses.json` — H6 computation: `"min"`

### Fix 3: Step 4 positive-path test (WARNING)

**Problem:** Step 4 tests only cover dry_run and empty-roster failure. No test for
the full config→experiment→parse success path.

**Fix:** Add a test that mocks all three subprocess calls (config gen, experiment,
parse) as successful and verifies the step completes with the correct state transitions.

**Files:**
- `tests/unit/test_rung_orchestrator.py` — add `TestStep4Execution` test class

## Files Changed

- `src/bid_euchre/arc_d_v2/tables.py` — deterministic artifact selection
- `src/bid_euchre/arc_d_v2/advance_check.py` — aggregate hypothesis evaluation
- `src/bid_euchre/arc_d_v2/orchestration.py` — pass mode/seed to Step 6
- `scripts/internal/generate_rung_tables.py` — mode/seed CLI args
- `plans/arc_d_v2/r0/hypotheses.json` — H6 computation fix
- `tests/unit/test_rung_orchestrator.py` — Step 4 positive-path test
- `tests/unit/test_rung_tables.py` — deterministic selection test

## Validation

- [ ] `uv run pytest tests/unit/test_rung_tables.py tests/unit/test_rung_orchestrator.py -v`
- [ ] `make check-quiet`

## Out of Scope

- Per-contract H2H faceting (WARNING, deferred — feature addition, not bug)
- R0 QUICK canonical rerun (post-merge validation)

## Outcome

_Filled after completion._
