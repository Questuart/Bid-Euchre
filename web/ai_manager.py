"""AI model roster management for hosted play.

V1 roster: ``heuristic`` (always available) and ``hybrid_olsa`` (available
when an artifact path is configured).  Models are preloaded once at app
startup and cached in ``app.state.ai_manager``.  Routes never load
artifacts on demand.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from bid_euchre.strategy.base import Strategy
from bid_euchre.strategy.bidding import BiddingPolicy, HeuristicSuitBidder
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

    The V1 roster is configuration-backed (no database ``model_registry``
    table).  ``heuristic`` is always available; ``hybrid_olsa`` is loaded
    when ``config.hybrid_olsa_artifact`` points to a valid artifact file.
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
        """Return all models available for selection, ordered by id."""
        return sorted(self.available_models.values(), key=lambda m: m.id)

    # ------------------------------------------------------------------
    # Internal — model loading
    # ------------------------------------------------------------------

    def _load_models(self, config: HostedPlayConfig) -> None:
        """Register and preload the approved V1 roster."""
        # 1. heuristic — always available
        self.available_models["heuristic"] = ModelInfo(
            id="heuristic",
            name="Heuristic",
            description="Rule-based bidder with greedy play strategy.",
            bidding_policy=HeuristicSuitBidder(),
            play_strategy=GluttonStrategy(),
        )

        # 2. hybrid_olsa — available when artifact path is set and exists
        self._try_load_hybrid_olsa(config)

        # Validate default_model_id is available
        if self.default_model_id not in self.available_models:
            logger.warning(
                "Default model %r not in roster; falling back to 'heuristic'",
                self.default_model_id,
            )
            self.default_model_id = "heuristic"

    def _try_load_hybrid_olsa(self, config: HostedPlayConfig) -> None:
        """Attempt to load hybrid_olsa, resolving artifact path with fallback.

        Resolution order for relative paths when ``models_dir`` is configured:
        1. Try the CWD-relative path first (preserve existing local artifacts).
        2. If CWD path doesn't exist **or** loading from it fails, fall back to
           ``models_dir / artifact_path``.
        """
        artifact_path = config.hybrid_olsa_artifact
        if not artifact_path:
            return

        # Build ordered list of candidate paths to try.
        candidates: list[str] = []
        if config.models_dir and not os.path.isabs(artifact_path):
            if os.path.isfile(artifact_path):
                # CWD path exists — try it first, models_dir as fallback.
                candidates.append(artifact_path)
                candidates.append(os.path.join(config.models_dir, artifact_path))
            else:
                # CWD path missing — try models_dir only.
                candidates.append(os.path.join(config.models_dir, artifact_path))
        else:
            # Absolute path or no models_dir — use as-is.
            candidates.append(artifact_path)

        for path in candidates:
            if not os.path.isfile(path):
                continue
            try:
                from bid_euchre.strategy.bidding import HybridOLSaBidder

                self.available_models["hybrid_olsa"] = ModelInfo(
                    id="hybrid_olsa",
                    name="Hybrid OLSa",
                    description=(
                        "Statistical bidder (OLS payoff model with "
                        "risk-aware evaluation) and greedy play."
                    ),
                    bidding_policy=HybridOLSaBidder(artifact_path=path),
                    play_strategy=GluttonStrategy(),
                )
                logger.info("Loaded hybrid_olsa model from %s", path)
                return
            except Exception:
                logger.warning(
                    "Failed to load hybrid_olsa from %s",
                    path,
                    exc_info=True,
                )

        logger.info(
            "hybrid_olsa artifact configured but not loadable: %s",
            artifact_path,
        )
