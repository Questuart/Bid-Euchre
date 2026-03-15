# Phase 0 Foundation Lock

**ID:** SP-0-01
**Date:** 2026-03-14
**Parent:** `plans/browser_game/governing_plan.md` -- §7.4 Phase 0 Dependencies
**Status:** in_progress
**Owner:** Codex

---

## Inputs

- Input 1: `plans/browser_game/governing_plan.md` -- current governing scope and execution structure
- Input 2: `src/bid_euchre/sim/simulation.py` -- reference batch simulator that must not become the browser runtime loop
- Input 3: `src/bid_euchre/core/rules.py` -- legal-play and trick-resolution primitives to reuse
- Input 4: `src/bid_euchre/scoring.py` -- per-hand scoring logic to extend into match scoring
- Input 5: `src/bid_euchre/strategy/bidding.py` -- bidder interfaces and artifact-driven bidding entry points
- Input 6: `src/bid_euchre/strategy/greedy.py` -- `GluttonStrategy` card-play implementation
- Input 7: `src/bid_euchre/models/bidding_artifact.py` -- artifact schema and loading path

## Assumptions

- Approved bidding artifacts exist or can be generated without inventing a new model format.
- Render and Postgres remain the preferred hosted deployment target unless a concrete blocker is found.
- Existing test layout under `tests/unit/` and `tests/integration/` is the correct place for hosted-play tests.

## Dependencies

- Phase 0 item 1 -- hosted-play rules contract
- Phase 0 item 4 -- persistence contract
- Phase 0 item 5 -- model publication policy
- Phase 0 item 6 -- testing contract

## Plan

### Step 1: Lock package and persistence boundaries
- Confirm `src/bid_euchre/hosted_play/` as the reusable domain layer.
- Confirm `web/` as the FastAPI interface layer.
- Define the initial storage entities: `matches`, `hands`, `action_events`, `model_registry`.
- Lock the future extraction boundary so web/ORM concerns do not leak into the hosted-play domain package.
- Lock persistence mode to SQLite for local/dev and Postgres for deployed environments.

### Step 2: Lock the rules and testing contracts
- Migrate the working hosted-play rules draft into `docs/01_core/HOSTED_PLAY_RULES.md` as the authoritative implementation contract.
- Specify where hosted-play tests live and which validation commands are mandatory in each PR.
- Lock the hosted dependency set under `[project.optional-dependencies].hosted` in `pyproject.toml`.

### Step 3: Inventory bidder artifacts and launch roster
- Locate actual artifact files and determine which ones are suitable for hosted play.
- Record any blockers if artifact generation or publication policy is still missing.
- Lock the initial launch roster to `heuristic` (always), `hybrid_olsa` (if artifact present), and `gbt_action_value` (if artifact present).

### Step 4: Prepare PR-1 execution handoff
- Convert the locked decisions into a concrete implementation sub-plan for PR-1.
- Update checkpoints and registry so the next session can start work immediately.

## Files Changed

- `plans/browser_game/governing_plan.md` -- revised governing structure and MVP cut line
- `plans/browser_game/0_foundation/plan.md` -- Phase 0 details and exit criteria
- `plans/browser_game/0_foundation/checkpoints.md` -- phase progress and active sub-plan tracking
- `plans/browser_game/sub_plan_registry.md` -- register this sub-plan
- `docs/01_core/HOSTED_PLAY_RULES.md` -- NEW: rules extension document for hosted play
- `pyproject.toml` -- dependency additions for web stack
- `plans/browser_game/2_backend_api/sub/2026-03-14_fastapi_app.md` -- align AI manager and persistence assumptions with locked Phase 0 decisions
- `plans/browser_game/5_deployment_launch/checkpoints.md` -- align hosting target with locked Phase 0 decision

## Validation

- [ ] Plan audit: referenced files and paths exist or are explicitly marked NEW
- [ ] Contract check: package layout and PR boundaries align with the governing plan
- [ ] Extraction check: hosted-play domain responsibilities are distinct from `web/` responsibilities
- [ ] Artifact inventory: at least one approved bidder artifact path is identified, or a concrete blocker is recorded
- [ ] Dependency check: `hosted` extras in `pyproject.toml` match the locked Phase 0 decision

## Planned Outputs

- `plans/browser_game/0_foundation/plan.md` -- phase detail
- `plans/browser_game/0_foundation/sub/2026-03-14_phase0_foundation_lock.md` -- actionable foundation sub-plan
- Updated `plans/browser_game/sub_plan_registry.md` and checkpoints

## Observed Outputs

_Filled during/after execution._

- Output 1: `docs/01_core/HOSTED_PLAY_RULES.md` -- authoritative hosted-play rules contract created on 2026-03-15
- Output 2: `plans/browser_game/hosted_play_rules.md` -- reduced to a pointer note so planning and implementation sources do not diverge
- Output 3: `pyproject.toml` -- `hosted` optional dependency group added on 2026-03-15

## Outcome

_Filled after completion._

- Status: --
- PR: --
- Deviations from plan: --
- Issues discovered: --

## Handoff

_Filled at session end if work is incomplete._

- Current state: Governing plan revised; Phase 0 still needs execution decisions locked in code/docs.
- Next action: Inventory actual bidder artifacts, then lock the dependency stack and initial schema sketch.
- Blockers: Artifact availability not yet verified. Dependency stack still not added to `pyproject.toml`.
- Files with uncommitted changes: --
