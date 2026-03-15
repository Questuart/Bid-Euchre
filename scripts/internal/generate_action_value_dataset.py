#!/usr/bin/env python
"""
Generate counterfactual action-value dataset for R1.5 training.

For each (deal, focal_seat): enumerate all legal actions, force each one,
continue the auction with a continuation policy, play out tricks with
GluttonStrategy, and record the focal team's net_points.

Output: Parquet with columns hand_id, deal_id, focal_seat, action_type,
contract_family, bid_n, trump_suit, 57 state feature columns, net_points,
tricks_won, focal_declared.

Usage:
    uv run python scripts/internal/generate_action_value_dataset.py \
        --seed 42 --n-deals 500 --mode SMOKE \
        --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
        --output-dir data/runs/action_value_smoke_42
"""

import argparse
import random
import sys
import time
from pathlib import Path

import pandas as pd

from bid_euchre.scoring import compute_points
from bid_euchre.sim.deals import generate_deal
from bid_euchre.strategy import GluttonStrategy
from bid_euchre.strategy.bidding import (
    STATE_FEATURE_NAMES,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
    enumerate_legal_actions,
    extract_state_features,
)

# Mode → n_deals mapping (override with --n-deals)
MODE_DEALS = {"SMOKE": 500, "QUICK": 2500, "FULL": 50000}


def sample_opponent_hands(
    focal_seat: int,
    hands: list,
    n_samples: int,
    rng: random.Random,
) -> list[list[list]]:
    """Sample opponent hand configurations, keeping focal + partner hands fixed.

    For each sample, the 20 opponent cards (from the two non-partner seats) are
    reshuffled into 2 hands of 10. The focal player's hand and partner's hand
    are unchanged across all samples.

    **Known limitation:** Resampling is NOT conditioned on the partial auction
    transcript. Resampled opponent hands may be inconsistent with the bids those
    opponents actually made — e.g., an opponent who bid 6H likely holds strong
    hearts, but a resample might give them a weak hand. The counterfactual
    rollout then reuses the original auction state (current_high_bid, transcript),
    creating a mismatch between the dealt hands and the observed bidding history.

    This is an intentional simplification for R1.5.3 Phase 0. Auction-conditioned
    sampling would require opponent belief models, which is out of scope until
    R2 (opponent context). The multi-rollout averaging mitigates (but does not
    eliminate) the noise from inconsistent samples.

    Args:
        focal_seat: The focal player's seat (0-3).
        hands: Original 4 hands [seat0, seat1, seat2, seat3].
        n_samples: Number of opponent configurations to generate.
        rng: Seeded RNG for deterministic shuffling.

    Returns:
        List of n_samples hand configurations, each a list of 4 hands.
    """
    partner_seat = (focal_seat + 2) % 4
    opp_seats = sorted(s for s in range(4) if s != focal_seat and s != partner_seat)

    # Pool all opponent cards (20 cards from 2 opponents)
    opp_pool = list(hands[opp_seats[0]]) + list(hands[opp_seats[1]])

    configs = []
    for _ in range(n_samples):
        shuffled = list(opp_pool)
        rng.shuffle(shuffled)
        new_hands = [None, None, None, None]
        new_hands[focal_seat] = list(hands[focal_seat])
        new_hands[partner_seat] = list(hands[partner_seat])
        new_hands[opp_seats[0]] = shuffled[:10]
        new_hands[opp_seats[1]] = shuffled[10:]
        configs.append(new_hands)

    return configs


def _deterministic_dealer(seed: int, deal_id: int) -> int:
    """Derive a deterministic dealer position for (seed, deal_id).

    Uses the SAME formula as play_single_hand() in auction mode with deal_seed:
        dealer_rng = random.Random(deal_seed + deal_id)
        dealer_index = dealer_rng.randrange(4)

    This is intentionally different from sim.deals._deal_rng (which uses
    seed * 1_000_003 + deal_id for card shuffles). The engine derives
    dealers separately from deals.
    """
    return random.Random(seed + deal_id).randrange(4)


def _bidding_order(dealer: int) -> list[int]:
    """Return the 4 seats in auction order (LOD first, dealer last)."""
    return [(dealer + offset) % 4 for offset in range(1, 5)]


