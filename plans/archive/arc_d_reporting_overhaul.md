# Arc D Reporting Overhaul — Plan

> **Date:** 2026-02-23
> **Status:** DRAFT — awaiting review
> **Goal:** Replace the current minimal per-rung reporting with Phase-0-quality notebooks and reports
> **Scope:** 3 notebook templates + report template rewrite + chart infrastructure

---

## Problem Statement

The current Arc D per-rung reporting produces a **38-line markdown file** with no charts, no health checks, no statistical tests, and no interpretive commentary. The Phase 0 report (`phase0_bidless_20260207.md`) demonstrates the standard we want: **522 lines**, 16+ embedded charts, per-contract tables with statistical validation, and human-readable interpretation of every finding.

**Quality gap:**
| Dimension | Phase 0 | Arc D R0 |
|-----------|-----------|---------|
| Report length | 522 lines | 38 lines |
| Charts | 16+ embedded PNGs | 0 |
| Tables | 12+ with per-contract breakdowns | 3 minimal |
| Statistical tests | ANOVA, t-tests, CIs, effect sizes | None |
| Interpretive commentary | Every section | None |
| Notebooks | 3 deep analysis notebooks | 1 monolithic template (766 lines) |

---

## Architecture Decision: 3 Notebooks + 1 Report

### Phase 0 Pattern (proven, to replicate)
```
notebooks/phase0_bidless/
├── 10_feature_health_checks.py    # Feature distributions, seat balance, symmetry
├── 20_outcome_health_checks.py    # Tricks distributions, strategy sanity, CDF/CCDF
└── 30_feature_outcome_eval.py     # Correlations, Ridge regression, feature importance
```

### Arc D Pattern (to build)
```
notebooks/_templates/arc_d/
├── 10_feature_health.py           # Parameterized template (papermill)
├── 20_outcome_health.py           # Parameterized template (papermill)
└── 30_feature_outcome_eval.py     # Standardized base (copy + extend per rung)

notebooks/arc_d/
├── r0/
│   ├── 10_feature_health.py       # Generated from template
│   ├── 20_outcome_health.py       # Generated from template
│   └── 30_feature_outcome_eval.py # Copy of template + R0-specific extensions
├── r1a/                           # Future rung
│   └── ...
```

### Report Output (per PR #416 convention)
```
docs/04_reports/r0/
├── model_arc_r0_20260222.md       # Current (39 lines) → rewrite (~400+ lines)
└── assets/charts/                 # Chart PNGs embedded in report

data/reports/arc_d/                # Working copies (gitignored)
└── r0/                            # Generated before promotion to docs/04_reports/
```

**Convention:** Per `docs/04_reports/README.md`, charts live in `assets/charts/` within
each rung directory. Working copies go to `data/reports/arc_d/` (gitignored); use
`--snapshot` to promote to the committed `docs/04_reports/` path.

---

## Data Source: Eval JSONL

All notebooks use the eval JSONL dataset for the rung, parsed via `build_eval_dataset()` from `src/bid_euchre/datasets/eval_dataset.py`.

**Available columns per row:**
| Column | Type | Description |
|--------|------|-------------|
| `deal_id` | str | Unique deal identifier |
| `seat` | int | 0–3 |
| `team` | int | 0 or 1 |
| `contract_type` | str | "suit", "high", "low" |
| `trump` | str/None | "C","D","H","S" or None |
| `tricks_won` | int | Team tricks (0–10) |
| `winning_bid` | int/None | Bid value |
| `bidder_seat` | int/None | Seat of winning bidder |
| `bidder_team` | int/None | 0 or 1 |
| `made_bid` | bool/None | Whether declaring team made contract |
| `is_bidder` | bool | This seat is the bidder |
| `is_declaring_team` | bool/None | This seat's team declared |
| `n_bids` | int | Number of bids in auction |
| `n_passes` | int | Number of passes in auction |
| `auction_rounds` | int | Total auction actions |
| `feat_*` | float | 39 hand features (feat_hand_value, feat_trump_count, etc.) |
| `hand_id` | str | Alias for deal_id (diagnostics compatibility) |

---

## Notebook 1: Feature Health Checks (Parameterized Template)

**File:** `notebooks/_templates/arc_d/10_feature_health.py`
**Analogue:** `notebooks/phase0_bidless/10_feature_health_checks.py`
**Parameters:** `EVAL_LOG_PATH`, `MODE`, `RUNG_ID`, `CHART_OUTPUT_DIR`
**Estimated length:** ~500 lines

### Sections

#### §0: Configuration & Data Loading
- Papermill parameters: `EVAL_LOG_PATH`, `MODE` (SMOKE/QUICK/FULL), `RUNG_ID`, `CHART_OUTPUT_DIR`
- Load eval JSONL via `build_eval_dataset()`
- Print deal count, row count, contract types, feature count
- MODE controls `max_deals` parameter

#### §1: Health Scorecard
- Use `compute_health_scorecard()` from diagnostics (already supports feat_ prefix)
- Display PASS/WARN/FAIL summary table
- **Chart:** Scorecard status bar (horizontal stacked bar)

#### §2: Dataset Integrity
- Row count validation: expect 4 × n_deals rows
- Schema validation: all 39 `feat_*` columns present
- NaN audit: count NaN per column, flag if > 0
- Duplicate check: no duplicate (deal_id, seat) pairs
- **Table:** Integrity check results with PASS/FAIL per check

#### §3: Strata Completeness
- Contract type distribution: counts per contract_type
- Suit distribution (suit contracts): counts per trump suit
- Seat distribution: counts per seat (should be uniform)
- Team distribution: counts per team (should be uniform)
- **Chart:** Stacked bar chart of deal counts by contract_type × trump
- **Table:** Strata count table with expected vs actual

