"""Tests for web.ai_manager — browser AI roster management."""

from __future__ import annotations

import pytest

from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import (
    ActionValueBidder,
    BidAction,
    BiddingObservation,
    BiddingPolicy,
    GBTActionValueBidder,
)
from bid_euchre.strategy.greedy import GluttonStrategy
from tests.unit.hosted_play.conftest import create_browser_ai_test_artifacts
from web.ai_manager import AIManager, ModelInfo
from web.config import HostedPlayConfig


class _DummyBidder(BiddingPolicy):
    def __init__(self) -> None:
        super().__init__(name="dummy")

    def choose_bid(self, obs: BiddingObservation) -> BidAction:
        return BidAction.pass_bid()


class _DummyStrategy(Strategy):
    def choose_card(self, *args, **kwargs) -> int:
        return 0


class TestModelInfo:
    def test_fields(self):
        info = ModelInfo(
            id="test",
            name="Test Model",
            description="A test model.",
            bidding_policy=_DummyBidder(),
            play_strategy=_DummyStrategy(),
        )
        assert info.id == "test"
        assert info.name == "Test Model"
        assert info.description == "A test model."
        assert isinstance(info.bidding_policy, BiddingPolicy)
        assert isinstance(info.play_strategy, Strategy)


class TestBrowserRoster:
    def test_browser_roster_loads_olsa_and_bud_bot(self, tmp_path):
        olsa_artifact, gbt_artifact = create_browser_ai_test_artifacts(tmp_path)
        mgr = AIManager(
            HostedPlayConfig(
                olsa_artifact=olsa_artifact,
                gbt_artifact=gbt_artifact,
            )
        )

        assert list(mgr.available_models) == ["bud_bot", "olsa"]

        olsa = mgr.get_model_info("olsa")
        assert olsa.name == "OLSa (Easy)"
        assert isinstance(olsa.bidding_policy, ActionValueBidder)
        assert isinstance(olsa.play_strategy, GluttonStrategy)

        bud_bot = mgr.get_model_info("bud_bot")
        assert bud_bot.name == "Bud Bot"
        assert isinstance(bud_bot.bidding_policy, GBTActionValueBidder)
        assert isinstance(bud_bot.play_strategy, GluttonStrategy)

    def test_list_available_preserves_ui_order(self, tmp_path):
        olsa_artifact, gbt_artifact = create_browser_ai_test_artifacts(tmp_path)
        mgr = AIManager(
            HostedPlayConfig(
                olsa_artifact=olsa_artifact,
                gbt_artifact=gbt_artifact,
            )
        )
        assert [model.id for model in mgr.list_available()] == ["bud_bot", "olsa"]

    def test_default_model_must_be_in_roster(self, tmp_path):
        olsa_artifact, gbt_artifact = create_browser_ai_test_artifacts(tmp_path)
        with pytest.raises(RuntimeError, match="Default model"):
            AIManager(
                HostedPlayConfig(
                    default_model_id="not_a_model",
                    olsa_artifact=olsa_artifact,
                    gbt_artifact=gbt_artifact,
                )
            )

    def test_missing_olsa_fails_startup(self, tmp_path):
        _, gbt_artifact = create_browser_ai_test_artifacts(tmp_path)
        with pytest.raises(RuntimeError, match="Missing: \\['olsa'\\]"):
            AIManager(
                HostedPlayConfig(
                    default_model_id="bud_bot",
                    olsa_artifact="missing-olsa.json",
                    gbt_artifact=gbt_artifact,
                )
            )

    def test_missing_bud_bot_fails_startup(self, tmp_path):
        olsa_artifact, _ = create_browser_ai_test_artifacts(tmp_path)
        with pytest.raises(RuntimeError, match="Missing: \\['bud_bot'\\]"):
            AIManager(
                HostedPlayConfig(
                    default_model_id="olsa",
                    olsa_artifact=olsa_artifact,
                    gbt_artifact="missing-gbt.json",
                )
            )
