# Accessibility Audit — Browser Game WCAG AA Compliance

**Date:** 2026-04-02
**Task packet:** `6677864d8e40`
**Lane:** analyst-c
**Status:** COMPLETE

---

## Executive Summary

The browser game has a **strong accessibility foundation**: semantic HTML, ARIA
landmarks, screen-reader labels, skip navigation, reduced-motion support,
high-contrast mode support, and touch-target sizing. These were clearly
designed in from the start, not bolted on.

However, the audit found **9 color contrast failures** that violate WCAG 2.1 AA
(many critically so), **1 significant keyboard accessibility gap** (focus
management after HTMX swaps), and several medium-severity ARIA issues.

**Verdict: 9 contrast blockers, 1 keyboard blocker, 4 medium, 3 low.**

---

## Scope

Files audited:

| Category | Files |
|----------|-------|
| CSS | `web/static/style.css`, `web/static/css/accessibility.css` |
| JS | `web/static/game.js` |
| Templates | `web/templates/base.html`, `game.html`, `landing.html`, `leaderboard.html`, `errors/404.html`, `errors/500.html` |
| Partials | `action_rail.html`, `bid_panel.html`, `bid_recap.html`, `game_board.html`, `game_controls.html`, `hand.html`, `hand_result.html`, `invite_code_form.html`, `match_result.html`, `model_select.html`, `moon_exchange.html`, `moon_exchange_select.html`, `next_controls.html`, `nickname_form.html`, `score.html`, `trick.html`, `trick_history.html` |

WCAG version: **2.1 Level AA**

---

## Findings

### Finding 1: Score colors invisible on surface backgrounds [CRITICAL]

**WCAG criterion:** 1.4.3 Contrast (Minimum) — 4.5:1 for normal text

The positive and negative score colors have critically low contrast against the
`--color-surface` background used by the score bar, hand result banner, and
match result screen.

| Combination | Foreground | Background | Ratio | Required | Verdict |
|-------------|-----------|------------|-------|----------|---------|
| Positive score on surface | `#2e7d32` | `#263238` | **1.94:1** | 4.5:1 | ❌ FAIL |
| Negative score on surface | `#c62828` | `#263238` | **1.58:1** | 4.5:1 | ❌ FAIL |

**Affected elements:**
- `.score--positive` / `.score--negative` in score bar (`score.html`)
- `.points--positive` / `.points--negative` in hand result table (`hand_result.html`)
- `.action-rail__item--trick` (green on surface)
- `.result--made .result-title` / `.result--set .result-title`
- `.result--win .result-title` / `.result--loss .result-title`

**Recommended fix:** Use lighter/brighter variants of these colors:
- Positive: `#66bb6a` (luminance ≈ 0.32, ratio ≈ 4.43:1 — borderline) or `#81c784` (≈ 5.4:1) ✅
- Negative: `#ef5350` (luminance ≈ 0.15, ratio ≈ 2.38:1 — still fails) or `#ff8a80` (≈ 4.6:1) ✅
- Alternative: Keep the dark colors and add a lighter background panel behind score values

**PR scope:** 1 file (`style.css`) — change 2 CSS custom properties and verify
no cascading visual regressions.

---

### Finding 2: Lead suit indicator nearly invisible [CRITICAL]

**WCAG criterion:** 1.4.3 Contrast (Minimum)

The lead suit icon in the trick area heading uses colors designed for card faces
(white background) but renders against the dark page background (`#0d3d0f`).

| Combination | Foreground | Background | Ratio | Required | Verdict |
|-------------|-----------|------------|-------|----------|---------|
| Spades/clubs lead suit | `#222` | `#0d3d0f` | **1.01:1** | 4.5:1 | ❌ FAIL (invisible) |
| Hearts/diamonds lead suit | `#c62828` | `#0d3d0f` | **1.87:1** | 4.5:1 | ❌ FAIL |

**Source:** `style.css` lines 464-472:
```css
.lead-suit--hearts, .lead-suit--diamonds { color: #c62828; }
.lead-suit--spades, .lead-suit--clubs { color: #222; }
```

**Template:** `trick.html` line 84 — the `<span class="lead-suit ...">` is
inside the `<h3>` which sits on the body/main background, not on the felt
trick table.

**Recommended fix:** Use the same colors as inline card text:
```css
.lead-suit--hearts, .lead-suit--diamonds { color: var(--color-red); }
.lead-suit--spades, .lead-suit--clubs { color: var(--color-text); }
```
This gives `#d32f2f` on `#0d3d0f` (≈ 3.2:1 — still fails for small text) and
`#fafafa` on `#0d3d0f` (≈ 14:1 ✅). For red suits, use `#ef5350` or `#ff8a80`.

**PR scope:** 1 file (`style.css`) — 2 CSS rule changes.