def run_partial_auction(
    hands: list,
    dealer: int,
    focal_seat: int,
    continuation_policy: BiddingPolicy,
) -> tuple[int, list[dict]]:
    """Run auction up to (but not including) focal_seat's turn.

    Returns:
        (current_high_bid, transcript_so_far)
    """
    current_high_bid = 0
    transcript: list[dict] = []

    for seat in _bidding_order(dealer):
        if seat == focal_seat:
            break  # Stop before focal seat bids

        obs = BiddingObservation(
            hand=hands[seat],
            seat=seat,
            dealer_seat=dealer,
            current_high_bid=current_high_bid,
            auction_transcript=tuple(dict(e) for e in transcript),
        )

        bid_action = continuation_policy.choose_bid(obs)

        # Process action
        is_effective_pass = bid_action.is_pass() or bid_action.n <= current_high_bid
        if is_effective_pass:
            transcript.append(
                {
                    "seat": seat,
                    "action": "PASS",
                    "tricks_bid": 0,
                    "contract_type": None,
                    "trump": None,
                }
            )
        else:
            ctype, trump = bid_action.to_contract_tuple()
            transcript.append(
                {
                    "seat": seat,
                    "action": "BID",
                    "tricks_bid": bid_action.n,
                    "contract_type": ctype,
                    "trump": trump,
                }
            )
            current_high_bid = bid_action.n

    return current_high_bid, transcript


def _complete_auction(
    hands: list,
    dealer: int,
    focal_seat: int,
    forced_action: BidAction,
    current_high_bid: int,
    transcript_so_far: list[dict],
    continuation_policy: BiddingPolicy,
) -> tuple[int | None, int | None, str | None, str | None, list[dict]]:
    """Complete the auction after forcing focal_seat's action.

    Returns:
        (winning_bid, bidder_position, contract_type, trump_suit, full_transcript)
    """
    transcript = [dict(e) for e in transcript_so_far]

    # Apply forced action
    is_effective_pass = forced_action.is_pass() or forced_action.n <= current_high_bid
    if is_effective_pass:
        transcript.append(
            {
                "seat": focal_seat,
                "action": "PASS",
                "tricks_bid": 0,
                "contract_type": None,
                "trump": None,
            }
        )
    else:
        ctype, trump = forced_action.to_contract_tuple()
        transcript.append(
            {
                "seat": focal_seat,
                "action": "BID",
                "tricks_bid": forced_action.n,
                "contract_type": ctype,
                "trump": trump,
            }
        )
        current_high_bid = forced_action.n

    # Track winning bidder across entire auction
    winning_bidder = None
    winning_contract = None
    winning_trump = None
    for entry in transcript:
        if entry["action"] == "BID":
            winning_bidder = entry["seat"]
            winning_contract = entry["contract_type"]
            winning_trump = entry["trump"]

    # Continue auction for seats after focal
    order = _bidding_order(dealer)
    focal_idx = order.index(focal_seat)
    remaining = order[focal_idx + 1 :]

    for seat in remaining:
        obs = BiddingObservation(
            hand=hands[seat],
            seat=seat,
            dealer_seat=dealer,
            current_high_bid=current_high_bid,
            auction_transcript=tuple(dict(e) for e in transcript),
        )

        bid_action = continuation_policy.choose_bid(obs)

        is_effective_pass = bid_action.is_pass() or bid_action.n <= current_high_bid
        if is_effective_pass:
            transcript.append(
                {
                    "seat": seat,
                    "action": "PASS",
                    "tricks_bid": 0,
                    "contract_type": None,
                    "trump": None,
                }
            )
        else:
            ctype, trump = bid_action.to_contract_tuple()
            transcript.append(
                {
                    "seat": seat,
                    "action": "BID",
                    "tricks_bid": bid_action.n,
                    "contract_type": ctype,
                    "trump": trump,
                }
            )
            current_high_bid = bid_action.n
            winning_bidder = seat
            winning_contract = ctype
            winning_trump = trump

    if winning_bidder is None:
        # All passed — misdeal
        return None, None, None, None, transcript

    return (
        current_high_bid,
        winning_bidder,
        winning_contract,
        winning_trump,
        transcript,
    )


