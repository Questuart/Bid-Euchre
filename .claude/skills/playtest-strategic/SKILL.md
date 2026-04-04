---
name: playtest-strategic
description: Play the browser game via HTTP with intelligent bidding and card play to find bugs that emerge during competitive gameplay.
---

# /playtest-strategic -- Strategic Browser Game Playtesting

Play complete matches of the Bid Euchre browser game via HTTP endpoints with
intelligent bidding and card selection. Unlike `/playtest` (always pass, first
legal card), this mode plays to WIN -- finding bugs that only emerge during
competitive, non-trivial gameplay.

## When to Use

- You want to find bugs triggered by non-trivial game states (actual bids,
  trump contracts, contested tricks)
- You want to test code paths that require a human player to bid and win
- You want to generate match data with realistic gameplay patterns
- You need to stress-test scoring, bower resolution, and contract fulfillment

## Arguments

| Argument | Description |
|----------|-------------|
| `--url <render_url>` | Base URL of the hosted game (e.g., `https://bid-euchre.onrender.com`) |
| `--code <invite_code>` | Invite code for game access |
| `--nickname <name>` | Player nickname (default: `StrategicBot`) |
| `--matches <N>` | Number of matches to play (default: `1`) |

## Prerequisites

1. **Invite code** -- obtain one from the operator or generate via:
   ```bash
   bash scripts/internal/create_invite_codes.sh <render_url> <count>
   ```
2. **WebFetch tool** -- required for HTTP requests to the game server
3. **Game server running** -- the target URL must be reachable

## Game Flow

Same HTTP flow as `/playtest` for setup. The difference is in decision-making
during the game loop (Steps 5a and 5b).

### Setup (Steps 1-4)

Identical to `/playtest`:

1. `POST {url}/enter-code` with `code={invite_code}`
2. Extract `link_uuid` from redirect
3. `POST {url}/play/{link_uuid}/nickname` with `nickname={nickname}`
4. Skip onboarding if present
5. Select AI: `POST {url}/play/{link_uuid}/select-ai` with `model_id=bud_bot`

### Step 5: Game Loop (Strategic)

#### 5a: Auction Phase -- Strategic Bidding

When `id="bid-panel"` is found in the HTML:

1. **Extract hand information** from the HTML:
   - Find all card elements in the hand area
   - Parse card rank and suit from element classes or data attributes
   - Look for patterns like `card--<rank>-<suit>` or `data-card="<rank><suit>"`

2. **Evaluate hand strength:**

   Count cards by suit to find the longest suit (candidate trump):
   ```
   For each suit (hearts, diamonds, clubs, spades):
     count = number of cards of that suit in hand
     high_cards = count of A, K, Q in that suit
     bowers = count of J of that suit + J of same-color suit
   ```

   Bid calculation heuristic:
   ```
   trump_suit = suit with most cards (break ties by high_card count)
   trump_count = cards in trump_suit
   bower_count = J of trump_suit + J of same-color suit (0, 1, or 2)
   high_count = A, K, Q of trump_suit
   off_aces = A of non-trump suits

   estimated_tricks = trump_count + bower_count + off_aces
   ```

   Bidding thresholds:
   | Estimated Tricks | Bid |
   |-----------------|-----|
   | < 5 | Pass (bid_n=0) |
   | 5 | Bid 5 |
   | 6 | Bid 6 |
   | 7 | Bid 7 |
   | 8+ | Bid 8 |

   Cap the bid at 8 (conservative -- avoid moon/loner complexity in MVP).

3. **Determine bid type:**
   - If bidding > 0: `bid_type=suit` with the trump suit
   - If passing: `bid_n=0&bid_type=regular`

4. **Submit bid:**
   ```
   POST {url}/play/{link_uuid}/bid
   Content-Type: application/x-www-form-urlencoded

   turn_number={N}&bid_n={bid}&bid_type={type}&trump_suit={suit}
   ```

   If the server requires different form fields for trump selection, adapt
   based on the form inputs visible in the bid panel HTML.

5. **Log the bid decision:**
   Record hand composition, estimated tricks, and bid for strategy analysis.

#### 5b: Trick Play -- Strategic Card Selection

When `id="card-play-form"` is found in the HTML:

1. **Parse game state from HTML:**
   - Cards already played in the current trick (visible in trick area)
   - Lead suit (suit of the first card played this trick)
   - Trump suit (from contract display)
   - Cards in hand (legal cards have `card--legal` class)

2. **Determine legal cards:**
   - Find all elements with `card--legal` class
   - Extract their card identity (rank + suit) and `data-card-index`

3. **Apply card selection strategy:**

   **If leading (first to play in trick):**
   - Lead with strongest trump if holding 3+ trump
   - Lead with off-suit Ace if holding one
   - Otherwise lead longest non-trump suit, highest card

   **If following and must follow suit (have cards in lead suit):**
   - If can beat all cards currently in trick: play lowest winning card
   - If cannot beat: play lowest card in suit (save high cards)

   **If following and void in lead suit (can trump or discard):**
   - If partner is winning the trick: discard lowest off-suit card
   - If opponents are winning: trump with lowest trump
   - If no trump available: discard lowest off-suit card

   **Simplification:** When parsing is ambiguous (can't determine who played
   which cards or who is winning), fall back to playing the first legal card.
   Log the fallback for analysis.

4. **Submit play:**
   ```
   POST {url}/play/{link_uuid}/play-card
   Content-Type: application/x-www-form-urlencoded

   turn_number={N}&card_index={selected_index}
   ```

