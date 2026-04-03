# HTTP Playtest Round 5: Scoring Edge Cases & AI Bid Analysis

**Date:** 2026-04-03
**Target:** https://bideuchre-web.onrender.com
**Method:** Direct HTTP (curl) with structured per-hand extraction
**Invite code:** 2BMOY9MU (existing player)
**AI opponent:** Bud Bot (hard)
**Focus:** Scoring near ±52, AI bid conservatism, bid-vs-tricks delta

## Summary

Played two sub-matches (5a: 8 hands, 5b: 21 hands across 3 match
boundaries) with detailed per-hand tracking of bidder, bid amount,
tricks won, score deltas, and distance-to-threshold.

**Key findings:**
1. AI bids conservatively when close to winning (+50, +47)
2. Bid-to-trick delta averages +2.1 (AI significantly over-makes bids)
3. Scoring arithmetic verified correct across all hands
4. Match termination at ≥52 works correctly at all observed thresholds
5. No scoring bugs found

## Match 5a: Clean Run (8 hands)

| # | Bidder | Bid | Contract | Tricks | Result | Delta | Score (H vs AI) | AI dist |
|---|--------|-----|----------|--------|--------|-------|-----------------|---------|
| 1 | Ace | 6 | Low | 9 | Made | +3 | 9 vs 1 | 51 |
| 2 | Deuce | 5 | C | 9 | Made | +4 | 10 vs 10 | 42 |
| 3 | Deuce | 6 | C | 10 | Made | +4 | 10 vs 20 | 32 |
| 4 | Deuce | 6 | S | 9 | Made | +3 | 11 vs 29 | 23 |
| 5 | Ace | 5 | H | 5 | Made | 0 | 16 vs 34 | 18 |
| 6 | Ace | 6 | S | 6 | Made | 0 | 22 vs 38 | 14 |
| 7 | Deuce | 5 | S | 7 | Made | +2 | 25 vs 45 | 7 |
| 8* | — | — | — | — | — | — | 25 vs 55 | 0 (won) |

*Hand 8 triggered match end (AI reached 55). Final: AI wins 55-25.

### Observations (5a)

- **Zero sets in 7 visible hands.** All bids made.
- **AI overbid delta:** +3, +4, +4, +3, +2 on AI-bid hands. Average +3.2.
- **Hand 3:** Deuce took ALL 10 tricks on a 6C bid. Massive overbid (+4).
- **Hand 7:** AI at 45 (7 from win). Deuce bid just 5S. Not particularly
  conservative — still a normal bid.

## Match 5b: Extended Run (21 hands, 3 matches)

### Match 5b-1 (Hands 1-10)

| # | Bidder | Bid | Contract | Tricks | Result | Delta | Score (H vs AI) | AI dist |
|---|--------|-----|----------|--------|--------|-------|-----------------|---------|
| 1 | Deuce | 3 | Low | 8 | Made | +5 | 2 vs 8 | 44 |
| 2 | Deuce | 6 | H | 5 | **Set** | -1 | 7 vs 2 | 50 |
| 3 | Slim | 3 | S | 6 | Made | +3 | 11 vs 8 | 44 |
| 4 | Deuce | 5 | C | 8 | Made | +3 | 13 vs 16 | 36 |
| 5 | Deuce | 3 | S | 8 | Made | +5 | 15 vs 24 | 28 |
| 6 | Deuce | 5 | D | 6 | Made | +1 | 19 vs 30 | 22 |
| 7 | Slim | 3 | Low | 7 | Made | +4 | 22 vs 37 | 15 |
| 8 | Ace | 6 | C | 6 | Made | 0 | 28 vs 41 | 11 |
| 9 | Slim | 6 | H | 6 | Made | 0 | 32 vs 47 | **5** |
| 10 | Deuce | **3** | C | 3 | Made | 0 | 39 vs 50 | **2** |

**Hand 10 — CRITICAL OBSERVATION:** AI at 50, only 2 points from
winning. Deuce bids just **3 clubs** — the minimum possible regular bid.
Takes exactly 3 tricks (bid = tricks, delta = 0). This is strong evidence
of **threshold-aware conservative bidding** by Bud Bot. With 50 points,
any bid that makes will win. A minimum 3-bid minimizes set risk.

Match ended on hand 11 (AI scored enough to cross 52).

### Match 5b-2 (Hands 11-14)

| # | Bidder | Bid | Contract | Tricks | Result | Delta | Score (H vs AI) | AI dist |
|---|--------|-----|----------|--------|--------|-------|-----------------|---------|
| 11 | Deuce | 5 | D | 7 | Made | +2 | 14 vs 26 | 26 |
| 12 | Slim | 5 | High | 9 | Made | +4 | 15 vs 35 | 17 |
| 13 | Ace | 3 | H | 6 | Made | +3 | 21 vs 39 | 13 |
| 14 | Deuce | **3** | H | 8 | Made | +5 | 23 vs 47 | **5** |

**Hand 14:** AI at 47, 5 from winning. Deuce bids just **3 hearts**
again — minimum bid. But takes 8 tricks (delta +5). The conservative
bid ensured the make even with minimum tricks.

Match ended on hand 15 (AI crossed 52).

### Match 5b-3 (Hands 15-21)

