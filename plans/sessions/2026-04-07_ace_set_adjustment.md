# Ace (AI Partner) Set Adjustment Analysis

**Date:** 2026-04-07
**Data source:** Render production database (`bideuchre-db`)
**Players analyzed:** Que (25 matches, 280 hands), Meeks (30 matches, 306 hands)
**Companion reports:** Meeks vs Bud (PR #2622), Que vs Meeks H2H (PR #2621)

---

## Executive Summary

When the AI partner at seat 2 ("Ace") wins the bid and gets set, the human
player has limited agency over that outcome. This analysis separates human-declared
hands from Ace-declared hands and computes adjusted metrics that remove Ace's
set variance.

**Key findings:**

1. **Ace gets set at 2x the opponent bot rate — but this is structural, not
   player-specific.** Across ALL 2,288 partner-bot declarations in the database,
   seat 2 gets set at **11.15%** vs **5.56%** for opponent bots. The partner bot
   inherently underperforms because human/bot partnerships play worse support
   than bot/bot partnerships.

2. **Meeks's Ace is moderately unlucky** (15.1% set rate vs 11.15% structural
   baseline → ~3 excess sets). **Que's Ace is at baseline** (12.9% vs 11.15%
   → ~1 excess set).

3. **2 matches each were potentially flipped** by Ace sets (losses that become
   wins if Ace sets are converted to makes).

4. **After full Ace adjustment, both players converge to the same +6.2 adjusted
   margin** — suggesting truly equal skill once Ace variance is removed.

---

## 1. Raw Breakdown: Human vs Ace Declarations

### Set Rate by Bidder Seat

| Player | Seat 0 (Human) | | Seat 2 (Ace) | |
|--------|---:|---|---:|---|
| | Hands / Sets / Set% | Avg Pts | Hands / Sets / Set% | Avg Pts |
| **Meeks** | 107 / 13 / **12.1%** | 5.36 | 73 / 11 / **15.1%** | 5.16 |
| **Que** | 126 / 23 / **18.3%** | 4.13 | 62 / 8 / **12.9%** | 5.79 |

**Observation:** The patterns are reversed — Meeks has a lower personal set rate
but a higher Ace set rate. Que has a higher personal set rate but a lower Ace
set rate. This suggests Que provides better support when the partner declares.

### Net EPPD by Declaration Source

| Player | Overall | Human Declared | Ace Declared | Opp Declared |
|--------|---------|----------------|--------------|--------------|
| **Meeks** | +0.209 | +2.542 | +1.849 | −2.722 |
| **Que** | +0.261 | +0.683 | +2.887 | −2.087 |

**Key insight:** Que generates much better net EPPD when Ace declares (+2.887 vs
+1.849 for Meeks), despite Que's personal declarations being worse (+0.683 vs
+2.542). This confirms Que is a better support player.

---

## 2. The Structural Baseline: Why Seat 2 Gets Set More

Before attributing Ace sets to bad luck, we must establish the correct baseline.
Is seat 2 inherently worse than seats 1/3?

### Partner Bot vs Opponent Bot Set Rates (ALL Matches)

| Role | Declarations | Sets | Set Rate | Avg Bid |
|------|-------------|------|----------|---------|
| Partner bot (seat 2) | 2,288 | 255 | **11.15%** | 4.98 |
| Opponent bots (seats 1, 3) | 4,676 | 260 | **5.56%** | 4.87 |

**The partner bot gets set at exactly 2x the opponent rate.** This holds
even after controlling for bid level:

| Bid Level | Partner Set% (n) | Opponent Set% (n) | Ratio |
|-----------|-----------------|-------------------|-------|
| 3 | 1.0% (293) | 0.2% (915) | 5.0x |
| 4 | 9.8% (143) | 4.4% (274) | 2.2x |
| 5 | 6.6% (776) | 3.3% (1,671) | 2.0x |
| 6 | 18.5% (875) | 10.4% (1,530) | 1.8x |
| 7 | 26.6% (64) | 15.0% (127) | 1.8x |

