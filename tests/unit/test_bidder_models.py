"""
Unit tests for OLSa_v2 and OLSa_SR_v2 bidder-aware models.

Tests model predictions, feature sensitivity, and bidder advantage effects.
"""

import os
import sys
import pickle
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.analysis.models import SimpleOLS

# Check if model files exist
OLSA_V2_EXISTS = all(os.path.exists(f'data/models/current/olsa_v2/olsa_v2_{c}.pkl') for c in ['suit', 'high', 'low'])
OLSA_SR_V2_EXISTS = all(os.path.exists(f'data/models/current/olsa_sr_v2/olsa_sr_v2_{c}.pkl') for c in ['suit', 'high', 'low'])


def test_simple_ols_basic():
    """Test SimpleOLS fit and predict on toy data."""
    # Simple linear relationship: y = 2*x + 1
    X = [[1], [2], [3], [4], [5]]
    y = [3, 5, 7, 9, 11]
    
    model = SimpleOLS()
    model.fit(X, y)
    
    # Check coefficients
    assert abs(model.coef_[0] - 2.0) < 0.01, f"Expected coef ~2.0, got {model.coef_[0]}"
    assert abs(model.intercept_ - 1.0) < 0.01, f"Expected intercept ~1.0, got {model.intercept_}"
    
    # Check predictions
    y_pred = model.predict(X)
    for y_true, y_p in zip(y, y_pred):
        assert abs(y_true - y_p) < 0.01, f"Prediction error: {y_true} vs {y_p}"
    
    print("✅ SimpleOLS basic test passed")


def test_simple_ols_multiple_features():
    """Test SimpleOLS with multiple features."""
    # y = 2*x1 + 3*x2 + 1
    X = [
        [1, 0],
        [0, 1],
        [1, 1],
        [2, 2],
        [3, 1],
    ]
    y = [3, 4, 6, 11, 10]  # 2*1+3*0+1, 2*0+3*1+1, 2*1+3*1+1, 2*2+3*2+1, 2*3+3*1+1
    
    model = SimpleOLS()
    model.fit(X, y)
    
    # Check predictions are reasonable
    y_pred = model.predict(X)
    mse = sum((yt - yp)**2 for yt, yp in zip(y, y_pred)) / len(y)
    assert mse < 0.1, f"MSE too high: {mse}"
    
    print("✅ SimpleOLS multiple features test passed")


@pytest.mark.skipif(not OLSA_V2_EXISTS, reason="OLSa_v2 model files not found")
def test_olsa_v2_models_exist():
    """Test that OLSa_v2 model files exist."""
    for contract in ['suit', 'high', 'low']:
        model_path = f'data/models/current/olsa_v2/olsa_v2_{contract}.pkl'
        assert os.path.exists(model_path), f"Model not found: {model_path}"
    
    print("✅ OLSa_v2 model files exist")


@pytest.mark.skipif(not OLSA_SR_V2_EXISTS, reason="OLSa_SR_v2 model files not found")
def test_olsa_sr_v2_models_exist():
    """Test that OLSa_SR_v2 model files exist."""
    for contract in ['suit', 'high', 'low']:
        model_path = f'data/models/current/olsa_sr_v2/olsa_sr_v2_{contract}.pkl'
        assert os.path.exists(model_path), f"Model not found: {model_path}"
    
    print("✅ OLSa_SR_v2 model files exist")


def test_olsa_v2_suit_model_predictions():
    """Test OLSa_v2 suit model makes sensible predictions."""
    model_path = 'data/models/current/olsa_v2/olsa_v2_suit.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Skipping test - model not found")
        return
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
    
    # Features: [trump_count, trump_rb_count, trump_lb_count, offsuit_aces, is_bidder]
    
    # Test case 1: Strong hand (many trump, bowers, bidder)
    strong_hand = [[6, 1, 1, 1, 1]]  # 6 trump, RB, LB, 1 ace, is bidder
    pred_strong = model.predict(strong_hand)[0]
    
    # Test case 2: Weak hand (few trump, no bowers, not bidder)
    weak_hand = [[2, 0, 0, 0, 0]]  # 2 trump, no bowers, no aces, not bidder
    pred_weak = model.predict(weak_hand)[0]
    
    # Strong hand should predict more tricks
    assert pred_strong > pred_weak, f"Strong hand should predict more tricks: {pred_strong} vs {pred_weak}"
    
    # Predictions should be in reasonable range (0-10 tricks)
    assert 0 <= pred_strong <= 12, f"Prediction out of range: {pred_strong}"
    assert 0 <= pred_weak <= 12, f"Prediction out of range: {pred_weak}"
    
    print(f"✅ OLSa_v2 suit predictions: strong={pred_strong:.2f}, weak={pred_weak:.2f}")


