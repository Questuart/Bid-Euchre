# Model Arc Runs

Provenance registry for Arc D model promotion decisions.
Updated by promotion scripts (`scripts/write_r0_promotion.py` for R0,
gate runner for R1+).

## Arc D: OLSa-Hybrid Bidder

| Rung | Decision | OLSa_Full net_eppd | OLSa net_eppd | Attribution Gap | Date | Bundle |
|------|----------|--------------------|---------------|-----------------|------|--------|
| r0 | PROMOTED | 1.9323 | 1.9529 | -0.0207 | 2026-03-04 | `rung_bundle_r0.json` |

## Columns

- **Rung**: R0-R5 progression level
- **Decision**: PROMOTED / ADVANCED / HALT
- **OLSa_Full net_eppd**: Primary metric for the promotional arm (seed 42)
- **OLSa net_eppd**: Attribution arm metric (seed 42)
- **Attribution Gap**: OLSa_Full net_eppd - OLSa net_eppd
- **Date**: ISO date of promotion decision
- **Bundle**: Path to rung bundle JSON in `data/artifacts/arc_d/`

## Report Generation

Per-rung reports with rich analysis can be generated using:

```bash
PYTHONPATH=src uv run python -c "
from bid_euchre.datasets.eval_dataset import build_eval_dataset
from bid_euchre.reporting.arc_d_report import generate_arc_d_rung_report
df = build_eval_dataset('data/runs/<EVAL_RUN>/logs/<LOG>.jsonl')
report = generate_arc_d_rung_report(
    'data/artifacts/arc_d/r0/rung_bundle_r0.json',
    decision_path='data/artifacts/arc_d/r0/promotion_decision_r0.json',
    eval_df=df,
    output_path='data/reports/arc_d/r0_report.md',
)
"
```

Cross-rung dashboard:

```bash
PYTHONPATH=src uv run python scripts/internal/generate_arc_dashboard.py \
    --artifacts-base data/artifacts/arc_d \
    --output data/reports/arc_d/dashboard.md \
    --snapshot  # also write to docs/04_reports/
```
