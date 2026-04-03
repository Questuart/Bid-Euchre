# Hybrid Playtest: Game Flow Statistics

**Date:** 2026-04-03
**Player:** Claude-HYB vs Bud Bot (all matches)
**Sample:** 4 completed matches, 35 total hands (31 with full data, 4 uncaptured final hands)
**Method:** Auto-play bot (always passes, plays first legal card). Stats from per-hand result screen parsing.

> **Caveat:** These statistics reflect automated play where the human seat always passes and plays the first legal card. Human gameplay would show different patterns (more varied bidding, strategic card play, longer hand durations).

## Match-Level Statistics

| Match | Hands | Final Score | Winner | Duration (auto) |
|-------|-------|-------------|--------|----------------|
| 1 | 7 | 10 – 53 | AI | ~3 min (est) |
| 2 | 8 | 27 – 53 | AI | ~5 min (est) |
| 3 | 10 | 27 – 52 | AI | ~6 min (est) |
| 4 | 10 | 41 – 59 | AI | 5:50 (measured) |

| Metric | Value |
|--------|-------|
| **Avg hands per match** | **8.75** |
| **Median hands per match** | **9** |
| **Range** | **7–10** |
| **Avg hand duration (automated)** | **~35 sec** |
| **Avg match duration (automated)** | **~5 min** |
| **Estimated human match duration** | **10–20 min** (based on game info: "6–12 hands, 10–20 minutes") |

### Score Distribution

| Match | Human Final | AI Final | Margin | Points/Hand (H) | Points/Hand (AI) |
|-------|-------------|----------|--------|-----------------|-----------------|
| 1 | 10 | 53 | -43 | 1.43 | 7.57 |
| 2 | 27 | 53 | -26 | 3.38 | 6.63 |
| 3 | 27 | 52 | -25 | 2.70 | 5.20 |
| 4 | 41 | 59 | -18 | 4.10 | 5.90 |

**Average human points/hand:** 2.90
**Average AI points/hand:** 6.33
**Average margin:** -28.0 per match

## Contract Type Distribution (31 captured hands)

| Type | Count | % | Description |
|------|-------|---|-------------|
| **Suit** | 20 | **64.5%** | Trump suit (♠♥♦♣) with bowers |
| **High** | 6 | **19.4%** | No-trump, Ace high |
| **Low** | 5 | **16.1%** | No-trump, 10 high |
| **Moon** | 0 | 0% | Not observed |
| **Loner** | 0 | 0% | Not observed |

### Suit Contract Breakdown

| Suit | Count | % of Suit Bids |
|------|-------|---------------|
| ♣ Clubs | 8 | 40% |
| ♠ Spades | 6 | 30% |
| ♥ Hearts | 4 | 20% |
| ♦ Diamonds | 2 | 10% |

Clubs dominate suit bids. Diamonds are underrepresented.

## Bid Level Distribution (31 captured hands)

| Bid Level | Count | % |
|-----------|-------|---|
| 3 | 10 | **32.3%** |
| 4 | 2 | 6.5% |
| 5 | 13 | **41.9%** |
| 6 | 6 | **19.4%** |
| 7–10 | 0 | 0% |

| Metric | Value |
|--------|-------|
| **Average bid level** | **4.52** |
| **Median bid level** | **5** |
| **Mode bid level** | **5** |

Most common: 5 (42%), then 3 (32%). No bids above 6 observed. The game predicts "expect 6–12 hands" which is close to observed 7–10.

## Outcome Distribution (31 captured hands)

| Outcome | Count | % |
|---------|-------|---|
| Made | 28 | **90.3%** |
| Set | 3 | **9.7%** |

Sets observed:
1. Match 1, H1: You bid 5♠, took 2 (badly set)
2. Match 3, H2: Ace bid 6♣, took 5 (narrowly set)
3. Match 3, H7: Deuce bid 6 Low, took 4 (set)

**All sets occurred on bids of 5 or 6.** No sets on bids of 3 or 4.

## Declaring Team Distribution (31 captured hands)

| Team | Count | % | Make Rate |
|------|-------|---|-----------|
| AI (Slim/Deuce) | 22 | **71.0%** | 95.5% (21/22) |
| Human (You/Ace) | 9 | **29.0%** | 77.8% (7/9) |

The AI team declares much more often because the human player always passes. Ace (human partner) bids when it can, but only wins the auction 29% of the time.

### Bidder Breakdown

| Bidder | Count | % | Team |
|--------|-------|---|------|
| Deuce | 14 | **45.2%** | AI |
| Slim | 8 | 25.8% | AI |
| Ace | 8 | 25.8% | Human |
| You | 1 | 3.2% | Human |

Deuce (AI) is the most aggressive bidder, winning nearly half of all auctions.

## Trick Distribution (31 captured hands)

| Tricks by Declarer | Count | % | Notes |
|-------------------|-------|---|-------|
| 2 | 1 | 3.2% | Badly set (bid 5) |
| 4 | 2 | 6.5% | Set / barely made |
| 5 | 4 | 12.9% | Barely made or set |
| 6 | 6 | 19.4% | Common |
| 7 | 7 | **22.6%** | Most common |
| 8 | 6 | 19.4% | Common |
| 9 | 4 | 12.9% | Strong hand |
| 10 | 1 | 3.2% | Perfect sweep |

| Metric | Value |
|--------|-------|
| **Average tricks by declarer** | **6.77** |
| **Median tricks by declarer** | **7** |
| **Avg defender tricks** | **3.23** |

The declaring team wins an average of 6.8 out of 10 tricks — a comfortable margin over typical bids of 4-5.

## Points per Hand Analysis

### By Contract Type

| Type | Avg Declarer Tricks | Avg Bid | Surplus |
|------|-------------------|---------|---------|
| Suit (20h) | 7.00 | 4.65 | +2.35 |
| High (6h) | 7.17 | 4.50 | +2.67 |
| Low (5h) | 6.00 | 4.40 | +1.60 |

High contracts produce the most tricks for declarers. Low contracts are tighter.

### Scoring Summary

| Metric | Value |
|--------|-------|
| Total points scored (human, 4 matches) | 105 |
| Total points scored (AI, 4 matches) | 217 |
| Total hands played | 35 |
| Avg points per hand (total, both teams) | 9.2 |
| Expected points per hand (theory: 10) | 10.0 |

The average total points per hand (9.2) is slightly below 10 because sets produce fewer total points (e.g., bid 5 set = -5 + defender_tricks, which sums to less than 10).

## Key Takeaways

1. **Matches are 7–10 hands** (avg 8.75). The game's estimate of "6–12 hands" is accurate.
2. **Suit contracts dominate** (65%) over no-trump (35%).
3. **Bids cluster at 3 and 5** — the 4-bid is rare (6.5%).
4. **Sets are uncommon** (~10%) and only occur on bids of 5+.
5. **Declarers win ~7 of 10 tricks** on average, well above typical bid levels.
6. **No Moon or Loner bids observed** across 31 hands — these are rare contract types.
7. **Automated match takes ~5-6 min**, human matches should take 10-20 min per the game's estimate.
8. **Clubs are the most common trump suit** (40% of suit bids) — possibly a Bud Bot preference.

## Outcome

No issues to file — this is a statistics collection round. Data will inform the game's UI copy (hand/duration estimates) and strategy development.
