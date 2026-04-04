# Go-Live Session Plan — 2026-04-04 (Daytime)

**Date:** 2026-04-04
**Goal:** Finalize browser game UX for go-live TOMORROW (2026-04-05), establish
playtesting infrastructure, and clear quick-win platform issues.
**Session duration:** ~4-6 hours
**Operator priority:** Go-live readiness > Playtesting skill > Platform quick wins > Proving

---

## 0. Current State Assessment

### What Shipped Overnight (21 PRs)

The overnight run closed significant backlog. Key go-live-relevant merges:

| PR | Issue | What Shipped |
|----|-------|-------------|
| #2347 | #2328 | Hide contract/trump during auction |
| #2348 | #2331 | Move auction log below hand details during gameplay |
| #2370 | #2346 | Player name team colors + remove duplicate labels |
| #2377 | #2363 | Fix CI concurrency group collision on main |
| #2374 | #2362 | Fix 30 test failures on main |
| #2350 | #2303 | Remove create_tables() from render_admin.py |
| #2356 | #2254+#2304 | Switch to dontAsk mode + narrow Bash patterns |
| #2357 | #2334 | CPU-aware gate before make check |
| #2373 | #2333 | Auto-start fleet-check cron on orchestrator boot |
| #2369 | #2352 | Escape-before-send tmux pattern |
| #2364 | #2349 | Tmux inbox nudge for reliable delivery |
| #2368 | #2306 | Issue closure verification tooling + proving skill |
| #2366 | #2309 | Tests for skip_to_next_decision + /skip route |
| #2360 | #2305 | Tests for onboarding_complete migration |
| #2381 | #2338 | /away-mode skill for operator presence management |
| #2382 | #2380 | Hand-end skip assertion with state checks |
| #2379 | #2375 | Harden fleet-check autostart guard |
| #2378 | #2371+#2367 | Convention follow-ups batch |
| #2376 | #2353+#2344+#2341 | Convention follow-ups batch 2 |
| #2372 | #2365+#2358+#2355 | Convention follow-ups batch 3 |
| #2361 | — | Comprehensive repo review R24 |

### What Did NOT Ship (Expected but Failed)

| Issue | Why | Impact |
|-------|-----|--------|
| **#2330** | Author hit usage limit, never completed | **CRITICAL** — go-live blocker |
| #2238 | Not dispatched overnight | Review lane still stalls |
| #2311 | PR #2325 merged but issue still open | Needs verification |

### Issues Still Open (Go-Live Relevant)

| # | Title | Status | Go-Live? |
|---|-------|--------|----------|
| **#2330** | AI card delay + Next after human plays | **OPEN — not started** | **BLOCKER** |
| **#2386** | Slow play / AI pacing still unresolved | **OPEN — meta-issue for #2330** | **BLOCKER** |
| **#2385** | Cards played rail needs legend | OPEN | Should-fix |
| #2332 | Hide Skip button from UI | **DONE** (template already updated) | Close it |
| #2346 | Player name team colors | PR #2370 merged | Needs proving |
| #2329 | Clubs/spades suit icons | needs-verification | Needs proving |
| #2310 | Bid selector default | needs-verification | Needs proving |
| #2296 | Leaderboard drops inactive players | Shipped (PR #2308) | Needs proving |
| #2288 | UI polish round 4 | All 8 items shipped | Needs proving |
| #2328 | Hide contract/trump during auction | PR #2347 merged | Needs proving |
| #2331 | Auction log reposition | PR #2348 merged | Needs proving |

---

## 1. Fleet Layout

