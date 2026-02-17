# Phase 0 Report Improvement Plan (r3 → r4)

> **Working document** — interview notes from planning session 2026-02-09
> **Source:** `docs/04_reports/phase0_bidless_20260207_r3.md`

---

## Overall Direction

- **Audience:** The report author (human reviewer)
- **Purpose:** Key human intervention step to validate experiment outcomes before proceeding. Decision record + technical evidence package.
- **Flow:** Health-first → strategy comparison. Build trust in the infrastructure, then deliver the strategy verdict.
- **Feature diagnostics** (current Sections 6-7) are part of the health story — a smell test for whether something has gone wrong, not a separate analysis topic.

---

## Confirmed Section Order

1. Executive Summary *(deferred until body is settled)*
2. Data Inventory *(expanded — sanity framework, artifact descriptions)*
3. Self-Play Fairness *(from r3 §3 — new grouped boxplot + table)*
4. Seat Balance *(from r3 §3 — new grouped boxplot + table)*
5. Feature & Distribution Health *(from r3 §6 — moved up into health block)*
6. Diagnostic Feature Evaluation *(from r3 §7 — moved up into health block)*
7. Strategy Sanity Checks *(from r3 §4: vs-random, rank stability, transitivity — NOT self-play)*
8. Strategy Comparison *(from r3 §4: heatmap, violin plots)*
9. Play Policy Gate *(from r3 §5 — glutton freeze decision)*
10. Known Limitations
11. Reproduction Commands
12. References

**Rationale:** Layered trust-building. Each section builds on the previous:
- §3-4: Simulation engine is fair (self-play + deals)
- §5-6: Data is healthy (features + diagnostics)
- §7: Competitive landscape is well-behaved (sanity checks)
- §8-9: Strategy results + freeze decision (the payoff)

---

## Global Rules

- [ ] **Every section gets a bulleted intro** immediately after the section header (3-4 bullets: purpose, data source, key finding, pass/fail criteria). This applies to §2-10.
- [ ] **Immutable r4 assets directory:** All new/regenerated charts go in `docs/04_reports/assets/phase0_20260207_r4/`. r3 assets remain untouched.
- [ ] **JSON-sourced tables (§6 and §9):** Complex numeric tables (diagnostic Ridge results, policy gate results) are generated from machine-readable JSON artifacts, not hand-maintained markdown. Ensures reproducibility and auditability. Simple tables (§3/§4 summaries) can remain hand-maintained.
- [ ] **Provenance JSON:** Create/update `phase0_bidless_20260207_r4_provenance.json` capturing commands, run IDs, chart filenames, and SHAs for every artifact used in the report.
- [ ] **Link integrity check:** After report is drafted, verify all image paths resolve to actual files. Catches broken chart references (which affected 3+ charts in r3).

---

## Section-by-Section Notes

### Section 1: Executive Summary

- [ ] **Hybrid approach:** Verdict sentence + question→answer bullets mirroring report flow
- [ ] **Structure:**
  1. One-sentence verdict: Glutton frozen as canonical play policy; all health checks pass.
  2. Bulleted question→answer format (4-5 bullets):
     - Simulation fairness → PASS (all self-play deltas < 0.025, threshold 0.25)
     - Deal fairness → PASS (seat balance identical across seats and contract types)
     - Feature health → PASS (distributions healthy, trump-invariant, no anomalies)
     - Feature signal → R² ~0.20 per contract (sufficient for Phase 1 bidding models)
     - Policy decision → Glutton advantage +0.19–0.21 tricks_won, all CIs exclude zero
- [ ] **Replace current 5-bullet summary** with this new structure

### Section 2: Data Inventory

- [ ] **Section intro** (bulleted: what the inventory is, why it matters as a human validation step, summary of artifacts)
- [ ] **Add sanity framework explanation before the table.** Explain the 4-test gate:
  - `self_play_fairness` — no team bias in same-strategy play (|mean delta| < 0.25)
  - `random_dominance` — intelligent strategies beat random_legal (win rate > 52%)
  - `rank_stability` — rankings consistent across contract types (Kendall tau > 0.6)
  - `transitivity` — no rock-paper-scissors dynamics (zero violations)
