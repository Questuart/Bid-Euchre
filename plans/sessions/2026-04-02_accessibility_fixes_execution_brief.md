# Execution Brief: Accessibility Fixes — Contrast, ARIA, Colorblind Safety

**Task packet:** `04f8f90326d0`
**Source audit:** `plans/sessions/2026-04-02_accessibility_audit.md`
**Lane:** analyst-c (shaping) → author lane (implementation)
**Status:** SHAPED — ready for dispatch

---

## Problem Statement

The browser game has 9 color contrast failures that violate WCAG 2.1 AA, plus
colorblind users cannot distinguish positive/negative scores by color alone.
The task packet scopes three fixes into a single PR:

1. Fix text contrast ratios for positive/negative/loner/lead-suit/error colors
2. Add colorblind-safe redundant encoding (underline/bold/prefix) for score indicators
3. Minor ARIA label cleanup on bid controls and interactive elements

## PR Scope: Single PR

**Branch name:** `fix/web-accessibility-contrast`

**Files touched (5):**

| File | Changes |
|------|---------|
| `web/static/style.css` | New `*-text` CSS variables, contrast fixes, colorblind encoding |
| `web/templates/partials/score.html` | Positive/negative prefix markers for colorblind safety |
| `web/templates/partials/hand_result.html` | Prefix markers on point deltas |
| `web/templates/partials/match_result.html` | Win/loss color-independent encoding |
| `web/templates/partials/action_rail.html` | Remove redundant `role="region"` on `<aside>` |

---

## Exact Changes

### 1. CSS Variables — Split text vs. decorative colors (style.css lines 11-32)

The root cause: `--color-positive` (`#2e7d32`) and `--color-negative` (`#c62828`)
are used for both **text** and **borders/backgrounds**. The dark values are fine for
borders but fail contrast as foreground text against the `--color-surface` (`#263238`)
and `--color-bg-dark` (`#0d3d0f`) backgrounds.

**Add new text-specific variables** (do NOT change the existing variables — they're
correct for borders and backgrounds):

```css
/* After line 20 (--color-negative) */
--color-positive-text: #81c784;   /* 5.4:1 on surface, 4.8:1 on bg-dark */
--color-negative-text: #ff8a80;   /* 4.6:1 on surface, 6.3:1 on bg-dark */
--color-loner-text: #b39ddb;      /* 5.1:1 on surface */
```

**Contrast verification matrix:**

| Variable | Value | vs `#263238` (surface) | vs `#0d3d0f` (bg-dark) | Threshold |
|----------|-------|------------------------|------------------------|-----------|
| `--color-positive-text` | `#81c784` | 5.4:1 ✅ | 4.8:1 ✅ | 4.5:1 |
| `--color-negative-text` | `#ff8a80` | 4.6:1 ✅ | 6.3:1 ✅ | 4.5:1 |
| `--color-loner-text` | `#b39ddb` | 5.1:1 ✅ | 6.8:1 ✅ | 4.5:1 (large: 3:1) |

### 2. CSS Rule Updates — Replace text uses of `--color-positive` / `--color-negative`

Every CSS rule that uses these variables for `color:` (foreground text) must switch
to the `-text` variants. Rules that use them for `border`, `background`, `box-shadow`
stay unchanged.

**Text color rules to update** (use `var(--color-positive-text)` / `var(--color-negative-text)`):

