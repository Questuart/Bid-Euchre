#!/usr/bin/env python3
"""
Trick Strategy Dashboard Generator for Bid Euchre Simulations.

Consolidates strategy performance analysis into a comprehensive dashboard:
- Comparison matrix (head-to-head win rates)
- Outcome distributions vs baseline
- Top performers by contract type
- Summary statistics

Works for both head_to_head_matrix and head_to_head modes.

Usage:
    PYTHONPATH=src python experiments/generate_trick_strategy_dashboard.py \\
        --run-dir data/runs/<run_id> \\
        --baseline random_legal
"""

import os
import sys
import json
import argparse
from glob import glob
from typing import Dict, Optional

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Import reporting framework
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bid_euchre.reporting import (
    apply_report_style, get_report_paths,
    ensure_dir, copy_to_latest, write_latest_pointer,
)
from bid_euchre.analysis import wilson_ci

# Apply report styling
apply_report_style()


# ============================================================================
# Data Loading
# ============================================================================

def load_matchup_results(run_dir: str) -> Dict:
    """Load all matchup results from a run directory."""
    paths = get_report_paths(run_dir)
    results_dir = paths.results_dir
    
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
    all_team0_tricks = []
    all_team1_tricks = []
    
    for scenario, data in matchup_results.items():
        hands = data["hands"]
        total_hands += hands
        total_team0_tricks += data["avg_team0"] * hands
        total_team1_tricks += data["avg_team1"] * hands
        
        # Count wins (team0 >= 6 tricks)
        dist = data["distribution_team0"]
        total_team0_wins += sum(count for tricks, count in dist.items() if int(tricks) >= 6)
        
        # Collect individual trick counts for violin plots
        for tricks_str, count in dist.items():
            tricks = int(tricks_str)
            all_team0_tricks.extend([tricks] * count)
        
        dist_t1 = data.get("distribution_team1", {})
        for tricks_str, count in dist_t1.items():
            tricks = int(tricks_str)
            all_team1_tricks.extend([tricks] * count)
    
    avg_team0 = total_team0_tricks / total_hands if total_hands > 0 else 0
    avg_team1 = total_team1_tricks / total_hands if total_hands > 0 else 0
    
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
        "team0_tricks_dist": all_team0_tricks,
        "team1_tricks_dist": all_team1_tricks,
    }


# ============================================================================
# Plotting Functions
# ============================================================================

