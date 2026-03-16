# Normalizer Offline Go/No-Go Screen Spec

**Date:** 2026-03-03
**Status:** PRE-EXECUTION (approved, awaiting implementation)
**Parent plan:** `plans/r0_canonical_v2_plan.md` §5 (Phase 1: Normalizer)
**Protocol:** `plans/r0_v2_normalizer_protocol.md` (pre-registered)
**Task:** TUI #13

---

## 0. Purpose

Fast offline screening pipeline to decide whether Track E normalizer is worth
full A/B implementation. Uses existing oracle-style data — no experiment reruns.

**This is a pre-screen only:** it informs go/no-go for full protocol execution.
It does not replace protocol adoption evidence (comparator + H2H batteries).

### Trigger Context

nb55 v2 oracle analysis found CS regret share = 90.9% (threshold = 25%).
Normalizer was TRIGGERED by protocol but DEFERRED during overnight execution.
This screen determines whether to proceed with full Track E implementation
or confirm deferral to R1.

---

## 1. Scope

### In Scope
1. Use existing oracle-style data construction from nb55.
2. Fit affine normalizer parameters on train split.
3. Evaluate on validation split with deal-grouped uncertainty.
4. Produce machine-readable artifact + short markdown decision note.

### Non-Goals
1. No bidder integration in production code.
2. No comparator/H2H battery runs.
3. No canonical ADOPT/REJECT decision — only a screening signal.

---

## 2. Deliverables

