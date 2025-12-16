#!/usr/bin/env python3
"""
Unified Dashboard Report Generator for Bid Euchre Simulations (v4.1).

Generates a streamlined 3x3 multi-panel figure with:
- Baseline Analysis (tricks, features, score calibration)
- Strategy Metrics (win rates, correlations, heatmaps)

Changes from v4:
- Score→Tricks: 2 grouped plots (NT vs Suits) instead of 6 tiny facets
- Trick PMF: Label on mean line
- Violin: Annotation for omitted bins
- Suit Symmetry: Raw means above bars
- Heatmap: n per cell
- Feature panels: Increased min n threshold

Usage:
    PYTHONPATH=src python experiments/generate_dashboard.py
    PYTHONPATH=src python experiments/generate_dashboard.py --seed 42
"""

import os
import sys
import json
import argparse
import subprocess
from glob import glob
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy import stats as scipy_stats

# ============================================================================
# Configuration
# ============================================================================

# Standardized contract labels
CONTRACT_LABELS = {
    "high": "NT-High",
    "low": "NT-Low",
    "suit_C": "Trump-C",
    "suit_D": "Trump-D",
    "suit_H": "Trump-H",
    "suit_S": "Trump-S",
}

# Color palette for contract types (consistent across all panels)
CONTRACT_COLORS = {
    "high": "#2ecc71",      # green
    "low": "#e74c3c",       # red
    "suit_C": "#3498db",    # blue (clubs)
    "suit_D": "#e67e22",    # orange (diamonds)
    "suit_H": "#9b59b6",    # purple (hearts)
    "suit_S": "#34495e",    # dark gray (spades)
}

# Line styles for overlaid plots
CONTRACT_LINESTYLES = {
    "high": "-",
    "low": "--",
    "suit_C": "-",
    "suit_D": "--",
    "suit_H": "-.",
    "suit_S": ":",
}

FEATURE_COLORS = {
    "bowers": "#e74c3c",
    "trump_count": "#3498db",
    "offsuit_aces": "#2ecc71",
    "high_offsuit": "#9b59b6",
    "rank_sum": "#f39c12",
}

# Expected value ranges for each feature
FEATURE_RANGES = {
    "bowers": (0, 4),
    "trump_count": (0, 10),
    "offsuit_aces": (0, 6),
    "high_offsuit": (0, 8),
}

# Minimum sample size for plotting (increased for v4.1)
MIN_SAMPLES_FOR_PLOT = 200
MIN_SAMPLES_FOR_PLOT_LOW = 50  # Lower threshold for heatmap cells

# Consistent y-axis limits for "avg tricks" plots
TRICKS_YLIM = (4.0, 6.0)
TRICKS_YLIM_EXTENDED = (3.0, 8.0)  # For individual plots with full range

# Figure styling
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7,
    "figure.titlesize": 12,
})


# ============================================================================
# Data Loading
# ============================================================================

def load_json_results(data_dir: str = "data/raw") -> List[Dict]:
    """Load all JSON result files from the data directory."""
    pattern = os.path.join(data_dir, "*.json")
    paths = sorted(glob(pattern))
    
    if not paths:
        raise FileNotFoundError(f"No JSON files found in {data_dir}")
    
    results = []
    for path in paths:
        with open(path) as f:
            data = json.load(f)
        data["_path"] = path
        data["_label"] = scenario_label(data)
        data["_display_label"] = CONTRACT_LABELS.get(data["_label"], data["_label"])
        results.append(data)
    
    print(f"Loaded {len(results)} scenario files from {data_dir}")
    return results


def load_json_results_from_run_dir(run_dir: str, strategy: str) -> List[Dict]:
    """Load scenario JSONs from a standardized run directory."""
    data_dir = os.path.join(run_dir, "results", strategy)
    return load_json_results(data_dir=data_dir)


def load_jsonl_logs(log_dir: str, run_id: Optional[str] = None) -> List[Dict]:
    """Load JSONL log records for detailed analysis."""
    if run_id:
        pattern = os.path.join(log_dir, f"{run_id}.jsonl")
    else:
        pattern = os.path.join(log_dir, "*.jsonl")
    
    paths = glob(pattern)
    if not paths:
        return []
    
    records = []
    for path in paths:
        with open(path) as f:
            for line in f:
                record = json.loads(line)
                if record.get("event") == "hand_end":
                    records.append(record)
    
    print(f"Loaded {len(records)} hand records from JSONL logs")
    return records


def load_jsonl_logs_from_run_dir(run_dir: str, strategy: str) -> List[Dict]:
    """Load hand_end records for a strategy from a standardized run directory."""
    logs_dir = os.path.join(run_dir, "logs")
    # Prefer exact strategy log if present, else fall back to any jsonl in logs/
    exact = os.path.join(logs_dir, f"{strategy}.jsonl")
    if os.path.exists(exact):
        return load_jsonl_logs(log_dir=logs_dir, run_id=strategy)
    # Runner uses <run_id>_<strategy>.jsonl naming
    pattern = os.path.join(logs_dir, f"*_{strategy}.jsonl")
    matches = glob(pattern)
    if matches:
        # Use the newest match
        matches.sort(key=os.path.getmtime, reverse=True)
        # Extract filename stem without extension
        stem = os.path.splitext(os.path.basename(matches[0]))[0]
        return load_jsonl_logs(log_dir=logs_dir, run_id=stem)
    return load_jsonl_logs(log_dir=logs_dir, run_id=None)


def scenario_label(result: Dict) -> str:
    """Generate a label for a scenario."""
    contract_type = result.get("contract_type", "unknown")
    trump_suit = result.get("trump_suit")
    
    if contract_type == "suit" and trump_suit:
        return f"suit_{trump_suit}"
    return contract_type


def get_git_commit_hash() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ============================================================================
# Data Processing Helpers
# ============================================================================

def get_distribution(result: Dict) -> Dict[int, int]:
    """Extract trick distribution, handling string keys from JSON."""
    dist = result.get("distribution_team0", {})
    return {int(k): int(v) for k, v in dist.items()}


def merge_distributions(results: List[Dict]) -> Dict[int, int]:
    """Merge trick distributions across all scenarios."""
    merged = defaultdict(int)
    for result in results:
        dist = get_distribution(result)
        for k, v in dist.items():
            merged[k] += v
    return dict(merged)


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


