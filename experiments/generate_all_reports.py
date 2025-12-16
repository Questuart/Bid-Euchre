#!/usr/bin/env python3
"""
Generate All Reports for a Run (standardized output contract).

Generates all appropriate reports for a run directory:
- Individual strategy dashboards (if logged data available)
- Paired comparison report (if multiple strategies with common deals)
- Summary markdown

Output structure (standardized):
    data/runs/<run_id>/dashboard/
    ├── <strategy_1>_<timestamp>/
    │   ├── dashboard.png
    │   └── individual_plots/
    ├── <strategy_2>_<timestamp>/
    │   ├── dashboard.png
    │   └── individual_plots/
    ├── paired_<timestamp>/
    │   ├── paired_comparison.png
    │   └── summary.md
    └── summary.md  # Overall run summary

Usage:
    PYTHONPATH=src python experiments/generate_all_reports.py \\
        --run-dir data/runs/<run_id>
"""

import os
import json
import argparse
import subprocess
from glob import glob
from datetime import datetime
from typing import Dict


def parse_args():
    parser = argparse.ArgumentParser(description="Generate all reports for a run")
    parser.add_argument(
        "--run-dir",
        type=str,
        required=True,
        help="Path to run directory"
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default="greedy",
        help="Baseline strategy for comparison (default: greedy)"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    # Load metadata
    meta_path = os.path.join(args.run_dir, "meta.json")
    if not os.path.exists(meta_path):
        print(f"❌ Error: meta.json not found in {args.run_dir}")
        return 1
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    print("=" * 70)
    print(f"🎯 Generating All Reports")
    print("=" * 70)
    print(f"Run: {meta['run_id']}")
    print(f"Strategies: {', '.join(meta['strategies'])}")
    print(f"Scenarios: {len(meta['scenarios'])}")
    print(f"Total hands: {meta['total_hands']:,}")
    print(f"Common deals: {meta.get('common_deals', False)}")
    print("=" * 70)
    
    # Check what logs are available
    logs_dir = os.path.join(args.run_dir, "logs")
    has_logs = os.path.exists(logs_dir) and len(glob(os.path.join(logs_dir, "*.jsonl"))) > 0
    
    strategies = meta["strategies"]
    seed = meta.get("seed", 42)
    
    reports_generated = []
    
    # 1. Generate individual strategy dashboards (if logs available)
    if has_logs:
        print("\n📊 Generating individual strategy dashboards...")
        for strategy in strategies:
            cmd = [
                "python", "experiments/generate_dashboard.py",
                "--run-dir", args.run_dir,
                "--strategy", strategy,
                "--seed", str(seed)
            ]
            
            try:
                env = os.environ.copy()
                env["PYTHONPATH"] = "src"
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    cwd=os.path.join(os.path.dirname(__file__), "..")
                )
                
                if result.returncode == 0:
                    print(f"   ✅ {strategy}")
                    reports_generated.append(f"dashboard/{strategy}_*/dashboard.png")
                else:
                    print(f"   ⚠️  {strategy} (skipped - no data)")
            except Exception as e:
                print(f"   ❌ {strategy} (error: {e})")
    else:
        print("\n⚠️  Skipping dashboards (no JSONL logs found)")
    
    # 2. Generate paired comparison (if multiple strategies with common deals)
    if len(strategies) > 1 and meta.get("common_deals", False):
        print("\n📊 Generating paired comparison report...")
        cmd = [
            "python", "experiments/generate_paired_comparison.py",
            "--run-dir", args.run_dir,
            "--baseline", args.baseline
        ]
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = "src"
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                cwd=os.path.join(os.path.dirname(__file__), "..")
            )
            
            if result.returncode == 0:
                print(f"   ✅ Paired comparison")
                reports_generated.append("dashboard/paired_*/paired_comparison.png")
                reports_generated.append("dashboard/paired_*/summary.md")
            else:
                print(f"   ❌ Failed to generate paired comparison")
                print(result.stderr[:200])
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        if len(strategies) == 1:
            print("\n⚠️  Skipping paired comparison (only one strategy)")
        else:
            print("\n⚠️  Skipping paired comparison (common_deals=False)")
    
    # 3. Generate overall summary markdown
    print("\n📝 Generating overall summary...")
    generate_overall_summary(args.run_dir, meta)
    reports_generated.append("dashboard/summary.md")
    print(f"   ✅ summary.md")
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ All reports generated!")
    print("=" * 70)
    print(f"📁 Output directory: {args.run_dir}/dashboard/")
    print(f"📊 Generated {len(reports_generated)} report artifacts:")
    for report in reports_generated:
        print(f"   • {report}")
    print()


