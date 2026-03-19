# Dashboard Data Contract Completion

<!-- review-tier: medium -->

**Date:** 2026-03-18
**Status:** DRAFT
**Owner:** author-d
**Audience:** Steward review

## 1. Finding Evaluation

The finding claims "dashboards still reflect the old data contract and old chart
implementations." This is **partially correct** — but several specific claims
overstate the code gaps while understating the data-availability root cause.

### 1.1 Claims Verified as Correct

| Claim | Evidence |
|-------|----------|
| `outcome_distributions.csv` is synthetic in all bundles | Every bundle shows `source=synthetic`, single-bin aggregate data, `degraded:synthetic` status file |
| `bid_levels.csv` uses aggregate schema in all bundles | R0 QUICK: `model,bid_rate,make_rate,pass_rate` — aggregate, not per-level |
| `predictions.csv`, `residuals.csv`, `calibration_bins.csv` absent from all bundles | No file present in any R0-R2 QUICK or FULL chart_data/ |
| `seat_balance.csv` absent from all bundles | No file present in any bundle |
| Health dashboard missing CDF/CCDF panel from plan spec §6.2 | No CDF/CCDF function exists in `generate_rung_charts.py` for the health dashboard |
| Health dashboard panel layout doesn't match plan spec §6.2 | Current: rates/mix/outcome/bid-level/seat/bid-type vs spec: outcome-violin/CDF/seat/mix/rates/bid-level |

### 1.2 Claims That Are Incorrect or Overstated

| Claim | Actual Code State |
|-------|-------------------|
| "`generate_model_eval_csvs()` still expects `actual`" | **Wrong.** Line 1948-1952: already has `"actual" if "actual" in family_df.columns else ("tricks_won" if "tricks_won"...)` fallback |
| "seat balance still expects `seat`, not `focal_seat`" | **Wrong.** Line 1753-1756: already handles both `seat` and `focal_seat` via fallback |
| "outcome distributions are still rendered as grouped bars" | **Wrong.** Lines 888-914 (standalone) and 1699-1731 (dashboard): violin+box code exists and activates for real data. It doesn't activate because data is synthetic |
| "`bid_levels.csv` still emits aggregate rates" | **Partially wrong.** `_extract_bid_levels_from_parquet()` (line 1151) produces `model,contract,bid_level,count,fraction` schema — but only when parquet available |
| "chart generators still implement legacy visuals" | **Mostly wrong.** Chart 9, 13, dashboard panels already have updated renderers. The issue is data quality, not visualization code |

### 1.3 Root Cause

