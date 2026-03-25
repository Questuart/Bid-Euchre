# SP-4-01: Browser Automation, Smoke, and Pilot Proving

**ID:** SP-4-01
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 4 -- Validation and Launch
**Status:** proposed
**Owner:** --

---

## Inputs

- `plans/browser_game_expansion/proving_matrix.md`
- `scripts/internal/smoke_hosted.sh`
- `docs/01_core/DEPLOYMENT.md`
- Phases 2 and 3 completed browser surface
- Claude browser-testing research results from 2026-03-24

## Assumptions

- Repo-owned browser E2E tests are required for pilot readiness.
- Claude-direct browser testing should be wired through Playwright/MCP when
  possible.
- Human proving is reserved for real-device and authorization-sensitive gaps.

## Dependencies

- Phase 2 complete
- Phase 3 complete
- `SP-0-01` complete

## Plan

### Step 1: Add the repo-owned browser E2E suite

- Add browser E2E tests that run against the real hosted-play app.
- Cover regular flow, moon/loner flow, hand pacing, and invite-code flow.

### Step 2: Add Claude-direct browser testing support

- Add project-scoped MCP/browser-testing config and a short runbook.
- Keep localhost/browser automation recoverable and documented.

### Step 3: Upgrade smoke and full regression commands

- Extend smoke scripts for the expanded app surface.
- Ensure unit/integration/E2E can be run as one launch gate.

### Step 4: Execute the automated proving matrix

- Run the full automated stack and record evidence in checkpoints.

### Step 5: Execute minimal human proving

- Real iPhone Safari smoke
- Production deployment approval
- Live invite redemption if still needed

## Files Changed

- `tests/e2e/hosted_play/` -- NEW browser E2E suite
- `.mcp.json` -- NEW project-scoped Claude browser-testing config
- `scripts/internal/smoke_hosted.sh`
- `scripts/internal/` -- any new browser smoke helper
- `docs/01_core/HOSTED_PLAY_PROVING_CHECKLIST.md`
- `docs/01_core/DEPLOYMENT.md`
- `plans/browser_game_expansion/proving_matrix.md`
- `tests/integration/hosted_play/test_postgres_smoke.py`

## Validation

### Pass/Fail Criteria

- [ ] **E2E suite:** `uv run python -m pytest tests/e2e/hosted_play -q`
  - Expected: happy path, moon/loner path, and invite-code path all pass.
- [ ] **Full regression:** `uv run python -m pytest tests/unit/hosted_play tests/integration/hosted_play tests/e2e/hosted_play -q`
  - Expected: all hosted-play validation passes together.
- [ ] **Smoke proof:** `bash scripts/internal/smoke_hosted.sh`
  - Expected: local Docker smoke still passes on the expanded app.
- [ ] **Claude-direct proof:** documented local browser smoke via MCP/browser-testing path
  - Expected: Claude can reach and exercise the local browser game directly.
- [ ] **Human proving:** execute required runs from `proving_matrix.md`
  - Expected: all required human gates recorded as pass or explicitly blocked.

## Planned Outputs

- Repo-owned browser E2E suite
- Claude-direct browser-testing path
- Expanded smoke/regression commands
- Final proving evidence package

## Observed Outputs

_To be filled during execution._

## Outcome

_Filled after completion._

- Status: proposed
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: ready after the browser surface and access flow stabilize.
- Next action: stand up E2E first, then layer on the Claude-direct browser path and final human proving.
- Blockers: Phases 2 and 3 incomplete.
- Files with uncommitted changes: --
