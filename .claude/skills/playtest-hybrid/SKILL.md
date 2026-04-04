---
name: playtest-hybrid
description: Play the browser game via HTTP with Playwright snapshots at key moments for visual verification. Combines speed with visual coverage.
---

# /playtest-hybrid -- Hybrid Browser Game Playtesting

Play complete matches of the Bid Euchre browser game using HTTP endpoints for
speed, with Playwright browser snapshots at key game moments for visual
verification. Best of both worlds: fast iteration with visual coverage.

## When to Use

- You want fast playtesting with visual verification of UI state
- You need to cover Go-Live Checklist sections C1-C5 (high-churn regression),
  D (lifecycle), and B (open issues)
- You want to verify both functional correctness AND rendering fidelity
- The orchestrator has assigned a hybrid playtesting task to your lane

## Arguments

| Argument | Description |
|----------|-------------|
| `--url <render_url>` | Base URL of the hosted game (e.g., `https://bid-euchre.onrender.com`) |
| `--code <invite_code>` | Invite code for game access |
| `--nickname <name>` | Player nickname (default: `HybridBot`) |
| `--matches <N>` | Number of matches to play (default: `1`) |

## Prerequisites

1. **Invite code** -- obtain one from the operator or generate via:
   ```bash
   bash scripts/internal/create_invite_codes.sh <render_url> <count>
   ```
2. **WebFetch tool** -- required for HTTP requests to the game server
3. **Playwright MCP** -- required for browser snapshots (`mcp__playwright__*`)
4. **Game server running** -- the target URL must be reachable

## Architecture

```
HTTP (fast)                    Playwright (visual snapshots)
    |                                    |
    v                                    v
join -> auction -> trick -> ...    snapshot at key moments:
    |                                - auction complete
    |                                - each trick result
    |                                - hand result (scores)
    |                                - match result (leaderboard)
    v
next match
```

The HTTP path drives all game state transitions (identical to `/playtest`).
Playwright is opened once and navigated to the game URL for snapshots only --
it does NOT drive gameplay.

## Execution Steps

### Step 1: Start HTTP Game Session

Follow the exact same HTTP flow as `/playtest`:

1. `POST {url}/enter-code` with `code={invite_code}`
2. Extract `link_uuid` from redirect
3. `POST {url}/play/{link_uuid}/nickname` with `nickname={nickname}`
4. Skip onboarding if present: `POST {url}/play/{link_uuid}/onboarding/skip`
5. Select AI: `POST {url}/play/{link_uuid}/select-ai` with `model_id=bud_bot`

### Step 2: Open Playwright Browser (Once)

After the HTTP session is established:

1. Navigate Playwright to `{url}/play/{link_uuid}`
2. Wait for the game board to render
3. Take an initial snapshot to verify the board loaded correctly

The Playwright browser session stays open throughout all matches. It is used
ONLY for snapshots, never for interaction.

### Step 3: Game Loop (HTTP-driven)

Run the standard game loop via HTTP (see `/playtest` for full details):

- **Auction:** Always pass (`bid_n=0&bid_type=regular`)
- **Trick play:** Play first legal card
- **Paused reveal:** POST `/next` to advance
- **Moon exchange:** Select first N cards (MVP)

### Step 4: Playwright Snapshots at Key Moments

Take snapshots at these game transitions. After each HTTP action that
transitions the game to a key moment, refresh the Playwright page and
capture state.

#### Snapshot Point 1: Auction Complete

**Trigger:** First trick-play phase detected after auction.

**Capture:**
```
mcp__playwright__browser_navigate -> {url}/play/{link_uuid}
mcp__playwright__browser_snapshot
```

**Verify visually:**
- Contract and trump suit are displayed correctly
- Bidder identity is shown
- Score displays are initialized

**Go-Live coverage:** C1 (auction UI), D (lifecycle transition)

#### Snapshot Point 2: After Each Trick

**Trigger:** Trick interstitial detected (next-controls after 4 cards played).

**Capture:**
```
mcp__playwright__browser_navigate -> {url}/play/{link_uuid}
mcp__playwright__browser_snapshot
```

**Verify visually:**
- Trick area shows all 4 cards played
- Bower badges render correctly (right/left bower indicators)
- Trick winner is highlighted
- Trick count updates

**Go-Live coverage:** C2 (trick display), C3 (bower badges), C4 (card rendering)

#### Snapshot Point 3: Hand Result

**Trigger:** `id="hand-result"` detected in HTTP response.

