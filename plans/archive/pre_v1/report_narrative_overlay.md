# Report Pipeline — Comprehensive Implementation Plan

**Date:** 2026-02-28
**Scope:** Four-stage report pipeline (data → charts → report → narrative), template-based drafting for recurring reports, R0 exemplar, consistency fixes
**Status:** DECISIONS RESOLVED — ready for implementation (open items 4-5 at EOF block PR-N0b)

---

## Background

The R0 report ecosystem has two quality tiers. Auto-generated reports (rung report, dashboard) lack
narrative interpretation — they're tables without story. Hand-crafted reports (comparator rankings,
H2H battery, promotion, C33 ablation) are excellent, but were shaped over 10+ PRs of iteration that
would need to be re-derived from scratch at each rung.

This plan introduces a **four-stage pipeline** and two complementary agent skills:

**Pipeline stages:**
1. **Data preparation** — JSON artifacts, eval datasets, bundles (existing)
2. **Chart generation** — dedicated script produces PNGs from existing `plot_*` library (NEW)
3. **Report generation** — Python generator emits markdown with embedded charts (existing `arc_d_report.py`)
4. **Narrative overlay** — agent adds interpretation within each section (NEW `/narrate-report` skill)

**Agent skills:**
- **`/narrate-report`** — adds interpretation to auto-generated reports (stage 4)
- **`/draft-rung-reports`** — produces first drafts of recurring hand-crafted reports from JSON artifacts + previous rung exemplars

Together, these ensure that R1+ reports inherit R0's quality without re-discovering the format.

### Plan Consolidation (2026-02-28)

This plan consolidates remaining scope from `~/.claude/plans/kind-nibbling-sphinx.md`
(Comparator Battery & H2H Refactor v2) and `plans/comparator_dual_track_plan.md`.

