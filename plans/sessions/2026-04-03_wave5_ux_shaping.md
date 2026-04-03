# Wave 5 UX Shaping — Dispatch-Ready Implementation Plans

> **Date:** 2026-04-03
> **Analyst:** analyst-a
> **Task packet:** ad5cab91c059
> **Issues:** #2200, #2222, #2216, #2210, #2231

---

## Executive Summary

Wave 5 contains 5 issues across 4 independent work streams targeting the browser
game UX. All streams are parallelizable with **no file-scope overlap** when
decomposed correctly. Each stream has a different complexity profile.

| Stream | Issues | Complexity | Est. PRs | Lane |
|--------|--------|-----------|----------|------|
| A — UI cleanup | #2200 | Large (L) | 2-3 | brws-author-a |
| B — Tab navigation | #2222 + #2216 | Medium (M) | 1 | brws-author-b |
| C — Hand result pause | #2210 | Small (S) — **ALREADY DONE** | 0 | — |
| D — Card reveal pacing | #2231 | Medium-Large (M-L) | 2 | brws-author-d |

**Key finding:** Issue #2210 (show final hand result before match-over) was
**already fully implemented** in PR #2253 (merged). The `_game_phase()` function
now returns `"hand_result"` when the match is complete but the final hand is
available, and `hand_result.html` renders a "See Match Results" CTA. This issue
should be closed. Stream C needs no work.

---

## Stream A — UI Cleanup (#2200)

### Problem Statement

The gameplay screen has accumulated 17 UI elements with severe information
duplication. The user's direction from issue comments is clear:

1. **Progressive disclosure** — show details on demand, not always visible
2. **Words, not icons** — spell out labels ("Lead Trick" not "L", "Dealer" not "D")
3. **Phase-dependent visibility** — show Dealer prominently during auction, Lead
   prominently during trick play; hide the other
