from typing import List, Tuple, Optional
from .cards import Card, effective_suit, rank_strength

def choose_card_basic(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    trump_suit: str,
    player_index: int,
) -> int:
    """
    Very simple bot:
    - If you can follow led suit, play your *lowest* card in that suit.
    - Otherwise, play your overall lowest card.
    Returns the INDEX in `hand` of the chosen card.
    """
    # Determine led suit if there is a lead
    if plays_so_far:
        _, lead_card = plays_so_far[0]
        led_suit = effective_suit(lead_card, trump_suit)
    else:
        led_suit = None

    # 1) Try to follow suit with lowest rank card
    best_idx: Optional[int] = None
    best_rank: Optional[int] = None

    if led_suit is not None:
        for i, c in enumerate(hand):
            if effective_suit(c, trump_suit) == led_suit:
                r = rank_strength(c.rank)
                if best_rank is None or r < best_rank:
                    best_rank = r
                    best_idx = i

        if best_idx is not None:
            return best_idx

    # 2) If we can't follow suit, play overall lowest rank card
    best_idx = None
    best_rank = None
    for i, c in enumerate(hand):
        r = rank_strength(c.rank)
        if best_rank is None or r < best_rank:
            best_rank = r
            best_idx = i

    assert best_idx is not None  # hand must be non-empty when called
    return best_idx