| Lane | Pool | Assignment | Status |
|------|------|-----------|--------|
| brws-author-a | Browser | **#2330 — AI card delay + pacing** | Primary |
| brws-author-b | Browser | #2385 — Cards played rail legend | Secondary |
| brws-author-c | Browser | Proving sweep (batch verify shipped features) | Reactive |
| brws-author-d | Browser | HOLD — reserve for #2330 follow-ups or proving fixes | Reserve |
| author-a | Platform | #2238 — Review lane permission stalls | Quick win |
| author-b | Platform | #2383 — Convention follow-up for away-mode | Quick win |
| author-c | Platform | HOLD for proving-related ops work | Reserve |
| author-d | Platform | **#2198 — Playtesting skill MVP** | Priority 2 |
| flex-a | Flex | Playtesting (once skill ships) | Wave 3+ |
| flex-b | Flex | Playtesting (once skill ships) | Wave 3+ |
| flex-c | Flex | Playtesting (once skill ships) | Wave 3+ |
| flex-d | Flex | Playtesting (once skill ships) | Wave 3+ |
| analyst-a/b/c/d | Analyst | Research (lower priority today) | Background |
| steward-review | Review | Autonomous review loop | Always |
| steward-ops | Ops | Monitoring | Always |

---

## 2. Wave Plan

### Wave 0 — Triage & Closures (T+0, 15 min)

**Orchestrator actions (no lane dispatch needed):**

1. **Close #2332** — Skip button is already hidden in `next_controls.html` via
   Jinja2 comment block. The template has `{# Skip button hidden per #2332 #}`.
   Post evidence comment and close:
   ```
   grep -A2 "Skip button hidden" web/templates/partials/next_controls.html
   ```

2. **Verify #2311** — PR #2325 merged. Check if `.test_durations` was regenerated.
   If yes, close with evidence. If not, dispatch to an author lane in Wave 1.

3. **Label needs-verification** on: #2346, #2329, #2310, #2296, #2288, #2328, #2331

4. **Check Render health:**
   ```bash
   curl -s https://bideuchre-web.onrender.com/health
   ```

### Wave 1 — Critical Browser UX + Quick Wins (T+15 min, parallel)

All 8 lanes dispatch simultaneously. No cross-lane file conflicts.

#### 🔴 brws-author-a: #2330 / #2386 — AI Card Delay + Pacing (GO-LIVE BLOCKER)

**Problem:** AI cards appear instantly, gameplay feels mechanical. Human plays
auto-advance without pause.

**Implementation spec:**

The backend pacing system already works correctly — each AI card play sets
`paused_after_play = True` and requires a "Next" click. The issue is:

1. **No visible delay:** Clicking "Next" immediately fires the HTMX request.
   AI cards appear with zero delay between Next click and card appearance.
2. **No pause after human plays:** When human plays a card, `submit_human_card()`
   immediately calls `_advance_ai()` which plays the first AI card in the same
   response. The human never sees JUST their card on the table.

**Changes needed:**

| File | Change | Risk |
|------|--------|------|
| `web/static/game.js` | Add JS delay (500-800ms) before HTMX request on Next button click. Show "thinking..." animation during delay. | Low — frontend only |
| `src/bid_euchre/hosted_play/engine.py` | In `submit_human_card()`, set `paused_after_play = True` BEFORE calling `_advance_ai()` when the human's card does NOT complete a trick. This gives the human a "see your card" pause. | Medium — changes pacing loop |
| `web/templates/partials/game_content.html` or `trick.html` | Add a "thinking" indicator element that JS can toggle | Low |
| `web/static/style.css` | Style for thinking indicator (`.pacing-indicator` classes already exist!) | Low |

**Detailed engine change:**

In `engine.py`, `submit_human_card()` currently does:
```python
# Human's card did NOT complete a trick:
state = self._advance_ai(state)  # Immediately plays AI cards
```

Change to:
```python
# Human's card did NOT complete a trick — pause to show human's card first:
hand_after.paused_after_play = True  # UI shows human's card + Next button
return state  # Don't advance AI yet — wait for Next click
```

Then `resume_after_play()` handles the Next click and runs `_advance_ai()`.

**Frontend delay approach:**

In `game.js`, intercept Next button form submissions:
```javascript
document.body.addEventListener('htmx:configRequest', function(event) {
    if (event.target.closest('.btn--next-step')) {
        // Show thinking animation
        var indicator = document.querySelector('.pacing-indicator');
        if (indicator) indicator.classList.add('active');
        // Delay the HTMX request by 600ms
        event.detail.triggerSpec = { delay: 600 };
    }
});
```

Or use HTMX's built-in `hx-trigger="click delay:600ms"` on the Next button.

