# R0 Notebook Plan Meta-Review Handoff (For Planning Agent)

Date: 2026-02-25
Scope reviewed:
- `plans/r0_10_feature_health_review.md`
- `plans/r0_notebook_execution_plan.md`

## Objective

Provide an execution-focused meta-review of the R0 notebook plan, including systemic risks, process improvements, and resolved alignment decisions incorporated into implementation guidance.

## Findings (Ordered by Severity)

### F1 (High): Final verification path does not execute Arc D R0 notebooks

Impact:
- Current execution-plan verification can report success without running `notebooks/arc_d/r0/*.ipynb`.
- This weakens confidence in runtime correctness before promotion-oriented reporting.

Evidence:
- Execution plan verification calls `make notebook-run` / `make notebook-run-full` (`plans/r0_notebook_execution_plan.md:529-531`).
- `Makefile` default targets run `scripts/run_notebooks.py` with default pattern (`Makefile:83-89`).
- Runner default pattern is `notebooks/phase0_bidless/*.ipynb` (`scripts/run_notebooks.py:203`).

Planning implication:
- Add explicit Arc D pattern execution gate (or use `make notebook-run-arc-d`) at phase closeout.

---

### F2 (High): Report destination path conflicts with current repo standard

Impact:
- Plan introduces output path churn and potential tool/doc fragmentation.

Evidence:
- New execution plan targets `docs/04_reports/arc_d/` for R0 promotion report (`plans/r0_notebook_execution_plan.md:472`).
- Existing R0 reports and prior planning standardize under `docs/04_reports/arc_d_v1/r0/` (`plans/arc_d_reporting_overhaul.md:820,830`; existing artifacts in `docs/04_reports/arc_d_v1/r0/`).
- Review doc formal report targets also point to `docs/04_reports/arc_d/` (`plans/r0_10_feature_health_review.md:1504-1507`).

Planning implication:
- Standardize final destination to one path before work starts (recommended: `docs/04_reports/arc_d_v1/r0/`).

---

### F3 (Medium): Issue-to-PR coverage map is not fully consistent

Impact:
- Risk of “planned but unimplemented” issue closure and downstream review churn.

Evidence:
- C15 acceptance expects updates in `10_` and `40_` (`plans/r0_10_feature_health_review.md:1356`), but PR-2a only scopes `10_` (`plans/r0_notebook_execution_plan.md:190-203`).
- C34/C36 acceptance references both `30_` and `40_` (`plans/r0_10_feature_health_review.md:1375,1377`), but PR-2d scopes only `30_` (`plans/r0_notebook_execution_plan.md:262-275`).
- C20 acceptance references `10_` and `20_` sections (`plans/r0_10_feature_health_review.md:1361`), while execution scope only explicitly includes `10_` in PR-2a.
- C23 Tier 1 normalization includes `10_` S4.3/S4.4 (`plans/r0_10_feature_health_review.md:1515-1516`), but execution plan assigns Tier 1 only to 20_ and 40_ (`plans/r0_notebook_execution_plan.md:218-229,345-355`).

Planning implication:
- Add a strict “issue -> PR -> file/section” trace matrix and reconcile mismatches pre-implementation.

---

### F4 (Medium): Parallelism model underestimates same-file merge contention

Impact:
- “Parallel” execution may degrade delivery speed due to rebases/conflict resolution.

Evidence:
- Phase 1 PRs all touch overlapping notebook files (`plans/r0_notebook_execution_plan.md:56,62-67,142,168-171`).
- Phase 2 splits same notebook across multiple PRs (e.g., `30_` in PR-2c/2d/2e; `40_` in PR-2f/2g) (`plans/r0_notebook_execution_plan.md:241-248,266-267,293-294,317,348`).

Planning implication:
- Re-bucket PRs by file ownership or define strict landing order within each notebook stream.

---

### F5 (Medium): `points_won` null semantics are ambiguous vs existing scoring contract

Impact:
- Mixed semantics may cause inconsistent interpretation across notebooks/reporting.

Evidence:
- Plan snippet proposes `points_won=None` when bidder info is missing (`plans/r0_notebook_execution_plan.md:37` and review snippet `plans/r0_10_feature_health_review.md:1411-1423`).
- Core scoring function currently returns trick-based points in no-bid case (`src/bid_euchre/scoring.py:29-38`).

