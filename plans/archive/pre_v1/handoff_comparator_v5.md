# Handoff: Comparator v5 — Bid Floor Removal + Full Re-run

## Context

A Q&A review of R0 reports (see `plans/r0_report_qa.md`, Q2) found that two
comparator bidders have artificial bid floors that suppress valid low bids:

- **ModeloEspecifico** — floor of 3 at `bidding.py:455`. Formula can produce
  scores of 1–2 but the guard `3 <= bid_n` rejects them. Current bid_rate=0.986.
- **RanktheTank** — suit thresholds start at strength≥200→bid 3, HIGH/LOW at
  strength≥200→bid 3. No path to bid 1 or 2. Current bid_rate=1.000 (but only
  because almost all hands score ≥200; some edge cases are silently skipped).

The previous fix round (PRs #463–#465, v2→v3) raised ModeloEspecifico's ceiling
6→10 and lowered OLSa's floor 3→1, but kept ModeloEspecifico's floor at 3 and
didn't touch RanktheTank's suit floor.

**Other bidders are correct:**
- hybrid_olsa: floor 1, ceiling 10, EV>0 economic gate — OK
- olsa / olsa_full: floor 1, ceiling 10 — OK
- stricthellraiser: always bids 3+ (design intent, dumb baseline) — OK
- fiveheadfred: always bids exactly 5 (design intent) — OK

## Goal

Remove artificial bid floors from ModeloEspecifico and RanktheTank, then re-run
the full experiment pipeline and regenerate all affected reports.

## Step 1: Code Fixes

### ModeloEspecifico (`src/bid_euchre/strategy/bidding.py`, class at L423)

Three guards need `3` changed to `1`:

- **L455**: `if 3 <= bid_n <= 10` → `if 1 <= bid_n <= 10`
- **L462**: `if 3 <= bid_n_high <= 10` → `if 1 <= bid_n_high <= 10`
- **L469**: `if 3 <= bid_n_low <= 10` → `if 1 <= bid_n_low <= 10`

Also delete the stale comment at L453–454 ("Floor of 3 is intentional...").

### RanktheTank (`src/bid_euchre/strategy/bidding.py`, class at L321)

Extend threshold tables to cover bids 1–10 (currently 3–10 for suit, 3–8 for
HIGH/LOW).

**Suit thresholds** (L348–366): Add two lower tiers:
```
elif strength >= 150:
    bid_n = 2
elif strength >= 100:
    bid_n = 1
```

**HIGH thresholds** (L374–387): Add two lower tiers:
```
elif strength >= 150:
    bid_n = 2
elif strength >= 100:
    bid_n = 1
```
Also extend ceiling: currently maxes at 500→bid 8. Add 550→9, 600→10 (or
appropriate values consistent with the suit thresholds' progression).

**LOW thresholds** (L394–407): Same changes as HIGH.

**Design note:** `score_hand_scalar()` (at `hand_eval.py:497`) uses
uniform 10-point spacing per rank. For suit: right bower=120, left=110,
trump A=100...T=60, offsuit A=50...T=10. A 10-card hand ranges roughly
100–1200 for suit. For HIGH/LOW: (rank_strength+1)*10, so 10–50 per card,
range ~100–500. The new thresholds should ensure even weak hands produce
bid_n=1, not a pass. Pick threshold values that are reachable (check
minimum possible scores via the scoring formula).

### Tests

Run existing tests for these bidders:
```bash
uv run python -m pytest tests/ -k "modelo or rankthetank or rank_the" -v
```

Add/update tests to verify:
- ModeloEspecifico bids 1 or 2 on a weak hand (construct a hand with
  0 bowers, 2 trump, 0 aces → score 1.0 → should bid 1)
- RanktheTank bids 1 on a minimal-strength hand
- Neither bidder has an artificial floor above 1

## Step 2: Re-run Comparator Battery → v5

```bash
uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml \
  --seed 42 \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --bidder-class HybridOLSaBidder \
  --bidder-name hybrid_olsa \
  --mode single_seat \
  --n-per 5000
```

This produces 20,000 deals/bidder (5,000/seat × 4 seats) × 7 bidders.
Save output as `comparator_battery_r0_v5.json`.

Then extract bootstrap CIs:
```bash
uv run python scripts/internal/extract_comparator_cis.py \
  --input <v5_run_dir> \
  --output data/artifacts/arc_d/r0/comparator_cis_r0_v5.json \
  --seed 42 --n-bootstrap 10000
```

## Step 3: Re-run H2H Battery → v3

```bash
uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --config experiments/configs/arc_d_r0_head_to_head.yaml \
  --seed 42 \
  --mode QUICK
```

Then FULL mode:
```bash
uv run python scripts/internal/run_arc_d_h2h_battery.py \
  --config experiments/configs/arc_d_r0_head_to_head.yaml \
  --seed 42 \
  --mode FULL
```

Save as `h2h_battery_quick_v3.json` and `h2h_battery_full_v3.json`.

## Step 4: Update Rung Bundle

Edit `data/artifacts/arc_d/r0/rung_bundle_r0.json`:
- `comparator_battery` → `data/artifacts/arc_d/r0/comparator_battery_r0_v5.json`
- `h2h_battery_quick` → `data/artifacts/arc_d/r0/h2h_battery_quick_v3.json`
- `h2h_battery_full` → `data/artifacts/arc_d/r0/h2h_battery_full_v3.json`

## Step 5: Re-run Notebooks

These notebooks read from the bundle or directly from run data:

| Notebook | Why | Priority |
|----------|-----|----------|
| `45_comparator_deep_dive.py` | Reads comparator data directly | MUST |
| `50_r0_matchups.py` | Reads H2H data | MUST |
| `40_r0_baseline.py` | Reads bundle (comparator summary) | MUST |
| `55_contract_selection_oracle.py` | Independent (uses bidless data) | SKIP (no change) |
| `56_pass_threshold_sweep.py` | Independent (uses bidless data) | SKIP (no change) |

Run in SMOKE mode first to verify execution, then QUICK for report-quality:
```bash
MODE=SMOKE make notebook-run
```

## Step 6: Regenerate Reports

Reports that cite comparator or H2H numbers (grep confirmed):

| Report | What changes |
|--------|-------------|
| `comparator_rankings.md` | Rankings table, pairwise significance, behavioral profiles, conclusions — **full rewrite of data sections** |
| `h2h_battery_analysis.md` | H2H deltas, competitive ranking, conclusions |
| `c33_ablation_report.md` | Cites comparator gap (modeloespecifico vs hybrid_olsa) |
| `model_arc_r0.md` | Cites campaign totals, comparator ranking summary |
| `dual_track_analysis.md` | Cites comparator rankings, tier classification |
| `r0_promotion_report.md` | Cites comparator and H2H summary metrics |
| `r0_retrospective.md` | Cites comparator summary |
| `measurement_integrity_r0.md` | References comparator methodology (probably no data changes) |
| `pass_threshold_decision.md` | May cite comparator gap — check |

**Approach:** After experiments complete, diff the v4→v5 comparator CIs and
v2→v3 H2H results. Use the deltas to identify which specific numbers changed
in each report. Most reports will need surgical updates to tables and prose
that cite specific net_eppd values.

## Step 7: Validation

- `make check-quiet` passes
- `make notebook-check` passes (sync clean, outputs stripped)
- Spot-check: `grep -r "bid_rate.*0\.986" docs/04_reports/r0/` — should reflect new value
- Spot-check: `grep -r "1\.587" docs/04_reports/r0/` — modeloespecifico net_eppd will change
- Compare v4 vs v5 rankings to verify RanktheTank/ModeloEspecifico shifted as expected

## PR Strategy

Recommend **2 PRs** (can be stacked or sequential):

1. **PR-code**: Code fixes (ModeloEspecifico + RanktheTank) + tests. Small, reviewable.
2. **PR-rerun**: Experiment re-runs + report regeneration + notebook updates + bundle update. Larger but mechanical.

Alternative: single PR if the cascade is small (unlikely given 8+ report files).

## Version History Reference

| Version | Date | Changes |
|---------|------|---------|
| v1 | 2026-02-23 | Initial (5 bidders, 10k deals, 4-way) |
| v2 | 2026-02-25 | Added olsa_full + olsa (7 bidders) |
| v3 | 2026-02-28 | Bidder fixes A/B/C, single-seat mode |
| v4 | 2026-02-28 | GluttonStrategy harmonization |
| **v5** | **TBD** | **ModeloEspecifico floor 3→1, RanktheTank thresholds 1–10** |
