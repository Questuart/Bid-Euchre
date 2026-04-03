# Gameplay Intelligence — Play Techniques

> Strategies and techniques learned during Render production proving.
> Date: 2026-04-02

## Effective Techniques

1. **Lead aces first in no-trump (High):** With 4 aces in a High contract, leading them sequentially guaranteed 4 tricks immediately. Since there's no trump to cut in, aces are near-guaranteed winners when you lead them.

2. **Follow up aces with kings in the same suit:** After pulling both copies of an ace from a suit (double deck), the king becomes the highest remaining card. K♥ won immediately after both A♥ copies were played.

3. **Void discarding strategy:** When void in the lead suit and can't win (no trump in High contract), discard your weakest card. Save kings and queens that might win later tricks.

4. **Bid aggressively with 4+ aces in High:** A hand with 4 aces in a High contract is extremely strong — bid 6+ confidently. The 10-0 sweep in Hand 2 confirms this.

5. **Trump ace timing matters:** In Hand 3, I played A♥ (trump ace) to win a diamond trick, but Ace (partner) played J♥ (right bower, higher rank) on the same trick. Coordinate with partner — don't both waste high trump on the same trick.

6. **Left bower is trump, not its printed suit:** J♦ was correctly treated as hearts (trump) in Hand 3. You can't follow a diamond lead with J♦ when hearts are trump — it counts as a heart. This affects both when you must play it and when you can play it.

## Game Flow Observations

1. **"Next" button pacing:** The step-by-step reveal of AI actions via the "Next" button creates good pacing. Each AI action is revealed one at a time.

2. **Auction visibility:** The auction panel clearly shows bidding history and current high bid. The bid form with type/level/suit dropdowns is intuitive.

3. **Card legality enforcement:** Cards that cannot be played (wrong suit when you have the lead suit) are clearly marked "(cannot play)" and are not clickable. Good UX — prevents illegal plays.

4. **Hand result screen:** Clear display of "Made it!" vs "Set!" with trick counts, scoring summary, and match totals. "Next Hand" button transitions smoothly.

5. **Match continuity:** Score carries over correctly between hands. Match score bar at bottom always visible. Hands numbered correctly (Hand 1, 2, 3...).

## Bugs Encountered

1. **BUG-001:** "Playing card..." stuck state during Hand 2 Trick 9. See bugs.md for details. Recovered via page refresh — game state preserved.

## Effective Techniques (Hands 4-6)

7. **Over-trump opponents with bowers:** In Hand 4 trick 6, Deuce played A♦ (trump ace) to win. I over-trumped with J♦ (right bower) — the only card that beats the trump ace. Always save your right bower for critical over-trump moments.

8. **Lead right bowers first as declarer:** In Hand 6, I led both J♣ (right bowers) tricks 1-2 to pull out all opponent trump. This guaranteed trump dominance early but left me vulnerable to opponent aces in off-suits later.

9. **Don't overbid kings:** In Hand 6, I had 2×K♥ + 2×K♦ but counted them as likely winners. Only 1 of 4 kings actually won a trick. With 2 copies per card in double deck, kings face tough odds against aces. Count at most 1 trick per 2 kings, not 1 per king.

10. **Trump to steal opponent-led tricks:** In Hand 6 trick 6, I trumped with A♣ when void in the led suit to steal the trick. As declarer, trumping wisely is essential when you lose the lead.

11. **Watch for trump-saving opponents:** Slim held K♣ (low trump) until trick 7, then used it to trump my off-suit K♦ lead. Opponents save trump specifically to steal your off-suit winners.

## Bidding Lessons

1. **Double right bowers = 2 guaranteed tricks, not 3+:** Both J♣ copies won, but opponents also hold 2 copies of every other club. After pulling trump, opponents still have off-suit aces.

2. **Count guaranteed tricks conservatively:** My Hand 6 bid of 6♣ with 2×J♣ + A♣ + 4 kings = overestimated. Realistic: 3 trump + 1-2 off-suit = bid 4-5, not 6.

3. **Passing as partner is often correct:** In Hands 4-5, passing let Ace play 6♦ with great diamond hands. Don't outbid your partner unless you have a clearly stronger hand.

## Bugs Encountered (Continued)

2. **BUG-002:** Left bower lead suit display shows printed suit instead of trump. See bugs.md for details.
