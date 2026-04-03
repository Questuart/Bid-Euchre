# HTTP Playtest: Production Browser Game

**Date:** 2026-04-02
**Target:** https://bideuchre-web.onrender.com
**Method:** Direct HTTP (curl) against production API, no browser
**Invite code:** 2BMOY9MU
**Nickname:** Claude-HTTP
**AI opponent:** Bud Bot (hard)

## Summary

Played a full 13-hand match via raw HTTP POST/GET calls against the
production Render deployment. The game completed normally with a loss
(human team -1, AI team 52). All core game flows worked: invite code
redemption, nickname setting, AI selection, bidding, card play, trick
reveals, hand results, and match completion.

**Result:** AI wins 52 to -1 after 13 hands.

## Match Scoring Log

| Hand | Bidder | Contract | Tricks | Result | Cumulative (You vs AI) |
|------|--------|----------|--------|--------|----------------------|
| 1 | You | 6 C | 5 | Set | -6 vs 5 |
| 2 | You | 8 C | 5 | Set | -14 vs 10 |
| 3 | You | 6 S | 6 | Made | -8 vs 14 |
| 4 | You | 8 C | 6 | Set | -16 vs 18 |
| 5 | Slim | 7 Low | 7 | Made | -13 vs 25 |
| 6 | Ace | 6 H | 8 | Made | -5 vs 27 |
| 7 | You | 6 D | 6 | Made | 1 vs 31 |
| 8 | Deuce | 6 Low | 4 | Set | 7 vs 25 |
| 9 | You | 9 H | 6 | Set | -2 vs 29 |
| 10 | You | 9 D | 7 | Set | -11 vs 32 |
| 11 | Deuce | 6 S | 6 | Made | (not captured) |
| 12 | Slim | 5 C | 8 | Made | (not captured) |
| 13 | ? | ? | ? | ? | Final: -1 vs 52 |

### Scoring Verification

Spot-checked hands 1-5 against the rules (bidder gets -bid on set,
+tricks on make; defenders always get tricks won). All transitions
correct:

- Hand 1: 0+(-6)=-6 human, 0+5=5 AI. Correct.
- Hand 2: -6+(-8)=-14 human, 5+5=10 AI. Correct.
- Hand 3: -14+6=-8 human, 10+4=14 AI. Correct.
- Hand 4: -8+(-8)=-16 human, 14+4=18 AI. Correct.
- Hand 5: -16+3=-13 human, 18+7=25 AI. Correct.

## API Behavior Observations

### Flow

1. `POST /enter-code` (code=2BMOY9MU) -> 302 redirect to `/play/{uuid}`
   - Sets `bid_euchre_player` cookie (HttpOnly, 30d, SameSite=lax)
   - Already-redeemed code returns existing player's UUID
2. `GET /play/{uuid}` -> nickname prompt HTML
3. `POST /play/{uuid}/nickname` (nickname=...) -> model select partial
4. `POST /play/{uuid}/select-ai` (model_id=bud_bot) -> game board partial
5. Game loop: `/next`, `/bid`, `/play-card`, `/next-hand` as needed
6. Match ends: game board shows match-result with "Play Again" button

### Idempotency

The `turn_number` field prevents replay attacks. Stale turn numbers
return the current board state without modification. This worked
correctly throughout the test.

### Error Handling

- **Invalid UUID:** Returns 404 "Hand Not Found" page. Good.
- **Bid on wrong phase:** Returns current board state (desync recovery). Good.
- **Play-card on wrong phase:** Returns current board state. Good.
- **Rate limiting:** 429 on 5th concurrent match creation. Good.

### Authentication Model

- Cookie-based session with UUID in URL path
- All game actions use the URL path UUID, not just the cookie
- Cookie is only used for landing page reconnect
- No CSRF protection beyond SameSite=lax cookie (acceptable for game)

## Bugs Found

