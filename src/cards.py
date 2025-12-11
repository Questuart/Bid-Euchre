from dataclasses import dataclass
from typing import List
import random

# Suits and ranks for this Bid Euchre variant
SUITS = ["C", "D", "H", "S"]  # Clubs, Diamonds, Hearts, Spades
RANKS = ["T", "J", "Q", "K", "A"]  # 10, Jack, Queen, King, Ace (no 9s)

# Same-color suit mapping for left bower logic:
#  - Spades <-> Clubs (both black)
#  - Hearts <-> Diamonds (both red)
SAME_COLOR_SUIT = {
    "S": "C",
    "C": "S",
    "H": "D",
    "D": "H",
}


@dataclass(frozen=True)
class Card:
    suit: str  # "C", "D", "H", "S"
    rank: str  # "T", "J", "Q", "K", "A"

    def __str__(self) -> str:
        # Example: "JH" for Jack of Hearts
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return str(self)


def create_deck() -> List[Card]:
    """
    Create the deck for this Bid Euchre variant:

    - Ranks: T, J, Q, K, A  (no 9s)
    - Suits: C, D, H, S
    - 2 copies of every (suit, rank) combination.

    Total cards: 4 suits * 5 ranks * 2 = 40.
    """
    single = [Card(s, r) for s in SUITS for r in RANKS]
    # Double-deck: 2 of each suit/rank
    return single + list(single)


def shuffle_deck(deck: List[Card]) -> None:
    """Shuffle the deck in place."""
    random.shuffle(deck)


def deal_hands(
    deck: List[Card],
    num_players: int = 4,
    hand_size: int = 10,
) -> List[List[Card]]:
    """
    Deal `hand_size` cards to `num_players` from the top of the deck.
    Default: 4 players, 10 cards each (total 40 cards).
    """
    if len(deck) < num_players * hand_size:
        raise ValueError("Not enough cards in deck to deal")

    hands: List[List[Card]] = []
    index = 0
    for _ in range(num_players):
        hand = deck[index:index + hand_size]
        hands.append(hand)
        index += hand_size
    return hands


# ----- Trump / bower utilities ----- #

def is_right_bower(card: Card, trump_suit: str) -> bool:
    """Right bower: Jack of trump suit."""
    return card.rank == "J" and card.suit == trump_suit


def is_left_bower(card: Card, trump_suit: str) -> bool:
    """
    Left bower: Jack of the same-color suit as trump.
    E.g. trump = Hearts -> left bower = Jack of Diamonds.
    """
    return card.rank == "J" and card.suit == SAME_COLOR_SUIT[trump_suit]


def effective_suit(card: Card, trump_suit: str) -> str:
    """
    In Bid Euchre, the left bower is treated as trump suit.
    This returns the suit the card *plays as* given the trump.
    """
    if is_right_bower(card, trump_suit) or is_left_bower(card, trump_suit):
        return trump_suit
    return card.suit


def rank_strength(rank: str) -> int:
    """
    Strength of a rank within a suit (ignoring bowers).
    Higher number = stronger card.
    Order is T < J < Q < K < A.
    """
    return RANKS.index(rank)
