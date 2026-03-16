# R0 QUICK Orchestration Cleanup

**ID:** SP-0-01
**Date:** 2026-03-14
**Parent:** `plans/arc_d_v2/lineage_plan.md` -- §9 Step 4, §9 Step 5, §9 Step 8, §9.5 QUICK→FULL transition
**Status:** in_progress
**Owner:** Claude

---

## Inputs

- Input 1: `plans/arc_d_v2/lineage_plan.md` -- canonical rung execution and reporting contract for R0*
- Input 2: `plans/arc_d_v2/r0/checkpoints.md` -- current human-readable rung state after PR #687
- Input 3: `src/bid_euchre/arc_d_v2/orchestration.py` -- orchestrator step execution and state handling
- Input 4: `src/bid_euchre/arc_d_v2/advance_check.py` -- machine-readable advance decision logic
- Input 5: `src/bid_euchre/arc_d_v2/tables.py` -- canonical table generation from H2H/comparator artifacts
- Input 6: `plans/arc_d_v2/r0/hypotheses.json` -- hypothesis definitions with table references
- Input 7: PR #687 findings -- bugs found during exploratory QUICK run

## Assumptions

- LA-2 is correctly implemented and does not require changes.
- The desired outcome is canonical `run_rung.py --rung r0 --mode quick` with no manual workarounds.
- Governing plan remains unchanged; this is a fix pass for orchestration defects.
- Raw generated outputs under `data/runs/` remain uncommitted.

## Dependencies

- PR #687 merged (pass gate + validation fixes).
- No other sub-plans block this work.

## Plan

### Step 1: Fix table generator filename resolution (tables.py)

**Problem:** `generate_all_tables()` hardcodes `h2h_battery.json` and `comparator_cis.json`
(lines 549-550), but the orchestrator writes `h2h_battery_{mode}_{seed}.json` and
`comparator_cis_{rung}_{seed}.json`.

**Fix:** Replace hardcoded paths with glob patterns that find the most recent matching
file. E.g., `sorted(rung_dir.glob("h2h_battery*.json"))[-1]` for the latest match.
Only matches `h2h_battery_*.json` (with underscore after "battery") to avoid false
positives. Falls back to the legacy `h2h_battery.json` name for backwards compatibility.
Same pattern for `comparator_cis*.json`.

### Step 2: Fix advance check hypothesis evaluation (advance_check.py + hypotheses.json)

Five distinct mismatches between hypothesis filter keys and actual table column names:

| Hypothesis | Filter Key | Actual Column | Fix Location |
|-----------|-----------|---------------|-------------|
| H1-H4,H7 | `challenger` | `model_a` | hypotheses.json |
| H1-H4,H7 | `opponent` | `model_b` | hypotheses.json |
| H1-H4,H7 | `net_eppd` (source_column) | `net_eppd_delta` | hypotheses.json |
| H5 | `contract_type` | `contract` | hypotheses.json |
| H5,H8,H9 | `comparator_filter` + `value - comparator_value` | code checks `anchor_filter` + `value - anchor_value` | advance_check.py |

**Fix in hypotheses.json:** Update filter keys and column names to match actual table schemas.
**Fix in advance_check.py:** Support `comparator_filter` + `value - comparator_value` in
`evaluate_hypothesis()` alongside the existing `anchor_filter`/`value - anchor_value`.

**H6 (pass_rate):** The `pass_rate` column doesn't exist in comparator_rankings.csv.
Convert H6 to use `bid_rate` with inverted threshold (bid_rate < 1.0 instead of
pass_rate > 0) or add pass_rate to the table generator. Simplest: update hypotheses.json
to check `bid_rate > 0.5` (all models should bid more than half the time).

### Step 3: Fix sufficiency check table name (advance_check.py)

**Problem:** `check_sufficiency()` expects `h2h_matrix.csv` (line 145) but the actual
table is `h2h_delta_matrix.csv`.

**Fix:** Update the expected table name from `h2h_matrix.csv` to `h2h_delta_matrix.csv`.

### Step 4: Fix orchestrator Step 4 to run H2H experiments (orchestration.py)

**Problem:** Step 4 only calls `run_arc_d_h2h_battery.py` which generates config + empty
summary, but doesn't run `run_experiment.py` to execute the actual H2H matchups.

**Fix:** After the config-generation subprocess succeeds, add two more subprocess calls:
1. `uv run python experiments/run_experiment.py --seed {seed} --config {config_path}`
2. `uv run python scripts/internal/run_arc_d_h2h_battery.py --parse-run {run_dir} --output {output}`

The config path is the `h2h_battery_{mode}_config.yaml` file written by the first call.
The run directory can be found by globbing `data/runs/arc_d_r0_h2h_battery_{seed}_*`.

### Step 5: Fix mode transition invalidation (orchestration.py)

**Problem:** When mode changes (SMOKE→QUICK), the orchestrator skips steps that were
completed at the prior mode because `state.json` still says `complete`.

**Fix:** In the mode-change detection code (the existing `Mode changed from X to Y` log),
also check each step's fingerprint mode. If a step was completed at a lower mode, reset
it to `pending`. This ensures QUICK doesn't reuse SMOKE results.

### Step 6: Add regression tests

- **test_rung_tables.py:** Test that `generate_all_tables()` finds mode/seed-suffixed
  filenames via glob (mock the filesystem with both naming conventions).
- **test_advance_check.py or test_rung_orchestrator.py:** Test hypothesis evaluation
  with real H2H column names (`model_a`/`model_b`/`net_eppd_delta`).
- **test_rung_orchestrator.py:** Test mode invalidation logic.

### Step 7: Validate and PR

- Run `make check-quiet` to verify all tests pass.
- Commit and push from worktree.
- Canonical rerun (`--mode quick`) deferred to post-merge validation if wall time is
  a concern (~25 min). A SMOKE rerun (`--mode smoke`) can validate the orchestrator
  path end-to-end in ~3 min.
- Create focused PR with exact repro commands.

## Files Changed

- `src/bid_euchre/arc_d_v2/tables.py` -- glob for mode/seed-suffixed filenames
- `src/bid_euchre/arc_d_v2/advance_check.py` -- comparator_filter support, sufficiency table name
- `src/bid_euchre/arc_d_v2/orchestration.py` -- Step 4 experiment execution, mode invalidation
- `plans/arc_d_v2/r0/hypotheses.json` -- column name corrections
- `tests/unit/test_rung_tables.py` -- filename glob regression
- `tests/unit/test_rung_orchestrator.py` -- mode invalidation, Step 4 execution
- `plans/arc_d_v2/r0/checkpoints.md` -- state update after canonical rerun
- `plans/arc_d_v2/sub_plan_registry.md` -- SP-0-01 status update

## Validation

- [ ] `uv run pytest tests/unit/test_rung_tables.py -v`
- [ ] `uv run pytest tests/unit/test_rung_orchestrator.py -v`
- [ ] `make check-quiet`
- [ ] SMOKE rerun: `uv run python scripts/internal/run_rung.py --rung r0 --mode smoke`
- [ ] (Post-merge) QUICK rerun: `uv run python scripts/internal/run_rung.py --rung r0 --mode quick`

## Planned Outputs

- Canonical orchestrator path that runs Steps 0-8 without manual workarounds
- Machine-readable advance check that evaluates all 9 hypotheses
- Regression test coverage for filename resolution, column mapping, mode invalidation
- Focused cleanup PR

## Observed Outputs

_Filled during/after execution._

## Outcome

_Filled after completion._

- Status: in_progress
- PR: TBD
- Deviations from plan: TBD
- Issues discovered: TBD
