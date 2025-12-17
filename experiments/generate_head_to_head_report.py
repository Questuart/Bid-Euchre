#!/usr/bin/env python3
"""
Generate Head-to-Head Comparison Report (v2.0 with Unified Reporting).

Creates comprehensive visualizations and summaries for head-to-head matchup experiments.

Changes from v1:
- Uses new reporting framework (paths, style, metrics modules)
- Writes to standardized archive + latest pattern
- Importable as library function

Usage:
    PYTHONPATH=src python experiments/generate_head_to_head_report.py \\
        --run-dir data/runs/<run_id>

Generates:
    <run_dir>/reports/head_to_head/
    ├── comparison_matrix.png (latest)
    ├── summary.md (latest)
    ├── matchups/ (latest per-matchup plots)
    └── _history/<timestamp>/ (archived version)
"""

import os
import sys
import json
import argparse
from glob import glob
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from bid_euchre.analysis import wilson_ci, paired_t_ci
from bid_euchre.reporting import (
    STRATEGY_NAMES,
    STRATEGY_COLORS,
    apply_report_style,
    get_report_paths,
    ensure_dir,
    copy_to_latest,
    write_latest_pointer,
)

# Apply report styling
apply_report_style()


def parse_args():
    parser = argparse.ArgumentParser(description="Generate head-to-head comparison report")
    parser.add_argument("--run-dir", type=str, required=True, help="Path to run directory")
    return parser.parse_args()


def load_matchup_results(run_dir: str) -> Dict:
    """Load all matchup results from a run directory."""
    results_dir = os.path.join(run_dir, "results")
    
    matchup_data = {}
    for matchup_dir in sorted(os.listdir(results_dir)):
        matchup_path = os.path.join(results_dir, matchup_dir)
        if not os.path.isdir(matchup_path):
            continue
        
        # Load all scenario files for this matchup
        scenarios = {}
        for json_file in glob(os.path.join(matchup_path, "*.json")):
            scenario_name = os.path.basename(json_file).replace(".json", "")
            with open(json_file) as f:
                scenarios[scenario_name] = json.load(f)
        
        matchup_data[matchup_dir] = scenarios
    
    return matchup_data


def compute_matchup_stats(matchup_results: Dict) -> Dict:
    """Compute aggregate statistics across all scenarios for a matchup."""
    total_hands = 0
    total_team0_tricks = 0
    total_team1_tricks = 0
    total_team0_wins = 0
    
    for scenario, data in matchup_results.items():
        hands = data["hands"]
        total_hands += hands
        total_team0_tricks += data["avg_team0"] * hands
        total_team1_tricks += data["avg_team1"] * hands
        
        # Count wins (team0 >= 6 tricks)
        dist = data["distribution_team0"]
        total_team0_wins += sum(count for tricks, count in dist.items() if int(tricks) >= 6)
    
    avg_team0 = total_team0_tricks / total_hands
    avg_team1 = total_team1_tricks / total_hands
    
    # Wilson CI for win rate
    win_rate, ci_lower, ci_upper = wilson_ci(total_team0_wins, total_hands, 0.95)
    
    return {
        "total_hands": total_hands,
        "avg_team0": avg_team0,
        "avg_team1": avg_team1,
        "delta_tricks": avg_team0 - avg_team1,
        "team0_wins": total_team0_wins,
        "win_rate": win_rate,
        "win_rate_ci_lower": ci_lower,
        "win_rate_ci_upper": ci_upper,
    }


def generate_summary_markdown(run_dir: str, all_stats: Dict) -> str:
    """Generate summary markdown with key findings."""
    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    
    perf_path = os.path.join(run_dir, "perf.json")
    with open(perf_path) as f:
        perf = json.load(f)
    
    lines = [
        f"# Head-to-Head Matchup Results",
        f"",
        f"**Experiment**: {meta['experiment_name']}",
        f"**Run ID**: {meta['run_id']}",
        f"**Date**: {meta['timestamp']}",
        f"**Seed**: {meta['seed']}",
        f"**Hands per Matchup**: {meta['n_per'] * len(meta['scenarios']):,}",
        f"**Duration**: {perf['total_duration_human']}",
        f"**Throughput**: {perf['overall_throughput_hands_per_sec']:.0f} hands/sec",
        f"",
        f"## Summary Statistics",
        f"",
        f"| Matchup | Team 0 Avg Tricks | Team 1 Avg Tricks | Δ Tricks | Team 0 Win Rate | 95% CI |",
        f"|---------|-------------------|-------------------|----------|-----------------|--------|",
    ]
    
    for matchup_name in sorted(all_stats.keys()):
        stats = all_stats[matchup_name]
        team0, team1 = matchup_name.split("_vs_")
        
        lines.append(
            f"| {team0} vs {team1} | {stats['avg_team0']:.3f} | {stats['avg_team1']:.3f} | "
            f"{stats['delta_tricks']:+.3f} | {stats['win_rate']*100:.1f}% | "
            f"[{stats['win_rate_ci_lower']*100:.1f}%, {stats['win_rate_ci_upper']*100:.1f}%] |"
        )
    
    lines.extend([
        f"",
        f"## Key Findings",
        f"",
        f"### Strategies That Beat Random",
        f"",
    ])
    
    # Find matchups where strategy beats random
    beats_random = []
    for matchup_name, stats in all_stats.items():
        if "_vs_random_legal" in matchup_name and matchup_name != "random_legal_vs_random_legal":
            strategy = matchup_name.replace("_vs_random_legal", "")
            delta = stats['delta_tricks']
            ci_lower = stats['win_rate_ci_lower']
            ci_upper = stats['win_rate_ci_upper']
            
            # Check if significantly better (win rate CI > 50%)
            if ci_lower > 0.50:
                beats_random.append((strategy, delta, stats['win_rate'], "✅ Significantly"))
            elif ci_upper < 0.50:
                beats_random.append((strategy, delta, stats['win_rate'], "❌ Significantly worse"))
            else:
                beats_random.append((strategy, delta, stats['win_rate'], "➖ Not significant"))
    
    for strategy, delta, win_rate, sig in sorted(beats_random, key=lambda x: -x[1]):
        lines.append(f"- **{strategy}**: Δ {delta:+.3f} tricks, {win_rate*100:.1f}% win rate - {sig}")
    
    lines.extend([
        f"",
        f"## Detailed Reports",
        f"",
        f"Individual matchup visualizations available in `reports/matchups/`",
        f"",
    ])
    
    return "\n".join(lines)


