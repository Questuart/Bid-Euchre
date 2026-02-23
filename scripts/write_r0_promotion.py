#!/usr/bin/env python
"""Write R0 auto-promotion decision record.

R0 is auto-promoted when all 6 required metrics are finite for both arms.
No improvement gate, no incumbent comparison (R0 establishes the baseline).

Reads the rung bundle, verifies both artifacts are frozen, loads eval
metrics from seed-42 eval files, checks all 6 metrics are finite,
and writes promotion_decision_r0.json.

Usage:
    PYTHONPATH=src uv run python scripts/write_r0_promotion.py \
        --bundle data/artifacts/arc_d/r0/rung_bundle_r0.json \
        --output data/artifacts/arc_d/r0/promotion_decision_r0.json
"""

import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timezone

from bid_euchre.models.freeze import verify_frozen

# The 6 required metrics for R0 auto-promotion.
# std_bidder_team_points is NOT required at R0 because the evaluator does not
# reliably produce it as a scalar.  SE-based gates only apply at R1+.
REQUIRED_METRICS = [
    "net_expected_points_per_deal",
    "expected_points_per_deal",
    "bid_rate",
    "make_rate",
    "cvar_5",
    "downside_variance",
]


def _git_sha() -> str:
    """Get current git HEAD SHA."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _all_metrics_finite(metrics: dict) -> tuple[bool, list[str]]:
    """Check that all 7 required metrics are present and finite.

    Returns:
        (all_ok, list_of_failures)
    """
    failures = []
    for name in REQUIRED_METRICS:
        val = metrics.get(name)
        if val is None:
            failures.append(f"{name}: missing")
        elif not isinstance(val, (int, float)):
            failures.append(f"{name}: not numeric ({type(val).__name__})")
        elif not math.isfinite(val):
            failures.append(f"{name}: not finite ({val})")
    return len(failures) == 0, failures


def _load_eval_metrics(eval_path: str) -> dict:
    """Load eval metrics from an eval result file.

    Delegates to the shared ``load_eval_metrics`` in
    ``bid_euchre.reporting.evaluator``.
    """
    from bid_euchre.reporting.evaluator import load_eval_metrics

    return load_eval_metrics(eval_path)


def write_r0_promotion(
    bundle_path: str,
    output_path: str,
) -> dict:
    """Write R0 auto-promotion decision.

    Args:
        bundle_path: Path to rung_bundle_r0.json.
        output_path: Path to write promotion_decision_r0.json.

    Returns:
        The promotion decision dict.

    Raises:
        ValueError: If bundle is missing arms or metrics are not finite.
        FileNotFoundError: If bundle or eval files don't exist.
    """
    with open(bundle_path) as f:
        bundle = json.load(f)

    # Validate bundle has both arms
    if "olsa" not in bundle:
        raise ValueError("Bundle missing 'olsa' arm block")
    if "olsa_full" not in bundle:
        raise ValueError("Bundle missing 'olsa_full' arm block")

    # Check artifacts are frozen
    olsa_path = bundle["olsa"]["artifact_path"]
    olsa_full_path = bundle["olsa_full"]["artifact_path"]

    olsa_frozen = verify_frozen(olsa_path)
    olsa_full_frozen = verify_frozen(olsa_full_path)

    tier_1_checks = {
        "artifact_integrity_olsa": "PASS" if olsa_frozen else "FAIL",
        "artifact_integrity_olsa_full": "PASS" if olsa_full_frozen else "FAIL",
    }

    halt_reasons = []
    if not olsa_frozen:
        halt_reasons.append(f"OLSa artifact not frozen: {olsa_path}")
    if not olsa_full_frozen:
        halt_reasons.append(f"OLSa_Full artifact not frozen: {olsa_full_path}")

    # Load eval metrics for both arms (seed 42)
    olsa_eval_path = bundle["olsa"].get("eval_seed42")
    olsa_full_eval_path = bundle["olsa_full"].get("eval_seed42")

    olsa_metrics: dict | None = None
    olsa_full_metrics: dict | None = None

    if olsa_eval_path:
        olsa_metrics = _load_eval_metrics(olsa_eval_path)
    else:
        halt_reasons.append("OLSa eval_seed42 path is null")

    if olsa_full_eval_path:
        olsa_full_metrics = _load_eval_metrics(olsa_full_eval_path)
    else:
        halt_reasons.append("OLSa_Full eval_seed42 path is null")

    # Check all 6 metrics finite for both arms.
    # Guard on `is not None` (not truthiness) so empty dicts from
    # malformed eval files are caught by _all_metrics_finite as "missing".
    if olsa_metrics is not None:
        ok, failures = _all_metrics_finite(olsa_metrics)
        tier_1_checks["no_nan_inf_olsa"] = "PASS" if ok else "FAIL"
        if not ok:
            halt_reasons.extend([f"OLSa {f}" for f in failures])

    if olsa_full_metrics is not None:
        ok, failures = _all_metrics_finite(olsa_full_metrics)
        tier_1_checks["no_nan_inf_olsa_full"] = "PASS" if ok else "FAIL"
        if not ok:
            halt_reasons.extend([f"OLSa_Full {f}" for f in failures])

    # Compute attribution gap (OLSa_Full - OLSa on net_eppd)
    attribution_gap = None
    if olsa_metrics is not None and olsa_full_metrics is not None:
        full_net = olsa_full_metrics.get("net_expected_points_per_deal")
        base_net = olsa_metrics.get("net_expected_points_per_deal")
        if full_net is not None and base_net is not None:
            attribution_gap = round(full_net - base_net, 6)

    # Decision
    decision = "PROMOTED" if not halt_reasons else "HALT"

    # Load artifact SHAs
    olsa_sha = bundle["olsa"].get("artifact_sha256")
    olsa_full_sha = bundle["olsa_full"].get("artifact_sha256")

    # Build promotion record
    record = {
        "schema_version": 3,
        "rung_id": "r0",
        "arc": "arc_d",
        "decision": decision,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evaluator_git_sha": _git_sha(),
        "attribution_gap": attribution_gap,
        "tier_1_checks": tier_1_checks,
        "challenger": {
            "arm": "OLSa_Full",
            "artifact_path": olsa_full_path,
            "artifact_sha256": olsa_full_sha,
            "metrics_seed42": olsa_full_metrics,
        },
        "olsa_arm": {
            "artifact_path": olsa_path,
            "artifact_sha256": olsa_sha,
            "metrics_seed42": olsa_metrics,
        },
        "control": None,  # No control at R0
        "gate_results": {
            "primary": {
                "metric": "auto_promote",
                "note": "R0 is auto-promoted when all 6 required metrics are finite",
                "pass": decision == "PROMOTED",
            },
        },
    }

    if halt_reasons:
        record["halt_reasons"] = halt_reasons

    with open(output_path, "w") as f:
        json.dump(record, f, indent=2)

    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="Write R0 auto-promotion decision")
    parser.add_argument("--bundle", required=True, help="Path to rung_bundle_r0.json")
    parser.add_argument(
        "--output", required=True, help="Output path for promotion_decision_r0.json"
    )

    args = parser.parse_args()

    record = write_r0_promotion(
        bundle_path=args.bundle,
        output_path=args.output,
    )

    print(f"Decision: {record['decision']}")
    if record.get("halt_reasons"):
        for reason in record["halt_reasons"]:
            print(f"  HALT: {reason}")
    else:
        print(f"  Attribution gap: {record['attribution_gap']}")
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()
    sys.exit(0)
