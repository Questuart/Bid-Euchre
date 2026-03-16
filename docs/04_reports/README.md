# Reports

Historical analysis reports for completed research phases.

Each rung has its own directory containing:
- The canonical report (markdown with embedded chart references)
- Chart assets (`assets/charts/`)
- Machine-readable provenance (`*_provenance.json`)
- An `archive/` subdirectory for superseded revisions

## Directory Structure

```
docs/04_reports/
  arc_d_v1/                Arc D v1 era (OLSa-Hybrid, pre-lineage rebuild)
    model_arc_d_dashboard.md   Cross-rung progression dashboard (snapshot)
    phase0/                    Phase 0 (bidless) report + charts
    r0/                        Arc D R0 rung report + companions
    r1/                        Arc D R1 rung reports
    r1_5/                      Arc D R1.5 rung (objective-alignment)
    r1_6/                      Arc D R1.6 (placeholder)
  arc_d_v2/                Arc D v2 era (multi-model lineage rebuild)
    r0/                        R0 rung (v2 lineage)
    r1/                        R1 rung (v2 lineage)
    r2/                        R2 rung (v2 lineage)
    r3/                        R3 rung (v2 lineage)
    cross_rung_deltas.csv      Cross-rung comparison data
  archive/                 Miscellaneous archived reports
  codex_validation/        Codex review validation results
  AGENTS.md                Codex review guidelines for reports
```

## Index

### Arc D v1: OLSa-Hybrid Bidder

Reports from the original Arc D research arc, prior to the v2 lineage rebuild.

#### Dashboard

| Report | Date | Summary |
|--------|------|---------|
| [arc_d_v1/model_arc_d_dashboard.md](arc_d_v1/model_arc_d_dashboard.md) | 2026-02-22 | Cross-rung progression dashboard (snapshot) |

#### R0: First Bidding Model

| Report | Date | Summary |
|--------|------|---------|
| [arc_d_v1/r0/01_r0_promotion_report.md](arc_d_v1/r0/01_r0_promotion_report.md) | 2026-02-22 | R0 promotion decision + gate threshold calibration |
| [arc_d_v1/r0/02_model_arc_r0.md](arc_d_v1/r0/02_model_arc_r0.md) | 2026-03-01 | R0 rung report (narrative refactor, 12 sections) |
| [arc_d_v1/r0/03_comparator_rankings.md](arc_d_v1/r0/03_comparator_rankings.md) | 2026-03-03 | Comparator battery rankings (v6, single-seat, GluttonStrategy, 8 bidders) |
| [arc_d_v1/r0/04_r0_experiment_summary.md](arc_d_v1/r0/04_r0_experiment_summary.md) | 2026-03-03 | H2H battery analysis + gate threshold calibration |
| [arc_d_v1/r0/05_c33_ablation_report.md](arc_d_v1/r0/05_c33_ablation_report.md) | 2026-03-03 | C33 ablation: Gaussian EV wrapper + bid-level search |
| [arc_d_v1/r0/06_dual_track_analysis.md](arc_d_v1/r0/06_dual_track_analysis.md) | 2026-03-03 | Dual-track rankings, archetype classification, roster scatter plots |
| [arc_d_v1/r0/07_h2h_pairwise_analysis.md](arc_d_v1/r0/07_h2h_pairwise_analysis.md) | 2026-03-03 | H2H pairwise analysis: full matrix, dominance, behavioral asymmetry |
| [arc_d_v1/r0/10_contract_selection_oracle.md](arc_d_v1/r0/10_contract_selection_oracle.md) | 2026-03-01 | Contract selection oracle: regret decomposition, pass-threshold dominance |
| [arc_d_v1/r0/11_pass_threshold_decision.md](arc_d_v1/r0/11_pass_threshold_decision.md) | 2026-03-02 | B0 threshold sweep decision: RETAIN t=0 (monotonic decline) |
| [arc_d_v1/r0/12_lambda_decision.md](arc_d_v1/r0/12_lambda_decision.md) | 2026-03-03 | D0 lambda tuning decision: RETAIN lambda=0.0 |
| [arc_d_v1/r0/13_normalizer_offline_screen.md](arc_d_v1/r0/13_normalizer_offline_screen.md) | 2026-03-03 | Track E normalizer pre-screen: NO_GO_DEFER_R1 |
| [arc_d_v1/r0/14_onemodel_decision.md](arc_d_v1/r0/14_onemodel_decision.md) | 2026-03-03 | OneModel comparison: RETAIN separate models |
| [arc_d_v1/r0/20_measurement_integrity_r0.md](arc_d_v1/r0/20_measurement_integrity_r0.md) | 2026-03-03 | Methodology limitations + deferral costs |
| [arc_d_v1/r0/21_r0_retrospective.md](arc_d_v1/r0/21_r0_retrospective.md) | 2026-03-02 | R0 development retrospective |
| [arc_d_v1/r0/22_v1_v2_delta_review.md](arc_d_v1/r0/22_v1_v2_delta_review.md) | 2026-03-03 | v1 to v2 delta review |
| [arc_d_v1/r0/23_phase0_to_r0_progression.md](arc_d_v1/r0/23_phase0_to_r0_progression.md) | 2026-03-01 | Phase 0 to R0 progression |

