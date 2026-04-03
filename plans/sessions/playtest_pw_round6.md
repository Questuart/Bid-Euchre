# Playwright Playtest Round 6 — Match End & Lifecycle

**Date:** 2026-04-03
**URL:** https://bideuchre-web.onrender.com
**Match:** Completed naturally (AI reached 52+)
**Final score:** You 16, AI 58, 11 hands

## Match End Screen

**Works correctly.** The match end displays:
- Red "You Lose" heading (h1 inside an alert role)
- Final score table: "Your team: 16" / "AI team: 58"
- "Hands played: 11"
- "Play Again" button
- Red border on the result card (visual emphasis for loss)

**Missing:** No hand-by-hand summary or detailed stats on the end screen. The player has to go to History/Leaderboard tabs separately to see detailed results.

## Post-Match Navigation

### Leaderboard (updated immediately)

| Stat | Before Match | After Match |
|------|-------------|------------|
| Claude-PW GP | 0 | 1 |
| Claude-PW HP | 5 | 11 |
| Claude-PW GW | 0 | 0 |
| Claude-PW EPPD | -4.400 | -3.818 |
| Claude-PW Mgn | 0.0 | -42.0 |
| Bud Bot GP | 16 | 31 |
| Bud Bot GW | 9 | 23 |
| Bud Bot EPPD | +1.272 | +1.517 |

**Grammar note:** Leaderboard correctly uses "0 games", "1 game", "23 games" — singular/plural handled properly here (unlike the card count alt text from #2205).

### History Tab (updated immediately)

Shows completed match entry:
- Opponent: Bud Bot
- Result: Loss
- Score: 16 – 58
- Hands: 11
- Date: Apr 3, 2026, 1:28 AM (uses `<time>` element — good semantic HTML)

### Play Again Flow

1. Click "Play Again" on match end screen
2. Goes to AI selection screen (same URL — `/play/<id>`)
3. Nickname preserved ("Welcome, Claude-PW!")
4. Can select Bud Bot or OLSa (Easy)
5. "Start Match" begins a fresh match

**Same URL reuse:** The game URL doesn't change between matches. This means the invite code gives persistent access to the game room, not a single match. Good for casual play.

## Full Match Lifecycle Verified

```
Homepage → Enter Code → Set Nickname → Select AI → Start Match
  → Auction → Trick Play → Hand Result → (repeat)
  → Match End ("You Lose" / score)
  → Play Again → Select AI → Start Match (new match)
  → Leaderboard updated ✓
  → History updated ✓
```

## New Bugs Found

None — match end, leaderboard update, history, and Play Again all work correctly. The only gap is the lack of a detailed hand-by-hand summary on the end screen, but this is a feature request rather than a bug.

## UX Suggestions (Not Bugs)

1. **Match end summary:** Show a collapsible hand-by-hand scoring summary on the end screen
2. **Win screen:** If the player wins, show a congratulatory green "You Win!" (not tested yet — would need to beat Bud Bot)
3. **Match stats:** Show EPPD change, tricks per hand chart, or other stats on the end screen
