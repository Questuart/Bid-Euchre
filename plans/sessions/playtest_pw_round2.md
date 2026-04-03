# Playwright Playtest Round 2 — Production (Render)

**Date:** 2026-04-03
**URL:** https://bideuchre-web.onrender.com
**Invite code:** 694MZVQC (resumed match from round 1)
**Nickname:** Claude-PW
**AI model:** Bud Bot
**Match progress:** Hands 2-6 (score You -4, AI 18 at stall point)
**Focus:** Moon/Loner bids, aggressive play, edge cases

## Environment

- Render free-tier hosting (cold start confirmed: ~10s spin-up between stalls)
- Playwright MCP for browser automation + scripted play loops
- Console: 1 error (new), 1 warning (known)

## New Bugs Found

### BUG-R2-1: Console TypeError on Moon Exchange render

**Severity:** Medium
**Repro:** Bid Moon in any suit during the auction.

**Console error:**
```
TypeError: Cannot read properties of null (reading 'insertBefore')
    at At (htmx.org@1.9.12:1:23203)
    at Nt (htmx.org@1.9.12:1:23330)
```

**What happens:** When the Moon Exchange panel renders via HTMX morph swap, HTMX tries to `insertBefore` on a null parent element. The Moon Exchange UI still renders and functions correctly, but this is a JS error that could cause subtle DOM issues.

**Root cause:** The HTMX morph swap (`hx-swap="morph:innerHTML"`) likely encounters a DOM structure mismatch between the auction panel and the Moon Exchange panel. The morph algorithm can't reconcile the old and new DOM trees, causing the null reference.

### BUG-R2-2: Duplicate card buttons have identical accessible names

**Severity:** Medium (Accessibility)
**Repro:** Have duplicate cards in hand (common in double-deck). Observe button labels.

**What happens:**
- Two "Play A of Spades" buttons with no way to distinguish them
- Two "Select K of Diamonds" buttons in Moon Exchange
- Two "Select 10 of Spades" buttons
- Screen readers and keyboard navigation cannot distinguish between duplicate cards

**Expected:** Add positional context or index, e.g., "Play A of Spades (1 of 2)" or "Play first A of Spades" / "Play second A of Spades".

### BUG-R2-3: HTMX stall frequency confirmation

**Severity:** CRITICAL (confirming #2202)
**Additional evidence:** Stall reproduced a **3rd time** in this session during Hand 6, trick 4 (`/play-card` POST). Over ~6 hands of play, the stall occurred 3 times — roughly once every 2 hands. This is not a rare edge case; it's a near-guaranteed failure mode for any match on Render free tier.

## Features Tested Successfully

### Moon Bid Mechanics

**Full flow tested:**
1. **Bid type selection:** Moon (20) selected from dropdown — bid level field dynamically hides (good UX)
2. **Moon Exchange UI:** Clean "🌙 Moon Exchange" panel appears
   - Card selection with toggle (pressed state shown)
   - Counter: "Select 2 more" → "Select 1 more" → "Cards selected"
   - Confirm button disabled until 2 cards selected
3. **Exchange summary:** Shows "Given to Ace: K♥, K♥" and "Received from Ace: A♦, J♦"
   - Partner AI correctly returned strongest trump (right bower + ace)
   - Updated hand displayed before trick play begins
4. **3-player trick display:** Partner (Ace) shown with "SO" (Sitting Out) badge, doesn't play
5. **Moon set scoring:** Hand result shows "🌙 Moon Set!" with -20 penalty. Correct.

### Low Contract Mechanics

- Hand 2 (Slim bid 7 Low): Rank ordering correct (10 > J > Q > K > A)
- J♠ correctly beats Q♠ and K♠ in Low
- Scoring after Low set verified

### Contract Type Variety

Across 6 hands, observed:
- Suit contracts (♦, ♣, ♠)
- Low contracts
- Moon contract
- Set and made outcomes for both teams

### Negative Score Display

Score correctly shows "You: -4" after Moon set. No display issues with negative numbers.

## What Worked Well (Round 2 Additions)

- **Moon Exchange flow:** Smooth, intuitive, good feedback at each step
- **Moon emoji (🌙):** Consistent branding in contract display, badge, and result
- **Sitting Out badge (SO):** Clear visual for Moon partner sit-out
- **Dynamic bid form:** Moon hides bid level; Regular shows level — clean conditional UI
- **Card exchange AI:** Partner gave back strong trump cards (right bower + ace), suggesting good AI exchange logic
- **Hand result variety:** "Made it!", "Set!", "🌙 Moon Set!" all display differently
- **Scripted play automation:** Game handled rapid automated clicks without errors (aside from server sleep stalls)

## Known Bugs Re-confirmed from Round 1

| Issue | Status |
|-------|--------|
| #2202 HTMX stall | Re-confirmed — 3 occurrences in 6 hands |
| #2203 Premature declarer | Not re-checked |
| #2205 "1 cards" grammar | Still present |
| #2206 Trick heading in auction | Still present |

## New Issues to File

| Issue | Bug | Severity | Label |
|-------|-----|----------|-------|
| #2214 | Console TypeError on Moon Exchange morph | Medium | fix:bug |
| #2215 | Duplicate card buttons identical accessible names | Medium | fix:bug |
