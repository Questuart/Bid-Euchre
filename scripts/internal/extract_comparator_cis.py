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

    # Locate JSONL log for each bidder
    all_data = {}
    for name in bidder_names:
        if args.single_seat:
            # Merge 4 seat sub-runs per bidder.
            # Use the latest matching directory per seat — sequential execution
            # means each seat has a distinct timestamp, so exact-match grouping
            # is not viable. Instead, select latest per seat and warn if the
            # timestamps span more than 1 hour (suggesting mixed batches).
            merged = {
                "bidder_team_points": [],
                "net_bidder_team_points": [],
                "deals_total": 0,
            }

            seat_run_dirs = []  # (seat, path) pairs for logging
            for seat in range(4):
                pattern = f"auction_comparator_{name}_seat{seat}_{args.seed}_*"
                candidates = sorted(runs_dir.glob(pattern))
                if not candidates:
                    print(
                        f"ERROR: No run dir for {name} seat {seat}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                run_dir = candidates[-1]  # latest matching
                seat_run_dirs.append((seat, run_dir))

                logs = sorted(run_dir.glob("logs/*.jsonl"))
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

            # Batch coherence check: warn if timestamps span >1 hour
            def _extract_timestamp(dir_path: Path) -> str:
                """Extract YYYYMMDD_HHMMSS from run directory name."""
                parts = dir_path.name.rsplit("_", 2)
                return "_".join(parts[-2:]) if len(parts) >= 3 else ""

            timestamps = [_extract_timestamp(p) for _, p in seat_run_dirs]
            if len(set(timestamps)) > 1:
                print(
                    f"  NOTE: {name} seat dirs have different timestamps "
                    f"({', '.join(timestamps)}); verify they are from the same batch",
                    file=sys.stderr,
                )

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
        "ranked_order": ranked,
        "bidders": results,
        "pairwise_significance": pairwise,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
