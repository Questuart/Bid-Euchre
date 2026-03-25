# Validation and Launch Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `4_validation_and_launch`
**Last updated:** 2026-03-24 by Codex

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phases 2 and 3 complete | PENDING | Product-experience and access-control checkpoints are complete | -- | -- | Final validation waits on the actual browser surface and auth flow. |
| Step 1: Add repo-owned browser E2E suite | PENDING | `uv run python -m pytest tests/e2e/hosted_play -q` passes on at least the happy-path match flow | -- | -- | `SP-4-01` |
| Step 2: Add Claude-direct browser testing config/runbook | PENDING | project-scoped MCP/browser-testing docs exist and a Claude-driven local browser smoke can be executed | -- | -- | `SP-4-01` |
| Step 3: Upgrade smoke scripts and full regression commands | PENDING | local/Docker/Postgres/browser smoke commands are documented and pass on the expanded product | -- | -- | `SP-4-01` |
| Step 4: Execute full automated proving matrix | PENDING | unit + integration + E2E + smoke suite all pass together with no known launch-blocking gap | -- | -- | `SP-4-01` |
| Step 5: Execute minimal required user proving | PENDING | iPhone Safari smoke, production authorization, and any final invite-redemption proving are recorded | -- | -- | `SP-4-01` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-4-01 | `4_validation_and_launch/sub/2026-03-24_browser-automation-smoke-and-proving.md` | proposed | Steps 1-5 |

## Blockers

- [ ] Phases 2 and 3 not complete.

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and proving-gate structure.
- Next: once the expanded product surface is stable, execute `SP-4-01` and keep human proving to the smallest viable set.
