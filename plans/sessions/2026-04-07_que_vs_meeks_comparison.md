# Que vs Meeks: Head-to-Head Comparison

> **Date:** 2026-04-07
> **Source:** Render production database (`bideuchre-db`)
> **Bot opponent:** `bud_bot` (all AI seats)
> **Sample:** Que 25 complete matches (280 hands) · Meeks 30 complete matches (306 hands)

## Executive Summary

Both players are strong, posting positive win rates against `bud_bot`.
**Que is the more aggressive bidder** — bidding 75% of the time at an average
level of 5.13 vs Meeks' 61% at 4.80. **Meeks is the safer declarer** — making
contracts 87.2% of the time when team0 declares vs Que's 83.5%. Que compensates
for a higher set rate with stronger defensive play and better clutch
performance. On net, Que edges Meeks on win rate (56% vs 57%) and margin
(+2.9 vs +2.1), but the gap is within noise given sample sizes.

**Verdict:** Approximately equal strength, with distinct strategic profiles.
Que is a high-volume aggressive bidder who creates more action; Meeks is a
disciplined declarer who excels when given the contract.

---

## 1. Overall Match Record

| Metric | Que | Meeks |
|--------|-----|-------|
| Matches (complete) | 25 | 30 |
| Wins | 14 (56.0%) | 17 (56.7%) |
| Losses | 11 (44.0%) | 13 (43.3%) |
| Avg human score | 47.0 | 45.6 |
| Avg AI score | 44.0 | 43.5 |
| Avg margin | **+2.9** | +2.1 |
| Avg hands/match | 11.2 | 10.2 |
| Date range | Apr 5–7 | Apr 2–7 |

Both players beat `bud_bot` at similar rates. Que's matches tend to go longer
(11.2 vs 10.2 hands), consistent with the higher bidding volume creating more
back-and-forth.

### Match Outcome Distribution

| Category | Que | Meeks |
|----------|-----|-------|
| Blowout win (>20 margin) | 5 (20.0%) | 8 (26.7%) |
| Solid win (6–20) | 8 (32.0%) | 5 (16.7%) |
| Close game (±5) | 3 (12.0%) | 4 (13.3%) |
| Solid loss (−6 to −20) | 5 (20.0%) | 8 (26.7%) |
| Blowout loss (>20) | 4 (16.0%) | 5 (16.7%) |

**Key insight:** Que wins more matches in the "solid win" bracket (32% vs 17%),
suggesting more consistent moderate victories. Meeks has more extreme outcomes —
more blowout wins *and* more solid losses. Meeks is streakier; Que is steadier.

### Recent Form (Last 10 Matches)

| Metric | Que | Meeks |
|--------|-----|-------|
| Wins | 6 | 4 |
| Losses | 4 | 6 |
| Avg margin | **+4.5** | −8.0 |
| Avg score | 48.0 | 43.0 |

Que's recent form is considerably stronger. Meeks' last 10 matches show a
negative margin, suggesting possible tilt or fatigue in later sessions.

---

## 2. Bidding Comparison

### Bid Frequency

| Metric | Que | Meeks |
|--------|-----|-------|
| Total bid actions | 280 | 306 |
| Actual bids (n > 0) | 210 (75.0%) | 188 (61.4%) |
| Passes (n = 0) | 70 (25.0%) | 118 (38.6%) |
| Avg bid level (when bidding) | **5.13** | 4.80 |
| Max bid | 10 (moon) | 10 (moon) |

**Que bids dramatically more often** — 75% of opportunities vs 61% for Meeks.
This 14 percentage point gap is the single biggest difference between the two
players. Que takes more initiative and seizes more contracts.

### Bid Level Distribution

| Level | Que | Meeks |
|-------|-----|-------|
| 1–2 | 2.4% | 5.3% |
| 3 | 8.6% | 16.0% |
| 4 | 20.5% | 25.0% |
| 5 | 26.2% | 19.1% |
| 6 | **35.2%** | 25.5% |
| 7 | 4.3% | 5.9% |
| 10 (moon) | 2.9% | 3.2% |

Que concentrates bids at 5 and 6 (61.4% combined). Meeks spreads more evenly
across 3–6. Que rarely makes exploratory low bids (only 2.4% at 1–2 vs 5.3%
for Meeks).

### Contract Type Preferences

| Contract | Que | Meeks |
|----------|-----|-------|
| Suit (C/D/H/S) | 75.2% | 69.7% |
| HIGH (no-trump) | 13.8% | **22.3%** |
| LOW (no-trump) | 11.0% | 8.5% |

Meeks has a notable preference for HIGH contracts (22% vs 14%), bidding
no-trump high more frequently. Que favors suit contracts more heavily and
also bids LOW slightly more than Meeks.

### Suit Preference (Suit Contracts Only)

| Suit | Que | Meeks |
|------|-----|-------|
| Spades | **31.0%** | 26.2% |
| Hearts | 24.7% | **31.5%** |
| Diamonds | 22.8% | **31.5%** |
| Clubs | 21.5% | 10.8% |

