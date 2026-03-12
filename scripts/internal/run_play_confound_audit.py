#!/usr/bin/env python
"""
E1 Play-Policy Confound Audit — ranking comparison script.

Compares H2H battery summaries run with different play strategies to determine
whether bidder rankings are stable across play policies (cosmetic confound)
or shift meaningfully (real confound requiring label retraining).

Usage:
    PYTHONPATH=src uv run python scripts/internal/run_play_confound_audit.py \
        --glutton data/artifacts/arc_d/e1/glutton/smoke.json \
        --greedy  data/artifacts/arc_d/e1/greedy/smoke.json

Output:
    - Per-bidder ranking comparison table
    - Spearman rank correlation
    - Per-cell delta comparison
    - Verdict: STABLE (cosmetic) or UNSTABLE (real confound)
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats


def extract_rankings(summary):
    """Extract per-bidder net_eppd rankings from H2H battery summary.

    For each bidder, compute mean net_eppd across all matchups where they
    appear as bidder_a (seats 0,2 = team0).

    Returns dict: {bidder_name: mean_net_eppd_delta}
    """
    cells = summary.get("cells", {})
    bidder_deltas = {}

    for _matchup_id, cell in cells.items():
        bidder_a = cell.get("bidder_a", "")
        delta = cell.get("net_eppd_delta")

        if delta is None:
            continue

        if bidder_a not in bidder_deltas:
            bidder_deltas[bidder_a] = []
        bidder_deltas[bidder_a].append(delta)

    # Compute mean delta per bidder
    rankings = {}
    for bidder, deltas in bidder_deltas.items():
        rankings[bidder] = float(np.mean(deltas))

    return rankings


def compare_rankings(glutton_rankings, greedy_rankings):
    """Compare rankings between two play policies.

    Returns:
        dict with comparison metrics:
        - spearman_rho: Spearman rank correlation
        - spearman_p: p-value for the correlation
        - bidder_table: per-bidder comparison
        - ranking_inversions: list of (bidder_a, bidder_b) pairs where
          relative ordering changed
        - verdict: "STABLE" or "UNSTABLE"
    """
    # Get common bidders
    common = sorted(set(glutton_rankings.keys()) & set(greedy_rankings.keys()))
    if len(common) < 2:
        return {
            "error": f"Need at least 2 common bidders, got {len(common)}",
            "verdict": "ERROR",
        }

    # Build rank arrays
    g_values = [glutton_rankings[b] for b in common]
    r_values = [greedy_rankings[b] for b in common]

    # Compute Spearman rank correlation
    rho, p_value = stats.spearmanr(g_values, r_values)

    # Build per-bidder comparison table
    g_sorted = sorted(common, key=lambda b: glutton_rankings[b], reverse=True)
    r_sorted = sorted(common, key=lambda b: greedy_rankings[b], reverse=True)
    g_rank = {b: i + 1 for i, b in enumerate(g_sorted)}
    r_rank = {b: i + 1 for i, b in enumerate(r_sorted)}

    bidder_table = []
    for b in g_sorted:
        bidder_table.append(
            {
                "bidder": b,
                "glutton_net_eppd": round(glutton_rankings[b], 4),
                "greedy_net_eppd": round(greedy_rankings[b], 4),
                "delta": round(glutton_rankings[b] - greedy_rankings[b], 4),
                "glutton_rank": g_rank[b],
                "greedy_rank": r_rank[b],
                "rank_change": r_rank[b] - g_rank[b],
            }
        )

    # Detect ranking inversions
    inversions = []
    for i, a in enumerate(common):
        for b in common[i + 1 :]:
            g_order = glutton_rankings[a] > glutton_rankings[b]
            r_order = greedy_rankings[a] > greedy_rankings[b]
            if g_order != r_order:
                inversions.append((a, b))

    # Verdict
    # STABLE: rho > 0.9 AND no inversions in top-4
    top4_glutton = set(g_sorted[:4])
    top4_greedy = set(r_sorted[:4])
    top4_match = top4_glutton == top4_greedy
    top4_inversions = [
        (a, b) for a, b in inversions if a in top4_glutton and b in top4_glutton
    ]

    if rho > 0.9 and len(top4_inversions) == 0:
        verdict = "STABLE"
    else:
        verdict = "UNSTABLE"

    return {
        "n_bidders": len(common),
        "spearman_rho": round(float(rho), 4),
        "spearman_p": round(float(p_value), 6),
        "bidder_table": bidder_table,
        "ranking_inversions": inversions,
        "top4_glutton": g_sorted[:4],
        "top4_greedy": r_sorted[:4],
        "top4_set_match": top4_match,
        "top4_inversions": top4_inversions,
        "verdict": verdict,
    }


def compare_cells(glutton_summary, greedy_summary):
    """Compare per-cell metrics between policies.

    Returns list of per-matchup comparisons with absolute delta changes.
    """
    g_cells = glutton_summary.get("cells", {})
    r_cells = greedy_summary.get("cells", {})
    common = sorted(set(g_cells.keys()) & set(r_cells.keys()))

    comparisons = []
    for mid in common:
        gc = g_cells[mid]
        rc = r_cells[mid]
        g_delta = gc.get("net_eppd_delta")
        r_delta = rc.get("net_eppd_delta")
        if g_delta is not None and r_delta is not None:
            comparisons.append(
                {
                    "matchup_id": mid,
                    "glutton_delta": round(g_delta, 4),
                    "greedy_delta": round(r_delta, 4),
                    "shift": round(g_delta - r_delta, 4),
                }
            )

    return comparisons


def print_report(result, cell_comparisons):
    """Print formatted audit report to stdout."""
    print("=" * 70)
    print("E1 PLAY-POLICY CONFOUND AUDIT — SMOKE REPORT")
    print("=" * 70)

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        return

    print(f"\nBidders compared: {result['n_bidders']}")
    print(f"Spearman ρ: {result['spearman_rho']:.4f} (p={result['spearman_p']:.6f})")
    print(f"Verdict: {result['verdict']}")

    print("\n--- Per-Bidder Rankings ---")
    print(
        f"{'Bidder':<25} {'Glutton':>10} {'Greedy':>10} {'Δ':>10} "
        f"{'G_Rank':>7} {'R_Rank':>7} {'Shift':>6}"
    )
    print("-" * 80)
    for row in result["bidder_table"]:
        print(
            f"{row['bidder']:<25} {row['glutton_net_eppd']:>10.4f} "
            f"{row['greedy_net_eppd']:>10.4f} {row['delta']:>10.4f} "
            f"{row['glutton_rank']:>7d} {row['greedy_rank']:>7d} "
            f"{row['rank_change']:>+6d}"
        )

    if result["ranking_inversions"]:
        print(f"\nRanking inversions ({len(result['ranking_inversions'])}):")
        for a, b in result["ranking_inversions"]:
            print(f"  {a} vs {b}")
    else:
        print("\nNo ranking inversions detected.")

    print(f"\nTop-4 (glutton): {result['top4_glutton']}")
    print(f"Top-4 (greedy):  {result['top4_greedy']}")
    print(f"Top-4 set match: {result['top4_set_match']}")

    if cell_comparisons:
        shifts = [c["shift"] for c in cell_comparisons]
        print("\n--- Cell-Level Shifts ---")
        print(f"Cells compared: {len(shifts)}")
        print(f"Mean shift (glutton - greedy): {np.mean(shifts):+.4f}")
        print(f"Median shift: {np.median(shifts):+.4f}")
        print(f"Max |shift|: {max(abs(s) for s in shifts):.4f}")
        print(f"Std shift: {np.std(shifts):.4f}")

    print("\n" + "=" * 70)
    print(f"VERDICT: {result['verdict']}")
    if result["verdict"] == "STABLE":
        print("Confound is cosmetic — rankings stable across play policies.")
        print("Proceed to Track B without label retraining.")
    else:
        print("Rankings shift across play policies — proceed to Quick tier.")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="E1 Play-Policy Confound Audit — compare rankings"
    )
    parser.add_argument(
        "--glutton",
        required=True,
        help="Path to glutton H2H battery summary JSON",
    )
    parser.add_argument(
        "--greedy",
        required=True,
        help="Path to greedy H2H battery summary JSON",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path for JSON audit report",
    )
    args = parser.parse_args()

    glutton_path = Path(args.glutton)
    greedy_path = Path(args.greedy)

    if not glutton_path.exists():
        print(f"ERROR: Glutton summary not found: {glutton_path}", file=sys.stderr)
        sys.exit(1)
    if not greedy_path.exists():
        print(f"ERROR: Greedy summary not found: {greedy_path}", file=sys.stderr)
        sys.exit(1)

    glutton_data = json.loads(glutton_path.read_text())
    greedy_data = json.loads(greedy_path.read_text())

    glutton_rankings = extract_rankings(glutton_data)
    greedy_rankings = extract_rankings(greedy_data)

    result = compare_rankings(glutton_rankings, greedy_rankings)
    cell_comparisons = compare_cells(glutton_data, greedy_data)

    print_report(result, cell_comparisons)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audit = {
            "audit_type": "e1_play_policy_confound",
            "glutton_source": str(glutton_path),
            "greedy_source": str(greedy_path),
            "rankings": result,
            "cell_comparisons": cell_comparisons,
        }
        output_path.write_text(json.dumps(audit, indent=2) + "\n")
        print(f"\nAudit JSON written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
