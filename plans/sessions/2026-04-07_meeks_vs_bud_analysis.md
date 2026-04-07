# Meeks vs Bud Bot — Gameplay Analysis

**Date:** 2026-04-07
**Data source:** Render production database (bideuchre-db)
**Sample:** Meeks = 30 completed matches (306 hands), Bud Bot = 857 completed matches (8,532 hands)

---

## 1. Executive Summary

Meeks is a strong human player with a **56.7% win rate** (17-13) against the Bud bot,
placing in the top tier of human players by volume. However, there is a **clear
performance decline** from 83% win rate in the first two days to 25% in the most
recent session. Three specific weaknesses stand out:

1. **Spades contracts** — 73.7% make rate vs 95-96% in other suits
2. **Moon bids** — 4 of 6 personal moon bids were set (-80 total points)
3. **High-level overbidding** — 36.4% set rate at bid level 7

The Bud bot, by contrast, is a conservative, volume bidder — it bids more often
(68.2% vs 61.4%) at much lower levels (avg 3.45 vs 4.80) with a very low set rate
(5.6% vs 12.1%).

---

## 2. Match-Level Performance

### Meeks Overall Record

| Metric | Value |
|--------|-------|
| Completed matches | 30 |
| Wins | 17 (56.7%) |
| Losses | 13 (43.3%) |
| Avg human score | 45.6 |
| Avg AI score | 43.5 |
| Avg margin | +2.1 |
| Avg hands/match | 10.2 |

### Performance Trend (Declining)

| Date | Matches | W-L | Win% | Avg Margin |
|------|---------|-----|------|------------|
| Apr 2 | 6 | 5-1 | 83% | **+15.3** |
| Apr 3 | 8 | 5-3 | 63% | +5.9 |
| Apr 4 | 6 | 3-3 | 50% | +0.8 |
| Apr 5 | 3 | 1-2 | 33% | -7.3 |
| Apr 6 | 3 | 2-1 | 67% | -2.3 |
| Apr 7 | 4 | 1-3 | 25% | **-12.8** |

**Notable:** The April 7 matches used strategy versions 0.7.0, 0.8.1, and 0.9.0.
The bot may be getting stronger across versions, or Meeks may be fatiguing / tilting
after losses. The 4 most recent matches show Meeks scoring an average of only 38.0
points vs the bot's 50.8.

### Points Per Hand Trend

Early matches (Apr 2): Meeks averaged 5.5-7.0 pts/hand.
Recent matches (Apr 7): Meeks averaged 2.0-5.9 pts/hand.
The bot has remained steady at ~4-5 pts/hand throughout.

### Comparison to Other Human Players

| Player | Matches | Win% | Avg Margin | Notes |
|--------|---------|------|------------|-------|
| Sydney | 7 | 85.7% | +14.9 | Small sample |
| Luther | 6 | 83.3% | +12.7 | Small sample |
| Que | 25 | 56.0% | +2.9 | Most comparable |
| **Meeks** | **29** | **55.2%** | **+2.1** | — |
| TEST | 7 | 42.9% | -9.4 | Test account |
| FlexBot-A | 368 | 38.6% | -6.0 | Automated |
| Claude | 50 | 2.0% | -56.3 | AI-as-human |

Meeks and Que are the two most active real human players with comparable records.
Sydney and Luther have strong records but very small samples (6-7 matches).

---

## 3. Bidding Policy Analysis

### Bid Frequency

| Metric | Meeks | Bud Bot | Que (reference) |
|--------|-------|---------|-----------------|
| Total bid decisions | 306 | 24,264 | 280 |
| Pass rate | 38.6% | 31.8% | 25.0% |
| Bid rate | **61.4%** | **68.2%** | **75.0%** |
| Avg bid level (when bidding) | **4.80** | **3.45** | **5.13** |

**Key insight:** Meeks is **less aggressive** than both Bud bot and Que in bid
frequency, but bids at **significantly higher levels** than Bud bot. This is a
high-risk, high-reward strategy — when it works, Meeks wins big; when it doesn't,
the set penalties are devastating.

Que bids even more aggressively (75% bid rate) at even higher average levels (5.13)
and has a slightly better win rate — suggesting Meeks could potentially bid
more often at moderate levels.

### Bid Level Distribution

| Bid Level | Meeks % | Bud Bot % | Delta |
|-----------|---------|-----------|-------|
| 1 | 0.5% | 23.8% | Bud bids much more at 1 |
| 2 | 4.8% | 14.5% | |
| 3 | 16.0% | 14.1% | Similar |
| 4 | 25.0% | 6.7% | **Meeks heavy at 4** |
| 5 | 19.1% | 24.3% | Similar |
| 6 | 25.5% | 15.3% | **Meeks heavy at 6** |
| 7 | 5.9% | 1.1% | Meeks 5x more |
| 8-10 | 3.2% | 0.2% | Meeks 16x more |

