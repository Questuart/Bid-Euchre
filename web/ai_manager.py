"""AI model roster management for hosted play.

Expansion roster: ``heuristic`` (always available, smoke/fallback) and
``olsa`` (R3 ``full_ols_av`` ``ActionValueBidder``, available when an
artifact path is configured).  Models are preloaded once at app startup
and cached in ``app.state.ai_manager``.  Routes never load artifacts on
demand.

The V1 ``hybrid_olsa`` roster entry has been removed because
``HybridOLSaBidder`` only produces regular bids and is not moon/loner-
capable.  See ``plans/browser_game_expansion/governing_plan.md`` §5.2.
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

    The expansion roster is configuration-backed (no database
    ``model_registry`` table).  ``heuristic`` is always available as a
    smoke/fallback model; ``olsa`` is loaded when
    ``config.olsa_artifact`` points to a valid ``action_value_olsa_v1``
    artifact file.
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
        """Register and preload the approved expansion roster."""
        # 1. heuristic — always available (smoke/fallback)
        self.available_models["heuristic"] = ModelInfo(
            id="heuristic",
            name="Heuristic",
            description="Rule-based bidder with greedy play strategy.",
            bidding_policy=HeuristicSuitBidder(),
            play_strategy=GluttonStrategy(),
        )

        # 2. olsa — R3 full_ols_av ActionValueBidder, available when artifact
        #    path is set and the artifact loads successfully.
        self._try_load_olsa(config)

        # Validate default_model_id is available
        if self.default_model_id not in self.available_models:
            logger.warning(
                "Default model %r not in roster; falling back to 'heuristic'",
                self.default_model_id,
            )
            self.default_model_id = "heuristic"

    def _try_load_olsa(self, config: HostedPlayConfig) -> None:
        """Attempt to load the OLSa model (ActionValueBidder).

        Resolution order for relative paths when ``models_dir`` is configured:
        1. Try the CWD-relative path first (preserve existing local artifacts).
        2. If CWD path doesn't exist **or** loading from it fails, fall back to
           ``models_dir / artifact_path``.
        """
        artifact_path = config.olsa_artifact
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
                from bid_euchre.strategy.bidding import ActionValueBidder

                self.available_models["olsa"] = ModelInfo(
                    id="olsa",
                    name="OLSa",
                    description=(
                        "Action-value bidder (R3 full_ols_av) with "
                        "greedy play strategy."
                    ),
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
            artifact_path,
        )
