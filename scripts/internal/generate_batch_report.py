#!/usr/bin/env python
"""Generate batch report with eligibility gate from suite rollup.

Aggregates run artifacts into a single batch report with machine-readable
eligibility gate (batch_gate.json) and human-readable report (BATCH_REPORT.md).

Usage:
    PYTHONPATH=src python scripts/internal/generate_batch_report.py \
        --rollup data/runs/suite_<id>/rollup.json \
        --output /tmp/batch_report

    PYTHONPATH=src python scripts/internal/generate_batch_report.py \
        --rollup data/runs/suite_<id>/rollup.json \
        --notebook-gate data/runs/suite_<id>/notebook_gate.json \
        --output /tmp/batch_report \
        --expected-configs config_a.yaml,config_b.yaml
"""

import argparse
import json
import sys
from pathlib import Path

from bid_euchre.reporting.eligibility import compute_eligibility


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate batch report with eligibility gate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--rollup",
        required=True,
        help="Path to suite rollup.json",
    )
    parser.add_argument(
        "--run-dir",
        default="data/runs",
        help="Base run directory (default: data/runs)",
    )
    parser.add_argument(
        "--notebook-gate",
        default=None,
        help="Path to notebook_gate.json (optional)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory for batch_gate.json and BATCH_REPORT.md",
    )
    parser.add_argument(
        "--expected-configs",
        default=None,
        help="Comma-separated config filenames for membership check (optional)",
    )
    return parser.parse_args()


def build_batch_report_markdown(rollup: dict, gate_dict: dict) -> str:
    """Build human-readable BATCH_REPORT.md."""
    lines = []

    # Header
    batch = rollup.get("batch", {})
    batch_id = batch.get("batch_id", gate_dict.get("batch_id", "unknown"))
    batch_purpose = batch.get("batch_purpose", gate_dict.get("batch_purpose", "unknown"))
    eligible = gate_dict.get("eligible", False)
    status_str = "ELIGIBLE" if eligible else "NOT ELIGIBLE"

    lines.append(f"# Batch Report: {batch_id}")
    lines.append("")
    lines.append(f"**Status**: {status_str}")
    lines.append(f"**Purpose**: {batch_purpose}")
    lines.append(f"**Suite**: {rollup.get('suite_name', 'unknown')}")
    lines.append(f"**Seed**: {rollup.get('suite_seed', 'unknown')}")
    lines.append(f"**Created**: {gate_dict.get('created_at_utc', 'unknown')}")
    lines.append("")

    # Member runs
    lines.append("## Member Runs")
    lines.append("")
    lines.append("| Config | Run ID | Status | Git SHA |")
    lines.append("|--------|--------|--------|---------|")
    for config in rollup.get("configs", []):
        config_name = Path(config.get("config_path", "")).name
        status_icon = "PASS" if config.get("status") == "ok" else "FAIL"
        lines.append(
            f"| {config_name} | {config.get('run_id', 'N/A')} "
            f"| {status_icon} | {config.get('git_sha', 'N/A')} |"
        )
    lines.append("")

    # Eligibility gate
    lines.append("## Eligibility Gate")
    lines.append("")
    lines.append("| Rule | Status | Detail |")
    lines.append("|------|--------|--------|")
    for reason in gate_dict.get("reasons", []):
        lines.append(
            f"| {reason['rule']} | {reason['status']} | {reason['detail']} |"
        )
    lines.append("")

    # Repro
    lines.append("## Repro Commands")
    lines.append("")
    lines.append("```bash")
    lines.append("# Re-run eligibility check:")
    lines.append(
        "PYTHONPATH=src python scripts/internal/generate_batch_report.py \\"
    )
    lines.append("    --rollup <rollup_path> --output <output_dir>")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def main():
    args = parse_args()

    # Load rollup
    rollup_path = Path(args.rollup)
    if not rollup_path.exists():
        print(f"Error: rollup not found: {args.rollup}", file=sys.stderr)
        sys.exit(1)

    with rollup_path.open() as f:
        rollup = json.load(f)

    # Resolve batch purpose from rollup or default
    batch = rollup.get("batch", {})
    batch_purpose = batch.get("batch_purpose", "exploration")

    # Parse expected configs
    expected_configs = None
    if args.expected_configs:
        expected_configs = set(args.expected_configs.split(","))

    # Compute eligibility
    gate = compute_eligibility(
        rollup=rollup,
        run_base_dir=args.run_dir,
        batch_purpose=batch_purpose,
        notebook_gate_path=args.notebook_gate,
        expected_configs=expected_configs,
    )

    gate_dict = gate.to_dict()

    # Write outputs
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    with (output_dir / "batch_gate.json").open("w") as f:
        json.dump(gate_dict, f, indent=2, sort_keys=True)

    report_md = build_batch_report_markdown(rollup, gate_dict)
    with (output_dir / "BATCH_REPORT.md").open("w") as f:
        f.write(report_md)

    # Print summary
    status = "ELIGIBLE" if gate.eligible else "NOT ELIGIBLE"
    print(f"Batch {gate.batch_id}: {status}")
    for r in gate.reasons:
        print(f"  [{r.status}] {r.rule}: {r.detail}")
    print(f"\nArtifacts: {output_dir}/")

    sys.exit(0 if gate.eligible else 1)


if __name__ == "__main__":
    main()
