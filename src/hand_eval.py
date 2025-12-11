from typing import Dict, Any, Optional, List
from .cards import (
    Card,
    is_right_bower,
    is_left_bower,
    effective_suit,
    rank_strength,
)


# ===========================
#  FEATURE EXTRACTION
# ===========================

def get_hand_features(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract raw features describing the hand.

    contract_type:
        "suit" : suit-contract with a trump suit and bowers.
        "high" : high no-trump (A high, no bowers).
        "low"  : low no-trump (T high, A low, no bowers).

    Returns a dict:
        {
            "bowers": int,
            "trump_count": int,   # only nonzero in suit contracts
            "offsuit_aces": int,
            "high_offsuit": int,
            "rank_sum": int,      # rough measure of total rank strength
        }
    """

    bowers = 0
    trump_count = 0
    offsuit_aces = 0
    high_offsuit = 0
    rank_sum = 0

    for card in hand:
        # rank_strength is 0..4; add 1 so ranksum isn't full of zeros
        rv = rank_strength(card, contract_type) + 1
        rank_sum += rv

        if contract_type == "suit":
            if trump_suit is None:
                raise ValueError("trump_suit must be provided for 'suit' contracts")

            eff_suit = effective_suit(card, trump_suit, contract_type)

            # Bowers
            if is_right_bower(card, trump_suit) or is_left_bower(card, trump_suit):
                bowers += 1

            # Trump count
            if eff_suit == trump_suit:
                trump_count += 1
            else:
                # Offsuit aces & high offsuit cards
                if card.rank == "A":
                    offsuit_aces += 1
                if card.rank in ("K", "Q", "J", "T"):
                    high_offsuit += 1

        else:
            # HIGH / LOW no-trump: no bowers, no trump suit
            if card.rank == "A":
                offsuit_aces += 1
            if card.rank in ("K", "Q", "J", "T"):
                high_offsuit += 1

    return {
        "bowers": bowers,
        "trump_count": trump_count,
        "offsuit_aces": offsuit_aces,
        "high_offsuit": high_offsuit,
        "rank_sum": rank_sum,
    }


# ===========================
#  OPTION A: SCALAR SCORE
# ===========================

def score_hand_scalar(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str] = None,
) -> int:
    """
    A simple monotonic scalar hand score.

    Used ONLY for debugging / sanity checks / visualization.
    Not used directly for strategy or bidding.
    """

    score = 0

    if contract_type == "suit":
        if trump_suit is None:
            raise ValueError("trump_suit must be provided for 'suit' contracts")

        # Large gaps ensure strict ordering for trump vs offsuit
        weights_trump = {
            "A": 80,
            "K": 70,
            "Q": 60,
            "J": 50,
            "T": 40,
        }

        weights_offsuit = {
            "A": 30,
            "K": 20,
            "Q": 10,
            "J": 5,
            "T": 1,
        }

        for card in hand:
            eff_suit = effective_suit(card, trump_suit, contract_type)

            # Bowers override everything
            if is_right_bower(card, trump_suit):
                score += 100
                continue
            if is_left_bower(card, trump_suit):
                score += 90
                continue

            # Trump cards
            if eff_suit == trump_suit:
                score += weights_trump.get(card.rank, 0)
            else:
                score += weights_offsuit.get(card.rank, 0)

    elif contract_type in ("high", "low"):
        # No trump: all suits are symmetric.
        # Use rank_strength as the base and exaggerate differences a bit.
        for card in hand:
            r = rank_strength(card, contract_type)  # 0..4
            score += (r + 1) * 10  # simple monotone weighting

    else:
        raise ValueError(f"Unknown contract_type: {contract_type}")

    return score


# ===========================
#  OPTION B: TUPLE SCORE
# ===========================

def score_hand_tuple(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str] = None,
):
    """
    Transparent lexicographic scoring.

    For use in sorting/grouping hands when you want interpretability instead of
    a single scalar.

    Returns:
        (bowers, trump_count, offsuit_aces, high_offsuit, rank_sum)
    """
    f = get_hand_features(hand, contract_type, trump_suit)
    return (
        f["bowers"],
        f["trump_count"],
        f["offsuit_aces"],
        f["high_offsuit"],
        f["rank_sum"],
    )


# ===========================
#  MAIN ENTRY POINT (CHOOSE MODE)
# ===========================

def score_hand(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str] = None,
    mode: str = "scalar",
):
    """
    Public scoring API.

    mode:
        "scalar" → score_hand_scalar
        "tuple"  → score_hand_tuple
    """
    if mode == "scalar":
        return score_hand_scalar(hand, contract_type, trump_suit)
    elif mode == "tuple":
        return score_hand_tuple(hand, contract_type, trump_suit)
    else:
        raise ValueError(f"Unknown hand scoring mode: {mode}")