**Validation:**
- Play a full hand and verify each transition requires Next
- Verify AI cards appear with visible delay after Next click
- Verify human's card appears on table before AI plays
- Verify no stuck states at trick completion or hand end
- `uv run python -m pytest tests/unit/hosted_play/ tests/integration/ -k "hosted_play or engine"`

**Scope:** `web/static/game.js`, `src/bid_euchre/hosted_play/engine.py`,
`web/templates/partials/` (trick/game_content), `web/static/style.css`

**Est:** 2-3 hours (most complex task today)

---

#### 🟡 brws-author-b: #2385 — Cards Played Rail Legend

**Problem:** Trick history uses underlines and highlights with no explanation.

**Changes:**
| File | Change |
|------|--------|
| `web/templates/partials/trick_history.html` | Add small legend text below the rail: "Underlined = winning card, Highlighted = your card" (or whatever the actual meanings are — check the CSS first) |
| `web/static/style.css` | Style the legend (small, muted, non-intrusive) |

**Validation:** Visual — legend appears, correct information, doesn't clutter UI.

**Scope:** `web/templates/partials/trick_history.html`, `web/static/style.css`

**Est:** 30-45 min

---

#### 🟢 brws-author-c: Proving Sweep (Batch Verification)

Verify all overnight-merged browser features still work correctly. This is NOT
implementation — it's a proving run using the deployed game.

**Checklist:**
- [ ] #2329 — Clubs/spades icons render dark/black (not white)
- [ ] #2310 — Bid selector defaults to next legal bid (not pass)
- [ ] #2296 — Leaderboard retains all players with 5+ hands
- [ ] #2288 — All 8 UI polish items visible
- [ ] #2346 — Player names colored by team (PR #2370)
- [ ] #2328 — Contract/trump hidden during auction (PR #2347)
- [ ] #2331 — Auction log moves below hand details during gameplay (PR #2348)

**Delivery:** Post proving evidence as comments on each issue and close verified
ones. File new issues for any regressions found.

**Scope:** No code changes — issue comments only.

**Est:** 1-1.5 hours

---

#### 🔵 brws-author-d: RESERVE

Hold for:
1. Follow-up fixes from brws-author-c proving sweep
2. #2330 overflow if the pacing changes need a second PR
3. Any go-live bugs discovered during proving

---

#### author-a: #2238 — Review Lane Permission Stalls

**Problem:** Review lane stalls on permission prompts. Root cause: `.claude/runtime/review_state/` writes not in auto-accept list.

**Fix:** Add to `.claude/settings.json` `permissions.allow`:
```json
"Edit(.claude/runtime/review_state/**)",
"Write(.claude/runtime/review_state/**)"
```

**Validation:** Review lane completes a full review cycle without stalling.

**Scope:** `.claude/settings.json`

**Est:** 15-20 min

---

#### author-b: #2383 — Convention Follow-Up for Away-Mode

**Problem:** Convention issues from PR #2381 review findings.

**Scope:** `.claude/skills/away-mode/`, `src/bid_euchre/ops/` (away-mode files)

**Est:** 20-30 min

---

#### author-c: RESERVE (Platform)

Hold for:
1. Infrastructure proving from overnight reopened issues
2. #2311 verification if needed
3. Any ops follow-ups from Wave 1

---

#### author-d: #2198 — Playtesting Skill MVP

See **Section 4 (Playtesting Skill Spec)** below for full spec.

**Est:** 2-3 hours for MVP

---

### Wave 2 — Follow-Ups + Deploy (T+1.5-2h)

Triggered when Wave 1 lanes complete.

| Lane | Task | Trigger |
|------|------|---------|
| brws-author-a | Continue #2330 or address review findings | — |
| brws-author-b | Available — take proving fixes from brws-author-c | brws-author-b done |
| brws-author-c | File issues for any regressions found | — |
| brws-author-d | Take first follow-up fix from proving | brws-author-c findings |
| author-a | Available — infrastructure proving batch | author-a done |
| author-b | Available — take follow-up work | author-b done |
| author-c | Infrastructure proving: #2271, #2301, #2312, #2313 batch | — |
| author-d | Continue #2198 PR-2 if PR-1 merged | author-d PR-1 done |
| **Orchestrator** | **Deploy latest main to Render** | All go-live PRs merged |

