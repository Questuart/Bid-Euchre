"""
Core simulation engine for Bid Euchre.

This module is library code (no CLI). It supports:
- self-play (same strategy for all seats)
- head-to-head by seat (different strategies per player)
"""

import random
from typing import Dict, Tuple, Optional, List, TYPE_CHECKING

from ..core.cards import create_deck, shuffle_deck, deal_hands, Card
from ..core.rules import trick_winner, get_legal_indices
from ..features.hand_eval import score_hand, get_hand_features
from ..strategy import Strategy, GreedyStrategy
from .deals import generate_deal, generate_initial_leader

if TYPE_CHECKING:
    from ..logging import GameLogger


def play_single_hand(
    contract_type: Optional[str],
    trump_suit: Optional[str] = None,
    strategy: Optional[Strategy] = None,
    strategies: Optional[List[Strategy]] = None,
    logger: Optional["GameLogger"] = None,
    deal_id: int = 0,
    hands: Optional[List[List[Card]]] = None,
    deal_seed: Optional[int] = None,
    initial_leader: Optional[int] = None,
    rng: Optional[random.Random] = None,
) -> Tuple[int, int, List[int], List[Dict[str, int]], int, List[List[Card]], Optional[int], Optional[int], Optional[int], str, Optional[str]]:
    """
    Play one full 10-trick hand.

    If contract_type is None, a bidding phase is conducted first.
    The winner of the bid chooses the contract and leads the first trick.

    Returns:
        (t0, t1, scores, features, leader, hands, bid, dealer_pos, bidder_pos, final_contract, final_trump)
    """
    # Resolve strategy-per-seat.
    if strategies is not None:
        if len(strategies) != 4:
            raise ValueError(f"`strategies` must have length 4 (got {len(strategies)})")
        seat_strategies = strategies
    else:
        if strategy is None:
            strategy = GreedyStrategy()
        seat_strategies = [strategy, strategy, strategy, strategy]

    if hands is None:
        deck: List[Card] = create_deck()
        shuffle_deck(deck, rng=rng)
        hands = deal_hands(deck, num_players=4, hand_size=10)
    else:
        hands = [list(h) for h in hands]

    starting_hands = [list(h) for h in hands]

    # BIDDING PHASE
    bidding_data = None
    dealer_index = None  # Track dealer position (0-3 or None if no bidding)
    bidder_position = None  # Track auction winner (0-3 or None)

    if contract_type is None:
        # Determine dealer
        if initial_leader is not None:
            dealer_index = (initial_leader - 1) % 4
        else:
            if rng is not None:
                dealer_index = rng.randrange(4)
            else:
                dealer_index = random.randrange(4)

        current_high_bid = 0
        winning_bidder = None
        final_contract = None
        final_trump = None

        # Bidding order: LOD, Partner of LOD, ROD, Dealer
        for i in range(1, 5):
            player_idx = (dealer_index + i) % 4
            partner_idx = (player_idx + 2) % 4
            strat = seat_strategies[player_idx]

            bid, ctype, trump = strat.decide_bid(
                hand=starting_hands[player_idx],
                current_high_bid=current_high_bid,
                current_winner_index=winning_bidder,
                partner_index=partner_idx,
                player_index=player_idx
            )

            # Dealer-partner pass rule: dealer passes if partner has the high bid
            if player_idx == dealer_index and winning_bidder == partner_idx:
                continue

            if bid > current_high_bid:
                current_high_bid = bid
                winning_bidder = player_idx
                final_contract = ctype
                final_trump = trump

        if winning_bidder is None:
            # Misdeal: everyone passed
            # Return zeros but still need scores/features (use dummy contract for logging)
            # Actually, let's just use 'high' as a dummy for feature extraction in misdeals
            dummy_ctype = "high"
            all_player_scores = [score_hand(h, dummy_ctype, None) for h in starting_hands]
            all_player_features = [get_hand_features(h, dummy_ctype, None) for h in starting_hands]
            # dealer_index is known, bidder_position is None (misdeal)
            return 0, 0, all_player_scores, all_player_features, -1, starting_hands, 0, dealer_index, None, dummy_ctype, None

        contract_type = final_contract
        trump_suit = final_trump
        initial_leader = winning_bidder
        bidder_position = winning_bidder  # Capture bidder for logging
        bidding_data = {
            "winner": winning_bidder,
            "bid": current_high_bid,
            "contract": contract_type,
            "trump": trump_suit
        }
    else:
        # Contract was fixed, no bid was made
        current_high_bid = None
        # No bidding phase: dealer and bidder are unknown
        dealer_index = None
        bidder_position = None

    # Validation (now that contract is decided)
    if contract_type == "suit" and trump_suit is None:
        raise ValueError("trump_suit must be provided or decided for 'suit' contracts")

    # Extract features for ALL 4 players
    all_player_scores: List[int] = []
    all_player_features: List[Dict[str, int]] = []
    for player_idx in range(4):
        score = score_hand(
            starting_hands[player_idx],
            contract_type=contract_type,
            trump_suit=trump_suit,
            mode="scalar",
        )
        features = get_hand_features(
            starting_hands[player_idx],
            contract_type=contract_type,
            trump_suit=trump_suit,
        )
        all_player_scores.append(score)
        all_player_features.append(features)

    # Log bidding if it happened
    if logger and bidding_data:
        # We need a new log event or just include it in hand_end.
        # For now, we can pass it via logger context if we had one.
        # Let's assume the logger will be updated or we'll just use the hand_end features.
        pass

    team_tricks = {0: 0, 1: 0}
    if initial_leader is None:
        if deal_seed is not None:
            initial_leader = generate_initial_leader(deal_seed, deal_id)
        else:
            if rng is not None:
                initial_leader = rng.randrange(4)
            else:
                initial_leader = random.randrange(4)
    leader = initial_leader

    # 10 tricks in a 10-card hand
    for trick_num in range(10):
        plays = []
        trick_leader = leader

        # Players act in order starting from leader
        for offset in range(4):
            player = (leader + offset) % 4
            hand = hands[player]

            # Engine-level guardrail: enforce legal plays (not just in strategies).
            legal_indices = get_legal_indices(hand, plays, contract_type, trump_suit)
            strat = seat_strategies[player]
            card_index = strat.choose_card(
                hand=hand,
                plays_so_far=plays,
                contract_type=contract_type,
                trump_suit=trump_suit,
                player_index=player,
            )
            if card_index not in legal_indices:
                raise ValueError(
                    f"Illegal play from strategy={getattr(strat, 'name', type(strat).__name__)} "
                    f"player={player} contract={contract_type} trump={trump_suit} "
                    f"chosen_index={card_index} legal_indices={legal_indices} hand_size={len(hand)}"
            )

            # Index integrity check: verify strategy returns valid index into actual hand
            # (catches bugs where strategy sorts/filters hand and returns wrong index)
            if card_index < 0 or card_index >= len(hand):
                raise ValueError(
                    f"Index integrity failure: strategy={getattr(strat, 'name', type(strat).__name__)} "
                    f"returned out-of-bounds index {card_index} for hand of size {len(hand)} "
                    f"player={player}"
                )

            card = hand.pop(card_index)
            plays.append((player, card))

        winner = trick_winner(
            plays,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )

        # Log trick completion (if logger enabled)
        if logger and logger.log_tricks:
            logger.log_trick_end(deal_id, trick_num, trick_leader, plays, winner)

        # Assign trick to a team
        if winner in (0, 2):
            team_tricks[0] += 1
        else:
            team_tricks[1] += 1

        leader = winner  # winner leads next trick

    return team_tricks[0], team_tricks[1], all_player_scores, all_player_features, initial_leader, starting_hands, current_high_bid, dealer_index, bidder_position, contract_type, trump_suit


def simulate_many_hands(
    n: int,
    contract_type: str,
    trump_suit: Optional[str] = None,
    seed: Optional[int] = None,
    strategy: Optional[Strategy] = None,
    strategies: Optional[List[Strategy]] = None,
    logger: Optional["GameLogger"] = None,
    deal_seed: Optional[int] = None,
) -> Dict:
    """
    Run Monte Carlo simulation of n hands.

    Args:
        n: Number of hands to simulate
        contract_type: "suit", "high", or "low"
        trump_suit: Trump suit for suit contracts
        seed: Random seed for reproducibility
        strategy: Strategy to use (defaults to GreedyStrategy)
        logger: Optional GameLogger for structured JSONL logging

    Returns a summary dict:
        {
            "hands": n,
            "contract_type": contract_type,
            "trump_suit": trump_suit,
            "avg_team0": float,
            "avg_team1": float,
            "distribution_team0": {0..10: count},
            "avg_score": float,  # avg across all 4 players
            "score_buckets": { score -> {count, total_tricks, avg_tricks} },
            "feature_buckets": {
                feature_name -> {
                    value -> {count, total_tricks, avg_tricks}
                }
            },
            "player_samples": int,  # total player-hand samples (n * 4)
        }

    Features are tracked for ALL 4 players per hand, bucketed by their team's tricks.
    This removes measurement anchoring and 4x the effective sample size.
    """
    # Create local RNG for reproducibility (never mutate global random state)
    local_rng: Optional[random.Random] = None
    if seed is not None and deal_seed is None:
        local_rng = random.Random(seed)

    dist_team0 = {i: 0 for i in range(11)}  # possible tricks 0–10

    total0 = 0
    total1 = 0
    total_score_all = 0  # sum across all 4 players

    # score -> stats dict (aggregated across all players)
    score_buckets: Dict[int, Dict[str, float]] = {}

    # feature_name -> value -> stats dict (aggregated across all players)
    feature_buckets: Dict[str, Dict[int, Dict[str, float]]] = {}

    player_samples = 0  # count of player-hand observations

    for deal_id in range(n):
        if deal_seed is not None:
            deal_hands_ = generate_deal(deal_seed, deal_id)
            t0, t1, all_scores, all_feats, initial_leader, starting_hands, winning_bid, dealer_pos, bidder_pos, actual_contract, actual_trump = play_single_hand(
                contract_type=contract_type,
                trump_suit=trump_suit,
                strategy=strategy,
                strategies=strategies,
                logger=logger,
                deal_id=deal_id,
                hands=deal_hands_,
                deal_seed=deal_seed,
            )
        else:
            t0, t1, all_scores, all_feats, initial_leader, starting_hands, winning_bid, dealer_pos, bidder_pos, actual_contract, actual_trump = play_single_hand(
                contract_type=contract_type,
                trump_suit=trump_suit,
                strategy=strategy,
                strategies=strategies,
                logger=logger,
                deal_id=deal_id,
                rng=local_rng,
            )

        # Log hand completion (if logger enabled)
        if logger and logger.is_enabled:
            logger.log_hand_end(
                deal_id=deal_id,
                seed=seed,
                contract=actual_contract,
                trump=actual_trump,
                leader=initial_leader,
                t0=t0,
                t1=t1,
                features=all_feats,
                scores=all_scores,
                hands=starting_hands,
                winning_bid=winning_bid,
                dealer_position=dealer_pos,
                bidder_position=bidder_pos,
            )
        total0 += t0
        total1 += t1
        dist_team0[t0] += 1

        # Process ALL 4 players' features
        for player_idx in range(4):
            # Determine this player's team's tricks
            if player_idx in (0, 2):
                team_tricks = t0
            else:
                team_tricks = t1

            score = all_scores[player_idx]
            feats = all_feats[player_idx]

            total_score_all += score
            player_samples += 1

            # Scalar score buckets (by this player's team's tricks)
            sb = score_buckets.setdefault(score, {"count": 0, "total_tricks": 0.0})
            sb["count"] += 1
            sb["total_tricks"] += team_tricks

            # Feature buckets (by this player's team's tricks)
            for fname, val in feats.items():
                fb = feature_buckets.setdefault(fname, {})
                vb = fb.setdefault(val, {"count": 0, "total_tricks": 0.0})
                vb["count"] += 1
                vb["total_tricks"] += team_tricks

    # Compute avg_tricks in each score bucket
    for score, stats in score_buckets.items():
        if stats["count"] > 0:
            stats["avg_tricks"] = stats["total_tricks"] / stats["count"]
        else:
            stats["avg_tricks"] = 0.0

    # Compute avg_tricks in each feature bucket
    for fname, by_val in feature_buckets.items():
        for val, stats in by_val.items():
            if stats["count"] > 0:
                stats["avg_tricks"] = stats["total_tricks"] / stats["count"]
            else:
                stats["avg_tricks"] = 0.0

    return {
        "hands": n,
        "contract_type": contract_type,
        "trump_suit": trump_suit,
        "avg_team0": total0 / n,
        "avg_team1": total1 / n,
        "distribution_team0": dist_team0,
        "avg_score": total_score_all / player_samples if player_samples > 0 else 0,
        "score_buckets": score_buckets,
        "feature_buckets": feature_buckets,
        "player_samples": player_samples,
        # Backward compatibility aliases
        "avg_score_player0": total_score_all / player_samples if player_samples > 0 else 0,
        "score_buckets_player0": score_buckets,
        "feature_buckets_player0": feature_buckets,
    }


def run_all_scenarios(
    n_per: int = 5000,
    seed: Optional[int] = None,
    strategy: Optional[Strategy] = None,
    logger: Optional["GameLogger"] = None,
) -> None:
    """
    Run simulations for:
      - High no-trump
      - Low no-trump
      - Suit contracts for C, D, H, S

    Args:
    n_per: number of hands per scenario.
        seed: random seed for reproducibility (each scenario gets seed + offset).
        strategy: strategy to use (defaults to GreedyStrategy).
        logger: optional GameLogger for structured JSONL logging.
    """
    scenarios = []

    # High and Low no-trump (no trump_suit)
    scenarios.append(("high", None, "High no-trump"))
    scenarios.append(("low", None, "Low no-trump"))

    # Suit contracts for each trump suit
    for suit in ["C", "D", "H", "S"]:
        label = f"Suit contract, trump={suit}"
        scenarios.append(("suit", suit, label))

    for i, (contract_type, trump_suit, label) in enumerate(scenarios):
        # Each scenario gets a different seed offset for variety
        scenario_seed = seed + i if seed is not None else None
        results = simulate_many_hands(
            n=n_per,
            contract_type=contract_type,
            trump_suit=trump_suit,
            seed=scenario_seed,
            strategy=strategy,
            logger=logger,
        )

        print("\n========================================")
        print(f"Scenario: {label}")
        print("========================================")
        print("Hands:            ", results["hands"])
        print("Player samples:   ", results["player_samples"], "(4x hands)")
        print("Contract type:    ", results["contract_type"])
        print("Trump suit:       ", results["trump_suit"])
        print("Avg score:        ", f"{results['avg_score']:.2f}")
        print("Avg tricks Team 0:", f"{results['avg_team0']:.3f}")
        print("Avg tricks Team 1:", f"{results['avg_team1']:.3f}")
        print("Sum of avgs (≈10):",
              f"{results['avg_team0'] + results['avg_team1']:.3f}")

        print("\nDistribution of Team 0 tricks:")
        dist = results["distribution_team0"]
        total_count = sum(dist.values())
        for k in range(11):
            count = dist[k]
            pct = 100.0 * count / total_count if total_count > 0 else 0.0
            print(f"  {k}: {count:5d}  ({pct:5.1f}%)")

        # Optional: print a small sample of score buckets for sanity checking
        buckets = results["score_buckets"]
        if buckets:
            print("\nSample of score buckets (hand score → avg tricks for team):")
            for score in sorted(buckets.keys())[:8]:
                b = buckets[score]
                print(f"  Score {score:3d}: "
                      f"n={b['count']:4d}, avg_tricks={b['avg_tricks']:.3f}")
