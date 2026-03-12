# Measurement Integrity Review — R1.5

## Header

| Field | Value |
|-------|-------|
| **Arc** | D (OLSa-Hybrid Bidder) |
| **Rung** | R1.5 (objective-alignment) |
| **Date** | 2026-03-08 |
| **Reviewer** | Claude (automated closeout review) |
| **gate_status** | ADVANCED |

## Evaluation Batteries

| Battery | Purpose | Script Path | Deal Count | Seed | Version |
|---------|---------|-------------|------------|------|---------|
| H2H battery (QUICK) | Screening — delta sign check | scripts/internal/run_arc_d_h2h_battery.py | 2,500/matchup | 42 | v1 |
| H2H battery (FULL) | Definitive — promotion gate | scripts/internal/run_arc_d_h2h_battery.py | 50,000/matchup | 42 | v1 |
| Gate X3 (offline ranking) | Offline model quality screen | scripts/internal/evaluate_gate_x3.py | 250 deals (test split) | 42 | v1 |
| Gate X2 (training) | Model R² check | scripts/internal/train_action_value.py | 2,500 (QUICK) | 42 | v1 |
| Gate X1 (dataset) | Schema + coverage sanity | scripts/internal/generate_action_value_dataset.py | 2,500 (QUICK) | 42 | v1 |
| Self-play screen | Catastrophic behavior check | experiments/run_experiment.py | 2,500 x 3 seeds | 42/43/44 | v1 |

## Known Methodological Limitations

| ID | Description | Category | Notes |
|----|-------------|----------|-------|
| L1 | Single-rollout oracle in X3 | (a) | Oracle built from 1 rollout/action; spec assumed averaged rollouts. Causes noisy top-1 metric. Adjudicated non-blocking. |
| L2 | QUICK-trained models used for FULL H2H | (b) | Plan Step 4 specifies FULL retraining; deferred to v2. See PD-1 below. |
| L3 | Single seed (42) for FULL battery | (b) | Cross-seed validation deferred. QUICK self-play used 3 seeds (42/43/44); FULL H2H is single-seed. |
| L4 | 3-bidder roster | (a) | Only AV v1 + 2 R0 variants. No R1 variants, no ModeloEspecifico, no broader comparator set. Accepted for v1 scope. |
| L5 | Comparator battery not run | (b) | Plan Step 8 specifies H2H + comparator. Comparator deferred — H2H alone is sufficient for ADVANCED decision. See PD-3 below. |
| L6 | No intermediate ablation bidder | (a) | Objective and decision-layer effects are confounded. Separating them would require an intermediate bidder (net_points objective + R0 decision layer). Not built. |
| L7 | Pass model R² = 0.046 | (a) | Pass model has very low predictive power. Cross-model calibration between pass and bid models may cause suboptimal pass/bid decisions. Manifests as near-zero pass rate in gameplay. |
| L8 | bid_rate conflation in H2H | (a) | Inherited from R0 (R0 L3 residual). H2H bid_rate mixes voluntary and forced bids in contested auctions. Not a new R1.5 issue. |

### Category Key

- **(a) Inherent:** Known limitation accepted for this design; no fix without redesign
- **(b) Deferrable:** Could be fixed; deferred with explicit cost analysis
- **(c) Blocker:** Must be fixed before promotion (per `05_rigor.md`)

No (c)-class items exist for R1.5. The decision is ADVANCED (not PROMOTED),
so promotion-blocking rigor requirements are not binding.

## Plan Deviations

Three formal deviations from the governing plan (`plans/r1_5_training_plan.md`):

### PD-1: FULL Retraining Deferred