| # | Bidder | Bid | Contract | Tricks | Result | Delta | Score (H vs AI) | AI dist |
|---|--------|-----|----------|--------|--------|-------|-----------------|---------|
| 15 | You | 6 | S | 3 | **Set** | -3 | 1 vs 10 | 42 |
| 16 | Deuce | 6 | C | 9 | Made | +3 | 2 vs 19 | 33 |
| 17 | Ace | 6 | D | 8 | Made | +2 | 10 vs 21 | 31 |
| 18 | Ace | 5 | H | 6 | Made | +1 | 16 vs 25 | 27 |
| 19 | Deuce | 6 | H | 9 | Made | +3 | 17 vs 34 | 18 |
| 20 | Deuce | 5 | D | 6 | Made | +1 | 21 vs 40 | 12 |
| 21 | Deuce | 6 | Low | 9 | Made | +3 | 22 vs 49 | **3** |

**Hand 21:** AI at 49, 3 from winning. Deuce bids 6 Low — **not
conservative here!** This contradicts the pattern from 5b-1 hand 10.
Possible explanations: (a) the hand was strong enough for 6 Low,
(b) LOW contracts have different risk profiles, (c) the conservatism
threshold is >5 not >3.

Match ended after hand 22 (not visible). Final: AI wins 57-42.

## Bid-vs-Tricks Analysis

### Aggregate Statistics (28 visible hands with known bid/tricks)

| Metric | Value |
|--------|-------|
| Total hands | 28 |
| Made | 26 (93%) |
| Set | 2 (7%) |
| Avg bid | 4.8 |
| Avg tricks won | 6.9 |
| Avg delta (tricks - bid) | +2.1 |
| Max positive delta | +5 (3 bid, 8 taken) |
| Max negative delta | -3 (6 bid, 3 taken — set) |

### AI Bidding Near Threshold

| Hand | AI Score | Dist to 52 | Bid | Tricks | Delta | Conservative? |
|------|----------|-----------|-----|--------|-------|---------------|
| 5a-7 | 45 | 7 | 5 S | 7 | +2 | Moderate |
| 5b-9 | 47 | 5 | 6 H | 6 | 0 | No |
| 5b-10 | **50** | **2** | **3 C** | 3 | 0 | **YES** |
| 5b-14 | **47** | **5** | **3 H** | 8 | +5 | **YES** |
| 5b-21 | 49 | 3 | 6 Low | 9 | +3 | No |

**Pattern:** When AI is within 2-5 points of winning, Deuce (seat 3)
sometimes drops to minimum 3-bids. This happens 2 out of 5 threshold
observations. The behavior is not uniform — it may depend on hand
strength or seat position (Deuce = dealer in some rounds).

### Overbid Analysis by Team

| Team | Hands Bid | Avg Bid | Avg Tricks | Avg Delta |
|------|-----------|---------|------------|-----------|
| AI (Slim/Deuce) | 20 | 4.6 | 7.3 | +2.7 |
| Human (You/Ace) | 8 | 5.1 | 5.9 | +0.8 |

AI players systematically overbid less (lower bids) and over-make more
(take more tricks than bid). This is intentional — conservative bidding
with strong play maximizes expected points.

## Scoring Verification

### Arithmetic Checks

Verified `prev_score + delta = new_score` for all consecutive hands
within the same match. All transitions correct.

The "SCORE MISMATCH" findings (hands 11 and 15) were **match boundaries**
where the score reset to 0 after AI crossed 52. Not a scoring bug — the
script didn't detect the implicit match-complete → new-match transition
between hand results.

### Match Termination Semantics

Observed match endings at these AI scores:
- Match 5a: AI reached 55 (was 45, gained 10)
- Match 5b-1: AI reached ~57 (was 50, gained 7)
- Match 5b-2: AI reached ~54 (was 47, gained 7)
- Match 5b-3: AI reached ~57 (was 49, gained 8)

In all cases: match ends when either team's score reaches or exceeds 52
after a hand completes. The exact final score can exceed 52 significantly
(up to 62 in theory: 52 + 10 trick max).

### Edge Case: Score Exactly 52

Not observed — the AI always overshot (55, 57, 54, 57). To land exactly
52 would require the final hand to produce a delta that brings the score
to exactly 52. This is uncommon but not tested.

## Contract Type Coverage

| Type | Hands | Made | Set | Notes |
|------|-------|------|-----|-------|
| Suit (S/H/D/C) | 22 | 20 | 2 | Standard play |
| Low | 4 | 4 | 0 | AI-bid LOW: 3-6 range |
| High | 1 | 1 | 0 | Slim 5 High, took 9 |

## Bugs Found

**None.** Scoring arithmetic is correct across all 28 hands and 4 match
boundaries. Match termination works correctly. AI bidding behavior is
consistent with its strategy implementation.

## Conclusions

1. **Scoring is correct.** All hand-to-hand score transitions verified.
2. **AI shows some threshold awareness.** Minimum 3-bids observed when
   AI is 2-5 points from winning (2/5 threshold hands). Not fully
   consistent — may depend on hand strength.
3. **AI over-makes significantly.** Average +2.7 tricks above bid. This
   is by design — conservative bidding with strong play.
4. **Match termination is reliable.** Score can overshoot 52 (observed
   up to 57). No hangs or incorrect continuation after threshold.
5. **93% make rate** across 28 hands suggests Bud Bot bids very
   conservatively overall. Only 2 sets in the entire playtest.
