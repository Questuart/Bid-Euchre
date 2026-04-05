---
name: playtesting
description: Play the browser game via HTTP endpoints to find bugs, test UX, and generate match data. Use from flex lanes for automated game proving and research.
---

# /playtest -- Automated Browser Game Playtesting

Play complete matches of the Bid Euchre browser game via direct HTTP calls to
the hosted web app. Logs observations per match for bug detection and research.

## When to Use

- You want to play through complete matches on the live game to find bugs
- You want to generate match data for research or quality assurance
- The orchestrator has assigned a playtesting task to your lane
- You want to verify game flow end-to-end after a deployment

## Arguments

| Argument | Description |
|----------|-------------|
| `--url <render_url>` | Base URL of the hosted game (e.g., `https://bid-euchre.onrender.com`) |
| `--code <invite_code>` | Invite code for game access |
| `--nickname <name>` | Player nickname (default: `PlaytestBot`) |
| `--matches <N>` | Number of matches to play (default: `1`) |

## Prerequisites

1. **Invite code** -- obtain one from the operator, or generate codes against
   the **hosted** database:
   ```bash
   DATABASE_URL="<hosted_db_url>" bash scripts/internal/create_invite_codes.sh [count] [label]
   ```
   Without `DATABASE_URL`, the script writes to a local SQLite file, which
   is only useful for local dev servers — those codes won't work on the
   hosted deployment.
2. **WebFetch tool** -- required for making HTTP requests to the game server
3. **Game server running** -- the target URL must be reachable

## Game Flow Overview

The browser game uses HTMX with server-rendered HTML partials. Each action is
a POST request with form data. The server returns HTML that we parse to
determine the current game phase and available actions.

### Phase Progression

```
enter-code -> nickname -> onboarding/skip -> select-ai -> [game loop] -> match result
```

### Game Loop Phases

Within a match, the game cycles through hands. Each hand follows:

```
auction (bid/pass) -> trick_play (play cards) -> hand_result -> next-hand
```

Paused states (requiring POST /next to advance):
- AI auction bids being revealed one at a time
- AI card plays being revealed one at a time (per-card pacing)
- Trick completion interstitials
- Redeal (all players passed)

## Execution Steps

### Step 1: Enter Invite Code

```
POST {url}/enter-code
Content-Type: application/x-www-form-urlencoded

code={invite_code}
```

**Response:** 302 redirect to `/play/{link_uuid}` (or HX-Redirect header if
sending `HX-Request: true`). Extract `link_uuid` from the redirect URL.

**Important:** Do NOT send `HX-Request: true` on this first request. Use a
plain POST so you get a 302 redirect. Extract the `link_uuid` from the
`Location` header or response URL.

### Step 2: Set Nickname

```
POST {url}/play/{link_uuid}/nickname
Content-Type: application/x-www-form-urlencoded

nickname={nickname}
```

**Response:** HTML partial -- either the onboarding welcome letter (new
player) or model selection (returning player).

### Step 3: Skip Onboarding

If the response from Step 2 contains `onboarding` or `Welcome`, skip it:

```
POST {url}/play/{link_uuid}/onboarding/skip
```

**Response:** HTML partial with model selection form.

### Step 4: Select AI Model and Start Match

```
POST {url}/play/{link_uuid}/select-ai
Content-Type: application/x-www-form-urlencoded

model_id=bud_bot
```

**Response:** HTML partial with the game board. Parse the phase from
the HTML to determine the initial state.

### Step 5: Game Loop

Repeat until match result is reached:

#### Detecting the Current Phase

Parse the HTML response for phase indicators:

| HTML Indicator | Phase | Action |
|----------------|-------|--------|
| `id="bid-panel"` | Auction (human turn) | Submit a bid |
| `id="match-result"` | Match complete | Log result, exit loop |
| `id="hand-result"` | Hand complete | POST next-hand |
| `id="card-play-form"` | Trick play (human turn) | Play a card |
| `id="model-select"` | Model selection | POST select-ai |
| `id="moon-exchange-select"` | Moon exchange selection | POST exchange (select 2 cards) |
| `id="moon-exchange"` (without `moon-exchange-select`) | Moon exchange summary | POST next |
| `class="next-controls"` | Paused reveal (catch-all) | POST next |

#### 5a: Auction Phase -- Submit Bid (Always Pass for MVP)

When `id="bid-panel"` is found in the HTML:

1. Extract `turn_number` from the hidden input: `name="turn_number" value="N"`
2. Submit a pass:

```
POST {url}/play/{link_uuid}/bid
Content-Type: application/x-www-form-urlencoded

turn_number={N}&bid_n=0&bid_type=regular
```

#### 5b: Trick Play -- Play a Card

When `id="card-play-form"` is found in the HTML:

1. Extract `turn_number` from: `name="turn_number" value="N"`
2. Find legal card buttons: `class="card card--* card--legal"` with
   `data-card-index="N"`
3. Pick the first legal card index (MVP strategy)
4. Submit:

```
POST {url}/play/{link_uuid}/play-card
Content-Type: application/x-www-form-urlencoded

turn_number={N}&card_index={first_legal_index}
```

#### 5c: Paused Reveal -- Advance

When `class="next-controls"` is found but none of the above action forms:

```
POST {url}/play/{link_uuid}/next
```

This advances AI bid reveals, AI card reveals, trick interstitials, and
redeal transitions.

#### 5d: Hand Result -- Next Hand

When `id="hand-result"` is found:

1. Log the hand result (parse scores from the HTML)
2. Advance:

```
POST {url}/play/{link_uuid}/next-hand
```

