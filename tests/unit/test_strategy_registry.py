"""Tests for strategy registry completeness and lookup."""
import pytest

from bid_euchre.experiments.config import (
    BIDDING_POLICY_REGISTRY,
    BIDDING_REQUIRED_PARAMS,
    PLAY_STRATEGY_REGISTRY,
    STRATEGY_REQUIRED_PARAMS,
    BiddingPolicyConfig,
    StrategyConfig,
)


def test_play_strategy_registry_not_empty():
    """Registry should contain at least the core strategies."""
    assert len(PLAY_STRATEGY_REGISTRY) >= 5


def test_bidding_policy_registry_not_empty():
    """Registry should contain at least the core bidders."""
    assert len(BIDDING_POLICY_REGISTRY) >= 5


def test_unknown_strategy_raises():
    """Unknown strategy class should raise ValueError with helpful message."""
    cfg = StrategyConfig(name="test", class_name="NonexistentStrategy", params={})
    with pytest.raises(ValueError, match="Unknown strategy class"):
        cfg.create_strategy()


def test_unknown_bidding_policy_raises():
    """Unknown bidding policy should raise ValueError with helpful message."""
    cfg = BiddingPolicyConfig(name="test", class_name="NonexistentBidder", params={})
    with pytest.raises(ValueError, match="Unknown bidding policy class"):
        cfg.create_bidding_policy()


def test_missing_required_strategy_param():
    """Missing required param should raise ValueError."""
    cfg = StrategyConfig(name="test", class_name="ArtifactGreedyStrategy", params={})
    with pytest.raises(ValueError, match="requires 'artifact_path'"):
        cfg.create_strategy()


def test_missing_required_bidding_param():
    """Missing required param should raise ValueError."""
    cfg = BiddingPolicyConfig(name="test", class_name="FixedBidder", params={})
    with pytest.raises(ValueError, match="requires 'n'"):
        cfg.create_bidding_policy()


def test_backward_compat_alias():
    """StrictRaiserBidder should resolve to StrictHellRaiser."""
    assert BIDDING_POLICY_REGISTRY["StrictRaiserBidder"] is BIDDING_POLICY_REGISTRY["StrictHellRaiser"]


def test_greedy_strategy_creates():
    """Simple strategy should create without params."""
    cfg = StrategyConfig(name="test_greedy", class_name="GreedyStrategy", params={})
    strategy = cfg.create_strategy()
    assert strategy is not None


def test_always_pass_bidder_creates():
    """Simple bidder should create without params."""
    cfg = BiddingPolicyConfig(name="test_pass", class_name="AlwaysPassBidder", params={})
    bidder = cfg.create_bidding_policy()
    assert bidder is not None


def test_required_params_keys_are_in_registry():
    """All entries in required params dicts must be in their respective registries."""
    for name in STRATEGY_REQUIRED_PARAMS:
        assert name in PLAY_STRATEGY_REGISTRY, f"{name} in STRATEGY_REQUIRED_PARAMS but not in registry"
    for name in BIDDING_REQUIRED_PARAMS:
        assert name in BIDDING_POLICY_REGISTRY, f"{name} in BIDDING_REQUIRED_PARAMS but not in registry"
