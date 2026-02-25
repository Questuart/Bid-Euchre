# R0 Notebook Fix Execution Plan (v2)

> Source: [`plans/r0_10_feature_health_review.md`](r0_10_feature_health_review.md)
> Total issues: 58 (1 High, 43 Medium, 11 Low, 3 Info)
> Critical path: C32 (`points_won` infrastructure)
> PRs: **9** (Phase 0–2) + 3 deferred
> Created: 2026-02-24 | Revised: 2026-02-25 (v2 rewrite)

---

## Overview

This plan executes the 58 issues identified in the R0 notebook review. The work is organized into **9 PRs across 3 phases**, ordered by dependency. Each PR is independently implementable — an agent needs only this plan, the review doc, and the listed reference files.

### v2 Changes from v1

- **17 PRs → 9 PRs**: Notebook-centric ownership replaces cross-cutting PRs.
- **5 phases → 3 phases**: Eliminated unnecessary sequencing.
- **Zero file overlap in Phase 1**: Each notebook is exclusively owned by one PR.
- **`points_won` semantics aligned**: Uses `compute_points()` from `scoring.py`; never `None`.
- **C59 distributed**: Audit/fix in each notebook-owner PR; PR-6 adds contract test only.
- **Report path corrected**: `docs/04_reports/r0/` (not `docs/04_reports/arc_d/`).
- **F1 recursive fix**: Makefile + `run_notebooks.py` glob fix included in PR-0.

### Key Constraints

- **C32** (`points_won` in `_expand_record()`) is the only issue touching `src/` production code. It blocks 6 downstream issues.
- **One concept per PR** — each PR targets a specific notebook (Phase 1) or cross-cutting concern (Phase 0/2).
- **Phase 1 PRs have zero file overlap** — any can run in parallel without merge contention.

---

## PR Summary Table

| PR | Phase | Scope | Size | Depends | Exclusive Files |
|----|-------|-------|------|---------|-----------------|
| PR-0 | 0 | C32 `points_won` infra + Makefile `notebook-run-arc-d` recursive fix + `run_notebooks.py` `recursive=True` | M | — | `eval_dataset.py`, `test_eval_dataset.py`, `Makefile`, `scripts/run_notebooks.py` |
| PR-1 | 1 | 10_ all fixes: C1,C2,C3,C5,C10,C13,C15,C18,C19,C20,C21,C22,C23-T1(S4.3/S4.4),C23-T2(S5/S6),C31,C59(audit/fix) | L | PR-0 | `10_feature_health.{py,ipynb}` |
| PR-2 | 1 | 20_ all fixes: C1,C20(S2/S6),C22,C23-T1(S3),C23-T2(S2),C24,C25,C26,C27,C28,C29,C30,C31,C59(audit/fix) | L | PR-0 | `20_outcome_health.{py,ipynb}` |
| PR-3 | 1 | 30_ all fixes: C2,C6,C12,C16,C22,C23-T2(S1),C31,C34,C35,C36,C37,C56,C59(audit/fix) | XL | PR-0 | `30_feature_outcome_eval.{py,ipynb}` |
| PR-4 | 1 | 40_ all fixes except §2/§4: C1,C2,C11,C15,C22,C23-T1(§3),C23-T2(§5/§7.5),C34,C35,C36,C38,C41,C44,C45,C46,C47,C48,C51,C52,C53,C54,C55,C58,C59(audit/fix) | XL | PR-0 | `40_r0_baseline.{py,ipynb}` |
| PR-5 | 1 | 50_ all fixes: C1,C2,C7,C22,C31,C59(audit/fix) | S | PR-0 | `50_r0_matchups.{py,ipynb}` |
| PR-6 | 1/late | C59 prefix-convention contract test (validates all notebooks) | S | PR-1..PR-5 | `test_notebook_template_contract.py` |
| PR-7 | 2 | 25_ new notebook (C49,C39,C40,C42,C43) + extract 40_ §2/§4 | L | PR-4 | `25_auction_health.{py,ipynb}`, 40_ §2/§4 only |
| PR-8 | 2 | Formal reports: R0 Promotion Report, Model Spec Doc, Comparator Rankings | M | PR-1..PR-7 | `docs/04_reports/r0/` |

---

## File Ownership Matrix (Phase 1 — Zero Overlap)

