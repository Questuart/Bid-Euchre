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
| Comparator battery | Absolute metric extraction (7 bidders vs GluttonStrategy) | scripts/internal/run_auction_comparator.py | 50,000 (FULL) | 42 |
| Semantic gate | Model health checks (Tier 1 artifact integrity) | src/bid_euchre/diagnostics/semantic_gate.py | N/A (artifact checks) | N/A |

## Known Methodological Limitations

| ID | Description | Category | Notes |
|----|-------------|----------|-------|
| L1 | Best-of-4 selection effect in comparator | (b) | Each bidder evaluated from all 4 seats; best-of-4 inflates absolute metrics |
| L2 | LOD positional bias in comparator | (b) | Coupled with L1; same single-seat redesign fixes both |
| L3 | bid_rate conflation in comparator | (b) | Coupled with L1; bid_rate mixes voluntary and forced bids |
| L4 | GluttonStrategy confounding in comparator | (a) | Inherent to self-play design; opponent never bids, inflating declaring-team metrics |
| L5 | Pairwise not round-robin H2H | (a) | H2H battery tests all pairs but not full round-robin tournaments; accepted for efficiency |

## Deferral Cost Descriptions

### B-L1: Best-of-4 selection effect

- **Fix-now impact:** 2-3 PRs to implement single-seat comparator redesign
  (see plans/comparator_experiment_redesign.md). Requires re-running comparator
  battery for R0, updating all absolute metric tables.
- **Fix-later impact:** Same fix cost plus crosswalk tables per rung (R0 vs R1
  metrics not directly comparable if methodology changes between rungs). Each
  additional rung of deferral adds one crosswalk.
- **Never-fix consequence:** Absolute metrics (net_eppd, bid_rate) remain
  inflated by selection effect. Rankings are unaffected (all bidders equally
  inflated), but metric magnitudes are not comparable to single-seat
  evaluations or theoretical expectations.

### B-L2: LOD positional bias

- **Fix-now impact:** Coupled with L1 — same single-seat redesign fixes both.
  No additional cost beyond L1.
- **Fix-later impact:** Same compounding as L1.
- **Never-fix consequence:** Seat-dependent strategies may show artificial
  advantages; positional confound in absolute metrics.

### B-L3: bid_rate conflation

- **Fix-now impact:** Coupled with L1 — single-seat design eliminates forced
  bidding (last-bidder-must-bid scenarios are seat-dependent).
- **Fix-later impact:** Same compounding as L1.
- **Never-fix consequence:** bid_rate metric includes forced bids, making it
  misleading as a measure of bidder selectivity. Relative rankings unaffected.

## Blockers

None. All (c)-class items have been resolved or do not apply to R0.

## Sign-off

- [x] All evaluation batteries listed
- [x] All known limitations classified (a/b/c)
- [x] All (b) items have deferral cost descriptions
- [x] No (c) items remain unresolved
- [x] Rigor firewall applied (05_rigor.md blockers are category (c))
