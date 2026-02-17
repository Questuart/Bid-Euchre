# Phase 0 Report Revision (r4) — Implementation Plan

> **Goal:** Comprehensive rewrite of `docs/04_reports/phase0_bidless_20260207.md` addressing chart bugs, section reordering, narrative improvements, and per-contract visualizations. Single PR.
>
> **Scope:** Code fixes (chart normalization), new tests, report rewrite, new charts.

---

## Part A: Code Fixes (chart normalization)

### Problem
`_normalize_for_diagnostics()` in `reporting/charts.py:63` maps raw column names to `feat_`-prefixed names expected by diagnostic chart functions. It's only applied in `generate_contract_faceted_charts()` (line 355), but NOT in:

- `generate_feature_health_charts()` (line 80)
- `generate_feature_outcome_charts()` (line 207)
- `generate_distribution_charts()` (line 289)

### Root Cause (verified from source)
- `join_features_outcomes()` (`datasets/join.py:11`) returns raw names: `hand_value`, `trump_suit`
- `_load_bidless_features()` expands `hand_features` struct to raw names
- Diagnostic charts expect: `feat_hand_value`, `trump`, `feat_*` prefixes
- Specifically broken functions:
  - `plot_feature_distributions()` (charts.py:175) — filters for `feat_` prefix at line 195
  - `plot_feature_correlation()` (charts.py:247) — filters for `feat_` prefix at line 265
  - `plot_feature_vs_outcome()` (charts.py:476) — expects `feat_` prefix, adds it if missing at line 498
  - `plot_hand_value_by_seat()` (charts.py:47) — expects `feat_hand_value` at line 58
  - `plot_hand_value_by_contract()` (charts.py:114) — expects `feat_hand_value` at line 134

### Fix
In `src/bid_euchre/reporting/charts.py`:

1. **`generate_feature_health_charts()`** — Add `df = _normalize_for_diagnostics(df)` after data is loaded (after the `hand_features` struct expansion in chart_runner, or at the start of the function if df is already flat)
2. **`generate_feature_outcome_charts()`** — Add `df = _normalize_for_diagnostics(df)` at function start
3. **`generate_distribution_charts()`** — No fix needed (uses `tricks_won` and `contract_type`, neither requires normalization)

**Note:** `generate_feature_health_charts` gets its df from `chart_runner._load_bidless_features()` which has raw names after struct expansion. The normalization must happen AFTER expansion. Two options:
- Option 1: Normalize inside `generate_feature_health_charts()` (cleanest — each generator normalizes its own input)
- Option 2: Normalize in `chart_runner.py` before passing to generators

**Recommendation:** Option 1 — normalize inside each generator. This makes generators defensive about input format.

### Files to modify
- `src/bid_euchre/reporting/charts.py:80` — add `df = _normalize_for_diagnostics(df)` in `generate_feature_health_charts()`
- `src/bid_euchre/reporting/charts.py:207` — add `df = _normalize_for_diagnostics(df)` in `generate_feature_outcome_charts()`

---

## Part B: New Tests (chart content validation)

### Current test state (verified)
- `tests/unit/test_chart_generators.py` — tests output file existence, count, file size > 1024 bytes
- `tests/unit/test_diagnostics_charts.py` — tests return types (Figure), axis properties
- **No content validation** — no test checks for placeholder text

### New test: assert no placeholder rendering

Add to `tests/unit/test_chart_generators.py`:

```python
class TestChartContentValidity:
    """Assert production charts contain actual data, not placeholder text."""

    def test_feature_health_no_placeholders(self, feature_outcome_with_trump_df):
        """feature_health charts should contain actual plot elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_health_charts(
                feature_outcome_with_trump_df, tmpdir
            )
            for p in paths:
                fig = plt.figure()
                img = plt.imread(p)
                # Placeholder charts are typically very small or uniform
                assert img.std() > 0.01, f"{Path(p).name} appears to be blank"
                plt.close(fig)

    def test_feature_outcome_no_placeholders(self, feature_outcome_with_trump_df):
        """feature_outcome charts should contain actual plot elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = generate_feature_outcome_charts(
                feature_outcome_with_trump_df, tmpdir
            )
            assert len(paths) >= 3  # correlation, scatter, outcome_distributions
            for p in paths:
                assert Path(p).stat().st_size > 2048, f"{Path(p).name} too small"
```