At every meaningful bid level, the partner bot sets at roughly 2x the
opponent rate.

### Control Group: Bot-vs-Bot Matches

This pattern persists even when seat 0 is another bot:

| Seat 0 Player | Partner Set% | Opponent Set% | Ratio |
|---------------|-------------|---------------|-------|
| FlexBot-A | 10.6% (955) | 6.8% (1,955) | 1.6x |
| Claude | 17.5% (57) | 8.3% (157) | 2.1x |
| **All players** | **11.15%** (2,288) | **5.56%** (4,676) | **2.0x** |

**Root cause hypothesis:** The bot at seat 2 bids assuming bot-quality support
from its partner, but receives human-quality (or FlexBot-quality) support play.
Bot-bot partnerships coordinate trick sequencing and trump management more
effectively than human-bot or FlexBot-bot partnerships. The better the seat 0
player, the lower the partner bot's set rate.

### Correct Baseline

| Baseline | Rate | Use When |
|----------|------|----------|
| Opponent bot (seats 1, 3) | 5.56% | Comparing to what an opponent bot achieves |
| Partner bot (seat 2, all matches) | **11.15%** | Comparing individual players to typical partner performance |
| Partner bot (FlexBot-A only) | 10.6% | Comparing to automated baseline |

**The 11.15% partner baseline is the correct reference** for evaluating whether
a specific player's Ace performs better or worse than expected.

---

## 3. Ace Set Details

### Meeks: 11 Ace Sets

| Bid | Contract | Type | Tricks | Pts | Date |
|-----|----------|------|--------|-----|------|
| 5 | S | suit | 4 | −5 | Apr 2 |
| 10 | HIGH | moon | 7 | −20 | Apr 3 |
| 5 | LOW | low | 4 | −5 | Apr 4 |
| 6 | LOW | low | 2 | −6 | Apr 4 |
| 7 | LOW | low | 6 | −7 | Apr 4 |
| 6 | D | suit | 5 | −6 | Apr 5 |
| 5 | D | suit | 4 | −5 | Apr 5 |
| 5 | D | suit | 4 | −5 | Apr 5 |
| 6 | D | suit | 4 | −6 | Apr 6 |
| 5 | C | suit | 3 | −5 | Apr 6 |
| 5 | S | suit | 3 | −5 | Apr 7 |

**Total Ace set damage: −75 points**

Patterns:
- **LOW contracts are the worst**: 3 of 11 sets (33.3% set rate on LOW)
- **Diamonds and Spades cluster**: 5 of 11 are D or S suit contracts
- **Sets cluster Apr 4–6**: 8 of 11 sets in a 3-day window
- **1 devastating moon set**: −20 points on a HIGH moon

### Que: 8 Ace Sets

| Bid | Contract | Type | Tricks | Pts | Date |
|-----|----------|------|--------|-----|------|
| 6 | LOW | low | 3 | −6 | Apr 5 |
| 6 | LOW | low | 4 | −6 | Apr 6 |
| 6 | S | suit | 5 | −6 | Apr 6 |
| 5 | D | suit | 3 | −5 | Apr 6 |
| 6 | S | suit | 5 | −6 | Apr 6 |
| 6 | C | suit | 5 | −6 | Apr 6 |
| 6 | H | suit | 4 | −6 | Apr 7 |
| 6 | H | suit | 5 | −6 | Apr 7 |

**Total Ace set damage: −47 points**

Patterns:
- **LOW contracts again**: 2 of 8 sets (20% set rate on LOW)
- **All 8 sets are at bid levels 5-6**: no extreme bids
- **Sets cluster Apr 6–7**: 6 of 8 in the last 2 days
- **No moon sets**: Que's Ace doesn't bid moons

