# Backend API Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `2_backend_api`
**Sub-plan:** `SP-2-01` → `2_backend_api/sub/2026-03-14_fastapi_app.md`
**Last updated:** 2026-03-14

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Read sub-plan SP-2-01 and verify Phase 1 complete | PENDING | -- | -- | Cannot start until Phase 1 engine passes all tests. |
| Step 1: Implement DB models and schema init (`db.py`, `schema.sql`) | PENDING | -- | -- | SQLAlchemy models for players, matches, hands, decisions. |
| Step 2: Implement AI manager (`ai_manager.py`) | PENDING | -- | -- | Model discovery, loading, roster. See SP-2-01 §AI Manager. |
| Step 3: Implement FastAPI app and routes (`app.py`, `routes.py`) | PENDING | -- | -- | All endpoints from SP-2-01 §Route Handlers. Idempotent submissions. |
| Step 4: Implement decision logging in routes | PENDING | -- | -- | Log human + AI decisions to `decisions` table on each action. |
| Step 5: Write integration tests | PENDING | -- | -- | 10 required tests listed in SP-2-01 §Required Tests. |
| Step 6: Run validation | PENDING | -- | -- | `uv run python -m pytest tests/unit/hosted_play/test_routes.py -v` + manual curl. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-2-01 | `2_backend_api/sub/2026-03-14_fastapi_app.md` | proposed | Step 0 |

## Blockers

- [ ] Phase 1 not complete.

## Session Log

### 2026-03-14 — Claude
- Completed: Sub-plan SP-2-01 created with DB models, AI manager, route handlers, idempotent submission design, and 10 required tests.
- Next: Start after Phase 1 engine is merged.
