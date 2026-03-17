# Per-Contract H2H Faceting + Multi-Seed FULL Aggregation

**Date:** 2026-03-15
**Status:** proposed

---

## Goal

Two features needed before R0 FULL:
1. Per-contract H2H faceting — emit suit/high/low rows in h2h_delta_matrix.csv (unblocks H1/H3/H4)
2. Multi-seed FULL aggregation — table generation merges artifacts across seeds [42, 123, 456]

## Plan

### Fix 1: Per-contract H2H faceting

**Where the data is:** JSONL logs have `contract` field on every `hand_end` event.
`parse_run_results()` reads these but computes only pooled metrics.

**Design:** Add per-contract metrics to the H2H battery JSON cells.

**Changes:**
- `scripts/internal/run_arc_d_h2h_battery.py` `parse_run_results()`:
  Group records by contract type. For each contract, compute the same
  metrics (delta, CI, win_rate). Store in `cell["by_contract"]["suit"]` etc.
- `src/bid_euchre/arc_d_v2/tables.py` `generate_h2h_delta_matrix()`:
  Emit per-contract rows from `cell["by_contract"]` in addition to the pooled row.

### Fix 2: Multi-seed FULL table aggregation

**Problem:** `generate_all_tables(mode, seed)` loads one artifact file. FULL mode
produces 3 (seeds 42, 123, 456).

**Design:** Accept `seeds: list[int]` instead of `seed: int`. Load all matching
artifacts and merge by averaging metrics across seeds.

**Changes:**
- `src/bid_euchre/arc_d_v2/tables.py`:
  - `_load_json_glob()` → `_load_json_multi_seed()` variant for multi-seed
  - `generate_all_tables(seeds=...)` loads and merges multiple batteries/CIs
  - Merging: average deltas, average win_rates, widen CIs
- `scripts/internal/generate_rung_tables.py`: `--seed` accepts comma-separated list
- `src/bid_euchre/arc_d_v2/orchestration.py` Step 6: pass all seeds

## Files Changed

- `scripts/internal/run_arc_d_h2h_battery.py` — per-contract grouping in parse
- `src/bid_euchre/arc_d_v2/tables.py` — per-contract H2H rows + multi-seed loading
- `scripts/internal/generate_rung_tables.py` — multi-seed CLI arg
- `src/bid_euchre/arc_d_v2/orchestration.py` — pass all seeds to Step 6
- `tests/unit/test_rung_tables.py` — per-contract H2H table test
- `tests/unit/test_rung_orchestrator.py` — multi-seed table generation test

## Validation

- [ ] `uv run pytest tests/unit/test_rung_tables.py tests/unit/test_rung_orchestrator.py -v`
- [ ] `make check-quiet`
- [ ] SMOKE rerun: `uv run python scripts/internal/run_rung.py --rung r0 --mode smoke`

## Outcome

_Filled after completion._
