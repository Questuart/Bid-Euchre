# Agent Handoff: C33 Ablation Report Refactor — Plan Development

## Your Task

Review the notes in `plans/c33_ablation_review_notes.md` and develop a detailed
implementation plan for refactoring the C33 ablation report and creating/modifying
supporting notebooks. The plan should be ready for a coding agent to execute.

**Output:** A written plan saved to `plans/c33_ablation_refactor_plan.md`.
Do NOT begin implementation.

---

## Context

### What is the C33 ablation?

The C33 ablation is an experiment that isolates the value of the Gaussian CDF
decision layer ("wrapper") in the hybrid_olsa bidder vs a simpler floor-based
threshold (olsa). Both bidders use identical OLS regression coefficients — the
only difference is how they decide whether to bid. The result: the wrapper adds
+0.21 net_eppd via "selective restraint" (avoiding bad bids, not finding better
ones).

### What's wrong with the current report?

The report (`docs/04_reports/r0/c33_ablation_report.md`) presents correct
results but:
1. Doesn't explain the architecture being ablated (reader must look elsewhere)
2. Results are point estimates only — no distributional detail
3. Matchup tables collapse team0/team1 into single rows
4. The 16.2% bid rate is confusingly low without explaining it's a competitive
   (not intrinsic) rate
5. The central claim ("selective restraint") is asserted but not demonstrated
   with evidence

### What are we building?

Three deliverables (see `plans/c33_ablation_review_notes.md` for full detail):
- **D1:** Refactored ablation report with new sections and expanded results
- **D2:** Violin plot addition to existing `notebooks/arc_d/r0/50_r0_matchups.py`
- **D3:** New notebook `notebooks/arc_d/r0/55_c33_ablation_deep_dive.py`

---

## Instructions for Plan Development

### Phase 1: Resolve open questions

Before planning, investigate these three questions (answers determine scope):

1. **Decision trace data availability:** Check whether the existing C33 ablation
   eval logs (JSONL in `data/runs/`) capture per-hand mu, sigma, P(make), and EV.
   Relevant files to check:
   - `src/bid_euchre/strategy/bidding.py` — look at `HybridOLSaBidder` and
     `OLSaBidder` classes for what gets logged during bid decisions
   - `src/bid_euchre/logging/` — JSONL log schema
   - `docs/01_core/DATA_CONTRACT.md` — logged fields

   If per-hand decision traces are NOT logged, the notebook (D3) will need to
   replay hands through both decision layers using the saved model artifact
   (`data/artifacts/arc_d/r0/hybrid_r0.json`). This changes the notebook
   complexity significantly.

2. **EV formula:** Read the exact EV computation in `HybridOLSaBidder` in
   `src/bid_euchre/strategy/bidding.py`. Capture the precise reward/penalty
   terms (are they trick-based? point-based? bid-dependent?). This is needed
   for the overlaid histograms in D3.

3. **Intrinsic bid rate provenance:** The notes reference hybrid_olsa intrinsic
   bid rates of ~62.5% and ~82.8% from different contexts. Check:
   - `docs/04_reports/r0/comparator_rankings.md`
   - `docs/04_reports/r0/h2h_battery_analysis.md`
   - `docs/04_reports/r0/r0_promotion_report.md`

   Determine which run/seed/context produced each number so the report can
   cite them accurately.

### Phase 2: Develop the plan

Structure the plan with:

1. **PR strategy** — How many PRs? What goes in each? Suggested:
   - PR 1: Report refactor (D1-a architecture section + D1-b results expansion
     + bid rate clarification) — pure writing, no data dependency
   - PR 2: New notebook (D3) + report evidence section (D1-c) + violin plot (D2)

   But adjust based on what you learn in Phase 1 (if replay is needed, D3 may
   be larger and warrant its own PR).

2. **Per-deliverable spec** — For each deliverable:
   - Exact files to create/modify (full paths)
   - What changes in each file (section-level for report, cell-level for notebooks)
   - Dependencies on other deliverables
   - Acceptance criteria (what does "done" look like?)

3. **Notebook D3 detailed spec** — This is the most complex deliverable:
   - Data loading strategy (existing logs vs replay)
   - Required imports and library functions to use
   - Each section's inputs, computation, and outputs
   - Chart specifications (axes, faceting, colors, expected visual pattern)
   - Assert-style gates (what sanity checks should the notebook enforce?)

4. **Report D1 section drafts** — For new sections (§3 Architecture Comparison,
   §5 Decision Divergence Evidence), provide draft outlines with placeholder
   references to notebook outputs. Don't write final prose, but specify:
   - Section heading
   - Subsection structure
   - What each paragraph covers
   - Where notebook figures/tables are referenced

5. **Validation checklist** — What to verify before the PR:
   - `make check` passes
   - `make notebook-check` passes (Jupytext sync, outputs cleared)
   - All charts faceted by contract_type
   - All matchup tables show team0/team1
   - Report cross-references are valid
   - No data artifacts committed

---

## Key Files to Read

Read these files during plan development (in priority order):

### Must-read
- `plans/c33_ablation_review_notes.md` — the review notes driving this plan
- `docs/04_reports/r0/c33_ablation_report.md` — the report being refactored
- `src/bid_euchre/strategy/bidding.py` — HybridOLSaBidder and OLSaBidder classes
  (decision logic, EV formula, what gets logged)
- `src/bid_euchre/reporting/evaluator.py` — bid_rate formula, metric computation

### Should-read
- `notebooks/arc_d/r0/50_r0_matchups.py` — existing matchup notebook (D2 target)
- `notebooks/arc_d/r0/30_feature_outcome_eval.py` — example of notebook structure,
  assert gates, chart patterns to follow
- `docs/04_reports/r0/h2h_battery_analysis.md` — bid rate numbers in context

### Reference
- `CLAUDE.md` — project conventions (worktree workflow, `uv run`, ruff, etc.)
- `.claude/rules/05_rigor.md` — statistical rigor requirements
- `docs/01_core/DATA_CONTRACT.md` — logging schema
- `.github/pull_request_template.md` — PR template

---

## Conventions

- All charts/tables MUST be faceted by contract_type or justify pooling
- All matchup tables MUST show team0 and team1 separately
- Always distinguish competitive (H2H) bid rate from intrinsic (comparator) bid rate
- Notebooks: edit .py files (Jupytext), not .ipynb
- Notebook naming: 55_ prefix (between existing 50_ and future 60_)
- All code changes in worktrees, never on main
- Run `make check-quiet` before claiming done
- Use `uv run` for all Python commands
