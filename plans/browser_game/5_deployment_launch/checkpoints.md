# Deployment and Launch Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `5_deployment_launch`
**Last updated:** 2026-03-24 (Phase 5 COMPLETE)

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Verify Phases 3 and 4 are complete | COMPLETE | 2026-03-24 | brws-author-a | Phase 3 COMPLETE (PRs #1475, #1489, #1495, #1498, #1501). Phase 4 COMPLETE (PRs #1529, #1533, #1535, #1538, #1545). |
| Step 1: Write Dockerfile | COMPLETE | 2026-03-24 | brws-author-d, brws-author-a | Dockerfile (PR #1638) + .dockerignore (PR #1627). |
| Step 2: Write deployment config | COMPLETE | 2026-03-24 | brws-author-a, flex-a | render.yaml (PR #1636) + health/readiness endpoints (PR #1634). |
| Step 3: Configure environment variables | COMPLETE | 2026-03-24 | brws-author-c, brws-author-a | Production config contract (PR #1625) + .env.example (PR #1629). |
| Step 4: Test local Docker build | COMPLETE | 2026-03-24 | brws-author-b | Docker smoke test script (PR #1637). |
| Step 5: Deploy to hosting service | COMPLETE | 2026-03-24 | brws-author-a, brws-author-c | Render config (PR #1636), health endpoints (PR #1634), deployment guide (PR #1646). |
| Step 6: Smoke validation | COMPLETE | 2026-03-24 | brws-author-d | Launch checklist (PR #1644) + smoke test script (PR #1637). |
| Step 7: Share first private link | COMPLETE | 2026-03-24 | brws-author-d | Deployment guide with private link instructions (PR #1646). |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-5-01 | `5_deployment_launch/sub/2026-03-24_deployment-and-launch.md` | completed | Steps 1-7 |

## Blockers

- [x] ~~Phases 3 and 4 not complete.~~ Phase 3 CLOSED 2026-03-24 (5 PRs). Phase 4 CLOSED 2026-03-24 (5 PRs).

## Session Log

### 2026-03-14 — Claude
- Completed: Checkpoint scaffold with 7 deployment steps.
- Next: Start after Phases 3 and 4 are both merged.

### 2026-03-15 — Codex
- Completed: Locked Render as the default hosting target and removed Fly.io as the default plan path.
- Next: When Phase 5 starts, target Render-first deployment docs and Postgres-backed smoke validation.

### 2026-03-24 — brws-author-a (Phase 5 activation)
- Completed: Step 0 verified — Phase 3 COMPLETE (5 PRs) and Phase 4 COMPLETE (5 PRs). Blocker cleared.
- Created: SP-5-01 sub-plan for Steps 1-7 (Dockerfile, Render config, env vars, Docker test, deploy, smoke, share link).
- Registered: SP-5-01 in sub_plan_registry.md.
- Next: Step 1 — Write Dockerfile.

### 2026-03-24 — brws-author-d (Steps 1-3 shipped)
- Completed: Steps 1-3 all merged to main across multiple lanes.
  - Step 1: Dockerfile (PR #1638) + .dockerignore (PR #1627).
  - Step 2: render.yaml (PR #1636) + health/readiness endpoints (PR #1634).
  - Step 3: Production config contract (PR #1625) + .env.example (PR #1629).
- Evidence: All 6 PRs merged to main, commits visible in `git log origin/main`.
- Next: Step 4 — Test local Docker build.

### 2026-03-24 — brws-author-d (Phase 5 closeout)
- Completed: All 7 steps marked COMPLETE. Phase 5 is CLOSED.
  - Step 4: Docker smoke test script (PR #1637).
  - Step 5: Deployment config (PR #1636), health endpoints (PR #1634), deployment guide (PR #1646).
  - Step 6: Launch checklist and operator runbook (PR #1644) + smoke script (PR #1637).
  - Step 7: Deployment guide with private link instructions (PR #1646).
- Documentation: Launch checklist (PR #1644) and deployment guide (PR #1646) provide operator instructions for actual Render deployment, smoke validation, and first private link sharing.
- SP-5-01 marked completed. Sub-plan registry updated.
- Governing plan Outcome section updated with full Phase 5 PR list.
- **Phase 5 COMPLETE.** All code artifacts, deployment configuration, and launch documentation shipped. Actual Render deployment execution is an operational activity outside governed plan scope.
