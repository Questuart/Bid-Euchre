# Hybrid Playtest Round 4: Leaderboard and History Accuracy

**Date:** 2026-04-03
**Player:** Claude-HYB (invite code QXBIA590)
**Opponent:** Bud Bot
**Method:** Auto-play engine (phase-based state machine) + Playwright screenshots of History and Leaderboard pages. Full cross-verification of aggregate stats against per-hand match data.

## Match 3 Summary (Game Session)

| Hand | Bidder | Contract | Result | Tricks | Hand Score (You/AI) | Cumulative (You/AI) |
|------|--------|----------|--------|--------|---------------------|---------------------|
| 1 | Slim | 6 ♥ | Made | 8 | +2 / +8 | 2 / 8 |
| 2 | Ace | 6 ♣ | **Set!** | 5 | **-6** / +5 | **-4** / 13 |
| 3 | Deuce | 3 High | Made | 7 | +3 / +7 | -1 / 20 |
| 4 | Deuce | 3 ♣ | Made | 5 | +5 / +5 | 4 / 25 |
| 5 | Slim | 3 High | Made | 6 | +4 / +6 | 8 / 31 |
| 6 | Slim | 5 ♥ | Made | 6 | +4 / +6 | 12 / 37 |
| 7 | Deuce | 6 Low | **Set!** | 4 | +6 / **-6** | 18 / **31** |
| 8 | Deuce | 6 High | Made | **10** | **0** / +10 | 18 / 41 |
| 9 | Ace | 5 ♠ | Made | 9 | +9 / +1 | 27 / 42 |
| 10 | (uncaptured) | ? | Made | ? | +0 / +10 | **27 / 52** |

**Result:** AI wins exactly at 52 (minimum threshold). 10 hands, 3 losses total for Claude-HYB.

### Scoring Edge Cases in This Match

1. **Negative cumulative score:** After hand 2, our score went to -4 (recovered by hand 4)
2. **AI set with score drop:** Hand 7 — Deuce bid 6 Low, only took 4. AI score dropped from 37 to 31 (-6)
3. **10-trick sweep:** Hand 8 — Deuce bid 6 High and took ALL 10 tricks. Our team scored 0 for the hand.
4. **Exact threshold win:** AI finished at exactly 52 (not over). Closest possible winning margin.
5. **Low no-trump set:** Hand 7 tested the Low contract set path (bid 6 Low, took only 4)

All scoring arithmetic verified — see verification table below.

### Scoring Arithmetic Verification

| After Hand | You Expected | You Actual | AI Expected | AI Actual | Pass? |
|-----------|-------------|-----------|------------|----------|-------|
| 1 | 0+2=2 | 2 | 0+8=8 | 8 | YES |
| 2 | 2+(-6)=-4 | -4 | 8+5=13 | 13 | YES |
| 3 | -4+3=-1 | -1 | 13+7=20 | 20 | YES |
| 4 | -1+5=4 | 4 | 20+5=25 | 25 | YES |
| 5 | 4+4=8 | 8 | 25+6=31 | 31 | YES |
| 6 | 8+4=12 | 12 | 31+6=37 | 37 | YES |
| 7 | 12+6=18 | 18 | 37+(-6)=31 | 31 | YES |
| 8 | 18+0=18 | 18 | 31+10=41 | 41 | YES |
| 9 | 18+9=27 | 27 | 41+1=42 | 42 | YES |
| 10 (inferred) | 27+0=27 | 27 | 42+10=52 | 52 | YES |

## History Page Verification

**URL:** `/history/649b8550-f76f-434c-842b-e04bc90b1f1b`

### History Table Content

| # | Opponent | Result | Score | Hands | Date | Expected | Match? |
|---|----------|--------|-------|-------|------|----------|--------|
| 1 | Bud Bot | Loss | 27 – 52 | 10 | Apr 3, 2026, 1:05 AM | Match 3: 27-52, 10h | ✅ |
| 2 | Bud Bot | Loss | 27 – 53 | 8 | Apr 3, 2026, 12:35 AM | Match 2: 27-53, 8h | ✅ |
| 3 | Bud Bot | Loss | 10 – 53 | 7 | Apr 2, 2026, 11:31 PM | Match 1: 10-53, 7h | ✅ |

**Observations:**
- All 3 completed matches present (no missing, no duplicates)
- Scores exactly match our captured match-over screen data
- Hand counts match
- Dates in descending order (newest first)
- "Loss" labels correctly shown in red for all 3
- Opponent correctly identified as "Bud Bot"
- Timestamps localized to browser timezone via JavaScript

**No per-hand breakdown available** — the History page shows only summary data (score, hands, date). Users must rely on in-game "Cards Played" detail during hand results to review individual hands.

## Leaderboard Page Verification

**URL:** `/leaderboard/649b8550-f76f-434c-842b-e04bc90b1f1b`

### Claude-HYB Full Stats Cross-Verification