#### §4: Symmetry Analysis

**§4.1: By Contract Type**
- Hand value distributions per contract type
- **Chart:** Violin + boxplot of `feat_hand_value` by contract_type
- **Table:** Summary statistics (N, mean, std, P25, P50, P75) per contract type

**§4.2: By Trump Suit (suit contracts only)**
- Hand value invariance across C/D/H/S
- ANOVA test: H₀ = hand_value means equal across suits
- **Chart:** Boxplot of `feat_hand_value` by trump suit
- **Table:** Per-suit statistics + ANOVA F-stat and p-value
- **Pass criterion:** ANOVA p > 0.05 (no suit bias)

**§4.3: By Team**
- Hand value distributions by team (0 vs 1)
- **Chart:** Violin + boxplot by team, faceted by contract_type
- **Table:** Team balance summary (mean delta, max deviation)

**§4.4: By Seat**
- Hand value distributions across 4 seats
- **Chart:** Grouped boxplot — seats × contract_types (like Phase 0 seat balance chart)
- **Table:** Per-seat statistics with ANOVA p-value
- **Pass criterion:** |mean deviation| < 0.25 across seats

**§4.5: Feature-Level Symmetry**
- Top 5 features by variance: check symmetry across seats
- **Chart:** Heatmap of feature means by seat (Z-score normalized)

#### §5: Feature Distributions
- Top N features by variance per contract type
- **Chart:** 3×3 grid of feature distribution histograms (top 9 features)
- **Chart:** Feature correlation matrix heatmap (top 15 features)
- **Table:** Feature summary statistics (mean, std, min, max per contract)

#### §6: Feature-Label Relationships
- Pearson correlation of each feature with tricks_won, per contract type
- **Chart:** Heatmap of feature × contract_type correlations
- **Chart:** Scatter plots of top 3 features vs tricks_won (per contract)
- **Table:** Top 10 features by |correlation| per contract type (like Phase 0 §6d)

#### §7: Summary
- Pass/fail summary table
- Key findings in bullet points
- Link to companion notebooks

**Charts produced (saved to CHART_OUTPUT_DIR):**
1. `health_scorecard.png`
2. `strata_completeness.png`
3. `hand_value_by_contract.png`
4. `hand_value_by_trump.png`
5. `hand_value_by_team.png`
6. `seat_balance_boxplot.png`
7. `feature_symmetry_heatmap.png`
8. `feature_distributions.png`
9. `feature_correlation_matrix.png`
10. `feature_outcome_heatmap.png`
11. `feature_vs_tricks_scatter.png`

---

## Notebook 2: Outcome Health Checks (Parameterized Template)

**File:** `notebooks/_templates/arc_d/20_outcome_health.py`
**Analogue:** `notebooks/phase0_bidless/20_outcome_health_checks.py`
**Parameters:** `EVAL_LOG_PATH`, `MODE`, `RUNG_ID`, `CHART_OUTPUT_DIR`
**Estimated length:** ~450 lines

### Sections

#### §0: Configuration & Data Loading
- Same parameter pattern as notebook 1
- Load eval JSONL, build deal-level frame (1 row per deal)

#### §1: Fail-Fast Validation
- Assert `tricks_won` in [0, 10]
- Assert team0_tricks + team1_tricks = 10
- Assert no missing contract_type
- Assert no missing tricks_won
- **Table:** Validation results (check, expected, actual, status)

#### §2: Outcome Distributions by Contract Type
- Tricks_won distributions per contract
- **Chart:** Histogram grid — tricks_won by contract_type (3 panels)
- **Chart:** Violin + boxplot of tricks_won by contract_type
- **Table:** Per-contract summary (N deals, mean, std, P5, P25, P50, P75, P95)

#### §3: Team & Seat Balance
- Team tricks balance: mean(team0_tricks) vs mean(team1_tricks)
- Seat-level tricks balance
- **Chart:** Grouped boxplot of tricks_won by team × contract_type
- **Table:** Team balance table with delta and significance test
- **Pass criterion:** |team_delta| < 0.25 per contract type

#### §4: Auction Health (Arc D-specific — no Phase 0 analogue)
- Contract selection frequency (how often each contract type was chosen by the bidder)
- Bid value distribution (histogram of winning_bid values)
- Pass rate analysis (n_passes vs n_bids ratio)
- Auction length distribution (auction_rounds)
- **Chart:** Bar chart of contract selection frequency
- **Chart:** Histogram of winning bid values, faceted by contract_type
- **Chart:** Auction length distribution (histogram)
- **Table:** Auction summary table (per-contract: mean_bid, median_bid, pass_rate, mean_rounds)

#### §5: Bidder Performance
- Make rate by contract type (fraction of deals where made_bid=True)
- Make rate by bid value (accuracy curve: higher bids → lower make rate)
- Overbid/underbid analysis: bid_value - tricks_won distribution
- **Chart:** Make rate bar chart by contract_type
- **Chart:** Make rate curve by bid_value (line chart with CI bands)
- **Chart:** Overbid/underbid histogram (bid - tricks_won)
- **Table:** Per-contract make rate with 95% binomial CI

#### §6: Distribution Analysis (CDF/CCDF)
- CDF of tricks_won per contract type
- CCDF (complementary) for tail analysis
- **Chart:** CDF curves by contract_type (overlay)
- **Chart:** CCDF curves by contract_type (overlay)

#### §7: Summary
- Pass/fail gates table
- Key findings
- Flags for human review