**Completed items (not in this plan):**
- C2c (#466) — comparator play strategy harmonization to GluttonStrategy
- C3 — H2H battery rerun (QUICK+FULL), post-bugfix
- C4 (#468) — H2H absolute per-team metrics + schema v2
- C5 (#467) — BiddingObservation.auction_transcript
- C2b-1 (#470) — comparator rankings refactor (v4, 9-section report)

**Remaining items absorbed into this plan:**
- C2b-2 → Phase 2 (companion report consistency: h2h_battery, promotion report,
  measurement_integrity, README)
- C6 → Phase 6 (dual-track report, archetype segmentation, roster scatter plots)

### Design Decisions (from review session 2026-02-28)

1. **Agent adds commentary within data sections** — not just dedicated narrative blocks. Each section
   gets a summary of what was done and key takeaways.
2. **Summarize-and-link** for companion reports — the main report carries compact tables + 2-3 sentences
   + cross-link, rather than duplicating or just linking.
3. **Keep generator as-is initially** — Stage 4 agent rewrites sections of the current markdown output.
   Refactor the generator to emit JSON sidecar later, once we know exactly what the sidecar needs.
4. **Start with manual skill invocation**, graduate to PostToolUse hook later.
5. **R0 reports serve as seed exemplars** — manually refactored once to establish standards.
   Future rungs use them as "previous rung context."

### Resolved Questions (2026-02-28)

1. **Regenerate first** — run current generator (picks up #450, #452 improvements), then overlay.
2. **Drop date from filename** — use `model_arc_r0.md` (stable, no link churn). Archive previous
   versions with versioning label: `archive/model_arc_r0_v1_20260224.md`. Generation timestamp
   lives in the report header.
3. **Show all 7 bidders** in the main report's comparator summary table (compact format: net_eppd + CI).
4. **Key pairwise matchups** (4-5 rows) in the main report's H2H summary — shows trained-bidder
   dominance order with delta + CI + verdict, plus the dominance diagram.
5. **`_DRAFT` suffix** for `/draft-rung-reports` output — rename to final after review.
6. **Skill names:** `/narrate-report` + `/draft-rung-reports`.

---

## Report Inventory: What Gets Produced at Each Rung

### Auto-Generated (Python → Markdown)

| # | Report | Generator | Narrative Value |
|---|--------|-----------|-----------------|
| A1 | **Rung report** | `arc_d_report.py` | **HIGH** — primary `/narrate-report` target |
| A2 | **Cross-rung dashboard** | `generate_arc_dashboard.py` | **MEDIUM** — trend narrative |
| A3 | Per-run analysis | `generate_report.py` | LOW — ephemeral, in `data/runs/` |
| A4 | Batch report | `generate_batch_report.py` | LOW — ephemeral, in `data/runs/` |

### Auto-Generated Data Artifacts (Python → JSON, feeds hand-crafted reports)

| # | Artifact | Generator | Consumed By |
|---|----------|-----------|-------------|
| D1 | `promotion_decision_r{N}.json` | `write_r0_promotion.py` / `run_arc_d_gate.py` | Promotion report |
| D2 | `comparator_battery_r{N}.json` | `run_auction_comparator.py` | Comparator rankings |
| D3 | `comparator_cis_r{N}.json` | `extract_comparator_cis.py` | Comparator rankings |
| D4 | `h2h_battery_quick.json` | `run_arc_d_h2h_battery.py` | H2H analysis |
| D5 | `h2h_battery_full.json` | `run_arc_d_h2h_battery.py` | H2H analysis |
| D6 | `gate_thresholds_r{N+1}.json` | `calibrate_arc_d_thresholds.py` | H2H analysis, Promotion report |
| D7 | `rung_bundle_r{N}.json` | Training pipeline | Rung report, Promotion report |

### Hand-Crafted, Recurring (agent/human → Markdown)

| # | Report | Recurs? | Exemplar | JSON Sources | Template Value |
|---|--------|---------|----------|--------------|----------------|
| H1 | **Promotion report** | Every rung | `r0_promotion_report.md` | D1, D7, eval files | **HIGH** — gate results, multi-seed, attribution gap |
| H2 | **Comparator rankings** | Every rung | `comparator_rankings.md` | D2, D3 | **HIGH** — 9 sections, behavioral profiles, methodology |
| H3 | **H2H battery analysis** | Every rung | `h2h_battery_analysis.md` | D4, D5, D6 | **HIGH** — campaign inventory, dominance, thresholds |
| H4 | **Measurement integrity** | Every rung | `measurement_integrity_r0.md` | All artifacts | **MEDIUM** — checklist, less structural |
| H5 | C33 ablation | R0 only | `c33_ablation_report.md` | — | NONE — one-time |

---

## Work Items

### Phase 0: Prerequisites

Infrastructure and data fixes required before the rung report refactor.

#### P0-1: Generator Data Fixes (G1–G3)

Three data issues in the current generator pipeline need fixing before regeneration:

| ID | Issue | Fix |
|----|-------|-----|
| **G1** | `rung_bundle_r0.json` `comparator_battery` points to v1 (5 bidders) | Update pointer to v4 comparator data |
| **G2** | Bundle has no `h2h_battery` reference | Add `h2h_battery_quick` + `h2h_battery_full` references |
| **G3** | Report §8 (Semantic Gate) shows only "PROMOTED" | Read gate checks from `promotion_decision_r0.json` and render pass/fail table |

- G1/G2 are bundle schema changes → update `arc_d_bundle.py` validation
- G3 is a generator logic change → update `_render_semantic_gate()` in `arc_d_report.py`
- **Files:** `src/bid_euchre/validation/arc_d_bundle.py`, `src/bid_euchre/reporting/arc_d_report.py`,
  `data/artifacts/arc_d/r0/rung_bundle_r0.json`

#### P0-2: Chart Runner Script

Create `scripts/internal/generate_rung_charts.py` — a dedicated script that produces all PNGs
needed by the rung report generator, using the existing `plot_*` diagnostics library.

**Rationale:** Separates chart generation from notebook execution. Notebooks remain exploratory;
the chart runner produces the curated subset that gets embedded in formal reports. The generator
already supports `chart_dir` parameter but currently no script produces the expected PNGs.

**Chart manifest** — the generator (`arc_d_report.py`) already looks for these 10 filenames:

| # | PNG Filename | Source Function | Report Section |
|---|-------------|-----------------|----------------|
| 1 | `seat_balance_boxplot.png` | `charts.plot_hand_value_by_seat()` | S2: Feature Health |
| 2 | `hand_value_by_contract.png` | `charts.plot_hand_value_by_contract()` | S2: Feature Health |
| 3 | `tricks_won_histogram.png` | `charts.plot_outcome_distributions()` | S3: Outcome Health |
| 4 | `cdf_by_contract.png` | `charts.plot_cdf()` | S3: Outcome Health |
| 5 | `auction_health.png` | `auction_charts.plot_auction_health()` | S4: Auction Analysis |
| 6 | `bidder_performance.png` | `auction_charts.plot_bidder_performance()` | S4: Auction Analysis |
| 7 | `coefficient_heatmap.png` | `charts.plot_coefficient_heatmap()` | S5: Model Specification |
| 8 | `pred_vs_actual_scatter.png` | `model_charts.plot_model_diagnostics()` | S6: Model Performance |
| 9 | `residual_distribution.png` | `model_charts.plot_model_diagnostics()` | S6: Model Performance |
| 10 | `dual_arm_comparison.png` | `model_charts.plot_dual_arm_comparison()` | S7: Dual-Arm |

**Additional charts** from user review (not yet in generator — add embedding support):

| # | PNG Filename | Source Function | Report Section | Notes |
|---|-------------|-----------------|----------------|-------|
| 11 | `calibration_curve.png` | `model_charts.plot_calibration_curve()` | S6: Model Performance | S3.5 Gaussian diagnostics |

**Script interface:**
```bash
uv run python scripts/internal/generate_rung_charts.py \
  --rung r0 \
  --eval-dir data/runs/arc_d_eval_r0_42_20260221_180253 \
  --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
  --output-dir data/reports/arc_d/r0/charts/
```

**Output directory:** `data/reports/arc_d/r{N}/charts/` (gitignored, same as other generated data)

**Implementation notes:**
- Each chart function returns a `matplotlib.figure.Figure` — call `fig.savefig(output_dir / name)`
- Load eval data via `build_eval_dataset()` (same as report generator)
- Load model artifacts from bundle for coefficient/calibration charts
- Script should be idempotent (overwrite existing PNGs)
- Add `--chart` flag for selective chart generation (optional, for development)

**Files:** `scripts/internal/generate_rung_charts.py` (new), `Makefile` (optional target)

---

### Phase 1: R0 Rung Report Refactor (exemplar for A1)

Create the narrative exemplar that defines the standard for all future auto-generated rung reports.

#### P1-0: Generate Charts, Regenerate Report, and Rename
- Archive current report: `model_arc_r0_20260224.md` → `model_arc_r0.md` (renamed; git history preserves original)
- Generate charts first (stage 2 of pipeline):
  ```bash
  uv run python scripts/internal/generate_rung_charts.py \
    --rung r0 \
    --eval-dir data/runs/arc_d_eval_r0_42_20260221_180253 \
    --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
    --output-dir data/reports/arc_d/r0/charts/
  ```
- Regenerate report with charts (stage 3 of pipeline):
  ```bash
  PYTHONPATH=src uv run python -c "
  from bid_euchre.datasets.eval_dataset import build_eval_dataset
  from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
  df = build_eval_dataset('data/runs/arc_d_eval_r0_42_20260221_180253/logs/*.jsonl')
  generate_arc_d_rung_report(
      'data/artifacts/arc_d/r0/rung_bundle_r0.json',
      decision_path='data/artifacts/arc_d/r0/promotion_decision_r0.json',
      eval_df=df,
      chart_dir='data/reports/arc_d/r0/charts/',
      output_path='docs/04_reports/arc_d_v1/r0/model_arc_r0.md',
  )
  "
  ```
- This picks up generator improvements from #450 (eval methodology) and #452 (residual variance)
- Charts are now embedded inline (using `chart_dir` parameter)
- Stable filename `model_arc_r0.md` — no date in filename, timestamp in header
- Update cross-links in companion reports and README to use new filename

#### P1-1: Refactor Executive Summary
- Replace bullet-point metadata dump with narrative structure:
  - **What is this?** R0 purpose (baseline establishment)
  - **What did we do?** Brief campaign inventory (~580k deals, 6 campaigns)
  - **What did we find?** Both arms positive, ranks 2nd/7, wrapper adds +0.21
  - **What are the caveats?** Negative attribution gap explained, high/low sample sizes
  - **What's the decision?** PROMOTED with rationale
- Add compact key metrics table (OLSa vs OLSa_Full side-by-side)
- Add companion reports cross-link block
- **File:** `docs/04_reports/arc_d_v1/r0/model_arc_r0.md`

#### P1-2: Add Section Commentary (per-section notes from review)

For each data section, add interpretation, charting, and borrowed analysis patterns.
Notes below from user review session (2026-02-28), organized by report section.

**S2 — Feature Health:**
- Add pass/fail counts: how many of the N features pass each sanity check (balance, range, etc.)
- Summary: "N features, M contract types evaluated, K deals, no anomalies detected"
- Charts (from chart runner): seat balance boxplot, hand value by contract
- Key insight: what the feature health tells us about data quality

**S3 — Outcome Health:**
- Add key assumptions and design: what outcomes we're measuring, what "health" means
- Summarize distribution shape — center, spread, skew
- Charts: tricks histogram, CDF by contract
- Borrow pattern from `30_feature_outcome_eval.py` (S3.5 Gaussian diagnostics — Q-Q, residuals)

**S4 — Auction Analysis:**
- Add experimental design: what auction data we're analyzing, how it relates to bidding policy
- Summarize auction behavior: bid rates, common contracts, seat effects
- Charts: auction health (multi-panel), bidder performance
- Reference dealer position bid analysis from `25_auction_health.py` notebooks

**S5 — Model Specification:**
- **Econometric-style consolidated table** (borrow from phase0 report pattern):
  Side-by-side OLSa vs OLSa_Full, with rows for key parameters:
  n_features, training set size, feature selection method, regularization, etc.
- Chart: coefficient heatmap
- Summarize model design choices: why OLS, why these features, what each arm tests
- Borrow coefficient comparison analysis from `30_feature_outcome_eval.py`

**S6 — Model Performance:**
- **Econometric-style metrics table** (borrow from phase0 report):
  Side-by-side R², RMSE, MAE with bootstrap CIs and status column (PASS/WARN/FAIL)
- Charts: pred-vs-actual scatter, residual distribution, calibration curve (new)
- Summarize what R²=0.24-0.29 means in context: ~75% unexplained variance is expected
  for R0 linear models; trick outcomes have inherent randomness
- Flag rigor concerns: sample-size warnings for high/low contracts (n<300)

**S7 — Dual-Arm & Attribution Gap:**
- Keep attribution gap analysis (own content, important narrative)
- Summarize-and-link comparator battery: compact 7-bidder table (net_eppd + CI) + link
  to comparator_rankings.md
- Summarize-and-link H2H results: key pairwise matchups (4-5 rows, delta + CI + verdict)
  + dominance diagram + link to h2h_battery_analysis.md
- Chart: dual-arm comparison
- Update data from 5-bidder v1 to 7-bidder v4 numbers (requires G1 fix)

**S8 — Semantic Gate:**
- Populate with pass/fail table from `promotion_decision_r0.json` (requires G3 fix)
- Note R0 uses Tier 1 only (artifact integrity — 4 checks)
- Cross-link to promotion report for full gate analysis + multi-seed stability

**S9 — Known Limitations:**
- Make R0-specific rather than generic boilerplate
- Include concrete items: high/low sample sizes, single-seed eval, R² ceiling,
  attribution gap direction, comparator sensitivity to play strategy
- Cross-reference measurement_integrity_r0.md for methodology limitations
- Borrow limitation framing from existing companion reports

#### P1-3: Fix Reproduction Commands
- Replace `<EVAL_RUN_DIR>`, `<LOG>`, `<RUNG>` placeholders with actual values
- Include the full four-stage pipeline command sequence:
  1. Chart generation (`generate_rung_charts.py`)
  2. Report generation (`arc_d_report.py` with `chart_dir`)
  3. Narrative overlay (`/narrate-report`)

#### P1-4: Add Companion Reports Section
New section linking all 5 companion reports with one-line descriptions:
- r0_promotion_report.md — Gate decision + multi-seed stability
- comparator_rankings.md — Absolute benchmarking (v4, 7 bidders)
- h2h_battery_analysis.md — Competitive ordering + threshold calibration
- c33_ablation_report.md — Gaussian EV wrapper validation
- measurement_integrity_r0.md — Methodology limitations + deferral costs

### Phase 2: Companion Report Consistency (= C2b-2)

Fix v2→v4 data staleness in companion reports. This phase consolidates the remaining
C2b-2 scope from `~/.claude/plans/kind-nibbling-sphinx.md` (Comparator Battery & H2H
Refactor v2). Completed items from that plan: C2c (#466), C3 (reruns), C4 (#468),
C5 (#467), C2b-1 (#470).

#### P2-1: Update h2h_battery_analysis.md §3
- Section 3 ("Comparator Rankings") carries v2 data (GreedyStrategy, 4-way mode)
- Replace with v4 summary table + "see [comparator_rankings.md] for full analysis"
- v2 data is no longer authoritative; the standalone comparator_rankings.md owns this
- Fix H2H field terminology (from C2b scope): `bid_rate_a/b` = team auction-win
  frequency (not per-bidder bid propensity), `make_rate_a/b` = conditional on team
  winning bid
- Update provenance to reference v2 H2H data (post-bugfix reruns)

#### P2-2: Update r0_promotion_report.md (section-by-section from review 2026-02-28)

**§1 — Executive Summary:**
- Lines 26-28 cite v2 comparator numbers (modeloespecifico +2.291, gap 0.624)
- Update to v4: modeloespecifico +1.587, hybrid_olsa +0.455, gap 1.132
- Note methodology change: "single-seat comparator with GluttonStrategy card play"

**§2 — Gate Results:**
- Add brief explanation of what each gate check does (currently just names + PASS/FAIL)
- Example: "artifact_integrity_olsa — verifies model JSON is loadable and schema-valid"
- Note what Tier 2 checks will add at R1+ (calibration, fairness, stability)

**§5 — Comparator Context:**
- **Primary staleness issue.** Full table is v2 data (4-way mode, GreedyStrategy)
- Replace with v4 table (single-seat, GluttonStrategy, 7 bidders with bootstrap CIs)
- Update all v2 references in text: rankings, gap size, methodology description
- Note the v2→v4 methodology change matters: gap nearly doubled (0.624 → 1.132)

**§8 — Exclusions:**
- H2H and C33 are no longer exclusions — they're available as companion reports
- Rename section to "Companion Reports" or "Related Reports" with summarize-and-link
- Convert "now available" notes into proper cross-links with one-line summaries

#### P2-2b: Resolve comparator_rankings.md placeholder sections

PR #470 left two placeholder sections in `comparator_rankings.md`:
- **§4 (Contract-Type Rankings)** — "pending FULL-mode notebook run" of `45_comparator_deep_dive.py`
- **§8 (Auction-Pressure Sensitivity)** — "pending post-fix 4-way rerun"

Action: Either populate from FULL-mode data (§4: ~20 min compute via `45_comparator_deep_dive.py`
in FULL mode), or replace both placeholders with explicit "Deferred to R1" notes explaining:
- §4: Why FULL-mode hasn't been run yet (compute budget / prioritization)
- §8: Whether 4-way mode is worth preserving given single-seat superiority

Decision point: The 4-way rerun (§8) is a design question — if single-seat mode is the
canonical instrument going forward, §8 may be permanently deferred or removed.

#### P2-3: Update measurement_integrity_r0.md
- Update play strategy context: comparator now uses GluttonStrategy (v4), consistent
  with H2H battery (from C2b scope)
- Note that play strategy confound (L3 in original review) is resolved by C2c (#466)

#### P2-4: Update docs/04_reports/README.md
- Directory structure section is stale (shows 3 files, actually 6+)
- Add measurement_integrity_r0.md to index
- Update descriptions to reflect v4 comparator

### Phase 3: Report Conventions Documentation

Codify the patterns from R0 so agents can follow them systematically.

#### P3-1: Create report narrative conventions doc
- **File:** `docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md`
- Sections:
  - **Exec summary convention**: Five-question structure (what, did, found, caveats, decision)
  - **Section commentary convention**: 2-4 sentences after data tables, interpretation + caveats
  - **Summarize-and-link convention**: When to summarize vs link, table sizing guidance
  - **Rigor annotations**: When to flag sample sizes, missing CIs, low R²
  - **Cross-linking convention**: How to reference companion reports, previous rungs
  - **Exemplar references**: Points to R0 reports as the canonical examples

#### P3-2: Create report template registry
- **File:** `docs/02_agent/REPORT_TEMPLATES.md`
- Documents the structure of each recurring report type:
  - Promotion report: sections, required fields, JSON sources
  - Comparator rankings: 9-section structure, what each section covers
  - H2H battery analysis: 8-section structure, what each section covers
  - Measurement integrity: checklist structure, classification scheme
- For each report type: which JSON artifacts it reads, what sections are structural vs
  rung-specific, what sections need interpretation vs data extraction

### Phase 4: `/narrate-report` Skill (auto-generated reports)

Agent skill that adds narrative overlay to auto-generated reports (A1, A2).

#### P4-1: Create skill template
- **File:** `.claude/skills/narrating-reports/SKILL.md`
- Phased template:
  - **Phase 0 — Context loading**
    - Read the auto-generated report (stage 3 output — markdown with embedded charts)
    - Read companion reports in same rung directory
    - Read previous rung's final report (if exists) for tone/structure continuity
    - Read `docs/02_agent/REPORT_NARRATIVE_CONVENTIONS.md` for style guide
  - **Phase 1 — Executive summary**
    - Replace bullet-point format with five-question narrative
    - Add key metrics table (dual-arm side-by-side)
    - Add companion reports cross-link block
  - **Phase 2 — Section commentary**
    - For each data section: add 2-4 sentence interpretation
    - Flag rigor concerns inline (sample sizes, missing CIs)
    - Add summarize-and-link blocks for topics covered by companion reports
  - **Phase 3 — Specialized sections**
    - Populate semantic gate with check breakdown
    - Revise known limitations to be rung-specific
    - Fix reproduction commands (resolve placeholders)
    - Add companion reports section
  - **Phase 4 — Validation checklist**
    - [ ] All companion reports cross-linked?
    - [ ] Sample-size warnings for n < 2000?
    - [ ] Attribution gap explained (not left as TODO)?
    - [ ] Gate decision has rationale?
    - [ ] Reproduction commands have real paths?
    - [ ] No stale v-N data (comparator, H2H versions match latest)?

#### P4-2: Dashboard variant
- Extend or create sibling skill for dashboard narrative
- Adds trend interpretation across rungs ("R1 closed X% of the gap to modeloespecifico")
- Lower priority — dashboard is a single table today

### Phase 5: `/draft-rung-reports` Skill (recurring hand-crafted reports)

Agent skill that produces first drafts of recurring reports (H1-H4) from JSON artifacts
and previous-rung exemplars.

#### P5-1: Create skill template
- **File:** `.claude/skills/drafting-rung-reports/SKILL.md`
- Input: rung identifier (e.g., "r1"), artifact directory path
- Phased template:
  - **Phase 0 — Discovery**
    - Scan `data/artifacts/arc_d/r{N}/` for available JSON artifacts
    - Read previous rung's reports from `docs/04_reports/r{N-1}/`
    - Read `docs/02_agent/REPORT_TEMPLATES.md` for structural requirements
    - Determine which reports can be drafted (based on available artifacts)
  - **Phase 1 — Promotion report draft**
    - Read `promotion_decision_r{N}.json` + `rung_bundle_r{N}.json`
    - Read eval metric files for multi-seed stability table
    - Follow R0 promotion report structure:
      - Exec summary (narrative), Gate results (table), Evaluation metrics (multi-seed),
        Attribution gap (narrative), Comparator context (summarize-and-link),
        Gate thresholds (if recalibrated), Provenance (table)
    - Adapt narrative: "R1 was PROMOTED/ADVANCED/HALTED because..."
    - Flag sections needing human interpretation (e.g., attribution gap direction change)
  - **Phase 2 — Comparator rankings draft**
    - Read `comparator_cis_r{N}.json` + `comparator_battery_r{N}.json`
    - Follow R0 comparator_rankings.md 9-section structure:
      - Summary, Methodology, Rankings table, Contract-type breakdown,
        Pairwise significance, Behavioral profiles, Key observations,
        Auction-pressure sensitivity, Provenance & reproduction
    - Populate data tables from JSON artifacts
    - Draft behavioral profiles using R0 descriptions as base, noting any changes
    - Draft key observations by comparing R{N} rankings to R{N-1}
    - Flag: new bidders, rank changes, tier changes
  - **Phase 3 — H2H battery analysis draft**
    - Read `h2h_battery_quick.json` + `h2h_battery_full.json` + `gate_thresholds_r{N+1}.json`
    - Follow R0 h2h_battery_analysis.md 8-section structure:
      - What was done, C33 ablation (if applicable), Comparator summary,
        H2H full matrix, Gate threshold calibration, Artifact inventory,
        Conclusions, Reproduction
    - Populate dominance tables, pairwise matchups, threshold tables from JSON
    - Draft interpretation: which matchups changed from R{N-1}, new findings
    - Flag: any self-play cells failing sanity, drift in thresholds
  - **Phase 4 — Measurement integrity draft**
    - Read all artifacts, enumerate evaluation batteries
    - Follow R0 measurement_integrity_r0.md checklist structure
    - Carry forward any unresolved (b)-class items from R{N-1}
    - Flag new limitations introduced by R{N} changes
  - **Phase 5 — Output and status**
    - Write drafts to `docs/04_reports/r{N}/` with `_DRAFT` suffix
    - Output summary: which reports were drafted, which artifacts were missing,
      which sections need human review

#### P5-2: Define artifact-to-report mapping
- Machine-readable mapping (JSON or in the skill template) that specifies:
  - Which artifacts each report type requires
  - Which sections can be auto-populated vs need interpretation
  - Which fields from each artifact map to which report sections
- This enables the skill to gracefully degrade: if h2h_battery_full.json doesn't exist yet,
  it can draft partial reports with "FULL data pending" placeholders

#### P5-3: Test on R0 artifacts
- Run `/draft-rung-reports r0` using the existing R0 JSON artifacts
- Compare output against the actual R0 hand-crafted reports
- Iterate on skill template until draft quality is useful as a starting point
- "Useful" = agent or human can review and finalize in <30 min, not rewrite from scratch

### Phase 6: Dual-Track Report & Roster Meta-Analysis (= C6)

Consolidated from `~/.claude/plans/kind-nibbling-sphinx.md` (W6 + W6b + W6c).
Prerequisites: C2b-2 (Phase 2), C3 (H2H reruns, DONE), C4 (#468, DONE).

#### P6-1: Dual-track comparator report (W6)
- Side-by-side presentation of both ranking tracks with explicit estimand labeling:

| Track | Estimand | Source | Key Metrics |
|-------|----------|--------|-------------|
| Decision quality | Declaring-only, every bid evaluated | Single-seat v4 | net_eppd, bid_rate (propensity), make_rate (unconditional) |
| Full-game | Declaring + defending, auction winners only | H2H self-play absolute | fullgame_eppd, team_bid_win_rate, team_make_rate |

- Both tracks now use GluttonStrategy (confound resolved by C2c/#466)
- Track disagreements are primarily estimand-driven (residual: `pair_deals` design difference)
- Analysis of agreement/disagreement between tracks
- **File:** New section in `comparator_rankings.md` or standalone `dual_track_analysis.md`

#### P6-2: Archetype-segmented H2H performance (W6b)
- Tag bidders by behavioral archetype derived from **single-seat comparator** metrics:

| Archetype | Criterion (single-seat) | R0 Bidders |
|-----------|------------------------|------------|
| AGGRESSIVE | bid_rate > 0.95 AND make_rate < 0.65 | fiveheadfred, rankthetank |
| SELECTIVE | bid_rate < 0.50 | hybrid_olsa, modeloespecifico |
| NEUTRAL | bid_rate > 0.95 AND make_rate ≥ 0.65 | stricthellraiser, olsa, olsa_full |

- Use tolerance bands (not exact thresholds) — flag edge cases for manual review
- Per-bidder table: mean H2H delta vs AGGRESSIVE / NEUTRAL / SELECTIVE opponents
- Archetype labels derived from single-seat data only (bid_rate = per-hand propensity);
  do NOT derive from H2H fields (different semantics: team auction-win frequency)

#### P6-3: Roster meta-analysis scatter plots (W6c)
- Three scatter plots decomposing rankings into behavioral components:
  1. **bid_rate × make_rate** — calibration (who overbids?)
  2. **bid_rate × net_eppd** — efficiency (payoff of selectivity)
  3. **make_rate × net_eppd** — conversion (who turns makes into points?)
- All from single-seat comparator v4 data (decision-quality estimand)
- Points labeled by bidder name, colored by archetype
- Track longitudinally across rungs (R0, R1, R2, ...)
- Add to `diagnostics/strategy_charts.py` or new `diagnostics/roster_charts.py`

---

## PR Strategy

| PR | Phase | Items | Depends On | Type |
|----|-------|-------|------------|------|
| **PR-N0a** | P0 | P0-1 (G1–G3) | — | Code: Generator data fixes |
| **PR-N0b** | P0 | P0-2 | Resolve open items 4-5 | Code: Chart runner script |
| **PR-N1** | P1 | P1-0 through P1-4 | PR-N0a, PR-N0b, Step 0 | Doc: R0 rung report refactor |
| **PR-N2** | P2 | P2-1 through P2-4 (incl. P2-2b) | PR-N1 | Doc: Companion report consistency (= C2b-2) |
| **PR-N3** | P3 | P3-1, P3-2 | — | Doc: Conventions + template registry |
| **PR-N4** | P4 | P4-1 | PR-N3 | Skill: `/narrate-report` |
| **PR-N5** | P5 | P5-1, P5-2 | PR-N3 | Skill: `/draft-rung-reports` |
| **PR-N6** | P4+P5 | P4-2, P5-3 | PR-N4, PR-N5 | Testing + dashboard variant |
| **PR-N7** | P6 | P6-1 through P6-3 | PR-N2 | Report+viz: Dual-track + archetype + scatter (= C6) |

**Dependency notes:**
- PR-N0a and PR-N3 have no blockers — start immediately (parallel).
- PR-N0b requires resolving open items 4-5 (calibration curve embedding, model artifact loading).
- PR-N1 (R0 report refactor) is blocked on Step 0 of the contract selection analysis.
  If calibrator is adopted, R0 experiments re-run first, then PR-N1 uses new data.
  If calibrator is not needed, PR-N1 proceeds with current data.
- PR-N3 (conventions) is decoupled from PR-N1 — conventions are model-agnostic.
  PR-N4 and PR-N5 (skills) can be built while waiting for Step 0.
- PR-N7 depends on PR-N2 (needs consistency fixes in companion reports first).

### Critical Path

```
                                    Contract Selection Step 0 (oracle analysis)
                                      │
PR-N0a (generator data fixes)  ─┐    │   (if calibrator: re-run R0 experiments)
                                 ├────┴──→ PR-N1 (R0 exemplar)
PR-N0b (chart runner script)   ─┘              │
                                                ├──→ PR-N2 (C2b-2 consistency) ──→ PR-N7 (C6 dual-track)
                                                │
PR-N3 (conventions docs)  ─────────────────────(parallel, no blockers)
  ├──→ PR-N4 (/narrate-report)     ─┐
  └──→ PR-N5 (/draft-rung-reports)  ─┤──→ PR-N6 (testing)
                                      │
                                 (parallel)
```

**Two independent tracks can proceed in parallel:**
- **Infrastructure track:** PR-N0a → PR-N0b → (ready for PR-N1 when Step 0 resolves)
- **Skills track:** PR-N3 → PR-N4/N5 → PR-N6 (fully independent of Step 0)

---

## Contract Selection Analysis — R0 Ablation Dependency

The contract selection investigation (`plans/contract_selection_analysis.md` v3) may add
a calibration layer for cross-contract utility comparison. **This must be measured at R0**
to preserve the ablation — the same logic as the C33 Gaussian wrapper ablation.

### Why R0, Not R1

If the calibrator is adopted only at R1 alongside other changes (new features, opponent
context, more training data), the calibrator's effect cannot be isolated. The ablation is:

```
R0-without-calibrator  →  R0-with-calibrator     (isolates calibrator effect)
R0-with-calibrator     →  R1                      (isolates R1-specific changes)
```

Deferring the calibrator to R1 collapses both into a single R0→R1 delta where the
calibrator's contribution is confounded with everything else.

### Sequencing: Step 0 Gates R0 Report Finalization

```
Step 0: Oracle analysis (offline, uses existing paired data)
  │
  ├─ Oracle gap small (HIGH/LOW < 3% combined)
  │    → Contract selection is near-optimal
  │    → Document finding in R0 reports
  │    → Finalize R0 reports (Phases 1–2)
  │    → R1 proceeds without calibrator
  │
  └─ Oracle gap meaningful (regret > 0.1 utility)
       → Step 1: Build calibrator prototype
       → Step 2: H2H validation (calibrated vs uncalibrated R0)
       → Re-run R0 experiments with calibrated model
       → Update R0 reports with calibrator ablation results
       → Finalize R0 reports (Phases 1–2)
       → R1 builds on calibrated R0 baseline
```

### Impact on This Plan

**Unaffected (build now, model-agnostic infrastructure):**
- Phase 0: Chart runner script + generator data fixes
- Phase 3: Report conventions + template registry
- Phase 4: `/narrate-report` skill
- Phase 5: `/draft-rung-reports` skill

**Blocked until Step 0 completes:**
- Phase 1: R0 rung report refactor — may need calibrator ablation data
- Phase 2: Companion report consistency — comparator/H2H data may change
- Phase 6: Dual-track + archetype analysis — rankings may shift

**Conditionally blocked (if calibrator adopted):**

| R0 Re-run | Why | Estimated Scale |
|---|---|---|
| R0 eval runs (3 seeds) | New contract mix → different net_eppd, bid_rate, make_rate | 50k deals × 3 seeds |
| R0 comparator battery | Calibrated hybrid_olsa entry replaces uncalibrated | 7+ bidders × 4 seats × 20k deals |
| R0 H2H battery (QUICK+FULL) | New pairwise matchups with calibrated bidder | 49+ cells × 2k-10k deals |
| R0 gate threshold recalibration | Null distribution may shift with new model | Depends on H2H results |
| R0 rung bundle | Updated model artifact, new eval metrics | Bundle rebuild |
| All R0 reports | Produced from new data via four-stage pipeline | Full pipeline run |

### Recommended Execution Order

1. **Build pipeline infrastructure now** (Phases 0, 3, 4, 5) — needed regardless of
   calibrator outcome. This is the critical path for R1 readiness.
2. **Run Step 0 in parallel** — oracle analysis is offline, uses existing paired data,
   fast to execute. The answer determines whether Phases 1–2 proceed as-is or wait.
3. **If calibrator adopted:**
   a. Build calibrator (Step 1) + validate (Step 2) — ~1-2 PRs
   b. Re-run R0 experiment suite with calibrated model
   c. Run four-stage pipeline on new R0 data to produce updated reports
   d. Document calibrator ablation (analogous to `c33_ablation_report.md`)
4. **If calibrator not needed:**
   a. Document oracle analysis finding in R0 reports (contract selection is near-optimal)
   b. Finalize R0 reports (Phases 1–2) with current data
5. **Proceed to R1** once R0 reports are finalized under either branch.

## Future Scope (not in this plan)

- **Makefile pipeline target** — single `make rung-report RUNG=r0` that chains all four stages
  (data prep → chart generation → report generation → narrative overlay prompt)
- **Generator JSON sidecar** — refactor `arc_d_report.py` to emit structured data alongside markdown
  (cleaner stage 3→stage 4 contract, eliminates markdown parsing in `/narrate-report`)
- **PostToolUse hook** — auto-trigger `/narrate-report` after `generate_arc_d_rung_report` calls
- **PostToolUse hook** — auto-trigger `/draft-rung-reports` after gate runner completes
- **Chart runner extensions** — add comparator/H2H charts for companion reports
  (currently only produces rung-report charts)
- **Per-run ANALYSIS_SUMMARY overlay** — narrative for experiment-level reports (low priority)
- **Notebook narrative** — auto-generate markdown cells summarizing notebook outputs

---

## Resolved Questions

All 6 open questions were resolved on 2026-02-28. See "Resolved Questions" in Design Decisions above.

## Remaining Open Items

1. **Archive versioning label format.** Proposed: `model_arc_r0_v1_20260224.md` (vN + original date).
   Confirm this pattern works for cases where a report has multiple revisions within the same day.

2. **Cross-link update scope.** Rename `model_arc_r0_20260224.md` → `model_arc_r0.md` completed
   in PR-N1 (B3). All references updated in docs/ and plans/.

3. **Eval data glob pattern.** The regeneration command uses `*.jsonl` — need to verify the exact
   log file path in the eval run directory before running.

4. **Calibration curve embedding.** The generator doesn't currently look for `calibration_curve.png`.
   Need to add embedding support in `_render_model_performance()` (small addition to P0-1 or P0-2).

5. **Chart runner model artifact loading.** Charts #7-10 (coefficient heatmap, pred-vs-actual,
   residuals, dual-arm comparison) require model artifacts (coefficients, predictions). Need to
   determine whether these are loaded from the bundle, from the eval run, or need separate loading
   logic in the chart runner script.
