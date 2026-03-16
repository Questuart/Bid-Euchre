---
name: draft-rung-reports
description: Produces first drafts of recurring reports (promotion, comparator, H2H, measurement integrity) from JSON artifacts and previous-rung exemplars. Outputs drafts with _DRAFT suffix for human review.
disable-model-invocation: true
---

# /draft-rung-reports -- First-Draft Generator for Recurring Reports

You are producing first drafts of the four recurring reports for a new rung,
using JSON artifacts and the previous rung's reports as structural templates.

## Input

The user provides:
- A rung identifier (e.g., "r1")
- Optionally, the artifact directory path (default: `data/artifacts/arc_d/r{N}/`)

## Phase 0 -- Discovery

1. Scan for available JSON artifacts:
   ```bash
   ls data/artifacts/arc_d/r{N}/
   ```

2. Check which artifacts exist:
   ```
   promotion_decision_r{N}.json    -- needed for promotion report
   rung_bundle_r{N}.json           -- needed for promotion report
   eval_r{N}*.json                 -- needed for promotion report (3 seeds)
   comparator_battery_r{N}*.json   -- needed for comparator rankings
   comparator_cis_r{N}*.json       -- needed for comparator rankings
   h2h_battery_quick*.json         -- needed for H2H analysis
   h2h_battery_full*.json          -- needed for H2H analysis
   gate_thresholds_r{N+1}.json     -- needed for H2H analysis
   ```

3. Read previous rung's reports (if N > 0):
   ```bash
   ls docs/04_reports/r{N-1}/
   ```
   Read each report to use as a structural template.
   **For R0:** There is no previous rung. Use the R0 exemplar reports in
   `docs/04_reports/arc_d_v1/r0/` as structural templates (these serve as the canonical
   examples for all future rungs). Skip any cross-rung comparison steps.

4. Read conventions and templates:
   ```bash
   cat docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md
   cat docs/02_agent/REPORT_TEMPLATES.md
   ```

5. Report which drafts can be produced based on available artifacts.
   If an artifact is missing, note it and produce a partial draft.

## Phase 1 -- Promotion Report Draft

**Required artifacts:** `promotion_decision_r{N}.json`, `rung_bundle_r{N}.json`,
`eval_r{N}*.json` (3 seeds)

**Output:** `docs/04_reports/r{N}/r{N}_promotion_report_DRAFT.md`

### Steps

1. Read the promotion decision JSON:
   ```bash
   uv run python -c "import json; print(json.dumps(json.load(open('data/artifacts/arc_d/r{N}/promotion_decision_r{N}.json')), indent=2))"
   ```

2. Read the previous rung's promotion report for structural reference (if N > 0).
   **For R0:** Use `REPORT_TEMPLATES.md` Section 1 as the sole structural reference.

3. Draft each section following `REPORT_TEMPLATES.md` Section 1:

   **Header:** Extract metadata from bundle and decision.

   **Executive Summary:** Five-question narrative using decision data:
   - Decision: extract from `decision` field
   - Key metrics: extract from `challenger.metrics_seed42`
   - Attribution gap: extract from `attribution_gap` field
   - Adapt narrative: "R{N} was [PROMOTED/ADVANCED/HALTED] because..."

   **Gate Results:** Table from `tier_1_checks` field.
   Add one-line descriptions for each check (copy from R0 exemplar).

   **Evaluation Metrics:** Multi-seed stability table from eval files.
   Read all 3 eval seed files and tabulate net_eppd, eppd, bid_rate, make_rate.

   **Attribution Gap:** Compute and interpret gap direction.
   Flag with `[NEEDS HUMAN REVIEW]` if gap direction changed from R{N-1} (skip for R0).

   **Comparator Context:** Placeholder with `[POPULATE FROM COMPARATOR REPORT]`
   if comparator report draft is also being generated, otherwise
   summarize-and-link to previous rung's comparator data.

   **Companion Reports:** Table of all reports in `docs/04_reports/r{N}/`.

   **Provenance:** Table of artifact paths from bundle.

## Phase 2 -- Comparator Rankings Draft

**Required artifacts:** `comparator_cis_r{N}*.json`, `comparator_battery_r{N}*.json`

**Output:** `docs/04_reports/r{N}/comparator_rankings_DRAFT.md`

### Steps

1. Read the comparator CI JSON to get ranking data:
   ```bash
   uv run python -c "import json; print(json.dumps(json.load(open('data/artifacts/arc_d/r{N}/comparator_cis_r{N}_v4.json')), indent=2))"
   ```

2. Read the previous rung's comparator rankings report for structure (if N > 0).
   **For R0:** Use `REPORT_TEMPLATES.md` Section 2 as the sole structural reference.

3. Draft 9 sections following `REPORT_TEMPLATES.md` Section 2:

   **Summary:** Identify tiers from net_eppd values. Note rank changes from R{N-1}
   (skip cross-rung comparison for R0 — this is the first ranking).

   **Methodology:** Copy from previous rung (if N > 0), update deal counts and bidder
   count. For R0, write methodology from scratch using `REPORT_TEMPLATES.md`.

   **Rankings Table:** Build from CI data: bidder, net_eppd, CI, bid_rate, make_rate.
   Sort by net_eppd descending.

   **Contract-Type Rankings:** Build from per-contract data if available.
   If not available, mark as `[PENDING FULL-MODE RUN]`.

   **Pairwise Statistical Significance:** Compute CI overlap matrix.

   **Behavioral Profiles:** Draft using R{N-1} descriptions as base (if N > 0).
   For R0, write fresh profiles from the metrics data.
   Flag any bidders whose metrics changed significantly with `[REVIEW]`.
   Flag new bidders with `[NEW BIDDER -- NEEDS PROFILE]`.

   **Key Observations:** Compare R{N} rankings to R{N-1} (if N > 0).
   For R0, note the initial tier structure and key findings.
   Note rank changes, tier changes, new bidders.

   **Auction-Pressure Sensitivity:** Mark as `[DEFERRED]` if no 4-way data.

   **Provenance & Reproduction:** Extract from run metadata.

