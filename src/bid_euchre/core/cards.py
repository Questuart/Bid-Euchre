import random
from dataclasses import dataclass
from typing import List, Optional, Set

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


def shuffle_deck(deck: List[Card], rng: Optional[random.Random] = None) -> None:
    """
    Shuffle a deck of cards.

    Args:
        deck: List of cards to shuffle (modified in-place)
        rng: Optional random.Random instance. If None, creates a new unseeded instance.
    """
    if rng is None:
        # Create local RNG instance for reproducibility compliance
        rng = random.Random()
    rng.shuffle(deck)


def deal_hands(
    deck: List[Card],
    num_players: int = 4,
    hand_size: int = 10,
    method: str = "round_robin",
) -> List[List[Card]]:
    """
    Deal hand_size cards to num_players from the deck.

    Args:
        deck: Shuffled deck of cards
        num_players: Number of players (default 4)
        hand_size: Cards per player (default 10)
        method: Dealing method - "block" or "round_robin" (default "round_robin")

    Methods:
        - "block": Contiguous slices [0:10], [10:20], [20:30], [30:40]
          (legacy, can amplify seed-dependent deck patterns)
        - "round_robin": Alternating cards like real dealing
          (seat 0: 0,4,8..., seat 1: 1,5,9..., etc.)
    """
    if len(deck) < num_players * hand_size:
        raise ValueError("Not enough cards in deck to deal")

    if method == "block":
        # Block dealing: contiguous slices
        hands: List[List[Card]] = []
        index = 0
        for _ in range(num_players):
            hands.append(deck[index:index + hand_size])
            index += hand_size
        return hands

    elif method == "round_robin":
        # Round-robin dealing: alternate cards
        hands: List[List[Card]] = [[] for _ in range(num_players)]
        for i in range(num_players * hand_size):
            seat = i % num_players
            hands[seat].append(deck[i])
        return hands

    else:
        raise ValueError(f"Unknown deal method: {method}")


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


# ================================
#    CARD COMPARISON UTILITIES
# ================================

def card_strength_in_trick(
    card: Card,
    led_suit: str,
    trump_suit: Optional[str],
    contract_type: str,
) -> tuple:
    """
    Returns a comparable tuple for card strength in a trick context.

    Higher tuple = stronger card. Cards that can't win return (0, 0, 0).

    For suit contracts:
    - (3, 2, 0) = right bower (strongest)
    - (3, 1, 0) = left bower
    - (2, rank) = other trump
    - (1, rank) = led suit (non-trump)
    - (0, 0, 0) = offsuit that didn't lead (cannot win)

    For high/low contracts:
    - (1, rank) = led suit
    - (0, 0, 0) = offsuit (cannot win)
    """
    eff_suit = effective_suit(card, trump_suit, contract_type)

    if contract_type == "suit" and trump_suit is not None:
        # Check for bowers
        if is_right_bower(card, trump_suit):
            return (3, 2, 0)
        if is_left_bower(card, trump_suit):
            return (3, 1, 0)

        # Other trump
        if eff_suit == trump_suit:
            return (2, rank_strength(card, contract_type), 0)

        # Led suit (non-trump)
        if eff_suit == led_suit:
            return (1, rank_strength(card, contract_type), 0)

        # Offsuit - cannot win
        return (0, 0, 0)

    else:
        # High or low contract - no trump
        if card.suit == led_suit:
            return (1, rank_strength(card, contract_type), 0)
        return (0, 0, 0)


def cards_that_beat(
    candidate: Card,
    led_suit: str,
    trump_suit: Optional[str],
    contract_type: str,
) -> Set[Card]:
    """
    Returns set of all cards from the deck that can beat the candidate.

    This is used for "sure win" logic: if no remaining card can beat
    the candidate, it's a guaranteed winner.

    Args:
        candidate: The card we're considering playing
        led_suit: The suit that was led (or will be led if candidate leads)
        trump_suit: Trump suit for "suit" contracts, None otherwise
        contract_type: "suit", "high", or "low"

    Returns:
        Set of Card objects that beat the candidate in this context
    """
    candidate_strength = card_strength_in_trick(candidate, led_suit, trump_suit, contract_type)

    # If candidate can't even participate (offsuit in led suit scenario),
    # everything that CAN participate beats it
    if candidate_strength == (0, 0, 0):
        # Return all cards that can win (all trump + all led suit)
        result: Set[Card] = set()
        for suit in SUITS:
            for rank in RANKS:
                card = Card(suit, rank)
                if card_strength_in_trick(card, led_suit, trump_suit, contract_type) > (0, 0, 0):
                    result.add(card)
        return result

    # Find all cards stronger than candidate
    result = set()
    for suit in SUITS:
        for rank in RANKS:
            card = Card(suit, rank)
            card_strength = card_strength_in_trick(card, led_suit, trump_suit, contract_type)
            if card_strength > candidate_strength:
                result.add(card)

    return result
