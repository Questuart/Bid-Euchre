# Comparator Methodology: Single-Seat Evaluation

> **Status:** Plan — ready for review
> **Scope:** Comparator battery experimental design change. Single-seat mode
> implementation, re-run protocol, artifact versioning, report updates.
> **Dependency:** `plans/bidder_correctness_fixes.md` — all bidder fixes
> (PR-B1 + PR-B2) must merge before the battery is re-run.
> **Extracted from:** `plans/comparator_experiment_redesign.md`
> **Companion doc:** `plans/comparator_rankings_review_notes.md` (report-level
> improvements, proceeds in parallel on existing data)

---

## Problem Statement

The current comparator battery runs a 4-way self-auction where all 4 seats
use the same bidding policy. This produces three interpretive artifacts:

1. **Best-of-4 selection effect** — the auction winner always has the
   strongest hand at the table, inflating make_rate and net_eppd.
2. **LOD positional bias** — seat 1 (left of dealer) bids against
   `current_high_bid=0`; the dealer must beat all previous bids.
3. **bid_rate conflation** — reported bid_rate is "probability at least 1
   of 4 seats bids," not the policy's per-hand selectivity.

These artifacts don't invalidate rank ordering (all policies face the same
design), but they make absolute metrics harder to interpret and not
comparable to H2H metrics.

**Decision (2026-02-26):** Single-seat becomes the primary comparator
methodology. The 4-way auction is retained as an optional sensitivity panel.

---

## Design: Single-Seat Evaluation

For each deal:
1. Randomly select 1 seat (using the deal's deterministic RNG).
2. That seat evaluates its hand with `current_high_bid=0`.
3. If it bids, play the hand with GreedyStrategy (all 4 seats).
4. If it passes, count as a pass deal (`numerator += 0, denominator += 1`).

### Metric computation (unchanged)

- `net_eppd = sum(declaring_pts - defending_pts) / total_deals`
- Pass deals contribute 0 to numerator, 1 to denominator.
- All metrics from the declaring team's perspective.

### What changes

| Metric | 4-way (v2) | Single-seat (v3) |
|--------|-----------|-----------------|
| bid_rate | P(≥1 of 4 seats bids) | P(this seat bids) |
| make_rate | Conditional on best-of-4 winner | Conditional on this seat's bid |
| net_eppd | Inflated by selection | Unbiased per-hand estimate |
| CVaR-5% | Worst 5% of best-of-4 | Worst 5% of single-seat |

### What stays the same

- **H2H battery** — unaffected (separate design, separate data)
- **Gate thresholds** — calibrated from H2H null signal, not comparator
- **C33 ablation** — uses H2H matchups, not comparator
- **Promotion decisions** — use H2H + semantic gate, not comparator
- **Pairwise significance** — valid within any consistent methodology

---

## Implementation

### Step 1: Add `AlwaysPassBidder` as sentinel for non-bidding seats

The simulation's `bidding_policies` parameter (`simulation.py:75–82`)
accepts a list of 4 policies. Passing `None` crashes at line 136 (no null
guard). Instead, use the existing `AlwaysPassBidder` (`bidding.py:154–163`)
for non-bidding seats:

```python
from bid_euchre.strategy.bidding import AlwaysPassBidder

# Single-seat: seat 2 bids, others always pass
pass_policy = AlwaysPassBidder()
policies = [pass_policy, pass_policy, target_policy, pass_policy]
```

**Seat randomization:** For each deal, pick the bidding seat using the
existing deterministic RNG: `seat = rng.randrange(4)` where `rng` is
`Random(deal_seed + deal_id)`. This is the same RNG source the simulation
already uses for dealer selection (`simulation.py:109`), ensuring
reproducibility.

**Important:** The bidding seat's `current_high_bid` will always be 0
because the other 3 seats always pass. The auction order (LOD) still runs,
but pass actions don't raise the bid. This gives Option A behavior (true
single-seat) with zero simulation changes.

### Step 2: Play policy clarification

**Current state:** The comparator config (`auction_comparator.yaml`) does
not set `play_strategy`. The simulation defaults to `GreedyStrategy`
(`simulation.py:70–72`):

```python
if strategy is None:
    strategy = GreedyStrategy()
```

The original `comparator_experiment_redesign.md` and some report text refer
to "GluttonStrategy" for card play, but the actual code uses
**GreedyStrategy**. This plan preserves the existing default (Greedy).

**Action:** Add an explicit comment to the comparator config or runner
documenting that the play policy is GreedyStrategy (the simulation default).
No code change needed.

### Step 3: Modify comparator runner

