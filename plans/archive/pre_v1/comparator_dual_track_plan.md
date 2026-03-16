# Comparator Dual-Track & Roster Meta-Analysis Plan

> **Status:** Plan — ready for review.
> **Date:** 2026-02-28
> **Depends on:** PR-C2 (v3 battery complete), Wave 1 bugfixes (#463, #464, #465 merged)
> **Context:** Discussion session analyzing comparator vs H2H relationship, context
> feature readiness, and reporting enhancements.

---

## Background

### Key Findings from Analysis Session

1. **The old comparator (v1/v2) and H2H self-play diagonal were mechanically
   identical.** Both put the same bidding policy in all 4 seats with a sequential
   auction. The only difference was metric extraction: the comparator computed
   absolute net_eppd, the H2H computed team deltas (≈0 for self-play).

2. **Single-seat mode (#464) was the actual innovation.** It replaced the 4-way
   auction with 1-bidder + 3-always_pass, giving every bid decision a direct
   outcome with no survivorship bias.

3. **The two instruments measure fundamentally different things:**

   | | Single-Seat Comparator | H2H Battery |
   |---|---|---|
   | Measures | Individual bid decision quality | Game performance (bid + defend) |
   | Every decision evaluated? | Yes | Only auction winner's |
   | Survivorship bias? | None | Yes — losing bids unobserved |
   | Context features work? | No (always_pass neighbors) | Yes (real auction dynamics) |
   | Absolute ranking? | Yes (net_eppd) | Not currently extracted (only deltas) |

4. **No third instrument needed.** The contextual comparator proposal was
   evaluated and deferred — the H2H cross-cells already provide context
   robustness signal when sliced by opponent archetype. A dedicated contextual
   comparator would become relevant at R2+ when bidders actually consume context
   features; building it now would require committing to archetype choices before
   we know which contexts differentiate good bidders from bad ones.

5. **The H2H battery data is stale.** Generated 2026-02-26, before bugfix PRs
   #463/#464/#465 merged on 2026-02-27.

6. **The H2H parser doesn't extract absolute net_eppd.** `_compute_team_points()`
   returns absolute `(t0_pts, t1_pts)` but the parser immediately collapses to
   `delta = t0_pts - t1_pts`. The field `net_eppd_a` is misleadingly named — it
   is the delta, not an absolute per-team metric.

### Design Decisions

- **Dual-track evaluation:** Always report both single-seat (decision quality)
  and H2H self-play absolute (game performance). Neither substitutes for the
  other.
- **Archetype segmentation:** Tag bidders by behavioral archetype
  (AGGRESSIVE/NEUTRAL/SELECTIVE) derived from bid_rate × make_rate. Slice H2H
  cross-cells by opponent archetype for context robustness signal.
- **Roster meta-analysis:** Scatter plots decomposing rankings into behavioral
  components (selectivity, accuracy, efficiency).
- **Context features deferred to R2:** `BiddingObservation.auction_transcript`
  is the prerequisite; no context-aware bidders exist at R0-R1.

---

## Work Items

### W1. C2b — Comparator Report Updates

**Scope:** Consume v3 single-seat artifacts (already produced by PR-C2) to
update existing reports.

**Files to modify:**
- `docs/04_reports/arc_d_v1/r0/comparator_rankings.md` — v3 numbers, methodology note
- `docs/04_reports/arc_d_v1/r0/h2h_battery_analysis.md` — Remove §3 duplication, fix
  terminology, update v2 provenance
- `docs/04_reports/arc_d_v1/r0/r0_promotion_report.md` — Update comparator context table
- `docs/04_reports/arc_d_v1/r0/model_arc_r0.md` — Update 5-bidder → 7-bidder v4 (renamed from `model_arc_r0_20260224.md`)
- `docs/04_reports/arc_d_v1/r0/measurement_integrity_r0.md` — Update to reflect GluttonStrategy
  as canonical comparator play strategy (post-C2c/#466 state)

**Artifacts consumed:**
- `data/artifacts/arc_d/r0/comparator_battery_r0_v3.json`
- `data/artifacts/arc_d/r0/comparator_cis_r0_v3.json`

**Blockers:** None — artifacts exist.

---

### W2. Rerun H2H Battery Post-Bugfix

**Scope:** Run-only. Existing H2H data predates #463/#464/#465. Rerun with
corrected bidders.

**Command:**
```bash
PYTHONPATH=src .venv/bin/python scripts/internal/run_arc_d_h2h_battery.py \
    --mode QUICK --seed 42 --n-per 2000 \
    --output data/artifacts/arc_d/r0/h2h_battery_quick_v2.json

# Then FULL subset:
PYTHONPATH=src .venv/bin/python scripts/internal/run_arc_d_h2h_battery.py \
    --mode FULL --seed 42 --n-per 10000 \
    --quick-summary data/artifacts/arc_d/r0/h2h_battery_quick_v2.json \
    --output data/artifacts/arc_d/r0/h2h_battery_full_v2.json
```

**Expected:** 49 matchups (QUICK), subset at higher N (FULL). Same 7 bidders.

**Artifacts produced (NOT committed):**
- `data/artifacts/arc_d/r0/h2h_battery_quick_v2.json`
- `data/artifacts/arc_d/r0/h2h_battery_full_v2.json`

**Validation:**
- All 49 cells populated (QUICK)
- Self-play diagonal deltas ≈ 0 (sanity)
- Behavioral shifts consistent with bugfixes (ModeloEspecifico, RanktheTank, OLSa)

**Blockers:** None — run-only, no code changes.

---

### W3. Extract Absolute Per-Team net_eppd from H2H

**Scope:** Code change to `scripts/internal/run_arc_d_h2h_battery.py` parser.

**Problem:** `_compute_team_points()` returns absolute `(t0_pts, t1_pts)` but
the parser at lines 519-520 immediately collapses:
```python
t0_pts, t1_pts = _compute_team_points(rec)
delta = t0_pts - t1_pts   # absolute values discarded
```

**Change:** Accumulate absolute per-team totals alongside deltas:
```python
t0_pts, t1_pts = _compute_team_points(rec)
delta = t0_pts - t1_pts
deltas.append(delta)
team0_points_abs.append(t0_pts)   # NEW
team1_points_abs.append(t1_pts)   # NEW
```

Then add to cell output:
```python
cell["abs_net_eppd_team0"] = round(float(np.mean(team0_points_abs)), 6)
cell["abs_net_eppd_team1"] = round(float(np.mean(team1_points_abs)), 6)
```

For self-play cells, both teams use the same bidder, so
`(abs_team0 + abs_team1) / 2` gives the bidder's absolute net_eppd under full
auction dynamics.

**Files to modify:**
- `scripts/internal/run_arc_d_h2h_battery.py` — parser section (~10 lines)

**Tests:**
- Verify `abs_net_eppd_team0 - abs_net_eppd_team1 ≈ net_eppd_delta` (consistency)
- Self-play: `abs_team0 ≈ abs_team1` (symmetry)

**Blockers:** None (but logically pairs with W2).

---

### W4. Self-Play Absolute Ranking Extraction

**Scope:** New extraction path that reads H2H self-play cells and produces a
rankings artifact parallel to the single-seat one.

**Output format:** Same schema as `comparator_cis_r0_v3.json` but sourced from
H2H self-play. Per bidder:
- `abs_net_eppd` (average of team0 + team1 absolute from W3)
- `bid_rate`, `make_rate` (already in H2H cells as `bid_rate_a`/`bid_rate_b`)
- `cvar_5` (already extracted)
- Bootstrap CIs on absolute metric

**Implementation options:**
- Extend `extract_comparator_cis.py` with `--source h2h-self-play` flag, or
- Add extraction logic to `run_arc_d_h2h_battery.py` summary output

**Files to modify:** TBD based on approach choice.

**Depends on:** W3 (absolute metrics in H2H cells).

---

### W5. Extend BiddingObservation with auction_transcript

**Scope:** Foundation for R2 context features. No bidders consume it yet.

**Change to `src/bid_euchre/strategy/bidding.py`:**
```python
@dataclass(frozen=True)
class BiddingObservation:
    hand: List[Card]
    seat: int
    dealer_seat: int
    current_high_bid: int
    auction_transcript: Tuple[dict, ...] = ()  # NEW: prior actions in bid order
    allowed_contracts: Tuple[str, ...] = (...)
```

**Change to `src/bid_euchre/sim/simulation.py`:**
In the auction loop (lines 122-182 for seat_bidding_policies path, lines
189-203 for single-policy path), pass accumulated `_transcript` entries into
each `BiddingObservation`:
```python
obs = BiddingObservation(
    hand=starting_hands[player_idx],
    seat=player_idx,
    dealer_seat=dealer_index,
    current_high_bid=current_high_bid,
    auction_transcript=tuple(_transcript),  # NEW
)
```

**Backward compatible:** Default `()` means existing bidders ignore it.

**Files to modify:**
- `src/bid_euchre/strategy/bidding.py` — dataclass field
- `src/bid_euchre/sim/simulation.py` — pass transcript in both auction paths

**Tests:**
- Existing tests pass unchanged (default `()`)
- New test: verify transcript accumulates correctly across seats

**Blockers:** None — independent of all other items.

---

### W6. Dual-Track Comparator Report

**Scope:** Present both ranking tracks side-by-side in the comparator report.

**Content:**
- Single-seat rankings (decision quality track) — from v3 artifacts
- H2H self-play absolute rankings (game performance track) — from W3/W4
- Agreement/disagreement analysis between tracks
- Documentation of what each track measures and why both matter

**Depends on:** W1, W2, W3, W4.

---

### W6b. Archetype-Segmented H2H Performance Summary

**Scope:** Tag bidders by behavioral archetype and slice H2H cross-cells.

**Archetype definitions (derived from bid_rate × make_rate):**

| Category | Criterion | R0 Bidders |
|---|---|---|
| AGGRESSIVE | bid_rate=1.0 AND make_rate < 0.6 | fiveheadfred, rankthetank |
| SELECTIVE | bid_rate < 1.0 | hybrid_olsa, modeloespecifico |
| NEUTRAL | bid_rate=1.0 AND make_rate ≥ 0.6 | stricthellraiser, olsa, olsa_full |

**Implementation:**
- Add `archetype` field to bidder roster config or a lookup dict in the report
  extractor
- Group H2H cross-cell deltas by opponent archetype
- Per-bidder summary table: mean delta vs AGGRESSIVE / NEUTRAL / SELECTIVE

**Output example:**
```
Bidder              vs AGGRESSIVE    vs NEUTRAL    vs SELECTIVE
hybrid_olsa            +2.17           +0.58            —
modeloespecifico       +1.82           -0.03          +0.64
...
```

**Files to modify:**
- H2H report extractor or report template (TBD)
- Bidder roster config (add archetype tags)

**Depends on:** W2 (post-bugfix H2H data).

---

### W6c. Bidder Roster Meta-Analysis Scatter Plots

**Scope:** Three scatter plots decomposing the rankings into behavioral
components.

**Plot 1: bid_rate × make_rate (Calibration)**
- X: bid_rate (selectivity), Y: make_rate (accuracy)
- Shows who is overbidding (high bid_rate, low make_rate) vs well-calibrated
- A "perfect" bidder would be top-left (selective) or top-right (bids often,
  still makes)

**Plot 2: bid_rate × net_eppd (Efficiency)**
- X: bid_rate, Y: net_eppd
- Shows the payoff curve of selectivity
- Key question: is it better to bid rarely and make most, or bid always and
  accept sets?
- The efficient frontier would be visible

**Plot 3: make_rate × net_eppd (Conversion)**
- X: make_rate, Y: net_eppd
- Two bidders with same make_rate can have different net_eppd if bid levels
  differ
- Shows who converts makes into points efficiently

**For all plots:**
- Points labeled by bidder name
- Colored by archetype (AGGRESSIVE=red, NEUTRAL=blue, SELECTIVE=green)
- Tracked longitudinally across rungs (R0, R1, R2, ...)

**Data source:** Single-seat comparator artifacts (v3 for R0) — absolute
metrics, every bid evaluated, no survivorship filtering.

**Files to create/modify:**
- New visualization in `src/bid_euchre/diagnostics/` or a notebook in
  `notebooks/arc_d/`
- Report template update to embed or reference plots

**Depends on:** v3 artifacts exist (PR-C2 complete). Can be done independently
of W2-W4.

---

## Dependency Graph

```
W1 (C2b report)        ─── no blockers, uses existing v3 artifacts
W2 (H2H rerun)         ─── no blockers, run-only
W5 (auction_transcript) ── no blockers, independent foundation

W3 (absolute extraction) ─ logically pairs with W2 but no hard dependency
W4 (self-play rankings)  ─ depends on W3

W6 (dual-track report)  ─── depends on W1 + W2 + W3 + W4
W6b (archetype summary)  ── depends on W2
W6c (scatter plots)      ── depends on v3 artifacts (already exist)
```

**Parallelism opportunities:**
- W1, W2, W5, W6c can all proceed in parallel immediately
- W3 can start immediately (code change) and be validated against W2 output
- W4 depends on W3
- W6 and W6b are the final integration steps

---

## Scope Boundaries

**In scope:**
- Report updates consuming existing v3 artifacts (W1)
- H2H battery rerun with post-bugfix bidders (W2)
- H2H parser enhancement for absolute metrics (W3)
- Self-play absolute ranking extraction (W4)
- BiddingObservation.auction_transcript foundation (W5)
- Dual-track report format with archetype segmentation and scatter plots (W6/6b/6c)

**Deferred to R2:**
- Context-aware bidder implementation (consumes auction_transcript)
- Contextual comparator instrument (reassess when context features exist)
- Context feature ablation analysis (single-seat vs self-play delta)

**Deferred to later:**
- Contract-type faceted breakdowns (notebook 45_comparator_deep_dive.py)
- 4-way sensitivity panel comparison
- Promotion gate changes based on dual-track rankings

---

## PR Structure (Tentative)

| PR | Work Items | Type | Blockers |
|----|-----------|------|----------|
| C2b | W1 | Report edits | None |
| C3 | W2 | Run-only | None |
| C4 | W3 + W4 | Code + extraction | W2 for validation |
| C5 | W5 | Code (foundation) | None |
| C6 | W6 + W6b + W6c | Report + viz | C2b, C3, C4 |

One concept per PR. C2b and C3 can proceed in parallel. C5 is independent.
C4 needs C3 data for validation but code can be written first. C6 is the
integration PR that ties everything together.
