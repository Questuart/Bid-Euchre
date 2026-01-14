"""
Unit tests for bidless hand feature extraction (v1).

Tests cover:
- Deterministic output for same input
- Schema version marker presence
- Feature name stability
- All contract types (suit, high, low)
- Seat context encoding
- Edge cases (empty hands, all trump, etc.)
"""

import pytest

from bid_euchre.core.cards import Card
from bid_euchre.features.bidless_hand_features import (
    BIDLESS_FEATURES_SCHEMA_VERSION,
    extract_bidless_hand_features,
    extract_feature_vector,
    get_feature_names,
)

# ============================================================================
# Feature Name Stability Tests
# ============================================================================


def test_get_feature_names_returns_stable_list():
    """Feature names list should be deterministic and stable."""
    names1 = get_feature_names()
    names2 = get_feature_names()

    # Same call returns same list
    assert names1 == names2

    # Schema version marker should be first
    assert names1[0] == "schema_version_marker"

    # No duplicates
    assert len(names1) == len(set(names1))


def test_feature_names_expected_count():
    """We expect 31 features in v1."""
    names = get_feature_names()
    # 1 schema + 5 rank counts + 7 trump + 6 offsuit dist + 2 offsuit control + 5 dealer + 5 leader = 31
    assert len(names) == 31


def test_feature_names_order_stability():
    """Feature names should appear in documented order."""
    names = get_feature_names()

    # Schema first
    assert names[0] == "schema_version_marker"

    # Rank counts next (A, K, Q, J, T)
    assert names[1:6] == [
        "count_aces",
        "count_kings",
        "count_queens",
        "count_jacks",
        "count_tens",
    ]

    # Trump features
    assert names[6:13] == [
        "trump_count",
        "has_right_bower",
        "has_left_bower",
        "trump_aces",
        "trump_kings",
        "trump_queens",
        "trump_tens",
    ]

    # Offsuit distribution
    assert names[13:19] == [
        "longest_offsuit_length",
        "second_longest_offsuit_length",
        "third_longest_offsuit_length",
        "shortest_offsuit_length",
        "void_count",
        "singleton_count",
    ]

    # Offsuit control
    assert names[19:21] == [
        "offsuit_aces",
        "offsuit_kings",
    ]

    # Dealer seat context
    assert names[21:26] == [
        "is_dealer_seat_0",
        "is_dealer_seat_1",
        "is_dealer_seat_2",
        "is_dealer_seat_3",
        "dealer_seat_unknown",
    ]

    # Leader seat context
    assert names[26:31] == [
        "is_leader_seat_0",
        "is_leader_seat_1",
        "is_leader_seat_2",
        "is_leader_seat_3",
        "leader_seat_unknown",
    ]


# ============================================================================
# Determinism Tests
# ============================================================================


def test_same_hand_produces_same_features():
    """Calling the function twice with the same input should produce identical output."""
    hand = [
        Card("H", "J"),  # Right bower
        Card("H", "A"),
        Card("H", "K"),
        Card("C", "A"),
        Card("C", "K"),
        Card("D", "A"),
        Card("D", "T"),
        Card("S", "Q"),
        Card("S", "T"),
        Card("S", "T"),
    ]

    features1 = extract_bidless_hand_features(
        hand, contract_type="suit", trump_suit="H", dealer_seat=0, leader_seat=1
    )
    features2 = extract_bidless_hand_features(
        hand, contract_type="suit", trump_suit="H", dealer_seat=0, leader_seat=1
    )

    assert features1 == features2


def test_feature_dict_order_is_stable():
    """Feature dict keys should maintain insertion order (Python 3.7+)."""
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(hand, contract_type="high")

    # Extract keys as list
    keys = list(features.keys())

    # Should match get_feature_names() order
    assert keys == get_feature_names()


# ============================================================================
# Schema Version Tests
# ============================================================================


def test_schema_version_marker_present():
    """All feature dicts should include schema version marker."""
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(hand, contract_type="high")

    assert "schema_version_marker" in features
    assert features["schema_version_marker"] == 1.0  # v1


def test_schema_version_constant_defined():
    """Schema version constant should be defined at module level."""
    assert BIDLESS_FEATURES_SCHEMA_VERSION == "v1"


# ============================================================================
# Contract Type Tests
# ============================================================================


def test_suit_contract_requires_trump_suit():
    """Suit contracts must specify trump_suit."""
    hand = [Card("H", "A")] * 10

    with pytest.raises(ValueError, match="trump_suit must be provided"):
        extract_bidless_hand_features(hand, contract_type="suit")


