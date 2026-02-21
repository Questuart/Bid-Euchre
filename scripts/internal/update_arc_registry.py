#!/usr/bin/env python3
"""Idempotent upsert into MODEL_ARC_RUNS.md registry.

Reads existing markdown table, finds matching rung_id row and replaces it,
or appends a new row. Generates row from bundle JSON + promotion decision.

Usage:
    uv run python scripts/internal/update_arc_registry.py \\
        --bundle data/artifacts/arc_d/r1/rung_bundle_r1.json \\
        --decision data/artifacts/arc_d/r1/promotion_decision_r1.json \\
        [--registry docs/02_agent/MODEL_ARC_RUNS.md] \\
        [--pr 400]
"""

import argparse
import json
import sys
from pathlib import Path

REGISTRY_HEADER = """\
# Model Arc Runs

Provenance registry for Arc D model promotion decisions.
Updated by promotion scripts (`scripts/write_r0_promotion.py` for R0,
gate runner for R1+).

## Arc D: OLSa-Hybrid Bidder

| Rung | Decision | OLSa_Full net_eppd | OLSa net_eppd | Attribution Gap | Date | Bundle |
|------|----------|--------------------|---------------|-----------------|------|--------|
"""

TABLE_SEPARATOR = "|------|----------|--------------------|---------------|-----------------|------|--------|"


def _build_row(bundle: dict, decision: dict, pr_number: str) -> str:
    """Build a markdown table row from bundle and decision data.

    Uses the unified registry schema: Rung, Decision, OLSa_Full net_eppd,
    OLSa net_eppd, Attribution Gap, Date, Bundle.

    Metrics are read from the decision record's embedded metrics (schema v3)
    or loaded from eval files (best effort).

    Args:
        bundle: Loaded rung bundle dict.
        decision: Loaded promotion decision dict.
        pr_number: PR number string (currently unused but retained for API compat).

    Returns:
        Markdown table row string (with leading/trailing |).
    """
    rung_id = bundle.get("rung_id", "?")
    status = decision.get("decision", "?")

    # Extract date from decision timestamp (ISO-8601 -> YYYY-MM-DD)
    timestamp = decision.get("timestamp", "")
    date_str = timestamp[:10] if len(timestamp) >= 10 else "--"

    # Extract attribution gap from decision record or reasons
    attribution_gap = ""
    ag_val = decision.get("attribution_gap")
    if ag_val is not None:
        attribution_gap = f"{ag_val:.4f}"
    else:
        for reason in decision.get("reasons", []):
            if "attribution_gap=" in str(reason):
                attribution_gap = str(reason).split("attribution_gap=")[-1]

    # Best-effort metric extraction: try decision record first (schema v3),
    # then fall back to loading eval files.
    olsa_full_net_eppd = ""
    olsa_net_eppd = ""

    # Schema v3 decision records embed metrics
    challenger = decision.get("challenger", {})
    if challenger and challenger.get("metrics_seed42"):
        m = challenger["metrics_seed42"]
        val = m.get("net_expected_points_per_deal", m.get("net_eppd"))
        if val is not None:
            olsa_full_net_eppd = f"{val:.4f}"

    olsa_arm = decision.get("olsa_arm", {})
    if olsa_arm and olsa_arm.get("metrics_seed42"):
        m = olsa_arm["metrics_seed42"]
        val = m.get("net_expected_points_per_deal", m.get("net_eppd"))
        if val is not None:
            olsa_net_eppd = f"{val:.4f}"

    # Fallback: load from eval files if decision doesn't embed metrics
    olsa_full = bundle.get("olsa_full", {})
    olsa = bundle.get("olsa", {})

    if not olsa_full_net_eppd:
        eval_path = olsa_full.get("eval_seed42")
        if eval_path:
            try:
                with open(eval_path) as f:
                    metrics = json.load(f)
                val = metrics.get(
                    "net_expected_points_per_deal", metrics.get("net_eppd")
                )
                if val is not None:
                    olsa_full_net_eppd = f"{val:.4f}"
            except (FileNotFoundError, json.JSONDecodeError, TypeError):
                pass

    if not olsa_net_eppd:
        eval_path = olsa.get("eval_seed42")
        if eval_path:
            try:
                with open(eval_path) as f:
                    metrics = json.load(f)
                val = metrics.get(
                    "net_expected_points_per_deal", metrics.get("net_eppd")
                )
                if val is not None:
                    olsa_net_eppd = f"{val:.4f}"
            except (FileNotFoundError, json.JSONDecodeError, TypeError):
                pass

    bundle_name = f"`rung_bundle_{rung_id}.json`"

    return (
        f"| {rung_id} | {status} | {olsa_full_net_eppd} | {olsa_net_eppd} "
        f"| {attribution_gap} | {date_str} | {bundle_name} |"
    )


def upsert_registry(
    registry_path: str, bundle: dict, decision: dict, pr_number: str
) -> str:
    """Idempotent upsert: replace existing rung row or append new one.

    Args:
        registry_path: Path to MODEL_ARC_RUNS.md.
        bundle: Loaded rung bundle dict.
        decision: Loaded promotion decision dict.
        pr_number: PR number string.

    Returns:
        Updated registry content string.
    """
    rung_id = bundle.get("rung_id", "?")
    new_row = _build_row(bundle, decision, pr_number)

    path = Path(registry_path)
    if not path.exists():
        return REGISTRY_HEADER + new_row + "\n"

    content = path.read_text()
    lines = content.split("\n")

    # Find and replace existing row for this rung_id
    replaced = False
    new_lines = []
    for line in lines:
        if line.startswith("|") and f"| {rung_id} |" in line:
            new_lines.append(new_row)
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        # Append before trailing blank lines
        while new_lines and new_lines[-1].strip() == "":
            new_lines.pop()
        new_lines.append(new_row)
        new_lines.append("")

    return "\n".join(new_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Update Arc D registry (MODEL_ARC_RUNS.md)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--bundle",
        type=str,
        required=True,
        help="Path to rung bundle JSON file",
    )
    parser.add_argument(
        "--decision",
        type=str,
        required=True,
        help="Path to promotion decision JSON file",
    )
    parser.add_argument(
        "--registry",
        type=str,
        default="docs/02_agent/MODEL_ARC_RUNS.md",
        help="Path to MODEL_ARC_RUNS.md (default: docs/02_agent/MODEL_ARC_RUNS.md)",
    )
    parser.add_argument(
        "--pr",
        type=str,
        default="?",
        help="GitHub PR number",
    )
    args = parser.parse_args()

    try:
        with open(args.bundle) as f:
            bundle = json.load(f)
        with open(args.decision) as f:
            decision = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading input files: {e}", file=sys.stderr)
        sys.exit(1)

    updated = upsert_registry(args.registry, bundle, decision, args.pr)

    Path(args.registry).parent.mkdir(parents=True, exist_ok=True)
    Path(args.registry).write_text(updated)
    print(f"Registry updated: {args.registry}")
    print(f"  Rung: {bundle.get('rung_id', '?')}")
    print(f"  Decision: {decision.get('decision', '?')}")


if __name__ == "__main__":
    main()
