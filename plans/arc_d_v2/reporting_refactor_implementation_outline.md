# Arc D v2 Reporting Refactor Implementation Outline

<!-- review-tier: medium -->

**Date:** 2026-03-18
**Status:** PROPOSED
**Owner:** Reporting refactor follow-up
**Audience:** Handoff to another implementation agent
**Supersedes:** Portions of `plans/arc_d_v2/reporting_pr_scope_full_chart_suite.md`, `plans/arc_d_v2/full_chart_suite_implementation.md`, and `plans/arc_d_v2/chart_suite_cleanup.md` where current repo state has diverged

## 1. Purpose

Outline the next reporting refactor for `arc_d_v2` now that the chart-suite compaction work has landed but the produced reports still undershoot the original goal.

This is intentionally an implementation outline rather than the full refactor plan. It is meant to:

- capture the current truth after the compaction work
- identify the remaining gaps that matter most
- define the workstreams and phase ordering
- give another agent enough structure to prepare the full refactor plan next

## 2. Goal

Produce a chart and report suite for both `quick` and `full` runs that is:

- robust for storytelling
- robust for health analysis
- robust for model evaluation
- compact enough to avoid report sprawl
- autonomous to generate from the pipeline without notebooks

The canonical surface remains:

- `00_manifest.md`
- `01_results.md`
- `02_decision.md`

Dashboards remain the primary review surface. Standalone numbered charts remain canonical supporting evidence. No new top-level report families are added.

## 3. Current State Summary

### 3.1 What is in good shape

- Dashboards-first presentation is in place.
- `charts/` vs `charts/full_chart_suite/` separation is in place.
- Numbered chart headings and manifest inventory exist.
- Competitive/H2H storytelling is the strongest part of the suite.
- `team0` / `team1` naming is present in the report-facing H2H markdown.
- Truncating long tables in `01_results.md` is directionally correct.

### 3.2 What is still materially weak

- `outcome_distributions.csv` is still synthetic in shipped bundles and does not satisfy the original plan's semantics.
- The health dashboard still overclaims distribution visibility relative to the backing data.
- The model-evaluation suite is structurally present but still missing the most important diagnostics in produced bundles.
- QUICK `02_decision.md` is still not a real decision artifact.
- Metadata and bundle-quality issues remain:
  - `Rung ?` in QUICK decision titles
  - `PENDING` recommendation in QUICK bundles
  - `Seeds: []` in manifests
  - FULL manifests reporting `Mode: QUICK`
  - `Model Class: None` in model rosters
  - machine-specific absolute artifact paths in committed outputs
- `behavior_by_contract.csv` is still pooled-only and does not actually provide contract faceting.
- `r1` and `r2` previously exhibited duplicate artifact surfaces; uniqueness should now be treated as a reporting integrity requirement.

### 3.3 V1 gold-standard lessons to preserve

From `phase0` and `r0`, the strongest charting patterns were:

- violin + box overlays for comparative distributions
- CDF / CCDF for tails and symmetry checks
- boxplots for seat / team balance
- scatter plots for prediction diagnostics
- heatmaps for matchup or feature structure

The key regression in `v2` is not just missing charts; it is a shift from shape-aware charts to summary bars.

## 4. Planning Principles

1. Fix data semantics before refining visual polish.
2. Prefer replacing weak charts over adding more charts.
3. QUICK must be review-grade, not placeholder-grade.
4. FULL must enrich QUICK, not branch into a second reporting universe.
5. The canonical 3-file surface must absorb the strongest narrative content.
6. No notebook dependency.
7. No new markdown report sprawl.

## 5. Scope Boundaries

### In scope

- report and chart refactor for `quick` and `full`
- chart-data extraction and semantics
- dashboard redesign
- report content flow and metadata fixes
- manifest quality and portability fixes
- validation for reporting integrity

### Out of scope

- changes to rung advancement policy itself
- model-training logic unrelated to report generation
- adding notebooks or notebook-driven reporting
- adding new top-level report families beyond `00/01/02`

## 6. Refactor Workstreams

### Workstream A: Canonical Contract and Metadata Repair

Objective: make the reporting contract internally consistent and portable.

Must cover:

- unify path and mode semantics across shared helpers, orchestration, manifest, and report generation
- ensure `quick` and `full` bundle headers render the correct:
  - rung id
  - mode
  - seeds
  - model class