**Charts produced:**
1. `tricks_won_histogram.png`
2. `tricks_won_violin.png`
3. `team_balance_boxplot.png`
4. `contract_selection.png`
5. `bid_distribution.png`
6. `auction_length.png`
7. `make_rate_by_contract.png`
8. `make_rate_by_bid.png`
9. `overbid_underbid.png`
10. `cdf_by_contract.png`
11. `ccdf_by_contract.png`

---

## Notebook 3: Feature-Outcome Evaluation (Standardized + Extensible)

**File:** `notebooks/_templates/arc_d/30_feature_outcome_eval.py`
**Analogue:** `notebooks/phase0_bidless/30_feature_outcome_eval.py`
**Parameters:** `EVAL_LOG_PATH`, `ARTIFACT_DIR`, `MODE`, `RUNG_ID`, `CHART_OUTPUT_DIR`
**Estimated length:** ~700 lines (base template)

This template is **copied** per rung (not parameterized), allowing rung-specific extensions to §6.

### Sections

#### §0: Configuration & Data Loading
- Parameters: eval log path, artifact directory (for model weights), rung ID
- Load eval JSONL via `build_eval_dataset()`
- Load model artifacts (OLSa + OLSa_Full coefficients) from artifact dir
- Load rung bundle JSON for metadata

#### §1: Feature-Outcome Correlations
- Per-contract Pearson correlation of each feat_* with tricks_won
- **Chart:** Heatmap of feature × contract_type correlations (like Phase 0 §6d but for actual model features)
- **Chart:** Top 5 features by |r| per contract — grouped bar chart
- **Table:** Full correlation table per contract (feature, Pearson r, p-value, significance)

#### §2: Model Specification
- Feature selection per arm per contract type
- Model coefficients per arm per contract type
- **Chart:** Coefficient heatmap (features × contracts, color = coefficient sign/magnitude) — primary arm
- **Chart:** Coefficient comparison bar chart (OLSa vs OLSa_Full side by side)
- **Table:** Full coefficient table per arm per contract (like Phase 0 §6c but with both arms)
- **Interpretive commentary:** What the coefficients mean for bidding — which features drive higher/lower bid predictions

#### §3: Model Performance Diagnostics
- Compute predictions from model weights on eval data
- **Chart:** Predicted vs actual scatter — per contract type (2×2 or 1×3 grid)
  - Include y=x reference line, R² annotation, regression line
- **Chart:** Residual distribution histograms — per contract type
  - Include normal overlay, mean/std annotation
- **Chart:** Residuals vs predicted — heteroscedasticity check
  - Include horizontal line at 0, LOWESS smoother
- **Chart:** Bootstrap R² distribution (histogram with CI bars)
- **Table:** Per-contract performance (R², R² 95% CI, MAE, MAE 95% CI, N)
  - Computed via bootstrap (1000 resamples in FULL mode, 100 in QUICK, skip in SMOKE)
- **Table:** Residual summary per contract (mean residual, std, P5, P95, max |residual|)

#### §4: Dual-Arm Comparison
- OLSa (constrained) vs OLSa_Full (promotional) side-by-side
- **Chart:** Grouped bar chart of key metrics by arm (bid_rate, make_rate, net_eppd, eppd, cvar_5)
- **Chart:** Per-contract R² comparison (OLSa vs OLSa_Full, grouped bars)
- **Table:** Arm comparison table (all metrics, per contract where applicable)
- **Attribution gap analysis:** net_eppd(Full) - net_eppd(constrained)
  - Interpretation: positive = Full outperforms; negative = constrained outperforms (investigate)

#### §5: Calibration Analysis
- Prediction calibration: group predictions into bins, compare mean prediction vs mean actual
- **Chart:** Calibration curve (predicted vs actual means per bin) — per contract
- **Chart:** Prediction distribution by contract type (histogram of model outputs)
- **Table:** Calibration bins table (bin range, N, mean_predicted, mean_actual, deviation)
- For bidder-only rows: bid_value vs predicted tricks — how well does the bid track the model?

#### §6: Rung-Specific Extensions (PLACEHOLDER)
```python
# ============================================================
# §6: RUNG-SPECIFIC ANALYSIS
# ============================================================
# This section is intentionally left as a placeholder.
# When copying this template for a specific rung (e.g., R0, R1a),
# add rung-specific analysis here:
#
# Examples for R0:
#   - Compare OLSa predictions to Phase 0 Ridge diagnostic
#   - Feature selection justification (why these 3/1/1 features?)
#
# Examples for R1a+:
#   - Auction dataset quality checks
#   - Comparison with previous rung's model
#   - Feature stability analysis across rungs
#   - Progressive improvement visualization
```

#### §7: Summary & Promotion Readiness
- Overall assessment combining feature health, outcome health, and model diagnostics
- Gate check summary table (from semantic gate)
- Promotion recommendation with evidence
- **Table:** Gate results (check_id, category, status, threshold, observed)
- Key limitations and open questions

**Charts produced:**
1. `feature_outcome_heatmap.png`
2. `top_features_by_correlation.png`
3. `coefficient_heatmap.png`
4. `coefficient_comparison.png`
5. `pred_vs_actual_scatter.png`
6. `residual_distribution.png`
7. `residual_vs_predicted.png`
8. `bootstrap_r2.png`
9. `dual_arm_comparison.png`
10. `per_contract_r2_comparison.png`
11. `calibration_curve.png`
12. `prediction_distribution.png`

---

## Report Template Rewrite

**File:** `src/bid_euchre/reporting/arc_d_report.py` (rewrite `generate_arc_d_rung_report()`)
**Target length:** ~400–500 lines of generated markdown
**Required charts:** 8–10 most important from the notebooks

### Report Structure

