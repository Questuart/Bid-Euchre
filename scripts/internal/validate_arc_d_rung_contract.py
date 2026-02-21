#!/usr/bin/env python3
"""Validate an Arc D rung bundle JSON file.

Checks schema conformance, file existence, and artifact hash integrity.

Usage:
    uv run python scripts/internal/validate_arc_d_rung_contract.py \\
        --bundle data/artifacts/arc_d/r1/rung_bundle_r1.json \\
        [--check-files] [--check-hashes] [--base-dir .]

Exit codes:
    0 = valid
    1 = validation errors found
"""

import argparse
import sys

from bid_euchre.validation.arc_d_bundle import (
    load_and_validate_bundle,
    validate_bundle_hashes,
)


def main():
    parser = argparse.ArgumentParser(
        description="Validate Arc D rung bundle",
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
        "--check-files",
        action="store_true",
        help="Also check that all referenced files exist on disk",
    )
    parser.add_argument(
        "--check-hashes",
        action="store_true",
        help="Also verify artifact SHA-256 hashes match file content",
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Base directory for resolving relative paths (default: .)",
    )
    args = parser.parse_args()

    bundle, valid, errors = load_and_validate_bundle(
        args.bundle,
        check_files=args.check_files,
        base_dir=args.base_dir,
    )

    if args.check_hashes and valid:
        hash_valid, hash_errors = validate_bundle_hashes(bundle, args.base_dir)
        if not hash_valid:
            valid = False
            errors.extend(hash_errors)

    if valid:
        rung_id = bundle.get("rung_id", "unknown")
        print(f"Bundle valid: rung_id={rung_id}, arc={bundle.get('arc', 'unknown')}")
        sys.exit(0)
    else:
        print(f"Bundle validation FAILED ({len(errors)} errors):")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
