# R1 Follow-Ups — Prioritized

**Date:** 2026-03-01
**Source:** Master plan execution sessions (A1 oracle analysis, B0 threshold sweep,
contract selection analysis, comparator overhaul)
**Governing doc:** `plans/MASTER_PLAN.md` §Stream 6

Items are ordered by expected impact on R1 model quality, with experimental
designs where applicable.

---

## R1 Promotion Gate — Follow-Up Checklist

**Rule:** R1 cannot be promoted until every item below is dispositioned.
This is a human-reviewed checklist referenced by `promotion_decision_r1.json`.
See `arc_d_execution_plan.md` §Phase R1 for the gate definition.

| # | Follow-Up | Blocks Promotion? | Disposition | Notes |
|---|-----------|-------------------|-------------|-------|
| P1 | HIGH/LOW feature enrichment | **Yes** | — | Core R1 objective |
| P2 | 2×2 factorial (context + unified model) | No (deferrable) | — | |
| P3 | Oracle re-analysis at R1 | **Yes** | — | Regret decomposition shift |
| P4 | Pass-threshold re-tuning | **Yes** | — | Re-run B0 protocol |
| P5 | Deferred report sections | No (deferrable) | — | |
| P6 | H2H bid_rate caveat | No (deferrable) | DONE | Adopted by v2 — fix terminology during report regeneration (§7.4 of r0_canonical_v2_plan.md) |
| P7 | Rung-to-rung report pipeline | No (deferrable) | — | Automate progression reports |
| P8 | Bid-level search in HybridOLSaBidder | **Yes** | DONE | Adopted by v2 — `compute_best_bid()` in #493, verified max-utility search |

**Disposition values:** DONE / DEFERRED (with rationale + target rung) / NOT APPLICABLE (with evidence)

---

## Priority 1: HIGH/LOW Feature Enrichment