- [ ] **Define PASS/SKIP/WARN/FAIL** before the table so reader understands columns.
- [ ] **Explain the SKIP pattern:**
  - Single-strategy self-play runs (greedy, glutton) can only run `self_play_fairness` → 1 PASS, 3 SKIP (no cross-strategy data for other tests).
  - Mixed-play (3 strategies) runs most tests → 3 PASS, 1 SKIP.
  - Full matrix runs (zoom, matrix_shallow) have all matchups → 4 PASS, 0 SKIP.
- [ ] **Expand artifact descriptions:** For each artifact, explain what was simulated, which strategies played, what question it answers, and why it exists in the inventory.
- [ ] **Move SKIP footnote** from below the table into the framework paragraph (explain before, not after).

### Section 3: Self-Play Fairness (from r3 §3)

- [ ] **Section intro** (bulleted: what self-play tests, why it matters, what failure looks like, data source)
- [ ] **Clarify data source:** Zoom run (3.3M hands, 5 strategies in self-play). Greedy/glutton single-strategy datasets can't contribute since they only have one strategy each.
- [ ] **Replace current 2 charts** (aggregate control chart + per-contract bar chart) **with 1 grouped boxplot:**
  - X-axis: strategy name (5 strategies)
  - Within each strategy: 4 color-coded boxplots (aggregate, suit, high, low)
  - Y-axis: raw tricks_won (should center on 5.0 for fair self-play)
  - Reference line at 5.0
- [ ] **Replace current summary table with richer table:**
  - Columns: Strategy | Contract | N | Mean | P25 | P75 | Min | Max | |Delta from 5.0| | Status (PASS/WARN)
  - One row per strategy × contract-group combination

### Section 4: Seat Balance (from r3 §3)

- [ ] **Section intro** (bulleted: what seat balance tests, why it matters, what failure looks like, data source)
- [ ] **Justify greedy-only data source:** Seat balance tests deal generation fairness, not play policy — results are identical regardless of which strategy plays. Using greedy dataset (300K hands) is sufficient.
- [ ] **Replace current 2 charts** (broken hand_value_by_seat + hand_value_by_seat_and_contract) **with 1 grouped boxplot:**
  - Mirror the self-play layout: seat (0-3) on x-axis
  - Within each seat: 4 color-coded boxplots (aggregate, suit, high, low)
  - Y-axis: hand_value
  - Should show identical distributions across all 4 seats
- [ ] **Add summary table** (same column structure as self-play table but with Seat instead of Strategy)
- [ ] **Fix broken chart:** Current `hand_value_by_seat.png` doesn't render — new chart replaces it

### Section 5: Feature & Distribution Health (from r3 §6)

- [ ] **Section intro** (bulleted: what feature health checks, why distributions matter for downstream models, data sources used, key finding)

#### 5a. Hand Value Calibration

- [ ] **Fix broken chart** (`hand_value_by_contract.png` not loading). Replace with grouped boxplot:
  - X-axis: contract type (suit, high, low)
  - Within each group: 2 boxplots (greedy, glutton)
  - Y-axis: hand_value
  - Shows hand evaluation is calibrated to contract structure and strategy-independent

#### 5b. Tricks Distribution

- [ ] **Replace current histogram** with grouped boxplot matching 5a layout:
  - X-axis: contract type (suit, high, low)
  - Within each group: 2 boxplots (greedy, glutton)
  - Y-axis: tricks_won
- [ ] **Replace CDF + CCDF with 2 side-by-side CDFs:**
  - One CDF for greedy, one for glutton
  - Each CDF shows curves per contract type (suit, high, low)
  - Discrete steps (0-10), no KDE smoothing
- [ ] **Add tricks_won percentage table:**
  - Rows: tricks_won (0-10)
  - Columns grouped by contract type (suit, high, low) × strategy (greedy, glutton)
  - Shows exact percentage of hands at each tricks_won level
- [ ] **Remove CCDF entirely** — tail info captured by the percentage table

#### 5c. Trump Suit Invariance

