# UX Audit — Spatial Layout & Visual Analysis

> **Date:** 2026-04-02
> **Analyst:** analyst-a
> **Task:** `17a3359a4728` — UX audit with Playwright screenshots
> **Screenshots:** `plans/sessions/ux_audit/*.png` (18 files, desktop + mobile)

---

## 1. Executive Summary

The browser game is fully playable end-to-end across desktop and mobile. The
core flow (landing → invite → nickname → model select → auction → trick play →
hand result → leaderboard) works correctly. The UX has several areas that would
benefit from iteration, organized below by severity.

**Key findings:**
- Card spatial layout is top-down linear (all AI at top, human at bottom) rather
  than the compass-rose arrangement you'd expect from a 4-player card table
- Seat marker icons (D, X, L, SO) are functional but cryptic for new players
- Mobile auction phase requires scrolling — bid controls pushed below fold
- The "Play card" button + help text are vestigial since mobile tap-to-play was
  added (PR #2003)
- Score bar and action rail compete for vertical space on mobile
- Landing/nickname/model-select pages have excessive whitespace on desktop

---

## 2. Phase-by-Phase Analysis

### 2.1 Landing Page

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| Layout | Centered, clean | Good vertical flow |
| CTA clarity | Good — "Enter Invite Code" is clear | Good |
| Whitespace | Excessive below the fold — feels empty | Appropriate |

**Issues:**
- **(P2)** No visual branding beyond text — no logo, card imagery, or thematic
  element. The dark green background is the only visual identity.
- **(P2)** The header bar on landing shows only "Bid Euchre" without nav links
  (Game / Leaderboard appear after entering). This is correct behavior but
  landing feels bare.

**Recommendations:**
- Add a subtle card fan or deck illustration to the hero section
- Consider a background pattern (card suit watermark) to reduce the "empty dark
  green box" feel on desktop

### 2.2 Nickname Form

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| Layout | Centered card — clean | Fills width well |
| Input sizing | Good | Good, touch-friendly |

**Issues:**
- **(P3)** Desktop form card is quite small (narrow) relative to the available
  space. The `max-width` on the card produces a lot of empty green space.
- **(P3)** No character limit or validation hint shown to the user.

### 2.3 Model Select

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| Layout | Centered card | Good width |
| AI description | Truncated in dropdown | Truncated, worse |

**Issues:**
- **(P1)** The AI model dropdown text is truncated: "Bud Bot — Gradient-boosted
  bidder with..." — users can't read the full description of what they're
  selecting.
- **(P2)** Only two model options (OLSa, Bud Bot) — the dropdown is the wrong
  UI primitive for 2 options. Radio buttons or cards with full descriptions
  would be clearer.
- **(P3)** "Welcome, UX Tester!" greeting is nice but the page is mostly
  whitespace below.

**Recommendations:**
- Replace `<select>` with radio cards showing full model name + 1-line
  description
- Add a brief "what to expect" note (match length, scoring target)

### 2.4 Auction Phase

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| Card layout | All 3 AI hands in top row | Same, works |
| Trick area | Compass-rose (Partner top, Left/Right sides, You bottom) | Same |
| Bid panel | Below trick area | **Pushed below fold** |
| Human hand | Below bid panel | **Requires scrolling** |
| Score bar | Below hand — visible | Below fold on initial load |

**Issues:**
- **(P1 — Spatial Layout)** The 3 AI hands are displayed as a horizontal row
  across the top, each showing face-down card backs. This is a linear layout,
  not a card-table spatial layout. The desired arrangement for a 4-player game
  is:
  - Partner (seat 2): **top center**  ✓ (currently in row, centered)
  - Left opponent (seat 1): **left side, vertically** ✗ (currently top-left)
  - Right opponent (seat 3): **right side, vertically** ✗ (currently top-right)
  - Human (seat 0): **bottom center** ✓

  The trick area *does* use compass-rose layout (partner top, left/right at
  sides, you at bottom) which is correct. But the AI hands use a flat row, so
  the spatial relationship between "AI Left's cards" and "AI Left's trick
  slot" is broken — Left's cards are at the top, but Left's trick slot is at
  the left of the trick table.

- **(P1 — Mobile Scrolling)** On mobile (375px), the full auction view doesn't
  fit in one screen. The vertical stack is: AI hands row → trick area → auction
  transcript → bid controls → human hand → score bar → action rail. The bid
  controls and human hand are pushed well below the fold. Players need to
  scroll to see their hand *and* the bid panel simultaneously, which is a
  significant usability problem.

- **(P2)** The bid controls use three inline `<select>` elements (Type, Level,
  Contract) plus Submit + Pass buttons. On mobile, these wrap awkwardly.
  The "Type: Regular" dropdown is full-width on mobile, pushing Level and
  Contract to a second line.

- **(P2 — Seat Markers)** The orange D (Dealer), gold X (Declarer), green ▶
  (Turn) badges are displayed both in the AI seat labels *and* on the trick
  table slots. The letters are functional but require learning:
  - D = Dealer (not obvious; could be "Diamonds")
  - X = Declarer (not intuitive)
  - L = Leader (only in trick area)
  - SO = Sitting Out

**Recommendations for spatial layout:**
```
  Desired card-table layout:

          [Partner hand - horizontal]

  [Left     [Trick Table - compass]    [Right
   hand       Partner top                hand
   vertical]  Left    Center   Right    vertical]
               You bottom

          [Human hand - horizontal]
          [Score bar]
```
- Move AI Left hand to left edge, displayed vertically (rotated 90°)
- Move AI Right hand to right edge, displayed vertically (rotated 90°)
- Keep Partner hand horizontal at top and human hand horizontal at bottom
- This creates the classic card-table compass-rose layout matching the trick
  area's existing layout

### 2.5 Trick Play Phase

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| Trick table | Compass-rose layout — good | Same, compact |
| Played cards | Clear, well-positioned | Slightly small but readable |
| Legal cards | Green glow + pointer — good | Green glow visible |
| Trick count | Center of table (0–0) — clear | Clear |

**Issues:**
- **(P1 — Play Card Button)** The "Play card" button and "Tap a card to play
  it." help text are shown during trick play on mobile. But PR #2003 changed
  mobile to tap-to-play (immediate play on tap). The button + help text are
  now vestigial on mobile — they add clutter and consume vertical space
  without serving a purpose. On desktop, the select-then-confirm flow still
  exists, so the button is needed there.

- **(P2)** The trick area has a large green felt background (min-height: 260px)
  which, combined with the AI hands row, consumes most of the viewport on
  mobile. The human hand is barely visible without scrolling.

- **(P2)** Card colors: Hearts and Diamonds are red (#d32f2f) — this is good.
  Spades and Clubs are black (#212121) on white card backgrounds — this is
  correct but means on mobile the small cards can feel low-contrast against
  the dark overall theme.

- **(P2 — Trick Winner Feedback)** The trick winner text ("AI Left won with
  ♠A") appears as small muted text below the trick table. This is the primary
  feedback for what just happened and it's too subtle.

**Recommendations:**
- Hide "Play card" button + help text on mobile viewport (CSS media query)
  since tap-to-play is already active
- Reduce `min-height` on `.trick-table` for mobile to reclaim vertical space
- Make trick winner feedback more prominent (larger text, brief highlight)

### 2.6 Hand Result

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| "Made it!" title | Clear, red text | Clear |
| Scoring table | Clean | Clean |
| Match score | Clear | Clear |
| Next Hand button | Prominent green | Full-width, good |

**Issues:**
- **(P2)** The result title "Made it!" is red regardless of whether it's good
  or bad for the human player. Looking at the CSS, `result--made` gets a green
  left border and `result--set` gets a red left border, which is correct. But
  the screenshot shows "Made it!" in red — this is because the AI made their
  bid (AI Right bid 3 ♣ and took 6 tricks), which is bad for the human. The
  result title color should be contextual:
  - AI made their bid = bad for human → red "Made it!" is correct
  - Human made their bid = good for human → should be green "Made it!"

  **Actually, re-checking:** The CSS `.result-title` appears to use a fixed
  color. The left border correctly indicates good/bad, but the title text
  color doesn't change. This is confusing — the left border says "red = bad"
  but the title in red could mean "emphasis."

- **(P3)** No visual distinction between which team made/got set. The heading
  says "AI Right bid 3 ♣ and took 6 tricks" which requires reading to
  understand the outcome. A badge or icon ("Your team defended!" vs "Your team
  got set!") would be clearer.

### 2.7 Leaderboard

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| Table layout | Clean, sticky headers | Responsive, columns hidden |
| Net EPPD column | Gold highlight — good | Visible |
| "Show More Stats" toggle | Works | Works |

**Issues:**
- **(P2 — Mobile Columns)** On mobile, the leaderboard shows #, Player, Net
  EPPD, Won, Win %, Avg — but the "Avg Margin" and "Matches" columns are cut
  off. The "Show More Stats" button exists but the secondary columns are
  probably too many for mobile.

- **(P3)** Duplicate entries visible ("UX Tester" appears twice in mobile
  screenshot) — this is an artifact of the test creating two invite codes,
  but it reveals that the leaderboard doesn't deduplicate by nickname.

---

## 3. Cross-Cutting Issues

### 3.1 Spatial Layout — Priority Recommendation

The single highest-impact UX change would be reorganizing the game board to
a card-table spatial layout. Currently:

```
Current layout:
  [AI Left cards] [AI Partner cards] [AI Right cards]   ← flat row
  [Trick table - compass rose]
  [Bid panel / controls]
  [Human hand]
  [Score bar]
  [Action rail]
```

This creates a disconnect: AI Left's cards are at top-left, but their trick
slot is at the *middle-left* of the compass rose. The spatial metaphor is
broken.

**Proposed layout (desktop):**
```
                    [AI Partner cards - horizontal]

  [AI Left cards    [Trick table - compass rose]      [AI Right cards
   vertical,         Partner top                       vertical,
   rotated]          Left    Center    Right            rotated]
                     You bottom

                    [Human hand - horizontal]
                    [Score bar]
```

**Proposed layout (mobile):**
Keep the current stacked layout but compress the AI hands row into a more
compact display (icon + count instead of full card backs) to save vertical
space. The card-table spatial rotation doesn't work well on narrow screens.

### 3.2 Information Density on Mobile

The mobile game view stacks 7+ sections vertically:
1. Header bar
2. Help drawer
3. AI hands row
4. Trick area (260px min-height)
5. Bid panel (auction only)
6. Human hand
7. Score bar
8. Action rail

On a 667px viewport, this requires significant scrolling. The player's most
critical information (their hand, what's been played, whose turn it is) is
spread across 3-4 screens of scrolling.

**Recommendations:**
- Collapse AI hands into a compact badge (e.g., "L:10 P:10 R:10") on mobile
- Reduce trick table min-height on mobile from 260px to ~180px
- Move score bar above the trick area (it's more reference-like)
- Hide action rail behind a toggle on mobile (it's a log, not primary UI)

### 3.3 Seat Marker Icon Clarity

| Icon | Meaning | Issue |
|------|---------|-------|
| D | Dealer | Could be "Diamonds" — confusing |
| X | Declarer | Unintuitive letter choice |
| ▶ | Current turn | Best of the set — clear |
| L | Leader | OK but only visible in trick area |
| SO | Sitting out | Good, but rarely seen |

**Recommendations:**
- Replace "D" (Dealer) with a chip/button icon (🎲 or a custom dealer button
  SVG)
- Replace "X" (Declarer) with "★" or a gavel icon
- Add tooltips (already exist via `title` attr — good)
- Consider adding a legend accessible from the help drawer

### 3.4 Color & Contrast

The dark green theme (--color-bg: #1b5e20) works well for a card table feel.
However:
- **(P2)** Muted text (#bdbdbd on #0d3d0f) has contrast ratio ~4.7:1 — barely
  meets WCAG AA for normal text. Body text is fine (#fafafa on #0d3d0f ≈ 15:1).
- **(P3)** Red text on dark green (var(--color-red) on var(--color-bg-dark))
  can be hard for red-green colorblind users. Consider adding underline or
  bold as redundant encoding.

---

## 4. Change Plan — File-Level Recommendations

### Priority 1 (High Impact)

| # | Change | Files | Effort |
|---|--------|-------|--------|
| 1a | Compass-rose AI hand layout (desktop) | `web/templates/partials/game_board.html`, `web/static/style.css` | Medium |
| 1b | Hide "Play card" button on mobile | `web/static/style.css` (media query only) | Small |
| 1c | Reduce mobile trick table height | `web/static/style.css` (media query) | Small |
| 1d | Compact AI hand display on mobile | `web/static/style.css`, `web/templates/partials/game_board.html` | Medium |

### Priority 2 (Moderate Impact)

| # | Change | Files | Effort |
|---|--------|-------|--------|
| 2a | Replace model `<select>` with radio cards | `web/templates/partials/model_select.html`, `web/static/style.css` | Medium |
| 2b | Improve trick-winner feedback visibility | `web/static/style.css` | Small |
| 2c | Contextual hand-result title color | `web/templates/partials/hand_result.html`, `web/static/style.css` | Small |
| 2d | Collapse action rail on mobile | `web/static/style.css`, possibly `web/templates/partials/action_rail.html` | Small |
| 2e | Move score bar above trick area on mobile | `web/static/style.css` (flex order) | Small |
| 2f | Seat marker icon improvements | `web/templates/partials/game_board.html`, `web/templates/partials/trick.html`, `web/static/style.css` | Medium |

### Priority 3 (Polish)

| # | Change | Files | Effort |
|---|--------|-------|--------|
| 3a | Landing page card/deck illustration | `web/static/` (new SVG), `web/templates/landing.html`, `web/static/style.css` | Medium |
| 3b | Nickname character limit hint | `web/templates/partials/nickname_form.html` | Tiny |
| 3c | Muted text contrast improvement | `web/static/style.css` (CSS var tweak) | Tiny |
| 3d | Colorblind-safe redundant encoding | `web/static/style.css` | Small |

---

## 5. Recommended PR Decomposition

These are ordered for safe serial execution — no cross-PR conflicts.

| PR | Scope | Items |
|----|-------|-------|
| PR-A | Mobile quick wins | 1b, 1c, 2d, 2e |
| PR-B | Compass-rose AI layout (desktop) | 1a |
| PR-C | Compact mobile AI hands | 1d |
| PR-D | Model select radio cards | 2a |
| PR-E | Feedback improvements | 2b, 2c, 2f |
| PR-F | Visual polish | 3a, 3b, 3c, 3d |

**PR-A** is the highest-ROI PR: pure CSS changes, no template modifications,
fixes the most pressing mobile usability issues.

---

## 6. Validation

### Screenshots captured
```
plans/sessions/ux_audit/desktop_01_landing.png
plans/sessions/ux_audit/desktop_02_invite_code_filled.png
plans/sessions/ux_audit/desktop_03_nickname_form.png
plans/sessions/ux_audit/desktop_04_model_select.png
plans/sessions/ux_audit/desktop_05_auction.png
plans/sessions/ux_audit/desktop_06_trick_play.png
plans/sessions/ux_audit/desktop_08_hand_result.png
plans/sessions/ux_audit/desktop_09_second_hand_start.png
plans/sessions/ux_audit/desktop_11_leaderboard.png
plans/sessions/ux_audit/mobile_01_landing.png
plans/sessions/ux_audit/mobile_02_invite_code_filled.png
plans/sessions/ux_audit/mobile_03_nickname_form.png
plans/sessions/ux_audit/mobile_04_model_select.png
plans/sessions/ux_audit/mobile_05_auction.png
plans/sessions/ux_audit/mobile_06_trick_play.png
plans/sessions/ux_audit/mobile_08_hand_result.png
plans/sessions/ux_audit/mobile_09_second_hand_start.png
plans/sessions/ux_audit/mobile_11_leaderboard.png
```

### Capture script
```
uv run python plans/sessions/ux_audit/capture_screenshots.py
```

### Post-implementation validation
After each PR, re-run the capture script and visually verify the changed
phases. Also run:
```bash
make browser-smoke    # Existing Playwright E2E tests
```
to confirm no functional regressions.
