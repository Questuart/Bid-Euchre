#!/usr/bin/env python3
"""
Generate All Reports for a Run (v2.0 with Unified Reporting).

Generates all appropriate reports for a run directory based on experiment mode:
- self_play: Individual strategy dashboards only
- head_to_head: Strategy dashboards + paired comparison
- head_to_head_matrix: Matrix report + optional pairwise comparisons

Changes from v1:
- Mode-aware report generation
- Uses new reporting framework (paths, style, metrics)
- Calls report generators as library functions (not subprocesses)
- Standardized output to <run_dir>/reports/

Output structure (standardized):
    <run_dir>/reports/
    ├── dashboards/<strategy>/
    │   ├── dashboard.png (latest)
    │   ├── plots/ (latest individual plots)
    │   └── _history/<timestamp>/
    ├── paired/
    │   ├── paired_comparison.png (latest)
    │   ├── summary.md (latest)
    │   └── _history/<timestamp>/
    ├── head_to_head/
    │   ├── comparison_matrix.png (latest)
    │   ├── summary.md (latest)
    │   ├── matchups/ (latest per-matchup plots)
    │   └── _history/<timestamp>/
    ├── summary.md (overall run summary)
    └── manifest.json (what was generated)

Usage:
    PYTHONPATH=src python experiments/generate_all_reports.py \\
        --run-dir data/runs/<run_id>
"""

import os
import json
import argparse
from glob import glob
from datetime import datetime
from typing import Dict, List

# Import report generation functions directly
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from experiments.generate_dashboard import plot_dashboard
from experiments.generate_paired_comparison import plot_paired_comparison
from experiments.generate_head_to_head_report import plot_head_to_head_report
from bid_euchre.reporting import get_report_paths, ensure_dir


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
        default="random_legal",
        help="Baseline strategy for comparison (default: random_legal)"
    )
    return parser.parse_args()


def detect_mode(meta: Dict) -> str:
    """
    Detect experiment mode from metadata.
    
    Returns:
        One of: "self_play", "head_to_head", "head_to_head_matrix"
    """
    mode = meta.get("mode")
    if mode:
        return mode
    
    # Fallback: infer from structure
    if len(meta["strategies"]) > 1:
        return "head_to_head"
    else:
        return "self_play"