Add `--single-seat` flag to `scripts/internal/run_auction_comparator.py`.

When `--single-seat` is set:
- For each bidder, build a per-deal policy assignment that places the
  target bidder on one randomly-selected seat and `AlwaysPassBidder` on
  the other three.
- The simplest approach: wrap the existing per-bidder experiment in a
  loop or modify the config to use `bidding_policies` (list of 4) instead
  of `bidding_policy` (singular).

**Design detail — per-deal vs per-run seat assignment:**

Option 1: **Per-run fixed seat** — assign the bidder to seat 0 for all
10k deals. Simpler, but introduces seat bias (always bidding from the
same position relative to dealer).

Option 2: **Per-deal random seat** — for each deal, randomly assign the
bidder to one of 4 seats. Eliminates seat bias. Requires passing
`bidding_policies` per-deal rather than once per-run.

**Recommendation: Option 2.** The simulation already supports per-deal
dealer randomization. Extending to per-deal bidder-seat randomization is
a small change and eliminates a confounder.

**Implementation approach for Option 2:**
- The comparator runner cannot currently vary `bidding_policies` per-deal
  because `simulate_many_hands` takes a single `bidding_policies` list.
- **Simplest fix:** Add a new `SingleSeatBiddingPolicy` wrapper that
  internally randomizes which seat is "active" per deal:

```python
class SingleSeatBiddingPolicy(BiddingPolicy):
    """Wrapper that activates the inner policy only for a designated seat."""
    def __init__(self, inner: BiddingPolicy, active_seat: int):
        self.inner = inner
        self.active_seat = active_seat

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        if obs.seat == self.active_seat:
            return self.inner.choose_bid(obs)
        return BidAction.pass_bid()
```

Then pass `bidding_policy=SingleSeatBiddingPolicy(target, seat=deal_rng.randrange(4))`
as the singular policy for all 4 seats. Wait — this doesn't work because
the policy is shared across all seats in the same deal.

**Better approach:** Use the existing `bidding_policies` (list of 4) and
create a custom `simulate_many_hands` wrapper or modify the simulation to
accept a callback that varies the policy list per deal. But this is more
invasive.

**Simplest viable approach:** Use `bidding_policies` with a
`SeatAwareBiddingPolicy` that checks `obs.seat`:

```python
class SeatAwareBiddingPolicy(BiddingPolicy):
    """Routes to inner policy only for a randomly-selected seat per deal."""
    def __init__(self, inner: BiddingPolicy, seed: int):
        self.inner = inner
        self.seed = seed
        self._deal_seats = {}  # Cache: deal_id → active_seat

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        # Problem: obs doesn't carry deal_id, so we can't vary per-deal.
```

**Problem:** `BiddingObservation` does not include `deal_id`. Without it,
a policy wrapper can't determine which seat is active for this deal.

**Resolution — two viable paths:**

**Path A (Minimal code change):** Run 4 separate sub-experiments, one per
seat. Each sub-experiment places the bidder on seat K and AlwaysPassBidder
on the other 3. Each runs N/4 deals. Merge results. This is clean,
deterministic, and requires no simulation changes.

```
Seat 0: [target, pass, pass, pass] × 2,500 deals
Seat 1: [pass, target, pass, pass] × 2,500 deals
Seat 2: [pass, pass, target, pass] × 2,500 deals
Seat 3: [pass, pass, pass, target] × 2,500 deals
Total: 10,000 deals, perfectly balanced across seats
```

**Path B (Simulation change):** Add `deal_id` to `BiddingObservation`, then
use the `SeatAwareBiddingPolicy` wrapper.

**Recommendation: Path A.** No simulation changes needed. Perfect seat
balance (exactly 25% per seat). Deterministic with seed. The comparator
runner already knows how to create per-policy configs — extending to
per-seat configs is straightforward.

### Step 4: Deal count and power

**Problem:** Single-seat mode has a higher pass rate than 4-way mode.
For selective bidders like hybrid_olsa (currently 62.5% bid_rate in 4-way
mode), the per-hand bid rate will be lower, yielding fewer bid-hands and
wider CIs.

**Minimum bid-hand target:** For stable CIs on CVaR-5%, we need at least
~500 bid-hands in the 5th percentile tail. If a bidder bids 30% of hands:
- 10k deals → 3,000 bid-hands → 150 in 5th percentile → thin but viable
- 20k deals → 6,000 bid-hands → 300 in 5th percentile → adequate
- 50k deals → 15,000 bid-hands → 750 in 5th percentile → comfortable

**Decision needed:** What is the minimum acceptable CI width on CVaR-5%?