**Meeks concentrates bids at levels 4-6** (69.6% of all bids) vs Bud bot which
spreads across 1-6. Bud bot's 23.8% at level 1 represents cheap "blocking" bids
or low-confidence entries — Meeks rarely does this (0.5%).

### Contract Type Preferences (When Bidding)

| Contract | Meeks % | Bud Bot % | Notes |
|----------|---------|-----------|-------|
| Suit (C/D/H/S) | 69.1% | 74.4% | Both favor suit |
| HIGH | 22.3% | 10.8% | **Meeks bids HIGH 2x more** |
| LOW | 8.5% | 14.8% | Meeks bids LOW less |

**Meeks strongly prefers HIGH contracts** (22.3% vs 10.8%) over LOW (8.5% vs 14.8%).
This is a notable strategic preference — HIGH is generally considered harder to
play well because Aces are the power cards and opponents can trump effectively.

### Suit Distribution (When Meeks Bids Suit)

| Suit | Meeks % | Avg Bid | Make% |
|------|---------|---------|-------|
| Diamonds | 36.8% | 5.14 | **96.4%** |
| Hearts | 26.3% | 5.40 | **95.0%** |
| Spades | 25.0% | 5.37 | **73.7%** |
| Clubs | 11.8% | 5.78 | 88.9% |

**The Spades problem is glaring.** Meeks bids Spades almost as often as Hearts
but makes them at a dramatically lower rate (73.7% vs 95%). Bud bot shows no
such suit bias (88-90% make rate across all suits).

### Auction Win Rate

| Winner | Hands | % |
|--------|-------|---|
| Meeks (seat 0) | 107 | 35.0% |
| Partner (seat 2) | 73 | 23.9% |
| **Meeks team total** | **180** | **58.8%** |
| Opponents (seats 1,3) | 126 | 41.2% |

Meeks's team declares in nearly 59% of hands — well above the 50% expected in
a balanced 4-player game. This is aggressive and generally positive, as the
declaring team has the advantage of choosing trump.

---

## 4. Set Rate Analysis

### Meeks Personal Bids — Set Rate by Level

| Bid Level | Hands | Made | Set | Set% | Avg Tricks |
|-----------|-------|------|-----|------|------------|
| 3 | 6 | 6 | 0 | **0%** | 5.83 |
| 4 | 18 | 18 | 0 | **0%** | 6.39 |
| 5 | 22 | 22 | 0 | **0%** | 7.14 |
| 6 | 44 | 39 | 5 | **11.4%** | 7.50 |
| 7 | 11 | 7 | 4 | **36.4%** | 7.27 |
| 10 (moon) | 6 | 2 | 4 | **66.7%** | 8.50 |
| **Total** | **107** | **94** | **13** | **12.1%** | — |

**At levels 3-5, Meeks never gets set.** This is excellent calibration.
The problems start at 6+ where the set rate escalates sharply.

### Bud Bot — Set Rate by Level (When Declaring)

| Bid Level | Hands | Set% | Avg Tricks |
|-----------|-------|------|------------|
| 2 | 125 | 0% | 6.12 |
| 3 | 915 | 0.2% | 6.29 |
| 4 | 273 | 4.4% | 6.44 |
| 5 | 1,669 | 3.3% | 7.03 |
| 6 | 1,525 | 10.4% | 7.47 |
| 7 | 126 | 15.1% | 8.01 |
| **Total** | **4,667** | **5.6%** | — |

Bud bot is significantly more conservative and has a much lower overall set rate
(5.6% vs 12.1%). At level 6, Meeks and Bud are similar (11.4% vs 10.4%),
but at level 7 Meeks is much worse (36.4% vs 15.1%).

### Meeks's 13 Set Hands — Detail

| Bid | Contract | Type | Tricks | Points | Date | Notes |
|-----|----------|------|--------|--------|------|-------|
| 10 | C | suit | 7 | -20 | Apr 2 | Moon set |
| 10 | LOW | low | 7 | -20 | Apr 3 | Moon set |
| 10 | HIGH | high | 9 | -20 | Apr 3 | Moon set, 1 trick short |
| 10 | HIGH | high | 8 | -20 | Apr 4 | Moon set |
| 7 | HIGH | high | 6 | -7 | Apr 2 | 1 trick short |
| 7 | HIGH | high | 5 | -7 | Apr 3 | 2 tricks short |
| 7 | H | suit | 6 | -7 | Apr 4 | 1 trick short |
| 7 | S | suit | 6 | -7 | Apr 7 | 1 trick short |
| 6 | S | suit | 4 | -6 | Apr 4 | 2 tricks short |
| 6 | S | suit | 3 | -6 | Apr 5 | 3 tricks short! |
| 6 | S | suit | 5 | -6 | Apr 6 | 1 trick short |
| 6 | D | suit | 5 | -6 | Apr 7 | 1 trick short |
| 6 | S | suit | 5 | -6 | Apr 7 | 1 trick short |

