from .cards import (
    Card,
    is_right_bower,
    is_left_bower,
    effective_suit
)


# ===========================
#  FEATURE EXTRACTION
# ===========================

def get_hand_features(hand, trump_suit):
    """
    Extract raw features that describe the hand.
    These are used for tuple scoring and later regression analysis.
    
    Returns a dict:
        {
            "bowers": int,
            "trump_count": int,
            "offsuit_aces": int,
            "high_offsuit": int,
            "rank_sum": int,
        }
    """
    bowers = 0
    trump_count = 0
    offsuit_aces = 0
    high_offsuit = 0  # K/Q/J/T outside trump
    rank_sum = 0      # Rough power measure (T=1, J=2, Q=3, K=4, A=5)

    rank_value = {"T": 1, "J": 2, "Q": 3, "K": 4, "A": 5}

    for card in hand:
        eff_suit = effective_suit(card, trump_suit)
        rv = rank_value[card.rank]
        rank_sum += rv

        # Bowers
        if is_right_bower(card, trump_suit):
            bowers += 1
        elif is_left_bower(card, trump_suit):
            bowers += 1

        # Trump count
        if eff_suit == trump_suit:
            trump_count += 1
        else:
            # Offsuit Aces
            if card.rank == "A":
                offsuit_aces += 1

            # High offsuit cards
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

def score_hand_scalar(hand, trump_suit):
    """
    A simple monotonic scalar hand score.
    Used ONLY for debugging, visualization, and sanity checks.
    Not used for strategy.
    """

    score = 0

    # Large gaps ensure strict ordering
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
        eff_suit = effective_suit(card, trump_suit)

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

    return score



# ===========================
#  OPTION B: TUPLE SCORE
# ===========================

def score_hand_tuple(hand, trump_suit):
    """
    Transparent lexicographic scoring.
    Returns a tuple where larger = stronger.
    
    Format:
        (bowers, trump_count, offsuit_aces, high_offsuit, rank_sum)
    """
    f = get_hand_features(hand, trump_suit)
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

def score_hand(hand, trump_suit, mode="scalar"):
    """
    Public scoring API.
    
    mode:
        "scalar" → score_hand_scalar
        "tuple"  → score_hand_tuple
    """
    if mode == "scalar":
        return score_hand_scalar(hand, trump_suit)
    elif mode == "tuple":
        return score_hand_tuple(hand, trump_suit)
    else:
        raise ValueError(f"Unknown hand scoring mode: {mode}")