#### §1: Executive Summary
- Rung ID, arc type, date, deal count
- Gate status (PROMOTED/ADVANCED/HALT) with color indicator
- Key metrics: net_eppd per arm, attribution gap, R² per contract
- One-line assessment of each health dimension (feature, outcome, model)
- Chart count and notebook reference

#### §2: Data Inventory
- Eval dataset provenance (log path, deal count, schema version)
- Per-seat row count, contract type distribution
- **Table:** Data summary (contract_type, N_deals, N_seat_rows, trump_distribution)
- Reproduction command for eval dataset

#### §3: Feature Health Summary
- Seat balance check results with quantitative thresholds
- Trump-suit invariance check (ANOVA p-value)
- **Chart:** `seat_balance_boxplot.png` (from notebook 1)
- **Chart:** `hand_value_by_contract.png` (from notebook 1)
- **Table:** Seat balance summary (per-contract mean deviation)

#### §4: Outcome Health Summary
- Tricks distribution summary
- Team balance check results
- **Chart:** `tricks_won_histogram.png` (from notebook 2)
- **Chart:** `cdf_by_contract.png` (from notebook 2)
- **Table:** Per-contract outcome statistics (mean, std, P5, P95)

#### §5: Auction Analysis
- Contract selection frequency
- Bid distribution summary
- Make rate by contract
- **Chart:** `make_rate_by_contract.png` (from notebook 2)
- **Table:** Auction summary (per-contract bid mean, make rate, pass rate)

#### §6: Model Specification & Feature Selection
- Per-arm, per-contract feature lists with coefficient values
- Feature selection rationale (for constrained arm)
- **Chart:** `coefficient_heatmap.png` (from notebook 3)
- **Table:** Coefficient table per arm (like Phase 0 §6c format)

#### §7: Model Performance
- Per-contract R², MAE with bootstrap CIs
- **Chart:** `pred_vs_actual_scatter.png` (from notebook 3)
- **Chart:** `residual_distribution.png` (from notebook 3)
- **Table:** Performance metrics table (contract, R², R² CI, MAE, MAE CI, N)

#### §8: Dual-Arm Comparison & Attribution Gap
- OLSa vs OLSa_Full metrics comparison
- Attribution gap with interpretation
- **Chart:** `dual_arm_comparison.png` (from notebook 3)
- **Table:** Arm comparison (net_eppd, eppd, bid_rate, make_rate per arm)

#### §9: Semantic Gate Summary
- All gate checks in table format
- Tier 1 (health) and Tier 2 (quality) results
- **Table:** Full gate results table

#### §10: Known Limitations
- Documented caveats, open questions, areas for investigation

#### §11: Reproduction Commands
- Eval dataset generation
- Notebook execution commands
- Chart generation
- Report generation
- Full validation

**Charts embedded in report (8–10 total, subset of notebook outputs):**
1. `seat_balance_boxplot.png`
2. `hand_value_by_contract.png`
3. `tricks_won_histogram.png`
4. `cdf_by_contract.png`
5. `make_rate_by_contract.png`
6. `coefficient_heatmap.png`
7. `pred_vs_actual_scatter.png`
8. `residual_distribution.png`
9. `dual_arm_comparison.png`

---

## Incorporating Already-Completed Rungs

### R0 Artifact Inventory

R0 is fully promoted with frozen artifacts. All data lives under `data/artifacts/arc_d/r0/`:

| Artifact | File | Contents |
|----------|------|----------|
| **Rung bundle** | `rung_bundle_r0.json` | Central manifest: artifact paths, features, eval seeds |
| **OLSa model** | `hybrid_r0.json` | Constrained arm (high:1, low:1, suit:3), SHA `7b523cd6` |
| **OLSa_Full model** | `hybrid_r0_full.json` | Promotional arm (high:2, low:2, suit:3), SHA `5436b759` |
| **Promotion decision** | `promotion_decision_r0.json` | PROMOTED, all tier-1 checks PASS, attribution gap = -0.1437 |
| **Comparator battery** | `comparator_battery_r0.json` | 5 bidders ranked by net_eppd, gate_status = PASS |
| **Training report** | `training_report_r0.json` | Training dataset ref, split details |
| **Feature selection** | `feature_selection_log_r0_full.json` | Forward selection log for OLSa_Full |
| **Split manifests** | `split_manifest_r0_{suit,high,low}.json` | Deterministic train/val/test hand_id maps |

**Eval summary JSONs** (aggregate metrics, NOT game logs):
- `eval_r0.json` / `eval_r0_s43.json` / `eval_r0_s44.json` — OLSa arm, seeds 42/43/44
- `eval_r0_full.json` / `eval_r0_full_s43.json` / `eval_r0_full_s44.json` — OLSa_Full arm

**Eval configs** (for regenerating game logs):
- `experiments/configs/arc_d_eval_r0.yaml` — OLSa arm (50K deals)
- `experiments/configs/arc_d_eval_r0_full.yaml` — OLSa_Full arm (50K deals)
- `experiments/configs/arc_d_eval_r0_diagnostic.yaml` — Head-to-head R0 vs Full

### JSONL Game Logs (Verified Present)

The notebooks use `build_eval_dataset()` which reads `*.jsonl` game logs containing `hand_end` records with per-seat features. The eval summary JSONs (`eval_r0.json` etc.) contain aggregate metrics and per-deal point arrays but **NOT** per-seat features.

**JSONL game log path pattern** (from `experiments/run_experiment.py`):
```
data/runs/<run_id>/logs/<run_id>_<strategy>.jsonl
```

**All 7 R0 eval game logs exist locally** (verified 2026-02-23):

