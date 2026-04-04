---
name: playtest-playwright
description: Play the browser game via Playwright MCP tools for visual verification — colors, layout, CSS, icons, animations, and responsive behavior. Use from flex lanes for visual QA and go-live proving.
---

# /playtest-playwright -- Visual Browser Game Testing (Playwright)

Drive the Bid Euchre browser game through Playwright MCP tools to visually
verify colors, layout, card rendering, icons, animations, responsive behavior,
and accessibility. This complements `/playtest` (HTTP-only) by exercising the
actual rendered DOM and taking visual snapshots at key moments.

## When to Use

- You want to visually verify the game UI (colors, layout, card rendering)
- You are running go-live checklist sections A, C2, G, or H
- You need to test responsive/mobile behavior at different viewport sizes
- You want to inspect rendered CSS, computed styles, or visual regressions
- You want to take snapshots of key game states for review
- The orchestrator assigned a visual QA task to your lane

## When NOT to Use

- For pure functional testing (use `/playtest` with HTTP instead)
- For load testing or high-volume match generation
- When the game server is not running

## Arguments

| Argument | Description |
|----------|-------------|
| `--url <render_url>` | Base URL of the hosted game (e.g., `https://bid-euchre.onrender.com`) |
| `--code <invite_code>` | Invite code for game access |
| `--nickname <name>` | Player nickname (default: `PlaytestBot`) |
| `--matches <N>` | Number of matches to play (default: `1`) |

## Prerequisites

1. **Invite code** -- obtain one from the operator or generate via:
   ```bash
   bash scripts/internal/create_invite_codes.sh <render_url> <count>
   ```
2. **Playwright MCP tools** -- the session must have Playwright MCP server
   available (browser_navigate, browser_snapshot, browser_click, etc.)
3. **Game server running** -- the target URL must be reachable

## Playwright MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Navigate to a URL |
| `browser_snapshot` | Take an accessibility snapshot of the current page (DOM tree) |
| `browser_take_screenshot` | Take a visual screenshot (PNG) |
| `browser_click` | Click an element by accessible name or role |
| `browser_fill_form` | Fill form fields by label |
| `browser_select_option` | Select dropdown option |
| `browser_press_key` | Press keyboard keys |
| `browser_evaluate` | Run JavaScript in the page context |
| `browser_resize` | Resize the viewport (for mobile testing) |
| `browser_hover` | Hover over an element |
| `browser_wait_for` | Wait for an element or condition |

## Game Flow (Playwright)

### Step 1: Navigate to Game

```
browser_navigate → {url}
```

**Visual check:** Page loads with the game branding. Look for the invite code
entry form.

Take a **snapshot** to confirm the landing page renders correctly.

### Step 2: Enter Invite Code

```
browser_fill_form → field: "code" or "Invite Code", value: {invite_code}
browser_click → "Enter" or "Join Game" button
```

**Visual check:** Form submits cleanly, page transitions to nickname entry.

### Step 3: Set Nickname

```
browser_fill_form → field: "nickname" or "Nickname", value: {nickname}
browser_click → "Submit" or "Continue" button
```

**Visual check:** Nickname is accepted, page shows either onboarding welcome
letter or model selection.

### Step 4: Skip Onboarding (if shown)

If a welcome letter / onboarding UI appears:

```
browser_click → "Skip" button
```

**Visual check:** Onboarding dismisses cleanly, model selection appears.

### Step 5: Select AI Model

```
browser_click → "bud_bot" or equivalent AI model option
browser_click → "Start Match" or submit button
```

**Visual check (snapshot):** Model selection screen renders correctly. AI
model options are visible with descriptions.

### Step 6: Game Loop

Repeat until match result is reached. At each state, take a **snapshot** to
read the current game state.

#### Phase Detection via Snapshot

Use `browser_snapshot` to read the accessibility tree. Detect the current
phase by looking for these patterns in the snapshot output:

| Snapshot Pattern | Phase | Action |
|-----------------|-------|--------|
| "Match Result" heading | Match complete | Log result, exit loop |
| "Hand Result" or hand result content | Hand complete | Click "Next Hand" or equivalent |
| Bid panel / bid form controls | Auction (human turn) | Submit a bid |
| Card play area with legal cards | Trick play (human turn) | Click a legal card |
| "Next" button visible (no action form) | Paused reveal | Click "Next" |
| Model selection controls | New match setup | Select AI model |
| "Exchange" form / moon exchange | Moon exchange | Select and confirm exchange |

#### 6a: Auction Phase -- Submit Bid

When the snapshot shows bid controls:

1. Take a **snapshot** to read the bid panel
2. Identify the bid dropdown and available options
3. Select "Pass" (MVP strategy -- always pass):

```
browser_select_option → bid dropdown: "Pass" or "0"
browser_click → "Submit Bid" or "Bid" button
```