| Dimension | Cost |
|-----------|------|
| **Fix-now** | 1 PR (rerun dataset generator at FULL, retrain). ~2-3 hours compute for 50k-deal dataset + training. Then re-run FULL H2H battery (~73 min). Total: ~1 day with PR overhead. |
| **Fix-later + compounding** | Same fix cost. No crosswalk needed — QUICK-trained and FULL-trained models would use the same artifact schema. Per-rung compounding: if v2 also skips FULL retraining, "QUICK-trained" becomes an unvalidated assumption across two rungs. |
| **Never-fix** | QUICK-trained models may have higher prediction variance than FULL-trained. Pass model R² (0.046) is particularly affected. If model accuracy is the limiting factor for suit regression, FULL retraining could help; if it is model expressiveness (OLS linearity), it would not. |

**Decision:** Deferred to v2. The FULL H2H battery tests gameplay outcomes, not
model accuracy. If v2 addresses the suit regression through model architecture
changes, FULL retraining should be done simultaneously.

### PD-2: Step 7 (Risk Treatment) Skipped

| Dimension | Cost |
|-----------|------|
| **Fix-now** | Implement pass threshold and/or CVaR penalty in ActionValueBidder. ~1-2 PRs + re-run H2H at FULL scale. |
| **Fix-later** | Same implementation cost. No compounding — risk parameters are additive to the base model. |
| **Never-fix** | Risk-neutral bidding may leave points on the table for marginal hands. However, R0 Track D RETAIN lambda=0.0 showed risk aversion hurts H2H performance. The v1 bidder's bid=4 strategy is naturally low-risk. |

**Decision:** Skipped per plan Step 6 decision tree (delta > 0.0 → proceed to
FULL). Available for v2 if suit deficit is addressed first.

### PD-3: Comparator Battery Deferred

| Dimension | Cost |
|-----------|------|
| **Fix-now** | Run single-seat comparator battery (~20k deals/bidder, ~30 min). 1 PR for report. |
| **Fix-later** | Same cost. No compounding — comparator is independent of H2H. |
| **Never-fix** | Absolute metric positioning (vs GluttonStrategy sentinels) is unknown for AV v1. Does not affect the ADVANCED decision since H2H evidence is definitive. Would be required for PROMOTED decision in v2. |

**Decision:** Deferred. CI_low < 0.180 regardless of comparator results; the
comparator cannot change the ADVANCED outcome.

## Contract-Type Faceting Compliance

Per repository convention, every metric claim must be faceted by contract_type
or justify pooling.

| Report | Faceting Status |
|--------|-----------------|
| rung_closeout.md | Faceted: per-contract deltas in executive summary and H2H section |
| 05_h2h_battery_full.md | Faceted: section 4 contract-type table |
| 06_ablation.md | Faceted: section 3 contract-type attribution table |
| 03_h2h_battery_quick.md | Pooled only (QUICK — per-contract data not measured) |
| 02_gameplay_screen_report.md | Contract mix distribution reported; per-contract deltas not applicable (self-play) |
| 01_offline_gate_x3_report.md | Per-family R² and choice rates reported |
| 04_risk_treatment.md | Skip rationale — no contract-specific data needed |
| 00_step0_foundations.md | Infrastructure — no metrics to facet |
| 00_step1_dataset_generator.md | All 4 contract families validated in Gate X1 |
| 00_step2_training_pipeline.md | Per-contract R² in Gate X2 table |
| 07_promotion_decision.md | Per-contract deltas in section 4 (next steps) |

## Blockers

None. All items are category (a) inherent or (b) deferrable. No (c)-class
blockers exist.

The ADVANCED decision does not require resolution of (b) items. For a future
PROMOTED decision (v2), PD-1 (FULL retraining) and PD-3 (comparator battery)
should be resolved, and L3 (single seed) should be addressed.

## Sign-off

- [x] All evaluation batteries listed
- [x] All known limitations classified (a/b/c)
- [x] All (b) items have deferral cost descriptions (three-dimensional)
- [x] No (c) items remain unresolved
- [x] Rigor firewall applied (05_rigor.md blockers are category (c))
- [x] Plan deviations formally documented with cost analysis
- [x] Contract-type faceting compliance checked across suite
