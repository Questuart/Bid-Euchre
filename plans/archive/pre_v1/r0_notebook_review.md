# R0 Notebook Review Log

> Reviewed: 2026-02-24
> Files: `notebooks/arc_d/r0/{10_feature_health,20_outcome_health,30_feature_outcome_eval}.py`
> Purpose: Section-by-section review to generate cleanup plan

---

## Legend

| Tag | Meaning |
|-----|---------|
| **BUG** | Incorrect behavior or silent data corruption risk |
| **RIGOR** | Violates statistical rigor or gating standards |
| **DRY** | Duplicated logic that should be consolidated |
| **STYLE** | Code quality / readability improvement |
| **GAP** | Missing analysis or unfilled section |
| **FRAGILE** | Works today but will break under reasonable changes |
| **DOC** | Misleading or stale documentation / labeling |

---

## 10_feature_health.py

### S0 Configuration & Data Loading (lines 35-127)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 1 | BUG | S0:36 | `EVAL_LOG_PATH` is a repo-root-relative path (`data/runs/...`) but Jupyter kernels start CWD in the notebook's directory (`notebooks/arc_d/r0/`). **The path never resolves when running the notebook normally** — it silently falls to synthetic data every time. Additionally, data source switching is undocumented. **Fix:** (a) add repo-root detection + `os.chdir()` at top of S0, (b) default EVAL_LOG_PATH to `""`, (c) add comment block in parameters explaining the control, (d) add discovery cell that globs `data/runs/arc_d_eval*`, (e) add explicit warning when path set but unresolved. Apply to all 3 notebooks. | **High** |
| 2 | FRAGILE | S0:70 | `max_deals = MODE_DEAL_COUNTS.get(MODE)` — no default. Invalid MODE silently falls to 30 deals. **Fix:** add default + warning print. | Low |
| 3 | GAP | S0:94-123 | Synthetic fallback only generates 3 features (`feat_hand_value`, `feat_trump_count`, `feat_bowers`). Real eval data has 39. Downstream S5/S6 show thin results on synthetic. **Fix:** align synthetic features across all 3 notebooks (use the 10-feature set from 30_). | Medium |
| 4 | STYLE | S0:94 | `rng = np.random.default_rng(42)` — SEED not named. 20_ and 30_ use `SEED = 42`. **Fix:** add `SEED = 42` to parameters, use throughout. | Low |
| 4b | DRY | S0:44-127 | Data loading duplicated across all 3 notebooks with subtle differences. Intentional per standalone-copy pattern. **Defer** — not worth extracting to shared helper for 3 files. | Low (defer) |

### S1 Health Scorecard (lines 129-172)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 5 | OK | S1 | Health scorecard + bar chart. Clean implementation. No issues. | — |

### S2 Dataset Integrity (lines 174-254)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 6 | OK | S2 | Four integrity checks (rows per deal, feat_* columns, NaN audit, duplicates). Each handles missing columns with SKIP. Sound. | — |

### S3 Strata Completeness (lines 256-332)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 7 | FRAGILE | S3:289 | `df.drop_duplicates(subset=["deal_id"])` takes the first row per deal (seat 0 by default due to sort order). Fine for deal-level columns (contract_type, trump) but fragile if data ordering changes. Compare to `20_outcome_health.py:139` which explicitly filters `df[df["seat"] == 0]`. | Low |

### S4 Symmetry Analysis (lines 334-540)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 8 | RIGOR | S4.2:376 | ANOVA p-value printed but no fail-fast gate. The result is informational only — no assert or gate check records whether trump suit symmetry holds. Contrast with 20_outcome_health.py S3 which has explicit `|delta| < 0.25` gates. | Medium |
| 9 | RIGOR | S4.4:489-493 | Same issue: per-contract ANOVA for seat balance is printed but not gated. Should at minimum record results for S7 summary. | Medium |
| 10 | OK | S4.3 | Team symmetry violin plot faceted by contract type. Correct. | — |

### S5 Feature Distributions (lines 542-585)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 11 | RIGOR | S5:551-556 | **Faceting rule violation.** Feature distribution histograms (`plot_feature_distributions`) and correlation matrix (`plot_feature_correlation`) are computed on the full dataset WITHOUT faceting by contract_type. Per project convention: "Every chart and table MUST be faceted by contract_type or explicitly justify pooling." No justification provided. | High |
| 12 | STYLE | S5:552 | Feature selection by pooled variance — reasonable for exploration but variance ranking changes by contract type (suit features irrelevant for high/low). The pooled ranking may hide contract-specific important features. | Low |

### S6 Feature-Label Relationships (lines 587-702)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 13 | BUG | S6:615 | `corr_df.fillna(0).values` — NaN correlations (from insufficient data) are replaced with 0.0 in the heatmap. This is misleading: 0.0 means "no correlation" while NaN means "couldn't compute." Should use a distinct color or mask for NaN cells. | Medium |
| 14 | OK | S6 | Pearson correlation heatmap faceted by contract type. Top 10 features table. Scatter plots for top 3 by max |r|. Sound analysis. | — |