**Capture:**
```
mcp__playwright__browser_navigate -> {url}/play/{link_uuid}
mcp__playwright__browser_snapshot
```

**Verify visually:**
- Team scores are displayed and match HTTP-parsed values
- Bid result (made/set) is shown correctly
- Score animation or highlight is visible
- Running score totals are correct

**Go-Live coverage:** C5 (scoring display), D (hand lifecycle)

#### Snapshot Point 4: Match Result

**Trigger:** `id="match-result"` detected in HTTP response.

**Capture:**
```
mcp__playwright__browser_navigate -> {url}/play/{link_uuid}
mcp__playwright__browser_snapshot
```

**Verify visually:**
- Winner announcement is correct (matches HTTP-parsed result)
- Final scores are displayed
- Leaderboard updates reflect the match outcome
- New match / exit options are available

**Go-Live coverage:** D (match lifecycle), C5 (final scoring)

### Step 5: Cross-Validate HTTP vs Visual

After each snapshot, compare the HTTP-parsed state with the visual state:

| Check | HTTP Source | Visual Source |
|-------|-----------|--------------|
| Contract/trump | Parsed from HTML | Displayed in game header |
| Scores | Parsed `score-value--human/ai` | Rendered in scoreboard |
| Winner | Parsed `result-title` | Shown in match-result panel |
| Phase | Detected from HTML ids | Visible UI state |

Log any discrepancies as **anomalies** -- these indicate rendering bugs or
state synchronization issues.

### Step 6: Log Observations

After each match, log observations to a session file.

**Output file:** `plans/sessions/playtest_hybrid_{YYYY-MM-DD}_{HHmmss}.md`

**Schema per match:**

```markdown
## Match {N}

- **Match ID:** {link_uuid}
- **Mode:** hybrid (HTTP + Playwright snapshots)
- **Duration:** {seconds}s
- **Final Score:** You {score_human} -- AI {score_ai}
- **Winner:** {human|ai}
- **Hands Played:** {N}
- **Snapshots Taken:** {count}
- **AI Model:** bud_bot

### Visual Verification Results
- Auction display: {pass|fail|skipped} -- {notes}
- Trick rendering: {pass|fail|skipped} -- {notes}
- Bower badges: {pass|fail|skipped} -- {notes}
- Score display: {pass|fail|skipped} -- {notes}
- Match result: {pass|fail|skipped} -- {notes}

### HTTP vs Visual Discrepancies
- {any mismatches between HTTP-parsed state and visual state}

### Anomalies
- {any HTTP errors, unexpected phases, stuck states}

### Go-Live Checklist Coverage
- C1 (auction UI): {covered|not covered}
- C2 (trick display): {covered|not covered}
- C3 (bower badges): {covered|not covered}
- C4 (card rendering): {covered|not covered}
- C5 (scoring display): {covered|not covered}
- D (lifecycle): {covered|not covered}
```

## Error Handling

### HTTP Errors

Same as `/playtest`:
- **404:** Log and abort
- **429:** Wait or abandon stale matches
- **409:** Re-fetch and retry
- **500:** Retry once after 5s

### Playwright Errors

- **Timeout on navigate:** Skip this snapshot, log as anomaly, continue
  HTTP-driven gameplay. Playwright failures must never block the game loop.
- **Snapshot failure:** Log the failure, continue. Visual coverage is
  best-effort; HTTP correctness testing continues regardless.
- **Browser crash:** Log anomaly. Continue HTTP-only for remaining matches.
  Do not attempt to restart Playwright mid-match.

### Key Principle

HTTP drives the game. Playwright is advisory. If Playwright fails, degrade
gracefully to HTTP-only mode (equivalent to `/playtest`). Never let a
Playwright issue block game progression.

## Performance Expectations

| Metric | Value |
|--------|-------|
| Time per match | ~8-15 min (HTTP speed + snapshot overhead) |
| Snapshots per match | ~12-20 (1 auction + ~10 tricks + ~1-2 hand results + 1 match result) |
| Playwright overhead per snapshot | ~3-5s (navigate + render + capture) |

## Example Invocation

```
/playtest-hybrid --url https://bid-euchre.onrender.com --code ABC12345 --nickname HybridBot --matches 2
```

This plays 2 complete matches with visual snapshots at each key moment.

## NOT in Scope

- Playwright-ONLY mode (use Playwright MCP directly for that)
- Strategic bidding or card play (use `/playtest-strategic` for that)
- Auto-filing GitHub issues (manual review of observations first)
- Overnight cron loop integration