**Patterns in set hands:**
- **4 of 13 sets are moon bids** — devastating at -20 each (-80 total)
- **4 of 5 sets at bid 6 are Spades** — confirms the Spades weakness
- **3 of 4 sets at bid 7 involve HIGH** — Meeks overbids HIGH at high levels
- **Recent sets cluster in Apr 5-7** — part of the performance decline

---

## 5. Play Policy Analysis

### Declaring Performance

| Metric | Meeks Team | Opponent Team |
|--------|------------|---------------|
| Avg tricks when declaring | 6.98 | 6.69 |
| Avg points when declaring | 5.28 | 6.03 |
| Make rate | 86.7% | 93.7% |

Meeks's team takes more raw tricks when declaring (6.98 vs 6.69) but has a
**lower make rate** because Meeks bids higher (avg 5.50 vs 5.15). The opponent's
higher make rate reflects the Bud bot's conservative bidding.

### Defending Performance

| Metric | Meeks Team | All Humans Avg |
|--------|------------|---------------|
| Avg tricks taken defending | **3.31** | 3.00 |
| Avg points defending | 3.31 | 3.00 |

**Meeks is an above-average defender**, taking 0.31 more tricks per hand than the
average human team. This is a genuine strength — strong defense compensates
for occasional overbidding.

### By Bidder Seat (Meeks Matches)

| Bidder | Hands | Avg Bid | Team0 Tricks | Make% | Team0 Pts |
|--------|-------|---------|--------------|-------|-----------|
| Seat 0 (Meeks) | 107 | 5.62 | 7.18 | 87.9% | 5.36 |
| Seat 1 (opponent) | 62 | 5.10 | 3.35 | 93.5% | 3.35 |
| Seat 2 (partner) | 73 | 5.41 | 6.68 | **84.9%** | 5.16 |
| Seat 3 (opponent) | 64 | 5.22 | 3.27 | 93.8% | 3.27 |

**The AI partner (seat 2) has the lowest make rate in the game (84.9%).**
When the partner declares, Meeks's team wins fewer tricks and makes the
contract less often — even though the partner bids at a lower level than Meeks.
This may be a coordination issue between Meeks's play style and the bot's expectations.

---

## 6. Moon & Special Bids

| Bid Type | Bidder | Outcome | Tricks | Points |
|----------|--------|---------|--------|--------|
| Moon D (suit) | Meeks | **MADE** | 10 | +20 |
| Moon C (suit) | Meeks | SET | 7 | -20 |
| Moon HIGH | Meeks | SET | 8 | -20 |
| Moon LOW | Meeks | **MADE** | 10 | +20 |
| Moon LOW | Meeks | SET | 7 | -20 |
| Moon HIGH | Meeks | SET | 9 | -20 |
| Moon HIGH | Partner | **MADE** | 10 | +20 |
| Moon HIGH | Partner | SET | 7 | -20 |

**Moon bid summary:** 3 made (+60 pts), 5 set (-100 pts). Net = **-40 points**.

Moon bids are net negative for Meeks. If all 6 of Meeks's personal moon bids had
been regular 6-bids instead, the worst case would have been -36 points (6 sets at -6),
and the expected case (at ~89% make rate for bid 6) would have been roughly +32 points.
**Moon bids have cost Meeks approximately 72+ points compared to safe alternatives.**

---

## 7. Bud Bot Profile

For completeness, here is the Bud bot's aggregate profile across all 857 matches:

| Metric | Value |
|--------|-------|
| Bid rate | 68.2% |
| Avg bid level | 3.45 |
| Set rate (when declaring) | 5.6% |
| Avg tricks when declaring | 7.00 |
| Make rate by contract: Suit | 88-90% |
| Make rate by contract: HIGH | 92.5% |
| Make rate by contract: LOW | 82.2% |

**Bud bot's strategy is volume-conservative:** bid often, bid low, rarely get set.
It wins its contracts 94.4% of the time. Its weakness is LOW contracts (82.2% make rate)
where it may not evaluate 10-low hands accurately.

---

## 8. Strengths & Weaknesses

