# Overnight Go-Live Finalization — Dispatch Plan (2026-04-05)

> **Purpose:** Shape and prioritize all open issues for an overnight autonomous
> fleet run to finalize the browser game for go-live.
>
> **Context:** Today's session merged 31 PRs and closed 18 issues. Two audit
> reports guide this plan:
> - `plans/sessions/2026-04-05_go_live_checklist.md` (86 items, covers Sections A-J)
> - A comprehensive Playwright E2E UX audit (45+ PASS, 5 flags)
>
> **Fleet capacity:** 4 brws-author lanes + 2 flex lanes for proving.
> Target: 12-16 PRs merged overnight.

---

## Issue Triage — Full Inventory (61 Open Issues)

### P0 — Go-Live Blockers (Must Fix Before Launch)

These bugs directly break core gameplay or cause user-visible state corruption.

| # | Title | Complexity | File Scope | Notes |
|---|-------|-----------|------------|-------|
| #2467 | Stale active match shadows completed match on refresh | small | `web/routes.py`, `web/cleanup.py` | Variant of #2446 — GET handler still prefers stale active match over completed one. PR #2453 fixed POST handler only. Fix: abandon ALL active matches in `/select-ai`, not just >2hr ones. |
| #2471 | Auction log not open by default during auction | small | `web/templates/partials/`, `web/static/game.js` | PR #2459 merged but may not be working on deploy. Needs investigation: template caching? JS override? Verify fix, then either close or write new fix. |
| #2440 | Card play hang — user stuck unable to advance | verify | — | Likely already fixed by PR #2414 (removed broken JS AI-delay guard). Needs **proving on Render**, not new code. If hang persists post-deploy, escalate to P0-fix. |
| #2442 | Gameplay latency between tricks | small | `web/routes.py` | PR #2399 added server-side `time.sleep()` delays. May be double-firing or compounding. Investigate delay logic, tune timing. |

### P0-Verify — Already Fixed, Need Proving

These have merged PRs but remain open (per tiered closure policy). Proving
closes them — no new code expected.

| # | Title | Fix PR | Proving Method |
|---|-------|--------|----------------|
| #2438 | Auction log closes too early | #2459 | Play a full auction, verify log stays open until Next |
| #2439 | Hand result doesn't clarify MADE IT/SET | #2450 | Complete a hand where declaring team is set, verify label |
| #2441 | Club/spade icons not black filled | #2452, #2419 | Visual check of all suit icon locations |
| #2446 | Match result screen skipped (stale match) | #2453 | Complete a match, verify match-result screen appears |
| #2454 | Remove help bar from gameplay | #2465 | Verify no help bar during gameplay |
| #2210 | Show final hand result before match-over | #2464 | Complete a match, verify last trick result shows first |
| #2455 | Dedication page in onboarding | #2461 | Fresh player flow, verify dedication page appears |

### P1 — Go-Live Important (Should Fix, Not Blocking)

User-facing quality issues that degrade experience but don't prevent play.

| # | Title | Complexity | File Scope | Notes |
|---|-------|-----------|------------|-------|
| #2466 | Remove icon/indicators section from help guide | trivial | `web/templates/partials/guide_content.html` | Delete the `{# ---- Icons & Indicators ---- #}` section. ~20 lines. |
| #2310 | Bid selector defaults to Pass instead of next bid | small | `web/routes.py`, `web/templates/partials/bid_panel.html`, `web/static/game.js` | **Routes.py overlap** — schedule in same wave as other routes changes or isolate to bid panel template/JS only. |
| #2386 | AI pacing feels instant and unnatural | medium | `web/routes.py`, `web/static/game.js` | PR #2399 shipped delay system. This may be a tuning issue (delay too short?) or the delays aren't reaching the client. Investigate before coding. |
| #2296 | Leaderboard drops inactive players | small | `web/leaderboard.py` | Query uses `min_hands=1` with no recency filter. Bug may be Render DB wipes (#2220) rather than code. Investigate DB state via `render_admin.py`. |
| #2346 | Player name styling (team colors, duplicates, card count) | small | `web/static/style.css`, `web/templates/partials/*.html` | CSS-only for colors. Template changes for duplicate removal. PR #2411 already removed orphaned CSS. |
| #2470 | Back button on onboarding intro/dedication flow | small | `web/templates/partials/onboarding_*.html`, `web/routes.py` | Minor routes.py change (back navigation handler). |
| #2303 | render_admin.py calls create_tables() on prod DB | small | `scripts/internal/render_admin.py` | Guard with `if not tables_exist()` or remove the call. No web/ overlap. |
| #2288 | UI polish round 4 — 8 refinements | verify | — | All 8 items addressed by prior PRs (#2314, #2315, #2316, #2319, #2399, #2419, #2465). Verify and close. |