- [ ] **Replace 2 existing charts with strategy-faceted versions** (for consistency with §5a/5b):
  - `hand_value_by_trump` — facet by strategy (greedy, glutton): either side-by-side or color-coded within each trump suit group
  - `outcome_by_trump` (tricks_by_trump) — same treatment: facet by strategy within each trump suit
- [ ] **Preserve variance numbers in narrative:** Keep the quantitative evidence from the removed charts (σ² range 8321.9–8369.7, spread < 0.6%) as inline text under the hand_value_by_trump chart
- [ ] **Remove 2 charts:**
  - `feature_heatmap_by_suit.png` — omit feature means by trump suit
  - `suit_variance_summary.png` — omit (variance numbers preserved in narrative instead)
- [ ] **Remove associated narrative** for the omitted charts (heatmap per-suit breakdown)

### Section 6: Diagnostic Feature Evaluation (from r3 §7)

- [ ] **Section intro** (bulleted: what this diagnostic measures, why it matters, data sources, key finding)

#### 6a. Methodology (r3 §7.1)

- [ ] **Keep as-is.** Paragraph explaining Ridge methodology, z-scoring, and exploratory nature.

#### 6b. Model Performance (r3 §7.2 + §7.3 combined)

- [ ] **Drop the pooled (overall) model entirely.** Only show per-contract models.
- [ ] **Combine into one table:**
  - Rows: suit, high, low (one per contract type)
  - Columns: Policy (greedy/glutton) | R² (test) | MAE (test) | N (test rows) | N (train hands)
  - No aggregate row — pooled model mixes contract types that behave fundamentally differently
- [ ] **Remove OLSa Validation column** from the performance table — OLSa isn't introduced in this report, so the column is confusing here
- [ ] **Add OLSa WARN as a standalone note** below the table: document the WARN (`trump_count`, `offsuit_aces` not in top 10 for suit contracts) as a flagged finding, with brief context on what OLSa validation checks and why the WARN was produced

#### 6c. Coefficients (r3 §7.4)

- [ ] **One table per contract type** (3 tables: suit, high, low):
  - Columns: Feature | Greedy Coeff | Glutton Coeff | Greedy Rank | Glutton Rank
  - Top 10 features per table, ranked by average absolute magnitude across both strategies
- [ ] **Add companion correlation table** per contract type:
  - Top 10 features ranked by Pearson r with tricks_won (bivariate)
  - Columns: Feature | Pearson r (with tricks_won) | Ridge Coeff (greedy) | Ridge Coeff (glutton)
  - Shows whether Ridge agrees with raw signal — disagreement flags multicollinearity effects
- [ ] **Replace the old pooled-model narrative** with a brief narrative about the per-contract tables — highlight notable patterns (e.g., which features dominate in suit vs NT, whether greedy and glutton agree or diverge on feature importance within each contract type)

#### 6d. Feature-Outcome Visualizations (r3 §7.5)

- [ ] **Remove both charts** (broken correlation chart + scatter by contract type)
  - Replaced by the per-contract correlation tables in 6c

#### 6e. Caveats (r3 §7.6)

- [ ] **Keep 5 caveats as-is** with one modification:
  - Reword final bullet about B0: add 1-2 sentence explainer of what B0 is ("Arc B Stage 0 — a regression that predicts hand_value from the other 40 features, essentially learning the hand evaluator's scoring function") and why it's distinct from this diagnostic (this predicts tricks_won, the actual game outcome)

### Section 7: Strategy Sanity Checks (from r3 §4 — vs-random, rank stability, transitivity)