| Arm | Seed | JSONL Path |
|-----|------|-----------|
| OLSa | 42 | `data/runs/arc_d_eval_r0_42_20260221_180253/logs/arc_d_eval_r0_42_20260221_180253_hybrid_olsa_r0.jsonl` |
| OLSa | 43 | `data/runs/arc_d_eval_r0_43_20260221_180412/logs/arc_d_eval_r0_43_20260221_180412_hybrid_olsa_r0.jsonl` |
| OLSa | 44 | `data/runs/arc_d_eval_r0_44_20260221_180531/logs/arc_d_eval_r0_44_20260221_180531_hybrid_olsa_r0.jsonl` |
| OLSa_Full | 42 | `data/runs/arc_d_eval_r0_full_42_20260221_175607/logs/arc_d_eval_r0_full_42_20260221_175607_hybrid_olsa_r0_full.jsonl` |
| OLSa_Full | 42 | `data/runs/arc_d_eval_r0_full_42_20260221_180650/logs/arc_d_eval_r0_full_42_20260221_180650_hybrid_olsa_r0_full.jsonl` |
| OLSa_Full | 43 | `data/runs/arc_d_eval_r0_full_43_20260221_180807/logs/arc_d_eval_r0_full_43_20260221_180807_hybrid_olsa_r0_full.jsonl` |
| OLSa_Full | 44 | `data/runs/arc_d_eval_r0_full_44_20260221_180923/logs/arc_d_eval_r0_full_44_20260221_180923_hybrid_olsa_r0_full.jsonl` |

If logs are ever lost, regenerate deterministically:
```bash
# All 6 seed × arm combinations:
for seed in 42 43 44; do
  uv run python experiments/run_experiment.py \
    --config experiments/configs/arc_d_eval_r0.yaml --seed $seed
  uv run python experiments/run_experiment.py \
    --config experiments/configs/arc_d_eval_r0_full.yaml --seed $seed
done
```

**Recommended utility** (Wave 1): Add `resolve_eval_log_from_bundle(bundle_path, arm, seed)` to eliminate manual log-path handling. Uses deterministic lookup: `bundle[arm]["eval_seed{seed}"]` → eval JSON → `run_id` + `source_logs[0]` → JSONL path. This avoids the two-OLSa_Full-seed-42-log ambiguity (two runs exist at lines 501-502 above).

### Comparator Battery Integration

The comparator battery (`comparator_battery_r0.json`) provides a competitive landscape view:

| Bidder | net_eppd | eppd | bid_rate | make_rate |
|--------|----------|------|----------|-----------|
| hybrid_olsa (R0) | ~1.48 | — | — | — |
| fiveheadfred | — | — | — | — |
| stricthellraiser | — | — | — | — |
| rankthetank | — | — | — | — |
| modeloespecifico | — | — | — | — |

*(Exact values from `comparator_battery_r0.json`; 5 bidders × 10K deals each)*

**Where comparator data appears:**
1. **Notebook 2 (Outcome Health), new §4.5:** Comparator landscape chart — bar chart ranking all bidders by net_eppd with the rung's model highlighted
2. **Notebook 3 (Feature-Outcome Eval), §4:** Extend dual-arm comparison to include comparator baselines for context
3. **Report §8:** Add comparator leaderboard table and bar chart to dual-arm section

### R0-Specific §6 Content (Notebook 3)

When the `30_feature_outcome_eval.py` template is copied for R0, the §6 placeholder gets filled with:

```
§6: R0-Specific Analysis
├── 6.1: Phase 0 Comparison
│   - Compare OLSa R² per contract to Phase 0 Ridge R² (0.19–0.24)
│   - Table: Phase 0 Ridge vs R0 OLSa vs R0 OLSa_Full performance
│   - Chart: Side-by-side R² bar chart (Phase 0 Ridge vs R0 arms)
│
├── 6.2: Feature Selection Justification
│   - Why 3/1/1 for constrained arm? (from forward selection log)
│   - Feature selection path visualization from feature_selection_log_r0_full.json
│   - Chart: Feature selection path (cumulative R² vs features added)
│
├── 6.3: Comparator Landscape
│   - R0 model vs 4 heuristic bidders (from comparator_battery_r0.json)
│   - Chart: Net EPPD leaderboard bar chart
│   - Table: Full comparator metrics
│   - Interpretation: How much does OLSa improve over hand-crafted heuristics?
│
├── 6.4: Attribution Gap Investigation
│   - Gap = -0.1437 (constrained outperforms full — unexpected)
│   - Hypothesis analysis: overfitting? Feature redundancy? Contract-specific?
│   - Chart: Per-contract attribution gap breakdown
│   - Table: Per-contract net_eppd for each arm
│
└── 6.5: Seed Sensitivity
    - R0 evaluated across seeds 42/43/44 for both arms
    - Chart: Metric stability across seeds (3-point line chart)
    - Table: Per-seed metrics with CV%
```

### Future Rungs: Template Reuse Pattern

For R1a and beyond:
```
notebooks/arc_d/
├── r0/
│   └── 30_feature_outcome_eval.py   # §6 = Phase 0 comparison + comparator + attribution gap
├── r1a/
│   └── 30_feature_outcome_eval.py   # §6 = Auction dataset quality + R0→R1a progression
├── r5a/
│   └── 30_feature_outcome_eval.py   # §6 = Off/def sub-model analysis + R0→R5a lift
```

Notebooks 1 and 2 are **parameterized** — same template, just pass different `EVAL_LOG_PATH` and `RUNG_ID`. No per-rung copies needed.

---

## Chart Infrastructure

