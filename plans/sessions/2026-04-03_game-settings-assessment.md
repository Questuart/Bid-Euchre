# Game Settings — Choose AI Opponent and Target Score

**Date:** 2026-04-03
**Task packet:** `1f063d359915`
**Analyst:** analyst-b
**Status:** SHAPED — ready for dispatch

---

## Problem Statement

The current model-select screen (`partials/model_select.html`) is the only
pre-match configuration surface. It allows AI opponent selection but:

1. The target score is hardcoded to ±52 everywhere (engine constant
   `MATCH_TARGET = 52`, four comparison sites in engine.py, three template
   literals in `score.html`, `model_select.html`, `guide.html`).
2. There is no way for the player to choose a shorter or longer match.
3. The AI model picker and any future settings (target score) should be
   unified into a single "game settings" screen before match start.

## Implementation Seam

### Subsystem Map

| Layer | File(s) | Change Type |
|-------|---------|-------------|
| Engine | `src/bid_euchre/hosted_play/engine.py` | Make `MATCH_TARGET` parameterizable per-match |
| State | `src/bid_euchre/hosted_play/state.py` | Add `target_score` to `MatchState` |
| DB | `web/db.py` | Add `target_score` column to `Match` model |
| Config | `web/config.py` | Add `TARGET_SCORE_OPTIONS` constant |
| Routes | `web/routes.py` | Accept `target_score` from form, pass to engine |
| Template | `web/templates/partials/model_select.html` | Rename to `game_settings.html`, add target score selector |
| Score display | `web/templates/partials/score.html` | Dynamic match target text |
| CSS | `web/static/style.css` | Target score selector styling |
| Tests | `tests/unit/hosted_play/test_routes.py` | Target score selection + validation |
| Tests | `tests/unit/hosted_play/test_engine.py` | Parameterized target score match end |

### Key Design Decisions

**1. Engine parameterization approach**

The engine currently uses a module constant:
```python
MATCH_TARGET = 52  # engine.py:41
```
…referenced in 4 comparison sites (lines 967, 971, 976, 980).

**Recommended:** Add `target_score: int = 52` to `MatchState` and pass it into
`start_match()`. The 4 comparison sites read `state.target_score` instead of
the module constant. Keep `MATCH_TARGET = 52` as the default but make it
overridable per-match. This avoids breaking any code that imports `MATCH_TARGET`.

**2. State serialization**