def generate_overall_summary(run_dir: str, meta: Dict):
    """Generate overall run summary markdown."""
    dashboard_dir = os.path.join(run_dir, "dashboard")
    os.makedirs(dashboard_dir, exist_ok=True)
    
    lines = []
    lines.append(f"# Run Summary: {meta['run_id']}\n\n")
    
    lines.append("## Experiment Configuration\n\n")
    lines.append(f"- **Experiment**: {meta['experiment_name']}\n")
    lines.append(f"- **Timestamp**: {meta['timestamp']}\n")
    lines.append(f"- **Random Seed**: {meta.get('seed', 'None (random)')}\n")
    lines.append(f"- **Hands per Scenario**: {meta['n_per']:,}\n")
    lines.append(f"- **Total Hands**: {meta['total_hands']:,}\n")
    lines.append(f"- **Common Deals**: {meta.get('common_deals', False)}\n")
    lines.append(f"- **Leader Randomized**: {meta.get('leader_randomized', True)}\n")
    lines.append(f"- **Log Level**: {meta.get('log_level', 'none')}\n\n")
    
    lines.append("## Strategies\n\n")
    for strategy in meta['strategies']:
        lines.append(f"- `{strategy}`\n")
    lines.append("\n")
    
    lines.append("## Scenarios\n\n")
    for scenario in meta['scenarios']:
        contract = scenario['contract_type']
        trump = scenario.get('trump_suit')
        label = f"{contract}" + (f" ({trump})" if trump else "")
        lines.append(f"- {label}\n")
    lines.append("\n")
    
    # Load performance metrics (from perf.json if available, else meta.json)
    perf_path = os.path.join(run_dir, "perf.json")
    if os.path.exists(perf_path):
        with open(perf_path) as f:
            perf = json.load(f)
    else:
        perf = meta.get("performance")  # Backwards compatibility
    
    if perf:
        lines.append("## Performance\n\n")
        lines.append(f"- **Total Duration**: {perf['total_duration_human']}\n")
        lines.append(f"- **Overall Throughput**: {perf['overall_throughput_hands_per_sec']:.0f} hands/sec\n\n")
        
        lines.append("### Per-Scenario Performance\n\n")
        lines.append("| Strategy | Scenario | Duration | Hands/sec |\n")
        lines.append("|----------|----------|----------|----------|\n")
        for metric in perf['by_scenario'][:10]:  # Show first 10
            lines.append(
                f"| {metric['strategy']} | {metric['scenario']} | "
                f"{metric['duration_sec']:.1f}s | {metric['hands_per_sec']:.0f} |\n"
            )
        if len(perf['by_scenario']) > 10:
            lines.append(f"| ... | ... | ... | ... |\n")
        lines.append("\n")
    
    lines.append("## Generated Reports\n\n")
    lines.append("### Strategy Dashboards\n\n")
    for strategy in meta['strategies']:
        lines.append(f"- `dashboard/{strategy}_<timestamp>/dashboard.png`\n")
    
    if len(meta['strategies']) > 1 and meta.get('common_deals'):
        lines.append("\n### Paired Comparison\n\n")
        lines.append(f"- `dashboard/paired_<timestamp>/paired_comparison.png`\n")
        lines.append(f"- `dashboard/paired_<timestamp>/summary.md`\n")
    
    lines.append("\n## Quick View\n\n")
    lines.append("```bash\n")
    lines.append(f"# View latest dashboards\n")
    lines.append(f"open {run_dir}/dashboard/*/dashboard.png\n")
    lines.append(f"open {run_dir}/dashboard/*/paired_comparison.png\n")
    lines.append("```\n")
    
    with open(os.path.join(dashboard_dir, "summary.md"), "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    import sys
    sys.exit(main())

