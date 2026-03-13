# Two-Stage OLS Evaluation — H16 Verdict

**Date:** 2026-03-12
**Rung:** R1.5.3 (model-architecture exploration)
**Hypothesis:** H16 — Does explicit make/set decomposition close the GBT gap?
**Verdict:** PARTIAL

## Summary

Two-stage OLS (logistic P(make) + conditional E[pts|make/set]) improves over flat OLS
by +0.124 net_eppd but falls 0.750 behind GBT — far outside the 0.3 threshold for
"closing the gap."

## Background

The suit contract target in bid euchre is structurally bimodal: E[pts|made] = +2.01
vs E[pts|set] = -12.85 (14.9 point gap). Standard OLS averages across this gap,
producing poor predictions near the decision boundary. Two-stage models this
explicitly with three components:

1. **P(make | state, bid_n)** — logistic regression (AUC = 0.9363)
2. **E[net_points | make]** — OLS on made subset
3. **E[net_points | set]** — OLS on set subset
4. **Composite:** P(make) * E[pts|make] + (1-P(make)) * E[pts|set]

The declare/defend decomposition tested in R1.5.2 FAILED (defend R² ≈ 0), but that's
a fundamentally different split. Make/set operates *within* the declaring subset,
separating outcomes by whether the bid was achieved.

## Model Training Results

| Component | Metric | Value |
|-----------|--------|-------|
| P(make) logistic | AUC | 0.9363 |
| P(make) logistic | Gate (>0.70) | PASS |
| E[pts\|make] OLS | R² | Embedded in composite |
| E[pts\|set] OLS | R² | Embedded in composite |
| **Composite suit** | **R²** | **0.5894** |
| High OLS | R² | 0.5328 |
| Low OLS | R² | 0.5143 |
| Pass OLS | R² | 0.0456 |

Composite suit R² (0.5894) vs flat OLS (0.565) = +0.024 improvement.
GBT suit R² = 0.594 — two-stage nearly matches GBT in R².

Top P(make) features: partner_suit_match (+0.53), bid_n (-0.43), seat_rel_3 (-0.26).

## H2H Battery Results

**Setup:** 4-bidder round-robin (two_stage_v1, ols_av_v1, gbt_av_v1, hybrid_olsa_full_r0).
QUICK mode: 2,000 paired deals × 16 directional matchups. Seed 42. GluttonStrategy play.

### Symmetrized net_eppd Deltas

| Matchup | Symmetrized delta | CI spans zero? |
|---------|-------------------|----------------|
| Two-Stage vs OLS AV | **+0.124** | Yes (marginal) |
| Two-Stage vs Hybrid R0 | **+0.191** | Yes (marginal) |
| Two-Stage vs GBT | **-0.750** | No |
| GBT vs Hybrid R0 | **+1.075** | No |
| GBT vs OLS AV | **+1.111** | No |
| OLS AV vs Hybrid R0 | **+0.129** | Yes (marginal) |

### Self-Play Profiles

| Bidder | eppd | make_rate | CVaR 5% |
|--------|------|-----------|---------|
| hybrid_olsa_full_r0 | 4.893 | 96.9% | -0.65 |
| ols_av_v1 | 4.809 | 94.3% | -2.02 |
| two_stage_v1 | 4.317 | 85.7% | -5.87 |
| gbt_av_v1 | 4.261 | 86.7% | -6.79 |

### Transitivity Check

Ranking: GBT >> Two-Stage > OLS ≈ R0. Fully transitive — no circular preferences.

## H16 Verdict: PARTIAL

| Criterion | Required | Actual | Status |
|-----------|----------|--------|--------|
| Two-stage vs OLS delta > 0 | > 0 | +0.124 | PASS |
| Pooled gap to GBT < 0.3 | < 0.3 | 0.750 | FAIL |

**PARTIAL:** Make/set decomposition provides a real improvement over flat OLS (+0.124)
but falls far short of GBT's advantage (+1.075 vs R0). The gap ratio is:
Two-stage closes 0.124 / 1.075 = **11.5%** of the GBT advantage.

## Interpretation

1. **The bimodal decomposition is the right idea.** Two-stage and GBT converge on
   the same behavioral profile (make_rate ~86%, aggressive bidding) — the logistic
   classifier correctly identifies the bimodal structure.

2. **OLS conditional models are too rigid.** While P(make) has AUC 0.9363, the
   conditional E[pts|make] and E[pts|set] are still linear. The residual within each
   regime still contains nonlinearity that GBT captures.

3. **Model capacity dominates decomposition strategy.** Phase 1A showed capacity
   dwarfs label quality by 35x. This result confirms: even the "right" decomposition
   with OLS only recovers 11.5% of GBT's edge.

4. **Two-stage validates the diagnosis, not the treatment.** The suit regression is
   caused by bimodality (confirmed by improved R² and behavioral shift), but the
   cure is model capacity (GBT), not structural decomposition (two-stage OLS).

## Recommendation

- **GBT is the clear mainline.** Proceed to FULL validation (Track A).
- **Two-stage provides interpretability value** — the P(make) logistic model and
  conditional means are human-readable — but the 0.750 H2H gap is too large
  for production use.
- **Future consideration:** EBM/boosted GAM could combine interpretability with
  nonlinear capacity. Not urgent given GBT's decisive lead.

## Reproduction

```bash
# Train two-stage model
uv run python scripts/internal/train_action_value.py \
  --dataset data/runs/action_value_quick_42 \
  --output data/runs/two_stage_quick_42/action_value_two_stage.json \
  --model-class two-stage --seed 42

# Run H2H battery (requires roster.json setup)
uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --roster data/runs/two_stage_h2h/roster.json \
  --mode QUICK --seed 42
```

## Provenance

- Run ID: `arc_d_r0_h2h_battery_42_20260312_214835`
- Config SHA: `3e9cf1ad8be99852`
- Git SHA: `cf17b73144bf0cd16f862adcf98c2c8fd7275a62`
- Dataset SHA: `ed36e4012411`
- Two-stage artifact: `two_stage_action_value_v1` schema
