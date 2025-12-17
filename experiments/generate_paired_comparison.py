#!/usr/bin/env python3
"""
Generate Paired Strategy Comparison Report (Statistical Rigor Edition).

Uses JSONL logs as source of truth for paired deal-level comparisons.
Includes confidence intervals, effect sizes, and proper statistical tests.

Usage:
    PYTHONPATH=src python experiments/generate_paired_comparison.py \\
        --run-dir data/runs/<run_id> --baseline random_legal
"""

import os
import json
import argparse
from glob import glob
from datetime import datetime
from collections import defaultdict
from typing import Dict, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats as scipy_stats

# Import our analysis utilities
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bid_euchre.analysis import (
    load_paired_data,
    compute_paired_deltas,
    paired_comparison_summary,
    wilson_ci,
    mean_with_ci,
)

# Strategy display configuration
STRATEGY_NAMES = {
    "greedy": "Greedy",
    "improved_greedy": "Improved Greedy",
    "random_legal": "Random Legal",
    "always_lowest": "Always Lowest",
    "always_highest": "Always Highest",
}

STRATEGY_COLORS = {
    "greedy": "#2ecc71",
    "improved_greedy": "#27ae60",
    "random_legal": "#95a5a6",
    "always_lowest": "#3498db",
    "always_highest": "#e74c3c",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generate paired strategy comparison")
    parser.add_argument("--run-dir", type=str, required=True)
    parser.add_argument("--baseline", type=str, default="random_legal")
    parser.add_argument("--output-dir", type=str, help="Override output directory")
    return parser.parse_args()


def plot_paired_comparison(
    run_dir: str,
    baseline: str,
    output_dir: str
):
    """Generate comprehensive paired comparison report."""
    
    # Load metadata
    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    
    strategies = meta["strategies"]
    
    # Load paired data from JSONL
    print("📂 Loading paired data from JSONL logs...")
    strategy_data = load_paired_data(run_dir, strategies)
    print(f"   Loaded {len(strategy_data)} strategies")
    
    # Create figure
    fig = plt.figure(figsize=(18, 12))
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.3)
    
    fig.suptitle(
        f"PAIRED STRATEGY COMPARISON — Baseline: {STRATEGY_NAMES.get(baseline, baseline).upper()} (Common Deals)",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )
    
    # Panel 1: Paired Delta Distribution (violin plots)
    ax1 = fig.add_subplot(gs[0, :2])
    plot_paired_delta_distribution(ax1, strategy_data, baseline)
    
    # Panel 2: Win Rate with CI (Wilson intervals)
    ax2 = fig.add_subplot(gs[0, 2])
    plot_win_rate_with_ci(ax2, strategy_data, baseline)
    
    # Panel 3-4: Per-Scenario Paired Deltas (2 heatmaps)
    ax3 = fig.add_subplot(gs[1, :])
    plot_paired_delta_heatmap(ax3, strategy_data, baseline)
    
    # Panel 5: % Deals Improved (bar chart)
    ax5 = fig.add_subplot(gs[2, 0])
    plot_pct_improved(ax5, strategy_data, baseline)
    
    # Panel 6: Mean Delta with CI (error bars)
    ax6 = fig.add_subplot(gs[2, 1])
    plot_mean_delta_with_ci(ax6, strategy_data, baseline)
    
    # Panel 7: Summary Table
    ax7 = fig.add_subplot(gs[2, 2])
    plot_paired_summary_table(ax7, strategy_data, baseline)
    
    plt.tight_layout()
    plt.savefig(output_dir + "/paired_comparison.png", dpi=150, bbox_inches="tight")
    print(f"✅ Paired comparison saved: {output_dir}/paired_comparison.png")
    plt.close()


