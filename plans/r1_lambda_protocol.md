# R1 CVaR Risk Lambda Tuning Protocol

## 0. Registration Statement

- **Version:** v1 (initial R1 registration)
- **Predecessor:** `plans/archive/r0_v2_lambda_tuning_protocol.md` v4
- **Registration PR:** (this PR)
- **Status:** PRE-REGISTERED — do not execute until HITL-1 approves

---

## 1. Motivation

### 1.1 Why Re-Evaluate at R1

R1 changes the utility landscape that lambda operates on:
1. **Feature enrichment (P1):** HIGH locked base expands 1→2 features
   (`offsuit_aces` + `quick_tricks`); LOW from 1→2 (`offsuit_tens_count` +
   `quick_tricks`). Better predictions change prediction variance, which
   changes the risk/reward tradeoff lambda controls.
2. **Auction-context data:** Partner bidding features provide new information
   that may reduce prediction uncertainty on hands where R0's model was
   least certain — exactly the marginal hands where CVaR matters most.

### 1.2 R0 v2 Decision: RETAIN λ=0.0

R0 v2 found that λ=0.5 improved self-play net_eppd by +0.884 but **reversed**
to −1.146 in H2H. The mechanism: λ>0 suppresses bids on volatile hands,
ceding ~82% of auctions to the aggressive λ=0 opponent. Auction dominance
overwhelmed the make-rate improvement (100% vs 97%).

**Lesson carried forward:** Self-play results are unreliable for lambda. The
decision instrument must be H2H.

### 1.3 Lambda as Hyperparameter

| Property | Value |
|----------|-------|
| Symbol | λ (risk_lambda) |
| Range | [0, ∞) |
| Semantic | Weight of CVaR tail-risk penalty on bidding utility |
| R0 v2 value | 0.0 (RETAIN — H2H reversed self-play gain) |
| Code location | `bidding.py:898–926` `_compute_risk_penalty_static()` |
| Config location | Experiment YAML `strategy.risk_lambda` |

---

## 2. Protocol Design

### 2.1 Two-Stage Evaluation

| Stage | Instrument | Purpose | Decision Authority |
|-------|------------|---------|-------------------|
| Stage 1 | Self-play sweep | Candidate identification + diagnostic | Diagnostic only |
| Stage 2 | H2H confirmation | Validate candidate against λ=0 | **Primary decision** |

This two-stage design was established in R0 v2 amendment v2 (§8) after
offline replay proved insufficient.

### 2.2 Data Source

**Stage 1:** Self-play simulation (4-seat, same bidder all seats) using
`scripts/internal/run_lambda_sweep.py`.

**Stage 2:** Head-to-head experiment (λ* vs λ=0) using H2H battery runner.

Both use the **R1 model artifacts** from Step 3 training.

### 2.3 Candidate Grid

| Index | λ | Interpretation |
|-------|---|----------------|
| 0 | 0.0 | Risk-neutral (current default) |
| 1 | 0.05 | Very mild risk aversion |
| 2 | 0.1 | Mild risk aversion |
| 3 | 0.2 | Moderate risk aversion |
| 4 | 0.5 | Moderate-high risk aversion |
| 5 | 1.0 | High risk aversion |
| 6 | 2.0 | Very high risk aversion |

Same 7-point v2 grid. Matches `run_lambda_sweep.py` default (line 593).
The 0.05 point was added at R0 v2 for low-end resolution.

### 2.4 Utility Calculation

```python
compute_best_bid(
    mu=predicted_mu,
    sigma=predicted_sigma,
    current_high_bid=current_high_bid,  # from auction context
    pass_threshold=t_star,  # from Step 7 result (0.0 if RETAIN)
    bid_level_search=True,
    risk_lambda=candidate_lambda,
    seed=42,
)
```

**Dependency on Step 7:** This protocol runs **after** threshold tuning.
The selected threshold t* from Step 7 is used as a fixed input.

### 2.5 Stage 1: Self-Play Sweep

**Runner:** `scripts/internal/run_lambda_sweep.py`

```bash
uv run python scripts/internal/run_lambda_sweep.py \
    --seed 42 \
    --grid 0.0 0.05 0.1 0.2 0.5 1.0 2.0 \
    --pass-threshold <t from Step 7> \
    --n-deals 10000
```

**Selection rule:** Epsilon-greedy (ε = 0.02 net_eppd units).
1. Apply guardrails: discard candidates violating bounds
2. Find `best_net_eppd = max(net_eppd)` among survivors
3. Select `λ_candidate = min(λ)` such that `best_net_eppd - net_eppd(λ) ≤ ε`