**Deploy Checklist:**
1. Verify main is green: `gh run list --branch main --limit 1`
2. Trigger Render deploy (push to main or manual trigger)
3. Health check: `curl -s https://bideuchre-web.onrender.com/health`
4. Smoke test: play one hand through the web UI

### Wave 3 — Playtesting (T+3-4h)

**Prereqs:** #2198 MVP merged + deployed, invite codes created.

| Lane | Mode | Nickname | Target |
|------|------|----------|--------|
| flex-a | Hybrid | Claude-HYB3 | 10+ matches |
| flex-b | HTTP-only | Claude-HTTP3 | 50+ matches |
| flex-c | Playwright | Claude-PW3 | 5+ matches |
| flex-d | HTTP try-hard | Claude-TRYHARD3 | 30+ matches |

**Pre-flight:**
```bash
# Create invite codes (from Render shell or local)
uv run python web/render_admin.py create-invite --code FLEX-A-0404
uv run python web/render_admin.py create-invite --code FLEX-B-0404
uv run python web/render_admin.py create-invite --code FLEX-C-0404
uv run python web/render_admin.py create-invite --code FLEX-D-0404
```

### Wave 4 — Go-Live Prep (T+4-5h)

1. **Operator manual proving run** using `plans/sessions/2026-04-05_go_live_checklist.md`
   - Priority sections: D (full lifecycle), C1 (pacing), B4 (AI card delay)
   - Estimated time: 45-60 min
2. **Final Render deploy** with all go-live PRs
3. **Address any P0 findings** from operator proving
4. **Mark go-live checklist outcome**

---

## 3. Go-Live Verification Matrix

Maps each go-live checklist section to the issue/PR that addresses it.

### Section A — Post-#2320 Merged Changes

| Checklist Item | Issue | PR | Status | Proving Lane |
|---------------|-------|-----|--------|-------------|
| A1. Hand sorting (alternating red/black) | #2326 | Merged prior | Verify | brws-author-c |
| A2. Bid selector default | #2310 | #2327 | needs-verification | brws-author-c |
| A3. Suit icon colors (clubs/spades) | #2329 | #2335 | needs-verification | brws-author-c |
| A4. Collapsible auction log | #2314 | Merged prior | Verify | brws-author-c |
| A5. "Leader" label + RB/LB legend | #2315 | Merged prior | Verify | brws-author-c |
| A6. "Your Team/Opponent" + Help tab | #2316 | Merged prior | Verify | brws-author-c |
| A7. Blue AI player names | #2319 | Merged prior | Verify | brws-author-c |

### Section B — Open Issues Expected Before Go-Live

| Checklist Item | Issue | Status | Lane |
|---------------|-------|--------|------|
| B1. Auction log repositioning | #2331 | ✅ PR #2348 merged | brws-author-c verify |
| B2. Hide contract/trump during auction | #2328 | ✅ PR #2347 merged | brws-author-c verify |
| B3. Skip button removal | #2332 | ✅ Already implemented | Close directly |
| **B4. AI card delay + Next after human** | **#2330** | **🔴 NOT IMPLEMENTED** | **brws-author-a** |

### Section C — High-Churn Features

| Checklist Item | Risk Level | Proving |
|---------------|------------|---------|
| C1. Pacing system | HIGH — depends on #2330 | After #2330 ships |
| C2. Bower display | Medium | brws-author-c verify |
| C3. Score display | Medium | brws-author-c verify |
| C4. Leaderboard | Medium | brws-author-c verify |
| C5. Auction log | Medium | brws-author-c verify |

### Critical Gap

