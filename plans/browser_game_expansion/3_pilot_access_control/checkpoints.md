# Pilot Access Control Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `3_pilot_access_control`
**Last updated:** 2026-03-24 by Codex

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phase 1 schema direction is locked | PENDING | Phase 1 storage/state fields are complete enough to extend player/match access safely | -- | -- | Access work should not race unresolved schema direction. |
| Step 1: Add invite-code data model and migration | PENDING | DB tests pass with invite-code fields/tables present and old paths migrated or rejected explicitly | -- | -- | `SP-3-01` |
| Step 2: Add code-gated entry/session flow | PENDING | route/integration tests prove invalid code denied and valid code grants access | -- | -- | `SP-3-01` |
| Step 3: Add player-chosen nickname bound to invited player | PENDING | first-use nickname flow works after valid code entry and survives refresh/session resume | -- | -- | `SP-3-01` |
| Step 4: Add admin code-generation workflow and smoke proof | PENDING | code generator/admin command produces usable invite records and one end-to-end smoke path passes | -- | -- | `SP-3-01` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-3-01 | `3_pilot_access_control/sub/2026-03-24_invite-codes-and-nickname-flow.md` | proposed | Steps 1-4 |

## Blockers

- [ ] Phase 1 schema contract not yet locked.

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and invite-code scope lock.
- Next: begin after Phase 1 lands; can overlap with late Phase 2 UI work once the schema path is stable.
