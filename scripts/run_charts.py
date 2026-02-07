#!/usr/bin/env python3
"""Generate production charts from run data.

Thin CLI wrapper around bid_euchre.reporting.chart_runner.

Usage:
    PYTHONPATH=src python scripts/run_charts.py \
        --run-dir data/runs/<run_id> \
        --output-dir /tmp/charts/ \
        --suite feature_health
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from bid_euchre.reporting.chart_runner import (
    AVAILABLE_SUITES,
    _load_bidless_features,
    _load_features_with_outcomes,
    _load_matchup_results,
)
from bid_euchre.reporting.charts import (
    generate_contract_faceted_charts,
    generate_distribution_charts,
    generate_feature_health_charts,
    generate_feature_outcome_charts,
    generate_strategy_matchup_charts,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate production charts from run data"
    )
    parser.add_argument(
        "--run-dir", required=True, help="Path to experiment run directory"
    )
    parser.add_argument("--output-dir", required=True, help="Output directory for PNGs")
    parser.add_argument(
        "--suite",
        choices=AVAILABLE_SUITES,
        default="all",
        help="Which chart suite to generate (default: all)",
    )
    parser.add_argument(
        "--dpi", type=int, default=150, help="Output resolution (default: 150)"
    )

    # Publish flags
    parser.add_argument(
        "--publish-report-assets",
        action="store_true",
        help="Publish charts as a versioned snapshot to assets root",
    )
    parser.add_argument(
        "--assets-root",
        default="docs/04_reports/assets",
        help="Assets root for publishing (default: docs/04_reports/assets)",
    )
    parser.add_argument(
        "--asset-prefix",
        default="phase0",
        help="Snapshot prefix (default: phase0)",
    )
    parser.add_argument(
        "--snapshot-id",
        default=None,
        help="Explicit snapshot ID (auto-generated if omitted)",
    )
    parser.add_argument(
        "--no-update-latest",
        dest="update_latest",
        action="store_false",
        help="Skip updating the latest alias",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_paths: list[str] = []
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
            paths = generate_strategy_matchup_charts(
                matchup_results, suite_dir, dpi=args.dpi
            )

        elif suite == "contract_faceted":
            df = _load_features_with_outcomes(run_dir)
            suite_dir = str(output_dir / suite)
            paths = generate_contract_faceted_charts(df, suite_dir, dpi=args.dpi)

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

    # Publish if requested
    if args.publish_report_assets:
        from bid_euchre.reporting.publish import (
            publish_chart_snapshot,
            update_versions_manifest,
        )

        assets_root = Path(args.assets_root)
        sid = publish_chart_snapshot(
            output_dir,
            assets_root,
            args.asset_prefix,
            snapshot_id=args.snapshot_id,
            update_latest=args.update_latest,
        )
        chart_files = [p.name for p in sorted((assets_root / sid).glob("*.png"))]
        mf = update_versions_manifest(
            assets_root,
            args.asset_prefix,
            sid,
            chart_files,
            source_run_ids=[str(run_dir.name)],
        )
        print(f"\nPublished snapshot: {sid}")
        print(f"Versions manifest: {mf}")


if __name__ == "__main__":
    main()
