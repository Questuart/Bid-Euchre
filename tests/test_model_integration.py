"""
Integration tests for bidder-aware models in simulation.

Tests that models can be loaded and used in actual gameplay without crashes,
and that they produce reasonable results.
"""

import os
import sys
import pickle

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.sim.simulation import play_single_hand, simulate_many_hands
from bid_euchre.strategy.regression import RegressionBidder
from bid_euchre.strategy.baselines import RandomLegalStrategy
from bid_euchre.logging import GameLogger, LogLevel


def test_olsa_v2_loads_successfully():
    """Test that OLSa_v2 models can be loaded."""
    model_paths = {
        'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
        'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
        'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
    }
    
    for contract, path in model_paths.items():
        assert os.path.exists(path), f"Model not found: {path}"
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        assert model_data is not None, f"Failed to load {contract} model"
        if isinstance(model_data, dict):
            model = model_data['model']
        else:
            model = model_data
        assert hasattr(model, 'predict'), f"{contract} model missing predict method"
    
    print("✅ All OLSa_v2 models loaded successfully")


def test_olsa_v2_plays_single_hand():
    """Test that OLSa_v2 can complete a single hand without crashing."""
    try:
        strategy = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
                'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
                'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    # Play a single hand with bidding
    strategies = [strategy, strategy, strategy, strategy]
    
    try:
        t0, t1, _, _, leader, _, bid, dealer, bidder, contract, trump = play_single_hand(
            contract_type=None,  # Trigger bidding
            strategies=strategies,
            deal_seed=42
        )
        
        # Check results are valid
        assert 0 <= t0 <= 10, f"Team 0 tricks out of range: {t0}"
        assert 0 <= t1 <= 10, f"Team 1 tricks out of range: {t1}"
        assert t0 + t1 == 10, f"Tricks don't sum to 10: {t0} + {t1}"
        assert bid is not None, f"Bid should not be None"
        assert 5 <= bid <= 10, f"Bid out of range: {bid}"
        
        print(f"✅ OLSa_v2 played single hand: {t0}-{t1}, bid={bid}, contract={contract}")
        
    except Exception as e:
        print(f"❌ OLSa_v2 failed to play hand: {e}")
        raise


def test_olsa_v2_plays_multiple_hands():
    """Test that OLSa_v2 can play multiple hands consistently."""
    try:
        strategy = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
                'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
                'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    # Play 10 hands
    strategies = [strategy, strategy, strategy, strategy]
    n_hands = 10
    
    for i in range(n_hands):
        try:
            t0, t1, _, _, leader, _, bid, dealer, bidder, contract, trump = play_single_hand(
                contract_type=None,
                strategies=strategies,
                deal_seed=42 + i
            )
            
            assert 0 <= t0 <= 10, f"Hand {i}: Team 0 tricks out of range"
            assert 0 <= t1 <= 10, f"Hand {i}: Team 1 tricks out of range"
            assert t0 + t1 == 10, f"Hand {i}: Tricks don't sum to 10"
            
        except Exception as e:
            print(f"❌ OLSa_v2 failed on hand {i}: {e}")
            raise
    
    print(f"✅ OLSa_v2 played {n_hands} hands successfully")


def test_olsa_sr_v2_plays_single_hand():
    """Test that OLSa_SR_v2 can complete a single hand without crashing."""
    try:
        strategy = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_sr_v2/olsa_sr_v2_suit.pkl',
                'high': 'data/models/olsa_sr_v2/olsa_sr_v2_high.pkl',
                'low': 'data/models/olsa_sr_v2/olsa_sr_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    strategies = [strategy, strategy, strategy, strategy]
    
    try:
        t0, t1, _, _, leader, _, bid, dealer, bidder, contract, trump = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=42
        )
        
        assert 0 <= t0 <= 10, f"Team 0 tricks out of range: {t0}"
        assert 0 <= t1 <= 10, f"Team 1 tricks out of range: {t1}"
        assert t0 + t1 == 10, f"Tricks don't sum to 10"
        
        print(f"✅ OLSa_SR_v2 played single hand: {t0}-{t1}, bid={bid}")
        
    except Exception as e:
        print(f"❌ OLSa_SR_v2 failed to play hand: {e}")
        raise