def plot_paired_delta_distribution(ax, strategy_data, baseline):
    """Violin plot of paired Δ tricks distribution."""
    strategies = [s for s in sorted(strategy_data.keys()) if s != baseline]
    
    delta_distributions = []
    labels = []
    for strategy in strategies:
        # Aggregate across all scenarios
        all_deltas = []
        for scenario in strategy_data[baseline].keys():
            paired = compute_paired_deltas(strategy_data, baseline, strategy, scenario)
            all_deltas.extend(paired["deltas"])
        
        if all_deltas:
            delta_distributions.append(all_deltas)
            labels.append(STRATEGY_NAMES.get(strategy, strategy))
    
    if delta_distributions:
        parts = ax.violinplot(
            delta_distributions,
            positions=range(len(labels)),
            widths=0.7,
            showmeans=True,
            showmedians=True,
        )
        
        for pc in parts["bodies"]:
            pc.set_facecolor("#3498db")
            pc.set_alpha(0.6)
        
        # Add mean markers
        for i, deltas in enumerate(delta_distributions):
            mean_val = np.mean(deltas)
            ax.plot(i, mean_val, 'ro', markersize=6, label='Mean' if i == 0 else '')
    
    ax.axhline(0, color="black", linestyle="-", linewidth=1.5, alpha=0.7, label="No difference")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("Δ Tricks (vs baseline)", fontsize=10)
    ax.set_title("Paired Trick Delta Distribution (per deal)", fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)


def plot_win_rate_with_ci(ax, strategy_data, baseline):
    """Win rate comparison with Wilson CI error bars."""
    strategies = sorted(strategy_data.keys())
    
    win_rates = []
    ci_lowers = []
    ci_uppers = []
    
    for strategy in strategies:
        all_wins = 0
        all_hands = 0
        
        for scenario in strategy_data[strategy].keys():
            records = strategy_data[strategy][scenario]
            wins = sum(1 for r in records if r["t0"] >= 6)
            all_wins += wins
            all_hands += len(records)
        
        # Wilson CI for proportion
        p, lower, upper = wilson_ci(all_wins, all_hands, confidence=0.95)
        win_rates.append(p * 100)
        ci_lowers.append(lower * 100)
        ci_uppers.append(upper * 100)
    
    colors = [STRATEGY_COLORS.get(s, "#95a5a6") for s in strategies]
    
    # Plot bars with error bars
    x_pos = range(len(strategies))
    bars = ax.bar(x_pos, win_rates, color=colors, alpha=0.7)
    
    # Add Wilson CI error bars
    yerr_lower = [win_rates[i] - ci_lowers[i] for i in range(len(strategies))]
    yerr_upper = [ci_uppers[i] - win_rates[i] for i in range(len(strategies))]
    ax.errorbar(
        x_pos, win_rates,
        yerr=[yerr_lower, yerr_upper],
        fmt='none',
        ecolor='black',
        capsize=4,
        linewidth=1.5,
        alpha=0.7,
    )
    
    # Highlight baseline
    baseline_idx = strategies.index(baseline)
    bars[baseline_idx].set_edgecolor("black")
    bars[baseline_idx].set_linewidth(2.5)
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], rotation=15, ha="right", fontsize=9)
    ax.set_ylabel("Win Rate (%) ± 95% CI", fontsize=10)
    ax.set_title("Win Rate (≥6 tricks) with Wilson CI", fontsize=11, fontweight="bold")
    ax.axhline(50.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_ylim(35, 50)
    ax.grid(axis="y", alpha=0.3)


def plot_paired_delta_heatmap(ax, strategy_data, baseline):
    """Heatmap of paired mean Δ tricks by strategy × scenario."""
    scenarios = sorted(list(strategy_data[baseline].keys()))
    strategies = [s for s in sorted(strategy_data.keys()) if s != baseline]
    
    # Build matrix of paired deltas
    matrix = np.zeros((len(strategies), len(scenarios)))
    
    for i, strategy in enumerate(strategies):
        for j, scenario in enumerate(scenarios):
            paired = compute_paired_deltas(strategy_data, baseline, strategy, scenario)
            if paired["n_matched"] > 0:
                matrix[i, j] = np.mean(paired["deltas"])
            else:
                matrix[i, j] = np.nan
    
    # Plot heatmap (RdBu_r is diverging around 0)
    im = ax.imshow(matrix, aspect="auto", cmap="RdBu_r", vmin=-0.5, vmax=0.5)
    
    # Add text annotations
    for i in range(len(strategies)):
        for j in range(len(scenarios)):
            if not np.isnan(matrix[i, j]):
                value = matrix[i, j]
                text_color = "white" if abs(value) > 0.25 else "black"
                ax.text(
                    j, i,
                    f"{value:+.3f}",
                    ha="center", va="center",
                    color=text_color,
                    fontsize=8,
                    fontweight="bold" if abs(value) > 0.1 else "normal"
                )
    
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels(scenarios, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(strategies)))
    ax.set_yticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], fontsize=9)
    ax.set_title(
        f"Paired Mean Δ Tricks by Scenario (vs {STRATEGY_NAMES.get(baseline, baseline)})",
        fontsize=11,
        fontweight="bold"
    )
    
    cbar = plt.colorbar(im, ax=ax, orientation="vertical", pad=0.02)
    cbar.set_label("Δ Tricks (+ = better)", fontsize=9)


def plot_pct_improved(ax, strategy_data, baseline):
    """Bar chart of % deals improved vs baseline."""
    strategies = [s for s in sorted(strategy_data.keys()) if s != baseline]
    
    pct_improved = []
    for strategy in strategies:
        all_deltas = []
        for scenario in strategy_data[baseline].keys():
            paired = compute_paired_deltas(strategy_data, baseline, strategy, scenario)
            all_deltas.extend(paired["deltas"])
        
        summary = paired_comparison_summary(all_deltas)
        pct_improved.append(summary["pct_improved"])
    
    colors = [STRATEGY_COLORS.get(s, "#95a5a6") for s in strategies]
    bars = ax.barh(range(len(strategies)), pct_improved, color=colors, alpha=0.7)
    
    ax.axvline(50.0, color="black", linestyle="-", linewidth=1.5, alpha=0.7)
    ax.set_yticks(range(len(strategies)))
    ax.set_yticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], fontsize=9)
    ax.set_xlabel("% of Deals with More Tricks", fontsize=10)
    ax.set_title("% Deals Improved vs Baseline", fontsize=11, fontweight="bold")
    ax.set_xlim(0, 100)
    ax.grid(axis="x", alpha=0.3)
    
    # Add value labels
    for i, (bar, pct) in enumerate(zip(bars, pct_improved)):
        ax.text(pct + 1, i, f"{pct:.1f}%", va="center", fontsize=8)


