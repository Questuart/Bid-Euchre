# R1.5 Step 1 — Counterfactual Dataset Generator Session Plan

**Date:** 2026-03-06
**Task:** #2 — PR-2: R1.5 Step 1 counterfactual dataset generator
**Governs:** `scripts/internal/generate_action_value_dataset.py` + unit tests
**Design spec:** `plans/r1_5_training_plan.md` (Section 5, Step 1)

---

## Scope

One PR. Dataset generator script + unit tests for Gate X1 validation.

### Deliverables

| # | File | Change |
|---|------|--------|
| 1 | `scripts/internal/generate_action_value_dataset.py` | New: counterfactual dataset generator |
| 2 | `tests/unit/test_action_value_dataset.py` | New: unit tests for dataset generation |

### Not in scope

- Training pipeline (Step 2, separate PR)
- Modifications to `sim/simulation.py` or any frozen files
- ActionValueBidder changes (done in Step 0)
- YAML config changes

---

## Architecture

### Why not delegate to run_experiment.py?

The existing auction pipeline runs one auction per deal, producing 1 outcome per (deal, seat). The counterfactual generator needs to enumerate ALL legal actions for each focal seat, force each action, and play out the remainder — producing ~40 rows per (deal, seat). This requires direct access to sim primitives.

### Data flow

```
For each deal_id in range(n_deals):
  hands = generate_deal(seed, deal_id)
  dealer = generate_initial_leader(seed, deal_id)  # reuse as dealer derivation

  For each focal_seat (0..3):
    # Run partial auction up to focal_seat's turn
    partial_auction = run_auction_up_to(hands, dealer, focal_seat, continuation_policy)
    obs = build_observation(hands[focal_seat], focal_seat, dealer, partial_auction)
    legal = enumerate_legal_actions(obs)

    For each action in legal:
      # Force this action, continue auction, play tricks, score
      net_points = simulate_counterfactual(
          hands, dealer, focal_seat, action, partial_auction, continuation_policy
      )

      # Extract features
      state_feats = extract_state_features(obs, contract_family, trump_suit)

      # Write row
      row = {hand_id, deal_id, focal_seat, action_type, contract_family,
             bid_n, 52 state features, net_points}
```

### Key design decisions

1. **Partial auction:** Must simulate the auction up to the focal seat's turn (preceding seats bid using the continuation policy). This establishes `current_high_bid` and `auction_transcript` correctly.

2. **Continuation after forced action:** After forcing the focal seat's action, remaining seats continue bidding using the continuation policy. If all pass (including focal), it's a misdeal — record `net_points=0`.

3. **Trick play:** All 4 seats play with GluttonStrategy. The continuation policy is only for bidding.

4. **net_points calculation:** Use `compute_points(winning_bid, bidder_position, t0, t1)` then extract the focal team's points. `net_points = focal_team_points - opponent_team_points`.

5. **Dealer derivation:** Use `_deal_rng(seed, deal_id).randrange(4)` for deterministic dealer position (same formula as `generate_initial_leader`).

6. **Bidding order:** LOD (left of dealer) first: seats `(dealer+1)%4, (dealer+2)%4, (dealer+3)%4, dealer`. The focal seat is one of these 4 positions.

7. **Misdeal handling:** If no one bids (all pass), set `net_points=0` for all actions in that (deal, focal_seat). This is correct: passing in a dead auction has zero expected value.

### Functions

```python
def run_partial_auction(
    hands: list[list[Card]], dealer: int, focal_seat: int,
    continuation_policy: BiddingPolicy
) -> tuple[int, list[dict]]:
    """Run auction up to (but not including) focal_seat's turn.
    Returns (current_high_bid, transcript_so_far)."""

def simulate_counterfactual(
    hands: list[list[Card]], dealer: int, focal_seat: int,
    forced_action: BidAction, current_high_bid: int,
    transcript_so_far: list[dict],
    continuation_policy: BiddingPolicy,
) -> float:
    """Force focal_seat to take forced_action, continue auction + play tricks.
    Returns net_points for focal_seat's team."""

def generate_dataset(
    seed: int, n_deals: int, continuation_policy: BiddingPolicy,
    mode: str = "SMOKE",
) -> pd.DataFrame:
    """Generate the full counterfactual dataset."""
```

### CLI interface

```bash
uv run python scripts/internal/generate_action_value_dataset.py \
    --seed 42 \
    --n-deals 500 \
    --mode SMOKE \
    --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
    --output-dir data/runs/action_value_smoke_42
```

Modes: SMOKE=500 deals, QUICK=2500, FULL=50000

### Output schema (Parquet)

| Column | Type | Description |
|--------|------|-------------|
| hand_id | int | Unique per (deal, focal_seat) |
| deal_id | int | Deal index |
| focal_seat | int | 0-3 |
| action_type | str | "pass" or "bid" |
| contract_family | str | "suit", "high", "low", or "none" (for pass) |
| bid_n | int | 0 for pass, 1-10 for bids |
| trump_suit | str/None | Suit letter or None |
| {52 state feature columns} | float | Flattened from STATE_FEATURE_NAMES |
| net_points | float | Target variable |

---

## Gate X1 Validation

Built into the script and also tested in unit tests:

| Check | Criterion |
|-------|-----------|
| Row count | `n_deals * 4 * mean_actions` (+/- 10% of expected) |
| Contract families | All 3 bid families + pass present |
| Pass coverage | Exactly 1 pass row per (deal_id, focal_seat) |
| net_points range | All values in [-10, +10] |
| No NaN | No NaN in features or target |
| Feature count | 52 state feature columns present |

---

## Unit Tests

| Test | What it validates |
|------|-------------------|
| `test_run_partial_auction_first_seat` | First seat has empty transcript, high_bid=0 |
| `test_run_partial_auction_later_seat` | Later seats see prior bids in transcript |
| `test_simulate_counterfactual_pass` | Pass action produces plausible net_points |
| `test_simulate_counterfactual_bid` | Bid action produces plausible net_points |
| `test_simulate_counterfactual_misdeal` | All-pass → net_points=0 |
| `test_generate_dataset_smoke` | SMOKE generates correct row counts |
| `test_gate_x1_pass_coverage` | Exactly 1 pass per (deal, seat) |
| `test_gate_x1_no_nan` | No NaN in output |
| `test_gate_x1_net_points_range` | net_points in [-10, +10] |
| `test_determinism` | Same seed → identical dataset |

---

## Implementation Order

1. Helper functions: `run_partial_auction()`, `simulate_counterfactual()`
2. Main `generate_dataset()` function
3. Gate X1 validation function
4. CLI wrapper (`main()`)
5. Unit tests
6. `make check`

---

## Outcome

_To be filled after implementation._
