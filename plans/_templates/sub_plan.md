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

## Verification Plan

_Required per Pattern 10 (§10.9 of
`plans/steward_platform/governing_plan.md`). Every deliverable below
ties to a named verification surface. **Strict existence, lenient form**
— every Work bullet or Readiness criterion names a surface; the surface
need not be pytest-uniform as long as it matches the deliverable class
per the §10.9 Pattern 10 table._

| Deliverable (§N.M) | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| (row per Work bullet or Readiness criterion) | (per §10.9 Pattern 10 table) | (path or command) | (lane) | (observable pass) |

**Worked example:**

| Deliverable | Class | Verification surface | Owner | Acceptance condition |
|---|---|---|---|---|
| §2 `scripts/internal/verify_map_coverage.py` | new Python script | `tests/unit/test_verify_map_coverage.py::test_coverage_threshold` | author | pytest passes; coverage computed is ≥90% on seeded fixture |
| §3 `verification_contract/map.md` authoring | new KB-class artifact | `INDEX.md` inclusion + `agent_readability_lint.py check verification-contract` clean | analyst | lint exits 0 |
| §4 feature flag `ENABLE_MAP_LINT` | config change | rollback test: flip flag off, re-run lint, expect degraded-but-non-fatal mode | ops | documented in §Rollback |

**Surface-class defaults** — see Pattern 10 table at §10.9 of
`plans/steward_platform/governing_plan.md` for the full deliverable-class
→ default-surface mapping. Placeholder tokens (TBD/TODO/FIXME/XXX) in
Verification surface column cause `/create-plan` refusal and `check
verification-contract` lint failures.

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
