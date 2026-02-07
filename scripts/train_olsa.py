#!/usr/bin/env python3
"""Train OLSa models from canonical bidless run data.

Thin CLI wrapper around bid_euchre.models.train_olsa.

Usage:
    PYTHONPATH=src python scripts/train_olsa.py \
        --run-dir data/runs/canonical_bidless_dataset_glutton_42_20260204_222713 \
        --seed 42 --output /tmp/olsa_artifacts/
"""

from __future__ import annotations

import argparse
import logging

from bid_euchre.models.freeze import freeze_artifact
from bid_euchre.models.train_olsa import save_artifacts, train_olsa


def main() -> None:
    parser = argparse.ArgumentParser(description="Train OLSa models")
    parser.add_argument(
        "--run-dir", required=True, help="Canonical bidless run directory"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output", required=True, help="Output directory for artifacts"
    )
    parser.add_argument(
        "--split-type",
        choices=["two_way", "three_way"],
        default="two_way",
        help="Split type: two_way for exploration (default), three_way required for promotion-track batches",
    )
    parser.add_argument(
        "--freeze",
        action="store_true",
        default=False,
        help="Freeze artifact after training (sets frozen_at + artifact_sha256)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    artifact, metrics = train_olsa(
        args.run_dir,
        args.seed,
        split_manifest_dir=args.output,
        split_type=args.split_type,
    )
    artifact_path = save_artifacts(artifact, metrics, args.output)
    if args.freeze:
        freeze_artifact(artifact_path)
        print(f"\nOLSa artifact (frozen): {artifact_path}")
    else:
        print(f"\nOLSa artifact: {artifact_path}")


if __name__ == "__main__":
    main()
