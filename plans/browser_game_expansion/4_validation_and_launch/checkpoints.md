# Validation and Launch Checkpoints

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Phase/Rung:** `4_validation_and_launch`
**Last updated:** 2026-03-25 by analyst (note Phase 2 gap dependency on validation)

---

## Step Progress

| Step | Status | Validates | Date | Agent/Session | Notes |
|------|--------|-----------|------|---------------|-------|
| Step 0: Verify Phases 2 and 3 complete | COMPLETE | Product-experience and access-control checkpoints are complete | 2026-03-25 | overnight fleet | Phases 2 and 3 confirmed complete. |
| Step 1: Add repo-owned browser E2E suite | COMPLETE | `uv run python -m pytest tests/e2e/hosted_play -q` passes on at least the happy-path match flow | 2026-03-25 | brws-author-c | PR #1821 merged. Playwright smoke suite with 7 tests. `SP-4-01` |
| Step 2: Add Claude-direct browser testing config/runbook | COMPLETE | project-scoped MCP/browser-testing docs exist and a Claude-driven local browser smoke can be executed | 2026-03-25 | brws-author-c | Included in PR #1821. `SP-4-01` |
| Step 3: Upgrade smoke scripts and full regression commands | COMPLETE | local/Docker/Postgres/browser smoke commands are documented and pass on the expanded product | 2026-03-25 | brws-author-d | PR #1822 merged. Pilot launch hardening: rate limiting, error pages, session cleanup, enhanced health. `SP-4-01` |
| Step 4: Execute full automated proving matrix | IN_PROGRESS | unit + integration + E2E + smoke suite all pass together with no known launch-blocking gap | -- | -- | **2 of 7 Playwright tests failing on main** — `test_full_hand_verify_transition` (non-deterministic stall) and `test_mobile_viewport_tap_targets` (coarse-pointer emulation gap). Filed as #1827. `SP-4-01` |
| Step 5: Execute minimal required user proving | PENDING | iPhone Safari smoke, production authorization, and any final invite-redemption proving are recorded | -- | -- | Requires operator. `SP-4-01` |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-4-01 | `4_validation_and_launch/sub/2026-03-24_browser-automation-smoke-and-proving.md` | in_progress | Steps 4-5 |

## Blockers

- [ ] **Phase 2 is NOT complete** — see BGE-3 amendment. Phase 2 launch-blocking gaps (#1842, #1841, #1838, #1839, #1844, #1846) must ship before Phase 4 validation is meaningful.
- [ ] 2 of 7 Playwright tests failing (#1827) — blocks Step 4 completion. Some failures may be caused by Phase 2 gaps (features under test don't exist).
- [ ] User proving (Step 5) requires operator at device.

## Session Log

### 2026-03-24 -- Codex
- Completed: checkpoint scaffold and proving-gate structure.
- Next: once the expanded product surface is stable, execute `SP-4-01` and keep human proving to the smallest viable set.

### 2026-03-25 -- overnight fleet (reconciled by analyst)
- Completed: Steps 0-3. PR #1821 (Playwright smoke suite), PR #1822 (pilot hardening).
- In progress: Step 4 — 2 of 7 Playwright tests failing on main (#1827).
- Pending: Step 5 — requires operator for iPhone Safari smoke and invite-code proving.