Planning implication:
- Decide single scoring contract for no-bid rows before PR-0 and encode tests accordingly.

## Process Improvements (Goal-Oriented)

1. Move from issue-count tracking to phase exit gates tied to promotion confidence:
   - Data semantics gate
   - Runtime execution gate
   - Analytical confidence gate
   - Reporting reproducibility gate
2. Reduce merge friction by aligning PRs to notebook boundaries, not only concept boundaries.
3. Require Arc D notebook runtime validation at each phase close, not only notebook hygiene checks.
4. Reuse existing report-generation path where possible to reduce manual report drift.

## Resolved Alignment Decisions (Locked for Implementation)

Question: Should R0 formal outputs stay under `docs/04_reports/arc_d_v1/r0/` (existing convention) instead of creating `docs/04_reports/arc_d/`?
Recommendation: Keep `docs/04_reports/arc_d_v1/r0/` and standardize naming there.
Tradeoff: You lose arc-folder isolation but keep continuity with existing tooling and history.
Why: The stated goal is execution-ready delivery, and path churn adds migration risk without analytical upside.
Decision: RESOLVED — use `docs/04_reports/arc_d_v1/r0/` as canonical output path for R0 formal reports.
Incorporation: Update both planning docs to replace `docs/04_reports/arc_d/` targets with `docs/04_reports/arc_d_v1/r0/`.

Question: Do you want to collapse the 17 PRs into fewer notebook-centric PRs to reduce merge conflict risk?
Recommendation: Yes, collapse to infra + notebook-focused streams + reports.
Tradeoff: Individual PRs get slightly larger, but integration speed and reliability improve.
Why: The stated goal is end-to-end execution, and current “parallel” plan has heavy same-file overlap.
Decision: RESOLVED — re-bucket PRs into notebook-centric streams to reduce same-file contention.
Incorporation: Revise phase plan to avoid parallel PRs touching the same notebook when not strictly necessary.

Question: For `points_won` when `winning_bid`/`bidder_position` is missing, should behavior match `compute_points()` (tricks-based) or remain `None`?
Recommendation: Match `compute_points()` for consistency.
Tradeoff: You include computed values on no-bid rows, but keep one scoring contract across codepaths.
Why: The stated goal includes robust cross-notebook analysis, and metric semantics should not diverge by loader.
Decision: RESOLVED — align dataset `points_won` semantics with `compute_points()` no-bid behavior.
Incorporation: PR-0 implementation and tests must encode no-bid rows as tricks-based points, not `None`.

Question: Should we explicitly add missing scope mappings now for C15/C20/C23-T1/C34/C36 before implementation starts?
Recommendation: Yes, update the execution plan matrix now.
Tradeoff: Slight planning overhead now avoids partial completion later.
Why: The stated goal is agent-handoff-ready execution, which needs one-to-one traceability.
Decision: RESOLVED — complete issue-to-PR trace matrix before code implementation starts.
Incorporation: Add explicit owner PR + target file/section mapping for C15/C20/C23-T1/C34/C36.

Question: Should phase completion require Arc D runtime execution (`make notebook-run-arc-d` or explicit pattern) in addition to `make notebook-check`?
Recommendation: Yes, require SMOKE runtime at minimum for each phase closeout.
Tradeoff: Extra runtime cost, higher confidence against runtime regressions.
Why: The stated goal is promotion-quality decisions, and hygiene checks alone do not validate execution behavior.
Decision: RESOLVED — phase closeout requires Arc D runtime execution (SMOKE minimum).
Incorporation: Add phase-level validation commands that target `notebooks/arc_d/r0/*.ipynb` explicitly.

## Planning Agent Action Checklist

1. Record these five resolved decisions in both planning docs as normative constraints.
2. Update report output paths to one canonical location.
3. Add explicit Arc D runtime verification commands to each phase exit criterion.
4. Reconcile issue-to-PR mapping for C15/C20/C23-T1/C34/C36.
5. Rework PR grouping to minimize same-file contention.
6. Confirm `points_won` no-bid semantics and lock test expectations.

## Definition of Done for Revised Plan

- Every issue in scope maps to exactly one owner PR (or explicit deferred item).
- Every phase has deterministic validation commands that actually run Arc D R0 notebooks.
- Report output paths align with existing repo conventions.
- Scoring semantics for `points_won` are explicitly defined and testable.
- Parallel execution plan reflects merge reality, not only conceptual independence.