The **code** was substantially updated during the reporting refactor (PRs #834-#848).
The extractors, chart generators, and dashboard renderers all support the new schemas.

The **data** flowing through them is degraded because:

1. **Parquet data is ephemeral** — lives in `data/runs/` (gitignored), only exists
   on the machine during/after experiment runs
2. **QUICK parquet doesn't exist** — no QUICK-mode datasets were ever generated
3. **No joblib models on disk** — predictions/residuals/calibration require loading
   trained models, which aren't persisted after training
4. **Report regeneration ran without data** — the refactor PRs regenerated bundles
   from committed JSON artifacts only, so all parquet-backed paths were skipped

The fix is not in the extractors (they work). The fix is in **ensuring chart_data
CSVs are generated and committed while run artifacts are still on disk**, and in
**completing the dashboard recomposition that the plan specified but wasn't done**.

### 1.4 What's Actually Available

| Data Source | SMOKE | QUICK | FULL |
|-------------|-------|-------|------|
| Parquet on disk | ✅ seed_1001 | ❌ None | ✅ seed_1001 (chunked) |
| Joblib models | ❌ | ❌ | ❌ |
| H2H battery JSON (committed) | — | ✅ R0-R3 | ✅ R0-R2 |
| Training artifact JSON (committed) | — | ✅ R0-R3 | ✅ R0-R2 |

**Key parquet limitation:** The parquet files have no `model` column. The extractors
fall back to `model="unknown"`, which produces valid but unlabeled distributions.
For per-model distributions, the parquet would need to be generated per-model or
the model identity would need to be inferred from context (e.g., filename).

## 2. Actionable Gaps

### Category A: Code Changes (in scope for this plan)

| # | Gap | Severity | Files |
|---|-----|----------|-------|
| A1 | Health dashboard panel layout doesn't match plan §6.2 | Medium | `generate_rung_charts.py` |
| A2 | Health dashboard missing CDF/CCDF tail panel | Medium | `generate_rung_charts.py` |
| A3 | Model eval dashboard residual panel uses bars, not violin | Low | `generate_rung_charts.py` |
| A4 | No `model` derivation from parquet filename/context | Medium | `tables.py` |
| A5 | `outcome_summary.csv` still generated and present in bundles | Low | `tables.py` |

### Category B: Infrastructure / Run Gaps (out of scope — log for follow-up)

| # | Gap | Blocked By |
|---|-----|------------|
| B1 | No QUICK parquet datasets exist | Requires running dataset build in QUICK mode |
| B2 | No joblib models persisted after training | Requires changing training step to preserve models |
| B3 | Historical bundles (R0-R2) have synthetic data | Requires re-running step 6 on a machine with data |
| B4 | R3 FULL bundle doesn't exist yet | R3 FULL run still in progress |

### Category C: Already Working (no action needed)

- `actual` vs `tricks_won` column handling
- `seat` vs `focal_seat` column handling
- Violin+box chart rendering (activates with real data)
- Per-bid-level histogram rendering (activates with parquet data)
- Synthetic degradation markers and status files
- Parquet discovery and wiring in orchestration step 6

## 3. Implementation Plan

### PR 1: Health Dashboard Recomposition

**Scope:** Reorder and recompose the health dashboard to match plan §6.2.

**Current panels:**
1. Bid rate / make rate (summary bars)
2. Contract mix (stacked bars)
3. Outcome distributions (violin+box or synthetic bars)
4. Bid-level distribution
5. Seat balance
6. Bid-type breakdown

**Target panels (per plan §6.2):**
1. Violin + box outcome distributions by contract
2. CDF / CCDF tail panel by contract (NEW)
3. Seat balance
4. Contract mix
5. Bid / pass / make rates
6. Bid-level distribution

**Tasks:**
1. Reorder existing panels to match target layout
2. Implement CDF/CCDF tail panel (Panel 2) — reads `outcome_distributions.csv`,
   renders empirical CDF curves by contract and model when real data exists;
   shows explicit "requires row-level data" placeholder when synthetic
3. Promote outcome distributions to Panel 1 position
4. Replace bid-type breakdown panel (6) with bid-level distribution
5. Update panel titles and sizing for the new layout
6. Add explicit "unavailable: requires parquet data" placeholders where
   degraded or missing data makes panels non-informative

**Files:**
- `scripts/internal/generate_rung_charts.py` — `generate_dashboard_health()`

**Acceptance:**
- Dashboard panel order matches plan §6.2
- CDF/CCDF panel renders with real data, shows clear placeholder with synthetic
- All 6 panels either display useful content or explicit unavailable markers

**Estimated size:** ~150 lines changed in one file

---

### PR 2: Model Eval Dashboard Polish

**Scope:** Improve model eval dashboard rendering when chart_data CSVs exist.

**Tasks:**
1. Upgrade residual panel from bars to stepped histogram or violin when row-level
   residuals are available (add detection for row-level vs binned schema)
2. Add contract-faceted view to pred_vs_actual panel (currently pooled) — use
   color by contract instead of by model when single model, vice versa
3. Add explicit degraded-state annotations on all panels when source CSVs are
   absent ("No model artifacts available" vs generic "Data not available")
4. Add N-sample counts to calibration panel points

**Files:**
- `scripts/internal/generate_rung_charts.py` — `generate_dashboard_model_eval()`

**Acceptance:**
- When predictions.csv/residuals.csv/calibration_bins.csv exist, all panels render
  meaningful diagnostics
- When absent, placeholders clearly explain *why* (model artifacts not persisted)
- Panel 4 uses violin or stepped histogram, not plain bars

**Estimated size:** ~80 lines changed in one file

---

### PR 3: Parquet Model Derivation + outcome_summary Cleanup

**Scope:** Fix `model` column handling for parquet-backed extractors and remove
stale `outcome_summary.csv` from generation.

**Tasks:**
1. In `_extract_outcome_distributions_from_parquet()`: when no `model` column
   exists, derive model name from the parquet file path (parent directory name
   or a `model_label` passed by the caller) instead of defaulting to "unknown"
2. Same fix in `_extract_bid_levels_from_parquet()` — consistent model derivation
3. In `generate_chart_data()`: stop generating `outcome_summary.csv` (plan §3.10
   says it "must be removed from canonical rendering")
4. In chart generators: remove any remaining `outcome_summary.csv` reader paths

**Files:**
- `src/bid_euchre/arc_d_v2/tables.py`
- `scripts/internal/generate_rung_charts.py` (if it reads outcome_summary)

**Acceptance:**
- Parquet-backed extractors produce meaningful model labels, not "unknown"
- `outcome_summary.csv` no longer generated or read by chart code
- No new files created; existing file count in chart_data/ decreases by 1

**Estimated size:** ~60 lines changed across 2 files

---

### PR 4 (optional, follow-up): Bundle Re-generation with Parquet Data

**Scope:** Re-run table generation step for FULL R0-R2 bundles using the parquet
data that exists on the machine, producing real chart_data CSVs.

**Prerequisite:** PRs 1-3 merged. FULL parquet data available on disk.

**Tasks:**
1. Run step 6 for R0, R1, R2 FULL mode, pointing at base_datasets/pre_r3/full/
2. Verify chart_data CSVs are generated (outcome_distributions, bid_levels,
   seat_balance with `source=parquet`)
3. Commit updated bundles
4. Note: predictions/residuals/calibration will still be absent (no joblib models)

**Blocked by:** B2 (no joblib models), partially by PR 3 (model derivation)

**This PR is optional** — it can wait for R3 FULL completion and be done as
part of the lineage closeout regeneration.

## 4. Out of Scope — Follow-up Items

These are logged for tracking but are not part of this plan:

1. **QUICK parquet dataset generation** — would require a new dataset-build run
   in QUICK mode. Not urgent; QUICK bundles are preliminary.
2. **Joblib model persistence** — training step currently doesn't preserve model
   files after evaluation. Would require changes to training pipeline.
   Impact: predictions.csv, residuals.csv, calibration_bins.csv will remain
   absent until models are preserved.
3. **Historical bundle synthetic data** — R0-R2 QUICK bundles will remain
   synthetic. This is acceptable given QUICK's preliminary status.
4. **decision_comparison.csv and disagreement_outcomes.csv** — require parquet
   with `bid_decision` and `model` columns. The current parquet schema lacks
   these. Would require dataset build changes. Low priority.

## 5. Sequencing

```
PR 1 (health dashboard recomposition)
  └─→ PR 2 (model eval dashboard polish)   [independent, can parallel]
  └─→ PR 3 (parquet model derivation)      [independent, can parallel]
        └─→ PR 4 (bundle regeneration)     [depends on PR 3 + data]
```

PRs 1, 2, 3 are independent and can be done in parallel or serial.
PR 4 depends on PR 3 and available data.

## 6. Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| CDF/CCDF panel looks empty with synthetic data | High | Explicit placeholder with "requires row-level data" note |
| Model derivation from path produces wrong labels | Low | Use dataset directory name which encodes the mode |
| Dashboard layout change breaks existing tests | Low | Chart tests are end-to-end smoke tests; update expected panels |
| PR 4 regeneration produces partial bundles | Medium | Only regenerate FULL where parquet exists; leave QUICK as-is |

## Outcome

**Status:** COMPLETE (2026-03-18)

All 4 session plan PRs implemented and merged in 2 PRs:

| PR | Scope | Status |
|----|-------|--------|
| #877 | PRs 1-3: PENDING→PRELIMINARY fix, health dashboard recomposition, model eval polish, parquet model derivation, outcome_summary removal | ✅ Merged |
| #881 | PR 4: R0-R2 FULL bundle regeneration with parquet-backed chart_data (6 new CSVs × 3 rungs) | ✅ Merged |

Previously #865 corrected the governing plan status and Chart 20 registry (prerequisite).