### S7 Summary (lines 704-751)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 15 | FRAGILE | S7:714 | `"scorecard" in dir()` — uses Python's `dir()` to check if variable exists. Fragile; a cell execution order change breaks this silently. Should use a dedicated flag variable (e.g., `_scorecard_computed = True`). | Medium |
| 16 | DOC | S7:747-748 | **Wrong companion notebook names.** References "01_model_rung_template.py" and "20_matchup_analysis.py" — these are template-era names. Actual companions are `20_outcome_health.py` and `30_feature_outcome_eval.py`. | Medium |
| 17 | GAP | S7 | No aggregate gate summary table. Section S4 computes ANOVA results but they aren't rolled up into the summary. Compare to 20_outcome_health.py S7 which has a proper gate_df. | Medium |

---

## 20_outcome_health.py

### S0 Configuration & Data Loading (lines 34-148)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 18 | FRAGILE | S0:35 | Same hardcoded `EVAL_LOG_PATH` issue as #1. | Medium |
| 19 | STYLE | S0:72 | `SEED = 42` defined as a module-level variable. Good — `10_feature_health.py` hardcodes `42` directly in `rng = np.random.default_rng(42)` (inconsistent). | Low |
| 20 | OK | S0 | Synthetic data includes auction columns (winning_bid, is_bidder, made_bid, etc.). More complete than 10_'s synthetic data. | — |

### S1 Fail-Fast Validation (lines 150-216)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 21 | STYLE | S1:172-175 | `df.groupby("deal_id").apply(lambda g: ...)` is slow for large datasets and triggers pandas FutureWarning. Can be replaced with a pivot or merge-based approach: group by (deal_id, team), take first tricks_won per team, and check sum. | Medium |
| 22 | OK | S1 | Hard asserts for tricks_won range, team totals, no missing values. Good fail-fast pattern. | — |

### S2 Outcome Distributions (lines 218-280)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 23 | OK | S2 | Histogram + violin by contract type. Summary table with percentiles. Clean. | — |

### S3 Team & Seat Balance (lines 282-347)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 24 | DOC | S3 title | Section header says "Team & Seat Balance" but **only analyzes team balance**. Seat balance analysis is entirely missing. Should either add seat analysis or rename the section. | Medium |
| 25 | OK | S3 | Mann-Whitney U test for team balance with `|delta| < 0.25` gate. Good nonparametric choice. | — |

### S4 Auction Health (lines 349-382)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 26 | RIGOR | S4:376 | `pass_rate = mean_passes / mean_rounds` — this computes the ratio of means, not the mean of per-deal ratios. These differ (Jensen's inequality). For accuracy: compute per-deal pass rate first, then average. However, for a summary table this is acceptable as an approximation. | Low |
| 27 | OK | S4 | Library composite figure + auction summary table. Reasonable. | — |

### S5 Bidder Performance (lines 384-433)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 28 | OK | S5 | Make rate with binomial CI, FLAG gate for extremes. Clean implementation. | — |

### S6 Distribution Analysis (lines 435-456)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 29 | OK | S6 | CDF/CCDF by contract type using library functions. Clean. | — |

### S7 Summary (lines 458-536)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 30 | GAP | S7:490 | S5 bidder performance gate uses make_rate bounds [0.2, 0.95] but these thresholds aren't documented anywhere. Should reference a doc or explain rationale. | Low |
| 31 | GAP | S7 | No gate for S2 (outcome distributions) — e.g., no check that mean tricks_won is near 5.0 for self-play, or that std is within expected range. | Low |

---

## 30_feature_outcome_eval.py

### S0 Configuration & Data Loading (lines 36-218)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 32 | FRAGILE | S0:37-38 | Same hardcoded paths issue as #1. Additionally `ARTIFACT_DIR` hardcoded to `data/artifacts/arc_d/r0`. | Medium |
| 33 | FRAGILE | S0:159-168 | `_resolve_path()` walks up parent directories to find repo root. Clever but opaque — if the bundle JSON contains paths relative to a different root, this silently resolves to the wrong file. A simpler approach: detect repo root via `.git` directory. | Low |
| 34 | STYLE | S0:64 | `from bid_euchre.reporting.evaluator import load_eval_metrics` — should verify this function's signature matches how it's called at line 176 (takes a string path). | Low |
| 35 | OK | S0 | Synthetic data generates 10 features. METRIC_ALIASES dict provides canonical mapping. Good. | — |

### S1 Feature-Outcome Correlations (lines 220-369)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 36 | OK | S1 | Heatmap + top 5 per contract + full table with p-values. Properly faceted by contract type. | — |

