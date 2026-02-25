#!/usr/bin/env python
"""Calibrate Arc D promotion gate thresholds from H2H null signal.

Reads H2H battery summary, extracts null signal from self-play diagonals
and seat-swap symmetry residuals, then calibrates delta_floor and
regression_threshold from quantiles of the null distribution.

Usage:
    PYTHONPATH=src uv run python scripts/internal/calibrate_arc_d_thresholds.py \
        --h2h-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
        --seed 42 \
        --output data/artifacts/arc_d/r0/gate_thresholds_r1.json

Optional drift check (compare QUICK calibration against FULL data):
    PYTHONPATH=src uv run python scripts/internal/calibrate_arc_d_thresholds.py \
        --h2h-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
        --full-summary data/artifacts/arc_d/r0/h2h_battery_full.json \
        --seed 42 \
        --output data/artifacts/arc_d/r0/gate_thresholds_r1.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np


def extract_null_signal(h2h_summary: dict) -> dict:
    """Extract null signal from H2H battery summary.

    The null distribution is composed of two sources:
    1. Self-play net_eppd values (should be ~0 for each bidder).
    2. Seat-swap symmetry residuals: for each pair (A, B),
       |delta(A_vs_B) + delta(B_vs_A)| should be ~0 if seat effects cancel.

    Args:
        h2h_summary: Loaded H2H battery summary JSON dict.
            Expected structure: {"cells": {key: {...}}} or {"matchups": {key: {...}}}
            where key is "bidderA_vs_bidderB".

    Returns:
        Dict with null_abs_values, self_play_deltas, seat_swap_residuals.
    """
    matchups = h2h_summary.get("cells", h2h_summary.get("matchups", {}))

    # 1. Self-play deltas: bidder_vs_bidder (diagonal)
    self_play_deltas: list[float] = []
    bidder_names: set[str] = set()

    for key, data in matchups.items():
        parts = key.split("_vs_")
        if len(parts) == 2:
            bidder_names.add(parts[0])
            bidder_names.add(parts[1])
            if parts[0] == parts[1]:
                delta = data.get("net_eppd_delta", 0.0)
                self_play_deltas.append(delta)

    # 2. Seat-swap symmetry residuals
    seat_swap_residuals: list[float] = []
    for a, b in combinations(sorted(bidder_names), 2):
        key_ab = f"{a}_vs_{b}"
        key_ba = f"{b}_vs_{a}"
        if key_ab in matchups and key_ba in matchups:
            delta_ab = matchups[key_ab].get("net_eppd_delta", 0.0)
            delta_ba = matchups[key_ba].get("net_eppd_delta", 0.0)
            residual = abs(delta_ab + delta_ba)
            seat_swap_residuals.append(residual)

    # Combine into null_abs array
    null_abs = [abs(d) for d in self_play_deltas] + seat_swap_residuals

    return {
        "null_abs_values": null_abs,
        "self_play_deltas": self_play_deltas,
        "seat_swap_residuals": seat_swap_residuals,
    }


def extract_cvar5_null(h2h_summary: dict) -> dict:
    """Extract CVaR-5 null signal from H2H battery self-play cells.

    For each self-play cell, extract cvar_5 value. Compute pairwise
    residuals between self-play cvar_5 values.

    Args:
        h2h_summary: Loaded H2H battery summary JSON dict.

    Returns:
        Dict with cvar5_residuals and cvar5_residual_std.
    """
    matchups = h2h_summary.get("cells", h2h_summary.get("matchups", {}))

    # Collect self-play cvar_5 values
    self_play_cvar5: dict[str, float] = {}
    for key, data in matchups.items():
        parts = key.split("_vs_")
        if len(parts) == 2 and parts[0] == parts[1]:
            cvar5 = data.get("cvar_5", 0.0)
            self_play_cvar5[parts[0]] = cvar5

    # Compute pairwise residuals
    cvar5_residuals: list[float] = []
    bidders = sorted(self_play_cvar5.keys())
    for a, b in combinations(bidders, 2):
        residual = self_play_cvar5[a] - self_play_cvar5[b]
        cvar5_residuals.append(residual)

    if len(cvar5_residuals) >= 2:
        cvar5_residual_std = float(np.std(cvar5_residuals, ddof=1))
    elif len(cvar5_residuals) == 1:
        cvar5_residual_std = abs(cvar5_residuals[0])
    else:
        cvar5_residual_std = 0.0

    return {
        "cvar5_residuals": cvar5_residuals,
        "cvar5_residual_std": cvar5_residual_std,
    }


def calibrate_thresholds(null_signal: dict, cvar5_null: dict, seed: int) -> dict:
    """Calibrate gate thresholds from null signal quantiles.

    Args:
        null_signal: Output from extract_null_signal().
        cvar5_null: Output from extract_cvar5_null().
        seed: RNG seed (recorded for provenance, not used in computation).

    Returns:
        Dict with calibrated thresholds and details.
    """
    null_abs = np.array(null_signal["null_abs_values"])

    if len(null_abs) == 0:
        raise ValueError("No null signal values found; cannot calibrate thresholds")

    q95 = float(np.percentile(null_abs, 95))
    q99 = float(np.percentile(null_abs, 99))

    delta_floor = max(0.01, q95)
    regression_threshold = max(0.05, q99)

    cvar5_tolerance = max(0.05, 2.0 * cvar5_null["cvar5_residual_std"])

    # Self-play delta std for diagnostic
    self_play_deltas = null_signal["self_play_deltas"]
    if len(self_play_deltas) >= 2:
        self_play_std = float(np.std(self_play_deltas, ddof=1))
    elif len(self_play_deltas) == 1:
        self_play_std = abs(self_play_deltas[0])
    else:
        self_play_std = 0.0

    # Seat-swap residual std
    seat_swap_residuals = null_signal["seat_swap_residuals"]
    if len(seat_swap_residuals) >= 2:
        seat_swap_std = float(np.std(seat_swap_residuals, ddof=1))
    elif len(seat_swap_residuals) == 1:
        seat_swap_std = seat_swap_residuals[0]
    else:
        seat_swap_std = 0.0

    return {
        "schema": "gate_thresholds_v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "calibration_source": None,  # Filled by caller
        "calibration_method": "null_distribution_quantiles",
        "seed": seed,
        "thresholds": {
            "delta_floor": round(delta_floor, 6),
            "regression_threshold": round(regression_threshold, 6),
            "cvar5_tolerance": round(cvar5_tolerance, 6),
            "bid_rate_min": 0.05,
            "bid_rate_max": 0.95,
            "make_rate_min": 0.45,
            "downside_variance_ratio": 1.10,
        },
        "calibration_details": {
            "null_abs_values": [round(v, 8) for v in null_abs.tolist()],
            "q95_null_abs": round(q95, 8),
            "q99_null_abs": round(q99, 8),
            "self_play_net_eppd_std": round(self_play_std, 8),
            "seat_swap_residual_std": round(seat_swap_std, 8),
            "null_distribution_n": len(null_abs),
            "self_play_cvar5_residuals": [
                round(v, 8) for v in cvar5_null["cvar5_residuals"]
            ],
            "cvar5_residual_std": round(cvar5_null["cvar5_residual_std"], 8),
            "drift_check": None,
        },
    }


def drift_check(quick_thresholds: dict, full_summary: dict) -> dict:
    """Check calibration drift between QUICK and FULL data.

    Re-derives null quantiles from FULL data and compares to QUICK-derived
    thresholds. Reports drift ratio and whether recalibration is needed.

    Args:
        quick_thresholds: Output from calibrate_thresholds() (QUICK data).
        full_summary: Loaded H2H battery summary from FULL data.

    Returns:
        Dict with drift_ratio, q95_full, and needs_recalibration flag.
    """
    full_null = extract_null_signal(full_summary)
    full_null_abs = np.array(full_null["null_abs_values"])

    if len(full_null_abs) == 0:
        return {"drift_ratio": 0.0, "q95_full": 0.0, "needs_recalibration": False}

    q95_full = float(np.percentile(full_null_abs, 95))
    q95_quick = quick_thresholds["calibration_details"]["q95_null_abs"]

    if q95_quick > 0:
        drift_ratio = abs(q95_full - q95_quick) / q95_quick
    else:
        drift_ratio = 0.0

    return {
        "drift_ratio": round(drift_ratio, 6),
        "q95_full": round(q95_full, 8),
        "needs_recalibration": drift_ratio > 0.25,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate Arc D promotion gate thresholds from H2H null signal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--h2h-summary",
        type=str,
        required=True,
        help="Path to H2H battery summary JSON",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for provenance (default: 42)",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output path for gate thresholds JSON",
    )
    parser.add_argument(
        "--full-summary",
        type=str,
        default=None,
        help="Optional FULL H2H summary for drift check",
    )
    args = parser.parse_args()

    # Load H2H summary
    h2h_path = Path(args.h2h_summary)
    if not h2h_path.exists():
        print(f"Error: H2H summary not found: {h2h_path}", file=sys.stderr)
        sys.exit(1)

    with open(h2h_path) as f:
        h2h_summary = json.load(f)

    # Extract null signal
    null_signal = extract_null_signal(h2h_summary)
    cvar5_null = extract_cvar5_null(h2h_summary)

    if len(null_signal["null_abs_values"]) == 0:
        print(
            "Error: No null signal values extracted. "
            "Check H2H summary format (needs 'cells' or 'matchups' with 'X_vs_X' keys).",
            file=sys.stderr,
        )
        sys.exit(1)

    # Calibrate
    thresholds = calibrate_thresholds(null_signal, cvar5_null, args.seed)
    thresholds["calibration_source"] = str(h2h_path.name)

    # Optional drift check
    if args.full_summary:
        full_path = Path(args.full_summary)
        if not full_path.exists():
            print(f"Error: FULL summary not found: {full_path}", file=sys.stderr)
            sys.exit(1)
        with open(full_path) as f:
            full_summary = json.load(f)

        drift_result = drift_check(thresholds, full_summary)
        thresholds["calibration_details"]["drift_check"] = drift_result

        if drift_result["needs_recalibration"]:
            print(
                f"Drift ratio {drift_result['drift_ratio']:.3f} > 0.25 "
                f"-- recalibrating from FULL data.",
                file=sys.stderr,
            )
            # Recalibrate from FULL data
            full_null_signal = extract_null_signal(full_summary)
            full_cvar5_null = extract_cvar5_null(full_summary)
            thresholds = calibrate_thresholds(
                full_null_signal, full_cvar5_null, args.seed
            )
            thresholds["calibration_source"] = str(full_path.name)
            thresholds["calibration_details"]["drift_check"] = drift_result
            thresholds["calibration_details"]["recalibrated_from"] = "FULL"

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(thresholds, f, indent=2)

    print(f"Gate thresholds written to: {output_path}")
    print(f"  delta_floor:          {thresholds['thresholds']['delta_floor']}")
    print(f"  regression_threshold: {thresholds['thresholds']['regression_threshold']}")
    print(f"  cvar5_tolerance:      {thresholds['thresholds']['cvar5_tolerance']}")
    print(
        f"  null_distribution_n:  "
        f"{thresholds['calibration_details']['null_distribution_n']}"
    )


if __name__ == "__main__":
    main()
