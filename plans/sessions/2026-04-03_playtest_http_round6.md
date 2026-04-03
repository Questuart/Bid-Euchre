# HTTP Playtest Round 6: /new-match Flow & Leaderboard Verification

**Date:** 2026-04-03
**Target:** https://bideuchre-web.onrender.com
**Method:** Direct HTTP (curl)
**Invite code:** 2BMOY9MU (existing player, Claude-HTTP)
**AI opponent:** Bud Bot (hard)
**Focus:** `/new-match` endpoint, leaderboard accuracy, history page, auxiliary endpoints

## Summary

Tested the full post-match → new-match → play → leaderboard pipeline.
Verified leaderboard stats update correctly after match completion.
Tested auxiliary endpoints (/guide, /comments, /history, /leaderboard)
with both valid and invalid UUIDs.

**Result:** AI wins 52-27 after 9 hands.
**Bugs found:** 0

## /new-match Endpoint Tests

### Test 1: POST /new-match from match-result page

- **Request:** `POST /play/{uuid}/new-match`
- **Response:** HTML partial with model-select form (bud_bot + olsa)
- **Status:** 200 OK
- **Content:** Shows "Welcome, Claude-HTTP!" greeting, two model radio
  cards, "Start Match" button
- **Verdict:** Works correctly

### Test 2: Double /new-match (idempotency)

- Sent `POST /new-match` twice in succession
- Second call returned the same model-select form
- No duplicate matches created, no errors
- **Verdict:** Idempotent. Safe against double-click.

### Test 3: /new-match → select-ai → game start

- After `/new-match`, sent `POST /select-ai` with `model_id=bud_bot`
- Response: game board HTML with first hand in auction reveal (NEXT state)
- Match started correctly
- **Verdict:** Full flow works end-to-end

### Test 4: /new-match from fresh completion

- After playing the match to completion, landed on match-result page
- `POST /new-match` returned model-select form with both AI options
- "Welcome, Claude-HTTP!" greeting preserved
- **Verdict:** Works from both stale and fresh match-result pages

## Leaderboard Verification

### Pre-Match State

```
#7 Claude-HTTP  EPPD=-2.643  GP=10  HP=98  W=1  W%=10%  Mgn=-25.9  Make%=70%  AvgB=5.6
```

### Post-Match State

```
#7 Claude-HTTP  EPPD=-2.654  GP=11  HP=107  W=1  W%=9%  Mgn=-25.8  Make%=71%  AvgB=5.5
```

### Delta Analysis

| Metric | Pre | Post | Delta | Expected | Correct? |
|--------|-----|------|-------|----------|----------|
| Games Played (GP) | 10 | 11 | +1 | +1 | Yes |
| Hands Played (HP) | 98 | 107 | +9 | +9 (match had 9 hands) | Yes |
| Game Wins (GW) | 1 | 1 | 0 | 0 (we lost) | Yes |
| Win % (W%) | 10% | 9% | -1pp | 1/11=9.1% | Yes |
| EPPD | -2.643 | -2.654 | -0.011 | Slightly worse (loss) | Yes |
| Margin (Mgn) | -25.9 | -25.8 | +0.1 | Close loss (27-52=-25) brings avg up slightly | Plausible |
| Make % | 70% | 71% | +1pp | Improvement this match | Yes |
| Avg Bid | 5.6 | 5.5 | -0.1 | Slightly lower | Plausible |

**All leaderboard stats updated correctly after the match.**

### Leaderboard Column Definitions (from UI headers)

| Abbrev | Full Name | Description |
|--------|-----------|-------------|
| EPPD | Excess Points Per Deal | Key performance metric |
| GP | Games Played | Completed matches |
| HP | Hands Played | Total hands across all matches |
| GW | Game Wins | Matches won |
| W% | Win % | GW/GP |
| Mgn | Margin | Average score margin (negative = losing) |
| WMgn | Win Margin | Average margin in wins only |
| Bid% | Bid % | Percentage of hands where player bid |
| Make% | Make % | Percentage of bids successfully made |
| AvgB | Average Bid | Mean bid amount |
| Moon% | Moon % | Percentage of bids that were moon |
| M.Make | Moon Make | Moon make rate |
| Loner% | Loner % | Percentage of bids that were loner |
| L.Make | Loner Make | Loner make rate |

### Other Players on Leaderboard