def _play_tricks(
    hands: list,
    initial_leader: int,
    contract_type: str,
    trump_suit: str | None,
) -> tuple[int, int]:
    """Play out 10 tricks with GluttonStrategy, matching the engine lifecycle.

    Calls on_hand_start() and observe_play() to ensure the strategy has
    correct contract state and card tracking (void inference, seen counts).
    Returns (t0, t1).
    """
    from bid_euchre.core.rules import get_legal_indices, trick_winner

    # Deep copy hands since play_tricks mutates them
    play_hands = [list(h) for h in hands]
    strategy = GluttonStrategy()

    # Call on_hand_start() — GluttonStrategy uses this to reset _seen_counts,
    # _void_suits_by_seat, and set _contract_type / _trump_suit.
    # The engine calls it once per unique strategy instance; we have one.
    strategy.on_hand_start(
        starting_hand=list(play_hands[initial_leader]),
        contract_type=contract_type,
        trump_suit=trump_suit,
        player_index=initial_leader,
    )

    team_tricks = {0: 0, 1: 0}
    leader = initial_leader

    for _trick_num in range(10):
        plays = []
        for offset in range(4):
            player = (leader + offset) % 4
            hand = play_hands[player]

            legal_indices = get_legal_indices(hand, plays, contract_type, trump_suit)
            card_index = strategy.choose_card(
                hand=hand,
                plays_so_far=plays,
                contract_type=contract_type,
                trump_suit=trump_suit,
                player_index=player,
            )
            if card_index not in legal_indices:
                card_index = legal_indices[0]

            card = hand.pop(card_index)
            plays.append((player, card))

            # Call observe_play() — tracks seen cards and infers voids
            strategy.observe_play(
                player_index=player,
                card=card,
                trick_plays=list(plays),
                contract_type=contract_type,
                trump_suit=trump_suit,
            )

        winner = trick_winner(plays, contract_type=contract_type, trump_suit=trump_suit)
        if winner in (0, 2):
            team_tricks[0] += 1
        else:
            team_tricks[1] += 1
        leader = winner

    return team_tricks[0], team_tricks[1]


def simulate_counterfactual(
    hands: list,
    dealer: int,
    focal_seat: int,
    forced_action: BidAction,
    current_high_bid: int,
    transcript_so_far: list[dict],
    continuation_policy: BiddingPolicy,
) -> tuple[float, float, bool]:
    """Force focal_seat to take forced_action, complete auction + play tricks.

    Returns:
        (net_points, tricks_won, focal_declared) where:
        - net_points: focal team's net points (focal - opponent)
        - tricks_won: focal team's raw tricks won
        - focal_declared: True if focal_seat's team won the auction

    Misdeal (all pass) returns (0.0, 0.0, False).
    """
    winning_bid, bidder_pos, contract_type, trump_suit, _transcript = _complete_auction(
        hands,
        dealer,
        focal_seat,
        forced_action,
        current_high_bid,
        transcript_so_far,
        continuation_policy,
    )

    if winning_bid is None:
        # Misdeal: all passed
        return 0.0, 0.0, False

    # Determine if focal team declared
    focal_declared = (bidder_pos is not None) and (bidder_pos % 2 == focal_seat % 2)

    # Play tricks (auction winner leads)
    t0, t1 = _play_tricks(hands, bidder_pos, contract_type, trump_suit)

    # Focal team's tricks won
    tricks_won = float(t0) if focal_seat in (0, 2) else float(t1)

    # Compute points
    points_t0, points_t1 = compute_points(winning_bid, bidder_pos, t0, t1)

    # net_points for focal_seat's team
    if focal_seat in (0, 2):
        net_points = float(points_t0 - points_t1)
    else:
        net_points = float(points_t1 - points_t0)

    return net_points, tricks_won, focal_declared


