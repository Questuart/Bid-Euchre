# Review Log: R0 Notebooks

> Scope: All 5 notebooks in `notebooks/arc_d/r0/`
> Reviewed: 2026-02-24
> Status: REVIEW COMPLETE — all 5 notebooks reviewed.
> Execution plan: [`plans/r0_notebook_execution_plan.md`](r0_notebook_execution_plan.md)
> Total issues: **58** (1 High, 43 Medium, 11 Low, 3 Info; C32 = Critical Path)

---

## Cross-Notebook Issue Inventory

### By Severity

**High (1):**

| ID | Scope | Description |
|----|-------|-------------|
| C6 | 30_feat_outcome | No fail-fast validation at all — model evaluation proceeds without data health check. **Only High severity issue.** |

**Medium (43):**

| ID | Scope | Description |
|----|-------|-------------|
| C1 | 10_, 20_, 40_, 50_ | Dual glob import (`_g` in discovery cell + `glob_mod` in imports) |
| C2 | 10_, 30_, 40_, 50_ | `MODE_DEAL_COUNTS.get(MODE)` has no fallback — MODE typo → `None` max_deals. Only 20_ has `get(MODE, 30)` |
| C7 | 50_matchups | No fail-fast validation |
| C10 | 10_ S4.3 | Team violin plot is visual-only — no statistical test (violates `05_rigor.md`) |
| C11 | 40_ §3 | Team balance is means-only table — no significance test |
| C13 | 10_ S4.5 | NaN-unsafe sort: `sorted(seat_mean_vars, key=seat_mean_vars.get)` — undefined with NaN |
| C18 | 10_ S7 | Companion notebook links wrong: `20_matchup_analysis.py` doesn't exist → `50_r0_matchups.py` |
| C20 | 10_ S4, potentially all | No minimum-N guard on sub-group analysis — QUICK mode produces thin strata where charts look meaningful but are noise |
| C22 | all 5 notebooks | No run metadata summary after data loading — reviewer doesn't know what run is being evaluated (bidder, seed, deal count, date, simulation type [self-play/matchup/bidless], purpose) |
| C23 | all 5 notebooks | No declaring vs defending segmentation — contract_type filtering introduces selection bias (bidder chose contract based on hand strength). Team/seat symmetry tests are confounded without this split. |
| C25 | 20_ S4 | Bid distribution chart pools all contract types — need suit (stacked by suit) and high/low (stacked by type) breakout |
| C26 | 20_ S5 | Make rate definition not stated — reviewer needs formal definition |
| C27 | 20_ S5 | Make rate by bid value chart embedded in composite — should be standalone for visibility |
| C28 | 20_ S5 | Overbid/underbid is pooled — should facet by contract type |
| C29 | 20_ S6 | No summary table — should include tricks % and points by contract type |
| C30 | 20_ S6, potentially 40_ | No points analysis — tricks_won misses asymmetric scoring risk (declaring: tricks if made, -bid if set). **Depends on C32** (needs `points_won` column). |
| C31 | 10_, 20_, 30_, 50_ (not 40_) | Most sections lack markdown description cells — title only, no explainer of what the section does and what the expected outcome is. 40_ is the reference pattern (1-2 line descriptions on every section). |
| C32 | 20_, 30_, 40_, 50_ | **CRITICAL PATH.** No `points_won` column in eval dataset — `_expand_record()` only computes `tricks_won`. Points analysis requires per-seat scoring via `compute_points()`. Tricks is the OLSa prediction target; net_eppd (points-based) is the optimization goal. Both correlation targets needed. **Blocks C30, C41, C46, 30_ S1 dual correlation.** |
| C34 | 30_ S2, 40_ §6 | Coefficient heatmap is low signal for sparse models — replace with `statsmodels.OLS` summary tables (Stata-style: coefs, std errors, t-stats, p-values, CIs, R², F-stat). `statsmodels` already a dependency. Apply to all model spec sections. |
| C35 | 30_ S3, 40_ §7 | Model diagnostic charts pool contract types — suit vs high/low have fundamentally different residual patterns and prediction ranges. Facet all charts (scatter, residuals, bootstrap) into separate panels per contract type. |
| C36 | 30_ S4, 40_ §8 | No metric definitions in dual-arm comparison — net_eppd, eppd, cvar_5, etc. used without glossary. Two metric sources (regression fit vs simulation eval) mixed without explanation. |
| C37 | 30_ S5 | Prediction distribution pools contract types and lacks actual distribution overlay. Facet by suit vs high/low; overlay actual tricks_won to validate model spread and Gaussian assumption. |
| C38 | 40_ §1, §7.5 | Double-prefix bug in diagnostics chart calls — passes `feat_*` names but API expects unprefixed. Affects `plot_feature_distributions()` in §1 ("No numeric features to plot") and `plot_feature_outcome_correlation()` in §7.5 ("Insufficient data" or "No numeric features found"). Template (10_) has the fix: strip prefix first. |
| C39 | 40_ §2 | Auction summary not faceted by seat — missing bidder seat distribution, dealer seat distribution, bid height by dealer seat. Rotation anomalies invisible. |
| C40 | 40_ §2 | Contract selection lacks suit breakout — "suit" is single bucket, no trump suit frequency shown. Can't verify no suit bias in bidder behavior. |
| C41 | 40_ §3 | No points_won analysis — only tricks_won. Points capture asymmetric scoring (declaring: tricks if made, -bid if set). Need mean, median, distribution. **Depends on C32.** |
| C42 | 40_ §4 | Bid accuracy and make rate are text-only — no charts. Need make rate by bid value chart and surplus distribution histogram per contract type. |
| C43 | 40_ §4 | Auction outcomes not faceted by seat — can't verify bidder symmetry across seat positions in self-play. |
| C44 | 40_ §5 | CDF/CCDF not faceted by team or seat — misses free symmetry validation in self-play. |
| C45 | 40_ §5 | No percentage table of tricks won at each increment — reviewer needs exact values alongside CDF chart. |
| C46 | 40_ §5 | No points_won in gameplay outcomes — declaring team stats and CDF/CCDF are tricks-only. **Depends on C32.** |
| C48 | 40_ §11 | Comparator battery only shows net_eppd — 5 other metrics (eppd, bid_rate, make_rate, cvar_5, net_cvar_5) discarded. Need grouped-bar metric comparison like dual-arm chart. |
| C49 | 40_ §2, §4 → new 25_ | Promote auction analysis to dedicated `25_auction_health.py` notebook. Absorbs §2 + §4 + fixes C39/C40/C42/C43 + new auction analyses. |
| C50 | 50_ | H2H matchup battery: net_eppd heatmap, win rate matrix, seat rotation validation, dominance ordering, bootstrap CIs, auction competition analysis. Requires new H2H experiment runner (TODO in arc_d_execution_plan.md). |
| C51 | 40_ | Error analysis: top 10 biggest mispredictions by |residual|, faceted by contract type. What hands does the model fail on? |
| C52 | 40_ | Contract selection analysis: model's suit/high/low selection frequency vs heuristic bidders from comparator battery. |
| C53 | 40_ | Declaring team win rate by bid value: for each bid level (5-10), fraction made + mean points surplus/deficit. Risk-reward by bid level. |
| C54 | 40_ §10 or 25_ | Confusion matrix: bid level × actual tricks won — shows bid accuracy pattern (underbid cluster vs set cluster vs efficient bids). |
| C55 | 40_ §3 or §5 | Points vs tricks scatter — reveals asymmetric scoring risk (set penalty creates cluster below diagonal). **Depends on C32.** |
| C56 | 30_ S6 | Permutation feature importance — permute each feature, measure R² drop. True importance vs coefficient magnitude. |
| C57 | 30_ S6 or 40_ | Bid decision boundary visualization — for each contract, feature value ranges where model bids vs passes. |
| C58 | 40_ §7.7 | Rolling net_eppd drift — extend drift detection with sliding-window net_eppd (not just hand_value). |
| C59 | all 5 notebooks | Prefix-convention sweep — audit all `plot_*` calls passing `feat_*` names; strip prefix where API expects unprefixed. Cross-cutting companion to C38. |
| C16 | 30_ S6 | Rung-specific analysis is empty placeholder — fill with 4 R0-specific analyses: Gaussian assumption validation, feature selection justification, residual structure analysis, bid decision audit. (Promoted from Low.) |

**Low (11):**

| ID | Scope | Description |
|----|-------|-------------|
| C3 | 10_ | Missing `SEED` parameter (only notebook without one) |
| C5 | 10_ | Synthetic fallback only creates 3 features (real data has 39) — CI coverage gap |
| C8 | 10_ | S1 (health scorecard) + S2 (dataset integrity) partially redundant |
| C12 | 30_ | No balance/symmetry checks — model eval without verifying data symmetry |
| C14 | 10_ + 30_ | Feature-outcome correlation sections overlap (10_ S6 ≈ 30_ S1) |
| C15 | 10_ + 40_ | Feature-outcome correlations lack p-values (30_ S1 has them) |
| C19 | 10_ S7 | `"scorecard" in dir()` is fragile — should use sentinel variable |
| C21 | 10_ S3 | Seat/team distribution checks are structural tautologies (`_expand_record` guarantees 4 rows/deal) — should annotate |
| C24 | 20_ S3 | Section title says "& Seat Balance" but only tests team balance — missing or rename |
| C33 | 40_ §11, comparator | No OLSaBidder vs HybridOLSaBidder ablation — can't prove decision-layer value. TODO added to arc_d_execution_plan.md (Wave 3+). |
| C47 | 40_ §5 | CDF/CCDF use full `df` but section says "declaring team" — scope mismatch between stats (declaring-only) and charts (all rows). |

**Info (3):**

| ID | Scope | Description |
|----|-------|-------------|
| C4 | 40_, 50_ | Param name `EVAL_RUN_DIR` / `MATCHUP_RUN_DIR` differs from `EVAL_LOG_PATH` — intentional per notebook scope |
| C9 | 10_, 30_, 40_, 50_ | Soft `if not df.empty` guards instead of assert-style fail-fast (only 20_ uses `assert`) |
| C17 | 30_ + 40_ | Model analysis sections overlap (model specs, dual-arm, performance) — 40_ is the R0 instantiation |

### By Concept Area

**S0 Configuration & Data Loading:**
- C1 (Med): Dual glob — 4/5 notebooks
- C2 (Med): MODE fallback missing — 4/5 notebooks
- C3 (Low): 10_ missing SEED param
- C4 (Info): Param naming intentional
- C5 (Low): 10_ synthetic only 3 features
- C22 (Med): No run metadata summary — reviewer doesn't know what run they're evaluating (bidder, seed, deal count, date, purpose). All 5 notebooks.

**Fail-Fast Validation:**
- C6 (High): 30_ has none
- C7 (Med): 50_ has none
- C8 (Low): 10_ S1/S2 redundancy
- C9 (Info): Most notebooks use soft guards, not asserts

**Symmetry & Balance:**
- C10 (Med): 10_ S4.3 team visual-only
- C11 (Med): 40_ §3 team means-only
- C12 (Low): 30_ no balance checks
- C13 (Med): 10_ S4.5 NaN-unsafe sort
- C20 (Med): No min-N guard on sub-group analysis (QUICK thin strata)
- C21 (Low): 10_ S3 seat/team checks are structural tautologies — annotate
- C23 (Med): No declaring vs defending segmentation — cross-notebook confound in symmetry/feature/outcome analysis
- C24 (Low): 20_ S3 title says "& Seat Balance" — only has team balance

**Feature Analysis:**
- C14 (Low): 10_ S6 ≈ 30_ S1 overlap
- C15 (Low): 10_ + 40_ missing p-values
- C38 (Med): 40_ §1 `plot_feature_distributions()` double-prefix bug — renders "No numeric features to plot"
- C59 (Med): Prefix-convention sweep — audit all `plot_*` calls in all notebooks (companion to C38)

**Auction & Bidder Analysis:**
- C25 (Med): 20_ S4 bid distribution needs suit/high-low breakout
- C26 (Med): 20_ S5 make rate definition missing
- C27 (Med): 20_ S5 make rate by bid value chart needs standalone extraction
- C28 (Med): 20_ S5 overbid/underbid needs contract type faceting
- C39 (Med): 40_ §2 auction summary not seat-faceted (bidder seat, dealer seat distributions)
- C40 (Med): 40_ §2 contract selection no suit breakout
- C42 (Med): 40_ §4 bid accuracy / make rate text-only — needs charts
- C43 (Med): 40_ §4 auction outcomes not seat-faceted
- C49 (Med): Promote 40_ §2 + §4 → new `25_auction_health.py` notebook