- [ ] **Section intro** (bulleted: what these sanity checks validate, why they're prerequisites for trusting strategy comparison, data source, key findings)
- [ ] **Remove r3 §4.1 summary table** — section intro bullets serve this purpose now
- [ ] **Remove r3 §4.2 self-play cross-reference** — self-play is its own Section 3, no pointer needed
- [ ] **Remove direction convention paragraph** — established earlier in the report by this point

#### 7a. Strategy Performance vs. Random (r3 §4.3)

- [ ] **Restructure table to 5 columns:** Strategy | Team 0 | Team 1 | Win Rate | N
  - Breaks out the matchup name into explicit team columns for clarity
  - Same 4 rows as current (glutton both directions, greedy both directions)
- [ ] **Keep narrative as-is** — threshold (52%) and direction-invariance confirmation (< 0.3% spread) are appropriate

#### 7b. Rank Stability (r3 §4.4)

- [ ] **Keep as-is.** Kendall tau table with p-values + explanatory paragraph about what failure would mean. Clean and appropriate for a pass/fail check.

#### 7c. Transitivity (r3 §4.5)

- [ ] **Keep as-is.** One-line result ("zero violations") + explanatory paragraph. Appropriately terse for a binary check.

### Section 8: Strategy Comparison (from r3 §4 — heatmap, violin plots)

- [ ] **Section intro** (bulleted: what this section shows, data source (zoom run, 50K hands/matchup), key finding (glutton dominance), what to look for)
- [ ] **Define win rate** — add a clear definition before the heatmap (e.g., "Win rate = proportion of hands where team 0 won more tricks than team 1. A 55% win rate means team 0's strategy won 55 out of every 100 hands.")

#### 8a. Strategy Landscape (r3 §4.6)

- [ ] **Keep both charts as-is:**
  - Win rate heatmap
  - Matchup summary chart
- [ ] **Expand narrative:** Add 2-3 paragraphs interpreting the results:
  - Overall hierarchy (glutton > greedy > always_highest/always_lowest > random_legal)
  - Key matchup insight: glutton vs greedy is the tightest competitive margin
  - What the heatmap symmetry shows (direction-invariance confirmed visually)

#### 8b. Tricks Distribution by Matchup (r3 §4.7)

- [ ] **Keep violin plots as-is**
- [ ] **Keep existing narrative** — paragraph about distributional shifts in cross-play is appropriate

### Section 9: Play Policy Gate (from r3 §5)

- [ ] **Section intro** (bulleted: what this gate decides, data source, methodology summary, verdict)

#### 9a. Methodology (r3 §5.1)

- [ ] **Keep as-is** — defines advantage metric, seeds, hands per scenario, bootstrap CI, gate criterion
- [ ] **Clarify unit:** Explicitly state that advantage is measured in mean tricks_won difference

#### 9b. Aggregate Results (r3 §5.2)

- [ ] **Restructure direction column** to Team 0 | Team 1 (consistent with §7)
- [ ] **Rename "Advantage" column** to "Glutton Advantage (tricks_won)" — removes ambiguity about who benefits and what unit
- [ ] **Keep 6 rows** (3 seeds × 2 directions), CIs, N, Status

#### 9c. Advantage by Contract Type (r3 §5.3)

- [ ] **Rename "Advantage" column** to "Glutton Advantage (tricks_won)" (same as 9b)
- [ ] **Add note** explaining why seed 42 only (representative; all 3 seeds show the same per-contract pattern)
- [ ] **Add horizontal bar chart with CI error bars:**
  - One bar per contract type (suit_S, suit_C, suit_D, suit_H, high, low)
  - Bar length = glutton advantage, error bars = bootstrap 95% CI
  - Reference line at 0.0 — visually shows how close LOW's CI is to zero
  - Makes the suit > high > low hierarchy immediately visual

#### 9d. Decision (r3 §5.4)

- [ ] **Keep as-is** — finding/evidence/caveat/decision structure is crisp and well-evidenced

### Section 10: Known Limitations (from r3 §8)

- [ ] **Section intro** (bulleted: purpose of this section)
- [ ] **Remove limitation #2** (SKIP counts) — now explained in §2 (Data Inventory) as part of the sanity framework, no longer a "limitation"
- [ ] **Remove limitation #4** (coefficient heatmap not integrated) — resolved by adding per-contract coefficient tables in §6c
- [ ] **Keep limitation #1** (no bootstrap CIs on diagnostic R²/MAE) — still true and relevant
- [ ] **Keep limitation #3** (LOW contract marginal significance) — important standing caveat

### Section 11: Reproduction Commands (from r3 §9)

- [ ] **Keep as-is.** All commands are correct and useful reference material. No section intro needed (pure reference).

### Section 12: References (from r3 §10)

- [ ] **Keep as-is.** All 5 document links are relevant. No section intro needed (pure reference).
