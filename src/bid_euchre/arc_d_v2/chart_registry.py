"""Chart registry for Arc D v2 rung reports.

Defines the canonical 23-chart numbered registry. Chart numbers are stable
identifiers — they never change based on availability. Used by report.py
for numbered headings and by manifest.py for chart inventory.

Layout: Charts 1-3 (dashboards) are at the top level of charts/.
Charts 4-23 (standalone) live under charts/full_chart_suite/.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChartEntry:
    """A single chart in the registry."""

    number: int
    filename: str
    title: str
    required: bool
    source: str


CHART_REGISTRY: tuple[ChartEntry, ...] = (
    ChartEntry(
        1,
        "dashboard_competitive.png",
        "Competitive Dashboard",
        True,
        "canonical tables",
    ),
    ChartEntry(
        2,
        "dashboard_health.png",
        "Health Dashboard",
        True,
        "canonical tables + chart_data",
    ),
    ChartEntry(
        3,
        "dashboard_model_eval.png",
        "Model Evaluation Dashboard",
        True,
        "canonical tables + chart_data",
    ),
    ChartEntry(
        4,
        "full_chart_suite/comparator_ranking_bars.png",
        "Comparator Ranking Bars",
        True,
        "tables/comparator_rankings.csv",
    ),
    ChartEntry(
        5,
        "full_chart_suite/tail_risk_panel.png",
        "Tail Risk Panel",
        True,
        "tables/comparator_rankings.csv",
    ),
    ChartEntry(
        6,
        "full_chart_suite/delta_bars_by_contract.png",
        "H2H Delta by Contract",
        True,
        "tables/h2h_delta_matrix.csv",
    ),
    ChartEntry(
        7,
        "full_chart_suite/h2h_heatmap.png",
        "H2H Heatmap",
        True,
        "tables/h2h_delta_matrix.csv",
    ),
    ChartEntry(
        8,
        "full_chart_suite/h2h_ranking_scatter.png",
        "H2H Ranking Scatter",
        False,
        "tables/comparator_rankings.csv + h2h_tier_summary.csv",
    ),
    ChartEntry(
        9,
        "full_chart_suite/outcome_distributions.png",
        "Outcome Distributions",
        False,
        "chart_data/outcome_distributions.csv",
    ),
    ChartEntry(
        10,
        "full_chart_suite/seat_balance.png",
        "Seat Balance",
        False,
        "chart_data/seat_balance.csv",
    ),
    ChartEntry(
        11,
        "full_chart_suite/contract_mix_bars.png",
        "Contract Mix",
        True,
        "chart_data/contract_mix.csv",
    ),
    ChartEntry(
        12,
        "full_chart_suite/bid_behavior_panel.png",
        "Bid and Make Rates",
        True,
        "tables/behavior_summary.csv",
    ),
    ChartEntry(
        13,
        "full_chart_suite/bid_level_distribution.png",
        "Bid Level Distribution",
        False,
        "chart_data/bid_levels.csv",
    ),
    ChartEntry(
        14,
        "full_chart_suite/r2_by_contract.png",
        "R-squared by Contract",
        True,
        "tables/model_performance.csv",
    ),
    ChartEntry(
        15,
        "full_chart_suite/mae_by_contract.png",
        "MAE by Contract",
        True,
        "tables/model_performance.csv",
    ),
    ChartEntry(
        16,
        "full_chart_suite/pred_vs_actual.png",
        "Predicted vs Actual",
        False,
        "chart_data/predictions.csv",
    ),
    ChartEntry(
        17,
        "full_chart_suite/residual_distribution.png",
        "Residual Distribution",
        False,
        "chart_data/residuals.csv",
    ),
    ChartEntry(
        18,
        "full_chart_suite/calibration_curve.png",
        "Calibration Curve",
        False,
        "chart_data/calibration_bins.csv",
    ),
    ChartEntry(
        19,
        "full_chart_suite/selection_path.png",
        "Selection Path",
        False,
        "chart_data/selection_paths.csv",
    ),
    ChartEntry(
        20,
        "full_chart_suite/feature_importance.png",
        "Feature Importance",
        False,
        "chart_data/selection_paths.csv",
    ),
    ChartEntry(
        21,
        "full_chart_suite/decision_agreement.png",
        "Decision Agreement",
        False,
        "chart_data/decision_comparison.csv",
    ),
    ChartEntry(
        22,
        "full_chart_suite/disagreement_outcomes.png",
        "Disagreement Outcomes",
        False,
        "chart_data/disagreement_outcomes.csv",
    ),
    ChartEntry(
        23,
        "full_chart_suite/h2h_intelligence_faceted.png",
        "Intelligence-Faceted H2H",
        False,
        "tables/h2h_tier_summary.csv",
    ),
)


def get_chart_by_number(n: int) -> ChartEntry | None:
    """Look up a chart entry by its stable number."""
    for entry in CHART_REGISTRY:
        if entry.number == n:
            return entry
    return None


def get_chart_by_filename(filename: str) -> ChartEntry | None:
    """Look up a chart entry by its PNG filename (with or without prefix)."""
    for entry in CHART_REGISTRY:
        if entry.filename == filename:
            return entry
    # Also match by basename for backward compatibility
    for entry in CHART_REGISTRY:
        if entry.filename.endswith("/" + filename) or (
            "/" not in filename and entry.filename.split("/")[-1] == filename
        ):
            return entry
    return None