Superseded revisions in `arc_d_v1/r0/archive/`.

#### R1.5: Objective-Alignment

| Report | Date | Summary |
|--------|------|---------|
| **[arc_d_v1/r1_5/rung_closeout.md](arc_d_v1/r1_5/rung_closeout.md)** | **2026-03-08** | **Canonical rung closeout -- ADVANCED** |
| [arc_d_v1/r1_5/measurement_integrity_r1_5.md](arc_d_v1/r1_5/measurement_integrity_r1_5.md) | 2026-03-08 | Methodology review: 8 limitations (0 blockers), 3 plan deviations |
| [arc_d_v1/r1_5/05_h2h_battery_full.md](arc_d_v1/r1_5/05_h2h_battery_full.md) | 2026-03-08 | Step 8: H2H battery FULL -- ADVANCED |
| [arc_d_v1/r1_5/06_ablation.md](arc_d_v1/r1_5/06_ablation.md) | 2026-03-08 | Step 9: ablation -- suit regression confirmed |
| [arc_d_v1/r1_5/07_promotion_decision.md](arc_d_v1/r1_5/07_promotion_decision.md) | 2026-03-08 | Step 10: promotion decision -- ADVANCED |
| [arc_d_v1/r1_5/01_offline_gate_x3_report.md](arc_d_v1/r1_5/01_offline_gate_x3_report.md) | 2026-03-08 | Step 3: Gate X3 offline ranking |
| [arc_d_v1/r1_5/02_gameplay_screen_report.md](arc_d_v1/r1_5/02_gameplay_screen_report.md) | 2026-03-08 | Step 5: 3-seed self-play screen |
| [arc_d_v1/r1_5/03_h2h_battery_quick.md](arc_d_v1/r1_5/03_h2h_battery_quick.md) | 2026-03-08 | Step 6: H2H battery QUICK -- Gate X4 PASS |
| [arc_d_v1/r1_5/04_risk_treatment.md](arc_d_v1/r1_5/04_risk_treatment.md) | 2026-03-08 | Step 7: risk treatment -- SKIPPED |
| [arc_d_v1/r1_5/00_step0_foundations.md](arc_d_v1/r1_5/00_step0_foundations.md) | 2026-03-07 | Implementation history: ActionValueBidder infrastructure |
| [arc_d_v1/r1_5/00_step1_dataset_generator.md](arc_d_v1/r1_5/00_step1_dataset_generator.md) | 2026-03-07 | Implementation history: counterfactual dataset generator, Gate X1 |
| [arc_d_v1/r1_5/00_step2_training_pipeline.md](arc_d_v1/r1_5/00_step2_training_pipeline.md) | 2026-03-08 | Implementation history: training pipeline, Gate X2 |
| [arc_d_v1/r1_5/08_gbt_prototype_evaluation.md](arc_d_v1/r1_5/08_gbt_prototype_evaluation.md) | 2026-03-11 | R1.5.3 Track B: GBT prototype -- VALIDATED |
| [arc_d_v1/r1_5/09_multi_rollout_diagnostic.md](arc_d_v1/r1_5/09_multi_rollout_diagnostic.md) | 2026-03-12 | R1.5.3 Phase 0: H14 CONFIRMED |
| [arc_d_v1/r1_5/10_model_label_matrix.md](arc_d_v1/r1_5/10_model_label_matrix.md) | 2026-03-12 | R1.5.3 Phase 1A: H15 CONFIRMED |
| **[arc_d_v1/r1_5/11_r1_5_arc_retrospective.md](arc_d_v1/r1_5/11_r1_5_arc_retrospective.md)** | **2026-03-12** | **Comprehensive R1.5 arc retrospective** |

#### Phase 0: Bidless

| Report | Date | Summary |
|--------|------|---------|
| [arc_d_v1/phase0/phase0_bidless_20260207.md](arc_d_v1/phase0/phase0_bidless_20260207.md) | 2026-02-18 | Canonical report (16 charts, 12 sections) |

Superseded revisions (r1-r4) are in `arc_d_v1/phase0/archive/`.

### Arc D v2: Multi-Model Lineage

Reports from the v2 lineage rebuild (GBT, two-stage, full OLS, modeloespecifico).
See `arc_d_v2/` for per-rung directories.

Working copies of per-rung reports are generated to `data/reports/arc_d/` (gitignored).
Use `--snapshot` flag with dashboard script to update the committed snapshot.
