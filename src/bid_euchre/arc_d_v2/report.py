"""Markdown rung report generation from canonical CSV tables and chart PNGs.

Reads CSVs from tables/ and PNGs from charts/ and renders structured
markdown reports:

- ``01_results.md`` — full results report with all sections
- ``02_decision.md`` — concise decision report with advancement recommendation

Extracted from ``scripts/internal/generate_rung_report.py``.
"""

from __future__ import annotations

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

    # Dashboard overview — three composite chart pages
    dashboards = [
        ("dashboard_competitive.png", "Competitive Dashboard"),
        ("dashboard_health.png", "Health Dashboard"),
        ("dashboard_model_eval.png", "Model Evaluation Dashboard"),
    ]
    has_dashboards = any((charts_dir / d[0]).exists() for d in dashboards)
    if has_dashboards:
        lines.extend(
            [
                "## Dashboards",
                "",
            ]
        )
        for dash_file, dash_title in dashboards:
            if (charts_dir / dash_file).exists():
                lines.append(f"### {dash_title}\n")
                lines.append(f"![{dash_title}](charts/{dash_file})\n")
            else:
                lines.append(f"### {dash_title}\n")
                lines.append(_chart_placeholder(dash_file))
        lines.append("")

    # section 1 Data Sanity
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

    # section 2 Offline Model Performance
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

    # R-squared and MAE charts
    lines.append(_chart_embed(charts_dir, "r2_by_contract.png"))
    lines.append(_chart_embed(charts_dir, "mae_by_contract.png"))
    lines.append("")

    # section 3 Offline Diagnostics
    lines.extend(
        [
            "## 3. Offline Diagnostics",
            "",
        ]
    )
    for chart_name in [
        "pred_vs_actual.png",
        "residual_distribution.png",
        "calibration_curve.png",
        "feature_importance.png",
    ]:
        lines.append(_chart_embed(charts_dir, chart_name))
    lines.append("")

    # section 4 Model Interpretability (optional -- graceful skip)
    lines.extend(
        [
            "## 4. Model Interpretability",
            "",
        ]
    )
    interp_charts = [
        "shap_summary.png",
        "shap_dependence_top5.png",
        "selection_path.png",
    ]
    has_interp = False
    for chart_name in interp_charts:
        if (charts_dir / chart_name).exists():
            lines.append(_chart_embed(charts_dir, chart_name))
            has_interp = True
    if not has_interp:
        lines.append("*Interpretability charts not yet generated.*\n")
    lines.append("")

    # section 5 Cross-Model Decision Analysis (optional -- graceful skip)
    lines.extend(
        [
            "## 5. Cross-Model Decision Analysis",
            "",
        ]
    )
    decision_charts = [
        "decision_agreement.png",
        "disagreement_outcomes.png",
    ]
    has_decision = False
    for chart_name in decision_charts:
        if (charts_dir / chart_name).exists():
            lines.append(_chart_embed(charts_dir, chart_name))
            has_decision = True
    if not has_decision:
        lines.append("*Decision comparison analysis not yet generated.*\n")
    lines.append("")

    # section 6 Comparator Rankings
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

    # section 7 H2H Battery
    lines.extend(
        [
            "## 7. H2H Battery",
            "",
        ]
    )
    # Charts first, compact table excerpt below
    lines.append(_chart_embed(charts_dir, "delta_bars_by_contract.png"))
    lines.append(_chart_embed(charts_dir, "h2h_heatmap.png"))
    lines.append("")

    h2h = _read_csv_safe(tables_dir / "h2h_delta_matrix.csv")
    if h2h is not None:
        lines.append(
            "<details><summary>Full H2H Delta Matrix (click to expand)</summary>\n"
        )
        lines.append(_df_to_markdown(h2h))
        lines.append("\n</details>\n")
    else:
        lines.append(_table_placeholder("h2h_delta_matrix.csv"))
    lines.append("")

    # section 8 Behavioral Analysis
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

    # section 9 Sanity Bounds
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
#  Decision report (02_decision.md)
# ──────────────────────────────────────────────


def _extract_advancement_decision(
    hypothesis_outcomes: pd.DataFrame | None,
) -> str:
    """Determine advancement decision from hypothesis outcomes.

    Returns one of: ADVANCE, HOLD, HALT, PENDING.
    """
    if hypothesis_outcomes is None or len(hypothesis_outcomes) == 0:
        return "PENDING"

    if "status" not in hypothesis_outcomes.columns:
        return "PENDING"

    statuses = hypothesis_outcomes["status"].str.upper().tolist()
    if not statuses:
        return "PENDING"

    n_fail = sum(1 for s in statuses if s == "FAIL")
    n_pass = sum(1 for s in statuses if s == "PASS")

    if n_fail > 0:
        return "HALT"
    if n_pass == len(statuses):
        return "ADVANCE"
    return "HOLD"


def _top_n_comparator_table(
    comparator: pd.DataFrame | None,
    n: int = 3,
) -> str:
    """Build a concise top-N comparator table (pooled facet only)."""
    if comparator is None:
        return _table_placeholder("comparator_rankings.csv")

    if "facet" in comparator.columns:
        pooled = comparator[comparator["facet"] == "pooled"].copy()
    else:
        pooled = comparator.copy()

    if len(pooled) == 0:
        return _table_placeholder("comparator_rankings.csv (pooled)")

    # Sort by net_eppd descending, take top N
    if "net_eppd" in pooled.columns:
        pooled = pooled.sort_values("net_eppd", ascending=False).head(n)
    else:
        pooled = pooled.head(n)

    # Select display columns
    display_cols = [
        c
        for c in ["model", "net_eppd", "ci_low", "ci_high", "rank"]
        if c in pooled.columns
    ]
    if not display_cols:
        return _table_placeholder("comparator_rankings.csv")

    return _df_to_markdown(pooled[display_cols])