4. **Reduce badge clutter** — remove multi-badge stacking per seat
5. **Team color coding** — assign consistent team colors (green/blue) for scores
6. **Move contract display** — one place, clearly labeled ("Current Contract and
   Trump: 6\u2660 by You")
7. **Simplify score labels** — "Current Game Score" and "Current Trick Score"

### Evidence — Duplication Map (from analyst-d audit)

| Information | Current locations | Target |
|-------------|------------------|--------|
| Contract/trump | Contract bar + Score bar | **1x** in contract bar only |
| Declarer | Contract bar + Score bar + 3 AI seats + trick area | **1x** in contract bar |
| Dealer | D badge on 4 seats + Score bar | **1x** in score bar (auction only) |
| Tricks won | Trick center + Score bar | **1x** in trick center |
| Bid amount | bid-tag on 4 seat labels + Score bar | **1x** in action rail / bid history |

### Implementation Seam

**Primary files (write scope):**
- `web/templates/partials/game_board.html` — seat marker simplification,
  icon legend removal, compact badge removal
- `web/templates/partials/contract_bar.html` — consolidated contract display
  with team color, full text labels
- `web/templates/partials/score.html` — simplified to "Current Game Score"
  only (remove duplicate contract/tricks info)
- `web/templates/partials/trick.html` — phase-dependent seat markers,
  "LEAD" text label instead of "L" icon
- `web/static/style.css` — team color variables, phase-dependent visibility,
  progressive disclosure styles

**Secondary files (read-only or minor touch):**
- `web/templates/partials/bid_panel.html` — verify auction-phase display
- `web/templates/partials/action_rail.html` — no changes expected
- `web/templates/partials/game_controls.html` — help drawer content update
  (legend section references new labels)

### Recommended PR Decomposition

**PR A.1 — Deduplicate information and simplify labels** (M)
- Remove contract/declarer/tricks from score bar (already in contract bar)
- Rename score bar label to "Current Game Score"
- Add "Current Trick Score" label to trick center
- Remove icon legend (bottom of game board)
- Remove compact AI badges (mobile duplicate)

**PR A.2 — Phase-dependent markers and progressive disclosure** (M)
- Replace badge icons with text: "LEAD" instead of "L", "Dealer" instead of "D"
- Show "Dealer" prominently during auction, hide during trick play
- Show "Lead Trick" prominently during trick play, hide during auction
- Collapse seat markers to single-badge-per-seat (most important role only)
- Move bid history into action rail (already exists, just clean up)

**PR A.3 — Team color coding** (S)
- CSS custom properties for team colors (`--team-human`, `--team-ai`)
- Apply to: trick center score, contract bar team indicator, score bar
- Keep it subtle — color-coded text/borders, not background fills

### Acceptance Criteria

- [ ] No information appears in more than one location
- [ ] Score bar shows only "Current Game Score: You X | AI Y"
- [ ] Contract bar shows full text: "Current Contract and Trump: 6\u2660 by You"
- [ ] During auction: "Dealer" label visible, "Lead" hidden
- [ ] During trick play: "Lead Trick" label visible, "Dealer" hidden
- [ ] No more than 1 badge per seat label
- [ ] All existing tests pass (`uv run python -m pytest tests/unit/hosted_play/`)
- [ ] Playwright smoke suite passes (`tests/browser/test_smoke_suite.py`)

### Validation Commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/unit/hosted_play/test_partials.py -q
uv run python -m pytest tests/unit/hosted_play/test_routes.py -q

# Tier 2 — before PR
make check-quiet
```

### Risks

1. **Template test brittleness** — `test_partials.py` (219 tests) asserts
   specific HTML content. Every label rename or element removal will break
   assertions. Budget ~30% of implementation time for test updates.
2. **Mobile layout regression** — removing compact badges and icon legend
   changes mobile layout. Verify with Playwright mobile viewport tests.
3. **Scope creep** — user feedback has 8+ bullet points. Scope lock to the
   3 PRs above; defer "team colors in card backs" and "card animation" to
   later waves.

---

## Stream B — Tab Navigation Client-Side Switching (#2222 + #2216)

### Problem Statement

Tab navigation (Game/History/Leaderboard/Comments/Guide) uses full `<a href>`
links that trigger complete page reloads. On Render's free tier, this can
trigger 30-180+ second cold-start waits, effectively trapping users.

The user's decision: **Option A — HTMX partial swaps for all tabs.**

### Evidence

Current implementation in `web/templates/base.html` lines 64-80:
```html
<a href="/play/{{ link_uuid }}" role="tab" ...>Game</a>
<a href="/history/{{ link_uuid }}" role="tab" ...>History</a>
<a href="/leaderboard/{{ link_uuid }}" role="tab" ...>Leaderboard</a>
<a href="/comments/{{ link_uuid }}" role="tab" ...>Comments</a>
<a href="/guide/{{ link_uuid }}" role="tab" ...>Guide</a>
```

Each tab links to a separate GET route that renders a full-page template
extending `base.html`. The fix requires:

1. Adding HTMX attributes to tab links for partial content loading
2. Creating partial-response variants of each tab route
3. Preserving game state when switching away from and back to the Game tab

### Implementation Seam

**Primary files (write scope):**
- `web/templates/base.html` — add `hx-get`, `hx-target`, `hx-swap`,
  `hx-push-url` to tab links; add `#tab-content` wrapper div
- `web/routes.py` — add partial response variants for History, Leaderboard,
  Comments, Guide; detect `HX-Request` header for partial vs full response
- `web/templates/history.html` — extract inner content to partial
- `web/templates/leaderboard.html` — extract inner content to partial
- `web/templates/comments.html` — extract inner content to partial
- `web/templates/guide.html` — extract inner content to partial

**Key design decision:** Use the `HX-Request` header to detect HTMX requests
and return only the inner content block (without `base.html` wrapping).
This avoids creating separate partial template files — the same route serves
both full page (first visit) and partial (tab switch).

### Implementation Plan

**Single PR — Tab navigation HTMX conversion** (M)

1. Add a `#tab-content` wrapper in `base.html` around `{% block content %}`:
   ```html
   <div id="tab-content">
       {% block content %}{% endblock %}
   </div>
   ```

2. Convert tab links to HTMX:
   ```html
   <a href="/history/{{ link_uuid }}"
      hx-get="/history/{{ link_uuid }}"
      hx-target="#tab-content"
      hx-swap="innerHTML"
      hx-push-url="true"
      role="tab" ...>History</a>
   ```

3. In each tab route handler, detect HTMX and return partial:
   ```python
   if request.headers.get("HX-Request"):
       return templates.TemplateResponse(
           "history.html",
           ctx,
           block_name="content",  # Jinja2 block rendering
       )
   ```
   Note: Starlette's `Jinja2Templates.TemplateResponse` does not natively
   support `block_name`. The implementation must use either:
   - **Option 1:** Separate `_content.html` partial templates (simple, no Jinja2
     gymnastics)
   - **Option 2:** A helper that renders only the block content
   Recommend **Option 1** — create thin `partials/history_content.html` etc.
   that contain just the content, and have the full templates include them.

4. Handle the Game tab specially — clicking "Game" while viewing another tab
   must reload the current game state via HTMX, not preserve stale HTML.

5. Update active tab styling — when HTMX swaps content, the tab active state
   must update. Use `hx-on::before-request` to toggle `header-nav__tab--active`
   classes, or use HTMX's `hx-indicator` / event system.

### Acceptance Criteria

- [ ] Clicking any tab loads content without full page reload
- [ ] Browser URL updates when switching tabs (`hx-push-url`)
- [ ] Browser back/forward navigation works correctly
- [ ] Direct URL access (e.g., `/history/abc`) still renders full page
- [ ] Active tab styling updates correctly on switch
- [ ] Game board state is preserved when switching away and back
- [ ] No cold-start trigger on tab switch (same HTTP connection)
- [ ] All existing tests pass

### Validation Commands

```bash
# Tier 1
uv run python -m pytest tests/unit/hosted_play/test_routes.py -q
uv run python -m pytest tests/unit/hosted_play/test_app.py -q

# Browser test (manual or Playwright)
# Navigate through all 5 tabs — verify no full page reload
# Check Network tab: only XHR requests, no full document loads

# Tier 2
make check-quiet
```

### Risks

1. **Game state preservation** — When the user switches to History and back,
   the game board must reflect the current server state. This requires
   re-fetching the game board partial on "Game" tab click, not caching stale
   HTML.
2. **Browser history** — HTMX's `hx-push-url` handles forward navigation but
   back-button needs `hx-history-elt` or `htmx:historyRestore` event handling.
   The `htmx.config.historyCacheSize` may need tuning.
3. **Comments form** — The comments page has a POST form. Verify HTMX partial
   swap doesn't break form submission.
4. **Leaderboard complexity** — Leaderboard has interactive elements (metric
   sort). Verify JS reinitializes after HTMX swap (use `htmx:afterSwap` event
   like the existing `game.js` pattern).

---

## Stream C — Hand Result Pause Before Match-Over (#2210)

### Status: ALREADY IMPLEMENTED

**PR #2253** (merged) fully implements this feature:
- `_game_phase()` in `routes.py` returns `"hand_result"` when the match is
  complete but the final hand is available (lines 279-285)
- `hand_result.html` renders a "See Match Results" CTA when
  `match_status == "complete"` (lines 161-184)
- `next_hand` handler uses `force_match_result=True` to transition from
  hand result to match-over screen (line 1596)
- CSS styles for `.btn--see-results` and `.match-ending-notice` added

The user's decision comment states "Option A — show hand result, pause, then
match-over" which is exactly what was shipped.

### Recommendation

**Close issue #2210 as completed.** Reference PR #2253 in the closing comment.

---

## Stream D — Sequential Card Reveal with Pacing (#2231)

### Problem Statement

When the human player plays a card or hits "Next", all remaining AI cards in
the trick appear simultaneously. There's no sense of which card was played
first. Same issue during bidding — all AI bids resolve instantly.

The user's decision: Server-side pacing is preferred (Approach A). Include a
"skip" mechanism for experienced players.

### Current Architecture

The engine's `_advance_ai()` method (engine.py line 538) is a **while loop**
that plays all AI turns until it hits a stopping point:
- Human's turn
- Trick completed (`paused_after_trick = True`)
- Hand/match complete
- Redeal

This means a single `/next` POST resolves the **entire trick** (all remaining
AI cards) in one response. The trick area template then renders all played
cards simultaneously.

During the auction, `_advance_ai()` processes all AI bids in one call. The
existing hidden-auction-reveal mechanism (`revealed_auction_count`) already
provides a one-bid-at-a-time reveal model for bids placed *before* the
human's turn.

### Implementation Seam — Approach A (Server-Side)

**Key insight:** The engine already has the `paused_after_trick` mechanism that
pauses after trick completion. Extend this pattern to pause **after each AI
card play** — not just after trick completion.

**Primary files (write scope):**

*PR D.1 — Engine-level per-card pacing:*
- `src/bid_euchre/hosted_play/engine.py` — modify `_advance_ai()` to set a
  new `paused_after_play` flag after each AI card play (not just trick completion)
- `src/bid_euchre/hosted_play/state.py` — add `paused_after_play: bool = False`
  to `HandState`
- `web/routes.py` — modify `/next` handler to clear `paused_after_play` and
  resume AI for one more card (similar to existing `paused_after_trick` handling)

*PR D.2 — Auction pacing + skip mechanism:*
- `src/bid_euchre/hosted_play/engine.py` — modify auction advancement to pause
  after each AI bid (leverage existing `revealed_auction_count` mechanism)
- `web/templates/partials/next_controls.html` — add "Skip" button alongside
  "Next" for fast-forward
- `web/routes.py` — add `/play/{link_uuid}/skip` route that advances to the
  next human turn or trick completion without individual pauses

### Detailed Design — PR D.1 (Per-Card Pacing)

**State change:**
```python
# state.py — HandState
paused_after_play: bool = False  # True when paused after a single AI card play
```

**Engine change in `_advance_ai()`:**
```python
# After each AI card play (before the trick-completion check):
if hand_after.phase == "trick_play" and not trick_just_completed:
    hand_after.paused_after_play = True
    return state
```

**Route change in `/next`:**
```python
elif hand.phase == "trick_play" and hand.paused_after_play:
    hand.paused_after_play = False
    state = engine.resume_ai_one_card(state)  # new method
```

**New engine method `resume_ai_one_card()`:**
- Clears `paused_after_play`
- Plays exactly one AI card
- If trick completes, sets `paused_after_trick = True`
- If another AI card is needed, sets `paused_after_play = True`
- If human's turn, returns (no flags set)

### Detailed Design — PR D.2 (Auction Pacing + Skip)

The auction already has `revealed_auction_count` for gradual reveal. But
currently the reveal only applies to bids placed *before* the human's turn.
After the human bids, the remaining AI bids resolve instantly.

**Change:** After `submit_human_bid()`, set `auction_settled = False` and
start the same reveal mechanism for any AI bids that follow. Each "Next"
tap reveals one more AI bid.

**Skip mechanism:**
```python
@router.post("/play/{link_uuid}/skip")
async def skip_pacing(request, link_uuid):
    """Skip all per-card/per-bid reveals and advance to next decision point."""
    # Clear paused_after_play / paused_after_trick
    # Call engine.resume_ai() (existing method) which advances to next human turn
```

### Acceptance Criteria

- [ ] After human plays a card, each AI card appears one at a time via "Next"
- [ ] After the trick completes (4 cards shown), the trick-winner pause works
  as before
- [ ] "Skip" button advances past all remaining reveals to the next decision
- [ ] During auction, AI bids after the human's bid appear one at a time
- [ ] Bidding reveal includes the "settle" pause (existing behavior preserved)
- [ ] All existing tests pass — no regression in trick resolution or scoring
- [ ] Engine serialization/deserialization handles new `paused_after_play` field

### Validation Commands

```bash
# Tier 1
uv run python -m pytest tests/unit/hosted_play/test_engine.py -q
uv run python -m pytest tests/unit/hosted_play/test_routes.py -q
uv run python -m pytest tests/unit/hosted_play/test_state.py -q

# Tier 2
make check-quiet
```

### Risks

1. **Loner/Moon edge cases** — When the human sits out (loner by AI partner),
   all 4 cards in a trick are AI plays. Each must pause individually. Test this
   path explicitly.
2. **State serialization** — Adding `paused_after_play` to `HandState` requires
   updating `to_dict()` and `from_dict()`. Must be backward-compatible with
   existing serialized match states (default `False`).
3. **Test explosion** — Every test that calls `/next` and expects a full trick
   resolution will need updating. The tests currently assume one "Next" =
   complete trick. With pacing, one "Next" = one card.
4. **Skip route conflicts** — The `/skip` endpoint must correctly handle all
   pause states (paused_after_play, paused_after_trick, hidden auction,
   settle pause). Test each combination.
5. **Performance** — Each card reveal is a separate HTTP round-trip. On slow
   connections this could feel sluggish. Consider adding a ~2s delay in the
   template (CSS animation or JS setTimeout) rather than relying on network
   latency for pacing feel.

---

## File Ownership & Parallelism Matrix

| File | Stream A | Stream B | Stream D | Conflict? |
|------|----------|----------|----------|-----------|
| `web/routes.py` | No | Yes (tab routes) | Yes (/next, /skip) | **No** — different functions |
| `web/templates/base.html` | No | **Yes** (tab links) | No | Safe |
| `web/templates/game.html` | Possible | No | No | Safe |
| `web/templates/partials/game_board.html` | **Yes** (primary) | No | No | Safe |
| `web/templates/partials/contract_bar.html` | **Yes** | No | No | Safe |
| `web/templates/partials/score.html` | **Yes** | No | No | Safe |
| `web/templates/partials/trick.html` | **Yes** | No | No | Safe |
| `web/templates/partials/next_controls.html` | No | No | **Yes** | Safe |
| `web/templates/partials/hand_result.html` | No | No | No | Safe |
| `web/templates/partials/match_result.html` | No | No | No | Safe |
| `web/templates/history.html` | No | **Yes** (partial) | No | Safe |
| `web/templates/leaderboard.html` | No | **Yes** (partial) | No | Safe |
| `web/templates/comments.html` | No | **Yes** (partial) | No | Safe |
| `web/templates/guide.html` | No | **Yes** (partial) | No | Safe |
| `web/static/style.css` | **Yes** (layout) | Possible (tab active) | Possible (reveal) | **Minor overlap** — additive only |
| `web/static/game.js` | No | Yes (tab switching JS) | No | Safe |
| `src/.../hosted_play/engine.py` | No | No | **Yes** | Safe |
| `src/.../hosted_play/state.py` | No | No | **Yes** | Safe |

**Verdict:** All 3 active streams (A, B, D) can run in parallel. The only
shared file is `style.css` where all changes are additive (new classes, no
modifications to existing rules). Route handler changes target different
functions within `routes.py`.

---

## Recommended Lane Assignments

| Lane | Stream | Issues | Estimated Duration |
|------|--------|--------|-------------------|
| brws-author-a | A — UI cleanup | #2200 | 2-3h (3 PRs) |
| brws-author-b | B — Tab navigation | #2222, #2216 | 1.5-2h (1 PR) |
| — | C — Hand result | #2210 | **0h — already done** |
| brws-author-d | D — Card reveal | #2231 | 2-3h (2 PRs) |

**Merge order:** All streams are independent. Merge as they complete. Rebase
before PR creation to avoid stale-base conflicts from parallel streams.

---

## Issue Comments to Post

### #2210 — Close as completed
> This was fully implemented in PR #2253 (merged). The `_game_phase()` function
> now shows the hand result screen before the match-over screen, with a "See
> Match Results" CTA button. The flow is exactly as described in the user
> decision comment: last trick -> hand result -> Next -> match-over.

### #2200 — Implementation plan summary
> Shaping complete. The cleanup is decomposed into 3 PRs:
> 1. Deduplicate information (remove contract/declarer/tricks from score bar)
> 2. Phase-dependent markers with text labels (not icons)
> 3. Team color coding
>
> Scope-locked to the user's direction from comments. Full plan at
> `plans/sessions/2026-04-03_wave5_ux_shaping.md`.

### #2222 + #2216 — Implementation plan summary
> Both issues are resolved by converting tab navigation from `<a href>` to
> HTMX partial swaps. Single PR. Uses `HX-Request` header detection for
> partial vs full-page responses. Full plan at
> `plans/sessions/2026-04-03_wave5_ux_shaping.md`.

### #2231 — Implementation plan summary
> Server-side pacing (Approach A) with 2 PRs:
> 1. Per-card reveal — extends existing `paused_after_trick` pattern
> 2. Auction pacing + skip button
>
> Key risks: loner/moon edge cases, test updates, state serialization backward
> compatibility. Full plan at `plans/sessions/2026-04-03_wave5_ux_shaping.md`.

---

## Outcome

_To be filled after implementation._
