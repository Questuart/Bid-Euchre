"""Tests for web.config — environment settings and config override."""

from __future__ import annotations

import pytest

from web.config import HostedPlayConfig, get_config, override_config

# ---------------------------------------------------------------------------
# HostedPlayConfig defaults
# ---------------------------------------------------------------------------


class TestHostedPlayConfigDefaults:
    """Verify default values on the frozen dataclass."""

    def test_default_database_url(self):
        cfg = HostedPlayConfig()
        assert cfg.database_url == "sqlite:///hosted_play.db"

    def test_default_model_id(self):
        cfg = HostedPlayConfig()
        assert cfg.default_model_id == "heuristic"

    def test_default_hybrid_olsa_artifact(self):
        cfg = HostedPlayConfig()
        assert cfg.hybrid_olsa_artifact is None

    def test_default_debug(self):
        cfg = HostedPlayConfig()
        assert cfg.debug is False

    def test_frozen(self):
        cfg = HostedPlayConfig()
        with pytest.raises(AttributeError):
            cfg.debug = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# from_env()
# ---------------------------------------------------------------------------


class TestFromEnv:
    """Verify from_env() reads environment variables correctly."""

    def test_reads_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == "postgresql://localhost/test"

    def test_reads_default_model_id(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_MODEL_ID", "hybrid_olsa")
        cfg = HostedPlayConfig.from_env()
        assert cfg.default_model_id == "hybrid_olsa"

    def test_reads_hybrid_olsa_artifact(self, monkeypatch):
        monkeypatch.setenv("HYBRID_OLSA_ARTIFACT", "/path/to/artifact.json")
        cfg = HostedPlayConfig.from_env()
        assert cfg.hybrid_olsa_artifact == "/path/to/artifact.json"

    def test_debug_true_values(self, monkeypatch):
        for val in ("1", "true", "yes", "True", "YES"):
            monkeypatch.setenv("DEBUG", val)
            cfg = HostedPlayConfig.from_env()
            assert cfg.debug is True, f"Expected True for DEBUG={val!r}"

    def test_debug_false_values(self, monkeypatch):
        for val in ("0", "false", "no", ""):
            monkeypatch.setenv("DEBUG", val)
            cfg = HostedPlayConfig.from_env()
            assert cfg.debug is False, f"Expected False for DEBUG={val!r}"

    def test_missing_env_vars_use_defaults(self, monkeypatch):
        # Clear relevant env vars
        for key in (
            "DATABASE_URL",
            "DEFAULT_MODEL_ID",
            "HYBRID_OLSA_ARTIFACT",
            "DEBUG",
        ):
            monkeypatch.delenv(key, raising=False)
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == "sqlite:///hosted_play.db"
        assert cfg.default_model_id == "heuristic"
        assert cfg.hybrid_olsa_artifact is None
        assert cfg.debug is False


# ---------------------------------------------------------------------------
# override_config / get_config
# ---------------------------------------------------------------------------


class TestOverrideGetConfig:
    """Verify the module-level config override mechanism."""

    def test_get_config_returns_env_by_default(self, monkeypatch):
        # Ensure no override is active
        override_config(None)
        for key in (
            "DATABASE_URL",
            "DEFAULT_MODEL_ID",
            "HYBRID_OLSA_ARTIFACT",
            "DEBUG",
        ):
            monkeypatch.delenv(key, raising=False)
        cfg = get_config()
        assert cfg.database_url == "sqlite:///hosted_play.db"

    def test_override_config_replaces_env(self):
        custom = HostedPlayConfig(database_url="sqlite:///custom.db")
        override_config(custom)
        try:
            cfg = get_config()
            assert cfg.database_url == "sqlite:///custom.db"
        finally:
            override_config(None)

    def test_override_config_none_clears(self):
        custom = HostedPlayConfig(database_url="sqlite:///custom.db")
        override_config(custom)
        override_config(None)
        cfg = get_config()
        # Should fall back to env/defaults
        assert (
            cfg.database_url != "sqlite:///custom.db"
            or cfg == HostedPlayConfig.from_env()
        )

    def test_round_trip(self):
        original = HostedPlayConfig(
            database_url="sqlite:///test.db",
            default_model_id="hybrid_olsa",
            debug=True,
        )
        override_config(original)
        try:
            retrieved = get_config()
            assert retrieved.database_url == "sqlite:///test.db"
            assert retrieved.default_model_id == "hybrid_olsa"
            assert retrieved.debug is True
        finally:
            override_config(None)
