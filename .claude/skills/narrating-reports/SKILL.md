---
name: narrate-report
description: Adds narrative interpretation to auto-generated rung reports. Transforms data-only markdown into a publication-quality report with executive summary, section commentary, and cross-links.
disable-model-invocation: true
---

# /narrate-report -- Narrative Overlay for Auto-Generated Reports

You are adding narrative interpretation to an auto-generated Arc D rung report.
The report already contains data tables, charts, and statistics — your job is
to add the "why" and "so what" to each section.

## Input

The user provides:
- A rung identifier (e.g., "r0", "r1")
- The path to the auto-generated report (default: `docs/04_reports/r{N}/model_arc_r{N}.md`)

## Phase 0 -- Context Loading

1. Read the auto-generated report:
   ```bash
   cat docs/04_reports/r{N}/model_arc_r{N}.md
   ```

2. Read companion reports in the same directory:
   ```bash
   ls docs/04_reports/r{N}/
   ```
   Read each companion report to understand findings you'll summarize-and-link.

3. Read the previous rung's final report (if exists):
   ```bash
   cat docs/04_reports/r{N-1}/model_arc_r{N-1}.md
   ```
   Use for tone/structure continuity and cross-rung comparisons.

4. Read conventions:
   ```bash
   cat docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md
   cat docs/02_agent/REPORT_TEMPLATES.md
   ```

5. Read the promotion decision and bundle for context:
   ```bash
   python3 -c "import json; d=json.load(open('data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json')); print(json.dumps({k:v for k,v in d.items() if k not in ('challenger','olsa_arm','control')}, indent=2))"
   python3 -c "import json; print(json.dumps(json.load(open('data/artifacts/arc_d/r{N}/rung_bundle_r{N}.json')), indent=2))"
   ```

## Phase 1 -- Executive Summary

Replace the bullet-point metadata format with the **five-question narrative**:

1. **What is this?** -- One sentence: rung purpose (baseline/improvement/etc.)
2. **What did we do?** -- Campaign inventory: total deals, key configurations
3. **What did we find?** -- Key results with a compact metrics table
4. **What are the caveats?** -- Sample sizes, attribution gap, known issues
5. **What's the decision?** -- Bold verdict with 1-sentence rationale

Add a **key metrics table** (dual-arm side-by-side: net_eppd, eppd, bid_rate, make_rate).

Add a **companion reports table** listing all reports in `docs/04_reports/r{N}/`
with one-line descriptions.

## Phase 2 -- Section Commentary

For each data section in the report, add **2-4 sentences of interpretation**
after the data tables/charts:

### S2 -- Feature Health
- Summarize: how many features, which contract types, pass/fail counts
- Key insight: what feature health tells us about data quality
- Flag any anomalies

### S3 -- Outcome Health
- Summarize: distribution shape, center, spread
- Context: what "healthy" looks like for trick distributions
- Flag sample-size warnings for HIGH/LOW contracts

### S4 -- Auction Analysis
- Summarize: bid rates, common contracts, seat effects
- Context: how auction behavior relates to bidding policy
- Reference dealer position analysis if available

### S5 -- Model Specification
- Summarize: model design choices, feature counts per arm
- Context: why OLS, why these features, what each arm tests
- Add econometric-style specification table if not present

### S6 -- Model Performance
- Summarize: R-squared meaning in context (~75% unexplained = expected for R0)
- Context: inherent randomness in trick outcomes limits R2 ceiling
- Flag sample-size warnings for per-contract metrics

### S7 -- Dual-Arm & Attribution Gap
- Explain attribution gap direction and magnitude
- Add summarize-and-link for comparator rankings (compact table + link)
- Add summarize-and-link for H2H results (key matchups + link)

### S8 -- Semantic Gate
- Explain what each Tier 1 check does
- Note which tiers are active at this rung
- Cross-link to promotion report for full gate analysis

### S9 -- Known Limitations
- Make rung-specific, not generic boilerplate
- Include concrete items from this rung's findings
- Cross-reference measurement_integrity_r{N}.md

## Phase 3 -- Specialized Sections

1. **Semantic gate table:** Populate from `promotion_decision_r{N}.json`
   (`tier_1_checks` field). Add one-line descriptions for each check.

2. **Known limitations:** Replace generic text with rung-specific items:
   - HIGH/LOW sample sizes (if small)
   - Single-seed eval limitations
   - R-squared ceiling explanation
   - Attribution gap direction
   - Comparator methodology caveats

3. **Reproduction commands:** Replace any `<PLACEHOLDER>` values with
   actual paths from the bundle and eval run directories.

4. **Companion reports section:** Add table linking all reports in the
   rung directory with one-line focus descriptions.

## Phase 4 -- Validation Checklist

Before finishing, verify:

- [ ] All companion reports are cross-linked in the companion reports table
- [ ] Sample-size warnings present for n < 2,000 (per contract type)
- [ ] Attribution gap is explained (direction, magnitude, interpretation)
- [ ] Gate decision has a rationale (not just "PROMOTED")
- [ ] Reproduction commands have real paths (no `<PLACEHOLDER>` or `<RUNG>`)
- [ ] No stale data versions (comparator v4, H2H v2, etc.)
- [ ] Every data table has at least one sentence of interpretation
- [ ] Contract-type faceting present or pooling justified
- [ ] Previous rung comparison included (if N > 0)

## Output

The modified report is written back to the same file path. The report
retains all original data content but gains narrative interpretation
throughout.
