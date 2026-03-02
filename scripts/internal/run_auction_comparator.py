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


def _write_batch_manifest(
    runs_dir, experiment_name, seed, n_per, policies, run_dirs_by_policy
):
    """Write a batch manifest after a complete single-seat battery run.

    The manifest is ONLY written when the batch is complete: all
    len(policies) × 4 expected members must exist with valid evaluation.json.

    Returns (manifest_path, batch_id) on success, (None, None) on failure.
    """
    expected_keys = []
    for policy in policies:
        for seat in range(4):
            expected_keys.append(f"{policy['name']}_seat{seat}")

    # Completeness gate
    missing = [k for k in expected_keys if k not in run_dirs_by_policy]
    if missing:
        print(
            f"ERROR: Incomplete batch — missing {len(missing)} members: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return None, None

    # Validate evaluation.json exists for each member
    members = {}
    for key in expected_keys:
        run_dir = run_dirs_by_policy[key]
        eval_path = Path(run_dir) / "reports" / "bidding_strategy" / "evaluation.json"
        if not eval_path.exists():
            print(
                f"ERROR: Missing evaluation.json in {run_dir}",
                file=sys.stderr,
            )
            return None, None
        members[key] = Path(run_dir).name

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    batch_id = f"{experiment_name}_{seed}_{timestamp}"
    manifest = {
        "schema": "batch_manifest_v1",
        "batch_id": batch_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_name": experiment_name,
        "seed": seed,
        "n_per": n_per,
        "mode": "single_seat",
        "expected_policies": [p["name"] for p in policies],
        "expected_seats": 4,
        "members": members,
    }

    runs_path = Path(runs_dir)
    manifest_path = runs_path / f"batch_manifest_{batch_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return str(manifest_path), batch_id


def _load_batch_manifest(manifest_path, runs_dir):
    """Load and validate a batch manifest, returning resolved run dirs.

    Returns dict: {member_key: resolved_run_dir_path}
    Calls sys.exit(1) on any validation failure.
    """
    manifest_p = Path(manifest_path)
    if not manifest_p.exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_p.read_text())
    if manifest.get("schema") != "batch_manifest_v1":
        print(
            f"ERROR: Unknown manifest schema: {manifest.get('schema')}",
            file=sys.stderr,
        )
        sys.exit(1)

    runs_path = Path(runs_dir)
    resolved = {}
    missing = []
    for key, dirname in manifest["members"].items():
        full_path = runs_path / dirname
        if not full_path.is_dir():
            missing.append(f"  {key}: {full_path}")
        else:
            resolved[key] = str(full_path)

    if missing:
        print(
            "ERROR: Manifest references missing run directories:\n"
            + "\n".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)

    return resolved


def _merge_single_seat_evaluations(run_dirs_by_policy, policies, load_fn=None):
    """Merge evaluation.json across 4 seats per bidder.

    Returns (metrics_by_bidder, missing_evaluations).
    The load_fn parameter enables test injection; defaults to load_evaluation.
    """
    if load_fn is None:
        load_fn = load_evaluation

    metrics_by_bidder = {}
    missing_evaluations = []

    for policy in policies:
        policy_name = policy["name"]
        merged_deals = 0
        merged_bid_hands = 0
        merged_bidder_pts_sum = 0.0
        merged_net_pts_sum = 0.0
        merged_make_count = 0
        missing_seat = False

        for seat in range(4):
            key = f"{policy_name}_seat{seat}"
            run_dir = run_dirs_by_policy.get(key)
            if not run_dir:
                missing_seat = True
                continue
            evaluation = load_fn(run_dir)
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
                "cvar_5": None,
                "net_cvar_5": None,
                "hands_with_bids": merged_bid_hands,
                "deals_total": merged_deals,
            }

    return metrics_by_bidder, missing_evaluations


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