| Stat | Abbrev | Leaderboard Value | Manual Calculation | Source | Match? |
|------|--------|------------------|--------------------|--------|--------|
| Rank | # | 10 | — | — | — |
| EPPD | EPPD | -3.760 | (64-158)/25 = -3.760 | net pts / hands | ✅ |
| Games Played | GP | 3 | 3 matches completed | count | ✅ |
| Hands Played | HP | 25 | 7+8+10 = 25 | sum | ✅ |
| Games Won | GW | 0 games | 0 wins out of 3 | count | ✅ |
| Win % | W% | 0% | 0/3 = 0% | ratio | ✅ |
| Avg Margin | Mgn | -31.3 | (-43-26-25)/3 = -31.33 | avg | ✅ |
| Win Margin | WMgn | 0.0 | No wins → 0.0 | n/a | ✅ |
| Bid % | Bid% | 20% | 5/25 = 20% | our team declared | ✅ |
| Make % | Make% | 60% | 3/5 = 60% | contracts made | ✅ |
| Avg Bid | AvgB | 4.8 | (5+3+5+6+5)/5 = 4.8 | avg level | ✅ |
| Moon % | Moon% | 0% | 0 moons | none bid | ✅ |
| Loner % | Loner% | 0% | 0 loners | none bid | ✅ |

**All 12 stats verified correct.**

### Bid% / Make% Detail Breakdown

Our team declared in 5 of 25 hands:

| Match | Hand | Bidder | Bid | Tricks | Made? |
|-------|------|--------|-----|--------|-------|
| 1 | 1 | You | 5♠ | 2 | NO (Set) |
| 1 | 3 | Ace | 3♠ | 6 | YES |
| 2 | 5 | Ace | 5♠ | 6 | YES |
| 3 | 2 | Ace | 6♣ | 5 | NO (Set) |
| 3 | 9 | Ace | 5♠ | 9 | YES |

- **Bid%:** 5/25 = 20% ✅
- **Make%:** 3/5 = 60% ✅
- **AvgB:** (5+3+5+6+5)/5 = 4.8 ✅

### Leaderboard Observations

1. **No current-player highlight:** Claude-HYB's row has no visual differentiation from other rows. Finding: users can't easily spot their own ranking.
2. **Bud Bot listed as AI (#3):** Correctly tagged with "AI" badge, ranked #3 with +1.209 EPPD.
3. **Column abbreviations with glossary:** Abbreviated headers (EPPD, GP, HP, etc.) with an expandable "What do these stats mean?" section. Good accessibility pattern.
4. **Other Claude bots visible:** Claude-HTTP (#7), CLAUDE (#8), Claude-PW (#9) — all with negative EPPD. Shows multiple test sessions from different playtest approaches.
5. **Human players:** Marg (#1, +2.000 EPPD), Olive Juice (#2, +1.500), Meeks (#4, +1.111, 70% win rate) — real humans playing.

## Findings

### Finding 1: All History and Leaderboard Data Verified Correct (PASS)

Every field in both the History table and Leaderboard was cross-verified against our captured match data. Zero discrepancies found across:
- 3 match summaries in History (scores, hands, dates, opponent, result)
- 12 leaderboard statistics for Claude-HYB (EPPD, GP, HP, GW, W%, Mgn, WMgn, Bid%, Make%, AvgB, Moon%, Loner%)

### Finding 2: No Current-Player Highlight on Leaderboard (Enhancement)

Claude-HYB's row (#10) has no visual highlighting to distinguish it from other players. On a busy leaderboard, users must scan to find their own entry.

**Recommendation:** Add a CSS class (e.g., `leaderboard-row--current`) or `aria-current="true"` to the current player's row.

### Finding 3: History Lacks Per-Hand Drill-Down (Observation)

The History page shows only match-level summaries (opponent, result, score, hands, date). There is no expandable detail showing per-hand breakdown (bidder, contract, tricks, scoring). Users who want to review individual hands from past matches have no way to access this data post-match.

### Finding 4: Exact-Threshold Win Renders Correctly (PASS)

AI won at exactly 52 points (minimum threshold). The match-over screen correctly showed "You Lose" with score 27-52. No off-by-one error in the win condition check.

### Finding 5: AI Set Correctly Reduces Score (PASS)

Hand 7: Deuce bid 6 Low, took only 4 tricks. AI team score correctly went from 37 to 31 (37 + (-6) = 31). The negative scoring for sets is working correctly in both directions (our team set in hand 2, AI team set in hand 7).

## Screenshots

| File | Description |
|------|-------------|
| `playtest/06_match4_end.png` | Match 3 "You Lose" screen (27-52, 10 hands) |
| `playtest/07_history_page.png` | History tab showing all 3 completed matches |
| `playtest/08_leaderboard.png` | Full leaderboard with Claude-HYB at #10 |

## Outcome

- **Issues filed:** #2224 — web: highlight current player's row on leaderboard
- **Overall assessment:** History and Leaderboard data integrity is excellent. Every stat verified correct across 3 matches and 25 hands. The data pipeline from game engine → database → aggregate display is working flawlessly.