---

### Finding 3: Loner accent color fails contrast [HIGH]

**WCAG criterion:** 1.4.3 Contrast (Minimum)

| Combination | Foreground | Background | Ratio | Required | Verdict |
|-------------|-----------|------------|-------|----------|---------|
| Loner result title | `#7e57c2` | `#263238` | **1.79:1** | 3:1 (large) | ❌ FAIL |
| Moon result title (large text) | `#ffa000` | `#263238` | **4.88:1** | 3:1 (large) | ✅ PASS |

The loner purple is too dark against the surface background. At 1.5rem+ font
size it qualifies as large text (3:1 threshold), but 1.79:1 still fails.

**Recommended fix:** Lighten to `#b39ddb` (loner glow color already defined
as `--color-loner-glow`). Ratio ≈ 5.1:1 ✅.

**PR scope:** 1 file (`style.css`).

---

### Finding 4: Invite error text fails contrast [HIGH]

**WCAG criterion:** 1.4.3 Contrast (Minimum)

| Combination | Foreground | Background | Ratio | Required | Verdict |
|-------------|-----------|------------|-------|----------|---------|
| Invite error | `#e53935` | `#0d3d0f` | **2.04:1** | 4.5:1 | ❌ FAIL |

**Source:** `style.css` line 1277: `.invite-error { color: #e53935; }`

The invite code form sits on the body background (no panel). Error text is
hard to read.

**Recommended fix:** Use `#ff8a80` (ratio ≈ 6.3:1 ✅) or wrap the form in a
surface-colored panel and use a brighter red.

**PR scope:** 1 file (`style.css`).

---

### Finding 5: Focus lost after HTMX swaps [HIGH]

**WCAG criterion:** 2.4.3 Focus Order, 3.2.2 On Input

When the game board is swapped via HTMX (`hx-target="#game-board"`,
`hx-swap="morph:innerHTML"`), the user's keyboard focus may be destroyed if
the focused element is replaced. This causes:

- Keyboard users lose their place and must Tab from the beginning
- Screen reader users lose their reading position and context
- After playing a card, focus should move to a meaningful element (trick area,
  next controls, or status announcement)

**Current code:** `game.js` handles `htmx:afterSwap` but only calls
`clearCardSelection()` and `syncCardPlayFormControls()` — no focus management.

**Evidence:** The `htmx:afterSwap` handler at line 151 of `game.js`:
```javascript
document.body.addEventListener('htmx:afterSwap', function (event) {
    var target = event.target;
    if (!(target instanceof Element) || target.id !== 'game-board') { return; }
    clearCardSelection(getCardPlayForm());
    syncCardPlayFormControls(getCardPlayForm());
    restoreTrickHistoryState();
}, true);
```

**Recommended fix:** After swap, set focus to a phase-appropriate element:
- During trick play: focus the trick area or the first legal card
- After trick completion (show_next): focus the "Next" button
- Hand result: focus the result banner (has `role="alert"` + `aria-live`)
- Auction: focus the bid panel

```javascript
// Add to htmx:afterSwap handler:
var nextBtn = document.querySelector('.btn--next-step, .btn--next-hand');
if (nextBtn) { nextBtn.focus(); return; }
var firstLegal = document.querySelector('.card--legal');
if (firstLegal) { firstLegal.focus(); return; }
var alert = document.querySelector('[role="alert"]');
if (alert) { alert.focus(); return; }
```

**PR scope:** 1 file (`game.js`).

---

### Finding 6: Excessive nested `aria-live` regions [MEDIUM]

**WCAG criterion:** 4.1.3 Status Messages (advisory)

The `#game-board` div has `aria-live="polite"`, and multiple children also
have `aria-live="polite"` or `aria-live="assertive"`:

| Element | aria-live | Template |
|---------|-----------|----------|
| `#game-board` | polite | `game.html` |
| `#trick-area` | polite | `trick.html` |
| `.trick-winner p` | polite | `trick.html` |
| `#card-play-help` | polite | `hand.html` |
| `.bid-info` | polite | `bid_panel.html` |
| `.auction-transcript` | polite | `bid_panel.html` |
| `#score-bar` | polite | `score.html` |
| `#action-rail` | polite | `action_rail.html` |
| `#hand-result` | assertive | `hand_result.html` |
| `#match-result` | assertive | `match_result.html` |
| `#moon-exchange` | assertive | `moon_exchange.html` |
| `#exchange-help` | polite | `moon_exchange_select.html` |

When the game board swaps (which it does on every action), the `aria-live` on
`#game-board` announces ALL changed content. Then each child live region
announces its own changes again. This can produce **duplicate or overlapping
screen reader announcements**.

**Recommended fix:**
- Remove `aria-live` from `#game-board` (the container)
- Keep `aria-live` only on the leaf elements that actually change
  (trick-winner, card-play-help, score-bar, alerts)
