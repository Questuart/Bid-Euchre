# Issue #2225: First-Time Player Onboarding Flow — Implementation Assessment

**Date:** 2026-04-03
**Issue:** #2225
**Analyst:** analyst-b
**Estimate:** **L (Large)**
**Status:** SHAPED — ready for dispatch

---

## Problem Statement

New players enter invite code → set nickname → immediately land on the AI model
selection screen. There is no guided introduction to the game. Issue #2225
requests a first-time onboarding flow:

1. Invite code + nickname (existing)
2. **Welcome letter** (new — content TBD by operator)
3. **Guide walkthrough** (new — step-by-step, reusing `guide.html` content)
4. Game (existing — model selection → match start)

Returning players skip the onboarding and go directly to the game.

## Current Post-Login Flow

```
enter_code (POST /enter-code)
  → creates Player(link_uuid, nickname=None)
  → redirects to /play/{link_uuid}

game_page (GET /play/{link_uuid})
  → if not player.nickname → phase="nickname" → nickname_form.html
  → POST /play/{uuid}/nickname → set nickname → returns model_select partial
  → if no active match → phase="model_select" → model_select.html
  → if active match → phase=<game phase> → game_board.html
```

The key insertion point is **after nickname is set, before model_select**. The
current flow goes: `set_nickname()` → immediately returns `model_select.html`.
The onboarding flow intercepts this transition.

## Implementation Seam

### DB Changes

| Change | File | Complexity |
|--------|------|------------|
| Add `onboarding_complete = Column(Integer, nullable=False, default=0)` to `Player` | `web/db.py` | Trivial |

**Why `Integer` not `Boolean`:** SQLAlchemy + SQLite doesn't have native booleans.
Using `Integer` with `0/1` is the existing pattern (matches `CheckConstraint` style).

**Migration concern:** Existing players in deployed DB need the column. Two options:
- `ALTER TABLE players ADD COLUMN onboarding_complete INTEGER NOT NULL DEFAULT 1`
  (mark existing players as complete)
- Or handle at startup with a migration script

**Recommendation:** Use `default=0` in the model, and add a one-time startup
migration that sets `onboarding_complete=1` for all players who already have a
nickname. This avoids forcing existing players through onboarding.

### Route Changes

| Route | File | Change |
|-------|------|--------|
| `POST /play/{uuid}/nickname` | `web/routes.py:869` | After setting nickname, check `onboarding_complete` — if 0, return welcome letter partial instead of model_select |
| `GET /play/{uuid}` | `web/routes.py:758` | Add onboarding phase check after nickname, before model_select |
| `POST /play/{uuid}/onboarding/next` (new) | `web/routes.py` | Advance through onboarding steps (welcome → guide pages → complete) |
| `POST /play/{uuid}/onboarding/skip` (new) | `web/routes.py` | Skip remaining onboarding, mark complete |

**Flow with onboarding:**
```
set_nickname()
  → if onboarding_complete == 0 → return "welcome_letter" partial
  → else → return model_select partial

game_page()
  → if not nickname → nickname phase
  → if not onboarding_complete → onboarding phase
  → if no match → model_select phase
  → else → game phase

POST onboarding/next
  → step 0 (welcome letter) → step 1 (guide page 1) → ... → step N → mark complete → return model_select

POST onboarding/skip
  → mark complete → return model_select
```

### Template Changes

| Template | Status | Complexity |
|----------|--------|------------|
| `partials/welcome_letter.html` (new) | New file | Small — simple static content with "Next" button |
| `partials/onboarding_guide.html` (new) | New file | Medium — step-by-step cards extracted from `guide.html` |
| `game.html` | Modify | Small — add `onboarding_welcome` and `onboarding_guide` phase includes |

**Guide content extraction:** The existing `guide.html` has 6 sections:
1. Quick Start (4 bullet points)
2. The Basics (deck/deal/goal)
3. Bidding (rules)
4. Card Play (follow suit, trump, bowers, duplicates, high/low)
5. Scoring (made bid, set, defenders, match end)
6. Icons & Indicators (table)
7. Tips & Tricks (7 tips)
8. Basic Strategies (7 items)

**Recommended walkthrough steps:**
- Step 1: Quick Start + The Basics (combined — orientation)
- Step 2: Bidding (most important mechanic to learn)
- Step 3: Card Play + Scoring (combined — playing the game)
- Step 4: Tips (optional — can be skipped)

This keeps the walkthrough to 3-4 steps max, not 8 individual pages. Each step
is a card with "Next" / "Skip" buttons, progress dots, and the content extracted
from `guide.html` sections.

### JS Changes

| File | Change | Complexity |
|------|--------|------------|
| `web/static/game.js` | None required if using HTMX for navigation | None |

**Key insight:** The existing flow already uses HTMX for transitions (nickname →
model_select). The onboarding flow can use the same pattern: each "Next" click
is an `hx-post` to `/play/{uuid}/onboarding/next` that swaps the content.

If operator wants client-side step navigation (no server round-trip per step),
add ~30 lines of JS for step toggling. But HTMX is simpler and consistent.

**Recommendation:** Use HTMX (server-rendered). Each step is a POST that returns
the next step's HTML. Progress state is server-side (`onboarding_step` in the
POST response, not persisted).

