# Card Jitter / Flicker Investigation — Issue #2538

**Date:** 2026-04-06
**Lane:** analyst-b
**Branch:** `analyst/investigate-card-jitter-2538`
**Task packet:** `b39392ac1d7f`
**Delivery mode:** PR (committed findings artifact)
**Status:** Investigation complete. No code/CSS/template changes in this PR.

Refs #2538.

## TL;DR

The card-play experience in the hosted browser game has multiple uncoordinated
DOM mutations happening within a single idiomorph swap, several of them
restarting, stopping, or overriding CSS animations mid-flight. The result is a
visible flicker/jitter whenever:

1. A trick transitions from "complete" (4 cards shown) to "new trick started"
   (1 card shown),
2. The AI plays a card that is also the currently-winning card,
3. The human plays a card (their own card pops into the slot and the hand
   cards cascade with no transition).

The investigation found **two primary mechanical bugs** and **one UX design
gap** that compound:

- **Bug A — animation override:** `.card--ai-delayed` uses the `animation`
  shorthand and, due to cascade order, **silently overrides** the
  `winning-card-pulse` animation on the lead card when the AI plays a card
  that leaves them currently winning. This is a CSS cascade bug, not a bug in
  the engine or template.
- **Bug B — morph replaces state without restarting animations:** when
  idiomorph morphs a `card-slot--empty` `<div>` into a `card card--played`
  `<div>`, the element is the SAME DOM node — CSS keyframe animations fire on
  class attribute change, but the `.card` element has no baseline
  `animation-name` or `transition` that covers non-ai card entries, so the
  human's own card (and the AI's last card of a trick) just pops into place.
- **Design gap — trick-boundary morph:** the transition from
  `paused_after_trick` (4 cards, winner highlighted) → new trick lead (1 card
  in one slot, 3 `card-slot--empty` divs) is handled as a **single idiomorph
  swap with no choreography**. Three cards vanish atomically, one card's text
  content changes, two overlapping animations stop/restart in the same frame.

The fix is **small-to-medium**: primarily CSS + a small template / context
refinement to propagate a "card just appeared" flag for every played-card
slot (not only AI plays). No engine/state changes needed.

---

## 1. Reproduction Steps

### Environment

- Local FastAPI server: `http://localhost:8000` (already running per task packet)
- Invite codes available: `AADJ6ONJ`, `NICK-TEST`, `REED-TEST`, `OLIVIA-TEST`
- Browser: Playwright-managed Chromium

### Playwright reproduction (what was run)

1. `browser_navigate http://localhost:8000/`
2. Click "I have an invite code", type `AADJ6ONJ`, submit.
3. Start a new match.
4. During the auction, click through bids until the human has a playable hand
   with trump committed.
5. On the first human trick, install a `MutationObserver` over `#game-board`
   logging added/removed nodes and class-attribute mutations, stamped with
   `performance.now()` deltas.
6. Click a legal hand card (`.card--legal[data-card-index]`).
7. Observe the mutations on the initial human play and subsequent AI plays.
8. Wait for the trick to complete (4 cards), observe `paused_after_trick` UI.
9. Click `Next` on the trick-result screen to start the next trick.
10. Observe the mutations at the trick boundary.

### What the mutation log shows

**Event A — Human plays A♠ (first card of trick):**
- `#hand-card-0` `<button>` (A♠) is removed from the DOM.
- `#hand-card-1` through `#hand-card-9` all have their `id` attribute rewritten
  (1→0, 2→1, ..., 9→8). Their inner `<span class="card__rank">` / `__suit`
  text content is replaced in place. No `transition` or `animation` property
  applies to these nodes, so the shifting card faces **cascade instantly**
  with no visual feedback. There is no fade-out on the removed button.
- `.trick-slot--bottom > div`: its class attribute mutates from
  `card-slot--empty` → `card card--spades card--played`. Its inner structure
  replaces `<span class="seat-label">` with `<span class="card__rank">` +
  `<span class="card__suit">`. **No animation fires** because `.card--played`
  has no `animation-name` baseline.
- `#trick-area` has `trick-area--ai-revealing` class added (server computed
  `ai_just_played=False` for the human, but the class is gated on
  `ai_just_played` so — wait, this class is NOT added for a human play, see
  `web/templates/partials/trick.html` line 85).

