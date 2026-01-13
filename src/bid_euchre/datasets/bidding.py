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
        # Auction outcome metadata for debugging redeals
        self._auction_outcome: Optional[str] = None
        self._winning_seat: Optional[int] = None
        self._winning_bid_n: Optional[int] = None
        self._winning_bid_contract: Optional[str] = None

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
            attempted_bid_n = 0
            attempted_bid_contract = None
            attempted_bid_trump_suit = None
        else:
            attempted_bid_n = action.n
            attempted_bid_contract = action.contract
            # For suit contracts, trump suit is stored in contract field
            # For HIGH/LOW, trump_suit should be None
            if action.contract in ["C", "D", "H", "S"]:
                attempted_bid_trump_suit = action.contract
                attempted_bid_contract = "suit"
            else:
                attempted_bid_trump_suit = None
                attempted_bid_contract = action.contract

        # Determine effective bid and legality
        is_legal_raise = True
        if attempted_bid_n <= obs.current_high_bid:
            # Illegal raise or pass - effective becomes PASS
            effective_bid_n = 0
            effective_bid_contract = None
            effective_bid_trump_suit = None
            if attempted_bid_n > obs.current_high_bid:
                is_legal_raise = False
        else:
            # Legal raise - attempted == effective
            effective_bid_n = attempted_bid_n
            effective_bid_contract = attempted_bid_contract
            effective_bid_trump_suit = attempted_bid_trump_suit

        # Build row with stable schema and ordering (run_id removed from row data)
        row = {
            # Keys
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
            # Attempted bids (what was proposed)
            "attempted_bid_n": attempted_bid_n,
            "attempted_bid_contract": attempted_bid_contract,
            "attempted_bid_trump_suit": attempted_bid_trump_suit,
            # Effective bids (what actually happened)
            "effective_bid_n": effective_bid_n,
            "effective_bid_contract": effective_bid_contract,
            "effective_bid_trump_suit": effective_bid_trump_suit,
            # Legality flag
            "is_legal_raise": is_legal_raise,
        }

        self.rows.append(row)
        if self._hand_snapshot is None:
            self._hand_snapshot = list(obs.hand)

    def set_final_contract(self, contract_type: Optional[str], trump_suit: Optional[str]) -> None:
        """Record the final contract for this hand (used when computing features)."""
        self._final_contract_type = contract_type
        self._final_trump_suit = trump_suit
        self._computed_hand_features = None

    def set_auction_outcome(
        self,
        auction_outcome: str,
        winning_seat: Optional[int] = None,
        winning_bid_n: Optional[int] = None,
        winning_bid_contract: Optional[str] = None
    ) -> None:
        """
        Record auction outcome metadata for debugging redeals.

        Args:
            auction_outcome: "won" or "all_pass_redeal"
            winning_seat: Seat that won the auction (0-3, null for redeals)
            winning_bid_n: Winning bid number (null for redeals)
            winning_bid_contract: Winning bid contract (null for redeals)
        """
        self._auction_outcome = auction_outcome
        self._winning_seat = winning_seat
        self._winning_bid_n = winning_bid_n
        self._winning_bid_contract = winning_bid_contract

    def _ensure_hand_features(self) -> None:
        """Compute hand features once the final contract is known."""
        if self._computed_hand_features is not None:
            return

        if self._hand_snapshot is None or self._final_contract_type is None:
            # Provide minimal features when contract info is unavailable
            features: Dict[str, Any] = {
                "trump_count": 0,
                "trump_rb_count": 0,
                "trump_lb_count": 0,
                "offsuit_aces": 0,
                "offsuit_length_3plus_count": 0,
                "hand_value": 0.0,
                "is_bidder": 0
            }
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

        # Add auction outcome metadata to each row
        for row in self.rows:
            row["auction_outcome"] = self._auction_outcome
            row["winning_seat"] = self._winning_seat
            row["winning_bid_n"] = self._winning_bid_n
            row["winning_bid_contract"] = self._winning_bid_contract

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

    def write_parquet(self, output_path: str, run_id: Optional[str] = None) -> None:
        """
        Write collected dataset to Parquet file with run_id in metadata.

        Args:
            output_path: Path to write the Parquet file
            run_id: Run ID to store in metadata (defaults to self.run_id)
        """
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as e:
            raise ImportError(
                "pyarrow is required for Parquet output. "
                "Install with: pip install pyarrow"
            ) from e

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        rows = self.get_rows_sorted()
        table = pa.Table.from_pylist(rows)

        # Add run_id and schema versions to metadata
        actual_run_id = run_id if run_id is not None else self.run_id
        metadata = {
            "run_id": actual_run_id,
            "bidding_dataset_schema_version": "1",
            "hand_feature_schema_version": "1"
        }
        # Convert metadata dict to bytes for Parquet
        metadata_bytes = {k: v.encode('utf-8') for k, v in metadata.items()}
        table = table.replace_schema_metadata(metadata_bytes)

        pq.write_table(table, output_path)


def emit_bidding_dataset(
    collectors: List[BiddingDatasetCollector],
    output_dir: str,
    format: str = "parquet"
) -> str:
    """
    Emit combined bidding dataset from multiple hand collectors.

    Args:
        collectors: List of collectors, one per hand
        output_dir: Base output directory
        format: Output format ("parquet" or "jsonl", default: "parquet")

    Returns:
        Path to the written dataset file (primary format)
    """
    if not collectors:
        # No auction hands to emit
        return ""

    datasets_dir = os.path.join(output_dir, "datasets")

    # Combine all rows from all collectors
    all_rows = []
    for collector in collectors:
        all_rows.extend(collector.get_rows_sorted())

    # Sort all rows deterministically across the entire dataset
    all_rows_sorted = sorted(all_rows, key=lambda r: (r["hand_id"], r["seat"]))

    # Extract run_id from first collector (all should be the same)
    run_id = collectors[0].run_id

    # Create collector with combined data for writing
    combined_collector = BiddingDatasetCollector(run_id, "combined")
    combined_collector.rows = all_rows_sorted

    # Always write primary format (parquet by default)
    if format == "parquet":
        primary_path = os.path.join(datasets_dir, "bidding.parquet")
        combined_collector.write_parquet(primary_path, run_id=run_id)
    else:
        primary_path = os.path.join(datasets_dir, "bidding.jsonl")
        combined_collector.write_jsonl(primary_path)

    # Write debug format if different from primary
    if format == "parquet":
        debug_path = os.path.join(datasets_dir, "bidding.jsonl")
        # Write JSONL with run_id added back for debugging
        with open(debug_path, "w") as f:
            for row in all_rows_sorted:
                # Add run_id back for JSONL debugging
                row_with_run_id = {"run_id": run_id, **row}
                json.dump(row_with_run_id, f, sort_keys=True)
                f.write("\n")

    # Write metadata JSON file
    meta_path = os.path.join(datasets_dir, "bidding_meta.json")
    meta_data = {
        "run_id": run_id,
        "bidding_dataset_schema_version": 1,
        "hand_feature_schema_version": 1,
        "parquet_path": "bidding.parquet",
        "jsonl_path": "bidding.jsonl"
    }
    with open(meta_path, "w") as f:
        json.dump(meta_data, f, indent=2)

    return primary_path
