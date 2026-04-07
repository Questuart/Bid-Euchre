# Residual Card Jitter Investigation After UX-1/2/3

**Date:** 2026-04-07
**Lane:** analyst-b
**Branch:** `analyst/jitter-residual-investigation`
**Task packet:** `911d444ca08a`
**Delivery mode:** PR (committed findings artifact)
**Status:** Investigation complete. No code/CSS/template changes in this PR.

Refs #2538.

---

## TL;DR

Three UX PRs shipped to fix card jitter (#2558 UX-1, #2566 UX-2, #2567 UX-3).
Operator proving on latest main (`eb12271e`) confirms **jitter persists during
AI card play and trick boundary transitions**.

The UX PRs correctly fixed CSS animation conflicts (Bug A), the
`paused_after_trick` gate (Bug C), and the empty-slot fade (part of Bug D).
The **remaining jitter is not an animation problem** — it is a
**layout reflow problem** caused by the compass grid center column changing
height when content appears/disappears during idiomorph swaps.

Two root causes account for ~99% of the visible jitter:

| # | Source | Shift | Severity |
|---|--------|-------|----------|
| **L1** | Next-controls div appears/disappears during auto-advance | **~87px** | **Critical** |
| **L2** | Trick-winner vs trick-current-winner paragraph size mismatch | **~12px** | Moderate |

Both are **CSS-only fixes** (no engine or route changes). Total estimated
change: ~15 lines of CSS.

---

## 1. Evidence: Mutation Observer + Layout Measurements

### Test Setup

- Server: `http://localhost:8000` on main `eb12271e` with `--reload`
- Playwright MutationObserver on `#game-board` capturing class mutations,
  child additions/removals, and `getBoundingClientRect()` on every change
- Game: Invite code `QUE-TEST`, active match, trick play phase

### Measurement A: Height tracking across trick boundary (trick 8 → 9)

Installed a MutationObserver that records `#trick-area` height and
`.compass-bottom` top position on every DOM mutation:

| Time | Event | trick-area height | compass-bottom top | Delta |
|------|-------|------------------:|-------------------:|------:|
| baseline | Trick 8 complete, "Next" button visible | 384.8 px | 687.6 px | — |
| +12s (click Next) | Trick boundary morph: leader card appears | 373.2 px | 676.0 px | −11.6 px |
| +12.02s (settle) | Next-controls removed (human's turn) | 373.2 px | 588.8 px | **−87.2 px** |

**The human hand jumps UP by 98.8 px total** (11.6 from trick-area + 87.2
from next-controls removal) in a single trick-boundary transition. This
is the visible jitter.

### Measurement B: Full mutation batch during AI card play

Human plays K♥ → three AI plays follow via auto-advance. Mutation log
shows 61 mutations in 9 batches across ~1.5 seconds:

| Batch | Time (ms) | Count | Key mutations |
|-------|-----------|------:|---------------|
| 1 | 153289 | 3 | Card selection + htmx-request |
| 2 | 153306 | 15 | **Human card appears** (card-slot--empty → card--played, NO animation), hand cards illegal→removed, next-controls added |
| 3 | 153328 | 5 | **Settling noise**: compass-layout, score-bar, action-rail get same class re-set |
| 4 | 153831 | 1 | Auto-advance htmx-request |
| 5 | 153839 | 11 | **AI card 1 appears** (card-slot--empty → card--played card--ai-delayed ✓), card-back removed from AI hand |
| 6 | 153860 | 5 | Settling noise (same 3 noop mutations) |
| 7 | 154712 | 1 | Auto-advance htmx-request |
| 8 | 154720 | 16 | **AI card 2 = trick closes**: card appears + card--ai-delayed ✓, previous card loses card--winning, trick-slot gains winner, trick-current-winner → trick-winner, trick-history row added, next-controls removed |
| 9 | 154741 | 4 | Settling noise |

Key observations:
- **AI cards DO get reveal animations** (card--ai-delayed present) — UX-1/2 working
- **Trick-closing card DOES get ai-delayed** — UX-2 working
- **Empty slots DO get slot-reset-fade** — UX-3 working
- **Human card still pops without animation** — known, low-priority (original source #1)
- **3 NOOP class mutations per swap** on compass-layout, score-bar, action-rail — idiomorph settling noise

### Measurement C: Layout area dimensions (stable state)

After trick 9 settles with human's turn to play:

| Area | Top | Height | Bottom |
|------|----:|-------:|-------:|
| trick-area | 178.0 | 373.2 | 551.2 |
| trick-table | 207.2 | 324.0 | 531.2 |
| trick-current-winner | 535.2 | 16.0 | 551.2 |
| trick-history | 551.2 | 32.0 | 583.2 |
| compass-center | 142.8 | 440.4 | 583.2 |
| compass-bottom | 588.8 | 208.2 | 797.0 |
| score-bar | 813.0 | 45.0 | 858.0 |

The compass grid uses `grid-template-rows: auto 1fr auto`. The center row
is `1fr`, so its height is driven by content. When next-controls (~87px)
are added, the center content grows, pushing compass-bottom down. When
they're removed, it collapses back up.

---

## 2. Root Cause Analysis

### L1 — Next-Controls Layout Collapse (Critical, ~87px)

**What happens:**

During auto-advance sequences, `show_next` toggles between `true` and
`false` as the server processes each AI play. The next-controls div
(containing a `<button>` and instruction text) occupies ~87px of vertical
space inside `compass-center`. When auto-advance completes and it becomes
the human's turn, `show_next` goes `false` and the next-controls div is
**removed entirely from the DOM** by idiomorph.

Because `compass-center` has no `min-height` and the grid row is `1fr`,
the center area collapses by ~87px, causing the human hand
(`.compass-bottom`) to jump upward by the same amount.

**File references:**
- `web/templates/partials/game_board.html` line 126-128: conditional include
  of `web/templates/partials/next_controls.html` inside compass-center
- `web/static/style.css` line 175: `.compass-center { grid-area: center; min-width: 0; }`
  — NO min-height set
- `web/static/style.css` line 167: `grid-template-rows: auto 1fr auto` — center
  row is intrinsically sized

**Why UX-1/2/3 didn't fix this:**
This is a layout/grid issue, not a CSS animation issue. The UX PRs fixed
animation cascade conflicts and missing reveal effects. They did not touch
the grid sizing or content reservation.

### L2 — Trick-Winner Paragraph Size Mismatch (Moderate, ~12px)

**What happens:**

The trick area shows different text depending on state:
- **Active trick:** `<p class="trick-current-winner">` — font-size: 0.85rem,
  no padding, no margin → ~16px tall
- **Completed trick:** `<p class="trick-winner">` — font-size: 1rem,
  font-weight: 600, margin: 0.35rem 0 0, padding: 0.25rem 0.75rem → ~27px tall

When a trick completes, idiomorph morphs the paragraph in-place (class
change from `trick-current-winner` to `trick-winner`). The 11px height
difference causes the trick-area to grow, pushing everything below down.

**File references:**
- `web/static/style.css` line 367-371: `.trick-current-winner` — 0.85rem, no padding
- `web/static/style.css` line 948-957: `.trick-winner` — 1rem, padding 0.25rem 0.75rem
- `web/templates/partials/trick.html` line 127-152: conditional winner text rendering

### L3 — Idiomorph Settling Noise (Minor, no visual impact)

Every morph:innerHTML swap triggers 3 spurious class-attribute mutations
on elements whose classes did NOT change:
- `.compass-layout` (same class → same class)
- `#score-bar` (same class → same class)
- `#action-rail` (same class → same class)

These are NOOP mutations from idiomorph touching every matched element,
even if nothing changed. Each triggers a style recomputation cycle.
While not visually perceptible, they add ~3 extra style recalcs per swap
on the critical rendering path.

**This is a known idiomorph behavior, not a bug in our code.** No fix
recommended unless performance profiling shows measurable frame drops.

### L4 — Hand Card Tag Type Change (Minor, <1px)

When the turn changes between "human can play" and "human can't play,"
hand cards morph between `<button class="card--legal">` and
`<div class="card--illegal">`. Idiomorph cannot morph across different
tag names — it removes the old node and adds the new one. This causes a
brief DOM teardown/rebuild, but because the replacement elements have
identical dimensions, the visual impact is negligible (<1px).

---

## 3. Mapping to Original 8 Sources

The original investigation (`plans/sessions/2026-04-06_card_jitter_investigation.md`)
identified 8 jitter sources. Here is their current status:

| # | Source | Status | Fixed by |
|---|--------|--------|----------|
| 1 | Human card pops without animation | **OPEN** (low priority) | — |
| 2 | Hand cards reflow when played card removed | **OPEN** (low priority) | — |
| 3 | Trick-closing AI card pops without reveal | **FIXED** | PR #2566 (UX-2) |
| 4 | Winning-card-pulse snaps off at trick end | **MITIGATED** | PR #2558 (UX-1) transition baseline |
| 5 | Previous-trick cards vanish atomically | **FIXED** | PR #2567 (UX-3) slot-reset-fade |
| 6 | Winning-card-pulse absent on new trick lead | **FIXED** | PR #2558 (UX-1) compound rule |
| 7 | Winning-card-pulse "snaps on" 850ms later | **FIXED** | PR #2558 (UX-1) composed animations |
| 8 | Winner-card-glow stops mid-iteration | **MITIGATED** | PR #2558 (UX-1) transition baseline |

**NEW sources discovered in this investigation:**

| # | Source | Shift | Priority |
|---|--------|-------|----------|
| L1 | Next-controls layout collapse | ~87px | **P0** |
| L2 | Trick-winner paragraph size mismatch | ~12px | **P1** |
| L3 | Idiomorph settling noise | 0px | P3 (no fix needed) |
| L4 | Hand card tag type change | <1px | P3 (no fix needed) |

---

## 4. Fix Recommendation

> **Operator directive (2026-04-07T02:30Z):** Remove the visible "Reveal
> the next card" / Next button from the `paused_after_play` state during
> trick play. Keep the 2-second pause between AI card plays so the player
> can see each card appear, but use the existing auto-advance timer — no
> user interaction needed. The `paused_after_trick` "Continue to next
> trick" button at trick end stays. No inserted visible content during the
> pause = no layout shift = no jitter.

### PR UX-4: Hide next-controls during auto-advance (~30 LoC)

**Goal:** Eliminate L1 (87px layout shift) by preventing the next-controls
div from taking layout space during auto-advance. Also fix L2 (12px
trick-winner height) for completeness.

#### Fix 1 — Hide next-controls from first paint during auto-advance

**Current behavior:** The `next-controls` div is rendered visible during
`paused_after_play`. JavaScript's `scheduleAutoAdvance()` fires on
`htmx:afterSettle` and adds `js-auto-advance-active` class which hides the
controls. But between the morph swap and JS execution (~20ms), the
controls are visible and take ~87px of layout space → layout shift.

**Fix:** Apply `next-controls--auto-advance` CSS to hide controls
**immediately** on first paint, before JS runs. The form stays in the DOM
(hidden) so `scheduleAutoAdvance()` can still find and submit it.

```css
/* web/static/style.css — replace the js-auto-advance-active rule */

/* Auto-advancing: hide from first paint — no layout shift.
   The form stays in DOM for JS auto-submit.  If JS fails,
   revealManualNextFallback() adds .next-controls--fallback-visible
   to override this and restore the manual button. */
.next-controls--auto-advance {
    position: absolute;
    height: 0;
    overflow: hidden;
    pointer-events: none;
    opacity: 0;
}

/* Fallback: restore manual button if JS auto-advance fails (#2487). */
.next-controls--auto-advance.next-controls--fallback-visible {
    position: static;
    height: auto;
    overflow: visible;
    pointer-events: auto;
    opacity: 1;
}
```

**JS change:** Update `revealManualNextFallback()` in `web/static/game.js`
to add `next-controls--fallback-visible` instead of removing
`js-auto-advance-active`:

```javascript
// web/static/game.js — update fallback function
function revealManualNextFallback(nextControls) {
    nextControls.classList.add('next-controls--fallback-visible');
}
```

**Auto-advance delay change:** The operator wants 2-second pauses between
AI cards. Update `web/routes.py` line 612:

```python
# Current:  ctx["auto_advance_delay_ms"] = 850 if is_ai else 500
# Changed:  ctx["auto_advance_delay_ms"] = 2000 if is_ai else 500
```

#### Fix 2 — Equalize trick-winner / trick-current-winner layout

Make both paragraph classes occupy the same vertical space:

```css
.trick-current-winner,
.trick-winner {
    font-size: 0.9rem;
    font-weight: 500;
    min-height: 1.8rem;
    margin: 0.25rem 0 0;
    padding: 0.2rem 0.5rem;
}

.trick-winner {
    font-weight: 600;
    animation: trick-winner-flash 1.5s ease-out;
}
```

### File scope

| File | Change | LoC |
|------|--------|----:|
| `web/static/style.css` | Fix 1 CSS (hide auto-advance), Fix 2 (paragraph height) | ~20 |
| `web/static/game.js` | Update `revealManualNextFallback()` to use new class | ~5 |
| `web/routes.py` | Change `auto_advance_delay_ms` from 850 to 2000 | ~1 |

No engine changes. No template changes. No new DOM elements.

### Validation

```bash
# Tier 1 — targeted
uv run python -m pytest tests/unit/web/ tests/integration/hosted_play/ -v
make lint

# Tier 2 — full validation
make check-gated

# Browser smoke
make browser-smoke
```

**Manual Playwright validation:**
1. Install MutationObserver + height tracker (as used in this investigation)
2. Play through a full trick sequence: human plays → 3 AI plays → trick completes → Next
3. Assert the `.compass-bottom` element's top offset does not shift by more than 4px between any two
   consecutive mutation batches
4. Assert `#trick-area` height does not change by more than 4px between
   `trick-current-winner` and `trick-winner` states
5. Verify AI cards still appear with reveal animation after ~2s pause
6. Verify the trick-end "Continue to next trick" Next button still appears and is clickable

---

## 5. Risk Register

| # | Risk | Mitigation |
|---|------|------------|
| R1 | Hiding next-controls via CSS before JS runs means the button is never visible during auto-advance. If JS fails to load, the player is stuck (no button, no auto-advance) | The `revealManualNextFallback()` function already exists for this case (#2487). Update it to add `.next-controls--fallback-visible` class which overrides the CSS hiding. Also, the `<noscript>` fallback (if any) should show the button. |
| R2 | Increasing auto-advance delay from 850ms to 2000ms makes the game feel slower | This is the operator's explicit requirement — 2s pause so players can see each card. If negative feedback, the value is a single-line change in `web/routes.py`. |
| R3 | The `position: absolute` on `.next-controls--auto-advance` removes it from layout flow. If any other CSS depends on the controls being in flow, it could break | The controls are inside `.compass-center` which is a block layout. `position: absolute` on a child of a non-positioned parent doesn't affect siblings. Verify with browser devtools. |
| R4 | Equalizing trick-winner/trick-current-winner font sizes may make the winner announcement less visually distinct | Compensate with font-weight difference (500 vs 600) and the existing `trick-winner-flash` animation. The layout stability is more important than the font-size distinction. |
| R5 | Idiomorph settling noise (L3) is left unfixed | This is an upstream idiomorph behavior. The performance impact is negligible. No fix needed. |
| R6 | The `paused_after_trick` Next button ("Continue to next trick") is NOT hidden — it still appears and causes its own layout shift | The trick-end button appears once per trick (not rapid-fire like mid-trick pauses) and requires user interaction. The operator explicitly said to keep it. The shift is acceptable because it's a natural pause point, not a mid-trick stutter. |

---

## 6. HTMX Swap Target Analysis (Orchestrator Escalation Follow-Up)

The orchestrator's escalation hypothesized that the HTMX swap target is
"too broad" — replacing the whole trick area when only one slot changed.

### Finding: Swap target is broad BUT idiomorph handles it correctly

Every game action (`play-card`, `next`, `bid`, etc.) uses:
```html
hx-target="#game-board"
hx-swap="morph:innerHTML"
```

This targets the **entire game board** (~200 DOM nodes), not just the trick
area. However, idiomorph's diff algorithm correctly identifies and
preserves unchanged nodes:

- Trick slots that didn't change → kept in place (no mutation)
- AI hand card-backs that didn't change → kept in place
- Score bar → kept in place (only spurious class re-set)

The swap target breadth is **not the cause of jitter**. Narrowing the swap
target (e.g., to `#trick-area`) would require:
- Multiple swap targets for different content regions (trick area, hand,
  AI hands, score bar, next-controls)
- Server-side partial rendering for each target separately
- HTMX Out-of-Band swaps (`hx-swap-oob`) for the secondary targets

This is a significant architectural change with high risk of coordination
bugs. **Not recommended** given that idiomorph is already doing the right
thing at the DOM level. The jitter is from layout reflow, not DOM churn.

---

## 7. Dispatch Packet for Implementation

```yaml
title: "fix(web): hide next-controls during auto-advance to prevent layout jitter"
branch: "fix/auto-advance-layout-shift"
scope_declared:
  - web/static/style.css
  - web/static/game.js
  - web/routes.py
validation: "make check-gated && make browser-smoke"
refs: "#2538"
estimated_loc: 30
risk: low
domain: browser-game
priority: high
description: |
  Eliminate ~99px of visible layout jitter during AI card play by hiding
  the next-controls div from first paint during auto-advance sequences.

  L1 (87px): Apply CSS hiding to .next-controls--auto-advance immediately
  (not waiting for JS to add js-auto-advance-active). Form stays in DOM
  for auto-submit. Add .next-controls--fallback-visible for JS failure
  recovery.

  L2 (12px): Equalize .trick-current-winner and .trick-winner paragraph
  layout properties (font-size, min-height, margin, padding).

  Also increase auto_advance_delay_ms from 850 to 2000 per operator
  directive (2s pause between AI cards for readability).

  See plans/sessions/2026-04-07_jitter_residual_investigation.md for
  full evidence, mutation logs, and layout measurements.
```

---

## 8. External References

- [HTMX Idiomorph Extension](https://htmx.org/extensions/idiomorph/) — morph:innerHTML behavior
- [Prevent Layout Shifts with CSS Grid Stacks](https://www.hsablonniere.com/prevent-layout-shifts-with-css-grid-stacks--qcj5jo/) — CSS grid technique for height-stable content switching
- [Content Jumping and How to Avoid It](https://css-tricks.com/content-jumping-avoid/) — min-height reservation pattern
- [Preventing Layout Shifts with Modern CSS](https://blog.openreplay.com/preventing-layout-shift-modern-css/) — comprehensive layout shift prevention
- [idiomorph source (GitHub)](https://github.com/bigskysoftware/idiomorph) — DOM-merging algorithm reference

---

## Outcome

_To be filled after implementation PR merges._
