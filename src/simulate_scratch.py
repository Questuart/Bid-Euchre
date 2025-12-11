from typing import Optional
from .cards import create_deck, shuffle_deck, deal_hands
from .rules import trick_winner
from .strategy import choose_card_basic


def play_full_hand(contract_type: str, trump_suit: Optional[str] = None):
    deck = create_deck()
    shuffle_deck(deck)
    hands = deal_hands(deck, num_players=4, hand_size=10)

    print(f"Contract type: {contract_type}   |   Trump suit: {trump_suit}")
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

            card_index = choose_card_basic(
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


def main():
    # Examples:
    # Suit contract: hearts trump
    # play_full_hand(contract_type="suit", trump_suit="H")

    # High no-trump:
    # play_full_hand(contract_type="high", trump_suit=None)

    # Low no-trump:
    play_full_hand(contract_type="suit", trump_suit="H")


if __name__ == "__main__":
    main()
