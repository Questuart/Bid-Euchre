# Comparator Experiment Redesign: Single-Seat Evaluation

> **Status:** Review notes — ready for external agent review and plan development.
> **Scope:** Comparator battery experimental design. R0 re-run + methodology
> change. Does NOT cover report quality improvements (see
> `plans/comparator_rankings_review_notes.md` for report-level changes).
> **Relationship to report:** The report improvements (Notes 1-10 in review
> notes) can proceed in parallel on existing data. This redesign would produce
> new data that the report then consumes. The two workstreams merge when the
> report is updated with new numbers.

---

## Problem Statement

The current comparator battery runs a 4-way self-auction where all 4 seats use
the same bidding policy. This design produces three interpretive artifacts that
complicate what should be a simple "how good is this policy?" measurement:

1. **Best-of-4 selection effect** — the auction winner always has the strongest
   hand at the table, inflating make_rate and net_eppd
2. **LOD positional bias** — the first bidder bids against `current_high_bid=0`
   while the dealer must beat all previous bids
3. **bid_rate conflation** — reported bid_rate reflects "probability at least 1
   of 4 seats bids," not the policy's per-hand selectivity

These artifacts don't invalidate the rank ordering (all policies face the same
design), but they make absolute metrics (net_eppd, bid_rate, make_rate) harder
to interpret and not directly comparable to H2H metrics.

---

## Current Design: How It Works

### Code path

1. `scripts/internal/run_auction_comparator.py` runs each bidder individually.
   For each bidder, it creates a per-policy config and calls the experiment
   runner.

2. The runner calls `simulate_many_hands()` with `bidding_policy=policy`
   (singular, not per-seat).

3. In `src/bid_euchre/sim/simulation.py` `play_single_hand()` (line 189-203),
   when a singular `bidding_policy` is provided, ALL 4 seats call
   `bidding_policy.choose_bid()` with their own hand and the current auction
   state.

4. The auction is sequential (LOD order: left of dealer → clockwise → dealer).
   Each bid must be **strictly** greater than `current_high_bid`. Both the
   policies themselves and the simulation enforce this:
   - `OLSaBidder.choose_bid()` line 741: `bid_n > obs.current_high_bid`
   - `HybridOLSaBidder.choose_bid()` line 1014: `bid_n <= obs.current_high_bid: continue`
   - Simulation line 160-161: `bid_action.n <= current_high_bid` → treated as pass

5. Dealer position is pseudo-random per deal: `Random(deal_seed + deal_id)`
   (line 109).

6. GluttonStrategy handles all card play for all 4 seats.

### Metric computation

The extraction script (`scripts/internal/extract_comparator_cis.py`) computes:
- `net_eppd = sum(declaring_pts - defending_pts) / total_deals`
- Always from the **declaring team's perspective**
- Pass deals (all 4 seats pass) contribute 0 to numerator, 1 to denominator

This means net_eppd is NOT zero-centered in self-play. Declaring is
structurally advantageous when you make your bid: net = `2 * tricks - 10`.
A policy that makes 90% of bids (modeloespecifico) gets +2.291 net_eppd.
A policy that overbids (stricthellraiser) gets -6.114. Both are self-play.

### Positional bias example

With identical OLSa policies on all 4 seats:
- Seat 1 (LOD): predicts `floor(mu) = 6`, sees `current_high_bid=0` → **bids 6**
- Seat 3: predicts `floor(mu) = 6`, sees `current_high_bid=6` → 6 is not > 6 →
  **forced to pass**

Two equally good hands get different outcomes based solely on auction position.

### bid_rate interpretation

- hybrid_olsa bid_rate = 62.5% means: on 62.5% of deals, **at least 1 of 4
  seats** had a hand good enough to bid. The per-hand selectivity rate is
  lower.
- For always-bid policies: bid_rate = 100% because at least 1 seat always bids
  (4 chances).

---

## Proposed Design: Single-Seat Evaluation

For each deal, randomly select 1 seat. That seat evaluates its hand with
`current_high_bid=0` and either bids its best contract or passes. If it bids,
play the hand with GluttonStrategy (all 4 seats). If it passes, count as a
pass deal (numerator += 0, denominator += 1).

### Pros

1. **Cleaner intrinsic measurement.** Directly answers "given a random hand,
   how well does this policy bid?" No best-of-4 inflation.

2. **No positional bias.** Every hand is evaluated with `current_high_bid=0`.
   No LOD advantage, no dealer disadvantage.