### Existing (reusable from `reporting/charts.py`)
- `generate_feature_health_charts()` — seat balance, hand value, feature distributions, correlations
- `generate_feature_outcome_charts()` — correlations, scatter plots, outcome distributions
- `generate_distribution_charts()` — CDF/CCDF
- `generate_contract_faceted_charts()` — trump invariance, feature heatmaps

### New Charts Needed
| Chart | Location | Description |
|-------|----------|-------------|
| `plot_auction_health()` | `diagnostics/auction_charts.py` (NEW) | Bid distribution, contract selection, auction length |
| `plot_bidder_performance()` | `diagnostics/auction_charts.py` (NEW) | Make rate curves, overbid/underbid |
| `plot_model_diagnostics()` | `diagnostics/model_charts.py` (NEW) | Pred vs actual, residuals, bootstrap R² |
| `plot_dual_arm_comparison()` | `diagnostics/model_charts.py` (NEW) | Arm metric bars, R² comparison |
| `plot_calibration_curve()` | `diagnostics/model_charts.py` (NEW) | Calibration analysis |

### Refactored (move inline code to reusable functions)
The existing `01_model_rung_template.py` has inline matplotlib code for some of these. Extract into diagnostic modules for reuse across notebooks and report generation.

---

## Implementation Phasing

### Wave 1: Chart Infrastructure + Log Resolver (1 PR)
**PR-C1:** New chart modules + eval log utility
- Create `src/bid_euchre/diagnostics/auction_charts.py` — auction health + bidder performance charts
- Create `src/bid_euchre/diagnostics/model_charts.py` — model diagnostics + dual-arm + calibration charts
- Add `resolve_eval_log_from_bundle(bundle_path, arm, seed)` to `src/bid_euchre/datasets/eval_dataset.py`
  - **Lookup path (deterministic, no path search):**
    1. Read rung bundle JSON → `bundle[arm]["eval_seed{seed}"]` → eval JSON path (e.g., `data/artifacts/arc_d/r0/eval_r0_full.json`)
    2. Read eval JSON → `run_id` field (e.g., `"arc_d_eval_r0_full_42_20260221_180650"`)
    3. Read eval JSON → `source_logs[0]` field (e.g., `"logs/arc_d_eval_r0_full_42_...jsonl"`)
    4. Construct: `data/runs/{run_id}/{source_logs[0]}` → absolute JSONL path
  - This avoids the two-OLSa_Full-seed-42-log ambiguity (lines 501-502) by using the eval JSON as canonical source of truth
  - Raises `FileNotFoundError` with clear message if eval JSON or JSONL log is missing
- Tests for each chart function (input validation, output file existence)
- Tests for log resolver (valid bundle → correct path, missing log → clear error, two-run tie-break uses eval JSON)
- ~8–10 new chart functions + 1 utility function

### Wave 2: Notebook Templates (3 PRs)

> **Jupytext pairing:** Each Wave 2 PR must include Jupytext sync within the PR itself
> (moved from Wave 5 to eliminate the testability gap — SMOKE-mode papermill execution
> requires `.ipynb` files, which are generated from `.py` via `jupytext --sync`).
> Each PR includes: Jupytext header in `.py` file → `jupytext --sync` → commit paired `.ipynb`.

**PR-N1:** Feature health template
- `notebooks/_templates/arc_d/10_feature_health.py` (with Jupytext header)
- Jupytext sync: generate paired `.ipynb` before committing
- Parameterized via papermill
- All §0–§7 sections as described above
- Test: SMOKE mode execution passes (requires `.ipynb` from Jupytext sync)

**PR-N2:** Outcome health template
- `notebooks/_templates/arc_d/20_outcome_health.py` (with Jupytext header)
- Jupytext sync: generate paired `.ipynb` before committing
- Parameterized via papermill
- All §0–§7 sections including auction-specific analysis
- Test: SMOKE mode execution passes (requires `.ipynb` from Jupytext sync)

**PR-N3:** Feature-outcome eval template
- `notebooks/_templates/arc_d/30_feature_outcome_eval.py` (with Jupytext header)
- Jupytext sync: generate paired `.ipynb` before committing
- Standardized base with §6 placeholder
- Full model diagnostics in §3
- Test: SMOKE mode with synthetic data passes (requires `.ipynb` from Jupytext sync)

### Wave 3: Report Template Rewrite (1 PR)
**PR-R1:** Overhaul `arc_d_report.py`
- Rewrite `generate_arc_d_rung_report()` to produce §1–§11 as described
- Embed chart references from notebook output directories
- Generate interpretive commentary from data
- Test: verify generated report structure, chart references, table formatting

### Wave 4: R0 Instantiation & Validation (1 PR)
**PR-V1:** Generate R0 notebooks and report from real data

Pre-requisite: All 7 R0 eval JSONL logs verified present (see "JSONL Game Logs" section).
Seed 42 is primary; seeds 43/44 required for §6.5 seed sensitivity analysis.
If logs are ever missing, regenerate all 6 seed × arm combinations:
```bash
for seed in 42 43 44; do
  uv run python experiments/run_experiment.py \
    --config experiments/configs/arc_d_eval_r0.yaml --seed $seed
  uv run python experiments/run_experiment.py \
    --config experiments/configs/arc_d_eval_r0_full.yaml --seed $seed
done
```

Deliverables:
- Run notebooks 1 & 2 via papermill with R0 eval log path and `RUNG_ID=r0`
- Copy `30_feature_outcome_eval.py` template → `notebooks/arc_d/r0/30_feature_outcome_eval.py`
- Fill R0-specific §6 content:
  - §6.1: Phase 0 Ridge R² comparison (greedy R² 0.20–0.23, glutton 0.19–0.24 from r5 report)
  - §6.2: Feature selection justification from `feature_selection_log_r0_full.json`
  - §6.3: Comparator landscape from `comparator_battery_r0.json` (5 bidders)
  - §6.4: Attribution gap investigation (gap = -0.1437, constrained > full)
  - §6.5: Seed sensitivity from 3-seed eval data (seeds 42/43/44)
