# UI Cleanup Mockups — Issue #2200

> **Task:** Design 3 UI cleanup options for the gameplay screen
> **Date:** 2026-04-03
> **Analyst:** analyst-d

---

## Part 1: Current State Audit

### UI Element Inventory (Trick Play Phase)

| # | Element | Template | Always Visible? | Information Conveyed |
|---|---------|----------|-----------------|---------------------|
| 1 | Help drawer | `game_controls.html` | Collapsed by default | Rules, icon legend |
| 2 | Contract bar (sticky) | `contract_bar.html` | During trick play | Contract level, trump, declarer, team color |
| 3 | AI seat labels + markers | `game_board.html` | Yes (3 locations) | Name, D/★/▶/SO badges, bid tag, card count |
| 4 | AI card backs | `game_board.html` | Yes (3 locations) | Visual hand size per AI |
| 5 | Trick area heading | `trick.html` | Yes | "Trick N of 10", lead suit icon |
| 6 | Trick table (compass) | `trick.html` | Yes | Played cards, seat markers (D/★/L/▶/SO), empty slots |
| 7 | Trick center count | `trick.html` | Yes | Tricks won "4–3" |
| 8 | "X is winning" text | `trick.html` | During active trick | Who's currently ahead |
| 9 | Trick winner text | `trick.html` | After trick complete | Who won, with what card |
| 10 | Trick history | `trick_history.html` | Collapsed `<details>` | Table of all completed tricks by seat |
| 11 | Human seat label | `game_board.html` | When bid exists | "You" + D/▶ badges + bid tag |
| 12 | Human hand (card fan) | `hand.html` | Yes | Cards, legal glow, bower badge |
| 13 | Play card form | `hand.html` | During trick play | Submit button + help text |
| 14 | Score bar | `score.html` | Yes | Score, hand #, dealer, contract, declarer, tricks, target |
| 15 | Icon legend | `game_board.html` | Yes | Badge reference: D, ★, L, ▶, Bid |
| 16 | Action rail | `action_rail.html` | Desktop only | Auction/trick event log |
| 17 | Bid panel | `bid_panel.html` | Auction only | Bid transcript + bid form |

### Duplication Map

| Information | Where it appears | Redundancy |
|-------------|-----------------|------------|
| **Contract/trump** | Contract bar + Score bar `contract-info` | **2x** — same info in two places |
| **Declarer** | Contract bar + Score bar + ★ marker on 3 AI seats + trick area seat markers | **5x** — severely redundant |
| **Dealer** | D badge on all 4 seats + Score bar "Dealer: X" | **5x** |
| **Current turn** | ▶ badge on seat labels + (implicitly) whose trick slot is empty | **2x** |
| **Tricks won** | Trick center "4–3" + Score bar "Tricks: 4–3" | **2x** |
| **Bid amount** | bid-tag on all 4 seat labels + Score bar contract info | **5x** |
| **Seat badges** | AI seat labels (3) + human seat label + trick area seat markers (4) | **Up to 8 badge locations per role** |

### Visibility Analysis (When is it needed?)

| Element | Auction | Trick Play | Between Tricks | Hand Result |
|---------|---------|------------|----------------|-------------|
| Contract bar | -- | **Essential** | Useful | -- |
| Seat markers (D) | Nice-to-have | Low | Low | -- |
| Seat markers (★) | -- | Useful | Useful | -- |
| Seat markers (▶) | Essential | Essential | Low | -- |
| Seat markers (L) | -- | Essential | Low | -- |
| Score bar (score) | Essential | Essential | Essential | Shown in result |
| Score bar (contract) | -- | Redundant w/ bar | Redundant | -- |
| Score bar (tricks) | -- | Redundant w/ center | Redundant | -- |
| Trick history | -- | On-demand | On-demand | -- |
| Icon legend | First game only | -- | -- | -- |
| Action rail | Essential (bids) | Low | Low | -- |

---

## Part 2: Current Layout (ASCII Reference)

