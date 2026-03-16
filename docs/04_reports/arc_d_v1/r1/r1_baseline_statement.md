# R1 Baseline Statement

**Date frozen:** 2026-03-06
**Commit:** `73b3ef0` (post-rung-relabel, PR #555)
**Status:** R1 CONCLUDED — preserved as historical trick-target rung
**gate_status:** X3 STOP (primary delta -0.348 net_eppd)

---

## Rung Definition

R1 added auction-context data and coarse partner features
(`partner_bid_level`, `partner_passed`, `partner_suit_match`) to the R0
trick-target prediction architecture. The training objective remained
`tricks_won` with hand-coded utility conversion to bidding decisions.

## Key Results

### Training Layer (Improved)
- Suit R² improved from ~0.25 (R0) to ~0.63 (R1) — Gate X2 passed (+0.40)
- Partner features dominated fit: `partner_bid_level` alone added +0.329 R²
- High/low selected only `partner_suit_match` (sample-size confound documented)
- Both dual arms (constrained + full) showed consistent improvement

### Gameplay Layer (Regressed)
- Primary H2H delta: **-0.348 net_eppd** (R1 worse than R0)
- Suit regression: **-0.76 net_eppd** [CI: -0.99, -0.53] — significant
- High/low: CIs span zero (no significant change)
- Gate X3: **STOP** — R1 not promotable

### Root Cause (Diagnosed)
- H10 confirmed analytically: `_compute_ev_static()` EV monotonically
  non-increasing in `bid_n` for sigma>0; `compute_best_bid(bid_level_search=True)`
  always picks `min_legal`
- Objective mismatch: train on `tricks_won`, decide with hand-coded utility,
  evaluate on `points_per_deal` — R² improvement ≠ gameplay improvement
- `bid_bonus=0.25` diagnostic probe reversed overall delta to +0.407 but
  suit-specific deficit persisted (-0.456) — decision layer is major bottleneck,
  not sole cause

## Canonical Artifacts

| Artifact | Path | Notes |
|----------|------|-------|
| R1 model (constrained) | `data/artifacts/arc_d/r1/hybrid_r1.json` | 3/2/2 locked base + partner features |
| R1 model (full) | `data/artifacts/arc_d/r1/hybrid_r1_full.json` | Forward-selected from all 42 features |
| Training data | `data/runs/canonical_auction_r1_42/datasets/bidless.parquet` | 41,424 hands from 50k deals |
| Step 5 H2H battery | `data/runs/` (3-seed, QUICK) | Gate X3 evidence |
| H10 validation | PR #552 | 101 parametric tests |
| bid_bonus sweep | PR #554 | 6-bidder, 36 matchups |

## What R1 Proved

1. Coarse partner features improve trick prediction substantially
2. Improved trick prediction does not guarantee improved gameplay
3. The trick-target → hand-coded-utility → bidding chain breaks at the utility step
4. Partner features are not intrinsically harmful — the decision stack was insufficient

## What R1 Did NOT Prove

- That partner features are useless for bidding (they may be valuable under a
  better objective)
- That the R1 models are worse at everything (they predict tricks better)
- That richer partner features would help or hurt (that's R1.6's question)

## Baseline for R1.5

R1.5 (objective-alignment) compares against:
- **R1 incumbent artifacts** as the trick-target baseline
- **R0 incumbent artifacts** as the pre-partner-context baseline
- The Step 5 H2H results as the canonical gameplay evidence

R1.5 must demonstrate gameplay improvement over R1 to justify the
objective change. R1.5 does NOT need to improve trick prediction — it
needs to improve points-per-deal under risk.

## Attribution Chain

| Transition | What It Measures |
|------------|-----------------|
| R0 → R1 | Partner context under trick-target objective (failed) |
| R1 → R1.5 | Objective change: tricks → points (pending) |
| R1.5 → R1.6 | Richer partner semantics under points objective (pending) |
| R1.6 → R2 | Opponent context (pending) |

---

**This statement is shared by both the R1 closeout package and the R1.5
implementation spec. Both workstreams must use consistent language and
artifact references.**