**Visual checks (Section A of go-live checklist):**
- [ ] Bid dropdown defaults to the minimum legal bid, NOT "Pass" (A2a)
- [ ] Auction log is open and centered in the compass area (A4a/C5a)
- [ ] Auction log entries show **colored suit icons** (C5b)
- [ ] Contract/trump bar is hidden during auction (B2a, if applicable)
- [ ] AI player names appear in **blue (#64b5f6)** (A7a)

#### 6b: Trick Play -- Play a Card

When the snapshot shows playable cards:

1. Take a **snapshot** to read the card play area
2. Identify legal cards (cards with interactive/clickable affordance)
3. Click the first legal card (MVP strategy):

```
browser_click → first legal card element
```

**Visual checks (Sections A, C2, G of go-live checklist):**
- [ ] Hand is sorted with **alternating red/black suits** (A1a)
- [ ] Trump suit appears **first** in sort order (A1b)
- [ ] Left bower sorts with the **trump group** (A1d)
- [ ] Right bower shows **"RB" badge** + original printed suit icon (C2a)
- [ ] Left bower shows **"LB" badge** + original printed suit icon (C2b)
- [ ] Clubs/spades icons are **dark/black** with shadow (A3a/A3b)
- [ ] Hearts/diamonds icons are **red** (A3c)
- [ ] "10" displayed (not "T") on ten cards (G2a)
- [ ] Rank text (A, K, Q, J, 10) is **white** (G3f)
- [ ] "Leader" label appears on the trick leader's seat (A5a)

#### 6c: Paused Reveal -- Advance

When the snapshot shows a "Next" button but no action form:

```
browser_click → "Next" button
```

**Visual checks (Section C1 — pacing):**
- [ ] AI card appears with a visible **thinking delay** (B4a, if applicable)
- [ ] After human plays, card appears and **"Next" button** shown (B4b)
- [ ] No auto-advance -- every transition requires a Next click (C1d)
- [ ] "Continue to the next trick" message appears after trick completes (C1c)

#### 6d: Hand Result -- Next Hand

When the snapshot shows hand result content:

1. Take a **snapshot** of the hand result screen
2. Log scores and trick counts
3. Click "Next Hand" or equivalent:

```
browser_click → "Next Hand" or "Continue" button
```

**Visual checks (Sections A5, C3 of go-live checklist):**
- [ ] RB/LB legend appears in trick history for **suit contracts** (A5b)
- [ ] Legend absent for HIGH/LOW contracts (A5c)
- [ ] Score bar shows **"Your Team: X | Opponent: Y"** (C3a/A6a)
- [ ] Trick counts are **team-colored**: green (human) / blue (AI) (C3c)
- [ ] Hand result uses **positive/negative styling** (C3e)

#### 6e: Match Result -- Log and Finish

When the snapshot shows match result:

1. Take a **screenshot** (`browser_take_screenshot`) of the final result
2. Parse winner and final scores from the snapshot
3. Log the match observation
4. If more matches remain:

```
browser_click → "New Match" or "Play Again" button
```

Then re-enter from Step 5 (select AI model).

#### 6f: Moon Exchange (if encountered)

When the snapshot shows exchange controls:

1. Take a **snapshot** to read available cards
2. Select the first N cards (MVP: no strategic selection):

```
browser_click → first card checkbox
browser_click → second card checkbox (etc.)
browser_click → "Confirm Exchange" button
```

**Visual check:** Bower cards in exchange show original suit + RB/LB badges.

## Visual Verification Procedures

### Procedure V1: Color Verification

Run JavaScript to extract computed styles and verify color values:

```
browser_evaluate → document.querySelector('.suit-icon--hearts')?.computedStyleMap?.()
```

Or use snapshot + visual reasoning to check:

| Element | Expected Color | Check ID |
|---------|---------------|----------|
| Hearts/diamonds suit icons | Red | A3c |
| Clubs/spades suit icons | Dark/black with shadow | A3a/A3b |
| AI player names | Blue (#64b5f6) | A7a |
| Human team scores | Green | G3d |
| AI team scores | Blue | G3e |
| Card rank text | White | G3f |

### Procedure V2: Layout Verification

Take a **screenshot** and visually inspect:

- Card alignment in hand area
- Trick area centering
- Score bar layout
- Auction log positioning (center during auction, below hand details after)
- Tab navigation bar alignment
- No overlapping elements

### Procedure V3: Responsive Testing

Resize the viewport and re-check layout:

```
browser_resize → width: 375, height: 812    (iPhone SE)
browser_take_screenshot
```

**Visual checks (Section H of go-live checklist):**
- [ ] No horizontal scrollbar at 375px width (H1a)
- [ ] All tabs reachable -- tabs wrap or scroll (H1b)
- [ ] Card play buttons large enough to tap (H1c)
- [ ] Bid dropdown usable on mobile (H1d)

Then restore desktop:

```
browser_resize → width: 1280, height: 800
```

Also test at 200% zoom:

```
browser_evaluate → document.body.style.zoom = '2'
browser_take_screenshot
```

**Visual checks:**
- [ ] No overlapping elements at 200% zoom (H2a)
- [ ] All controls reachable at 150% zoom (H2b)

### Procedure V4: Accessibility Snapshot

Use `browser_snapshot` to verify the accessibility tree:

- [ ] Card elements have meaningful aria-labels (suit, rank, copy index) (H3a)
- [ ] Next/Skip buttons have descriptive labels (H3b)
- [ ] Auction log is semantically structured (H3c)

## Observation Logging

After each match, log observations to a session file.

**Output file:** `plans/sessions/playtest_visual_{YYYY-MM-DD}_{HHmmss}.md`

**Schema per match:**

```markdown
## Match {N}

- **Match ID:** {link_uuid}
- **Duration:** ~{minutes}min
- **Final Score:** You {score_human} -- AI {score_ai}
- **Winner:** {human|ai}
- **Hands Played:** {N}
- **AI Model:** bud_bot
- **Viewport:** {width}x{height}

### Visual Checks Performed

| Check | Section | Result | Notes |
|-------|---------|--------|-------|
| Suit icon colors | A3 | PASS/FAIL | {details} |
| Hand sorting | A1 | PASS/FAIL | {details} |
| Bower badges | C2 | PASS/FAIL | {details} |
| Score labels | A6/C3 | PASS/FAIL | {details} |
| AI name colors | A7 | PASS/FAIL | {details} |
| Pacing flow | C1 | PASS/FAIL | {details} |
| Mobile layout | H1 | PASS/FAIL | {details} |
| Zoom behavior | H2 | PASS/FAIL | {details} |

### Visual Anomalies
- {any rendering bugs, wrong colors, broken layout, missing elements}

### Screenshots Taken
- {list of screenshots with descriptions}

### Strategy Notes
- Always passed in auction (MVP)
- Always played first legal card (MVP)
```

## Go-Live Checklist Coverage

This skill is designed to cover these go-live checklist sections:

| Section | Coverage | Key Checks |
|---------|----------|------------|
| **A** (New changes) | Full | Suit colors, hand sorting, bowers, auction log, labels |
| **C1** (Pacing) | Full | Next-button flow, no auto-advance, delays |
| **C2** (Bower display) | Full | RB/LB badges, sort position, trick history |
| **C3** (Score display) | Partial | Score bar labels, team colors, styling |
| **C5** (Auction log) | Partial | Visibility, collapse, suit icons |
| **G** (UI/UX polish) | Full | Tab nav, card display, color consistency |
| **H** (Mobile/accessibility) | Full | Viewport, zoom, aria-labels |

Sections NOT covered (require HTTP-level or multi-session testing):
- **D** (Full lifecycle) -- use `/playtest` for end-to-end functional testing
- **E** (Moon/loner) -- edge cases better tested via HTTP with controlled setups
- **F** (Error recovery) -- requires deliberate error injection
- **I** (Leaderboard) -- multi-player testing beyond single-session scope
- **J** (Onboarding) -- covered but requires incognito/fresh session

## Error Handling

### Browser Errors
- **Page not loading:** Verify URL is correct. Check if server is running.
  Try `browser_navigate` again after 5 seconds.
- **Element not found:** Take a fresh `browser_snapshot` to re-read the DOM.
  The element name may differ from expected.
- **Click not working:** Try `browser_press_key` with Enter as an alternative.
  Or use `browser_evaluate` to trigger the click via JavaScript.

### Stuck State Detection
If the same phase snapshot repeats more than 10 times without progress (no
score changes, no new cards), the game is stuck. Take a **screenshot** for
evidence, log the anomaly, and abort the match.

### Recovery
If the game gets into an unexpected state:
1. Take a screenshot for the anomaly log
2. Try `browser_navigate` back to `{url}/play/{link_uuid}` to refresh state
3. If still stuck, navigate to `{url}` to start fresh with a new match

## Example Invocation

```
/playtest-playwright --url https://bid-euchre.onrender.com --code ABC12345 --nickname VisualBot --matches 2
```

This plays 2 complete matches with visual verification at each key state,
performing responsive checks between matches. Total expected time: 20-40
minutes depending on hand count and depth of visual inspection.

## Recommended Session Structure

For a thorough visual QA session:

1. **Match 1 at desktop viewport** (1280x800)
   - Full game flow with visual checks at every phase
   - Run Procedure V1 (color verification) during first hand
   - Run Procedure V4 (accessibility) once during auction
2. **Responsive check between matches**
   - Run Procedure V3 (responsive testing) on the model select screen
3. **Match 2 at mobile viewport** (375x812)
   - Play a full match at mobile size
   - Verify touch targets, layout wrapping, no horizontal scroll
4. **Post-session**
   - Restore desktop viewport
   - Write observation log
   - File issues for any FAIL results

## NOT in Scope

- Strategic bidding (bid > 0) -- always pass in MVP
- Strategic card selection -- always first legal card
- Performance benchmarking / load testing
- Multi-player testing (requires separate sessions)
- Database / API verification (use HTTP-based testing)
- Auto-filing GitHub issues (manual for now)
