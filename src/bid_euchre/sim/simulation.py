import random
import argparse
from typing import Dict, Tuple, Optional, List
from ..core.cards import create_deck, shuffle_deck, deal_hands, Card
from ..core.rules import trick_winner
from ..strategy.strategy import Strategy, BasicStrategy, GreedyStrategy
from ..features.hand_eval import score_hand, get_hand_features

def play_single_hand(
    contract_type: str,
    trump_suit: Optional[str] = None,
    strategy: Optional[Strategy] = None,
) -> Tuple[int, int, List[int], List[Dict[str, int]]]:
    """
    Play one full 10-trick hand with the chosen bot.

    contract_type: "suit", "high", or "low"
    trump_suit: required for "suit", must be None for "high"/"low"

    Returns:
        (team0_tricks, team1_tricks, all_player_scores, all_player_features)
    where:
        - team 0 = players 0 and 2
        - team 1 = players 1 and 3
        - all_player_scores = list of 4 scalar hand scores (one per player)
        - all_player_features = list of 4 feature dicts (one per player)
    """
    if contract_type == "suit" and trump_suit is None:
        raise ValueError("trump_suit must be provided for 'suit' contracts")
    if contract_type in ("high", "low") and trump_suit is not None:
        raise ValueError("trump_suit must be None for 'high'/'low' contracts")

    # Use provided strategy or default to GreedyStrategy
    if strategy is None:
        strategy = GreedyStrategy()

    deck: List[Card] = create_deck()
    shuffle_deck(deck)
    hands = deal_hands(deck, num_players=4, hand_size=10)

    # Copy starting hands for scoring (since we mutate hands as we play)
    starting_hands = [list(h) for h in hands]
    
    # Extract features for ALL 4 players (removes measurement anchoring)
    all_player_scores = []
    all_player_features = []
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

    team_tricks = {0: 0, 1: 0}
    leader = random.randrange(4)  # player who leads the first trick

    # 10 tricks in a 10-card hand
    for _ in range(10):
        plays = []

        # Players act in order starting from leader
        for offset in range(4):
            player = (leader + offset) % 4
            hand = hands[player]

            card_index = strategy.choose_card(
                hand=hand,
                plays_so_far=plays,
                contract_type=contract_type,
                trump_suit=trump_suit,
                player_index=player,
            )
            card = hand.pop(card_index)
            plays.append((player, card))

        winner = trick_winner(
            plays,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )

        # Assign trick to a team
        if winner in (0, 2):
            team_tricks[0] += 1
        else:
            team_tricks[1] += 1

        leader = winner  # winner leads next trick

    return team_tricks[0], team_tricks[1], all_player_scores, all_player_features


def simulate_many_hands(
    n: int,
    contract_type: str,
    trump_suit: Optional[str] = None,
    seed: Optional[int] = None,
    strategy: Optional[Strategy] = None,
) -> Dict:
    """
    Run Monte Carlo simulation of n hands.

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
    if seed is not None:
        random.seed(seed)

    dist_team0 = {i: 0 for i in range(11)}  # possible tricks 0–10

    total0 = 0
    total1 = 0
    total_score_all = 0  # sum across all 4 players

    # score -> stats dict (aggregated across all players)
    score_buckets: Dict[int, Dict[str, float]] = {}

    # feature_name -> value -> stats dict (aggregated across all players)
    feature_buckets: Dict[str, Dict[int, Dict[str, float]]] = {}

    player_samples = 0  # count of player-hand observations

    for _ in range(n):
        t0, t1, all_scores, all_feats = play_single_hand(contract_type, trump_suit, strategy)
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


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run Bid Euchre simulations")
    parser.add_argument(
        "--n_per", "-n",
        type=int,
        default=5000,
        help="Number of hands per scenario (default: 5000)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=42,
        help="Random seed for reproducible results (default: 42)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # Run all scenarios with specified parameters
    run_all_scenarios(n_per=args.n_per, seed=args.seed)
