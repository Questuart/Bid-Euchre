"""
Artifact-backed strategy for Auction mode.

This module provides a strategy that reuses an existing playable card policy
but delegates bidding to a deterministic artifact (v1 schema) that predicts
how aggressively to bid for a fixed contract.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..core.cards import Card
from ..features.hand_eval import get_hand_features
from ..models.bidding_artifact import load_artifact
from ..strategy.greedy import ImprovedGreedyStrategy

HIGH_CARD_WEIGHTS: Dict[str, int] = {
    "A": 4,
    "K": 3,
    "Q": 2,
    "J": 1,
    "T": 0,
}


class ArtifactGreedyStrategy(ImprovedGreedyStrategy):
    """
    Greedy card-play logic with artifact-backed bidding decisions.

    The artifact controls bidding for a single contract (suit/HIGH/LOW). Card
    play defers to :class:`ImprovedGreedyStrategy`.
    """

    def __init__(
        self,
        name: str,
        artifact_path: str,
    ):
        super().__init__(name=name)
        artifact = load_artifact(artifact_path)
        model_params = artifact["model_params"]

        if artifact["model_type"] != "linear_regression":
            raise ValueError(
                "ArtifactGreedyStrategy only supports linear_regression artifacts"
            )

        self._artifact = artifact
        self._feature_names: List[str] = list(model_params["features"])
        self._coefficients: List[float] = [float(v) for v in model_params["coefficients"]]
        self._intercept: float = float(model_params.get("intercept", 0.0))
        self._contract_token = artifact["contract"]
        self._contract_type, self._trump_suit = self._resolve_contract(artifact["contract"])

        if len(self._feature_names) != len(self._coefficients):
            raise ValueError(
                "Mismatch between artifact feature list and coefficient length"
            )

    def _resolve_contract(self, contract: str) -> tuple[str, Any]:
        if contract in {"C", "D", "H", "S"}:
            return "suit", contract
        if contract == "HIGH":
            return "high", None
        if contract == "LOW":
            return "low", None
        raise ValueError(f"Unsupported artifact contract: {contract}")

    def _derivable_features(self, hand: List[Card]) -> Dict[str, float]:
        suit_lengths: Dict[str, int] = {}
        for card in hand:
            suit_lengths[card.suit] = suit_lengths.get(card.suit, 0) + 1

        max_suit_len = max(suit_lengths.values()) if suit_lengths else 0
        high_card_points = sum(HIGH_CARD_WEIGHTS.get(card.rank, 0) for card in hand)

        return {
            "suit_length": float(max_suit_len),
            "high_card_points": float(high_card_points),
        }

    def _hand_feature_vector(self, hand: List[Card]) -> List[float]:
        core_features = get_hand_features(
            hand,
            contract_type=self._contract_type,
            trump_suit=self._trump_suit,
        )
        derived = self._derivable_features(hand)
        combined = {**core_features, **derived}

        values = []
        for name in self._feature_names:
            value = combined.get(name, 0.0)
            values.append(float(value))
        return values

    def _predict_bid_value(self, hand: List[Card]) -> float:
        vector = self._hand_feature_vector(hand)
        total = self._intercept
        for coef, value in zip(self._coefficients, vector):
            total += coef * value
        return total

    def decide_bid(
        self,
        hand: List[Card],
        current_high_bid: int,
        current_winner_index: Any,
        partner_index: int,
        player_index: int,
    ) -> tuple[int, Any, Any]:
        """
        Override bidding decision to consult the artifact (linear regression).
        """
        bid_value = self._predict_bid_value(hand)
        bid_amount = int(round(bid_value))
        bid_amount = max(0, min(10, bid_amount))

        if bid_amount <= current_high_bid:
            return 0, None, None

        if self._contract_type == "suit":
            return bid_amount, "suit", self._trump_suit
        return bid_amount, self._contract_type, None
