#!/usr/bin/env python
"""Generate markdown rung report from canonical CSV tables and chart PNGs.

Reads CSVs from tables/ and PNGs from charts/ and renders a structured
markdown report (01_results.md) with sections matching the canonical
rung report structure.

Usage:
    uv run python scripts/internal/generate_rung_report.py \\
        --report-dir /tmp/rung_report
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _read_csv_safe(path: Path) -> pd.DataFrame | None:
    """Read a CSV, returning None if not found or empty."""
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
        return df if len(df) > 0 else None
    except Exception as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def _table_placeholder(table_name: str) -> str:
    """Return a placeholder for a missing table."""
    return f"> [table_name={table_name}] not yet generated\n"


def _chart_placeholder(chart_name: str) -> str:
    """Return a placeholder for a missing chart."""
    return f"> [chart_name={chart_name}] not yet generated\n"


def _df_to_markdown(df: pd.DataFrame, float_format: str = "%.4f") -> str:
    """Convert a DataFrame to a markdown table string."""
    # Format float columns
    formatted = df.copy()
    for col in formatted.select_dtypes(include=["float64", "float32"]).columns:
        formatted[col] = formatted[col].apply(
            lambda x: float_format % x if pd.notna(x) else ""
        )

    # Build header
    cols = list(formatted.columns)
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join(["---"] * len(cols)) + " |"

    # Build rows
    rows = []
    for _, row in formatted.iterrows():
        cells = [str(row[c]) if pd.notna(row[c]) else "" for c in cols]
        rows.append("| " + " | ".join(cells) + " |")

    return "\n".join([header, separator] + rows) + "\n"


def _chart_embed(charts_dir: Path, chart_name: str) -> str:
    """Return markdown image embed or placeholder for a chart."""
    chart_path = charts_dir / chart_name
    if chart_path.exists():
        return f"![{chart_name}](charts/{chart_name})\n"
    return _chart_placeholder(chart_name)


def generate_report(report_dir: Path) -> str:
    """Generate the 01_results.md report from tables and charts.

    Args:
        report_dir: Directory containing tables/*.csv and charts/*.png.

    Returns:
        Rendered markdown report string.
    """
    tables_dir = report_dir / "tables"
    charts_dir = report_dir / "charts"

    lines = [
        "# Rung Results Report",
        "",
        "Generated from canonical CSV tables and chart PNGs.",
        "",
    ]

    # §1 Data Sanity
    lines.extend(
        [
            "## 1. Data Sanity",
            "",
        ]
    )
    data_sanity = _read_csv_safe(tables_dir / "data_sanity.csv")
    if data_sanity is not None:
        lines.append(_df_to_markdown(data_sanity))
    else:
        lines.append(_table_placeholder("data_sanity.csv"))
    lines.append("")

    # §2 Offline Model Performance
    lines.extend(
        [
            "## 2. Offline Model Performance",
            "",
        ]
    )
    model_perf = _read_csv_safe(tables_dir / "model_performance.csv")
    if model_perf is not None:
        lines.append(_df_to_markdown(model_perf))
    else:
        lines.append(_table_placeholder("model_performance.csv"))
    lines.append("")

    # R² and MAE charts
    lines.append(_chart_embed(charts_dir, "r2_by_contract.png"))
    lines.append(_chart_embed(charts_dir, "mae_by_contract.png"))
    lines.append("")

    # §3 Offline Diagnostics
    lines.extend(
        [
            "## 3. Offline Diagnostics",
            "",
        ]
    )
    for chart_name in [
        "pred_vs_actual_scatter.png",
        "residual_distribution.png",
        "calibration_curve.png",
    ]:
        lines.append(_chart_embed(charts_dir, chart_name))
    lines.append("")

    # §4 Model Interpretability (optional — graceful skip)
    lines.extend(
        [
            "## 4. Model Interpretability",
            "",
        ]
    )
    interp_charts = [
        "coefficient_heatmap.png",
    ]
    has_interp = False
    for chart_name in interp_charts:
        if (charts_dir / chart_name).exists():
            lines.append(_chart_embed(charts_dir, chart_name))
            has_interp = True
    if not has_interp:
        lines.append("*Interpretability charts not yet generated (PR 3b).*\n")
    lines.append("")

    # §5 Cross-Model Decision Analysis (optional — graceful skip)
    lines.extend(
        [
            "## 5. Cross-Model Decision Analysis",
            "",
            "*Decision comparison analysis not yet generated (PR 3b).*",
            "",
        ]
    )

    # §6 Comparator Rankings
    lines.extend(
        [
            "## 6. Comparator Rankings",
            "",
        ]
    )
    comparator = _read_csv_safe(tables_dir / "comparator_rankings.csv")
    if comparator is not None:
        lines.append(_df_to_markdown(comparator))
    else:
        lines.append(_table_placeholder("comparator_rankings.csv"))
    lines.append("")

    lines.append(_chart_embed(charts_dir, "comparator_ranking_bars.png"))
    lines.append(_chart_embed(charts_dir, "tail_risk_panel.png"))
    lines.append("")

    # §7 H2H Battery
    lines.extend(
        [
            "## 7. H2H Battery",
            "",
        ]
    )
    h2h = _read_csv_safe(tables_dir / "h2h_delta_matrix.csv")
    if h2h is not None:
        lines.append(_df_to_markdown(h2h))
    else:
        lines.append(_table_placeholder("h2h_delta_matrix.csv"))
    lines.append("")

    lines.append(_chart_embed(charts_dir, "delta_bars_by_contract.png"))
    lines.append(_chart_embed(charts_dir, "h2h_heatmap.png"))
    lines.append("")

    # §8 Behavioral Analysis
    lines.extend(
        [
            "## 8. Behavioral Analysis",
            "",
        ]
    )
    behavior = _read_csv_safe(tables_dir / "behavior_summary.csv")
    if behavior is not None:
        lines.append("### Pooled Behavior Summary\n")
        lines.append(_df_to_markdown(behavior))
    else:
        lines.append(_table_placeholder("behavior_summary.csv"))
    lines.append("")

    behavior_contract = _read_csv_safe(tables_dir / "behavior_by_contract.csv")
    if behavior_contract is not None:
        lines.append("### Behavior by Contract\n")
        lines.append(_df_to_markdown(behavior_contract))
    else:
        lines.append(_table_placeholder("behavior_by_contract.csv"))
    lines.append("")

    lines.append(_chart_embed(charts_dir, "bid_behavior_panel.png"))
    lines.append(_chart_embed(charts_dir, "contract_mix_bars.png"))
    lines.append("")

    # §9 Sanity Bounds
    lines.extend(
        [
            "## 9. Sanity Bounds",
            "",
        ]
    )
    sanity = _read_csv_safe(tables_dir / "sanity_bounds_check.csv")
    if sanity is not None:
        lines.append(_df_to_markdown(sanity))
    else:
        lines.append(_table_placeholder("sanity_bounds_check.csv"))
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate markdown rung report from CSV tables and chart PNGs."
    )
    parser.add_argument(
        "--report-dir",
        required=True,
        type=Path,
        help="Directory containing tables/*.csv and charts/*.png",
    )
    parser.add_argument(
        "--output",
        default=None,
        type=Path,
        help="Output file path (default: report-dir/01_results.md)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    report_content = generate_report(args.report_dir)

    output_path = args.output or (args.report_dir / "01_results.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_content)
    logger.info("Wrote report: %s", output_path)


if __name__ == "__main__":
    main()
