#!/usr/bin/env python3
"""
Generate Strategy Comparison Report

Loads results from multiple strategies playing identical deals and generates:
- Δ tricks distribution vs greedy (baseline)
- Win rate differences with confidence intervals
- Per-feature performance slices
- Head-to-head comparison tables

Usage:
    PYTHONPATH=src python experiments/generate_strategy_comparison.py --run-dir data/runs/<run_id> --seed 42
"""

import os
import sys
import json
import argparse
from glob import glob
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats as scipy_stats

# Strategy display names
STRATEGY_NAMES = {
    "greedy": "Greedy (1-trick)",
    "random_legal": "Random Legal",
    "always_lowest": "Always Lowest",
    "always_highest": "Always Highest",
}

# Strategy colors
STRATEGY_COLORS = {
    "greedy": "#2ecc71",
    "random_legal": "#95a5a6",
    "always_lowest": "#3498db",
    "always_highest": "#e74c3c",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Generate strategy comparison report")
    parser.add_argument(
        "--run-dir",
        type=str,
        required=True,
        help="Path to run directory containing multi-strategy results",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used in the run",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default="greedy",
        help="Baseline strategy for comparison (default: greedy)",
    )
    return parser.parse_args()


def load_all_strategy_data(run_dir: str) -> Dict[str, Dict]:
    """Load results for all strategies from a run directory."""
    results_dir = os.path.join(run_dir, "results")
    
    # Find all strategy subdirectories
    strategy_dirs = [
        d for d in os.listdir(results_dir)
        if os.path.isdir(os.path.join(results_dir, d))
    ]
    
    all_data = {}
    for strategy in strategy_dirs:
        strategy_path = os.path.join(results_dir, strategy)
        json_files = glob(os.path.join(strategy_path, "*.json"))
        
        strategy_data = {}
        for file_path in json_files:
            with open(file_path, "r") as f:
                data = json.load(f)
                filename = os.path.basename(file_path)
                # Extract scenario key (e.g., "suit_C", "high", "low")
                if filename.startswith("suit_"):
                    scenario = filename.replace(".json", "")
                else:
                    scenario = filename.replace(".json", "")
                strategy_data[scenario] = data
        
        all_data[strategy] = strategy_data
    
    return all_data


def load_jsonl_logs(run_dir: str, strategy: str) -> List[Dict]:
    """Load JSONL logs for a strategy."""
    logs_dir = os.path.join(run_dir, "logs")
    log_files = glob(os.path.join(logs_dir, f"*{strategy}.jsonl"))
    
    records = []
    for log_file in log_files:
        with open(log_file, "r") as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get("event") == "hand_end":
                        records.append(record)
                except json.JSONDecodeError:
                    continue
    
    return records


def compute_strategy_comparison(all_data: Dict[str, Dict], baseline: str = "greedy") -> Dict:
    """
    Compute comparison statistics for all strategies vs baseline.
    
    Returns dict with:
        - mean_tricks_delta: Dict[strategy, float]
        - win_rate_delta: Dict[strategy, float]
        - per_scenario_delta: Dict[strategy, Dict[scenario, float]]
    """
    if baseline not in all_data:
        raise ValueError(f"Baseline strategy '{baseline}' not found in data")
    
    baseline_data = all_data[baseline]
    comparison = {
        "mean_tricks_delta": {},
        "win_rate_delta": {},
        "per_scenario_delta": {},
    }
    
    for strategy, strategy_data in all_data.items():
        if strategy == baseline:
            comparison["mean_tricks_delta"][strategy] = 0.0
            comparison["win_rate_delta"][strategy] = 0.0
            comparison["per_scenario_delta"][strategy] = {}
            continue
        
        # Compute overall mean delta
        baseline_tricks = []
        strategy_tricks = []
        baseline_wins = []
        strategy_wins = []
        
        scenario_deltas = {}
        for scenario in baseline_data.keys():
            if scenario not in strategy_data:
                continue
            
            base = baseline_data[scenario]
            strat = strategy_data[scenario]
            
            # Extract mean tricks (Team0)
            base_mean = base["avg_team0"]
            strat_mean = strat["avg_team0"]
            delta = strat_mean - base_mean
            scenario_deltas[scenario] = delta
            
            baseline_tricks.append(base_mean)
            strategy_tricks.append(strat_mean)
            
            # Extract win rates
            base_wins = sum(
                count for tricks, count in base["distribution_team0"].items()
                if int(tricks) >= 6
            ) / base["hands"]
            strat_wins = sum(
                count for tricks, count in strat["distribution_team0"].items()
                if int(tricks) >= 6
            ) / strat["hands"]
            
            baseline_wins.append(base_wins)
            strategy_wins.append(strat_wins)
        
        comparison["mean_tricks_delta"][strategy] = np.mean(list(scenario_deltas.values()))
        comparison["win_rate_delta"][strategy] = np.mean(strategy_wins) - np.mean(baseline_wins)
        comparison["per_scenario_delta"][strategy] = scenario_deltas
    
    return comparison


def plot_strategy_comparison(all_data: Dict, baseline: str, output_path: str):
    """Generate comprehensive strategy comparison report."""
    
    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.35, wspace=0.3)
    
    fig.suptitle(
        f"STRATEGY COMPARISON REPORT — Baseline: {STRATEGY_NAMES.get(baseline, baseline).upper()}",
        fontsize=14,
        fontweight="bold",
        y=0.98,
    )
    
    # Panel 1: Mean Tricks Comparison (bar chart)
    ax1 = fig.add_subplot(gs[0, 0])
    plot_mean_tricks_comparison(ax1, all_data, baseline)
    
    # Panel 2: Win Rate Comparison (bar chart)
    ax2 = fig.add_subplot(gs[0, 1])
    plot_win_rate_comparison(ax2, all_data, baseline)
    
    # Panel 3: Δ Tricks Distribution (violin plot)
    ax3 = fig.add_subplot(gs[0, 2])
    plot_delta_distribution(ax3, all_data, baseline)
    
    # Panel 4: Per-Scenario Comparison (heatmap)
    ax4 = fig.add_subplot(gs[1, :])
    plot_scenario_heatmap(ax4, all_data, baseline)
    
    # Panel 5: Summary Statistics (table)
    ax5 = fig.add_subplot(gs[2, :])
    plot_summary_table(ax5, all_data, baseline)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"✅ Strategy comparison report saved to: {output_path}")
    plt.close()


