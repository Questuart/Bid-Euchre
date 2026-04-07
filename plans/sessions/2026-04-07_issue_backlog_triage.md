# Issue Backlog Triage Report — 2026-04-07

**Analyst:** analyst-c | **Task:** d62acb5a4eae | **Date:** 2026-04-07

## Summary

91 open issues reviewed against 200+ recently merged PRs. Findings:

| Category | Count | Action |
|----------|-------|--------|
| **CLOSE** — resolved by merged PRs | 31 | Close with PR citation |
| **STALE** — superseded or no longer relevant | 8 | Close with reason |
| **KEEP OPEN** — still valid | 52 | Retain, status noted |

### Systemic Finding: `Fixes #N` Auto-Close Failure

10 issues remain open despite merged PRs that use `Fixes #N` in the PR body.
GitHub auto-close appears to be failing silently. Possible causes:
- Branch protection rules interfering with auto-close
- `Fixes #N` appearing in a non-standard location (e.g., inside a table or
  code block) that GitHub's parser doesn't recognize
- Merge method (squash vs merge commit) interaction

**Recommendation:** Investigate the auto-close failure pattern and manually
close the 10 affected issues with a comment citing the merged PR.

---

## CLOSE — Resolved by Merged PRs (31 issues)

### A. Auto-Close Failed — `Fixes #N` in PR Body, PR Merged (10 issues)

These issues should have been auto-closed by GitHub when the PR merged.
They were not. Each has a clear `Fixes #N` in the PR body and the PR is
confirmed MERGED.

| Issue | Title | Fixing PR | Merged |
|-------|-------|-----------|--------|
| #2576 | Pass button not blue after UX-5 merge | #2578 | 2026-04-07 |
| #2575 | Moon exchange highlights duplicate cards | #2577 | 2026-04-07 |
| #2547 | Unfilter stratbot from leaderboard, rename to Claude | #2565 | 2026-04-07 |
| #2545 | Auction pane visual distinction + Pass button blue | #2571 | 2026-04-07 |
| #2539 | High Bid display missing contract type suit icon | #2569 | 2026-04-07 |
| #2538 | Card play jitter/flicker during play animation | #2567 + #2574 | 2026-04-07 |
| #2509 | Remove Hand Details dropdown from game UI | #2511 | 2026-04-06 |
| #2508 | Duplicate bid log — collapsible log and table both visible | #2510 | 2026-04-06 |
| #2489 | Update dedication page text with expanded version | #2490 | 2026-04-05 |
| #2473 | Hide LB/RB bower badges during auction phase | #2476 | 2026-04-05 |

**Action:** Close each manually with comment: "Resolved by PR #NNNN (merged YYYY-MM-DD). Auto-close did not fire."

### B. Addressed with Verification Evidence (8 issues)

These issues used `Refs #N` in the PR body and have post-merge verification
comments or sufficient implementation evidence.

| Issue | Title | Addressing PR(s) | Evidence |
|-------|-------|-------------------|----------|
| #2477 | Auction log tracks trick results | #2481 | Proving evidence comment (2026-04-05) |
| #2470 | Add back button to onboarding flow | #2483 | Proving evidence comment (2026-04-05) |
| #2346 | Player name styling — team colors, duplicates, card count | #2480, #2411 | Proving evidence comment with 5 comments |
| #2338 | Create /away-mode skill for operator presence | #2381 + follow-ups (#2394, #2424, #2432) | Skill exists, multiple refinement PRs |
| #2455 | Add dedication page + remove skip option | #2461 | PR covers both items (dedication + skip removal) |
| #2521 | Bid form polish — large text, single-line, full-width Pass | #2531 | Comprehensive implementation (Refs) |
| #2554 | Moon exchange reveal — partner hand with highlights | #2562 | Feature fully implemented |
| #2466 | Remove icons/indicators section from help guide | #2478 | Section removed (Refs) |

**Action:** Close each with comment citing PR and evidence summary.

### C. Addressed by Refs — Recommend Close After Verification (7 issues)

These issues have PRs that address them (`Refs #N`) but no post-merge
verification comment. Recommend operator spot-check before closing.

