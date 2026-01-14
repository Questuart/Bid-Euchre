"""
Bidless Hand Feature Extractor v1 (Deterministic)

Extracts features from a 10-card hand AFTER the bidding phase (contract is known).
Used for value model training to predict trick outcomes.

Key requirements:
- Deterministic: same input always produces same output
- Stable ordering: features always appear in the same order
- Schema versioned: includes version marker for forward compatibility

Feature categories:
- Hand composition (by rank)
- Trump strength (suit contracts only)
- Offsuit control and distribution
- Seat context (dealer, leader positions)
"""

from typing import Dict, List, Optional, Tuple

from ..core.cards import Card, effective_suit, is_left_bower, is_right_bower

# Schema version for feature compatibility tracking
BIDLESS_FEATURES_SCHEMA_VERSION = "v1"


def extract_bidless_hand_features(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str] = None,
    dealer_seat: Optional[int] = None,
    leader_seat: Optional[int] = None,
) -> Dict[str, float]:
    """
    Extract features from a bidless hand for value model training.

    Args:
        hand: List of 10 cards in the player's hand
        contract_type: "suit", "high", or "low"
        trump_suit: Trump suit (required for "suit" contracts, None otherwise)
        dealer_seat: Seat index of the dealer (0-3), or None if unknown
        leader_seat: Seat index of the leader (0-3), or None if unknown

    Returns:
        Dictionary mapping feature names to numeric values, in stable order.
        Includes schema_version marker for compatibility tracking.

    Raises:
        ValueError: if contract_type is "suit" but trump_suit is None
    """
    if contract_type == "suit" and trump_suit is None:
        raise ValueError("trump_suit must be provided for 'suit' contracts")

    # Initialize feature dict with explicit ordering (Python 3.7+ dicts maintain insertion order)
    features: Dict[str, float] = {}

    # Schema version (for compatibility tracking)
    features["schema_version_marker"] = 1.0  # v1 = 1.0

    # ===========================
    # Hand Composition Features
    # ===========================
    # Count cards by rank (explicit order: A, K, Q, J, T)
    features["count_aces"] = float(sum(1 for c in hand if c.rank == "A"))
    features["count_kings"] = float(sum(1 for c in hand if c.rank == "K"))
    features["count_queens"] = float(sum(1 for c in hand if c.rank == "Q"))
    features["count_jacks"] = float(sum(1 for c in hand if c.rank == "J"))
    features["count_tens"] = float(sum(1 for c in hand if c.rank == "T"))

    # ===========================
    # Trump Features (Suit Contracts Only)
    # ===========================
    if contract_type == "suit":
        trump_count = 0
        has_right_bower = 0.0
        has_left_bower = 0.0
        trump_aces = 0
        trump_kings = 0
        trump_queens = 0
        trump_tens = 0

        for card in hand:
            eff_suit = effective_suit(card, trump_suit, contract_type)
            if eff_suit == trump_suit:
                trump_count += 1
                if is_right_bower(card, trump_suit):
                    has_right_bower = 1.0
                elif is_left_bower(card, trump_suit):
                    has_left_bower = 1.0
                elif card.rank == "A":
                    trump_aces += 1
                elif card.rank == "K":
                    trump_kings += 1
                elif card.rank == "Q":
                    trump_queens += 1
                elif card.rank == "T":
                    trump_tens += 1

        features["trump_count"] = float(trump_count)
        features["has_right_bower"] = has_right_bower
        features["has_left_bower"] = has_left_bower
        features["trump_aces"] = float(trump_aces)
        features["trump_kings"] = float(trump_kings)
        features["trump_queens"] = float(trump_queens)
        features["trump_tens"] = float(trump_tens)
    else:
        # High/Low contracts: no trump, set all to 0
        features["trump_count"] = 0.0
        features["has_right_bower"] = 0.0
        features["has_left_bower"] = 0.0
        features["trump_aces"] = 0.0
        features["trump_kings"] = 0.0
        features["trump_queens"] = 0.0
        features["trump_tens"] = 0.0

    # ===========================
    # Offsuit Distribution Features
    # ===========================
    # Group cards by suit (effective suit for suit contracts, literal suit for high/low)
    suit_lengths: Dict[str, int] = {"C": 0, "D": 0, "H": 0, "S": 0}

    for card in hand:
        if contract_type == "suit":
            eff_suit = effective_suit(card, trump_suit, contract_type)
            # Don't count trump cards in offsuit distribution
            if eff_suit != trump_suit:
                suit_lengths[card.suit] += 1
        else:
            # High/Low: use literal suit
            suit_lengths[card.suit] += 1

    # Sort suit lengths for stable feature ordering (longest to shortest)
    sorted_lengths = sorted(suit_lengths.values(), reverse=True)

    features["longest_offsuit_length"] = float(sorted_lengths[0])
    features["second_longest_offsuit_length"] = float(sorted_lengths[1])
    features["third_longest_offsuit_length"] = float(sorted_lengths[2])
    features["shortest_offsuit_length"] = float(sorted_lengths[3])

    # Count voids and singletons
    features["void_count"] = float(sum(1 for length in suit_lengths.values() if length == 0))
    features["singleton_count"] = float(sum(1 for length in suit_lengths.values() if length == 1))

    # ===========================
    # Offsuit Control Features
    # ===========================
    # Count offsuit aces (for suit contracts) or all aces (for high/low)
    if contract_type == "suit":
        offsuit_aces = 0
        offsuit_kings = 0
        for card in hand:
            eff_suit = effective_suit(card, trump_suit, contract_type)
            if eff_suit != trump_suit:
                if card.rank == "A":
                    offsuit_aces += 1
                elif card.rank == "K":
                    offsuit_kings += 1
        features["offsuit_aces"] = float(offsuit_aces)
        features["offsuit_kings"] = float(offsuit_kings)
    else:
        # High/Low: all cards are "offsuit"
        features["offsuit_aces"] = float(features["count_aces"])
        features["offsuit_kings"] = float(features["count_kings"])

    # ===========================
    # Seat Context Features
    # ===========================
    # One-hot encode dealer position (0-3, or -1 if unknown)
    # This helps model learn positional advantages
    features["is_dealer_seat_0"] = 1.0 if dealer_seat == 0 else 0.0
    features["is_dealer_seat_1"] = 1.0 if dealer_seat == 1 else 0.0
    features["is_dealer_seat_2"] = 1.0 if dealer_seat == 2 else 0.0
    features["is_dealer_seat_3"] = 1.0 if dealer_seat == 3 else 0.0
    features["dealer_seat_unknown"] = 1.0 if dealer_seat is None else 0.0

    # One-hot encode leader position (0-3, or -1 if unknown)
    features["is_leader_seat_0"] = 1.0 if leader_seat == 0 else 0.0
    features["is_leader_seat_1"] = 1.0 if leader_seat == 1 else 0.0
    features["is_leader_seat_2"] = 1.0 if leader_seat == 2 else 0.0
    features["is_leader_seat_3"] = 1.0 if leader_seat == 3 else 0.0
    features["leader_seat_unknown"] = 1.0 if leader_seat is None else 0.0

    return features