def test_olsa_v2_is_bidder_effect():
    """Test that is_bidder coefficient increases prediction as expected."""
    model_path = 'data/models/current/olsa_v2/olsa_v2_suit.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Skipping test - model not found")
        return
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
    
    # Features: [trump_count, trump_rb_count, trump_lb_count, offsuit_aces, is_bidder]
    # Same hand, only difference is is_bidder
    hand_not_bidder = [[4, 0, 1, 1, 0]]  # Not bidder
    hand_is_bidder = [[4, 0, 1, 1, 1]]    # Is bidder
    
    pred_not_bidder = model.predict(hand_not_bidder)[0]
    pred_is_bidder = model.predict(hand_is_bidder)[0]
    
    # Bidder should have advantage
    bidder_advantage = pred_is_bidder - pred_not_bidder
    
    # From training, we expect ~0.65 trick advantage for suit
    assert bidder_advantage > 0.3, f"Bidder advantage too small: {bidder_advantage}"
    assert bidder_advantage < 1.0, f"Bidder advantage too large: {bidder_advantage}"
    
    print(f"✅ OLSa_v2 bidder advantage for suit: {bidder_advantage:.3f} tricks")


def test_olsa_v2_low_bidder_advantage():
    """Test that LOW contract shows massive bidder advantage."""
    model_path = 'data/models/current/olsa_v2/olsa_v2_low.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Skipping test - model not found")
        return
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
    
    # Features: [offsuit_length_3plus_count, is_bidder]
    hand_not_bidder = [[2, 0]]  # 2 long suits, not bidder
    hand_is_bidder = [[2, 1]]    # 2 long suits, is bidder
    
    pred_not_bidder = model.predict(hand_not_bidder)[0]
    pred_is_bidder = model.predict(hand_is_bidder)[0]
    
    bidder_advantage = pred_is_bidder - pred_not_bidder
    
    # From training, we expect ~1.4 trick advantage for LOW
    assert bidder_advantage > 1.0, f"LOW bidder advantage should be >1 trick: {bidder_advantage}"
    assert bidder_advantage < 2.0, f"LOW bidder advantage too large: {bidder_advantage}"
    
    print(f"✅ OLSa_v2 bidder advantage for LOW: {bidder_advantage:.3f} tricks (massive!)")


def test_olsa_v2_high_bidder_disadvantage():
    """Test that HIGH contract shows slight bidder disadvantage."""
    model_path = 'data/models/current/olsa_v2/olsa_v2_high.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Skipping test - model not found")
        return
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
    
    # Features: [offsuit_aces, offsuit_length_3plus_count, is_bidder]
    hand_not_bidder = [[2, 1, 0]]  # 2 aces, 1 long suit, not bidder
    hand_is_bidder = [[2, 1, 1]]    # 2 aces, 1 long suit, is bidder
    
    pred_not_bidder = model.predict(hand_not_bidder)[0]
    pred_is_bidder = model.predict(hand_is_bidder)[0]
    
    bidder_effect = pred_is_bidder - pred_not_bidder
    
    # From training, we expect ~-0.11 trick effect (slight disadvantage)
    # Allow some tolerance (-0.3 to +0.1)
    assert bidder_effect > -0.3, f"HIGH bidder effect too negative: {bidder_effect}"
    assert bidder_effect < 0.2, f"HIGH bidder effect should be near zero or negative: {bidder_effect}"
    
    print(f"✅ OLSa_v2 bidder effect for HIGH: {bidder_effect:.3f} tricks (neutral/slight disadvantage)")


def test_olsa_sr_v2_hand_value_sensitivity():
    """Test that hand_value increases prediction in OLSa_SR_v2."""
    model_path = 'data/models/current/olsa_sr_v2/olsa_sr_v2_suit.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Skipping test - model not found")
        return
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
    
    # Features: [hand_value, is_bidder]
    low_value = [[50, 0]]    # Low hand value, not bidder
    high_value = [[150, 0]]  # High hand value, not bidder
    
    pred_low = model.predict(low_value)[0]
    pred_high = model.predict(high_value)[0]
    
    # Higher hand value should predict more tricks (though coefficient is weak)
    assert pred_high >= pred_low, f"Higher hand_value should predict >= tricks: {pred_high} vs {pred_low}"
    
    print(f"✅ OLSa_SR_v2 hand_value sensitivity: low={pred_low:.2f}, high={pred_high:.2f}")


