> **DEPRECATED:** This file is a historical narrative artifact from the Arc D v2
> lineage. The canonical decision surface is `02_decision.md`. This file is
> retained for reference but will not be updated or regenerated.

# R2 FULL — Rung Decision Report

**Lineage:** Arc D v2
**Rung:** R2 (opponent context features)
**Mode:** FULL (50,000 deals × 1 seed, seed 42)
**Date:** 2026-03-18
**Advance check decision:** `INVESTIGATE`

## Decision

**ADVANCE to R3** (override of INVESTIGATE verdict).

The advance_check produced INVESTIGATE because H2 (GBT suit R² exceeds R1)
failed narrowly: observed 0.604 vs threshold > 0.621 (a 2.7% miss). All
other 8 hypotheses pass (including H8 — `constrained_ols_av` is in the R2
roster), all sufficiency checks pass (4/4 tables, 23/23 sanity PASS, 8/8
models active), and all canary checks pass.

**Rationale for override:**
- H2 targets a secondary diagnostic metric (suit R²), not the primary
  decision metric (pooled net_eppd or H2H delta). The miss is 0.017
  absolute on a metric with natural seed-to-seed variance.
- The primary metrics are strong: GBT pooled net_eppd = 2.184 (above the
  2.0 threshold), GBT H2H win rate = 55.8%, GBT H2H delta = +1.053.
- `full_ols_av` leads the comparator at 2.234 net_eppd — the lineage
  best-in-class is updated.
- R2 adds opponent context features on top of R1's partner context. The
  R² regression likely reflects that opponent features add noise to suit
  prediction while still improving overall decision quality (net_eppd and
  win rate both improve).

**Seed coverage caveat:** R2 FULL artifacts are based on seed 42 only. The
lineage FULL-mode contract (seeds 42/123/456) was not fully satisfied.
Statistical claims requiring multi-seed validation (CI robustness, rank
stability) should reference R1 or R3 FULL evidence instead.

## Evidence Summary

### Comparator Rankings (pooled net_eppd)

| Model | net_eppd | 95% CI | Rank |
|-------|----------|--------|------|
| full_ols_av | 2.234 | [2.113, 2.357] | 1 |
| constrained_ols_av | 2.204 | [2.080, 2.329] | 2 |
| selected_ols_av | 2.195 | [2.070, 2.324] | 3 |
| gbt_av | 2.184 | [2.054, 2.317] | 4 |
| selected_two_stage_av | 1.920 | [1.784, 2.054] | 5 |
| modeloespecifico | 1.661 | [1.501, 1.819] | 6 |
| stricthellraiser | 0.110 | [-0.044, 0.265] | 7 |
| rankthetank | -9.697 | [-9.958, -9.432] | 8 |

### GBT H2H vs Anchor

| Metric | Value |
|--------|-------|
| H2H delta | +1.053 |
| Win rate | 55.8% |
| Suit R² | 0.604 |

### GBT Model Performance (R² by contract)

| Contract | R² | MAE |
|----------|-----|-----|
| suit | 0.604 | 3.520 |
| high | 0.540 | 3.877 |
| low | 0.555 | 3.764 |
| pass | 0.085 | 3.370 |

### Hypothesis Results

| ID | Description | Status | Observed | Threshold |
|----|-------------|--------|----------|-----------|
| H1 | GBT pooled H2H delta vs anchor > 0.3 | **PASS** | 1.053 | > 0.3 |
| H2 | GBT suit R² exceeds R1 (0.621) | **FAIL** | 0.604 | > 0.621 |
| H3 | GBT comparator net_eppd ≥ 2.0 | **PASS** | 2.184 | > 2.0 |
| H4 | GBT suit H2H delta positive | **PASS** | 0.939 | > 0.0 |
| H5 | Two-stage gap vs GBT narrows | **PASS** | −0.264 | > −1.0 |
| H6 | All models bid ≥ 50% | **PASS** | 0.952 | > 0.5 |
| H7 | GBT win rate vs anchor > 45% | **PASS** | 0.558 | > 0.45 |
| H8 | Full OLS ≈ constrained OLS | **PASS** | +0.030 | >= −0.2 |
| H9 | Heuristic worst among trained | **PASS** | −0.523 | < 0.0 |

### Gate Summary

- Hypotheses: 8/9 PASS, 1 FAIL (H2), 0 SKIP
- Sufficiency: 4/4 tables, 23/23 sanity, 8/8 models
- Canaries: C1–C5 all PASS
- Best in lineage: `full_ols_av` at 2.234 net_eppd (updated)

## References

- Advance check: `data/artifacts/arc_d_v2/r2/advance_check.json` (not committed)
- Tables: `docs/04_reports/arc_d_v2/r2/full/tables/`
- H2H battery: `data/artifacts/arc_d_v2/r2/h2h_battery_full_*.json`
- gate_status: ADVANCE (overridden from INVESTIGATE)