```
┌─────────────────────────────────────────────────────┐
│ ▸ Help: Bid Euchre Rules                            │  ← game_controls (collapsed)
├─────────────────────────────────────────────────────┤
│                                                     │
│              Ace D ★  [bid: 6♠]                     │  ← partner seat label
│             ▓▓ ▓▓ ▓▓ ▓▓ ▓▓ ▓▓ ▓▓                   │  ← partner card backs (7)
│             Ace (7)                                  │
│                                                     │
│  Slim ▶      ┌─────────────────────┐    Deuce       │
│  [bid: P]    │ Contract: 6♠ — You  │    [bid: 4♠]   │
│  ▓           │                     │         ▓      │
│  ▓           │     ┌────┐          │         ▓      │
│  ▓           │  ┌──┤ A♠ ├──┐       │         ▓      │
│  ▓           │  │  └────┘  │       │         ▓      │
│  ▓           │┌─┴─┐  4-3  ┌┴──┐   │         ▓      │
│  Slim(5)     ││Q♥ │       │---│   │    Deuce(5)    │
│              │└───┘       └───┘   │                 │
│              │   ┌────┐           │                 │
│              │   │10♠ │           │                 │
│              │   └────┘           │                 │
│              │ Trick 4 of 10  ♠   │                 │
│              │ You are winning    │                 │
│              │                    │                 │
│              │ ▸ Cards Played(3/10)│                 │
│              └────────────────────┘                 │
│                                                     │
│  You D [bid: 6♠]                                    │
│  ┌────┬────┬────┬────┬────┬────┬────┐               │
│  │10♠ │ J♠ │ Q♠ │ A♠ │ K♥ │10♦ │ Q♣ │              │
│  │ ♠  │ ♠B │ ♠  │ ♠  │ ♥  │ ♦  │ ♣  │              │
│  └────┴────┴────┴────┴────┴────┴────┘               │
│  [Play card]   Tap a card to play it.               │
│                                                     │
├─────────────────────────────────────────────────────┤
│ You: 12 | AI: 8 · Hand 3 · Dealer: You             │  ← score bar
│ Contract: 6♠ · Declarer: You · Tricks: 4–3          │  ← REDUNDANT w/ contract bar + trick center
│ First to 52 wins · -52 = loss                       │
├─────────────────────────────────────────────────────┤
│ D Dealer · ★ Declarer · L Lead · ▶ Turn · 5♠ Bid   │  ← icon legend
├─────────────────────────────────────────────────────┤
│ Auction Log                                         │  ← action rail (hidden on mobile)
│ Slim passed · You bid 6♠ · Ace bid 4♠ · Deuce bid 4♠│
└─────────────────────────────────────────────────────┘
```

**Current element count during trick play:** 12+ distinct visual regions competing for attention.

---

## Part 3: Three Design Options

---

### Option A: Progressive Disclosure

**Philosophy:** Show only what matters for the current decision. Everything else is one tap away.

**Always visible (Primary):**
- Human hand (cards with legal glow)
- Trick table (played cards only, no seat markers)
- Trick score counter ("4–3") in trick center
- Compact status line: score + contract + trick number

**Collapsed / on-demand (Secondary):**
- Trick history (already collapsed — keep as-is)
- AI card counts (collapse into compact badges, expand to full card backs on tap)
- Seat role details (tap a seat label to see D/★/L badges)
- Help drawer (already collapsed — keep as-is)

**Removed entirely:**
- Icon legend (move into Help drawer permanently)
- Action rail (already hidden on mobile; remove on desktop too — info in trick history)
- Contract bar as separate element (merge into unified status line)
- Score bar "contract" and "tricks" sub-sections (canonical location is status line + trick center)
- "X is winning" text (the gold glow on the winning card is sufficient)
- Bid tags on seat labels (visible in trick history on demand)

```
┌─────────────────────────────────────────────────────┐
│ You: 12 | AI: 8    6♠ by You    Trick 4/10    [?]  │  ← unified status line
├─────────────────────────────────────────────────────┤
│                                                     │
│             [A]:7  [tap to expand]                   │  ← collapsed partner
│                                                     │
│  [S]:5       ┌────────────────────┐       [D]:5     │  ← collapsed side hands
│              │                    │                 │
│              │     ┌────┐         │                 │
│              │  ┌──┤ A♠ ├──┐      │                 │
│              │  │  └────┘  │      │                 │
│              │┌─┴─┐  4-3  ┌┴──┐  │                 │
│              ││Q♥ │       │---│  │                 │
│              │└───┘       └───┘  │                 │
│              │   ┌────┐          │                 │
│              │   │10♠ │          │                 │
│              │   └────┘          │                 │
│              │                   │                 │
│              │ ▸ Cards Played    │                 │
│              └───────────────────┘                 │
│                                                     │
│  ┌────┬────┬────┬────┬────┬────┬────┐               │
│  │10♠ │ J♠ │ Q♠ │ A♠ │ K♥ │10♦ │ Q♣ │              │
│  │ ♠  │ ♠B │ ♠  │ ♠  │ ♥  │ ♦  │ ♣  │              │
│  └────┴────┴────┴────┴────┴────┴────┘               │
│              Tap a card to play.                     │
└─────────────────────────────────────────────────────┘
```

