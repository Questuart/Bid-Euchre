"""
Post-train behavioral validation for action-value artifacts.

Runs a deterministic self-play screen (50 deals, seed=42) and checks that
the bidding behavior is sane. Designed to catch stale/broken artifacts
that produce pathological bids (e.g., always-bid-10, never-pass).

Thresholds are intentionally loose — they catch catastrophic failures,
not fine-grained quality regressions.

Exit codes:
    0: All checks passed
    1: One or more checks failed
    2: Error loading artifact or running simulation

Usage:
    uv run python scripts/internal/validate_action_value_artifact.py \\
        --artifact data/runs/av_gbt_42/action_value_gbt.json

    # Override number of deals or seed:
    uv run python scripts/internal/validate_action_value_artifact.py \\
        --artifact data/artifacts/arc_d/r1_5/action_value_full.json \\
        --n-deals 100 --seed 123

    # Allow zero pass rate (for bidders that legitimately never pass):
    uv run python scripts/internal/validate_action_value_artifact.py \\
        --artifact <path> --allow-zero-pass-rate
"""

import argparse
import json
import sys
from pathlib import Path

from bid_euchre.sim.hooks import BiddingDecisionEvent, SimulationHooks
from bid_euchre.sim.simulation import simulate_many_hands
from bid_euchre.strategy.bidding import (
    ActionValueBidder,
    GBTActionValueBidder,
    TwoStageActionValueBidder,
)

# ── Thresholds ──────────────────────────────────────────────
# Intentionally loose: catch pathological artifacts, not quality regressions.

THRESHOLD_AVG_BID = 7.0  # Upper bound — stale artifact had avg_bid=10.0
THRESHOLD_BID_10_RATE = 0.05  # Max 5% of winning bids at level 10
THRESHOLD_MAKE_RATE_LOW = 0.50  # Min make rate — below 50% means systematic overbidding
THRESHOLD_PASS_RATE_MIN = (
    0.0  # Min pass rate (action-level) — 0% requires --allow-zero-pass-rate
)

# R² thresholds for per-model quality warning (not blocking)
R2_WARNING_THRESHOLD = 0.30


def load_bidder(artifact_path: str) -> object:
    """Load the correct bidder class based on artifact schema."""
    with open(artifact_path) as f:
        artifact = json.load(f)

    schema = artifact.get("schema_version", "")
    if schema == "action_value_gbt_v1":
        return GBTActionValueBidder(artifact_path)
    elif schema == "action_value_olsa_v1":
        return ActionValueBidder(artifact_path)
    elif schema == "two_stage_action_value_v1":
        return TwoStageActionValueBidder(artifact_path)
    else:
        raise ValueError(f"Unknown artifact schema: {schema!r}")


def run_behavioral_screen(
    artifact_path: str,
    n_deals: int = 50,
    seed: int = 42,
    allow_zero_pass_rate: bool = False,
) -> dict:
    """Run self-play and collect behavioral metrics.

    Returns dict with metrics and list of (check_name, passed, detail) tuples.
    """
    bidder = load_bidder(artifact_path)

    # Track per-action pass rate via hooks
    action_counts = {"total": 0, "pass": 0}

    def on_bid_decision(event: BiddingDecisionEvent) -> None:
        action_counts["total"] += 1
        if event.bid_amount == 0:
            action_counts["pass"] += 1

    hooks = SimulationHooks(
        on_bidding_decision=on_bid_decision,
    )

    result = simulate_many_hands(
        n=n_deals,
        contract_type=None,  # auction mode
        seed=seed,
        bidding_policies=[bidder, bidder, bidder, bidder],
        hooks=hooks,
    )

    bp = result.get("bidding_points", {})
    hands_with_bids = bp.get("hands_with_bids", 0)

    # Compute metrics
    if hands_with_bids > 0:
        avg_bid = bp["avg_bid"]
        make_rate = bp["make_rate"]
        bid_dist = bp.get("bid_distribution", {})
        bid_10_count = bid_dist.get(10, 0)
        bid_10_rate = bid_10_count / hands_with_bids
    else:
        avg_bid = 0.0
        make_rate = 0.0
        bid_10_rate = 0.0

    total_actions = action_counts["total"]
    pass_actions = action_counts["pass"]
    pass_rate = pass_actions / total_actions if total_actions > 0 else 0.0

    metrics = {
        "n_deals": n_deals,
        "seed": seed,
        "hands_with_bids": hands_with_bids,
        "avg_bid": avg_bid,
        "make_rate": make_rate,
        "bid_10_rate": bid_10_rate,
        "pass_rate": pass_rate,
        "total_auction_actions": total_actions,
        "pass_actions": pass_actions,
    }

    # Run checks
    checks = []

    checks.append(
        (
            "avg_bid",
            avg_bid < THRESHOLD_AVG_BID,
            f"avg_bid={avg_bid:.2f} (threshold: <{THRESHOLD_AVG_BID})",
        )
    )

    checks.append(
        (
            "bid_10_rate",
            bid_10_rate < THRESHOLD_BID_10_RATE,
            f"bid_10_rate={bid_10_rate:.3f} (threshold: <{THRESHOLD_BID_10_RATE})",
        )
    )

    checks.append(
        (
            "make_rate",
            make_rate > THRESHOLD_MAKE_RATE_LOW,
            f"make_rate={make_rate:.3f} (threshold: >{THRESHOLD_MAKE_RATE_LOW})",
        )
    )

    if allow_zero_pass_rate:
        checks.append(
            (
                "pass_rate",
                True,
                f"pass_rate={pass_rate:.3f} (skipped — --allow-zero-pass-rate)",
            )
        )
    else:
        checks.append(
            (
                "pass_rate",
                pass_rate > THRESHOLD_PASS_RATE_MIN,
                f"pass_rate={pass_rate:.3f} (threshold: >{THRESHOLD_PASS_RATE_MIN})",
            )
        )

    return {"metrics": metrics, "checks": checks}


