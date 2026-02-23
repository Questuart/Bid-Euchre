# Reports

Historical analysis reports for completed research phases.

Each report is a point-in-time snapshot with:
- Embedded charts (in `assets/<report_date>/`)
- Machine-readable provenance (`<report>_provenance.json`)
- Links to detailed source documents in `docs/02_agent/`

## Index

### Arc D: OLSa-Hybrid Bidder

| Report | Date | Phase | Summary |
|--------|------|-------|---------|
| [model_arc_d_dashboard.md](model_arc_d_dashboard.md) | 2026-02-22 | Arc D | Cross-rung progression dashboard (snapshot) |
| [model_arc_r0_20260222.md](model_arc_r0_20260222.md) | 2026-02-22 | Arc D | R0 baseline lock report (immutable snapshot) |

Working copies of per-rung reports are generated to `data/reports/arc_d/` (gitignored).
Use `--snapshot` flag with dashboard script to update the committed snapshot.

### Phase 0: Bidless

| Report | Date | Phase | Summary |
|--------|------|-------|---------|
| [phase0_bidless_20260207_r5.md](phase0_bidless_20260207_r5.md) | 2026-02-18 | Phase 0 (Bidless) | **Current** — Glutton correlations, per-contract §6d tables |
| [phase0_bidless_20260207_r4.md](phase0_bidless_20260207_r4.md) | 2026-02-16 | Phase 0 (Bidless) | Health-first restructure, 12 sections, 8 new charts, per-contract Ridge coefficients |
| [phase0_bidless_20260207_r3.md](phase0_bidless_20260207_r3.md) | 2026-02-08 | Phase 0 (Bidless) | Comprehensive rewrite with normalization fix, seat×contract chart, coefficient heatmap |
| [phase0_bidless_20260207_r2.md](phase0_bidless_20260207_r2.md) | 2026-02-07 | Phase 0 (Bidless) | Refactored report with chart versioning, t-test gate |
| [phase0_bidless_20260207.md](phase0_bidless_20260207.md) | 2026-02-07 | Phase 0 (Bidless) | Original report (immutable) |
