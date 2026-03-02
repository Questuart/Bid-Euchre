# Measurement Integrity Review — R0

## Header

| Field | Value |
|-------|-------|
| **Arc** | D (OLSa-Hybrid Bidder) |
| **Rung** | R0 (baseline) |
| **Date** | 2026-02-26 |
| **Reviewer** | Human + Claude (retro review) |
| **gate_status** | PROMOTED |

## Evaluation Batteries

| Battery | Purpose | Script Path | Deal Count | Seed |
|---------|---------|-------------|------------|------|
| H2H battery | Pairwise competitive ordering (7 bidders, 49 matchups) | scripts/internal/run_arc_d_h2h_battery.py | 10,000/cell (FULL) | 42 |
| Comparator battery | Absolute metric extraction (7 bidders vs GluttonStrategy) | scripts/internal/run_auction_comparator.py | 20,000/bidder (v4 single-seat) | 42 |
| Semantic gate | Model health checks (Tier 1 artifact integrity) | src/bid_euchre/diagnostics/semantic_gate.py | N/A (artifact checks) | N/A |

## Known Methodological Limitations

| ID | Description | Category | Notes |
|----|-------------|----------|-------|
| L1 | Best-of-4 selection effect in comparator | (b) | **Resolved** by single-seat redesign (#466, #470). v4 evaluates one seat at a time. |
| L2 | LOD positional bias in comparator | (b) | **Resolved** (coupled with L1; same single-seat redesign fixes both) |
| L3 | bid_rate conflation in comparator | (b) | **Partially resolved** by single-seat mode; bid_rate now measures per-hand propensity in comparator. H2H bid_rate still conflates (team auction-win freq) |
| L4 | GluttonStrategy confounding in comparator | (a) | Inherent to self-play design; opponent never bids, inflating declaring-team metrics. Play strategy now harmonized across instruments (C2c, #466). |
| L5 | Pairwise not round-robin H2H | (a) | H2H battery tests all pairs but not full round-robin tournaments; accepted for efficiency |

## Deferral Cost Descriptions

### B-L1: Best-of-4 selection effect — RESOLVED

Single-seat comparator implemented (#466, #470). v4 data (20,000 deals/bidder,
single-seat mode, GluttonStrategy) is the canonical comparator instrument.
Best-of-4 selection effect is eliminated by design.

Historical cost analysis (retained for context):
- **Fix-now impact:** 2-3 PRs to implement single-seat comparator redesign.
  Requires re-running comparator battery for R0, updating all absolute metric
  tables.
- **Fix-later impact:** Same fix cost plus crosswalk tables per rung.
- **Never-fix consequence:** Absolute metrics remain inflated by selection
  effect.

### B-L2: LOD positional bias — RESOLVED

Coupled with L1 — resolved by the same single-seat redesign (#466, #470).

### B-L3: bid_rate conflation — PARTIALLY RESOLVED

Single-seat mode fixes comparator bid_rate conflation: in v4, bid_rate is a
clean per-hand propensity measure (one bidder, uncontested auction).

**Residual limitation:** H2H bid_rate still mixes voluntary and forced bids.
In the H2H battery, both teams participate in contested auctions, so a bidder's
observed bid_rate reflects both its intrinsic propensity and whether it was
outbid. This is an inherent property of the H2H estimand (competitive ordering),
not a methodology defect — but users should interpret H2H bid_rate as
"team auction-win frequency" rather than "bidder selectivity."

## Blockers

None. All (c)-class items have been resolved or do not apply to R0.

## Sign-off

- [x] All evaluation batteries listed
- [x] All known limitations classified (a/b/c)
- [x] All (b) items have deferral cost descriptions
- [x] No (c) items remain unresolved
- [x] Rigor firewall applied (05_rigor.md blockers are category (c))
