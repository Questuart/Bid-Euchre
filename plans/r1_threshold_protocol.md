# R1 Pass-Threshold Tuning Protocol (P4)

## 0. Registration Statement

- **Version:** v1 (initial R1 registration)
- **Predecessor:** `plans/archive/r0_v2_threshold_protocol.md` v2
- **Registration PR:** (this PR)
- **Status:** PRE-REGISTERED — do not execute until HITL-1 approves

---

## 1. Motivation

### 1.1 Why Re-Tune at R1

R1 changes two factors that affect the optimal pass threshold:
1. **Feature enrichment (P1):** HIGH locked base expands from 1→2 features
   (`offsuit_aces` + `quick_tricks`); LOW from 1→2 (`offsuit_tens_count` +
   `quick_tricks`). Better predictions change the utility distribution.
2. **Auction-context data:** R1 trains on auction-context data (partner bids
   visible), not bidless. The threshold must be tuned against the same data
   distribution the model was trained on.

### 1.2 Threshold as Hyperparameter

| Property | Value |
|----------|-------|
| Symbol | t (pass_threshold) |
| Range | [0, ∞) |
| Semantic | Minimum expected utility to bid (higher = more conservative) |
| R0 v2 value | 0.0 (RETAIN — monotonic decline observed) |
| Code location | `bidding.py:797` `compute_best_bid(pass_threshold=t)` |
| Config location | Experiment YAML `strategy.pass_threshold` |

---

## 2. Protocol Design

### 2.1 Data Source

**R1 canonical auction-context dataset:**
`data/training/r1/canonical_auction_context_42.parquet`

Generated in Step 1 using R0 HybridOLSaBidder as the bidding policy.
Must exist and pass X1 (feature smoke) before this protocol executes.

### 2.2 Train/Validation Split

- **Method:** 60/40 by `deal_id` hash using `deal_partition(seed=42)`
  (`src/bid_euchre/analysis/sweep.py`)
- **Grouping:** By `deal_id` (prevents hand-level leakage; 4 rows per hand)
- **Seed:** 42

### 2.3 Candidate Threshold Grid

| Index | t |
|-------|---|
| 0 | 0.0 |
| 1 | 0.1 |
| 2 | 0.2 |
| 3 | 0.5 |
| 4 | 1.0 |
| 5 | 2.0 |
| 6 | 5.0 |

Same 7-point grid as R0 v2. Retained to detect whether R1 features change
the shape of the utility-vs-threshold curve.

### 2.4 Utility Calculation

For each candidate t, compute `compute_best_bid()` with:

```python
compute_best_bid(
    mu=predicted_mu,
    sigma=predicted_sigma,
    current_high_bid=current_high_bid,  # from auction context
    pass_threshold=t,
    bid_level_search=True,
    risk_lambda=0.0,    # threshold tuned at λ=0 (sequential: threshold first)
    seed=42,
)
```

### 2.5 Primary Endpoint

**net_eppd** (net expected points per deal) on the validation split.

### 2.6 Guardrails

| Guardrail | Threshold |
|-----------|-----------|
| bid_rate | ∈ [0.05, 0.95] |
| make_rate | ≥ 0.45 |

Any candidate violating guardrails is excluded before selection.

---

## 3. Decision Rule

### 3.1 Selection on Train

Select t* = argmax(net_eppd) on the 60% training partition,
subject to guardrails.

### 3.2 Validation

On the 40% validation partition:
- Compute net_eppd(t*) and net_eppd(t=0)
- Bootstrap 10,000 resamples (seed=42, grouped by deal_id)
- Compute 95% CI on delta = net_eppd(t*) − net_eppd(t=0)

### 3.3 Decision Gate

| Condition | Decision |
|-----------|----------|
| CI_low > 0 | **ADOPT t*** |
| CI includes 0 | **RETAIN t=0** (insufficient evidence) |
| t* = 0.0 | **RETAIN t=0** (trivially) |

**SESOI:** CI-excludes-0 (no minimum delta). Free hyperparameter — any
significant improvement is worth adopting.

### 3.4 If ADOPT

1. Update all experiment configs: `strategy.pass_threshold: <t*>`
2. Re-run Steps 4–6 (eval, H2H, comparator) at QUICK with new threshold
3. Proceed to Step 8 (lambda) using the selected threshold

---

## 4. Interaction with Lambda (Track D)

**Sequential:** Threshold is tuned first at λ=0. Lambda (Step 8) then uses
the selected threshold (t=0 or t*). This matches the R0 v2 ordering
(`plans/archive/r0_v2_threshold_protocol.md` §4).

If lambda also ADOPTs λ*, a final FULL rerun with (t*, λ*) is required
before the promotion gate.

---

## 5. Provenance

| Item | Value |
|------|-------|
| Sweep function | `compute_ev_vectorized()` in `src/bid_euchre/analysis/sweep.py` |
| Split function | `deal_partition()` in `src/bid_euchre/analysis/sweep.py` |
| Utility function | `compute_best_bid()` in `src/bid_euchre/strategy/bidding.py:797` |
| Bootstrap | 10,000 resamples, seed=42, grouped by deal_id |
| Grid | [0.0, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0] |
| R0 v2 result | RETAIN t=0 (monotonic decline in net_eppd) |
| R0 v2 report | `docs/04_reports/r0/11_pass_threshold_decision.md` |

---

## 6. Amendment Log

| Version | Date | Change |
|---------|------|--------|
| v1 | 2026-03-04 | Initial R1 registration. Changed data source from bidless → auction-context. Retained grid and decision rule from R0 v2. |