**Recommendation:** Start with **20,000 deals** (5,000 per seat × 4 seats).
This is a 2× increase from the current 10k, costs minutes of wall time,
and provides adequate power for all current bidders. If CIs are still too
wide for the most selective bidder, increase to 50k in a follow-up.

### Step 5: Re-run battery

After bidder fixes (PR-B1 + PR-B2) are merged:

```bash
PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml \
  --seed 42 --single-seat --n-per 20000 \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --bidder-class HybridOLSaBidder --bidder-name hybrid_olsa
```

(Exact flags TBD based on implementation.)

### Step 6: Re-run CI extraction

```bash
PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/artifacts/arc_d/r0 --runs-dir data/runs --seed 42 \
  --n-bootstrap 10000 \
  --output data/artifacts/arc_d/r0/comparator_cis_r0_v3.json \
  --battery-file comparator_battery_r0_v3.json
```

Version tag: **v3** (v1 = 5-bidder 4-way, v2 = 7-bidder 4-way,
v3 = 7-bidder single-seat).

### Step 7: Verify and crosswalk

- Compare v2 (4-way) and v3 (single-seat) rankings side by side.
- Document any rank changes and explain why (best-of-4 removal, ceiling/
  floor fixes, threshold recalibration).
- This crosswalk is diagnostic — it goes in the report's sensitivity
  section, not the primary results.

### Step 8: Update downstream reports

Merge with the report improvements from `comparator_rankings_review_notes.md`:

| File | Update |
|------|--------|
| `docs/04_reports/r0/comparator_rankings.md` | New numbers + methodology (v3) |
| `docs/04_reports/r0/h2h_battery_analysis.md` §3 | Cross-reference only (Note 7: remove duplication) |
| `docs/04_reports/r0/r0_promotion_report.md` | Update comparator context |

---

## Sensitivity Panel (Optional — Lower Priority)

Retain one 4-way battery run as an "auction-pressure sensitivity" panel.

**Purpose:** Show whether rank ordering changes under contested-auction
conditions. This answers "does the best-of-4 selection effect favor certain
policies?" without conflating it with the primary measurement.

**Implementation:** Re-use existing v2 data OR re-run with fixed bidders
for consistency. Label explicitly as "sensitivity analysis" in the report.

**Recommendation:** Defer to after the primary single-seat battery is
complete and reviewed. The v2 data already exists and can be referenced
without a new run. Only re-run if bidder fixes change results enough
that the v2 data is no longer representative.

---

## PR Structure

**PR-C1: Single-seat mode implementation**
- Comparator runner: `--single-seat` flag + per-seat sub-experiment logic
- Config updates (if needed)
- Tests for the new mode
- Does NOT include experiment results or report updates

**PR-C2: Battery re-run + report updates**
- New v3 artifacts (not committed — data policy)
- Updated `comparator_rankings.md` with v3 numbers
- v2 → v3 crosswalk in sensitivity section
- Report improvements from review notes (merged)

### Sequencing

```
PR-B1 (Fix A+B) ──┐
                   ├──→ PR-C1 (single-seat mode) → PR-C2 (rerun + report)
PR-B2 (Fix C) ────┘
```

PR-B1 and PR-B2 can parallel. PR-C1 can parallel with PR-B1/B2 (code
doesn't depend on bidder fixes). PR-C2 must wait for all three to merge.

---

## Open Questions

1. **Deal count:** 20k recommended. Is this sufficient, or should we go
   straight to 50k? Compute is cheap; the only cost is slightly larger
   JSONL logs.

2. **Artifact naming:** `comparator_cis_r0_v3.json` vs
   `comparator_single_seat_r0.json`. v3 maintains the version sequence;
   the descriptive name is more self-documenting. Recommend v3 for
   consistency with existing v1/v2 naming.

3. **Sensitivity panel timing:** Run alongside v3, or defer to a later PR?
   Recommend defer — the v2 data is already available for comparison.

---

## Key Files

| File | Role |
|------|------|
| `scripts/internal/run_auction_comparator.py` | Runner (modify: add --single-seat) |
| `scripts/internal/extract_comparator_cis.py` | CI extraction (minor: version tag) |
| `src/bid_euchre/sim/simulation.py` | Simulation (NO changes needed with Path A) |
| `src/bid_euchre/strategy/bidding.py` | `AlwaysPassBidder` (existing, used as sentinel) |
| `experiments/configs/auction_comparator.yaml` | Config (document play policy) |
| `docs/04_reports/r0/comparator_rankings.md` | Report (update with v3 data) |
| `plans/comparator_rankings_review_notes.md` | Report improvements (merge into PR-C2) |