| # | File | Type |
|---|------|------|
| 1 | `scripts/internal/run_normalizer_offline_screen.py` | Script |
| 2 | `tests/unit/test_normalizer_offline_screen.py` | Tests |
| 3 | `data/artifacts/arc_d/r0/normalizer_offline_screen_v1.json` | Artifact (gitignored) |
| 4 | `docs/04_reports/arc_d_v1/r0/normalizer_offline_screen.md` | Report (TUI #14) |

---

## 3. Script Interface

```
uv run python scripts/internal/run_normalizer_offline_screen.py \
  --bidless-path data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless.parquet \
  --outcomes-path data/runs/canonical_bidless_dataset_glutton_42_20260221_175752/datasets/bidless_outcomes.parquet \
  --artifact-path data/artifacts/arc_d/r0/hybrid_r0.json \
  --seed 42 \
  --pass-threshold 0.0 \
  --risk-lambda 0.0 \
  --n-bootstrap 10000 \
  --output data/artifacts/arc_d/r0/normalizer_offline_screen_v1.json
```

All args have defaults except `--output`.

---

## 4. Data Construction (must match nb55 semantics)

### 4.1 Reusable Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `join_features_outcomes()` | `src/bid_euchre/datasets/join.py` | Join bidless features + outcomes |
| `deal_partition()` | `src/bid_euchre/analysis/sweep.py` | 60/40 train/val split by deal_id hash |
| `compute_ev_vectorized()` | `src/bid_euchre/analysis/sweep.py` | Gaussian expected net-differential |
| `bid_level_search_vectorized()` | `src/bid_euchre/analysis/sweep.py` | Vectorized bid-level search (all legal levels) |

### 4.2 Pipeline

1. Join features/outcomes via `join_features_outcomes(bidless_path, outcomes_path)`.
2. Keep complete `(deal_id, seat)` groups with all 6 contract keys.
3. For each hand × contract:
   - Predict `mu` using contract-family model weights from artifact.
   - Compute `sigma` from residual variance in artifact.
   - Get `(bid_n, utility)` via `bid_level_search_vectorized()` (lambda=0.0).
   - If utility is -inf: `bid_n=0` (hand passes for this contract).
   - Compute realized `actual_net`:
     ```python
     if bid_n == 0:
         actual_net = 0.0  # pass earns 0
     elif tricks >= bid_n:
         actual_net = 2.0 * tricks - 10.0  # make
     else:
         actual_net = tricks - bid_n - 10.0  # set
     ```
4. Oracle contract per hand = argmax `actual_net` over contracts where bid_n > 0.
   If all bid_n == 0, oracle passes (actual_net = 0).
5. Baseline model contract = argmax raw `utility` over contracts where utility > 0.
   Tie-break: higher bid_n, then contract_key ordering (production parity).
   If all utility <= 0, model passes.

### 4.3 Contract-Type Grouping

6 contract utilities (suit_C, suit_D, suit_H, suit_S, high, low) are evaluated,
but the 4 suit contracts share one normalizer parameter pair. The softmax operates
over 6 values with 3 distinct (alpha, beta) pairs.

---

## 5. Execution Order

### Step 0: Diagnostic Zero (early exit)

**Run BEFORE fitting.** Compute utility gap distribution on disagreement hands:

```python
disagreement_mask = (model_contract != oracle_contract)
utility_gap = utility[model_contract] - utility[oracle_contract]  # on disagreement hands
```

Report quantiles (p25, p50, p75, p90) and overlap summary.

**Early exit rule:**
- If `median_gap > 2.0 AND p75_gap > 3.0`: → **NO_GO** (model poverty, not miscalibration)
- Skip fitting entirely. This saves time when the problem is clearly model quality.

### Step 1: Normalizer Fit

**Parameters:** 6 values: `alpha[ct], beta[ct]` for `ct in {suit, high, low}`.

**Transform:** `u_norm = alpha[ct] * u_raw + beta[ct]`

**Train split:** `deal_partition(deal_id, seed=42)` → 60% train / 40% val.

**Objective (train):** Minimize negative log-likelihood of oracle contract under
softmax over normalized per-contract utilities.

```python
# For each hand i with oracle contract c*:
# P(c* | u_norm) = exp(u_norm[c*]) / sum_c(exp(u_norm[c]))
# Loss = -mean(log P(c* | u_norm)) + lambda_reg * ||params - identity||^2
```

**Optimization:**
- Method: `L-BFGS-B`
- Bounds: `alpha in [0.5, 2.0]`, `beta in [-5.0, 5.0]`
- Regularization: L2 toward identity (`alpha=1, beta=0`) with weight `1e-3`
- If optimizer fails: hard fail with explicit error in artifact.

### Step 2: Validation

Evaluate on validation split (40%):

**Accuracy metrics:**
- `accuracy_baseline`: fraction of hands where model contract matches oracle
- `accuracy_normalized`: fraction where normalizer-adjusted contract matches oracle
- `accuracy_lift`: normalized - baseline

**Net-eppd metrics:**
- `net_eppd_baseline`: mean actual_net using model's chosen contract
- `net_eppd_normalized`: mean actual_net using normalizer's chosen contract
- `delta_net_eppd`: normalized - baseline
- 95% CI via grouped bootstrap by `deal_id` (10,000 resamples)

**Pass-decision shift:**
- `bid_rate_baseline`: fraction of hands where model bids (max utility > 0)
- `bid_rate_normalized`: fraction where normalizer-adjusted model bids
- `bid_rate_delta`: normalized - baseline
- `new_bidders_count`: hands switching pass → bid
- `lost_bidders_count`: hands switching bid → pass

**Guardrails:**
- `bid_rate_normalized in [0.05, 0.95]`
- `make_rate_normalized >= 0.45`

---

## 6. Go/No-Go Rubric

### GO_TO_FULL_TRACK_E
All true:
- `delta_net_eppd >= +0.08` (inflated from protocol's +0.05 for offline overestimate)
- CI excludes 0 (`ci_low > 0`)
- Guardrails pass
- `accuracy_lift >= 0.03`

### NO_GO_DEFER_R1
Any true:
- `delta_net_eppd <= 0`
- `ci_high < +0.03`
- `accuracy_lift < 0.02`
- Early exit from Diagnostic Zero

### NEEDS_REVIEW
Everything else — human decision with data packaged for review.

### Overestimate Caveat

The offline replay uses counterfactual outcomes (all 6 contracts simulated per
hand). In a real A/B, the normalizer's effect will be **smaller** because
defending strategy adapts to the declared contract. Expect ~50-75% of offline
estimate in real experiments.

This is why the GO threshold is +0.08 (not +0.05): an offline +0.08 maps to
~+0.04-0.06 in practice, which is near the protocol's +0.05 adoption threshold.

---

## 7. Output Artifact Schema

```json
{
  "schema": "normalizer_offline_screen_v1",
  "created_at_utc": "...",
  "seed": 42,
  "pass_threshold": 0.0,
  "risk_lambda": 0.0,
  "diagnostic_zero": {
    "n_disagreement_hands": 1234,
    "utility_gap_quantiles": {"p25": ..., "p50": ..., "p75": ..., "p90": ...},
    "early_exit": false
  },
  "fit": {
    "optimizer_status": "converged",
    "params": {
      "alpha": {"suit": 1.0, "high": 1.5, "low": 0.8},
      "beta": {"suit": 0.0, "high": -0.3, "low": 0.1}
    },
    "train_accuracy_baseline": 0.85,
    "train_accuracy_normalized": 0.88,
    "final_loss": 0.42
  },
  "val_metrics": {
    "accuracy_baseline": 0.84,
    "accuracy_normalized": 0.87,
    "accuracy_lift": 0.03,
    "net_eppd_baseline": 2.1,
    "net_eppd_normalized": 2.2,
    "delta_net_eppd": 0.1,
    "delta_ci_low": 0.05,
    "delta_ci_high": 0.15,
    "bid_rate_baseline": 0.93,
    "bid_rate_normalized": 0.90,
    "bid_rate_delta": -0.03,
    "new_bidders_count": 50,
    "lost_bidders_count": 120,
    "make_rate_normalized": 0.97,
    "guardrails_pass": true
  },
  "decision": "GO_TO_FULL_TRACK_E | NO_GO_DEFER_R1 | NEEDS_REVIEW",
  "rationale": ["delta >= +0.08", "CI excludes 0", ...]
}
```

---

## 8. Required Tests

| # | Test | Purpose |
|---|------|---------|
| 1 | Split reproducibility | `deal_partition` produces same split with same seed |
| 2 | Utility transform correctness | alpha/beta application matches expected output |
| 3 | Objective decreases from identity | Optimizer makes progress on synthetic calibratable data |
| 4 | Tie-break parity | Production tuple ordering `(utility, bid_n, contract_key)` |
| 5 | Bootstrap grouping | Groups by `deal_id`, not hand-level |
| 6 | Guardrail computations | Boundary cases for bid_rate and make_rate |
| 7 | End-to-end smoke | Tiny synthetic dataset → artifact with correct schema |

---

## 9. Report Spec (TUI #14)

File: `docs/04_reports/arc_d_v1/r0/normalizer_offline_screen.md`

**Required sections:**
1. **Executive Summary** — GO/NO_GO/NEEDS_REVIEW with 1-sentence rationale
2. **Background** — 90.9% CS regret, normalizer triggered but deferred, this is a fast pre-screen
3. **Method** — offline oracle replay, affine normalizer, softmax NLL, deal-grouped bootstrap
4. **Diagnostic Zero** — utility gap distribution on disagreement hands
5. **Results** — accuracy, net_eppd delta with CI, bid_rate shift, guardrails
6. **Decision** — gate-by-gate breakdown
7. **Key Takeaways** — what this tells us about R0 model limitations and R1 prospects
8. **Provenance** — artifact path, seed, data source, parameters

---

## 10. Assumptions

1. Uses `lambda=0.0` aligned with retained Track D outcome.
2. This screen is a prioritization tool only, not canonical protocol evidence.
3. Any GO result must still pass full Track E protocol gates before adoption.
4. If NO_GO: confirms deferral to R1, documented in promotion report.

---

## 11. Amendment Log

| Version | Date | Change | Rationale |
|---------|------|--------|-----------|
| v1 | 2026-03-03 | Initial spec | Pre-screen before full Track E |
