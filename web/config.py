"""Environment settings for the browser-game web application.

Settings are loaded from environment variables with sensible defaults
for local development.  Production deployments override via env vars
(e.g. ``DATABASE_URL`` for Postgres).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class HostedPlayConfig:
    """Immutable application configuration."""

    # Database ----------------------------------------------------------
    database_url: str = "sqlite:///hosted_play.db"

    # AI model roster ---------------------------------------------------
    default_model_id: str = "heuristic"
    hybrid_olsa_artifact: str | None = None

    # App ---------------------------------------------------------------
    debug: bool = False

    @classmethod
    def from_env(cls) -> HostedPlayConfig:
        """Build config from environment variables."""
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///hosted_play.db"),
            default_model_id=os.environ.get("DEFAULT_MODEL_ID", "heuristic"),
            hybrid_olsa_artifact=os.environ.get("HYBRID_OLSA_ARTIFACT"),
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