3. **bid_rate is directly interpretable.** Measures the policy's per-hand
   selectivity. hybrid_olsa's bid_rate would report how often the policy bids
   on an average hand, not the compound probability across 4 seats.

4. **Simpler to explain.** "Each bidder evaluates 10,000 random hands" vs
   "Each bidder runs a 4-way self-auction on each deal."

5. **Cheaper to run.** 1 policy evaluation per deal instead of 4.

6. **net_eppd interpretation improves.** Still measured from declarer's
   perspective (positive = profitable contracts), but without best-of-4
   inflation. Makes absolute values more meaningful for cross-rung tracking.

### Cons

1. **Higher pass rate → fewer bid-hands → wider CIs.** For selective bidders
   like hybrid_olsa, the per-hand pass rate will be much higher than the
   current best-of-4 rate. Fewer bid-hands means wider CIs on make_rate and
   CVaR. **Mitigation:** Increase deal count (e.g., 20k or 50k instead of
   10k). Compute is cheap.

2. **Rankings might shift.** The best-of-4 effect could differentially benefit
   some policies. If rankings change, downstream reports need updating.
   **Counter:** If rankings change, the current ones are misleading — better
   to know.

3. **Doesn't test `current_high_bid` interaction.** Future policies with
   opponent modeling may behave differently based on auction context. Single-
   seat with `current_high_bid=0` doesn't test this. **Counter:** The current
   4-way design doesn't test this either — all 4 seats use the same policy,
   so there's no meaningful strategic interaction. H2H is the right place to
   test auction dynamics.

4. **Less "realistic."** In a real game, you face an auction. **Counter:**
   The 4-way self-auction isn't realistic either — real opponents use different
   policies. Neither design simulates a real auction; single-seat is at least
   honest about what it measures.

---

## Why R0 Is the Ideal Time

1. **No backward compatibility cost.** R0 is rung zero — there's no prior
   rung to crosswalk against. At R1+, we'd need dual runs to maintain
   comparability.

2. **R1 hasn't started.** The R0→R1 transition is complete but no R1
   experiments have run. Cleanest possible transition point.

3. **Compute is cheap.** 7 bidders × 10-50k deals = minutes of wall time.

4. **Reports need updates anyway.** The comparator rankings report has 10
   improvement notes pending. Changing the underlying numbers is incremental.

---

## What's NOT Affected

Regardless of which comparator design is used:

- **H2H battery** is unaffected (separate design, separate data)
- **Gate thresholds** are calibrated from H2H null signal, not comparator
- **C33 ablation** uses H2H matchups, not comparator
- **Promotion decisions** use H2H + semantic gate, not comparator rankings
- **Pairwise significance** tests are valid within any consistent methodology

The comparator is used for *absolute benchmarking* and *progress tracking*, not
for promotion decisions. Changing its design doesn't affect the gate.

---

## Pre-Requisite Fixes (before re-running)

### Fix A: Remove ModeloEspecifico bid ceiling

