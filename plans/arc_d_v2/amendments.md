# Lineage Amendments — Arc D v2

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Last updated:** 2026-03-15

---

## Amendment Log

### LA-1 — [Auction Position Features at R1+](#lineage-amendment-la-1)
### LA-2 — [Anchor Compatibility Policy](#lineage-amendment-la-2)
### LA-3 — [Hybrid Execution Path: QUICK-First Ladder](#lineage-amendment-la-3)

---

## Lineage Amendment LA-1

**Date:** 2026-03-14
**Type:** feature_addition
**Effective from:** Rung R1
**Change:** Add `auction_position` (int 0-3) and `is_dealer` (int 0|1) to the context bundle at R1+. Correct §6.2 left/right opponent auction-order claims.

**Rationale:**
The R1 partner features and R2 opponent features encode WHAT other players bid, but not WHERE the observer is in the auction order. This creates an ambiguity: when all partner features are zero, the model cannot distinguish "partner hasn't bid yet (observer is bidding first)" from "partner passed with nothing to bid."

Additionally, the dealer has special privileges (R3 moon/loner takeover) that the model cannot learn without an explicit `is_dealer` feature.

The plan's §6.2 claims "left opponent bids after you" — this is only true for non-dealer positions. When the observer IS the dealer (bids last), the geometric-left opponent (seat+1) actually bids FIRST. Adding `auction_position` lets GBT learn this interaction; the prose should be corrected to not claim a fixed auction-order mapping.

**New features:**

| Feature | Type | Definition | Rung |
|---------|------|-----------|------|
| `auction_position` | int (0-3) | Position in bidding order. 0=first to bid (left of dealer), 3=last (dealer). Computed as `(seat - dealer_seat - 1) % 4`. | R1+ |
| `is_dealer` | int (0\|1) | 1 if observer is the dealer, 0 otherwise. Computed as `int(seat == dealer_seat)`. | R1+ |

**Impact on feature counts:**

| Rung | Before | After |
|------|--------|-------|
| R0* | 39 (hand-only, unchanged) | 39 |
| R1 | 45 (39 hand + 6 partner) | 47 (39 hand + 6 partner + 2 position) |
| R2 | 57 (39 + 6 + 12 opponent) | 59 (39 + 6 + 12 + 2 position) |

**Impact on comparability:** None for R0* (unchanged). R1+ models have 2 additional features. Cross-rung comparisons remain valid because context bundles are additive by design — R1 includes R0* features plus new features.

**Implementation notes:**
- Both values are already available in `BiddingObservation` (`seat` and `dealer_seat` fields)
- Feature extraction should be added to `auction_context.py` alongside partner features
- The constrained arm (§5.1) should add both features to its locked set at R1+
- `--feature-set full` at R1+ automatically includes all features, so no FEATURE_SETS changes needed

**Approved by:** [human reviewer — to be filled]

---

## Lineage Amendment LA-2

**Date:** 2026-03-14
**Type:** evaluation_contract
**Effective from:** R0*
**Change:** Define anchor model compatibility policy. Separate anchor roles across evaluation modes.

**Rationale:**
The frozen anchor (`hybrid_r0_full`) serves two roles:
1. Historical reference for cross-lineage comparison
2. Live executable participant in evaluation batteries

These roles have different compatibility requirements. The anchor was trained on the
legacy OLSa feature schema (tricks_won target, no `current_high_bid` positional feature).
R0* action-value models use a different schema (net_points target, 39 hand + 2 action
features). Loading the anchor through the ActionValueBidder runtime path fails because
the feature inference assumes modern positional features.

**Policy decisions:**

| Evaluation Mode | Anchor Required? | Loading Path | Rationale |
|----------------|-----------------|-------------|-----------|
| H2H battery | **Yes** | HybridOLSaBidder (native) | Direct competitive comparison, anchor's own bidder class |
| Cross-rung deltas | **Yes** | Via H2H results | Longitudinal tracking across rungs |
| Comparator battery | **No** | N/A | Comparator ranks models independently vs AlwaysPass sentinels; anchor not needed for this |

