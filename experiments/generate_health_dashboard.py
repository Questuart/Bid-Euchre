#!/usr/bin/env python3
"""
Health Dashboard Generator for Bid Euchre Simulations.

Generates data quality and sanity check visualizations:
1. Trick count distribution PMF
2. Hand score by trick count violin plot
3. Suit symmetry analysis
4. Trick count distribution by contract type

This dashboard validates that simulation mechanics are working correctly
and provides early warning of data quality issues.

Usage:
    PYTHONPATH=src python experiments/generate_health_dashboard.py \\
        --run-dir data/runs/<run_id>
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
from scipy import stats as scipy_stats

# Import reporting framework
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from bid_euchre.reporting import (
    CONTRACT_LABELS, CONTRACT_COLORS, OUTCOME_COLORS,
    apply_report_style, get_report_paths,
    ensure_dir, copy_to_latest, write_latest_pointer,
)

# Apply report styling
apply_report_style()


# ============================================================================
# Data Loading
# ============================================================================

def load_results(run_dir: str) -> List[Dict]:
    """Load all result JSON files from a run directory."""
    paths = get_report_paths(run_dir)
    results_dir = paths.results_dir
    
    results = []
    
    # Handle both flat structure and nested structure
    for root, dirs, files in os.walk(results_dir):
        for fname in files:
            if fname.endswith('.json'):
                fpath = os.path.join(root, fname)
                with open(fpath) as f:
                    data = json.load(f)
                    
                    # Extract scenario information from data
                    contract_type = data.get("contract_type")
                    trump_suit = data.get("trump_suit")
                    
                    # Create label
                    if trump_suit:
                        label = f"suit_{trump_suit}"
                    else:
                        label = contract_type
                    
                    data["_label"] = label
                    results.append(data)
    
    return results


def load_hand_records(run_dir: str) -> List[Dict]:
    """Load hand-level records from JSONL logs."""
    paths = get_report_paths(run_dir)
    logs_dir = paths.logs_dir
    
    if not os.path.exists(logs_dir):
        return []
    
    hand_records = []
    for jsonl_file in glob(os.path.join(logs_dir, "*.jsonl")):
        with open(jsonl_file) as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    hand_records.append(record)
    
    return hand_records


# ============================================================================
# Data Processing Helpers
# ============================================================================

def get_distribution(result: Dict) -> Dict[int, int]:
    """Extract trick distribution, handling both team0 and team1 keys."""
    dist_t0 = result.get("distribution_team0", {})
    dist_t1 = result.get("distribution_team1", {})
    
    # Convert string keys to ints and merge
    merged = {}
    for d in [dist_t0, dist_t1]:
        for k, v in d.items():
            tricks = int(k)
            merged[tricks] = merged.get(tricks, 0) + v
    
    return merged


def merge_distributions(results: List[Dict]) -> Dict[int, int]:
    """Merge trick count distributions across all results."""
    merged = {}
    for result in results:
        dist = get_distribution(result)
        for tricks, count in dist.items():
            merged[tricks] = merged.get(tricks, 0) + count
    return merged


def get_score_buckets(result: Dict) -> Dict[int, Dict]:
    """Extract score buckets, handling string keys."""
    buckets = result.get("score_buckets", {})
    return {int(k): v for k, v in buckets.items()}


def merge_score_buckets(results: List[Dict]) -> Dict[int, Dict]:
    """Merge score buckets across all scenarios."""
    merged = defaultdict(lambda: {"count": 0, "total_tricks": 0.0})
    
    for result in results:
        buckets = get_score_buckets(result)
        for score, stats in buckets.items():
            merged[score]["count"] += stats.get("count", 0)
            merged[score]["total_tricks"] += stats.get("total_tricks", 0.0)
    
    for score, stats in merged.items():
        if stats["count"] > 0:
            stats["avg_tricks"] = stats["total_tricks"] / stats["count"]
        else:
            stats["avg_tricks"] = 0.0
    
    return dict(merged)


# ============================================================================
# Plotting Functions
# ============================================================================

def plot_trick_distribution(ax, results: List[Dict]):
    """Panel 1: Trick Count Distribution as PMF with mean line."""
    merged_dist = merge_distributions(results)
    
    total = sum(merged_dist.values())
    if total == 0:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Trick Count Distribution")
        return
    
    tricks = list(range(11))
    probs = [merged_dist.get(t, 0) / total for t in tricks]
    
    # Compute stats
    samples = []
    for t, count in merged_dist.items():
        samples.extend([t] * count)
    mean_tricks = np.mean(samples)
    std_tricks = np.std(samples, ddof=1)
    
    # Color by outcome
    colors = ["#e74c3c" if t < 5 else "#2ecc71" if t > 5 else "#f39c12" for t in tricks]
    bars = ax.bar(tricks, probs, color=colors, alpha=0.8, edgecolor="white", width=0.8)
    
    # Probability labels
    for i, (t, p) in enumerate(zip(tricks, probs)):
        if p > 0.02:
            ax.text(t, p + 0.008, f"{p:.0%}", ha="center", fontsize=7)
    
    # Mean line with label
    ax.axvline(mean_tricks, color="#2c3e50", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.text(mean_tricks + 0.15, max(probs) * 0.85, f"μ={mean_tricks:.2f}", 
            fontsize=9, color="#2c3e50", fontweight="bold", rotation=90, va="center")
    
    ax.set_xlabel("Team Tricks")
    ax.set_ylabel("Probability")
    ax.set_title("Trick Count Distribution (PMF)")
    ax.set_xticks(tricks)
    ax.set_ylim(0, max(probs) * 1.2)
    
    # Stats annotation
    ax.text(0.98, 0.95, f"σ={std_tricks:.2f}\nn={total:,}", 
            transform=ax.transAxes, fontsize=8, ha="right", va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))


def plot_tricks_vs_score_violin(ax, results: List[Dict], hand_records: Optional[List[Dict]] = None):
    """
    Panel 2: Violin plot of hand scores by trick count.
    
    Uses exact per-hand scores from JSONL logs when available.
    Falls back to approximation from score buckets if not.
    """
    if hand_records and plot_tricks_vs_score_violin_from_logs(ax, hand_records):
        return
    
    # Fallback: approximate from score buckets
    merged_buckets = merge_score_buckets(results)
    
    all_data = {i: [] for i in range(11)}
    for score, stats in merged_buckets.items():
        avg_t = stats.get("avg_tricks", 5)
        count = stats.get("count", 0)
        
        base_trick = int(round(avg_t))
        base_trick = max(0, min(10, base_trick))
        
        samples_to_add = min(count, 40)
        all_data[base_trick].extend([score] * samples_to_add)
        
        if base_trick > 0 and count > 10:
            all_data[base_trick - 1].extend([score] * min(count // 5, 8))
        if base_trick < 10 and count > 10:
            all_data[base_trick + 1].extend([score] * min(count // 5, 8))
    
    positions = []
    data_for_violin = []
    counts = []
    omitted_bins = []
    for t in range(11):
        n = len(all_data[t])
        if n >= 10:
            positions.append(t)
            data_for_violin.append(all_data[t])
            counts.append(n)
        else:
            omitted_bins.append(t)
    
    if data_for_violin:
        parts = ax.violinplot(data_for_violin, positions=positions,
                              showmeans=True, showmedians=False, widths=0.85)
        for pc in parts['bodies']:
            pc.set_facecolor('#3498db')
            pc.set_alpha(0.6)
            pc.set_edgecolor('#2c3e50')
        parts['cmeans'].set_color('#e74c3c')
        parts['cmeans'].set_linewidth(2)
        
        for pos, n in zip(positions, counts):
            ax.text(pos, 160, f"n={n}", ha="center", fontsize=6, color="gray")
    
    ax.set_xlabel("Team Tricks")
    ax.set_ylabel("Hand Score")
    ax.set_title("Hand Score by Trick Count")
    ax.set_xticks(range(11))
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(150, 900)
    ax.axvline(5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)
    
    if omitted_bins:
        omit_str = ",".join(str(b) for b in omitted_bins)
        ax.text(0.02, 0.02, f"(bins {omit_str}: n<10)",
                transform=ax.transAxes, fontsize=6, color="gray", va="bottom")


def plot_tricks_vs_score_violin_from_logs(ax, hand_records: List[Dict]) -> bool:
    """Exact violin plot from JSONL hand records."""
    if not hand_records:
        return False
    
    # Build score distributions keyed by team tricks
    by_tricks: Dict[int, List[int]] = {i: [] for i in range(11)}
    for rec in hand_records:
        scores = rec.get("scores")
        feats = rec.get("features") or []
        if not scores or len(scores) != 4:
            continue
        t0 = int(rec.get("t0", 0))
        t1 = int(rec.get("t1", 0))
        for p_idx, s in enumerate(scores):
            team_tricks = t0 if p_idx in (0, 2) else t1
            by_tricks[team_tricks].append(int(s))
    
    positions = []
    data_for_violin = []
    counts = []
    omitted_bins = []
    for t in range(11):
        n = len(by_tricks[t])
        if n >= 10:
            positions.append(t)
            data_for_violin.append(by_tricks[t])
            counts.append(n)
        else:
            omitted_bins.append(t)
    
    if not data_for_violin:
        return False
    
    parts = ax.violinplot(data_for_violin, positions=positions,
                          showmeans=True, showmedians=False, widths=0.85)
    for pc in parts['bodies']:
        pc.set_facecolor('#3498db')
        pc.set_alpha(0.6)
        pc.set_edgecolor('#2c3e50')
    parts['cmeans'].set_color('#e74c3c')
    parts['cmeans'].set_linewidth(2)
    
    for pos, n in zip(positions, counts):
        ax.text(pos, 160, f"n={n}", ha="center", fontsize=6, color="gray")
    
    ax.set_xlabel("Team Tricks")
    ax.set_ylabel("Hand Score")
    ax.set_title("Hand Score by Trick Count")
    ax.set_xticks(range(11))
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(150, 900)
    ax.axvline(5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)
    
    if omitted_bins:
        omit_str = ",".join(str(b) for b in omitted_bins)
        ax.text(0.02, 0.02, f"(bins {omit_str}: n<10)",
                transform=ax.transAxes, fontsize=6, color="gray", va="bottom")
    
    return True


def plot_suit_symmetry(ax, results: List[Dict]):
    """Panel 3: Suit Symmetry with statistical test."""
    suit_results = [r for r in results if r.get("contract_type") == "suit"]
    
    if len(suit_results) < 2:
        ax.text(0.5, 0.5, "Need ≥2 suit contracts", ha="center", va="center", 
               transform=ax.transAxes)
        ax.set_title("Suit Symmetry")
        return
    
    labels = []
    means = []
    cis = []
    all_samples_list = []
    
    for result in suit_results:
        label = result["_label"].replace("suit_", "")
        dist = get_distribution(result)
        
        samples = []
        for tricks, count in dist.items():
            samples.extend([tricks] * count)
        
        if samples:
            n = len(samples)
            mean = np.mean(samples)
            se = np.std(samples, ddof=1) / np.sqrt(n) if n > 1 else 0
            ci_95 = 1.96 * se
            
            labels.append(label)
            means.append(mean)
            cis.append(ci_95)
            all_samples_list.append(samples)
    
    x = np.arange(len(labels))
    colors = [CONTRACT_COLORS.get(f"suit_{l}", "#3498db") for l in labels]
    
    bars = ax.bar(x, means, yerr=cis, color=colors, alpha=0.8, capsize=4, edgecolor="white")
    ax.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.7)
    
    # Add means above bars
    for i, (bar, mean) in enumerate(zip(bars, means)):
        ax.text(bar.get_x() + bar.get_width()/2, mean + cis[i] + 0.02, 
                f"{mean:.2f}", ha="center", va="bottom", fontsize=8, fontweight="bold")
    
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10, fontweight="bold")
    ax.set_ylabel("Mean Tricks ± 95% CI")
    ax.set_ylim(4.5, 5.5)
    
    # Kruskal-Wallis test
    if len(all_samples_list) >= 2:
        try:
            stat, p_value = scipy_stats.kruskal(*all_samples_list)
            test_result = f"K-W p={p_value:.3f}"
        except Exception:
            test_result = "K-W: N/A"
    else:
        test_result = ""
    
    ax.set_title(f"Suit Symmetry ({test_result})", fontsize=10)
    
    # Effect size annotation
    if means:
        delta = max(means) - min(means)
        pooled_std = np.std(np.concatenate(all_samples_list)) if all_samples_list else 1
        cohens_d = delta / pooled_std if pooled_std > 0 else 0
        
        ax.text(0.02, 0.98, f"Δmax={delta:.3f}\nd={cohens_d:.2f}", 
               transform=ax.transAxes, fontsize=8, va="top", fontfamily="monospace",
               bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))


def plot_tricks_by_contract_type(ax, results: List[Dict]):
    """Panel 4: Violin plot of trick distribution by contract type."""
    # Group results by contract type
    by_contract = defaultdict(list)
    for result in results:
        contract_type = result.get("contract_type")
        label = CONTRACT_LABELS.get(contract_type, contract_type)
        
        dist = get_distribution(result)
        samples = []
        for tricks, count in dist.items():
            samples.extend([tricks] * count)
        
        if samples:
            by_contract[label].extend(samples)
    
    if not by_contract:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Tricks by Contract Type")
        return
    
    # Sort by contract type order
    contract_order = ["High", "Low", "Suit"]
    sorted_contracts = [c for c in contract_order if c in by_contract and len(by_contract[c]) > 0]
    
    if not sorted_contracts:
        ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Tricks by Contract Type")
        return
    
    positions = list(range(len(sorted_contracts)))
    data_for_violin = [by_contract[c] for c in sorted_contracts]
    
    # Create violin plots
    parts = ax.violinplot(data_for_violin, positions=positions,
                          showmeans=True, showmedians=True, widths=0.7)
    
    # Color by contract type
    colors_map = {"High": "#e74c3c", "Low": "#3498db", "Suit": "#2ecc71"}
    for i, (pc, contract) in enumerate(zip(parts['bodies'], sorted_contracts)):
        color = colors_map.get(contract, "#95a5a6")
        pc.set_facecolor(color)
        pc.set_alpha(0.6)
        pc.set_edgecolor('#2c3e50')
    
    parts['cmeans'].set_color('#e74c3c')
    parts['cmeans'].set_linewidth(2)
    parts['cmedians'].set_color('#2c3e50')
    parts['cmedians'].set_linewidth=1.5
    
    # Add sample counts and means
    for pos, (contract, data) in enumerate(zip(sorted_contracts, data_for_violin)):
        n = len(data)
        mean = np.mean(data)
        ax.text(pos, 10.3, f"n={n:,}", ha="center", fontsize=7, color="gray")
        ax.text(pos, -0.5, f"μ={mean:.2f}", ha="center", fontsize=7, 
                fontweight="bold", color="black")
    
    ax.set_xticks(positions)
    ax.set_xticklabels(sorted_contracts, fontsize=10, fontweight="bold")
    ax.set_ylabel("Tricks Won")
    ax.set_title("Trick Distribution by Contract Type")
    ax.set_ylim(-0.8, 10.8)
    ax.axhline(5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)
    
    # Statistical test across contract types
    if len(data_for_violin) >= 2:
        try:
            stat, p_value = scipy_stats.kruskal(*data_for_violin)
            ax.text(0.98, 0.98, f"K-W: p={p_value:.3f}", 
                   transform=ax.transAxes, fontsize=7, ha="right", va="top",
                   bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        except Exception:
            pass


# ============================================================================
# Main Report Generation
# ============================================================================

def generate_health_dashboard(run_dir: str, output_dir: Optional[str] = None) -> str:
    """
    Generate health dashboard report.
    
    Writes to standardized archive + latest pattern:
        <run_dir>/reports/health/
        ├── health_dashboard.png (latest)
        ├── summary.md (latest)
        ├── plots/ (individual plots)
        └── _history/<timestamp>/ (archived version)
    
    Args:
        run_dir: Base run directory
        output_dir: Optional override for output location
    
    Returns:
        Path to latest health_dashboard.png
    """
    print("=" * 70)
    print("🏥 Generating Health Dashboard")
    print("=" * 70)
    
    # Load data
    print("📂 Loading results...")
    results = load_results(run_dir)
    print(f"   Loaded {len(results)} result files")
    
    print("📂 Loading hand records...")
    hand_records = load_hand_records(run_dir)
    print(f"   Loaded {len(hand_records)} hand records")
    
    # Determine output paths
    paths = get_report_paths(run_dir)
    
    if output_dir:
        # Legacy mode: use provided output_dir
        archive_dir = output_dir
        latest_dir = output_dir
    else:
        # New standardized paths
        archive_dir = paths.health_archive
        latest_dir = paths.health_root
    
    ensure_dir(archive_dir)
    ensure_dir(latest_dir)
    
    # Create 2x2 figure
    fig = plt.figure(figsize=(14, 10))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3,
                          left=0.08, right=0.95, top=0.93, bottom=0.07)
    
    # Plot all panels
    print("📊 Generating plots...")
    
    ax1 = fig.add_subplot(gs[0, 0])
    plot_trick_distribution(ax1, results)
    print("   ✅ Trick distribution")
    
    ax2 = fig.add_subplot(gs[0, 1])
    plot_tricks_vs_score_violin(ax2, results, hand_records)
    print("   ✅ Score by tricks violin")
    
    ax3 = fig.add_subplot(gs[1, 0])
    plot_suit_symmetry(ax3, results)
    print("   ✅ Suit symmetry")
    
    ax4 = fig.add_subplot(gs[1, 1])
    plot_tricks_by_contract_type(ax4, results)
    print("   ✅ Tricks by contract type")
    
    # Add overall title
    meta_path = os.path.join(run_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        run_id = meta.get("run_id", "Unknown")
    else:
        run_id = os.path.basename(run_dir)
    
    fig.suptitle(f"Health Dashboard: {run_id}", 
                fontsize=14, fontweight="bold", y=0.98)
    
    # Save to archive
    archive_png = os.path.join(archive_dir, "health_dashboard.png")
    fig.savefig(archive_png, dpi=150, bbox_inches="tight")
    print(f"   💾 Saved to archive: {archive_png}")
    
    # Copy to latest
    latest_png = os.path.join(latest_dir, "health_dashboard.png")
    copy_to_latest(archive_png, latest_png)
    print(f"   💾 Saved to latest: {latest_png}")
    
    plt.close(fig)
    
    # Generate summary markdown
    generate_summary_md(run_dir, results, latest_dir, archive_dir, paths.timestamp)
    
    # Write latest pointer
    if not output_dir:
        relative_archive = os.path.relpath(archive_dir, latest_dir)
        write_latest_pointer(latest_dir, relative_archive)
    
    print("=" * 70)
    print("✅ Health dashboard generated successfully!")
    print(f"📁 Latest: {latest_png}")
    print("=" * 70)
    
    return latest_png


def generate_summary_md(run_dir: str, results: List[Dict], 
                       latest_dir: str, archive_dir: str, timestamp: str):
    """Generate summary markdown for health dashboard."""
    lines = []
    lines.append("# Health Dashboard Summary\n\n")
    
    # Load metadata
    meta_path = os.path.join(run_dir, "meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        
        lines.append("## Run Information\n\n")
        lines.append(f"- **Run ID**: {meta.get('run_id', 'Unknown')}\n")
        lines.append(f"- **Experiment**: {meta.get('experiment_name', 'Unknown')}\n")
        lines.append(f"- **Total Hands**: {meta.get('total_hands', 0):,}\n")
        lines.append(f"- **Scenarios**: {len(meta.get('scenarios', []))}\n\n")
    
    # Compute overall statistics
    merged_dist = merge_distributions(results)
    total_hands = sum(merged_dist.values())
    
    if total_hands > 0:
        samples = []
        for tricks, count in merged_dist.items():
            samples.extend([tricks] * count)
        
        mean_tricks = np.mean(samples)
        std_tricks = np.std(samples, ddof=1)
        median_tricks = np.median(samples)
        
        lines.append("## Overall Statistics\n\n")
        lines.append(f"- **Total Observations**: {total_hands:,}\n")
        lines.append(f"- **Mean Tricks**: {mean_tricks:.3f}\n")
        lines.append(f"- **Std Dev**: {std_tricks:.3f}\n")
        lines.append(f"- **Median**: {median_tricks:.1f}\n\n")
    
    # Suit symmetry check
    suit_results = [r for r in results if r.get("contract_type") == "suit"]
    if len(suit_results) >= 2:
        lines.append("## Suit Symmetry Test\n\n")
        
        all_samples_list = []
        suit_means = []
        for result in suit_results:
            dist = get_distribution(result)
            samples = []
            for tricks, count in dist.items():
                samples.extend([tricks] * count)
            if samples:
                all_samples_list.append(samples)
                suit_means.append(np.mean(samples))
        
        if len(all_samples_list) >= 2:
            try:
                stat, p_value = scipy_stats.kruskal(*all_samples_list)
                lines.append(f"- **Kruskal-Wallis Test**: H={stat:.3f}, p={p_value:.4f}\n")
                lines.append(f"- **Interpretation**: {'✅ PASS' if p_value > 0.05 else '⚠️ FAIL'} (suits are {'balanced' if p_value > 0.05 else 'imbalanced'})\n")
                lines.append(f"- **Max Difference**: {max(suit_means) - min(suit_means):.3f} tricks\n\n")
            except Exception as e:
                lines.append(f"- **Test**: Failed ({e})\n\n")
    
    # Contract type comparison
    lines.append("## Contract Type Comparison\n\n")
    by_contract = defaultdict(list)
    for result in results:
        contract_type = result.get("contract_type")
        dist = get_distribution(result)
        samples = []
        for tricks, count in dist.items():
            samples.extend([tricks] * count)
        if samples:
            by_contract[contract_type].extend(samples)
    
    lines.append("| Contract Type | Mean | Std Dev | N |\n")
    lines.append("|---------------|------|---------|---|\n")
    for contract in ["high", "low", "suit"]:
        if contract in by_contract:
            data = by_contract[contract]
            mean = np.mean(data)
            std = np.std(data, ddof=1)
            n = len(data)
            label = CONTRACT_LABELS.get(contract, contract)
            lines.append(f"| {label} | {mean:.3f} | {std:.3f} | {n:,} |\n")
    lines.append("\n")
    
    # Data quality checks
    lines.append("## Data Quality Checks\n\n")
    lines.append("- ✅ Trick distribution loaded successfully\n")
    lines.append(f"- {'✅' if total_hands > 1000 else '⚠️'} Sample size: {total_hands:,} hands\n")
    lines.append(f"- {'✅' if len(suit_results) >= 4 else '⚠️'} Suit coverage: {len(suit_results)} suits\n")
    lines.append(f"- {'✅' if 4.8 < mean_tricks < 5.2 else '⚠️'} Mean tricks near 5.0: {mean_tricks:.3f}\n")
    lines.append("\n")
    
    lines.append(f"## Report Details\n\n")
    lines.append(f"- **Generated**: {timestamp}\n")
    lines.append(f"- **Archive**: `{os.path.relpath(archive_dir, run_dir)}`\n")
    
    summary_path = os.path.join(latest_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.writelines(lines)
    
    print(f"   📝 Summary saved: {summary_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate health dashboard")
    parser.add_argument("--run-dir", type=str, required=True, help="Path to run directory")
    parser.add_argument("--output-dir", type=str, help="Override output directory")
    return parser.parse_args()


def main():
    args = parse_args()
    generate_health_dashboard(args.run_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
