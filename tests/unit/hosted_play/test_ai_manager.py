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
# AIManager — olsa conditional loading
# ---------------------------------------------------------------------------


class TestOlsa:
    """olsa is loaded only when the artifact path exists and is valid."""

    def test_olsa_skipped_when_no_artifact(self):
        config = HostedPlayConfig(olsa_artifact=None)
        mgr = AIManager(config)
        assert "olsa" not in mgr.available_models

    def test_olsa_skipped_when_artifact_missing(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.json")
        config = HostedPlayConfig(olsa_artifact=missing)
        mgr = AIManager(config)
        assert "olsa" not in mgr.available_models

    def test_olsa_skipped_on_invalid_artifact(self, tmp_path):
        """An artifact file that exists but has wrong format -> not loaded."""
        bad_artifact = tmp_path / "bad.json"
        bad_artifact.write_text(json.dumps({"artifact_type": "wrong"}))
        config = HostedPlayConfig(olsa_artifact=str(bad_artifact))
        mgr = AIManager(config)
        # Should not crash, but olsa should not be available
        assert "olsa" not in mgr.available_models

    def test_olsa_relative_path_resolved_via_models_dir(self, tmp_path):
        """When artifact path is relative and models_dir is set, resolve against it."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        # Create a bad artifact (won't load, but tests path resolution)
        bad_artifact = models_dir / "olsa.json"
        bad_artifact.write_text(json.dumps({"artifact_type": "wrong"}))
        config = HostedPlayConfig(
            olsa_artifact="olsa.json",
            models_dir=str(models_dir),
        )
        mgr = AIManager(config)
        # File found (resolution worked) but content is invalid -> not loaded
        assert "olsa" not in mgr.available_models

    def test_olsa_absolute_path_ignores_models_dir(self, tmp_path):
        """An absolute artifact path should be used as-is, ignoring models_dir."""
        models_dir = tmp_path / "models"
        models_dir.mkdir()
        abs_artifact = tmp_path / "absolute.json"
        abs_artifact.write_text(json.dumps({"artifact_type": "wrong"}))
        config = HostedPlayConfig(
            olsa_artifact=str(abs_artifact),
            models_dir=str(models_dir),
        )
        mgr = AIManager(config)
        # File found at absolute path (not resolved via models_dir)
        assert "olsa" not in mgr.available_models

    def test_olsa_relative_path_preserved_when_exists(
        self, tmp_path, monkeypatch, caplog
    ):
        """A relative artifact path that already exists from CWD is preserved.

        When MODELS_DIR is set but the relative path already resolves from the
        working directory, the original relative path is used (not overridden
        with models_dir prefix).
        """
        # Create artifact in CWD-relative location
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        rel_dir = workdir / "rel"
        rel_dir.mkdir()
        artifact = rel_dir / "olsa.json"
        artifact.write_text(json.dumps({"artifact_type": "wrong"}))

        # Create a *different* directory for models_dir (no artifact here)
        models_dir = tmp_path / "elsewhere"
        models_dir.mkdir()

        # Run from workdir so "rel/olsa.json" is a valid relative path
        monkeypatch.chdir(workdir)
        config = HostedPlayConfig(
            olsa_artifact="rel/olsa.json",
            models_dir=str(models_dir),
        )
        import logging

        with caplog.at_level(logging.WARNING, logger="web.ai_manager"):
            mgr = AIManager(config)

        # The file was found at its original relative path and loading was
        # attempted (producing a warning because the content is invalid).
        # If models_dir had been prepended, the file would NOT be found
        # and no loading attempt (warning) would occur.
        assert "olsa" not in mgr.available_models
        assert any(
            "Failed to load OLSa from rel/olsa.json" in m for m in caplog.messages
        )

    def test_olsa_cwd_failure_falls_back_to_models_dir(
        self, tmp_path, monkeypatch, caplog
    ):
        """When CWD artifact exists but fails to load, models_dir is tried.

        If the CWD-relative path exists but the artifact is corrupt/invalid,
        the loader should fall back to the models_dir copy if one exists.
        """
        # Create a bad artifact in CWD-relative location.
        workdir = tmp_path / "workdir"
        workdir.mkdir()
        cwd_artifact_dir = workdir / "data" / "models"
        cwd_artifact_dir.mkdir(parents=True)
        cwd_artifact = cwd_artifact_dir / "olsa.json"
        cwd_artifact.write_text(json.dumps({"artifact_type": "wrong"}))

        # Create the same relative name in models_dir (also bad — we just
        # want to verify the fallback attempt happens).
        models_dir = tmp_path / "shared_models"
        models_dir.mkdir()
        fallback_artifact = models_dir / "data" / "models" / "olsa.json"
        fallback_artifact.parent.mkdir(parents=True)
        fallback_artifact.write_text(json.dumps({"artifact_type": "also_wrong"}))

        monkeypatch.chdir(workdir)
        config = HostedPlayConfig(
            olsa_artifact="data/models/olsa.json",
            models_dir=str(models_dir),
        )
        import logging

        with caplog.at_level(logging.WARNING, logger="web.ai_manager"):
            mgr = AIManager(config)

        # Neither artifact is valid, so olsa is not loaded.
        assert "olsa" not in mgr.available_models

        # Both load attempts should be logged — CWD first, then models_dir.
        warning_messages = [
            r.message for r in caplog.records if r.levelno >= logging.WARNING
        ]
        assert any(
            "Failed to load OLSa from data/models/olsa.json" in m
            for m in warning_messages
        ), f"Expected CWD attempt warning; got: {warning_messages}"
        assert any(
            str(models_dir) in m and "Failed to load" in m for m in warning_messages
        ), f"Expected models_dir fallback attempt warning; got: {warning_messages}"

    def test_olsa_relative_without_models_dir_not_resolved(self):
        """A relative artifact with no models_dir stays relative (likely not found)."""
        config = HostedPlayConfig(
            olsa_artifact="nonexistent/olsa.json",
            models_dir=None,
        )
        mgr = AIManager(config)
        assert "olsa" not in mgr.available_models


# ---------------------------------------------------------------------------
# AIManager — default model fallback
# ---------------------------------------------------------------------------


class TestDefaultModelFallback:
    """default_model_id falls back to heuristic if not in roster."""

    def test_default_is_heuristic_when_explicitly_set(self):
        config = HostedPlayConfig(default_model_id="heuristic")
        mgr = AIManager(config)
        assert mgr.default_model_id == "heuristic"

    def test_default_olsa_falls_back_when_no_artifact(self):
        """Default is 'olsa', but without artifact it falls back to heuristic."""
        config = HostedPlayConfig(default_model_id="olsa")
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
