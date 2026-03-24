# Data Pipeline Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `4_data_pipeline`
**Sub-plan:** `SP-4-01` → `4_data_pipeline/sub/2026-03-14_export_replay.md`
**Last updated:** 2026-03-24 (closeout)

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Read sub-plan SP-4-01 and verify Phase 2 complete | COMPLETE | 2026-03-24 | brws-author-a | Phase 2 COMPLETE (PRs #1430, #1435). Ready to start. |
| Step 1: Implement export logic (`web/export.py`) | COMPLETE | 2026-03-24 | brws-author-a | `decision_to_jsonl` (PR #1529), `export_decisions` (PR #1535). |
| Step 2: Implement export CLI (`scripts/internal/export_hosted_decisions.py`) | COMPLETE | 2026-03-24 | brws-author-a | PR #1538. --db, --output, --match-uuid, --human-only flags. |
| Step 3: Implement replay validation | COMPLETE | 2026-03-24 | brws-author-a | PR #1545. `validate_replay` JSONL correctness verifier. |
| Step 4: Write tests | COMPLETE | 2026-03-24 | brws-author-a | PR #1533 (fixture helpers) + tests in PRs #1529, #1535, #1545. All 6 required tests covered. |
| Step 5: Run validation | COMPLETE | 2026-03-24 | brws-author-a | All hosted_play tests pass (`tests/unit/hosted_play/`). Full `make check-quiet` green. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-4-01 | `4_data_pipeline/sub/2026-03-14_export_replay.md` | completed | -- |

## Blockers

- [x] ~~Phase 2 not complete.~~ Phase 2 CLOSED 2026-03-24 (PRs #1430, #1435). Phase 3 also COMPLETE.

## Note on Parallelism

Phase 4 depends on Phase 2 (not Phase 3). Can run in parallel with Phase 3.

## Session Log

### 2026-03-24 — brws-author-a (SP-4-01 closeout)
- All 5 steps COMPLETE. PRs: #1529, #1533, #1535, #1538, #1545.
- Validation pass: all hosted_play tests pass in `tests/unit/hosted_play/`.
- SP-4-01 status: active → completed.
- Phase 4 data pipeline is fully delivered.

### 2026-03-24 — brws-author-a (Phase 4 activation)
- Phase 2 blocker cleared (PRs #1430, #1435 merged).
- Phase 3 also COMPLETE (PRs #1475, #1489, #1495, #1498, #1501).
- SP-4-01 status: proposed → active.
- Phase 4 is now fully unblocked and ready to start.

### 2026-03-14 — Claude
- Completed: Sub-plan SP-4-01 created with JSONL export format, CLI tool, replay validation, and 6 required tests.
- Next: Start after Phase 2 backend API is merged. Can run in parallel with Phase 3.
