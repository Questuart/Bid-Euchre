import pytest

from bid_euchre.core.cards import Card
from bid_euchre.sim.simulation import play_single_hand
from bid_euchre.strategy.artifact_strategy import ArtifactGreedyStrategy
from bid_euchre.strategy.baselines import RandomLegalStrategy


@pytest.fixture
def dummy_strategies():
    """Create dummy strategies using artifact fixtures for testing."""
    return {
        "suit": ArtifactGreedyStrategy(
            name="dummy_suit",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_suit.json",
        ),
        "high": ArtifactGreedyStrategy(
            name="dummy_high",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_high.json",
        ),
        "low": ArtifactGreedyStrategy(
            name="dummy_low",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_low.json",
        ),
    }


def test_artifact_bidder_bidding_rules(dummy_strategies):
    """Test artifact bidder follows strict raiser imitation rules."""
    # Test initial bidding
    hand = [Card("H", "A")] * 5 + [Card("H", "T")] * 5

    bidder = dummy_strategies["suit"]
    bid, ctype, trump = bidder.decide_bid(hand, 0, None, 2, 0)
    assert bid == 3  # initial_bid from artifact
    assert ctype == "suit"
    assert trump == "S"

    # Test raising behavior - bid should increase when there's a current high bid
    bid, ctype, trump = bidder.decide_bid(hand, 3, None, 2, 0)  # current high bid = 3
    assert bid == 4  # 3 + raise_increment = 4

    # Test max bid limit - should pass when at max
    bid, ctype, trump = bidder.decide_bid(
        hand, 10, None, 2, 0
    )  # current high bid = 10 (max)
    assert bid == 0  # pass when cannot raise further
    # Wait, np.round(3.5) is 4.0.


def test_fixed_bid_fred():
    """Test that fixed bid strategies always bid the fixed amount."""
    hand = [Card("H", "A")] * 10

    fred = ArtifactGreedyStrategy(
        name="fred", artifact_path="data/fixtures/bidding_artifact_v1_dummy_fixed5.json"
    )
    bid, _, _ = fred.decide_bid(hand, 0, None, 2, 0)
    assert bid == 5


def test_misdeal_logic():
    """Verify that if all players pass, it's a misdeal."""
    # RandomLegalStrategy always returns 0 for decide_bid (default)
    strategies = [RandomLegalStrategy() for _ in range(4)]

    t0, t1, scores, feats, leader, hands, bid, _, _, _, _, _ = play_single_hand(
        contract_type=None, strategies=strategies
    )

    assert t0 == 0
    assert t1 == 0
    assert leader == -1
    assert bid == 0


def test_artifact_bidder_initial_bid():
    """Test that artifact bidder makes its initial bid."""
    strategies = [
        RandomLegalStrategy(),  # Seat 0
        RandomLegalStrategy(),  # Seat 1
        RandomLegalStrategy(),  # Seat 2
        ArtifactGreedyStrategy(
            name="bidder",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_fixed12.json",
        ),  # Seat 3 bids 10 initially
    ]

    # Play hand with contract_type=None to trigger bidding
    t0, t1, _, _, leader, _, bid, _, _, _, _, _ = play_single_hand(
        contract_type=None, strategies=strategies, initial_leader=0
    )

    # Seat 3 should win with initial bid of 10
    assert leader == 3
    assert bid == 10


def test_bid_winner_leads():
    """The person who wins the bid must lead the first trick."""
    strategies = [
        ArtifactGreedyStrategy(
            name="bidder",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_fixed6.json",
        ),  # wants to bid 6
        RandomLegalStrategy(),
        RandomLegalStrategy(),
        RandomLegalStrategy(),
    ]

    t0, t1, _, _, leader, _, bid, _, _, _, _, _ = play_single_hand(
        contract_type=None,
        strategies=strategies,
        initial_leader=1,  # make someone else dealer so Seat 0 is LOD
    )

    assert leader == 0
    assert bid == 6


if __name__ == "__main__":
    # Setup dummy strategies
    dummy_strategies = {
        "suit": ArtifactGreedyStrategy(
            name="dummy_suit",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_suit.json",
        ),
        "high": ArtifactGreedyStrategy(
            name="dummy_high",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_high.json",
        ),
        "low": ArtifactGreedyStrategy(
            name="dummy_low",
            artifact_path="data/fixtures/bidding_artifact_v1_dummy_low.json",
        ),
    }

    print("Running tests manually...")
    try:
        test_artifact_bidder_bidding_rules(dummy_strategies)
        print("✅ test_artifact_bidder_bidding_rules PASSED")

        test_fixed_bid_fred()
        print("✅ test_fixed_bid_fred PASSED")

        test_misdeal_logic()
        print("✅ test_misdeal_logic PASSED")

        test_artifact_bidder_initial_bid()
        print("✅ test_artifact_bidder_initial_bid PASSED")

        test_bid_winner_leads()
        print("✅ test_bid_winner_leads PASSED")

        print("\n🎉 ALL TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
