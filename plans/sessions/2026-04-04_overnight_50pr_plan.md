# Overnight 50-PR Fleet Run Plan — 2026-04-04

**Date:** 2026-04-04
**Goal:** Achieve ~50 merged PRs overnight by running 16 lanes across 6 waves over ~8 hours.
**Prior art:** `plans/sessions/2026-04-04_overnight_dispatch_plan.md` (8-11 PR plan, Wave 1 mostly cleared).
**Tracker issue:** _to be filed_

---

## 1. Fleet Layout (16 Lanes)

| Lane | Pool | Specialization | Warm? |
|------|------|---------------|-------|
| brws-author-a | Browser | `web/`, templates, CSS, JS | Yes |
| brws-author-b | Browser | `web/`, templates, CSS, JS | Yes |
| brws-author-c | Browser | `web/`, templates, CSS, JS | Yes |
| brws-author-d | Browser | `web/`, templates, CSS, JS | Yes |
| author-a | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| author-b | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| author-c | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| author-d | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| flex-a | Flex | Any domain (assigned per wave) | Yes |
| flex-b | Flex | Any domain (assigned per wave) | Yes |
| flex-c | Flex | Any domain (assigned per wave) | Yes |
| flex-d | Flex | Any domain (assigned per wave) | Yes |
| steward-analyst | Analyst | Shaping, research (no PRs) | Yes |
| steward-analyst-b | Analyst | Shaping, research (no PRs) | Yes |
| steward-review | Review | Autonomous review loop | Yes |
| steward-ops | Ops | Monitoring, alerts | Yes |

**Active PR-producing lanes: 12** (4 browser + 4 platform + 4 flex).
**Support lanes: 4** (2 analyst + review + ops).

## 2. Issue Triage Table

### 2a. Pre-Dispatch Actions

| # | Action | Notes |
|---|--------|-------|
| 2310 | **Close** — already fixed by PR #2327 | Merged 2026-04-04, issue still OPEN |

### 2b. Currently In-Flight (7 issues — do NOT dispatch)

| # | Title | Lane | Status |
|---|-------|------|--------|
| 2328 | Hide contract/trump during auction | brws lane | In progress |
| 2329 | Clubs/spades black fill | brws lane | In progress |
| 2330 | AI card delay + Next after human plays | brws lane | In progress |
| 2331 | Move auction log below hand | brws lane | In progress |
| 2303 | render_admin create_tables on prod | brws lane | In progress |
| 2312 | Review lane HWM subprocess | author lane | In progress |
| 2313 | Tiered issue closure + DISABLE_MOUSE | author lane | In progress |

**Expected PRs from in-flight: 7** (count toward total).

### 2c. Ready to Dispatch (10 existing issues)

| # | Title | Type | Est. | Lane Pool |
|---|-------|------|------|-----------|
| 2311 | Regenerate .test_durations + shard timeout | CI fix | 45 min | author |
| 2254 | dontAsk permission mode | Ops | 30 min | author |
| 2304 | Narrow Bash auto-accept patterns | Process | 30 min | author |
| 2309 | Tests for skip_to_next_decision | Follow-up test | 30 min | browser/flex |
| 2305 | Tests for onboarding migration | Follow-up test | 30 min | browser/flex |
| 2332 | Hide Skip button from UI | Web fix | 15 min | browser/flex |
| 2324 | Convention follow-up PR #2322 | Convention | 20 min | any |
| 2333 | Auto-start fleet-check cron | Ops feat | 30 min | author |
| 2334 | CPU-aware gate before make check | Ops feat | 60 min | author |
| 2238 | Review lane permission stalls | Ops bug | 45 min | author |

**Note:** #2254 and #2304 both touch `.claude/settings.json` — **combine into one task** for a single lane. #2238 is partially mitigated by #2254 (dontAsk mode).