### Ace Set Rate by Contract Type

| Contract | Meeks Ace Set% (n) | Que Ace Set% (n) |
|----------|-------------------|-----------------|
| Suit | 11.9% (59) | 12.2% (49) |
| HIGH | 20.0% (5) | 0.0% (3) |
| LOW | **33.3%** (9) | **20.0%** (10) |

**LOW contracts are the Achilles heel** — both players' Aces struggle most
on LOW, consistent with the known Bud bot weakness on LOW (82.2% make rate
in the Meeks vs Bud report).

### Ace Set Rate by Bid Level

| Bid Level | Meeks Ace Set% (n) | Que Ace Set% (n) |
|-----------|-------------------|-----------------|
| 3 | 0.0% (4) | — |
| 4 | 0.0% (3) | 0.0% (1) |
| 5 | **16.7%** (36) | 5.9% (17) |
| 6 | 12.0% (25) | **17.1%** (41) |
| 7 | 33.3% (3) | 0.0% (3) |
| 10 | 50.0% (2) | — |

---

## 4. Match Impact Analysis

### Matches Where Ace Sets Potentially Flipped the Outcome

A match is "FLIPPED" if the loss margin is smaller than the total Ace-set
swing (removing penalty + adding estimated make value).

**Meeks — 2 Flipped Matches:**

| Match | Score | Margin | Ace Sets | Set Pts | Swing | Adj Margin | Impact |
|-------|-------|--------|----------|---------|-------|------------|--------|
| 48 | 44–54 | −10 | 1 | −7 | +13 | +3 | **FLIPPED** |
| 49 | 35–52 | −17 | 2 | −11 | +20 | +3 | **FLIPPED** |
| 9 | 39–55 | −16 | 1 | −5 | +9 | −7 | contributed |
| 17 | 14–52 | −38 | 1 | −20 | +27 | −11 | contributed |
| 490 | 44–58 | −14 | 1 | −5 | +9 | −5 | contributed |
| 632 | 22–52 | −30 | 2 | −10 | +16 | −14 | contributed |

**Que — 2 Flipped Matches:**

| Match | Score | Margin | Ace Sets | Set Pts | Swing | Adj Margin | Impact |
|-------|-------|--------|----------|---------|-------|------------|--------|
| 495 | 52–57 | −5 | 1 | −6 | +10 | +5 | **FLIPPED** |
| 498 | 45–54 | −9 | 1 | −6 | +11 | +2 | **FLIPPED** |
| 488 | 21–52 | −31 | 1 | −6 | +9 | −22 | contributed |
| 525 | 37–54 | −17 | 1 | −5 | +8 | −9 | contributed |
| 680 | 26–52 | −26 | 1 | −6 | +11 | −15 | contributed |
| 888 | 23–56 | −33 | 1 | −6 | +11 | −22 | contributed |

### Ace Sets by Match Outcome

| Player | Outcome | Matches | Ace Sets | Ace Set Pts | Ace Set% |
|--------|---------|---------|----------|-------------|----------|
| **Meeks** | Win | 17 | 3 | −17 | 7.1% |
| **Meeks** | Loss | 13 | 8 | −58 | **25.8%** |
| **Que** | Win | 14 | 2 | −12 | 5.7% |
| **Que** | Loss | 11 | 6 | −35 | **22.2%** |

**Critical finding:** Ace set rate in losses is 3.5–4x higher than in wins.
In matches they lose, both players' Aces get set ~23–26% of the time. This
doesn't prove causation (losing matches may feature more aggressive play by
both teams), but shows Ace sets concentrate disproportionately in losses.

---

## 5. Adjusted Metrics

### Maximum Adjustment (All Ace Sets → Makes)

This is the upper bound — what if Ace NEVER got set?