def plot_mean_tricks_comparison(ax, all_data: Dict, baseline: str):
    """Bar chart of mean tricks per strategy (all scenarios aggregated)."""
    strategies = sorted(all_data.keys())
    means = []
    stderr = []
    
    for strategy in strategies:
        all_means = []
        for scenario_data in all_data[strategy].values():
            all_means.append(scenario_data["avg_team0"])
        means.append(np.mean(all_means))
        stderr.append(np.std(all_means) / np.sqrt(len(all_means)))
    
    colors = [STRATEGY_COLORS.get(s, "#95a5a6") for s in strategies]
    bars = ax.bar(range(len(strategies)), means, yerr=stderr, color=colors, alpha=0.7, capsize=5)
    
    # Highlight baseline
    baseline_idx = strategies.index(baseline)
    bars[baseline_idx].set_edgecolor("black")
    bars[baseline_idx].set_linewidth(2)
    
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], rotation=15, ha="right")
    ax.set_ylabel("Mean Team 0 Tricks")
    ax.set_title("Mean Tricks (Aggregate)")
    ax.axhline(5.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_ylim(3.5, 6.5)
    ax.grid(axis="y", alpha=0.3)


def plot_win_rate_comparison(ax, all_data: Dict, baseline: str):
    """Bar chart of win rates per strategy."""
    strategies = sorted(all_data.keys())
    win_rates = []
    
    for strategy in strategies:
        all_wins = []
        all_hands = []
        for scenario_data in all_data[strategy].values():
            wins = sum(
                count for tricks, count in scenario_data["distribution_team0"].items()
                if int(tricks) >= 6
            )
            all_wins.append(wins)
            all_hands.append(scenario_data["hands"])
        
        win_rate = sum(all_wins) / sum(all_hands) * 100
        win_rates.append(win_rate)
    
    colors = [STRATEGY_COLORS.get(s, "#95a5a6") for s in strategies]
    bars = ax.bar(range(len(strategies)), win_rates, color=colors, alpha=0.7)
    
    # Highlight baseline
    baseline_idx = strategies.index(baseline)
    bars[baseline_idx].set_edgecolor("black")
    bars[baseline_idx].set_linewidth(2)
    
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], rotation=15, ha="right")
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate (≥6 tricks)")
    ax.axhline(50.0, color="gray", linestyle="--", linewidth=0.8, alpha=0.5)
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.3)


def plot_delta_distribution(ax, all_data: Dict, baseline: str):
    """Violin plot of Δ tricks distribution for each strategy vs baseline."""
    baseline_data = all_data[baseline]
    strategies = [s for s in sorted(all_data.keys()) if s != baseline]
    
    delta_distributions = []
    for strategy in strategies:
        deltas = []
        for scenario in baseline_data.keys():
            if scenario in all_data[strategy]:
                base_mean = baseline_data[scenario]["avg_team0"]
                strat_mean = all_data[strategy][scenario]["avg_team0"]
                deltas.append(strat_mean - base_mean)
        delta_distributions.append(deltas)
    
    parts = ax.violinplot(delta_distributions, positions=range(len(strategies)), widths=0.7, showmeans=True)
    
    for pc in parts["bodies"]:
        pc.set_facecolor("#3498db")
        pc.set_alpha(0.7)
    
    ax.axhline(0, color="black", linestyle="-", linewidth=1.5, alpha=0.7)
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], rotation=15, ha="right")
    ax.set_ylabel(f"Δ Tricks (vs {STRATEGY_NAMES.get(baseline, baseline)})")
    ax.set_title("Trick Delta Distribution")
    ax.grid(axis="y", alpha=0.3)