**Event B — ~850 ms later, auto-advance fires `/next`; AI plays next card:**
- Server renders with `ai_just_played=True` and `last_played_seat=1` (Slim).
- Morph sets `.trick-slot--left > div` class `card-slot--empty` → `card
  card--clubs card--played card--bower card--ai-delayed`. The `card--ai-delayed`
  class brings `animation: ai-card-reveal 0.75s ease-out both` → this one AI
  card **does** get its fade-in.
- `#trick-area` gains `trick-area--ai-revealing` (gates the Next-button
  delay).
- Auto-advance schedules the next `/next` at 850 ms.

**Event C — Last AI card of the trick completes the trick:**
- Server sets `paused_after_trick = True`, NOT `paused_after_play` (see
  `src/bid_euchre/hosted_play/engine.py` line 733-735).
- Therefore `web/routes.py` computes `ai_just_played = False` because the
  condition at line 579-584 requires the `paused_after_play` flag:
  ```python
  ctx["ai_just_played"] = (
      hand.phase == "trick_play"
      and hand.paused_after_play          # ← false on trick boundary
      and last_seat is not None
      and last_seat != HUMAN_SEAT
  )
  ```
- So the 4th card (the trick-closing AI card) is rendered **without**
  `card--ai-delayed`. It pops into the last empty slot with no animation.
  This is a pre-existing gap — issue #2386 / #2442 fixed per-card reveal but
  the trick-closing card falls outside the `paused_after_play` branch.
- Simultaneously, the winning slot gains `trick-slot--winner`, which triggers
  the `winner-card-glow` 1.5 s animation on the descendant card (CSS selector
  `trick-slot--winner card`, space-separated compound). This glow **does**
  play, but on the already-present card (the one that had been `card--winning`
  a moment ago), not on the trick-closing card.
- `card--winning` (lines 261-265 in `web/static/style.css`) is dropped from
  the previously-winning card because `current_trick` is now `None`
  (template `web/templates/partials/trick.html` line 60: `is_winning` requires
  `current_trick is not none`), interrupting its `winning-card-pulse`
  animation mid-iteration.

**Event D — User clicks `Next` on trick-result screen; new trick lead:**
- Server calls `resume_ai`, `_advance_ai` runs the trick winner's lead card
  play, sets `paused_after_play = True`, returns.
- Server renders with:
  - `current_trick` containing 1 play (the lead).
  - `ai_just_played = True` (good).
  - `trick_winning_seat = <leader>` (they're winning because they're the
    only played card).
- Morph effects on the right slot (say Deuce just led):
  - Outer `.trick-slot--right` class: `trick-slot trick-slot--right
    trick-slot--winner` → `trick-slot trick-slot--right`. This **stops**
    the `winner-card-glow` animation mid-iteration.
  - Inner card div class: `card card--spades card--played card--bower` (J♠
    trick 2 winner) → `card card--spades card--played card--winning
    card--ai-delayed` (A♠ trick 3 lead). The card's **text content** changes
    simultaneously. The `.card__rank` span's text node is mutated in place.
  - Because `card--ai-delayed` is declared AFTER `card--winning` in
    `web/static/style.css` (line 268 vs line 261) and both use the shorthand
    `animation:` property, **`card--winning` loses its cascade battle**:
    the computed `animation` on the element becomes `ai-card-reveal 0.75s
    ease-out both`. The `winning-card-pulse 2s infinite` is **never applied**
    while `card--ai-delayed` is present. **This is Bug A.**
- Morph effects on the other three slots (top/left/bottom — NOT the leader):
  - Outer class: `trick-slot trick-slot--<pos>` (may drop `trick-slot--winner`
    if they were a non-winning slot of the previous trick — same
    instantaneous stop).
  - Inner div: `card card--<suit> card--played ...` (showing the previous
    trick's card from that seat) → `card-slot--empty` (showing a seat
    label). **Inner text flips** from rank/suit spans to `<span
    class="seat-label">`, and the element's class attribute changes from
    the long `card` class list to the short `card-slot--empty`. No
    animation, no fade-out, no transition. Three cards vanish atomically.
- Meanwhile the hand partial morphs (winner-of-last-trick gets a new full
  hand of 10, if loser → no change). The previously-winning player had their
  card played in this request, so their hand cascades too.