**Anchor compatibility contract:**
- The anchor is ONLY loaded through `HybridOLSaBidder` -- never through `ActionValueBidder`
- H2H roster entries for the anchor use `class_name: HybridOLSaBidder` with `artifact_path`
- Comparator roster does NOT include the anchor
- If a future runtime change breaks `HybridOLSaBidder` loading, that is a blocker

**Impact on reports:**
- Comparator rankings table (S12.1): current roster only, no anchor row
- H2H delta table (S12.2): includes anchor (loaded via its own bidder class)
- Cross-rung deltas (S12.8): anchor deltas from H2H results
- This separation keeps the evidence contract clean -- each evaluation mode uses
  the appropriate loading mechanism

**Impact on orchestrator:**
- `generate_comparator_config()` excludes the anchor from bidding_policies
- `generate_h2h_roster()` includes the anchor with `class_name: HybridOLSaBidder`
- Anchor compatibility precheck added to `check_anchor_compatibility()` utility

**Approved by:** [human reviewer]

---

## Lineage Amendment LA-3

**Date:** 2026-03-15
**Type:** execution_order
**Effective from:** R0*
**Change:** Adopt Hybrid Execution Path — run QUICK-only through R0→R1→R2 before
committing to any FULL runs. FULL is deferred, not skipped.

**Rationale:**
The governing plan §9.5 prescribes QUICK→FULL per rung before advancing to the next
rung. In practice, this front-loads ~10-14 hours of FULL compute per rung before learning
whether the added context (partner features at R1, opponent features at R2) actually helps.
Running QUICK across all rungs first gives directional signal in ~2 hours total, letting
us decide which rung(s) merit FULL investment.

Additionally, the multi-seed FULL aggregation mechanism (§9.6) requires pooling per-deal
data across seeds and bootstrapping CIs from the pooled distribution — not averaging
per-seed summaries. This upstream aggregation is not yet implemented (see PR #690 Codex
review). Deferring FULL until after the ladder is explored at QUICK scale avoids blocking
on this infrastructure work.

**Modified execution order:**

| Step | Action | Gate |
|------|--------|------|
| 1 | Fix PR #690 (descope FULL merge, keep per-contract faceting) | PR merged |
| 2 | Canonical R0 QUICK rerun | Steps 0-8 green, advance check evaluable |
| 3 | Implement R1 (partner + position features) | Sub-plan created |
| 4 | R1 QUICK | Steps 0-8 green |
| 5 | Implement R2 (opponent features) | Sub-plan created |
| 6 | R2 QUICK | Steps 0-8 green |
| 7 | Review QUICK results across R0-R2 | Human decision point |
| 8 | FULL backfill for selected rung(s) | Only if QUICK results warrant |

**What this changes from §9.5:**
- §9.5 says: QUICK → evaluate → FULL → advance (per rung, sequential)
- LA-3 says: QUICK → advance (per rung) → review all → FULL backfill (selected rungs)

**What this does NOT change:**
- Each rung still runs the full 9-step pipeline at QUICK scale
- Advance checks still gate rung transitions (PROCEED required to advance)
- FULL is deferred, not eliminated — it remains required for publication-grade evidence
- §9.6 multi-seed aggregation contract is unchanged (pooled bootstrap, not averaged CIs)
- All outputs from QUICK-only runs must be labeled as `mode: quick` in artifacts

**Labeling requirement:**
All QUICK-only advance decisions must note `"evidence_tier": "quick"` in the advance
check JSON. This prevents QUICK results from being mistaken for FULL-grade evidence
in downstream reports or promotion decisions.

**Reversal conditions:**
- If QUICK results at any rung are ambiguous or surprising, revert to §9.5 (run FULL
  before advancing)
- If FULL is needed for a specific hypothesis (e.g., seed stability), run it at that
  rung before proceeding

**Impact on orchestrator:**
- `run_rung.py --mode quick` remains the primary execution command per rung
- `run_rung.py --mode all` (QUICK→FULL) is not used under LA-3
- FULL backfill uses `run_rung.py --mode full` after QUICK results are reviewed

**Approved by:** [human reviewer]
