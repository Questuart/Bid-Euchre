#!/usr/bin/env python3
"""PR analytics Bollinger Band dashboard.

Produces a 5-panel PNG:
  1. PRs merged per day with Bollinger Bands (working days only)
  2. Net lines per day with Bollinger Bands (additions - deletions from PRs)
  3. Additions merged per day with Bollinger Bands (volume-weighted)
  4. Line churn ratio with Bollinger Bands (percentage)
  5. File churn ratio with Bollinger Bands (percentage)

Usage:
    uv run python scripts/generate_dashboard.py
    uv run python scripts/generate_dashboard.py --output path/to/out.png
    uv run python scripts/generate_dashboard.py --repo /path/to/repo
"""

from __future__ import annotations

import argparse
import json as _json
import logging
import os
import subprocess
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

# ── Bollinger Band parameters ────────────────────────────────────────────
WINDOW = 10  # 10 active days (any day with commits)
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


_GH_PR_LIMIT = 10_000


def _gather_pr_counts(
    repo: str,
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """Return per-day PR merge counts, additions, and deletions from merged PRs.

    Uses ``gh pr list`` as the data source.  Requires the ``gh`` CLI to be
    installed and authenticated.

    Warns when the number of PRs returned equals ``_GH_PR_LIMIT``, which
    indicates the result set may be truncated.
    """
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--state",
            "merged",
            "--json",
            "mergedAt,additions,deletions",
            "--limit",
            str(_GH_PR_LIMIT),
        ],
        capture_output=True,
        text=True,
        cwd=repo,
        check=True,
    )
    prs = _json.loads(result.stdout)

    if len(prs) >= _GH_PR_LIMIT:
        logger.warning(
            "gh pr list returned %d PRs (the configured limit). "
            "Results may be truncated — consider increasing _GH_PR_LIMIT.",
            len(prs),
        )

    pr_counts: dict[str, int] = defaultdict(int)
    pr_additions: dict[str, int] = defaultdict(int)
    pr_deletions: dict[str, int] = defaultdict(int)

    for pr in prs:
        merged_at = pr.get("mergedAt", "")
        if not merged_at:
            continue
        date = merged_at[:10]  # YYYY-MM-DD
        pr_counts[date] += 1
        pr_additions[date] += pr.get("additions", 0)
        pr_deletions[date] += pr.get("deletions", 0)

    return dict(pr_counts), dict(pr_additions), dict(pr_deletions)