def test_high_contract_no_trump():
    """High contracts should have zero trump features."""
    hand = [Card("H", "J"), Card("D", "J")] + [Card("H", "A")] * 8

    features = extract_bidless_hand_features(hand, contract_type="high")

    assert features["trump_count"] == 0.0
    assert features["has_right_bower"] == 0.0
    assert features["has_left_bower"] == 0.0
    assert features["trump_aces"] == 0.0


def test_low_contract_no_trump():
    """Low contracts should have zero trump features."""
    hand = [Card("H", "J"), Card("D", "J")] + [Card("H", "A")] * 8

    features = extract_bidless_hand_features(hand, contract_type="low")

    assert features["trump_count"] == 0.0
    assert features["has_right_bower"] == 0.0
    assert features["has_left_bower"] == 0.0


def test_suit_contract_with_bowers():
    """Suit contracts should correctly identify bowers."""
    hand = [
        Card("H", "J"),  # Right bower (trump=H)
        Card("D", "J"),  # Left bower (same color)
        Card("H", "A"),
        Card("C", "A"),
        Card("C", "K"),
        Card("C", "Q"),
        Card("S", "A"),
        Card("S", "K"),
        Card("S", "Q"),
        Card("S", "T"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="suit", trump_suit="H")

    assert features["trump_count"] == 3.0  # RB + LB + HA
    assert features["has_right_bower"] == 1.0
    assert features["has_left_bower"] == 1.0
    assert features["trump_aces"] == 1.0  # HA
    assert features["trump_kings"] == 0.0
    assert features["trump_queens"] == 0.0


# ============================================================================
# Hand Composition Tests
# ============================================================================


def test_rank_counts_basic():
    """Test basic rank counting."""
    hand = [
        Card("H", "A"),
        Card("D", "A"),
        Card("C", "K"),
        Card("S", "Q"),
        Card("H", "J"),
        Card("D", "T"),
        Card("C", "T"),
        Card("S", "T"),
        Card("H", "T"),
        Card("D", "T"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="high")

    assert features["count_aces"] == 2.0
    assert features["count_kings"] == 1.0
    assert features["count_queens"] == 1.0
    assert features["count_jacks"] == 1.0
    assert features["count_tens"] == 5.0


def test_all_same_rank():
    """Test hand with all cards of same rank."""
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(hand, contract_type="high")

    assert features["count_aces"] == 10.0
    assert features["count_kings"] == 0.0
    assert features["count_queens"] == 0.0
    assert features["count_jacks"] == 0.0
    assert features["count_tens"] == 0.0


# ============================================================================
# Trump Features Tests (Suit Contracts)
# ============================================================================


def test_all_trump_hand():
    """Test hand with maximum trump cards."""
    hand = [
        Card("H", "J"),  # Right bower
        Card("D", "J"),  # Left bower
        Card("H", "A"),
        Card("H", "A"),  # Duplicate
        Card("H", "K"),
        Card("H", "Q"),
        Card("H", "T"),
        Card("H", "T"),
        Card("H", "T"),
        Card("H", "T"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="suit", trump_suit="H")

    assert features["trump_count"] == 10.0
    assert features["has_right_bower"] == 1.0
    assert features["has_left_bower"] == 1.0
    assert features["trump_aces"] == 2.0
    assert features["trump_kings"] == 1.0
    assert features["trump_queens"] == 1.0
    assert features["trump_tens"] == 4.0


def test_no_trump_cards_in_suit_contract():
    """Test suit contract with no trump cards (all offsuit)."""
    hand = [
        Card("C", "A"),
        Card("C", "K"),
        Card("D", "A"),
        Card("D", "K"),
        Card("S", "A"),
        Card("S", "K"),
        Card("S", "Q"),
        Card("S", "J"),  # Not left bower (different color)
        Card("C", "T"),
        Card("D", "T"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="suit", trump_suit="H")

    assert features["trump_count"] == 0.0
    assert features["has_right_bower"] == 0.0
    assert features["has_left_bower"] == 0.0
    assert features["trump_aces"] == 0.0


# ============================================================================
# Offsuit Distribution Tests
# ============================================================================


def test_void_counting():
    """Test void (zero-length suit) counting."""
    # All hearts (in high contract, no trump adjustment)
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(hand, contract_type="high")

    # 3 suits have zero cards
    assert features["void_count"] == 3.0
    assert features["singleton_count"] == 0.0
    assert features["longest_offsuit_length"] == 10.0
    assert features["shortest_offsuit_length"] == 0.0


def test_singleton_counting():
    """Test singleton (one-card suit) counting."""
    hand = [
        Card("H", "A"),  # 1 heart
        Card("D", "A"),  # 1 diamond
        Card("C", "A"),  # 1 club
        Card("S", "A"),
        Card("S", "K"),
        Card("S", "Q"),
        Card("S", "J"),
        Card("S", "T"),
        Card("S", "T"),
        Card("S", "T"),  # 7 spades
    ]

    features = extract_bidless_hand_features(hand, contract_type="high")

    assert features["void_count"] == 0.0
    assert features["singleton_count"] == 3.0  # H, D, C
    assert features["longest_offsuit_length"] == 7.0  # Spades
    assert features["shortest_offsuit_length"] == 1.0


def test_suit_distribution_sorted():
    """Test that suit lengths are sorted longest to shortest."""
    hand = [
        Card("H", "A"),
        Card("H", "K"),  # 2 hearts
        Card("D", "A"),
        Card("D", "K"),
        Card("D", "Q"),
        Card("D", "J"),  # 4 diamonds
        Card("C", "A"),  # 1 club
        Card("S", "A"),
        Card("S", "K"),
        Card("S", "Q"),  # 3 spades
    ]

    features = extract_bidless_hand_features(hand, contract_type="high")

    # Sorted: [4, 3, 2, 1]
    assert features["longest_offsuit_length"] == 4.0
    assert features["second_longest_offsuit_length"] == 3.0
    assert features["third_longest_offsuit_length"] == 2.0
    assert features["shortest_offsuit_length"] == 1.0


def test_offsuit_distribution_excludes_trump():
    """In suit contracts, trump cards should not count in offsuit distribution."""
    hand = [
        Card("H", "J"),  # Right bower (trump)
        Card("H", "A"),  # Trump
        Card("H", "K"),  # Trump
        Card("C", "A"),
        Card("C", "K"),
        Card("C", "Q"),  # 3 clubs
        Card("D", "A"),
        Card("D", "K"),  # 2 diamonds
        Card("S", "A"),
        Card("S", "K"),  # 2 spades
    ]

    features = extract_bidless_hand_features(hand, contract_type="suit", trump_suit="H")

    # Trump count = 3, offsuit lengths = [3, 2, 2, 0] (H is excluded from offsuit)
    assert features["trump_count"] == 3.0
    assert features["longest_offsuit_length"] == 3.0
    assert features["void_count"] == 1.0  # Hearts (all trump)


# ============================================================================
# Offsuit Control Tests
# ============================================================================


def test_offsuit_aces_in_suit_contract():
    """Test offsuit ace counting in suit contracts."""
    hand = [
        Card("H", "J"),  # Right bower (trump)
        Card("H", "A"),  # Trump ace (not offsuit)
        Card("C", "A"),  # Offsuit ace
        Card("D", "A"),  # Offsuit ace
        Card("S", "A"),  # Offsuit ace
        Card("C", "K"),
        Card("D", "K"),
        Card("S", "K"),
        Card("S", "Q"),
        Card("S", "T"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="suit", trump_suit="H")

    assert features["offsuit_aces"] == 3.0  # CDA, DDA, SA (not HA)
    assert features["offsuit_kings"] == 3.0


def test_offsuit_control_in_high_contract():
    """In high/low contracts, all aces are 'offsuit'."""
    hand = [
        Card("H", "A"),
        Card("D", "A"),
        Card("C", "A"),
        Card("S", "K"),
        Card("S", "K"),
        Card("S", "Q"),
        Card("S", "J"),
        Card("S", "T"),
        Card("C", "T"),
        Card("D", "T"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="high")

    # All aces count as offsuit in high/low
    assert features["offsuit_aces"] == 3.0
    assert features["offsuit_kings"] == 2.0


# ============================================================================
# Seat Context Tests
# ============================================================================


def test_dealer_seat_encoding():
    """Test one-hot encoding of dealer seat."""
    hand = [Card("H", "A")] * 10

    # Dealer at seat 0
    features = extract_bidless_hand_features(hand, contract_type="high", dealer_seat=0)
    assert features["is_dealer_seat_0"] == 1.0
    assert features["is_dealer_seat_1"] == 0.0
    assert features["is_dealer_seat_2"] == 0.0
    assert features["is_dealer_seat_3"] == 0.0
    assert features["dealer_seat_unknown"] == 0.0

    # Dealer at seat 2
    features = extract_bidless_hand_features(hand, contract_type="high", dealer_seat=2)
    assert features["is_dealer_seat_0"] == 0.0
    assert features["is_dealer_seat_1"] == 0.0
    assert features["is_dealer_seat_2"] == 1.0
    assert features["is_dealer_seat_3"] == 0.0
    assert features["dealer_seat_unknown"] == 0.0


def test_dealer_seat_unknown():
    """Test encoding when dealer seat is None."""
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(hand, contract_type="high", dealer_seat=None)

    assert features["is_dealer_seat_0"] == 0.0
    assert features["is_dealer_seat_1"] == 0.0
    assert features["is_dealer_seat_2"] == 0.0
    assert features["is_dealer_seat_3"] == 0.0
    assert features["dealer_seat_unknown"] == 1.0


def test_leader_seat_encoding():
    """Test one-hot encoding of leader seat."""
    hand = [Card("H", "A")] * 10

    # Leader at seat 1
    features = extract_bidless_hand_features(hand, contract_type="high", leader_seat=1)
    assert features["is_leader_seat_0"] == 0.0
    assert features["is_leader_seat_1"] == 1.0
    assert features["is_leader_seat_2"] == 0.0
    assert features["is_leader_seat_3"] == 0.0
    assert features["leader_seat_unknown"] == 0.0

    # Leader at seat 3
    features = extract_bidless_hand_features(hand, contract_type="high", leader_seat=3)
    assert features["is_leader_seat_0"] == 0.0
    assert features["is_leader_seat_1"] == 0.0
    assert features["is_leader_seat_2"] == 0.0
    assert features["is_leader_seat_3"] == 1.0
    assert features["leader_seat_unknown"] == 0.0


def test_leader_seat_unknown():
    """Test encoding when leader seat is None."""
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(hand, contract_type="high", leader_seat=None)

    assert features["is_leader_seat_0"] == 0.0
    assert features["is_leader_seat_1"] == 0.0
    assert features["is_leader_seat_2"] == 0.0
    assert features["is_leader_seat_3"] == 0.0
    assert features["leader_seat_unknown"] == 1.0


def test_both_seats_specified():
    """Test with both dealer and leader seats specified."""
    hand = [Card("H", "A")] * 10

    features = extract_bidless_hand_features(
        hand, contract_type="high", dealer_seat=0, leader_seat=2
    )

    # Dealer at 0
    assert features["is_dealer_seat_0"] == 1.0
    assert features["dealer_seat_unknown"] == 0.0

    # Leader at 2
    assert features["is_leader_seat_2"] == 1.0
    assert features["leader_seat_unknown"] == 0.0


# ============================================================================
# Feature Vector Tests
# ============================================================================


def test_extract_feature_vector_returns_list():
    """Test that extract_feature_vector returns list of floats."""
    hand = [Card("H", "A")] * 10

    values, names = extract_feature_vector(hand, contract_type="high")

    assert isinstance(values, list)
    assert isinstance(names, list)
    assert len(values) == len(names)
    assert all(isinstance(v, float) for v in values)
    assert all(isinstance(n, str) for n in names)


def test_feature_vector_matches_dict():
    """Test that feature vector matches dict extraction."""
    hand = [Card("H", "J"), Card("H", "A"), Card("C", "K")] + [Card("S", "T")] * 7

    features_dict = extract_bidless_hand_features(
        hand, contract_type="suit", trump_suit="H", dealer_seat=1
    )
    values, names = extract_feature_vector(
        hand, contract_type="suit", trump_suit="H", dealer_seat=1
    )

    # Every value should match corresponding dict entry
    for value, name in zip(values, names):
        assert value == features_dict[name]


def test_feature_vector_order_stability():
    """Test that feature vector order is stable across calls."""
    hand = [Card("H", "A")] * 10

    values1, names1 = extract_feature_vector(hand, contract_type="high")
    values2, names2 = extract_feature_vector(hand, contract_type="high")

    assert values1 == values2
    assert names1 == names2


def test_feature_vector_names_match_get_feature_names():
    """Test that feature vector names match get_feature_names()."""
    hand = [Card("H", "A")] * 10

    _, names = extract_feature_vector(hand, contract_type="high")

    assert names == get_feature_names()


# ============================================================================
# Edge Cases
# ============================================================================


def test_empty_hand():
    """Test with empty hand (edge case)."""
    hand = []

    features = extract_bidless_hand_features(hand, contract_type="high")

    # All counts should be 0
    assert features["count_aces"] == 0.0
    assert features["trump_count"] == 0.0
    assert features["void_count"] == 4.0  # All suits void
    assert features["longest_offsuit_length"] == 0.0


def test_hand_with_all_jacks():
    """Test hand with all jacks (left/right bowers in suit contract)."""
    hand = [
        Card("H", "J"),
        Card("H", "J"),  # 2 right bowers
        Card("D", "J"),
        Card("D", "J"),  # 2 left bowers
        Card("C", "J"),
        Card("S", "J"),  # 2 offsuit jacks
        Card("C", "A"),
        Card("C", "K"),
        Card("S", "A"),
        Card("S", "K"),
    ]

    features = extract_bidless_hand_features(hand, contract_type="suit", trump_suit="H")

    assert features["count_jacks"] == 6.0
    assert features["trump_count"] == 4.0  # 2 RB + 2 LB
    assert features["has_right_bower"] == 1.0
    assert features["has_left_bower"] == 1.0
