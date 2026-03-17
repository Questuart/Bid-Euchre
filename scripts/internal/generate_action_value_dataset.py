#!/usr/bin/env python
"""
Generate counterfactual action-value dataset for R1.5 training.

For each (deal, focal_seat): enumerate all legal actions, force each one,
continue the auction with a continuation policy, play out tricks with
GluttonStrategy, and record the focal team's net_points.

Output: Parquet with columns hand_id, deal_id, focal_seat, action_type,
contract_family, bid_n, trump_suit, is_moon, is_loner, 69 state feature
columns, net_points, tricks_won, focal_declared.

Usage:
    uv run python scripts/internal/generate_action_value_dataset.py \
        --seed 42 --n-deals 500 --mode SMOKE \
        --continuation-artifact data/artifacts/arc_d/r0/hybrid_r0_full.json \
        --output-dir data/runs/action_value_smoke_42
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from bid_euchre.scoring import compute_points
from bid_euchre.sim.deals import generate_deal
from bid_euchre.sim.exchange import perform_exchange
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
MODE_DEALS = {"SMOKE": 25, "QUICK": 5000, "FULL": 50000}


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


def _play_tricks_loner(
    hands: list,
    initial_leader: int,
    sitting_out_seat: int,
    contract_type: str,
    trump_suit: str | None,
) -> tuple[int, int]:
    """Play out 10 tricks with 3 players (loner: partner sits out).

    Matches the engine's 3-player trick play logic from simulation.py.
    The sitting_out_seat is skipped in play order but tricks are still
    attributed to teams (0,2) vs (1,3).

    Returns (t0, t1).
    """
    from bid_euchre.core.rules import get_legal_indices, trick_winner

    play_hands = [list(h) for h in hands]
    strategy = GluttonStrategy()

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

        # Build 3-player play order, skipping sitting_out_seat
        play_order = []
        p = leader
        for _ in range(3):
            while p == sitting_out_seat:
                p = (p + 1) % 4
            play_order.append(p)
            p = (p + 1) % 4

        for player in play_order:
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


def simulate_moon_counterfactual(
    hands: list,
    focal_seat: int,
    contract_type: str,
    trump_suit: str | None,
) -> tuple[float, float]:
    """Simulate a moon bid: exchange cards with partner, play 4-player tricks.

    Moon scoring: +20 if declaring team wins all 10 tricks, -20 otherwise.
    Defending team gets their tricks won.

    Returns:
        (net_points, tricks_won) for focal team.
    """
    partner_seat = (focal_seat + 2) % 4

    # Perform card exchange: mooner gives 2 worst, gets partner's 2 best
    mooner_hand, partner_hand, _, _ = perform_exchange(
        list(hands[focal_seat]),
        list(hands[partner_seat]),
        contract_type,
        trump_suit,
    )

    # Build hands with exchanged cards
    exchanged_hands = [list(h) for h in hands]
    exchanged_hands[focal_seat] = mooner_hand
    exchanged_hands[partner_seat] = partner_hand

    # Play tricks with mooner leading (auction winner leads)
    t0, t1 = _play_tricks(exchanged_hands, focal_seat, contract_type, trump_suit)

    # Compute points with moon scoring
    # focal_seat is the bidder
    points_t0, points_t1 = compute_points(
        winning_bid=10,
        bidder_position=focal_seat,
        tricks_team0=t0,
        tricks_team1=t1,
        bid_type="moon",
    )

    tricks_won = float(t0) if focal_seat in (0, 2) else float(t1)

    if focal_seat in (0, 2):
        net_points = float(points_t0 - points_t1)
    else:
        net_points = float(points_t1 - points_t0)

    return net_points, tricks_won


def simulate_loner_counterfactual(
    hands: list,
    focal_seat: int,
    contract_type: str,
    trump_suit: str | None,
) -> tuple[float, float]:
    """Simulate a loner bid: 3-player trick play (partner sits out).

    Loner scoring: +40 if declaring team wins all 10 tricks, -40 otherwise.
    Defending team gets their tricks won.

    Returns:
        (net_points, tricks_won) for focal team.
    """
    partner_seat = (focal_seat + 2) % 4

    # Play tricks with 3 players (partner sits out), mooner leads
    t0, t1 = _play_tricks_loner(
        hands,
        focal_seat,
        sitting_out_seat=partner_seat,
        contract_type=contract_type,
        trump_suit=trump_suit,
    )

    # Compute points with loner scoring
    points_t0, points_t1 = compute_points(
        winning_bid=10,
        bidder_position=focal_seat,
        tricks_team0=t0,
        tricks_team1=t1,
        bid_type="loner",
    )

    tricks_won = float(t0) if focal_seat in (0, 2) else float(t1)

    if focal_seat in (0, 2):
        net_points = float(points_t0 - points_t1)
    else:
        net_points = float(points_t1 - points_t0)

    return net_points, tricks_won


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


def _load_completed_chunks(manifest_path: Path) -> set[tuple[int, int]]:
    """Read manifest.jsonl, return set of (deal_start, deal_end) for completed chunks."""
    completed: set[tuple[int, int]] = set()
    if manifest_path.exists():
        with open(manifest_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("status") == "complete":
                    completed.add((entry["deal_start"], entry["deal_end"]))
    return completed


def _write_chunk(
    rows: list[dict],
    output_dir: Path,
    deal_start: int,
    deal_end: int,
    seed: int,
    started_at: str,
) -> None:
    """Write a chunk of rows as a parquet part file and append to manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    part_name = f"part_{deal_start:06d}_{deal_end:06d}.parquet"
    part_path = output_dir / part_name

    df = pd.DataFrame(rows)
    df.to_parquet(part_path, index=False)

    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    finished_dt = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
    duration_sec = (finished_dt - started_dt).total_seconds()

    manifest_entry = {
        "seed": seed,
        "deal_start": deal_start,
        "deal_end": deal_end,
        "n_deals": deal_end - deal_start + 1,
        "rows": len(rows),
        "path": part_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_sec": round(duration_sec, 1),
        "status": "complete",
    }

    manifest_path = output_dir / "manifest.jsonl"
    with open(manifest_path, "a") as f:
        f.write(json.dumps(manifest_entry) + "\n")