def _gather_line_stats(repo: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return per-day insertions and deletions from git numstat (commit date)."""
    output = _git(["log", "--format=COMMIT %cd", "--date=short", "--numstat"], repo)

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
    """Return per-day unique files and files touched more than once (commit date)."""
    output = _git(["log", "--format=COMMIT %cd", "--date=short", "--numstat"], repo)

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
    data: np.ndarray,
    window: int,
    num_std: int,
    *,
    clamp_lower: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Compute SMA, upper band, lower band, and %B.

    Args:
        clamp_lower: If ``True`` (default), clamp the lower band at zero.
            Set to ``False`` for metrics that can go negative (e.g. net lines).
    """
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
        lower[i] = max(0, m - num_std * s) if clamp_lower else m - num_std * s
        band_width = upper[i] - lower[i]
        pct_b[i] = (data[i] - lower[i]) / band_width if band_width > 0 else 0.5

    return sma, upper, lower, pct_b


def generate_dashboard(repo: str, output: str) -> None:
    """Generate the full dashboard PNG."""
    pr_counts_map, pr_additions_map, pr_deletions_map = _gather_pr_counts(repo)
    day_ins, day_del = _gather_line_stats(repo)
    unique_files_map, churned_files_map = _gather_file_churn(repo)

    # Union of all active dates across both data sources
    sorted_dates = sorted(
        set(pr_counts_map.keys())
        | set(day_ins.keys())
        | set(day_del.keys())
        | set(unique_files_map.keys())
    )
    n = len(sorted_dates)

    # ── Panel 1/2/3 metrics (PR-based) ───────────────────────────────────
    raw_prs = np.array([pr_counts_map.get(d, 0) for d in sorted_dates], dtype=float)
    pr_additions = np.array(
        [pr_additions_map.get(d, 0) for d in sorted_dates], dtype=float
    )
    pr_net_lines = np.array(
        [pr_additions_map.get(d, 0) - pr_deletions_map.get(d, 0) for d in sorted_dates],
        dtype=float,
    )

    # ── Panel 4/5 metrics (git-log-based, commit date) ───────────────────
    gross_lines = np.array(
        [day_ins.get(d, 0) + day_del.get(d, 0) for d in sorted_dates], dtype=float
    )
    net_lines = np.array(
        [abs(day_ins.get(d, 0) - day_del.get(d, 0)) for d in sorted_dates],
        dtype=float,
    )
    safe_gross = np.where(gross_lines > 0, gross_lines, 1.0)
    churn_ratio = np.where(gross_lines > 0, 1 - net_lines / safe_gross, 0.0)

    unique_files = np.array(
        [unique_files_map.get(d, 0) for d in sorted_dates], dtype=float
    )
    churned_files = np.array(
        [churned_files_map.get(d, 0) for d in sorted_dates], dtype=float
    )
    safe_unique = np.where(unique_files > 0, unique_files, 1.0)
    file_churn_ratio = np.where(unique_files > 0, churned_files / safe_unique, 0.0)

    # ── Bollinger Bands ──────────────────────────────────────────────────
    raw_sma, raw_upper, raw_lower, raw_pctb = _bollinger(raw_prs, WINDOW, NUM_STD)
    net_sma, net_upper, net_lower, net_pctb = _bollinger(
        pr_net_lines, WINDOW, NUM_STD, clamp_lower=False
    )
    add_sma, add_upper, add_lower, add_pctb = _bollinger(pr_additions, WINDOW, NUM_STD)

    # Churn ratios as percentages for Bollinger computation
    churn_pct = churn_ratio * 100
    file_churn_pct = file_churn_ratio * 100
    lc_sma, lc_upper, lc_lower, lc_pctb = _bollinger(churn_pct, WINDOW, NUM_STD)
    fc_sma, fc_upper, fc_lower, fc_pctb = _bollinger(file_churn_pct, WINDOW, NUM_STD)

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
    net_valid = ~np.isnan(net_sma)
    add_valid = ~np.isnan(add_sma)
    churn_valid = ~np.isnan(lc_sma)
    fc_valid = ~np.isnan(fc_sma)

    # ── Plot ─────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(
        5,
        1,
        figsize=(16, 25),
        gridspec_kw={"height_ratios": [3, 3, 3, 2.5, 2.5]},
        sharex=True,
    )
    fig.suptitle(
        f"PR Analytics Dashboard \u2014 Bollinger Bands\n"
        f"{WINDOW}-working-day SMA, {NUM_STD}\u03c3  \u2022  "
        f"data source: gh pr list  \u2022  "
        f"{n} active days",
        fontsize=14,
        fontweight="bold",
        y=0.995,
    )

    # ── Panel 1: PRs merged per day ──────────────────────────────────────
    ax1 = axes[0]
    _draw_bollinger_panel(
        ax1,
        x,
        raw_prs,
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
    ax1.set_ylabel("PRs merged", fontsize=11)
    ax1.set_title("PRs Merged per Day", fontsize=12, pad=4)

    # ── Panel 2: Net lines per day ───────────────────────────────────────
    ax2 = axes[1]
    _draw_bollinger_panel(
        ax2,
        x,
        pr_net_lines,
        net_sma,
        net_upper,
        net_lower,
        net_pctb,
        net_valid,
        latest_idx,
        band_color="#16a085",
        sma_color="#1abc9c",
        dot_color="#2c3e50",
        allow_negative=True,
    )
    ax2.set_ylabel("Net lines", fontsize=11)
    ax2.set_title(
        "Net Lines per Day  (additions \u2212 deletions from PRs)",
        fontsize=12,
        pad=4,
    )
    ax2.axhline(y=0, color="#7f8c8d", linewidth=0.8, linestyle="-", alpha=0.5, zorder=1)

    # ── Panel 3: Additions merged per day ────────────────────────────────
    ax3 = axes[2]
    _draw_bollinger_panel(
        ax3,
        x,
        pr_additions,
        add_sma,
        add_upper,
        add_lower,
        add_pctb,
        add_valid,
        latest_idx,
        band_color="#27ae60",
        sma_color="#27ae60",
        dot_color="#1a5276",
    )
    ax3.set_ylabel("Additions merged", fontsize=11)
    ax3.set_title(
        "Additions Merged per Day  (volume-weighted PR activity)",
        fontsize=12,
        pad=4,
    )

    # ── Panel 4: Line churn ratio (Bollinger) ───────────────────────────
    ax4 = axes[3]
    _draw_bollinger_panel(
        ax4,
        x,
        churn_pct,
        lc_sma,
        lc_upper,
        lc_lower,
        lc_pctb,
        churn_valid,
        latest_idx,
        band_color="#e67e22",
        sma_color="#d35400",
        dot_color="#7f8c8d",
        max_y=100.0,
        fmt=".1f",
    )
    ax4.set_ylabel("Line churn %", fontsize=11)
    ax4.set_title("Line Churn Ratio  (1 \u2212 net/gross)", fontsize=12, pad=4)

    # ── Panel 5: File churn ratio (Bollinger) ─────────────────────────
    ax5 = axes[4]
    _draw_bollinger_panel(
        ax5,
        x,
        file_churn_pct,
        fc_sma,
        fc_upper,
        fc_lower,
        fc_pctb,
        fc_valid,
        latest_idx,
        band_color="#8e44ad",
        sma_color="#6c3483",
        dot_color="#7f8c8d",
        max_y=100.0,
        fmt=".1f",
    )
    ax5.set_ylabel("File churn %", fontsize=11)
    ax5.set_title(
        "File Churn Ratio  (multi-touch files / unique files)", fontsize=12, pad=4
    )
    ax5.set_xlabel("Working day", fontsize=11)

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
    print(
        f"  PRs merged: {raw_prs[li]:.0f}, "
        f"SMA: {raw_sma[li]:.1f}, %B: {raw_pctb[li]:.2f}"
    )
    print(
        f"  Net lines: {pr_net_lines[li]:+.0f}, "
        f"SMA: {net_sma[li]:+.1f}, %B: {net_pctb[li]:.2f}"
    )
    print(
        f"  Additions: {pr_additions[li]:.0f}, "
        f"SMA: {add_sma[li]:.1f}, %B: {add_pctb[li]:.2f}"
    )
    print(
        f"  Line churn: {churn_pct[li]:.1f}%, "
        f"SMA: {lc_sma[li]:.1f}%, %B: {lc_pctb[li]:.2f}"
    )
    print(
        f"  File churn: {file_churn_pct[li]:.1f}%, "
        f"SMA: {fc_sma[li]:.1f}%, %B: {fc_pctb[li]:.2f}"
    )


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
    max_y: float | None = None,
    fmt: str = ".0f",
    allow_negative: bool = False,
) -> None:
    """Draw a single Bollinger Band panel.

    Args:
        max_y: Hard cap for y-axis (e.g. 100 for percentage panels).
        fmt: Format specifier for latest-day label values (e.g. ".0f", ".1f").
        allow_negative: If ``True``, allow y-axis to extend below zero
            (for metrics like net lines that can be negative).
    """
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
            f"Latest: {data[latest_idx]:{fmt}}  SMA: {sma[latest_idx]:{fmt}}  "
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
    if n_valid > 0:
        stats_text = (
            f"Above: {n_above}/{n_valid} ({100 * n_above / n_valid:.0f}%)  "
            f"Below: {n_below}/{n_valid} ({100 * n_below / n_valid:.0f}%)  "
            f"Within: {n_within}/{n_valid} ({100 * n_within / n_valid:.0f}%)"
        )
    else:
        stats_text = "Insufficient data for Bollinger statistics"
    ax.text(
        0.99,
        0.03,
        stats_text,
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
    y_top = max_y if max_y is not None else float(np.max(data)) * 1.15
    if allow_negative:
        y_bot = float(np.min(data)) * 1.15 if float(np.min(data)) < 0 else 0
        ax.set_ylim(y_bot, y_top)
    else:
        ax.set_ylim(0, y_top)
    ax.set_xlim(-1, len(x) + 0.5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PR analytics dashboard")
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
