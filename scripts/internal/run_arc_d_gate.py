#!/usr/bin/env python3
"""Arc D Promotion Gate Runner.

CLI wrapper for the promotion_gate() function. Evaluates a rung bundle
and writes a promotion decision JSON file.

Usage:
    uv run python scripts/internal/run_arc_d_gate.py \\
        --bundle data/artifacts/arc_d/r1/rung_bundle_r1.json \\
        [--base-dir .]

Exit codes:
    0 = PROMOTED or ADVANCED
    1 = HALT
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bid_euchre.validation.arc_d_gate import promotion_gate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main():
    parser = argparse.ArgumentParser(
        description="Arc D Promotion Gate Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--bundle",
        type=str,
        required=True,
        help="Path to rung bundle JSON file",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Base directory for resolving relative paths (default: .)",
    )
    parser.add_argument(
        "--thresholds",
        type=str,
        default=None,
        help="Path to gate thresholds JSON (auto-discovered if not provided)",
    )
    args = parser.parse_args()

    bundle_path = args.bundle
    base_dir = args.base_dir

    # Extract rung_id from bundle
    try:
        with open(bundle_path) as f:
            bundle_data = json.load(f)
        rung_id = bundle_data.get("rung_id", "unknown")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading bundle: {e}", file=sys.stderr)
        sys.exit(1)

    # Run the gate
    decision, reasons = promotion_gate(
        bundle_path, rung_id, base_dir, thresholds_path=args.thresholds
    )

    # Print result
    print(f"Decision: {decision}")
    for reason in reasons:
        print(f"  - {reason}")

    # Write promotion decision JSON (schema_version 3, matches R0 writer)
    decision_record = {
        "schema_version": 3,
        "rung_id": rung_id,
        "arc": "arc_d",
        "decision": decision,
        "reasons": reasons,
        "bundle_path": bundle_path,
        "timestamp": _utc_now_iso(),
    }

    decision_path = Path(bundle_path).parent / f"promotion_decision_{rung_id}.json"
    with open(decision_path, "w") as f:
        json.dump(decision_record, f, indent=2)
    print(f"\nDecision record written to: {decision_path}")

    # Exit code
    sys.exit(1 if decision == "HALT" else 0)


if __name__ == "__main__":
    main()
