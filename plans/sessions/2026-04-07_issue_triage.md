# Issue Triage — 2026-04-07

> **81 open issues** triaged in two passes.
> **Pass 1** (PR #2592): 30 issues (#2519–#2591). 14 closed, 1 missed (#2554).
> **Pass 2** (this document): 66 issues below #2519 + 3 corrections from Pass 1.

## Executive Summary

| Action | Count | Source |
|--------|-------|--------|
| **CLOSE — Fixed by merged PRs** | 25 | Pass 2 new (22) + Pass 1 corrections (3) |
| **CLOSE — Stale / superseded** | 8 | Pass 2 new |
| **KEEP — Needs verification** | 11 | Pass 2 new |
| **KEEP — Convention follow-ups** | 6 | Pass 2 new |
| **KEEP — Bugs needing fix** | 2 | Pass 2 new |
| **KEEP — Feature requests** | 9 | Pass 2 new |
| **KEEP — Research** | 7 | Pass 2 new |
| **KEEP — (from Pass 1)** | 12 | Pass 1 survivors (15 − 3 now closeable) |

**After executing all closures: 81 → 33 = 48 open issues.**

---

## Pass 1 Corrections (3 issues)

Issues from Pass 1 that were either missed or have since been fixed.

| Issue | Title | Fixed by PR | Status |
|-------|-------|-------------|--------|
| #2554 | Moon exchange reveal: show partner's hand | #2562 | **Missed** — was in the close list but `gh issue close` was not executed |
| #2591 | Auction log: show all 4 bidders on mobile | #2593 | **Fixed since Pass 1** — was KEEP, now has merged fix |
| #2509 | Remove Hand Details dropdown | #2511 | **Fixed since Pass 1** — was KEEP, now has merged fix |

### Closure commands (Pass 1 corrections)

```bash
for n in 2554 2591 2509; do
  gh issue close $n \
    --comment "Closing — fixed by merged PR. See plans/sessions/2026-04-07_issue_triage.md Pass 1 corrections."
done
```

---

## Pass 2: Issues Below #2519

### 1. CLOSE — Fixed by Merged PRs (22 issues)

#### 1a. Browser Game — Fixed (17 issues)

| Issue | Title | Fixed by PR(s) | Evidence |
|-------|-------|----------------|----------|
| #2288 | UI polish round 4 — 8 refinements | #2315, #2316, #2314, #2319, #2335, #2480, #2486 | All 8 items: (1) LEAD→LEADER #2315, (2) RB/LB legend #2315, (3) black spade #2335, (4) AI blue #2319, (5) score labels #2316, (6) auction log #2314, (7) card pacing #2486, (8) guide tab #2316 |
| #2346 | Player name styling — team colors | #2480, #2370 | Team-color classes added to all player name contexts |
| #2386 | AI pacing still not resolved | #2486 | Auto-advance AI card reveals; per-trick clicks reduced from 4+ to 1 |
| #2441 | Club/spade icons in trick log not black | #2452, #2419 | CSS suit variant restored for trick winner display |
| #2442 | Gameplay latency between tricks | #2486 | Auto-advance eliminates manual Next clicks for AI cards |
| #2455 | Add dedication page to onboarding | #2461 | Full implementation with proving evidence in comments |
| #2466 | Remove icons section from help guide | #2478 | Section removed, CSS cleaned up |
| #2470 | Back button to onboarding flow | #2483 | Back navigation implemented with proving evidence |
| #2471 | Auction log not open by default | #2475, #2491 | Stale state reset + forced open during auction |
| #2473 | Hide LB/RB bower badges during auction | #2476 | Badges hidden until trump decided |
| #2477 | Auction log tracks trick results | #2481 | Restricted to auction actions only |
| #2489 | Update dedication page text | #2490 | Expanded text from operator specification |
| #2493 | Auction log shows winner prematurely | #2496 | Winner line hidden during active auction |
| #2494 | Filter test players from leaderboard | #2495 | Exclusion list with exact + prefix matching |
| #2503 | Auction auto-advances AI bids | #2513 | Auto-advance suppressed during auction reveal/settle |
| #2505 | Black suit icons invisible on dark bg | #2512 | Force text presentation for suit icons on iOS/mobile |
| #2508 | Duplicate auction bid log display | #2510 | Duplicate transcript table removed |

#### 1b. Ops/Platform — Fixed (3 issues)

| Issue | Title | Fixed by PR | Evidence |
|-------|-------|-------------|----------|
| #2306 | Harden issue close workflow | #2368 | Verification tooling + proving skill implemented |
| #2304 | Narrow Bash auto-accept patterns | #2356 | `python *` → specific patterns; `tmux *` → specific subcommands |
| #2313 | Tiered closure policy + DISABLE_MOUSE | #2339 | ISSUE_TRIAGE_WORKFLOW.md updated, deferred rule added |

#### 1c. Strategy — Fixed (1 issue)

| Issue | Title | Fixed by PR(s) | Evidence |
|-------|-------|----------------|----------|
| #2300 | Glutton suit preservation bias | #2396, #2397 | Void-suit sort removed; lead-strongest-in-low fixed |

#### 1d. Infrastructure — Fixed (1 issue)

| Issue | Title | Evidence |
|-------|-------|----------|
| #2198 | Create playtesting skill | `.claude/skills/playtesting/SKILL.md` + 3 variant skills (hybrid, playwright, strategic) all exist |

### Closure commands (Pass 2 — fixed)

```bash
for n in 2288 2346 2386 2441 2442 2455 2466 2470 2471 2473 2477 2489 2493 2494 2503 2505 2508 2306 2304 2313 2300 2198; do
  gh issue close $n \
    --comment "Closing — fixed by merged PR(s). See plans/sessions/2026-04-07_issue_triage.md §Pass 2 for evidence."
done
```

---

### 2. CLOSE — Stale / Superseded / No Action (8 issues)

| Issue | Title | Reason to close |
|-------|-------|-----------------|
| #2220 | Render free-tier spin-down (15+ min outage) | **User decided "no action"** — accept cold starts, HTMX tab fix reduced frequency |
| #2254 | Switch to dontAsk permission mode | **Tried and reverted** — PR #2356 implemented dontAsk, then reverted to bypassPermissions. Decision finalized. |
| #2337 | Overnight 50-PR fleet run dispatch plan | **Stale session artifact** — the 2026-04-04 session is over. Plan consumed. |
| #2320 | Manual proving run checklist (Waves 3–5) | **Stale one-time task** — go-live happened 2026-04-05. Proving window closed. |
| #2351 | Comprehensive audit of all closed issues | **Audit completed** — extensive analyst findings posted in comments. Follow-up actions tracked separately. |
| #2384 | Design verification framework for issues | **Superseded** — PR #2368 implemented concrete tooling (verify_issue_closure.py + proving skill). The abstract design research is no longer needed. |
| #2409 | Pattern of closing issues without verification | **Superseded** — PR #2339 (tiered closure policy) + PR #2368 (verification tooling) directly address this concern. |
| #2112 | Playwright proving agent too slow | **Superseded** — HTTP-first playtesting skills created (`.claude/skills/playtesting/`, `playtest-hybrid/`, `playtest-strategic/`). Playwright speed is no longer a bottleneck. |

### Closure commands (Pass 2 — stale)

```bash
for n in 2220 2254 2337 2320 2351 2384 2409 2112; do
  gh issue close $n \
    --comment "Closing — stale or superseded. See plans/sessions/2026-04-07_issue_triage.md §Pass 2 for rationale."
done
```

---

### 3. KEEP — Needs Verification (11 issues)

Issues with fix PRs merged but lacking production/fleet verification.
Should be proved before closing (Tier 2 workflow).

#### 3a. Browser Game — Needs Verification (3 issues)

| Issue | Title | Fix PR(s) | Verification needed |
|-------|-------|-----------|---------------------|
| #2440 | Card play hang — user stuck | #2414, #2486 | Play 5+ games on Render without hang. Auto-advance should bypass the failure mode. |
| #2502 | AI misplays Low contracts (conserves 10s) | #2588 (Cash-A high/low) | Play 3+ Low contracts on Render. Verify AI leads 10s aggressively. |
| #2504 | AI holds ace in High contract | #2588 (Cash-A high/low) | Play 3+ High contracts on Render. Verify AI cashes aces early. |

**Note:** #2502 and #2504 should both be addressed by Cash-A (PR #2588),
which enables sure-winner cashing for high/low contracts. Cash-A step 0.5
leads non-trump sure-winners; in Low, 10s are top rank; in High, aces are
top rank. Needs gameplay proving to confirm.

#### 3b. Ops/Platform — Needs Verification (8 issues)

| Issue | Title | Fix PR | Status | Verification |
|-------|-------|--------|--------|--------------|
| #2238 | Review lane permission stalls | Multiple | **Still reproducing** — last comment: "All lanes reset to bypassPermissions". bypassPermissions still prompts on sensitive files. | Test a full review cycle without manual intervention |
| #2249 | Claude Code auto-accept audit | #2250, #2356 | **Partially addressed** — features audited, dontAsk tried/reverted. | Verify fleet runs without permission stalls |
| #2271 | Duplicate make check processes | #2285 (docs), #2357 (CPU gate) | **Mitigated, not root-fixed** — `make check-gated` throttles concurrency, but background-then-foreground pattern still possible | Verify no duplicate processes during fleet run |
| #2301 | CI shard-1 stuck 55+ min | #2321 (timeout) | **Mitigated** — CI timeout added. Root cause: browser test hang in `test_go_live_proving.py` | Verify no shard-1 timeouts in last 10 CI runs |
| #2333 | Fleet-check autostart on boot | #2373, #2418 | **Multiple fix attempts, still broken** — hook output format mismatch | Verify fleet-check starts after `/clear` on orchestrator |
| #2334 | CPU-aware gate before make check | #2357 | **Merged, needs fleet verification** | Verify `make check-gated` polls CPU and waits when load is high |
| #2338 | Away-mode skill | #2381 | **Merged, needs verification** | Run `/away-mode` and verify Telegram push |
| #2349 | Inbox messages not delivered when idle | #2364 | **Merged, needs verification** — original issue: lanes miss messages when idle | Send message to idle lane and verify receipt |

### Recommended verification batch

```bash
# Proving commands for browser game issues
# Run 5 games on Render and note Low/High contract results
# Issue #2440: Confirm no hang during 5 games
# Issue #2502: Note AI behavior in Low contracts
# Issue #2504: Note AI behavior in High contracts

# Ops verification can be done during next fleet run:
# #2271: Monitor for duplicate make check processes
# #2301: Check last 10 CI runs for shard-1 timeouts
# #2333: After /clear on orchestrator, check if fleet-check auto-starts
# #2334: Start 3+ lanes running make check-gated simultaneously
```

---

### 4. KEEP — Convention Follow-ups (6 issues)

Review coordinator findings from recent PRs. All are small (S-sized),
non-blocking improvements.

#### 4a. Playwright Test Improvements (3 issues)

| Issue | PR | Finding | File |
|-------|----|---------|------|
| #2462 | #2458 | Detect auction state independently of bid panel | `test_go_live_proving.py:79` |
| #2463 | #2460 | Handle auction reveal/redeal after test submits Pass | `test_go_live_proving.py:121` |
| #2484 | #2480 | Require bid panel before taking Pass path | `test_go_live_proving.py:90` |

**Recommendation:** Batch into 1 PR. All touch `tests/browser/test_go_live_proving.py`.

#### 4b. Browser Game Resilience (3 issues)

| Issue | PR | Finding | File |
|-------|----|---------|------|
| #2487 | #2486 | Recover from auto-advance request failures | `game.js:685` |
| #2492 | #2491 | Preserve user-selected auction log state during auction | `game.js:329` |
| #2497 | #2495 | Avoid hiding real users based on mutable nicknames | `leaderboard.py:32` |

**Recommendation:** Batch into 1 PR. All touch `web/static/` or `web/`.

---

### 5. KEEP — Bugs Still Needing Fix (2 issues)

| Issue | Title | Size | Notes |
|-------|-------|------|-------|
| #2506 | AI doesn't continue leading established suit | M | Cash-A fixes sure-winner leading but NOT suit continuity. Multiple evidence comments show AI switching suits after establishing one. Needs strategy logic fix. |
| #2507 | Clear comments board for go-live | S | DB operation (purge test comments from `bideuchre-db`). Not code — operator action or script. |

---

### 6. KEEP — Feature Requests (9 issues)

#### 6a. Browser Game Features (7 issues)

| Issue | Title | Size | Priority |
|-------|-------|------|----------|
| #2468 | Log glutton counterfactual alongside human plays | M | High — enables decision-diff dataset for strategy research |
| #2469 | Log GBT bidding counterfactual alongside human bids | M | High — enables bid divergence tracking |
| #2185 | AI suggested plays and bid recommendations | M-L | Medium — nice UX feature, depends on counterfactual logging |
| #2131 | Enable Codex to play the browser game | L | Low — interesting but non-essential |
| #2136 | Claude post a test comment to comments board | S | Low — proving task, not a feature |
| #2085 | Automated Claude proving run (50 games) | M | Low — playtesting skills exist, this is an operational milestone |
| #2188 | Ingest browser comments to flag issues | M | Low — nice-to-have ops automation |

#### 6b. Ops/Platform Features (2 issues)

| Issue | Title | Size | Priority |
|-------|-------|------|----------|
| #2403 | Create /session-end skill for shutdown + handoff | M | Medium — reduces manual shutdown steps |
| #2415 | Reliable lane status introspection | M | Medium — current pane capture is fragile |

**Deferred (merged into other work):**
| Issue | Title | Reason |
|-------|-------|--------|
| #2404 | Enhanced /away-mode with autonomous directives | Depends on #2338 verification first |

---

### 7. KEEP — Research (7 issues)

| Issue | Title | Size | Priority | Notes |
|-------|-------|------|----------|-------|
| #1917 | Glutton strategy revamp — experiment design | L | Low | Partially addressed by Cash-A and glutton fixes. Broader research question remains. |
| #2149 | AI overbids when it doesn't need to | M | Medium | Enhancement A (PR #2586) adds overbid cap. May partially fix. Needs gameplay verification. |
| #2229 | Simulation vs browser game parity experiment | M | Medium | PR #2126 fixed original bug. Experiment not yet run. |
| #2290 | Glutton wastes Aces early, conserves 10s | M | Medium | Partially addressed by Cash-A sure-winner leading. Deeper ordering issue may persist in non-lead situations. |
| #2389 | Glutton bid-context awareness evaluation | M | Low | Research: does glutton need declaring vs defending awareness given GBT? |
| #2390 | Unify bidding (GBT) and play (glutton) | L | Low | Long-term strategic research. |
| #2391 | Validate glutton discard/lead simplification | M | Medium | PRs #2396, #2397 ARE the simplifications. This issue asks for simulation validation of those simplifications. |

---

## Combined Dispatch Plan (All 48 Remaining Issues)

### Wave 1 — Bulk Close (33 issues → 0 remaining)

Execute all closure commands from Sections Pass 1 Corrections, §1, and §2.

```bash
# Pass 1 corrections (3)
for n in 2554 2591 2509; do
  gh issue close $n \
    --comment "Closing — fixed by merged PR. See plans/sessions/2026-04-07_issue_triage.md."
done

# Pass 2 — fixed by merged PRs (22)
for n in 2288 2346 2386 2441 2442 2455 2466 2470 2471 2473 2477 2489 2493 2494 2503 2505 2508 2306 2304 2313 2300 2198; do
  gh issue close $n \
    --comment "Closing — fixed by merged PR(s). See plans/sessions/2026-04-07_issue_triage.md."
done

# Pass 2 — stale/superseded (8)
for n in 2220 2254 2337 2320 2351 2384 2409 2112; do
  gh issue close $n \
    --comment "Closing — stale or superseded. See plans/sessions/2026-04-07_issue_triage.md."
done
```

**After Wave 1: 81 → 48 open issues.**

### Wave 2 — Convention Follow-up Batches (6 + 9 from Pass 1 = 15 issues → 5 PRs)

From Pass 1 (still valid):

| Batch | Issues | Domain | Lane | Est. |
|-------|--------|--------|------|------|
| A — Strategy fixes | #2587, #2561, #2536, #2583 | `src/bid_euchre/strategy/`, `experiments/configs/` | author (Cash-A familiarity) | 1-2h |
| B — Browser game fixes (Pass 1) | #2572, #2533, #2532 | `web/`, `tests/browser/` | brws-author | 1-2h |
| C — Test fixes | #2568, #2530 | `tests/` | any author | 1h |

From Pass 2:

| Batch | Issues | Domain | Lane | Est. |
|-------|--------|--------|------|------|
| D — Playwright test fixes | #2462, #2463, #2484 | `tests/browser/test_go_live_proving.py` | any author | 1h |
| E — Browser resilience | #2487, #2492, #2497 | `web/static/game.js`, `web/leaderboard.py` | brws-author | 1-2h |

**Safe parallelism:** All 5 batches are disjoint by file scope. Run all in parallel.

### Wave 3 — Verification Sprint (11 issues)

Prove-then-close for issues with merged fix PRs.

| Priority | Issues | Method |
|----------|--------|--------|
| **P1 — Gameplay** | #2440, #2502, #2504 | Operator plays 5+ games on Render, notes Low/High AI behavior |
| **P2 — Ops (next fleet run)** | #2271, #2301, #2334 | Monitor during fleet run |
| **P3 — Ops (manual test)** | #2333, #2338, #2349 | Test each in isolation |
| **P4 — Ongoing** | #2238, #2249 | Track across multiple sessions |

### Wave 4 — Bug Fixes + Quick Wins (2 bugs + 2 easy features → 4 PRs)

| Issue | Lane | Est. |
|-------|------|------|
| #2506 (AI suit continuity) | author (strategy) | 2-3h |
| #2507 (clear comments DB) | operator (DB script) | 15min |
| #2521 (bid form item 1) | brws-author | 1h |
| #2136 (Claude post test comment) | flex (proving) | 30min |

### Wave 5 — Strategy Infrastructure (from Pass 1, still valid)

| Issue | Lane | Est. |
|-------|------|------|
| #2520 (rename greedy→glutton) | author | 1-2h |
| #2519 (strategy versioning items 3-6) | author | 2-3h |

**Dependency:** #2520 before #2519.

### Wave 6 — Feature Requests (backlog, schedule as bandwidth allows)

| Priority | Issues | Domain |
|----------|--------|--------|
| High | #2468, #2469 | Counterfactual logging (enables research) |
| Medium | #2185, #2403, #2415 | UX + ops tooling |
| Low | #2131, #2085, #2188, #2404 | Nice-to-haves |

### Wave 7 — Research (backlog, analyst bandwidth)

| Priority | Issues | Scope |
|----------|--------|-------|
| Medium | #2149, #2229, #2290, #2391 | Verifiable experiments |
| Low | #1917, #2389, #2390, #2537 | Open-ended investigations |

---

## Lane Assignment Summary (Waves 2-4)

| Lane | Batch/Issues | PR Count |
|------|--------------|----------|
| **author-a** | Batch A (#2587, #2561, #2536, #2583) | 1 |
| **author-b** | Batch C (#2568, #2530) + Batch D (#2462, #2463, #2484) | 2 |
| **author-c** | #2506 (AI suit continuity) | 1 |
| **brws-author-a** | Batch B (#2572, #2533, #2532) | 1 |
| **brws-author-b** | Batch E (#2487, #2492, #2497) + #2521 | 2 |
| **analyst** | Verification coordination + research triage | report |
| **orchestrator** | Wave 1 closures + verification sprint | bulk ops |

---

## Risks and Scope Traps

1. **Cash-A verification gap** — #2502 and #2504 are "likely fixed" by Cash-A
   but the flag was only recently enabled (PR #2588). No gameplay proving has
   been done since. Could close prematurely.

2. **#2238 permission stalls** — This is a chronic issue with 7 comments and
   multiple fix attempts. bypassPermissions still prompts on `.claude/` files.
   May require upstream Claude Code changes.

3. **Convention follow-up staleness** — Some findings (especially from older
   PRs) may reference code that has since been refactored. Each batch PR
   should verify the finding is still reproducible before fixing.

4. **#2506 strategy fix scope** — "Continue leading established suit" could
   expand into a full play-strategy redesign. Bound to: if AI wins a trick
   and holds more cards in the same suit, lead that suit again.

5. **Research issue sprawl** — 7 research issues with overlapping scope
   (#1917, #2290, #2389, #2390 all touch glutton strategy). Risk of
   duplicate investigation. Recommend consolidating into one research
   initiative with clear sub-questions.

---

## Pass 1 — Original Triage (Reference)

> The original 30-issue triage (PR #2592) is preserved below for reference.
> **14 of 15 recommended closures were executed.** #2554 was missed (now
> corrected above). 2 KEEP issues (#2591, #2509) have since been fixed.

### Pass 1 Survivors (12 issues still open, still valid)

**Convention follow-ups (9):** #2587, #2583, #2572, #2568, #2561, #2536, #2533, #2532, #2530
**Substantive work (3):** #2537, #2521, #2520, #2519

(#2591 and #2509 moved to CLOSE in Pass 1 Corrections above.)

---

## Outcome

_To be filled after dispatch._