### BUG-1: Match completion page missing score in scoreboard widget

**Severity:** Low (cosmetic)
**Details:** On the match-complete page, the scoreboard widget
(`score-value` spans) is not present in the same format as during play.
The score is only visible in the result text ("Your team: -1, AI team: 52").
The `get_score()` regex that works during play (looking for
`score-value` class spans) fails on the match result page.

This is not a user-facing bug (human players see the result text), but
it indicates the match-result partial doesn't include the persistent
score bar that exists during gameplay.

### BUG-2: Abandoned matches accumulate with no cleanup

**Severity:** Medium (operational)
**Details:** Each `POST /select-ai` creates a new active match. If a
player navigates away or their match state becomes corrupted, the match
stays "active" indefinitely. The rate limit (429 after ~4 active matches)
prevents unbounded growth, but there's no automatic cleanup of abandoned
matches. The health endpoint shows `active_matches: 8` for 8 players,
suggesting 1:1 ratio, but my testing created 4 extra abandoned matches.

**Recommendation:** Add a match timeout (e.g., mark matches inactive
after 24h without activity) or add an "abandon match" endpoint.

### BUG-3: Score bar absent on hand-result interstitial

**Severity:** Low (cosmetic)
**Details:** During the hand-result display (between hands), the standard
scoreboard widget with `score-value` class spans is either not present or
uses a different format. The score is shown in the result text
("Match score: You 7 -- AI 3") but not in the same structured HTML as
during active play. Consistent score rendering across all game phases
would improve parsability for accessibility tools and automated testing.

## Game Flow Notes

### Auction Reveal Mechanic

The auction uses a reveal-step mechanic: after the human bids, AI bids
are hidden and revealed one at a time via `/next` calls. Each `/next`
reveals one auction action. After all bids are revealed, a "settle"
pause requires one more `/next` ("Auction complete. Continue to play.").

This is a good UX choice for a browser game — it creates tension and
prevents information overload. However, it means a minimum of 4 HTTP
round-trips per auction (3 reveals + 1 settle for a 4-player auction
where human bids first).

### Trick Play Pacing

