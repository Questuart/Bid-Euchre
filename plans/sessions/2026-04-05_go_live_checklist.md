# Go-Live Proving Checklist — Browser Game (2026-04-05)

> **Purpose:** Comprehensive manual proving run for the browser game before
> go-live. Builds upon #2320 (Waves 3–5 checklist) by adding all changes
> merged since that checklist was written, all open issues expected before
> go-live, and deeper edge-case / regression coverage.
>
> **Relationship to #2320:** That checklist covers ~22 PRs through Wave 5.
> This checklist covers the **delta** — everything that changed after #2320
> was written, plus gaps in #2320's coverage. Items from #2320 that are
> unchanged are NOT duplicated here; run #2320 first, then this checklist.
>
> **Time estimate:** 45–60 minutes (3–4 full matches plus targeted edge-case
> probing)
>
> **Prerequisites:**
> - Access to the deployed browser game (Render or local Docker)
> - Fresh browser / incognito window (for onboarding tests)
> - Mobile device or responsive dev tools (for viewport tests)
> - A second browser session (for leaderboard multi-player verification)

---

## How to Use This Checklist

1. **Run #2320 first** — that covers the foundational features
2. **Then run this checklist** — focuses on post-#2320 changes and gaps
3. **Mark conditional items** — sections marked `[IF MERGED]` should be
   tested only if the referenced issue/PR has been implemented
4. **Record failures** — note the exact step, screenshot, and browser/device

---

## Section A — Post-#2320 Merged Changes (Wave 9+)

These PRs merged after #2320 was written. They were listed as "verify after
merge" in #2320 but need explicit proving steps.

### A1. Hand Sorting — Alternating Red/Black Suits (#2326)

- [ ] **A1a.** During a suit contract, verify your hand is sorted with
  **alternating suit colors**: black suit → red suit → black suit → red suit
  (e.g., ♠ → ♥ → ♣ → ♦)
- [ ] **A1b.** Verify **trump suit appears first** in the sort order, with
  remaining suits alternating starting from the opposite color
- [ ] **A1c.** During a HIGH or LOW contract (no trump), verify suits still
  alternate red/black in a fixed order
- [ ] **A1d.** Verify **left bower sorts with the trump group**, not with its
  printed suit
- [ ] **A1e.** Play multiple hands with different trump suits — verify the
  sort order adapts correctly each time

### A2. Bid Selector Default (#2327)

- [ ] **A2a.** Start a fresh auction. Verify the bid dropdown **defaults to
  the minimum legal bid** (e.g., "1" at the start of the auction), NOT "Pass"
- [ ] **A2b.** After another player bids (e.g., 7), verify your dropdown
  **defaults to the next legal bid** (e.g., 8), not pass
- [ ] **A2c.** When all bids up to 10 are taken, verify the dropdown defaults
  to **Pass** (since no higher bid is possible)
- [ ] **A2d.** Verify you can still **manually select Pass** at any point
  even when the default is a numeric bid

### A3. Suit Icon Colors — Clubs/Spades Fix (#2335)

- [ ] **A3a.** In your hand, verify **clubs (♣) and spades (♠)** suit icons
  are rendered in **dark/black**, not white-on-dark
- [ ] **A3b.** Verify clubs/spades icons have a subtle **outline/shadow** for
  visibility on the dark felt background
- [ ] **A3c.** Verify **hearts (♥) and diamonds (♦)** remain red
- [ ] **A3d.** Check suit icons in **all locations**: hand cards, trick area,
  auction log, trick history, leaderboard tooltips

### A4. Collapsible Auction Log (#2314) — Upgrade from #2320 §3f

#2320 had this as conditional. Now merged — full proving:

- [ ] **A4a.** During auction, verify the auction log is **open by default**
  and positioned **center-screen** (inside compass area)
- [ ] **A4b.** Click the collapse toggle — verify it closes smoothly
- [ ] **A4c.** Click again — verify it reopens
- [ ] **A4d.** After auction ends and gameplay begins, verify the auction log
  **auto-collapses**
- [ ] **A4e.** During gameplay, manually expand the collapsed auction log —
  verify you can still read the full auction history
- [ ] **A4f.** Verify the collapse/expand control has a visible affordance
  (triangle/arrow indicator)

### A5. "Leader" Label + RB/LB Legend (#2315) — Upgrade from #2320 §5c/5d

