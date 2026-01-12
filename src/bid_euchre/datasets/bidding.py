"""
Bidding dataset collection and emission for training datasets.

This module provides utilities for collecting bidding decisions during auction mode
and emitting them as structured datasets for training ML models.
"""

import json
import os
from typing import Any, Dict, List, Optional

from ..core.cards import Card
from ..features.hand_eval import get_hand_features
from ..strategy.bidding import BidAction, BiddingObservation


class BiddingDatasetCollector:
    """
    Collects bidding decisions during auction mode for dataset emission.

    v1 dataset includes:
    - Raw hand representation (cards)
    - Derived feature vector with stable schema
    - Bid actions and outcomes
    """

    def __init__(self, run_id: str, hand_id: int):
        """
        Initialize collector for a specific hand.

        Args:
            run_id: Unique run identifier
            hand_id: Unique hand identifier within the run
        """
        self.run_id = run_id
        self.hand_id = hand_id
        self.rows: List[Dict[str, Any]] = []
        self._hand_snapshot: Optional[List[Card]] = None
        self._final_contract_type: Optional[str] = None
        self._final_trump_suit: Optional[str] = None
        self._computed_hand_features: Optional[Dict[str, Any]] = None

    def record_decision(
        self,
        obs: BiddingObservation,
        action: BidAction,
        deal_id: Optional[int] = None
    ) -> None:
        """
        Record a single bidding decision.

        Args:
            obs: Bidding observation at decision time
            action: Bid action taken
            deal_id: Optional deal identifier for reproducibility
        """
        # Serialize hand cards consistently
        hand_cards = [f"{card.rank}{card.suit}" for card in obs.hand]

        if action.n < 0 or action.n > 10:
            return

        # Convert bid action to dataset format
        if action.is_pass():
            bid_n = 0
            bid_contract = None
        else:
            bid_n = action.n
            bid_contract = action.contract

        # Build row with stable schema and ordering
        row = {
            # Keys
            "run_id": self.run_id,
            "hand_id": self.hand_id,
            "seat": obs.seat,
            "dealer_seat": obs.dealer_seat,
            "deal_id": deal_id,
            # Context
            "current_high_bid": obs.current_high_bid,
            # Inputs
            "hand_cards": hand_cards,
            "hand_features": None,
            "hand_feature_schema_version": 1,
            # Labels
            "bid_n": bid_n,
            "bid_contract": bid_contract,
        }

        self.rows.append(row)
        if self._hand_snapshot is None:
            self._hand_snapshot = list(obs.hand)

    def set_final_contract(self, contract_type: Optional[str], trump_suit: Optional[str]) -> None:
        """Record the final contract for this hand (used when computing features)."""
        self._final_contract_type = contract_type
        self._final_trump_suit = trump_suit
        self._computed_hand_features = None

    def _ensure_hand_features(self) -> None:
        """Compute hand features once the final contract is known."""
        if self._computed_hand_features is not None:
            return

        if self._hand_snapshot is None or self._final_contract_type is None:
            features: Dict[str, Any] = {}
        else:
            features = get_hand_features(
                self._hand_snapshot,
                self._final_contract_type,
                self._final_trump_suit,
            )

        self._computed_hand_features = features
        for row in self.rows:
            row["hand_features"] = features

    def get_rows_sorted(self) -> List[Dict[str, Any]]:
        """
        Get rows sorted deterministically.

        Returns rows sorted by (hand_id, seat) for stable ordering.
        """
        self._ensure_hand_features()
        return sorted(self.rows, key=lambda r: (r["hand_id"], r["seat"]))

    def write_jsonl(self, output_path: str) -> None:
        """
        Write collected dataset to JSONL file.

        Args:
            output_path: Path to write the JSONL file
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        rows = self.get_rows_sorted()
        with open(output_path, "w") as f:
            for row in rows:
                json.dump(row, f, sort_keys=True)
                f.write("\n")


def emit_bidding_dataset(
    collectors: List[BiddingDatasetCollector],
    output_dir: str
) -> str:
    """
    Emit combined bidding dataset from multiple hand collectors.

    Args:
        collectors: List of collectors, one per hand
        output_dir: Base output directory (will write to output_dir/datasets/bidding.jsonl)

    Returns:
        Path to the written dataset file
    """
    if not collectors:
        # No auction hands to emit
        return ""

    datasets_dir = os.path.join(output_dir, "datasets")
    output_path = os.path.join(datasets_dir, "bidding.jsonl")

    # Combine all rows from all collectors
    all_rows = []
    for collector in collectors:
        all_rows.extend(collector.get_rows_sorted())

    # Sort all rows deterministically across the entire dataset
    all_rows_sorted = sorted(all_rows, key=lambda r: (r["hand_id"], r["seat"]))

    # Write combined dataset
    os.makedirs(datasets_dir, exist_ok=True)
    with open(output_path, "w") as f:
        for row in all_rows_sorted:
            json.dump(row, f, sort_keys=True)
            f.write("\n")

    return output_path
