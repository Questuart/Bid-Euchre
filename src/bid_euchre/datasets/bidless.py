"""
Bidless dataset collection and emission for training hand-strength/value models.

This module provides utilities for collecting hand strength/value data during
bidless simulations (declared contract/trump; no auction) and emitting them as
structured datasets for training ML models.

Includes both:
- BidlessDatasetCollector: In-memory collector for small datasets
- BidlessDatasetWriter: Streaming writer for memory-efficient large-scale emission
"""

import json
import os
from typing import Any, Dict, List, Optional, TextIO

from ..core.cards import Card
from ..features.hand_eval import get_hand_features


class BidlessDatasetCollector:
    """
    Collects hand strength/value data during bidless simulations for dataset emission.

    v1 dataset includes:
    - Raw hand representation (cards)
    - Derived feature vector with stable schema
    - Contract context (type and trump suit)
    - Hand value/strength score
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
        self._hands_by_seat: Dict[int, List[Card]] = {}  # Store each seat's hand
        self._contract_type: Optional[str] = None
        self._trump_suit: Optional[str] = None
        self._features_computed: bool = False

    def record_hand_value(
        self,
        hand: List[Card],
        seat: int,
        dealer_seat: int,
        contract_type: str,
        trump_suit: Optional[str] = None,
        deal_id: Optional[int] = None
    ) -> None:
        """
        Record a hand's strength/value for the given contract context.

        Args:
            hand: The player's hand cards
            seat: Player seat position (0-3)
            dealer_seat: Dealer seat position (0-3)
            contract_type: Declared contract type ("suit", "HIGH", "LOW")
            trump_suit: Trump suit for suit contracts ("C", "D", "H", "S", None for HIGH/LOW)
            deal_id: Optional deal identifier for reproducibility
        """
        # Validate contract type (accept both "high"/"low" and "HIGH"/"LOW")
        ct_lower = contract_type.lower()
        if ct_lower not in ("suit", "high", "low"):
            raise ValueError(f"Invalid contract_type: {contract_type}")

        # Validate trump_suit for suit contracts
        if ct_lower == "suit" and trump_suit is None:
            raise ValueError("trump_suit must be provided for 'suit' contracts")
        if ct_lower in ("high", "low") and trump_suit is not None:
            raise ValueError("trump_suit must be None for high/low contracts")

        # Validate seat positions
        if not (0 <= seat <= 3):
            raise ValueError(f"seat must be 0-3, got {seat}")
        if not (0 <= dealer_seat <= 3):
            raise ValueError(f"dealer_seat must be 0-3, got {dealer_seat}")

        # Serialize hand cards consistently
        hand_cards = [f"{card.rank}{card.suit}" for card in hand]

        # Build row with stable schema and ordering
        row = {
            # Keys
            "hand_id": self.hand_id,
            "seat": seat,
            "dealer_seat": dealer_seat,
            "deal_id": deal_id,
            # Inputs
            "hand_cards": hand_cards,
            "hand_features": None,
            "hand_feature_schema_version": 1,
            # Contract context
            "contract_type": contract_type,
            "trump_suit": trump_suit,
        }

        self.rows.append(row)
        # Store each seat's hand for per-seat feature computation
        self._hands_by_seat[seat] = list(hand)

    def set_contract_context(self, contract_type: str, trump_suit: Optional[str] = None) -> None:
        """
        Set the contract context for hand feature computation.

        This should be called after recording all hands to enable feature computation.
        """
        # Validate contract type (accept both "high"/"low" and "HIGH"/"LOW")
        ct_lower = contract_type.lower()
        if ct_lower not in ("suit", "high", "low"):
            raise ValueError(f"Invalid contract_type: {contract_type}")
        if ct_lower == "suit" and trump_suit is None:
            raise ValueError("trump_suit must be provided for 'suit' contracts")
        if ct_lower in ("high", "low") and trump_suit is not None:
            raise ValueError("trump_suit must be None for high/low contracts")

        self._contract_type = contract_type
        self._trump_suit = trump_suit
        self._features_computed = False  # Force recomputation

    def _ensure_hand_features(self) -> None:
        """Compute hand features per-seat using contract info from each row."""
        if self._features_computed:
            return

        for row in self.rows:
            seat = row["seat"]
            hand = self._hands_by_seat.get(seat)
            # Use contract info from the row itself (set during record_hand_value)
            contract_type = row.get("contract_type")
            trump_suit = row.get("trump_suit")

            if hand is None or contract_type is None:
                # Provide minimal features when hand/contract info is unavailable
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
                    hand,
                    contract_type,
                    trump_suit,
                )

            # Each row gets its own copy to avoid aliasing
            row["hand_features"] = dict(features)

        self._features_computed = True

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
            "bidless_dataset_schema_version": "1",
            "hand_feature_schema_version": "1"
        }
        # Convert metadata dict to bytes for Parquet
        metadata_bytes = {k: v.encode('utf-8') for k, v in metadata.items()}
        table = table.replace_schema_metadata(metadata_bytes)

        pq.write_table(table, output_path)


def emit_bidless_dataset(
    collectors: List[BidlessDatasetCollector],
    output_dir: str,
    format: str = "parquet"
) -> str:
    """
    Emit combined bidless dataset from multiple hand collectors.

    Args:
        collectors: List of collectors, one per hand
        output_dir: Base output directory
        format: Output format ("parquet" or "jsonl", default: "parquet")

    Returns:
        Path to the written dataset file (primary format)
    """
    if not collectors:
        # No hands to emit
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
    combined_collector = BidlessDatasetCollector(run_id, "combined")
    combined_collector.rows = all_rows_sorted
    combined_collector._features_computed = True  # Features already computed in individual collectors

    # Always write primary format (parquet by default)
    if format == "parquet":
        primary_path = os.path.join(datasets_dir, "bidless.parquet")
        combined_collector.write_parquet(primary_path, run_id=run_id)
    else:
        primary_path = os.path.join(datasets_dir, "bidless.jsonl")
        combined_collector.write_jsonl(primary_path)

    # Write debug format if different from primary
    if format == "parquet":
        debug_path = os.path.join(datasets_dir, "bidless.jsonl")
        # Write JSONL with run_id added back for debugging
        with open(debug_path, "w") as f:
            for row in all_rows_sorted:
                # Add run_id back for JSONL debugging
                row_with_run_id = {"run_id": run_id, **row}
                json.dump(row_with_run_id, f, sort_keys=True)
                f.write("\n")

    # Write metadata JSON file
    meta_path = os.path.join(datasets_dir, "bidless_meta.json")
    meta_data = {
        "run_id": run_id,
        "bidless_dataset_schema_version": 1,
        "hand_feature_schema_version": 1,
        "parquet_path": "bidless.parquet",
        "jsonl_path": "bidless.jsonl"
    }
    with open(meta_path, "w") as f:
        json.dump(meta_data, f, indent=2)

    return primary_path


class BidlessDatasetWriter:
    """
    Streaming writer for bidless dataset - writes rows incrementally to avoid memory accumulation.

    This writer is designed for large-scale dataset emission where accumulating all rows
    in memory would be prohibitive. It buffers rows and flushes them to disk incrementally.

    Output format behavior (matches emit_bidless_dataset contract):
    - format="parquet": Writes parquet as primary + debug JSONL with run_id injected
    - format="jsonl": Writes JSONL as primary without run_id, no parquet emitted
    """

    def __init__(
        self,
        run_dir: str,
        run_id: str,
        format: str = "parquet",
        flush_rows: int = 50_000,
    ):
        """
        Initialize the streaming writer.

        Args:
            run_dir: Base run directory (datasets written to run_dir/datasets/)
            run_id: Unique run identifier
            format: Primary output format ("parquet" or "jsonl")
            flush_rows: Number of rows to buffer before flushing to parquet
        """
        if format not in ("parquet", "jsonl"):
            raise ValueError(f"format must be 'parquet' or 'jsonl', got: {format}")

        self.run_dir = run_dir
        self.run_id = run_id
        self.format = format
        self.flush_rows = flush_rows

        # Create datasets directory
        self._datasets_dir = os.path.join(run_dir, "datasets")
        os.makedirs(self._datasets_dir, exist_ok=True)

        # Internal state
        self._buffer: List[Dict[str, Any]] = []
        self._total_rows: int = 0
        self._finalized: bool = False

        # Parquet writer state (lazy-initialized)
        self._parquet_writer: Any = None  # pq.ParquetWriter
        self._parquet_schema: Any = None  # pa.Schema

        # JSONL file handles
        self._jsonl_file: Optional[TextIO] = None
        self._debug_jsonl_file: Optional[TextIO] = None

        # Open JSONL files based on format
        if format == "parquet":
            # Debug JSONL with run_id injected
            debug_path = os.path.join(self._datasets_dir, "bidless.jsonl")
            self._debug_jsonl_file = open(debug_path, "w")
        else:
            # Primary JSONL without run_id
            primary_path = os.path.join(self._datasets_dir, "bidless.jsonl")
            self._jsonl_file = open(primary_path, "w")

    def append_rows(self, rows: List[Dict[str, Any]]) -> None:
        """
        Add rows to buffer. Flushes to disk if buffer exceeds threshold.

        Args:
            rows: List of row dicts to append
        """
        if self._finalized:
            raise RuntimeError("Cannot append rows after finalize() has been called")

        self._buffer.extend(rows)

        # Flush to disk if buffer is large enough
        if len(self._buffer) >= self.flush_rows:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        """Flush buffered rows to disk (sorted by hand_id, seat)."""
        if not self._buffer:
            return

        # Sort buffer deterministically
        sorted_rows = sorted(self._buffer, key=lambda r: (r["hand_id"], r["seat"]))

        if self.format == "parquet":
            self._write_parquet_batch(sorted_rows)
            # Also write to debug JSONL with run_id
            if self._debug_jsonl_file is not None:
                for row in sorted_rows:
                    row_with_run_id = {"run_id": self.run_id, **row}
                    json.dump(row_with_run_id, self._debug_jsonl_file, sort_keys=True)
                    self._debug_jsonl_file.write("\n")
                self._debug_jsonl_file.flush()
        else:
            # Write to primary JSONL without run_id
            if self._jsonl_file is not None:
                for row in sorted_rows:
                    json.dump(row, self._jsonl_file, sort_keys=True)
                    self._jsonl_file.write("\n")
                self._jsonl_file.flush()

        self._total_rows += len(sorted_rows)
        self._buffer = []

    def _write_parquet_batch(self, rows: List[Dict[str, Any]]) -> None:
        """Write a batch of rows to parquet, handling schema promotion for nullable fields."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as e:
            raise ImportError(
                "pyarrow is required for Parquet output. "
                "Install with: pip install pyarrow"
            ) from e

        # Build table from rows
        table = pa.Table.from_pylist(rows)

        if self._parquet_writer is None:
            # First flush - initialize parquet writer with schema promotion
            schema = table.schema

            # Promote trump_suit from null to string if needed
            # This handles the case where first batch is all high/low contracts (trump_suit=None)
            trump_idx = schema.get_field_index("trump_suit")
            if trump_idx >= 0:
                trump_field = schema.field(trump_idx)
                if pa.types.is_null(trump_field.type):
                    # Promote null to nullable string
                    new_fields = list(schema)
                    new_fields[trump_idx] = pa.field("trump_suit", pa.string())
                    schema = pa.schema(new_fields)
                    # Rebuild table with promoted schema
                    table = pa.Table.from_pylist(rows, schema=schema)

            # Add metadata
            metadata = {
                "run_id": self.run_id,
                "bidless_dataset_schema_version": "1",
                "hand_feature_schema_version": "1",
            }
            metadata_bytes = {k: v.encode("utf-8") for k, v in metadata.items()}
            schema = schema.with_metadata(metadata_bytes)

            self._parquet_schema = schema
            parquet_path = os.path.join(self._datasets_dir, "bidless.parquet")
            self._parquet_writer = pq.ParquetWriter(parquet_path, schema)

        # Ensure table matches expected schema (cast if needed)
        if table.schema != self._parquet_schema.remove_metadata():
            table = pa.Table.from_pylist(rows, schema=self._parquet_schema.remove_metadata())

        self._parquet_writer.write_table(table)

    def finalize(self) -> str:
        """
        Flush remaining rows, close writers, write metadata.

        Returns:
            Path to the primary output file (parquet or jsonl)
        """
        if self._finalized:
            raise RuntimeError("finalize() has already been called")

        # Flush any remaining rows
        self._flush_buffer()

        # Close parquet writer
        if self._parquet_writer is not None:
            self._parquet_writer.close()

        # Close JSONL files
        if self._jsonl_file is not None:
            self._jsonl_file.close()
        if self._debug_jsonl_file is not None:
            self._debug_jsonl_file.close()

        # Write metadata JSON
        meta_path = os.path.join(self._datasets_dir, "bidless_meta.json")
        meta_data = {
            "run_id": self.run_id,
            "bidless_dataset_schema_version": 1,
            "hand_feature_schema_version": 1,
            "parquet_path": "bidless.parquet" if self.format == "parquet" else None,
            "jsonl_path": "bidless.jsonl",
            "row_count": self._total_rows,
        }
        with open(meta_path, "w") as f:
            json.dump(meta_data, f, indent=2)

        self._finalized = True

        # Return primary output path
        if self.format == "parquet":
            return os.path.join(self._datasets_dir, "bidless.parquet")
        else:
            return os.path.join(self._datasets_dir, "bidless.jsonl")