- [ ] **A5a.** During trick play, verify the **"Leader"** label appears on
  the seat of the player who led the trick (not "Lead Trick")
- [ ] **A5b.** In trick history for a suit contract, verify an **RB/LB
  abbreviation legend** appears explaining "RB = Right Bower",
  "LB = Left Bower"
- [ ] **A5c.** Verify the legend only appears in **suit contracts** (not
  HIGH/LOW where there are no bowers)

### A6. "Your Team / Opponent" Labels + Help/Guide Tab (#2316) — Upgrade from #2320 §2b/9a/13e

- [ ] **A6a.** Verify the score bar shows **"Your Team: X"** and
  **"Opponent: Y"** (not "You:" / "AI:")
- [ ] **A6b.** On the model select screen, verify the **quick-start guide
  banner is removed** (Help/Guide tab replaces it)
- [ ] **A6c.** Verify the tab is labeled **"Help / Guide"** (not just "Guide")
- [ ] **A6d.** Click the Help/Guide tab — verify it loads the guide content
  via HTMX partial swap

### A7. Blue AI Player Names (#2319) — Upgrade from #2320 §9e

- [ ] **A7a.** During gameplay, verify AI player names (Slim, Ace, Deuce or
  equivalent) appear in **blue (#64b5f6)**
- [ ] **A7b.** Verify the **human player name** (seat 0) is NOT blue
- [ ] **A7c.** Check blue AI names in **all locations**: compass seats, trick
  history, hand result screen, auction log, leaderboard

---

## Section B — Open Issues Expected Before Go-Live

These issues are OPEN at time of writing. Test only after they are
implemented and merged. Mark N/A if not merged by proving time.

### B1. Auction Log Repositioning During Gameplay (#2331) `[IF MERGED]`

- [ ] **B1a.** During auction phase, verify auction log is in its normal
  position (center-screen per #2314)
- [ ] **B1b.** After auction ends and gameplay begins, verify the auction log
  **moves below the hand details pane** (beneath the gameplay board)
- [ ] **B1c.** Verify the relocated auction log is still **expandable** and
  readable

### B2. Hide Contract/Trump During Auction (#2328) `[IF MERGED]`

- [ ] **B2a.** During the auction phase, verify the **"Current Contract and
  Trump"** bar is **hidden** or shows no contract info
- [ ] **B2b.** After the auction ends and a contract is set, verify the
  contract/trump bar **appears** with correct info
- [ ] **B2c.** Verify the transition is clean — no flash of stale contract
  info during auction

### B3. Skip Button Removal (#2332) `[IF MERGED]`

- [ ] **B3a.** During per-card reveal pacing, verify **only the "Next" button
  is visible** — no "Skip" button
- [ ] **B3b.** Verify "Next" advances through all AI card reveals one at a
  time
- [ ] **B3c.** After removing Skip, verify the last AI card + trick
  completion still works correctly (no stuck state)

### B4. AI Card Delay + Next After Human Plays (#2330) `[IF MERGED]`

- [ ] **B4a.** When AI plays a card, verify there is a visible **thinking
  delay** before the card appears (the card doesn't appear instantly)
- [ ] **B4b.** After the human player plays a card, verify the **card appears
  on the trick area** and a **"Next" button** appears — the game does NOT
  auto-advance
- [ ] **B4c.** Click "Next" — verify the next AI player then plays (with
  thinking delay per B4a)
- [ ] **B4d.** Verify the overall flow feels natural:
  Human plays → sees card → clicks Next → AI "thinks" → AI card appears →
  Next → repeat
- [ ] **B4e.** Verify trick completion still works: after the 4th card, the
  trick result should be shown with a Next button to continue

---

## Section C — High-Churn Features (Regression Risk)

These features have been modified by 3+ PRs and are most likely to have
regressions from interaction effects.

### C1. Pacing System (HIGH CHURN: #2231, #2294, #2330, #2332)

The pacing system has been changed by at least 4 PRs. Full lifecycle test:

- [ ] **C1a.** Human leads a trick → card appears → **Next** button shown →
  click Next → AI card appears (with delay if #2330 merged) →
  Next → repeat until trick complete
- [ ] **C1b.** AI leads a trick → AI card appears (with delay) → Next →
  repeat for each AI → human turn: legal cards highlighted, play one →
  card appears → Next → remaining AI plays (if any) → trick resolves
- [ ] **C1c.** After trick completes, verify **"Continue to the next trick"**
  message and Next button appear
- [ ] **C1d.** Verify **no auto-advance** anywhere — every transition requires
  a Next click
- [ ] **C1e.** Play 3+ full hands — verify pacing doesn't break or get stuck
  on any trick/hand boundary
- [ ] **C1f.** If Skip button is still present (i.e., #2332 NOT merged):
  verify Skip fast-forwards correctly and doesn't leave orphaned state

### C2. Bower Display (HIGH CHURN: #2234, #2274, #2298, #2315)

Bowers have been reworked 4+ times across display, sorting, and labeling:

- [ ] **C2a.** In a suit contract, locate the **right bower** (J of trump) in
  your hand. Verify it shows:
  - Original printed suit icon (J♠ not J♥ if trump is hearts)
  - **"RB"** badge
  - Correct trump-group sort position
- [ ] **C2b.** Locate the **left bower** (J of same color as trump). Verify:
  - Original printed suit icon
  - **"LB"** badge
  - Sorts with the trump group (not with its printed suit)
- [ ] **C2c.** Play a bower card — verify it appears correctly in the
  **trick area** with original suit + badge
- [ ] **C2d.** After the trick, verify the bower appears correctly in the
  **trick history table** with rank in white and suit icon colored
- [ ] **C2e.** In a HIGH or LOW contract, verify J cards appear as normal
  jacks with **no RB/LB badges** and **no bower sorting**

### C3. Score Display (HIGH CHURN: #2240, #2270, #2280, #2316)

Score bar and labels reworked across 4 PRs:

- [ ] **C3a.** Score bar shows: **"Your Team: X | Opponent: Y"**
- [ ] **C3b.** Contract info shows: **"Current Contract and Trump: N♣ by
  [declarer]"** with colored suit icon
- [ ] **C3c.** Trick counts are **team-colored**: green for human team,
  blue for AI team
- [ ] **C3d.** Hand details are behind a **collapsible dropdown** (not always
  visible)
- [ ] **C3e.** After a hand ends, verify the hand result uses
  **positive/negative styling** (green positive, red negative)

### C4. Leaderboard (HIGH CHURN: #2191, #2240, #2270, #2308)

- [ ] **C4a.** Column headers are **abbreviated**: GP, HP, GW, W%, Net PPD,
  PPD
- [ ] **C4b.** **Glossary** below the table explains each abbreviation
- [ ] **C4c.** **Net PPD** (formerly EPPD) and **PPD** are separate columns
- [ ] **C4d.** Current player row is **highlighted**
- [ ] **C4e.** **Abandoned match hands** are included in stats (play a game,
  abandon it by starting a new one, verify the hands still count)

### C5. Auction Log (HIGH CHURN: #2243, #2280, #2314, #2331)

- [ ] **C5a.** During auction: log is visible, open by default, center-screen
- [ ] **C5b.** Log entries show colored suit icons
- [ ] **C5c.** After page refresh during auction, log entries **persist**
- [ ] **C5d.** After auction ends, log auto-collapses
- [ ] **C5e.** If #2331 merged: log repositions below hand details during
  gameplay

---

## Section D — Full Game Lifecycle (End-to-End)

Play a complete match (first to 52 or -52) and verify every transition.

### D1. Match Creation

- [ ] **D1a.** Select AI model on model select screen — verify match starts
  cleanly
- [ ] **D1b.** Verify the URL updates to `/play/<link_uuid>`

### D2. Auction Phase

- [ ] **D2a.** Dealer label appears on the correct seat
- [ ] **D2b.** Bid dropdown defaults to next legal bid (not Pass)
- [ ] **D2c.** Contract/trump bar is hidden during auction (if #2328 merged)
- [ ] **D2d.** All four players bid in correct order
- [ ] **D2e.** Auction log records all bids with suit icons

### D3. Auction-to-Play Transition

- [ ] **D3a.** "Auction complete" interstitial appears
- [ ] **D3b.** No trick plays visible until dismissed
- [ ] **D3c.** Contract/trump bar appears after transition
- [ ] **D3d.** Auction log auto-collapses

### D4. Trick Play (Multiple Hands)

- [ ] **D4a.** Play at least 5 complete hands
- [ ] **D4b.** Verify each hand's trick count totals to 10
- [ ] **D4c.** Verify hand scores are correctly calculated and applied
- [ ] **D4d.** Verify the score bar updates after each hand

### D5. Hand Result

- [ ] **D5a.** After each hand, verify hand result screen appears
- [ ] **D5b.** Shows trick log with per-trick winners
- [ ] **D5c.** Shows scoring breakdown with positive/negative styling

### D6. Match End

- [ ] **D6a.** When a team reaches 52 or -52, verify the **final hand
  result** appears first
- [ ] **D6b.** "See Match Results" button appears after the hand result
- [ ] **D6c.** Match-over screen shows final scores and win/loss status
- [ ] **D6d.** Verify the match is recorded (check History tab)
- [ ] **D6e.** Return to model select — verify you can start a new match
  immediately

---

## Section E — Moon/Loner Edge Cases

### E1. Moon Bid

- [ ] **E1a.** If a Moon bid is made (by any player), verify the **Moon
  exchange UI** appears for the declarer
- [ ] **E1b.** During exchange, verify bower cards show original suit +
  RB/LB badges
- [ ] **E1c.** Exchange works: select cards, confirm, hand updates correctly
- [ ] **E1d.** After exchange, trick play uses **3 players** (declarer's
  partner sits out)
- [ ] **E1e.** Verify scoring: declarer's team gets all tricks if made,
  penalty if set

### E2. Loner Bid

- [ ] **E2a.** If a Loner bid is made, verify the same flow as Moon but
  with loner-specific behavior
- [ ] **E2b.** Verify tooltips say **"your team"** not "you personally"

### E3. All-Pass Redeal

- [ ] **E3a.** If all 4 players pass in the auction, verify the hand is
  **redealt** — no stuck state
- [ ] **E3b.** Verify the redeal does not corrupt the hand counter or score

### E4. Set Scoring

- [ ] **E4a.** Engineer a situation where the declaring team fails to make
  their bid (gets set)
- [ ] **E4b.** Verify the declaring team receives **negative bid value**
  (not negative tricks)
- [ ] **E4c.** Verify the defending team receives their **tricks won**
  (positive)
- [ ] **E4d.** Verify the score bar reflects both teams' scores correctly

---

## Section F — Error Recovery & Resilience

### F1. Page Refresh Mid-Game

- [ ] **F1a.** During the auction phase: refresh the page. Verify the
  auction resumes correctly with all prior bids visible
- [ ] **F1b.** During trick play: refresh the page. Verify:
  - Current trick state is preserved
  - Score is correct
  - Hand sort is correct
  - It's the correct player's turn
- [ ] **F1c.** During the hand result screen: refresh. Verify the result
  is still visible
- [ ] **F1d.** Refresh on the match-over screen: verify match status persists

### F2. Stale Match Cleanup

- [ ] **F2a.** Start a match, close the browser tab mid-game
- [ ] **F2b.** Open the game in a new tab
- [ ] **F2c.** Start a new match — verify you're **not blocked** by the
  orphaned match
- [ ] **F2d.** Check leaderboard — hands from the abandoned match should
  appear in your stats

### F3. Double-Click / Race Conditions

- [ ] **F3a.** Double-click a card play quickly — verify you get a
  **409 Conflict** with the correct board state (not a duplicate play)
- [ ] **F3b.** Double-click a bid submission — verify only one bid is
  recorded
- [ ] **F3c.** Double-click the "Next" button — verify no skipped reveals
  or broken state

### F4. HTMX Timeout Recovery

- [ ] **F4a.** (If testable) Slow your connection or simulate latency.
  Verify an HTMX timeout toast appears after ~15 seconds
- [ ] **F4b.** After timeout, verify the form is reset and you can retry

### F5. Illegal Move Handling

- [ ] **F5a.** If possible, attempt an **illegal card** (card not in hand
  or not following suit). Verify you get an inline error banner, not a
  blank page or JSON
- [ ] **F5b.** Verify the error banner **auto-fades** after ~5 seconds
- [ ] **F5c.** Verify you can play a legal card after the error

---

## Section G — UI / UX Polish

### G1. Tab Navigation

- [ ] **G1a.** Click each tab (Game, History, Leaderboard, Comments,
  Help/Guide). Verify **HTMX partial swap** — no full page reload, URL
  updates
- [ ] **G1b.** Use **browser back/forward** — verify tabs switch correctly
  via popstate
- [ ] **G1c.** While on the Game tab during active play, switch to History
  and back — verify **game state is preserved**

### G2. Card Display Consistency

- [ ] **G2a.** Verify **"10"** is displayed (not "T") for ten cards in all
  locations: hand, trick area, trick history, hand result
- [ ] **G2b.** Verify duplicate cards (double-deck) have **copy index** in
  aria-labels: "A of Spades (1)" vs "(2)"
- [ ] **G2c.** Verify **card count grammar**: "1 card" (singular) and
  "3 cards" (plural) wherever counts are shown

### G3. Color Consistency

- [ ] **G3a.** Hearts/diamonds: red suit icons everywhere
- [ ] **G3b.** Clubs/spades: black/dark suit icons with shadow for visibility
- [ ] **G3c.** AI names: blue (#64b5f6)
- [ ] **G3d.** Human team score elements: green
- [ ] **G3e.** AI team score elements: blue
- [ ] **G3f.** Rank text (A, K, Q, J, 10): white in all card displays

---

## Section H — Mobile & Accessibility

### H1. Mobile Viewport

- [ ] **H1a.** On a mobile device (or Chrome DevTools responsive mode at
  375px width): verify **no horizontal scrollbar** appears
- [ ] **H1b.** All tabs are **reachable** — tabs should wrap or be scrollable
- [ ] **H1c.** Card play buttons are **large enough to tap** without
  accidental misclicks
- [ ] **H1d.** Auction bid dropdown is **usable on touch** — opens native
  select picker

### H2. Zoom / Large Text

- [ ] **H2a.** Zoom to **200%** in desktop browser. Verify layout still
  works: no overlapping elements, all controls reachable
- [ ] **H2b.** Zoom to **150%** — verify the game board doesn't break

### H3. Screen Reader / Accessibility

- [ ] **H3a.** Verify card elements have meaningful **aria-labels** including
  suit, rank, and copy index
- [ ] **H3b.** Verify Next/Skip buttons have descriptive labels
- [ ] **H3c.** Verify the auction log is semantically structured (not just
  visual)

---

## Section I — Leaderboard, History, Comments

### I1. Match History

- [ ] **I1a.** After completing a match, open the History tab. Verify the
  match appears with correct timestamp, result, and score
- [ ] **I1b.** Verify timestamps are in **local timezone** (not UTC)
- [ ] **I1c.** Play multiple matches — verify they appear in reverse
  chronological order

### I2. Comments

- [ ] **I2a.** Open the Comments tab. Verify it loads without error
- [ ] **I2b.** If comment functionality exists: post a comment, verify it
  appears

### I3. Leaderboard Multi-Player

- [ ] **I3a.** Open the game in a **second browser** with a different player
  identity
- [ ] **I3b.** Play some matches in both browsers
- [ ] **I3c.** Verify both players appear on the leaderboard with correct
  stats

---

## Section J — Onboarding (Fresh Player Experience)

These extend #2320 §1 with deeper verification.

### J1. Complete Onboarding Flow

- [ ] **J1a.** Fresh incognito window → verify **welcome letter** appears
  (not model select)
- [ ] **J1b.** Step through all **3 walkthrough steps** — verify content is
  meaningful and well-formatted
- [ ] **J1c.** After step 3, verify landing on **model select** screen
- [ ] **J1d.** Open another incognito window → verify **"Skip"** button on
  welcome screen jumps to model select
- [ ] **J1e.** After completing onboarding, close and reopen browser →
  verify onboarding does **not** appear again
- [ ] **J1f.** Start a match after onboarding — verify the transition is
  clean (no flash of wrong screen)

---

## Test Priority Matrix

If time is limited, run items in this priority order:

| Priority | Section | Why |
|----------|---------|-----|
| P0 — Must | D (Full lifecycle) | Core game functionality |
| P0 — Must | C1 (Pacing) | Highest churn, most interaction risk |
| P0 — Must | E1-E4 (Moon/Set) | Complex edge cases rarely tested |
| P1 — Should | A1-A7 (New changes) | Post-#2320 changes never proven |
| P1 — Should | F1-F3 (Error recovery) | Resilience for real users |
| P1 — Should | C2-C5 (High churn) | Regression risk from interactions |
| P2 — Nice | B1-B4 (Open issues) | Only if merged; fresh code |
| P2 — Nice | G (UI polish) | Visual consistency |
| P2 — Nice | H (Mobile) | Platform coverage |
| P3 — If time | I (History/Comments) | Lower risk |
| P3 — If time | J (Onboarding) | Covered in #2320 |

---

## Outcome

_To be filled after the proving run with pass/fail results, discovered bugs,
and follow-up issue numbers._
