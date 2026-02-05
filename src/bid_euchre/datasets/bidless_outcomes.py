"""
Bidless outcomes dataset collection and emission.

This module collects per-hand outcome data during bidless simulations
(declared contract/trump; no auction). The outcomes dataset is designed
for analysis and reporting, not for ML training (use bidless.py for that).

Key design:
- Per-hand granularity (not per-seat) - 4x smaller than features dataset
- Explicit strategy/matchup identification columns
- team0_win uses weighted win rate: 1.0=win, 0.5=tie, 0.0=loss
"""

import json
import os
from typing import Any, Dict, List, Optional


class BidlessOutcomesCollector:
    """
    Collects per-hand outcome data during bidless simulations.

    Each hand produces exactly one row with:
    - hand_id, deal_id: identifiers for joining/pairing
    - contract context: dealer_seat, contract_type, trump_suit
    - strategy context: strategy_id, matchup_id, team0_strategy, team1_strategy
    - outcomes: tricks_team0, tricks_team1, team0_win
    """

    def __init__(self, run_id: str):
        """
        Initialize collector for a run.

        Args:
            run_id: Unique run identifier
        """
        self.run_id = run_id
        self.rows: List[Dict[str, Any]] = []

    def record_outcome(
        self,
        hand_id: int,
        deal_id: int,
        dealer_seat: int,
        contract_type: str,
        trump_suit: Optional[str],
        strategy_id: str,
        matchup_id: str,
        team0_strategy: str,
        team1_strategy: str,
        tricks_team0: int,
        tricks_team1: int,
    ) -> None:
        """
        Record outcome for a single hand.

        Args:
            hand_id: Globally unique hand identifier
            deal_id: Physical deal index for pairing (same across scenarios if pair_deals=True)
            dealer_seat: Dealer position (0-3)
            contract_type: Contract type ("suit", "high", "low")
            trump_suit: Trump suit for suit contracts ("C", "D", "H", "S"), None for high/low
            strategy_id: Strategy name for self_play mode
            matchup_id: Matchup identifier (e.g., "greedy_vs_random_legal")
            team0_strategy: Strategy name for team 0 (seats 0, 2)
            team1_strategy: Strategy name for team 1 (seats 1, 3)
            tricks_team0: Tricks won by team 0 (0-10)
            tricks_team1: Tricks won by team 1 (0-10)
        """
        # Compute team0_win using weighted win rate
        # 1.0 = win (>5 tricks), 0.5 = tie (exactly 5), 0.0 = loss (<5)
        if tricks_team0 > 5:
            team0_win = 1.0
        elif tricks_team0 == 5:
            team0_win = 0.5
        else:
            team0_win = 0.0

        row = {
            "hand_id": hand_id,
            "deal_id": deal_id,
            "dealer_seat": dealer_seat,
            "contract_type": contract_type,
            "trump_suit": trump_suit,
            "strategy_id": strategy_id,
            "matchup_id": matchup_id,
            "team0_strategy": team0_strategy,
            "team1_strategy": team1_strategy,
            "tricks_team0": tricks_team0,
            "tricks_team1": tricks_team1,
            "team0_win": team0_win,
        }
        self.rows.append(row)

    def get_rows_sorted(self) -> List[Dict[str, Any]]:
        """
        Get rows sorted deterministically by hand_id.

        Returns:
            List of outcome rows sorted by hand_id for stable ordering.
        """
        return sorted(self.rows, key=lambda r: r["hand_id"])


def emit_bidless_outcomes_dataset(
    collector: BidlessOutcomesCollector,
    output_dir: str,
    format: str = "parquet",
) -> str:
    """
    Emit bidless outcomes dataset from collector.

    Args:
        collector: Collector containing outcome data
        output_dir: Base output directory (run_dir)
        format: Output format ("parquet" or "jsonl", default: "parquet")

    Returns:
        Path to the written dataset file (primary format)
    """
    if not collector.rows:
        return ""

    datasets_dir = os.path.join(output_dir, "datasets")
    os.makedirs(datasets_dir, exist_ok=True)

    all_rows = collector.get_rows_sorted()
    run_id = collector.run_id

    # Write primary format
    if format == "parquet":
        primary_path = os.path.join(datasets_dir, "bidless_outcomes.parquet")
        _write_parquet(all_rows, primary_path, run_id)
    else:
        primary_path = os.path.join(datasets_dir, "bidless_outcomes.jsonl")
        _write_jsonl(all_rows, primary_path, run_id)

    # Always write JSONL for debugging
    if format == "parquet":
        debug_path = os.path.join(datasets_dir, "bidless_outcomes.jsonl")
        _write_jsonl(all_rows, debug_path, run_id)

    # Write metadata
    meta_path = os.path.join(datasets_dir, "bidless_outcomes_meta.json")
    meta_data = {
        "run_id": run_id,
        "bidless_outcomes_schema_version": 1,
        "row_count": len(all_rows),
        "parquet_path": "bidless_outcomes.parquet",
        "jsonl_path": "bidless_outcomes.jsonl",
    }
    with open(meta_path, "w") as f:
        json.dump(meta_data, f, indent=2)

    return primary_path


def _write_jsonl(rows: List[Dict[str, Any]], output_path: str, run_id: str) -> None:
    """Write rows to JSONL file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        for row in rows:
            row_with_run_id = {"run_id": run_id, **row}
            json.dump(row_with_run_id, f, sort_keys=True)
            f.write("\n")


def _write_parquet(rows: List[Dict[str, Any]], output_path: str, run_id: str) -> None:
    """Write rows to Parquet file with metadata."""
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as e:
        raise ImportError(
            "pyarrow is required for Parquet output. Install with: pip install pyarrow"
        ) from e

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    table = pa.Table.from_pylist(rows)

    # Add metadata
    metadata = {
        "run_id": run_id,
        "bidless_outcomes_schema_version": "1",
    }
    metadata_bytes = {k: v.encode("utf-8") for k, v in metadata.items()}
    table = table.replace_schema_metadata(metadata_bytes)

    pq.write_table(table, output_path)