### P2 — Post-Launch (Can Wait)

| # | Title | Category |
|---|-------|----------|
| #2468 | Log glutton counterfactual alongside human card plays | enhancement — data pipeline |
| #2469 | Log GBT bidding counterfactual alongside human bids | enhancement — data pipeline |
| #2131 | Enable Codex to play the browser game | enhancement — tooling |
| #2136 | Have Claude post a test comment to comments board | enhancement — testing |
| #2185 | AI suggested plays and bid recommendations | enhancement — feature |
| #2188 | Ingest browser game comments to flag issues | enhancement — ops |
| #2220 | Render free-tier spin-down restart failures | ops — infra (may be root cause of #2296) |
| #2333 | Auto-start fleet-check cron on orchestrator boot | ops — convenience |
| #2334 | CPU-aware gate before make check | ops — fleet efficiency |
| #2338 | Create /away-mode skill | ops — operator tooling |
| #2349 | Inbox messages not delivered when lane is idle | ops — messaging |
| #2403 | Create /session-end skill | ops — orchestration |
| #2404 | Enhance /away-mode with Telegram status loop | ops — operator tooling |
| #2415 | Reliable lane status introspection | ops — fleet visibility |
| #2085 | Automated 50-game Claude proving run | testing — automation |
| #2112 | Playwright proving agent too slow | testing — performance |
| #2320 | Manual proving checklist (Waves 3-5) | testing — verification |
| #2337 | Overnight 50-PR fleet run dispatch plan | ops — planning (superseded by this plan) |

### P2-Convention — Review Follow-up Issues

These are auto-generated by the review coordinator. Low priority, batch later.

| # | Title | Source PR |
|---|-------|----------|
| #2449 | Convention follow-up for PR #2448 | #2448 |
| #2457 | Convention follow-up for PR #2456 | #2456 |
| #2462 | Convention follow-up for PR #2458 | #2458 |
| #2463 | Convention follow-up for PR #2460 | #2460 |
| #2304 | Narrow broad Bash auto-accept patterns | #2268 |

### P3 — Research / Deferred

| # | Title | Category |
|---|-------|----------|
| #1917 | Glutton strategy revamp experiment design | research — strategy |
| #2149 | AI overbids when it doesn't need to | research — bidding |
| #2229 | Simulation vs browser game parity experiment | research — validation |
| #2290 | Deuce wastes Aces early / conserves 10s | research — play ordering |
| #2300 | Glutton suit preservation bias deep dive | research — strategy |
| #2389 | Glutton bid-context awareness evaluation | research — strategy |
| #2390 | Unify GBT bidding and glutton play strategies | research — architecture |
| #2391 | Validate glutton discard/lead simplification | research — strategy |
| #2198 | Create playtesting skill (already shipped #2401) | verify — close |
| #2238 | Review lane permission stalls (already fixed #2398) | verify — close |
| #2249 | Evaluate Claude Code auto-accept features | ops — research |
| #2254 | Switch to dontAsk permission mode | ops — research |
| #2271 | Duplicate make check processes | ops — needs-verification |
| #2301 | CI tests-shard stuck 55+ min | ops — CI reliability |
| #2306 | Harden issue close workflow | ops — process |
| #2313 | Tiered issue closure policy (shipped) | verify — close |
| #2351 | Comprehensive audit of closed issues | ops — research |
| #2384 | Design verification framework for issue lifecycle | ops — research |
| #2409 | Pattern of closing issues without verification | ops — process |

---

## Wave Structure

### Constraints

1. **`web/routes.py` is a 2,644-line hotspot.** Multiple issues touch it.
   Only ONE lane edits routes.py at a time. Other lanes work on
   template-only, CSS-only, or non-web files.
2. **CPU management:** Max 4-5 concurrent `make check-gated` runs.
3. **Proving gates:** After each wave's PRs merge, a flex lane runs targeted
   Playwright/HTTP proving before the next wave starts routes.py changes.

### Wave 1 — Critical Bugs (2 lanes, ~2h)

**Goal:** Fix the two P0 bugs that need new code. Start proving P0-Verify items.

| Lane | Issue | Branch | File Scope | Est. |
|------|-------|--------|------------|------|
| brws-author-a | #2467 (stale match shadows) | `fix/web-stale-match-shadow` | `web/routes.py`, `web/cleanup.py` | small |
| brws-author-b | #2471 (auction log default) | `fix/web-auction-log-default` | `web/templates/partials/`, `web/static/game.js` | small |
| flex-a | P0-Verify proving | — | — | Run go-live checklist items for #2438, #2439, #2441, #2446, #2454, #2210 on Render. Post evidence, close verified issues. |

