# Desktop Gameplay Proving Report (1280x720)

**Date:** 2026-04-02
**Viewport:** 1280x720 (desktop)
**Invite Code:** MEEKSPILOT
**Server:** http://localhost:8000
**Tool:** Playwright MCP (automated browser)

## Summary

**Games completed (total on server):** 10 (5 prior + 5 during this session)
**Games with interactive card play:** 4 sessions attempted
**Interactive completion rate:** Low — games complete server-side via auto-play, but player
  has minimal agency due to 400 errors on card play and auto-advance state jumps
**Critical blocker:** Card play endpoint returns 400 Bad Request, making games unplayable without constant workarounds

> **Most interactive card-play attempts failed.** A P1 server-client state
> desynchronization bug causes the `/play-card` endpoint to return 400 errors,
> blocking card play in most trick-play situations. Of the 4 interactive
> sessions attempted, none could be played through without repeated 400 errors.
> The bug reproduces consistently across games, opponents, and card types.
> See P1-001 below.

## Issues Found

### P1 — Critical (Game-Breaking)

#### P1-001: Card play returns 400 Bad Request — server-client state desync

**Severity:** P1 (game-breaking, blocks normal play)
**Frequency:** ~70% of card play attempts
**Repro steps:**
1. Enter game via invite code MEEKSPILOT
2. Start a match with any AI opponent
3. Click "Next" to advance through auction/auto-played tricks
4. When it's your turn to play a card, click a playable card button
5. Observe: 400 Bad Request on `POST /play/{uuid}/play-card`

**Console errors:**
```
Failed to load resource: the server responded with a status of 400 (Bad Request)
  @ http://localhost:8000/play/{uuid}/play-card
Response Status Error Code 400 from /play/{uuid}/play-card
  @ https://unpkg.com/htmx.org@1.9.12
```

**Root cause analysis (from `web/routes.py` lines 1100-1118):**
The `submit_card()` endpoint validates three conditions before accepting a card play:
1. `hand.phase == "trick_play"` — phase check
2. `hand.current_seat == HUMAN_SEAT` — turn check
3. `not _awaiting_next(hand)` — reveal state check

The most likely failing check is #3: `_awaiting_next(hand)` returns True when
`hand.paused_after_trick` is True. The server's auto-play mechanism advances
through AI tricks and sets `paused_after_trick=True` for each completed trick,
but the rendered HTML shows the player's turn to play cards — not a "Next" button.

The render logic and the validation logic disagree on whether the game is in a
"paused" or "active play" state.

**Impact:** Players cannot complete games normally. The only workaround is to
reload the page after every successful card play, which is not viable UX.

**Screenshots:**
- `gameplay_screenshots/game01_error_400_play_card.png` — error toast during play
- `gameplay_screenshots/game01_game_not_found.png` — eventual 404 after repeated errors

---

#### P1-002: Game state jumps — multiple hands skip without player visibility

**Severity:** P1 (loss of player agency)
**Frequency:** Every game, every "Next" click
**Repro steps:**
1. During trick play, click "Next" to advance
2. Observe: game jumps forward by 2-6 hands at a time
3. Player never sees their cards for bidding or gets to play cards in skipped hands

**Examples observed:**
- Game 1: Hand 1 Trick 5 (score 0-0) → Hand 7 Trick 6 (score 26-34) — 6 hands skipped
- Game 2: Hand 1 result → Hand 3 Trick 8 (via one "Next Hand" click)
- Game 2: Hand 3 → Hand 6 Trick 7 (via one "Next" click)
- Game 2: Hand 6 → Hand 8 Trick 9 (via one card play + auto-advance)

**Impact:** The player has no visibility into most of the match. They're a
spectator for ~80% of the hands, only occasionally getting to play 1-2 cards
before another state jump.

---

#### P1-003: Game session loss after 400 errors — "Game not found" (404)

**Severity:** P1 (data loss)
**Frequency:** Observed in Game 1 after multiple 400 errors
**Repro steps:**
1. Encounter a 400 error on card play
2. Click "Play card" button to retry
3. Observe: 404 Not Found — "Game not found. It may have expired."

