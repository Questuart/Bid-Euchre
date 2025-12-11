from typing import List, Tuple, Optional
from .cards import Card, effective_suit, rank_strength


def choose_card_basic(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    contract_type: str,
    trump_suit: Optional[str],
    player_index: int,
) -> int:
    """
    Very simple bot:
    - If you can follow the led suit, play your lowest-ranked card in that suit.
    - If you cannot follow suit, play your lowest-ranked card overall.

    Works for:
      - "suit" contracts (with trump_suit)
      - "high" and "low" contracts (no trump_suit)
    """

    # Determine led suit
    if plays_so_far:
        _, lead_card = plays_so_far[0]
        led_suit = effective_suit(lead_card, trump_suit, contract_type)
    else:
        led_suit = None

    # 1) Try to follow suit with lowest-rank card
    best_idx: Optional[int] = None
    best_rank: Optional[int] = None

    if led_suit is not None:
        for i, c in enumerate(hand):
            if effective_suit(c, trump_suit, contract_type) == led_suit:
                r = rank_strength(c, contract_type)
                if best_rank is None or r < best_rank:
                    best_rank = r
                    best_idx = i

        if best_idx is not None:
            return best_idx

    # 2) If we can't follow suit, play overall lowest-ranked card
    best_idx = None
    best_rank = None
    for i, c in enumerate(hand):
        r = rank_strength(c, contract_type)
        if best_rank is None or r < best_rank:
            best_rank = r
            best_idx = i

    assert best_idx is not None  # hand must be non-empty when called
    return best_idx
