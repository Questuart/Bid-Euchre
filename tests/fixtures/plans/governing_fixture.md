# Governing Fixture Plan

<!-- review-tier: governing -->

**Date:** 2026-03-17
**Status:** FIXTURE
**Scope:** Test fixture for review infrastructure FULL tests

---

## Overview

This is a multi-rung research plan for evaluating the comparative
performance of bidding strategies across the R0-R3 rung ladder.

## Hypotheses

| ID | Hypothesis | Test | Threshold |
|----|-----------|------|-----------|
| H1 | GBT outperforms heuristic on H2H | Paired comparison | p < 0.05 |
| H2 | R² improves monotonically across rungs | Regression | R² > 0.5 |
| H3 | Moon/loner bids have positive expected value | Bootstrap CI | CI > 0 |

## Rung Ladder

### R0: Baseline
- Train GBT on 10k deals
- Evaluate against Smart bidder
- Gate: H2H delta > 0

### R1: Feature Enhancement
- Add positional features
- Retrain on 20k deals
- Gate: R² improvement > 0.05

### R2: Interaction Terms
- Add suit×position interactions
- Retrain on 30k deals
- Gate: Comparator score > 2.0

### R3: Moon/Loner
- Enable moon/loner enumeration
- Retrain with counterfactuals
- Gate: 9/9 criteria PASS

## Promotion Gates

Each rung must satisfy:
1. H2H delta > 0 (ADVANCE threshold)
2. No regression on comparator score
3. All hypotheses tested with statistical rigor
4. Sample size >= 2000 deals per evaluation

## Steps

### Phase A: Dataset Generation
1. Generate training data for each rung
2. Validate deal balance (seat, contract, trump)
3. Run ANOVA on seat distribution (p > 0.05)

### Phase B: Model Training
1. Train GBT with hyperparameter sweep
2. Cross-validate on held-out set
3. Record feature importances

### Phase C: Evaluation
1. Run H2H battery (3 seeds × 2500 deals)
2. Compute bootstrap CIs on all metrics
3. Generate promotion report

### Phase D: Reporting
1. Draft results report with exact repro commands
2. Draft decision report with gate outcomes
3. Archive artifacts in `data/runs/`

## Files
- `src/bid_euchre/strategy/bidding.py`
- `src/bid_euchre/features/hand_eval.py`
- `src/bid_euchre/models/gbt_bidder.py`
- `src/bid_euchre/arc_d_v2/orchestration.py`
- `experiments/configs/rung_*.yaml`
- `scripts/internal/run_rung.py`
- `scripts/internal/generate_rung_report.py`
- `notebooks/S1_rung_analysis.py`
- `notebooks/S2_h2h_comparison.py`
- `notebooks/S3_feature_importance.py`
- `notebooks/S4_promotion_evidence.py`

## Statistical Requirements

- All evaluations use seeded randomness (`--seed 42`)
- Bootstrap CIs with 10,000 resamples
- Multiple comparison correction (Bonferroni) for H1-H3
- Effect sizes reported alongside p-values
- Minimum 2,000 deals per evaluation cell

## Validation

```bash
# Smoke test
uv run python experiments/run_experiment.py --seed 42 \
  --config experiments/configs/quick_test.yaml --n_per 10

# Full evaluation
uv run python scripts/run_suite.py \
  --suite experiments/suites/rung_ladder.yaml \
  --seed 42 --n-per 2500

# Report generation
uv run python scripts/internal/generate_rung_report.py \
  --rung r0 --mode quick --seed 42
```

## Outcome
<!-- Filled after implementation -->
- PR: (fixture — not implemented)
