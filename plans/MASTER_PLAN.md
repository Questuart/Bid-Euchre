# Master Plan — Bid Euchre R0 Finalization & R1 Readiness

**Date:** 2026-02-28
**Status:** ACTIVE
**Scope:** All outstanding work from R0 finalization through R1 readiness, including
contract selection analysis, report pipeline infrastructure, R0 report updates, and
R1 training cycle.

**Last updated by:** A1 completion + Path B decision sync (2026-03-02)

---

## How to Use This Plan

This is the **governing document** for all project work. When starting a new session:

1. Read this file first to understand what's in flight
2. Check the Phase Status table (§2) for current progress
3. Find your assigned work stream and read its sub-plan
4. Update this file when work items complete

Sub-plans contain implementation detail (file paths, function signatures, commands).
This plan contains sequencing, dependencies, and rationale.

---

## 1. Executive Summary

R0 is functionally complete — code, experiments, and notebooks are done. But R0 reports
are not finalized, and a critical analysis (contract selection) may require R0 experiment
re-runs before reports can be locked. Meanwhile, report pipeline infrastructure (skills,
chart runner, conventions) can be built in parallel since it's model-agnostic.

**The critical path to R1 runs through the contract selection decision:**

```
Contract Selection Step 0 (oracle analysis)
  │
  ├── Gap small → finalize R0 reports with current data → begin R1
  │
  └── Gap large → build calibrator → re-run R0 experiments → finalize R0 reports → begin R1
```

**Three parallel tracks can proceed immediately:**
1. Contract selection oracle analysis (determines the critical path)
2. Report pipeline infrastructure (needed regardless of calibrator outcome)
3. C33 ablation report refactor (R0-only, independent)

---

## 2. Phase Status