`MatchState.to_dict()` / `from_dict()` must include `target_score` with a
default of 52 for backward compatibility (existing serialized matches in DB
don't have this field).

**3. DB column**

Add `target_score = Column(Integer, nullable=False, default=52)` to the `Match`
model. SQLite `CREATE TABLE` is idempotent via `create_all()`, but existing
rows in deployed environments will need the column added. Since the column has
a default, an additive migration is safe.

**4. Form design**

Transform `model_select.html` → `game_settings.html` with two sections:
- AI opponent (existing radio cards — no change to markup structure)
- Target score (new radio button group: 32, 42, **52** (default), 72)

The form still POSTs to `/play/{link_uuid}/select-ai` (rename endpoint is
optional; keeping it avoids breaking existing test helpers).

**5. Hardcoded "±52" text**

Three template locations reference "52" literally:
- `partials/score.html:69-70` — "First to ±52 wins"
- `partials/model_select.html:11` — "First to ±52 wins"
- `partials/model_select.html:44` — "First team to ±52 points wins"

Plus several guide references:
- `guide.html:134,147,185,231`
- `partials/game_controls.html:18`

**In-match display:** `score.html` and the new `game_settings.html` must use
the dynamic target score from context. Guide/help pages can keep "52" as the
default description (they describe general rules, not the current match).

**6. Preference persistence**

The task packet mentions "persist preferences." The simplest approach: store
`target_score` on the `Match` row (already needed for engine correctness).
For cross-match preference memory, add `preferred_target_score` and
`preferred_model_id` to the `Player` model. Pre-populate the form with the
player's last choices.

**Recommendation:** Split into two slices:
- **Slice 1 (core):** Per-match target score — engine, state, DB match column,
  form, display. No player preference persistence.
- **Slice 2 (polish):** Player preference columns + form pre-population.

Slice 2 is optional and can be deferred without blocking the core feature.

## Acceptance Criteria

### Slice 1 (Core)

- [ ] Player can select target score (32, 42, 52, 72) on the pre-match screen
- [ ] Default selection is 52
- [ ] Selected target score is stored on the Match DB row
- [ ] Engine uses the per-match target score for match-end checks
- [ ] Score bar displays the actual target (not hardcoded "52")
- [ ] Existing matches without `target_score` column default to 52
- [ ] Invalid target score values are rejected (400 response)
- [ ] All existing tests continue to pass (backward compat)
- [ ] New tests cover: target score selection, custom target match end,
      invalid value rejection

### Slice 2 (Polish — optional)

- [ ] Player's last model + target score selections are remembered
- [ ] Form pre-populates with player's preferences
- [ ] New player defaults to bud_bot + 52

## Validation Commands

```bash
# Tier 1 — during implementation
uv run python -m pytest tests/unit/hosted_play/test_routes.py -v
uv run python -m pytest tests/unit/hosted_play/test_engine.py -v

# Tier 2 — before PR
make check-quiet
```

## File Ownership and Safe Parallelism

**Single-author scope.** All files are in the web/hosted-play boundary:

| File | Operation |
|------|-----------|
| `src/bid_euchre/hosted_play/engine.py` | Modify match-end logic |
| `src/bid_euchre/hosted_play/state.py` | Add field to MatchState |
| `src/bid_euchre/hosted_play/__init__.py` | Update exports if needed |
| `web/db.py` | Add column to Match |
| `web/routes.py` | Accept + pass target_score |
| `web/templates/partials/model_select.html` | Rename → game_settings.html (or keep + extend) |
| `web/templates/partials/score.html` | Dynamic target text |
| `web/static/style.css` | Minor styling for score selector |
| `tests/unit/hosted_play/test_routes.py` | New tests |
| `tests/unit/hosted_play/test_engine.py` | New tests |

No overlap with other active lanes. Safe for single-author dispatch.

## Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Template rename breaks HTMX partial references | Medium | Grep all `model_select` references in routes.py (6+ occurrences at lines 256, 822, 853, 890, 1449) — must update all. Alternative: keep filename, just add content. |
| Existing serialized MatchState in DB missing `target_score` | Low | `from_dict()` defaults to 52 — already the pattern for all optional fields |
| Leaderboard/stats assume 52-point matches | Medium | Leaderboard metrics (net_eppd, win_rate) are match-agnostic. But if comparing across target scores, consider adding `target_score` filter later. Not a blocker for Slice 1. |
| Guide/help text says "52" | Low | Guide describes general rules — leave as-is or add "(default)" qualifier |
| Browser E2E tests reference "52" text | Low | Check Playwright tests for hardcoded assertions |

## Recommended PR Decomposition

**Single PR** for Slice 1 is appropriate — the changes are cohesive and
~150-200 lines of production code + ~100 lines of tests. No need to split
further.

**Branch name:** `feat/web-game-settings` (already exists on this worktree)

## Implementation Notes for Author Lane

1. Start with engine + state changes (pure logic, easy to test).
2. Add DB column.
3. Update route to accept + validate `target_score` form field.
4. Update template: add target score radio group below AI picker.
5. Update score.html to use dynamic target.
6. Add/update tests.
7. Run Tier 2 validation.

**Template rename decision:** Recommend keeping `model_select.html` filename
to minimize reference churn. The template evolves from "model select" to
"game settings" in content but the filename can stay. If renaming, update
all 6+ route references.

## Smoke-Test Boundary

After implementation, a human can verify by:
1. Starting a new match → seeing the target score selector
2. Picking "32" → playing to ±32 → match ends correctly
3. Score bar shows "First to ±32 wins" during the match

## Outcome

_To be filled after implementation._
