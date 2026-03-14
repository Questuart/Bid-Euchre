# Lineage Amendments — Arc D v2

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Last updated:** 2026-03-14

---

## Amendment Log

### LA-1 — [Auction Position Features at R1+](#lineage-amendment-la-1)
### LA-2 — [Anchor Compatibility Policy](#lineage-amendment-la-2)

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