- Auto-advance fires 850 ms later; but if the next player is the human,
  `_advance_ai` returns immediately at the "current_seat == HUMAN_SEAT" check
  (`src/bid_euchre/hosted_play/engine.py` lines 619-621) **without** re-setting
  `paused_after_play` — so `resume_after_play` cleared it, the loop returns,
  and the response has `paused_after_play = False`, `ai_just_played = False`,
  `show_next = False`, legal hand shown. Morph removes `card--ai-delayed` from
  the lead card mid-reveal-animation if the 750 ms reveal hasn't finished.
  Since 850 ms > 750 ms the reveal usually does complete, but the subsequent
  morph then triggers a fresh animation handoff: the element gains back its
  implicit `winning-card-pulse` (because `card--ai-delayed` is gone and
  `card--winning` is still present), starting a new 2 s animation from t=0.
  The gold glow "snaps on."

### Summary of observed jitter sources

| # | Event                                    | Cause                                               |
|---|------------------------------------------|-----------------------------------------------------|
| 1 | Played human card pops into bottom slot  | No animation baseline on `.card--played` entry      |
| 2 | Hand cards reflow when played card removed | No `transition` on `.card` position / opacity     |
| 3 | Trick-closing AI card pops without reveal | `paused_after_trick` bypasses `ai_just_played` gate |
| 4 | Winning-card-pulse snaps off at trick end | `.card--winning` dropped mid-animation              |
| 5 | Previous-trick cards vanish when new trick starts | Empty-slot morph is instantaneous             |
| 6 | Winning-card-pulse absent on new trick lead | Bug A — `card--ai-delayed` overrides `card--winning` |
| 7 | Winning-card-pulse "snaps on" 850 ms later | Second morph removes `card--ai-delayed`, new animation keyframe start |
| 8 | `winner-card-glow` stops mid-iteration   | `trick-slot--winner` class dropped at trick boundary |

---

## 2. Root Cause Analysis

### File references (source of truth)