| File | PR-1 | PR-2 | PR-3 | PR-4 | PR-5 |
|------|------|------|------|------|------|
| `10_feature_health.{py,ipynb}` | **own** | — | — | — | — |
| `20_outcome_health.{py,ipynb}` | — | **own** | — | — | — |
| `30_feature_outcome_eval.{py,ipynb}` | — | — | **own** | — | — |
| `40_r0_baseline.{py,ipynb}` | — | — | — | **own** | — |
| `50_r0_matchups.{py,ipynb}` | — | — | — | — | **own** |

Phase 1 PRs touch **only** their owned notebook files. No merge contention.

---

## Phase 0: Infrastructure (Sequential — Must Ship First)

### PR-0: `points_won` infra + Makefile/runner recursive fix [M]

**Branch:** `feat/r0-nb-0-points-infra`

**Issues:** C32, F1

**Why first:** Only PR touching `src/` code. Blocks C30, C41, C46, C55, C58, and 30_ S1 dual correlation. Also fixes F1 (recursive notebook execution).

**Files:**
- `src/bid_euchre/datasets/eval_dataset.py` — modify `_expand_record()`
- `tests/unit/test_eval_dataset.py` — add tests for `points_won` computation
- `Makefile` — L98: change default pattern to `notebooks/arc_d/**/*.ipynb`
- `scripts/run_notebooks.py` — L59: add `recursive=True` to `glob.glob()` call

**Scope:**

1. **C32 — `points_won` computation:**

   Use `compute_points()` from `bid_euchre.scoring` (L10-50) once per record. Map team-level results to per-seat:

   ```python
   from bid_euchre.scoring import compute_points

   # Inside _expand_record(), after building the row dict:
   # Call once per record, map to per-seat.
   pts_t0, pts_t1 = compute_points(winning_bid, bidder_position, t0, t1)
   # Per seat: team 0 seats (0, 2) get pts_t0; team 1 seats (1, 3) get pts_t1
   points_won = pts_t0 if seat in (0, 2) else pts_t1
   row["points_won"] = points_won  # NEVER None
   ```

   Semantics:
   - No-bid: `points_won = tricks_won` (matches `scoring.py` L36-38)
   - Made bid: declaring `points_won = tricks_won`, defending `points_won = tricks_won`
   - Set bid: declaring `points_won = -winning_bid`, defending `points_won = tricks_won`
   - **`points_won` is NEVER None** — `compute_points()` handles the no-bid case by returning tricks

2. **F1 — Makefile recursive fix:**

   `Makefile` L98: change default from `notebooks/arc_d/*.ipynb` to `notebooks/arc_d/**/*.ipynb`

3. **F1 — Runner recursive fix:**

   `scripts/run_notebooks.py` L59: change `glob.glob(str(repo_root / pattern))` to `glob.glob(str(repo_root / pattern), recursive=True)`

4. **Tests:**
   - Made bid: declaring team points = tricks_won
   - Set bid: declaring team points = -winning_bid
   - Defending team: points always = tricks_won
   - No-bid: both teams get tricks_won (not None)

**Acceptance criteria:**
- `uv run python -m pytest tests/unit/test_eval_dataset.py -x -q` passes
- `build_eval_dataset()` returns DataFrame with `points_won` column (never None)
- `make notebook-run-arc-d` discovers R0 notebooks recursively
- `make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"` runs R0 notebooks

**Phase 0 exit gate:**
```bash
uv run python -m pytest tests/unit/test_eval_dataset.py -x -q
make check-quiet
make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"
```

---

## Phase 1: Per-Notebook Fixes (Parallel — Zero File Overlap)

All 5 notebook PRs are independent and have zero file overlap. They can be implemented and merged in any order or simultaneously. All depend on PR-0 for `points_won` availability.

PR-6 (contract test) depends on PR-1 through PR-5 completing first, since it validates the prefix fixes made in those PRs.

### C59 Ownership Model

C59 is **distributed** across PRs with explicit per-PR responsibility:
- **PR-1 through PR-5**: Each PR includes "C59(audit/fix)" — the notebook owner audits ALL `plot_*` calls in their notebook and strips `feat_` prefix where the diagnostics API expects unprefixed names. If no instances exist, the PR notes "C59: no prefix issues found."
- **PR-6**: Adds a static contract test that greps all `.py` notebook files for known `feat_`-prefix → `plot_*` anti-patterns. This test catches future regressions after notebooks are fixed.

---

### PR-1: 10_feature_health — all fixes [L]

**Branch:** `feat/r0-nb-1-10-feature-health`

**Issues:** C1, C2, C3, C5, C10, C13, C15, C18, C19, C20, C21, C22, C23-T1(S4.3/S4.4), C23-T2(S5/S6), C31, C59(audit/fix)

**Files:** `notebooks/arc_d/r0/10_feature_health.{py,ipynb}` (exclusive)