def check_r2_quality(artifact_path: str) -> list:
    """Check R² values in the artifact (warning, not blocking)."""
    with open(artifact_path) as f:
        artifact = json.load(f)

    warnings = []
    models = artifact.get("models", {})
    for family in ("suit", "high", "low"):
        model = models.get(family, {})
        r2 = model.get("r_squared")
        if r2 is not None and r2 < R2_WARNING_THRESHOLD:
            warnings.append(
                f"WARNING: {family} R²={r2:.4f} < {R2_WARNING_THRESHOLD} "
                f"— possible wrong-target or stale artifact"
            )
    return warnings


def main():
    parser = argparse.ArgumentParser(
        description="Post-train behavioral validation for action-value artifacts",
    )
    parser.add_argument(
        "--artifact",
        required=True,
        help="Path to action-value artifact JSON",
    )
    parser.add_argument(
        "--n-deals",
        type=int,
        default=50,
        help="Number of self-play deals (default: 50)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed (default: 42)",
    )
    parser.add_argument(
        "--allow-zero-pass-rate",
        action="store_true",
        help="Skip pass_rate > 0%% check (for bidders that legitimately never pass)",
    )
    args = parser.parse_args()

    artifact_path = args.artifact
    if not Path(artifact_path).exists():
        print(f"ERROR: Artifact not found: {artifact_path}", file=sys.stderr)
        sys.exit(2)

    print("=== Action-Value Artifact Behavioral Validation ===")
    print(f"  Artifact: {artifact_path}")
    print(f"  Deals: {args.n_deals}, Seed: {args.seed}")
    print()

    # R² quality warnings (informational)
    r2_warnings = check_r2_quality(artifact_path)
    for w in r2_warnings:
        print(f"  {w}")
    if r2_warnings:
        print()

    # Behavioral screen
    try:
        result = run_behavioral_screen(
            artifact_path,
            n_deals=args.n_deals,
            seed=args.seed,
            allow_zero_pass_rate=args.allow_zero_pass_rate,
        )
    except Exception as e:
        print(f"ERROR: Failed to run behavioral screen: {e}", file=sys.stderr)
        sys.exit(2)

    metrics = result["metrics"]
    checks = result["checks"]

    print("  Behavioral Metrics:")
    print(f"    avg_bid:      {metrics['avg_bid']:.2f}")
    print(f"    bid_10_rate:  {metrics['bid_10_rate']:.3f}")
    print(f"    make_rate:    {metrics['make_rate']:.3f}")
    print(
        f"    pass_rate:    {metrics['pass_rate']:.3f} ({metrics['pass_actions']}/{metrics['total_auction_actions']} actions)"
    )
    print()

    # Report check results
    n_pass = 0
    n_fail = 0
    for name, passed, detail in checks:
        status = "PASS" if passed else "FAIL"
        if passed:
            n_pass += 1
        else:
            n_fail += 1
        print(f"  [{status}] {name}: {detail}")

    print()
    if n_fail > 0:
        print(f"  VALIDATION FAILED: {n_fail} check(s) failed")
        sys.exit(1)
    else:
        print(f"  VALIDATION PASSED: {n_pass}/{n_pass} checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
