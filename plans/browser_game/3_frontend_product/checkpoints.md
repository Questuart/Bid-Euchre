# Frontend Product Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `3_frontend_product`
**Sub-plan:** `SP-3-02` → `3_frontend_product/sub/2026-03-24_browser-ui.md`
**Design reference:** `SP-3-01` → `3_frontend_product/sub/2026-03-14_htmx_game_ui.md` (superseded as execution plan; retained as design reference for CSS, layout, HTMX patterns)
**Last updated:** 2026-03-24

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Verify Phase 2 complete and read SP-3-02 | COMPLETE | 2026-03-24 | brws-author-a | Phase 2 CLOSED (PRs #1430, #1435). SP-3-02 created (#1447). |
| Step 1: Game board template (HTML/CSS for card display, bid UI, play UI) | IN_PROGRESS | 2026-03-24 | brws-author-a | `game.html`, `landing.html`, `style.css`. CSS-only card rendering with Unicode suits. |
| Step 2: Template partials for HTMX responses (bid result, card play result, trick complete) | COMPLETE | 2026-03-24 | brws-author-b | PR #1475 merged. 8 HTMX partials: nickname, model-select, bid, hand, trick, score, hand-result, match-result. |
| Step 3: Static assets (CSS, minimal JS for HTMX) | IN_PROGRESS | 2026-03-24 | brws-author-d | `style.css`, `game.js`. Decision timer, card click handler, HTMX enhancements. |
| Step 4: End-to-end local vertical slice (uvicorn + browser test) | PENDING | -- | -- | Full match flow: create → nickname → select AI → bid → play → score → win/loss. |
| Step 5: Refresh/resume proof (browser refresh preserves game state) | PENDING | -- | -- | Idempotent submissions + persisted state survive refresh at any point. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-3-02 | `3_frontend_product/sub/2026-03-24_browser-ui.md` | active | Steps 1-3 |
| SP-3-01 | `3_frontend_product/sub/2026-03-14_htmx_game_ui.md` | superseded | -- |

## Blockers

- [x] ~~Phase 2 not complete.~~ Phase 2 CLOSED 2026-03-24 (PRs #1430, #1435).

## Key Constraint

Server-rendered HTML with HTMX, no frontend build tooling. Routes already
return HTMX partials from `web/routes.py` (#1435).

## Note on Parallelism

Phase 3 and Phase 4 can execute in parallel after Phase 2 merges.
If two agents are available, launch both simultaneously.

## Session Log

### 2026-03-24 — orchestrator (checkpoint update)
- Step 0: COMPLETE — Phase 2 verified, SP-3-02 created (PR #1447).
- Step 1: IN_PROGRESS on brws-author-a (game board template, landing page, CSS).
- Step 2: COMPLETE — PR #1475 merged (8 HTMX template partials).
- Step 3: IN_PROGRESS on brws-author-d (static assets: CSS + JS).
- SP-3-02 status: proposed → active.
- Issue #1442 (spinner-aware activity detection) already closed by PR #1468.

### 2026-03-24 — brws-author-a
- Completed: Phase 2 closure confirmed. Updated checkpoints with new 5-step structure from SP-3-02.
- Phase 3 is now unblocked. SP-3-01 superseded by SP-3-02 (refined step structure).
- Next: Step 0 (verify Phase 2 + read SP-3-02), then Step 1 (game board template).

### 2026-03-14 — Claude
- Completed: Sub-plan SP-3-01 created with card CSS, game table layout, HTMX wiring patterns, decision timer, and 12-item validation checklist.
- Next: Start after Phase 2 backend API is merged.
