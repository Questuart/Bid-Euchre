# R1.5 Forward Decision Tree

**Date:** 2026-03-11 (revised)
**Arc:** D — OLSa-Hybrid Bidder
**Status:** ACTIVE — governs post-R1.5.2 research direction
**Prerequisite:** [Post-R1 Retrospective](docs/04_reports/r1_5/post_r1_retro.md)
**Incumbent:** hybrid_olsa_full R0 (`hybrid_r0_full.json`)

## Rung Naming Convention

| Rung | Scope | Status |
|------|-------|--------|
| R1.5 | Objective-alignment (AV v1 pipeline) | ADVANCED |
| R1.5.2 | Diagnostics (ablation, interaction terms, calibration) | CONCLUDED |
| R1.5.3 | Decision-level diagnostic + alternative model approaches | NEXT |
| R1.5.4 | Partner context improvements | Deferred |
| R2 | Opponent context | Future |

## Current State

R1.5.2 diagnostics are **CONCLUDED**. All prediction-level hypotheses
have been eliminated. The suit regression (-0.142 net_eppd) is the sole
promotion blocker. The **leading working hypothesis** is H12: OLS predicts
the mean of a bimodal make/set target, producing suboptimal bid decisions
for suit contracts.

H12 has strong correlational evidence (bimodality BIC=4,081, OLS predicts
between modes, suit has best R^2 but worst gameplay delta) but **no
decision-level proof**. The mechanism by which between-mode predictions
translate into bad bids has not been tested.

**Key numbers:**
- AV v1 pooled delta vs R0: **+0.152** net_eppd, CI [+0.124, +0.180]
- Suit deficit: **-0.142**, CI [-0.180, -0.105]
- High gain: **+0.430**, Low gain: **+0.495**
- Promotion threshold: CI_low > **0.180**

## Decision Tree

```
R1.5.2 diagnostics CONCLUDED
│
├─── Step 0: Decision-Level Suit Diagnostic
│    Plan: plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md
│    Data: existing FULL H2H logs (50K deals) + counterfactual dataset
│    No new models — pure analysis
│
│    Analyses:
│    ├── Error taxonomy: over-bid, wrong contract, wrong level, under-bid
│    ├── AV v1 vs R0 disagreement states (which side wins?)
│    ├── Make/set boundary concentration (where do errors cluster?)
│    ├── H13: bid-level headroom (does always-bid-4 leave value?)
│    └── Optional: repeated-rollout subset for noisy disagreement states
│
│    ├── Errors at make/set boundary (>60% of deficit)
│    │   → Track A: Two-Stage Model (suit-only prototype)
│    │
│    ├── Errors spread, nonlinear patterns
│    │   → Track B: GBT (nonlinear boundaries)
│    │
│    ├── Errors mostly wrong-contract (suit vs high/low)
│    │   → New direction (contract selection mechanism)
│    │
│    └── Single-rollout noise dominates
│        → Repeated-rollout subset before any treatment
│
├─── Track A: Two-Stage Model (primary, if Step 0 supports H12)
│    Method: P(make) × E[pts|make] + P(set) × E[pts|set]
│    Implementation: minimal suit-only prototype, no shared infra
│    Most interpretable, directly tests H12
│
│    ├── SUCCEEDS (suit delta > -0.092, improvement > 0.05)
│    │   → Extend to all contracts
│    │   → Proper bidder class + registration
│    │   → FULL evaluation → promotion gate
│    │
│    └── FAILS
│        → H12 decomposition is not sufficient
│        → Track B
│
├─── Track B: Gradient Boosted Trees (fallback)
│    Method: sklearn GBT regressor, per-contract
│    Still learns conditional mean (does NOT handle bimodality natively)
│    Tests nonlinear feature boundaries, not regime decomposition
│
│    ├── SUCCEEDS
│    │   → FULL evaluation → promotion gate
│    │
│    └── FAILS
│        → Rules out these model families on this data/label setup
│        → Does NOT prove a fundamental prediction→decision limit
│        → Reassess: Track C, hybrid routing, richer data (R1.5.4)
│
├─── Track C: Pairwise Policy Optimization (deferred)
│    Worst for understanding: changes learning objective, amplifies
│    single-rollout noise, failures hard to interpret
│    Activated only after interpretable prediction-side fixes exhausted
│
├─── Hybrid Routing (benchmark, not mainline fix)
│    AV v1 for high/low, R0 for suit
│    Upper bound on achievable delta without suit fix
│    Fallback if research stalls AND promotion pressure urgent
│
└─── Rung Ladder (future)
     R1.5.4 (partner-context) — richer partner signal for suit
     R2     (opponent-context) — after R1.5 family stabilizes
```

## Phase Sequencing

| Phase | Trigger | Plan File | Estimated Effort |
|-------|---------|-----------|-----------------|
| **Step 0: Suit Diagnostic** | Immediate | `plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md` | 1 PR (analysis) |
| **Track A: Two-Stage** | Step 0 supports H12 | Same plan | 1-2 PRs (prototype → extension) |
| **Track B: GBT** | Track A fails | Same plan | 1 PR (prototype) |
| **Track C: Pairwise** | A and B fail | Same plan | 1 PR (deferred) |
| **FULL Evaluation** | Any track succeeds | Same plan | 1 PR |
| **Hybrid Routing** | Promotion pressure + no fix | Not yet planned | 1 PR |
| **R1.5.4: Partner Context** | R1.5.3 exhausted | Not yet planned | New sub-rung |

## Key Principles

1. **Diagnose before treating.** Step 0 builds decision-level understanding
   before any model architecture work. This prevents building the wrong fix
   (the mistake that caused R1's regression).

2. **One track at a time.** Sequential prototyping, not parallel
   infrastructure. Each track's existence depends on the previous one's
   outcome. Infrastructure is built only for the winning approach.

3. **H12 is a working hypothesis, not a proven cause.** The plan is
   structured to test H12 cleanly (Track A) while preserving alternatives
   if it's wrong. Language should say "leading mechanism" or "working
   hypothesis," not "conclusively identified root cause."

4. **Interpretable fixes first.** Track A (two-stage decomposition) and
   Track B (GBT) are interpretable — if they work, we learn something
   about the mechanism. Track C (policy optimization) is deferred because
   it changes the learning objective, making failures hard to diagnose.

5. **Failure is not proof of impossibility.** If Tracks A and B both fail,
   that rules out those model families on this data and label setup. It
   does not prove a fundamental prediction→decision limit.

6. **Hybrid routing is a benchmark, not a goal.** It measures the
   achievable delta if suit were perfectly fixed. It remains available as
   a pragmatic fallback but is not a research success criterion.

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
