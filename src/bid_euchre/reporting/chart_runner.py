"""CLI for generating production charts from run data.

Usage:
    uv run python -m bid_euchre.reporting.chart_runner \
        --run-dir data/runs/<run_id> \
        --output-dir /tmp/charts/ \
        --suite feature_health
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .charts import (
    generate_distribution_charts,
    generate_feature_health_charts,
    generate_feature_outcome_charts,
    generate_strategy_matchup_charts,
)

AVAILABLE_SUITES = ["feature_health", "feature_outcome", "distribution", "strategy_matchup", "all"]


def _load_bidless_features(run_dir: Path) -> pd.DataFrame:
    """Load bidless features from a run directory."""
    parquet_path = run_dir / "datasets" / "bidless.parquet"
    if not parquet_path.exists():
        raise FileNotFoundError(f"No bidless.parquet found in {run_dir / 'datasets'}")
    return pd.read_parquet(parquet_path)


def _load_features_with_outcomes(run_dir: Path) -> pd.DataFrame:
    """Load features joined with outcomes from a run directory."""
    from ..datasets.join import join_features_outcomes

    bidless_path = str(run_dir / "datasets" / "bidless.parquet")
    outcomes_path = str(run_dir / "datasets" / "bidless_outcomes.parquet")

    if not Path(bidless_path).exists():
        raise FileNotFoundError(f"Missing: {bidless_path}")
    if not Path(outcomes_path).exists():
        raise FileNotFoundError(f"Missing: {outcomes_path}")

    return join_features_outcomes(bidless_path, outcomes_path)


def _load_matchup_results(run_dir: Path) -> dict:
    """Load strategy matchup results from a matrix run directory.

    Reads results/<team0>_vs_<team1>/*.json and aggregates into
    Dict[(team0, team1), Dict] suitable for generate_strategy_matchup_charts.

    Returns empty dict if the run is not a matrix run.
    """
    results_dir = run_dir / "results"
    if not results_dir.exists():
        return {}

    matchup_results = {}
    for matchup_dir in sorted(results_dir.iterdir()):
        if not matchup_dir.is_dir():
            continue
        name = matchup_dir.name
        if "_vs_" not in name:
            continue

        team0, team1 = name.split("_vs_", maxsplit=1)

        # Aggregate scenario JSONs in this matchup directory
        scenario_files = sorted(matchup_dir.glob("*.json"))
        if not scenario_files:
            continue

        total_deals = 0
        weighted_win_rate = 0.0
        weighted_mean_t0 = 0.0
        weighted_mean_t1 = 0.0
        all_tricks_t0 = []

        for sf in scenario_files:
            with open(sf) as f:
                data = json.load(f)
            n = data.get("deals", data.get("hands", 0))
            if n == 0:
                continue
            total_deals += n
            weighted_win_rate += data.get("win_rate_team0", 0) * n
            weighted_mean_t0 += data.get("avg_team0", data.get("mean_tricks_team0", 0)) * n
            weighted_mean_t1 += data.get("avg_team1", data.get("mean_tricks_team1", 0)) * n

            # Reconstruct trick list from distribution histogram if available
            dist = data.get("distribution_team0", {})
            for k_str, count in dist.items():
                all_tricks_t0.extend([int(k_str)] * count)

        if total_deals == 0:
            continue

        result = {
            "win_rate": weighted_win_rate / total_deals,
            "mean_tricks_team0": weighted_mean_t0 / total_deals,
            "mean_tricks_team1": weighted_mean_t1 / total_deals,
            "mean_tricks": weighted_mean_t0 / total_deals,
            "deals": total_deals,
        }
        if all_tricks_t0:
            result["tricks_team0"] = all_tricks_t0

        matchup_results[(team0, team1)] = result

    return matchup_results


def main():
    parser = argparse.ArgumentParser(description="Generate production charts from run data")
    parser.add_argument("--run-dir", required=True, help="Path to experiment run directory")
    parser.add_argument("--output-dir", required=True, help="Output directory for PNGs")
    parser.add_argument(
        "--suite",
        choices=AVAILABLE_SUITES,
        default="all",
        help="Which chart suite to generate (default: all)",
    )
    parser.add_argument("--dpi", type=int, default=150, help="Output resolution (default: 150)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_paths = []
    suites = AVAILABLE_SUITES[:-1] if args.suite == "all" else [args.suite]

    for suite in suites:
        print(f"Generating {suite} charts...")

        if suite == "feature_health":
            df = _load_bidless_features(run_dir)
            # Flatten struct columns if present
            if "hand_features" in df.columns:
                features = pd.json_normalize(df["hand_features"].tolist())
                df = pd.concat([df.drop(columns=["hand_features"]), features], axis=1)
            suite_dir = str(output_dir / suite)
            paths = generate_feature_health_charts(df, suite_dir, dpi=args.dpi)

        elif suite == "feature_outcome":
            df = _load_features_with_outcomes(run_dir)
            suite_dir = str(output_dir / suite)
            paths = generate_feature_outcome_charts(df, suite_dir, dpi=args.dpi)

        elif suite == "distribution":
            df = _load_features_with_outcomes(run_dir)
            suite_dir = str(output_dir / suite)
            paths = generate_distribution_charts(df, suite_dir, dpi=args.dpi)

        elif suite == "strategy_matchup":
            matchup_results = _load_matchup_results(run_dir)
            if not matchup_results:
                print("  Skipping strategy_matchup: no matchup data found in results/")
                continue
            suite_dir = str(output_dir / suite)
            paths = generate_strategy_matchup_charts(matchup_results, suite_dir, dpi=args.dpi)

        else:
            print(f"  Unknown suite: {suite}")
            continue

        all_paths.extend(paths)
        print(f"  Generated {len(paths)} chart(s)")

    # Write manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({"charts": all_paths, "run_dir": str(run_dir)}, f, indent=2)

    print(f"\nTotal: {len(all_paths)} chart(s) generated")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
