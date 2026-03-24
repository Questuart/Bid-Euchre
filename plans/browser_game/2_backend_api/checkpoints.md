# Backend API Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `2_backend_api`
**Sub-plan:** `SP-2-01` → `2_backend_api/sub/2026-03-14_fastapi_app.md`
**Last updated:** 2026-03-24

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Read sub-plan SP-2-01 and verify Phase 1 complete | COMPLETE | 2026-03-23 | brws-author-b | Phase 1 CLOSED (PRs #1380, #1392, #1402). MatchEngine API verified against SP-2-01 route handler requirements. |
| Step 1: Implement DB models and schema init (`db.py`, `schema.sql`) | COMPLETE | 2026-03-23 | brws-author-b | PR #1430. SQLAlchemy models + config + schema. |
| Step 2: Implement AI manager (`ai_manager.py`) | COMPLETE | 2026-03-23 | brws-author-b | PR #1430. Config-backed heuristic + hybrid_olsa roster. |
| Step 3: Implement FastAPI app and routes (`app.py`, `routes.py`) | IN_PROGRESS | 2026-03-24 | brws-author-b | 8 route handlers with idempotent submissions. |
| Step 4: Implement decision logging in routes | IN_PROGRESS | 2026-03-24 | brws-author-b | Human decisions logged with full detail; AI decisions with placeholders (V1 limitation). |
| Step 5: Write integration tests | IN_PROGRESS | 2026-03-24 | brws-author-b | 17 tests covering all 10 required scenarios + edge cases. |
| Step 6: Run validation | IN_PROGRESS | 2026-03-24 | brws-author-b | 17/17 tests passing, `make check-quiet` green. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-2-01 | `2_backend_api/sub/2026-03-14_fastapi_app.md` | in_progress | Steps 3-6 |

## Blockers

- [x] ~~Phase 1 not complete.~~ Phase 1 CLOSED 2026-03-23 (PRs #1380, #1392, #1402).

## Session Log

### 2026-03-24 — brws-author-b
- Completed: Steps 3-6 — Route handlers, decision logging, integration tests, validation.
- Files created: `web/routes.py` (8 route handlers), `web/templates/base.html`, `tests/unit/hosted_play/test_routes.py` (17 tests).
- Files updated: `web/app.py` (router registration).
- All 10 required test scenarios from SP-2-01 covered plus 7 additional edge case tests.
- Known V1 limitation: AI decision logging uses placeholders for legal_actions/game_state since the engine doesn't expose per-step callbacks.
- Validation: 17/17 tests passing, `make check-quiet` green.
- Next: PR for merge.

### 2026-03-23 — brws-author-b
- Completed: Step 0 — verified Phase 1 prerequisites against SP-2-01.
- Verified: Phase 1 CLOSED on main. `MatchEngine` provides all APIs required by SP-2-01 route handlers: `start_match()`, `submit_human_bid()`, `submit_human_card()`, `get_visible_state()`, `serialize()`, `deserialize()`. State dataclasses (`MatchState`, `HandState`, `TrickState`, `TrickResult`) with full JSON round-trip. 60 tests passing.
- Verified: SP-2-01 route handler design (`/bid`, `/play-card`) maps directly to engine API — no gaps.
- Next: Step 1 (DB models + schema init) is now unblocked.

### 2026-03-23 — Codex
- Completed: Aligned backend Step 1/2 notes with amendment BG-1 and the new Phase 0 schema contract.
- Next: Begin after Phase 1 merges. Use config-backed startup preload for `heuristic` and `hybrid_olsa`; do not add a V1 database `model_registry`.

### 2026-03-14 — Claude
- Completed: Sub-plan SP-2-01 created with DB models, AI manager, route handlers, idempotent submission design, and 10 required tests.
- Next: Start after Phase 1 engine is merged.
