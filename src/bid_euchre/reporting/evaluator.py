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


def _generate_comparison_report(run_dir: Path, strategy_metrics: List[Dict]) -> None:
    """
    Generate a markdown comparison report for risk metrics.

    Creates a clear table comparing EV, CVaR-5%, and downside variance across strategies.
    """
    output_dir = Path(run_dir) / "reports" / "bidding_strategy"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "RISK_METRICS_COMPARISON.md"

    # Sort strategies by expected_points for consistent ordering
    sorted_strategies = sorted(
        strategy_metrics,
        key=lambda s: s.get("expected_points", 0) or 0,
        reverse=True
    )

    with output_path.open("w") as f:
        f.write("# Risk Metrics Comparison\n\n")
        f.write("**Run ID:** `{}`\n\n".format(Path(run_dir).name))
        f.write("**Primary Series:** `bidder_team_points` (team points from successful bids)\n\n")
        f.write("**Metric Definitions:**\n")
        f.write("- **EV (Expected Value)**: Average points across all bidding hands\n")
        f.write("- **CVaR-5%**: Average of worst 5% of outcomes (tail risk)\n")
        f.write("- **Downside Variance**: Variance of outcomes below zero\n\n")

        f.write("## Comparative Analysis\n\n")
        f.write("| Strategy | Hands | EV | CVaR-5% | Downside Var | Make Rate |\n")
        f.write("|----------|------:|---:|--------:|-------------:|-----------:|\n")

        for strategy in sorted_strategies:
            strategy_id = strategy["strategy_id"]
            hands = strategy["hands_with_bids"]
            ev = strategy.get("expected_points")
            cvar = strategy.get("cvar_5")
            downside_var = strategy.get("downside_variance")
            make_rate = strategy.get("make_rate")

            # Format values
            ev_str = f"{ev:.3f}" if ev is not None else "N/A"
            cvar_str = f"{cvar:.3f}" if cvar is not None else "N/A"
            downside_str = f"{downside_var:.3f}" if downside_var is not None else "N/A"
            make_rate_str = f"{make_rate:.1%}" if make_rate is not None else "N/A"

            f.write(f"| {strategy_id} | {hands} | {ev_str} | {cvar_str} | {downside_str} | {make_rate_str} |\n")

        f.write("\n")
        f.write("**Note:** Higher EV and Make Rate are better. Lower CVaR-5% and Downside Variance indicate lower risk.\n\n")
        f.write("*Generated: {}*\n".format(datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")))


def _generate_baseline_matrix_report(run_dir: Path, strategy_metrics: List[Dict]) -> None:
    """
    Generate a baseline matrix JSON report with metrics per strategy.

    Creates a deterministic matrix report containing key risk metrics for each strategy,
    ordered by strategy_id for reproducible output.
    """
    output_dir = Path(run_dir) / "reports" / "bidding_strategy"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "baseline_matrix.json"

    # Sort strategies by strategy_id for deterministic ordering
    sorted_strategies = sorted(strategy_metrics, key=lambda s: s.get("strategy_id", ""))

    # Build matrix with only the required fields
    matrix = []
    for strategy in sorted_strategies:
        entry = {
            "strategy_id": strategy["strategy_id"],
            "expected_points": strategy.get("expected_points"),
            "make_rate": strategy.get("make_rate"),
            "cvar_5": strategy.get("cvar_5"),
            "downside_variance": strategy.get("downside_variance"),
            "n_hands": strategy.get("hands_with_bids", 0)
        }
        matrix.append(entry)

    payload = {
        "run_id": Path(run_dir).name,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "description": "Baseline matrix report with deterministic strategy ordering",
        "strategies": matrix
    }

    with output_path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def generate_bidder_evaluation(run_dir: Path) -> Optional[Path]:
    """
    Generate evaluation JSON and markdown report summarizing metrics per bidder strategy.

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

    # Generate comparison markdown report
    _generate_comparison_report(run_dir, strategy_metrics)

    # Generate baseline matrix JSON report
    _generate_baseline_matrix_report(run_dir, strategy_metrics)

    return output_path