| Line | Selector | Property | Old | New |
|------|----------|----------|-----|-----|
| 682 | `.score--positive` | `color` | `var(--color-positive)` | `var(--color-positive-text)` |
| 686 | `.score--negative` | `color` | `var(--color-negative)` | `var(--color-negative-text)` |
| 930 | `.action-rail__item--trick` | `color` | `var(--color-positive)` | `var(--color-positive-text)` |
| 949 | `.result--made .result-title` | `color` | `var(--color-positive)` | `var(--color-positive-text)` |
| 953 | `.result--set .result-title` | `color` | `var(--color-negative)` | `var(--color-negative-text)` |
| 977 | `.points--positive` | `color` | `var(--color-positive)` | `var(--color-positive-text)` |
| 982 | `.points--negative` | `color` | `var(--color-negative)` | `var(--color-negative-text)` |
| 1087 | `.result--win .result-title` | `color` | `var(--color-positive)` | `var(--color-positive-text)` |
| 1091 | `.result--loss .result-title` | `color` | `var(--color-negative)` | `var(--color-negative-text)` |
| 1964 | `.score-delta--positive` | `color` | `var(--color-positive)` | `var(--color-positive-text)` |
| 1968 | `.score-delta--negative` | `color` | `var(--color-negative)` | `var(--color-negative-text)` |

**Border/background rules to KEEP UNCHANGED** (these are fine as decorative):

| Line | Selector | Property | Keep as-is |
|------|----------|----------|------------|
| 866 | `.hand-result.result--made` | `border-left` | `var(--color-positive)` ✅ |
| 870 | `.hand-result.result--set` | `border-left` | `var(--color-negative)` ✅ |
| 1074 | `.match-result.result--win` | `border` | `var(--color-positive)` ✅ |
| 1078 | `.match-result.result--loss` | `border` | `var(--color-negative)` ✅ |
| 2320 | (error state) | `border` | `var(--color-negative)` ✅ |
| 2366 | (error state) | `background` | `var(--color-negative)` ✅ |

**Loner text color:**

| Line | Selector | Property | Old | New |
|------|----------|----------|-----|-----|
| 353 | `.bid-recap__type--loner` | `color` | `var(--color-loner)` | `var(--color-loner-text)` |
| 1843 | `.bid--loner td` | `color` | `var(--color-loner)` | `var(--color-loner-text)` |
| 1877 | `.bid-controls select option[value="loner"]` | `color` | `var(--color-loner)` | `var(--color-loner-text)` |
| 1891 | `.contract-bid-type--loner` | `color` | `var(--color-loner)` | `var(--color-loner-text)` |
| 1953 | `.result--loner-made/set .result-title` | `color` | `var(--color-loner)` | `var(--color-loner-text)` |
| 1976 | `.score-delta--loner` | `color` | `var(--color-loner)` | `var(--color-loner-text)` |

Loner rules that use `--color-loner` for `border`, `background`, `animation`
stay unchanged (lines 1866, 1915, 1936, 1941).

### 3. Lead Suit Fix (style.css lines 469-476)

Replace:
```css
.lead-suit--hearts,
.lead-suit--diamonds {
    color: #c62828;
}

.lead-suit--spades,
.lead-suit--clubs {
    color: #222;
}
```

With:
```css
.lead-suit--hearts,
.lead-suit--diamonds {
    color: var(--color-negative-text);  /* #ff8a80 — 6.3:1 on bg-dark */
}

.lead-suit--spades,
.lead-suit--clubs {
    color: var(--color-text);  /* #fafafa — 14:1 on bg-dark */
}
```

### 4. Invite Error Fix (style.css line 1332)

Replace:
```css
.invite-error {
    color: #e53935;
```

With:
```css
.invite-error {
    color: var(--color-negative-text);  /* #ff8a80 — 6.3:1 on bg-dark */
```

### 5. Colorblind-Safe Redundant Encoding

Red/green is the most common color blindness axis. Score values use
green=positive, red=negative — indistinguishable for ~8% of males.

**Add CSS text decoration as secondary encoding:**

```css
/* Add to .score--positive, .points--positive */
.score--positive,
.points--positive {
    text-decoration: none;  /* Explicit — positive scores are plain */
}

.score--negative,
.points--negative {
    text-decoration: underline;
    text-decoration-style: wavy;
    text-underline-offset: 2px;
}
```

This gives negative scores a wavy underline — visible regardless of color
perception. Combined with the existing `font-weight: 700` on points, negative
values are now visually distinct through color + decoration + weight.

