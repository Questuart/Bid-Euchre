# Execution Brief: Score Change Animation + Trick Count Display

**Date:** 2026-04-02
**Task packet:** `e2c683b2ccbc`
**Origin:** Orchestrator dispatch
**Shaped by:** analyst-d
**Target:** Browser game UX — author lane implementation

---

## Problem Statement

During trick play in the browser game, scoring feedback is static and passive:
the score bar updates silently on HTMX swaps, and the player has no visual
signal that points or tricks were just won. The task requests three
enhancements:

1. **+N animation on trick win** — a brief floating indicator when a trick is
   won showing the updated trick count
2. **Running trick count per team visible during play** — already partially
   exists in two places but could be more prominent
3. **Score bar highlight on change** — a flash/pulse on the score bar when
   the match score changes (hand end)

## Evidence: Current State

### What already exists

| Feature | Location | Status |
|---------|----------|--------|
| Match score display (`score_human` / `score_ai`) | `web/templates/partials/score.html` lines 19-29 | Ships — static text, no animation |
| Trick count center display (`tricks_team0`–`tricks_team1`) | `web/templates/partials/trick.html` lines 102-103 | Ships — center of trick table, static |
| Trick count in score bar (during trick_play) | `web/templates/partials/score.html` line 60 | Ships — inside contract-info, text only |
| Hand result banner with score delta | `web/templates/partials/hand_result.html` lines 73-82 | Ships — animated slide-in for moon/loner only |
| Banner slide-in + glow animations | `web/static/style.css` lines 1898-1944 | Ships — moon/loner banners only |
| Reduced-motion support | `web/static/style.css` lines 2126-2140 | Ships — disables all animations |
| HTMX morph swap for game board | All POST routes → `_render_game_board()` → `morph:innerHTML` | Ships |

### Key architectural pattern

Every user action (bid, play card, next) triggers a POST that returns
`_render_game_board()` HTML. The `#game-board` container is replaced via
`hx-swap="morph:innerHTML"`. The morph algorithm diffs the DOM, meaning
**unchanged elements are not re-created** — only changed attributes/text nodes
are patched. This is important for animations: CSS animations trigger on
element insertion, not on attribute changes.

### HTMX morph implication for animations

Because morph does not destroy/recreate unchanged DOM nodes, a trick count
changing from "3–2" to "4–2" will patch the text content but NOT re-trigger
any CSS `animation` property. To animate on value change, the implementation
must use one of:

1. **JS-driven class toggle** — after `htmx:afterSwap`, detect value change
   and add a temporary animation class, remove it after the animation completes
2. **Data attribute comparison** — store previous value in a `data-*` attribute,
   compare on swap, trigger animation if different
3. **CSS transition on a property** — transitions (not animations) respond to
   property changes, but text content changes don't trigger CSS transitions

**Recommendation: Option 1 (JS class toggle in game.js)** — this follows the
existing pattern where `htmx:afterSwap` on `#game-board` already runs
`clearCardSelection()` and `restoreTrickHistoryState()`. Adding a score-change
detector in the same handler is the natural extension.

## Implementation Seam

### Files to modify

| File | Change |
|------|--------|
| `web/static/style.css` | Add `@keyframes` for trick-count pop and score-bar flash. Add `.trick-count--changed` and `.score-bar--changed` animation classes. Add reduced-motion overrides. |
| `web/static/game.js` | Add score/trick change detection in the `htmx:afterSwap` handler. Store previous values, compare after swap, toggle animation classes. |
| `web/templates/partials/score.html` | Add `data-score-human` and `data-score-ai` attributes on score value spans for JS comparison. |
| `web/templates/partials/trick.html` | Add `data-tricks-team0` and `data-tricks-team1` attributes on the trick count element for JS comparison. |

### Files NOT modified (backend untouched)

- `src/bid_euchre/hosted_play/engine.py` — no new context variables needed
- `src/bid_euchre/hosted_play/state.py` — no state changes
- `web/routes.py` — no route changes
- `web/templates/partials/game_board.html` — no structural changes

### Test files to create/modify

| File | Change |
|------|--------|
| `tests/unit/hosted_play/test_partials.py` | Add tests verifying `data-*` attributes render on score and trick partials |
| (new or existing browser test) | Verify animation class appears after a trick-winning swap (if Playwright E2E is in scope) |

## Micro-Slice Sequence (Single PR)

This is a single-concept, single-PR task. All changes are cosmetic/UX with no
backend or data contract impact.

### Implementation order within the PR

1. **Template data attributes** — Add `data-score-human`, `data-score-ai` to
   `score.html` and `data-tricks-team0`, `data-tricks-team1` to `trick.html`
2. **CSS animations** — Add `@keyframes score-flash` (brief background pulse)
   and `@keyframes trick-pop` (scale bounce). Add animation classes
   `.score-bar--changed`, `.trick-count--changed`. Add reduced-motion overrides.
3. **JS change detection** — In `game.js`, add a function in the
   `htmx:afterSwap` handler that:
   - Reads previous score/trick values from module-scoped variables
   - Compares to current DOM values via `data-*` attributes
   - If changed, adds the animation class and removes it after animation ends
   - Updates the stored previous values
4. **Unit tests** — Add partial render tests for `data-*` attributes

## Acceptance Criteria

1. When a trick is won, the trick count display in the center of the trick table
   briefly scales up (pop animation) to draw attention to the change
2. When the match score changes (at hand end / hand_result transition), the
   score bar briefly flashes/pulses to highlight the update
3. All animations respect `prefers-reduced-motion: reduce` and are suppressed
4. No backend changes — purely CSS + JS + template attribute additions
5. Existing partial render tests continue to pass
6. New tests verify `data-*` attributes are present in rendered HTML
7. `make check` passes

## Validation Commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/unit/hosted_play/test_partials.py -v

# Tier 2 — before PR
make check-quiet
```

## Known Risks and Scope Traps

| Risk | Mitigation |
|------|------------|
| **Morph may not preserve animation class** — if morph replaces the element, the just-added class is lost | Use `requestAnimationFrame` or `setTimeout(0)` to apply class after morph settles. Test empirically. |
| **Score change only visible at hand boundaries** — match score doesn't change mid-trick-play, so the score bar flash is only useful during the hand_result → next_hand transition | Document this limitation. The trick-count animation is the primary mid-play feedback. |
| **Scope creep into +N floating text** — a floating "+1" number that rises and fades is more complex (absolute positioning, z-index, cleanup) | Recommend deferring floating text to a follow-up. The pop animation on the trick count is sufficient MVP feedback. |
| **Double-animation on rapid swaps** — if the player clicks "Next" quickly, animations may stack | Use `animationend` event listener to clean up classes, or clear previous animation before starting new one. |

## Safe Parallelism

This PR is fully independent — it touches only:
- `web/static/style.css` (append-only new sections)
- `web/static/game.js` (new function + handler extension)
- `web/templates/partials/score.html` (attribute additions only)
- `web/templates/partials/trick.html` (attribute additions only)
- `tests/unit/hosted_play/test_partials.py` (new test methods)

No overlap with backend, engine, model, or route changes. Safe to run in
parallel with any non-browser-template PR.

## Relationship to Governing Plan

This work extends **Phase 2 (Product Experience)** of the browser game
expansion, which is already marked COMPLETE. This is a post-Phase-2
enhancement, not a regression fix. It should be tracked as a standalone
UX improvement PR, not as a Phase 2 checkpoint reopening.

## Outcome

_To be filled after implementation._
