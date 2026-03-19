#!/usr/bin/env python3
"""Generate churn-corrected Bollinger Band dashboard for commit analytics.

Produces a 4-panel PNG:
  1. Raw commits with Bollinger Bands (working days only)
  2. Churn-corrected effective commits with Bollinger Bands
  3. Line churn ratio per working day
  4. File churn ratio per working day

Usage:
    uv run python scripts/generate_dashboard.py
    uv run python scripts/generate_dashboard.py --output path/to/out.png
    uv run python scripts/generate_dashboard.py --repo /path/to/repo
"""

from __future__ import annotations

import argparse
import os
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# ── Bollinger Band parameters ────────────────────────────────────────────
WINDOW = 10  # 10 working days ≈ 2 calendar weeks
NUM_STD = 2  # Standard 2σ bands


def _git(args: list[str], repo: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    return result.stdout


def _gather_commit_counts(repo: str) -> tuple[list[str], np.ndarray]:
    """Return sorted working-day dates and their commit counts."""
    output = _git(["log", "--format=%ad", "--date=short"], repo)
    counts = Counter(output.strip().split("\n"))
    sorted_dates = sorted(counts.keys())
    daily_commits = np.array([counts[d] for d in sorted_dates])
    return sorted_dates, daily_commits


def _gather_line_stats(repo: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return per-day insertions and deletions from git numstat."""
    output = _git(["log", "--format=COMMIT %ad", "--date=short", "--numstat"], repo)

    day_ins: dict[str, int] = defaultdict(int)
    day_del: dict[str, int] = defaultdict(int)

    date = None
    for line in output.split("\n"):
        if line.startswith("COMMIT"):
            date = line.split()[1]
        elif line and date:
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0] != "-":
                day_ins[date] += int(parts[0])
                day_del[date] += int(parts[1])

    return dict(day_ins), dict(day_del)


def _gather_file_churn(repo: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return per-day unique files and files touched more than once."""
    output = _git(["log", "--format=COMMIT %ad", "--date=short", "--numstat"], repo)

    file_touches: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    date = None
    for line in output.split("\n"):
        if line.startswith("COMMIT"):
            date = line.split()[1]
        elif line and date:
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0] != "-":
                file_touches[date][parts[2]] += 1

    unique_files = {d: len(files) for d, files in file_touches.items()}
    churned_files = {
        d: sum(1 for c in files.values() if c > 1) for d, files in file_touches.items()
    }
    return unique_files, churned_files


def _bollinger(
    data: np.ndarray, window: int, num_std: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute SMA, upper band, lower band, and %B."""
    n = len(data)
    sma = np.full(n, np.nan)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    pct_b = np.full(n, np.nan)

    for i in range(window - 1, n):
        w = data[i - window + 1 : i + 1]
        m, s = float(np.mean(w)), float(np.std(w, ddof=1))
        sma[i] = m
        upper[i] = m + num_std * s
        lower[i] = max(0, m - num_std * s)
        band_width = upper[i] - lower[i]
        pct_b[i] = (data[i] - lower[i]) / band_width if band_width > 0 else 0.5

    return sma, upper, lower, pct_b


def generate_dashboard(repo: str, output: str) -> None:
    """Generate the full dashboard PNG."""
    sorted_dates, raw_commits = _gather_commit_counts(repo)
    day_ins, day_del = _gather_line_stats(repo)
    unique_files_map, churned_files_map = _gather_file_churn(repo)

    n = len(sorted_dates)

    # ── Derived metrics ──────────────────────────────────────────────────
    gross_lines = np.array(
        [day_ins.get(d, 0) + day_del.get(d, 0) for d in sorted_dates], dtype=float
    )
    net_lines = np.array(
        [abs(day_ins.get(d, 0) - day_del.get(d, 0)) for d in sorted_dates],
        dtype=float,
    )
    churn_ratio = np.where(gross_lines > 0, 1 - net_lines / gross_lines, 0)

    unique_files = np.array(
        [unique_files_map.get(d, 0) for d in sorted_dates], dtype=float
    )
    churned_files = np.array(
        [churned_files_map.get(d, 0) for d in sorted_dates], dtype=float
    )
    file_churn_ratio = np.where(unique_files > 0, churned_files / unique_files, 0)

    effective_commits = raw_commits * (1 - churn_ratio)

    # ── Bollinger Bands ──────────────────────────────────────────────────
    raw_sma, raw_upper, raw_lower, raw_pctb = _bollinger(
        raw_commits.astype(float), WINDOW, NUM_STD
    )
    eff_sma, eff_upper, eff_lower, eff_pctb = _bollinger(
        effective_commits, WINDOW, NUM_STD
    )

    # ── Latest day (replaces hardcoded "today") ──────────────────────────
    latest_idx = n - 1

    # ── X-axis setup ─────────────────────────────────────────────────────
    x = np.arange(n)
    label_every = max(1, n // 15)
    tick_positions = list(range(0, n, label_every))
    if (n - 1) not in tick_positions:
        tick_positions.append(n - 1)
    tick_labels = [sorted_dates[i] for i in tick_positions]

    valid = ~np.isnan(raw_sma)

    # ── Plot ─────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(16, 15),
        gridspec_kw={"height_ratios": [3, 3, 1.2, 1.2]},
        sharex=True,
    )
    fig.suptitle(
        f"Commit Analytics Dashboard — Churn-Corrected Bollinger Bands\n"
        f"{WINDOW}-working-day SMA, {NUM_STD}\u03c3  \u2022  "
        f"effective commits = raw \u00d7 (1 \u2212 line churn ratio)  \u2022  "
        f"{n} active days",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )

    # ── Panel 1: Raw commits ─────────────────────────────────────────────
    ax1 = axes[0]
    _draw_bollinger_panel(
        ax1,
        x,
        raw_commits.astype(float),
        raw_sma,
        raw_upper,
        raw_lower,
        raw_pctb,
        valid,
        latest_idx,
        band_color="#3498db",
        sma_color="#2980b9",
        dot_color="#2c3e50",
    )
    ax1.set_ylabel("Raw commits", fontsize=11)
    ax1.set_title("Raw Commits (uncorrected)", fontsize=12, pad=4)

    # ── Panel 2: Effective commits ───────────────────────────────────────
    ax2 = axes[1]
    _draw_bollinger_panel(
        ax2,
        x,
        effective_commits,
        eff_sma,
        eff_upper,
        eff_lower,
        eff_pctb,
        valid,
        latest_idx,
        band_color="#27ae60",
        sma_color="#27ae60",
        dot_color="#1a5276",
    )
    ax2.set_ylabel("Effective commits", fontsize=11)
    ax2.set_title(
        "Churn-Corrected Commits  (raw \u00d7 (1 \u2212 churn ratio))",
        fontsize=12,
        pad=4,
    )

    # ── Panel 3: Line churn ratio ────────────────────────────────────────
    ax3 = axes[2]
    _draw_churn_bar(ax3, x, churn_ratio, latest_idx, "Line Churn Ratio")

    # ── Panel 4: File churn ratio ────────────────────────────────────────
    ax4 = axes[3]
    _draw_churn_bar(ax4, x, file_churn_ratio, latest_idx, "File Churn")
    ax4.set_xlabel("Working day", fontsize=11)

    # ── X-axis ticks ─────────────────────────────────────────────────────
    for ax in axes:
        ax.set_xticks(tick_positions)
    axes[-1].set_xticklabels(tick_labels, rotation=40, ha="right", fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.96])

    # ── Save ─────────────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Dashboard saved to {output}")

    # ── Summary stats ────────────────────────────────────────────────────
    li = latest_idx
    print(f"  Latest day: {sorted_dates[li]}")
    print(f"  Raw: {raw_commits[li]}, SMA: {raw_sma[li]:.1f}, %B: {raw_pctb[li]:.2f}")
    print(
        f"  Effective: {effective_commits[li]:.1f}, "
        f"SMA: {eff_sma[li]:.1f}, %B: {eff_pctb[li]:.2f}"
    )
    print(f"  Line churn: {churn_ratio[li] * 100:.1f}%")
    print(f"  File churn: {file_churn_ratio[li] * 100:.1f}%")


def _draw_bollinger_panel(
    ax: plt.Axes,
    x: np.ndarray,
    data: np.ndarray,
    sma: np.ndarray,
    upper: np.ndarray,
    lower: np.ndarray,
    pct_b: np.ndarray,
    valid: np.ndarray,
    latest_idx: int,
    *,
    band_color: str,
    sma_color: str,
    dot_color: str,
) -> None:
    """Draw a single Bollinger Band panel."""
    light_band = band_color
    ax.fill_between(
        x[valid], lower[valid], upper[valid], color=light_band, alpha=0.10, zorder=1
    )
    ax.plot(x[valid], sma[valid], color=sma_color, linewidth=2.5, zorder=4)
    ax.plot(
        x[valid], upper[valid], color=light_band, lw=1, ls="--", alpha=0.6, zorder=2
    )
    ax.plot(
        x[valid], lower[valid], color=light_band, lw=1, ls="--", alpha=0.6, zorder=2
    )
    ax.plot(x, data, color=dot_color, linewidth=1, alpha=0.4, zorder=2)

    for i in range(len(x)):
        if np.isnan(sma[i]):
            c = "#bdc3c7"
        elif data[i] > upper[i]:
            c = "#e74c3c"
        elif data[i] < lower[i]:
            c = "#27ae60"
        else:
            c = dot_color
        is_latest = i == latest_idx
        ax.scatter(
            x[i],
            data[i],
            c=c,
            s=150 if is_latest else 25,
            marker="*" if is_latest else "o",
            edgecolors="black" if is_latest else "white",
            linewidth=1.5 if is_latest else 0.4,
            zorder=6 if is_latest else 3,
            alpha=0.9,
        )

    # Latest-day label
    if not np.isnan(sma[latest_idx]):
        sigma = (
            (data[latest_idx] - sma[latest_idx])
            / ((upper[latest_idx] - sma[latest_idx]) / NUM_STD)
            if (upper[latest_idx] - sma[latest_idx]) > 0
            else 0
        )
        ax.text(
            0.99,
            0.95,
            f"Latest: {data[latest_idx]:.0f}  SMA: {sma[latest_idx]:.0f}  "
            f"%B: {pct_b[latest_idx]:.2f}  ({sigma:+.1f}\u03c3)",
            transform=ax.transAxes,
            fontsize=9,
            ha="right",
            va="top",
            fontweight="bold",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="#ffeaa7",
                edgecolor=sma_color,
                alpha=0.9,
            ),
            zorder=7,
        )

    # Stats bar
    n_valid = int(np.sum(valid))
    n_above = sum(
        1 for i in range(len(x)) if not np.isnan(sma[i]) and data[i] > upper[i]
    )
    n_below = sum(
        1 for i in range(len(x)) if not np.isnan(sma[i]) and data[i] < lower[i]
    )
    n_within = n_valid - n_above - n_below
    ax.text(
        0.99,
        0.03,
        f"Above: {n_above}/{n_valid} ({100 * n_above / n_valid:.0f}%)  "
        f"Below: {n_below}/{n_valid} ({100 * n_below / n_valid:.0f}%)  "
        f"Within: {n_within}/{n_valid} ({100 * n_within / n_valid:.0f}%)",
        transform=ax.transAxes,
        fontsize=8,
        ha="right",
        va="bottom",
        bbox=dict(
            boxstyle="round,pad=0.3",
            facecolor="white",
            edgecolor="#bdc3c7",
            alpha=0.85,
        ),
        fontfamily="monospace",
        zorder=7,
    )

    # Legend
    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#e74c3c",
            markersize=8,
            label="Above upper band",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor=dot_color,
            markersize=8,
            label="Within bands",
        ),
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="#27ae60",
            markersize=8,
            label="Below lower band",
        ),
        Line2D([0], [0], color=sma_color, linewidth=2.5, label=f"{WINDOW}-day SMA"),
        Line2D(
            [0],
            [0],
            color=light_band,
            linewidth=8,
            alpha=0.15,
            label=f"\u00b1{NUM_STD}\u03c3 band",
        ),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=8, framealpha=0.9)
    ax.grid(axis="y", alpha=0.15, zorder=0)
    ax.set_ylim(0, float(np.max(data)) * 1.15)
    ax.set_xlim(-1, len(x) + 0.5)


def _draw_churn_bar(
    ax: plt.Axes,
    x: np.ndarray,
    ratio: np.ndarray,
    latest_idx: int,
    title: str,
) -> None:
    """Draw a churn ratio bar panel."""
    colors = [
        "#e74c3c" if r > 0.5 else "#e67e22" if r > 0.3 else "#3498db" for r in ratio
    ]
    colors[latest_idx] = "#c0392b"
    ax.bar(x, ratio * 100, color=colors, alpha=0.75, width=0.7, zorder=2)
    median_val = float(np.median(ratio)) * 100
    ax.axhline(
        median_val,
        color="#2c3e50",
        linewidth=1,
        linestyle="--",
        alpha=0.5,
        label=f"Median: {median_val:.0f}%",
    )
    ax.set_ylabel(f"{title} %", fontsize=11)
    ax.set_title(title, fontsize=10, pad=4)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.15, zorder=0)
    ax.set_ylim(0, 100)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate commit analytics dashboard")
    parser.add_argument(
        "--output",
        default="assets/dashboard/commit_bollinger.png",
        help="Output path for the PNG (default: assets/dashboard/commit_bollinger.png)",
    )
    parser.add_argument(
        "--repo",
        default=".",
        help="Path to git repository (default: current directory)",
    )
    args = parser.parse_args()

    repo = str(Path(args.repo).resolve())
    generate_dashboard(repo, args.output)


if __name__ == "__main__":
    main()