**Key changes:**
1. **Unified status line** replaces contract bar + score bar + trick heading. One horizontal bar: `Score | Contract | Trick N/10 | [?] help`
2. **AI hands collapsed** to single-letter badges with count (`[A]:7`). Tap to expand to full card backs.
3. **Seat markers removed** from default view. Tap a player name to see their role (dealer, declarer, etc.)
4. **Icon legend deleted** from game board; content lives in Help drawer only.
5. **Action rail removed** from desktop too (was already hidden on mobile).
6. **"X is winning" text removed** — the gold card glow communicates this visually.

**Pros:**
- Maximum card/trick visibility
- Clean first impression for new players
- Information accessible but not competing for attention
- Fewest changes to template structure (mostly hiding + merging)

**Cons:**
- Players must tap to see details they might want at a glance
- Learning curve for finding collapsed info
- "Where did the dealer indicator go?" initial confusion

---

### Option B: Minimal

**Philosophy:** Cut everything that isn't needed for the current decision. If you can't justify it for every trick, it goes.

**Keep:**
- Human hand (cards with legal glow)
- Trick table (played cards, empty slots with seat names)
- Trick center score ("4–3")
- Score bar — **simplified**: just `You: 12 | AI: 8`
- Contract bar — **simplified**: just `6♠ — You` (no "Contract:" label, no team color border, no relationship text)
- Turn indicator: ▶ on the ONE seat whose turn it is (not on all seats)
- Bid panel (auction only)

**Remove:**
- AI card back visuals (replace with text count in seat label: "Ace (7)")
- All seat markers EXCEPT ▶ (turn) — dealer/declarer/lead information is in the contract bar or trick history
- Icon legend (entirely — it's explaining badges we're removing)
- Action rail (entirely)
- "X is winning" text
- Trick winner text (the card glow on the winning card + trick history serves this)
- Score bar contract/declarer/tricks/dealer/target sub-sections (all redundant)
- Bid tags on seat labels
- Human seat label (your hand is obviously yours)

```
┌─────────────────────────────────────────────────────┐
│ ▸ Help                                              │
├─────────────────────────────────────────────────────┤
│ 6♠ — You                    You: 12 | AI: 8        │  ← contract + score (one line)
├─────────────────────────────────────────────────────┤
│                                                     │
│              Ace (7)                                 │  ← text-only partner count
│                                                     │
│  Slim (5)    ┌────────────────────┐    Deuce (5)    │
│  ▶           │                    │                 │  ← ▶ only on whose turn
│              │     ┌────┐         │                 │
│              │  ┌──┤ A♠ ├──┐      │                 │
│              │  │  └────┘  │      │                 │
│              │┌─┴─┐  4-3  ┌┴──┐  │                 │
│              ││Q♥ │       │---│  │                 │
│              │└───┘       └───┘  │                 │
│              │   ┌────┐          │                 │
│              │   │10♠ │          │                 │
│              │   └────┘          │                 │
│              │ Trick 4/10    ♠   │                 │
│              │                   │                 │
│              │ ▸ Cards Played    │                 │
│              └───────────────────┘                 │
│                                                     │
│  ┌────┬────┬────┬────┬────┬────┬────┐               │
│  │10♠ │ J♠ │ Q♠ │ A♠ │ K♥ │10♦ │ Q♣ │              │
│  │ ♠  │ ♠B │ ♠  │ ♠  │ ♥  │ ♦  │ ♣  │              │
│  └────┴────┴────┴────┴────┴────┴────┘               │
│              Tap a card to play.                     │
└─────────────────────────────────────────────────────┘
```

