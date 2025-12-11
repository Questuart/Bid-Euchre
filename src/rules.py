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
) -> int:
    """
    Determine which player wins a trick.

    plays: list of (player_index, card_played) in play order (0..3 index).
    trump_suit: "C","D","H","S"

    Returns: player_index of the trick winner.
    """
    if not plays:
        raise ValueError("No cards played in trick")

    # Lead card defines led suit (using effective suit logic)
    lead_player, lead_card = plays[0]
    led_suit = effective_suit(lead_card, trump_suit)

    trump_candidates = []
    led_suit_candidates = []

    for player_idx, card in plays:
        eff_suit = effective_suit(card, trump_suit)

        if eff_suit == trump_suit:
            trump_candidates.append((player_idx, card))
        elif eff_suit == led_suit:
            led_suit_candidates.append((player_idx, card))
        # Anything off-suit and non-trump cannot win

    # If any trump was played, highest trump wins
    if trump_candidates:
        return _highest_trump(trump_candidates, trump_suit)

    # Otherwise, highest card in led suit wins
    return _highest_in_suit(led_suit_candidates, led_suit, trump_suit)


def _highest_trump(
    trump_plays: List[Tuple[int, Card]],
    trump_suit: str,
) -> int:
    """
    Given only trump cards, decide winner using Euchre ordering:
    Right bower (J of trump) > Left bower (J of same color) > A K Q J T.
    (Rank order comes from rank_strength in cards.py.)
    """
    best_player = None
    best_score = None

    for player_idx, card in trump_plays:
        if is_right_bower(card, trump_suit):
            score = (3, 2, 99)  # top tier
        elif is_left_bower(card, trump_suit):
            score = (3, 1, 99)  # next tier
        else:
            # Other trumps: compare by rank (T < J < Q < K < A)
            score = (2, 0, rank_strength(card.rank))

        if best_score is None or score > best_score:
            best_score = score
            best_player = player_idx

    assert best_player is not None
    return best_player


def _highest_in_suit(
    suit_plays: List[Tuple[int, Card]],
    suit: str,
    trump_suit: str,
) -> int:
    """
    Choose highest card among those that effectively match the led suit.
    (We won't ever see trump here, by construction in trick_winner.)
    """
    best_player = None
    best_rank = None

    for player_idx, card in suit_plays:
        if effective_suit(card, trump_suit) != suit:
            continue

        rs = rank_strength(card.rank)
        if best_rank is None or rs > best_rank:
            best_rank = rs
            best_player = player_idx

    # Fallback: if somehow empty, give to first player who followed suit
    if best_player is None:
        return suit_plays[0][0]

    return best_player