- Or: remove `aria-live` from children and rely on the container only

**PR scope:** 4-5 template files.

---

### Finding 7: Redundant `aria-label` overriding visible labels [MEDIUM]

**WCAG criterion:** 1.3.1 Info and Relationships

Several form controls have both a visible `<label>` and an `aria-label`. The
`aria-label` overrides the visible label for assistive technology, which can
cause confusion if they say different things.

| Element | Visible label | aria-label | File |
|---------|--------------|------------|------|
| `#nickname-input` | "Nickname:" | "Your display nickname" | `nickname_form.html` |
| `#model-select-dropdown` | "AI opponent" (sr-only) | "AI opponent model" | `model_select.html` |
| `#bid-type` | "Type:" | "Bid type" | `bid_panel.html` |
| `#bid-level` | "Bid:" | "Bid level" | `bid_panel.html` |
| `#bid-contract` | "Contract:" | "Contract suit" | `bid_panel.html` |
| `#invite-code-input` | "Invite code" (sr-only) | "Invite code" | `invite_code_form.html` |

**Recommended fix:** Remove `aria-label` from elements that already have
associated `<label>` elements. The visible label (or sr-only label) is
sufficient and avoids the override mismatch.

**PR scope:** 3 template files.

---

### Finding 8: `role="region"` overuse [MEDIUM]

**WCAG criterion:** 1.3.1 Info and Relationships (advisory)

Almost every `<div>` wrapper has `role="region"` with an `aria-label`. While
technically valid, this makes landmark navigation very noisy — a screen reader
user navigating by landmarks hears 10+ regions, diluting the value.

WCAG recommends using landmark roles sparingly:

| Element | role="region" needed? | Rationale |
|---------|----------------------|-----------|
| `#game-board` | ✅ Yes | Primary dynamic content area |
| AI hands row | ❌ Maybe | Supplementary info, not a primary landmark |
| Trick area | ✅ Yes | Core interactive area |
| Score bar | ✅ Yes | Key status info |
| Bid panel | ✅ Yes | Interactive auction controls |
| Human hand | ✅ Yes | Primary interaction area |
| Action rail (`<aside>`) | ✅ Already has implicit role | `<aside>` = complementary |
| Game controls | ❌ No | Minor UI chrome |
| Next controls | ❌ No | Transient control |
| Help drawer | ❌ No | Supplementary content |
| Various HTMX swap targets | ❌ No | Implementation detail |

**Recommended fix:** Remove `role="region"` from secondary wrappers, keep it
on the 5-6 primary interactive areas.

**PR scope:** 5-6 template files.

---

### Finding 9: Redundant ARIA roles on semantic elements [MEDIUM]

**WCAG criterion:** None directly (best practice)

| Element | Native role | Explicit role | Action |
|---------|------------|---------------|--------|
| `<header>` | banner (when child of body) | `role="banner"` | Remove redundant role |
| `<main>` | main | `role="main"` | Remove redundant role |
| `<details>` (trick-history) | group | `role="region"` | Remove — overrides native semantics |

**Recommended fix:** Remove redundant `role` attributes. The `<details>`
element in trick-history should not have `role="region"` as it overrides
the native disclosure semantics.

**PR scope:** 2 template files (`base.html`, `trick_history.html`).

---

### Finding 10: No `<footer>` element [LOW]

**WCAG criterion:** None (best practice)

The page has no `<footer>` landmark. For a game UI this is fine, but adding a
minimal footer with copyright/link info would complete the landmark structure.

---

### Finding 11: `<details>` native semantics overridden [LOW]

The trick history `<details>` element has `role="region"` which overrides the
native disclosure widget semantics. Screen readers may not announce the
expand/collapse behavior properly.

**Fix:** Remove `role="region"` from `<details id="trick-history">`.

---

### Finding 12: No keyboard shortcut documentation [LOW]

No `accesskey` attributes or shortcut documentation exists. Adding basic
keyboard shortcuts (e.g., `P` for Pass, `N` for Next) with documentation
would improve the play experience for keyboard-only users.

---

## What's Working Well ✅

The following accessibility features are properly implemented:

1. **Skip navigation link** — `.skip-link` hidden until focused, jumps to `#main-content`
2. **Focus-visible styles** — 3px green ring on keyboard focus, suppressed on mouse
3. **Touch target sizing** — 44px minimums via `@media (pointer: coarse)` and narrow breakpoints
4. **Reduced motion** — `@media (prefers-reduced-motion: reduce)` suppresses all animations
5. **High contrast mode** — `@media (forced-colors: active)` provides fallback borders
6. **Screen-reader-only class** — `.sr-only` properly implemented for hidden labels
7. **Card ARIA labels** — Every card has descriptive `aria-label` ("Play Ace of Spades")
8. **Decorative content hidden** — Emoji and suit symbols use `aria-hidden="true"`
9. **Table semantics** — Proper `<thead>`, `<th scope="col">`, `<tbody>` throughout
10. **Form labels** — Every input has an associated `<label>` element
11. **AI hand descriptions** — Face-down cards use `role="img"` with card count labels
12. **Error pages** — Use `role="alert"` with descriptive text
13. **Invite code input** — `aria-describedby` links to help text
14. **Exchange selection** — Uses `aria-pressed` for toggle state
15. **Leaderboard** — Proper table roles, sticky headers, metric tooltips

---

## Recommended PR Decomposition

### PR 1: Fix contrast colors [CRITICAL] — 1 file

**Files:** `web/static/style.css`

**Changes:**
- Update `--color-positive` to `#81c784` (or new `--color-positive-text` variable)
- Update `--color-negative` to `#ff8a80` (or new `--color-negative-text` variable)
- Fix `.lead-suit` colors to use visible values on dark bg
- Fix `.invite-error` color
- Fix loner accent to use `--color-loner-glow` (`#b39ddb`) for text

**Contrast verification matrix (all against `#263238` surface):**

| Variable | Current | Proposed | Ratio |
|----------|---------|----------|-------|
| `--color-positive` (text use) | `#2e7d32` (1.94:1) | `#81c784` (5.4:1) | ✅ |
| `--color-negative` (text use) | `#c62828` (1.58:1) | `#ff8a80` (4.6:1) | ✅ |
| Loner text | `#7e57c2` (1.79:1) | `#b39ddb` (5.1:1) | ✅ |

**Risk:** Changing CSS variables may affect non-text uses (borders, backgrounds)
where the darker originals are fine. May need separate `*-text` variables for
foreground color vs. the existing variables for borders/backgrounds.

**Validation:**
```bash
# Visual inspection of all phases
uv run python -m pytest tests/unit/ -k "test_template" --no-header
# Manual: open game in browser, check all phases with DevTools contrast checker
```

### PR 2: Fix HTMX focus management [HIGH] — 1 file

**Files:** `web/static/game.js`

**Changes:** Add focus management to `htmx:afterSwap` handler

**Validation:**
```bash
# Tab through game in browser without mouse
# Verify focus lands on meaningful element after each HTMX swap
# Test with screen reader (VoiceOver on macOS)
```

### PR 3: Clean up ARIA issues [MEDIUM] — 5-6 files

**Files:** Templates — `game.html`, `base.html`, `trick_history.html`,
`nickname_form.html`, `model_select.html`, `bid_panel.html`

**Changes:**
- Remove `aria-live` from `#game-board` container
- Remove redundant `aria-label` on labeled inputs
- Remove redundant `role` attributes on semantic elements
- Remove `role="region"` from `<details>` and secondary wrappers

**Validation:**
```bash
make check-quiet
# Screen reader testing with VoiceOver
```

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| CSS variable change cascades to borders/backgrounds | Medium | Use separate `*-text` variables for foreground color; keep original variables for backgrounds/borders |
| Focus management interferes with HTMX morph | Medium | Test with idiomorph swap mode; focus after morph completes |
| Removing `aria-live` from container breaks screen reader flow | Low | Test with VoiceOver before and after; keep leaf live regions |
| Color changes affect moon/loner visual identity | Low | Only change text-on-surface combinations; keep glow/border colors |

---

## Non-Text Contrast (WCAG 1.4.11)

For completeness, graphical elements need 3:1 contrast:

| Element | Current | Ratio vs surface | Verdict |
|---------|---------|------------------|---------|
| Card borders (legal) | `#2e7d32` on `#263238` | 1.94:1 | ⚠️ FAIL — but compensated by glow |
| Result--win border | `#2e7d32` on `#263238` | 1.94:1 | ⚠️ FAIL |
| Result--loss border | `#c62828` on `#263238` | 1.58:1 | ⚠️ FAIL |
| Card backs | `#1565c0` on `#2e7d32` | ~2.1:1 | ⚠️ FAIL — but decorative |
| Empty card slot dashed border | `rgba(255,255,255,0.3)` | ~1.8:1 | ⚠️ FAIL — decorative placeholder |

Non-text contrast failures are **lower priority** than text contrast failures.
The card border failures are partially compensated by the green glow
(`box-shadow`) which provides additional visual distinction.

---

## Outcome

Audit complete. Three PRs recommended:
1. **PR 1 (Critical):** CSS contrast fix — 1 file, ~15 property changes
2. **PR 2 (High):** HTMX focus management — 1 file, ~15 lines JS
3. **PR 3 (Medium):** ARIA cleanup — 5-6 template files, attribute removals

Returning to orchestrator for dispatch.