**Expected PRs from dispatch: 9** (10 issues → 9 PRs due to combining #2254+#2304).

### 2d. Needs Shaping / Research (not dispatched directly)

| # | Title | Category | Disposition |
|---|-------|----------|-------------|
| 2300 | Glutton suit preservation bias | Research | Analyst posts findings as issue comment |
| 2149 | AI overbids calibration | Research | Deferred — needs experiment design |
| 1917 | Glutton strategy revamp | Research | Deferred — large initiative |
| 2220 | Render free-tier restart | Infra | Analyst investigation, no PR |
| 2198 | Playtesting skill | Feature | Too large for overnight; file sub-issues |
| 2185 | AI suggested plays | Feature | Deferred |
| 2188 | Ingest browser comments | Feature | Deferred |
| 2131 | Enable Codex to play game | Feature | Deferred |
| 2136 | Claude post test comment | Playwright | Deferred |
| 2085 | Automated 50-game run | Blocked by #2198 | Deferred |
| 2112 | Playwright too slow | Perf | Deferred |
| 2306 | Harden issue close | Process | Partially covered by #2313 |
| 2249 | Claude Code features audit | Research | Already analyzed (#2254 is the result) |
| 2320 | Manual proving checklist | Human task | Not code work — excluded |

## 3. New Issues to File (34 issues)

These fill the pipeline to reach ~50 PRs. Each is a concrete, bounded task.

### 3a. Browser Game — Forum Feature (Phase AC, SP-AC-02) [4 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-1 | feat(web): forum data model, migration, and CRUD backend | `web/models/forum.py`, `web/db.py`, migration script | 90 min | None (Phase 3 complete) |
| NEW-2 | feat(web): forum route and UI tab with invite-only gating | `web/routes.py`, `web/templates/forum/` | 90 min | NEW-1 |
| NEW-3 | feat(web): Claude bot constraints — match and forum rate limits | `web/middleware.py`, `web/routes.py` | 60 min | NEW-2 |
| NEW-4 | test(web): integration tests for forum + Claude constraints | `tests/unit/hosted_play/test_forum.py`, `tests/integration/` | 60 min | NEW-2 |

### 3b. Browser Game — GBT Evaluation (Phase 5) [2 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-5 | feat(web): wire gbt_av model behind config flag (Phase 5 Step 1) | `web/ai_manager.py`, `web/config.py` | 60 min | None |
| NEW-6 | test(web): measure GBT preload and runtime impact (Phase 5 Step 2) | `tests/unit/hosted_play/test_ai_manager.py`, benchmark script | 60 min | NEW-5 |

### 3c. Browser Game — UI Polish [5 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-7 | feat(web): add trick history panel showing all tricks played | `web/templates/partials/trick_history.html`, `web/routes.py` | 60 min | None |
| NEW-8 | feat(web): add match summary stats on match-end screen | `web/templates/partials/match_result.html`, CSS | 45 min | None |
| NEW-9 | feat(web): add keyboard shortcuts for card play (number keys) | `web/static/game.js` | 45 min | None |
| NEW-10 | fix(web): improve card hover/select visual feedback | `web/static/style.css`, `web/static/game.js` | 30 min | None |
| NEW-11 | feat(web): add bid history tooltip showing all bids made | `web/templates/partials/bid_panel.html`, JS | 30 min | None |

### 3d. Web Test Coverage [3 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-12 | test(web): add unit tests for middleware.py (rate limiting, error handling) | `tests/unit/hosted_play/test_middleware.py` | 45 min | None |
| NEW-13 | test(web): add unit tests for template_filters.py | `tests/unit/hosted_play/test_template_filters.py` | 30 min | None |
| NEW-14 | test(web): add E2E smoke tests for new auction-phase UI changes | `tests/e2e/hosted_play/test_auction_ui.py` | 60 min | #2328 merged |

### 3e. Ops Improvements [6 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-15 | ops: add review loop health check command | `scripts/internal/review_health.py` | 45 min | None |
| NEW-16 | docs(ops): document hook dependency graph | `.claude/hooks/README.md` | 30 min | None |
| NEW-17 | ops: add fleet startup validation script | `scripts/internal/fleet_preflight.py` | 45 min | None |
| NEW-18 | ops: add worktree health check for fleet boot | `scripts/internal/worktree_health.py` | 30 min | None |
| NEW-19 | ops: consolidate duplicate alert-inject hooks | `.claude/hooks/alert-inject.*` | 30 min | None |
| NEW-20 | ops: add lane activity summary to fleet-check output | `src/bid_euchre/ops/dashboard.py` | 45 min | None |

### 3f. Documentation [5 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-21 | docs: update ARCHITECTURE.md for web/ and ops/ growth | `docs/01_core/ARCHITECTURE.md` | 45 min | None |
| NEW-22 | docs: update DEPLOYMENT.md for invite codes and current Render config | `docs/01_core/DEPLOYMENT.md` | 30 min | None |
| NEW-23 | docs: add ops module README with API overview | `src/bid_euchre/ops/README.md` | 30 min | None |
| NEW-24 | docs: add PR analytics summary for March-April 2026 | `docs/04_reports/pr_analytics_2026_04.md` | 30 min | None |
| NEW-25 | docs: session audit 2026-04-04 overnight run | `plans/sessions/2026-04-04_overnight_run_audit.md` | 30 min | Run completes |

### 3g. CI/DX [4 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-26 | ci: add CI status badge to project README | `README.md` | 15 min | None |
| NEW-27 | ci: add automated .test_durations refresh workflow | `.github/workflows/test-durations.yml` | 45 min | #2311 merged |
| NEW-28 | fix(ci): add ruff version pin to prevent surprise updates | `pyproject.toml`, CI config | 20 min | None |
| NEW-29 | chore: update PR template with new validation commands | `.github/pull_request_template.md` | 20 min | None |

### 3h. Convention Follow-ups (anticipated from review) [3 issues]

| New # | Title | Scope | Est. | Depends On |
|-------|-------|-------|------|------------|
| NEW-30 | fix: convention follow-ups from overnight review batch 1 | Various (as review coordinator finds) | 30 min | Wave 1-2 PRs reviewed |
| NEW-31 | fix: convention follow-ups from overnight review batch 2 | Various | 30 min | Wave 3-4 PRs reviewed |
| NEW-32 | fix: convention follow-ups from overnight review batch 3 | Various | 30 min | Wave 5 PRs reviewed |

### 3i. Research Outputs (analyst comment, no PR) [2 tasks]

| Task | Title | Output | Lane |
|------|-------|--------|------|
| R-1 | Glutton choose_card() discard analysis (#2300) | Issue comment with trace findings | analyst |
| R-2 | Render free-tier restart options (#2220) | Issue comment with mitigation recs | analyst-b |

## 4. Wave Plan

### Timing Model

- **PR cycle time:** 45-90 min (implementation + make check + review + merge)
- **CPU gate:** Max 3 concurrent `make check` runs (#2334, deployed Wave 1)
- **Review throughput:** Review lane handles ~2-3 PRs concurrently, ~4/hour
- **Target merge rate:** 6-7 PRs/hour across all lanes

### Wave 1 — Clear Backlog + CPU Gate (T+0, all 12 PR lanes)

In-flight work continues. New dispatches fill remaining lanes.

| Lane | Issue(s) | Branch | File Scope | Validation | Est. |
|------|----------|--------|------------|------------|------|
| brws-author-a | #2328 | (in-flight) | templates | — | — |
| brws-author-b | #2329 | (in-flight) | CSS | — | — |
| brws-author-c | #2330 | (in-flight) | JS, routes | — | — |
| brws-author-d | #2331 | (in-flight) | templates | ��� | — |
| author-a | #2311 | `fix/ci-test-durations` | `.test_durations`, `.github/` | CI: shards <10 min | 45m |
| author-b | #2254+#2304 | `ops/dontask-and-patterns` | `.claude/settings.json` | No permission stalls | 45m |
| author-c | #2334 | `ops/cpu-aware-gate` | `Makefile`, scripts | `make check-gated` waits on load | 60m |
| author-d | #2333 | `ops/fleet-check-autostart` | `.claude/settings.json`, hooks | Fleet-check auto-starts | 30m |
| flex-a | #2332 | `fix/hide-skip-button` | `web/templates/` | Skip button not visible | 15m |
| flex-b | #2309 | `fix/test-skip-to-next` | `tests/unit/hosted_play/` | pytest passes | 30m |
| flex-c | #2305 | `fix/test-onboarding` | `tests/unit/hosted_play/` | pytest passes | 30m |
| flex-d | #2324 | `fix/convention-2322` | `plans/sessions/` | make check passes | 20m |

**In-flight:** #2303, #2312, #2313 on remaining active lanes.
**Expected Wave 1 output:** ~16 PRs (7 in-flight + 9 new dispatches).
**Wall clock:** ~60 min.

### Wave 2 — Browser Polish + Ops (T+1h, freed lanes)

Lanes completing Wave 1 pick up new issues. Browser lanes pivot to UI polish. Platform lanes start ops improvements.

| Lane | Issue | Branch | File Scope | Validation | Est. |
|------|-------|--------|------------|------------|------|
| brws-author-a | NEW-7 | `feat/trick-history-panel` | templates, routes | Visual: trick history visible | 60m |
| brws-author-b | NEW-8 | `feat/match-summary-stats` | templates, CSS | Match end shows stats | 45m |
| brws-author-c | NEW-10 | `fix/card-hover-feedback` | CSS, JS | Cards highlight on hover/select | 30m |
| brws-author-d | NEW-11 | `feat/bid-history-tooltip` | templates, JS | Bid history accessible | 30m |
| author-a | NEW-15 | `ops/review-health-check` | scripts/internal | Health check runs clean | 45m |
| author-b | #2238 | `fix/review-permission-stalls` | `.claude/settings.json`, ops | Review lane no stalls | 45m |
| author-c | NEW-17 | `ops/fleet-preflight` | scripts/internal | Preflight passes | 45m |
| author-d | NEW-16 | `docs/hook-dependency-graph` | `.claude/hooks/README.md` | README exists with diagram | 30m |
| flex-a | NEW-12 | `test/web-middleware` | tests/unit/hosted_play | pytest passes | 45m |
| flex-b | NEW-13 | `test/web-template-filters` | tests/unit/hosted_play | pytest passes | 30m |
| flex-c | NEW-26 | `ci/readme-badge` | `README.md` | Badge renders on GitHub | 15m |
| flex-d | NEW-29 | `chore/pr-template-update` | `.github/` | Template has new sections | 20m |

**Expected Wave 2 output:** ~12 PRs.
**Cumulative:** ~28 PRs.
**Wall clock:** T+1h to T+2h.

### Wave 3 — Forum Feature + GBT + Docs (T+2h, freed lanes)

Larger features begin. Forum work serializes (NEW-1 before NEW-2). GBT evaluation starts.

| Lane | Issue | Branch | File Scope | Validation | Est. |
|------|-------|--------|------------|------------|------|
| brws-author-a | NEW-1 | `feat/forum-backend` | web/models, web/db | Forum DB tests pass | 90m |
| brws-author-b | NEW-5 | `feat/gbt-config-wiring` | web/ai_manager, web/config | GBT loads behind flag | 60m |
| brws-author-c | NEW-9 | `feat/keyboard-shortcuts` | web/static/game.js | Keys 1-10 play cards | 45m |
| brws-author-d | NEW-14 | `test/auction-e2e-smoke` | tests/e2e/hosted_play | E2E tests pass | 60m |
| author-a | NEW-18 | `ops/worktree-health` | scripts/internal | Health check passes | 30m |
| author-b | NEW-19 | `ops/consolidate-alert-hooks` | .claude/hooks | Consolidated, make check passes | 30m |
| author-c | NEW-21 | `docs/architecture-update` | docs/01_core | Docs reflect current state | 45m |
| author-d | NEW-20 | `ops/lane-activity-summary` | ops/dashboard.py | Summary appears in output | 45m |
| flex-a | NEW-22 | `docs/deployment-update` | docs/01_core | Docs current | 30m |
| flex-b | NEW-23 | `docs/ops-module-readme` | src/bid_euchre/ops | README exists | 30m |
| flex-c | NEW-28 | `fix/ruff-version-pin` | pyproject.toml | Ruff pinned, CI passes | 20m |
| flex-d | NEW-24 | `docs/pr-analytics` | docs/04_reports | Report committed | 30m |

**Expected Wave 3 output:** ~12 PRs.
**Cumulative:** ~40 PRs.
**Wall clock:** T+2h to T+3.5h.

### Wave 4 — Forum Completion + Tests + CI (T+3.5h, freed lanes)

Forum routes build on Wave 3 backend. Convention follow-ups arrive from review.

| Lane | Issue | Branch | File Scope | Validation | Est. |
|------|-------|--------|------------|------------|------|
| brws-author-a | NEW-2 | `feat/forum-routes-ui` | web/routes, web/templates/forum | Forum tab works | 90m |
| brws-author-b | NEW-6 | `test/gbt-performance` | tests, benchmark script | Measurements committed | 60m |
| brws-author-c | NEW-4 | `test/forum-integration` | tests/unit, tests/integration | Forum tests pass | 60m |
| brws-author-d | NEW-30 | `fix/convention-batch-1` | Various (review findings) | make check passes | 30m |
| author-a | NEW-27 | `ci/test-durations-auto` | .github/workflows | Workflow triggers | 45m |
| author-b | NEW-31 | `fix/convention-batch-2` | Various (review findings) | make check passes | 30m |
| author-c | (available — stretch goal or follow-up) | | | | |
| author-d | (available — stretch goal or follow-up) | | | | |
| flex-a | (available) | | | | |
| flex-b | (available) | | | | |
| flex-c | (available) | | | | |
| flex-d | (available) | | | | |

**Expected Wave 4 output:** ~6-8 PRs.
**Cumulative:** ~46-48 PRs.
**Wall clock:** T+3.5h to T+5h.

### Wave 5 — Stretch Goals + Cleanup (T+5h, freed lanes)

Final wave. Claude bot constraints, remaining convention fixes, session audit.

| Lane | Issue | Branch | File Scope | Validation | Est. |
|------|-------|--------|------------|------------|------|
| brws-author-a | NEW-3 | `feat/claude-bot-constraints` | web/middleware, web/routes | Rate limits enforced | 60m |
| brws-author-b | NEW-32 | `fix/convention-batch-3` | Various | make check passes | 30m |
| author-a | NEW-25 | `docs/overnight-audit` | plans/sessions | Audit committed | 30m |
| (other lanes) | (available for any remaining follow-ups, bug fixes from review, or early #2300 shaping) | | | |

**Expected Wave 5 output:** ~3-5 PRs.
**Cumulative:** ~50-53 PRs.
**Wall clock:** T+5h to T+7h.

### Wave 6 — Overflow/Recovery (T+7h+, if needed)

Any lanes still running pick up:
- Review coordinator follow-up issues
- Any failed CI reruns
- Stalled lane recovery

## 5. Dependency Graph

```
Wave 1 (independent, parallel)
├── #2311 (CI durations)
├── #2254+#2304 (dontAsk) ──→ #2238 depends on this (Wave 2)
├── #2334 (CPU gate) ──→ enables safer concurrent make check
├── #2333 (fleet-check auto)
├── #2332 (hide Skip)
├── #2309 (tests)
├── #2305 (tests)
├── #2324 (convention)
└── 7× in-flight (continue)

Wave 2 (independent, parallel)
├── NEW-7..11 (browser polish, independent)
├── NEW-12,13 (test coverage, independent)
├── NEW-15..17 (ops, independent)
├── NEW-26,29 (CI/DX, independent)
└── #2238 (depends: #2254 merged)

Wave 3
├── NEW-1 (forum backend) ──→ serializes: NEW-2 (Wave 4) ──→ NEW-3 (Wave 5)
├── NEW-5 (GBT wiring) ──→ NEW-6 (Wave 4)
├── NEW-9,14 (browser, independent)
├── NEW-18..24 (ops/docs, independent)
└── NEW-28 (CI, independent)

Wave 4
├── NEW-2 (forum UI) depends: NEW-1
├── NEW-4 (forum tests) depends: NEW-2
├── NEW-6 (GBT test) depends: NEW-5
├── NEW-27 (CI auto) depends: #2311
└── NEW-30,31 (convention) depends: review findings from Waves 1-3

Wave 5
├── NEW-3 (bot constraints) depends: NEW-2
├── NEW-32 (convention) depends: review findings from Wave 4
└── NEW-25 (audit) depends: run completion
```

**Critical serialization chains:**
1. Forum: NEW-1 → NEW-2 → NEW-3 (must be same browser lane or sequential)
2. GBT: NEW-5 → NEW-6 (same lane preferred)
3. Convention follow-ups: appear as review runs (reactive, not pre-planned)

## 6. File Ownership & Safe Parallelism

### Conflict-Prone Files

| File | Lanes That Touch It | Mitigation |
|------|---------------------|-----------|
| `.claude/settings.json` | author-b (#2254+#2304), author-d (#2333), #2238 | Combine #2254+#2304. Serialize #2333 after. #2238 after dontAsk merges. |
| `web/routes.py` | forum (NEW-1,2), several browser fixes | Forum work in Wave 3-4 after browser fixes merge in Wave 1-2. |
| `web/static/game.js` | #2330, NEW-9, NEW-10 | #2330 in-flight now. NEW-9 and NEW-10 in different waves. |
| `web/templates/` (partials) | Multiple browser PRs | Template partials are modular — low conflict risk if targeting different files. |
| `web/db.py` | NEW-1 (forum), #2303 (render_admin) | #2303 in-flight now, will merge before NEW-1 starts. |
| `Makefile` | #2334 (CPU gate) | Single owner in Wave 1. |

### Safe Parallel Groups

**Group A (all independent, any order):**
- #2311, #2332, #2309, #2305, #2324, #2333 (different files)
- NEW-7 through NEW-13 (different test/template files)
- NEW-15 through NEW-24 (different script/doc files)

**Group B (must serialize):**
- #2254+#2304 → #2238 (same file: settings.json)
- NEW-1 → NEW-2 → NEW-3 → NEW-4 (forum chain)
- NEW-5 → NEW-6 (GBT chain)

## 7. PR Budget Summary

| Source | PRs | Confidence |
|--------|-----|-----------|
| In-flight issues (Wave 1) | 7 | High (already started) |
| Existing backlog dispatch | 9 | High (well-scoped) |
| New browser UI polish | 5 | High (small, bounded) |
| New test coverage | 5 | High (well-scoped) |
| New ops improvements | 6 | Medium (some may need iteration) |
| New docs | 5 | High (bounded scope) |
| New CI/DX | 4 | Medium-High |
| Forum feature (Phase AC) | 4 | Medium (larger scope) |
| GBT evaluation (Phase 5) | 2 | Medium |
| Convention follow-ups | 3 | Medium (reactive) |
| **Total** | **50** | |

### Confidence Tiers

- **High confidence (36 PRs):** In-flight + backlog + UI polish + tests + docs
- **Medium confidence (14 PRs):** Ops improvements + forum + GBT + convention

### Fallback Targets

| Scenario | Expected PRs | Notes |
|----------|-------------|-------|
| Everything goes well | 50-53 | All waves complete |
| Normal friction (80%) | 40-45 | Some Wave 4-5 tasks slip |
| Heavy friction (60%) | 30-35 | Forum chain incomplete, some ops slip |
| Minimum viable run | 25-28 | Waves 1-2 only + in-flight |

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CPU overload from concurrent make check | High | Delays all PRs | #2334 (CPU gate) dispatched first; use make check-gated |
| Forum feature takes longer than estimated | Medium | 2-4 PRs slip | Assign to strongest browser lane; budget extra time |
| Review lane stalls block merges | Medium | Delays cascade | #2254 (dontAsk) fixes root cause; manual override backup |
| Merge conflicts on shared files | Medium | 30-60 min delay per | File ownership table + wave sequencing prevents most |
| Lane context exhaustion (>15 min tasks) | Low | Silent lane death | Monitor via fleet-check; keep tasks < 90 min |
| CI flake or shard hang | Low-Medium | 20-30 min per incident | #2311 fixes durations; timeout safety net from #2321 |
| Make check validation takes too long | Medium | Throughput drops | CPU gate limits concurrent runs; stagger validation |

## 9. Monitoring Plan

| Check | Frequency | Tool | Action on Failure |
|-------|-----------|------|-------------------|
| Lane health | Every 8 min | `/fleet-check` cron | Nudge stalled lane or reassign |
| CPU load | Continuous | CPU gate (once deployed) | Queue `make check` runs |
| PR merge rate | Every 30 min | `gh pr list --state merged` | If < 4/hour, investigate bottleneck |
| Review loop | Every 10 min | `/check-reviews` cron | Manual review override if stuck |
| CI status | Per PR | `gh pr checks` | Rerun on flake; investigate on persistent fail |

## 10. Pre-Dispatch Checklist

- [ ] Close #2310 (already fixed by PR #2327)
- [ ] Verify 7 in-flight lanes are progressing (not stalled)
- [ ] File all NEW-1 through NEW-32 issues on GitHub
- [ ] Verify main is green: `gh run list --branch main --limit 1`
- [ ] Fetch latest main in all worktrees
- [ ] Deploy CPU gate (#2334) and dontAsk (#2254+#2304) early in Wave 1
- [ ] Start fleet-check cron: `/loop 8m /fleet-check`
- [ ] Start review cron: `/loop 10m /check-reviews`
- [ ] Dispatch Wave 1 tasks via task queue

## 11. New Issue Filing Guide

### Issues to File Immediately (before dispatch)

Priority order (file these first — they're needed for Wave 2+):

1. **NEW-7:** `feat(web): add trick history panel showing all tricks played`
2. **NEW-8:** `feat(web): add match summary stats on match-end screen`
3. **NEW-9:** `feat(web): add keyboard shortcuts for card play (number keys)`
4. **NEW-10:** `fix(web): improve card hover/select visual feedback`
5. **NEW-11:** `feat(web): add bid history tooltip showing all bids made`
6. **NEW-12:** `test(web): add unit tests for middleware.py`
7. **NEW-13:** `test(web): add unit tests for template_filters.py`
8. **NEW-14:** `test(web): add E2E smoke tests for auction-phase UI changes`
9. **NEW-15:** `ops: add review loop health check command`
10. **NEW-16:** `docs(ops): document hook dependency graph`
11. **NEW-17:** `ops: add fleet startup validation script`
12. **NEW-18:** `ops: add worktree health check for fleet boot`
13. **NEW-19:** `ops: consolidate duplicate alert-inject hooks`
14. **NEW-20:** `ops: add lane activity summary to fleet-check output`
15. **NEW-21:** `docs: update ARCHITECTURE.md for web/ and ops/ growth`
16. **NEW-22:** `docs: update DEPLOYMENT.md for invite codes and Render config`
17. **NEW-23:** `docs: add ops module README with API overview`
18. **NEW-24:** `docs: add PR analytics summary for March-April 2026`
19. **NEW-26:** `ci: add CI status badge to project README`
20. **NEW-27:** `ci: add automated .test_durations refresh workflow`
21. **NEW-28:** `fix(ci): add ruff version pin to prevent surprise updates`
22. **NEW-29:** `chore: update PR template with new validation commands`

### Issues to File When Needed (Wave 3+)

23. **NEW-1:** `feat(web): forum data model, migration, and CRUD backend (SP-AC-02)`
24. **NEW-2:** `feat(web): forum route and UI tab with invite-only gating (SP-AC-02)`
25. **NEW-3:** `feat(web): Claude bot constraints — match and forum rate limits (SP-AC-02)`
26. **NEW-4:** `test(web): integration tests for forum + Claude constraints`
27. **NEW-5:** `feat(web): wire gbt_av model behind config flag (Phase 5)`
28. **NEW-6:** `test(web): measure GBT preload and runtime impact (Phase 5)`

### Convention Follow-ups (filed reactively)

29. **NEW-30:** Convention batch 1 (after Wave 1-2 review)
30. **NEW-31:** Convention batch 2 (after Wave 3-4 review)
31. **NEW-32:** Convention batch 3 (after Wave 5 review)

### Session Audit (filed at end)

32. **NEW-25:** `docs: session audit 2026-04-04 overnight run`

## Outcome

<!-- Filled after the run -->
- PRs opened:
- PRs merged:
- Issues closed:
- Issues filed:
- Wall clock:
- Peak merge rate:
- Notable incidents:
