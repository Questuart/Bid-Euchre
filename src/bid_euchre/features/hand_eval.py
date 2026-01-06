from typing import Any, Dict, List, Optional

from ..core.cards import (
    Card,
    effective_suit,
    is_left_bower,
    is_right_bower,
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
    Extract comprehensive features describing the hand.

    contract_type:
        "suit" : suit-contract with a trump suit and bowers.
        "high" : high no-trump (A high, no bowers).
        "low"  : low no-trump (T high, A low, no bowers).

    Returns a dict with 40+ features covering:
        - Trump strength (suit contracts only)
        - Offsuit control
        - Distribution (voids, suit lengths)
        - High/Low specific features
    """
    from collections import Counter

    if contract_type == "suit" and trump_suit is None:
        raise ValueError("trump_suit must be provided for 'suit' contracts")

    # ===========================
    # Initialize Counters
    # ===========================

    # Legacy features (keep for backward compatibility)
    bowers = 0
    trump_count = 0
    offsuit_aces = 0
    high_offsuit = 0
    rank_sum = 0

    # Trump features (suit contracts only)
    trump_rb_count = 0
    trump_lb_count = 0
    trump_ace_count = 0
    trump_king_count = 0
    trump_queen_count = 0
    trump_ten_count = 0
    trump_ranks = []  # List of trump rank values for top-3 calculation
    trump_rank_counts = Counter()  # For duplicate pairs

    # Offsuit control
    offsuit_king_count_total = 0
    offsuit_queen_count_total = 0
    offsuit_by_suit = {"C": [], "D": [], "H": [], "S": []}  # Track cards by suit

    # High/Low card counts (all contracts)
    high_card_count = 0  # Aces + Kings
    low_card_count = 0   # Jacks + Tens

    # ===========================
    # First Pass: Categorize Cards
    # ===========================

    for card in hand:
        # Legacy rank_sum (keep for compatibility)
        rv = rank_strength(card, contract_type) + 1
        rank_sum += rv

        # High/Low card counts
        if card.rank in ("A", "K"):
            high_card_count += 1
        if card.rank in ("J", "T"):
            low_card_count += 1

        if contract_type == "suit":
            eff_suit = effective_suit(card, trump_suit, contract_type)

            # Categorize as trump or offsuit
            if eff_suit == trump_suit:
                # TRUMP CARDS
                trump_count += 1

                # Right bower
                if is_right_bower(card, trump_suit):
                    trump_rb_count += 1
                    bowers += 1
                    trump_ranks.append(6)  # RB = 6
                    trump_rank_counts[6] += 1
                # Left bower
                elif is_left_bower(card, trump_suit):
                    trump_lb_count += 1
                    bowers += 1
                    trump_ranks.append(5)  # LB = 5
                    trump_rank_counts[5] += 1
                # Regular trump cards
                elif card.rank == "A":
                    trump_ace_count += 1
                    trump_ranks.append(4)
                    trump_rank_counts[4] += 1
                elif card.rank == "K":
                    trump_king_count += 1
                    trump_ranks.append(3)
                    trump_rank_counts[3] += 1
                elif card.rank == "Q":
                    trump_queen_count += 1
                    trump_ranks.append(2)
                    trump_rank_counts[2] += 1
                elif card.rank == "T":
                    trump_ten_count += 1
                    trump_ranks.append(1)
                    trump_rank_counts[1] += 1
            else:
                # OFFSUIT CARDS
                offsuit_by_suit[card.suit].append(card)

                if card.rank == "A":
                    offsuit_aces += 1
                elif card.rank == "K":
                    offsuit_king_count_total += 1
                    high_offsuit += 1
                elif card.rank == "Q":
                    offsuit_queen_count_total += 1
                    high_offsuit += 1
                elif card.rank == "J":
                    high_offsuit += 1
                elif card.rank == "T":
                    high_offsuit += 1
        else:
            # HIGH / LOW contracts - all cards are "offsuit"
            offsuit_by_suit[card.suit].append(card)

            if card.rank == "A":
                offsuit_aces += 1
            elif card.rank == "K":
                offsuit_king_count_total += 1
                high_offsuit += 1
            elif card.rank == "Q":
                offsuit_queen_count_total += 1
                high_offsuit += 1
            elif card.rank == "J":
                high_offsuit += 1
            elif card.rank == "T":
                high_offsuit += 1

    # ===========================
    # Trump Features (Suit Contracts)
    # ===========================

    top_trump_count = trump_rb_count + trump_lb_count + trump_ace_count

    # Top 3 trump ranks (sorted descending, pad with 0s)
    trump_ranks_sorted = sorted(trump_ranks, reverse=True)
    highest_trump_rank = trump_ranks_sorted[0] if len(trump_ranks_sorted) > 0 else 0
    second_highest_trump_rank = trump_ranks_sorted[1] if len(trump_ranks_sorted) > 1 else 0
    third_highest_trump_rank = trump_ranks_sorted[2] if len(trump_ranks_sorted) > 2 else 0

    # Trump power
    trump_power_sum = sum(trump_ranks)
    trump_power_avg = trump_power_sum / max(trump_count, 1)

    # Trump duplicate pairs (count of ranks with exactly 2 cards)
    trump_duplicate_pairs = sum(1 for count in trump_rank_counts.values() if count == 2)

    # Top trump sum
    top_trump_sum = bowers + trump_ace_count

    # ===========================
    # Offsuit Control Features
    # ===========================

    offsuit_suits_with_ace = 0
    offsuit_suits_with_double_ace = 0
    offsuit_suits_with_ace_and_king = 0

    for suit, cards in offsuit_by_suit.items():
        ace_count = sum(1 for c in cards if c.rank == "A")
        king_count = sum(1 for c in cards if c.rank == "K")

        if ace_count >= 1:
            offsuit_suits_with_ace += 1
        if ace_count == 2:
            offsuit_suits_with_double_ace += 1
        if ace_count >= 1 and king_count >= 1:
            offsuit_suits_with_ace_and_king += 1

    # ===========================
    # Distribution Features
    # ===========================

    # Suit lengths (for all 4 suits)
    suit_lengths = [len(cards) for cards in offsuit_by_suit.values()]
    suit_lengths_sorted = sorted(suit_lengths, reverse=True)

    max_suit_len = suit_lengths_sorted[0] if len(suit_lengths_sorted) > 0 else 0
    second_suit_len = suit_lengths_sorted[1] if len(suit_lengths_sorted) > 1 else 0
    third_suit_len = suit_lengths_sorted[2] if len(suit_lengths_sorted) > 2 else 0
    fourth_suit_len = suit_lengths_sorted[3] if len(suit_lengths_sorted) > 3 else 0

    void_count = sum(1 for length in suit_lengths if length == 0)
    num_singletons = sum(1 for length in suit_lengths if length == 1)
    num_doubletons = sum(1 for length in suit_lengths if length == 2)

    # Offsuit length 3+ count
    offsuit_length_3plus_count = sum(1 for length in suit_lengths if length >= 3)

    # Offsuit tens count
    offsuit_tens_count = sum(
        1 for cards in offsuit_by_suit.values()
        for c in cards if c.rank == "T"
    )

    # Best and second-best offsuit rank sums
    offsuit_rank_sums = []
    for suit, cards in offsuit_by_suit.items():
        suit_rank_sum = sum(rank_strength(c, contract_type) + 1 for c in cards)
        offsuit_rank_sums.append(suit_rank_sum)

    offsuit_rank_sums_sorted = sorted(offsuit_rank_sums, reverse=True)
    offsuit_best_rank_sum = offsuit_rank_sums_sorted[0] if len(offsuit_rank_sums_sorted) > 0 else 0
    offsuit_secondbest_rank_sum = offsuit_rank_sums_sorted[1] if len(offsuit_rank_sums_sorted) > 1 else 0

    # ===========================
    # High/Low Specific Features
    # ===========================

    # Double-ten-jack count: suits with 2 tens AND at least 1 jack
    double_ten_jack_count = 0
    for suit, cards in offsuit_by_suit.items():
        ten_count = sum(1 for c in cards if c.rank == "T")
        jack_count = sum(1 for c in cards if c.rank == "J")
        if ten_count == 2 and jack_count >= 1:
            double_ten_jack_count += 1

    # Interaction terms (only meaningful for suit contracts)
    trump_count_x_void_count = trump_count * void_count if contract_type == "suit" else 0
    trump_count_x_offsuit_ace = trump_count * offsuit_aces if contract_type == "suit" else 0

    # Hand Value (used for OLSa HV / OLSa SR)
    hand_value = score_hand_scalar(hand, contract_type, trump_suit)
    # Special adjustment for Low: use fixed offsuit weights if requested by user logic
    # Actually, score_hand_scalar uses rank_strength which is already inverted for Low.
    # To match the user's "offsuit weights" request for LOW (where A=50, T=10):
    if contract_type == "low":
        hand_value_fixed = 0
        weights_fixed = {"A": 50, "K": 40, "Q": 30, "J": 20, "T": 10}
        for card in hand:
            hand_value_fixed += weights_fixed.get(card.rank, 0)
        hand_value = hand_value_fixed

    # ===========================
    # Return Feature Dictionary
    # ===========================

    return {
        # Legacy features (backward compatibility)
        "bowers": bowers,
        "trump_count": trump_count,
        "offsuit_aces": offsuit_aces,
        "high_offsuit": high_offsuit,
        "rank_sum": rank_sum,
        "hand_value": hand_value,

        # Trump features (suit contracts)
        "trump_rb_count": trump_rb_count,
        "trump_lb_count": trump_lb_count,
        "trump_ace_count": trump_ace_count,
        "trump_king_count": trump_king_count,
        "trump_queen_count": trump_queen_count,
        "trump_ten_count": trump_ten_count,
        "top_trump_count": top_trump_count,
        "highest_trump_rank": highest_trump_rank,
        "second_highest_trump_rank": second_highest_trump_rank,
        "third_highest_trump_rank": third_highest_trump_rank,
        "trump_power_sum": trump_power_sum,
        "trump_power_avg": trump_power_avg,
        "trump_duplicate_pairs": trump_duplicate_pairs,
        "top_trump_sum": top_trump_sum,

        # Offsuit control
        "offsuit_king_count_total": offsuit_king_count_total,
        "offsuit_queen_count_total": offsuit_queen_count_total,
        "offsuit_suits_with_ace": offsuit_suits_with_ace,
        "offsuit_suits_with_double_ace": offsuit_suits_with_double_ace,
        "offsuit_suits_with_ace_and_king": offsuit_suits_with_ace_and_king,

        # Distribution features
        "void_count": void_count,
        "max_suit_len": max_suit_len,
        "second_suit_len": second_suit_len,
        "third_suit_len": third_suit_len,
        "fourth_suit_len": fourth_suit_len,
        "num_singletons": num_singletons,
        "num_doubletons": num_doubletons,
        "offsuit_tens_count": offsuit_tens_count,
        "offsuit_length_3plus_count": offsuit_length_3plus_count,
        "offsuit_best_rank_sum": offsuit_best_rank_sum,
        "offsuit_secondbest_rank_sum": offsuit_secondbest_rank_sum,

        # High/Low specific
        "double_ten_jack_count": double_ten_jack_count,
        "high_card_count": high_card_count,
        "low_card_count": low_card_count,
        "trump_count_x_void_count": trump_count_x_void_count,
        "trump_count_x_offsuit_ace": trump_count_x_offsuit_ace,
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

        # Uniform spacing (10 points per rank difference)
        weights_trump = {
            "A": 100,
            "K": 90,
            "Q": 80,
            "J": 70,
            "T": 60,
        }

        weights_offsuit = {
            "A": 50,
            "K": 40,
            "Q": 30,
            "J": 20,
            "T": 10,
        }

        for card in hand:
            eff_suit = effective_suit(card, trump_suit, contract_type)

            # Bowers override everything (must be higher than any regular trump)
            if is_right_bower(card, trump_suit):
                score += 120
                continue
            if is_left_bower(card, trump_suit):
                score += 110
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
