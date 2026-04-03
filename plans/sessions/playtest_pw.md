# Playwright Playtest — Production (Render)

**Date:** 2026-04-02
**URL:** https://bideuchre-web.onrender.com
**Invite code:** 694MZVQC
**Nickname:** Claude-PW
**AI model:** Bud Bot
**Match progress:** Hand 1 complete (You 7, AI 3), Hand 2 in progress (Slim bid 7 Low)

## Environment

- Render free-tier hosting (cold start observed: ~10s spin-up)
- Playwright MCP for browser automation
- Console: 0 errors, 1 warning (deprecated meta tag)

## Bugs Found

### BUG-1: HTMX request stall — no timeout/retry (CRITICAL)

**Severity:** CRITICAL
**Repro:** Play a match on Render free-tier; if the server goes to sleep mid-HTMX request, the UI is permanently stuck.

**What happens:**
1. User clicks a card to play or clicks "Next" to advance
2. The HTMX POST request is sent (`/play-card` or `/next`)
3. The Render server goes idle/sleeps mid-request
4. The request never returns a response
5. The form gains `class="htmx-request"` which intercepts all pointer events
6. UI shows "Playing card..." indefinitely with no way to recover except manual page refresh

**Observed:** Stalled twice in a single match:
- Trick 9, Hand 1: `/play-card` POST hung (no response code in network log)
- Hand 2 auction: `/next` POST hung (form `htmx-request` class blocked clicks)

**Root cause:** No HTMX timeout (`hx-timeout`) or retry (`hx-retry`) configured on game action forms. When the server sleeps mid-request, the client waits forever.

**Expected:** HTMX should have a timeout (e.g., 15s) and auto-retry or show a "Connection lost — click to retry" message.

**Recovery:** Page refresh recovers correctly — game state is preserved server-side. But users won't know to refresh.

### BUG-2: Premature contract/declarer display during auction

**Severity:** Medium
**Repro:** During Hand 1 auction, after Deuce bid 1♣ but before all players had bid.

**What happens:**
- Status bar showed "Contract: 1 ♣ · Declarer: Deuce" before auction was complete
- Deuce received the ★ (Declarer) badge prematurely
- After I passed (next bid), the status reverted to "Auction in progress" and ★ badge disappeared

**Expected:** Contract/declarer info should only appear after the auction is fully resolved.

### BUG-3: "Trick 1 of 10" heading during auction phase

**Severity:** Low
**Repro:** Every hand — visible during the auction before any cards are played.

**What happens:** The trick area header shows "Trick 1 of 10" during the auction phase, even though no tricks are being played yet.

**Expected:** During auction, the heading should either be hidden or say "Auction" instead of "Trick 1 of 10".

### BUG-4: Singular card count grammar — "1 cards"

**Severity:** Low
**Repro:** Observe any player's hand count when they have exactly 1 card.

**What happens:**
- "Deuce has 1 cards" (alt text)
- "Ace has 1 cards"
- "Slim has 1 cards"
- Display shows "Deuce (1)" which is fine, but the accessible alt text says "1 cards"

**Expected:** "1 card" (singular) vs "N cards" (plural).

### BUG-5: Left bower shows physical suit, not effective suit

**Severity:** Medium (UX confusion)
**Repro:** Play a suit contract where a left bower is played (e.g., J♣ when ♠ is trump).

**What happens:**
- Trick 9, Hand 1: Deuce led J♣ (left bower of ♠)
- The card displays as "J ♣" (physical suit)
- But the heading says "Lead suit: Spades ♠" (effective suit)
- No visual indicator that J♣ is acting as a trump card

**Expected:** Either:
- Show a bower badge/indicator on the card (e.g., "LB" overlay)
- Tint or highlight the card differently
- Add a tooltip explaining "Left bower — counts as ♠ trump"

### BUG-6: Auction log loses first entry after page refresh

**Severity:** Low
**Repro:** Refresh the page mid-hand after the auction.

**What happens:**
- Before refresh, auction log showed: "Deuce bid 1 C", "You passed", "Slim bid 2 D", "Ace bid 3 S"
- After refresh, auction log showed: "You passed", "Slim bid 2 D", "Ace bid 3 S"
- "Deuce bid 1 C" was lost

**Expected:** Full auction log preserved across page refresh.

### BUG-7: Batched state transitions — auction to play

**Severity:** Low (UX)
**Repro:** Click "Next" after the auction completes.

**What happens:** A single "Next" click transitions from "auction complete" to "2+ cards already played in trick 1". Users miss seeing the auction conclusion and the start of play as separate events.

**Expected:** Intermediate states: (1) auction concluded → (2) trick 1 starts → (3) first card played → etc.

### BUG-8: Deprecated meta tag warning

**Severity:** Info
**Console warning:** `<meta name="apple-mobile-web-app-capable" content="yes"> is deprecated. Please include <meta name="mobile-web-app-capable" content="yes">`

## What Worked Well

- **Session persistence:** Game state survives page refresh perfectly
- **Card legality enforcement:** Only legal plays are clickable (green border); illegal cards show "(cannot play)"
- **Scoring accuracy:** Hand 1 scored correctly (bid 3♠, took 7 → +7 declaring, +3 defending)
- **Accessible card display:** Cards have proper alt text, ARIA labels, and screen reader support
- **Badge system:** D (Dealer), ★ (Declarer), L (Lead), ▶ (Turn) badges are informative
- **Contract banner:** "Contract: 3 ♠ — Ace (Partner)" clearly shows the current contract
- **Auction panel:** Clean bid form with type/level/suit dropdowns + pass button
- **History tab:** Cards Played collapsible shows trick history
- **Match status bar:** Score, hand number, contract, and trick count always visible

## Filed Issues

| Issue | Bug | Severity | Label |
|-------|-----|----------|-------|
| #2202 | HTMX request stall — no timeout/retry | CRITICAL | fix:bug |
| #2203 | Premature contract/declarer display | Medium | fix:bug |
| #2204 | Left bower shows physical suit | Medium | fix:bug |
| #2205 | "1 cards" grammar | Low | fix:bug |
| #2206 | Trick heading during auction | Low | fix:bug |
| #2207 | Auction log truncation after refresh | Low | fix:bug |
| #2208 | Batched auction→play transitions | Low | fix:bug |
| — | Deprecated meta tag (apple-mobile-web-app-capable) | Info | not filed |