def _h2h_tier_summary_table(
    h2h_tier: pd.DataFrame | None,
) -> str:
    """Build a concise H2H tier summary table using team0/team1 labels."""
    if h2h_tier is None:
        return _table_placeholder("h2h_tier_summary.csv")

    required = {"model", "tier", "mean_delta"}
    if not required.issubset(h2h_tier.columns):
        return _table_placeholder("h2h_tier_summary.csv")

    # Rename model columns to team0-oriented labels for H2H context
    display = h2h_tier.copy()
    display = display.rename(columns={"model": "team0_model"})

    display_cols = [
        c
        for c in ["team0_model", "tier", "mean_delta", "mean_win_rate", "n_opponents"]
        if c in display.columns
    ]
    return _df_to_markdown(display[display_cols])


def _hypothesis_summary_table(
    outcomes: pd.DataFrame | None,
) -> str:
    """Build a concise hypothesis pass/fail summary."""
    if outcomes is None or len(outcomes) == 0:
        return "> No hypothesis outcomes available.\n"

    display_cols = [
        c for c in ["hypothesis_id", "description", "status"] if c in outcomes.columns
    ]
    if not display_cols:
        return _table_placeholder("hypothesis_outcomes.csv")

    return _df_to_markdown(outcomes[display_cols])


def generate_decision_report(
    tables_dir: Path,
    charts_dir: Path,
    chart_data_dir: Path | None = None,
    output_path: Path | None = None,
    rung: str = "?",
    mode: str = "QUICK",
) -> str:
    """Generate the 02_decision.md report.

    Produces a concise decision-focused report that synthesizes evidence
    from tables and charts into an advancement recommendation.

    Args:
        tables_dir: Directory containing ``*.csv`` tables.
        charts_dir: Directory containing ``*.png`` charts.
        chart_data_dir: Directory containing chart source CSVs (optional).
        output_path: If provided, write the report to this file.
        rung: Rung identifier (e.g., ``"R0"``, ``"R3"``).
        mode: Compute mode (e.g., ``"QUICK"``, ``"FULL"``).

    Returns:
        Rendered markdown decision report string.
    """
    # Read the key tables
    hypothesis_outcomes = _read_csv_safe(tables_dir / "hypothesis_outcomes.csv")
    comparator = _read_csv_safe(tables_dir / "comparator_rankings.csv")
    h2h_tier = _read_csv_safe(tables_dir / "h2h_tier_summary.csv")

    decision = _extract_advancement_decision(hypothesis_outcomes)

    lines: list[str] = []

    # Title
    lines.append(f"# Rung {rung} ({mode}) — Decision Report")
    lines.append("")

    # Advancement Decision
    lines.append("## Advancement Decision")
    lines.append("")
    lines.append(f"**{decision}**")
    lines.append("")

    # Evidence Summary
    lines.append("## Evidence Summary")
    lines.append("")

    # Comparator Standing
    lines.append("### Comparator Standing")
    lines.append("")
    lines.append(_top_n_comparator_table(comparator))
    lines.append("")
    lines.append(
        "See Chart 1 (Comparator Ranking Bars) and "
        "Chart 4 (Tail Risk Panel) for visual context."
    )
    lines.append("")

    # Head-to-Head Performance
    lines.append("### Head-to-Head Performance")
    lines.append("")
    lines.append(_h2h_tier_summary_table(h2h_tier))
    lines.append("")
    lines.append(
        "See Chart 3 (H2H Heatmap), Chart 2 (Delta Bars by Contract), "
        "and the intelligence-faceted H2H chart for tier-level analysis."
    )
    lines.append("")

    # Hypothesis Outcomes
    lines.append("### Hypothesis Outcomes")
    lines.append("")
    lines.append(_hypothesis_summary_table(hypothesis_outcomes))
    lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    if decision == "ADVANCE":
        lines.append(
            "All hypothesis checks passed. Evidence supports advancing "
            "to the next rung."
        )
    elif decision == "HALT":
        n_fail = 0
        if hypothesis_outcomes is not None and "status" in hypothesis_outcomes.columns:
            n_fail = (hypothesis_outcomes["status"].str.upper() == "FAIL").sum()
        lines.append(
            f"{n_fail} hypothesis check(s) failed. "
            "Review the failing checks and address root causes before "
            "re-running this rung."
        )
    elif decision == "HOLD":
        lines.append(
            "Some hypothesis checks have indeterminate status. "
            "Additional evidence or manual review is needed."
        )
    else:
        lines.append(
            "Hypothesis outcomes not yet available. "
            "Run the advance check pipeline to populate results."
        )
    lines.append("")

    # Supporting Evidence
    lines.append("## Supporting Evidence")
    lines.append("")
    lines.append("- Chart 1: Comparator Ranking Bars")
    lines.append("- Chart 2: Delta Bars by Contract")
    lines.append("- Chart 3: H2H Heatmap")
    lines.append("- Chart 4: Tail Risk Panel")
    lines.append("- Chart 5: Bid Behavior Panel")
    lines.append("- Chart 9: Intelligence-Faceted H2H")
    lines.append(
        "- Full tables: `tables/comparator_rankings.csv`, "
        "`tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`"
    )
    lines.append("")

    content = "\n".join(lines)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        logger.info("Wrote decision report: %s", output_path)

    return content