**Alternative approach (more robust):** Test diagnostic functions directly with normalized data, assert axes have actual data elements:

```python
def test_plot_feature_distributions_with_normalized_data(self):
    """After normalization, plot_feature_distributions should find features."""
    df = _make_feature_df()
    norm_df = _normalize_for_diagnostics(df)
    fig = plot_feature_distributions(norm_df)
    # Should have subplot axes with actual histograms
    assert len(fig.axes) > 1, "No subplots — features not found"
    plt.close(fig)
```

### Files to modify
- `tests/unit/test_chart_generators.py` — add `TestChartContentValidity` class

---

## Part C: Report Rewrite

### C.1 — Section Reordering

**Current order:**
1. Executive Summary
2. Data Inventory
3. Run Health Summary
4. Play Policy Gate
5. Strategy Sanity Tests
6. Diagnostic Feature Evaluation
7. Feature and Distribution Health
8. Contract-Faceted Analysis
9. Known Limitations
10. Reproduction Commands
11. References

**New order (health → validation → findings → analysis):**
1. Executive Summary *(rewritten with goal/purpose framing)*
2. Data Inventory *(unchanged)*
3. Run Health Summary *(expanded with contract_type faceting)*
4. Strategy Sanity Tests *(moved before Policy Gate, expanded explanations)*
5. Play Policy Gate *(restructured: finding → evidence → decision)*
6. Feature and Distribution Health *(merged with Contract-Faceted Analysis)*
7. Diagnostic Feature Evaluation *(rewritten with model explanation, heatmap viz)*
8. Known Limitations *(updated)*
9. Reproduction Commands *(unchanged)*
10. References *(unchanged)*

### C.2 — Executive Summary Rewrite

Add opening paragraph:
> This report documents the Phase 0 "bidless" data collection for the Bid Euchre AI project. The goal of Phase 0 was to: (1) generate high-quality training data for hand features and trick outcomes across all contract types, (2) select and freeze a canonical play policy for consistent data generation going forward, and (3) validate the simulation engine produces fair, unbiased results. This report presents the evidence for each of these goals.

Key takeaways (rewritten for clarity):
- Data: 5.82M hands collected, quality-validated
- Play policy: Glutton selected over Greedy (statistically significant advantage)
- Engine health: Zero bias across seats, teams, and contract types
- Feature signal: Hand features predict ~20% of trick variance (sufficient for bidding model development)

### C.3 — Run Health Summary (Section 3)

Changes:
1. **Self-play control chart** — Currently aggregate only. Need to either:
   - Modify `plot_self_play_control()` in `strategy_charts.py` to support faceting by contract type, OR
   - Use the existing `self_play_by_contract` chart (already generated) more prominently
   - **Recommendation:** Keep both charts. The aggregate chart is the headline, the per-contract chart is the evidence. Add contract_type breakdown to the table.

2. **Self-play table** — Add per-contract breakdown columns or a second table showing mean delta by contract type per strategy

3. **Seat balance** — Chart loads fine (`hand_value_by_seat.png`). To add contract_type faceting, we'd need a new chart function (e.g., `plot_hand_value_by_seat_and_contract()`). This is a NEW diagnostic chart, not just a report change.
   - **Question for user:** Is this worth the code investment for r4, or can we note it as a future enhancement?

4. **Source attribution** — Add explicit "Source: greedy self-play dataset (300K hands)" to every chart/section

### C.4 — Strategy Sanity Tests (Section 4, was Section 5)