**Status:** Planned for R1
**Origin:** Oracle analysis (#472) — 82% of regret is pass-threshold (model conservatism),
caused by 1-feature HIGH/LOW models that can't produce positive utility for most hands.

### What

The current R0 models use:
- **HIGH:** 1 feature (`offsuit_aces`)
- **LOW:** 1 feature (`offsuit_tens_count`)
- **Suit:** 3 features (forward-selected)

The oracle shows HIGH/LOW optimal in 31.9% of hands, but the model bids them 1.7%
of the time. The features are too impoverished to detect when HIGH/LOW is profitable.

### Actions

1. **Lower `min_improvement` threshold** in `feature_selection.py` for non-suit contracts.
   The current threshold may be too aggressive, stopping selection at 1 feature when
   marginal features still carry signal for HIGH/LOW.

2. **Add hand-crafted distributional features** not in the current 39-feature set:
   - HIGH: suit spread, void count, ace concentration
   - LOW: low-card connectivity, ten concentration, short-suit count

3. **3-arm R0→R1 ablation** on the same split/seed for clean attribution:
   1. Frozen R0 (1/1/3 features per HIGH/LOW/suit)
   2. R0+features only (e.g., 2/2/3, same threshold logic)
   3. Full R1 (features + any threshold retuning)

### Decision: Do NOT redefine canonical R0

**Question:** Should we re-run and redefine canonical R0 with multi-feature HIGH/LOW
for cleaner R0→R1 ablation?

**Answer:** No. Keep canonical R0 frozen; run a separate "R0+features" ablation
experiment instead. This preserves historical comparability and decision traceability,
at the cost of one extra experiment lane.

**Why:** The R0 path is already recorded as promoted and frozen, and the 2026-03-01
oracle decision explicitly points feature enrichment to R1; changing R0 now muddies
rung semantics and governance (see
[10_contract_selection_oracle.md](../docs/04_reports/r0/10_contract_selection_oracle.md),
[model_arc_d_dashboard.md](../docs/04_reports/model_arc_d_dashboard.md)).

---

## Priority 2: Context Features + Unified Model (2x2 Factorial Per Rung)

**Status:** Planned — applies at each rung (R1+)
**Origin:** Arc D execution plan (rung = context ladder), contract selection
analysis Option B (unified regression), master plan §Stream 6

### What

The Arc D rung ladder adds context features incrementally:
- **R1:** Partner context (`partner_bid_level`, `partner_passed`,
  `partner_suit_match`, `partner_bid_confidence`)
- **R2:** Opponent context (`opponent_max_bid`, `opponent_bid_count`,
  `opponent_suit_signal`, `opponent_aggression`)
- **R3+:** Full transcript, seat awareness, etc.

Independently, the unified cross-contract model ("OneModelIsAllItTakes") replaces
3 separate OLS models with a single OLS using contract type as input features +
interaction terms, called 6x per hand. Inherently calibrated across contracts.
(Option B from `plans/contract_selection_analysis.md`)

These two axes — **context enrichment** and **model architecture** — should NOT
be conflated. At each rung, run a 2×2 factorial so context lift and architecture
lift are separately attributable.

### Experimental Design: 2x2 Factorial (Template Per Rung)

At each rung R{N}, run on the same split/seed:

| Arm | Context Features | Unified Model | Label |
|-----|-----------------|---------------|-------|
| 1   | R{N-1} context  | No (separate models) | `R{N}_baseline` |
| 2   | R{N} context    | No (separate models) | `+context` |
| 3   | R{N-1} context  | Yes (unified)        | `+unified_model` |
| 4   | R{N} context    | Yes (unified)        | `+context+unified_model` |

At R1 specifically:
- Arm 1 = R0 features + HIGH/LOW enrichment (Priority 1), no partner context, separate models
- Arm 2 = + partner context features, separate models
- Arm 3 = R0 features + HIGH/LOW enrichment, unified model
- Arm 4 = + partner context + unified model

### Reporting (same structure each rung)

1. **Context lift:** `(2 - 1)` and `(4 - 3)`
2. **Unified-model lift:** `(3 - 1)` and `(4 - 2)`
3. **Interaction term:** whether `(4)` beats additive expectation `(2) + (3) - (1)`

### Execution

- Run QUICK first, then FULL only for contrasts that are positive/non-regressive
- This matches the existing "partner context can run in parallel" direction in
  `MASTER_PLAN.md` (PR-R2a off critical path)
- The unified model arm requires moderate rewrite of training + bidding pipeline
  (see `contract_selection_analysis.md` §Option B for capacity concerns)
- **Carry forward:** If the unified model is positive at R{N}, it becomes the
  baseline architecture for R{N+1}'s arm 1. If it regresses, drop it and carry
  forward separate models. The factorial design makes this decision clean at
  each rung.

### Capacity concern

A single linear model may lack capacity for 3 very different contract dynamics
(bowers/ruffing in suit vs no-trump HIGH vs inverted-rank LOW). The 2×2 design
will reveal this at each rung: if arm 3 regresses vs arm 1, the unified model
hurts despite calibration benefits — separate models with better features is
the answer. This concern may diminish at later rungs as richer context features
give the unified model more signal to distinguish contract dynamics.

---

## Priority 3: Cross-Contract Calibration & Oracle Re-Analysis at R1

**Status:** Planned for R1 (revisit)
**Origin:** Oracle analysis (#472) §5.3, contract selection analysis §Option C,
master plan §Stream 6

### What

The R0 oracle analysis found:
- Mean regret: 3.92 utility [3.89, 3.95]
- 82% pass-threshold, 17% contract-selection, 1% over-bidding

Once R1 enriches HIGH/LOW features (Priority 1), the regret decomposition will
shift. The pass-threshold slice should shrink as models produce positive utility
for more hands. The contract-selection slice (17%) may then become the dominant
bottleneck.

### Actions

1. **Re-run oracle analysis on R1 model** using the same notebook
   (`55_contract_selection_oracle.py`) with R1 artifacts. Compare the 3-way
   regret decomposition (pass-threshold / contract-selection / over-bidding)
   against R0 baseline.

2. **Evaluate whether a calibration layer (Option C) is now warranted.**
   At R0, the calibrator addressed only 17% of regret — disproportionate effort.
   If contract-selection regret rises to >30% at R1 (because pass-threshold
   regret fell), Option C becomes cost-effective.

3. **Compare Option B (unified model) vs Option C (calibration layer)** results
   from the Priority 2 factorial. If arm 3 (unified model) captures most of the
   contract-selection regret, Option C is unnecessary.

### Decision gate

- If R1 contract-selection regret > 30%: evaluate Option C (calibration layer)
- If R1 contract-selection regret ≤ 30%: defer to R2
- If Priority 2 arm 3 (unified model) is positive: Option C is likely redundant

---

## Priority 4: Pass-Threshold Re-Tuning

**Status:** Planned for each rung
**Origin:** B0 threshold sweep (#476), 11_pass_threshold_decision.md §6

### What

B0 found `t=0` optimal for R0 because the model can't distinguish profitable
marginal hands — lowering the pass gate just admits hands that bid on wrong
contracts or get set. But better features shift the utility distribution rightward,
potentially making threshold tuning viable.

### Actions

1. **Re-run B0 protocol** (`plans/r0_pass_threshold_protocol.md`) on R1 data
   - Change artifact path and dataset path
   - Potentially adjust SESOI (0.05 may be too tight or too loose for R1)
   - Same 60/40 deal_id split, same 11-point grid

2. **Run after R1 model is trained but before R1 reports finalize** (same
   sequencing as R0: threshold decision blocks report finalization)

3. **If R1 threshold sweep shows ADOPT:** implement as R1 hyperparameter,
   re-run R1 evals with new threshold before promotion

### Key insight from R0

The pass-threshold regret is fundamentally a model accuracy problem. Features
that improve calibration near the bid/pass boundary (e.g., partner context,
opponent context in R2) are the ones most likely to unlock threshold gains.

---

## Priority 5: Deferred Report Sections

**Status:** Can be filled at R1 when FULL-mode runs happen
**Origin:** Comparator rankings report (#470)

### Comparator Rankings §4 — Contract-Type Breakdown

Per-contract-type rankings at FULL resolution. Currently exists in QUICK-mode
notebook data (`45_comparator_deep_dive` §S3) but not at publication resolution.
FULL compute budget was prioritized for H2H battery at R0.

**Action:** When R1 FULL-mode comparator runs execute, produce contract-type
breakdown table at publication resolution. Include in R1 comparator report.

### Comparator Rankings §8 — Auction-Pressure Sensitivity

4-way rerun showing how rankings change under contested auctions. Deferred because
the H2H battery already captures auction interaction effects in a paired-deal
design. Single-seat remains the canonical comparator instrument.

**Action:** Revisit if R1 H2H results diverge significantly from single-seat
rankings (suggesting auction dynamics matter more than expected).

---

## Priority 6: H2H bid_rate Conflation (L3)

**Status:** DONE — adopted by R0 v2 (r0_canonical_v2_plan.md §7.4)
**Origin:** Measurement integrity review (20_measurement_integrity_r0.md L3)

### What

In H2H battery data, `bid_rate_a/b` = team auction-win frequency (NOT per-bidder
bid propensity). In single-seat comparator data, `bid_rate` = per-hand propensity.
These are different estimands sharing similar names.

**Impact:** Reports must interpret H2H bid_rate as "team auction-win frequency"
rather than "bidder selectivity." This is an inherent property of the H2H
estimand (competitive ordering), not a methodology defect.

**Actions:**
1. Ensure all R1+ reports and notebooks use correct terminology.
   Consider renaming the H2H field to `auction_win_rate_a/b` if the conflation
   causes persistent confusion.
2. Report **seat-balanced competitive bid rate** as the headline metric in H2H
   reports (e.g., C33 §2): average the two reciprocal cross-matchups per bidder.
   Keep single-cell rates as supporting detail. Example from R0 C33:
   `hybrid_olsa: (16.2+16.5)/2 = 16.35%`, `olsa: (83.8+83.5)/2 = 83.65%`.
   Low cost, improves defensibility without changing conclusions.

---

## Priority 7: Rung-to-Rung Report Pipeline

**Status:** Planned (deferrable)
**Origin:** Phase 0→R0 progression report (hand-written), bundle gate requirement

### What

The Phase 0→R0 progression report (`docs/04_reports/r0/23_phase0_to_r0_progression.md`)
was manually authored. Starting at R1, `progression_report` is a required bundle
artifact enforced by the rung bundle validator. Future rung transitions should have
automated or semi-automated report generation.

### Proposed Approach

Either:
- **Skill:** `/generate-progression-report` that takes prior + current bundle paths
  and populates the 8-section template from `EXPERIMENT_REPORTS.md`
- **Script:** `scripts/internal/generate_progression_report.py` with CLI args for
  prior bundle, current bundle, and output path

### Why R1→R2+ Is Cleaner

R1→R2+ comparisons are cleaner than Phase 0→R0 because:
1. Both rungs use the same game mode (auction-selected contracts)
2. Both have standard bundle JSONs with comparable eval metrics
3. The forced-vs-selected confound that complicated Phase 0→R0 does not apply

### Dependencies

- A2 pipeline infrastructure
- R1 bundle available (eval runs complete)

---

## Priority 8: Bid-Level Search in HybridOLSaBidder

**Status:** DONE — adopted by R0 v2 (#493 `compute_best_bid()`, verified max-utility search)
**Origin:** R0 report Q&A session (2026-03-02), C33 ablation code review
**Blocks promotion:** No longer blocking — implemented in v2

### What

The current HybridOLSaBidder evaluates **one bid level per contract**: `bid_n = floor(mu)`.
If EV is negative at that level, it skips the contract entirely. It never checks whether
a lower bid level would have positive EV.

Example: `mu = 4.8` → `bid_n = 4`. If EV < 0 at bid 4 (e.g., P(make|4) is too low given
sigma), bidding 3 might have positive EV — higher P(make) and lower set penalty. But the
current code never evaluates this.

This is a "greedy single-point" limitation that leaves value on the table, especially for
marginal hands near the bid/pass boundary.

### Implementation

Add a `bid_level_search` parameter to `HybridOLSaBidder.__init__()` (default `False` for
backward compatibility with R0):

```python
# In choose_bid(), replace single-level evaluation with:
for search_n in range(bid_n, max(0, obs.current_high_bid), -1):
    ev = self._compute_ev(mu, sigma, search_n)
    penalty = self._compute_risk_penalty(mu, sigma, search_n)
    utility = ev - penalty
    if utility > 0 and (best_utility is None or utility > best_utility):
        best_utility = utility
        best_bid_n = search_n
        best_contract = contract
        break  # Highest level with positive EV is optimal (EV decreases as bid rises)
```

**Note:** EV is monotonically decreasing with bid level (higher bid → lower P(make) →
lower EV), so the first positive-EV level found searching downward is optimal. No need
to evaluate all levels.

**Cost:** Minimal — at most ~10 additional `_compute_ev` calls per contract (fast
arithmetic, no model inference).

### Ablation Design

At R1, run a C33-style ablation:
- Arm A: `bid_level_search=False` (R0 behavior)
- Arm B: `bid_level_search=True`
- Same model artifact, same deals, seat-swapped

This cleanly isolates the bid-level search contribution from P1 (feature enrichment)
and other R1 changes.

### Interaction with Other Priorities

- **P1 (HIGH/LOW enrichment):** Compounding potential — better features produce more
  accurate mu/sigma for HIGH/LOW, and bid-level search unlocks bids at lower levels
  where the current code passes. Test interaction via the P2 factorial.
- **P4 (pass-threshold re-tune):** Bid-level search may reduce the need for threshold
  adjustment — hands that currently pass because EV < 0 at floor(mu) might bid at a
  lower level instead.

---

## R0 Process Lessons — Checklist

**Source:** `docs/04_reports/r0/21_r0_retrospective.md` §5
**Status:** Review before starting R1 execution (C2)

These are development process recommendations from the R0 retrospective. They do not
block promotion but should be reviewed and dispositioned before R1 execution begins.

| # | Process Item | Disposition | Notes |
|---|-------------|-------------|-------|
| W1 | Pre-register calibration protocols before battery runs | — | Comparator v1→v4 required 4 iterations; define config, controls, and metrics upfront |
| W2 | Run integration smoke test before large experiment runs | — | Parser bugs (#442, #443, #453) surfaced during battery execution, forcing reruns |
| W3 | Review notebooks incrementally (per-notebook, not batch) | — | 72 items accumulated across 5 notebooks at R0; fix-forward, not fix-later |
| W4 | Preserve design-first pattern, reduce plan iterations | — | R0 had 3 plan versions; target 1–2 by leveraging existing conventions |
| W5 | Automate progression reports | — | = P7 above; implement early in R1 to reduce per-rung overhead |
| W6 | Expand fail-fast gates into battery orchestration scripts | — | Validate deal counts, schema compatibility, metric completeness before aggregation |

**Disposition values:** DONE / ADOPTED (with evidence) / DEFERRED (with rationale) / NOT APPLICABLE

---

## Cross-Reference

| Follow-Up | Master Plan Phase | Sub-Plan | Report |
|-----------|-------------------|----------|--------|
| HIGH/LOW features | C2 (R1 training) | `arc_d_execution_plan.md` | `10_contract_selection_oracle.md` §5.3 |
| Partner context + unified model | C2 (R1 training) | `arc_d_execution_plan.md` Phase R1, `contract_selection_analysis.md` §Option B | — |
| Oracle re-analysis | Post-C2 | `contract_selection_analysis.md` | `10_contract_selection_oracle.md` |
| Pass-threshold re-tune | Post-C2 | `r0_pass_threshold_protocol.md` (template) | `11_pass_threshold_decision.md` §6 |
| Deferred report sections | B3/D1 | `report_narrative_overlay.md` | `03_comparator_rankings.md` §4, §8 |
| H2H bid_rate caveat | All | `20_measurement_integrity_r0.md` L3 | All H2H reports |
| Rung-to-rung pipeline | Post-A2 | — | `23_phase0_to_r0_progression.md` (template) |
| Bid-level search | C2 (R1 training) | `r0_report_qa.md` Q4 | `05_c33_ablation_report.md` |
| Process lessons (W1–W6) | Pre-C2 | `21_r0_retrospective.md` §5 | — |