5. **Log the play decision:**
   Record cards available, strategy applied, and card chosen.

#### 5c-5f: Paused Reveal, Hand Result, Match Result, Moon Exchange

Same as `/playtest`:

- **Paused reveal:** POST `/next`
- **Hand result:** Log scores, POST `/next-hand`
- **Match result:** Log final scores and winner
- **Moon exchange:** Select first N cards (strategic exchange is out of scope)

### Step 6: Log Observations

After each match, log observations to a session file.

**Output file:** `plans/sessions/playtest_strategic_{YYYY-MM-DD}_{HHmmss}.md`

**Schema per match:**

```markdown
## Match {N}

- **Match ID:** {link_uuid}
- **Mode:** strategic (HTTP with intelligent play)
- **Duration:** {seconds}s
- **Final Score:** You {score_human} -- AI {score_ai}
- **Winner:** {human|ai}
- **Hands Played:** {N}
- **Bids Made:** {count} (out of {total_auction_turns})
- **Bids Won:** {count}
- **Contracts Made:** {count} / {bids_won}
- **AI Model:** bud_bot

### Bidding Summary
| Hand | Cards in Trump | Bowers | Estimated Tricks | Bid | Won Auction | Made Contract |
|------|---------------|--------|-----------------|-----|-------------|---------------|
| 1 | 4H | 1 | 6 | 6 | Yes | Yes (7 tricks) |
| 2 | 3S | 0 | 4 | Pass | - | - |
| ... | | | | | | |

### Strategy Decisions Log
- Hand 1, Trick 3: Led with Ace of trump (3 trump remaining)
- Hand 1, Trick 5: Trumped opponent's off-suit lead (void in clubs)
- Hand 2: Passed (only 3 spades, no bowers)
- ...

### Interesting Hands
- {Hands with unusual outcomes: set despite strong hand, made despite weak hand,
  bower interactions, all-trump hands, etc.}

### Anomalies
- {HTTP errors, unexpected phases, stuck states, scoring discrepancies}
- {Strategy fallbacks (times card selection fell back to first-legal)}

### Bug Indicators
- {Any scoring errors: tricks won != expected}
- {Bower resolution issues: wrong card won a trick}
- {Contract fulfillment errors: bid made/set incorrectly calculated}
- {Turn order issues: played out of turn, wrong player led}
```

## Card Parsing Guide

### Identifying Cards in Hand

Look for card elements in the hand area. Common HTML patterns:

```
<button class="card card--ace-hearts card--legal" data-card-index="3">
<button class="card card--jack-spades card--legal" data-card-index="7">
```

Extract rank and suit from the class name pattern `card--{rank}-{suit}`.

### Identifying Cards in Trick Area

Cards played in the current trick appear in the trick area:

```
<div class="trick-card trick-card--seat-0">
  <div class="card card--king-diamonds">
```

The seat class indicates which player played the card.

### Identifying Trump and Contract

Look for contract information in the game header:

```
<span class="contract-trump">{suit}</span>
<span class="contract-bid">{bid_number}</span>
<span class="contract-bidder">{seat}</span>
```

### Identifying Bowers

In suit contracts, bowers are:
- **Right bower:** Jack of trump suit
- **Left bower:** Jack of same-color suit (hearts/diamonds share, clubs/spades share)

Color pairings:
- Hearts <-> Diamonds (red)
- Clubs <-> Spades (black)

When counting hand strength, check for both bowers.

## Error Handling

Same as `/playtest`:
- **404:** Log and abort
- **429:** Wait or abandon stale matches
- **409:** Re-fetch and retry
- **500:** Retry once after 5s

### Strategy-Specific Error Handling

- **Cannot parse hand:** Fall back to first legal card. Log the parsing failure.
- **Cannot determine trump:** Fall back to passing in auction, first legal card
  in play. Log the parsing failure.
- **Ambiguous trick state:** Fall back to first legal card. Log the ambiguity.

The strategy is best-effort. Parsing failures degrade gracefully to
`/playtest` behavior (always pass, first legal card). Every fallback is
logged so we can improve parsing over time.

## Performance Expectations

| Metric | Value |
|--------|-------|
| Time per match | ~5-10 min (same as HTTP-only /playtest) |
| Overhead vs /playtest | Negligible (strategy computation is instant) |
| Expected win rate | ~30-50% vs bud_bot (depends on hand distribution) |

## Bug Categories This Mode Catches

Unlike `/playtest` (which always passes and plays first legal card), strategic
play exercises these additional code paths:

| Code Path | Always-Pass Mode | Strategic Mode |
|-----------|-----------------|----------------|
| Human winning auction | Never | Frequent |
| Human as declarer | Never | Frequent |
| Trump contracts (human-declared) | Never | Frequent |
| Bower trick resolution | Rare (only AI-declared) | Frequent |
| Contract made/set scoring | Only AI contracts | Both sides |
| Non-trivial trick outcomes | Only AI-driven | Both sides |

## Example Invocation

```
/playtest-strategic --url https://bid-euchre.onrender.com --code ABC12345 --nickname StrategicBot --matches 3
```

This plays 3 complete matches with intelligent bidding and card play, logging
detailed strategy decisions and anomalies after each match.

## NOT in Scope

- Playwright browser snapshots (use `/playtest-hybrid` for that)
- Moon/loner bidding (bid capped at 8)
- Strategic moon exchange (first N cards selected)
- Auto-filing GitHub issues
- Overnight cron loop integration
- Optimal play (this is heuristic, not minimax)
