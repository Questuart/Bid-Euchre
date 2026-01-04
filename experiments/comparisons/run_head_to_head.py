#!/usr/bin/env python3
"""Deprecated: Head-to-Head Matchup Runner.

This script is kept for backwards compatibility.

Use instead:
    PYTHONPATH=src python experiments/run_experiment.py \
        --config experiments/configs/head_to_head_vs_random.yaml \
        --mode head_to_head_matrix

This wrapper forwards args to the unified runner.
"""

import argparse
import os
import subprocess
import sys


def parse_args():
    parser = argparse.ArgumentParser(description="(Deprecated) run head-to-head matchups")
    parser.add_argument("--config", "-c", type=str, required=True)
    parser.add_argument("--n_per", "-n", type=int)
    parser.add_argument("--seed", "-s", type=int)
    parser.add_argument("--run-dir", type=str, default="data/runs")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print("⚠️  DEPRECATED: experiments/run_head_to_head.py")
    print("    Use experiments/run_experiment.py --mode head_to_head_matrix instead.\n")

    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(__file__), "run_experiment.py"),
        "--config",
        args.config,
        "--mode",
        "head_to_head_matrix",
        "--run-dir",
        args.run_dir,
    ]

    if args.n_per is not None:
        cmd += ["--n_per", str(args.n_per)]
    if args.seed is not None:
        cmd += ["--seed", str(args.seed)]
    if args.dry_run:
        cmd += ["--dry-run"]

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
