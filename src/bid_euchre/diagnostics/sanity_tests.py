"""
Strategy sanity tests for bidless experiments.

This module provides statistical sanity checks for validating strategy behavior
in bidless (declared contract) experiments. Tests are designed to catch:
- Self-play bias (team 0 shouldn't systematically beat team 1 in self-play)
- Random dominance failures (greedy/glutton should beat random_legal)
- Rank instability (strategy rankings should be consistent across contracts)
- Transitivity violations (if A>B and B>C, then A>C)

Usage:
    from bid_euchre.diagnostics.sanity_tests import run_sanity_tests

    results = run_sanity_tests(run_dir)
    print(results["self_play_fairness"]["status"])  # "PASS", "WARN", or "FAIL"
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class SanityTestResult:
    """Result of a single sanity test."""

    name: str
    status: str  # "PASS", "WARN", "FAIL", "SKIP"
    message: str
    details: Dict[str, Any]


def run_sanity_tests(
    run_dir: str,
    outcomes_df: Optional[pd.DataFrame] = None,
) -> Dict[str, SanityTestResult]:
    """
    Run all sanity tests for a bidless experiment run.

    Args:
        run_dir: Path to run directory containing results/ and datasets/
        outcomes_df: Optional pre-loaded outcomes DataFrame. If None, will try
                    to load from bidless_outcomes.parquet or results/*.json.

    Returns:
        Dict mapping test name to SanityTestResult
    """
    run_path = Path(run_dir)

    # Load outcomes data
    if outcomes_df is None:
        outcomes_df = _load_outcomes_data(run_path)

    if outcomes_df is None or len(outcomes_df) == 0:
        return {
            "error": SanityTestResult(
                name="error",
                status="SKIP",
                message="No outcomes data found",
                details={"run_dir": str(run_dir)},
            )
        }

    results = {}

    # Run each test
    results["self_play_fairness"] = test_self_play_fairness(outcomes_df)
    results["random_dominance"] = test_random_dominance(outcomes_df)
    results["rank_stability"] = test_rank_stability(outcomes_df)
    results["transitivity"] = test_transitivity(outcomes_df)

    return results


def test_self_play_fairness(df: pd.DataFrame) -> SanityTestResult:
    """
    Test that self-play matchups are fair (team 0 ≈ team 1).

    For each self-play matchup (where team0_strategy == team1_strategy),
    compute the mean delta (team0_tricks - team1_tricks) and check if
    it's close to 0.

    Criteria:
    - PASS: |mean_delta| < 0.25 for all self-play matchups
    - FAIL: |mean_delta| >= 0.5 for any self-play matchup
    - WARN: otherwise
    """
    # Identify self-play matchups
    if "team0_strategy" not in df.columns or "team1_strategy" not in df.columns:
        # Fall back to matchup_id parsing
        if "matchup_id" not in df.columns:
            return SanityTestResult(
                name="self_play_fairness",
                status="SKIP",
                message="No strategy columns found",
                details={},
            )
        df = df.copy()
        # Parse matchup_id like "greedy_vs_greedy"
        parts = df["matchup_id"].str.split("_vs_", expand=True)
        if parts.shape[1] == 2:
            df["team0_strategy"] = parts[0]
            df["team1_strategy"] = parts[1]
        else:
            return SanityTestResult(
                name="self_play_fairness",
                status="SKIP",
                message="Could not parse matchup_id",
                details={},
            )

    self_play = df[df["team0_strategy"] == df["team1_strategy"]]

    if len(self_play) == 0:
        return SanityTestResult(
            name="self_play_fairness",
            status="SKIP",
            message="No self-play matchups found",
            details={},
        )

    # Compute per-strategy mean delta
    if "tricks_team0" in self_play.columns:
        self_play = self_play.copy()
        self_play["delta"] = self_play["tricks_team0"] - self_play["tricks_team1"]
    else:
        # Compute from tricks_won assuming seat 0 is team 0
        return SanityTestResult(
            name="self_play_fairness",
            status="SKIP",
            message="No tricks_team0/tricks_team1 columns",
            details={},
        )

    strategy_deltas = self_play.groupby("team0_strategy")["delta"].agg(["mean", "std", "count"])

    violations = []
    warnings = []

    for strategy, row in strategy_deltas.iterrows():
        mean_delta = row["mean"]
        if abs(mean_delta) >= 0.5:
            violations.append({"strategy": strategy, "mean_delta": round(mean_delta, 4)})
        elif abs(mean_delta) >= 0.25:
            warnings.append({"strategy": strategy, "mean_delta": round(mean_delta, 4)})

    details = {
        "strategy_deltas": strategy_deltas.to_dict("index"),
        "violations": violations,
        "warnings": warnings,
    }

    if violations:
        return SanityTestResult(
            name="self_play_fairness",
            status="FAIL",
            message=f"Self-play bias detected: {len(violations)} strategies with |delta| >= 0.5",
            details=details,
        )
    elif warnings:
        return SanityTestResult(
            name="self_play_fairness",
            status="WARN",
            message=f"Minor self-play bias: {len(warnings)} strategies with |delta| >= 0.25",
            details=details,
        )
    else:
        return SanityTestResult(
            name="self_play_fairness",
            status="PASS",
            message="All self-play matchups are fair (|delta| < 0.25)",
            details=details,
        )


def test_random_dominance(df: pd.DataFrame) -> SanityTestResult:
    """
    Test that intelligent strategies beat random_legal.

    Greedy and glutton should have win_rate > 0.52 against random_legal.

    Criteria:
    - PASS: All intelligent strategies beat random at > 0.52
    - FAIL: Any intelligent strategy loses to random (< 0.5)
    - WARN: Win rate between 0.5 and 0.52
    """
    intelligent_strategies = {"greedy", "glutton"}

    # Find matchups of intelligent vs random_legal
    if "team0_strategy" not in df.columns or "team0_win" not in df.columns:
        return SanityTestResult(
            name="random_dominance",
            status="SKIP",
            message="Required columns not found",
            details={},
        )

    results_list = []

    for strategy in intelligent_strategies:
        # Check both directions
        for team0_name, team1_name in [(strategy, "random_legal"), ("random_legal", strategy)]:
            matchup = df[
                (df["team0_strategy"] == team0_name) &
                (df["team1_strategy"] == team1_name)
            ]

            if len(matchup) == 0:
                continue

            win_rate = matchup["team0_win"].mean()

            # If intelligent strategy is team0, win_rate should be high
            # If intelligent strategy is team1, win_rate should be low
            if team0_name == strategy:
                intelligent_win_rate = win_rate
            else:
                intelligent_win_rate = 1.0 - win_rate

            results_list.append({
                "strategy": strategy,
                "vs": "random_legal",
                "matchup": f"{team0_name}_vs_{team1_name}",
                "intelligent_win_rate": round(intelligent_win_rate, 4),
                "n_hands": len(matchup),
            })

    if not results_list:
        return SanityTestResult(
            name="random_dominance",
            status="SKIP",
            message="No intelligent vs random_legal matchups found",
            details={},
        )

    violations = [r for r in results_list if r["intelligent_win_rate"] < 0.5]
    warnings = [r for r in results_list if 0.5 <= r["intelligent_win_rate"] < 0.52]
    passes = [r for r in results_list if r["intelligent_win_rate"] >= 0.52]

    details = {
        "matchups": results_list,
        "violations": violations,
        "warnings": warnings,
        "passes": passes,
    }

    if violations:
        return SanityTestResult(
            name="random_dominance",
            status="FAIL",
            message=f"Intelligent strategy lost to random: {[v['strategy'] for v in violations]}",
            details=details,
        )
    elif warnings:
        return SanityTestResult(
            name="random_dominance",
            status="WARN",
            message=f"Marginal dominance: {len(warnings)} matchups with win_rate < 0.52",
            details=details,
        )
    else:
        return SanityTestResult(
            name="random_dominance",
            status="PASS",
            message="All intelligent strategies beat random_legal (win_rate > 0.52)",
            details=details,
        )


def test_rank_stability(df: pd.DataFrame) -> SanityTestResult:
    """
    Test that strategy rankings are stable across contract families.

    Computes Kendall's tau between strategy rankings in different contract
    families (suit vs high vs low).

    Criteria:
    - PASS: min(tau) > 0.6 across all family pairs
    - WARN: any tau < 0.3
    - SKIP: insufficient data
    """
    if "contract_type" not in df.columns or "team0_win" not in df.columns:
        return SanityTestResult(
            name="rank_stability",
            status="SKIP",
            message="Required columns not found",
            details={},
        )

    if "strategy_id" not in df.columns and "team0_strategy" not in df.columns:
        return SanityTestResult(
            name="rank_stability",
            status="SKIP",
            message="No strategy column found",
            details={},
        )

    strategy_col = "strategy_id" if "strategy_id" in df.columns else "team0_strategy"

    # Compute mean win rate per strategy per contract family
    family_rankings = {}
    for contract_type in df["contract_type"].unique():
        subset = df[df["contract_type"] == contract_type]
        rankings = subset.groupby(strategy_col)["team0_win"].mean().sort_values(ascending=False)
        family_rankings[contract_type] = rankings

    if len(family_rankings) < 2:
        return SanityTestResult(
            name="rank_stability",
            status="SKIP",
            message="Need at least 2 contract families for comparison",
            details={},
        )

    # Compute pairwise Kendall's tau
    from scipy.stats import kendalltau

    tau_results = []
    families = list(family_rankings.keys())

    for i, fam1 in enumerate(families):
        for fam2 in families[i+1:]:
            # Get common strategies
            common = set(family_rankings[fam1].index) & set(family_rankings[fam2].index)
            if len(common) < 3:
                continue

            common = sorted(common)
            rank1 = [family_rankings[fam1][s] for s in common]
            rank2 = [family_rankings[fam2][s] for s in common]

            tau, p_value = kendalltau(rank1, rank2)
            tau_results.append({
                "family1": fam1,
                "family2": fam2,
                "tau": round(tau, 4),
                "p_value": round(p_value, 4),
                "n_strategies": len(common),
            })

    if not tau_results:
        return SanityTestResult(
            name="rank_stability",
            status="SKIP",
            message="Insufficient overlapping strategies between contract families",
            details={},
        )

    min_tau = min(r["tau"] for r in tau_results)

    details = {
        "pairwise_tau": tau_results,
        "min_tau": min_tau,
    }

    if min_tau < 0.3:
        return SanityTestResult(
            name="rank_stability",
            status="WARN",
            message=f"Rank instability detected: min(tau) = {min_tau:.2f}",
            details=details,
        )
    elif min_tau > 0.6:
        return SanityTestResult(
            name="rank_stability",
            status="PASS",
            message=f"Rankings stable across contract families (min tau = {min_tau:.2f})",
            details=details,
        )
    else:
        return SanityTestResult(
            name="rank_stability",
            status="PASS",
            message=f"Rankings moderately stable (min tau = {min_tau:.2f})",
            details=details,
        )


def test_transitivity(df: pd.DataFrame) -> SanityTestResult:
    """
    Test for transitivity violations in win rates.

    If A beats B and B beats C, then A should beat C.

    Criteria:
    - PASS: No transitivity violations
    - WARN: Transitivity violations found (informational only)
    """
    if "team0_strategy" not in df.columns or "team1_strategy" not in df.columns:
        return SanityTestResult(
            name="transitivity",
            status="SKIP",
            message="Required columns not found",
            details={},
        )

    if "team0_win" not in df.columns:
        return SanityTestResult(
            name="transitivity",
            status="SKIP",
            message="team0_win column not found",
            details={},
        )

    # Build win rate matrix
    strategies = sorted(set(df["team0_strategy"]) | set(df["team1_strategy"]))

    if len(strategies) < 3:
        return SanityTestResult(
            name="transitivity",
            status="SKIP",
            message="Need at least 3 strategies for transitivity check",
            details={},
        )

    win_matrix = {}
    for s1 in strategies:
        win_matrix[s1] = {}
        for s2 in strategies:
            if s1 == s2:
                win_matrix[s1][s2] = 0.5
                continue

            matchup = df[
                (df["team0_strategy"] == s1) &
                (df["team1_strategy"] == s2)
            ]

            if len(matchup) > 0:
                win_matrix[s1][s2] = matchup["team0_win"].mean()
            else:
                win_matrix[s1][s2] = None

    # Check transitivity: if A>B and B>C, then A>C
    margin = 0.01  # Margin for "beats"
    violations = []

    for a in strategies:
        for b in strategies:
            if a == b:
                continue
            win_ab = win_matrix[a].get(b)
            if win_ab is None or win_ab <= 0.5 + margin:
                continue  # A doesn't beat B

            for c in strategies:
                if c in (a, b):
                    continue
                win_bc = win_matrix[b].get(c)
                win_ac = win_matrix[a].get(c)

                if win_bc is None or win_ac is None:
                    continue

                # A beats B, B beats C
                if win_bc > 0.5 + margin:
                    # A should beat C
                    if win_ac <= 0.5:
                        violations.append({
                            "A": a, "B": b, "C": c,
                            "A_vs_B": round(win_ab, 3),
                            "B_vs_C": round(win_bc, 3),
                            "A_vs_C": round(win_ac, 3),
                        })

    details = {
        "n_strategies": len(strategies),
        "violations": violations,
    }

    if violations:
        return SanityTestResult(
            name="transitivity",
            status="WARN",
            message=f"Found {len(violations)} transitivity violations",
            details=details,
        )
    else:
        return SanityTestResult(
            name="transitivity",
            status="PASS",
            message="No transitivity violations found",
            details=details,
        )


def _load_outcomes_data(run_path: Path) -> Optional[pd.DataFrame]:
    """
    Load outcomes data from run directory.

    Prefers bidless_outcomes.parquet, falls back to parsing results/*.json.
    """
    # Try outcomes parquet first
    outcomes_parquet = run_path / "datasets" / "bidless_outcomes.parquet"
    if outcomes_parquet.exists():
        return pd.read_parquet(outcomes_parquet)

    # Fall back to parsing results JSON files
    results_dir = run_path / "results"
    if not results_dir.exists():
        return None

    rows = []
    for matchup_dir in sorted(results_dir.iterdir()):
        if not matchup_dir.is_dir():
            continue

        matchup_id = matchup_dir.name
        # Parse team names from matchup_id (e.g., "greedy_vs_random_legal")
        parts = matchup_id.split("_vs_")
        if len(parts) == 2:
            team0_strategy, team1_strategy = parts
        else:
            team0_strategy = team1_strategy = matchup_id

        for result_file in sorted(matchup_dir.glob("*.json")):
            with open(result_file) as f:
                result = json.load(f)

            # Parse scenario from filename
            scenario = result_file.stem
            contract_type = scenario.split("_")[0] if "_" in scenario else scenario
            trump_suit = scenario.split("_")[1] if "_" in scenario and len(scenario.split("_")) > 1 else None

            # Expand distribution to per-hand rows
            distribution = result.get("distribution_team0", {})
            for tricks_str, count in distribution.items():
                tricks = int(tricks_str)
                team0_win = 1.0 if tricks > 5 else (0.5 if tricks == 5 else 0.0)

                for _ in range(count):
                    rows.append({
                        "matchup_id": matchup_id,
                        "team0_strategy": team0_strategy,
                        "team1_strategy": team1_strategy,
                        "contract_type": contract_type,
                        "trump_suit": trump_suit,
                        "tricks_team0": tricks,
                        "tricks_team1": 10 - tricks,
                        "team0_win": team0_win,
                    })

    if not rows:
        return None

    return pd.DataFrame(rows)


def serialize_results(results: Dict[str, SanityTestResult]) -> Dict[str, Any]:
    """Convert SanityTestResult objects to JSON-serializable dict."""
    return {
        name: {
            "name": result.name,
            "status": result.status,
            "message": result.message,
            "details": _make_json_serializable(result.details),
        }
        for name, result in results.items()
    }


def _make_json_serializable(obj: Any) -> Any:
    """Convert numpy types and other non-serializable objects to JSON-safe types."""
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif pd.isna(obj):
        return None
    else:
        return obj


def write_sanity_report(
    run_dir: str,
    results: Dict[str, SanityTestResult],
) -> Tuple[Path, Path]:
    """
    Write sanity test results to JSON and Markdown files.

    Args:
        run_dir: Path to run directory
        results: Dict of sanity test results

    Returns:
        Tuple of (json_path, md_path)
    """
    run_path = Path(run_dir)
    sanity_dir = run_path / "reports" / "sanity_tests"
    sanity_dir.mkdir(parents=True, exist_ok=True)

    # Write JSON
    json_path = sanity_dir / "strategy_sanity.json"
    with open(json_path, "w") as f:
        json.dump(serialize_results(results), f, indent=2)

    # Write Markdown
    md_path = sanity_dir / "strategy_sanity.md"
    with open(md_path, "w") as f:
        f.write("# Strategy Sanity Test Results\n\n")

        # Summary table
        f.write("## Summary\n\n")
        f.write("| Test | Status | Message |\n")
        f.write("|------|--------|--------|\n")

        for name, result in results.items():
            status_emoji = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}.get(result.status, "❓")
            f.write(f"| {result.name} | {status_emoji} {result.status} | {result.message} |\n")

        f.write("\n")

        # Details for each test
        f.write("## Details\n\n")
        for name, result in results.items():
            f.write(f"### {result.name}\n\n")
            f.write(f"**Status:** {result.status}\n\n")
            f.write(f"**Message:** {result.message}\n\n")

            if result.details:
                f.write("**Details:**\n```json\n")
                f.write(json.dumps(_make_json_serializable(result.details), indent=2))
                f.write("\n```\n\n")

    return json_path, md_path