Changes:
1. **Move before Play Policy Gate** — Sanity tests validate infrastructure; Policy Gate reports a finding
2. **Explain "Direction"** — Add: "In each matchup, 'team_0_vs_team_1' means team 0 plays strategy A and team 1 plays strategy B. Seats (0,2) form team 0; seats (1,3) form team 1."
3. **Rename "Random Dominance"** → "Strategy Performance vs. Random"
4. **Expand Self-Play Fairness** — Explain what it tests (both teams should win ~50% when playing the same strategy, meaning ~5.0 tricks each) and why it matters (validates no inherent team advantage in the engine)
5. **Expand Rank Stability** — Explain: "Rank stability tests whether the competitive ordering of strategies is the same across different contract types. A Kendall tau of 1.0 means the ranking is identical — if glutton beats greedy in suit contracts, it also beats greedy in high and low contracts."
6. **Expand Transitivity** — Explain: "Transitivity tests the logical consistency of the competitive ordering. If A > B and B > C, then A > C should hold. Zero violations means the strategy landscape has a clean, linear ordering with no rock-paper-scissors dynamics."

### C.5 — Play Policy Gate (Section 5, was Section 4)

Changes:
1. **Explain Directions** — Add clear definition at top of methodology: "Direction indicates which strategy plays as team 0 (seats 0,2) and team 1 (seats 1,3). Both directions are tested to confirm the advantage is not an artifact of seat assignment."
2. **Aggregate results** — Sort by team 0 strategy. Consider restructuring as: "Glutton advantage (mean across directions)" per seed, then show direction breakdown as sub-table
3. **Statistical test** — Add t-test or Welch's t-test on the pooled advantage. The bootstrap CIs already demonstrate significance, but an explicit p-value is more universally understood.
4. **Per-Scenario Breakdown** — Rename to "Advantage by Contract Type". Explain: "This table shows glutton's advantage broken down by contract type, answering whether glutton's superiority is uniform or concentrated in specific contracts."
5. **Decision section** — Restructure as:
   - **Finding:** Glutton outperforms greedy by +0.19 to +0.21 mean tricks
   - **Evidence:** 720K hands across 3 seeds, 2 directions, 6 contract types; all bootstrap CIs exclude zero
   - **Caveat:** LOW contract advantage is marginal (CI barely excludes zero)
   - **Decision:** Freeze glutton as canonical play policy for all subsequent data generation

### C.6 — Feature and Distribution Health (Section 6, merged)

Merge current sections 7 (Feature and Distribution Health) and 8 (Contract-Faceted Analysis) into one section. All charts in this section come from the greedy self-play dataset — state this once at the top.

Subsections:
1. Hand value calibration (by contract, by trump suit)
2. Tricks distribution (CDF, CCDF)
3. Trump suit invariance (heatmap, variance summary)

