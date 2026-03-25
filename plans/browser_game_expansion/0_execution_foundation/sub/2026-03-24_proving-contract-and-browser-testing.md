# SP-0-01: Proving Contract and Browser Testing Foundation

**ID:** SP-0-01
**Date:** 2026-03-24
**Parent:** `plans/browser_game_expansion/governing_plan.md` -- Phase 0 -- Execution Foundation
**Status:** in_progress
**Owner:** Codex

---

## Inputs

- `plans/browser_game/governing_plan.md` -- completed browser baseline
- `plans/browser_game/3_frontend_product/checkpoints.md` -- confirms shipped browser vertical slice
- `scripts/internal/smoke_hosted.sh` -- current smoke baseline
- `docs/01_core/DEPLOYMENT.md` -- current deploy/runbook baseline
- `docs/01_core/HOSTED_PLAY_RULES.md` -- current hosted-play rules contract
- Official tooling references gathered on 2026-03-24:
  - Anthropic Claude Code MCP docs
  - Anthropic computer-use docs
  - Microsoft `playwright-mcp`
  - Playwright browser/emulation docs

## Assumptions

- Claude-driven direct browser testing is a hard requirement for this expansion.
- `cmux` is an optional operational aid, not a required source of truth.
- The repo may add a project-scoped browser-testing configuration if it is
  easy to recover locally and documented clearly.
- Human proving should be kept to the smallest viable set.

## Dependencies

- None beyond the activation of the expansion initiative.

## Plan

### Step 1: Lock the proving checklist and validation tiers

- Create the durable proving contract for old and new browser features.
- Distinguish automated validation from user-proving so later phases do not
  overuse manual checks.
- Name the final docs and test paths that later sub-plans must populate.

### Step 2: Choose the repo-owned browser automation stack

- Lock a committed E2E test path for the repo.
- Lock the direct Claude browser-testing path through Playwright/MCP.
- Record fallback behavior if MCP is unavailable locally.

### Step 3: Lock migration and smoke expectations

- Define how schema-changing phases will migrate data.
- Define which smoke commands must exist by the time Phase 4 closes.
- Require production/staging snapshot discipline before destructive changes.

### Step 4: Update doc targets for implementation sub-plans

- Ensure later phases know exactly which docs they must update:
  hosted-play rules, deployment guide, proving checklist, launch runbook.

## Files Changed

- `plans/browser_game_expansion/governing_plan.md` -- execution contract
- `plans/browser_game_expansion/proving_matrix.md` -- proving tiers and user-run gate
- `plans/browser_game_expansion/4_validation_and_launch/checkpoints.md` -- proving execution target
- `docs/01_core/HOSTED_PLAY_PROVING_CHECKLIST.md` -- NEW, implementation target
- `.mcp.json` -- NEW, optional project-scoped Claude browser-testing config
- `tests/e2e/hosted_play/` -- NEW, repo-owned browser E2E test path

## Validation

### Pass/Fail Criteria

- [ ] **Plan wiring:** `find plans/browser_game_expansion -maxdepth 2 -type f | sort`
  - Expected: governing plan, registry, roadmap, proving matrix, and phase checkpoints all exist.
- [ ] **Doc target proof:** `rg -n "HOSTED_PLAY_PROVING_CHECKLIST|tests/e2e/hosted_play|\\.mcp\\.json" plans/browser_game_expansion`
  - Expected: all three targets are referenced by the phase/sub-plan package.
- [ ] **Smoke baseline proof:** `bash scripts/internal/smoke_hosted.sh`
  - Expected: existing hosted-play smoke still passes before any expansion code is written.
- [ ] **Integration-level proof:** `uv run python -m pytest tests/integration/hosted_play/test_postgres_smoke.py -q`
  - Expected: current Postgres smoke passes so later schema changes have a baseline.

## Planned Outputs

- Durable proving matrix
- Locked browser-testing stack decision
- Locked migration/smoke contract
- Concrete implementation targets for docs and E2E harness

## Observed Outputs

- Plan package created under `plans/browser_game_expansion/`
- Proving matrix created at `plans/browser_game_expansion/proving_matrix.md`

## Outcome

_Filled after completion._

- Status: in_progress
- PR: pending
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: phase package exists; implementation targets and proving tiers are locked at plan level.
- Next action: create the repo-owned proving checklist doc and lock the concrete E2E/MCP configuration path before Phase 1 starts.
- Blockers: no committed E2E harness or proving checklist doc exists yet.
- Files with uncommitted changes: planning docs only
