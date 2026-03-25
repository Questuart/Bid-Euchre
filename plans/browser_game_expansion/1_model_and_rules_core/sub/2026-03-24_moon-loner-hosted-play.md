# SP-1-02: Moon/Loner Hosted-Play Plumbing

**ID:** SP-1-02
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 1 -- Model and Rules Core
**Status:** proposed
**Owner:** --

---

## Inputs

- `src/bid_euchre/hosted_play/engine.py`
- `src/bid_euchre/hosted_play/state.py`
- `web/db.py`
- `web/schema.sql`
- `web/routes.py`
- `src/bid_euchre/strategy/bidding.py` -- `BidAction`, `enumerate_legal_actions`
- `src/bid_euchre/sim/exchange.py` -- `perform_exchange(...)`
- `src/bid_euchre/sim/simulation.py` -- moon exchange and loner sit-out reference flow
- `src/bid_euchre/scoring.py`
- existing hosted-play unit/integration/export tests

## Assumptions

- Moon and loner are launch blockers for the expansion initiative.
- The hosted-play engine must reuse canonical exchange/scoring/rules logic
  instead of open-coding new behavior.
- The existing four-player assumptions in hosted play are insufficient and must
  be replaced rather than patched with UI-only behavior.

## Dependencies

- `SP-0-01` complete
- `SP-1-01` complete or at least the new OLSa roster contract locked

## Plan

### Step 1: Extend hand state for bid type and active-seat metadata

- Add explicit bid-type state so hosted play does not infer everything from
  `winning_bid` alone.
- Add active-seat or sitting-out metadata for loner hands.
- Add exchange-state fields for moon hands if needed for resume/logging/UI.

### Step 2: Replace regular-only auction logic

- Use canonical legal-action generation for moon/loner.
- Track the winning bid by bid rank/overcall semantics, not `bid.n` only.
- Ensure dealer take-away cases remain correct if supported.

### Step 3: Add moon exchange and loner trick flow

- Run `perform_exchange(...)` after a moon win and before trick play starts.
- Support three-player trick order for loner hands.
- Ensure completed-trick and next-lead logic remain correct.

### Step 4: Extend persistence and export compatibility

- Add new DB fields where queryable summary columns are needed
  (`winning_bid_type`, `sitting_out_seat`, etc.).
- Keep serialized hand state/export/replay compatible with the new semantics.
- Update route logging and any replay assumptions accordingly.

### Step 5: Prove both old and new rules paths

- Add deterministic unit and integration tests for:
  - regular auction still working
  - moon overcalls
  - loner overcalls
  - moon exchange
  - loner partner sit-out
  - regular flow regression

## Files Changed

- `src/bid_euchre/hosted_play/state.py`
- `src/bid_euchre/hosted_play/engine.py`
- `web/db.py`
- `web/schema.sql`
- `web/routes.py`
- `web/export.py`
- `docs/01_core/HOSTED_PLAY_RULES.md`
- `tests/unit/hosted_play/test_state.py`
- `tests/unit/hosted_play/test_engine.py`
- `tests/unit/hosted_play/test_db.py`
- `tests/unit/hosted_play/test_routes.py`
- `tests/unit/hosted_play/test_export.py`
- `tests/integration/hosted_play/test_data_capture.py`

## Validation

### Pass/Fail Criteria

- [ ] **Unit tests:** `uv run python -m pytest tests/unit/hosted_play/test_engine.py tests/unit/hosted_play/test_state.py tests/unit/hosted_play/test_db.py -q`
  - Expected: new moon/loner and regular-regression tests all pass.
- [ ] **Route/integration tests:** `uv run python -m pytest tests/unit/hosted_play/test_routes.py tests/integration/hosted_play/test_data_capture.py -q`
  - Expected: routes and logging remain correct for regular + moon/loner hands.
- [ ] **Replay/export proof:** `uv run python -m pytest tests/unit/hosted_play/test_export.py -q`
  - Expected: export/replay still accepts the expanded hand state.
- [ ] **Integration-level proof:** execute a seeded hosted-play hand that reaches moon and loner code paths
  - Expected: hosted-play outcomes match canonical exchange/scoring/trick-order expectations.
- [ ] **Regression proof:** existing all-pass redeal and regular hand flows remain green
  - Expected: no prior hosted-play behavior regresses.

## Planned Outputs

- Hosted-play moon/loner support across engine/state/persistence/logging
- Updated hosted-play rules contract
- Regression tests proving old and new paths

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: ready after `SP-1-01`.
- Next action: land deterministic core/state/persistence work before UI polish.
- Blockers: Phase 0 incomplete; roster migration not yet executed.
- Files with uncommitted changes: --
