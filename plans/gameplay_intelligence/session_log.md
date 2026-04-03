# Gameplay Intelligence — Session Log

> Render production proving: bideuchre-web.onrender.com
> Invite code: PD9B4LL9
> Date: 2026-04-02
> Player name: CLAUDE
> AI opponent: Bud Bot

## Game 1 (Match ID: 7354c408)

**Status:** In progress (Hand 3 of N, first to ±52)
**Current match score after Hand 3: You 7, AI 14**

### Hand 1 — Dealer: Slim
- **Auction:** Ace passed, Deuce bid 1♦, You bid 4♠, Slim bid 5 High (won)
- **Contract:** 5 High (Slim, declarer)
- **Result:** Slim made it — took 8 tricks. Your team: +2, AI team: +8
- **Match score after hand:** You 2, AI 8
- **Notes:** Slim (Bud Bot) aggressively outbid with 5 High. Had a strong hearts-heavy hand with multiple aces. AI played very efficiently in no-trump.

### Hand 2 — Dealer: Ace
- **Auction:** Deuce bid 3♠, You bid 6 High, Slim passed, Ace passed
- **Contract:** 6 High (You, declarer)
- **Result:** Made it — took ALL 10 tricks! Your team: +10, AI team: 0
- **Match score after hand:** You 12, AI 8
- **Notes:** Monster hand — 4 aces (A♠, A♥×2, A♣) + 3 kings + Q♥. Led aces first 4 tricks, then kings. Opponents couldn't win a single trick. Perfect 10-0 sweep.
- **Bug:** Card play got stuck in "Playing card..." state during trick 9. HTMX request appeared to stall — card was selected (highlighted) but not played. Required page refresh. Game state preserved correctly across refresh.

### Hand 3 — Dealer: Deuce
- **Auction:** You bid 3♠, Slim bid 4♥, Ace bid 5♥ (won), Deuce passed
- **Contract:** 5♥ (Ace, declarer — my partner)
- **Result:** SET! Ace bid 5♥ but took only 4 tricks. Your team: -5, AI team: +6
- **Match score after hand:** You 7, AI 14
- **Notes:** Slim had deep hearts (trump) and repeatedly trumped our off-suit aces. Bower hierarchy verified: J♥ (right bower) > J♦ (left bower) > A♥. Left bower (J♦) correctly treated as hearts trump, not diamonds — card legality enforcement was correct. Partner Ace overbid.

### Key Proving Observations

**Contract types tested:**
- High (no-trump): Hands 1 & 2 — aces are highest, no bowers
- Suit (hearts trump): Hand 3 — bower hierarchy, trump cutting, suit legality

**Features verified working:**
1. Invite code entry and game creation
2. AI opponent selection (Bud Bot vs OLSa)
3. Bidding UI: type/level/suit dropdowns, submit, pass
4. Card legality enforcement (correct suit following, bower as trump)
5. Trick resolution with correct winner determination
6. Trump cutting off-suit leads
7. Bower hierarchy (right > left > ace of trump)
8. Hand result scoring (made vs set)
9. Match score accumulation across hands
10. "Next" button pacing for AI action reveals
11. Cards Played history expandable section
12. Auction log
13. Game state preservation across page refresh

### Hand 4 — Dealer: You
- **Auction:** Slim 3 Lo, Ace 6♦ (won), Deuce passed, You passed
- **Contract:** 6♦ (Ace, declarer — my partner)
- **Result:** Made it — took 8 tricks. Your team: +8, AI team: +2
- **Match score after hand:** You 15, AI 16
- **Notes:** Ace had monster diamond hand with both J♦ (right bowers), left bower J♥, K♦, A♣, A♠, A♥, K♥. Led with aces first 3 tricks, then used bowers to close out. I contributed A♦ (trump ace) to win trick 6 over-trumping Deuce's K♦, and led A♣ for trick 7. Ace won tricks 8-10 with J♦, J♦, K♦.

### Hand 5 — Dealer: Slim
- **Auction:** Ace 6♦ (won), Deuce passed, You passed, Slim passed
- **Contract:** 6♦ (Ace, declarer — my partner)
- **Result:** Made it — took 7 tricks. Your team: +7, AI team: +3
- **Match score after hand:** You 22, AI 19
- **Notes:** Hard-fought hand. Slim trumped my A♥ with T♦ (trick 4) and won trick 5 with K♣. Score was 2-3 against us at one point. I played J♦ (right bower) to win trick 6 over Deuce's A♦, then led Q♦ (trump) trick 7. Ace's J♥ (left bower) won it. Ace closed out with J♦ and K♦.

