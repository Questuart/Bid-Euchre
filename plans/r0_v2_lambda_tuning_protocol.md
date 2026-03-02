# R0 v2 CVaR Risk Lambda Tuning Protocol

**Arc:** D (OLSa-Hybrid Bidder)
**Rung:** R0 v2 (corrected baseline)
**Date:** 2026-03-02
**Type:** Pre-registered analysis protocol
**Status:** PRE-REGISTERED (not yet executed)
**Governs:** Track D (Lambda Tuning) of R0 Canonical v2

---

## 0. Registration Statement

This protocol is **pre-registered**: all analysis choices (candidate grid, primary
endpoint, split method, decision rule) are locked before execution. No post-hoc
adjustments to the grid, success criteria, or decision rules are permitted. If the
protocol is insufficient, it must be amended with a new version (v2) documenting
the rationale, and the amendment must be recorded before re-execution.

**Protocol version:** v1
**Registration PR:** (to be filled on merge)

---

## 1. Motivation

### 1.1 What risk_lambda Does

The `risk_lambda` parameter controls the weight of a CVaR (Conditional Value at Risk)
tail-risk penalty in the bidding utility calculation. The utility for a given bid is:

```
utility = EV(mu, sigma, bid_n) - risk_lambda * max(0, -CVaR_5%(mu, sigma, bid_n))
```

Where:
- `EV` is the expected net-differential under a Gaussian trick model
  (`_compute_ev_static()`, `bidding.py:862-896`)
- `CVaR_5%` is the mean of the worst 5% of outcomes from Monte Carlo simulation
  (`_compute_risk_penalty_static()`, `bidding.py:898-926`)
- `risk_lambda = 0.0` means **risk-neutral** (current default -- no tail-risk penalty)
- `risk_lambda > 0` penalizes bids with large downside tails, making the bidder
  more conservative on high-variance hands

### 1.2 Why Tune Lambda