**Key changes:**
1. **AI card backs removed** — just show "Name (N)" text. Saves significant vertical and horizontal space.
2. **Contract + score merged into one top line.** No separate contract bar or score bar.
3. **Single turn indicator** — ▶ only appears next to the ONE player whose turn it is. No other seat markers.
4. **Everything below the hand is gone** — no score bar, no icon legend, no action rail.
5. **Trick heading simplified** to "Trick 4/10" (no "of").

**Pros:**
- Dramatically less visual noise
- Focus is entirely on cards and the trick
- Works beautifully on mobile (less scrolling)
- Easiest to implement — mostly deletion

**Cons:**
- Lose at-a-glance dealer/declarer info (must check contract bar or help)
- No visual representation of AI hand sizes (numbers less intuitive)
- Experienced players may miss the auction log on desktop
- Can feel "too sparse" for users who like information density

---

### Option C: Visual Hierarchy (Recommended)

**Philosophy:** Keep everything, but create clear visual tiers so the eye naturally finds what matters. The problem isn't too much information — it's that everything is at the same visual weight.

**Tier 1 — Primary (bold, full-size):**
- Human hand (cards, legal glow) — largest element on screen
- Trick table (played cards) — second largest
- Turn indicator — bright, animated pulse on the active seat

**Tier 2 — Secondary (medium, clearly present):**
- Score: `You: 12 | AI: 8` — kept prominent in score bar
- Contract bar — kept but made more compact (no "Contract:" header, just `6♠ You`)
- Trick count — in trick center alongside tricks-won counter
- AI card backs — kept but smaller, with reduced opacity when not that player's turn

**Tier 3 — Tertiary (subtle, small, reduced opacity):**
- Seat markers — shrunk, dimmed to ~60% opacity, only dealer and declarer shown (remove L/▶ markers — turn is shown by trick slot + card glow)
- Trick history — kept collapsed (no change)
- Help drawer — kept collapsed (no change)

**Removed (redundant):**
- Icon legend (info lives in Help drawer)
- Score bar contract/tricks/declarer duplicates (canonical in contract bar + trick center)
- Score bar "First to 52 wins" text (move to Help drawer)
- Action rail on desktop (already hidden on mobile; keep only during auction as "Bid Log")
- Bid tags on seat labels (redundant with auction transcript)
- "X is winning" text (gold card glow is sufficient)

```
┌─────────────────────────────────────────────────────┐
│ ▸ Help                                              │
├─────────────────────────────────────────────────────┤
│ 6♠ You (Partner)              You: 12 │ AI: 8      │  ← compact contract + score
├─────────────────────────────────────────────────────┤
│                                                     │
│              Ace  D★                                │  ← seat label with SUBTLE markers
│             ▓▓ ▓▓ ▓▓ ▓▓ ▓▓ ▓▓ ▓▓                   │  ← card backs (dimmed ~60% when
│             (7 cards)                                │     not their turn)
│                                                     │
│  Slim        ┌────────────────────┐       Deuce     │
│  ▓           │                    │            ▓    │
│  ▓           │     ┌────┐         │            ▓    │
│  ▓ ●         │  ┌──┤ A♠ ├──┐      │            ▓    │  ← ● pulse dot = turn
│  ▓           │  │  └────┘  │      │            ▓    │
│  ▓           │┌─┴─┐ 4-3   ┌┴──┐  │            ▓    │
│              ││Q♥ │ T4/10 │---│  │                 │
│              │└───┘       └───┘  │                 │
│              │   ┌────┐          │                 │
│              │   │10♠ │          │                 │
│              │   └────┘          │                 │
│              │                   │                 │
│              │ ▸ Cards Played    │                 │
│              └───────────────────┘                 │
│                                                     │
│  ┌────┬────┬────┬────┬────┬────┬────┐               │
│  │10♠ │ J♠ │ Q♠ │ A♠ │ K♥ │10♦ │ Q♣ │   ← TIER 1  │
│  │ ♠  │ ♠B │ ♠  │ ♠  │ ♥  │ ♦  │ ♣  │   (largest)  │
│  └────┴────┴────┴────┴────┴────┴────┘               │
│              Tap a card to play.                     │
├─────────────────────────────────────────────────────┤
│ Hand 3 · Dealer: You             First to 52   [?]  │  ← slim info bar (tertiary)
└─────────────────────────────────────────────────────┘
```

