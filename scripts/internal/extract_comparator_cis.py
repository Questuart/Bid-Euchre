#!/usr/bin/env python
"""
Extract bootstrap confidence intervals for comparator battery metrics.

Reads JSONL game logs from each comparator run, computes per-deal
net_bidder_team_points (bidder - opponent differential), and produces
bootstrap 95% CIs for key metrics plus pairwise significance tests.

Metric definitions match src/bid_euchre/reporting/evaluator.py:
  - net_eppd = sum(net_differential for bid-hands) / total_deals
  - eppd     = sum(bidder_pts for bid-hands) / total_deals
  - CVaR-5%  = mean of worst 5% of per-hand outcomes

Output: JSON file consumed by docs/04_reports/r0/comparator_rankings.md

Usage:
    PYTHONPATH=src uv run python scripts/internal/extract_comparator_cis.py \
        --artifacts-dir data/artifacts/arc_d/r0 \
        --runs-dir data/runs \
        --seed 42 --n-bootstrap 10000 \
        --output data/artifacts/arc_d/r0/comparator_cis_r0.json

The --seed value is used both for bootstrap resampling AND to select the correct
run directories (pattern: auction_comparator_{name}_{seed}_*).  If JSONL-derived
metrics disagree with the comparator battery, the script exits non-zero unless
--force is supplied.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from bid_euchre.analysis.stats import bootstrap_ci
from bid_euchre.scoring import compute_points


def _parse_jsonl_points(log_path: Path) -> dict:
    """Parse JSONL game log into per-deal bidder/net points arrays.

    Mirrors evaluator.py logic:
      - bidder_team_points: bidder's points on hands WITH bids only
      - net_bidder_team_points: (bidder - opponent) on hands WITH bids only
      - deals_total: total hand_end count (including all-pass redeals)

    net_eppd = sum(net_bidder_team_points) / deals_total
    """
    bidder_pts = []
    net_pts = []
    deals_total = 0

    with log_path.open() as f:
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

            deals_total += 1

            winning_bid = record.get("winning_bid")
            bidder_position = record.get("bidder_position")
            t0 = record["t0"]
            t1 = record["t1"]

            # Skip all-pass redeals (no winning bid or bidder)
            if winning_bid is None or bidder_position is None:
                continue

            pts_t0, pts_t1 = compute_points(winning_bid, bidder_position, t0, t1)

            # Bidder team's points
            if bidder_position in (0, 2):
                bidder_val = pts_t0
                net_val = pts_t0 - pts_t1  # bidder - opponent
            else:
                bidder_val = pts_t1
                net_val = pts_t1 - pts_t0  # bidder - opponent

            bidder_pts.append(float(bidder_val))
            net_pts.append(float(net_val))

    return {
        "bidder_team_points": bidder_pts,
        "net_bidder_team_points": net_pts,
        "deals_total": deals_total,
    }


def _cvar_5(arr):
    """CVaR at 5th percentile (mean of worst 5% of outcomes)."""
    n = max(1, int(len(arr) * 0.05))
    return float(np.mean(np.sort(arr)[:n]))


def _compute_bidder_metrics(data: dict) -> dict:
    """Compute summary metrics from parsed deal data.

    Matches evaluator.py definitions:
      eppd     = sum(bidder_team_points) / deals_total
      net_eppd = sum(net_bidder_team_points) / deals_total
    """
    btp = np.array(data["bidder_team_points"])
    ntp = np.array(data["net_bidder_team_points"])
    deals_total = data["deals_total"]

    hands_with_bids = len(btp)
    bid_rate = hands_with_bids / deals_total if deals_total > 0 else 0.0
    # make_rate = fraction of bids where bidder earned positive points
    make_rate = float((btp > 0).sum() / hands_with_bids) if hands_with_bids > 0 else 0.0

    return {
        "deals_total": deals_total,
        "hands_with_bids": hands_with_bids,
        "bid_rate": bid_rate,
        "make_rate": make_rate,
        "eppd": float(btp.sum() / deals_total) if deals_total > 0 else 0.0,
        "net_eppd": float(ntp.sum() / deals_total) if deals_total > 0 else 0.0,
        "cvar_5": _cvar_5(btp) if hands_with_bids > 0 else 0.0,
        "net_cvar_5": _cvar_5(ntp) if hands_with_bids > 0 else 0.0,
    }


def _bootstrap_pairwise_pvalue(
    data_a: np.ndarray,
    data_b: np.ndarray,
    n_bootstrap: int,
    seed: int,
) -> float:
    """Bootstrap permutation test for difference in means.

    H0: mean(A) == mean(B).  Returns two-sided p-value.
    Uses per-deal arrays (padded with zeros for pass deals) so the
    denominator is correctly total_deals for both groups.
    """
    rng = np.random.RandomState(seed)
    observed_diff = data_a.mean() - data_b.mean()

    # Pool and permute
    pooled = np.concatenate([data_a, data_b])
    n_a = len(data_a)
    count_extreme = 0

    for _ in range(n_bootstrap):
        rng.shuffle(pooled)
        perm_diff = pooled[:n_a].mean() - pooled[n_a:].mean()
        if abs(perm_diff) >= abs(observed_diff):
            count_extreme += 1

    return count_extreme / n_bootstrap


def _extract_timestamp(dir_path: Path) -> str:
    """Extract YYYYMMDD_HHMMSS from run directory name."""
    parts = dir_path.name.rsplit("_", 2)
    return "_".join(parts[-2:]) if len(parts) >= 3 else ""


def _load_manifest_runs(manifest_path, bidder_names, runs_dir):
    """Load batch manifest and resolve run directories per bidder.

    Returns dict: {bidder_name: [(seat, run_dir_path), ...]}
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

    expected_seats = manifest.get("expected_seats", 4)
    if expected_seats != 4:
        print(
            f"ERROR: Expected 4 seats, manifest says {expected_seats}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate bidder cardinality
    expected_policies = manifest.get("expected_policies", [])
    for name in bidder_names:
        if name not in expected_policies:
            print(
                f"ERROR: Bidder '{name}' from battery not in manifest "
                f"(manifest policies: {expected_policies})",
                file=sys.stderr,
            )
            sys.exit(1)

    runs_path = Path(runs_dir)
    result = {}
    for name in bidder_names:
        seat_dirs = []
        for seat in range(4):
            key = f"{name}_seat{seat}"
            dirname = manifest["members"].get(key)
            if dirname is None:
                print(
                    f"ERROR: Manifest missing member '{key}'",
                    file=sys.stderr,
                )
                sys.exit(1)
            full_path = runs_path / dirname
            if not full_path.is_dir():
                print(
                    f"ERROR: Manifest member '{key}' directory not found: {full_path}",
                    file=sys.stderr,
                )
                sys.exit(1)
            seat_dirs.append((seat, full_path))
        result[name] = seat_dirs

    return result


def _validate_batch_coherence(seat_run_dirs, bidder_name, strict=True):
    """Validate that all seat runs in a batch share consistent metadata.

    Checks: seed, n_per (from config in meta.json), and mode consistency.
    If strict (manifest mode): sys.exit(1) on mismatch.
    If not strict (legacy mode): stderr warning only.
    """
    seeds = []
    n_pers = []
    for seat, run_dir in seat_run_dirs:
        meta_path = Path(run_dir) / "meta.json"
        if not meta_path.exists():
            msg = f"WARNING: No meta.json in {run_dir} (seat {seat} of {bidder_name})"
            if strict:
                print(f"ERROR: {msg}", file=sys.stderr)
                sys.exit(1)
            else:
                print(msg, file=sys.stderr)
            continue
        meta = json.loads(meta_path.read_text())
        seeds.append(meta.get("seed"))
        config = meta.get("config", {})
        n_pers.append(config.get("parameters", {}).get("n_per"))

    if len(set(seeds)) > 1:
        msg = f"Batch coherence violation for {bidder_name}: mixed seeds {set(seeds)}"
        if strict:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"WARNING: {msg}", file=sys.stderr)

    if len(set(n_pers)) > 1:
        msg = f"Batch coherence violation for {bidder_name}: mixed n_per {set(n_pers)}"
        if strict:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"WARNING: {msg}", file=sys.stderr)

    # Cardinality check
    if len(seat_run_dirs) != 4:
        msg = (
            f"Batch coherence violation for {bidder_name}: "
            f"expected 4 seats, got {len(seat_run_dirs)}"
        )
        if strict:
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"WARNING: {msg}", file=sys.stderr)


