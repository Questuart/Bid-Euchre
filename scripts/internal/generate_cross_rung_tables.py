#!/usr/bin/env python
"""CLI wrapper for cross-rung progression table generation.

Loads comparator CIs JSON from each rung's artifacts directory and produces
a cross_rung_progression.csv showing per-model metrics across rungs for
trend analysis.

Canonical domain logic lives in ``bid_euchre.arc_d_v2.tables``.

Usage:
    uv run python scripts/internal/generate_cross_rung_tables.py \
        --artifacts-base data/artifacts/arc_d_v2 \
        --rungs r0,r1,r2,r3 \
        --mode quick \
        --seed 42 \
        --output-dir docs/04_reports/arc_d_v2/cross_rung/tables
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from bid_euchre.arc_d_v2.tables import generate_cross_rung_progression

logger = logging.getLogger(__name__)


def _load_comparator_cis(
    artifacts_base: Path,
    rung: str,
    mode: str | None,
    seed: int | None,
) -> dict | None:
    """Load a comparator CIs JSON for a single rung.

    Resolution order (matching ``_load_json_glob`` in tables.py):
    1. ``{rung}/comparator_cis_{mode}_{seed}.json`` — deterministic
    2. ``{rung}/comparator_cis.json`` — legacy bare name
    3. ``{rung}/comparator_cis_*.json`` — newest by mtime (last resort)
    """
    rung_dir = artifacts_base / rung

    # Deterministic path when mode and seed are known
    if mode and seed is not None:
        deterministic = rung_dir / f"comparator_cis_{mode}_{seed}.json"
        if deterministic.exists():
            logger.debug("Loading deterministic: %s", deterministic)
            return json.loads(deterministic.read_text())

    # Legacy bare name
    bare = rung_dir / "comparator_cis.json"
    if bare.exists():
        logger.debug("Loading bare: %s", bare)
        return json.loads(bare.read_text())

    # Glob fallback
    candidates = sorted(
        rung_dir.glob("comparator_cis_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    if candidates:
        chosen = candidates[-1]
        logger.warning(
            "Glob fallback for %s: chose %s from %d candidates",
            rung,
            chosen.name,
            len(candidates),
        )
        return json.loads(chosen.read_text())

    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate cross-rung progression table from comparator CIs artifacts."
        ),
    )
    parser.add_argument(
        "--artifacts-base",
        required=True,
        type=Path,
        help=(
            "Base directory containing per-rung artifact subdirectories "
            "(e.g. data/artifacts/arc_d_v2)"
        ),
    )
    parser.add_argument(
        "--rungs",
        required=True,
        help="Comma-separated rung labels (e.g. r0,r1,r2,r3)",
    )
    parser.add_argument(
        "--mode",
        choices=["smoke", "quick", "full"],
        default=None,
        help="Execution mode for deterministic artifact selection",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic artifact selection",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write cross_rung_progression.csv",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    rungs = [r.strip() for r in args.rungs.split(",") if r.strip()]
    if not rungs:
        logger.error("No rungs specified")
        return 1

    # Load comparator CIs for each rung
    rung_comparator_cis: dict[str, dict] = {}
    for rung in rungs:
        cis = _load_comparator_cis(args.artifacts_base, rung, args.mode, args.seed)
        if cis is None:
            logger.warning(
                "No comparator CIs found for rung %s in %s — skipping",
                rung,
                args.artifacts_base / rung,
            )
            continue
        rung_comparator_cis[rung] = cis

    if not rung_comparator_cis:
        logger.error(
            "No comparator CIs found for any rung. Check --artifacts-base path."
        )
        return 1

    logger.info(
        "Loaded comparator CIs for %d rungs: %s",
        len(rung_comparator_cis),
        ", ".join(sorted(rung_comparator_cis.keys())),
    )

    # Generate the cross-rung progression table
    df = generate_cross_rung_progression(rung_comparator_cis)

    # Write output
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "cross_rung_progression.csv"
    df.to_csv(output_path, index=False)
    logger.info("Wrote %s (%d rows)", output_path, len(df))

    return 0


if __name__ == "__main__":
    sys.exit(main())
