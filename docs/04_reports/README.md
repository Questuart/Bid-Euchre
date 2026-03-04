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
  phase0/                  Phase 0 (bidless) report + charts
    phase0_bidless_20260207.md   (canonical, was r5)
    assets/charts/               (chart PNGs)
    archive/                     (r1-r4 superseded revisions)
  r0/                      Arc D R0 rung report + companions
    01_r0_promotion_report.md       (promotion decision)
    02_model_arc_r0.md              (canonical rung report)
    03_comparator_rankings.md       (v6 comparator battery)
    04_r0_experiment_summary.md     (H2H battery + thresholds)
    05_c33_ablation_report.md       (Gaussian wrapper ablation)
    06_dual_track_analysis.md       (dual-track + archetype analysis)
    07_h2h_pairwise_analysis.md     (H2H pairwise analysis)
    10_contract_selection_oracle.md (oracle regret analysis)
    11_pass_threshold_decision.md   (B0 threshold sweep)
    12_lambda_decision.md           (D0 lambda tuning decision)
    13_normalizer_offline_screen.md (Track E normalizer pre-screen)
    14_onemodel_decision.md         (OneModel comparison)
    20_measurement_integrity_r0.md  (methodology review)
    21_r0_retrospective.md          (development process retrospective)
    22_v1_v2_delta_review.md        (v1→v2 delta review)
    23_phase0_to_r0_progression.md  (Phase 0→R0 progression)
    archive/                        (superseded revisions)
  model_arc_d_dashboard.md  Cross-rung progression dashboard
```

## Index

### Arc D: OLSa-Hybrid Bidder

| Report | Date | Summary |
|--------|------|---------|
| [model_arc_d_dashboard.md](model_arc_d_dashboard.md) | 2026-02-22 | Cross-rung progression dashboard (snapshot) |
| [r0/01_r0_promotion_report.md](r0/01_r0_promotion_report.md) | 2026-02-22 | R0 promotion decision + gate threshold calibration |
| [r0/02_model_arc_r0.md](r0/02_model_arc_r0.md) | 2026-03-01 | R0 rung report (narrative refactor, 12 sections) |
| [r0/03_comparator_rankings.md](r0/03_comparator_rankings.md) | 2026-03-03 | Comparator battery rankings (v6, single-seat, GluttonStrategy, 8 bidders) |
| [r0/04_r0_experiment_summary.md](r0/04_r0_experiment_summary.md) | 2026-03-03 | H2H battery analysis + gate threshold calibration |
| [r0/05_c33_ablation_report.md](r0/05_c33_ablation_report.md) | 2026-03-03 | C33 ablation: Gaussian EV wrapper + bid-level search (+0.13 H2H pooled, +2.36 comparator gap) |
| [r0/06_dual_track_analysis.md](r0/06_dual_track_analysis.md) | 2026-03-03 | Dual-track rankings, archetype classification, roster scatter plots |
| [r0/07_h2h_pairwise_analysis.md](r0/07_h2h_pairwise_analysis.md) | 2026-03-03 | H2H pairwise analysis: full matrix, dominance, behavioral asymmetry |
| [r0/10_contract_selection_oracle.md](r0/10_contract_selection_oracle.md) | 2026-03-01 | Contract selection oracle: regret decomposition, pass-threshold dominance |
| [r0/11_pass_threshold_decision.md](r0/11_pass_threshold_decision.md) | 2026-03-02 | B0 threshold sweep decision: RETAIN t=0 (monotonic decline) |
| [r0/12_lambda_decision.md](r0/12_lambda_decision.md) | 2026-03-03 | D0 lambda tuning decision: RETAIN lambda=0.0 (self-play gain reversed in H2H) |
| [r0/13_normalizer_offline_screen.md](r0/13_normalizer_offline_screen.md) | 2026-03-03 | Track E normalizer pre-screen: NO_GO_DEFER_R1 (accuracy +4% but net_eppd -0.269) |
| [r0/14_onemodel_decision.md](r0/14_onemodel_decision.md) | 2026-03-03 | OneModel comparison: RETAIN separate models |
| [r0/20_measurement_integrity_r0.md](r0/20_measurement_integrity_r0.md) | 2026-03-03 | Methodology limitations + deferral costs (L1-L3 resolved/partially resolved) |
| [r0/21_r0_retrospective.md](r0/21_r0_retrospective.md) | 2026-03-02 | R0 development retrospective: process lessons, course corrections, R1 recommendations |
| [r0/22_v1_v2_delta_review.md](r0/22_v1_v2_delta_review.md) | 2026-03-03 | v1 to v2 delta review |
| [r0/23_phase0_to_r0_progression.md](r0/23_phase0_to_r0_progression.md) | 2026-03-01 | Phase 0→R0 progression: variance direction check, contract mix shift, role asymmetry |

Superseded revisions in `r0/archive/`.

Working copies of per-rung reports are generated to `data/reports/arc_d/` (gitignored).
Use `--snapshot` flag with dashboard script to update the committed snapshot.

### Phase 0: Bidless

| Report | Date | Summary |
|--------|------|---------|
| [phase0/phase0_bidless_20260207.md](phase0/phase0_bidless_20260207.md) | 2026-02-18 | Canonical report (16 charts, 12 sections) |

Superseded revisions (r1-r4) are in `phase0/archive/`.
