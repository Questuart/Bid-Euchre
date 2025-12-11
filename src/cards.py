from dataclasses import dataclass
from typing import List
import random

# Suits and ranks for this Bid Euchre variant
SUITS = ["C", "D", "H", "S"]  # Clubs, Diamonds, Hearts, Spades
RANKS = ["T", "J", "Q", "K", "A"]  # 10, Jack, Queen, King, Ace (no 9s)

# Same-color suit mapping for left bower logic (standard mode only)
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

    hands = []
    index = 0
    for _ in range(num_players):
        hands.append(deck[index:index + hand_size])
        index += hand_size

    return hands


# ================================
#        BOWER UTILITIES
#  (apply only in standard mode)
# ================================

def is_right_bower(card: Card, trump_suit: str) -> bool:
    return card.rank == "J" and card.suit == trump_suit


def is_left_bower(card: Card, trump_suit: str) -> bool:
    return card.rank == "J" and card.suit == SAME_COLOR_SUIT[trump_suit]


# ================================
#  EFFECTIVE SUIT (depends on mode)
# ================================

def effective_suit(card: Card, trump_suit: str, trump_mode: str):
    """
    Determine the effective suit under each trump mode.

    Modes:
      - "standard": bowers count as trump.
      - "high": no bowers.
      - "low": no bowers.
    """
    if trump_mode == "standard":
        if is_right_bower(card, trump_suit) or is_left_bower(card, trump_suit):
            return trump_suit

    # High & Low modes: no bowers → suit is real suit
    return card.suit


# ================================
#       RANK STRENGTH
# ================================

def rank_strength(card: Card, trump_suit: str, trump_mode: str):
    """
    Returns a numeric strength for comparing ranks.
    Lower index = weaker, higher index = stronger.
    """

    # === STANDARD (Euchre-style) ===
    # Order for non-bowers (bowers handled separately in rules.py)
    if trump_mode == "standard":
        order = ["T", "J", "Q", "K", "A"]  # T weakest, A strongest
        return order.index(card.rank)

    # === HIGH TRUMP ===
    # A high, T low
    if trump_mode == "high":
        order = ["T", "J", "Q", "K", "A"]
        return order.index(card.rank)

    # === LOW TRUMP ===
    # T high, A low  (REVERSED)
    if trump_mode == "low":
        order = ["A", "K", "Q", "J", "T"]  # A lowest, T highest
        return order.index(card.rank)

    raise ValueError(f"Unknown trump mode: {trump_mode}")
