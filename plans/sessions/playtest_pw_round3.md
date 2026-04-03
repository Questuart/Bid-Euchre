# Playwright Playtest Round 3 — Accessibility & Mobile Layout

**Date:** 2026-04-03
**URL:** https://bideuchre-web.onrender.com
**Invite code:** 694MZVQC (continued match)
**Nickname:** Claude-PW
**Viewport:** 375x812 (iPhone SE / small mobile)
**Match progress:** Hands 6-10 (score You 11, AI 43)

## New Bugs Found

### BUG-R3-1: Large text mode overflows on mobile viewport (375px)

**Severity:** High (Accessibility)
**Repro:** Enable large text (Aa toggle) on a 375px mobile viewport during gameplay.

**What happens:**
- Nav tabs overflow left — "Game" tab completely off-screen
- "Help: Bid Euchre Rules" accordion text clipped at left edge
- "CONTRACT:" banner clipped at left edge
- Tab bar shows "...tory Leaderboard Comments Guide" (History truncated)

**Expected:** Large text mode should use responsive font scaling or horizontal scroll on the tab bar. The "Game" tab being unreachable is a critical accessibility failure — users who enabled large text for vision needs cannot navigate back to their game.

### BUG-R3-2: Tab navigation uses full page navigation, not client-side switching

**Severity:** Medium (UX/Performance)
**Repro:** Click any tab (History, Leaderboard, Comments, Guide) during a game.

**What happens:**
- Each tab navigates to a new URL (e.g., `/history/<id>`, `/leaderboard/<id>`)
- On Render free tier, this can trigger the server loading screen if it's gone idle
- Navigating to History then back to Game lost ~60s to Render cold start

**Impact:** Users exploring leaderboards or rules mid-game may get stuck waiting for the server. Client-side tab switching (HTMX partials or JS tabs) would avoid server round-trips entirely.

### BUG-R3-3: Guide page emoji rendering — replacement character

**Severity:** Low
**Repro:** Open the Guide tab. First Quick Start bullet point shows □ instead of 🂡.

**What happens:** The playing card emoji (🂡) in "□ You and your AI partner vs two AI opponents" renders as a replacement character on some platforms/fonts.

**Expected:** Use a universally supported emoji or text fallback.

### BUG-R3-4: "Guide" tab text truncated at 375px viewport

**Severity:** Low (Cosmetic)
**Repro:** View the tab bar on a 375px viewport. The "Guide" tab text is clipped to "Guid..." with the "e" barely visible.

**Expected:** Either abbreviate tab labels on mobile (e.g., "Rules") or use icons alongside text.

### BUG-R3-5: Render cold start ~90s with no custom loading page

**Severity:** Medium (Deployment/UX)
**Repro:** Let the Render free-tier instance spin down (~15min idle), then visit any page.

**What happens:**
- Users see Render's branded "APPLICATION LOADING" page with animated boot sequence
- Boot takes ~30s infrastructure + ~60s app initialization = ~90s total
- No game branding or loading indicator — only raw Render boot log

**Expected:** Consider a custom loading page, service worker with offline shell, or paid Render tier to eliminate cold starts.

## What Worked Well on Mobile

- **Compact AI hand display:** Top bar "S:6 A:6★ D:6Ⓓ" is an excellent mobile adaptation
- **Card tappability:** Cards are large enough to tap accurately at 375px
- **Status bar:** Score, hand info, contract all readable at bottom
- **Game board layout:** Trick area centered, cards clearly displayed
- **Tab navigation works:** All tabs load correct content (History, Leaderboard, Guide)
- **Leaderboard:** Table fits 375px, color-coded EPPD, AI badges, expandable stats
- **Guide:** Clear sections, Quick Start card, readable at mobile width
- **Normal text mode:** Game is fully playable and readable at 375px

## Tabs Tested

| Tab | Status | Notes |
|-----|--------|-------|
| Game | Works | Mobile-adapted layout with compact player info |
| History | Works | Shows "No completed matches yet" (correct) |
| Leaderboard | Works | Table fits mobile, color-coded EPPD, "Show More Stats" expands |
| Comments | Not tested | (skipped due to cold start delays) |
| Guide | Works | Good content, emoji rendering issue on first bullet |

## HTMX Stall Count (Cumulative)

| Round | Stalls | Hands Played |
|-------|--------|-------------|
| 1 | 2 | ~1.5 hands |
| 2 | 1 | ~4 hands |
| 3 | 3+ | ~5 hands |
| **Total** | **6+** | **~10 hands** |

## Filed Issues

| Issue | Bug | Severity |
|-------|-----|----------|
| #2221 | Large text + mobile overflow (Game tab unreachable) | High |
| #2222 | Tab navigation full page nav (not client-side) | Medium |
