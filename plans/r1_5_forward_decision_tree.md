# R1.5 Forward Decision Tree

**Date:** 2026-03-11
**Arc:** D — OLSa-Hybrid Bidder
**Status:** ACTIVE — governs post-R1.5.2 research direction
**Prerequisite:** [Post-R1 Retrospective](docs/04_reports/r1_5/post_r1_retro.md)
**Incumbent:** hybrid_olsa_full R0 (`hybrid_r0_full.json`)

## Rung Naming Convention

| Rung | Scope | Status |
|------|-------|--------|
| R1.5 | Objective-alignment (AV v1 pipeline) | ADVANCED |
| R1.5.2 | Diagnostics (ablation, interaction terms, calibration) | CONCLUDED |
| R1.5.3 | Alternative model approaches (3 tracks) | NEXT |
| R1.5.4 | Partner context improvements | Deferred |
| R2 | Opponent context | Future |

## Current State

R1.5.2 diagnostics are **CONCLUDED**. All "easy" hypotheses have been
eliminated. The suit regression (-0.142 net_eppd) is the sole promotion
blocker. The leading theory is H12: OLS predicts the mean of a bimodal
make/set target, producing suboptimal bid decisions for suit contracts.

**Key numbers:**
- AV v1 pooled delta vs R0: **+0.152** net_eppd, CI [+0.124, +0.180]
- Suit deficit: **-0.142**, CI [-0.180, -0.105]
- High gain: **+0.430**, Low gain: **+0.495**
- Promotion threshold: CI_low > **0.180**

## Decision Tree

```
R1.5.2 diagnostics CONCLUDED
│
├─── R1.5.3: Alternative Model Approaches
│    Plan: plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md
│    Three tracks tested at QUICK scale, best promoted to FULL
│
│    Track A: Two-Stage Model
│    ├── Method: P(make) × E[pts|make] + P(set) × E[pts|set]
│    ├── Tests H12 directly (bimodal target decomposition)
│    └── Suit-only initially, extend to high/low if successful
│
│    Track B: Gradient Boosted Trees
│    ├── Method: LightGBM/XGBoost on same features
│    ├── Non-linear model class (handles bimodality natively)
│    └── Per-contract models like AV v1
│
│    Track C: Pairwise Policy Optimization
│    ├── Method: Logistic regression on feature differences
│    ├── Bypasses predict→decide pipeline entirely
│    └── Highest ceiling, largest implementation effort
│
│    ├─── Any track SUCCEEDS at QUICK scale
│    │    (suit delta > 0 vs both AV v1 and R0)
│    │    → FULL retraining (50k deals)
│    │    → FULL H2H battery
│    │    → Promotion evaluation (CI_low > 0.180?)
│    │    └── If promoted: R0 replaced, move to R1.5.4 or R2
│    │    └── If CI still tight: combine with risk treatment, retry
│    │
│    └─── All tracks FAIL
│         → Prediction→decision gap is fundamental at OLS+ level
│         → Fallback: Hybrid Routing
│
├─── Fallback: Hybrid Routing (available at any point)
│    Use AV v1 for high/low, R0 for suit
│    Expected pooled delta: high/low gains with no suit penalty
│    Delivers promotion but does not advance suit understanding
│    Trigger: promotion pressure is urgent AND no architectural fix found
│
└─── Rung Ladder (future)
     R1.5.4 (partner-context) — richer partner signal for suit
     R2     (opponent-context) — after R1.5 family stabilizes
```

## Phase Sequencing

| Phase | Trigger | Plan File | Estimated Effort |
|-------|---------|-----------|-----------------|
| **R1.5.3: Alternative Approaches** | Immediate (current) | `plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md` | 6 PRs, ~1 day per track |
| **Fallback: Hybrid Routing** | Promotion pressure + no fix | Not yet planned (straightforward) | 1 PR |
| **R1.5.4: Partner Context** | R1.5.3 FAILS or deferred | Not yet planned | New sub-rung |

## Key Principles

1. **Narrow before broad.** Track A tests the single leading hypothesis
   (H12) with minimal change surface (suit head only). Tracks B and C
   broaden to alternative architectures if Track A is inconclusive.

2. **Pre-registered outcomes.** Each track has explicit success/failure
   definitions. No post-hoc reinterpretation.

3. **Causal cleanliness over promotion speed.** A clean negative result
   (H12 refuted) is more valuable than a messy positive result (hybrid
   routing promotes but doesn't explain).

4. **Fallback always available.** Hybrid routing can deliver promotion
   at any point if the research direction stalls and the pragmatic need
   becomes urgent.

## Archived Plans

The following plans governed earlier phases and are preserved in
`plans/archive/` for reference:

| Plan | Era | Reason for Archival |
|------|-----|-------------------|
| `r1_master_plan.md` | R1 | Concluded. Rung ladder (§10) remains canonical reference. |
| `r1_training_plan.md` | R1 | R1 STOP. Training cycle complete. |
| `r1_5_training_plan.md` | R1.5 v1 | ADVANCED. 10-step pipeline complete. |
| `r1_follow_ups.md` | R1 | Superseded by retrospective decision log. |
| `r2_follow_ups.md` | R1 | Accumulated during R1. Superseded by R1.5.3 plan. |
| `h10_validation_pack.md` | R1 | COMPLETED. H10 proven analytically. |
| `r1_lambda_protocol.md` | R0v2 | RETAIN λ=0.0. Concluded. |
| `r1_normalizer_trigger.md` | R0v2 | NO_GO_DEFER_R1. Concluded. |
| `r1_threshold_protocol.md` | R0v2 | RETAIN t=0. Concluded. |
| `arc_d_execution_plan.md` | R0 | v3 from 2026-02-20. Predates R1.5. |

## Provenance

| Item | Value |
|------|-------|
| gate_status | N/A — decision tree, not a gate artifact |
| Governing retrospective | `docs/04_reports/r1_5/post_r1_retro.md` |
| analysis_base_sha | f74ff62 |