| Metric | Meeks Raw | Meeks Adj | Que Raw | Que Adj |
|--------|-----------|-----------|---------|---------|
| Win rate | 56.7% (17-13) | **63.3%** (19-11) | 56.0% (14-11) | **64.0%** (16-9) |
| Avg margin | +2.1 | **+6.2** | +2.9 | **+6.2** |
| Flipped matches | — | 2 | — | 2 |
| Total swing | — | +121 pts | — | +81 pts |

**Both players converge to an identical +6.2 adjusted margin**, suggesting
equal underlying skill once Ace variance is removed.

### Structural Adjustment (vs 11.15% Partner Baseline)

Using the correct baseline (partner bot gets set at 11.15% across all matches):

| Metric | Meeks | Que |
|--------|-------|-----|
| Actual Ace set rate | 15.1% | 12.9% |
| Expected set rate (baseline) | 11.15% | 11.15% |
| Expected sets | 8.1 | 6.9 |
| Actual sets | 11 | 8 |
| **Excess sets** | **~3** | **~1** |
| Excess damage (pts) | ~42 | ~13 |
| EPPD adjustment | +0.138 | +0.048 |
| **Adjusted net EPPD** | **+0.347** | **+0.309** |

**After structural adjustment, Meeks gains a slight edge** (+0.347 vs +0.309),
compared to the raw numbers where Que led (+0.261 vs +0.209). The ~3 excess
Ace sets Meeks suffered account for most of the raw EPPD gap.

### Aggressive Adjustment (vs 5.56% Opponent Baseline)

Using the opponent bot baseline (overstates the effect but answers "what if
Ace played like an opponent?"):

| Metric | Meeks | Que |
|--------|-------|-----|
| Expected sets at 5.56% | 4.1 | 3.5 |
| Excess sets | 7 | 4.5 |
| Excess damage (pts) | ~99 | ~60 |
| EPPD adjustment | +0.323 | +0.215 |
| **Adjusted net EPPD** | **+0.532** | **+0.476** |

---

## 6. Answer: How Much Is Ace's Fault?

### Meeks

| Component | Points Impact | % of Raw Margin Gap |
|-----------|--------------|---------------------|
| Total Ace set damage | −75 pts (11 sets) | — |
| Excess vs structural baseline | −42 pts (~3 excess sets) | — |
| Matches potentially flipped | 2 of 13 losses | 15% of losses |
| Win rate impact | 56.7% → 63.3% (max) | +6.6 pp |
| EPPD impact (structural) | +0.138 EPPD | 66% of raw EPPD |

**Verdict:** Ace's excess sets (beyond the structural 11.15% baseline) account
for ~42 points of damage across 30 matches — roughly 1.4 points per match.
This is meaningful but not enormous. The larger story is that the partner bot
structurally gets set at 2x the opponent rate regardless of who plays at
seat 0. Meeks is somewhat unlucky with Ace (3 excess sets above baseline),
but the majority of Ace's damage is "expected."

### Que

| Component | Points Impact | % of Raw Margin Gap |
|-----------|--------------|---------------------|
| Total Ace set damage | −47 pts (8 sets) | — |
| Excess vs structural baseline | −13 pts (~1 excess set) | — |
| Matches potentially flipped | 2 of 11 losses | 18% of losses |
| Win rate impact | 56.0% → 64.0% (max) | +8.0 pp |
| EPPD impact (structural) | +0.048 EPPD | 18% of raw EPPD |

**Verdict:** Que's Ace is essentially at the structural baseline (12.9% vs
11.15% expected). Only ~1 excess set above baseline. Que's Ace sets are
mostly "normal" partner bot variance, not bad luck. Que compensates for
Ace's structural weakness through exceptional defense (14.1% opponent set
rate — the highest of any player).

### Comparative

