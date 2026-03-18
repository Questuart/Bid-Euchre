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

from bid_euchre.arc_d_v2.chart_registry import get_chart_by_filename

logger = logging.getLogger(__name__)

# Column renames applied when rendering H2H tables in markdown.
# The underlying CSV schema is unchanged — only the report-facing labels change.
_H2H_COLUMN_RENAMES = {"model_a": "team0", "model_b": "team1"}

# Tables with more than this many rows are truncated in the report.
_TABLE_ROW_LIMIT = 12
_TABLE_ROW_SHOW = 10


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


def _bare_filename(chart_name: str) -> str:
    """Extract bare filename from a chart path (strip directory prefix)."""
    return chart_name.rsplit("/", 1)[-1]


def _chart_placeholder(chart_name: str) -> str:
    """Return a placeholder for a missing chart."""
    entry = get_chart_by_filename(_bare_filename(chart_name))
    if entry is not None:
        return (
            f"### Chart {entry.number}. {entry.title}\n\n"
            f"*Chart not available — source data absent.*\n"
        )
    return f"> [chart_name={chart_name}] not yet generated\n"


def _df_to_markdown(
    df: pd.DataFrame,
    float_format: str = "%.4f",
    *,
    table_name: str = "",
    column_renames: dict[str, str] | None = None,
) -> str:
    """Convert a DataFrame to a markdown table string.

    Args:
        df: The DataFrame to render.
        float_format: Format string for float columns.
        table_name: If non-empty and the table exceeds _TABLE_ROW_LIMIT rows,
            the output is truncated with a note pointing to this CSV file.
        column_renames: Optional column header renames for the rendered output.
            Does NOT modify the underlying DataFrame or CSV.
    """
    # Format float columns
    formatted = df.copy()
    for col in formatted.select_dtypes(include=["float64", "float32"]).columns:
        formatted[col] = formatted[col].apply(
            lambda x: float_format % x if pd.notna(x) else ""
        )

    # Truncate long tables
    truncated = False
    if table_name and len(formatted) > _TABLE_ROW_LIMIT:
        formatted = formatted.head(_TABLE_ROW_SHOW)
        truncated = True

    # Apply column renames for display
    display_cols = list(formatted.columns)
    if column_renames:
        display_cols = [column_renames.get(c, c) for c in display_cols]

    # Build header
    header = "| " + " | ".join(display_cols) + " |"
    separator = "| " + " | ".join(["---"] * len(display_cols)) + " |"

    # Build rows
    rows = []
    for _, row in formatted.iterrows():
        cells = [str(row[c]) if pd.notna(row[c]) else "" for c in formatted.columns]
        rows.append("| " + " | ".join(cells) + " |")

    parts = [header, separator] + rows
    if truncated:
        parts.append("")
        parts.append(f"*Full table omitted from markdown — see `tables/{table_name}`*")

    return "\n".join(parts) + "\n"


