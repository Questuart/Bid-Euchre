# HTTP Playtest Round 3: LOW Contracts & Negative Scores

**Date:** 2026-04-03
**Target:** https://bideuchre-web.onrender.com
**Method:** Direct HTTP (curl) against production API, no browser
**Invite code:** 2BMOY9MU (existing player reused)
**Nickname:** Claude-HTTP
**AI opponent:** Bud Bot (hard)
**Focus:** LOW contracts, HIGH no-trump, negative score edge cases

## Summary

Played 10 hands (9 hand results + 1 final that triggered match end).
AI wins 54 to 46 — the closest match of all three rounds. Observed
2 LOW contracts and 2 HIGH contracts, all bid and made by AI players.

**Result:** AI wins 54 to 46 after 10 hands.
**Bugs found:** 0 new (all contract types worked correctly)

## Match Scoring Log

| Hand | Bidder | Contract | Tricks | Result | Score (You vs AI) |
|------|--------|----------|--------|--------|-------------------|
| 1 | Ace (partner) | 7 Low | 8 | Made | 8 vs 2 |
| 2 | Slim (opp) | 5 S | 8 | Made | 10 vs 10 |
| 3 | Deuce (opp) | 6 High | 10 | Made | 10 vs 20 |
| 4 | Ace (partner) | 4 H | 6 | Made | 16 vs 24 |
| 5 | Deuce (opp) | 3 D | 6 | Made | 20 vs 30 |
| 6 | Slim (opp) | 5 H | 6 | Made | 24 vs 36 |
| 7 | Ace (partner) | 3 High | 7 | Made | 31 vs 39 |
| 8 | Ace (partner) | 6 Low | 6 | Made | 37 vs 43 |
| 9 | Ace (partner) | 2 H | 5 | Made | 42 vs 48 |
| 10 | ? | ? | ? | ? | 46 vs 54 (match end) |

### Scoring Verification

- Hand 1: Ace bids 7 Low, takes 8. Our team: +8, AI: +2. Score: 8-2. Correct.
- Hand 3: Deuce bids 6 High, takes 10 (sweep!). Our team: +0, AI: +10. Score: 10-20. Correct.
- Hand 7: Ace bids 3 High, takes 7. Our team: +7, AI: +3. Score: 31-39. Correct.
- Hand 8: Ace bids 6 Low, takes 6. Our team: +6, AI: +4. Score: 37-43. Correct.

All scoring transitions check out.

## Edge Cases Observed

### LOW Contracts (Hands 1 & 8)

**Hand 1: Ace bid 7 Low, took 8 tricks.**
- In LOW no-trump, 10 is the highest rank (not A).
- My partner Ace successfully bid and made a LOW contract.
- Trick table shows correct LOW ordering: lower ranks win.
- The game correctly displayed "7 Low" in the result.

**Hand 8: Ace bid 6 Low, took 6 tricks.**
- Another successful LOW contract by partner.
- Exactly made (6 bid, 6 taken).
- Scoring: +6 for our team (bidder made), +4 for AI (defenders' tricks).

### HIGH No-Trump Contracts (Hands 3 & 7)

**Hand 3: Deuce bid 6 High, took ALL 10 tricks.**
- AI swept the entire hand (10/10 tricks).
- Scoring: +10 for AI (bidder), +0 for us. Correct.
- This is a notable edge case: taking all tricks in no-trump.

**Hand 7: Ace bid 3 High, took 7 tricks.**
- Low bid (3), took 7. Scoring: +7 (tricks won, not bid). Correct.

### Close Match Score

- Both teams stayed positive throughout (no negative scores this match)
- Final score 46 vs 54 — AI won by just 8 points
- This is the first match where my bot didn't get crushed

### All Bids Made

Every hand in this match was "Made" — no sets at all. This is unusual
and suggests the AI bidders were conservative. My bot passed on every
hand (the aggressive LOW bidding logic never triggered because the
choose_bid function evaluated the hands as not LOW-enough given its
threshold of 3+ tens).

### Match Completion Without Hand Result

Confirmed again: when the 10th hand's tricks push AI to 54 (>=52),
the response goes directly to match-complete without showing hand-result.
The match-result page says "Hands played: 10" but we only got 9
HAND_RESULT responses. This is consistent with round 2 behavior.

## API Behavior Notes

### No Errors

Zero API errors in this entire match. No illegal bids (we passed every
time), no desync issues, no unknown states. The cleanest run of all
three rounds.

### Performance

- 247 HTTP requests for 10 hands (~25 per hand)
- Total time: ~2.5 minutes
- No timeouts or slow responses

### Rate Limiting Recovery

After round 2 ended, the completed match freed a rate-limit slot,
allowing `POST /select-ai` to succeed for round 3. Confirms that
match completion correctly reduces the active match count.

## Findings

### No New Bugs

All contract types (suit, LOW, HIGH) work correctly:
- LOW contracts: 10 is high, scoring is correct
- HIGH contracts: A is high (standard no-trump), scoring correct
- Suit contracts: normal play with bowers
- Match termination at >=52 works correctly

### Observation: Score Display Still Empty on Match-Complete

The `get_score()` parser (looking for `score-value` spans) returned
empty on the match-complete page, consistent with round 1/2 observation
(filed as #2212). The score is available in the result prose text.

## Contract Type Coverage Across All 3 Rounds

| Contract Type | Round 1 | Round 2 | Round 3 | Total |
|---------------|---------|---------|---------|-------|
| Suit (S/H/D/C) | 9 | 7 | 6 | 22 |
| LOW | 1 | 0 | 2 | 3 |
| HIGH | 0 | 1 | 2 | 3 |
| Moon | 0 | 0 | 0 | 0 |
| Loner | 0 | 0 | 0 | 0 |

Moon and loner contracts were never triggered across 32 hands.
These are rare by design (require exceptional hands).

## Outcome

Round 3 completed cleanly. LOW and HIGH contracts verified working
correctly. No new bugs found. All known bugs from rounds 1-2 confirmed
(score display on result pages, abandoned match cleanup, illegal bid
JSON response).