def plot_mean_delta_with_ci(ax, strategy_data, baseline):
    """Mean Δ tricks with 95% CI (paired t-interval)."""
    strategies = [s for s in sorted(strategy_data.keys()) if s != baseline]
    
    means = []
    ci_lowers = []
    ci_uppers = []
    
    for strategy in strategies:
        all_deltas = []
        for scenario in strategy_data[baseline].keys():
            paired = compute_paired_deltas(strategy_data, baseline, strategy, scenario)
            all_deltas.extend(paired["deltas"])
        
        summary = paired_comparison_summary(all_deltas)
        means.append(summary["mean_delta"])
        ci_lowers.append(summary["ci_lower"])
        ci_uppers.append(summary["ci_upper"])
    
    colors = [STRATEGY_COLORS.get(s, "#95a5a6") for s in strategies]
    
    # Horizontal bar chart
    y_pos = range(len(strategies))
    bars = ax.barh(y_pos, means, color=colors, alpha=0.7, height=0.6)
    
    # Add CI error bars
    xerr_lower = [means[i] - ci_lowers[i] for i in range(len(strategies))]
    xerr_upper = [ci_uppers[i] - means[i] for i in range(len(strategies))]
    ax.errorbar(
        means, y_pos,
        xerr=[xerr_lower, xerr_upper],
        fmt='none',
        ecolor='black',
        capsize=4,
        linewidth=1.5,
        alpha=0.7,
    )
    
    ax.axvline(0, color="black", linestyle="-", linewidth=1.5, alpha=0.7)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], fontsize=9)
    ax.set_xlabel("Mean Δ Tricks ± 95% CI (paired)", fontsize=10)
    ax.set_title("Mean Trick Delta (Paired T-Test)", fontsize=11, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    
    # Add value labels
    for i, (m, bar) in enumerate(zip(means, bars)):
        label = f"{m:+.3f}"
        x_pos = m + 0.02 if m > 0 else m - 0.02
        ha = "left" if m > 0 else "right"
        ax.text(x_pos, i, label, va="center", ha=ha, fontsize=8, fontweight="bold")


def plot_paired_summary_table(ax, strategy_data, baseline):
    """Summary table with paired statistics."""
    ax.axis("off")
    
    strategies = [s for s in sorted(strategy_data.keys()) if s != baseline]
    
    table_data = []
    table_data.append(["Strategy", "Mean Δ", "95% CI", "% Better", "% Worse", "n"])
    
    for strategy in strategies:
        all_deltas = []
        for scenario in strategy_data[baseline].keys():
            paired = compute_paired_deltas(strategy_data, baseline, strategy, scenario)
            all_deltas.extend(paired["deltas"])
        
        summary = paired_comparison_summary(all_deltas)
        
        row = [
            STRATEGY_NAMES.get(strategy, strategy),
            f"{summary['mean_delta']:+.3f}",
            f"[{summary['ci_lower']:+.3f}, {summary['ci_upper']:+.3f}]",
            f"{summary['pct_improved']:.1f}%",
            f"{summary['pct_worse']:.1f}%",
            f"{summary['n']:,}",
        ]
        table_data.append(row)
    
    table = ax.table(
        cellText=table_data,
        cellLoc="center",
        loc="center",
        colWidths=[0.20, 0.12, 0.22, 0.12, 0.12, 0.12],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 2)
    
    # Style header
    for j in range(len(table_data[0])):
        cell = table[(0, j)]
        cell.set_facecolor("#34495e")
        cell.set_text_props(weight="bold", color="white")
    
    ax.set_title(
        f"Paired Comparison Summary (vs {STRATEGY_NAMES.get(baseline, baseline)})",
        fontsize=11,
        fontweight="bold",
        pad=10
    )


def main():
    args = parse_args()
    
    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(args.run_dir, "dashboard", f"paired_{timestamp}")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print("🎯 Generating Paired Strategy Comparison Report")
    print("=" * 60)
    
    # Generate report
    plot_paired_comparison(args.run_dir, args.baseline, output_dir)
    
    # Also generate summary markdown
    generate_summary_markdown(args.run_dir, args.baseline, output_dir)
    
    print(f"\n📁 Output directory: {output_dir}/")
    print(f"   • paired_comparison.png")
    print(f"   • summary.md")
    print()


def generate_summary_markdown(run_dir: str, baseline: str, output_dir: str):
    """Generate summary.md with key metrics."""
    # Load metadata
    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path) as f:
        meta = json.load(f)
    
    strategies = meta["strategies"]
    strategy_data = load_paired_data(run_dir, strategies)
    
    lines = []
    lines.append(f"# Strategy Comparison Summary\n")
    lines.append(f"**Run**: `{meta['run_id']}`  ")
    lines.append(f"**Baseline**: {STRATEGY_NAMES.get(baseline, baseline)}  ")
    lines.append(f"**Date**: {meta['timestamp']}  ")
    lines.append(f"**Total Hands**: {meta['total_hands']:,}  ")
    lines.append(f"**Common Deals**: {meta['common_deals']}  \n")
    
    lines.append("## Paired Comparison Results\n")
    lines.append("| Strategy | Mean Δ Tricks | 95% CI | % Improved | % Worse | n |\n")
    lines.append("|----------|---------------|--------|------------|---------|---|\n")
    
    for strategy in sorted(strategy_data.keys()):
        if strategy == baseline:
            continue
        
        all_deltas = []
        for scenario in strategy_data[baseline].keys():
            paired = compute_paired_deltas(strategy_data, baseline, strategy, scenario)
            all_deltas.extend(paired["deltas"])
        
        summary = paired_comparison_summary(all_deltas)
        
        lines.append(
            f"| {STRATEGY_NAMES.get(strategy, strategy)} | "
            f"{summary['mean_delta']:+.3f} | "
            f"[{summary['ci_lower']:+.3f}, {summary['ci_upper']:+.3f}] | "
            f"{summary['pct_improved']:.1f}% | "
            f"{summary['pct_worse']:.1f}% | "
            f"{summary['n']:,} |\n"
        )
    
    lines.append("\n## Performance Metrics\n")
    if "performance" in meta:
        perf = meta["performance"]
        lines.append(f"- **Duration**: {perf['total_duration_human']}  \n")
        lines.append(f"- **Throughput**: {perf['overall_throughput_hands_per_sec']:.0f} hands/sec  \n")
    
    lines.append("\n## Interpretation\n")
    lines.append("- **Mean Δ**: Average difference in Team 0 tricks per deal\n")
    lines.append("- **95% CI**: Paired t-test confidence interval\n")
    lines.append("- **% Improved**: Percentage of deals where strategy won more tricks than baseline\n")
    lines.append("- **% Worse**: Percentage of deals where strategy won fewer tricks than baseline\n")
    lines.append("- **n**: Number of matched deal pairs\n")
    
    with open(os.path.join(output_dir, "summary.md"), "w") as f:
        f.writelines(lines)
    
    print(f"✅ Summary markdown saved: {output_dir}/summary.md")


if __name__ == "__main__":
    main()

