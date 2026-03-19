# Post-Merge Review Patches — PRs #834, #835, #837

**Date:** 2026-03-18
**Trigger:** Consolidated post-merge review poll (9 review agents)
**Scope:** Follow-up fixes for CRITICAL/HIGH/actionable MEDIUM findings

## Context

Three code PRs (#834, #835, #837) were merged and reviewed post-merge.
No subsequent PRs (#832, #838) addressed any of the findings.
This plan groups fixes into focused PRs per the "one concept per PR" rule.

### Review Accuracy Corrections

Several review findings were inaccurate. Corrections verified via grep:

- **PR #837:** `--dataset-dir` is not a CLI flag. The gap is `execute_step_6()`
  and `execute_step_8()` having zero test coverage (`execute_step_9()` is a
  file-existence check, also untested). Step 7 already has 2 tests:
  `test_step_7_runs_interp_charts_when_available` (L2384) and
  `test_step_7b_includes_rung_and_mode_in_report_cmd` (L3145).
- **PR #835:** `start-agent-role.sh` exports `CLAUDE_ROLE`, not `CLAUDE_LANE_ID`.
  The writer is `write_registry()`, not `write_lane_metadata()`. No
  `role_to_lane_id()` function exists. Rule 75 does not exist — the
  persistence policy is in `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md`
  § Cleanup Policy.
- **PR #834:** The three "existing" column fallback tests reported by the
  exploration agent **do not exist** (verified: grep returned zero matches).
  `focal_seat` does **not** appear anywhere in `tables.py` — L1621 only
  checks for `"seat"`. The review's focal_seat findings are phantom —
  PR #834 added `tricks_won`/`actual` fallback for `value_col` and
  `contract_family`/`contract_type`/`contract` fallback for `contract_col`,
  NOT `focal_seat` fallback for `seat_col`.

### Plan Review Findings (Round 1)

2 CRITICAL, 3 WARNING addressed in this revision:
- ✅ CRITICAL: Removed phantom "existing tests" claim
- ✅ CRITICAL: Removed phantom `focal_seat` test targets
- ✅ WARNING: Fixed line number for stale warning (L1634, not L1643)
- ✅ WARNING: Removed step 7 from zero-coverage list (already has tests)
- ✅ WARNING: Grounded seed handling in actual `state.seeds` attribute

---

## PR 1: Test coverage for orchestration steps 6, 8, 9

**Addresses:** PR #837 — 1 CRITICAL + 2 HIGH (steps 6/8/9 zero coverage)
**Branch:** `fix/step6-8-9-orchestration-tests`
**Files to modify:**
- `tests/unit/test_rung_orchestrator.py` — add new test class

### Actual function signatures (from source)

```python
def execute_step_6(state: RunState, dry_run: bool = False) -> bool:
    # Seeds accessed via: state.seeds (list[int])
    # Seed CLI arg: ",".join(str(s) for s in state.seeds) if state.seeds else "42"
    # Script: scripts/internal/generate_rung_tables.py
    # Invoked via: run_subprocess(cmd, "6", rung)

def execute_step_8(state: RunState, dry_run: bool = False) -> bool:
    # Script: scripts/internal/generate_advance_check.py
    # Invoked via: run_subprocess(cmd, "8", rung)

def execute_step_9(state: RunState, dry_run: bool = False) -> bool:
    # File check: docs/04_reports/arc_d_v2/<rung>/<subdir>/04_rung_decision.md
    # No subprocess — just path existence check
```

### Tests to add

**Step 6 (table generation):**
1. **`test_step6_success_constructs_correct_command`** — mock `run_subprocess`,
   verify cmd includes `--rung-dir`, `--output-dir`, `--mode`, `--seed` with
   correct values derived from `state.rung`, `state.mode`, `state.seeds`
2. **`test_step6_dry_run_skips_subprocess`** — verify `run_subprocess` not
   called, step marked complete
3. **`test_step6_script_missing_skips`** — verify graceful skip when
   `generate_rung_tables.py` not found (L1421–1428)
4. **`test_step6_subprocess_failure_marks_failed`** — verify `mark_step_failed`
   called with error message when `run_subprocess` returns `(False, error)`
5. **`test_step6_multi_seed_comma_separated`** — verify `state.seeds=[42,123]`
   produces `--seed 42,123` in command; `state.seeds=None` produces `--seed 42`

**Step 8 (advance check):**
6. **`test_step8_success_constructs_correct_command`** — verify cmd includes
   `--hypotheses`, `--tables-dir`, `--output`, `--mode`, `--rung`
7. **`test_step8_dry_run_skips_subprocess`** — analogous to step 6
8. **`test_step8_subprocess_failure_marks_failed`** — analogous to step 6

**Step 9 (narrative marker):**
9. **`test_step9_decision_exists_marks_complete`** — mock `decision_path.exists()`
   returning True, verify `mark_step_complete("9")` called
10. **`test_step9_decision_missing_marks_skipped`** — mock returning False,
    verify `mark_step_skipped("9", ...)` called

### Approach
- Follow existing patterns from step 0–5 tests in the same file
- Use `unittest.mock.patch` on `run_subprocess` (already used in step 5 tests)
- Use `tmp_path` for `_repo_root()` mocking
- Each test is self-contained with a minimal `RunState`

---

## PR 2: Widen `INFRA_PATH_PREFIXES` + CLAUDE.md worktree caveat

**Addresses:** PR #835 — 1 MEDIUM (infra gate gap) + 1 MEDIUM (doc contradiction)
**Branch:** `fix/infra-gate-coverage`
**Files to modify:**
- `scripts/lint_repo.py` L627–631 — add `.claude/scripts/` and `.claude/tmux/`
  to `INFRA_PATH_PREFIXES`
- `CLAUDE.md` L19 — add caveat: "(ephemeral PR worktrees only; persistent
  role worktrees are never cleaned up — see
  `docs/02_agent/AUTONOMOUS_OPERATOR_WORKFLOW.md` § Cleanup Policy)"
- `tests/unit/test_lint_repo.py` — add tests:
  1. `test_modified_claude_script_without_tests_violation` — `.claude/scripts/foo.sh`
  2. `test_modified_tmux_script_without_tests_violation` — `.claude/tmux/bar.sh`
  3. `test_new_claude_script_no_violation` — additions exempt (existing pattern)

---

## PR 3: Column fallback tests for `generate_seat_balance_csv`

**Addresses:** PR #834 — 2 MEDIUM (untested column fallback paths)
**Branch:** `fix/seat-balance-fallback-tests`
**Files to modify:**
- `tests/unit/test_rung_tables.py` — add to existing `TestChartDataGeneration` class

### Actual column logic (from `tables.py` L1620–1639)

```python
seat_col = "seat" if "seat" in df.columns else None  # L1621
contract_col = "contract_family" if ... else "contract_type" if ... else "contract" if ... else None  # L1622-1628
value_col = "tricks_won" if ... else "actual" if ... else None  # L1629-1631

if seat_col is None or value_col is None:
    logger.warning(...)  # L1634
    return None  # L1639

if contract_col:
    grouped = df.groupby([seat_col, contract_col])  # L1643
else:
    grouped = df.groupby(seat_col)  # pooled path, L1654
```

### Tests to add

1. **`test_seat_balance_no_seat_col_returns_none`** — DataFrame with only
   `tricks_won` and `contract_family` (no `seat`) → returns None, logs warning
2. **`test_seat_balance_no_value_col_returns_none`** — DataFrame with only
   `seat` (no `tricks_won` or `actual`) → returns None, logs warning
3. **`test_seat_balance_pooled_no_contract_col`** — DataFrame with `seat` +
   `tricks_won` but NO contract column → uses pooled groupby on seat_col only
4. **`test_seat_balance_contract_type_fallback`** — DataFrame with
   `contract_type` (not `contract_family`) → uses `contract_type` as contract_col
5. **`test_seat_balance_actual_fallback`** — DataFrame with `actual` (not
   `tricks_won`) → uses `actual` as value_col

---

## Deferred / Accepted Risk

| Finding | Disposition |
|---------|-------------|
| PR #835 HIGH: `write_registry()` untested | **Deferred.** No shell test infra. Infra gate widening (PR 2) prevents future gaps. Follow-up issue. |
| PR #835 HIGH: `bootstrap_role()` untested | **Deferred.** Same rationale. |
| PR #835 HIGH: `CLAUDE_ROLE` export untested | **Deferred.** Same rationale. |
| PR #835 HIGH: Registry schema compatibility | **Deferred.** Same rationale. |
| PR #835 HIGH: Stale `last_active` on reattach | **Deferred.** Design decision needed. Follow-up issue. |
| PR #837 LOW: `MODE_DATASET_SEEDS` silent fallback | **Accepted.** Defensive default. |
| PR #837 INFO: Runbook `shards/` mismatch | **Pre-existing.** |
| PR #834 LOW (×3): Docstring, float check, deferred import | **Accepted.** Style issues. |
| PR #835 MEDIUM: python3 in POSIX script | **Accepted.** macOS-only. |
| PR #835 MEDIUM: `tmux_pane` mixed type | **Accepted.** Cosmetic. |

## Follow-Up Issues to File

1. **Shell script test infrastructure** — smoke test harness for
   `.claude/scripts/` and `.claude/tmux/` (covers `write_registry`,
   `bootstrap_role`, `CLAUDE_ROLE` export, registry schema)
2. **Stale `last_active` on tmux reattach** — metadata only written on
   initial bootstrap, drifts from reality on subsequent attaches

## Execution Order

All three PRs are independent — can execute in parallel.
Priority: PR 1 (CRITICAL) > PR 2 (preventive) > PR 3 (coverage).

## Outcome

<!-- Fill after implementation -->
