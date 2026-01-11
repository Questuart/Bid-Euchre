#!/usr/bin/env python
"""
Compare rollup.json summary metrics against a baseline fixture.

Fixture Schema (v0):
{
  "schema_version": 0,
  "description": "Expected metrics for baseline_full suite configs",
  "default_tolerance": 0.01,
  "configs": {
    "config_name.yaml": {
      "avg_tricks": 4.23,
      "tolerance": 0.01  // optional, falls back to default_tolerance
    }
  }
}

Rollup Schema:
{
  "summary": [
    {
      "config": "config_name.yaml",
      "status": "ok",
      "avg_tricks": 4.23,
      ...
    }
  ]
}

Usage:
    python scripts/compare_rollup.py --rollup path/to/rollup.json --fixture data/fixtures/baseline_full_expected.json

Exit codes:
    0: All metrics within tolerance
    1: One or more metrics exceed tolerance
    2: Missing expected configs or unexpected configs present
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Tuple


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Compare rollup.json summary metrics against a baseline fixture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--rollup",
        required=True,
        help="Path to rollup.json file to compare"
    )
    parser.add_argument(
        "--fixture",
        required=True,
        help="Path to fixture JSON file containing expected metrics"
    )
    return parser.parse_args()


def load_json_file(path: str) -> Dict[str, Any]:
    """Load and parse JSON file with clear error messages."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def validate_rollup_structure(rollup: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate rollup has required summary array and return it."""
    if "summary" not in rollup:
        print("ERROR: rollup.json missing 'summary' key", file=sys.stderr)
        sys.exit(1)

    summary = rollup["summary"]
    if not isinstance(summary, list):
        print("ERROR: rollup.json 'summary' is not an array", file=sys.stderr)
        sys.exit(1)

    return summary


def validate_fixture_structure(fixture: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
    """Validate fixture structure and return configs dict and default tolerance."""
    if fixture.get("schema_version") != 0:
        print(f"ERROR: Unsupported fixture schema version: {fixture.get('schema_version')}", file=sys.stderr)
        sys.exit(1)

    if "configs" not in fixture:
        print("ERROR: fixture missing 'configs' key", file=sys.stderr)
        sys.exit(1)

    configs = fixture["configs"]
    if not isinstance(configs, dict):
        print("ERROR: fixture 'configs' is not an object", file=sys.stderr)
        sys.exit(1)

    # Check for unpopulated fixture
    if not configs and fixture.get("note", "").upper().find("UNPOPULATED") != -1:
        print("ERROR: Fixture is not yet populated with expected values.", file=sys.stderr)
        print("To populate the fixture:", file=sys.stderr)
        print("1. Run the baseline_full suite: python scripts/run_suite.py --suite experiments/suites/baseline_full.yaml --seed 42 --n_per 100", file=sys.stderr)
        print("2. Extract avg_tricks values from the generated rollup.json summary array", file=sys.stderr)
        print("3. Update data/fixtures/baseline_full_expected.json with avg_tricks values for each config", file=sys.stderr)
        sys.exit(1)

    default_tolerance = fixture.get("default_tolerance", 0.01)
    if not isinstance(default_tolerance, (int, float)):
        print("ERROR: fixture 'default_tolerance' is not a number", file=sys.stderr)
        sys.exit(1)

    return configs, default_tolerance


def check_run_health(summary: List[Dict[str, Any]]) -> None:
    """Check that all runs completed successfully."""
    failed_configs = []
    for entry in summary:
        if entry.get("status") != "ok":
            failed_configs.append(entry["config"])

    if failed_configs:
        sorted_failed = sorted(failed_configs)
        print("ERROR: Suite has failed configs:", file=sys.stderr)
        for config in sorted_failed:
            print(f"  - {config}", file=sys.stderr)
        print("All configs must have status='ok' for drift comparison", file=sys.stderr)
        sys.exit(1)


def compare_metrics(
    summary: List[Dict[str, Any]],
    expected_configs: Dict[str, Any],
    default_tolerance: float
) -> List[str]:
    """Compare actual vs expected metrics, return list of drift messages."""
    drift_messages = []

    # Build actual results dict
    actual_results = {}
    for entry in summary:
        if entry.get("status") == "ok":
            config = entry["config"]
            avg_tricks = entry.get("avg_tricks")
            if avg_tricks is not None:
                actual_results[config] = avg_tricks

    # Check for unexpected configs
    actual_configs = set(actual_results.keys())
    expected_config_names = set(expected_configs.keys())

    unexpected = actual_configs - expected_config_names
    if unexpected:
        for config in sorted(unexpected):
            drift_messages.append(f"UNEXPECTED_CONFIG: {config}")

    # Check for missing expected configs
    missing = expected_config_names - actual_configs
    if missing:
        for config in sorted(missing):
            drift_messages.append(f"MISSING_CONFIG: {config}")

    # Compare metrics for configs present in both
    common_configs = actual_configs & expected_config_names
    for config in sorted(common_configs):
        actual_value = actual_results[config]
        expected_data = expected_configs[config]

        if not isinstance(expected_data, dict):
            drift_messages.append(f"INVALID_FIXTURE_CONFIG: {config} - expected object, got {type(expected_data)}")
            continue

        expected_value = expected_data.get("avg_tricks")
        if expected_value is None:
            drift_messages.append(f"INVALID_FIXTURE_CONFIG: {config} - missing avg_tricks")
            continue

        # Use config-specific tolerance or default
        tolerance = expected_data.get("tolerance", default_tolerance)
        if not isinstance(tolerance, (int, float)):
            drift_messages.append(f"INVALID_FIXTURE_CONFIG: {config} - invalid tolerance: {tolerance}")
            continue

        diff = abs(actual_value - expected_value)
        if diff > tolerance:
            drift_messages.append(f"DRIFT: {config} avg_tricks: {actual_value:.6f} vs {expected_value:.6f} (diff: {diff:.6f}, tolerance: {tolerance:.6f})")

    return drift_messages


def main():
    """Main entry point."""
    args = parse_args()

    # Load and validate inputs
    rollup = load_json_file(args.rollup)
    fixture = load_json_file(args.fixture)

    summary = validate_rollup_structure(rollup)
    expected_configs, default_tolerance = validate_fixture_structure(fixture)

    # Check run health - all configs must succeed
    check_run_health(summary)

    # Compare metrics
    drift_messages = compare_metrics(summary, expected_configs, default_tolerance)

    # Report results
    if drift_messages:
        print("Drift detected:")
        for msg in sorted(drift_messages):
            print(f"  {msg}")
        sys.exit(1)
    else:
        print("No drift detected - all metrics within tolerance")
        sys.exit(0)


if __name__ == "__main__":
    main()