# Frontend Product Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `3_frontend_product`
**Sub-plan:** `SP-3-01` → `3_frontend_product/sub/2026-03-14_htmx_game_ui.md`
**Last updated:** 2026-03-14

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Read sub-plan SP-3-01 and verify Phase 2 complete | PENDING | -- | -- | Cannot start until backend API passes all tests. |
| Step 1: Build base template and CSS card styles | PENDING | -- | -- | `base.html`, `style.css`. CSS-only cards with Unicode suits. |
| Step 2: Build landing, nickname, and model selection pages | PENDING | -- | -- | `landing.html`, `nickname_form.html`, `model_select.html`. |
| Step 3: Build game table layout and trick area | PENDING | -- | -- | `game.html`, `trick.html`, `hand.html`, `score.html`. |
| Step 4: Build bid panel | PENDING | -- | -- | `bid_panel.html`. Dynamic legal bid levels. Contract type selector. |
| Step 5: Build hand/match result screens | PENDING | -- | -- | `hand_result.html`, `match_result.html`. |
| Step 6: Add decision timer JS | PENDING | -- | -- | `game.js`. Minimal JS for timing + HTMX enhancements. |
| Step 7: Manual browser validation | PENDING | -- | -- | Full checklist from SP-3-01 §Validation. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-3-01 | `3_frontend_product/sub/2026-03-14_htmx_game_ui.md` | proposed | Step 0 |

## Blockers

- [ ] Phase 2 not complete.

## Note on Parallelism

Phase 3 and Phase 4 can execute in parallel after Phase 2 merges.
If two agents are available, launch both simultaneously.

## Session Log

### 2026-03-14 — Claude
- Completed: Sub-plan SP-3-01 created with card CSS, game table layout, HTMX wiring patterns, decision timer, and 12-item validation checklist.
- Next: Start after Phase 2 backend API is merged.
