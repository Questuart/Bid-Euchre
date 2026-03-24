# Deployment and Launch Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `5_deployment_launch`
**Last updated:** 2026-03-24

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Verify Phases 3 and 4 are complete | COMPLETE | 2026-03-24 | brws-author-a | Phase 3 COMPLETE (PRs #1475, #1489, #1495, #1498, #1501). Phase 4 COMPLETE (PRs #1529, #1533, #1535, #1538, #1545). |
| Step 1: Write Dockerfile | COMPLETE | 2026-03-24 | brws-author-d, brws-author-a | Dockerfile (PR #1638) + .dockerignore (PR #1627). |
| Step 2: Write deployment config | COMPLETE | 2026-03-24 | brws-author-a, flex-a | render.yaml (PR #1636) + health/readiness endpoints (PR #1634). |
| Step 3: Configure environment variables | COMPLETE | 2026-03-24 | brws-author-c, brws-author-a | Production config contract (PR #1625) + .env.example (PR #1629). |
| Step 4: Test local Docker build | PENDING | -- | -- | `docker build -t bideuchre-web .` + `docker run` + play one hand. |
| Step 5: Deploy to hosting service | PENDING | -- | -- | Deploy, verify persistent storage, create first private link. |
| Step 6: Smoke validation | PENDING | -- | -- | Create match → play one full hand → verify decision rows in DB → verify JSONL export. |
| Step 7: Share first private link | PENDING | -- | -- | Generate UUID link, share with friends. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-5-01 | `5_deployment_launch/sub/2026-03-24_deployment-and-launch.md` | active | Steps 1-7 |

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