**#2330 is the ONLY remaining go-live blocker that requires code changes.**
Everything else is either shipped (needs proving) or cosmetic (#2385 legend).

---

## 4. Playtesting Skill Spec (#2198 MVP)

### Design Principles (MVP Only)

- **HTTP endpoint mode only** — fastest, ~30s-1min per match
- **Simple game lifecycle** — join → bid → play → score → repeat
- **Observation logging** — write to session file, no auto-issue-filing (v2)
- **Single skill file** — `.claude/skills/playtesting/SKILL.md`
- **Invite code required** — pre-created via render_admin.py

### Skill Interface

```
/playtest --url <render_url> --code <invite_code> --nickname <name> --matches <N>
```

### Game Loop (HTTP Mode)

```
1. POST /enter-code  →  body: code=<invite_code>
2. POST /nickname    →  body: nickname=<name>
3. POST /select-ai   →  body: model_id=bud_bot
4. LOOP (per hand):
   a. GET /play/<uuid>  →  parse HTML for phase, turn_number
   b. IF auction:
      - Parse legal bids from HTML
      - POST /play/<uuid>/bid  →  body: bid_n=0 (always pass for MVP)
   c. IF trick_play + human turn:
      - Parse legal cards from HTML
      - POST /play/<uuid>/play-card  →  body: card_index=0, turn_number=N
   d. IF show_next:
      - POST /play/<uuid>/next
   e. IF hand_result or match_result:
      - Log scores
      - POST /play/<uuid>/next-hand  or  /play/<uuid>/play-again
5. After match: log observations to session file
6. Repeat from step 3
```

### Observation Schema

Per-match log entry:
```yaml
match_id: <uuid>
duration_seconds: <N>
final_score: [team0, team1]
hands_played: <N>
anomalies: []  # List of unexpected behaviors
strategy_notes: []  # What the AI did
```

### File Scope

| File | Purpose |
|------|---------|
| `.claude/skills/playtesting/SKILL.md` | Skill definition + instructions |
| `scripts/internal/create_invite_codes.sh` | Helper to batch-create codes |

### Acceptance Criteria

- [ ] Skill can be invoked and plays a complete match via HTTP
- [ ] Observations are logged to a session file
- [ ] No crashes or stuck states during normal gameplay
- [ ] Skill instructions are clear enough for flex lanes to use independently

### What's NOT in MVP (v2+)

- Playwright / hybrid mode
- Auto-issue-filing for bugs
- Strategic bidding/playing (bid > 0)
- Continuous overnight loop with cron
- Context-clear resilience

---

## 5. Dependency Graph

```
Wave 0 (orchestrator)
├── Close #2332 (already done)
├── Verify #2311
└── Label needs-verification issues

Wave 1 (parallel, no conflicts)
├── brws-author-a: #2330 (pacing) ──────────────────────────────┐
├── brws-author-b: #2385 (legend)                               │
├── brws-author-c: Proving sweep (no code changes)              │
├── author-a: #2238 (settings.json)                             │
├── author-b: #2383 (convention follow-up)                      │
└── author-d: #2198 PR-1 (playtesting skill) ────────────────┐  │
                                                              │  │
Wave 2 (freed lanes)                                          │  │
├── Follow-up fixes from proving                              │  │
├── Deploy to Render ← depends: #2330 merged ─────────────────┤──┘
└── author-d: #2198 PR-2 (if time) ← depends: PR-1 ──────────┘

Wave 3 (playtesting)
├── flex-a/b/c/d: Play games ← depends: #2198 merged + invite codes
└── Monitor via capture-pane

Wave 4 (go-live prep)
├── Operator proving run ← depends: Render deploy
└── Final fixes (if needed)
```

### Critical Serialization Chains

1. **#2330 → Render deploy → Operator proving** — pacing MUST ship before proving
2. **#2198 PR-1 → flex lane playtesting** — skill MUST ship before flex lanes play
3. **#2238 and #2383 are independent** — no file overlap

---

## 6. File Ownership — Safe Parallelism

### Conflict Matrix

| File / Directory | Lane | Conflict? |
|-----------------|------|-----------|
| `web/static/game.js` | brws-author-a (#2330) | **Exclusive** |
| `web/routes.py` | brws-author-a (#2330) | **Exclusive** |
| `src/bid_euchre/hosted_play/engine.py` | brws-author-a (#2330) | **Exclusive** |
| `web/templates/partials/trick_history.html` | brws-author-b (#2385) | **Exclusive** |
| `web/static/style.css` | brws-author-a OR brws-author-b | ⚠️ **Potential conflict** |
| `.claude/settings.json` | author-a (#2238) | **Exclusive** |
| `.claude/skills/away-mode/` | author-b (#2383) | **Exclusive** |
| `.claude/skills/playtesting/` | author-d (#2198) | **Exclusive** |

### Conflict Mitigation

**`web/static/style.css`** — both #2330 (pacing indicator styles) and #2385
(legend styles) may touch this file. However:
- #2330 uses **existing** `.pacing-indicator` classes (already in CSS lines 3108-3144)
- #2385 adds **new** legend classes

These are additive changes to different parts of the file. Low conflict risk.
If both PRs are open simultaneously, merge #2330 first (higher priority),
then have #2385 rebase.

---

## 7. Estimated Timeline

| Time | Event | Expected Output |
|------|-------|----------------|
| T+0 | Wave 0: Triage + closures | 1-3 issues closed |
| T+15m | Wave 1: Dispatch all lanes | 8 tasks in progress |
| T+45m | author-a, author-b complete | 2 quick-win PRs merged |
| T+1h | brws-author-b complete | Legend PR merged |
| T+1.5h | brws-author-c proving done | 5-7 issues verified/closed |
| T+2-3h | **brws-author-a #2330 complete** | **GO-LIVE BLOCKER CLEARED** |
| T+2-3h | author-d #2198 MVP complete | Playtesting skill merged |
| T+3h | Wave 2: Deploy to Render | Game live with pacing fix |
| T+3.5h | Wave 3: Flex lanes playtesting | 4 lanes playing games |
| T+4-5h | Wave 4: Operator proving run | Go-live checklist executed |
| T+5-6h | Final fixes + go-live sign-off | ✅ Ready for tomorrow |

### PR Budget

| Source | PRs | Confidence |
|--------|-----|-----------|
| #2330 (pacing fix) | 1 | High |
| #2385 (legend) | 1 | High |
| #2238 (review perms) | 1 | High |
| #2383 (convention) | 1 | High |
| #2198 (playtesting MVP) | 1 | Medium-High |
| Proving follow-up fixes | 1-3 | Medium |
| **Total** | **6-8** | |

---

## 8. Risk Assessment

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| **#2330 takes longer than 3h** | Go-live delay | Medium | brws-author-d is reserve; split into frontend-only PR (delay animation) and backend PR (pause-after-human) if needed |
| **#2330 introduces pacing regression** | Stuck states during gameplay | Medium | Full hand playthrough test required before merge; engine tests cover pause/resume |
| **Render deploy fails** | Can't prove on production | Low | Local Docker smoke test as fallback |
| **Proving sweep finds regressions** | New bugs block go-live | Medium | brws-author-d is reserve for emergency fixes |
| **#2198 scope creep** | Playtesting delayed | Medium | Strict MVP — HTTP mode only, no auto-issue-filing |
| **Review lane stalls delay merges** | Throughput reduction | Medium | #2238 fix in Wave 1; manual override available |
| **CSS conflict between #2330 and #2385** | Merge conflict | Low | Merge #2330 first, #2385 rebases |

### Fallback: If #2330 Can't Ship Today

If the full pacing implementation proves too complex for one session:

**Minimal viable pacing (frontend-only):**
1. Add `hx-trigger="click delay:600ms"` to the Next button in `next_controls.html`
2. Show `.pacing-indicator` animation during the delay
3. This gives a "thinking" feel without any backend changes

This is a 30-minute change that covers 70% of the UX improvement. The
backend change (pause after human card play) can ship in a follow-up.

---

## 9. Pre-Dispatch Checklist

- [ ] Close #2332 (already implemented — post evidence + close)
- [ ] Verify #2311 status (PR #2325 merged — check if issue can close)
- [ ] Label needs-verification on shipped-but-open issues
- [ ] Verify Render health: `curl -s https://bideuchre-web.onrender.com/health`
- [ ] Verify main is green: `gh run list --branch main --limit 1`
- [ ] Check all 8 author lane worktrees are clean: `git status`
- [ ] Dispatch Wave 1 tasks via task queue
- [ ] Set up fleet-check cron for monitoring

---

## Outcome

<!-- Filled after session completion -->
- PRs opened:
- PRs merged:
- Issues closed:
- Go-live checklist status:
- Playtesting status:
- Notes:
