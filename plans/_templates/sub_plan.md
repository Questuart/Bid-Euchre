# <Sub-Plan Title>

**ID:** SP-<phase>-<seq>
**Date:** YYYY-MM-DD
**Parent:** `<governing_plan_path>` -- <section reference> (e.g., "Phase 0, item 3")
**Status:** proposed | in_progress | blocked | completed | abandoned | superseded
**Owner:** <agent session ID or human name>

---

## Inputs

What this sub-plan consumes. Be specific: file paths, artifact names,
prior sub-plan outputs.

- Input 1: `path/to/artifact` -- description
- Input 2: ...

## Assumptions

Conditions assumed true. If any assumption is violated, escalate before
proceeding.

- Assumption 1
- Assumption 2

## Dependencies

Other sub-plans or steps that must complete first.

- `SP-<X>-<Y>` -- reason
- Phase 0 item N -- reason

## Plan

### Step 1: <title>
- Detail
- Detail

### Step 2: <title>
- Detail

## Files Changed

- `path/to/file.py` -- what changes
- `path/to/new_file.py` -- NEW: purpose

## Validation

How to verify correctness before marking COMPLETE. Every sub-plan must
include at least one **integration-level** verification — not just "unit
tests pass" but proof the feature works end-to-end.

### Pass/Fail Criteria

Define specific, observable conditions that prove the work is done:

- [ ] **Test command:** `uv run python -m pytest tests/unit/test_X.py -v`
  - Expected: ≥N tests pass, 0 failures
- [ ] **Integration check:** `<command that exercises the feature end-to-end>`
  - Expected: `<specific output or behavior>`
- [ ] **Wiring proof (for library code):** `grep -c <function_name> src/bid_euchre/<caller>.py`
  - Expected: ≥ 1 (at least one non-test caller exists)
- [ ] **Smoke check:** description
- [ ] `make check` passes

## Planned Outputs

Artifacts this sub-plan will produce.

- `path/to/output1` -- description
- `path/to/output2` -- description

## Observed Outputs

_Filled during/after execution._

- Output 1: actual path, notes on deviations
- Output 2: ...

## Outcome

_Filled after completion._

- Status: completed | abandoned | superseded
- PR: #NNN (if applicable)
- Deviations from plan: ...
- Issues discovered: ...

## Handoff

_Filled at session end if work is incomplete._

- Current state: what has been done
- Next action: what the next agent should do first
- Blockers: anything preventing progress
- Files with uncommitted changes: list
