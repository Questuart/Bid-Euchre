# Overnight Fleet Run Plan — 2026-04-04 (Rescoped)

**Date:** 2026-04-04
**Goal:** Maximize merged PRs overnight using ONLY existing open GitHub issues. Flex lanes play the browser game continuously for proving and research.
**Prior art:** Original 50-PR plan (PR #2336) rejected — invented 32 new issues. This rescope uses open backlog only.
**Tracker issue:** #2337

---

## 1. Fleet Layout (16 Lanes)

| Lane | Pool | Role | Warm? |
|------|------|------|-------|
| brws-author-a | Browser | `web/`, templates, CSS, JS | Yes |
| brws-author-b | Browser | `web/`, templates, CSS, JS | Yes |
| brws-author-c | Browser | `web/`, templates, CSS, JS | Yes |
| brws-author-d | Browser | `web/`, templates, CSS, JS | Yes |
| author-a | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| author-b | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| author-c | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| author-d | Platform | `src/bid_euchre/ops/`, CI, `.claude/` | Yes |
| flex-a | Flex | Browser game — hybrid mode | Yes |
| flex-b | Flex | Browser game — HTTP mode | Yes |
| flex-c | Flex | Browser game — Playwright mode | Yes |
| flex-d | Flex | Browser game — HTTP try-hard mode | Yes |
| steward-analyst | Analyst | Research (#2300) | Yes |
| steward-analyst-b | Analyst | Research (#2220) | Yes |
| steward-review | Review | Autonomous review loop | Yes |
| steward-ops | Ops | Monitoring, alerts | Yes |

**Active PR-producing lanes: 8** (4 browser + 4 platform).
**Playtesting lanes: 4** (flex pool — continuous browser game play).
**Support lanes: 4** (2 analyst + review + ops).

## 2. Issue Triage Table

### 2a. Already Merged (REMOVED from plan)

| # | PR | Merged |
|---|-----|--------|
| 2310 | #2327 | 2026-04-04 04:36 |
| 2311 | #2325 | 2026-04-04 04:21 |
| 2254+2304 | #2268 | Prior session |
| 2329 | #2335 | 2026-04-04 05:02 |
| 2313 | #2339 | 2026-04-04 05:16 |

### 2b. Currently In-Flight (6 issues — do NOT re-dispatch)

| # | Title | Lane | Status |
|---|-------|------|--------|
| 2328 | Hide contract/trump during auction | brws-author-a | In progress |
| 2332 | Hide Skip button from UI | brws-author-b | In progress |
| 2331 | Move auction log below hand | brws-author-c | In progress |
| 2303 | render_admin create_tables on prod | brws-author-d | In progress |
| 2312 | Review lane HWM subprocess | author-c | In progress |
| — | Fleet-check cron update | author-a | In progress |

**Expected PRs from in-flight: 6** (count toward total).

### 2c. Ready to Dispatch (12 existing issues)

| # | Title | Type | Est. | Lane Pool | PRs |
|---|-------|------|------|-----------|-----|
| 2334 | CPU-aware gate before make check | Ops feat | 60 min | platform | 1 |
| 2333 | Auto-start fleet-check cron | Ops feat | 30 min | platform | 1 |
| 2330 | AI card delay + Next after human plays | Web fix | 60 min | browser | 1 |
| 2324 | Convention follow-up PR #2322 | Convention | 20 min | any | 1 |
| 2238 | Review lane permission stalls | Ops bug | 45 min | platform | 1 |
| 2309 | Tests for skip_to_next_decision | Test | 30 min | any | 1 |
| 2305 | Tests for onboarding migration | Test | 30 min | any | 1 |
| 2306 | Harden issue close workflow | Ops feat | 45 min | platform | 1 |
| 2338 | Away-mode skill + Telegram push | Ops feat | 60 min | platform | 1 |
| 2249 | Claude Code features audit | Ops/docs | 45 min | platform | 1 |
| 2136 | Claude post test comment to board | Web test | 30 min | browser | 1 |
| 2188 | Ingest browser game comments | Ops feat | 60 min | platform | 1 |

**Expected PRs from direct dispatch: 12.**

### 2d. Multi-PR Decomposition (3 existing issues → 6 PRs)

| # | Title | PR Slice | Est. | Depends On |
|---|-------|----------|------|------------|
| 2198 | Playtesting skill | PR-1: `/play-game` skill foundation | 90 min | None |
| 2198 | Playtesting skill | PR-2: `/playtest` QA loop skill | 60 min | PR-1 |
| 2198 | Playtesting skill | PR-3: `/researcher` competitive play skill | 60 min | PR-1 |
| 2085 | Automated 50-game proving run | PR: 50-game config + runner | 60 min | #2198 PR-1 |
| 2112 | Playwright proving too slow | PR-1: profiling + quick wins | 60 min | None |
| 2112 | Playwright proving too slow | PR-2: optimization (if time) | 60 min | PR-1 |

**Expected PRs from multi-PR issues: 5-6.**

### 2e. Research / Analyst (no PR — issue comments)

| # | Title | Lane | Output |
|---|-------|------|--------|
| 2300 | Glutton suit preservation bias | analyst-a | Issue comment with trace findings |
| 2220 | Render free-tier restart options | analyst-b | Issue comment with mitigation recs |

### 2f. Deferred (not dispatched overnight)

| # | Title | Reason |
|---|-------|--------|
| 2185 | AI suggested plays | Too large — needs design |
| 2149 | AI overbids calibration | Research initiative — needs experiment design |
| 1917 | Glutton strategy revamp | Large research initiative |
| 2131 | Enable Codex to play | Large — overlaps with #2198, dispatch if lanes idle |
| 2320 | Manual proving checklist | Human task, not code work |
| 2337 | Overnight plan dispatch issue | Meta tracking issue |

## 3. Flex Lane Playtesting (Continuous)

All 4 flex lanes play the browser game on Render production for the entire run.
See analyst-b findings on #2198 for detailed prompts and API reference.

### Mode Assignments

| Lane | Mode | Nickname | Speed | Primary Value |
|------|------|----------|-------|--------------|
| flex-a | Hybrid | Claude-HYB2 | ~5 min/match | Visual + logic verification |
| flex-b | HTTP-only | Claude-HTTP2 | ~30 sec/match | Volume, scoring, API edge cases |
| flex-c | Playwright | Claude-PW2 | ~20 min/match | Visual regressions, a11y |
| flex-d | HTTP try-hard | Claude-TRYHARD | ~1 min/match | Strategic play quality |

### Dispatch Prompts (inject via tmux)

**flex-a — Hybrid mode:**
> Play the Bid Euchre browser game at https://bideuchre-web.onrender.com using a hybrid approach. Enter invite code [CODE], set nickname "Claude-HYB2", select Bud Bot. For each game: use Playwright MCP to navigate to the game page, then use JavaScript fetch() for fast gameplay (always pass on bids, play first legal card via card_index=0). Take Playwright snapshots at: hand results, match results, leaderboard. After each match, click "Play Again". Log bugs to plans/sessions/ and file GitHub issues for P0/P1 bugs. Play 10+ matches. Target: ~5 min/match.

**flex-b — HTTP-only mode:**
> Play the Bid Euchre browser game at https://bideuchre-web.onrender.com using direct HTTP calls only (no browser). Use curl or fetch to: POST /enter-code with code=[CODE], POST nickname "Claude-HTTP2", POST select-ai model_id=bud_bot. Then loop: GET /play/{uuid} to read state, parse HTML for turn_number and phase, POST /bid (always pass: bid_n=0), POST /play-card (card_index=0 for first legal card), POST /next to advance reveals. Track scores per hand. Play 50+ matches. Log anomalies to plans/sessions/. File GitHub issues for any bugs. Target: ~30 sec/match.

**flex-c — Playwright-only mode:**
> Play the Bid Euchre browser game at https://bideuchre-web.onrender.com using Playwright MCP browser automation only. Enter invite code [CODE], set nickname "Claude-PW2", select Bud Bot. Navigate the game by reading accessibility snapshots, clicking buttons, and observing visual state. Always pass on bids, play the first available card button. Take screenshots at hand results and match results. Log every UI inconsistency, accessibility issue, or rendering bug. Play 5+ matches (this mode is slow). File GitHub issues for all findings. Target: ~20 min/match.

**flex-d — HTTP try-hard mode:**
> Play the Bid Euchre browser game at https://bideuchre-web.onrender.com using direct HTTP calls, but play strategically. Enter invite code [CODE], set nickname "Claude-TRYHARD", select Bud Bot. Bidding strategy: evaluate your hand (count trump, aces, bowers) and bid aggressively when strong (5+ trump = bid 5-6 in that suit; 3+ aces with no clear trump = bid 3+ High). Play strategy: lead aces and bowers first, follow suit with highest card, trump when void. Parse the HTML game board to understand your cards, the current trick, and what's been played. Goal: win matches and achieve a positive EPPD on the leaderboard. Play 30+ matches. Log strategy observations to plans/sessions/. Target: ~1 min/match.

### Playtesting Pre-Flight

1. Create 4 invite codes (one per lane) via `render_admin.py`
2. Verify Render is healthy: `curl -s https://bideuchre-web.onrender.com/health`
3. Inject prompts into flex-a through flex-d via tmux (two-step: text then Enter)
4. Monitor via `capture-pane` every 15 min

## 4. Wave Plan

### Timing Model

- **PR cycle time:** 45-90 min (implementation + make check + review + merge)
- **CPU gate:** Max 3 concurrent `make check` runs (once #2334 deploys)
- **Review throughput:** Review lane handles ~2-3 PRs concurrently, ~4/hour
- **Target merge rate:** 3-4 PRs/hour across 8 lanes

### Wave 1 — Clear In-Flight + Fill Available Lanes (T+0)

In-flight work continues. Free lanes get high-priority dispatches.

| Lane | Issue(s) | Status | File Scope | Est. |
|------|----------|--------|------------|------|
| brws-author-a | #2328 | In-flight | templates | — |
| brws-author-b | #2332 | In-flight | templates | — |
| brws-author-c | #2331 | In-flight | templates | — |
| brws-author-d | #2303 | In-flight | web/db, render_admin | — |
| author-a | fleet-check | In-flight | `.claude/`, hooks | — |
| author-b | **#2334** | **New dispatch** | `Makefile`, scripts | 60m |
| author-c | #2312 | In-flight | ops, review scripts | — |
| author-d | **#2333** | **New dispatch** | `.claude/settings.json`, hooks | 30m |

**Expected Wave 1 output:** 8 PRs (6 in-flight + 2 new).
**Wall clock:** ~60 min.

### Wave 2 — Backlog Clear (T+1h, as lanes free up)

Lanes completing Wave 1 pick up next issues. Priority: quick wins first, unblock dependencies.

| Priority | Issue | Lane Pool | File Scope | Validation | Est. |
|----------|-------|-----------|------------|------------|------|
| 1 | #2330 | browser | JS, routes, templates | AI delay visible, Next required | 60m |
| 2 | #2324 | any | plans/sessions/ | make check passes | 20m |
| 3 | #2238 | platform | `.claude/settings.json`, ops | Review lane no stalls | 45m |
| 4 | #2309 | any | tests/unit/hosted_play/ | pytest passes | 30m |
| 5 | #2305 | any | tests/unit/hosted_play/ | pytest passes | 30m |
| 6 | #2306 | platform | ops, hooks | Proving check enforced | 45m |

**Note:** #2238 depends on dontAsk mode (PR #2268, already merged). Safe to dispatch.
**Note:** #2238 and #2333 both touch `.claude/settings.json` — serialize: #2333 first (Wave 1), then #2238 (Wave 2).

**Expected Wave 2 output:** ~6 PRs.
**Cumulative:** ~14 PRs.
**Wall clock:** T+1h to T+2h.

### Wave 3 — Ops & Skills (T+2h, freed lanes)

Larger ops features and test work. #2198 PR-1 starts here to unblock Wave 4 items.

| Priority | Issue | Lane Pool | File Scope | Validation | Est. |
|----------|-------|-----------|------------|------------|------|
| 1 | #2198 PR-1 | platform | `.claude/skills/play-game/` | Skill invocable | 90m |
| 2 | #2338 | platform | `.claude/skills/away-mode/`, ops | Skill invocable | 60m |
| 3 | #2249 | platform | docs, ops | Audit report committed | 45m |
| 4 | #2136 | browser | Playwright, web | Comment posted on board | 30m |
| 5 | #2188 | platform | ops, scripts | Comments ingested | 60m |
| 6 | #2112 PR-1 | browser/platform | scripts, Playwright config | Profile committed, quick wins | 60m |

**Expected Wave 3 output:** ~5-6 PRs.
**Cumulative:** ~19-20 PRs.
**Wall clock:** T+2h to T+3.5h.

### Wave 4 — Skill Chain + Proving (T+3.5h, freed lanes)

Complete the playtesting skill chain. Lanes not in the chain take follow-up work.

| Priority | Issue | Lane Pool | File Scope | Depends On | Est. |
|----------|-------|-----------|------------|------------|------|
| 1 | #2198 PR-2 | platform | `.claude/skills/playtest/` | #2198 PR-1 merged | 60m |
| 2 | #2198 PR-3 | platform | `.claude/skills/researcher/` | #2198 PR-1 merged | 60m |
| 3 | #2085 | browser | config, scripts | #2198 PR-1 merged | 60m |
| 4 | (follow-ups) | any | Various (from review findings) | Review findings exist | 30m |

**Expected Wave 4 output:** ~3-4 PRs.
**Cumulative:** ~22-24 PRs.
**Wall clock:** T+3.5h to T+5h.

### Wave 5 — Stretch + Overflow (T+5h+)

Any lanes still running pick up remaining dispatchable work or bug fixes from playtesting lanes.

| Issue | Notes |
|-------|-------|
| #2131 | Enable Codex to play — only if lanes are idle and #2198 PR-1 merged |
| #2112 PR-2 | Playwright optimization — only if PR-1 findings warrant it |
| Bug fixes | From flex lane playtesting — filed as issues during the run |
| Convention fixes | From review coordinator findings |

**Expected Wave 5 output:** 2-4 PRs.
**Cumulative:** ~25-28 PRs.
**Wall clock:** T+5h to T+8h.

### Wave 6 — Recovery (T+8h+, if needed)

- Retry any failed CI runs
- Recover stalled lanes
- Merge any PRs stuck in review

## 5. Dependency Graph

```
Wave 1 (independent, parallel)
├── #2328, #2332, #2331, #2303, fleet-check, #2312 (in-flight, continue)
├── #2334 (CPU gate) ──→ enables safer concurrent make check
└── #2333 (fleet-check auto) ──→ touches `.claude/settings.json`

Wave 2 (independent, parallel — fill freed lanes)
├── #2330 (AI delay + Next)
├── #2324 (convention follow-up)
├── #2238 (review lane stalls) — depends: #2333 merged (shared file)
├── #2309 (tests)
├── #2305 (tests)
└── #2306 (harden issue close)

Wave 3
├── #2198 PR-1 (play-game skill) ──→ serializes: PR-2 (Wave 4), PR-3 (Wave 4)
├── #2338 (away-mode skill, independent)
├── #2249 (features audit, independent)
├── #2136 (Claude post comment, independent)
├── #2188 (ingest comments, independent)
└── #2112 PR-1 (Playwright profiling, independent)

Wave 4
├── #2198 PR-2 (playtest skill) ← depends: #2198 PR-1
├── #2198 PR-3 (researcher skill) ← depends: #2198 PR-1
├── #2085 (50-game run) ← depends: #2198 PR-1
└── Review follow-ups (reactive)

Wave 5
├── #2131 (Codex play) ← depends: #2198 PR-1 (optional)
├── #2112 PR-2 (Playwright optimization, optional)
└── Bug fixes from flex lane playtesting (reactive)
```

**Critical serialization chains:**
1. `.claude/settings.json`: #2333 (Wave 1) → #2238 (Wave 2) — same file
2. Playtesting skill: #2198 PR-1 → PR-2 + PR-3 + #2085 (all depend on foundation)
3. Playwright: #2112 PR-1 → PR-2 (profiling before optimization)

## 6. File Ownership & Safe Parallelism

### Conflict-Prone Files

| File | Lanes That Touch It | Mitigation |
|------|---------------------|-----------|
| `.claude/settings.json` | #2333 (Wave 1), #2238 (Wave 2) | Serialize: #2333 first |
| `web/routes.py` | #2330, #2136 | Different waves; low overlap |
| `web/static/game.js` | #2330 | Single owner |
| `web/templates/` (partials) | #2328, #2332, #2331, #2330 | Modular partials — different files |
| `web/db.py` | #2303 | Single owner in Wave 1 |
| `Makefile` | #2334 | Single owner in Wave 1 |
| `.claude/skills/` | #2198 (x3), #2338 | Different skill directories — no conflict |

### Safe Parallel Groups

**Group A (all independent, any order):**
- #2334, #2324, #2309, #2305, #2306 (different files)
- #2338, #2249, #2136, #2188 (different files)

**Group B (must serialize):**
- #2333 → #2238 (same file: `.claude/settings.json`)
- #2198 PR-1 → PR-2, PR-3, #2085 (skill chain)
- #2112 PR-1 → PR-2 (profiling before optimization)

## 7. PR Budget Summary

| Source | PRs | Confidence |
|--------|-----|-----------|
| In-flight issues (Wave 1) | 6 | High (already started) |
| New dispatch Wave 1 | 2 | High (well-scoped) |
| Backlog dispatch (Wave 2) | 6 | High (small, bounded) |
| Ops & skills (Wave 3) | 5-6 | Medium-High |
| Skill chain + proving (Wave 4) | 3-4 | Medium (depends on PR-1 landing) |
| Stretch + overflow (Wave 5) | 2-4 | Low-Medium |
| **Total** | **25-28** | |

### Confidence Tiers

- **High confidence (14 PRs):** In-flight + backlog clear (Waves 1-2)
- **Medium confidence (8-10 PRs):** Ops features + skill chain (Waves 3-4)
- **Low confidence (2-4 PRs):** Stretch goals + reactive follow-ups (Wave 5)

### Fallback Targets

| Scenario | Expected PRs | Notes |
|----------|-------------|-------|
| Everything goes well | 28-30 | All waves complete, flex lanes file extra bugs |
| Normal friction (80%) | 22-25 | Some Wave 4-5 tasks slip |
| Heavy friction (60%) | 16-20 | Skill chain incomplete |
| Minimum viable run | 14 | Waves 1-2 only |

### Why Not 50?

The original plan reached 50 by inventing 32 new issues. With only existing open issues:
- **18 dispatchable issues** yield ~23 PRs (including multi-PR splits)
- **6 in-flight** items add 6 PRs
- **Total ceiling: ~29 PRs** from existing backlog
- Additional PRs come only from reactive work (review follow-ups, playtest bug reports)

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| CPU overload from concurrent make check | High | Delays all PRs | #2334 (CPU gate) dispatched first; use `make check-gated` |
| Render cold-start stalls playtesting | Medium | Flex lanes blocked | 4 concurrent lanes keep server warm; fallback to localhost |
| #2198 skill chain takes longer than est. | Medium | 3-4 PRs slip to later | Start PR-1 early (Wave 3); PR-2/3 can be next-session |
| Review lane stalls block merges | Medium | Cascade delays | #2238 fixes root cause; manual override backup |
| Merge conflicts on `.claude/settings.json` | Medium | 30-60 min delay | Strict serialization: #2333 → #2238 |
| Lane context exhaustion (>15 min tasks) | Low | Silent lane death | Keep tasks < 90 min; monitor via fleet-check |
| Playwright mode too slow for flex-c | High | Low game count | Accept 5 matches; value is UX bugs not volume |
| HTML parsing breaks from recent UI PRs | Low-Medium | HTTP/hybrid modes stall | Test parsing first hand; fix inline |

## 9. Monitoring Plan

| Check | Frequency | Tool | Action on Failure |
|-------|-----------|------|-------------------|
| Lane health (PR lanes) | Every 8 min | `/fleet-check` cron | Nudge stalled lane or reassign |
| Flex lane health | Every 15 min | `capture-pane` batch | Restart prompt if stalled |
| CPU load | Continuous | CPU gate (once #2334 deploys) | Queue `make check` runs |
| PR merge rate | Every 30 min | `gh pr list --state merged` | If < 2/hour, investigate |
| Review loop | Every 10 min | `/check-reviews` cron | Manual override if stuck |
| Render health | Every 30 min | `curl .../health` | Switch flex lanes to localhost |
| CI status | Per PR | `gh pr checks` | Rerun on flake |

## 10. Pre-Dispatch Checklist

- [ ] Close issues already fixed: #2310, #2311, #2329, #2313 (PRs merged but issues open)
- [ ] Verify 6 in-flight lanes are progressing (not stalled)
- [ ] Verify main is green: `gh run list --branch main --limit 1`
- [ ] Create 4 invite codes for flex lane playtesting
- [ ] Verify Render health: `curl -s https://bideuchre-web.onrender.com/health`
- [ ] Fetch latest main in all worktrees
- [ ] Start fleet-check cron: `/loop 8m /fleet-check`
- [ ] Start review cron: `/loop 10m /check-reviews`
- [ ] Dispatch Wave 1 new tasks: #2334 → author-b, #2333 → author-d
- [ ] Dispatch flex lane playtesting prompts
- [ ] Dispatch analyst tasks: #2300 → analyst-a, #2220 → analyst-b

## Outcome

<!-- Filled after the run -->
- PRs opened:
- PRs merged:
- Issues closed:
- Games played (flex lanes):
- Wall clock:
- Peak merge rate:
- Notable incidents:
