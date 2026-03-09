# R1.5 Step 8: H2H Battery (FULL)

**Arc:** D — OLSa-Hybrid Bidder
**Rung:** R1.5 (objective-alignment)
**Date:** 2026-03-08
**Gate:** Promotion (CI_low > 0.180 net_eppd vs R0 best)

## Executive Summary

The FULL H2H battery (50,000 deals × 9 matchups) confirms ActionValueBidder v1
outperforms both R0 baselines with a primary delta of **+0.152 net_eppd** vs
hybrid_olsa_full R0. However, the 95% CI [+0.124, +0.180] does not clear the
promotion delta floor of 0.180 (CI_low = +0.124). Contract-type analysis reveals
large gains in high (+0.430) and low (+0.495), offset by a suit regression
(-0.142).

**Verdict: ADVANCED** — v1 shows real, statistically significant improvement
but falls short of promotion. The suit-contract deficit is the primary blocker.

## 1. Motivation

The QUICK H2H battery (Step 6) produced a primary delta of +0.165 net_eppd
(rotation-specific CIs excluding zero), passing Gate X4 and exceeding the
"delta > 0.0" threshold for proceeding to FULL evaluation. Step 7 (risk
treatment) was skipped — the risk-neutral v1 ActionValueBidder proceeds
directly to FULL-scale validation.

This step provides the definitive statistical test for promotion. The QUICK
battery's wide CIs (n=2,500) narrow substantially at FULL scale (n=50,000),
enabling a clear promotion or advancement decision.

### Promotion vs Advancement

| Outcome | Threshold | Meaning |
|---------|-----------|---------|
| PROMOTED | CI_low > 0.180 | v1 replaces R0 as incumbent |
| ADVANCED | CI_low > -0.10, point estimate > 0 | v1 shows signal, needs refinement |
| HALTED | CI_low < -0.10 | v1 regresses vs R0, investigate |

## 2. Methodology

### Configuration

- **Roster:** 3 bidders (ActionValueBidder v1, hybrid_olsa_full R0, hybrid_olsa R0)
- **Matchups:** 9 (3 self-play + 6 cross-matchups with seat rotations)
- **n_per:** 50,000 deals per matchup
- **Seed:** 42
- **Paired deals:** Yes (common deal sequences across matchups)
- **Play policy:** GluttonStrategy (greedy trick play)
- **Models:** QUICK-trained v1 models (FULL retraining deferred; see
  [04_risk_treatment.md](04_risk_treatment.md) section 2.4)

### Reproduction

The roster file (`data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json`) is gitignored.
To recreate it, see the roster definition in
[`experiments/configs/r1_5_h2h_battery_quick.yaml`](../../../experiments/configs/r1_5_h2h_battery_quick.yaml)
(bidding_policies section) or use the inline roster from the committed config.

```bash
# Run FULL battery (requires local roster artifact)
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --roster data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json \
    --seed 42 --n-per 50000 --mode FULL \
    --output data/artifacts/arc_d/r1_5/h2h_battery_full.json

# Parse results from existing run directory
PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
    --parse-run data/runs/arc_d_r0_h2h_battery_42_20260308_173038 \
    --roster data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json \
    --seed 42 --mode FULL \
    --output data/artifacts/arc_d/r1_5/h2h_battery_full.json
```

## 3. Gate X4 Results (FULL)

### Primary Delta (symmetrized across seat rotations)

| Comparison | Delta | CI_low | CI_high | Significant |
|------------|-------|--------|---------|-------------|
| **AV v1 vs HO_full R0** | **+0.152** | **+0.124** | **+0.180** | **Yes** |
| AV v1 vs HO R0 | +0.182 | +0.155 | +0.210 | Yes |
| HO_full R0 vs HO R0 | +0.028 | +0.002 | +0.055 | Yes |

Symmetrized delta = mean of (rotation 1, −rotation 2) net_eppd.

### Per-Rotation Detail (primary: AV v1 vs HO_full R0)

| Rotation | team0 | team1 | Net EPPD | CI |
|----------|-------|-------|----------|----|
| 1 | AV v1 | HO_full R0 | +0.138 | [+0.099, +0.177] |
| 2 | HO_full R0 | AV v1 | -0.165 | [-0.205, -0.127] |

### Promotion Assessment

| Criterion | Value | Threshold | Result |
|-----------|-------|-----------|--------|
| Point estimate (vs HO_full R0) | +0.152 | > 0.180 | FAIL |
| CI_low (vs HO_full R0) | +0.124 | > 0.180 | FAIL |
| Point estimate (vs HO R0) | +0.182 | > 0.180 | PASS |
| CI_low (vs HO R0) | +0.155 | > 0.180 | FAIL |

**Result: ADVANCED, not PROMOTED.** The improvement is real and significant
(CI excludes zero) but insufficient to clear the delta floor against the best
R0 incumbent (hybrid_olsa_full R0).

### Full Matchup Matrix

| Matchup | Net EPPD | CI | Make% | team0 bids | team1 bids |
|---------|----------|----|-------|------------|------------|
| AV v1 self-play | -0.018 | [-0.058, +0.022] | 94.6% | 24,941 | 25,059 |
| AV v1 vs HO_full R0 | +0.138 | [+0.099, +0.177] | 95.6% | 28,083 | 21,917 |
| HO_full R0 vs AV v1 | -0.165 | [-0.205, -0.127] | 95.7% | 21,854 | 28,146 |
| AV v1 vs HO R0 | +0.171 | [+0.132, +0.210] | 95.7% | 28,537 | 21,463 |
| HO R0 vs AV v1 | -0.193 | [-0.232, -0.155] | 95.7% | 21,441 | 28,559 |
| HO_full R0 self-play | -0.011 | [-0.048, +0.027] | 96.8% | 24,998 | 25,002 |
| HO_full R0 vs HO R0 | +0.022 | [-0.016, +0.059] | 96.8% | 25,399 | 24,601 |
| HO R0 vs HO_full R0 | -0.035 | [-0.073, +0.003] | 96.8% | 24,638 | 25,362 |
| HO R0 self-play | -0.002 | [-0.040, +0.035] | 96.9% | — | — |

## 4. Behavioral Analysis

### Bid Volume Asymmetry

ActionValueBidder v1 consistently bids more than R0 opponents:

- In cross-matchups: AV v1 bids on ~28,000-28,500 of 50,000 hands (56-57%)
- R0 opponents bid on ~21,400-21,900 (43-44%)
- In self-play: bids are balanced (24,941 vs 25,059)

This "quantity over quality" strategy is the key behavioral difference — v1 bids
on nearly every hand at bid=4, accepting low set risk (-4 points) while R0 is
more selective.

### Make Rate

| Bidder context | Make rate |
|---------------|-----------|
| AV v1 self-play | 94.6% |
| AV v1 in cross-matchups | 95.6-95.7% |
| R0 self-play | 96.8-96.9% |

V1's lower self-play make rate (94.6% vs 96.8%) reflects its higher bid volume —
it takes marginal hands that R0 would pass on.

### Contract-Type Faceting

| Contract | Delta (vs HO_full R0) | CI | Significant |
|----------|----------------------|-----|-------------|
| **Suit** | **-0.142** | [-0.180, -0.105] | **Yes (regression)** |
| **High** | **+0.430** | [+0.359, +0.501] | **Yes** |
| **Low** | **+0.495** | [+0.444, +0.546] | **Yes** |

The suit regression (-0.142) is a confirmed structural weakness. V1's advantage
is concentrated in no-trump contracts (high and low), where the simpler scoring
(no bowers, no trump suit) is easier for the action-value model to learn.

## 5. QUICK-to-FULL Stability

| Metric | QUICK (n=2,500) | FULL (n=50,000) | Stable? |
|--------|-----------------|-----------------|---------|
| Pooled delta (vs HO_full R0) | +0.165 | +0.152 | Yes (-8%) |
| AV v1 bid rate | 56-57% | 56-57% | Yes |
| AV v1 make rate (self-play) | 95.4% | 94.6% | Yes |
| Suit delta | (not measured) | -0.142 | — |
| High delta | (not measured) | +0.430 | — |
| Low delta | (not measured) | +0.495 | — |

The point estimate is very stable (QUICK +0.165 → FULL +0.152, 8% shrinkage).
Behavioral metrics (bid rate, make rate) are nearly identical. The FULL CIs
are ~4× tighter, as expected for a 20× sample increase.

## 6. Implications

### For Promotion

**Not promoted.** CI_low (+0.124) falls short of the 0.180 delta floor. The v1
bidder shows genuine improvement over R0, but the suit-contract regression
prevents it from clearing the promotion threshold.

### For v2 (Risk Treatment)

The suit regression (-0.142) is the primary target for v2. Potential approaches:

1. **Contract-specific decision rules:** Apply pass threshold only for suit
   contracts where the model underbids
2. **Suit-specific model improvements:** Investigate why suit predictions are
   weaker (bower interactions, trump complexity)
3. **Hybrid approach:** Use AV v1 for high/low decisions, fall back to R0 for
   suit contracts

See [04_risk_treatment.md](04_risk_treatment.md) section 3 for trigger conditions.

### Caveats and Plan Deviations

- **FULL retraining deferred:** Models trained on QUICK data (not retrained at
  FULL scale as specified in plan Step 4). Rationale: model quality already
  validated at QUICK; retraining deferred to v2 cycle. See
  [04_risk_treatment.md](04_risk_treatment.md) section 2.4.
- **Comparator battery deferred:** Plan Step 8 specifies "H2H Battery (FULL) +
  Comparator." The comparator battery (single-seat against GluttonStrategy) was
  not run for v1. The H2H battery alone is sufficient for the ADVANCED decision
  since CI_low < 0.180 regardless.
- **Risk treatment skipped:** Plan Step 7 (v2 risk treatment) was skipped since
  delta > 0.0. This means Step 8 evaluates v1 (risk-neutral), not the
  risk-treated v2 specified in the plan.
- Single seed (42) — cross-seed validation deferred
- 3-bidder roster — broader roster deferred to v2

## 7. Arc Context

| Step | Status | Gate |
|------|--------|------|
| 0-2 | DONE | Infrastructure + training |
| 3 | DONE | X3 offline ranking (adjudicated ADVANCED) |
| 5 | DONE | Self-play screen (all gates PASSED) |
| 6 | DONE | X4 QUICK H2H (+0.165) |
| 7 | SKIPPED | Risk treatment (delta > 0.0) |
| **8** | **DONE (H2H only)** | **FULL H2H: +0.152, CI [+0.124, +0.180]. Comparator battery deferred** |
| 9 | DONE | Ablation (see below) |
| 10 | DONE | Promotion decision: ADVANCED |

## 8. Provenance

| Item | Value |
|------|-------|
| gate_status | ADVANCED — delta +0.152 significant, CI_low +0.124 below delta floor 0.180 |
| Roster | `data/artifacts/arc_d/r1_5/h2h_roster_r1_5.json` |
| Summary | `data/artifacts/arc_d/r1_5/h2h_battery_full.json` |
| Config | `data/artifacts/arc_d/r1_5/h2h_battery_full_config.yaml` |
| Run dir | `data/runs/arc_d_r0_h2h_battery_42_20260308_173038` |
| Seed | 42 |
| n_per | 50,000 |
| Runtime | 72.9 minutes |
| Prior report | [03_h2h_battery_quick.md](03_h2h_battery_quick.md) |
| Risk treatment | [04_risk_treatment.md](04_risk_treatment.md) — SKIPPED |
| analysis_base_sha | c15f7dd |