- convert artifact references in committed markdown and manifests to repo-relative paths where appropriate
- make `02_decision.md` a real rung-labeled artifact in both modes
- apply long-table truncation policy consistently to `02_decision.md`, not just `01_results.md`

Primary outputs:

- corrected headers and provenance in `00_manifest.md`
- corrected title / status behavior in `02_decision.md`
- consistent path contract and relative file references

### Workstream B: Chart-Data Contract Completion

Objective: make chart data complete enough to support the intended chart suite.

Required `chart_data` inventory target:

- `outcome_distributions.csv`
- `seat_balance.csv`
- `bid_levels.csv`
- `contract_mix.csv`
- `predictions.csv`
- `residuals.csv`
- `calibration_bins.csv`
- `decision_comparison.csv`
- `disagreement_outcomes.csv`
- `feature_importances.csv`
- `selection_paths.csv`
- `cross_rung_progression.csv`

Critical rule:

- `outcome_distributions.csv` must contain real distribution rows, not synthetic single-bin placeholders

Additional table requirements:

- `behavior_by_contract.csv` must contain actual contract rows
- `behavior_summary.csv` should be expanded with:
  - `avg_bid`
  - `bid_std`
  - `bid_min`
  - `bid_max`

Primary outputs:

- complete chart-data contract for both modes
- explicit fallback behavior when source artifacts genuinely do not exist
- no silently misleading "distribution-shaped" outputs

### Workstream C: Chart-Suite Redesign

Objective: improve chart quality while staying compact.

Keep as core strengths:

- comparator ranking
- tail risk
- H2H heatmap
- H2H ranking scatter
- intelligence-faceted H2H
- feature importance / selection path

Replace or redesign weak current views:

- replace weak outcome summary/distribution views with real distribution charts
- use violin + box plots where comparative shape matters
- bring back CDF / CCDF where tails matter
- prioritize prediction diagnostics over extra summary bars in model-eval

Preferred chart-type direction:

- Health:
  - violin + box outcome distributions by contract
  - seat/team balance boxplot or violin + box
  - CDF / CCDF tail panel
- Competitive:
  - keep ranking scatter and H2H heatmap
  - add distribution-aware H2H delta view where data quality supports it
- Model evaluation:
  - predicted vs actual scatter or hexbin
  - residual distribution by contract
  - calibration curve
  - decision disagreement outcome chart

Primary outputs:

- stronger standalone chart definitions
- fewer misleading summary-only charts
- chart choices that more closely match `phase0` / `r0` precedent

### Workstream D: Dashboard Recomposition

Objective: make the 3 dashboards the primary review surface for both modes.

Target composition:

`dashboard_competitive.png`

- comparator ranking
- tail risk
- H2H delta by contract
- H2H heatmap
- H2H ranking scatter
- intelligence-faceted H2H

`dashboard_health.png`

- outcome distribution by contract
- CDF / CCDF outcome tail panel
- seat balance
- contract mix
- bid / pass / make behavior
- bid-level distribution

`dashboard_model_eval.png`

- `R²` by contract
- `MAE` by contract
- predicted vs actual
- residual distribution
- calibration
- feature importance or selection path

Guidance:

- dashboards summarize; they do not eliminate the need for numbered charts
- if a panel has no trustworthy source data, show an explicit status placeholder rather than a misleading proxy

### Workstream E: Report Flow and Narrative Consolidation

Objective: make the canonical reports readable and decision-useful.

`00_manifest.md`

- move from file list toward evidence manifest
- include chart status, chart-data status, seeds, model classes, and provenance

`01_results.md`

- dashboards first
- standalone charts only where they add real explanatory value
- compact tables only
- no raw long H2H dumps outside collapsed sections

`02_decision.md`

- absorb the value currently living in extra decision reports
- become the canonical narrative for both QUICK and FULL
- cite chart numbers and only the minimum supporting tables
- QUICK must produce an actual recommendation state, not a placeholder

Primary outputs:

- canonical quick report surface becomes usable
- full report surface becomes deeper without becoming broader

### Workstream F: Reporting Integrity Validation

Objective: make bundle quality testable.

Validation should cover:

- required chart-data files exist when their source artifacts exist
- missing chart-data files cause explicit placeholders, not silent omissions
- `outcome_distributions.csv` is non-synthetic unless explicitly gated as fallback
- `behavior_by_contract.csv` contains contract-level rows
- manifests report correct mode and seeds
- decision reports contain rung id and non-placeholder state
- bundle outputs differ across rungs unless the underlying evidence is intentionally identical
- no chart marked present lacks its backing file

## 7. Phase Order

### Phase 1: Contract Repair

Workstreams A and B, minimum viable subset:

- metadata correctness
- path correctness
- true/final source-data inventory
- remove synthetic distribution pretense

Why first:

- chart and report quality cannot improve until the backing contract is trustworthy

### Phase 2: Health and Model-Eval Recovery

Workstreams B, C, and D focused on the weakest surfaces:

- real outcome distributions
- seat balance
- prediction diagnostics
- residuals
- calibration
- behavior faceting

Why second:

- these are the largest remaining analytical gaps versus the original plan and `v1`

### Phase 3: Canonical Narrative Repair

Workstreams E and F:

- make QUICK decision reports usable
- fold full-report value back into canonical `02_decision.md`
- finalize validation and report hygiene

Why third:

- after the chart/data surfaces are trustworthy, the narrative layer can be tightened without rework

## 8. Quick vs Full Rules

### QUICK

Purpose:

- fast review-grade bundle for triage and promotion review

Requirements:

- all 3 dashboards present
- no placeholder decision header
- explicit status when source data is absent
- enough chart-data coverage to support health and model-eval summaries

### FULL

Purpose:

- same structure, richer evidence

Requirements:

- same chart numbering
- same canonical report files
- richer confidence intervals, fuller tables, and denser supporting data
- no extra decision-report family unless explicitly approved later

## 9. Open Design Decisions For The Full Plan

These need to be resolved in the full refactor plan, not in this outline:

- exact registry contract:
  - preserve 23 numbered charts
  - return to 22
  - or explicitly bless 23 + unnumbered extras
- which current chart numbers are replacements vs direct fixes
- whether cross-rung progression belongs in the canonical suite or as a supporting chart
- which distribution views should be dashboard panels versus standalone evidence
- exact fallback policy when raw prediction-level artifacts are absent

## 10. Expected File Touch Surface

Likely code paths:

- `src/bid_euchre/arc_d_v2/paths.py`
- `src/bid_euchre/arc_d_v2/orchestration.py`
- `src/bid_euchre/arc_d_v2/chart_registry.py`
- `src/bid_euchre/arc_d_v2/manifest.py`
- `src/bid_euchre/arc_d_v2/report.py`
- `src/bid_euchre/arc_d_v2/tables.py`
- `scripts/internal/generate_rung_charts.py`
- `scripts/internal/generate_interpretability.py`
- `scripts/internal/generate_interpretability_charts.py`
- targeted tests under `tests/unit/`

Likely artifact touch surface:

- `docs/04_reports/arc_d_v2/r0/quick/**`
- `docs/04_reports/arc_d_v2/r1/quick/**`
- `docs/04_reports/arc_d_v2/r2/quick/**`
- `docs/04_reports/arc_d_v2/r3/quick/**`
- `docs/04_reports/arc_d_v2/r0/full/**`
- `docs/04_reports/arc_d_v2/r1/full/**`
- `docs/04_reports/arc_d_v2/r2/full/**`
- `docs/04_reports/arc_d_v2/r3/full/**`

## 11. Acceptance Frame For The Full Refactor Plan

The later full refactor plan should be considered complete only if:

- QUICK and FULL both produce usable `00/01/02` bundles
- health analysis is backed by real distributions
- model evaluation includes actual prediction diagnostics
- decision reports are real decision artifacts
- the strongest narrative value no longer depends on extra report files
- the chart suite is closer to the `v1` gold standard in chart quality without recreating `v1` sprawl

## 12. Handoff Notes

Use this outline as the starting point for the full refactor plan.

The next agent should:

1. reconcile the current repo state against this outline
2. resolve the open design decisions in Section 9
3. convert each workstream into concrete implementation phases
4. define exact chart replacement mapping
5. define source CSV schemas and fallback rules
6. define validation commands and acceptance checks

Do not assume the existing produced bundles are analytically trustworthy just because the scaffolding and numbering are present.