### CSS Changes

| File | Change | Complexity |
|------|--------|------------|
| `web/static/style.css` | New styles for onboarding cards, progress dots, step navigation | ~60-80 lines |

Follows existing patterns: `.model-card`, `.guide__section`, `.quick-start-guide`
provide reusable design vocabulary.

### Test Changes

| Test File | New Tests | Complexity |
|-----------|-----------|------------|
| `tests/unit/hosted_play/test_routes.py` | ~8-10 new tests | Medium |

Tests needed:
- [ ] New player sees welcome letter after setting nickname
- [ ] Onboarding next advances through steps
- [ ] Onboarding skip marks complete and shows model_select
- [ ] Returning player (onboarding_complete=1) skips to model_select
- [ ] Existing player without column defaults to complete (migration)
- [ ] game_page shows onboarding for incomplete player
- [ ] game_page shows model_select for completed player

## Difficulty Estimate: L (Large)

### Sizing Rationale

| Dimension | Assessment |
|-----------|------------|
| Files touched | 6-7 (db, routes, 2-3 new templates, game.html, style.css, tests) |
| New routes | 2 (onboarding/next, onboarding/skip) |
| DB change | 1 new column + migration for existing data |
| Template work | 2 new partials + game.html dispatch update |
| Content | Welcome letter is TBD — needs operator input or placeholder |
| Test additions | ~8-10 new test methods |
| Total LOC estimate | ~300-400 new/modified lines |
| Cross-cutting concerns | Post-login flow, HTMX swap target chain, mobile layout |

**Why L, not M:**
1. The guide content extraction requires careful decomposition of the 252-line
   `guide.html` into step-sized chunks without duplicating content.
2. Two new routes with step-state management add complexity.
3. The onboarding flow intersects with the existing post-login flow at two
   points (`set_nickname` and `game_page`), requiring careful refactoring.
4. Migration of existing players is a deployment concern.
5. Welcome letter content is TBD — implementation needs a placeholder that
   the operator can later customize.

**Why not XL:**
1. No new JS required (HTMX handles navigation).
2. No new DB tables, just one column.
3. Content is reused from existing `guide.html`.
4. Design vocabulary already exists in CSS.

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Welcome letter content not defined | Medium | Use placeholder content; make it easy to swap (template-only, no code change needed) |
| Guide content duplication (guide.html vs onboarding) | Medium | Extract shared content into Jinja2 macros or include fragments |
| Existing deployed players forced through onboarding | High | Migration must mark existing players complete; test this explicitly |
| HTMX swap chain complexity | Medium | Each onboarding step targets `#game-board` like existing phases; follow existing pattern |
| Mobile layout untested for new partials | Low | Reuse existing responsive patterns; include mobile viewport test |
| Onboarding state lost on page refresh | Low | If mid-onboarding, `game_page` detects `onboarding_complete=0` and restarts from welcome; acceptable UX |

## Acceptance Criteria

- [ ] New player flow: invite code → nickname → welcome letter → guide steps → game
- [ ] Returning player (played before): skips directly to game
- [ ] "Skip" button on any onboarding step → marks complete, goes to game
- [ ] Welcome letter uses placeholder content (operator can customize later)
- [ ] Guide walkthrough reuses existing `guide.html` content, not duplicate copy
- [ ] `onboarding_complete` flag persisted on Player record
- [ ] Existing players in deployed DB default to onboarding_complete=1
- [ ] Mobile-friendly layout for onboarding steps
- [ ] All existing tests pass (no regression)
- [ ] 8+ new tests covering the onboarding flow

## Validation Commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/unit/hosted_play/test_routes.py -v
uv run python -m pytest tests/unit/hosted_play/test_routes.py -k "onboarding" -v

# Tier 2 — before PR
make check-quiet
```

## Recommended PR Decomposition

**Option A (single PR):** One PR with all changes. Appropriate if a single
author lane handles it in one session. ~300-400 LOC is within single-PR range.

**Option B (two PRs):** Split if the welcome letter content is delayed:
- PR 1: DB migration + route plumbing + guide walkthrough (no welcome letter)
- PR 2: Welcome letter content + any design polish

**Recommendation:** Option A unless welcome letter content is blocked.

## Dependencies and Sequencing

- **No blocking dependencies.** Can start immediately.
- **Soft dependency on game settings (#1f063d359915):** If both land, the
  onboarding flow ends at the game settings screen (not just model_select).
  But neither blocks the other — they compose cleanly.
- **Guide content is stable.** The `guide.html` content was added in #2132/PR #2147
  and is not expected to change.

## Orchestrator Handoff

This assessment is complete. The work is ready for dispatch to an author lane
with:
- **Scope:** `web/db.py`, `web/routes.py`, `web/templates/game.html`,
  `web/templates/partials/welcome_letter.html` (new),
  `web/templates/partials/onboarding_guide.html` (new),
  `web/static/style.css`, `tests/unit/hosted_play/test_routes.py`
- **Estimate:** L — expect 1-2 hours for an experienced author lane
- **Branch:** `feat/web-onboarding-flow`
- **Blocker:** Welcome letter content TBD — use placeholder

## Outcome

_To be filled after implementation._