def get_feature_names() -> List[str]:
    """
    Return the stable, ordered list of feature names.

    This list is deterministic and matches the order of features
    returned by extract_bidless_hand_features().

    Returns:
        List of feature names in extraction order
    """
    return [
        # Schema version
        "schema_version_marker",
        # Hand composition (by rank)
        "count_aces",
        "count_kings",
        "count_queens",
        "count_jacks",
        "count_tens",
        # Trump features (suit contracts)
        "trump_count",
        "has_right_bower",
        "has_left_bower",
        "trump_aces",
        "trump_kings",
        "trump_queens",
        "trump_tens",
        # Offsuit distribution
        "longest_offsuit_length",
        "second_longest_offsuit_length",
        "third_longest_offsuit_length",
        "shortest_offsuit_length",
        "void_count",
        "singleton_count",
        # Offsuit control
        "offsuit_aces",
        "offsuit_kings",
        # Seat context (dealer)
        "is_dealer_seat_0",
        "is_dealer_seat_1",
        "is_dealer_seat_2",
        "is_dealer_seat_3",
        "dealer_seat_unknown",
        # Seat context (leader)
        "is_leader_seat_0",
        "is_leader_seat_1",
        "is_leader_seat_2",
        "is_leader_seat_3",
        "leader_seat_unknown",
    ]


def extract_feature_vector(
    hand: List[Card],
    contract_type: str,
    trump_suit: Optional[str] = None,
    dealer_seat: Optional[int] = None,
    leader_seat: Optional[int] = None,
) -> Tuple[List[float], List[str]]:
    """
    Extract features as a fixed-order numeric vector.

    This is a convenience wrapper around extract_bidless_hand_features()
    that returns features as a list instead of a dict, for direct use
    in ML frameworks.

    Args:
        hand: List of 10 cards
        contract_type: "suit", "high", or "low"
        trump_suit: Trump suit (required for "suit")
        dealer_seat: Dealer position (0-3 or None)
        leader_seat: Leader position (0-3 or None)

    Returns:
        Tuple of (feature_values, feature_names)
        - feature_values: List of numeric feature values in stable order
        - feature_names: List of feature names matching the values
    """
    features_dict = extract_bidless_hand_features(
        hand, contract_type, trump_suit, dealer_seat, leader_seat
    )
    feature_names = get_feature_names()

    # Extract values in the stable order defined by get_feature_names()
    feature_values = [features_dict[name] for name in feature_names]

    return feature_values, feature_names
