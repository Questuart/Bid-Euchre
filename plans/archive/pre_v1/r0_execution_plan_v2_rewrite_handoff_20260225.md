# R0 Execution Plan v2 Rewrite Handoff (Agent-Ready)

Date: 2026-02-25
Status: Ready for planning-agent execution
Decision basis: User approved latest re-review findings and recommendations.

## Objective

Rewrite the R0 notebook planning docs to incorporate F1-F5 fixes and locked decisions, with a conflict-minimized PR structure and executable verification gates.

## Source Documents To Update

1. `plans/r0_notebook_execution_plan.md` (full rewrite: v1 -> v2)
2. `plans/r0_10_feature_health_review.md` (targeted Meta-Review Addendum updates)

## Locked Decisions (Do Not Reopen)

1. Report output path is `docs/04_reports/r0/` (not `docs/04_reports/arc_d/`).
2. PR structure is notebook-centric (17 PRs -> 9 PRs).
3. `points_won` semantics align with `compute_points()` no-bid behavior and are never `None`.
4. Full issue-to-PR trace matrix is required (all 58 issues covered, no gaps).
5. Phase exit requires Arc D runtime execution for R0 notebooks.
6. PR-8 (formal reports) depends on Phase 2 completion (not Phase 1 only).
7. PR-6 prefix-convention test should run after notebook fixes it validates.
8. Verification grep must be scoped to revised R0 planning docs, not all `plans/`.

## Required Rewrite: `plans/r0_notebook_execution_plan.md`

Implement v2 structure with 9 PRs:

- PR-0 (Phase 0): C32 points infra + Arc D runner fix in Makefile and notebook runner.
- PR-1 (Phase 1): `10_feature_health` all assigned fixes.
- PR-2 (Phase 1): `20_outcome_health` all assigned fixes.
- PR-3 (Phase 1): `30_feature_outcome_eval` all assigned fixes.
- PR-4 (Phase 1): `40_r0_baseline` all assigned fixes except extracted §2/§4.
- PR-5 (Phase 1): `50_r0_matchups` all assigned fixes (excluding deferred infra).
- PR-6 (Phase 1/late): C59 prefix-convention contract test updates (depends PR-1..PR-5).
- PR-7 (Phase 2): new `25_auction_health` + extract `40_` §2/§4.
- PR-8 (Phase 2): formal reports under `docs/04_reports/r0/` (depends PR-1..PR-7 / Phase 2 complete).

Deferred items (explicitly mark as deferred):

- C50 (H2H infra)
- C33 (ablation)
- C57 (decision boundary)

### F1 Fix Requirements

PR-0 must include both:

1. Makefile Arc D target default pattern update to recursive Arc D notebooks.
2. `scripts/run_notebooks.py` update so `**` glob patterns work (`recursive=True` in `glob.glob` call).

Phase exit gates must include:

`make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"`

### F2 Fix Requirements

All report paths in execution plan must point to `docs/04_reports/r0/`.

### F3 Fix Requirements

Add explicit issue-to-PR trace matrix:

- Must include all 58 issues.
- Must indicate deferred items as deferred (not missing).
- Must reconcile known cross-notebook issues:
  - C15 in PR-1 and PR-4
  - C20 in PR-1 and PR-2
  - C23 Tier 1 in PR-1, PR-2, PR-4
  - C34 in PR-3 and PR-4
  - C36 in PR-3 and PR-4

### F4 Fix Requirements

Document file ownership matrix showing no same-file contention across Phase 1 notebook PRs.

### F5 Fix Requirements

C32 implementation notes must specify:

- Use `compute_points(winning_bid, bidder_position, t0, t1)` once per record.
- Map team-level points to per-seat rows by team membership.
- No-bid rows use tricks-based points from scoring contract.
- `points_won` is never `None`.

## Required Targeted Edits: `plans/r0_10_feature_health_review.md`

1. In Formal Report Targets, replace `docs/04_reports/arc_d/` with `docs/04_reports/r0/`.
2. Add a section for resolved alignment decisions (reflecting locked decisions above).
3. Update Dependency DAG to the 9-PR notebook-centric v2 structure.
4. Update C32 reference snippet to use `compute_points()` contract and clarify never-`None` `points_won`.
5. Clarify C59 execution model:
   - Fixes distributed across notebook-owned PRs.
   - PR-6 is test/contract enforcement, not bulk notebook edits.

## Acceptance Criteria for Planning Rewrite

1. `plans/r0_notebook_execution_plan.md` shows 9 PRs with corrected dependencies.
2. PR-0 scope includes both Makefile and `scripts/run_notebooks.py` recursive-glob compatibility.
3. PR-8 dependency is Phase 2 complete (or equivalent explicit dependency on PR-1..PR-7).
4. PR-6 is sequenced after notebook fixes it validates.
5. All report targets in both docs use `docs/04_reports/r0/`.
6. Trace matrix covers all 58 issues with no unintentional gaps.
7. Deferred list explicitly contains C50, C33, C57.

## Verification Commands (Scoped and Executable)

1. Confirm no old report path in revised docs only:

`rg -n "docs/04_reports/arc_d" plans/r0_notebook_execution_plan.md plans/r0_10_feature_health_review.md`

Expected: no matches.

2. Confirm recursive glob support in runner:

`rg -n "glob\\.glob\\(.*recursive=True" scripts/run_notebooks.py`

Expected: one match in notebook discovery path.

3. Confirm Arc D recursive default in Makefile target:

`rg -n "notebook-run-arc-d|notebooks/arc_d/\\*\\*/\\*\\.ipynb" Makefile`

Expected: target present and recursive default pattern present.

4. Confirm deferred items are explicit in v2 plan:

`rg -n "C50|C33|C57|Deferred" plans/r0_notebook_execution_plan.md`

5. Confirm trace matrix exists and includes all issue IDs:

`rg -n "Trace Matrix|C1|C59" plans/r0_notebook_execution_plan.md`

Expected: matrix section present and issue coverage complete.

## Handoff Notes for Planning Agent

1. Keep this as a planning-only rewrite; do not implement source/notebook code changes in this task.
2. Preserve existing naming and conventions already used in `docs/04_reports/r0/`.
3. Avoid introducing additional PR splits that reintroduce same-file contention.
4. If ambiguity appears, prefer consistency with locked decisions in this handoff.
