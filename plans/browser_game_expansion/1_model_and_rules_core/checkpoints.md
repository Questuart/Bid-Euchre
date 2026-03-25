# Model and Rules Core Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `1_model_and_rules_core`
**Last updated:** 2026-03-25 by analyst (reconcile shipped overnight work)

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phase 0 complete | COMPLETE | Phase 0 checkpoint Steps 1-4 are `COMPLETE` | 2026-03-25 | overnight fleet | Phase 0 confirmed complete before Phase 1 execution. |
| Step 1: Replace browser roster wiring with `full_ols_av` / `OLSa` | COMPLETE | `tests/unit/hosted_play/test_ai_manager.py -q` passes with `full_ols_av` as the visible default roster entry | 2026-03-25 | brws-author-a | PR #1798 merged. `SP-1-01` |
| Step 2: Update config/env/docs for the new artifact contract | COMPLETE | `tests/unit/hosted_play/test_config.py -q` passes and docs no longer describe `hybrid_olsa` as the browser default | 2026-03-25 | brws-author-a | Included in PR #1798. `SP-1-01` |
| Step 3: Add moon/loner bidding legality and overcall handling | COMPLETE | `tests/unit/hosted_play/test_engine.py -k 'moon or loner or overcall'` passes | 2026-03-25 | brws-author-a | PR #1804 merged. `SP-1-02` |
| Step 4: Add moon exchange and loner sit-out trick flow | COMPLETE | seeded engine/integration tests cover exchange and 3-player loner trick order with 0 failures | 2026-03-25 | brws-author-a | Included in PR #1804. `SP-1-02` |
| Step 5: Extend persistence/export state for new bid types | COMPLETE | `tests/unit/hosted_play/test_db.py`, `test_routes.py`, and export/replay tests pass with moon/loner hand data | 2026-03-25 | brws-author-a | Included in PR #1804. `SP-1-02` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-1-01 | `1_model_and_rules_core/sub/2026-03-24_olsa-roster-migration.md` | completed | Step 1 |
| SP-1-02 | `1_model_and_rules_core/sub/2026-03-24_moon-loner-hosted-play.md` | completed | Steps 3-5 |

## Blockers

None remaining. Phase 1 is complete.

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and sub-plan registration.
- Next: once Phase 0 closes, execute `SP-1-01` first, then `SP-1-02`.

### 2026-03-25 -- overnight fleet (reconciled by analyst)
- Completed: All steps (0-5). PR #1798 (OLSa roster), PR #1804 (moon/loner core).
- Phase 1 is COMPLETE. Phase 2 can begin.