| Issue | Title | Addressing PR(s) | Status |
|-------|-------|-------------------|--------|
| #2493 | Auction log shows winner prematurely | #2496 | Winner line hidden during auction |
| #2471 | Auction log not open by default during auction | #2491, #2475 | Multiple fixes applied |
| #2505 | Cards Played log suit icons invisible on dark background | #2512 | Text presentation forced on iOS/mobile |
| #2494 | Filter test players from leaderboard display | #2495, #2501 | Filtering implemented, but comment requests additional names — check if #2501 covered them |
| #2198 | Create playtesting skill for automated proving | #2401, #2413, #2421 | 4 playtesting skills created (HTTP, hybrid, strategic, Playwright) |
| #2304 | Narrow broad Bash auto-accept patterns | #2526 | Patterns narrowed per issue spec |
| #2288 | UI polish round 4 — 8 refinements | Multiple PRs | Most items addressed: #2465 (help bar), #2476 (bower badges), #2491/#2475 (auction log), #2486 (card play UX), #2419 (suit icons). Check items 1 (LEAD TRICK rename) and 2 (RB/LB legend) |

**Action:** Spot-check in deployed app, then close with verification note.

### D. Follow-Up Convention Issues — Batch Addressed (6 issues)

These follow-up convention issues from the review coordinator were addressed
by batch cleanup PR #2527 (merged 2026-04-06).

| Issue | Follow-up for PR | Addressed by |
|-------|------------------|--------------|
| #2492 | #2491 | #2527 (batch cleanup) |
| #2497 | #2495 | #2527 (batch cleanup) |
| #2487 | #2486 | #2527 (batch cleanup) |
| #2484 | #2480 | #2527 (batch cleanup) |
| #2463 | #2460 | #2527 (batch cleanup) |
| #2462 | #2458 | #2527 (batch cleanup) |

**Action:** Close each with comment: "Convention findings addressed by batch PR #2527."

---

## STALE — Superseded or No Longer Relevant (8 issues)

| Issue | Title | Reason to Close |
|-------|-------|-----------------|
| #2337 | Overnight 50-PR fleet run — dispatch plan | **Completed.** The overnight run on 2026-03-25c achieved 35 merged PRs. Planning issue only, no implementation remains. |
| #2136 | Have Claude post a test comment to comments board | **Superseded.** Testing exercise for pre-go-live. Go-live has occurred. Comments board functionality proven in production. |
| #2085 | Automated Claude proving run — 50 games | **Superseded.** Replaced by playtesting skills (#2401 HTTP, #2413 hybrid/strategic, #2421 Playwright). Those skills provide reusable, parameterized game proving. |
| #2112 | Playwright proving agent too slow — 20+ min per turn | **Superseded.** /playtest-hybrid skill (#2413) uses HTTP for speed with Playwright snapshots at key moments. The pure-Playwright approach was abandoned in favor of hybrid. |
| #2320 | Manual proving run checklist — browser game changes | **Completed.** Individual issues being proved are tracked separately. The checklist itself was a coordination artifact for the go-live push. |
| #2131 | Enable Codex to play the browser game | **Superseded.** Codex was retired as reviewer; replaced by local Codex CLI. The concept of an AI playing the browser game is now covered by playtesting skills. |
| #2507 | Clear the comments board for go-live | **Manual DB action.** This is a one-time operational task (purge test comments from Render DB), not a code issue. Should be tracked as an operator TODO, not a GitHub issue. |
| #2409 | Pattern of closing issues without functional verification | **Partially addressed.** Tiered closure policy (#2313), proving workflow (`.claude/rules/deferred/55_issue_closure.md`), and verify_issue_closure.py script now exist. The process gap this issue identified has been filled by institutional changes. Remaining enforcement is cultural, not code. |

**Action:** Close each with the stated reason.

---

## KEEP OPEN — Still Valid (52 issues)

### E. Follow-Up Convention Issues — Recent, Not Yet Addressed (13 issues)

These are auto-generated by the review coordinator for recently merged PRs.
Each contains specific code improvement findings. They are low priority (P2
equivalent) but represent valid technical debt.