### Hand 6 — Dealer: Ace
- **Auction:** Deuce 1♥, You 6♣ (won!), Slim passed, Ace passed
- **Contract:** 6♣ (You, declarer — first time as declarer!)
- **Result:** SET! Bid 6♣ but only took 5 tricks. Your team: -6, AI team: +5
- **Match score after hand:** You 16, AI 24
- **Notes:** Had 2×J♣ (both right bowers!) + A♣ = 3 guaranteed trump tricks. Led J♣ tricks 1-2 pulling all opponent trump. Led K♥ trick 3 but Slim had A♥. Won tricks 4-6 (Ace A♠, Ace A♦, me A♣ trumping). Slim trumped K♦ with K♣ trick 7. Then Slim played J♠ (left bower) trick 8 — **BUG-002: lead suit displayed as "Spades" but J♠ as left bower should be "Clubs" (trump)**. Lost tricks 9-10 to opponent aces.
- **Strategy lesson:** 2× right bower + A♣ was only 3 guaranteed tricks. Kings in off-suits are unreliable — opponents can trump or out-ace them. Should have bid 5♣ not 6♣.

### Key Proving Observations (Continued)

**Contract types tested (Hands 4-6):**
- Suit (diamonds trump): Hands 4 & 5 — bower hierarchy, cross-trumping
- Suit (clubs trump): Hand 6 — declarer experience, bower leads

**Features verified working (additional):**
14. Human as declarer (Hand 6 — first time bidding and winning auction)
15. Bid form with type/level/suit dropdowns — worked correctly
16. Trump sorting in hand display — cards re-sort with trump first after auction
17. Set scoring for human declarer — correctly applied -6 penalty
18. Contract status display in header bar ("Contract: 6♣ · Declarer: You")
19. Double right bower handling — both J♣ copies won as highest trump

**New bug found:**
- BUG-002: Left bower lead suit display — see bugs.md

### Hand 7 — Dealer: Deuce
- **Auction:** You 5♦, Slim passed, Ace 6 High, Deuce 7♠ (won!)
- **Contract:** 7♠ (Deuce, declarer — opponent)
- **Result:** Made it — took 7 tricks. Your team: +3, AI team: +7
- **Match score after hand:** You 19, AI 31
- **Notes:** Deuce had massive spade hand with J♠ (right bower), J♣ (left bower), K♠×2, A♠, A♦ + deep off-suit. Ace counter-played J♠ (right bower) in trick 2 to win 1 trick. But Deuce dominated with trump leads (J♣ left bower tricks 2,4, K♠ trick 5, J♠ right bower trick 8).
- **BUG-002 confirmed display-only:** In trick 2, Deuce led J♣ (left bower). Display showed "Lead suit: Clubs" BUT my K♣ cards were correctly marked "cannot play" — legality engine treats left bower as trump (spades), not clubs. In trick 4, same pattern: J♣ led, all my cards playable (void in trump). Legality is correct, only the display label is wrong.

## Game 1 Status

**In progress** — Match score: You 19, AI 31 (first to ±52)
Hands played: 7

## Game 2

_Not started._

## Game 3

_Not started._

## Session Summary

**Session 2** (continuing Game 1): Played hands 4-7 (4 complete hands this session,
7 total in match). Match score: You 19, AI 31. Game still in progress.

**Results:** Won hands 4 & 5 (Ace as declarer, 6♦ both times), was set on hand 6
(first time as human declarer, bid 6♣ with double right bowers but only took 5),
lost hand 7 (Deuce made 7♠ with dominant spade hand).

**Bugs found:** 2 total
- BUG-001: "Playing card..." stuck state (Medium, recoverable)
- BUG-002: Left bower lead suit display (Medium, display-only — CONFIRMED legality is correct)

**Contract types tested across 7 hands:**
- Suit (♦ trump): Hands 3, 4, 5, 7 (as declarer partner)
- Suit (♥ trump): Hand 3
- Suit (♣ trump): Hand 6 (as declarer)
- Suit (♠ trump): Hand 7 (as defender)
- High (no-trump): Hands 1, 2

**Features verified:** 19 distinct features across bidding, card play, scoring,
UI, and game state management. See "Key Proving Observations" above.

**Remaining:** Game 1 needs ~3-5 more hands to reach ±52. Games 2 and 3 not started.
Match can be resumed via invite code PD9B4LL9 — game state persists across sessions.
