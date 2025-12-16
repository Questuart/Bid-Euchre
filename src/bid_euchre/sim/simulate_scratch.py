import argparse
from typing import Optional

from ..core.cards import create_deck, shuffle_deck, deal_hands
from ..core.cards import Card
from ..core.rules import trick_winner
from ..strategy.strategy import Strategy, BasicStrategy, GreedyStrategy


def play_full_hand(
    contract_type: str,
    trump_suit: Optional[str],
    strategy: Strategy,
) -> None:
    deck = create_deck()
    shuffle_deck(deck)
    hands = deal_hands(deck, num_players=4, hand_size=10)

    print(f"Contract type: {contract_type}   |   Trump suit: {trump_suit}")
    print(f"Strategy: {strategy}")
    for i, hand in enumerate(hands):
        print(f"Player {i} starting hand: {hand}")

    # team 0 = players 0 and 2
    # team 1 = players 1 and 3
    team_tricks = {0: 0, 1: 0}

    leader = 0  # player who leads first trick

    for trick_num in range(10):  # 10 tricks in a 10-card hand
        print(f"\n--- Trick {trick_num + 1} ---")
        plays = []

        # Players play in order starting from leader
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
            print(f"Player {player} plays {card}")

        winner = trick_winner(
            plays,
            contract_type=contract_type,
            trump_suit=trump_suit,
        )
        print(f"Trick winner: Player {winner}")

        # assign trick to a team
        if winner in (0, 2):
            team_tricks[0] += 1
        else:
            team_tricks[1] += 1

        leader = winner  # winner leads next trick

    print("\n=== Final result ===")
    print("Team 0 (players 0 & 2) tricks:", team_tricks[0])
    print("Team 1 (players 1 & 3) tricks:", team_tricks[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Play a single 10-trick hand with basic or greedy bots."
    )
    parser.add_argument(
        "contract_type",
        nargs="?",
        choices=["suit", "high", "low"],
        default="suit",
        help="Type of contract: 'suit', 'high', or 'low'. Default: suit.",
    )
    parser.add_argument(
        "trump_suit",
        nargs="?",
        help="Trump suit for 'suit' contracts: C, D, H, or S. "
             "Ignored for 'high' and 'low'. Default: H for suit.",
    )
    parser.add_argument(
        "--strategy",
        choices=["basic", "greedy"],
        default="greedy",
        help="Strategy to use: 'basic' or 'greedy'. Default: greedy.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    contract_type = args.contract_type
    trump_suit: Optional[str] = args.trump_suit

    # Create strategy instance
    strategy: Strategy = (
        GreedyStrategy() if args.strategy == "greedy" else BasicStrategy()
    )

    # Validate trump_suit / contract_type combo
    if contract_type == "suit":
        if trump_suit is None:
            trump_suit = "H"
        trump_suit = trump_suit.upper()
        if trump_suit not in ("C", "D", "H", "S"):
            raise ValueError(
                f"Invalid trump suit '{trump_suit}'. Must be one of C, D, H, S."
            )
    else:
        if trump_suit is not None:
            print(
                f"Warning: trump_suit '{trump_suit}' ignored "
                f"for contract_type={contract_type}."
            )
        trump_suit = None

    play_full_hand(
        contract_type=contract_type,
        trump_suit=trump_suit,
        strategy=strategy,
    )


if __name__ == "__main__":
    main()