**Outcome & Points:**
- C29 (Med): 20_ S6 no summary table (tricks % + points by contract)
- C30 (Med): 20_ S6 no points analysis — asymmetric scoring risk invisible in tricks-only view. Depends on C32.
- C32 (Med): No `points_won` in eval dataset — `_expand_record()` needs `compute_points()` call. Infrastructure for C30, 30_ S1 dual correlation, 40_ points analysis.
- C41 (Med): 40_ §3 no points_won analysis — only tricks_won shown, misses asymmetric scoring. Depends on C32.
- C44 (Med): 40_ §5 CDF not team/seat faceted — misses symmetry check
- C45 (Med): 40_ §5 no percentage table at each tricks increment
- C46 (Med): 40_ §5 no points_won CDF/stats. Depends on C32.
- C47 (Low): 40_ §5 CDF scope mismatch (all rows vs declaring-only stats)

**Model-Specific:**
- C16 (Med): 30_ S6 empty placeholder → fill with 4 R0-specific analyses (promoted from Low)
- C17 (Info): 30_ + 40_ model section overlap
- C33 (Low): No OLSaBidder vs HybridOLSaBidder ablation — TODO in arc_d_execution_plan.md for Wave 3+
- C48 (Med): 40_ §11 comparator battery uses only net_eppd — needs full 6-metric grouped-bar comparison
- C50 (Med): 50_ H2H matchup battery — heatmap, win rate matrix, dominance analysis, bootstrap CIs
- C51 (Med): 40_ error analysis — top mispredictions by |residual|
- C52 (Med): 40_ contract selection analysis — model vs heuristic comparison
- C53 (Med): 40_ declaring win rate by bid value — risk-reward chart
- C54 (Med): Confusion matrix bid × actual tricks — bid accuracy pattern
- C55 (Med): Points vs tricks scatter — asymmetric scoring risk (depends C32)
- C34 (Med): Coefficient heatmap → statsmodels summary tables (Stata-style output). All model spec sections.
- C35 (Med): Model diagnostic charts pooled — facet by contract type (suit vs high/low). All model perf sections.
- C36 (Med): No metric definitions in dual-arm comparison — add glossary + distinguish regression vs simulation metric sources.
- C37 (Med): Calibration prediction distribution pooled + no actual overlay. Facet + overlay actual tricks_won.
- C56 (Med): Permutation feature importance — permute + measure R² drop (30_ S6)
- C57 (Med): Bid decision boundary — feature ranges where model bids vs passes (30_ S6 or 40_)
- C58 (Med): Rolling net_eppd drift — extend 40_ §7.7 with sliding-window net_eppd

**Documentation & Descriptions:**
- C31 (Med): Section description cells missing — most sections title-only, need 1-2 line explainer (40_ is reference pattern)

**Summary Sections:**
- C18 (Med): 10_ wrong companion links
- C19 (Low): 10_ fragile `dir()` check

### C23 Detail: Declaring vs Defending Segmentation

> `is_declaring_team` column is available in every eval DataFrame (from `_expand_record()`).
> **Root cause:** `contract_type` is endogenous — determined by the bidder's decision based on hand strength. Any analysis that filters by contract_type and compares teams/seats is confounded by which team declared.

**Tier 1 — Confound Removal (essential, tests are misleading without it):**

| Notebook | Section | What to Add |
|----------|---------|-------------|
| 10_ | S4.3 Team Balance | Split ANOVA by declaring/defending. Print bidder_team distribution per contract type. |
| 10_ | S4.4 Seat Balance | Print bidder_seat distribution per contract type. Note bidder seat has systematically higher hand_value. |
| 20_ | S3 Team & Seat Balance | Show declaring vs defending means separately alongside existing Mann-Whitney U. |
| 40_ | §3 Gameplay Health | Add declaring/defending split + stat test (also fixes C11). |

**Tier 2 — Analytical Insight (highly valuable, different story for each role):**

| Notebook | Section | What to Add |
|----------|---------|-------------|
| 10_ | S6 Feature-Label Correlations | Split heatmap: declaring rows vs defending rows. Correlation structure differs fundamentally by role. |
| 10_ | S5 Feature Distributions | Overlay or side-by-side declaring vs defending for top features. Declaring hands have higher hand_value (selection effect). |
| 20_ | S2 Outcome Distributions | Overlaid declaring vs defending histograms. Declaring team wins more tricks on average. |
| 30_ | S1 Feature-Outcome Correlations | Split correlation heatmap by declaring/defending (same pattern as 10_ S6). Also add dual target: features × `tricks_won` + features × `points_won` (C32). Divergences reveal overbidding exposure. |
| 40_ | §5 Gameplay Outcomes | Already filters to `is_declaring_team` — add defending team for contrast. |
| 40_ | §7.5 Feature-Outcome Correlations | Split by declaring/defending. |

**Tier 3 — Nice-to-Have (informative but not critical):**

| Notebook | Section | What to Add |
|----------|---------|-------------|
| 10_ | S4.5 Feature-Level Symmetry | Could split by declaring/defending — but seat-level, less direct. |
| 50_ | §3 Self-Play Fairness | Self-play = same bidder both sides — split is symmetric by design, less meaningful. |
| 50_ | §5 Per-Opponent Analysis | Declaring vs defending performance per opponent. |
| 50_ | §6 Performance by Contract | Declaring win rate vs defending win rate. |

**Not applicable:** 10_ S1-S3 (structural checks), 10_ S4.2 (tests deal generator, not bidder), 20_ S4 (already bidder-specific), 30_ S2-S5 (model evaluation — separate design choice).

---

## Per-Notebook Detail: 10_feature_health.py

> Notebook: `notebooks/arc_d/r0/10_feature_health.py` (782 lines, 8 sections)
> Status: DISCUSSION IN PROGRESS

### S0 Configuration & Data Loading (L35–158)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C1 | Med | Dual glob import (`_g` at L66, `glob_mod` at L72) | **FIX** |
| C2 | Med | `MODE_DEAL_COUNTS.get(MODE)` no fallback (L96) | **FIX** |
| C3 | Low | Missing `SEED` parameter — only notebook without one | **FIX** |
| C5 | Low | Synthetic fallback only 3 features vs 39 real | **FIX** |