The current default `risk_lambda = 0.0` was set as a placeholder (PR #493, Amendment A).
All canonical config surfaces carry explicit `risk_lambda: 0.0` entries awaiting the
result of this protocol:

| Config location | File | Line |
|----------------|------|------|
| Auction comparator | `experiments/configs/auction_comparator.yaml` | L50, L58 |
| C33 ablation | `experiments/configs/arc_d_r0_c33_ablation.yaml` | L42, L49 |
| H2H battery roster | `scripts/internal/run_arc_d_h2h_battery.py` | L57, L66 |

A non-zero lambda could improve net_eppd by avoiding bids on hands where the tail
risk of a large set penalty outweighs the expected gain. Conversely, an overly
aggressive lambda could suppress profitable but volatile bids.

### 1.3 Lambda as Hyperparameter

| Parameter | Where Set | When Re-tuned | Current Value |
|-----------|-----------|---------------|---------------|
| OLS coefficients | `hybrid_r0.json` | Per-rung | Per-contract arm |
| residual_variance (sigma) | `hybrid_r0.json` | Per-rung | Per-contract family |
| pass_threshold (t) | Bidding policy | Per-rung (Track C) | 0.0 (pending) |
| **risk_lambda** | **Experiment config** | **Per-rung (Track D)** | **0.0** |

---

## 2. Protocol Design

### 2.1 Data Source

**Dataset:** `canonical_bidless_dataset_glutton_42_20260221_175752`
(same as threshold protocol and oracle analysis)

**Joined data:** 40,000 hand observations (10,000 deals x 4 seats), each with
6 paired contract outcomes and model predictions.

### 2.2 Train/Validation Split

**Split method:** GroupKFold by `deal_id` (identical to threshold protocol)

| Partition | Allocation | Deals | Hands | Purpose |
|-----------|-----------|-------|-------|---------|
| Train | deal_id hash % 5 in {0,1,2} | ~6,000 | ~24,000 | Select optimal lambda |
| Validation | deal_id hash % 5 in {3,4} | ~4,000 | ~16,000 | Evaluate selected lambda |

**Split implementation:** Same deterministic hash-based partition as threshold protocol:
```python
import hashlib

def deal_partition(deal_id: str, seed: int = 42) -> str:
    h = hashlib.sha256(f"{deal_id}:{seed}".encode()).hexdigest()
    bucket = int(h[:8], 16) % 5
    return "train" if bucket < 3 else "val"
```

Grouping by `deal_id` prevents seat-level leakage (each deal's 4 observations
stay in the same partition).

### 2.3 Candidate Grid

| risk_lambda | Interpretation |
|-------------|----------------|
| 0.0 | **Risk-neutral (current default)** |
| 0.1 | Mild risk aversion |
| 0.2 | Moderate risk aversion |
| 0.5 | Moderate-high risk aversion |
| 1.0 | High risk aversion |
| 2.0 | Very high risk aversion |

**Grid rationale:** Six candidates spanning two orders of magnitude. The CVaR
penalty is computed as `max(0, -CVaR_5%) * risk_lambda`, where CVaR_5% for a
typical hand is O(1-5) utility units. At `lambda=2.0`, the penalty can reach
10+ utility units, which would suppress nearly all volatile bids. The 0.1-0.5
range is where the tradeoff between risk reduction and bid suppression is most
likely to be interesting.

### 2.4 Utility Calculation

For each candidate `lambda`, utility is computed via `compute_best_bid()`
(`bidding.py:788`) with the v2 policy:

```python
result = compute_best_bid(
    mu=mu,
    sigma=sigma,
    current_high_bid=0,
    pass_threshold=t_star,  # from Track C result (0.0 if RETAIN)
    bid_level_search=True,
    risk_lambda=candidate_lambda,
    seed=42,
)
```

**Dependency on Track C:** This protocol runs **after** Track C (threshold tuning).
The selected threshold `t*` from Track C is used as a fixed input. If Track C
retained `t = 0.0`, this protocol uses `pass_threshold=0.0`.

### 2.5 Primary Endpoint

**net_eppd on the validation partition**, computed as:

For each hand in validation:
1. For each of the 6 contracts, call `compute_best_bid()` with `risk_lambda=lambda`,
   `pass_threshold=t*`, and `bid_level_search=True`
2. Select the contract with highest utility (if any pass the threshold)
3. If the model bids: use `bid_n` from search, look up actual outcome from
   paired data, compute `net = actual_net` for chosen contract at chosen level
4. If the model passes: net = 0 (per oracle convention)

### 2.6 Guardrails

| Guardrail | Threshold | Rationale |
|-----------|-----------|-----------|
| bid_rate in [0.05, 0.95] | Hard bounds | Same as threshold protocol |
| make_rate >= 0.45 | Hard floor | Below 45%, set penalties dominate |

If the optimal `lambda` by primary endpoint violates any guardrail, select the
candidate with highest net_eppd among guardrail-passing survivors. If no `lambda > 0`
improves over `lambda = 0.0`, retain `lambda = 0.0`.

---

## 3. Decision Rule

### 3.1 Selection on Train

1. Compute primary endpoint for each candidate `lambda` on **train** partition,
   using `compute_best_bid()` with `bid_level_search=True` and `pass_threshold=t*`
2. Apply guardrails: discard candidates that violate hard bounds
3. Select `lambda*_train` = candidate with highest net_eppd among survivors

### 3.2 Validation

1. Compute primary endpoint + guardrail metrics for `lambda*_train` and `lambda = 0.0`
   on **validation** partition
2. Compute improvement: `delta = net_eppd(lambda*_train) - net_eppd(lambda=0.0)`
3. Bootstrap 95% CI on delta (10,000 resamples, seed 42, grouped by deal_id)

### 3.3 Decision Gate

| Condition | Decision | Action |
|-----------|----------|--------|
| delta > 0 AND CI excludes 0 AND guardrails pass | **ADOPT** | Update all config surfaces with selected lambda |
| delta CI includes 0 | **RETAIN** | Keep lambda=0.0 |
| delta < 0 | **RETAIN** | Risk penalty harmful, keep lambda=0.0 |

### 3.4 Implementation (if ADOPT)

If the decision is ADOPT, update all three config-pinned locations:

1. `experiments/configs/auction_comparator.yaml` -- `risk_lambda: <lambda*>` (L50, L58)
2. `experiments/configs/arc_d_r0_c33_ablation.yaml` -- `risk_lambda: <lambda*>` (L42, L49)
3. `scripts/internal/run_arc_d_h2h_battery.py` -- `"risk_lambda": <lambda*>` (L57, L66)

These updates must happen **before** running Tracks A/B/C (comparator, H2H, C33
batteries) to ensure all canonical batteries use the tuned lambda value.

---

## 4. Interaction with Track C (Threshold Tuning)

Lambda tuning is **sequential after** threshold tuning:

1. **Track C:** Tune threshold `t` with `risk_lambda=0.0` -> yields `t*`
2. **Track D (this protocol):** Tune lambda with `pass_threshold=t*` -> yields `lambda*`

**Why sequential, not joint?** The 7x6 = 42 cell joint grid is feasible but
the sequential approach is simpler to validate. The interaction between `t` and
`lambda` is expected to be weak: `t` controls pool entry (which hands bid at all),
while `lambda` controls utility ranking within the bidding pool (which bids look
better when tail risk is penalized). A hand that passes at `t*` would also pass
at any `lambda > 0` (risk penalty only decreases utility).

**Interaction check (diagnostic, not gating):** After selecting `lambda*`, report
the correlation between threshold and lambda effects across the grid. If the
interaction is unexpectedly strong (e.g., optimal `t` changes by > 0.5 when
lambda changes), flag for joint optimization in R1.

---

## 5. CVaR Implementation Reference

The CVaR risk penalty is computed by `_compute_risk_penalty_static()` at
`bidding.py:898-926`:

```python
def _compute_risk_penalty_static(
    mu: float, sigma: float, bid_n: int, risk_lambda: float, seed: int
) -> float:
    if risk_lambda == 0.0:
        return 0.0
    # ... Monte Carlo CVaR computation ...
    # 1000 draws from N(mu, sigma)
    # Compute net for each draw (make/set payoff)
    # CVaR = mean of worst 5% of nets
    # penalty = max(0, -CVaR) * risk_lambda
```

Key parameters:
- `_CVAR_DRAWS = 1000` (Monte Carlo sample size)
- `_CVAR_TAIL = 0.05` (5th percentile tail)
- `_CVAR_SEED_DEFAULT = 42` (deterministic RNG for reproducibility)
- Continuity correction: `threshold = bid_n - 0.5`

---

## 6. Provenance

| Item | Value |
|------|-------|
| Protocol version | v1 |
| Dataset | `canonical_bidless_dataset_glutton_42_20260221_175752` |
| Model artifact | `data/artifacts/arc_d/r0/hybrid_r0.json` |
| CVaR computation | `_compute_risk_penalty_static()` (`bidding.py:898-926`) |
| Bidder entry point | `compute_best_bid()` (`bidding.py:788`) |
| Config surfaces | `auction_comparator.yaml`, `arc_d_r0_c33_ablation.yaml`, `run_arc_d_h2h_battery.py` |
| Depends on | Track C result (`pass_threshold=t*`) |
| Split seed | 42 |
| Bootstrap seed | 42 |
| Bootstrap resamples | 10,000 |
| Grid | [0.0, 0.1, 0.2, 0.5, 1.0, 2.0] |

---

## 7. Amendment Log

| Version | Date | Change | Rationale |
|---------|------|--------|-----------|
| v1 | 2026-03-02 | Initial protocol | Pre-registered before execution |
