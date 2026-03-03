#!/usr/bin/env python
"""
Lambda Sweep: simulation-based risk_lambda tuning for HybridOLSaBidder.

Runs self-play experiments at each lambda grid point, extracts per-deal net
differentials from JSONL logs, computes paired bootstrap CIs vs baseline
(lambda=0.0), and selects lambda* via epsilon-greedy rule.

Usage:
    uv run python scripts/internal/run_lambda_sweep.py \
        --artifact-path data/artifacts/arc_d/r0/hybrid_r0.json \
        --output /tmp/lambda_sweep_result.json \
        --seed 42 --n-per 10000

    # Skip-run mode (analyze existing runs):
    uv run python scripts/internal/run_lambda_sweep.py \
        --artifact-path data/artifacts/arc_d/r0/hybrid_r0.json \
        --output /tmp/lambda_sweep_result.json \
        --skip-run --manifest data/runs/lambda_sweep_manifest_....json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

# ---------------------------------------------------------------------------
# Run directory detection (same pattern as run_auction_comparator.py)
# ---------------------------------------------------------------------------


def _snapshot_runs_dir(runs_base="data/runs"):
    """Snapshot current run directory names for before/after diffing."""
    runs_path = Path(runs_base)
    if not runs_path.is_dir():
        return set()
    return {p.name for p in runs_path.iterdir() if p.is_dir()}


def _detect_new_run_dir(runs_base, before_snapshot):
    """Detect the new run directory by diffing data/runs/ before/after."""
    runs_path = Path(runs_base)
    if not runs_path.is_dir():
        return None
    after_snapshot = {p.name for p in runs_path.iterdir() if p.is_dir()}
    new_dirs = after_snapshot - before_snapshot
    if len(new_dirs) == 1:
        return str(runs_path / new_dirs.pop())
    return None


# ---------------------------------------------------------------------------
# Grid parsing
# ---------------------------------------------------------------------------


def parse_lambda_grid(grid_str):
    """Parse comma-separated lambda grid string into sorted list of floats."""
    return sorted(float(x.strip()) for x in grid_str.split(","))


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------


def generate_self_play_config(lambda_val, artifact_path, pass_threshold, seed, n_per):
    """Generate a self-play experiment config dict for a single lambda value.

    Returns a dict suitable for YAML serialization.
    """
    lambda_str = f"{lambda_val:.4f}".rstrip("0").rstrip(".")
    return {
        "experiment_name": f"lambda_sweep_{lambda_str}",
        "bidding_policies": [
            {
                "name": "hybrid_olsa",
                "class_name": "HybridOLSaBidder",
                "params": {
                    "artifact_path": str(artifact_path),
                    "bid_level_search": True,
                    "risk_lambda": float(lambda_val),
                    "pass_threshold": float(pass_threshold),
                },
            }
        ],
        "strategies": [
            {"name": "glutton", "class_name": "GluttonStrategy"},
        ],
        "scenarios": [{"contract_type": None}],
        "parameters": {
            "play_strategy": "glutton",
            "n_per": int(n_per),
            "seed": int(seed),
            "log_level": "hand",
        },
    }


# ---------------------------------------------------------------------------
# Experiment execution (follows run_auction_comparator.py pattern)
# ---------------------------------------------------------------------------


def run_experiment(config_path, seed, runs_base="data/runs"):
    """Run a single experiment via the canonical runner.

    Returns the detected run directory path, or None on failure.
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

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAILED: experiment with config {config_path}")
        print(result.stderr)
        return None

    # Primary: parse stdout for "Run directory: <path>"
    for line in result.stdout.splitlines():
        if "Run directory:" in line:
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


# ---------------------------------------------------------------------------
# Per-deal net extraction from JSONL
# ---------------------------------------------------------------------------


def load_per_deal_nets(run_dir):
    """Extract per-deal net differential from JSONL hand_end records.

    Uses canonical scoring (compute_points from bid_euchre.scoring).
    Net = bidder_team_points - opponent_team_points.
    All-pass redeals (no winning_bid): net = 0.

    Returns dict: {deal_id: net_differential}
    """
    # Deferred import: avoid import-time dependency on bid_euchre when
    # only using CLI/config helpers from this script module.
    from bid_euchre.scoring import compute_points

    logs_dir = Path(run_dir) / "logs"
    if not logs_dir.is_dir():
        return {}

    nets = {}
    for log_file in sorted(logs_dir.glob("*.jsonl")):
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("event") != "hand_end":
                    continue

                deal_id = record.get("deal_id")
                if deal_id is None:
                    continue

                winning_bid = record.get("winning_bid")
                bidder_position = record.get("bidder_position")
                t0 = record.get("t0")
                t1 = record.get("t1")

                # All-pass redeal: net = 0
                if winning_bid is None or bidder_position is None:
                    nets[int(deal_id)] = 0.0
                    continue

                if t0 is None or t1 is None:
                    continue

                pts0, pts1 = compute_points(
                    int(winning_bid), int(bidder_position), int(t0), int(t1)
                )
                # Net = bidder_team - opponent_team
                if int(bidder_position) in (0, 2):
                    nets[int(deal_id)] = float(pts0 - pts1)
                else:
                    nets[int(deal_id)] = float(pts1 - pts0)

    return nets


# ---------------------------------------------------------------------------
# Deal pairing validation
# ---------------------------------------------------------------------------


def validate_pairing(baseline_nets, candidate_nets):
    """Assert identical deal_id keys between baseline and candidate.

    Raises ValueError if deal sets don't match exactly.
    """
    baseline_keys = set(baseline_nets.keys())
    candidate_keys = set(candidate_nets.keys())

    if baseline_keys != candidate_keys:
        only_baseline = baseline_keys - candidate_keys
        only_candidate = candidate_keys - baseline_keys
        msg_parts = ["Deal sets don't match for paired comparison."]
        if only_baseline:
            msg_parts.append(f"  Only in baseline: {len(only_baseline)} deals")
        if only_candidate:
            msg_parts.append(f"  Only in candidate: {len(only_candidate)} deals")
        raise ValueError("\n".join(msg_parts))


# ---------------------------------------------------------------------------
# Paired bootstrap CI
# ---------------------------------------------------------------------------


def paired_bootstrap_ci(
    baseline_nets, candidate_nets, n_bootstrap=10000, ci=0.95, seed=42
):
    """Compute paired bootstrap CI on delta = candidate - baseline.

    Args:
        baseline_nets: dict {deal_id: net} for lambda=0.0
        candidate_nets: dict {deal_id: net} for candidate lambda
        n_bootstrap: Number of bootstrap resamples.
        ci: Confidence level (default 0.95).
        seed: RNG seed.

    Returns:
        (delta_mean, ci_lo, ci_hi)
    """
    # Align by deal_id
    deal_ids = sorted(baseline_nets.keys())
    baseline_arr = np.array([baseline_nets[d] for d in deal_ids])
    candidate_arr = np.array([candidate_nets[d] for d in deal_ids])
    deltas = candidate_arr - baseline_arr

    delta_mean = float(np.mean(deltas))

    rng = np.random.RandomState(seed)
    n = len(deltas)
    boot_means = np.array(
        [rng.choice(deltas, size=n, replace=True).mean() for _ in range(n_bootstrap)]
    )

    alpha = (1.0 - ci) / 2.0
    ci_lo = float(np.percentile(boot_means, 100 * alpha))
    ci_hi = float(np.percentile(boot_means, 100 * (1.0 - alpha)))

    return delta_mean, ci_lo, ci_hi


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------


def apply_guardrails(
    metrics, bid_rate_floor=0.05, bid_rate_cap=0.95, make_rate_floor=0.45
):
    """Apply guardrail checks to a metrics dict.

    Returns dict with guardrail results: {pass_bid_rate_floor, pass_bid_rate_cap,
    pass_make_rate, all_pass}.
    """
    bid_rate = metrics.get("bid_rate")
    make_rate = metrics.get("make_rate")

    result = {
        "pass_bid_rate_floor": bid_rate >= bid_rate_floor
        if bid_rate is not None
        else True,
        "pass_bid_rate_cap": bid_rate <= bid_rate_cap if bid_rate is not None else True,
        "pass_make_rate": make_rate >= make_rate_floor
        if make_rate is not None
        else True,
    }
    result["all_pass"] = all(
        [
            result["pass_bid_rate_floor"],
            result["pass_bid_rate_cap"],
            result["pass_make_rate"],
        ]
    )
    return result