def generate_dataset(
    seed: int,
    n_deals: int,
    continuation_policy: BiddingPolicy,
    progress: bool = True,
    n_opponent_samples: int = 1,
    include_moon_loner: bool = False,
    chunk_size: int | None = None,
    output_dir: Path | None = None,
    dataset_seed: int | None = None,
) -> pd.DataFrame | None:
    """Generate the full counterfactual action-value dataset.

    For each (deal, focal_seat), enumerates all legal actions, forces each one,
    and records the resulting net_points.

    When n_opponent_samples > 1, opponent hands are resampled while keeping
    focal + partner hands fixed.  Labels become the mean across samples.
    Metadata columns ``std_net_points`` and ``n_samples`` are added.

    When include_moon_loner=True, moon and loner counterfactuals are appended
    for each (deal, focal_seat) after the regular actions. Moon bids simulate
    card exchange followed by 4-player trick play; loner bids simulate 3-player
    trick play (partner sits out). Both use specialized scoring (+/-20 for moon,
    +/-40 for loner). Action features is_moon and is_loner are set accordingly.

    When chunk_size is set and output_dir is provided, rows are flushed to
    parquet part files every chunk_size deals. Returns None (data is on disk).
    When chunk_size is None, returns the full DataFrame (existing behavior).
    """
    chunked = chunk_size is not None and output_dir is not None
    completed_chunks: set[tuple[int, int]] = set()
    if chunked:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = output_dir / "manifest.jsonl"
        completed_chunks = _load_completed_chunks(manifest_path)

    # Dataset seed for global UIDs (defaults to simulation seed)
    ds_seed = dataset_seed if dataset_seed is not None else seed

    rows: list[dict] = []
    t0 = time.time()
    multi = n_opponent_samples > 1
    total_rows_written = 0

    # Track chunk boundaries for chunked mode
    chunk_deal_start = 0

    # Contracts to evaluate for moon/loner: all 6 contract types
    contracts = [
        ("C", "suit", "C"),
        ("D", "suit", "D"),
        ("H", "suit", "H"),
        ("S", "suit", "S"),
        ("HIGH", "high", None),
        ("LOW", "low", None),
    ]

    chunk_started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for deal_id in range(n_deals):
        # Determine current chunk boundaries
        if chunked:
            current_chunk_start = (deal_id // chunk_size) * chunk_size
            current_chunk_end = min(current_chunk_start + chunk_size, n_deals) - 1

            # Check if this is the start of a new chunk
            if deal_id == current_chunk_start:
                chunk_deal_start = current_chunk_start
                chunk_started_at = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )

            # Skip if this chunk is already complete (resumability)
            if (current_chunk_start, current_chunk_end) in completed_chunks:
                if deal_id == current_chunk_end:
                    if progress:
                        print(
                            f"  [skip] Chunk deals {current_chunk_start}-"
                            f"{current_chunk_end} already complete",
                            file=sys.stderr,
                        )
                continue

        # Global hand_id: deterministic from deal_id
        hand_id = deal_id * 4

        hands = generate_deal(seed, deal_id)
        dealer = _deterministic_dealer(seed, deal_id)

        for focal_seat in range(4):
            current_hand_id = hand_id + focal_seat

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

                # Extract state features (69 columns) — from ORIGINAL hands
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
                    "hand_id": current_hand_id,
                    "deal_id": deal_id,
                    "focal_seat": focal_seat,
                    "action_type": action_type,
                    "contract_family": contract_family,
                    "bid_n": bid_n,
                    "trump_suit": trump_suit if trump_suit else "",
                    "is_moon": 0,
                    "is_loner": 0,
                    "dataset_seed": ds_seed,
                    "deal_uid": f"{ds_seed}:{deal_id}",
                    "hand_uid": f"{ds_seed}:{current_hand_id}",
                }
                # Add 69 state features as individual columns
                for i, fname in enumerate(STATE_FEATURE_NAMES):
                    row[fname] = state[i]
                row["net_points"] = net_points
                row["tricks_won"] = tricks_won
                row["focal_declared"] = focal_declared

                if multi:
                    row["std_net_points"] = std_np
                    row["n_samples"] = n_opponent_samples

                rows.append(row)

            # Moon and loner counterfactuals (appended after regular actions)
            if include_moon_loner:
                for contract_code, contract_family, trump_suit in contracts:
                    # State features for this contract
                    state = extract_state_features(obs, contract_family, trump_suit)

                    # --- Moon counterfactual ---
                    if multi:
                        np_vals = []
                        tw_vals = []
                        for config_hands in opp_configs:
                            np_i, tw_i = simulate_moon_counterfactual(
                                config_hands,
                                focal_seat,
                                contract_family,
                                trump_suit,
                            )
                            np_vals.append(np_i)
                            tw_vals.append(tw_i)
                        moon_net = sum(np_vals) / len(np_vals)
                        moon_tw = sum(tw_vals) / len(tw_vals)
                        mean_np = moon_net
                        std_np = (
                            sum((x - mean_np) ** 2 for x in np_vals) / len(np_vals)
                        ) ** 0.5
                    else:
                        moon_net, moon_tw = simulate_moon_counterfactual(
                            hands,
                            focal_seat,
                            contract_family,
                            trump_suit,
                        )

                    moon_row = {
                        "hand_id": current_hand_id,
                        "deal_id": deal_id,
                        "focal_seat": focal_seat,
                        "action_type": "bid",
                        "contract_family": contract_family,
                        "bid_n": 10,
                        "trump_suit": trump_suit if trump_suit else "",
                        "is_moon": 1,
                        "is_loner": 0,
                        "dataset_seed": ds_seed,
                        "deal_uid": f"{ds_seed}:{deal_id}",
                        "hand_uid": f"{ds_seed}:{current_hand_id}",
                    }
                    for i, fname in enumerate(STATE_FEATURE_NAMES):
                        moon_row[fname] = state[i]
                    moon_row["net_points"] = moon_net
                    moon_row["tricks_won"] = moon_tw
                    moon_row["focal_declared"] = True
                    if multi:
                        moon_row["std_net_points"] = std_np
                        moon_row["n_samples"] = n_opponent_samples
                    rows.append(moon_row)

                    # --- Loner counterfactual ---
                    if multi:
                        np_vals = []
                        tw_vals = []
                        for config_hands in opp_configs:
                            np_i, tw_i = simulate_loner_counterfactual(
                                config_hands,
                                focal_seat,
                                contract_family,
                                trump_suit,
                            )
                            np_vals.append(np_i)
                            tw_vals.append(tw_i)
                        loner_net = sum(np_vals) / len(np_vals)
                        loner_tw = sum(tw_vals) / len(tw_vals)
                        mean_np = loner_net
                        std_np = (
                            sum((x - mean_np) ** 2 for x in np_vals) / len(np_vals)
                        ) ** 0.5
                    else:
                        loner_net, loner_tw = simulate_loner_counterfactual(
                            hands,
                            focal_seat,
                            contract_family,
                            trump_suit,
                        )

                    loner_row = {
                        "hand_id": current_hand_id,
                        "deal_id": deal_id,
                        "focal_seat": focal_seat,
                        "action_type": "bid",
                        "contract_family": contract_family,
                        "bid_n": 10,
                        "trump_suit": trump_suit if trump_suit else "",
                        "is_moon": 0,
                        "is_loner": 1,
                        "dataset_seed": ds_seed,
                        "deal_uid": f"{ds_seed}:{deal_id}",
                        "hand_uid": f"{ds_seed}:{current_hand_id}",
                    }
                    for i, fname in enumerate(STATE_FEATURE_NAMES):
                        loner_row[fname] = state[i]
                    loner_row["net_points"] = loner_net
                    loner_row["tricks_won"] = loner_tw
                    loner_row["focal_declared"] = True
                    if multi:
                        loner_row["std_net_points"] = std_np
                        loner_row["n_samples"] = n_opponent_samples
                    rows.append(loner_row)

        # Flush chunk if at chunk boundary
        if chunked:
            current_chunk_end = (
                min((deal_id // chunk_size + 1) * chunk_size, n_deals) - 1
            )
            if deal_id == current_chunk_end and rows:
                _write_chunk(
                    rows,
                    output_dir,
                    chunk_deal_start,
                    current_chunk_end,
                    seed,
                    chunk_started_at,
                )
                total_rows_written += len(rows)
                if progress:
                    elapsed = time.time() - t0
                    rate = (deal_id + 1) / elapsed
                    print(
                        f"  [{deal_id + 1}/{n_deals}] chunk "
                        f"{chunk_deal_start}-{current_chunk_end} "
                        f"written ({len(rows)} rows), "
                        f"{rate:.1f} deals/s, {elapsed:.1f}s elapsed",
                        file=sys.stderr,
                    )
                rows = []

        elif progress and (deal_id + 1) % max(1, n_deals // 10) == 0:
            elapsed = time.time() - t0
            rate = (deal_id + 1) / elapsed
            print(
                f"  [{deal_id + 1}/{n_deals}] {len(rows)} rows, "
                f"{rate:.1f} deals/s, {elapsed:.1f}s elapsed",
                file=sys.stderr,
            )

    if chunked:
        # Any remaining rows (shouldn't happen if n_deals % chunk_size == 0,
        # but handle partial final chunk)
        if rows:
            final_start = (n_deals - 1) // chunk_size * chunk_size
            final_end = n_deals - 1
            _write_chunk(
                rows, output_dir, final_start, final_end, seed, chunk_started_at
            )
            total_rows_written += len(rows)
        return None
    else:
        return pd.DataFrame(rows)


def validate_gate_x1(
    df: pd.DataFrame, n_deals: int, include_moon_loner: bool = False
) -> None:
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

    # 3. net_points range is plausible (moon: +/-20, loner: +/-40)
    min_np = df["net_points"].min()
    max_np = df["net_points"].max()
    np_floor = -50 if include_moon_loner else -20
    np_ceil = 50 if include_moon_loner else 20
    assert min_np >= np_floor, f"net_points min too low: {min_np}"
    assert max_np <= np_ceil, f"net_points max too high: {max_np}"

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

    # 5. Row count sanity
    # Regular: ~40 actions per seat; moon/loner: +12 rows per seat (6 contracts × 2)
    if include_moon_loner:
        expected_rows = n_deals * 4 * (40 + 12)
    else:
        expected_rows = n_deals * 4 * 40
    actual_rows = len(df)
    ratio = actual_rows / expected_rows
    assert 0.3 <= ratio <= 2.0, (
        f"Row count {actual_rows} is outside expected range "
        f"({expected_rows * 0.3:.0f} - {expected_rows * 2.0:.0f})"
    )

    # 6. 69 state feature columns present
    for fname in STATE_FEATURE_NAMES:
        assert fname in df.columns, f"Missing state feature column: {fname}"

    # 7. is_moon and is_loner columns present
    assert "is_moon" in df.columns, "Missing is_moon column"
    assert "is_loner" in df.columns, "Missing is_loner column"

    if include_moon_loner:
        # Verify moon and loner rows exist
        moon_rows = df[df["is_moon"] == 1]
        loner_rows = df[df["is_loner"] == 1]
        assert len(moon_rows) > 0, "No moon counterfactual rows found"
        assert len(loner_rows) > 0, "No loner counterfactual rows found"
        # Each (deal, seat) should have exactly 6 moon + 6 loner
        moon_counts = moon_rows.groupby(["deal_id", "focal_seat"]).size()
        loner_counts = loner_rows.groupby(["deal_id", "focal_seat"]).size()
        assert (moon_counts == 6).all(), (
            f"Expected 6 moon rows per (deal, seat), got: "
            f"{moon_counts.value_counts().to_dict()}"
        )
        assert (loner_counts == 6).all(), (
            f"Expected 6 loner rows per (deal, seat), got: "
            f"{loner_counts.value_counts().to_dict()}"
        )
    else:
        # Without moon/loner, all is_moon and is_loner should be 0
        assert (df["is_moon"] == 0).all(), "Found is_moon=1 without include_moon_loner"
        assert (
            df["is_loner"] == 0
        ).all(), "Found is_loner=1 without include_moon_loner"

    avg_actions = actual_rows / (n_deals * 4)
    print(
        f"  Gate X1 PASS: {actual_rows} rows, {n_deals * 4} hands, "
        f"{avg_actions:.1f} avg actions/seat"
        f"{' (with moon/loner)' if include_moon_loner else ''}"
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
    parser.add_argument(
        "--include-moon-loner",
        action="store_true",
        help="Include moon/loner counterfactuals (R3+, not on by default)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Write parquet part files every N deals (reduces peak memory)",
    )
    parser.add_argument(
        "--dataset-seed",
        type=int,
        default=None,
        help="Dataset-level seed for global UIDs (defaults to --seed)",
    )
    args = parser.parse_args()

    n_deals = args.n_deals if args.n_deals is not None else MODE_DEALS[args.mode]
    n_opp = args.n_opponent_samples
    include_ml = args.include_moon_loner
    chunk_size = args.chunk_size

    print("=== R1.5 Counterfactual Action-Value Dataset Generator ===")
    print(f"  Seed: {args.seed}")
    print(f"  Mode: {args.mode} ({n_deals} deals)")
    print(f"  Opponent samples: {n_opp}")
    print(f"  Moon/loner: {'yes' if include_ml else 'no'}")
    print(f"  Chunk size: {chunk_size or 'disabled (single file)'}")
    print(f"  Continuation: {args.continuation_artifact}")

    # Load continuation policy
    print("  Loading continuation policy...")
    continuation = load_continuation_policy(args.continuation_artifact)

    # Determine output directories
    output_dir = Path(args.output_dir)
    datasets_dir = output_dir / "datasets"

    # Chunked output dir is a subdirectory
    chunked_output_dir = datasets_dir / "action_value" if chunk_size else None

    # Generate dataset
    sim_equiv = n_deals * n_opp
    extra_per_seat = " + 12 moon/loner" if include_ml else ""
    print(
        f"  Generating dataset ({n_deals} deals × 4 seats × "
        f"~40 actions{extra_per_seat} × {n_opp} samples)..."
    )
    print(f"  Simulation equivalents: ~{sim_equiv * 4 * 40:,}")

    result = generate_dataset(
        args.seed,
        n_deals,
        continuation,
        n_opponent_samples=n_opp,
        include_moon_loner=include_ml,
        chunk_size=chunk_size,
        output_dir=chunked_output_dir,
        dataset_seed=args.dataset_seed,
    )

    if chunk_size:
        # Chunked mode: read back and validate
        part_files = sorted(chunked_output_dir.glob("part_*.parquet"))
        total_rows = sum(len(pd.read_parquet(p)) for p in part_files)
        print(f"  Total rows: {total_rows} across {len(part_files)} part files")

        if not args.skip_validation:
            print("  Running Gate X1 validation on concatenated chunks...")
            df = pd.concat([pd.read_parquet(p) for p in part_files], ignore_index=True)
            validate_gate_x1(df, n_deals, include_moon_loner=include_ml)

        print(f"\n  Output: {chunked_output_dir}/")
        print(f"  Parts: {len(part_files)}")
        print(f"  Rows: {total_rows}")
        print(f"  Deals: {n_deals}")
        print("  Done.")
    else:
        df = result
        print(f"  Total rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")

        # Validate
        if not args.skip_validation:
            print("  Running Gate X1 validation...")
            validate_gate_x1(df, n_deals, include_moon_loner=include_ml)

        # Write output
        datasets_dir.mkdir(parents=True, exist_ok=True)
        output_path = datasets_dir / "action_value.parquet"
        df.to_parquet(output_path, index=False)

        print(f"\n  Output: {output_path}")
        print(f"  Rows: {len(df)}")
        print(f"  Deals: {n_deals}")
        print("  Done.")


if __name__ == "__main__":
    main()
