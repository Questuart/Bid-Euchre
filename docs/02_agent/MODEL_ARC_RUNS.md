# Model Arc Runs

Provenance registry for Arc D model promotion decisions.
Updated by promotion scripts (`scripts/write_r0_promotion.py` for R0,
gate runner for R1+).

## Arc D: OLSa-Hybrid Bidder

| Rung | Decision | OLSa_Full net_eppd | OLSa net_eppd | Attribution Gap | Date | Bundle |
|------|----------|--------------------|---------------|-----------------|------|--------|
| r0 | PROMOTED | 1.4837 | 1.6274 | -0.1437 | 2026-02-22 | `rung_bundle_r0.json` |

## Columns

- **Rung**: R0-R5 progression level
- **Decision**: PROMOTED / ADVANCED / HALT
- **OLSa_Full net_eppd**: Primary metric for the promotional arm (seed 42)
- **OLSa net_eppd**: Attribution arm metric (seed 42)
- **Attribution Gap**: OLSa_Full net_eppd - OLSa net_eppd
- **Date**: ISO date of promotion decision
- **Bundle**: Path to rung bundle JSON in `data/artifacts/arc_d/`
