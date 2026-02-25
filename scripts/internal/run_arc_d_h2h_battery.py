#!/usr/bin/env python
"""
H2H battery runner for Arc D competitive validation.

Generates all-vs-all matchups from a bidder roster, runs them via the canonical
experiment runner in head_to_head_matrix mode, and produces a normalized summary JSON.

Two-phase workflow:
  QUICK: All 49 matchups at n_per=2000
  FULL:  Subset of matchups at n_per=10000 (cells involving key bidders + CI-crosses-zero)

Usage:
    PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
        --mode QUICK --seed 42 --n-per 2000 \
        --output data/artifacts/arc_d/r0/h2h_battery_quick.json

    PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
        --mode FULL --seed 42 --n-per 10000 \
        --quick-summary data/artifacts/arc_d/r0/h2h_battery_quick.json \
        --output data/artifacts/arc_d/r0/h2h_battery_full.json

    # Config-only mode (generate YAML without running):
    PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
        --mode QUICK --seed 42 --n-per 2000 \
        --output data/artifacts/arc_d/r0/h2h_battery_quick.json \
        --config-only

    # Parse an existing run into summary:
    PYTHONPATH=src uv run python scripts/internal/run_arc_d_h2h_battery.py \
        --mode QUICK --seed 42 --n-per 2000 \
        --output data/artifacts/arc_d/r0/h2h_battery_quick.json \
        --parse-run data/runs/<run_id>
"""

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Default roster: 7 bidders for all-vs-all battery
# ---------------------------------------------------------------------------

DEFAULT_ROSTER = [
    {
        "name": "hybrid_olsa",
        "class_name": "HybridOLSaBidder",
        "params": {"artifact_path": "data/artifacts/arc_d/r0/hybrid_r0.json"},
    },
    {
        "name": "olsa",
        "class_name": "OLSaBidder",
        "params": {"artifact_path": "data/artifacts/arc_d/r0/hybrid_r0.json"},
    },
    {
        "name": "olsa_full",
        "class_name": "OLSaBidder",
        "params": {"artifact_path": "data/artifacts/arc_d/r0/hybrid_r0_full.json"},
    },
    {"name": "modeloespecifico", "class_name": "ModeloEspecifico"},
    {
        "name": "fiveheadfred",
        "class_name": "FixedBidder",
        "params": {"n": 5, "contract": "S"},
    },
    {"name": "stricthellraiser", "class_name": "StrictHellRaiser"},
    {"name": "rankthetank", "class_name": "RanktheTank"},
]

# Key bidders always included in FULL subset
KEY_BIDDERS = {"hybrid_olsa", "olsa", "olsa_full"}


# ---------------------------------------------------------------------------
# Matchup generation
# ---------------------------------------------------------------------------


def generate_matchups(roster):
    """Generate all-vs-all matchups from a bidder roster.

    For N bidders, produces:
      - N self-play matchups
      - C(N,2) * 2 cross-matchups (both seat rotations)
      = N + N*(N-1) = N^2 total matchups

    Parameters
    ----------
    roster : list[dict]
        Bidder roster entries with at minimum a ``name`` key.

    Returns
    -------
    list[dict]
        Matchup dicts suitable for experiment YAML config.
    """
    matchups = []
    names = [r["name"] for r in roster]

    for i, a_name in enumerate(names):
        for j, b_name in enumerate(names):
            if j < i:
                # Only generate for i <= j; reverse rotation handled below
                continue

            if a_name == b_name:
                # Self-play
                matchups.append(
                    {
                        "matchup_id": f"{a_name}_self_play",
                        "bidder_a": a_name,
                        "bidder_b": b_name,
                        "seat_bidding_policies": [
                            a_name,
                            a_name,
                            a_name,
                            a_name,
                        ],
                        "team0": "glutton",
                        "team1": "glutton",
                    }
                )
            else:
                # Rotation 1: a as seats 0,2
                matchups.append(
                    {
                        "matchup_id": f"{a_name}_vs_{b_name}",
                        "bidder_a": a_name,
                        "bidder_b": b_name,
                        "seat_bidding_policies": [
                            a_name,
                            b_name,
                            a_name,
                            b_name,
                        ],
                        "team0": "glutton",
                        "team1": "glutton",
                    }
                )
                # Rotation 2: b as seats 0,2
                matchups.append(
                    {
                        "matchup_id": f"{b_name}_vs_{a_name}",
                        "bidder_a": b_name,
                        "bidder_b": a_name,
                        "seat_bidding_policies": [
                            b_name,
                            a_name,
                            b_name,
                            a_name,
                        ],
                        "team0": "glutton",
                        "team1": "glutton",
                    }
                )

    return matchups


