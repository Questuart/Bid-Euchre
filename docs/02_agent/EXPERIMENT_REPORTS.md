# Experiment Report Convention

Operational guidance for writing experiment reports in the Bid Euchre research
framework. Defines when reports are required, where they live, and the standard
template.

---

## When Required

Write an experiment report for any experiment that is:

- **Referenced in a promotion decision** (gate pass/fail justification)
- **Used for gate threshold calibration** (null-signal derivation, drift checks)
- **An ablation study** validating an architectural choice
- **A head-to-head battery** establishing competitive ordering

Reports are **NOT required** for:

- Smoke tests (`--n-per 10`, `MODE=SMOKE`)
- Exploratory runs used only for debugging or iteration
- Intermediate experiment configs that were superseded before analysis

## Location and Naming

Reports live in `docs/04_reports/<rung>/` alongside the rung's other
documentation.

- **Directory:** `docs/04_reports/<rung>/` (e.g., `docs/04_reports/r0/`)
- **Naming:** `[NN_]<descriptive_name>.md` — optional numeric prefix for ordering.
  Examples: `05_c33_ablation_report.md`, `02_model_arc_r0.md`,
  `03_comparator_rankings.md`
- **Forward-only:** This convention applies to new reports. Existing reports
  with date-stamped or legacy names are not required to rename.

## Template

Every experiment report should follow this structure. Sections may be
combined or abbreviated when the content is trivial, but all should be present.

### Header

```markdown
# <Report Title>

**Arc:** <arc letter and name>
**Rung:** <rung ID>
**Date:** <YYYY-MM-DD>
**Purpose:** <one-line summary>
```

### Executive Summary

A concise overview (5-10 lines) that a reader can scan without reading the
full report. Must include:

- **Key quantitative findings** — the 2-3 most important numbers with CIs
- **Decision or conclusion** — what the results mean for the project
- **Surprising or non-obvious takeaways** — anything that changes prior
  assumptions or reframes the problem

The executive summary should be self-contained: a reader who stops here should
walk away with the correct conclusion, not a misleading simplification.

### 1. Motivation

Why the experiment was run. What question does it answer? What decision does it
inform? Link to the plan or prior report that motivated it.

### 2. Methodology

- Deal count, seed, matchup structure
- Statistical method (bootstrap CIs, permutation tests, etc.)
- Config file reference (YAML path or inline description)
- Game variant details (if non-standard)

### 3. Results

Tables with point estimates and 95% confidence intervals. **Incorporate key
chart references** throughout this section — visualizations make results
concrete and scannable. See "Chart Integration" below for guidance.

Example:

```markdown
| Matchup | net_eppd_delta | 95% CI | Significant? |
|---------|----------------|--------|--------------|
| A vs B  | +0.21          | [+0.01, +0.28] | Yes |

> See notebook 55_contract_selection_oracle, S7b scatter plot for the
> oracle vs model utility comparison.
```

### 4. Interpretation

Mechanism explanations for observed results. Caveats, confounders, and
limitations. What do the numbers mean in context?

### 5. Impact & Decisions

How the results change the development plan. What was promoted, halted, or
deferred? What thresholds were set or revised?

### 6. Arc Context

Where this experiment fits in the arc progression. What came before (prior
rung, prior ablation)? What comes next?

### 7. Provenance

Machine-readable traceability. Must include `gate_status` to satisfy the
repo lint rule (see below).

| Item | Value |
|------|-------|
| gate_status | <PROMOTED / ADVANCED / HALTED / N/A> |
| Artifact path | data/artifacts/arc_d/r0/... |
| Git SHA | <commit hash> |
| Seed | 42 |
| n_deals | 10,000 |

**Artifact paths:** Use plain text in tables for paths under `data/artifacts/`
and `data/runs/`. Backtick-quoting these paths triggers the docs-check linter,
which validates backtick-quoted `.py` paths against disk. Since artifact
directories are gitignored, backtick-quoted artifact paths will cause lint
failures.

### 8. Reproduction

Exact shell commands to reproduce the experiment from scratch:

```bash
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/<config>.yaml
```

---

## Chart Integration

Reports should reference key visualizations from the companion notebook to
make results concrete. Charts serve two purposes: (1) making distributions
and relationships visible at a glance, and (2) providing evidence that
supports the textual interpretation.

**Guidelines:**

- **Reference, don't duplicate.** Point to the notebook section and chart name
  (e.g., "See notebook 55_contract_selection_oracle, S7b scatter plot").
  Do not paste images or recreate chart data in the report.
- **Describe what the chart shows.** Include a 1-2 sentence description of
  what the reader should look for (e.g., "The red cluster at predicted
  utility <= 0 visualizes the pass-threshold population").
- **Use blockquote format** for chart callouts within the Results section:

```markdown
> **Regret Heatmap (S7c):** Confusion-matrix showing total regret
> contribution by (model choice -> oracle choice). The pass->suit cell
> dominates, confirming the decomposition numerically.
```

- **Place charts near the data they illustrate.** A scatter plot of predicted
  vs actual belongs in Results, not buried in a Diagnostics appendix.
- **Minimum charts per report:** At least one visualization reference for any
  report with quantitative results. If the notebook has no charts, the report
  should note this explicitly.

## Cross-Referencing

- **Between reports:** Use relative markdown links
  (`[03_comparator_rankings.md](03_comparator_rankings.md)`).
- **To notebooks:** Reference by name and section
  (`notebook 50_r0_matchups, Figure 3`). Do NOT duplicate notebook analysis
  in the report.
- **To artifacts:** Reference artifact filenames in the Provenance table.
  Use plain text (not backticks) for gitignored paths.

## Lint Requirements

Every `.md` file under `docs/04_reports/` (except `README.md`) must contain
at least one of the gate evidence patterns defined in `scripts/lint_repo.py`:

- `batch_gate.json`
- `notebook_gate.json`
- `canonical_summary.json`
- `gate_status`

The simplest way to satisfy this is to include `gate_status` in the Provenance
table. Reports that describe experiments without a formal gate decision should
use `gate_status: N/A`.

## Report Index

All reports must be indexed in `docs/04_reports/README.md` with their date
and a one-line summary. Update the index when adding or substantially revising
a report.
