# Execution Foundation Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `0_execution_foundation`
**Last updated:** 2026-03-25 by brws-author-a

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Register expansion initiative package | COMPLETE | `find plans/browser_game_expansion -maxdepth 2 -type f | wc -l` returns `>= 5` | 2026-03-24 | Codex | Governing plan, roadmap, proving matrix, registry, and checkpoints created. |
| Step 1: Lock proving checklist and validation tiers | COMPLETE | `docs/01_core/HOSTED_PLAY_PROVING_CHECKLIST.md` exists with baseline + expansion feature IDs | 2026-03-25 | brws-author-a | Created `HOSTED_PLAY_PROVING_CHECKLIST.md` with 15 baseline items (B-01..B-15), 27 expansion items (E-01..E-27), 3 user proving runs (D-01..D-03), and 4 validation tiers (A/B/C/D). |
| Step 2: Lock repo-owned browser automation stack | COMPLETE | `tests/e2e/hosted_play/` exists with discoverable scaffold tests; `e2e` pytest marker registered | 2026-03-25 | brws-author-a | Created E2E test scaffold at `tests/e2e/hosted_play/` with conftest, placeholder test, and `e2e` marker in `pytest.ini`. Playwright/MCP integration deferred to Phase 4 (PR-7) implementation. |
| Step 3: Lock migration strategy for schema changes | COMPLETE | `docs/01_core/HOSTED_PLAY_MIGRATION_STRATEGY.md` exists with migration file convention, environment policies, and checklist | 2026-03-25 | brws-author-a | Created migration strategy doc covering repo-owned migration scripts under `web/migrations/`, SQLite reset for dev, Postgres snapshot policy, and per-migration checklist. |
| Step 4: Update rules/deployment/proving document targets | COMPLETE | `docs/01_core/HOSTED_PLAY_RULES.md` has expansion sections (§11-§16); deployment and proving references are consistent | 2026-03-25 | brws-author-a | Extended HOSTED_PLAY_RULES.md with §11 Model Serving, §12 Moon Bids, §13 Loner Bids, §14 Hand-End Pause, §15 Invite-Code Access, §16 Hand Sorting. |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-0-01 | `0_execution_foundation/sub/2026-03-24_proving-contract-and-browser-testing.md` | completed | -- |

## Blockers

None remaining. Phase 0 is complete.

## Session Log

### 2026-03-24 -- Codex
- Completed: Step 0.
- In progress: Step 1 via `SP-0-01`.
- Next: lock the proving contract, browser automation approach, and migration strategy before Phase 1 execution starts.

### 2026-03-25 -- brws-author-a
- Completed: Steps 1-4 in a single PR.
- Created `docs/01_core/HOSTED_PLAY_PROVING_CHECKLIST.md` (Step 1).
- Created `tests/e2e/hosted_play/` scaffold with `e2e` marker (Step 2).
- Created `docs/01_core/HOSTED_PLAY_MIGRATION_STRATEGY.md` (Step 3).
- Extended `docs/01_core/HOSTED_PLAY_RULES.md` with expansion sections §11-§16 (Step 4).
- Phase 0 is now COMPLETE. Phase 1 can begin.
