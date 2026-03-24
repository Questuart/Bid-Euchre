# SP-3-02: Browser UI Implementation

**ID:** SP-3-02
**Parent:** Phase 3 — Frontend Product
**Status:** proposed
**Governing plan:** `plans/browser_game/governing_plan.md`
**Design reference:** `SP-3-01` → `3_frontend_product/sub/2026-03-14_htmx_game_ui.md`
**Created:** 2026-03-24
**Supersedes:** SP-3-01 (as execution plan; SP-3-01 retained as design reference)

---

## Goal

Build the browser UI for match setup, bidding, trick play, score display,
and refresh-safe resume. Server-rendered HTML with HTMX partial swaps —
no frontend build tooling. Routes already return HTMX partials from
`web/routes.py` (PR #1435).

## Prerequisites

- Phase 2 CLOSED: PRs #1430 (DB models, AI manager), #1435 (routes, templates, tests)
- Routes return HTMX partials for all game actions
- `web/templates/base.html` exists (minimal scaffold from Phase 2)
- `MatchEngine` provides stepwise hand/match progression

## Steps

### Step 1: Game Board Template

**Files to create/update:**

| File | Purpose |
|------|---------|
| `web/templates/game.html` | Main game layout (extends `base.html`) — card table with 4 seats, trick area, score bar |
| `web/templates/landing.html` | Landing page with "Start a New Game" button |
| `web/static/style.css` | Card rendering CSS (Unicode suits, rank text, fan layout, legal/illegal states) |

**Key design decisions (from SP-3-01):**
- CSS-only card rendering — no images. Unicode suits (`♠♥♦♣`) + rank text.
- Card layout: overlapping fan (`margin: 0 -10px`), hover lift effect.
- Legal cards: green border + glow. Illegal cards: dimmed + `cursor: not-allowed`.
- Game table: partner (top), opponents (left/right), human (bottom), trick area (center).
- AI hands shown as face-down card backs with visible count.

**Acceptance criteria:**
- `game.html` renders the 4-seat table layout with trick area and score bar
- `landing.html` has a form that POSTs to `/new`
- `style.css` renders cards with correct colors (red for ♥♦, black for ♠♣)

### Step 2: Template Partials for HTMX Responses

**Files to create/update:**

| File | Purpose |
|------|---------|
| `web/templates/partials/nickname_form.html` | Nickname input form |
| `web/templates/partials/model_select.html` | AI model picker with available models |
| `web/templates/partials/bid_panel.html` | Bid amount + contract type selector |
| `web/templates/partials/hand.html` | Player's cards (legal cards as form buttons, illegal as plain divs) |
| `web/templates/partials/trick.html` | Current trick area (4 card slots) |
| `web/templates/partials/score.html` | Match score + hand info + contract display |
| `web/templates/partials/hand_result.html` | Made/set banner between hands |
| `web/templates/partials/match_result.html` | Win/loss screen with "Play Again" button |

**Key design decisions (from SP-3-01):**
- Each partial is a self-contained HTMX swap target.
- Bid panel: `<select>` for bid level (pass + legal levels) and contract type (♠♥♦♣ + High + Low).
- Card play: each legal card is a `<form>` with `hx-post` to `/play/{uuid}/play-card`.
- All forms include `turn_number` hidden input for idempotency.
- `#game-board` is the primary HTMX swap target (`hx-target="#game-board" hx-swap="innerHTML"`).

**Acceptance criteria:**
- All 8 partials render correctly within `game.html`
- Bid panel shows only legal bid levels from visible state
- Card play forms submit correct `card_index` and `turn_number`

### Step 3: Static Assets (CSS, minimal JS)

**Files to create/update:**

| File | Purpose |
|------|---------|
| `web/static/style.css` | Complete CSS: card styles, table layout, responsive basics, phase-specific views |
| `web/static/game.js` | Decision timer (records `decision_time_ms`), HTMX swap hooks, card click handler |

**Key design decisions (from SP-3-01):**
- Decision timer: `Date.now()` on load, inject `decision_time_ms` hidden input on `htmx:beforeRequest`.
- Timer reset: listen for `htmx:afterSwap` to restart timing on new decision prompt.
- No frontend build tooling — raw CSS and vanilla JS served as static files.

**Acceptance criteria:**
- `game.js` injects `decision_time_ms` on every bid/play form submission
- Timer resets correctly after each HTMX swap
- CSS renders correctly in modern browsers (Chrome, Firefox, Safari)

### Step 4: End-to-End Local Vertical Slice

**Validation command:**
```bash
PYTHONPATH=src uv run uvicorn web.app:app --reload --port 8000
# Open http://localhost:8000 in browser
```

**Flow to validate:**
1. Landing page → "Start a New Game" → POST `/new` → redirect to `/play/{uuid}`
2. Enter nickname → POST `/play/{uuid}/nickname` → model selection partial
3. Select AI model → POST `/play/{uuid}/select-ai` → first hand dealt, game board appears
4. Bid phase → select bid level + contract → POST `/play/{uuid}/bid` → board updates
5. Play phase → click legal card → POST `/play/{uuid}/play-card` → trick updates, AI plays
6. After 10 tricks → hand result banner → next hand auto-starts
7. Play to +52 or -52 → match result screen
8. "Play Again" → POST `/play/{uuid}/new-match` → new model selection

**Acceptance criteria:**
- Complete match playable from landing to win/loss screen
- AI turns auto-advance without user interaction
- All-pass hands trigger redeal
- Decision logging verified in database (decisions table populated)

### Step 5: Refresh/Resume Proof

**Tests to perform:**
1. Refresh browser mid-auction → resumes at correct bid state
2. Refresh browser mid-trick → resumes with correct cards played
3. Refresh between hands → shows correct hand result or next hand
4. Double-click bid/play button → idempotent (same response, no state corruption)
5. Navigate away and return via URL → full state restored from DB

**Acceptance criteria:**
- `GET /play/{uuid}` always renders correct current state from persisted `match_state_json`
- No double-counting of actions on duplicate POST
- Browser back/forward buttons don't corrupt state

## Validation Commands

```bash
# Tier 1 (during dev): run existing route tests to verify no regression
uv run python -m pytest tests/unit/hosted_play/test_routes.py -v

# Tier 2 (before PR): full validation
make check-quiet

# Manual: local server test
PYTHONPATH=src uv run uvicorn web.app:app --reload --port 8000
```

## Outcome

_To be filled after implementation._