| Question | Meeks | Que |
|----------|-------|-----|
| Is Ace unlucky beyond structural baseline? | **Yes** (3 excess sets) | **No** (~1 excess set) |
| How much does Ace cost in raw points? | −75 total, −42 excess | −47 total, −13 excess |
| Would removing ALL Ace sets change the win rate? | +6.6 pp (56.7→63.3%) | +8.0 pp (56.0→64.0%) |
| After adjustment, who is stronger? | +6.2 adj margin | +6.2 adj margin |
| Main "hidden" strength? | Superior declaration (+2.542 net EPPD) | Superior defense (14.1% opp set rate) |

**Bottom line:** Both players are approximately equal after Ace adjustment.
Meeks's advantage in declaration (+2.542 net EPPD when bidding) is offset by
Que's advantage in defense (14.1% opponent disruption rate). The apparent
gap in raw stats is largely explained by ~3 extra Ace sets for Meeks and
Que's exceptional defensive play.

---

## 7. Strategic Implications

### For Both Players

1. **LOW contracts are the biggest Ace liability.** Both players' Aces struggle
   most on LOW (33% and 20% set rates). When Ace bids LOW, expect trouble.
   Consider more aggressively outbidding Ace on LOW to keep the declaration
   at seat 0 where the human has more control.

2. **The structural 2x penalty is real.** The partner bot will always get set
   more than opponents because human support play is inherently weaker than
   bot support play. This is a game design property, not a player failure.

3. **Ace sets concentrate in losses.** 23-26% Ace set rate in losses vs 6-7%
   in wins. A single Ace set rarely costs a match alone, but combined with
   other bad hands, it amplifies losing streaks.

### For Meeks Specifically

4. **Meeks may be a weak support player.** Ace's 15.1% set rate (vs 12.9% for
   Que) suggests Meeks doesn't support partner declarations as well. When Ace
   wins the bid, focus on feeding Ace winning tricks rather than competing for
   tricks independently.

5. **The Apr 4-6 Ace set cluster** (8 of 11 sets) coincides with Meeks's
   overall performance decline. Ace sets may have contributed to tilt.

### For Que Specifically

6. **Que's strength is defense, not Ace luck.** Que doesn't need better Ace
   luck — Que compensates through the highest opponent disruption rate of any
   player (14.1%). This is sustainable and skill-based.

---

## Methodology

### Data

All statistics queried directly from the Render production database
(`bideuchre-db`) on 2026-04-07. Complete matches only (`matches.status = 'complete'`,
`hands.status = 'complete'`).

### Definitions

- **Ace:** The AI bot at seat 2 (human's partner)
- **Set:** Team took fewer tricks than the winning bid
- **Structural baseline:** Partner bot (seat 2) set rate across all 2,288
  declarations in the database = 11.15%
- **Opponent baseline:** Opponent bot (seats 1, 3) set rate across all 4,676
  declarations = 5.56%
- **Ace set swing:** For each Ace set, the counterfactual is a make. Swing =
  (−points_from_set) + (tricks_team0 as make points)
- **Adjusted margin:** Original margin + sum of Ace set swings for that match
- **Flipped match:** A loss where adjusted margin > 0

### Caveats

1. **Sample sizes are moderate** (62-73 Ace declarations per player). Differences
   of a few sets are within statistical noise.
2. **The counterfactual assumes all sets become makes** with points = tricks won.
   In reality, some sets would have remained sets even with perfect support.
3. **"Flipped" matches assume only Ace sets change.** Other hands in the match
   could also have gone differently with different play.
4. **Both players face the same bud_bot AI** but with different random seeds,
   making strict controlled comparison impossible.
5. **No decision-level data** — we can see outcomes but not the specific plays
   that led to Ace getting set (was it Ace's bid calibration or the human's
   support play?).

## Outcome

Analysis committed as `plans/sessions/2026-04-07_ace_set_adjustment.md`.
Covers all three player comparisons (Que, Meeks, and the structural partner-bot
baseline). Written for the analyst worktree; orchestrator can share methodology
with analyst-b and analyst-c lanes for cross-referencing in their reports.