| Issue | Follow-up for PR | Key Finding |
|-------|------------------|-------------|
| #2572 | #2571 | Restore Pass button contrast; mobile tap target test |
| #2568 | #2567 | Wait for trick-reset state before jitter check |
| #2563 | #2562 | Review findings for moon exchange reveal |
| #2561 | #2559 | Review findings for Cash-A.1 draw-trump fix |
| #2557 | #2555 | Review findings for StratBot tips |
| #2553 | #2550 | Review findings for UI/UX wave plan precheck |
| #2546 | #2543 | Review findings for StratBot V3 session report |
| #2542 | #2541 | Review findings for card jitter report precheck |
| #2536 | #2534 | Gate Fix 1b on holding ≥3 trump |
| #2533 | #2531 | Keep Submit Bid usable when bid level is Pass |
| #2532 | #2529 | Review findings for strategy versioning |
| #2530 | #2525 | Review findings for bid selector tests |
| #2528 | #2526 | Review findings for bash pattern narrowing |

**Recommendation:** These could be batch-addressed in a single convention
cleanup PR (like #2527 did for the previous batch). Low urgency.

### F. Active Bugs — Browser Game (7 issues)

| Issue | Title | Status |
|-------|-------|--------|
| #2503 | Auction auto-advances AI bids without waiting for Next | PR #2513 (Refs) merged but comment says behavior still flaky — **not fully resolved** |
| #2440 | Card play can hang — user stuck after playing card | PR #2414 removed broken JS guard, but root cause uncertain. No verification evidence. 0 comments. |
| #2442 | Gameplay latency between tricks | PR #2486 (Refs) added auto-advance. Playtest timing shows PASS but UX "feels instant" concern may persist. |
| #2386 | AI pacing still not resolved — feels instant and unnatural | PR #2486 (Refs). Overlaps significantly with #2442. Consider consolidating. |
| #2441 | Club/spade suit icons not rendering as black filled | PR #2452 + #2419 (Refs). Visual verification attempted but inconclusive. |
| #2346 | Player name styling (remaining items from proving) | Multiple PRs address this. Mostly resolved but proving comment history shows iteration. Consider closing if latest proving is clean. |
| #2300 | Glutton suit preservation bias | PR #2397 (Refs) + PR #2396. Extensive analysis. Research continues under strategy revamp. |

### G. AI Strategy Bugs & Research (11 issues)

| Issue | Title | Status |
|-------|-------|--------|
| #2537 | StratBot defense losing ~1.22/hand investigation | Active research. Analyst plans at `plans/sessions/2026-04-07_stratbot_v3_partial.md`. |
| #2506 | AI doesn't continue leading established suit | Active bug — not yet addressed by any PR. |
| #2504 | AI holds ace in High until last trick | Active bug — cash_winners analysis in progress. |
| #2502 | AI misplays Low — conserves 10s instead of leading | PR #2534 (Refs #2502, Cash-A) partially addresses. Cash-A.1 (#2559) adds more fixes. |
| #2520 | Rename greedy.py → glutton.py | Valid refactor request. Not yet started. |
| #2519 | Strategy versioning + fingerprinting | PR #2529 adds GLUTTON_STRATEGY_VERSION. Full fingerprinting scope is larger. |
| #2290 | Glutton wastes Aces early — suboptimal discard | Reopened. Root cause identified (void-creation sort bias). PR #2396 removes void sort. |
| #2149 | AI overbids when doesn't need to — bidding calibration | Enhancement A redesigned. Active research under GBT/Glutton plan. |
| #1917 | Glutton strategy revamp — experiment design | Ongoing research. Design doc updated. Subsumed by broader Glutton+GBT plan. |
| #2391 | Validate glutton discard simplification vs simulation | Research backlog. Not started. |
| #2389 | Glutton bid-context awareness | Research backlog. Deferred pending GBT deployment. |

### H. Feature Requests & Enhancements (10 issues)

| Issue | Title | Status |
|-------|-------|--------|
| #2469 | Log GBT bidding counterfactual alongside human bids | Enhancement backlog. Not started. |
| #2468 | Log glutton strategy counterfactual alongside human plays | Enhancement backlog. Not started. |
| #2390 | Unify bidding (GBT) and play (glutton) into cohesive AI | Research/design. Depends on GBT + Glutton revamp. |
| #2229 | Sim vs browser game parity experiment | Reopened. Plan exists but no author picked it up. |
| #2185 | AI suggested plays and bid recommendations | Analyst shaping complete (7 comments). Ready for dispatch. |
| #2188 | Ingest browser game comments to flag issues automatically | Enhancement backlog. Not started. |
| #2404 | Enhance /away-mode with autonomous work directive | Enhancement on top of shipped away-mode (#2338). |
| #2403 | Create /session-end skill for shutdown + handoff | Enhancement backlog. Not started. |
| #2220 | Render free-tier service fails to restart | Operational. Has analyst investigation. May need paid tier. |
| #2254 | Switch to dontAsk permission mode | Reverted. Needs user/Anthropic assist to solve core problem. |

### I. Ops & Process Improvements (11 issues)

| Issue | Title | Status |
|-------|-------|--------|
| #2415 | Orchestrator needs reliable lane status introspection | Enhancement. /capture-pane and /lane-status skills partially address. |
| #2384 | Design verification framework for issue lifecycle | Process design. Not started. |
| #2351 | Comprehensive audit of all closed issues | Has Wave 2 triage comment. This triage report partially addresses. |
| #2349 | Inbox messages not delivered when lane is idle | Architectural. Push-based delivery unresolved. tmux nudge is workaround. |
| #2334 | CPU-aware gate before make check | Reopened. PR merged but needs fleet verification. |
| #2333 | Auto-start fleet-check cron on orchestrator boot | Reopened. PR #2418 merged but behavior not tested. |
| #2313 | Tiered issue closure policy + DISABLE_MOUSE | Reopened. Needs fleet verification. |
| #2306 | Harden issue close workflow | Reopened. Needs fleet verification. |
| #2301 | CI tests-shard stuck for 55+ min | Bug. Has 6 comments of investigation. |
| #2271 | Author lanes spawn duplicate make check processes | Reopened, needs-verification. Fleet-level proving needed. |
| #2249 | Evaluate Claude Code auto-accept features | Needs user/Anthropic assist. Core self-edit problem unsolved. |
| #2238 | Review lane stalls on permission prompt | Core problem: Claude Code sensitive file detection. Workaround deployed. Fundamental fix needs upstream change. |

---

## Recommendations

### Immediate Actions (Operator)

1. **Close 31 CLOSE-category issues** with cited evidence (see sections A–D above)
2. **Close 8 STALE issues** with stated reasons
3. **Investigate auto-close failure** — 10 issues have `Fixes #N` in merged
   PR bodies but didn't auto-close. This pattern may affect future PRs.

### Short-Term Actions (Next Session)

4. **Batch convention cleanup PR** for the 13 recent follow-up issues (#2572
   etc.) — single PR like #2527 did for the previous batch.
5. **Spot-check 7 CLOSE-after-verification issues** (section C) in deployed
   app and close.
6. **Consolidate #2442 and #2386** — they describe the same gameplay pacing
   concern from different angles.

### Backlog Observations

7. **AI strategy bugs** (#2504, #2506) are actively being investigated under
   the Glutton+GBT plan. The analyst plans are well-documented.
8. **5 reopened ops issues** (#2271, #2306, #2313, #2333, #2334) all share the
   same pattern: "PR merged but needs fleet verification." Consider a dedicated
   fleet verification session to prove and close all 5.
9. **2 issues need user/Anthropic assist** (#2238, #2249) for Claude Code
   permission model improvements. These are blocked on upstream changes.
10. **#2185 (AI suggested plays)** has complete analyst shaping and is ready
    for author dispatch.

---

## Outcome

Report produced as `plans/sessions/2026-04-07_issue_backlog_triage.md`.
Recommended 39 closures (31 resolved + 8 stale), 52 keep-open with status notes.
