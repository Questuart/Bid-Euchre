# SP-2-02: Mobile, Accessibility, and Help Pass

**ID:** SP-2-02
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 2 -- Product Experience
**Status:** proposed
**Owner:** --

---

## Inputs

- `web/static/style.css`
- `web/static/game.js`
- `web/templates/partials/`
- `web/templates/game.html`
- `plans/browser_game_expansion/proving_matrix.md`

## Assumptions

- Desktop gameplay structure from `SP-2-01` exists first.
- Mobile Safari is a required proving target.
- A small help drawer and reduced-motion controls are in scope; large tutorial
  systems are not.

## Dependencies

- `SP-2-01` complete enough that the stable browser states exist

## Plan

### Step 1: Make card interaction touch-safe

- Add tap-select/confirm or an equivalent interaction that prevents accidental
  plays on touch devices.
- Ensure legal-card affordances do not rely on hover alone.

### Step 2: Improve mobile layout and accessibility

- Add narrow-screen layout refinements and larger touch targets.
- Add reduced-motion support.
- Ensure the page remains lightweight and server-rendered.

### Step 3: Add compact help/settings surfaces

- Add a small rules/help drawer for bowers, High/Low, scoring, moon/loner.
- Add player-facing pace controls where appropriate.
- Fix decision-time persistence if it is still only client-injected.

## Files Changed

- `web/static/style.css`
- `web/static/game.js`
- `web/templates/game.html`
- `web/templates/partials/hand.html`
- `web/templates/partials/bid_panel.html`
- `web/templates/partials/score.html`
- `web/routes.py`
- `tests/unit/hosted_play/test_partials.py`
- `tests/unit/hosted_play/test_routes.py`
- `tests/e2e/hosted_play/` -- mobile viewport coverage

## Validation

### Pass/Fail Criteria

- [ ] **Route/template tests:** `uv run python -m pytest tests/unit/hosted_play/test_partials.py tests/unit/hosted_play/test_routes.py -q`
  - Expected: settings/help/touch-related rendering paths pass.
- [ ] **Mobile viewport proof:** browser E2E in a narrow mobile viewport
  - Expected: the player can complete at least one bid and one card play without layout breakage.
- [ ] **Reduced-motion proof:** style/game settings check
  - Expected: motion-reduced path renders without relying on hidden state.
- [ ] **Telemetry proof:** bid/play submissions persist `decision_time_ms`
  - Expected: DB rows include decision-time values after human actions.

## Planned Outputs

- Mobile-safe interaction model
- Reduced-motion and help surface
- Decision-time persistence fix if still missing

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: ready after gameplay pacing/state legibility lands.
- Next action: execute with mobile viewport tests available.
- Blockers: `SP-2-01` not complete.
- Files with uncommitted changes: --