**Console errors:**
```
Failed to load resource: the server responded with a status of 404 (Not Found)
  @ http://localhost:8000/play/{uuid}/play-card
```

**Impact:** The entire game session is lost mid-match. The match continues on
the server (verified: re-entering the invite code shows "You Lose" with a final
score), but the player loses all interactive control.

---

### P2 — Major (Functional Issues)

#### P2-001: Bid value off-by-one — selected level differs from submitted bid

**Severity:** P2
**Frequency:** Observed once (Game 1)
**Repro steps:**
1. In the auction form, select bid level "6" from the dropdown
2. Select contract "Spades"
3. Click "Submit Bid"
4. Observe: Action rail shows "You bid 5 S" (not 6)

**Note:** This may be an artifact of Playwright's `selectOption` interaction
vs. the HTML option values. Needs manual verification. If the option `value`
attributes are 0-indexed while labels are 1-indexed, this is a real bug.

---

#### P2-002: Player never gets to bid in most hands

**Severity:** P2
**Frequency:** ~80% of hands
**Details:** The "Next" button auto-resolves the entire auction without giving
the player a chance to bid. The player only sees the bid form in the first
hand of the first game. In all subsequent interactions, clicking "Next"
advances through the auction and auto-passes for the player.

**Expected:** Player should always see their hand and get a bidding opportunity
on every hand where they could bid.

---

#### P2-003: Tied score (55-55) displayed as "Loss" in match history