Rationale: When multiple lambdas produce similar net_eppd, prefer the
smallest (most risk-neutral) to minimize unnecessary bid suppression.

### 2.6 Guardrails

| Guardrail | Metric | Threshold |
|-----------|--------|-----------|
| bid_rate | **Seat-level bid propensity** | ∈ [0.05, 0.95] |
| make_rate | Per-deal make rate | ≥ 0.45 |

**Critical:** The bid_rate guardrail uses **seat-level bid propensity**, not
the evaluator's deal-level `bid_rate`. In 4-seat self-play, deal-level
bid_rate inflates toward 1.0 because `deal_bid_rate ≈ 1 - (1-p)^4`.
This correction was established in R0 v2 amendment v3 (§9).

Seat-level propensity is computed from `auction_transcript` in JSONL
hand_end records:
```python
seat_bids = sum(1 for entry in transcript if entry["action"] == "BID")
seat_opportunities = len(transcript)
seat_bid_propensity = total_seat_bids / total_seat_opportunities
```

---

## 3. Decision Rule

### 3.1 Stage 1 Result

| λ_candidate | Status | Next Step |
|-------------|--------|-----------|
| 0.0 | **RETAIN (FINAL)** | No further action |
| > 0.0 | **PROVISIONAL** | Proceed to Stage 2 |

### 3.2 Stage 2: H2H Confirmation

Run targeted H2H experiment: `hybrid_olsa(λ=λ_candidate)` vs
`hybrid_olsa(λ=0.0)`.

- Same model artifact, `pass_threshold=t*`, `bid_level_search=True`
- 10,000 deals per matchup, seed 42
- 4 matchups: 2 self-play + 2 cross-rotation

Compute paired delta: `delta = net_eppd(λ*) - net_eppd(λ=0)`
Bootstrap 95% CI (10,000 resamples, seed=42, grouped by deal_id).

### 3.3 Decision Gate

| Condition | Decision |
|-----------|----------|
| delta > 0 AND CI excludes 0 | **ADOPT λ*** |
| delta CI includes 0 | **RETAIN λ=0** (insufficient evidence) |
| delta < 0 | **RETAIN λ=0** (risk penalty harmful) |

**SESOI:** CI-excludes-0 (no minimum delta). Free hyperparameter — any
significant improvement is worth adopting.

### 3.4 If Self-Play and H2H Disagree

If self-play identifies λ* > 0 but H2H shows delta ≤ 0 (the R0 pattern):
- **RETAIN λ=0** — H2H takes precedence
- Document the disagreement and magnitude
- This exact pattern occurred at R0 v2 (self-play +0.884, H2H −1.146)

### 3.5 If ADOPT

1. Update all experiment configs: `strategy.risk_lambda: <λ*>`
2. Re-run Steps 4–6 (eval, H2H, comparator) with new lambda
3. Proceed to Step 12 (promotion gate) using the selected lambda

---

## 4. Interaction with Step 7 (Threshold Tuning)

**Sequential:** Threshold is tuned first at λ=0. Lambda (this protocol) then
uses the selected threshold (t=0 or t*). This matches the R0 v2 ordering.

**If both ADOPT:** A final FULL rerun with (t*, λ*) is required before the
promotion gate (see training plan §Hyperparameter ADOPT Rerun Matrix).

**Interaction check (diagnostic, non-gating):** If the R0 pattern recurs
(self-play vs H2H reversal), note whether the magnitude has changed. If the
reversal is smaller at R1, this suggests better predictions are reducing the
gap — a positive signal for R2 lambda viability.

---

## 5. Provenance

| Item | Value |
|------|-------|
| Sweep runner | `scripts/internal/run_lambda_sweep.py` (default grid L593) |
| CVaR computation | `_compute_risk_penalty_static()` in `bidding.py:898–926` |
| Utility function | `compute_best_bid()` in `bidding.py:797` |
| Epsilon-greedy ε | 0.02 net_eppd units |
| Bootstrap | 10,000 resamples, seed=42, grouped by deal_id |
| Grid | [0.0, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0] |
| R0 v2 result | RETAIN λ=0.0 (self-play +0.884 reversed to −1.146 in H2H) |
| R0 v2 report | `docs/04_reports/r0/archive/12_lambda_decision.md` |
| Depends on | Step 7 result (pass_threshold = t*) |

---

## 6. Amendment Log

| Version | Date | Change |
|---------|------|--------|
| v1 | 2026-03-04 | Initial R1 registration. Codified R0 v2 lessons: H2H as decision instrument, seat-level propensity guardrail, epsilon-greedy selection. Changed data source to use R1 model artifacts. |
