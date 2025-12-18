"""
Comprehensive unit tests for hand evaluation features.

Tests all 40+ features from get_hand_features() including:
- Trump strength (bowers, trump count, power metrics)
- Offsuit control (aces, kings, suit coverage)
- Distribution (voids, singletons, suit lengths)
- High/Low specific features
- Edge cases and boundary conditions
"""

import pytest
from bid_euchre.core.cards import Card
from bid_euchre.features.hand_eval import (
    get_hand_features,
    score_hand_scalar,
    score_hand_tuple,
    score_hand,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def empty_hand():
    """Empty hand for boundary testing."""
    return []


@pytest.fixture
def all_trump_hand():
    """Hand with all trump cards (suit contract)."""
    return [
        Card("H", "J"),  # Right bower
        Card("D", "J"),  # Left bower
        Card("H", "A"),
        Card("H", "K"),
        Card("H", "Q"),
        Card("H", "T"),
        Card("H", "9"),  # Note: 9 is not in standard euchre deck
    ]


@pytest.fixture
def no_trump_hand():
    """Hand with no trump (all offsuit)."""
    return [
        Card("C", "A"),
        Card("C", "K"),
        Card("D", "A"),
        Card("D", "K"),
        Card("S", "A"),
    ]


@pytest.fixture
def void_hand():
    """Hand with multiple void suits."""
    return [
        Card("H", "A"),
        Card("H", "K"),
        Card("H", "Q"),
        Card("H", "T"),
        Card("H", "J"),
    ]


@pytest.fixture
def balanced_hand():
    """Balanced hand with good distribution."""
    return [
        Card("H", "A"),
        Card("H", "K"),
        Card("D", "A"),
        Card("D", "K"),
        Card("C", "A"),
        Card("C", "K"),
        Card("S", "A"),
        Card("S", "K"),
    ]


@pytest.fixture
def bower_hand():
    """Hand with both bowers."""
    return [
        Card("H", "J"),  # Right bower (trump = H)
        Card("D", "J"),  # Left bower (trump = H)
        Card("C", "A"),
        Card("C", "K"),
        Card("S", "A"),
    ]


@pytest.fixture
def weak_hand():
    """Very weak hand."""
    return [
        Card("C", "9"),
        Card("D", "9"),
        Card("S", "9"),
        Card("H", "9"),
        Card("C", "T"),
    ]


# ============================================================================
# Test: Basic Feature Extraction
# ============================================================================

class TestBasicFeatures:
    """Test basic feature extraction for all contract types."""
    
    def test_suit_contract_basic(self):
        """Test basic features for suit contract."""
        hand = [
            Card("H", "J"),  # Right bower
            Card("D", "J"),  # Left bower
            Card("H", "A"),
            Card("C", "A"),
            Card("S", "K"),
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        # Legacy features
        assert features["bowers"] == 2
        assert features["trump_count"] == 3  # RB, LB, HA
        assert features["offsuit_aces"] == 1  # CA
        assert features["rank_sum"] > 0
        
        # Trump features
        assert features["trump_rb_count"] == 1
        assert features["trump_lb_count"] == 1
        assert features["trump_ace_count"] == 1
        assert features["top_trump_count"] == 3  # RB + LB + HA
        assert features["highest_trump_rank"] == 6  # RB = 6
    
    def test_high_contract_basic(self):
        """Test basic features for high contract."""
        hand = [
            Card("H", "A"),
            Card("D", "A"),
            Card("C", "K"),
            Card("S", "Q"),
            Card("H", "T"),
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        # No trump features (high contract)
        assert features["bowers"] == 0
        assert features["trump_count"] == 0
        assert features["offsuit_aces"] == 2  # HA, DA
        
        # High/Low features
        assert features["high_card_count"] == 3  # 2 aces + 1 king
        assert features["low_card_count"] == 1  # 1 ten
    
    def test_low_contract_basic(self):
        """Test basic features for low contract."""
        hand = [
            Card("H", "T"),
            Card("D", "J"),
            Card("C", "T"),
            Card("S", "A"),  # Weak in low
            Card("H", "K"),   # Weak in low
        ]
        
        features = get_hand_features(hand, contract_type="low", trump_suit=None)
        
        # No trump features (low contract)
        assert features["bowers"] == 0
        assert features["trump_count"] == 0
        
        # High/Low features
        assert features["low_card_count"] == 3  # 2 tens + 1 jack


# ============================================================================
# Test: Trump Strength Features (Suit Contracts Only)
# ============================================================================

class TestTrumpFeatures:
    """Test trump-specific features for suit contracts."""
    
    def test_bower_identification(self):
        """Test right and left bower detection."""
        hand = [
            Card("H", "J"),  # Right bower
            Card("D", "J"),  # Left bower
            Card("C", "A"),
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["trump_rb_count"] == 1
        assert features["trump_lb_count"] == 1
        assert features["bowers"] == 2
    
    def test_trump_rank_distribution(self):
        """Test trump rank counting."""
        hand = [
            Card("H", "J"),  # RB
            Card("H", "A"),
            Card("H", "K"),
            Card("H", "Q"),
            Card("H", "T"),
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["trump_rb_count"] == 1
        assert features["trump_ace_count"] == 1
        assert features["trump_king_count"] == 1
        assert features["trump_queen_count"] == 1
        assert features["trump_ten_count"] == 1
        assert features["trump_count"] == 5
    
    def test_trump_power_metrics(self):
        """Test trump power sum and average."""
        hand = [
            Card("H", "J"),  # RB = 6
            Card("D", "J"),  # LB = 5
            Card("H", "A"),  # = 4
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["trump_power_sum"] == 15  # 6 + 5 + 4
        assert features["trump_power_avg"] == 5.0  # 15 / 3
        assert features["top_trump_count"] == 3  # RB + LB + A
    
    def test_highest_trump_ranks(self):
        """Test top 3 trump rank tracking."""
        hand = [
            Card("H", "A"),  # 4
            Card("H", "K"),  # 3
            Card("H", "Q"),  # 2
            Card("H", "T"),  # 1
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["highest_trump_rank"] == 4  # Ace
        assert features["second_highest_trump_rank"] == 3  # King
        assert features["third_highest_trump_rank"] == 2  # Queen
    
    def test_trump_duplicate_pairs(self):
        """Test trump duplicate pair detection."""
        hand = [
            Card("H", "A"),
            Card("H", "A"),  # Pair of aces
            Card("H", "K"),
            Card("H", "K"),  # Pair of kings
            Card("H", "Q"),  # Single queen
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["trump_duplicate_pairs"] == 2  # 2 pairs
    
    def test_no_trump_cards(self, no_trump_hand):
        """Test hand with no trump cards."""
        features = get_hand_features(no_trump_hand, contract_type="suit", trump_suit="H")
        
        assert features["trump_count"] == 0
        assert features["trump_power_sum"] == 0
        assert features["trump_power_avg"] == 0
        assert features["highest_trump_rank"] == 0


# ============================================================================
# Test: Offsuit Control Features
# ============================================================================

class TestOffsuitControl:
    """Test offsuit control and high card features."""
    
    def test_offsuit_aces(self):
        """Test offsuit ace counting."""
        hand = [
            Card("H", "J"),  # Trump (RB)
            Card("C", "A"),  # Offsuit ace
            Card("D", "A"),  # Offsuit ace
            Card("S", "A"),  # Offsuit ace
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["offsuit_aces"] == 3
        assert features["offsuit_suits_with_ace"] == 3
    
    def test_offsuit_kings_queens(self):
        """Test offsuit king and queen counting."""
        hand = [
            Card("H", "J"),  # Trump
            Card("C", "K"),
            Card("D", "K"),
            Card("S", "Q"),
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["offsuit_king_count_total"] == 2
        assert features["offsuit_queen_count_total"] == 1
        assert features["high_offsuit"] == 3  # 2 kings + 1 queen
    
    def test_double_ace_suit(self):
        """Test detection of suits with double aces."""
        hand = [
            Card("C", "A"),
            Card("C", "A"),  # Double ace in clubs
            Card("D", "A"),  # Single ace in diamonds
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["offsuit_suits_with_double_ace"] == 1
        assert features["offsuit_suits_with_ace"] == 2
    
    def test_ace_king_combinations(self):
        """Test suits with both ace and king."""
        hand = [
            Card("C", "A"),
            Card("C", "K"),  # Ace-King in clubs
            Card("D", "A"),
            Card("D", "K"),  # Ace-King in diamonds
            Card("S", "A"),  # Ace only in spades
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["offsuit_suits_with_ace_and_king"] == 2
    
    def test_offsuit_rank_sums(self):
        """Test offsuit rank sum calculations."""
        hand = [
            Card("C", "A"),  # Strong suit
            Card("C", "K"),
            Card("C", "Q"),
            Card("D", "T"),  # Weak suit
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["offsuit_best_rank_sum"] > features["offsuit_secondbest_rank_sum"]


# ============================================================================
# Test: Distribution Features
# ============================================================================

class TestDistribution:
    """Test hand distribution features."""
    
    def test_void_detection(self, void_hand):
        """Test void suit detection."""
        features = get_hand_features(void_hand, contract_type="high", trump_suit=None)
        
        assert features["void_count"] == 3  # 3 suits have 0 cards
        assert features["max_suit_len"] == 5  # All 5 cards in one suit
    
    def test_singletons_doubletons(self):
        """Test singleton and doubleton detection."""
        hand = [
            Card("C", "A"),  # Singleton
            Card("D", "A"),
            Card("D", "K"),  # Doubleton
            Card("S", "A"),
            Card("S", "K"),
            Card("S", "Q"),  # 3-card suit
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["num_singletons"] == 1
        assert features["num_doubletons"] == 1
        assert features["offsuit_length_3plus_count"] == 1
    
    def test_suit_length_ordering(self, balanced_hand):
        """Test suit length ordering (longest to shortest)."""
        features = get_hand_features(balanced_hand, contract_type="high", trump_suit=None)
        
        # Should be ordered longest to shortest
        assert features["max_suit_len"] >= features["second_suit_len"]
        assert features["second_suit_len"] >= features["third_suit_len"]
        assert features["third_suit_len"] >= features["fourth_suit_len"]
    
    def test_offsuit_tens_count(self):
        """Test offsuit ten counting."""
        hand = [
            Card("C", "T"),
            Card("D", "T"),
            Card("S", "T"),
            Card("H", "A"),
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["offsuit_tens_count"] == 3


# ============================================================================
# Test: High/Low Specific Features
# ============================================================================

class TestHighLowFeatures:
    """Test features specific to high and low contracts."""
    
    def test_high_card_count(self):
        """Test high card counting (A, K)."""
        hand = [
            Card("C", "A"),
            Card("D", "A"),
            Card("S", "K"),
            Card("H", "Q"),
            Card("C", "T"),
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["high_card_count"] == 3  # 2 aces + 1 king
    
    def test_low_card_count(self):
        """Test low card counting (J, T)."""
        hand = [
            Card("C", "J"),
            Card("D", "J"),
            Card("S", "T"),
            Card("H", "T"),
            Card("C", "A"),
        ]
        
        features = get_hand_features(hand, contract_type="low", trump_suit=None)
        
        assert features["low_card_count"] == 4  # 2 jacks + 2 tens
    
    def test_double_ten_jack_count(self):
        """Test double ten + jack combination."""
        hand = [
            Card("C", "T"),
            Card("C", "T"),
            Card("C", "J"),  # Clubs has 2 tens + 1 jack
            Card("D", "T"),
            Card("D", "J"),  # Diamonds has only 1 ten + 1 jack
        ]
        
        features = get_hand_features(hand, contract_type="low", trump_suit=None)
        
        assert features["double_ten_jack_count"] == 1  # Only clubs qualifies


# ============================================================================
# Test: Interaction Terms
# ============================================================================

class TestInteractionTerms:
    """Test feature interaction terms."""
    
    def test_trump_void_interaction(self):
        """Test trump_count × void_count interaction."""
        hand = [
            Card("H", "J"),  # Trump
            Card("H", "A"),  # Trump
            Card("H", "K"),  # Trump
            Card("H", "Q"),  # Trump (all same suit)
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        assert features["trump_count"] == 4
        # void_count counts all suits with 0 cards in offsuit_by_suit dict
        # When all cards are trump, all 4 offsuit entries (C,D,H,S) are checked
        # and 4 of them (including trump suit's offsuit entry) are empty
        assert features["void_count"] == 4  
        assert features["trump_count_x_void_count"] == 16  # 4 × 4
    
    def test_trump_offsuit_ace_interaction(self, bower_hand):
        """Test trump_count × offsuit_ace interaction."""
        features = get_hand_features(bower_hand, contract_type="suit", trump_suit="H")
        
        expected = features["trump_count"] * features["offsuit_aces"]
        assert features["trump_count_x_offsuit_ace"] == expected
    
    def test_no_interaction_in_high_low(self):
        """Test that interaction terms are 0 for high/low contracts."""
        hand = [Card("C", "A"), Card("D", "A")]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["trump_count_x_void_count"] == 0
        assert features["trump_count_x_offsuit_ace"] == 0


# ============================================================================
# Test: Edge Cases and Boundary Conditions
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_hand_features(self, empty_hand):
        """Test features with empty hand."""
        features = get_hand_features(empty_hand, contract_type="high", trump_suit=None)
        
        # All counts should be 0
        assert features["bowers"] == 0
        assert features["trump_count"] == 0
        assert features["offsuit_aces"] == 0
        assert features["high_card_count"] == 0
        assert features["void_count"] == 4  # All suits are void
    
    def test_all_trump_hand_suit_contract(self, all_trump_hand):
        """Test hand with all trump cards."""
        features = get_hand_features(all_trump_hand[:6], contract_type="suit", trump_suit="H")
        
        # Should have high trump count, no offsuit
        assert features["trump_count"] >= 5
        assert features["offsuit_aces"] == 0
        assert features["void_count"] == 4  # All 4 offsuit slots are empty
    
    def test_missing_trump_suit_raises(self):
        """Test that suit contract without trump_suit raises error."""
        hand = [Card("C", "A")]
        
        with pytest.raises(ValueError, match="trump_suit must be provided"):
            get_hand_features(hand, contract_type="suit", trump_suit=None)
    
    def test_all_same_rank(self):
        """Test hand with all same rank."""
        hand = [
            Card("C", "A"),
            Card("D", "A"),
            Card("S", "A"),
            Card("H", "A"),
        ]
        
        features = get_hand_features(hand, contract_type="high", trump_suit=None)
        
        assert features["offsuit_aces"] == 4
        assert features["high_card_count"] == 4


# ============================================================================
# Test: Scoring Functions
# ============================================================================

class TestScoringFunctions:
    """Test hand scoring functions."""
    
    def test_score_hand_scalar_suit(self, bower_hand):
        """Test scalar scoring for suit contracts."""
        score = score_hand_scalar(bower_hand, contract_type="suit", trump_suit="H")
        
        # Bowers should contribute highly (RB=120, LB=110)
        assert score >= 230  # At minimum RB + LB
        assert isinstance(score, int)
    
    def test_score_hand_scalar_high(self):
        """Test scalar scoring for high contracts."""
        hand = [
            Card("C", "A"),  # Strong
            Card("D", "A"),
            Card("S", "T"),  # Weak
        ]
        
        score = score_hand_scalar(hand, contract_type="high", trump_suit=None)
        
        assert score > 0
        assert isinstance(score, int)
    
    def test_score_hand_scalar_monotonic(self):
        """Test that better hands score higher."""
        strong_hand = [
            Card("H", "J"),  # RB
            Card("D", "J"),  # LB
            Card("H", "A"),
        ]
        
        weak_hand = [
            Card("C", "9"),
            Card("D", "9"),
            Card("S", "9"),
        ]
        
        strong_score = score_hand_scalar(strong_hand, "suit", "H")
        weak_score = score_hand_scalar(weak_hand, "suit", "H")
        
        assert strong_score > weak_score
    
    def test_score_hand_tuple(self, bower_hand):
        """Test tuple scoring."""
        score_tuple = score_hand_tuple(bower_hand, contract_type="suit", trump_suit="H")
        
        assert isinstance(score_tuple, tuple)
        assert len(score_tuple) == 5
        assert score_tuple[0] == 2  # bowers
        assert score_tuple[1] == 2  # trump_count
    
    def test_score_hand_mode_selection(self, bower_hand):
        """Test score_hand() mode parameter."""
        scalar_score = score_hand(bower_hand, "suit", "H", mode="scalar")
        tuple_score = score_hand(bower_hand, "suit", "H", mode="tuple")
        
        assert isinstance(scalar_score, int)
        assert isinstance(tuple_score, tuple)
    
    def test_score_hand_invalid_mode(self, bower_hand):
        """Test that invalid mode raises error."""
        with pytest.raises(ValueError, match="Unknown hand scoring mode"):
            score_hand(bower_hand, "suit", "H", mode="invalid")


# ============================================================================
# Test: Feature Completeness
# ============================================================================

class TestFeatureCompleteness:
    """Test that all expected features are present."""
    
    def test_all_features_present(self):
        """Test that get_hand_features returns all 40+ expected features."""
        hand = [
            Card("H", "J"),
            Card("D", "J"),
            Card("C", "A"),
        ]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        expected_features = {
            # Legacy
            "bowers", "trump_count", "offsuit_aces", "high_offsuit", "rank_sum",
            
            # Trump features
            "trump_rb_count", "trump_lb_count", "trump_ace_count", "trump_king_count",
            "trump_queen_count", "trump_ten_count", "top_trump_count",
            "highest_trump_rank", "second_highest_trump_rank", "third_highest_trump_rank",
            "trump_power_sum", "trump_power_avg", "trump_duplicate_pairs", "top_trump_sum",
            
            # Offsuit control
            "offsuit_king_count_total", "offsuit_queen_count_total",
            "offsuit_suits_with_ace", "offsuit_suits_with_double_ace",
            "offsuit_suits_with_ace_and_king",
            
            # Distribution
            "void_count", "max_suit_len", "second_suit_len", "third_suit_len",
            "fourth_suit_len", "num_singletons", "num_doubletons",
            "offsuit_tens_count", "offsuit_length_3plus_count",
            "offsuit_best_rank_sum", "offsuit_secondbest_rank_sum",
            
            # High/Low specific
            "double_ten_jack_count", "high_card_count", "low_card_count",
            
            # Interactions
            "trump_count_x_void_count", "trump_count_x_offsuit_ace",
        }
        
        actual_features = set(features.keys())
        
        # Check all expected features are present
        missing = expected_features - actual_features
        assert not missing, f"Missing features: {missing}"
        
        # Check count
        assert len(features) >= 40, f"Expected 40+ features, got {len(features)}"
    
    def test_all_features_have_values(self):
        """Test that all features return valid numeric values."""
        hand = [Card("H", "A"), Card("D", "K")]
        
        features = get_hand_features(hand, contract_type="suit", trump_suit="H")
        
        for fname, fval in features.items():
            assert isinstance(fval, (int, float)), f"Feature {fname} has non-numeric value: {fval}"
            assert not (isinstance(fval, float) and (fval != fval)), f"Feature {fname} is NaN"


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