**Scope notes:**
- **#2467** touches `web/routes.py` (game_page GET handler line ~1029, select_ai
  line ~1272) and `web/cleanup.py`. Fix: in `select_ai()`, before creating new
  match, abandon ALL active matches for the player (not just >2hr stale ones).
  Add test in `tests/unit/hosted_play/test_routes.py`.
- **#2471** should NOT touch `web/routes.py` — investigate template-only fix
  (ensure auction log starts expanded in template, verify no JS collapse on load).
  If routes.py change is needed, hold for Wave 1 merge of #2467 first.

**Wave 1 gate:** Both PRs pass CI + review. Flex lane confirms no regression
on match creation and auction flows.

### Wave 2 — Latency + Pacing (1 lane, ~2h)

**Goal:** Investigate and fix the gameplay latency/pacing complaints. These
are related issues sharing the same code path.

| Lane | Issue | Branch | File Scope | Est. |
|------|-------|--------|------------|------|
| brws-author-a | #2442 + #2386 (latency + pacing) | `fix/web-gameplay-pacing` | `web/routes.py` (delay logic), `web/static/game.js` | medium |
| brws-author-b | #2466 (remove icon section) | `fix/web-remove-guide-icons` | `web/templates/partials/guide_content.html` | trivial |
| brws-author-c | #2303 (render_admin create_tables) | `fix/render-admin-create-tables` | `scripts/internal/render_admin.py` | small |
| brws-author-d | #2346 (player name styling) | `fix/web-player-name-styling` | `web/static/style.css`, `web/templates/partials/*.html` | small |

**Scope notes:**
- **#2442 + #2386** are the same root cause. Investigate `web/routes.py` for
  `time.sleep()` calls in the trick-play handlers. Check if delays fire multiple
  times per trick. Target: AI delay of ~750ms before card appears, no stacking.
  This lane has exclusive routes.py access in Wave 2.
- **#2466** is a trivial template delete — no overlap with anything.
- **#2303** is a standalone script fix — no web overlap.
- **#2346** is CSS + templates — no routes.py or JS overlap.

**Wave 2 gate:** Pacing lane proves timing with manual playtest (3 tricks
minimum). Flex lane verifies no visual regressions from #2346 CSS changes.

### Wave 3 — UX Polish (2-3 lanes, ~2h)

**Goal:** Ship remaining P1 UX improvements.

| Lane | Issue | Branch | File Scope | Est. |
|------|-------|--------|------------|------|
| brws-author-a | #2310 (bid selector default) | `fix/web-bid-selector-default` | `web/routes.py` (bid panel context), `web/templates/partials/bid_panel.html`, `web/static/game.js` | small |
| brws-author-b | #2470 (back button onboarding) | `feat/web-onboarding-back-button` | `web/templates/partials/onboarding_*.html`, `web/routes.py` (back handler) | small |
| flex-a | Proving round 2 | — | Run checklist sections C1 (pacing), D6 (match end), E1-E4 (moon/loner/set). Post evidence. |

**Scope notes:**
- **#2310** touches routes.py (bid panel template context) and bid_panel.html.
  Must ensure the template receives the minimum legal bid value from the handler.
- **#2470** touches routes.py minimally (add back-navigation route). The two
  routes.py changes are in DIFFERENT handlers (bid panel vs onboarding), so
  parallel execution is **acceptable** if both lanes are careful with rebasing.
  However, if risk-averse, serialize #2470 after #2310.

**Wave 3 gate:** Bid selector defaults verified in auction. Back button works
in onboarding flow. Full match lifecycle proving passes.

### Wave 4 — Investigation + Cleanup (1-2 lanes, ~1h)

**Goal:** Investigate remaining open questions. Close verifiable issues.

| Lane | Task | Notes |
|------|------|-------|
| brws-author-a | #2296 (leaderboard investigation) | Use `render_admin.py` to query Render DB. Check if player data still exists. May be Render DB wipe (#2220) not a code bug. If code fix needed: `web/leaderboard.py`. |
| flex-a | Issue cleanup: close verified issues | Close #2288 (all items done), #2198 (skill shipped), #2238 (fix shipped), #2313 (policy shipped). Post evidence for each. |
| flex-b | Final proving pass | Run go-live checklist Section D (full lifecycle) end-to-end. Report results. |

---

## Lane Assignment Summary