## Phase 3 -- H2H Battery Analysis Draft

**Required artifacts:** `h2h_battery_quick*.json`, `h2h_battery_full*.json`,
`gate_thresholds_r{N+1}.json`

**Output:** `docs/04_reports/r{N}/h2h_battery_analysis_DRAFT.md`

### Steps

1. Read H2H battery JSON files:
   ```bash
   uv run python -c "
   import json
   for fn in ['h2h_battery_quick_v2.json', 'h2h_battery_full_v2.json']:
       with open(f'data/artifacts/arc_d/r{N}/{fn}') as f:
           d = json.load(f)
       print(f'{fn}: {len(d.get(\"cells\",[]))} cells, roster={d.get(\"roster\",[])}')
   "
   ```

2. Read previous rung's H2H analysis for structure (if N > 0).
   **For R0:** Use `REPORT_TEMPLATES.md` Section 3 as the sole structural reference.

3. Draft 8 sections following `REPORT_TEMPLATES.md` Section 3:

   **What Was Done:** Campaign inventory from metadata.
   Total deals, number of matchups, QUICK vs FULL breakdown.

   **C33 Ablation:** Only for R0. For R1+, omit or note "see R0 report."

   **Comparator Summary:** Summarize-and-link to comparator rankings.

   **H2H Full Matrix:** Build dominance table from cells data.
   Each cell: bidder_a vs bidder_b, delta, CI, verdict.
   Team breakout required (show team0 and team1 separately).

   **Gate Threshold Calibration:** Extract from gate_thresholds JSON.
   Include delta_floor, regression threshold, derivation method.

   **Artifact Inventory:** List all generated files with paths.

   **Conclusions:** Draft findings. Flag with `[NEEDS HUMAN REVIEW]`:
   - Any self-play cells failing sanity (delta != ~0)
   - Threshold drift from previous rung (skip for R0 — first rung)
   - Unexpected dominance reversals

   **Reproduction:** Commands with seeds.

## Phase 4 -- Measurement Integrity Draft

**Required artifacts:** All artifacts (cross-cutting review)

**Output:** `docs/04_reports/r{N}/measurement_integrity_r{N}_DRAFT.md`

### Steps

1. Read all available artifacts to understand evaluation scope.

2. Read previous rung's measurement integrity review (if N > 0).
   **For R0:** There are no carry-forward items. All limitations are new.

3. Read the measurement integrity template:
   ```bash
   cat docs/02_agent/MEASUREMENT_INTEGRITY_REVIEW.md
   ```

4. Draft sections:

   **Header:** Standard metadata table.

   **Evaluation Batteries:** Inventory all batteries run, with deal counts.

   **Known Methodological Limitations:**
   - Carry forward all unresolved (b)-class items from R{N-1} (skip for R0)
   - Update resolution status for any items fixed in this rung (skip for R0)
   - Identify new limitations introduced by R{N} changes (all items are new for R0)
   - Classify each: (a) accepted, (b) deferred, (c) blocker

   **Deferral Cost Descriptions:**
   For each (b)-class item, provide three-cost analysis:
   - Fix-now: PRs, reruns, delay
   - Fix-later + compounding: same fix + crosswalk costs
   - Never-fix: long-term impact
   Mark all as `[NEEDS HUMAN REVIEW]` -- deferral decisions are human calls.

   **Conclusion:** Overall methodology assessment.

## Phase 5 -- Output and Status

1. Write all drafts to `docs/04_reports/r{N}/` with `_DRAFT` suffix:
   ```
   r{N}_promotion_report_DRAFT.md
   comparator_rankings_DRAFT.md
   h2h_battery_analysis_DRAFT.md
   measurement_integrity_r{N}_DRAFT.md
   ```

2. Output a summary table:

   ```
   | Report | Status | Missing Artifacts | Sections Needing Review |
   |--------|--------|-------------------|------------------------|
   | Promotion | DRAFTED | none | Attribution gap interpretation |
   | Comparator | DRAFTED | none | Behavioral profiles |
   | H2H | PARTIAL | gate_thresholds | Conclusions |
   | Integrity | DRAFTED | none | All deferral costs |
   ```

3. Rename instructions: After human review, rename `_DRAFT` files to final:
   ```bash
   mv docs/04_reports/r{N}/r{N}_promotion_report_DRAFT.md \
      docs/04_reports/r{N}/r{N}_promotion_report.md
   ```

## Artifact-to-Report Quick Reference

| Artifact | Promotion | Comparator | H2H | Integrity |
|----------|-----------|------------|-----|-----------|
| `promotion_decision_r{N}.json` | Required | - | - | Reference |
| `rung_bundle_r{N}.json` | Required | - | Reference | Reference |
| `eval_r{N}*.json` (3 seeds) | Required | - | - | Reference |
| `comparator_battery_r{N}*.json` | Summarize | Required | Reference | Reference |
| `comparator_cis_r{N}*.json` | Summarize | Required | - | - |
| `h2h_battery_quick*.json` | - | - | Required | Reference |
| `h2h_battery_full*.json` | - | - | Required | Reference |
| `gate_thresholds_r{N+1}.json` | Reference | - | Required | Reference |