- Generate updated R0 report: `docs/04_reports/r0/model_arc_r0_20260222.md` → ~400+ lines
- Embed R0 charts in `docs/04_reports/r0/assets/charts/` (per README.md convention)
- Validate: report length ≥ 300 lines, ≥ 8 charts, ≥ 8 tables, statistical tests present

### Wave 5: Template Integration & Cleanup (1 PR)
**PR-I1:** Integration

Jupytext pairing:
- ~~Moved to Wave 2~~ — each Wave 2 PR now includes its own Jupytext sync
- Wave 5 only handles: verify `make notebook-check` passes end-to-end

Makefile + recursive glob fix:
- Current `notebook-run-arc-d` target uses pattern `notebooks/arc_d/*.ipynb`
- New notebooks live at `notebooks/arc_d/r0/*.ipynb` (one level deeper)
- Update `notebook-run-arc-d` default pattern to `notebooks/arc_d/**/*.ipynb`
- Add `notebook-run-arc-d-templates` target for SMOKE-mode template validation
- **Fix `discover_notebooks()` recursive glob** (`scripts/run_notebooks.py:59`):
  `glob.glob(str(repo_root / pattern))` must pass `recursive=True` when pattern
  contains `**`, otherwise `**` silently matches nothing. Fix:
  ```python
  all_notebooks = sorted(glob.glob(str(repo_root / pattern), recursive=True))
  ```
  This is a prerequisite for the `notebooks/arc_d/**/*.ipynb` pattern to work.

Test contract migration (see "Test Migration Scope" section below):
- Update `test_notebook_template_contract.py` required sections and parameters
- Update `test_arc_d_reporting.py` report heading assertions

Additional deliverables:
- Deprecate old `01_model_rung_template.py` (move to `notebooks/_templates/archive/`)
  - **Reference update checklist** (all consumers of old template path):
    - `src/bid_euchre/reporting/report_template.py:132` — reproduction command references old `.ipynb` path
    - `tests/unit/test_notebook_template_contract.py:13` — `TEMPLATE_PATH` constant
    - `docs/02_agent/PROMOTION_WORKFLOW.md:116` — doc reference
    - `plans/arc_d_execution_plan.md:1747` — `cp` command (plan doc, not code — optional update)
  - Each reference must be updated to point to the new 3-notebook structure or removed
- Regenerate cross-rung dashboard: `scripts/internal/generate_arc_dashboard.py --snapshot`
- Update CLAUDE.md and docs with new workflow
- Add quality bar contract test (automated report validation)
- End-to-end validation: `make check` passes

**Total: 7 PRs across 5 waves**

---

## Test Migration Scope

The structural rewrite changes notebook section names, parameter lists, and report headings.
Existing tests hard-code these contracts and must be updated.

### `tests/unit/test_notebook_template_contract.py`

**Current assertions (to update):**
- `REQUIRED_PARAMETERS`: `["MODE", "SEED", "EVAL_RUN_DIR", "ARTIFACT_DIR", "RUNG_ID", "CHART_OUTPUT_DIR", "PROMOTION_DECISION_PATH"]`
- `REQUIRED_SECTIONS`: `["§0 Setup", "§1 Deal Health", "§2 Auction Health", ..., "§10 Promotion"]` (11 sections)
- `REQUIRED_CHART_FILENAMES`: `["seat_balance_boxplot.png", "pred_vs_actual_scatter.png", "residual_distribution.png", "dual_arm_comparison.png"]`
- R0-specific: asserts `§11 Comparator Battery` section, `compute_health_scorecard` import, `.mannwhitney_stat`/`.mannwhitney_pvalue` usage
- R0 matchup notebook: asserts `_r0_team()`, `_r0_sign()` helpers, 8 required sections

**Migration plan:**
| What | Old | New | PR |
|------|-----|-----|-----|
| Template parameters | 7 params for monolithic template | Notebook 1: `EVAL_LOG_PATH, MODE, RUNG_ID, CHART_OUTPUT_DIR`; Notebook 3: adds `ARTIFACT_DIR` | PR-N1, PR-N3 |
| Template sections | 11 sections (§0–§10) | 3 notebooks × 7 sections each | PR-N1, PR-N2, PR-N3 |
| Chart filenames | 4 required | Updated per notebook (see chart lists above) | PR-N1, PR-N2, PR-N3 |
| R0 enrichment | `§11 Comparator Battery` in monolithic | §6.3 in `30_feature_outcome_eval.py` R0 copy | PR-V1 |
| R0 matchup notebook | `03_r0_matchups.py` (unchanged) | Keep as-is; not part of this rewrite | — |

### `tests/unit/test_arc_d_reporting.py`

**Current assertions (to update):**
- Lines 294–306: `"# ARC_D Rung R0 Report"`, `"## Dual-Arm Comparison"`, `"## Feature Selection"`, `"## Attribution Gap"`
- Lines 527–539: `"## Executive Summary"`, `"## Data Provenance"`, `"## Deal Health"`, `"## Auction Analysis"`, `"## Gameplay Analysis"`, `"## Reproducibility"`

**Migration plan:**
- Update heading assertions to match new report structure (§1–§11 headings from Report Template section)
- Add assertions for new sections: `"## Feature Health Summary"`, `"## Outcome Health Summary"`, `"## Model Performance"`, `"## Semantic Gate Summary"`
- Update metric formatting tests if table structure changes
- Deliver in **PR-R1** (Wave 3)

