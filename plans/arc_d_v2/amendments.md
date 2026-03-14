# Lineage Amendments — Arc D v2

**Governing plan:** `plans/arc_d_v2/lineage_plan.md`
**Last updated:** 2026-03-14

---

## Amendment Log

### LA-1 — [Auction Position Features at R1+](#lineage-amendment-la-1)

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
