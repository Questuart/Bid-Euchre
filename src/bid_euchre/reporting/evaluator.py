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


def load_eval_metrics(eval_path: str | Path) -> dict:
    """Load eval metrics from an evaluator JSON output file.

    Handles three formats:
    1. Full evaluator output: {"strategies": [{...metrics...}]}
    2. Nested: {"metrics": {...}}
    3. Flat: top-level metrics dict

    Args:
        eval_path: Path to eval JSON file.

    Returns:
        Dict of metric name -> value.

    Raises:
        FileNotFoundError: If eval file doesn't exist.
        json.JSONDecodeError: If file is invalid JSON.
    """
    with open(eval_path) as f:
        data = json.load(f)
    if "strategies" in data and isinstance(data["strategies"], list):
        return data["strategies"][0] if data["strategies"] else {}
    if "metrics" in data:
        return data["metrics"]
    return data


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


def _parse_record_fields(record: Dict) -> Optional[tuple[int, int, int, int]]:
    """Extract and validate (winning_bid, bidder_position, t0, t1) from a hand_end record."""
    winning_bid = record.get("winning_bid")
    bidder_position = record.get("bidder_position")
    if winning_bid is None or bidder_position is None:
        return None

    t0 = record.get("t0")
    t1 = record.get("t1")
    if t0 is None or t1 is None:
        return None

    try:
        return int(winning_bid), int(bidder_position), int(t0), int(t1)
    except (TypeError, ValueError):
        return None


def _bidder_team_points(record: Dict) -> Optional[int]:
    parsed = _parse_record_fields(record)
    if parsed is None:
        return None

    winning_bid, bidder_position, t0, t1 = parsed
    pts0, pts1 = compute_points(winning_bid, bidder_position, t0, t1)
    if bidder_position in (0, 2):
        return pts0
    return pts1


def _net_differential_points(record: Dict) -> Optional[int]:
    """Compute net differential: bidder_team_points - opponent_team_points.

    Make (tricks >= bid_n): net = 2 * tricks_won - 10
    Set  (tricks < bid_n):  net = tricks_won - bid_n - 10
    """
    parsed = _parse_record_fields(record)
    if parsed is None:
        return None

    winning_bid, bidder_position, t0, t1 = parsed
    pts0, pts1 = compute_points(winning_bid, bidder_position, t0, t1)
    if bidder_position in (0, 2):
        return pts0 - pts1
    return pts1 - pts0


def compute_cvar(values: List[int], tail_fraction: float = 0.05) -> Optional[float]:
    if not values:
        return None
    sorted_values = sorted(values)
    tail_size = max(1, ceil(len(sorted_values) * tail_fraction))
    tail = sorted_values[:tail_size]
    return sum(tail) / len(tail)


def compute_downside_variance(
    values: List[int], target: float = 0.0
) -> Optional[float]:
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

    # Sort strategies by net_expected_points for consistent ordering
    sorted_strategies = sorted(
        strategy_metrics,
        key=lambda s: s.get("net_expected_points", 0) or 0,
        reverse=True,
    )

    with output_path.open("w") as f:
        f.write("# Risk Metrics Comparison\n\n")
        f.write("**Run ID:** `{}`\n\n".format(Path(run_dir).name))
        f.write(
            "**Primary Series:** `net_bidder_team_points` (net differential: bidder - opponent)\n\n"
        )
        f.write("**Metric Definitions:**\n")
        f.write(
            "- **Net EV**: Average net differential (bidder - opponent) across hands with bids\n"
        )
        f.write("- **Net EV/Deal**: Net EV with `0` assigned to all-pass redeals\n")
        f.write("- **EV (Expected Value)**: Average bidder team points (secondary)\n")
        f.write("- **EV/Deal**: EV with `0` assigned to all-pass redeals (secondary)\n")
        f.write("- **Bid Rate**: Fraction of deals with an auction winner\n")
        f.write("- **Net CVaR-5%**: Average of worst 5% of net differential outcomes\n")
        f.write(
            "- **Downside Variance**: Variance of net differential outcomes below zero\n\n"
        )

        f.write("## Comparative Analysis\n\n")
        f.write(
            "| Strategy | Deals | Bid Hands | Bid Rate | Net EV | Net EV/Deal | EV/Deal | Net CVaR-5% | Downside Var | Make Rate |\n"
        )
        f.write(
            "|----------|------:|----------:|---------:|-------:|------------:|--------:|------------:|-------------:|----------:|\n"
        )

        for strategy in sorted_strategies:
            strategy_id = strategy["strategy_id"]
            deals = strategy.get("deals_total", 0)
            hands = strategy["hands_with_bids"]
            bid_rate = strategy.get("bid_rate")
            net_ev = strategy.get("net_expected_points")
            net_ev_per_deal = strategy.get("net_expected_points_per_deal")
            ev_per_deal = strategy.get("expected_points_per_deal")
            net_cvar = strategy.get("net_cvar_5")
            net_downside_var = strategy.get("net_downside_variance")
            make_rate = strategy.get("make_rate")

            # Format values
            bid_rate_str = f"{bid_rate:.1%}" if bid_rate is not None else "N/A"
            net_ev_str = f"{net_ev:.3f}" if net_ev is not None else "N/A"
            net_ev_deal_str = (
                f"{net_ev_per_deal:.3f}" if net_ev_per_deal is not None else "N/A"
            )
            ev_deal_str = f"{ev_per_deal:.3f}" if ev_per_deal is not None else "N/A"
            net_cvar_str = f"{net_cvar:.3f}" if net_cvar is not None else "N/A"
            net_downside_str = (
                f"{net_downside_var:.3f}" if net_downside_var is not None else "N/A"
            )
            make_rate_str = f"{make_rate:.1%}" if make_rate is not None else "N/A"

            f.write(
                f"| {strategy_id} | {deals} | {hands} | {bid_rate_str} | {net_ev_str} | {net_ev_deal_str} | {ev_deal_str} | {net_cvar_str} | {net_downside_str} | {make_rate_str} |\n"
            )

        f.write("\n")
        f.write(
            "**Note:** Higher Net EV and Make Rate are better. Lower Net CVaR-5% and Downside Variance indicate lower risk.\n\n"
        )
        f.write(
            "*Generated: {}*\n".format(
                datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            )
        )