**Key changes:**
1. **Contract bar compacted:** Remove "Contract:" header text, remove team-color bottom border (rely on text alone), keep declarer + relationship. One line.
2. **Score bar split into two tiers:**
   - Tier 2 (top line, next to contract): `You: 12 | AI: 8` only
   - Tier 3 (bottom slim bar): `Hand 3 · Dealer: You · First to 52 · [?]`
3. **Seat markers reduced to D and ★ only**, rendered at 60% opacity, smaller font. Remove L (leader shown by trick area positioning), remove ▶ (turn shown by pulse dot + card glow).
4. **Turn indicator replaced** with a subtle animated pulse dot (●) next to the active player's name, instead of ▶ badge on every seat label.
5. **AI card backs dimmed** when it's not that player's turn — makes the active player pop visually.
6. **Icon legend removed** from game board; consolidated into Help drawer.
7. **Redundant score bar sections removed** — no more duplicate contract/tricks/declarer text.
8. **Action rail hidden** except during auction phase (where it serves as "Bid History").

**Pros:**
- No information loss — everything is still accessible
- Natural eye flow: hand → trick → score → details
- Dimming/sizing creates layers without hiding
- Lowest user confusion ("where did X go?") because nothing disappears
- Mobile-friendly: smaller markers + slimmer bars save space naturally

**Cons:**
- More CSS work than Option B (opacity states, animations, responsive tiers)
- Still has more visual elements than Option B
- Opacity-based hierarchy can be subtle on low-contrast displays

---

## Part 4: Recommendation

### **Option C (Visual Hierarchy) is the recommended "user version"**

Rationale:

1. **Lowest risk of "where did it go?"** — New players won't hunt for removed features. Everything is present but visually layered.

2. **Best balance of information density and clarity** — Experienced card players want to see the contract, dealer, and hand count at a glance. Removing them (Option B) optimizes for simplicity at the cost of expert playability.

3. **Progressive disclosure is still used where it already exists** — Trick history and Help drawer remain collapsed. We just stop duplicating their content everywhere else.

4. **Implementation can be incremental** — Each change in Option C is independent:
   - PR 1: Remove redundant score bar sections + merge contract bar compact
   - PR 2: Replace ▶ badges with pulse-dot turn indicator
   - PR 3: Add opacity dimming for non-active AI hands
   - PR 4: Move icon legend into Help drawer, remove from board
   - PR 5: Remove bid tags from seat labels

5. **The core deletion from all options overlaps** — Regardless of which option is chosen, these changes are common:
   - Remove icon legend from game board
   - Remove duplicate contract/tricks/declarer from score bar
   - Remove "X is winning" text
   - Remove bid tags from seat labels

### Comparison Matrix

| Criterion | A: Progressive | B: Minimal | **C: Hierarchy** |
|-----------|---------------|-----------|-----------------|
| Visual noise reduction | High | Very High | High |
| Information loss | Medium (hidden) | High (removed) | **None** |
| New player friendliness | Medium | High | **High** |
| Expert player friendliness | Low | Medium | **High** |
| Mobile improvement | High | Very High | High |
| Implementation effort | Medium | Low | Medium |
| Risk of "where did it go?" | High | Medium | **Low** |
| Incremental shippability | Medium | High | **High** |

---

## Part 5: Common Deletions (All Options)

These changes should happen regardless of which option is chosen:

1. **Move icon legend into Help drawer** — it's a reference, not an active-play element
2. **Remove score bar duplicate sections** — contract, declarer, and tricks info already in contract bar and trick center
3. **Remove "X is winning" text** — gold card glow conveys this
4. **Remove bid tags from seat labels** — visible in auction transcript / trick history
5. **Remove score bar "First to 52 wins" text** — move to Help drawer
6. **Remove action rail during trick play** — keep only during auction as "Bid History"

These alone would significantly reduce clutter with zero information loss.

---

## Outcome

- **Original mockups** posted as comment on issue #2200: https://github.com/Questuart/Bid-Euchre/issues/2200#issuecomment-4184921169
- **User design direction** received: baseline Progressive Disclosure, words not icons, 5 mission-critical items, remove help bar/legend/turn indicator
- **Refined proposal** posted as comment: https://github.com/Questuart/Bid-Euchre/issues/2200#issuecomment-4185006826
  - Key changes from original: keep "best card" text (was proposed for removal), replace all badges with word labels, remove help drawer entirely (use Guide tab), remove turn indicator, spell out contract in words, contextual trick progress vs contract
