#!/usr/bin/env python
"""CLI wrapper for advance check generation.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.advance_check``.

Usage:
    uv run python scripts/internal/generate_advance_check.py \
        --hypotheses plans/arc_d_v2/r0/hypotheses.json \
        --tables-dir docs/04_reports/arc_d_v2/r0/canonical/tables \
        --output plans/arc_d_v2/r0/advance_check.json \
        --mode full --rung r0
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bid_euchre.arc_d_v2.advance_check import (
    generate_advance_check,
)
from bid_euchre.arc_d_v2.orchestration import load_roster


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate advance check for Arc D v2 rung"
    )
    parser.add_argument(
        "--hypotheses",
        required=True,
        type=Path,
        help="Path to hypotheses.json",
    )
    parser.add_argument(
        "--tables-dir",
        required=True,
        type=Path,
        help="Path to tables/ directory",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output path for advance_check.json",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["smoke", "quick", "full"],
        help="Execution mode",
    )
    parser.add_argument(
        "--rung",
        required=True,
        help="Rung ID (e.g., r0)",
    )

    args = parser.parse_args(argv)

    if not args.hypotheses.exists():
        print(f"ERROR: Hypotheses file not found: {args.hypotheses}", file=sys.stderr)
        return 1

    # Load roster to determine active models for hypothesis SKIP logic (LA-4)
    active_models: set[str] | None = None
    try:
        roster = load_roster(args.rung, mode=args.mode)
        active_models = {m.name for m in roster.all_active_models()}
    except Exception as exc:
        print(
            f"WARNING: Could not load roster for {args.rung}/{args.mode}: {exc}",
            file=sys.stderr,
        )
        # Fall through with active_models=None (no SKIP logic, backward compat)

    result = generate_advance_check(
        args.hypotheses,
        args.tables_dir,
        args.mode,
        args.rung,
        active_models=active_models,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Advance check written to {args.output}")
    print(f"Decision: {result['advance_decision']} — {result['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
