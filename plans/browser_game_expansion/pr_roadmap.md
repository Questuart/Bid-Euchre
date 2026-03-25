# PR Roadmap -- Browser Game Expansion and Pilot Readiness

**Governing plan:** `plans/browser_game_expansion/governing_plan.md`
**Last updated:** 2026-03-25 by analyst (reconcile shipped vs unshipped after user proving)

---

## Purpose

This roadmap sequences the browser-game expansion into coherent PR-sized
deliverables that an orchestrator can dispatch across browser lanes without
losing the dependency chain.

## PR Sequence

| PR | Theme | Primary Phase | Depends On | Status | Scope |
|----|-------|---------------|------------|--------|-------|
| PR-1 | Proving foundation and validation contract | Phase 0 | None | **SHIPPED** (PR #1787) | Lock proving checklist, browser automation direction, migration policy, and launch gate docs. |
| PR-2 | OLSa roster migration | Phase 1 | PR-1 | **SHIPPED** (PR #1798) | Replace `hybrid_olsa` browser wiring with `full_ols_av`, update config/env contract, improve display naming. |
| PR-3 | Moon/loner hosted-play core | Phase 1 | PR-2 | **SHIPPED** (PR #1804) | Add moon/loner legality, overcall tracking, exchange, loner sit-out flow, persistence schema changes, and core tests. |
| PR-4 | Moon/loner browser UI and pacing | Phase 2 | PR-3 | **PARTIAL** (PR #1809) | See gap analysis below. |
| PR-5 | Mobile, accessibility, and telemetry | Phase 2 | PR-4 | **PARTIAL** (PR #1818) | See gap analysis below. |
| PR-6 | Invite codes and nickname flow | Phase 3 | PR-3 | **SHIPPED** (PR #1800) | Add invite-code data model, entry/session flow, code generator/admin workflow, and player-chosen nickname. |
| PR-7 | Browser automation and smoke suite | Phase 4 | PR-5 + PR-6 | **SHIPPED** (PR #1821) | Add browser E2E tests, Claude-direct browser testing config, upgraded smoke scripts, and proving checklist execution harness. Note: 2 of 7 tests failing (#1827). |
| PR-8 | Pilot launch hardening | Phase 4 | PR-7 | **SHIPPED** (PR #1822) | Final launch gating docs, deploy-time checks, iPhone Safari proving protocol, and pilot operator runbook updates. |
| PR-9 | Optional GBT evaluation | Phase 5 | PR-3 | PENDING | Measure `gbt_av`, optionally wire it behind config, and decide whether to expose it after the stable pilot path exists. |
| PR-AC1 | Leaderboard and analytics | Phase AC | PR-6 | PENDING | Add invite-only leaderboard ranked by net_eppd with product-facing metrics. Route-backed tab in shared invited-user shell. |
| PR-AC2 | Feedback forum and Claude bot constraints | Phase AC | PR-AC1 | PENDING | Add invite-only forum (read/create/hide-unhide), Claude bot rate limits and labeling, shared shell navigation. |

## PR-4 Gap Analysis (PARTIAL — PR #1809)

**Shipped:**
- Moon/loner bid UI (badges, gold/purple colors, emoji icons)
- AI response pacing delays (300ms-2s per bid type)
- Animated scoring banner templates (code exists in `hand_result.html`)
- 14 new template unit tests

**NOT shipped (in original PR-4 scope):**
- Persistent last-trick display (#1844)
- Action rail / event feed (#1845)
- Dealer/declarer/turn markers (#1846)
- Hand-end pause + next-deal route (engine auto-advances, #1842)

**Broken (templates exist but never render):**
- Hand result screen (moon/loner banners, animated scoring) — engine auto-advances past it (#1842)
- Match completion screen — game ends silently (#1841)
- Moon/loner labels show trick count (10) instead of point values (20/40) (#1838)
- Moon card exchange happens silently, no player visibility (#1839)

## PR-5 Gap Analysis (PARTIAL — PR #1818)

**Shipped:**
- Responsive CSS breakpoints (375px / 414px)
- ARIA labels and accessibility landmarks (26 new test assertions)
- 44px touch targets (WCAG 2.5.5)
- Keyboard focus rings (:focus-visible)
- Reduced-motion CSS coverage
- Skip navigation link and forced-colors support

**NOT shipped (in original PR-5 scope):**
- Touch-safe tap-select/confirm for card play (#1847)
- Pace controls UI (#1848)
- Help drawer / rules surface (#1849)

**Already working (not a gap):**
- `decision_time_ms` persistence — client injection + server persistence fully wired

## Follow-Up PR Sequence

The unshipped items require new PRs. Recommended sequence:

| PR | Theme | Issues | Blocker? | Depends On |
|----|-------|--------|----------|------------|
| PR-4b | Engine hand-end pause + match completion | #1842, #1841 | **YES** | None — root cause fix |
| PR-4c | Moon exchange visibility + label fix | #1839, #1838 | **YES** | PR-4b |
| PR-4d | Last-trick display + seat markers | #1844, #1846 | **YES** | PR-4b |
| PR-4e | Action rail | #1845 | No | PR-4b |
| PR-5b | Tap-select/confirm for card play | #1847 | No | PR-4b |
| PR-5c | Pace controls + help drawer | #1848, #1849 | No | PR-4b |

## Parallelism Guidance

- `PR-4b` is the **critical path** — all other follow-ups depend on the engine auto-advance fix.
- `PR-4c` and `PR-4d` can run in parallel after `PR-4b`.
- `PR-4e`, `PR-5b`, `PR-5c` can run in parallel after `PR-4b`.
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
| PR-4b | Engine stops at hand complete phase, `hand_result.html` renders, match_result renders at +-52 |
| PR-4c | Exchange details visible in UI, labels show (20)/(40) |
| PR-4d | Last trick visible after win, dealer/turn/declarer markers present |
| PR-5 | Mobile viewport E2E, reduced-motion and touch-flow checks |
| PR-5b | Tap-select then confirm required for card play on touch devices |
| PR-6 | Access-code route/integration tests plus admin CLI smoke |
| PR-7 | Full hosted-play unit/integration/E2E matrix, Claude-direct browser smoke, Docker/Postgres smoke |
| PR-8 | Final pre-pilot checklist, real-device proving evidence, deployment/runbook validation |
| PR-9 | Artifact preload/runtime measurements, browser smoke, explicit promote/defer decision |
| PR-AC1 | Leaderboard unit/route/integration tests, access gating, ranking by net_eppd, column partitioning |
| PR-AC2 | Forum unit/route/integration tests, Claude bot constraint enforcement, rate limiting, automated labeling, browser E2E |

## Launch Blockers

**Original:** `PR-1` through `PR-8`.

**Updated:** `PR-1` through `PR-8` **plus** `PR-4b`, `PR-4c`, `PR-4d`.

`PR-4e`, `PR-5b`, `PR-5c`, `PR-9`, `PR-AC1`, and `PR-AC2` are not launch blockers.
