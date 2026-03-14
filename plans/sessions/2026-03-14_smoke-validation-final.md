# SMOKE Validation Run — 2026-03-14

## Goal

Run clean SMOKE end-to-end (`run_rung.py --rung r0 --mode smoke`) and fix
blockers preventing completion.

## Fixes Applied

### 1. `--skip-validation` in SMOKE mode (primary fix)

**File:** `src/bid_euchre/arc_d_v2/orchestration.py` (execute_step_2)

SMOKE mode (500 deals) produces insufficient data for Gate X2 R-squared
validation thresholds. The `--skip-validation` flag exists in
`train_action_value.py` but the orchestrator was not passing it.

**Fix:** Added `--skip-validation` to the training command when
`state.mode == "smoke"`.

### 2. Step 3 command interface mismatch

**File:** `src/bid_euchre/arc_d_v2/orchestration.py` (execute_step_3)

The orchestrator was calling `generate_rung_tables.py` with `--rung`,
`--mode`, `--seed`, `--tables` flags that the script does not accept.
The script's actual interface is `--rung-dir` and `--output-dir`.

**Fix:** Rewrote step 3 to:
- Collect training artifacts into `data/artifacts/arc_d_v2/<rung>/` with
  the `training_artifact_<model>.json` naming convention
- Copy `roster.json` from the plan directory
- Call the script with `--rung-dir` and `--output-dir`

### 3. Step 3b command interface mismatch

**File:** `src/bid_euchre/arc_d_v2/orchestration.py` (execute_step_3b)

Same issue: orchestrator was calling `generate_interpretability.py` with
`--rung`, `--mode`, `--seed` but the script expects `--rung-dir` and
`--report-dir`.

**Fix:** Updated command to use `--rung-dir` and `--report-dir`.

## SMOKE Run Results

| Step | Name | Status | Notes |
|------|------|--------|-------|
| 0 | Precondition check | PASS | Plan, hypotheses, checkpoints found |
| 1 | Generate training dataset | PASS | 500 deals, ~79s |
| 2 | Train roster models | PASS | 5 models trained with `--skip-validation` |
| 3 | Offline eval + data sanity | PASS | Tables generated from training artifacts |
| 3b | Interpretability (SHAP) | PASS | SHAP values computed |
| 4 | H2H battery | PASS | Config generated (81 matchups x 50 deals) |
| 5 | Comparator battery | FAIL | See below |
| 6-9 | Remaining steps | NOT RUN | Blocked by step 5 |

### Step 5 Failure Analysis

The comparator script fails because trained R0 models (39 features, no
auction context) are being loaded with partner feature inference that
expects `current_high_bid` in the feature names. This is a model-spec
vs runtime mismatch:

- R0 models have 39 hand features (no `current_high_bid`)
- The `ActionValueBidder` tries to infer partner features at runtime
  and fails when `current_high_bid` is absent

This is a **pre-existing orchestration issue** unrelated to the fixes
in this PR. The R0 roster definition needs to either:
1. Disable partner feature inference for R0 models, or
2. Include `current_high_bid` in R0 training

**Recommendation:** File as a follow-up issue for the Arc D v2 lineage work.

## Tests

- 87 tests pass in `test_rung_orchestrator.py` (including 2 new tests)
- `make check-quiet` passes

## Outcome

PR: fix/smoke-skip-validation