| File | Line(s) | Role |
|---|---|---|
| `web/static/style.css` | 183-199 | `.card` base — only transitions `transform` and `box-shadow` (0.15 s) |
| `web/static/style.css` | 245-250 | `.card--played` — no animation baseline, no `opacity` transition |
| `web/static/style.css` | 260-265 | `.card--winning` — `animation: winning-card-pulse 2s ease-in-out infinite` |
| `web/static/style.css` | 267-281 | `.card--ai-delayed` — `animation: ai-card-reveal 0.75s ease-out both` **(cascade wins over `.card--winning`)** |
| `web/static/style.css` | 935-940 | `trick-slot--winner` descendant card selector — `animation: winner-card-glow 1.5s ease-in-out 2` |
| `web/templates/partials/trick.html` | 55-78 | `card_slot` macro — renders `card-slot--empty` OR `card card--played ...` on the same parent slot element |
| `web/templates/partials/trick.html` | 60-62 | `is_winning` depends on `current_trick is not none` — drops `card--winning` at trick boundary |
| `web/templates/partials/trick.html` | 85 | `trick-area--ai-revealing` class — conditional on `ai_just_played`, which is False on `paused_after_trick` |
| `web/templates/partials/hand.html` | 44-69 | Hand card list — cards are `<button>` when legal, `<div>` when illegal; IDs `hand-card-{idx}` **cascade** on play (removed card's ID is reassigned to the next card) |
| `web/routes.py` | 282-287 | `_last_played_seat` — returns seat of last card in active trick |
| `web/routes.py` | 575-584 | `ai_just_played` computation — gated on `paused_after_play` (false on `paused_after_trick`) |
| `web/routes.py` | 590-603 | `auto_advance_delay_ms` — 850 ms for AI, 500 ms for human (matches `ai-card-reveal` 0.75 s duration + 100 ms buffer) |
| `src/bid_euchre/hosted_play/engine.py` | 619-621 | `_advance_ai` returns early when it reaches human's turn — does NOT set `paused_after_play` for the AI card immediately before (it was already set at line 739 in the prior iteration) |
| `src/bid_euchre/hosted_play/engine.py` | 728-740 | **Every** AI card play sets either `paused_after_play` (trick in progress) or `paused_after_trick` (trick completed) — this branch is correct, per-card pacing always pauses |
| `src/bid_euchre/hosted_play/engine.py` | 263-296 | `submit_human_card` — human play also sets `paused_after_play` / `paused_after_trick` |
| `web/static/game.js` | 169-180 | `htmx:afterSwap` handler — clears card selection, restores panel state, but does NOT coordinate animation restart |
| `web/static/game.js` | 739-748 | `htmx:afterSettle` on `#game-board` — schedules auto-advance timer but has no animation choreography hook |

### The cascade bug (Bug A)

From `web/static/style.css` lines 261-281:

```css
.card--winning {
    box-shadow: 0 0 10px 3px rgba(255, 215, 0, 0.8);
    border: 2px solid #ffd700;
    animation: winning-card-pulse 2s ease-in-out infinite;
}

.card--ai-delayed {
    animation: ai-card-reveal var(--ai-card-delay, 0.75s) ease-out both;
}
```

Both rules set the CSS shorthand `animation:` property. When two rules with
equal specificity (both single-class selectors: 0,1,0) target the same
element, **CSS source order decides** — the later rule wins. `.card--ai-delayed`
is declared after `.card--winning`, so on any element that has **both**
classes, the computed `animation-name` is `ai-card-reveal` only. The
`winning-card-pulse` is cleanly overridden, not composed.

This happens **every time** the AI plays a card that leaves them as the
currently-winning player — which is the norm for the lead card of a new
trick. The gold pulse effect is invisible for ~750 ms until `card--ai-delayed`
is removed on the next morph.

CSS shorthand animation override is a subtle CSS footgun. The fix is either:
(a) use the longhand `animation-name: ai-card-reveal, winning-card-pulse;`
and matching longhand durations, or (b) declare a compound selector
`.card--winning.card--ai-delayed` that explicitly specifies both animations
as a comma-separated list.

### The morph-without-animation bug (Bug B)

Idiomorph 0.3.0 with `morph:innerHTML` is designed to **preserve DOM identity**.
When an element's class attribute is mutated from `card-slot--empty` to `card
card--played ...`, the browser sees:

1. Class list change → recompute styles.
2. New computed `animation-name` = the value from `.card--played`. But
   `.card--played` has **no** `animation` property. So no animation fires.

The base `card` class itself (lines 183-199 in `web/static/style.css`) only
has:
```css
transition: transform 0.15s ease, box-shadow 0.15s ease;
```
Neither `opacity`, `transform` from a hidden initial state, nor a default
`animation` is declared. So the card just **appears** — it's there in the
next paint frame, with no fade-in.

The only path to a reveal animation is via `card--ai-delayed`, which is
gated in `web/templates/partials/trick.html` lines 61-62 on `ai_just_played
AND last_played_seat == seat`. That gate **excludes** human cards AND the
trick-closing AI card (see Bug C below).

### The `paused_after_trick` gap (Bug C, design gap)

From `web/routes.py` lines 579-584:

```python
ctx["ai_just_played"] = (
    hand.phase == "trick_play"
    and hand.paused_after_play
    and last_seat is not None
    and last_seat != HUMAN_SEAT
)
```

When the AI plays the 4th card of a trick, the `_advance_ai` loop in
`src/bid_euchre/hosted_play/engine.py` sets `paused_after_trick = True`, NOT
`paused_after_play` (engine lines 733-735). Because `ai_just_played` requires
`paused_after_play`, the trick-closing AI card is rendered **without**
`card--ai-delayed` → no reveal animation. The card just pops into the last
empty slot.

This is a pre-existing mis-match between the engine's pacing state machine
and the template's "reveal" condition. Fixing it requires either:
- Include `paused_after_trick` in the condition: `and (hand.paused_after_play
  or hand.paused_after_trick)`, OR
- Emit a separate "card_just_appeared" flag per slot (see recommendation
  below).

### The trick-boundary morph (Bug D, choreography gap)

When transitioning from `paused_after_trick` → new trick lead in a single
HTMX swap, idiomorph performs ~6 simultaneous class-and-content mutations:

1. `trick-slot--<winner>` loses `trick-slot--winner` → stops `winner-card-glow`.
2. Lead card's slot gains `card--winning` + `card--ai-delayed` → animations
   collide (Bug A).
3. Three non-lead slots flip from `card card--played ...` with rank/suit
   spans → `card-slot--empty` with a seat-label span → **atomic, no fade-out**.
4. `#trick-area` heading text changes from "Trick N of 10 complete" → "Trick
   N+1 of 10" — DOM text-node mutation.
5. `.trick-winner` paragraph is removed (current_trick is non-null, so the
   `if display_winner is not none` branch no longer applies) — **no fade-out**.
6. Hand partial morphs: winner-of-previous-trick may have had their card
   played, cascading hand IDs.

All of this happens in a single paint frame. Because there is no orchestration
(no `View Transitions API` use, no sequenced animations, no `hx-swap`
`settle-delay`), the effect is a **visual stutter**: several things move at
once with no temporal separation. The brain perceives this as flicker.

---

## 3. Concrete Fix Recommendation

The fix is layered — start with the smallest, lowest-risk change and escalate
only as needed.

### Recommendation (primary, small — 2 files, ~30 lines)

**Goal:** Eliminate Bug A (animation override) and Bug C (`paused_after_trick`
gap), and smooth the trick-boundary empty-slot morph. Leave the choreography
gap (Bug D) for a follow-up.

#### Fix 1 — `web/static/style.css`

Replace the current `.card--ai-delayed` rule with an explicit compound rule
that composes with `.card--winning`:

```css
/* AI card delay — fade-in animation when AI plays (#2330).  Declared with
   longhand animation-name so compound selectors below can extend rather
   than override. */
.card--ai-delayed {
    animation-name: ai-card-reveal;
    animation-duration: var(--ai-card-delay, 0.75s);
    animation-timing-function: ease-out;
    animation-fill-mode: both;
}

/* When an AI card is both revealing AND currently winning, compose both
   animations so the gold pulse starts after the reveal completes. */
.card--winning.card--ai-delayed {
    animation-name: ai-card-reveal, winning-card-pulse;
    animation-duration: var(--ai-card-delay, 0.75s), 2s;
    animation-timing-function: ease-out, ease-in-out;
    animation-delay: 0s, var(--ai-card-delay, 0.75s);
    animation-iteration-count: 1, infinite;
    animation-fill-mode: both, none;
}
```

Also add a subtle baseline transition to `.card` so that class-attribute
morphs smooth out:

```css
.card {
    /* existing rules ... */
    transition:
        transform 0.2s ease,
        box-shadow 0.2s ease,
        border-color 0.2s ease,
        opacity 0.2s ease;
}
```

#### Fix 2 — `web/routes.py`

Broaden the `ai_just_played` gate to include the trick-closing card:

```python
# Lines 579-584, replace:
ctx["ai_just_played"] = (
    hand.phase == "trick_play"
    and (hand.paused_after_play or hand.paused_after_trick)
    and last_seat is not None
    and last_seat != HUMAN_SEAT
)
```

Caution: `last_played_seat` during `paused_after_trick` must still resolve
to the 4th card's seat. `_last_played_seat` (lines 282-287) returns the last
play in the **active** trick; once the trick is moved to `completed_tricks`
the active trick's plays may be empty. Verify behavior by running locally
and inspecting the rendered class list on the winning-slot card during the
trick-result screen. If `_last_played_seat` returns `None` during
`paused_after_trick`, the helper must also fall back to
`hand.completed_tricks[-1].plays[-1][0]`.

#### Fix 3 — Optional, light choreography for the empty-slot morph

To address the "three cards vanishing atomically" part of Bug D, give
`.card-slot--empty` a default fade-in/out. Because it's the **element's
class** that changes (not a new DOM node), a pure `transition` on
`opacity` on the parent element won't trigger on class switch unless the
`opacity` value itself changes. The pragmatic hack:

```css
.card-slot--empty {
    /* existing layout ... */
    animation: slot-reset-fade 0.2s ease-out both;
}

@keyframes slot-reset-fade {
    0% { opacity: 0.3; transform: scale(0.95); }
    100% { opacity: 1; transform: scale(1); }
}
```

This fires every time a slot morphs back to empty (trick boundary). The
appearance is a gentle re-fade rather than an instant swap.

### Recommendation (secondary, if primary is insufficient — medium complexity)

Introduce an explicit **choreography step** at the trick-boundary morph by
adding a brief `hx-swap` transition class hook:

- `web/templates/partials/game_board.html` or
  `web/templates/partials/trick.html`: wrap the trick area in a container that
  gets a `data-transitioning` attribute when `paused_after_trick` is being
  cleared.
- `web/static/game.js` `htmx:beforeSwap` handler: add a `trick-area--fade-out`
  class on `#trick-area` 150 ms before the swap, let it fade the old cards,
  then let HTMX perform the morph. After the morph, `htmx:afterSwap` drops
  the class and adds `trick-area--fade-in`. CSS transitions handle the rest.

This is a heavier lift (touches `web/static/game.js`, the trick partial, and
`web/static/style.css`), but it would give the trick boundary a proper
cinematic handoff instead of a simultaneous mutation. **Defer to a follow-up
issue** unless the primary recommendation falls short in smoke testing.

### Recommendation NOT to take

Do **not** replace idiomorph with a full-innerHTML swap (hx-swap="innerHTML"
without morph). That would lose DOM identity preservation and break the hand
card selection state, HTMX scroll restoration, and any in-progress animations
the user benefits from. Idiomorph is the right tool; the fix is in how we
use it.

---

## 4. Estimated Complexity

| Scope | Files touched | LoC | Risk |
|---|---|---|---|
| Primary recommendation | `web/static/style.css`, `web/routes.py` (+ maybe `_last_played_seat`) | ~30 LoC | Low |
| + Optional Fix 3 (slot fade) | above + `web/static/style.css` | ~40 LoC | Low |
| Secondary recommendation (choreography) | `web/static/style.css`, `web/static/game.js`, `web/templates/partials/trick.html` | ~80–120 LoC | Medium |

**Total estimated complexity for the primary fix: SMALL.**

Primary + secondary combined: **SMALL-to-MEDIUM** (fits in one PR with
adequate Playwright smoke coverage).

No engine/state changes. No schema changes. No new tests for game logic.
New visual smoke tests should be added for the animation behavior (see
Risk section).

---

## 5. Risk Register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Adding a `transition` to the base `card` class may inadvertently animate **hand card selection** highlighting (`card--selected`, `card--legal` hover states), making selection feel sluggish | Scope the new transition to `card--played` only, not all cards. Alternatively, verify the existing `card--legal` hover is already covered by the 0.15 s transform/box-shadow transition and only add `opacity` / `border-color` transitions. |
| R2 | The compound `card--winning.card--ai-delayed` rule's chained animation delays the gold pulse for 750 ms. Users may perceive the winning highlight as "slow to kick in" | This is arguably an improvement (sequenced = more polished). Validate in the smoke test by timing the start of `winning-card-pulse` relative to the reveal. If negative feedback, reduce `ai-card-reveal` to 0.5 s and update `auto_advance_delay_ms` from 850 → 600 ms. |
| R3 | Broadening `ai_just_played` to include `paused_after_trick` may apply `card--ai-delayed` to the **wrong slot** if the `_last_played_seat` helper doesn't correctly return the 4th card's seat during that state | Verify `_last_played_seat` behavior in both `paused_after_play` and `paused_after_trick` states. Add a fallback to `completed_tricks[-1].plays[-1][0]` in the helper if needed. Cover with a new unit test in `tests/unit/hosted_play/` (or wherever existing routes tests live). |
| R4 | `card--ai-delayed` will start being applied on the trick-closing card, which is animated AND has the `trick-slot--winner` parent simultaneously. The compound `trick-slot--winner card` descendant selector has higher specificity (0,2,0) than `card--ai-delayed` (0,1,0) — the WINNING slot's glow animation (`winner-card-glow`) will **win** the cascade over `ai-card-reveal`, meaning the trick-closing card may revert to "no reveal animation" anyway | Add another compound rule: `trick-slot--winner card--ai-delayed` with the composed animation list. Or reorder cascade so `card--ai-delayed` wins on the trick-closing card. Test all four slot positions. |
| R5 | The `slot-reset-fade` animation (optional Fix 3) will fire on **every** render where a slot is empty, including the first render of a new trick for the 3 non-lead slots — which is correct — but also on initial page load. Fresh page load will show slots fading in. | Acceptable; matches polish elsewhere on the board. If objectionable, gate the animation class behind an `is_transition` flag computed server-side only when coming from `paused_after_trick`. |
| R6 | HTMX/idiomorph `morph:innerHTML` may not apply the new class mutation atomically with the text-content mutation, creating a one-frame gap where the old class's animation has been removed but the new animation hasn't started. This is existing behavior (and is part of what causes the current jitter) | The primary fix mitigates this by ensuring `card--winning` and `card--ai-delayed` are **composable**, so removing one without the other doesn't stop the other's animation. Also add `transition: opacity 0.2s` to the base card class so any one-frame gap manifests as a soft blend rather than a hard pop. |
| R7 | The auto-advance timer (`scheduleAutoAdvance` in `web/static/game.js` lines 699-737) triggers at 850 ms, but the new compound animation is 750 ms `ai-card-reveal` + 2 s `winning-card-pulse` starting at 0.75 s. If auto-advance fires during the pulse, the pulse stops mid-cycle (current behavior) | Expected; the pulse is infinite until trick end, so mid-cycle stops are normal. The fix is to make the STOP smoother via the new `transition: box-shadow 0.2s ease` on the base card class. |
| R8 | Hand card cascade (IDs `hand-card-N` getting remapped on play) has no fix in this recommendation. The human's hand still instantly reshuffles when a card is played | Out of scope for this fix — addressed in a follow-up. Low priority because this is the human's own action and the "pop" feels responsive rather than jittery. |
| R9 | Playwright visual regression tests for animations are flaky | Use `@keyframes` start/end state assertions rather than pixel-diff. Assert computed-style `animation-name` and `animation-delay` at specific times relative to the swap. Or use `browser_console_messages` with performance marks. |
| R10 | Mobile viewport behavior not verified in this investigation | The recommendation does not change mobile layout. Existing `@media (max-width: 600px)` rules in `web/static/style.css` are unaffected. Smoke-test on mobile viewport in Playwright. |

---

## 6. Files Referenced (Grep-Style Index)

| Path | Relevant lines |
|---|---|
| `web/static/style.css` | 183-199, 245-250, 260-281, 283-305, 924-940, 2845-2858, 3130-3145 |
| `web/static/game.js` | 100-180, 595-655, 664-798 |
| `web/templates/partials/trick.html` | 1-153 (entire file) |
| `web/templates/partials/hand.html` | 1-94 (entire file) |
| `web/templates/partials/next_controls.html` | 1-41 (entire file) |
| `web/templates/partials/game_board.html` | (composite partial — context for swap target) |
| `web/templates/base.html` | 40-54 (htmx + idiomorph script tags) |
| `web/routes.py` | 275-305, 328-340, 543-689, 1585-1858, 1941-1960 |
| `src/bid_euchre/hosted_play/engine.py` | 260-296, 543-570, 596-743 |

---

## 7. External Context

No external research was needed for this investigation — the bug is entirely
internal to our CSS cascade + template + engine pacing interaction.
Idiomorph's published behavior (GitHub `bigskysoftware/idiomorph`) aligns
with what was observed: in-place mutation of matched DOM nodes, preserving
identity and triggering style recomputation on class-attribute mutations.
The CSS shorthand `animation` cascade override behavior is documented in
[MDN: `animation`](https://developer.mozilla.org/en-US/docs/Web/CSS/animation)
(shorthand sets all longhands — a later rule with `animation:` replaces the
earlier rule's animation list entirely).

---

## 8. Recommended PR Decomposition

This is an investigation-only PR. If the fix proceeds from this report, it
should be decomposed as follows:

1. **PR A — CSS cascade + transition baseline (small, ~20 LoC).**
   - Update the `card--ai-delayed` rule to use longhand animation properties.
   - Add a `card--winning.card--ai-delayed` compound rule.
   - Add a `trick-slot--winner card--ai-delayed` compound rule (per R4).
   - Add a `card--played { transition: ... }` baseline.
   - Playwright smoke test: verify the computed animation-name on the lead
     card of a new trick is `ai-card-reveal, winning-card-pulse` when AI
     leads (assert via `getComputedStyle`).
   - Refs #2538 (does not close it).

2. **PR B — `ai_just_played` gate broadening + `_last_played_seat` fallback
   (small, ~10 LoC + 1 unit test).**
   - `web/routes.py` lines 579-584: include `paused_after_trick` in the gate.
   - `web/routes.py` lines 282-287: fallback to `completed_tricks[-1].plays[-1][0]`
     when the active trick is empty.
   - Create a new unit test in `tests/unit/web/` (or
     `tests/integration/hosted_play/`, depending on existing conventions) to
     add coverage for `ai_just_played` and `last_played_seat` during both
     pause states.
   - Refs #2538.

3. **PR C — Trick-boundary slot fade + smoke test (small-medium, ~30 LoC).**
   - Add a new `slot-reset-fade` keyframe and apply it to `card-slot--empty`.
   - Playwright visual test: navigate through a full trick, click Next on
     trick-result, assert no layout shift > 4 px within 300 ms post-swap.
   - `Fixes #2538` (closes the issue assuming smoke test passes).

4. **PR D — Follow-up: trick-boundary choreography (medium, deferred).**
   - Introduce `htmx:beforeSwap` / `htmx:afterSwap` choreography in
     `web/static/game.js`.
   - Optional; file as a new issue referencing #2538 and citing this report.

Estimated PR A + B + C total: **2–3 hours of dev time**, including
Playwright smoke tests. PR D is 4–6 hours if needed.

---

## 9. Validation & Smoke Test Boundary

For the **implementation PR(s)** that follow this investigation:

### Automated validation

```bash
# Tier 1 — targeted
uv run python -m pytest tests/unit/web/ tests/integration/hosted_play/ -v

# Tier 2 — full gated check before PR
make check-gated

# Manual Playwright smoke (new test)
uv run python -m pytest tests/integration/web/test_card_animations.py -v
```

### Manual smoke (pending user validation)

- Start a local match (`AADJ6ONJ` invite).
- Play one full hand (10 tricks) observing:
  - Each AI card fades in with the reveal animation (0.75 s each).
  - The trick-closing AI card fades in (not an instant pop).
  - The gold pulse on the winning card is visible THROUGHOUT the trick,
    including immediately after a new trick's lead card is played.
  - The trick boundary transition is smooth — no simultaneous
    instant-pop of 3 cards into empty slots.
  - The human's own card has a gentle appearance (not a hard pop).
- Test on mobile viewport (iPhone 13 Playwright emulation).
- Test with reduced motion preference (`prefers-reduced-motion: reduce`)
  — the animations should gracefully degrade (follow-up consideration).

### Out of scope (follow-up issues)

- Hand card cascade animation (when played card is removed and remaining
  cards reshuffle).
- Full View Transitions API adoption for the board.
- `prefers-reduced-motion` compliance for all card animations.

---

## 10. Handoff Notes for Orchestrator

- **What shipped in this lane:** this findings report only. No code/CSS
  changes. PR contains one new file: this markdown document.
- **What is in flight:** nothing after this PR merges.
- **What is blocked:** nothing — the fix path is clear and bounded.
- **Next safe slices for author dispatch:**
  - Dispatch PR A (CSS cascade + baseline transition) to a browser-game
    author lane (`brws-author-*`).
  - Dispatch PR B (`ai_just_played` gate + helper fallback) to the same lane
    after PR A merges (avoid stacked conflicts on routes.py / style.css).
  - Dispatch PR C (slot fade + smoke test) after PR B merges.
  - File PR D as a follow-up issue; defer until after user smoke-tests
    PR A–C.
- **User smoke tests pending:** yes — after PR C lands, the user should
  play a full hand locally and confirm the jitter is gone.
- **Restart notes:** the branch is `analyst/investigate-card-jitter-2538`
  off `origin/main`. The findings live at this path. If this session is
  lost, resume by reading `plans/sessions/2026-04-06_card_jitter_investigation.md`
  and dispatching PR A.
- **Constraints noted in task packet that were honored:**
  - ✅ Investigation only, no implementation.
  - ✅ Did not touch `web/ai_manager.py`.
  - ✅ Report contains reproduction steps, root cause with file:line refs,
    concrete fix recommendation, complexity estimate, and risk register.
  - ✅ Delivered as PR mode (committed markdown artifact).

Refs #2538.
