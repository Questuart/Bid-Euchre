# Execution Foundation Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `0_execution_foundation`
**Last updated:** 2026-03-24 by Codex

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Register expansion initiative package | COMPLETE | `find plans/browser_game_expansion -maxdepth 2 -type f | wc -l` returns `>= 5` | 2026-03-24 | Codex | Governing plan, roadmap, proving matrix, registry, and checkpoints created. |
| Step 1: Lock proving checklist and validation tiers | IN_PROGRESS | `rg -n "HOSTED_PLAY_PROVING_CHECKLIST|Proving Matrix|tests/e2e/hosted_play" plans/browser_game_expansion docs/01_core` returns `>= 1` planned target per item | 2026-03-24 | Codex | Driven by `SP-0-01`. |
| Step 2: Lock repo-owned browser automation stack | PENDING | `.mcp.json` or equivalent project-scoped MCP config path is chosen and documented; E2E test path chosen | -- | -- | Claude-direct browser testing must be part of the repo plan, not a one-off local hack. |
| Step 3: Lock migration strategy for schema changes | PENDING | `rg -n "migration" plans/browser_game_expansion/governing_plan.md` returns `>= 1` and the chosen migration path names real file locations | -- | -- | Required before invite-code and hand-schema changes. |
| Step 4: Update rules/deployment/proving document targets | PENDING | Governing plan references concrete doc targets under `docs/01_core/` for hosted-play rules and proving | -- | -- | Prevents docs drift once implementation starts. |

**Status values:** `PENDING`, `IN_PROGRESS`, `COMPLETE`, `BLOCKED`, `SKIPPED`

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-0-01 | `0_execution_foundation/sub/2026-03-24_proving-contract-and-browser-testing.md` | in_progress | Step 1 |

## Blockers

- [ ] No repo-owned browser automation stack is committed yet.
- [ ] Hosted-play proving checklist doc does not exist yet under `docs/01_core/`.

## Session Log

### 2026-03-24 -- Codex
- Completed: Step 0.
- In progress: Step 1 via `SP-0-01`.
- Next: lock the proving contract, browser automation approach, and migration strategy before Phase 1 execution starts.