def get_feature_buckets(result: Dict) -> Dict[str, Dict[int, Dict]]:
    """Extract feature buckets."""
    buckets = result.get("feature_buckets", {})
    return {
        fname: {int(k): v for k, v in by_val.items()}
        for fname, by_val in buckets.items()
    }


def merge_feature_buckets(results: List[Dict]) -> Dict[str, Dict[int, Dict]]:
    """Merge feature buckets across all scenarios."""
    merged = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total_tricks": 0.0}))
    
    for result in results:
        buckets = get_feature_buckets(result)
        for fname, by_val in buckets.items():
            for val, stats in by_val.items():
                merged[fname][val]["count"] += stats.get("count", 0)
                merged[fname][val]["total_tricks"] += stats.get("total_tricks", 0.0)
    
    out = {}
    for fname, by_val in merged.items():
        out[fname] = {}
        for val, stats in by_val.items():
            if stats["count"] > 0:
                stats["avg_tricks"] = stats["total_tricks"] / stats["count"]
            else:
                stats["avg_tricks"] = 0.0
            out[fname][val] = dict(stats)
    
    return out


def compute_win_rates(results: List[Dict]) -> Dict[str, Tuple[float, int]]:
    """Compute win rate (≥6 tricks) for each contract type."""
    win_rates = {}
    
    for result in results:
        label = result["_label"]
        dist = get_distribution(result)
        total = sum(dist.values())
        wins = sum(count for tricks, count in dist.items() if tricks >= 6)
        
        if total > 0:
            win_rates[label] = (wins / total * 100, total)
        else:
            win_rates[label] = (0.0, 0)
    
    return win_rates


