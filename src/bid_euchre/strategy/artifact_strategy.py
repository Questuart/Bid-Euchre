"""
Artifact-backed strategy for Auction mode.

This module provides a strategy that reuses an existing playable card policy
but delegates bidding to a deterministic artifact (v1 schema) that predicts
how aggressively to bid for a fixed contract.
"""

from __future__ import annotations

from typing import Any, List

from ..core.cards import Card
from ..models.bidding_artifact import load_artifact
from ..strategy.bidding import ArtifactBidder, BiddingObservation
from ..strategy.greedy import ImprovedGreedyStrategy


class ArtifactGreedyStrategy(ImprovedGreedyStrategy):
    """
    Greedy card-play logic with artifact-backed bidding decisions.

    The artifact controls bidding for a single contract (suit/HIGH/LOW). Card
    play defers to :class:`ImprovedGreedyStrategy`.

    Supports all artifact model types by delegating to ArtifactBidder:
    - linear_regression: Linear model with hand features
    - strict_raiser_imitation_v1: Rule-based StrictRaiserBidder imitation
    - heuristics_imitation_v1: Rule-based HeuristicsBidder imitation
    """

    def __init__(
        self,
        name: str,
        artifact_path: str,
    ):
        super().__init__(name=name)

        # Load artifact to extract contract for strategy naming
        artifact = load_artifact(artifact_path)
        self._contract_token = artifact["contract"]

        # Delegate bidding to ArtifactBidder (supports all model types)
        self._bidder = ArtifactBidder(artifact_path=artifact_path, name=f"{name}_bidder")

    def decide_bid(
        self,
        hand: List[Card],
        current_high_bid: int,
        current_winner_index: Any,
        partner_index: int,
        player_index: int,
    ) -> tuple[int, Any, Any]:
        """
        Override bidding decision to delegate to the artifact bidder.

        Converts the greedy strategy interface to BiddingObservation,
        calls the artifact bidder, and converts the result back.
        """
        # Create BiddingObservation for ArtifactBidder
        obs = BiddingObservation(
            hand=hand,
            seat=player_index,
            dealer_seat=0,  # Not used by current artifact models
            current_high_bid=current_high_bid,
        )

        # Get bid action from artifact bidder
        action = self._bidder.choose_bid(obs)

        # Convert BidAction to decide_bid return format
        if action.is_pass():
            return 0, None, None

        # Return bid with contract type and suit
        # Map contract string to type (suit vs HIGH/LOW)
        if action.contract in {"C", "D", "H", "S"}:
            return action.n, "suit", action.contract
        elif action.contract in {"HIGH", "LOW"}:
            return action.n, action.contract.lower(), None
        else:
            raise ValueError(f"Unexpected contract type from artifact: {action.contract}")