**Severity:** P2
**Frequency:** Observed once
**Details:** Match history shows a game with score 55-55 marked as "Loss".
When both teams exceed the ±52 threshold in the same hand, the result
depends on the stored `Match.won` boolean. The history template renders
`"Win" if match.won else "Loss"` with no draw state — a 55-55 tie is
stored as `won=False` (the declaring team that pushed the score over
threshold is the winner, so the human's team lost).

**Root cause:** The `Match.won` boolean and history template lack nuance
for close finishes. While RULES.md §6.6 says the declaring team wins when
both teams cross ±52 in the same hand, the display is misleading: a 55-55
result shown as plain "Loss" gives the player no indication that it was a
near-tie decided by the declaring-team rule. The history template should
either show the final score alongside the outcome or add a qualifier
(e.g., "Loss — declaring team wins at 55-55") so the result is not
confusing.

**Screenshot:** `gameplay_screenshots/history_10_games.png` (row 1)

---

#### P2-004: Bid silently rejected — player auto-passed without feedback

**Severity:** P2
**Frequency:** Observed once
**Details:** After submitting a 5♦ bid via the auction form, the response
rendered a new game state where "Your bid: Pass" was shown. The submitted
bid was silently discarded with no error message. This occurred because the
match ended server-side while the client was still showing the auction form
for a previous hand — another manifestation of the state desync (P1-001).

**Impact:** Players lose bidding agency with no feedback about why.

---

#### P2-005: Match result screen skipped — new match starts without showing outcome

**Severity:** P2
**Frequency:** Observed once
**Details:** After playing a card that caused the match to end (score reached ±52),
the HTMX response rendered the next game's trick-play state instead of the
match result ("You Win"/"You Lose") screen. The player has no visibility into
the final match outcome.

---

### P3 — Minor (UX Polish)

#### P3-001: Content below fold at 1280x720

**Severity:** P3
**Details:** At the specified desktop viewport (1280x720), the player's hand
cards and the score bar are partially below the visible area. Players must
scroll to see their full hand during the auction phase.

**Recommendation:** Reduce vertical spacing or use a more compact layout to
ensure the full game board fits within 720px viewport height.

**Screenshot:** `gameplay_screenshots/game01_auction.png`

---

#### P3-002: Deprecated `apple-mobile-web-app-capable` meta tag

**Severity:** P3
**Console warning:**
```
<meta name="apple-mobile-web-app-capable" content="yes"> is deprecated.
Please include <meta name="mobile-web-app-capable" content="yes"> instead.
```
**Impact:** No functional impact, but produces console warnings on every page load.

---

#### ~~P3-003: No per-game nickname or opponent selection on first entry~~ (FALSE POSITIVE)

**Severity:** ~~P3~~ False positive
**Frequency:** Every first entry via invite code
**Details:** The first time entering via invite code, the game starts directly
without showing the opponent selection screen. The "Welcome, Meeks!" opponent
selection dialog only appears after clicking "Play Again" at the end of a match.
The nickname ("Meeks") is derived from the invite code, not player input.

**Root cause:** The invite code flow creates the player record with a nickname
derived from the code, then redirects straight to a new match with the default
opponent. The opponent selection screen only appears on the welcome/rematch
page, not during initial invite code entry.
First-entry flow is: invite code → player created → default opponent → play
(opponent selection is skipped).

**False positive rationale:** This is intentional design, not a bug. The
first-entry flow deliberately starts the player with the default opponent to
minimize friction. The nickname is auto-generated from the invite code as a
feature, not a defect. Opponent selection is available on subsequent games.

---

### Info — Observations (No Action Required)

#### INFO-001: History page works correctly
The match history table displays completed matches with opponent, result, score,
hands played, and date. Layout is clean at 1280x720.

#### INFO-002: Leaderboard page works correctly
Rankings display correctly with Net EPPD, win rate, and match counts. The
"Show More Stats" and "What do these stats mean?" expandable sections both
function properly and content is well-written.

#### INFO-003: Game board visual design is solid
The card table layout, trick display, bid badges, dealer/declarer indicators,
and color-coded suits are all well-designed and visually clear at desktop
resolution.

#### INFO-004: Help section (Bid Euchre Rules) accessible
The collapsible rules help section is present on every game page via the
"Help: Bid Euchre Rules" disclosure widget.

---

## Workaround for P1-001

During testing, the following workaround was discovered:
1. **Full page reload** (`Ctrl+R` or navigate to the game URL) sometimes
   provides a fresh server state where the first card play succeeds
2. However, subsequent card plays in the same page session often fail again
3. This is not a viable user workaround — it breaks game flow entirely

## Recommended Fix Priority

1. **P1-001 (card play 400):** Investigate the `_awaiting_next()` check in
   `web/routes.py`. The `paused_after_trick` flag and the `render_game_board`
   logic must agree on whether to show a "Next" button or card play buttons.
   The auto-advance mechanism likely needs to clear `paused_after_trick` before
   rendering the trick-play state.

2. **P1-002 (state jumps):** The "Next" button's HTMX handler should only
   advance one step at a time, not auto-resolve entire hands. Each auction
   bid, each trick, and each hand result should be a separate reveal step.

3. **P1-003 (session loss):** Add error recovery — if the play-card endpoint
   returns 400, the client should reload the game board state rather than
   showing a generic error toast and leaving the player stuck.

4. **P2-001 (bid off-by-one):** Verify option values in the bid dropdown match
   the displayed labels.

5. **P2-002 (no bidding opportunity):** Ensure auto-advance pauses when it
   reaches the player's bidding turn.

## Screenshots Index

| File | Description |
|------|-------------|
| `game01_landing.png` | Landing page — clean, well-designed |
| `game01_auction.png` | Auction phase — hand partially below fold |
| `game01_error_400_play_card.png` | 400 error on card play attempt |
| `game01_state_jump.png` | After state jump — Hand 7 from Hand 1 |
| `game01_game_not_found.png` | 404 "Game not found" error |
| `game01_result.png` | Match result — "You Lose" 44-56 |
| `game02_opponent_select.png` | Opponent selection screen (Play Again flow) |
| `game02_hand_result.png` | Hand result panel — "Made it!" |
| `history_page.png` | Match History table |
| `leaderboard_page.png` | Leaderboard rankings |
| `leaderboard_stats_help.png` | Leaderboard with stats help expanded |
| `history_10_games.png` | 10 completed matches — 55-55 tie shown as "Loss" |

## Test Environment

- **Browser:** Chromium (Playwright headless)
- **Viewport:** 1280x720
- **Server:** FastAPI dev server at localhost:8000
- **AI Models tested:** Bud Bot, OLSa (Easy) (via history; only Bud Bot interactively)
- **Invite code:** MEEKSPILOT (maps to player "Meeks")