| Lane | Wave 1 | Wave 2 | Wave 3 | Wave 4 |
|------|--------|--------|--------|--------|
| brws-author-a | #2467 | #2442/#2386 | #2310 | #2296 |
| brws-author-b | #2471 | #2466 | #2470 | idle |
| brws-author-c | idle | #2303 | idle | idle |
| brws-author-d | idle | #2346 | idle | idle |
| flex-a | P0-Verify proving | idle | Proving round 2 | Issue cleanup |
| flex-b | idle | idle | idle | Final proving |

**Expected output:** 8-10 new PRs merged + 7-12 issues closed via proving.

---

## Key Blockers and Risks

### 1. `web/routes.py` Serialization Bottleneck (HIGH)

Routes.py is 2,644 lines and touched by 6 of the 10 P0/P1 issues. Parallel
edits to routes.py cause merge conflicts and wasted cycles.

**Mitigation:** The wave structure above ensures at most ONE lane edits
routes.py per wave. Wave 1: brws-author-a. Wave 2: brws-author-a. Wave 3:
brws-author-a + brws-author-b (different handlers, acceptable overlap).

### 2. Render Deployment Lag (MEDIUM)

PRs merge to main but Render auto-deploys may take 5-15 minutes. Proving
runs against Render may see stale code.

**Mitigation:** Proving lanes should verify the deployed commit hash via
`/health` endpoint before running assertions. If stale, wait and retry.

### 3. #2471 Investigation Uncertainty (MEDIUM)

The auction log fix (#2459) may actually be working — the issue was filed
based on suspicion, not confirmed reproduction. If investigation confirms
the fix works, the issue becomes P0-Verify (just needs proving/close).

**Mitigation:** brws-author-b should start #2471 with investigation (15 min
cap). If fix works, post evidence and move on to Wave 2 work early.

### 4. #2442/#2386 Pacing — Investigation May Be Needed (MEDIUM)

The "gameplay latency" and "AI pacing" issues may have different root causes
or may already be resolved by PR #2399 + #2414. Investigation before coding
prevents wasted work.

**Mitigation:** brws-author-a should spend 15-20 min profiling the trick
transition flow before writing code. Check for double `time.sleep()`,
compounding delays, or unnecessary round-trips.

### 5. Render DB Wipes (#2220) May Explain #2296 (LOW)

The leaderboard "dropping players" may be caused by Render free-tier DB
resets rather than a code bug. If so, the fix is infrastructure (paid tier
or DB backup), not code.

**Mitigation:** Investigate DB state first. If data is simply gone (not
filtered), document the finding and defer to infra fix.

---

## Proving Protocol

### After Each Wave

1. **Flex lane runs targeted checks** from the go-live checklist
   (`plans/sessions/2026-04-05_go_live_checklist.md`)
2. **Post evidence** as comments on the relevant issues
3. **Close verified issues** with proving evidence per tiered closure policy

### Checklist Priority (from the audit)

| Priority | Checklist Section | Proves |
|----------|------------------|--------|
| P0 | D6 (Match end) | #2467 fix, #2446/#2210 verification |
| P0 | A4 (Auction log) | #2471 fix, #2438 verification |
| P0 | C1 (Pacing) | #2442/#2386 fix |
| P1 | D (Full lifecycle, 5+ hands) | Overall regression check |
| P1 | E1-E4 (Moon/Loner/Set) | Edge case coverage |
| P2 | F1-F3 (Error recovery) | Resilience |
| P2 | J (Onboarding) | #2455, #2470 verification |

### Playwright Automation

Where possible, use `/playtest-hybrid` or `/playtest-strategic` skills for
proving. Manual proving for visual items (CSS colors, layout).

---

## Issue Cleanup Candidates

Issues that can be closed without new code (already addressed by merged PRs):

| # | Title | Evidence |
|---|-------|----------|
| #2288 | UI polish round 4 | All 8 items addressed by PRs #2314, #2315, #2316, #2319, #2399, #2419, #2465 |
| #2198 | Create playtesting skill | Shipped in PR #2401 |
| #2238 | Review lane permission stalls | Fixed in PR #2398 |
| #2313 | Tiered issue closure policy | Shipped (rules/deferred/55_issue_closure.md exists) |
| #2337 | Overnight 50-PR fleet run plan | Superseded by this plan |

---

## Success Criteria

- [ ] All P0 bugs fixed and proven (0 go-live blockers remain)
- [ ] All P0-Verify items proven and closed (7 issues)
- [ ] At least 5/8 P1 items shipped
- [ ] Go-live checklist sections D and C1 pass end-to-end
- [ ] No regressions introduced (checklist sections A, F verify)
- [ ] `make check-gated` green on main after all merges

## Outcome

_To be filled after the overnight run with actual results._
