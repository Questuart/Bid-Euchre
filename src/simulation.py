from typing import Dict, Tuple, Optional, List
from .cards import create_deck, shuffle_deck, deal_hands, Card
from .rules import trick_winner
from .strategy import choose_card_basic


def play_single_hand(
    contract_type: str,
    trump_suit: Optional[str] = None,
) -> Tuple[int, int]:
    """
    Play one full 10-trick hand with the basic bot.

    contract_type: "suit", "high", or "low"
    trump_suit: required for "suit", must be None for "high"/"low"

    Returns:
        (team0_tricks, team1_tricks)
    where:
        team 0 = players 0 and 2
        team 1 = players 1 and 3
    """
    if contract_type == "suit" and trump_suit is None:
        raise ValueError("trump_suit must be provided for 'suit' contracts")
    if contract_type in ("high", "low") and trump_suit is not None:
        raise ValueError("trump_suit must be None for 'high'/'low' contracts")

    deck: List[Card] = create_deck()
    shuffle_deck(deck)
    hands = deal_hands(deck, num_players=4, hand_size=10)

    team_tricks = {0: 0, 1: 0}
    leader = 0  # player who leads the first trick

    # 10 tricks in a 10-card hand
    for _ in range(10):
        plays = []

        # Players act in order starting from leader
        for offset in range(4):
            player = (leader + offset) % 4
            hand = hands[player]

            card_index = choose_card_basic(
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

    return team_tricks[0], team_tricks[1]


def simulate_many_hands(
    n: int,
    contract_type: str,
    trump_suit: Optional[str] = None,
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
        }
    """
    dist_team0 = {i: 0 for i in range(11)}  # possible tricks 0–10

    total0 = 0
    total1 = 0

    for _ in range(n):
        t0, t1 = play_single_hand(contract_type, trump_suit)
        total0 += t0
        total1 += t1
        dist_team0[t0] += 1

    return {
        "hands": n,
        "contract_type": contract_type,
        "trump_suit": trump_suit,
        "avg_team0": total0 / n,
        "avg_team1": total1 / n,
        "distribution_team0": dist_team0,
    }


def run_all_scenarios(n_per: int = 5000) -> None:
    """
    Run simulations for:
      - High no-trump
      - Low no-trump
      - Suit contracts for C, D, H, S

    n_per: number of hands per scenario.
    """
    scenarios = []

    # High and Low no-trump (no trump_suit)
    scenarios.append(("high", None, "High no-trump"))
    scenarios.append(("low", None, "Low no-trump"))

    # Suit contracts for each trump suit
    for suit in ["C", "D", "H", "S"]:
        label = f"Suit contract, trump={suit}"
        scenarios.append(("suit", suit, label))

    for contract_type, trump_suit, label in scenarios:
        results = simulate_many_hands(
            n=n_per,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )

        print("\n========================================")
        print(f"Scenario: {label}")
        print("========================================")
        print("Hands:        ", results["hands"])
        print("Contract type:", results["contract_type"])
        print("Trump suit:   ", results["trump_suit"])
        print("Avg tricks Team 0:", f"{results['avg_team0']:.3f}")
        print("Avg tricks Team 1:", f"{results['avg_team1']:.3f}")
        print("Sum of avgs (should be ~10):",
              f"{results['avg_team0'] + results['avg_team1']:.3f}")

        print("\nDistribution of Team 0 tricks:")
        dist = results["distribution_team0"]
        total_count = sum(dist.values())
        for k in range(11):
            count = dist[k]
            pct = 100.0 * count / total_count if total_count > 0 else 0.0
            print(f"  {k}: {count:5d}  ({pct:5.1f}%)")


if __name__ == "__main__":
    # Run all scenarios with 5000 hands each
    run_all_scenarios(n_per=5000)
