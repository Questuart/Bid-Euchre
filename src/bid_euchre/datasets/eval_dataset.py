"""Parse JSONL eval logs into analysis-ready per-seat DataFrames.

This module converts hand_end records from game log JSONL files into a
flat DataFrame with one row per (deal, seat) pair.  Features are prefixed
with ``feat_`` at the parser boundary so downstream diagnostics functions
(``compute_health_scorecard``, ``plot_hand_value_by_seat``, etc.) work
without adapter logic.

Aggregation guidance
--------------------
The per-seat rows are suitable for:

* Feature distributions, seat balance, tricks-won distribution.

For bidder-level analysis (bid accuracy, make rate) filter to
``is_bidder == True`` which yields one row per deal.

For declaring-team metrics (points, outcomes) deduplicate on
``(deal_id, team)`` after filtering ``is_declaring_team == True``.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_hand_end_records(log_path: Path) -> Iterable[Dict]:
    """Yield hand_end records from a JSONL log, skipping non-hand events.

    Follows the same error-tolerance pattern as
    ``reporting.evaluator._iter_hand_end_records``: empty lines and
    malformed JSON are silently skipped.
    """
    with log_path.open() as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skipping malformed JSON line in %s", log_path)
                continue
            if record.get("event") == "hand_end":
                yield record


def _expand_record(record: Dict) -> List[Dict]:
    """Expand a single hand_end record into 4 per-seat rows."""
    deal_id = record["deal_id"]
    contract_type = record["contract"]
    trump = record.get("trump")
    t0 = record["t0"]
    t1 = record["t1"]
    winning_bid = record.get("winning_bid")
    bidder_position = record.get("bidder_position")
    dealer_position = record.get("dealer_position")
    made_bid = record.get("made_bid")
    redeal_flag = record.get("redeal_flag")
    features_list = record.get("features", [{}, {}, {}, {}])

    bidder_team: int | None = None
    if bidder_position is not None:
        bidder_team = 0 if bidder_position in (0, 2) else 1

    # Auction summary
    transcript = record.get("auction_transcript") or []
    n_bids = sum(1 for e in transcript if e.get("action") == "BID")
    n_passes = sum(1 for e in transcript if e.get("action") == "PASS")
    auction_rounds = len(transcript)

    rows: List[Dict] = []
    for seat in range(4):
        team = 0 if seat in (0, 2) else 1
        tricks_won = t0 if seat in (0, 2) else t1

        row: Dict = {
            "deal_id": deal_id,
            "seat": seat,
            "team": team,
            "contract_type": contract_type,
            "trump": trump,
            "tricks_won": tricks_won,
            "winning_bid": winning_bid,
            "bidder_seat": bidder_position,
            "bidder_team": bidder_team,
            "dealer_seat": dealer_position,
            "made_bid": made_bid,
            "redeal_flag": redeal_flag,
            "is_bidder": seat == bidder_position,
            "is_declaring_team": team == bidder_team
            if bidder_team is not None
            else None,
            "n_bids": n_bids,
            "n_passes": n_passes,
            "auction_rounds": auction_rounds,
        }

        # Flatten features with feat_ prefix
        seat_features = features_list[seat] if seat < len(features_list) else {}
        for name, value in seat_features.items():
            row[f"feat_{name}"] = value

        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_eval_dataset(
    log_path: str | Path,
    *,
    skip_redeals: bool = True,
    max_deals: int | None = None,
) -> pd.DataFrame:
    """Build a per-seat evaluation DataFrame from a JSONL game log.

    Parameters
    ----------
    log_path:
        Path to a ``*.jsonl`` game log file containing ``hand_end`` records.
    skip_redeals:
        If True (default), exclude deals where ``redeal_flag`` is True.
    max_deals:
        If set, stop after processing this many deals (after redeal filtering).

    Returns
    -------
    pd.DataFrame
        One row per (deal, seat) pair with ``feat_*`` columns for all 39
        hand features, auction summary columns, and team/bidder metadata.

    Raises
    ------
    FileNotFoundError
        If *log_path* does not exist.
    ValueError
        If the log contains no ``hand_end`` records (after filtering).
    """
    log_path = Path(log_path)
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    all_rows: List[Dict] = []
    deals_collected = 0

    for record in _iter_hand_end_records(log_path):
        if skip_redeals and record.get("redeal_flag"):
            continue

        all_rows.extend(_expand_record(record))
        deals_collected += 1

        if max_deals is not None and deals_collected >= max_deals:
            break

    if not all_rows:
        raise ValueError(
            f"No hand_end records found in {log_path}"
            + (" (redeals excluded)" if skip_redeals else "")
        )

    df = pd.DataFrame(all_rows)

    # Assign hand_id = deal_id for diagnostics API compatibility
    # (health_checks.py expects hand_id for structural checks)
    df["hand_id"] = df["deal_id"]

    return df
