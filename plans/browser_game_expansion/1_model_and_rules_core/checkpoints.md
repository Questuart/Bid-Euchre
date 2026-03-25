# Model and Rules Core Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `1_model_and_rules_core`
**Last updated:** 2026-03-24 by Codex

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phase 0 complete | PENDING | Phase 0 checkpoint Steps 1-4 are `COMPLETE` | -- | -- | Phase 1 must not begin until the proving and migration contracts are locked. |
| Step 1: Replace browser roster wiring with `full_ols_av` / `OLSa` | PENDING | `tests/unit/hosted_play/test_ai_manager.py -q` passes with `full_ols_av` as the visible default roster entry | -- | -- | `SP-1-01` |
| Step 2: Update config/env/docs for the new artifact contract | PENDING | `tests/unit/hosted_play/test_config.py -q` passes and docs no longer describe `hybrid_olsa` as the browser default | -- | -- | `SP-1-01` |
| Step 3: Add moon/loner bidding legality and overcall handling | PENDING | `tests/unit/hosted_play/test_engine.py -k 'moon or loner or overcall'` passes | -- | -- | `SP-1-02` |
| Step 4: Add moon exchange and loner sit-out trick flow | PENDING | seeded engine/integration tests cover exchange and 3-player loner trick order with 0 failures | -- | -- | `SP-1-02` |
| Step 5: Extend persistence/export state for new bid types | PENDING | `tests/unit/hosted_play/test_db.py`, `test_routes.py`, and export/replay tests pass with moon/loner hand data | -- | -- | `SP-1-02` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-1-01 | `1_model_and_rules_core/sub/2026-03-24_olsa-roster-migration.md` | proposed | Step 1 |
| SP-1-02 | `1_model_and_rules_core/sub/2026-03-24_moon-loner-hosted-play.md` | proposed | Steps 3-5 |

## Blockers

- [ ] Phase 0 not complete.

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and sub-plan registration.
- Next: once Phase 0 closes, execute `SP-1-01` first, then `SP-1-02`.
