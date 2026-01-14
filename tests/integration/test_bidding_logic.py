from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.baselines import RandomLegalStrategy

# REMOVED: Dummy model paths for testing (legacy pickle path)

# REMOVED: test_regression_bidder_policy (legacy pickle path)

# REMOVED: test_fixed_bid_fred (legacy pickle path)

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

# REMOVED: test_partner_pass_rule (legacy pickle path)

# REMOVED: test_bid_winner_leads (legacy pickle path)

if __name__ == "__main__":
    print("Running tests manually...")
    try:
        test_misdeal_logic()
        print("✅ test_misdeal_logic PASSED")

        print("\n🎉 ALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
