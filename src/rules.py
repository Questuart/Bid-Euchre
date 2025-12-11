from typing import List, Tuple, Optional
from .cards import (
    Card,
    effective_suit,
    is_right_bower,
    is_left_bower,
    rank_strength,
)


def trick_winner(
    plays: List[Tuple[int, Card]],
    contract_type: str,
    trump_suit: Optional[str] = None,
) -> int:
    """
    Determine which player wins a trick.

    plays: list of (player_index, card_played) in play order (0..3 index).
    contract_type: "suit", "high", or "low"
    trump_suit: "C","D","H","S" for "suit" contracts; None for "high"/"low".

    Returns: player_index of the trick winner.
    """
    if not plays:
        raise ValueError("No cards played in trick")

    # Lead card defines led suit (using effective suit logic)
    lead_player, lead_card = plays[0]
    led_suit = effective_suit(lead_card, trump_suit, contract_type)

    trump_candidates: List[Tuple[int, Card]] = []
    led_suit_candidates: List[Tuple[int, Card]] = []

    for player_idx, card in plays:
        eff_suit = effective_suit(card, trump_suit, contract_type)

        # For suit contracts, we consider trump suit
        if contract_type == "suit" and trump_suit is not None and eff_suit == trump_suit:
            trump_candidates.append((player_idx, card))

        if eff_suit == led_suit:
            led_suit_candidates.append((player_idx, card))

    # SUIT CONTRACT: if any trump was played, highest trump wins
    if contract_type == "suit" and trump_suit is not None and trump_candidates:
        return _highest_trump(trump_candidates, trump_suit)

    # Otherwise, highest card in led suit wins (for suit, high, or low)
    return _highest_in_suit(led_suit_candidates, contract_type)


def _highest_trump(
    trump_plays: List[Tuple[int, Card]],
    trump_suit: str,
) -> int:
    """
    Determine highest trump card in a SUIT contract.

    Ordering:
      Right bower (J of trump)
      Left bower  (J of same-color suit)
      A K Q J T (other trump ranks)
    """
    best_player: Optional[int] = None
    best_value = None

    for player_idx, card in trump_plays:
        if is_right_bower(card, trump_suit):
            value = (3, 2, 99)
        elif is_left_bower(card, trump_suit):
            value = (3, 1, 99)
        else:
            # other trumps: use suit-contract ordering
            v = rank_strength(card, "suit")
            value = (2, 0, v)

        if best_value is None or value > best_value:
            best_value = value
            best_player = player_idx

    assert best_player is not None
    return best_player


def _highest_in_suit(
    suit_plays: List[Tuple[int, Card]],
    contract_type: str,
) -> int:
    """
    Choose highest card among those that match the led suit.

    For all contract types, we assume suit_plays already only contains
    cards whose effective_suit == led_suit, so we just compare ranks.
    """
    if not suit_plays:
        raise ValueError("No cards following led suit")

    best_player = None
    best_rank_val = None

    for player_idx, card in suit_plays:
        r = rank_strength(card, contract_type)
        if best_rank_val is None or r > best_rank_val:
            best_rank_val = r
            best_player = player_idx

    assert best_player is not None
    return best_player