def _make_per_deal_net_array(data: dict) -> np.ndarray:
    """Create per-deal net_eppd array: bid-hand differentials + zeros for passes.

    This yields an array of length deals_total where:
      - bid-hand entries = net_bidder_team_points values
      - pass-hand entries = 0 (no score on all-pass)

    mean() of this array == net_eppd.
    """
    ntp = data["net_bidder_team_points"]
    n_passes = data["deals_total"] - len(ntp)
    return np.concatenate([np.array(ntp, dtype=float), np.zeros(n_passes, dtype=float)])


def main():
    parser = argparse.ArgumentParser(
        description="Extract bootstrap CIs for comparator battery"
    )
    parser.add_argument(
        "--artifacts-dir",
        required=True,
        help="Path to artifacts dir (e.g., data/artifacts/arc_d/r0)",
    )
    parser.add_argument(
        "--runs-dir",
        required=True,
        help="Path to data/runs directory",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-bootstrap", type=int, default=10000)
    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON path",
    )
    parser.add_argument(
        "--battery-file",
        default="comparator_battery_r0.json",
        help="Battery JSON filename within artifacts-dir (default: comparator_battery_r0.json)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write output even if JSONL-vs-battery validation fails",
    )
    parser.add_argument(
        "--single-seat",
        action="store_true",
        help="Merge 4 per-seat sub-runs per bidder",
    )
    parser.add_argument(
        "--manifest",
        default=None,
        help="Batch manifest JSON for single-seat coherence validation",
    )
    parser.add_argument(
        "--allow-legacy-seat-discovery",
        action="store_true",
        help="Allow heuristic 'latest per seat' discovery when no manifest exists",
    )
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    runs_dir = Path(args.runs_dir)

    # Load comparator battery to get bidder list
    battery_path = artifacts_dir / args.battery_file
    if not battery_path.exists():
        print(f"ERROR: {battery_path} not found", file=sys.stderr)
        sys.exit(1)
    battery = json.loads(battery_path.read_text())

    bidder_names = list(battery["bidders"].keys())
    print(f"Bidders: {bidder_names}")

    # Resolve single-seat run directories (manifest or legacy)
    manifest_seat_dirs = None  # {bidder_name: [(seat, path), ...]}
    use_strict_coherence = True
    if args.single_seat:
        if args.manifest:
            # Priority 1: explicit manifest
            manifest_seat_dirs = _load_manifest_runs(
                args.manifest, bidder_names, str(runs_dir)
            )
            print(f"  Using manifest: {args.manifest}")
        elif not args.allow_legacy_seat_discovery:
            # Priority 2: hard-fail (safe default)
            print(
                "ERROR: --single-seat requires --manifest <path> for batch "
                "coherence validation.\n"
                "Run the battery first with the orchestrator to generate a "
                "manifest, or use --allow-legacy-seat-discovery for unsafe "
                "heuristic mode.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            # Priority 3: legacy heuristic (opt-in)
            use_strict_coherence = False
            print(
                "  WARNING: No manifest provided. Using legacy 'latest per seat' "
                "heuristic (may mix batches).",
                file=sys.stderr,
            )

    # Locate JSONL log for each bidder
    all_data = {}
    run_directories = {}  # {bidder_name: [dir_basenames]} for provenance
    for name in bidder_names:
        if args.single_seat:
            merged = {
                "bidder_team_points": [],
                "net_bidder_team_points": [],
                "deals_total": 0,
            }

            if manifest_seat_dirs is not None:
                # Manifest-resolved paths
                seat_run_dirs = manifest_seat_dirs[name]
            else:
                # Legacy glob discovery
                seat_run_dirs = []
                for seat in range(4):
                    pattern = f"auction_comparator_{name}_seat{seat}_{args.seed}_*"
                    candidates = sorted(runs_dir.glob(pattern))
                    if not candidates:
                        print(
                            f"ERROR: No run dir for {name} seat {seat}",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    seat_run_dirs.append((seat, candidates[-1]))

            # Validate batch coherence
            _validate_batch_coherence(seat_run_dirs, name, strict=use_strict_coherence)

            run_directories[name] = []
            for seat, run_dir in seat_run_dirs:
                logs = sorted(Path(run_dir).glob("logs/*.jsonl"))
                if not logs:
                    print(
                        f"ERROR: No JSONL log in {run_dir}/logs/",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                log_path = logs[0]
                print(f"    {name} seat {seat}: {log_path}")
                seat_data = _parse_jsonl_points(log_path)
                merged["bidder_team_points"].extend(seat_data["bidder_team_points"])
                merged["net_bidder_team_points"].extend(
                    seat_data["net_bidder_team_points"]
                )
                merged["deals_total"] += seat_data["deals_total"]
                run_directories[name].append(Path(run_dir).name)

            all_data[name] = merged
        else:
            # Original single-directory mode
            candidates = sorted(
                runs_dir.glob(f"auction_comparator_{name}_{args.seed}_*")
            )
            if not candidates:
                print(
                    f"ERROR: No run dir for {name} with seed {args.seed}",
                    file=sys.stderr,
                )
                sys.exit(1)
            run_dir = candidates[-1]  # most recent matching seed
            logs = sorted(run_dir.glob("logs/*.jsonl"))
            if not logs:
                print(f"ERROR: No JSONL log in {run_dir}/logs/", file=sys.stderr)
                sys.exit(1)
            log_path = logs[0]
            print(f"  {name}: {log_path}")
            all_data[name] = _parse_jsonl_points(log_path)

    # Verify metrics match battery point estimates
    print("\nValidation (JSONL vs battery):")
    mismatches = []
    for name in bidder_names:
        metrics = _compute_bidder_metrics(all_data[name])
        bat = battery["bidders"][name]
        net_match = abs(metrics["net_eppd"] - bat["net_eppd"]) < 0.01
        eppd_match = abs(metrics["eppd"] - bat["eppd"]) < 0.01
        status = "OK" if (net_match and eppd_match) else "MISMATCH"
        if status == "MISMATCH":
            mismatches.append(name)
        print(
            f"  {name}: net_eppd={metrics['net_eppd']:.4f} (bat={bat['net_eppd']:.4f}) "
            f"eppd={metrics['eppd']:.4f} (bat={bat['eppd']:.4f}) [{status}]"
        )

    if mismatches:
        msg = (
            f"ERROR: JSONL-derived metrics disagree with battery for: "
            f"{', '.join(mismatches)}"
        )
        if args.force:
            print(f"WARNING: {msg} (continuing due to --force)", file=sys.stderr)
        else:
            print(f"{msg}\nUse --force to write output anyway.", file=sys.stderr)
            sys.exit(1)

    # Compute metrics + bootstrap CIs for each bidder
    results = {}
    for name, data in all_data.items():
        metrics = _compute_bidder_metrics(data)
        btp = np.array(data["bidder_team_points"])
        ntp = np.array(data["net_bidder_team_points"])

        # Per-deal arrays for bootstrap (zeros for pass deals)
        per_deal_net = _make_per_deal_net_array(data)

        # Bootstrap CIs on per-deal arrays (net_eppd, eppd)
        net_eppd_ci = bootstrap_ci(
            per_deal_net.tolist(),
            statistic=np.mean,
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        )
        n_passes = data["deals_total"] - len(btp)
        per_deal_eppd = np.concatenate([btp, np.zeros(n_passes)])
        eppd_ci = bootstrap_ci(
            per_deal_eppd.tolist(),
            statistic=np.mean,
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        )

        # CVaR CIs on bid-hand-only arrays (matches evaluator definition)
        cvar5_ci = (
            bootstrap_ci(
                btp.tolist(),
                statistic=_cvar_5,
                n_bootstrap=args.n_bootstrap,
                seed=args.seed,
            )
            if len(btp) > 0
            else (0.0, 0.0, 0.0)
        )
        net_cvar5_ci = (
            bootstrap_ci(
                ntp.tolist(),
                statistic=_cvar_5,
                n_bootstrap=args.n_bootstrap,
                seed=args.seed,
            )
            if len(ntp) > 0
            else (0.0, 0.0, 0.0)
        )

        results[name] = {
            **metrics,
            "net_eppd_ci": list(net_eppd_ci),
            "eppd_ci": list(eppd_ci),
            "cvar_5_ci": list(cvar5_ci),
            "net_cvar_5_ci": list(net_cvar5_ci),
        }
        print(
            f"  {name}: net_eppd={metrics['net_eppd']:.4f} "
            f"[{net_eppd_ci[1]:.4f}, {net_eppd_ci[2]:.4f}]"
        )

    # Sort by net_eppd descending for rankings
    ranked = sorted(results.keys(), key=lambda n: results[n]["net_eppd"], reverse=True)

    # Pairwise significance between adjacent bidders (by net_eppd rank)
    # Uses per-deal arrays so means reflect net_eppd correctly
    pairwise = []
    for i in range(len(ranked) - 1):
        a_name = ranked[i]
        b_name = ranked[i + 1]
        a_arr = _make_per_deal_net_array(all_data[a_name])
        b_arr = _make_per_deal_net_array(all_data[b_name])
        p_val = _bootstrap_pairwise_pvalue(
            a_arr,
            b_arr,
            n_bootstrap=args.n_bootstrap,
            seed=args.seed,
        )
        pairwise.append(
            {
                "bidder_a": a_name,
                "bidder_b": b_name,
                "net_eppd_diff": float(a_arr.mean() - b_arr.mean()),
                "p_value": p_val,
            }
        )
        print(
            f"  {a_name} vs {b_name}: diff={a_arr.mean() - b_arr.mean():.4f}, p={p_val:.4f}"
        )

    output = {
        "schema": "comparator_cis_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "n_bootstrap": args.n_bootstrap,
        "batch_manifest": args.manifest,
        "ranked_order": ranked,
        "bidders": results,
        "pairwise_significance": pairwise,
    }
    if run_directories:
        output["run_directories"] = run_directories

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
