# SP-5-01: GBT Evaluation and Optional Promotion

**ID:** SP-5-01
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 5 -- Optional GBT Evaluation
**Status:** proposed
**Owner:** --

---

## Inputs

- `data/artifacts/arc_d_v2/r3/` -- `gbt_*` joblibs and `training_artifact_gbt_av.json`
- `docs/04_reports/arc_d_v2/r3/full/02_decision.md`
- `docs/04_reports/arc_d_v2/r3/full/tables/h2h_delta_matrix.csv`
- `src/bid_euchre/strategy/bidding.py` -- `GBTActionValueBidder`
- browser model-serving code from Phase 1

## Assumptions

- GBT is not a launch blocker for the pilot.
- Evaluation should answer a product decision, not reopen the core pilot path.
- H2H evidence and browser-serving cost both matter.

## Dependencies

- Phase 1 complete
- Preferably Phase 4 stable so the pilot path is no longer moving

## Plan

### Step 1: Add optional hidden browser wiring

- Add `gbt_av` behind config only.
- Do not make it the default visible pilot path during initial rollout.

### Step 2: Measure operational and UX cost

- Record cold load, warm decision latency, and any browser UX impact.
- Compare against the stable OLSa path.

### Step 3: Make a promote/defer decision

- Compare H2H evidence, operational complexity, and pilot feedback.
- Decide whether to expose GBT publicly, keep it hidden, or defer entirely.

## Files Changed

- `web/ai_manager.py`
- `web/config.py`
- `.env.example`
- `docs/01_core/DEPLOYMENT.md`
- `tests/unit/hosted_play/test_ai_manager.py`
- `tests/unit/hosted_play/test_config.py`
- optional measurement notes/checkpoints updates

## Validation

### Pass/Fail Criteria

- [ ] **Unit tests:** `uv run python -m pytest tests/unit/hosted_play/test_ai_manager.py tests/unit/hosted_play/test_config.py -q`
  - Expected: optional GBT wiring works without breaking the default OLSa path.
- [ ] **Measurement proof:** execute the agreed preload/runtime measurement script
  - Expected: cold-load and warm-latency numbers are recorded.
- [ ] **Browser smoke:** create and play a GBT-backed local match
  - Expected: browser flow remains stable if GBT is enabled.
- [ ] **Decision proof:** checkpoint/sub-plan records an explicit promote/defer outcome
  - Expected: no ambiguous "maybe later" status remains.

## Planned Outputs

- Optional GBT browser wiring
- Operational measurements
- Explicit promotion/defer decision

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: deferred by design.
- Next action: do not start until the OLSa/moon-loner pilot path is stable.
- Blockers: Phase 1 incomplete.
- Files with uncommitted changes: --