### New: Quality Bar Contract Test

Add `tests/unit/test_report_quality_bar.py` (deliver in **PR-I1**, Wave 5):
```python
def test_generated_report_meets_quality_bar(generated_report_text):
    """Verify generated report meets minimum quality standards."""
    lines = generated_report_text.strip().split("\n")
    assert len(lines) >= 300, f"Report too short: {len(lines)} lines"

    chart_refs = [l for l in lines if "![" in l and ".png" in l]
    assert len(chart_refs) >= 8, f"Too few charts: {len(chart_refs)}"

    table_headers = [l for l in lines if l.startswith("|") and "---" not in l]
    assert len(table_headers) >= 8, f"Too few table rows: {len(table_headers)}"

    # At least 3 statistical test references
    stat_keywords = ["p-value", "p =", "ANOVA", "bootstrap", "95% CI", "confidence interval"]
    stat_lines = [l for l in lines if any(kw in l for kw in stat_keywords)]
    assert len(stat_lines) >= 3, f"Too few statistical tests: {len(stat_lines)}"
```

---

## Quality Bar

The overhaul is complete when an Arc D rung report:
1. **Length:** ≥ 300 lines of generated markdown (vs current 39)
2. **Charts:** ≥ 8 embedded chart references (vs current 0)
3. **Tables:** ≥ 8 data tables with per-contract breakdowns (vs current 3)
4. **Statistical tests:** ≥ 3 tests with p-values/CIs (ANOVA, bootstrap, binomial CI)
5. **Interpretive commentary:** Every section has 2+ sentences explaining what the data shows and what it means
6. **Reproduction:** Complete commands section to regenerate everything
7. **Notebook depth:** Each of the 3 notebooks produces ≥ 10 charts covering its domain

---

## Resolved Decisions

| Decision | Resolution | Source |
|----------|-----------|--------|
| Data source | Eval JSONL only (not training parquet) | User choice |
| Template 1 & 2 style | Parameterized (papermill) | User choice |
| Template 3 style | Standardized base, copy + extend per rung | User choice |
| Regression depth | Full model diagnostics (pred/actual, residuals, bootstrap CIs, calibration) | User choice |
| Phasing | Plan first, 7 PRs across 5 horizontal waves | User choice |
| Old template fate | Deprecate after R0 validation in Wave 4 | User choice |
| CI inclusion | Yes — SMOKE mode in `make notebook-run` | User choice |

## Remaining Open Questions

1. **Chart style:** Should charts use a consistent style (seaborn whitegrid, consistent colormap, specific DPI)? Phase 0 uses `sns.set_theme(style="whitegrid")` + `dpi=150`. (Recommendation: yes, match Phase 0.)

2. **Per-rung report naming:** Continue with `model_arc_r0_YYYYMMDD.md` pattern, or switch to `arc_d_r0_report.md`? The reports directory has been restructured to `docs/04_reports/r0/` per PR #416.

3. **Comparator integration depth:** Should the comparator leaderboard appear in all 3 notebooks or just notebook 3 + report? (Recommendation: notebook 2 gets a brief mention, notebook 3 gets full analysis, report gets summary table.)

## Review Fixes Applied (2026-02-23, Round 1)

| Finding | Priority | Fix |
|---------|----------|-----|
| JSONL path incorrect (`game_log.jsonl` → `logs/<run_id>_<strategy>.jsonl`) | P1 Correctness | Fixed path pattern, added verified log inventory table |
| Seed regeneration only covers seed 42 | P1 Correctness | Updated to `for seed in 42 43 44` loop |
| Report output path inconsistent | P2 Correctness | Standardized on `docs/04_reports/r0/` per PR #416 |
| JSONL availability stale open question | P3 Correctness | Removed from open questions; all 7 logs verified present |
| Notebook execution integration gap | P1 Completeness | Added Jupytext pairing, Makefile glob update, `discover_notebooks()` scope |
| Test migration under-specified | P1 Completeness | Added "Test Migration Scope" section with per-file change plans |
| Asset directory not pinned | P2 Completeness | Standardized on `assets/charts/` per `docs/04_reports/README.md` |
| Dashboard refresh missing | P2 Completeness | Added `generate_arc_dashboard.py --snapshot` to Wave 5 |
| `resolve_eval_log_from_bundle()` utility | Recommendation | Added to Wave 1 scope |
| Quality bar contract test | Recommendation | Added to Wave 5 with example implementation |

## Review Fixes Applied (2026-02-23, Round 2)

| Finding | Priority | Fix |
|---------|----------|-----|
| Wave 2 testability gap: Jupytext sync deferred to Wave 5 but needed for SMOKE papermill tests | P1 Sequencing | Moved Jupytext pairing into each Wave 2 PR; Wave 5 reduced to end-to-end verify |
| `**` glob pattern requires `recursive=True` in `discover_notebooks()` | P1 Correctness | Added explicit `recursive=True` fix with code snippet to Wave 5 Makefile section |
| `resolve_eval_log_from_bundle()` ambiguous with 2 OLSa_Full seed-42 logs | P1 Correctness | Specified deterministic lookup: bundle → eval JSON → `run_id` + `source_logs[0]` (no path search) |
| Old template deprecation missing `report_template.py:132` and `PROMOTION_WORKFLOW.md:116` refs | P2 Completeness | Added 4-item reference update checklist to Wave 5 deprecation deliverable |
| Stale line counts: 523→522, 767→766, 39→38; filename `_r5.md` suffix doesn't exist | P3 Accuracy | Corrected all numbers and filename to match actual disk state |