| # | Player | EPPD | GP | W% | Notes |
|---|--------|------|----|----|-------|
| 1 | Marg | +2.000 | 0 | 0% | 3 hands only |
| 2 | Olive Juice | +1.500 | 0 | 0% | 4 hands only |
| 3 | **Bud Bot** (AI) | +1.442 | 27 | 70% | Most games played |
| 4 | Meeks | +1.111 | 10 | 70% | Top human player |
| 5 | OLSa (Easy) AI | -1.714 | 0 | 0% | 7 hands only |
| 6 | TEST | -1.824 | 1 | 0% | Test account |
| 7 | **Claude-HTTP** | -2.654 | 11 | 9% | This playtest bot |
| 8 | CLAUDE | -2.800 | 1 | 0% | Different Claude test |
| 9 | Claude-HYB | -3.200 | 4 | 0% | Hybrid Claude test |
| 10 | Claude-PW | -3.818 | 1 | 0% | Playwright Claude test |
| 11 | Pete | -8.333 | 0 | 0% | 3 hands only |

**Observation:** AI players (Bud Bot, OLSa) appear on the leaderboard
alongside human players. Bud Bot is ranked #3 with +1.442 EPPD and
70% win rate across 27 games. The leaderboard does not distinguish
between AI and human entries — both use the same ranking metric.

## Match History Verification

### Pre-Match

- 11 completed matches visible
- Most recent: "Bud Bot Loss 29-52, 9 hands, Apr 03 08:20 AM"

### Post-Match

- 12 completed matches visible (+1, correct)
- New entry at top: "Bud Bot Loss 27-52, 9 hands, Apr 03 08:31 AM"
- Score matches our match result (27 vs 52)
- Hands count matches (9)
- Timestamp is correct (within the minute we played)

**History is accurate and up-to-date.**

## Auxiliary Endpoint Tests

| Endpoint | UUID | HTTP Status | Correct? |
|----------|------|-------------|----------|
| `/leaderboard/{uuid}` | Valid | 200 | Yes |
| `/leaderboard/{uuid}` | Invalid | 404 | Yes |
| `/history/{uuid}` | Valid | 200 | Yes |
| `/history/{uuid}` | Invalid | 404 | Yes |
| `/guide/{uuid}` | Valid | 200 | Yes |
| `/comments/{uuid}` | Valid | 200 | Yes |

All auxiliary endpoints return correct status codes. Invalid UUIDs
return 404 as expected.

## Match Details

| Hand | Score (H vs AI) | Notes |
|------|-----------------|-------|
| 1 | 2 vs 8 | |
| 2 | 9 vs 11 | |
| 3 | 15 vs 15 | Tied! |
| 4 | 16 vs 24 | |
| 5 | 21 vs 29 | |
| 6 | 28 vs 32 | Ace bid 3 High, took 7 (HIGH contract) |
| 7 | 29 vs 41 | AI pulling ahead |
| 8 | 23 vs 46 | Score dropped (set?) |
| 9* | 27 vs 52 | Match end (AI wins) |

*Hand 9 triggered match completion. Not visible as HAND_RESULT.

### Score Anomaly: Hand 8

Score went from 29-41 (hand 7) to 23-46 (hand 8). Human team dropped
from 29 to 23 (-6), which means the human team was set on a 6-bid.
AI gained +5. This is consistent: set bidder gets -bid, defenders get
tricks won. If human bid 6 and took 4, that's -6 for human, +4 for AI.
But 41+4=45 not 46. Need +5 which means took 5 tricks → -6+5=-1 →
29-6=23 human (correct), 41+5=46 AI (correct). So the human bid 6,
took 5, got set. Score math checks out.

## Bugs Found

**None.** All tested flows work correctly:
- `/new-match` returns model-select (idempotent)
- Leaderboard updates accurately after match completion
- History shows correct match result with accurate scores and timestamps
- All auxiliary endpoints return correct status codes
- 404 for invalid UUIDs across all gated endpoints

## Cumulative Bug Tracker (All Rounds)

| Issue | Severity | Status | Round |
|-------|----------|--------|-------|
| #2211 | Medium | Filed | R1 — abandoned match cleanup |
| #2212 | Low | Filed | R1 — score display standardization |
| #2217 | Low | Filed | R2 — illegal bid returns JSON not HTML |

No new bugs in rounds 3-6. The application is well-built.