def _generate_baseline_matrix_report(
    run_dir: Path, strategy_metrics: List[Dict]
) -> None:
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
            "expected_points_per_deal": strategy.get("expected_points_per_deal"),
            "net_expected_points": strategy.get("net_expected_points"),
            "net_expected_points_per_deal": strategy.get(
                "net_expected_points_per_deal"
            ),
            "make_rate": strategy.get("make_rate"),
            "bid_rate": strategy.get("bid_rate"),
            "pass_rate": strategy.get("pass_rate"),
            "cvar_5": strategy.get("cvar_5"),
            "downside_variance": strategy.get("downside_variance"),
            "net_cvar_5": strategy.get("net_cvar_5"),
            "net_downside_variance": strategy.get("net_downside_variance"),
            "n_hands": strategy.get("hands_with_bids", 0),
            "n_deals": strategy.get("deals_total", 0),
        }
        matrix.append(entry)

    payload = {
        "run_id": Path(run_dir).name,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "description": "Baseline matrix report with deterministic strategy ordering",
        "strategies": matrix,
    }

    with output_path.open("w") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def generate_bidder_evaluation(run_dir: Path) -> Optional[Path]:
    """
    Generate evaluation JSON and markdown report summarizing metrics per bidder strategy.

    The primary series is `net_bidder_team_points` (net differential: bidder - opponent).
    Secondary series `bidder_team_points` is retained for backward compatibility.
    CVaR-5% is defined as the average of the worst 5% of outcomes.
    Downside variance is the variance of returns that fall below zero.
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
        deals_total = len(records)
        bidder_points: List[int] = []
        net_points: List[int] = []
        made_count = 0
        for record in records:
            points = _bidder_team_points(record)
            if points is None:
                continue
            bidder_points.append(points)
            if points >= 0:
                made_count += 1

            net = _net_differential_points(record)
            if net is not None:
                net_points.append(net)

        hands_with_bids = len(bidder_points)
        expected = sum(bidder_points) / hands_with_bids if hands_with_bids else None
        expected_per_deal = sum(bidder_points) / deals_total if deals_total else None
        make_rate = made_count / hands_with_bids if hands_with_bids else None
        bid_rate = hands_with_bids / deals_total if deals_total else None
        pass_rate = (1.0 - bid_rate) if bid_rate is not None else None

        # Net-differential metrics
        net_hands = len(net_points)
        net_expected = sum(net_points) / net_hands if net_hands else None
        net_expected_per_deal = sum(net_points) / deals_total if deals_total else None

        entry = {
            "strategy_id": strategy_id,
            "deals_total": deals_total,
            "hands_with_bids": hands_with_bids,
            "bidder_team_points": bidder_points,
            "net_bidder_team_points": net_points,
            "expected_points": _round(expected),
            "expected_points_per_deal": _round(expected_per_deal),
            "net_expected_points": _round(net_expected),
            "net_expected_points_per_deal": _round(net_expected_per_deal),
            "make_rate": _round(make_rate),
            "bid_rate": _round(bid_rate),
            "pass_rate": _round(pass_rate),
            "cvar_5": _round(compute_cvar(bidder_points)),
            "downside_variance": _round(compute_downside_variance(bidder_points)),
            "net_cvar_5": _round(compute_cvar(net_points)),
            "net_downside_variance": _round(compute_downside_variance(net_points)),
        }
        strategy_metrics.append(entry)

    output_dir = Path(run_dir) / "reports" / "bidding_strategy"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "evaluation.json"

    payload = {
        "run_id": Path(run_dir).name,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "primary_series": "net_bidder_team_points",
        "source_logs": [str(p.relative_to(run_dir)) for p in used_log_files],
        "strategies": strategy_metrics,
        "metric_definitions": {
            "net_expected_points": "net EV (bidder - opponent) over hands with bids",
            "net_expected_points_per_deal": "net EV per deal with 0 for all-pass redeals",
            "net_cvar_5": "avg of worst 5% net_bidder_team_points",
            "net_downside_variance": "variance of net_bidder_team_points below 0",
            "cvar_5": "avg of worst 5% bidder_team_points (secondary)",
            "downside_variance": "variance of bidder_team_points below 0 (secondary)",
            "expected_points": "EV over hands with an auction winner (secondary)",
            "expected_points_per_deal": "EV per deal with 0 for all-pass redeals (secondary)",
            "bid_rate": "fraction of deals with an auction winner",
            "pass_rate": "fraction of deals that are all-pass redeals",
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
