# <Initiative Name> — Governing Plan

**Date:** YYYY-MM-DD
**Status:** PROPOSED | ACTIVE | COMPLETED | SUPERSEDED
**Scope:** 1-2 sentence scope statement
**Supersedes:** link to prior plan, or "None"

---

## 1. Decision

What is being done and why. One paragraph.

## 2. Goals

1. Goal 1
2. Goal 2
3. ...

## 3. Key Definitions

Define terms, statuses, contracts, or conventions specific to this initiative.

## 4. Execution Structure

### 4.1 Phases / Rungs / Milestones

| Phase | Name | Description | Depends On |
|-------|------|-------------|------------|
| 0 | Infrastructure | Setup work before main execution | None |
| 1 | First milestone | ... | Phase 0 |

### 4.2 Step Template (per phase/rung)

Each phase/rung follows a standard sequence of steps. Define the step
sequence here. For each step, specify:

- **Commands:** Exact CLI commands to run
- **Validates:** Conditions that must hold before proceeding
- **Pass/Fail Criteria:** Specific, observable conditions that prove the step
  is done — not just "tests pass" but what outcome proves the feature works.
  Each step must include at least one verification command and expected result.
  Example:
  ```
  - `uv run python -m pytest tests/unit/test_audit.py -v` passes (≥8 tests)
  - `grep -c audit_reply src/bid_euchre/ops/*.py` returns ≥ 1
  ```
- **Error recovery:** What to do when something fails
- **Outputs:** Artifacts produced

### 4.3 Phase 0 Dependencies

List hard prerequisites that must be complete before main execution begins.

## 5. Sub-Plan Governance

Sub-plans are required for implementation-heavy steps (>3 files changed,
new code, or design choices not specified in this plan).

### 5.1 Sub-Plan Registry

Maintained in: `plans/<initiative>/sub_plan_registry.md`

Each sub-plan entry tracks:

| Field | Description |
|-------|-------------|
| `id` | Stable identifier: `SP-<phase>-<seq>` (e.g., `SP-0-01`) |
| `parent` | Parent plan section reference (e.g., "Phase 0, item 3") |
| `status` | `proposed`, `in_progress`, `blocked`, `completed`, `abandoned`, `superseded` |
| `owner` | Agent session ID or human name |
| `file` | Path to the sub-plan document |

### 5.2 When to Create a Sub-Plan

- The step requires >3 files changed
- The step involves new code (not just running existing scripts)
- The step has design choices not fully specified in this governing plan

### 5.3 Sub-Plan Lifecycle

```
proposed --> in_progress --> completed
                |               |
                v               v
             blocked       abandoned
                |
                v
           in_progress (after unblock)

Any status --> superseded (when replaced)
```

## 6. Checkpoint Contract

Each phase/rung maintains a `checkpoints.md` file at:
`plans/<initiative>/<phase>/checkpoints.md`

See `plans/_templates/checkpoints.md` for format.

## 7. Evidence / Output Contract

Define what artifacts each phase produces, where they live, and how
they are validated.

## 8. Risks

| Risk | Mitigation |
|------|------------|
| ... | ... |

## 9. Success Criteria

1. Criterion 1
2. Criterion 2

## Outcome

_To be filled after implementation._

- Result: COMPLETED | ABANDONED | SUPERSEDED
- PRs: #NNN, #NNN
- Notes: deviations from plan
