# Measurement Integrity Review — R0

> **Version:** v2 (PR #510) | v1 archived at `archive/v1/`

## Header

| Field | Value |
|-------|-------|
| **Arc** | D (OLSa-Hybrid Bidder) |
| **Rung** | R0 (baseline) |
| **Date** | 2026-02-26 (v1); 2026-03-03 (v2 update) |
| **Reviewer** | Human + Claude (retro review) |
| **gate_status** | PROMOTED |

## Evaluation Batteries

| Battery | Purpose | Script Path | Deal Count | Seed | Version |
|---------|---------|-------------|------------|------|---------|
| H2H battery | Pairwise competitive ordering | scripts/internal/run_arc_d_h2h_battery.py | 10,000/cell (FULL) | 42 | v4 |
| Comparator battery | Absolute metric extraction (8 bidders vs GluttonStrategy) | scripts/internal/run_auction_comparator.py | 20,000/bidder (single-seat) | 42 | v6 |
| Semantic gate | Model health checks (Tier 1 artifact integrity) | src/bid_euchre/diagnostics/semantic_gate.py | N/A (artifact checks) | N/A | — |
| Lambda sweep | Risk parameter sensitivity | scripts/internal/run_lambda_sweep.py | Simulation-based | 42 | v2 |
| Normalizer screen | Feature normalization impact | scripts/internal/run_normalizer_offline_screen.py | Offline | 42 | v1 |
| C33 ablation | Search vs wrapper effect decomposition | experiments/configs/arc_d_r0_c33_ablation.yaml | 90,000 (3 arms x 30k) | 42 | v2 |
| Eval dataset | Per-rung evaluation data (3-seed) | scripts/internal/run_arc_d_eval.py | 50,000 x 3 seeds | 42/43/44 | v2 |
| Pass-threshold sweep | Threshold sensitivity analysis | notebook 56 | 10,000 | 42 | v2 |
| Contract selection oracle | Oracle regret decomposition | notebook 55 | 40,000 (QUICK) | 42 | v2 |
| OneModel comparison | Single-model vs per-contract comparison | notebook 60 | 5,000 | 42 | v1 |

## Known Methodological Limitations

| ID | Description | Category | Notes |
|----|-------------|----------|-------|
| L1 | Best-of-4 selection effect in comparator | (b) | **Resolved** by single-seat redesign (#466, #470). v4+ evaluates one seat at a time. |
| L2 | LOD positional bias in comparator | (b) | **Resolved** (coupled with L1; same single-seat redesign fixes both) |
| L3 | bid_rate conflation in comparator | (b) | **Resolved** in comparator by single-seat mode; bid_rate now measures per-hand propensity. H2H bid_rate still conflates (team auction-win freq) — residual deferral, see B-L3. |
| L4 | GluttonStrategy confounding in comparator | (a) | Inherent to self-play design; opponent never bids, inflating declaring-team metrics. Play strategy now harmonized across instruments (C2c, #466). |
| L5 | Pairwise not round-robin H2H | (a) | H2H battery tests all pairs but not full round-robin tournaments; accepted for efficiency |
| L6 | Normalizer deferral | (a) | Normalizer screen showed +4% accuracy but -0.269 net_eppd. Deferred to R1 (NO_GO_DEFER_R1). Model poverty, not miscalibration — see [13_normalizer_offline_screen.md](13_normalizer_offline_screen.md) |
| L7 | Self-play vs H2H lambda divergence | (a) | Lambda=0.5 showed +0.884 in self-play but -1.15 in H2H. Self-play metrics can mislead for parameters affecting auction competitiveness. Lambda=0.0 RETAINED. See [12_lambda_decision.md](12_lambda_decision.md) |

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

### B-L3: bid_rate conflation — RESOLVED (comparator), residual deferral (H2H)

bid_rate conflation was a genuine methodology defect in the comparator: multi-seat
mode mixed auction-win frequency with bidding propensity. **Resolved** by
single-seat redesign (#466, #470). In v4+, bid_rate is a clean per-hand
propensity measure (one bidder, uncontested auction).

**Residual deferral (H2H):** H2H bid_rate still mixes voluntary and forced bids.
In the H2H battery, both teams participate in contested auctions, so a bidder's
observed bid_rate reflects both its intrinsic propensity and whether it was
outbid. This is an inherent property of the H2H estimand (competitive ordering),
not a remaining methodology defect — but users should interpret H2H bid_rate as
"team auction-win frequency" rather than "bidder selectivity."

## Blockers

None. All (c)-class items have been resolved or do not apply to R0.

## V2 Update Notes

The v2 canonical phase added two new evaluation instruments (lambda sweep,
normalizer screen) and updated the comparator battery to v6 (8 bidders with
bid-level search). Two new (a)-class limitations (L6, L7) document deferred
decisions from v2 screening. No new (b)- or (c)-class items were introduced.

The bid-level search (v2) resolved the pass-threshold problem that was the
dominant source of oracle regret in v1. The remaining regret is concentrated
in contract selection (CS regret share 90.9%), which is an (a)-class feature
poverty limitation addressable in R1.

## Sign-off

- [x] All evaluation batteries listed (including v2 additions)
- [x] All known limitations classified (a/b/c)
- [x] All (b) items have deferral cost descriptions
- [x] No (c) items remain unresolved
- [x] Rigor firewall applied (05_rigor.md blockers are category (c))
- [x] V2 canonical data versions noted (comparator v6, H2H v4)