`ModeloEspecifico.choose_bid()` (bidding.py lines 438, 445, 452) caps bids at
`<= 6`. The game rules allow bids 1-10 (RULES.md §3.2, line 111). OLSaBidder
and HybridOLSaBidder correctly use `<= 10`. The `<= 6` cap has no documented
rationale — it was present from the initial implementation (PR #154) and was
never revisited.

**Effect of the bug:** Hands scoring > 6 in the formula (e.g., 2 bowers + 6
trump + 2 offsuit aces = 7.0) get **no bid at all** in that contract type,
rather than bidding 6. This silently suppresses strong hands and artificially
deflates bid_rate while inflating make_rate.

**Fix:** Change `<= 6` to `<= 10` on all three guard lines (suit, HIGH, LOW).
The formula's practical maximum for suit is ~9 (4 bowers + 10 trump + 0 aces),
so bids of 7-9 become possible for very strong hands.

**Impact on comparator results:** ModeloEspecifico's bid_rate may increase
slightly (more hands qualify) and its net_eppd could change. Rankings may shift.
This is a correctness fix — the current results are based on a bugged bidder.

### Fix B: Remove bid floor from OLSa-family bidders

OLSaBidder (line 741) and HybridOLSaBidder use `3 <= bid_n` as a minimum bid.
The game rules (RULES.md §3.2, line 115) explicitly state: "the first non-pass
bid may be as low as **1**." There is no documented rationale for the `>= 3`
floor.

For OLSaBidder, if the model predicts `mu = 1.7`, flooring to `bid_n = 1` is
a legal bid that reflects the model's assessment. Whether it's profitable is
the model's problem, not the guard clause's.

For HybridOLSaBidder, the `>= 3` floor is even less defensible: the Gaussian
EV wrapper already gates on `EV > 0`. If the model says bidding 1 is positive
EV, the floor overrides that judgment.

**Fix:** Change `3 <= bid_n <= 10` to `1 <= bid_n <= 10` in OLSaBidder and
HybridOLSaBidder. For heuristic bidders (ModeloEspecifico, RanktheTank, etc.),
the `>= 3` floor may be an intentional design choice since their formulas are
hand-tuned — leave as-is but document the rationale in their docstrings.

**Impact:** Likely minimal for trained models (OLS predictions of < 3 are
rare for hands worth bidding), but removes an artificial constraint that could
mask model behavior at the margins.

### Fix C: Recalibrate RanktheTank thresholds from empirical data

RanktheTank uses `score_hand_scalar()` (exposed as `hand_value` in the feature
set) with fixed thresholds to map strength → bid level:
- Suit: 200→3, 250→4, 300→5, 350→6 (max bid 6, range covers ~200-350 of a
  100-1000 scale)
- HIGH/LOW: 20→3, 30→4, 40→5 (max bid 5)

**Two bugs:**
1. **Suit ceiling at 6.** The threshold table only goes up to 350→6. Hands
   scoring 400-1000 still bid 6. Bids of 7-10 are unreachable.
2. **HIGH/LOW thresholds are miscalibrated.** `score_hand_scalar` for HIGH/LOW
   returns 100-500 (10 cards × 10-50 per card). The thresholds (20, 30, 40)
   are far below the minimum possible score of 100. Every hand that gets
   evaluated for HIGH/LOW hits the top threshold (40) and bids 5. The
   `elif` and `else` branches are dead code.

**Fix: Derive thresholds empirically from the canonical bidless dataset.**

**Data source:** `canonical_bidless_dataset_glutton_42_20260221_175752`
- ~1.2M rows (50k deals × 4 seats × 6 scenarios)
- Each row has `hand_value` (= `score_hand_scalar`), `contract_type`, `seat`
- Outcomes dataset has `tricks_team0`/`tricks_team1` per `hand_id`
- Join: seats 0,2 → `tricks_team0`, seats 1,3 → `tricks_team1`

**Approach:**
1. Join features + outcomes on `hand_id` to get per-seat `tricks_won`.
2. For each contract type (suit, high, low), compute `hand_value` →
   `mean(tricks_won)` empirically.
3. Set threshold for bid level N = the `hand_value` where
   `mean(tricks_won) ≈ N`. This produces a mapping grounded in actual
   trick-taking outcomes under Glutton play (the same play policy used in
   the comparator).
4. If the mapping doesn't cover all bid levels (e.g., no hands have
   `mean(tricks_won) ≈ 1`), that's fine — those thresholds just produce
   very low bids on very weak hands, which is the correct behavior.

**Why Glutton play is the right reference:** The comparator battery uses
Glutton (or Greedy) for all card play. Calibrating thresholds against tricks
won under the same play policy ensures the bid level approximates actual
expected tricks in the comparator context.

**Deliverable:** A small calibration script or notebook cell that reads the
bidless parquet, computes the threshold table, and outputs the values to
hard-code into `RanktheTank.choose_bid()`. The thresholds are static —
they don't need to be computed at runtime.

**Also fix:**
- HIGH/LOW mutual exclusion (line 368/383): evaluate BOTH and pick the
  higher-scoring contract, rather than choosing based on card count alone.
- Update `score_hand_scalar` docstring ("not used for bidding" is stale).

---

## Implementation Path

### Step 1: Fix ModeloEspecifico bid ceiling (Fix A above)

### Step 1b: Recalibrate RanktheTank thresholds (Fix C above)

### Step 2: Modify comparator runner

Add single-seat mode to `scripts/internal/run_auction_comparator.py` (or
create a new script). Key change in the simulation call:

- Instead of `bidding_policy=policy` (all 4 seats), pass
  `bidding_policies=[policy, None, None, None]` with a randomly selected
  seat, or add a new parameter to `simulate_many_hands`.
- Alternatively, call `play_single_hand` directly with a wrapper that
  assigns the policy to one random seat per deal and uses a pass-always
  policy for the other 3.

