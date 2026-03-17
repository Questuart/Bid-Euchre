# R3 Inference Fix: Moon/Loner Enumeration + Bid-Type Faceted Reporting

**Date:** 2026-03-16
**Goal:** Fix bidders to enumerate moon/loner at inference time and add bid_type faceting to reporting tables so moon/loner behavior is visible in the standard pipeline.

## Problem

R3 QUICK results show inflated R² (0.899) but flat H2H/comparator vs R2. Root cause:
training data includes moon/loner counterfactuals, but `choose_bid()` calls
`enumerate_legal_actions(obs)` without `include_moon_loner=True`. Models never
actually bid moon/loner during games — the R3 result is invalid.

## Design Principle

**Backward compatible bid_type faceting.** All tables gain a `bid_type` column:
- R0-R2 data: every row is `bid_type: "regular"` (no behavioral change)
- R3 data: rows are `"regular"`, `"moon"`, or `"loner"` based on actual bids

Same schema everywhere. The pipeline doesn't need R3-specific code paths —
it just reports what the game logs contain.

## Plan

### PR 1: Inference Fix (bidding.py + simulation.py)

**Step 1a: Bidder moon/loner detection**

All 3 bidder classes (`ActionValueBidder`, `GBTActionValueBidder`,
`TwoStageActionValueBidder`) in `src/bid_euchre/strategy/bidding.py`.

Each bidder's `__init__()` already detects artifact feature layout
(e.g., `_needs_full_state`). Add `_has_moon_loner` detection:
- Check if artifact metadata contains `is_moon` in its feature list
- Or check if `ACTION_FEATURE_NAMES` (4 features) vs `ACTION_FEATURE_NAMES_BASE` (2)

**Step 1b: Pass flag to enumerate_legal_actions**

In each bidder's `choose_bid()` method (~lines 2285, 2473, 2675):
```python
# Before:
legal = enumerate_legal_actions(obs)
# After:
legal = enumerate_legal_actions(obs, include_moon_loner=self._has_moon_loner)
```

**Step 1c: Simulation auction must accept moon/loner bids**

Verify `play_single_hand()` in `src/bid_euchre/sim/simulation.py` handles
moon/loner bids returned by policies. PR #717 added the overcall hierarchy
and PR #721/723/725 added exchange/loner/scoring. But check that the
`BiddingPolicy` path (not just `seat_bidding_policies`) correctly processes
moon/loner `BidAction` objects through the full auction→exchange→trick→score flow.

**Files:**
- `src/bid_euchre/strategy/bidding.py` — `_has_moon_loner` + choose_bid changes
- `src/bid_euchre/sim/simulation.py` — verify moon/loner flow (may need no changes)

**Tests:**
- `tests/unit/test_action_value_bidder.py` — bidder with moon/loner artifact enumerates moon/loner
- `tests/unit/test_action_value_bidder.py` — bidder without moon/loner artifact does NOT enumerate
- `tests/integration/test_r3_smoke.py` — end-to-end: model trained on moon/loner data actually bids moon/loner

### PR 2: Bid-Type Faceted Reporting

**Step 2a: Game logger already writes bid_type (schema v8)**

Verify `log_hand_end()` writes `bid_type` field. This was done in PR #725.
No changes needed to logging.

**Step 2b: Comparator extraction — facet by bid_type**

`scripts/internal/extract_comparator_cis.py` reads JSONL and computes
bootstrap CIs. Add bid_type grouping:
- Group deals by `bid_type` (regular/moon/loner)
- Compute per-bid_type stats: net_eppd, bid_rate, make_rate, CVaR
- Also compute pooled (all bid_types combined) for backward compat
- Output format: existing columns + `bid_type` column (like `facet` for contract type)

**Step 2c: H2H battery — facet by bid_type**

`scripts/internal/run_arc_d_h2h_battery.py` `parse_run_results()` already
facets by contract type (suit/high/low/pooled). Add bid_type faceting:
- For each matchup cell, also group by bid_type
- Output: `by_bid_type` dict alongside existing `by_contract`

**Step 2d: Table generation — emit bid_type rows**

`src/bid_euchre/arc_d_v2/tables.py` generates CSV tables from battery JSON.
- `generate_comparator_rankings()` — add rows for each bid_type
- `generate_h2h_delta_matrix()` — add rows for each bid_type
- `generate_behavior_summary()` / `generate_behavior_by_contract()` — add bid_type breakdowns

**Step 2e: Behavior by bid_type table (new)**

New table: `behavior_by_bid_type.csv`
- Columns: model, bid_type, count, bid_rate, make_rate, mean_net_points
- Shows how often each model bids moon/loner, and their success rate
- For R0-R2: only "regular" rows (100% bid rate for that type)
- For R3: "regular", "moon", "loner" rows with actual frequencies

**Files:**
- `scripts/internal/extract_comparator_cis.py` — bid_type grouping
- `scripts/internal/run_arc_d_h2h_battery.py` — bid_type in parse_run_results
- `src/bid_euchre/arc_d_v2/tables.py` — bid_type rows in generated tables

**Tests:**
- Table generation with R0-style data produces only "regular" bid_type rows
- Table generation with R3-style data produces regular + moon + loner rows
- behavior_by_bid_type.csv has expected schema

### Rerun R3 QUICK

After both PRs merge:
```bash
uv run python scripts/internal/run_rung.py --rung r3 --mode quick --seed 42
```

The orchestrator's state.json will detect mode transition and reset stale completions.

**Expected behavioral changes:**
- GBT should bid moon/loner when EV is favorable
- R² may drop from 0.899 (inflated) to a more realistic level
- H2H delta should change (up or down depending on moon/loner quality)
- behavior_by_bid_type.csv will show actual moon/loner frequencies

## Review Findings (incorporated)

### Critical (from plan review 2026-03-16):

1. **Action feature size mismatch:** `extract_action_features()` (line 1749) always returns
   4 features after PR #729. R0-R2 models have coefficients for only 2. The `_has_moon_loner`
   flag must ALSO control action feature vector size — either parameterize
   `extract_action_features(bid_type, n_action=2)` or truncate to first 2 features for
   models without moon/loner. Without this, R0-R2 inference crashes in `predict_ols()`.

2. **Scoring in extract_comparator_cis.py:** Line 79 calls `compute_points()` without
   `bid_type`. Must pass `bid_type=record.get("bid_type", "regular")`.

3. **Scoring in run_arc_d_h2h_battery.py:** `_compute_team_points()` (line 443) uses
   inline scoring that ignores moon/loner multipliers. Must call `compute_points()` with
   `bid_type` or add moon/loner handling.

4. **_has_moon_loner detection scope:** Must be computed UNCONDITIONALLY in `__init__`,
   not inside the `if not self._has_positional` branch. R3 models have positional=True.

5. **CLI typo:** `run_rung.py` expects `--seeds` (plural), not `--seed`.

## Success Criteria

- Models with moon/loner artifacts enumerate and bid moon/loner at inference
- Models without moon/loner artifacts behave identically to before (R0-R2 compat)
- All reporting tables include bid_type faceting
- R0-R2 tables show only "regular" rows
- R3 tables show regular + moon + loner breakdowns
- `make check-quiet` passes

## Outcome
<!-- Filled after implementation -->
- PR: #NNN / abandoned / deferred
- Notes: any deviations from plan