| Phase | Description | Status | Blocker |
|-------|-------------|--------|---------|
| **A1** | Contract selection Step 0 (oracle) | **COMPLETE** (#472, 2026-03-02) | — |
| **A2** | Report pipeline infrastructure | NOT STARTED | None — start immediately |
| **A3** | C33 ablation report refactor | NOT STARTED | None — start immediately |
| **B1** | Contract selection Steps 1–2 (calibrator) | **SKIPPED** (Path B) | — |
| **B2** | R0 experiment re-runs | **SKIPPED** (Path B) | — |
| **B3** | R0 report finalization | UNBLOCKED | None (A1 complete, calibrator skipped) |
| **B4** | Skills testing on R0 data | BLOCKED | A2 + B3 |
| **C1** | Dual-track + archetype analysis (C6) | BLOCKED | B3 |
| **C2** | R1 training cycle (PR-R1a) | BLOCKED | B3 |
| **D1** | R1 experiments + reports | BLOCKED | C2 + B4 (reports require validated skills) |

---

## 3. Work Streams

### Stream 1: Contract Selection Analysis (R0 Ablation)

**Why this matters:** The OLSa bidder selects suit 98.3% of the time. If a calibrator
can improve contract selection, it must be measured at R0 to preserve the ablation —
otherwise the calibrator effect is confounded with R1 changes (new features, opponent
context, more training data). Same logic as the C33 Gaussian wrapper ablation.

**Sub-plan:** `plans/contract_selection_analysis.md` (v3)

| Step | Work | Estimated Effort | Output |
|------|------|-----------------|--------|
| **Step 0** | Oracle/regret analysis | 1 PR (offline analysis notebook) | Oracle contract mix, regret distribution |
| **Step 1** | Calibrator prototype | 1–2 PRs (if Step 0 triggers) | Calibrator model + offline validation |
| **Step 2** | H2H validation | 1 PR (experiment run) | Calibrated vs uncalibrated H2H results |
| **Re-runs** | R0 experiment suite | Run-only (if calibrator adopted) | Updated eval, comparator, H2H data |
| **Report** | Calibrator ablation report | 1 PR (analogous to c33_ablation) | R0 ablation documented |

**Decision gate:** Step 0 result determines whether Steps 1–2 happen.
Two indicators, evaluated together:
- Oracle HIGH/LOW contract share (how often non-suit is optimal)
- Mean regret in utility space (how much utility is lost by current selection)

**Precedence rule:** Regret is the primary decision driver (it directly measures
utility loss). Contract mix is diagnostic context. Specifically:
- Mean regret > 0.1 utility → calibrator worth pursuing → Steps 1–2 → B2 re-runs
  (regardless of contract mix — regret could come from wrong-suit selection too)
- Mean regret ≤ 0.1 utility AND HIGH/LOW < 3% → calibrator not needed → proceed
  to B3 with current data
- Mean regret ≤ 0.1 utility AND HIGH/LOW ≥ 3% → contract selection matters but
  current model captures it adequately → proceed to B3 with current data, document
  the oracle mix for future reference

**Step 0 Result (2026-03-02, PR #472):**

Gate fired **CALIBRATOR_WARRANTED** (mean regret 3.92 >> 0.1 threshold). However,
the 3-way regret decomposition fundamentally reframed the problem:

| Category | % of total regret | Interpretation |
|----------|-------------------|----------------|
| Pass-threshold | **81.9%** | Model passes; oracle would bid (model conservatism) |
| Contract-selection | 16.9% | Both bid; model picks wrong contract |
| Over-bidding | 1.1% | Model bids; oracle would pass |

The plan assumed regret would come from contract mis-ranking (motivating a calibrator).
Instead, 82% comes from the pass threshold — the model declines to bid on hands where
the oracle would profit. Root cause: feature poverty in HIGH/LOW models (1 feature each).

**Decision: Path B selected** — skip calibrator, finalize R0, address in R1.
Rationale: calibrator addresses only 17% of regret; the dominant fix (feature enrichment
for HIGH/LOW) is already on the R1 roadmap. See `docs/04_reports/r0/contract_selection_oracle.md`.

**Sample-size note:** The sub-plan acceptance gate specifies ≥50,000 paired hands.
Step 0 was run in QUICK mode (40,000 hands = 10k deals × 4 seats). This exceeds
the repo-wide minimum for bias detection (2,000) and group-level inference (1,000)
by 20x. The 95% CIs are tight ([3.89, 3.95] for mean regret). A FULL-mode run
(200k hands) can be produced for archival purposes but would not change the decision
given the regret is 40x above the 0.1 threshold. The sub-plan gate was written
before the QUICK/FULL mode convention was established for oracle analyses.

**Key context for cold-start:**
- Paired outcome data already exists: `canonical_bidless_dataset_glutton_42_20260221_175752`
- Construction path (4 steps — direct join is NOT possible, tables have different granularity):
  1. **Filter** to canonical single-policy glutton run (eliminates strategy ambiguity)
  2. **Join** via existing `join_features_outcomes()` from `datasets/join.py` — bridges
     per-seat bidless ↔ per-hand outcomes on `(hand_id, contract_type, trump_suit)`
  3. **Pivot** wide on `(contract_type, trump_suit)` → 6 outcome columns per `(deal_id, seat)`
  4. **Validate** 6 rows per group pre-pivot, drop incomplete groups
- See `contract_selection_analysis.md` §Step 0 Construction Path for full detail
- Regret must be computed in **utility space** (EV − CVaR_penalty), NOT raw tricks
- The `HybridOLSaBidder._compute_ev()` formula is in `bidding.py:900–942`
- Pass is a valid action: `utility <= 0 → pass` (`bidding.py:1043`)

---

### Stream 2: Report Pipeline Infrastructure

**Why this matters:** R1+ reports need systematic production — the four-stage pipeline
(data → charts → report → narrative) replaces ad-hoc report writing. This infrastructure
is model-agnostic and should be built now regardless of the calibrator decision.

**Sub-plan:** `plans/report_narrative_overlay.md` (684 lines) — Phases 0, 3, 4, 5

| PR | Work | Estimated Effort | Depends On |
|----|------|-----------------|------------|
| **PR-N0a** | Generator data fixes (G1–G3) | Small code PR | None |
| **PR-N0b** | Chart runner script | Medium code PR | Resolve open items 4-5 |
| **PR-N3** | Report conventions + template registry | Doc PR | None |
| **PR-N4** | `/narrate-report` skill | Skill PR | PR-N3 |
| **PR-N5** | `/draft-rung-reports` skill | Skill PR | PR-N3 |

**Key context for cold-start:**
- Generator (`arc_d_report.py`) already supports `chart_dir` parameter — 10 PNG filenames
  are hardcoded in `_render_*()` functions but no script produces them yet
- Chart manifest: 11 charts mapped to existing `plot_*` functions in `diagnostics/`
- G1: Bundle comparator pointer stale (v1 → v4)
- G2: Bundle has no H2H battery reference
- G3: Report §8 (Semantic Gate) doesn't read gate checks from `promotion_decision_r0.json`
- Skill pattern: see `.claude/skills/reviewing-changes/SKILL.md` for the multi-phase template
- Five-question exec summary: What is this? What did we do? What did we find? Caveats? Decision?

---

### Stream 3: R0 Report Finalization

**Why this matters:** R0 reports carry stale v2 comparator data, lack narrative, have no
charts, and may need calibrator ablation data. They must be finalized before R1 begins
because R0 reports are the baseline comparison point.

**Sub-plan:** `plans/report_narrative_overlay.md` — Phases 1, 2

**Blocked on:** Stream 1 Step 0 result (determines whether data changes before finalization)

| PR | Work | Estimated Effort | Depends On |
|----|------|-----------------|------------|
| **PR-N1** | R0 rung report refactor | Large doc PR | PR-N0a, PR-N0b, Step 0 |
| **PR-N2** | Companion report consistency (= C2b-2) | Medium doc PR | PR-N1 |

**Reports to update (Phase 2 = C2b-2):**

| Report | Key Changes |
|--------|-------------|
| `h2h_battery_analysis.md` §3 | v2→v4 comparator data, field terminology fixes |
| `r0_promotion_report.md` | v2→v4 exec summary + comparator table, gate descriptions |
| `comparator_rankings.md` §4, §8 | Resolve placeholder sections (populate from FULL data or defer with rationale) |
| `measurement_integrity_r0.md` | Play strategy context (GluttonStrategy), L3 resolved |
| `docs/04_reports/README.md` | Stale directory listing, missing entries |

**Key context for cold-start:**
- v2 comparator: 4-way mode, GreedyStrategy, different numbers (e.g., modeloespecifico +2.291)
- v4 comparator: single-seat, GluttonStrategy, current numbers (e.g., modeloespecifico +1.587)
- The v2→v4 gap nearly doubled (0.624 → 1.132) — methodology change, not just data refresh
- **H2H field semantics (CRITICAL):** In H2H battery data, `bid_rate_a/b` = team auction-win
  frequency (NOT per-bidder bid propensity); `make_rate_a/b` = conditional on team winning bid.
  In single-seat comparator data, `bid_rate` = per-hand propensity. These are different estimands
  sharing similar names — do not conflate them in reports. See `report_narrative_overlay.md` P2-1.
- User's per-section notes for rung report are in `report_narrative_overlay.md` P1-2
- Econometric-style tables: borrow from `docs/04_reports/phase0/phase0_bidless_20260207.md`

---

### Stream 4: C33 Ablation Report Refactor

**Why this matters:** The C33 ablation report documents the Gaussian wrapper validation.
It's well-structured but the "selective restraint" mechanism needs empirical grounding.
R0-specific — no persistence to other rungs.

**Sub-plan:** `plans/c33_ablation_refactor_plan.md` (1,040 lines)

| Work | Estimated Effort | Depends On |
|------|-----------------|------------|
| Refactor report with replay diagnostics | 1–2 PRs | None |

**Key context for cold-start:**
- C33 ablation result: hybrid_olsa > olsa by +0.21 net_eppd (significant, CI excludes 0)
- Decision trace data NOT logged — requires replay through model artifact
- Replay: parse JSONL `hands` field → `get_hand_features()` → run both decision layers
- Must reconstruct: mu, sigma, P(make), EV, bid/pass for each hand × all 6 contracts
- The EV formula is in `bidding.py:900–942` (asymmetric payoff, continuity correction)

---

### Stream 5: Dual-Track & Roster Meta-Analysis (C6)

**Why this matters:** Side-by-side presentation of decision-quality (single-seat comparator)
and full-game (H2H self-play) rankings, with archetype segmentation and roster scatter plots.
Extends the comparator analysis to answer "do the two instruments agree?"

**Sub-plan:** `plans/report_narrative_overlay.md` — Phase 6
**Background:** `plans/comparator_dual_track_plan.md` (absorbed into Phase 6)

| PR | Work | Estimated Effort | Depends On |
|----|------|-----------------|------------|
| **PR-N7** | Dual-track report + archetype + scatter | Large report+viz PR | PR-N2 |

**Key context for cold-start:**
- Two estimands: decision-quality (declaring-only, every bid) vs full-game (declaring+defending, auction winners only)
- Both now use GluttonStrategy (confound resolved by C2c/#466)
- Archetype labels from single-seat data only (bid_rate = per-hand propensity)
  - AGGRESSIVE: bid_rate > 0.95 AND make_rate < 0.65 (fiveheadfred, rankthetank)
  - SELECTIVE: bid_rate < 0.50 (hybrid_olsa, modeloespecifico)
  - NEUTRAL: bid_rate > 0.95 AND make_rate ≥ 0.65 (stricthellraiser, olsa, olsa_full)
- **H2H field semantics differ:** `bid_rate_a/b` in H2H = team auction-win frequency (see Stream 3)
- Three scatter plots: bid_rate×make_rate, bid_rate×net_eppd, make_rate×net_eppd
- H2H absolute metrics available since #468 (schema v2): `abs_net_eppd_team0/team1`
- Completed prerequisites: C2c (#466), C3 (reruns), C4 (#468), C5 (#467), C2b-1 (#470)

---

### Stream 6: R1 Training Cycle (PR-R1a)

**Why this matters:** R1 is the first improvement rung — new training data, new model,
new features. All the pipeline infrastructure and R0 baselines must be locked before
R1 begins.

**Sub-plan:** `plans/arc_d_execution_plan.md` (v3) — Wave 3+
**Gap:** PR-R1a needs a concrete execution checklist (file paths, commands, validation
gates). The arc_d_execution_plan covers R1 at a high level but was written before the
calibrator question arose. **Create a detailed PR-R1a sub-plan when R0 is finalized.**

| Work | Estimated Effort | Depends On |
|------|-----------------|------------|
| R1 training data generation | Run-only | B3 (R0 finalized) |
| R1 model training (dual-arm) | Code + run | Training data |
| R1 bundle + gate | Code PR | Model artifacts |
| R1 eval runs (3 seeds, 50k deals) | Run-only | Bundle |
| R1 report production (using skills) | Pipeline run | PR-N4, PR-N5 |

**Key context for cold-start:**
- Dual-arm: OLSa_Full (promotional, forward-selected) + OLSa (attribution, locked 3/1/1)
- Primary metric: net_eppd; eppd is secondary diagnostic
- Gate thresholds (FULL-calibrated): delta_floor=0.180, regression=0.184
- R1 challenger must improve by +0.18 net_eppd over R0 incumbent in paired H2H
- Calibrator was SKIPPED (Path B) — R0 baseline has no calibrator, R1 does not inherit one
- PR-R2a (opponent context features via auction_transcript) can parallel — off critical path

**R1 design priorities from A1 oracle analysis:**
- **HIGH/LOW feature enrichment is the #1 priority.** The 1-feature models (offsuit_aces,
  offsuit_tens_count) are clearly insufficient. Consider lowering `min_improvement` threshold
  in `feature_selection.py` for non-suit contracts, or adding hand-crafted distributional
  features (suit spread, void count for HIGH; low-card connectivity for LOW).
- **Pass-threshold tuning:** Investigate whether `utility <= -X` (X > 0) recovers some of
  the 82% pass-threshold regret. Can be a quick sensitivity sweep without new models.
- **Cross-contract calibration (Option B):** A unified regression may be worth revisiting
  since feature poverty and calibration problems interact.

---

## 4. Dependency Graph

```
PHASE A — A1 COMPLETE, A2/A3 UNBLOCKED
──────────────────────────────────────────────────────
A1: ✓ COMPLETE (#472)                A2: Pipeline Infrastructure       A3: C33 Ablation
   Path B selected                      PR-N0a (generator fixes)          Report Refactor
   (calibrator skipped)                 PR-N0b (chart runner)
                                        PR-N3  (conventions)
                                        PR-N4  (narrate skill)
                                        PR-N5  (draft skill)

PHASE B — UNBLOCKED (Path B: no calibrator)
──────────────────────────────────────────────────────
              A1 result: Path B
                │
    B1: SKIPPED (calibrator addresses only 17% of regret)
    B2: SKIPPED (no calibrator to validate)
                │
           B3: R0 Report Finalization
               PR-N1 (rung report)
               PR-N2 (companion reports)
                │
           B4: Skills Testing
               PR-N6 (test on R0 data)

PHASE C — BLOCKED ON B3
──────────────────────────────────────────────────────
           B3 complete
                │
    ┌───────────┴───────────┐
    │                       │
C1: Dual-Track (C6)    C2: R1 Training
    PR-N7                   (PR-R1a)
    (report + viz)          │
                       R1 experiments
                            │
                       D1: R1 Reports ← also requires B4 (validated skills)
                       (uses A2 skills)
```

---

## 5. Execution Phases — Detailed Sequencing

### Phase A: Immediate Parallel Work (no blockers)

All three streams can start immediately and run in parallel. Assign to separate agents
or work sequentially — no dependencies between them.

**A1 — Contract Selection Oracle Analysis** ✓ COMPLETE (#472, 2026-03-02)
- Deliverable: Oracle contract mix, regret distribution, Path B decision
- Report: `docs/04_reports/r0/contract_selection_oracle.md`
- Notebook: `notebooks/arc_d/r0/55_contract_selection_oracle.py`
- Key finding: pass-threshold regret (82%) dominates contract-selection regret (17%)

**A2 — Report Pipeline Infrastructure**
- Effort: ~5 PRs across multiple sessions
- Order: PR-N0a ∥ PR-N0b ∥ PR-N3 → PR-N4 ∥ PR-N5
- Deliverable: Chart runner, generator fixes, conventions doc, two skills
- Sub-plan: `plans/report_narrative_overlay.md` Phases 0, 3, 4, 5

**A3 — C33 Ablation Report Refactor**
- Effort: 1–2 PRs
- Deliverable: Empirically grounded ablation report with replay diagnostics
- Sub-plan: `plans/c33_ablation_refactor_plan.md`

### Phase B: Calibrator Decision & R0 Finalization (blocked on A1)

**B1 — Calibrator Build** ✗ SKIPPED (Path B — calibrator addresses only 17% of regret)
- Gate fired CALIBRATOR_WARRANTED but regret decomposition showed the prescribed
  remedy is mismatched to the dominant problem (model conservatism, not contract ranking)
- R1 feature enrichment for HIGH/LOW is the appropriate fix

**B2 — R0 Experiment Re-runs** ✗ SKIPPED (no calibrator to validate)

**B3 — R0 Report Finalization** (UNBLOCKED — A1 complete, B1/B2 skipped)
- Uses current R0 data (no calibrator re-runs)
- Effort: 2 PRs (PR-N1 rung report refactor, PR-N2 companion consistency)
- Sub-plan: `plans/report_narrative_overlay.md` Phases 1, 2
- Note: PR-N2 must also update stale v2 comparator data in promotion report and
  C33 arc-context (see §7 What's Done)

**B4 — Skills Testing**
- Run `/narrate-report` on the finalized R0 rung report (validates the skill)
- Run `/draft-rung-reports r0` and compare against actual R0 reports
- Effort: 1 PR (PR-N6)
- Sub-plan: `plans/report_narrative_overlay.md` P4-2, P5-3

### Phase C: Post-R0 Finalization (blocked on B3)

**C1 — Dual-Track + Archetype (C6)**
- Side-by-side comparator vs H2H analysis
- Effort: 1 large PR (PR-N7)
- Sub-plan: `plans/report_narrative_overlay.md` Phase 6

**C2 — R1 Training Cycle**
- New training data, model, bundle, gate
- Effort: multiple PRs
- Sub-plan: `plans/arc_d_execution_plan.md` (Wave 3+)
- **Gap:** Create `plans/r1_training_plan.md` before starting — concrete commands,
  validation gates, file paths. Must account for calibrator if adopted.

### Phase D: R1 Reports (blocked on C2 + B4)

- Run the four-stage pipeline on R1 data
- Use `/narrate-report` and `/draft-rung-reports` skills from A2
- **Requires B4 complete** — skills must be validated on R0 data before using for R1
- Effort: Pipeline runs + review
- No separate sub-plan needed — skills + conventions handle this

---

## 6. Sub-Plan Registry

| Plan File | Governs | Status | Streams |
|-----------|---------|--------|---------|
| **`plans/MASTER_PLAN.md`** | All work sequencing | ACTIVE | All |
| **`plans/contract_selection_analysis.md`** | Oracle analysis + calibrator | Step 0 COMPLETE, Steps 1–2 SKIPPED (v3) | 1 |
| **`plans/report_narrative_overlay.md`** | Pipeline, reports, skills, C6 | ACTIVE (684 lines) | 2, 3, 5 |
| **`plans/c33_ablation_refactor_plan.md`** | C33 report refactor | ACTIVE (1,040 lines) | 4 |
| **`plans/arc_d_execution_plan.md`** | Full Arc D (R0 done, R1+ remaining) | ACTIVE (v3) | 6 |
| `plans/comparator_dual_track_plan.md` | C6 background (absorbed into report_narrative_overlay P6) | REFERENCE | 5 |
| `plans/bidder_correctness_fixes.md` | Fixes A/B/C | COMPLETE (#463–#465) | — |
| `plans/comparator_rankings_refactor_plan.md` | Rankings report v4 | COMPLETE (#470) | — |
| `plans/comparator_single_seat.md` | Single-seat methodology | COMPLETE (#464) | — |
| `plans/comparator_experiment_redesign.md` | Comparator redesign | COMPLETE (#464) | — |
| `plans/comparator_rankings_review_notes.md` | Review notes | REFERENCE | — |
| `plans/c33_ablation_review_notes.md` | Review notes | REFERENCE (consumed) | — |
| `plans/c33_ablation_plan_prompt.md` | Agent handoff | REFERENCE (consumed) | — |

**Plans to create (when triggered):**
- ~~`plans/calibrator_implementation.md`~~ — N/A (B1 skipped, Path B selected)
- `plans/r1_training_plan.md` — before starting R1 training cycle (C2)

---

## 7. Key Project State (for cold-start recovery)

### What's Done

- **R0 code:** All merged (#389–#396, #439–#441)
- **R0 experiments:** All complete (eval, comparator v4, H2H v2 QUICK+FULL)
- **R0 notebooks:** 6/6 passing (#428–#438), plus oracle notebook (#472)
- **Comparator overhaul:** Wave 1 (#463–#465), dual-track code (#466–#468), rankings (#470)
- **A1 oracle analysis:** COMPLETE (#472) — regret 3.92 [3.89, 3.95], Path B selected
- **R0 reports:** 7 exist; most need updating before B3 can be marked complete:
  - `r0_promotion_report.md` — still cites v2 comparator numbers (v2 battery, +2.291 gap)
  - `model_arc_r0_20260224.md` — templated placeholder paths in §11 reproduction
  - `c33_ablation_report.md` — arc-context references "Comparator battery v2"
  - `contract_selection_oracle.md` — NEW, current (merged #472)
  - `comparator_rankings.md` — current (merged #470)
  - `h2h_battery_analysis.md` — needs v2→v4 comparator cross-references

### Key Results (R0)

| Metric | OLSa (attribution) | OLSa_Full (promotional) |
|--------|--------------------|-----------------------|
| net_eppd (seed 42) | +1.627 | +1.484 |
| bid_rate | 63.2% | 82.8% |
| make_rate | 87.3% | 83.3% |
| R² | 0.18–0.22 | 0.24–0.29 |

- **Attribution gap:** −0.143 (constrained arm slightly outperforms — benign at R0)
- **C33 ablation:** +0.21 net_eppd (Gaussian wrapper, significant)
- **Comparator rank:** 2nd/7 (modeloespecifico +1.587, hybrid_olsa +0.455, gap 1.132)
- **Gate thresholds:** delta_floor=0.180, regression=0.184 (FULL-calibrated)
- **Contract mix:** 98.3% suit / 0.9% low / 0.8% high (oracle: 68.1% suit / 17.9% low / 14.0% high)
- **Oracle regret:** 3.92 utility [3.89, 3.95]; 82% pass-threshold, 17% contract-selection

### Key Artifacts

| Artifact | Path |
|----------|------|
| R0 eval run | `data/runs/arc_d_eval_r0_42_20260221_180253/` |
| R0 bundle | `data/artifacts/arc_d/r0/rung_bundle_r0.json` |
| R0 promotion decision | `data/artifacts/arc_d/r0/promotion_decision_r0.json` |
| Comparator battery v4 | `data/artifacts/arc_d/r0/comparator_battery_r0_v4.json` |
| Comparator CIs v4 | `data/artifacts/arc_d/r0/comparator_cis_r0_v4.json` |
| H2H battery (QUICK) | `data/artifacts/arc_d/r0/h2h_battery_quick_v2.json` |
| H2H battery (FULL) | `data/artifacts/arc_d/r0/h2h_battery_full_v2.json` |
| Gate thresholds (R1) | `data/artifacts/arc_d/r0/gate_thresholds_r1.json` |
| Training data | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| OLSa model | `data/artifacts/arc_d/r0/hybrid_r0.json` |
| OLSa_Full model | `data/artifacts/arc_d/r0/hybrid_r0_full.json` |

### Key Files (for implementation)

| Area | Files |
|------|-------|
| Bidding policies | `src/bid_euchre/strategy/bidding.py` (OLSaBidder L691, HybridOLSaBidder L778) |
| Feature extraction | `src/bid_euchre/features/hand_eval.py` (39 features) |
| Report generator | `src/bid_euchre/reporting/arc_d_report.py` (1,244 lines, 11 sections) |
| Chart library | `src/bid_euchre/diagnostics/charts.py`, `model_charts.py`, `auction_charts.py`, `strategy_charts.py` |
| Eval dataset parser | `src/bid_euchre/datasets/eval_dataset.py` |
| Bundle validator | `src/bid_euchre/validation/arc_d_bundle.py` |
| Gate runner | `src/bid_euchre/validation/arc_d_gate.py` |
| Semantic gate | `src/bid_euchre/diagnostics/semantic_gate.py` (12+3 checks) |
| Feature-outcome join | `src/bid_euchre/datasets/join.py` |
| Comparator runner | `scripts/internal/run_auction_comparator.py` |
| H2H battery runner | `scripts/internal/run_arc_d_h2h_battery.py` |
| CI extractor | `scripts/internal/extract_comparator_cis.py` |
| Threshold calibrator | `scripts/internal/calibrate_arc_d_thresholds.py` |

### Repo Conventions (critical for agents)

- **Worktree-only:** All code changes in `git worktree add ../Bid-Euchre-<branch> -b <branch>`
- **Runner:** Always `uv run` (never raw `python` or `pip`)
- **Validation:** `make check-quiet` before PRs (repo-lint + ruff + pytest + notebook-check + docs-check)
- **Determinism:** `--seed <int>` required for all experiments
- **Data policy:** Never commit `data/runs/`, `data/reports/`, `data/models/`
- **One concept per PR**, use `.github/pull_request_template.md`
- **Contract-type faceting:** Every chart/table MUST facet by contract_type or justify pooling
- **Team breakout:** Matchup tables MUST show team0/team1 separately

---

## 8. Completion Checklist

### Phase A (parallel, no blockers)
- [x] A1: Oracle contract mix computed, regret distribution reported, go/no-go decision made (#472)
- [ ] A2-a: PR-N0a merged (generator data fixes G1–G3)
- [ ] A2-b: PR-N0b merged (chart runner script)
- [ ] A2-c: PR-N3 merged (report conventions + template registry)
- [ ] A2-d: PR-N4 merged (`/narrate-report` skill)
- [ ] A2-e: PR-N5 merged (`/draft-rung-reports` skill)
- [ ] A3: C33 ablation report refactored with replay diagnostics

### Phase B (blocked on A1 — now unblocked)
- [x] B1: Calibrator decision documented — **Path B: SKIPPED** (regret decomposition shows calibrator addresses only 17%)
- N/A B1-a: ~~Calibrator prototype~~ (skipped)
- N/A B1-b: ~~Calibrator H2H validation~~ (skipped)
- N/A B2: ~~R0 experiments re-run~~ (skipped)
- N/A B2-a: ~~Calibrator ablation report~~ (skipped)
- [ ] B3-a: PR-N1 merged (R0 rung report refactor with charts + narrative)
- [ ] B3-b: PR-N2 merged (companion report consistency = C2b-2)
- [ ] B4: PR-N6 merged (skills tested on R0 data)

### Phase C (blocked on B3)
- [ ] C1: PR-N7 merged (dual-track + archetype + scatter = C6)
- [ ] C2-a: R1 training plan created (`plans/r1_training_plan.md`)
- [ ] C2-b: R1 training data generated
- [ ] C2-c: R1 model trained (dual-arm)
- [ ] C2-d: R1 bundle + gate created
- [ ] C2-e: R1 eval runs complete (3 seeds)

### Phase D (blocked on C2 + B4)
- [ ] D1-a: R1 charts generated (chart runner)
- [ ] D1-b: R1 rung report generated + narrated (`/narrate-report`)
- [ ] D1-c: R1 companion reports drafted (`/draft-rung-reports`)
- [ ] D1-d: R1 reports reviewed and finalized

---

## 9. Plan Maintenance

Update this file when:
- A work item completes (check the box, add PR number)
- A phase transitions (update Phase Status table)
- A conditional branch resolves (B1 calibrator decision)
- A new sub-plan is created (add to Sub-Plan Registry)
- A blocking issue is discovered (add to Phase Status blocker column)

**MEMORY.md** should reference this file and track PR numbers. This file tracks
sequencing and status. Sub-plans track implementation detail.