**Scope:**

| Issue | Size | What to do |
|-------|------|------------|
| C1 | S | Remove `import glob as glob_mod`; replace `glob_mod.glob()` with `Path.glob()`. Keep discovery `_g`. |
| C2 | S | `MODE_DEAL_COUNTS.get(MODE, 30)` + `warnings.warn()` on unknown MODE. |
| C3 | S | Add `SEED = 42` to parameters cell; wire to synthetic fallback RNG. |
| C5 | S | Expand synthetic fallback to 10 features (match 30_'s list). |
| C10 | S | Add per-contract ANOVA after S4.3 violin plot. Print F-stat + p-value. |
| C13 | S | Filter NaN before `sorted()` in S4.5: `valid_vars = {k: v for k,v in ... if not np.isnan(v)}`. |
| C15 | S | Add p-values to S6 correlation table via `scipy.stats.pearsonr()`. |
| C18 | S | Fix S7 companion links to correct notebook paths. |
| C19 | S | Add `scorecard = None` sentinel before S1; use `if scorecard is not None:` in S7. |
| C20 | M | Add min-N guard at start of S4: warn when any contract type < 30 deals. |
| C21 | S | Add inline comments labeling structural invariant vs empirical in S3. |
| C22 | M | Add run metadata summary cell after data loading. |
| C23-T1 | M | S4.3: split ANOVA by declaring/defending + bidder_team distribution. S4.4: print bidder_seat distribution per contract type. |
| C23-T2 | M | S5: declaring/defending overlay on top features. S6: split correlation heatmap by declaring/defending. |
| C31 | S | Add 1-2 line markdown description cells to title-only sections. |
| C59 | S | Audit all `plot_*` calls; strip `feat_` where API expects unprefixed. |

**Acceptance criteria:**
- S4.3 has ANOVA with F-stat and p-value, split by declaring/defending
- S4.5 doesn't crash on NaN variance
- S6 table shows p-values, split by declaring/defending
- S7 links point to correct notebook paths
- Min-N warning fires for SMOKE mode (< 30 deals)
- No `glob_mod` in notebook
- All `plot_*` calls use unprefixed feature names
- `make notebook-check` passes

---

### PR-2: 20_outcome_health — all fixes [L]

**Branch:** `feat/r0-nb-2-20-outcome-health`

**Issues:** C1, C20(S2/S6), C22, C23-T1(S3), C23-T2(S2), C24, C25, C26, C27, C28, C29, C30, C31, C59(audit/fix)

**Files:** `notebooks/arc_d/r0/20_outcome_health.{py,ipynb}` (exclusive)

**Scope:**

| Issue | Size | What to do |
|-------|------|------------|
| C1 | S | Remove `import glob as glob_mod`; use `Path.glob()`. |
| C20 | M | S2/S6: min-N guard when any contract type < 30 deals. |
| C22 | M | Add run metadata summary cell after data loading. |
| C23-T1 | M | S3: declaring/defending means split + bidder_team distribution alongside Mann-Whitney U. |
| C23-T2 | M | S2: declaring/defending overlay on outcome histograms. |
| C24 | S | Add seat balance analysis to S3 or rename section title. |
| C25 | M | Add second S4 chart: bid distribution stacked by trump suit (suit) and by type (high/low). |
| C26 | S | Add make rate definition in S5 markdown header. |
| C27 | M | Extract make rate by bid value as standalone chart with CI bands. |
| C28 | M | Facet overbid/underbid histogram by contract type. |
| C29 | M | Add summary table to S6: per contract type, tricks %, mean, median. |
| C30 | M | Add points analysis to S6: declaring/defending points table + CDF/CCDF + expected points by bid value. **Depends C32.** |
| C31 | S | Add 1-2 line markdown description cells to title-only sections. |
| C59 | S | Audit all `plot_*` calls; strip `feat_` where API expects unprefixed. |

**Acceptance criteria:**
- S3 has seat balance + declaring vs defending means
- S4 has trump-suit-stacked bid chart
- S5 defines make rate + has standalone make rate curve
- S5 overbid histogram shows separate panels per contract type
- S6 has summary table + points CDF + expected points curve
- All `plot_*` calls use unprefixed feature names
- `make notebook-check` passes

---

### PR-3: 30_feature_outcome_eval — all fixes [XL]

**Branch:** `feat/r0-nb-3-30-feature-outcome`

**Issues:** C2, C6, C12, C16, C22, C23-T2(S1), C31, C34, C35, C36, C37, C56, C59(audit/fix)

**Files:** `notebooks/arc_d/r0/30_feature_outcome_eval.{py,ipynb}` (exclusive)

**Scope:**

| Issue | Size | What to do |
|-------|------|------------|
| C2 | S | `MODE_DEAL_COUNTS.get(MODE, 30)` + `warnings.warn()` on unknown MODE. |
| C6 | M | Add fail-fast validation section after data loading with 4 assert-style checks (range, zero-sum, no-missing, feat count). Emulates 20_ S1 pattern. |
| C12 | M | Add balance/symmetry check section before model analysis (team balance by contract). |
| C16 | L | Fill S6 placeholder with 5 R0-specific analyses: Gaussian validation (Shapiro-Wilk + Q-Q), feature selection justification, residual structure, bid decision audit (5-10 traced deals), permutation importance (C56). |
| C22 | M | Add run metadata summary cell after data loading. |
| C23-T2 | M | S1: add features × `points_won` heatmap alongside existing `tricks_won` heatmap. Split by declaring/defending. |
| C31 | S | Add 1-2 line markdown description cells to title-only sections. |
| C34 | M | S2: replace coefficient heatmap with `sm.OLS().fit().summary()` tables per arm × contract. Keep coefficient comparison bar chart. |
| C35 | M | S3: facet diagnostic charts (scatter, residual, bootstrap) by contract type into separate panels. Keep pooled summary. |
| C36 | S | S4: add metric glossary markdown cell. Note metric sources (regression vs simulation). |
| C37 | M | S5: facet prediction distribution by contract type + overlay actual tricks_won. |
| C56 | M | S6: permutation feature importance — permute each feature, measure R² drop. Per-contract results. (Included in C16 scope.) |
| C59 | S | Audit all `plot_*` calls; strip `feat_` where API expects unprefixed. |

**Reference snippets:** See review doc → C34 (`statsmodels.OLS` pattern), C32 (`compute_points` for dual correlation).

**Acceptance criteria:**
- Fail-fast section with assert-style checks after data loading
- S1 has dual-target correlation heatmap (tricks + points), split by declaring/defending
- S2 has statsmodels summary tables (not heatmap) for each arm × contract
- S3 charts faceted by contract type (separate panels)
- S4 has metric glossary
- S5 prediction distributions faceted with actual overlay
- S6 has 5 non-placeholder analyses including permutation importance
- Balance check section exists before model analysis
- All `plot_*` calls use unprefixed feature names
- `make notebook-check` passes

---

### PR-4: 40_r0_baseline — all fixes except §2/§4 [XL]

**Branch:** `feat/r0-nb-4-40-baseline`

**Issues:** C1, C2, C11, C15, C22, C23-T1(§3), C23-T2(§5/§7.5), C34, C35, C36, C38, C41, C44, C45, C46, C47, C48, C51, C52, C53, C54, C55, C58, C59(audit/fix)

**Files:** `notebooks/arc_d/r0/40_r0_baseline.{py,ipynb}` (exclusive)

**Note:** §2 (bid distribution) and §4 (make rate) content remains in 40_ for now. PR-7 extracts them to 25_auction_health.

**Scope:**

| Issue | Size | What to do |
|-------|------|------------|
| C1 | S | Remove `import glob as glob_mod`; use `Path.glob()`. |
| C2 | S | `MODE_DEAL_COUNTS.get(MODE, 30)` + `warnings.warn()` on unknown MODE. |
| C11 | S | §3: add Mann-Whitney U p-value to team balance table per contract type. |
| C15 | S | §7.5: add p-values to correlation table via `scipy.stats.pearsonr()`. |
| C22 | M | Add run metadata summary cell after data loading. |
| C23-T1 | M | §3: declaring/defending split + stat test. |
| C23-T2 | M | §5: add defending team stats for contrast. §7.5: split feature-outcome correlations by declaring/defending. |
| C34 | M | §6: replace coefficient heatmap with `sm.OLS().fit().summary()` tables per arm × contract. Keep bar chart. |
| C35 | M | §7: facet pred vs actual + residual charts by contract type. |
| C36 | S | §8: add markdown glossary cell defining all metrics + note on metric sources. |
| C38 | S | §1: strip `feat_` prefix in `top5_by_var` before `plot_feature_distributions()`. §7.5: strip prefix for `plot_feature_outcome_correlation()`. |
| C41 | M | §3: `points_won` mean, median, distribution alongside `tricks_won`. **Depends C32.** |
| C44 | S | §5: add `plot_cdf(df, ..., group_by="team")` and `group_by="seat"`. |
| C45 | M | §5: add percentage table via `pd.crosstab(contract_type, tricks_won, normalize="index")`. |
| C46 | M | §5: `points_won` CDF + declaring stats. **Depends C32.** |
| C47 | S | §5: fix CDF scope mismatch — label as "all seats" or filter to declaring. |
| C48 | M | §11: extract all 6 metrics from comparator JSON; grouped-bar 2-panel chart + full comparison table. |
| C51 | M | §7: error analysis — top 10 worst mispredictions by \|residual\| per contract. |
| C52 | M | §8: contract selection comparison — model vs heuristic frequencies. |
| C53 | M | §10: declaring win rate by bid value (5-10) with fraction made + mean surplus. |
| C54 | M | §10: confusion matrix (bid × actual tricks) heatmap. |
| C55 | M | §3 or §5: points vs tricks scatter, color = contract_type. **Depends C32.** |
| C58 | S | §7.7: extend drift with rolling `net_eppd`. **Depends C32.** |
| C59 | S | Audit all `plot_*` calls; strip `feat_` where API expects unprefixed. |

**Acceptance criteria:**
- §3 has significance test + points_won stats + declaring/defending split
- §5 has team/seat CDFs + percentage table + corrected scope + points CDF
- §7 has per-contract faceted diagnostics + error analysis table
- §8 has contract selection comparison + metric glossary
- §10 has win rate by bid value + confusion matrix
- §11 has grouped-bar chart with all 6 metrics
- All `plot_*` calls use unprefixed feature names (C38 + C59)
- `make notebook-check` passes

---

### PR-5: 50_r0_matchups — all fixes [S]

**Branch:** `feat/r0-nb-5-50-matchups`

**Issues:** C1, C2, C7, C22, C31, C59(audit/fix)

**Files:** `notebooks/arc_d/r0/50_r0_matchups.{py,ipynb}` (exclusive)

**Scope:**

| Issue | Size | What to do |
|-------|------|------------|
| C1 | S | Remove `import glob as glob_mod`; use `Path.glob()`. |
| C2 | S | `MODE_DEAL_COUNTS.get(MODE, 30)` + `warnings.warn()` on unknown MODE. |
| C7 | M | Add fail-fast validation section after data loading with 4 assert-style checks. Emulates 20_ S1 pattern. |
| C22 | M | Add run metadata summary cell after data loading. |
| C31 | S | Add 1-2 line markdown description cells to title-only sections. |
| C59 | S | Audit all `plot_*` calls; strip `feat_` where API expects unprefixed. If no instances, note "C59: no prefix issues found." |

**Acceptance criteria:**
- Fail-fast section with assert-style checks after data loading
- Run metadata summary present
- Section descriptions present
- No `glob_mod` in notebook
- All `plot_*` calls use unprefixed feature names
- `make notebook-check` passes

---

### PR-6: C59 prefix-convention contract test [S]

**Branch:** `feat/r0-nb-6-prefix-test`

**Issues:** C59 (test enforcement)

**Files:** `tests/unit/test_notebook_template_contract.py` (new or extended)

**Depends:** PR-1 through PR-5 (validates fixes made in those PRs)

**Scope:**

Add a static contract test that greps all `.py` notebook files in `notebooks/arc_d/r0/` for known `feat_`-prefix → `plot_*` anti-patterns:
- `plot_feature_distributions(...features=[...feat_...])`
- `plot_feature_outcome_correlation(...features=[...feat_...])`
- `plot_feature_heatmap_by_suit(...features=[...feat_...])`

Any match = test failure with descriptive error message.

**Acceptance criteria:**
- Test passes after all notebook PRs are merged (no prefix anti-patterns remain)
- Test fails if a `feat_`-prefixed arg is reintroduced in any notebook
- `uv run python -m pytest tests/unit/test_notebook_template_contract.py -x -q` passes

**Phase 1 exit gate:**
```bash
make check-quiet
make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"
```

---

## Phase 2: New Content + Reports (After Phase 1)

### PR-7: 25_auction_health — new notebook + 40_ §2/§4 extraction [L]

**Branch:** `feat/r0-nb-7-25-auction-health`

**Issues:** C49, C39, C40, C42, C43

**Depends:** PR-4 (extracts content from 40_)

**Files:**
- `notebooks/arc_d/r0/25_auction_health.{py,ipynb}` — NEW
- `notebooks/arc_d/r0/40_r0_baseline.{py,ipynb}` — remove §2 + §4 content (replace with cross-ref)

**Scope:**

Create dedicated auction health notebook absorbing 40_ §2 + §4:
1. **S0** — Setup, CWD resolution, data loading (same pattern as other notebooks)
2. **S1** — Fail-fast validation
3. **S2** — Bid distribution by contract (existing from 40_ §2) + suit breakout (C40)
4. **S3** — Bidder/dealer seat distributions (C39) + bid height by dealer seat
5. **S4** — Make rate by bid value chart (C42) + surplus distribution
6. **S5** — Seat-faceted bid accuracy (C43)
7. **S6** — Auction length and pass rate analysis
8. **S7** — Summary

Remove §2 and §4 content from 40_, replace with markdown note: "See `25_auction_health.py` for auction analysis."

**Acceptance criteria:**
- `25_auction_health.py` exists with 8 sections
- 40_ §2 and §4 replaced with cross-reference
- Paired .ipynb created via Jupytext
- `make notebook-check` passes
- `uv run python -m pytest tests/unit/test_notebook_template_contract.py -x -q` passes

---

### PR-8: Formal reports [M]

**Branch:** `feat/r0-nb-8-formal-reports`

**Issues:** Formal report targets from meta-review

**Depends:** PR-1 through PR-7 (Phase 2 complete)

**Files:**
- `docs/04_reports/r0/r0_promotion_report.md` — NEW
- `docs/01_core/schemas/olsa_r0_model_spec.md` — NEW
- `docs/04_reports/r0/comparator_rankings.md` — NEW

**Scope:**

1. **R0 Promotion Report** — gate checks, eval metrics, attribution gap, promotion decision. Reference notebook outputs.
2. **Model Spec Document** — OLSa/HybridOLSa R0 frozen parameters: feature lists, per-contract weights, bias terms, sigma models, decision thresholds.
3. **Comparator Rankings** — all comparator bidders by `net_eppd` + 5 other metrics, with bootstrap CIs and statistical significance.

**Explicitly excluded:** H2H Matchup Report (blocked by deferred C50). See Deferred Items.

**Acceptance criteria:**
- Reports reference specific metric values from R0 eval
- Model spec matches frozen artifact contents
- Comparator rankings include all bidders with CIs
- `make docs-check` passes

**Phase 2 exit gate:**
```bash
make check-quiet
make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"
```

---

## Deferred Items

| ID | Item | Reason | Where Tracked |
|----|------|--------|---------------|
| C50 | H2H matchup battery + 50_ content | Requires experiment runner + 49 runs; infra doesn't exist | `plans/arc_d_execution_plan.md` Wave 3+ |
| C33 | OLSa vs Hybrid ablation | Requires new experiment runs | `plans/arc_d_execution_plan.md` Wave 3+ |
| C57 | Bid decision boundary viz | Lower priority; can be added post-merge | Future enhancement |
| H2H Report | H2H Matchup formal report | Blocked by C50 | `plans/arc_d_execution_plan.md` Wave 3+ |

---

## Issue-to-PR Trace Matrix

Every issue maps to exactly one owner PR per notebook (or is explicitly deferred). Cross-notebook issues are listed once per notebook they affect.

| Issue | PR | Notebook/File | Notes |
|-------|----|---------------|-------|
| C1 | PR-1 | 10_ | Remove glob_mod |
| C1 | PR-2 | 20_ | Remove glob_mod |
| C1 | PR-4 | 40_ | Remove glob_mod |
| C1 | PR-5 | 50_ | Remove glob_mod |
| C2 | PR-1 | 10_ | MODE fallback |
| C2 | PR-3 | 30_ | MODE fallback |
| C2 | PR-4 | 40_ | MODE fallback |
| C2 | PR-5 | 50_ | MODE fallback |
| C3 | PR-1 | 10_ | SEED parameter |
| C5 | PR-1 | 10_ | Synthetic expansion |
| C6 | PR-3 | 30_ | Fail-fast validation |
| C7 | PR-5 | 50_ | Fail-fast validation |
| C8 | — | — | Leave as-is (Low, decided) |
| C9 | — | — | Info, no action |
| C10 | PR-1 | 10_ | Per-contract ANOVA |
| C11 | PR-4 | 40_ | Mann-Whitney U |
| C12 | PR-3 | 30_ | Balance/symmetry check |
| C13 | PR-1 | 10_ | NaN-safe sort |
| C14 | — | — | Low, acknowledged overlap |
| C15 | PR-1 | 10_ S6 | Correlation p-values |
| C15 | PR-4 | 40_ §7.5 | Correlation p-values |
| C16 | PR-3 | 30_ S6 | Rung-specific analyses (includes C56) |
| C17 | — | — | Info, no action |
| C18 | PR-1 | 10_ | Fix companion links |
| C19 | PR-1 | 10_ | Scorecard sentinel |
| C20 | PR-1 | 10_ S4 | Min-N guard |
| C20 | PR-2 | 20_ S2/S6 | Min-N guard |
| C21 | PR-1 | 10_ | Inline comments (structural vs empirical) |
| C22 | PR-1 | 10_ | Run metadata summary |
| C22 | PR-2 | 20_ | Run metadata summary |
| C22 | PR-3 | 30_ | Run metadata summary |
| C22 | PR-4 | 40_ | Run metadata summary |
| C22 | PR-5 | 50_ | Run metadata summary |
| C23-T1 | PR-1 | 10_ S4.3/S4.4 | Declaring/defending + bidder distribution |
| C23-T1 | PR-2 | 20_ S3 | Declaring/defending means + stat test |
| C23-T1 | PR-4 | 40_ §3 | Declaring/defending split + stat test |
| C23-T2 | PR-1 | 10_ S5/S6 | Declaring/defending overlay + split heatmap |
| C23-T2 | PR-2 | 20_ S2 | Declaring/defending overlay on histograms |
| C23-T2 | PR-3 | 30_ S1 | Split heatmap by declaring/defending |
| C23-T2 | PR-4 | 40_ §5/§7.5 | Defending stats + split correlations |
| C24 | PR-2 | 20_ | Seat balance in S3 |
| C25 | PR-2 | 20_ | Bid distribution by trump suit |
| C26 | PR-2 | 20_ | Make rate definition |
| C27 | PR-2 | 20_ | Make rate standalone chart |
| C28 | PR-2 | 20_ | Overbid histogram by contract type |
| C29 | PR-2 | 20_ | Tricks summary table |
| C30 | PR-2 | 20_ | Points analysis (depends C32) |
| C31 | PR-1 | 10_ | Section descriptions |
| C31 | PR-2 | 20_ | Section descriptions |
| C31 | PR-3 | 30_ | Section descriptions |
| C31 | PR-5 | 50_ | Section descriptions |
| C32 | PR-0 | eval_dataset.py | `points_won` infra (**critical path**) |
| C33 | **DEFERRED** | — | OLSa vs Hybrid ablation |
| C34 | PR-3 | 30_ S2 | OLS summary tables |
| C34 | PR-4 | 40_ §6 | OLS summary tables |
| C35 | PR-3 | 30_ S3 | Contract-faceted diagnostics |
| C35 | PR-4 | 40_ §7 | Contract-faceted diagnostics |
| C36 | PR-3 | 30_ S4 | Metric glossary |
| C36 | PR-4 | 40_ §8 | Metric glossary |
| C37 | PR-3 | 30_ S5 | Faceted prediction distributions |
| C38 | PR-4 | 40_ §1/§7.5 | Prefix strip (known instances) |
| C39 | PR-7 | 25_ S3 | Bidder/dealer seat distributions |
| C40 | PR-7 | 25_ S2 | Suit breakout |
| C41 | PR-4 | 40_ §3 | Points_won stats (depends C32) |
| C42 | PR-7 | 25_ S4 | Make rate by bid value |
| C43 | PR-7 | 25_ S5 | Seat-faceted bid accuracy |
| C44 | PR-4 | 40_ §5 | Team/seat CDFs |
| C45 | PR-4 | 40_ §5 | Percentage table |
| C46 | PR-4 | 40_ §5 | Points CDF (depends C32) |
| C47 | PR-4 | 40_ §5 | CDF scope fix |
| C48 | PR-4 | 40_ §11 | Full comparator metrics |
| C49 | PR-7 | 25_ | New auction health notebook |
| C50 | **DEFERRED** | 50_ | H2H matchup battery |
| C51 | PR-4 | 40_ §7 | Error analysis |
| C52 | PR-4 | 40_ §8 | Contract selection comparison |
| C53 | PR-4 | 40_ §10 | Win rate by bid value |
| C54 | PR-4 | 40_ §10 | Confusion matrix |
| C55 | PR-4 | 40_ §3/§5 | Points vs tricks scatter (depends C32) |
| C56 | PR-3 | 30_ S6 | Permutation importance (in C16 scope) |
| C57 | **DEFERRED** | — | Bid decision boundary viz |
| C58 | PR-4 | 40_ §7.7 | Rolling net_eppd drift (depends C32) |
| C59 | PR-1 | 10_ | Prefix audit/fix |
| C59 | PR-2 | 20_ | Prefix audit/fix |
| C59 | PR-3 | 30_ | Prefix audit/fix |
| C59 | PR-4 | 40_ | Prefix audit/fix |
| C59 | PR-5 | 50_ | Prefix audit/fix |
| C59 | PR-6 | test | Prefix convention contract test |

**Coverage:** All 58 issues accounted for. 3 explicitly deferred (C33, C50, C57). 3 no-action (C8 Low, C9 Info, C14 Low, C17 Info — 4 total).

---

## Phase Exit Gates

`make check-quiet` already runs `check` which includes `repo-lint + lint + test + notebook-check + docs-check` (Makefile L59). No separate `docs-check` needed.

```
Phase 0: uv run python -m pytest tests/unit/test_eval_dataset.py -x -q
         make check-quiet
         make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"

Phase 1: make check-quiet
         make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"

Phase 2: make check-quiet
         make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"
```

---

## Agent Handoff Guide

### For any PR in this plan:

1. **Read the PR specification** above for scope and files.
2. **Read the issue descriptions** in `plans/r0_10_feature_health_review.md` for detailed context.
3. **Check reference snippets** in the review doc's "Reference Snippets" section for tricky patterns.
4. **Check dependencies** — if the PR depends on PR-0, verify C32 has merged.
5. **Work in a worktree** — `git worktree add ../Bid-Euchre-<branch> -b <branch-name>`
6. **Tier 1 testing** during implementation: `uv run python -m pytest tests/unit/test_<relevant>.py`
7. **Tier 2 testing** before PR: `make check-quiet`
8. **Jupytext sync** after notebook changes: `make notebook-sync`
9. **nbstripout** before committing: `uv run python -m nbstripout notebooks/arc_d/r0/<notebook>.ipynb`

### Common footguns:

| Footgun | Mitigation |
|---------|------------|
| Double-prefix bug | Always strip `feat_` before passing to `plot_*` functions. See C38 snippet in review doc. |
| `0.0` is falsy | Never use `x = x or fallback` for numeric metrics. Use `if x is None:`. |
| NaN in sorted() | Filter NaN before any `sorted(key=...)` call. |
| `f_oneway` with 1 group | Guard with `len(groups) >= 2`. |
| Notebook sync | Run `make notebook-sync` after editing .py files. Commit .py AND .ipynb. |
| Circular imports | Don't re-export `reporting.charts` in `reporting.__init__`. Import directly. |
| Stale branch | Always `git rebase origin/main` before opening PR. |
| Worktree pre-commit | Run `uv sync --all-extras && uv pip install pre-commit` in fresh worktrees. |
| PATH for commits | Use `PATH=".venv/bin:$PATH" git commit ...` in worktrees. |
| `points_won` never None | Use `compute_points()` — no-bid case returns tricks. Don't guard with `if points_won is not None`. |
| Report output path | `docs/04_reports/r0/` — not `docs/04_reports/arc_d/`. |

### PR naming convention:

```
feat/r0-nb-0-points-infra
feat/r0-nb-1-10-feature-health
feat/r0-nb-2-20-outcome-health
feat/r0-nb-3-30-feature-outcome
feat/r0-nb-4-40-baseline
feat/r0-nb-5-50-matchups
feat/r0-nb-6-prefix-test
feat/r0-nb-7-25-auction-health
feat/r0-nb-8-formal-reports
```

### Per-PR scope quick reference:

| PR | What changes | ~Lines changed | Key reference |
|----|-------------|----------------|---------------|
| PR-0 | `eval_dataset.py` + tests + Makefile + runner | ~80 | `scoring.py` L10-50 |
| PR-1 | 10_ notebook (16 issues) | ~200 | Review doc C1-C31 |
| PR-2 | 20_ notebook (14 issues) | ~250 | Review doc C24-C30 |
| PR-3 | 30_ notebook (13 issues) | ~350 | Review doc C34-C37, C16 |
| PR-4 | 40_ notebook (23 issues) | ~400 | Review doc C38-C58 |
| PR-5 | 50_ notebook (6 issues) | ~60 | Review doc C7 |
| PR-6 | Contract test | ~40 | C59 anti-patterns |
| PR-7 | 25_ new + 40_ extraction | ~250 | Review doc C49/C39-C43 |
| PR-8 | 3 markdown reports | ~150 | R0 eval metrics |

### Verification after all PRs merge:

```bash
# Full validation
make check-quiet

# Notebook execution (not in make check — run manually)
make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"  # SMOKE mode

# Visual spot check
# Open each .ipynb in Jupyter, verify charts render and no "No numeric features" errors
```