### S2 Model Specification (lines 371-566)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 37 | STYLE | S2:427-428 | `try: from bid_euchre.diagnostics.charts import plot_coefficient_heatmap` — conditional import inside a cell body. These library functions exist (verified), so the try/except is defensive but adds complexity. Consider moving imports to S0 and removing the fallback. | Low |
| 38 | STYLE | S2:643-644 | Same pattern with `plot_model_diagnostics`. | Low |
| 39 | OK | S2 | Coefficient display, heatmap, dual-arm comparison. Sound analysis. | — |

### S3 Model Performance Diagnostics (lines 568-838)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 40 | DRY | S3+S4+S5 | **Predictions computed 3 times.** S3 (line 607-609), S4 (line 871-873), and S5 (line 1045-1047) each independently compute `X @ weights + bias` for the same data. Should compute once in S3 and store in a dict for reuse. | Medium |
| 41 | RIGOR | S3:736 | Bootstrap with only 100 iterations in QUICK mode. For R2 CI this is quite thin — 500 minimum would give more stable percentile estimates. Not blocking but worth noting. | Low |
| 42 | OK | S3 | Pred vs actual, residual distribution, residuals vs predicted, bootstrap R2 with CIs. Thorough diagnostics. | — |

### S4 Dual-Arm Comparison (lines 840-1010)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 43 | OK | S4 | R2 per arm per contract, attribution gap, eval metrics table. Sound. | — |

### S5 Calibration Analysis (lines 1012-1198)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 44 | DRY | S5:1137-1162 | Standalone prediction distribution plot duplicates the one inside the calibration fallback (lines 1112-1126). The fallback already includes a prediction distribution panel, so this creates a redundant chart when the fallback is used. | Low |
| 45 | OK | S5 | Calibration curve + bins table. Good analysis. | — |

### S6 Rung-Specific Analysis (lines 1200-1220)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 46 | GAP | S6 | **Placeholder not filled for R0.** The template says "fill when copying for a specific rung" and lists R0 examples (Phase 0 Ridge comparison, feature selection justification, comparator landscape, attribution gap investigation, seed sensitivity). None of these are implemented. This is the most significant gap — it's the section that would differentiate this from a generic template run. | High |

### S7 Summary & Promotion Readiness (lines 1222-1322)

| # | Tag | Section | Issue | Severity |
|---|-----|---------|-------|----------|
| 47 | GAP | S7:1315-1321 | Promotion recommendation is a manual checklist ("Review all sections above"). No automated gate aggregation. Compare to 20_outcome_health.py which has a proper gate_df with PASS/FAIL counts. | Medium |
| 48 | STYLE | S7:1238 | `n_zero_var = sum(df[c].var() == 0 ...)` — floating point comparison with `== 0` could miss near-zero variance features. Use `< 1e-10` or similar threshold. | Low |

---

## Cross-Cutting Issues

| # | Tag | Issue | Severity |
|---|-----|-------|----------|
| 49 | DRY | Data loading boilerplate (~40-50 lines) duplicated across all 3 notebooks with subtle differences (synthetic feature sets, SEED handling, path resolution). Consider a shared `_load_eval_data()` helper in `bid_euchre.datasets.eval_dataset`. | Medium |
| 50 | STYLE | Chart save boilerplate repeated ~20 times across all notebooks: `if CHART_OUTPUT_DIR: out = Path(...); out.mkdir(...); fig.savefig(...)`. Consider a helper: `_save_chart(fig, name)`. | Low |
| 51 | FRAGILE | All 3 notebooks hardcode the same `EVAL_LOG_PATH` and artifact paths. If the eval run is regenerated with a different timestamp, all 3 must be updated manually. | Medium |
| 52 | GAP | No cross-notebook consistency check. The 3 notebooks load the same data independently but there's no verification they're analyzing the same dataset (e.g., comparing deal counts or a dataset fingerprint). | Low |

---

## Priority Summary

### High Severity (2 items — should fix before next rung)
- **#11**: S5 feature distributions not faceted by contract_type (faceting rule violation)
- **#46**: S6 rung-specific placeholder not filled for R0

### Medium Severity (14 items — should fix in cleanup PR)
- **#1, #18, #32, #51**: Hardcoded paths across all notebooks
- **#3**: Thin synthetic fallback in 10_feature_health
- **#8, #9**: Symmetry ANOVA results not gated in 10_
- **#13**: NaN correlations silently replaced with 0.0
- **#15**: Fragile `"scorecard" in dir()` check
- **#16**: Wrong companion notebook names in 10_'s S7
- **#17, #47**: No aggregate gate summary in 10_ and 30_
- **#21**: Slow `.apply(lambda)` in 20_ S1
- **#24**: Section title mismatch in 20_ S3
- **#40, #49**: DRY violations (triple prediction computation, data loading duplication)

### Low Severity (12 items — nice-to-have)
- #2, #4, #7, #12, #19, #26, #30, #31, #33, #34, #37, #38, #41, #44, #48, #50, #52