def plot_comparison_matrix(ax, all_stats: Dict):
    """Generate comparison matrix heatmap."""
    # Extract unique strategies
    strategies = set()
    for matchup_name in all_stats.keys():
        team0, team1 = matchup_name.split("_vs_")
        strategies.add(team0)
        strategies.add(team1)
    
    strategies = sorted(strategies)
    n = len(strategies)
    
    if n == 0:
        ax.text(0.5, 0.5, "No matchup data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Head-to-Head Win Rate Matrix")
        return
    
    # Build matrix: matrix[i][j] = win rate of strategy i vs strategy j
    matrix = np.full((n, n), np.nan)
    
    for matchup_name, stats in all_stats.items():
        team0, team1 = matchup_name.split("_vs_")
        i = strategies.index(team0)
        j = strategies.index(team1)
        matrix[i, j] = stats['win_rate'] * 100  # Convert to percentage
    
    # Create heatmap
    im = ax.imshow(matrix, cmap='RdYlGn', vmin=0, vmax=100, aspect='auto')
    
    # Add text annotations
    for i in range(n):
        for j in range(n):
            if not np.isnan(matrix[i, j]):
                text_color = "black" if 30 < matrix[i, j] < 70 else "white"
                ax.text(j, i, f"{matrix[i, j]:.1f}%",
                       ha="center", va="center", color=text_color,
                       fontsize=8, fontweight="bold")
    
    # Set ticks and labels
    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    ax.set_xticklabels(strategies, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(strategies, fontsize=9)
    
    ax.set_xlabel("Team 1 (Opponent)", fontsize=10, fontweight="bold")
    ax.set_ylabel("Team 0 (Player)", fontsize=10, fontweight="bold")
    ax.set_title("Win Rate Matrix (%)", fontsize=11, fontweight="bold", pad=10)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Win Rate (%)", rotation=270, labelpad=15, fontsize=9)


def plot_strategy_vs_baseline_violin(ax, all_stats: Dict, baseline: str):
    """Violin plot of strategy performance vs baseline."""
    # Find matchups against baseline
    vs_baseline_stats = {}
    for matchup_name, stats in all_stats.items():
        if f"_vs_{baseline}" in matchup_name and matchup_name != f"{baseline}_vs_{baseline}":
            strategy = matchup_name.replace(f"_vs_{baseline}", "")
            vs_baseline_stats[strategy] = stats
    
    if not vs_baseline_stats:
        ax.text(0.5, 0.5, f"No matchups vs {baseline}", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"Performance vs {baseline}")
        return
    
    # Sort by delta tricks
    sorted_strategies = sorted(vs_baseline_stats.keys(), 
                               key=lambda s: vs_baseline_stats[s]['delta_tricks'], 
                               reverse=True)
    
    # Prepare data for violin plot
    positions = list(range(len(sorted_strategies)))
    data_for_violin = [vs_baseline_stats[s]['team0_tricks_dist'] for s in sorted_strategies]
    
    # Create violin plots
    parts = ax.violinplot(data_for_violin, positions=positions,
                          showmeans=True, showmedians=False, widths=0.7)
    
    # Color by performance
    for i, (pc, strategy) in enumerate(zip(parts['bodies'], sorted_strategies)):
        delta = vs_baseline_stats[strategy]['delta_tricks']
        if delta > 0.1:
            color = '#2ecc71'  # Green - better
        elif delta < -0.1:
            color = '#e74c3c'  # Red - worse
        else:
            color = '#f39c12'  # Orange - similar
        pc.set_facecolor(color)
        pc.set_alpha(0.6)
        pc.set_edgecolor('#2c3e50')
    
    parts['cmeans'].set_color('#2c3e50')
    parts['cmeans'].set_linewidth=2
    
    # Add delta annotations
    for pos, strategy in enumerate(sorted_strategies):
        delta = vs_baseline_stats[strategy]['delta_tricks']
        y_pos = 10.3
        ax.text(pos, y_pos, f"{delta:+.2f}", ha="center", fontsize=7, 
                fontweight="bold", color="black")
    
    ax.set_xticks(positions)
    ax.set_xticklabels(sorted_strategies, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Tricks Won", fontsize=10)
    ax.set_title(f"Performance vs {baseline}\n(Δ tricks shown above)", 
                fontsize=11, fontweight="bold", pad=10)
    ax.set_ylim(-0.5, 10.8)
    ax.axhline(5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)


def plot_win_rate_bars(ax, all_stats: Dict, baseline: str):
    """Bar chart of win rates vs baseline with confidence intervals."""
    # Find matchups against baseline
    vs_baseline_stats = {}
    for matchup_name, stats in all_stats.items():
        if f"_vs_{baseline}" in matchup_name and matchup_name != f"{baseline}_vs_{baseline}":
            strategy = matchup_name.replace(f"_vs_{baseline}", "")
            vs_baseline_stats[strategy] = stats
    
    if not vs_baseline_stats:
        ax.text(0.5, 0.5, f"No matchups vs {baseline}", ha="center", va="center", transform=ax.transAxes)
        ax.set_title(f"Win Rates vs {baseline}")
        return
    
    # Sort by win rate
    sorted_strategies = sorted(vs_baseline_stats.keys(), 
                               key=lambda s: vs_baseline_stats[s]['win_rate'], 
                               reverse=True)
    
    win_rates = [vs_baseline_stats[s]['win_rate'] * 100 for s in sorted_strategies]
    ci_lowers = [vs_baseline_stats[s]['win_rate_ci_lower'] * 100 for s in sorted_strategies]
    ci_uppers = [vs_baseline_stats[s]['win_rate_ci_upper'] * 100 for s in sorted_strategies]
    
    # Compute error bars
    yerr_lower = [wr - ci_l for wr, ci_l in zip(win_rates, ci_lowers)]
    yerr_upper = [ci_u - wr for wr, ci_u in zip(win_rates, ci_uppers)]
    
    positions = np.arange(len(sorted_strategies))
    
    # Color by significance
    colors = []
    for strategy in sorted_strategies:
        ci_lower = vs_baseline_stats[strategy]['win_rate_ci_lower']
        ci_upper = vs_baseline_stats[strategy]['win_rate_ci_upper']
        if ci_lower > 0.50:
            colors.append('#2ecc71')  # Green - significantly better
        elif ci_upper < 0.50:
            colors.append('#e74c3c')  # Red - significantly worse
        else:
            colors.append('#95a5a6')  # Gray - not significant
    
    bars = ax.bar(positions, win_rates, yerr=[yerr_lower, yerr_upper], 
                  color=colors, alpha=0.8, capsize=4, edgecolor="white")
    
    # Add 50% reference line
    ax.axhline(50, color="#2c3e50", linestyle="--", linewidth=1.5, alpha=0.7, label="50% (even)")
    
    # Add win rate labels
    for i, (bar, wr) in enumerate(zip(bars, win_rates)):
        ax.text(bar.get_x() + bar.get_width()/2, wr + yerr_upper[i] + 1, 
                f"{wr:.1f}%", ha="center", va="bottom", fontsize=7, fontweight="bold")
    
    ax.set_xticks(positions)
    ax.set_xticklabels(sorted_strategies, rotation=45, ha="right", fontsize=9)
    ax.set_ylabel("Win Rate (%) ± 95% CI", fontsize=10)
    ax.set_title(f"Win Rates vs {baseline}", fontsize=11, fontweight="bold", pad=10)
    ax.set_ylim(0, 105)
    ax.legend(loc="upper right", fontsize=8)


def plot_summary_table(ax, all_stats: Dict, baseline: str):
    """Summary statistics table."""
    ax.axis('tight')
    ax.axis('off')
    
    # Find matchups against baseline
    vs_baseline_stats = {}
    for matchup_name, stats in all_stats.items():
        if f"_vs_{baseline}" in matchup_name and matchup_name != f"{baseline}_vs_{baseline}":
            strategy = matchup_name.replace(f"_vs_{baseline}", "")
            vs_baseline_stats[strategy] = stats
    
    if not vs_baseline_stats:
        ax.text(0.5, 0.5, f"No matchups vs {baseline}", ha="center", va="center", transform=ax.transAxes)
        return
    
    # Sort by delta tricks
    sorted_strategies = sorted(vs_baseline_stats.keys(), 
                               key=lambda s: vs_baseline_stats[s]['delta_tricks'], 
                               reverse=True)
    
    # Build table data
    headers = ["Strategy", "Δ Tricks", "Win Rate", "95% CI", "Status"]
    table_data = []
    
    for strategy in sorted_strategies:
        stats = vs_baseline_stats[strategy]
        delta = stats['delta_tricks']
        win_rate = stats['win_rate'] * 100
        ci_lower = stats['win_rate_ci_lower'] * 100
        ci_upper = stats['win_rate_ci_upper'] * 100
        
        # Determine status
        if ci_lower > 50:
            status = "✅ Better"
        elif ci_upper < 50:
            status = "❌ Worse"
        else:
            status = "➖ Similar"
        
        table_data.append([
            strategy,
            f"{delta:+.3f}",
            f"{win_rate:.1f}%",
            f"[{ci_lower:.1f}, {ci_upper:.1f}]",
            status
        ])
    
    # Create table
    table = ax.table(cellText=table_data, colLabels=headers,
                    cellLoc='left', loc='center',
                    colWidths=[0.25, 0.15, 0.15, 0.25, 0.20])
    
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 1.8)
    
    # Style header
    for i in range(len(headers)):
        cell = table[(0, i)]
        cell.set_facecolor('#34495e')
        cell.set_text_props(weight='bold', color='white')
    
    # Color code rows
    for i, strategy in enumerate(sorted_strategies):
        stats = vs_baseline_stats[strategy]
        ci_lower = stats['win_rate_ci_lower']
        ci_upper = stats['win_rate_ci_upper']
        
        if ci_lower > 0.50:
            color = '#d5f4e6'  # Light green
        elif ci_upper < 0.50:
            color = '#fadbd8'  # Light red
        else:
            color = '#f8f9fa'  # Light gray
        
        for j in range(len(headers)):
            table[(i+1, j)].set_facecolor(color)
    
    ax.set_title(f"Summary Statistics vs {baseline}", 
                fontsize=11, fontweight="bold", pad=10, loc='left')


# ============================================================================
# Main Report Generation
# ============================================================================

def generate_trick_strategy_dashboard(run_dir: str, baseline: str = "random_legal", 
                                      output_dir: Optional[str] = None) -> str:
    """
    Generate trick strategy dashboard.
    
    Writes to standardized archive + latest pattern:
        <run_dir>/reports/trick_strategy/
        ├── comprehensive_dashboard.png (latest)
        ├── summary.md (latest)
        └── _history/<timestamp>/ (archived version)
    
    Args:
        run_dir: Base run directory
        baseline: Baseline strategy for comparison
        output_dir: Optional override for output location
    
    Returns:
        Path to latest comprehensive_dashboard.png
    """
    print("=" * 70)
    print("🎯 Generating Trick Strategy Dashboard")
    print("=" * 70)
    
    # Load metadata
    meta_path = os.path.join(run_dir, "meta.json")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"meta.json not found in {run_dir}")
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    # Load matchup results
    print("📂 Loading matchup results...")
    matchup_data = load_matchup_results(run_dir)
    print(f"   Loaded {len(matchup_data)} matchups")
    
    # Compute statistics
    print("📊 Computing statistics...")
    all_stats = {}
    for matchup_name, results in matchup_data.items():
        all_stats[matchup_name] = compute_matchup_stats(results)
    print(f"   Computed stats for {len(all_stats)} matchups")
    
    # Determine output paths
    paths = get_report_paths(run_dir)
    
    if output_dir:
        archive_dir = output_dir
        latest_dir = output_dir
    else:
        archive_dir = paths.trick_strategy_archive
        latest_dir = paths.trick_strategy_root
    
    ensure_dir(archive_dir)
    ensure_dir(latest_dir)
    
    # Create comprehensive dashboard (2x2 layout)
    fig = plt.figure(figsize=(16, 12))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3,
                          left=0.08, right=0.95, top=0.93, bottom=0.07)
    
    print("📊 Generating plots...")
    
    ax1 = fig.add_subplot(gs[0, 0])
    plot_comparison_matrix(ax1, all_stats)
    print("   ✅ Comparison matrix")
    
    ax2 = fig.add_subplot(gs[0, 1])
    plot_strategy_vs_baseline_violin(ax2, all_stats, baseline)
    print("   ✅ Strategy vs baseline violin")
    
    ax3 = fig.add_subplot(gs[1, 0])
    plot_win_rate_bars(ax3, all_stats, baseline)
    print("   ✅ Win rate bars")
    
    ax4 = fig.add_subplot(gs[1, 1])
    plot_summary_table(ax4, all_stats, baseline)
    print("   ✅ Summary table")
    
    # Add overall title
    run_id = meta.get("run_id", "Unknown")
    fig.suptitle(f"Trick Strategy Dashboard: {run_id}", 
                fontsize=14, fontweight="bold", y=0.98)
    
    # Save to archive
    archive_png = os.path.join(archive_dir, "comprehensive_dashboard.png")
    fig.savefig(archive_png, dpi=150, bbox_inches="tight")
    print(f"   💾 Saved to archive: {archive_png}")
    
    # Copy to latest
    latest_png = os.path.join(latest_dir, "comprehensive_dashboard.png")
    copy_to_latest(archive_png, latest_png)
    print(f"   💾 Saved to latest: {latest_png}")
    
    plt.close(fig)
    
    # Generate summary markdown
    generate_summary_md(run_dir, all_stats, baseline, latest_dir, archive_dir, paths.timestamp)
    
    # Write latest pointer
    if not output_dir:
        relative_archive = os.path.relpath(archive_dir, latest_dir)
        write_latest_pointer(latest_dir, relative_archive)
    
    print("=" * 70)
    print("✅ Trick strategy dashboard generated successfully!")
    print(f"📁 Latest: {latest_png}")
    print("=" * 70)
    
    return latest_png


