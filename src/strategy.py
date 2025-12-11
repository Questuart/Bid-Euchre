from typing import List, Tuple, Optional
from .cards import Card, effective_suit, rank_strength

def choose_card_basic(
    hand: List[Card],
    plays_so_far: List[Tuple[int, Card]],
    trump_suit: str,
    trump_mode: str,
    player_index: int,
) -> int:
    """
    Very simple bot:
    - If you can follow the led suit, play your lowest-ranked card in that suit.
    - If you cannot follow suit, play your lowest-ranked card overall.

    Returns: the INDEX in `hand` of the chosen card.
    """

    # Determine led suit
    if plays_so_far:
        _, lead_card = plays_so_far[0]
        led_suit = effective_suit(lead_card, trump_suit, trump_mode)
    else:
        led_suit = None

    # First attempt to follow suit
    best_idx: Optional[int] = None
    best_rank: Optional[int] = None

    if led_suit is not None:
        for i, c in enumerate(hand):
            if effective_suit(c, trump_suit, trump_mode) == led_suit:
                r = rank_strength(c, trump_suit, trump_mode)
                if best_rank is None or r < best_rank:
                    best_rank = r
                    best_idx = i

        # If we found a legal follow-suit card, play it
        if best_idx is not None:
            return best_idx

    # Otherwise: discard the lowest-ranked card in the hand
    best_idx = None
    best_rank = None

    for i, c in enumerate(hand):
        r = rank_strength(c, trump_suit, trump_mode)
        if best_rank is None or r < best_rank:
            best_rank = r
            best_idx = i

    assert best_idx is not None
    return best_idx
