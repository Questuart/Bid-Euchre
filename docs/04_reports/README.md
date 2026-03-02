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
  r0/                      Arc D R0 rung report
    model_arc_r0_20260224.md
    archive/                     (superseded revisions)
  model_arc_d_dashboard.md  Cross-rung progression dashboard
```

## Index

### Arc D: OLSa-Hybrid Bidder

| Report | Date | Summary |
|--------|------|---------|
| [model_arc_d_dashboard.md](model_arc_d_dashboard.md) | 2026-02-22 | Cross-rung progression dashboard (snapshot) |
| [r0/model_arc_r0_20260224.md](r0/model_arc_r0_20260224.md) | 2026-02-24 | R0 full evaluation report (11-section) |
| [r0/r0_promotion_report.md](r0/r0_promotion_report.md) | 2026-02-25 | R0 promotion decision + gate threshold calibration |
| [r0/comparator_rankings.md](r0/comparator_rankings.md) | 2026-02-28 | Comparator battery rankings (v4, single-seat, GluttonStrategy, 7 bidders) |
| [r0/c33_ablation_report.md](r0/c33_ablation_report.md) | 2026-02-25 | C33 ablation: Gaussian EV wrapper effect (+0.21 net_eppd) |
| [r0/h2h_battery_analysis.md](r0/h2h_battery_analysis.md) | 2026-02-25 | H2H battery analysis + gate threshold calibration |
| [r0/contract_selection_oracle.md](r0/contract_selection_oracle.md) | 2026-03-01 | Contract selection oracle: regret decomposition, pass-threshold dominance |

Superseded revisions in `r0/archive/`.

Working copies of per-rung reports are generated to `data/reports/arc_d/` (gitignored).
Use `--snapshot` flag with dashboard script to update the committed snapshot.

### Phase 0: Bidless

| Report | Date | Summary |
|--------|------|---------|
| [phase0/phase0_bidless_20260207.md](phase0/phase0_bidless_20260207.md) | 2026-02-18 | Canonical report (16 charts, 12 sections) |

Superseded revisions (r1-r4) are in `phase0/archive/`.
