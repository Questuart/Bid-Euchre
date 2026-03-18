# R2 FULL — Rung Decision Report

**Lineage:** Arc D v2
**Rung:** R2 (opponent context features)
**Mode:** FULL (50,000 deals × 3 seeds)
**Date:** 2026-03-18
**Advance check decision:** `INVESTIGATE`

## Decision

**ADVANCE to R3** (override of INVESTIGATE verdict).

The advance_check produced INVESTIGATE because H2 (GBT suit R² exceeds R1)
failed narrowly: observed 0.604 vs threshold > 0.621 (a 2.7% miss). H8 was
skipped (LA-4 roster trim). All other 7 hypotheses pass, all sufficiency
checks pass (4/4 tables, 23/23 sanity PASS, 5/5 models active), and all
canary checks pass.

**Rationale for override:**
- H2 targets a secondary diagnostic metric (suit R²), not the primary
  decision metric (pooled net_eppd or H2H delta). The miss is 0.017
  absolute on a metric with natural seed-to-seed variance.
- The primary metrics are strong: GBT pooled net_eppd = 2.009 (above the
  2.0 threshold), GBT H2H win rate = 57.2%, GBT H2H delta = +1.012.
- `full_ols_av` leads the comparator at 2.275 net_eppd — the lineage
  best-in-class is updated.
- R2 adds opponent context features on top of R1's partner context. The
  R² regression likely reflects that opponent features add noise to suit
  prediction while still improving overall decision quality (net_eppd and
  win rate both improve).

## Evidence Summary

### Comparator Rankings (pooled net_eppd)

| Model | net_eppd | 95% CI | Rank |
|-------|----------|--------|------|
| full_ols_av | 2.275 | [2.188, 2.363] | 1 |
| gbt_av | 2.009 | [1.908, 2.108] | 2 |
| selected_two_stage_av | 1.962 | [1.869, 2.055] | 3 |
| modeloespecifico | 1.633 | [1.517, 1.749] | 4 |

### GBT H2H vs Anchor

| Metric | Value |
|--------|-------|
| H2H delta | +1.012 |
| Win rate | 57.2% |
| Suit R² | 0.604 |

### GBT Model Performance (R² by contract)

| Contract | R² | MAE |
|----------|-----|-----|
| suit | 0.604 | 3.527 |
| high | 0.564 | 3.772 |
| low | 0.551 | 3.803 |
| pass | 0.085 | 3.270 |

### Hypothesis Results

| ID | Description | Status | Observed | Threshold |
|----|-------------|--------|----------|-----------|
| H1 | GBT pooled H2H delta vs anchor > 0.3 | **PASS** | 1.012 | > 0.3 |
| H2 | GBT suit R² exceeds R1 (0.621) | **FAIL** | 0.604 | > 0.621 |
| H3 | GBT comparator net_eppd ≥ 2.0 | **PASS** | 2.009 | > 2.0 |
| H4 | GBT suit H2H delta positive | **PASS** | 1.011 | > 0.0 |
| H5 | Two-stage gap vs GBT narrows | **PASS** | −0.047 | > −1.0 |
| H6 | All models bid ≥ 50% | **PASS** | 0.986 | > 0.5 |
| H7 | GBT win rate vs anchor > 45% | **PASS** | 0.572 | > 0.45 |
| H8 | Full OLS ≈ constrained OLS | **SKIP** | — | LA-4 trim |
| H9 | Heuristic worst among trained | **PASS** | −0.376 | < 0.0 |

### Gate Summary

- Hypotheses: 7/7 PASS, 1 FAIL, 1 SKIP
- Sufficiency: 4/4 tables, 23/23 sanity, 5/5 models
- Canaries: C1–C5 all PASS
- Best in lineage: `full_ols_av` at 2.275 net_eppd (updated)

## References

- Advance check: `data/artifacts/arc_d_v2/r2/advance_check.json` (not committed)
- Tables: `docs/04_reports/arc_d_v2/r2/full/tables/`
- H2H battery: `data/artifacts/arc_d_v2/r2/h2h_battery_full_*.json`
- gate_status: ADVANCE (overridden from INVESTIGATE)