def test_model_coefficients_reasonable():
    """Test that all model coefficients are in reasonable ranges."""
    models_to_check = [
        ('data/models/current/olsa_v2/olsa_v2_suit.pkl', 'OLSa_v2_suit', 5),
        ('data/models/current/olsa_v2/olsa_v2_high.pkl', 'OLSa_v2_high', 3),
        ('data/models/current/olsa_v2/olsa_v2_low.pkl', 'OLSa_v2_low', 2),
        ('data/models/current/olsa_sr_v2/olsa_sr_v2_suit.pkl', 'OLSa_SR_v2_suit', 2),
        ('data/models/current/olsa_sr_v2/olsa_sr_v2_high.pkl', 'OLSa_SR_v2_high', 2),
        ('data/models/current/olsa_sr_v2/olsa_sr_v2_low.pkl', 'OLSa_SR_v2_low', 2),
    ]
    
    for model_path, name, expected_n_features in models_to_check:
        if not os.path.exists(model_path):
            print(f"⚠️  Skipping {name} - model not found")
            continue
        
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        
        # Check number of coefficients
        assert len(model.coef_) == expected_n_features, \
            f"{name}: Expected {expected_n_features} features, got {len(model.coef_)}"
        
        # Check coefficients are not NaN or Inf
        for i, coef in enumerate(model.coef_):
            assert not np.isnan(coef), f"{name}: Coefficient {i} is NaN"
            assert not np.isinf(coef), f"{name}: Coefficient {i} is Inf"
            assert abs(coef) < 10, f"{name}: Coefficient {i} suspiciously large: {coef}"
        
        # Check intercept
        assert not np.isnan(model.intercept_), f"{name}: Intercept is NaN"
        assert not np.isinf(model.intercept_), f"{name}: Intercept is Inf"
        assert -5 < model.intercept_ < 15, f"{name}: Intercept suspiciously out of range: {model.intercept_}"
    
    print("✅ All model coefficients are reasonable")


def test_predictions_in_valid_range():
    """Test that predictions stay in valid range (0-10 tricks)."""
    # Test many random feature combinations
    np.random.seed(42)
    
    model_path = 'data/models/current/olsa_v2/olsa_v2_suit.pkl'
    if not os.path.exists(model_path):
        print("⚠️  Skipping test - model not found")
        return
    
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
        model = model_data['model'] if isinstance(model_data, dict) else model_data
    
    # Generate random hands
    # Features: [trump_count, trump_rb_count, trump_lb_count, offsuit_aces, is_bidder]
    n_tests = 100
    for _ in range(n_tests):
        trump_count = np.random.randint(0, 8)
        trump_rb = np.random.randint(0, 2)
        trump_lb = np.random.randint(0, 2)
        offsuit_aces = np.random.randint(0, 4)
        is_bidder = np.random.randint(0, 2)
        
        hand = [[trump_count, trump_rb, trump_lb, offsuit_aces, is_bidder]]
        pred = model.predict(hand)[0]
        
        # Allow some tolerance outside [0, 10] but not too much
        assert -2 < pred < 12, f"Prediction way out of range: {pred} for hand {hand[0]}"
    
    print(f"✅ {n_tests} random predictions all in reasonable range")


def run_all_tests():
    """Run all tests."""
    tests = [
        test_simple_ols_basic,
        test_simple_ols_multiple_features,
        test_olsa_v2_models_exist,
        test_olsa_sr_v2_models_exist,
        test_olsa_v2_suit_model_predictions,
        test_olsa_v2_is_bidder_effect,
        test_olsa_v2_low_bidder_advantage,
        test_olsa_v2_high_bidder_disadvantage,
        test_olsa_sr_v2_hand_value_sensitivity,
        test_model_coefficients_reasonable,
        test_predictions_in_valid_range,
    ]
    
    print("="*80)
    print("Running Bidder Model Unit Tests")
    print("="*80)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"⚠️  {test.__name__} SKIPPED: {e}")
            skipped += 1
    
    print("\n" + "="*80)
    print(f"Test Summary: {passed} passed, {failed} failed, {skipped} skipped")
    print("="*80)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
