# SP-3-01: HTMX Game UI

**ID:** SP-3-01
**Parent:** Phase 3 — Frontend Product
**Status:** proposed
**Governing plan:** `plans/browser_game/governing_plan.md`
**Created:** 2026-03-14

---

## Goal

Build the browser UI for match setup, bidding, trick play, score display,
and refresh-safe resume. Server-rendered HTML with HTMX partial swaps.
Must work through plain POST/redirect if HTMX is absent.

## Files to Create

| File | Lines (est.) | Purpose |
|------|-------------|---------|
| `web/templates/landing.html` | ~30 | Create game button |
| `web/templates/game.html` | ~80 | Main game layout (extends base) |
| `web/templates/partials/nickname_form.html` | ~20 | Nickname input |
| `web/templates/partials/model_select.html` | ~30 | AI model picker |
| `web/templates/partials/bid_panel.html` | ~50 | Bid amount + contract selector |
| `web/templates/partials/hand.html` | ~40 | Player's cards (clickable) |
| `web/templates/partials/trick.html` | ~40 | Current trick area (4 slots) |
| `web/templates/partials/score.html` | ~30 | Match score + hand info |
| `web/templates/partials/hand_result.html` | ~30 | Made/set banner between hands |
| `web/templates/partials/match_result.html` | ~30 | Win/loss screen |
| `web/static/style.css` | ~200 | Card rendering, layout, colors |
| `web/static/game.js` | ~60 | Decision timer, card click handler |

Total: 12 files, ~640 lines.

## Card Rendering (CSS-Only)

No card images. Unicode suits + rank text, styled with CSS:

```html
<div class="card card--hearts card--legal" data-index="3">
    <span class="card__rank">A</span>
    <span class="card__suit">♥</span>
</div>
```

```css
.card {
    width: 60px; height: 90px;
    border: 2px solid #333; border-radius: 8px;
    background: white; cursor: pointer;
    display: inline-flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-size: 1.2rem; margin: 0 -10px;  /* overlap fan */
    transition: transform 0.15s;
}
.card:hover { transform: translateY(-10px); }
.card--hearts, .card--diamonds { color: #d32f2f; }
.card--spades, .card--clubs { color: #212121; }
.card--legal { border-color: #2e7d32; box-shadow: 0 0 4px #4caf50; }
.card--illegal { opacity: 0.4; cursor: not-allowed; }
```

## Game Table Layout

```
┌─────────────────────────────────────────┐
│           AI Partner (seat 2)           │
│         ░░░░░░░░░░ (face down)          │
├──────────┬─────────────┬────────────────┤
│ AI Left  │  TRICK AREA │  AI Right      │
│ (seat 1) │   ┌──┐┌──┐  │  (seat 3)      │
│ ░░░░░    │   │  ││  │  │  ░░░░░         │
│          │   └──┘└──┘  │                │
├──────────┴─────────────┴────────────────┤
│          Human Hand (seat 0)            │
│    [A♠] [K♠] [Q♠] [J♥] [10♦] ...       │
├─────────────────────────────────────────┤
│  Score: You +12 | AI -3  │ Hand 5/??    │
│  Contract: 6♠ (You bid)  │ Tricks: 4-2  │
└─────────────────────────────────────────┘
```

AI hands shown as face-down card backs (count visible). Only the human's
cards are shown face-up.

## HTMX Wiring

### Bid Submission
```html
<form hx-post="/play/{{uuid}}/bid" hx-target="#game-board" hx-swap="innerHTML">
    <input type="hidden" name="turn_number" value="{{turn_number}}">
    <select name="bid_n">
        <option value="0">Pass</option>
        {% for n in legal_bid_levels %}
        <option value="{{n}}">{{n}}</option>
        {% endfor %}
    </select>
    <select name="contract">
        <option value="S">♠ Spades</option>
        <option value="H">♥ Hearts</option>
        <option value="D">♦ Diamonds</option>
        <option value="C">♣ Clubs</option>
        <option value="HIGH">High (no trump)</option>
        <option value="LOW">Low (no trump)</option>
    </select>
    <button type="submit">Bid</button>
</form>
```

### Card Play
```html
<!-- Each legal card is a form submission -->
<form hx-post="/play/{{uuid}}/play-card" hx-target="#game-board" hx-swap="innerHTML">
    <input type="hidden" name="turn_number" value="{{turn_number}}">
    <input type="hidden" name="card_index" value="{{idx}}">
    <button type="submit" class="card card--{{suit_class}} card--legal">
        <span class="card__rank">{{rank}}</span>
        <span class="card__suit">{{suit_symbol}}</span>
    </button>
</form>
<!-- Illegal cards are plain divs (not clickable) -->
<div class="card card--{{suit_class}} card--illegal">
    <span class="card__rank">{{rank}}</span>
    <span class="card__suit">{{suit_symbol}}</span>
</div>
```

### Game Board Update Target
```html
<!-- game.html -->
<div id="game-board">
    {% include "partials/trick.html" %}
    {% include "partials/hand.html" %}
    {% include "partials/score.html" %}
    {% if phase == "auction" %}
        {% include "partials/bid_panel.html" %}
    {% endif %}
</div>
```

## Phase-Specific Views

1. **Landing** (`/`) — "Start a New Game" button → POST `/new`
2. **Nickname** — text input, sets cookie, POST → model selection
3. **Model selection** — cards showing available AI models with names/descriptions
4. **Auction** — bid panel + current auction state (who bid what)
5. **Trick play** — card table + current trick + human hand
6. **Hand result** — "Made 6!" or "Set! -7 points" banner, auto-transitions to next hand
7. **Match result** — "You Win!" / "You Lose" with final score + "Play Again" button

## Fallback Without HTMX

All POST endpoints must also work as standard form submissions with redirect.
The HTMX `hx-*` attributes enhance the experience but aren't required.
Test: disable JavaScript and verify the game still works (slower, full-page reloads).

## Decision Timer (`game.js`)

Minimal JS that records how long the human takes to act:

```javascript
// Start timer when game board loads with a decision prompt
let decisionStart = Date.now();

// On form submit, inject decision_time_ms
document.querySelectorAll('form[hx-post]').forEach(form => {
    form.addEventListener('htmx:beforeRequest', () => {
        const elapsed = Date.now() - decisionStart;
        const input = document.createElement('input');
        input.type = 'hidden'; input.name = 'decision_time_ms';
        input.value = elapsed;
        form.appendChild(input);
    });
});

// Reset timer on HTMX swap (new decision prompt loaded)
document.body.addEventListener('htmx:afterSwap', () => {
    decisionStart = Date.now();
});
```

## Validation

Manual browser testing checklist:

- [ ] Create game → enter nickname → select AI → first hand appears
- [ ] Bid panel shows only legal bid levels
- [ ] Cards fan out, legal cards highlighted
- [ ] Click legal card → trick updates, AI plays appear
- [ ] Illegal card click does nothing
- [ ] After 10 tricks → hand result banner → next hand
- [ ] After all-pass → redeal notification → new hand
- [ ] Match reaches +52 → win screen
- [ ] Match reaches -52 → loss screen
- [ ] Browser refresh mid-hand → resumes correctly
- [ ] "Play Again" starts new match
- [ ] Works without JavaScript (plain form submissions)

```bash
# Start local server
cd /path/to/repo && PYTHONPATH=src uv run uvicorn web.app:app --reload --port 8000
# Open http://localhost:8000 in browser
```

## Outcome

_To be filled after implementation._
