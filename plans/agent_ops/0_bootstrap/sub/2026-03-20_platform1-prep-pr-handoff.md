# Platform-1 Prep PR Handoff

**ID:** SP-0-02
**Date:** 2026-03-20
**Parent:** `plans/agent_ops/governing_plan.md` -- Phase 0 dependencies (§4.3) and `Platform-1` handoff boundary
**Status:** in_progress
**Owner:** Opus

---

## Inputs

- Input 1: `plans/agent_ops/governing_plan.md` -- canonical initiative scope and the boundary between Phase 0 cleanup and actual `Platform-1` work.
- Input 2: `plans/agent_ops/0_bootstrap/checkpoints.md` -- bootstrap progress log and current phase context.
- Input 3: `plans/agent_ops/sub_plan_registry.md` -- active sub-plan index.
- Input 4: `plans/agent_ops/0_bootstrap/sub/2026-03-20_platform-entry-hardening.md` -- superseded broad plan; keep only the residual cleanup insights.
- Input 5: `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md` -- operator checklist that still needs reconciliation to current shipped behavior.
- Input 6: `scripts/internal/ops.py` -- CLI entrypoint for status/health/worktree/index surfaces.
- Input 7: `src/bid_euchre/__init__.py` -- current package import side effects.
- Input 8: `src/bid_euchre/ops/status.py` and `src/bid_euchre/ops/worktrees.py` -- runtime health, lane summaries, and worktree hygiene surfaces.
- Input 9: `tests/unit/test_ops_cli.py`, `tests/unit/test_ops_status.py`, `tests/unit/test_ops_worktrees.py` -- existing regression coverage for the prep-PR scope.

## Assumptions

- Treat `Platform-1` as **unblocked** for planning purposes; this PR is cleanup and reconciliation, not a gate-closure PR.
- Do **not** reopen review-surface bridge work, merge-truth design, or broader pre-Platform-1 debates inside this slice.
- The only substantive code-prep items left are:
  - import-light / lazy startup cleanup for ops entrypoints
  - runtime hygiene cleanup for worktree/health noise
  - docs/checkpoint reconciliation so Phase 0 durable state matches current reality
- If the work reveals a concrete, still-open blocker to `Platform-1`, record it precisely and stop broadening scope.

## Dependencies

- `SP-0-01` -- superseded; this plan inherits only its residual cleanup items.
- No additional bridge PR is required before this prep PR.

## Plan

### Step 1: Make the ops/control-plane import path lighter
- Reduce startup coupling from `scripts/internal/ops.py` into the full research package.
- Prefer the smallest safe fix:
  - make `src/bid_euchre/__init__.py` import-light or lazy
  - keep package-level behavior stable for current consumers
- Goal: ops entrypoints should not pay unnecessary experiments/strategy import cost before reaching control-plane code.

### Step 2: Clean up runtime hygiene surfaced by `ops.py health`
- Reconcile or prune the currently unregistered worktrees that make health output noisy.
- Tighten any obviously misleading health/status messaging only if the change is narrow and directly tied to cleanup.
- Do not reopen larger lane-state semantics unless a concrete low-risk fix is required by the cleanup.

### Step 3: Reconcile durable docs/checkpoints with current Platform-1 posture
- Update bootstrap durable state so it no longer implies the bridge gate is still blocked if the shipped repo state says otherwise.
- Mark `SP-0-01` as superseded and keep `SP-0-02` explicitly non-blocking.
- Update the operator-facing checklist and checkpoint log only to reflect current shipped reality, not to redesign the roadmap.

### Step 4: Ship one focused prep PR
- Keep this as a single-concept PR: control-plane cleanup before/alongside `Platform-1`.
- Avoid bundling actual `Platform-1` implementation, message-bus design, or new orchestration capabilities.

## Files Changed

- `src/bid_euchre/__init__.py` -- import-light / lazy package initialization for ops-friendly startup.
- `scripts/internal/ops.py` -- only if needed for startup path, health wording, or narrow cleanup plumbing.
- `src/bid_euchre/ops/worktrees.py` -- only if needed for bounded worktree hygiene or status cleanup.
- `src/bid_euchre/ops/status.py` -- only if a minimal cleanup-related adjustment is needed.
- `docs/02_agent/PLATFORM_ENTRY_CHECKLIST.md` -- reconcile checklist text/status with current shipped state.
- `plans/agent_ops/0_bootstrap/checkpoints.md` -- record the supersession and current non-blocking prep scope.
- `plans/agent_ops/sub_plan_registry.md` -- update sub-plan statuses.
- `tests/unit/test_ops_cli.py` -- regression coverage for prep-PR behavior.
- `tests/unit/test_ops_status.py` -- regression coverage if status semantics change.
- `tests/unit/test_ops_worktrees.py` -- regression coverage if cleanup logic changes.

## Validation

- [ ] Targeted tests: `uv run pytest -q tests/unit/test_ops_cli.py tests/unit/test_ops_status.py tests/unit/test_ops_worktrees.py`
- [ ] Startup smoke: `uv run python scripts/internal/ops.py --json status`
- [ ] Health smoke: `uv run python scripts/internal/ops.py --json health`
- [ ] Worktree smoke: `uv run python scripts/internal/ops.py --json worktrees`
- [ ] Final repo validation: `make check-quiet`

## Planned Outputs

- One focused prep PR that leaves the control plane cleaner ahead of `Platform-1`.
- Reduced ops startup coupling from package import side effects.
- Cleaner runtime health/worktree surface with fewer stale or distracting warnings.
- Durable docs/checkpoints that show `Platform-1` as unblocked and this work as non-blocking cleanup.

## Observed Outputs

_Filled during/after execution._

- Output 1: --
- Output 2: --

## Outcome

_Filled after completion._

- Status: proposed
- PR: --
- Deviations from plan: --
- Issues discovered: --

## Handoff

- Current state: this is the active prep-PR handoff. `SP-0-01` is superseded and should not be used for execution.
- Next action:
  1. Refresh `plans/agent_ops/governing_plan.md`, `plans/agent_ops/0_bootstrap/checkpoints.md`, this sub-plan, and the superseded `SP-0-01`.
  2. Draft/refine the concrete execution plan for this narrow PR.
  3. Spawn at least one reviewer agent to review that execution plan before major edits.
  4. Build a task list covering implementation, validation, and PR shipment.
  5. Assess safe parallelism and only delegate disjoint write scopes.
  6. Execute end to end autonomously:
     - implement
     - test
     - run smoke/failure-injection validation
     - commit
     - open or update the PR
     - include validation evidence in the PR body
- Suggested PR title:
  - `ops: cleanup control-plane startup and runtime hygiene before Platform-1`
- Suggested PR body focus:
  - import-light ops startup
  - worktree/health cleanup
  - Phase 0 checklist/checkpoint reconciliation
- Blockers: none recorded; if a real `Platform-1` blocker appears, record it precisely instead of expanding this PR.
- Files with uncommitted changes:
  - `plans/agent_ops/0_bootstrap/sub/2026-03-20_platform-entry-hardening.md`
  - `plans/agent_ops/0_bootstrap/sub/2026-03-20_platform1-prep-pr-handoff.md`
  - `plans/agent_ops/sub_plan_registry.md`
  - `plans/agent_ops/0_bootstrap/checkpoints.md`
