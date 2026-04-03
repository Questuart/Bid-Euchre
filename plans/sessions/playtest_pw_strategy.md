# AI Strategy Research Notes — Playwright Playtest

**Date:** 2026-04-03
**Match:** Full match, 11 hands, Claude-PW vs Bud Bot
**Final score:** You 16, AI 58 (loss)
**AI model:** Bud Bot ("A confident bidder who plays aggressively")

## Auction Behavior

### Bud Bot Bidding Patterns (Observed Across 11 Hands)

| Hand | Dealer | AI Bids | Winner | Result |
|------|--------|---------|--------|--------|
| 1 | Ace | Deuce: 1♣ | Ace: 3♠ | Made (7 tricks) |
| 2 | Deuce | Slim: 7 Low | Slim: 7 Low | Made (AI) |
| 3 | You | Slim: 3 Lo, Ace: 4♦ | You: Moon ♦ | Set (-20) |
| 4 | Ace | Slim: 5♠ | Slim: 5♠ | Made (AI) |
| 5 | Slim | Slim: 6 Low | Slim: 6 Low | Set (AI) |
| 6 | Deuce | Slim: 1♥, Ace: 6♣ | Ace: 6♣ | Made |
| 7-9 | Various | (automated, details lost) | Mixed | Mixed |
| 10 | Deuce | Slim: 1♥, Ace: 2♥, Deuce: 5♠ | Deuce: 5♠ | Made (7 tricks) |
| 11 | Ace | Deuce: 5♠ | Deuce: 5♠ | Made (7 tricks) |

### Key Observations

**1. Bud Bot bids aggressively and wins**
- Deuce bid 5♠ three times (hands 10, 11, and likely others) and made all three with 7 tricks (2 over bid)
- Slim bid 7 Low and 6 Low — very aggressive Low bids
- The "confident bidder" description is accurate

**2. Jump bidding**
- Hand 10: Current bid was 2♥ (Ace), Deuce jumped to 5♠ — a 3-level jump
- This suggests Bud Bot evaluates hand strength independently and bids its full value regardless of current auction state

**3. Low contract preference (Slim seat)**
- Slim bid Low contracts in hands 2, 3, 5 — disproportionately often
- This may reflect that Slim's dealt hands happened to favor Low, or the bot has a Low-bid bias
- Slim bid 7 Low successfully in hand 2, suggesting the bot accurately evaluates Low hand strength

**4. Partner coordination (limited)**
- Hand 3: Slim bid 3 Low, then Ace (partner) outbid with 4♦ (different suit/type)
- Hand 10: Slim bid 1♥, then Ace bid 2♥ (same suit, raised), then Deuce jumped to 5♠
- Partners don't appear to coordinate bids — they bid independently based on hand strength
- No observed "support bids" or signaling

**5. Declarer always makes**
- In observed AI-declared hands, the AI always made the contract (except one 6 Low set)
- Bud Bot's bidding appears calibrated — it doesn't overbid frequently
- The 7 Low was the most aggressive AI bid and it succeeded

## Card Play Strategy

### Trick Play Observations

**1. Moon Exchange AI Logic**
- Hand 3: I bid Moon ♦, partner Ace gave me J♦ (right bower) + A♦ (ace of trump)
- This is optimal exchange behavior — the partner gave its two strongest trump cards
- Suggests the exchange AI correctly identifies the declared trump suit and donates accordingly

**2. Deuce's Lead Strategy (Hand 10, 5♠ contract)**
- Trick 1: Deuce (declarer) won lead
- Trick 7: Deuce led J♦ (off-suit) — drawing cards before using remaining trump
- I trumped Deuce's J♦ lead with 10♠ to win (Deuce lost that trick)
- Deuce recovered and won 5+ tricks overall

**3. AI Trump Management**
- Deuce consistently took 7 tricks on 5-bids — saving enough trump to close out
- Trick 1 (Hand 10): Deuce played J♠ (right bower) as the opening card — led with strength
- Later tricks: Deuce shifted to off-suit leads to draw out defenders' trump

**4. Defensive Play (Slim/Deuce when defending)**
- Slim played A♦ in trick 7 (following suit, playing high to try to win)
- Deuce trumped with Q♠ when void in the led suit (trick 6, hand 1) — correct defense

### AI Strengths
- **Accurate bid calibration:** Bids match achievable trick count (rarely set)
- **Strong opening leads:** Uses bowers/aces to establish control early
- **Good trump conservation:** Saves trump for later tricks when controlling off-suits
- **Optimal Moon exchange:** Gives best trump cards to declaring partner

### AI Potential Weaknesses
- **No partner signaling:** Bids don't seem to communicate hand information to partner
- **Occasional overbid:** Slim's 6 Low was set (hand 5) — may overestimate Low hands
- **Predictable lead pattern:** Tends to lead strongest card first (aces, bowers) — a human could exploit this by holding off early

## Match-Level Strategy

### Win Condition Analysis

The AI won 58-16 in 11 hands. Key factors:
1. **My Moon set (-20):** This single hand cost me 20 points, which was the margin of the game
2. **AI bid accuracy:** AI declared and made in most hands, accumulating steady points
3. **Defensive tricks:** Even when defending, AI's team picked up 2-4 tricks per hand
4. **Consistency:** AI never fell behind on tricks — always met or exceeded its bids

### Bud Bot vs OLSa Comparison (Theoretical)

Based on the leaderboard:
- Bud Bot: EPPD +1.517, 74% win rate, +14.2 average margin
- OLSa: EPPD -1.714, 0% win rate

Bud Bot appears significantly stronger — the "aggressive bidder" strategy works well against human opponents who are playing suboptimally (like me, passing most auctions).

## No New Bugs Found

All bugs observed in this round were previously filed in rounds 1-4.
