"""Environment settings for the browser-game web application.

Settings are loaded from environment variables with sensible defaults
for local development.  Production deployments override via env vars
(e.g. ``DATABASE_URL`` for Postgres).

Environment variable contract (Expansion §5.2)
-----------------------------------------------

=========================================  =============================================
Variable                                   Purpose
=========================================  =============================================
``DATABASE_URL``                           SQLAlchemy connection string (Postgres in prod)
``SECRET_KEY``                             Session/cookie signing key
``ALLOWED_ORIGINS``                        Comma-separated CORS origin allowlist
``APP_URL``                                Public base URL for generated links
``MODELS_DIR``                             Directory containing model artifacts
``DEFAULT_MODEL_ID``                       Default AI model identifier
``OLSA_ARTIFACT``                          Path to OLSa (ActionValueBidder) artifact file
``GBT_ARTIFACT``                           Path to Bud Bot (GBTActionValueBidder) artifact file
``DEBUG``                                  Enable debug mode (``1``/``true``/``yes``)
=========================================  =============================================
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field

_DEFAULT_OLSA_ARTIFACT = "data/artifacts/arc_d_v2/r3/training_artifact_full_ols_av.json"
_DEFAULT_GBT_ARTIFACT = "data/artifacts/arc_d_v2/r3/training_artifact_gbt_av.json"


def _default_secret_key() -> str:
    """Generate an ephemeral dev-only secret key.

    In production, ``SECRET_KEY`` **must** be set via the environment.
    The generated fallback is unique per process start so that forgetting
    to set the variable in production causes immediate session breakage
    (fail-loud) rather than silently reusing a well-known constant.
    """
    return f"dev-insecure-{secrets.token_hex(16)}"


def _parse_origins(raw: str) -> list[str]:
    """Parse a comma-separated origin allowlist into a list.

    Strips whitespace around each entry and drops empty strings.
    """
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True)
class HostedPlayConfig:
    """Immutable application configuration."""

    # Database ----------------------------------------------------------
    database_url: str = "sqlite:///hosted_play.db"

    # Security ----------------------------------------------------------
    secret_key: str = field(default_factory=_default_secret_key)

    # CORS --------------------------------------------------------------
    allowed_origins: list[str] = field(default_factory=lambda: ["*"])

    # App URL -----------------------------------------------------------
    app_url: str = "http://localhost:8000"

    # AI model roster ---------------------------------------------------
    default_model_id: str = "bud_bot"
    olsa_artifact: str | None = _DEFAULT_OLSA_ARTIFACT
    gbt_artifact: str | None = _DEFAULT_GBT_ARTIFACT
    models_dir: str | None = None

    # Testing -----------------------------------------------------------
    # When set, forces deterministic match seeding in select_ai.
    # Used by browser tests for reproducible AI decisions.
    test_seed: int | None = None

    # App ---------------------------------------------------------------
    debug: bool = False

    @classmethod
    def from_env(cls) -> HostedPlayConfig:
        """Build config from environment variables."""
        raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")

        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///hosted_play.db"),
            secret_key=os.environ.get("SECRET_KEY", _default_secret_key()),
            allowed_origins=_parse_origins(raw_origins),
            app_url=os.environ.get("APP_URL", "http://localhost:8000"),
            default_model_id=os.environ.get("DEFAULT_MODEL_ID", "bud_bot"),
            olsa_artifact=os.environ.get("OLSA_ARTIFACT", _DEFAULT_OLSA_ARTIFACT),
            gbt_artifact=os.environ.get("GBT_ARTIFACT", _DEFAULT_GBT_ARTIFACT),
            models_dir=os.environ.get("MODELS_DIR"),
            debug=os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"),
        )


# Module-level config override — set by ``override_config()`` for tests.
_config_override: HostedPlayConfig | None = None


def override_config(config: HostedPlayConfig | None) -> None:
    """Set a config override (primarily for tests).

    Pass ``None`` to clear the override and revert to env-based config.
    """
    global _config_override  # noqa: PLW0603
    _config_override = config


def get_config() -> HostedPlayConfig:
    """Return the active config.

    Uses the override if set, otherwise builds from environment variables.
    """
    if _config_override is not None:
        return _config_override
    return HostedPlayConfig.from_env()