def main():
    args = parse_args()
    
    # Load metadata
    meta_path = os.path.join(args.run_dir, "meta.json")
    if not os.path.exists(meta_path):
        print(f"❌ Error: meta.json not found in {args.run_dir}")
        return 1
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    # Detect mode
    mode = detect_mode(meta)
    
    print("=" * 70)
    print(f"🎯 Generating All Reports")
    print("=" * 70)
    print(f"Run: {meta['run_id']}")
    print(f"Mode: {mode}")
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
    
    # Track what was generated
    manifest = {
        "generated_at": datetime.now().isoformat(),
        "mode": mode,
        "reports": [],
    }
    
    # =======================================================================
    # 1. Generate individual strategy dashboards (if logs available)
    # =======================================================================
    
    if has_logs and mode != "head_to_head_matrix":
        print("\n📊 Generating individual strategy dashboards...")
        for strategy in strategies:
            try:
                latest_png = plot_dashboard(
                    run_dir=args.run_dir,
                    strategy=strategy,
                    seed=seed,
                    save_individual=True
                )
                print(f"   ✅ {strategy}")
                manifest["reports"].append({
                    "type": "dashboard",
                    "strategy": strategy,
                    "path": os.path.relpath(latest_png, args.run_dir),
                })
            except Exception as e:
                print(f"   ⚠️  {strategy} (skipped - {e})")
    else:
        if not has_logs:
            print("\n⚠️  Skipping dashboards (no JSONL logs found)")
        else:
            print("\n⚠️  Skipping dashboards (head_to_head_matrix mode)")
    
    # =======================================================================
    # 2. Generate paired comparison (if multiple strategies with common deals)
    # =======================================================================
    
    if mode == "head_to_head" and len(strategies) > 1 and meta.get("common_deals", False):
        print("\n📊 Generating paired comparison report...")
        try:
            latest_png = plot_paired_comparison(
                run_dir=args.run_dir,
                baseline=args.baseline,
                output_dir=None  # Use new paths
            )
            print(f"   ✅ Paired comparison")
            manifest["reports"].append({
                "type": "paired",
                "baseline": args.baseline,
                "path": os.path.relpath(latest_png, args.run_dir),
            })
        except Exception as e:
            print(f"   ❌ Failed to generate paired comparison: {e}")
    else:
        if len(strategies) == 1:
            print("\n⚠️  Skipping paired comparison (only one strategy)")
        elif not meta.get("common_deals", False):
            print("\n⚠️  Skipping paired comparison (common_deals=False)")
        else:
            print(f"\n⚠️  Skipping paired comparison (mode={mode})")
    
    # =======================================================================
    # 3. Generate head-to-head matrix (if head_to_head_matrix mode)
    # =======================================================================
    
    if mode == "head_to_head_matrix":
        print("\n📊 Generating head-to-head matrix report...")
        try:
            latest_png = plot_head_to_head_report(args.run_dir)
            print(f"   ✅ Head-to-head matrix")
            manifest["reports"].append({
                "type": "head_to_head",
                "path": os.path.relpath(latest_png, args.run_dir),
            })
        except Exception as e:
            print(f"   ❌ Failed to generate head-to-head report: {e}")
    
    # =======================================================================
    # 4. Generate overall summary markdown
    # =======================================================================
    
    print("\n📝 Generating overall summary...")
    generate_overall_summary(args.run_dir, meta, manifest, mode)
    print(f"   ✅ summary.md")
    
    # =======================================================================
    # 5. Write manifest
    # =======================================================================
    
    paths = get_report_paths(args.run_dir)
    manifest_path = os.path.join(paths.reports_root, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ All reports generated!")
    print("=" * 70)
    print(f"📁 Output directory: {paths.reports_root}/")
    print(f"📊 Generated {len(manifest['reports'])} report(s):")
    for report in manifest["reports"]:
        print(f"   • {report['type']}: {report['path']}")
    print(f"\n📄 Manifest: {manifest_path}")
    print()


def generate_overall_summary(run_dir: str, meta: Dict, manifest: Dict, mode: str):
    """Generate overall run summary markdown."""
    paths = get_report_paths(run_dir)
    ensure_dir(paths.reports_root)
    
    lines = []
    lines.append(f"# Run Summary: {meta['run_id']}\n\n")
    
    lines.append("## Experiment Configuration\n\n")
    lines.append(f"- **Experiment**: {meta['experiment_name']}\n")
    lines.append(f"- **Mode**: {mode}\n")
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
    
    # Load performance metrics
    perf_path = os.path.join(run_dir, "perf.json")
    if os.path.exists(perf_path):
        with open(perf_path) as f:
            perf = json.load(f)
        
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
    for report in manifest["reports"]:
        if report["type"] == "dashboard":
            lines.append(f"### Strategy Dashboard: {report['strategy']}\n\n")
            lines.append(f"- `{report['path']}`\n\n")
        elif report["type"] == "paired":
            lines.append(f"### Paired Comparison (baseline: {report['baseline']})\n\n")
            lines.append(f"- `{report['path']}`\n\n")
        elif report["type"] == "head_to_head":
            lines.append(f"### Head-to-Head Matrix\n\n")
            lines.append(f"- `{report['path']}`\n\n")
    
    lines.append("## Quick View\n\n")
    lines.append("```bash\n")
    lines.append(f"# View latest reports\n")
    if mode != "head_to_head_matrix":
        lines.append(f"open {run_dir}/reports/dashboards/*/dashboard.png\n")
    if mode == "head_to_head":
        lines.append(f"open {run_dir}/reports/paired/paired_comparison.png\n")
    if mode == "head_to_head_matrix":
        lines.append(f"open {run_dir}/reports/head_to_head/comparison_matrix.png\n")
    lines.append("```\n")
    
    with open(paths.summary_md, "w") as f:
        f.writelines(lines)


if __name__ == "__main__":
    import sys
    sys.exit(main())