def _chart_embed(charts_dir: Path, chart_name: str) -> str:
    """Return markdown image embed or placeholder for a chart.

    The ``chart_name`` may include the ``full_chart_suite/`` prefix for
    standalone charts (4-23). The file is looked up relative to charts_dir.
    """
    entry = get_chart_by_filename(_bare_filename(chart_name))
    chart_path = charts_dir / chart_name
    if chart_path.exists():
        if entry is not None:
            return (
                f"### Chart {entry.number}. {entry.title}\n\n"
                f"![{entry.title}](charts/{chart_name})\n"
            )
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
        for dash_file, _dash_title in dashboards:
            lines.append(_chart_embed(charts_dir, dash_file))
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
        lines.append(_df_to_markdown(data_sanity, table_name="data_sanity.csv"))
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
        lines.append(_df_to_markdown(model_perf, table_name="model_performance.csv"))
    else:
        lines.append(_table_placeholder("model_performance.csv"))
    lines.append("")

    # R-squared and MAE charts
    lines.append(_chart_embed(charts_dir, "full_chart_suite/r2_by_contract.png"))
    lines.append(_chart_embed(charts_dir, "full_chart_suite/mae_by_contract.png"))
    lines.append("")

    # section 3 Offline Diagnostics
    lines.extend(
        [
            "## 3. Offline Diagnostics",
            "",
        ]
    )
    for chart_name in [
        "full_chart_suite/pred_vs_actual.png",
        "full_chart_suite/residual_distribution.png",
        "full_chart_suite/calibration_curve.png",
        "full_chart_suite/feature_importance.png",
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
        "full_chart_suite/shap_summary.png",
        "full_chart_suite/shap_dependence_top5.png",
        "full_chart_suite/selection_path.png",
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
        "full_chart_suite/decision_agreement.png",
        "full_chart_suite/disagreement_outcomes.png",
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
        lines.append(_df_to_markdown(comparator, table_name="comparator_rankings.csv"))
    else:
        lines.append(_table_placeholder("comparator_rankings.csv"))
    lines.append("")

    lines.append(
        _chart_embed(charts_dir, "full_chart_suite/comparator_ranking_bars.png")
    )
    lines.append(_chart_embed(charts_dir, "full_chart_suite/tail_risk_panel.png"))
    lines.append("")

    # section 7 H2H Battery
    lines.extend(
        [
            "## 7. H2H Battery",
            "",
        ]
    )
    # Charts first, compact table excerpt below
    lines.append(
        _chart_embed(charts_dir, "full_chart_suite/delta_bars_by_contract.png")
    )
    lines.append(_chart_embed(charts_dir, "full_chart_suite/h2h_heatmap.png"))
    lines.append("")

    h2h = _read_csv_safe(tables_dir / "h2h_delta_matrix.csv")
    if h2h is not None:
        lines.append(
            "<details><summary>Full H2H Delta Matrix (click to expand)</summary>\n"
        )
        lines.append(
            _df_to_markdown(
                h2h,
                table_name="h2h_delta_matrix.csv",
                column_renames=_H2H_COLUMN_RENAMES,
            )
        )
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
        lines.append(_df_to_markdown(behavior, table_name="behavior_summary.csv"))
    else:
        lines.append(_table_placeholder("behavior_summary.csv"))
    lines.append("")

    behavior_contract = _read_csv_safe(tables_dir / "behavior_by_contract.csv")
    if behavior_contract is not None:
        lines.append("### Behavior by Contract\n")
        lines.append(
            _df_to_markdown(behavior_contract, table_name="behavior_by_contract.csv")
        )
    else:
        lines.append(_table_placeholder("behavior_by_contract.csv"))
    lines.append("")

    lines.append(_chart_embed(charts_dir, "full_chart_suite/bid_behavior_panel.png"))
    lines.append(_chart_embed(charts_dir, "full_chart_suite/contract_mix_bars.png"))
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
        lines.append(_df_to_markdown(sanity, table_name="sanity_bounds_check.csv"))
    else:
        lines.append(_table_placeholder("sanity_bounds_check.csv"))
    lines.append("")

    # section 10 Data Quality Notes
    chart_data_dir = report_dir / "chart_data"
    has_degraded = False
    notes: list[str] = []

    # Check for synthetic outcome distributions
    status_file = chart_data_dir / "outcome_distributions.status"
    if status_file.exists():
        status_text = status_file.read_text().strip()
        if "degraded" in status_text:
            has_degraded = True
            notes.append(
                "- **Outcome distributions (Chart 9):** synthetic data — "
                "parquet-backed real distributions unavailable for this bundle"
            )

    # Check for sanity bound failures that are expected
    if sanity is not None and "status" in sanity.columns:
        failures = sanity[sanity["status"].str.upper() == "FAIL"]
        if len(failures) > 0:
            for _, row in failures.iterrows():
                check = row.get("check_name", "unknown")
                notes.append(
                    f"- **Sanity: {check}** — failed. "
                    "This may be expected for small sample sizes or early rungs."
                )

    if has_degraded or notes:
        lines.extend(
            [
                "## 10. Data Quality Notes",
                "",
            ]
        )
        for note in notes:
            lines.append(note)
        lines.append("")

    # Gate status marker — required by repo linter for promotion registry docs
    lines.append("<!-- gate_status: data sanity checks in \u00a71 above -->")
    lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
#  Decision report (02_decision.md)
# ──────────────────────────────────────────────


def _extract_advancement_decision(
    hypothesis_outcomes: pd.DataFrame | None,
    mode: str = "QUICK",
) -> str:
    """Determine advancement decision from hypothesis outcomes.

    Returns one of: ADVANCE, HOLD, HALT, PRELIMINARY, PENDING.

    When *mode* is ``"QUICK"`` and hypothesis outcomes are absent or empty,
    returns ``"PRELIMINARY"`` instead of ``"PENDING"`` to signal that a
    data-driven triage summary should be generated.
    """
    if hypothesis_outcomes is None or len(hypothesis_outcomes) == 0:
        return "PRELIMINARY" if mode == "QUICK" else "PENDING"

    if "status" not in hypothesis_outcomes.columns:
        return "PRELIMINARY" if mode == "QUICK" else "PENDING"

    statuses = hypothesis_outcomes["status"].str.upper().tolist()
    if not statuses:
        return "PRELIMINARY" if mode == "QUICK" else "PENDING"

    # Exclude SKIP hypotheses (excluded models) from the decision
    evaluated = [s for s in statuses if s != "SKIP"]
    if not evaluated:
        return "PRELIMINARY" if mode == "QUICK" else "PENDING"

    n_fail = sum(1 for s in evaluated if s == "FAIL")
    n_pass = sum(1 for s in evaluated if s == "PASS")

    if n_fail > 0:
        return "HALT"
    if n_pass == len(evaluated):
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

    return _df_to_markdown(outcomes[display_cols], table_name="hypothesis_outcomes.csv")


def _build_preliminary_triage(
    tables_dir: Path,
    comparator: pd.DataFrame | None,
    h2h_tier: pd.DataFrame | None,
) -> list[str]:
    """Build a data-driven preliminary triage for QUICK mode.

    When hypothesis outcomes are absent (typical for QUICK runs that skip
    the advance-check pipeline), this summarises available evidence so the
    decision report is informative rather than a blank "PENDING".
    """
    parts: list[str] = []
    parts.append("**PRELIMINARY — formal advance-check evidence absent**")
    parts.append("")
    parts.append("Data-driven triage based on available QUICK evidence:")
    parts.append("")

    # Comparator performance
    if comparator is not None and "net_eppd" in comparator.columns:
        if "facet" in comparator.columns:
            pooled = comparator[comparator["facet"] == "pooled"]
        else:
            pooled = comparator
        if len(pooled) > 0:
            top = pooled.sort_values("net_eppd", ascending=False).head(3)
            for _, row in top.iterrows():
                model = row.get("model", "?")
                net = row["net_eppd"]
                parts.append(f"- **{model}** net_eppd = {net:.3f}")

    # H2H win rates
    if h2h_tier is not None and "mean_win_rate" in h2h_tier.columns:
        best = h2h_tier.sort_values("mean_win_rate", ascending=False).head(1)
        if len(best) > 0:
            row = best.iloc[0]
            parts.append(
                f"- Best H2H win rate: **{row.get('model', '?')}** "
                f"({row['mean_win_rate']:.1%} vs {row.get('tier', '?')} tier)"
            )

    # Data sanity
    data_sanity = _read_csv_safe(tables_dir / "data_sanity.csv")
    if data_sanity is not None:
        if "status" in data_sanity.columns:
            n_fail = (data_sanity["status"].str.upper() == "FAIL").sum()
            if n_fail > 0:
                parts.append(f"- Data sanity: **{n_fail} failure(s)** detected")
            else:
                parts.append("- Data sanity: all checks passed")

    parts.append("")
    parts.append("**Watch items / caveats:**")
    parts.append("")
    parts.append("- Formal hypothesis tests not yet executed")
    parts.append("- QUICK sample sizes may be insufficient for tail analysis")
    parts.append(
        "- Run the advance-check pipeline (`--mode FULL`) for definitive evidence"
    )

    return parts


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

    decision = _extract_advancement_decision(hypothesis_outcomes, mode=mode)

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
    comp_bars = get_chart_by_filename("comparator_ranking_bars.png")
    comp_ref = (
        f"Chart {comp_bars.number} ({comp_bars.title})"
        if comp_bars
        else "Comparator Ranking Bars"
    )
    tail_risk = get_chart_by_filename("tail_risk_panel.png")
    tail_ref = (
        f"Chart {tail_risk.number} ({tail_risk.title})"
        if tail_risk
        else "Tail Risk Panel"
    )
    lines.append(f"See {comp_ref} and {tail_ref} for visual context.")
    lines.append("")

    # Head-to-Head Performance
    lines.append("### Head-to-Head Performance")
    lines.append("")
    lines.append(_h2h_tier_summary_table(h2h_tier))
    lines.append("")
    h2h_heatmap = get_chart_by_filename("h2h_heatmap.png")
    h2h_heat_ref = (
        f"Chart {h2h_heatmap.number} ({h2h_heatmap.title})"
        if h2h_heatmap
        else "H2H Heatmap"
    )
    delta_bars = get_chart_by_filename("delta_bars_by_contract.png")
    delta_ref = (
        f"Chart {delta_bars.number} ({delta_bars.title})"
        if delta_bars
        else "Delta Bars by Contract"
    )
    intel_h2h = get_chart_by_filename("h2h_intelligence_faceted.png")
    intel_ref = (
        f"Chart {intel_h2h.number} ({intel_h2h.title})"
        if intel_h2h
        else "Intelligence-Faceted H2H"
    )
    lines.append(
        f"See {h2h_heat_ref}, {delta_ref}, and {intel_ref} for tier-level analysis."
    )
    lines.append("")

    # Hypothesis Outcomes
    lines.append("### Hypothesis Outcomes")
    lines.append("")
    lines.append(_hypothesis_summary_table(hypothesis_outcomes))
    lines.append("")

    # Data Sanity Status
    data_sanity = _read_csv_safe(tables_dir / "data_sanity.csv")
    if data_sanity is not None and "status" in data_sanity.columns:
        failures = data_sanity[data_sanity["status"].str.upper() == "FAIL"]
        if len(failures) > 0:
            lines.append("### Data Sanity")
            lines.append("")
            n_fail = len(failures)
            n_total = len(data_sanity)
            lines.append(f"**{n_fail}/{n_total} sanity checks failed.**")
            lines.append("")
            for _, row in failures.iterrows():
                check = row.get("check_name", "unknown")
                lines.append(f"- {check}: FAIL")
            lines.append("")
            lines.append(
                "*Note: some sanity check failures may be expected for conservative "
                "thresholds or early rungs with limited sample sizes.*"
            )
            lines.append("")

    # Recommendation
    lines.append("## Recommendation")
    lines.append("")
    if decision == "ADVANCE":
        n_skip = 0
        if hypothesis_outcomes is not None and "status" in hypothesis_outcomes.columns:
            n_skip = (hypothesis_outcomes["status"].str.upper() == "SKIP").sum()
        if n_skip > 0:
            lines.append(
                f"All evaluated hypothesis checks passed ({n_skip} skipped). "
                "Evidence supports advancing to the next rung."
            )
        else:
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
    elif decision == "PRELIMINARY":
        lines.extend(_build_preliminary_triage(tables_dir, comparator, h2h_tier))
    else:
        lines.append(
            "Hypothesis outcomes not yet available. "
            "Run the advance check pipeline to populate results."
        )
    lines.append("")

    # Supporting Evidence — chart numbers from registry
    lines.append("## Supporting Evidence")
    lines.append("")
    evidence_charts = [
        "comparator_ranking_bars.png",
        "delta_bars_by_contract.png",
        "h2h_heatmap.png",
        "tail_risk_panel.png",
        "bid_behavior_panel.png",
        "h2h_intelligence_faceted.png",
    ]
    for chart_file in evidence_charts:
        entry = get_chart_by_filename(chart_file)
        if entry:
            lines.append(f"- Chart {entry.number}: {entry.title}")
        else:
            basename = chart_file.replace(".png", "").replace("_", " ")
            lines.append(f"- {basename}")
    lines.append(
        "- Full tables: `tables/comparator_rankings.csv`, "
        "`tables/h2h_delta_matrix.csv`, `tables/h2h_tier_summary.csv`"
    )
    lines.append("")

    # Gate status marker — required by repo linter for promotion registry docs
    lines.append("<!-- gate_status: data sanity checks in \u00a71 above -->")
    lines.append("")

    content = "\n".join(lines)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
        logger.info("Wrote decision report: %s", output_path)

    return content
