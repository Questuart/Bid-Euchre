"""AI model roster management for hosted play.

The browser-facing roster is intentionally narrow:

- ``olsa`` -> ``OLSa`` backed by the Arc D v2 R3 OLS action-value artifact
- ``bud_bot`` -> ``Bud Bot`` backed by the Arc D v2 R3 GBT action-value artifact

Both models are preloaded once at app startup and cached in
``app.state.ai_manager``. Routes never load artifacts on demand.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import BiddingPolicy
from bid_euchre.strategy.greedy import GluttonStrategy

from .config import HostedPlayConfig

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """Metadata + instantiated strategy for one AI opponent model."""

    id: str
    name: str
    description: str
    bidding_policy: BiddingPolicy
    play_strategy: Strategy


class AIManager:
    """Preloads approved bidding policies and play strategies at startup.

    The browser roster is configuration-backed (no database
    ``model_registry`` table). Startup fails loudly when the approved
    artifact-backed roster cannot be loaded.
    """

    def __init__(self, config: HostedPlayConfig) -> None:
        self.available_models: dict[str, ModelInfo] = {}
        self.default_model_id: str = config.default_model_id
        self._load_models(config)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_model_info(self, model_id: str) -> ModelInfo:
        """Return model info for *model_id*.

        Raises ``KeyError`` if the model is not in the roster.
        """
        return self.available_models[model_id]

    def list_available(self) -> list[ModelInfo]:
        """Return all models available for selection in UI order."""
        return list(self.available_models.values())

    # ------------------------------------------------------------------
    # Internal — model loading
    # ------------------------------------------------------------------

    def _load_models(self, config: HostedPlayConfig) -> None:
        """Register and preload the approved browser roster."""
        self._try_load_olsa(config)
        self._try_load_bud_bot(config)

        expected_roster = {"olsa", "bud_bot"}
        missing_models = sorted(expected_roster - self.available_models.keys())
        if missing_models:
            raise RuntimeError(
                "Approved browser AI roster incomplete. Missing: "
                f"{missing_models}. Configure valid OLSa and Bud Bot artifacts "
                "before startup."
            )

        if self.default_model_id not in self.available_models:
            raise RuntimeError(
                "Default model "
                f"{self.default_model_id!r} is not in the approved browser roster "
                f"{sorted(self.available_models)}"
            )

    def _resolve_candidate_paths(
        self,
        artifact_path: str | None,
        config: HostedPlayConfig,
    ) -> list[str]:
        """Resolve artifact candidates from the configured path."""
        if not artifact_path:
            return []

        candidates: list[str] = []
        if config.models_dir and not os.path.isabs(artifact_path):
            if os.path.isfile(artifact_path):
                candidates.append(artifact_path)
                candidates.append(os.path.join(config.models_dir, artifact_path))
            else:
                candidates.append(os.path.join(config.models_dir, artifact_path))
        else:
            candidates.append(artifact_path)
        return candidates

    def _try_load_olsa(self, config: HostedPlayConfig) -> None:
        """Attempt to load the OLSa model (ActionValueBidder).

        Resolution order for relative paths when ``models_dir`` is configured:
        1. Try the CWD-relative path first (preserve existing local artifacts).
        2. If CWD path doesn't exist **or** loading from it fails, fall back to
           ``models_dir / artifact_path``.
        """
        for path in self._resolve_candidate_paths(config.olsa_artifact, config):
            if not os.path.isfile(path):
                continue
            try:
                from bid_euchre.strategy.bidding import ActionValueBidder

                self.available_models["olsa"] = ModelInfo(
                    id="olsa",
                    name="OLSa",
                    description=("Action-value bidder with Glutton card play."),
                    bidding_policy=ActionValueBidder(
                        artifact_path=path,
                        name="olsa",
                        skip_behavioral_check=True,
                    ),
                    play_strategy=GluttonStrategy(),
                )
                logger.info("Loaded OLSa model from %s", path)
                return
            except Exception:
                logger.warning(
                    "Failed to load OLSa from %s",
                    path,
                    exc_info=True,
                )

        logger.info(
            "OLSa artifact configured but not loadable: %s",
            config.olsa_artifact,
        )

    def _try_load_bud_bot(self, config: HostedPlayConfig) -> None:
        """Attempt to load the Bud Bot model (GBTActionValueBidder)."""
        for path in self._resolve_candidate_paths(config.gbt_artifact, config):
            if not os.path.isfile(path):
                continue
            try:
                from bid_euchre.strategy.bidding import GBTActionValueBidder

                self.available_models["bud_bot"] = ModelInfo(
                    id="bud_bot",
                    name="Bud Bot",
                    description=("Gradient-boosted bidder with Glutton card play."),
                    bidding_policy=GBTActionValueBidder(
                        artifact_path=path,
                        name="bud_bot",
                        skip_behavioral_check=True,
                    ),
                    play_strategy=GluttonStrategy(),
                )
                logger.info("Loaded Bud Bot model from %s", path)
                return
            except Exception:
                logger.warning(
                    "Failed to load Bud Bot from %s",
                    path,
                    exc_info=True,
                )

        logger.info(
            "Bud Bot artifact configured but not loadable: %s",
            config.gbt_artifact,
        )
