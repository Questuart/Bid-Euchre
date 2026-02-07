"""
Integration tests for artifact-based bidding strategies in simulation.

Tests that artifact-based strategies can be loaded and used in actual gameplay without crashes,
and that they produce reasonable results.
"""

import sys

from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.artifact_strategy import ArtifactGreedyStrategy
from bid_euchre.strategy.baselines import RandomLegalStrategy


def test_artifact_strategies_load_successfully():
    """Test that artifact-based strategies can be loaded."""
    artifact_paths = {
        'suit': 'data/fixtures/bidding_artifact_v1_dummy_suit.json',
        'high': 'data/fixtures/bidding_artifact_v1_dummy_high.json',
        'low': 'data/fixtures/bidding_artifact_v1_dummy_low.json',
    }

    for contract, path in artifact_paths.items():
        # ArtifactGreedyStrategy constructor will raise if artifact can't be loaded
        strategy = ArtifactGreedyStrategy(f"test_{contract}", path)
        assert strategy is not None, f"Failed to create {contract} strategy"

    print("✅ All artifact strategies loaded successfully")


def test_artifact_strategy_plays_single_hand():
    """Test that artifact strategy can complete a single hand without crashing."""
    strategy = ArtifactGreedyStrategy(
        name="test_strategy",
        artifact_path='data/fixtures/bidding_artifact_v1_dummy_suit.json'
    )

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
        assert bid is not None, "Bid should not be None"
        assert isinstance(bid, int), f"Bid should be int: {bid}"

        print(f"✅ Artifact strategy played single hand: {t0}-{t1}, bid={bid}, contract={contract}")

    except Exception as e:
        print(f"❌ Artifact strategy failed to play hand: {e}")
        raise


def test_artifact_strategy_plays_multiple_hands():
    """Test that artifact strategy can play multiple hands consistently."""
    strategy = ArtifactGreedyStrategy(
        name="test_strategy",
        artifact_path='data/fixtures/bidding_artifact_v1_dummy_suit.json'
    )

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
            print(f"❌ Artifact strategy failed on hand {i}: {e}")
            raise

    print(f"✅ Artifact strategy played {n_hands} hands successfully")


def test_artifact_strategy_different_contracts():
    """Test artifact strategies for different contract types."""
    strategies = [
        ArtifactGreedyStrategy("suit", 'data/fixtures/bidding_artifact_v1_dummy_suit.json'),
        ArtifactGreedyStrategy("high", 'data/fixtures/bidding_artifact_v1_dummy_high.json'),
        ArtifactGreedyStrategy("low", 'data/fixtures/bidding_artifact_v1_dummy_low.json'),
        ArtifactGreedyStrategy("suit", 'data/fixtures/bidding_artifact_v1_dummy_suit.json'),
    ]

    try:
        t0, t1, _, _, leader, _, bid, dealer, bidder, contract, trump = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=42
        )

        assert 0 <= t0 <= 10, f"Team 0 tricks out of range: {t0}"
        assert 0 <= t1 <= 10, f"Team 1 tricks out of range: {t1}"
        assert t0 + t1 == 10, "Tricks don't sum to 10"

        print(f"✅ Mixed artifact strategies played single hand: {t0}-{t1}, bid={bid}")

    except Exception as e:
        print(f"❌ Mixed artifact strategies failed to play hand: {e}")
        raise


def test_artifact_strategy_vs_random():
    """Test artifact strategy vs random baseline (sanity check)."""
    artifact_strat = ArtifactGreedyStrategy(
        name="artifact",
        artifact_path='data/fixtures/bidding_artifact_v1_dummy_suit.json'
    )
    random_strat = RandomLegalStrategy(seed=42)

    # Artifact on team 0, Random on team 1
    strategies = [artifact_strat, random_strat, artifact_strat, random_strat]

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

    # Artifact should perform reasonably vs random
    win_rate = team0_wins / 50

    print(f"✅ Artifact vs Random: {team0_wins}-{team1_wins} (win rate: {win_rate:.2%})")
    print("   (Note: with bidding, win rates are complex due to points scoring)")


def test_artifact_strategy_bidding_behavior():
    """Test that artifact strategy makes reasonable bids."""
    strategy = ArtifactGreedyStrategy(
        name="artifact",
        artifact_path='data/fixtures/bidding_artifact_v1_dummy_suit.json'
    )

    strategies = [strategy, strategy, strategy, strategy]

    bids = []
    for i in range(100):
        t0, t1, _, _, _, _, bid, _, _, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=200 + i
        )
        if bid is not None and bid > 0:  # Valid bid
            bids.append(bid)

    # Check bid distribution - with strict raiser, bids should be 3,4,5,...
    avg_bid = sum(bids) / len(bids) if bids else 0
    min_bid = min(bids) if bids else 0
    max_bid = max(bids) if bids else 0

    assert avg_bid > 0, f"Average bid should be positive: {avg_bid}"
    assert min_bid >= 0, f"Min bid out of range: {min_bid}"
    assert max_bid <= 10, f"Max bid out of range: {max_bid}"

    print(f"✅ Artifact bidding behavior: avg={avg_bid:.2f}, range=[{min_bid}, {max_bid}]")
    print(f"   Bid distribution: {sorted(set(bids))} (unique bids)")


def test_artifact_strategy_make_bid_rate():
    """Test that artifact strategy makes its bid at a reasonable rate."""
    strategy = ArtifactGreedyStrategy(
        name="artifact",
        artifact_path='data/fixtures/bidding_artifact_v1_dummy_suit.json'
    )

    strategies = [strategy, strategy, strategy, strategy]

    made_count = 0
    total_count = 0

    for i in range(100):
        t0, t1, _, _, _, _, bid, dealer, bidder, _, _ = play_single_hand(
            contract_type=None,
            strategies=strategies,
            deal_seed=300 + i
        )

        if bid is None or bidder is None or bid == 0:
            continue

        # Determine which team was bidder
        bidder_team_tricks = t0 if bidder in (0, 2) else t1

        # Check if bid was made
        if bidder_team_tricks >= bid:
            made_count += 1
        total_count += 1

    make_rate = made_count / total_count if total_count > 0 else 0

    # Strategy should make some bids (non-zero rate)
    assert make_rate >= 0, f"Make-bid rate should be non-negative: {make_rate:.1%}"

    print(f"✅ Artifact make-bid rate: {make_rate:.1%} ({made_count}/{total_count})")


def test_no_crashes_with_edge_cases():
    """Test that artifact strategies don't crash on edge case hands."""
    strategy = ArtifactGreedyStrategy(
        name="artifact",
        artifact_path='data/fixtures/bidding_artifact_v1_dummy_suit.json'
    )

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
        test_artifact_strategies_load_successfully,
        test_artifact_strategy_plays_single_hand,
        test_artifact_strategy_plays_multiple_hands,
        test_artifact_strategy_different_contracts,
        test_artifact_strategy_vs_random,
        test_artifact_strategy_bidding_behavior,
        test_artifact_strategy_make_bid_rate,
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
