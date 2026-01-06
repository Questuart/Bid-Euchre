import os
import pickle

import numpy as np
import pytest

from bid_euchre.analysis.models import SimpleOLS
from bid_euchre.core.cards import Card
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.baselines import RandomLegalStrategy
from bid_euchre.strategy.regression import RegressionBidder

# Dummy model paths for testing
DUMMY_MODEL_DIR = "tests/dummy_models"

@pytest.fixture
def dummy_models():
    """Create dummy models for testing."""
    os.makedirs(DUMMY_MODEL_DIR, exist_ok=True)
    
    # Simple model that predicts tricks = 1.0 * feature_val
    model = SimpleOLS()
    model.coef_ = np.array([1.0])
    model.intercept_ = 0.0
    
    # We'll use 'rank_sum' as the single feature for all dummy models
    # to keep it predictable in tests.
    model_data = {
        'model': model,
        'features': ['rank_sum'],
        'contract_type': 'suit'
    }
    
    paths = {}
    for ctype in ['suit', 'high', 'low']:
        path = os.path.join(DUMMY_MODEL_DIR, f"dummy_{ctype}.pkl")
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
        paths[ctype] = path
        
    return paths

def test_regression_bidder_policy(dummy_models):
    """Test floor, ceil, round policies."""
    # A hand with rank_sum = 6.5
    # (Not real cards, just dummying the evaluation)
    
    # We need to mock get_hand_features to return a specific rank_sum
    # Or just use real cards that sum to something known.
    # T=1, J=2, Q=3, K=4, A=5
    # 5 Aces = 25. 5 Tens = 5. Total = 30.
    hand = [Card("H", "A")] * 5 + [Card("H", "T")] * 5
    # rank_sum = 5*5 + 5*1 = 30.0
    # dummy model predicts 30.0
    
    bidder_round = RegressionBidder(dummy_models, policy="round")
    bid, ctype, trump = bidder_round.decide_bid(hand, 0, None, 2, 0)
    assert bid == 30
    
    # Let's try a policy with non-integers
    # We'll mock the prediction directly if possible or just use cards.
    
    # To test rounding/floor/ceil, we need a model that returns a float.
    model_float = SimpleOLS()
    model_float.coef_ = np.array([0.1]) # 1/10th of rank_sum
    model_float.intercept_ = 0.5
    # For a hand of 10 Queens, rank_sum = 10 * 3 = 30.0 in all contracts.
    # pred = 30 * 0.1 + 0.5 = 3.5
    hand_queens = [Card("H", "Q")] * 10
    
    for ctype in ['suit', 'high', 'low']:
        with open(os.path.join(DUMMY_MODEL_DIR, f"dummy_{ctype}.pkl"), 'wb') as f:
            pickle.dump({'model': model_float, 'features': ['rank_sum']}, f)
        
    bidder_floor = RegressionBidder(dummy_models, policy="floor")
    bid, _, _ = bidder_floor.decide_bid(hand_queens, 0, None, 2, 0)
    assert bid == 3 # floor(3.5)
    
    bidder_ceil = RegressionBidder(dummy_models, policy="ceil")
    bid, _, _ = bidder_ceil.decide_bid(hand_queens, 0, None, 2, 0)
    assert bid == 4 # ceil(3.5)
    
    bidder_round = RegressionBidder(dummy_models, policy="round")
    bid, _, _ = bidder_round.decide_bid(hand_queens, 0, None, 2, 0)
    assert bid == 4 # round(3.5) -> 4 (numpy rounds half to even, but 3.5 -> 4 usually)
    # Wait, np.round(3.5) is 4.0.

def test_fixed_bid_fred(dummy_models):
    """Test that fixed_bid (FiveHeadFred) always bids the fixed amount."""
    hand = [Card("H", "A")] * 10 # rank_sum = 50
    
    fred = RegressionBidder(dummy_models, fixed_bid=5)
    bid, _, _ = fred.decide_bid(hand, 0, None, 2, 0)
    assert bid == 5

def test_misdeal_logic():
    """Verify that if all players pass, it's a misdeal."""
    # RandomLegalStrategy always returns 0 for decide_bid (default)
    strategies = [RandomLegalStrategy() for _ in range(4)]
    
    t0, t1, scores, feats, leader, hands, bid, _, _, _, _ = play_single_hand(
        contract_type=None,
        strategies=strategies
    )
    
    assert t0 == 0
    assert t1 == 0
    assert leader == -1
    assert bid == 0

def test_partner_pass_rule(dummy_models):
    """Dealer should pass if partner has the high bid."""
    class ForceBid10(RandomLegalStrategy):
        def decide_bid(self, hand, current_high_bid, current_winner_index, partner_index, player_index):
            return 10, "high", None

    strategies = [
        RandomLegalStrategy(), # Seat 0
        ForceBid10(),          # Seat 1 (Partner of 3)
        RandomLegalStrategy(), # Seat 2
        RegressionBidder(dummy_models, fixed_bid=12) # Seat 3 (Dealer, wants to bid 12)
    ]
    
    # Play hand with contract_type=None to trigger bidding
    # Seat 3 is dealer if initial_leader=0 (LOD)
    t0, t1, _, _, leader, _, bid, _, _, _, _ = play_single_hand(
        contract_type=None,
        strategies=strategies,
        initial_leader=0 
    )
    
    # Winner should be Seat 1, NOT Seat 3
    assert leader == 1
    assert bid == 10

def test_bid_winner_leads(dummy_models):
    """The person who wins the bid must lead the first trick."""
    strategies = [
        RegressionBidder(dummy_models, fixed_bid=6), # wants to bid 6
        RandomLegalStrategy(),
        RandomLegalStrategy(),
        RandomLegalStrategy()
    ]
    
    t0, t1, _, _, leader, _, bid, _, _, _, _ = play_single_hand(
        contract_type=None,
        strategies=strategies,
        initial_leader=1 # make someone else dealer so Seat 0 is LOD
    )
    
    assert leader == 0
    assert bid == 6

if __name__ == "__main__":
    # Setup dummy models
    paths = {
        'suit': os.path.join(DUMMY_MODEL_DIR, "dummy_suit.pkl"),
        'high': os.path.join(DUMMY_MODEL_DIR, "dummy_high.pkl"),
        'low': os.path.join(DUMMY_MODEL_DIR, "dummy_low.pkl")
    }
    os.makedirs(DUMMY_MODEL_DIR, exist_ok=True)
    model = SimpleOLS()
    model.coef_ = np.array([1.0])
    model.intercept_ = 0.0
    for p in paths.values():
        with open(p, 'wb') as f:
            pickle.dump({'model': model, 'features': ['rank_sum']}, f)

    print("Running tests manually...")
    try:
        test_regression_bidder_policy(paths)
        print("✅ test_regression_bidder_policy PASSED")
        
        test_fixed_bid_fred(paths)
        print("✅ test_fixed_bid_fred PASSED")
        
        test_misdeal_logic()
        print("✅ test_misdeal_logic PASSED")
        
        test_partner_pass_rule(paths)
        print("✅ test_partner_pass_rule PASSED")
        
        test_bid_winner_leads(paths)
        print("✅ test_bid_winner_leads PASSED")
        
        print("\n🎉 ALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