Move `outcome_distributions.png` here from Section 6 (it's a health check, not a diagnostic feature evaluation result).

### C.7 — Diagnostic Feature Evaluation (Section 7, was Section 6)

Changes:
1. **Add model explanation** — "To validate that hand features carry predictive signal for trick outcomes, we trained a Ridge regression (alpha=1.0) to predict tricks_won from all 41 hand features. This is an exploratory diagnostic — not a production model. The purpose is to confirm that hand features contain enough signal to justify building per-contract bidding models in Phase 1."
2. **Replace top-10 tables with heatmap** — Generate a feature-importance heatmap showing top features × contract types × policies. This replaces the current 2 × 1 = 2 pooled tables with a single visual that's easier to scan and shows per-contract variation.
   - **New chart function needed:** `plot_coefficient_heatmap(coefs_by_contract: dict, title: str)` in `diagnostics/charts.py`
   - Input: dict mapping contract_type → Series of standardized coefficients
   - Output: heatmap with features on y-axis, contract types on x-axis, color = coefficient magnitude
   - **Question for user:** Do we generate this from re-running the Ridge regression, or hardcode the existing coefficient data into the report? Re-running requires the diagnostic evaluation script.
3. **Move outcome_distributions** out of this section (see C.6)
4. **Keep feature_vs_outcome_by_contract** — This is the right section for it
5. **Expand caveats** — Explain WHY each caveat matters:
   - Standardized coefficients: "Without standardization, features with larger scales would appear more important simply due to unit differences"
   - Correlated features: "When two features are correlated (e.g., trump_count and trump_rb_count), the regression splits the signal between them, making both appear weaker than their true predictive value"
   - Grouped split: "Each hand produces 4 seat rows. If train and test sets shared hands, the model could memorize hand-specific patterns rather than learning general feature relationships"

---

## Part D: New Charts Needed

### D.1 — Coefficient Heatmap (replaces 2 top-10 tables)
- **Function:** New `plot_coefficient_heatmap()` in `diagnostics/charts.py`
- **Data source:** Re-run `scripts/evaluate_diagnostic_tricks.py` with `--per-contract` flag, OR generate from existing per-contract Ridge results
- **Integration:** Add to `reporting/charts.py` `generate_feature_outcome_charts()`, save as `coefficient_heatmap.png`

### D.2 — Seat Balance by Contract (optional, see C.3 question)
- **Function:** New `plot_hand_value_by_seat_and_contract()` in `diagnostics/charts.py`
- **Would require:** Faceted boxplot with contract_type on x-axis, colored by seat

---

## Part E: Report Asset Updates

After code fixes, regenerate ALL charts:
```bash
# Greedy run (now with normalization fix, all suites)
PYTHONPATH=src uv run python -m bid_euchre.reporting.chart_runner \
  --run-dir data/runs/canonical_bidless_dataset_greedy_42_20260204_221121 \
  --output-dir /tmp/phase0_r4/greedy --suite all --dpi 150

# Zoom run (strategy_matchup)
PYTHONPATH=src uv run python -m bid_euchre.reporting.chart_runner \
  --run-dir data/runs/canonical_bidless_outcomes_zoom_42_20260204_222712 \
  --output-dir /tmp/phase0_r4/zoom --suite strategy_matchup --dpi 150
```

Copy all PNGs to `docs/04_reports/assets/phase0_20260207/`, update provenance JSON.

---

## Files Modified (complete list)

| File | Change |
|------|--------|
| `src/bid_euchre/reporting/charts.py` | Add `_normalize_for_diagnostics()` to feature_health + feature_outcome generators |
| `tests/unit/test_chart_generators.py` | Add `TestChartContentValidity` class |
| `docs/04_reports/phase0_bidless_20260207.md` | Full rewrite (sections, narrative, charts) |
| `docs/04_reports/phase0_bidless_20260207_provenance.json` | Update with new charts and SHA |
| `docs/04_reports/assets/phase0_20260207/*.png` | Regenerated charts (3 fixed + potentially new ones) |
| `src/bid_euchre/diagnostics/charts.py` | New `plot_coefficient_heatmap()` + `plot_hand_value_by_seat_and_contract()` |
| `scripts/evaluate_diagnostic_tricks.py` | Add `--per-contract` output for coefficient heatmap data |

---

## Resolved Questions

1. **Seat balance by contract_type** → **Add new chart now.** Create `plot_hand_value_by_seat_and_contract()` in `diagnostics/charts.py`.
2. **Coefficient heatmap data source** → **Re-run script.** Run `evaluate_diagnostic_tricks.py` with per-contract output (~2 min).
3. **Self-play table expansion** → **Separate table below.** Keep aggregate table, add per-contract breakdown table underneath.

---

## Commit to Memory

Per user request, record this pattern:
> **Always facet by contract_type.** Suit contracts behave fundamentally differently from high/low (no-trump) contracts. Every chart and table in a report should either be faceted by contract type or explicitly justify why pooling is appropriate.
