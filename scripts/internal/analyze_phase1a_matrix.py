#!/usr/bin/env python
"""
Phase 1A: 2×2 Model×Label matrix analysis.

Parses H2H battery results and produces the decomposition table:
  {OLS, GBT} × {N=1, N=20} + Hybrid R0 incumbent.

Computes per-cell metrics: pooled net_eppd delta vs R0, per-contract deltas,
behavioral profiles, and the critical B vs C comparison.

Usage:
    PYTHONPATH=src uv run python scripts/internal/analyze_phase1a_matrix.py \
        --run-dir data/runs/<run_id> \
        --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Bootstrap CI
# ---------------------------------------------------------------------------


def bootstrap_ci(deltas, n_bootstrap=10000, ci=0.95, seed=42):
    """Bootstrap percentile CI on mean of deltas."""
    rng = np.random.default_rng(seed)
    arr = np.array(deltas, dtype=float)
    n = len(arr)
    if n < 2:
        m = float(np.mean(arr)) if n > 0 else 0.0
        return m, m
    boot = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        boot[i] = np.mean(rng.choice(arr, size=n, replace=True))
    alpha = (1 - ci) / 2
    return float(np.percentile(boot, 100 * alpha)), float(
        np.percentile(boot, 100 * (1 - alpha))
    )


# ---------------------------------------------------------------------------
# Parse JSONL logs
# ---------------------------------------------------------------------------


def parse_hand_end_records(run_dir: Path) -> dict[str, list[dict]]:
    """Parse hand_end events from JSONL log files, grouped by matchup_id."""
    matchup_records: dict[str, list[dict]] = defaultdict(list)
    jsonl_files = sorted(run_dir.glob("**/*.jsonl"))
    if not jsonl_files:
        print(f"WARNING: No JSONL files in {run_dir}", file=sys.stderr)
        return matchup_records

    for path in jsonl_files:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("event") != "hand_end":
                    continue
                mid = rec.get("matchup_id") or rec.get("strategy_id", "")
                matchup_records[mid].append(rec)

    return matchup_records


def compute_team_points(rec: dict) -> tuple[float, float]:
    """Compute (team0_points, team1_points) from a hand_end record."""
    t0 = rec.get("t0", 0)
    t1 = rec.get("t1", 0)
    bp = rec.get("bidder_position")
    winning_bid = rec.get("winning_bid", 0)
    made_bid = rec.get("made_bid", True)

    if bp is None:
        return (t0, t1)

    if bp in (0, 2):
        team0_pts = t0 if made_bid else -winning_bid
        team1_pts = t1
    else:
        team0_pts = t0
        team1_pts = t1 if made_bid else -winning_bid
    return (team0_pts, team1_pts)


# ---------------------------------------------------------------------------
# Per-matchup analysis
# ---------------------------------------------------------------------------


def analyze_matchup(
    fwd_records: list[dict],
    rev_records: list[dict],
    seed: int = 42,
) -> dict:
    """Analyze a bidder-pair from both rotations.

    fwd_records: bidder A on seats 0,2 (team0)
    rev_records: bidder A on seats 1,3 (team1)

    Returns dict with pooled delta (A-B), per-contract deltas, CIs,
    behavioral stats.
    """
    deltas_all = []
    contract_deltas: dict[str, list[float]] = defaultdict(list)

    # Behavioral stats for bidder A
    a_bids = 0
    a_makes = 0
    a_bid_levels = []
    n_deals = 0

    for rec in fwd_records:
        t0, t1 = compute_team_points(rec)
        delta = t0 - t1  # A is team0
        deltas_all.append(delta)

        ct = rec.get("contract") or rec.get("contract_type", "suit")
        if ct:
            contract_deltas[ct].append(delta)

        bp = rec.get("bidder_position")
        if bp is not None:
            if bp in (0, 2):  # A declared
                a_bids += 1
                if rec.get("made_bid", False):
                    a_makes += 1
                a_bid_levels.append(rec.get("winning_bid", 4))

        n_deals += 1

    for rec in rev_records:
        t0, t1 = compute_team_points(rec)
        delta = t1 - t0  # A is team1
        deltas_all.append(delta)

        ct = rec.get("contract") or rec.get("contract_type", "suit")
        if ct:
            contract_deltas[ct].append(delta)

        bp = rec.get("bidder_position")
        if bp is not None:
            if bp in (1, 3):  # A declared
                a_bids += 1
                if rec.get("made_bid", False):
                    a_makes += 1
                a_bid_levels.append(rec.get("winning_bid", 4))

        n_deals += 1

    pooled_delta = float(np.mean(deltas_all)) if deltas_all else 0.0
    ci_low, ci_high = bootstrap_ci(deltas_all, seed=seed)

    per_contract = {}
    for ct in ("suit", "high", "low"):
        vals = contract_deltas.get(ct, [])
        if vals:
            per_contract[ct] = {
                "delta": float(np.mean(vals)),
                "ci": bootstrap_ci(vals, seed=seed),
                "n": len(vals),
            }

    make_rate = a_makes / a_bids if a_bids > 0 else 0.0
    avg_bid = float(np.mean(a_bid_levels)) if a_bid_levels else 0.0

    return {
        "pooled_delta": pooled_delta,
        "ci_low": ci_low,
        "ci_high": ci_high,
        "per_contract": per_contract,
        "n_deals": n_deals,
        "make_rate": make_rate,
        "avg_bid": avg_bid,
        "a_bids": a_bids,
    }


def analyze_self_play(records: list[dict], seed: int = 42) -> dict:
    """Analyze self-play matchup for sanity check."""
    deltas = []
    bid_levels = []
    n_pass = 0
    n_bids = 0
    n_makes = 0

    for rec in records:
        t0, t1 = compute_team_points(rec)
        deltas.append(t0 - t1)

        bp = rec.get("bidder_position")
        if bp is not None:
            n_bids += 1
            if rec.get("made_bid", False):
                n_makes += 1
            bid_levels.append(rec.get("winning_bid", 4))
        else:
            n_pass += 1

    net_eppd = float(np.mean(deltas)) if deltas else 0.0
    ci_low, ci_high = bootstrap_ci(deltas, seed=seed)

    return {
        "net_eppd": net_eppd,
        "ci": (ci_low, ci_high),
        "n_deals": len(records),
        "make_rate": n_makes / n_bids if n_bids > 0 else 0.0,
        "avg_bid": float(np.mean(bid_levels)) if bid_levels else 0.0,
        "pass_rate": n_pass / len(records) if records else 0.0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

CELLS = {
    "cell_a_ols_n1": {"model": "OLS", "labels": "N=1"},
    "cell_b_ols_n20": {"model": "OLS", "labels": "N=20"},
    "cell_c_gbt_n1": {"model": "GBT", "labels": "N=1"},
    "cell_d_gbt_n20": {"model": "GBT", "labels": "N=20"},
}

CELL_NAMES = list(CELLS.keys())
R0 = "hybrid_r0"


def main():
    parser = argparse.ArgumentParser(description="Phase 1A matrix analysis")
    parser.add_argument("--run-dir", required=True, help="Experiment run directory")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", help="Output JSON path (optional)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        # Try finding the latest run matching the pattern
        parent = run_dir.parent
        candidates = sorted(parent.glob(f"{run_dir.name}*"))
        if candidates:
            run_dir = candidates[-1]
            print(f"Using run dir: {run_dir}")
        else:
            print(f"ERROR: Run dir not found: {run_dir}", file=sys.stderr)
            sys.exit(1)

    records = parse_hand_end_records(run_dir)
    available = sorted(records.keys())
    print(f"Found {len(available)} matchups: {available[:5]}...")

    # === Self-play sanity ===
    print("\n=== Self-Play Sanity Checks ===")
    print(
        f"{'Bidder':<25} {'net_eppd':>10} {'CI':>22} {'avg_bid':>8} {'make%':>7} {'pass%':>7}"
    )
    self_play_results = {}
    for cell in CELL_NAMES + [R0]:
        sp_key = f"{cell}_self_play"
        sp_recs = records.get(sp_key, [])
        if sp_recs:
            sp = analyze_self_play(sp_recs, seed=args.seed)
            self_play_results[cell] = sp
            print(
                f"{cell:<25} {sp['net_eppd']:>+10.3f} "
                f"[{sp['ci'][0]:>+.3f}, {sp['ci'][1]:>+.3f}] "
                f"{sp['avg_bid']:>8.2f} {sp['make_rate']*100:>6.1f}% "
                f"{sp['pass_rate']*100:>6.1f}%"
            )

    # === vs R0 comparisons ===
    print("\n=== vs Hybrid R0 (Incumbent) ===")
    print(
        f"{'Cell':<25} {'Pooled':>8} {'CI':>22} "
        f"{'Suit':>8} {'High':>8} {'Low':>8} "
        f"{'avg_bid':>8} {'make%':>7}"
    )
    vs_r0 = {}
    for cell in CELL_NAMES:
        fwd_key = f"{cell}_vs_{R0}"
        rev_key = f"{R0}_vs_{cell}"
        fwd = records.get(fwd_key, [])
        rev = records.get(rev_key, [])
        if fwd or rev:
            result = analyze_matchup(fwd, rev, seed=args.seed)
            vs_r0[cell] = result
            suit = result["per_contract"].get("suit", {}).get("delta", 0)
            high = result["per_contract"].get("high", {}).get("delta", 0)
            low = result["per_contract"].get("low", {}).get("delta", 0)
            print(
                f"{cell:<25} {result['pooled_delta']:>+8.3f} "
                f"[{result['ci_low']:>+.3f}, {result['ci_high']:>+.3f}] "
                f"{suit:>+8.3f} {high:>+8.3f} {low:>+8.3f} "
                f"{result['avg_bid']:>8.2f} {result['make_rate']*100:>6.1f}%"
            )

    # === Key cross-comparisons ===
    print("\n=== Key Cross-Comparisons ===")
    print(
        f"{'Comparison':<40} {'Delta':>8} {'CI':>22} "
        f"{'Suit':>8} {'High':>8} {'Low':>8}"
    )

    cross_comparisons = [
        ("B vs A (label effect, OLS)", "cell_b_ols_n20", "cell_a_ols_n1"),
        ("C vs A (model effect)", "cell_c_gbt_n1", "cell_a_ols_n1"),
        ("D vs C (label effect, GBT)", "cell_d_gbt_n20", "cell_c_gbt_n1"),
        ("B vs C (labels > model?)", "cell_b_ols_n20", "cell_c_gbt_n1"),
        ("D vs B (GBT+N20 vs OLS+N20)", "cell_d_gbt_n20", "cell_b_ols_n20"),
        ("D vs A (full interaction)", "cell_d_gbt_n20", "cell_a_ols_n1"),
    ]

    cross_results = {}
    for label, a, b in cross_comparisons:
        fwd_key = f"{a}_vs_{b}"
        rev_key = f"{b}_vs_{a}"
        fwd = records.get(fwd_key, [])
        rev = records.get(rev_key, [])
        if fwd or rev:
            result = analyze_matchup(fwd, rev, seed=args.seed)
            cross_results[label] = result
            suit = result["per_contract"].get("suit", {}).get("delta", 0)
            high = result["per_contract"].get("high", {}).get("delta", 0)
            low = result["per_contract"].get("low", {}).get("delta", 0)
            print(
                f"{label:<40} {result['pooled_delta']:>+8.3f} "
                f"[{result['ci_low']:>+.3f}, {result['ci_high']:>+.3f}] "
                f"{suit:>+8.3f} {high:>+8.3f} {low:>+8.3f}"
            )

    # === 2×2 Decomposition ===
    print("\n=== 2×2 Effect Decomposition (vs R0) ===")
    cell_a = vs_r0.get("cell_a_ols_n1", {}).get("pooled_delta", 0)
    cell_b = vs_r0.get("cell_b_ols_n20", {}).get("pooled_delta", 0)
    cell_c = vs_r0.get("cell_c_gbt_n1", {}).get("pooled_delta", 0)
    cell_d = vs_r0.get("cell_d_gbt_n20", {}).get("pooled_delta", 0)

    label_effect_ols = cell_b - cell_a
    label_effect_gbt = cell_d - cell_c
    model_effect_n1 = cell_c - cell_a
    model_effect_n20 = cell_d - cell_b
    interaction = (cell_d - cell_c) - (cell_b - cell_a)

    print(f"  Cell A (OLS, N=1):  {cell_a:>+.3f}")
    print(f"  Cell B (OLS, N=20): {cell_b:>+.3f}")
    print(f"  Cell C (GBT, N=1):  {cell_c:>+.3f}")
    print(f"  Cell D (GBT, N=20): {cell_d:>+.3f}")
    print()
    print(f"  Label effect (OLS):  B-A = {label_effect_ols:>+.3f}")
    print(f"  Label effect (GBT):  D-C = {label_effect_gbt:>+.3f}")
    print(f"  Model effect (N=1):  C-A = {model_effect_n1:>+.3f}")
    print(f"  Model effect (N=20): D-B = {model_effect_n20:>+.3f}")
    print(f"  Interaction:         {interaction:>+.3f}")

    # === Gate checks ===
    print("\n=== Phase 1A Gate Checks ===")
    best_cell = max(vs_r0.items(), key=lambda x: x[1].get("pooled_delta", -99))
    best_name, best = best_cell
    best_ci_low = best.get("ci_low", 0)

    print(f"  Best candidate: {best_name}")
    print(
        f"  Pooled delta vs R0: {best['pooled_delta']:>+.3f} [{best_ci_low:>+.3f}, {best.get('ci_high', 0):>+.3f}]"
    )
    print(
        f"  CI_low > 0 (statistically positive): {'PASS' if best_ci_low > 0 else 'FAIL'}"
    )

    best_suit = best.get("per_contract", {}).get("suit", {}).get("delta", -99)
    print(f"  Suit delta: {best_suit:>+.3f}")
    print(
        f"  Suit delta > -0.092 (improved from -0.142): {'PASS' if best_suit > -0.092 else 'FAIL'}"
    )
    print(
        f"  Suit delta > 0 (regression resolved): {'PASS' if best_suit > 0 else 'FAIL'}"
    )

    # === Output JSON ===
    if args.output:
        output = {
            "self_play": self_play_results,
            "vs_r0": {
                k: {
                    "pooled_delta": v["pooled_delta"],
                    "ci_low": v["ci_low"],
                    "ci_high": v["ci_high"],
                    "per_contract": {
                        ct: {"delta": d["delta"], "ci": d["ci"], "n": d["n"]}
                        for ct, d in v.get("per_contract", {}).items()
                    },
                    "make_rate": v["make_rate"],
                    "avg_bid": v["avg_bid"],
                }
                for k, v in vs_r0.items()
            },
            "cross_comparisons": {
                k: {
                    "pooled_delta": v["pooled_delta"],
                    "ci_low": v["ci_low"],
                    "ci_high": v["ci_high"],
                    "per_contract": {
                        ct: {"delta": d["delta"], "ci": d["ci"], "n": d["n"]}
                        for ct, d in v.get("per_contract", {}).items()
                    },
                }
                for k, v in cross_results.items()
            },
            "decomposition": {
                "cell_a": cell_a,
                "cell_b": cell_b,
                "cell_c": cell_c,
                "cell_d": cell_d,
                "label_effect_ols": label_effect_ols,
                "label_effect_gbt": label_effect_gbt,
                "model_effect_n1": model_effect_n1,
                "model_effect_n20": model_effect_n20,
                "interaction": interaction,
            },
            "gate_checks": {
                "best_candidate": best_name,
                "pooled_ci_low_gt_0": best_ci_low > 0,
                "suit_delta_gt_neg_092": best_suit > -0.092,
                "suit_delta_gt_0": best_suit > 0,
            },
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(output, indent=2, default=str))
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