def generate_h2h_config(roster, matchups, seed, n_per):
    """Generate a YAML-serializable config dict for H2H battery.

    Parameters
    ----------
    roster : list[dict]
        Bidder roster entries.
    matchups : list[dict]
        Matchup definitions from ``generate_matchups``.
    seed : int
        RNG seed.
    n_per : int
        Deals per matchup.

    Returns
    -------
    dict
        Config dict suitable for YAML serialization and experiment runner.
    """
    # Build bidding_policies from roster
    bidding_policies = []
    for entry in roster:
        policy = {"name": entry["name"], "class_name": entry["class_name"]}
        if "params" in entry:
            policy["params"] = entry["params"]
        bidding_policies.append(policy)

    # Build matchups for YAML (strip internal keys like bidder_a/bidder_b)
    yaml_matchups = []
    for m in matchups:
        yaml_matchups.append(
            {
                "matchup_id": m["matchup_id"],
                "team0": m["team0"],
                "team1": m["team1"],
                "seat_bidding_policies": m["seat_bidding_policies"],
            }
        )

    config = {
        "experiment_name": "arc_d_r0_h2h_battery",
        "parameters": {
            "seed": seed,
            "n_per": n_per,
            "log_level": "hand",
            "mode": "head_to_head_matrix",
            "pair_deals": True,
        },
        "strategies": [{"name": "glutton", "class_name": "GluttonStrategy"}],
        "bidding_policies": bidding_policies,
        "matchups": yaml_matchups,
        "scenarios": [{"contract_type": None}],
    }

    return config


# ---------------------------------------------------------------------------
# FULL-mode subset selection
# ---------------------------------------------------------------------------


def select_full_subset(quick_summary, roster):
    """Select matchups for FULL mode from QUICK results.

    Selection criteria:
    1. Always include cells involving KEY_BIDDERS.
    2. Include any cross-matchup cell where CI crosses zero
       (ci_low < 0 < ci_high for net_eppd_delta).

    Parameters
    ----------
    quick_summary : dict
        QUICK battery summary (h2h_battery_v1 schema).
    roster : list[dict]
        Full bidder roster.

    Returns
    -------
    set[str]
        Set of matchup_ids to include in FULL run.
    """
    selected = set()
    cells = quick_summary.get("cells", {})

    for matchup_id, cell in cells.items():
        bidder_a = cell.get("bidder_a", "")
        bidder_b = cell.get("bidder_b", "")

        # Criterion 1: involves a key bidder
        if bidder_a in KEY_BIDDERS or bidder_b in KEY_BIDDERS:
            selected.add(matchup_id)
            continue

        # Criterion 2: CI crosses zero (for cross-matchups only)
        ci_low = cell.get("ci_low")
        ci_high = cell.get("ci_high")
        if ci_low is not None and ci_high is not None:
            if ci_low < 0 < ci_high:
                selected.add(matchup_id)

    return selected


# ---------------------------------------------------------------------------
# Summary parsing
# ---------------------------------------------------------------------------