def generate_summary_md(run_dir: str, all_stats: Dict, baseline: str,
                       latest_dir: str, archive_dir: str, timestamp: str):
    """Generate summary markdown."""
    lines = []
    lines.append("# Trick Strategy Dashboard Summary\n\n")
    
    # Load metadata
    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    
    lines.append("## Run Information\n\n")
    lines.append(f"- **Run ID**: {meta.get('run_id', 'Unknown')}\n")
    lines.append(f"- **Experiment**: {meta.get('experiment_name', 'Unknown')}\n")
    lines.append(f"- **Mode**: {meta.get('mode', 'Unknown')}\n")
    lines.append(f"- **Baseline**: {baseline}\n\n")
    
    # Performance vs baseline
    lines.append(f"## Performance vs {baseline}\n\n")
    
    vs_baseline_stats = {}
    for matchup_name, stats in all_stats.items():
        if f"_vs_{baseline}" in matchup_name and matchup_name != f"{baseline}_vs_{baseline}":
            strategy = matchup_name.replace(f"_vs_{baseline}", "")
            vs_baseline_stats[strategy] = stats
    
    if vs_baseline_stats:
        # Sort by delta tricks
        sorted_strategies = sorted(vs_baseline_stats.keys(), 
                                   key=lambda s: vs_baseline_stats[s]['delta_tricks'], 
                                   reverse=True)
        
        lines.append("| Strategy | Δ Tricks | Win Rate | 95% CI | Status |\n")
        lines.append("|----------|----------|----------|--------|--------|\n")
        
        for strategy in sorted_strategies:
            stats = vs_baseline_stats[strategy]
            delta = stats['delta_tricks']
            win_rate = stats['win_rate'] * 100
            ci_lower = stats['win_rate_ci_lower'] * 100
            ci_upper = stats['win_rate_ci_upper'] * 100
            
            if ci_lower > 50:
                status = "✅ Better"
            elif ci_upper < 50:
                status = "❌ Worse"
            else:
                status = "➖ Similar"
            
            lines.append(f"| {strategy} | {delta:+.3f} | {win_rate:.1f}% | [{ci_lower:.1f}, {ci_upper:.1f}] | {status} |\n")
        
        lines.append("\n")
    
    # Top performers
    lines.append("## Top Performers\n\n")
    if vs_baseline_stats:
        top3 = sorted_strategies[:3]
        for i, strategy in enumerate(top3, 1):
            stats = vs_baseline_stats[strategy]
            lines.append(f"{i}. **{strategy}**: Δ {stats['delta_tricks']:+.3f} tricks, {stats['win_rate']*100:.1f}% win rate\n")
        lines.append("\n")
    
    # Report details
    lines.append("## Report Details\n\n")
    lines.append(f"- **Generated**: {timestamp}\n")
    lines.append(f"- **Archive**: `{os.path.relpath(archive_dir, run_dir)}`\n")
    
    summary_path = os.path.join(latest_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.writelines(lines)
    
    print(f"   📝 Summary saved: {summary_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate trick strategy dashboard")
    parser.add_argument("--run-dir", type=str, required=True, help="Path to run directory")
    parser.add_argument("--baseline", type=str, default="random_legal", help="Baseline strategy")
    parser.add_argument("--output-dir", type=str, help="Override output directory")
    return parser.parse_args()


def main():
    args = parse_args()
    generate_trick_strategy_dashboard(args.run_dir, args.baseline, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