def format_json(
    metrics_by_bidder, gate_failures, seed, n_per, single_seat=False, batch_id=None
):
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
    if batch_id is not None:
        result["batch_id"] = batch_id
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
    parser.add_argument(
        "--manifest",
        default=None,
        help="Explicit batch manifest path for --skip-run discovery",
    )
    parser.add_argument(
        "--allow-legacy-seat-discovery",
        action="store_true",
        help="Allow heuristic 'latest per seat' discovery when no manifest exists (unsafe)",
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
    batch_id = None  # Set when a manifest is written or loaded

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
                        "strategies": config.get("strategies", []),
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

                    # Validate play strategy passed through to generated config
                    with open(config_path) as _f:
                        _written = yaml.safe_load(_f)
                    if not _written.get("strategies"):
                        raise ValueError(
                            f"Generated config {config_path} is missing 'strategies' section. "
                            f"Ensure the source config includes a strategies list "
                            f"(e.g., strategies: [{{name: glutton, class_name: GluttonStrategy}}])."
                        )
                    if not _written.get("parameters", {}).get("play_strategy"):
                        raise ValueError(
                            f"Generated config {config_path} is missing 'parameters.play_strategy'. "
                            f"Ensure the source config includes play_strategy in parameters."
                        )

                    print(f"  Running {policy_name} seat {seat} ({seat_n} deals)...")
                    run_dir = run_experiment(config_path, args.seed)
                    if run_dir is None:
                        print(f"  FAILED: {policy_name} seat {seat}")
                        continue

                    # Track with seat-specific key
                    run_dirs_by_policy[f"{policy_name}_seat{seat}"] = run_dir
                    generate_evaluation(run_dir)

            # Write batch manifest (only if all seats completed)
            manifest_path, batch_id = _write_batch_manifest(
                "data/runs",
                experiment_name,
                args.seed,
                n_per_effective,
                policies,
                run_dirs_by_policy,
            )
            if manifest_path:
                print(f"  Batch manifest: {manifest_path}")
            else:
                print(
                    "  WARNING: Incomplete batch — no manifest written",
                    file=sys.stderr,
                )
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
                    "strategies": config.get("strategies", []),
                    "scenarios": config.get("scenarios", [{"contract_type": None}]),
                    "parameters": {
                        **config.get("parameters", {}),
                        "n_per": n_per_effective,
                    },
                }

                config_path = f"/tmp/auction_comparator_{policy_name}.yaml"
                with open(config_path, "w") as f:
                    yaml.dump(per_policy_config, f)

                # Validate play strategy passed through to generated config
                with open(config_path) as _f:
                    _written = yaml.safe_load(_f)
                if not _written.get("strategies"):
                    raise ValueError(
                        f"Generated config {config_path} is missing 'strategies' section. "
                        f"Ensure the source config includes a strategies list "
                        f"(e.g., strategies: [{{name: glutton, class_name: GluttonStrategy}}])."
                    )
                if not _written.get("parameters", {}).get("play_strategy"):
                    raise ValueError(
                        f"Generated config {config_path} is missing 'parameters.play_strategy'. "
                        f"Ensure the source config includes play_strategy in parameters."
                    )

                print(f"  Running {policy_name}...")
                run_dir = run_experiment(config_path, args.seed)
                if run_dir is None:
                    print(f"  FAILED: {policy_name}")
                    continue

                run_dirs_by_policy[policy_name] = run_dir
                generate_evaluation(run_dir)
    else:
        # In --skip-run mode, discover run directories
        runs_path = Path("data/runs")
        if runs_path.is_dir():
            if args.single_seat:
                # Single-seat: manifest-based discovery with hard-fail default
                if args.manifest:
                    # Priority 1: explicit --manifest
                    run_dirs_by_policy = _load_batch_manifest(
                        args.manifest, "data/runs"
                    )
                    manifest_data = json.loads(Path(args.manifest).read_text())
                    batch_id = manifest_data.get("batch_id")
                    print(f"  Using manifest: {args.manifest} (batch_id={batch_id})")
                elif args.allow_legacy_seat_discovery:
                    # Legacy heuristic (opt-in only)
                    print(
                        "  WARNING: No batch manifest provided. Using legacy "
                        "'latest per seat' heuristic (unsafe — may mix batches).",
                        file=sys.stderr,
                    )
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
                    # Hard-fail (safe default)
                    print(
                        f"ERROR: No batch manifest provided for "
                        f"{experiment_name} seed={args.seed}.\n"
                        f"Run the battery first (without --skip-run), "
                        f"or provide --manifest <path>,\n"
                        f"or use --allow-legacy-seat-discovery for "
                        f"unsafe heuristic mode.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
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
        metrics_by_bidder, missing_evaluations = _merge_single_seat_evaluations(
            run_dirs_by_policy, policies
        )
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
            batch_id=batch_id,
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
