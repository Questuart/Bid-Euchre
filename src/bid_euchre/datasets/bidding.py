"""
Bidding dataset collection and emission for training datasets.

This module provides utilities for collecting bidding decisions during auction mode
and emitting them as structured datasets for training ML models.
"""

import json
import os
from typing import Any, Dict, List, Optional

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
        # Get hand features using existing feature computation
        # For auction mode, we need to determine contract type for features
        # Since this is auction mode, we'll use a dummy contract for feature computation
        # The features will be computed assuming a "suit" contract with no specific trump
        # This gives us the full feature set for training
        hand_features = get_hand_features(obs.hand, "suit", None)

        # Serialize hand cards consistently
        hand_cards = [f"{card.rank}{card.suit}" for card in obs.hand]

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
            "hand_features": hand_features,
            "hand_feature_schema_version": 1,
            # Labels
            "bid_n": bid_n,
            "bid_contract": bid_contract,
        }

        self.rows.append(row)

    def get_rows_sorted(self) -> List[Dict[str, Any]]:
        """
        Get rows sorted deterministically.

        Returns rows sorted by (hand_id, seat) for stable ordering.
        """
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