### Meeks Strengths

1. **Excellent calibration at levels 3-5** — 0% set rate across 46 hands.
   Meeks knows when a hand is worth 3-5 tricks and rarely overestimates.

2. **Strong defense** — 3.31 tricks/hand when defending (vs 3.00 average).
   Meeks is good at competing for tricks even when not declaring.

3. **High trick-taking ability** — 7.18 avg tricks when declaring at seat 0.
   When Meeks has the right hand, execution is solid.

4. **Diamonds and Hearts mastery** — 95-96% make rate in these suits. Meeks
   has excellent judgment for these contracts.

5. **Positive overall record** — 56.7% win rate over 30 matches is strong
   against a competent AI opponent.

### Meeks Weaknesses

1. **Spades problem** — 73.7% make rate is the worst by far. Meeks appears to
   overvalue Spade hands or misplay Spade contracts. 4 of 5 sets at bid 6 are Spades.
   **Actionable: Downbid Spades by 1 level (e.g., bid 5 instead of 6).**

2. **Moon bid gambles** — -40 net points from moon bids. The EV is deeply
   negative at current success rates (33%).
   **Actionable: Stop bidding moon unless holding 9+ near-certain tricks.**

3. **Level 7 overbidding** — 36.4% set rate. Three of four bid-7 sets involved HIGH.
   **Actionable: Only bid 7 with absolute powerhouse hands (8+ sure tricks).**

4. **Performance decline** — Win rate dropped from 83% to 25% over 6 days.
   This may be fatigue, tilt, or the bot getting stronger (v0.7.0 → v0.9.0).
   **Actionable: Take breaks between sessions. Track per-version results.**

5. **Conservative pass rate** — 38.6% pass rate vs Que's 25.0%. Meeks may be
   leaving value on the table by not competing at lower levels (3-4).
   **Actionable: Try entering at 3 more often with moderate hands.**

### Bud Bot Strengths

1. **Very low set rate** (5.6%) — conservative bidding means it almost always makes.
2. **Even suit balance** — no exploitable suit preference.
3. **HIGH contract proficiency** — 92.5% make rate at HIGH.
4. **Volume bidding** — enters often (68.2%) at low levels to control the auction.

### Bud Bot Weaknesses

1. **LOW contract struggles** — 82.2% make rate is the weakest contract type.
   Meeks could potentially exploit this by forcing the bot into LOW situations.
2. **Conservative strategy limits upside** — avg bid 3.45 means the bot rarely
   gets the big scores. It wins by attrition, not domination.
3. **Improving but exploitable** — strategy versions indicate active development,
   but the core conservative philosophy may be beatable by well-calibrated
   aggressive play.

---

## 9. Recommendations for Meeks

### Immediate (High Impact)

1. **Fix the Spades leak.** Before bidding 6+ Spades, ensure you have at least
   7 near-certain tricks. Consider bidding 5 Spades instead of 6 on borderline hands.
   This single change could recover ~30 points across the sample.

2. **Eliminate moon bids** (or nearly). Moon bids are -40 net. Save them for
   hands where you hold both bowers, the ace, and 7+ additional winning cards.
   The risk/reward at current success rates is terrible.

3. **Be cautious with HIGH at 7.** Three of four bid-7 sets were HIGH contracts.
   HIGH at level 7 requires holding most of the Aces — if you're missing more
   than 1-2, downbid to 6.

### Strategic (Medium Impact)

4. **Bid more at levels 3-4.** Meeks passes 38.6% of the time. Consider entering
   at 3 with moderate hands — the 0% set rate at 3-5 suggests room to bid more
   without risk.

5. **Exploit Bud bot's LOW weakness.** When conditions favor a LOW contract,
   consider bidding it — the bot only makes LOW at 82.2%, suggesting opportunities
   to set the bot on LOW defense.

6. **Monitor strategy versions.** The bot may be getting stronger (Apr 7 results
   against v0.7.0-v0.9.0 are poor). Adapt strategy if the bot's bidding changes.

### Mental Game

7. **Take breaks after losses.** The declining trend suggests possible tilt.
   Two back-to-back losses in a session should trigger a cooldown.

8. **Track session stats.** Knowing your current-session win rate can help
   identify when fatigue is affecting play quality.

---

## Outcome

Analysis committed as `plans/sessions/2026-04-07_meeks_vs_bud_analysis.md`.

**Data provenance:** All statistics queried directly from the Render production
database (`bideuchre-db`) on 2026-04-07. Meeks = player_id 2 (30 complete matches,
306 hands). Bud bot = ai_model 'bud_bot' (857 complete matches, 8,532 hands).
