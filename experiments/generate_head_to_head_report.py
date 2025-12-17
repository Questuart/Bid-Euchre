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
    OUTCOME_COLORS,
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
        f"Individual matchup visualizations available in `reports/head_to_head/matchups/`",
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


def _scenario_sort_key(name: str) -> tuple:
    order = {
        'suit_C': 0,
        'suit_D': 1,
        'suit_H': 2,
        'suit_S': 3,
        'high': 4,
        'low': 5,
    }
    return (order.get(name, 999), name)


def _outcome_counts_from_distribution(dist: Dict) -> Dict[str, int]:
    win = 0
    push = 0
    loss = 0
    for k, v in dist.items():
        t = int(k)
        c = int(v)
        if t >= 6:
            win += c
        elif t == 5:
            push += c
        else:
            loss += c
    return {'win': win, 'push': push, 'loss': loss, 'n': win + push + loss}


def _pretty_matchup_name(matchup_name: str) -> str:
    if '_vs_' not in matchup_name:
        return matchup_name
    team0, team1 = matchup_name.split('_vs_', 1)
    t0 = STRATEGY_NAMES.get(team0, team0)
    t1 = STRATEGY_NAMES.get(team1, team1)
    return f"{t0} vs {t1}"


def plot_matchup_detail(matchup_name: str, scenarios: Dict, output_path: str) -> None:
    """Per-matchup PNG showing Δ tricks + Win/Push/Loss by scenario."""
    scenario_names = sorted(scenarios.keys(), key=_scenario_sort_key)
    if not scenario_names:
        return

    labels = []
    deltas = []
    avg0 = []
    avg1 = []
    n_hands = []
    win_rates = []
    push_rates = []
    loss_rates = []

    for s in scenario_names:
        data = scenarios[s]
        hands = int(data.get('hands', 0))
        a0 = float(data.get('avg_team0', 0.0))
        a1 = float(data.get('avg_team1', 0.0))
        dist0 = data.get('distribution_team0', {})

        counts = _outcome_counts_from_distribution(dist0)
        n = int(counts['n'] if counts['n'] > 0 else hands)

        labels.append(s)
        deltas.append(a0 - a1)
        avg0.append(a0)
        avg1.append(a1)
        n_hands.append(n)

        win_rates.append((counts['win'] / n) if n else 0.0)
        push_rates.append((counts['push'] / n) if n else 0.0)
        loss_rates.append((counts['loss'] / n) if n else 0.0)

    y = np.arange(len(labels))
    fig = plt.figure(figsize=(14, 8), facecolor='white')
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.25)
    fig.suptitle(f"Head-to-Head Matchup Detail — {_pretty_matchup_name(matchup_name)}",
                 fontsize=14, fontweight='bold', y=0.98)

    ax1 = fig.add_subplot(gs[0, 0])
    colors = ['#27ae60' if d > 0 else '#e74c3c' if d < 0 else '#95a5a6' for d in deltas]
    ax1.barh(y, deltas, color=colors, alpha=0.85, edgecolor='white', linewidth=0.5)
    ax1.axvline(0, color='#7f8c8d', linewidth=1, alpha=0.7)
    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=9)
    ax1.set_xlabel('Δ Tricks (Team0 − Team1)', fontsize=10)
    ax1.set_title('Per-Scenario Δ Tricks', fontsize=11, fontweight='bold')
    for i, (d, n) in enumerate(zip(deltas, n_hands)):
        ax1.text(d + (0.02 if d >= 0 else -0.02), i, f"{d:+.2f} (n={n:,})",
                 va='center', ha='left' if d >= 0 else 'right', fontsize=8, color='#2c3e50')

    ax2 = fig.add_subplot(gs[0, 1])
    loss_pct = [lr * 100 for lr in loss_rates]
    push_pct = [pr * 100 for pr in push_rates]
    win_pct = [wr * 100 for wr in win_rates]
    ax2.barh(y, loss_pct, color=OUTCOME_COLORS['loss'], alpha=0.85, edgecolor='white', linewidth=0.5, label='Loss (≤4)')
    ax2.barh(y, push_pct, left=loss_pct, color=OUTCOME_COLORS['push'], alpha=0.85, edgecolor='white', linewidth=0.5, label='Push (5)')
    ax2.barh(y, win_pct, left=[a + b for a, b in zip(loss_pct, push_pct)],
             color=OUTCOME_COLORS['win'], alpha=0.85, edgecolor='white', linewidth=0.5, label='Win (≥6)')
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels, fontsize=9)
    ax2.set_xlim(0, 100)
    ax2.set_xlabel('Outcome Rate (%)', fontsize=10)
    ax2.set_title('Team0 Outcomes by Scenario', fontsize=11, fontweight='bold')
    ax2.legend(loc='lower right', fontsize=8, framealpha=0.9)

    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(avg0, y, marker='o', label='Team0', color='#2c3e50')
    ax3.plot(avg1, y, marker='o', label='Team1', color='#95a5a6')
    ax3.axvline(5.0, color='#bdc3c7', linestyle='--', linewidth=1, alpha=0.6)
    ax3.set_yticks(y)
    ax3.set_yticklabels(labels, fontsize=9)
    ax3.set_xlabel('Average Tricks', fontsize=10)
    ax3.set_title('Average Tricks by Scenario', fontsize=11, fontweight='bold')
    ax3.set_xlim(3, 8)
    ax3.legend(loc='lower right', fontsize=8, framealpha=0.9)

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.axis('off')
    total_n = sum(n_hands)
    mean_delta = float(np.average(deltas, weights=n_hands)) if total_n > 0 else float(np.mean(deltas))
    overall_win = float(np.average(win_rates, weights=n_hands)) if total_n > 0 else float(np.mean(win_rates))
    ax4.text(0.02, 0.95, '\n'.join([
        f"Matchup: {_pretty_matchup_name(matchup_name)}",
        f"Scenarios: {len(labels)}",
        f"Total hands: {total_n:,}",
        '',
        f"Weighted mean Δ tricks: {mean_delta:+.3f}",
        f"Weighted win rate: {overall_win*100:.1f}%",
        '',
        'Win: Team0 tricks ≥ 6',
        'Push: Team0 tricks = 5',
    ]),
    va='top', ha='left', fontsize=10,
    bbox=dict(boxstyle='round', facecolor='white', edgecolor='#ecf0f1', alpha=0.95))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)


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

    # Generate per-matchup detail plots in archive
    print("🧩 Generating per-matchup detail plots...")
    for matchup_name, scenarios in matchup_results.items():
        try:
            plot_matchup_detail(matchup_name, scenarios, os.path.join(matchups_archive, f"{matchup_name}.png"))
        except Exception as e:
            print(f"   ⚠️  Failed matchup plot {matchup_name}: {e}")
    
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