After each trick completes, the game pauses ("Continue to the next
trick") requiring a `/next` call. This adds 10 extra round-trips per
hand but creates natural pacing for human players.

### Card Legality Display

Legal cards get `card--legal` class; illegal cards get `card--illegal`.
Legal cards also get a `(tap to play)` suffix on their title attribute.
The `data-card-index` attribute on each card provides the index for the
`/play-card` endpoint. This is well-structured for both human interaction
and programmatic access.

### Hand Result Display

The hand result shows:
- Made/Set indicator with CSS class (`result--made`, `result--set`)
- Bidder name, contract, tricks taken
- Team scores for the hand
- Cumulative match score
- Full trick-by-trick table with winner column

This is comprehensive and correct.

## Performance

- Health endpoint latency: ~1.2s (cold start on Render free tier)
- Game action latency: ~0.3-0.5s per POST
- Full 13-hand match: ~2 minutes of wall clock time
- No timeouts or server errors during normal play
- Server uptime at start: 144s (recently restarted, likely cold start)

## Accessibility

- ARIA labels present on all interactive elements
- `role="region"`, `aria-live="polite"/"assertive"` used correctly
- Card labels include suit names ("A of Hearts", not just "A H")
- Score bar has `aria-label="Match score: You -11, AI 32"` (good)

## Recommendations

1. **Add match cleanup job** — timeout abandoned matches after 24h
2. **Consider API mode** — a JSON API alongside the HTMX HTML API would
   enable easier automated testing and potential third-party clients
3. **Standardize score display** — use consistent `score-value` spans
   on all pages (game board, hand result, match result) for accessibility
   and testing parsability

## Outcome

Full match played successfully via HTTP. Scoring verified correct.
No critical bugs found. Three low/medium findings documented above.

---

# Match 2: Edge Case Targeting

**Date:** 2026-04-03
**AI opponent:** Bud Bot (hard)
**Strategy:** Aggressive bidding — attempt moon, loner, LOW, HIGH contracts

## Summary

Played 9 hands (8 from first run, 1 from continuation after fixing bid
retry logic). AI wins 55 to -36. Exercised HIGH no-trump contract
(hand 3 of first run). LOW bid attempts were rejected as illegal when
AI had already bid higher — script lacked overcall awareness.

**Result:** AI wins 55 to -36 after 9 hands.

## Match Scoring Log

| Hand | Bidder | Contract | Tricks | Result | Cumulative (You vs AI) |
|------|--------|----------|--------|--------|----------------------|
| 1 | You | 7 H | 2 | Set | -7 vs 8 |
| 2 | You | 6 H | 4 | Set | -13 vs 14 |
| 3 | You | 6 HIGH | 7 | Made | -6 vs 17 |
| 4 | You | 8 C | 3 | Set | -14 vs 24 |
| 5 | You | 6 S | 4 | Set | -20 vs 30 |
| 6 | You | 7 D | 3 | Set | -27 vs 37 |
| 7 | You | 6 C | 4 | Set | -33 vs 43 |
| 8 | You | 6 H | 5 | Set | -39 vs 48 |
| 9 | (AI) | ? | ? | ? | -36 vs 55 (match end) |

### Edge Cases Observed

1. **HIGH no-trump contract (hand 3):** Successfully bid and made 6 HIGH
   with 4 aces. Took 7 tricks. Scoring correct (+7 for bidder team, +3
   for defenders). No-trump ordering (A high) worked correctly.

2. **Deep negative score:** Human team reached -39 (close to -52 loss
   threshold). AI reached 55 and won. Match termination at >=52 works.

3. **Illegal bid rejection:** Attempting 6 LOW when AI had already bid
   higher returned `{"detail":"Illegal bid"}` (HTTP 400). This is
   correct server behavior — the bid must overcall. However, the error
   response is a raw JSON error, not an HTML game board partial. An
   HTMX client would show this JSON to the user briefly before the
   error handler fires.

4. **Match-complete skips hand-result:** When the final trick of a hand
   causes the match to end (score crosses ±52), the response goes
   directly to the match-result page without showing the hand-result
   interstitial. This means the player never sees the detailed trick
   table for the final hand. This is arguably correct (match is over)
   but differs from the mid-match flow.

### New Bugs Found

#### BUG-4: Illegal bid returns JSON error instead of board re-render

**Severity:** Low
**Details:** When submitting an illegal bid (e.g., 6 LOW when current
high bid is higher), the server returns `{"detail":"Illegal bid"}` as
a JSON 400 response. For HTMX clients, this renders as raw JSON text
in the game board area until the error handler kicks in.

The `/play-card` endpoint already has desync recovery — it returns the
current board HTML for out-of-phase requests. The `/bid` endpoint
should do the same for illegal bids instead of returning HTTP 400.

Looking at routes.py, the `/bid` endpoint does have desync recovery for
phase/seat/awaiting_next checks (returns board HTML). But the final
legality check at line ~1054 raises HTTPException(400, "Illegal bid").
This could be changed to return the current board with an error flash.

#### BUG-5: Match rate limit (429) with no self-cleanup

**Severity:** Medium (confirms #2211)
**Details:** After creating several abandoned matches during testing,
hit 429 rate limit on `/select-ai`. Had to wait for match completion
to free a slot. Confirms need for the abandoned match cleanup proposed
in #2211. The rate limit blocks new match creation but doesn't help
the player recover from abandoned matches.

## Performance Notes

- Match completed in ~3 minutes (9 hands)
- Auction reveal: 3-4 `/next` calls per hand
- Trick play: 10 `/play-card` + 10 `/next` per hand
- Average ~25 HTTP round-trips per hand