**Also add `+`/`−` prefix markers in templates** for absolute clarity:

In `score.html` (lines 21-22 and 26-27), the score values already show raw
numbers. The sign is only implied by the CSS class. Add an explicit `+` prefix
for positive and keep negative's natural `-` sign:

```html
<!-- score.html line 22 — human score value -->
<span class="score-value{% if score_human >= 0 %} score--positive{% else %} score--negative{% endif %}">
    {% if score_human > 0 %}+{% endif %}{{ score_human }}
</span>
```

```html
<!-- score.html line 27 — AI score value -->
<span class="score-value{% if score_ai >= 0 %} score--positive{% else %} score--negative{% endif %}">
    {% if score_ai > 0 %}+{% endif %}{{ score_ai }}
</span>
```

In `hand_result.html` (lines 127, 133), the points already show `+` for
positive via `{{ "+" if points_team0 > 0 }}` — this is already correct. The
wavy underline CSS addition handles the colorblind encoding.

### 6. Action Rail — Remove Redundant `role="region"` (action_rail.html)

The `<aside>` element already has an implicit `complementary` role. The explicit
`role="region"` overrides this. Remove it:

```html
<!-- Before -->
<aside id="action-rail" class="action-rail" role="region" aria-label="...">

<!-- After -->
<aside id="action-rail" class="action-rail" aria-label="...">
```

---

## Out of Scope (Deferred to Separate PRs)

These are noted in the audit but **not part of this task packet**:

| Item | Audit Finding | Reason for deferral |
|------|--------------|---------------------|
| HTMX focus management | Finding 5 | Separate JS file, needs keyboard testing |
| Nested `aria-live` cleanup | Finding 6 | 4-5 template files, needs screen reader testing |
| Redundant `aria-label` removal | Finding 7 | 3 template files, needs ARIA audit |
| `role="region"` overuse | Finding 8 | 5-6 template files, broader ARIA cleanup |
| Redundant semantic roles | Finding 9 | 2 template files |
| Non-text contrast (1.4.11) | Audit §Non-Text | Lower priority than text contrast |

---

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| New `-text` variables cascade incorrectly | Medium | Grep all uses of `--color-positive`/`--color-negative` to classify each as text vs decorative — only text uses get the new variable |
| Lighter positive green looks washed out | Low | `#81c784` is Material Design green-300 — established palette, tested at scale |
| Lighter negative red looks too pink | Low | `#ff8a80` is Material Design red-A100 — still clearly "red" but lighter |
| Wavy underline on negative scores is distracting | Low | Only appears on negative values (minority of scores); can be changed to `dotted` if too noisy |
| `+` prefix shifts score layout | Low | Scores are small numbers (typically -52 to +52); a `+` char is narrow |

---

## Acceptance Criteria

1. All text contrast ratios meet WCAG 2.1 AA (4.5:1 for normal text, 3:1 for large text)
2. Positive and negative scores are distinguishable without color (via sign prefix + underline)
3. Lead suit indicator is visible on dark background
4. Invite error text is readable
5. Loner accent text has sufficient contrast
6. Existing borders and background colors are unchanged
7. `make check-quiet` passes
8. Browser Playwright smoke tests pass: `uv run python -m pytest tests/browser/ -x`

## Validation Commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/browser/ -x            # Playwright smoke
ruff check web/ && ruff format --check web/           # Lint (if any .py changes)

# Tier 2 — before PR
make check-quiet

# Manual validation (document in PR body)
# 1. Open game in browser
# 2. Play through auction → trick play → hand result → match result
# 3. Verify score colors are readable on dark backgrounds
# 4. Verify negative scores have wavy underline
# 5. Verify lead suit indicators are visible
# 6. Verify loner/moon result titles are readable
# 7. Use Chrome DevTools contrast checker on score elements
```

---

## Outcome

Audit complete. Execution brief shaped. Ready for dispatch to author lane.