def plot_scenario_heatmap(ax, all_data: Dict, baseline: str):
    """Heatmap of mean tricks for all strategies across all scenarios."""
    scenarios = sorted(list(all_data[baseline].keys()))
    strategies = sorted(all_data.keys())
    
    # Build matrix: rows = strategies, cols = scenarios
    matrix = np.zeros((len(strategies), len(scenarios)))
    for i, strategy in enumerate(strategies):
        for j, scenario in enumerate(scenarios):
            if scenario in all_data[strategy]:
                matrix[i, j] = all_data[strategy][scenario]["avg_team0"]
            else:
                matrix[i, j] = np.nan
    
    im = ax.imshow(matrix, aspect="auto", cmap="RdYlGn", vmin=3.0, vmax=7.0)
    
    # Add text annotations
    for i in range(len(strategies)):
        for j in range(len(scenarios)):
            if not np.isnan(matrix[i, j]):
                text_color = "white" if matrix[i, j] < 4.5 or matrix[i, j] > 5.5 else "black"
                ax.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", color=text_color, fontsize=8)
    
    ax.set_xticks(range(len(scenarios)))
    ax.set_xticklabels(scenarios, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(strategies)))
    ax.set_yticklabels([STRATEGY_NAMES.get(s, s) for s in strategies], fontsize=9)
    ax.set_title("Mean Team 0 Tricks by Strategy × Scenario", fontsize=10)
    
    cbar = plt.colorbar(im, ax=ax, orientation="vertical", pad=0.02)
    cbar.set_label("Avg Tricks", fontsize=8)


def plot_summary_table(ax, all_data: Dict, baseline: str):
    """Summary statistics table."""
    ax.axis("off")
    
    strategies = sorted(all_data.keys())
    table_data = []
    table_data.append(["Strategy", "Mean Tricks", "StdDev", "Win Rate (%)", "Δ vs Baseline"])
    
    baseline_mean_tricks = np.mean([all_data[baseline][s]["avg_team0"] for s in all_data[baseline].keys()])
    
    for strategy in strategies:
        all_means = [all_data[strategy][s]["avg_team0"] for s in all_data[strategy].keys()]
        mean_tricks = np.mean(all_means)
        std_tricks = np.std(all_means)
        
        all_wins = []
        all_hands = []
        for scenario_data in all_data[strategy].values():
            wins = sum(
                count for tricks, count in scenario_data["distribution_team0"].items()
                if int(tricks) >= 6
            )
            all_wins.append(wins)
            all_hands.append(scenario_data["hands"])
        
        win_rate = sum(all_wins) / sum(all_hands) * 100
        delta = mean_tricks - baseline_mean_tricks
        
        row = [
            STRATEGY_NAMES.get(strategy, strategy),
            f"{mean_tricks:.3f}",
            f"{std_tricks:.3f}",
            f"{win_rate:.1f}%",
            f"{delta:+.3f}" if strategy != baseline else "—"
        ]
        table_data.append(row)
    
    table = ax.table(
        cellText=table_data,
        cellLoc="center",
        loc="center",
        colWidths=[0.25, 0.15, 0.15, 0.15, 0.15],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    
    # Style header row
    for j in range(len(table_data[0])):
        cell = table[(0, j)]
        cell.set_facecolor("#34495e")
        cell.set_text_props(weight="bold", color="white")
    
    # Highlight baseline row
    baseline_idx = strategies.index(baseline) + 1
    for j in range(len(table_data[0])):
        cell = table[(baseline_idx, j)]
        cell.set_facecolor("#f39c12")
        cell.set_text_props(weight="bold")
    
    ax.set_title("Strategy Performance Summary", fontsize=11, fontweight="bold", pad=10)


def main():
    args = parse_args()
    
    # Load meta.json
    meta_path = os.path.join(args.run_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
        print(f"📊 Loaded run: {meta['run_id']}")
        print(f"   Strategies: {', '.join(meta['strategies'])}")
        print(f"   Scenarios: {len(meta['scenarios'])}")
        print(f"   Hands per scenario: {meta['n_per']:,}")
    
    # Load all strategy data
    print("\n📂 Loading strategy results...")
    all_data = load_all_strategy_data(args.run_dir)
    print(f"   Found {len(all_data)} strategies:")
    for strategy in sorted(all_data.keys()):
        print(f"     - {strategy} ({len(all_data[strategy])} scenarios)")
    
    # Generate comparison report
    print("\n🎨 Generating comparison report...")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dashboard_dir = os.path.join(args.run_dir, "dashboard", f"comparison_{timestamp}")
    os.makedirs(dashboard_dir, exist_ok=True)
    
    output_path = os.path.join(dashboard_dir, "strategy_comparison.png")
    plot_strategy_comparison(all_data, args.baseline, output_path)
    
    # Also generate individual strategy dashboards
    print("\n🎯 Next steps:")
    print(f"   # View comparison report:")
    print(f"   open {output_path}")
    print()
    print(f"   # Generate individual strategy dashboards:")
    for strategy in sorted(all_data.keys()):
        print(f"   PYTHONPATH=src python experiments/generate_dashboard.py --run-dir {args.run_dir} --strategy {strategy} --seed {args.seed}")
    print()


if __name__ == "__main__":
    main()