**Notes:**
- CWD resolution cell (PR #426 pattern) present and correct
- Discovery cell present and correct
- Unresolved-path warning at L118–121 is good UX
- `build_eval_dataset()` sets `hand_id = deal_id`, satisfying downstream checks
- L105 uses `glob_mod.glob(str(...))` — could use `Path.glob()` instead (30_ pattern)

**Decided S0 fixes:**

Definite (all agreed):
1. Add `SEED = 42` to parameters cell
2. Add MODE fallback with warning: `get(MODE)` → warn + default to 30 on unknown MODE
3. Replace `glob_mod.glob(str(eval_path / "logs" / "*.jsonl"))` with `Path.glob()` at L105
4. Remove `import glob as glob_mod` from L72 (dead after #3)
5. Wire SEED to synthetic: `rng = np.random.default_rng(SEED)` at L125 (currently hardcoded 42)

Optional (included):
6. Expand synthetic to 10 features (match 30_'s list: hand_value, trump_count, bowers, aces, voids, singletons, long_suit_length, short_suit_count, offsuit_aces, offsuit_non_ace_count)
7. Add `*.jsonl` fallback for flat directories (30_ pattern: try `logs/*.jsonl` first, then `*.jsonl`)

Cross-notebook (C22):
8. Add run metadata summary cell after data loading — print a brief table of run identity: bidder name, seed, total deals loaded, date, contract type breakdown, run directory path. Source from a dictionary in the notebook or parsed from the JSONL filename/records. Helps reviewer immediately understand what run they're evaluating.

### S1 Health Scorecard (L160–203)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | Info | `hands_differ` check always WARNs on eval data | NOTED |

**What it does:** Runs `compute_health_scorecard(df)` from `diagnostics/health_checks.py` — a 6-check suite — then renders a stacked PASS/WARN/FAIL bar chart.

**The 6 checks:**

| Check | What it validates |
|-------|-------------------|
| `row_uniqueness` | `(hand_id, seat)` pairs are unique |
| `seats_per_hand` | Every `hand_id` has exactly 4 seats |
| `feature_nans` | No NaN/Inf in `feat_*` columns |
| `feature_variance` | No constant (zero-variance) features |
| `seat_balance` | `feat_hand_value` means within 5% of global mean per seat |
| `hands_differ` | `hand_cards` differ across seats within each hand |

**Why `hands_differ` always WARNs on eval data:**
`build_eval_dataset()` produces `feat_*` columns and auction metadata but does NOT include a `hand_cards` column (raw card lists). The `hands_differ` check requires `hand_cards` to compare across seats. When the column is missing, it returns WARN with message "Missing hand_cards or hand_id column." This is honest behavior (SKIP-like), not a false positive — the check was designed for the older bidless dataset format which included raw card data. No fix needed.

**No fixes needed for S1.** Clean delegation to production library, bar chart is a good visual summary, `scorecard` variable persists for reuse in S7.

### S2 Dataset Integrity (L206–285)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C8 | Low | Partial redundancy with S1 | LEAVE AS-IS |

**What it does:** Four manual integrity checks, printed as a table:

| Check | What it validates | Overlaps S1? |
|-------|-------------------|:------------:|
| 4 rows per deal | Groups by `deal_id`, flags any with ≠ 4 rows | yes (`seats_per_hand`) |
| feat_* columns present | Counts `feat_*` columns, WARN if 0 | **no** (unique to S2) |
| NaN audit | Counts NaNs per feature column | yes (`feature_nans`) |
| No duplicate (deal_id, seat) | Checks for duplicate pairs | yes (`row_uniqueness`) |

**Decision: Leave as-is (option A).** The redundancy is harmless — S2 provides more granular per-check detail than S1's summary scorecard, which is useful when debugging specific data issues. The notebook is meant for human review, not automation. S2's unique contribution is the feat_* presence check. `feat_cols` is redefined here and in S4.5, S5, S6 (local cell scope, not harmful).

### S3 Strata Completeness (L287–363)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C21 | Low | Seat/team distribution checks are structural tautologies — `_expand_record()` always produces exactly 4 rows (1 per seat, 2 per team). Should annotate which checks are structural invariants vs empirical properties. | **FIX** |

**What it does:** Validates that the dataset covers all expected strata and visualizes the distribution as a stacked bar chart.

| Check | What it validates | Type |
|-------|-------------------|------|
| Contract type distribution | Unique deals per contract type (suit/high/low) | Empirical (depends on bidder behavior) |
| Trump suit distribution | Deals per trump suit (C/D/H/S) — suit contracts only | Empirical (depends on deal generator) |
| Seat distribution | Row counts per seat (should be equal across 4 seats) | **Structural invariant** (guaranteed by `_expand_record`) |
| Team distribution | Row counts per team (should be equal across 2 teams) | **Structural invariant** (guaranteed by `_expand_record`) |
| Stacked bar chart | Deal-level contract_type × trump visualization | Empirical |

**Key implementation details:**
- Deal-level dedup via `drop_duplicates(subset=["deal_id"])` — correct (avoids 4× inflation from per-seat rows)
- `fillna('__NONE__')` sentinel for no-trump contracts — matches MEMORY.md NaN trump merge pattern
- No statistical uniformity test (intentional — strata completeness = "are all buckets populated", balance testing is in S4)
- Seat/team checks are tautological by construction but serve as regression guards on the data pipeline

**Decided S3 fix:**
1. Add inline comments labelling each check as structural invariant or empirical property (e.g., `# Structural invariant: _expand_record() guarantees 4 rows per deal`)

### S4 Symmetry Analysis (L365–571)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C20 | **Med** | No minimum-N guard on sub-group analysis — QUICK mode can produce thin strata (e.g. 14 deals / 56 rows for high/low) where boxplots look meaningful but are noise. S3 reports deal-level N, S4 reports row-level N, creating confusion. | **FIX** |

**Decided S4 cross-cutting fix:**
1. Add per-strata minimum-N check at start of S4 (or as a helper used by each sub-section). When any contract type has fewer than ~30 deals, print a warning. This applies to S4.1, S4.2, S4.3, and S4.4.

**S4.1 By Contract Type (L371–387):**

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No issues (affected by C20 min-N guard) | OK |

**What it does:** Box plot of `feat_hand_value` grouped by contract type via `plot_hand_value_by_contract(df)`, plus `.describe()` summary stats table per contract type.

**Key details:** Chart function at `diagnostics/charts.py:122` uses `df["contract_type"].unique()` — data-driven, only shows present types. Visual + descriptive stats but no statistical test. This is appropriate — the question "do hand values differ by contract type?" has an expected *yes* answer (suit vs no-trump are fundamentally different). The purpose is shape inspection, not null hypothesis testing.

**Decision: No code changes.** Affected by C20 min-N guard.

**S4.2 By Trump Suit (L389–448):**

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No issues | OK |

**What it does:** Tests whether `feat_hand_value` is balanced across the 4 trump suits (suit contracts only). ANOVA test + boxplot.

**Key details:** Filters to `trump.notna()` (suit contracts only). ANOVA with proper guards: `len(trump_suits) >= 2` and `len(groups) >= 2`. Prints F-stat and p-value. Per-suit stats table. This is the **gold-standard pattern** — statistical test paired with visualization. Tests the null that hand value is independent of trump suit, which should hold if the deal generator is fair.

**Decision: No changes.** Reference pattern for S4.3 to emulate.

**S4.3 By Team (L450–491):**

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C10 | **Med** | Violin plot is visual-only — no statistical test. Violates `05_rigor.md`. S4.2 and S4.4 both have ANOVA. | **FIX** |
| C23 | **Med** | No declaring vs defending segmentation — team comparison is confounded by which team won the auction. (Tier 1: confound removal) | **FIX** |

**What it does:** Violin plots of `feat_hand_value` by team, faceted by contract type. Uses manual `ax.violinplot()` with `showmeans=True, showmedians=True`.

**Key details:** Loops over contract types, creates per-type violin plots. No ANOVA, no t-test, no p-value — the only sub-section without a statistical test. The 20_ notebook handles team balance with Mann-Whitney U (L354–362). S4.4 in this notebook does per-contract ANOVA for seats. Additionally, the team comparison is confounded: within a contract type, the declaring team systematically has higher hand_value because they chose to bid based on hand strength.

**Decided S4.3 fixes:**
1. Add per-contract ANOVA after violin plot, mirroring S4.4 pattern (C10)
2. Print bidder_team distribution per contract type (C23 Tier 1):
```python
print("\n=== Bidder Team Distribution (per contract type) ===")
if "bidder_team" in df.columns:
    for ct in sorted(df["contract_type"].unique()):
        subset = df[df["contract_type"] == ct].drop_duplicates(subset=["deal_id"])
        bt_counts = subset["bidder_team"].value_counts().sort_index()
        print(f"  {ct}: {bt_counts.to_dict()}")
```
3. Split ANOVA by declaring/defending to remove confound (C23 Tier 1):
```python
print("\n=== Team Balance ANOVA — Declaring vs Defending (per contract type) ===")
for ct in sorted(df["contract_type"].unique()):
    subset = df[df["contract_type"] == ct]
    for role, role_label in [(True, "declaring"), (False, "defending")]:
        role_df = subset[subset["is_declaring_team"] == role]
        groups = [role_df.loc[role_df["team"] == t, "feat_hand_value"].dropna().values
                  for t in sorted(role_df["team"].unique())]
        groups = [g for g in groups if len(g) > 0]
        if len(groups) >= 2:
            f_stat, p_val = f_oneway(*groups)
            print(f"  {ct} ({role_label}): F={f_stat:.3f}, p={p_val:.4f}")
        else:
            print(f"  {ct} ({role_label}): Not enough groups")
```

**S4.4 By Seat (L493–526):**

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C23 | **Med** | No bidder_seat distribution shown — bidder seat has systematically higher hand_value within a contract type. (Tier 1: confound removal) | **FIX** |

**What it does:** Box plot of `feat_hand_value` by seat × contract type via `plot_hand_value_by_seat_and_contract(df)`, plus per-contract ANOVA with proper guards.

**Key details:** Delegates to production chart function. Then runs ANOVA per contract type: filters, groups by seat, `f_oneway(*groups)`. Prints F-stat and p-value. This is the reference pattern — chart + statistical test. However, within a contract type, the bidder seat will have systematically higher hand_value because the bidder chose to bid based on their hand. If bidder_seat is unevenly distributed (e.g., seat 0 wins most auctions), the ANOVA will detect "seat imbalance" that's really declaring/defending asymmetry.

**Decided S4.4 fix:**
1. Print bidder_seat distribution per contract type (C23 Tier 1):
```python
print("\n=== Bidder Seat Distribution (per contract type) ===")
if "bidder_seat" in df.columns:
    for ct in sorted(df["contract_type"].unique()):
        subset = df[df["contract_type"] == ct].drop_duplicates(subset=["deal_id"])
        bs_counts = subset["bidder_seat"].value_counts().sort_index()
        print(f"  {ct}: {bs_counts.to_dict()}")
```

**S4.5 Feature-Level Symmetry (L528–571):**

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C13 | **Med** | NaN-unsafe sort: `sorted(seat_mean_vars, key=seat_mean_vars.get, reverse=True)` — undefined with NaN. MEMORY.md anti-pattern. | **FIX** |

**What it does:** For each numeric feature, computes variance of per-seat means (`seat_mean_vars`). Reports top 5 features with highest cross-seat variance. Then renders a Z-score heatmap of features × trump suits via `plot_feature_heatmap_by_suit(df)`.

**Key details:** The top-5 selection at L543–544 uses `sorted(..., key=seat_mean_vars.get)` which is undefined when any value is NaN. The Z-score heatmap only runs when trump data exists.

**Decided S4.5 fix:**
1. Filter NaN before sort:
```python
valid_vars = {k: v for k, v in seat_mean_vars.items() if not np.isnan(v)}
top5_by_seat_var = sorted(valid_vars, key=valid_vars.get, reverse=True)[:5]
```

### S5 Feature Distributions (L573–616)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C23 | **Med** | No declaring vs defending split — declaring hands have higher hand_value by selection. (Tier 2: analytical insight) | **FIX** |

**What it does:** Two visualizations of feature properties:
1. **Top 9 features by variance** — histogram grid via `plot_feature_distributions(df, features=top_9_names)`. Selects features with highest pooled variance.
2. **Correlation matrix** — top 15 features via `plot_feature_correlation(df, features=top_15_names)`. Shows pairwise Pearson r between features.
3. **Summary stats table** — `.describe()` for all numeric features (count, mean, std, min, max).

**Key details:**
- Uses `variances = {c: df[c].var() for c in numeric_feats}` — NaN-safe (pandas `.var()` skips NaN by default)
- Top-9/top-15 selection also uses `sorted(..., key=variances.get)` — same NaN-unsafe sort pattern as S4.5 (but less likely to hit NaN here since these are column-level variances, not group-level)
- `feat_cols` redefined locally (cell scope)

**Decided S5 fix:**
1. Add declaring vs defending overlay or side-by-side for top features (C23 Tier 2) — show that declaring hands have systematically different feature distributions (especially hand_value, trump_count, bowers)

### S6 Feature-Label Relationships (L618–733)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C15 | Low | Pearson r computed but no p-values reported (30_ S1 has them) | **FIX** |
| C23 | **Med** | No declaring vs defending split — feature→tricks_won correlation is fundamentally different for each role. (Tier 2: analytical insight) | **FIX** |

**What it does:** Three outputs:
1. **Heatmap** — Pearson r of each feature vs `tricks_won`, faceted by contract_type (rows=features, columns=contract types). Color-coded RdBu with cell annotations.
2. **Top 10 table** — per contract type, top 10 features ranked by |r|.
3. **Scatter plots** — top 3 features by max |r| across contracts, scatter vs `tricks_won` colored by contract type.

**Key details:**
- Per-contract correlation loop at L627–638: filters by contract type, computes Pearson r per feature where `valid.sum() > 2`
- `corr_df.fillna(0)` for heatmap rendering — zeros out missing correlations (acceptable for viz)
- Scatter uses `alpha=0.3, s=8` to handle overplotting
- No p-values reported (C15 — 30_ S1 computes them via `pearsonr()`)
- The feature→tricks_won correlation is confounded by declaring/defending: the declaring team chose the contract based on hand strength, so their hand_value is correlated with contract difficulty, not just tricks_won

**Decided S6 fixes:**
1. Add p-values to correlation table using `scipy.stats.pearsonr()` (C15)
2. Split correlation heatmap by declaring vs defending rows (C23 Tier 2) — either two side-by-side heatmaps or a combined one with a declaring/defending column per contract type

### S7 Summary (L735–781)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C18 | **Med** | Companion links wrong: `01_model_rung_template.py` path unclear, `20_matchup_analysis.py` doesn't exist → should be `50_r0_matchups.py` | **FIX** |
| C19 | Low | `"scorecard" in dir()` is fragile — should use `scorecard = None` sentinel | **FIX** |

**What it does:** Structured summary with 4 sub-sections:
1. **Scorecard recap** — pulls from `scorecard` variable (set in S1), prints PASS/WARN/FAIL counts and any blocking failures.
2. **Dataset summary** — deal count, row count, feature count, data source, MODE.
3. **Key findings** — contract type distribution, seat hand_value range.
4. **Companion notebook links** — hardcoded paths to related notebooks.

**Key details:**
- `"scorecard" in dir()` at L745 is fragile — if S1 was skipped (e.g., `df.empty`), `scorecard` is never defined and this silently skips the recap. A `scorecard = None` sentinel before S1 would be more robust (C19).
- Companion links at L778–779 are wrong (C18): `01_model_rung_template.py` is in `notebooks/_templates/` not in `r0/`, and `20_matchup_analysis.py` doesn't exist — should be `50_r0_matchups.py`. Also missing references to `20_outcome_health.py` and `30_feature_outcome_eval.py`.
- Contract type distribution at L769 uses row-level counts (not deal-level) — inconsistent with S3's deal-level reporting.

**Decided S7 fixes:**
1. Fix companion notebook links (C18): update to `20_outcome_health.py`, `30_feature_outcome_eval.py`, `40_r0_baseline.py`, `50_r0_matchups.py`
2. Replace `"scorecard" in dir()` with `scorecard = None` sentinel before S1 (C19)
3. Change contract type distribution in key findings to deal-level (`drop_duplicates(subset=["deal_id"])`) for consistency with S3

---

## Per-Notebook Detail: 20_outcome_health.py

> Notebook: `notebooks/arc_d/r0/20_outcome_health.py` (567 lines, 8 sections)
> Status: REVIEWED — all sections decided

### S0 Configuration & Data Loading (L34–180)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C1 | Med | Dual glob import (`_g` at L65, `glob_mod` at L71) | **FIX** |
| C22 | Med | Dataset summary at L173–179 is close but lacks bidder name, run date, seed, run path | **FIX** |

**What it does:** Parameters cell → CWD resolution → discovery cell → imports → data loading with synthetic fallback → `deal_df` creation (seat 0 filter) → dataset summary.

**Key details:**
- **20_ is the reference for MODE fallback** — L100: `get(MODE, 30)` with default. Only notebook that does this. C2 does NOT apply here.
- Has `SEED = 42` (L98) ✓
- **Richest synthetic fallback** — includes all outcome + auction + bidder columns. No `feat_*` columns (correct — this notebook is outcome-focused).
- `deal_df = df[df["seat"] == 0].copy()` (L170) — deal-level frame for auction analysis. Correct: deal-level columns are identical across seats.

**Decided S0 fixes:**
1. Replace `glob_mod.glob(str(...))` with `Path.glob()` at L110, remove `import glob as glob_mod` (C1)
2. Expand dataset summary into full run metadata block (C22): bidder name (parse from run dir), seed, run path, date, contract type breakdown. Same pattern for all 5 notebooks.

### S1 Fail-Fast Validation (L182–247)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No issues — gold-standard section | OK |

**What it does:** 4 assert-style gates with results tracking table:

| Check | What it validates |
|-------|-------------------|
| `tricks_won in [0, 10]` | Range check on outcome variable |
| `team0 + team1 tricks == 10` | Zero-sum constraint per deal |
| `no missing contract_type` | No null contract types |
| `no missing tricks_won` | No null outcomes |

**Key details:**
- **Only notebook that uses `assert` statements** — all others use soft `if not df.empty` guards (C9 reference). C6 (30_) and C7 (50_) should emulate this.
- `_validation_results` list collects check metadata for the summary table

**Decision: No changes.** Reference pattern for fail-fast validation.

### S2 Outcome Distributions by Contract Type (L249–311)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C20 | Med | No min-N guard — histogram title shows row-level N (4× deals), thin strata produce noisy distributions | **FIX** |
| C23 | Med | No declaring vs defending split (Tier 2) | **FIX** |

**What it does:** Three outputs:
1. **Histogram grid** — `tricks_won` by contract_type, bins 0–10, per-panel N in title
2. **Violin/box plot** — `plot_outcome_distributions(df, outcome="tricks_won", group_by="contract_type")`
3. **Summary table** — per-contract N, mean, std, P5–P95 quantiles

**Key details:**
- Histogram N at L271 is row-level (4× deals)
- Summary table quantiles (P5–P95) are a good addition vs 10_

**Decided S2 fixes:**
1. Add min-N guard with warning when strata < 30 deals (C20)
2. Add declaring vs defending overlay on histograms or split summary rows (C23 Tier 2)

### S3 Team & Seat Balance (L313–378)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C23 | **Med** | Team delta confounded by declaring/defending (Tier 1) | **FIX** |
| C24 | Low | Section title says "& Seat Balance" but only tests team balance — no seat analysis | **FIX** |

**What it does:** Two outputs:
1. **Boxplot** — tricks_won by team × contract_type, with mean markers
2. **Balance table** — per-contract team0_mean, team1_mean, delta, Mann-Whitney U p-value, pass/fail gate (|delta| < 0.25)

**Key details:**
- **Mann-Whitney U is the right test** — nonparametric, robust for small N, appropriate for discrete bounded outcome. Reference pattern.
- Gate: |delta| < 0.25 — reasonable practical significance threshold
- `_team_balance_gates` feeds into S7 — good gate propagation
- Missing seat balance despite section title

**Decided S3 fixes:**
1. Add bidder_team distribution per contract type + split delta by declaring/defending (C23 Tier 1)
2. Add seat balance analysis or rename section title (C24)

### S4 Auction Health (L380–413)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C25 | Med | Bid distribution chart pools all contract types — need suit (stacked by suit) and high/low (stacked by type) breakout | **FIX** |

**What it does:** Two outputs:
1. **Library composite figure** — `plot_auction_health(df)` (3 panels: contract selection, bid distribution, auction length)
2. **Auction summary table** — per-contract n_deals, mean_bid, median_bid, pass_rate, mean_rounds

**Key details:**
- Uses `deal_df` (seat 0 filter) for deal-level stats — correct
- Clean delegation to library for composite chart

**Decided S4 fix:**
1. Add a second chart: bid distribution faceted by contract group (C25):
   - **Suit contracts**: bid histogram stacked by trump suit (C/D/H/S) — shows whether bidding level varies by suit
   - **High/Low contracts**: bid histogram stacked by contract type (high/low) — shows whether high and low contracts cluster at different bid levels
   - This reveals within-group bid structure that the pooled composite chart hides

### S5 Bidder Performance (L415–464)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C26 | Med | Make rate definition not stated — reviewer needs formal definition | **FIX** |
| C27 | Med | Make rate by bid value chart is embedded in composite — should be standalone for visibility | **FIX** |
| C28 | Med | Overbid/underbid is pooled — should facet by contract type | **FIX** |

**What it does:** Two outputs:
1. **Library composite figure** — `plot_bidder_performance(df)` (3 panels: make rate, make rate by bid value, overbid histogram)
2. **Make rate table** — per-contract N, made, make_rate, 95% binomial CI

**Key details:**
- Proper `is_bidder == True` filter — avoids double-counting
- **Binomial CI** via `scipy.stats.binom.interval(0.95, n, p)` — correct for Bernoulli outcome. Reference pattern.
- Gate: `0.2 ≤ make_rate ≤ 0.95` → PASS, else FLAG
- C23 not applicable — already bidder-specific analysis

**Decided S5 fixes:**
1. Add formal make rate definition in section markdown header (C26): "Make rate = fraction of deals where the declaring team won at least as many tricks as the winning bid (`tricks_won >= winning_bid`). Range [0, 1]; healthy range 0.4–0.8."
2. Extract make rate by bid value curve as standalone chart (C27) — keep the composite but add a full-size version with labeled data points and CI bands
3. Add overbid/underbid histogram faceted by contract type (C28) — suit contracts may have different overbid patterns than high/low

### S6 Distribution Analysis CDF/CCDF (L466–487)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C23 | Med | CDF/CCDF should split declaring vs defending — curves shift right for declaring team (Tier 2) | **FIX** |
| C20 | Med | No min-N guard (thin strata → step-function CDFs) | **FIX** |
| C29 | Med | No summary table — should include tricks % and points by contract type | **FIX** |
| C30 | Med | No points analysis — tricks_won misses asymmetric scoring risk (set penalty = -bid) | **FIX** |

**What it does:** Two charts:
1. CDF of tricks_won by contract_type via `plot_cdf()`
2. CCDF of tricks_won by contract_type via `plot_ccdf()`

**Key details:** Very thin section — just 2 library calls, no statistical tests, no summary, no interpretation. Not represented in S7 gates.

**Decided S6 fixes:**
1. Add declaring vs defending CDF/CCDF overlay (C23 Tier 2)
2. Add min-N guard (C20)
3. Add summary table (C29): per contract type, % at each tricks value (0–10), mean, median
4. Add points analysis (C30) — compute game points from existing columns:
   - **Declaring team:** `tricks_won if made_bid else -winning_bid`
   - **Defending team:** `tricks_won` (always)
   - Points distribution table by contract type (declaring vs defending)
   - Points CDF/CCDF — reveals the -bid tail risk for declarers
   - Expected points by bid value curve — shows the risk/reward inflection

### S7 Summary (L489–567)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No issues — strongest summary section across all notebooks | OK |

**What it does:** Structured gate-based summary:
1. Collects gates from S1 (`_validation_results`), S3 (`_team_balance_gates`), S5 (`_bidder_perf_gates`)
2. PASS/FAIL/FLAG summary table
3. Totals by status
4. Key findings (deal count, contract type distribution — correctly deal-level via seat 0)
5. Failure/flag detail messages

**Key details:**
- 3-level status: PASS / FAIL / FLAG (FLAG = human review, softer than FAIL)
- S2, S4, S6 not represented in gates — acceptable (informational sections)

**Decision: No changes.** Best summary pattern. Reference for other notebooks.

---

## Per-Notebook Detail: 30_feature_outcome_eval.py

> Notebook: `notebooks/arc_d/r0/30_feature_outcome_eval.py` (1353 lines, 8 sections)
> Status: REVIEWED — all sections decided

### S0 Configuration & Data Loading (L36–249)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C2 | Med | `MODE_DEAL_COUNTS.get(MODE)` no fallback (L95) — MODE typo → `None` max_deals | **FIX** |
| C6 | **High** | No fail-fast validation at all — goes straight from data loading to model analysis. Only High severity issue across all 5 notebooks. | **FIX** |
| C22 | Med | Data summary at L240–249 is close (shape, feat count, deals per contract) but lacks bidder name, seed, run date, run path | **FIX** |

**What it does:** Parameters cell → CWD resolution → discovery cell → imports → data loading (JSONL primary with dir-to-file resolution, synthetic fallback) → artifact bundle loading → eval metrics loading → METRIC_ALIASES → data summary.

**Key details:**
- **Best S0 pattern across all notebooks** — reference for synthetic fallback (10 features, all auction/bidder columns), `Path.glob()` for data discovery, JSONL fallback (try `logs/*.jsonl` then `*.jsonl`), SEED=42 present
- Artifact bundle loading (L177–228) is unique to 30_ — loads `rung_bundle_{RUNG_ID}.json`, resolves repo-root-relative paths via `_resolve_path()`, loads eval metrics per arm, loads model artifacts
- `METRIC_ALIASES` dict (L231–238) provides canonical↔alias mapping — single source of truth for metric naming
- **No `glob_mod`** — discovery cell uses `import glob as _g` only (unlike 10_, 20_, 40_, 50_). C1 does NOT apply.
- **No MODE fallback** — `MODE_DEAL_COUNTS.get(MODE)` at L95 with no default (C2 applies)
- Data summary at L240–249 prints shape, feat count, contract types, deals per contract — close to C22 but lacks run identity

**Decided S0 fixes:**
1. Add MODE fallback with warning (C2): `get(MODE)` → warn + default to 30 on unknown MODE
2. Add fail-fast validation section after data loading (C6) — emulate 20_ S1 pattern:
   - tricks_won range [0, 10]
   - team0 + team1 = 10 (zero-sum)
   - no missing contract_type
   - no missing tricks_won
   - feature columns present (>0 feat_* columns)
3. Expand data summary into full run metadata block (C22)

### S1 Feature-Outcome Correlations (L251–400)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C23 | **Med** | No declaring vs defending split — correlation is confounded by role (Tier 2: analytical insight) | **FIX** |
| C32 | **Med** | Correlates only against `tricks_won` — should also correlate against `points_won` since net_eppd is the optimization target | **FIX** |

**What it does:** Three outputs:
1. **Correlation heatmap** — features × contract_type, Pearson r vs `tricks_won`, RdBu color-coded with cell annotations
2. **Top 5 bar charts** — per contract type, top 5 features by |r| with signed annotation
3. **Full correlation table** — per contract type, all features with Pearson r, p-value (via scipy), N

**Key details:**
- **Has p-values** (L378–383) — uses `scipy.stats.pearsonr()` with `HAS_SCIPY` guard. This is the reference pattern that 10_ S6 and 40_ §7.5 should adopt (C15).
- Markdown header has description (L252–256) — one of the few sections with it
- Correlates features against `tricks_won` only. Since OLSa predicts tricks_won, this is the model-diagnostic view. But net_eppd (points-based) is the optimization goal — features that correlate with tricks but not with points may indicate overbidding exposure (C32).
- Within a contract type, the declaring team chose the contract based on hand strength, so declaring hands have systematically higher feature values. Pooling declaring + defending conflates this selection effect with the feature→outcome relationship.

**Decided S1 fixes:**
1. Add declaring vs defending split (C23 Tier 2): side-by-side heatmaps or a combined one with declaring/defending column groups. This reveals whether feature→outcome correlation differs by role — expected: declaring hand_value correlates strongly because the bidder selected on it; defending correlation is the "pure" signal.
2. Add dual correlation target (C32): features × `tricks_won` + features × `points_won`. Requires `points_won` column from C32 infrastructure change to `_expand_record()`. Side-by-side heatmaps showing both targets. Divergences between tricks and points correlations highlight where overbidding risk lives — a feature that boosts tricks but not points suggests the bidder overvalues it.

### S2 Model Specification (L402–597)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C34 | **Med** | Coefficient heatmap is low signal for sparse models — replace with `statsmodels.OLS` summary tables (Stata-style output with std errors, t-stats, p-values, CIs). Apply to all model spec sections (30_ S2, 40_ §6). | **FIX** |

**What it does:** Four outputs:
1. **Model specs table** — per arm × contract: feature names, weights (sorted by |w|), bias
2. **Coefficient heatmap** — primary arm (OLSa_Full), all features × contracts, via `plot_coefficient_heatmap()` with ImportError fallback to manual heatmap
3. **Coefficient comparison** — OLSa vs OLSa_Full side-by-side horizontal bar charts per contract
4. **Full coefficient table** — per arm × contract, all features with weights

**Key details:**
- Primary arm selection: prefers `olsa_full`, falls back to first available
- Coefficient comparison (L497–576) builds `features_union` across both arms, handles missing features with `w_map.get(f, 0.0)`
- All charts have `CHART_OUTPUT_DIR` save logic
- Clean separation: artifact loading in S0, display in S2
- `statsmodels>=0.14.0` is already a project dependency (`pyproject.toml` L28) but never used in production code

**Decided S2 fixes:**
1. **Drop coefficient heatmap** — low information density, especially for sparse 3/1/1 models (mostly empty cells). Also drop the manual fallback heatmap.
2. **Add `statsmodels.OLS` summary tables** — refit each per-contract model with `sm.OLS(y, sm.add_constant(X)).fit()` for display only (actual bidder uses frozen artifact weights). Produces canonical regression output: coefficients, std errors, t-statistics, p-values, 95% CIs, R², adjusted R², F-statistic. One summary per contract × arm.
3. **Keep coefficient comparison bar chart** (OLSa vs OLSa_Full side-by-side) — this visual comparison of the two arms' weights is genuinely useful.
4. **Keep full coefficient table** as compact fallback when statsmodels unavailable.

### S3 Model Performance Diagnostics (L599–869)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C35 | **Med** | All diagnostic charts pool contract types on shared axes — suit vs high/low have fundamentally different residual patterns, prediction ranges, and model structures (3 features vs 1). Facet into separate panels per contract group. | **FIX** |

**What it does:** Five outputs:
1. **Pred vs Actual scatter** — via `plot_model_diagnostics()` with fallback, color-coded by contract type
2. **Residual distribution** — histogram per contract type, vertical line at 0
3. **Residuals vs Predicted** — scatter per contract type, horizontal line at 0
4. **Bootstrap R2** — histogram of bootstrap R2 distribution with 95% CI lines (skips SMOKE; 100 boots QUICK, 1000 FULL)
5. **Performance table** — per-contract R2, MAE, N, with 95% CIs (R2_95CI, MAE_95CI) + residual summary (mean, std, P5, P95, max|residual|)

**Key details:**
- Reuses primary arm from S2 selection logic
- Bootstrap uses `SEED` for reproducibility
- Per-contract bootstrap CIs (L822–841) — correct: runs separate bootstrap per contract
- Residual summary table (L851–862) is unique to 30_ — good diagnostic
- `ss_tot > 0` guard prevents division by zero in R2 computation
- `len(all_y_arr) >= 50` guard on bootstrap — avoids unstable CIs with tiny samples

**Decided S3 fix:**
1. **Facet all charts by contract group** (C35) — suit vs high/low in separate panels:
   - **Pred vs Actual**: separate scatter per contract type, each with own y=x line and axis scale. Suit predictions cluster differently than high/low.
   - **Residual distribution**: separate histograms per contract type. Suit residuals may be normally distributed while high/low (1-feature models) may have heavier tails.
   - **Residuals vs Predicted**: separate scatter per contract type. Heteroscedasticity patterns differ — suit has 3 features to spread predictions, high/low compress into narrow bands.
   - **Bootstrap R2**: separate histograms per contract type (currently only the CI table is per-contract, the histogram is pooled).
   - **Performance table**: already per-contract — no change needed.
   - Keep the pooled versions as a summary overview, but the per-contract faceted versions are the primary diagnostic.

### S4 Dual-Arm Comparison (L871–1041)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C36 | **Med** | No metric definitions — arm comparison table uses net_eppd, eppd, bid_rate, make_rate, cvar_5, downside_variance without defining any of them. Reviewer unfamiliar with Arc D terminology would be lost. Also: per-contract R2 duplicates S3 computation without explanation of the difference (S3 = single-arm diagnostics, S4 = cross-arm comparison). | **FIX** |

**What it does:** Four outputs:
1. **Library dual-arm comparison** — via `plot_dual_arm_comparison()` when eval metrics available
2. **Per-contract R2 bar chart** — grouped bars, OLSa vs OLSa_Full, annotated with R2 values
3. **Attribution gap analysis** — `OLSa_Full net_eppd - OLSa net_eppd`, signed interpretation
4. **Arm comparison table** — eval metrics (net_eppd, eppd, bid_rate, make_rate, cvar_5, downside_variance) for both arms

**Key details:**
- Recomputes per-contract R2 for each arm independently (doesn't reuse S3 results) — same formula as S3 but for both arms. The R2 values are identical to S3's for the primary arm.
- Attribution gap (L1006–1022) is the key dual-arm metric: measures the value of additional features beyond the sparse 3/1/1 selection. For R0: gap = -0.1437 (negative = more features slightly hurt)
- `_eval_available` and `_arm_metrics` gates from S0 — clean data dependency chain
- Uses `METRIC_ALIASES` for canonical→display mapping
- **Two metric sources mixed without explanation**: R2 comes from regression fit on eval data (notebook-computed), while net_eppd/make_rate/etc. come from pre-computed simulation eval files (loaded in S0). A reviewer needs to know which metrics are "how well does the model predict tricks?" vs "how well does the bidder play games?"

**Decided S4 fixes:**
1. **Add metric glossary** (C36) — markdown cell or printed table defining all terms used in the arm comparison:
   - `net_eppd`: Net expected points per deal — (bidder team points − opponent team points) averaged across all deals. Primary optimization target.
   - `eppd`: Expected points per deal — bidder team points only, averaged across deals where the bidder won the auction.
   - `bid_rate`: Fraction of deals where the bidder chose to bid (vs pass).
   - `make_rate`: Fraction of bid deals where declaring team won ≥ bid tricks.
   - `cvar_5`: Conditional Value at Risk at 5th percentile — average points in worst 5% of deals. Measures tail risk.
   - `downside_variance`: Variance of points in deals where the bidder was set.
   - `R2`: Coefficient of determination — fraction of variance in tricks_won explained by the model's predictions. Computed per-contract from notebook eval data (not from simulation).
   - `attribution_gap`: net_eppd(OLSa_Full) − net_eppd(OLSa). Positive = more features help; negative = sparse is sufficient.
2. **Add note distinguishing metric sources**: "R2 is computed from regression fit on this notebook's eval data. All other metrics (net_eppd, make_rate, etc.) come from simulation evaluation runs loaded in S0."
3. **Drop standalone per-contract R2 bar chart** (L958–1004) — fully redundant with the R2 panel inside `plot_dual_arm_comparison()`. Same values, different formatting. Keep the library chart (shows R2 in context alongside other metrics).

### S5 Calibration Analysis (L1043–1229)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C37 | **Med** | Prediction distribution pools contract types and lacks actual distribution overlay. Facet into suit vs high/low panels; overlay actual tricks_won distribution to show whether model prediction spread matches reality. | **FIX** |

**What it does:** Four outputs:
1. **Calibration curve** — via `plot_calibration_curve()` with fallback, binned predicted vs actual mean per contract type + perfect calibration line
2. **Prediction distribution** — histogram per contract type (standalone, separate from calibration fallback version)
3. **Calibration bins table** — per contract × 10 quantile bins: N, pred range, mean pred, mean actual, deviation

**Key details:**
- `pd.qcut(yp, q=10, labels=False, duplicates="drop")` for binning — handles ties correctly
- `len(yp) < 10` guard before binning — avoids errors with tiny samples
- Deviation = mean_actual - mean_pred — positive = model underpredicts, negative = overpredicts
- Prediction distribution shown twice (inside calibration fallback and standalone) — minor redundancy but harmless since library chart replaces the fallback

**Decided S5 fix:**
1. **Facet prediction distribution by contract type** (C37) — separate panels for suit vs high/low. The 3-feature suit model produces wider prediction spread than the 1-feature high/low models. Pooling hides this structural difference.
2. **Overlay actual tricks_won distribution** (C37) — on each faceted panel, show both predicted (model output) and actual (simulation outcome) distributions. This reveals:
   - Whether the model's prediction range matches the actual outcome range (under-dispersion check)
   - Whether the distribution shapes match (the Gaussian assumption in HybridOLSa depends on roughly symmetric residuals)
   - For high/low (1-feature models), whether the narrow prediction band adequately represents the actual spread

### S6 Rung-Specific Analysis (L1231–1251)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C16 | ~~Low~~ → **Med** | Empty placeholder — fill with R0-specific model analysis unique to 30_'s perspective. 4 analyses identified, none overlap with 40_. | **FIX** |

**What it does:** Currently a placeholder printing "S6 is a placeholder -- fill when copying template for a specific rung."

**Key details:**
- Template design: intended to be filled per rung
- Original assessment (leave empty) was wrong — 4 valuable analyses exist that are unique to 30_'s model-focused lens and don't duplicate 40_

**Decided S6 content for R0 (4 analyses):**

1. **Gaussian assumption validation** — the HybridOLSa decision layer assumes `tricks ~ N(mu, sigma²)`. Test this directly per contract type:
   - Shapiro-Wilk or Anderson-Darling normality test on per-contract residuals
   - Q-Q plot of residuals vs normal distribution
   - If the assumption fails for a contract type, it has implications for the Gaussian EV calculation and R1a design direction
   - This is the most important R0-specific check — first deployment of HybridOLSa, need to validate the core assumption

2. **Feature selection justification** — explain the 3/1/1 sparse feature choice:
   - Forward selection results from `feature_selection.py` — features tried, CV score progression, stopping point
   - Comparison of the 3/1/1 selection vs top features by S1 correlation ranking — are they the same? If not, why does forward selection prefer different features than raw correlation?
   - Contextualizes S2's coefficient display with the *process* that produced it

3. **Residual structure analysis** — deeper than S3's scatter/histogram:
   - Correlate residuals with features NOT in the model — if residuals correlate strongly with `voids` or `hand_value`, the model is missing predictive signal
   - Per-contract residual correlations table: for each excluded feature, Pearson r with residuals + p-value
   - Identifies features that future rungs (R1a+) should consider adding

4. **Bid decision audit** — trace 5–10 sample deals through the full pipeline:
   - Hand features → OLS prediction (mu) → residual variance (sigma) → Gaussian EV calculation → bid decision → actual outcome
   - Include examples of: correct bid + make, correct bid + set, overbid, underbid, pass
   - Makes the model tangible for the reviewer — shows how the math plays out on real hands

**No overlap with 40_:** 40_ covers seed sensitivity (§9), comparator battery (§11), trump invariance (§7.6), drift detection (§7.7). All four S6 analyses are model-internals focused, which is 30_'s unique domain.

### S7 Summary & Promotion Readiness (L1253–1353)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No structural issues — good summary section | OK |

**What it does:** Five summary sub-sections:
1. **Feature health** — NaN count, zero-variance count per feature
2. **Outcome health** — tricks_won range, mean, per-contract mean/std/n
3. **Model diagnostics** — arms loaded, contracts per arm, total feature slots
4. **Eval metrics** — per-arm net_eppd, make_rate, bid_rate + attribution gap
5. **Limitations** — MODE, data_source, synthetic/SMOKE warnings
6. **Promotion recommendation** — checklist of S1–S6 with human-review guidance

**Key details:**
- No gate propagation (unlike 20_ S7) — uses soft prints rather than PASS/FAIL/FLAG table. This is acceptable: 30_ is a model evaluation notebook (subjective assessment), not a health check notebook (binary pass/fail). Promotion is a human decision informed by all sections.
- Limitations section is good — explicitly flags MODE and data_source constraints
- Promotion recommendation at L1344–1353 lists S1–S6 as a human checklist — appropriate for HITL workflow
- Feature health check at L1265–1277 is independent of S0 (no upstream dependency on health scorecard like 10_ S7)

**Decision: No changes.** Appropriate summary for a model evaluation notebook. The human-checklist approach is the right pattern here — promotion decisions require holistic judgment, not binary gates.

---

## Per-Notebook Detail: 40_r0_baseline.py

> Notebook: `notebooks/arc_d/r0/40_r0_baseline.py` (1025 lines, 12 sections)
> Status: NOT YET REVIEWED

### §0 Setup (L34–227)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C1 | Med | Dual glob import (`_g` + `glob_mod`) | Cross-ref |
| C2 | Med | `MODE_DEAL_COUNTS.get(MODE)` no fallback — typo → `None` | Cross-ref |
| C22 | Med | No run metadata summary after data loading | Cross-ref |

**What it does:** Parameters, CWD resolution, discovery cell, imports, data loading (JSONL primary, synthetic fallback), health scorecard, artifact bundle loading, METRIC_ALIASES.

**Key details:**
- CWD resolution (L50-61): correctly finds repo root — pattern from PR #426
- Discovery cell (L68-75): shows `arc_d_eval*` runs — appropriate for 40_
- Data loading (L114-174): robust — tries JSONL eval logs, warns if EVAL_RUN_DIR set but empty, falls back to synthetic. Synthetic creates 3 features (feat_hand_value, feat_trump_count, feat_bowers).
- Bundle loading (L181-227): loads rung bundle, eval metrics per arm, model artifacts per arm. Good error handling.
- METRIC_ALIASES (L220-227): single mapping point for canonical↔alias metric names

**Decision: Apply cross-cutting fixes C1, C2, C22.** Otherwise solid setup.

### §1 Deal Health (L229–274)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C38 | Med | `plot_feature_distributions()` double-prefix bug — passes `feat_*` names but API expects unprefixed. Third chart renders "No numeric features to plot". | **FIX** |
| C11 | Med | Team balance means-only (in §3, but §1 seat balance also visual-only) — see §3 for stat test fix | Cross-ref |

**What it does:** Four visualization/analysis steps:
1. **Seat balance boxplot** via `plot_hand_value_by_seat(df)` — visual seat balance check
2. **Hand value by contract type** via `plot_hand_value_by_contract(df)` — contract type distribution
3. **Top-5 feature distributions** via `plot_feature_distributions(df, features=top5_by_var)` — **BROKEN**: double-prefix bug
4. **Per-contract feature variance table** — top 10 features by std, per contract type (text output)
5. **Seat balance stats** via `compute_seat_balance(df)` — reports max_deviation and is_balanced

**Key details:**
- Bug at L254-255: `top5_by_var` has `feat_*` names from `df[numeric_feats].var().nlargest(5).index`. `plot_feature_distributions` at charts.py:213 re-adds `feat_` prefix → looks for `feat_feat_hand_value` etc. → no matches → "No numeric features to plot"
- Template (10_feature_health.py:575) has the fix: `top_9_names = [c.replace("feat_", "") for c in top_9]`
- The per-contract variance table (L258-264) works fine — uses raw column names directly
- §1 is the only section in 40_ that calls this function with explicit features; other notebooks either don't call it or use the correct pattern

**Decided §1 fix:**
1. **Strip `feat_` prefix** (C38) — change L254 to: `top5_by_var = [c.removeprefix("feat_") for c in df[numeric_feats].var().nlargest(5).index.tolist()]`

### §2 Auction Health (L276–333)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C39 | Med | Auction summary not faceted by seat — bidder seat distribution, dealer seat distribution, and bid height/pass rate by dealer position not shown. Seat rotation anomalies would be invisible. | **FIX** |
| C40 | Med | Contract selection lacks suit breakout — "suit" is a single bucket but trump suit choice matters (verify no suit bias in bidder behavior). | **FIX** |
| C22 | Med | No run metadata summary (cross-cutting) | Cross-ref |
| C31 | Med | Section description adequate (has 2-line explainer) — 40_ is the reference pattern | OK |

**What it does:** Three analyses, gated on `_data_source == "eval_logs"`:
1. **Bid distribution by contract type** — value_counts of `winning_bid` per contract, with bar chart (L287-314)
2. **Auction summary** — mean pass rate, mean bids/deal, mean passes/deal (L316-322). Single pooled number.
3. **Contract selection frequency** — value_counts of `contract_type` (L324-327). No trump suit breakout.

All operate on `deal_df = df[df["seat"] == 0]` (one row per deal).

**Key details:**
- Data limitation: `_expand_record()` stores `n_bids`, `n_passes`, `auction_rounds` as deal-level aggregates (identical across all 4 seats). Per-seat bid actions not available without re-parsing `auction_transcript`.
- However, `bidder_seat` and `dealer_seat` ARE per-row columns — seat distribution analysis is possible now.
- Auction summary (L319) computes pass rate as `mean(n_passes) / mean(auction_rounds)` — this is ratio-of-means, not mean-of-ratios. For a summary stat it's fine, but worth noting.
- Section markdown (L277-280) has a good 2-line description — matches the 40_ reference pattern for C31.

**Decided §2 fixes:**
1. **Seat-faceted auction stats** (C39):
   - Bidder seat distribution: `deal_df["bidder_seat"].value_counts()` — should be ~25% each if rotation is fair
   - Dealer seat distribution: `deal_df["dealer_seat"].value_counts()` — should be uniform
   - Bid height by dealer seat: groupby `dealer_seat`, mean of `winning_bid` — checks if deal position affects auction outcome
   - Pass rate by dealer seat: groupby `dealer_seat`, mean of `n_passes` / `auction_rounds`
2. **Suit breakout in contract selection** (C40):
   - For suit contracts: value_counts of `trump` within `contract_type == "suit"`
   - Cross-tab: `pd.crosstab(deal_df["contract_type"], deal_df["trump"].fillna("__NONE__"))`
   - Should show ~equal frequency across C/D/H/S if no suit bias

**Structural decision (C49): Promote to dedicated `25_auction_health.py` notebook.** The planned fixes (C39, C40, C42, C43) plus new auction analyses (bid escalation, pass rate by position) would triple the auction content. Moving §2 and §4 out of 40_ reduces it to "eval verification + promotion gate." The 25_ notebook absorbs:
- Bid distribution by contract type (from §2)
- Suit breakout for contract selection (C40)
- Bidder seat / dealer seat distributions (C39)
- Make rate and bid accuracy with charts (from §4 + C42)
- Seat-faceted bid accuracy (C43)
- Auction length analysis
- Bid escalation patterns (from auction transcript, if available)
- Pass rate by position relative to dealer

### §3 Gameplay Health (L335–361)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C41 | Med | No points_won analysis — only tricks_won shown. Points capture asymmetric scoring (declaring: tricks if made, -bid if set). Need mean, median, distribution alongside tricks. **Depends on C32.** | **FIX** |
| C11 | Med | Team balance is means-only table — no significance test (Mann-Whitney U or t-test). Visual-only violates `05_rigor.md`. | **FIX** |
| C23 | Med | No declaring vs defending segmentation (cross-cutting) | Cross-ref |

**What it does:** Two analyses:
1. **Tricks won distribution** via `plot_outcome_distributions(df, outcome="tricks_won", group_by="contract_type")` — histograms faceted by contract type (L341-353)
2. **Team balance table** — `groupby(["contract_type", "team"])["tricks_won"].mean().unstack()` — means only, no significance test (L355-359)

**Key details:**
- Distribution chart is well done — uses diagnostics library, faceted by contract type, saves to CHART_OUTPUT_DIR
- Team balance table shows only means — in self-play the teams should be symmetric, but without a stat test we can't confirm this. C11 flagged this in the initial inventory.
- Missing: points_won analysis (C41). tricks_won is the OLSa prediction target, but net_eppd (points-based) is the optimization goal. The asymmetric payoff (declaring team gets -bid on set, not -tricks) means tricks_won can look healthy while the points distribution reveals risk.
- Missing: declaring vs defending split (C23). The team balance means are confounded — declaring team has systematically higher tricks_won (they chose the contract based on hand strength).

**Decided §3 fixes:**
1. **Add points_won analysis** (C41, depends on C32):
   - Mean and median points_won by contract type and team
   - Distribution chart for points_won alongside tricks_won (same `plot_outcome_distributions` call pattern)
   - Highlights the asymmetric scoring risk that tricks_won alone hides
2. **Add stat test to team balance** (C11):
   - Mann-Whitney U test per contract type (team 0 tricks vs team 1 tricks)
   - Print p-value alongside means — self-play should show p > 0.05
   - Also add declaring vs defending split (C23): show means for declaring team vs defending team separately

### §4 Auction Outcomes (L363–393)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C42 | Med | Text-only — no charts for bid accuracy or make rate. Reviewer needs visual patterns (make rate by bid value, surplus distribution). | **FIX** |
| C43 | Med | Not faceted by seat — can't verify bidder behavior is symmetric across seat positions. In self-play, seat 0 and seat 2 (same team) should bid identically in expectation. | **FIX** |

**What it does:** Single analysis block on `bidder_df` (one row per deal, `is_bidder == True`):
- Per contract type: make rate, overbid rate (`tricks < bid`), underbid rate (`tricks > bid + 1`), mean surplus (`tricks - bid`)
- All text output, no charts

**Key details:**
- Correctly filters to bidder-only rows (L371) — avoids double-counting
- Overbid threshold at L384: `tricks_won < winning_bid` — this is the raw tricks comparison, not points. Appropriate for bid accuracy analysis.
- Underbid at L385 uses `> winning_bid + 1` — a surplus of exactly 1 is "efficient", 2+ is underbid. Reasonable threshold but should be documented.
- No seat-level breakout — in self-play all 4 seats use the same bidder, so we expect identical behavior. But if there's a rotation bug or seed interaction, per-seat stats would catch it.
- Section markdown (L364-367) has a good description — 40_ reference pattern.

**Decided §4 disposition:** Move to `25_auction_health.py` (C49). All §4 content + fixes C42/C43 absorbed by the new notebook. §4 is deleted from 40_.

### §5 Gameplay Outcomes (L395–439)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C44 | Med | CDF/CCDF not faceted by team or seat — misses free symmetry validation. In self-play, team 0 and team 1 CDFs should overlap. Divergence flags simulation or data bug. | **FIX** |
| C45 | Med | No percentage table of tricks won at each increment — CDF chart shows shape but reviewer needs exact values (e.g., "60% of declaring hands win ≥ 6 tricks in suit contracts"). | **FIX** |
| C46 | Med | No points_won analysis — declaring summary stats and CDF/CCDF are tricks-only. Points capture asymmetric payoff risk. Need parallel points_won stats + CDF. **Depends on C32.** | **FIX** |
| C47 | Low | CDF/CCDF use full `df` (all seats/teams) but section title says "declaring team" — mismatch between stats scope (declaring-only) and chart scope (all rows). | **FIX** |

**What it does:** Two analysis blocks:
1. **Declaring team summary stats** (L402-418): Filters to `is_declaring_team == True`, deduplicates on `(deal_id, team)`, prints mean/std/5th/95th pctl of tricks_won per contract type.
2. **CDF and CCDF charts** (L420-435): Uses full `df` (NOT declaring-only), grouped by `contract_type`. Shows cumulative distribution shape.

**Key details:**
- Declaring filter is correct for stats: `drop_duplicates(subset=["deal_id", "team"])` yields one row per deal for the declaring team
- CDF/CCDF scope mismatch (C47): stats use `declaring_df`, charts use `df`. Minor — in self-play the declaring team perspective is the more interesting one, but all-seat CDF is also valid. Should be explicit about which view each chart represents.
- `plot_cdf` supports `group_by` as a single column string — to add team/seat faceting, call separately with `group_by="team"` or `group_by="seat"`
- No per-increment percentage table — the CDF chart encodes this information but requires visual estimation. An explicit table (tricks = 0,1,...,10 × contract type → % of deals) gives precise numbers for the review report.

**Decided §5 fixes:**
1. **Facet CDF by team and seat** (C44):
   - Add `plot_cdf(df, column="tricks_won", group_by="team", title="CDF Tricks Won by Team")` — self-play symmetry check, lines should overlap
   - Add `plot_cdf(df, column="tricks_won", group_by="seat", title="CDF Tricks Won by Seat")` — 4 lines should overlap, catches rotation bugs
   - Keep existing contract_type faceted CDF as well
2. **Add percentage table** (C45):
   - Per contract type: for each tricks_won value (0–10), show % of deals at that level and cumulative %
   - Can use `pd.crosstab(declaring_df["contract_type"], declaring_df["tricks_won"], normalize="index")`
3. **Add points_won CDF and stats** (C46, depends on C32):
   - Same declaring_df summary stats but for `points_won` (mean, median, std, 5th/95th pctl)
   - CDF of points_won by contract_type — shows tail risk from set penalties
   - Points CDF by team — another symmetry check
4. **Fix scope mismatch** (C47):
   - Either filter CDF/CCDF to `declaring_df` (consistent with stats) or add clear labels showing "all seats" vs "declaring only"

### §6 Model Specs (L441–496)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C34 | Med | Coefficient heatmap is low signal for sparse models — replace with `statsmodels.OLS` summary tables (Stata-style). | **FIX** |

**What it does:** For each model arm (olsa, olsa_full): prints feature names, weights, bias per contract type sorted by |weight|. Then renders coefficient heatmap for primary arm via `plot_coefficient_heatmap()`.

**Key details:**
- Weight display (L448-467) is useful — sorted by absolute weight, shows sparse 3/1/1 vs full 39 feature contrast
- Coefficient heatmap (L469-494) is low signal: sparse model has 3 features per contract, heatmap is mostly empty cells
- C34 applies: replace heatmap with `statsmodels.OLS` summary tables (coefs, std errors, t-stats, p-values, CIs, R², F-stat)

**Decided §6 fix:** Apply C34 — drop coefficient heatmap, add statsmodels summary tables per arm per contract.

### §7 Model Performance (L498–634)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C35 | Med | Pred vs actual scatter and residual histogram pool all contract types — facet into separate panels. | **FIX** |
| C51 | Med | No error analysis — add top 10 worst mispredictions by |residual| per contract type. | **FIX** |

**What it does:** For primary arm: computes predictions (X @ weights + bias) per contract type, prints per-contract R²/MAE. Charts: pred vs actual scatter (pooled), residual histogram (pooled), bootstrap R²/MAE with CIs.

**Key details:**
- Per-contract metrics (L546-550) are good — prints R² and MAE per contract type
- Scatter and histogram (L557-585) pool all contract types — suit has wider prediction range than high/low, pooling hides structure
- Bootstrap (L588-609) pools all contract types — should also report per-contract CIs
- Fallback (L613-633) renders placeholder charts when no model artifacts — good for CI

**Decided §7 fixes:**
1. **Facet by contract type** (C35): separate scatter + residual panels per contract type
2. **Error analysis** (C51): after scatter/residual, show top 10 deals with largest |residual| per contract — print deal_id, features, predicted, actual, residual

### §7.5 Feature-Outcome Correlations (L636–675)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C38 | Med | Double-prefix bug: `features=numeric_feats` passes `feat_*` names but `plot_feature_outcome_correlation()` re-adds `feat_` at charts.py:685. Same pattern as §1. | **FIX** |
| C15 | Low | Correlation table (L655-673) has no p-values — 30_ S1 has them. | Cross-ref |

**What it does:** Two analyses:
1. **Feature-outcome correlation bar chart** via `plot_feature_outcome_correlation(df, outcome="tricks_won", features=numeric_feats)` — top features by absolute Pearson r (L647-653). **BROKEN**: double-prefix bug (C38).
2. **Per-contract correlation table** (L655-673) — top 10 features by |r| with tricks_won per contract type. Uses `numeric_feats` directly for `grp[fc].corr(grp["tricks_won"])` — this works because `fc` is a valid column name (`feat_*`).

**Key details:**
- Chart call at L650: `features=numeric_feats` where `numeric_feats` has `feat_*` prefix. Function at charts.py:685 does `[f"feat_{f}" for f in features]` → looks for `feat_feat_*` → no matches → renders "No numeric features found"
- If `numeric_feats` is empty (no feat_* columns or non-numeric dtype), the outer guard at L645 fails first → "Insufficient data for feature-outcome correlations"
- Per-contract table at L662-664 uses column names directly (`grp[fc].corr(...)`) so it works correctly regardless of the prefix issue
- Missing p-values (C15) — the table shows r but not significance. 30_ S1 includes p-values via `scipy.stats.pearsonr`.

**Decided §7.5 fix:**
1. **Strip prefix** (C38): `features=[c.removeprefix("feat_") for c in numeric_feats]`
2. **Add diagnostic on guard failure**: print `len(feat_cols)`, `len(numeric_feats)`, sample dtypes when the else branch is reached

### §7.6 Trump Suit Invariance (L677–714)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No issues — solid section | OK |

**What it does:** For suit contracts: hand value by trump suit (boxplot), tricks won by trump suit (boxplot), feature heatmap by suit (mean values). All from diagnostics library.

**Decision: No changes.** Good section — verifies no suit-specific patterns in model behavior. Uses proper diagnostics library calls.

### §7.7 Drift Detection (L716–747)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | No issues — solid section | OK |

**What it does:** Rolling mean of feat_hand_value by deal order. Mann-Whitney U test comparing first 10% vs last 10% of deals. Prints statistic, p-value, and warns if p < 0.05.

**Decision: No changes.** Good section — statistical test included (not just visual), proper MWU test with significance threshold.

### §8 Dual-Arm Comparison (L749–829)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C36 | Med | No metric definitions — net_eppd, eppd, cvar_5, etc. used without glossary. Two metric sources (regression fit vs simulation eval) mixed without explanation. | **FIX** |
| C52 | Med | No contract selection analysis — model's suit/high/low frequency vs heuristic bidders. | **FIX** |

**What it does:** Side-by-side OLSa vs OLSa_Full metrics from eval JSON. Summary table + grouped bar chart with 2 panels (rate metrics, point metrics). Uses METRIC_ALIASES for canonical naming.

**Key details:**
- Bar chart (L766-825) is well structured — separate panels for rate vs point metrics, value labels, legend. This is the reference chart style the user wants replicated in §11 (C48).
- No glossary — reviewer needs to know what net_eppd, eppd, cvar_5, downside_variance mean and where they come from (eval JSON, not notebook-computed)

**Decided §8 fixes:**
1. **Metric glossary** (C36): markdown cell before the chart defining each metric, noting source (simulation eval)
2. **Contract selection comparison** (C52): add table comparing contract type selection frequency between OLSa and OLSa_Full — does the full model choose different contract types?

### §9 Seed Sensitivity (L831–888)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| — | — | Minor: only shows net_eppd across seeds. Could include make_rate and bid_rate for completeness. | OK (stretch) |

**What it does:** Loads eval metrics for seeds 42, 43, 44 per arm. Computes range and CV%. Warns if CV >= 10%.

**Key details:**
- Only tracks `net_expected_points_per_deal` — other metrics (make_rate, bid_rate) not included
- CV threshold of 10% is reasonable — R0 should be well within this
- Good warning system for high seed sensitivity

**Decision: No changes required.** Adequate for R0. Could expand to multiple metrics in future rungs, but net_eppd is the primary decision metric.

### §10 Promotion Summary (L890–956)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C53 | Med | No declaring team win rate by bid value — risk-reward by bid level not shown. | **FIX** |

**What it does:** Attribution gap computation (full - base net_eppd), promotion decision display from JSON, tier 1 checks table, gate results.

**Key details:**
- Attribution gap (L897-922): correctly computed from eval metrics or promotion decision file. Good dual-source with fallback.
- Promotion display (L925-956): loads promotion_decision_r0.json, shows decision, tier 1 checks, gate results. Well structured.
- Missing: risk-reward by bid level (C53) — for each bid value (5-10), what fraction of declaring hands made it and what's the mean points surplus/deficit? This gives the reviewer intuition about the model's bidding aggressiveness.

**Decided §10 fix:** Add C53 — declaring team win rate by bid value chart. Could also live in 25_ (auction health), but it's most relevant here alongside the promotion decision.

### §11 Comparator Battery (L958–1025)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C48 | Med | Only net_eppd shown — comparator JSON has 6 metrics (net_eppd, eppd, bid_rate, make_rate, cvar_5, net_cvar_5) but only net_eppd is extracted and charted. Need full grouped-bar metric comparison like the dual-arm chart (§8). | **FIX** |
| C33 | Low | No OLSaBidder vs HybridOLSaBidder ablation (cross-cutting, future Wave 3+) | Cross-ref |

**What it does:** Loads comparator battery JSON from rung bundle or standalone file, extracts net_eppd per bidder, prints ranked table + horizontal bar chart.

**Key details:**
- Data loading (L966-991): robust — tries bundle key first, then standalone JSON, drills into "bidders" key. Good fallback chain.
- Currently extracts only `net_eppd` (L998): `metrics.get("net_eppd")` — discards 5 other metrics present in `arc_d_comparator_v1` schema (eppd, bid_rate, make_rate, cvar_5, net_cvar_5)
- Horizontal bar chart (L1007-1020): single metric ranking. Highlights OLSa/hybrid in blue (#2196F3), heuristics in grey (#9E9E9E). Good color convention.
- Missing: full metric comparison across all bidders — the dual-arm comparison chart (§8) shows grouped bars for rate metrics and point metrics side-by-side. Same style needed here.

**Decided §11 fixes:**
1. **Full metric extraction** (C48): extract all 6 metrics from comparator JSON, not just net_eppd
2. **Grouped-bar metric comparison** (C48): same 2-panel layout as §8 dual-arm chart:
   - Left panel: rate metrics (bid_rate, make_rate) — grouped bars per bidder, value labels
   - Right panel: point metrics (net_eppd, eppd, cvar_5) — grouped bars per bidder, value labels
   - Color convention: highlight OLSa/hybrid bidders, grey for heuristics
3. **Keep existing net_eppd ranking bar**: useful as a quick summary — the grouped-bar chart adds detail
4. **Full comparison table**: DataFrame with all 6 metrics × all bidders, sorted by net_eppd

---

## Per-Notebook Detail: 50_r0_matchups.py

> Notebook: `notebooks/arc_d/r0/50_r0_matchups.py` (535 lines, 8 sections)
> Status: REVIEWED (structural assessment — no H2H data exists yet)

**Overall assessment:** 50_ is a well-structured placeholder notebook for H2H matchup analysis. The code is correct for its intended data structure (per-matchup JSONL logs with A_vs_B naming convention). However:
1. **No H2H matchup runs exist** — only self-play eval runs and per-bidder comparator runs exist in `data/runs/`
2. **Discovery cell (L74) globs wrong pattern** — `arc_d_eval*` shows eval runs, not matchup runs
3. **Falls back to synthetic demo data** because `MATCHUP_RUN_DIR` is empty
4. **H2H experiment runner doesn't exist yet** — requires new config + runner (TODO in arc_d_execution_plan.md)

| # | Severity | Issue | Status |
|---|----------|-------|--------|
| C50 | Med | H2H matchup battery needed: 7 bidders (HybridOLSa, OLSa, 5 heuristics) × all pairs + self-play = 49 runs. New experiment runner required. | **FIX (infrastructure)** |
| C1 | Med | Dual glob import (cross-cutting) | Cross-ref |
| C2 | Med | MODE fallback missing (cross-cutting) | Cross-ref |
| C7 | Med | No fail-fast validation | Cross-ref |
| C22 | Med | No run metadata summary (cross-cutting) | Cross-ref |
| C31 | Med | Section descriptions missing (cross-cutting) | Cross-ref |

**New analysis sections for 50_ (C50):**
1. **Net_eppd heatmap** — rows = bidder A, cols = bidder B, cells = A's net_eppd against B. Diagonal = self-play. Color gradient red→white→green.
2. **Win rate matrix** — same layout, cells = % of deals where A outscores B. Complementary to net_eppd.
3. **Seat rotation validation** — per pair, compare A_vs_B vs B_vs_A net_eppd. Table + significance test.
4. **Dominance ordering** — pairwise comparison: is there a strict ranking or rock-paper-scissors? Visualize as directed graph.
5. **Bootstrap CIs** — on H2H net_eppd differences per pair.
6. **Auction competition analysis** — how does bid height / contract selection change under competition vs self-play?
7. **Self-play control panel** — diagonal as baseline. Compare against comparator battery (§11) values — should match.
8. **Discovery cell fix** — glob `data/runs/*matchup*` or `data/runs/*h2h*` instead of `arc_d_eval*`

**Existing sections (§0-§7) are structurally sound** for their intended data. Section-by-section review deferred until H2H data exists — the code needs to be tested against real data before detailed review is meaningful.

---

## Meta-Review Addendum

> Added 2026-02-24 after zooming out on the entire review document.
> Addresses 8 systemic findings from the meta-review.

### New Issues (C54–C59)

| ID | Scope | Size | Description | Depends On |
|----|-------|------|-------------|------------|
| C54 | 40_ §10 or 25_ | M | Confusion matrix: bid level × actual tricks won — shows bid accuracy pattern (underbid cluster vs set cluster vs efficient bids). Heat-colored grid, 6 bid levels × 11 trick outcomes. | — |
| C55 | 40_ §3 or §5 | M | Points vs tricks scatter — reveals asymmetric scoring risk. Set penalty creates cluster below diagonal (tricks_won vs points_won). Each dot = one deal, color = contract_type. | C32 |
| C56 | 30_ S6 | M | Permutation feature importance — for each feature in the model, permute values and measure R² drop. Reveals true predictive importance vs raw coefficient magnitude. Per-contract results. | — |
| C57 | 30_ S6 or 40_ | M | Bid decision boundary visualization — for each contract, show feature value ranges where model decides to bid vs pass. Gaussian EV threshold plotted against feature space. | — |
| C58 | 40_ §7.7 | S | Rolling net_eppd drift — extend existing drift detection (hand_value only) with sliding-window net_eppd over deal sequence. Detects non-stationarity in bidder performance. | C32 |
| C59 | all 5 notebooks | S | Prefix-convention sweep — each notebook-owner PR (PR-1..PR-5) audits all `plot_*` calls in its notebook, stripping `feat_` where API expects unprefixed. PR-6 adds a contract test validating no regressions. Companion to C38. | — |

### Updated Summary

| Severity | Count | Notes |
|----------|-------|-------|
| High | 1 | C6 (30_ no fail-fast) |
| Medium | 43 | Includes 6 new issues (C54–C59) |
| Low | 11 | Unchanged |
| Info | 3 | Unchanged |
| **Total** | **58** | **+6 from meta-review** |

**Critical path:** C32 (add `points_won` to `_expand_record()`) is the only issue touching production `src/` code. It blocks C30, C41, C46, C55, C58, and 30_ S1 dual correlation target. Must ship first.

### Dependency DAG

```
Phase 0:  PR-0 (C32 infra + Makefile + runner fix)
              │
Phase 1:  PR-1(10_)  PR-2(20_)  PR-3(30_)  PR-4(40_)  PR-5(50_)
          (each owns its notebook exclusively — zero file overlap)
              │           │          │          │          │
          PR-6 (C59 prefix convention test — depends PR-1..PR-5)
              │
Phase 2:  PR-7 (25_ new + 40_ §2/§4 extraction)
          PR-8 (formal reports — excludes H2H, depends PR-1..PR-7)
```

**Execution order constraints (v2):**
- PR-0 must merge before all Phase 1 PRs (provides `points_won` column).
- Phase 1 PRs (PR-1..PR-5) are independent of each other — zero file overlap, can run in parallel.
- PR-6 depends on PR-1..PR-5 (validates prefix fixes made in those PRs).
- PR-7 depends on PR-4 (extracts §2/§4 content from 40_).
- PR-8 depends on PR-1..PR-7 (formal reports reference notebook outputs from all phases).

### Acceptance Criteria & T-Shirt Sizes

> **S** = 1-10 lines, mechanical fix, <30 min
> **M** = 10-50 lines, new chart/table, 30 min – 2 hr
> **L** = 50+ lines, new section or structural change, 2-4 hr
> **XL** = New notebook or experiment infrastructure, 4+ hr

| ID | Size | Acceptance Criteria |
|----|------|---------------------|
| C1 | S | `import glob as glob_mod` removed from 4 notebooks; discovery cell `_g` is sole glob import. |
| C2 | S | `MODE_DEAL_COUNTS.get(MODE)` in 4 notebooks has fallback with `warnings.warn()` on unknown MODE. |
| C3 | S | `SEED = 42` present in 10_ parameters cell; wired to synthetic fallback RNG. |
| C5 | S | 10_ synthetic creates 10 features (match 30_'s list). |
| C6 | M | 30_ has fail-fast section after data loading with 4 assert-style checks (range, zero-sum, no-missing, feat count). Emulates 20_ S1. |
| C7 | M | 50_ has fail-fast section after data loading. Same 4 checks. |
| C8 | — | Leave as-is (Low, decided). |
| C9 | — | Info, no action. |
| C10 | S | 10_ S4.3 has per-contract ANOVA after violin plot. Prints F-stat + p-value. |
| C11 | S | 40_ §3 team balance table includes Mann-Whitney U p-value per contract type. |
| C12 | M | 30_ has balance/symmetry check section before model analysis (team balance by contract). |
| C13 | S | 10_ S4.5 sorts `seat_mean_vars` with NaN filter: `{k:v for k,v in ... if not np.isnan(v)}`. |
| C14 | — | Low, acknowledged overlap. |
| C15 | S | 10_ S6 and 40_ §7.5 correlation tables include p-values from `scipy.stats.pearsonr()`. |
| C16 | L | 30_ S6 has 4 analyses: Gaussian validation (Shapiro-Wilk + Q-Q), feature selection justification, residual structure (excluded features × residuals), bid decision audit (5-10 traced deals). |
| C17 | — | Info, no action. |
| C18 | S | 10_ S7 companion links updated to `20_outcome_health.py`, `30_feature_outcome_eval.py`, `40_r0_baseline.py`, `50_r0_matchups.py`. |
| C19 | S | `scorecard = None` sentinel before S1 in 10_; `if scorecard is not None:` replaces `"scorecard" in dir()`. |
| C20 | M | Per-strata min-N guard (≥30 deals) in 10_ S4 and 20_ S2/S6. Prints warning for thin strata. |
| C21 | S | 10_ S3 has inline comments labeling structural invariant vs empirical checks. |
| C22 | M | All 5 notebooks have run metadata cell after data loading: bidder name, seed, deal count, date, contract breakdown, run path. |
| C23 | L | Tier 1 (confound removal): bidder_team/bidder_seat distributions + declaring/defending ANOVA splits in 10_ S4.3, 10_ S4.4, 20_ S3, 40_ §3. Tier 2 (analytical insight): declaring/defending overlays in 10_ S5, 10_ S6, 20_ S2, 30_ S1, 40_ §5, 40_ §7.5. |
| C24 | S | 20_ S3 either adds seat balance analysis or renames to "Team Balance". |
| C25 | M | 20_ S4 has second chart: bid distribution stacked by trump suit (suit contracts) + stacked by type (high/low). |
| C26 | S | 20_ S5 has markdown definition of make rate in section header. |
| C27 | M | 20_ S5 has standalone make rate by bid value curve (full size, labeled data points, CI bands). |
| C28 | M | 20_ S5 overbid/underbid histogram faceted by contract type. |
| C29 | M | 20_ S6 has summary table: per contract type, tricks %, mean, median. |
| C30 | M | 20_ S6 has points analysis: declaring/defending points table + CDF/CCDF + expected points by bid value curve. **Depends C32.** |
| C31 | S | 1-2 line markdown description cell added to title-only sections in 10_, 20_, 30_, 50_. 40_ is reference. |
| C32 | M | `_expand_record()` in `eval_dataset.py` computes `points_won` per seat using scoring rules. Tests added. All downstream notebooks can access `points_won` column. **CRITICAL PATH.** |
| C33 | — | Deferred to Wave 3+. |
| C34 | M | 30_ S2 and 40_ §6: coefficient heatmap replaced with `sm.OLS(...).fit().summary()` table per arm × contract. Keep coefficient comparison bar chart. |
| C35 | M | 30_ S3 and 40_ §7: all diagnostic charts (scatter, residual, bootstrap) faceted by contract type into separate panels. Keep pooled view as summary. |
| C36 | S | 30_ S4 and 40_ §8: markdown glossary cell defining all metrics + note on metric sources (regression vs simulation). |
| C37 | M | 30_ S5: prediction distribution faceted by contract type + actual tricks_won overlay. |
| C38 | S | 40_ §1 and §7.5: `features` arg stripped of `feat_` prefix before passing to `plot_feature_distributions()` / `plot_feature_outcome_correlation()`. |
| C39 | M | (Absorbed by C49 → 25_ notebook) Bidder/dealer seat distributions + bid height by dealer seat. |
| C40 | M | (Absorbed by C49 → 25_ notebook) Suit breakout: `pd.crosstab(contract_type, trump)`. |
| C41 | M | 40_ §3 has points_won mean, median, distribution alongside tricks_won. **Depends C32.** |
| C42 | M | (Absorbed by C49 → 25_ notebook) Make rate by bid value chart + surplus distribution histogram. |
| C43 | M | (Absorbed by C49 → 25_ notebook) Seat-faceted bid accuracy stats. |
| C44 | S | 40_ §5 has `plot_cdf(df, ..., group_by="team")` and `group_by="seat"` calls. |
| C45 | M | 40_ §5 has percentage table: `pd.crosstab(contract_type, tricks_won, normalize="index")`. |
| C46 | M | 40_ §5 has points_won CDF + declaring stats. **Depends C32.** |
| C47 | S | 40_ §5 CDF scope labeled explicitly ("all seats" vs "declaring only"). |
| C48 | M | 40_ §11 extracts all 6 metrics; grouped-bar 2-panel chart (rate + point metrics) + full comparison table. |
| C49 | L | New `25_auction_health.py` notebook. Absorbs 40_ §2 + §4 content + C39/C40/C42/C43. ~200 lines. |
| C50 | XL | **DEFERRED.** 50_ H2H matchup battery. Requires new experiment runner + 49 runs (7 bidders). Notebook content: heatmap, win rate matrix, seat rotation, dominance, bootstrap CIs, auction competition, self-play control. Tracked in `plans/arc_d_execution_plan.md` Wave 3+. |
| C51 | M | 40_ §7 has error analysis: top 10 worst mispredictions by |residual| per contract type. Print deal_id, features, predicted, actual, residual. |
| C52 | M | 40_ §8 has contract selection comparison: model suit/high/low frequency vs heuristic bidders. |
| C53 | M | 40_ §10 has declaring win rate by bid value: fraction made + mean points surplus/deficit per bid level (5-10). |
| C54 | M | 40_ §10 or 25_: confusion matrix (bid × actual tricks) as heatmap. |
| C55 | M | 40_ §3 or §5: points vs tricks scatter, color = contract_type. **Depends C32.** |
| C56 | M | 30_ S6: permutation importance — permute each feature, measure R² drop. Per-contract. |
| C57 | M | **DEFERRED.** Bid decision boundary — feature ranges for bid vs pass decision. Lower priority; can be added post-merge. |
| C58 | S | 40_ §7.7: extend drift detection with rolling net_eppd over deal sequence. **Depends C32.** |
| C59 | S | Prefix-convention sweep — each notebook-owner PR (PR-1..PR-5) audits all `plot_*` calls, stripping `feat_` where API expects unprefixed. PR-6 adds contract test. |

### Reference Snippets

> Code patterns for tricky implementations. Copy-paste these to avoid common errors.

**C32 — `points_won` computation in `_expand_record()`:**
```python
from bid_euchre.scoring import compute_points

# Inside _expand_record(), after building the row dict:
# Call once per record, map to per-seat.
pts_t0, pts_t1 = compute_points(winning_bid, bidder_position, t0, t1)
# Per seat: team 0 seats (0, 2) get pts_t0; team 1 seats (1, 3) get pts_t1
points_won = pts_t0 if seat in (0, 2) else pts_t1
row["points_won"] = points_won  # NEVER None
```

**`points_won` semantics (aligned with `compute_points()` in `scoring.py` L10-50):**
- No-bid: `points_won = tricks_won` (L36-38 — both teams get their tricks)
- Made bid: declaring `points_won = tricks_won`, defending `points_won = tricks_won`
- Set bid: declaring `points_won = -winning_bid`, defending `points_won = tricks_won`
- **`points_won` is NEVER None** — `compute_points()` handles all cases including no-bid

**C38/C59 — Prefix strip pattern (from 10_ template L575):**
```python
# CORRECT — strip prefix before passing to diagnostics API
top_9 = df[numeric_feats].var().nlargest(9).index.tolist()
top_9_names = [c.removeprefix("feat_") for c in top_9]
fig = plot_feature_distributions(df, features=top_9_names)

# WRONG — double-prefix bug
fig = plot_feature_distributions(df, features=top_9)  # feat_feat_*
```

**C34 — `statsmodels.OLS` summary (display-only refit):**
```python
import statsmodels.api as sm

# Refit for display — actual bidder uses frozen artifact weights
feat_names = model_artifact["features"]  # e.g., ["hand_value", "trump_count", "bowers"]
X = contract_df[[f"feat_{f}" for f in feat_names]].values
X_const = sm.add_constant(X)
y = contract_df["tricks_won"].values
result = sm.OLS(y, X_const).fit()
print(result.summary(xname=["const"] + feat_names))
# Produces: coefs, std errors, t-stats, p-values, CIs, R², adj R², F-stat
```

**C23 — Declaring vs defending ANOVA split:**
```python
from scipy.stats import f_oneway

for ct in sorted(df["contract_type"].unique()):
    subset = df[df["contract_type"] == ct]
    for role in [True, False]:
        label = "declaring" if role else "defending"
        role_df = subset[subset["is_declaring_team"] == role]
        groups = [role_df.loc[role_df["team"] == t, "feat_hand_value"].dropna().values
                  for t in sorted(role_df["team"].unique())]
        groups = [g for g in groups if len(g) > 0]
        if len(groups) >= 2:
            f_stat, p_val = f_oneway(*groups)
            print(f"  {ct} ({label}): F={f_stat:.3f}, p={p_val:.4f}")
```

**C22 — Run metadata summary block:**
```python
print("=" * 60)
print("RUN METADATA")
print("=" * 60)
print(f"  Data source:    {_data_source}")
print(f"  Run directory:  {EVAL_RUN_DIR or 'N/A (synthetic)'}")
print(f"  Total deals:    {df['deal_id'].nunique():,}")
print(f"  Total rows:     {len(df):,} (4 per deal)")
print(f"  Mode:           {MODE}")
# Parse bidder name from run dir or bundle
if _arm_artifacts:
    print(f"  Arms loaded:    {list(_arm_artifacts.keys())}")
print(f"  Contract types: {dict(df.drop_duplicates('deal_id')['contract_type'].value_counts())}")
```

**C20 — Minimum-N guard:**
```python
MIN_DEALS_PER_STRATUM = 30

deal_counts = df.drop_duplicates(subset=["deal_id"]).groupby("contract_type").size()
thin_strata = deal_counts[deal_counts < MIN_DEALS_PER_STRATUM]
if len(thin_strata) > 0:
    import warnings
    warnings.warn(
        f"Thin strata detected (< {MIN_DEALS_PER_STRATUM} deals): "
        f"{thin_strata.to_dict()}. Sub-group charts may be noisy.",
        stacklevel=2,
    )
```

### Formal Report Targets

> Analyses that should be promoted from embedded notebook output to standalone markdown reports.

| Report | Source | Purpose | When |
|--------|--------|---------|------|
| **R0 Promotion Report** | 40_ §10, 30_ S7 | Formal gate-check summary: all semantic gate results, eval metrics for both arms, attribution gap, promotion decision with rationale. Published to `docs/04_reports/r0/`. | After all Phase 2 fixes land |
| **Model Spec Document** | 30_ S2, 40_ §6 | Frozen reference: OLSa and HybridOLSa R0 parameters — feature lists, per-contract weights, bias terms, sigma models, decision thresholds. Published to `docs/01_core/schemas/`. | After C34 (statsmodels tables) |
| **Comparator Rankings** | 40_ §11 | Formal ranking: all comparator bidders by net_eppd + 5 other metrics, with bootstrap CIs and statistical significance. Published to `docs/04_reports/r0/`. | After C48 (full metrics) |
| **H2H Matchup Report** | 50_ | Formal H2H analysis: heatmaps, dominance ordering, statistical significance of pairwise differences. Published to `docs/04_reports/r0/`. | After C50 (H2H infrastructure) — **DEFERRED** (blocked by C50) |

### C23 Tier Reference Normalization

All per-section C23 references now specify which tier applies:

| Notebook | Section | C23 Tier | What to add |
|----------|---------|----------|-------------|
| 10_ | S4.3 Team Balance | **Tier 1** | Split ANOVA by declaring/defending + bidder_team distribution |
| 10_ | S4.4 Seat Balance | **Tier 1** | Print bidder_seat distribution per contract type |
| 10_ | S5 Feature Distributions | **Tier 2** | Declaring/defending overlay on top features |
| 10_ | S6 Feature-Label Correlations | **Tier 2** | Split heatmap by declaring/defending |
| 20_ | S2 Outcome Distributions | **Tier 2** | Declaring/defending overlay on histograms |
| 20_ | S3 Team & Seat Balance | **Tier 1** | Declaring/defending means alongside Mann-Whitney U |
| 30_ | S1 Feature-Outcome Correlations | **Tier 2** | Split heatmap by declaring/defending |
| 40_ | §3 Gameplay Health | **Tier 1** | Declaring/defending split + stat test |
| 40_ | §5 Gameplay Outcomes | **Tier 2** | Add defending team stats for contrast |
| 40_ | §7.5 Feature-Outcome Correlations | **Tier 2** | Split by declaring/defending |

### Execution Plan Cross-Reference

The full execution plan with PR ordering, per-PR scope, and agent handoff instructions lives at:

**[`plans/r0_notebook_execution_plan.md`](r0_notebook_execution_plan.md)**

### Resolved Alignment Decisions (2026-02-25)

1. **Report output path**: `docs/04_reports/r0/` (was previously under `arc_d`). Preserves continuity with existing `model_arc_r0_20260224.md`.
2. **PR structure**: Notebook-centric streams (9 PRs, not 17). Each notebook owned by exactly one PR per phase. Eliminates same-file merge contention.
3. **`points_won` semantics**: Align with `compute_points()` no-bid behavior (`scoring.py` L36-38). `points_won` is never `None`. No-bid rows use tricks-based scoring.
4. **Issue-to-PR traceability**: Full trace matrix required. Every issue maps to exactly one owner PR per notebook (or is explicitly deferred).
5. **Phase exit gates**: Require Arc D R0 runtime execution (`make notebook-run-arc-d NOTEBOOK="notebooks/arc_d/r0/*.ipynb"`) at every phase closeout. No separate `docs-check` (already included in `make check-quiet`).
6. **PR-6 sequencing**: Prefix-convention test runs after notebook fixes it validates (depends PR-1..PR-5).
7. **PR-8 dependency**: Formal reports depend on Phase 2 completion (PR-1..PR-7). Explicitly excludes H2H Matchup Report (blocked by deferred C50).
8. **C59 ownership**: Audit/fix distributed to notebook-owner PRs (PR-1..PR-5). PR-6 adds contract test only.