The most striking difference: **Que distributes bids evenly across all four
suits** (21–31%), while **Meeks strongly avoids Clubs** (only 11%). Meeks
concentrates on Hearts and Diamonds (63% combined). Que is willing to bid
any suit, including Clubs — suggesting either more versatile hand evaluation
or lower suit preference thresholds.

### Who Wins the Bid?

| Bidder | Que | Meeks |
|--------|-----|-------|
| Human (seat 0) | **45.0%** | 35.0% |
| AI partner (seat 2) | 22.1% | 23.9% |
| Opponents (seats 1/3) | 32.9% | 41.2% |

Que personally wins the bid in 45% of hands vs Meeks' 35%. Combined with the
AI partner, Que's team declares 67.1% of hands vs Meeks' 58.9%. This means
Que's team is on offense much more often — the opponents only get to declare
33% of the time vs 41% against Meeks.

---

## 3. Declaration Performance

### Overall Make/Set Rate (Team0 Declares)

| Metric | Que | Meeks |
|--------|-----|-------|
| Hands declared | 188 | 180 |
| Made | 157 (83.5%) | 156 (**86.7%**) |
| Set | 31 (16.5%) | 24 (13.3%) |
| Avg tricks (when declaring) | 6.69 | **6.91** |
| Avg overtricks | 1.02 | **1.58** |
| Avg points (declaring) | 4.68 | **5.28** |

Meeks makes contracts at a higher rate and averages more overtricks (1.58 vs
1.02). This is partly explained by Meeks' lower average bid level — bidding
more conservatively leads to more overtricks and fewer sets.

### Make Rate by Bid Level

| Bid | Que Make% (n) | Meeks Make% (n) |
|-----|---------------|-----------------|
| 3 | — | 100.0% (10) |
| 4 | 92.9% (14) | 100.0% (21) |
| 5 | **93.2%** (44) | 89.7% (58) |
| 6 | 82.1% (112) | **88.4%** (69) |
| 7 | **75.0%** (12) | 64.3% (14) |
| 10 | 33.3% (6) | 37.5% (8) |

At bid level 6 (the most common for Que), Meeks makes 88% vs Que's 82%. But
Que bids 6 far more often (112 hands vs 69), so the 6% make rate gap reflects
Que taking on more marginal 6-bids. At level 7, Que is stronger (75% vs 64%).

### Human Bids vs AI Partner Bids

| | Que set% | Meeks set% |
|--|----------|-----------|
| Human bid | 18.3% | 12.1% |
| AI partner bid | 12.9% | 15.1% |

When **Que personally bids**, the team gets set 18.3% — notably higher than
Meeks' 12.1%. This confirms Que pushes more aggressively. When the AI partner
bids, set rates are similar (~13–15%), suggesting the AI partner normalizes
play quality regardless of which human is at seat 0.

### Performance by Contract Type

| Contract | Que Make% (avg pts) | Meeks Make% (avg pts) |
|----------|--------------------|-----------------------|
| Suit | 84.1% (5.2) | **88.9%** (5.7) |
| HIGH | **88.2%** (5.5) | 80.8% (3.8) |
| LOW | 76.9% (1.5) | **78.9%** (4.1) |

Notable split: **Que excels at HIGH contracts** (88% make rate vs 81% for
Meeks), while **Meeks excels at suit contracts** (89% vs 84%). Meeks' LOW
contract performance generates better points (4.1 vs 1.5 for Que), suggesting
better trick management in low contracts.

---

## 4. Defensive Performance

When the AI opponents (team1) declare:

| Contract | Que set opp% (n) | Meeks set opp% (n) |
|----------|-------------------|---------------------|
| Suit | **10.3%** (68) | 5.2% (97) |
| HIGH | **27.3%** (11) | 0.0% (12) |
| LOW | **23.1%** (13) | 17.6% (17) |
| Overall | **14.1%** (92) | 6.3% (126) |

**Que is the dramatically better defender.** Que sets AI opponents 14.1% of
the time overall vs just 6.3% for Meeks. The gap is especially stark on HIGH
contracts (27% vs 0%) and suit contracts (10% vs 5%). This suggests Que plays
more disruptively on defense — either through better trick sequencing, more
aggressive trump play, or better partner signaling.

This is arguably Que's biggest strength: the ability to disrupt AI declarations.

---

## 5. Efficiency Metrics

### Points Per Hand (PPH)

| Metric | Que | Meeks |
|--------|-----|-------|
| PPH (team0) | 4.193 | **4.471** |
| PPH (opponents) | 3.932 | 4.261 |
| **Net PPH** | 0.261 | 0.209 |

Meeks generates more absolute points per hand for team0 (4.47 vs 4.19), but
also concedes more to opponents (4.26 vs 3.93). On net PPH, Que has a slight
edge (0.261 vs 0.209), meaning Que's point generation is more *efficient*
relative to what the opponents earn.

### EV by Role

| Role | Que (avg pts) | Meeks (avg pts) |
|------|---------------|-----------------|
| Declaring | 4.68 | **5.28** |
| Defending | 3.20 | **3.31** |

Meeks earns more per hand in both roles in absolute terms. But Que's team
defends only 92 hands (33%) vs Meeks' 126 hands (41%) — Que simply declares
much more often, so the lower per-hand EV on defense matters less.

