"""
Paired comparison analysis for strategies on common deals.
"""

import json
import os
from glob import glob
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np
from .stats import paired_t_ci


def load_paired_data(run_dir: str, strategies: List[str]) -> Dict[str, Dict[str, List[Dict]]]:
    """
    Load paired hand-level data from JSONL logs for multiple strategies.

    Returns dict:
        {strategy: {scenario: [hand_records]}}

    Each hand_record has: deal_id, seed, contract, trump, leader, t0, t1, features, scores
    """
    logs_dir = os.path.join(run_dir, "logs")

    strategy_data = {}
    for strategy in strategies:
        log_files = glob(os.path.join(logs_dir, f"*{strategy}.jsonl"))

        if not log_files:
            continue

        # Group records by scenario
        scenario_records = defaultdict(list)

        for log_file in log_files:
            with open(log_file, "r") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        if record.get("event") == "hand_end":
                            # Create scenario key
                            contract = record["contract"]
                            trump = record.get("trump")
                            if contract == "suit" and trump:
                                scenario = f"suit_{trump}"
                            else:
                                scenario = contract

                            scenario_records[scenario].append(record)
                    except (json.JSONDecodeError, KeyError):
                        continue

        strategy_data[strategy] = dict(scenario_records)

    return strategy_data


def compute_paired_deltas(
    strategy_data: Dict[str, Dict[str, List[Dict]]],
    baseline_strategy: str,
    comparison_strategy: str,
    scenario: Optional[str] = None
) -> Dict[str, List[float]]:
    """
    Compute paired differences (comparison - baseline) for deals that both strategies played.

    Args:
        strategy_data: Output from load_paired_data
        baseline_strategy: Name of baseline strategy
        comparison_strategy: Name of strategy to compare
        scenario: Optional specific scenario to analyze (e.g., "suit_H", "high")

    Returns:
        Dict with:
            - "deltas": List of paired differences in Team 0 tricks
            - "deal_ids": List of matching deal IDs
            - "baseline_tricks": List of baseline Team 0 tricks
            - "comparison_tricks": List of comparison Team 0 tricks
    """
    if baseline_strategy not in strategy_data:
        raise ValueError(f"Baseline strategy '{baseline_strategy}' not found in data")
    if comparison_strategy not in strategy_data:
        raise ValueError(f"Comparison strategy '{comparison_strategy}' not found in data")

    baseline_records = strategy_data[baseline_strategy]
    comparison_records = strategy_data[comparison_strategy]

    # Get scenarios to analyze
    if scenario:
        scenarios = [scenario] if scenario in baseline_records and scenario in comparison_records else []
    else:
        scenarios = set(baseline_records.keys()) & set(comparison_records.keys())

    # Build paired data indexed by (deal_id, seed)
    deltas = []
    deal_ids = []
    baseline_tricks_list = []
    comparison_tricks_list = []

    for scen in scenarios:
        base_hands = baseline_records.get(scen, [])
        comp_hands = comparison_records.get(scen, [])

        # Index by (deal_id, seed) for matching
        base_index = {(h["deal_id"], h["seed"]): h for h in base_hands}
        comp_index = {(h["deal_id"], h["seed"]): h for h in comp_hands}

        # Find matching deals
        common_keys = set(base_index.keys()) & set(comp_index.keys())

        for key in sorted(common_keys):
            base_hand = base_index[key]
            comp_hand = comp_index[key]

            # Sanity check: same deal setup
            if base_hand["contract"] != comp_hand["contract"]:
                continue
            if base_hand.get("trump") != comp_hand.get("trump"):
                continue
            if base_hand["leader"] != comp_hand["leader"]:
                continue

            # Compute delta
            base_t0 = base_hand["t0"]
            comp_t0 = comp_hand["t0"]
            delta = comp_t0 - base_t0

            deltas.append(delta)
            deal_ids.append(key)
            baseline_tricks_list.append(base_t0)
            comparison_tricks_list.append(comp_t0)

    return {
        "deltas": deltas,
        "deal_ids": deal_ids,
        "baseline_tricks": baseline_tricks_list,
        "comparison_tricks": comparison_tricks_list,
        "n_matched": len(deltas),
    }


def paired_comparison_summary(
    deltas: List[float],
    confidence: float = 0.95
) -> Dict[str, float]:
    """
    Compute summary statistics for paired differences.

    Args:
        deltas: List of paired differences (strategy - baseline)
        confidence: Confidence level for intervals

    Returns:
        Dict with mean_delta, ci_lower, ci_upper, pct_improved, pct_worse, pct_tied
    """
    if len(deltas) == 0:
        return {
            "mean_delta": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "pct_improved": 0.0,
            "pct_worse": 0.0,
            "pct_tied": 0.0,
            "n": 0,
        }

    deltas = np.array(deltas)
    mean_delta, ci_lower, ci_upper = paired_t_ci(deltas.tolist(), confidence)

    improved = np.sum(deltas > 0)
    worse = np.sum(deltas < 0)
    tied = np.sum(deltas == 0)
    n = len(deltas)

    return {
        "mean_delta": float(mean_delta),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "pct_improved": float(improved / n * 100),
        "pct_worse": float(worse / n * 100),
        "pct_tied": float(tied / n * 100),
        "n": int(n),
    }