def generate_dataset(
    seed: int,
    n_deals: int,
    continuation_policy: BiddingPolicy,
    progress: bool = True,
    n_opponent_samples: int = 1,
) -> pd.DataFrame:
    """Generate the full counterfactual action-value dataset.

    For each (deal, focal_seat), enumerates all legal actions, forces each one,
    and records the resulting net_points.

    When n_opponent_samples > 1, opponent hands are resampled while keeping
    focal + partner hands fixed.  Labels become the mean across samples.
    Metadata columns ``std_net_points`` and ``n_samples`` are added.
    """
    rows: list[dict] = []
    hand_id = 0
    t0 = time.time()
    multi = n_opponent_samples > 1

    for deal_id in range(n_deals):
        hands = generate_deal(seed, deal_id)
        dealer = _deterministic_dealer(seed, deal_id)

        for focal_seat in range(4):
            # Run partial auction up to focal_seat (uses ORIGINAL hands
            # so that features reflect the actual deal configuration)
            current_high_bid, transcript = run_partial_auction(
                hands, dealer, focal_seat, continuation_policy
            )

            # Build observation for focal_seat
            obs = BiddingObservation(
                hand=hands[focal_seat],
                seat=focal_seat,
                dealer_seat=dealer,
                current_high_bid=current_high_bid,
                auction_transcript=tuple(dict(e) for e in transcript),
            )

            # Enumerate legal actions
            legal = enumerate_legal_actions(obs)

            # Pre-generate opponent configurations if multi-sample
            if multi:
                sample_rng = random.Random(seed + deal_id * 10000 + focal_seat)
                opp_configs = sample_opponent_hands(
                    focal_seat, hands, n_opponent_samples, sample_rng
                )

            for action in legal:
                # Determine contract family and trump for feature extraction
                if action.is_pass():
                    contract_family = "none"
                    trump_suit = None
                    action_type = "pass"
                    bid_n = 0
                else:
                    ctype, trump_suit = action.to_contract_tuple()
                    contract_family = ctype
                    action_type = "bid"
                    bid_n = action.n

                # Extract state features (57 columns) — from ORIGINAL hands
                state = extract_state_features(obs, contract_family, trump_suit)

                if multi:
                    # Multi-sample: run counterfactual on each opponent config
                    np_vals = []
                    tw_vals = []
                    fd_vals = []
                    for config_hands in opp_configs:
                        np_i, tw_i, fd_i = simulate_counterfactual(
                            config_hands,
                            dealer,
                            focal_seat,
                            action,
                            current_high_bid,
                            transcript,
                            continuation_policy,
                        )
                        np_vals.append(np_i)
                        tw_vals.append(tw_i)
                        fd_vals.append(fd_i)

                    net_points = sum(np_vals) / len(np_vals)
                    tricks_won = sum(tw_vals) / len(tw_vals)
                    focal_declared = sum(fd_vals) / len(fd_vals) > 0.5

                    # Variance metadata
                    mean_np = net_points
                    std_np = (
                        sum((x - mean_np) ** 2 for x in np_vals) / len(np_vals)
                    ) ** 0.5
                else:
                    # Single-sample: existing behavior
                    net_points, tricks_won, focal_declared = simulate_counterfactual(
                        hands,
                        dealer,
                        focal_seat,
                        action,
                        current_high_bid,
                        transcript,
                        continuation_policy,
                    )

                # Build row
                row = {
                    "hand_id": hand_id,
                    "deal_id": deal_id,
                    "focal_seat": focal_seat,
                    "action_type": action_type,
                    "contract_family": contract_family,
                    "bid_n": bid_n,
                    "trump_suit": trump_suit if trump_suit else "",
                }
                # Add 57 state features as individual columns
                for i, fname in enumerate(STATE_FEATURE_NAMES):
                    row[fname] = state[i]
                row["net_points"] = net_points
                row["tricks_won"] = tricks_won
                row["focal_declared"] = focal_declared

                if multi:
                    row["std_net_points"] = std_np
                    row["n_samples"] = n_opponent_samples

                rows.append(row)

            hand_id += 1

        if progress and (deal_id + 1) % max(1, n_deals // 10) == 0:
            elapsed = time.time() - t0
            rate = (deal_id + 1) / elapsed
            print(
                f"  [{deal_id + 1}/{n_deals}] {len(rows)} rows, "
                f"{rate:.1f} deals/s, {elapsed:.1f}s elapsed",
                file=sys.stderr,
            )

    return pd.DataFrame(rows)


def validate_gate_x1(df: pd.DataFrame, n_deals: int) -> None:
    """Run Gate X1 validation checks on the dataset.

    Raises AssertionError on failure.
    """
    # 1. Pass coverage: exactly 1 pass per (deal_id, focal_seat)
    pass_df = df[df["action_type"] == "pass"]
    pass_counts = pass_df.groupby(["deal_id", "focal_seat"]).size()
    assert (pass_counts == 1).all(), (
        f"Expected exactly 1 pass per (deal, seat), got: "
        f"{pass_counts.value_counts().to_dict()}"
    )
    assert (
        len(pass_counts) == n_deals * 4
    ), f"Expected {n_deals * 4} (deal, seat) pairs with pass, got {len(pass_counts)}"

    # 2. All contract families represented
    families = set(df["contract_family"].unique())
    expected_families = {"none", "suit", "high", "low"}
    missing = expected_families - families
    assert not missing, f"Missing contract families: {missing}"

    # 3. net_points range is plausible
    min_np = df["net_points"].min()
    max_np = df["net_points"].max()
    assert min_np >= -20, f"net_points min too low: {min_np}"
    assert max_np <= 20, f"net_points max too high: {max_np}"

    # 4. No NaN in features or target
    feature_cols = STATE_FEATURE_NAMES + ["net_points", "tricks_won"]
    nan_counts = df[feature_cols].isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    assert len(nan_cols) == 0, f"NaN found in columns: {nan_cols.to_dict()}"

    # 4b. tricks_won range check
    assert df["tricks_won"].between(0, 10).all(), (
        f"tricks_won outside [0, 10]: "
        f"min={df['tricks_won'].min()}, max={df['tricks_won'].max()}"
    )

    # 4c. focal_declared is boolean-like
    focal_vals = set(df["focal_declared"].unique())
    assert focal_vals.issubset(
        {True, False, 0, 1}
    ), f"focal_declared has unexpected values: {focal_vals}"

    # 5. Row count sanity (expect ~40 actions per seat on average)
    expected_rows = n_deals * 4 * 40  # rough estimate
    actual_rows = len(df)
    ratio = actual_rows / expected_rows
    assert 0.5 <= ratio <= 1.5, (
        f"Row count {actual_rows} is outside expected range "
        f"({expected_rows * 0.5:.0f} - {expected_rows * 1.5:.0f})"
    )

    # 6. 57 state feature columns present
    for fname in STATE_FEATURE_NAMES:
        assert fname in df.columns, f"Missing state feature column: {fname}"

    avg_actions = actual_rows / (n_deals * 4)
    print(
        f"  Gate X1 PASS: {actual_rows} rows, {n_deals * 4} hands, "
        f"{avg_actions:.1f} avg actions/seat"
    )


def load_continuation_policy(artifact_path: str) -> BiddingPolicy:
    """Load a bidding policy to use as the continuation policy."""
    from bid_euchre.strategy.bidding import HybridOLSaBidder

    return HybridOLSaBidder(artifact_path=artifact_path, name="continuation")


def main():
    parser = argparse.ArgumentParser(
        description="Generate counterfactual action-value dataset for R1.5"
    )
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--n-deals",
        type=int,
        default=None,
        help="Number of deals (overrides --mode default)",
    )
    parser.add_argument(
        "--mode",
        default="SMOKE",
        choices=["SMOKE", "QUICK", "FULL"],
        help="Dataset scale (default: SMOKE)",
    )
    parser.add_argument(
        "--continuation-artifact",
        required=True,
        help="Path to bidder artifact for continuation policy",
    )
    parser.add_argument(
        "--output-dir", required=True, help="Output directory for dataset"
    )
    parser.add_argument(
        "--n-opponent-samples",
        type=int,
        default=1,
        help="Number of opponent hand resamples per action (default 1 = original behavior)",
    )
    parser.add_argument(
        "--skip-validation", action="store_true", help="Skip Gate X1 validation"
    )
    args = parser.parse_args()

    n_deals = args.n_deals if args.n_deals is not None else MODE_DEALS[args.mode]
    n_opp = args.n_opponent_samples

    print("=== R1.5 Counterfactual Action-Value Dataset Generator ===")
    print(f"  Seed: {args.seed}")
    print(f"  Mode: {args.mode} ({n_deals} deals)")
    print(f"  Opponent samples: {n_opp}")
    print(f"  Continuation: {args.continuation_artifact}")

    # Load continuation policy
    print("  Loading continuation policy...")
    continuation = load_continuation_policy(args.continuation_artifact)

    # Generate dataset
    sim_equiv = n_deals * n_opp
    print(
        f"  Generating dataset ({n_deals} deals × 4 seats × ~40 actions × {n_opp} samples)..."
    )
    print(f"  Simulation equivalents: ~{sim_equiv * 4 * 40:,}")
    df = generate_dataset(
        args.seed,
        n_deals,
        continuation,
        n_opponent_samples=n_opp,
    )

    print(f"  Total rows: {len(df)}")
    print(f"  Columns: {len(df.columns)}")

    # Validate
    if not args.skip_validation:
        print("  Running Gate X1 validation...")
        validate_gate_x1(df, n_deals)

    # Write output
    output_dir = Path(args.output_dir)
    datasets_dir = output_dir / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    output_path = datasets_dir / "action_value.parquet"
    df.to_parquet(output_path, index=False)

    print(f"\n  Output: {output_path}")
    print(f"  Rows: {len(df)}")
    print(f"  Deals: {n_deals}")
    print("  Done.")


if __name__ == "__main__":
    main()
