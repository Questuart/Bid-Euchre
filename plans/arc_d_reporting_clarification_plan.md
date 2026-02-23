# Plan: Clarify Reporting Requirements in Arc D Execution Plan

**Date:** 2026-02-22
**Type:** Doc-only plan (updates `plans/arc_d_execution_plan.md`)
**Motivation:** PR #400 (R0b) shipped without notebook, rung report, or dashboard output.
The plan's own R0b DoD doesn't require them, but the global blind-test flow (§10 line 1780)
says "REPORT -> write rung report, update registry, regenerate arc dashboard" applies to
*every rung*. The R1b–R5b template (step 10, line 1627) also mandates these. This creates
a contradictory state that needs resolution.

---

## Problem: Three Conflicting Signals

| Source | Line(s) | Says |
|--------|---------|------|
| R0b Definition of Done | 1520–1529 | No notebook, no rung report, no dashboard. Only JSON artifacts + registry. |
| R1b–R5b Template Step 10 | 1627–1629 | "Run notebook, generate rung report, regenerate arc dashboard" |
| Global Blind-Test Flow | 1769–1780 | "REPORT -> write rung report, update registry (idempotent), regenerate arc dashboard" — explicitly says "applies to every rung, both arms" |

**Root cause:** R0b is a special case — it's auto-promoted (no gate comparison against
a predecessor) and was designed to be a lightweight baseline lock. But the plan never
explicitly *exempted* R0 from the global REPORT step, creating ambiguity.

---

## Proposed Changes

### Change 1: Add explicit R0 exemption note to the global blind-test flow

**Where:** §10, line 1769 (before the blind-test flow block)

**Add after "### Blind-Test Flow (applies to every rung, both arms)":**

```
**R0 exception:** R0 is auto-promoted with minimal reporting (JSON artifacts +
registry row). Rung report and dashboard generation begin at R1b, when there is
a predecessor to compare against. A post-hoc R0 report may be generated for
completeness but is not a promotion prerequisite.
```

**Rationale:** The rung report (`generate_arc_d_rung_report()`) and dashboard
(`generate_arc_dashboard.py`) are most valuable when comparing against a predecessor.
R0 has no predecessor — its report would be "baseline established, no delta to
report." Making this an explicit exception removes the ambiguity.

### Change 2: Update R0b DoD with reporting status clarification

**Where:** §9, line 1520, after the existing DoD checklist

**Add:**

```
**Reporting note:** R0 is the baseline rung. Rung report (`generate_arc_d_rung_report`)
and arc dashboard (`generate_arc_dashboard.py`) are deferred to R1b, when the first
cross-rung comparison becomes possible. A post-hoc R0 notebook instantiation
(`01_model_rung_template.py` → `02_r0_baseline.py`) is optional follow-up work.
```

### Change 3: Add "Step 0: Reporting" preamble to the R1b–R5b template

**Where:** §9, line 1587, before "All training+eval PRs (R1b, R2b, R3b, R4b, R5b)
follow this 10-step template:"

**Add preamble:**

```
**Reporting mandate (R1b onward):** Every training+eval PR from R1b forward MUST
produce three reporting outputs as part of Step 10:
  1. Rung report: `generate_arc_d_rung_report(bundle, decision)` → `docs/04_reports/model_arc_r{N}_<date>.md`
  2. Notebook: instantiate `01_model_rung_template.py` → `notebooks/arc_d/02_r{N}_eval.py` (Jupytext-paired)
  3. Arc dashboard: `generate_arc_dashboard.py` → `docs/04_reports/model_arc_d_dashboard.md`

This is NOT optional. The blind-test flow's REPORT step (§10) is a hard gate.
```

### Change 4: Expand R1b–R5b template step 10 with explicit commands

**Where:** §9, line 1627–1629 (currently just "Run notebook, generate rung report,
regenerate arc dashboard")

**Replace with:**

```
10. Generate reporting outputs (three mandatory deliverables):
    a. Rung report:
       PYTHONPATH=src uv run python -c "
         from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
         generate_arc_d_rung_report(
           'data/artifacts/arc_d/r{N}/rung_bundle_r{N}.json',
           'data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json',
           'docs/04_reports/model_arc_r{N}_<date>.md')
       "
    b. Notebook instantiation:
       cp notebooks/_templates/01_model_rung_template.py notebooks/arc_d/02_r{N}_eval.py
       # Edit RUNG_ID, ARTIFACT_DIR, and RUNG_LABEL parameters
       jupytext --to ipynb --output notebooks/arc_d/02_r{N}_eval.ipynb notebooks/arc_d/02_r{N}_eval.py
       # Run with: uv run jupyter execute notebooks/arc_d/02_r{N}_eval.ipynb
    c. Arc dashboard:
       PYTHONPATH=src uv run python scripts/internal/generate_arc_dashboard.py \
         --artifacts-base data/artifacts/arc_d \
         --output docs/04_reports/model_arc_d_dashboard.md
```

### Change 5 (optional): Create post-hoc R0 report as follow-up work

If the user wants R0 reporting retroactively, this would be a separate lightweight task
(not a plan change):

```bash
# Rung report (works with existing bundle + decision JSON)
PYTHONPATH=src uv run python -c "
  from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
  generate_arc_d_rung_report(
    'data/artifacts/arc_d/r0/rung_bundle_r0.json',
    'data/artifacts/arc_d/r0/promotion_decision_r0.json',
    'docs/04_reports/model_arc_r0_<date>.md')
"

# Dashboard (single-row table with just R0)
PYTHONPATH=src uv run python scripts/internal/generate_arc_dashboard.py \
  --artifacts-base data/artifacts/arc_d \
  --output docs/04_reports/model_arc_d_dashboard.md
```

This is listed as optional because the outputs would be trivial (no predecessor
comparison, single-row dashboard). The value increases when R1b completes and the
dashboard shows progression.

---

## What This Plan Does NOT Change

- **R0b is not retroactively non-compliant.** The PR was correct per its own DoD.
- **No code changes.** All infrastructure (`generate_arc_d_rung_report`,
  `generate_arc_dashboard.py`, notebook template) already exists.
- **No new PRs.** This is a doc-only update to `plans/arc_d_execution_plan.md`.
- **The R1b–R5b mandatory notebook/report requirement is unchanged.** It was
  always intended; this plan just makes it unambiguous and adds exact commands.

---

## Implementation

Single PR: `feat/arc-d-plan-reporting-clarification`

**Files modified:**
- `plans/arc_d_execution_plan.md` (Changes 1–4)

**Validation:**
- `make repo-lint` (doc linting)
- Visual review of the four insertion points

**Estimated scope:** ~30 lines added to the execution plan. No code.

---

## Decision Required

**Change 5 (post-hoc R0 report):** Should we generate the R0 rung report and
dashboard now, or defer until R1b produces the first comparison? Generating now
creates a single-row dashboard that will be overwritten at R1b. Deferring means
the dashboard doesn't exist until R1b ships.