def _get_git_sha():
    """Get current git SHA, or 'unknown' if not in a repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return "unknown"


def _config_sha(config_dict):
    """Compute SHA-256 of a config dict (deterministic JSON serialization)."""
    canonical = json.dumps(config_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def generate_summary(
    mode,
    seed,
    n_per,
    roster,
    matchups,
    config_dict,
    quick_source=None,
):
    """Generate a skeleton summary artifact (h2h_battery_v1 schema).

    This produces the schema structure with empty cell data. Actual metrics
    would be populated after parsing experiment run results.

    Parameters
    ----------
    mode : str
        "QUICK" or "FULL".
    seed : int
        RNG seed.
    n_per : int
        Deals per matchup.
    roster : list[dict]
        Bidder roster.
    matchups : list[dict]
        Matchup definitions.
    config_dict : dict
        The generated experiment config (for config_sha).
    quick_source : str or None
        Path to QUICK summary used for FULL subset selection.

    Returns
    -------
    dict
        Summary artifact in h2h_battery_v1 schema.
    """
    cfg_sha = _config_sha(config_dict)

    cells = {}
    for m in matchups:
        mid = m["matchup_id"]
        is_self_play = m["bidder_a"] == m["bidder_b"]
        cells[mid] = {
            "bidder_a": m["bidder_a"],
            "bidder_b": m["bidder_b"],
            "net_eppd_a": None,
            "net_eppd_b": None,
            "net_eppd_delta": None,
            "ci_low": None,
            "ci_high": None,
            "win_rate_a": 0.5 if is_self_play else None,
            "bid_rate_a": None,
            "bid_rate_b": None,
            "make_rate_a": None,
            "make_rate_b": None,
            "deals_total": n_per,
            "pair_deals": True,
            "run_id": None,
            "config_sha": cfg_sha,
            "matchup_id": mid,
        }

    return {
        "schema": "h2h_battery_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "seed": seed,
        "n_per": n_per,
        "roster": [r["name"] for r in roster],
        "cells": cells,
        "quick_source": quick_source,
        "provenance": {
            "script": "scripts/internal/run_arc_d_h2h_battery.py",
            "git_sha": _get_git_sha(),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="H2H battery runner for Arc D competitive validation"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["QUICK", "FULL"],
        help="Battery mode: QUICK (all matchups, lower n) or FULL (subset, higher n)",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument(
        "--n-per",
        type=int,
        default=None,
        help="Deals per matchup (default: 2000 for QUICK, 10000 for FULL)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output path for summary JSON artifact",
    )
    parser.add_argument(
        "--quick-summary",
        default=None,
        help="Path to QUICK summary JSON (for FULL subset selection)",
    )
    parser.add_argument(
        "--roster",
        default=None,
        help="Path to custom roster JSON file (default: built-in 7-bidder roster)",
    )
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Generate YAML config and exit (do not run experiment)",
    )
    parser.add_argument(
        "--parse-run",
        default=None,
        help="Path to existing run directory to parse into summary (not yet implemented)",
    )
    args = parser.parse_args()

    # Resolve n_per default
    if args.n_per is None:
        args.n_per = 2000 if args.mode == "QUICK" else 10000

    # Load roster
    if args.roster:
        roster_path = Path(args.roster)
        if not roster_path.exists():
            print(f"ERROR: Roster file not found: {roster_path}", file=sys.stderr)
            sys.exit(1)
        roster = json.loads(roster_path.read_text())
    else:
        roster = DEFAULT_ROSTER

    # Generate all matchups
    all_matchups = generate_matchups(roster)

    # For FULL mode, optionally filter to subset
    if args.mode == "FULL" and args.quick_summary:
        quick_path = Path(args.quick_summary)
        if not quick_path.exists():
            print(
                f"ERROR: QUICK summary not found: {quick_path}",
                file=sys.stderr,
            )
            sys.exit(1)
        quick_data = json.loads(quick_path.read_text())
        selected_ids = select_full_subset(quick_data, roster)
        matchups = [m for m in all_matchups if m["matchup_id"] in selected_ids]
        print(
            f"FULL subset: {len(matchups)} of {len(all_matchups)} matchups selected",
            file=sys.stderr,
        )
    else:
        matchups = all_matchups

    # Generate experiment config
    config = generate_h2h_config(roster, matchups, args.seed, args.n_per)

    # Write YAML config
    output_path = Path(args.output)
    config_path = output_path.parent / f"h2h_battery_{args.mode.lower()}_config.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"Config written to: {config_path}", file=sys.stderr)

    if args.config_only:
        print(
            f"\nTo run:\n  uv run python experiments/run_experiment.py "
            f"--config {config_path} --seed {args.seed}",
            file=sys.stderr,
        )
        sys.exit(0)

    if args.parse_run:
        print(
            "NOTE: --parse-run is a placeholder for future implementation.",
            file=sys.stderr,
        )
        print(
            "Run parsing requires JSONL log analysis matching evaluator.py logic.",
            file=sys.stderr,
        )
        sys.exit(0)

    # Generate summary artifact
    quick_source = args.quick_summary if args.mode == "FULL" else None
    summary = generate_summary(
        mode=args.mode,
        seed=args.seed,
        n_per=args.n_per,
        roster=roster,
        matchups=matchups,
        config_dict=config,
        quick_source=quick_source,
    )

    output_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Summary written to: {output_path}", file=sys.stderr)

    n_matchups = len(matchups)
    total_deals = n_matchups * args.n_per
    print(
        f"\n{args.mode} battery: {n_matchups} matchups x {args.n_per} deals = "
        f"{total_deals:,} total deals",
        file=sys.stderr,
    )
    print(
        f"\nTo run experiment:\n  uv run python experiments/run_experiment.py "
        f"--config {config_path} --seed {args.seed}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
