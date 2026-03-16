# Foundation Checkpoints

**Governing plan:** `plans/browser_game/governing_plan.md`
**Phase/Rung:** `0_foundation`
**Last updated:** 2026-03-15 by Codex

---

## Step Progress

| Step | Status | Date | Agent/Session | Notes |
|------|--------|------|---------------|-------|
| Step 0: Draft governing plan and initiative scaffold | COMPLETE | 2026-03-14 | Codex | Governing plan, amendments log, registry, and phase checkpoints created. |
| Step 1: Lock hosted-play rules contract | COMPLETE | 2026-03-15 | Codex | Authoritative rules contract now lives at `docs/01_core/HOSTED_PLAY_RULES.md`; planning draft left as a pointer only. |
| Step 2: Add dependencies and package skeleton | IN_PROGRESS | 2026-03-15 | Codex | `hosted` extras added to `pyproject.toml`; package skeleton still pending. |
| Step 3: Create database schema | PENDING | -- | -- | Create `web/schema.sql` with players, matches, hands, decisions tables. See governing plan §5.2 and SP-2-01. |
| Step 4: Inventory model artifacts | COMPLETE | 2026-03-15 | Codex | Verified `heuristic` is always available; hybrid and GBT artifacts exist under `data/artifacts/arc_d/r0/` and `data/artifacts/arc_d_v2/r0/`. |
| Step 5: Promote plan to ACTIVE | COMPLETE | 2026-03-15 | Codex | Governing plan status set to `ACTIVE`; Phase 0 now tracks only execution-prep work. |

## Active Sub-Plans

| Sub-Plan ID | File | Status | Blocking Step |
|-------------|------|--------|---------------|
| SP-0-01 | `sub/2026-03-14_phase0_foundation_lock.md` | in_progress | Step 2 |

## Blockers

- [x] ~~Authoritative hosted-play rules doc~~ → `docs/01_core/HOSTED_PLAY_RULES.md`
- [ ] Package skeleton not yet added (`src/bid_euchre/hosted_play/__init__.py`, `web/__init__.py`)
- [ ] Initial database schema not yet locked in files

## Session Log

### 2026-03-15 -- Codex
- Completed: Promoted the hosted-play rules draft into the authoritative docs path, added the `hosted` dependency extra to `pyproject.toml`, and locked the initial artifact roster in the planning docs.
- In progress: Phase 0 still needs the package skeleton and initial schema contract.
- Next: Finish SP-0-01 by locking the initial schema in the backend sub-plan and adding the package markers.

### 2026-03-15 -- Codex
- Completed: Promoted the governing plan to `ACTIVE` after closing the core Phase 0 decision questions.
- In progress: Phase 0 execution prep remains active through SP-0-01.
- Next: Hand off to the next agent to create package markers and finalize the initial schema contract.

### 2026-03-14 -- Codex
- Completed: Rewrote governing plan with MVP cut line, PR boundaries, testing strategy, package layout.
- In progress: Phase 0 scope lock.

### 2026-03-14 -- Claude
- Completed: Hosted play rules contract, 4 implementation sub-plans (SP-1-01 through SP-4-01), updated all 6 checkpoint files, updated sub-plan registry.
- In progress: Awaiting human review before promoting to ACTIVE.
- Next: Resolve remaining Phase 0 steps (authoritative rules doc path, deps, schema, artifact inventory), then begin Phase 1.
