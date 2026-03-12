# R1.5 Forward Decision Tree

**Date:** 2026-03-12 (revised)
**Arc:** D — OLSa-Hybrid Bidder
**Status:** ACTIVE — governs post-R1.5.2 research direction
**Prerequisite:** [Post-R1 Retrospective](docs/04_reports/r1_5/post_r1_retro.md)
**Incumbent:** hybrid_olsa_full R0 (`hybrid_r0_full.json`)

## Rung Naming Convention

| Rung | Scope | Status |
|------|-------|--------|
| R1.5 | Objective-alignment (AV v1 pipeline) | ADVANCED |
| R1.5.2 | Diagnostics (ablation, interaction terms, calibration) | CONCLUDED |
| R1.5.3 | Decision-level diagnostic + alternative model approaches | ACTIVE (Step 0 complete) |
| R1.5.4 | Partner context improvements | Deferred |
| R2 | Opponent context | Future |

## Current State

R1.5.3 **Step 0 is COMPLETE** (PR #610). The decision-level suit diagnostic
decomposed the -0.142 suit deficit into error types and determined the gate
decision: **Track B (GBT) or further investigation**.

**Step 0 key findings:**
- Boundary errors = 28.5% of deficit (< 60% Track A threshold)
- Clear-set region dominates at 43.0% of absolute residual
- Wrong contract: 26.5% of suit hands would be better as high/low
- H13 answered: bid-level optimization irrelevant (2.3% improvable)
- AV v1 suit made rate 96.5% vs R0 98.0% (nearly identical bidding frequency)

**Gate decision:** Errors spread across calibration range, not concentrated
at boundary. Track A (two-stage) is NOT the primary fix. Track B (GBT) or
alternative nonlinear approach is recommended.

**Play-policy sanity check: PASS.** Glutton significantly outperforms Greedy
across all seeds, directions, and scenarios (mean +0.20 tricks, p<0.0001).
Suit scenarios show the strongest Glutton advantage (+0.23 to +0.31), ruling
out Glutton as a suit-specific confounder. Labels are adequate for Track B.

**Key numbers:**
- AV v1 pooled delta vs R0: **+0.152** net_eppd, CI [+0.124, +0.180]
- Suit deficit: **-0.142**, CI [-0.180, -0.105]
- High gain: **+0.430**, Low gain: **+0.495**
- Promotion threshold: CI_low > **0.180**

## Decision Tree

```
R1.5.2 diagnostics CONCLUDED
│
├─── Step 0: Decision-Level Suit Diagnostic ✓ COMPLETE (PR #610)
│    Gate decision: Track B — errors spread across calibration range
│    Boundary = 28.5% (<60%), clear-set = 43.0%, wrong-contract = 26.5%
│    H13 answered: bid-level headroom irrelevant (2.3%)
│
├─── Step 0.5: Play-Policy Sanity Check ✓ PASS
│    play_policy_gate.py: Glutton vs Greedy, 3 seeds × 20K hands
│    Result: PASS all 6 directions (mean adv +0.19 to +0.21, all p<0.0001)
│    Suit scenarios: strongest Glutton advantage (+0.23 to +0.31)
│    Conclusion: Glutton labels are adequate. Proceed to Track B.
│
├─── Track A: Two-Stage Model (deprioritized by Step 0 gate)
│    Method: P(make) × E[pts|make] + P(set) × E[pts|set]
│    Implementation: minimal suit-only prototype, no shared infra
│    Most interpretable, directly tests H12
│    Step 0 showed boundary errors = only 28.5% — Track A addresses the
│    wrong failure mode. Preserved as fallback if Track B fails.
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

| Phase | Trigger | Plan File | Status |
|-------|---------|-----------|--------|
| **Step 0: Suit Diagnostic** | Immediate | `plans/sessions/2026-03-12_r1-5-3-step0-suit-diagnostic.md` | COMPLETE (PR #610) |
| **Step 0.5: Play-Policy Check** | Step 0 complete | Same plan (below) | PASS |
| **Track B: GBT** | Step 0 gate + Step 0.5 PASS | `plans/sessions/2026-03-11_r1-5-3-alternative-approaches.md` | NEXT |
| **Track A: Two-Stage** | Track B fails (fallback) | Same plan | Deprioritized |
| **Track C: Pairwise** | A and B fail | Same plan | Deferred |
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
| analysis_base_sha | 4a2b5b5 |