def plot_comparison_matrix(all_stats: Dict, output_path: str):
    """Generate comparison matrix heatmap."""
    # Extract unique strategies
    strategies = set()
    for matchup_name in all_stats.keys():
        team0, team1 = matchup_name.split("_vs_")
        strategies.add(team0)
        strategies.add(team1)
    
    strategies = sorted(strategies)
    n = len(strategies)
    
    # Build matrix: matrix[i][j] = win rate of strategy i vs strategy j
    matrix = np.full((n, n), np.nan)
    
    for matchup_name, stats in all_stats.items():
        team0, team1 = matchup_name.split("_vs_")
        i = strategies.index(team0)
        j = strategies.index(team1)
        matrix[i, j] = stats['win_rate'] * 100  # Convert to percentage
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    
    im = ax.imshow(matrix, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
    
    # Add text annotations
    for i in range(n):
        for j in range(n):
            if not np.isnan(matrix[i, j]):
                text = ax.text(j, i, f"{matrix[i, j]:.1f}%",
                              ha="center", va="center", color="black",
                              fontsize=10, fontweight="bold")
    
    # Set ticks and labels
    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    ax.set_xticklabels(strategies, rotation=45, ha="right")
    ax.set_yticklabels(strategies)
    
    ax.set_xlabel("Team 1 (Opponents)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Team 0 (Players)", fontsize=12, fontweight="bold")
    ax.set_title("Head-to-Head Win Rate Matrix (%)\n(Team 0 Win Rate vs Team 1)", 
                 fontsize=14, fontweight="bold", pad=20)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Team 0 Win Rate (%)", rotation=270, labelpad=20)
    
    # Add reference line at 50%
    ax.axhline(y=-0.5, color='black', linewidth=2)
    ax.axvline(x=-0.5, color='black', linewidth=2)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_head_to_head_report(run_dir: str) -> str:
    """
    Generate head-to-head comparison report using new framework.
    
    Writes to standardized archive + latest pattern:
        <run_dir>/reports/head_to_head/
        ├── comparison_matrix.png (latest)
        ├── summary.md (latest)
        ├── matchups/ (latest per-matchup plots)
        └── _history/<timestamp>/ (archived version)
    
    Args:
        run_dir: Base run directory
    
    Returns:
        Path to latest comparison_matrix.png
    """
    print("📊 Generating Head-to-Head Comparison Report")
    print("=" * 70)
    print(f"Run directory: {run_dir}\n")
    
    # Load results
    print("📂 Loading matchup results...")
    matchup_results = load_matchup_results(run_dir)
    print(f"   Found {len(matchup_results)} matchups\n")
    
    # Compute statistics
    print("📈 Computing statistics...")
    all_stats = {}
    for matchup_name, scenarios in matchup_results.items():
        all_stats[matchup_name] = compute_matchup_stats(scenarios)
    print(f"   Computed stats for {len(all_stats)} matchups\n")
    
    # Get paths using new framework
    paths = get_report_paths(run_dir)
    archive_dir = paths.h2h_archive
    latest_dir = paths.h2h_root
    matchups_archive = os.path.join(archive_dir, "matchups")
    
    ensure_dir(archive_dir)
    ensure_dir(matchups_archive)
    
    # Generate summary markdown in archive
    print("📝 Generating summary...")
    summary_md = generate_summary_markdown(run_dir, all_stats)
    archive_summary = os.path.join(archive_dir, "summary.md")
    with open(archive_summary, "w") as f:
        f.write(summary_md)
    
    # Generate comparison matrix in archive
    print("📊 Generating comparison matrix...")
    archive_matrix = os.path.join(archive_dir, "comparison_matrix.png")
    plot_comparison_matrix(all_stats, archive_matrix)
    
    # Copy to latest
    latest_summary = os.path.join(latest_dir, "summary.md")
    latest_matrix = os.path.join(latest_dir, "comparison_matrix.png")
    latest_matchups = paths.h2h_matchups
    
    copy_to_latest(archive_summary, latest_summary)
    copy_to_latest(archive_matrix, latest_matrix)
    
    if os.path.exists(matchups_archive):
        copy_to_latest(matchups_archive, latest_matchups, is_dir=True)
    
    # Write latest pointer
    archive_rel = os.path.relpath(archive_dir, latest_dir)
    write_latest_pointer(latest_dir, archive_rel)
    
    print("✅ Head-to-head report")
    print(f"   Latest: {latest_matrix}")
    print(f"   Archive: {archive_matrix}")
    
    return latest_matrix


def main():
    args = parse_args()
    plot_head_to_head_report(args.run_dir)


if __name__ == "__main__":
    main()

