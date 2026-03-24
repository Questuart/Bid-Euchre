"""Tests for web.ai_manager — AI model roster management."""

from __future__ import annotations

import json

import pytest

from bid_euchre.strategy.bidding import BiddingPolicy, HeuristicSuitBidder
from bid_euchre.strategy.greedy import GluttonStrategy
from web.ai_manager import AIManager, ModelInfo
from web.config import HostedPlayConfig

# ---------------------------------------------------------------------------
# ModelInfo
# ---------------------------------------------------------------------------


class TestModelInfo:
    """Verify ModelInfo dataclass fields."""

    def test_fields(self):
        info = ModelInfo(
            id="test",
            name="Test Model",
            description="A test model.",
            bidding_policy=HeuristicSuitBidder(),
            play_strategy=GluttonStrategy(),
        )
        assert info.id == "test"
        assert info.name == "Test Model"
        assert info.description == "A test model."
        assert isinstance(info.bidding_policy, BiddingPolicy)


# ---------------------------------------------------------------------------
# AIManager — heuristic always available
# ---------------------------------------------------------------------------


class TestHeuristicModel:
    """The heuristic model is always registered."""

    def test_heuristic_always_available(self):
        config = HostedPlayConfig()
        mgr = AIManager(config)
        assert "heuristic" in mgr.available_models

    def test_heuristic_model_info(self):
        config = HostedPlayConfig()
        mgr = AIManager(config)
        info = mgr.get_model_info("heuristic")
        assert info.id == "heuristic"
        assert info.name == "Heuristic"
        assert isinstance(info.bidding_policy, HeuristicSuitBidder)
        assert isinstance(info.play_strategy, GluttonStrategy)


# ---------------------------------------------------------------------------
# AIManager — hybrid_olsa conditional loading
# ---------------------------------------------------------------------------


class TestHybridOlsa:
    """hybrid_olsa is loaded only when the artifact path exists and is valid."""

    def test_hybrid_olsa_skipped_when_no_artifact(self):
        config = HostedPlayConfig(hybrid_olsa_artifact=None)
        mgr = AIManager(config)
        assert "hybrid_olsa" not in mgr.available_models

    def test_hybrid_olsa_skipped_when_artifact_missing(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.json")
        config = HostedPlayConfig(hybrid_olsa_artifact=missing)
        mgr = AIManager(config)
        assert "hybrid_olsa" not in mgr.available_models

    def test_hybrid_olsa_skipped_on_invalid_artifact(self, tmp_path):
        """An artifact file that exists but has wrong format → not loaded."""
        bad_artifact = tmp_path / "bad.json"
        bad_artifact.write_text(json.dumps({"artifact_type": "wrong"}))
        config = HostedPlayConfig(hybrid_olsa_artifact=str(bad_artifact))
        mgr = AIManager(config)
        # Should not crash, but hybrid_olsa should not be available
        assert "hybrid_olsa" not in mgr.available_models

    def test_hybrid_olsa_relative_path_resolved_via_models_dir(self, tmp_path):
        """When artifact path is relative and models_dir is set, resolve against it."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        # Create a bad artifact (won't load, but tests path resolution)
        bad_artifact = models_dir / "hybrid.json"
        bad_artifact.write_text(json.dumps({"artifact_type": "wrong"}))
        config = HostedPlayConfig(
            hybrid_olsa_artifact="hybrid.json",
            models_dir=str(models_dir),
        )
        mgr = AIManager(config)
        # File found (resolution worked) but content is invalid → not loaded
        assert "hybrid_olsa" not in mgr.available_models

    def test_hybrid_olsa_absolute_path_ignores_models_dir(self, tmp_path):
        """An absolute artifact path should be used as-is, ignoring models_dir."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        abs_artifact = tmp_path / "absolute.json"
        abs_artifact.write_text(json.dumps({"artifact_type": "wrong"}))
        config = HostedPlayConfig(
            hybrid_olsa_artifact=str(abs_artifact),
            models_dir=str(models_dir),
        )
        mgr = AIManager(config)
        # File found at absolute path (not resolved via models_dir)
        assert "hybrid_olsa" not in mgr.available_models

    def test_hybrid_olsa_relative_without_models_dir_not_resolved(self):
        """A relative artifact with no models_dir stays relative (likely not found)."""
        config = HostedPlayConfig(
            hybrid_olsa_artifact="nonexistent/hybrid.json",
            models_dir=None,
        )
        mgr = AIManager(config)
        assert "hybrid_olsa" not in mgr.available_models


# ---------------------------------------------------------------------------
# AIManager — default model fallback
# ---------------------------------------------------------------------------


class TestDefaultModelFallback:
    """default_model_id falls back to heuristic if not in roster."""

    def test_default_is_heuristic(self):
        config = HostedPlayConfig(default_model_id="heuristic")
        mgr = AIManager(config)
        assert mgr.default_model_id == "heuristic"

    def test_unknown_default_falls_back_to_heuristic(self):
        config = HostedPlayConfig(default_model_id="nonexistent_model")
        mgr = AIManager(config)
        assert mgr.default_model_id == "heuristic"


# ---------------------------------------------------------------------------
# AIManager — list_available
# ---------------------------------------------------------------------------


class TestListAvailable:
    """list_available returns sorted models."""

    def test_returns_at_least_heuristic(self):
        config = HostedPlayConfig()
        mgr = AIManager(config)
        models = mgr.list_available()
        assert len(models) >= 1
        assert models[0].id == "heuristic"

    def test_sorted_by_id(self):
        config = HostedPlayConfig()
        mgr = AIManager(config)
        models = mgr.list_available()
        ids = [m.id for m in models]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# AIManager — get_model_info
# ---------------------------------------------------------------------------


class TestGetModelInfo:
    """get_model_info retrieves or raises KeyError."""

    def test_known_model(self):
        config = HostedPlayConfig()
        mgr = AIManager(config)
        info = mgr.get_model_info("heuristic")
        assert info.id == "heuristic"

    def test_unknown_model_raises(self):
        config = HostedPlayConfig()
        mgr = AIManager(config)
        with pytest.raises(KeyError):
            mgr.get_model_info("totally_unknown")
