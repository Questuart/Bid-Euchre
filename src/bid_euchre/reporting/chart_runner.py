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
)

AVAILABLE_SUITES = ["feature_health", "feature_outcome", "distribution", "all"]


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