# ---------------------------------------------------------------------------
# Lambda selection (epsilon-greedy)
# ---------------------------------------------------------------------------


def select_lambda_star(sweep_results, epsilon=0.02):
    """Select lambda* via epsilon-greedy: smallest lambda within epsilon of best.

    Among lambda values that pass all guardrails, select the smallest lambda
    whose net_eppd is within `epsilon` of the best net_eppd.

    If no lambda passes guardrails, returns 0.0 (retain baseline).

    Args:
        sweep_results: list of dicts, each with 'risk_lambda', 'net_eppd',
            and 'guardrails' (dict with 'all_pass' key).
        epsilon: Tolerance for epsilon-greedy selection.

    Returns:
        Selected lambda value (float).
    """
    survivors = [
        r for r in sweep_results if r.get("guardrails", {}).get("all_pass", False)
    ]

    if not survivors:
        return 0.0

    best_net_eppd = max(r["net_eppd"] for r in survivors)

    # Within-epsilon candidates, sorted by lambda ascending
    within_eps = sorted(
        [r for r in survivors if best_net_eppd - r["net_eppd"] <= epsilon],
        key=lambda r: r["risk_lambda"],
    )

    if not within_eps:
        return 0.0

    return within_eps[0]["risk_lambda"]


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------


def write_sweep_manifest(runs_base, grid, seed, n_per, run_dirs):
    """Write a sweep manifest mapping lambda values to run directories.

    Args:
        runs_base: Base runs directory (e.g., "data/runs")
        grid: List of lambda values
        seed: Experiment seed
        n_per: Deals per experiment
        run_dirs: dict {lambda_value: run_dir_path}

    Returns:
        Path to written manifest file.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest = {
        "schema": "lambda_sweep_manifest_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "n_per": n_per,
        "grid": grid,
        "members": {str(lam): Path(run_dir).name for lam, run_dir in run_dirs.items()},
    }

    runs_path = Path(runs_base)
    manifest_path = runs_path / f"lambda_sweep_manifest_{seed}_{timestamp}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return str(manifest_path)


def _load_sweep_manifest(manifest_path, runs_dir):
    """Load and validate a sweep manifest, returning resolved run dirs.

    Returns dict: {lambda_value_float: resolved_run_dir_path}
    Calls sys.exit(1) on validation failure.
    """
    manifest_p = Path(manifest_path)
    if not manifest_p.exists():
        print(f"ERROR: Manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(manifest_p.read_text())
    if manifest.get("schema") != "lambda_sweep_manifest_v1":
        print(
            f"ERROR: Unknown manifest schema: {manifest.get('schema')}",
            file=sys.stderr,
        )
        sys.exit(1)

    runs_path = Path(runs_dir)
    resolved = {}
    missing = []
    for lam_str, dirname in manifest["members"].items():
        full_path = runs_path / dirname
        if not full_path.is_dir():
            missing.append(f"  lambda={lam_str}: {full_path}")
        else:
            resolved[float(lam_str)] = str(full_path)

    if missing:
        print(
            "ERROR: Manifest references missing run directories:\n"
            + "\n".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)

    return resolved


# ---------------------------------------------------------------------------
# Summary formatting
# ---------------------------------------------------------------------------


def format_sweep_summary(
    grid,
    sweep_results,
    lambda_star,
    seed,
    n_per,
    pass_threshold,
    artifact_path,
    epsilon,
    bootstrap_results=None,
):
    """Format the final sweep summary as a lambda_sweep_v1 JSON dict.

    Args:
        grid: Lambda grid values
        sweep_results: List of per-lambda result dicts
        lambda_star: Selected lambda value
        seed: Experiment seed
        n_per: Deals per experiment
        pass_threshold: Pass threshold used
        artifact_path: Path to model artifact
        epsilon: Epsilon-greedy tolerance
        bootstrap_results: Optional dict {lambda: (delta, ci_lo, ci_hi)}

    Returns:
        dict with lambda_sweep_v1 schema.
    """
    results_list = []
    for r in sweep_results:
        entry = {
            "risk_lambda": r["risk_lambda"],
            "net_eppd": r["net_eppd"],
            "bid_rate": r["bid_rate"],
            "make_rate": r["make_rate"],
            "guardrails": r.get("guardrails", {}),
        }
        lam = r["risk_lambda"]
        if bootstrap_results and lam in bootstrap_results:
            delta, ci_lo, ci_hi = bootstrap_results[lam]
            entry["delta_vs_baseline"] = delta
            entry["ci_95_lo"] = ci_lo
            entry["ci_95_hi"] = ci_hi
            entry["ci_excludes_zero"] = ci_lo > 0 or ci_hi < 0
        results_list.append(entry)

    requires_h2h = lambda_star > 0.0
    status = "PROVISIONAL" if requires_h2h else "FINAL"

    return {
        "schema": "lambda_sweep_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "n_per": n_per,
        "pass_threshold": pass_threshold,
        "artifact_path": str(artifact_path),
        "grid": grid,
        "epsilon": epsilon,
        "lambda_star": lambda_star,
        "status": status,
        "requires_h2h_confirmation": requires_h2h,
        "results": results_list,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Lambda Sweep: simulation-based risk_lambda tuning"
    )
    parser.add_argument("--seed", type=int, default=42, help="Experiment seed")
    parser.add_argument(
        "--n-per", type=int, default=10000, help="Deals per lambda point"
    )
    parser.add_argument(
        "--grid",
        type=str,
        default="0.0,0.05,0.1,0.2,0.5,1.0,2.0",
        help="Comma-separated lambda grid (default: 0.0,0.05,0.1,0.2,0.5,1.0,2.0)",
    )
    parser.add_argument(
        "--artifact-path", required=True, help="Path to hybrid_olsa_v1 artifact"
    )
    parser.add_argument(
        "--pass-threshold",
        type=float,
        default=0.0,
        help="Pass threshold from Track C (default: 0.0)",
    )
    parser.add_argument(
        "--output", required=True, help="Output path for sweep summary JSON"
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip experiment runs, analyze existing data",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Manifest path for --skip-run mode",
    )
    parser.add_argument(
        "--epsilon",
        type=float,
        default=0.02,
        help="Epsilon for epsilon-greedy selection (default: 0.02)",
    )
    parser.add_argument(
        "--n-bootstrap",
        type=int,
        default=10000,
        help="Number of bootstrap resamples (default: 10000)",
    )
    args = parser.parse_args()

    grid = parse_lambda_grid(args.grid)

    # Validate artifact exists
    if not Path(args.artifact_path).exists():
        print(f"ERROR: Artifact not found: {args.artifact_path}", file=sys.stderr)
        sys.exit(1)

    # Ensure 0.0 is in the grid (required as baseline)
    if 0.0 not in grid:
        print("ERROR: Grid must include 0.0 as baseline", file=sys.stderr)
        sys.exit(1)

    run_dirs = {}  # {lambda_float: run_dir_path}

    if not args.skip_run:
        print(
            f"Running lambda sweep: {len(grid)} grid points, "
            f"n_per={args.n_per}, seed={args.seed}"
        )
        print(f"Grid: {grid}")

        for lam in grid:
            config = generate_self_play_config(
                lam, args.artifact_path, args.pass_threshold, args.seed, args.n_per
            )

            lambda_str = f"{lam:.4f}".rstrip("0").rstrip(".")
            config_path = f"/tmp/lambda_sweep_{lambda_str}.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config, f)

            print(f"  Running lambda={lam}...")
            run_dir = run_experiment(config_path, args.seed)
            if run_dir is None:
                print(f"  FAILED: lambda={lam}")
                continue

            run_dirs[lam] = run_dir
            generate_evaluation(run_dir)

        # Write manifest
        if run_dirs:
            manifest_path = write_sweep_manifest(
                "data/runs", grid, args.seed, args.n_per, run_dirs
            )
            print(f"  Manifest: {manifest_path}")
    else:
        # Skip-run mode: load from manifest
        if not args.manifest:
            print(
                "ERROR: --skip-run requires --manifest <path>",
                file=sys.stderr,
            )
            sys.exit(1)
        run_dirs = _load_sweep_manifest(args.manifest, "data/runs")
        print(f"  Loaded manifest: {args.manifest} ({len(run_dirs)} runs)")

    # --- Collect metrics ---
    sweep_results = []
    per_deal_nets_by_lambda = {}

    for lam in grid:
        run_dir = run_dirs.get(lam)
        if not run_dir:
            print(f"WARNING: No run directory for lambda={lam}, skipping")
            continue

        # Load evaluation metrics
        evaluation = load_evaluation(run_dir)
        if not evaluation or not evaluation.get("strategies"):
            print(f"WARNING: No evaluation for lambda={lam}, skipping")
            continue

        strat = evaluation["strategies"][0]
        metrics = {
            "risk_lambda": lam,
            "net_eppd": strat.get("net_expected_points_per_deal", 0.0),
            "bid_rate": strat.get("bid_rate", 0.0),
            "make_rate": strat.get("make_rate", 0.0),
            "deals_total": strat.get("deals_total", 0),
            "hands_with_bids": strat.get("hands_with_bids", 0),
        }

        # Apply guardrails
        metrics["guardrails"] = apply_guardrails(metrics)
        sweep_results.append(metrics)

        # Load per-deal nets for bootstrap
        nets = load_per_deal_nets(run_dir)
        if nets:
            per_deal_nets_by_lambda[lam] = nets

    if not sweep_results:
        print("ERROR: No valid results collected", file=sys.stderr)
        sys.exit(1)

    # --- Paired bootstrap CIs ---
    bootstrap_results = {}
    baseline_nets = per_deal_nets_by_lambda.get(0.0, {})

    if baseline_nets:
        for lam in grid:
            if lam == 0.0:
                continue
            candidate_nets = per_deal_nets_by_lambda.get(lam, {})
            if not candidate_nets:
                continue

            try:
                validate_pairing(baseline_nets, candidate_nets)
                delta, ci_lo, ci_hi = paired_bootstrap_ci(
                    baseline_nets,
                    candidate_nets,
                    n_bootstrap=args.n_bootstrap,
                    seed=args.seed,
                )
                bootstrap_results[lam] = (delta, ci_lo, ci_hi)
                ci_str = f"[{ci_lo:+.4f}, {ci_hi:+.4f}]"
                excludes = "yes" if (ci_lo > 0 or ci_hi < 0) else "no"
                print(
                    f"  lambda={lam}: delta={delta:+.4f}, "
                    f"95% CI={ci_str}, excludes 0: {excludes}"
                )
            except ValueError as e:
                print(f"  WARNING: Pairing failed for lambda={lam}: {e}")

    # --- Select lambda* ---
    lambda_star = select_lambda_star(sweep_results, epsilon=args.epsilon)
    print(f"\nlambda* = {lambda_star}")

    # --- Write output ---
    summary = format_sweep_summary(
        grid=grid,
        sweep_results=sweep_results,
        lambda_star=lambda_star,
        seed=args.seed,
        n_per=args.n_per,
        pass_threshold=args.pass_threshold,
        artifact_path=args.artifact_path,
        epsilon=args.epsilon,
        bootstrap_results=bootstrap_results,
    )

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    print(f"Output written to: {args.output}")
    print(f"Status: {summary['status']}")
    if summary["requires_h2h_confirmation"]:
        print(
            f"  lambda*={lambda_star} requires H2H confirmation before final adoption"
        )
    else:
        print(f"  lambda*={lambda_star} is final (baseline retained)")


if __name__ == "__main__":
    main()