**Design decision needed:** How to handle the non-bidding seats. Options:
- A. Only 1 seat has the policy; other 3 always pass → the selected seat
  always wins the auction if it bids (true single-seat, simplest)
- B. Use `play_single_hand` with a custom "single evaluator" mode that
  bypasses the auction entirely → cleaner but requires simulation changes

Recommend Option A — minimal code change, same effect.

### Step 3: Re-run battery

```bash
# Re-run with single-seat mode (exact flag TBD)
PYTHONPATH=src uv run python scripts/internal/run_auction_comparator.py \
  --config experiments/configs/auction_comparator.yaml \
  --seed 42 --single-seat \
  --olsa-artifact data/artifacts/arc_d/r0/hybrid_r0.json \
  --bidder-class HybridOLSaBidder --bidder-name hybrid_olsa
```

Consider increasing deal count to 20k-50k to compensate for higher pass rates
(especially for hybrid_olsa).

### Step 4: Re-run extraction

```bash
PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
  --artifacts-dir data/artifacts/arc_d/r0 --runs-dir data/runs --seed 42 \
  --n-bootstrap 10000 --output data/artifacts/arc_d/r0/comparator_cis_r0_v3.json \
  --battery-file comparator_battery_r0_v3.json
```

Note: v3 to distinguish from v2 (current 7-bidder, 4-way auction).

### Step 5: Verify rankings

Compare v2 (4-way) and v3 (single-seat) rankings. Document any rank changes
and explain why they occurred. This crosswalk is optional but good practice.

### Step 6: Update downstream

- `docs/04_reports/r0/comparator_rankings.md` — new numbers + methodology
  (merge with Notes 1-10 report improvements)
- `docs/04_reports/r0/h2h_battery_analysis.md` §3 — update or cross-reference
- `docs/04_reports/r0/r0_promotion_report.md` — update comparator context
- `notebooks/arc_d/r0/40_r0_baseline.py` §11 — update comparator charts

---

## Decision: Dual-Mode with Single-Seat Primary (2026-02-26)

**Decided:** Make single-seat the canonical (primary) comparator methodology.
Retain the 4-way auction as a secondary diagnostic panel.

**Rationale:** Cost and churn are not constraints at R0 (zero backward-
compatibility cost, reports need updates anyway). The deciding criterion is
measurement validity: single-seat is the cleaner estimate of intrinsic bidding
quality per random hand.

**What you give up:** The primary metric no longer reflects behavior under
contested `current_high_bid` pressure.

**Mitigation:** Run one 4-way battery alongside as an explicit
"auction-pressure sensitivity" panel. This preserves the signal without
conflating it with the intrinsic measurement.

**Updated implementation path:**
1. Implement `--single-seat` mode in the comparator runner.
2. Re-run all 7 bidders at seed 42 / n=10,000 in single-seat mode and
   regenerate CIs → this becomes the **primary ranking**.
3. Also run one 4-way battery as a **sensitivity panel** (existing v2 data
   may suffice, or re-run for consistency).
4. Update the report so primary rankings are single-seat and 4-way is
   explicitly labeled "auction-pressure sensitivity."

---

## Open Questions for Reviewing Agent

1. **Deal count for single-seat mode.** 10k deals may produce too few
   bid-hands for selective bidders (hybrid_olsa). Should we increase to 20k
   or 50k? What's the minimum for stable CIs on CVaR-5%?

2. **Non-bidding seat handling.** Option A (3 seats always pass) vs Option B
   (bypass auction entirely). Is there a reason to prefer one over the other?

3. **v3 artifact naming.** The current battery is v2 (superseded v1's 5-bidder
   roster). Should the single-seat battery be v3, or a separate artifact name
   (e.g., `comparator_single_seat_r0.json`)?

---

## Key Files

| File | Role |
|------|------|
| `scripts/internal/run_auction_comparator.py` | Comparator orchestrator (modify) |
| `scripts/internal/extract_comparator_cis.py` | CI extraction (may need minor changes) |
| `src/bid_euchre/sim/simulation.py` | `play_single_hand` / `simulate_many_hands` |
| `src/bid_euchre/strategy/bidding.py` | `OLSaBidder`, `HybridOLSaBidder` |
| `src/bid_euchre/scoring.py` | `compute_points` (scoring formula) |
| `experiments/configs/auction_comparator.yaml` | Battery config |
| `docs/04_reports/r0/comparator_rankings.md` | Report (update with new data) |
