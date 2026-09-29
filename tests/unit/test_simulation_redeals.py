"""Regression tests for simulation aggregation across auction redeals."""

import json

import pytest

from bid_euchre.logging import GameLogger, LogLevel
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.bidding import (
    AlwaysPassBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
)


class AlternatingAuctionPolicy(BiddingPolicy):
    """Alternate complete all-pass auctions with played HIGH contracts."""

    def __init__(self) -> None:
        super().__init__(name="alternating_auction")
        self._calls = 0

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        deal_index = self._calls // 4
        self._calls += 1
        if deal_index % 2 == 0:
            return BidAction.pass_bid()
        if obs.current_high_bid == 0:
            return BidAction.bid(1, "HIGH")
        return BidAction.pass_bid()


def test_all_pass_redeals_do_not_become_team1_wins() -> None:
    result = simulate_many_hands(
        n=3,
        contract_type=None,
        deal_seed=42,
        bidding_policy=AlwaysPassBidder(),
    )

    assert result["hands"] == 3
    assert result["played_hands"] == 0
    assert result["redeals"] == 3
    assert result["avg_team0"] == 0.0
    assert result["avg_team1"] == 0.0
    assert result["win_rate_team0"] is None
    assert result["win_rate_team1"] is None
    assert result["tie_rate"] is None
    assert sum(result["distribution_team0"].values()) == 0
    assert result["player_samples"] == 0
    assert result["score_buckets"] == {}
    assert result["feature_buckets"] == {}

    # Points-per-deal metrics retain all attempted deals in their denominator.
    assert result["avg_points_team0"] == 0.0
    assert result["avg_points_team1"] == 0.0
    assert result["distribution_points_team0"] == {0: 3}
    assert result["distribution_points_team1"] == {0: 3}


def test_mixed_redeals_use_played_hand_denominators() -> None:
    result = simulate_many_hands(
        n=4,
        contract_type=None,
        deal_seed=17,
        bidding_policy=AlternatingAuctionPolicy(),
    )

    assert result["hands"] == 4
    assert result["played_hands"] == 2
    assert result["redeals"] == 2
    assert sum(result["distribution_team0"].values()) == 2
    assert result["avg_team0"] + result["avg_team1"] == 10.0
    assert result["win_rate_team0"] + result["win_rate_team1"] == 1.0
    assert result["player_samples"] == 8
    assert sum(bucket["count"] for bucket in result["score_buckets"].values()) == 8
    for buckets in result["feature_buckets"].values():
        assert sum(bucket["count"] for bucket in buckets.values()) == 8

    # Point distributions and averages still cover all four attempted deals.
    assert sum(result["distribution_points_team0"].values()) == 4
    assert sum(result["distribution_points_team1"].values()) == 4
    points0_sum = sum(
        points * count for points, count in result["distribution_points_team0"].items()
    )
    points1_sum = sum(
        points * count for points, count in result["distribution_points_team1"].items()
    )
    assert result["avg_points_team0"] == points0_sum / 4
    assert result["avg_points_team1"] == points1_sum / 4
    assert result["bidding_points"]["hands_with_bids"] == 2


def test_deal_seed_is_recorded_in_hand_log(tmp_path) -> None:
    log_path = tmp_path / "seeded.jsonl"
    logger = GameLogger(
        run_id="seeded",
        strategy_id="greedy",
        level=LogLevel.HAND,
    ).open(str(log_path))
    try:
        simulate_many_hands(
            n=1,
            contract_type="high",
            seed=None,
            deal_seed=1234,
            logger=logger,
        )
    finally:
        logger.close()

    records = [json.loads(line) for line in log_path.read_text().splitlines()]
    hand_end = next(record for record in records if record["event"] == "hand_end")
    assert hand_end["seed"] == 1234


def test_nonpositive_hand_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be greater than 0"):
        simulate_many_hands(n=0, contract_type="high", seed=42)
