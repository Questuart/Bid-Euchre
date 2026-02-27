#!/usr/bin/env python
"""
Auction Comparator: run all bidders in auction mode and compare metrics.

Orchestrates the experiment runner per bidder, then applies gate checks
and generates a comparison report.

Usage:
    uv run python scripts/run_auction_comparator.py \
        --config experiments/configs/auction_comparator.yaml \
        --seed 42 \
        --olsa-artifact /tmp/olsa_artifacts/olsa_v1.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Map known bidder classes to short policy names.
# Fallback: lowercase the class name for unknown classes.
_CLASS_TO_NAME = {
    "OLSaBidder": "olsa",
    "HybridOLSaBidder": "hybrid_olsa",
}


def _detect_new_run_dir(runs_base, before_snapshot):
    """Detect the new run directory by diffing data/runs/ before/after.

    Returns the new directory path, or None if no new directory was created.
    """
    runs_path = Path(runs_base)
    if not runs_path.is_dir():
        return None
    after_snapshot = {p.name for p in runs_path.iterdir() if p.is_dir()}
    new_dirs = after_snapshot - before_snapshot
    if len(new_dirs) == 1:
        return str(runs_path / new_dirs.pop())
    return None


def _snapshot_runs_dir(runs_base="data/runs"):
    """Snapshot current run directory names for before/after diffing."""
    runs_path = Path(runs_base)
    if not runs_path.is_dir():
        return set()
    return {p.name for p in runs_path.iterdir() if p.is_dir()}


def run_experiment(config_path, seed, runs_base="data/runs", extra_args=None):
    """Run a single experiment via the canonical runner.

    Returns the detected run directory path, or None on failure.
    The runner auto-generates run IDs with timestamps, so we detect the
    new directory by snapshotting data/runs/ before/after.
    """
    before = _snapshot_runs_dir(runs_base)

    cmd = [
        sys.executable,
        "experiments/run_experiment.py",
        "--config",
        config_path,
        "--seed",
        str(seed),
    ]
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED: experiment with config {config_path}")
        print(result.stderr)
        return None

    # Primary: parse stdout for "Run directory: <path>"
    for line in result.stdout.splitlines():
        if "Run directory:" in line:
            # Line format: "📁 Run directory: data/runs/<run_id>"
            run_dir = line.split("Run directory:")[-1].strip()
            if run_dir and Path(run_dir).is_dir():
                return run_dir

    # Fallback: diff data/runs/ before/after
    detected = _detect_new_run_dir(runs_base, before)
    if detected:
        return detected

    print("WARNING: Could not detect run directory from stdout or filesystem diff")
    return None


def generate_evaluation(run_dir):
    """Generate evaluator report for a run."""
    cmd = [
        sys.executable,
        "scripts/generate_report.py",
        "--run-dir",
        run_dir,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def load_evaluation(run_dir):
    """Load the evaluator JSON output."""
    eval_path = Path(run_dir) / "reports" / "bidding_strategy" / "evaluation.json"
    if not eval_path.exists():
        return None
    with open(eval_path) as f:
        return json.load(f)


def gate_check(metrics_by_bidder):
    """
    Apply gate checks:
    1. No bidder has bid_rate == 0 (degenerate)
    2. Report overall coverage
    """
    failures = []

    for name, metrics in metrics_by_bidder.items():
        bid_rate = metrics.get("bid_rate", 0)
        if bid_rate == 0:
            failures.append(f"GATE FAIL: {name} has bid_rate=0 (never bids)")

    return failures


def format_json(metrics_by_bidder, gate_failures, seed, n_per, single_seat=False):
    """Generate JSON comparison output with arc_d_comparator_v1 schema."""
    bidders = {}
    for name, m in metrics_by_bidder.items():
        bidders[name] = {
            "net_eppd": m.get("net_expected_points_per_deal"),
            "eppd": m.get("expected_points_per_deal", 0),
            "bid_rate": m.get("bid_rate", 0),
            "make_rate": m.get("make_rate", 0),
            "cvar_5": m.get("cvar_5"),
            "net_cvar_5": m.get("net_cvar_5"),
        }
    result = {
        "schema": "arc_d_comparator_v1",
        "seed": seed,
        "n_per": n_per,
        "gate_status": "FAIL" if gate_failures else "PASS",
        "bidders": bidders,
    }
    if single_seat:
        result["mode"] = "single_seat"
    return result


def format_report(metrics_by_bidder, gate_failures, seed):
    """Generate markdown comparison report."""
    lines = [
        "# Auction Comparator Gate Report",
        "",
        f"- **Seed:** {seed}",
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}",
        f"- **Bidders:** {len(metrics_by_bidder)}",
        "- **Metric source:** evaluation.json (expected_points from evaluator)",
        "",
    ]

    # Gate results
    if gate_failures:
        lines.extend(
            [
                "## Gate Status: FAIL",
                "",
            ]
        )
        for f in gate_failures:
            lines.append(f"- {f}")
        lines.append("")
    else:
        lines.extend(
            [
                "## Gate Status: PASS",
                "",
            ]
        )

    # Comparison table
    lines.extend(
        [
            "## Bidder Comparison",
            "",
            "| Bidder | Expected Points | Make Rate | Bid Rate | CVaR-5% | N (bid hands) |",
            "|--------|----------------|-----------|----------|---------|---------------|",
        ]
    )

    # Sort by expected_points descending
    sorted_bidders = sorted(
        metrics_by_bidder.items(),
        key=lambda x: x[1].get("expected_points", 0),
        reverse=True,
    )

    for name, m in sorted_bidders:
        ep = m.get("expected_points", 0)
        mr = m.get("make_rate", 0)
        br = m.get("bid_rate", 0)
        cvar = m.get("cvar_5")
        n_bids = m.get("hands_with_bids", 0)
        cvar_str = f"{cvar:.2f}" if cvar is not None else "N/A"
        lines.append(
            f"| {name} | {ep:.4f} | {mr:.4f} | {br:.4f} | {cvar_str} | {n_bids:,} |"
        )

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Auction Comparator")
    parser.add_argument("--config", required=True, help="YAML config path")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--olsa-artifact", default=None, help="Path to OLSa artifact")
    parser.add_argument(
        "--bidder-class",
        default="OLSaBidder",
        help="Bidder class for --olsa-artifact (default: OLSaBidder)",
    )
    parser.add_argument(
        "--bidder-name",
        default=None,
        help="Policy name for the artifact bidder in output (default: derived from class)",
    )
    parser.add_argument(
        "--single-seat",
        action="store_true",
        help="Run single-seat mode: each bidder evaluated one seat at a time",
    )
    parser.add_argument(
        "--n-per",
        type=int,
        default=None,
        help="Override n_per from config YAML",
    )
    parser.add_argument(
        "--output-format",
        default="markdown",
        choices=["markdown", "json"],
        help="Output format (default: markdown)",
    )
    parser.add_argument("--output", default=None, help="Output report path")
    parser.add_argument(
        "--skip-run", action="store_true", help="Skip experiment run, just analyze"
    )
    args = parser.parse_args()

    # Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)

    policies = config.get("bidding_policies", [])
    n_per = config.get("parameters", {}).get("n_per", 10000)

    # Add artifact bidder if provided
    if args.olsa_artifact:
        if not os.path.exists(args.olsa_artifact):
            print(f"ERROR: OLSa artifact not found: {args.olsa_artifact}")
            sys.exit(1)
        bidder_name = args.bidder_name or _CLASS_TO_NAME.get(
            args.bidder_class, args.bidder_class.lower()
        )
        policies.append(
            {
                "name": bidder_name,
                "class_name": args.bidder_class,
                "params": {"artifact_path": args.olsa_artifact},
            }
        )

    experiment_name = config.get("experiment_name", "auction_comparator")

    # Track run directories per policy (populated during run or from --skip-run lookup)
    run_dirs_by_policy = {}

    n_per_effective = args.n_per or n_per

    if not args.skip_run:
        if args.single_seat:
            # Single-seat mode: 4 sub-experiments per bidder
            print(
                f"Running single-seat comparator with {len(policies)} bidders, "
                f"n_per={n_per_effective}..."
            )
            base_per_seat = n_per_effective // 4
            remainder = n_per_effective % 4

            for policy in policies:
                policy_name = policy["name"]

                for seat in range(4):
                    seat_n = base_per_seat + (1 if seat < remainder else 0)

                    # Build seat_bidding_policies: target at this seat, always_pass elsewhere
                    seat_bp = ["always_pass"] * 4
                    seat_bp[seat] = policy_name

                    per_seat_config = {
                        "experiment_name": f"{experiment_name}_{policy_name}_seat{seat}",
                        "bidding_policies": [
                            policy,
                            {"name": "always_pass", "class_name": "AlwaysPassBidder"},
                        ],
                        "seat_bidding_policies": seat_bp,
                        "scenarios": config.get("scenarios", [{"contract_type": None}]),
                        "parameters": {
                            **config.get("parameters", {}),
                            "n_per": seat_n,
                        },
                    }

                    config_path = (
                        f"/tmp/auction_comparator_{policy_name}_seat{seat}.yaml"
                    )
                    with open(config_path, "w") as f:
                        yaml.dump(per_seat_config, f)

                    print(f"  Running {policy_name} seat {seat} ({seat_n} deals)...")
                    run_dir = run_experiment(config_path, args.seed)
                    if run_dir is None:
                        print(f"  FAILED: {policy_name} seat {seat}")
                        continue

                    # Track with seat-specific key
                    run_dirs_by_policy[f"{policy_name}_seat{seat}"] = run_dir
                    generate_evaluation(run_dir)
        else:
            # Original 4-way self-play mode
            print(
                f"Running auction comparator with {len(policies)} bidders, "
                f"n_per={n_per_effective}..."
            )
            for policy in policies:
                policy_name = policy["name"]

                # Create a per-policy config
                per_policy_config = {
                    "experiment_name": f"{experiment_name}_{policy_name}",
                    "bidding_policies": [policy],
                    "scenarios": config.get("scenarios", [{"contract_type": None}]),
                    "parameters": {
                        **config.get("parameters", {}),
                        "n_per": n_per_effective,
                    },
                }

                config_path = f"/tmp/auction_comparator_{policy_name}.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(per_policy_config, f)

                print(f"  Running {policy_name}...")
                run_dir = run_experiment(config_path, args.seed)
                if run_dir is None:
                    print(f"  FAILED: {policy_name}")
                    continue

                run_dirs_by_policy[policy_name] = run_dir
                generate_evaluation(run_dir)
    else:
        # In --skip-run mode, scan data/runs/ for matching directories
        runs_path = Path("data/runs")
        if runs_path.is_dir():
            if args.single_seat:
                # Single-seat skip-run: discover per-seat directories
                for policy in policies:
                    policy_name = policy["name"]
                    for seat in range(4):
                        prefix = f"{experiment_name}_{policy_name}_seat{seat}_"
                        matches = sorted(
                            (
                                p
                                for p in runs_path.iterdir()
                                if p.is_dir() and p.name.startswith(prefix)
                            ),
                            key=lambda p: p.name,
                            reverse=True,
                        )
                        if matches:
                            run_dirs_by_policy[f"{policy_name}_seat{seat}"] = str(
                                matches[0]
                            )
            else:
                for policy in policies:
                    policy_name = policy["name"]
                    prefix = f"{experiment_name}_{policy_name}_"
                    matches = sorted(
                        (
                            p
                            for p in runs_path.iterdir()
                            if p.is_dir() and p.name.startswith(prefix)
                        ),
                        key=lambda p: p.name,
                        reverse=True,
                    )
                    if matches:
                        run_dirs_by_policy[policy_name] = str(matches[0])

    # Collect metrics (require evaluation.json — no silent fallback)
    metrics_by_bidder = {}
    missing_evaluations = []

    if args.single_seat:
        # Single-seat mode: merge evaluation.json across 4 seats per bidder
        for policy in policies:
            policy_name = policy["name"]
            merged_deals = 0
            merged_bid_hands = 0
            merged_bidder_pts_sum = 0.0
            merged_net_pts_sum = 0.0
            merged_make_count = 0  # bids where bidder earned positive points
            missing_seat = False

            for seat in range(4):
                key = f"{policy_name}_seat{seat}"
                run_dir = run_dirs_by_policy.get(key)
                if not run_dir:
                    missing_seat = True
                    continue
                evaluation = load_evaluation(run_dir)
                if evaluation and evaluation.get("strategies"):
                    strat = evaluation["strategies"][0]
                    dt = strat.get("deals_total", 0)
                    hwb = strat.get("hands_with_bids", 0)
                    merged_deals += dt
                    merged_bid_hands += hwb
                    ep = strat.get("expected_points_per_deal", 0)
                    nep = strat.get("net_expected_points_per_deal", 0)
                    merged_bidder_pts_sum += ep * dt
                    merged_net_pts_sum += nep * dt
                    # make_rate * hands_with_bids = number of made bids
                    mr = strat.get("make_rate", 0)
                    merged_make_count += int(round(mr * hwb))
                else:
                    missing_seat = True

            if missing_seat or merged_deals == 0:
                missing_evaluations.append(policy_name)
            else:
                metrics_by_bidder[policy_name] = {
                    "expected_points": merged_bidder_pts_sum / merged_deals,
                    "expected_points_per_deal": merged_bidder_pts_sum / merged_deals,
                    "net_expected_points_per_deal": merged_net_pts_sum / merged_deals,
                    "make_rate": merged_make_count / merged_bid_hands
                    if merged_bid_hands > 0
                    else 0.0,
                    "bid_rate": merged_bid_hands / merged_deals,
                    # CVaR requires raw per-hand distributions; point estimates
                    # from evaluation.json can't be merged. The CI extractor
                    # computes these from JSONL logs directly.
                    "cvar_5": None,
                    "net_cvar_5": None,
                    "hands_with_bids": merged_bid_hands,
                    "deals_total": merged_deals,
                }
    else:
        # Original mode: one run per bidder
        for policy in policies:
            policy_name = policy["name"]
            run_dir = run_dirs_by_policy.get(policy_name)

            if not run_dir:
                missing_evaluations.append(policy_name)
                continue

            evaluation = load_evaluation(run_dir)
            if evaluation and evaluation.get("strategies"):
                strat = evaluation["strategies"][0]
                metrics_by_bidder[policy_name] = {
                    "expected_points": strat.get("expected_points", 0),
                    "expected_points_per_deal": strat.get(
                        "expected_points_per_deal", 0
                    ),
                    "net_expected_points_per_deal": strat.get(
                        "net_expected_points_per_deal"
                    ),
                    "make_rate": strat.get("make_rate", 0),
                    "bid_rate": strat.get("bid_rate", 0),
                    "cvar_5": strat.get("cvar_5"),
                    "net_cvar_5": strat.get("net_cvar_5"),
                    "hands_with_bids": strat.get("hands_with_bids", 0),
                    "deals_total": strat.get("deals_total", 0),
                }
            else:
                missing_evaluations.append(policy_name)

    if missing_evaluations:
        print("ERROR: Missing evaluation data for the following bidders:")
        for name in missing_evaluations:
            run_dir = run_dirs_by_policy.get(name, "<no run directory found>")
            print(f"  - {name}  (run_dir: {run_dir})")
        print("\nTo generate evaluation data, re-run without --skip-run:")
        print(
            f"  uv run python scripts/run_auction_comparator.py --config {args.config} --seed {args.seed}"
        )
        sys.exit(1)

    if not metrics_by_bidder:
        print("ERROR: No metrics collected. Check experiment runs.")
        sys.exit(1)

    # Gate check
    gate_failures = gate_check(metrics_by_bidder)

    # Generate report in requested format
    if args.output_format == "json":
        output_data = format_json(
            metrics_by_bidder,
            gate_failures,
            args.seed,
            n_per_effective,
            single_seat=args.single_seat,
        )
        output_str = json.dumps(output_data, indent=2)
    else:
        output_str = format_report(metrics_by_bidder, gate_failures, args.seed)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(output_str)
        # File path confirmation always to stderr in JSON mode
        if args.output_format == "json":
            print(f"Report written to {args.output}", file=sys.stderr)
        else:
            print(f"\nReport written to {args.output}")
    else:
        print(output_str)

    # Gate status: stderr in JSON mode, stdout in markdown mode
    if gate_failures:
        gate_msg = "\nGATE STATUS: FAIL\n" + "\n".join(f"  {f}" for f in gate_failures)
        if args.output_format == "json":
            print(gate_msg, file=sys.stderr)
        else:
            print(gate_msg)
        sys.exit(1)
    else:
        if args.output_format != "json":
            print("\nGATE STATUS: PASS")


if __name__ == "__main__":
    main()
