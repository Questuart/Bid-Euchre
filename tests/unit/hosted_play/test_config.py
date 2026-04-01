"""Tests for web.config — environment settings and config override."""

from __future__ import annotations

import pytest

from web.config import (
    HostedPlayConfig,
    _parse_origins,
    get_config,
    override_config,
)

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
        assert cfg.default_model_id == "bud_bot"

    def test_default_olsa_artifact(self):
        cfg = HostedPlayConfig()
        assert (
            cfg.olsa_artifact
            == "data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json"
        )

    def test_default_gbt_artifact(self):
        cfg = HostedPlayConfig()
        assert (
            cfg.gbt_artifact
            == "data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json"
        )

    def test_default_debug(self):
        cfg = HostedPlayConfig()
        assert cfg.debug is False

    def test_default_secret_key_generated(self):
        cfg = HostedPlayConfig()
        # Dev fallback starts with "dev-insecure-" and is non-empty
        assert cfg.secret_key.startswith("dev-insecure-")
        assert len(cfg.secret_key) > len("dev-insecure-")

    def test_default_secret_key_unique_per_instance(self):
        # Each default construction should produce a different key
        cfg1 = HostedPlayConfig()
        cfg2 = HostedPlayConfig()
        assert cfg1.secret_key != cfg2.secret_key

    def test_default_allowed_origins(self):
        cfg = HostedPlayConfig()
        assert cfg.allowed_origins == ["*"]

    def test_default_app_url(self):
        cfg = HostedPlayConfig()
        assert cfg.app_url == "http://localhost:8000"

    def test_default_models_dir(self):
        cfg = HostedPlayConfig()
        assert cfg.models_dir is None

    def test_frozen(self):
        cfg = HostedPlayConfig()
        with pytest.raises(AttributeError):
            cfg.debug = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _parse_origins helper
# ---------------------------------------------------------------------------


class TestParseOrigins:
    """Verify comma-separated origin parsing."""

    def test_single_origin(self):
        assert _parse_origins("https://example.com") == ["https://example.com"]

    def test_multiple_origins(self):
        result = _parse_origins("https://a.com,https://b.com,https://c.com")
        assert result == ["https://a.com", "https://b.com", "https://c.com"]

    def test_strips_whitespace(self):
        result = _parse_origins(" https://a.com , https://b.com ")
        assert result == ["https://a.com", "https://b.com"]

    def test_drops_empty_entries(self):
        result = _parse_origins("https://a.com,,https://b.com,")
        assert result == ["https://a.com", "https://b.com"]

    def test_wildcard(self):
        assert _parse_origins("*") == ["*"]

    def test_empty_string(self):
        assert _parse_origins("") == []


# ---------------------------------------------------------------------------
# from_env()
# ---------------------------------------------------------------------------


class TestFromEnv:
    """Verify from_env() reads environment variables correctly."""

    def _clear_all_config_env(self, monkeypatch):
        """Helper to unset all config-related env vars."""
        for key in (
            "DATABASE_URL",
            "SECRET_KEY",
            "ALLOWED_ORIGINS",
            "APP_URL",
            "DEFAULT_MODEL_ID",
            "OLSA_ARTIFACT",
            "GBT_ARTIFACT",
            "MODELS_DIR",
            "DEBUG",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_reads_database_url(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == "postgresql://localhost/test"

    def test_reads_default_model_id(self, monkeypatch):
        monkeypatch.setenv("DEFAULT_MODEL_ID", "olsa")
        cfg = HostedPlayConfig.from_env()
        assert cfg.default_model_id == "olsa"

    def test_reads_olsa_artifact(self, monkeypatch):
        monkeypatch.setenv("OLSA_ARTIFACT", "/path/to/artifact.json")
        cfg = HostedPlayConfig.from_env()
        assert cfg.olsa_artifact == "/path/to/artifact.json"

    def test_reads_gbt_artifact(self, monkeypatch):
        monkeypatch.setenv("GBT_ARTIFACT", "/path/to/gbt.json")
        cfg = HostedPlayConfig.from_env()
        assert cfg.gbt_artifact == "/path/to/gbt.json"

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

    # -- New production fields ------------------------------------------

    def test_reads_secret_key(self, monkeypatch):
        monkeypatch.setenv("SECRET_KEY", "super-secret-prod-key")
        cfg = HostedPlayConfig.from_env()
        assert cfg.secret_key == "super-secret-prod-key"

    def test_secret_key_fallback_is_dev_insecure(self, monkeypatch):
        self._clear_all_config_env(monkeypatch)
        cfg = HostedPlayConfig.from_env()
        assert cfg.secret_key.startswith("dev-insecure-")

    def test_reads_allowed_origins(self, monkeypatch):
        monkeypatch.setenv(
            "ALLOWED_ORIGINS", "https://app.example.com,https://staging.example.com"
        )
        cfg = HostedPlayConfig.from_env()
        assert cfg.allowed_origins == [
            "https://app.example.com",
            "https://staging.example.com",
        ]

    def test_allowed_origins_default_wildcard(self, monkeypatch):
        self._clear_all_config_env(monkeypatch)
        cfg = HostedPlayConfig.from_env()
        assert cfg.allowed_origins == ["*"]

    def test_reads_app_url(self, monkeypatch):
        monkeypatch.setenv("APP_URL", "https://bideuchre.example.com")
        cfg = HostedPlayConfig.from_env()
        assert cfg.app_url == "https://bideuchre.example.com"

    def test_app_url_default(self, monkeypatch):
        self._clear_all_config_env(monkeypatch)
        cfg = HostedPlayConfig.from_env()
        assert cfg.app_url == "http://localhost:8000"

    def test_reads_models_dir(self, monkeypatch):
        monkeypatch.setenv("MODELS_DIR", "/opt/models")
        cfg = HostedPlayConfig.from_env()
        assert cfg.models_dir == "/opt/models"

    def test_models_dir_default_none(self, monkeypatch):
        self._clear_all_config_env(monkeypatch)
        cfg = HostedPlayConfig.from_env()
        assert cfg.models_dir is None

    def test_missing_env_vars_use_defaults(self, monkeypatch):
        # Clear relevant env vars
        self._clear_all_config_env(monkeypatch)
        cfg = HostedPlayConfig.from_env()
        assert cfg.database_url == "sqlite:///hosted_play.db"
        assert cfg.secret_key.startswith("dev-insecure-")
        assert cfg.allowed_origins == ["*"]
        assert cfg.app_url == "http://localhost:8000"
        assert cfg.default_model_id == "bud_bot"
        assert (
            cfg.olsa_artifact
            == "data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json"
        )
        assert (
            cfg.gbt_artifact
            == "data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json"
        )
        assert cfg.models_dir is None
        assert cfg.debug is False


# ---------------------------------------------------------------------------
# override_config / get_config
# ---------------------------------------------------------------------------


class TestOverrideGetConfig:
    """Verify the module-level config override mechanism."""

    def _clear_all_config_env(self, monkeypatch):
        """Helper to unset all config-related env vars."""
        for key in (
            "DATABASE_URL",
            "SECRET_KEY",
            "ALLOWED_ORIGINS",
            "APP_URL",
            "DEFAULT_MODEL_ID",
            "OLSA_ARTIFACT",
            "GBT_ARTIFACT",
            "MODELS_DIR",
            "DEBUG",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_get_config_returns_env_by_default(self, monkeypatch):
        # Ensure no override is active
        override_config(None)
        self._clear_all_config_env(monkeypatch)
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
            default_model_id="olsa",
            debug=True,
        )
        override_config(original)
        try:
            retrieved = get_config()
            assert retrieved.database_url == "sqlite:///test.db"
            assert retrieved.default_model_id == "olsa"
            assert retrieved.debug is True
        finally:
            override_config(None)

    def test_round_trip_new_fields(self):
        """Verify new production fields survive override round-trip."""
        original = HostedPlayConfig(
            secret_key="test-key-123",
            allowed_origins=["https://test.example.com"],
            app_url="https://test.example.com",
            models_dir="/tmp/models",
        )
        override_config(original)
        try:
            retrieved = get_config()
            assert retrieved.secret_key == "test-key-123"
            assert retrieved.allowed_origins == ["https://test.example.com"]
            assert retrieved.app_url == "https://test.example.com"
            assert retrieved.models_dir == "/tmp/models"
        finally:
            override_config(None)
