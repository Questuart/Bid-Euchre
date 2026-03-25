# SP-1-01: OLSa Roster Migration

**ID:** SP-1-01
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 1 -- Model and Rules Core
**Status:** proposed
**Owner:** --

---

## Inputs

- `web/ai_manager.py`
- `web/config.py`
- `web/routes.py`
- `web/templates/partials/model_select.html`
- `src/bid_euchre/strategy/bidding.py` -- `ActionValueBidder`, `HybridOLSaBidder`
- `data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json`
- `plans/browser_game/governing_plan.md` and `plans/browser_game/amendments.md`

## Assumptions

- The pilot-visible artifact-backed model should be the R3 `full_ols_av`
  artifact rather than the old hybrid artifact.
- `ActionValueBidder` is the correct browser-facing bidder class for this wave.
- `gbt_av` remains deferred and is not exposed in the visible roster yet.

## Dependencies

- Phase 0 complete
- `SP-0-01` complete

## Plan

### Step 1: Replace the artifact-backed browser roster entry

- Add a browser roster entry backed by `ActionValueBidder`.
- Point it at `training_artifact_full_ols_av.json`.
- Make it the default visible product model.

### Step 2: Clean up config and env naming

- Replace or deprecate `HYBRID_OLSA_ARTIFACT` with a new OLSa-specific config
  variable.
- Update deployment docs and `.env.example` expectations accordingly.

### Step 3: Align product naming

- Expose the model in the UI as `OLSa`.
- Decide whether the browser should present only one visible model option for
  the pilot.
- Ensure `heuristic` is not accidentally the visible default.

## Files Changed

- `web/ai_manager.py` -- swap `HybridOLSaBidder` browser wiring for `ActionValueBidder`
- `web/config.py` -- update model artifact env contract
- `web/routes.py` -- align model-selection and default behavior
- `web/templates/partials/model_select.html` -- rename visible model labels
- `.env.example` -- document new artifact variable
- `docs/01_core/DEPLOYMENT.md` -- update model config contract
- `tests/unit/hosted_play/test_ai_manager.py` -- new roster/default expectations
- `tests/unit/hosted_play/test_config.py` -- env parsing changes
- `tests/unit/hosted_play/test_routes.py` -- model-selection surface expectations

## Validation

### Pass/Fail Criteria

- [ ] **Unit tests:** `uv run python -m pytest tests/unit/hosted_play/test_ai_manager.py tests/unit/hosted_play/test_config.py -q`
  - Expected: all targeted tests pass with the new OLSa roster/default behavior.
- [ ] **Route surface:** `uv run python -m pytest tests/unit/hosted_play/test_routes.py -k model -q`
  - Expected: model-selection flow renders the new visible product model contract.
- [ ] **Wiring proof:** `rg -n "ActionValueBidder|full_ols_av|OLSa" web/ai_manager.py web/config.py web/templates`
  - Expected: new model wiring/naming exists in the browser app surface.
- [ ] **Integration check:** start the app locally and create a match using the visible browser model
  - Expected: match creation succeeds and the engine starts with the OLSa roster entry.

## Planned Outputs

- Browser-visible `OLSa` default model
- Updated env/deployment contract
- Tests proving the roster shift

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: ready after Phase 0.
- Next action: update the model-serving contract first, before moon/loner engine changes.
- Blockers: Phase 0 incomplete.
- Files with uncommitted changes: --
