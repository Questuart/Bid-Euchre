# SP-3-01: Invite Codes and Nickname Flow

**ID:** SP-3-01
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 3 -- Pilot Access Control
**Status:** proposed
**Owner:** --

---

## Inputs

- `web/db.py`
- `web/schema.sql`
- `web/routes.py`
- `web/templates/`
- `docs/01_core/DEPLOYMENT.md`
- existing player/match/private-link flow

## Assumptions

- Pilot auth is invite-code based, not password based.
- A player may choose their display nickname after valid code entry.
- The current private-link flow may remain, but invite-code gating becomes
  mandatory before actual play access.

## Dependencies

- Phase 1 schema direction locked

## Plan

### Step 1: Add invite-code persistence and migration

- Add invite/access data to the hosted-play persistence layer.
- Support active/revoked states and secure storage for codes.

### Step 2: Gate browser access on a valid code

- Add the code-entry route/form/session behavior.
- Ensure invalid or revoked codes cannot reach gameplay.

### Step 3: Bind nickname to the invited player flow

- Allow a user-chosen display nickname after successful code entry.
- Preserve the nickname across refresh/resume/session behavior.

### Step 4: Add a small admin workflow

- Add a repo-owned script/command to create invite codes and print/share the
  information the user needs.
- Keep the workflow small enough for 20-40 invited users.

## Files Changed

- `web/db.py`
- `web/schema.sql`
- `web/routes.py`
- `web/templates/game.html`
- `web/templates/partials/` -- access-code and nickname forms
- `scripts/internal/` -- new invite-code admin helper
- `docs/01_core/DEPLOYMENT.md`
- `tests/unit/hosted_play/test_db.py`
- `tests/unit/hosted_play/test_routes.py`
- `tests/integration/hosted_play/`
- `tests/e2e/hosted_play/`

## Validation

### Pass/Fail Criteria

- [ ] **DB tests:** `uv run python -m pytest tests/unit/hosted_play/test_db.py -q`
  - Expected: invite-code schema/constraints pass.
- [ ] **Route tests:** `uv run python -m pytest tests/unit/hosted_play/test_routes.py -k 'invite or code or nickname' -q`
  - Expected: invalid code denied; valid code grants entry; nickname persists.
- [ ] **Integration check:** run the admin code generator and redeem one generated code locally
  - Expected: generated invite can unlock the intended player flow.
- [ ] **Browser proof:** E2E flow from code entry to gameplay
  - Expected: a valid invited player reaches the board; an invalid one does not.

## Planned Outputs

- Invite-code access control
- Player-chosen nickname flow
- Admin code-generation workflow

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: ready once schema direction is stable.
- Next action: implement persistence and route gating before launch validation.
- Blockers: Phase 1 incomplete.
- Files with uncommitted changes: --