def compute_joint_trump_bowers_from_logs(
    hand_records: List[Dict],
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute true joint heatmap stats from JSONL logs:
      (bowers, trump_count) -> mean team tricks, and counts per cell.

    Returns:
        mean_tricks: shape (max_bowers+1, max_trump+1) with NaN for empty cells
        counts:      shape (max_bowers+1, max_trump+1)
    """
    # Determine bounds from observed data (double-deck can exceed 2 bowers)
    max_bowers = 0
    max_trump = 0
    for rec in hand_records:
        feats = rec.get("features") or []
        for p_idx, f in enumerate(feats):
            if not isinstance(f, dict):
                continue
            b = int(f.get("bowers", 0))
            tc = int(f.get("trump_count", 0))
            max_bowers = max(max_bowers, b)
            max_trump = max(max_trump, tc)

    max_bowers = max(max_bowers, 2)
    max_trump = max(max_trump, 10)

    sums = np.zeros((max_bowers + 1, max_trump + 1), dtype=float)
    counts = np.zeros((max_bowers + 1, max_trump + 1), dtype=int)

    for rec in hand_records:
        feats = rec.get("features") or []
        t0 = int(rec.get("t0", 0))
        t1 = int(rec.get("t1", 0))
        for p_idx, f in enumerate(feats):
            if not isinstance(f, dict):
                continue
            team_tricks = t0 if p_idx in (0, 2) else t1
            b = int(f.get("bowers", 0))
            tc = int(f.get("trump_count", 0))
            if 0 <= b <= max_bowers and 0 <= tc <= max_trump:
                sums[b, tc] += team_tricks
                counts[b, tc] += 1

    mean = np.full_like(sums, np.nan, dtype=float)
    nonzero = counts > 0
    mean[nonzero] = sums[nonzero] / counts[nonzero]
    return mean, counts


def compute_feature_correlations_from_logs(hand_records: List[Dict]) -> Dict[str, Tuple[float, int]]:
    """
    Compute Pearson correlation between each feature and team tricks using raw hand data.
    """
    if not hand_records:
        return {}
    
    feature_data = defaultdict(lambda: {"feature_vals": [], "trick_vals": []})
    
    for record in hand_records:
        features_list = record.get("features", [])
        t0 = record.get("t0", 5)
        t1 = record.get("t1", 5)
        
        for player_idx, player_features in enumerate(features_list):
            team_tricks = t0 if player_idx in (0, 2) else t1
            
            for fname, fval in player_features.items():
                if fname in FEATURE_RANGES:
                    feature_data[fname]["feature_vals"].append(fval)
                    feature_data[fname]["trick_vals"].append(team_tricks)
    
    correlations = {}
    for fname, data in feature_data.items():
        fvals = np.array(data["feature_vals"])
        tvals = np.array(data["trick_vals"])
        n = len(fvals)
        
        if n >= 30:
            corr, _ = scipy_stats.pearsonr(fvals, tvals)
            correlations[fname] = (corr if not np.isnan(corr) else 0.0, n)
        else:
            correlations[fname] = (0.0, n)
    
    return correlations


def compute_feature_correlations_from_buckets(results: List[Dict]) -> Dict[str, Tuple[float, int]]:
    """Fallback: Compute correlation from aggregated buckets."""
    merged = merge_feature_buckets(results)
    correlations = {}
    
    for fname, by_val in merged.items():
        vals = []
        avgs = []
        weights = []
        
        for val, stats in sorted(by_val.items()):
            if stats["count"] >= MIN_SAMPLES_FOR_PLOT_LOW:
                vals.append(val)
                avgs.append(stats["avg_tricks"])
                weights.append(stats["count"])
        
        total_n = sum(stats["count"] for stats in by_val.values())
        
        if len(vals) >= 3:
            weights = np.array(weights)
            vals = np.array(vals)
            avgs = np.array(avgs)
            
            w_sum = weights.sum()
            mean_x = np.average(vals, weights=weights)
            mean_y = np.average(avgs, weights=weights)
            
            cov_xy = np.sum(weights * (vals - mean_x) * (avgs - mean_y)) / w_sum
            var_x = np.sum(weights * (vals - mean_x)**2) / w_sum
            var_y = np.sum(weights * (avgs - mean_y)**2) / w_sum
            
            if var_x > 0 and var_y > 0:
                corr = cov_xy / np.sqrt(var_x * var_y)
            else:
                corr = 0.0
            
            correlations[fname] = (np.clip(corr, -1, 1), total_n)
        else:
            correlations[fname] = (0.0, total_n)
    
    return correlations


# ============================================================================
# Plotting Functions
# ============================================================================

def plot_trick_distribution(ax, results: List[Dict]):
    """Panel 1: Trick Count Distribution as PMF with mean line label."""
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
            ax.text(t, p + 0.008, f"{p:.0%}", ha="center", fontsize=6)
    
    # Mean line with label directly on it
    ax.axvline(mean_tricks, color="#2c3e50", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.text(mean_tricks + 0.15, max(probs) * 0.85, f"μ={mean_tricks:.2f}", 
            fontsize=8, color="#2c3e50", fontweight="bold", rotation=90, va="center")
    
    ax.set_xlabel("Team 0 Tricks")
    ax.set_ylabel("Probability")
    ax.set_title("Trick Count Distribution (PMF)")
    ax.set_xticks(tricks)
    ax.set_ylim(0, max(probs) * 1.2)
    
    # Stats annotation (smaller, just σ and n)
    ax.text(0.98, 0.95, f"σ={std_tricks:.2f}\nn={total:,}", 
            transform=ax.transAxes, fontsize=7, ha="right", va="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))


def plot_tricks_vs_score_violin(ax, results: List[Dict], hand_records: Optional[List[Dict]] = None):
    """
    Panel 2: Violin plot of hand scores by trick count.

    Prefer exact per-hand scores from JSONL logs (schema v2 `scores`) when available.
    Falls back to an approximation from score buckets if scores are not present.
    """
    if hand_records and plot_tricks_vs_score_violin_from_logs(ax, hand_records):
        return

    # Fallback: approximate from score buckets (legacy behavior)
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
            ax.text(pos, 160, f"n={n}", ha="center", fontsize=5, color="gray")

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
    """Exact violin plot from JSONL hand records (requires `scores`)."""
    if not hand_records:
        return False
    # Build score distributions keyed by team tricks (0-10)
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
        ax.text(pos, 160, f"n={n}", ha="center", fontsize=5, color="gray")

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
        
        # Add n labels at bottom
        for pos, n in zip(positions, counts):
            ax.text(pos, 160, f"n={n}", ha="center", fontsize=5, color="gray")
    
    ax.set_xlabel("Team Tricks")
    ax.set_ylabel("Hand Score")
    ax.set_title("Hand Score by Trick Count")
    ax.set_xticks(range(11))
    ax.set_xlim(-0.5, 10.5)
    ax.set_ylim(150, 850)
    ax.axvline(5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)
    
    # Note about omitted bins
    if omitted_bins:
        omit_str = ",".join(str(b) for b in omitted_bins)
        ax.text(0.02, 0.02, f"(bins {omit_str}: n<10)", 
                transform=ax.transAxes, fontsize=6, color="gray", va="bottom")


def plot_feature_vs_tricks_faceted(fig, gs_slot, results: List[Dict]):
    """Panel 3: Feature Value → Avg Tricks (2×2 small multiples) with n>=200 threshold."""
    merged = merge_feature_buckets(results)
    
    features = ["bowers", "trump_count", "offsuit_aces", "high_offsuit"]
    
    gs_inner = gs_slot.subgridspec(2, 2, hspace=0.45, wspace=0.4)
    
    for idx, fname in enumerate(features):
        row, col = divmod(idx, 2)
        ax_sub = fig.add_subplot(gs_inner[row, col])
        
        if fname not in merged:
            ax_sub.text(0.5, 0.5, "No data", ha="center", va="center", 
                       transform=ax_sub.transAxes, fontsize=7)
            ax_sub.set_title(fname, fontsize=9, pad=2)
            continue
        
        by_val = merged[fname]
        min_v, max_v = FEATURE_RANGES.get(fname, (0, 10))
        
        # Collect all points, mark low-n ones
        vals_high_n = []
        avg_tricks_high_n = []
        cis_high_n = []
        
        vals_low_n = []
        avg_tricks_low_n = []
        
        for v in sorted(by_val.keys()):
            if min_v <= v <= max_v:
                stats = by_val[v]
                n = stats["count"]
                
                if n >= MIN_SAMPLES_FOR_PLOT:
                    vals_high_n.append(v)
                    avg_tricks_high_n.append(stats["avg_tricks"])
                    se = 1.7 / np.sqrt(n)
                    cis_high_n.append(1.96 * se)
                elif n >= MIN_SAMPLES_FOR_PLOT_LOW:
                    # Gray out low-n points
                    vals_low_n.append(v)
                    avg_tricks_low_n.append(stats["avg_tricks"])
        
        color = FEATURE_COLORS.get(fname, "#3498db")
        
        # Plot low-n points in gray
        if vals_low_n:
            ax_sub.scatter(vals_low_n, avg_tricks_low_n, color="lightgray", 
                          s=20, marker="o", zorder=1, alpha=0.6)
        
        # Plot high-n points with error bars
        if vals_high_n:
            ax_sub.errorbar(vals_high_n, avg_tricks_high_n, yerr=cis_high_n, 
                           fmt="o-", color=color, markersize=5, linewidth=1.5, 
                           capsize=3, capthick=1, zorder=2)
        
        ax_sub.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=0.8, alpha=0.5)
        
        ax_sub.set_title(fname, fontsize=9, pad=2)
        ax_sub.set_ylim(TRICKS_YLIM_EXTENDED)
        ax_sub.set_xlim(min_v - 0.3, max_v + 0.3)
        ax_sub.tick_params(labelsize=6)
        
        total_n = sum(stats["count"] for stats in by_val.values())
        ax_sub.text(0.95, 0.05, f"n={total_n:,}", transform=ax_sub.transAxes, 
                   fontsize=6, ha="right", color="gray")
        
        if not vals_high_n and not vals_low_n:
            ax_sub.text(0.5, 0.5, f"n<{MIN_SAMPLES_FOR_PLOT_LOW}\nper bin", 
                       ha="center", va="center", transform=ax_sub.transAxes, 
                       fontsize=7, color="gray")


def plot_score_tricks_grouped(fig, gs_slot, results: List[Dict]):
    """Panel 4: Score → Tricks as 2 grouped plots (NT vs Suits)."""
    gs_inner = gs_slot.subgridspec(1, 2, wspace=0.35)
    
    results_by_label = {r["_label"]: r for r in results}
    
    # Find global x-axis range
    all_scores = []
    for result in results:
        buckets = get_score_buckets(result)
        all_scores.extend(buckets.keys())
    
    if all_scores:
        x_min = min(all_scores) // 50 * 50
        x_max = (max(all_scores) // 50 + 1) * 50
    else:
        x_min, x_max = 100, 800
    
    # Helper to get binned data
    def get_binned_data(label):
        if label not in results_by_label:
            return [], []
        result = results_by_label[label]
        buckets = get_score_buckets(result)
        
        bin_size = 50
        binned = defaultdict(lambda: {"count": 0, "total_tricks": 0.0})
        for score, stats in buckets.items():
            bin_center = (score // bin_size) * bin_size + bin_size // 2
            n = stats["count"]
            avg = stats["avg_tricks"]
            binned[bin_center]["count"] += n
            binned[bin_center]["total_tricks"] += n * avg
        
        valid_bins = []
        avgs = []
        for b in sorted(binned.keys()):
            n = binned[b]["count"]
            if n >= 20:
                valid_bins.append(b)
                avgs.append(binned[b]["total_tricks"] / n)
        
        return valid_bins, avgs
    
    # Left panel: No-Trump contracts
    ax_nt = fig.add_subplot(gs_inner[0, 0])
    
    for label in ["high", "low"]:
        bins, avgs = get_binned_data(label)
        if bins:
            color = CONTRACT_COLORS.get(label, "#333")
            style = CONTRACT_LINESTYLES.get(label, "-")
            display_label = CONTRACT_LABELS.get(label, label)
            ax_nt.plot(bins, avgs, color=color, linestyle=style, linewidth=2, 
                      marker="o", markersize=4, label=display_label)
    
    ax_nt.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=0.5, alpha=0.7)
    ax_nt.set_title("No-Trump Contracts", fontsize=9, fontweight="bold")
    ax_nt.set_xlabel("Hand Score", fontsize=8)
    ax_nt.set_ylabel("Avg Tricks", fontsize=8)
    ax_nt.set_ylim(TRICKS_YLIM_EXTENDED)
    ax_nt.set_xlim(x_min, x_max)
    ax_nt.legend(loc="lower right", fontsize=7)
    ax_nt.tick_params(labelsize=6)
    
    # Right panel: Suit contracts
    ax_suit = fig.add_subplot(gs_inner[0, 1])
    
    for label in ["suit_C", "suit_D", "suit_H", "suit_S"]:
        bins, avgs = get_binned_data(label)
        if bins:
            color = CONTRACT_COLORS.get(label, "#333")
            style = CONTRACT_LINESTYLES.get(label, "-")
            display_label = CONTRACT_LABELS.get(label, label).replace("Trump-", "")
            ax_suit.plot(bins, avgs, color=color, linestyle=style, linewidth=2, 
                        marker="o", markersize=3, label=display_label)
    
    ax_suit.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=0.5, alpha=0.7)
    ax_suit.set_title("Suit Contracts", fontsize=9, fontweight="bold")
    ax_suit.set_xlabel("Hand Score", fontsize=8)
    ax_suit.set_ylim(TRICKS_YLIM_EXTENDED)
    ax_suit.set_xlim(x_min, x_max)
    ax_suit.legend(loc="lower right", fontsize=7, ncol=2)
    ax_suit.tick_params(labelsize=6)


def plot_suit_symmetry(ax, results: List[Dict]):
    """Panel 5: Suit Symmetry with raw means above bars."""
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
    
    # Add raw means above bars
    for i, (bar, mean) in enumerate(zip(bars, means)):
        ax.text(bar.get_x() + bar.get_width()/2, mean + cis[i] + 0.02, 
                f"{mean:.2f}", ha="center", va="bottom", fontsize=7, fontweight="bold")
    
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, fontweight="bold")
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
    
    ax.set_title(f"Suit Symmetry ({test_result})", fontsize=9)
    
    # Effect size annotation
    if means:
        delta = max(means) - min(means)
        pooled_std = np.std(np.concatenate(all_samples_list)) if all_samples_list else 1
        cohens_d = delta / pooled_std if pooled_std > 0 else 0
        
        ax.text(0.02, 0.98, f"Δmax={delta:.3f}\nd={cohens_d:.2f}", 
               transform=ax.transAxes, fontsize=7, va="top", fontfamily="monospace",
               bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))


def plot_win_rate_by_contract(ax, results: List[Dict]):
    """Panel 6: Win Rate by Contract Type (horizontal bars)."""
    win_rates = compute_win_rates(results)
    
    labels = list(win_rates.keys())
    rates = [win_rates[l][0] for l in labels]
    counts = [win_rates[l][1] for l in labels]
    colors = [CONTRACT_COLORS.get(l, "#95a5a6") for l in labels]
    display_labels = [CONTRACT_LABELS.get(l, l) for l in labels]
    
    sorted_data = sorted(zip(display_labels, rates, colors, counts, labels), key=lambda x: x[1])
    display_labels, rates, colors, counts, labels = zip(*sorted_data)
    
    y = np.arange(len(labels))
    ax.barh(y, rates, color=colors, alpha=0.8, edgecolor="white")
    
    ax.axvline(x=50, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels(display_labels)
    ax.set_xlabel("Win Rate (%)")
    ax.set_title("P(tricks ≥ 6) by Contract")
    ax.set_xlim(0, 100)
    
    for i, (rate, n) in enumerate(zip(rates, counts)):
        ax.text(rate + 1, i, f"{rate:.1f}%", va="center", fontsize=7)


def plot_trump_bowers_heatmap(ax, results: List[Dict]):
    """Panel 7: 2D Heatmap of trump_count × bowers → avg tricks (true joint when possible)."""
    # Backwards-compatible fallback: use marginals if no joint data is available.
    # The preferred path is to call this via generate_individual_plots or dashboard
    # using JSONL logs; see plot_trump_bowers_heatmap_from_logs below.
    merged = merge_feature_buckets(results)

    trump_buckets = merged.get("trump_count", {})
    bowers_buckets = merged.get("bowers", {})

    if not trump_buckets or not bowers_buckets:
        ax.text(0.5, 0.5, "No feature data", ha="center", va="center", transform=ax.transAxes)
        ax.set_title("Trump × Bowers → Tricks")
        return

    # Legacy approximation (kept only as fallback)
    heatmap = np.full((3, 11), np.nan)
    cell_counts = np.zeros((3, 11), dtype=int)

    bowers_effect = {}
    for b, stats in bowers_buckets.items():
        if stats["count"] >= MIN_SAMPLES_FOR_PLOT_LOW:
            bowers_effect[b] = stats["avg_tricks"] - 5

    for trump_val, trump_stats in trump_buckets.items():
        if 0 <= trump_val <= 10 and trump_stats["count"] >= MIN_SAMPLES_FOR_PLOT_LOW // 2:
            base_avg = trump_stats["avg_tricks"]
            for bowers_val in range(3):
                if bowers_val in bowers_effect:
                    adjusted = base_avg + bowers_effect[bowers_val] * 0.5
                    heatmap[bowers_val, trump_val] = np.clip(adjusted, 3, 7)
                    cell_counts[bowers_val, trump_val] = min(
                        trump_stats["count"],
                        bowers_buckets.get(bowers_val, {}).get("count", 0),
                    )

    _plot_trump_bowers_heatmap_matrix(ax, heatmap, cell_counts, title_suffix="(approx)")


def _plot_trump_bowers_heatmap_matrix(ax, mean: np.ndarray, counts: np.ndarray, title_suffix: str = "") -> None:
    """Shared helper to render a heatmap with value + n labels."""
    if mean.size == 0 or counts.size == 0:
        ax.text(0.5, 0.5, "No heatmap data", ha="center", va="center", transform=ax.transAxes)
        return

    mask = counts < (MIN_SAMPLES_FOR_PLOT_LOW // 2)
    mean_masked = np.ma.masked_where(mask, mean)

    max_trump = mean.shape[1] - 1
    max_bowers = mean.shape[0] - 1

    im = ax.imshow(
        mean_masked,
        cmap="RdYlGn",
        aspect="auto",
        vmin=4,
        vmax=6,
        origin="lower",
        extent=[-0.5, max_trump + 0.5, -0.5, max_bowers + 0.5],
    )

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Avg Tricks", fontsize=7)
    cbar.ax.tick_params(labelsize=6)

    for b in range(mean.shape[0]):
        for tc in range(mean.shape[1]):
            if mask[b, tc]:
                continue
            val = float(mean[b, tc])
            n = int(counts[b, tc])
            color = "white" if val < 4.5 or val > 5.5 else "black"
            ax.text(tc, b + 0.10, f"{val:.1f}", ha="center", va="center", fontsize=6, color=color, fontweight="bold")
            ax.text(tc, b - 0.20, f"n={n:,}", ha="center", va="center", fontsize=4, color="gray", alpha=0.8)

    ax.set_xlabel("Trump Count")
    ax.set_ylabel("Bowers")
    title = "Trump × Bowers → Tricks"
    if title_suffix:
        title = f"{title} {title_suffix}"
    ax.set_title(title)
    ax.set_xticks(range(0, max_trump + 1, 2))
    ax.set_yticks(list(range(0, max_bowers + 1)))


def plot_trump_bowers_heatmap_from_logs(ax, hand_records: List[Dict]) -> bool:
    """
    Plot true joint heatmap from JSONL logs. Returns True if plotted, False if not possible.
    """
    if not hand_records:
        return False
    mean, counts = compute_joint_trump_bowers_from_logs(hand_records)
    if np.all(np.isnan(mean)):
        return False
    _plot_trump_bowers_heatmap_matrix(ax, mean, counts, title_suffix="(joint)")
    return True


def plot_feature_correlations(ax, results: List[Dict], hand_records: List[Dict]):
    """Panel 8: Univariate Pearson correlations with tricks."""
    
    if hand_records:
        correlations = compute_feature_correlations_from_logs(hand_records)
        data_source = "raw"
    else:
        correlations = compute_feature_correlations_from_buckets(results)
        data_source = "agg"
    
    if not correlations:
        ax.text(0.5, 0.5, "No feature data", ha="center", va="center", 
               transform=ax.transAxes)
        ax.set_title("Feature Correlations")
        return
    
    sorted_features = sorted(correlations.items(), key=lambda x: -abs(x[1][0]))
    
    features = [f[0] for f in sorted_features]
    corrs = [f[1][0] for f in sorted_features]
    ns = [f[1][1] for f in sorted_features]
    colors = [FEATURE_COLORS.get(f, "#95a5a6") for f in features]
    
    y = np.arange(len(features))
    ax.barh(y, corrs, color=colors, alpha=0.8, edgecolor="white")
    ax.axvline(x=0, color="#2c3e50", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(features)
    ax.set_xlabel("Pearson r")
    ax.set_title("Feature → Tricks (directional)")
    
    ax.set_xlim(-0.5, 0.5)
    
    for i, (c, n) in enumerate(zip(corrs, ns)):
        ha = "left" if c >= 0 else "right"
        offset = 0.02 if c >= 0 else -0.02
        ax.text(c + offset, i, f"{c:.2f}", va="center", ha=ha, fontsize=7)
    
    total_n = sum(ns) // len(ns) if ns else 0
    ax.text(0.5, -0.12, f"(Pearson, {data_source}, n≈{total_n:,})", 
           transform=ax.transAxes, fontsize=6, ha="center", color="gray")


def plot_summary_with_metadata(ax, results: List[Dict], hand_records: List[Dict],
                                strategy_name: str, seed: Optional[int] = None):
    """Panel 9: Combined Summary Statistics + Run Metadata."""
    total_hands = sum(r.get("hands", 0) for r in results)
    player_samples = sum(r.get("player_samples", 0) for r in results)
    n_scenarios = len(results)
    
    merged_dist = merge_distributions(results)
    samples = []
    for tricks, count in merged_dist.items():
        samples.extend([tricks] * count)
    
    if samples:
        mean_tricks = np.mean(samples)
        std_tricks = np.std(samples, ddof=1)
        median_tricks = np.median(samples)
        n = len(samples)
        ci_95 = 1.96 * std_tricks / np.sqrt(n)
        
        win_count = sum(count for tricks, count in merged_dist.items() if tricks >= 6)
        win_rate = win_count / n * 100
        win_se = np.sqrt(win_rate * (100 - win_rate) / n)
        win_ci = 1.96 * win_se
    else:
        mean_tricks = std_tricks = median_tricks = ci_95 = 0
        win_rate = win_ci = 0
        n = 0
    
    # Compute R² approximation from correlations
    if hand_records:
        correlations = compute_feature_correlations_from_logs(hand_records)
    else:
        correlations = compute_feature_correlations_from_buckets(results)
    r_squared = sum(c**2 for c, _ in correlations.values()) if correlations else 0
    
    commit_hash = get_git_commit_hash()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    
    contracts = sorted(set(CONTRACT_LABELS.get(r.get("_label", "?"), "?") for r in results))
    contracts_str = ", ".join(contracts[:3])
    if len(contracts) > 3:
        contracts_str += f" +{len(contracts) - 3}"
    
    text = f"""SUMMARY & METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Strategy:      {strategy_name}
Seed:          {seed if seed else 'random'}
Scenarios:     {n_scenarios}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total hands:   {total_hands:,}
Player obs:    {player_samples:,}
Unit:          player-hand
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRICK DISTRIBUTION
Mean:          {mean_tricks:.3f} ± {ci_95:.3f}
Median:        {median_tricks:.1f}
Std:           {std_tricks:.3f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WIN RATE (≥6 tricks)
Rate:          {win_rate:.1f}% ± {win_ci:.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FEATURES
R² (approx):   {r_squared:.3f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python {python_version} | {commit_hash}
{datetime.now().strftime('%Y-%m-%d %H:%M')}"""
    
    ax.text(0.02, 0.98, text, transform=ax.transAxes, fontsize=7,
            verticalalignment="top", fontfamily="monospace",
            bbox=dict(boxstyle="round", facecolor="#f8f9fa", alpha=0.9))
    ax.axis("off")


# ============================================================================
# Main Dashboard Generator
# ============================================================================

def save_individual_plot(plot_func, filename: str, output_dir: str, 
                         figsize: Tuple[int, int] = (8, 6), **kwargs):
    """Save an individual plot to its own file."""
    fig, ax = plt.subplots(figsize=figsize, facecolor="white")
    plot_func(ax, **kwargs)
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return filepath


def save_individual_faceted_plot(plot_func, filename: str, output_dir: str,
                                  figsize: Tuple[int, int] = (10, 8), **kwargs):
    """Save a faceted plot that needs its own gridspec."""
    fig = plt.figure(figsize=figsize, facecolor="white")
    gs = gridspec.GridSpec(1, 1, figure=fig, left=0.08, right=0.95, top=0.92, bottom=0.08)
    plot_func(fig, gs[0, 0], **kwargs)
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    return filepath


def generate_individual_plots(
    results: List[Dict],
    hand_records: List[Dict],
    output_dir: str,
    strategy_name: str,
    seed: Optional[int] = None,
) -> List[str]:
    """Generate and save individual plots to a subdirectory."""
    
    plots_dir = os.path.join(output_dir, "individual_plots")
    os.makedirs(plots_dir, exist_ok=True)
    
    saved_files = []
    
    print(f"\n📁 Saving individual plots to: {plots_dir}")
    
    # 1. Trick Distribution
    fig, ax = plt.subplots(figsize=(10, 7), facecolor="white")
    plot_trick_distribution(ax, results)
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "01_trick_distribution.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 2. Violin Plot
    fig, ax = plt.subplots(figsize=(12, 7), facecolor="white")
    plot_tricks_vs_score_violin(ax, results, hand_records)
    ax.set_ylim(100, 900)  # Extended range for full visibility
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "02_score_by_tricks_violin.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 3. Feature vs Tricks (faceted) - with extended y-axis
    fig = plt.figure(figsize=(12, 10), facecolor="white")
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3,
                           left=0.08, right=0.95, top=0.94, bottom=0.08)
    
    merged = merge_feature_buckets(results)
    features = ["bowers", "trump_count", "offsuit_aces", "high_offsuit"]
    
    for idx, fname in enumerate(features):
        row, col = divmod(idx, 2)
        ax_sub = fig.add_subplot(gs[row, col])
        
        if fname not in merged:
            ax_sub.text(0.5, 0.5, "No data", ha="center", va="center", 
                       transform=ax_sub.transAxes, fontsize=9)
            ax_sub.set_title(fname, fontsize=11, pad=4)
            continue
        
        by_val = merged[fname]
        min_v, max_v = FEATURE_RANGES.get(fname, (0, 10))
        
        vals_high_n = []
        avg_tricks_high_n = []
        cis_high_n = []
        vals_low_n = []
        avg_tricks_low_n = []
        
        for v in sorted(by_val.keys()):
            if min_v <= v <= max_v:
                stats = by_val[v]
                n = stats["count"]
                
                if n >= MIN_SAMPLES_FOR_PLOT:
                    vals_high_n.append(v)
                    avg_tricks_high_n.append(stats["avg_tricks"])
                    se = 1.7 / np.sqrt(n)
                    cis_high_n.append(1.96 * se)
                elif n >= MIN_SAMPLES_FOR_PLOT_LOW:
                    vals_low_n.append(v)
                    avg_tricks_low_n.append(stats["avg_tricks"])
        
        color = FEATURE_COLORS.get(fname, "#3498db")
        
        if vals_low_n:
            ax_sub.scatter(vals_low_n, avg_tricks_low_n, color="lightgray", 
                          s=30, marker="o", zorder=1, alpha=0.6)
        
        if vals_high_n:
            ax_sub.errorbar(vals_high_n, avg_tricks_high_n, yerr=cis_high_n, 
                           fmt="o-", color=color, markersize=7, linewidth=2, 
                           capsize=4, capthick=1.5, zorder=2)
        
        ax_sub.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.5)
        
        ax_sub.set_title(fname, fontsize=11, pad=4)
        ax_sub.set_ylim(TRICKS_YLIM_EXTENDED)  # Extended for headroom
        ax_sub.set_xlim(min_v - 0.5, max_v + 0.5)
        ax_sub.set_xlabel(fname, fontsize=9)
        ax_sub.set_ylabel("Avg Tricks", fontsize=9)
        ax_sub.tick_params(labelsize=8)
        
        total_n = sum(stats["count"] for stats in by_val.values())
        ax_sub.text(0.95, 0.05, f"n={total_n:,}", transform=ax_sub.transAxes, 
                   fontsize=8, ha="right", color="gray")
    
    filepath = os.path.join(plots_dir, "03_feature_vs_tricks.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 4. Score vs Tricks Grouped (faceted) - with extended y-axis
    fig = plt.figure(figsize=(14, 6), facecolor="white")
    gs = gridspec.GridSpec(1, 2, figure=fig, wspace=0.25,
                           left=0.07, right=0.95, top=0.90, bottom=0.12)
    
    results_by_label = {r["_label"]: r for r in results}
    
    all_scores = []
    for result in results:
        buckets = get_score_buckets(result)
        all_scores.extend(buckets.keys())
    
    if all_scores:
        x_min = min(all_scores) // 50 * 50
        x_max = (max(all_scores) // 50 + 1) * 50
    else:
        x_min, x_max = 100, 800
    
    def get_binned_data(label):
        if label not in results_by_label:
            return [], []
        result = results_by_label[label]
        buckets = get_score_buckets(result)
        
        bin_size = 50
        binned = defaultdict(lambda: {"count": 0, "total_tricks": 0.0})
        for score, stats in buckets.items():
            bin_center = (score // bin_size) * bin_size + bin_size // 2
            n = stats["count"]
            avg = stats["avg_tricks"]
            binned[bin_center]["count"] += n
            binned[bin_center]["total_tricks"] += n * avg
        
        valid_bins = []
        avgs = []
        for b in sorted(binned.keys()):
            n = binned[b]["count"]
            if n >= 20:
                valid_bins.append(b)
                avgs.append(binned[b]["total_tricks"] / n)
        
        return valid_bins, avgs
    
    # Left panel: No-Trump contracts
    ax_nt = fig.add_subplot(gs[0, 0])
    
    for label in ["high", "low"]:
        bins, avgs = get_binned_data(label)
        if bins:
            color = CONTRACT_COLORS.get(label, "#333")
            style = CONTRACT_LINESTYLES.get(label, "-")
            display_label = CONTRACT_LABELS.get(label, label)
            ax_nt.plot(bins, avgs, color=color, linestyle=style, linewidth=2.5, 
                      marker="o", markersize=5, label=display_label)
    
    ax_nt.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.7)
    ax_nt.set_title("No-Trump Contracts", fontsize=11, fontweight="bold")
    ax_nt.set_xlabel("Hand Score", fontsize=10)
    ax_nt.set_ylabel("Avg Tricks", fontsize=10)
    ax_nt.set_ylim(TRICKS_YLIM_EXTENDED)
    ax_nt.set_xlim(x_min, x_max)
    ax_nt.legend(loc="lower right", fontsize=9)
    ax_nt.tick_params(labelsize=8)
    
    # Right panel: Suit contracts
    ax_suit = fig.add_subplot(gs[0, 1])
    
    for label in ["suit_C", "suit_D", "suit_H", "suit_S"]:
        bins, avgs = get_binned_data(label)
        if bins:
            color = CONTRACT_COLORS.get(label, "#333")
            style = CONTRACT_LINESTYLES.get(label, "-")
            display_label = CONTRACT_LABELS.get(label, label).replace("Trump-", "")
            ax_suit.plot(bins, avgs, color=color, linestyle=style, linewidth=2.5, 
                        marker="o", markersize=4, label=display_label)
    
    ax_suit.axhline(y=5, color="#bdc3c7", linestyle="--", linewidth=1, alpha=0.7)
    ax_suit.set_title("Suit Contracts", fontsize=11, fontweight="bold")
    ax_suit.set_xlabel("Hand Score", fontsize=10)
    ax_suit.set_ylim(TRICKS_YLIM_EXTENDED)
    ax_suit.set_xlim(x_min, x_max)
    ax_suit.legend(loc="lower right", fontsize=9, ncol=2)
    ax_suit.tick_params(labelsize=8)
    
    filepath = os.path.join(plots_dir, "04_score_vs_tricks_grouped.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 5. Suit Symmetry
    fig, ax = plt.subplots(figsize=(10, 7), facecolor="white")
    plot_suit_symmetry(ax, results)
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "05_suit_symmetry.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 6. Win Rate by Contract
    fig, ax = plt.subplots(figsize=(10, 7), facecolor="white")
    plot_win_rate_by_contract(ax, results)
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "06_win_rate_by_contract.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 7. Trump x Bowers Heatmap - prefer TRUE JOINT from JSONL logs when available
    fig, ax = plt.subplots(figsize=(12, 8), facecolor="white")

    plotted = plot_trump_bowers_heatmap_from_logs(ax, hand_records)
    if not plotted:
        # Fallback to the legacy approximation, but label it as such.
        plot_trump_bowers_heatmap(ax, results)
    
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "07_trump_bowers_heatmap.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 8. Feature Correlations
    fig, ax = plt.subplots(figsize=(10, 7), facecolor="white")
    plot_feature_correlations(ax, results, hand_records)
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "08_feature_correlations.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    # 9. Summary (text-based)
    fig, ax = plt.subplots(figsize=(8, 10), facecolor="white")
    plot_summary_with_metadata(ax, results, hand_records, strategy_name, seed)
    fig.tight_layout(pad=1.5)
    filepath = os.path.join(plots_dir, "09_summary_metadata.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none", bbox_inches="tight")
    plt.close(fig)
    saved_files.append(filepath)
    print(f"   ✓ {os.path.basename(filepath)}")
    
    print(f"\n   📊 Saved {len(saved_files)} individual plots")
    return saved_files


def generate_dashboard(
    data_dir: str = "data/raw",
    log_dir: str = "logs",
    run_id: Optional[str] = None,
    output_dir: str = "data/reports",
    strategy_name: str = "greedy",
    seed: Optional[int] = None,
    save_individual: bool = True,
) -> str:
    """Generate the unified dashboard report (v4.1)."""
    
    results = load_json_results(data_dir)
    hand_records = load_jsonl_logs(log_dir, run_id)
    
    # Create timestamped folder for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(output_dir, f"{strategy_name}_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    
    # Save individual plots first
    if save_individual:
        generate_individual_plots(results, hand_records, run_dir, strategy_name, seed)
    
    # Create figure with 3x3 layout
    fig = plt.figure(figsize=(14, 12), facecolor="white")
    fig.suptitle(f"BID EUCHRE ANALYSIS DASHBOARD — {strategy_name.upper()} (v4.1)", 
                 fontsize=14, fontweight="bold", y=0.98)
    
    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.06)
    
    # Row 1
    ax1 = fig.add_subplot(gs[0, 0])
    plot_trick_distribution(ax1, results)
    
    ax2 = fig.add_subplot(gs[0, 1])
    plot_tricks_vs_score_violin(ax2, results, hand_records)
    
    plot_feature_vs_tricks_faceted(fig, gs[0, 2], results)
    
    # Row 2
    plot_score_tricks_grouped(fig, gs[1, 0], results)
    
    ax5 = fig.add_subplot(gs[1, 1])
    plot_suit_symmetry(ax5, results)
    
    ax6 = fig.add_subplot(gs[1, 2])
    plot_win_rate_by_contract(ax6, results)
    
    # Row 3
    ax7 = fig.add_subplot(gs[2, 0])
    plotted = plot_trump_bowers_heatmap_from_logs(ax7, hand_records)
    if not plotted:
        plot_trump_bowers_heatmap(ax7, results)
    
    ax8 = fig.add_subplot(gs[2, 1])
    plot_feature_correlations(ax8, results, hand_records)
    
    ax9 = fig.add_subplot(gs[2, 2])
    plot_summary_with_metadata(ax9, results, hand_records, strategy_name, seed)
    
    # Save dashboard to the timestamped run directory
    filename = "dashboard.png"
    filepath = os.path.join(run_dir, filename)
    
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none")
    plt.close(fig)
    
    print(f"\n✅ Dashboard saved to: {filepath}")
    print(f"📁 Run folder: {run_dir}")
    return filepath


def generate_dashboard_from_loaded(
    results: List[Dict],
    hand_records: List[Dict],
    output_dir: str,
    strategy_name: str = "greedy",
    seed: Optional[int] = None,
    save_individual: bool = True,
) -> str:
    """
    Generate dashboard given already-loaded scenario results and JSONL hand records.

    This is used for standardized run layouts (data/runs/<run_id>/...).
    It writes a timestamped dashboard folder inside `output_dir`.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dash_dir = os.path.join(output_dir, f"{strategy_name}_{timestamp}")
    os.makedirs(dash_dir, exist_ok=True)

    if save_individual:
        generate_individual_plots(results, hand_records, dash_dir, strategy_name, seed)

    fig = plt.figure(figsize=(14, 12), facecolor="white")
    fig.suptitle(f"BID EUCHRE ANALYSIS DASHBOARD — {strategy_name.upper()} (v4.1)",
                 fontsize=14, fontweight="bold", y=0.98)

    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.4, wspace=0.35,
                           left=0.06, right=0.96, top=0.92, bottom=0.06)

    # Row 1
    ax1 = fig.add_subplot(gs[0, 0])
    plot_trick_distribution(ax1, results)

    ax2 = fig.add_subplot(gs[0, 1])
    plot_tricks_vs_score_violin(ax2, results, hand_records)

    plot_feature_vs_tricks_faceted(fig, gs[0, 2], results)

    # Row 2
    plot_score_tricks_grouped(fig, gs[1, 0], results)

    ax5 = fig.add_subplot(gs[1, 1])
    plot_suit_symmetry(ax5, results)

    ax6 = fig.add_subplot(gs[1, 2])
    plot_win_rate_by_contract(ax6, results)

    # Row 3
    ax7 = fig.add_subplot(gs[2, 0])
    plotted = plot_trump_bowers_heatmap_from_logs(ax7, hand_records)
    if not plotted:
        plot_trump_bowers_heatmap(ax7, results)

    ax8 = fig.add_subplot(gs[2, 1])
    plot_feature_correlations(ax8, results, hand_records)

    ax9 = fig.add_subplot(gs[2, 2])
    plot_summary_with_metadata(ax9, results, hand_records, strategy_name, seed)

    filepath = os.path.join(dash_dir, "dashboard.png")
    fig.savefig(filepath, dpi=150, facecolor="white", edgecolor="none")
    plt.close(fig)

    print(f"\n✅ Dashboard saved to: {filepath}")
    print(f"📁 Dashboard folder: {dash_dir}")
    return filepath


# ============================================================================
# CLI
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate unified Bid Euchre analysis dashboard (v4.1)"
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="If set, load standardized run outputs from this directory (data/runs/<run_id>)."
    )
    parser.add_argument(
        "--data-dir", "-d",
        default="data/raw",
        help="Directory containing JSON result files"
    )
    parser.add_argument(
        "--log-dir", "-l",
        default="logs",
        help="Directory containing JSONL log files"
    )
    parser.add_argument(
        "--run-id", "-r",
        default=None,
        help="Specific run ID to load from logs"
    )
    parser.add_argument(
        "--output-dir", "-o",
        default="data/reports",
        help="Output directory for dashboard"
    )
    parser.add_argument(
        "--strategy", "-s",
        default="greedy",
        help="Strategy name for labeling"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed used for the run"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    print("🎯 Generating Bid Euchre Analysis Dashboard (v4.1)")
    print("=" * 50)
    
    if args.run_dir:
        # Standardized layout: <run_dir>/{results/<strategy>,logs/}
        results = load_json_results_from_run_dir(args.run_dir, args.strategy)
        hand_records = load_jsonl_logs_from_run_dir(args.run_dir, args.strategy)
        # Write dashboard into <run_dir>/dashboard/...
        out_dir = os.path.join(args.run_dir, "dashboard")
        filepath = generate_dashboard_from_loaded(
            results=results,
            hand_records=hand_records,
            output_dir=out_dir,
            strategy_name=args.strategy,
            seed=args.seed,
        )
    else:
        filepath = generate_dashboard(
            data_dir=args.data_dir,
            log_dir=args.log_dir,
            run_id=args.run_id,
            output_dir=args.output_dir,
            strategy_name=args.strategy,
            seed=args.seed,
        )
    
    print(f"\n📊 Dashboard generation complete!")
    print(f"   Open: {filepath}")


if __name__ == "__main__":
    main()