---

## 6. Situational Performance

### Performance by Game State

| State | Que avg pts | Meeks avg pts |
|-------|-------------|---------------|
| Ahead big (>10) | 3.57 | **5.31** |
| Ahead small (1–10) | 4.37 | **4.64** |
| Tied | 4.03 | 2.98 |
| Behind small (1–10) | **5.22** | 4.28 |
| Behind big (>10) | 3.71 | **4.64** |

**Key behavioral difference:** Que shows a clear **comeback pattern** —
averaging 5.22 points per hand when trailing by a small margin, the highest
rate for either player in any state. Meeks shows a **front-runner pattern** —
performing best when already ahead (5.31 when ahead big).

This suggests:
- **Que plays with more urgency when behind**, possibly taking more risks that
  pay off in deficit situations
- **Meeks coasts when ahead**, maintaining leads through steady play
- **Meeks struggles when tied** (2.98 PPH — the lowest figure in the table)

### Clutch Performance (Either Team at 40+)

| Metric | Que | Meeks |
|--------|-----|-------|
| Clutch hands | 62 | 68 |
| Hands won | 31 (**50.0%**) | 31 (45.6%) |
| Team0 bids in clutch | 40 (64.5%) | 42 (61.8%) |

In late-game hands where a win is near, Que wins 50% of hands vs Meeks' 46%.
Que also takes the bid slightly more often in clutch situations. This small
edge is consistent with Que's stronger recent form.

---

## 7. Moon Bids

Both players attempt moons at similar rates (~3% of bids), with mixed results:

| Player | Total Moons | Made | Set | Make% |
|--------|-------------|------|-----|-------|
| Que | 6 | 2 | 4 | 33.3% |
| Meeks | 8 | 3 | 5 | 37.5% |

Moon success rates are similar and both below 40%. Que also attempted one
**loner** bid (10-LOW loner) which failed — scoring −40 points. Neither player
shows a clear edge on moon play.

---

## 8. Strategic Profile Contrast

### Que — "The Aggressor"

- **High-volume bidder** (75% bid rate, avg level 5.13)
- **Suit-balanced** — bids all four suits roughly equally
- **Dominant defender** — sets AI opponents 14% of the time
- **Comeback specialist** — plays best when trailing
- **Higher risk tolerance** — 18% set rate on personal bids but compensates
  through defensive disruption and bid volume
- **Recent form trending up** — 6-4 in last 10

### Meeks — "The Technician"

- **Selective bidder** (61% bid rate, avg level 4.80)
- **Suit-preferential** — favors Hearts/Diamonds, avoids Clubs
- **Strong declarer** — 87% make rate with 1.58 avg overtricks
- **Front-runner** — plays best when already ahead
- **Lower risk tolerance** — 12% set rate, fewer marginal bids
- **Recent form cooling** — 4-6 in last 10, suggesting possible tilt

---

## 9. Verdict

**Overall strength: Approximately equal**, with Que holding a marginal
edge in recent play.

| Dimension | Edge |
|-----------|------|
| Win rate | Tie (56% vs 57%) |
| Average margin | Que (+2.9 vs +2.1) |
| Recent form | **Que** (6-4 vs 4-6) |
| Bid frequency | **Que** (75% vs 61%) |
| Bid accuracy | **Meeks** (12% set vs 18%) |
| Declaration quality | **Meeks** (87% make, 5.28 PPH) |
| Defensive disruption | **Que** (14% vs 6% opp set rate) |
| Clutch play | **Que** (50% vs 46%) |
| No-trump (HIGH) | **Que** (88% vs 81% make) |
| Suit contracts | **Meeks** (89% vs 84% make) |
| Composure when behind | **Que** (5.22 PPH) |
| Composure when ahead | **Meeks** (5.31 PPH) |

### What Each Needs to Improve

**Que** should:
1. Reduce set rate on personal bids (18% → closer to 15%) — some marginal
   6-bids should be 5-bids or passes
2. Improve LOW contract execution (1.5 avg points is weak)
3. Maintain defensive intensity (this is the biggest differentiator)

**Meeks** should:
1. Bid more aggressively — passing 39% of the time cedes too many
   declarations to the AI opponents
2. Expand suit range — the Clubs avoidance (11%) may be leaving value
   on the table
3. Improve defensive play — setting opponents only 6% is too passive
4. Break out of the recent losing streak — the tied-game struggles (2.98 PPH)
   suggest a confidence issue

---

## Statistical Caveats

- **Sample sizes are moderate** (25 and 30 matches, 280 and 306 hands).
  Differences within ±5% are likely noise.
- Both players face the same `bud_bot` AI, but different random seeds
  produce different deals, making strict controlled comparison impossible.
- The game is 3-AI-1-human, so ~75% of all play actions are AI-driven.
  The human's primary agency is in bidding and card play decisions at seat 0.
- Meeks has a 5-day longer history (starting Apr 2 vs Apr 5), which may
  include a learning curve period.
- No decision timing data was available in the database.

## Outcome

Analysis delivered for task packet `3d976777e13f`. Findings written to this
file and committed via PR.