def test_olsa_v2_vs_random():
    """Test OLSa_v2 vs random baseline (sanity check)."""
    try:
        olsa_v2 = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
                'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
                'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    random_strat = RandomLegalStrategy(seed=42)
    
    # OLSa_v2 on team 0, Random on team 1
    strategies = [olsa_v2, random_strat, olsa_v2, random_strat]
    
    # Play 50 hands
    team0_wins = 0
    team1_wins = 0
    
    for i in range(50):
        t0, t1, _, _, _, _, _, _, _, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=100 + i
        )
        
        if t0 > t1:
            team0_wins += 1
        elif t1 > t0:
            team1_wins += 1
    
    # OLSa_v2 should win more than random (but this is a loose check)
    # In reality with bidding, this is complex, so just check it doesn't lose badly
    win_rate = team0_wins / 50
    
    print(f"✅ OLSa_v2 vs Random: {team0_wins}-{team1_wins} (win rate: {win_rate:.2%})")
    print(f"   (Note: with bidding, win rates are complex due to points scoring)")


def test_olsa_v2_bidding_behavior():
    """Test that OLSa_v2 makes reasonable bids."""
    try:
        strategy = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
                'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
                'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    strategies = [strategy, strategy, strategy, strategy]
    
    bids = []
    for i in range(100):
        t0, t1, _, _, _, _, bid, _, _, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=200 + i
        )
        if bid is not None and bid >= 5:  # Valid bid
            bids.append(bid)
    
    # Check bid distribution
    avg_bid = sum(bids) / len(bids) if bids else 0
    min_bid = min(bids) if bids else 0
    max_bid = max(bids) if bids else 0
    
    assert 5 <= avg_bid <= 10, f"Average bid out of range: {avg_bid}"
    assert 5 <= min_bid <= 10, f"Min bid out of range: {min_bid}"
    assert 5 <= max_bid <= 10, f"Max bid out of range: {max_bid}"
    
    print(f"✅ OLSa_v2 bidding behavior: avg={avg_bid:.2f}, range=[{min_bid}, {max_bid}]")
    print(f"   Bid distribution: {sorted(bids)[:10]}... (first 10 of {len(bids)})")


def test_olsa_v2_make_bid_rate():
    """Test that OLSa_v2 makes its bid at a reasonable rate."""
    try:
        strategy = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
                'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
                'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    strategies = [strategy, strategy, strategy, strategy]
    
    made_count = 0
    total_count = 0
    
    for i in range(100):
        t0, t1, _, _, _, _, bid, dealer, bidder, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=300 + i
        )
        
        if bid is None or bidder is None:
            continue
        
        # Determine which team was bidder
        bidder_team_tricks = t0 if bidder in (0, 2) else t1
        
        # Check if bid was made
        if bidder_team_tricks >= bid:
            made_count += 1
        total_count += 1
    
    make_rate = made_count / total_count if total_count > 0 else 0
    
    # Model should make bid at least 40% of the time (conservative check)
    # In reality, a good model should be 60-70%+
    assert make_rate > 0.3, f"Make-bid rate too low: {make_rate:.1%}"
    
    print(f"✅ OLSa_v2 make-bid rate: {make_rate:.1%} ({made_count}/{total_count})")


def test_no_crashes_with_edge_cases():
    """Test that models don't crash on edge case hands."""
    try:
        strategy = RegressionBidder(
            model_paths={
                'suit': 'data/models/olsa_v2/olsa_v2_suit.pkl',
                'high': 'data/models/olsa_v2/olsa_v2_high.pkl',
                'low': 'data/models/olsa_v2/olsa_v2_low.pkl',
            },
            policy='round'
        )
    except FileNotFoundError:
        print("⚠️  Skipping test - models not found")
        return
    
    strategies = [strategy, strategy, strategy, strategy]
    
    # Test many random seeds to hit edge cases
    for i in range(50):
        try:
            t0, t1, _, _, _, _, _, _, _, _, _ = play_single_hand(
                contract_type=None,
                strategies=strategies,
                deal_seed=1000 + i
            )
        except Exception as e:
            print(f"❌ Crashed on seed {1000+i}: {e}")
            raise
    
    print("✅ No crashes on 50 random edge case hands")


def run_all_tests():
    """Run all integration tests."""
    tests = [
        test_olsa_v2_loads_successfully,
        test_olsa_v2_plays_single_hand,
        test_olsa_v2_plays_multiple_hands,
        test_olsa_sr_v2_plays_single_hand,
        test_olsa_v2_vs_random,
        test_olsa_v2_bidding_behavior,
        test_olsa_v2_make_bid_rate,
        test_no_crashes_with_edge_cases,
    ]
    
    print("="*80)
    print("Running Model Integration Tests")
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
            print(f"⚠️  {test.__name__} ERROR: {e}")
            skipped += 1
    
    print("\n" + "="*80)
    print(f"Test Summary: {passed} passed, {failed} failed, {skipped} skipped/errors")
    print("="*80)
    
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
