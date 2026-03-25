# SP-2-01: Gameplay Readability and Hand Pacing

**ID:** SP-2-01
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 2 -- Product Experience
**Status:** proposed
**Owner:** --

---

## Inputs

- `web/routes.py`
- `web/static/style.css`
- `web/static/game.js`
- `web/templates/game.html`
- `web/templates/partials/`
- `src/bid_euchre/hosted_play/engine.py`
- current browser-ui tests and partial tests

## Assumptions

- Phase 1 moon/loner state semantics are already correct.
- The player's main UX pain points are readability and pacing, not missing
  foundation.
- A hand-end pause is preferable to auto-dealing the next hand immediately.

## Dependencies

- Phase 1 complete
- `SP-1-02` complete

## Plan

### Step 1: Surface moon/loner actions and state in the browser

- Render legal moon/loner actions clearly in the bid UI.
- Replace the most form-like bid controls with a compact, game-native bid box
  or chip/button treatment where practical.
- Show bid type and any special hand mode in score/header state.
- Auto-sort the human hand for display by printed suit, then by display rank
  `J > A > K > Q > T`, while keeping suit buckets strictly segregated.
- Treat hand sorting as presentation-only: do not change effective-suit logic or
  left-bower gameplay semantics.

### Step 2: Add state legibility improvements

- Add persistent last-trick display.
- Add action rail from AI/human events.
- Add turn/dealer/declarer markers and winner highlight.

### Step 3: Add deliberate hand pacing

- Stop auto-dealing immediately after scoring.
- Show a hand-result pause with an explicit "Next deal" action.
- Keep redeal behavior readable as well.
- Add only lightweight deal/reveal motion if it materially improves readability
  without creating a brittle animation system.

## Files Changed

- `web/routes.py`
- `web/static/style.css`
- `web/static/game.js`
- `web/templates/game.html`
- `web/templates/partials/bid_panel.html`
- `web/templates/partials/hand.html`
- `web/templates/partials/trick.html`
- `web/templates/partials/score.html`
- `web/templates/partials/hand_result.html`
- `web/templates/partials/game_board.html`
- `web/routes.py` or a dedicated presentation helper for stable hand ordering
- `tests/unit/hosted_play/test_partials.py`
- `tests/unit/hosted_play/test_routes.py`
- `tests/e2e/hosted_play/` -- new flow coverage once Phase 4 harness exists

## Validation

### Pass/Fail Criteria

- [ ] **Route/template tests:** `uv run python -m pytest tests/unit/hosted_play/test_partials.py tests/unit/hosted_play/test_routes.py -q`
  - Expected: new game-board states render correctly.
- [ ] **Hand-order proof:** add a deterministic rendering/helper test for the
  human hand sort
  - Expected: printed suits stay grouped and per-suit order is `J, A, K, Q, T`.
- [ ] **Integration-level proof:** local browser/E2E run through a hand end
  - Expected: cards remain visible, action rail updates, and next hand does not start until the player continues.
- [ ] **Moon/loner UI proof:** execute one moon and one loner browser flow
  - Expected: special bid type is visible in the UI and hand progression remains readable.

## Planned Outputs

- Readable trick and action state
- Explicit next-deal flow
- Browser UI aligned to moon/loner semantics

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: waiting on Phase 1.
- Next action: implement the hand-end pause and state-legibility changes before mobile polish.
- Blockers: Phase 1 incomplete.
- Files with uncommitted changes: --
