from typing import List, Tuple
from .cards import (
    Card,
    effective_suit,
    is_right_bower,
    is_left_bower,
    rank_strength,
)

def trick_winner(
    plays: List[Tuple[int, Card]],
    trump_suit: str,
    trump_mode: str = "standard",
) -> int:
    """
    Determine which player wins a trick.

    plays: list of (player_index, card_played) in play order (0..3 index).
    trump_suit: "C","D","H","S"
    trump_mode: "standard", "high", "low"

    Returns: player_index of the trick winner.
    """
    if not plays:
        raise ValueError("No cards played in trick")

    # Lead card defines led suit (using effective suit logic)
    lead_player, lead_card = plays[0]
    led_suit = effective_suit(lead_card, trump_suit, trump_mode)

    trump_candidates = []
    led_suit_candidates = []

    for player_idx, card in plays:
        eff_suit = effective_suit(card, trump_suit, trump_mode)

        if eff_suit == trump_suit:
            trump_candidates.append((player_idx, card))
        elif eff_suit == led_suit:
            led_suit_candidates.append((player_idx, card))
        # Off-suit non-trump cannot win

    # If any trump was played → highest trump wins
    if trump_candidates:
        return _highest_trump(trump_candidates, trump_suit, trump_mode)

    # Otherwise highest card in led suit wins
    return _highest_in_suit(led_suit_candidates, led_suit, trump_suit, trump_mode)


def _highest_trump(trump_plays, trump_suit, trump_mode):
    """
    Determine highest trump card based on trump mode.
    """

    best_player = None
    best_value = None

    for player_idx, card in trump_plays:

        # STANDARD: bowers apply
        if trump_mode == "standard":
            if is_right_bower(card, trump_suit):
                value = (3, 2, 99)
            elif is_left_bower(card, trump_suit):
                value = (3, 1, 99)
            else:
                v = rank_strength(card, trump_suit, trump_mode)
                value = (2, 0, v)

        # HIGH or LOW: *no bowers*, rank decides everything
        else:
            v = rank_strength(card, trump_suit, trump_mode)
            value = (1, 0, v)

        if best_value is None or value > best_value:
            best_value = value
            best_player = player_idx

    return best_player


def _highest_in_suit(
    suit_plays: List[Tuple[int, Card]],
    suit: str,
    trump_suit: str,
    trump_mode: str,
) -> int:
    """
    Choose highest card among those matching led suit (effective suit).
    """

    best_player = None
    best_rank = None

    for player_idx, card in suit_plays:

        if effective_suit(card, trump_suit, trump_mode) != suit:
            continue

        r = rank_strength(card, trump_suit, trump_mode)

        if best_rank is None or r > best_rank:
            best_rank = r
            best_player = player_idx

    # Should not happen, but fallback for safety
    if best_player is None:
        return suit_plays[0][0]

    return best_player
