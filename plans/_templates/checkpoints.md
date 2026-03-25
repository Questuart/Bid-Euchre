# <Phase/Rung Name> Checkpoints

**Governing plan:** `plans/<initiative>/governing_plan.md`
**Phase/Rung:** <identifier>
**Last updated:** YYYY-MM-DD by <agent/session>

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: <name> | PENDING | `<verification command>` → `<expected result>` | -- | -- | -- |
| Step 1: <name> | PENDING | `<verification command>` → `<expected result>` | -- | -- | -- |
| Step 2: <name> | PENDING | `<verification command>` → `<expected result>` | -- | -- | -- |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

**Validates column:** Every step must define at least one specific, observable
pass/fail condition — not just "tests pass" but a concrete verification command
and expected result. A step cannot be marked `COMPLETE` unless its Validates
condition has been verified.

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-0-01 | `sub/2026-03-14_slug.md` | in_progress | Step 2 |

## Blockers

List anything preventing forward progress. Each blocker should link to a
Q&A log entry or sub-plan.

- [ ] Blocker description -- linked to Q-N in qa_log.md

## Session Log

Reverse chronological. One entry per agent session that touched this phase.

### YYYY-MM-DD -- <agent/session>
- Completed: Step X, Step Y
- In progress: Step Z (3/5 models trained)
- Issues: description
- Next: what the next session should do
