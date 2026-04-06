# UI/UX Wave/PR Plan — 2026-04-06

> **Task packet:** `bc7a61ff8881`
> **Drafted by:** analyst-b (shaping only — no implementation, no dispatch)
> **Status:** PROPOSAL — awaiting orchestrator + operator approval before dispatch
> **Delivery mode:** PR (durable plan artifact under `plans/sessions/`)
> **Branch:** `analyst/uiux-wave-plan-2026-04-06`

This plan packages every UI/UX item flagged during the 2026-04-06 session into
a single coherent wave the orchestrator can execute against the
`brws-author` pool. It is the implementation companion to the card-jitter
investigation report (`plans/sessions/2026-04-06_card_jitter_investigation.md`)
and adds two issues that surfaced after that report landed (#2539, #2545).

---

## 0. TL;DR

- **5 PRs**, all single-lane serial (`brws-author-a`), all `Track B` (NO
  auto-merge — operator AM proving required), spanning 3 issues:
  #2538 (jitter), #2539 (high-bid contract icon), #2545 (auction pane).
- **Strict serial order** required because every PR touches one or more of
  `web/static/style.css`, `web/templates/partials/bid_panel.html`, or
  `web/routes.py`. Parallel dispatch would cause merge conflicts.
- **Three jitter PRs** (UX-1, UX-2, UX-3) close #2538 in sequence; UX-3 is
  the only one that uses `Fixes #2538`. UX-1/UX-2 use `Refs #2538`.
- **UX-4** closes #2539 (high-bid display contract icon).
  **UX-5** closes #2545 (auction row differentiation + Pass button blue).
- **PR D** from the jitter report (trick-boundary choreography) is **out of
  scope for this wave** and is recorded in the deferred register for a
  follow-up issue.
- **Auto-merge:** **NO for all 5 PRs.** Every change is visible UI behavior
  the operator must eyeball locally before merge. The orchestrator must
  explicitly disable `gh pr merge --auto` and convert to draft on each PR as
  soon as it opens — see §6 and the 2026-04-06 09:47 auto-merge incident.

Refs #2538, #2539, #2545.

---

## 1. Operator constraints (from 2026-04-06 session, applied here)

The 2026-04-06 overnight plan (`plans/sessions/2026-04-06_overnight_run_plan.md`)
declared an operator policy that still governs this wave:

| Constraint | This wave's compliance |
|---|---|
| "All UI/UX improvements must be approved by user proving run before shipping" | Every PR is **NO auto-merge**. Operator merges manually after Playwright smoke + visual inspection. |
| "Test locally via Playwright; no Render deploys" | Every PR must include a Playwright smoke result in the body. No `render.yaml` touched. |
| "No new research" | UX-5 picks one design option (surface-elevation per #2545's Option B) without further research. Item 1 of #2521 (large text default) is **explicitly excluded**. |
| "Propose first" | This document is the proposal. Orchestrator must not dispatch until operator signs off. |
| Auto-merge incident: PRs #2531 + #2534 auto-merged 2026-04-06 09:47:55-09:47:59 despite NO policy | Defense in depth: PR body banner + draft-on-open + explicit operator merge. See §6 §AM mitigation. |

---

## 2. Wave summary

| PR | Title | Issue(s) | Lane | Size | Depends on | Auto-merge |
|----|-------|----------|------|------|------------|------------|
| **UX-1** | CSS cascade fix — `card--ai-delayed` longhand + compound rules | Refs #2538 | brws-author-a | S (~30 LoC, 1 file) | — | **NO** |
| **UX-2** | `ai_just_played` gate broadens to `paused_after_trick` + helper fallback | Refs #2538 | brws-author-a | S (~10 LoC + 1 unit test) | UX-1 merged | **NO** |
| **UX-3** | Slot reset fade animation + Playwright trick-boundary smoke | **Fixes #2538** | brws-author-a | S–M (~30 LoC + new pytest) | UX-2 merged | **NO** |
| **UX-4** | High Bid display — contract type suit icon | **Fixes #2539** | brws-author-a | S (~25 LoC, 2 files) | UX-3 merged | **NO** |
| **UX-5** | Auction pane row differentiation + Pass button blue | **Fixes #2545** | brws-author-a | M (~60 LoC, 2 files) | UX-4 merged | **NO** |

**File overlap matrix** (shows why this is a serial chain):

| PR \ File | `style.css` | `accessibility.css` | `bid_panel.html` | `trick.html` | `routes.py` | tests |
|---|---|---|---|---|---|---|
| UX-1 | ✏️ |  |  |  |  |  |
| UX-2 |  |  |  |  | ✏️ | ✏️ |
| UX-3 | ✏️ |  |  | (read) |  | ✏️ (new Playwright) |
| UX-4 | ✏️ |  | ✏️ |  | ✏️ | ✏️ |
| UX-5 | ✏️ | ✏️ | ✏️ |  |  | ✏️ (Playwright check) |

Three of the 5 PRs touch `style.css` and three touch `routes.py` /
`bid_panel.html`. This is the strict-serial constraint: dispatching any two
in parallel risks rebase conflicts that re-validate the entire chain.

---

## 3. Wave structure + dependencies

```
Wave 0  (operator approves this plan) ──────┐
                                             │
Wave 1  UX-1 (cascade fix)         ◄─────────┘
        brws-author-a → PR opens → operator proves → merge
                │
                ▼
Wave 2  UX-2 (ai_just_played gate)
        brws-author-a → PR opens → operator proves → merge
                │
                ▼
Wave 3  UX-3 (slot fade + Playwright smoke)  → CLOSES #2538
        brws-author-a → PR opens → operator proves → merge
                │
                ▼
Wave 4  UX-4 (high bid icon)                 → CLOSES #2539
        brws-author-a → PR opens → operator proves → merge
                │
                ▼
Wave 5  UX-5 (auction row + Pass button)     → CLOSES #2545
        brws-author-a → PR opens → operator proves → merge
                │
                ▼
        Wave complete; #2538/#2539/#2545 all closed
```

**Why a single lane?** Every PR rebases on the previous PR's `main`. If two
PRs ran in parallel on `brws-author-a` and `brws-author-b`, they would both
diverge from main and the second would hit a `style.css`/`bid_panel.html`
conflict during the mandatory pre-PR rebase (per `/start-task` Phase 2b).
Serializing on one lane eliminates that risk entirely and matches the lane's
existing scope-lock discipline.

**Why brws-author-a?** It is already the lane that historically takes
auction-form scope (#2521 items 2/3/4 → PR #2531). Choosing the same lane
gives the operator a single window to monitor and the lane retains warm
context across PRs. Alternative: brws-author-b also acceptable; the
orchestrator picks based on lane idle state at dispatch time.

**Parallelism opportunities (none, but documented for clarity):**
- UX-4 and UX-5 are functionally independent of the jitter chain (no animation
  interaction). However, both touch `bid_panel.html` and `style.css`, which
  the jitter chain also touches (UX-3's slot-reset-fade lives in `style.css`
  too). Parallel dispatch to a second brws lane saves wall time but creates
  guaranteed merge conflicts on every interleave. **Recommendation:
  reject the parallelism.** If wall time is critical, the operator can
  reorder Wave 4/5 ahead of Wave 1-3 (UX-4 and UX-5 do not depend on jitter
  fixes), but they must still ship serial within `brws-author-a`.

---

## 4. Per-PR packet skeletons

### 4.1 PR UX-1 — CSS cascade fix (Refs #2538)

| Field | Value |
|---|---|
| **Title** | `fix(web): card-played CSS cascade — longhand animation + compound winning/ai-delayed rule` |
| **Branch** | `fix/web-card-jitter-css-cascade` |
| **Lane** | `brws-author-a` |
| **Plan reference** | `plans/sessions/2026-04-06_card_jitter_investigation.md` §3 "Recommendation (primary, small)" Fix 1 |
| **Closes** | (none — `Refs #2538`) |
| **Depends on** | Operator approval of this plan |
| **Auto-merge** | **NO** (visible animation behavior change — gold pulse becomes visible on new trick lead) |

**Scope (declared):**
- `web/static/style.css` — only the rules at lines 245-250 (`.card--played`),
  260-265 (`.card--winning`), 267-281 (`.card--ai-delayed`), and 935-940
  (`trick-slot--winner card`)
- No other files

**Implementation summary** (per the jitter report §3 Fix 1):
1. Replace the `.card--ai-delayed { animation: ... }` shorthand with longhand
   `animation-name`/`animation-duration`/`animation-timing-function`/
   `animation-fill-mode` properties so future compound rules can extend
   instead of override.
2. Add a compound `.card--winning.card--ai-delayed` rule with chained
   `animation-name: ai-card-reveal, winning-card-pulse;` and matching
   longhand lists for duration/delay/iteration-count/fill-mode.
3. Add a compound `.trick-slot--winner .card--ai-delayed` rule per Risk R4
   in the jitter report — the descendant selector
   `.trick-slot--winner .card` has higher specificity (0,2,0) than
   `.card--ai-delayed` (0,1,0) and would otherwise win the cascade for the
   trick-closing card.
4. Add baseline transitions to `.card--played` so the entry of any played
   card (human or AI) blends rather than pops:
   ```css
   .card--played {
       transition: transform 0.2s ease, box-shadow 0.2s ease,
                   border-color 0.2s ease, opacity 0.2s ease;
   }
   ```
   Scope the transition to `.card--played` (not the base `.card`) per Risk
   R1 in the jitter report — adding `opacity` transition to all `.card`
   elements would lag hand-card selection feedback.

**Acceptance criteria:**
- `getComputedStyle(card_div, 'animation-name')` on a card with both
  `.card--winning` and `.card--ai-delayed` returns
  `ai-card-reveal, winning-card-pulse` (not just `ai-card-reveal`).
- The same assertion on a card under `.trick-slot--winner` returns the
  composed list (per R4 fix).
- `.card--played` elements have a non-zero `transition-duration` for
  `opacity`.
- No regression on `.card--legal` hover responsiveness (manual eyeball).
- Mobile viewport unchanged at `@media (max-width: 600px)`.

**Validation:**
- **Tier 1 targeted:**
  ```bash
  uv run python -m pytest tests/integration/web/ -v -k "css or style or animation"
  ```
  (No existing pytest covers CSS animation properties; if no tests match,
  skip Tier 1 — Tier 2 + Playwright cover this PR.)
- **Tier 2:**
  ```bash
  make check-gated
  ```
- **Playwright smoke (manual, attach result to PR body):**
  - `make web` on free port (default 8000)
  - `mcp__playwright__browser_navigate http://localhost:8000/play/<test-uuid>`
  - Reach a state where AI just played a winning lead card
  - `mcp__playwright__browser_evaluate` → `getComputedStyle(card,
    'animation-name')` returns the comma-separated list
  - Take screenshot at `data/local_smoke/UX-1/winning-lead-after-ai.png`
    (gitignored path)

**Known risks** (cross-reference jitter report §5):
- **R1** — adding the opacity transition could affect hand cards if the
  selector accidentally widens. Scope strictly to `.card--played`.
- **R2** — the chained pulse-after-reveal delays the gold glow by 750 ms.
  This is intentional polish; if operator dislikes, the follow-up is to
  reduce `--ai-card-delay` to 0.5s.
- **R4** — the `.trick-slot--winner .card--ai-delayed` compound is needed.
  Verify all four slot positions render the composed animation.
- **R10** — mobile-viewport unchanged but smoke-test at iPhone 13 viewport.

**PR body must include the no-auto-merge banner (see §4.6 boilerplate).**

---

### 4.2 PR UX-2 — `ai_just_played` gate broadening + helper fallback (Refs #2538)

| Field | Value |
|---|---|
| **Title** | `fix(web): broaden ai_just_played gate to paused_after_trick + helper fallback` |
| **Branch** | `fix/web-ai-just-played-trick-boundary` |
| **Lane** | `brws-author-a` |
| **Plan reference** | `plans/sessions/2026-04-06_card_jitter_investigation.md` §3 Fix 2 |
| **Closes** | (none — `Refs #2538`) |
| **Depends on** | UX-1 merged (file conflict avoidance on `routes.py`/CSS interactions) |
| **Auto-merge** | **NO** (changes which cards animate on the trick-closing AI play — visible behavior) |

**Scope (declared):**
- `web/routes.py` — only the helper at lines 282-287 (`_last_played_seat`)
  and the context computation at lines 575-584 (`ai_just_played` /
  `last_played_seat`)
- `tests/unit/web/` — at least one new unit test covering both pause states
  (path determined by lane after grepping existing routes-test conventions;
  if no `tests/unit/web/` exists, fall back to `tests/integration/hosted_play/`)

**Implementation summary** (per jitter report §3 Fix 2):

1. **Routes — broaden the gate:**
   ```python
   ctx["ai_just_played"] = (
       hand.phase == "trick_play"
       and (hand.paused_after_play or hand.paused_after_trick)
       and last_seat is not None
       and last_seat != HUMAN_SEAT
   )
   ```
2. **Routes — helper fallback at `_last_played_seat`:**
   - During `paused_after_trick`, the active trick has been moved to
     `completed_tricks` and `hand.current_trick.plays` may be empty.
   - Add a fallback: if the active trick has no plays AND
     `hand.completed_tricks` is non-empty, return
     `hand.completed_tricks[-1].plays[-1][0]` (the seat of the last play in
     the most recent completed trick).
3. **Unit test:**
   - Construct a hand state in `paused_after_trick` with a known
     completed trick and no active trick plays.
   - Assert `_last_played_seat(hand)` returns the 4th-card seat.
   - Assert `_build_game_context(...)` returns
     `ai_just_played=True` for that state when the 4th-card seat is an AI
     seat.
   - Also cover `paused_after_play` to ensure no regression.

**Acceptance criteria:**
- New unit test passes.
- The trick-closing AI card (4th card) renders with `card--ai-delayed`
  (verifiable via Playwright `getAttribute('class')` containing
  `card--ai-delayed`).
- Existing routes tests still pass.

**Validation:**
- **Tier 1 targeted:**
  ```bash
  uv run python -m pytest tests/unit/web/ tests/unit/hosted_play/ tests/integration/hosted_play/ -v
  ```
- **Tier 2:**
  ```bash
  make check-gated
  ```
- **Playwright smoke:**
  - Play one full trick to the 4th card via the local hosted app
  - `mcp__playwright__browser_evaluate` → confirm the 4th-card slot's
    inner div has class `card--ai-delayed` for at least 100 ms post-swap
  - Screenshot at `data/local_smoke/UX-2/trick-closing-ai-card.png`

**Known risks** (cross-reference jitter report §5):
- **R3** — `_last_played_seat` could return `None` or the wrong seat
  during `paused_after_trick`. The helper fallback covers this; the unit
  test must lock it.
- **R6** — one-frame gap during morph mitigated by UX-1's
  `.card--played` transition. UX-2 alone does not introduce a new gap.

**PR body must include the no-auto-merge banner.**

---

### 4.3 PR UX-3 — Slot reset fade + Playwright smoke (Fixes #2538)

| Field | Value |
|---|---|
| **Title** | `fix(web): card-slot empty fade + Playwright trick-boundary smoke (Fixes #2538)` |
| **Branch** | `fix/web-slot-reset-fade-2538` |
| **Lane** | `brws-author-a` |
| **Plan reference** | `plans/sessions/2026-04-06_card_jitter_investigation.md` §3 Fix 3 + §9 |
| **Closes** | **`Fixes #2538`** (the issue closes when this PR merges; UX-1 + UX-2 are prerequisites) |
| **Depends on** | UX-2 merged |
| **Auto-merge** | **NO** (adds a new animation; needs operator visual proving) |

**Scope (declared):**
- `web/static/style.css` — only the `.card-slot--empty` rule and a new
  `@keyframes slot-reset-fade` block
- `tests/integration/web/` — new file `test_card_animations.py` (or extend
  existing if one exists; lane determines after grepping)
- No template changes — the animation fires automatically on every render
  where the slot class is `card-slot--empty`

**Implementation summary** (per jitter report §3 Fix 3):

1. **CSS:**
   ```css
   .card-slot--empty {
       /* existing layout rules ... */
       animation: slot-reset-fade 0.2s ease-out both;
   }

   @keyframes slot-reset-fade {
       0%   { opacity: 0.3; transform: scale(0.95); }
       100% { opacity: 1;   transform: scale(1); }
   }
   ```
2. **Playwright smoke test (new):**
   - File: `tests/integration/web/test_card_animations.py`
   - Test: `test_trick_boundary_no_layout_jitter`
   - Boots a local FastAPI test client (or uses existing
     `tests/integration/hosted_play/conftest.py` fixtures), navigates to a
     trick-result screen, clicks `Next`, asserts that no card-slot or
     trick-area element has a layout shift greater than **4 px** within
     **300 ms** post-swap. (Use Playwright's
     `page.evaluate('performance.measure(...)')` and a
     `LayoutShiftAttribution`-based check, or fall back to comparing
     `getBoundingClientRect()` snapshots before/after.)
3. **`prefers-reduced-motion` consideration:**
   - The existing `@media (prefers-reduced-motion: reduce)` block at
     `web/static/style.css:3118` already covers `.card--winning` and
     `.trick-slot--winner .card`. Extend it to set
     `.card-slot--empty { animation: none; }` per Risk R5.

**Acceptance criteria:**
- The new Playwright test passes locally and in CI.
- Visual smoke (operator AM): trick-boundary transition is perceptibly
  smoother than current main (subjective — operator confirms).
- Mobile viewport unchanged.
- `prefers-reduced-motion: reduce` disables the new animation.
- The full chain (UX-1 + UX-2 + UX-3 merged) eliminates all 8 jitter
  sources from the report's §1 summary table EXCEPT items 2 and 8
  (hand-card cascade and winner-glow stop), which are out of scope and
  go to the deferred register.

**Validation:**
- **Tier 1 targeted:**
  ```bash
  uv run python -m pytest tests/integration/web/test_card_animations.py -v
  ```
- **Tier 2:**
  ```bash
  make check-gated
  ```
- **Playwright smoke:**
  - Full hand walkthrough — 10 tricks, with screenshots at:
    - `data/local_smoke/UX-3/trick-boundary-before-fade.png` (mid-fade frame)
    - `data/local_smoke/UX-3/trick-boundary-after-fade.png` (settled frame)
  - Mobile viewport (iPhone 13 emulation) — `data/local_smoke/UX-3/mobile.png`
  - `prefers-reduced-motion: reduce` — `data/local_smoke/UX-3/reduced-motion.png`
    (animation disabled)

**Known risks** (cross-reference jitter report §5):
- **R5** — the slot-reset-fade fires on initial page load too (acceptable
  per the jitter report; matches polish elsewhere).
- **R9** — Playwright animation tests are flaky. The 4 px / 300 ms
  threshold is intentionally generous. If the test flakes in CI, retry
  once before failing the lane.

**PR body must include the no-auto-merge banner AND a "How to prove the
fix" checklist (see §4.6).**

---

### 4.4 PR UX-4 — High Bid display contract type icon (Fixes #2539)

| Field | Value |
|---|---|
| **Title** | `fix(web): show contract type suit icon next to high bid (Fixes #2539)` |
| **Branch** | `fix/web-high-bid-contract-icon-2539` |
| **Lane** | `brws-author-a` |
| **Plan reference** | This plan §4.4; issue body of #2539 |
| **Closes** | **`Fixes #2539`** |
| **Depends on** | UX-3 merged (file overlap on `bid_panel.html`/CSS) |
| **Auto-merge** | **NO** (visible UI change — operator must verify the icon renders correctly with red/light color coding for all 6 contract types) |

**Scope (declared):**
- `web/templates/partials/bid_panel.html` — only the "Current high bid"
  block at lines 86-96
- `web/routes.py` — `_build_game_context` at lines 605-620 (add a new
  context variable `current_high_bid_contract`)
- Possibly `web/static/style.css` — only if a new utility class is needed
  (the existing `.suit-icon` and `.suit-icon--{hearts,diamonds,spades,clubs}`
  classes at lines 3074-3087 should be reused, NO new color rules)
- `tests/unit/web/` or `tests/unit/hosted_play/` — at least one new test
  covering the new context variable for each contract type

**Implementation summary:**

1. **Routes — new context variable:**
   The engine already tracks `hand.contract_type` ("suit" / "high" / "low")
   and `hand.trump` (one of "S", "H", "D", "C") at the high bid (see
   `src/bid_euchre/hosted_play/engine.py` line 794-795). Pass them to
   the partial as a single normalized variable:
   ```python
   if not _has_hidden_auction(hand) and hand.current_high_bid > 0:
       if hand.contract_type == "suit" and hand.trump is not None:
           ctx["current_high_bid_contract"] = hand.trump  # "S"|"H"|"D"|"C"
       elif hand.contract_type == "high":
           ctx["current_high_bid_contract"] = "HIGH"
       elif hand.contract_type == "low":
           ctx["current_high_bid_contract"] = "LOW"
       else:
           ctx["current_high_bid_contract"] = None
   else:
       ctx["current_high_bid_contract"] = None
   ```
2. **Template — render the icon:**
   - Reuse the `suit_symbols` map already defined at line 12.
   - Reuse the `.suit-icon suit-icon--{hearts,diamonds,spades,clubs}` CSS
     class set at `web/static/style.css` lines 3074-3087 (already
     color-coded red for hearts/diamonds, light for spades/clubs).
   - Render the line as:
     ```jinja
     {% if current_high_bid > 0 %}
     <p class="bid-info" aria-live="polite">
         High Bid: {{ current_high_bid }}
         {% if current_high_bid_contract in ["S", "H", "D", "C"] %}
             <span class="suit-icon suit-icon--{{ {'S':'spades','H':'hearts','D':'diamonds','C':'clubs'}[current_high_bid_contract] }}">{{ suit_symbols[current_high_bid_contract] }}</span>
         {% elif current_high_bid_contract == "HIGH" %}
             <span class="contract-label">Hi</span>
         {% elif current_high_bid_contract == "LOW" %}
             <span class="contract-label">Lo</span>
         {% endif %}
         {{ bid_type_labels.get(bid_type|default("regular"), "") }}
         {% if bid_type|default("regular") == "moon" %}
             <span class="bid-type-badge bid-type-badge--moon">Moon</span>
         {% elif bid_type|default("regular") == "loner" %}
             <span class="bid-type-badge bid-type-badge--loner">Loner</span>
         {% endif %}
     </p>
     {% endif %}
     ```
   - Note: `Hi`/`Lo` labels match the wording in #2539's "Expected" block
     (`High Bid: 6 Hi`, `High Bid: 6 Lo`). For Moon contracts the existing
     `bid_type_labels` block already produces `" Moon"` so no extra rule is
     needed.
3. **CSS — minimal additions only if missing:**
   - The existing `.suit-icon--*` rules are sufficient. **Do not add new
     color rules.**
   - If `.contract-label` is not already defined, add a lightweight rule
     in `web/static/style.css` (single 3-line block with neutral color);
     otherwise reuse.
4. **Unit test:**
   - Construct hand states for each of the 6 contract values (S, H, D, C,
     HIGH, LOW) plus the "no high bid yet" case.
   - Assert `_build_game_context(...)["current_high_bid_contract"]` matches
     expected.
   - Optionally Jinja-render the partial against a fixture and assert the
     `<span class="suit-icon suit-icon--hearts">♥</span>` substring is in
     the output for the hearts case.

**Acceptance criteria:**
- The "Current high bid" line displays the contract icon for all 6
  contract types.
- Hearts and diamonds render in red; spades and clubs render in light/white
  on the dark surface (matches Cards Played log per #2505).
- The `Hi`/`Lo` label is displayed for `high`/`low` contracts.
- The Moon and Loner badges still render correctly (no regression to
  #2531).
- No regression on the bid form rendering on mobile viewport.

**Validation:**
- **Tier 1 targeted:**
  ```bash
  uv run python -m pytest tests/unit/hosted_play/ tests/unit/web/ -v -k "bid_panel or high_bid or context"
  ```
- **Tier 2:**
  ```bash
  make check-gated
  ```
- **Playwright smoke:**
  - Reach an auction state where one player has bid 6♠
  - Screenshot at `data/local_smoke/UX-4/high-bid-spades.png`
  - Repeat for hearts (`high-bid-hearts.png`) and HIGH
    (`high-bid-high.png`)
  - Mobile viewport screenshot

**Known risks:**
- **R-UX4-A** — the contract type column is `hand.contract_type` which is
  `None` until the auction starts having bids. Guard the new context var
  with `current_high_bid > 0` to avoid stale display.
- **R-UX4-B** — `.suit-icon--clubs` color rule applies the same `--color-text`
  as `.suit-icon--spades`. On `accessibility.css` (high-contrast theme), if
  any override exists, ensure it still resolves to a visible color. Verify
  Playwright with the high-contrast media query or system preference.
- **R-UX4-C** — the Moon/Loner badge logic must remain unchanged. Run a
  separate Playwright pass against a Moon-bid auction to confirm the
  badge still renders.

**PR body must include the no-auto-merge banner.**

---

### 4.5 PR UX-5 — Auction pane row differentiation + Pass button blue (Fixes #2545)

| Field | Value |
|---|---|
| **Title** | `fix(web): auction row surface elevation + Pass button blue (Fixes #2545)` |
| **Branch** | `fix/web-auction-pane-rows-pass-blue-2545` |
| **Lane** | `brws-author-a` |
| **Plan reference** | This plan §4.5; issue body of #2545 |
| **Closes** | **`Fixes #2545`** |
| **Depends on** | UX-4 merged (overlap on `bid_panel.html`/CSS) |
| **Auto-merge** | **NO** (visible UI change — operator must approve the chosen palette option) |

**Scope (declared):**
- `web/templates/partials/bid_panel.html` — minor (may add `.bid-row` class
  variants like `bid-row--type` if the implementation chooses
  attribute-based styling, but the file is mostly already structured)
- `web/static/style.css` — `.bid-row` block at lines 1229-1245, plus a
  new "auction surface" block
- `web/static/css/accessibility.css` — `.pass-btn` block at lines 299-318
  (recolor to blue per #2545 recommendation)
- `tests/integration/web/` — extend `test_card_animations.py` (or new file)
  with a single Playwright assertion that the three rows have distinct
  computed-style backgrounds and the Pass button has a blue border or fill

**Implementation summary:**

The issue gives the implementer two options. **Recommendation: pick
Option B (subtle surface elevation)** for both palette harmony and to
avoid color-coding overload (the palette already carries suit colors,
team colors, and the gold winning glow).

1. **Row differentiation — surface elevation:**
   - Each `.bid-row` gets:
     - `background: var(--color-surface-light)` (existing CSS variable)
     - `border: 1px solid rgba(255, 255, 255, 0.08)`
     - `border-radius: 6px`
     - `padding: 0.5rem 0.75rem`
   - Add `.bid-row` margin-bottom of `0.5rem` so the rows visually separate.
   - Add a focus-within accent stripe on the left edge:
     ```css
     .bid-row:focus-within {
         border-left: 3px solid var(--color-legal-glow);
         padding-left: calc(0.75rem - 2px);
     }
     ```
   - **Do not add per-row accent colors** — the 2026-04-06 palette already
     uses cyan for legal-glow, gold for winning, red for hearts, and team
     colors for score bars. Per-row colors would clash.
   - Mobile viewport: keep the same elevation; the touch target sizes are
     unchanged from #2531.

2. **Pass button blue (outlined first attempt):**
   - In `web/static/css/accessibility.css` lines 299-318, change
     `.pass-btn`:
     - `border: 2px solid var(--color-pass-blue, #1565c0)` (new var or
       reuse `#1565c0` from the existing `.btn--see-results` gradient at
       `web/static/style.css` line 1671)
     - `color: var(--color-pass-blue, #1565c0)`
     - `background: transparent`
   - Hover state:
     - `background: rgba(21, 101, 192, 0.12)`
     - `color: #ffffff`
   - **Do NOT introduce a new `--color-blue` CSS variable in
     `:root`** — reuse `#1565c0` literal in the rule, OR add
     `--color-pass-blue: #1565c0;` to the existing `:root` block at
     `web/static/style.css:14` (single line addition). The orchestrator's
     review coordinator may flag a new variable; pre-empt by adding it
     where existing color vars live.
   - **Reject filled blue as the first attempt.** Per #2545 the implementer
     should try outlined first and only fall back to filled if mobile
     visual smoke shows the outline reads as ghost/disabled. Document the
     decision in the PR body.

3. **Test (Playwright):**
   - Extend `tests/integration/web/test_card_animations.py` with a new
     test `test_auction_panel_visual_distinction`:
     - Reach the auction phase
     - `getComputedStyle('.bid-row').background` differs from the panel
       background AND between adjacent rows
     - `getComputedStyle('.pass-btn').borderColor` is the blue value
     - Mobile viewport — same assertions

**Acceptance criteria:**
- New player can immediately see Type/Bid/Contract as three distinct
  configuration controls (qualitative; operator confirms in AM).
- Pass button reads as a clear primary action, distinct from Submit Bid.
- No regression to #2531: single-line layout preserved, full-width Pass
  button preserved, null contract default preserved, Submit Bid still
  disabled until contract picked.
- Mobile viewport (iPhone 14 Pro emulation) — all controls remain tap-target
  ≥ 44px (per `accessibility.css:103-106`).
- No conflict with team-color blue in the score bar (verify by viewing the
  score bar and Pass button in the same screenshot).

**Validation:**
- **Tier 1 targeted:**
  ```bash
  uv run python -m pytest tests/integration/web/test_card_animations.py -v -k "auction or pass"
  ```
- **Tier 2:**
  ```bash
  make check-gated
  ```
- **Playwright smoke:**
  - Auction view with all 3 rows visible — `data/local_smoke/UX-5/auction-rows.png`
  - Same view at iPhone 14 Pro viewport — `data/local_smoke/UX-5/auction-rows-mobile.png`
  - Pass button hover state — `data/local_smoke/UX-5/pass-button-hover.png`
  - Score bar + bid panel in same frame (color-clash check) —
    `data/local_smoke/UX-5/score-and-bid.png`

**Known risks:**
- **R-UX5-A** — Pass button blue clashes with team-color blue used in the
  score bar (`#1565c0` is the same hue family as the hosted app's
  Team A color). Mitigation: the blue is an outline, not a fill, and is
  visually anchored to the form rather than the score bar. Smoke-test by
  viewing both elements in the same screenshot.
- **R-UX5-B** — `.bid-row` background change interacts with the
  `.bid-row label` styling (currently muted-text color). If the surface
  elevation makes the label unreadable, raise the label color to
  `var(--color-text)`.
- **R-UX5-C** — `accessibility.css` has its own focus-visible rules at
  line 67-70 for `.pass-btn`. The new `border: 2px solid blue` must not
  conflict with the focus-visible outline. Test by tabbing to Pass.
- **R-UX5-D** — `prefers-reduced-motion` is unaffected (no animation
  changes), but `prefers-color-scheme: light` (if ever supported) is
  unaffected; the hosted app is dark-only so no light-theme regression
  testing required.

**PR body must include the no-auto-merge banner AND a "Design choice"
note explaining whether outlined or filled blue was chosen and why (per
#2545's "implementer should mock both up and pick" guidance).**

---

### 4.6 PR body boilerplate footer (apply to all 5 PRs)

Every PR in this wave must include the following footer block in the PR
body. The orchestrator should pre-populate the packet with this text.

```markdown
---

> **CRITICAL: Do not run `gh pr merge` on this PR.**
>
> This is a Track B UI/UX change. Per the 2026-04-06 UI/UX wave plan
> (`plans/sessions/2026-04-06_uiux_wave_plan.md` §6 Auto-merge policy
> matrix), this PR is **NO auto-merge**. The operator must:
>
> 1. Pull the branch locally: `gh pr checkout <N>`
> 2. Run `make web` and reach the affected screen
> 3. Verify the change matches the acceptance criteria above
> 4. Merge manually: `gh pr merge <N> --squash`
>
> **Auto-merge incident reference:** PRs #2531 and #2534 auto-merged
> 2026-04-06 09:47:55-09:47:59 despite a NO policy. The orchestrator
> runbook now requires explicit `gh pr ready --undo <N>` (convert to
> draft) on every Track B PR as soon as it opens.

## Implementation Handoff Protocol (per `.claude/CLAUDE.md`)

This packet was prepared by analyst-b. The receiving lane MUST follow the
full Implementation Handoff Protocol before writing code:

1. **Refresh plan context** — read `plans/sessions/2026-04-06_uiux_wave_plan.md`
   §<your-PR-section> AND
   `plans/sessions/2026-04-06_card_jitter_investigation.md` §3 (if your PR
   is UX-1, UX-2, or UX-3).
2. **Draft execution plan** inline in your lane (file scope, test plan,
   commit sequence).
3. **Spawn at least one reviewer agent** to review the execution plan
   before any source edits.
4. **Create a TUI task list** (`TaskCreate`) for implement → validate →
   commit → push → PR.
5. **Assess parallelism** — this PR is single-lane serial; no sub-tasks
   should fan out to other lanes.
6. **Execute end to end autonomously** through `gh pr create`.
   **Do NOT run `gh pr merge`.**
7. Include `## Validation Performed` evidence in the PR body — the
   commands you ran, their output, and the Playwright screenshot
   filenames.
```

---

## 5. Wave ordering + gates

### Strict serial dependency chain

```
UX-1 ──► UX-2 ──► UX-3 ──► UX-4 ──► UX-5
                  │
                  └─ closes #2538
                              │
                              └─ closes #2539
                                          │
                                          └─ closes #2545
```

### Gate per wave step

| Step | Gate | What proves the gate |
|---|---|---|
| Operator approves this plan | Plan PR merged | `gh pr view <plan-PR>` shows MERGED |
| UX-1 dispatch | Gate above + brws-author-a idle | `lane-status` shows `brws-author-a` clean on `main` |
| UX-1 PR opened | Lane completes implementation, runs Tier 2, opens PR | `gh pr view UX-1` exists |
| UX-1 reviewed | Review coordinator verdict `passed`, CI green | `gh pr checks UX-1` all green |
| UX-1 proven | Operator runs Playwright + visual smoke locally | Operator confirmation in lane or PR comment |
| UX-1 merged | Operator runs `gh pr merge --squash` | `gh pr view UX-1` shows MERGED |
| UX-2 dispatch | UX-1 merged + brws-author-a idle | (same shape as above for UX-2..5) |
| ... | ... | ... |
| UX-5 merged + #2545 closed | Wave complete | `gh issue list --state open --search '#2538 OR #2539 OR #2545'` returns empty |

**Maximum wall time estimate:** assuming each PR takes ~45 min implement +
~20 min review coordinator + ~10 min operator proving + ~5 min merge =
~80 min per PR × 5 PRs = **~6.5 hours** of serial wall time. The wave is
deliberately not parallelized to keep the file-conflict risk at zero.

### Operator proving boundary (per PR)

Each PR's Playwright smoke evidence must include, at minimum:

- 1 screenshot per acceptance criterion checkpoint
- 1 mobile-viewport screenshot
- A console-message dump (`mcp__playwright__browser_console_messages`)
  with no `error` or `warning` entries

These artifacts live under `data/local_smoke/<packet-id>/` (gitignored
path). The PR body cites the filenames and a short caption.

---

## 6. Auto-merge policy matrix

| PR | Track | Change class | Auto-merge | Rationale |
|---|---|---|---|---|
| UX-1 | B | CSS cascade fix | **NO** | Visible animation behavior change (gold pulse becomes visible on new trick lead — per jitter report Bug A fix) |
| UX-2 | B | Routes context + helper | **NO** | Visible behavior change (4th-card AI play now animates) |
| UX-3 | B | New animation + Playwright test | **NO** | Visible animation change at every trick boundary |
| UX-4 | B | Template + routes + tests | **NO** | New visible UI element (suit icon next to high bid) |
| UX-5 | B | CSS + template + tests | **NO** | Visible style change to the auction form + Pass button |

**Default for this entire wave: NO auto-merge for everything.** Every PR
changes user-visible behavior in the hosted browser app, and per the
operator policy "all UI/UX improvements must be approved by user proving
run before shipping."

### Auto-merge incident mitigation (mandatory orchestrator runbook)

The 2026-04-06 09:47 incident (PRs #2531 and #2534 auto-merged within 4
seconds of CI passing despite their NO-auto-merge banners) demonstrates
that PR-body banners alone are insufficient. For this wave the
orchestrator MUST do **all four** of the following on every PR as soon as
it opens:

1. **Convert PR to draft immediately on open:**
   ```bash
   gh pr ready --undo <N>
   ```
   Drafts cannot be auto-merged by GitHub even if the review coordinator
   posts `success`. This is the primary defense.

2. **Disable auto-merge if it was set:**
   ```bash
   gh pr merge <N> --disable-auto
   ```
   Idempotent; safe to run even if auto-merge was never enabled.

3. **Add the no-auto-merge label** (if a `do-not-merge` label exists in the
   repo; otherwise create one as part of the wave's first PR). Branch
   protection rules can be set to require this label's *absence* for merge.

4. **Post the proving checklist as a PR comment** so the operator's GitHub
   notification mentions the specific Playwright + visual checks they
   need to run.

**The orchestrator must verify all 4 mitigations are in place before
moving on to the next PR's dispatch.** A `gh pr view <N> --json
isDraft,autoMergeRequest` check satisfies #1 and #2.

---

## 7. Implementation handoff protocol (boilerplate, applied per packet)

Every author-lane packet in this wave must obey `.claude/CLAUDE.md`
"Implementation Handoff Protocol" verbatim. The packet body contains the
text from §4.6 above, which the receiving lane echoes back before
implementation begins. The lane must:

1. **Refresh plan context** (read this plan + the jitter investigation
   report if applicable, before any source edits).
2. **Draft execution plan** in the lane's worktree as a TUI task
   description or scratch markdown — not a free-form intent.
3. **Spawn a plan reviewer agent** (per `.claude/CLAUDE.md`); the
   reviewer's role is to flag hidden scope creep or missed acceptance
   criteria.
4. **Create a TUI task list** for the lane's own bookkeeping.
5. **Assess parallelism**; for this wave the answer is "no parallelism —
   single-lane serial" and the lane confirms.
6. **Execute end-to-end** through `gh pr create`. The lane MUST NOT run
   `gh pr merge` on its own PR.
7. **Validation Performed** block in the PR body lists exact commands and
   their outputs, plus screenshot filenames.

The orchestrator's `start-task` skill packet wrapper already includes
these steps; this plan just makes the packet-level requirement explicit so
no PR ships without the discipline.

---

## 8. Risk register (wave-wide)

| # | Risk | Severity | PR | Mitigation |
|---|---|---|---|---|
| RW-1 | CSS regression on mobile viewports — any of UX-1, UX-3, UX-5 changes a `style.css` rule that affects mobile layout | MEDIUM | UX-1, UX-3, UX-5 | Each PR's Playwright smoke includes an iPhone 14 Pro / iPhone 13 viewport screenshot. The acceptance criteria explicitly require "mobile viewport unchanged." |
| RW-2 | Animation timing race with auto-advance (PR #2486) — UX-1 + UX-2 change which cards animate, and the auto-advance timer at 850 ms could fire mid-reveal | MEDIUM | UX-1, UX-2 | UX-1's compound rule sequences the gold pulse to start AFTER the 750 ms reveal; auto-advance at 850 ms gives a 100 ms buffer (per existing `web/routes.py:600` constant). UX-2 only broadens the gate; it doesn't change timing. The Playwright smoke covers this by playing 2 full tricks. |
| RW-3 | New compound rules collide with `prefers-reduced-motion` media query | LOW | UX-1, UX-3 | The existing `@media (prefers-reduced-motion: reduce)` block at `style.css:3118` is extended in UX-3 to cover `.card-slot--empty`. UX-1 inherits the existing `.card--winning { animation: none; }` rule. Verify in Playwright with `page.emulateMedia({reducedMotion: 'reduce'})`. |
| RW-4 | Pass button blue (UX-5) conflicts with team-color blue in the score bar | MEDIUM | UX-5 | Pass button uses an OUTLINE blue (border + text), the score bar uses a FILL blue (background). The visual distinction is treatment, not hue. Smoke-test by capturing both elements in one screenshot. If clash persists, fall back to a different blue shade (e.g., `#0d47a1` instead of `#1565c0`). |
| RW-5 | Merge conflicts if any of the 5 PRs land out of order | HIGH | All | **Eliminated by single-lane serial dispatch.** Each PR rebases on `main` immediately before opening, and the next PR cannot start until the previous is merged. The orchestrator must enforce this — do NOT dispatch UX-2 until UX-1 is MERGED, etc. |
| RW-6 | Auto-merge incident recurs (a Track B PR auto-merges before operator proving) | HIGH | All | Four-layer defense in §6 §"Auto-merge incident mitigation" — convert to draft, disable auto-merge, label, comment. Orchestrator verifies all four before moving on. |
| RW-7 | UX-3's Playwright smoke test (4 px / 300 ms layout shift) is flaky in CI | LOW | UX-3 | Test retries once before failing. The threshold is generous (4 px) — most legitimate fixes will pass with margin. Document the threshold in the test docstring so future tightening is intentional. |
| RW-8 | UX-4's new `current_high_bid_contract` context variable causes a Jinja `UndefinedError` on partials that don't get the new var (e.g., the bid_recap or comments partials) | LOW | UX-4 | The variable is only consumed in `bid_panel.html`. Other partials don't reference it. The route handler always sets it (to `None` when no high bid). Add a defensive `{% if current_high_bid_contract is defined %}` guard if the lane is uncertain. |
| RW-9 | UX-5 row surface elevation reduces contrast on `.bid-row label` text (currently `--color-text-muted`) | LOW | UX-5 | If smoke-test shows poor readability, raise the label color to `var(--color-text)` in the same PR. |
| RW-10 | Playwright MCP browser flakes mid-smoke — screenshot or evaluate fails | LOW | All | Screenshots are evidence, not gating. If Playwright fails, the lane records the failure in the PR body and marks the smoke as `degraded`. The operator decides during AM proving whether to merge or revert. |
| RW-11 | The wave's serial nature means a single-PR failure blocks the entire chain | MEDIUM | All | The orchestrator can re-dispatch any failed PR (idempotent task packets). UX-4 and UX-5 are functionally independent of UX-1/2/3 — if the jitter chain blocks, the orchestrator MAY reorder to ship UX-4/5 first (still serial, still single-lane). Document the reorder in the AM handoff. |
| RW-12 | UX-2 unit test for `_last_played_seat` uses a `MatchState` fixture that does not match the actual engine's state machine | LOW | UX-2 | Lane reads `src/bid_euchre/hosted_play/engine.py` lines 728-740 (the `_advance_ai` branch that sets `paused_after_trick`) and constructs the fixture by calling the actual `engine.submit_human_card` / `engine.advance_ai` methods rather than synthesizing a state from scratch. |
| RW-13 | UX-4's icon span breaks the `aria-live="polite"` announcement (screen reader reads "♥" as nothing or as "heart symbol") | LOW | UX-4 | The icon is supplementary; keep the textual "High Bid: 6" content as the screen reader's anchor. Add `aria-hidden="true"` on the `<span class="suit-icon">` to prevent double-announcement. |

---

## 9. Deferred items register

The following work is **explicitly out of scope** for this wave but is
recorded here so the orchestrator can file follow-up issues if it doesn't
already track them.

| # | Item | Why deferred | Reopens when |
|---|---|---|---|
| D1 | **PR D — trick-boundary choreography** (the secondary recommendation in jitter report §3) | Heavier lift (touches `web/static/game.js`, requires `htmx:beforeSwap` hook). The primary chain (UX-1/2/3) should resolve the perceived jitter without it. | After UX-3 merges + operator confirms residual choreography stutter is still visible. File as follow-up issue referencing #2538. |
| D2 | **#2521 item 1 — large text as default** | Explicitly labeled "research/feasibility task" in the issue body. Operator's "no new research" directive applies. | Operator lifts research freeze. |
| D3 | **Hand-card cascade animation** (when human plays a card and the remaining 9 reshuffle in place) | Out of scope per jitter report §5 R8 — low priority, the human's own action and the "pop" feels responsive rather than jittery. | Operator surfaces it as a polish complaint. |
| D4 | **`prefers-reduced-motion` full audit** for all card animations (not just the new ones) | Audit-flavored task; UX-1/3 cover their own additions but the existing `winner-card-glow`, `winning-card-pulse`, and `ai-card-reveal` were not audited for reduced-motion compliance in this wave. | Operator opens an a11y audit pass. |
| D5 | **#2539 / #2545 mobile-viewport accessibility test extension** | The Playwright smoke covers visual; a deeper a11y test (axe-core, screen-reader simulation) is a separate concern. | A11y audit pass. |
| D6 | **Cash-A strategy bugs (#2506 etc.)** | Backend strategy work, not UI/UX. Tracked on a separate analyst-c track. | (Already handled separately.) |

---

## 10. Success criteria

When the operator wakes up or checks in mid-wave, the run is a **success**
if:

- [ ] All 5 PRs (UX-1..5) are open in `brws-author-a`'s branch namespace
- [ ] Each PR is in **draft** state with the no-auto-merge banner in the body
- [ ] Each PR has the review coordinator verdict `passed` and CI green
- [ ] Each PR has Playwright smoke screenshots referenced in the body
- [ ] The 5 PRs respect the strict dependency order (no PR opened before
      its predecessor merged)
- [ ] Issues #2538, #2539, #2545 close in order (UX-3 → UX-4 → UX-5)
- [ ] Zero auto-merged Track B PRs (any auto-merge is a HIGH-severity
      regression to file against the orchestrator runbook)
- [ ] Zero regressions reported against merged PRs via post-merge review

**Partial success** (operator-visible, not a full rollback):
- UX-1/2/3 merged but UX-4/5 paused on operator availability — fine, the
  operator picks them up at the next checkpoint.
- UX-3's Playwright test flakes once — acceptable; second run passes.
- UX-5's Pass button outlined-blue is rejected by operator and the lane
  iterates to filled-blue in a follow-up commit — acceptable, scope is
  preserved.

**Failure signals** (require AM intervention):
- Any Track B PR auto-merged → revert immediately, file HIGH issue.
- The serial chain breaks (a later PR opens before an earlier one merges)
  → orchestrator must close the out-of-order PR and re-dispatch.
- A merged PR causes a `make check-gated` failure on `main` → revert,
  file infra-incident issue.
- Operator reports the jitter is **worse** after UX-3 merges → revert
  UX-3 (UX-1/2 may stay), reopen #2538, dispatch a corrective PR or
  escalate to PR D.

---

## 11. AM checkpoint expectations

When the operator opens the dashboard at the next checkpoint, they should
see:

### Active wave state

- **brws-author-a** holds one active branch (the current PR in the chain)
- All other brws-author lanes idle on `main`
- Open PR list filtered to `--label do-not-merge` shows the in-flight wave PRs

### Per-PR proving checklist (paste into operator's morning routine)

For each open PR in the wave:

1. `gh pr view <N>` — read body, confirm draft, confirm banner present
2. `gh pr checks <N>` — confirm CI green, review coordinator `passed`
3. `gh pr checkout <N>` — pull the branch into a local proving worktree
4. `make web` — start hosted app on free port
5. Open `http://localhost:8000/play/<test-uuid>` in a real browser
6. Reproduce the acceptance criteria for that PR
7. Compare against the screenshots in `data/local_smoke/<packet-id>/`
   (the lane attached references in the PR body)
8. If good: `gh pr ready <N>` (un-draft) then `gh pr merge <N> --squash`
9. If bad: comment on PR with specific repro + dismiss the lane via the
   orchestrator escalation path

### What to look for if something is wrong

- **PR opened but not in draft** → orchestrator's auto-draft step (per §6)
  failed. Manually `gh pr ready --undo <N>`. File an issue against the
  runbook.
- **Two PRs open simultaneously in the wave** → serial chain broken. Close
  the out-of-order PR and re-dispatch.
- **PR body missing banner** → the packet template was not applied. Add
  the banner via `gh pr edit --body`.
- **Playwright smoke missing screenshots** → the lane shipped without
  evidence. Hold the merge until the lane provides the screenshots
  (re-dispatch as a continuation task if the lane is idle).

---

## 12. Dispatch handoff to orchestrator

When this plan is approved and merged, the orchestrator should:

1. **Verify the wave gate**: this plan PR merged, brws-author-a idle.
2. **Pre-create all 5 task packets** in `dispatched=False` state via
   `ops.py task create`, populating `scope_declared`, `validation`, and
   the PR body template (§4.6) for each. Each packet references this
   plan's path + the applicable §4.x section verbatim.
3. **Set explicit dependency metadata**: each packet's `metadata` block
   should record `depends_on: [<previous-packet-id>]`. The orchestrator's
   dispatch loop should refuse to dispatch a packet whose dependency is
   not yet `completed`.
4. **Dispatch UX-1 only.** Wait for the lane to open the PR and confirm
   the orchestrator's 4-layer auto-merge mitigation (§6) is in place.
5. **Wait for operator merge of UX-1.** Do NOT auto-dispatch UX-2 — wait
   for the merge confirmation (the orchestrator's task-completion hook
   will fire when the operator runs `gh pr merge`).
6. **Repeat for UX-2 → UX-3 → UX-4 → UX-5.**
7. **After UX-5 merges**, run `gh issue list --search "#2538 OR #2539 OR
   #2545"` and confirm all three are closed. If any are still open,
   investigate the `Fixes` keyword in the PR body.
8. **Update MEMORY.md** with: PR numbers, branch names, one-line summary
   per PR, and a wave-completion note.
9. **File a follow-up issue** for the deferred PR D (trick-boundary
   choreography) with a link back to `plans/sessions/2026-04-06_card_jitter_investigation.md`
   §3 "Recommendation (secondary)".

---

## 13. References

### Plans + investigations

- `plans/sessions/2026-04-06_card_jitter_investigation.md` — root analysis
  for #2538; UX-1/2/3 implement the §3 primary recommendation
- `plans/sessions/2026-04-06_overnight_run_plan.md` — prior wave plan;
  source of the §6 auto-merge policy matrix format
- `plans/sessions/2026-04-06_ai_play_strategy_investigation.md` — Cash-A
  context (out of scope for this wave; referenced for completeness)

### Rules

- `.claude/rules/deferred/40_prs.md` — PR template + hard gates
- `.claude/rules/deferred/55_issue_closure.md` — Tier 2 verified-close
  policy (`Refs` vs `Fixes`); UX-1/2 use `Refs`, UX-3/4/5 use `Fixes`
- `.claude/rules/deferred/60_review_gate.md` — review coordinator + the
  auto-merge caveat that motivates the §6 mitigation
- `.claude/rules/15_testing_tiers.md` — Tier 1 / Tier 2 validation
- `.claude/rules/75_worktree_protection.md` — brws-author-a is protected;
  no `git worktree remove`
- `.claude/CLAUDE.md` — Implementation Handoff Protocol §

### Issues addressed by this wave

- **#2538** — UI: card play jitter/flicker (UX-1 Refs, UX-2 Refs, UX-3 Fixes)
- **#2539** — UI: auction "High Bid" display missing contract type suit icon (UX-4 Fixes)
- **#2545** — UI: auction pane visual distinction + Pass button blue (UX-5 Fixes)

### Related closed PRs (context only)

- **PR #2531** — `fix(web): bid form polish — single-line layout, full-width Pass, null contract default (#2521 items 2/3/4)` — merged 2026-04-06 09:47:55
- **PR #2534** — `feat(strategy): Cash-A sure-winners + draw-trump lead fixes` — merged 2026-04-06 09:47:59
- **PR #2540** — analyst's card jitter investigation report
- **PR #2541** — analyst's path-ref expansion on the jitter report
- **PR #2486** — auto-advance AI card reveals for natural pacing (the
  timing baseline UX-1/2 must respect)

### Source files referenced (read-only verification by analyst-b)

| Path | Lines | Why |
|---|---|---|
| `web/static/style.css` | 183-199, 245-250, 260-281, 935-940, 1229-1304, 3055-3087, 3118-3143 | UX-1, UX-3, UX-4, UX-5 surface |
| `web/static/css/accessibility.css` | 67-70, 102-106, 287-318 | UX-5 Pass button surface |
| `web/templates/partials/bid_panel.html` | 1-139 (entire file) | UX-4, UX-5 surface |
| `web/templates/partials/trick.html` | 55-78, 60-62, 85 | UX-1/2/3 reference (no edits) |
| `web/routes.py` | 282-287, 575-620 | UX-2, UX-4 surface |
| `src/bid_euchre/hosted_play/engine.py` | 619-621, 728-740, 773-810 | UX-2, UX-4 reference (no edits) |

---

## Outcome

*(To be filled after the orchestrator dispatches and the wave completes.)*

- UX-1 PR: TBD
- UX-2 PR: TBD
- UX-3 PR: TBD (closes #2538)
- UX-4 PR: TBD (closes #2539)
- UX-5 PR: TBD (closes #2545)
- Wave completion timestamp: TBD
- Operator AM proving notes: TBD
- Deferred PR D follow-up issue: TBD
