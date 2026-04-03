# Gameplay Intelligence — Bugs

> Bugs observed during Render production proving sessions.
> Date: 2026-04-02

## BUG-001: Card play stuck in "Playing card..." state

- **Severity:** Medium (recoverable via page refresh)
- **Reproduction:** During Game 1, Hand 2, Trick 9 — clicked "Play J of Spades" button. Card was visually selected (active state) and text changed to "Playing card..." but the HTMX play-card request never completed. The "Play selected card" button appeared enabled but clicking it had no effect. Waited 30+ seconds.
- **Recovery:** Page refresh (navigating to the same game URL) restored correct game state. Card play worked normally after refresh.
- **Likely cause:** HTMX request timeout or network glitch on Render free tier. The card selection event fired but the POST to play the card may have failed silently.
- **Game state impact:** None — server-side state was preserved correctly. Only the client-side UI was stuck.
- **Frequency:** 1 occurrence in ~20 card plays across 2 hands.

## BUG-002: Left bower lead shows printed suit instead of trump suit

- **Severity:** Medium (potential card legality impact)
- **Reproduction:** Game 1, Hand 6. Contract 6♣ (clubs trump). Slim led J♠ (left bower — should count as clubs trump). The trick header displayed "Lead suit: Spades" instead of "Lead suit: Clubs". The trick result was "Slim won with ♠J".
- **Expected behavior:** When the left bower is led, the lead suit should be displayed as the trump suit (Clubs), not the printed suit (Spades). Other players must follow trump (clubs), not spades.
- **Actual behavior:** Lead suit shown as "Spades". Card legality enforcement unclear — all my cards were playable (I was void in both spades and clubs), so the legality impact couldn't be verified from my perspective. Ace played T♠ and Deuce played Q♥ — both may have been void in clubs anyway.
- **Likely cause:** The lead suit display logic uses the card's printed suit rather than its effective suit. For the left bower, the effective suit is trump, not the printed suit.
- **Game state impact:** Trick resolution was correct — J♠ as left bower won the trick as trump. The issue is with the lead suit display and potentially the card legality enforcement for other players.
- **Frequency:** 1 occurrence — first time left bower was led in 6 hands.
- **Follow-up needed:** Test with a hand where another player has the printed suit (spades) but not trump (clubs) when left bower is led — would they be forced to play spades or clubs?
- **UPDATE (Hand 7):** CONFIRMED display-only bug. In Hand 7 (7♠ contract), Deuce led J♣ (left bower). Display showed "Lead suit: Clubs" but my K♣ cards were marked "cannot play" — the legality engine correctly treated J♣ as trump (spades) lead. Since I had no spades, all non-club cards were also playable. The card legality enforcement is CORRECT; only the trick header label is wrong. This is a cosmetic bug, not a game logic bug.
- **Occurrences:** 3 total — Hand 6 trick 8 (clubs trump, J♠ led), Hand 7 tricks 2 and 4 (spades trump, J♣ led).
