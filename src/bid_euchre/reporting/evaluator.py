"""
Deterministic evaluator for auction-mode bidders.

This module parses hand-level logs and summarizes bidder risk metrics,
ensuring outputs are stable given the same run.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ..scoring import compute_points
from .paths import get_data_paths


def _iter_hand_end_records(log_path: Path) -> Iterable[Dict]:
    if not log_path.exists():
        return

    with log_path.open() as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("event") == "hand_end":
                yield record


def _bidder_team_points(record: Dict) -> Optional[int]:
    winning_bid = record.get("winning_bid")
    bidder_position = record.get("bidder_position")
    if winning_bid is None or bidder_position is None:
        return None

    t0 = record.get("t0")
    t1 = record.get("t1")
    if t0 is None or t1 is None:
        return None

    try:
        t0 = int(t0)
        t1 = int(t1)
        winning_bid = int(winning_bid)
        bidder_position = int(bidder_position)
    except (TypeError, ValueError):
        return None

    pts0, pts1 = compute_points(winning_bid, bidder_position, t0, t1)
    if bidder_position in (0, 2):
        return pts0
    return pts1


def compute_cvar(values: List[int], tail_fraction: float = 0.05) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    tail_size = max(1, ceil(len(sorted_values) * tail_fraction))
    tail = sorted_values[:tail_size]
    return sum(tail) / len(tail)


def compute_downside_variance(values: List[int], target: float = 0.0) -> Optional[float]:
    negatives = [v for v in values if v < target]
    if not negatives:
        return None
    mean_negative = sum(negatives) / len(negatives)
    variance = sum((value - mean_negative) ** 2 for value in negatives) / len(negatives)
    return variance


def _round(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 5)


def generate_bidder_evaluation(run_dir: Path) -> Optional[Path]:
    """
    Generate evaluation JSON summarizing metrics per bidder strategy.

    The primary series is always `bidder_team_points`. CVaR-5% is defined as
    the average of the worst 5% of outcomes. Downside variance is the variance
    of returns that fall below zero.
    """
    logs_path, _ = get_data_paths(str(run_dir))
    logs_dir = Path(logs_path)
    records_by_strategy: Dict[str, List[Dict]] = defaultdict(list)
    used_log_files: List[Path] = []

    for log_file in sorted(logs_dir.glob("*.jsonl")):
        seen = False
        for record in _iter_hand_end_records(log_file):
            strategy_id = record.get("strategy_id") or "unknown"
            records_by_strategy[strategy_id].append(record)
            seen = True
        if seen:
            used_log_files.append(log_file)

    if not records_by_strategy:
        return None

    strategy_metrics = []
    for strategy_id in sorted(records_by_strategy.keys()):
        records = sorted(
            records_by_strategy[strategy_id],
            key=lambda r: (int(r.get("deal_id", 0)), r.get("timestamp", "")),
        )
        bidder_points: List[int] = []
        made_count = 0
        for record in records:
            points = _bidder_team_points(record)
            if points is None:
                continue
            bidder_points.append(points)
            if points >= 0:
                made_count += 1

        hands_with_bids = len(bidder_points)
        expected = sum(bidder_points) / hands_with_bids if hands_with_bids else None
        make_rate = made_count / hands_with_bids if hands_with_bids else None

        entry = {
            "strategy_id": strategy_id,
            "hands_with_bids": hands_with_bids,
            "bidder_team_points": bidder_points,
            "expected_points": _round(expected),
            "make_rate": _round(make_rate),
            "cvar_5": _round(compute_cvar(bidder_points)),
            "downside_variance": _round(compute_downside_variance(bidder_points)),
        }
        strategy_metrics.append(entry)

    output_dir = Path(run_dir) / "reports" / "bidding_strategy"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evaluation.json"

    payload = {
        "run_id": Path(run_dir).name,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "primary_series": "bidder_team_points",
        "source_logs": [str(p.relative_to(run_dir)) for p in used_log_files],
        "strategies": strategy_metrics,
        "metric_definitions": {
            "cvar_5": "avg of worst 5% bidder_team_points",
            "downside_variance": "variance of bidder_team_points below 0",
        },
    }

    with output_path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")

    return output_path
