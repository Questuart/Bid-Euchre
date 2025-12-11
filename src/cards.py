from dataclasses import dataclass
from typing import List, Optional
import random

# Suits and ranks for this Bid Euchre variant
SUITS = ["C", "D", "H", "S"]  # Clubs, Diamonds, Hearts, Spades
RANKS = ["T", "J", "Q", "K", "A"]  # 10, Jack, Queen, King, Ace (no 9s)

# Same-color suit mapping for left bower logic (suit contracts only)
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
        return f"{self.rank}{self.suit}"

    def __repr__(self) -> str:
        return str(self)


def create_deck() -> List[Card]:
    """
    Create the deck for this Bid Euchre variant:

    - Ranks: T, J, Q, K, A (no 9s)
    - Suits: C, D, H, S
    - 2 copies of every (suit, rank) combination.

    Total cards = 4 suits * 5 ranks * 2 = 40 cards.
    """
    single = [Card(s, r) for s in SUITS for r in RANKS]
    return single + list(single)  # double deck


def shuffle_deck(deck: List[Card]) -> None:
    random.shuffle(deck)


def deal_hands(
    deck: List[Card],
    num_players: int = 4,
    hand_size: int = 10,
) -> List[List[Card]]:
    """
    Deal hand_size cards to num_players from the top of the deck.
    """
    if len(deck) < num_players * hand_size:
        raise ValueError("Not enough cards in deck to deal")

    hands: List[List[Card]] = []
    index = 0
    for _ in range(num_players):
        hands.append(deck[index:index + hand_size])
        index += hand_size

    return hands


# ================================
#        BOWER UTILITIES
#  (apply only in SUIT contracts)
# ================================

def is_right_bower(card: Card, trump_suit: str) -> bool:
    return card.rank == "J" and card.suit == trump_suit


def is_left_bower(card: Card, trump_suit: str) -> bool:
    return card.rank == "J" and card.suit == SAME_COLOR_SUIT[trump_suit]


# ================================
#  EFFECTIVE SUIT (depends on contract)
# ================================

def effective_suit(
    card: Card,
    trump_suit: Optional[str],
    contract_type: str,
) -> str:
    """
    Determine the effective suit of a card based on the contract.

    contract_type:
      - "suit" : normal trump-suit game, bowers count as trump.
      - "high" : no trump suit; suits are literal.
      - "low"  : no trump suit; suits are literal.
    """
    if contract_type == "suit" and trump_suit is not None:
        if is_right_bower(card, trump_suit) or is_left_bower(card, trump_suit):
            return trump_suit

    # High & Low: no bowers, no trump; suit is always the printed suit.
    return card.suit


# ================================
#       RANK STRENGTH
# ================================

def rank_strength(card: Card, contract_type: str) -> int:
    """
    Returns a numeric strength for comparing ranks within a suit.

    Higher index = stronger card.

    For "suit" and "high":
        T < J < Q < K < A

    For "low":
        A < K < Q < J < T   (T is strongest, A is weakest)
    """

    if contract_type in ("suit", "high"):
        order = ["T", "J", "Q", "K", "A"]
    elif contract_type == "low":
        order = ["A", "K", "Q", "J", "T"]
    else:
        raise ValueError(f"Unknown contract_type: {contract_type}")

    return order.index(card.rank)
