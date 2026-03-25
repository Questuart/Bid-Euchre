# PR Roadmap -- Browser Game Expansion and Pilot Readiness

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-24

---

## Purpose

This roadmap sequences the browser-game expansion into coherent PR-sized
deliverables that an orchestrator can dispatch across browser lanes without
losing the dependency chain.

## PR Sequence

| PR | Theme | Primary Phase | Depends On | Scope |
|----|-------|---------------|------------|-------|
| PR-1 | Proving foundation and validation contract | Phase 0 | None | Lock proving checklist, browser automation direction, migration policy, and launch gate docs. |
| PR-2 | OLSa roster migration | Phase 1 | PR-1 | Replace `hybrid_olsa` browser wiring with `full_ols_av`, update config/env contract, improve display naming. |
| PR-3 | Moon/loner hosted-play core | Phase 1 | PR-2 | Add moon/loner legality, overcall tracking, exchange, loner sit-out flow, persistence schema changes, and core tests. |
| PR-4 | Moon/loner browser UI and pacing | Phase 2 | PR-3 | Add moon/loner bid UI, last-trick display, action rail, winner/dealer/declarer markers, hand-end pause, and next-deal route. |
| PR-5 | Mobile, accessibility, and telemetry | Phase 2 | PR-4 | Touch-safe play, pace controls, reduced motion, help drawer, decision-time persistence, and narrow-screen layout. |
| PR-6 | Invite codes and nickname flow | Phase 3 | PR-3 | Add invite-code data model, entry/session flow, code generator/admin workflow, and player-chosen nickname. |
| PR-7 | Browser automation and smoke suite | Phase 4 | PR-5 + PR-6 | Add browser E2E tests, Claude-direct browser testing config, upgraded smoke scripts, and proving checklist execution harness. |
| PR-8 | Pilot launch hardening | Phase 4 | PR-7 | Final launch gating docs, deploy-time checks, iPhone Safari proving protocol, and pilot operator runbook updates. |
| PR-9 | Optional GBT evaluation | Phase 5 | PR-3 | Measure `gbt_av`, optionally wire it behind config, and decide whether to expose it after the stable pilot path exists. |
| PR-AC1 | Leaderboard and analytics | Phase AC | PR-6 | Add invite-only leaderboard ranked by net_eppd with product-facing metrics. Route-backed tab in shared invited-user shell. |
| PR-AC2 | Feedback forum and Claude bot constraints | Phase AC | PR-AC1 | Add invite-only forum (read/create/hide-unhide), Claude bot rate limits and labeling, shared shell navigation. |

## Parallelism Guidance

- `PR-2` and `PR-3` are serialized.
- `PR-4` and `PR-6` can run in parallel after `PR-3`.
- `PR-5` can start once `PR-4` has landed enough structure to test on mobile.
- `PR-7` waits on the stable browser surface from `PR-5` and the access flow
  from `PR-6`.
- `PR-9` is intentionally outside the launch blocker chain.
- `PR-AC1` starts after `PR-6` (invite codes) is stable. `PR-AC2` follows
  `PR-AC1`. Both are outside the launch blocker chain.

## Required Validation by PR

| PR | Required Validation |
|----|---------------------|
| PR-1 | Plan docs consistent, proving matrix written, smoke/runbook references updated |
| PR-2 | `tests/unit/hosted_play/test_ai_manager.py`, `test_config.py`, targeted model-loading smoke |
| PR-3 | `test_engine.py`, `test_db.py`, `test_routes.py`, replay/export regression, moon/loner seeded integration proof |
| PR-4 | Route/template tests plus local browser/E2E proof of moon/loner hand flow |
| PR-5 | Mobile viewport E2E, reduced-motion and touch-flow checks |
| PR-6 | Access-code route/integration tests plus admin CLI smoke |
| PR-7 | Full hosted-play unit/integration/E2E matrix, Claude-direct browser smoke, Docker/Postgres smoke |
| PR-8 | Final pre-pilot checklist, real-device proving evidence, deployment/runbook validation |
| PR-9 | Artifact preload/runtime measurements, browser smoke, explicit promote/defer decision |
| PR-AC1 | Leaderboard unit/route/integration tests, access gating, ranking by net_eppd, column partitioning |
| PR-AC2 | Forum unit/route/integration tests, Claude bot constraint enforcement, rate limiting, automated labeling, browser E2E |

## Launch Blockers

`PR-1` through `PR-8` are launch blockers for the expanded pilot scope.

`PR-9`, `PR-AC1`, and `PR-AC2` are not launch blockers.