#### 5e: Match Result -- Log and Finish

When `id="match-result"` is found:

1. Parse winner from: `class="result-title"` (contains "You Win!" or "You Lose")
2. Parse final scores from: `class="score-final"` elements
3. Parse hands played from: `class="hands-count"` text
4. Log the match observation
5. If more matches remain, start a new match:

```
POST {url}/play/{link_uuid}/new-match
```

Then re-enter the game loop from Step 4 (select-ai).

#### 5f: Moon Exchange Selection (if encountered)

When `id="moon-exchange-select"` is detected (the interactive selection phase):

1. Find card buttons with `data-exchange-index="N"` attributes
2. Select the first 2 exchange indices (MVP: no strategic selection)
3. Map the selected `data-exchange-index` values to the hidden form fields
   `card_index_0` and `card_index_1` (these are the actual `<input name="...">`
   fields inside `id="exchange-form"`)
4. Submit the exchange form:

```
POST {url}/play/{link_uuid}/exchange
Content-Type: application/x-www-form-urlencoded

card_index_0={exchange_index_0}&card_index_1={exchange_index_1}
```

#### 5g: Moon Exchange Summary (interstitial)

When `id="moon-exchange"` is detected (without `id="moon-exchange-select"`),
this is the summary showing which cards were swapped. Advance like any other
interstitial:

```
POST {url}/play/{link_uuid}/next
```

### Step 6: Log Observations

After each match, log observations to a session file.

**Output file:** `plans/sessions/playtest_{YYYY-MM-DD}_{HHmmss}.md`

**Schema per match:**

```markdown
## Match {N}

- **Match ID:** {link_uuid}
- **Duration:** {seconds}s
- **Final Score:** You {score_human} -- AI {score_ai}
- **Winner:** {human|ai}
- **Hands Played:** {N}
- **AI Model:** bud_bot

### Anomalies
- {any HTTP errors, unexpected phases, stuck states}

### Strategy Notes
- Always passed in auction (MVP)
- Always played first legal card (MVP)
```

## HTML Parsing Guide

The game returns server-rendered HTML. Key parsing patterns:

### Extract turn_number
```
Look for: <input type="hidden" name="turn_number" value="(\d+)">
```

### Extract legal card indices
```
Look for: data-card-index="(\d+)" on elements with class containing "card--legal"
```

### Extract scores from hand_result
```
Look for: class="score-value--human">{score}</span>
Look for: class="score-value--ai">{score}</span>
```

### Extract match status
```
Look for: data-match-status="(setup|active|complete)"
```

### Detect phase from game_board
Priority order (check in this order):
1. `id="match-result"` -> match complete
2. `id="hand-result"` -> hand complete
3. `id="bid-panel"` -> auction (human's turn to bid)
4. `id="card-play-form"` -> trick play (human's turn to play)
5. `id="model-select"` -> needs model selection
6. `id="moon-exchange-select"` -> moon exchange selection (POST exchange)
7. `id="moon-exchange"` (without `moon-exchange-select`) -> moon exchange summary (POST next)
8. `class="next-controls"` -> paused, needs /next to advance (catch-all)

## Error Handling

### HTTP Errors
- **404:** Game not found -- link_uuid may be invalid. Log and abort.
- **429:** Match limit reached -- wait or abandon stale matches.
- **409:** Turn conflict -- re-fetch the game page and retry with fresh state.
- **500:** Server error -- log, wait 5s, retry once. If persistent, abort.

### Stuck State Detection
If the same phase repeats more than 20 times without progress (no score
changes, no turn_number changes), the game is stuck. Log the anomaly and
abort the match.

### Cookie Handling
The game sets a `player_link` cookie after entering an invite code. If
using WebFetch, cookies may not persist between requests. As a workaround,
always include the `link_uuid` in the URL path (which the game uses as the
primary player identifier).

## Implementation Notes for WebFetch

When using the WebFetch tool to make requests:

1. **Content-Type:** Always set `Content-Type: application/x-www-form-urlencoded`
   for POST requests
2. **Follow redirects:** The enter-code endpoint returns a 302 redirect.
   WebFetch may auto-follow; check the final URL for the link_uuid
3. **Parse HTML text:** The response body is HTML. Use string matching or
   regex patterns (not a DOM parser) to detect phases and extract values
4. **No HX-Request header:** Do not send `HX-Request: true` unless you want
   HTMX partial responses. For playtesting, either mode works, but full
   page responses are easier to parse for phase detection

## Observation Categories

### Bug Indicators (file as issues)
- HTTP 500 errors
- Unexpected phase transitions (e.g., trick_play before auction)
- Score calculation errors (tricks won != expected based on card plays)
- Game stuck in a phase for >20 iterations
- Server returns empty/malformed HTML

### UX Notes (log for research)
- How many /next clicks are needed per hand (pacing friction)
- Time to complete a match
- Frequency of redeals
- Moon/loner occurrences

### Strategy Notes (log for research)
- Observed AI bidding patterns
- Trump suit distribution
- How often the AI team makes their bid
- Score trajectories

## Example Invocation

```
/playtest --url https://bid-euchre.onrender.com --code ABC12345 --nickname TestBot --matches 3
```

This plays 3 complete matches, logging observations after each. Total
expected time: 15-30 minutes depending on hand count per match.

## NOT in MVP Scope

- Playwright/browser automation mode
- Strategic bidding (bid > 0)
- Strategic card selection (anything beyond first legal card)
- Auto-filing GitHub issues for detected bugs
- Overnight cron loop integration
- Context clear and resume between matches
